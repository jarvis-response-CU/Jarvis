# References:
#   https://fastapi.tiangolo.com/tutorial/testing/
#   https://docs.pytest.org/en/stable/how-to/parametrize.html

import numpy as np
import pytest
from fastapi.testclient import TestClient

from jarvis.server import app
from jarvis.simulations.fire.map_run import run_at_point

BOULDER = (40.015, -105.2705)
client = TestClient(app)


def cells_of(result):
    return np.array(result["cells"]).reshape(-1, 3)


@pytest.mark.parametrize(
    "from_deg, direction",
    [
        (270, (0, 1)),
        (90, (0, -1)),
        (0, (-1, 0)),
        (180, (1, 0)),
    ],
)
def test_fire_runs_downwind(from_deg, direction):
    result = run_at_point(*BOULDER, hours=1, wind_speed_mps=5, wind_from_deg=from_deg)
    cells = cells_of(result)
    center = result["rows"] // 2
    offset = cells[:, :2] - center
    # Mean offset of burned cells points the way the wind blows (row, col).
    mean_row, mean_col = offset.mean(axis=0)
    assert np.sign(round(mean_row)) == direction[0]
    assert np.sign(round(mean_col)) == direction[1]


def test_fire_never_reaches_the_domain_edge():
    result = run_at_point(*BOULDER, hours=6, wind_speed_mps=10, wind_from_deg=225)
    cells = cells_of(result)
    positions = cells[:, :2]
    assert positions.min() > 0
    assert positions.max() < result["rows"] - 1
    assert cells[:, 2].max() <= result["duration_min"]


def test_bounds_are_centered_on_ignition():
    result = run_at_point(*BOULDER, hours=2, wind_speed_mps=3, wind_from_deg=0)
    b = result["bounds"]
    assert (b["south"] + b["north"]) / 2 == pytest.approx(BOULDER[0])
    assert (b["west"] + b["east"]) / 2 == pytest.approx(BOULDER[1])


def test_endpoint_runs_and_validates():
    request = {"lat": 40.0, "lng": -105.3, "hours": 1, "wind_speed_mps": 4, "wind_from_deg": 270}
    ok = client.post("/api/fire/simulate", json=request)
    assert ok.status_code == 200
    assert len(ok.json()["cells"]) > 0

    bad_request = dict(request)
    bad_request["lat"] = 95
    bad = client.post("/api/fire/simulate", json=bad_request)
    assert bad.status_code == 422
