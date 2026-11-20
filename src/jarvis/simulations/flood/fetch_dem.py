# References:
#   https://apps.nationalmap.gov/3depdem/
#   https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer

"""Offline step: clip a region's DEM from USGS 3DEP into data/raw/flood/<region>/dem.tif.

Run by hand; the flood endpoint never downloads. Example:
    python -m jarvis.simulations.flood.fetch_dem --region nyc
"""

import argparse
import io
import math
import urllib.parse
import urllib.request

import numpy as np

from jarvis.config import load_settings
from jarvis.simulations.common.grid import validate_bounds

SERVICE_URL = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/exportImage"
# same box the map opens on for flooding (REGIONS.flood in web/js/map.js)
REGIONS = {"nyc": {"south": 40.4774, "west": -74.2591, "north": 40.9176, "east": -73.7004}}
ARCSEC_DEG = 1 / 3600
TILE_PX = 2000
NODATA = -9999.0
REQUEST_TIMEOUT_S = 120


def export_url(bounds: dict, width: int, height: int) -> str:
    query = {
        "bbox": f"{bounds['west']},{bounds['south']},{bounds['east']},{bounds['north']}",
        "bboxSR": 4326,
        "imageSR": 4326,
        "size": f"{width},{height}",
        "format": "tiff",
        "pixelType": "F32",
        "interpolation": "RSP_BilinearInterpolation",
        "f": "image",
    }
    return f"{SERVICE_URL}?{urllib.parse.urlencode(query)}"


def fetch_tile(bounds: dict, width: int, height: int) -> np.ndarray:
    """Elevation in meters for the box as a north-up [height, width] array."""
    import rasterio

    request = urllib.request.Request(export_url(bounds, width, height), headers={"User-Agent": "jarvis"})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_S) as response:
        payload = response.read()
    try:
        with rasterio.MemoryFile(io.BytesIO(payload)) as memory, memory.open() as src:
            data = src.read(1).astype("float32")
    except rasterio.errors.RasterioError as err:
        raise RuntimeError(f"3DEP did not return a GeoTIFF: {payload[:200]!r}") from err
    if data.shape != (height, width):
        raise RuntimeError(f"3DEP returned {data.shape}, expected {(height, width)}")
    return data


def build_dem(bounds: dict, path, cell_deg: float = ARCSEC_DEG / 3, tile_px: int = TILE_PX, fetch=fetch_tile):
    """Write the box to a compressed GeoTIFF tile by tile; the file appears only when complete."""
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.windows import Window

    validate_bounds(bounds)
    cols = math.ceil((bounds["east"] - bounds["west"]) / cell_deg - 1e-6)
    rows = math.ceil((bounds["north"] - bounds["south"]) / cell_deg - 1e-6)
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".part")
    profile = {
        "driver": "GTiff", "height": rows, "width": cols, "count": 1, "dtype": "float32",
        "crs": "EPSG:4326", "transform": from_origin(bounds["west"], bounds["north"], cell_deg, cell_deg),
        "nodata": NODATA, "compress": "deflate", "predictor": 3, "tiled": True,
    }
    try:
        with rasterio.open(partial, "w", **profile) as dst:
            for row in range(0, rows, tile_px):
                for col in range(0, cols, tile_px):
                    height, width = min(tile_px, rows - row), min(tile_px, cols - col)
                    tile = {
                        "north": bounds["north"] - row * cell_deg,
                        "south": bounds["north"] - (row + height) * cell_deg,
                        "west": bounds["west"] + col * cell_deg,
                        "east": bounds["west"] + (col + width) * cell_deg,
                    }
                    data = fetch(tile, width, height)
                    # the service reports missing data as large negative values
                    data = np.where(np.isfinite(data) & (data > -1000), data, NODATA).astype("float32")
                    dst.write(data, 1, window=Window(col, row, width, height))
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)
    return rows, cols


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--region", default="nyc", help="folder name under data/raw/flood")
    parser.add_argument("--bounds", nargs=4, type=float, metavar=("SOUTH", "WEST", "NORTH", "EAST"),
                        help="override the region's default box")
    parser.add_argument("--arcsec", type=float, default=1 / 3,
                        help="cell size in arc-seconds: 1/3 is about 10 m, 1 is about 30 m")
    args = parser.parse_args(argv)

    if args.bounds:
        bounds = dict(zip(("south", "west", "north", "east"), args.bounds))
    elif args.region in REGIONS:
        bounds = REGIONS[args.region]
    else:
        parser.error(f"unknown region {args.region!r}; pass --bounds")
    path = load_settings().raw_dir / "flood" / args.region / "dem.tif"
    rows, cols = build_dem(bounds, path, cell_deg=args.arcsec * ARCSEC_DEG)
    print(f"wrote {rows} x {cols} cells to {path} ({path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
