"""Place a structure inventory on a hazard grid without touching hazard physics."""

import numpy as np
import pandas as pd

from jarvis.simulations.common.grid import GridSpec, latlon_to_row_col


def structures_on_grid(result: dict, structures: pd.DataFrame) -> pd.DataFrame:
    """Structures inside the result's grid, with integer `row` and `col` columns."""
    grid = GridSpec.from_result(result)
    row, col = latlon_to_row_col(grid, structures["lat"].to_numpy(), structures["lon"].to_numpy())
    on_grid = (row >= 0) & (row < grid.rows) & (col >= 0) & (col < grid.cols)
    placed = structures[on_grid].copy()
    placed["row"] = row[on_grid]
    placed["col"] = col[on_grid]
    return placed


def exposure_summary(inventory: str, on_grid: pd.DataFrame, affected=None, **extra) -> dict:
    """Counts and replacement value on the grid, and for the affected subset when given."""
    value = on_grid["bld_value"].to_numpy(dtype=float)
    summary = {
        "inventory": inventory,
        "properties_on_grid": int(len(on_grid)),
        "building_value_on_grid": round(float(value.sum())),
    }
    if affected is not None:
        affected = np.asarray(affected, dtype=bool)
        summary["properties_affected"] = int(affected.sum())
        summary["affected_building_value"] = round(float(value[affected].sum()))
    return {**summary, **extra}
