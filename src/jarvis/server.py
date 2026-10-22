# References:
#   https://fastapi.tiangolo.com/tutorial/body/
#   https://fastapi.tiangolo.com/tutorial/static-files/
#   https://docs.pydantic.dev/latest/concepts/fields/

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from jarvis import __version__
from jarvis.config import PROJECT_ROOT, load_settings
from jarvis.simulations.fire.damage_run import estimate_damage, load_structures
from jarvis.simulations.fire.map_run import run_at_point

WEB_DIR = PROJECT_ROOT / "web"

app = FastAPI(title="Jarvis", version=__version__)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


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
