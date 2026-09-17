#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import posixpath
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, NamedTuple, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind as cg
import theme
from callgrind import Vec

Group = Literal["repo", "system", "external"]


class HeatArgs(NamedTuple):
    callgrind_file: list[str]
    output: str
    event: str
    repo_root: str
    tree: list[str]
    all_sources: bool
    title: str | None


class LineCost(NamedTuple):
    self_cost: Vec
    calls_cost: Vec
    count_: int


class CallRow(NamedTuple):
    fn: int
    file: str
    line: int
    cost: Vec
    count_: int


class FileModel(TypedDict):
    self: Vec
    calls: Vec
    src: str | None
    lines: dict[str, LineCost]
    lfn: dict[str, int]
    callees: dict[str, list[CallRow]]
    group: Group
    raw: str


class FunctionModel(TypedDict):
    name: str
    file: str
    line: int
    self: Vec
    calls: Vec
    callers: list[CallRow]


class MetaModel(TypedDict):
    events: list[str]
    eventLong: dict[str, str]
    derived: list[cg.DerivedIndexed]
    defaultEvent: str
    totals: Vec


class HeatModel(TypedDict):
    meta: MetaModel
    theme: theme.ThemeRuntime
    files: dict[str, FileModel]
    functions: list[FunctionModel]
    cold: list[str]


class PathInfo(NamedTuple):
    display: str
    local: str | None
    group: Group


def path_norm(path: str, repo_root: str) -> PathInfo:
    if path == "???":
        return PathInfo("(unknown)", None, "external")
    root = repo_root.rstrip("/") + "/"
    if os.path.isabs(path):
        path = posixpath.normpath(path)
    if path.startswith(root):
        rel = path[len(root):]
        return PathInfo(rel, os.path.join(repo_root, rel), "repo")
    if os.path.isabs(path):
        if os.path.isfile(path):
            return PathInfo(path.lstrip("/"), path, "system")
        return PathInfo(path.lstrip("/"), None, "external")
    cand = os.path.join(repo_root, path)
    if os.path.isfile(cand):
        return PathInfo(posixpath.normpath(path), cand, "repo")
    return PathInfo(posixpath.normpath(path), None, "external")


def source_read(local: str) -> str | None:
    try:
        with open(local, "rb") as f:
            data = f.read()
    except OSError:
        return None
    return data.decode("utf-8", errors="replace")


