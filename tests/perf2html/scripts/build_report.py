#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, json, os, re, sys, urllib.parse
from collections.abc import Callable, Sequence
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind, callgrind_diff, settings, theme

_ASSET_CALLERS_SCRIPT_NAME: str = ""
_ASSET_DEBUG_SCRIPT_NAME: str = ""
_ASSET_FRAME_SCRIPT_NAME: str = ""
_ASSET_MENU_SCRIPT_NAME: str = ""
_ASSET_MENU_STYLESHEET_NAME: str = ""
_ASSET_OVERVIEW_SCRIPT_NAME: str = ""
_ASSET_PULLDOWN_TEXT_SCRIPT_NAME: str = ""
_ASSET_SETTINGS_PAGE_SCRIPT_NAME: str = ""
_ASSET_TEMPLATE_CALLERS_PAGE_NAME: str = ""
_ASSET_TEMPLATE_OVERVIEW_PAGE_NAME: str = ""
_ASSET_TEMPLATE_SETTINGS_PAGE_NAME: str = ""
_CALLERS_PAGE_DIR_NAME: str = ""
_CALLERS_TIME_SUFFIX_SECONDS: dict[str, float] = {}
_DIFF_CALLER_COUNTS_FILE_SUFFIX: str = ""
_FLAME_GRAPH_LOCAL_PROFILE_PATH: str = ""
_FLAME_GRAPH_VIEW_ENTRY: tuple[str, str] = ("", "")
_HEAT_MAP_VIEW_ENTRY: tuple[str, str] = ("", "")
_OVERVIEW_VALGRIND_LOG_FIRST_LINE_PATTERN: str = ""
_RANKING_COUNTER_NAME: str = ""
_REPORT_TEST_SUITE_NAME: str = ""
_SETTINGS_VIEW_ENTRY: tuple[str, str] = ("", "")
_TABLE_ROW_COUNT_CHOICES: tuple[int, ...] = ()
_VALGRIND_DEBUG_LINE_PATTERN: str = ""
settings.load_into(__name__)

_CALLERS_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_CALLERS_PAGE_NAME)

_CALLERS_PAGE_ASSETS_DEPTH = 1

_DEBUG_SCRIPT = theme.asset_text_read(_ASSET_DEBUG_SCRIPT_NAME)

_EXIT_INPUT_UNREADABLE = 20

_FLAME_GRAPH_VIEW_KEY = _FLAME_GRAPH_VIEW_ENTRY[0]

_HEAT_MAP_VIEW_KEY = _HEAT_MAP_VIEW_ENTRY[0]

_PID_PREFIX = re.compile(r"^==\d+==\s?")

_SETTINGS_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_SETTINGS_PAGE_NAME)

