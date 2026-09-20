#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import NamedTuple, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind
import callgrind_diff
import theme
from callgrind import Costs, Group

# The whole page body and its script. Named exactly this: check_js.py looks
# it up by name. JS in a triple-quoted string needs "\\n" written "\\\\n".
BODY = """<div id="hdr" class="strip">
  <label>event: <select id="event"></select></label>
  <label>scale: <select id="scale">
    <option value="global">log, global</option>
    <option value="file">log, per file</option>
    <option value="linear">linear, global</option>
  </select></label>
  <label>tree: <select id="sort">
    <option value="heat">by heat</option>
    <option value="name">by name</option>
  </select></label>
  <label>search:
    <input id="q" type="search" placeholder="file name\u2026"></label>
</div>
<div id="layout">
  <nav id="tree"></nav>
  <div id="split" class="split" title="drag to resize"></div>
  <section id="main"></section>
  <div id="minimap" class="empty"><div id="mmBox"></div>
    <div id="mmViewport" hidden></div></div>
</div>
<script id="heatdata" type="application/json">__DATA__</script>
<script>
__THEME_JS__
</script>
<script>(function () {
"use strict";
const model = JSON.parse(document.getElementById("heatdata").textContent);
const files = model.files, functions = model.functions;
const treeEl = document.getElementById("tree");
const mainEl = document.getElementById("main");
const minimapEl = document.getElementById("minimap");
const mmBox = document.getElementById("mmBox");
const mmViewport = document.getElementById("mmViewport");
const store = Theme.store;
let scale = store.get("heat.scale") || "global";
let sortMode = store.get("heat.sort") || "heat";
let curFile = null, query = "";
document.getElementById("scale").value = scale;
document.getElementById("sort").value = sortMode;
Theme.splitter(document.getElementById("split"), treeEl, "heat.tree", 120);

const at = (vector, index) =>
  (vector && index < vector.length) ? vector[index] : 0;
const EVS = [];
model.meta.events.forEach((name, index) => {
  EVS.push({
    key: name,
    long: model.meta.eventLong[name] || "",
    get: vector => at(vector, index),
  });
});
for (const [name, terms, long] of model.meta.derived) {
  const get = vector =>
    terms.reduce((sum, term) => sum + term[0] * at(vector, term[1]), 0);
  EVS.push({
    key: name,
    long: long || model.meta.eventLong[name] || "",
    get,
    derived: true,
  });
}
const evByKey = key => EVS.find(event => event.key === key);
let currentEvent = evByKey(model.meta.defaultEvent) || EVS[0];
const EXTRA = ["D1m", "DLm", "Bcm"].map(evByKey).filter(Boolean);

const EVENT_SHORT = {
  Ir: "instructions", Dr: "data reads", Dw: "data writes",
  I1mr: "L1 icache miss", D1mr: "L1 dcache read miss",
  D1mw: "L1 dcache write miss",
  ILmr: "L3 icache miss", DLmr: "L3 dcache read miss",
  DLmw: "L3 dcache write miss",
  Bc: "branches", Bcm: "misprediction", Bi: "indirect branches",
  Bim: "indirect misprediction",
  Ge: "bus events", sysCount: "syscalls", sysTime: "syscall time",
  sysCpuTime: "syscall cpu time",
  AcCost1: "L1 access cost", SpLoss1: "L1 spatial loss",
  AcCost2: "L3 access cost", SpLoss2: "L3 spatial loss",
  ILdmr: "L3 insn write-back", DLdmr: "L3 read write-back",
  DLdmw: "L3 write write-back",
  D1m: "L1 cache", DLm: "L3 cache", L1m: "L1 cache, all", LLm: "L3 cache, all",
  Bm: "misprediction, all", CEst: "cycle estimate",
};
const evLabel = event => EVENT_SHORT[event.key]
  ? EVENT_SHORT[event.key] + " / " + event.key : event.key;
const evLong = event => EVENT_SHORT[event.key] || event.long || event.key;
const evSel = document.getElementById("event");
let evMaxLen = 0;
for (const event of EVS) {
  const option = document.createElement("option");
  option.value = event.key;
  option.textContent =
    event.key + (event.long ? " \\u2014 " + event.long : "");
  evMaxLen = Math.max(evMaxLen, option.textContent.length);
  evSel.appendChild(option);
}
evSel.value = currentEvent.key;

evSel.style.width = (evMaxLen + 4) + "ch";
let TOTAL = 1, MAXP = 1, MAXPX = {};
const val = vector => currentEvent.get(vector);
const mag = Math.abs;

function recomputeScale() {
  TOTAL = currentEvent.get(model.meta.totals) || 1;
  let max = 0;
  for (const file of Object.values(files)) {
    for (const rec of Object.values(file.lines)) {
      const self = mag(val(rec[0]));
      if (self > max) max = self;
    }
  }
  MAXP = Math.max(100 * max / TOTAL, 0.0001);
  MAXPX = {};
  for (const extra of EXTRA) {
    let extraMax = 0;
    for (const file of Object.values(files)) {
      for (const rec of Object.values(file.lines)) {
        const self = mag(extra.get(rec[0]));
        if (self > extraMax) extraMax = self;
      }
    }
    const extraTotal = extra.get(model.meta.totals) || 1;
    MAXPX[extra.key] = {
      total: extraTotal,
      maxP: Math.max(100 * extraMax / extraTotal, 0.0001),
    };
  }
}

const esc = value => String(value)
  .replace(/&/g, "&amp;").replace(/</g, "&lt;")
  .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const pct = value => 100 * value / TOTAL;
let fmtP = percent => percent >= 9.95 ? percent.toFixed(1) + "%"
  : percent >= 0.01 ? percent.toFixed(2) + "%"
  : percent > 0 ? "<0.01%" : "";
const fmtPct = value => fmtP(pct(value));
const fmtN = value => value.toLocaleString("en-US");

let fmtH = value => {
  let unit = "";
  for (const nextUnit of ["K", "M", "G", "T"]) {
    if (value < 999.5) break;
    value /= 1000;
    unit = nextUnit;
  }
  return (unit && value < 9.95 ? value.toFixed(1) : value.toFixed(0)) + unit;
};
const num = value => ({ text: fmtH(value), title: fmtN(value) });
let HOT = "Hottest", HOT_LINES = "hottest lines";
const SELF = {
  label: "self",
  title: "share of the total spent on this line/function itself,"
    + " not in what it calls",
  num: true,
};
const HAS_CALLS = functions.some(func => func.callers.length > 0);

const DIFF = !!model.meta.diff;
if (DIFF) {
  const sign = value => value > 0 ? "+" : "\\u2212";
  const plainP = fmtP, plainH = fmtH;
  fmtP = percent => percent ? sign(percent) + plainP(mag(percent)) : "";
  fmtH = value => value ? sign(value) + plainH(mag(value)) : "0";
  HOT = "Most changed";
  HOT_LINES = "most changed lines";
  SELF.title = "the line/function's own change, as a share of every"
    + " change added up; + is more than the baseline, \\u2212 is less";
}

const PMIN = 0.001;
function heatP(percent, maxP) {
  const sign = DIFF && percent < 0 ? -1 : 1;
  percent = mag(percent);
  if (percent <= 0) return 0;
  if (scale === "linear") return sign * Math.min(1, percent / maxP);
  if (percent < PMIN) return 0;
  const span = Math.log10(Math.max(maxP, PMIN * 10) / PMIN);
  return sign * Math.min(1, Math.log10(percent / PMIN) / span);
}
function heatT(cost, maxP) { return heatP(pct(cost), maxP); }

const RGB = hex =>
  [1, 3, 5].map(index => parseInt(hex.slice(index, index + 2), 16));
const STOPS = model.theme.heat.map(RGB), BG = RGB(model.theme.bg);
function heatStyle(heat, aMin, aMax) {
  const magnitude = mag(heat);
  if (magnitude <= 0) return "";
  const scaled = (DIFF ? (heat + 1) * 0.5 : heat) * (STOPS.length - 1);
  const index = Math.min(Math.max(Math.floor(scaled), 0), STOPS.length - 2);
  const frac = scaled - index;
  const alpha = aMin + (aMax - aMin) * magnitude;
  const mixed = [0, 1, 2].map(channel => {
    const lo = STOPS[index][channel], hi = STOPS[index + 1][channel];
    return Math.round(
      BG[channel] + (lo + (hi - lo) * frac - BG[channel]) * alpha);
  });
  const lum =
    (0.2126 * mixed[0] + 0.7152 * mixed[1] + 0.0722 * mixed[2]) / 255;
  const fg = lum > 0.5 ? model.theme.fgDark : model.theme.fgLight;
  return `background:rgb(${mixed.join(",")});color:${fg}`;
}
const heatBg = heat => heatStyle(heat, 0.18, 0.92);
const heatBgSoft = heat => heatStyle(heat, 0.12, 0.55);

const fnCalls = functions.map(func =>
  func.callers.reduce((sum, caller) => sum + caller[4], 0));
const CALLS_TOTAL = fnCalls.reduce((sum, count) => sum + count, 0) || 1;
const CALLS_MAX = fnCalls.reduce((max, count) => Math.max(max, count), 0);
const CALLS_MAXP = Math.max(100 * CALLS_MAX / CALLS_TOTAL, 0.0001);
const numCalls = count => count ? {
  text: fmtH(count),
  title: fmtN(count) + " calls",
  style: heatBg(heatP(100 * count / CALLS_TOTAL, CALLS_MAXP)),
} : "";

const enc = value => encodeURIComponent(value).replace(/%2F/g, "/");
function hashOf(state) {
  const parts = [];
  if (state.fn) parts.push("fn=" + enc(state.fn));
  else if (state.file) {
    parts.push("f=" + enc(state.file));
    if (state.line) parts.push("l=" + state.line);
  }
  if (EVS.length > 1) parts.push("e=" + enc(state.ev || currentEvent.key));
  return parts.length ? "#" + parts.join("&") : "";
}
const hashFor = (path, line) => hashOf({ file: path, line: line });
const hashForFn = name => hashOf({ fn: name });
function fnName(index) {
  return (index != null && functions[index]) ? functions[index].name : "?";
}

function link(path, line, text) {
  if (!files[path] || !line) return esc(text);
  return `<a href="${hashFor(path, line)}">${esc(text)}</a>`;
}

const fnLinkable = funcIndex => funcIndex != null && functions[funcIndex]
  && functions[funcIndex].line && files[functions[funcIndex].file];
function linkFn(funcIndex, text) {
  if (!fnLinkable(funcIndex)) return esc(text);
  const href = hashForFn(functions[funcIndex].name);
  return `<a href="${href}">${esc(text)}</a>`;
}
const SYMBOL_CHARS = 20;
const SRC_COLS = 80;
const HOT_CHIPS = 10;

const PAD = 3;

const cellOf = value => (value && typeof value === "object") ? value
  : { text: value == null ? "" : String(value) };

function colWidths(cols, cellRows) {
  return cols.map((col, colIndex) => {
    let width = col.label.length;
    if (col.width != null) width = Math.max(width, col.width);
    else {
      for (const row of cellRows) {
        if (!row[colIndex]) continue;
        width = Math.max(width, (row[colIndex].text || "").length);
      }
      if (col.clip != null) {
        width = Math.max(col.label.length, Math.min(width, col.clip));
      }
    }
    return width + PAD;
  });
}
function table(key, cols, rows, opts) {
  opts = opts || {};
  const cellRows = rows.map(row => row.map(cellOf));
  const widths = colWidths(cols, cellRows);
  const tableCls = ["cols", opts.fill ? "fill" : "", opts.cls || ""]
    .filter(Boolean).join(" ");
  let html = opts.bare ? "" : `<div class="tbl">`;
  html += `<div class="tbl-cols"><table class="${tableCls}"`
    + ` data-key="${esc(key)}"><colgroup>`;
  cols.forEach((col, colIndex) => {
    const colCls = [colIndex % 2 ? "alt" : "", col.grow ? "grow" : ""]
      .filter(Boolean).join(" ");
    html += `<col${colCls ? ` class="${colCls}"` : ""}`
      + ` data-min="${col.label.length + PAD}ch"`
      + ` style="width:${widths[colIndex]}ch">`;
  });
  html += `</colgroup><thead><tr>`;
  for (const col of cols) {
    html += `<th${col.num ? ' class="n"' : ""}`
      + `${col.title ? ` title="${esc(col.title)}"` : ""}>`
      + `${esc(col.label)}</th>`;
  }
  html += `</tr></thead><tbody>`;
  cellRows.forEach((row, rowIndex) => {
    const href = opts.rowHref && opts.rowHref[rowIndex];
    html += href ? `<tr class="rowlink" data-href="${esc(href)}">`
      : opts.rowAttrs ? `<tr ${opts.rowAttrs[rowIndex]}>` : "<tr>";
    row.forEach((cellValue, colIndex) => {
      const col = cols[colIndex] || {};
      const cls = [col.num ? "n" : "", col.cls || "", cellValue.cls || ""]
        .filter(Boolean).join(" ");
      const text = cellValue.text || "";
      const clipped = text.length + PAD > widths[colIndex];
      const title = cellValue.title || (clipped ? text : "");
      html += `<td${cls ? ` class="${cls}"` : ""}`
        + `${cellValue.style ? ` style="${cellValue.style}"` : ""}`
        + `${title ? ` title="${esc(title)}"` : ""}>`
        + `${cellValue.html != null ? cellValue.html : esc(text)}</td>`;
    });
    html += "</tr>";
  });
  html += `</tbody></table></div>`;
  return opts.bare ? html : html + `</div>`;
}

function tableText(cols, rows) {
  const cellRows = rows.map(row => row.map(cellOf));
  const widths = cols.map((col, colIndex) => {
    let width = col.label.length;
    for (const row of cellRows) {
      if (!row[colIndex]) continue;
      width = Math.max(width, (row[colIndex].text || "").length);
    }
    return width;
  });
  const pad = (text, width, numeric) =>
    numeric ? text.padStart(width) : text.padEnd(width);
  const line = cells => "| " + cells
    .map((text, colIndex) => pad(text, widths[colIndex], cols[colIndex].num))
    .join(" | ") + " |";
  const out = [line(cols.map(col => col.label))];
  const rule = cols.map((col, colIndex) => col.num
    ? "-".repeat(widths[colIndex] - 1) + ":"
    : "-".repeat(widths[colIndex]));
  out.push("| " + rule.join(" | ") + " |");
  for (const row of cellRows) {
    out.push(line(cols.map((col, colIndex) =>
      (row[colIndex] && row[colIndex].text) || "")));
  }
  return out.join("\\n");
}
const evCol = (event, extra) => Object.assign(
  { label: event.key, title: event.long, num: true }, extra || {});
const extraCols = () => EXTRA.map(extra => evCol(extra, {
  label: evLabel(extra),
  title: extra.long + " (share of that event's total)", cls: "x",
}));
function extraCells(vec) {
  return EXTRA.map(extra => {
    const self = extra.get(vec), maxEntry = MAXPX[extra.key];
    const percent = 100 * self / maxEntry.total;
    const heat = heatP(percent, maxEntry.maxP);
    return {
      text: self ? fmtP(percent) : "",
      style: heatBg(heat),
      cls: heat > 0.45 ? "hot" : "",
      title: extra.key + ": " + fmtN(self),
    };
  });
}

let TREE = null;
function buildTree() {
  const root = { name: "", path: "", dirs: new Map(), files: [], self: 0 };
  function insert(path, self, cold) {
    const parts = path.split("/");
    let node = root;
    for (let partIndex = 0; partIndex < parts.length - 1; partIndex++) {
      const segment = parts[partIndex];
      if (!node.dirs.has(segment)) {
        node.dirs.set(segment, {
          name: segment,
          path: node.path ? node.path + "/" + segment : segment,
          dirs: new Map(),
          files: [],
          self: 0,
        });
      }
      node = node.dirs.get(segment);
    }
    node.files.push({
      name: parts[parts.length - 1], path, self, cold, zero: self === 0,
    });
  }
  for (const path of Object.keys(files)) {
    insert(path, val(files[path].self), false);
  }
  for (const path of model.cold) insert(path, 0, true);
  (function sum(node) {
    let total = 0;
    for (const dir of node.dirs.values()) total += sum(dir);
    for (const file of node.files) total += file.self;
    node.self = total;
    return total;
  })(root);
  return root;
}
const openDirs = new Set(), coldOpen = new Set();
function cmp(nodeA, nodeB) {
  const byName = nodeA.name.localeCompare(nodeB.name);
  if (sortMode !== "heat") return byName;
  return (mag(nodeB.self) - mag(nodeA.self)) || byName;
}
function matches(path) { return !query || path.toLowerCase().includes(query); }
function subtreeMatches(node) {
  if (!query) return true;
  for (const file of node.files) if (matches(file.path)) return true;
  for (const dir of node.dirs.values()) if (subtreeMatches(dir)) return true;
  return false;
}
const MAXPDIR = 100;
function renderTree() {
  const out = [];
  function rec(node, depth) {
    const dirs = [...node.dirs.values()].filter(subtreeMatches).sort(cmp);
    for (const dir of dirs) {
      const open = query ? true : openDirs.has(dir.path);
      const heatStyleAttr = heatBgSoft(heatT(dir.self, MAXPDIR));
      out.push(`<div class="node dir${heatStyleAttr ? " heat" : ""}"`
        + ` data-dir="${esc(dir.path)}"`
        + ` style="padding-left:${6 + depth * 14}px;${heatStyleAttr}">`
        + `<span class="caret">${open ? "\\u25BC" : "\\u25B6"}</span>`
        + `<span class="name" title="${esc(dir.path)}">`
        + `${esc(dir.name)}/</span>`
        + `<span class="pct">${fmtPct(dir.self)}</span></div>`);
      out.push(`<div class="kids${open ? " open" : ""}">`);
      rec(dir, depth + 1);
      out.push(`</div>`);
    }
    const fileList = node.files.filter(file => matches(file.path)).sort(cmp);
    const fileRow = file => {
      const sel = file.path === curFile ? " sel" : "";
      const heatStyleAttr = file.cold ? ""
        : heatBgSoft(heatT(file.self, MAXPDIR));
      const cold = file.cold ? " (no samples; source not embedded)" : "";
      out.push(`<div class="node file${file.cold ? " cold" : ""}`
        + `${heatStyleAttr ? " heat" : ""}${sel}"`
        + ` data-file="${esc(file.path)}"`
        + ` style="padding-left:${6 + depth * 14}px;${heatStyleAttr}">`
        + `<span class="caret">\\u25B6</span>`
        + `<span class="name" title="${esc(file.path)}${cold}">`
        + `${esc(file.name)}</span>`
        + `<span class="pct">${fmtPct(file.self)}</span></div>`);
    };
    const zero = fileList.filter(file => file.zero);
    for (const file of fileList) if (!file.zero) fileRow(file);
    if (zero.length) {
      const show = query ? true : coldOpen.has(node.path);
      out.push(`<div class="node more" data-more="${esc(node.path)}"`
        + ` style="padding-left:${6 + depth * 14}px">`
        + `<span class="caret">${show ? "\\u25BC" : "\\u25B6"}</span>`
        + `<span class="name">no samples</span>`
        + `<span class="pct"></span></div>`);
      if (show) for (const file of zero) fileRow(file);
    }
  }
  rec(TREE, 0);
  treeEl.innerHTML = out.join("");
}
treeEl.addEventListener("click", clickEvent => {
  const node = clickEvent.target.closest(".node");
  if (!node) return;
  if (node.dataset.dir != null) {
    const path = node.dataset.dir;
    if (openDirs.has(path)) openDirs.delete(path); else openDirs.add(path);
    renderTree();
  } else if (node.dataset.more != null) {
    const path = node.dataset.more;
    if (coldOpen.has(path)) coldOpen.delete(path); else coldOpen.add(path);
    renderTree();
  } else if (node.dataset.file != null) {
    if (node.classList.contains("cold")) return;
    location.hash = hashFor(node.dataset.file);
  }
});
function revealInTree(path) {
  const parts = path.split("/");
  let acc = "";
  for (let partIndex = 0; partIndex < parts.length - 1; partIndex++) {
    acc = acc ? acc + "/" + parts[partIndex] : parts[partIndex];
    openDirs.add(acc);
  }
}

const entryIdx = {};
functions.forEach((func, index) => {
  if (!func.line) return;
  entryIdx[func.file] = entryIdx[func.file] || {};
  entryIdx[func.file][func.line] = index;
});

function topLines(count) {
  const all = [];
  for (const [path, file] of Object.entries(files)) {
    for (const [lineNumber, rec] of Object.entries(file.lines)) {
      const self = val(rec[0]);
      if (mag(self) <= 0) continue;
      all.push([path, +lineNumber, self, file.lineFunction[lineNumber]]);
    }
  }
  all.sort((rowA, rowB) => mag(rowB[2]) - mag(rowA[2]));
  return all.slice(0, count).map(entry => {
    const file = files[entry[0]];
    let snip = "";
    if (file.source != null) {
      const sourceLines = file.source.split("\\n");
      if (entry[1] >= 1 && entry[1] <= sourceLines.length) {
        snip = sourceLines[entry[1] - 1].trim().slice(0, 110);
      }
    }
    return [entry[0], entry[1], entry[2], entry[3], snip];
  });
}
function renderHome() {
  curFile = null;
  let html = `<div class="home">`;
  const lineRows = topLines(60);
  html += `<h2>${HOT} lines by ${esc(evLabel(currentEvent))}</h2>`
    + table("heat.home.lines",
    [{ label: "#", title: "rank", num: true }, SELF,
     { label: "function",
       title: `the function the line belongs to (first ${SYMBOL_CHARS}`
         + ` characters; drag the bar for more)`,
       width: SYMBOL_CHARS },
     { label: "defined at",
       title: "file:line; opens the listing there", clip: 28 },
     { label: "source",
       title: "the source line, trimmed; drag the bar for more", clip: 36 },
     evCol(currentEvent), ...extraCols()],
    lineRows.map((entry, index) => {
      const [path, lineNumber, cost, funcIndex, snip] = entry;
      const rec = files[path].lines[lineNumber];
      const loc = path + ":" + lineNumber;
      return [String(index + 1),
              { text: fmtPct(cost), style: heatBg(heatT(cost, MAXP)) },
              { text: fnName(funcIndex), title: fnName(funcIndex) },
              { text: loc, html: link(path, lineNumber, loc) },
              snip, num(cost), ...extraCells(rec[0])];
    }), { rowHref: lineRows.map(entry => hashFor(entry[0], entry[1])) });
  const topFunctions = functions
    .map((func, index) => [index, val(func.self)])
    .filter(entry => mag(entry[1]) > 0)
    .sort((entryA, entryB) => mag(entryB[1]) - mag(entryA[1]))
    .slice(0, 60);
  const callCols = HAS_CALLS ? [
    { label: "calls", title: "times the function was entered", num: true },
    { label: "incl", title: "total: self plus everything it calls",
      num: true },
  ] : [];
  html += `<h2>${HOT} functions by self ${esc(evLabel(currentEvent))}</h2>`
    + table("heat.home.functions",
    [{ label: "#", title: "rank", num: true }, SELF,
     { label: "function",
       title: `first ${SYMBOL_CHARS} characters; drag the bar for more`,
       width: SYMBOL_CHARS },
     { label: "defined at",
       title: "file:line of the function's first executed line", clip: 48 },
     ...callCols, ...extraCols()],
    topFunctions.map(([funcIndex, self], index) => {
      const func = functions[funcIndex];
      const loc = func.line ? func.file + ":" + func.line : func.file;
      const calls = HAS_CALLS
        ? [numCalls(fnCalls[funcIndex]), fmtPct(self + val(func.calls))] : [];
      return [String(index + 1),
              { text: fmtPct(self), style: heatBg(heatT(self, MAXP)) },
              { text: func.name, title: func.name },
              { text: loc, html: linkFn(funcIndex, loc) },
              ...calls, ...extraCells(func.self)];
    }), { rowHref: topFunctions.map(([funcIndex]) =>
      fnLinkable(funcIndex) ? hashForFn(functions[funcIndex].name) : "") });
  html += `</div>`;
  mainEl.innerHTML = html;
  mainEl.scrollTop = 0;
  renderTree();
  Theme.init(mainEl);
  minimapClear();
}

function renderFile(path, line) {
  const file = files[path];
  if (!file) { renderHome(); return; }
  const first = curFile !== path, keepTop = first ? -1 : mainEl.scrollTop;
  curFile = path;
  revealInTree(path);
  const lines = file.lines;
  let fileMax = 0;
  for (const rec of Object.values(lines)) {
    const self = mag(val(rec[0]));
    if (self > fileMax) fileMax = self;
  }
  const maxP = scale === "file" ? Math.max(pct(fileMax), 0.0001) : MAXP;
  let html = `<div class="srcwrap"><div class="fhead band">`
    + `<span class="path">${esc(path)}</span>`;
  const fileSelf = val(file.self);
  html += `<span class="stat" title="${fmtN(fileSelf)}">`
    + `self <b>${fmtPct(fileSelf) || "0%"}</b>`
    + ` (${fmtH(fileSelf)} ${esc(evLabel(currentEvent))})</span>`;
  for (const extra of EXTRA) {
    const self = extra.get(file.self);
    if (!self) continue;
    html += `<span class="stat"`
      + ` title="${esc(extra.long)}: ${fmtN(self)}">`
      + `${esc(evLabel(extra))}`
      + ` <b>${fmtP(100 * self / MAXPX[extra.key].total)}</b>`
      + ` (${fmtH(self)})</span>`;
  }
  if (file.group === "external") {
    html += `<span class="stat">not in this repo (${esc(file.raw)})</span>`;
  }
  html += `</div>`;
  if (file.source == null) {
    html += `<div class="nosrc">Source not available.</div></div>`;
    mainEl.innerHTML = html;
    renderTree();
    Theme.init(mainEl);
    minimapClear();
    return;
  }

  const hot = Object.keys(lines)
    .map(lineKey => [+lineKey, val(lines[lineKey][0])])
    .filter(entry => mag(entry[1]) > 0)
    .sort((entryA, entryB) => mag(entryB[1]) - mag(entryA[1]));
  const chips = hot.filter(entry => mag(pct(entry[1])) >= 0.01)
    .slice(0, HOT_CHIPS);
  if (chips.length) {
    html += `<div class="chips"><span class="lbl">${HOT_LINES}</span>`;
    for (const [lineNumber, cost] of chips) {
      html += `<span class="chip" data-goto="${lineNumber}"`
        + ` style="${heatBg(heatT(cost, maxP))}">`
        + `${lineNumber} \\u00b7 ${fmtPct(cost)}</span>`;
    }
    html += `</div>`;
  }

  const rows = [], attrs = [];
  const emitRow = (lineNumber, text) => {
    const rec = lines[lineNumber];
    const self = rec ? val(rec[0]) : 0, calls = rec ? val(rec[1]) : 0;
    const heat = heatT(self, maxP), heatStyleAttr = heatBg(heat);
    const funcIndex = file.lineFunction[lineNumber];
    const over = rec && rec[2] ? " over " + fmtH(rec[2]) + " calls" : "";
    const callsNote = HAS_CALLS
      ? `, ${fmtN(calls)} in calls${over}` : "";
    const inFn = funcIndex != null
      ? " \\u2014 in " + fnName(funcIndex) : "";
    const title = rec
      ? `${fmtN(self)} ${currentEvent.key} self${callsNote}${inFn}` : "";
    const cls = [rec ? "clickable" : "",
                 file.callees[lineNumber] ? "hasc" : ""]
      .filter(Boolean).join(" ");
    attrs.push(`id="L${lineNumber}"${cls ? ` class="${cls}"` : ""}`
      + ` data-ln="${lineNumber}"`
      + `${title ? ` title="${esc(title)}"` : ""}`);
    const callCell = HAS_CALLS ? [{
      text: calls ? fmtPct(calls) : "",
      style: heatBg(heatT(calls, maxP)),
    }] : [];
    rows.push([{ text: self ? fmtPct(self) : "", style: heatStyleAttr,
                 cls: heat > 0.45 ? "hot" : "" },
               { text: String(lineNumber), style: heatStyleAttr },
               { text, style: heatStyleAttr },
               ...callCell,
               ...(rec ? extraCells(rec[0]) : EXTRA.map(() => ""))]);
  };
  const sourceLines = file.source.split("\\n");
  if (sourceLines.length && sourceLines[sourceLines.length - 1] === "") {
    sourceLines.pop();
  }
  let nlines = sourceLines.length;
  for (let lineIndex = 0; lineIndex < sourceLines.length; lineIndex++) {
    emitRow(lineIndex + 1, sourceLines[lineIndex]);
  }
  for (const lineKey of Object.keys(lines)) {
    if (+lineKey <= sourceLines.length) continue;
    nlines = Math.max(nlines, +lineKey);
    emitRow(+lineKey, "(line beyond end of file: source changed since"
      + " the profile was taken)");
  }

  const callCol = HAS_CALLS ? [{
    label: "calls",
    title: "total cost of the calls made from the line, share of total",
    num: true,
    cls: "incl",
  }] : [];
  const cols = [evCol(currentEvent, {
                  title: currentEvent.long
                    + ", share of total, spent on the line itself",
                  cls: "self" }),
                { label: "line", num: true,
                  width: String(nlines).length + 2, cls: "ln" },
                { label: "source", width: SRC_COLS, grow: true, cls: "code" },
                ...callCol,
                ...extraCols()];
  html += table("heat.src", cols, rows,
    { rowAttrs: attrs, fill: 1, cls: "src", bare: true });
  html += `<div class="srctail"></div></div>`;
  mainEl.innerHTML = html;
  renderTree();

  minimapBuild();
  Theme.init(mainEl);
  srctailFit();
  if (!first) mainEl.scrollTop = keepTop;
  else if (!line) {
    const hottest = hot.length ? hot[0][0] : 0;
    const hottestRow = hottest ? document.getElementById("L" + hottest) : null;
    if (hottestRow) centerRow(hottestRow); else mainEl.scrollTop = 0;
  }
  minimapSync();
}

function rowOnScreen(rowEl) {
  const rowRect = rowEl.getBoundingClientRect();
  const mainRect = mainEl.getBoundingClientRect();
  return rowRect.top >= mainRect.top + coverH(rowEl.closest("table"))
    && rowRect.bottom <= mainRect.top + mainEl.clientHeight;
}

function coverH(table) {
  let height = table.tHead.rows[0].cells[0].getBoundingClientRect().height;
  for (const band of mainEl.querySelectorAll(".band")) {
    height += band.getBoundingClientRect().height;
  }
  return height;
}

function centerRow(rowEl) {
  const cover = coverH(rowEl.closest("table"));
  const rowRect = rowEl.getBoundingClientRect();
  const mainRect = mainEl.getBoundingClientRect();
  const detailEl = rowEl.nextElementSibling;
  const blockBottom = (detailEl && detailEl.classList.contains("detail"))
    ? detailEl.getBoundingClientRect().bottom : rowRect.bottom;
  const blockHeight = blockBottom - rowRect.top;
  const slack = (mainEl.clientHeight - cover - blockHeight) / 2;
  mainEl.scrollTop += rowRect.top - mainRect.top - cover - slack;
}

function srctailFit() {
  const tail = mainEl.querySelector(".srctail");
  const table = mainEl.querySelector("table.src");
  if (!tail || !table) return;
  const rows = table.tBodies[0].rows, last = rows[rows.length - 1];
  if (!last) return;
  const cover = coverH(table), rowHeight = last.getBoundingClientRect().height;
  tail.style.height =
    Math.max(0, (mainEl.clientHeight - cover - rowHeight) / 2) + "px";
}

const MM_MIN_COLS = 80;
const MM_MIN_LINES = 40;
let mmChPx = 0, mmScale = 1, mmCloneH = 0;
function minimapClear() {
  minimapEl.classList.add("empty");
  mmBox.innerHTML = "";
  mmViewport.hidden = true;
}
function minimapBuild() {
  const table = mainEl.querySelector("table.src");
  const tbody = table && table.tBodies[0];
  if (!tbody || tbody.rows.length < MM_MIN_LINES) { minimapClear(); return; }

  const probeCell = tbody.rows[0].querySelector("td.code");
  if (!probeCell) { minimapClear(); return; }
  const span = document.createElement("span");
  span.textContent = "0123456789";
  span.style.cssText =
    "position:absolute;visibility:hidden;white-space:pre;font:inherit";
  probeCell.appendChild(span);
  mmChPx = span.getBoundingClientRect().width / 10 || 7.2;
  probeCell.removeChild(span);

  const clone = document.createElement("table");
  clone.className = "src";
  const body = document.createElement("tbody");
  for (const row of tbody.rows) {
    if (row.classList.contains("detail")) continue;
    const code = row.querySelector("td.code");
    if (!code) continue;
    const cloneRow = document.createElement("tr");
    cloneRow.className = row.className;
    cloneRow.appendChild(code.cloneNode(true));
    body.appendChild(cloneRow);
  }
  clone.appendChild(body);
  mmBox.innerHTML = "";
  mmBox.appendChild(clone);
  minimapEl.classList.remove("empty");
  mmViewport.hidden = false;
  mmCloneH = clone.offsetHeight;
  minimapLayout();
}

function minimapLayout() {
  if (minimapEl.classList.contains("empty")) return;
  const bandW = minimapEl.clientWidth, bandH = minimapEl.clientHeight;

  mmScale = Math.min(1, bandW / (MM_MIN_COLS * mmChPx), bandH / mmCloneH);
  mmBox.style.transform = `scale(${mmScale})`;
  mmBox.style.transformOrigin = "top left";
  mmBox.style.width = (bandW / mmScale) + "px";
  minimapSync();
}

function mmGeom() {
  const table = mainEl.querySelector("table.src"), tbody = table.tBodies[0];
  const main = mainEl.getBoundingClientRect();
  const body = tbody.getBoundingClientRect();
  const detailEl = tbody.querySelector("tr.detail");
  const detail = detailEl && detailEl.getBoundingClientRect();
  const rows = body.height - (detail ? detail.height : 0);
  const above = yCoord => {
    let pixels = yCoord - body.top;
    if (detail) {
      pixels -= Math.max(0, Math.min(yCoord, detail.bottom) - detail.top);
    }
    return Math.max(0, Math.min(rows, pixels));
  };
  return {
    rows, above, cover: coverH(table), body, detail,
    top: main.top,
    bottom: main.top + mainEl.clientHeight,
    head: table.tHead.rows[0].cells[0].getBoundingClientRect().bottom,
  };
}
function minimapSync() {
  if (minimapEl.classList.contains("empty")) return;
  const geom = mmGeom(), scaledH = mmCloneH * mmScale;
  const rowStart = geom.above(geom.head), rowEnd = geom.above(geom.bottom);
  const boxHeight = Math.max(8, scaledH * (rowEnd - rowStart) / geom.rows);
  const boxTop = Math.min(scaledH - boxHeight, scaledH * rowStart / geom.rows);
  mmViewport.style.top = Math.max(0, boxTop) + "px";
  mmViewport.style.height = boxHeight + "px";
}

function mmScrollTo(row) {
  const geom = mmGeom();
  row = Math.max(0, Math.min(geom.rows, row));
  let yCoord = geom.body.top - geom.top + mainEl.scrollTop + row - geom.cover;
  if (geom.detail && geom.detail.top - geom.body.top < row) {
    yCoord += geom.detail.height;
  }
  const most = mainEl.scrollHeight - mainEl.clientHeight;
  mainEl.scrollTop = Math.max(0, Math.min(most, yCoord));
}
mainEl.addEventListener("scroll", minimapSync);
minimapEl.addEventListener("click", clickEvent => {
  if (clickEvent.target.closest("#mmViewport")) return;
  const geom = mmGeom(), scaledH = mmCloneH * mmScale;
  const offsetY = clickEvent.clientY - minimapEl.getBoundingClientRect().top;
  const row = offsetY / scaledH * geom.rows;
  mmScrollTo(row - (mainEl.clientHeight - geom.cover) / 2);
});
mmViewport.addEventListener("pointerdown", downEvent => {
  const startY = downEvent.clientY, startTop = mmViewport.offsetTop;
  const scaledH = mmCloneH * mmScale;
  mmViewport.classList.add("drag");
  if (mmViewport.setPointerCapture) {
    mmViewport.setPointerCapture(downEvent.pointerId);
  }
  const move = moveEvent => mmScrollTo(
    (startTop + moveEvent.clientY - startY) / scaledH * mmGeom().rows);
  const drag = on => {
    const method = on ? "addEventListener" : "removeEventListener";
    mmViewport[method]("pointermove", move);
    mmViewport[method]("pointerup", release);
    mmViewport[method]("pointercancel", release);
  };
  const release = () => {
    mmViewport.classList.remove("drag");
    drag(false);
  };
  drag(true);
  downEvent.preventDefault();
  downEvent.stopPropagation();
});

function detailLine() {
  const detailRow = mainEl.querySelector("tr.detail");
  return detailRow ? +detailRow.previousElementSibling.dataset.ln : 0;
}

function detailSet(line) {
  if (line === detailLine()) return;
  for (const detailRow of mainEl.querySelectorAll("tr.detail")) {
    detailRow.remove();
  }
  const row = line ? document.getElementById("L" + line) : null;
  if (row) {
    detailOpen(curFile, line, row);
    if (!rowOnScreen(row)) centerRow(row);
  }
  minimapSync();
}
function detailOpen(path, lineNumber, row) {
  const file = files[path];
  const callees = (file.callees[lineNumber] || []).slice()
    .sort((calleeA, calleeB) => val(calleeB[3]) - val(calleeA[3]));
  const funcIndex = (entryIdx[path] || {})[lineNumber];
  const lineFuncIndex = file.lineFunction[lineNumber];
  const rec = file.lines[lineNumber] || [[], [], 0];
  const fnCol = label => ({
    label,
    title: `first ${SYMBOL_CHARS} characters; drag the bar for more`,
    width: SYMBOL_CHARS,
  });
  const locCol = {
    label: "defined at",
    title: "file:line of the function's first executed line",
    clip: 48,
  };
  const callCost = val(rec[1]);
  const self = val(rec[0]);
  const selfLabel = funcIndex != null ? "self" : "line self";
  const statCols = [{ label: "metric" }, { label: "share", num: true },
                    { label: "amount", num: true }];
  const statRows = [[
    { text: `${selfLabel} ${evLabel(currentEvent)}`,
      title: SELF.title },
    fmtPct(self) || "0%",
    num(self),
  ]];
  if (callCost) {
    statRows.push([{ text: "calls" }, fmtPct(callCost), num(callCost)]);
    statRows.push([{ text: "call count" }, "", numCalls(rec[2])]);
  }
  for (const extra of EXTRA) {
    const extraSelf = extra.get(rec[0]);
    if (!extraSelf) continue;
    statRows.push([{ text: evLabel(extra), title: extra.long },
                   fmtP(100 * extraSelf / MAXPX[extra.key].total),
                   num(extraSelf)]);
  }
  const inFn = lineFuncIndex != null ? " in " + fnName(lineFuncIndex) : "";
  const headLine = `${path}:${lineNumber}${inFn}`;
  const inFnHtml = lineFuncIndex != null
    ? " in <b>" + esc(fnName(lineFuncIndex)) + "</b>" : "";
  let html = `<div class="dbox">`;
  html += `<a href="#" class="dclose" title="close">[X]</a>`;
  html += `<div>${esc(path)}:${lineNumber}${inFnHtml}</div>`;
  html += table("heat.detail.stats", statCols, statRows);
  const textParts = [headLine + "\\n" + tableText(statCols, statRows)];
  if (callees.length) {
    const cols = [{ label: "% of total", num: true }, evCol(currentEvent),
                  { label: "call count", num: true }, fnCol("callee"),
                  locCol];
    const rows = callees.map(
      ([calleeIndex, callFile, callLine, vec, count]) => {
        const loc = callLine ? callFile + ":" + callLine : callFile;
        return [fmtPct(val(vec)), num(val(vec)), numCalls(count),
                { text: fnName(calleeIndex), title: fnName(calleeIndex) },
                { text: loc, html: linkFn(calleeIndex, loc) }];
      });
    const heading = `calls from this line (total ${evLabel(currentEvent)})`;
    html += `<h4>${esc(heading)}</h4>`
      + table("heat.detail.callees", cols, rows);
    textParts.push(heading + "\\n" + tableText(cols, rows));
  }
  if (funcIndex != null) {
    const func = functions[funcIndex];
    const callers = func.callers.slice()
      .sort((callerA, callerB) => callerB[4] - callerA[4]);
    const fnSelf = fmtPct(val(func.self)) || "0%";
    const fnTotal = fmtPct(val(func.self) + val(func.calls)) || "0%";
    const heading = HAS_CALLS
      ? `${func.name} by call count: self ${fnSelf}, total ${fnTotal}.`
      : `${func.name}: self ${fnSelf}.`;
    html += `<h4>${esc(heading)}</h4>`;
    if (callers.length) {
      const cols = [{ label: "call count", num: true },
                    { label: "% of total", num: true }, evCol(currentEvent),
                    fnCol("caller"),
                    { label: "called at", title: "file:line of the call",
                      clip: 48 }];
      const rows = callers.map(
        ([callerIndex, callFile, callLine, vec, count]) => {
          const loc = callLine ? callFile + ":" + callLine : callFile;
          return [numCalls(count), fmtPct(val(vec)), num(val(vec)),
                  { text: fnName(callerIndex), title: fnName(callerIndex) },
                  { text: loc, html: link(callFile, callLine, loc) }];
        });
      html += table("heat.detail.callers", cols, rows);
      textParts.push(heading + "\\n" + tableText(cols, rows));
    } else if (HAS_CALLS) {
      const none = "(no recorded caller \\u2014 a root or a resolver stub)";
      html += `<div class="dim">${none}</div>`;
      textParts.push(heading + "\\n" + none);
    } else {
      textParts.push(heading);
    }
  }
  html += `<div class="dactions"><a href="#" class="dcopy">copy</a>`
    + ` <a href="#" class="dclose2">close</a></div>`;
  html += `</div>`;
  const detailRow = document.createElement("tr");
  detailRow.className = "detail";
  detailRow.innerHTML = `<td colspan="${row.cells.length}">${html}</td>`;
  detailRow._copyText = textParts.join("\\n\\n");
  row.after(detailRow);
  Theme.init(detailRow);
}

mainEl.addEventListener("click", clickEvent => {
  const chip = clickEvent.target.closest(".chip");
  if (chip) { location.hash = hashFor(curFile, +chip.dataset.goto); return; }
  const copy = clickEvent.target.closest(".dcopy");
  if (copy) {
    clickEvent.preventDefault();
    navigator.clipboard.writeText(copy.closest("tr.detail")._copyText);
    return;
  }
  const close = clickEvent.target.closest(".dclose, .dclose2");
  if (close) {
    clickEvent.preventDefault();
    location.hash = hashFor(curFile);
    return;
  }
  if (clickEvent.target.closest("a")) return;
  const linkRow = clickEvent.target.closest("tr.rowlink");
  if (linkRow) { location.hash = linkRow.dataset.href; return; }
  const row = clickEvent.target.closest("tr.clickable");
  if (row && curFile) {
    const lineNumber = +row.dataset.ln;
    location.hash = lineNumber === detailLine()
      ? hashFor(curFile) : hashFor(curFile, lineNumber);
  }
});

let state = { file: null, line: 0, fn: null };
let shown = "";
function stateOf(hash) {
  const parsed = { file: null, line: 0, fn: null, ev: null };
  for (const part of (hash || "").replace(/^#/, "").split("&")) {
    const eqIndex = part.indexOf("=");
    if (eqIndex < 0) continue;
    let value;
    try {
      value = decodeURIComponent(part.slice(eqIndex + 1));
    } catch (decodeError) {
      continue;
    }
    const key = part.slice(0, eqIndex);
    if (key === "f") parsed.file = value;
    else if (key === "l") parsed.line = +value || 0;
    else if (key === "fn") parsed.fn = value;
    else if (key === "e") parsed.ev = value;
  }
  return parsed;
}
function applyEvent(key) {
  currentEvent = evByKey(key) || EVS[0];
  evSel.value = currentEvent.key;
  recomputeScale();
  TREE = buildTree();
  for (const dir of TREE.dirs.values()) {
    if (mag(dir.self) / TOTAL > 0.05) openDirs.add(dir.path);
  }
}
function syncHash() {
  const hash = hashOf(state);
  if (hash !== location.hash) history.replaceState(null, "", hash || "#");
  if (window.parent !== window) {
    window.parent.postMessage({ theme: "hash", hash: hash }, "*");
  }
}
function route() {
  const parsed = stateOf(location.hash);
  const event = evByKey(parsed.ev)
    || evByKey(model.meta.defaultEvent) || EVS[0];
  if (event.key !== currentEvent.key) applyEvent(event.key);
  let file = parsed.file, line = parsed.line, fn = parsed.fn;
  if (fn) {
    const func = functions.find(candidate => candidate.name === fn);
    if (func && func.line && files[func.file]) {
      file = func.file;
      line = func.line;
    }
    else { fn = null; file = null; line = 0; }
  }
  if (file && !files[file]) { file = null; line = 0; }

  const key = (file ? "file\\n" + file : "home")
    + "\\n" + currentEvent.key + "\\n" + scale;
  if (key !== shown) {
    shown = key;
    if (file) renderFile(file, line);
    else renderHome();
  }
  if (file) {
    if (line && !document.getElementById("L" + line)) line = 0;
    detailSet(line);
  }
  state = { file: file, line: line, fn: fn };
  syncHash();
}
window.addEventListener("hashchange", route);
window.addEventListener("message", messageEvent => {
  if (messageEvent.data === "theme:reset-cols") Theme.resetCols();
});

let mmResizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(mmResizeTimer);
  mmResizeTimer = setTimeout(() => { srctailFit(); minimapLayout(); }, 120);
});
evSel.addEventListener("change", changeEvent => {
  location.hash = hashOf(
    Object.assign({}, state, { ev: changeEvent.target.value }));
});
document.getElementById("scale").addEventListener("change", changeEvent => {
  scale = changeEvent.target.value;
  store.set("heat.scale", scale);
  shown = "";
  route();
});
document.getElementById("sort").addEventListener("change", changeEvent => {
  sortMode = changeEvent.target.value;
  store.set("heat.sort", sortMode);
  renderTree();
});
document.getElementById("q").addEventListener("input", inputEvent => {
  query = inputEvent.target.value.trim().toLowerCase();
  renderTree();
});
applyEvent(currentEvent.key);
route();
})();
</script>
"""

