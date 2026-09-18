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
import callgrind_diff
import theme
from theme import Cell, CellOrText, Column, html_escape

EVENT = "Ir"
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
TOP = 50


FRAME_JS = """\

(function () {
  const bar = document.getElementById("bar"), home = document.getElementById("home"), view = document.getElementById("view");
  const titleElement = document.getElementById("title"), links = [...bar.querySelectorAll("a[data-view]")];
  const util = document.getElementById("util"), framed = window.parent !== window;
  let page = "", state = "", title = titleElement.textContent;
  function setTitle(newTitle) {
    title = newTitle;
    titleElement.textContent = framed ? "" : newTitle;
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
  }
  function show(hash) {
    const [key, sub] = parse(hash);
    const link = links.find(anchor => anchor.dataset.view === key), current = link || links[0];
    for (const anchor of links) anchor.classList.toggle("on", anchor === current);
    setTitle(current.dataset.title);
    util.hidden = !framed && !!(link && key && link.dataset.frame);
    if (!link || !key) {
      view.hidden = true; home.hidden = false;
      window.Theme.relayout(home);
      sync(""); return;
    }
    const href = link.getAttribute("href");
    if (href !== page || sub !== state) view.contentWindow.location.replace(href + (sub || "#"));
    else view.contentWindow.postMessage("theme:title?", "*");
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
  function resetAll() {
    window.Theme.resetCols(home);
    if (page) view.contentWindow.postMessage("theme:reset-cols", "*");
  }
  resetCols.addEventListener("click", event => {
    event.preventDefault();
    resetAll();
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
    if (event.source === view.contentWindow && event.data) {
      if (event.data.theme === "title") setTitle(event.data.title);
      else if (event.data.theme === "hash" && page) {
        state = event.data.hash;
        sync(build(parse(location.hash)[0], state));
      }
      return;
    }
    if (framed && event.source === window.parent) {
      if (event.data === "theme:title?") setTitle(title);
      else if (event.data === "theme:reset-cols") resetAll();
    }
  });
  window.addEventListener("hashchange", () => show(location.hash));
  show(location.hash);
})();
"""


class FunctionCost(NamedTuple):
    cost: int
    function: str


class Header(NamedTuple):
    label: str
    value: str


class HeaderBlock(NamedTuple):
    label: str
    pairs: list[Header]


class OverviewArgs(NamedTuple):
    output: str
    test: list[str]
    header: list[str]
    header_file: str
    header_block: list[str]
    diff: bool


class StripLink(NamedTuple):
    key: str
    label: str
    href: str
    title: str
    frame: bool = False


class TestArgs(NamedTuple):
    callgrind_file: list[str]
    output: str
    test: str
    raw_data: list[str]
    log: list[str]
    no_log: bool
    help_href: str
    diff: bool
    header: list[str]


class TestDirectory(NamedTuple):
    name: str
    directory: str


class TimingArgs(NamedTuple):
    output: str
    test: str
    output_file: str
    header: list[str]


class View(NamedTuple):
    key: str
    label: str
    path: str


VIEWS: tuple[View, ...] = (
    View("flame-graph", "flame graph",   "flame-graph/index.html"),
    View("heat-map",    "heat map",      "heat-map/index.html"),
    View("perf-tool",   "native timing", "perf-tool/index.html"),
)

DIFF_VIEWS: tuple[View, ...] = (
    View("heat-map", "heat map", "heat-map/index.html"),
)


def diff_functions_table(profile: callgrind.Profile) -> str:
    total = profile.value(callgrind_diff.profile_magnitudes(profile), EVENT) or 1
    ranked = sorted((FunctionCost(profile.value(costs, EVENT), function)
                     for function, costs in profile.function_self.items() if profile.value(costs, EVENT) != 0),
                    key=lambda t: (-abs(t.cost), t.function))[:TOP]
    max_pct = 100.0 * abs(ranked[0].cost) / total if ranked else 1.0
    columns = [Column("#", "rank by how much the function changed, largest first", numeric=True),
               Column("% self", f"the function's own {EVENT} delta, as a share of every line's {EVENT} change "
                                "added up; + is more than the baseline, - is less", numeric=True),
               Column("symbol", f"the function, first {SYMBOL_CHARS} characters (drag the bar for more); "
                                "opens the heat map at its first line", width=SYMBOL_CHARS),
               Column(EVENT, f"the signed {EVENT} delta itself", numeric=True, grow=True)]
    rows: list[list[CellOrText]] = []
    for rank, ranked_function in enumerate(ranked, 1):
        share = 100.0 * ranked_function.cost / total
        href = entry_link(profile, ranked_function.function)
        rows.append([str(rank),
                     Cell(theme.num_signed_pct(share), style=theme.heat_style(theme.heat_t(share, max_pct), signed=True)),
                     Cell(ranked_function.function, title=ranked_function.function,
                          html=f'<a href="{href}">{html_escape(ranked_function.function)}</a>' if href else None),
                     Cell(theme.num_signed(ranked_function.cost), title=f"{ranked_function.cost:+,} {EVENT}")])
    return theme.table_render("report.functions", columns, rows, fill=True)


