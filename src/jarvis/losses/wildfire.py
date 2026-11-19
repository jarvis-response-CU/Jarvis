"""Wildfire loss in the shared interface. The numbers are the existing Marshall Fire factors, unchanged."""

import numpy as np
import pandas as pd

from jarvis.losses.common import MISSING_REPLACEMENT_VALUE, OK

MODEL_ID = "Marshall Fire empirical loss factors"


def loss_metadata(enhanced: bool) -> dict:
    return {
        "loss_model": MODEL_ID,
        "demand": "structure reached by simulated fire",
        "inventory": "NSI baseline; Boulder assessor override when enhanced" if enhanced else "NSI baseline",
    }


def fire_loss_table(structures: pd.DataFrame) -> pd.DataFrame:
    """Per-structure expected loss: building value times its loss factor."""
    value = structures["bld_value"].to_numpy(dtype=float)
    factor = structures["loss_factor"].to_numpy(dtype=float)
    status = np.where(np.isfinite(value) & np.isfinite(factor), OK, MISSING_REPLACEMENT_VALUE)
    return pd.DataFrame({
        "structure_value": value,
        "expected_total_loss": np.where(status == OK, value * factor, np.nan),
        "loss_status": status,
    }, index=structures.index)
