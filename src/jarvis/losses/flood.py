# References:
#   FEMA Hazus Flood Model Technical Manual; NHERI SimCenter DLML "flood/building/portfolio/Hazus v6.1"

"""Hazus Flood v6.1 depth-damage losses through the packaged DLML curves and Pelicun's interpolator."""

import importlib.util
import re
from functools import lru_cache

import dlml
import numpy as np
import pandas as pd
from pelicun import base

from jarvis.losses.common import (
    FEET_PER_METER, MISSING_FIRST_FLOOR_HEIGHT, MISSING_REPLACEMENT_VALUE, MODEL_ERROR, OK, UNSUPPORTED_OCCUPANCY,
)

FLOOD_DATASET = "flood/building/portfolio/Hazus v6.1"
MODEL_ID = "Hazus Flood v6.1"
BASEMENT_FOUNDATION = 3504
SLAB_FOUNDATION = 3501
RES1_SUBTYPE = re.compile(r"^RES1-(\d|SL)S?(N|W)B$")
# nsi foundation types with a basement: basement and walkout
BASEMENT_TYPES = {"B", "W"}


@lru_cache
def ruleset():
    path = dlml.get_file(FLOOD_DATASET, "FloodRulesets.py")
    spec = importlib.util.spec_from_file_location("jarvis_hazus_flood_rulesets", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.configure_flood_vulnerability


@lru_cache
def curve_table() -> pd.DataFrame:
    table = pd.read_csv(dlml.get_file(FLOOD_DATASET, "loss_repair.csv"))
    table = table[(table["Incomplete"] == 0) & table["ID"].str.endswith("-Cost")]
    return table.set_index("ID")


@lru_cache
def contents_by_suffix() -> dict:
    suffix = {}
    for curve_id in curve_table().index:
        if curve_id.startswith("contents."):
            suffix[re.sub(r"^contents\.\d+\.", "", curve_id)] = curve_id
    return suffix


def validate_datasets() -> None:
    """Fail loudly when the pinned model data is not the expected release."""
    if FLOOD_DATASET not in dlml.list_datasets():
        raise RuntimeError(f"{FLOOD_DATASET} is not in the installed DLML")
    if "loss_repair" not in dlml.available_collections(FLOOD_DATASET):
        raise RuntimeError(f"{FLOOD_DATASET} has no loss_repair collection")


def evaluate_curve(curve: str, depth, depth_unit: str = "m", curve_unit: str = "ft"):
    """Loss ratio of a 'ratios|depths' curve at depths given in depth_unit."""
    depth = np.asarray(depth, dtype=float)
    converted = base.convert_units(depth, unit=depth_unit, to_unit=curve_unit, category="length")
    low, high = (float(v) for v in (curve.split("|")[1].split(",")[0], curve.split("|")[1].split(",")[-1]))
    # hold the end values outside the tabulated depths, as hazus does
    return np.asarray(base.stringterpolation(curve)(np.clip(converted, low, high)), dtype=float)


def hazus_features(asset) -> dict | None:
    """Inputs for the packaged flood ruleset, or None when the occupancy is not recognized."""
    occupancy = str(asset["occupancy"] or "")
    parent = occupancy.split("-")[0]
    if not parent:
        return None
    has_basement = asset["foundation_type"] in BASEMENT_TYPES
    stories = asset["stories"]
    split_level = False
    subtype = RES1_SUBTYPE.match(occupancy)
    if subtype:
        # the nsi res1 subtype is the most specific story and basement information available
        has_basement = subtype.group(2) == "W"
        if subtype.group(1) == "SL":
            split_level, stories = True, 2
        else:
            stories = int(subtype.group(1))
    if stories is None or pd.isna(stories):
        stories = 1
    return {
        "OccupancyClass": parent,
        "NumberOfStories": int(max(1, round(stories))),
        "SplitLevel": split_level,
        "FoundationType": BASEMENT_FOUNDATION if has_basement else SLAB_FOUNDATION,
        "FloodZone": str(asset.get("flood_zone") or "X"),
        "YearBuilt": int(asset["year_built"]) if pd.notna(asset["year_built"]) else 1985,
        "FirstFloorElevation": 0.0,
        "City": "NA",
    }


def assign_curves(assets: pd.DataFrame) -> pd.DataFrame:
    """Hazus structure and contents curve ids for each asset, with a loss_status for those that have none."""
    select = ruleset()
    structure, contents, status = [], [], []
    for _, asset in assets.iterrows():
        features = hazus_features(asset)
        curve = None
        if features is not None:
            try:
                curve = select(features)
            except (KeyError, UnboundLocalError):
                curve = None
        if curve is None or f"{curve}-Cost" not in curve_table().index:
            structure.append(None)
            contents.append(None)
            status.append(UNSUPPORTED_OCCUPANCY)
            continue
        structure.append(f"{curve}-Cost")
        contents.append(contents_by_suffix().get(re.sub(r"^structural\.\d+\.", "", curve) + "-Cost"))
        status.append(OK)
    return pd.DataFrame(
        {"structure_curve": structure, "contents_curve": contents, "loss_status": status}, index=assets.index
    )


def curve_ratio(curve_ids, depth_ft_relative) -> np.ndarray:
    """Loss ratio per asset from its own curve; NaN where there is no curve."""
    ratios = np.full(len(curve_ids), np.nan)
    curve_ids = pd.Series(curve_ids)
    for curve_id, positions in curve_ids.groupby(curve_ids).groups.items():
        row = curve_table().loc[curve_id]
        ratios[positions] = evaluate_curve(
            row["LossFunction-Theta_0"], depth_ft_relative[positions], depth_unit="ft", curve_unit=row["Demand-Unit"]
        )
    return ratios


def estimate_flood_loss(depth_m: np.ndarray, assets: pd.DataFrame, curves: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-structure Hazus flood loss for maximum depths above ground, in meters.

    `curves` is assign_curves(assets), passed in when the same assets are evaluated repeatedly.
    """
    depth_m = np.asarray(depth_m, dtype=float)
    curves = assign_curves(assets) if curves is None else curves
    floor_m = assets["first_floor_height_m"].to_numpy(dtype=float)
    # hazus flood depth is relative to first-floor elevation
    relative_m = depth_m - floor_m

    status = curves["loss_status"].to_numpy(dtype=object).copy()
    status[(status == OK) & ~np.isfinite(floor_m)] = MISSING_FIRST_FLOOR_HEIGHT
    usable = status == OK

    structure_ratio = np.full(len(assets), np.nan)
    contents_ratio = np.full(len(assets), np.nan)
    if usable.any():
        relative_ft = np.where(usable, relative_m * FEET_PER_METER, 0.0)
        try:
            structure_ratio[usable] = curve_ratio(curves["structure_curve"].to_numpy()[usable], relative_ft[usable])
            has_contents = usable & curves["contents_curve"].notna().to_numpy()
            if has_contents.any():
                contents_ratio[has_contents] = curve_ratio(
                    curves["contents_curve"].to_numpy()[has_contents], relative_ft[has_contents]
                )
        except Exception:
            status[usable] = MODEL_ERROR
            structure_ratio[:] = np.nan
            contents_ratio[:] = np.nan

    for ratios in (structure_ratio, contents_ratio):
        finite = ratios[np.isfinite(ratios)]
        if len(finite) and (finite.min() < 0 or finite.max() > 1):
            raise ValueError("hazus flood loss ratio outside 0-1")

    structure_value = assets["structure_value"].to_numpy(dtype=float)
    contents_value = assets["contents_value"].to_numpy(dtype=float)
    structure_loss = structure_ratio * structure_value
    contents_loss = contents_ratio * contents_value
    status[(status == OK) & ~np.isfinite(structure_value)] = MISSING_REPLACEMENT_VALUE
    total = np.where(np.isfinite(structure_loss), structure_loss + np.nan_to_num(contents_loss), np.nan)
    total[status != OK] = np.nan

    return pd.DataFrame({
        "asset_id": assets["asset_id"].to_numpy(),
        "max_depth_m": depth_m,
        "first_floor_height_m": floor_m,
        "depth_above_first_floor_m": relative_m,
        "occupancy": assets["occupancy"].to_numpy(),
        "structure_value": structure_value,
        "contents_value": contents_value,
        "structure_loss_ratio": structure_ratio,
        "contents_loss_ratio": contents_ratio,
        "expected_structure_loss": structure_loss,
        "expected_contents_loss": contents_loss,
        "expected_total_loss": total,
        "model_id": MODEL_ID,
        "loss_status": status,
    })
