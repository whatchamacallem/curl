#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence
from typing import NamedTuple
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind as cg
import theme
from theme import Cell, CellLike, Col, html_esc

PERF_CHART = "https://curl.se/perf/index.html"


class View(NamedTuple):
    key: str
    label: str
    path: str


VIEWS: tuple[View, ...] = (
    View("flame-graph", "flame graph",   "flame-graph/index.html"),
    View("heat-map",    "heat map",      "heat-map/index.html"),
    View("perf-tool",   "native timing", "perf-tool/index.html"),
)
SYMBOL_CHARS = 20
LOG_SKIP = 9


class StripLink(NamedTuple):
    key: str
    label: str
    href: str
    title: str


class Meta(NamedTuple):
    label: str
    value: str


class FnCost(NamedTuple):
    cost: int
    fn: str


class TestDir(NamedTuple):
    name: str
    dir: str


class TestArgs(NamedTuple):
    callgrind_file: list[str]
    output: str
    test: str
    raw_data: list[str]
    log: list[str]
    no_log: bool
    event: str
    top: int
    repo_root: str
    help_href: str


class TimingArgs(NamedTuple):
    output: str
    test: str
    output_file: str
    meta: list[str]


class OverviewArgs(NamedTuple):
    output: str
    test: list[str]
    meta: list[str]


FRAME_JS = """\

(function () {
  const bar = document.getElementById("bar"), home = document.getElementById("home"), view = document.getElementById("view");
  const titleEl = document.getElementById("title"), links = [...bar.querySelectorAll("a[data-view]")];
  const utilEl = document.getElementById("util");
  const framed = window.parent !== window;
  let title = titleEl.textContent, page = "", state = "", innerUtil = false;
  if (framed) titleEl.hidden = true;
  function utilShow() {
    if (utilEl) utilEl.hidden = innerUtil;
    if (framed) window.parent.postMessage({ theme: "util", has: !!utilEl && !innerUtil }, "*");
  }
  function setTitle(t) {
    title = t;
    titleEl.textContent = t;
    document.title = t;
    if (framed) window.parent.postMessage({ theme: "title", title: t }, "*");
  }

  function parse(hash) {
    const m = /^#([\\w-]*)(?:\\/(.*))?$/.exec(hash || "");
    return m ? [m[1], m[2] ? "#" + m[2] : ""] : ["", ""];
  }
  const build = (key, sub) => key ? "#" + key + (sub ? "/" + sub.slice(1) : "") : "";
  function sync(hash) {
    if (hash !== location.hash) history.replaceState(null, "", hash || "#");
    if (framed) window.parent.postMessage({ theme: "hash", hash: hash }, "*");
  }
  function show(hash) {
    const [key, sub] = parse(hash);
    const link = links.find(a => a.dataset.view === key), cur = link || links[0];
    for (const a of links) a.classList.toggle("on", a === cur);
    setTitle(cur.dataset.title);
    if (!link || !key) {
      view.hidden = true; home.hidden = false;
      window.Theme.relayout(home);
      innerUtil = false; utilShow();
      sync(""); return;
    }
    const href = link.getAttribute("href");
    if (href !== page || sub !== state) {

      innerUtil = false; utilShow();
      view.contentWindow.location.replace(href + (sub || "#"));
    }
    if (href === page) view.contentWindow.postMessage("theme:title?", "*");
    page = href; state = sub;
    home.hidden = true; view.hidden = false;
    sync(build(key, sub));
  }
  function hashFor(href) {
    for (const a of links) {
      const base = a.getAttribute("href");
      if (a.dataset.view && href.startsWith(base)) {
        const rest = href.slice(base.length);
        return build(a.dataset.view, rest.startsWith("#") ? rest : "");
      }
    }
    return null;
  }
  const resetCols = document.getElementById("reset-cols");
  if (resetCols) resetCols.addEventListener("click", e => {
    e.preventDefault();
    window.Theme.resetCols(home);
    if (page) view.contentWindow.postMessage("theme:reset-cols", "*");
  });
  document.addEventListener("click", e => {
    const a = e.target.closest("a[href]");
    if (!a || a === resetCols || a.target || e.ctrlKey || e.metaKey || e.shiftKey || e.button) return;
    const href = a.getAttribute("href");
    const hash = a.dataset.view != null ? build(a.dataset.view, "") : hashFor(href);
    if (hash == null) return;
    e.preventDefault();
    if (hash === (location.hash || "")) show(hash); else location.hash = hash;
  });
  window.addEventListener("message", e => {
    if (e.source === view.contentWindow) {
      if (e.data && e.data.theme === "title") setTitle(e.data.title);
      else if (e.data && e.data.theme === "util") { innerUtil = !!e.data.has; utilShow(); }
      else if (e.data && e.data.theme === "hash" && page) { state = e.data.hash; sync(build(parse(location.hash)[0], state)); }
    } else if (framed && e.source === window.parent) {
      if (e.data === "theme:title?") { setTitle(title); utilShow(); }
      else if (e.data === "theme:reset-cols") {
        window.Theme.resetCols(home);
        if (page) view.contentWindow.postMessage("theme:reset-cols", "*");
      }
    }
  });
  window.addEventListener("hashchange", () => show(location.hash));
  show(location.hash);
})();
"""


