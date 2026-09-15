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
and must be 1.0000. Colors, fonts and table behaviour come from theme.py.

Usage:
  callgrind_to_heatmap.py callgrind.out.X -o report/heat-map/index.html \
      [--event Ir] [--repo-root .] [--tree lib include src tests/perf] \
      [--all-sources] [--title "..."]
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
import theme  # noqa: E402


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
            "totalsRows": cg.totals_rows(p),
            "cmd": p.cmd,
            "source": src_name,
            "generated": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "repoRoot": repo_root,
            "allSources": bool(args.all_sources),
        },
        "theme": theme.runtime(),
        "files": files,
        "functions": functions,
        "cold": sorted(cold),
    }


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------

CSS = """\
body { display: flex; flex-direction: column; height: 100vh; }
#hdr { display: flex; gap: 4px 14px; align-items: center; flex-wrap: wrap; flex: none;
  padding: 5px 14px; background: var(--nav); border-bottom: 1px solid var(--bar); }
#hdr h1 { font-size: 13px; margin: 0; white-space: nowrap; }
#hdr h1 a { color: var(--accent); }
#hdr .meta, #hdr label { color: var(--muted); white-space: nowrap; }
#hdr input { width: 18ch; }
.legend { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); }
.legend i { display: inline-block; width: 96px; height: 10px; border-radius: 2px; background: var(--heat); }
#layout { display: flex; flex: 1; min-height: 0; }
#tree { width: 280px; min-width: 120px; flex: none; overflow: auto; padding: 4px 0 24px; }
#main { flex: 1; min-width: 0; overflow: auto; }
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
.fhead { background: var(--panel); border-bottom: 1px solid var(--bar); padding: 5px 14px;
  display: flex; gap: 4px 18px; align-items: baseline; flex-wrap: wrap; }
.fhead .path { font-weight: 600; }
.fhead .stat { color: var(--muted); }
.chips { display: flex; gap: 4px; flex-wrap: wrap; padding: 5px 14px; border-bottom: 1px solid var(--bar); }
.chips .lbl { color: var(--muted); align-self: center; margin-right: 4px; }
.chip { padding: 0 7px; border-radius: 10px; border: 1px solid var(--bar); cursor: pointer; }
.chip:hover { outline: 1px solid var(--link); }
.nosrc { padding: 8px 14px; color: var(--muted); }
table.src td { padding-top: 0; padding-bottom: 0; }
table.src td.ln { color: var(--muted); user-select: none; cursor: pointer; }
table.src td.ln:hover { color: var(--link); }
table.src td.self, table.src td.incl, table.src td.x { color: var(--muted); }
table.src tr.heat td { color: inherit; }
table.src td.hot { font-weight: 600; }
table.src td.code { overflow: visible; text-overflow: clip; white-space: pre; tab-size: 4; }
table.src tr.hasc td.ln::before { content: "\\25B8 "; color: var(--link); }
table.src tr.target td { box-shadow: inset 0 0 0 2px var(--accent); }
table.src tr.detail td { white-space: normal; overflow: visible; padding: 0; }
.dbox { margin: 3px 12px 8px; padding: 6px 12px; background: var(--panel); border: 1px solid var(--bar); border-radius: 4px; }
.dbox h4 { margin: 6px 0 2px; font-size: 12px; color: var(--muted); font-weight: 600; }
.dbox .tbl { max-height: 40vh; background: var(--bg); }
.home { padding: 12px 14px 40px; }
.home h2:first-of-type { margin-top: 10px; }
@media (max-width: 720px) {
  #layout { flex-direction: column; }
  #tree { width: auto !important; max-height: 38vh; border-bottom: 1px solid var(--bar); }
  .split { display: none; }
  #hdr input { width: 12ch; }
}
"""

