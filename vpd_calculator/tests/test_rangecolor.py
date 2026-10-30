"""Heatmap palettes and the range-anchored colour mapping shared by Plotly, Matplotlib and the R script."""

import sys
from pathlib import Path

import numpy as np
import pytest
from matplotlib import colormaps

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mpl_export  # noqa: E402
import plots  # noqa: E402
import rangecolor as rc  # noqa: E402
import rscript  # noqa: E402
import vpd  # noqa: E402

pytestmark = pytest.mark.unit

LO, HI = 0.70, 1.30


def hex_at(stops, x):
    xs = [p for p, _ in stops]
    return rc._hex([np.interp(x, xs, [rc._rgb(c)[i] for _, c in stops]) for i in range(3)])


def close(a, b, tol=2):
    return max(abs(x - y) for x, y in zip(rc._rgb(a), rc._rgb(b))) <= tol


def test_default_palette_is_the_documented_adaptation_with_its_anchor_colours():
    assert rc.DEFAULT_PALETTE == "Blue–green–red" and rc.PALETTES[0] == rc.DEFAULT_PALETTE
    lut = rc.palette_lut(rc.DEFAULT_PALETTE, 101)
    for pos, colour in rc.BREWER_ANCHORS:
        assert close(lut[round(pos * 100)], colour, 1), (pos, colour)
    assert [c for _, c in rc.BREWER_ANCHORS] == ["#08306B", "#2171B5", "#66C2A5", "#1A9850", "#66BD63", "#A6D96A",
                                                  "#FDAE61", "#D73027", "#A50026"]
    notice = (Path(__file__).resolve().parents[1] / "assets" / "colorbrewer_NOTICE.txt").read_text()
    assert "Cynthia Brewer" in notice and "Apache License, Version 2.0" in notice and "not claimed to be perceptually" in notice
    assert not (Path(__file__).resolve().parents[1] / "assets" / "roma.txt").exists()


@pytest.mark.parametrize("name", list(rc.MPL_NAMES))
def test_other_palettes_keep_their_original_colours(name):
    lut = rc.palette_lut(name, 256)
    cm = colormaps[rc.MPL_NAMES[name]]
    for i in (0, 64, 127, 128, 200, 255):
        assert close(lut[i], rc._hex(np.array(cm(i / 255)[:3]) * 255), 1)


def test_normal_range_anchors_and_data_dependent_window():
    m = rc.mapping(0.2, 3.4, LO, HI)
    assert m["anchored"] and (m["cmin"], m["cmax"]) == (0.2, 3.4)                 # covers the plotted data; no fixed window
    for v, p in ((0.2, 0), (LO, 0.4), (1.0, 0.5), (HI, 0.6), (3.4, 1.0)):
        assert rc.position(v, m) == pytest.approx(p)
    assert rc.position(0.45, m) == pytest.approx(0.2) and rc.position(2.35, m) == pytest.approx(0.8)   # continuous between anchors
    assert rc.position(-5, m) == 0 and rc.position(9, m) == 1


def test_window_extends_to_include_the_anchors_and_keeps_negative_values():
    inside = rc.mapping(0.8, 1.2, LO, HI)                                           # data inside the range
    assert inside["cmin"] == pytest.approx(LO - rc.DELTA) and inside["cmax"] == pytest.approx(HI + rc.DELTA)
    below = rc.mapping(-0.4, 2.0, LO, HI)
    assert below["cmin"] == -0.4
    far = rc.mapping(3.0, 4.0, LO, HI)                                              # target outside the plotted data
    assert far["cmin"] < LO and far["cmax"] == 4.0 and rc.position(LO, far) == pytest.approx(0.4)


def test_equal_limits_use_one_central_anchor_and_invalid_ranges_fall_back_safely():
    one = rc.mapping(0.2, 3.0, 1.0, 1.0)
    assert one["vs"] == [0.2, 1.0, 3.0] and one["ps"] == [0.0, 0.5, 1.0] and rc.position(1.0, one) == 0.5
    st = rc.stops(rc.DEFAULT_PALETTE, one)
    assert close(hex_at(st, (1.0 - 0.2) / 2.8), "#1a9850", 3)                       # green at the single target
    inv = rc.mapping(0.2, 3.0, 1.3, 0.7)
    assert not inv["anchored"] and inv["ps"] == [0.0, 1.0] and inv["cmin"] == 0.0 and inv["cmax"] == 3.0
    assert not rc.mapping(0.2, 3.0, None, None)["anchored"]
    assert rc.mapping(0.2, 3.0, 0.7, 1.3, z_max=1.0)["cmax"] == 3.0                 # manual maximum below the upper limit ignored
    assert rc.mapping(0.2, 3.0, 0.7, 1.3, z_max=2.0)["cmax"] == 2.0                 # a valid manual maximum is used