def meta_parse_pairs(items: Sequence[str]) -> list[Meta]:
    out: list[Meta] = []
    for item in items:
        if "=" not in item:
            sys.exit(f"error: --meta expects LABEL=VALUE, got {item!r}")
        label, _, value = item.partition("=")
        out.append(Meta(label.strip(), value))
    return out


def file_read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        print(f"warning: {path}: {e}", file=sys.stderr)
        return f"(missing: {path})"


def strip_render(title: str, links: Sequence[StripLink], help_href: str = "README.md") -> str:
    def sep() -> str:
        return '<span class="sep">|</span>'
    parts = [f'<b class="title" id="title">{html_esc(title)}</b>']
    for i, link in enumerate(links):
        if i:
            parts.append(sep())
        parts.append(f'<a href="{html_esc(link.href)}" data-view="{html_esc(link.key)}" '
                     f'data-title="{html_esc(link.title)}">{html_esc(link.label)}</a>')
    parts.append('<span class="sp"></span>')
    parts.append('<span class="util" id="util">')
    parts.append('<a href="#" id="reset-cols">reset columns</a>')
    parts.append(sep())
    parts.append(f'<a href="{html_esc(help_href)}" target="_blank">help</a>')
    parts.append(sep())
    parts.append(f'<a href="{PERF_CHART}" target="_blank" rel="noopener">curl.se/perf</a>')
    parts.append("</span>")
    return f'<nav id="bar" class="strip">{"".join(parts)}</nav>'


def meta_table(key: str, pairs: Sequence[Meta]) -> str:
    if not pairs:
        return ""
    rows: list[list[CellLike]] = [[Cell(m.label, cls="dim"), m.value] for m in pairs]
    return theme.table_render(key, [Col("label"), Col("value", clip=100)], rows, header=False)


def rawdata_list(paths: Sequence[str], out_dir: str) -> str:
    if not paths:
        return ""
    items = "".join(f'<li><a href="{html_esc(os.path.relpath(p, out_dir))}">{html_esc(os.path.basename(p))}</a></li>'
                    for p in paths)
    return f'<details class="sec"><summary><h2>raw data</h2></summary><ul class="rawdata">{items}</ul></details>'


def path_display(repo_root: str, path: str) -> str:
    root = os.path.abspath(repo_root).rstrip("/") + "/"
    if path == "???" or not path:
        return ""
    norm = os.path.normpath(path) if os.path.isabs(path) else path
    if norm.startswith(root):
        return norm[len(root):]
    if os.path.isabs(norm) and not os.path.isfile(norm):
        return os.path.basename(norm)
    return norm


