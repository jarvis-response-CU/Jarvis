# References:
#   https://github.com/theskumar/python-dotenv
#   https://docs.python.org/3/library/dataclasses.html

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    log_level: str
    host: str
    port: int

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"


def load_settings() -> Settings:
    data_dir = Path(os.getenv("JARVIS_DATA_DIR", "data"))
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir

    log_level = os.getenv("JARVIS_LOG_LEVEL", "INFO").upper()
    if log_level not in VALID_LOG_LEVELS:
        raise ValueError(
            f"JARVIS_LOG_LEVEL must be one of {sorted(VALID_LOG_LEVELS)}, got {log_level!r}"
        )

    port_raw = os.getenv("JARVIS_PORT", "8000")
    try:
        port = int(port_raw)
    except ValueError:
        raise ValueError(f"JARVIS_PORT must be an integer, got {port_raw!r}") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"JARVIS_PORT must be between 1 and 65535, got {port}")

    return Settings(
        data_dir=data_dir,
        log_level=log_level,
        host=os.getenv("JARVIS_HOST", "127.0.0.1"),
        port=port,
    )
