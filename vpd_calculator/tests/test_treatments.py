import io
import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import treatments as tr  # noqa: E402
import vpd  # noqa: E402

pytestmark = pytest.mark.unit


def rows(*records):
    return pd.DataFrame(records, columns=tr.INPUTS)


def test_two_valid_treatments_match_the_production_calculation():
    out = tr.evaluate(rows(("Control", 22.0, 60.0, 0.0), ("Warm", 33.0, 60.0, -2.0)))
    for (_, r), (t, rh, off) in zip(out.iterrows(), [(22.0, 60.0, 0.0), (33.0, 60.0, -2.0)]):
        ref = vpd.calculate_vpd(t, rh, off)
        assert r[tr.T_LEAF] == ref.t_leaf and r[tr.VPD_AIR] == ref.vpd_air and r[tr.VPD_LEAF] == ref.vpd_leaf
        assert r[tr.STATUS] == tr.OK
    assert out[tr.VPD_AIR].tolist() == [vpd.vpd_air(22, 60), vpd.vpd_air(33, 60)]
    assert out[tr.T_LEAF].tolist() == [22.0, 31.0]


def test_example_rows_are_the_documented_defaults():
    ex = tr.evaluate(tr.EXAMPLES)
    assert ex[tr.NAME].str.startswith("Example").all()
    assert ex[tr.T_AIR].tolist() == [22.0, 33.0] and ex[tr.RH].tolist() == [60.0, 60.0]
    assert ex[tr.OFFSET].tolist() == [0.0, 0.0] and (ex[tr.STATUS] == tr.OK).all()


def test_invalid_and_incomplete_rows_are_flagged_while_valid_rows_still_calculate():
    out = tr.evaluate(rows(("Good", 25.0, 50.0, 0.0), ("Hot", 99.0, 50.0, 0.0), ("No RH", 25.0, None, 0.0),
                           ("", 25.0, 50.0, 0.0), ("Humid", 25.0, 120.0, 0.0), ("Text", "abc", 50.0, 0.0),
                           ("Inf", float("inf"), 50.0, 0.0), ("Offset", 25.0, 50.0, 11.0), (None, None, None, None)))
    assert out.loc[0, tr.STATUS] == tr.OK and out.loc[0, tr.VPD_AIR] == vpd.vpd_air(25, 50)
    bad = out.iloc[1:]
    assert all(s.startswith(f"Row {i} not calculated") for i, s in zip(range(2, 10), bad[tr.STATUS]))
    assert bad[[tr.T_LEAF, tr.VPD_AIR, tr.VPD_LEAF]].isna().all().all()
    assert "between -10 and 60" in out.loc[1, tr.STATUS] and "Relative humidity missing" in out.loc[2, tr.STATUS]
    assert "treatment name missing" in out.loc[3, tr.STATUS] and "between 0 and 100" in out.loc[4, tr.STATUS]
    assert "not a number" in out.loc[5, tr.STATUS] and "between -10 and 10" in out.loc[7, tr.STATUS]


def test_negative_leaf_vpd_is_flagged_as_possible_condensation():
    out = tr.evaluate(rows(("Fog", 22.0, 100.0, -3.0), ("Dry", 22.0, 40.0, -3.0)))
    assert out.loc[0, tr.VPD_LEAF] < 0 and out.loc[0, tr.STATUS] == tr.CONDENSATION
    assert out.loc[1, tr.STATUS] == tr.OK


def test_csv_has_inputs_and_results_at_full_precision():
    out = tr.evaluate(rows(("A", 22.34, 60.0, -1.5), ("bad", 22.0, None, 0.0)))
    csv = pd.read_csv(io.StringIO(tr.to_csv(out).decode()))
    assert list(csv.columns) == tr.INPUTS + tr.RESULTS + [tr.STATUS]
    ref = vpd.calculate_vpd(22.34, 60.0, -1.5)
    assert csv.loc[0, tr.VPD_AIR] == pytest.approx(ref.vpd_air, abs=1e-12) and csv.loc[0, tr.VPD_AIR] != round(ref.vpd_air, 1)
    assert csv.loc[0, tr.T_AIR] == 22.34 and csv.loc[0, tr.OFFSET] == -1.5
    assert math.isnan(csv.loc[1, tr.VPD_AIR]) and "not calculated" in csv.loc[1, tr.STATUS]
