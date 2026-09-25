# References:
#   https://arxiv.org/abs/2509.16018
#   https://numpy.org/doc/stable/reference/generated/numpy.nonzero.html

"""Run the cellular automaton around a real-world ignition point for the map."""

import math

import numpy as np

from jarvis.simulations.fire.cellular_automaton import Domain, simulate, spread_rates, uniform_wind

METERS_PER_DEGREE_LAT = 111_320
MIN_CELL_M = 30  # LANDFIRE's resolution; no point simulating finer
MAX_CELLS_PER_SIDE = 400  # keeps a run under a few seconds


def run_at_point(lat: float, lng: float, hours: float, wind_speed_mps: float, wind_from_deg: float) -> dict:
    """Simulate a fire lit at (lat, lng) and return burned cells with their ignition minute."""
    if not -90 < lat < 90:
        raise ValueError("lat/lng out of range")
    if not -180 <= lng <= 180:
        raise ValueError("lat/lng out of range")
    if hours <= 0:
        raise ValueError("hours must be positive")

    duration_s = hours * 3600
    # Size the square so the fastest (downwind) spread can't reach the edge,
    # whichever way the wind blows.
    max_rate = 0.1 * wind_speed_mps + 5e-3
    half_m = max_rate * duration_s * 1.15 + 200
    cell_m = max(MIN_CELL_M, 2 * half_m / MAX_CELLS_PER_SIDE)
    side = math.ceil(2 * half_m / cell_m)
    domain = Domain(width_m=side * cell_m, height_m=side * cell_m, cell_m=cell_m)

    wind_x, wind_y = uniform_wind(domain, wind_speed_mps, wind_from_deg)
    rates = spread_rates(wind_x, wind_y)
    center = side * cell_m / 2
    ignition = simulate(domain, rates, (center, center), duration_s)

    # ponytail: flat-earth degrees-per-meter; fine at fire scale (tens of km),
    # use a real projection if runs ever span hundreds of km.
    half_lat = center / METERS_PER_DEGREE_LAT
    half_lng = center / (METERS_PER_DEGREE_LAT * math.cos(math.radians(lat)))
    bounds = {
        "south": lat - half_lat,
        "west": lng - half_lng,
        "north": lat + half_lat,
        "east": lng + half_lng,
    }

    # Row 0 is the south edge. Flat [row, col, minute, ...] keeps the JSON small.
    burned_rows, burned_cols = np.nonzero(np.isfinite(ignition))
    burned_minutes = np.round(ignition[burned_rows, burned_cols] / 60)
    cells = []
    for row, col, minute in zip(burned_rows, burned_cols, burned_minutes):
        cells.extend([int(row), int(col), int(minute)])

    return {
        "bounds": bounds,
        "rows": side,
        "cols": side,
        "cell_m": cell_m,
        "duration_min": round(duration_s / 60),
        "cells": cells,
    }