def functions_table(p: cg.Profile, event: str, top: int, repo_root: str) -> str:
    total = p.value(p.totals(), event) or 1

    def entry_link(fn: str) -> str:
        entry = p.fn_entry.get(fn, cg.LineKey(p.fn_home.get(fn, "???"), 0))
        f = path_display(repo_root, entry.file)
        if not f or not entry.line or not (os.path.isfile(os.path.join(repo_root, f)) or os.path.isfile(f)):
            return ""
        return "heat-map/index.html#fn=" + html_esc(quote(fn, safe="/-_.!~*'()"))

    ranked = sorted((FnCost(p.value(vec, event), fn) for fn, vec in p.fn_self.items() if p.value(vec, event) > 0),
                    key=lambda t: (-t.cost, t.fn))[:top]
    max_pct = 100.0 * ranked[0].cost / total if ranked else 1.0
    fn_calls = {fn: sum(cc.count for cc in callers.values()) for fn, callers in p.callers.items()}
    calls_total = sum(fn_calls.values()) or 1
    calls_max_pct = 100.0 * max(fn_calls.values(), default=0) / calls_total
    cols = [Col("#", "rank", num=True),
            Col("% self", f"share of all {event} spent in the function itself, not in what it calls", num=True),
            Col("symbol", f"the function, first {SYMBOL_CHARS} characters (drag the bar for more); "
                          "opens the heat map at its first line", width=SYMBOL_CHARS),
            Col("calls", "times the function was entered", num=True),
            Col("callers", "who called it, with the share of those calls; cut off at the edge, hover for all")]
    rows: list[list[CellLike]] = []
    for rank, r in enumerate(ranked, 1):
        by_caller: dict[str, int] = {}
        for caller, cc in p.callers.get(r.fn, {}).items():
            by_caller[caller.fn] = by_caller.get(caller.fn, 0) + cc.count
        ncalls = sum(by_caller.values())
        share = 100.0 * r.cost / total
        href = entry_link(r.fn)
        by_caller_sorted = sorted(by_caller.items(), key=lambda kv: (-kv[1], kv[0]))
        who = ", ".join(f"{cfn} ({theme.num_pct(100.0 * n / ncalls)})" for cfn, n in by_caller_sorted)

        def caller_html(cfn: str, n: int) -> str:
            chref = entry_link(cfn)
            label = f"{html_esc(cfn)} ({theme.num_pct(100.0 * n / ncalls)})"
            return f'<a href="{chref}">{label}</a>' if chref else label

        who_html = ", ".join(caller_html(cfn, n) for cfn, n in by_caller_sorted)
        rows.append([str(rank),
                     Cell(theme.num_pct(share), style=theme.heat_style(theme.heat_t(share, max_pct))),
                     Cell(r.fn, title=r.fn, html=f'<a href="{href}">{html_esc(r.fn)}</a>' if href else None),
                     Cell(theme.num_human(ncalls), title=f"{ncalls:,} calls",
                          style=theme.heat_style(theme.heat_t(100.0 * ncalls / calls_total, calls_max_pct))) if ncalls else "",
                     Cell(who, title=who, html=who_html) if who else Cell("(no recorded caller)", cls="dim")])
    return theme.table_render("report.functions", cols, rows, fill=True, lines=True)


TIME_LINE = re.compile(r"^(\s*[A-Za-z][\w/ ]*:\s*)"
                       r"(-?\d+(?:\.\d+)?)\s*(usecs?|us|µs|msecs?|ms|nsecs?|ns|secs?|s)\s*$",
                       re.I | re.M)
TIME_SCALE: dict[str, float] = {"usec": 1e-6, "usecs": 1e-6, "us": 1e-6, "µs": 1e-6,
                                "msec": 1e-3, "msecs": 1e-3, "ms": 1e-3,
                                "nsec": 1e-9, "nsecs": 1e-9, "ns": 1e-9,
                                "sec": 1.0, "secs": 1.0, "s": 1.0}


def time_humanize(text: str) -> str:
    def one(m: re.Match[str]) -> str:
        scale = TIME_SCALE.get(m.group(3).lower())
        return m.group(0) if scale is None else m.group(1) + theme.num_time(float(m.group(2)) * scale)
    return TIME_LINE.sub(one, text)


def value_humanize(label: str, value: str) -> str:
    line = time_humanize(f"{label}: {value}")
    return line.split(": ", 1)[1] if line != f"{label}: {value}" else value


PID_PREFIX = re.compile(r"^==\d+==\s?")


def log_block(path: str) -> str:
    lines = file_read_text(path).rstrip().split("\n")[LOG_SKIP:]
    text = "\n".join(PID_PREFIX.sub("", ln) for ln in lines)
    return f'<div class="tbl"><pre class="logbox">{html_esc(text)}</pre></div>'


