# VPD Calculator

Interactive vapour pressure deficit (VPD) calculator for controlled-environment plant research.
Built with Python, Streamlit, Plotly and Matplotlib.

- **Calculator**: bidirectional. Mode A computes VPD from temperature and RH; mode B computes the RH required
  for a target air or leaf VPD (closed form). Leaf temperature as an offset (illustrative presets or custom) or a
  measured value. Target VPD range with illustrative growth-stage presets, plus independent day and night
  ranges with required RH ranges and condensation guidance.
- **VPD Heatmap**: temperature x RH, air or leaf VPD, labelled contours, selected point and target range.
  Downloads: grid CSV, PNG (300 dpi) and PDF via Matplotlib, and a reproducible R script (ggplot2).
- **Methods & References**: equations, assumptions, APA 7 references, software citation (APA 7, BibTeX, IEEE)
  and the Scientific validation section.

Values are shown with one decimal; internal calculations, validation tables and CSV files keep full precision.

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
pip install -r requirements-dev.txt
python -m playwright install chromium     # browser tests only
python -m pytest
```

## Layout

| File | Purpose |
|---|---|
| `app.py` | Streamlit interface (three tabs) |
| `vpd.py` | Calculations (FAO-56), validation, grids, condensation limit |
| `presets.py` | Illustrative growth-stage ranges and leaf-offset scenarios, with source and disclaimers |
| `plots.py` | Interactive Plotly figures |
| `mpl_export.py` | Static PNG/PDF figures with Matplotlib (no browser) |
| `rscript.py` | Reproducible R script export (calculation + ggplot2 heatmap) |
| `share.py` | Shareable-link (URL query parameter) encoding |
| `citation.py` | Software citation strings |
| `validation.py` | Published table values, calculated benchmarks and comparisons shown in the validation section |
| `tests/` | pytest suite (science, AppTest, Playwright e2e, export validation) |
| `scripts/` | CI helper scripts |

## Notes

- `es(T) = 0.6108 exp(17.27 T / (T + 237.3))`: FAO-56 Eq. 11 (Allen et al., 1998).
- Unattainable RH (outside 0-100 %) is reported, never clipped. Negative leaf VPD is allowed and flagged.
- Growth-stage presets are illustrative horticultural ranges (Koverda, 2020; Pulse Grow), not validated
  species-specific optima. Pulse Grow is not the source of the equations.
- Leaf-offset presets are illustrative scenarios, not universal correction factors.
- Dark/light theme follows Streamlit's theme (Settings menu, top right).

## License

MIT, see [../LICENSE](../LICENSE).

## References

- Allen, R. G., Pereira, L. S., Raes, D., & Smith, M. (1998). *Crop evapotranspiration: Guidelines for computing crop
  water requirements* (FAO Irrigation and Drainage Paper No. 56). FAO. https://www.fao.org/4/x0490e/x0490e00.htm
  (Eq. 11: https://www.fao.org/4/x0490e/x0490e07.htm)
- Koverda, P. (2020, February 12). *The ultimate vapor pressure deficit (VPD) guide*. Pulse Grow.
  https://pulsegrow.com/blogs/learn/vpd (illustrative ranges and interface inspiration)

The complete reference list is in the app under Methods & References.
