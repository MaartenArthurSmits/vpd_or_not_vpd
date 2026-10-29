import sys
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logger_data  # noqa: E402
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


def test_treatment_figure_trace_count():
    df = vpd.treatment_table(vpd.TREATMENTS, "vpd", 1.0, 0.6)
    fig = plots.treatment_figure(df)
    assert len(fig.data) == 6
    assert isinstance(fig, go.Figure)


def test_timeseries_figure():
    clean, _ = logger_data.load_logger_data(
        logger_data.example_data(), "timestamp", "air_temp_C", "RH_percent")
    fig = plots.timeseries_figure(clean, interval=(0.8, 1.2))
    assert len(fig.data) == 4
    assert len(fig.layout.shapes) == 1
