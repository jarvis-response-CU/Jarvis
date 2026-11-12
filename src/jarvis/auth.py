# References:
#   https://supabase.com/docs/reference/self-hosting-auth/introduction
#   https://supabase.com/docs/guides/auth/sessions
#   https://docs.python.org/3/library/urllib.request.html

"""Sign-in through Supabase Auth's REST API.

The browser keeps Supabase's access and refresh tokens in cookies; the server
asks Supabase whether an access token is still good and swaps an expired one
for a new pair with the refresh token.
"""

import json
import time
import urllib.error
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


def sign_in(email, password):
    """Access and refresh tokens for a correct email and password."""
    if not email or not password:
        raise AuthError("email and password are required")
    session = _call("token?grant_type=password", {"email": email, "password": password})
    return session["access_token"], session["refresh_token"]


def refresh(refresh_token):
    """A new token pair, for when the access token has expired."""
    session = _call("token?grant_type=refresh_token", {"refresh_token": refresh_token})
    return session["access_token"], session["refresh_token"]


def is_signed_in(access_token):
    if not access_token:
        return False
    now = time.time()
    if _trusted_until.get(access_token, 0) > now:
        return True
    try:
        _call("user", token=access_token)
    except AuthError:
        _trusted_until.pop(access_token, None)
        return False
    _trusted_until[access_token] = now + TRUSTED_FOR_SECONDS
    return True