def diff_overview_rows(tests: Sequence[TestDirectory]) -> tuple[list[Column], list[list[CellOrText]]]:
    columns = [Column("one report per test"),
               Column(EVENT, f"the whole run's {EVENT} delta", numeric=True),
               Column("% of change", f"that delta against every function's {EVENT} change added up", numeric=True),
               Column("functions changed", f"functions whose {EVENT} moved at all", numeric=True)]
    rows: list[list[CellOrText]] = []
    for test in tests:
        raw_dir = os.path.join(test.directory, "raw")
        files = sorted(os.path.join(raw_dir, name) for name in os.listdir(raw_dir)) if os.path.isdir(raw_dir) else []
        link = Cell(test.name, html=f'<a href="{html_escape(test.name)}/index.html">{html_escape(test.name)}</a>')
        if not files:
            rows.append([link, "", "", ""])
            continue
        profile = callgrind.profile_load(files)
        delta = profile.value(profile.totals(), EVENT)
        changed = sum(1 for costs in profile.function_self.values() if profile.value(costs, EVENT) != 0)
        magnitude = profile.value(callgrind_diff.profile_magnitudes(profile), EVENT)
        rows.append([link, Cell(theme.num_signed(delta), title=f"{delta:+,} {EVENT}"),
                     theme.num_signed_pct(100.0 * delta / magnitude) if magnitude else "", theme.num_human(changed)])
    return columns, rows


def diff_report_overview(args: OverviewArgs) -> None:
    tests = overview_tests(args)
    columns, rows = diff_overview_rows(tests)
    overview_page(args, tests, columns, rows)


def diff_report_test(args: TestArgs) -> None:
    profile = callgrind.profile_load(args.callgrind_file)
    report_page(args, DIFF_VIEWS, f"top {TOP} functions by change in self", diff_functions_table(profile))


def entry_link(profile: callgrind.Profile, function: str) -> str:
    entry = profile.function_entry.get(function)
    if entry is None or not entry.line or callgrind.path_norm(entry.file).local is None:
        return ""
    return "heat-map/index.html#fn=" + html_escape(quote(function, safe="/-_.!~*'()"))


def file_read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError as error:
        print(f"warning: {path}: {error}", file=sys.stderr)
        return f"(missing: {path})"


