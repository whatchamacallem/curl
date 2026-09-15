#!/usr/bin/env python3
"""Turn a callgrind profile into a self-contained "source heatmap" web page.

The page is a file explorer over the profiled source tree: directories and
files are colored/sorted by how much of the selected event (instructions by
default; any cache-miss or branch event callgrind recorded can be picked from
the header) was spent inside them, and each file opens as a source listing
with every line colored by its self cost. Beside the selected event, every
line also shows its L1 data misses, LL data misses and conditional-branch
mispredicts (when the profile was taken with --cache-sim / --branch-sim), so
a line that is cheap in instructions but hurts in misses is visible without
switching events. Clicking a line number shows every event for that line,
what it calls (inclusive cost) and, on a function's first line, who calls it,
so you can click down or up the call graph across files. Everything is
embedded in one HTML file (no server, no CDN), so it can be opened from
file:// or mailed around.

Parsing and per-line attribution live in callgrind.py (same directory) and
mirror callgrind_annotate exactly; the self-check ratio it computes (sum of
self-cost lines / callgrind's own summary) is printed to stderr on every run
and must be 1.0000.

Usage:
  callgrind_to_heatmap.py callgrind.out.X -o report/heat-map/index.html \
      [--event Ir] [--repo-root .] [--tree lib include src tests/perf] \
      [--all-sources] [--title "..."] [--bare]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import posixpath
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind as cg  # noqa: E402


# --------------------------------------------------------------------------
# Path handling / source loading
# --------------------------------------------------------------------------


def norm_path(path: str, repo_root: str) -> tuple[str, str | None, str]:
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


def read_source(local: str) -> str | None:
    try:
        with open(local, "rb") as f:
            data = f.read()
    except OSError:
        return None
    return data.decode("utf-8", errors="replace")


def tracked_files(repo_root: str, dirs: list[str]) -> list[str]:
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


def trim(vec: list[int]) -> list[int]:
    """Drop trailing zeros; the page pads on read. Keeps the model small."""
    n = len(vec)
    while n and vec[n - 1] == 0:
        n -= 1
    return vec[:n]


def build_model(p: cg.Profile, args: argparse.Namespace, src_name: str) -> dict:
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
        d, loc, g = norm_path(raw, repo_root)
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
        entry = files.setdefault(d, {
            "self": [0] * nev, "calls": [0] * nev, "src": None, "lines": {}, "lfn": {},
            "callees": {}, "group": group[raw], "raw": raw,
        })
        if entry["src"] is None and local[raw]:
            entry["src"] = read_source(local[raw])
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
            [fn_index[callee], disp.get(ef, ef), el, trim(vec), count])
    for e in files.values():
        for lst in e["callees"].values():
            lst.sort(key=lambda t: -(t[3][0] if t[3] else 0))
        for rec in e["lines"].values():
            rec[0] = trim(rec[0])
            rec[1] = trim(rec[1])
        e["self"] = trim(e["self"])
        e["calls"] = trim(e["calls"])

    functions = []
    for name in fn_names:
        home = p.fn_home[name]
        ef, el = p.fn_entry.get(name, (home, 0))
        callers = sorted(
            ([fn_index[cf], disp.get(cfile, cfile), cl, trim(vec), count]
             for (cf, cfile, cl), (count, vec) in p.callers[name].items()),
            key=lambda t: -(t[3][0] if t[3] else 0))
        functions.append({
            "name": name,
            "file": disp.get(ef, ef),
            "line": el,
            "self": trim(p.fn_self.get(name, [])),
            "calls": trim(p.fn_calls.get(name, [])),
            "callers": callers,
        })

    # cold files: tracked sources in the requested dirs with no samples
    cold: list[str] = []
    for rel in tracked_files(repo_root, args.tree):
        if rel in files:
            continue
        if args.all_sources:
            src = read_source(os.path.join(repo_root, rel))
            files[rel] = {"self": [], "calls": [], "src": src, "lines": {}, "lfn": {},
                          "callees": {}, "group": "repo", "raw": rel}
        else:
            cold.append(rel)

    derived = [[name, [[c, i] for c, i in terms], long] for name, terms, long in p.derived_terms()]
    default_event = args.event if args.event in p.event_names() else (p.events[0] if p.events else "Ir")
    return {
        "meta": {
            "title": args.title,
            "events": p.events,
            "eventLong": {n: p.event_long.get(n, "") for n in p.event_names()},
            "derived": derived,
            "defaultEvent": default_event,
            "totals": p.totals(),
            "desc": p.desc,
            "stats": cg.totals_report(p),
            "cmd": p.cmd,
            "source": src_name,
            "generated": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "repoRoot": repo_root,
            "allSources": bool(args.all_sources),
        },
        "files": files,
        "functions": functions,
        "cold": sorted(cold),
    }


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

HEAD = """<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono:wght@400;600&display=swap">
<style>
:root {
  color-scheme: light;
  --bg: #fbfbfc; --fg: #1b1d22; --muted: #6b6f7a; --panel: #f1f2f5;
  --border: #d8dae0; --accent: #0b5fcc; --sel: #e1ebfb; --code: #22252c;
  --heat-l: 52%;
  --sans: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #121418; --fg: #e6e7ea; --muted: #979ba6; --panel: #1b1e24;
    --border: #31353e; --accent: #7cb0ff; --sel: #22385c; --code: #e6e7ea;
    --heat-l: 42%;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #121418; --fg: #e6e7ea; --muted: #979ba6; --panel: #1b1e24;
  --border: #31353e; --accent: #7cb0ff; --sel: #22385c; --code: #e6e7ea;
  --heat-l: 42%;
}
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; }
body { background: var(--bg); color: var(--fg);
  font: 13px/1.45 var(--sans);
  display: flex; flex-direction: column; height: 100vh; }
