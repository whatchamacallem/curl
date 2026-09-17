#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Sequence
import os
import re
import sys
from typing import NamedTuple
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind
import theme
from theme import Cell, CellOrText, Column, html_escape

LOG_SKIP_LINES = 9
PERF_CHART = "https://curl.se/perf/index.html"
PID_PREFIX = re.compile(r"^==\d+==\s?")
SYMBOL_CHARS = 20
TIME_LINE = re.compile(r"^(\s*[A-Za-z][\w/ ]*:\s*)"
                       r"(-?\d+(?:\.\d+)?)\s*(usecs?|us|µs|msecs?|ms|nsecs?|ns|secs?|s)\s*$",
                       re.I | re.M)
TIME_SCALE: dict[str, float] = {"usec": 1e-6, "usecs": 1e-6, "us": 1e-6, "µs": 1e-6,
                                "msec": 1e-3, "msecs": 1e-3, "ms": 1e-3,
                                "nsec": 1e-9, "nsecs": 1e-9, "ns": 1e-9,
                                "sec": 1.0, "secs": 1.0, "s": 1.0}


FRAME_JS = """\

(function () {
  const bar = document.getElementById("bar"), home = document.getElementById("home"), view = document.getElementById("view");
  const titleElement = document.getElementById("title"), links = [...bar.querySelectorAll("a[data-view]")];
  const utilElement = document.getElementById("util");
  const framed = window.parent !== window;
  let title = titleElement.textContent, page = "", state = "", innerUtil = false;
  if (framed) titleElement.hidden = true;
  function utilShow() {
    if (utilElement) utilElement.hidden = innerUtil;
    if (framed) window.parent.postMessage({ theme: "util", has: !!utilElement && !innerUtil }, "*");
  }
  function setTitle(newTitle) {
    title = newTitle;
    titleElement.textContent = newTitle;
    document.title = newTitle;
    if (framed) window.parent.postMessage({ theme: "title", title: newTitle }, "*");
  }

  function parse(hash) {
    const match = /^#([\\w-]*)(?:\\/(.*))?$/.exec(hash || "");
    return match ? [match[1], match[2] ? "#" + match[2] : ""] : ["", ""];
  }
  const build = (key, sub) => key ? "#" + key + (sub ? "/" + sub.slice(1) : "") : "";
  function sync(hash) {
    if (hash !== location.hash) history.replaceState(null, "", hash || "#");
    if (framed) window.parent.postMessage({ theme: "hash", hash: hash }, "*");
  }
  function show(hash) {
    const [key, sub] = parse(hash);
    const link = links.find(anchor => anchor.dataset.view === key), current = link || links[0];
    for (const anchor of links) anchor.classList.toggle("on", anchor === current);
    setTitle(current.dataset.title);
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
    for (const anchor of links) {
      const base = anchor.getAttribute("href");
      if (anchor.dataset.view && href.startsWith(base)) {
        const rest = href.slice(base.length);
        return build(anchor.dataset.view, rest.startsWith("#") ? rest : "");
      }
    }
    return null;
  }
  const resetCols = document.getElementById("reset-cols");
  if (resetCols) resetCols.addEventListener("click", event => {
    event.preventDefault();
    window.Theme.resetCols(home);
    if (page) view.contentWindow.postMessage("theme:reset-cols", "*");
  });
  document.addEventListener("click", event => {
    const anchor = event.target.closest("a[href]");
    if (!anchor || anchor === resetCols || anchor.target || event.ctrlKey || event.metaKey || event.shiftKey || event.button) return;
    const href = anchor.getAttribute("href");
    const hash = anchor.dataset.view != null ? build(anchor.dataset.view, "") : hashFor(href);
    if (hash == null) return;
    event.preventDefault();
    if (hash === (location.hash || "")) show(hash); else location.hash = hash;
  });
  window.addEventListener("message", event => {
    if (event.source === view.contentWindow) {
      if (event.data && event.data.theme === "title") setTitle(event.data.title);
      else if (event.data && event.data.theme === "util") { innerUtil = !!event.data.has; utilShow(); }
      else if (event.data && event.data.theme === "hash" && page) { state = event.data.hash; sync(build(parse(location.hash)[0], state)); }
    } else if (framed && event.source === window.parent) {
      if (event.data === "theme:title?") { setTitle(title); utilShow(); }
      else if (event.data === "theme:reset-cols") {
        window.Theme.resetCols(home);
        if (page) view.contentWindow.postMessage("theme:reset-cols", "*");
      }
    }
  });
  window.addEventListener("hashchange", () => show(location.hash));
  show(location.hash);
})();
"""


class FunctionCost(NamedTuple):
    cost: int
    function: str


