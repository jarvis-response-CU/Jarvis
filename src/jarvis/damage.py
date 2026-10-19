# References:
#   https://en.wikipedia.org/wiki/Point_in_polygon#Ray_casting_algorithm
#   https://numpy.org/doc/stable/reference/generated/numpy.errstate.html

"""Damage numbers for a fire: which buildings it reaches and what they're worth.

Exposed value is the total building value inside the burned area. Land isn't
counted because it doesn't burn. Expected loss multiplies each building's
value by a loss factor looked up from its siding and roof
(data/loss_factors.csv, tuned by jarvis.tune_loss).

Run it with:  python -m jarvis.damage
That prints the exposed value inside the real 2021 Marshall Fire perimeter.
"""

import json
from itertools import pairwise

import numpy as np
import pandas as pd

from jarvis.config import PROJECT_ROOT, load_settings
from jarvis.structures import build

LOSS_FACTORS_PATH = PROJECT_ROOT / "data" / "loss_factors.csv"
ANY = "any"
# Assessor descriptions grouped into the materials the loss table is keyed on.
# Anything else counts as "other", and a blank as "unknown".
WALL_GROUPS = {
    "Frame Wood/Shake": "wood",
    "Log": "wood",
    "Cedar": "wood",
    "Brick Veneer": "masonry",
    "Brick on Block": "masonry",
    "Moss Rock/Flagstone": "masonry",
    "Faux Stone": "masonry",
    "Painted Block": "masonry",
    "Frame Stucco": "stucco",
    "Block Stucco": "stucco",
    "Cement Board": "fiber_cement",
    "Vinyl": "vinyl_metal",
    "Metal": "vinyl_metal",
}
ROOF_GROUPS = {
    "Asphalt": "asphalt",
    "Shake": "wood_shake",
    "Metal": "metal_tile",
    "Clay Tile": "metal_tile",
    "Concrete Tile": "metal_tile",
    "Rubber Membrane": "flat",
    "Built-Up": "flat",
    "Tar and Gravel": "flat",
    "Roll": "flat",
}


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


def material_groups(descriptions, groups):
    """Map assessor descriptions to loss-table groups."""
    descriptions = pd.Series(descriptions, dtype=object)
    is_blank = descriptions.isna() | (descriptions.str.strip() == "")
    grouped = descriptions.map(groups).fillna("other")
    return grouped.where(~is_blank, "unknown")


def wall_group(walls):
    return material_groups(walls, WALL_GROUPS)


def roof_group(roofs):
    return material_groups(roofs, ROOF_GROUPS)


def read_loss_factors(path=LOSS_FACTORS_PATH):
    """The loss table as {(wall group, roof group): loss factor}."""
    table = pd.read_csv(path)
    factors = {}
    for row in table.itertuples():
        factors[(row.wall, row.roof)] = row.loss_factor
    if (ANY, ANY) not in factors:
        raise ValueError(f"{path} needs an overall row with wall and roof set to {ANY!r}")
    return factors


def loss_factors(walls, roofs, factors):
    """Loss factor for each building.

    Uses the siding and roof row when the table has one, else the siding-only
    row, else the overall row. Unknown materials have no rows of their own
    (see jarvis.tune_loss), so they always fall back.
    """
    result = []
    for wall, roof in zip(wall_group(walls), roof_group(roofs), strict=True):
        for key in [(wall, roof), (wall, ANY)]:
            if key in factors:
                result.append(factors[key])
                break
        else:
            result.append(factors[(ANY, ANY)])
    return np.array(result)


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
