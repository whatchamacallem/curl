#!/usr/bin/env python3
from __future__ import annotations

import argparse, os, re, sys, urllib.parse
from collections.abc import Sequence
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind, callgrind_diff, settings, theme

# All constants needed from settings.py have to be loaded here before anything
# else.
_ASSET_CALLERS_SCRIPT_NAME: str = ""
_ASSET_FRAME_SCRIPT_NAME: str = ""
_ASSET_MENU_SCRIPT_NAME: str = ""
_ASSET_MENU_STYLESHEET_NAME: str = ""
_ASSET_PULLDOWN_TEXT_SCRIPT_NAME: str = ""
_ASSET_TEMPLATE_OVERVIEW_PAGE_NAME: str = ""
_CALLERS_PERF_LOG_SKIPPED_HEAD_LINES: int = 0
_CALLERS_TIME_SUFFIX_SECONDS: dict[str, float] = {}
_CALLERS_TOP_FUNCTION_ROWS: int = 0
_CALLERS_VIEW_KEY: str = ""
_DIFF_CALLER_COUNTS_FILE_SUFFIX: str = ""
_FLAME_GRAPH_LOCAL_PROFILE_PATH: str = ""
_FLAME_GRAPH_VIEW_ENTRY: tuple[str, str, str] = ("", "", "")
_HEAT_MAP_VIEW_ENTRY: tuple[str, str, str] = ("", "", "")
_MENU_BUTTON_ORDER: tuple[str, ...] = ()
_MENU_PULLDOWN_MERGED_TEST_NAME: str = ""
_RANKING_COUNTER_NAME: str = ""
_STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS: int = 0
_STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS: int = 0
settings.load_into(__name__)

# How far a test's callers page sits below the report root: how many "../"
# its shared-asset links need. The layout fixes it.
_CALLERS_PAGE_ASSETS_DEPTH = 1

# What this exits with when a file a page is built from will not open.
# ENOTDIR: the closest errno has to "the tree is not what we were told".
_EXIT_INPUT_UNREADABLE = 20

# Valgrind's "==1234== " line prefix, stripped so the log reads as output.
_PID_PREFIX = re.compile(r"^==\d+==\s?")

# The overview page sits at the report root: its links need no "../".
_OVERVIEW_PAGE_ASSETS_DEPTH = 0

# The overview's content: its headings, the blank lines between its blocks,
# and the markers overview_page() substitutes.
_OVERVIEW_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_OVERVIEW_PAGE_NAME)

# A "Something: 1.23 ms" perf log line, the only valid speed number. Blank
# space is [ \t]*, never \s*, which under re.M merges two paragraphs.
_TIME_LINE = re.compile(
    r"^([ \t]*[A-Za-z][\w/ ]*:[ \t]*)"
    r"(-?\d+(?:\.\d+)?)[ \t]*"
    r"(usecs?|us|msecs?|ms|nsecs?|ns|secs?|s)[ \t]*$",
    re.I | re.M,
)


