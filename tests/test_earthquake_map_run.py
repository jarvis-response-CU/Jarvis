import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from jarvis.server import app
from jarvis.simulations.common.nsi import NsiUnavailable
from jarvis.simulations.earthquake import damage_run, site_conditions
from jarvis.simulations.earthquake.map_run import joyner_boore_km, run_at_point

BOUNDS = {"south": 33.9, "west": -118.4, "north": 34.2, "east": -118.1}
EPICENTER = (34.05, -118.25)
client = TestClient(app)


def cells_of(result, key="cells"):
    return np.array(result[key]).reshape(-1, 3)


def test_result_schema_and_labels():
    result = run_at_point(*EPICENTER, 6.5, "strike_slip", BOUNDS)
    assert result["hazard"] == "earthquake"
    assert result["model"]["id"] == "BSSA14-PGA"
    assert result["model"]["distance_model"] == "epicentral_proxy"
    assert result["model"]["site_model"] == "vs30_constant"
    assert (result["value_name"], result["value_unit"], result["value_scale"]) == ("PGA", "g", 0.001)
    assert result["exposure"] is None and result["damage"] is None
    assert result["source"]["magnitude"] == 6.5
    assert len(result["cells"]) == len(result["sigma_ln"])


def test_pga_is_highest_near_the_epicenter_and_summary_matches():
    result = run_at_point(*EPICENTER, 6.5, "strike_slip", BOUNDS)
    cells = cells_of(result)
    assert cells[:, 2].max() * 0.001 == pytest.approx(result["summary"]["max_pga_g"], abs=1e-3)
    top = cells[np.argmax(cells[:, 2])]
    lat = result["bounds"]["south"] + (top[0] + 0.5) * (result["bounds"]["north"] - result["bounds"]["south"]) / result["rows"]
    assert lat == pytest.approx(EPICENTER[0], abs=0.01)
    summary = result["summary"]
    assert summary["max_pga16_g"] < summary["max_pga_g"] < summary["max_pga84_g"]


def test_row_zero_is_south():
    north_epicenter = run_at_point(34.19, -118.25, 6.5, "strike_slip", BOUNDS)
    cells = cells_of(north_epicenter)
    top = cells[np.argmax(cells[:, 2])]
    assert top[0] > north_epicenter["rows"] * 0.8


def test_cell_count_is_bounded():
    result = run_at_point(*EPICENTER, 6.5, "unspecified", {"south": 33.0, "west": -119.5, "north": 35.0, "east": -117.0})
    assert result["rows"] * result["cols"] <= 45_000


def test_rupture_geometry_distance_is_labeled_and_zero_on_the_fault():
    lat = np.array([[34.05, 34.15]])
    lon = np.array([[-118.25, -118.25]])
    line = [(34.0, -118.25), (34.1, -118.25)]
    distance, label = joyner_boore_km(lat, lon, 34.05, -118.25, line)
    assert label == "rupture_geometry"
    assert distance[0, 0] == pytest.approx(0, abs=1e-3) and distance[0, 1] == pytest.approx(5.5, rel=0.02)
    polygon = [(34.0, -118.3), (34.1, -118.3), (34.1, -118.2), (34.0, -118.2)]
    inside, _ = joyner_boore_km(lat, lon, 34.05, -118.25, polygon, "polygon")
    assert inside[0, 0] == 0 and inside[0, 1] > 0


def test_invalid_inputs_raise():
    with pytest.raises(ValueError):
        run_at_point(*EPICENTER, 9.0, "strike_slip", BOUNDS)
    with pytest.raises(ValueError):
        run_at_point(*EPICENTER, 6.5, "strike_slip", {"south": 34, "west": -118, "north": 33, "east": -117})
    with pytest.raises(ValueError):
        run_at_point(*EPICENTER, 6.5, "strike_slip", {"south": 20, "west": -130, "north": 40, "east": -100})


def test_vs30_raster_is_used_when_present(tmp_path, monkeypatch):
    import rasterio
    from rasterio.transform import from_bounds

    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path))
    folder = tmp_path / "raw" / "earthquake" / "la"
    folder.mkdir(parents=True)
    with rasterio.open(
        folder / "vs30.tif", "w", driver="GTiff", height=10, width=10, count=1, dtype="float32",
        crs="EPSG:4326", transform=from_bounds(-118.5, 33.8, -118.0, 34.3, 10, 10),
    ) as dst:
        dst.write(np.full((1, 10, 10), 300, dtype="float32"))
    soft = run_at_point(*EPICENTER, 6.5, "strike_slip", BOUNDS)
    assert soft["model"]["site_model"] == "vs30_raster"
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path / "empty"))
    rock = run_at_point(*EPICENTER, 6.5, "strike_slip", BOUNDS)
    assert soft["summary"]["max_pga_g"] > rock["summary"]["max_pga_g"]


