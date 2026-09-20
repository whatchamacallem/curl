#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Sequence
from typing import NamedTuple
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind
import callgrind_diff
import theme
from theme import Cell, CellOrText, Column, html_escape

# The event the summary tables rank and colour by.
_EVENT = "Ir"

# The script every framing level runs, deciding what it is by whether it has
# a parent. Named exactly this: check_js.py looks it up by name.
FRAME_JS = """\

(function () {
  const bar = document.getElementById("bar");
  const home = document.getElementById("home");
  const view = document.getElementById("view");
  const titleElement = document.getElementById("title");
  const links = [...bar.querySelectorAll("a[data-view]")];
  const util = document.getElementById("util");
  const framed = window.parent !== window;
  let page = "", state = "", title = titleElement.textContent;
  function setTitle(newTitle) {
    title = newTitle;
    titleElement.textContent = framed ? "" : newTitle;
    document.title = newTitle;
    if (!framed) return;
    window.parent.postMessage({ theme: "title", title: newTitle }, "*");
  }

  function parse(hash) {
    const match = /^#([\\w-]*)(?:\\/(.*))?$/.exec(hash || "");
    return match ? [match[1], match[2] ? "#" + match[2] : ""] : ["", ""];
  }
  const build = (key, sub) =>
    key ? "#" + key + (sub ? "/" + sub.slice(1) : "") : "";
  function sync(hash) {
    if (hash !== location.hash) history.replaceState(null, "", hash || "#");
    if (framed) window.parent.postMessage({ theme: "hash", hash: hash }, "*");
  }
  function show(hash) {
    const [key, sub] = parse(hash);
    const link = links.find(anchor => anchor.dataset.view === key);
    const current = link || links[0];
    for (const anchor of links) {
      anchor.classList.toggle("on", anchor === current);
    }
    setTitle(current.dataset.title);
    util.hidden = !framed && !!(link && key && link.dataset.frame);
    if (!link || !key) {
      view.hidden = true; home.hidden = false;
      window.Theme.relayout(home);
      sync(""); return;
    }
    const href = link.getAttribute("href");
    if (href !== page || sub !== state) {
      view.contentWindow.location.replace(href + (sub || "#"));
    } else view.contentWindow.postMessage("theme:title?", "*");
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
    if (!anchor || anchor === resetCols || anchor.target) return;
    if (event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (event.button) return;
    const href = anchor.getAttribute("href");
    const hash = anchor.dataset.view != null
      ? build(anchor.dataset.view, "") : hashFor(href);
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

# Valgrind's own preamble, dropped from the log a page shows.
_LOG_SKIP_LINES = 9

# The "curl.se/perf" link in every page's util block.
_PERF_CHART = "https://curl.se/perf/index.html"

# Valgrind's "==1234== " line prefix, stripped so the log reads as output.
_PID_PREFIX = re.compile(r"^==\d+==\s?")

# How much of a long symbol a column shows before it clips.
_SYMBOL_CHARS = 20

# A "Something: 1.23 ms" line of the perf log, which is the only valid speed
# number -- callgrind's wall clock never is.
_TIME_LINE = re.compile(
    r"^(\s*[A-Za-z][\w/ ]*:\s*)"
    r"(-?\d+(?:\.\d+)?)\s*(usecs?|us|msecs?|ms|nsecs?|ns|secs?|s)\s*$",
    re.I | re.M,
)

# What each of those suffixes is in seconds.
_TIME_SCALE: dict[str, float] = {
    "usec": 1e-6,
    "usecs": 1e-6,
    "us": 1e-6,
    "msec": 1e-3,
    "msecs": 1e-3,
    "ms": 1e-3,
    "nsec": 1e-9,
    "nsecs": 1e-9,
    "ns": 1e-9,
    "sec": 1.0,
    "secs": 1.0,
    "s": 1.0,
}

# How many functions the summary's top table lists.
_TOP = 50


# BuildReport - Writes the overview page and every test's summary page, and
# the strip of links that frames the views.
class BuildReport:
    # CallerDelta - How one caller's calls into one function changed, read back
    # from callgrind_diff.py's sidecar.
    class CallerDelta(NamedTuple):
        # who does the calling
        function: str
        # how many more (or fewer) times it called
        count_: int
        # how much more (or less) those calls cost
        cost: int

    # FunctionCost - One function and one number, for ranking the top table.
    class FunctionCost(NamedTuple):
        # what it is ranked on
        cost: int
        # whose cost it is
        function: str

    # Header - One LABEL=VALUE row above a page's content. Not the heat map's
    # MetaModel, which is its data rather than its provenance.
    class Header(NamedTuple):
        # the left column
        label: str
        # the right column
        value: str

    # HeaderBlock - A named group of those rows, e.g. "baseline".
    class HeaderBlock(NamedTuple):
        # the heading above the group
        label: str
        # the rows themselves
        pairs: list[BuildReport.Header]

    # OverviewArgs - What the overview page is built from.
    class OverviewArgs(NamedTuple):
        # where the page goes
        output: str
        # each test as "name=directory"
        test: list[str]
        # extra LABEL=VALUE rows
        header: list[str]
        # a file of the same rows
        header_file: str
        # grouped rows as "block:LABEL=VALUE"
        header_block: list[str]
        # build a diff overview: no native timing
        diff: bool

    # StripLink - One link in a page's top strip.
    class StripLink(NamedTuple):
        # what the URL hash calls it
        key: str
        # what the link says
        label: str
        # where it points
        href: str
        # its hover text
        title: str
        # load it into the frame rather than navigating
        frame: bool = False

    # TestArgs - Everything one test's summary page is built from. Each
    # optional log renders a section only when it is given.
    class TestArgs(NamedTuple):
        # the callgrind file(s), merged into one profile
        callgrind_file: list[str]
        # where the page goes
        output: str
        # the test's name
        test: str
        # raw files to link, if any
        raw_data: list[str]
        # the valgrind log(s) to embed, if any
        log: list[str]
        # the perf log to embed, if any
        perf_log: str
        # the trace log to embed -- also what gates the flame graph link
        trace_log: str
        # embed no log at all
        no_log: bool
        # where the "help" link points
        help_href: str
        # the callgrind file is a delta
        diff: bool
        # extra LABEL=VALUE rows
        header: list[str]
        # callgrind_diff.py's caller sidecar, for the diff call columns
        callers_data: str

    # TestDirectory - One test of the overview, and where its report sits.
    class TestDirectory(NamedTuple):
        # the test's name
        name: str
        # its directory, relative to the overview
        directory: str

    # View - One of the pages a test summary can frame.
    class View(NamedTuple):
        # what the URL hash calls it
        key: str
        # what the strip link says
        label: str
        # where the page sits
        path: str

    def caller_delta_cell(
        self,
        profile: callgrind.Profile,
        deltas: Sequence[BuildReport.CallerDelta],
    ) -> Cell:
        if not deltas:
            return Cell("(no recorded caller change)", cls="dim")
        parts: list[str] = []
        html_parts: list[str] = []
        for delta in deltas:
            count_text = (
                f" {theme.num_signed(delta.count_)} calls"
                if delta.count_
                else ""
            )
            text = (
                f"{theme.num_signed(delta.cost)} {delta.function}{count_text}"
            )
            parts.append(text)
            href = self.entry_link(profile, delta.function)
            label = (
                f"{theme.num_signed(delta.cost)}"
                f" {html_escape(delta.function)}"
                f"{html_escape(count_text)}"
            )
            html_parts.append(
                f'<a href="{href}">{label}</a>' if href else label
            )
        joined = ", ".join(parts)
        return Cell(joined, title=joined, html=", ".join(html_parts))

    def caller_link(
        self,
        profile: callgrind.Profile,
        caller_name: str,
        count: int,
        call_count: int,
    ) -> str:
        href = self.entry_link(profile, caller_name)
        share = theme.num_pct(100.0 * count / call_count)
        label = f"{html_escape(caller_name)} ({share})"
        return f'<a href="{href}">{label}</a>' if href else label

    def callers_data_load(
        self, path: str
    ) -> dict[str, list[BuildReport.CallerDelta]]:
        if not path:
            return {}
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
        return {
            callee: [
                BuildReport.CallerDelta(function, count, cost)
                for function, count, cost in deltas
            ]
            for callee, deltas in doc["callers"].items()
        }

    def diff_functions_table(
        self,
        profile: callgrind.Profile,
        callers_data: dict[str, list[BuildReport.CallerDelta]],
    ) -> str:
        total = (
            profile.value(callgrind_diff.profile_magnitudes(profile), _EVENT)
            or 1
        )
        ranked = sorted(
            (
                BuildReport.FunctionCost(
                    profile.value(costs, _EVENT), function
                )
                for function, costs in profile.function_self.items()
                if profile.value(costs, _EVENT) != 0
            ),
            key=lambda t: (-abs(t.cost), t.function),
        )[:_TOP]
        max_pct = 100.0 * abs(ranked[0].cost) / total if ranked else 1.0
        call_counts = {
            callee: sum(delta.count_ for delta in deltas)
            for callee, deltas in callers_data.items()
        }
        calls_magnitude = (
            sum(abs(count) for count in call_counts.values()) or 1
        )
        calls_max_pct = (
            100.0
            * max((abs(count) for count in call_counts.values()), default=0)
            / calls_magnitude
        )
        columns = [
            Column(
                "#",
                "rank by how much the function changed, largest first",
                numeric=True,
            ),
            Column(
                "% self",
                f"the function's own {_EVENT} delta, as a share of every"
                f" line's {_EVENT} change added up. + is more than the"
                " baseline, - is less",
                numeric=True,
            ),
            Column(
                "symbol",
                f"the function, first {_SYMBOL_CHARS} characters (drag"
                " the bar for more); opens the heat map at its first line",
                width=_SYMBOL_CHARS,
            ),
            Column(_EVENT, f"the signed {_EVENT} delta itself", numeric=True),
            Column(
                "calls",
                "change in how many times the function was entered",
                numeric=True,
            ),
            Column(
                "callers",
                "who its call count changed with, signed by change in"
                f" {_EVENT}. cut off at the edge, hover for all",
                grow=True,
            ),
        ]
        rows: list[list[CellOrText]] = []
        for rank, ranked_function in enumerate(ranked, 1):
            share = 100.0 * ranked_function.cost / total
            href = self.entry_link(profile, ranked_function.function)
            deltas = callers_data.get(ranked_function.function, [])
            call_count = call_counts.get(ranked_function.function, 0)
            call_share = 100.0 * call_count / calls_magnitude
            rows.append(
                [
                    str(rank),
                    Cell(
                        theme.num_signed_pct(share),
                        style=theme.heat_style(
                            theme.heat_t(share, max_pct), signed=True
                        ),
                    ),
                    Cell(
                        ranked_function.function,
                        title=ranked_function.function,
                        html=f'<a href="{href}">'
                        f"{html_escape(ranked_function.function)}</a>"
                        if href
                        else None,
                    ),
                    Cell(
                        theme.num_signed(ranked_function.cost),
                        title=f"{ranked_function.cost:+,} {_EVENT}",
                    ),
                    Cell(
                        theme.num_signed(call_count),
                        title=f"{call_count:+,} calls",
                        style=theme.heat_style(
                            theme.heat_t(call_share, calls_max_pct),
                            signed=True,
                        ),
                    )
                    if call_count
                    else "",
                    self.caller_delta_cell(profile, deltas),
                ]
            )
        return theme.table_render("report.functions", columns, rows, fill=True)

    def diff_overview(self, args: BuildReport.OverviewArgs) -> None:
        tests = self.overview_tests(args)
        columns, rows = self.diff_overview_rows(tests)
        self.overview_page(args, tests, columns, rows)

    def diff_overview_rows(
        self, tests: Sequence[BuildReport.TestDirectory]
    ) -> tuple[list[Column], list[list[CellOrText]]]:
        columns = [
            Column("one report per test"),
            Column(_EVENT, f"the whole run's {_EVENT} delta", numeric=True),
            Column(
                "% of change",
                f"that delta against every function's {_EVENT} change"
                " added up",
                numeric=True,
            ),
            Column(
                "functions changed",
                f"functions whose {_EVENT} moved at all",
                numeric=True,
            ),
        ]
        rows: list[list[CellOrText]] = []
        for test in tests:
            raw_dir = os.path.join(test.directory, "raw")
            files = (
                sorted(
                    os.path.join(raw_dir, name) for name in os.listdir(raw_dir)
                )
                if os.path.isdir(raw_dir)
                else []
            )
            link = Cell(
                test.name,
                html=f'<a href="{html_escape(test.name)}/index.html">'
                f"{html_escape(test.name)}</a>",
            )
            if not files:
                rows.append([link, "", "", ""])
                continue
            profile = callgrind.profile_load(files)
            delta = profile.value(profile.totals(), _EVENT)
            changed = sum(
                1
                for costs in profile.function_self.values()
                if profile.value(costs, _EVENT) != 0
            )
            magnitude = profile.value(
                callgrind_diff.profile_magnitudes(profile), _EVENT
            )
            rows.append(
                [
                    link,
                    Cell(
                        theme.num_signed(delta), title=f"{delta:+,} {_EVENT}"
                    ),
                    theme.num_signed_pct(100.0 * delta / magnitude)
                    if magnitude
                    else "",
                    theme.num_human(changed),
                ]
            )
        return columns, rows

    def diff_test(self, args: BuildReport.TestArgs) -> None:
        profile = callgrind.profile_load(args.callgrind_file)
        callers_data = self.callers_data_load(args.callers_data)
        self.report_page(
            args,
            [_HEAT_VIEW],
            f"top {_TOP} functions by change in self",
            self.diff_functions_table(profile, callers_data),
        )

    def entry_link(self, profile: callgrind.Profile, function: str) -> str:
        entry = profile.function_entry.get(function)
        if (
            entry is None
            or not entry.line
            or callgrind.path_norm(entry.file).local is None
        ):
            return ""
        return "heat-map/index.html#fn=" + html_escape(
            quote(function, safe="/-_.!~*'()")
        )

    def file_read(self, path: str) -> str:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                return handle.read()
        except OSError as error:
            print(f"warning: {path}: {error}", file=sys.stderr)
            return f"(missing: {path})"

    def functions_table(self, profile: callgrind.Profile) -> str:
        total = profile.value(profile.totals(), _EVENT) or 1
        ranked = sorted(
            (
                BuildReport.FunctionCost(
                    profile.value(costs, _EVENT), function
                )
                for function, costs in profile.function_self.items()
                if profile.value(costs, _EVENT) > 0
            ),
            key=lambda t: (-t.cost, t.function),
        )[:_TOP]
        max_pct = 100.0 * ranked[0].cost / total if ranked else 1.0
        function_calls = {
            function: sum(tally.count for tally in callers.values())
            for function, callers in profile.callers.items()
        }
        calls_total = sum(function_calls.values()) or 1
        calls_max_pct = (
            100.0 * max(function_calls.values(), default=0) / calls_total
        )
        columns = [
            Column("#", "rank", numeric=True),
            Column(
                "% self",
                f"share of all {_EVENT} spent in the function itself,"
                " not in what it calls",
                numeric=True,
            ),
            Column(
                "symbol",
                f"the function, first {_SYMBOL_CHARS} characters (drag"
                " the bar for more). opens the heat map at its first line",
                width=_SYMBOL_CHARS,
            ),
            Column(
                _EVENT,
                f"the function's own {_EVENT}, self cost only",
                numeric=True,
            ),
            Column("calls", "times the function was entered", numeric=True),
            Column(
                "callers",
                "who called it, with the share of those calls. cut off"
                " at the edge, hover for all",
                grow=True,
            ),
        ]
        rows: list[list[CellOrText]] = []
        for rank, ranked_function in enumerate(ranked, 1):
            by_caller: dict[str, int] = {}
            for caller, tally in profile.callers.get(
                ranked_function.function, {}
            ).items():
                by_caller[caller.function] = (
                    by_caller.get(caller.function, 0) + tally.count
                )
            call_count = sum(by_caller.values())
            share = 100.0 * ranked_function.cost / total
            href = self.entry_link(profile, ranked_function.function)
            by_caller_sorted = sorted(
                by_caller.items(), key=lambda pair: (-pair[1], pair[0])
            )
            who = ", ".join(
                f"{caller_name} ({theme.num_pct(100.0 * count / call_count)})"
                for caller_name, count in by_caller_sorted
            )
            who_html = ", ".join(
                self.caller_link(profile, caller_name, count, call_count)
                for caller_name, count in by_caller_sorted
            )
            rows.append(
                [
                    str(rank),
                    Cell(
                        theme.num_pct(share),
                        style=theme.heat_style(theme.heat_t(share, max_pct)),
                    ),
                    Cell(
                        ranked_function.function,
                        title=ranked_function.function,
                        html=f'<a href="{href}">'
                        f"{html_escape(ranked_function.function)}</a>"
                        if href
                        else None,
                    ),
                    Cell(
                        theme.num_human(ranked_function.cost),
                        title=f"{ranked_function.cost:,} {_EVENT}",
                    ),
                    Cell(
                        theme.num_human(call_count),
                        title=f"{call_count:,} calls",
                        style=theme.heat_style(
                            theme.heat_t(
                                100.0 * call_count / calls_total, calls_max_pct
                            )
                        ),
                    )
                    if call_count
                    else "",
                    Cell(who, title=who, html=who_html)
                    if who
                    else Cell("(no recorded caller)", cls="dim"),
                ]
            )
        return theme.table_render("report.functions", columns, rows, fill=True)

    def header_blocks_render(
        self, key: str, blocks: Sequence[BuildReport.HeaderBlock]
    ) -> str:
        body = ""
        for index, block in enumerate(blocks):
            if not block.pairs:
                continue
            body += f"<h2>{html_escape(block.label)}</h2>" + self.header_table(
                f"{key}.{index}", block.pairs
            )
        return body

    def header_parse_blocks(
        self, items: Sequence[str]
    ) -> list[BuildReport.HeaderBlock]:
        out: list[BuildReport.HeaderBlock] = []
        for item in items:
            if "=" not in item:
                sys.exit(
                    f"error: --header-block expects LABEL=FILE, got {item!r}"
                )
            label, _, path = item.partition("=")
            out.append(
                BuildReport.HeaderBlock(
                    label.strip(), self.header_read_file(path)
                )
            )
        return out

    def header_parse_pairs(
        self, items: Sequence[str]
    ) -> list[BuildReport.Header]:
        out: list[BuildReport.Header] = []
        for item in items:
            if "=" not in item:
                sys.exit(f"error: --header expects LABEL=VALUE, got {item!r}")
            label, _, value = item.partition("=")
            out.append(BuildReport.Header(label.strip(), value))
        return out

    def header_read_file(self, path: str) -> list[BuildReport.Header]:
        lines = [
            line
            for line in self.file_read(path).splitlines()
            if line.strip() and "=" in line
        ]
        return self.header_parse_pairs(lines)

    def header_table(
        self, key: str, pairs: Sequence[BuildReport.Header]
    ) -> str:
        if not pairs:
            return ""
        rows: list[list[CellOrText]] = [
            [Cell(pair.label, cls="dim"), pair.value] for pair in pairs
        ]
        return theme.table_render(
            key,
            [Column("label"), Column("value", grow=True)],
            rows,
            fill=True,
            header=False,
        )

    def log_block(self, path: str) -> str:
        lines = self.file_read(path).rstrip().split("\n")[_LOG_SKIP_LINES:]
        text = "\n".join(_PID_PREFIX.sub("", line) for line in lines)
        return (
            f'<div class="tbl"><pre class="logbox">{html_escape(text)}'
            "</pre></div>"
        )

    def log_section(self, paths: Sequence[str]) -> str:
        if not paths:
            return ""
        body = ""
        for path in paths:
            if len(paths) > 1:
                body += f"<p>{html_escape(os.path.basename(path))}</p>"
            body += self.log_block(path)
        return (
            '<details class="sec"><summary><h2>valgrind log</h2></summary>'
            + body
            + "</details>"
        )

    def output_section(self, title: str, path: str) -> str:
        if not path:
            return ""
        output = self.time_humanize(self.file_read(path).rstrip())
        body = (
            f'<div class="tbl"><pre class="logbox">{html_escape(output)}'
            "</pre></div>"
        )
        return (
            f'<details class="sec"><summary><h2>{title}</h2></summary>'
            + body
            + "</details>"
        )

    def overview(self, args: BuildReport.OverviewArgs) -> None:
        tests = self.overview_tests(args)
        keys: list[str] = []
        numbers: dict[str, dict[str, str]] = {}
        for test in tests:
            values: dict[str, str] = {}
            for line in self.file_read(
                os.path.join(test.directory, "perf-tool", "output.txt")
            ).splitlines():
                match = re.match(r"^([A-Za-z][^:]{0,30}):\s+(.+?)\s*$", line)
                if match:
                    values[match.group(1)] = self.value_humanize(
                        match.group(1), match.group(2)
                    )
                    if match.group(1) not in keys:
                        keys.append(match.group(1))
            numbers[test.name] = values
        columns = [Column("report")] + [
            Column(key, numeric=True) for key in keys
        ]
        rows: list[list[CellOrText]] = [
            [
                Cell(
                    test.name,
                    html=f'<a href="{html_escape(test.name)}/index.html">'
                    f"{html_escape(test.name)}</a>",
                )
            ]
            + [numbers[test.name].get(key, "") for key in keys]
            for test in tests
        ]
        self.overview_page(args, tests, columns, rows)

    def overview_page(
        self,
        args: BuildReport.OverviewArgs,
        tests: Sequence[BuildReport.TestDirectory],
        columns: Sequence[Column],
        rows: Sequence[Sequence[CellOrText]],
    ) -> None:
        links = [BuildReport.StripLink("", "overview", "#", "overview")] + [
            BuildReport.StripLink(
                test.name,
                test.name,
                f"{test.name}/index.html",
                test.name,
                frame=True,
            )
            for test in tests
        ]
        body = self.strip_render("overview", links)
        pairs = self.header_parse_pairs(args.header) + (
            self.header_read_file(args.header_file) if args.header_file else []
        )
        body = (
            body
            + '<main id="home"><div class="page">'
            + self.header_table("overview.header", pairs)
        )
        body += self.header_blocks_render(
            "overview.block", self.header_parse_blocks(args.header_block)
        )
        body += "<h2>test suites</h2>" + theme.table_render(
            "overview.tests", columns, rows
        )
        body += (
            '</div></main><iframe id="view" hidden'
            ' title="report page"></iframe>'
        )
        self.page_write(
            args.output,
            theme.page_document(
                "overview", body, extra_js=FRAME_JS, body_class="frame"
            ),
        )

    def overview_tests(
        self, args: BuildReport.OverviewArgs
    ) -> list[BuildReport.TestDirectory]:
        out_dir = os.path.dirname(os.path.abspath(args.output))
        tests = [
            BuildReport.TestDirectory(name, os.path.join(out_dir, name))
            for name in args.test
        ]
        tests.sort()
        return tests

    def page_write(self, path: str, page: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(page)
        print(
            f"wrote {path} ({len(page.encode('utf-8')):,} bytes)",
            file=sys.stderr,
        )

    def rawdata_section(self, paths: Sequence[str], out_dir: str) -> str:
        if not paths:
            return ""
        items = "".join(
            f'<li><a href="{html_escape(os.path.relpath(path, out_dir))}"'
            ' target="_blank">'
            f"{html_escape(os.path.basename(path))}</a></li>"
            for path in paths
        )
        return (
            '<details class="sec"><summary><h2>raw data</h2></summary>'
            f'<ul class="rawdata">{items}</ul></details>'
        )

    def report_page(
        self,
        args: BuildReport.TestArgs,
        views: Sequence[BuildReport.View],
        heading: str,
        table: str,
    ) -> None:
        links = [BuildReport.StripLink("", "summary", "#", args.test)] + [
            BuildReport.StripLink(
                view.key, view.label, view.path, f"{args.test} / {view.label}"
            )
            for view in views
        ]
        body = self.strip_render(args.test, links, help_href=args.help_href)
        out_dir = os.path.dirname(os.path.abspath(args.output))
        body += '<main id="home"><div class="page">' + self.header_table(
            "report.header", self.header_parse_pairs(args.header)
        )
        body += self.output_section("perf log", args.perf_log)
        body += self.output_section("trace log", args.trace_log)
        if not args.no_log:
            body += self.log_section(args.log)
        body += self.rawdata_section(args.raw_data, out_dir)
        body += f"<h2>{heading}</h2>" + table
        body += (
            '</div></main><iframe id="view" hidden'
            ' title="report page"></iframe>'
        )
        self.page_write(
            args.output,
            theme.page_document(
                args.test, body, extra_js=FRAME_JS, body_class="frame"
            ),
        )

    def strip_render(
        self,
        title: str,
        links: Sequence[BuildReport.StripLink],
        help_href: str = "README.md",
    ) -> str:
        separator = '<span class="sep">|</span>'
        parts = [f'<b class="title" id="title">{html_escape(title)}</b>']
        for index, link in enumerate(links):
            if index:
                parts.append(separator)
            parts.append(
                f'<a href="{html_escape(link.href)}"'
                f' data-view="{html_escape(link.key)}"'
                f' data-title="{html_escape(link.title)}"'
                f"{' data-frame=1' if link.frame else ''}>"
                f"{html_escape(link.label)}</a>"
            )
        parts.append('<span class="sp"></span>')
        parts.append('<span class="util" id="util">')
        parts.append('<a href="#" id="reset-cols">reset columns</a>')
        parts.append(separator)
        parts.append(
            f'<a href="{html_escape(help_href)}" target="_blank">help</a>'
        )
        parts.append(separator)
        parts.append(
            f'<a href="{_PERF_CHART}" target="_blank" rel="noopener">'
            "curl.se/perf</a>"
        )
        parts.append("</span>")
        return f'<nav id="bar" class="strip">{"".join(parts)}</nav>'

    def test(self, args: BuildReport.TestArgs) -> None:
        profile = callgrind.profile_load(args.callgrind_file)
        views = [_FLAME_VIEW, _HEAT_VIEW] if args.trace_log else [_HEAT_VIEW]
        self.report_page(
            args,
            views,
            f"top {_TOP} functions by self",
            self.functions_table(profile),
        )

    def time_humanize(self, text: str) -> str:
        def one(match: re.Match[str]) -> str:
            scale = _TIME_SCALE.get(match.group(3).lower())
            return (
                match.group(0)
                if scale is None
                else match.group(1)
                + theme.num_time(float(match.group(2)) * scale)
            )

        return _TIME_LINE.sub(one, text)

    def value_humanize(self, label: str, value: str) -> str:
        line = self.time_humanize(f"{label}: {value}")
        return line.split(": ", 1)[1] if line != f"{label}: {value}" else value


# The flame graph view, linked only where a trace was actually recorded.
_FLAME_VIEW = BuildReport.View(
    "flame-graph", "flame graph", "flame-graph/index.html"
)

# The heat map view, which every test has.
_HEAT_VIEW = BuildReport.View("heat-map", "heat map", "heat-map/index.html")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    test_parser = subparsers.add_parser(
        "test", help="one perf test's index page"
    )
    test_parser.add_argument(
        "callgrind_file",
        nargs="+",
        help="callgrind output file(s). several are merged into one profile",
    )
    test_parser.add_argument("-o", "--output", required=True)
    test_parser.add_argument("--test", required=True, help="the page's title")
    test_parser.add_argument(
        "--raw-data",
        action="append",
        default=[],
        metavar="FILE",
        help="raw data file to link (repeatable). listed relative to -o",
    )
    test_parser.add_argument(
        "--log",
        action="append",
        default=[],
        help="valgrind log to include (repeatable)",
    )
    test_parser.add_argument(
        "--perf-log",
        default="",
        metavar="FILE",
        help="the perf tool's captured stdout, shown in a collapsed"
        " 'perf log' section",
    )
    test_parser.add_argument(
        "--trace-log",
        default="",
        metavar="FILE",
        help="the native trace run's captured output"
        " (flame-graph/output.txt), shown in a collapsed 'trace log'"
        " section; without it the page has no flame graph link",
    )
    test_parser.add_argument(
        "--no-log",
        action="store_true",
        help="omit the valgrind log section even if --log was given",
    )
    test_parser.add_argument(
        "--help-href",
        default="README.md",
        help="the strip's 'help' target, relative to this page (default:"
        " README.md. a per-test page under an overview needs"
        " ../README.md)",
    )
    test_parser.add_argument(
        "--diff",
        action="store_true",
        help="the callgrind file is a callgrind_diff.py delta: rank by"
        " |change|, print signed numbers, and drop the views a diff has"
        " no data for",
    )
    test_parser.add_argument(
        "--header", action="append", metavar="LABEL=VALUE", default=[]
    )
    test_parser.add_argument(
        "--callers-data",
        default="",
        metavar="FILE",
        help="--diff only: a callgrind_diff.py --callers-output JSON"
        " file, for the summary table's calls/callers columns",
    )

    overview_parser = subparsers.add_parser(
        "overview", help="the page over several tests"
    )
    overview_parser.add_argument("-o", "--output", required=True)
    overview_parser.add_argument(
        "--test",
        action="append",
        metavar="NAME",
        required=True,
        help="a test, whose report directory sits next to the output"
        " (repeatable)",
    )
    overview_parser.add_argument(
        "--header", action="append", metavar="LABEL=VALUE", default=[]
    )
    overview_parser.add_argument(
        "--header-file",
        default="",
        metavar="FILE",
        help="a file of LABEL=VALUE lines, appended to the --header"
        " rows. any other line (a MANIFEST.txt version line) is"
        " ignored",
    )
    overview_parser.add_argument(
        "--header-block",
        action="append",
        metavar="LABEL=FILE",
        default=[],
        help="a further header table under its own heading, read from"
        " such a file (repeatable)",
    )
    overview_parser.add_argument(
        "--diff",
        action="store_true",
        help="the reports are callgrind_diff.py deltas: summarize each"
        " test's change instead of its native timing, which a diff does"
        " not have",
    )

    namespace = parser.parse_args()
    report = BuildReport()
    if namespace.cmd == "test":
        test_args = BuildReport.TestArgs(
            callgrind_file=namespace.callgrind_file,
            output=namespace.output,
            test=namespace.test,
            raw_data=namespace.raw_data,
            log=namespace.log,
            perf_log=namespace.perf_log,
            trace_log=namespace.trace_log,
            no_log=namespace.no_log,
            help_href=namespace.help_href,
            diff=namespace.diff,
            header=namespace.header,
            callers_data=namespace.callers_data,
        )
        (report.diff_test if namespace.diff else report.test)(test_args)
    else:
        overview_args = BuildReport.OverviewArgs(
            output=namespace.output,
            test=namespace.test,
            header=namespace.header,
            header_file=namespace.header_file,
            header_block=namespace.header_block,
            diff=namespace.diff,
        )
        (report.diff_overview if namespace.diff else report.overview)(
            overview_args
        )


if __name__ == "__main__":
    main()
