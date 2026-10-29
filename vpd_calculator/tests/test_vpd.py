import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import vpd  # noqa: E402

pytestmark = pytest.mark.science


def test_air_vpd_22c_60rh():
    assert vpd.vpd_air(22, 60) == pytest.approx(1.0576, abs=2e-3)
    assert vpd.calculate_vpd(22, 60).vpd_air == pytest.approx(1.0576, abs=2e-3)


def test_required_rh_for_air_vpd_1kpa():
    r = vpd.calculate_required_rh(22, 1.0, vpd.AIR)
    assert r.rh == pytest.approx(62.18, abs=0.02)
    assert r.attainable
    assert r.vpd_air == pytest.approx(1.0, abs=1e-9)


def test_leaf_vpd_with_negative_offset():
    r = vpd.calculate_vpd(22, 60, offset=-2)
    assert r.vpd_leaf == pytest.approx(0.7519, abs=2e-3)
    assert r.t_leaf == 20


def test_reverse_leaf_recovers_rh():
    for t, rh, off in [(22, 60, -2), (33, 45, -1.5), (17, 80, 1.0), (25, 30, 0)]:
        v = vpd.vpd_leaf(t, rh, t + off)
        r = vpd.calculate_required_rh(t, v, vpd.LEAF, offset=off)
        assert r.rh == pytest.approx(rh, abs=1e-9)


def test_forward_reverse_consistent_over_grid():
    for t in np.arange(5, 41, 2.5):
        for rh in np.arange(10, 101, 10):
            for off in (-3, 0, 2):
                fwd = vpd.calculate_vpd(t, rh, off)
                a = vpd.calculate_required_rh(t, fwd.vpd_air, vpd.AIR, off)
                b = vpd.calculate_required_rh(t, fwd.vpd_leaf, vpd.LEAF, off)
                assert a.rh == pytest.approx(rh, abs=1e-8)
                assert b.rh == pytest.approx(rh, abs=1e-8)
                assert a.attainable and b.attainable


def test_zero_air_vpd_at_saturation():
    for t in (5, 22, 33):
        assert vpd.vpd_air(t, 100) == pytest.approx(0, abs=1e-12)


def test_unattainable_targets_flagged_not_clamped():
    too_low = vpd.calculate_required_rh(22, -0.5, vpd.AIR)
    assert not too_low.attainable and too_low.rh > 100
    too_high = vpd.calculate_required_rh(22, 5.0, vpd.AIR)
    assert not too_high.attainable and too_high.rh < 0
    assert "Unattainable" in too_high.message
    # leaf 3 degrees cooler: minimum leaf VPD (100% RH) is about -0.55 kPa
    leaf = vpd.calculate_required_rh(22, -0.7, vpd.LEAF, offset=-3)
    assert not leaf.attainable and leaf.rh > 100
    assert vpd.calculate_required_rh(22, 0.1, vpd.LEAF, offset=-3).attainable


def test_negative_leaf_vpd_warns():
    r = vpd.calculate_vpd(22, 95, offset=-3)
    assert r.vpd_leaf < 0
    assert any("condensation" in w for w in r.warnings)


def test_mode_switch_consistency():
    # A -> B -> A round trip returns original inputs
    a = vpd.calculate_vpd(25, 55, offset=-1)
    b = vpd.calculate_required_rh(25, a.vpd_leaf, vpd.LEAF, offset=-1)
    a2 = vpd.calculate_vpd(25, b.rh, offset=-1)
    assert a2.vpd_air == pytest.approx(a.vpd_air)
    assert a2.vpd_leaf == pytest.approx(a.vpd_leaf)
    # measured leaf temperature equals equivalent offset
    m = vpd.calculate_vpd(25, 55, measured_leaf=24)
    assert m.vpd_leaf == pytest.approx(a.vpd_leaf)


def test_rh_range_orientation_and_clipping():
    r = vpd.rh_range_for_vpd_range(22, 0.8, 1.2)
    assert r["rh_min"] < r["rh_max"]
    assert r["rh_max"] == pytest.approx(vpd.rh_for_air_vpd(22, 0.8))
    r2 = vpd.rh_range_for_vpd_range(22, 0.0, 10.0)
    assert r2["rh_min"] == 0 and not r2["fully_attainable"]
    assert not vpd.rh_range_for_vpd_range(22, 4.0, 5.0)["attainable"]


def test_grid_and_matrix_agree():
    g = vpd.vpd_grid(15, 30, 40, 90, 5, 10, offset=-2)
    m = vpd.vpd_matrix(np.arange(15, 31, 5), np.arange(40, 91, 10), vpd.LEAF, -2)
    assert np.allclose(g["VPD_leaf_kPa"].to_numpy().reshape(m.shape), m)


# ---- classify_vpd: absolute floating-point tolerance at the target limits ----------------------
def test_classify_tolerance_is_tiny_and_documented():
    assert vpd.VPD_CLASSIFY_TOL == 1e-9


@pytest.mark.parametrize("value,expected", [
    (0.8, "inside"), (1.2, "inside"), (1.0, "inside"),                       # exact boundaries
    (0.8 - 1e-12, "inside"), (0.8 + 1e-12, "inside"),                        # noise at the lower limit
    (1.2 - 1e-12, "inside"), (1.2 + 1e-12, "inside"),                        # noise at the upper limit
    (np.nextafter(1.2, 2.0), "inside"), (np.nextafter(0.8, 0.0), "inside"),  # one ulp outside
    (0.8 - 1e-6, "below"), (0.8 - 0.01, "below"), (0.0, "below"), (-0.5, "below"),
    (1.2 + 1e-6, "above"), (1.2 + 0.01, "above"), (5.0, "above"),
])
def test_classify_ordinary_range(value, expected):
    assert vpd.classify_vpd(value, 0.8, 1.2) == expected


def test_classify_tolerance_edge_is_not_widened_beyond_1e9():
    assert vpd.classify_vpd(1.2 + 2e-9, 0.8, 1.2) == "above"
    assert vpd.classify_vpd(0.8 - 2e-9, 0.8, 1.2) == "below"


@pytest.mark.parametrize("value,expected", [
    (1.0, "inside"), (1.0000000000000004, "inside"), (1.0 - 4e-16, "inside"), (1.0 + 5e-10, "inside"),
    (1.0 + 1e-6, "above"), (1.0 - 1e-6, "below"), (1.01, "above"), (0.99, "below"),
])
def test_classify_equal_limits(value, expected):
    assert vpd.classify_vpd(value, 1.0, 1.0) == expected


@pytest.mark.parametrize("kind", [vpd.AIR, vpd.LEAF])
def test_classify_reverse_calculation_at_25c_with_point_target(kind):
    r = vpd.calculate_required_rh(25, 1.0, kind)
    value = r.vpd_air if kind == vpd.AIR else r.vpd_leaf     # full precision, unrounded
    assert vpd.classify_vpd(value, 1.0, 1.0) == "inside"
    assert vpd.classify_vpd(value, 1.0, 1.2) == "inside"
    assert vpd.classify_vpd(value, 0.8, 1.0) == "inside"


def test_classify_25c_air_example_value_is_noisy():
    value = vpd.calculate_required_rh(25, 1.0, vpd.AIR).vpd_air
    assert value != 1.0 and abs(value - 1.0) < 1e-12        # the floating-point noise being absorbed
    assert vpd.classify_vpd(value, 1.0, 1.0) == "inside"
    assert (value > 1.0) == (value == 1.0000000000000004)    # documents the observed overshoot
