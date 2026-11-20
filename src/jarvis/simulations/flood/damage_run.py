"""Exposure for a simulated flood. Expected loss stays unavailable until official depth-damage curves are added."""

from importlib.metadata import version

import numpy as np
import pandas as pd

from jarvis.losses.common import loss_summary
from jarvis.losses.flood import MODEL_ID, assign_curves, estimate_flood_loss
from jarvis.losses.nsi import nsi_to_assets
from jarvis.simulations.common.exposure import exposure_summary, structures_on_grid

FLOOD_DISPLAY_DEPTH_M = 0.01


def depth_grid(cells, result: dict) -> np.ndarray:
    depth = np.zeros((result["rows"], result["cols"]))
    packed = np.array(cells, dtype=float).reshape(-1, 3)
    if len(packed):
        depth[packed[:, 0].astype(int), packed[:, 1].astype(int)] = packed[:, 2] * result["value_scale"]
    return depth


def estimate_exposure(result: dict, structures: pd.DataFrame, inventory: str) -> dict:
    """Structure counts on the grid and flooded per frame; flooded means depth >= FLOOD_DISPLAY_DEPTH_M."""
    on_grid = structures_on_grid(result, structures)
    rows, cols = on_grid["row"].to_numpy(), on_grid["col"].to_numpy()
    value = on_grid["bld_value"].to_numpy(dtype=float)

    by_frame = {"properties": [], "exposed_value": []}
    for cells in result["frames"]:
        flooded = depth_grid(cells, result)[rows, cols] >= FLOOD_DISPLAY_DEPTH_M
        by_frame["properties"].append(int(flooded.sum()))
        by_frame["exposed_value"].append(round(float(value[flooded].sum())))

    max_depth = depth_grid(result["max_cells"], result)[rows, cols]
    at_peak = max_depth >= FLOOD_DISPLAY_DEPTH_M
    final = (
        depth_grid(result["frames"][-1], result)[rows, cols] >= FLOOD_DISPLAY_DEPTH_M
        if result["frames"] else np.zeros(len(on_grid), dtype=bool)
    )
    return exposure_summary(
        inventory, on_grid, at_peak,
        display_depth_m=FLOOD_DISPLAY_DEPTH_M,
        properties_flooded_final=int(final.sum()),
        by_frame=by_frame,
    )


def estimate_damage(result: dict, structures: pd.DataFrame, inventory: str) -> dict:
    """Hazus Flood v6.1 expected loss from each structure's maximum depth, in total and by frame.

    The by-frame series use the deepest water seen so far, so the final value equals the total.
    """
    on_grid = structures_on_grid(result, structures)
    assets = nsi_to_assets(on_grid).reset_index(drop=True)
    curves = assign_curves(assets)
    rows, cols = on_grid["row"].to_numpy(), on_grid["col"].to_numpy()

    def loss_at(depth):
        # a structure the water never reached has no flood loss
        exposed = depth >= FLOOD_DISPLAY_DEPTH_M
        table = estimate_flood_loss(depth[exposed], assets[exposed], curves[exposed])
        return exposed, table

    running = np.zeros((result["rows"], result["cols"]))
    by_frame = []
    for cells in result["frames"]:
        running = np.maximum(running, depth_grid(cells, result))
        _, table = loss_at(running[rows, cols])
        by_frame.append(round(float(np.nansum(table["expected_total_loss"]))))

    peak = depth_grid(result["max_cells"], result)[rows, cols]
    exposed, table = loss_at(peak)
    summary = loss_summary(MODEL_ID, table.assign(), np.ones(len(table), dtype=bool))
    structure_loss = float(np.nansum(table["expected_structure_loss"]))
    contents_loss = float(np.nansum(table["expected_contents_loss"]))
    warnings = []
    if summary["assets_without_loss_model"]:
        warnings.append("some structures have no Hazus flood curve or first-floor height and are not in the loss")
    return {
        **summary,
        "loss_model": MODEL_ID,
        "loss_engine": f"pelicun {version('pelicun')}",
        "model_data": f"simcenter-dlml {version('simcenter-dlml')}",
        "demand": "maximum inundation depth relative to first floor",
        "inventory": inventory,
        "expected_structure_loss": round(structure_loss),
        "expected_contents_loss": round(contents_loss),
        "warnings": warnings,
        "by_frame": {"expected_loss": by_frame},
    }