BODY = """<div id="hdr">
  <h1><a id="homelink" href="#">__TITLE__</a></h1>
  <span class="meta" id="hmeta"></span>
  <label>event <select id="event"></select></label>
  <label>find <input id="q" type="search" placeholder="file name\u2026"></label>
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
  <div id="split" class="split" title="drag to resize, double-click to reset"></div>
  <section id="main"></section>
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
const evSel = document.getElementById("event");
for (const e of EVS) { const o = document.createElement("option"); o.value = e.key; o.textContent = e.key + (e.long ? " \\u2014 " + e.long : ""); evSel.appendChild(o); }
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
const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
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
function hashFor(path, line) { return "#f=" + encodeURIComponent(path) + (line ? "&l=" + line : ""); }
function fnName(i) { return (i != null && fns[i]) ? fns[i].name : "?"; }
function link(path, line, text) { return files[path] && line ? `<a href="${hashFor(path, line)}">${esc(text)}</a>` : esc(text); }
const SYMBOL_CHARS = 20; // visible characters of a function name before it is cut off

// A .tbl box: legend banner from the columns' titles, then a fixed-layout
// table with widths in characters (everything is monospace). Mirrors
// theme.table() in theme.py. cols: {label, title, num, width, clip, cls};
// cells: a string, or {text, html, style, cls, title}.
const PAD = 3; // 1ch padding each side + 1ch slack for the divider bar and ch rounding
function table(key, cols, rows, opts) {
  opts = opts || {};
  const cell = c => (c && typeof c === "object") ? c : { text: c == null ? "" : String(c) };
  const rc = rows.map(r => r.map(cell));
  const widths = cols.map((col, i) => {
    if (col.width != null) return col.width + PAD;
    let n = col.label.length;
    for (const r of rc) if (r[i]) n = Math.max(n, (r[i].text || "").length);
    if (col.clip != null) n = Math.min(n, col.clip);
    return n + PAD;
  });
  let h = `<div class="tbl">`;
  const leg = cols.filter(c => c.title).map(c => `<span><b>${esc(c.label)}</b> ${esc(c.title)}</span>`);
  if (leg.length && !opts.noLegend) h += `<div class="tbl-legend band">${leg.join("")}</div>`;
  h += `<div class="tbl-cols"><table class="cols${opts.fill ? " fill" : ""}" data-key="${esc(key)}"><colgroup>`;
  cols.forEach((c, i) => { h += `<col${i % 2 ? ' class="alt"' : ""}${(opts.fill && i === cols.length - 1) ? "" : ` style="width:${widths[i]}ch"`}>`; });
  h += `</colgroup><thead><tr>`;
  for (const c of cols) h += `<th${c.num ? ' class="n"' : ""}${c.title ? ` title="${esc(c.title)}"` : ""}>${esc(c.label)}</th>`;
  h += `</tr></thead><tbody>`;
  for (const r of rc) {
    h += "<tr>";
    r.forEach((c, i) => {
      const col = cols[i] || {};
      const cls = [col.num ? "n" : "", col.cls || "", c.cls || ""].filter(Boolean).join(" ");
      const text = c.text || "", title = c.title || ((text.length + PAD > widths[i]) ? text : "");
      h += `<td${cls ? ` class="${cls}"` : ""}${c.style ? ` style="${c.style}"` : ""}${title ? ` title="${esc(title)}"` : ""}>${c.html != null ? c.html : esc(text)}</td>`;
    });
    h += "</tr>";
  }
  return h + `</tbody></table></div></div>`;
}
const evCol = (e, extra) => Object.assign({ label: e.key, title: e.long, num: true }, extra || {});
const extraCols = () => EXTRA.map(x => evCol(x, { title: x.long + " (share of that event's total)", cls: "x" }));
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
const SELF = { label: "self", title: "share of the total spent on this line/function itself, not in what it calls", num: true };
function renderHome() {
  curFile = null;
  const groups = [...TREE.dirs.values()].sort((a, b) => b.self - a.self);
  let h = `<div class="home">`;
  h += `<p><b>${esc(ev.key)}</b> = ${esc(ev.long || ev.key)}. Every percentage is the share of the <b>${fmtN(TOTAL)}</b> total for that event. Click a file in the tree, or a line below. In a listing, click a line number to see every event for that line, what it calls (and, on a function's first line, who calls it). Pick another event in the header to re-color everything by cache misses or branch mispredicts.</p>`;
  h += `<h2>Callgrind totals</h2>` + table("heat.totals",
    [{ label: "group", title: "I instruction cache, D data cache, LL last-level cache; events: every total; simulation: cache geometry used" },
     { label: "metric" }, { label: "value", num: true }, { label: "detail", clip: 72 }],
    D.meta.totalsRows.map(r => [{ text: r[0], cls: "dim" }, r[1], r[2], { text: r[3], cls: "dim" }]));
  h += `<h2>Where ${esc(ev.key)} goes</h2>` + table("heat.home.tree",
    [{ label: "tree", title: "top-level directory of the source tree" }, SELF, evCol(ev)],
    groups.map(g => [g.name + "/", { text: fmtPct(g.self), style: heatBg(heatT(g.self, 100)) }, fmtN(g.self)]));
  h += `<h2>Hottest lines by ${esc(ev.key)}</h2>` + table("heat.home.lines",
    [{ label: "#", title: "rank", num: true }, SELF, evCol(ev), ...extraCols(),
     { label: "location", title: "file:line; opens the listing there", clip: 28 },
     { label: "function", title: `the function the line belongs to (first ${SYMBOL_CHARS} characters; drag the bar for more)`, width: SYMBOL_CHARS },
     { label: "source", title: "the source line, trimmed; drag the bar for more", clip: 36 }],
    topLines(60).map((t, i) => {
      const [path, ln, cost, fnidx, snip] = t, rec = files[path].lines[ln];
      return [String(i + 1), { text: fmtPct(cost), style: heatBg(heatT(cost, MAXP)) }, fmtN(cost), ...extraCells(rec[0]),
              { text: path + ":" + ln, html: link(path, ln, path + ":" + ln) }, { text: fnName(fnidx), title: fnName(fnidx) }, snip];
    }));
  const topF = fns.map((f, i) => [i, val(f.self)]).filter(t => t[1] > 0).sort((a, b) => b[1] - a[1]).slice(0, 60);
  h += `<h2>Hottest functions by self ${esc(ev.key)}</h2>` + table("heat.home.functions",
    [{ label: "#", title: "rank", num: true }, SELF, { label: "incl", title: "inclusive: self plus everything it calls", num: true },
     ...extraCols(), { label: "calls", title: "times the function was entered", num: true },
     { label: "function", title: `first ${SYMBOL_CHARS} characters; drag the bar for more`, width: SYMBOL_CHARS },
     { label: "defined at", title: "file:line of the function's first executed line", clip: 48 }],
    topF.map(([fi, s], i) => {
      const f = fns[fi], loc = f.line ? f.file + ":" + f.line : f.file, ncalls = f.callers.reduce((a, c) => a + c[4], 0);
      return [String(i + 1), { text: fmtPct(s), style: heatBg(heatT(s, MAXP)) }, fmtPct(s + val(f.calls)), ...extraCells(f.self),
              ncalls ? fmtCount(ncalls) : "", { text: f.name, title: f.name }, { text: loc, html: link(f.file, f.line, loc) }];
    }));
  h += `</div>`;
  mainEl.innerHTML = h;
  mainEl.scrollTop = 0;
  renderTree();
  Theme.init(mainEl);
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
  let h = `<div class="fhead band"><span class="path">${esc(path)}</span>`;
  h += `<span class="stat">self <b>${fmtPct(val(f.self)) || "0%"}</b> (${fmtN(val(f.self))} ${esc(ev.key)})</span>`;
  for (const x of EXTRA) { const s = x.get(f.self); if (s) h += `<span class="stat" title="${esc(x.long)}">${esc(x.key)} <b>${fmtP(100 * s / MAXPX[x.key].total)}</b> (${fmtN(s)})</span>`; }
  if (f.group === "external") h += `<span class="stat">not in this repo (${esc(f.raw)})</span>`;
  h += `</div>`;
  const cols = [{ label: "line", num: true }, evCol(ev, { title: ev.long + ", share of total, spent on the line itself" }),
                { label: "calls", title: "inclusive cost of the calls made from the line, share of total", num: true },
                ...extraCols(), { label: "source" }];
  h += `<div class="tbl-legend band">${cols.filter(c => c.title).map(c => `<span><b>${esc(c.label)}</b> ${esc(c.title)}</span>`).join("")}</div>`;
  const hot = Object.keys(lines).map(k => [+k, val(lines[k][0])]).filter(t => t[1] > 0).sort((a, b) => b[1] - a[1]).slice(0, 12);
  if (hot.length) {
    h += `<div class="chips"><span class="lbl">hottest lines</span>`;
    for (const [ln, cost] of hot) h += `<span class="chip" data-goto="${ln}" style="${heatBg(heatT(cost, maxP))}">${ln} \\u00b7 ${fmtPct(cost)}</span>`;
    h += `</div>`;
  }
  if (f.src == null) {
    h += `<div class="nosrc">Source not available on this machine; showing only the lines that carry cost.</div>`;
  }
  const rows = [];
  const emitRow = (ln, text) => {
    const rec = lines[ln];
    const self = rec ? val(rec[0]) : 0, calls = rec ? val(rec[1]) : 0;
    const t = heatT(self, maxP), hs = heatBg(t);
    const fnidx = f.lfn[ln];
    const title = rec ? `${fmtN(self)} ${ev.key} self, ${fmtN(calls)} in calls${rec[2] ? " (" + fmtCount(rec[2]) + ")" : ""}${fnidx != null ? " \\u2014 in " + fnName(fnidx) : ""}` : "";
    const xs = rec ? extraCells(rec[0]).map(c => `<td class="n x${c.cls ? " " + c.cls : ""}" style="${c.style}" title="${esc(c.title)}">${esc(c.text)}</td>`).join("") : EXTRA.map(() => `<td class="n x"></td>`).join("");
    rows.push(`<tr id="L${ln}" class="${f.callees[ln] ? "hasc" : ""}${line === ln ? " target" : ""}${hs ? " heat" : ""}" style="${hs}"${title ? ` title="${esc(title)}"` : ""}><td class="n ln" data-ln="${ln}">${ln}</td><td class="n self${t > 0.45 ? " hot" : ""}">${self ? fmtPct(self) : ""}</td><td class="n incl">${calls ? fmtPct(calls) : ""}</td>${xs}<td class="code">${text == null ? "" : esc(text)}</td></tr>`);
  };
  let nlines = 0;
  if (f.src != null) {
    const srcl = f.src.split("\\n");
    if (srcl.length && srcl[srcl.length - 1] === "") srcl.pop();
    nlines = srcl.length;
    for (let i = 0; i < srcl.length; i++) emitRow(i + 1, srcl[i]);
    for (const k of Object.keys(lines)) if (+k > srcl.length) { nlines = Math.max(nlines, +k); emitRow(+k, "(line beyond end of file: source changed since the profile was taken)"); }
  } else {
    for (const k of Object.keys(lines).map(Number).sort((a, b) => a - b)) { nlines = k; emitRow(k, null); }
  }
  h += `<div class="tbl-cols"><table class="cols fill src" data-key="heat.src"><colgroup>`;
  cols.forEach((c, i) => {
    // line numbers carry a 2-character call marker; the cost columns hold "<0.01%"
    const w = (i === 0 ? String(nlines).length + 2 : 6) + PAD;
    h += `<col${i % 2 ? ' class="alt"' : ""}${i === cols.length - 1 ? "" : ` style="width:${w}ch"`}>`;
  });
  h += `</colgroup><thead><tr>${cols.map(c => `<th${c.num ? ' class="n"' : ""}${c.title ? ` title="${esc(c.title)}"` : ""}>${esc(c.label)}</th>`).join("")}</tr></thead><tbody>`;
  h += rows.join("") + `</tbody></table></div>`;
  mainEl.innerHTML = h;
  renderTree();
  Theme.init(mainEl);
  if (line) {
    const el = document.getElementById("L" + line);
    if (el) { el.scrollIntoView({ block: "center" }); toggleDetail(path, line, true); }
  } else if (first) mainEl.scrollTop = 0;
}

function eventTable(selfv, callsv) {
  const rows = [];
  for (const e of EVS) {
    const s = e.get(selfv), c = e.get(callsv), tot = e.get(D.meta.totals) || 1;
    if (!s && !c) continue;
    rows.push([{ text: e.key, style: e === ev ? "font-weight:600" : "" }, fmtN(s), fmtP(100 * s / tot) || "0%", c ? fmtN(c) : "", { text: e.long, cls: "dim" }]);
  }
  return table("heat.detail.events",
    [{ label: "event" }, { label: "self", num: true }, { label: "% of total", num: true },
     { label: "in calls", title: "inclusive cost of the calls made from this line", num: true }, { label: "meaning", clip: 60 }],
    rows, { noLegend: true });
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
  const fnCol = label => ({ label, title: `first ${SYMBOL_CHARS} characters; drag the bar for more`, width: SYMBOL_CHARS });
  const locCol = { label: "defined at", title: "file:line of the function's first executed line", clip: 48 };
  let h = `<div class="dbox">`;
  h += `<div>line ${ln}${fnidx != null ? " in <b>" + esc(fnName(fnidx)) + "</b>" : ""}: self ${fmtN(val(rec[0]))} ${esc(ev.key)} (${fmtPct(val(rec[0])) || "0%"})${val(rec[1]) ? `, calls ${fmtN(val(rec[1]))} (${fmtPct(val(rec[1]))}) over ${fmtCount(rec[2])}` : ""}</div>`;
  h += `<h4>all events on this line</h4>` + eventTable(rec[0], rec[1]);
  if (callees.length) {
    h += `<h4>calls from this line (inclusive ${esc(ev.key)})</h4>` + table("heat.detail.callees",
      [{ label: "% of total", num: true }, evCol(ev), { label: "call count", num: true }, fnCol("callee"), locCol],
      callees.map(([ci, cf, cl, vec, count]) => {
        const loc = cl ? cf + ":" + cl : cf;
        return [fmtPct(val(vec)), fmtN(val(vec)), fmtCount(count), { text: fnName(ci), title: fnName(ci) }, { text: loc, html: link(cf, cl, loc) }];
      }), { noLegend: true });
  }
  if (fi != null) {
    const fn = fns[fi];
    const callers = fn.callers.slice().sort((a, b) => b[4] - a[4]);
    h += `<h4>${esc(fn.name)} is entered here \\u2014 self ${fmtPct(val(fn.self)) || "0%"}, inclusive ${fmtPct(val(fn.self) + val(fn.calls)) || "0%"}. Called from (by call count):</h4>`;
    h += callers.length ? table("heat.detail.callers",
      [{ label: "call count", num: true }, { label: "% of total", num: true }, evCol(ev), fnCol("caller"), { label: "called at", title: "file:line of the call", clip: 48 }],
      callers.map(([ci, cf, cl, vec, count]) => {
        const loc = cl ? cf + ":" + cl : cf;
        return [fmtCount(count), fmtPct(val(vec)), fmtN(val(vec)), { text: fnName(ci), title: fnName(ci) }, { text: loc, html: link(cf, cl, loc) }];
      }), { noLegend: true }) : `<div class="dim">(no recorded caller \\u2014 a root or a resolver stub)</div>`;
  }
  if (!callees.length && fi == null) h += `<div class="dim">no calls recorded from this line</div>`;
  h += `</div>`;
  const tr = document.createElement("tr");
  tr.className = "detail";
  tr.innerHTML = `<td colspan="${4 + EXTRA.length}">${h}</td>`;
  row.after(tr);
  Theme.init(tr);
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
  store.set("heat.event", ev.key);
  recomputeScale();
  TREE = buildTree();
  for (const d of TREE.dirs.values()) if (d.self / TOTAL > 0.05) openDirs.add(d.path);
  document.getElementById("hmeta").textContent = `${D.meta.cmd || ""} \\u00b7 ${fmtN(TOTAL)} ${ev.key} \\u00b7 ${D.meta.source} \\u00b7 ${D.meta.generated}`;
  route();
}
window.addEventListener("hashchange", route);
document.getElementById("homelink").addEventListener("click", e => { e.preventDefault(); location.hash = ""; });
evSel.addEventListener("change", e => setEvent(e.target.value));
document.getElementById("scale").addEventListener("change", e => { scale = e.target.value; store.set("heat.scale", scale); route(); });
document.getElementById("sort").addEventListener("change", e => { sortMode = e.target.value; store.set("heat.sort", sortMode); renderTree(); });
document.getElementById("q").addEventListener("input", e => { query = e.target.value.trim().toLowerCase(); renderTree(); });
setEvent(ev.key);
})();
</script>
"""


def render_html(model: dict, title: str) -> str:
    data = json.dumps(model, separators=(",", ":"), ensure_ascii=False)
    data = data.replace("</", "<\\/")  # never close our own <script>
    body = BODY.replace("__TITLE__", theme.esc(title)).replace("__THEME_JS__", theme.js()).replace("__DATA__", data)
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{theme.esc(title)}</title>\n<style>\n{theme.css()}{CSS}</style>\n</head>\n<body>\n"
            + body + "</body>\n</html>\n")


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
    html = render_html(model, args.title)
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
