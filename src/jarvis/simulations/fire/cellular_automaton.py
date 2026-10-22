# References:
#   https://arxiv.org/abs/2509.16018
#   https://doi.org/10.2737/PSW-RP-259
#   https://doi.org/10.2737/INT-RP-438
#   https://doi.org/10.1007/s13595-019-0829-8
#   https://numpy.org/doc/stable/reference/generated/numpy.pad.html

"""Wind-driven cellular-automaton fire spread.

Implements the CA from Ebby & Farazmand, "Discrete Empirical Interpolation
Method with Upper and Lower Bound Constraints", arXiv:2509.16018v2 (2026),
Section 5.3 and Appendix C (itself based on HFire, Peterson et al. 2009).
Paper: docs/papers/2509.16018v2.pdf (CC BY-NC-ND 4.0).

Spread depends only on wind: flat terrain, uniform fuel, no moisture, no
spotting. It's the paper's testbed, not an operational spread predictor.
"""

from dataclasses import dataclass

import numpy as np

# The 8 spread directions (paper: theta in {0, pi/4, ..., 7pi/4}), as grid
# steps (dx, dy) with +x east and +y north.
DIRECTIONS = np.arange(8) * np.pi / 4
STEPS = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
STEP_LENGTH_FACTOR = np.array([np.hypot(dx, dy) for dx, dy in STEPS])
# Rothermel's ratio keeps growing with wind, which draws a needle at 25 m/s.
# Starting value, to be tuned against the Marshall Fire's perimeter.
MAX_LENGTH_TO_WIDTH = 8


@dataclass(frozen=True)
class Domain:
    width_m: float = 2000.0
    height_m: float = 1000.0
    cell_m: float = 10.0

    @property
    def shape(self) -> tuple[int, int]:
        return round(self.height_m / self.cell_m), round(self.width_m / self.cell_m)


def wind_field(domain: Domain, base_speed: float = 2.5, perturbation: float = 0.1,
               frequency: int = 5, rng: np.random.Generator | None = None):
    """Randomized incompressible wind (eq. C.1). Returns (vx, vy) in m/s per cell."""
    if base_speed < 0 or perturbation < 0 or frequency <= 0:
        raise ValueError("base_speed and perturbation must be >= 0, frequency > 0")
    rng = rng or np.random.default_rng()
    a, b = rng.standard_normal(2)
    phase_x, phase_y = rng.uniform(0, 2 * np.pi, 2)

    rows, cols = domain.shape
    x = (np.arange(cols) + 0.5) * domain.cell_m
    y = (np.arange(rows) + 0.5) * domain.cell_m
    xx, yy = np.meshgrid(x, y)

    # The paper's C.1 matches v = (dpsi/dy, -dpsi/dx) from eq. 35: the two
    # minus signs in -d/dx of cos() cancel, so the sin term is positive.
    x_wave = 2 * np.pi * frequency * xx / domain.width_m + phase_x
    y_wave = 2 * np.pi * frequency * yy / domain.height_m + phase_y
    vx = base_speed + perturbation * 2 * np.pi * b * np.cos(y_wave)
    vy = perturbation * 2 * np.pi * a * np.sin(x_wave)
    return vx, vy


def uniform_wind(domain: Domain, speed_mps: float, from_deg: float):
    """Steady wind everywhere. from_deg is the meteorological direction the
    wind blows FROM (0 = north, 90 = east), as NWS reports it."""
    if speed_mps < 0:
        raise ValueError("speed_mps must be >= 0")
    toward = np.radians(90 - (from_deg + 180))  # compass bearing -> math angle
    rows, cols = domain.shape
    vx = np.full((rows, cols), speed_mps * np.cos(toward))
    vy = np.full((rows, cols), speed_mps * np.sin(toward))
    return vx, vy


