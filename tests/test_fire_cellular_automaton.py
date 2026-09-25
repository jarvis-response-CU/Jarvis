# References:
#   https://arxiv.org/abs/2509.16018
#   https://docs.pytest.org/en/stable/

import numpy as np
import pytest

from jarvis.simulations.fire.cellular_automaton import (
    Domain,
    burned_fraction,
    simulate,
    spread_rates,
    wind_field,
)

DOMAIN = Domain(width_m=2000, height_m=1000, cell_m=10)
CENTER = (1000, 500)


def steady_wind(speed):
    rows, cols = DOMAIN.shape
    return np.full((rows, cols), float(speed)), np.zeros((rows, cols))


def extent_cells(ignition_time, t, axis_step):
    """How many cells the fire reached from the center along one grid direction."""
    row = int(CENTER[1] // DOMAIN.cell_m)
    col = int(CENTER[0] // DOMAIN.cell_m)
    dx, dy = axis_step
    n = 0
    while ignition_time[row + dy * (n + 1), col + dx * (n + 1)] <= t:
        n += 1
    return n


def test_no_wind_spreads_evenly_in_all_directions():
    rates = spread_rates(*steady_wind(0))
    ignition = simulate(DOMAIN, rates, CENTER, duration_s=10_000)
    axis_steps = [(1, 0), (-1, 0), (0, 1), (0, -1)]
    reach = [extent_cells(ignition, 10_000, step) for step in axis_steps]
    assert len(set(reach)) == 1
    assert reach[0] == pytest.approx(5e-3 * 10_000 / DOMAIN.cell_m, abs=1)


def test_downwind_reach_matches_max_spread_rate():
    rates = spread_rates(*steady_wind(2.5))
    ignition = simulate(DOMAIN, rates, CENTER, duration_s=600)
    expected_cells = (0.1 * 2.5 + 5e-3) * 600 / DOMAIN.cell_m
    downwind = extent_cells(ignition, 600, (1, 0))
    upwind = extent_cells(ignition, 600, (-1, 0))
    assert downwind == pytest.approx(expected_cells, abs=1)
    assert upwind < downwind / 5


def test_burned_fraction_is_bounded_and_grows_over_time():
    rng = np.random.default_rng(0)
    rates = spread_rates(*wind_field(DOMAIN, rng=rng))
    ignition = simulate(DOMAIN, rates, (380, 490), duration_s=3600)
    early = burned_fraction(ignition, 1800)
    late = burned_fraction(ignition, 3600)
    assert early.min() >= 0
    assert late.max() <= 1

    early_burning = (early > 0).sum()
    late_burning = (late > 0).sum()
    assert early_burning > 1
    assert late_burning > early_burning


def test_rejects_ignition_outside_domain():
    rates = spread_rates(*steady_wind(1))
    with pytest.raises(ValueError, match="outside the domain"):
        simulate(DOMAIN, rates, (5000, 500), duration_s=60)
