"""Local DEM loading. Never downloads; the DEM must already be under data/raw/flood."""

import math
from dataclasses import dataclass

import numpy as np

from jarvis.config import load_settings
from jarvis.simulations.common.grid import GridSpec, domain_size_m, validate_bounds

MAX_CELLS = 250_000
METERS_PER_DEGREE = 111_320


class DemUnavailable(ValueError):
    pass


@dataclass
class TerrainGrid:
    elevation: np.ndarray
    grid: GridSpec
    source: str


def dem_candidates():
    root = load_settings().raw_dir / "flood"
    if not root.exists():
        return []
    return [*sorted(root.glob("*/dem.tif")), *([root / "dem.tif"] if (root / "dem.tif").exists() else [])]


def native_cell_m(src) -> float:
    resolution = max(abs(src.res[0]), abs(src.res[1]))
    if src.crs and src.crs.is_geographic:
        return resolution * METERS_PER_DEGREE
    return resolution


def find_dem(bounds: dict):
    import rasterio
    from rasterio.warp import transform_bounds

    candidates = dem_candidates()
    for path in candidates:
        with rasterio.open(path) as src:
            west, south, east, north = transform_bounds(
                "EPSG:4326", src.crs, bounds["west"], bounds["south"], bounds["east"], bounds["north"]
            )
            b = src.bounds
            if b.left <= west and b.right >= east and b.bottom <= south and b.top >= north:
                return path
    if not candidates:
        raise DemUnavailable("no local DEM is installed; add one at data/raw/flood/dem.tif")
    raise DemUnavailable("the requested area is outside local DEM coverage")


def load_dem(bounds: dict, max_cells: int = MAX_CELLS) -> TerrainGrid:
    """Elevation for the box in meters on a square-celled south-up grid, at native resolution unless over max_cells."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_bounds
    from rasterio.warp import reproject

    validate_bounds(bounds)
    path = find_dem(bounds)
    width_m, height_m = domain_size_m(bounds)
    with rasterio.open(path) as src:
        native = native_cell_m(src)
        cell_m = max(native, math.sqrt(width_m * height_m / max_cells))
        rows = max(1, round(height_m / cell_m))
        cols = max(1, round(width_m / cell_m))
        resampling = Resampling.average if cell_m > 1.5 * native else Resampling.bilinear
        destination = np.full((rows, cols), np.nan, dtype="float32")
        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            dst_transform=from_bounds(
                bounds["west"], bounds["south"], bounds["east"], bounds["north"], cols, rows
            ),
            dst_crs="EPSG:4326",
            dst_nodata=np.nan,
            src_nodata=src.nodata,
            resampling=resampling,
        )

    elevation = np.flipud(destination).astype(float)
    if not np.isfinite(elevation).any():
        raise DemUnavailable("the local DEM has no data for the requested area")
    # nodata cells become the lowest ground so water can still drain into them
    elevation = np.where(np.isfinite(elevation), elevation, np.nanmin(elevation))
    grid = GridSpec(
        bounds["south"], bounds["west"], bounds["north"], bounds["east"], rows, cols, cell_m
    )
    return TerrainGrid(elevation, grid, str(path))
