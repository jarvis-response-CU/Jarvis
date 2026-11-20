"""Median PGA field around a real-world epicenter, on a north-up georeferenced grid."""

import math

import numpy as np

from jarvis.simulations.common.grid import (
    GridSpec, cell_centers, domain_size_m, encode_sparse, to_local_xy, utm_transformer, validate_bounds,
)
from jarvis.simulations.common.raster import quantize, raster_result
from jarvis.simulations.earthquake import gmpe
from jarvis.simulations.earthquake.site_conditions import VS30_DEFAULT, load_vs30

MIN_CELL_M = 100.0
MAX_CELLS = 40_000
MAX_DOMAIN_KM = 600.0
DISPLAY_PGA_G = 0.05
METERS_PER_DEGREE = 111_320
VALUE_SCALE = 0.001
SIGMA_SCALE = 0.001


def segment_distance_m(x, y, vertices):
    """Distance from each point to the nearest segment of a polyline given as (x, y) rows."""
    best = np.full(x.shape, np.inf)
    for (x1, y1), (x2, y2) in zip(vertices[:-1], vertices[1:]):
        dx, dy = x2 - x1, y2 - y1
        length2 = dx * dx + dy * dy
        t = np.zeros_like(x) if length2 == 0 else np.clip(((x - x1) * dx + (y - y1) * dy) / length2, 0, 1)
        best = np.minimum(best, np.hypot(x - (x1 + t * dx), y - (y1 + t * dy)))
    return best


def inside_polygon(x, y, vertices):
    result = np.zeros(x.shape, dtype=bool)
    for (x1, y1), (x2, y2) in zip(vertices, np.roll(vertices, -1, axis=0)):
        crosses = (y1 > y) != (y2 > y)
        with np.errstate(divide="ignore", invalid="ignore"):
            crossing_x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
        result ^= crosses & (x < crossing_x)
    return result


def joyner_boore_km(lat, lon, source_lat, source_lng, rupture=None, rupture_kind="line"):
    """(R_JB in km, distance model label). Without rupture geometry this is the epicentral proxy."""
    transformer = utm_transformer(source_lat, source_lng)
    x, y = to_local_xy(transformer, lat, lon)
    if rupture is None:
        sx, sy = to_local_xy(transformer, source_lat, source_lng)
        return np.hypot(x - sx, y - sy) / 1000.0, "epicentral_proxy"

    points = np.array([to_local_xy(transformer, p[0], p[1]) for p in rupture], dtype=float)
    if rupture_kind == "polygon":
        closed = np.vstack([points, points[:1]])
        distance = np.where(inside_polygon(x, y, points), 0.0, segment_distance_m(x, y, closed))
    else:
        distance = segment_distance_m(x, y, points)
    return distance / 1000.0, "rupture_geometry"


def build_grid(bounds: dict) -> GridSpec:
    validate_bounds(bounds)
    width_m, height_m = domain_size_m(bounds)
    if max(width_m, height_m) > MAX_DOMAIN_KM * 1000:
        raise ValueError(f"domain is larger than {MAX_DOMAIN_KM:g} km")
    cell_m = max(MIN_CELL_M, math.sqrt(width_m * height_m / MAX_CELLS))
    return GridSpec(
        bounds["south"], bounds["west"], bounds["north"], bounds["east"],
        max(1, round(height_m / cell_m)), max(1, round(width_m / cell_m)), cell_m,
    )


def footprint_radius_km(magnitude: float, mechanism: str, vs30: float, min_pga_g: float = DISPLAY_PGA_G) -> float:
    """Distance at which median PGA falls to min_pga_g."""
    distance = np.arange(0.0, gmpe.RJB_MAX_KM + 0.1, 0.1)
    pga, _ = gmpe.predict_pga(magnitude, mechanism, distance, vs30)
    above = np.nonzero(pga >= min_pga_g)[0]
    return float(distance[above[-1]]) if len(above) else 0.0


def footprint_bounds(lat: float, lng: float, radius_km: float) -> dict:
    half_m = max(radius_km, 1.0) * 1.05 * 1000
    d_lat = half_m / METERS_PER_DEGREE
    d_lng = half_m / (METERS_PER_DEGREE * math.cos(math.radians(lat)))
    return {"south": lat - d_lat, "west": lng - d_lng, "north": lat + d_lat, "east": lng + d_lng}


def run_at_point(lat: float, lng: float, magnitude: float, mechanism: str, bounds: dict | None = None,
                 vs30_default: float = VS30_DEFAULT, rupture=None, rupture_kind: str = "line",
                 min_pga_g: float = DISPLAY_PGA_G) -> dict:
    """Median PGA at or above min_pga_g around (lat, lng); without bounds the box fits that footprint."""
    if not -90 < lat < 90 or not -180 <= lng <= 180:
        raise ValueError("lat/lng out of range")
    gmpe.validate(magnitude, mechanism, vs30_default)
    radius_km = footprint_radius_km(magnitude, mechanism, vs30_default, min_pga_g)
    if bounds is None:
        bounds = footprint_bounds(lat, lng, radius_km)
    grid = build_grid(bounds)

    cell_lat, cell_lon = cell_centers(grid)
    r_jb, distance_model = joyner_boore_km(cell_lat, cell_lon, lat, lng, rupture, rupture_kind)
    vs30, site_model = load_vs30(bounds, grid, vs30_default)
    pga50, sigma = gmpe.predict_pga(magnitude, mechanism, r_jb, vs30)

    in_domain = (r_jb <= gmpe.RJB_MAX_KM) & (pga50 >= min_pga_g)
    q = quantize(pga50, VALUE_SCALE)
    rows, cols = np.nonzero(in_domain & (q > 0))
    summary = {"max_pga_g": 0.0, "max_pga16_g": 0.0, "max_pga84_g": 0.0}
    summary_extra = {"footprint_radius_km": radius_km, "min_pga_g": min_pga_g}
    if len(rows):
        top = np.argmax(pga50[rows, cols])
        r, c = rows[top], cols[top]
        summary = {
            "max_pga_g": float(pga50[r, c]),
            "max_pga16_g": float(pga50[r, c] * math.exp(-sigma[r, c])),
            "max_pga84_g": float(pga50[r, c] * math.exp(sigma[r, c])),
        }

    return raster_result(
        "earthquake",
        {
            "id": "BSSA14-PGA",
            "distance_model": distance_model,
            "site_model": site_model,
            "assumptions": [
                "shallow crustal active-tectonic-region GMPE",
                "median horizontal RotD50 PGA",
                "point-source RJB approximation unless rupture geometry supplied",
            ],
        },
        grid, "PGA", "g", VALUE_SCALE,
        source={"lat": lat, "lng": lng, "magnitude": magnitude, "mechanism": mechanism},
        cells=encode_sparse(rows, cols, q[rows, cols]),
        sigma_ln=encode_sparse(rows, cols, quantize(sigma[rows, cols], SIGMA_SCALE)),
        sigma_scale=SIGMA_SCALE,
        summary={**summary, **summary_extra},
    )
