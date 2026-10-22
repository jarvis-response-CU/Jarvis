# References:
#   https://numpy.org/doc/stable/reference/generated/numpy.bincount.html

"""Damage estimate for a simulated fire: the buildings in its burned cells.

A property counts as reached once the cell it sits in ignites. Its expected
loss is its building value times the loss factor for its siding and roof
(see jarvis.damage). The loss factors were tuned on the 2021 Marshall Fire,
which burned in extreme wind, so they run high for a calmer fire.
"""

from functools import lru_cache

import numpy as np
import pandas as pd

from jarvis.config import load_settings
from jarvis.damage import loss_factors, read_loss_factors
from jarvis.structures import build

COLUMNS = ["lat", "lon", "bld_value", "wall", "roof"]


@lru_cache
def load_structures() -> pd.DataFrame:
    """Every property's location, value and loss factor.

    Building the table from the raw county files takes about a minute, so the
    first run saves it under data/processed/. Raises FileNotFoundError when
    the raw files haven't been downloaded (python -m jarvis.wildfire).
    """
    settings = load_settings()
    cache = settings.processed_dir / "structures.csv"
    if cache.exists():
        table = pd.read_csv(cache)
    else:
        table = build(settings.raw_dir / "wildfire")[COLUMNS]
        cache.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(cache, index=False)
    table = table.copy()
    table["loss_factor"] = loss_factors(table["wall"], table["roof"], read_loss_factors())
    return table


def estimate_damage(result: dict, structures: pd.DataFrame) -> dict:
    """Properties reached, their value and their expected loss, in total and by minute.

    `result` is what run_at_point returns. The by-minute lists run from minute
    0 to the end of the run, cumulative, so the map's time slider can index them.
    """
    bounds = result["bounds"]
    rows, cols = result["rows"], result["cols"]

    ignition_minute = np.full((rows, cols), np.nan)
    cells = np.array(result["cells"]).reshape(-1, 3)
    ignition_minute[cells[:, 0], cells[:, 1]] = cells[:, 2]

    row = np.floor((structures["lat"] - bounds["south"]) / (bounds["north"] - bounds["south"]) * rows)
    col = np.floor((structures["lon"] - bounds["west"]) / (bounds["east"] - bounds["west"]) * cols)
    is_on_grid = (row >= 0) & (row < rows) & (col >= 0) & (col < cols)
    reached = structures[is_on_grid].copy()
    reached["minute"] = ignition_minute[row[is_on_grid].astype(int), col[is_on_grid].astype(int)]
    reached = reached[reached["minute"].notna()]
    reached["expected_loss"] = reached["bld_value"] * reached["loss_factor"]

    last_minute = result["duration_min"]
    minute = np.minimum(reached["minute"].astype(int), last_minute)

    def cumulative(weights):
        return np.cumsum(np.bincount(minute, weights=weights, minlength=last_minute + 1))

    properties = cumulative(np.ones(len(reached)))
    exposed_value = cumulative(reached["bld_value"].to_numpy())
    expected_loss = cumulative(reached["expected_loss"].to_numpy())
    return {
        "properties": int(properties[-1]),
        "exposed_value": round(exposed_value[-1]),
        "expected_loss": round(expected_loss[-1]),
        "by_minute": {
            "properties": properties.astype(int).tolist(),
            "exposed_value": exposed_value.round().astype(int).tolist(),
            "expected_loss": expected_loss.round().astype(int).tolist(),
        },
    }
