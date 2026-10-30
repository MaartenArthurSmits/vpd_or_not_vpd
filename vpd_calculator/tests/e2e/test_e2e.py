"""Playwright end-to-end tests. Selectors use accessible roles/labels and Streamlit test ids."""

import re
import shutil
import struct
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


def choose(page, combobox_name, option):
    combo = page.get_by_role("combobox", name=combobox_name, exact=True).locator("visible=true").first
    combo.click()
    combo.fill(option)
    combo.press("Enter")


def download(page, button_name, artifacts_dir, filename):
    with page.expect_download(timeout=TIMEOUT) as info:
        page.get_by_role("button", name=button_name).click()
    path = artifacts_dir / "downloads" / filename
    info.value.save_as(path)
    return path


def fmt_range(rr):
    return f"{rr['rh_min']:.1f} - {rr['rh_max']:.1f} %"


def result(page, name="primary"):
    return page.get_by_test_id(name).first


def test_app_loads_with_default_result(page):
    assert page.title()
    page.get_by_text("Vapour Pressure Deficit calculator").first.wait_for()
    result(page).wait_for(timeout=TIMEOUT)
    assert "1.06 kPa" in result(page).inner_text()                        # 22 degC, 60 % RH, zero offset
    assert "Air VPD: 1.06 kPa" in result(page, "secondary").inner_text()
    assert page.get_by_role("tab").count() == 5
    for tab in ("Calculator", "Acceptable range", "Compare treatments", "VPD Heatmap", "Methods & References"):
        assert page.get_by_role("tab", name=tab).count() == 1


def test_changing_numeric_inputs_updates_results(page):
    set_number(page, "Air temperature (°C)", 30)
    set_number(page, "Relative humidity (%)", 50)
    expected = f"{vpd.vpd_air(30, 50):.2f} kPa"
    result(page).get_by_text(expected).wait_for(timeout=TIMEOUT)
    assert expected in result(page).inner_text()


def test_results_follow_the_slider_before_it_is_released(page):
    result(page).wait_for(timeout=TIMEOUT)
    slider = page.get_by_role("slider", name="Air temperature (°C) slider")
    box = slider.bounding_box()
    y = box["y"] + box["height"] / 2
    page.mouse.move(box["x"] + box["width"] * 22 / 45, y)
    page.mouse.down()
    page.mouse.move(box["x"] + box["width"] * 30 / 45, y, steps=8)
    temperature = float(num(page, "Air temperature (°C)").input_value())
    assert temperature > 25
    expected = f"{vpd.vpd_air(temperature, 60):.2f} kPa"
    result(page).get_by_text(expected).wait_for(timeout=2_000)             # pointer is still down
    page.mouse.up()
    page.wait_for_function(f"() => location.search.includes('t={temperature:g}')", timeout=TIMEOUT)  # committed


def test_switching_modes_reverse_calculation_and_state_preserved(page):
    page.get_by_text(share.MODE_B, exact=True).click()
    result(page, "required-rh").get_by_text("62.2%").wait_for(timeout=TIMEOUT)
    set_number(page, "Air temperature (°C)", 30)
    expected = f"{vpd.rh_for_air_vpd(30, 1.0):.1f} %"
    result(page, "required-rh").get_by_text(expected.replace(" %", "%")).wait_for(timeout=TIMEOUT)
    page.get_by_text(share.MODE_A, exact=True).click()
    expected = f"{vpd.vpd_air(30, 60):.2f} kPa"
    result(page).get_by_text(expected).wait_for(timeout=TIMEOUT)
    assert num(page, "Air temperature (°C)").input_value().startswith("30")


def test_unattainable_target_message(page):
    page.get_by_text(share.MODE_B, exact=True).click()
    set_number(page, "Target VPD (kPa)", 5)
    page.get_by_text("Unattainable").first.wait_for(timeout=TIMEOUT)


def test_day_night_target_choice_keeps_calculator_inputs(page):
    result(page).wait_for(timeout=TIMEOUT)
    assert "Day target" in page.locator(".status").first.inner_text()
    page.get_by_text("Night", exact=True).first.click()
    page.locator(".status").filter(has_text="Night target").first.wait_for(timeout=TIMEOUT)
    assert num(page, "Air temperature (°C)").input_value() == "22.0"


def test_day_and_night_sections(page):
    assert page.get_by_role("heading", name="Day", exact=True).count() == 0      # not in the Calculator tab
    open_tab(page, "Acceptable range")
    page.get_by_role("heading", name="Day", exact=True).wait_for(timeout=TIMEOUT)
    page.get_by_role("heading", name="Night", exact=True).wait_for(timeout=TIMEOUT)
    assert page.get_by_role("heading", name="Day", exact=True).count() == 1
    assert page.get_by_role("heading", name="Night", exact=True).count() == 1
    set_number(page, "Night air temperature (°C)", 15)
    expected = fmt_range(vpd.rh_range_for_vpd_range(15, 0.8, 1.2))
    metric(page, "Night RH range").get_by_text(expected).wait_for(timeout=TIMEOUT)
    assert "15.0 °C" in metric(page, "Night RH range").inner_text()
    assert "22.0 °C" in metric(page, "Day RH range").inner_text()      # day unchanged
    page.get_by_text("Condensation guidance").first.wait_for()
    open_tab(page, "Calculator")                                                  # settings survive tab changes
    open_tab(page, "Acceptable range")
    assert num(page, "Night air temperature (°C)").input_value().startswith("15")


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
    assert cell["VPD_air_kPa"] == pytest.approx(vpd.vpd_air(22, 60), abs=1e-9)   # full precision in CSV


