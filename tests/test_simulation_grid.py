import numpy as np
import pytest

from jarvis.simulations.common.grid import (
    GridSpec, cell_centers, domain_size_m, encode_sparse, latlon_to_row_col, row_col_to_latlon, validate_bounds,
)
from jarvis.simulations.common.raster import quantize, raster_result, sparse_cells

GRID = GridSpec(40.0, -105.0, 40.002, -104.996, 2, 4, 30)


def test_row_zero_is_south_and_col_zero_is_west():
    row, col = latlon_to_row_col(GRID, [40.0001, 40.0019], [-104.9999, -104.9961])
    assert row.tolist() == [0, 1]
    assert col.tolist() == [0, 3]


def test_cell_centers_round_trip():
    lat, lon = cell_centers(GRID)
    assert lat.shape == (2, 4)
    row, col = latlon_to_row_col(GRID, lat, lon)
    assert (row == np.arange(2)[:, None]).all()
    assert (col == np.arange(4)[None, :]).all()
    assert row_col_to_latlon(GRID, 0, 0)[0] == pytest.approx(40.0005)


def test_points_outside_get_out_of_range_indices():
    row, col = latlon_to_row_col(GRID, [39.0, 41.0], [-106.0, -104.0])
    assert row.tolist()[0] < 0 and row.tolist()[1] >= GRID.rows
    assert col.tolist()[0] < 0 and col.tolist()[1] >= GRID.cols


def test_domain_size_uses_a_real_projection():
    width, height = domain_size_m({"south": 40.0, "west": -105.0, "north": 40.1, "east": -104.9})
    assert height == pytest.approx(11_100, rel=0.01)
    assert width == pytest.approx(11_100 * np.cos(np.radians(40.05)), rel=0.01)


def test_validate_bounds_rejects_flipped_box():
    with pytest.raises(ValueError):
        validate_bounds({"south": 41, "west": 0, "north": 40, "east": 1})


def test_encode_sparse_is_flat():
    assert encode_sparse([0, 1], [2, 3], [4, 5]) == [0, 2, 4, 1, 3, 5]


def test_sparse_cells_omit_values_below_threshold():
    array = np.array([[0.0, 0.0005], [0.0012, 0.5]])
    assert sparse_cells(array, 0.001, 0.001) == [1, 0, 1, 1, 1, 500]
    assert quantize(0.0126, 0.001) == 13


def test_raster_result_has_null_exposure_and_damage():
    result = raster_result("flood", {"id": "x"}, GRID, "water_depth", "m", 0.001, frames=[])
    assert result["exposure"] is None and result["damage"] is None
    assert result["bounds"]["south"] == 40.0 and result["value_scale"] == 0.001