class Meta(NamedTuple):
    label: str
    value: str


class OverviewArgs(NamedTuple):
    output: str
    test: list[str]
    meta: list[str]


class StripLink(NamedTuple):
    key: str
    label: str
    href: str
    title: str


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


class TestDirectory(NamedTuple):
    name: str
    directory: str


class TimingArgs(NamedTuple):
    output: str
    test: str
    output_file: str
    meta: list[str]


class View(NamedTuple):
    key: str
    label: str
    path: str


VIEWS: tuple[View, ...] = (
    View("flame-graph", "flame graph",   "flame-graph/index.html"),
    View("heat-map",    "heat map",      "heat-map/index.html"),
    View("perf-tool",   "native timing", "perf-tool/index.html"),
)


def file_read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError as error:
        print(f"warning: {path}: {error}", file=sys.stderr)
        return f"(missing: {path})"


def functions_table(profile: callgrind.Profile, event: str, top: int, repo_root: str) -> str:
    total = profile.value(profile.totals(), event) or 1

    def entry_link(function: str) -> str:
        entry = profile.function_entry.get(function, callgrind.SourceLine(profile.function_home.get(function, "???"), 0))
        display_path = path_display(repo_root, entry.file)
        if not display_path or not entry.line \
                or not (os.path.isfile(os.path.join(repo_root, display_path)) or os.path.isfile(display_path)):
            return ""
        return "heat-map/index.html#fn=" + html_escape(quote(function, safe="/-_.!~*'()"))

    ranked = sorted((FunctionCost(profile.value(costs, event), function)
                     for function, costs in profile.function_self.items() if profile.value(costs, event) > 0),
                    key=lambda t: (-t.cost, t.function))[:top]
    max_pct = 100.0 * ranked[0].cost / total if ranked else 1.0
    function_calls = {function: sum(tally.count for tally in callers.values())
                      for function, callers in profile.callers.items()}
    calls_total = sum(function_calls.values()) or 1
    calls_max_pct = 100.0 * max(function_calls.values(), default=0) / calls_total
    columns = [Column("#", "rank", numeric=True),
              Column("% self", f"share of all {event} spent in the function itself, not in what it calls", numeric=True),
              Column("symbol", f"the function, first {SYMBOL_CHARS} characters (drag the bar for more); "
                               "opens the heat map at its first line", width=SYMBOL_CHARS),
              Column("calls", "times the function was entered", numeric=True),
              Column("callers", "who called it, with the share of those calls; cut off at the edge, hover for all")]
    rows: list[list[CellOrText]] = []
    for rank, ranked_function in enumerate(ranked, 1):
        by_caller: dict[str, int] = {}
        for caller, tally in profile.callers.get(ranked_function.function, {}).items():
            by_caller[caller.function] = by_caller.get(caller.function, 0) + tally.count
        call_count = sum(by_caller.values())
        share = 100.0 * ranked_function.cost / total
        href = entry_link(ranked_function.function)
        by_caller_sorted = sorted(by_caller.items(), key=lambda pair: (-pair[1], pair[0]))
        who = ", ".join(f"{caller_name} ({theme.num_pct(100.0 * count / call_count)})"
                        for caller_name, count in by_caller_sorted)

        def caller_html(caller_name: str, count: int) -> str:
            caller_href = entry_link(caller_name)
            label = f"{html_escape(caller_name)} ({theme.num_pct(100.0 * count / call_count)})"
            return f'<a href="{caller_href}">{label}</a>' if caller_href else label

        who_html = ", ".join(caller_html(caller_name, count) for caller_name, count in by_caller_sorted)
        rows.append([str(rank),
                     Cell(theme.num_pct(share), style=theme.heat_style(theme.heat_t(share, max_pct))),
                     Cell(ranked_function.function, title=ranked_function.function,
                          html=f'<a href="{href}">{html_escape(ranked_function.function)}</a>' if href else None),
                     Cell(theme.num_human(call_count), title=f"{call_count:,} calls",
                          style=theme.heat_style(theme.heat_t(100.0 * call_count / calls_total, calls_max_pct)))
                     if call_count else "",
                     Cell(who, title=who, html=who_html) if who else Cell("(no recorded caller)", cls="dim")])
    return theme.table_render("report.functions", columns, rows, fill=True, lines=True)


def log_block(path: str) -> str:
    lines = file_read_text(path).rstrip().split("\n")[LOG_SKIP_LINES:]
    text = "\n".join(PID_PREFIX.sub("", line) for line in lines)
    return f'<div class="tbl"><pre class="logbox">{html_escape(text)}</pre></div>'