@pytest.mark.parametrize("lo,hi", [(0.70, 1.30), (0.30, 0.70), (1.0, 1.0)])
def test_default_palette_is_green_at_the_midpoint_and_the_gradient_continues_through_the_range(lo, hi):
    m = rc.mapping(-0.2, 4.0, lo, hi)
    st = rc.stops(rc.DEFAULT_PALETTE, m)
    assert [p for p, _ in st] == sorted(set(p for p, _ in st)) and st[0][0] == 0 and st[-1][0] == 1 and len(st) == 256
    x = lambda v: (v - m["cmin"]) / (m["cmax"] - m["cmin"])
    mid = hex_at(st, x((lo + hi) / 2))
    r, g, b = rc._rgb(mid)
    assert g > r and g > b and close(mid, "#1a9850", 3)
    if hi > lo:
        cols = {hex_at(st, x(v)) for v in np.linspace(lo, hi, 30)}
        assert len(cols) == 30                                                       # no constant band inside the range
        assert close(hex_at(st, x(lo)), "#66c2a5", 3) and close(hex_at(st, x(hi)), "#66bd63", 3)
    assert close(hex_at(st, 0.0), "#08306b") and close(hex_at(st, 1.0), "#a50026")


def test_upper_values_stay_distinguishable_in_auto_mode():
    m = rc.mapping(0.0, 4.5, LO, HI)
    st = rc.stops(rc.DEFAULT_PALETTE, m)
    cols = [hex_at(st, (v - m["cmin"]) / (m["cmax"] - m["cmin"])) for v in (2.0, 2.3, 3.0, 4.0, 4.5)]
    assert len(set(cols)) == 5                                                       # nothing above 2.30 kPa collapses


def test_plotly_figure_uses_the_shared_stops_ticks_and_has_no_overlay():
    fig = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, -1.0, target=(LO, HI), target_kind=vpd.LEAF, anchor=(LO, HI),
                               point=(22, 60))
    z = vpd.vpd_matrix(np.arange(10, 40.001, 0.25), np.arange(20, 100.001, 0.5), vpd.LEAF, -1.0)
    m = rc.mapping(float(z.min()), float(z.max()), LO, HI)
    h = fig.data[0]
    assert (h.zmin, h.zmax) == (m["cmin"], m["cmax"]) and [list(s) for s in rc.stops(rc.DEFAULT_PALETTE, m)] == [list(s) for s in h.colorscale]
    assert "0.70 lower limit" in h.colorbar.ticktext and "1.30 upper limit" in h.colorbar.ticktext
    assert "%{z:.2f} kPa" in h.hovertemplate
    names = [t.name for t in fig.data]
    assert not any(n and "overlay" in n for n in names) and "Target Canopy VPD 0.70-1.30 kPa" in names and "Selected" in names
    assert np.array_equal(np.asarray(h.z), z)                                         # grid and hover values unchanged
    hidden = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, -1.0, target=None, anchor=(LO, HI))      # boundaries off
    assert [list(s) for s in hidden.data[0].colorscale] == [list(s) for s in h.colorscale]
    assert not any(n and n.startswith("Target") for n in [t.name for t in hidden.data])


def test_range_moves_the_colours_and_other_palettes_actually_change_the_chart():
    a = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, -1.0, anchor=(0.7, 1.3))
    b = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, -1.0, anchor=(1.0, 1.4))
    assert a.data[0].colorscale != b.data[0].colorscale
    spec = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, -1.0, "Spectral_r", anchor=(0.7, 1.3))
    turbo = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, -1.0, "Turbo", anchor=(0.7, 1.3))
    assert spec.data[0].colorscale[0][1] == rc.palette_lut("Spectral_r")[0] and spec.data[0].colorscale != a.data[0].colorscale
    assert turbo.data[0].colorscale[0][1] == rc.palette_lut("Turbo")[0] and turbo.data[0].colorscale != spec.data[0].colorscale
    inv = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, -1.0, anchor=None)
    assert inv.data[0].zmin <= 0.0 and "lower limit" not in " ".join(getattr(inv.data[0].colorbar, "ticktext", None) or [])


