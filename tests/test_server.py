import pytest
from fastapi.testclient import TestClient

from jarvis import auth
from jarvis.server import app

client = TestClient(app)


@pytest.fixture
def signed_in(monkeypatch):
    monkeypatch.setattr(auth, "is_signed_in", lambda token: token == "good")
    client.cookies.set("jarvis_access", "good")
    yield
    client.cookies.clear()


def test_index_serves_page(signed_in):
    response = client.get("/")
    assert response.status_code == 200
    assert "Jarvis" in response.text


def test_static_serves_main_module(signed_in):
    response = client.get("/static/js/main.js")
    assert response.status_code == 200
    assert "javascript" in response.headers["content-type"]


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_signed_out_page_redirects_to_login(monkeypatch):
    monkeypatch.setattr(auth, "is_signed_in", lambda token: False)
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_signed_out_api_is_401(monkeypatch):
    monkeypatch.setattr(auth, "is_signed_in", lambda token: False)
    response = client.post("/api/fire/simulate", json={})
    assert response.status_code == 401


def test_login_page_is_open():
    response = client.get("/login")
    assert response.status_code == 200
    assert 'action="/login"' in response.text


def test_wrong_password_shows_error(monkeypatch):
    def reject(email, password):
        raise auth.AuthError("nope")

    monkeypatch.setattr(auth, "sign_in", reject)
    response = client.post("/login", data={"email": "a@b.co", "password": "x"})
    assert response.status_code == 200
    assert "Wrong email or password" in response.text


def test_good_login_sets_cookies(monkeypatch):
    monkeypatch.setattr(auth, "sign_in", lambda email, password: ("access", "refresh"))
    response = client.post("/login", data={"email": "a@b.co", "password": "root"}, follow_redirects=False)
    assert response.status_code == 303
    assert "jarvis_access=access" in response.headers.get_list("set-cookie")[0]
    client.cookies.clear()


def test_google_start_redirects_and_keeps_verifier(monkeypatch):
    monkeypatch.setattr(auth, "google_sign_in", lambda redirect_to: (f"https://supabase.example/authorize?to={redirect_to}", "verifier"))
    response = client.get("/auth/google", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].endswith("/auth/callback")
    assert "jarvis_pkce=verifier" in response.headers["set-cookie"]
    client.cookies.clear()


def test_google_callback_for_outsider_shows_error(monkeypatch):
    def reject(code, verifier):
        raise auth.AuthError("not allowed")

    monkeypatch.setattr(auth, "finish_google_sign_in", reject)
    response = client.get("/auth/callback?code=abc")
    assert response.status_code == 200
    assert "Use your CU email" in response.text
