# VPD Calculator

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://vpd-or-not-vpd.streamlit.app/)

An interactive vapour pressure deficit (VPD) calculator for controlled-environment plant research
(e.g. *Fragaria vesca* phytotron experiments), built with Python, Streamlit and Plotly.

- Bidirectional: VPD from temperature and RH, or the RH required for a target air or leaf VPD
- Interactive temperature x RH heatmap with contours and a user-defined target VPD interval
- Day/night treatment comparison (Control/Warming temperature presets)
- CSV and PNG exports

## Quick start

```powershell
cd vpd_calculator
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Run the tests with `python -m pytest` from `vpd_calculator/`.

See [vpd_calculator/README.md](vpd_calculator/README.md) for details, project layout and notes.

## Deploy on Streamlit Community Cloud

1. Go to https://share.streamlit.io and choose **Create app** from this GitHub repository.
2. Branch `main`, main file path `vpd_calculator/app.py`.
3. Deploy. `packages.txt` (repo root) installs Chromium for server-side PNG export; if that export is
   unavailable, the app falls back to the camera icon in the chart toolbar.

Live app: https://vpd-or-not-vpd.streamlit.app/

## Method and sources

Saturation vapour pressure uses FAO-56 Eq. 11 (Allen et al. 1998,
https://www.fao.org/4/x0490e/x0490e07.htm). Target VPD intervals in the app are user-defined and are
not validated optima for any species.

## License

[MIT](LICENSE)
