#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, math, os, re, sys, urllib.parse
from collections.abc import Sequence
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind, settings, theme

# All constants needed from settings.py have to be loaded here before anything
# else.
_ASSET_FRAME_SCRIPT_NAME: str = ""
_ASSET_UI_STRINGS_SCRIPT_NAME: str = ""
_DIFF_CALLER_COUNTS_FILE_SUFFIX: str = ""
_FLAME_GRAPH_VIEW_ENTRY: tuple[str, str, str] = ("", "", "")
_HEAT_MAP_VIEW_ENTRY: tuple[str, str, str] = ("", "", "")
_RANKING_COUNTER_NAME: str = ""
_STRIP_CURL_PERF_SITE_HREF: str = ""
_STRIP_TEST_MENU_EXTRA_WIDTH_CHARS: int = 0
_STRIP_TEST_MENU_MERGED_TEST_NAME: str = ""
_SUMMARY_PERF_LOG_SKIPPED_HEAD_LINES: int = 0
_SUMMARY_TIME_SUFFIX_SECONDS: dict[str, float] = {}
_SUMMARY_TOP_FUNCTION_ROWS: int = 0
_TABLE_FUNCTION_NAME_WIDTH_CHARS: int = 0
settings.load_into(__name__)

# What this exits with when a file a page is built from will not open.
# ENOTDIR: the closest errno has to "the tree is not what we were told".
_EXIT_INPUT_UNREADABLE = 20

# Valgrind's "==1234== " line prefix, stripped so the log reads as output.
_PID_PREFIX = re.compile(r"^==\d+==\s?")

# How fine the scale slider's travel is, as an HTML range step over 0..1.
# Fine enough to feel continuous, coarse enough not to redraw per pixel.
_STRIP_SCALE_SLIDER_STEP = 0.01

# The overview page sits at the report root: its links need no "../".
_OVERVIEW_PAGE_ASSETS_DEPTH = 0

# How far a test's summary page sits below the report root: how many "../"
# its shared-asset, logo and help links need. The layout fixes it.
_SUMMARY_PAGE_ASSETS_DEPTH = 1

