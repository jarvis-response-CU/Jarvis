# References:
#   https://docs.pytest.org/en/stable/how-to/tmp_path.html

import json

import numpy as np
import pandas as pd
import pytest

from jarvis.damage import (
    fire_perimeter,
    inside,
    loss_factors,
    read_loss_factors,
    wall_group,
)


def square(west, south, size):
    east = west + size
    north = south + size
    return [[west, south], [east, south], [east, north], [west, north], [west, south]]


def test_points_in_a_hole_are_outside():
    geometry = {"type": "Polygon", "coordinates": [square(0, 0, 10), square(4, 4, 2)]}
    lats = np.array([1.0, 5.0, 11.0])
    lons = np.array([1.0, 5.0, 1.0])
    assert inside(geometry, lats, lons).tolist() == [True, False, False]


def test_points_in_either_piece_of_a_multipolygon_are_inside():
    geometry = {"type": "MultiPolygon", "coordinates": [[square(0, 0, 1)], [square(5, 5, 1)]]}
    lats = np.array([0.5, 5.5, 3.0])
    lons = np.array([0.5, 5.5, 3.0])
    assert inside(geometry, lats, lons).tolist() == [True, True, False]


def test_fire_perimeter_is_found_by_name(tmp_path):
    marshall = {"type": "Polygon", "coordinates": [square(0, 0, 1)]}
    features = [
        {"type": "Feature", "properties": {"NAME": "CALWOOD"}, "geometry": None},
        {"type": "Feature", "properties": {"NAME": "MARSHALL"}, "geometry": marshall},
    ]
    path = tmp_path / "fire_perimeters.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))

    assert fire_perimeter(path, "MARSHALL") == marshall
    with pytest.raises(ValueError, match="no fire named"):
        fire_perimeter(path, "HAYMAN")


def test_assessor_siding_is_grouped():
    walls = ["Frame Wood/Shake", "Cement Board", "Strawbale", "", None]
    assert wall_group(walls).tolist() == ["wood", "fiber_cement", "other", "unknown", "unknown"]


def test_loss_factor_falls_back_to_siding_then_overall():
    factors = {("wood", "asphalt"): 0.6, ("wood", "any"): 0.5, ("any", "any"): 0.4}
    walls = ["Frame Wood/Shake", "Frame Wood/Shake", "Brick Veneer", None]
    roofs = ["Asphalt", None, "Asphalt", "Asphalt"]
    assert loss_factors(walls, roofs, factors).tolist() == [0.6, 0.5, 0.4, 0.4]


def test_loss_table_without_an_overall_row_is_rejected(tmp_path):
    path = tmp_path / "loss_factors.csv"
    table = pd.DataFrame({"wall": ["wood"], "roof": ["any"], "loss_factor": [0.5]})
    table.to_csv(path, index=False)
    with pytest.raises(ValueError, match="overall row"):
        read_loss_factors(path)
