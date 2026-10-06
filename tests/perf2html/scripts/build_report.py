#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, json, os, re, sys, urllib.parse
from collections.abc import Sequence
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind, callgrind_diff, settings, theme

_ASSET_CALLERS_SCRIPT_NAME: str = ""
_ASSET_FRAME_SCRIPT_NAME: str = ""
_ASSET_MENU_SCRIPT_NAME: str = ""
_ASSET_MENU_STYLESHEET_NAME: str = ""
_ASSET_PULLDOWN_TEXT_SCRIPT_NAME: str = ""
_ASSET_TEMPLATE_CALLERS_PAGE_NAME: str = ""
_ASSET_TEMPLATE_OVERVIEW_PAGE_NAME: str = ""
_CALLERS_TIME_SUFFIX_SECONDS: dict[str, float] = {}
_CALLERS_TOP_FUNCTION_ROWS: int = 0
_CALLERS_VALGRIND_LOG_FIRST_LINE_PATTERN: str = ""
_DIFF_CALLER_COUNTS_FILE_SUFFIX: str = ""
_FLAME_GRAPH_LOCAL_PROFILE_PATH: str = ""
_FLAME_GRAPH_VIEW_ENTRY: tuple[str, str, str] = ("", "", "")
_HEAT_MAP_VIEW_ENTRY: tuple[str, str, str] = ("", "", "")
_RANKING_COUNTER_NAME: str = ""
_REPORT_TEST_SUITE_NAME: str = ""
_STORAGE_KEY_CALLERS_ROWS: str = ""
_STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS: int = 0
_TABLE_ROW_COUNT_CHOICES: tuple[int, ...] = ()
_VALGRIND_DEBUG_LINE_PATTERN: str = ""
settings.load_into(__name__)

_CALLERS_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_CALLERS_PAGE_NAME)

_CALLERS_PAGE_ASSETS_DEPTH = 1

_EXIT_INPUT_UNREADABLE = 20

_PID_PREFIX = re.compile(r"^==\d+==\s?")

_OVERVIEW_PAGE_ASSETS_DEPTH = 0

_OVERVIEW_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_OVERVIEW_PAGE_NAME)

_TIME_SUFFIX_ALTERNATION = "|".join(
    re.escape(suffix) for suffix in sorted(_CALLERS_TIME_SUFFIX_SECONDS)
)

_TIME_LINE = re.compile(
    r"^([ \t]*[A-Za-z][\w/ ]*:[ \t]*)"
    r"(-?\d+(?:\.\d+)?)[ \t]*"
    rf"({_TIME_SUFFIX_ALTERNATION})[ \t]*$",
    re.I | re.M,
)


