"""Export-file validation: CSV grid, VPD-vs-RH CSV, Matplotlib PNG/PDF, R script (numbers + ggplot2 heatmap)."""

import io
import re
import shutil
import struct
import subprocess
from pathlib import Path

import pandas as pd
import pytest

import mpl_export
import plots
import rscript
import validation
import vpd

pytestmark = pytest.mark.exports

ROOT = Path(__file__).resolve().parents[1]

HEATMAP = dict(t_min=10.0, t_max=40.0, rh_min=10.0, rh_max=100.0, kind=vpd.LEAF, offset=-2.0,
               colorscale="Viridis", contour_step=0.5, z_max=None, point=(22.0, 60.0), target=(0.8, 1.2))


def parse_r_output(text):
    out = {}
    for line in text.splitlines():
        m = re.match(r"^(\w+): (-?\d+\.\d+)$", line.strip())
        if m:
            out[m.group(1)] = float(m.group(2))
    return out


def r_has_ggplot2():
    if shutil.which("Rscript") is None:
        return False
    res = subprocess.run(["Rscript", "-e", "cat(requireNamespace('ggplot2', quietly=TRUE))"],
                         capture_output=True, text=True, timeout=120)
    return res.stdout.strip() == "TRUE"


# ---- CSV ------------------------------------------------------------------------------
def test_grid_csv_has_expected_columns_and_values():
    csv = vpd.vpd_grid(10, 40, 10, 100, 0.5, 1.0).to_csv(index=False)
    df = pd.read_csv(io.StringIO(csv))
    assert {"temperature_C", "RH_percent", "leaf_temperature_C", "es_kPa", "ea_kPa",
            "VPD_air_kPa", "VPD_leaf_kPa"} <= set(df.columns)
    assert len(df) == 61 * 91
    assert df.notna().all().all()
    assert df["VPD_air_kPa"].min() >= -1e-12 and df["RH_percent"].between(10, 100).all()
    cell = df[(df.temperature_C == 22) & (df.RH_percent == 60)].iloc[0]
    assert cell["VPD_air_kPa"] == pytest.approx(vpd.vpd_air(22, 60), abs=1e-12)   # full precision kept


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


# ---- Matplotlib export: no Chrome/Chromium ------------------------------------------------
def test_heatmap_png_and_pdf_are_valid_without_a_browser():
    fig = mpl_export.heatmap_mpl(**{k: v for k, v in HEATMAP.items()})
    png = mpl_export.to_bytes(fig, "png", 300)
    pdf = mpl_export.to_bytes(fig, "pdf")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", png[16:24]) == (3000, 1950)
    assert pdf[:5] == b"%PDF-"


def test_app_has_no_chrome_dependent_export():
    for f in ("app.py", "mpl_export.py", "requirements.txt"):
        text = (ROOT / f).read_text(encoding="utf-8")
        assert "kaleido" not in text.lower() and "to_image" not in text, f
    assert not (ROOT.parent / "packages.txt").exists()      # no chromium apt package needed


# ---- R script: structure ------------------------------------------------------------------
def test_r_script_structure_forward_and_reverse():
    a = rscript.build_r_script(True, 22.0, 60.0, 1.0, vpd.AIR, 22.0, (0.8, 1.2), vpd.AIR)
    assert "es <- function(t) 0.6108 * exp(17.27 * t / (t + 237.3))" in a
    assert "t_air  <- 22.0" in a and "rh     <- 60.0" in a and "vpd_lo <- 0.8" in a
    assert "library(ggplot2)" not in a                       # heatmap only when requested
    b = rscript.build_r_script(False, 22.0, 60.0, 1.0, vpd.LEAF, 20.0, None)
    assert "rh <- 100 * (es(t_leaf) - target_vpd) / es(t_air)" in b
    assert "vpd_lo" not in b


def test_r_script_heatmap_block_reproduces_settings():
    s = rscript.build_r_script(True, 22.0, 60.0, 1.0, vpd.AIR, 22.0, (0.8, 1.2), vpd.AIR, heatmap=HEATMAP)
    for expected in ("library(ggplot2)", "hm_t_min  <- 10.0", "hm_t_max  <- 40.0", "hm_rh_min <- 10.0",
                     "hm_rh_max <- 100.0", 'hm_kind   <- "leaf"', "hm_offset <- -2.0",
                     'scale_fill_viridis_c(option = "D"', "breaks = unique(c(0.8, 1.2))",
                     'annotate("point", x = 22.0, y = 60.0', 'ggsave("vpd_heatmap.png"', "dpi = 300",
                     'ggsave("vpd_heatmap.pdf"'):
        assert expected in s, expected


def test_r_script_heatmap_omits_target_and_point_when_not_requested():
    h = HEATMAP | {"target": None, "point": None}
    s = rscript.build_r_script(True, 22.0, 60.0, 1.0, vpd.AIR, 22.0, None, vpd.AIR, heatmap=h)
    assert "linetype = \"dashed\"" not in s and "annotate(" not in s


# ---- R script: execution (needs Rscript; heatmap also needs ggplot2) ---------------------------
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


@pytest.mark.skipif(not r_has_ggplot2(), reason="Rscript or ggplot2 not installed")
@pytest.mark.parametrize("heatmap", [HEATMAP, HEATMAP | {"kind": vpd.AIR, "colorscale": "RdYlBu_r", "target": None,
                                                         "point": None}])
