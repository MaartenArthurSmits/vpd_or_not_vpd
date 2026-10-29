"""Playwright end-to-end tests. Selectors use accessible roles/labels and Streamlit test ids."""

import io
import re
import shutil
import subprocess

import pandas as pd
import pytest

import share
import vpd

pytestmark = pytest.mark.e2e

TIMEOUT = 30_000


def num(page, label):
    return page.get_by_role("spinbutton", name=label, exact=True)


def set_number(page, label, value):
    box = num(page, label)
    box.fill(str(value))
    box.press("Enter")


def metric(page, label):
    return page.get_by_test_id("stMetric").filter(has_text=label).first


def open_tab(page, name):
    page.get_by_role("tab", name=name).click()


def download(page, button_name, artifacts_dir, filename):
    with page.expect_download(timeout=TIMEOUT) as info:
        page.get_by_role("button", name=button_name).click()
    path = artifacts_dir / "downloads" / filename
    info.value.save_as(path)
    return path


def test_app_loads_with_default_result(page):
    assert page.title()
    page.get_by_text("Vapour Pressure Deficit calculator").first.wait_for()
    assert "1.058 kPa" in metric(page, "Air VPD").inner_text()
    for tab in ("Calculator", "VPD Heatmap", "Day/Night Experiments", "Measured Data", "Methods & References"):
        assert page.get_by_role("tab", name=tab).count() == 1


def test_changing_numeric_inputs_updates_results(page):
    set_number(page, "Air temperature (°C)", 30)
    set_number(page, "Relative humidity (%)", 50)
    expected = f"{vpd.vpd_air(30, 50):.3f} kPa"
    page.get_by_test_id("stMetric").filter(has_text="Air VPD").first.get_by_text(expected).wait_for(timeout=TIMEOUT)
    assert expected in metric(page, "Air VPD").inner_text()


def test_switching_modes_reverse_calculation_and_state_preserved(page):
    page.get_by_text(share.MODE_B, exact=True).click()
    metric(page, "Required relative humidity").get_by_text("62.18 %").wait_for(timeout=TIMEOUT)
    set_number(page, "Air temperature (°C)", 30)
    expected = f"{vpd.rh_for_air_vpd(30, 1.0):.2f} %"
    metric(page, "Required relative humidity").get_by_text(expected).wait_for(timeout=TIMEOUT)
    page.get_by_text(share.MODE_A, exact=True).click()
    page.get_by_text("Calculation mode").first.wait_for()
    assert num(page, "Air temperature (°C)").input_value().startswith("30")
    assert f"{vpd.vpd_air(30, 60):.3f} kPa" in metric(page, "Air VPD").inner_text()


def test_unattainable_target_message(page):
    page.get_by_text(share.MODE_B, exact=True).click()
    set_number(page, "Target VPD (kPa)", 5)
    page.get_by_text("Unattainable").first.wait_for(timeout=TIMEOUT)


def test_heatmap_controls(page):
    open_tab(page, "VPD Heatmap")
    chart = page.locator('[data-testid="stPlotlyChart"]:visible').first
    chart.wait_for(timeout=TIMEOUT)
    page.get_by_text("Air VPD (kPa) as a function of temperature").first.wait_for(timeout=TIMEOUT)
    page.get_by_text("Leaf VPD", exact=True).locator("visible=true").first.click()
    page.get_by_text("Leaf VPD (kPa) as a function of temperature").first.wait_for(timeout=TIMEOUT)
    page.get_by_role("combobox", name="Colour scale").click()
    page.get_by_role("option", name="Viridis").click()
    chart.wait_for()
    set_number(page, "Min temperature (°C)", 12)
    page.get_by_text("Leaf VPD (kPa) as a function of temperature").first.wait_for()


@pytest.mark.exports
def test_download_grid_csv(page, artifacts_dir):
    open_tab(page, "VPD Heatmap")
    path = download(page, "Download grid (CSV)", artifacts_dir, "vpd_grid.csv")
    df = pd.read_csv(path)
    assert {"temperature_C", "RH_percent", "VPD_air_kPa", "VPD_leaf_kPa"} <= set(df.columns)
    assert len(df) == 61 * 91 and df.notna().all().all()
    cell = df[(df.temperature_C == 22) & (df.RH_percent == 60)].iloc[0]
    assert cell["VPD_air_kPa"] == pytest.approx(vpd.vpd_air(22, 60), abs=1e-9)


