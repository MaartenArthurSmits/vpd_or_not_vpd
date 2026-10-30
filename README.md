# VPD Calculator

[![tests](https://github.com/MaartenArthurSmits/vpd_or_not_vpd/actions/workflows/tests.yml/badge.svg)](https://github.com/MaartenArthurSmits/vpd_or_not_vpd/actions/workflows/tests.yml)
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://vpd-or-not-vpd.streamlit.app/)

An interactive vapour pressure deficit (VPD) calculator for controlled-environment plant research,
built with Python, Streamlit and Plotly.

**Use it online:** https://vpd-or-not-vpd.streamlit.app/

## Features

Five tabs: **Calculator**, **Acceptable range**, **Compare treatments**, **VPD Heatmap**, **Methods & References**.

- **Bidirectional calculator:** VPD from temperature and RH, or the RH required for a target air or leaf VPD.
- **Leaf temperature:** an offset (illustrative scenarios 0, -1, -2, +1, +2 °C or custom) or a measured value, with an
  explanation of air versus leaf VPD.
- **Acceptable range:** one range preset (published starting ranges with sources) sets the Day and Night VPD limits, which
  can then be edited independently. The Calculator and this tab show the same result and range bar.
- **Compare treatments:** an editable table of treatments (air temperature, RH, leaf offset) with leaf temperature,
  air VPD and leaf VPD for each valid row, flagged condensation risk and a CSV download.
- **Heatmap:** interactive temperature x RH plot (air or leaf VPD) with contours, target range and selected point.
- **Exports:** grid CSV, treatment CSV, publication-quality heatmap PNG (300 dpi) and PDF rendered with Matplotlib
  (no browser needed), and a reproducible R script that recreates the calculation and the heatmap with ggplot2.
- **Shareable link:** the Acceptable range tab has a Copy link button; the link restores calculator, Day/Night and
  heatmap settings (comparison treatments are not included).
- **Scientific validation** against FAO-56 tables and an alternative published equation (Methods & References).

Values are displayed with one decimal place; calculations, validation tables and CSV exports keep full precision.

**About the presets.** Growth-stage VPD ranges and the typical leaf-offset note come from a grower guide
(Koverda, 2020; Pulse Grow, https://pulsegrow.com/blogs/learn/vpd), which also inspired the interface. Pulse Grow is not
the source of the equations (FAO-56 is), and the ranges are illustrative, not scientifically validated
species-specific optima.

## Run locally

```powershell
cd vpd_calculator
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

The exported R script needs R with the `ggplot2` package (optional: `metR` for contour labels).

## Calculation API (local, experimental)

A small FastAPI service exposes the forward calculation. It is **local only and not yet publicly deployed**;
reverse calculation, graph endpoints and hosting are not implemented.

```powershell
cd vpd_calculator
pip install -r requirements-api.txt
uvicorn api:app --reload          # interactive docs: http://127.0.0.1:8000/docs
```

```powershell
curl -X POST http://127.0.0.1:8000/v1/calculate -H "Content-Type: application/json" `
  -d '{"air_temperature_c": 22, "relative_humidity_percent": 60, "measured_leaf_temperature_c": 20}'
```

Give either `leaf_temperature_offset_c` or `measured_leaf_temperature_c`, not both (neither means zero offset). The
response has `results` (leaf temperature, air and leaf VPD, saturation and actual vapour pressures, in °C and kPa, at
full precision), `possible_condensation` (true when leaf VPD is negative), warnings and the equation source (FAO-56
Eq. 11). Inputs use the same limits as the calculator.

## Testing

From `vpd_calculator/`:

```powershell
pip install -r requirements-dev.txt
python -m playwright install chromium     # one-off, for browser tests

python -m pytest -m "science or unit"      # scientific + unit tests
python -m pytest -m apptest                # Streamlit AppTest interaction tests
python -m pytest -m "e2e and not exports"  # Playwright browser tests (starts a local server)
python -m pytest -m exports                # export-file validation (CSV, PNG, PDF, R script)
python -m pytest                           # all
```

R-script tests run when `Rscript` (and, for the heatmap, `ggplot2`) is installed; otherwise they are skipped.
Screenshots (desktop and mobile), downloaded files and console diagnostics go to
`vpd_calculator/tests/artifacts/`. This folder is git-ignored; GitHub Actions uploads it as the
`test-artifacts` artifact.

See [docs/VALIDATION.md](docs/VALIDATION.md) for the scientific validation (published table values, calculated
benchmarks, tolerances, limitations).

## Project layout

Everything is in `vpd_calculator/`; run `streamlit run app.py` from that folder.

| File | Purpose |
|---|---|
| `app.py` | Streamlit interface (five tabs) |
| `vpd.py` | Calculations (FAO-56), grids, condensation limit |
| `presets.py` | Illustrative growth-stage ranges and leaf-offset scenarios, with sources and disclaimers |
| `plots.py` | Interactive Plotly figures |
| `mpl_export.py` | Static PNG/PDF figures with Matplotlib (no browser) |
| `rscript.py` | Reproducible R script export (calculation + ggplot2 heatmap) |
| `share.py` | Shareable-link and setup-file (JSON) encoding |
| `treatments.py` | Treatment-comparison table: row validation and calculation |
| `api.py` | Local FastAPI service for the forward calculation (`POST /v1/calculate`) |
| `citation.py` | Software citation strings |
| `validation.py` | Published table values, calculated benchmarks and comparisons for the validation section |
| `tests/`, `scripts/` | pytest suite (science, AppTest, Playwright, exports) and CI helper script |

In Positron, select the `.venv` interpreter and use the Run App button on `app.py`.

## Method and sources

Saturation vapour pressure uses FAO-56 Eq. 11 (Allen et al., 1998, https://www.fao.org/4/x0490e/x0490e07.htm).
Full APA 7 references are in the app under Methods & References.

Notes: unattainable RH (outside 0-100 %) is reported, never clipped; negative leaf VPD is allowed and flagged;
leaf-offset presets are illustrative scenarios, not universal correction factors.

## Citation

See [CITATION.cff](CITATION.cff) (GitHub's "Cite this repository" button) or the "How to cite this software" section
in the app, which gives APA 7, BibTeX and IEEE formats. No DOI has been minted.

## License

[MIT](LICENSE)
