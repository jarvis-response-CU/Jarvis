# References:
#   https://en.wikipedia.org/wiki/Point_in_polygon#Ray_casting_algorithm
#   https://numpy.org/doc/stable/reference/generated/numpy.errstate.html

"""Damage numbers for a fire: which buildings it reaches and what they're worth.

Exposed value is the total building value inside the burned area. Land isn't
counted because it doesn't burn.

Run it with:  python -m jarvis.damage
That prints the exposed value inside the real 2021 Marshall Fire perimeter.
"""

import json
from itertools import pairwise

import numpy as np

from jarvis.config import load_settings
from jarvis.structures import build


def inside_ring(ring, lats, lons):
    """Whether each point is inside a closed ring of [lon, lat] points."""
    result = np.zeros(len(lats), dtype=bool)
    for (lon1, lat1), (lon2, lat2) in pairwise(ring):
        # Ray casting: a point is inside if a line running east from it
        # crosses the ring's edges an odd number of times.
        crosses_latitude = (lat1 > lats) != (lat2 > lats)
        # Flat edges divide by zero here, but crosses_latitude is False for them.
        with np.errstate(divide="ignore", invalid="ignore"):
            crossing_lon = lon1 + (lats - lat1) * (lon2 - lon1) / (lat2 - lat1)
        result ^= crosses_latitude & (lons < crossing_lon)
    return result


def inside(geometry, lats, lons):
    """Whether each point is inside a GeoJSON Polygon or MultiPolygon."""
    polygons = geometry["coordinates"]
    if geometry["type"] == "Polygon":
        polygons = [polygons]

    result = np.zeros(len(lats), dtype=bool)
    for polygon in polygons:
        # The first ring is the outline; a point inside a hole flips back out.
        for ring in polygon:
            result ^= inside_ring(ring, lats, lons)
    return result


def fire_perimeter(path, name):
    """The shape of one fire from the county's fire history layer."""
    with open(path) as file:
        features = json.load(file)["features"]
    for feature in features:
        if feature["properties"]["NAME"] == name:
            return feature["geometry"]
    raise ValueError(f"no fire named {name!r} in {path}")


def main():
    raw_dir = load_settings().raw_dir / "wildfire"
    structures = build(raw_dir)
    marshall = fire_perimeter(raw_dir / "fire_perimeters.geojson", "MARSHALL")

    is_exposed = inside(marshall, structures["lat"].to_numpy(), structures["lon"].to_numpy())
    exposed = structures[is_exposed]
    print(f"{len(exposed)} properties with buildings inside the Marshall Fire perimeter")
    print(f"exposed value: ${exposed['bld_value'].sum():,} at today's assessor values")


if __name__ == "__main__":
    main()
