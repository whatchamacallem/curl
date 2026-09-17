#!/usr/bin/env python3
"""Turn a callgrind profile into a self-contained "source heatmap" web page.

Usage:
  callgrind_to_heatmap.py callgrind.out.X [callgrind.out.Y ...] \
      -o report/heat-map/index.html [--event CEst] [--repo-root .] \
      [--tree lib include src tests/perf] [--all-sources] [--title "..."]
"""
from __future__ import annotations

import argparse
import json
import os
import posixpath
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind as cg  # noqa: E402
import theme  # noqa: E402


# --------------------------------------------------------------------------
# Path handling / source loading
# --------------------------------------------------------------------------


def path_norm(path: str, repo_root: str) -> tuple[str, str | None, str]:
    """Return (display path, local path to read source from or None, group).

    group is "repo" for files inside the repository, "system" for other
    absolute paths that exist on disk, "external" for everything else.
    """
    if path == "???":
        return "(unknown)", None, "external"
    root = repo_root.rstrip("/") + "/"
    if os.path.isabs(path):
        path = posixpath.normpath(path)  # build dirs record e.g. build/lib/../../lib/x.c
    if path.startswith(root):
        rel = path[len(root):]
        return rel, os.path.join(repo_root, rel), "repo"
    if os.path.isabs(path):
        if os.path.isfile(path):
            return path.lstrip("/"), path, "system"
        return path.lstrip("/"), None, "external"
    # relative: try the repo root first
    cand = os.path.join(repo_root, path)
    if os.path.isfile(cand):
        return posixpath.normpath(path), cand, "repo"
    return posixpath.normpath(path), None, "external"


def source_read(local: str) -> str | None:
    try:
        with open(local, "rb") as f:
            data = f.read()
    except OSError:
        return None
    return data.decode("utf-8", errors="replace")


