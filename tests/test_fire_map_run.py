# References:
#   https://fastapi.tiangolo.com/tutorial/testing/
#   https://docs.pytest.org/en/stable/how-to/parametrize.html

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from jarvis.server import app
from jarvis.simulations.fire.map_run import run_at_point

BOULDER = (40.015, -105.2705)
client = TestClient(app)


def cells_of(result):
    return np.array(result["cells"]).reshape(-1, 3)


def meters_from_ignition(result):
    """(east, north) meters from the ignition point to each burned cell's center."""
    bounds = result["bounds"]
    cells = cells_of(result)
    lat = bounds["south"] + (cells[:, 0] + 0.5) * (bounds["north"] - bounds["south"]) / result["rows"]
    lng = bounds["west"] + (cells[:, 1] + 0.5) * (bounds["east"] - bounds["west"]) / result["cols"]
    north = (lat - BOULDER[0]) * 111_320
    east = (lng - BOULDER[1]) * 111_320 * np.cos(np.radians(BOULDER[0]))
    return east, north


def burned_km2(result):
    return len(result["cells"]) // 3 * result["cell_m"] ** 2 / 1e6


@pytest.mark.parametrize(
    "from_deg, direction",
    [
        (270, (1, 0)),
        (90, (-1, 0)),
        (0, (0, -1)),
        (180, (0, 1)),
        (225, (1, 1)),
    ],
)
def test_fire_runs_downwind(from_deg, direction):
    result = run_at_point(*BOULDER, hours=1, wind_speed_mps=5, wind_from_deg=from_deg)
    east, north = meters_from_ignition(result)
    # Mean position of the burn is on the side the wind blows toward (east, north).
    assert np.sign(round(east.mean() / 100)) == direction[0]
    assert np.sign(round(north.mean() / 100)) == direction[1]


def test_fire_burns_about_as_much_whichever_way_the_wind_blows():
    # The model spreads in 8 directions; the grid is turned so off-axis wind
    # doesn't starve a narrow fire.
    on_axis = burned_km2(run_at_point(*BOULDER, hours=3, wind_speed_mps=15, wind_from_deg=270))
    off_axis = burned_km2(run_at_point(*BOULDER, hours=3, wind_speed_mps=15, wind_from_deg=247.5))
    assert off_axis == pytest.approx(on_axis, rel=0.15)


def test_ignition_point_is_inside_the_bounds_and_burns_first():
    result = run_at_point(*BOULDER, hours=2, wind_speed_mps=3, wind_from_deg=0)
    b = result["bounds"]
    assert b["south"] < BOULDER[0] < b["north"]
    assert b["west"] < BOULDER[1] < b["east"]
    assert cells_of(result)[:, 2].min() == 0
    assert cells_of(result)[:, 2].max() <= result["duration_min"]


def test_endpoint_runs_and_validates(monkeypatch):
    one_house = pd.DataFrame([{"lat": 40.0, "lon": -105.3, "bld_value": 100, "loss_factor": 0.5}])
    monkeypatch.setattr("jarvis.server.load_structures", lambda: one_house)
    request = {"lat": 40.0, "lng": -105.3, "hours": 1, "wind_speed_mps": 4, "wind_from_deg": 270}
    ok = client.post("/api/fire/simulate", json=request)
    assert ok.status_code == 200
    assert len(ok.json()["cells"]) > 0
    assert ok.json()["damage"]["properties"] == 1

    bad_request = dict(request)
    bad_request["lat"] = 95
    bad = client.post("/api/fire/simulate", json=bad_request)
    assert bad.status_code == 422
