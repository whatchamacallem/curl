#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, json, os, re, sys, urllib.parse
from collections.abc import Iterable, Mapping, Sequence
from typing import NamedTuple, NotRequired, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind, callgrind_diff, settings, theme

_ASSET_DEBUG_SCRIPT_NAME: str = ""
_ASSET_TEMPLATE_CALLERS_PAGE_NAME: str = ""
_ASSET_TEMPLATE_OVERVIEW_PAGE_NAME: str = ""
_ASSET_TEMPLATE_SETTINGS_PAGE_NAME: str = ""
_CALLERS_PAGE_DIR_NAME: str = ""
_CALLERS_TIME_SUFFIX_SECONDS: dict[str, float] = {}
_CALLGRIND_OUTPUT_FILE_EXTENSION: str = ""
_DIFF_CALLER_COUNTS_FILE_EXTENSION: str = ""
_FLAME_GRAPH_LOCAL_PROFILE_PATH: str = ""
_FLAME_GRAPH_VIEW_ENTRY: tuple[str, str] = ("", "")
_HEAT_MAP_VIEW_ENTRY: tuple[str, str] = ("", "")
_RANKING_COUNTER_NAME: str = ""
_REPORT_TEST_SUITE_NAME: str = ""
_SETTINGS_VIEW_ENTRY: tuple[str, str] = ("", "")
settings.load_into(__name__)

_CALLERS_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_CALLERS_PAGE_NAME)

_DEBUG_SCRIPT = theme.asset_text_read(_ASSET_DEBUG_SCRIPT_NAME)

_FLAME_GRAPH_VIEW_KEY = _FLAME_GRAPH_VIEW_ENTRY[0]

_HEAT_MAP_VIEW_KEY = _HEAT_MAP_VIEW_ENTRY[0]

_SETTINGS_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_SETTINGS_PAGE_NAME)