# BuildReport - Writes the overview page with the menu and the frame every
# view loads into, and every test's callers page, one of those views.
class BuildReport:
    # CallersData - the call graph a delta file cannot carry, plus the
    # baseline every share divides by.
    class CallersData(NamedTuple):
        # per function, who called it and how that changed
        callers: dict[str, list[callgrind_diff.CallerDelta]]
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

    # MenuLink - One entry of the tests pulldown's list.
    class MenuLink(NamedTuple):
        # the test the entry opens, which is also what the entry says
        test_name: str
        # the address the entry opens
        href: str

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
        # each test's perf log as "name=path", for a full overview
        perf_log: list[str]
        # the timer artifacts archive linked as raw data, for a full overview
        raw_data: str

    # TestArgs - Everything one test's callers page is built from. Each
    # optional log renders a section only when it is given.
    class TestArgs(NamedTuple):
        # the callgrind file(s), merged into one profile
        callgrind_file: list[str]
        # where the page goes
        output: str
        # the test's name
        test: str
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

    # View - One view of a test with a page of its own at the report root.
    class View(NamedTuple):
        # what an address's view= calls the view
        key: str
        # what its button, link and title say
        label: str

    # One address in the grammar every page reads, the test, the view, then
    # the view's own keys in their order. The one writer of its key names.
    def address_of(
        self, test_name: str, view_key: str, function_name: str = ""
    ) -> str:
        hash_text = f"#test={self.address_value_of(test_name)}&view={view_key}"
        if function_name:
            hash_text += f"&function={self.address_value_of(function_name)}"
        if view_key == _FLAME_VIEW.key:
            hash_text += f"&localProfilePath={_FLAME_GRAPH_LOCAL_PROFILE_PATH}"
        return hash_text

    # One address value encoded as the pages encode one, what
    # encodeURIComponent escapes, less "/", kept readable.
    def address_value_of(self, value: str) -> str:
        return urllib.parse.quote(value, safe="/-_.!~*'()")

    # The baseline run's total in this page's counter, from the synthesized
    # callers diff beside the delta.
    def baseline_total_load(self, path: str) -> int:
        doc = callgrind_diff.callers_doc_load(path)
        counters = doc["counters"]
        callgrind.ranking_counter_check(counters, path)
        return callgrind.counter_value(
            counters, doc["baselineTotal"], _RANKING_COUNTER_NAME
        )

    # One blank line between two blocks of a page, a text line's height.
    def blank_line_render(self) -> str:
        return "<br />"

    # The "callers" cell of a diff row: each caller and how its calls moved.
    def caller_delta_cell(
        self,
        test_name: str,
        profile: callgrind.LineProfile,
        deltas: Sequence[callgrind_diff.CallerDelta],
    ) -> theme.Cell:
        if not deltas:
            return theme.Cell("(no recorded caller change)", cls="dimmed_")
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
            href = self.entry_link(test_name, profile, delta.function)
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
        test_name: str,
        profile: callgrind.LineProfile,
        caller_name: str,
        count: int,
        call_count: int,
    ) -> str:
        href = self.entry_link(test_name, profile, caller_name)
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
        doc = callgrind_diff.callers_doc_load(path)
        counters = doc["counters"]
        callgrind.ranking_counter_check(counters, path)
        return BuildReport.CallersData(
            callers=doc["callers"],
            baseline={
                name: callgrind.counter_value(
                    counters, costs, _RANKING_COUNTER_NAME
                )
                for name, costs in doc["baseline"].items()
                if "\n" not in name
            },
            baseline_calls=doc["baselineCalls"],
        )

    # One collapsed section of a callers page: a heading and its markup.
    # Every section, core and diff alike, is this same shape.
    def details_section(self, title: str, body: str) -> str:
        return (
            '<details class="callers-collapsed-section-">'
            '<summary class="callers-collapsed-section-title-">'
            f"{theme.html_escape(title)}</summary>{body}</details>"
        )

    # The diff callers page's top table, ranked by |change| in self cost.
    def diff_functions_table(
        self,
        test_name: str,
        profile: callgrind.LineProfile,
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
        )[:_CALLERS_TOP_FUNCTION_ROWS]
        shares = [
            theme.diff_share_of(
                cost.cost, callers_data.baseline.get(cost.function)
            )
            for cost in ranked
        ]
        call_counts = {
            callee: sum(delta.count_ for delta in deltas)
            for callee, deltas in callers_data.callers.items()
        }
        call_shares = {
            callee: theme.diff_share_of(
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
            rows.append(
                [
                    str(rank),
                    theme.Cell(
                        theme.num_signed_pct(share),
                        style=theme.heat_style(
                            theme.heat_of_share(share), signed=True
                        ),
                    ),
                    self.function_link_cell(
                        test_name, profile, ranked_function.function
                    ),
                    theme.num_signed(ranked_function.cost),
                    theme.Cell(
                        theme.num_signed(call_count),
                        style=theme.heat_style(
                            theme.heat_of_share(
                                call_shares[ranked_function.function]
                            ),
                            signed=True,
                        ),
                    )
                    if call_count
                    else "",
                    self.caller_delta_cell(test_name, profile, deltas),
                ]
            )
        return theme.table_render("report.functions", columns, rows, fill=True)

    # Write the diff report's overview page, whose menu has no flame graph.
    def diff_overview(self, args: BuildReport.OverviewArgs) -> None:
        tests = self.overview_tests(args)
        columns, rows = self.diff_overview_rows(tests, args.diff_profile)
        self.overview_page(args, tests, columns, rows, False)

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
        profile_of = self.named_paths_of(diff_profiles, "--diff-profile")
        rows: list[list[theme.CellOrText]] = []
        for test in tests:
            # every test the diff paired has its delta and its callers file
            # beside it: one without is a broken run, never an empty row
            profile_path = profile_of[test.name]
            callers = profile_path + _DIFF_CALLER_COUNTS_FILE_SUFFIX
            link = self.test_link_cell(test.name)
            profile = callgrind.profile_load([profile_path])
            callgrind.ranking_counter_check(profile.counters, profile_path)
            delta = profile.value(profile.totals(), _RANKING_COUNTER_NAME)
            changed = sum(
                1
                for costs in profile.function_self.values()
                if profile.value(costs, _RANKING_COUNTER_NAME) != 0
            )
            share = theme.diff_share_of(
                delta, self.baseline_total_load(callers)
            )
            rows.append(
                [
                    link,
                    theme.num_signed(delta),
                    theme.num_signed_pct(share),
                    theme.num_human(changed),
                ]
            )
        return columns, rows

    # Write one test's diff callers page.
    def diff_test(self, args: BuildReport.TestArgs) -> None:
        profile = callgrind.profile_load(args.callgrind_file)
        callgrind.ranking_counter_check(
            profile.counters, " ".join(args.callgrind_file)
        )
        callers_data = self.callers_data_load(args.callers_data)
        self.report_page(
            args,
            f"top {_CALLERS_TOP_FUNCTION_ROWS} functions by change in self",
            self.diff_functions_table(args.test, profile, callers_data),
        )

    # The heat map address opening a function, markup ready, or "" when that
    # function has no entry line to open there.
    def entry_link(
        self, test_name: str, profile: callgrind.LineProfile, function: str
    ) -> str:
        entry = profile.function_entry.get(function)
        if entry is None or not entry.line:
            return ""
        return theme.html_escape(
            self.address_of(test_name, _HEAT_VIEW.key, function)
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

    # The callers page's link to its test's flame graph, the address the
    # menu's flame graph button opens for that test.
    def flame_graph_link_render(self, test_name: str) -> str:
        href = self.address_of(test_name, _FLAME_VIEW.key)
        return (
            f'<div><a href="{theme.html_escape(href)}">'
            f"{theme.html_escape(_FLAME_VIEW.label)}</a></div>"
        )

    # The columns of a callers page's top table. A core report and a diff rank
    # differently but say the same thing, so both are laid out the same.
    def function_columns(self) -> list[theme.Column]:
        return [
            theme.Column("#", numeric=True),
            theme.Column("% self", numeric=True),
            theme.Column(
                "symbol", width=_STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS
            ),
            theme.Column(_RANKING_COUNTER_NAME, numeric=True),
            theme.Column("calls", numeric=True),
            theme.Column("callers", grow=True),
        ]

    # The "symbol" cell: the function's name, linked into the heat map when
    # it has an entry line to open there and bare text when it has not.
    def function_link_cell(
        self, test_name: str, profile: callgrind.LineProfile, function: str
    ) -> theme.Cell:
        href = self.entry_link(test_name, profile, function)
        return theme.Cell(
            function,
            html=f'<a href="{href}">{theme.html_escape(function)}</a>'
            if href
            else None,
        )

    # The callers page's top table, ranked by self cost in the ranking counter.
    def functions_table(
        self, test_name: str, profile: callgrind.Profile
    ) -> str:
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
        )[:_CALLERS_TOP_FUNCTION_ROWS]
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
                self.caller_link(
                    test_name, profile, caller_name, count, call_count
                )
                for caller_name, count in by_caller_sorted
            )
            rows.append(
                [
                    str(rank),
                    theme.Cell(
                        theme.num_pct(share),
                        style=theme.heat_style(theme.heat_of_share(share)),
                    ),
                    self.function_link_cell(
                        test_name, profile, ranked_function.function
                    ),
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
                    else theme.Cell("(no recorded caller)", cls="dimmed_"),
                ]
            )
        return theme.table_render("report.functions", columns, rows, fill=True)

    # One heading line of an overview or callers page, told apart by colour.
    def heading_render(self, text: str) -> str:
        return f'<div class="page-heading-">{theme.html_escape(text)}</div>'

    # One log file as a preformatted block, with valgrind's pid prefix gone.
    def log_block(self, path: str) -> str:
        lines = (
            self.file_read(path)
            .rstrip()
            .split("\n")[_CALLERS_PERF_LOG_SKIPPED_HEAD_LINES:]
        )
        text = "\n".join(_PID_PREFIX.sub("", line) for line in lines)
        return self.log_box_render(text)

    # The collapsed "valgrind log" section, empty when no log was given.
    def log_section(self, paths: Sequence[str]) -> str:
        if not paths:
            return ""
        body = ""
        for path in paths:
            if len(paths) > 1:
                body += (
                    '<div class="callers-collapsed-section-file-name-">'
                    f"{theme.html_escape(os.path.basename(path))}</div>"
                )
            body += self.log_block(path)
        return self.details_section("valgrind log", body)

    # Captured output as one preformatted block, escaped for the page.
    def log_box_render(self, text: str) -> str:
        return (
            '<div class="table-box-">'
            '<pre class="callers-collapsed-section-log-box-">'
            f"{theme.html_escape(text)}"
            "</pre></div>"
        )

    # Every non-empty block as a heading plus its own LABEL=VALUE table, a
    # blank line between two blocks.
    def manifest_blocks_render(
        self,
        key: str,
        blocks: Sequence[BuildReport.ManifestBlock],
    ) -> str:
        return self.blank_line_render().join(
            self.heading_render(block.label)
            + self.manifest_table(f"{key}.{index}", block.pairs)
            for index, block in enumerate(blocks)
            if block.pairs
        )

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
            [theme.Cell(pair.label, cls="dimmed_"), pair.value]
            for pair in pairs
        ]
        return theme.table_render(
            key,
            [theme.Column("label"), theme.Column("value", grow=True)],
            rows,
            fill=True,
            column_titles=False,
        )

    # A numbered menu button that opens a page or a view. menu.js writes its
    # text, and a view button's address for the test on show.
    def menu_button_link_render(
        self, name: str, href: str, new_tab: bool = False
    ) -> str:
        target_attribute = ' target="_blank"' if new_tab else ""
        return (
            f'<a class="menu-button-" id="menu-{name}-button-"'
            f' href="{theme.html_escape(href)}"{target_attribute}></a>'
        )

    # A numbered menu button that acts on the page rather than opening one.
    # menu.js writes its text, as it does every numbered button's.
    def menu_button_render(self, name: str) -> str:
        return (
            f'<button class="menu-button-" id="menu-{name}-button-"'
            ' type="button"></button>'
        )

    # One entry of the tests pulldown, kept out of the tab order: the
    # pulldown's search box moves between its entries.
    def menu_link_render(self, link: BuildReport.MenuLink) -> str:
        test_name = theme.html_escape(link.test_name)
        return (
            f'<a href="{theme.html_escape(link.href)}"'
            f' data-test-name-="{test_name}" tabindex=-1>{test_name}</a>'
        )

    # The overview's pulldowns by name, its tests, each opening that test's
    # heat map, then the files and functions menu.js lists for the test.
    def menu_pulldowns_render(
        self, test_entries: Sequence[BuildReport.MenuLink]
    ) -> dict[str, str]:
        names = [entry.test_name for entry in test_entries]
        if _MENU_PULLDOWN_MERGED_TEST_NAME not in names:
            sys.exit(
                "error: the overview's pulldowns start in"
                f" {_MENU_PULLDOWN_MERGED_TEST_NAME!r}, the merged test,"
                f" which is not one of its tests: {' '.join(names)}"
            )
        width = (
            max(len(name) for name in names)
            + _STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS
        )
        test_links = "".join(
            self.menu_link_render(entry) for entry in test_entries
        )
        return {
            "test": self.pulldown_render("test", width, test_links),
            "file": self.pulldown_render("file", width, ""),
            "function": self.pulldown_render("function", width, ""),
        }

    # The one menu row, the overview's. The logo linking the report root, the
    # buttons, then the title cell menu.js writes the address into.
    def menu_render(
        self,
        test_entries: Sequence[BuildReport.MenuLink],
        has_flame_graph: bool,
    ) -> str:
        root_href = theme.shared_href(
            _OVERVIEW_PAGE_ASSETS_DEPTH, "index.html"
        )
        help_href = theme.shared_href(_OVERVIEW_PAGE_ASSETS_DEPTH, "README.md")
        # each button by the name in its id; menu.js points the three view
        # buttons at the test on show
        button_markups = {
            "overview": self.menu_button_link_render("overview", "#"),
            **self.menu_pulldowns_render(test_entries),
            _HEAT_VIEW.key: self.menu_button_link_render(_HEAT_VIEW.key, "#"),
            _CALLERS_VIEW_KEY: self.menu_button_link_render(
                _CALLERS_VIEW_KEY, "#"
            ),
            _FLAME_VIEW.key: self.menu_button_link_render(
                _FLAME_VIEW.key, "#"
            ),
            "reset": self.menu_button_render("reset"),
            "help": self.menu_button_link_render(
                "help", help_href, new_tab=True
            ),
            "scale": self.menu_button_render("scale"),
        }
        # in the order the setting numbers them by; a diff has no flame
        # graph, so its button is left out and every number kept
        ordered_buttons = [
            button_markups[name]
            for name in _MENU_BUTTON_ORDER
            if has_flame_graph or name != _FLAME_VIEW.key
        ]
        parts = [
            '<a class="menu-logo-" id="menu-logo-"'
            f' href="{theme.html_escape(root_href)}"></a>',
            *ordered_buttons,
            '<div class="menu-title-" id="menu-title-"></div>',
        ]
        menu_items = "".join(parts)
        return f'<nav id="menu_" class="menu-strip-">{menu_items}</nav>'

    # The NAME=FILE arguments of one repeatable flag as a name to path map;
    # an entry without the "=" is a broken command line, stopped here.
    def named_paths_of(
        self, entries: Sequence[str], flag: str
    ) -> dict[str, str]:
        path_of: dict[str, str] = {}
        for entry in entries:
            if "=" not in entry:
                sys.exit(f"error: {flag} wants NAME=FILE: {entry!r}")
            name, path = entry.split("=", 1)
            path_of[name] = path
        return path_of

    # A collapsed section holding a captured log, with its times humanized.
    def output_section(self, title: str, path: str) -> str:
        if not path:
            return ""
        output = self.time_humanize(self.file_read(path).rstrip())
        return self.details_section(title, self.log_box_render(output))

    # Write the full report's overview page, from each test's perf log.
    def overview(self, args: BuildReport.OverviewArgs) -> None:
        tests = self.overview_tests(args)
        perf_log_of = self.named_paths_of(args.perf_log, "--perf-log")
        keys: list[str] = []
        numbers: dict[str, dict[str, str]] = {}
        for test in tests:
            values: dict[str, str] = {}
            # every test named has its perf log named too: one without is a
            # broken run, never an empty row
            for line in self.file_read(perf_log_of[test.name]).splitlines():
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
        self.overview_page(args, tests, columns, rows, True)

    # Assemble and write an overview page around an already built table, in
    # the overview template's layout of headings and blank lines.
    def overview_page(
        self,
        args: BuildReport.OverviewArgs,
        tests: Sequence[BuildReport.TestDirectory],
        columns: Sequence[theme.Column],
        rows: Sequence[Sequence[theme.CellOrText]],
        has_flame_graph: bool,
    ) -> None:
        test_entries = [
            BuildReport.MenuLink(
                test.name, self.address_of(test.name, _HEAT_VIEW.key)
            )
            for test in tests
        ]
        body = self.menu_render(test_entries, has_flame_graph)
        out_dir = os.path.dirname(os.path.abspath(args.output))
        pairs = self.manifest_parse_rows(args.header) + (
            self.manifest_read_file(args.header_file)
            if args.header_file
            else []
        )
        # a full report's own rows are its manifest; a diff's rows are its
        # two inputs', each a block of its own
        manifest_blocks = [BuildReport.ManifestBlock("manifest", pairs)]
        manifest_blocks += self.manifest_parse_blocks(args.header_block)
        raw_data_markup = self.raw_data_render(args.raw_data, out_dir)
        tests_markup = theme.table_render("overview.tests", columns, rows)
        manifest_markup = self.manifest_blocks_render(
            "overview.block", manifest_blocks
        )
        # the manifest goes in last: its rows carry the command line's own
        # text, and a marker spelled there must never be substituted
        page_content = (
            _OVERVIEW_PAGE.replace("__RAW_DATA__", raw_data_markup)
            .replace("__TESTS__", tests_markup)
            .replace("__MANIFEST__", manifest_markup)
        )
        body += self.page_main_open() + page_content + self.page_main_close()
        # menu.js lists the files and functions pulldowns from the pulldown
        # text and activates the frame, so both load before menu.js
        self.page_write(
            args.output,
            theme.page_document(
                "overview",
                body,
                extra_js=(
                    _ASSET_PULLDOWN_TEXT_SCRIPT_NAME,
                    _ASSET_FRAME_SCRIPT_NAME,
                    _ASSET_MENU_SCRIPT_NAME,
                ),
                body_class="frame_",
                depth=_OVERVIEW_PAGE_ASSETS_DEPTH,
                extra_css=(_ASSET_MENU_STYLESHEET_NAME,),
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

    # What closes the overview's content. The frame every view loads into
    # follows it, empty until an address names a view.
    def page_main_close(self) -> str:
        return (
            '</div></main><iframe id="overview-view-frame-" hidden'
            ' title="report page"></iframe>'
        )

    # What opens the overview's content, the home the menu shows while the
    # address names no view.
    def page_main_open(self) -> str:
        return '<main id="overview-home-"><div class="page_">'

    # Write a page, making its directory, and report its size.
    def page_write(self, path: str, page: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(page)
        print(
            f"wrote {path} ({len(page.encode('utf-8')):,} bytes)",
            file=sys.stderr,
        )

    # One menu pulldown: its numbered button, the search box taking the
    # button's place while open, and the list dropping below the button.
    def pulldown_render(self, key: str, width: int, entries: str) -> str:
        return (
            f'<span class="menu-pulldown-" id="menu-{key}-pulldown-">'
            '<button class="menu-button- menu-pulldown-button-"'
            f' id="menu-{key}-button-" type="button"></button>'
            '<input class="menu-pulldown-search-box-" type="text"'
            f' style="width:{width}ch"'
            ' hidden autocomplete="off" spellcheck="false">'
            f'<span class="menu-pulldown-entry-list-" hidden>{entries}'
            '<span class="menu-pulldown-no-match-note-" hidden></span>'
            "</span></span>"
        )

    # The overview's line linking the timer artifacts archive as raw data,
    # after a blank line, as one table cell. Nothing when none is given.
    def raw_data_render(self, path: str, out_dir: str) -> str:
        if not path:
            return ""
        archive_name = os.path.basename(path)
        line_label = "raw data: "
        archive_link = (
            f'<a href="{theme.html_escape(os.path.relpath(path, out_dir))}"'
            f' target="_blank">{theme.html_escape(archive_name)}</a>'
        )
        raw_data_cell = theme.Cell(
            line_label + archive_name, html=line_label + archive_link
        )
        return self.blank_line_render() + theme.table_render(
            "overview.raw_data",
            [theme.Column("raw data")],
            [[raw_data_cell]],
            column_titles=False,
        )

    # Assemble and write one test's callers page around its top table, a
    # view the overview frames, with no menu of its own.
    def report_page(
        self,
        args: BuildReport.TestArgs,
        heading: str,
        table: str,
    ) -> None:
        body = self.manifest_table(
            "report.header", self.manifest_parse_rows(args.header)
        )
        if args.trace_log:
            body += self.flame_graph_link_render(args.test)
        body += self.output_section("perf log", args.perf_log)
        body += self.output_section("trace log", args.trace_log)
        if not args.no_log:
            body += self.log_section(args.log)
        body += self.heading_render(heading) + table
        self.page_write(
            args.output,
            theme.page_document(
                args.test,
                self.view_main_render(body),
                extra_js=(_ASSET_CALLERS_SCRIPT_NAME,),
                body_class="frame_",
                depth=_CALLERS_PAGE_ASSETS_DEPTH,
            ),
        )

    # Write one test's callers page.
    def test(self, args: BuildReport.TestArgs) -> None:
        profile = callgrind.profile_load(args.callgrind_file)
        callgrind.ranking_counter_check(
            profile.counters, " ".join(args.callgrind_file)
        )
        self.report_page(
            args,
            f"top {_CALLERS_TOP_FUNCTION_ROWS} functions by self",
            self.functions_table(args.test, profile),
        )

    # An overview row's first cell, the test's name, linking the address of
    # its heat map, the view a test opens on.
    def test_link_cell(self, name: str) -> theme.Cell:
        href = theme.html_escape(self.address_of(name, _HEAT_VIEW.key))
        return theme.Cell(
            name, html=f'<a href="{href}">{theme.html_escape(name)}</a>'
        )

    # Rewrite every "Something: 1.23 ms" line in the theme's time notation.
    def time_humanize(self, text: str) -> str:
        return _TIME_LINE.sub(self.time_line_rewrite, text)

    # One matched "Something: 1.23 ms" line, rewritten in the theme's time
    # notation. _TIME_LINE matches exactly the suffixes the setting scales.
    def time_line_rewrite(self, match: re.Match[str]) -> str:
        scale = _CALLERS_TIME_SUFFIX_SECONDS[match.group(3).lower()]
        return match.group(1) + theme.num_time(float(match.group(2)) * scale)

    # The same rewrite for one already split label and value.
    def value_humanize(self, label: str, value: str) -> str:
        line = self.time_humanize(f"{label}: {value}")
        return line.split(": ", 1)[1] if line != f"{label}: {value}" else value

    # A framed view's content in the one box that scrolls it, whose tables
    # size their columns to its width.
    def view_main_render(self, view_content: str) -> str:
        return f'<main><div class="page_">{view_content}</div></main>'


# The flame graph view, linked only where a trace was actually recorded.
_FLAME_VIEW = BuildReport.View(*_FLAME_GRAPH_VIEW_ENTRY[:2])

# The heat map view, which every test has.
_HEAT_VIEW = BuildReport.View(*_HEAT_MAP_VIEW_ENTRY[:2])


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
        help="the native trace run's captured output, shown in a collapsed"
        " 'trace log' section; without it the page has no flame graph link",
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
        "--perf-log",
        action="append",
        metavar="NAME=FILE",
        default=[],
        help="without --diff, a test's perf log as the timing run wrote it,"
        " to read its row from. repeatable, one per --test",
    )
    overview_parser.add_argument(
        "--raw-data",
        default="",
        metavar="FILE",
        help="without --diff, the timer artifacts archive, linked as the"
        " overview's raw data relative to -o",
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
            perf_log=namespace.perf_log,
            raw_data=namespace.raw_data,
        )
        (report.diff_overview if namespace.diff else report.overview)(
            overview_args
        )


if __name__ == "__main__":
    main()
