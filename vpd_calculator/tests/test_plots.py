import sys
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mpl_export  # noqa: E402
import plots  # noqa: E402
import vpd  # noqa: E402

pytestmark = pytest.mark.unit


def kinds(fig):
    return [type(t).__name__ for t in fig.data]


def test_heatmap_base_traces_and_axes():
    fig = plots.heatmap_figure(10, 40, 20, 100)
    assert kinds(fig) == ["Heatmap", "Contour"]
    assert list(fig.layout.xaxis.range) == [10, 40]
    assert list(fig.layout.yaxis.range) == [20, 100]
    assert "Air VPD" in fig.layout.title.text


def test_heatmap_values_match_calculation():
    fig = plots.heatmap_figure(10, 40, 20, 100, vpd.AIR)
    hm = fig.data[0]
    i = int(np.argmin(np.abs(np.asarray(hm.y) - 60)))
    j = int(np.argmin(np.abs(np.asarray(hm.x) - 22)))
    assert hm.z[i][j] == pytest.approx(vpd.vpd_air(22, 60), abs=1e-9)


def test_heatmap_leaf_offset_changes_values():
    air = plots.heatmap_figure(10, 40, 20, 100, vpd.AIR, offset=-2).data[0].z
    leaf = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, offset=-2).data[0].z
    assert np.all(np.asarray(leaf) < np.asarray(air))


def test_heatmap_target_and_point_layers():
    fig = plots.heatmap_figure(10, 40, 20, 100, point=(22, 60), target=(0.8, 1.2))
    assert kinds(fig) == ["Heatmap", "Heatmap", "Contour", "Contour", "Scatter"]
    target = target_trace(fig).contours
    assert target.start == 0.8 and target.end == 1.2
    mask = np.asarray(fig.data[1].z, dtype=float)
    assert np.isnan(mask).any() and (mask[~np.isnan(mask)] == 1).all()


def test_heatmap_point_outside_range_is_omitted():
    fig = plots.heatmap_figure(10, 40, 20, 100, point=(50, 60))
    assert "Scatter" not in kinds(fig)


def test_vpd_vs_rh_figure():
    rr = vpd.rh_range_for_vpd_range(22, 0.8, 1.2)
    fig = plots.vpd_vs_rh_figure(22, -2, vpd.AIR, rh_range=rr, point_rh=60)
    assert len(fig.data) == 3
    assert len(fig.layout.shapes) >= 1  # shaded RH range


# ---- Matplotlib (Agg) static export: no browser needed ----------------------------------
def png_size(data: bytes):
    import struct
    return struct.unpack(">II", data[16:24])


def test_mpl_heatmap_png_and_pdf_without_browser():
    fig = mpl_export.heatmap_mpl(10, 40, 10, 100, vpd.LEAF, -2.0, point=(22, 60), target=(0.8, 1.2))
    png = mpl_export.to_bytes(fig, "png", 100)
    pdf = mpl_export.to_bytes(fig, "pdf")
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 10_000
    assert pdf[:5] == b"%PDF-" and len(pdf) > 5_000


def test_mpl_png_is_300_dpi_publication_size():
    fig = mpl_export.heatmap_mpl(10, 40, 10, 100, figsize=(10.0, 6.5))
    assert png_size(mpl_export.to_bytes(fig, "png", 300)) == (3000, 1950)


def test_mpl_heatmap_axes_labels_and_limits():
    fig = mpl_export.heatmap_mpl(12, 38, 20, 90, vpd.AIR)
    ax = fig.axes[0]
    assert ax.get_xlabel() == "Air temperature (°C)" and ax.get_ylabel() == "Relative humidity (%)"
    assert ax.get_xlim() == (12, 38) and ax.get_ylim() == (20, 90)
    assert "Air VPD" in ax.get_title()
    assert any("VPD" in a.get_ylabel() for a in fig.axes)          # colourbar label


def test_mpl_selected_point_only_inside_range():
    inside = mpl_export.heatmap_mpl(10, 40, 10, 100, point=(22, 60))
    outside = mpl_export.heatmap_mpl(10, 40, 10, 100, point=(50, 60))
    assert len(inside.axes[0].lines) == 1 and len(outside.axes[0].lines) == 0


