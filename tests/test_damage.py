# References:
#   https://docs.pytest.org/en/stable/how-to/tmp_path.html

import json

import numpy as np
import pytest

from jarvis.damage import fire_perimeter, inside


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
