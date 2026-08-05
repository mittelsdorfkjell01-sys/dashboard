"""Shared password policy, including privacy-preserving breach checks."""

from __future__ import annotations

import hashlib

import httpx

from app.config import get_settings

_COMMON = {
    "password1234",
    "passwort1234",
    "qwerty123456",
    "admin1234567",
    "surfwinddate",
}


def ensure_password_safe(password: str, *, min_length: int = 12) -> None:
    if len(password or "") < min_length:
        raise ValueError(f"Das Passwort muss mindestens {min_length} Zeichen haben.")
    if password.casefold() in _COMMON:
        raise ValueError("Dieses Passwort ist zu häufig. Bitte wähle ein anderes.")
    if not get_settings().password_breach_check_enabled:
        return

    digest = hashlib.sha1(password.encode("utf-8"), usedforsecurity=False).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]
    try:
        response = httpx.get(
            f"https://api.pwnedpasswords.com/range/{prefix}",
            headers={"Add-Padding": "true", "User-Agent": "Surfwinddate-Password-Policy"},
            timeout=3.0,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(
            "Die Passwort-Sicherheitsprüfung ist gerade nicht erreichbar. Bitte erneut versuchen."
        ) from exc
    if any(line.partition(":")[0] == suffix for line in response.text.splitlines()):
        raise ValueError(
            "Dieses Passwort ist aus einem Datenleck bekannt. Bitte wähle ein anderes."
        )