def repo_tracked_files(repo_root: str, dirs: list[str]) -> list[str]:
    if not dirs:
        return []
    try:
        out = subprocess.run(
            ["git", "-C", repo_root, "ls-files", "--", *dirs],
            check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    return [ln for ln in out.split("\n") if ln.endswith((".c", ".h"))]


# --------------------------------------------------------------------------
# Build the JSON model
# --------------------------------------------------------------------------


def vec_trim(vec: list[int]) -> list[int]:
    """Drop trailing zeros; the page pads on read. Keeps the model small."""
    n = len(vec)
    while n and vec[n - 1] == 0:
        n -= 1
    return vec[:n]


def model_build(p: cg.Profile, args: argparse.Namespace) -> dict:
    repo_root = os.path.abspath(args.repo_root)
    nev = len(p.events)

    fn_names = sorted(p.fn_home.keys())
    fn_index = {n: i for i, n in enumerate(fn_names)}

    # display path for every raw file name
    disp: dict[str, str] = {}
    local: dict[str, str | None] = {}
    group: dict[str, str] = {}
    raw_files = set(f for f, _ in p.line_self) | set(f for f, _ in p.line_calls) \
        | set(f for f, _ in p.fn_entry.values())
    for raw in raw_files:
        d, loc, g = path_norm(raw, repo_root)
        if g == "external":
            ob = os.path.basename(p.file_ob.get(raw, "")) or "(unknown object)"
            d = f"{ob}/{d}"
        disp[raw] = d
        local[raw] = loc
        group[raw] = g

    def vadd(dst: list[int], src: list[int]) -> None:
        for k, v in enumerate(src):
            dst[k] += v

    files: dict[str, dict] = {}
    for raw in raw_files:
        d = disp[raw]
        # "raw" is shown only for group == "external" (see f.raw in the JS);
        # for repo/system files it's the absolute source path and must not
        # leak into the page, so it's dropped to the (already relative) d.
        entry = files.setdefault(d, {
            "self": [0] * nev, "calls": [0] * nev, "src": None, "lines": {}, "lfn": {},
            "callees": {}, "group": group[raw], "raw": raw if group[raw] == "external" else d,
        })
        if entry["src"] is None and local[raw]:
            entry["src"] = source_read(local[raw])
    for (raw, ln), vec in p.line_self.items():
        e = files[disp[raw]]
        vadd(e["self"], vec)
        rec = e["lines"].setdefault(str(ln), [[0] * nev, [0] * nev, 0])
        vadd(rec[0], vec)
    for (raw, ln), vec in p.line_calls.items():
        e = files[disp[raw]]
        vadd(e["calls"], vec)
        rec = e["lines"].setdefault(str(ln), [[0] * nev, [0] * nev, 0])
        vadd(rec[1], vec)
        rec[2] += p.line_callcount[(raw, ln)]
    for (raw, ln), fn in p.line_fn.items():
        files[disp[raw]]["lfn"][str(ln)] = fn_index[fn]
    for (raw, ln, callee), (count, vec) in p.callees.items():
        e = files[disp[raw]]
        ef, el = p.fn_entry.get(callee, (p.fn_home.get(callee, "???"), 0))
        e["callees"].setdefault(str(ln), []).append(
            [fn_index[callee], disp.get(ef, ef), el, vec_trim(vec), count])
    for e in files.values():
        for lst in e["callees"].values():
            lst.sort(key=lambda t: -(t[3][0] if t[3] else 0))
        for rec in e["lines"].values():
            rec[0] = vec_trim(rec[0])
            rec[1] = vec_trim(rec[1])
        e["self"] = vec_trim(e["self"])
        e["calls"] = vec_trim(e["calls"])

    functions = []
    for name in fn_names:
        home = p.fn_home[name]
        ef, el = p.fn_entry.get(name, (home, 0))
        callers = sorted(
            ([fn_index[cf], disp.get(cfile, cfile), cl, vec_trim(vec), count]
             for (cf, cfile, cl), (count, vec) in p.callers[name].items()),
            key=lambda t: -(t[3][0] if t[3] else 0))
        functions.append({
            "name": name,
            "file": disp.get(ef, ef),
            "line": el,
            "self": vec_trim(p.fn_self.get(name, [])),
            "calls": vec_trim(p.fn_calls.get(name, [])),
            "callers": callers,
        })

    # cold files: tracked sources in the requested dirs with no samples
    cold: list[str] = []
    for rel in repo_tracked_files(repo_root, args.tree):
        if rel in files:
            continue
        if args.all_sources:
            src = source_read(os.path.join(repo_root, rel))
            files[rel] = {"self": [], "calls": [], "src": src, "lines": {}, "lfn": {},
                          "callees": {}, "group": "repo", "raw": rel}
        else:
            cold.append(rel)

    derived = [[name, [[c, i] for c, i in terms], long] for name, terms, long in p.derived_terms()]
    default_event = args.event if args.event in p.event_names() else (p.events[0] if p.events else "Ir")
    return {
        "meta": {
            "events": p.events,
            "eventLong": {n: p.event_long.get(n, "") for n in p.event_names()},
            "derived": derived,
            "defaultEvent": default_event,
            "totals": p.totals(),
        },
        "theme": theme.theme_runtime(),
        "files": files,
        "functions": functions,
        "cold": sorted(cold),
    }


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

CSS = """\
body { display: flex; flex-direction: column; height: 100vh; }
#hdr { gap: 4px 14px; }
#hdr label { color: var(--muted); white-space: nowrap; }
#hdr input { width: 36ch; }
#layout { display: flex; flex: 1; min-height: 0; }
#tree { width: 280px; min-width: 120px; flex: none; overflow: auto; padding: 4px 0 24px; }
#main { flex: 1; min-width: 0; overflow: auto; background: var(--bg); }
/* .srcwrap: the file view's one block child of #main -- header band, chips
   and the listing -- as wide as the widest of them (or the pane, whichever
   is more), so the sticky header band's background always reaches the far
   right edge of everything #main can scroll to sideways, instead of ending
   at the pane's width and letting rows show past it once the listing has
   been dragged wider than the pane. Nothing inside ever overflows it: the
   listing's cells clip (table.cols' own rule), so the wrapper's width is
   exactly the scrollable width. */
.srcwrap { width: max-content; min-width: 100%; }
/* only the listing box may set the wrapper's width: the header band and
   chips wrap their contents to whatever width they're given, and without
   this their *unwrapped* single-line width (all of .fhead's stats in a row)
   is what max-content would take from them, pushing the wrapper -- and a
   horizontal scrollbar -- past the pane on every file. */
.srcwrap > :not(.tbl-cols) { contain: inline-size; }
/* minimap: fixed-width band after #main, VS-Code style -- a scaled clone of
   table.src's code column only, drawn once per renderFile (minimapBuild)
   and reflowed (never re-cloned) on resize (minimapLayout). It never
   scrolls on its own and #minimap itself is never resized: a file whose
   scaled clone is shorter than the band just leaves the rest of the band
   empty. background matches #main's (var(--bg), the page background -- not
   var(--panel), which reads as a visibly different, bluer panel) since an
   unheated row's cell has no background of its own and otherwise falls
   back to whatever #minimap itself is painted, same as the real source --
   this is also why there is no border between it and #main: the two are
   meant to blend together tonally, same as VS Code's own minimap. */
#minimap { width: 110px; flex: none; overflow: hidden; position: relative;
  background: var(--bg); cursor: pointer; }
#minimap.empty { display: none; }
#mmBox { position: absolute; top: 0; left: 0; }
/* the clone is one column wide and exactly as wide as #mmBox (which
   minimapLayout sizes to the band): table-layout: fixed only takes effect
   with a non-auto table width, and without it the lone column sized itself
   to the longest line, so every row's heat background stopped there
   instead of at the band's edge. Text longer than the column overflows the
   cell and is clipped by #minimap. */
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
.chips { display: flex; gap: 4px; flex-wrap: wrap; padding: 5px 14px; background: var(--panel); }
.chips .lbl { color: var(--muted); align-self: center; margin-right: 4px; }
.chip { padding: 0 7px; background: var(--bg-alt); cursor: pointer; }
.chip:hover { outline: 1px solid var(--link); outline-offset: -1px; }
.nosrc { padding: 8px 14px; color: var(--muted); }
table.src > tbody > tr > td { padding-top: 0; padding-bottom: 0; }
table.src td.ln { color: var(--muted); user-select: none; }
tr.rowlink { cursor: pointer; }
table.src tr.clickable { cursor: pointer; }
table.src tr.clickable:hover td.ln { color: var(--link); }
table.src td.self, table.src td.incl, table.src td.x { color: var(--muted); }
/* the row's self-cost heat (tr[style]) only colors .ln/.self/.code -- .incl
   ("calls") and .x (D1m/DLm/Bcm) carry their own independent cost and, for
   .x, their own inline heat background (extraCells' style=), so they must
   never inherit the row's text color: that would recolor text sitting on
   one background (or none) using contrast computed for a different one. */
table.src tr.heat td.ln, table.src tr.heat td.self, table.src tr.heat td.code { color: inherit; }
table.src td.hot { font-weight: 600; }
/* a line longer than the source column clips at the column's edge (no
   ellipsis: it's code), same as every other cell; drag the trailing bar to
   see more. It never spills past the table, so the table's width is the
   whole of what can scroll sideways (see .srcwrap). */
table.src td.code { text-overflow: clip; white-space: pre; tab-size: 4; }
table.src tr.hasc td.ln::before { content: "\\25B8 "; color: var(--link); }
table.src tr.target td { box-shadow: inset 0 0 0 2px var(--accent); }
/* the direct-child combinator matters here: "tr.detail td" (no >) would also
   match every <td> inside the popup's own nested tables (.dbox's callee/
   caller tables), overriding their table.cols overflow:hidden/nowrap with
   higher specificity than that rule (three classes+types beats table.cols
   td's two) and letting long function names visibly overlap the next
   column instead of being clipped with an ellipsis. */
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
<script>
(function () {
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

// ---------- events ----------
// Every cost is a vector in D.meta.events order (trailing zeros dropped).
// EVS lists the raw events that occurred plus the derived ones (sums of raw
// columns) whose inputs exist; the selected one drives heat, sorting and the
// self/calls columns. EXTRA are the always-visible miss columns.
const at = (v, i) => (v && i < v.length) ? v[i] : 0;
const EVS = [];
D.meta.events.forEach((n, i) => { if (at(D.meta.totals, i) > 0) EVS.push({ key: n, long: D.meta.eventLong[n] || "", get: v => at(v, i) }); });
for (const [n, terms, long] of D.meta.derived) {
  const get = v => terms.reduce((s, t) => s + t[0] * at(v, t[1]), 0);
  if (get(D.meta.totals) > 0) EVS.push({ key: n, long: long || D.meta.eventLong[n] || "", get, derived: true });
}
const evByKey = k => EVS.find(e => e.key === k);
let ev = evByKey(store.get("heat.event")) || evByKey(D.meta.defaultEvent) || EVS[0];
const EXTRA = ["D1m", "DLm", "Bcm"].map(evByKey).filter(Boolean);
// Short plain-language name for every event key callgrind can emit plus the
// derived ones (mirrors callgrind.py's EVENT_LONG / DERIVED_DEFAULTS, kept
// short enough for an inline label). evLabel() is "short / KEY" wherever a
// key would otherwise stand alone with no long name next to it.
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
// Fixed to the longest option's width (+ slack for the native dropdown
// arrow) so picking a shorter/longer event never reflows the header row.
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

// ---------- helpers ----------
const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const pct = v => 100 * v / TOTAL;
const fmtP = p => p >= 9.95 ? p.toFixed(1) + "%" : p >= 0.01 ? p.toFixed(2) + "%" : p > 0 ? "<0.01%" : ""; // theme.num_pct()
const fmtPct = v => fmtP(pct(v));
const fmtN = v => v.toLocaleString("en-US"); // exact; tooltips only
// 2.1K, 21K, 210K, 2.1M, 2.0G: at least two meaningful digits (theme.num_human() in theme.py)
function fmtH(v) {
  let unit = "";
  for (const u of ["K", "M", "G", "T"]) { if (v < 999.5) break; v /= 1000; unit = u; }
  return (unit && v < 9.95 ? v.toFixed(1) : v.toFixed(0)) + unit;
}
const num = v => ({ text: fmtH(v), title: fmtN(v) }); // a count cell: short, exact on hover
const PMIN = 0.001; // lines below 0.001% of total stay uncolored in log mode
function heatP(p, maxP) {
  if (p <= 0) return 0;
  if (scale === "linear") return Math.min(1, p / maxP);
  if (p < PMIN) return 0;
  return Math.min(1, Math.log10(p / PMIN) / Math.log10(Math.max(maxP, PMIN * 10) / PMIN));
}
function heatT(cost, maxP) { return heatP(pct(cost), maxP); }
// The ramp color at t, blended over the page background (alpha grows with
// t), plus a text color that keeps contrast on the result. Same math as
// theme.heat_style() in theme.py.
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
const heatBgSoft = t => heatStyle(t, 0.12, 0.55); // tree rows: keep names readable
function hashFor(path, line) {
  const parts = ["f=" + encodeURIComponent(path)];
  if (line) parts.push("l=" + line);
  if (EVS.length > 1) parts.push("e=" + encodeURIComponent(ev.key));
  return "#" + parts.join("&");
}
function fnName(i) { return (i != null && fns[i]) ? fns[i].name : "?"; }
function link(path, line, text) { return files[path] && line ? `<a href="${hashFor(path, line)}">${esc(text)}</a>` : esc(text); }
const SYMBOL_CHARS = 20; // visible characters of a function name before it is cut off

// A .tbl box: a fixed-layout table with widths in characters (everything is
// monospace). Mirrors theme.table_render() in theme.py. cols: {label, title,
// num, width, clip, cls}; cells: a string, or {text, html, style, cls, title}.
// opts.rowHref: one hash per row (or "" to skip) makes the whole row a click
// target (see the delegated click handler below, "row-click"), even though
// only the "defined at" cell's own <a> visibly reacts to hover -- a plain
// row has nothing else to click on, and repeating the link's hover style
// on every cell would suggest each cell opens something different.
const PAD = 3; // 1ch padding each side + 1ch slack for the divider bar and ch rounding
const PCTW = "-100.0%".length; // width floor for any col with neither `width` nor `clip`: it only ever
                                // holds a percentage/count short enough to fit "-100.0%"; scanning actual
                                // cell text let a long header label (e.g. "L1 cache / D1m") balloon the
                                // column into a wide heat-colored block for a tiny value -- the header
                                // still gets its full text as a tooltip and just ellipsizes on screen.
function table(key, cols, rows, opts) {
  opts = opts || {};
  const cell = c => (c && typeof c === "object") ? c : { text: c == null ? "" : String(c) };
  const rc = rows.map(r => r.map(cell));
  const widths = cols.map((col, i) => {
    if (col.width != null) return col.width + PAD;
    if (col.clip != null) {
      let n = col.label.length;
      for (const r of rc) if (r[i]) n = Math.max(n, (r[i].text || "").length);
      return Math.min(n, col.clip) + PAD;
    }
    return Math.max(col.label.length, PCTW) + PAD;
  });
  let h = `<div class="tbl">`;
  h += `<div class="tbl-cols"><table class="cols" data-key="${esc(key)}"><colgroup>`;
  cols.forEach((c, i) => { h += `<col${i % 2 ? ' class="alt"' : ""} style="width:${widths[i]}ch">`; });
  h += `</colgroup><thead><tr>`;
  for (const c of cols) h += `<th${c.num ? ' class="n"' : ""}${c.title ? ` title="${esc(c.title)}"` : ""}>${esc(c.label)}</th>`;
  h += `</tr></thead><tbody>`;
  rc.forEach((r, ri) => {
    const href = opts.rowHref && opts.rowHref[ri];
    h += href ? `<tr class="rowlink" data-href="${esc(href)}">` : "<tr>";
    r.forEach((c, i) => {
      const col = cols[i] || {};
      const cls = [col.num ? "n" : "", col.cls || "", c.cls || ""].filter(Boolean).join(" ");
      const text = c.text || "", title = c.title || ((text.length + PAD > widths[i]) ? text : "");
      h += `<td${cls ? ` class="${cls}"` : ""}${c.style ? ` style="${c.style}"` : ""}${title ? ` title="${esc(title)}"` : ""}>${c.html != null ? c.html : esc(text)}</td>`;
    });
    h += "</tr>";
  });
  h += `</tbody></table></div>`;
  return h + `</div>`;
}
// Plain-text twin of table(): a GFM pipe table, space-padded so the columns
// line up whether it's pasted raw or rendered as markdown -- same cols/rows
// inputs, so it can never drift out of sync with what the box shows.
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

// ---------- tree ----------
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

// ---------- function entry index: file -> line -> fn index ----------
const entryIdx = {};
fns.forEach((f, i) => { if (f.line) { (entryIdx[f.file] = entryIdx[f.file] || {})[f.line] = i; } });

// ---------- views ----------
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
      const f = fns[fi], loc = f.line ? f.file + ":" + f.line : f.file, ncalls = f.callers.reduce((a, c) => a + c[4], 0);
      return [String(i + 1),
              { text: fmtPct(s), style: heatBg(heatT(s, MAXP)) },
              { text: f.name, title: f.name },
              { text: loc, html: link(f.file, f.line, loc) },
              ncalls ? num(ncalls) : "", fmtPct(s + val(f.calls)), ...extraCells(f.self)];
    }), { rowHref: topF.map(([fi]) => hashFor(fns[fi].file, fns[fi].line)) });
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
  const first = curFile !== path;
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
  const cols = [{ label: "line", num: true }, evCol(ev, { title: ev.long + ", share of total, spent on the line itself" }),
                { label: "calls", title: "total cost of the calls made from the line, share of total", num: true },
                ...extraCols(), { label: "source" }];
  const hot = Object.keys(lines).map(k => [+k, val(lines[k][0])]).filter(t => t[1] > 0).sort((a, b) => b[1] - a[1]).slice(0, 12);
  if (hot.length) {
    h += `<div class="chips"><span class="lbl">hottest lines</span>`;
    for (const [ln, cost] of hot) h += `<span class="chip" data-goto="${ln}" style="${heatBg(heatT(cost, maxP))}">${ln} \\u00b7 ${fmtPct(cost)}</span>`;
    h += `</div>`;
  }
  const rows = [];
  const emitRow = (ln, text) => {
    const rec = lines[ln];
    const self = rec ? val(rec[0]) : 0, calls = rec ? val(rec[1]) : 0;
    const t = heatT(self, maxP), hs = heatBg(t);
    const fnidx = f.lfn[ln];
    const title = rec ? `${fmtN(self)} ${ev.key} self, ${fmtN(calls)} in calls${rec[2] ? " over " + fmtH(rec[2]) + " calls" : ""}${fnidx != null ? " \\u2014 in " + fnName(fnidx) : ""}` : "";
    const xs = rec ? extraCells(rec[0]).map(c => `<td class="n x${c.cls ? " " + c.cls : ""}" style="${c.style}" title="${esc(c.title)}">${esc(c.text)}</td>`).join("") : EXTRA.map(() => `<td class="n x"></td>`).join("");
    const cls = [rec ? "clickable" : "", f.callees[ln] ? "hasc" : "", line === ln ? "target" : "", hs ? "heat" : ""].filter(Boolean).join(" ");
    rows.push(`<tr id="L${ln}" class="${cls}" style="${hs}"${title ? ` title="${esc(title)}"` : ""}><td class="n ln" data-ln="${ln}">${ln}</td><td class="n self${t > 0.45 ? " hot" : ""}">${self ? fmtPct(self) : ""}</td><td class="n incl">${calls ? fmtPct(calls) : ""}</td>${xs}<td class="code">${text == null ? "" : esc(text)}</td></tr>`);
  };
  const srcl = f.src.split("\\n");
  if (srcl.length && srcl[srcl.length - 1] === "") srcl.pop();
  let nlines = srcl.length;
  for (let i = 0; i < srcl.length; i++) emitRow(i + 1, srcl[i]);
  for (const k of Object.keys(lines)) if (+k > srcl.length) { nlines = Math.max(nlines, +k); emitRow(+k, "(line beyond end of file: source changed since the profile was taken)"); }
  h += `<div class="tbl-cols"><table class="cols fill src" data-key="heat.src"><colgroup>`;
  cols.forEach((c, i) => {
    // line numbers carry a 2-character call marker; the cost columns fit "-100.0%"
    const w = (i === 0 ? String(nlines).length + 2 : PCTW) + PAD;
    h += `<col${i % 2 ? ' class="alt"' : ""}${i === cols.length - 1 ? "" : ` style="width:${w}ch"`}>`;
  });
  h += `</colgroup><thead><tr>${cols.map(c => `<th${c.num ? ' class="n"' : ""}${c.title ? ` title="${esc(c.title)}"` : ""}>${esc(c.label)}</th>`).join("")}</tr></thead><tbody>`;
  h += rows.join("") + `</tbody></table></div></div>`;
  mainEl.innerHTML = h;
  renderTree();
  // The minimap band goes up before the listing's width is settled: it
  // narrows the pane by its own width, and Theme.init's 90% fill measures
  // the pane as it is at that moment.
  minimapBuild();
  Theme.init(mainEl);
  srcCenter();
  if (line) {
    const el = document.getElementById("L" + line);
    if (el) { centerRow(el); toggleDetail(path, line, true); }
  } else if (first) {
    const hottest = hot.length ? hot[0][0] : 0;
    const el = hottest ? document.getElementById("L" + hottest) : null;
    if (el) centerRow(el); else mainEl.scrollTop = 0;
  }
  minimapSync();
}
// The height of what stays put over the top of the pane while the listing
// scrolls under it: the sticky header band plus the (sticky) header cells
// -- the cells, not the <thead>, which scrolls away like any other box.
function coverH(table) {
  let h = table.tHead.rows[0].cells[0].getBoundingClientRect().height;
  for (const b of mainEl.querySelectorAll(".band")) h += b.getBoundingClientRect().height;
  return h;
}
// Scrolls the pane so the row sits mid-way down the part of it not under
// the sticky header -- vertically only. scrollIntoView would also pull the
// pane sideways to bring a row wider than the pane into view, shifting a
// listing the reader has dragged wider than the pane every time a chip or
// a "defined at" link is followed.
function centerRow(el) {
  const cover = coverH(el.closest("table"));
  const r = el.getBoundingClientRect(), m = mainEl.getBoundingClientRect();
  mainEl.scrollTop += r.top - m.top - cover - (mainEl.clientHeight - cover - r.height) / 2;
}
// Centers the listing in the pane: Theme.init opened it at 90% of the pane's
// width (fillBaseline), so equal side margins of the leftover put it at 5%
// from either edge. Whole pixels, so the margins never overshoot the pane
// by a fraction and raise a horizontal scrollbar. Computed once per render
// (and again on "reset columns", which re-derives the 90% too); dragging a
// column wider grows the listing rightward from that fixed left margin,
// with the same margin kept after its trailing bar (a margin on a
// max-content wrapper's child counts toward the wrapper's width).
function srcCenter() {
  const box = mainEl.querySelector(".srcwrap > .tbl-cols");
  if (!box) return;
  const table = box.querySelector("table");
  const gap = Math.max(0, Math.floor((mainEl.clientWidth - table.getBoundingClientRect().width) / 2));
  box.style.marginLeft = box.style.marginRight = gap + "px";
}

// ---------- minimap ----------
// A VS-Code-style scaled thumbnail of the current file's source column,
// between #split and #main. Built once per renderFile call by cloning the
// live table.src rows (dropping every column but .code, since only the
// source's own coloring is wanted, not line/self/calls/event) rather than
// re-rendering from the model a second time -- this way it can never drift
// out of sync with what the source table actually shows. CSS transform:
// scale() then shrinks the clone to fit; the clone itself is never
// rebuilt except by the next renderFile, so resize only has to reposition
// and rescale the existing DOM (minimapLayout), not re-snapshot it.
const MM_MIN_COLS = 80; // never zoom in tighter (wider effective scale) than 80 source columns
const MM_MIN_LINES = 40; // below this the file can't scroll off-screen; omit the minimap
let mmChPx = 0, mmScale = 1, mmCloneH = 0;
function minimapClear() {
  minimapEl.classList.add("empty");
  mmBox.innerHTML = "";
  mmViewport.hidden = true;
}
function minimapBuild() {
  const table = mainEl.querySelector("table.src"), tbody = table && table.tBodies[0];
  if (!tbody || tbody.rows.length < MM_MIN_LINES) { minimapClear(); return; }
  // Measure the monospace cell size straight from the live table so the
  // clone's scale is exact regardless of font metrics.
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
    if (row.classList.contains("detail")) continue; // never open at build time, but be safe
    const code = row.querySelector("td.code");
    if (!code) continue;
    const tr = document.createElement("tr");
    tr.className = row.className;
    tr.style.cssText = row.style.cssText;
    tr.appendChild(code.cloneNode(true));
    body.appendChild(tr);
  }
  clone.appendChild(body);
  mmBox.innerHTML = "";
  mmBox.appendChild(clone);
  minimapEl.classList.remove("empty"); // display: none while empty -- unhide before measuring
  mmViewport.hidden = false;
  mmCloneH = clone.offsetHeight; // unscaled: offsetHeight ignores mmBox's transform
  minimapLayout();
}
// The true band height comes from #minimap's own flex-stretched layout size
// (#layout's align-items: stretch, unset anywhere in CSS) and must never be
// read back off #minimap after minimapLayout has touched it -- earlier this
// function shortened #minimap itself to the scaled content height, so a
// later call (e.g. on window resize, or the next file's minimapBuild) read
// clientHeight off a band that was still shrunk from a previous short file,
// permanently capping it below the real available height. Fixed here by
// never resizing #minimap: it always stays the full band, and "shorter than
// the content" is represented purely by mmBox not filling the space below
// -- a click past the end of the scaled content just scrolls to the end.
function minimapLayout() {
  if (minimapEl.classList.contains("empty")) return;
  const bandW = minimapEl.clientWidth, bandH = minimapEl.clientHeight;
  // Scale is pinned to fit exactly MM_MIN_COLS (80) source columns in the
  // band -- never zoomed out further for a file with longer lines, so every
  // row's heat background always reaches the band's right edge (a short
  // file's shorter lines would otherwise leave a gap there, and previously
  // the scale shrank per-file to whatever the actual longest line was,
  // which produced inconsistent zoom levels file to file). A line longer
  // than 80 columns overflows mmBox rather than being fitted; #minimap's
  // own overflow:hidden clips it, same as it always clipped anything below
  // the visible band vertically.
  // The whole file must still fit the band vertically -- minimapSync's
  // viewport math (and the "never scrolls on its own" design, see its
  // comment above) assumes the full clone is what's on screen; without this
  // the width-only scale left tall files' minimap frozen on their first
  // screenful while the viewport box kept sliding down past content that
  // was never actually drawn.
  mmScale = Math.min(1, bandW / (MM_MIN_COLS * mmChPx), bandH / mmCloneH);
  mmBox.style.transform = `scale(${mmScale})`;
  mmBox.style.transformOrigin = "top left";
  mmBox.style.width = (bandW / mmScale) + "px";
  minimapSync();
}
// What the viewport box mirrors, read live off the listing every time
// (nothing is cached across scrolls, so a header band that re-wraps on
// resize or a detail popup opening under a row can't put the box out of
// step): `rows` is the height of the source rows alone (an open detail
// popup's row excluded -- the clone never has one), `above(y)` how many of
// those row pixels lie above client-y `y`, `cover` what hides the top of
// the pane once the listing has scrolled up under it (coverH). The first
// visible row is the one right under the header cells' bottom edge
// (`head`): while the listing is still below the header in flow, that edge
// is the body's own top, so nothing is hidden; once stuck, everything
// scrolled past it is.
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
  const r0 = g.above(g.head), r1 = g.above(g.bottom); // the rows on screen, as row pixels from the top
  const h = Math.max(8, scaledH * (r1 - r0) / g.rows);
  mmViewport.style.top = Math.max(0, Math.min(scaledH - h, scaledH * r0 / g.rows)) + "px";
  mmViewport.style.height = h + "px";
}
// Scrolls #main so that `r0` row pixels sit hidden above the sticky header
// band and table head: the inverse of minimapSync's r0.
function mmScrollTo(r0) {
  const g = mmGeom();
  r0 = Math.max(0, Math.min(g.rows, r0));
  let y = g.body.top - g.top + mainEl.scrollTop + r0 - g.cover; // that row's scroll position, less what covers it
  if (g.detail && g.detail.top - g.body.top < r0) y += g.detail.height; // an open popup above it shifts it down
  mainEl.scrollTop = Math.max(0, Math.min(mainEl.scrollHeight - mainEl.clientHeight, y));
}
mainEl.addEventListener("scroll", minimapSync);
minimapEl.addEventListener("click", e => {
  if (e.target.closest("#mmViewport")) return; // the viewport box has its own drag handler
  const g = mmGeom(), scaledH = mmCloneH * mmScale;
  const r = (e.clientY - minimapEl.getBoundingClientRect().top) / scaledH * g.rows; // the row pixel under the pointer
  mmScrollTo(r - (mainEl.clientHeight - g.cover) / 2); // centered on screen
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
  e.stopPropagation(); // don't also trigger the bare-background click-to-jump
});

function toggleDetail(path, ln, forceOpen) {
  const f = files[path];
  const row = document.getElementById("L" + ln);
  if (!row) return;
  const next = row.nextElementSibling;
  if (next && next.classList.contains("detail")) { if (!forceOpen) next.remove(); return; }
  document.querySelectorAll("tr.detail").forEach(e => e.remove());
  const callees = (f.callees[ln] || []).slice().sort((a, b) => val(b[3]) - val(a[3]));
  const fi = (entryIdx[path] || {})[ln];
  const fnidx = f.lfn[ln];
  const rec = f.lines[ln] || [[], [], 0];
  const fnCol = label => ({ label, title: `first ${SYMBOL_CHARS} characters; drag the bar for more`, width: SYMBOL_CHARS });
  const locCol = { label: "defined at", title: "file:line of the function's first executed line", clip: 48 };
  const callsClause = val(rec[1]) ? `, calls ${fmtH(val(rec[1]))} (${fmtPct(val(rec[1]))}) over ${fmtH(rec[2])} calls` : "";
  const extraStats = xs => xs.map(x => { const s = x.get(rec[0]); return s ? `, ${evLabel(x)} ${fmtP(100 * s / MAXPX[x.key].total)} (${fmtH(s)})` : ""; }).join("");
  // Entry lines skip "in fnName" and "line": the "entered here" heading right below already names the function.
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
      return [fmtPct(val(vec)), num(val(vec)), num(count), { text: fnName(ci), title: fnName(ci) }, { text: loc, html: link(cf, cl, loc) }];
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
        return [num(count), fmtPct(val(vec)), num(val(vec)), { text: fnName(ci), title: fnName(ci) }, { text: loc, html: link(cf, cl, loc) }];
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
  tr.innerHTML = `<td colspan="${4 + EXTRA.length}">${h}</td>`;
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
  if (close) { ev2.preventDefault(); close.closest("tr.detail").remove(); minimapSync(); return; }
  if (ev2.target.closest("a")) return; // let the row's own link (e.g. "defined at") handle its own click
  const linkRow = ev2.target.closest("tr.rowlink");
  if (linkRow) { location.hash = linkRow.dataset.href; return; }
  const row = ev2.target.closest("tr.clickable");
  // a popup opening or closing changes which rows are on screen without a scroll event
  if (row && curFile) { toggleDetail(curFile, +row.querySelector("td.ln").dataset.ln, false); minimapSync(); return; }
});

// ---------- routing ----------
// The hash is the one source of truth for "what's on screen" (file, line,
// event) so a link into this page -- including one relayed through the
// outer frame's own hash, see syncHash()/FRAME_JS -- reopens the same view.
// applyEvent() only updates state (no navigation); setEvent() is the
// user-facing entry point (select box) that also rewrites the hash.
function applyEvent(key) {
  ev = evByKey(key) || EVS[0];
  store.set("heat.event", ev.key);
  recomputeScale();
  TREE = buildTree();
  for (const d of TREE.dirs.values()) if (d.self / TOTAL > 0.05) openDirs.add(d.path);
}
function curLine() {
  const d = mainEl.querySelector("tr.detail");
  const id = d && d.previousElementSibling && d.previousElementSibling.id;
  return id && id[0] === "L" ? +id.slice(1) : 0;
}
// Rewrites location.hash to match what's actually rendered right now
// (replaceState: a view refinement of the same page, not a new history
// entry) and relays it to the outer frame page, if any, so FRAME_JS can
// mirror it into the top-level URL -- see the "message" listener there.
function syncHash() {
  const hash = curFile ? hashFor(curFile, curLine()) : (EVS.length > 1 ? "#e=" + encodeURIComponent(ev.key) : "#");
  if (hash !== location.hash) history.replaceState(null, "", hash || "#");
  if (window.parent !== window) window.parent.postMessage({ theme: "hash", hash: hash || "" }, "*");
}
// Renders whatever the hash currently names (file+line, if any) using
// whatever event is currently applied, then syncs the hash to match --
// shared by route() (hash changed elsewhere: parse it first) and setEvent()
// (event changed here: ev is already right, no re-parse wanted, or a stale
// e= still in the hash would immediately override the just-applied value).
function renderFromHash() {
  const m = /^#(?:f=([^&]*))?(?:&?l=(\\d+))?/.exec(location.hash);
  evSel.value = ev.key;
  if (m && m[1]) renderFile(decodeURIComponent(m[1]), m[2] ? +m[2] : 0);
  else renderHome();
  syncHash();
}
function route() {
  const m = /^#(?:f=[^&]*)?(?:&?l=\\d+)?(?:&?e=([^&]*))?/.exec(location.hash);
  const key = m && m[1] ? decodeURIComponent(m[1]) : null;
  if (key && evByKey(key) && key !== ev.key) applyEvent(key);
  renderFromHash();
}
function setEvent(key) {
  applyEvent(key);
  renderFromHash();
}
window.addEventListener("hashchange", route);
// Re-picking [heat map] in an outer strip while already showing this page
// (see FRAME_JS in build_report.py) posts this instead of reloading the
// iframe, so it jumps back to the hottest-lines/functions overview.
window.addEventListener("message", e => {
  if (e.data === "theme:home") location.hash = "";
  else if (e.data === "theme:reset-cols") { Theme.resetCols(mainEl); srcCenter(); }
});
// Same 120ms-debounced resize pattern as theme.js's own relayout() listener
// (kept separate rather than folded into Theme.relayout: the minimap only
// needs to reposition/rescale existing DOM, never re-snapshot it).
let mmResizeTimer = null;
window.addEventListener("resize", () => { clearTimeout(mmResizeTimer); mmResizeTimer = setTimeout(minimapLayout, 120); });
evSel.addEventListener("change", e => setEvent(e.target.value));
document.getElementById("scale").addEventListener("change", e => { scale = e.target.value; store.set("heat.scale", scale); route(); });
document.getElementById("sort").addEventListener("change", e => { sortMode = e.target.value; store.set("heat.sort", sortMode); renderTree(); });
document.getElementById("q").addEventListener("input", e => { query = e.target.value.trim().toLowerCase(); renderTree(); });
applyEvent(ev.key);
route();
})();
</script>
"""


def heatmap_render(model: dict, title: str) -> str:
    data = json.dumps(model, separators=(",", ":"), ensure_ascii=False)
    data = data.replace("</", "<\\/")  # never close our own <script>
    body = BODY.replace("__THEME_JS__", theme.theme_js()).replace("__DATA__", data)
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{theme.html_esc(title)}</title>\n<style>\n{theme.theme_css()}{CSS}</style>\n</head>\n<body>\n"
            + body + "</body>\n</html>\n")


# --------------------------------------------------------------------------


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
    args = ap.parse_args()

    prof = cg.profile_load(args.callgrind_file)
    if not prof.events:
        sys.exit("error: no 'events:' line -- not a callgrind file?")
    src_name = os.path.basename(args.callgrind_file[0])
    if len(args.callgrind_file) > 1:
        src_name += f" + {len(args.callgrind_file) - 1} more"
    if args.title is None:
        args.title = f"heat map: {prof.cmd or src_name}"

    self_sum, total, ratio = cg.profile_self_check(prof)
    print(f"events: {' '.join(prof.events)}", file=sys.stderr)
    print(f"callgrind summary ({prof.events[0]}): {total:,}", file=sys.stderr)
    print(f"sum of self-cost lines:          {self_sum:,}", file=sys.stderr)
    print(f"ratio (must be 1.0000):          {ratio:.4f}", file=sys.stderr)
    if total and abs(ratio - 1.0) > 1e-6:
        print("error: per-line self cost does not add up to callgrind's summary; refusing to write", file=sys.stderr)
        sys.exit(2)

    model = model_build(prof, args)
    html = heatmap_render(model, args.title)
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