# The extra stylesheet the heat map needs on top of the shared theme.
_CSS = """\
body { display: flex; flex-direction: column; height: 100vh; }
#hdr { gap: 4px 14px; }
#hdr label { color: var(--muted); white-space: nowrap; }
#hdr input { width: 36ch; }
#layout { display: flex; flex: 1; min-height: 0; }
#tree { width: 280px; min-width: 120px; flex: none; overflow: auto;
  padding: 4px 0 24px; }
#main { flex: 1; min-width: 0; overflow: auto; background: var(--bg); }

.srcwrap { width: max-content; min-width: 100%; }

.srctail { height: 50vh; }

.srcwrap > :not(.tbl-cols) { contain: inline-size; }

#minimap { width: 110px; flex: none; overflow: hidden; position: relative;
  background: var(--bg); cursor: pointer; }
#minimap.empty { display: none; }
#mmBox { position: absolute; top: 0; left: 0; }

#mmBox table.src { border-collapse: collapse; table-layout: fixed;
  width: 100%; }
#mmBox table.src td { padding: 0; border: 0; white-space: pre;
  overflow: visible; }
#mmViewport { position: absolute; left: 0; right: 0;
  background: rgba(245, 246, 250, 0.36);
  border: 1px solid rgba(245, 246, 250, 0.55); cursor: grab; }
#mmViewport.drag { cursor: grabbing; }
.node { display: flex; align-items: center; gap: 4px; padding-right: 8px;
  cursor: pointer; white-space: nowrap; }
.node:hover { outline: 1px solid var(--link); outline-offset: -1px; }
.node.sel { background: var(--sel); }
.node .caret { width: 12px; flex: none; text-align: center;
  color: var(--muted); font-size: 9px; }
.node.file .caret { visibility: hidden; }
.node .name { flex: 1; min-width: 0; overflow: hidden;
  text-overflow: ellipsis; }
.node.dir .name { font-weight: 600; }
.node.cold .name { color: var(--muted); font-weight: 400; }
.node .pct { flex: none; width: 7ch; text-align: right;
  font-variant-numeric: tabular-nums; color: var(--muted); }
.node.heat .pct, .node.heat .caret { color: inherit; }
.node.cold .pct { visibility: hidden; }
.node.more .name { color: var(--muted); font-style: italic; }
.kids { display: none; }
.kids.open { display: block; }
.fhead { background: var(--sel); padding: 5px 14px;
  display: flex; gap: 4px 18px; align-items: baseline; flex-wrap: wrap; }
.fhead .path { font-weight: 600; }
.fhead .stat { color: var(--muted); }

.chips { display: flex; gap: 4px; flex-wrap: nowrap; padding: 5px 14px;
  background: var(--sel); overflow: hidden; }
.chips .lbl { color: var(--muted); align-self: center; margin-right: 4px;
  flex: none; }
.chip { padding: 0 7px; background: var(--bg-alt); cursor: pointer;
  flex: none; white-space: nowrap; }
.chip:hover { outline: 1px solid var(--link); outline-offset: -1px; }
.nosrc { padding: 8px 14px; color: var(--muted); }
table.src th { background: var(--sel); }
table.src > tbody > tr > td { padding-top: 0; padding-bottom: 0; }
table.src td.ln { color: var(--muted); user-select: none; }
tr.rowlink { cursor: pointer; }
table.src tr.clickable { cursor: pointer; }

table.src tr.clickable:hover td.ln { text-decoration: underline; }

table.src td.self, table.src td.incl, table.src td.x { color: var(--muted); }
table.src td.hot { font-weight: 600; }

table.src td.code { text-overflow: clip; white-space: pre; tab-size: 4; }
table.src tr.hasc td.ln::before { content: "\\25B8 "; color: var(--link); }

table.src tr.detail > td { white-space: normal; overflow: visible;
  padding: 0; }
.dbox { position: relative; margin: 3px 12px 8px; padding: 6px 12px;
  background: var(--panel); }
.dbox h4 { margin: 6px 0 2px; font-size: 12px; color: var(--muted);
  font-weight: 600; }
.dbox .dclose { position: absolute; top: 6px; right: 10px;
  color: var(--muted); }
.dbox .dclose:hover { color: var(--link); text-decoration: none; }
.dbox .tbl { background: var(--bg); }
.dactions { margin-top: 8px; }
.dactions a { color: var(--link); margin-right: 14px; }
.home { padding: 12px 14px 40px; }
.home h2:first-of-type { margin-top: 10px; }
@media (max-width: 720px) {
  #layout { flex-direction: column; }
  #tree { width: auto !important; max-height: 38vh; background: var(--panel); }
  .split, #minimap { display: none; }
  #hdr input { width: 12ch; }
}
"""

