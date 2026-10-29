# Scientific validation

This document records what the VPD calculator is checked against, with what tolerances, and what those
checks do and do not show. The same comparisons are shown live in the app under
**Methods & References → Scientific validation**.

None of the comparisons below are experimental measurements. They test that the code implements the
published equations correctly; they do not test how well those equations describe a particular chamber or leaf.

## Equations and units

Temperature in °C, relative humidity (RH) in %, pressures in kPa.

**FAO-56 (primary, used by the application)** – Allen et al. (1998), Eq. 11:

```
es(T) = 0.6108 * exp(17.27 * T / (T + 237.3))
ea    = es(T_air) * RH / 100
VPD_air  = es(T_air)  - ea  = es(T_air) * (1 - RH/100)
VPD_leaf = es(T_leaf) - ea
RH (target air VPD)  = 100 * (1 - VPD / es(T_air))
RH (target leaf VPD) = 100 * (es(T_leaf) - VPD) / es(T_air)
```

**Johnston et al. (2025) (alternative, comparison only)**:

```
es(T) = 0.61078 * exp(17.08085 * T / (T + 234.175))      [kPa]
```

The paper writes the equation in hPa; the result has been divided by 10. VPD_air = es(T) × (1 − RH/100).

## Sources

| Source | Link |
|---|---|
| FAO-56 Eq. 11 (Chapter 3) | https://www.fao.org/4/x0490e/x0490e07.htm |
| FAO-56 Annex 2, Table 2.3 | https://www.fao.org/4/x0490e/x0490e0j.htm |
| Grossiord et al. (2020), Fig. 2 | https://doi.org/10.1111/nph.16485 |
| Johnston et al. (2025), Fig. 1 | https://doi.org/10.1029/2024JG008146 |
| Garen et al. (2026), Fig. 1a | https://doi.org/10.1093/plphys/kiag575 |

The three research figures illustrate the expected relationships between temperature, RH and VPD
(Grossiord: temperature, RH, vapour pressure and VPD; Johnston: different temperature/RH combinations giving
equivalent VPD; Garen: a psychrometric chart with physically impossible combinations marked). They are
not reproduced here for copyright reasons and are **not a numerical validation** on their own.

## Reference cases

### Saturation vapour pressure, FAO-56 Table 2.3 (published to 3 d.p.)

Tolerance: ±0.0005 kPa (half of the last published decimal, plus 1e-9 for floating point).

| T (°C) | Published es (kPa) | Application es (kPa) | Difference (kPa) |
|---|---|---|---|
| 15 | 1.705 | 1.705346 | +0.000346 |
| 20 | 2.338 | 2.338281 | +0.000281 |
| 22 | 2.644 | 2.643931 | −0.000069 |
| 25 | 3.168 | 3.167778 | −0.000222 |
| 30 | 4.243 | 4.243065 | +0.000065 |
| 33 | 5.030 | 5.030148 | +0.000148 |
| 35 | 5.623 | 5.622681 | −0.000319 |

### Air VPD cases (reference values to 4 d.p.)

Tolerance: ±0.0001 kPa (reference rounding is ±0.00005 kPa).

| T (°C) | RH (%) | FAO-56 ref. (kPa) | Application (kPa) | Difference | Johnston ref. (kPa) | Johnston, independent calc. (kPa) | Application − Johnston (kPa) |
|---|---|---|---|---|---|---|---|
| 20 | 50 | 1.1691 | 1.169141 | +0.000041 | 1.1710 | 1.170999 | −0.001858 |
| 22 | 60 | 1.0576 | 1.057572 | −0.000028 | 1.0593 | 1.059263 | −0.001691 |
| 25 | 60 | 1.2671 | 1.267111 | +0.000011 | 1.2691 | 1.269100 | −0.001989 |
| 30 | 70 | 1.2729 | 1.272920 | +0.000020 | 1.2747 | 1.274723 | −0.001803 |
| 33 | 60 | 2.0121 | 2.012059 | −0.000041 | 2.0146 | 2.014607 | −0.002548 |

