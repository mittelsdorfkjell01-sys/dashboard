"""Account domain logic: visitor sign-up/profile, favourites, spot proposals.

Service functions flush but do not commit — the API endpoint owns the
transaction (mirrors :mod:`app.auth.service`). Validation errors raise
:class:`ValueError` (mapped to 400 at the API) or the specific errors below.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session

from app.account.security import (
    create_account_action_token, decode_account_action_token,
    hash_password, verify_password,
)
from app.config import get_settings
from app.password_policy import ensure_password_safe
from app.models import AppUser, CommunityUpvote, Favorite, LocalTip, RecommendationLog, Region, Spot, SpotImage, SpotRating, SpotSubmission, UserEvent
from app.models.app_user import normalize_email


class EmailExistsError(ValueError):
    """Duplicate email on registration / profile change (→ 409 at the API)."""


class AuthError(ValueError):
    """Bad credentials or wrong current password (→ 401/400 at the API)."""


# --- accounts --------------------------------------------------------------

def get_by_email(db: Session, email: str) -> AppUser | None:
    return db.execute(
        select(AppUser).where(AppUser.email == normalize_email(email))
    ).scalar_one_or_none()


def _validate_password(password: str) -> None:
    ensure_password_safe(password, min_length=get_settings().app_password_min_length)


def _validate_email(email: str) -> str:
    email = normalize_email(email)
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("Bitte eine gültige E-Mail eingeben.")
    return email


def register(
    db: Session, *, email: str, password: str, display_name: str | None
) -> AppUser:
    email = _validate_email(email)
    _validate_password(password)
    password_hash = hash_password(password)
    if get_by_email(db, email) is not None or db.scalar(
        select(AppUser.id).where(AppUser.pending_email == email)
    ):
        raise EmailExistsError("Für diese E-Mail existiert bereits ein Konto.")
    user = AppUser(
        email=email,
        password_hash=password_hash,
        display_name=(display_name or "").strip() or email.split("@")[0],
    )
    db.add(user)
    db.flush()
    return user


def authenticate(db: Session, email: str, password: str) -> AppUser:
    user = get_by_email(db, email)
    if user is None or not user.is_active or not verify_password(
        password, user.password_hash
    ):
        raise AuthError("E-Mail oder Passwort ist falsch.")
    if user.email_verified_at is None:
        raise AuthError("Bitte bestätige zuerst deine E-Mail-Adresse.")
    return user


def update_profile(
    db: Session,
    user: AppUser,
    *,
    display_name: str | None = None,
    email: str | None = None,
) -> AppUser:
    if email is not None and _validate_email(email) != user.email:
        raise ValueError("E-Mail-Adressen werden über die Bestätigungsfunktion geändert.")
    if display_name is not None:
        cleaned = display_name.strip()
        if cleaned:
            user.display_name = cleaned
    db.flush()
    return user


def start_email_change(db: Session, user: AppUser, email: str, password: str) -> str:
    if not verify_password(password, user.password_hash):
        raise AuthError("Das Passwort ist falsch.")
    email = _validate_email(email)
    if email == user.email:
        raise ValueError("Die neue Adresse ist bereits deine aktuelle Adresse.")
    if get_by_email(db, email) or db.scalar(select(AppUser.id).where(
        AppUser.pending_email == email, AppUser.id != user.id
    )):
        raise EmailExistsError("Diese E-Mail-Adresse ist nicht verfügbar.")
    user.pending_email = email
    user.email_token_version += 1
    db.flush()
    return create_account_action_token(user.id, purpose="change_email", version=user.email_token_version, email=email)


def registration_token(user: AppUser) -> str:
    return create_account_action_token(user.id, purpose="verify", version=user.email_token_version, email=user.email)


def confirm_email(db: Session, token: str, *, password: str | None = None) -> AppUser:
    from datetime import datetime, timezone
    from jwt import PyJWTError

    for purpose in ("verify", "change_email"):
        try:
            payload = decode_account_action_token(token, purpose)
            break
        except PyJWTError:
            continue
    else:
        raise AuthError("Bestätigungslink ist ungültig oder abgelaufen.")
    try:
        user = db.get(AppUser, uuid.UUID(payload["sub"]))
    except (ValueError, KeyError, TypeError):
        user = None
    if user is None or payload.get("ver") != user.email_token_version:
        raise AuthError("Bestätigungslink ist ungültig oder abgelaufen.")
    if purpose == "verify":
        if user.email_verified_at is not None or payload.get("email") != user.email or not password:
            raise AuthError("Bestätigungslink ist ungültig oder abgelaufen.")
        _validate_password(password)
        # The mail recipient chooses the final password; a third party who
        # pre-registered this address cannot later sign in with its own choice.
        user.password_hash = hash_password(password)
        user.email_verified_at = datetime.now(timezone.utc)
        user.session_version += 1
    else:
        if not user.pending_email or payload.get("email") != user.pending_email:
            raise AuthError("Bestätigungslink ist ungültig oder abgelaufen.")
        user.email = user.pending_email
        user.pending_email = None
        user.session_version += 1
    user.email_token_version += 1
    db.flush()
    return user


def reset_token(user: AppUser) -> str:
    return create_account_action_token(user.id, purpose="reset", version=user.session_version)


def reset_password(db: Session, token: str, password: str) -> None:
    from jwt import PyJWTError

    try:
        payload = decode_account_action_token(token, "reset")
        user = db.get(AppUser, uuid.UUID(payload["sub"]))
    except (PyJWTError, ValueError, KeyError, TypeError):
        user = None
    if user is None or user.email_verified_at is None or payload.get("ver") != user.session_version:
        raise AuthError("Zurücksetzungslink ist ungültig oder abgelaufen.")
    _validate_password(password)
    user.password_hash = hash_password(password)
    user.session_version += 1
    db.flush()


def update_preferences(db: Session, user: AppUser, preferences: dict) -> dict:
    # Serialize concurrent patches from the same account across tabs/devices.
    db.refresh(user, with_for_update=True)
    user.preferences = {**(user.preferences or {}), **preferences}
    db.flush()
    return user.preferences


def list_my_activity(db: Session, user: AppUser) -> dict:
    """Recent account-owned community content for the private profile."""
    ratings = db.scalars(select(SpotRating).where(
        SpotRating.app_user_id == user.id
    ).order_by(SpotRating.created_at.desc()).limit(5)).all()
    tips = db.scalars(select(LocalTip).where(
        LocalTip.app_user_id == user.id
    ).order_by(LocalTip.created_at.desc()).limit(5)).all()
    images = db.scalars(select(SpotImage).where(
        SpotImage.app_user_id == user.id
    ).order_by(SpotImage.created_at.desc()).limit(5)).all()
    corrections = db.scalars(select(SpotSubmission).where(
        SpotSubmission.app_user_id == user.id,
        SpotSubmission.payload["kind"].astext == "spot_edit_suggestion",
    ).order_by(SpotSubmission.created_at.desc()).limit(5)).all()
    items = [
        {"id": str(row.id), "kind": kind, "spotId": str(row.spot_id) if row.spot_id else None,
         "createdAt": row.created_at.isoformat(), "status": row.status}
        for kind, rows in (("rating", ratings), ("tip", tips), ("image", images))
        for row in rows
    ]
    items.extend({
        "id": str(row.id), "kind": "correction",
        "spotId": (row.payload or {}).get("spot_id"),
        "createdAt": row.created_at.isoformat(), "status": row.status,
        "reviewNote": row.review_note,
    } for row in corrections)
    items.sort(key=lambda item: item["createdAt"], reverse=True)
    return {"items": items[:8]}


def change_password(db: Session, user: AppUser, old_pw: str, new_pw: str) -> None:
    if not verify_password(old_pw, user.password_hash):
        raise AuthError("Das aktuelle Passwort ist falsch.")
    ensure_password_safe(new_pw, min_length=get_settings().app_password_min_length)
    user.password_hash = hash_password(new_pw)
    user.session_version += 1
    db.flush()


def export_account_data(db: Session, user: AppUser) -> dict:
    """Return every account-linked record without credentials or abuse hashes."""
    ratings = db.scalars(select(SpotRating).where(SpotRating.app_user_id == user.id)).all()
    tips = db.scalars(select(LocalTip).where(LocalTip.app_user_id == user.id)).all()
    submissions = db.scalars(
        select(SpotSubmission).where(SpotSubmission.app_user_id == user.id)
    ).all()
    images = db.scalars(select(SpotImage).where(SpotImage.app_user_id == user.id)).all()
    favorites = db.scalars(select(Favorite).where(Favorite.app_user_id == user.id)).all()
    upvotes = db.scalars(select(CommunityUpvote).where(CommunityUpvote.app_user_id == user.id)).all()
    events = db.scalars(select(UserEvent).where(UserEvent.app_user_id == user.id).order_by(UserEvent.created_at)).all()
    recommendation_rows = db.scalars(
        select(RecommendationLog)
        .where(RecommendationLog.app_user_id == user.id)
        .order_by(RecommendationLog.created_at)
    ).all()
    from app.account import rider as rider_service

    rider_profile = rider_service._profile(db, user)
    sport_profiles = []
    if rider_profile is not None:
        from app.models import RiderSportProfile

        rows = db.scalars(select(RiderSportProfile).where(
            RiderSportProfile.rider_profile_id == rider_profile.id
        ).order_by(RiderSportProfile.sport)).all()
        sport_profiles = [
            rider_service.sport_profile_payload(row, row.sport, rider_profile.profile_version)
            for row in rows
        ]

    def stamp(row) -> dict:
        data = {
            "id": str(row.id),
            "created_at": row.created_at.isoformat(),
        }
        if getattr(row, "updated_at", None):
            data["updated_at"] = row.updated_at.isoformat()
        return data

    return {
        "account": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
            "created_at": user.created_at.isoformat(),
            "preferences": user.preferences or {},
        },
        "rider_profile": rider_service.profile_payload(rider_profile),
        "rider_sport_profiles": sport_profiles,
        "gear": rider_service.list_gear(db, user),
        "events": [
            {
                "id": str(row.id), "type": row.type,
                "spot_id": str(row.spot_id) if row.spot_id else None,
                "surface": row.surface, "context": row.context or {},
                "recommendation_log_id": (
                    str(row.recommendation_log_id) if row.recommendation_log_id else None
                ),
                "created_at": row.created_at.isoformat(),
            }
            for row in events
        ],
        "recommendation_log": [
            {
                "id": str(row.id),
                "spot_id": str(row.spot_id),
                "surface": row.surface,
                "audience_segment": row.audience_segment,
                "window_start": row.window_start.isoformat(),
                "components": row.components,
                "params_version": row.params_version,
                "profile_fingerprint": row.profile_fingerprint,
                "created_at": row.created_at.isoformat(),
            }
            for row in recommendation_rows
        ],
        "favorites": [{**stamp(row), "spot_id": str(row.spot_id)} for row in favorites],
        "upvotes": [
            {**stamp(row), "tip_id": str(row.tip_id) if row.tip_id else None,
             "rating_id": str(row.rating_id) if row.rating_id else None}
            for row in upvotes
        ],
        "ratings": [
            {
                **stamp(row), "spot_id": str(row.spot_id), "stars": row.stars,
                "skill_level": row.skill_level, "sport": row.sport,
                "conditions": row.conditions, "status": row.status,
            }
            for row in ratings
        ],
        "tips": [
            {
                **stamp(row), "spot_id": str(row.spot_id),
                "parent_id": str(row.parent_id) if row.parent_id else None,
                "body": row.body, "title": row.title, "status": row.status,
            }
            for row in tips
        ],
        "submissions": [
            {
                **stamp(row), "payload": row.payload, "status": row.status,
                "review_note": row.review_note,
                "resulting_spot_id": str(row.resulting_spot_id) if row.resulting_spot_id else None,
            }
            for row in submissions
        ],
        "images": [
            {
                **stamp(row), "spot_id": str(row.spot_id), "url": row.url,
                "kind": row.kind, "status": row.status, "credit": row.credit,
                "license_version": row.license_version,
                "license_accepted_at": row.license_accepted_at.isoformat()
                if row.license_accepted_at else None,
            }
            for row in images
        ],
    }


def delete_account(db: Session, user: AppUser, password: str) -> None:
    """Anonymize retained UGC, remove favourites, and delete the account."""
    if not verify_password(password, user.password_hash):
        raise AuthError("Das Passwort ist falsch.")

    for model, email_field, name_field in (
        (SpotRating, "author_email", "author_name"),
        (LocalTip, "author_email", "author_name"),
        (SpotSubmission, "submitter_email", "submitter_name"),
    ):
        rows = db.scalars(select(model).where(model.app_user_id == user.id)).all()
        for row in rows:
            setattr(row, email_field, None)
            setattr(row, name_field, "Gelöschtes Konto")
            row.ip_hash = None
            row.app_user_id = None

    for image in db.scalars(select(SpotImage).where(SpotImage.app_user_id == user.id)).all():
        image.submitter_email = None
        image.ip_hash = None
        image.app_user_id = None

    db.execute(delete(Favorite).where(Favorite.app_user_id == user.id))
    db.delete(user)
    db.flush()


# --- favourites ------------------------------------------------------------

def list_favorites(db: Session, user: AppUser) -> list[dict]:
    """The user's favourites, newest first, resolved against the live spot.

    Each row is ``{id, name, region, sports, addedAt}`` (the shape the frontend
    account layer expects). A favourite whose spot was deleted is skipped — the
    cascade normally removes it, so this only guards a race.
    """
    rows = db.execute(
        select(Favorite, Spot)
        .join(Spot, Spot.id == Favorite.spot_id)
        .where(Favorite.app_user_id == user.id, Spot.status == "published")
        .order_by(Favorite.created_at.desc())
    ).all()
    out: list[dict] = []
    for fav, spot in rows:
        region = spot.region
        region_label = (
            f"{region.name}, {region.country}"
            if region and region.country
            else (region.name if region else None)
        )
        out.append(
            {
                "id": str(spot.id),
                "name": spot.name,
                "region": region_label,
                "sports": list(spot.sports or []),
                "addedAt": fav.created_at.isoformat(),
            }
        )
    return out


def add_favorite(db: Session, user: AppUser, spot_id: uuid.UUID) -> bool:
    """Save a spot. Idempotent — returns True if newly added, False if it was
    already saved. Raises ValueError when the spot does not exist."""
    if not db.execute(select(exists().where(Spot.id == spot_id, Spot.status == "published"))).scalar():
        raise ValueError("Spot nicht gefunden.")
    already = db.execute(
        select(exists().where(
            Favorite.app_user_id == user.id, Favorite.spot_id == spot_id
        ))
    ).scalar()
    if already:
        return False
    db.add(Favorite(app_user_id=user.id, spot_id=spot_id))
    db.flush()
    return True


def remove_favorite(db: Session, user: AppUser, spot_id: uuid.UUID) -> None:
    db.execute(
        delete(Favorite).where(
            Favorite.app_user_id == user.id, Favorite.spot_id == spot_id
        )
    )
    db.flush()


# --- spot proposals --------------------------------------------------------

def list_my_submissions(db: Session, user: AppUser, *, limit: int = 50, offset: int = 0) -> list[dict]:
    """The user's spot proposals, newest first, as ``{id, name, status,
    createdAt}``. The display name comes from the stored payload."""
    subs = db.execute(
        select(SpotSubmission)
        .where(SpotSubmission.app_user_id == user.id,
               SpotSubmission.payload["kind"].astext.is_distinct_from("spot_edit_suggestion"))
        .order_by(SpotSubmission.created_at.desc())
        .limit(limit).offset(offset)
    ).scalars().all()
    resulting_ids = [s.resulting_spot_id for s in subs if s.resulting_spot_id]
    published_ids = set(db.scalars(select(Spot.id).where(
        Spot.id.in_(resulting_ids), Spot.status == "published"
    )).all()) if resulting_ids else set()
    return [
        {
            "id": str(s.id),
            "name": (s.payload or {}).get("name") or "Unbenannter Spot",
            "status": s.status,
            "createdAt": s.created_at.isoformat(),
            "updatedAt": s.updated_at.isoformat() if s.updated_at else None,
            "reviewedAt": s.reviewed_at.isoformat() if s.reviewed_at else None,
            "reviewNote": s.review_note,
            "resultingSpotId": str(s.resulting_spot_id) if s.resulting_spot_id else None,
            "publishedSpotId": str(s.resulting_spot_id)
            if s.resulting_spot_id in published_ids else None,
            "regionId": (s.payload or {}).get("region_id"),
            "lat": (s.payload or {}).get("lat"),
            "lon": (s.payload or {}).get("lon"),
            "sports": (s.payload or {}).get("sports") or [],
        }
        for s in subs
    ]


def create_named_submission(
    db: Session, user: AppUser, name: str, *, region_id: uuid.UUID | None = None,
    lat: float | None = None, lon: float | None = None, sports: list[str] | None = None,
) -> dict:
    """Store an account-owned proposal for editorial review."""
    clean = " ".join((name or "").split())
    if not clean:
        raise ValueError("Bitte gib einen Spotnamen ein.")
    if (lat is None) != (lon is None) or (lat is not None and region_id is None):
        raise ValueError("Bitte gib Region und Kartenposition zusammen an.")
    if region_id is not None and not db.scalar(select(Region.id).where(
        Region.id == region_id, Region.status == "published"
    )):
        raise ValueError("Region nicht gefunden.")
    existing = db.scalar(select(Spot.id).where(
        func.lower(Spot.name) == clean.lower(),
        Spot.status == "published",
        *((Spot.region_id == region_id,) if region_id else ()),
    ).limit(1))
    if existing:
        raise ValueError("Diesen Spot gibt es bereits. Bitte suche ihn zuerst im Katalog.")
    previous = db.scalar(select(SpotSubmission.id).where(
        SpotSubmission.app_user_id == user.id,
        SpotSubmission.status == "pending",
        func.lower(SpotSubmission.payload["name"].astext) == clean.lower(),
    ).limit(1))
    if previous:
        raise ValueError("Du hast diesen Spot bereits vorgeschlagen.")
    payload = {"name": clean}
    if region_id is not None:
        payload["region_id"] = str(region_id)
    if lat is not None:
        payload.update(lat=lat, lon=lon)
    if sports:
        payload["sports"] = sports
    sub = SpotSubmission(
        payload=payload,
        submitter_name=user.display_name,
        submitter_email=user.email,
        app_user_id=user.id,
        status="pending",
    )
    db.add(sub)
    db.flush()
    db.refresh(sub)  # load server_default created_at / status
    return {
        "id": str(sub.id),
        "name": clean,
        "status": sub.status,
        "createdAt": sub.created_at.isoformat(),
        "regionId": payload.get("region_id"),
        "lat": lat, "lon": lon, "sports": sports or [],
        "reviewNote": None, "reviewedAt": None,
        "resultingSpotId": None, "publishedSpotId": None,
    }


def withdraw_submission(db: Session, user: AppUser, submission_id: uuid.UUID) -> None:
    sub = db.get(SpotSubmission, submission_id)
    if sub is None or sub.app_user_id != user.id:
        raise LookupError("Vorschlag nicht gefunden.")
    if sub.status != "pending":
        raise ValueError("Nur ungeprüfte Vorschläge können zurückgezogen werden.")
    sub.status = "withdrawn"
    db.flush()