a { color: var(--accent); text-decoration: none; cursor: pointer; }
a:hover { text-decoration: underline; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
#hdr { display: flex; gap: 10px 16px; align-items: center; flex-wrap: wrap;
  padding: 6px 16px; border-bottom: 1px solid var(--border); background: var(--panel); }
#hdr h1 { font-size: 15px; margin: 0; white-space: nowrap; }
#hdr h1 a { color: inherit; }
#hdr .meta { color: var(--muted); font-size: 12px; }
#hdr label { color: var(--muted); font-size: 12px; white-space: nowrap; }
#hdr select, #hdr input { font: inherit; font-size: 12px; background: var(--bg); color: var(--fg);
  border: 1px solid var(--border); border-radius: 4px; padding: 2px 6px; }
#hdr input { width: 200px; }
#layout { display: flex; flex: 1; min-height: 0; }
#tree { width: 280px; min-width: 160px; max-width: 60vw; overflow: auto; resize: horizontal;
  border-right: 1px solid var(--border); padding: 4px 0 24px; font-size: 12.5px; }
#main { flex: 1; min-width: 0; overflow: auto; }
.node { display: flex; align-items: center; gap: 4px; padding: 1px 8px 1px 0;
  cursor: pointer; white-space: nowrap; }
.node:hover { outline: 1px solid var(--accent); outline-offset: -1px; }
.node.sel { background: var(--sel); }
.node .caret { width: 12px; flex: none; text-align: center; color: var(--muted); font-size: 9px; }
.node.file .caret { visibility: hidden; }
.node .name { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
.node.dir .name { font-weight: 600; }
.node.cold .name { color: var(--muted); font-weight: 400; }
.node .pct { flex: none; width: 56px; text-align: right; font-variant-numeric: tabular-nums;
  color: var(--muted); font-size: 11.5px; }
.node.cold .pct { visibility: hidden; }
.node.more .name { color: var(--muted); font-style: italic; font-size: 11.5px; }
table.src tr.th td { color: var(--muted); font-size: 10.5px; padding-top: 4px; padding-bottom: 2px;
  position: sticky; top: 0; background: var(--bg); z-index: 1; }
.kids { display: none; }
.kids.open { display: block; }
#main .fhead { position: sticky; top: 0; z-index: 2; background: var(--panel);
  border-bottom: 1px solid var(--border); padding: 6px 16px; display: flex; gap: 8px 18px;
  align-items: baseline; flex-wrap: wrap; }
#main .fhead .path { font-weight: 600; font-size: 14px; }
#main .fhead .stat { color: var(--muted); font-size: 12px; }
#main .fhead .stat b { color: var(--fg); }
.chips { display: flex; gap: 4px; flex-wrap: wrap; padding: 6px 16px; border-bottom: 1px solid var(--border); }
.chips .lbl { color: var(--muted); font-size: 12px; align-self: center; margin-right: 4px; }
.chip { font: 11.5px var(--mono); padding: 1px 7px; border-radius: 10px;
  border: 1px solid var(--border); cursor: pointer; color: var(--fg); }
.chip:hover { outline: 1px solid var(--accent); }
table.src { border-collapse: collapse; width: 100%; font: 12px/1.42 var(--mono); font-variant-numeric: tabular-nums; }
table.src td { padding: 0 8px; vertical-align: top; white-space: pre; }
td.ln { text-align: right; color: var(--muted); user-select: none; width: 1%; cursor: pointer; }
td.ln:hover { color: var(--accent); }
td.self, td.incl, td.x { text-align: right; width: 1%; font-variant-numeric: tabular-nums; color: var(--muted); }
td.self.hot { color: var(--fg); font-weight: 600; }
td.x { border-left: 1px dotted var(--border); }
td.x.hot { color: var(--fg); }
td.incl { border-right: 1px solid var(--border); }
td.code { tab-size: 4; color: var(--code); }
tr.hasc td.ln::before { content: "\\25B8 "; color: var(--accent); }
tr.target td { box-shadow: inset 0 0 0 2px var(--accent); }
tr.detail td { white-space: normal; padding: 0; }
.dbox { margin: 3px 12px 8px 12px; padding: 6px 12px; background: var(--panel);
  border: 1px solid var(--border); border-radius: 6px; font: 12px var(--sans); }