# The event the page opens on, when the profile can supply it.
_DEFAULT_EVENT = "CEst"

# Directories whose tracked .c/.h are listed even when nothing sampled them,
# so a file with no cost is visibly cold rather than simply missing.
_TREE = ("lib", "include", "src", "tests/perf")


# CallgrindToHeatmap - Turns one profile into a single self-contained page
# that shows cost per source line, with the source itself embedded.
class CallgrindToHeatmap:
    # CallRow - One end of one call edge, as the page's script reads it. Used
    # for a line's callees and for a function's callers alike.
    class CallRow(NamedTuple):
        # the other function, as an index into the functions list
        function: int
        # the file to open when it is clicked
        file: str
        # the line to jump to there
        line: int
        # what the calls cost between them
        cost: Costs
        # how many calls
        count_: int

    # LineCost - One source line's numbers.
    class LineCost(NamedTuple):
        # cost on the line itself
        self_cost: Costs
        # cost below the calls it makes
        calls_cost: Costs
        # how many calls it makes
        count_: int

    # FileModel - One source file as the page's script sees it.
    class FileModel(TypedDict):
        # the file's own cost
        self: Costs
        # cost below what it calls
        calls: Costs
        # the source text, embedded, or None when it is not on this box
        source: str | None
        # per line number, that line's numbers
        lines: dict[str, CallgrindToHeatmap.LineCost]
        # per line number, which function owns it
        lineFunction: dict[str, int]
        # per line number, what that line calls
        callees: dict[str, list[CallgrindToHeatmap.CallRow]]
        # repo, system or external
        group: Group
        # the path as callgrind spelled it
        raw: str

    # FunctionModel - One function as the page's script sees it.
    class FunctionModel(TypedDict):
        # its name
        name: str
        # where to open it
        file: str
        # the line to jump to
        line: int
        # cost in the function itself
        self: Costs
        # cost below what it calls
        calls: Costs
        # who calls it, most expensive first
        callers: list[CallgrindToHeatmap.CallRow]

    # MetaModel - What the page needs to label and scale everything. Not the
    # report's LABEL=VALUE header -- that is build_report.py's Header.
    class MetaModel(TypedDict):
        # the recorded events, in cost-vector order
        events: list[str]
        # each event spelled out, for tooltips
        eventLong: dict[str, str]
        # the events the page adds up itself
        derived: list[callgrind.ResolvedDerivedEvent]
        # which event the page opens on
        defaultEvent: str
        # what shares are taken against
        totals: Costs
        # signed numbers and a signed heat ramp
        diff: bool

    # HeatModel - The whole page's data, in one JSON blob.
    class HeatModel(TypedDict):
        # labels, totals and which event to show
        meta: CallgrindToHeatmap.MetaModel
        # the few theme values the script needs
        theme: theme.ThemeRuntime
        # every file that has samples, by display path
        files: dict[str, CallgrindToHeatmap.FileModel]
        # every function, indexed by the call rows
        functions: list[CallgrindToHeatmap.FunctionModel]
        # tracked files with no samples at all
        cold: list[str]

    # HeatArgs - What this tool reads, and the page it writes.
    class HeatArgs(NamedTuple):
        # the callgrind file(s), merged into one profile
        callgrind_file: list[str]
        # where the page goes
        output: str
        # the page title
        title: str
        # the input is a callgrind_diff.py delta
        diff: bool

    # FileTally - One file's numbers while they are still being added up.
    @dataclass
    class FileTally:
        # repo, system or external
        group: Group
        # the path as callgrind spelled it
        raw: str
        # the file's own cost so far
        self_cost: Costs
        # cost below what it calls, so far
        calls_cost: Costs
        # the source text once it has been read
        source: str | None = None
        # per line number, that line's tally
        lines: dict[str, CallgrindToHeatmap.LineTally] = field(
            default_factory=dict
        )
        # per line number, which function owns it
        line_function: dict[str, int] = field(default_factory=dict)
        # per line number, what that line calls
        callees: dict[str, list[CallgrindToHeatmap.CallRow]] = field(
            default_factory=dict
        )

        # Freeze the tally into the page's own shape, trailing zeros dropped.
        def emit(self) -> CallgrindToHeatmap.FileModel:
            def first(row: CallgrindToHeatmap.CallRow) -> int:
                return -(row.cost[0] if row.cost else 0)

            trim = CallgrindToHeatmap.costs_trim
            return {
                "self": trim(self.self_cost),
                "calls": trim(self.calls_cost),
                "source": self.source,
                "lines": {
                    line: CallgrindToHeatmap.LineCost(
                        trim(record.self_cost),
                        trim(record.calls_cost),
                        record.count,
                    )
                    for line, record in self.lines.items()
                },
                "lineFunction": self.line_function,
                "callees": {
                    line: sorted(rows, key=first)
                    for line, rows in self.callees.items()
                },
                "group": self.group,
                "raw": self.raw,
            }

        # One line's tally, started at zero the first time it is asked for.
        def line(
            self, line_number: int, event_count: int
        ) -> CallgrindToHeatmap.LineTally:
            record = self.lines.get(str(line_number))
            if record is None:
                record = self.lines[str(line_number)] = (
                    CallgrindToHeatmap.LineTally(
                        [0] * event_count, [0] * event_count
                    )
                )
            return record

    # LineTally - One line's numbers while they are still being added up.
    @dataclass
    class LineTally:
        # cost on the line itself, so far
        self_cost: Costs
        # cost below the calls it makes, so far
        calls_cost: Costs
        # how many calls it makes, so far
        count: int = 0

    # Drop trailing zeros, because every cost vector is the full event width
    # and the page does not need what it would only render blank.
    @staticmethod
    def costs_trim(costs: Costs) -> Costs:
        length = len(costs)
        while length and costs[length - 1] == 0:
            length -= 1
        return costs[:length]

    # Turn a finished model into a diff one: shares go against the summed
    # magnitude of every change, since the signed total is near zero.
    def diff_model(
        self, model: CallgrindToHeatmap.HeatModel, profile: callgrind.Profile
    ) -> None:
        model["meta"]["totals"] = callgrind_diff.profile_magnitudes(profile)
        model["meta"]["diff"] = True

    # Resolve every path once, qualifying an external file by its object so
    # two libraries' same-named headers stay apart.
    def display_paths(
        self, profile: callgrind.Profile, raw_files: Sequence[str]
    ) -> dict[str, callgrind.PathInfo]:
        info: dict[str, callgrind.PathInfo] = {}
        for raw in raw_files:
            path_info = callgrind.path_norm(raw)
            if path_info.group == "external":
                object_name = (
                    os.path.basename(profile.file_ob.get(raw, ""))
                    or "(unknown object)"
                )
                path_info = path_info._replace(
                    display=f"{object_name}/{path_info.display}"
                )
            info[raw] = path_info
        return info

    # Add every line, call and callee up per file, and read the source in.
    def files_model(
        self,
        profile: callgrind.Profile,
        info: dict[str, callgrind.PathInfo],
        function_index: dict[str, int],
    ) -> dict[str, CallgrindToHeatmap.FileModel]:
        event_count = len(profile.events)
        display = {raw: path_info.display for raw, path_info in info.items()}
        accumulators: dict[str, CallgrindToHeatmap.FileTally] = {}
        for raw, path_info in info.items():
            entry = accumulators.get(path_info.display)
            if entry is None:
                entry = accumulators[path_info.display] = (
                    CallgrindToHeatmap.FileTally(
                        group=path_info.group,
                        raw=raw
                        if path_info.group == "external"
                        else path_info.display,
                        self_cost=[0] * event_count,
                        calls_cost=[0] * event_count,
                    )
                )
            if entry.source is None and path_info.local:
                entry.source = self.source_read(path_info.local)
        for key, costs in profile.line_self.items():
            entry = accumulators[display[key.file]]
            callgrind.costs_add(entry.self_cost, costs)
            callgrind.costs_add(
                entry.line(key.line, event_count).self_cost, costs
            )
        for key, costs in profile.line_calls.items():
            entry = accumulators[display[key.file]]
            callgrind.costs_add(entry.calls_cost, costs)
            record = entry.line(key.line, event_count)
            callgrind.costs_add(record.calls_cost, costs)
            record.count += profile.line_call_count[key]
        for key, function in profile.line_function.items():
            accumulators[display[key.file]].line_function[str(key.line)] = (
                function_index[function]
            )
        for site, tally in profile.callees.items():
            entry_line = profile.function_entry.get(
                site.callee,
                callgrind.SourceLine(
                    profile.function_home.get(site.callee, "???"), 0
                ),
            )
            accumulators[display[site.file]].callees.setdefault(
                str(site.line), []
            ).append(
                CallgrindToHeatmap.CallRow(
                    function_index[site.callee],
                    display.get(entry_line.file, entry_line.file),
                    entry_line.line,
                    self.costs_trim(tally.costs),
                    tally.count,
                )
            )
        return {name: entry.emit() for name, entry in accumulators.items()}

    # Every function with its entry point and its callers, dearest first.
    def functions_model(
        self,
        profile: callgrind.Profile,
        info: dict[str, callgrind.PathInfo],
        function_names: Sequence[str],
        function_index: dict[str, int],
    ) -> list[CallgrindToHeatmap.FunctionModel]:
        display = {raw: path_info.display for raw, path_info in info.items()}
        functions: list[CallgrindToHeatmap.FunctionModel] = []
        for name in function_names:
            entry = profile.function_entry.get(
                name, callgrind.SourceLine(profile.function_home[name], 0)
            )
            callers = sorted(
                (
                    CallgrindToHeatmap.CallRow(
                        function_index[caller.function],
                        display.get(caller.file, caller.file),
                        caller.line,
                        self.costs_trim(tally.costs),
                        tally.count,
                    )
                    for caller, tally in profile.callers.get(name, {}).items()
                ),
                key=lambda row: -(row.cost[0] if row.cost else 0),
            )
            functions.append(
                {
                    "name": name,
                    "file": display.get(entry.file, entry.file),
                    "line": entry.line,
                    "self": self.costs_trim(
                        profile.function_self.get(name, [])
                    ),
                    "calls": self.costs_trim(
                        profile.function_calls.get(name, [])
                    ),
                    "callers": callers,
                }
            )
        return functions

    # The whole page's data: every file, every function, and the cold list.
    def model(
        self, profile: callgrind.Profile
    ) -> CallgrindToHeatmap.HeatModel:
        function_names = sorted(profile.function_home)
        function_index = {name: i for i, name in enumerate(function_names)}
        raw_files = sorted(
            {key.file for key in profile.line_self}
            | {key.file for key in profile.line_calls}
            | {entry.file for entry in profile.function_entry.values()}
        )
        info = self.display_paths(profile, raw_files)
        files = self.files_model(profile, info, function_index)
        functions = self.functions_model(
            profile, info, function_names, function_index
        )
        cold = sorted(
            relative
            for relative in self.repo_tracked_files()
            if relative not in files
        )
        default_event = (
            _DEFAULT_EVENT
            if _DEFAULT_EVENT in profile.event_names()
            else profile.events[0]
        )
        return {
            "meta": {
                "events": profile.events,
                "eventLong": {
                    name: profile.event_long.get(name, "")
                    for name in profile.event_names()
                },
                "derived": profile.resolved_derived_events(),
                "defaultEvent": default_event,
                "totals": profile.totals(),
                "diff": False,
            },
            "theme": theme.theme_runtime(),
            "files": files,
            "functions": functions,
            "cold": cold,
        }

    # Bake the model into the page. "</" is escaped so no embedded source can
    # close the script tag early.
    def render(self, model: CallgrindToHeatmap.HeatModel, title: str) -> str:
        data = json.dumps(model, separators=(",", ":"), ensure_ascii=False)
        data = data.replace("</", "<\\/")
        body = BODY.replace("__THEME_JS__", theme.theme_js()).replace(
            "__DATA__", data
        )
        return (
            '<!doctype html>\n<html lang="en">\n'
            '<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport"'
            ' content="width=device-width, initial-scale=1">\n'
            f"<title>{theme.html_escape(title)}</title>\n<style>\n"
            f"{theme.theme_css()}{_CSS}</style>\n"
            "</head>\n<body>\n" + body + "</body>\n</html>\n"
        )

    # Every tracked .c/.h under _TREE, so a file with no samples still shows.
    def repo_tracked_files(self) -> list[str]:
        try:
            output = subprocess.run(
                ["git", "-C", callgrind.REPO_ROOT, "ls-files", "--", *_TREE],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            return []
        return [
            line for line in output.split("\n") if line.endswith((".c", ".h"))
        ]

    # Read the profile, build the model and write the one page.
    def run(self, args: CallgrindToHeatmap.HeatArgs) -> None:
        profile = callgrind.profile_load(args.callgrind_file)
        model = self.model(profile)
        if args.diff:
            self.diff_model(model, profile)
        html = self.render(model, args.title)
        os.makedirs(
            os.path.dirname(os.path.abspath(args.output)), exist_ok=True
        )
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(html)
        embedded_count = sum(
            1
            for entry in model["files"].values()
            if entry["source"] is not None
        )
        print(
            f"files with samples: {len(model['files'])}"
            f" ({embedded_count} with source embedded),"
            f" cold files listed: {len(model['cold'])}, "
            f"functions: {len(model['functions'])}",
            file=sys.stderr,
        )
        print(
            f"wrote {args.output} ({len(html.encode('utf-8')):,} bytes)",
            file=sys.stderr,
        )

    # Read one source file to embed, or None when it is not on this box.
    def source_read(self, local: str) -> str | None:
        try:
            with open(local, "rb") as handle:
                data = handle.read()
        except OSError:
            return None
        return data.decode("utf-8", errors="replace")


# main - Build one heat map page from the given callgrind file(s).
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "callgrind_file",
        nargs="+",
        help="callgrind output file(s). several are merged into one profile",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="output .html path (directories are created)",
    )
    parser.add_argument("--title", required=True)
    parser.add_argument(
        "--diff",
        action="store_true",
        help="the callgrind file is a callgrind_diff.py delta: print "
        "signed numbers and take shares against the summed magnitude "
        "of every change",
    )
    namespace = parser.parse_args()
    CallgrindToHeatmap().run(
        CallgrindToHeatmap.HeatArgs(
            callgrind_file=namespace.callgrind_file,
            output=namespace.output,
            title=namespace.title,
            diff=namespace.diff,
        )
    )


if __name__ == "__main__":
    main()
