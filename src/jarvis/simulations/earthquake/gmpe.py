# References:
#   Boore, Stewart, Seyhan & Atkinson (2014), Earthquake Spectra 30(3), 1057-1085, doi:10.1193/070113EQS184M

"""BSSA14 NGA-West2 ground-motion model for PGA, base-region, no basin term."""

import numpy as np

PGA = {
    "e0": 0.4473, "e1": 0.4856, "e2": 0.2459, "e3": 0.4539, "e4": 1.4310, "e5": 0.05053,
    "e6": -0.1662, "Mh": 5.5,
    "c1": -1.1340, "c2": 0.1917, "c3": -0.008088, "h": 4.5, "delta_c3": 0.0,
    "c": -0.6000, "Vc": 1500.0, "f4": -0.1500, "f5": -0.007010,
    "R1": 110.0, "R2": 270.0, "delta_phi_R": 0.100, "delta_phi_V": 0.070,
    "phi1": 0.695, "phi2": 0.495, "tau1": 0.398, "tau2": 0.348,
}
MREF = 4.5
RREF_KM = 1.0
VREF = 760.0
SITE_F1 = 0.0
SITE_F3 = 0.1
V1 = 225.0
V2 = 300.0
MECHANISMS = {"unspecified": "e0", "strike_slip": "e1", "normal": "e2", "reverse": "e3"}
MAG_RANGE = (3.0, 8.5)
RJB_MAX_KM = 400.0
VS30_RANGE = (150.0, 1500.0)


def validate(magnitude: float, mechanism: str, vs30=None) -> None:
    if not MAG_RANGE[0] <= magnitude <= MAG_RANGE[1]:
        raise ValueError(f"magnitude must be within {MAG_RANGE[0]} to {MAG_RANGE[1]}")
    if mechanism not in MECHANISMS:
        raise ValueError(f"mechanism must be one of {sorted(MECHANISMS)}")
    if vs30 is not None:
        vs30 = np.asarray(vs30, dtype=float)
        if vs30.min() < VS30_RANGE[0] or vs30.max() > VS30_RANGE[1]:
            raise ValueError(f"Vs30 must be within {VS30_RANGE[0]:g} to {VS30_RANGE[1]:g} m/s")


def source_term(magnitude: float, mechanism: str, c=PGA) -> float:
    e_mech = c[MECHANISMS[mechanism]]
    dm = magnitude - c["Mh"]
    if magnitude <= c["Mh"]:
        return e_mech + c["e4"] * dm + c["e5"] * dm**2
    return e_mech + c["e6"] * dm


def path_term(magnitude: float, r_jb_km, c=PGA):
    r = np.sqrt(np.asarray(r_jb_km, dtype=float) ** 2 + c["h"] ** 2)
    return (
        (c["c1"] + c["c2"] * (magnitude - MREF)) * np.log(r / RREF_KM)
        + (c["c3"] + c["delta_c3"]) * (r - RREF_KM)
    )


def linear_site_term(vs30, c=PGA):
    return c["c"] * np.log(np.minimum(vs30, c["Vc"]) / VREF)


def nonlinear_site_term(vs30, pga_rock, c=PGA):
    vs = np.minimum(vs30, VREF)
    f2 = c["f4"] * (np.exp(c["f5"] * (vs - 360.0)) - np.exp(c["f5"] * (VREF - 360.0)))
    return SITE_F1 + f2 * np.log((pga_rock + SITE_F3) / SITE_F3)


def ramp(low, high, m):
    """Linear interpolation between the M <= 4.5 and M >= 5.5 values."""
    return np.interp(m, [MREF, 5.5], [low, high])


def sigma_ln(magnitude: float, r_jb_km, vs30, c=PGA):
    """Total aleatory standard deviation of ln PGA."""
    r_jb_km = np.asarray(r_jb_km, dtype=float)
    vs30 = np.asarray(vs30, dtype=float)
    tau = ramp(c["tau1"], c["tau2"], magnitude)
    phi = ramp(c["phi1"], c["phi2"], magnitude)
    with np.errstate(divide="ignore", invalid="ignore"):
        distance_part = np.where(
            r_jb_km <= c["R1"], 0.0,
            np.where(
                r_jb_km <= c["R2"],
                c["delta_phi_R"] * np.log(np.maximum(r_jb_km, c["R1"]) / c["R1"]) / np.log(c["R2"] / c["R1"]),
                c["delta_phi_R"],
            ),
        )
        site_part = np.where(
            vs30 <= V1, c["delta_phi_V"],
            np.where(
                vs30 < V2,
                c["delta_phi_V"] * np.log(V2 / np.clip(vs30, V1, V2)) / np.log(V2 / V1),
                0.0,
            ),
        )
    phi = phi + distance_part - site_part
    return np.sqrt(tau**2 + phi**2)


def predict_pga(magnitude: float, mechanism: str, r_jb_km, vs30):
    """Median PGA in g and sigma of ln PGA, broadcast over r_jb_km and vs30."""
    validate(magnitude, mechanism)
    r_jb_km = np.asarray(r_jb_km, dtype=float)
    vs30 = np.asarray(vs30, dtype=float)
    fe_fp = source_term(magnitude, mechanism) + path_term(magnitude, r_jb_km)
    # reference-rock pga feeds the nonlinear site term
    pga_rock = np.exp(fe_fp)
    mu = fe_fp + linear_site_term(vs30) + nonlinear_site_term(vs30, pga_rock)
    return np.exp(mu), sigma_ln(magnitude, r_jb_km, vs30)
