"""Calculator inputs and result panel as one small Streamlit custom component (st.components.v2).

Streamlit's own sliders only report a value when the pointer is released, so results cannot follow a drag.
This component draws the Calculator's numeric inputs (slider + number field) and its result panel in the
browser and recomputes the panel on every pointer movement. The committed values are sent to Python on
release / Enter, where the app stores them in session state and recomputes everything at full precision
(exports, heatmap, links). The JavaScript formulas mirror vpd.py (FAO-56); tests/e2e compares them with it.
"""

from __future__ import annotations

import streamlit as st

CSS = """
.vpd { font-family: inherit; color: var(--st-text-color, inherit); display: grid;
       grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); gap: 2rem; }
.vpd.ro { grid-template-columns: 1fr; }
@media (max-width: 800px) { .vpd { grid-template-columns: 1fr; } }
.field { margin-bottom: 1rem; }
.field label { display: block; font-size: 0.875rem; margin-bottom: 0.25rem; }
.field input[type=number] { width: 100%; box-sizing: border-box; padding: 0.4rem 0.6rem; font: inherit;
       color: inherit; background: var(--st-secondary-background-color, #f0f2f6);
       border: 1px solid transparent; border-radius: 0.5rem; }
.field input[type=range] { width: 100%; margin: 0.4rem 0 0; accent-color: var(--st-primary-color, #ff4b4b); }
.panel h3 { margin: 0 0 0.5rem; font-size: 1.5rem; font-weight: 600; }
.big { font-size: 2.3rem; font-weight: 600; line-height: 1.2; }
.big .lab { font-size: 1.1rem; font-weight: 400; opacity: 0.8; }
.status { font-weight: 600; margin: 0.5rem 0 0.25rem; }
.status.in { color: #1b7f3b; }
.hint, .cap { font-size: 0.8rem; opacity: 0.75; margin: 0.25rem 0; }
.rowlab { position: relative; height: 1.2rem; font-size: 0.85rem; font-weight: 600; color: #1b7f3b; }
.rowlab span { position: absolute; transform: translateX(-50%); white-space: nowrap; }
.bar { position: relative; height: 16px; border-radius: 8px; background: rgba(128,128,128,0.25); margin: 0.2rem 0; }
.band { position: absolute; top: 0; bottom: 0; background: #4caf50; opacity: 0.85; border-radius: 8px; }
.tick { position: absolute; top: -4px; bottom: -4px; width: 0; border-left: 3px solid #1b7f3b; }
.mark { position: absolute; top: -6px; width: 6px; height: 28px; margin-left: -3px; background: var(--st-text-color, #222);
        border: 2px solid var(--st-background-color, #fff); border-radius: 3px; box-sizing: content-box; }
.axis { position: relative; height: 1.1rem; font-size: 0.75rem; opacity: 0.7; }
.axis span { position: absolute; }
.big2 { font-size: 1.3rem; font-weight: 600; margin-top: 0.25rem; }
.second { font-size: 0.95rem; opacity: 0.85; margin-top: 0.75rem; }
.second b { font-weight: 600; }
details { margin-top: 0.75rem; border: 1px solid rgba(128,128,128,0.35); border-radius: 0.5rem; padding: 0.4rem 0.75rem; }
summary { cursor: pointer; font-size: 0.9rem; }
.det { display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; margin-top: 0.5rem; font-size: 0.8rem; }
.det b { display: block; font-size: 1.1rem; font-weight: 600; }
.warn, .err { margin-top: 0.75rem; padding: 0.6rem 0.8rem; border-radius: 0.5rem; font-size: 0.9rem; }
.warn { background: rgba(255, 193, 7, 0.2); }
.err { background: rgba(255, 75, 75, 0.2); }
"""

