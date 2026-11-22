# References:
#   https://supabase.com/docs/reference/self-hosting-auth/introduction
#   https://supabase.com/docs/guides/auth/sessions
#   https://supabase.com/docs/guides/auth/social-login/auth-google
#   https://supabase.com/docs/guides/auth/sessions/pkce-flow
#   https://datatracker.ietf.org/doc/html/rfc7636
#   https://docs.python.org/3/library/urllib.request.html

"""Sign-in through Supabase Auth's REST API.

The browser keeps Supabase's access and refresh tokens in cookies; the server
asks Supabase whether an access token is still good and swaps an expired one
for a new pair with the refresh token.
"""

import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from jarvis.config import load_settings

# A token Supabase already accepted isn't asked about again for a few minutes,
# so every map tile and module request doesn't turn into a call to Supabase.
TRUSTED_FOR_SECONDS = 5 * 60
_trusted_until = {}


class AuthError(Exception):
    pass


def _call(path, body=None, token=None):
    settings = load_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise AuthError("JARVIS_SUPABASE_URL and JARVIS_SUPABASE_ANON_KEY aren't set")

    headers = {"apikey": settings.supabase_anon_key, "Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode()

    request = urllib.request.Request(f"{settings.supabase_url}/auth/v1/{path}", data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)
    except urllib.error.HTTPError as err:
        raise AuthError(f"Supabase answered {err.code} for {path}") from None
    except urllib.error.URLError as err:
        raise AuthError(f"couldn't reach Supabase: {err.reason}") from None
    # A timeout while reading the reply isn't wrapped in URLError.
    except TimeoutError:
        raise AuthError(f"Supabase didn't answer {path} in time") from None


def sign_in(email, password):
    """Access and refresh tokens for a correct email and password on the team list."""
    if not email or not password:
        raise AuthError("email and password are required")
    session = _call("token?grant_type=password", {"email": email, "password": password})
    if not is_signed_in(session["access_token"]):
        raise AuthError(f"{email} isn't on the team list")
    return session["access_token"], session["refresh_token"]


def google_sign_in(redirect_to):
    """Where to send the browser for Google, and the verifier to keep until it comes back.

    PKCE: Supabase gets a hash of a random verifier now and the verifier itself
    when the code is exchanged, so a code that leaks on the way back is useless alone.
    """
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    params = urllib.parse.urlencode({
        "provider": "google",
        "redirect_to": redirect_to,
        "code_challenge": challenge,
        "code_challenge_method": "s256",
    })
    return f"{load_settings().supabase_url}/auth/v1/authorize?{params}", verifier


def finish_google_sign_in(auth_code, verifier):
    """Access and refresh tokens for the code Google sent back, if the account is allowed in."""
    if not auth_code or not verifier:
        raise AuthError("the sign-in link is missing its code or verifier")
    session = _call("token?grant_type=pkce", {"auth_code": auth_code, "code_verifier": verifier})
    if not is_signed_in(session["access_token"]):
        raise AuthError("that Google account isn't allowed in")
    return session["access_token"], session["refresh_token"]


def is_allowed(email, via_google=False):
    """On the team list, or a Google-verified address at a school domain (any CU account).

    The domain rule is Google-only because Google has checked the person owns
    the address; a typed-in email would only be as safe as Supabase's confirmation setting.
    """
    settings = load_settings()
    email = (email or "").lower()
    if email in settings.allowed_emails:
        return True
    domain = email.rpartition("@")[2]
    return via_google and bool(domain) and domain in settings.allowed_domains


def has_google_verified_email(user):
    """True when a Google identity on this account verified the account's own email.

    Checked on the identity, not the account, because an account's email can be
    changed after a Google sign-in under some other address.
    """
    email = (user.get("email") or "").lower()
    for identity in user.get("identities") or []:
        if identity.get("provider") != "google":
            continue
        data = identity.get("identity_data") or {}
        if data.get("email_verified") is True and (data.get("email") or "").lower() == email:
            return True
    return False


def refresh(refresh_token):
    """A new token pair, for when the access token has expired."""
    session = _call("token?grant_type=refresh_token", {"refresh_token": refresh_token})
    if not is_signed_in(session["access_token"]):
        raise AuthError("refreshed user isn't on the team list")
    return session["access_token"], session["refresh_token"]


def is_signed_in(access_token):
    if not access_token:
        return False
    now = time.time()
    if _trusted_until.get(access_token, 0) > now:
        return True
    try:
        user = _call("user", token=access_token)
    except AuthError:
        _trusted_until.pop(access_token, None)
        return False
    # Anyone can make a Supabase account with the public key, so a real token
    # isn't enough: the email has to be confirmed and allowed in too.
    if not user.get("email_confirmed_at"):
        return False
    # The domain rule needs this session itself to come from a Google sign-in, not
    # just a Google identity somewhere on the account: someone could make a password
    # account under a student's email before the student ever signs in with Google.
    via_google = signed_in_with_oauth(access_token) and has_google_verified_email(user)
    if not is_allowed(user.get("email"), via_google=via_google):
        return False
    # Requests are checked on several threads at once, so another one may have
    # dropped the same stale entry already.
    for token, until in list(_trusted_until.items()):
        if until <= now:
            _trusted_until.pop(token, None)
    _trusted_until[access_token] = min(now + TRUSTED_FOR_SECONDS, _expires_at(access_token))
    return True


# Supabase has already vouched for the token before these run; they only read its claims.
def _claims(access_token):
    try:
        payload = access_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError):
        return {}


# The token's own expiry, so the cache never trusts it past that.
def _expires_at(access_token):
    return _claims(access_token).get("exp", 0)


# How the session was started, from the token's amr claim ("password", "oauth", ...).
def signed_in_with_oauth(access_token):
    methods = _claims(access_token).get("amr") or []
    for entry in methods:
        if isinstance(entry, dict) and entry.get("method") == "oauth":
            return True
    return False
