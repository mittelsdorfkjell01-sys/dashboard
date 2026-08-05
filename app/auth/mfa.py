"""TOTP enrollment and verification for admin accounts."""

from __future__ import annotations

import base64
import hashlib
import time
from datetime import datetime, timedelta, timezone

import pyotp
from cryptography.fernet import Fernet, InvalidToken
from pyotp.utils import strings_equal

from app.config import get_settings
from app.models import AdminUser


def _fernet() -> Fernet:
    settings = get_settings()
    key = settings.mfa_encryption_key
    if not key:
        # Development-only fallback. Production admin deployments reject a
        # missing dedicated key in Settings validation.
        key = base64.urlsafe_b64encode(
            hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest()
        ).decode("ascii")
    return Fernet(key.encode("ascii"))


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("ascii")).decode("ascii")


def decrypt_secret(user: AdminUser) -> str:
    if not user.totp_secret_encrypted:
        raise ValueError("Für dieses Konto ist kein TOTP-Secret hinterlegt.")
    try:
        return _fernet().decrypt(user.totp_secret_encrypted.encode("ascii")).decode("ascii")
    except (InvalidToken, ValueError) as exc:
        raise ValueError("Das TOTP-Secret konnte nicht entschlüsselt werden.") from exc


def begin_enrollment(user: AdminUser) -> tuple[str, str]:
    secret = pyotp.random_base32()
    user.totp_secret_encrypted = encrypt_secret(secret)
    user.totp_enabled_at = None
    user.totp_last_step = None
    uri = pyotp.TOTP(secret).provisioning_uri(
        name=user.email, issuer_name="Surfwinddate Dashboard"
    )
    return secret, uri


def verify_code(user: AdminUser, code: str, *, consume: bool = True) -> bool:
    if not code or not code.isdigit() or len(code) != 6:
        return False
    totp = pyotp.TOTP(decrypt_secret(user), interval=30)
    current_step = int(time.time() // totp.interval)
    now = datetime.now(timezone.utc)
    for offset in (-1, 0, 1):
        if strings_equal(totp.at(now + timedelta(seconds=offset * totp.interval)), code):
            step = current_step + offset
            if consume and user.totp_last_step is not None and step <= user.totp_last_step:
                return False
            if consume:
                user.totp_last_step = step
            return True
    return False


def enable(user: AdminUser, code: str) -> bool:
    if not verify_code(user, code):
        return False
    user.totp_enabled_at = datetime.now(timezone.utc)
    user.session_version += 1
    return True


def disable(user: AdminUser) -> None:
    user.totp_secret_encrypted = None
    user.totp_enabled_at = None
    user.totp_last_step = None
    user.session_version += 1
