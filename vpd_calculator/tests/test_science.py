"""Scientific tests: published tabulated values, calculated benchmarks, an alternative equation,
and mathematical properties. Tolerances are stated explicitly below.

Evidence categories (kept separate on purpose):
  1. agreement with PUBLISHED tabulated values: FAO-56 Annex 2, Table 2.3 (saturation vapour pressure)
  2. agreement with CALCULATED benchmarks: air VPDs evaluated from the FAO-56 Eq. 11 constants (4 d.p.).
     These are not printed in FAO-56 Table 2.3 and are not an independent source.
  3. comparison with an alternative published equation (Johnston et al., 2025), implemented independently
     here; its coefficients are verified against the paper (Eq. 2, external review 2026-10-29); its benchmark
     VPDs are calculated from that equation (not verified to be printed in the paper)
  4. internal consistency / mathematical properties
None of these are experimental measurements.
"""

import io
import math

import numpy as np
import pandas as pd
import pytest

import plots
import validation
import vpd

pytestmark = pytest.mark.science

# ---- explicit tolerances -----------------------------------------------------
TOL_TABLE_ES = 5.0e-4 + 1e-9      # kPa; FAO-56 Table 2.3 is rounded to 3 d.p. (half unit 5e-4)
TOL_REF_VPD = 1.0e-4              # kPa; calculated benchmark VPDs are rounded to 4 d.p. (half unit 5e-5)
TOL_EXACT = 1.0e-12               # kPa; same equation through different code paths
TOL_RH_ROUNDTRIP = 1.0e-9         # percentage points; forward -> reverse round trip
MAX_REL_EQ_DIFF = 3.0e-3          # |es_FAO - es_Johnston| / es over 0-40 degC (observed ~1e-3)

# ---- reference data ---------------------------------------------------------
# PUBLISHED: es values printed in FAO-56 Annex 2, Table 2.3 (rows T = 15.0 ... 35.0 checked against
# https://www.fao.org/4/x0490e/x0490e0j.htm, 2026-10-29).
FAO_ES = {15: 1.705, 20: 2.338, 22: 2.644, 25: 3.168, 30: 4.243, 33: 5.030, 35: 5.623}
# CALCULATED (not published): es(T) * (1 - RH/100) with the FAO-56 Eq. 11 / Johnston et al. (2025)
# constants, rounded to 4 d.p. Origin: earlier project specification; reproduced at 4 d.p. by a
# stand-alone calculation on 2026-10-29. Not printed in FAO-56 Table 2.3.
CASES = [  # T, RH, FAO-56-equation VPD, Johnston-equation VPD
    (20, 50, 1.1691, 1.1710),
    (22, 60, 1.0576, 1.0593),
    (25, 60, 1.2671, 1.2691),
    (30, 70, 1.2729, 1.2747),
    (33, 60, 2.0121, 2.0146),
]


def johnston_es_independent(t):
    """Johnston et al. (2025) as printed (hPa), converted to kPa. Written independently of production code."""
    es_hpa = 6.1078 * math.exp(17.08085 * t / (t + 234.175))
    return es_hpa / 10.0


def johnston_vpd_independent(t, rh):
    return johnston_es_independent(t) * (1.0 - rh / 100.0)


TEMPS = np.arange(-5.0, 50.0, 2.5)
RHS = np.arange(0.0, 100.1, 12.5)


# ===== 1. published tabulated values (FAO-56 Table 2.3) ========================
@pytest.mark.parametrize("t,published", list(FAO_ES.items()))
def test_es_matches_fao56_table_2_3(t, published):
    assert abs(vpd.saturation_vapour_pressure(t) - published) <= TOL_TABLE_ES


@pytest.mark.parametrize("t,rh,fao,_j", CASES)
def test_air_vpd_matches_calculated_fao56_benchmarks(t, rh, fao, _j):   # calculated, not published
    assert abs(vpd.calculate_vpd(t, rh).vpd_air - fao) <= TOL_REF_VPD


# ===== 2. calculated benchmarks and the alternative published equation ==========
# (the Johnston implementation below is independent of production code)
@pytest.mark.parametrize("t,rh,_f,johnston", CASES)
def test_independent_johnston_implementation_reproduces_calculated_benchmarks(t, rh, _f, johnston):
    assert abs(johnston_vpd_independent(t, rh) - johnston) <= TOL_REF_VPD


@pytest.mark.parametrize("t", [0, 10, 15, 22, 30, 40])
def test_validation_module_johnston_matches_independent_reference(t):
    assert validation.johnston_es(t) == pytest.approx(johnston_es_independent(t), abs=TOL_EXACT)