def functions_table(profile: callgrind.Profile) -> str:
    total = profile.value(profile.totals(), EVENT) or 1
    ranked = sorted((FunctionCost(profile.value(costs, EVENT), function)
                     for function, costs in profile.function_self.items() if profile.value(costs, EVENT) > 0),
                    key=lambda t: (-t.cost, t.function))[:TOP]
    max_pct = 100.0 * ranked[0].cost / total if ranked else 1.0
    function_calls = {function: sum(tally.count for tally in callers.values())
                      for function, callers in profile.callers.items()}
    calls_total = sum(function_calls.values()) or 1
    calls_max_pct = 100.0 * max(function_calls.values(), default=0) / calls_total
    columns = [Column("#", "rank", numeric=True),
               Column("% self", f"share of all {EVENT} spent in the function itself, not in what it calls", numeric=True),
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
        href = entry_link(profile, ranked_function.function)
        by_caller_sorted = sorted(by_caller.items(), key=lambda pair: (-pair[1], pair[0]))
        who = ", ".join(f"{caller_name} ({theme.num_pct(100.0 * count / call_count)})"
                        for caller_name, count in by_caller_sorted)

        def caller_html(caller_name: str, count: int) -> str:
            caller_href = entry_link(profile, caller_name)
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
    return theme.table_render("report.functions", columns, rows, fill=True)


def log_block(path: str) -> str:
    lines = file_read_text(path).rstrip().split("\n")[LOG_SKIP_LINES:]
    text = "\n".join(PID_PREFIX.sub("", line) for line in lines)
    return f'<div class="tbl"><pre class="logbox">{html_escape(text)}</pre></div>'


def log_section(paths: Sequence[str]) -> str:
    if not paths:
        return ""
    body = ""
    for path in paths:
        if len(paths) > 1:
            body += f"<p>{html_escape(os.path.basename(path))}</p>"
        body += log_block(path)
    return '<details class="sec"><summary><h2>valgrind log</h2></summary>' + body + "</details>"


def header_parse_pairs(items: Sequence[str]) -> list[Header]:
    out: list[Header] = []
    for item in items:
        if "=" not in item:
            sys.exit(f"error: --header expects LABEL=VALUE, got {item!r}")
        label, _, value = item.partition("=")
        out.append(Header(label.strip(), value))
    return out


def header_read_file(path: str) -> list[Header]:
    lines = [line for line in file_read_text(path).splitlines() if line.strip() and "=" in line]
    return header_parse_pairs(lines)


def header_blocks_render(key: str, blocks: Sequence[HeaderBlock]) -> str:
    body = ""
    for index, block in enumerate(blocks):
        if not block.pairs:
            continue
        body += f"<h2>{html_escape(block.label)}</h2>" + header_table(f"{key}.{index}", block.pairs)
    return body


def header_parse_blocks(items: Sequence[str]) -> list[HeaderBlock]:
    out: list[HeaderBlock] = []
    for item in items:
        if "=" not in item:
            sys.exit(f"error: --header-block expects LABEL=FILE, got {item!r}")
        label, _, path = item.partition("=")
        out.append(HeaderBlock(label.strip(), header_read_file(path)))
    return out


def header_table(key: str, pairs: Sequence[Header]) -> str:
    if not pairs:
        return ""
    rows: list[list[CellOrText]] = [[Cell(pair.label, cls="dim"), pair.value] for pair in pairs]
    return theme.table_render(key, [Column("label"), Column("value", clip=100)], rows, header=False)


def page_write(path: str, page: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(page)
    print(f"wrote {path} ({len(page.encode('utf-8')):,} bytes)", file=sys.stderr)


def rawdata_section(paths: Sequence[str], out_dir: str) -> str:
    if not paths:
        return ""
    items = "".join(f'<li><a href="{html_escape(os.path.relpath(path, out_dir))}">'
                    f'{html_escape(os.path.basename(path))}</a></li>' for path in paths)
    return f'<details class="sec"><summary><h2>raw data</h2></summary><ul class="rawdata">{items}</ul></details>'


def report_page(args: TestArgs, views: Sequence[View], heading: str, table: str) -> None:
    links = [StripLink("", "summary", "#", args.test)] + \
        [StripLink(view.key, view.label, view.path, f"{args.test} / {view.label}") for view in views]
    body = strip_render(args.test, links, help_href=args.help_href)
    out_dir = os.path.dirname(os.path.abspath(args.output))
    body += '<main id="home"><div class="page">' + header_table("report.header", header_parse_pairs(args.header))
    if not args.no_log:
        body += log_section(args.log)
    body += rawdata_section(args.raw_data, out_dir)
    body += f"<h2>{heading}</h2>" + table
    body += '</div></main><iframe id="view" hidden title="report page"></iframe>'
    page_write(args.output, theme.page_document(args.test, body, extra_js=FRAME_JS, body_class="frame"))


def report_test(args: TestArgs) -> None:
    profile = callgrind.profile_load(args.callgrind_file)
    report_page(args, VIEWS, f"top {TOP} functions by self", functions_table(profile))


def overview_page(args: OverviewArgs, tests: Sequence[TestDirectory], columns: Sequence[Column],
                  rows: Sequence[Sequence[CellOrText]]) -> None:
    links = [StripLink("", "overview", "#", "overview")] + \
        [StripLink(test.name, test.name, f"{test.name}/index.html", test.name, frame=True) for test in tests]
    body = strip_render("overview", links)
    pairs = header_parse_pairs(args.header) + (header_read_file(args.header_file) if args.header_file else [])
    body = body + '<main id="home"><div class="page">' + header_table("overview.header", pairs)
    body += header_blocks_render("overview.block", header_parse_blocks(args.header_block))
    body += "<h2>test suites</h2>" + theme.table_render("overview.tests", columns, rows)
    body += '</div></main><iframe id="view" hidden title="report page"></iframe>'
    page_write(args.output, theme.page_document("overview", body, extra_js=FRAME_JS, body_class="frame"))


def overview_tests(args: OverviewArgs) -> list[TestDirectory]:
    out_dir = os.path.dirname(os.path.abspath(args.output))
    tests = [TestDirectory(name, os.path.join(out_dir, name)) for name in args.test]
    tests.sort()
    return tests


def report_overview(args: OverviewArgs) -> None:
    tests = overview_tests(args)
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
    overview_page(args, tests, columns, rows)


def report_timing(args: TimingArgs) -> None:
    body = '<div class="page">' + header_table("timing.header", header_parse_pairs(args.header))
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
                     f'data-title="{html_escape(link.title)}"{" data-frame=1" if link.frame else ""}>'
                     f'{html_escape(link.label)}</a>')
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


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    test_parser = subparsers.add_parser("test", help="one perf test's index page")
    test_parser.add_argument("callgrind_file", nargs="+",
                             help="callgrind output file(s); several are merged into one profile")
    test_parser.add_argument("-o", "--output", required=True)
    test_parser.add_argument("--test", required=True, help="the page's title")
    test_parser.add_argument("--raw-data", action="append", default=[], metavar="FILE",
                             help="callgrind trace file to link (repeatable); listed relative to -o")
    test_parser.add_argument("--log", action="append", default=[], help="valgrind log to include (repeatable)")
    test_parser.add_argument("--no-log", action="store_true",
                             help="omit the valgrind log section even if --log was given")
    test_parser.add_argument("--help-href", default="README.md",
                             help="the strip's 'help' target, relative to this page (default: README.md; "
                                  "a per-test page under an overview needs ../README.md)")
    test_parser.add_argument("--diff", action="store_true",
                             help="the callgrind file is a callgrind_diff.py delta: rank by |change|, print "
                                  "signed numbers, and drop the views a diff has no data for")
    test_parser.add_argument("--header", action="append", metavar="LABEL=VALUE", default=[])

    timing_parser = subparsers.add_parser("timing", help="the native timing run page")
    timing_parser.add_argument("-o", "--output", required=True)
    timing_parser.add_argument("--test", required=True)
    timing_parser.add_argument("--output-file", required=True, help="the run's captured output")
    timing_parser.add_argument("--header", action="append", metavar="LABEL=VALUE", default=[])

    overview_parser = subparsers.add_parser("overview", help="the page over several tests")
    overview_parser.add_argument("-o", "--output", required=True)
    overview_parser.add_argument("--test", action="append", metavar="NAME", required=True,
                                 help="a test, whose report directory sits next to the output (repeatable)")
    overview_parser.add_argument("--header", action="append", metavar="LABEL=VALUE", default=[])
    overview_parser.add_argument("--header-file", default="", metavar="FILE",
                                 help="a file of LABEL=VALUE lines, appended to the --header rows; any other "
                                      "line (a MANIFEST.txt version line) is ignored")
    overview_parser.add_argument("--header-block", action="append", metavar="LABEL=FILE", default=[],
                                 help="a further header table under its own heading, read from such a file "
                                      "(repeatable)")
    overview_parser.add_argument("--diff", action="store_true",
                                 help="the reports are callgrind_diff.py deltas: summarize each test's change "
                                      "instead of its native timing, which a diff does not have")

    namespace = parser.parse_args()
    if namespace.cmd == "test":
        test_args = TestArgs(callgrind_file=namespace.callgrind_file, output=namespace.output, test=namespace.test,
                             raw_data=namespace.raw_data, log=namespace.log, no_log=namespace.no_log,
                             help_href=namespace.help_href, diff=namespace.diff, header=namespace.header)
        (diff_report_test if namespace.diff else report_test)(test_args)
    elif namespace.cmd == "timing":
        report_timing(TimingArgs(output=namespace.output, test=namespace.test,
                                 output_file=namespace.output_file, header=namespace.header))
    else:
        overview_args = OverviewArgs(output=namespace.output, test=namespace.test, header=namespace.header,
                                     header_file=namespace.header_file, header_block=namespace.header_block,
                                     diff=namespace.diff)
        (diff_report_overview if namespace.diff else report_overview)(overview_args)


if __name__ == "__main__":
    main()