JS = r"""
const es = (t) => 0.6108 * Math.exp(17.27 * t / (t + 237.3));
const RH_TOL = 1e-9, VPD_TOL = 1e-9;
const k2 = (x) => x.toFixed(2).replace('-', '\u2212') + ' kPa';
const f1 = (x) => x.toFixed(1);
const signed1 = (x) => (x >= 0 ? '+' : '\u2212') + Math.abs(x).toFixed(1);
const NAME = { air: 'Air VPD', leaf: 'Canopy VPD' };

export function compute(d, v) {
  const tAir = v.t_air;
  const tLeaf = d.leafMethod === 'measured' ? v.calc_leaf_meas : tAir + v.calc_offset;
  const esA = es(tAir), esL = es(tLeaf);
  const out = { tLeaf, offset: tLeaf - tAir, esA, esL, warnings: [], attainable: true };
  if (d.mode === 'a') {
    out.rh = v.rh;
  } else {
    // Reverse mode: the target is always canopy VPD (the representative leaf temperature sets e_s at the leaf).
    out.rh = 100 * (esL - v.target_vpd) / esA;
    out.attainable = out.rh >= -RH_TOL && out.rh <= 100 + RH_TOL;
    if (!out.attainable) {
      const lo = esL - esA, hi = esL;
      out.message = out.rh > 100
        ? `Unattainable: the target canopy VPD of ${k2(v.target_vpd)} is below the minimum reachable VPD (${k2(lo)} at 100% RH) for these temperatures (would need RH = ${f1(out.rh)}%).`
        : `Unattainable: the target canopy VPD of ${k2(v.target_vpd)} exceeds the maximum reachable VPD (${k2(hi)} at 0% RH) for these temperatures (would need RH = ${f1(out.rh)}%).`;
    }
  }
  out.ea = esA * out.rh / 100;
  out.air = esA - out.ea;
  out.leaf = esL - out.ea;
  if (out.attainable && out.leaf < 0) {
    out.warnings.push(`Canopy VPD is negative (${k2(out.leaf)}): the air is supersaturated relative to the leaf surface, so condensation on the leaf is possible.`);
  }
  return out;
}

export function classify(value, lo, hi) {
  if (value < lo - VPD_TOL) return 'below';
  if (value > hi + VPD_TOL) return 'above';
  return 'inside';
}

// Horizontal bar: value marker plus a green band (range) or a line (single target). `s` describes the scale.
function barHtml(s) {
  const point = s.point;
  let dmin = Math.min(...s.domain), dmax = Math.max(...s.domain);
  const pad = 0.04 * (dmax - dmin);
  if (s.cur <= dmin) dmin -= pad;
  if (s.cur >= dmax) dmax += pad;
  const pct = (x) => (100 * (x - dmin) / (dmax - dmin));
  const pos = s.pos;
  const word = point ? { below: 'Below target', inside: 'At target', above: 'Above target' }[pos]
                     : { below: 'Below range', inside: 'Within range', above: 'Above range' }[pos];
  const mid = Math.min(92, Math.max(8, point ? pct(s.lo) : (pct(s.lo) + pct(s.hi)) / 2));
  const shape = s.empty ? ''
    : point ? `<div class="tick" style="left:${pct(s.lo)}%"></div>`
            : `<div class="band" style="left:${pct(s.lo)}%;width:${pct(s.hi) - pct(s.lo)}%"></div>`;
  return `
    <div class="status ${pos === 'inside' ? 'in' : ''}">${word} \u00b7 ${s.context}</div>
    <div class="rowlab"><span style="left:${mid}%">${s.empty ? 'No attainable RH in this range' : (point ? 'Target ' : '') + s.bounds}</span></div>
    <div class="bar" role="img" aria-label="${s.unit} bar: ${word}" data-unit="${s.unit}">${shape}<div class="mark" data-testid="marker" style="left:${pct(s.cur)}%"></div></div>
    <div class="axis"><span style="left:0">${s.axis(dmin)}</span><span style="right:0">${s.axis(dmax)}</span></div>
    ${s.note ? `<div class="hint">${s.note}</div>` : ''}
    <div class="hint">Edit this target in the Acceptable range tab.</div>`;
}

// Forward mode: the bar shows canopy VPD (kPa); an air-VPD range is converted to canopy-VPD limits.
function leafBar(r, t) {
  const shift = t.kind === 'air' ? r.esL - r.esA : 0;      // leaf VPD = air VPD + es(T_leaf) - es(T_air) at the same e_a
  const lo = t.lo + shift, hi = t.hi + shift;
  const kpa = (x) => x.toFixed(2).replace('-', '\u2212');
  return barHtml({
    cur: r.leaf, lo, hi, point: t.lo === t.hi, pos: classify(r.leaf, lo, hi), unit: 'kPa', domain: [0, lo, hi, r.leaf, 2],
    bounds: lo === hi ? k2(lo) : `${kpa(lo)}\u2013${kpa(hi)} kPa`, axis: (x) => kpa(x),
    context: `${t.period} target \u00b7 Canopy VPD`,
    note: t.kind === 'air'
      ? `Converted from the ${t.period.toLowerCase()} air-VPD range ${t.lo === t.hi ? k2(t.lo) : t.lo.toFixed(2) + '\u2013' + t.hi.toFixed(2) + ' kPa'} to canopy-VPD limits at the current air and leaf temperatures (${f1(r.tLeaf - r.offset)} / ${f1(r.tLeaf)} \u00b0C).`
      : '',
  });
}

// Reverse mode: the bar shows canopy RH (%) against the RH interval of the acceptable VPD range.
function rhBar(d, r, t) {
  const rhFor = (v) => t.kind === 'air' ? 100 * (1 - v / r.esA) : 100 * (r.esL - v) / r.esA;
  const rawLo = rhFor(t.hi), rawHi = rhFor(t.lo);          // higher VPD <-> lower RH
  const lo = Math.max(rawLo, 0), hi = Math.min(rawHi, 100);
  const empty = lo > hi;
  const vpdNow = t.kind === 'air' ? r.air : r.leaf;         // classify in VPD space (same order, same tolerance)
  const pos = classify(vpdNow, t.lo, t.hi);
  const pc = (x) => x.toFixed(1).replace('-', '\u2212');
  const partial = !empty && (rawLo < 0 || rawHi > 100);
  return barHtml({
    cur: r.rh, lo: empty ? 0 : lo, hi: empty ? 0 : hi, point: t.lo === t.hi, empty, pos, unit: 'RH (%)', domain: [0, 100, r.rh],
    bounds: t.lo === t.hi ? `${pc(lo)} %` : `${pc(lo)}\u2013${pc(hi)} %`, axis: (x) => pc(x) + ' %',
    context: `${t.period} target \u00b7 ${NAME[t.kind]} ${t.lo === t.hi ? k2(t.lo) : t.lo.toFixed(2) + '\u2013' + t.hi.toFixed(2) + ' kPa'}`,
    note: partial ? `Part of the range is unattainable (unclipped RH ${pc(rawLo)} to ${pc(rawHi)} %); the attainable part is shown.` : '',
  });
}

function reverseHtml(d, r, t) {
  const rhText = (x) => `${f1(x)} %`;
  let h = '';
  if (r.attainable) {
    h += `<div class="big" data-testid="primary"><span class="lab">Canopy RH</span> \u2014 ${rhText(Math.min(Math.max(r.rh, 0), 100))}</div>`;
    h += t ? rhBar(d, r, t) : `<div class="hint">The acceptable range is invalid (lower limit above upper limit). Fix it in the Acceptable range tab.</div>`;
  } else {
    h += `<div class="err">${r.message}</div>`;
    h += `<div class="big" data-testid="primary"><span class="lab">Canopy RH (not physically attainable)</span> \u2014 ${rhText(r.rh)}</div>`;
  }
  h += `<div class="cap">Leaf temperature used: ${f1(r.tLeaf)} \u00b0C (offset ${signed1(r.offset)} \u00b0C)</div>`;
  if (r.attainable) for (const w of r.warnings) h += `<div class="warn">${w}</div>`;
  return h;
}

export function resultsHtml(d, v) {
  const r = compute(d, v);
  const t = d.target;
  if (d.mode === 'b') return reverseHtml(d, r, t);
  let h = `<div class="big" data-testid="primary"><span class="lab">Canopy VPD</span> \u2014 ${k2(r.leaf)}</div>`;
  if (t) {
    h += leafBar(r, t);
  } else {
    h += `<div class="hint">The acceptable range is invalid (lower limit above upper limit). Fix it in the Acceptable range tab.</div>`;
  }
  h += `<div class="second" data-testid="secondary">Air VPD: <b>${k2(r.air)}</b></div>`;
  h += `<div class="cap">Leaf temperature used: ${f1(r.tLeaf)} \u00b0C (offset ${signed1(r.offset)} \u00b0C)</div>`;
  for (const w of r.warnings) h += `<div class="warn">${w}</div>`;
  return h;
}

export default function (component) {
  const { data, parentElement, setStateValue } = component;
  const d = data;
  const values = {};
  for (const old of Array.from(parentElement.children)) {   // a re-render must replace, not stack, the panel
    if (old.classList && old.classList.contains('vpd')) old.remove();
  }
  // A rerun triggered by an earlier commit can arrive after a newer edit; keep the newer local values until
  // Python's data has caught up (a changed input set, e.g. a mode switch, always takes Python's values).
  const sig = d.inputs.map((f) => f.key).join(',');
  for (const f of d.inputs) values[f.key] = f.value;
  if (parentElement.__vpdEpoch !== d.epoch) {                  // Reset: unsent local edits must not undo it
    parentElement.__vpdPending = null;
    parentElement.__vpdEpoch = d.epoch;
  }
  const pending = parentElement.__vpdPending;
  if (pending && pending.sig === sig) {
    if (d.inputs.every((f) => f.value === pending.values[f.key])) parentElement.__vpdPending = null;
    else for (const f of d.inputs) values[f.key] = pending.values[f.key];
  } else {
    parentElement.__vpdPending = null;
  }
  const root = document.createElement('div');
  root.className = 'vpd';
  const left = document.createElement('div');
  const panel = document.createElement('div');
  panel.className = 'panel';
  if (!d.readonly) root.append(left);                          // display-only copy shows just the panel
  else root.classList.add('ro');
  root.append(panel);
  parentElement.appendChild(root);

  const refresh = () => {
    let html = resultsHtml(d, values);
    if (d.readonly) html = html.replace(/<div class="hint">Edit this target[^<]*<\/div>/, '');
    panel.innerHTML = `<h3>${d.title || 'Results'}</h3>` + html;
  };
  const commit = () => {
    parentElement.__vpdPending = { sig, values: { ...values } };   // newer than any rerun still in flight
    setStateValue('values', { ...values });
  };

  for (const f of (d.readonly ? [] : d.inputs)) {
    const box = document.createElement('div');
    box.className = 'field';
    const label = document.createElement('label');
    label.textContent = f.label;
    const num = document.createElement('input');
    num.type = 'number'; num.step = f.step; num.min = f.numMin; num.max = f.numMax;
    num.setAttribute('aria-label', f.label);
    num.dataset.key = f.key;
    const sld = document.createElement('input');
    sld.type = 'range'; sld.min = f.min; sld.max = f.max; sld.step = f.step;
    sld.setAttribute('aria-label', f.label + ' slider');
    sld.dataset.key = f.key;
    const show = () => {
      num.value = values[f.key].toFixed(f.dec);
      sld.value = Math.min(Math.max(values[f.key], f.min), f.max);
    };
    show();
    sld.addEventListener('input', () => {            // fires continuously while dragging
      values[f.key] = parseFloat(sld.value);
      num.value = values[f.key].toFixed(f.dec);
      refresh();
    });
    sld.addEventListener('change', commit);           // pointer released
    num.addEventListener('change', () => {
      const x = parseFloat(num.value);
      if (Number.isFinite(x) && x >= f.numMin && x <= f.numMax) values[f.key] = x;
      show(); refresh(); commit();
    });
    box.append(label, num, sld);
    left.appendChild(box);
  }
  refresh();
  return () => root.remove();
}
"""

