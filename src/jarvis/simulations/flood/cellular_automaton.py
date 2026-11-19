# References:
#   Liu et al. (2015), Nat. Hazards Earth Syst. Sci. 15, 381-391, doi:10.5194/nhess-15-381-2015
#   Guidolin et al. (2016), Environ. Model. Softw. 84, 378-394, doi:10.1016/j.envsoft.2016.07.008

"""Weighted cellular-automaton (WCA2D-style) flood model on a square raster, south-up."""

from dataclasses import dataclass, field

import numpy as np

GRAVITY = 9.81
MIN_DT_S = 0.1
MAX_DT_S = 30.0
CELL_STEP_BUDGET = 1e8
NUMERIC_TOLERANCE = 1e-9
LEVEL_TOLERANCE_M = 1e-6
DRY_DEPTH_M = 1e-3
MIN_SLOPE = 1e-3
DEFAULT_ROUGHNESS_N = 0.05


@dataclass
class FloodScenario:
    duration_s: float
    rainfall_mm_hr: float = 0.0
    point_source_row: int | None = None
    point_source_col: int | None = None
    point_inflow_m3_s: float = 0.0
    roughness_n: float | np.ndarray = DEFAULT_ROUGHNESS_N
    infiltration_mm_hr: float | np.ndarray = 0.0
    infiltration_capacity_mm: float | np.ndarray | None = None
    initial_depth_m: float | np.ndarray = 0.0
    output_interval_s: float = 300.0

    def has_source(self) -> bool:
        return (
            self.rainfall_mm_hr > 0
            or (self.point_inflow_m3_s > 0 and self.point_source_row is not None)
            or bool(np.any(np.asarray(self.initial_depth_m) > 0))
        )


@dataclass
class FloodResult:
    depth: np.ndarray
    max_depth: np.ndarray
    mass_balance: dict
    steps: int
    frame_times_s: list = field(default_factory=list)


def neighbor_levels(level, elevation, boundary_type):
    """Water level of the four neighbors: row+1, col+1, row-1, col-1."""
    if boundary_type == "open":
        # ghost cells beyond the edge are dry ground at the edge elevation
        padded = np.pad(elevation, 1, mode="edge")
        padded[1:-1, 1:-1] = level
    else:
        padded = np.pad(level, 1, mode="constant", constant_values=np.inf)
    return np.stack([padded[2:, 1:-1], padded[1:-1, 2:], padded[:-2, 1:-1], padded[1:-1, :-2]])


def transfer_volumes(level, depth, roughness, cell_m, dt, prev_outflow, neighbors):
    """Outgoing volume per direction [4, rows, cols] and each cell's total outflow."""
    area = cell_m**2
    drop = level[None] - neighbors
    downstream = drop > LEVEL_TOLERANCE_M
    volume = np.where(downstream, area * drop, 0.0)
    total = volume.sum(axis=0)
    smallest = np.where(downstream, volume, np.inf).min(axis=0)
    flowing = downstream.any(axis=0) & (depth > DRY_DEPTH_M)
    smallest = np.where(flowing, smallest, 0.0)

    denominator = total + smallest
    weights = np.divide(volume, denominator, out=np.zeros_like(volume), where=denominator > 0)
    weights = weights * flowing[None]

    main = np.argmax(weights, axis=0)[None]
    main_weight = np.take_along_axis(weights, main, axis=0)[0]
    main_drop = np.take_along_axis(drop, main, axis=0)[0]
    slope = np.where(flowing, main_drop, 0.0) / cell_m

    v_critical = np.sqrt(GRAVITY * depth)
    v_manning = depth ** (2 / 3) * np.sqrt(slope) / roughness
    interface_limit = np.minimum(v_critical, v_manning) * depth * dt * cell_m
    with np.errstate(divide="ignore", invalid="ignore"):
        by_interface = np.where(main_weight > 0, interface_limit / main_weight, 0.0)
    cell_total = np.minimum.reduce([depth * area, by_interface, smallest + prev_outflow])
    cell_total = np.where(flowing, cell_total, 0.0)
    return weights * cell_total[None], cell_total


def pick_dt(level, depth, roughness, cell_m, neighbors, remaining_s, min_dt=MIN_DT_S):
    drop = (level[None] - neighbors).max(axis=0)
    slope = np.where(np.isfinite(drop), drop, 0.0) / cell_m
    active = (depth > DRY_DEPTH_M) & (slope > MIN_SLOPE)
    if not active.any():
        return min(MAX_DT_S, remaining_s)
    limit = (cell_m**2 / 4) * (2 * roughness[active] / depth[active] ** (5 / 3)) * np.sqrt(slope[active])
    return float(min(np.clip(limit.min(), min_dt, MAX_DT_S), remaining_s))


