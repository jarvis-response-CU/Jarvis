import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from jarvis.server import app
from jarvis.simulations.common.nsi import NsiUnavailable
from jarvis.simulations.flood import damage_run
from jarvis.simulations.flood.map_run import run_flood
from jarvis.simulations.flood.terrain import DemUnavailable, load_dem

BOUNDS = {"south": 40.00, "west": -105.30, "north": 40.01, "east": -105.29}
client = TestClient(app)


@pytest.fixture
def dem(tmp_path, monkeypatch):
    import rasterio
    from rasterio.transform import from_bounds

    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path))
    folder = tmp_path / "raw" / "flood"
    folder.mkdir(parents=True)
    rows = cols = 40
    # slopes down toward the south, so row 0 of the result is lowest
    elevation = np.repeat(np.linspace(1700, 1690, rows)[:, None], cols, axis=1).astype("float32")
    with rasterio.open(
        folder / "dem.tif", "w", driver="GTiff", height=rows, width=cols, count=1, dtype="float32",
        crs="EPSG:4326", transform=from_bounds(-105.31, 39.99, -105.28, 40.02, cols, rows),
    ) as dst:
        dst.write(elevation[None])
    return folder / "dem.tif"


def test_dem_is_flipped_to_south_up(dem):
    terrain = load_dem(BOUNDS)
    assert terrain.elevation[0].mean() < terrain.elevation[-1].mean()
    assert terrain.grid.rows * terrain.grid.cols <= 250_000
    assert terrain.grid.cell_m > 0


def test_cell_budget_resamples(dem):
    small = load_dem(BOUNDS, max_cells=100)
    assert small.grid.rows * small.grid.cols <= 150
    assert small.grid.cell_m > load_dem(BOUNDS).grid.cell_m


def test_outside_coverage_is_a_clear_error(dem):
    with pytest.raises(DemUnavailable, match="outside local DEM coverage"):
        load_dem({"south": 41.0, "west": -105.3, "north": 41.01, "east": -105.29})


def test_missing_dem_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path))
    with pytest.raises(DemUnavailable, match="no local DEM"):
        load_dem(BOUNDS)


def test_rain_run_returns_frames_max_raster_and_balanced_mass(dem):
    result = run_flood(BOUNDS, hours=1, rainfall_mm_hr=40)
    assert result["hazard"] == "flood" and result["model"]["id"] == "WCA2D-derived"
    assert (result["value_name"], result["value_unit"], result["value_scale"]) == ("water_depth", "m", 0.001)
    assert result["frame_minutes"][0] == 0 and result["frame_minutes"][-1] == 60
    assert len(result["frames"]) == len(result["frame_minutes"])
    assert result["frames"][0] == []
    assert len(result["max_cells"]) > 0
    assert result["mass_balance"]["relative_error"] < 1e-9
    assert result["exposure"] is None and result["damage"] is None
    cells = np.array(result["max_cells"]).reshape(-1, 3)
    assert cells[:, 2].min() >= 1 and cells[:, 2].max() * 0.001 == pytest.approx(result["max_depth_m"], abs=1e-3)
    south = cells[cells[:, 0] < result["rows"] / 2, 2].sum()
    north = cells[cells[:, 0] >= result["rows"] / 2, 2].sum()
    assert south > north


def test_point_inflow_floods_near_the_source(dem):
    result = run_flood(BOUNDS, hours=1, source_lat=40.005, source_lng=-105.295, point_inflow_m3_s=5)
    assert result["source"]["mode"] == "point_inflow"
    balance = result["mass_balance"]
    assert balance["point_inflow_m3"] == pytest.approx(5 * 3600, rel=1e-6)
    assert balance["relative_error"] < 1e-9


def test_frame_count_is_capped_for_long_runs(dem):
    result = run_flood(BOUNDS, hours=24, rainfall_mm_hr=5)
    assert len(result["frames"]) <= 125