@pytest.mark.exports
def test_download_heatmap_png_pdf_and_svg_via_matplotlib(page, artifacts_dir):
    open_tab(page, "VPD Heatmap")
    page.get_by_role("button", name="Prepare figure downloads").click()
    page.get_by_role("button", name="Download PNG").wait_for(timeout=120_000)
    png = download(page, "Download PNG", artifacts_dir, "vpd_heatmap.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 10_000
    assert struct.unpack(">II", png[16:24]) == (3000, 1950)               # 300 dpi
    pdf = download(page, "Download PDF", artifacts_dir, "vpd_heatmap.pdf").read_bytes()
    assert pdf[:5] == b"%PDF-" and len(pdf) > 5_000
    svg = download(page, "Download SVG", artifacts_dir, "vpd_heatmap.svg").read_bytes()
    assert b"<svg" in svg[:600] and b"</svg>" in svg[-20:]
    assert page.get_by_text("Server-side PNG export is not available").count() == 0


@pytest.mark.exports
def test_download_r_script_with_ggplot2_heatmap_and_reproduce(page, artifacts_dir):
    set_number(page, "Air temperature (°C)", 22.34)                         # precise decimal input
    result(page).get_by_text(f"{vpd.vpd_air(22.34, 60):.2f} kPa").wait_for(timeout=TIMEOUT)
    open_tab(page, "VPD Heatmap")
    page.get_by_text("Leaf VPD", exact=True).locator("visible=true").first.click()
    page.get_by_text("Leaf VPD (kPa) as a function of temperature").first.wait_for(timeout=TIMEOUT)
    path = download(page, "Download reproducible R script", artifacts_dir, "vpd_heatmap.R")
    text = path.read_text(encoding="utf-8")
    assert "es <- function(t) 0.6108 * exp(17.27 * t / (t + 237.3))" in text
    assert "t_air  <- 22.34" in text
    for expected in ("library(ggplot2)", "hm_t_min  <- 10.0", 'hm_kind   <- "leaf"', "breaks = unique(c(0.8, 1.2))",
                     'annotate("point", x = 22.34', 'ggsave("vpd_heatmap.png"', "dpi = 300", 'ggsave("vpd_heatmap.pdf"'):
        assert expected in text, expected
    expected_vpd = vpd.vpd_air(22.34, 60)
    assert f"# vpd_air: {expected_vpd:.6f}" in text
    if shutil.which("Rscript"):
        run_dir = artifacts_dir / "downloads" / "r_run"
        run_dir.mkdir(exist_ok=True)
        res = subprocess.run(["Rscript", str(path)], capture_output=True, text=True, timeout=300, cwd=run_dir)
        if res.returncode != 0 and "ggplot2" in res.stderr and "there is no package" in res.stderr:
            pytest.skip("ggplot2 not installed in this R")
        assert res.returncode == 0, res.stderr
        m = re.search(r"^vpd_air: (\d+\.\d+)$", res.stdout, re.M)
        assert float(m.group(1)) == pytest.approx(expected_vpd, abs=1e-6)
        assert (run_dir / "vpd_heatmap.png").read_bytes()[:4] == b"\x89PNG"
        assert (run_dir / "vpd_heatmap.pdf").read_bytes()[:5] == b"%PDF-"


def test_methods_citation_formats_and_references(page):
    open_tab(page, "Methods & References")
    page.get_by_text("How to cite this software").first.click()
    page.get_by_text("@misc{smits2026vpdcalculator").first.wait_for(timeout=TIMEOUT)
    page.get_by_text("0009-0004-1315-0822").first.wait_for()
    page.get_by_text("[Computer software]").first.wait_for()
    assert page.get_by_text("The ultimate vapor pressure deficit (VPD) guide").count() >= 1


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


@pytest.mark.exports
def test_download_validation_png_via_matplotlib(page, artifacts_dir):
    open_tab(page, "Methods & References")
    page.get_by_text("Scientific validation").first.click()
    page.get_by_role("button", name="Prepare VPD-vs-RH graph (PNG)").click()
    page.get_by_role("button", name="Download VPD-vs-RH graph (PNG)").wait_for(timeout=60_000)
    data = download(page, "Download VPD-vs-RH graph (PNG)", artifacts_dir, "vpd_vs_rh.png").read_bytes()
    assert data[:4] == b"\x89PNG" and len(data) > 10_000


@pytest.mark.parametrize("name,size", [("desktop", {"width": 1440, "height": 900}),
                                       ("mobile", {"width": 390, "height": 844})])
def test_full_page_screenshots(browser, app_url, artifacts_dir, console_log, name, size):
    ctx = browser.new_context(viewport=size, is_mobile=(name == "mobile"), accept_downloads=True)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: console_log.append({"type": "pageerror", "text": str(e)}))
    pg.goto(app_url)
    pg.get_by_text("Calculation mode").first.wait_for(timeout=60_000)
    for tab, slug in (("Calculator", "calculator"), ("Acceptable range", "daynight"), ("Compare treatments", "compare"),
                      ("VPD Heatmap", "heatmap"),
                      ("Methods & References", "methods")):
        pg.get_by_role("tab", name=tab).click()
        pg.wait_for_timeout(1500)
        # Streamlit scrolls inside its main container, so enlarge the viewport to the content height.
        height = pg.evaluate("document.querySelector('[data-testid=\"stMain\"]').scrollHeight")
        pg.set_viewport_size({"width": size["width"], "height": min(int(height) + 80, 8000)})
        pg.wait_for_timeout(800)
        out = artifacts_dir / "screenshots" / f"{slug}-{name}.png"
        pg.screenshot(path=out, full_page=True)
        pg.set_viewport_size(size)
        assert out.stat().st_size > 5_000
    ctx.close()


def test_zz_no_unexpected_console_errors(console_log):
    """Runs last (name sorts after the others in this module)."""
    assert console_log == [], f"Unexpected browser console errors: {console_log}"