def broadcast(value, shape, name):
    array = np.asarray(value, dtype=float)
    if array.ndim and array.shape != shape:
        raise ValueError(f"{name} must be a scalar or match the elevation grid")
    return np.broadcast_to(array, shape).astype(float)


def simulate(elevation, cell_m, scenario: FloodScenario, boundary_type="closed", on_frame=None) -> FloodResult:
    """Run the scenario; on_frame(time_s, depth) is called at t=0 and every output interval."""
    if boundary_type not in ("closed", "open"):
        raise ValueError("boundary_type must be 'closed' or 'open'")
    if scenario.duration_s <= 0 or scenario.output_interval_s <= 0:
        raise ValueError("duration and output interval must be positive")
    elevation = np.asarray(elevation, dtype=float)
    shape = elevation.shape
    area = cell_m**2
    roughness = broadcast(scenario.roughness_n, shape, "roughness_n")
    infiltration_rate = broadcast(scenario.infiltration_mm_hr, shape, "infiltration_mm_hr") / 3.6e6
    rain_rate = scenario.rainfall_mm_hr / 3.6e6
    capacity = None
    if scenario.infiltration_capacity_mm is not None:
        capacity = broadcast(scenario.infiltration_capacity_mm, shape, "infiltration_capacity_mm") / 1000.0
    cumulative_infiltration = np.zeros(shape)
    # bound runtime on big grids: deep water would otherwise drive the step toward the minimum
    min_dt = min(MAX_DT_S, max(MIN_DT_S, scenario.duration_s * elevation.size / CELL_STEP_BUDGET))

    depth = broadcast(scenario.initial_depth_m, shape, "initial_depth_m").copy()
    max_depth = depth.copy()
    prev_outflow = np.zeros(shape)
    point = (scenario.point_source_row, scenario.point_source_col)
    has_point = scenario.point_inflow_m3_s > 0 and point[0] is not None

    totals = {"rainfall_m3": 0.0, "point_inflow_m3": 0.0, "infiltration_m3": 0.0, "boundary_outflow_m3": 0.0}
    initial_m3 = float(depth.sum() * area)
    frame_times = [0.0]
    if on_frame:
        on_frame(0.0, depth)

    t = 0.0
    steps = 0
    next_output = min(scenario.output_interval_s, scenario.duration_s)
    while t < scenario.duration_s - 1e-9:
        level = elevation + depth
        neighbors = neighbor_levels(level, elevation, boundary_type)
        dt = pick_dt(level, depth, roughness, cell_m, neighbors, next_output - t, min_dt)
        out, prev_outflow = transfer_volumes(level, depth, roughness, cell_m, dt, prev_outflow, neighbors)

        # apply all transfers at once from the old state
        incoming = np.zeros(shape)
        incoming[1:, :] += out[0][:-1, :]
        incoming[:, 1:] += out[1][:, :-1]
        incoming[:-1, :] += out[2][1:, :]
        incoming[:, :-1] += out[3][:, 1:]
        totals["boundary_outflow_m3"] += float(
            out[0][-1, :].sum() + out[1][:, -1].sum() + out[2][0, :].sum() + out[3][:, 0].sum()
        )

        depth = depth + (incoming - out.sum(axis=0)) / area + rain_rate * dt
        totals["rainfall_m3"] += rain_rate * dt * area * depth.size
        if has_point:
            depth[point] += scenario.point_inflow_m3_s * dt / area
            totals["point_inflow_m3"] += scenario.point_inflow_m3_s * dt

        infiltrated = np.minimum(infiltration_rate * dt, depth)
        if capacity is not None:
            infiltrated = np.minimum(infiltrated, np.maximum(capacity - cumulative_infiltration, 0.0))
        cumulative_infiltration += infiltrated
        depth = depth - infiltrated
        totals["infiltration_m3"] += float(infiltrated.sum() * area)

        assert depth.min() >= -NUMERIC_TOLERANCE
        depth = np.maximum(depth, 0.0)
        np.maximum(max_depth, depth, out=max_depth)
        t += dt
        steps += 1

        if t >= next_output - 1e-9:
            frame_times.append(next_output)
            if on_frame:
                on_frame(next_output, depth)
            next_output = min(next_output + scenario.output_interval_s, scenario.duration_s)

    final_m3 = float(depth.sum() * area)
    supplied = initial_m3 + totals["rainfall_m3"] + totals["point_inflow_m3"]
    expected = supplied - totals["infiltration_m3"] - totals["boundary_outflow_m3"]
    mass_balance = {
        "initial_m3": initial_m3,
        **totals,
        "final_m3": final_m3,
        "relative_error": abs(final_m3 - expected) / max(supplied, 1e-12),
    }
    return FloodResult(depth, max_depth, mass_balance, steps, frame_times)