@pytest.mark.exports
def test_download_heatmap_png(page, artifacts_dir):
    open_tab(page, "VPD Heatmap")
    page.get_by_role("button", name="Prepare publication-quality PNG").click()
    page.get_by_role("button", name="Download PNG").wait_for(timeout=120_000)
    path = download(page, "Download PNG", artifacts_dir, "vpd_heatmap.png")
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) > 10_000


@pytest.mark.exports
def test_download_r_script_and_reproduce(page, artifacts_dir):
    set_number(page, "Air temperature (°C)", 25)
    page.get_by_test_id("stMetric").filter(has_text="Air VPD").first.get_by_text(
        f"{vpd.vpd_air(25, 60):.3f} kPa").wait_for(timeout=TIMEOUT)
    path = download(page, "Download reproducible R script", artifacts_dir, "vpd_calculation.R")
    text = path.read_text(encoding="utf-8")
    assert "es <- function(t) 0.6108 * exp(17.27 * t / (t + 237.3))" in text
    assert "t_air  <- 25.0" in text
    expected = vpd.vpd_air(25, 60)
    assert f"# vpd_air: {expected:.6f}" in text
    if shutil.which("Rscript"):
        res = subprocess.run(["Rscript", str(path)], capture_output=True, text=True, timeout=60)
        assert res.returncode == 0, res.stderr
        m = re.search(r"^vpd_air: (\d+\.\d+)$", res.stdout, re.M)
        assert float(m.group(1)) == pytest.approx(expected, abs=1e-6)


@pytest.mark.exports
def test_download_settings_csv(page, artifacts_dir):
    path = download(page, "Download current settings and results (CSV)", artifacts_dir, "vpd_settings.csv")
    df = pd.read_csv(path)
    assert list(df.columns) == ["quantity", "value"]
    values = dict(zip(df.quantity, df.value))
    assert float(values["vpd_air"]) == pytest.approx(vpd.vpd_air(22, 60), abs=1e-9)


def test_methods_validation_section(page):
    open_tab(page, "Methods & References")
    page.get_by_text("Scientific validation").first.click()
    page.get_by_text("Largest absolute differences").first.wait_for(timeout=TIMEOUT)
    assert "kPa" in page.get_by_text("Largest absolute differences").first.inner_text()
    page.locator('[data-testid="stDataFrame"]:visible').first.wait_for(timeout=TIMEOUT)
    assert page.get_by_text("doi.org/10.1111/nph.16485").count() >= 1


@pytest.mark.exports
def test_download_validation_csv(page, artifacts_dir):
    open_tab(page, "Methods & References")
    page.get_by_text("Scientific validation").first.click()
    path = download(page, "Download VPD-vs-RH numerical results (CSV)", artifacts_dir, "vpd_vs_rh.csv")
    df = pd.read_csv(path)
    assert sorted(df.temperature_C.unique()) == [20, 25, 30]
    assert (df[df.RH_percent == 100].VPD_FAO56_kPa.abs() < 1e-12).all()


@pytest.mark.parametrize("name,size", [("desktop", {"width": 1440, "height": 900}),
                                       ("mobile", {"width": 390, "height": 844})])
def test_full_page_screenshots(browser, app_url, artifacts_dir, console_log, name, size):
    ctx = browser.new_context(viewport=size, is_mobile=(name == "mobile"), accept_downloads=True)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: console_log.append({"type": "pageerror", "text": str(e)}))
    pg.goto(app_url)
    pg.get_by_text("Calculation mode").first.wait_for(timeout=60_000)
    for tab, slug in (("Calculator", "calculator"), ("VPD Heatmap", "heatmap"),
                      ("Methods & References", "methods")):
        pg.get_by_role("tab", name=tab).click()
        pg.wait_for_timeout(1500)
        # Streamlit scrolls inside its main container, so enlarge the viewport to the content height.
        height = pg.evaluate("document.querySelector('[data-testid=\"stMain\"]').scrollHeight")
        pg.set_viewport_size({"width": size["width"], "height": min(int(height) + 80, 6000)})
        pg.wait_for_timeout(800)
        out = artifacts_dir / "screenshots" / f"{slug}-{name}.png"
        pg.screenshot(path=out, full_page=True)
        pg.set_viewport_size(size)
        assert out.stat().st_size > 5_000
    ctx.close()


def test_zz_no_unexpected_console_errors(console_log):
    """Runs last (name sorts after the others in this module)."""
    assert console_log == [], f"Unexpected browser console errors: {console_log}"
