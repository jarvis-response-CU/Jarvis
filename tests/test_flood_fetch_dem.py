import numpy as np
import pytest

from jarvis.simulations.flood import fetch_dem
from jarvis.simulations.flood.terrain import load_dem

BOUNDS = {"south": 40.00, "west": -74.00, "north": 40.01, "east": -73.99}
CELL = 0.001


def fake_fetch(bounds, width, height):
    lat = bounds["north"] - (np.arange(height) + 0.5) * (bounds["north"] - bounds["south"]) / height
    data = np.repeat(((lat - 40.0) * 1000)[:, None], width, axis=1).astype("float32")
    data[0, 0] = -3.4e38
    return data


def test_url_asks_for_the_box_as_float_geotiff():
    url = fetch_dem.export_url(BOUNDS, 10, 10)
    assert "bbox=-74.0%2C40.0%2C-73.99%2C40.01" in url and "pixelType=F32" in url and "size=10%2C10" in url


def test_default_region_matches_the_map_region():
    nyc = fetch_dem.REGIONS["nyc"]
    assert (nyc["south"], nyc["west"], nyc["north"], nyc["east"]) == (40.4774, -74.2591, 40.9176, -73.7004)


def test_tiled_download_builds_one_dem_the_loader_can_read(tmp_path, monkeypatch):
    import rasterio

    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path))
    path = tmp_path / "raw" / "flood" / "nyc" / "dem.tif"
    rows, cols = fetch_dem.build_dem(BOUNDS, path, cell_deg=CELL, tile_px=4, fetch=fake_fetch)
    assert (rows, cols) == (10, 10)
    with rasterio.open(path) as src:
        assert src.bounds.left == pytest.approx(-74.0) and src.bounds.top == pytest.approx(40.01)
        data = src.read(1)
    assert data[0, 0] == fetch_dem.NODATA and data[0, 5] > data[-1, 5]
    terrain = load_dem(BOUNDS)
    assert terrain.elevation[0].mean() < terrain.elevation[-1].mean()


def test_failed_download_leaves_no_file(tmp_path):
    def broken(bounds, width, height):
        raise RuntimeError("service down")

    path = tmp_path / "dem.tif"
    with pytest.raises(RuntimeError):
        fetch_dem.build_dem(BOUNDS, path, cell_deg=CELL, tile_px=4, fetch=broken)
    assert not path.exists() and not list(tmp_path.glob("*.part"))


def test_main_rejects_unknown_region_without_bounds(capsys):
    with pytest.raises(SystemExit):
        fetch_dem.main(["--region", "atlantis"])
