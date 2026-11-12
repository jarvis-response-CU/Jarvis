# References:
#   https://fastapi.tiangolo.com/tutorial/body/
#   https://fastapi.tiangolo.com/tutorial/static-files/
#   https://docs.pydantic.dev/latest/concepts/fields/

import urllib.parse

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from jarvis import __version__, auth
from jarvis.config import PROJECT_ROOT, load_settings
from jarvis.simulations.fire.damage_run import estimate_damage, load_structures
from jarvis.simulations.fire.map_run import run_at_point

WEB_DIR = PROJECT_ROOT / "web"
ACCESS_COOKIE = "jarvis_access"
REFRESH_COOKIE = "jarvis_refresh"
VERIFIER_COOKIE = "jarvis_pkce"
OPEN_PATHS = {"/login", "/health", "/auth/google", "/auth/callback"}

app = FastAPI(title="Jarvis", version=__version__)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


# Fly ends HTTPS at its proxy, so the scheme the browser used comes in a header.
def is_https(request):
    return request.headers.get("x-forwarded-proto", request.url.scheme) == "https"


def set_session(response, request, access_token, refresh_token):
    for name, value in [(ACCESS_COOKIE, access_token), (REFRESH_COOKIE, refresh_token)]:
        response.set_cookie(
            name, value, max_age=30 * 24 * 3600, httponly=True, secure=is_https(request), samesite="lax"
        )


# Everything but the sign-in page and the health check needs a signed-in user.
@app.middleware("http")
async def require_sign_in(request: Request, call_next):
    if request.url.path in OPEN_PATHS:
        return await call_next(request)

    access_token = request.cookies.get(ACCESS_COOKIE)
    if await run_in_threadpool(auth.is_signed_in, access_token):
        return await call_next(request)

    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if refresh_token:
        try:
            new_access, new_refresh = await run_in_threadpool(auth.refresh, refresh_token)
        except auth.AuthError:
            pass
        else:
            response = await call_next(request)
            set_session(response, request, new_access, new_refresh)
            return response

    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Sign in first"}, status_code=401)
    return RedirectResponse("/login", status_code=303)


def login_page(error=""):
    page = (WEB_DIR / "login.html").read_text()
    if error:
        page = page.replace("<!--error-->", f'<p class="error">{error}</p>')
    return HTMLResponse(page)


@app.get("/login", include_in_schema=False)
def show_login() -> HTMLResponse:
    return login_page()


@app.post("/login", include_in_schema=False)
async def submit_login(request: Request):
    form = urllib.parse.parse_qs((await request.body()).decode())
    email = form.get("email", [""])[0].strip()
    password = form.get("password", [""])[0]
    try:
        access_token, refresh_token = await run_in_threadpool(auth.sign_in, email, password)
    except auth.AuthError:
        return login_page("Wrong email or password.")
    response = RedirectResponse("/", status_code=303)
    set_session(response, request, access_token, refresh_token)
    return response


@app.get("/auth/google", include_in_schema=False)
def start_google(request: Request):
    callback = f"{'https' if is_https(request) else 'http'}://{request.headers['host']}/auth/callback"
    url, verifier = auth.google_sign_in(callback)
    response = RedirectResponse(url, status_code=303)
    # Only needed until Google sends the browser back, a minute or two at most.
    response.set_cookie(
        VERIFIER_COOKIE, verifier, max_age=600, httponly=True, secure=is_https(request), samesite="lax"
    )
    return response


@app.get("/auth/callback", include_in_schema=False)
async def finish_google(request: Request, code: str = ""):
    verifier = request.cookies.get(VERIFIER_COOKIE, "")
    try:
        access_token, refresh_token = await run_in_threadpool(auth.finish_google_sign_in, code, verifier)
    except auth.AuthError:
        return login_page("That Google account can't sign in here. Use your CU email.")
    response = RedirectResponse("/", status_code=303)
    set_session(response, request, access_token, refresh_token)
    response.delete_cookie(VERIFIER_COOKIE)
    return response


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


class FireRun(BaseModel):
    lat: float = Field(gt=-90, lt=90)
    lng: float = Field(ge=-180, le=180)
    hours: float = Field(gt=0, le=12)
    wind_speed_mps: float = Field(ge=0, le=40)
    wind_from_deg: float = Field(ge=0, le=360)


@app.post("/api/fire/simulate")
def simulate_fire(run: FireRun) -> dict:
    result = run_at_point(run.lat, run.lng, run.hours, run.wind_speed_mps, run.wind_from_deg)
    try:
        result["damage"] = estimate_damage(result, load_structures())
    except FileNotFoundError:
        # The raw county files aren't downloaded; the spread still works without damage.
        result["damage"] = None
    return result


def run() -> None:
    settings = load_settings()
    uvicorn.run(
        "jarvis.server:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