def test_mpl_reference_figure_png():
    import validation
    curves = validation.reference_curves([20, 25, 30])
    fig = mpl_export.reference_mpl(curves, show_johnston=True)
    assert len(fig.axes[0].lines) == 6
    assert mpl_export.to_bytes(fig, "png", 100)[:4] == b"\x89PNG"


def test_interface_plots_use_one_decimal_hover():
    fig = plots.heatmap_figure(10, 40, 20, 100, point=(22, 60))
    assert ":.1f} kPa" in fig.data[0].hovertemplate and ":.1f} °C" in fig.data[0].hovertemplate


# ---- Target kind is independent of the heatmap's colour kind -------------------------------------
# Acceptance point: 22 degC, RH 60 %, leaf offset -2 degC -> air VPD 1.05757 kPa, leaf VPD 0.75192 kPa.
T_AIR, RH, OFFSET, TARGET = 22.0, 60.0, -2.0, (0.8, 1.2)
BOTH = [vpd.AIR, vpd.LEAF]


def target_trace(fig):
    """The dashed target contour (not the overlay, the ordinary contours or the zero-VPD line)."""
    (trace,) = [t for t in fig.data if type(t).__name__ == "Contour" and (t.name or "").startswith("Target")]
    return trace


def test_acceptance_point_values():
    assert vpd.vpd_air(T_AIR, RH) == pytest.approx(1.05757, abs=1e-5)
    assert vpd.vpd_leaf(T_AIR, RH, T_AIR + OFFSET) == pytest.approx(0.75192, abs=1e-5)


def _cell(fig_trace, x=T_AIR, y=RH):
    i = int(np.argmin(np.abs(np.asarray(fig_trace.y) - y)))
    j = int(np.argmin(np.abs(np.asarray(fig_trace.x) - x)))
    return i, j


@pytest.mark.parametrize("hm_kind", BOTH)
@pytest.mark.parametrize("target_kind,inside", [(vpd.AIR, True), (vpd.LEAF, False)])
def test_plotly_target_follows_target_kind_on_both_heatmaps(hm_kind, target_kind, inside):
    fig = plots.heatmap_figure(10, 40, 20, 100, hm_kind, OFFSET, point=(T_AIR, RH), target=TARGET,
                               target_kind=target_kind)
    colours, mask, target_contour = fig.data[0], fig.data[1], target_trace(fig)
    i, j = _cell(mask)
    assert (not np.isnan(mask.z[i][j])) is inside
    # colours still follow the heatmap's own VPD type
    expected_colour = vpd.vpd_air(T_AIR, RH) if hm_kind == vpd.AIR else vpd.vpd_leaf(T_AIR, RH, T_AIR + OFFSET)
    assert colours.z[i][j] == pytest.approx(expected_colour, abs=1e-9)
    # dashed contours are drawn on the target-kind field
    expected_target = vpd.vpd_air(T_AIR, RH) if target_kind == vpd.AIR else vpd.vpd_leaf(T_AIR, RH, T_AIR + OFFSET)
    assert target_contour.z[i][j] == pytest.approx(expected_target, abs=1e-9)
    assert "Air VPD" in target_contour.name if target_kind == vpd.AIR else "Canopy VPD" in target_contour.name


@pytest.mark.parametrize("target_kind", BOTH)
def test_plotly_target_region_is_identical_for_both_heatmap_views(target_kind):
    figs = [plots.heatmap_figure(10, 40, 20, 100, k, OFFSET, target=TARGET, target_kind=target_kind) for k in BOTH]
    m0, m1 = (np.asarray(f.data[1].z, dtype=float) for f in figs)
    assert np.array_equal(np.isnan(m0), np.isnan(m1))
    assert np.array_equal(np.asarray(target_trace(figs[0]).z), np.asarray(target_trace(figs[1]).z))


def test_plotly_target_kind_defaults_to_heatmap_kind():
    fig = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, OFFSET, target=TARGET)
    explicit = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, OFFSET, target=TARGET, target_kind=vpd.LEAF)
    assert np.array_equal(np.asarray(target_trace(fig).z), np.asarray(target_trace(explicit).z))


def _mpl_target_artists(fig):
    """Filled target region (white, alpha 0.35) and dashed target contours of a heatmap_mpl figure."""
    ax = fig.axes[0]
    filled = [c for c in ax.collections if c.get_alpha() == 0.35]
    dashed = [c for c in ax.collections if c.get_linewidths() is not None and len(c.get_linewidths())
              and c.get_linewidths()[0] == 2.0]
    assert len(filled) == 1 and len(dashed) == 1
    return filled[0], dashed[0]