@pytest.mark.parametrize("t,rh,_f,_j", CASES)
def test_application_close_to_johnston_but_not_identical(t, rh, _f, _j):
    app = vpd.calculate_vpd(t, rh).vpd_air
    alt = johnston_vpd_independent(t, rh)
    assert app != pytest.approx(alt, abs=1e-6)          # coefficients differ, so values differ
    assert abs(app - alt) / alt < MAX_REL_EQ_DIFF        # but only slightly


def test_equation_difference_is_small_over_growth_range():
    for t in np.arange(0, 40.1, 1.0):
        rel = abs(float(vpd.saturation_vapour_pressure(t)) - johnston_es_independent(t)) / johnston_es_independent(t)
        assert rel < MAX_REL_EQ_DIFF


def test_validation_tables_all_within_tolerance():
    assert (validation.es_comparison()["Outcome"] == "Within tolerance").all()
    assert (validation.vpd_comparison()["Outcome (vs calculated benchmark)"] == "Within tolerance").all()
    mx = validation.max_abs_differences()
    assert mx["es_vs_FAO_table"] <= TOL_TABLE_ES
    assert mx["vpd_vs_FAO56_benchmark"] <= TOL_REF_VPD


def test_validation_table_labels_do_not_call_calculated_values_published():
    assert "Published es (kPa)" in validation.es_comparison().columns
    cols = list(validation.vpd_comparison().columns) + list(validation.alternative_equation_comparison().columns)
    assert "FAO-56 calculated benchmark VPD (kPa)" in cols
    assert "Johnston calculated benchmark VPD (kPa)" in cols
    assert not any("published" in c.lower() for c in cols)


def test_validation_flags_a_wrong_reference():
    bad = [(22, 60, 1.2000, 1.0593)]
    assert validation.vpd_comparison(bad)["Outcome (vs calculated benchmark)"].iloc[0] == "Outside tolerance"


# ===== 3. internal consistency: mathematical properties ==============================================
def test_es_monotonic_in_temperature():
    es = vpd.saturation_vapour_pressure(np.arange(-10, 60, 0.25))
    assert np.all(np.diff(es) > 0)


@pytest.mark.parametrize("t", [0.0, 5.0, 15.0, 22.0, 33.0, 45.0])
def test_air_vpd_decreases_linearly_with_rh(t):
    rh = np.linspace(0, 100, 101)
    v = vpd.vpd_air(t, rh)
    assert np.all(np.diff(v) < 0)
    assert np.allclose(np.diff(v, 2), 0, atol=TOL_EXACT)


@pytest.mark.parametrize("rh", [0, 25, 60, 100])
def test_air_vpd_increases_with_temperature_at_constant_rh(rh):
    v = vpd.vpd_air(np.arange(0, 45, 1.0), rh)
    if rh == 100:
        assert np.allclose(v, 0, atol=TOL_EXACT)
    else:
        assert np.all(np.diff(v) > 0)


@pytest.mark.parametrize("t", TEMPS)
def test_limits_zero_vpd_at_saturation_and_es_at_zero_rh(t):
    assert abs(vpd.vpd_air(t, 100.0)) <= TOL_EXACT
    assert abs(vpd.vpd_air(t, 0.0) - vpd.saturation_vapour_pressure(t)) <= TOL_EXACT


@pytest.mark.parametrize("off", [-4.0, -1.0, 0.0, 2.5])
@pytest.mark.parametrize("kind", [vpd.AIR, vpd.LEAF])
def test_forward_reverse_consistency(off, kind):
    for t in TEMPS:
        for rh in RHS:
            f = vpd.calculate_vpd(t, rh, off)
            target = f.vpd_air if kind == vpd.AIR else f.vpd_leaf
            r = vpd.calculate_required_rh(t, target, kind, off)
            assert abs(r.rh - rh) <= TOL_RH_ROUNDTRIP
            assert r.attainable


def test_leaf_equals_air_when_temperatures_equal():
    for t in TEMPS:
        for rh in RHS:
            r = vpd.calculate_vpd(t, rh, offset=0.0)
            assert abs(r.vpd_leaf - r.vpd_air) <= TOL_EXACT
            assert abs(vpd.vpd_leaf(t, rh) - vpd.vpd_air(t, rh)) <= TOL_EXACT
            assert abs(vpd.calculate_vpd(t, rh, measured_leaf=t).vpd_leaf - r.vpd_air) <= TOL_EXACT


