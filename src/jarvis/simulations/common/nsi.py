# References:
#   https://www.hec.usace.army.mil/confluence/nsi/technicalreferences/2026/api-reference-guide
#   https://www.hec.usace.army.mil/confluence/nsi/technicalreferences/2026/technical-documentation

"""National Structure Inventory loader with a tiled local cache."""

import json
import math
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from jarvis.config import load_settings

NSI_RELEASE = "2026"
INVENTORY_ID = "nsi_2026"
# bump when the normalized columns change so stale tiles are not reused
CACHE_VERSION = "v2"
TILE_DEG = 0.05
MAX_TILES = 400
REQUEST_TIMEOUT_S = 60
FETCH_WORKERS = 8

# public nsi field -> jarvis column
FIELD_MAP = {
    "fd_id": "asset_id",
    "firmzone": "flood_zone",
    "x": "lon",
    "y": "lat",
    "occtype": "occupancy",
    "bldgtype": "building_type",
    "sqft": "sqft",
    "found_type": "foundation_type",
    "found_ht": "foundation_height_ft",
    "num_story": "stories",
    "val_struct": "depreciated_structure_value",
    "val_cont": "contents_value",
    "med_yr_blt": "median_year_built",
    "ground_elv": "ground_elevation_ft",
    "bldheight": "building_height_m",
    "fullrep": "replacement_value",
}
COLUMNS = [*FIELD_MAP.values(), "bld_value"]


class NsiUnavailable(RuntimeError):
    pass


def tile_range(bounds: dict) -> tuple[range, range]:
    rows = range(math.floor(bounds["south"] / TILE_DEG), math.ceil(bounds["north"] / TILE_DEG))
    cols = range(math.floor(bounds["west"] / TILE_DEG), math.ceil(bounds["east"] / TILE_DEG))
    return rows, cols


def tile_bounds(row: int, col: int) -> dict:
    return {
        "south": row * TILE_DEG,
        "north": (row + 1) * TILE_DEG,
        "west": col * TILE_DEG,
        "east": (col + 1) * TILE_DEG,
    }


def cache_dir():
    return load_settings().processed_dir / "nsi" / NSI_RELEASE / CACHE_VERSION


def normalize(features: list) -> pd.DataFrame:
    """Public NSI GeoJSON features as a Jarvis-schema table."""
    records = []
    for feature in features:
        props = dict(feature.get("properties") or {})
        coords = (feature.get("geometry") or {}).get("coordinates")
        if coords and len(coords) >= 2:
            props.setdefault("x", coords[0])
            props.setdefault("y", coords[1])
        records.append({new: props.get(old) for old, new in FIELD_MAP.items()})
    table = pd.DataFrame(records, columns=list(FIELD_MAP.values()))
    for column in table.columns:
        if column not in ("asset_id", "flood_zone", "occupancy", "building_type", "foundation_type"):
            table[column] = pd.to_numeric(table[column], errors="coerce")
    table = table.dropna(subset=["lat", "lon"])
    # full replacement value when present, else depreciated structure value; no land
    table["bld_value"] = table["replacement_value"].fillna(table["depreciated_structure_value"])
    table = table[table["bld_value"].notna() & (table["bld_value"] > 0)]
    return table[COLUMNS].reset_index(drop=True)


def fetch_tile(bounds: dict) -> list:
    # the 2026 api returns nothing for bbox queries; a polygon body works
    root = load_settings().nsi_api_root.rstrip("/")
    w, s_, e, n = bounds["west"], bounds["south"], bounds["east"], bounds["north"]
    polygon = {"type": "Polygon", "coordinates": [[[w, s_], [e, s_], [e, n], [w, n], [w, s_]]]}
    request = urllib.request.Request(
        f"{root}/structures?fmt=fc",
        data=json.dumps(polygon).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "jarvis"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        payload = json.load(response)
    if "features" not in payload:
        raise ValueError(f"unexpected NSI response: {str(payload)[:200]}")
    return payload["features"]


def load_tile(row: int, col: int, fetch=fetch_tile) -> pd.DataFrame:
    path = cache_dir() / f"tile_{row}_{col}.csv"
    if path.exists():
        return pd.read_csv(path)
    table = normalize(fetch(tile_bounds(row, col)))
    # an empty tile is refetched next time rather than trusted
    if len(table):
        path.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(path, index=False)
    return table


def load_nsi(bounds: dict, fetch=fetch_tile) -> pd.DataFrame:
    """Structures inside bounds; cached tiles are reused and only missing tiles are fetched."""
    rows, cols = tile_range(bounds)
    tiles = [(row, col) for row in rows for col in cols]
    if len(tiles) > MAX_TILES:
        raise NsiUnavailable(f"area needs {len(tiles)} inventory tiles; the limit is {MAX_TILES}")
    try:
        with ThreadPoolExecutor(FETCH_WORKERS) as pool:
            parts = list(pool.map(lambda tile: load_tile(*tile, fetch=fetch), tiles))
    except Exception as err:
        raise NsiUnavailable(f"NSI request failed: {err}") from err

    table = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=COLUMNS)
    inside = (
        (table["lat"] >= bounds["south"]) & (table["lat"] < bounds["north"])
        & (table["lon"] >= bounds["west"]) & (table["lon"] < bounds["east"])
    )
    return table[inside].reset_index(drop=True)
