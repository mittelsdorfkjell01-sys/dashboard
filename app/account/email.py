"""Transactional mail for public account ownership and recovery flows."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from app.config import get_settings


class MailUnavailable(RuntimeError):
    pass


def send_account_link(address: str, *, purpose: str, token: str) -> None:
    settings = get_settings()
    if not settings.account_smtp_host or not settings.account_smtp_from:
        raise MailUnavailable("E-Mail-Versand ist derzeit nicht eingerichtet.")

    routes = {
        "verify": ("E-Mail-Adresse bestätigen", "bestaetigen"),
        "change_email": ("Neue E-Mail-Adresse bestätigen", "bestaetigen"),
        "reset": ("Passwort zurücksetzen", "passwort-zuruecksetzen"),
    }
    subject, route = routes[purpose]
    link = f"{settings.account_public_origin.rstrip('/')}/{route}?token={quote(token, safe='')}&purpose={purpose}"
    _send(address, f"Surfwinddata: {subject}",
          f"Öffne diesen Link, um {subject.lower()}:\n\n{link}\n\n"
          "Falls du das nicht angefordert hast, ignoriere diese Nachricht.")


def send_account_notice(address: str, *, subject: str, body: str) -> None:
    # Notification mails (e.g. a decision on a spot proposal) are not purely
    # transactional, so they carry a List-Unsubscribe header pointing at the
    # account settings opt-out and a mailto fallback (RFC 2369 / 8058). Auth
    # mails via send_account_link stay header-free — they are strictly
    # transactional and have no opt-out.
    _send(address, f"Surfwinddata: {subject}", body, with_unsubscribe=True)


def _unsubscribe_header() -> str | None:
    settings = get_settings()
    origin = settings.account_public_origin.rstrip("/")
    targets = [f"<{origin}/konto/einstellungen>"]
    if settings.account_smtp_from:
        targets.append(f"<mailto:{settings.account_smtp_from}?subject=unsubscribe>")
    return ", ".join(targets) if targets else None


def _send(address: str, subject: str, body: str, *, with_unsubscribe: bool = False) -> None:
    settings = get_settings()
    if not settings.account_smtp_host or not settings.account_smtp_from:
        raise MailUnavailable("E-Mail-Versand ist derzeit nicht eingerichtet.")
    message = EmailMessage()
    message["From"] = settings.account_smtp_from
    message["To"] = address
    message["Subject"] = subject
    if with_unsubscribe:
        header = _unsubscribe_header()
        if header:
            message["List-Unsubscribe"] = header
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.account_smtp_host, settings.account_smtp_port, timeout=10) as smtp:
            if settings.account_smtp_starttls:
                smtp.starttls()
            if settings.account_smtp_username:
                smtp.login(settings.account_smtp_username, settings.account_smtp_password or "")
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise MailUnavailable("E-Mail konnte derzeit nicht versendet werden.") from exc
