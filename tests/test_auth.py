import pytest

from jarvis import auth


@pytest.fixture
def supabase_says(monkeypatch):
    monkeypatch.setenv("JARVIS_ALLOWED_EMAILS", "Teammate@colorado.edu, other@colorado.edu")
    auth._trusted_until.clear()

    def answer(email):
        user = {"email": email, "email_confirmed_at": "2026-11-12T00:00:00Z"}
        monkeypatch.setattr(auth, "_call", lambda path, body=None, token=None: user)

    yield answer
    auth._trusted_until.clear()


def test_teammate_token_is_accepted(supabase_says):
    supabase_says("teammate@colorado.edu")
    assert auth.is_signed_in("token-a")


def test_valid_token_from_outsider_is_rejected(supabase_says):
    supabase_says("stranger@example.com")
    assert not auth.is_signed_in("token-b")


def test_no_allowlist_lets_nobody_in(supabase_says, monkeypatch):
    monkeypatch.setenv("JARVIS_ALLOWED_EMAILS", "")
    supabase_says("teammate@colorado.edu")
    assert not auth.is_signed_in("token-c")


def test_cache_never_outlives_the_token(supabase_says):
    import base64, json, time
    expires = int(time.time()) + 30
    payload = base64.urlsafe_b64encode(json.dumps({"exp": expires}).encode()).decode().rstrip("=")
    token = f"header.{payload}.signature"
    supabase_says("teammate@colorado.edu")
    assert auth.is_signed_in(token)
    assert auth._trusted_until[token] == expires


def test_refresh_for_outsider_is_rejected(monkeypatch):
    monkeypatch.setenv("JARVIS_ALLOWED_EMAILS", "teammate@colorado.edu")
    auth._trusted_until.clear()

    def supabase(path, body=None, token=None):
        if path.startswith("token"):
            return {"access_token": "new-access", "refresh_token": "new-refresh"}
        return {"email": "stranger@example.com", "email_confirmed_at": "2026-11-12T00:00:00Z"}

    monkeypatch.setattr(auth, "_call", supabase)
    with pytest.raises(auth.AuthError):
        auth.refresh("stolen-or-outsider-refresh")


def test_unconfirmed_teammate_email_is_rejected(monkeypatch):
    monkeypatch.setenv("JARVIS_ALLOWED_EMAILS", "teammate@colorado.edu")
    auth._trusted_until.clear()
    monkeypatch.setattr(auth, "_call", lambda path, body=None, token=None: {"email": "teammate@colorado.edu", "email_confirmed_at": None})
    assert not auth.is_signed_in("token-d")
