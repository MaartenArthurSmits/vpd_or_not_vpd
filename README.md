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

Run the tests (from `vpd_calculator/`): `pip install -r requirements-dev.txt`, then `python -m pytest`.

See [vpd_calculator/README.md](vpd_calculator/README.md) for details, project layout and notes.

## Method and sources

Saturation vapour pressure uses FAO-56 Eq. 11 (Allen et al. 1998,
https://www.fao.org/4/x0490e/x0490e07.htm). Target VPD intervals in the app are user-defined and are
not validated optima for any species.

## Citation

See [CITATION.cff](CITATION.cff) (GitHub's "Cite this repository" button).

## License

[MIT](LICENSE)
