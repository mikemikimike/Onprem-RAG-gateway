"""The standalone AskIISc app (askiisc_chat, :9000) with BACKEND=gateway must forward the signed-in user's
identity, like the gateway's own /chat. It used to call stream_via_gateway(message, tier) without the email,
so every user of that app shared one cache owner and per-user semantic-cache isolation was lost; cached
answers could not be regenerated either (no token forwarded)."""

import asyncio
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(ROOT, "askiisc_chat"))
os.environ.setdefault("SESSION_SECRET", "x" * 40)

app_mod = pytest.importorskip("askiisc.app")


@pytest.fixture
def captured(monkeypatch):
    calls = []

    def fake_stream(query, tier, user_email="", regenerate_token=None):
        calls.append({"query": query, "tier": tier, "user_email": user_email, "regenerate_token": regenerate_token})

        async def gen():
            yield "data: {}\n\n"
        return gen()

    monkeypatch.setattr(app_mod, "stream_via_gateway", fake_stream)
    monkeypatch.setattr(app_mod.C, "BACKEND", "gateway")
    monkeypatch.setattr(app_mod.C, "REQUIRE_LOGIN", False)
    return calls


def test_signed_in_user_email_and_regenerate_token_are_forwarded(captured, monkeypatch):
    monkeypatch.setattr(app_mod, "current_user", lambda request: {"email": "alice@iisc.ac.in", "name": "Alice", "sub": "a"})
    asyncio.run(app_mod.chat(app_mod.ChatReq(message="What is graphene?", regenerate_token="tok123"), None))
    assert captured == [{"query": "What is graphene?", "tier": "internal", "user_email": "alice@iisc.ac.in",
                         "regenerate_token": "tok123"}]


def test_two_users_are_distinguished(captured, monkeypatch):
    for email in ("alice@iisc.ac.in", "bob@iisc.ac.in"):
        monkeypatch.setattr(app_mod, "current_user", lambda request, e=email: {"email": e, "name": e, "sub": e})
        asyncio.run(app_mod.chat(app_mod.ChatReq(message="What is graphene?"), None))
    assert [c["user_email"] for c in captured] == ["alice@iisc.ac.in", "bob@iisc.ac.in"]


def test_signed_out_user_sends_no_identity(captured, monkeypatch):
    monkeypatch.setattr(app_mod, "current_user", lambda request: None)
    asyncio.run(app_mod.chat(app_mod.ChatReq(message="What is graphene?"), None))
    assert captured[0]["user_email"] == ""
