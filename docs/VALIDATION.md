# Scientific validation

This document records what the VPD calculator is checked against, with what tolerances, and what those
checks do and do not show. The same comparisons are shown live in the app under
**Methods & References → Scientific validation**.

None of the comparisons below are experimental measurements. They test that the code implements the
published equations correctly; they do not test how well those equations describe a particular chamber or leaf.

**Published versus calculated numbers.** Only the saturation-vapour-pressure values of FAO-56 Table 2.3 are
numbers printed in a source. The five air-VPD cases are *calculated benchmarks*: they were produced by evaluating
the equations and rounding to 4 d.p. Agreement with a calculated benchmark shows that the code evaluates the
equation as intended; it is not agreement with a published table, and it is not an independent source.

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

## Provenance of the reference numbers

Verification date 2026-10-29. FAO-56 pages were read online in this project's review session. The Johnston et al. (2025) equation was verified by an external source review; the article could not be opened in that session (HTTP 403), so this is reported on the reviewer's evidence.

| Reference set | Published or calculated | Source and exact location | Status |
|---|---|---|---|
| es at 15, 20, 22, 25, 30, 33, 35 °C (`FAO_ES_TABLE`) | **Published** (3 d.p.) | FAO-56 Annex 2, Table 2.3 "Saturation vapour pressure (e°(T)) for different temperatures (T)"; table runs 1.0–48.5 °C in 0.5 °C steps. https://www.fao.org/4/x0490e/x0490e0j.htm | All seven values read from the page and found identical (e.g. 22.0 → 2.644, 33.0 → 5.030). |
| es equation, constants 0.6108, 17.27, 237.3 | Published equation | FAO-56 Chapter 3, Eq. 11 (the equation is an image on the page; the same formula with these constants is written out in Example 3 on that page, which prints e°(15 °C) = 1.705 and e°(24.5 °C) = 3.075 kPa). https://www.fao.org/4/x0490e/x0490e07.htm | Constants confirmed from Example 3 text. |
| Five air-VPD cases, FAO-56 column (`VPD_CASES`) | **Calculated** (4 d.p.) | es(T) × (1 − RH/100) with the Eq. 11 constants. FAO-56 does not print these cases: its only VPD example (Example 6, es − ea = 0.91 kPa) uses different inputs. | A stand-alone recalculation (plain `math`, not the production code) reproduces all five values at 4 d.p. Their original source was a project specification, which is not in this repository. |
| Five air-VPD cases, Johnston column (`VPD_CASES`) | **Calculated** (4 d.p.) | es(T) × (1 − RH/100) with es = 0.61078·exp(17.08085·T/(T+234.175)) kPa (the paper's hPa form divided by 10). | The stand-alone recalculation reproduces all five at 4 d.p. **Not verified:** that these five VPD values are printed in the paper. The *coefficients* are a separate row below. |
| Johnston es equation, coefficients 6.1078 (hPa; ÷ 10 → 0.61078 kPa), 17.08085, 234.175 | Published equation | Johnston et al. (2025), Section 1 "Introduction", Equation 2: `es_hPa(T) = 6.1078 * exp(17.08085 * T / (T + 234.175))`. https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2024JG008146 | **Verified** against the printed equation by an external source review, 2026-10-29. The hPa → kPa conversion (÷ 10) is applied by this project. |
| Original project specification (source of the 4 d.p. benchmark numbers) | Unknown | Not in this repository. | Historical provenance **unverified**; the numbers are supported here only by recalculation from the equations. |

Tolerances are unchanged: ±0.0005 kPa for Table 2.3 (half the last printed decimal), ±0.0001 kPa for the
4 d.p. calculated benchmarks.

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

### Air VPD cases (calculated benchmarks to 4 d.p.; not published tabulated values)

Tolerance: ±0.0001 kPa (benchmark rounding is ±0.00005 kPa).

| T (°C) | RH (%) | FAO-56 calculated benchmark (kPa) | Application (kPa) | Difference | Johnston calculated benchmark (kPa) | Johnston, independent calc. (kPa) | Application − Johnston (kPa) |
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
| Application VPD vs calculated FAO-56 benchmark VPD | 0.000041 | 0.0001 |
| Application VPD vs Johnston equation | 0.002548 | not a pass/fail criterion |

## What the tests cover

Evidence categories are kept separate.

1. **Agreement with published tabulated values** (`tests/test_science.py`): saturation vapour pressure in FAO-56
   Table 2.3 only, at ±0.0005 kPa.
2. **Agreement with calculated benchmarks** (`tests/test_science.py`): the five FAO-56-equation air-VPD cases
   (4 d.p., ±0.0001 kPa). These are calculated values, not published tabulated numbers, and they were not generated
   with the production functions. This checks the implementation of the equation, not a source.
3. **Comparison with an alternative published equation** (`tests/test_science.py`): the Johnston equation is
   re-implemented independently in the test file (from the hPa form of Eq. 2 in the paper, whose coefficients were
   verified by an external source review; see Provenance) and reproduces the calculated Johnston benchmark VPDs within 0.0001 kPa.
   The production FAO-56 function is never used to generate those expected values. The application and the Johnston equation differ by about 0.0017–0.0025 kPa in these
   cases (relative es difference at most 0.16 % between 0 and 40 °C) because the coefficients differ.
   Two closely related empirical fits agreeing is not independent proof of accuracy.
4. **Internal consistency** (`tests/test_science.py`, `tests/test_vpd.py`): es monotonic in temperature; air VPD
   linear and decreasing in RH; VPD = 0 at 100 % RH and = es at 0 % RH; forward/reverse round trips (RH recovered
   to 1e-9 percentage points) for air and leaf VPD; leaf VPD = air VPD when leaf temperature = air temperature;
   leaf VPD increasing with leaf temperature; negative leaf VPD possible; impossible targets rejected, never
   clamped; calculator, heatmap and CSV values identical to 1e-12 kPa; display rounding never feeds back into
   calculations.
5. **Interface and export tests** (`tests/test_app.py` with Streamlit AppTest; `tests/e2e/` with Playwright and
   Chromium; `tests/test_exports.py`): the rendered application shows the expected numbers, validation messages
   appear, and downloaded PNG, PDF, CSV and R-script files exist and have valid content. The R script is executed with
   `Rscript` (when available): it reproduces the app's values and, with ggplot2, the heatmap PNG and PDF.

Explicit numerical tolerances are defined at the top of `tests/test_science.py` and in `validation.py`.

## Limitations

- Both equations are empirical fits; agreement between them says little about accuracy at extreme temperatures.
  Checks used 15–35 °C (FAO table) and 0–45 °C (properties).
- The calculated benchmark VPD values are rounded to 4 d.p., so differences below about 5e-5 kPa cannot be resolved.
- The interface shows values with one decimal place for readability; the validation tables and CSV exports keep full
  precision, and all comparisons use unrounded values.
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
PNG/PDF export uses Matplotlib (no browser needed). R-script reproduction needs `Rscript` (and `ggplot2` for the heatmap) and is skipped if absent.

## Interpreting results

"Within tolerance" means the application's number differs from the reference number by no more than the
rounding of that number. For FAO-56 Table 2.3 the reference is a published table; for the air-VPD cases it is a
calculated benchmark. Both support the claim that the FAO-56 equation is implemented as intended. Neither
means the calculation matches measurements from your chamber.
