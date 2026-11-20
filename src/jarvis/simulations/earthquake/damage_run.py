"""Exposure for a simulated earthquake. Expected loss stays unavailable until a Hazus-style model exists."""

import numpy as np
import pandas as pd

from jarvis.simulations.common.exposure import exposure_summary, structures_on_grid


def pga_grid(result: dict) -> np.ndarray:
    pga = np.zeros((result["rows"], result["cols"]))
    cells = np.array(result["cells"]).reshape(-1, 3)
    pga[cells[:, 0], cells[:, 1]] = cells[:, 2] * result["value_scale"]
    return pga


def estimate_exposure(result: dict, structures: pd.DataFrame, inventory: str) -> dict:
    on_grid = structures_on_grid(result, structures)
    pga = pga_grid(result)[on_grid["row"].to_numpy(), on_grid["col"].to_numpy()]
    # reached means the structure sits in a shaken cell of the footprint
    exposure = exposure_summary(inventory, on_grid, pga > 0)
    if len(on_grid):
        exposure["max_pga_at_structures_g"] = float(pga.max())
    return exposure