Maximum absolute differences (full precision):

| Comparison | Max abs. difference (kPa) | Tolerance (kPa) |
|---|---|---|
| Application es vs FAO-56 Table 2.3 | 0.000346 | 0.0005 |
| Application VPD vs FAO-56 reference VPD | 0.000041 | 0.0001 |
| Application VPD vs Johnston equation | 0.002548 | not a pass/fail criterion |

## What the tests cover

Evidence categories are kept separate.

1. **Agreement with published tabulated values** (`tests/test_science.py`): FAO-56 Table 2.3 and the FAO-56 VPD
   reference cases, at the tolerances above.
2. **Agreement with an alternative published equation** (`tests/test_science.py`): the Johnston equation is
   re-implemented independently in the test file (from the hPa form printed in the paper) and reproduces the
   published Johnston VPD values within 0.0001 kPa. The production FAO-56 function is never used to generate
   those expected values. The application and the Johnston equation differ by about 0.0017–0.0025 kPa in these
   cases (relative es difference at most 0.16 % between 0 and 40 °C) because the coefficients differ.
   Two closely related empirical fits agreeing is not independent proof of accuracy.
3. **Internal consistency** (`tests/test_science.py`, `tests/test_vpd.py`): es monotonic in temperature; air VPD
   linear and decreasing in RH; VPD = 0 at 100 % RH and = es at 0 % RH; forward/reverse round trips (RH recovered
   to 1e-9 percentage points) for air and leaf VPD; leaf VPD = air VPD when leaf temperature = air temperature;
   leaf VPD increasing with leaf temperature; negative leaf VPD possible; impossible targets rejected, never
   clamped; calculator, heatmap and CSV values identical to 1e-12 kPa; display rounding never feeds back into
   calculations.
4. **Interface and export tests** (`tests/test_app.py` with Streamlit AppTest; `tests/e2e/` with Playwright and
   Chromium; `tests/test_exports.py`): the rendered application shows the expected numbers, validation messages
   appear, and downloaded PNG, CSV and R-script files exist and have valid content. The R script is executed with
   `Rscript` (when available) and reproduces the app's values.

Explicit numerical tolerances are defined at the top of `tests/test_science.py` and in `validation.py`.

## Limitations

- Both equations are empirical fits; agreement between them says little about accuracy at extreme temperatures.
  Checks used 15–35 °C (FAO table) and 0–45 °C (properties).
- The reference VPD values are rounded, so differences below about 5e-5 kPa cannot be resolved.
- The app does not model atmospheric pressure, leaf boundary-layer effects, or sensor error.
- Leaf VPD assumes saturated air inside the leaf at leaf temperature.
- Target VPD ranges are user-defined; no species-specific optimum is claimed.
- The in-app validation tables are evaluated when the page renders; the automated test suite is a separate
  check, run locally or in CI.

## Reproducing

```powershell
cd vpd_calculator
pip install -r requirements-dev.txt
python -m playwright install chromium

python -m pytest -m "science or unit"       # scientific and unit tests
python -m pytest -m apptest                 # Streamlit AppTest
python -m pytest -m "e2e and not exports"   # browser tests (starts a local Streamlit server)
python -m pytest -m exports                 # export-file validation
python -m pytest                            # everything
```

Screenshots, downloaded files, the Streamlit server log and `console-errors.json` are written to
`vpd_calculator/tests/artifacts/` (git-ignored; uploaded as the `test-artifacts` artifact in GitHub Actions).
PNG export uses kaleido, which needs Chrome/Chromium; R-script reproduction needs `Rscript` and is skipped if absent.

## Interpreting results

"Within tolerance" means the application's number differs from the published reference by no more than the
rounding of that reference. It supports the claim that the FAO-56 equation is implemented correctly. It does not
mean the calculation matches measurements from your chamber.