def spread_rates(vx: np.ndarray, vy: np.ndarray) -> np.ndarray:
    """Directional spread rate R(theta) in m/s, shape (8, rows, cols) (eqs. C.2–C.4)."""
    speed = np.hypot(vx, vy)
    wind_direction = np.arctan2(vy, vx)

    max_rate = 0.1 * speed + 5e-3  # "10% rule": spread ~ a tenth of wind speed
    # Rothermel (1991) length-to-width ratio 1 + 0.25*U with U in mi/h;
    # 0.5592 = 0.25 * 2.237 is the same rule with U in m/s.
    length_to_width = np.minimum(1 + 0.5592 * speed, MAX_LENGTH_TO_WIDTH)
    eccentricity = np.sqrt(1 - (1 / length_to_width) ** 2)

    angle = DIRECTIONS[:, None, None] - wind_direction[None]
    return max_rate * (1 - eccentricity) / (1 - eccentricity * np.cos(angle))


def simulate(domain: Domain, rates: np.ndarray, ignition_xy: tuple[float, float],
             duration_s: float) -> np.ndarray:
    """Run the CA and return each cell's ignition time in seconds (inf = never burned)."""
    rows, cols = domain.shape
    if rates.shape != (8, rows, cols):
        raise ValueError(f"rates must have shape (8, {rows}, {cols}), got {rates.shape}")
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")
    x, y = ignition_xy
    col = int(x // domain.cell_m)
    row = int(y // domain.cell_m)
    if not (0 <= row < rows and 0 <= col < cols):
        raise ValueError(f"ignition point {ignition_xy} is outside the domain")

    # eqs. C.5–C.6: no cell can be crossed in one step, and steps divide T evenly.
    max_dt = domain.cell_m / rates.max()
    n_steps = int(np.ceil(duration_s / max_dt))
    dt = duration_s / n_steps

    ignition_time = np.full((rows, cols), np.inf)
    ignition_time[row, col] = 0.0
    burned_down = np.zeros((rows, cols), dtype=bool)
    distance = np.zeros((8, rows, cols))
    thresholds = STEP_LENGTH_FACTOR * domain.cell_m

    for step in range(1, n_steps + 1):
        t = step * dt
        burning = np.isfinite(ignition_time) & ~burned_down
        distance[:, burning] += rates[:, burning] * dt

        newly_ignited = np.zeros((rows, cols), dtype=bool)
        spillover = np.zeros((8, rows, cols))
        for k, (dx, dy) in enumerate(STEPS):
            reached = burning & (distance[k] >= thresholds[k])
            src, dst = _shifted_slices(dx, dy, rows, cols)
            targets = reached[src] & ~np.isfinite(ignition_time[dst])
            newly_ignited[dst] |= targets
            # The paper carries the distance past the neighbor's center into
            # the new cell; we give it to that cell's same-direction counter.
            excess = np.where(targets, distance[k][src] - thresholds[k], 0.0)
            spillover[k][dst] = np.maximum(spillover[k][dst], excess)

        ignition_time[newly_ignited] = t
        distance[:, newly_ignited] = spillover[:, newly_ignited]
        surrounded = _all_neighbors_ignited(np.isfinite(ignition_time))
        burned_down |= burning & surrounded

    return ignition_time


def burned_fraction(ignition_time: np.ndarray, t: float) -> np.ndarray:
    """Share of [0, t] each cell has been burning, in [0, 1] (eq. 33)."""
    if t <= 0:
        raise ValueError("t must be positive")
    return np.where(ignition_time <= t, (t - ignition_time) / t, 0.0)


def _shifted_slices(dx: int, dy: int, rows: int, cols: int):
    """Index pairs so that array[src] and array[dst] line up source -> neighbor."""
    def axis(d, n):
        if d >= 0:
            return slice(0, n - d), slice(d, n)
        return slice(-d, n), slice(0, n + d)

    src_c, dst_c = axis(dx, cols)
    src_r, dst_r = axis(dy, rows)
    return (src_r, src_c), (dst_r, dst_c)


def _all_neighbors_ignited(ignited: np.ndarray) -> np.ndarray:
    # Off-grid neighbors count as ignited so edge cells can still burn down.
    padded = np.pad(ignited, 1, constant_values=True)
    rows, cols = ignited.shape
    result = np.ones_like(ignited)
    for dx, dy in STEPS:
        result &= padded[1 + dy:1 + dy + rows, 1 + dx:1 + dx + cols]
    return result
