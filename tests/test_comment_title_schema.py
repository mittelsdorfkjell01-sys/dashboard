from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.community import TipIn, TipOut


def test_optional_comment_title_round_trip() -> None:
    payload = TipIn(body="Hilfreicher Kommentar", title="Beste Zeit")
    row = SimpleNamespace(
        id=uuid4(), body=payload.body, title=payload.title, author_name="Anonym",
        created_at=datetime.now(timezone.utc), parent_id=None,
    )
    assert TipOut.of(row).title == "Beste Zeit"


def test_legacy_comment_without_title_stays_compatible() -> None:
    assert TipIn(body="Alter Kommentar").title is None


def test_comment_title_is_limited_to_120_characters() -> None:
    with pytest.raises(ValidationError):
        TipIn(body="Text", title="x" * 121)