_SETTINGS_PAGE_ASSETS_DEPTH = 1

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
        heading_markup: str
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
        trace_log: list[str]
        valgrind_log: list[str]
        raw_data: str

    class TestArgs(NamedTuple):
        callgrind_file: list[str]
        report_dir: str
        test: str
        callers_data: str

    class TestDirectory(NamedTuple):
        name: str
        directory: str

    def address_of(
        self, test_name: str, view_key: str, function_name: str = ""
    ) -> str:
        hash_text = f"#test={self.address_value_of(test_name)}&view={view_key}"
        if function_name:
            hash_text += f"&function={self.address_value_of(function_name)}"
        if view_key == _FLAME_GRAPH_VIEW_KEY:
            hash_text += f"&localProfilePath={_FLAME_GRAPH_LOCAL_PROFILE_PATH}"
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
        return theme.render_element("br", {}, None)

    def caller_link(
        self,
        test_name: str,
        profile: callgrind.LineProfile,
        caller: BuildReport.CallerShare,
    ) -> str:
        href = self.entry_link(test_name, profile, caller.function)
        label = theme.render_html_escape(
            f"{caller.function} ({caller.share_text})"
        )
        if not href:
            return label
        return theme.render_menu_button(
            "link", label, theme.MenuButtonFields("a", href)
        )

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

    # Writes the report's debug script, its manifest table filled in.
    def debug_script_write(
        self, assets_dir: str, manifest_lines: Sequence[str]
    ) -> None:
        table_text = json.dumps(
            settings.manifest_table(manifest_lines), ensure_ascii=False
        )
        path = os.path.join(assets_dir, _ASSET_DEBUG_SCRIPT_NAME)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                theme.template_fill(
                    _DEBUG_SCRIPT, {"__MANIFEST_TABLE__": table_text}
                )
            )

    def details_section(self, section_id: str, body: str) -> str:
        return theme.render_element(
            "details",
            {"id": section_id, "class": "overview-collapsed-section-"},
            theme.render_menu_button(
                "action", "", theme.MenuButtonFields("summary")
            )
            + body,
        )

    def diff_functions_rows(
        self,
        test_name: str,
        profile: callgrind.LineProfile,
        callers_data: BuildReport.CallersData,
    ) -> list[list[theme.CellOrText]]:
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
        return rows

    def diff_overview(self, args: BuildReport.OverviewArgs) -> None:
        tests = self.overview_tests(args)
        rows = self.diff_overview_rows(tests, args.diff_profile)
        self.overview_page(args, tests, [], rows, True)

    def diff_overview_rows(
        self,
        tests: Sequence[BuildReport.TestDirectory],
        diff_profiles: Sequence[str],
    ) -> list[list[theme.CellOrText]]:
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
        return rows

    def diff_test(self, args: BuildReport.TestArgs) -> None:
        profile = callgrind.profile_load(args.callgrind_file)
        callers_data = self.callers_data_load(args.callers_data)
        self.report_page(
            args,
            True,
            self.diff_functions_rows(args.test, profile, callers_data),
        )

    def entry_link(
        self, test_name: str, profile: callgrind.LineProfile, function: str
    ) -> str:
        entry = profile.function_entry.get(function)
        if entry is None or not entry.line:
            return ""
        return self.address_of(test_name, _HEAT_MAP_VIEW_KEY, function)

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

    def function_link_cell(
        self, test_name: str, profile: callgrind.LineProfile, function: str
    ) -> theme.Cell:
        return theme.Cell(
            function, href=self.entry_link(test_name, profile, function)
        )

    def functions_rows(
        self, test_name: str, profile: callgrind.Profile
    ) -> list[list[theme.CellOrText]]:
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
        return rows

    def log_block(self, path: str) -> str:
        lines = [
            _PID_PREFIX.sub("", line)
            for line in self.file_read(path).rstrip().split("\n")
            if not re.match(_VALGRIND_DEBUG_LINE_PATTERN, line)
        ]
        for index, line in enumerate(lines):
            if re.match(_OVERVIEW_VALGRIND_LOG_FIRST_LINE_PATTERN, line):
                return self.log_box_render("\n".join(lines[index:]))
        sys.exit(
            f"error: {os.path.abspath(path)}: no line matches"
            f" {_OVERVIEW_VALGRIND_LOG_FIRST_LINE_PATTERN!r}, the line the"
            " valgrind log section starts at"
        )

    # Writes one collapsed section holding each named test's log in turn.
    def logs_section(
        self,
        section_id: str,
        tests: Sequence[BuildReport.TestDirectory],
        paths: Sequence[str],
        flag: str,
        box_of: Callable[[str], str],
    ) -> str:
        path_of = self.named_paths_of(paths, flag)
        test_names = [test.name for test in tests]
        for name in path_of:
            if name not in test_names:
                sys.exit(f"error: {flag} names no --test: {name}")
        if not path_of:
            return ""
        body = "".join(
            theme.render_element(
                "div",
                {"class": "overview-collapsed-section-test-name-"},
                theme.render_html_escape(name),
            )
            + box_of(path_of[name])
            for name in test_names
            if name in path_of
        )
        return self.blank_line_render() + self.details_section(
            section_id, body
        )

    def log_box_render(self, text: str) -> str:
        return theme.render_element(
            "div",
            {"class": "table-box-"},
            theme.render_element(
                "pre",
                {
                    "class": "overview-collapsed-section-log-box-"
                    " page-text-scroll-box-"
                },
                theme.render_html_escape(text),
            )
            + self.text_scrollbar_render("vertical")
            + self.text_scrollbar_render("horizontal"),
        )

    def manifest_blocks_render(
        self,
        key: str,
        blocks: Sequence[BuildReport.ManifestBlock],
    ) -> str:
        return self.blank_line_render().join(
            block.heading_markup
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
                    theme.render_heading(
                        theme.render_html_escape(label.strip())
                    ),
                    self.manifest_read_file(path),
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
        return self.table_data_render(
            {"class": "overview-manifest-table-"}, key, rows
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
        help_href = theme.href(_OVERVIEW_PAGE_ASSETS_DEPTH, "README.md")
        names_text = json.dumps(list(test_names), ensure_ascii=False)
        return theme.render_element(
            "nav",
            {
                "id": "menu-",
                "class": "menu-strip-",
                "data-flame-graph-": str(int(has_flame_graph)),
                "data-help-href-": help_href,
                "data-test-names-": names_text,
            },
            "",
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
        rows: list[list[theme.CellOrText]] = [
            [self.test_link_cell(test.name)]
            + [numbers[test.name].get(key, "") for key in keys]
            for test in tests
        ]
        self.overview_page(args, tests, keys, rows, False)

    def overview_page(
        self,
        args: BuildReport.OverviewArgs,
        tests: Sequence[BuildReport.TestDirectory],
        column_labels: Sequence[str],
        rows: Sequence[Sequence[theme.CellOrText]],
        is_diff: bool,
    ) -> None:
        out_dir = os.path.dirname(os.path.abspath(args.output))
        pairs = self.manifest_parse_rows(args.header) + (
            self.manifest_read_file(args.header_file)
            if args.header_file
            else []
        )
        manifest_blocks = [
            BuildReport.ManifestBlock(
                theme.render_heading("", "overview-manifest-heading-"), pairs
            )
        ]
        manifest_blocks += self.manifest_parse_blocks(args.header_block)
        raw_data_markup = self.raw_data_render(args.raw_data, out_dir)
        tests_markup = self.table_data_render(
            {
                "id": "overview-tests-table-",
                "data-diff-": str(int(is_diff)),
                "data-column-labels-": json.dumps(
                    list(column_labels), ensure_ascii=False
                ),
            },
            "overview.tests",
            rows,
        )
        manifest_markup = self.manifest_blocks_render(
            "overview.block", manifest_blocks
        )
        menu_markup = self.menu_render(
            [test.name for test in tests], not is_diff
        )
        page_content = theme.template_fill(
            _OVERVIEW_PAGE,
            {
                "__MENU__": menu_markup,
                "__OVERVIEW_HEADING__": theme.render_heading(
                    "", "overview-title-heading-"
                ),
                "__RAW_DATA__": raw_data_markup,
                "__MANIFEST__": manifest_markup,
                "__TESTS_HEADING__": theme.render_heading(
                    "", "overview-tests-heading-"
                ),
                "__TESTS__": tests_markup,
                "__PERF_LOG__": self.logs_section(
                    "overview-collapsed-section-perf-log-",
                    tests,
                    args.perf_log,
                    "--perf-log",
                    self.output_box_render,
                ),
                "__TRACE_LOG__": self.logs_section(
                    "overview-collapsed-section-trace-log-",
                    tests,
                    args.trace_log,
                    "--trace-log",
                    self.output_box_render,
                ),
                "__VALGRIND_LOG__": self.logs_section(
                    "overview-collapsed-section-valgrind-log-",
                    tests,
                    args.valgrind_log,
                    "--valgrind-log",
                    self.log_block,
                ),
            },
        )
        self.page_write(
            args.output,
            theme.page_document(
                "",
                page_content,
                extra_js=(
                    _ASSET_OVERVIEW_SCRIPT_NAME,
                    _ASSET_PULLDOWN_TEXT_SCRIPT_NAME,
                    _ASSET_FRAME_SCRIPT_NAME,
                    _ASSET_MENU_SCRIPT_NAME,
                ),
                body_class="frame-",
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

    # Writes a captured output in a log box, its times humanized.
    def output_box_render(self, path: str) -> str:
        return self.log_box_render(
            self.time_humanize(self.file_read(path).rstrip())
        )

    def raw_data_render(self, path: str, out_dir: str) -> str:
        if not path:
            return ""
        return self.blank_line_render() + theme.render_element(
            "div",
            {"id": "overview-raw-data-"},
            theme.render_menu_button(
                "link",
                "",
                theme.MenuButtonFields(
                    "a", os.path.relpath(path, out_dir), opens_new_tab=True
                ),
            ),
        )

    def report_page(
        self,
        args: BuildReport.TestArgs,
        is_diff: bool,
        rows: Sequence[Sequence[theme.CellOrText]],
    ) -> None:
        page_content = theme.template_fill(
            _CALLERS_PAGE,
            {
                "__FUNCTIONS__": self.table_data_render(
                    {
                        "id": "callers-functions-table-",
                        "data-diff-": str(int(is_diff)),
                    },
                    "report.functions",
                    rows,
                ),
            },
        )
        self.page_write(
            os.path.join(
                args.report_dir, _CALLERS_PAGE_DIR_NAME, f"{args.test}.html"
            ),
            theme.page_document(
                args.test,
                page_content,
                extra_js=(_ASSET_CALLERS_SCRIPT_NAME,),
                body_class="frame-",
                depth=_CALLERS_PAGE_ASSETS_DEPTH,
                extra_css=(_ASSET_MENU_STYLESHEET_NAME,),
            ),
        )

    # Writes the settings view, the settings relayed to it.
    def settings_page(self, report_dir: str) -> None:
        self.page_write(
            os.path.join(report_dir, _SETTINGS_VIEW_ENTRY[1]),
            theme.page_document(
                "",
                _SETTINGS_PAGE,
                extra_js=(_ASSET_SETTINGS_PAGE_SCRIPT_NAME,),
                body_class="frame-",
                depth=_SETTINGS_PAGE_ASSETS_DEPTH,
                extra_css=(_ASSET_MENU_STYLESHEET_NAME,),
            ),
        )

    def test(self, args: BuildReport.TestArgs) -> None:
        profile = callgrind.profile_load(args.callgrind_file)
        self.report_page(args, False, self.functions_rows(args.test, profile))

    # Writes the rows a page script draws as the table the key names.
    def table_data_render(
        self,
        attributes: dict[str, str],
        key: str,
        rows: Sequence[Sequence[theme.CellOrText]],
    ) -> str:
        return theme.render_element(
            "div",
            attributes
            | {"data-key-": key, "data-rows-": theme.table_rows_text(rows)},
            "",
        )

    def test_link_cell(self, name: str) -> theme.Cell:
        return theme.Cell(name, href=self.address_of(name, _HEAT_MAP_VIEW_KEY))

    def text_scrollbar_render(self, axis_name: str) -> str:
        return theme.render_element(
            "div",
            {
                "class": f"page-text-scrollbar- {axis_name}-",
                "aria-hidden": "true",
            },
            "",
        )

    def time_humanize(self, text: str) -> str:
        return _TIME_LINE.sub(self.time_line_rewrite, text)

    def time_line_rewrite(self, match: re.Match[str]) -> str:
        scale = _CALLERS_TIME_SUFFIX_SECONDS[match.group(3).lower()]
        return match.group(1) + theme.num_time(float(match.group(2)) * scale)

    def value_humanize(self, label: str, value: str) -> str:
        line = self.time_humanize(f"{label}: {value}")
        return line.split(": ", 1)[1] if line != f"{label}: {value}" else value


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    test_parser = subparsers.add_parser(
        "test", help="one perf test's callers page"
    )
    test_parser.add_argument(
        "callgrind_file",
        nargs="+",
        help="callgrind output file(s). several are merged into one profile",
    )
    test_parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="the report directory to write"
        f" {_CALLERS_PAGE_DIR_NAME}/<test>.html into",
    )
    test_parser.add_argument(
        "--test", required=True, help="the page's title and file name"
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

    debug_parser = subparsers.add_parser(
        "debug", help="the report's debug script, holding its manifest table"
    )
    debug_parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="the directory to write the debug script to",
    )
    debug_parser.add_argument(
        "manifest_line",
        nargs="+",
        help="every argument is a LABEL=VALUE manifest row, the version line"
        " first under its label, the checksum left out",
    )

    settings_parser = subparsers.add_parser(
        "settings",
        help="the settings view, editing the settings while settings"
        " debugging is enabled",
    )
    settings_parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="the report directory to write the settings view into",
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
        help="a test the overview lists, its callers page written by"
        " the test subcommand (repeatable)",
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
        " to read its row from and show in a collapsed 'perf log' section."
        " repeatable, one per --test",
    )
    overview_parser.add_argument(
        "--trace-log",
        action="append",
        metavar="NAME=FILE",
        default=[],
        help="without --diff, a test's native trace run output, shown in a"
        " collapsed 'trace log' section. repeatable",
    )
    overview_parser.add_argument(
        "--valgrind-log",
        action="append",
        metavar="NAME=FILE",
        default=[],
        help="without --diff, a test's valgrind log, shown in a collapsed"
        " 'valgrind log' section. repeatable",
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
    elif namespace.cmd == "debug":
        report.debug_script_write(namespace.output, namespace.manifest_line)
    elif namespace.cmd == "settings":
        report.settings_page(namespace.output)
    elif namespace.cmd == "test":
        test_args = BuildReport.TestArgs(
            callgrind_file=namespace.callgrind_file,
            report_dir=namespace.output,
            test=namespace.test,
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
            trace_log=namespace.trace_log,
            valgrind_log=namespace.valgrind_log,
            raw_data=namespace.raw_data,
        )
        (report.diff_overview if namespace.diff else report.overview)(
            overview_args
        )


if __name__ == "__main__":
    main()
