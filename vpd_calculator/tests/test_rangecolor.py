"""Range-based heatmap colours: one specification, used by Plotly, Matplotlib and the R script."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mpl_export  # noqa: E402
import plots  # noqa: E402
import rangecolor as rc  # noqa: E402
import rscript  # noqa: E402
import vpd  # noqa: E402

pytestmark = pytest.mark.unit

LO, HI = 0.70, 1.30


@pytest.mark.parametrize("value,colour", [
    (0.70, rc.GREEN), (1.30, rc.GREEN), (1.00, rc.GREEN),                  # inclusive boundaries and inside
    (0.60, rc.NEAR_WHITE), (1.40, rc.NEAR_WHITE),                            # 0.10 away
    (0.50, rc.YELLOW), (1.50, rc.YELLOW),                                    # 0.20
    (0.40, rc.ORANGE), (1.60, rc.ORANGE),                                    # 0.30
    (0.30, rc.RED), (1.70, rc.RED),                                          # 0.40
    (-0.30, rc.DEEP_RED), (2.30, rc.DEEP_RED), (5.0, rc.DEEP_RED), (-2.0, rc.DEEP_RED),   # 1.00 away or more
])
def test_example_colours_for_the_0_70_to_1_30_range(value, colour):
    assert rc.colour_for(value, LO, HI) == colour


def test_outside_colours_interpolate_smoothly_and_green_stays_inside():
    assert rc.colour_for(0.65, LO, HI) == rc.NEAR_WHITE                      # within 0.10 of the range
    mid = rc.colour_for(0.55, LO, HI)                                        # between near-white and yellow
    assert mid not in (rc.NEAR_WHITE, rc.YELLOW)
    greens = [v for v in np.linspace(-1, 3, 4001) if rc.colour_for(float(v), LO, HI) == rc.GREEN]
    assert min(greens) >= LO - 1e-9 and max(greens) <= HI + 1e-9


def sample(stops, pos):
    xs = [p for p, _ in stops]
    chans = [[rc._rgb(c)[i] for _, c in stops] for i in range(3)]
    return rc._hex([np.interp(pos, xs, ch) for ch in chans])


@pytest.mark.parametrize("lo,hi", [(0.70, 1.30), (0.30, 0.70), (1.00, 1.40)])
def test_plotly_colour_stops_reproduce_the_mapping_in_fixed_kpa(lo, hi):
    zmin, zmax = rc.domain(lo, hi)
    stops = rc.colorscale(lo, hi)
    assert [p for p, _ in stops] == sorted(set(p for p, _ in stops)) and stops[0][0] == 0.0 and stops[-1][0] == 1.0
    for v in np.linspace(zmin, zmax, 400):
        if min(abs(v - lo), abs(v - hi)) < 1e-4:
            continue                                                          # the green/near-white edge is EPS wide
        got, want = rc._rgb(sample(stops, (v - zmin) / (zmax - zmin))), rc._rgb(rc.colour_for(float(v), lo, hi))
        assert max(abs(a - b) for a, b in zip(got, want)) <= 1, (v, got, want)


def test_changing_the_target_moves_the_green_region_and_axes_do_not_change_colours():
    assert rc.colour_for(0.40, 0.30, 0.70) == rc.GREEN and rc.colour_for(0.40, LO, HI) == rc.ORANGE
    assert rc.colour_for(1.00, 1.00, 1.40) == rc.GREEN and rc.colour_for(1.00, LO, HI) == rc.GREEN
    colour_a = rc.colour_for(1.55, LO, HI)
    wide = plots.heatmap_figure(5, 45, 5, 100, vpd.LEAF, -1.0, target=(LO, HI), target_kind=vpd.LEAF, range_colour=True)
    narrow = plots.heatmap_figure(15, 30, 30, 90, vpd.LEAF, -1.0, target=(LO, HI), target_kind=vpd.LEAF, range_colour=True)
    for fig in (wide, narrow):
        h = fig.data[0]
        assert (h.zmin, h.zmax) == rc.domain(LO, HI) and [list(s) for s in rc.colorscale(LO, HI)] == [list(s) for s in h.colorscale]
    assert colour_a == rc.colour_for(1.55, LO, HI)


def test_single_value_target_has_no_green_and_invalid_or_air_views_keep_the_numerical_palette():
    assert rc.GREEN not in [c for _, c in rc.vpd_stops(1.0, 1.0)] and rc.colour_for(1.0, 1.0, 1.0) == rc.NEAR_WHITE
    fig = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, -1.0, target=(1.0, 1.0), target_kind=vpd.LEAF, range_colour=True)
    assert not any(t.name and "(overlay)" in t.name for t in fig.data)
    assert [t.name for t in fig.data if t.name and t.name.startswith("Target")] == ["Target Canopy VPD 1.00 kPa"]
    air = plots.heatmap_figure(10, 40, 20, 100, vpd.AIR, -1.0, target=(LO, HI), target_kind=vpd.LEAF, range_colour=True)
    assert air.data[0].colorscale != tuple(tuple(s) for s in rc.colorscale(LO, HI)) and air.data[0].zmax != rc.domain(LO, HI)[1]
    off = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, -1.0, "Viridis", target=None, range_colour=True)
    assert off.data[0].zmin != rc.domain(LO, HI)[0] and off.data[0].colorscale[0][1] == "#440154"


def test_plotly_range_figure_details():
    fig = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, -1.0, target=(LO, HI), target_kind=vpd.LEAF, range_colour=True,
                               point=(22, 60))
    h = fig.data[0]
    assert "%{z:.2f} kPa" in h.hovertemplate and "0.70 lower limit" in h.colorbar.ticktext and "1.30 upper limit" in h.colorbar.ticktext
    names = [t.name for t in fig.data]
    assert not any(n and "(overlay)" in n for n in names) and "Target Canopy VPD 0.70-1.30 kPa" in names and "Selected" in names
    assert {"Within range (green)", "Below range: VPD under the lower limit", "Above range: VPD over the upper limit"} <= set(names)
    assert "Canopy VPD: 0.90 kPa" in fig.data[-1].hovertemplate                          # selected-point value, 2 decimals


def test_matplotlib_export_uses_the_same_stops_and_zero_boundary_survives():
    fig = mpl_export.heatmap_mpl(10, 40, 20, 100, vpd.LEAF, -2.0, target=(LO, HI), target_kind=vpd.LEAF, range_colour=True,
                                 point=(22, 60))
    ax = fig.axes[0]
    mesh = ax.collections[0]
    assert (mesh.norm.vmin, mesh.norm.vmax) == rc.domain(LO, HI)
    cmap = mesh.cmap
    zmin, zmax = rc.domain(LO, HI)
    for v, want in ((1.0, rc.GREEN), (0.5, rc.YELLOW), (1.7, rc.RED), (-0.3, rc.DEEP_RED)):
        got = tuple(round(255 * x) for x in cmap((v - zmin) / (zmax - zmin))[:3])
        assert max(abs(a - b) for a, b in zip(got, rc._rgb(want))) <= 2
    text = " ".join(t.get_text() for t in fig.texts)
    assert rc.EXPLANATION in text and "Target Canopy VPD 0.70-1.30 kPa" in [t.get_text() for t in ax.get_legend().get_texts()]
    assert vpd.ZERO_LABEL in [t.get_text() for t in ax.get_legend().get_texts()]
    assert len(mpl_export.to_bytes(fig, "png", 60)) > 5000


def test_r_script_uses_the_same_stops_and_limits():
    h = dict(t_min=10, t_max=40, rh_min=20, rh_max=100, kind=vpd.LEAF, offset=-1.0, colorscale="Viridis", contour_step=0.5,
             z_max=None, point=(22, 60), target=(LO, HI), target_kind=vpd.LEAF, range_colour=True)
    s = rscript.build_r_script(True, 22, 60, 1.0, vpd.LEAF, 21, (LO, HI), vpd.LEAF, heatmap=h)
    zmin, zmax = rc.domain(LO, HI)
    assert "scale_fill_gradientn" in s and f"zlim      <- c({rscript._num(zmin)}, {rscript._num(zmax)})" in s
    for pos, colour in rc.colorscale(LO, HI):
        assert f'"{colour}"' in s and repr(pos) in s
    assert rc.EXPLANATION in s and "target Canopy VPD 0.70-1.30 kPa" in s and "scale_fill_viridis_c" not in s
    plain = rscript.build_r_script(True, 22, 60, 1.0, vpd.LEAF, 21, (LO, HI), vpd.LEAF, heatmap=h | {"range_colour": False})
    assert "scale_fill_viridis_c" in plain and "scale_fill_gradientn" not in plain