@pytest.mark.parametrize("hm_kind", BOTH)
@pytest.mark.parametrize("target_kind,inside", [(vpd.AIR, True), (vpd.LEAF, False)])
def test_mpl_target_follows_target_kind_on_both_heatmaps(hm_kind, target_kind, inside):
    fig = mpl_export.heatmap_mpl(10, 40, 10, 100, hm_kind, OFFSET, point=(T_AIR, RH), target=TARGET,
                                 target_kind=target_kind)
    filled, _ = _mpl_target_artists(fig)
    assert any(p.contains_point((T_AIR, RH)) for p in filled.get_paths()) is inside
    legend_text = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
    label = "Air VPD" if target_kind == vpd.AIR else "Canopy VPD"
    assert any(f"Target {label} 0.8-1.2 kPa" in t for t in legend_text)


@pytest.mark.parametrize("target_kind", BOTH)
def test_mpl_target_geometry_is_identical_for_both_heatmap_views(target_kind):
    arts = [_mpl_target_artists(mpl_export.heatmap_mpl(10, 40, 10, 100, k, OFFSET, target=TARGET,
                                                       target_kind=target_kind)) for k in BOTH]
    for a, b in zip(arts[0], arts[1]):
        assert len(a.get_paths()) == len(b.get_paths())
        for pa, pb in zip(a.get_paths(), b.get_paths()):
            assert np.allclose(pa.vertices, pb.vertices)


@pytest.mark.parametrize("target_kind", BOTH)
def test_mpl_png_and_pdf_render_with_mixed_kinds(target_kind):
    fig = mpl_export.heatmap_mpl(10, 40, 10, 100, vpd.AIR, OFFSET, point=(T_AIR, RH), target=TARGET,
                                 target_kind=target_kind)
    assert mpl_export.to_bytes(fig, "png", 100)[:8] == b"\x89PNG\r\n\x1a\n"
    assert mpl_export.to_bytes(fig, "pdf")[:5] == b"%PDF-"


# ---- single-value targets (lower limit == upper limit): one contour, no shaded band ---------------
POINT = (1.0, 1.0)


def test_target_label_helper_single_value_and_range():
    assert vpd.target_label(vpd.AIR, 1.0, 1.0) == "Target Air VPD 1.0 kPa"
    assert vpd.target_label(vpd.LEAF, 1.0, 1.0) == "Target Canopy VPD 1.0 kPa"
    assert vpd.target_label(vpd.AIR, 0.8, 1.2) == "Target Air VPD 0.8-1.2 kPa"
    assert vpd.is_point_target(1.0, 1.0) and not vpd.is_point_target(0.8, 1.2)
    assert [vpd.classify_wording(p) for p in ("below", "inside", "above")] == [
        "below target", "at target", "above target"]


@pytest.mark.parametrize("target_kind,label", [(vpd.AIR, "Target Air VPD 1.0 kPa"),
                                                (vpd.LEAF, "Target Canopy VPD 1.0 kPa")])
def test_plotly_single_target_has_one_contour_and_no_band(target_kind, label):
    fig = plots.heatmap_figure(10, 40, 20, 100, vpd.AIR, OFFSET, point=(T_AIR, RH), target=POINT,
                               target_kind=target_kind)
    assert kinds(fig) == ["Heatmap", "Contour", "Contour", "Scatter"]      # no shaded overlay heatmap
    contour = fig.data[2]
    assert contour.contours.start == contour.contours.end == 1.0
    assert contour.name == label and contour.showlegend
    assert all("(overlay)" not in (t.name or "") for t in fig.data)


def test_plotly_range_target_still_has_overlay_and_range_label():
    fig = plots.heatmap_figure(10, 40, 20, 100, vpd.AIR, OFFSET, target=TARGET, target_kind=vpd.AIR)
    assert kinds(fig) == ["Heatmap", "Heatmap", "Contour", "Contour"]
    assert fig.data[1].name == "Target Air VPD 0.8-1.2 kPa (overlay)"
    assert target_trace(fig).name == "Target Air VPD 0.8-1.2 kPa"


