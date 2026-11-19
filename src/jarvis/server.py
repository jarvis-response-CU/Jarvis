# References:
#   https://fastapi.tiangolo.com/tutorial/body/
#   https://fastapi.tiangolo.com/tutorial/static-files/
#   https://docs.pydantic.dev/latest/concepts/fields/

import urllib.parse
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from jarvis import __version__, auth
from jarvis.config import PROJECT_ROOT, load_settings
from jarvis.losses import wildfire as wildfire_loss
from jarvis.simulations.common.nsi import INVENTORY_ID, NsiUnavailable, load_nsi
from jarvis.simulations.earthquake import damage_run as earthquake_damage
from jarvis.simulations.earthquake.map_run import run_at_point as run_earthquake
from jarvis.simulations.fire.damage_run import estimate_damage, estimate_exposure, load_inventory
from jarvis.simulations.fire.map_run import run_at_point
from jarvis.simulations.flood import damage_run as flood_damage
from jarvis.simulations.flood.map_run import run_flood

WEB_DIR = PROJECT_ROOT / "web"
ACCESS_COOKIE = "jarvis_access"
REFRESH_COOKIE = "jarvis_refresh"
OPEN_PATHS = {"/login", "/health"}

app = FastAPI(title="Jarvis", version=__version__)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


def set_session(response, request, access_token, refresh_token):
    # Fly ends HTTPS at its proxy, so the scheme the browser used comes in a header.
    is_https = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    for name, value in [(ACCESS_COOKIE, access_token), (REFRESH_COOKIE, refresh_token)]:
        response.set_cookie(
            name, value, max_age=30 * 24 * 3600, httponly=True, secure=is_https, samesite="lax"
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


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


INVENTORY_QUALITY = "screening-level modeled inventory"


class FireRun(BaseModel):
    lat: float = Field(gt=-90, lt=90)
    lng: float = Field(ge=-180, le=180)
    hours: float = Field(gt=0, le=12)
    wind_speed_mps: float = Field(ge=0, le=40)
    wind_from_deg: float = Field(ge=0, le=360)
    enhanced_damage: bool = False


class FloodRun(BaseModel):
    south: float
    west: float
    north: float
    east: float
    hours: float = Field(gt=0, le=24)
    rainfall_mm_hr: float = Field(ge=0)
    source_lat: float | None = None
    source_lng: float | None = None
    point_inflow_m3_s: float = Field(default=0, ge=0)
    roughness_n: float = Field(gt=0)
    infiltration_mm_hr: float = Field(default=0, ge=0)
    enhanced_damage: bool = False


class EarthquakeRun(BaseModel):
    lat: float
    lng: float
    # all four omitted: the box is sized to the shaking footprint
    south: float | None = None
    west: float | None = None
    north: float | None = None
    east: float | None = None
    magnitude: float = Field(ge=3.0, le=8.5)
    mechanism: Literal["unspecified", "strike_slip", "normal", "reverse"]
    vs30_mps: float = Field(default=760, ge=150, le=1500)
    enhanced_damage: bool = False


@app.post("/api/fire/simulate")
def simulate_fire(run: FireRun) -> dict:
    result = run_at_point(run.lat, run.lng, run.hours, run.wind_speed_mps, run.wind_from_deg)
    structures, meta = load_inventory(result["bounds"], run.enhanced_damage)
    result["model"] = {
        "id": "wind-driven-ca",
        "assumptions": ["wind held constant", "fuel, terrain and humidity omitted"],
    }
    result["inventory"] = {"id": meta["inventory"], "quality": INVENTORY_QUALITY, **meta}
    result["loss_model"] = wildfire_loss.loss_metadata(meta["mode"] == "enhanced")
    result["damage_model"] = {
        "id": "marshall_fire_loss_factors",
        "mode": "enhanced_boulder_local" if meta["mode"] == "enhanced" else "baseline_nsi_bldgtype",
        "limitations": [
            "calibrated from 2021 Marshall Fire",
            "NSI building type is coarser than local siding data",
            "may run high for calmer fires",
        ],
    }
    if structures is None:
        # the spread still works without an inventory
        result["exposure"] = None
        result["damage"] = None
        return result
    result["exposure"] = estimate_exposure(result, structures, meta["inventory"])
    result["damage"] = {**estimate_damage(result, structures), **meta}
    return result


def attach_nsi_exposure(result: dict, estimate, estimate_loss=None) -> dict:
    """Exposure (and loss, when a model is given) from the NSI cache; a missing inventory leaves both null."""
    result["inventory"] = {"id": INVENTORY_ID, "quality": INVENTORY_QUALITY}
    try:
        structures = load_nsi(result["bounds"])
    except NsiUnavailable as err:
        result["inventory"]["warning"] = str(err)
        return result
    result["exposure"] = estimate(result, structures, INVENTORY_ID)
    if estimate_loss is not None:
        try:
            result["damage"] = estimate_loss(result, structures, INVENTORY_ID)
        except Exception as err:
            # the hazard and exposure are still useful when the loss model fails
            result["inventory"]["loss_warning"] = str(err)
    return result


@app.post("/api/flood/simulate")
def simulate_flood(run: FloodRun) -> dict:
    bounds = {"south": run.south, "west": run.west, "north": run.north, "east": run.east}
    try:
        result = run_flood(
            bounds, run.hours, run.rainfall_mm_hr, run.source_lat, run.source_lng,
            run.point_inflow_m3_s, run.roughness_n, run.infiltration_mm_hr,
        )
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    return attach_nsi_exposure(result, flood_damage.estimate_exposure, flood_damage.estimate_damage)


@app.post("/api/earthquake/simulate")
def simulate_earthquake(run: EarthquakeRun) -> dict:
    box = {"south": run.south, "west": run.west, "north": run.north, "east": run.east}
    bounds = box if all(v is not None for v in box.values()) else None
    try:
        result = run_earthquake(
            run.lat, run.lng, run.magnitude, run.mechanism, bounds, vs30_default=run.vs30_mps
        )
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    return attach_nsi_exposure(result, earthquake_damage.estimate_exposure)


def run() -> None:
    settings = load_settings()
    uvicorn.run(
        "jarvis.server:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
