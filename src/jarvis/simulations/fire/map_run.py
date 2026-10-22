# References:
#   https://arxiv.org/abs/2509.16018
#   https://numpy.org/doc/stable/reference/generated/numpy.nonzero.html

"""Run the cellular automaton around a real-world ignition point for the map."""

import math

import numpy as np

from jarvis.simulations.fire.cellular_automaton import (
    DIRECTIONS,
    Domain,
    simulate,
    spread_rates,
    uniform_wind,
)

METERS_PER_DEGREE_LAT = 111_320
MIN_CELL_M = 30  # LANDFIRE's resolution; no point simulating finer
MAX_CELLS = 250_000  # keeps a run to about ten seconds
EDGE_MARGIN_M = 200


def spread_extents(wind_speed_mps: float, duration_s: float) -> tuple[float, float, float]:
    """How far a fire can get downwind, upwind and to either side, in meters."""
    rates = spread_rates(np.array([[wind_speed_mps]]), np.array([[0.0]]))[:, 0, 0]
    along_wind = rates * np.cos(DIRECTIONS) * duration_s
    across_wind = rates * np.abs(np.sin(DIRECTIONS)) * duration_s
    return along_wind.max(), -along_wind.min(), across_wind.max()


def run_at_point(lat: float, lng: float, hours: float, wind_speed_mps: float, wind_from_deg: float) -> dict:
    """Simulate a fire lit at (lat, lng) and return burned cells with their ignition minute."""
    if not -90 < lat < 90:
        raise ValueError("lat/lng out of range")
    if not -180 <= lng <= 180:
        raise ValueError("lat/lng out of range")
    if hours <= 0:
        raise ValueError("hours must be positive")

    duration_s = hours * 3600
    # The model only spreads in 8 directions, and a narrow wind-driven fire
    # slips between them when the wind is off-axis. So simulate on a grid
    # turned to put the wind along its x axis, then turn the result back.
    downwind, upwind, sideways = spread_extents(wind_speed_mps, duration_s)
    length_m = (downwind + upwind) * 1.15 + 2 * EDGE_MARGIN_M
    width_m = 2 * sideways * 1.15 + 2 * EDGE_MARGIN_M
    cell_m = max(MIN_CELL_M, math.sqrt(length_m * width_m / MAX_CELLS))
    cols = math.ceil(length_m / cell_m)
    rows = math.ceil(width_m / cell_m)
    domain = Domain(width_m=cols * cell_m, height_m=rows * cell_m, cell_m=cell_m)

    wind_x, wind_y = uniform_wind(domain, wind_speed_mps, from_deg=270)
    rates = spread_rates(wind_x, wind_y)
    start_x = upwind * 1.15 + EDGE_MARGIN_M
    start_y = rows * cell_m / 2
    ignition = simulate(domain, rates, (start_x, start_y), duration_s)

    # Unit vectors, in (east, north), for the way the wind blows and for its left.
    toward = math.radians((wind_from_deg + 180) % 360)
    along = (math.sin(toward), math.cos(toward))
    left = (-math.cos(toward), math.sin(toward))

    # Meters east and north of the ignition point for every burned cell center.
    burned_rows, burned_cols = np.nonzero(np.isfinite(ignition))
    u = (burned_cols + 0.5) * cell_m - start_x
    v = (burned_rows + 0.5) * cell_m - start_y
    east = u * along[0] + v * left[0]
    north = u * along[1] + v * left[1]

    # Lay a north-up grid of the same cells over the burn. Looking each of its
    # cells up in the turned grid leaves no gaps, which placing the turned
    # cells straight onto it would.
    west_m = math.floor(east.min() / cell_m) * cell_m
    south_m = math.floor(north.min() / cell_m) * cell_m
    out_cols = math.ceil((east.max() - west_m) / cell_m) + 1
    out_rows = math.ceil((north.max() - south_m) / cell_m) + 1
    grid_east = west_m + (np.arange(out_cols) + 0.5) * cell_m
    grid_north = south_m + (np.arange(out_rows) + 0.5) * cell_m
    grid_east, grid_north = np.meshgrid(grid_east, grid_north)
    sim_col = np.floor((grid_east * along[0] + grid_north * along[1] + start_x) / cell_m).astype(int)
    sim_row = np.floor((grid_east * left[0] + grid_north * left[1] + start_y) / cell_m).astype(int)
    in_domain = (sim_col >= 0) & (sim_col < cols) & (sim_row >= 0) & (sim_row < rows)
    ignition_time = np.full((out_rows, out_cols), np.inf)
    ignition_time[in_domain] = ignition[sim_row[in_domain], sim_col[in_domain]]

    # ponytail: flat-earth degrees-per-meter; fine at fire scale (tens of km),
    # use a real projection if runs ever span hundreds of km.
    meters_per_degree_lng = METERS_PER_DEGREE_LAT * math.cos(math.radians(lat))
    bounds = {
        "south": lat + south_m / METERS_PER_DEGREE_LAT,
        "west": lng + west_m / meters_per_degree_lng,
        "north": lat + (south_m + out_rows * cell_m) / METERS_PER_DEGREE_LAT,
        "east": lng + (west_m + out_cols * cell_m) / meters_per_degree_lng,
    }

    # Row 0 is the south edge. Flat [row, col, minute, ...] keeps the JSON small.
    burned_rows, burned_cols = np.nonzero(np.isfinite(ignition_time))
    burned_minutes = np.round(ignition_time[burned_rows, burned_cols] / 60)
    cells = []
    for row, col, minute in zip(burned_rows, burned_cols, burned_minutes):
        cells.extend([int(row), int(col), int(minute)])

    return {
        "bounds": bounds,
        "rows": out_rows,
        "cols": out_cols,
        "cell_m": cell_m,
        "duration_min": round(duration_s / 60),
        "cells": cells,
    }
