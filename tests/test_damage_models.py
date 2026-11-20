import numpy as np
import pandas as pd

from jarvis.damage import nsi_loss_factors, read_loss_factors
from jarvis.simulations.common.nsi import INVENTORY_ID, NsiUnavailable
from jarvis.simulations.fire import damage_run
from jarvis.simulations.fire.damage_run import BOULDER_COVERAGE, load_inventory, merge_inventories

FACTORS = {("any", "any"): 0.48, ("wood", "any"): 0.6, ("masonry", "any"): 0.47}


def test_nsi_building_types_map_to_broad_groups():
    result = nsi_loss_factors(["W", "M", "H", "S", None, "w"], FACTORS)
    assert result.tolist() == [0.6, 0.47, 0.48, 0.48, 0.48, 0.6]


def test_real_loss_table_supplies_the_numbers():
    factors = read_loss_factors()
    assert nsi_loss_factors(["W"], factors)[0] == factors[("wood", "any")]


def frame(points):
    return pd.DataFrame(points, columns=["lat", "lon", "bld_value", "loss_factor"])


def test_local_records_replace_nsi_inside_coverage_without_double_counting():
    inside = ((BOULDER_COVERAGE["south"] + BOULDER_COVERAGE["north"]) / 2, -105.3)
    nsi = frame([[*inside, 1, 0.5], [35.0, -100.0, 2, 0.5]])
    local = frame([[*inside, 10, 0.1]])
    merged = merge_inventories(nsi, local)
    assert sorted(merged["bld_value"]) == [2, 10]


BOUNDS = {"south": 40.0, "west": -105.3, "north": 40.01, "east": -105.29}


def patch_inventories(monkeypatch, nsi_table=None, local_table=None):
    def nsi(bounds, factors):
        if nsi_table is None:
            raise NsiUnavailable("offline")
        return nsi_table

    def local():
        if local_table is None:
            raise FileNotFoundError
        return local_table

    monkeypatch.setattr(damage_run, "nsi_structures", nsi)
    monkeypatch.setattr(damage_run, "load_structures", local)
    monkeypatch.setattr(damage_run, "read_loss_factors", lambda: FACTORS)


def test_baseline_uses_nsi(monkeypatch):
    nsi = frame([[40.005, -105.295, 5, 0.5]])
    patch_inventories(monkeypatch, nsi, frame([[40.005, -105.295, 9, 0.1]]))
    structures, meta = load_inventory(BOUNDS, enhanced=False)
    assert structures["bld_value"].tolist() == [5]
    assert meta == {
        "mode": "baseline", "inventory": INVENTORY_ID, "enhanced_requested": False, "enhanced_available": False,
    }


def test_enhanced_uses_local_inside_coverage(monkeypatch):
    patch_inventories(monkeypatch, frame([[40.005, -105.295, 5, 0.5]]), frame([[40.005, -105.295, 9, 0.1]]))
    structures, meta = load_inventory(BOUNDS, enhanced=True)
    assert structures["bld_value"].tolist() == [9]
    assert meta["mode"] == "enhanced" and meta["inventory"] == "nsi_2026+boulder_local"


def test_enhanced_without_local_files_falls_back_to_nsi(monkeypatch):
    patch_inventories(monkeypatch, frame([[40.005, -105.295, 5, 0.5]]), None)
    structures, meta = load_inventory(BOUNDS, enhanced=True)
    assert structures["bld_value"].tolist() == [5]
    assert meta["enhanced_requested"] and not meta["enhanced_available"] and meta["mode"] == "baseline"


def test_no_inventory_returns_none_with_warning(monkeypatch):
    patch_inventories(monkeypatch, None, None)
    structures, meta = load_inventory(BOUNDS)
    assert structures is None and "offline" in meta["inventory_warning"]


def test_fire_exposure_counts_reached_structures():
    result = {
        "bounds": {"south": 40.0, "west": -105.0, "north": 40.003, "east": -104.997},
        "rows": 3, "cols": 3, "duration_min": 5, "cells": [0, 0, 0],
    }
    structures = frame([[40.0005, -104.9995, 100, 0.5], [40.0025, -104.9975, 50, 0.5]])
    exposure = damage_run.estimate_exposure(result, structures, INVENTORY_ID)
    assert exposure["properties_on_grid"] == 2 and exposure["properties_affected"] == 1
    assert np.isclose(exposure["affected_building_value"], 100)