COPY_CSS = """
button { font: inherit; color: inherit; background: var(--st-background-color, #fff); cursor: pointer;
         border: 1px solid rgba(128,128,128,0.5); border-radius: 0.5rem; padding: 0.25rem 0.75rem; }
button:hover { border-color: var(--st-primary-color, #ff4b4b); }
span { margin-left: 0.5rem; font-size: 0.85rem; color: #1b7f3b; }
"""

COPY_JS = r"""
export default function (component) {
  const { data, parentElement } = component;
  for (const old of Array.from(parentElement.children)) {
    if (old.classList && old.classList.contains('copy')) old.remove();
  }
  const root = document.createElement('div');
  root.className = 'copy';
  const button = document.createElement('button');
  button.type = 'button';
  button.textContent = 'Copy link';
  const note = document.createElement('span');
  note.setAttribute('role', 'status');
  const copy = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (e) {                                   // clipboard API unavailable (e.g. insecure context)
      const box = document.createElement('textarea');
      box.value = text;
      document.body.appendChild(box);
      box.select();
      document.execCommand('copy');
      box.remove();
    }
  };
  button.addEventListener('click', async () => {
    await copy(data.url);
    note.textContent = 'Link copied';
    setTimeout(() => { note.textContent = ''; }, 2000);
  });
  root.append(button, note);
  parentElement.appendChild(root);
  return () => root.remove();
}
"""

_component = None
_copy_component = None


def _mount(**kwargs):
    global _component
    if _component is None:
        _component = st.components.v2.component("vpd_live_calculator", css=CSS, js=JS)
    return _component(**kwargs)


def live_calculator(data: dict, on_values):
    """Mount the component. `on_values` runs (before the rerun) when the user commits new values."""
    return _mount(key="calc_live", data=data, default={"values": None}, on_values_change=on_values)


def copy_link_button(url: str):
    """A small button that copies `url` (the current shareable link) to the clipboard."""
    global _copy_component
    if _copy_component is None:
        _copy_component = st.components.v2.component("vpd_copy_link", css=COPY_CSS, js=COPY_JS)
    return _copy_component(key="copy_link", data={"url": url})


def result_panel(data: dict, key: str = "range_panel"):
    """Display-only copy of the Calculator's result panel (same JS, same data; no inputs, nothing is sent back)."""
    return _mount(key=key, data=data)