.dbox h4 { margin: 4px 0 2px; font-size: 12px; color: var(--muted); font-weight: 600; }
.dbox table { border-collapse: collapse; }
.dbox td { padding: 1px 10px 1px 0; white-space: nowrap; }
.dbox td.n { text-align: right; font-variant-numeric: tabular-nums; }
.dbox td.m { color: var(--muted); }
.dbox .evs { display: flex; gap: 24px; flex-wrap: wrap; }
.nosrc { padding: 8px 16px; color: var(--muted); }
.home { padding: 14px 20px 40px; max-width: 1200px; }
.home h2 { font-size: 14px; margin: 18px 0 6px; }
.home h2:first-child { margin-top: 4px; }
.home p { color: var(--muted); margin: 4px 0; max-width: 90ch; }
.home pre { font: 12px/1.4 var(--mono); background: var(--panel); border: 1px solid var(--border);
  border-radius: 6px; padding: 8px 12px; overflow-x: auto; margin: 4px 0; }
.tbl-wrap { position: relative; overflow: auto; max-height: 70vh; margin: 4px 0 8px;
  border: 1px solid var(--border); border-radius: 6px; }
.tbl-legend { display: flex; gap: 4px 14px; flex-wrap: wrap; align-items: baseline;
  padding: 5px 10px; background: var(--panel); border-bottom: 1px solid var(--border);
  color: var(--muted); font-size: 11.5px; position: sticky; top: 0; z-index: 2; }
.tbl-legend b { color: var(--fg); font-weight: 600; font-family: var(--mono); }
.home table { border-collapse: collapse; width: 100%; font-size: 12.5px; }
.home th { text-align: left; color: var(--muted); font-weight: 600; padding: 3px 10px 3px 0;
  border-bottom: 1px solid var(--border); background: var(--bg); position: sticky; z-index: 1;
  white-space: nowrap; cursor: default; }
.home td { padding: 2px 10px 2px 0; vertical-align: top; border-bottom: 1px solid var(--border); }
.home td.n, .home th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.home td.c { font: 11.5px var(--mono); white-space: pre; overflow: hidden; text-overflow: ellipsis; max-width: 40ch; }
.rcol { position: relative; }
.rcol .rgrip { position: absolute; right: -4px; top: 0; bottom: 0; width: 8px; cursor: col-resize;
  z-index: 2; touch-action: none; }
.rcol .rgrip:hover, .rcol .rgrip.active { background: var(--accent); opacity: .35; }
.legend { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); font-size: 12px; }
.legend i { display: inline-block; width: 120px; height: 10px; border-radius: 2px;
  background: linear-gradient(90deg, hsla(55,100%,var(--heat-l),.12), hsla(35,100%,var(--heat-l),.55), hsla(0,100%,var(--heat-l),.9)); }
@media (max-width: 1440px) {
  #tree { width: 230px; }
  .home { padding: 12px 14px 32px; }
  #hdr { padding: 6px 10px; }
}
@media (max-width: 720px) {
  #layout { flex-direction: column; }
  #tree { width: auto !important; max-width: none; max-height: 38vh; resize: none;
    border-right: 0; border-bottom: 1px solid var(--border); }
  #hdr input { width: 120px; }
}
</style>
"""

BODY = """<div id="hdr">
  <h1><a id="homelink">__TITLE__</a></h1>
  <span class="meta" id="hmeta"></span>
  <label>event <select id="event"></select></label>
  <label>find <input id="q" type="search" placeholder="file name…"></label>
  <label>scale <select id="scale">
    <option value="global">log, global</option>
    <option value="file">log, per file</option>
    <option value="linear">linear, global</option>
  </select></label>
  <label>tree <select id="sort"><option value="heat">by heat</option><option value="name">by name</option></select></label>
  <span class="legend">cold <i></i> hot</span>
</div>
<div id="layout">
  <nav id="tree"></nav>
  <section id="main"></section>
