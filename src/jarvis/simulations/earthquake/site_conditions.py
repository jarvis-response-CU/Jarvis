"""Vs30 for the grid; reference rock when no local raster is installed."""

import numpy as np

from jarvis.config import load_settings
from jarvis.simulations.common.grid import GridSpec, cell_centers

VS30_DEFAULT = 760.0


def find_vs30_raster(bounds: dict):
    root = load_settings().raw_dir / "earthquake"
    for path in sorted(root.glob("*/vs30.tif")) if root.exists() else []:
        if covers(path, bounds):
            return path
    return None


def covers(path, bounds: dict) -> bool:
    import rasterio
    from rasterio.warp import transform_bounds

    with rasterio.open(path) as src:
        west, south, east, north = transform_bounds(
            "EPSG:4326", src.crs, bounds["west"], bounds["south"], bounds["east"], bounds["north"]
        )
        b = src.bounds
        return b.left <= west and b.right >= east and b.bottom <= south and b.top >= north


def load_vs30(bounds: dict, grid: GridSpec, default: float = VS30_DEFAULT):
    """(vs30 array [rows, cols], source label)."""
    path = find_vs30_raster(bounds)
    if path is None:
        return np.full((grid.rows, grid.cols), default), "vs30_constant"

    import rasterio
    from rasterio.warp import transform

    lat, lon = cell_centers(grid)
    with rasterio.open(path) as src:
        x, y = transform("EPSG:4326", src.crs, lon.ravel().tolist(), lat.ravel().tolist())
        values = np.array([v[0] for v in src.sample(zip(x, y))], dtype=float)
        nodata = src.nodata
    values = values.reshape(grid.rows, grid.cols)
    bad = ~np.isfinite(values) | (values <= 0)
    if nodata is not None:
        bad |= values == nodata
    values[bad] = default
    return np.clip(values, 150.0, 1500.0), "vs30_raster"