# A "Something: 1.23 ms" perf log line, the only valid speed number. Blank
# space is [ \t]*, never \s*, which under re.M merges two paragraphs.
_TIME_LINE = re.compile(
    r"^([ \t]*[A-Za-z][\w/ ]*:[ \t]*)"
    r"(-?\d+(?:\.\d+)?)[ \t]*"
    r"(usecs?|us|msecs?|ms|nsecs?|ns|secs?|s)[ \t]*$",
    re.I | re.M,
)


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

    # CallersData - the call graph a delta file cannot carry, plus the
    # baseline every share divides by.
    class CallersData(NamedTuple):
        # per function, who called it and how that changed
        callers: dict[str, list[BuildReport.CallerDelta]]
        # per function, its baseline cost in the synthesized callers
        # diff's counter
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
        # each test's working diff profile as "name=path", for a diff
        # overview
        diff_profile: list[str]

    # StripLink - One link in a page's top strip.
    class StripLink(NamedTuple):
        # what the URL hash calls it
        key: str
        # what the link says
        label: str
        # where it points
        href: str
        # what the status row and the tab title read while it is shown
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

    # The baseline run's total in this page's counter, from the synthesized
    # callers diff beside the delta.
    def baseline_total_load(self, path: str) -> int:
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
        counters: list[str] = doc["counters"]
        costs: list[int] = doc["baselineTotal"]
        self.counters_check(counters, path)
        return callgrind.counter_value(counters, costs, _RANKING_COUNTER_NAME)

    # The "callers" cell of a diff row: each caller and how its calls moved.
    def caller_delta_cell(
        self,
        profile: callgrind.Profile,
        deltas: Sequence[BuildReport.CallerDelta],
    ) -> theme.Cell:
        if not deltas:
            return theme.Cell("(no recorded caller change)", cls="dim")
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
                f" {theme.html_escape(delta.function)}"
                f"{theme.html_escape(count_text)}"
            )
            html_parts.append(
                f'<a href="{href}">{label}</a>' if href else label
            )
        joined = ", ".join(parts)
        return theme.Cell(joined, html=", ".join(html_parts))

    # One caller of a non-diff row, with its share of that function's calls.
    def caller_link(
        self,
        profile: callgrind.Profile,
        caller_name: str,
        count: int,
        call_count: int,
    ) -> str:
        href = self.entry_link(profile, caller_name)
        share = theme.num_pct(100.0 * count / call_count)
        label = f"{theme.html_escape(caller_name)} ({share})"
        return f'<a href="{href}">{label}</a>' if href else label

    # Read the synthesized callers diff back. Its vectors carry only the
    # recorded counters, so a derived one is added up from them here.
    def callers_data_load(self, path: str) -> BuildReport.CallersData:
        if not path:
            sys.exit(
                "error: --diff needs --callers-data, the callgrind_diff.py"
            )
        try:
            with open(path, encoding="utf-8") as handle:
                doc = json.load(handle)
        except OSError as error:
            sys.exit(f"error: {path}: {error}: the callgrind_diff.py")
        counters: list[str] = doc["counters"]
        self.counters_check(counters, path)
        return BuildReport.CallersData(
            callers={
                callee: [
                    BuildReport.CallerDelta(function, count, cost)
                    for function, count, cost in deltas
                ]
                for callee, deltas in doc["callers"].items()
            },
            baseline={
                name: callgrind.counter_value(
                    counters, costs, _RANKING_COUNTER_NAME
                )
                for name, costs in doc["baseline"].items()
                if "\n" not in name
            },
            baseline_calls=doc["baselineCalls"],
        )

    # Refuse a profile whose counters cannot add up to the ranking counter,
    # rather than a bare KeyError from Profile.value further in.
    def counters_check(self, counters: Sequence[str], path: str) -> None:
        if _RANKING_COUNTER_NAME in callgrind.counter_names(counters):
            return
        sys.exit(
            f"error: {path} cannot supply {_RANKING_COUNTER_NAME}, the"
            f" counter every diff share is counted in: it records"
            f" {' '.join(counters)}"
        )

    # One collapsed section of a summary page: a heading and its markup.
    # Every section, core and diff alike, is this same shape.
    def details_section(self, title: str, body: str) -> str:
        return (
            f'<details class="sec"><summary><h2>'
            f"{theme.html_escape(title)}</h2></summary>{body}</details>"
        )

    # The diff summary's top table, ranked by |change| in self cost.
    def diff_functions_table(
        self,
        profile: callgrind.Profile,
        callers_data: BuildReport.CallersData,
    ) -> str:
        ranked = sorted(
            (
                BuildReport.FunctionCost(
                    profile.value(costs, _RANKING_COUNTER_NAME), function
                )
                for function, costs in profile.function_self.items()
                if profile.value(costs, _RANKING_COUNTER_NAME) != 0
            ),
            key=lambda t: (-abs(t.cost), t.function),
        )[:_SUMMARY_TOP_FUNCTION_ROWS]
        shares = [
            self.diff_share(
                cost.cost, callers_data.baseline.get(cost.function)
            )
            for cost in ranked
        ]
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
        columns = self.function_columns()
        rows: list[list[theme.CellOrText]] = []
        for rank, ranked_function in enumerate(ranked, 1):
            share = shares[rank - 1]
            deltas = callers_data.callers.get(ranked_function.function, [])
            call_count = call_counts.get(ranked_function.function, 0)
            call_share = call_shares.get(ranked_function.function)
            rows.append(
                [
                    str(rank),
                    theme.Cell(
                        theme.num_signed_pct(share)
                        if share is not None
                        else "",
                        style=theme.heat_style(
                            theme.heat_of_share(share), signed=True
                        )
                        if share is not None
                        else "",
                    ),
                    self.function_link_cell(profile, ranked_function.function),
                    theme.num_signed(ranked_function.cost),
                    theme.Cell(
                        theme.num_signed(call_count),
                        style=theme.heat_style(
                            theme.heat_of_share(call_share),
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

    # Write the diff report's overview page.
    def diff_overview(self, args: BuildReport.OverviewArgs) -> None:
        tests = self.overview_tests(args)
        columns, rows = self.diff_overview_rows(tests, args.diff_profile)
        self.overview_page(args, tests, columns, rows)

    # One overview row per test, read from its working subtracted profile.
    def diff_overview_rows(
        self,
        tests: Sequence[BuildReport.TestDirectory],
        diff_profiles: Sequence[str],
    ) -> tuple[list[theme.Column], list[list[theme.CellOrText]]]:
        columns = [
            theme.Column("one report per test"),
            theme.Column(_RANKING_COUNTER_NAME, numeric=True),
            theme.Column("% of change", numeric=True),
            theme.Column("functions changed", numeric=True),
        ]
        profile_of: dict[str, str] = {}
        for entry in diff_profiles:
            if "=" not in entry:
                sys.exit(f"error: --diff-profile wants NAME=FILE: {entry!r}")
            name, path = entry.split("=", 1)
            profile_of[name] = path
        rows: list[list[theme.CellOrText]] = []
        for test in tests:
            # every test the diff paired has its delta and its callers file
            # beside it: one without is a broken run, never an empty row
            profile_path = profile_of[test.name]
            callers = profile_path + _DIFF_CALLER_COUNTS_FILE_SUFFIX
            link = self.test_link_cell(test.name)
            profile = callgrind.profile_load([profile_path])
            self.counters_check(profile.counters, profile_path)
            delta = profile.value(profile.totals(), _RANKING_COUNTER_NAME)
            changed = sum(
                1
                for costs in profile.function_self.values()
                if profile.value(costs, _RANKING_COUNTER_NAME) != 0
            )
            share = self.diff_share(delta, self.baseline_total_load(callers))
            rows.append(
                [
                    link,
                    theme.num_signed(delta),
                    theme.num_signed_pct(share) if share is not None else "",
                    theme.num_human(changed),
                ]
            )
        return columns, rows

    # A delta as a percentage of that same thing's own baseline. What the
    # baseline never had is infinite; None when there is no change at all.
    def diff_share(self, delta: int, baseline: int | None) -> float | None:
        if not baseline:
            return math.copysign(math.inf, delta) if delta else None
        return 100.0 * delta / abs(baseline)

    # Write one test's diff summary page.
    def diff_test(self, args: BuildReport.TestArgs) -> None:
        profile = callgrind.profile_load(args.callgrind_file)
        self.counters_check(profile.counters, " ".join(args.callgrind_file))
        callers_data = self.callers_data_load(args.callers_data)
        self.report_page(
            args,
            [_HEAT_VIEW],
            f"top {_SUMMARY_TOP_FUNCTION_ROWS} functions by change in self",
            self.diff_functions_table(profile, callers_data),
        )

    # The heat map href for a function, or "" when it has no local source.
    def entry_link(self, profile: callgrind.Profile, function: str) -> str:
        entry = profile.function_entry.get(function)
        if (
            entry is None
            or not entry.line
            or callgrind.path_norm(entry.file).local is None
        ):
            return ""
        return "heat-map/index.html#fn=" + theme.html_escape(
            urllib.parse.quote(function, safe="/-_.!~*'()")
        )

    # Read a file the page is built from; one that will not open stops the
    # run, so no manifest is written and no page carries an absolute path.
    def file_read(self, path: str) -> str:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                return handle.read()
        except OSError as error:
            print(
                f"error: {os.path.abspath(path)}: {error}: the page cannot"
                " be built without it",
                file=sys.stderr,
            )
            sys.exit(_EXIT_INPUT_UNREADABLE)

    # The scripts a framed page runs, in order: the strings first, so the
    # frame runtime can look an id up the moment it runs.
    def framed_page_script_names(self) -> tuple[str, str]:
        return (_ASSET_UI_STRINGS_SCRIPT_NAME, _ASSET_FRAME_SCRIPT_NAME)

    # The columns of a summary's top table. A core report and a diff rank
    # differently but say the same thing, so both are laid out the same.
    def function_columns(self) -> list[theme.Column]:
        return [
            theme.Column("#", numeric=True),
            theme.Column("% self", numeric=True),
            theme.Column("symbol", width=_TABLE_FUNCTION_NAME_WIDTH_CHARS),
            theme.Column(_RANKING_COUNTER_NAME, numeric=True),
            theme.Column("calls", numeric=True),
            theme.Column("callers", grow=True),
        ]

    # The "symbol" cell: the function's name, linked into the heat map when
    # it has local source to open there and bare text when it has not.
    def function_link_cell(
        self, profile: callgrind.Profile, function: str
    ) -> theme.Cell:
        href = self.entry_link(profile, function)
        return theme.Cell(
            function,
            html=f'<a href="{href}">{theme.html_escape(function)}</a>'
            if href
            else None,
        )

    # The summary's top table, ranked by self cost in the ranking counter.
    def functions_table(self, profile: callgrind.Profile) -> str:
        total = profile.value(profile.totals(), _RANKING_COUNTER_NAME) or 1
        ranked = sorted(
            (
                BuildReport.FunctionCost(
                    profile.value(costs, _RANKING_COUNTER_NAME), function
                )
                for function, costs in profile.function_self.items()
                if profile.value(costs, _RANKING_COUNTER_NAME) > 0
            ),
            key=lambda t: (-t.cost, t.function),
        )[:_SUMMARY_TOP_FUNCTION_ROWS]
        function_calls = {
            function: sum(tally.count for tally in callers.values())
            for function, callers in profile.callers.items()
        }
        calls_total = sum(function_calls.values()) or 1
        columns = self.function_columns()
        rows: list[list[theme.CellOrText]] = []
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
                    theme.Cell(
                        theme.num_pct(share),
                        style=theme.heat_style(theme.heat_of_share(share)),
                    ),
                    self.function_link_cell(profile, ranked_function.function),
                    theme.num_human(ranked_function.cost),
                    theme.Cell(
                        theme.num_human(call_count),
                        style=theme.heat_style(
                            theme.heat_of_share(
                                100.0 * call_count / calls_total
                            )
                        ),
                    )
                    if call_count
                    else "",
                    theme.Cell(who, html=who_html)
                    if who
                    else theme.Cell("(no recorded caller)", cls="dim"),
                ]
            )
        return theme.table_render("report.functions", columns, rows, fill=True)

    # One log file as a preformatted block, with valgrind's pid prefix gone.
    def log_block(self, path: str) -> str:
        lines = (
            self.file_read(path)
            .rstrip()
            .split("\n")[_SUMMARY_PERF_LOG_SKIPPED_HEAD_LINES:]
        )
        text = "\n".join(_PID_PREFIX.sub("", line) for line in lines)
        return self.logbox_render(text)

    # The collapsed "valgrind log" section, empty when no log was given.
    def log_section(self, paths: Sequence[str]) -> str:
        if not paths:
            return ""
        body = ""
        for path in paths:
            if len(paths) > 1:
                body += f"<p>{theme.html_escape(os.path.basename(path))}</p>"
            body += self.log_block(path)
        return self.details_section("valgrind log", body)

    # Captured output as one preformatted block, escaped for the page.
    def logbox_render(self, text: str) -> str:
        return (
            f'<div class="tbl"><pre class="logbox">{theme.html_escape(text)}'
            "</pre></div>"
        )

    # Every non-empty block as a heading plus its own LABEL=VALUE table.
    def manifest_blocks_render(
        self,
        key: str,
        blocks: Sequence[BuildReport.ManifestBlock],
    ) -> str:
        body = ""
        for index, block in enumerate(blocks):
            if not block.pairs:
                continue
            body += (
                f"<h2>{theme.html_escape(block.label)}</h2>"
            ) + self.manifest_table(f"{key}.{index}", block.pairs)
        return body

    # Parse --header-block LABEL=FILE arguments into blocks of rows.
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

    # Parse LABEL=VALUE arguments into rows.
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

    # Read LABEL=VALUE rows from a file, skipping every other line.
    def manifest_read_file(self, path: str) -> list[BuildReport.ManifestRow]:
        lines = [
            line
            for line in self.file_read(path).splitlines()
            if line.strip() and "=" in line
        ]
        return self.manifest_parse_rows(lines)

    # The untitled two-column table those rows are rendered as.
    def manifest_table(
        self,
        key: str,
        pairs: Sequence[BuildReport.ManifestRow],
    ) -> str:
        if not pairs:
            return ""
        rows: list[list[theme.CellOrText]] = [
            [theme.Cell(pair.label, cls="dim"), pair.value] for pair in pairs
        ]
        return theme.table_render(
            key,
            [theme.Column("label"), theme.Column("value", grow=True)],
            rows,
            fill=True,
            column_titles=False,
        )

    # A collapsed section holding a captured log, with its times humanized.
    def output_section(self, title: str, path: str) -> str:
        if not path:
            return ""
        output = self.time_humanize(self.file_read(path).rstrip())
        return self.details_section(title, self.logbox_render(output))

    # Write the full report's overview page, from each test's perf log.
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
        columns = [theme.Column("report")] + [
            theme.Column(key, numeric=True) for key in keys
        ]
        rows: list[list[theme.CellOrText]] = [
            [self.test_link_cell(test.name)]
            + [numbers[test.name].get(key, "") for key in keys]
            for test in tests
        ]
        self.overview_page(args, tests, columns, rows)

    # Assemble and write an overview page around an already built table.
    def overview_page(
        self,
        args: BuildReport.OverviewArgs,
        tests: Sequence[BuildReport.TestDirectory],
        columns: Sequence[theme.Column],
        rows: Sequence[Sequence[theme.CellOrText]],
    ) -> None:
        links = [BuildReport.StripLink("", "overview", "#", "overview")]
        test_menu_entries = [
            BuildReport.StripLink(
                test.name,
                test.name,
                f"{test.name}/index.html",
                test.name,
                frame=True,
            )
            for test in tests
        ]
        body = self.strip_render(
            "overview",
            links,
            depth=_OVERVIEW_PAGE_ASSETS_DEPTH,
            test_menu_entries=test_menu_entries,
        )
        pairs = self.manifest_parse_rows(args.header) + (
            self.manifest_read_file(args.header_file)
            if args.header_file
            else []
        )
        body = (
            body
            + self.page_main_open()
            + self.manifest_table("overview.header", pairs)
        )
        body += self.manifest_blocks_render(
            "overview.block", self.manifest_parse_blocks(args.header_block)
        )
        body += "<h2>test suites</h2>" + theme.table_render(
            "overview.tests", columns, rows
        )
        body += self.page_main_close()
        self.page_write(
            args.output,
            theme.page_document(
                "overview",
                body,
                extra_js=self.framed_page_script_names(),
                body_class="frame",
                depth=_OVERVIEW_PAGE_ASSETS_DEPTH,
            ),
        )

    # The named tests and their directories, sorted for a stable page.
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

    # What closes the content of a framed page: the frame every view loads
    # into follows it, empty until a strip link fills it.
    def page_main_close(self) -> str:
        return (
            '</div></main><iframe id="view" hidden'
            ' title="report page"></iframe>'
        )

    # What opens the content of a framed page. Both the overview and a test
    # summary are a page inside the one frame host, so both start here.
    def page_main_open(self) -> str:
        return '<main id="home"><div class="page">'

    # Write a page, making its directory, and report its size.
    def page_write(self, path: str, page: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(page)
        print(
            f"wrote {path} ({len(page.encode('utf-8')):,} bytes)",
            file=sys.stderr,
        )

    # The collapsed "raw data" section linking this test's archives.
    def rawdata_section(self, paths: Sequence[str], out_dir: str) -> str:
        if not paths:
            return ""
        items = "".join(
            "<li><a href="
            f'"{theme.html_escape(os.path.relpath(path, out_dir))}"'
            ' target="_blank">'
            f"{theme.html_escape(os.path.basename(path))}</a></li>"
            for path in paths
        )
        return self.details_section(
            "raw data", f'<ul class="rawdata">{items}</ul>'
        )

    # Assemble and write one test's summary page around its top table.
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
        body = self.strip_render(
            args.test, links, depth=_SUMMARY_PAGE_ASSETS_DEPTH
        )
        out_dir = os.path.dirname(os.path.abspath(args.output))
        body += self.page_main_open() + self.manifest_table(
            "report.header", self.manifest_parse_rows(args.header)
        )
        body += self.output_section("perf log", args.perf_log)
        body += self.output_section("trace log", args.trace_log)
        if not args.no_log:
            body += self.log_section(args.log)
        body += self.rawdata_section(args.raw_data, out_dir)
        body += f"<h2>{heading}</h2>" + table
        body += self.page_main_close()
        self.page_write(
            args.output,
            theme.page_document(
                args.test,
                body,
                extra_js=self.framed_page_script_names(),
                body_class="frame",
                depth=_SUMMARY_PAGE_ASSETS_DEPTH,
            ),
        )

    # One link of a strip. A test menu entry is the same link, kept out of
    # the tab order: the menu's search box moves between its entries.
    def strip_link_render(
        self, link: BuildReport.StripLink, in_tab_order: bool = True
    ) -> str:
        return (
            f'<a href="{theme.html_escape(link.href)}"'
            f' data-view="{theme.html_escape(link.key)}"'
            f' data-title="{theme.html_escape(link.title)}"'
            f"{' data-frame=1' if link.frame else ''}"
            f"{'' if in_tab_order else ' tabindex=-1'}>"
            f"{theme.html_escape(link.label)}</a>"
        )

    # The top strip: the title cell, which as the logo leads to the report
    # root, the view links, the test menu, and the utility links on the right.
    def strip_render(
        self,
        title: str,
        links: Sequence[BuildReport.StripLink],
        depth: int,
        test_menu_entries: Sequence[BuildReport.StripLink] = (),
    ) -> str:
        separator = '<span class="sep">|</span>'
        root_href = theme.shared_href(depth, "index.html")
        help_href = theme.shared_href(depth, "README.md")
        parts = [
            '<b class="title" id="title"'
            f' data-root-href="{theme.html_escape(root_href)}">'
            f"{theme.html_escape(title)}</b>"
        ]
        for index, link in enumerate(links):
            if index:
                parts.append(separator)
            parts.append(self.strip_link_render(link))
        if test_menu_entries:
            parts.append(separator)
            parts.append(self.test_menu_render(test_menu_entries))
        parts.append('<span class="sp"></span>')
        parts.append(
            '<label class="scale" id="scale-label" for="scale-slider">'
            '<span id="scale-text"></span>'
            '<input type="range" id="scale-slider" min="0" max="1"'
            f' step="{_STRIP_SCALE_SLIDER_STEP}">'
            "</label>"
        )
        parts.append('<span class="util" id="util">')
        parts.append(separator)
        parts.append('<a href="#" id="layout-reset">reset</a>')
        parts.append(separator)
        parts.append(
            f'<a href="{theme.html_escape(help_href)}"'
            ' target="_blank">help</a>'
        )
        parts.append(separator)
        parts.append(
            f'<a href="{_STRIP_CURL_PERF_SITE_HREF}" target="_blank"'
            ' rel="noopener">'
            "curl.se/perf</a>"
        )
        parts.append("</span>")
        return f'<nav id="bar" class="strip">{"".join(parts)}</nav>'

    # Write one test's summary page.
    def test(self, args: BuildReport.TestArgs) -> None:
        profile = callgrind.profile_load(args.callgrind_file)
        self.counters_check(profile.counters, " ".join(args.callgrind_file))
        views = [_FLAME_VIEW, _HEAT_VIEW] if args.trace_log else [_HEAT_VIEW]
        self.report_page(
            args,
            views,
            f"top {_SUMMARY_TOP_FUNCTION_ROWS} functions by self",
            self.functions_table(profile),
        )

    # An overview row's first cell: the test's name, linking the summary
    # page in its own directory beside the overview.
    def test_link_cell(self, name: str) -> theme.Cell:
        escaped = theme.html_escape(name)
        return theme.Cell(
            name, html=f'<a href="{escaped}/index.html">{escaped}</a>'
        )

    # The overview's test menu: a box fitting every test name and reading the
    # merged one, its caret button, and each test's strip link in a list below.
    def test_menu_render(
        self, entries: Sequence[BuildReport.StripLink]
    ) -> str:
        names = [entry.label for entry in entries]
        if _STRIP_TEST_MENU_MERGED_TEST_NAME not in names:
            sys.exit(
                "error: the overview's test menu reads"
                f" {_STRIP_TEST_MENU_MERGED_TEST_NAME!r}, the merged test,"
                f" which is not one of its tests: {' '.join(names)}"
            )
        width = (
            max(len(name) for name in names)
            + _STRIP_TEST_MENU_EXTRA_WIDTH_CHARS
        )
        merged_name = theme.html_escape(_STRIP_TEST_MENU_MERGED_TEST_NAME)
        items = "".join(
            self.strip_link_render(entry, in_tab_order=False)
            for entry in entries
        )
        return (
            '<span class="test-menu">'
            '<input id="test-menu-search" type="text"'
            f' style="width:{width}ch" value="{merged_name}"'
            ' readonly autocomplete="off" spellcheck="false">'
            '<button id="test-menu-button" type="button" tabindex=-1>'
            "</button>"
            '<span class="test-menu-list" id="test-menu-list" hidden>'
            f"{items}"
            '<span class="test-menu-no-match" id="test-menu-no-match"'
            " hidden></span></span></span>"
        )

    # Rewrite every "Something: 1.23 ms" line in the theme's time notation.
    def time_humanize(self, text: str) -> str:
        return _TIME_LINE.sub(self.time_line_rewrite, text)

    # One matched "Something: 1.23 ms" line, rewritten in the theme's time
    # notation. _TIME_LINE matches exactly the suffixes the setting scales.
    def time_line_rewrite(self, match: re.Match[str]) -> str:
        scale = _SUMMARY_TIME_SUFFIX_SECONDS[match.group(3).lower()]
        return match.group(1) + theme.num_time(float(match.group(2)) * scale)

    # The same rewrite for one already split label and value.
    def value_humanize(self, label: str, value: str) -> str:
        line = self.time_humanize(f"{label}: {value}")
        return line.split(": ", 1)[1] if line != f"{label}: {value}" else value


# The flame graph view, linked only where a trace was actually recorded.
_FLAME_VIEW = BuildReport.View(*_FLAME_GRAPH_VIEW_ENTRY)

# The heat map view, which every test has.
_HEAT_VIEW = BuildReport.View(*_HEAT_MAP_VIEW_ENTRY)


# main - The test, assets and overview subcommands.
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

    assets_parser = subparsers.add_parser(
        "assets", help="the report's one shared copy of the theme"
    )
    assets_parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="the directory to write the shared stylesheets and scripts to",
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
        "--diff-profile",
        action="append",
        metavar="NAME=FILE",
        default=[],
        help="with --diff, a test's subtracted profile as callgrind_diff.py"
        " wrote it, to read its row from (its synthesized callers diff is"
        f" that name plus {_DIFF_CALLER_COUNTS_FILE_SUFFIX}). repeatable",
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
    if namespace.cmd == "assets":
        theme.theme_assets_write(namespace.output)
    elif namespace.cmd == "test":
        test_args = BuildReport.TestArgs(
            callgrind_file=namespace.callgrind_file,
            output=namespace.output,
            test=namespace.test,
            raw_data=namespace.raw_data,
            log=namespace.log,
            perf_log=namespace.perf_log,
            trace_log=namespace.trace_log,
            no_log=namespace.no_log,
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
            diff_profile=namespace.diff_profile,
        )
        (report.diff_overview if namespace.diff else report.overview)(
            overview_args
        )


if __name__ == "__main__":
    main()
