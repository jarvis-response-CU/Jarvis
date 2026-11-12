import base64
import json

import pytest

from jarvis import auth


def token_with_amr(method):
    payload = base64.urlsafe_b64encode(json.dumps({"amr": [{"method": method}], "exp": 9999999999}).encode())
    return f"header.{payload.decode().rstrip('=')}.signature"


@pytest.fixture
def supabase_says(monkeypatch):
    monkeypatch.setenv("JARVIS_ALLOWED_EMAILS", "Teammate@colorado.edu, other@colorado.edu")
    monkeypatch.setenv("JARVIS_ALLOWED_DOMAINS", "")
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
    monkeypatch.setenv("JARVIS_ALLOWED_DOMAINS", "")
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
    monkeypatch.setenv("JARVIS_ALLOWED_DOMAINS", "")
    auth._trusted_until.clear()
    monkeypatch.setattr(auth, "_call", lambda path, body=None, token=None: {"email": "teammate@colorado.edu", "email_confirmed_at": None})
    assert not auth.is_signed_in("token-d")


def test_any_cu_email_is_allowed(monkeypatch):
    monkeypatch.setenv("JARVIS_ALLOWED_EMAILS", "brody@gmail.com")
    monkeypatch.setenv("JARVIS_ALLOWED_DOMAINS", "colorado.edu")
    assert auth.is_allowed("new.student@Colorado.edu", via_google=True)
    assert not auth.is_allowed("new.student@colorado.edu", via_google=False)
    assert auth.is_allowed("brody@gmail.com")
    assert not auth.is_allowed("someone@gmail.com", via_google=True)
    assert not auth.is_allowed("tricky@colorado.edu.evil.com", via_google=True)
    assert not auth.is_allowed("", via_google=True)


def test_google_sign_in_sends_a_hash_of_the_verifier(monkeypatch):
    import base64, hashlib, urllib.parse
    monkeypatch.setenv("JARVIS_SUPABASE_URL", "https://example.supabase.co")
    url, verifier = auth.google_sign_in("https://jarvis.example/auth/callback")
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    assert url.startswith("https://example.supabase.co/auth/v1/authorize?")
    assert query["provider"] == ["google"]
    assert query["code_challenge"] == [expected]
    assert verifier not in url


def test_cu_password_account_off_the_list_is_rejected(monkeypatch):
    monkeypatch.setenv("JARVIS_ALLOWED_EMAILS", "")
    monkeypatch.setenv("JARVIS_ALLOWED_DOMAINS", "colorado.edu")
    auth._trusted_until.clear()
    confirmed = {"email": "typed.in@colorado.edu", "email_confirmed_at": "2026-11-12T00:00:00Z"}
    monkeypatch.setattr(auth, "_call", lambda path, body=None, token=None: {**confirmed, "app_metadata": {"providers": ["email"]}})
    assert not auth.is_signed_in("token-e")
    google = {"provider": "google", "identity_data": {"email": "typed.in@colorado.edu", "email_verified": True}}
    monkeypatch.setattr(auth, "_call", lambda path, body=None, token=None: {**confirmed, "identities": [google]})
    assert auth.is_signed_in(token_with_amr("oauth"))


def test_email_changed_after_google_sign_in_is_rejected(monkeypatch):
    monkeypatch.setenv("JARVIS_ALLOWED_EMAILS", "")
    monkeypatch.setenv("JARVIS_ALLOWED_DOMAINS", "colorado.edu")
    auth._trusted_until.clear()
    google_gmail = {"provider": "google", "identity_data": {"email": "someone@gmail.com", "email_verified": True}}
    user = {"email": "switched@colorado.edu", "email_confirmed_at": "2026-11-12T00:00:00Z",
            "app_metadata": {"providers": ["google"]}, "identities": [google_gmail]}
    monkeypatch.setattr(auth, "_call", lambda path, body=None, token=None: user)
    assert not auth.is_signed_in("token-g")


def test_password_session_on_google_linked_cu_account_is_rejected(monkeypatch):
    monkeypatch.setenv("JARVIS_ALLOWED_EMAILS", "")
    monkeypatch.setenv("JARVIS_ALLOWED_DOMAINS", "colorado.edu")
    auth._trusted_until.clear()
    google = {"provider": "google", "identity_data": {"email": "student@colorado.edu", "email_verified": True}}
    user = {"email": "student@colorado.edu", "email_confirmed_at": "2026-11-12T00:00:00Z", "identities": [google]}
    monkeypatch.setattr(auth, "_call", lambda path, body=None, token=None: user)
    assert not auth.is_signed_in(token_with_amr("password"))
    assert auth.is_signed_in(token_with_amr("oauth"))