@pytest.mark.parametrize("t,rh", [(22, 60), (10, 30), (35, 80)])
def test_leaf_vpd_increases_with_leaf_temperature(t, rh):
    v = [vpd.vpd_leaf(t, rh, t + off) for off in np.arange(-5, 5.1, 0.5)]
    assert np.all(np.diff(v) > 0)


@pytest.mark.parametrize("t", [10.0, 22.0, 33.0])
def test_negative_leaf_vpd_when_leaf_cool_enough(t):
    r = vpd.calculate_vpd(t, 100.0, offset=-3.0)
    assert r.vpd_leaf < 0
    assert any("condensation" in w for w in r.warnings)


@pytest.mark.parametrize("t,target,kind,off,expect_high", [
    (22, -0.5, vpd.AIR, 0.0, True),     # below minimum (0 kPa at 100 % RH)
    (22, 5.0, vpd.AIR, 0.0, False),     # above es(22) ~ 2.64 kPa
    (22, 3.0, vpd.AIR, 0.0, False),
    (22, -0.7, vpd.LEAF, -3.0, True),   # below es(19) - es(22) ~ -0.55
    (30, 9.0, vpd.LEAF, 2.0, False),
])
def test_impossible_targets_rejected_and_not_clamped(t, target, kind, off, expect_high):
    r = vpd.calculate_required_rh(t, target, kind, off)
    assert not r.attainable
    assert (r.rh > 100) if expect_high else (r.rh < 0)
    assert "Unattainable" in r.message


def test_boundary_targets_are_attainable():
    es22 = float(vpd.saturation_vapour_pressure(22))
    assert vpd.calculate_required_rh(22, es22, vpd.AIR).attainable          # RH = 0 %
    assert vpd.calculate_required_rh(22, 0.0, vpd.AIR).attainable           # RH = 100 %
    assert not vpd.calculate_required_rh(22, es22 + 1e-6, vpd.AIR).attainable


# ===== precision and consistency across code paths ==============================
def test_calculation_paths_agree_at_full_precision():
    t, rh = 27.3, 41.7
    direct = vpd.vpd_air(t, rh)
    via_result = vpd.calculate_vpd(t, rh).vpd_air
    via_grid = vpd.vpd_grid(t, t, rh, rh, 1.0, 1.0)["VPD_air_kPa"].iloc[0]
    via_matrix = vpd.vpd_matrix([t], [rh])[0, 0]
    via_ea = float(vpd.saturation_vapour_pressure(t) - vpd.actual_vapour_pressure(t, rh))
    for other in (via_result, via_grid, via_matrix, via_ea):
        assert abs(other - direct) <= TOL_EXACT


def test_calculator_heatmap_and_csv_agree():
    t, rh = 22.0, 60.0
    expected = vpd.calculate_vpd(t, rh).vpd_air
    grid = vpd.vpd_grid(10, 40, 10, 100, 0.5, 1.0)
    csv = pd.read_csv(io.StringIO(grid.to_csv(index=False)))
    row = csv[(csv.temperature_C == t) & (csv.RH_percent == rh)]
    assert abs(row["VPD_air_kPa"].iloc[0] - expected) <= TOL_EXACT       # CSV round trip keeps precision
    hm = plots.heatmap_figure(10, 40, 10, 100).data[0]
    i = int(np.where(np.isclose(hm.y, rh))[0][0])
    j = int(np.where(np.isclose(hm.x, t))[0][0])
    assert abs(hm.z[i][j] - expected) <= TOL_EXACT


def test_csv_round_trip_preserves_all_values_for_leaf_offset():
    grid = vpd.vpd_grid(5, 35, 10, 100, 2.5, 10.0, offset=-1.5)
    back = pd.read_csv(io.StringIO(grid.to_csv(index=False)))
    pd.testing.assert_frame_equal(grid, back, check_exact=False, atol=TOL_EXACT, rtol=0)


def test_display_rounding_does_not_affect_internal_values():
    r = vpd.calculate_required_rh(22, 1.0, vpd.AIR)
    assert f"{r.rh:.2f}" == "62.18"
    assert r.rh != 62.18                                   # stored unrounded
    assert abs(r.vpd_air - 1.0) <= TOL_EXACT              # exact recovery of the target
    rounded = vpd.vpd_air(22, round(r.rh, 2))             # what rounding would have done
    assert abs(rounded - 1.0) > 1e-6
    back = vpd.calculate_vpd(22, r.rh)
    assert abs(back.vpd_air - 1.0) <= TOL_EXACT
