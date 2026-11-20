import numpy as np
import pytest

from jarvis.simulations.flood.cellular_automaton import (
    FloodScenario, neighbor_levels, simulate, transfer_volumes,
)

CELL = 10.0


def run(elevation, **kwargs):
    boundary = kwargs.pop("boundary_type", "closed")
    scenario = FloodScenario(**{"duration_s": 1800, "output_interval_s": 600, **kwargs})
    return simulate(elevation, CELL, scenario, boundary)


def slope(rows=20, cols=20, grade=0.02):
    return np.fromfunction(lambda r, c: r * grade, (rows, cols))


def center_of_mass_row(depth):
    return (depth.sum(axis=1) * np.arange(depth.shape[0])).sum() / depth.sum()


def test_zero_input_gives_zero_water():
    result = run(slope(), rainfall_mm_hr=0.0)
    assert result.depth.max() == 0 and result.max_depth.max() == 0
    assert result.mass_balance["final_m3"] == 0


def test_closed_boundary_conserves_mass():
    result = run(slope(), rainfall_mm_hr=30, point_source_row=10, point_source_col=10, point_inflow_m3_s=2.0)
    balance = result.mass_balance
    assert balance["boundary_outflow_m3"] == 0
    expected = balance["initial_m3"] + balance["rainfall_m3"] + balance["point_inflow_m3"]
    assert balance["final_m3"] == pytest.approx(expected, rel=1e-9)
    assert balance["relative_error"] < 1e-9


def test_rainfall_volume_matches_rate():
    result = run(slope(), rainfall_mm_hr=36)
    assert result.mass_balance["rainfall_m3"] == pytest.approx(0.036 / 3600 * 1800 * 400 * CELL**2, rel=1e-9)


def test_open_boundary_conservation():
    result = run(slope(), rainfall_mm_hr=30, infiltration_mm_hr=5, boundary_type="open")
    balance = result.mass_balance
    assert balance["boundary_outflow_m3"] > 0 and balance["infiltration_m3"] > 0
    inflow = balance["initial_m3"] + balance["rainfall_m3"] + balance["point_inflow_m3"]
    assert inflow == pytest.approx(
        balance["final_m3"] + balance["infiltration_m3"] + balance["boundary_outflow_m3"], rel=1e-9
    )


def test_infiltration_capacity_limits_losses():
    result = run(np.zeros((6, 6)), rainfall_mm_hr=20, infiltration_mm_hr=50, infiltration_capacity_mm=2.0)
    assert result.mass_balance["infiltration_m3"] == pytest.approx(0.002 * 36 * CELL**2, rel=1e-6)


def test_depth_is_never_negative():
    rng = np.random.default_rng(0)
    elevation = rng.random((25, 25)) * 2
    result = run(elevation, rainfall_mm_hr=60, initial_depth_m=0.5, boundary_type="open")
    assert result.depth.min() >= 0 and result.max_depth.min() >= 0


def test_water_moves_downhill():
    elevation = slope(grade=0.05)
    initial = np.zeros_like(elevation)
    initial[10, 5:15] = 0.5
    result = run(elevation, initial_depth_m=initial)
    assert center_of_mass_row(result.depth) < center_of_mass_row(initial)
    assert result.mass_balance["relative_error"] < 1e-9


def test_symmetric_bowl_stays_symmetric():
    n = 21
    y, x = np.mgrid[:n, :n] - n // 2
    bowl = 0.05 * np.hypot(x, y)
    result = run(bowl, point_source_row=n // 2, point_source_col=n // 2, point_inflow_m3_s=1.0)
    depth = result.depth
    assert np.allclose(depth, depth[::-1, :], atol=1e-9)
    assert np.allclose(depth, depth[:, ::-1], atol=1e-9)
    assert np.allclose(depth, depth.T, atol=1e-9)


def test_closed_depression_fills_before_spilling():
    elevation = np.full((15, 15), 1.0)
    elevation[5:10, 5:10] = 0.0
    basin = np.zeros_like(elevation)
    basin[5:10, 5:10] = 0.5
    held = run(elevation, initial_depth_m=basin).depth
    assert held[:5, :].max() == 0 and held[10:, :].max() == 0
    assert held[5:10, 5:10].sum() == pytest.approx(basin.sum(), rel=1e-9)

    basin[5:10, 5:10] = 1.4
    spilled = run(elevation, initial_depth_m=basin).depth
    assert spilled[:5, :].sum() + spilled[10:, :].sum() > 0


def test_frames_are_emitted_at_output_interval():
    frames = []
    simulate(
        slope(8, 8), CELL, FloodScenario(duration_s=900, rainfall_mm_hr=20, output_interval_s=300),
        on_frame=lambda t, depth: frames.append((t, depth.copy())),
    )
    assert [t for t, _ in frames] == [0.0, 300.0, 600.0, 900.0]
    assert frames[0][1].max() == 0 and frames[-1][1].max() > 0


def test_resolution_gives_consistent_volume_and_extent():
    def event(rows, cell):
        elevation = np.fromfunction(lambda r, c: 0.02 * r * cell, (rows, rows))
        scenario = FloodScenario(duration_s=1800, rainfall_mm_hr=40, output_interval_s=1800)
        result = simulate(elevation, cell, scenario)
        wet = (result.depth > 0.01).mean()
        return result.depth.mean(), wet

    coarse = event(10, 20.0)
    fine = event(20, 10.0)
    assert coarse[0] == pytest.approx(fine[0], rel=0.01)
    assert abs(coarse[1] - fine[1]) < 0.15


def test_published_one_step_transfer_rule():
    # center cell with two lower neighbors: weights follow the wca2d volume rule
    level = np.array([[1.0, 1.0, 1.0], [1.0, 1.2, 0.8], [1.0, 1.0, 1.0]])
    elevation = np.zeros((3, 3))
    depth = level - elevation
    neighbors = neighbor_levels(level, elevation, "closed")
    # [row+1, col+1, row-1, col-1] of the center cell
    assert neighbors[:, 1, 1].tolist() == [1.0, 0.8, 1.0, 1.0]
    out, _ = transfer_volumes(
        level, depth, np.full((3, 3), 0.05), CELL, 60.0, np.zeros((3, 3)), neighbors
    )
    area = CELL**2
    drops = np.array([0.2, 0.4, 0.2, 0.2])
    volumes = area * drops
    weights = volumes / (volumes.sum() + volumes.min())
    # the interface limit is large here, so total outflow is volume_min plus nothing carried over
    expected_total = min(1.2 * area, volumes.min())
    assert out[:, 1, 1] == pytest.approx(weights * expected_total, rel=1e-9)
    assert out[:, 1, 1].sum() < volumes.min()


def test_invalid_inputs():
    with pytest.raises(ValueError):
        simulate(np.zeros((3, 3)), CELL, FloodScenario(duration_s=0))
    with pytest.raises(ValueError):
        simulate(np.zeros((3, 3)), CELL, FloodScenario(duration_s=10), boundary_type="leaky")
    with pytest.raises(ValueError):
        simulate(np.zeros((3, 3)), CELL, FloodScenario(duration_s=10, roughness_n=np.ones((2, 2))))


def test_has_source():
    assert not FloodScenario(duration_s=1).has_source()
    assert FloodScenario(duration_s=1, rainfall_mm_hr=1).has_source()
    assert FloodScenario(duration_s=1, initial_depth_m=0.1).has_source()