def page_write(path: str, page: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {path} ({len(page.encode('utf-8')):,} bytes)", file=sys.stderr)


def report_test(args: TestArgs) -> None:
    p = cg.profile_load(args.callgrind_file)
    if not p.events:
        sys.exit("error: no 'events:' line -- not a callgrind file?")
    if args.event not in p.event_names():
        sys.exit(f"error: event {args.event!r} not in this profile ({' '.join(p.event_names())})")
    check = cg.profile_self_check(p)
    print(f"ratio (must be 1.0000): {check.ratio:.4f}", file=sys.stderr)
    if check.total and abs(check.ratio - 1.0) > 1e-6:
        sys.exit("error: per-line self cost does not add up to callgrind's summary")

    links = [StripLink("", "summary", "#", args.test)] + \
        [StripLink(v.key, v.label, v.path, f"{args.test} / {v.label}") for v in VIEWS]
    body = strip_render(args.test, links, help_href=args.help_href)
    out_dir = os.path.dirname(os.path.abspath(args.output))
    body += '<main id="home"><div class="page">'
    if args.log and not args.no_log:
        body += '<details class="sec"><summary><h2>valgrind log</h2></summary>'
        for log in args.log:
            if len(args.log) > 1:
                body += f"<p>{html_esc(os.path.basename(log))}</p>"
            body += log_block(log)
        body += "</details>"
    body += rawdata_list(args.raw_data, out_dir)
    body += f"<h2>top {args.top} functions by self</h2>" + functions_table(p, args.event, args.top, args.repo_root)
    body += '</div></main><iframe id="view" hidden title="report page"></iframe>'
    page_write(args.output, theme.page_document(args.test, body, extra_js=FRAME_JS, body_class="frame"))


def report_timing(args: TimingArgs) -> None:
    body = '<div class="page">' + meta_table("timing.meta", meta_parse_pairs(args.meta))
    out = time_humanize(file_read_text(args.output_file).rstrip())
    body += f"<h2>output</h2><pre>{html_esc(out)}</pre></div>"
    page_write(args.output, theme.page_document(f"{args.test} / native timing", body))


def report_overview(args: OverviewArgs) -> None:
    out_dir = os.path.dirname(os.path.abspath(args.output))
    tests: list[TestDir] = []
    for item in args.test:
        name, _, d = item.partition("=")
        tests.append(TestDir(name, d or os.path.join(out_dir, name)))
    tests.sort()
    keys: list[str] = []
    numbers: dict[str, dict[str, str]] = {}
    for t in tests:
        vals: dict[str, str] = {}
        for line in file_read_text(os.path.join(t.dir, "perf-tool", "output.txt")).splitlines():
            m = re.match(r"^([A-Za-z][^:]{0,30}):\s+(.+?)\s*$", line)
            if m:
                vals[m.group(1)] = value_humanize(m.group(1), m.group(2))
                if m.group(1) not in keys:
                    keys.append(m.group(1))
        numbers[t.name] = vals
    cols = [Col("one report per test")] + [Col(k, num=True) for k in keys]
    rows: list[list[CellLike]] = [
        [Cell(t.name, html=f'<a href="{html_esc(t.name)}/index.html">{html_esc(t.name)}</a>')]
        + [numbers[t.name].get(k, "") for k in keys]
        for t in tests]
    links = [StripLink("", "overview", "#", "overview")] + \
        [StripLink(t.name, t.name, f"{t.name}/index.html", t.name) for t in tests]
    body = strip_render("overview", links)
    body += '<main id="home"><div class="page">' + meta_table("overview.meta", meta_parse_pairs(args.meta))
    body += "<h2>test suites</h2>" + theme.table_render("overview.tests", cols, rows)
    body += '</div></main><iframe id="view" hidden title="report page"></iframe>'
    page_write(args.output, theme.page_document("overview", body, extra_js=FRAME_JS, body_class="frame"))


def report_main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("test", help="one perf test's index page")
    t.add_argument("callgrind_file", nargs="+", help="callgrind output file(s); several are merged into one profile")
    t.add_argument("-o", "--output", required=True)
    t.add_argument("--test", required=True, help="perf test name")
    t.add_argument("--raw-data", action="append", default=[], metavar="FILE",
                   help="callgrind trace file to link (repeatable); listed relative to -o")
    t.add_argument("--log", action="append", default=[], help="valgrind log to include (repeatable)")
    t.add_argument("--no-log", action="store_true", help="omit the valgrind log section even if --log was given")
    t.add_argument("--event", default="Ir", help="event that ranks the functions (default: Ir)")
    t.add_argument("--top", type=int, default=50)
    t.add_argument("--repo-root", default=".")
    t.add_argument("--help-href", default="README.md",
                   help="the strip's 'help' target, relative to this page (default: README.md; "
                        "a per-test page under an overview needs ../README.md)")

    n = sub.add_parser("timing", help="the native timing run page")
    n.add_argument("-o", "--output", required=True)
    n.add_argument("--test", required=True)
    n.add_argument("--output-file", required=True, help="the run's captured output")
    n.add_argument("--meta", action="append", metavar="LABEL=VALUE", default=[])

    o = sub.add_parser("overview", help="the page over several tests")
    o.add_argument("-o", "--output", required=True)
    o.add_argument("--test", action="append", metavar="NAME[=DIR]", required=True,
                   help="a test and its report directory (default: NAME next to the output)")
    o.add_argument("--meta", action="append", metavar="LABEL=VALUE", default=[])

    args = ap.parse_args()
    if args.cmd == "test":
        report_test(TestArgs(callgrind_file=args.callgrind_file, output=args.output, test=args.test,
                             raw_data=args.raw_data, log=args.log, no_log=args.no_log, event=args.event,
                             top=args.top, repo_root=args.repo_root, help_href=args.help_href))
    elif args.cmd == "timing":
        report_timing(TimingArgs(output=args.output, test=args.test, output_file=args.output_file, meta=args.meta))
    else:
        report_overview(OverviewArgs(output=args.output, test=args.test, meta=args.meta))


if __name__ == "__main__":
    report_main()
