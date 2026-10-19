# References:
#   https://bouldercounty.gov/news/boulder-county-releases-updated-list-of-structures-damaged-and-destroyed-in-the-marshall-fire/
#   https://services3.arcgis.com/APrbG4iiuZuctqvI/ArcGIS/rest/services/Boulder_County_Parcels_2021_Marshall_Fire_v3/FeatureServer/6

"""Tune the loss factors on the 2021 Marshall Fire and write data/loss_factors.csv.

A loss factor is the share of Marshall homes with a given siding that were
destroyed, out of the homes the fire reached. Damaged homes count as not
destroyed. Sidings with fewer than MIN_HOMES homes get no row, so lookups
fall back to the overall row. Each siding's share is also pulled toward the
overall share, as if it had PRIOR_HOMES more homes at that rate, so no group
lands on a flat 0 or 1.

There are no roof rows yet: nine in ten Marshall roofs on record were
asphalt, and destroyed homes' roofs are blank about twice as often as
survivors', so this data can't tell roof types apart.

Destroyed homes come from the county's Marshall list, which kept their
assessor records from before the fire. Surviving homes are the ones inside
the perimeter, described by today's records.

Run it with:  python -m jarvis.tune_loss
"""

import json

import pandas as pd

from jarvis.config import load_settings
from jarvis.damage import ANY, LOSS_FACTORS_PATH, fire_perimeter, inside, wall_group
from jarvis.structures import build

FIRE_DATE = "2021-12-30"
MIN_HOMES = 30
PRIOR_HOMES = 30
RESIDENTIAL_CLASSES = {
    "SINGLE FAM RES IMPROVEMENTS",
    "CONDOS-IMPROVEMENTS",
    "DUP/TRIPLEX IMPROVEMENTS",
    "MULTI-UNITS (4-8) IMPROVEMENTS",
    "MULTI-UNITS (9+) IMPROVEMENTS",
    "MANUFACTURED HOUSING IMPROVEMENTS",
    "FARM/RANCH RESIDENTIAL IMPROVEMENTS",
    "RES IMP NOT INTEGRAL TO AG",
}
NEW_MATERIAL_PERMITS = ["RESIDENTIAL RE-ROOF", "SIDING"]


def destroyed_homes(path):
    """Homes on the Marshall destroyed list, with their siding before the fire."""
    with open(path) as file:
        features = json.load(file)["features"]
    homes = pd.DataFrame([feature["properties"] for feature in features])
    is_destroyed = homes["Status"] == "Destroyed"
    is_home = homes["bldgClassDscr"].isin(RESIDENTIAL_CLASSES)
    homes = homes[is_destroyed & is_home]
    return pd.DataFrame({
        "strap": homes["strap"],
        "wall": homes["ExtWallDscrPrim"],
        "destroyed": True,
    })


def straps_to_skip(path):
    """Properties whose records don't describe the home that faced the fire.

    That's anything re-roofed or re-sided since the fire, and homes still
    being built when it hit, which the assessor dates 2021 anyway.
    """
    permits = pd.read_csv(path, dtype=str, keep_default_na=False)
    issued = pd.to_datetime(permits["issue_dt"], format="%m/%d/%Y %I:%M:%S %p", errors="coerce")
    category = permits["permit_category"]
    is_new_material = category.isin(NEW_MATERIAL_PERMITS) & (issued >= FIRE_DATE)
    is_unfinished = (category == "NEW CONSTRUCTION") & issued.between("2021-10-01", FIRE_DATE)
    return set(permits.loc[is_new_material | is_unfinished, "strap"])


def built_before_fire(homes):
    return (homes["built_year"] <= pd.Timestamp(FIRE_DATE).year).fillna(False)


def surviving_homes(structures, perimeter, skip_straps):
    """Homes inside the perimeter that existed during the fire and weren't destroyed."""
    homes = structures[structures["bldg_class"].isin(RESIDENTIAL_CLASSES)]
    homes = homes[inside(perimeter, homes["lat"].to_numpy(), homes["lon"].to_numpy())]
    homes = homes[built_before_fire(homes) & ~homes["strap"].isin(skip_straps)]
    return pd.DataFrame({
        "strap": homes["strap"],
        "wall": homes["wall"],
        "destroyed": False,
    })


def rate_row(wall, homes, parent_factor=None, prior_homes=PRIOR_HOMES):
    """One row of the loss table, pulled toward parent_factor when there is one."""
    destroyed = int(homes["destroyed"].sum())
    if parent_factor is None:
        factor = destroyed / len(homes)
    else:
        factor = (destroyed + prior_homes * parent_factor) / (len(homes) + prior_homes)
    return {
        "wall": wall,
        "roof": ANY,
        "loss_factor": round(factor, 3),
        "destroyed": destroyed,
        "homes": len(homes),
    }


def loss_table(homes, min_homes=MIN_HOMES, prior_homes=PRIOR_HOMES):
    """Destroyed share overall and for each siding group."""
    homes = homes.assign(wall=wall_group(homes["wall"]))
    overall = rate_row(ANY, homes)
    rows = [overall]
    for wall, wall_homes in homes.groupby("wall"):
        if wall != "unknown" and len(wall_homes) >= min_homes:
            rows.append(rate_row(wall, wall_homes, overall["loss_factor"], prior_homes))
    return pd.DataFrame(rows)


def main():
    raw_dir = load_settings().raw_dir / "wildfire"
    perimeter = fire_perimeter(raw_dir / "fire_perimeters.geojson", "MARSHALL")
    structures = build(raw_dir)

    destroyed = destroyed_homes(raw_dir / "marshall_fire_parcels.geojson")
    # The list marks a whole parcel destroyed even when only a shed or garage
    # burned. A listed house still on the roll from before the fire stood.
    standing = structures.loc[built_before_fire(structures), "strap"]
    destroyed = destroyed[~destroyed["strap"].isin(standing)]

    skip = set(destroyed["strap"]) | straps_to_skip(raw_dir / "permits.csv")
    survived = surviving_homes(structures, perimeter, skip)
    print(f"tuning on {len(destroyed)} destroyed and {len(survived)} surviving homes")

    table = loss_table(pd.concat([destroyed, survived], ignore_index=True))
    table.to_csv(LOSS_FACTORS_PATH, index=False)
    print(table.to_string(index=False))
    print(f"wrote {LOSS_FACTORS_PATH}")


if __name__ == "__main__":
    main()
