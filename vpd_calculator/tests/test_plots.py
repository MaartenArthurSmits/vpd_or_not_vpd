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
    target = fig.data[3].contours
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
