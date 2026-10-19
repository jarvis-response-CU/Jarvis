# References:
#   https://bouldercounty.gov/property-and-land/assessor/data-download/
#   https://en.wikipedia.org/wiki/Shoelace_formula
#   https://en.wikipedia.org/wiki/Centroid#Of_a_polygon
#   https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_sql.html

"""Build boulder.structures: one row per property with a building value.

Joins the assessor's value and building files to the county parcel shapes
(all downloaded by jarvis.wildfire) so every property gets a location. Class,
year built and materials come from the property's largest building section.
Only the building value counts, because land doesn't burn.

Run it with:  python -m jarvis.structures
"""

import json

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from jarvis.config import load_settings
from jarvis.inbox import database_url

# Like inbox, this schema isn't exposed by Supabase's web API.
SCHEMA = "boulder"
TABLE = "structures"
COLUMNS = [
    "strap", "parcel_no", "lat", "lon", "bld_value", "bldg_class", "built_year", "roof", "wall",
]
METERS_PER_DEGREE = 111_320
# The assessor fills unknown parcel numbers with these; they would match each other.
BLANK_PARCEL_NUMBERS = ["", "000000000000"]


def ring_area_and_center(ring):
    """Area in square meters and (lat, lon) center of a closed ring of [lon, lat] points."""
    points = np.asarray(ring, dtype=float)

    # Measure on a flat grid around the ring; a degree of longitude is shorter
    # than a degree of latitude this far north.
    lon0, lat0 = points.mean(axis=0)
    meters_per_degree_lon = METERS_PER_DEGREE * np.cos(np.radians(lat0))
    x = (points[:, 0] - lon0) * meters_per_degree_lon
    y = (points[:, 1] - lat0) * METERS_PER_DEGREE

    cross = x[:-1] * y[1:] - x[1:] * y[:-1]
    area = cross.sum() / 2
    if area == 0:
        return 0.0, None
    center_x = ((x[:-1] + x[1:]) * cross).sum() / (6 * area)
    center_y = ((y[:-1] + y[1:]) * cross).sum() / (6 * area)
    lat = lat0 + center_y / METERS_PER_DEGREE
    lon = lon0 + center_x / meters_per_degree_lon
    return abs(area), (lat, lon)


def parcel_centers(path):
    """Center of each parcel's largest piece: a table of parcel_no, lat, lon."""
    with open(path) as file:
        features = json.load(file)["features"]

    largest = {}
    for feature in features:
        parcel_no = feature["properties"]["PARCEL_NO"]
        geometry = feature["geometry"]
        if parcel_no is None or parcel_no in BLANK_PARCEL_NUMBERS:
            continue
        # A handful of parcels come with an empty shape.
        if geometry is None or not geometry["coordinates"]:
            continue
        polygons = geometry["coordinates"]
        if geometry["type"] == "Polygon":
            polygons = [polygons]

        # Some parcels come in several pieces, sometimes as separate features.
        # A polygon's first ring is its outline; the others are holes. The
        # outline's center can miss a concave parcel or land in a hole (about
        # 270 properties, up to about 330 m away).
        for polygon in polygons:
            area, center = ring_area_and_center(polygon[0])
            previous_area = largest[parcel_no][0] if parcel_no in largest else 0
            if center is not None and area > previous_area:
                largest[parcel_no] = (area, center)

    rows = []
    for parcel_no, (_area, (lat, lon)) in largest.items():
        rows.append({"parcel_no": parcel_no, "lat": lat, "lon": lon})
    return pd.DataFrame(rows, columns=["parcel_no", "lat", "lon"])


def primary_buildings(path):
    """Class, year built, roof and siding of each property's largest building section."""
    # A building is listed once per section and again for each basement,
    # garage or material type, in no particular order.
    buildings = pd.read_csv(path, dtype=str, keep_default_na=False)
    finished_sf = pd.to_numeric(buildings["TotalFinishedSF"], errors="coerce")
    buildings["finished_sf"] = finished_sf.fillna(0)
    buildings["bld_num"] = pd.to_numeric(buildings["bld_num"], errors="coerce")

    largest_first = buildings.sort_values(
        ["strap", "finished_sf", "bld_num"], ascending=[True, False, True]
    )
    primary = largest_first.drop_duplicates("strap")

    roof = primary["Roof_CoverDscr"].str.strip()
    wall = primary["ExtWallDscrPrim"].str.strip()
    # The assessor uses 0 for an unknown year.
    built_year = pd.to_numeric(primary["builtYear"], errors="coerce").astype("Int64")
    return pd.DataFrame({
        "strap": primary["strap"],
        "bldg_class": primary["bldgClassDscr"].str.strip(),
        "built_year": built_year.where(built_year > 0),
        "roof": roof.where(roof != ""),
        "wall": wall.where(wall != ""),
    })


def build(raw_dir):
    """Every property with a building value and a location, as one table."""
    values = pd.read_csv(raw_dir / "values.csv", dtype=str, keep_default_na=False)
    accounts = pd.read_csv(raw_dir / "account_parcels.csv", dtype=str, keep_default_na=False)
    accounts = accounts.rename(columns={"Parcelno": "parcel_no"})

    table = pd.DataFrame({
        "strap": values["strap"],
        "bld_value": pd.to_numeric(values["bldAcutalVal"]),  # the county's spelling
    })
    table = table[table["bld_value"] > 0]
    table = table.merge(accounts, on="strap", validate="one_to_one")
    table = table.merge(parcel_centers(raw_dir / "parcels.geojson"), on="parcel_no")
    table = table.merge(primary_buildings(raw_dir / "buildings.csv"), on="strap", how="left")
    return table[COLUMNS].reset_index(drop=True)


def load(table, engine):
    with engine.begin() as connection:
        connection.execute(text(f"create schema if not exists {SCHEMA}"))
    table.to_sql(TABLE, engine, schema=SCHEMA, if_exists="replace", index=False, chunksize=1000)


def main():
    table = build(load_settings().raw_dir / "wildfire")
    total = table["bld_value"].sum()
    print(f"built {len(table)} properties with ${total:,} in building value")
    load(table, create_engine(database_url()))
    print(f"loaded them into {SCHEMA}.{TABLE}")


if __name__ == "__main__":
    main()
