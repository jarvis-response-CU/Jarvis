# References:
#   https://numpy.org/doc/stable/reference/generated/numpy.bincount.html

"""Damage estimate for a simulated fire: the buildings in its burned cells.

A property counts as reached once the cell it sits in ignites. Its expected
loss is its building value times the loss factor for its siding and roof
(see jarvis.damage). The loss factors were tuned on the 2021 Marshall Fire,
which burned in extreme wind, so they run high for a calmer fire.
"""

import os
from functools import lru_cache

import numpy as np
import pandas as pd

from jarvis.config import load_settings
from jarvis.damage import loss_factors, nsi_loss_factors, read_loss_factors
from jarvis.inbox import engine
from jarvis.simulations.common.exposure import exposure_summary, structures_on_grid
from jarvis.simulations.common.nsi import INVENTORY_ID, NsiUnavailable, load_nsi
from jarvis.structures import build

COLUMNS = ["lat", "lon", "bld_value", "wall", "roof"]
# configured extent of the local boulder county files
BOULDER_COVERAGE = {"south": 39.913, "west": -105.693, "north": 40.263, "east": -105.052}
LOCAL_INVENTORY_ID = "nsi_2026+boulder_local"


@lru_cache
def load_structures() -> pd.DataFrame:
    """Every property's location, value and loss factor.

    Reads boulder.structures from the database when JARVIS_DATABASE_URL is
    set. Without it, building the table from the raw county files takes about
    a minute, so the first run saves it under data/processed/. Raises
    FileNotFoundError when the raw files haven't been downloaded
    (python -m jarvis.wildfire).
    """
    settings = load_settings()
    cache = settings.processed_dir / "structures.csv"
    if os.getenv("JARVIS_DATABASE_URL"):
        table = pd.read_sql(f"select {', '.join(COLUMNS)} from boulder.structures", engine())
    elif cache.exists():
        table = pd.read_csv(cache)
    else:
        table = build(settings.raw_dir / "wildfire")[COLUMNS]
        cache.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(cache, index=False)
    table = table.copy()
    table["loss_factor"] = loss_factors(table["wall"], table["roof"], read_loss_factors())
    return table


def reached_structures(result: dict, structures: pd.DataFrame, ignition_minute) -> pd.DataFrame:
    on_grid = structures_on_grid(result, structures)
    on_grid["minute"] = ignition_minute[on_grid["row"].to_numpy(), on_grid["col"].to_numpy()]
    return on_grid[on_grid["minute"].notna()].copy()


def estimate_damage(result: dict, structures: pd.DataFrame) -> dict:
    """Properties reached, their value and their expected loss, in total and by minute.

    `result` is what run_at_point returns. The by-minute lists run from minute
    0 to the end of the run, cumulative, so the map's time slider can index them.
    """
    rows, cols = result["rows"], result["cols"]

    ignition_minute = np.full((rows, cols), np.nan)
    cells = np.array(result["cells"]).reshape(-1, 3)
    ignition_minute[cells[:, 0], cells[:, 1]] = cells[:, 2]

    reached = reached_structures(result, structures, ignition_minute)
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


def estimate_exposure(result: dict, structures: pd.DataFrame, inventory: str) -> dict:
    ignition_minute = np.full((result["rows"], result["cols"]), np.nan)
    cells = np.array(result["cells"]).reshape(-1, 3)
    ignition_minute[cells[:, 0], cells[:, 1]] = cells[:, 2]
    on_grid = structures_on_grid(result, structures)
    reached = ~np.isnan(ignition_minute[on_grid["row"].to_numpy(), on_grid["col"].to_numpy()])
    return exposure_summary(inventory, on_grid, reached)


def nsi_structures(bounds: dict, factors: dict) -> pd.DataFrame:
    table = load_nsi(bounds)
    table["loss_factor"] = nsi_loss_factors(table["building_type"], factors)
    return table[["lat", "lon", "bld_value", "loss_factor"]]


def merge_inventories(nsi: pd.DataFrame, local: pd.DataFrame) -> pd.DataFrame:
    """Local records replace NSI points inside the local coverage, so nothing is counted twice."""
    c = BOULDER_COVERAGE
    in_coverage = (
        (nsi["lat"] >= c["south"]) & (nsi["lat"] <= c["north"])
        & (nsi["lon"] >= c["west"]) & (nsi["lon"] <= c["east"])
    )
    columns = ["lat", "lon", "bld_value", "loss_factor"]
    return pd.concat([nsi[~in_coverage][columns], local[columns]], ignore_index=True)


def load_inventory(bounds: dict, enhanced: bool = False) -> tuple[pd.DataFrame | None, dict]:
    """The structures to price for a fire in `bounds`, and metadata on how they were chosen.

    NSI is the baseline everywhere. With `enhanced`, the Boulder County files replace
    NSI inside their coverage when installed. Never raises for missing inventory.
    """
    meta = {
        "mode": "baseline",
        "inventory": INVENTORY_ID,
        "enhanced_requested": enhanced,
        "enhanced_available": False,
    }
    local = None
    if enhanced:
        try:
            local = load_structures()
            meta["enhanced_available"] = True
        except FileNotFoundError:
            pass

    nsi = None
    try:
        nsi = nsi_structures(bounds, read_loss_factors())
    except NsiUnavailable as err:
        meta["inventory_warning"] = str(err)

    if local is not None:
        meta["mode"] = "enhanced"
        in_view = structures_on_grid({"bounds": bounds, "rows": 1, "cols": 1}, local)
        if len(in_view):
            meta["inventory"] = LOCAL_INVENTORY_ID
        if nsi is None:
            return local, meta
        return merge_inventories(nsi, local), meta
    return nsi, meta
