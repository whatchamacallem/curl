#!/usr/bin/env python3
"""Turn a callgrind profile into a self-contained "source heatmap" web page.

The page is a file explorer over the profiled source tree: directories and
files are colored/sorted by how many instructions (or whatever event you pick)
were executed inside them, and each file opens as a source listing with every
line colored by its self cost. Call sites expand to show what they call (with
inclusive cost) and function entry lines show who calls them, so you can click
down or up the call graph across files. Everything is embedded in one HTML
file (no server, no CDN), so it can be opened from file:// or mailed around.

Per-line attribution mirrors callgrind_annotate exactly:
  * cost lines are charged to the *current* file, which `fl=` sets for a
    function and `fi=`/`fe=` switch for inlined code, and to the current
    line, decoded from callgrind's absolute/`+n`/`-n`/`*` subpositions;
  * the cost line that follows a `calls=` record is the *inclusive* cost of
    that call, charged to the call-site line separately (never as self cost);
  * `calls=` target positions are decoded relative to the last cost line but
    do not advance it.

A self-check ratio (sum of self-cost lines / callgrind's own summary) is
printed to stderr on every run and must be 1.0000.

Usage:
  callgrind_to_heatmap.py callgrind.out.X -o ~/Downloads/curlheat/index.html \
      [--event Ir] [--repo-root .] [--tree lib include src tests/perf] \
      [--all-sources] [--title "..."] [--bare]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import posixpath
import re
import subprocess
import sys
from collections import defaultdict

# --------------------------------------------------------------------------
# Callgrind parsing
# --------------------------------------------------------------------------

_NAME_RE = re.compile(r"^\((\d+)\)(?: (.*))?$")


class Profile:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.positions: list[str] = ["line"]
        self.cmd = ""
        self.summary = 0
        # (file, line) -> cost
        self.line_self: dict[tuple[str, int], int] = defaultdict(int)
        self.line_calls: dict[tuple[str, int], int] = defaultdict(int)
        self.line_callcount: dict[tuple[str, int], int] = defaultdict(int)
        # (file, line) -> function name (first function that charged it)
        self.line_fn: dict[tuple[str, int], str] = {}
        # fn name -> home file (file active at its first fn= record)
        self.fn_home: dict[str, str] = {}
        self.fn_self: dict[str, int] = defaultdict(int)
        self.fn_calls: dict[str, int] = defaultdict(int)
        # callee fn -> (file, line) of its first executed line (calls= target)
        self.fn_entry: dict[str, tuple[str, int]] = {}
        # (caller file, caller line, callee fn) -> [count, cost]
        self.callees: dict[tuple[str, int, str], list[int]] = defaultdict(lambda: [0, 0])
        # callee fn -> {(caller fn, caller file, caller line): [count, cost]}
        self.callers: dict[str, dict[tuple[str, str, int], list[int]]] = defaultdict(
            lambda: defaultdict(lambda: [0, 0]))
        # file -> object it was seen in (for grouping files without source)
        self.file_ob: dict[str, str] = {}


def parse_callgrind(text: str, event: str) -> Profile:
    p = Profile()
    names: dict[str, dict[str, str]] = {"fl": {}, "fn": {}, "ob": {}}

    def unc(kind: str, val: str) -> str:
        m = _NAME_RE.match(val)
        if not m:
            return val
        ident, name = m.group(1), m.group(2)
        if name is not None:
            names[kind][ident] = name
            return name
        return names[kind].get(ident, f"({ident})")

    ev_idx = 0
    npos = 1
    line_idx = 0
    prev = [0]
    cur_file = "???"
    cur_fn = "???"
    cur_ob = "???"
    cur_cob: str | None = None
    cur_cfile: str | None = None
    cur_cfn: str | None = None
    pending_call: tuple[int, int] | None = None
    in_body = False

    def decode(tok: str, k: int) -> int:
        if tok == "*":
            return prev[k]
        if tok[0] == "+":
            return prev[k] + int(tok[1:])
        if tok[0] == "-":
            return prev[k] - int(tok[1:])
        if tok.startswith("0x") or tok.startswith("0X"):
            return int(tok, 16)
        return int(tok)

    for raw in text.split("\n"):
        if not raw or raw[0] == "#":
            continue
        c0 = raw[0]
        if c0.isdigit() or c0 in "+-*":
            toks = raw.split()
            for k in range(npos):
                prev[k] = decode(toks[k], k)
            line = prev[line_idx]
            costs = toks[npos:]
            cost = int(costs[ev_idx]) if ev_idx < len(costs) else 0
            if pending_call is not None:
                count, target = pending_call
                pending_call = None
                callee = cur_cfn or "???"
                callee_file = cur_cfile if cur_cfile is not None else cur_file
                cur_cfile = None
                key = (cur_file, line)
                p.line_calls[key] += cost
                p.line_callcount[key] += count
                p.line_fn.setdefault(key, cur_fn)
                p.fn_calls[cur_fn] += cost
                e = p.callees[(cur_file, line, callee)]
                e[0] += count
                e[1] += cost
                r = p.callers[callee][(cur_fn, cur_file, line)]
                r[0] += count
                r[1] += cost
                if callee not in p.fn_entry:
                    p.fn_entry[callee] = (callee_file, target)
                p.fn_home.setdefault(callee, callee_file)
                p.file_ob.setdefault(callee_file, cur_cob or cur_ob)
                cur_cob = None
            else:
                key = (cur_file, line)
                p.line_self[key] += cost
                p.line_fn.setdefault(key, cur_fn)
                p.fn_self[cur_fn] += cost
                p.file_ob.setdefault(cur_file, cur_ob)
            continue

        key, sep, val = raw.partition("=")
        if not sep:
            key, sep, val = raw.partition(":")
            if not sep:
                continue
            val = val.strip()
            if key == "events":
                p.events = val.split()
                if event not in p.events:
                    sys.exit(f"error: event {event!r} not in profile events {p.events}")
                ev_idx = p.events.index(event)
            elif key == "positions":
                p.positions = val.split()
                npos = len(p.positions)
                line_idx = p.positions.index("line") if "line" in p.positions else npos - 1
                prev = [0] * npos
            elif key == "cmd":
                p.cmd = val
            elif key in ("summary", "totals"):
                vals = val.split()
                if ev_idx < len(vals):
                    p.summary = int(vals[ev_idx])
            continue

        if key == "fl":
            cur_file = unc("fl", val)
            in_body = True
        elif key in ("fi", "fe"):
            cur_file = unc("fl", val)
        elif key == "fn":
            cur_fn = unc("fn", val)
            p.fn_home.setdefault(cur_fn, cur_file)
            cur_cfile = None
        elif key == "ob":
            cur_ob = unc("ob", val)
        elif key == "cob":
            cur_cob = unc("ob", val)
        elif key in ("cfl", "cfi"):
            cur_cfile = unc("fl", val)
        elif key == "cfn":
            cur_cfn = unc("fn", val)
        elif key == "calls":
            parts = val.split()
            count = int(parts[0])
            target = decode(parts[1 + line_idx], line_idx) if len(parts) > 1 + line_idx else 0
            pending_call = (count, target)
        elif key in ("jfi", "jfn"):
            unc("fl" if key == "jfi" else "fn", val)
        # jump=, jcnd=, and anything else: ignored
    del in_body
    return p


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


def build_model(p: Profile, args: argparse.Namespace, src_name: str) -> dict:
    total = p.summary or sum(p.line_self.values())
    repo_root = os.path.abspath(args.repo_root)

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

    files: dict[str, dict] = {}
    for raw in raw_files:
        d = disp[raw]
        entry = files.setdefault(d, {
            "self": 0, "calls": 0, "src": None, "lines": {}, "lfn": {},
            "callees": {}, "group": group[raw], "raw": raw,
        })
        if entry["src"] is None and local[raw]:
            entry["src"] = read_source(local[raw])
    for (raw, ln), cost in p.line_self.items():
        e = files[disp[raw]]
        e["self"] += cost
        rec = e["lines"].setdefault(str(ln), [0, 0, 0])
        rec[0] += cost
    for (raw, ln), cost in p.line_calls.items():
        e = files[disp[raw]]
        e["calls"] += cost
        rec = e["lines"].setdefault(str(ln), [0, 0, 0])
        rec[1] += cost
        rec[2] += p.line_callcount[(raw, ln)]
    for (raw, ln), fn in p.line_fn.items():
        files[disp[raw]]["lfn"][str(ln)] = fn_index[fn]
    for (raw, ln, callee), (count, cost) in p.callees.items():
        e = files[disp[raw]]
        ef, el = p.fn_entry.get(callee, (p.fn_home.get(callee, "???"), 0))
        e["callees"].setdefault(str(ln), []).append(
            [fn_index[callee], disp.get(ef, ef), el, cost, count])
    for e in files.values():
        for lst in e["callees"].values():
            lst.sort(key=lambda t: -t[3])
        pcts = [rec[0] for rec in e["lines"].values()]
        e["maxLine"] = max(pcts) if pcts else 0

    functions = []
    for name in fn_names:
        home = p.fn_home[name]
        ef, el = p.fn_entry.get(name, (home, 0))
        callers = sorted(
            ([fn_index[cf], disp.get(cfile, cfile), cl, cost, count]
             for (cf, cfile, cl), (count, cost) in p.callers[name].items()),
            key=lambda t: -t[3])
        functions.append({
            "name": name,
            "file": disp.get(ef, ef),
            "line": el,
            "self": p.fn_self.get(name, 0),
            "calls": p.fn_calls.get(name, 0),
            "callers": callers,
        })

    # cold files: tracked sources in the requested dirs with no samples
    cold: list[str] = []
    for rel in tracked_files(repo_root, args.tree):
        if rel in files:
            continue
        if args.all_sources:
            src = read_source(os.path.join(repo_root, rel))
            files[rel] = {"self": 0, "calls": 0, "src": src, "lines": {}, "lfn": {},
                          "callees": {}, "group": "repo", "raw": rel, "maxLine": 0}
        else:
            cold.append(rel)

    top_lines = sorted(
        ((d, int(ln), rec[0]) for d, e in files.items() for ln, rec in e["lines"].items()),
        key=lambda t: -t[2])[:60]
    top_lines_out = []
    for d, ln, cost in top_lines:
        e = files[d]
        snippet = ""
        if e["src"] is not None:
            srcl = e["src"].split("\n")
            if 1 <= ln <= len(srcl):
                snippet = srcl[ln - 1].strip()[:110]
        fnidx = e["lfn"].get(str(ln))
        top_lines_out.append([d, ln, cost, fnidx, snippet])

    top_functions = sorted(range(len(functions)),
                           key=lambda i: -functions[i]["self"])[:60]

    max_line = max((e["maxLine"] for e in files.values()), default=0)
    return {
        "meta": {
            "title": args.title,
            "event": args.event,
            "total": total,
            "cmd": p.cmd,
            "source": src_name,
            "generated": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "maxLine": max_line,
            "repoRoot": repo_root,
            "allSources": bool(args.all_sources),
        },
        "files": files,
        "functions": functions,
        "cold": sorted(cold),
        "topLines": top_lines_out,
        "topFunctions": top_functions,
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
#tree { width: 360px; min-width: 180px; max-width: 70vw; overflow: auto; resize: horizontal;
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
table.src tr.th td { color: var(--muted); font-size: 10.5px; padding-top: 4px; padding-bottom: 2px; }
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
td.self, td.incl { text-align: right; width: 1%; font-variant-numeric: tabular-nums; color: var(--muted); }
td.self.hot { color: var(--fg); font-weight: 600; }
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
.nosrc { padding: 8px 16px; color: var(--muted); }
.home { padding: 14px 20px 40px; max-width: 1200px; }
.home h2 { font-size: 14px; margin: 18px 0 6px; }
.home h2:first-child { margin-top: 4px; }
.home p { color: var(--muted); margin: 4px 0; max-width: 90ch; }
.home table { border-collapse: collapse; width: 100%; font-size: 12.5px; }
.home th { text-align: left; color: var(--muted); font-weight: 600; padding: 3px 10px 3px 0; border-bottom: 1px solid var(--border); }
.home td { padding: 2px 10px 2px 0; vertical-align: top; border-bottom: 1px solid var(--border); }
.home td.n, .home th.n { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.home td.c { font: 11.5px var(--mono); white-space: pre; overflow: hidden; text-overflow: ellipsis; max-width: 60ch; }
.legend { display: inline-flex; align-items: center; gap: 6px; color: var(--muted); font-size: 12px; }
.legend i { display: inline-block; width: 120px; height: 10px; border-radius: 2px;
  background: linear-gradient(90deg, hsla(55,100%,var(--heat-l),.12), hsla(35,100%,var(--heat-l),.55), hsla(0,100%,var(--heat-l),.9)); }
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
const TOTAL = D.meta.total || 1;
const files = D.files, fns = D.functions;
const treeEl = document.getElementById("tree"), mainEl = document.getElementById("main");
let scale = "global", sortMode = "heat", curFile = null, query = "";
try { scale = localStorage.getItem("heat.scale") || scale; sortMode = localStorage.getItem("heat.sort") || sortMode; } catch (e) {}
document.getElementById("scale").value = scale;
document.getElementById("sort").value = sortMode;

// ---------- helpers ----------
const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const pct = v => 100 * v / TOTAL;
const fmtPct = v => { const p = pct(v); return p >= 10 ? p.toFixed(1) + "%" : p >= 0.01 ? p.toFixed(2) + "%" : p > 0 ? "<0.01%" : ""; };
const fmtN = v => v.toLocaleString("en-US");
const fmtCount = v => v.toLocaleString("en-US") + "\\u00d7";
const MAXP = Math.max(pct(D.meta.maxLine), 0.0001);
const PMIN = 0.001; // lines below 0.001% of total stay uncolored in log mode
function heatT(cost, maxP) {
  const p = pct(cost);
  if (p <= 0) return 0;
  if (scale === "linear") return Math.min(1, p / maxP);
  if (p < PMIN) return 0;
  return Math.min(1, Math.log10(p / PMIN) / Math.log10(Math.max(maxP, PMIN * 10) / PMIN));
}
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
  for (const p of Object.keys(files)) insert(p, files[p].self, false);
  for (const p of D.cold) insert(p, 0, true);
  (function sum(n) { let s = 0; for (const d of n.dirs.values()) s += sum(d); for (const f of n.files) s += f.self; n.self = s; return s; })(root);
  return root;
}
const TREE = buildTree();
const openDirs = new Set(), coldOpen = new Set();
function cmp(a, b) { return sortMode === "heat" ? (b.self - a.self) || a.name.localeCompare(b.name) : a.name.localeCompare(b.name); }
function matches(path) { return !query || path.toLowerCase().includes(query); }
function subtreeMatches(n) {
  if (!query) return true;
  for (const f of n.files) if (matches(f.path)) return true;
  for (const d of n.dirs.values()) if (subtreeMatches(d)) return true;
  return false;
}
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
      out.push(`<div class="node more" data-more="${esc(n.path)}" style="padding-left:${6 + depth * 14}px"><span class="caret">${show ? "\\u25BC" : "\\u25B6"}</span><span class="name">${zero.length} file${zero.length > 1 ? "s" : ""} without samples</span><span class="pct"></span></div>`);
      if (show) for (const f of zero) fileRow(f);
    }
  }
  rec(TREE, 0);
  treeEl.innerHTML = out.join("");
}
const MAXPDIR = 100;
treeEl.addEventListener("click", ev => {
  const n = ev.target.closest(".node");
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
function renderHome() {
  curFile = null;
  const groups = [...TREE.dirs.values()].sort((a, b) => b.self - a.self);
  let h = `<div class="home">`;
  h += `<p>${esc(D.meta.event)} = instructions executed (callgrind). Every number is the share of the <b>${fmtN(TOTAL)}</b> total. Click a file in the tree, or a line below. In a listing, click a line number to see what that line calls (and, on a function's first line, who calls it).</p>`;
  h += `<h2>Where the time goes</h2><table><tr><th>tree</th><th class="n">self</th><th class="n">${esc(D.meta.event)}</th></tr>`;
  for (const g of groups) h += `<tr><td>${esc(g.name)}/</td><td class="n" style="${heatBg(heatT(g.self, 100))}">${fmtPct(g.self)}</td><td class="n">${fmtN(g.self)}</td></tr>`;
  h += `</table>`;
  h += `<h2>Hottest lines</h2><table><tr><th class="n">#</th><th class="n">self</th><th class="n">${esc(D.meta.event)}</th><th>location</th><th>function</th><th>source</th></tr>`;
  D.topLines.forEach((t, i) => {
    const [path, ln, cost, fnidx, snip] = t;
    h += `<tr><td class="n">${i + 1}</td><td class="n" style="${heatBg(heatT(cost, MAXP))}">${fmtPct(cost)}</td><td class="n">${fmtN(cost)}</td><td><a href="${hashFor(path, ln)}">${esc(path)}:${ln}</a></td><td>${esc(fnName(fnidx))}</td><td class="c">${esc(snip)}</td></tr>`;
  });
  h += `</table>`;
  h += `<h2>Hottest functions (self)</h2><table><tr><th class="n">#</th><th class="n">self</th><th class="n">incl</th><th>function</th><th>defined at</th></tr>`;
  D.topFunctions.forEach((fi, i) => {
    const f = fns[fi];
    const loc = f.line ? `<a href="${hashFor(f.file, f.line)}">${esc(f.file)}:${f.line}</a>` : esc(f.file);
    h += `<tr><td class="n">${i + 1}</td><td class="n" style="${heatBg(heatT(f.self, MAXP))}">${fmtPct(f.self)}</td><td class="n">${fmtPct(f.self + f.calls)}</td><td>${esc(f.name)}</td><td>${loc}</td></tr>`;
  });
  h += `</table></div>`;
  mainEl.innerHTML = h;
  mainEl.scrollTop = 0;
  renderTree();
}

function renderFile(path, line) {
  const f = files[path];
  if (!f) { renderHome(); return; }
  const first = curFile !== path;
  curFile = path;
  revealInTree(path);
  const maxP = scale === "file" ? Math.max(pct(f.maxLine), 0.0001) : MAXP;
  const lines = f.lines;
  let h = `<div class="fhead"><span class="path">${esc(path)}</span>`;
  h += `<span class="stat">self <b>${fmtPct(f.self) || "0%"}</b> (${fmtN(f.self)} ${esc(D.meta.event)})</span>`;
  if (f.group === "external") h += `<span class="stat">not in this repo (${esc(f.raw)})</span>`;
  h += `</div>`;
  const hot = Object.keys(lines).map(k => [+k, lines[k][0]]).filter(t => t[1] > 0).sort((a, b) => b[1] - a[1]).slice(0, 12);
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
    const self = rec ? rec[0] : 0, calls = rec ? rec[1] : 0;
    const t = heatT(self, maxP);
    const hasc = f.callees[ln] ? " hasc" : "";
    const fnidx = f.lfn[ln];
    const title = rec ? `${fmtN(self)} self, ${fmtN(calls)} in calls${rec[2] ? " (" + fmtCount(rec[2]) + ")" : ""}${fnidx != null ? " — in " + fnName(fnidx) : ""}` : "";
    rows.push(`<tr id="L${ln}" class="${hasc}${line === ln ? " target" : ""}" style="${heatBg(t)}"${title ? ` title="${esc(title)}"` : ""}><td class="ln" data-ln="${ln}">${ln}</td><td class="self${t > 0.45 ? " hot" : ""}">${self ? fmtPct(self) : ""}</td><td class="incl">${calls ? fmtPct(calls) : ""}</td><td class="code">${text == null ? "" : esc(text)}</td></tr>`);
  };
  h += `<table class="src"><tr class="th"><td class="ln">line</td><td class="self">self</td><td class="incl" title="inclusive cost of the calls made from this line">calls</td><td class="code"></td></tr>`;
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
  if (line) {
    const el = document.getElementById("L" + line);
    if (el) { el.scrollIntoView({ block: "center" }); toggleDetail(path, line, true); }
  } else if (first) mainEl.scrollTop = 0;
}

function toggleDetail(path, ln, forceOpen) {
  const f = files[path];
  const row = document.getElementById("L" + ln);
  if (!row) return;
  const next = row.nextElementSibling;
  if (next && next.classList.contains("detail")) { if (!forceOpen) next.remove(); return; }
  document.querySelectorAll("tr.detail").forEach(e => e.remove());
  const callees = f.callees[ln] || [];
  const fi = (entryIdx[path] || {})[ln];
  const fnidx = f.lfn[ln];
  const rec = f.lines[ln] || [0, 0, 0];
  let h = `<div class="dbox">`;
  h += `<div>line ${ln}${fnidx != null ? " in <b>" + esc(fnName(fnidx)) + "</b>" : ""}: self ${fmtN(rec[0])} (${fmtPct(rec[0]) || "0%"})${rec[1] ? `, calls ${fmtN(rec[1])} (${fmtPct(rec[1])}) over ${fmtCount(rec[2])}` : ""}</div>`;
  if (callees.length) {
    h += `<h4>calls from this line (inclusive)</h4><table>`;
    for (const [ci, cf, cl, cost, count] of callees) {
      const loc = files[cf] && cl ? `<a href="${hashFor(cf, cl)}">${esc(cf)}:${cl}</a>` : esc(cf);
      h += `<tr><td class="n">${fmtPct(cost)}</td><td class="n">${fmtN(cost)}</td><td class="n">${fmtCount(count)}</td><td>${esc(fnName(ci))}</td><td>${loc}</td></tr>`;
    }
    h += `</table>`;
  }
  if (fi != null) {
    const fn = fns[fi];
    h += `<h4>${esc(fn.name)} is entered here — self ${fmtPct(fn.self) || "0%"}, inclusive ${fmtPct(fn.self + fn.calls) || "0%"}. Called from:</h4><table>`;
    for (const [ci, cf, cl, cost, count] of fn.callers) {
      const loc = files[cf] && cl ? `<a href="${hashFor(cf, cl)}">${esc(cf)}:${cl}</a>` : esc(cf);
      h += `<tr><td class="n">${fmtPct(cost)}</td><td class="n">${fmtN(cost)}</td><td class="n">${fmtCount(count)}</td><td>${esc(fnName(ci))}</td><td>${loc}</td></tr>`;
    }
    if (!fn.callers.length) h += `<tr><td>(no recorded caller — a root or a resolver stub)</td></tr>`;
    h += `</table>`;
  }
  if (!callees.length && fi == null) h += `<div style="color:var(--muted)">no calls recorded from this line</div>`;
  h += `</div>`;
  const tr = document.createElement("tr");
  tr.className = "detail";
  tr.innerHTML = `<td colspan="4">${h}</td>`;
  row.after(tr);
}

mainEl.addEventListener("click", ev => {
  const chip = ev.target.closest(".chip");
  if (chip) { location.hash = hashFor(curFile, +chip.dataset.goto); return; }
  const ln = ev.target.closest("td.ln");
  if (ln && curFile) { toggleDetail(curFile, +ln.dataset.ln, false); return; }
});

// ---------- routing ----------
function route() {
  const m = /^#f=([^&]*)(?:&l=(\\d+))?/.exec(location.hash);
  if (m) renderFile(decodeURIComponent(m[1]), m[2] ? +m[2] : 0);
  else renderHome();
}
window.addEventListener("hashchange", route);
document.getElementById("homelink").addEventListener("click", () => { location.hash = ""; });
document.getElementById("scale").addEventListener("change", ev => { scale = ev.target.value; try { localStorage.setItem("heat.scale", scale); } catch (e) {} route(); });
document.getElementById("sort").addEventListener("change", ev => { sortMode = ev.target.value; try { localStorage.setItem("heat.sort", sortMode); } catch (e) {} renderTree(); });
document.getElementById("q").addEventListener("input", ev => { query = ev.target.value.trim().toLowerCase(); renderTree(); });
document.getElementById("hmeta").textContent = `${D.meta.cmd || ""} · ${fmtN(TOTAL)} ${D.meta.event} · ${D.meta.source} · ${D.meta.generated}`;
for (const d of TREE.dirs.values()) if (d.self / TOTAL > 0.05) openDirs.add(d.path);
route();
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
    ap.add_argument("--event", default="Ir", help="callgrind event to visualise (default: Ir)")
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
    prof = parse_callgrind(text, args.event)
    if args.title is None:
        args.title = f"heatmap: {prof.cmd or os.path.basename(args.callgrind_file)}"

    self_sum = sum(prof.line_self.values())
    ratio = self_sum / prof.summary if prof.summary else float("nan")
    print(f"callgrind summary ({args.event}): {prof.summary:,}", file=sys.stderr)
    print(f"sum of self-cost lines:          {self_sum:,}", file=sys.stderr)
    print(f"ratio (must be 1.0000):          {ratio:.4f}", file=sys.stderr)
    if prof.summary and abs(ratio - 1.0) > 1e-6:
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
