"""Georeferenced grids shared by every hazard. Row 0 is south, col 0 is west."""

from dataclasses import dataclass

import numpy as np
from pyproj import Transformer


@dataclass(frozen=True)
class GridSpec:
    south: float
    west: float
    north: float
    east: float
    rows: int
    cols: int
    cell_m: float

    @classmethod
    def from_result(cls, result: dict) -> "GridSpec":
        bounds = result["bounds"]
        return cls(
            bounds["south"], bounds["west"], bounds["north"], bounds["east"],
            result["rows"], result["cols"], result.get("cell_m", 0.0),
        )

    @property
    def bounds(self) -> dict:
        return {"south": self.south, "west": self.west, "north": self.north, "east": self.east}


def latlon_to_row_col(grid: GridSpec, lat, lon):
    """Integer row and col of each point; out-of-grid points get out-of-range indices."""
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    row = np.floor((lat - grid.south) / (grid.north - grid.south) * grid.rows)
    col = np.floor((lon - grid.west) / (grid.east - grid.west) * grid.cols)
    return row.astype(int), col.astype(int)


def row_col_to_latlon(grid: GridSpec, row, col):
    """Center of each cell."""
    row = np.asarray(row, dtype=float)
    col = np.asarray(col, dtype=float)
    lat = grid.south + (row + 0.5) * (grid.north - grid.south) / grid.rows
    lon = grid.west + (col + 0.5) * (grid.east - grid.west) / grid.cols
    return lat, lon


def cell_centers(grid: GridSpec):
    """2-D arrays [rows, cols] of cell-center latitude and longitude."""
    lat, lon = row_col_to_latlon(grid, np.arange(grid.rows), np.arange(grid.cols))
    lon2d, lat2d = np.meshgrid(lon, lat)
    return lat2d, lon2d


def utm_transformer(lat: float, lon: float) -> Transformer:
    zone = int((lon + 180) // 6) % 60 + 1
    epsg = (32600 if lat >= 0 else 32700) + zone
    return Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)


def to_local_xy(transformer: Transformer, lat, lon):
    """Meters in the transformer's local metric projection."""
    return transformer.transform(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))


def domain_size_m(bounds: dict) -> tuple[float, float]:
    """(width, height) of a lat/lon box in meters, measured along its middle."""
    lat0 = (bounds["south"] + bounds["north"]) / 2
    lon0 = (bounds["west"] + bounds["east"]) / 2
    transformer = utm_transformer(lat0, lon0)
    west, _ = to_local_xy(transformer, lat0, bounds["west"])
    east, _ = to_local_xy(transformer, lat0, bounds["east"])
    _, south = to_local_xy(transformer, bounds["south"], lon0)
    _, north = to_local_xy(transformer, bounds["north"], lon0)
    return float(east - west), float(north - south)


def validate_bounds(bounds: dict) -> None:
    if not (-90 <= bounds["south"] < bounds["north"] <= 90):
        raise ValueError("south must be below north, within -90 to 90")
    if not (-180 <= bounds["west"] < bounds["east"] <= 180):
        raise ValueError("west must be below east, within -180 to 180")


def encode_sparse(rows, cols, values) -> list:
    """Flat [row, col, value, ...] list, the compact form the front end reads."""
    packed = np.stack([np.asarray(rows), np.asarray(cols), np.asarray(values)], axis=1)
    return packed.astype(int).ravel().tolist()
