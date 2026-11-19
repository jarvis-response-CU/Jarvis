import numpy as np
import pytest

from jarvis.simulations.earthquake import gmpe


def pga(m=6.5, mech="strike_slip", r=10.0, v=760.0):
    median, sigma = gmpe.predict_pga(m, mech, r, v)
    return float(median), float(sigma)


@pytest.mark.parametrize(
    "args, median, sigma",
    [
        ((6.5, "strike_slip", 10, 760), 0.210403, 0.605086),
        ((6.5, "strike_slip", 10, 300), 0.286659, 0.605086),
        ((5.0, "reverse", 50, 760), 0.00898348, 0.702249),
    ],
)
def test_golden_values(args, median, sigma):
    result = pga(*args)
    assert result[0] == pytest.approx(median, rel=1e-4)
    assert result[1] == pytest.approx(sigma, rel=1e-4)


def test_reference_rock_has_no_site_amplification():
    assert gmpe.linear_site_term(760.0) == 0
    assert gmpe.nonlinear_site_term(760.0, 0.3) == pytest.approx(0)


def test_softer_soil_amplifies():
    assert pga(v=300)[0] > pga(v=760)[0] > pga(v=1200)[0]


def test_positive_and_decays_with_distance():
    distances = np.array([0, 1, 5, 10, 25, 50, 100, 200, 400])
    median, sigma = gmpe.predict_pga(6.5, "unspecified", distances, 760.0)
    assert (median > 0).all() and (sigma > 0).all()
    assert (np.diff(median) < 0).all()


def test_larger_magnitude_is_stronger():
    assert pga(m=7.5)[0] > pga(m=6.5)[0] > pga(m=5.5)[0]


@pytest.mark.parametrize("mechanism", sorted(gmpe.MECHANISMS))
def test_all_mechanisms_run(mechanism):
    median, sigma = pga(mech=mechanism)
    assert 0 < median < 2 and sigma > 0


def test_mechanisms_differ():
    assert len({round(pga(mech=m)[0], 6) for m in gmpe.MECHANISMS}) == 4


@pytest.mark.parametrize(
    "kwargs",
    [
        {"m": (4.5 - 1e-9, 4.5 + 1e-9)},
        {"m": (5.5 - 1e-9, 5.5 + 1e-9)},
        {"r": (gmpe.PGA["R1"] - 1e-9, gmpe.PGA["R1"] + 1e-9)},
        {"r": (gmpe.PGA["R2"] - 1e-9, gmpe.PGA["R2"] + 1e-9)},
        {"v": (gmpe.V1 - 1e-9, gmpe.V1 + 1e-9)},
        {"v": (gmpe.V2 - 1e-9, gmpe.V2 + 1e-9)},
    ],
)
def test_continuity(kwargs):
    (key, (low, high)), = kwargs.items()
    below = pga(**{key: low})
    above = pga(**{key: high})
    assert below[0] == pytest.approx(above[0], rel=1e-6)
    assert below[1] == pytest.approx(above[1], rel=1e-6)


def test_source_term_is_continuous_at_hinge():
    assert gmpe.source_term(5.5 - 1e-9, "reverse") == pytest.approx(gmpe.source_term(5.5 + 1e-9, "reverse"))


def test_sigma_distance_and_site_corrections():
    base = gmpe.sigma_ln(6.5, 10, 760)
    assert gmpe.sigma_ln(6.5, 400, 760) > base
    assert gmpe.sigma_ln(6.5, 10, 200) < base


@pytest.mark.parametrize(
    "magnitude, mechanism, vs30",
    [(2.9, "strike_slip", 760), (8.6, "strike_slip", 760), (6, "thrust", 760), (6, "normal", 100), (6, "normal", 2000)],
)
def test_domain_is_enforced(magnitude, mechanism, vs30):
    with pytest.raises(ValueError):
        gmpe.validate(magnitude, mechanism, vs30)
