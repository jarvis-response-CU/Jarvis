import dlml
import pelicun
import pandas as pd
import pytest

from jarvis.losses import common
from jarvis.losses.flood import FLOOD_DATASET, validate_datasets
from jarvis.losses.nsi import nsi_to_assets

EARTHQUAKE_DATASET = "seismic/building/portfolio/Hazus v6.1"


def test_pinned_versions_and_datasets():
    from importlib.metadata import version

    assert pelicun.__version__ == "3.10.0" and version("simcenter-dlml") == "3.2"
    datasets = dlml.list_datasets()
    assert FLOOD_DATASET in datasets and EARTHQUAKE_DATASET in datasets
    assert {"fragility", "consequence_repair"} <= set(dlml.available_collections(EARTHQUAKE_DATASET))
    assert "loss_repair" in dlml.available_collections(FLOOD_DATASET)
    validate_datasets()


def nsi_row(**overrides):
    row = {
        "asset_id": "7", "lat": 40.0, "lon": -105.0, "occupancy": "RES1-1SNB", "building_type": "W", "sqft": 1500,
        "foundation_type": "S", "foundation_height_ft": 2.0, "stories": 1, "depreciated_structure_value": 90.0,
        "contents_value": 50.0, "median_year_built": 1980, "ground_elevation_ft": 5000, "building_height_m": 4.0,
        "replacement_value": 100.0, "bld_value": 100.0, "flood_zone": "X",
    }
    return {**row, **overrides}


def test_nsi_becomes_loss_assets_with_feet_converted_and_no_invented_classification():
    assets = nsi_to_assets(pd.DataFrame([nsi_row()]))
    assert list(assets.columns[: len(common.ASSET_COLUMNS)]) == common.ASSET_COLUMNS
    row = assets.iloc[0]
    assert row["first_floor_height_m"] == pytest.approx(2.0 * 0.3048, rel=1e-6)
    assert row["structure_value"] == 100 and row["contents_value"] == 50 and row["source"] == "nsi"
    assert row["structure_type"] is None and row["design_level"] is None


def test_summary_never_divides_by_unmodeled_value():
    rows = pd.DataFrame({
        "structure_value": [100.0, 900.0, 50.0],
        "expected_total_loss": [10.0, float("nan"), 5.0],
        "loss_status": ["ok", "unsupported_occupancy", "ok"],
    })
    summary = common.loss_summary("m", rows, [True, True, False])
    assert summary["properties_exposed"] == 2 and summary["properties_modeled"] == 1
    assert summary["assets_without_loss_model"] == 1 and summary["exposed_value"] == 1000
    assert summary["expected_loss"] == 10 and summary["loss_ratio"] == pytest.approx(0.1)


def test_empty_summary_has_no_ratio():
    rows = pd.DataFrame({"structure_value": [], "expected_total_loss": [], "loss_status": []})
    assert common.loss_summary("m", rows, [])["loss_ratio"] is None
