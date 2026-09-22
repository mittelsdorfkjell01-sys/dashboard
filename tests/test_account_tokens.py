"""Account action links must be scoped to one purpose and expire."""

import uuid

import jwt
import pytest

from app.account.security import create_account_action_token, decode_account_action_token


def test_account_action_token_rejects_other_purpose():
    token = create_account_action_token(uuid.uuid4(), purpose="verify", version=2)
    assert decode_account_action_token(token, "verify")["ver"] == 2
    with pytest.raises(jwt.InvalidTokenError):
        decode_account_action_token(token, "reset")


def test_account_action_token_rejects_expired_link(monkeypatch):
    from app.account import security

    real_datetime = security.dt.datetime

    class FutureDateTime(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return real_datetime.now(tz) - security.dt.timedelta(hours=25)

    monkeypatch.setattr(security.dt, "datetime", FutureDateTime)
    token = create_account_action_token(uuid.uuid4(), purpose="verify", version=0)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_account_action_token(token, "verify")