def test_plotly_single_target_contour_is_drawn_at_the_value():
    fig = plots.heatmap_figure(10, 40, 20, 100, vpd.LEAF, OFFSET, target=POINT, target_kind=vpd.AIR)
    z = np.asarray(target_trace(fig).z)
    assert z.min() < 1.0 < z.max()                       # the 1.0 kPa level crosses the grid


@pytest.mark.parametrize("target_kind,label", [(vpd.AIR, "Target Air VPD 1.0 kPa"),
                                                (vpd.LEAF, "Target Canopy VPD 1.0 kPa")])
def test_mpl_single_target_is_one_contour_without_filled_band(target_kind, label):
    fig = mpl_export.heatmap_mpl(10, 40, 10, 100, vpd.AIR, OFFSET, point=(T_AIR, RH), target=POINT,
                                 target_kind=target_kind)
    ax = fig.axes[0]
    assert not [c for c in ax.collections if c.get_alpha() == 0.35]          # no shaded band
    dashed = [c for c in ax.collections if len(c.get_linewidths()) and c.get_linewidths()[0] == 2.0]
    assert len(dashed) == 1 and list(dashed[0].levels) == [1.0]                # exactly one level
    assert label in [t.get_text() for t in ax.get_legend().get_texts()]
    assert mpl_export.to_bytes(fig, "png", 100)[:8] == b"\x89PNG\r\n\x1a\n"
    assert mpl_export.to_bytes(fig, "pdf")[:5] == b"%PDF-"


def test_vpd_vs_rh_single_target_is_a_line_not_a_band():
    rr = vpd.rh_range_for_vpd_range(22, 1.0, 1.0)
    assert rr["rh_min"] == rr["rh_max"]
    fig = plots.vpd_vs_rh_figure(22, 0, vpd.AIR, rh_range=rr, point_rh=60)
    assert [s.type for s in fig.layout.shapes].count("rect") == 0
    assert any(a.text == "target RH" for a in fig.layout.annotations)


# ---- leaf saturation (VPD = 0) boundary ----------------------------------------------------------------
ZERO = "Leaf saturation: VPD = 0 kPa"


def test_plotly_zero_boundary_only_on_leaf_heatmaps_where_it_crosses():
    crossing = plots.heatmap_figure(10, 40, 10, 100, vpd.LEAF, -2.0, target=TARGET, target_kind=vpd.AIR)
    zero = [t for t in crossing.data if t.name == ZERO]
    assert len(zero) == 1 and zero[0].showlegend and zero[0].contours.start == zero[0].contours.end == 0.0
    assert zero[0].line.color != "black"                                  # distinct from target/ordinary contours
    assert np.min(crossing.data[0].z) < 0                                 # negative values are preserved
    for fig in (plots.heatmap_figure(10, 40, 10, 100, vpd.LEAF, 0.0),     # touches only the 100 % RH edge
                plots.heatmap_figure(10, 40, 10, 100, vpd.LEAF, 2.0),     # entirely positive
                plots.heatmap_figure(10, 40, 10, 100, vpd.AIR, -2.0)):    # air heatmaps unchanged
        assert all(t.name != ZERO for t in fig.data)


def _mpl_zero_artists(fig):
    return [c for c in fig.axes[0].collections if len(c.get_linewidths()) and abs(c.get_linewidths()[0] - 3.2) < 1e-9]


def test_mpl_zero_boundary_drawn_only_when_crossing():
    crossing = mpl_export.heatmap_mpl(10, 40, 10, 100, vpd.LEAF, -2.0, point=(T_AIR, RH))
    assert len(_mpl_zero_artists(crossing)) == 1
    assert ZERO in [t.get_text() for t in crossing.axes[0].get_legend().get_texts()]
    assert "possible condensation" in crossing.get_supxlabel()
    assert mpl_export.to_bytes(crossing, "png", 80)[:4] == b"\x89PNG" and mpl_export.to_bytes(crossing, "pdf")[:5] == b"%PDF-"
    for fig in (mpl_export.heatmap_mpl(10, 40, 10, 100, vpd.LEAF, 0.0),
                mpl_export.heatmap_mpl(10, 40, 10, 100, vpd.LEAF, 2.0),
                mpl_export.heatmap_mpl(10, 40, 10, 100, vpd.AIR, -2.0)):
        assert _mpl_zero_artists(fig) == []
        assert "possible condensation" not in fig.get_supxlabel()
