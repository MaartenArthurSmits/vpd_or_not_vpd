# VPD Calculator

[![tests](https://github.com/MaartenArthurSmits/vpd_or_not_vpd/actions/workflows/tests.yml/badge.svg)](https://github.com/MaartenArthurSmits/vpd_or_not_vpd/actions/workflows/tests.yml)
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://vpd-or-not-vpd.streamlit.app/)

An interactive vapour pressure deficit (VPD) calculator for controlled-environment plant research,
built with Python, Streamlit and Plotly.

**Use it online:** https://vpd-or-not-vpd.streamlit.app/

## Features

Three tabs: **Calculator**, **VPD Heatmap**, **Methods & References**.

- **Bidirectional calculator:** VPD from temperature and RH, or the RH required for a target air or leaf VPD.
- **Leaf temperature:** an offset (illustrative scenarios 0, -1, -2, +1, +2 °C or custom) or a measured value, with an
  explanation of air versus leaf VPD.
- **Target VPD range:** illustrative growth-stage presets (seedlings/propagation, vegetative, flowering, general
  horticulture) or a custom range, with the corresponding RH range.
- **Day and night:** independently configured day and night temperature, leaf offset and target VPD range, with
  required RH ranges and condensation guidance.
- **Heatmap:** interactive temperature x RH plot (air or leaf VPD) with contours, target range and selected point.
- **Exports:** grid CSV, settings CSV, publication-quality heatmap PNG (300 dpi) and PDF rendered with Matplotlib
  (no browser needed), and a reproducible R script that recreates the calculation and the heatmap with ggplot2.
- **Shareable links** restore calculator settings.
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

See [docs/VALIDATION.md](docs/VALIDATION.md) for the scientific validation (published table values, calculated benchmarks, tolerances, limitations)
and [vpd_calculator/README.md](vpd_calculator/README.md) for project layout.

## Method and sources

Saturation vapour pressure uses FAO-56 Eq. 11 (Allen et al., 1998, https://www.fao.org/4/x0490e/x0490e07.htm).
Full APA 7 references are in the app under Methods & References.

## Citation

See [CITATION.cff](CITATION.cff) (GitHub's "Cite this repository" button) or the "How to cite this software" section
in the app, which gives APA 7, BibTeX and IEEE formats. No DOI has been minted.

## License

[MIT](LICENSE)