def test_default_vs30_is_reference_rock(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path))
    from jarvis.simulations.common.grid import GridSpec

    vs30, source = site_conditions.load_vs30(BOUNDS, GridSpec(33.9, -118.4, 34.2, -118.1, 2, 2, 1000))
    assert source == "vs30_constant" and (vs30 == 760.0).all()


def test_exposure_counts_structures_without_damage():
    result = run_at_point(*EPICENTER, 6.5, "strike_slip", BOUNDS)
    structures = pd.DataFrame({"lat": [34.05, 50.0], "lon": [-118.25, -118.25], "bld_value": [1000.0, 5.0]})
    exposure = damage_run.estimate_exposure(result, structures, "nsi_2026")
    assert exposure["properties_on_grid"] == 1 and exposure["building_value_on_grid"] == 1000
    assert exposure["properties_affected"] == 1 and exposure["affected_building_value"] == 1000
    assert exposure["max_pga_at_structures_g"] > 0


REQUEST = {
    "lat": 34.05, "lng": -118.25, "south": 33.9, "west": -118.4, "north": 34.2, "east": -118.1,
    "magnitude": 6.5, "mechanism": "strike_slip",
}


def test_endpoint_returns_exposure_when_inventory_loads(monkeypatch):
    monkeypatch.setattr("jarvis.auth.is_signed_in", lambda token: True)
    table = pd.DataFrame({"lat": [34.05], "lon": [-118.25], "bld_value": [200.0]})
    monkeypatch.setattr("jarvis.server.load_nsi", lambda bounds: table)
    response = client.post("/api/earthquake/simulate", json=REQUEST)
    body = response.json()
    assert response.status_code == 200
    assert body["exposure"]["properties_on_grid"] == 1 and body["damage"] is None
    assert body["inventory"]["id"] == "nsi_2026"


def test_endpoint_still_returns_hazard_when_inventory_fails(monkeypatch):
    monkeypatch.setattr("jarvis.auth.is_signed_in", lambda token: True)

    def fail(bounds):
        raise NsiUnavailable("down")

    monkeypatch.setattr("jarvis.server.load_nsi", fail)
    body = client.post("/api/earthquake/simulate", json=REQUEST).json()
    assert len(body["cells"]) > 0
    assert body["exposure"] is None and body["damage"] is None
    assert body["inventory"]["warning"] == "down"


def test_endpoint_validates(monkeypatch):
    monkeypatch.setattr("jarvis.auth.is_signed_in", lambda token: True)
    assert client.post("/api/earthquake/simulate", json={**REQUEST, "magnitude": 9}).status_code == 422
    assert client.post("/api/earthquake/simulate", json={**REQUEST, "mechanism": "thrust"}).status_code == 422
    flipped = {**REQUEST, "south": 35.0}
    assert client.post("/api/earthquake/simulate", json=flipped).status_code == 422


def test_footprint_mode_sizes_the_box_and_shape_to_the_magnitude():
    small = run_at_point(*EPICENTER, 5.5, "unspecified")
    large = run_at_point(*EPICENTER, 7.0, "unspecified")
    assert large["summary"]["footprint_radius_km"] > 1.5 * small["summary"]["footprint_radius_km"]
    assert large["cell_m"] > small["cell_m"] or large["rows"] > small["rows"]
    for result in (small, large):
        assert result["summary"]["footprint_radius_km"] > 0
        cells = cells_of(result)
        assert (cells[:, 2] * result["value_scale"] >= result["summary"]["min_pga_g"] - 1e-3).all()
        bounds = result["bounds"]
        lat = bounds["south"] + (cells[:, 0] + 0.5) * (bounds["north"] - bounds["south"]) / result["rows"]
        lng = bounds["west"] + (cells[:, 1] + 0.5) * (bounds["east"] - bounds["west"]) / result["cols"]
        north_m = (lat - EPICENTER[0]) * 111_320
        east_m = (lng - EPICENTER[1]) * 111_320 * np.cos(np.radians(EPICENTER[0]))
        farthest_km = np.hypot(north_m, east_m).max() / 1000
        assert farthest_km <= result["summary"]["footprint_radius_km"] + result["cell_m"] / 1000 * 1.5


def test_footprint_is_round_not_square():
    result = run_at_point(*EPICENTER, 7.0, "unspecified")
    filled = len(result["cells"]) // 3 / (result["rows"] * result["cols"])
    assert 0.6 < filled < 0.9


def test_endpoint_without_bounds_uses_the_footprint(monkeypatch):
    monkeypatch.setattr("jarvis.auth.is_signed_in", lambda token: True)
    monkeypatch.setattr("jarvis.server.load_nsi", lambda bounds: pd.DataFrame({"lat": [34.05], "lon": [-118.25], "bld_value": [1.0]}))
    body = client.post("/api/earthquake/simulate", json={"lat": 34.05, "lng": -118.25, "magnitude": 6.5, "mechanism": "reverse"}).json()
    assert body["summary"]["footprint_radius_km"] > 20 and body["exposure"]["properties_on_grid"] == 1