def test_r_script_ggplot2_heatmap_runs_and_exports_png_and_pdf(tmp_path, heatmap):
    script = rscript.build_r_script(True, 22.0, 60.0, 1.0, vpd.AIR, 22.0, (0.8, 1.2), vpd.AIR, heatmap=heatmap)
    path = tmp_path / "vpd_heatmap.R"
    path.write_text(script, encoding="utf-8")
    res = subprocess.run(["Rscript", str(path)], capture_output=True, text=True, timeout=300, cwd=tmp_path)
    assert res.returncode == 0, res.stderr
    png = (tmp_path / "vpd_heatmap.png").read_bytes()
    pdf = (tmp_path / "vpd_heatmap.pdf").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", png[16:24]) == (3000, 1950)           # 10 x 6.5 in at 300 dpi
    assert pdf[:5] == b"%PDF-"
    assert parse_r_output(res.stdout)["vpd_air"] == pytest.approx(vpd.vpd_air(22, 60), abs=1e-6)


# ---- R script: target follows the Calculator's air/leaf setting, not the heatmap's colour kind ----
@pytest.mark.parametrize("hm_kind", [vpd.AIR, vpd.LEAF])
@pytest.mark.parametrize("target_kind", [vpd.AIR, vpd.LEAF])
def test_r_script_target_uses_its_own_kind(hm_kind, target_kind):
    h = HEATMAP | {"kind": hm_kind, "target_kind": target_kind}
    s = rscript.build_r_script(True, 22.0, 60.0, 1.0, vpd.AIR, 20.0, (0.8, 1.2), target_kind, heatmap=h)
    assert f'hm_kind   <- "{hm_kind}"' in s and f'hm_target_kind <- "{target_kind}"' in s
    assert "grid$vpd_target <- es(t_ref_target) - es(grid$temperature) * grid$rh / 100" in s
    assert "aes(z = vpd_target), breaks = unique(c(0.8, 1.2))" in s
    assert f"target {'Air' if target_kind == vpd.AIR else 'Canopy'} VPD 0.8-1.2 kPa" in s
    assert "hm_offset <- -2.0" in s


@pytest.mark.skipif(not r_has_ggplot2(), reason="Rscript or ggplot2 not installed")
@pytest.mark.parametrize("hm_kind", [vpd.AIR, vpd.LEAF])
@pytest.mark.parametrize("target_kind,inside", [(vpd.AIR, True), (vpd.LEAF, False)])
def test_r_script_target_region_matches_acceptance_point(tmp_path, hm_kind, target_kind, inside):
    h = HEATMAP | {"kind": hm_kind, "target_kind": target_kind, "colorscale": "Viridis"}
    script = rscript.build_r_script(True, 22.0, 60.0, 1.0, vpd.AIR, 20.0, (0.8, 1.2), target_kind, heatmap=h)
    script += ("\ncell <- grid[grid$temperature == 22 & grid$rh == 60, ]\n"
               "cat(sprintf('target_vpd_cell: %.6f\\n', cell$vpd_target))\n"
               "cat(sprintf('colour_vpd_cell: %.6f\\n', cell$vpd))\n")
    path = tmp_path / "vpd_heatmap.R"
    path.write_text(script, encoding="utf-8")
    res = subprocess.run(["Rscript", str(path)], capture_output=True, text=True, timeout=300, cwd=tmp_path)
    assert res.returncode == 0, res.stderr
    out = parse_r_output(res.stdout)
    air, leaf = vpd.vpd_air(22, 60), vpd.vpd_leaf(22, 60, 20)
    assert out["target_vpd_cell"] == pytest.approx(air if target_kind == vpd.AIR else leaf, abs=1e-6)
    assert out["colour_vpd_cell"] == pytest.approx(air if hm_kind == vpd.AIR else leaf, abs=1e-6)
    assert (0.8 <= out["target_vpd_cell"] <= 1.2) is inside


@pytest.mark.parametrize("target_kind,label", [(vpd.AIR, "target Air VPD 1.0 kPa"),
                                                (vpd.LEAF, "target Canopy VPD 1.0 kPa")])
def test_r_script_single_target_uses_one_contour_and_single_value_label(target_kind, label):
    h = HEATMAP | {"kind": vpd.AIR, "target": (1.0, 1.0), "target_kind": target_kind}
    s = rscript.build_r_script(True, 22.0, 60.0, 1.0, vpd.AIR, 20.0, (1.0, 1.0), target_kind, heatmap=h)
    assert f'subtitle = "Dashed contour: {label}"' in s
    assert "breaks = unique(c(1.0, 1.0))" in s                  # unique() collapses to one break
    assert s.count('linetype = "dashed"') == 1 and "geom_polygon" not in s and "geom_tile" not in s
    assert "# User-defined target for" in s and "target range" not in s


def test_r_script_range_target_wording_is_unchanged():
    h = HEATMAP | {"kind": vpd.AIR, "target_kind": vpd.AIR}
    s = rscript.build_r_script(True, 22.0, 60.0, 1.0, vpd.AIR, 20.0, (0.8, 1.2), vpd.AIR, heatmap=h)
    assert 'subtitle = "Dashed contours: target Air VPD 0.8-1.2 kPa"' in s
    assert "# User-defined target range for air VPD" in s


def test_r_script_zero_boundary_only_when_it_crosses_the_leaf_grid():
    def script(kind, offset):
        h = HEATMAP | {"kind": kind, "offset": offset, "target": None}
        return rscript.build_r_script(True, 22.0, 60.0, 1.0, vpd.AIR, 22.0 + offset, None, vpd.AIR, heatmap=h)
    crossing = script(vpd.LEAF, -2.0)
    assert 'aes(z = vpd, colour = "Leaf saturation: VPD = 0 kPa"), breaks = 0' in crossing
    assert "scale_colour_manual" in crossing and "possible condensation" in crossing
    for s in (script(vpd.LEAF, 0.0), script(vpd.LEAF, 2.0), script(vpd.AIR, -2.0)):
        assert "Leaf saturation" not in s and "possible condensation" not in s