_OVERVIEW_PAGE_SCRIPTS_DEPTH = 0

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
    class CalleeRow(NamedTuple):
        function: int
        calls: int
        values: list[int]
        callers: list[BuildReport.CallerRow]

    class CallerRow(NamedTuple):
        function: int
        calls: int

    class CallersData(NamedTuple):
        callers: dict[str, list[callgrind_diff.CallerDelta]]
        baseline_calls: dict[str, int]
        baseline: dict[str, callgrind.Costs]
        counters: list[str]

    class CallersModel(TypedDict):
        counterNames: list[str]
        counterTotals: NotRequired[list[int]]
        functions: list[BuildReport.FunctionLink]
        callees: list[BuildReport.CalleeRow] | list[BuildReport.DiffCalleeRow]

    class DiffCalleeRow(NamedTuple):
        function: int
        calls: int
        values: list[int]
        callers: list[BuildReport.DiffCallerRow]
        baseline_calls: int | None
        baseline_values: list[int]

    class DiffCallerRow(NamedTuple):
        function: int
        calls: int
        baseline_calls: int

    class FunctionLink(NamedTuple):
        name: str
        href: str

    class ManifestBlock(NamedTuple):
        heading_markup: str
        pairs: list[BuildReport.ManifestRow]

    class ManifestRow(NamedTuple):
        label: str
        value: str

    class OverviewArgs(NamedTuple):
        output: str
        header: list[str]
        header_file: str
        header_block: list[str]
        diff_profile: str
        profile: str
        perf_log: str
        raw_data: str

    class TestArgs(NamedTuple):
        callgrind_file: list[str]
        report_dir: str
        test: str
        callers_data: str

    class TestDirectory(NamedTuple):
        name: str
        directory: str

    def address(
        self, test_name: str, view_key: str, function_name: str = ""
    ) -> str:
        hash_text = f"#test={self.address_value(test_name)}&view={view_key}"
        if function_name:
            hash_text += f"&function={self.address_value(function_name)}"
        if view_key == _FLAME_GRAPH_VIEW_KEY:
            hash_text += f"&localProfilePath={_FLAME_GRAPH_LOCAL_PROFILE_PATH}"
        return hash_text

    def address_value(self, value: str) -> str:
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

    def callers_data_load(self, path: str) -> BuildReport.CallersData:
        if not path:
            print(
                "error: --diff needs --callers-data, the callgrind_diff.py",
                file=sys.stderr,
            )
            sys.exit(2)
        doc = callgrind_diff.callers_doc_load(path)
        return BuildReport.CallersData(
            callers=doc["callers"],
            baseline_calls=doc["baselineCalls"],
            baseline=doc["baseline"],
            counters=doc["counters"],
        )

    # Lists every called function with its calls, counters and callers.
    def callers_model(
        self, test_name: str, profile: callgrind.Profile
    ) -> BuildReport.CallersModel:
        caller_counts_by_callee: dict[str, list[tuple[str, int]]] = {}
        for callee_name, caller_tallies in profile.callers.items():
            count_by_caller: dict[str, int] = {}
            for caller, tally in caller_tallies.items():
                count_by_caller[caller.function] = (
                    count_by_caller.get(caller.function, 0) + tally.count
                )
            if sum(count_by_caller.values()) > 0:
                caller_counts_by_callee[callee_name] = sorted(
                    count_by_caller.items(),
                    key=lambda pair: (-pair[1], pair[0]),
                )
        function_names = set(caller_counts_by_callee)
        for caller_counts in caller_counts_by_callee.values():
            function_names.update(
                caller_name for caller_name, _ in caller_counts
            )
        function_links = self.function_links(
            test_name, profile, function_names
        )
        index_by_name = {
            link.name: index for index, link in enumerate(function_links)
        }
        counter_names = callgrind.counter_names(profile.counters)
        callee_rows: list[BuildReport.CalleeRow] = []
        for callee_name, caller_counts in sorted(
            caller_counts_by_callee.items()
        ):
            callee_rows.append(
                BuildReport.CalleeRow(
                    index_by_name[callee_name],
                    sum(call_count for _, call_count in caller_counts),
                    self.counter_values(
                        profile.counters,
                        profile.function_self.get(callee_name, []),
                        counter_names,
                    ),
                    [
                        BuildReport.CallerRow(
                            index_by_name[caller_name], call_count
                        )
                        for caller_name, call_count in caller_counts
                    ],
                )
            )
        return {
            "counterNames": counter_names,
            "counterTotals": self.counter_values(
                profile.counters, profile.totals(), counter_names
            ),
            "functions": function_links,
            "callees": callee_rows,
        }

    # Returns each named counter's value in the costs.
    def counter_values(
        self,
        counters: Sequence[str],
        costs: callgrind.Costs,
        counter_names: Sequence[str],
    ) -> list[int]:
        return [
            callgrind.counter_value(counters, costs, counter_name)
            for counter_name in counter_names
        ]

    # Writes the report's debug script, its manifest table filled in.
    def debug_script_write(
        self, scripts_dir: str, manifest_lines: Sequence[str]
    ) -> None:
        table_text = json.dumps(
            settings.manifest_table(manifest_lines), ensure_ascii=False
        )
        path = os.path.join(scripts_dir, _ASSET_DEBUG_SCRIPT_NAME)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                theme.template_fill(
                    _DEBUG_SCRIPT, {"__MANIFEST_TABLE__": table_text}
                )
            )

    # Lists every function with a changed caller, its changes and baselines.
    def diff_callers_model(
        self,
        test_name: str,
        profile: callgrind.LineProfile,
        callers_data: BuildReport.CallersData,
    ) -> BuildReport.CallersModel:
        function_names = set(callers_data.callers)
        for deltas in callers_data.callers.values():
            function_names.update(delta.function for delta in deltas)
        function_links = self.function_links(
            test_name, profile, function_names
        )
        index_by_name = {
            link.name: index for index, link in enumerate(function_links)
        }
        counter_names = callgrind.counter_names(profile.counters)
        callee_rows: list[BuildReport.DiffCalleeRow] = []
        for callee_name, deltas in sorted(callers_data.callers.items()):
            callee_rows.append(
                BuildReport.DiffCalleeRow(
                    index_by_name[callee_name],
                    sum(delta.count_ for delta in deltas),
                    self.counter_values(
                        profile.counters,
                        profile.function_self.get(callee_name, []),
                        counter_names,
                    ),
                    [
                        BuildReport.DiffCallerRow(
                            index_by_name[delta.function],
                            delta.count_,
                            delta.baseline_count,
                        )
                        for delta in deltas
                    ],
                    callers_data.baseline_calls.get(callee_name),
                    self.counter_values(
                        callers_data.counters,
                        callers_data.baseline.get(callee_name, []),
                        counter_names,
                    ),
                )
            )
        return {
            "counterNames": counter_names,
            "functions": function_links,
            "callees": callee_rows,
        }

    def diff_overview(self, args: BuildReport.OverviewArgs) -> None:
        profile_paths = callgrind.named_paths(args.diff_profile)
        tests = self.overview_tests(args, profile_paths)
        rows = self.diff_overview_rows(tests, profile_paths)
        profile = callgrind.profile_load(
            [profile_paths[_REPORT_TEST_SUITE_NAME]]
        )
        self.overview_page(
            args,
            tests,
            [],
            rows,
            callgrind.counter_names(profile.counters),
            True,
        )

    def diff_overview_rows(
        self,
        tests: Sequence[BuildReport.TestDirectory],
        profile_paths: Mapping[str, str],
    ) -> list[list[theme.CellOrText]]:
        rows: list[list[theme.CellOrText]] = []
        for test in tests:
            profile_path = profile_paths[test.name]
            callers = profile_path.removesuffix(
                f".{_CALLGRIND_OUTPUT_FILE_EXTENSION}"
            )
            callers = f"{callers}.{_DIFF_CALLER_COUNTS_FILE_EXTENSION}"
            link = self.test_link_cell(test.name)
            profile = callgrind.profile_load([profile_path])
            callgrind.ranking_counter_check(profile.counters, profile_path)
            delta = profile.value(profile.totals(), _RANKING_COUNTER_NAME)
            changed = sum(
                1
                for costs in profile.function_self.values()
                if profile.value(costs, _RANKING_COUNTER_NAME) != 0
            )
            share = theme.diff_share(delta, self.baseline_total_load(callers))
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
            self.diff_callers_model(args.test, profile, callers_data),
        )

    def entry_link(
        self, test_name: str, profile: callgrind.LineProfile, function: str
    ) -> str:
        entry = profile.function_entry.get(function)
        if entry is None or not entry.line:
            return ""
        return self.address(test_name, _HEAT_MAP_VIEW_KEY, function)

    def file_read(self, path: str) -> str:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                return handle.read()
        except OSError as error:
            sys.exit(
                f"error: {os.path.abspath(path)}: {error}: the page cannot"
                " be built without it"
            )

    # Returns each named function with its heat map address, the names sorted.
    def function_links(
        self,
        test_name: str,
        profile: callgrind.LineProfile,
        function_names: set[str],
    ) -> list[BuildReport.FunctionLink]:
        return [
            BuildReport.FunctionLink(
                function_name,
                self.entry_link(test_name, profile, function_name),
            )
            for function_name in sorted(function_names)
        ]

    def manifest_blocks_render(
        self, blocks: Sequence[BuildReport.ManifestBlock]
    ) -> str:
        return self.blank_line_render().join(
            block.heading_markup + self.manifest_table(block.pairs)
            for block in blocks
            if block.pairs
        )

    def manifest_parse_blocks(
        self, items: Sequence[str]
    ) -> list[BuildReport.ManifestBlock]:
        out: list[BuildReport.ManifestBlock] = []
        for item in items:
            if "=" not in item:
                print(
                    f"error: --header-block expects LABEL=FILE, got {item!r}",
                    file=sys.stderr,
                )
                sys.exit(2)
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
                print(
                    f"error: --header expects LABEL=VALUE, got {item!r}",
                    file=sys.stderr,
                )
                sys.exit(2)
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

    # Writes the manifest rows as the text table the error page shows too.
    def manifest_table(self, pairs: Sequence[BuildReport.ManifestRow]) -> str:
        return theme.render_element(
            "pre",
            {},
            theme.render_html_escape(
                settings.manifest_table(
                    [f"{pair.label}={pair.value}" for pair in pairs]
                )
            ),
        )

    # Writes the empty menu and preference strips, the menu holding the facts.
    def menu_render(
        self,
        test_names: Sequence[str],
        counter_names: Sequence[str],
        is_diff: bool,
    ) -> str:
        if _REPORT_TEST_SUITE_NAME not in test_names:
            sys.exit(
                "error: the overview's pulldowns start in"
                f" {_REPORT_TEST_SUITE_NAME!r}, the merged test,"
                f" which is not one of its tests: {' '.join(test_names)}"
            )
        help_href = theme.href(_OVERVIEW_PAGE_SCRIPTS_DEPTH, "README.md")
        names_text = json.dumps(list(test_names), ensure_ascii=False)
        menu_markup = theme.render_element(
            "nav",
            {
                "id": "menu-",
                "class": "strip-",
                "data-counter-names-": json.dumps(list(counter_names)),
                "data-diff-": str(int(is_diff)),
                "data-flame-graph-": str(int(not is_diff)),
                "data-help-href-": help_href,
                "data-test-names-": names_text,
            },
            "",
        )
        return menu_markup + theme.render_element(
            "div", {"id": "menu-preference-", "class": "strip-"}, ""
        )

    def overview(self, args: BuildReport.OverviewArgs) -> None:
        perf_log = callgrind.named_paths(args.perf_log)
        tests = self.overview_tests(args, perf_log)
        keys: list[str] = []
        numbers: dict[str, dict[str, str]] = {}
        for test in tests:
            values: dict[str, str] = {}
            for line in self.file_read(perf_log[test.name]).splitlines():
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
        profile = callgrind.profile_load(
            list(callgrind.named_paths(args.profile).values())
        )
        self.overview_page(
            args,
            tests,
            keys,
            rows,
            callgrind.counter_names(profile.counters),
            False,
        )

    def overview_page(
        self,
        args: BuildReport.OverviewArgs,
        tests: Sequence[BuildReport.TestDirectory],
        column_labels: Sequence[str],
        rows: Sequence[Sequence[theme.CellOrText]],
        counter_names: Sequence[str],
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
        manifest_markup = self.manifest_blocks_render(manifest_blocks)
        menu_markup = self.menu_render(
            [test.name for test in tests], counter_names, is_diff
        )
        page_content = theme.template_fill(
            _OVERVIEW_PAGE,
            {
                "__MENU__": menu_markup,
                "__RAW_DATA__": raw_data_markup,
                "__MANIFEST__": manifest_markup,
                "__TESTS_HEADING__": theme.render_heading(
                    "", "overview-tests-heading-"
                ),
                "__TESTS__": tests_markup,
            },
        )
        self.page_write(args.output, page_content)

    def overview_tests(
        self, args: BuildReport.OverviewArgs, test_names: Iterable[str]
    ) -> list[BuildReport.TestDirectory]:
        out_dir = os.path.dirname(os.path.abspath(args.output))
        tests = [
            BuildReport.TestDirectory(name, os.path.join(out_dir, name))
            for name in test_names
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
        raw_data_markup = theme.render_element(
            "div",
            {"id": "overview-raw-data-"},
            theme.render_element(
                "a",
                {"href": os.path.relpath(path, out_dir), "target": "_blank"},
                "",
            ),
        )
        return raw_data_markup + self.blank_line_render()

    # Writes a test's callers page, holding the model its script draws.
    def report_page(
        self,
        args: BuildReport.TestArgs,
        is_diff: bool,
        callers_model: BuildReport.CallersModel,
    ) -> None:
        model_text = json.dumps(
            callers_model, separators=(",", ":"), ensure_ascii=False
        )
        page_content = theme.template_fill(
            _CALLERS_PAGE,
            {
                "__PAGE_TITLE__": theme.render_html_escape(args.test),
                "__FUNCTIONS__": theme.render_element(
                    "div",
                    {
                        "id": "callers-functions-table-",
                        "data-diff-": str(int(is_diff)),
                        "data-key-": "report.functions",
                        "data-model-": model_text,
                    },
                    "",
                ),
            },
        )
        self.page_write(
            os.path.join(
                args.report_dir, _CALLERS_PAGE_DIR_NAME, f"{args.test}.html"
            ),
            page_content,
        )

    # Writes the settings view, the settings relayed to it.
    def settings_page(self, report_dir: str) -> None:
        self.page_write(
            os.path.join(report_dir, _SETTINGS_VIEW_ENTRY[1]), _SETTINGS_PAGE
        )

    def test(self, args: BuildReport.TestArgs) -> None:
        profile = callgrind.profile_load(args.callgrind_file)
        self.report_page(args, False, self.callers_model(args.test, profile))

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
        return theme.Cell(name, href=self.address(name, _HEAT_MAP_VIEW_KEY))

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

    scripts_parser = subparsers.add_parser(
        "scripts", help="the report's one shared copy of the theme"
    )
    scripts_parser.add_argument(
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
        "--diff-profile",
        metavar="PATTERN",
        default="",
        help="with --diff, every test's subtracted profile as"
        " callgrind_diff.py wrote it, one * for the test, each read for its"
        " row (its synthesized callers diff is that name with the extension"
        f" .{_DIFF_CALLER_COUNTS_FILE_EXTENSION})",
    )
    overview_parser.add_argument(
        "--profile",
        metavar="PATTERN",
        default="",
        help="without --diff, every test's callgrind file, one * for the"
        " test, whose counters the menu offers",
    )
    overview_parser.add_argument(
        "--perf-log",
        metavar="PATTERN",
        default="",
        help="without --diff, every test's perf log as the timing run wrote"
        " it, one * for the test, each read for its row in the tests table",
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
    if namespace.cmd == "scripts":
        theme.theme_scripts_write(namespace.output)
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
            header=namespace.header,
            header_file=namespace.header_file,
            header_block=namespace.header_block,
            diff_profile=namespace.diff_profile,
            profile=namespace.profile,
            perf_log=namespace.perf_log,
            raw_data=namespace.raw_data,
        )
        (report.diff_overview if namespace.diff else report.overview)(
            overview_args
        )


if __name__ == "__main__":
    main()
