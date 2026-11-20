import numpy as np
import pandas as pd
import pytest

from jarvis.losses import wildfire
from jarvis.losses.common import loss_summary
from jarvis.simulations.fire.damage_run import estimate_damage

RESULT = {
    "bounds": {"south": 40.0, "west": -105.0, "north": 40.003, "east": -104.997},
    "rows": 3, "cols": 3, "duration_min": 20, "cells": [0, 0, 0, 1, 1, 10],
}


def test_wrapper_matches_the_existing_wildfire_numbers():
    structures = pd.DataFrame({
        "lat": [40.0005, 40.0015], "lon": [-104.9995, -104.9985], "bld_value": [100.0, 200.0], "loss_factor": [0.5, 0.25],
    })
    damage = estimate_damage(RESULT, structures)
    table = wildfire.fire_loss_table(structures)
    summary = loss_summary(wildfire.MODEL_ID, table, [True, True])
    assert summary["expected_loss"] == damage["expected_loss"] == 100
    assert summary["exposed_value"] == damage["exposed_value"] == 300


def test_missing_value_is_null_not_zero():
    table = wildfire.fire_loss_table(pd.DataFrame({"bld_value": [np.nan, 10.0], "loss_factor": [0.5, 0.5]}))
    assert np.isnan(table["expected_total_loss"].iloc[0]) and table["loss_status"].iloc[0] != "ok"
    assert table["expected_total_loss"].iloc[1] == pytest.approx(5)


def test_metadata_names_the_baseline_and_enhanced_inventory():
    assert "Boulder" in wildfire.loss_metadata(True)["inventory"]
    assert wildfire.loss_metadata(False)["loss_model"] == "Marshall Fire empirical loss factors"
