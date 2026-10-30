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
ROMA = [tuple(float(x) for x in l.split()) for l in
        (Path(__file__).resolve().parents[1] / "assets" / "roma.txt").read_text().splitlines() if l.strip()]


def test_lut_is_the_complete_roma_table_reversed_and_attributed():
    assert len(ROMA) == 256 and rc.LUT == tuple(reversed(ROMA))
    assert rc.LOW_COLOUR == "#0a3198" or rc.LUT[0][2] > 0.55 and rc.LUT[0][0] < 0.05                # deep blue
    assert rc.LUT[-1][0] > 0.45 and rc.LUT[-1][1] < 0.1 and rc.LUT[-1][2] < 0.01                      # dark brick red
    mid = rc.LUT[127]
    assert mid[1] > mid[0] and mid[1] > mid[2] and mid[1] > 0.9                                         # pale green
    notice = (Path(__file__).resolve().parents[1] / "assets" / "roma_NOTICE.txt").read_text()
    assert "zenodo.8035877" in notice and "MIT License" in notice and "Fabio Crameri" in notice


@pytest.mark.parametrize("lo,hi", [(0.70, 1.30), (0.30, 0.70), (1.00, 1.40), (1.0, 1.0)])
def test_colour_window_is_fixed_in_kpa_and_centred_on_the_range_midpoint(lo, hi):
    zmin, zmax = rc.domain(lo, hi)
    assert (zmin + zmax) / 2 == pytest.approx((lo + hi) / 2) and zmax - zmin == pytest.approx(hi - lo + 2 * rc.MARGIN)
    mid = rc.colour_for((lo + hi) / 2, lo, hi)
    assert mid == pytest.approx(tuple((a + b) / 2 for a, b in zip(rc.LUT[127], rc.LUT[128])), abs=1e-12)
    assert rc.colour_for(zmin - 5, lo, hi) == pytest.approx(rc.LUT[0]) and rc.colour_for(zmax + 5, lo, hi) == pytest.approx(rc.LUT[-1])


def test_gradient_continues_through_the_range_with_no_constant_band():
    cols = [rc.colour_for(v, LO, HI) for v in np.linspace(LO, HI, 50)]
    assert len({c for c in cols}) == 50                                       # every value inside the range differs
    assert rc.colour_for(0.40, LO, HI) != rc.colour_for(0.40, 0.30, 0.70)     # moving the range moves the colours


def test_plotly_uses_the_table_unchanged_and_the_same_window_for_any_axes():
    wide = plots.heatmap_figure(5, 45, 5, 100, vpd.LEAF, -1.0, target=(LO, HI), target_kind=vpd.LEAF, range_colour=True)
    narrow = plots.heatmap_figure(15, 30, 30, 90, vpd.LEAF, -1.0, target=(LO, HI), target_kind=vpd.LEAF, range_colour=True)
    for fig in (wide, narrow):
        h = fig.data[0]
        assert (h.zmin, h.zmax) == rc.domain(LO, HI) and [s[1] for s in h.colorscale] == list(rc.HEX) and len(h.colorscale) == 256
        assert not any(t.name and "(overlay)" in t.name for t in fig.data)
        assert "0.70 lower limit" in h.colorbar.ticktext and "1.30 upper limit" in h.colorbar.ticktext
        assert "%{z:.2f} kPa" in h.hovertemplate
    names = [t.name for t in wide.data]
    assert "Target Canopy VPD 0.70-1.30 kPa" in names and not any(n and "green" in n for n in names)


def test_single_value_target_invalid_range_air_view_and_highlight_off_keep_their_behaviour():
    one = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, -1.0, target=(1.0, 1.0), target_kind=vpd.LEAF, range_colour=True)
    assert [t.name for t in one.data if t.name and t.name.startswith("Target")] == ["Target Canopy VPD 1.00 kPa"]
    assert (one.data[0].zmin, one.data[0].zmax) == rc.domain(1.0, 1.0)
    air = plots.heatmap_figure(10, 40, 20, 100, vpd.AIR, -1.0, target=(LO, HI), target_kind=vpd.LEAF, range_colour=True)
    assert air.data[0].zmax != rc.domain(LO, HI)[1]
    off = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, -1.0, "Viridis", target=None, range_colour=True)
    assert off.data[0].colorscale[0][1] == "#440154"


def test_matplotlib_export_uses_the_same_table_and_keeps_the_zero_boundary():
    fig = mpl_export.heatmap_mpl(10, 40, 20, 100, vpd.LEAF, -2.0, target=(LO, HI), target_kind=vpd.LEAF, range_colour=True,
                                 point=(22, 60))
    ax = fig.axes[0]
    mesh = ax.collections[0]
    assert (mesh.norm.vmin, mesh.norm.vmax) == rc.domain(LO, HI)
    for i in (0, 64, 127, 128, 200, 255):
        assert tuple(mesh.cmap(i)[:3]) == pytest.approx(rc.LUT[i], abs=1e-6)
    legend = [t.get_text() for t in ax.get_legend().get_texts()]
    assert "Target Canopy VPD 0.70-1.30 kPa" in legend and vpd.ZERO_LABEL in legend
    assert rc.EXPLANATION in " ".join(" ".join(t.get_text() for t in fig.texts).replace("\\n", " ").split())
    assert len(mpl_export.to_bytes(fig, "png", 60)) > 5000


def test_r_script_embeds_the_same_256_colours_and_limits():
    h = dict(t_min=10, t_max=40, rh_min=20, rh_max=100, kind=vpd.LEAF, offset=-1.0, colorscale="Viridis", contour_step=0.5,
             z_max=None, point=(22, 60), target=(LO, HI), target_kind=vpd.LEAF, range_colour=True)
    s = rscript.build_r_script(True, 22, 60, 1.0, vpd.LEAF, 21, (LO, HI), vpd.LEAF, heatmap=h)
    zmin, zmax = rc.domain(LO, HI)
    assert "scale_fill_gradientn(colours = roma_r" in s and f"zlim      <- c({rscript._num(zmin)}, {rscript._num(zmax)})" in s
    line = next(l for l in s.split("\n") if l.startswith("roma_r <- c("))
    assert line.count('"#') == 256 and f'"{rc.HEX[0]}"' in line and f'"{rc.HEX[-1]}"' in line and "zenodo.8035877" in s
    assert rc.EXPLANATION in s and "target Canopy VPD 0.70-1.30 kPa" in s and "scale_fill_viridis_c" not in s
    plain = rscript.build_r_script(True, 22, 60, 1.0, vpd.LEAF, 21, (LO, HI), vpd.LEAF, heatmap=h | {"range_colour": False})
    assert "scale_fill_viridis_c" in plain and "roma_r" not in plain