class BuildReport:
    class CallerShare(NamedTuple):
        function: str
        share_text: str

    class CallersData(NamedTuple):
        callers: dict[str, list[callgrind_diff.CallerDelta]]
        baseline_calls: dict[str, int]

    class FunctionCalls(NamedTuple):
        calls: int
        function: str

    class ManifestBlock(NamedTuple):
        label: str
        pairs: list[BuildReport.ManifestRow]

    class ManifestRow(NamedTuple):
        label: str
        value: str

    class OverviewArgs(NamedTuple):
        output: str
        test: list[str]
        header: list[str]
        header_file: str
        header_block: list[str]
        diff_profile: list[str]
        perf_log: list[str]
        raw_data: str

    class TestArgs(NamedTuple):
        callgrind_file: list[str]
        output: str
        test: str
        log: list[str]
        perf_log: str
        trace_log: str
        no_log: bool
        callers_data: str

    class TestDirectory(NamedTuple):
        name: str
        directory: str

    class View(NamedTuple):
        key: str
        label: str

    def address_of(
        self, test_name: str, view_key: str, function_name: str = ""
    ) -> str:
        hash_text = f"#test={self.address_value_of(test_name)}&view={view_key}"
        if function_name:
            hash_text += f"&function={self.address_value_of(function_name)}"
        if view_key == _FLAME_VIEW.key:
            hash_text += f"&profiler_path={_FLAME_GRAPH_LOCAL_PROFILE_PATH}"
        return hash_text

    def address_value_of(self, value: str) -> str:
        return urllib.parse.quote(value, safe="/-_.!~*'()")

    def baseline_total_load(self, path: str) -> int:
        doc = callgrind_diff.callers_doc_load(path)
        counters = doc["counters"]
        callgrind.ranking_counter_check(counters, path)
        return callgrind.counter_value(
            counters, doc["baselineTotal"], _RANKING_COUNTER_NAME
        )

    def blank_line_render(self) -> str:
        return "<br />"

    def caller_link(
        self,
        test_name: str,
        profile: callgrind.LineProfile,
        caller: BuildReport.CallerShare,
    ) -> str:
        href = self.entry_link(test_name, profile, caller.function)
        label = (
            f"{theme.html_escape(caller.function)}"
            f" ({theme.html_escape(caller.share_text)})"
        )
        return f'<a href="{href}">{label}</a>' if href else label

    # Lists each caller of a function with its share of calls, linked.
    def callers_cell(
        self,
        test_name: str,
        profile: callgrind.LineProfile,
        callers: Sequence[BuildReport.CallerShare],
    ) -> theme.Cell:
        return theme.Cell(
            ", ".join(
                f"{caller.function} ({caller.share_text})"
                for caller in callers
            ),
            html=", ".join(
                self.caller_link(test_name, profile, caller)
                for caller in callers
            ),
        )

    def callers_data_load(self, path: str) -> BuildReport.CallersData:
        if not path:
            sys.exit(
                "error: --diff needs --callers-data, the callgrind_diff.py"
            )
        doc = callgrind_diff.callers_doc_load(path)
        return BuildReport.CallersData(
            callers=doc["callers"], baseline_calls=doc["baselineCalls"]
        )

    def callers_heading_render(self, ranking_text: str) -> str:
        return (
            '<div class="page-heading-"'
            f' data-row-count-key-="{_STORAGE_KEY_CALLERS_ROWS}">'
            'top <span class="page-heading-row-count-">'
            f"{_CALLERS_TOP_FUNCTION_ROWS}</span> functions by"
            f" {theme.html_escape(ranking_text)}</div>"
        )

    def details_section(self, title: str, body: str) -> str:
        return (
            '<details class="callers-collapsed-section-">'
            '<summary class="callers-collapsed-section-title-">'
            f"{theme.html_escape(title)}</summary>{body}</details>"
        )

    def diff_functions_table(
        self,
        test_name: str,
        profile: callgrind.LineProfile,
        callers_data: BuildReport.CallersData,
    ) -> str:
        call_counts = {
            callee: sum(delta.count_ for delta in deltas)
            for callee, deltas in callers_data.callers.items()
        }
        ranked = sorted(
            (
                BuildReport.FunctionCalls(calls, function)
                for function, calls in call_counts.items()
            ),
            key=lambda ranked_function: (
                -abs(ranked_function.calls),
                ranked_function.function,
            ),
        )[: max(_TABLE_ROW_COUNT_CHOICES)]
        columns = self.function_columns()
        rows: list[list[theme.CellOrText]] = []
        for rank, ranked_function in enumerate(ranked, 1):
            call_share = theme.diff_share_of(
                ranked_function.calls,
                callers_data.baseline_calls.get(ranked_function.function),
            )
            rows.append(
                [
                    str(rank),
                    self.function_link_cell(
                        test_name, profile, ranked_function.function
                    ),
                    theme.Cell(
                        theme.num_signed(ranked_function.calls),
                        style=theme.heat_style(
                            theme.heat_of_share(call_share), signed=True
                        ),
                    ),
                    self.callers_cell(
                        test_name,
                        profile,
                        [
                            BuildReport.CallerShare(
                                delta.function,
                                theme.num_signed_pct(
                                    theme.diff_share_of(
                                        delta.count_, delta.baseline_count
                                    )
                                ),
                            )
                            for delta in callers_data.callers[
                                ranked_function.function
                            ]
                        ],
                    ),
                ]
            )
        return theme.table_render("report.functions", columns, rows, fill=True)

    def diff_overview(self, args: BuildReport.OverviewArgs) -> None:
        tests = self.overview_tests(args)
        columns, rows = self.diff_overview_rows(tests, args.diff_profile)
        self.overview_page(args, tests, columns, rows, False)

    def diff_overview_rows(
        self,
        tests: Sequence[BuildReport.TestDirectory],
        diff_profiles: Sequence[str],
    ) -> tuple[list[theme.Column], list[list[theme.CellOrText]]]:
        columns = [
            theme.Column("one report per test"),
            theme.Column(_RANKING_COUNTER_NAME, numeric=True),
            theme.Column("% of change", numeric=True),
            theme.Column(
                f"functions changed in {_RANKING_COUNTER_NAME}", numeric=True
            ),
        ]
        profile_of = self.named_paths_of(diff_profiles, "--diff-profile")
        rows: list[list[theme.CellOrText]] = []
        for test in tests:
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

    def diff_test(self, args: BuildReport.TestArgs) -> None:
        profile = callgrind.profile_load(args.callgrind_file)
        callers_data = self.callers_data_load(args.callers_data)
        self.report_page(
            args,
            self.callers_heading_render("change in calls"),
            self.diff_functions_table(args.test, profile, callers_data),
        )

    def entry_link(
        self, test_name: str, profile: callgrind.LineProfile, function: str
    ) -> str:
        entry = profile.function_entry.get(function)
        if entry is None or not entry.line:
            return ""
        return theme.html_escape(
            self.address_of(test_name, _HEAT_VIEW.key, function)
        )

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

    def flame_graph_link_render(self, test_name: str) -> str:
        href = self.address_of(test_name, _FLAME_VIEW.key)
        return (
            f'<div><a href="{theme.html_escape(href)}">'
            f"{theme.html_escape(_FLAME_VIEW.label)}</a></div>"
        )

    def function_columns(self) -> list[theme.Column]:
        return [
            theme.Column("#", numeric=True),
            theme.Column(
                "symbol", width=_STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS
            ),
            theme.Column("calls", numeric=True),
            theme.Column("callers", grow=True),
        ]

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

    def functions_table(
        self, test_name: str, profile: callgrind.Profile
    ) -> str:
        call_counts = {
            callee: sum(tally.count for tally in callers.values())
            for callee, callers in profile.callers.items()
        }
        calls_total = sum(call_counts.values())
        ranked = sorted(
            (
                BuildReport.FunctionCalls(calls, function)
                for function, calls in call_counts.items()
                if calls > 0
            ),
            key=lambda ranked_function: (
                -ranked_function.calls,
                ranked_function.function,
            ),
        )[: max(_TABLE_ROW_COUNT_CHOICES)]
        columns = self.function_columns()
        rows: list[list[theme.CellOrText]] = []
        for rank, ranked_function in enumerate(ranked, 1):
            call_count = ranked_function.calls
            by_caller: dict[str, int] = {}
            for caller, tally in profile.callers[
                ranked_function.function
            ].items():
                by_caller[caller.function] = (
                    by_caller.get(caller.function, 0) + tally.count
                )
            by_caller_sorted = sorted(
                by_caller.items(), key=lambda pair: (-pair[1], pair[0])
            )
            rows.append(
                [
                    str(rank),
                    self.function_link_cell(
                        test_name, profile, ranked_function.function
                    ),
                    theme.Cell(
                        theme.num_human(call_count),
                        style=theme.heat_style(
                            theme.heat_of_share(
                                100.0 * call_count / calls_total
                            )
                        ),
                    ),
                    self.callers_cell(
                        test_name,
                        profile,
                        [
                            BuildReport.CallerShare(
                                caller_name,
                                theme.num_pct(100.0 * count / calls_total),
                            )
                            for caller_name, count in by_caller_sorted
                        ],
                    ),
                ]
            )
        return theme.table_render("report.functions", columns, rows, fill=True)

    def heading_render(self, text: str) -> str:
        return f'<div class="page-heading-">{theme.html_escape(text)}</div>'

    def log_block(self, path: str) -> str:
        lines = [
            _PID_PREFIX.sub("", line)
            for line in self.file_read(path).rstrip().split("\n")
            if not re.match(_VALGRIND_DEBUG_LINE_PATTERN, line)
        ]
        for index, line in enumerate(lines):
            if re.match(_CALLERS_VALGRIND_LOG_FIRST_LINE_PATTERN, line):
                return self.log_box_render("\n".join(lines[index:]))
        sys.exit(
            f"error: {os.path.abspath(path)}: no line matches"
            f" {_CALLERS_VALGRIND_LOG_FIRST_LINE_PATTERN!r}, the line the"
            " valgrind log section starts at"
        )

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

    def log_box_render(self, text: str) -> str:
        return (
            '<div class="table-box-">'
            '<pre class="callers-collapsed-section-log-box-'
            ' page-text-scroll-box-">'
            f"{theme.html_escape(text)}</pre>"
            + self.text_scrollbar_render("vertical")
            + self.text_scrollbar_render("horizontal")
            + "</div>"
        )

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
        self,
        key: str,
        pairs: Sequence[BuildReport.ManifestRow],
    ) -> str:
        if not pairs:
            return ""
        rows: list[list[theme.CellOrText]] = [
            [pair.label, pair.value] for pair in pairs
        ]
        return theme.table_render(
            key,
            [theme.Column("label"), theme.Column("value", grow=True)],
            rows,
            fill=True,
            column_titles=False,
        )

    # Writes the empty menu strip, its report facts in its attributes.
    def menu_render(
        self, test_names: Sequence[str], has_flame_graph: bool
    ) -> str:
        if _REPORT_TEST_SUITE_NAME not in test_names:
            sys.exit(
                "error: the overview's pulldowns start in"
                f" {_REPORT_TEST_SUITE_NAME!r}, the merged test,"
                f" which is not one of its tests: {' '.join(test_names)}"
            )
        help_href = theme.shared_href(_OVERVIEW_PAGE_ASSETS_DEPTH, "README.md")
        logo_href = theme.shared_href(
            _OVERVIEW_PAGE_ASSETS_DEPTH, "index.html"
        )
        names_text = json.dumps(list(test_names), ensure_ascii=False)
        return (
            '<nav id="menu-" class="menu-strip-"'
            f' data-flame-graph-="{int(has_flame_graph)}"'
            f' data-help-href-="{theme.html_escape(help_href)}"'
            f' data-logo-href-="{theme.html_escape(logo_href)}"'
            f' data-test-names-="{theme.html_escape(names_text)}"></nav>'
        )

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

    def output_section(self, title: str, path: str) -> str:
        if not path:
            return ""
        output = self.time_humanize(self.file_read(path).rstrip())
        return self.details_section(title, self.log_box_render(output))

    def overview(self, args: BuildReport.OverviewArgs) -> None:
        tests = self.overview_tests(args)
        perf_log_of = self.named_paths_of(args.perf_log, "--perf-log")
        keys: list[str] = []
        numbers: dict[str, dict[str, str]] = {}
        for test in tests:
            values: dict[str, str] = {}
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

    def overview_page(
        self,
        args: BuildReport.OverviewArgs,
        tests: Sequence[BuildReport.TestDirectory],
        columns: Sequence[theme.Column],
        rows: Sequence[Sequence[theme.CellOrText]],
        has_flame_graph: bool,
    ) -> None:
        out_dir = os.path.dirname(os.path.abspath(args.output))
        pairs = self.manifest_parse_rows(args.header) + (
            self.manifest_read_file(args.header_file)
            if args.header_file
            else []
        )
        manifest_blocks = [BuildReport.ManifestBlock("manifest", pairs)]
        manifest_blocks += self.manifest_parse_blocks(args.header_block)
        raw_data_markup = self.raw_data_render(args.raw_data, out_dir)
        tests_markup = theme.table_render("overview.tests", columns, rows)
        manifest_markup = self.manifest_blocks_render(
            "overview.block", manifest_blocks
        )
        menu_markup = self.menu_render(
            [test.name for test in tests], has_flame_graph
        )
        page_content = theme.template_fill(
            _OVERVIEW_PAGE,
            {
                "__MENU__": menu_markup,
                "__RAW_DATA__": raw_data_markup,
                "__MANIFEST__": manifest_markup,
                "__TESTS__": tests_markup,
            },
        )
        self.page_write(
            args.output,
            theme.page_document(
                "overview",
                page_content,
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

    def report_page(
        self,
        args: BuildReport.TestArgs,
        heading_markup: str,
        table: str,
    ) -> None:
        flame_graph_markup = (
            self.flame_graph_link_render(args.test) if args.trace_log else ""
        )
        perf_log_markup = self.output_section("perf log", args.perf_log)
        trace_log_markup = self.output_section("trace log", args.trace_log)
        valgrind_log_markup = "" if args.no_log else self.log_section(args.log)
        page_content = theme.template_fill(
            _CALLERS_PAGE,
            {
                "__FLAME_GRAPH_LINK__": flame_graph_markup,
                "__PERF_LOG__": perf_log_markup,
                "__TRACE_LOG__": trace_log_markup,
                "__VALGRIND_LOG__": valgrind_log_markup,
                "__HEADING__": heading_markup,
                "__FUNCTIONS__": table,
            },
        )
        self.page_write(
            args.output,
            theme.page_document(
                args.test,
                page_content,
                extra_js=(_ASSET_CALLERS_SCRIPT_NAME,),
                body_class="frame_",
                depth=_CALLERS_PAGE_ASSETS_DEPTH,
                extra_css=(_ASSET_MENU_STYLESHEET_NAME,),
            ),
        )

    def test(self, args: BuildReport.TestArgs) -> None:
        profile = callgrind.profile_load(args.callgrind_file)
        self.report_page(
            args,
            self.callers_heading_render("calls"),
            self.functions_table(args.test, profile),
        )

    def test_link_cell(self, name: str) -> theme.Cell:
        href = theme.html_escape(self.address_of(name, _HEAT_VIEW.key))
        return theme.Cell(
            name, html=f'<a href="{href}">{theme.html_escape(name)}</a>'
        )

    def text_scrollbar_render(self, axis_name: str) -> str:
        return (
            f'<div class="page-text-scrollbar- {axis_name}_"'
            ' aria-hidden="true"></div>'
        )

    def time_humanize(self, text: str) -> str:
        return _TIME_LINE.sub(self.time_line_rewrite, text)

    def time_line_rewrite(self, match: re.Match[str]) -> str:
        scale = _CALLERS_TIME_SUFFIX_SECONDS[match.group(3).lower()]
        return match.group(1) + theme.num_time(float(match.group(2)) * scale)

    def value_humanize(self, label: str, value: str) -> str:
        line = self.time_humanize(f"{label}: {value}")
        return line.split(": ", 1)[1] if line != f"{label}: {value}" else value


_FLAME_VIEW = BuildReport.View(*_FLAME_GRAPH_VIEW_ENTRY[:2])

_HEAT_VIEW = BuildReport.View(*_HEAT_MAP_VIEW_ENTRY[:2])


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