</div>
<script id="heatdata" type="application/json">__DATA__</script>
<script>
(function () {
"use strict";
const D = JSON.parse(document.getElementById("heatdata").textContent);
const files = D.files, fns = D.functions;
const treeEl = document.getElementById("tree"), mainEl = document.getElementById("main");
let scale = "global", sortMode = "heat", curFile = null, query = "";
try { scale = localStorage.getItem("heat.scale") || scale; sortMode = localStorage.getItem("heat.sort") || sortMode; } catch (e) {}
document.getElementById("scale").value = scale;
document.getElementById("sort").value = sortMode;

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
let ev = null;
try { ev = evByKey(localStorage.getItem("heat.event")); } catch (e) {}
ev = ev || evByKey(D.meta.defaultEvent) || EVS[0];
const EXTRA = ["D1m", "DLm", "Bcm"].map(evByKey).filter(Boolean);
const evSel = document.getElementById("event");
for (const e of EVS) { const o = document.createElement("option"); o.value = e.key; o.textContent = e.key + (e.long ? " — " + e.long : ""); evSel.appendChild(o); }
evSel.value = ev.key;
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
const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const pct = v => 100 * v / TOTAL;
const fmtP = p => p >= 10 ? p.toFixed(1) + "%" : p >= 0.01 ? p.toFixed(2) + "%" : p > 0 ? "<0.01%" : "";
const fmtPct = v => fmtP(pct(v));
const fmtN = v => v.toLocaleString("en-US");
const fmtCount = v => v.toLocaleString("en-US") + "\\u00d7";
const PMIN = 0.001; // lines below 0.001% of total stay uncolored in log mode
function heatP(p, maxP) {
  if (p <= 0) return 0;
  if (scale === "linear") return Math.min(1, p / maxP);
  if (p < PMIN) return 0;
  return Math.min(1, Math.log10(p / PMIN) / Math.log10(Math.max(maxP, PMIN * 10) / PMIN));
}
function heatT(cost, maxP) { return heatP(pct(cost), maxP); }
function heatBg(t) {
  if (t <= 0) return "";
  const hue = 55 - 55 * t, a = 0.10 + 0.80 * t;
  return `background:hsla(${hue.toFixed(0)},100%,var(--heat-l),${a.toFixed(2)})`;
}
function heatBgSoft(t) { // tree rows: keep names readable
  if (t <= 0) return "";
  const hue = 55 - 55 * t, a = 0.07 + 0.40 * t;
  return `background:hsla(${hue.toFixed(0)},100%,var(--heat-l),${a.toFixed(2)})`;
}
function hashFor(path, line) { return "#f=" + encodeURIComponent(path) + (line ? "&l=" + line : ""); }
function fnName(i) { return (i != null && fns[i]) ? fns[i].name : "?"; }

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
      const open = query ? true : openDirs.has(d.path);
      out.push(`<div class="node dir" data-dir="${esc(d.path)}" style="padding-left:${6 + depth * 14}px;${heatBgSoft(heatT(d.self, MAXPDIR))}"><span class="caret">${open ? "\\u25BC" : "\\u25B6"}</span><span class="name" title="${esc(d.path)}">${esc(d.name)}/</span><span class="pct">${fmtPct(d.self)}</span></div>`);
      out.push(`<div class="kids${open ? " open" : ""}">`);
      rec(d, depth + 1);
      out.push(`</div>`);
    }
    const fl = n.files.filter(f => matches(f.path)).sort(cmp);
    const fileRow = f => {
      const sel = f.path === curFile ? " sel" : "";
      out.push(`<div class="node file${f.cold ? " cold" : ""}${sel}" data-file="${esc(f.path)}" style="padding-left:${6 + depth * 14}px;${f.cold ? "" : heatBgSoft(heatT(f.self, MAXPDIR))}"><span class="caret">\\u25B6</span><span class="name" title="${esc(f.path)}${f.cold ? " (no samples; source not embedded)" : ""}">${esc(f.name)}</span><span class="pct">${fmtPct(f.self)}</span></div>`);
    };
    const zero = fl.filter(f => f.zero);
    for (const f of fl) if (!f.zero) fileRow(f);
    if (zero.length) {
      const show = query ? true : coldOpen.has(n.path);
      out.push(`<div class="node more" data-more="${esc(n.path)}" style="padding-left:${6 + depth * 14}px"><span class="caret">${show ? "\\u25BC" : "\\u25B6"}</span><span class="name">${zero.length} file${zero.length > 1 ? "s" : ""} without ${esc(ev.key)}</span><span class="pct"></span></div>`);
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
function rth(label, cls, title) {
  return `<th class="rcol${cls ? " " + cls : ""}"${title ? ` title="${title}"` : ""}>${label}</th>`;
}
function extraCells(vec, hot) {
  let h = "";
  for (const x of EXTRA) {
    const s = x.get(vec), m = MAXPX[x.key], p = 100 * s / m.total, t = heatP(p, m.maxP);
    h += `<td class="x${t > 0.45 ? " hot" : ""}" style="${heatBg(t)}" title="${esc(x.key)}: ${fmtN(s)}">${s ? fmtP(p) : ""}</td>`;
  }
  return h;
}
// Column abbreviations used across the tables, spelled out once so a legend
// banner can show them without requiring a hover.
const GLOSS = {
  "#": "rank", self: "self cost (time attributed to this line/function alone)",
  incl: "inclusive cost (self + everything it calls)",
  calls: "how many times this was called, or the inclusive cost of calls made from a line",
  location: "file:line", "defined at": "file:line where the function starts",
  tree: "directory or file", source: "source line, trimmed",
};
function legendBar(keys, extraStyle) {
  const seen = new Set();
  const parts = [];
  for (const k of keys) {
    const isEvent = k && typeof k === "object";
    const label = isEvent ? k.key : k;
    if (seen.has(label)) continue;
    seen.add(label);
    const desc = isEvent ? (k.long || "") : (GLOSS[label] || "");
    if (!desc || desc === label) continue;
    parts.push(`<span><b>${esc(label)}</b> ${esc(desc)}</span>`);
  }
  if (!parts.length) return "";
  const style = extraStyle ? ` style="${extraStyle}"` : "";
  return `<div class="tbl-legend"${style}>${parts.join("")}</div>`;
}
// Wrap a <table>...</table> string with a sticky-header scroll box and,
// optionally, a plain-language legend banner above it.
function wrapTable(tableHtml, legendKeys) {
  const legend = legendKeys ? legendBar(legendKeys) : "";
  return `<div class="tbl-wrap">${legend}${tableHtml}</div>`;
}
// Drag-to-resize for <th class="rcol"> columns: each such header gets a
// grip on its right edge; dragging sets an explicit width on that <th> (and
// its table switches to a fixed layout so the width sticks).
// A sticky legend banner and a sticky <th> row can both be direct/nested
// children of the same scrolling .tbl-wrap; the header's sticky offset must
// equal the legend's rendered height (0 when there is no legend) or the two
// overlap instead of stacking.
function alignStickyHeaders(root) {
  for (const wrap of root.querySelectorAll(".tbl-wrap")) {
    const legend = wrap.querySelector(":scope > .tbl-legend");
    const offset = legend ? legend.getBoundingClientRect().height : 0;
    for (const th of wrap.querySelectorAll("th")) th.style.top = offset + "px";
  }
}
function initResizableColumns(root) {
  alignStickyHeaders(root);
  for (const th of root.querySelectorAll(".rcol")) {
    if (th.querySelector(".rgrip")) continue;
    const grip = document.createElement("span");
    grip.className = "rgrip";
    th.appendChild(grip);
  }
  root.querySelectorAll(".rcol .rgrip").forEach(grip => {
    grip.addEventListener("pointerdown", e => {
      const th = grip.parentElement, table = th.closest("table");
      const startX = e.clientX, startW = th.getBoundingClientRect().width;
      table.style.tableLayout = "fixed";
      if (grip.setPointerCapture) grip.setPointerCapture(e.pointerId);
      grip.classList.add("active");
      const onMove = e2 => { th.style.width = Math.max(32, startW + (e2.clientX - startX)) + "px"; };
      const onUp = () => {
        grip.classList.remove("active");
        grip.removeEventListener("pointermove", onMove);
        grip.removeEventListener("pointerup", onUp);
      };
      grip.addEventListener("pointermove", onMove);
      grip.addEventListener("pointerup", onUp);
      e.preventDefault();
    });
  });
}
function renderHome() {
  curFile = null;
  const groups = [...TREE.dirs.values()].sort((a, b) => b.self - a.self);
  let h = `<div class="home">`;
  h += `<p><b>${esc(ev.key)}</b> = ${esc(ev.long || ev.key)}. Every percentage is the share of the <b>${fmtN(TOTAL)}</b> total for that event. Click a file in the tree, or a line below. In a listing, click a line number to see every event for that line, what it calls (and, on a function's first line, who calls it). Pick another event in the header to re-color everything by cache misses or branch mispredicts.</p>`;
  h += `<h2>Callgrind totals</h2><pre>${esc(D.meta.stats)}</pre>`;
  let t1 = `<table><tr>${rth("tree")}${rth("self", "n")}<th class="n">${esc(ev.key)}</th></tr>`;
  for (const g of groups) t1 += `<tr><td>${esc(g.name)}/</td><td class="n" style="${heatBg(heatT(g.self, 100))}">${fmtPct(g.self)}</td><td class="n">${fmtN(g.self)}</td></tr>`;
  t1 += `</table>`;
  h += `<h2>Where ${esc(ev.key)} goes</h2>` + wrapTable(t1, ["tree", "self", ev]);
  const xh = EXTRA.map(x => rth(esc(x.key), "n", esc(x.long))).join("");
  let t2 = `<table><tr>${rth("#", "n")}${rth("self", "n")}${rth(esc(ev.key), "n")}${xh}${rth("location")}${rth("function")}<th>source</th></tr>`;
  topLines(60).forEach((t, i) => {
    const [path, ln, cost, fnidx, snip] = t;
    const rec = files[path].lines[ln];
    t2 += `<tr><td class="n">${i + 1}</td><td class="n" style="${heatBg(heatT(cost, MAXP))}">${fmtPct(cost)}</td><td class="n">${fmtN(cost)}</td>${extraCells(rec[0]).replace(/<td class="x/g, '<td class="n x')}<td><a href="${hashFor(path, ln)}">${esc(path)}:${ln}</a></td><td>${esc(fnName(fnidx))}</td><td class="c">${esc(snip)}</td></tr>`;
  });
  t2 += `</table>`;
  h += `<h2>Hottest lines by ${esc(ev.key)}</h2>` + wrapTable(t2, ["#", "self", ev, ...EXTRA, "location", "function", "source"]);
  const topF = fns.map((f, i) => [i, val(f.self)]).filter(t => t[1] > 0).sort((a, b) => b[1] - a[1]).slice(0, 60);
  let t3 = `<table><tr>${rth("#", "n")}${rth("self", "n")}${rth("incl", "n")}${xh}${rth("calls", "n")}${rth("function")}<th>defined at</th></tr>`;
  topF.forEach(([fi, s], i) => {
    const f = fns[fi];
    const loc = f.line ? `<a href="${hashFor(f.file, f.line)}">${esc(f.file)}:${f.line}</a>` : esc(f.file);
    const ncalls = f.callers.reduce((a, c) => a + c[4], 0);
    t3 += `<tr><td class="n">${i + 1}</td><td class="n" style="${heatBg(heatT(s, MAXP))}">${fmtPct(s)}</td><td class="n">${fmtPct(s + val(f.calls))}</td>${extraCells(f.self).replace(/<td class="x/g, '<td class="n x')}<td class="n">${ncalls ? fmtCount(ncalls) : ""}</td><td>${esc(f.name)}</td><td>${loc}</td></tr>`;
  });
  t3 += `</table>`;
  h += `<h2>Hottest functions by self ${esc(ev.key)}</h2>` + wrapTable(t3, ["#", "self", "incl", ...EXTRA, "calls", "function", "defined at"]);
  h += `</div>`;
  mainEl.innerHTML = h;
  mainEl.scrollTop = 0;
  renderTree();
  initResizableColumns(mainEl);
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
  let h = `<div class="fhead"><span class="path">${esc(path)}</span>`;
  h += `<span class="stat">self <b>${fmtPct(val(f.self)) || "0%"}</b> (${fmtN(val(f.self))} ${esc(ev.key)})</span>`;
  for (const x of EXTRA) { const s = x.get(f.self); if (s) h += `<span class="stat" title="${esc(x.long)}">${esc(x.key)} <b>${fmtP(100 * s / MAXPX[x.key].total)}</b> (${fmtN(s)})</span>`; }
  if (f.group === "external") h += `<span class="stat">not in this repo (${esc(f.raw)})</span>`;
  h += `</div>`;
  h += legendBar(["self", "incl", ev, ...EXTRA], "position:sticky;top:0;z-index:2;border-top:1px solid var(--border)");
  const hot = Object.keys(lines).map(k => [+k, val(lines[k][0])]).filter(t => t[1] > 0).sort((a, b) => b[1] - a[1]).slice(0, 12);
  if (hot.length) {
    h += `<div class="chips"><span class="lbl">hottest lines</span>`;
    for (const [ln, cost] of hot) h += `<span class="chip" data-goto="${ln}" style="${heatBg(heatT(cost, maxP))}">${ln} · ${fmtPct(cost)}</span>`;
    h += `</div>`;
  }
  if (f.src == null) {
    h += `<div class="nosrc">Source not available on this machine; showing only the lines that carry cost.</div>`;
  }
  const rows = [];
  const emitRow = (ln, text) => {
    const rec = lines[ln];
    const self = rec ? val(rec[0]) : 0, calls = rec ? val(rec[1]) : 0;
    const t = heatT(self, maxP);
    const hasc = f.callees[ln] ? " hasc" : "";
    const fnidx = f.lfn[ln];
    const title = rec ? `${fmtN(self)} ${ev.key} self, ${fmtN(calls)} in calls${rec[2] ? " (" + fmtCount(rec[2]) + ")" : ""}${fnidx != null ? " — in " + fnName(fnidx) : ""}` : "";
    rows.push(`<tr id="L${ln}" class="${hasc}${line === ln ? " target" : ""}" style="${heatBg(t)}"${title ? ` title="${esc(title)}"` : ""}><td class="ln" data-ln="${ln}">${ln}</td><td class="self${t > 0.45 ? " hot" : ""}">${self ? fmtPct(self) : ""}</td><td class="incl">${calls ? fmtPct(calls) : ""}</td>${rec ? extraCells(rec[0]) : EXTRA.map(() => `<td class="x"></td>`).join("")}<td class="code">${text == null ? "" : esc(text)}</td></tr>`);
  };
  const xh = EXTRA.map(x => `<td class="x rcol" title="${esc(x.long)} (share of that event's total)">${esc(x.key)}</td>`).join("");
  h += `<table class="src"><tr class="th"><td class="ln rcol">line</td><td class="self rcol">${esc(ev.key)}</td><td class="incl rcol" title="inclusive cost of the calls made from this line">calls</td>${xh}<td class="code"></td></tr>`;
  if (f.src != null) {
    const srcl = f.src.split("\\n");
    if (srcl.length && srcl[srcl.length - 1] === "") srcl.pop();
    for (let i = 0; i < srcl.length; i++) emitRow(i + 1, srcl[i]);
    for (const k of Object.keys(lines)) if (+k > srcl.length) emitRow(+k, "(line beyond end of file: source changed since the profile was taken)");
  } else {
    for (const k of Object.keys(lines).map(Number).sort((a, b) => a - b)) emitRow(k, null);
  }
  h += rows.join("") + `</table>`;
  mainEl.innerHTML = h;
  renderTree();
  initResizableColumns(mainEl);
  if (line) {
    const el = document.getElementById("L" + line);
    if (el) { el.scrollIntoView({ block: "center" }); toggleDetail(path, line, true); }
  } else if (first) mainEl.scrollTop = 0;
}

function eventTable(selfv, callsv) {
  let h = `<table><tr><td class="m">event</td><td class="n m">self</td><td class="n m">% of total</td><td class="n m">in calls</td><td class="m"></td></tr>`;
  for (const e of EVS) {
    const s = e.get(selfv), c = e.get(callsv), tot = e.get(D.meta.totals) || 1;
    if (!s && !c) continue;
    h += `<tr><td${e === ev ? ' style="font-weight:600"' : ""}>${esc(e.key)}</td><td class="n">${fmtN(s)}</td><td class="n">${fmtP(100 * s / tot) || "0%"}</td><td class="n">${c ? fmtN(c) : ""}</td><td class="m">${esc(e.long)}</td></tr>`;
  }
  return h + `</table>`;
}

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
  let h = `<div class="dbox">`;
  h += `<div>line ${ln}${fnidx != null ? " in <b>" + esc(fnName(fnidx)) + "</b>" : ""}: self ${fmtN(val(rec[0]))} ${esc(ev.key)} (${fmtPct(val(rec[0])) || "0%"})${val(rec[1]) ? `, calls ${fmtN(val(rec[1]))} (${fmtPct(val(rec[1]))}) over ${fmtCount(rec[2])}` : ""}</div>`;
  h += `<h4>all events on this line</h4>` + eventTable(rec[0], rec[1]);
  if (callees.length) {
    h += `<h4>calls from this line (inclusive ${esc(ev.key)})</h4><table><tr><td class="n m">% of total</td><td class="n m">${esc(ev.key)}</td><td class="n m">call count</td><td class="m">callee</td><td class="m">defined at</td></tr>`;
    for (const [ci, cf, cl, vec, count] of callees) {
      const loc = files[cf] && cl ? `<a href="${hashFor(cf, cl)}">${esc(cf)}:${cl}</a>` : esc(cf);
      h += `<tr><td class="n">${fmtPct(val(vec))}</td><td class="n">${fmtN(val(vec))}</td><td class="n">${fmtCount(count)}</td><td>${esc(fnName(ci))}</td><td>${loc}</td></tr>`;
    }
    h += `</table>`;
  }
  if (fi != null) {
    const fn = fns[fi];
    const callers = fn.callers.slice().sort((a, b) => b[4] - a[4]);
    h += `<h4>${esc(fn.name)} is entered here — self ${fmtPct(val(fn.self)) || "0%"}, inclusive ${fmtPct(val(fn.self) + val(fn.calls)) || "0%"}. Called from (by call count):</h4><table><tr><td class="n m">call count</td><td class="n m">% of total</td><td class="n m">${esc(ev.key)}</td><td class="m">caller</td><td class="m">defined at</td></tr>`;
    for (const [ci, cf, cl, vec, count] of callers) {
      const loc = files[cf] && cl ? `<a href="${hashFor(cf, cl)}">${esc(cf)}:${cl}</a>` : esc(cf);
      h += `<tr><td class="n">${fmtCount(count)}</td><td class="n">${fmtPct(val(vec))}</td><td class="n">${fmtN(val(vec))}</td><td>${esc(fnName(ci))}</td><td>${loc}</td></tr>`;
    }
    if (!fn.callers.length) h += `<tr><td>(no recorded caller — a root or a resolver stub)</td></tr>`;
    h += `</table>`;
  }
  if (!callees.length && fi == null) h += `<div style="color:var(--muted)">no calls recorded from this line</div>`;
  h += `</div>`;
  const tr = document.createElement("tr");
  tr.className = "detail";
  tr.innerHTML = `<td colspan="${4 + EXTRA.length}">${h}</td>`;
  row.after(tr);
}

mainEl.addEventListener("click", ev2 => {
  const chip = ev2.target.closest(".chip");
  if (chip) { location.hash = hashFor(curFile, +chip.dataset.goto); return; }
  const ln = ev2.target.closest("td.ln");
  if (ln && curFile) { toggleDetail(curFile, +ln.dataset.ln, false); return; }
});

// ---------- routing ----------
function route() {
  const m = /^#f=([^&]*)(?:&l=(\\d+))?/.exec(location.hash);
  if (m) renderFile(decodeURIComponent(m[1]), m[2] ? +m[2] : 0);
  else renderHome();
}
function setEvent(key) {
  ev = evByKey(key) || EVS[0];
  try { localStorage.setItem("heat.event", ev.key); } catch (e) {}
  recomputeScale();
  TREE = buildTree();
  for (const d of TREE.dirs.values()) if (d.self / TOTAL > 0.05) openDirs.add(d.path);
  document.getElementById("hmeta").textContent = `${D.meta.cmd || ""} · ${fmtN(TOTAL)} ${ev.key} · ${D.meta.source} · ${D.meta.generated}`;
  route();
}
window.addEventListener("hashchange", route);
let resizeT = null;
window.addEventListener("resize", () => {
  clearTimeout(resizeT);
  resizeT = setTimeout(() => alignStickyHeaders(mainEl), 120);
});
document.getElementById("homelink").addEventListener("click", () => { location.hash = ""; });
evSel.addEventListener("change", e => setEvent(e.target.value));
document.getElementById("scale").addEventListener("change", e => { scale = e.target.value; try { localStorage.setItem("heat.scale", scale); } catch (x) {} route(); });
document.getElementById("sort").addEventListener("change", e => { sortMode = e.target.value; try { localStorage.setItem("heat.sort", sortMode); } catch (x) {} renderTree(); });
document.getElementById("q").addEventListener("input", e => { query = e.target.value.trim().toLowerCase(); renderTree(); });
setEvent(ev.key);
})();
</script>
"""


def render_html(model: dict, title: str, bare: bool) -> str:
    data = json.dumps(model, separators=(",", ":"), ensure_ascii=False)
    data = data.replace("</", "<\\/")  # never close our own <script>
    head = HEAD.replace("__TITLE__", title)
    body = BODY.replace("__TITLE__", title).replace("__DATA__", data)
    if bare:
        return head + body
    return "<!doctype html>\n<html lang=\"en\">\n<head>\n" + head + "</head>\n<body>\n" + body + "</body>\n</html>\n"


# --------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("callgrind_file")
    ap.add_argument("-o", "--output", required=True, help="output .html path (directories are created)")
    ap.add_argument("--event", default="Ir", help="event selected when the page opens (default: Ir)")
    ap.add_argument("--repo-root", default=".", help="repository root the profile's paths are relative to")
    ap.add_argument("--tree", nargs="*", default=["lib", "include", "src", "tests/perf"],
                    help="directories whose tracked .c/.h files are listed in the tree even without samples")
    ap.add_argument("--all-sources", action="store_true",
                    help="embed the source of every tracked file in --tree, not just files with samples")
    ap.add_argument("--title", default=None)
    ap.add_argument("--bare", action="store_true",
                    help="emit only <title>/<style>/body markup, no <!doctype>/<html>/<head>/<body> wrapper")
    args = ap.parse_args()

    with open(args.callgrind_file, encoding="utf-8", errors="replace") as f:
        text = f.read()
    prof = cg.parse_callgrind(text)
    if not prof.events:
        sys.exit("error: no 'events:' line -- not a callgrind file?")
    if args.title is None:
        args.title = f"heatmap: {prof.cmd or os.path.basename(args.callgrind_file)}"

    self_sum, total, ratio = cg.self_check(prof)
    print(f"events: {' '.join(prof.events)}", file=sys.stderr)
    print(f"callgrind summary ({prof.events[0]}): {total:,}", file=sys.stderr)
    print(f"sum of self-cost lines:          {self_sum:,}", file=sys.stderr)
    print(f"ratio (must be 1.0000):          {ratio:.4f}", file=sys.stderr)
    if total and abs(ratio - 1.0) > 1e-6:
        print("error: per-line self cost does not add up to callgrind's summary; refusing to write", file=sys.stderr)
        sys.exit(2)

    model = build_model(prof, args, os.path.basename(args.callgrind_file))
    html = render_html(model, args.title, args.bare)
    out_dir = os.path.dirname(os.path.abspath(args.output))
    os.makedirs(out_dir, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)
    nsrc = sum(1 for e in model["files"].values() if e["src"] is not None)
    print(f"files with samples: {len(model['files'])} ({nsrc} with source embedded), "
          f"cold files listed: {len(model['cold'])}, functions: {len(model['functions'])}", file=sys.stderr)
    print(f"wrote {args.output} ({len(html.encode('utf-8')):,} bytes)", file=sys.stderr)


if __name__ == "__main__":
    main()
