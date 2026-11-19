import numpy as np
import pandas as pd
import pytest

from jarvis.losses import flood
from jarvis.losses.common import FEET_PER_METER

FT = 1 / FEET_PER_METER


def asset(occupancy="RES1-1SNB", floor_ft=1.0, structure=300_000.0, contents=150_000.0, **extra):
    row = {
        "asset_id": "a", "occupancy": occupancy, "stories": 1, "foundation_type": "S", "year_built": 1980,
        "flood_zone": "X", "first_floor_height_m": floor_ft * FT, "structure_value": structure,
        "contents_value": contents,
    }
    return {**row, **extra}


def evaluate(depth_ft, **kwargs):
    assets = pd.DataFrame([asset(**kwargs)])
    return flood.estimate_flood_loss(np.array([depth_ft * FT]), assets).iloc[0]


HEC_FDA_STRUCTURE = "0, 0.05, 0.07, 0.10, 0.25, 0.50, 0.70, 0.80|-1, 0, 1, 2, 5, 10, 15, 20"
HEC_FDA_CONTENTS = "0, 0.02, 0.05, 0.15, 0.50, 0.80, 0.90, 0.95|-1, 0, 1, 2, 5, 10, 15, 20"


def test_published_hec_fda_curve_interpolation():
    depth_ft = np.array([-1, 0, 0.5, 1, 3.5, 7.5, 20, 30, -5])
    structure = flood.evaluate_curve(HEC_FDA_STRUCTURE, depth_ft, "ft", "ft")
    assert structure == pytest.approx([0, 0.05, 0.06, 0.07, 0.175, 0.375, 0.80, 0.80, 0])
    contents = flood.evaluate_curve(HEC_FDA_CONTENTS, depth_ft, "ft", "ft")
    assert contents == pytest.approx([0, 0.02, 0.035, 0.05, 0.325, 0.65, 0.95, 0.95, 0])


def test_unit_equivalence_meters_and_feet():
    in_feet = flood.evaluate_curve(HEC_FDA_STRUCTURE, np.array([3.0]), "ft", "ft")
    in_meters = flood.evaluate_curve(HEC_FDA_STRUCTURE, np.array([3.0 * 0.3048]), "m", "ft")
    assert in_meters == pytest.approx(in_feet)


def test_depth_is_measured_from_the_first_floor():
    low = evaluate(3.0, floor_ft=0.0)
    high = evaluate(3.0, floor_ft=2.0)
    assert high["depth_above_first_floor_m"] == pytest.approx(1.0 * 0.3048)
    assert high["structure_loss_ratio"] <= low["structure_loss_ratio"]
    assert high["expected_structure_loss"] <= low["expected_structure_loss"]


@pytest.mark.parametrize("occupancy, stories, foundation", [
    ("RES1-1SNB", 1, "S"), ("RES1-2SWB", 2, "B"), ("COM1", 1, "S"), ("IND2", 1, "S"), ("RES3B", 3, "S"),
])
def test_loss_ratio_is_non_decreasing_with_depth(occupancy, stories, foundation):
    depths = [-3, -1, 0, 1, 2, 4, 8, 12]
    ratios = [evaluate(d, occupancy=occupancy, stories=stories, foundation_type=foundation)["structure_loss_ratio"]
              for d in depths]
    assert all(b >= a - 1e-12 for a, b in zip(ratios, ratios[1:]))
    assert all(0 <= r <= 1 for r in ratios)


def test_doubling_replacement_value_doubles_loss():
    one = evaluate(2.0)
    two = evaluate(2.0, structure=600_000.0, contents=300_000.0)
    assert one["structure_loss_ratio"] == two["structure_loss_ratio"]
    assert two["expected_total_loss"] == pytest.approx(2 * one["expected_total_loss"])


def test_total_is_structure_plus_contents_and_ratios_match_the_curves():
    row = evaluate(2.0)
    assert row["expected_total_loss"] == pytest.approx(row["expected_structure_loss"] + row["expected_contents_loss"])
    curves = flood.assign_curves(pd.DataFrame([asset()]))
    table = flood.curve_table()
    expected = flood.evaluate_curve(
        table.loc[curves["structure_curve"].iloc[0], "LossFunction-Theta_0"], np.array([1.0]), "ft", "ft"
    )
    assert row["structure_loss_ratio"] == pytest.approx(expected[0])


