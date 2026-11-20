"""Shared pieces of the loss pipeline: the asset record, status values and summaries."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

OK = "ok"
MISSING_REPLACEMENT_VALUE = "missing_replacement_value"
MISSING_FIRST_FLOOR_HEIGHT = "missing_first_floor_height"
UNSUPPORTED_OCCUPANCY = "unsupported_occupancy"
MISSING_STRUCTURE_TYPE = "missing_structure_type"
MISSING_DESIGN_LEVEL = "missing_design_level"
OUTSIDE_MODEL_DOMAIN = "outside_model_domain"
MODEL_ERROR = "model_error"
STATUSES = (
    OK, MISSING_REPLACEMENT_VALUE, MISSING_FIRST_FLOOR_HEIGHT, UNSUPPORTED_OCCUPANCY,
    MISSING_STRUCTURE_TYPE, MISSING_DESIGN_LEVEL, OUTSIDE_MODEL_DOMAIN, MODEL_ERROR,
)
FEET_PER_METER = 3.280839895


@dataclass
class LossAsset:
    asset_id: str
    lat: float
    lon: float
    occupancy: str | None
    building_type: str | None
    structure_type: str | None
    design_level: str | None
    year_built: int | None
    stories: float | None
    sqft: float | None
    foundation_type: str | None
    first_floor_height_m: float | None
    structure_value: float | None
    contents_value: float | None
    wall: str | None = None
    roof: str | None = None
    source: str = "nsi"


ASSET_COLUMNS = [field for field in LossAsset.__dataclass_fields__]


def loss_summary(model: str, rows: pd.DataFrame, exposed, warnings=None) -> dict:
    """Common summary of a per-asset loss table; `exposed` flags the structures the hazard reached."""
    exposed = np.asarray(exposed, dtype=bool)
    modeled = (rows["loss_status"] == OK).to_numpy()
    value = rows["structure_value"].to_numpy(dtype=float)
    loss = rows["expected_total_loss"].to_numpy(dtype=float)
    modeled_value = float(np.nansum(value[modeled & exposed]))
    expected_loss = float(np.nansum(loss[modeled & exposed]))
    return {
        "model": model,
        "properties_exposed": int(exposed.sum()),
        "properties_modeled": int((modeled & exposed).sum()),
        "exposed_value": round(float(np.nansum(value[exposed]))),
        "expected_loss": round(expected_loss),
        # never divide by the value of assets left out of the loss model
        "loss_ratio": expected_loss / modeled_value if modeled_value > 0 else None,
        "assets_with_loss_model": int((modeled & exposed).sum()),
        "assets_without_loss_model": int((~modeled & exposed).sum()),
        "warnings": list(warnings or []),
    }
