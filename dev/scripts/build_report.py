#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections.abc import Sequence
from typing import NamedTuple
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind
import theme
from theme import Cell, CellOrText, Column, html_escape

# What callgrind_diff.py's synthesized callers diff is named, next to the
# delta it describes.
_CALLERS_SUFFIX = ".callers.json"

# The event the diff tables rank and colour by, and the one their baselines
# are read in. It stays a recorded event: the synthesized callers diff locates
# a baseline by slot in the cost vector, which a derived event like CEst has
# none of.
_DIFF_EVENT = "Ir"

# The event the non-diff summary's top table ranks and colours by. Derived,
# so a profile missing its inputs falls back -- see event_of().
_EVENT = "CEst"

# What the non-diff top table ranks by when the profile cannot derive _EVENT.
_EVENT_FALLBACK = "Ir"

# The diff share that paints the hottest colour. A change the size of the
# thing's own baseline is as lit as a cell gets.
_FULL_HEAT_PCT = 100.0

# The script every framing level runs, deciding what it is by whether it has
# a parent, read from scripts/frame.js at generate time.
FRAME_JS = theme.theme_asset("frame.js")

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
    # from callgrind_diff.py's synthesized callers diff.
    class CallerDelta(NamedTuple):
        # who does the calling
        function: str
        # how many more (or fewer) times it called
        count_: int
        # how much more (or less) those calls cost
        cost: int

    # CallersData - callgrind_diff.py's synthesized callers diff, read back:
    # the call graph a delta file cannot carry, and the baseline every share
    # divides by.
    class CallersData(NamedTuple):
        # per function, who called it and how that changed
        callers: dict[str, list[BuildReport.CallerDelta]]
        # per function, its baseline cost in the synthesized callers diff's
        # event
        baseline: dict[str, int]
        # per function, how many times the baseline called it
        baseline_calls: dict[str, int]

    # FunctionCost - One function and one number, for ranking the top table.
    class FunctionCost(NamedTuple):
        # what it is ranked on
        cost: int
        # whose cost it is
        function: str

    # ManifestBlock - A named group of those rows, e.g. "baseline".
    class ManifestBlock(NamedTuple):
        # the heading above the group
        label: str
        # the rows themselves
        pairs: list[BuildReport.ManifestRow]

    # ManifestRow - One LABEL=VALUE row above a page's content. Not the heat
    # map's HeatMapTotals, which is its data rather than where it came from.
    class ManifestRow(NamedTuple):
        # the left column
        label: str
        # the right column
        value: str

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
        # callgrind_diff.py's synthesized callers diff, for the call columns
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

    # The baseline run's total in this page's event, read from the synthesized
    # callers diff left beside the delta file. None when there is none to
    # divide by, which is what an empty share cell means.
    def baseline_total_load(self, paths: Sequence[str]) -> int | None:
        total = 0
        found = False
        for path in paths:
            with open(path, encoding="utf-8") as handle:
                doc = json.load(handle)
            events: list[str] = doc.get("events", [])
            costs: list[int] = doc.get("baselineTotal", [])
            slot = events.index(_DIFF_EVENT) if _DIFF_EVENT in events else 0
            total += costs[slot] if slot < len(costs) else 0
            found = True
        return total if found else None

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
        return Cell(joined, html=", ".join(html_parts))

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

    def callers_data_load(self, path: str) -> BuildReport.CallersData:
        if not path:
            return BuildReport.CallersData({}, {}, {})
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
        index = doc["event"]
        events: list[str] = doc.get("events", [])
        slot = events.index(index) if index in events else 0
        return BuildReport.CallersData(
            callers={
                callee: [
                    BuildReport.CallerDelta(function, count, cost)
                    for function, count, cost in deltas
                ]
                for callee, deltas in doc["callers"].items()
            },
            baseline={
                name: costs[slot] if slot < len(costs) else 0
                for name, costs in doc["baseline"].items()
                if "\n" not in name
            },
            baseline_calls=doc["baselineCalls"],
        )

    def diff_functions_table(
        self,
        profile: callgrind.Profile,
        callers_data: BuildReport.CallersData,
    ) -> str:
        ranked = sorted(
            (
                BuildReport.FunctionCost(
                    profile.value(costs, _DIFF_EVENT), function
                )
                for function, costs in profile.function_self.items()
                if profile.value(costs, _DIFF_EVENT) != 0
            ),
            key=lambda t: (-abs(t.cost), t.function),
        )[:_TOP]
        shares = [
            self.diff_share(
                cost.cost, callers_data.baseline.get(cost.function)
            )
            for cost in ranked
        ]
        max_pct = max(
            (abs(share) for share in shares if share is not None), default=1.0
        )
        call_counts = {
            callee: sum(delta.count_ for delta in deltas)
            for callee, deltas in callers_data.callers.items()
        }
        call_shares = {
            callee: self.diff_share(
                count, callers_data.baseline_calls.get(callee)
            )
            for callee, count in call_counts.items()
        }
        calls_max_pct = max(
            (
                abs(share)
                for share in call_shares.values()
                if share is not None
            ),
            default=1.0,
        )
        columns = [
            Column("#", numeric=True),
            Column("% self", numeric=True),
            Column("symbol", width=_SYMBOL_CHARS),
            Column(_DIFF_EVENT, numeric=True),
            Column("calls", numeric=True),
            Column("callers", grow=True),
        ]
        rows: list[list[CellOrText]] = []
        for rank, ranked_function in enumerate(ranked, 1):
            share = shares[rank - 1]
            href = self.entry_link(profile, ranked_function.function)
            deltas = callers_data.callers.get(ranked_function.function, [])
            call_count = call_counts.get(ranked_function.function, 0)
            call_share = call_shares.get(ranked_function.function)
            rows.append(
                [
                    str(rank),
                    Cell(
                        theme.num_signed_pct(share)
                        if share is not None
                        else "",
                        style=theme.heat_style(
                            self.diff_heat(share, max_pct), signed=True
                        )
                        if share is not None
                        else "",
                    ),
                    Cell(
                        ranked_function.function,
                        html=f'<a href="{href}">'
                        f"{html_escape(ranked_function.function)}</a>"
                        if href
                        else None,
                    ),
                    theme.num_signed(ranked_function.cost),
                    Cell(
                        theme.num_signed(call_count),
                        style=theme.heat_style(
                            self.diff_heat(call_share, calls_max_pct),
                            signed=True,
                        )
                        if call_share is not None
                        else "",
                    )
                    if call_count
                    else "",
                    self.caller_delta_cell(profile, deltas),
                ]
            )
        return theme.table_render("report.functions", columns, rows, fill=True)

    # Where a diff share sits on the heat ramp. Anything at or past its own
    # baseline is fully lit, so a line that cost 1 and moved 200K does not
    # set a scale that leaves every honest change colourless.
    def diff_heat(self, share: float, max_share: float) -> float:
        return theme.heat_t(
            math.copysign(min(abs(share), _FULL_HEAT_PCT), share),
            min(max_share, _FULL_HEAT_PCT),
        )

    def diff_overview(self, args: BuildReport.OverviewArgs) -> None:
        tests = self.overview_tests(args)
        columns, rows = self.diff_overview_rows(tests)
        self.overview_page(args, tests, columns, rows)

    def diff_overview_rows(
        self, tests: Sequence[BuildReport.TestDirectory]
    ) -> tuple[list[Column], list[list[CellOrText]]]:
        columns = [
            Column("one report per test"),
            Column(_DIFF_EVENT, numeric=True),
            Column("% of change", numeric=True),
            Column("functions changed", numeric=True),
        ]
        rows: list[list[CellOrText]] = []
        for test in tests:
            raw_dir = os.path.join(test.directory, "raw")
            names = (
                sorted(os.listdir(raw_dir)) if os.path.isdir(raw_dir) else []
            )
            files = [
                os.path.join(raw_dir, name)
                for name in names
                if not name.endswith(_CALLERS_SUFFIX)
            ]
            synthesized_callers = [
                os.path.join(raw_dir, name)
                for name in names
                if name.endswith(_CALLERS_SUFFIX)
            ]
            link = Cell(
                test.name,
                html=f'<a href="{html_escape(test.name)}/index.html">'
                f"{html_escape(test.name)}</a>",
            )
            if not files:
                rows.append([link, "", "", ""])
                continue
            profile = callgrind.profile_load(files)
            delta = profile.value(profile.totals(), _DIFF_EVENT)
            changed = sum(
                1
                for costs in profile.function_self.values()
                if profile.value(costs, _DIFF_EVENT) != 0
            )
            share = self.diff_share(
                delta, self.baseline_total_load(synthesized_callers)
            )
            rows.append(
                [
                    link,
                    theme.num_signed(delta),
                    theme.num_signed_pct(share) if share is not None else "",
                    theme.num_human(changed),
                ]
            )
        return columns, rows

    # A delta as a percentage of what the same thing cost in the baseline, so
    # a cost that went away entirely reads -100% and one that doubled +100%.
    # Something the baseline never had is +100%, all of it new. None only
    # when there is no change at all to take a share of.
    def diff_share(self, delta: int, baseline: int | None) -> float | None:
        if not baseline:
            return 100.0 if delta else None
        return 100.0 * delta / abs(baseline)

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

    # What the non-diff top table ranks by: _EVENT when the run recorded
    # everything it is derived from, else the recorded fallback. A profile
    # that cannot supply an event raises rather than scoring it zero.
    def event_of(self, profile: callgrind.Profile) -> str:
        names = profile.event_names()
        for name in (_EVENT, _EVENT_FALLBACK):
            if name in names:
                return name
        return names[0] if names else _EVENT_FALLBACK

    def file_read(self, path: str) -> str:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                return handle.read()
        except OSError as error:
            print(f"warning: {path}: {error}", file=sys.stderr)
            return f"(missing: {path})"

    def functions_table(self, profile: callgrind.Profile) -> str:
        event = self.event_of(profile)
        total = profile.value(profile.totals(), event) or 1
        ranked = sorted(
            (
                BuildReport.FunctionCost(profile.value(costs, event), function)
                for function, costs in profile.function_self.items()
                if profile.value(costs, event) > 0
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
            Column("#", numeric=True),
            Column("% self", numeric=True),
            Column("symbol", width=_SYMBOL_CHARS),
            Column(event, numeric=True),
            Column("calls", numeric=True),
            Column("callers", grow=True),
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
                        html=f'<a href="{href}">'
                        f"{html_escape(ranked_function.function)}</a>"
                        if href
                        else None,
                    ),
                    theme.num_human(ranked_function.cost),
                    Cell(
                        theme.num_human(call_count),
                        style=theme.heat_style(
                            theme.heat_t(
                                100.0 * call_count / calls_total, calls_max_pct
                            )
                        ),
                    )
                    if call_count
                    else "",
                    Cell(who, html=who_html)
                    if who
                    else Cell("(no recorded caller)", cls="dim"),
                ]
            )
        return theme.table_render("report.functions", columns, rows, fill=True)

    def manifest_blocks_render(
        self, key: str, blocks: Sequence[BuildReport.ManifestBlock]
    ) -> str:
        body = ""
        for index, block in enumerate(blocks):
            if not block.pairs:
                continue
            body += (
                f"<h2>{html_escape(block.label)}</h2>"
            ) + self.manifest_table(f"{key}.{index}", block.pairs)
        return body

    def manifest_parse_blocks(
        self, items: Sequence[str]
    ) -> list[BuildReport.ManifestBlock]:
        out: list[BuildReport.ManifestBlock] = []
        for item in items:
            if "=" not in item:
                sys.exit(
                    f"error: --header-block expects LABEL=FILE, got {item!r}"
                )
            label, _, path = item.partition("=")
            out.append(
                BuildReport.ManifestBlock(
                    label.strip(), self.manifest_read_file(path)
                )
            )
        return out

    def manifest_parse_rows(
        self, items: Sequence[str]
    ) -> list[BuildReport.ManifestRow]:
        out: list[BuildReport.ManifestRow] = []
        for item in items:
            if "=" not in item:
                sys.exit(f"error: --header expects LABEL=VALUE, got {item!r}")
            label, _, value = item.partition("=")
            out.append(BuildReport.ManifestRow(label.strip(), value))
        return out

    def manifest_read_file(self, path: str) -> list[BuildReport.ManifestRow]:
        lines = [
            line
            for line in self.file_read(path).splitlines()
            if line.strip() and "=" in line
        ]
        return self.manifest_parse_rows(lines)

    def manifest_table(
        self, key: str, pairs: Sequence[BuildReport.ManifestRow]
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
            column_titles=False,
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
        pairs = self.manifest_parse_rows(args.header) + (
            self.manifest_read_file(args.header_file)
            if args.header_file
            else []
        )
        body = (
            body
            + '<main id="home"><div class="page">'
            + self.manifest_table("overview.header", pairs)
        )
        body += self.manifest_blocks_render(
            "overview.block", self.manifest_parse_blocks(args.header_block)
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
        body += '<main id="home"><div class="page">' + self.manifest_table(
            "report.header", self.manifest_parse_rows(args.header)
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