@pytest.mark.parametrize("occupancy, foundation, structure_curve", [
    ("RES1-1SNB", "S", "structural.658.RES1.BCAR_Jan_2011.all_floors.slab_no_basement.coastal_a_or_v_zone-Cost"),
    ("RES1-2SWB", "B", "structural.108.RES1.FIA_Modified.two_floors.with_basement.a_zone-Cost"),
    ("COM1", "S", "structural.217.COM1.USACE_Galveston.average_retail-Cost"),
])
def test_golden_curve_selection_and_values(occupancy, foundation, structure_curve):
    stories = 2 if occupancy == "RES1-2SWB" else 1
    row = evaluate(2.0, occupancy=occupancy, stories=stories, foundation_type=foundation, floor_ft=0.0)
    curves = flood.assign_curves(pd.DataFrame([asset(occupancy=occupancy, stories=stories, foundation_type=foundation)]))
    assert curves["structure_curve"].iloc[0] == structure_curve
    ratios, depths = flood.curve_table().loc[structure_curve, "LossFunction-Theta_0"].split("|")
    golden = np.interp(2.0, [float(x) for x in depths.split(",")], [float(x) for x in ratios.split(",")])
    assert row["structure_loss_ratio"] == pytest.approx(golden)


def test_basement_and_no_basement_use_different_curves():
    no_basement = evaluate(0.0, occupancy="RES1-2SNB", stories=2, foundation_type="S", floor_ft=0.0)
    basement = evaluate(0.0, occupancy="RES1-2SWB", stories=2, foundation_type="B", floor_ft=0.0)
    assert basement["structure_loss_ratio"] > no_basement["structure_loss_ratio"]


def test_missing_first_floor_height_is_reported_not_zeroed():
    row = flood.estimate_flood_loss(
        np.array([1.0]), pd.DataFrame([asset(first_floor_height_m=np.nan)])
    ).iloc[0]
    assert row["loss_status"] == "missing_first_floor_height" and np.isnan(row["expected_total_loss"])


def test_unsupported_occupancy_is_null_not_zero():
    row = evaluate(1.0, occupancy="RES2", flood_zone="AO")
    assert row["loss_status"] == "unsupported_occupancy" and np.isnan(row["expected_total_loss"])
    assert evaluate(1.0, occupancy="NOPE")["loss_status"] == "unsupported_occupancy"


def test_missing_contents_value_keeps_structure_loss():
    row = evaluate(2.0, contents=np.nan)
    assert row["expected_structure_loss"] > 0 and np.isnan(row["expected_contents_loss"])
    assert row["expected_total_loss"] == pytest.approx(row["expected_structure_loss"])


def test_missing_structure_value_still_returns_ratios():
    row = evaluate(2.0, structure=np.nan)
    assert row["loss_status"] == "missing_replacement_value" and row["structure_loss_ratio"] > 0
    assert np.isnan(row["expected_structure_loss"])


def test_curve_without_contents_leaves_contents_null():
    row = evaluate(2.0, occupancy="COM1")
    assert np.isnan(row["contents_loss_ratio"]) and row["expected_structure_loss"] > 0


def test_flood_damage_run_summary_and_frames():
    from jarvis.simulations.flood.damage_run import estimate_damage

    result = {
        "bounds": {"south": 40.0, "west": -105.0, "north": 40.003, "east": -104.997},
        "rows": 3, "cols": 3, "value_scale": 0.001,
        "frames": [[], [0, 0, 500], [0, 0, 1500, 1, 1, 8]],
        "max_cells": [0, 0, 1500, 1, 1, 8],
    }
    structures = pd.DataFrame({
        "asset_id": ["1", "2", "3"], "lat": [40.0005, 40.0015, 40.0025], "lon": [-104.9995, -104.9985, -104.9975],
        "occupancy": ["RES1-1SNB", "COM1", "COM1"], "building_type": ["W", "M", "M"], "sqft": 1000.0,
        "foundation_type": "S", "foundation_height_ft": 0.5, "stories": 1, "depreciated_structure_value": 1.0,
        "contents_value": 50_000.0, "median_year_built": 1980, "ground_elevation_ft": 1.0,
        "building_height_m": 4.0, "replacement_value": 100_000.0, "bld_value": 100_000.0, "flood_zone": "X",
    })
    damage = estimate_damage(result, structures, "nsi_2026")
    assert damage["loss_model"] == "Hazus Flood v6.1" and damage["loss_engine"] == "pelicun 3.10.0"
    assert damage["model_data"] == "simcenter-dlml 3.2"
    assert damage["properties_exposed"] == 1 and damage["assets_with_loss_model"] == 1
    assert damage["expected_loss"] > 0
    by_frame = damage["by_frame"]["expected_loss"]
    assert by_frame[0] == 0 and by_frame == sorted(by_frame) and by_frame[-1] == damage["expected_loss"]
    assert damage["expected_loss"] == damage["expected_structure_loss"] + damage["expected_contents_loss"]