def test_equal_limits_give_a_single_target_contour():
    fig = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, -1.0, target=(1.0, 1.0), target_kind=vpd.LEAF, anchor=(1.0, 1.0))
    assert [t.name for t in fig.data if t.name and t.name.startswith("Target")] == ["Target Canopy VPD 1.00 kPa"]


def test_saturation_boundary_is_a_thin_labelled_dotted_line_without_an_ordinary_zero_contour():
    fig = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, -2.0, target=(LO, HI), target_kind=vpd.LEAF, anchor=(LO, HI))
    (sat,) = [t for t in fig.data if t.name == vpd.ZERO_LABEL]
    assert vpd.ZERO_LABEL == "Saturation boundary: canopy VPD = 0 kPa"
    assert sat.line.dash == "dot" and sat.line.width <= 2 and sat.line.color == vpd.ZERO_COLOUR
    for t in fig.data:
        if isinstance(t.type, str) and t.type == "contour" and t.name is None:
            levels = np.arange(t.contours.start, t.contours.end + 1e-9, t.contours.size)
            assert not np.any(np.abs(levels) < 1e-9)
    none = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, 0.0, anchor=(LO, HI))                   # zero does not cross
    assert not any(t.name == vpd.ZERO_LABEL for t in none.data)


def test_matplotlib_export_uses_the_same_stops_and_keeps_the_saturation_boundary():
    fig = mpl_export.heatmap_mpl(10, 40, 20, 100, vpd.LEAF, -2.0, target=(LO, HI), target_kind=vpd.LEAF, anchor=(LO, HI),
                                 point=(22, 60))
    ax = fig.axes[0]
    mesh = ax.collections[0]
    z = vpd.vpd_matrix(np.arange(10, 40.001, 0.25), np.arange(20, 100.001, 0.5), vpd.LEAF, -2.0)
    m = rc.mapping(float(z.min()), float(z.max()), LO, HI)
    assert (mesh.norm.vmin, mesh.norm.vmax) == (m["cmin"], m["cmax"])
    st = rc.stops(rc.DEFAULT_PALETTE, m)
    for x in (0.0, 0.25, 0.5, 0.75, 1.0):
        got = rc._hex(np.array(mesh.cmap(x)[:3]) * 255)
        assert close(got, hex_at(st, x), 2)
    legend = [t.get_text() for t in ax.get_legend().get_texts()]
    assert "Target Canopy VPD 0.70-1.30 kPa" in legend and vpd.ZERO_LABEL in legend
    text = " ".join(" ".join(t.get_text() for t in fig.texts).replace("\\n", " ").split())
    assert rc.EXPLANATION in text and "ColorBrewer" in text
    assert len(mpl_export.to_bytes(fig, "png", 60)) > 5000


def test_r_script_embeds_the_same_palette_positions_and_limits():
    h = dict(t_min=10, t_max=40, rh_min=20, rh_max=100, kind=vpd.LEAF, offset=-2.0, colorscale="Spectral_r", contour_step=0.5,
             z_max=None, point=(22, 60), target=(LO, HI), target_kind=vpd.LEAF, anchor=(LO, HI))
    s = rscript.build_r_script(True, 22, 60, 1.0, vpd.LEAF, 20, (LO, HI), vpd.LEAF, heatmap=h)
    z = vpd.vpd_matrix(np.arange(10, 40.001, 0.25), np.arange(20, 100.001, 0.5), vpd.LEAF, -2.0)
    m = rc.mapping(float(z.min()), float(z.max()), LO, HI)
    assert f"zlim      <- c({rscript._num(m['cmin'])}, {rscript._num(m['cmax'])})" in s
    pal = next(l for l in s.split("\n") if l.startswith("pal <- c("))
    pos = next(l for l in s.split("\n") if l.startswith("pal_pos <- c("))
    assert pal.count('"#') == 256 and pos.count(",") == 255 and "scale_fill_gradientn(colours = pal, values = pal_pos" in s
    assert "setdiff(round(seq(" in s and "linewidth = 0.5, linetype = \"dotted\"" in s and "overlay" not in s
    assert rc.EXPLANATION in s and "target Canopy VPD 0.70-1.30 kPa" in s
    default = rscript.build_r_script(True, 22, 60, 1.0, vpd.LEAF, 20, (LO, HI), vpd.LEAF, heatmap=h | {"colorscale": rc.DEFAULT_PALETTE})
    assert "adapts ColorBrewer colours" in default
