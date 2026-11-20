"""Quantized sparse rasters: the shared shape of every hazard result."""

import numpy as np

from jarvis.simulations.common.grid import GridSpec, encode_sparse


def quantize(values, value_scale: float):
    return np.round(np.asarray(values, dtype=float) / value_scale).astype(int)


def sparse_cells(array, value_scale: float, min_value: float = 0.0) -> list:
    """Cells of a south-up array at or above min_value, as flat [row, col, quantized, ...]."""
    array = np.asarray(array)
    keep = np.nan_to_num(array, nan=-np.inf) >= max(min_value, np.finfo(float).tiny)
    rows, cols = np.nonzero(keep)
    return encode_sparse(rows, cols, quantize(array[rows, cols], value_scale))


def raster_result(hazard: str, model: dict, grid: GridSpec, value_name: str, value_unit: str,
                  value_scale: float, **extra) -> dict:
    return {
        "hazard": hazard,
        "model": model,
        "bounds": grid.bounds,
        "rows": grid.rows,
        "cols": grid.cols,
        "cell_m": grid.cell_m,
        "value_name": value_name,
        "value_unit": value_unit,
        "value_scale": value_scale,
        **extra,
        "exposure": None,
        "damage": None,
    }