@pytest.mark.parametrize(
    "kwargs",
    [
        {"hours": 1},
        {"hours": 0, "rainfall_mm_hr": 5},
        {"hours": 1, "point_inflow_m3_s": 3},
        {"hours": 1, "rainfall_mm_hr": 5, "roughness_n": 0},
        {"hours": 1, "point_inflow_m3_s": 3, "source_lat": 45.0, "source_lng": -105.295},
    ],
)
def test_invalid_scenarios_raise(dem, kwargs):
    with pytest.raises(ValueError):
        run_flood(BOUNDS, **kwargs)


def structures():
    return pd.DataFrame({
        "asset_id": ["1", "2", "3"], "lat": [40.0005, 40.009, 45.0], "lon": [-105.2995, -105.2905, -105.0],
        "occupancy": "RES1-1SNB", "building_type": "W", "sqft": 1000.0, "foundation_type": "S",
        "foundation_height_ft": 0.5, "stories": 1, "depreciated_structure_value": 1.0, "contents_value": 50.0,
        "median_year_built": 1980, "ground_elevation_ft": 1.0, "building_height_m": 4.0,
        "replacement_value": 100.0, "bld_value": [100.0, 300.0, 9.0], "flood_zone": "X",
    })


def test_exposure_counts_flooded_structures_by_frame(dem):
    result = run_flood(BOUNDS, hours=1, rainfall_mm_hr=40)
    exposure = damage_run.estimate_exposure(result, structures(), "nsi_2026")
    assert exposure["properties_on_grid"] == 2 and exposure["building_value_on_grid"] == 400
    assert exposure["display_depth_m"] == 0.01
    by_frame = exposure["by_frame"]
    assert len(by_frame["properties"]) == len(result["frames"])
    assert by_frame["properties"][0] == 0
    assert exposure["properties_affected"] >= exposure["properties_flooded_final"]
    assert exposure["properties_flooded_final"] == by_frame["properties"][-1]


REQUEST = {**{k: v for k, v in BOUNDS.items()}, "hours": 1, "rainfall_mm_hr": 25, "roughness_n": 0.05}


def test_endpoint_returns_exposure_and_hazus_damage(dem, monkeypatch):
    monkeypatch.setattr("jarvis.auth.is_signed_in", lambda token: True)
    monkeypatch.setattr("jarvis.server.load_nsi", lambda bounds: structures())
    response = client.post("/api/flood/simulate", json=REQUEST)
    body = response.json()
    assert response.status_code == 200
    assert body["exposure"]["properties_on_grid"] == 2
    assert body["damage"]["loss_model"] == "Hazus Flood v6.1" and "loss_warning" not in body["inventory"]


def test_endpoint_survives_inventory_failure(dem, monkeypatch):
    monkeypatch.setattr("jarvis.auth.is_signed_in", lambda token: True)

    def fail(bounds):
        raise NsiUnavailable("down")

    monkeypatch.setattr("jarvis.server.load_nsi", fail)
    body = client.post("/api/flood/simulate", json=REQUEST).json()
    assert len(body["max_cells"]) > 0 and body["exposure"] is None
    assert body["inventory"]["warning"] == "down"


def test_endpoint_reports_missing_dem_coverage(dem, monkeypatch):
    monkeypatch.setattr("jarvis.auth.is_signed_in", lambda token: True)
    far = {**REQUEST, "south": 10.0, "north": 10.01}
    response = client.post("/api/flood/simulate", json=far)
    assert response.status_code == 422 and "DEM" in response.json()["detail"]


def test_endpoint_validates(monkeypatch):
    monkeypatch.setattr("jarvis.auth.is_signed_in", lambda token: True)
    assert client.post("/api/flood/simulate", json={**REQUEST, "hours": 48}).status_code == 422
    assert client.post("/api/flood/simulate", json={**REQUEST, "roughness_n": 0}).status_code == 422
