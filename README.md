# VPD Calculator

[![tests](https://github.com/MaartenArthurSmits/vpd_or_not_vpd/actions/workflows/tests.yml/badge.svg)](https://github.com/MaartenArthurSmits/vpd_or_not_vpd/actions/workflows/tests.yml)
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://vpd-or-not-vpd.streamlit.app/)

An interactive vapour pressure deficit (VPD) calculator for controlled-environment plant research
(e.g. *Fragaria vesca* phytotron experiments), built with Python, Streamlit and Plotly.

- Bidirectional: VPD from temperature and RH, or the RH required for a target air or leaf VPD
- Interactive temperature x RH heatmap with contours and a user-defined target VPD interval
- Day/night treatment comparison (Control/Warming temperature presets)
- Measured-data tab: upload logger CSVs (temperature, RH over time) and plot VPD
- Shareable links that restore calculator settings
- Scientific validation against FAO-56 tables and an alternative published equation (Methods & References tab)
- CSV and PNG exports

**Use it online:** https://vpd-or-not-vpd.streamlit.app/

## Run locally

```powershell
cd vpd_calculator
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Testing

From `vpd_calculator/`:

```powershell
pip install -r requirements-dev.txt
python -m playwright install chromium     # one-off, for browser tests

python -m pytest -m "science or unit"      # scientific + unit tests
python -m pytest -m apptest                # Streamlit AppTest interaction tests
python -m pytest -m "e2e and not exports"  # Playwright browser tests (starts a local server)
python -m pytest -m exports                # export-file validation (CSV, PNG, R script)
python -m pytest                           # all
```

Screenshots (desktop and mobile), downloaded files and console diagnostics go to
`vpd_calculator/tests/artifacts/`. This folder is git-ignored; GitHub Actions uploads it as the
`test-artifacts` artifact. Widgets have stable `key`s and tests use accessible labels, so they are easy to extend.

See [docs/VALIDATION.md](docs/VALIDATION.md) for the scientific validation (published reference values, tolerances, limitations).

See [vpd_calculator/README.md](vpd_calculator/README.md) for details, project layout and notes.

## Method and sources

Saturation vapour pressure uses FAO-56 Eq. 11 (Allen et al. 1998,
https://www.fao.org/4/x0490e/x0490e07.htm). Target VPD intervals in the app are user-defined and are
not validated optima for any species.

## Citation

See [CITATION.cff](CITATION.cff) (GitHub's "Cite this repository" button).

## License

[MIT](LICENSE)