def repo_tracked_files(repo_root: str, dirs: Sequence[str]) -> list[str]:
    if not dirs:
        return []
    try:
        out = subprocess.run(
            ["git", "-C", repo_root, "ls-files", "--", *dirs],
            check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [ln for ln in out.split("\n") if ln.endswith((".c", ".h"))]


def vec_trim(vec: Vec) -> Vec:
    n = len(vec)
    while n and vec[n - 1] == 0:
        n -= 1
    return vec[:n]


@dataclass
class _LineAcc:
    self_cost: Vec
    calls_cost: Vec
    count: int = 0


@dataclass
class _FileAcc:
    group: Group
    raw: str
    self_cost: Vec
    calls_cost: Vec
    src: str | None = None
    lines: dict[str, _LineAcc] = field(default_factory=dict)
    lfn: dict[str, int] = field(default_factory=dict)
    callees: dict[str, list[CallRow]] = field(default_factory=dict)

    def line(self, ln: int, nev: int) -> _LineAcc:
        rec = self.lines.get(str(ln))
        if rec is None:
            rec = self.lines[str(ln)] = _LineAcc([0] * nev, [0] * nev)
        return rec

    def emit(self) -> FileModel:
        def first(row: CallRow) -> int:
            return -(row.cost[0] if row.cost else 0)
        return {"self": vec_trim(self.self_cost), "calls": vec_trim(self.calls_cost), "src": self.src,
                "lines": {ln: LineCost(vec_trim(r.self_cost), vec_trim(r.calls_cost), r.count)
                          for ln, r in self.lines.items()},
                "lfn": self.lfn,
                "callees": {ln: sorted(rows, key=first) for ln, rows in self.callees.items()},
                "group": self.group, "raw": self.raw}


def model_build(p: cg.Profile, args: HeatArgs) -> HeatModel:
    repo_root = os.path.abspath(args.repo_root)
    nev = len(p.events)

    fn_names = sorted(p.fn_home)
    fn_index = {n: i for i, n in enumerate(fn_names)}

    raw_files = sorted({k.file for k in p.line_self} | {k.file for k in p.line_calls}
                       | {e.file for e in p.fn_entry.values()})
    info: dict[str, PathInfo] = {}
    for raw in raw_files:
        pi = path_norm(raw, repo_root)
        if pi.group == "external":
            ob = os.path.basename(p.file_ob.get(raw, "")) or "(unknown object)"
            pi = pi._replace(display=f"{ob}/{pi.display}")
        info[raw] = pi
    disp = {raw: pi.display for raw, pi in info.items()}

    acc: dict[str, _FileAcc] = {}
    for raw in raw_files:
        pi = info[raw]
        e = acc.get(pi.display)
        if e is None:
            e = acc[pi.display] = _FileAcc(group=pi.group, raw=raw if pi.group == "external" else pi.display,
                                           self_cost=[0] * nev, calls_cost=[0] * nev)
        if e.src is None and pi.local:
            e.src = source_read(pi.local)
    for key, vec in p.line_self.items():
        e = acc[disp[key.file]]
        cg.vec_add(e.self_cost, vec)
        cg.vec_add(e.line(key.line, nev).self_cost, vec)
    for key, vec in p.line_calls.items():
        e = acc[disp[key.file]]
        cg.vec_add(e.calls_cost, vec)
        rec = e.line(key.line, nev)
        cg.vec_add(rec.calls_cost, vec)
        rec.count += p.line_callcount[key]
    for key, fn in p.line_fn.items():
        acc[disp[key.file]].lfn[str(key.line)] = fn_index[fn]
    for site, cc in p.callees.items():
        entry = p.fn_entry.get(site.callee, cg.LineKey(p.fn_home.get(site.callee, "???"), 0))
        acc[disp[site.file]].callees.setdefault(str(site.line), []).append(
            CallRow(fn_index[site.callee], disp.get(entry.file, entry.file), entry.line, vec_trim(cc.cost), cc.count))
    files: dict[str, FileModel] = {d: e.emit() for d, e in acc.items()}

    functions: list[FunctionModel] = []
    for name in fn_names:
        entry = p.fn_entry.get(name, cg.LineKey(p.fn_home[name], 0))
        callers = sorted(
            (CallRow(fn_index[c.fn], disp.get(c.file, c.file), c.line, vec_trim(cc.cost), cc.count)
             for c, cc in p.callers.get(name, {}).items()),
            key=lambda r: -(r.cost[0] if r.cost else 0))
        functions.append({
            "name": name,
            "file": disp.get(entry.file, entry.file),
            "line": entry.line,
            "self": vec_trim(p.fn_self.get(name, [])),
            "calls": vec_trim(p.fn_calls.get(name, [])),
            "callers": callers,
        })

    cold: list[str] = []
    for rel in repo_tracked_files(repo_root, args.tree):
        if rel in files:
            continue
        if args.all_sources:
            files[rel] = {"self": [], "calls": [], "src": source_read(os.path.join(repo_root, rel)),
                          "lines": {}, "lfn": {}, "callees": {}, "group": "repo", "raw": rel}
        else:
            cold.append(rel)

    default_event = args.event if args.event in p.event_names() else (p.events[0] if p.events else "Ir")
    return {
        "meta": {
            "events": p.events,
            "eventLong": {n: p.event_long.get(n, "") for n in p.event_names()},
            "derived": p.derived_terms(),
            "defaultEvent": default_event,
            "totals": p.totals(),
        },
        "theme": theme.theme_runtime(),
        "files": files,
        "functions": functions,
        "cold": sorted(cold),
    }


CSS = """\
body { display: flex; flex-direction: column; height: 100vh; }
#hdr { gap: 4px 14px; }
#hdr label { color: var(--muted); white-space: nowrap; }
#hdr input { width: 36ch; }
#layout { display: flex; flex: 1; min-height: 0; }
#tree { width: 280px; min-width: 120px; flex: none; overflow: auto; padding: 4px 0 24px; }
#main { flex: 1; min-width: 0; overflow: auto; background: var(--bg); }

.srcwrap { width: max-content; min-width: 100%; }

.srctail { height: 50vh; }

.srcwrap > :not(.tbl-cols) { contain: inline-size; }

#minimap { width: 110px; flex: none; overflow: hidden; position: relative;
  background: var(--bg); cursor: pointer; }
#minimap.empty { display: none; }
#mmBox { position: absolute; top: 0; left: 0; }

#mmBox table.src { border-collapse: collapse; table-layout: fixed; width: 100%; }
#mmBox table.src td { padding: 0; border: 0; white-space: pre; overflow: visible; }
#mmViewport { position: absolute; left: 0; right: 0; background: rgba(245, 246, 250, 0.36);
  border: 1px solid rgba(245, 246, 250, 0.55); cursor: grab; }
#mmViewport.drag { cursor: grabbing; }
.node { display: flex; align-items: center; gap: 4px; padding-right: 8px; cursor: pointer; white-space: nowrap; }
.node:hover { outline: 1px solid var(--link); outline-offset: -1px; }
.node.sel { background: var(--sel); }
.node .caret { width: 12px; flex: none; text-align: center; color: var(--muted); font-size: 9px; }
.node.file .caret { visibility: hidden; }
.node .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.node.dir .name { font-weight: 600; }
.node.cold .name { color: var(--muted); font-weight: 400; }
.node .pct { flex: none; width: 7ch; text-align: right; font-variant-numeric: tabular-nums; color: var(--muted); }
.node.heat .pct, .node.heat .caret { color: inherit; }
.node.cold .pct { visibility: hidden; }
.node.more .name { color: var(--muted); font-style: italic; }
.kids { display: none; }
.kids.open { display: block; }
.fhead { background: var(--panel); padding: 5px 14px;
  display: flex; gap: 4px 18px; align-items: baseline; flex-wrap: wrap; }
.fhead .path { font-weight: 600; }
.fhead .stat { color: var(--muted); }

.chips { display: flex; gap: 4px; flex-wrap: nowrap; padding: 5px 14px; background: var(--panel); overflow: hidden; }
.chips .lbl { color: var(--muted); align-self: center; margin-right: 4px; flex: none; }
.chip { padding: 0 7px; background: var(--bg-alt); cursor: pointer; flex: none; white-space: nowrap; }
.chip:hover { outline: 1px solid var(--link); outline-offset: -1px; }
.nosrc { padding: 8px 14px; color: var(--muted); }
table.src > tbody > tr > td { padding-top: 0; padding-bottom: 0; }
table.src td.ln { color: var(--muted); user-select: none; }
tr.rowlink { cursor: pointer; }
table.src tr.clickable { cursor: pointer; }

table.src tr.clickable:hover td.ln { text-decoration: underline; }

table.src td.self, table.src td.incl, table.src td.x { color: var(--muted); }
table.src td.hot { font-weight: 600; }

table.src td.code { text-overflow: clip; white-space: pre; tab-size: 4; }
table.src tr.hasc td.ln::before { content: "\\25B8 "; color: var(--link); }

table.src tr.detail > td { white-space: normal; overflow: visible; padding: 0; }
.dbox { position: relative; margin: 3px 12px 8px; padding: 6px 12px; background: var(--panel); }
.dbox h4 { margin: 6px 0 2px; font-size: 12px; color: var(--muted); font-weight: 600; }
.dbox .dclose { position: absolute; top: 6px; right: 10px; color: var(--muted); }
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

BODY = """<div id="hdr" class="strip">
  <label>event <select id="event"></select></label>
  <label>scale <select id="scale">
    <option value="global">log, global</option>
    <option value="file">log, per file</option>
    <option value="linear">linear, global</option>
  </select></label>
  <label>tree <select id="sort"><option value="heat">by heat</option><option value="name">by name</option></select></label>
  <label>search <input id="q" type="search" placeholder="file name\u2026"></label>
</div>
<div id="layout">
  <nav id="tree"></nav>
  <div id="split" class="split" title="drag to resize"></div>
  <section id="main"></section>
  <div id="minimap" class="empty"><div id="mmBox"></div><div id="mmViewport" hidden></div></div>
</div>
<script id="heatdata" type="application/json">__DATA__</script>
<script>
__THEME_JS__
</script>
<script>(function () {
"use strict";
const D = JSON.parse(document.getElementById("heatdata").textContent);
const files = D.files, fns = D.functions;
const treeEl = document.getElementById("tree"), mainEl = document.getElementById("main");
const minimapEl = document.getElementById("minimap"), mmBox = document.getElementById("mmBox"), mmViewport = document.getElementById("mmViewport");
const store = Theme.store;
let scale = store.get("heat.scale") || "global", sortMode = store.get("heat.sort") || "heat", curFile = null, query = "";
document.getElementById("scale").value = scale;
document.getElementById("sort").value = sortMode;
Theme.splitter(document.getElementById("split"), treeEl, "heat.tree", 120);

const at = (v, i) => (v && i < v.length) ? v[i] : 0;
const EVS = [];
D.meta.events.forEach((n, i) => { if (at(D.meta.totals, i) > 0) EVS.push({ key: n, long: D.meta.eventLong[n] || "", get: v => at(v, i) }); });
for (const [n, terms, long] of D.meta.derived) {
  const get = v => terms.reduce((s, t) => s + t[0] * at(v, t[1]), 0);
  if (get(D.meta.totals) > 0) EVS.push({ key: n, long: long || D.meta.eventLong[n] || "", get, derived: true });
}
const evByKey = k => EVS.find(e => e.key === k);
let ev = evByKey(D.meta.defaultEvent) || EVS[0];
const EXTRA = ["D1m", "DLm", "Bcm"].map(evByKey).filter(Boolean);

const EVENT_SHORT = {
  Ir: "instructions", Dr: "data reads", Dw: "data writes",
  I1mr: "L1 icache miss", D1mr: "L1 dcache read miss", D1mw: "L1 dcache write miss",
  ILmr: "L3 icache miss", DLmr: "L3 dcache read miss", DLmw: "L3 dcache write miss",
  Bc: "branches", Bcm: "misprediction", Bi: "indirect branches", Bim: "indirect misprediction",
  Ge: "bus events", sysCount: "syscalls", sysTime: "syscall time", sysCpuTime: "syscall cpu time",
  AcCost1: "L1 access cost", SpLoss1: "L1 spatial loss", AcCost2: "L3 access cost", SpLoss2: "L3 spatial loss",
  ILdmr: "L3 insn write-back", DLdmr: "L3 read write-back", DLdmw: "L3 write write-back",
  D1m: "L1 cache", DLm: "L3 cache", L1m: "L1 cache, all", LLm: "L3 cache, all",
  Bm: "misprediction, all", CEst: "cycle estimate",
};
const evLabel = e => EVENT_SHORT[e.key] ? EVENT_SHORT[e.key] + " / " + e.key : e.key;
const evLong = e => EVENT_SHORT[e.key] || e.long || e.key;
const evSel = document.getElementById("event");
let evMaxLen = 0;
for (const e of EVS) {
  const o = document.createElement("option");
  o.value = e.key;
  o.textContent = e.key + (e.long ? " \\u2014 " + e.long : "");
  evMaxLen = Math.max(evMaxLen, o.textContent.length);
  evSel.appendChild(o);
}
evSel.value = ev.key;

evSel.style.width = (evMaxLen + 4) + "ch";
let TOTAL = 1, MAXP = 1, MAXPX = {};
const val = v => ev.get(v);

function recomputeScale() {
  TOTAL = ev.get(D.meta.totals) || 1;
  let m = 0;
  for (const f of Object.values(files)) for (const rec of Object.values(f.lines)) { const s = val(rec[0]); if (s > m) m = s; }
  MAXP = Math.max(100 * m / TOTAL, 0.0001);
  MAXPX = {};
  for (const x of EXTRA) {
    let mx = 0;
    for (const f of Object.values(files)) for (const rec of Object.values(f.lines)) { const s = x.get(rec[0]); if (s > mx) mx = s; }
    MAXPX[x.key] = { total: x.get(D.meta.totals) || 1, maxP: Math.max(100 * mx / (x.get(D.meta.totals) || 1), 0.0001) };
  }
}

const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const pct = v => 100 * v / TOTAL;
const fmtP = p => p >= 9.95 ? p.toFixed(1) + "%" : p >= 0.01 ? p.toFixed(2) + "%" : p > 0 ? "<0.01%" : "";
const fmtPct = v => fmtP(pct(v));
const fmtN = v => v.toLocaleString("en-US");

function fmtH(v) {
  let unit = "";
  for (const u of ["K", "M", "G", "T"]) { if (v < 999.5) break; v /= 1000; unit = u; }
  return (unit && v < 9.95 ? v.toFixed(1) : v.toFixed(0)) + unit;
}
const num = v => ({ text: fmtH(v), title: fmtN(v) });
const PMIN = 0.001;
function heatP(p, maxP) {
  if (p <= 0) return 0;
  if (scale === "linear") return Math.min(1, p / maxP);
  if (p < PMIN) return 0;
  return Math.min(1, Math.log10(p / PMIN) / Math.log10(Math.max(maxP, PMIN * 10) / PMIN));
}
function heatT(cost, maxP) { return heatP(pct(cost), maxP); }

const RGB = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
const STOPS = D.theme.heat.map(RGB), BG = RGB(D.theme.bg);
function heatStyle(t, aMin, aMax) {
  if (t <= 0) return "";
  const x = t * (STOPS.length - 1), i = Math.min(Math.floor(x), STOPS.length - 2), f = x - i, a = aMin + (aMax - aMin) * t;
  const m = [0, 1, 2].map(k => Math.round(BG[k] + (STOPS[i][k] + (STOPS[i + 1][k] - STOPS[i][k]) * f - BG[k]) * a));
  const lum = (0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]) / 255;
  return `background:rgb(${m.join(",")});color:${lum > 0.5 ? D.theme.fgDark : D.theme.fgLight}`;
}
const heatBg = t => heatStyle(t, 0.18, 0.92);
const heatBgSoft = t => heatStyle(t, 0.12, 0.55);

const fnCalls = fns.map(f => f.callers.reduce((a, c) => a + c[4], 0));
const CALLS_TOTAL = fnCalls.reduce((a, b) => a + b, 0) || 1;
const CALLS_MAXP = Math.max(100 * fnCalls.reduce((a, b) => Math.max(a, b), 0) / CALLS_TOTAL, 0.0001);
const numCalls = n => n ? { text: fmtH(n), title: fmtN(n) + " calls", style: heatBg(heatP(100 * n / CALLS_TOTAL, CALLS_MAXP)) } : "";

const enc = v => encodeURIComponent(v).replace(/%2F/g, "/");
function hashOf(s) {
  const parts = [];
  if (s.fn) parts.push("fn=" + enc(s.fn));
  else if (s.file) { parts.push("f=" + enc(s.file)); if (s.line) parts.push("l=" + s.line); }
  if (EVS.length > 1) parts.push("e=" + enc(s.ev || ev.key));
  return parts.length ? "#" + parts.join("&") : "";
}
const hashFor = (path, line) => hashOf({ file: path, line: line });
const hashForFn = name => hashOf({ fn: name });
function fnName(i) { return (i != null && fns[i]) ? fns[i].name : "?"; }

function link(path, line, text) { return files[path] && line ? `<a href="${hashFor(path, line)}">${esc(text)}</a>` : esc(text); }

const fnLinkable = fi => fi != null && fns[fi] && fns[fi].line && files[fns[fi].file];
function linkFn(fi, text) { return fnLinkable(fi) ? `<a href="${hashForFn(fns[fi].name)}">${esc(text)}</a>` : esc(text); }
const SYMBOL_CHARS = 20;
const SRC_COLS = 80;
const HOT_CHIPS = 10;

const PAD = 3;

function colWidths(cols, rc) {
  return cols.map((col, i) => {
    let n = col.label.length;
    if (col.width != null) n = Math.max(n, col.width);
    else if (!col.grow) {
      for (const r of rc) if (r[i]) n = Math.max(n, (r[i].text || "").length);
      if (col.clip != null) n = Math.max(col.label.length, Math.min(n, col.clip));
    }
    return n + PAD;
  });
}
function table(key, cols, rows, opts) {
  opts = opts || {};
  const cell = c => (c && typeof c === "object") ? c : { text: c == null ? "" : String(c) };
  const rc = rows.map(r => r.map(cell));
  const widths = colWidths(cols, rc);
  const tcls = ["cols", opts.fill ? "fill" : "", opts.cls || ""].filter(Boolean).join(" ");
  let h = opts.bare ? "" : `<div class="tbl">`;
  h += `<div class="tbl-cols"><table class="${tcls}" data-key="${esc(key)}"${opts.fill ? ` data-fill="${opts.fill}"` : ""}><colgroup>`;
  cols.forEach((c, i) => {
    const ccls = [i % 2 ? "alt" : "", c.grow ? "grow" : ""].filter(Boolean).join(" ");
    h += `<col${ccls ? ` class="${ccls}"` : ""} style="width:${widths[i]}ch">`;
  });
  h += `</colgroup><thead><tr>`;
  for (const c of cols) h += `<th${c.num ? ' class="n"' : ""}${c.title ? ` title="${esc(c.title)}"` : ""}>${esc(c.label)}</th>`;
  h += `</tr></thead><tbody>`;
  rc.forEach((r, ri) => {
    const href = opts.rowHref && opts.rowHref[ri];
    h += href ? `<tr class="rowlink" data-href="${esc(href)}">` : opts.rowAttrs ? `<tr ${opts.rowAttrs[ri]}>` : "<tr>";
    r.forEach((c, i) => {
      const col = cols[i] || {};
      const cls = [col.num ? "n" : "", col.cls || "", c.cls || ""].filter(Boolean).join(" ");
      const text = c.text || "", title = c.title || ((text.length + PAD > widths[i]) ? text : "");
      h += `<td${cls ? ` class="${cls}"` : ""}${c.style ? ` style="${c.style}"` : ""}${title ? ` title="${esc(title)}"` : ""}>${c.html != null ? c.html : esc(text)}</td>`;
    });
    h += "</tr>";
  });
  h += `</tbody></table></div>`;
  return opts.bare ? h : h + `</div>`;
}

function tableText(cols, rows) {
  const cell = c => (c && typeof c === "object") ? c : { text: c == null ? "" : String(c) };
  const rc = rows.map(r => r.map(cell));
  const widths = cols.map((col, i) => {
    let n = col.label.length;
    for (const r of rc) if (r[i]) n = Math.max(n, (r[i].text || "").length);
    return n;
  });
  const pad = (s, w, num) => num ? s.padStart(w) : s.padEnd(w);
  const line = cells => "| " + cells.map((s, i) => pad(s, widths[i], cols[i].num)).join(" | ") + " |";
  const out = [line(cols.map(c => c.label))];
  out.push("| " + cols.map((c, i) => (c.num ? "-".repeat(widths[i] - 1) + ":" : "-".repeat(widths[i]))).join(" | ") + " |");
  for (const r of rc) out.push(line(cols.map((c, i) => (r[i] && r[i].text) || "")));
  return out.join("\\n");
}
const evCol = (e, extra) => Object.assign({ label: e.key, title: e.long, num: true }, extra || {});
const extraCols = () => EXTRA.map(x => evCol(x, {
  label: evLabel(x),
  title: x.long + " (share of that event's total)", cls: "x",
}));
function extraCells(vec) {
  return EXTRA.map(x => {
    const s = x.get(vec), m = MAXPX[x.key], p = 100 * s / m.total, t = heatP(p, m.maxP);
    return { text: s ? fmtP(p) : "", style: heatBg(t), cls: t > 0.45 ? "hot" : "", title: x.key + ": " + fmtN(s) };
  });
}

let TREE = null;
function buildTree() {
  const root = { name: "", path: "", dirs: new Map(), files: [], self: 0 };
  function insert(path, self, cold) {
    const parts = path.split("/");
    let node = root;
    for (let i = 0; i < parts.length - 1; i++) {
      const seg = parts[i];
      if (!node.dirs.has(seg)) node.dirs.set(seg, { name: seg, path: node.path ? node.path + "/" + seg : seg, dirs: new Map(), files: [], self: 0 });
      node = node.dirs.get(seg);
    }
    node.files.push({ name: parts[parts.length - 1], path, self, cold, zero: self === 0 });
  }
  for (const p of Object.keys(files)) insert(p, val(files[p].self), false);
  for (const p of D.cold) insert(p, 0, true);
  (function sum(n) { let s = 0; for (const d of n.dirs.values()) s += sum(d); for (const f of n.files) s += f.self; n.self = s; return s; })(root);
  return root;
}
const openDirs = new Set(), coldOpen = new Set();
function cmp(a, b) { return sortMode === "heat" ? (b.self - a.self) || a.name.localeCompare(b.name) : a.name.localeCompare(b.name); }
function matches(path) { return !query || path.toLowerCase().includes(query); }
function subtreeMatches(n) {
  if (!query) return true;
  for (const f of n.files) if (matches(f.path)) return true;
  for (const d of n.dirs.values()) if (subtreeMatches(d)) return true;
  return false;
}
const MAXPDIR = 100;
function renderTree() {
  const out = [];
  function rec(n, depth) {
    const dirs = [...n.dirs.values()].filter(subtreeMatches).sort(cmp);
    for (const d of dirs) {
      const open = query ? true : openDirs.has(d.path), hs = heatBgSoft(heatT(d.self, MAXPDIR));
      out.push(`<div class="node dir${hs ? " heat" : ""}" data-dir="${esc(d.path)}" style="padding-left:${6 + depth * 14}px;${hs}"><span class="caret">${open ? "\\u25BC" : "\\u25B6"}</span><span class="name" title="${esc(d.path)}">${esc(d.name)}/</span><span class="pct">${fmtPct(d.self)}</span></div>`);
      out.push(`<div class="kids${open ? " open" : ""}">`);
      rec(d, depth + 1);
      out.push(`</div>`);
    }
    const fl = n.files.filter(f => matches(f.path)).sort(cmp);
    const fileRow = f => {
      const sel = f.path === curFile ? " sel" : "", hs = f.cold ? "" : heatBgSoft(heatT(f.self, MAXPDIR));
      out.push(`<div class="node file${f.cold ? " cold" : ""}${hs ? " heat" : ""}${sel}" data-file="${esc(f.path)}" style="padding-left:${6 + depth * 14}px;${hs}"><span class="caret">\\u25B6</span><span class="name" title="${esc(f.path)}${f.cold ? " (no samples; source not embedded)" : ""}">${esc(f.name)}</span><span class="pct">${fmtPct(f.self)}</span></div>`);
    };
    const zero = fl.filter(f => f.zero);
    for (const f of fl) if (!f.zero) fileRow(f);
    if (zero.length) {
      const show = query ? true : coldOpen.has(n.path);
      out.push(`<div class="node more" data-more="${esc(n.path)}" style="padding-left:${6 + depth * 14}px"><span class="caret">${show ? "\\u25BC" : "\\u25B6"}</span><span class="name">${zero.length} file${zero.length > 1 ? "s" : ""} without ${esc(evLabel(ev))}</span><span class="pct"></span></div>`);
      if (show) for (const f of zero) fileRow(f);
    }
  }
  rec(TREE, 0);
  treeEl.innerHTML = out.join("");
}
treeEl.addEventListener("click", ev2 => {
  const n = ev2.target.closest(".node");
  if (!n) return;
  if (n.dataset.dir != null) {
    const p = n.dataset.dir;
    if (openDirs.has(p)) openDirs.delete(p); else openDirs.add(p);
    renderTree();
  } else if (n.dataset.more != null) {
    const p = n.dataset.more;
    if (coldOpen.has(p)) coldOpen.delete(p); else coldOpen.add(p);
    renderTree();
  } else if (n.dataset.file != null) {
    if (n.classList.contains("cold")) return;
    location.hash = hashFor(n.dataset.file);
  }
});
function revealInTree(path) {
  const parts = path.split("/");
  let acc = "";
  for (let i = 0; i < parts.length - 1; i++) { acc = acc ? acc + "/" + parts[i] : parts[i]; openDirs.add(acc); }
}

const entryIdx = {};
fns.forEach((f, i) => { if (f.line) { (entryIdx[f.file] = entryIdx[f.file] || {})[f.line] = i; } });

function topLines(n) {
  const all = [];
  for (const [d, e] of Object.entries(files)) for (const [ln, rec] of Object.entries(e.lines)) { const s = val(rec[0]); if (s > 0) all.push([d, +ln, s, e.lfn[ln]]); }
  all.sort((a, b) => b[2] - a[2]);
  return all.slice(0, n).map(t => {
    const e = files[t[0]];
    let snip = "";
    if (e.src != null) { const srcl = e.src.split("\\n"); if (t[1] >= 1 && t[1] <= srcl.length) snip = srcl[t[1] - 1].trim().slice(0, 110); }
    return [t[0], t[1], t[2], t[3], snip];
  });
}
const SELF = { label: "self", title: "share of the total spent on this line/function itself, not in what it calls", num: true };
function renderHome() {
  curFile = null;
  let h = `<div class="home">`;
  const lineRows = topLines(60);
  h += `<h2>Hottest lines by ${esc(evLabel(ev))}</h2>` + table("heat.home.lines",
    [{ label: "#", title: "rank", num: true }, SELF,
     { label: "function", title: `the function the line belongs to (first ${SYMBOL_CHARS} characters; drag the bar for more)`, width: SYMBOL_CHARS },
     { label: "defined at", title: "file:line; opens the listing there", clip: 28 },
     { label: "source", title: "the source line, trimmed; drag the bar for more", clip: 36 },
     evCol(ev), ...extraCols()],
    lineRows.map((t, i) => {
      const [path, ln, cost, fnidx, snip] = t, rec = files[path].lines[ln];
      return [String(i + 1),
              { text: fmtPct(cost), style: heatBg(heatT(cost, MAXP)) },
              { text: fnName(fnidx), title: fnName(fnidx) },
              { text: path + ":" + ln, html: link(path, ln, path + ":" + ln) },
              snip, num(cost), ...extraCells(rec[0])];
    }), { rowHref: lineRows.map(t => hashFor(t[0], t[1])) });
  const topF = fns.map((f, i) => [i, val(f.self)]).filter(t => t[1] > 0).sort((a, b) => b[1] - a[1]).slice(0, 60);
  h += `<h2>Hottest functions by self ${esc(evLabel(ev))}</h2>` + table("heat.home.functions",
    [{ label: "#", title: "rank", num: true }, SELF,
     { label: "function", title: `first ${SYMBOL_CHARS} characters; drag the bar for more`, width: SYMBOL_CHARS },
     { label: "defined at", title: "file:line of the function's first executed line", clip: 48 },
     { label: "calls", title: "times the function was entered", num: true },
     { label: "incl", title: "total: self plus everything it calls", num: true }, ...extraCols()],
    topF.map(([fi, s], i) => {
      const f = fns[fi], loc = f.line ? f.file + ":" + f.line : f.file;
      return [String(i + 1),
              { text: fmtPct(s), style: heatBg(heatT(s, MAXP)) },
              { text: f.name, title: f.name },
              { text: loc, html: linkFn(fi, loc) },
              numCalls(fnCalls[fi]), fmtPct(s + val(f.calls)), ...extraCells(f.self)];
    }), { rowHref: topF.map(([fi]) => fnLinkable(fi) ? hashForFn(fns[fi].name) : "") });
  h += `</div>`;
  mainEl.innerHTML = h;
  mainEl.scrollTop = 0;
  renderTree();
  Theme.init(mainEl);
  minimapClear();
}

function renderFile(path, line) {
  const f = files[path];
  if (!f) { renderHome(); return; }
  const first = curFile !== path, keepTop = first ? -1 : mainEl.scrollTop;
  curFile = path;
  revealInTree(path);
  const lines = f.lines;
  let fmax = 0;
  for (const rec of Object.values(lines)) { const s = val(rec[0]); if (s > fmax) fmax = s; }
  const maxP = scale === "file" ? Math.max(pct(fmax), 0.0001) : MAXP;
  let h = `<div class="srcwrap"><div class="fhead band"><span class="path">${esc(path)}</span>`;
  h += `<span class="stat" title="${fmtN(val(f.self))}">self <b>${fmtPct(val(f.self)) || "0%"}</b> (${fmtH(val(f.self))} ${esc(evLabel(ev))})</span>`;
  for (const x of EXTRA) { const s = x.get(f.self); if (s) h += `<span class="stat" title="${esc(x.long)}: ${fmtN(s)}">${esc(evLabel(x))} <b>${fmtP(100 * s / MAXPX[x.key].total)}</b> (${fmtH(s)})</span>`; }
  if (f.group === "external") h += `<span class="stat">not in this repo (${esc(f.raw)})</span>`;
  h += `</div>`;
  if (f.src == null) {
    h += `<div class="nosrc">Source not available.</div></div>`;
    mainEl.innerHTML = h;
    renderTree();
    Theme.init(mainEl);
    minimapClear();
    return;
  }

  const hot = Object.keys(lines).map(k => [+k, val(lines[k][0])])
    .filter(t => t[1] > 0).sort((a, b) => b[1] - a[1]);
  const chips = hot.filter(t => pct(t[1]) >= 0.01).slice(0, HOT_CHIPS);
  if (chips.length) {
    h += `<div class="chips"><span class="lbl">hottest lines</span>`;
    for (const [ln, cost] of chips) h += `<span class="chip" data-goto="${ln}" style="${heatBg(heatT(cost, maxP))}">${ln} \\u00b7 ${fmtPct(cost)}</span>`;
    h += `</div>`;
  }

  const rows = [], attrs = [];
  const emitRow = (ln, text) => {
    const rec = lines[ln];
    const self = rec ? val(rec[0]) : 0, calls = rec ? val(rec[1]) : 0;
    const t = heatT(self, maxP), hs = heatBg(t);
    const fnidx = f.lfn[ln];
    const title = rec ? `${fmtN(self)} ${ev.key} self, ${fmtN(calls)} in calls${rec[2] ? " over " + fmtH(rec[2]) + " calls" : ""}${fnidx != null ? " \\u2014 in " + fnName(fnidx) : ""}` : "";
    const cls = [rec ? "clickable" : "", f.callees[ln] ? "hasc" : ""].filter(Boolean).join(" ");
    attrs.push(`id="L${ln}"${cls ? ` class="${cls}"` : ""} data-ln="${ln}"${title ? ` title="${esc(title)}"` : ""}`);
    rows.push([{ text: self ? fmtPct(self) : "", style: hs, cls: t > 0.45 ? "hot" : "" },
               { text: String(ln), style: hs },
               { text, style: hs },
               { text: calls ? fmtPct(calls) : "", style: heatBg(heatT(calls, maxP)) },
               ...(rec ? extraCells(rec[0]) : EXTRA.map(() => ""))]);
  };
  const srcl = f.src.split("\\n");
  if (srcl.length && srcl[srcl.length - 1] === "") srcl.pop();
  let nlines = srcl.length;
  for (let i = 0; i < srcl.length; i++) emitRow(i + 1, srcl[i]);
  for (const k of Object.keys(lines)) if (+k > srcl.length) { nlines = Math.max(nlines, +k); emitRow(+k, "(line beyond end of file: source changed since the profile was taken)"); }

  const cols = [evCol(ev, { title: ev.long + ", share of total, spent on the line itself", cls: "self" }),
                { label: "line", num: true, width: String(nlines).length + 2, cls: "ln" },
                { label: "source", width: SRC_COLS, grow: true, cls: "code" },
                { label: "calls", title: "total cost of the calls made from the line, share of total", num: true, cls: "incl" },
                ...extraCols()];
  h += table("heat.src", cols, rows, { rowAttrs: attrs, fill: 1, cls: "src", bare: true });
  h += `<div class="srctail"></div></div>`;
  mainEl.innerHTML = h;
  renderTree();

  minimapBuild();
  Theme.init(mainEl);
  srctailFit();
  if (!first) mainEl.scrollTop = keepTop;
  else if (!line) {
    const hottest = hot.length ? hot[0][0] : 0;
    const el = hottest ? document.getElementById("L" + hottest) : null;
    if (el) centerRow(el); else mainEl.scrollTop = 0;
  }
  minimapSync();
}

function rowOnScreen(el) {
  const r = el.getBoundingClientRect(), m = mainEl.getBoundingClientRect();
  return r.top >= m.top + coverH(el.closest("table")) && r.bottom <= m.top + mainEl.clientHeight;
}

function coverH(table) {
  let h = table.tHead.rows[0].cells[0].getBoundingClientRect().height;
  for (const b of mainEl.querySelectorAll(".band")) h += b.getBoundingClientRect().height;
  return h;
}

function centerRow(el) {
  const cover = coverH(el.closest("table"));
  const r = el.getBoundingClientRect(), m = mainEl.getBoundingClientRect();
  mainEl.scrollTop += r.top - m.top - cover - (mainEl.clientHeight - cover - r.height) / 2;
}

function srctailFit() {
  const tail = mainEl.querySelector(".srctail"), table = mainEl.querySelector("table.src");
  if (!tail || !table) return;
  const rows = table.tBodies[0].rows, last = rows[rows.length - 1];
  if (!last) return;
  const cover = coverH(table), rowH = last.getBoundingClientRect().height;
  tail.style.height = Math.max(0, (mainEl.clientHeight - cover - rowH) / 2) + "px";
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
  const table = mainEl.querySelector("table.src"), tbody = table && table.tBodies[0];
  if (!tbody || tbody.rows.length < MM_MIN_LINES) { minimapClear(); return; }

  const probeCell = tbody.rows[0].querySelector("td.code");
  if (!probeCell) { minimapClear(); return; }
  const span = document.createElement("span");
  span.textContent = "0123456789";
  span.style.cssText = "position:absolute;visibility:hidden;white-space:pre;font:inherit";
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
    const tr = document.createElement("tr");
    tr.className = row.className;
    tr.appendChild(code.cloneNode(true));
    body.appendChild(tr);
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
  const main = mainEl.getBoundingClientRect(), body = tbody.getBoundingClientRect();
  const detailEl = tbody.querySelector("tr.detail"), detail = detailEl && detailEl.getBoundingClientRect();
  const rows = body.height - (detail ? detail.height : 0);
  const above = y => {
    let px = y - body.top;
    if (detail) px -= Math.max(0, Math.min(y, detail.bottom) - detail.top);
    return Math.max(0, Math.min(rows, px));
  };
  return { rows, above, cover: coverH(table), body, detail, top: main.top, bottom: main.top + mainEl.clientHeight,
           head: table.tHead.rows[0].cells[0].getBoundingClientRect().bottom };
}
function minimapSync() {
  if (minimapEl.classList.contains("empty")) return;
  const g = mmGeom(), scaledH = mmCloneH * mmScale;
  const r0 = g.above(g.head), r1 = g.above(g.bottom);
  const h = Math.max(8, scaledH * (r1 - r0) / g.rows);
  mmViewport.style.top = Math.max(0, Math.min(scaledH - h, scaledH * r0 / g.rows)) + "px";
  mmViewport.style.height = h + "px";
}

function mmScrollTo(r0) {
  const g = mmGeom();
  r0 = Math.max(0, Math.min(g.rows, r0));
  let y = g.body.top - g.top + mainEl.scrollTop + r0 - g.cover;
  if (g.detail && g.detail.top - g.body.top < r0) y += g.detail.height;
  mainEl.scrollTop = Math.max(0, Math.min(mainEl.scrollHeight - mainEl.clientHeight, y));
}
mainEl.addEventListener("scroll", minimapSync);
minimapEl.addEventListener("click", e => {
  if (e.target.closest("#mmViewport")) return;
  const g = mmGeom(), scaledH = mmCloneH * mmScale;
  const r = (e.clientY - minimapEl.getBoundingClientRect().top) / scaledH * g.rows;
  mmScrollTo(r - (mainEl.clientHeight - g.cover) / 2);
});
mmViewport.addEventListener("pointerdown", e => {
  const y0 = e.clientY, top0 = mmViewport.offsetTop, scaledH = mmCloneH * mmScale;
  mmViewport.classList.add("drag");
  if (mmViewport.setPointerCapture) mmViewport.setPointerCapture(e.pointerId);
  const move = ev => mmScrollTo((top0 + ev.clientY - y0) / scaledH * mmGeom().rows);
  const up = () => {
    mmViewport.classList.remove("drag");
    for (const [t, f] of [["pointermove", move], ["pointerup", up], ["pointercancel", up]]) mmViewport.removeEventListener(t, f);
  };
  for (const [t, f] of [["pointermove", move], ["pointerup", up], ["pointercancel", up]]) mmViewport.addEventListener(t, f);
  e.preventDefault();
  e.stopPropagation();
});

function detailLine() {
  const d = mainEl.querySelector("tr.detail");
  return d ? +d.previousElementSibling.dataset.ln : 0;
}

function detailSet(line) {
  if (line === detailLine()) return;
  for (const e of mainEl.querySelectorAll("tr.detail")) e.remove();
  const row = line ? document.getElementById("L" + line) : null;
  if (row) {
    detailOpen(curFile, line, row);
    if (!rowOnScreen(row)) centerRow(row);
  }
  minimapSync();
}
function detailOpen(path, ln, row) {
  const f = files[path];
  const callees = (f.callees[ln] || []).slice().sort((a, b) => val(b[3]) - val(a[3]));
  const fi = (entryIdx[path] || {})[ln];
  const fnidx = f.lfn[ln];
  const rec = f.lines[ln] || [[], [], 0];
  const fnCol = label => ({ label, title: `first ${SYMBOL_CHARS} characters; drag the bar for more`, width: SYMBOL_CHARS });
  const locCol = { label: "defined at", title: "file:line of the function's first executed line", clip: 48 };
  const callsClause = val(rec[1]) ? `, calls ${fmtH(val(rec[1]))} (${fmtPct(val(rec[1]))}) over ${fmtH(rec[2])} calls` : "";
  const extraStats = xs => xs.map(x => { const s = x.get(rec[0]); return s ? `, ${evLabel(x)} ${fmtP(100 * s / MAXPX[x.key].total)} (${fmtH(s)})` : ""; }).join("");

  const headLine = (fi != null)
    ? `${path}:${ln} self ${fmtPct(val(rec[0])) || "0%"} by ${evLong(ev)}, ${fmtH(val(rec[0]))} ${ev.key}.${callsClause}${extraStats(EXTRA)}`
    : `${path}:${ln}${fnidx != null ? " in " + fnName(fnidx) : ""}: line self ${fmtPct(val(rec[0])) || "0%"} ${evLong(ev)}, ${fmtH(val(rec[0]))} ${ev.key}${callsClause}${extraStats(EXTRA)}`;
  let h = `<div class="dbox">`;
  h += `<a href="#" class="dclose" title="close">[X]</a>`;
  h += (fi != null)
    ? `<div>${esc(path)}:${ln} self ${fmtPct(val(rec[0])) || "0%"} by ${esc(evLong(ev))}, ${fmtH(val(rec[0]))} ${esc(ev.key)}.${esc(callsClause)}${esc(extraStats(EXTRA))}</div>`
    : `<div>${esc(path)}:${ln}${fnidx != null ? " in <b>" + esc(fnName(fnidx)) + "</b>" : ""}: line self ${fmtPct(val(rec[0])) || "0%"} ${esc(evLong(ev))}, ${fmtH(val(rec[0]))} ${esc(ev.key)}${esc(callsClause)}${esc(extraStats(EXTRA))}</div>`;
  const textParts = [headLine];
  if (callees.length) {
    const cols = [{ label: "% of total", num: true }, evCol(ev), { label: "call count", num: true }, fnCol("callee"), locCol];
    const rows = callees.map(([ci, cf, cl, vec, count]) => {
      const loc = cl ? cf + ":" + cl : cf;
      return [fmtPct(val(vec)), num(val(vec)), numCalls(count), { text: fnName(ci), title: fnName(ci) }, { text: loc, html: linkFn(ci, loc) }];
    });
    const heading = `calls from this line (total ${evLabel(ev)})`;
    h += `<h4>${esc(heading)}</h4>` + table("heat.detail.callees", cols, rows);
    textParts.push(heading + "\\n" + tableText(cols, rows));
  }
  if (fi != null) {
    const fn = fns[fi];
    const callers = fn.callers.slice().sort((a, b) => b[4] - a[4]);
    const heading = `${fn.name} by call count: self ${fmtPct(val(fn.self)) || "0%"}, total ${fmtPct(val(fn.self) + val(fn.calls)) || "0%"}.`;
    h += `<h4>${esc(fn.name)} by call count: self ${fmtPct(val(fn.self)) || "0%"}, total ${fmtPct(val(fn.self) + val(fn.calls)) || "0%"}.</h4>`;
    if (callers.length) {
      const cols = [{ label: "call count", num: true }, { label: "% of total", num: true }, evCol(ev), fnCol("caller"), { label: "called at", title: "file:line of the call", clip: 48 }];
      const rows = callers.map(([ci, cf, cl, vec, count]) => {
        const loc = cl ? cf + ":" + cl : cf;
        return [numCalls(count), fmtPct(val(vec)), num(val(vec)), { text: fnName(ci), title: fnName(ci) }, { text: loc, html: link(cf, cl, loc) }];
      });
      h += table("heat.detail.callers", cols, rows);
      textParts.push(heading + "\\n" + tableText(cols, rows));
    } else {
      h += `<div class="dim">(no recorded caller \\u2014 a root or a resolver stub)</div>`;
      textParts.push(heading + "\\n(no recorded caller \\u2014 a root or a resolver stub)");
    }
  }
  h += `<div class="dactions"><a href="#" class="dcopy">copy</a> <a href="#" class="dclose2">close</a></div>`;
  h += `</div>`;
  const tr = document.createElement("tr");
  tr.className = "detail";
  tr.innerHTML = `<td colspan="${row.cells.length}">${h}</td>`;
  tr._copyText = textParts.join("\\n\\n");
  row.after(tr);
  Theme.init(tr);
}

mainEl.addEventListener("click", ev2 => {
  const chip = ev2.target.closest(".chip");
  if (chip) { location.hash = hashFor(curFile, +chip.dataset.goto); return; }
  const copy = ev2.target.closest(".dcopy");
  if (copy) {
    ev2.preventDefault();
    navigator.clipboard.writeText(copy.closest("tr.detail")._copyText);
    return;
  }
  const close = ev2.target.closest(".dclose, .dclose2");
  if (close) { ev2.preventDefault(); location.hash = hashFor(curFile); return; }
  if (ev2.target.closest("a")) return;
  const linkRow = ev2.target.closest("tr.rowlink");
  if (linkRow) { location.hash = linkRow.dataset.href; return; }
  const row = ev2.target.closest("tr.clickable");
  if (row && curFile) { const ln = +row.dataset.ln; location.hash = ln === detailLine() ? hashFor(curFile) : hashFor(curFile, ln); }
});

let st = { file: null, line: 0, fn: null };
let shown = "";
function stateOf(hash) {
  const s = { file: null, line: 0, fn: null, ev: null };
  for (const part of (hash || "").replace(/^#/, "").split("&")) {
    const i = part.indexOf("=");
    if (i < 0) continue;
    let v;
    try { v = decodeURIComponent(part.slice(i + 1)); } catch (e) { continue; }
    const k = part.slice(0, i);
    if (k === "f") s.file = v; else if (k === "l") s.line = +v || 0; else if (k === "fn") s.fn = v; else if (k === "e") s.ev = v;
  }
  return s;
}
function applyEvent(key) {
  ev = evByKey(key) || EVS[0];
  evSel.value = ev.key;
  recomputeScale();
  TREE = buildTree();
  for (const d of TREE.dirs.values()) if (d.self / TOTAL > 0.05) openDirs.add(d.path);
}
function syncHash() {
  const hash = hashOf(st);
  if (hash !== location.hash) history.replaceState(null, "", hash || "#");
  if (window.parent !== window) window.parent.postMessage({ theme: "hash", hash: hash }, "*");
}
function route() {
  const s = stateOf(location.hash);
  const e = evByKey(s.ev) || evByKey(D.meta.defaultEvent) || EVS[0];
  if (e.key !== ev.key) applyEvent(e.key);
  let file = s.file, line = s.line, fn = s.fn;
  if (fn) {
    const f = fns.find(x => x.name === fn);
    if (f && f.line && files[f.file]) { file = f.file; line = f.line; }
    else { fn = null; file = null; line = 0; }
  }
  if (file && !files[file]) { file = null; line = 0; }

  const key = (file ? "file\\n" + file : "home") + "\\n" + ev.key + "\\n" + scale;
  if (key !== shown) { shown = key; if (file) renderFile(file, line); else renderHome(); }
  if (file) {
    if (line && !document.getElementById("L" + line)) line = 0;
    detailSet(line);
  }
  st = { file: file, line: line, fn: fn };
  syncHash();
}
window.addEventListener("hashchange", route);
window.addEventListener("message", e => {
  if (e.data === "theme:reset-cols") Theme.resetCols(mainEl);
});

let mmResizeTimer = null;
window.addEventListener("resize", () => {
  clearTimeout(mmResizeTimer);
  mmResizeTimer = setTimeout(() => { srctailFit(); minimapLayout(); }, 120);
});
evSel.addEventListener("change", e => { location.hash = hashOf(Object.assign({}, st, { ev: e.target.value })); });
document.getElementById("scale").addEventListener("change", e => { scale = e.target.value; store.set("heat.scale", scale); shown = ""; route(); });
document.getElementById("sort").addEventListener("change", e => { sortMode = e.target.value; store.set("heat.sort", sortMode); renderTree(); });
document.getElementById("q").addEventListener("input", e => { query = e.target.value.trim().toLowerCase(); renderTree(); });
applyEvent(ev.key);
route();
})();
</script>
"""


def heatmap_render(model: HeatModel, title: str) -> str:
    data = json.dumps(model, separators=(",", ":"), ensure_ascii=False)
    data = data.replace("</", "<\\/")
    body = BODY.replace("__THEME_JS__", theme.theme_js()).replace("__DATA__", data)
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{theme.html_esc(title)}</title>\n<style>\n{theme.theme_css()}{CSS}</style>\n</head>\n<body>\n"
            + body + "</body>\n</html>\n")


def heatmap_main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("callgrind_file", nargs="+", help="callgrind output file(s); several are merged into one profile")
    ap.add_argument("-o", "--output", required=True, help="output .html path (directories are created)")
    ap.add_argument("--event", default="CEst", help="event selected when the page opens (default: CEst, KCachegrind's cycle estimate)")
    ap.add_argument("--repo-root", default=".", help="repository root the profile's paths are relative to")
    ap.add_argument("--tree", nargs="*", default=["lib", "include", "src", "tests/perf"],
                    help="directories whose tracked .c/.h files are listed in the tree even without samples")
    ap.add_argument("--all-sources", action="store_true",
                    help="embed the source of every tracked file in --tree, not just files with samples")
    ap.add_argument("--title", default=None)
    ns = ap.parse_args()
    args = HeatArgs(callgrind_file=ns.callgrind_file, output=ns.output, event=ns.event, repo_root=ns.repo_root,
                    tree=ns.tree, all_sources=ns.all_sources, title=ns.title)

    prof = cg.profile_load(args.callgrind_file)
    if not prof.events:
        sys.exit("error: no 'events:' line -- not a callgrind file?")
    src_name = os.path.basename(args.callgrind_file[0])
    if len(args.callgrind_file) > 1:
        src_name += f" + {len(args.callgrind_file) - 1} more"
    title = args.title if args.title is not None else f"heat map: {prof.cmd or src_name}"

    check = cg.profile_self_check(prof)
    print(f"events: {' '.join(prof.events)}", file=sys.stderr)
    print(f"callgrind summary ({prof.events[0]}): {check.total:,}", file=sys.stderr)
    print(f"sum of self-cost lines:          {check.self_sum:,}", file=sys.stderr)
    print(f"ratio (must be 1.0000):          {check.ratio:.4f}", file=sys.stderr)
    if check.total and abs(check.ratio - 1.0) > 1e-6:
        print("error: per-line self cost does not add up to callgrind's summary; refusing to write", file=sys.stderr)
        sys.exit(2)

    model = model_build(prof, args)
    html = heatmap_render(model, title)
    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    nsrc = sum(1 for e in model["files"].values() if e["src"] is not None)
    print(f"files with samples: {len(model['files'])} ({nsrc} with source embedded), "
          f"cold files listed: {len(model['cold'])}, functions: {len(model['functions'])}", file=sys.stderr)
    print(f"wrote {args.output} ({len(html.encode('utf-8')):,} bytes)", file=sys.stderr)


if __name__ == "__main__":
    heatmap_main()
