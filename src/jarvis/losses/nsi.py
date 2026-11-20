"""Normalize NSI structures into loss assets. Public NSI has no parcel-level construction detail."""

import pandas as pd

from jarvis.losses.common import ASSET_COLUMNS, FEET_PER_METER


def nsi_to_assets(table: pd.DataFrame) -> pd.DataFrame:
    """One row per structure with the LossAsset columns, plus the NSI flood zone."""
    assets = pd.DataFrame(index=table.index)
    assets["asset_id"] = table["asset_id"].astype("string") if "asset_id" in table else table.index.astype(str)
    assets["lat"] = table["lat"]
    assets["lon"] = table["lon"]
    assets["occupancy"] = table["occupancy"]
    assets["building_type"] = table["building_type"]
    # nsi has no hazus structure type or design level; enrichment must supply them
    assets["structure_type"] = None
    assets["design_level"] = None
    assets["year_built"] = table["median_year_built"]
    assets["stories"] = table["stories"]
    assets["sqft"] = table["sqft"]
    assets["foundation_type"] = table["foundation_type"]
    # nsi foundation height is in feet
    assets["first_floor_height_m"] = table["foundation_height_ft"] / FEET_PER_METER
    assets["structure_value"] = table["bld_value"]
    assets["contents_value"] = table["contents_value"]
    assets["wall"] = None
    assets["roof"] = None
    assets["source"] = "nsi"
    assets["flood_zone"] = table["flood_zone"] if "flood_zone" in table else None
    return assets[[*ASSET_COLUMNS, "flood_zone"]]
