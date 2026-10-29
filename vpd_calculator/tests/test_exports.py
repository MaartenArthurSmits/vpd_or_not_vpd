"""Export-file validation: CSV grid, settings CSV pieces, VPD-vs-RH CSV, R script."""

import io
import re
import shutil
import subprocess

import pandas as pd
import pytest

import plots
import rscript
import validation
import vpd

pytestmark = pytest.mark.exports


def parse_r_output(text):
    out = {}
    for line in text.splitlines():
        m = re.match(r"^(\w+): (-?\d+\.\d+)$", line.strip())
        if m:
            out[m.group(1)] = float(m.group(2))
    return out


def test_grid_csv_has_expected_columns_and_values():
    csv = vpd.vpd_grid(10, 40, 10, 100, 0.5, 1.0).to_csv(index=False)
    df = pd.read_csv(io.StringIO(csv))
    assert {"temperature_C", "RH_percent", "leaf_temperature_C", "es_kPa", "ea_kPa",
            "VPD_air_kPa", "VPD_leaf_kPa"} <= set(df.columns)
    assert len(df) == 61 * 91
    assert df.notna().all().all()
    assert df["VPD_air_kPa"].min() >= -1e-12 and df["RH_percent"].between(10, 100).all()
    cell = df[(df.temperature_C == 22) & (df.RH_percent == 60)].iloc[0]
    assert cell["VPD_air_kPa"] == pytest.approx(1.0576, abs=1e-4)


def test_validation_csv_content():
    curves = validation.reference_curves([20, 25, 30])
    df = pd.read_csv(io.StringIO(curves.to_csv(index=False)))
    assert sorted(df.temperature_C.unique()) == [20, 25, 30]
    assert df.RH_percent.min() == 0 and df.RH_percent.max() == 100
    at100 = df[df.RH_percent == 100]
    assert (at100.VPD_FAO56_kPa.abs() < 1e-12).all()
    assert (df.difference_FAO56_minus_Johnston_kPa.abs() < 0.01).all()


def test_reference_figures_build():
    curves = validation.reference_curves([20, 25, 30])
    assert len(plots.reference_figure(curves, False).data) == 3
    assert len(plots.reference_figure(curves, True).data) == 6
    assert len(plots.reference_difference_figure(curves).data) == 3


def test_png_export_produces_valid_png():
    pytest.importorskip("kaleido")
    fig = plots.heatmap_figure(10, 40, 10, 100, template="plotly_white", width=700, height=500)
    try:
        png = fig.to_image(format="png")
    except Exception as e:  # Chrome not available in this environment
        pytest.skip(f"kaleido/Chrome unavailable: {type(e).__name__}")
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 5_000


def test_r_script_structure_forward_and_reverse():
    a = rscript.build_r_script(True, 22.0, 60.0, 1.0, vpd.AIR, 22.0, (0.8, 1.2), vpd.AIR)
    assert "es <- function(t) 0.6108 * exp(17.27 * t / (t + 237.3))" in a
    assert "t_air  <- 22.0" in a and "rh     <- 60.0" in a and "vpd_lo <- 0.8" in a
    b = rscript.build_r_script(False, 22.0, 60.0, 1.0, vpd.LEAF, 20.0, None)
    assert "rh <- 100 * (es(t_leaf) - target_vpd) / es(t_air)" in b
    assert "vpd_lo" not in b


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript not installed")
@pytest.mark.parametrize("mode_a,t,rh,target,kind,t_leaf", [
    (True, 22.0, 60.0, 1.0, vpd.AIR, 20.0),
    (False, 22.0, 60.0, 1.0, vpd.AIR, 22.0),
    (False, 25.0, 60.0, 0.8, vpd.LEAF, 23.0),
])
def test_r_script_reproduces_app_values(tmp_path, mode_a, t, rh, target, kind, t_leaf):
    script = rscript.build_r_script(mode_a, t, rh, target, kind, t_leaf, (0.8, 1.2), vpd.AIR)
    path = tmp_path / "vpd.R"
    path.write_text(script, encoding="utf-8")
    res = subprocess.run(["Rscript", str(path)], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    r = parse_r_output(res.stdout)
    expected = (vpd.calculate_vpd(t, rh, measured_leaf=t_leaf) if mode_a
                else vpd.calculate_required_rh(t, target, kind, measured_leaf=t_leaf))
    assert r["vpd_air"] == pytest.approx(expected.vpd_air, abs=1e-6)   # R prints 6 d.p.
    assert r["vpd_leaf"] == pytest.approx(expected.vpd_leaf, abs=1e-6)
    assert r["rh"] == pytest.approx(expected.rh, abs=1e-5)
