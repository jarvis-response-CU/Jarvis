from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from jarvis import __version__
from jarvis.config import PROJECT_ROOT, load_settings

WEB_DIR = PROJECT_ROOT / "web"

app = FastAPI(title="Jarvis", version=__version__)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


def run() -> None:
    settings = load_settings()
    uvicorn.run(
        "jarvis.server:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
