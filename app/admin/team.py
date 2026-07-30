"""Team notes + activity feed for the admin back office.

* Team notes — short messages an operator posts for the team (tiles on overview).
* Activity — a merged, most-recent-first feed of the real audited changes from
  ``spot_audit`` and ``moderation_audit`` (both only hold actual mutations, so no
  every-click noise). Read-only; shown under user management.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BoardTask, ModerationAudit, Spot, SpotAudit, TeamNote


# --- team notes ------------------------------------------------------------

def list_notes(db: Session, *, limit: int = 30) -> list[dict]:
    rows = db.scalars(
        select(TeamNote).order_by(TeamNote.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": str(n.id),
            "author": n.author,
            "body": n.body,
            "created_at": n.created_at.isoformat(),
        }
        for n in rows
    ]


def create_note(db: Session, *, author: str | None, body: str) -> TeamNote:
    if not (body and body.strip()):
        raise ValueError("Die Nachricht darf nicht leer sein.")
    note = TeamNote(author=author, body=body.strip())
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def delete_note(db: Session, note_id) -> bool:
    note = db.get(TeamNote, note_id)
    if note is None:
        return False
    db.delete(note)
    db.commit()
    return True


# --- board tasks (kanban) --------------------------------------------------

def _task_view(t: BoardTask) -> dict:
    return {
        "id": str(t.id),
        "title": t.title,
        "body": t.body,
        "status": t.status,
        "author": t.author,
        "created_at": t.created_at.isoformat(),
    }


def list_tasks(db: Session) -> list[dict]:
    rows = db.scalars(
        select(BoardTask).order_by(BoardTask.created_at.desc())
    ).all()
    return [_task_view(t) for t in rows]


def create_task(db: Session, *, title: str, body: str | None, author: str | None) -> BoardTask:
    if not (title and title.strip()):
        raise ValueError("Titel darf nicht leer sein.")
    task = BoardTask(
        title=title.strip(),
        body=(body or "").strip() or None,
        status="open",
        author=author,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_task(
    db: Session, task_id, *, status: str | None = None,
    title: str | None = None, body: str | None = None,
) -> BoardTask | None:
    task = db.get(BoardTask, task_id)
    if task is None:
        return None
    if status in ("open", "done"):
        task.status = status
    if title is not None and title.strip():
        task.title = title.strip()
    if body is not None:
        task.body = body.strip() or None
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task_id) -> bool:
    task = db.get(BoardTask, task_id)
    if task is None:
        return False
    db.delete(task)
    db.commit()
    return True


# --- activity feed ---------------------------------------------------------

_SPOT_ACTIONS = {
    "create": "Spot angelegt",
    "update": "Spot bearbeitet",
    "publish": "Spot veröffentlicht",
    "unpublish": "Spot offline genommen",
    "archive": "Spot archiviert",
    "image": "Spot-Bild geändert",
    "override": "Wert überschrieben",
    "revert": "Override entfernt",
}
_MOD_ACTIONS = {
    "submission_approve": "Einreichung freigegeben",
    "submission_reject": "Einreichung abgelehnt",
    "image_approve": "Hero-Bild freigegeben",
    "image_reject": "Bild abgelehnt",
    "image_remove": "Bild entfernt",
    "image_dismiss_reports": "Meldungen verworfen",
    "tip_hide": "Tipp verborgen",
    "tip_restore": "Tipp wiederhergestellt",
    "rating_hide": "Bewertung verborgen",
    "rating_restore": "Bewertung wiederhergestellt",
}


def _changed_fields(action: str, changes) -> list[str]:
    """The field keys touched by a spot audit entry — for 'what was edited'.

    Empty where the action label already says it all (create/publish/image/…);
    populated for edits and overrides.
    """
    if action in ("create", "publish", "unpublish", "archive", "image"):
        return []
    if not isinstance(changes, dict):
        return []
    if isinstance(changes.get("fields"), list):  # update_spot
        return [str(f) for f in changes["fields"]]
    if isinstance(changes.get("editorial_keys"), list):  # update_spot_metadata
        return [f"editorial.{f}" for f in changes["editorial_keys"]]
    if "field" in changes and isinstance(changes["field"], str):  # override/revert
        return [changes["field"]]
    return [k for k in changes.keys() if k not in ("auto", "from", "to")]


def activity(db: Session, *, limit: int = 30, q: str | None = None) -> list[dict]:
    """Most-recent audited changes across spots and moderation, merged. Actors
    are resolved to display names. When ``q`` is given, a wider window is
    searched and filtered by actor name/email, target and label."""
    from app.models import AdminUser

    fetch = 200 if q else limit
    name_by_email = {
        u.email: u.display_name for u in db.scalars(select(AdminUser)).all()
    }

    spot_rows = db.execute(
        select(
            SpotAudit.actor, SpotAudit.action, SpotAudit.created_at,
            SpotAudit.changes, Spot.name, Spot.id,
        )
        .join(Spot, Spot.id == SpotAudit.spot_id)
        .order_by(SpotAudit.created_at.desc())
        .limit(fetch)
    ).all()
    mod_rows = db.execute(
        select(
            ModerationAudit.actor, ModerationAudit.action,
            ModerationAudit.created_at, ModerationAudit.target_type,
            ModerationAudit.note,
        )
        .order_by(ModerationAudit.created_at.desc())
        .limit(fetch)
    ).all()

    items: list[dict] = []
    for actor, action, at, changes, spot_name, spot_id in spot_rows:
        items.append({
            "actor": name_by_email.get(actor, actor),
            "actor_email": actor,
            "action": action,
            "label": _SPOT_ACTIONS.get(action, action),
            "target": spot_name,
            "target_id": str(spot_id),
            "kind": "spot",
            "fields": _changed_fields(action, changes),
            "at": at.isoformat() if at else None,
        })
    for actor, action, at, target_type, note in mod_rows:
        items.append({
            "actor": name_by_email.get(actor, actor),
            "actor_email": actor,
            "action": action,
            "label": _MOD_ACTIONS.get(action, action),
            "target": note or target_type,
            "target_id": None,
            "kind": "moderation",
            "fields": [],
            "at": at.isoformat() if at else None,
        })

    items.sort(key=lambda x: x["at"] or "", reverse=True)

    if q:
        ql = q.lower()
        items = [
            it for it in items
            if ql in (it["actor"] or "").lower()
            or ql in (it["actor_email"] or "").lower()
            or ql in (it["target"] or "").lower()
            or ql in (it["label"] or "").lower()
        ]
        return items[:100]
    return items[:limit]
