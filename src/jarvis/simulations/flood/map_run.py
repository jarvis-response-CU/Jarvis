"""Run the flood automaton over a local DEM and return a north-up georeferenced result."""

import numpy as np

from jarvis.simulations.common.grid import latlon_to_row_col
from jarvis.simulations.common.raster import raster_result, sparse_cells
from jarvis.simulations.flood.cellular_automaton import FloodScenario, simulate
from jarvis.simulations.flood.terrain import load_dem

VALUE_SCALE = 0.001
MIN_DEPTH_M = 0.001
MAX_FRAMES = 120
MODEL_ID = "WCA2D-derived"


def run_flood(bounds: dict, hours: float, rainfall_mm_hr: float = 0.0, source_lat: float | None = None,
              source_lng: float | None = None, point_inflow_m3_s: float = 0.0,
              roughness_n: float = 0.05, infiltration_mm_hr: float = 0.0,
              boundary_type: str = "closed", output_interval_min: float = 5.0, terrain=None) -> dict:
    """Simulate rain on the grid and/or a point inflow, with depth frames and the maximum-depth raster."""
    if hours <= 0:
        raise ValueError("hours must be positive")
    if rainfall_mm_hr < 0 or point_inflow_m3_s < 0 or infiltration_mm_hr < 0 or roughness_n <= 0:
        raise ValueError("rainfall, inflow and infiltration must be non-negative and roughness positive")
    if rainfall_mm_hr <= 0 and point_inflow_m3_s <= 0:
        raise ValueError("set rainfall or a point inflow")
    if point_inflow_m3_s > 0 and (source_lat is None or source_lng is None):
        raise ValueError("a point inflow needs source_lat and source_lng")

    terrain = terrain or load_dem(bounds)
    grid = terrain.grid
    duration_s = hours * 3600
    interval_s = max(output_interval_min * 60, duration_s / MAX_FRAMES)

    source_row = source_col = None
    if source_lat is not None and source_lng is not None:
        row, col = latlon_to_row_col(grid, source_lat, source_lng)
        if not (0 <= row < grid.rows and 0 <= col < grid.cols):
            raise ValueError("the source is outside the domain")
        source_row, source_col = int(row), int(col)

    scenario = FloodScenario(
        duration_s=duration_s,
        rainfall_mm_hr=rainfall_mm_hr,
        point_source_row=source_row,
        point_source_col=source_col,
        point_inflow_m3_s=point_inflow_m3_s,
        roughness_n=roughness_n,
        infiltration_mm_hr=infiltration_mm_hr,
        output_interval_s=interval_s,
    )
    frames = []
    result = simulate(
        terrain.elevation, grid.cell_m, scenario, boundary_type,
        on_frame=lambda t, depth: frames.append(sparse_cells(depth, VALUE_SCALE, MIN_DEPTH_M)),
    )

    return raster_result(
        "flood",
        {
            "id": MODEL_ID,
            "version": "1",
            "assumptions": [
                "2-D raster cellular automaton",
                "diffusive-like approximation",
                "momentum not fully resolved",
                "zero infiltration unless specified",
            ],
        },
        grid, "water_depth", "m", VALUE_SCALE,
        duration_min=round(duration_s / 60),
        frame_minutes=[round(t / 60, 2) for t in result.frame_times_s],
        frames=frames,
        max_cells=sparse_cells(result.max_depth, VALUE_SCALE, MIN_DEPTH_M),
        source={
            "lat": source_lat, "lng": source_lng, "mode": "point_inflow" if point_inflow_m3_s > 0 else "rain",
        },
        inputs={
            "rainfall_mm_hr": rainfall_mm_hr,
            "point_inflow_m3_s": point_inflow_m3_s,
            "roughness_n": roughness_n,
            "infiltration_mm_hr": infiltration_mm_hr,
            "boundary_type": boundary_type,
        },
        max_depth_m=float(np.max(result.max_depth)),
        mass_balance=result.mass_balance,
        steps=result.steps,
    )