def meta_parse_pairs(items: Sequence[str]) -> list[Meta]:
    out: list[Meta] = []
    for item in items:
        if "=" not in item:
            sys.exit(f"error: --meta expects LABEL=VALUE, got {item!r}")
        label, _, value = item.partition("=")
        out.append(Meta(label.strip(), value))
    return out


def meta_table(key: str, pairs: Sequence[Meta]) -> str:
    if not pairs:
        return ""
    rows: list[list[CellOrText]] = [[Cell(pair.label, cls="dim"), pair.value] for pair in pairs]
    return theme.table_render(key, [Column("label"), Column("value", clip=100)], rows, header=False)


def path_display(repo_root: str, path: str) -> str:
    root = os.path.abspath(repo_root).rstrip("/") + "/"
    if path == "???" or not path:
        return ""
    normalized = os.path.normpath(path) if os.path.isabs(path) else path
    if normalized.startswith(root):
        return normalized[len(root):]
    if os.path.isabs(normalized) and not os.path.isfile(normalized):
        return os.path.basename(normalized)
    return normalized


def page_write(path: str, page: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(page)
    print(f"wrote {path} ({len(page.encode('utf-8')):,} bytes)", file=sys.stderr)


def rawdata_list(paths: Sequence[str], out_dir: str) -> str:
    if not paths:
        return ""
    items = "".join(f'<li><a href="{html_escape(os.path.relpath(path, out_dir))}">'
                    f'{html_escape(os.path.basename(path))}</a></li>' for path in paths)
    return f'<details class="sec"><summary><h2>raw data</h2></summary><ul class="rawdata">{items}</ul></details>'


def report_main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    test_parser = subparsers.add_parser("test", help="one perf test's index page")
    test_parser.add_argument("callgrind_file", nargs="+",
                             help="callgrind output file(s); several are merged into one profile")
    test_parser.add_argument("-o", "--output", required=True)
    test_parser.add_argument("--test", required=True, help="perf test name")
    test_parser.add_argument("--raw-data", action="append", default=[], metavar="FILE",
                             help="callgrind trace file to link (repeatable); listed relative to -o")
    test_parser.add_argument("--log", action="append", default=[], help="valgrind log to include (repeatable)")
    test_parser.add_argument("--no-log", action="store_true",
                             help="omit the valgrind log section even if --log was given")
    test_parser.add_argument("--event", default="Ir", help="event that ranks the functions (default: Ir)")
    test_parser.add_argument("--top", type=int, default=50)
    test_parser.add_argument("--repo-root", default=".")
    test_parser.add_argument("--help-href", default="README.md",
                             help="the strip's 'help' target, relative to this page (default: README.md; "
                                  "a per-test page under an overview needs ../README.md)")

    timing_parser = subparsers.add_parser("timing", help="the native timing run page")
    timing_parser.add_argument("-o", "--output", required=True)
    timing_parser.add_argument("--test", required=True)
    timing_parser.add_argument("--output-file", required=True, help="the run's captured output")
    timing_parser.add_argument("--meta", action="append", metavar="LABEL=VALUE", default=[])

    overview_parser = subparsers.add_parser("overview", help="the page over several tests")
    overview_parser.add_argument("-o", "--output", required=True)
    overview_parser.add_argument("--test", action="append", metavar="NAME[=DIR]", required=True,
                                 help="a test and its report directory (default: NAME next to the output)")
    overview_parser.add_argument("--meta", action="append", metavar="LABEL=VALUE", default=[])

    namespace = parser.parse_args()
    if namespace.cmd == "test":
        report_test(TestArgs(callgrind_file=namespace.callgrind_file, output=namespace.output, test=namespace.test,
                             raw_data=namespace.raw_data, log=namespace.log, no_log=namespace.no_log,
                             event=namespace.event, top=namespace.top, repo_root=namespace.repo_root,
                             help_href=namespace.help_href))
    elif namespace.cmd == "timing":
        report_timing(TimingArgs(output=namespace.output, test=namespace.test,
                                 output_file=namespace.output_file, meta=namespace.meta))
    else:
        report_overview(OverviewArgs(output=namespace.output, test=namespace.test, meta=namespace.meta))


def report_overview(args: OverviewArgs) -> None:
    out_dir = os.path.dirname(os.path.abspath(args.output))
    tests: list[TestDirectory] = []
    for item in args.test:
        name, _, directory = item.partition("=")
        tests.append(TestDirectory(name, directory or os.path.join(out_dir, name)))
    tests.sort()
    keys: list[str] = []
    numbers: dict[str, dict[str, str]] = {}
    for test in tests:
        values: dict[str, str] = {}
        for line in file_read_text(os.path.join(test.directory, "perf-tool", "output.txt")).splitlines():
            match = re.match(r"^([A-Za-z][^:]{0,30}):\s+(.+?)\s*$", line)
            if match:
                values[match.group(1)] = value_humanize(match.group(1), match.group(2))
                if match.group(1) not in keys:
                    keys.append(match.group(1))
        numbers[test.name] = values
    columns = [Column("one report per test")] + [Column(key, numeric=True) for key in keys]
    rows: list[list[CellOrText]] = [
        [Cell(test.name, html=f'<a href="{html_escape(test.name)}/index.html">{html_escape(test.name)}</a>')]
        + [numbers[test.name].get(key, "") for key in keys]
        for test in tests]
    links = [StripLink("", "overview", "#", "overview")] + \
        [StripLink(test.name, test.name, f"{test.name}/index.html", test.name) for test in tests]
    body = strip_render("overview", links)
    body += '<main id="home"><div class="page">' + meta_table("overview.meta", meta_parse_pairs(args.meta))
    body += "<h2>test suites</h2>" + theme.table_render("overview.tests", columns, rows)
    body += '</div></main><iframe id="view" hidden title="report page"></iframe>'
    page_write(args.output, theme.page_document("overview", body, extra_js=FRAME_JS, body_class="frame"))


def report_test(args: TestArgs) -> None:
    profile = callgrind.profile_load(args.callgrind_file)
    if not profile.events:
        sys.exit("error: no 'events:' line -- not a callgrind file?")
    if args.event not in profile.event_names():
        sys.exit(f"error: event {args.event!r} not in this profile ({' '.join(profile.event_names())})")
    balance = callgrind.profile_self_check(profile)
    print(f"ratio (must be 1.0000): {balance.ratio:.4f}", file=sys.stderr)
    if balance.total and abs(balance.ratio - 1.0) > 1e-6:
        sys.exit("error: per-line self cost does not add up to callgrind's summary")

    links = [StripLink("", "summary", "#", args.test)] + \
        [StripLink(view.key, view.label, view.path, f"{args.test} / {view.label}") for view in VIEWS]
    body = strip_render(args.test, links, help_href=args.help_href)
    out_dir = os.path.dirname(os.path.abspath(args.output))
    body += '<main id="home"><div class="page">'
    if args.log and not args.no_log:
        body += '<details class="sec"><summary><h2>valgrind log</h2></summary>'
        for log in args.log:
            if len(args.log) > 1:
                body += f"<p>{html_escape(os.path.basename(log))}</p>"
            body += log_block(log)
        body += "</details>"
    body += rawdata_list(args.raw_data, out_dir)
    body += f"<h2>top {args.top} functions by self</h2>" + functions_table(profile, args.event, args.top, args.repo_root)
    body += '</div></main><iframe id="view" hidden title="report page"></iframe>'
    page_write(args.output, theme.page_document(args.test, body, extra_js=FRAME_JS, body_class="frame"))


def report_timing(args: TimingArgs) -> None:
    body = '<div class="page">' + meta_table("timing.meta", meta_parse_pairs(args.meta))
    output = time_humanize(file_read_text(args.output_file).rstrip())
    body += f"<h2>output</h2><pre>{html_escape(output)}</pre></div>"
    page_write(args.output, theme.page_document(f"{args.test} / native timing", body))


def strip_render(title: str, links: Sequence[StripLink], help_href: str = "README.md") -> str:
    def separator() -> str:
        return '<span class="sep">|</span>'
    parts = [f'<b class="title" id="title">{html_escape(title)}</b>']
    for index, link in enumerate(links):
        if index:
            parts.append(separator())
        parts.append(f'<a href="{html_escape(link.href)}" data-view="{html_escape(link.key)}" '
                     f'data-title="{html_escape(link.title)}">{html_escape(link.label)}</a>')
    parts.append('<span class="sp"></span>')
    parts.append('<span class="util" id="util">')
    parts.append('<a href="#" id="reset-cols">reset columns</a>')
    parts.append(separator())
    parts.append(f'<a href="{html_escape(help_href)}" target="_blank">help</a>')
    parts.append(separator())
    parts.append(f'<a href="{PERF_CHART}" target="_blank" rel="noopener">curl.se/perf</a>')
    parts.append("</span>")
    return f'<nav id="bar" class="strip">{"".join(parts)}</nav>'


def time_humanize(text: str) -> str:
    def one(match: re.Match[str]) -> str:
        scale = TIME_SCALE.get(match.group(3).lower())
        return match.group(0) if scale is None else match.group(1) + theme.num_time(float(match.group(2)) * scale)
    return TIME_LINE.sub(one, text)


def value_humanize(label: str, value: str) -> str:
    line = time_humanize(f"{label}: {value}")
    return line.split(": ", 1)[1] if line != f"{label}: {value}" else value


if __name__ == "__main__":
    report_main()
