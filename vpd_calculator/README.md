# VPD Calculator

Interactive vapour pressure deficit (VPD) calculator for controlled-environment plant research
(e.g. *Fragaria vesca* phytotron experiments). Built with Python, Streamlit and Plotly.

- **Calculator**: bidirectional. Mode A computes VPD from temperature and RH; mode B computes the
  RH required for a target air or leaf VPD (closed-form). Leaf temperature as an offset or a
  measured value. Target VPD interval -> RH range.
- **VPD Heatmap**: temperature x RH, air or leaf VPD, labelled contours, selected point and target region.
- **Day/Night Experiments**: independent day/night settings, Control/Warming temperature presets,
  comparison table and plot across treatments.
- **Methods**: equations, assumptions, references.

Exports: heatmap PNG, temperature/RH/VPD grid CSV, treatment comparison CSV, current settings CSV.

## Run

```powershell
cd vpd_calculator
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

In Positron, select the `.venv` interpreter and use the Run App button on `app.py`.

## Tests

```powershell
python -m pytest
```

## Layout

| File | Purpose |
|---|---|
| `vpd.py` | Calculations (FAO-56), validation, grids, treatment tables |
| `plots.py` | Plotly figures |
| `app.py` | Streamlit interface |
| `tests/` | pytest suite |

## Notes

- `es(T) = 0.6108 exp(17.27 T / (T + 237.3))`: FAO-56 Eq. 11 (Allen et al. 1998).
- Unattainable RH (outside 0-100 %) is reported, never clipped. Negative leaf VPD is allowed and flagged.
- Target VPD intervals are user-defined, not validated optima for any species.
- PNG export uses `kaleido`, which needs Chrome/Chromium; if missing, run `plotly_get_chrome` or use the
  camera icon in the chart toolbar.
- Dark/light theme follows Streamlit's theme (Settings menu, top right).

## References

- Allen, R.G., Pereira, L.S., Raes, D., Smith, M. (1998). *Crop evapotranspiration: guidelines for computing
  crop water requirements.* FAO Irrigation and Drainage Paper 56. FAO, Rome.
  Eq. 11: https://www.fao.org/4/x0490e/x0490e07.htm (full text: https://www.fao.org/4/x0490e/x0490e00.htm)
- Interface inspiration only: Pulse Grow, *Vapor Pressure Deficit (VPD)*. https://pulsegrow.com/blogs/learn/vpd
