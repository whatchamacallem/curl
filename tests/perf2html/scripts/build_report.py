#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, json, os, sys, urllib.parse
from collections.abc import Container, Iterable, Sequence
from typing import NamedTuple, NotRequired, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artifacts, callgrind, callgrind_diff, callgrind_to_heatmap
import perf_measure, settings, theme

_ASSET_DEBUG_SCRIPT_NAME: str = ""
_ASSET_TEMPLATE_CALL_GRAPH_PAGE_NAME: str = ""
_ASSET_TEMPLATE_DATABASE_PAGE_NAME: str = ""
_ASSET_TEMPLATE_OVERVIEW_PAGE_NAME: str = ""
_ASSET_TEMPLATE_SETTINGS_PAGE_NAME: str = ""
_CALL_GRAPH_PAGE_DIR_NAME: str = ""
_DATABASE_PAGE_DIR_NAME: str = ""
_DATABASE_VIEW_KEY: str = ""
_FLAME_GRAPH_LOCAL_PROFILE_PATH: str = ""
_FLAME_GRAPH_VIEW_ENTRY: tuple[str, str] = ("", "")
_HEAT_MAP_VIEW_ENTRY: tuple[str, str] = ("", "")
_OVERVIEW_PAGE_PATH: str = ""
_PROFILE_START_FUNCTION_NAME: str = ""
_PROFILE_START_FUNCTION_UNRECORDED_CALLS: int = 0
_RANKING_COUNTER_NAME: str = ""
_README_HTML_NAME: str = ""
_README_MARKDOWN_NAME: str = ""
_REPORT_SCRIPTS_DIR_NAME: str = ""
_SETTINGS_HELD_SCRIPT_TEMPLATE_ID: str = ""
_SETTINGS_VIEW_ENTRY: tuple[str, str] = ("", "")
settings.load_into(__name__)

_CALL_GRAPH_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_CALL_GRAPH_PAGE_NAME)

_DATABASE_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_DATABASE_PAGE_NAME)

_DEBUG_SCRIPT = theme.asset_text_read(_ASSET_DEBUG_SCRIPT_NAME)

_FLAME_GRAPH_VIEW_KEY = _FLAME_GRAPH_VIEW_ENTRY[0]

_HEAT_MAP_VIEW_KEY = _HEAT_MAP_VIEW_ENTRY[0]

_SETTINGS_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_SETTINGS_PAGE_NAME)

_OVERVIEW_PAGE_SCRIPTS_DEPTH = 0

_OVERVIEW_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_OVERVIEW_PAGE_NAME)


class BuildReport:
    class CallChange(NamedTuple):
        calls: int
        baseline_calls: int

    class CallGraphArgs(NamedTuple):
        artifacts: str
        report: str

    class CallGraphEdge(NamedTuple):
        caller: int
        callee: int
        calls: int
        line: int
        inclusive_value: int

    class CallGraphFunction(NamedTuple):
        name: str
        self_value: int

    class CallGraphModel(TypedDict):
        functions: list[BuildReport.CallGraphFunction]
        roots: list[BuildReport.CallGraphRoot]
        edges: list[BuildReport.CallGraphEdge]
        test_total: int

    class CallGraphRoot(NamedTuple):
        function: int
        calls: int

    class CallRow(NamedTuple):
        function: int
        calls: int

    class DatabaseArgs(NamedTuple):
        artifacts: str
        report: str
        diff: bool

    class DatabaseModel(TypedDict):
        counterNames: list[str]
        counterTotals: NotRequired[list[int]]
        derivedCounters: list[callgrind.ResolvedDerivedCounter]
        functions: list[BuildReport.FunctionLink]
        functionRows: (
            list[BuildReport.FunctionRow] | list[BuildReport.DiffFunctionRow]
        )

    class DiffCallRow(NamedTuple):
        function: int
        calls: int
        baseline_calls: int

    class DiffFunctionRow(NamedTuple):
        function: int
        file: str
        line: int
        calls: int
        values: list[int]
        callers: list[BuildReport.DiffCallRow]
        callees: list[BuildReport.DiffCallRow]
        baseline_calls: int
        baseline_values: list[int]

    class FunctionLink(NamedTuple):
        name: str
        href: str

    class FunctionRow(NamedTuple):
        function: int
        file: str
        line: int
        calls: int
        values: list[int]
        callers: list[BuildReport.CallRow]
        callees: list[BuildReport.CallRow]

    class ManifestBlock(NamedTuple):
        heading_markup: str
        pairs: list[BuildReport.ManifestRow]

    class ManifestRow(NamedTuple):
        label: str
        value: str

    class ReportArgs(NamedTuple):
        artifacts: str
        report: str
        diff: bool

    def __init__(self, verbose: int) -> None:
        self.verbose = verbose

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

    def blank_line_render(self) -> str:
        return theme.render_element("br", {}, None)

    # Writes every listed test's call graph page from its recording.
    def call_graph(self, args: BuildReport.CallGraphArgs) -> None:
        artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        for test_name in artifacts.test_list_read(artifacts_dir):
            profile = callgrind.profile_load(
                artifacts_dir, "callgrind", test_name
            )
            callgrind.ranking_counter_check(
                profile.counters,
                artifacts.artifact_path(artifacts_dir, "callgrind", test_name),
            )
            self.call_graph_page(
                args.report,
                test_name,
                self.call_graph_model(test_name, profile),
            )

    # Returns each caller and callee pair's calls, first call line and costs.
    def call_graph_edges(
        self, profile: callgrind.Profile
    ) -> dict[tuple[str, str], callgrind.CallerCalls]:
        edges: dict[tuple[str, str], callgrind.CallerCalls] = {}
        for callee_name in profile.callers:
            for caller_name, entry in callgrind.caller_calls(
                profile, callee_name
            ).items():
                edges[(caller_name, callee_name)] = entry
        return edges

    # Lists the test's functions and call edges, their costs, roots and total.
    def call_graph_model(
        self, test_name: str, profile: callgrind.Profile
    ) -> BuildReport.CallGraphModel:
        edges = self.call_graph_edges(profile)
        call_graph_functions = [
            BuildReport.CallGraphFunction(
                function_name,
                callgrind.counter_value(
                    profile.counters,
                    profile.function_self.get(function_name, []),
                    _RANKING_COUNTER_NAME,
                ),
            )
            for function_name in sorted(
                {name for pair in edges for name in pair}
            )
        ]
        index_by_name = {
            function.name: index
            for index, function in enumerate(call_graph_functions)
        }
        # A root is uncalled, so the recording holds no call of it.
        return {
            "functions": call_graph_functions,
            "roots": [
                BuildReport.CallGraphRoot(
                    index_by_name[root_name], self.function_calls(root_name, 0)
                )
                for root_name in self.call_graph_roots(test_name, edges)
            ],
            "edges": [
                BuildReport.CallGraphEdge(
                    index_by_name[caller_name],
                    index_by_name[callee_name],
                    tally.calls,
                    tally.line,
                    callgrind.counter_value(
                        profile.counters, tally.costs, _RANKING_COUNTER_NAME
                    ),
                )
                for (caller_name, callee_name), tally in sorted(edges.items())
            ],
            "test_total": callgrind.counter_value(
                profile.counters, profile.totals(), _RANKING_COUNTER_NAME
            ),
        }

    # Writes a test's call graph page, holding the model its script lays out.
    def call_graph_page(
        self,
        report_dir: str,
        test_name: str,
        call_graph_model: BuildReport.CallGraphModel,
    ) -> None:
        model_text = json.dumps(
            call_graph_model, separators=(",", ":"), ensure_ascii=False
        )
        page_content = theme.template_fill(
            _CALL_GRAPH_PAGE,
            {
                "__HELD_SCRIPT_TEMPLATE_ID__": theme.render_html_escape(
                    _SETTINGS_HELD_SCRIPT_TEMPLATE_ID
                ),
                "__PAGE_TITLE__": theme.render_html_escape(test_name),
                "__CALL_GRAPH__": theme.render_element(
                    "table",
                    {"id": "call-graph-table-", "data-model-": model_text},
                    "",
                ),
            },
        )
        self.page_write(
            os.path.join(
                report_dir, _CALL_GRAPH_PAGE_DIR_NAME, f"{test_name}.html"
            ),
            page_content,
        )

    # Returns every uncalled caller, refusing a function none of them reaches.
    def call_graph_roots(
        self, test_name: str, pairs: Iterable[tuple[str, str]]
    ) -> list[str]:
        callee_names: dict[str, list[str]] = {}
        for caller_name, callee_name in pairs:
            callee_names.setdefault(caller_name, []).append(callee_name)
        called_names = {
            name for names in callee_names.values() for name in names
        }
        root_names = sorted(set(callee_names) - called_names)
        if not root_names:
            sys.exit(
                f"error: {test_name}'s call graph has no uncalled function"
                " to start at"
            )
        reached_names = set(root_names)
        pending_names = list(root_names)
        while pending_names:
            for callee_name in callee_names.get(pending_names.pop(), []):
                if callee_name not in reached_names:
                    reached_names.add(callee_name)
                    pending_names.append(callee_name)
        unreached_names = sorted(called_names - reached_names)
        if unreached_names:
            sys.exit(
                f"error: {test_name}'s call graph reaches"
                f" {' '.join(unreached_names)} from none of its uncalled"
                f" functions {' '.join(root_names)}"
            )
        return root_names

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

    # Writes every listed test's database page, a diff's of the delta.
    def database(self, args: BuildReport.DatabaseArgs) -> None:
        artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        for test_name in artifacts.test_list_read(artifacts_dir):
            database_model = (
                self.diff_database_model(artifacts_dir, test_name)
                if args.diff
                else self.database_model(
                    test_name,
                    callgrind.profile_load(
                        artifacts_dir, "callgrind", test_name
                    ),
                )
            )
            self.database_page(
                args.report, test_name, args.diff, database_model
            )

    # Lists each function the test calls, where it is, its calls and counters.
    def database_model(
        self, test_name: str, profile: callgrind.Profile
    ) -> BuildReport.DatabaseModel:
        edges = self.call_graph_edges(profile)
        recorded_calls: dict[str, int] = {}
        for (_, callee_name), tally in edges.items():
            recorded_calls[callee_name] = (
                recorded_calls.get(callee_name, 0) + tally.calls
            )
        calls_by_name = {
            name: self.function_calls(name, recorded_calls.get(name, 0))
            for name in profile.function_home
        }
        row_names = {
            name for name, calls in calls_by_name.items() if calls > 0
        }
        named_names = row_names | {name for pair in edges for name in pair}
        locations = callgrind_to_heatmap.CallgrindToHeatmap(
            self.verbose
        ).function_locations(
            profile, self.file_display_paths(profile), named_names
        )
        function_links = self.function_links(
            test_name,
            named_names,
            {name for name, location in locations.items() if location.line},
        )
        index_by_name = {
            link.name: index for index, link in enumerate(function_links)
        }
        callers: dict[str, list[BuildReport.CallRow]] = {}
        callees: dict[str, list[BuildReport.CallRow]] = {}
        for (caller_name, callee_name), tally in sorted(
            edges.items(), key=lambda item: (-item[1].calls, item[0])
        ):
            callers.setdefault(callee_name, []).append(
                BuildReport.CallRow(index_by_name[caller_name], tally.calls)
            )
            callees.setdefault(caller_name, []).append(
                BuildReport.CallRow(index_by_name[callee_name], tally.calls)
            )
        counter_names = list(profile.counters)
        row_order = sorted(row_names, key=lambda name: (locations[name], name))
        return {
            "counterNames": counter_names,
            "counterTotals": self.counter_values(
                profile.counters, profile.totals(), counter_names
            ),
            "derivedCounters": profile.resolved_derived_counters(),
            "functions": function_links,
            "functionRows": [
                BuildReport.FunctionRow(
                    index_by_name[name],
                    locations[name].file,
                    locations[name].line,
                    calls_by_name[name],
                    self.counter_values(
                        profile.counters,
                        profile.function_self.get(name, []),
                        counter_names,
                    ),
                    callers.get(name, []),
                    callees.get(name, []),
                )
                for name in row_order
            ],
        }

    # Writes a test's database page, holding the model its script draws.
    def database_page(
        self,
        report_dir: str,
        test_name: str,
        is_diff: bool,
        database_model: BuildReport.DatabaseModel,
    ) -> None:
        model_text = json.dumps(
            database_model, separators=(",", ":"), ensure_ascii=False
        )
        page_content = theme.template_fill(
            _DATABASE_PAGE,
            {
                "__HELD_SCRIPT_TEMPLATE_ID__": theme.render_html_escape(
                    _SETTINGS_HELD_SCRIPT_TEMPLATE_ID
                ),
                "__PAGE_TITLE__": theme.render_html_escape(test_name),
                "__DATABASE__": theme.render_element(
                    "div",
                    {
                        "id": "database-model-",
                        "data-diff-": str(int(is_diff)),
                        "data-model-": model_text,
                    },
                    "",
                ),
            },
        )
        self.page_write(
            os.path.join(
                report_dir, _DATABASE_PAGE_DIR_NAME, f"{test_name}.html"
            ),
            page_content,
        )

    # Writes the report's debug script, its manifest table filled in.
    def debug_script_write(
        self, report_dir: str, manifest_lines: Sequence[str]
    ) -> None:
        table_text = json.dumps(
            settings.manifest_table(manifest_lines), ensure_ascii=False
        )
        path = os.path.join(
            report_dir, _REPORT_SCRIPTS_DIR_NAME, _ASSET_DEBUG_SCRIPT_NAME
        )
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                theme.template_fill(
                    _DEBUG_SCRIPT, {"__MANIFEST_TABLE__": table_text}
                )
            )

    # Lists each function either side calls, its change beside its baselines.
    def diff_database_model(
        self, artifacts_dir: str, test_name: str
    ) -> BuildReport.DatabaseModel:
        function_diff = callgrind_diff.function_diff_load(
            artifacts_dir, test_name
        )
        derived = callgrind.DerivedPaths(
            *(
                artifacts.artifact_path(artifacts_dir, kind)
                for kind in ("baseline-profiles", "modified-profiles")
            )
        )
        diff_rows = {
            row.function_name: row for row in function_diff["functions"]
        }
        diff_names = list(diff_rows)
        call_changes: dict[tuple[str, str], BuildReport.CallChange] = {}
        caller_changes: dict[str, list[BuildReport.CallChange]] = {}
        for caller_name, diff_row in diff_rows.items():
            for call_row in diff_row.callee_rows:
                callee_name = diff_names[call_row.function_index]
                change = BuildReport.CallChange(
                    call_row.call_count, call_row.baseline_count
                )
                call_changes[(caller_name, callee_name)] = change
                caller_changes.setdefault(callee_name, []).append(change)
        calls_by_name = {
            name: self.diff_function_calls(name, caller_changes.get(name, []))
            for name in diff_names
        }
        # A row is a function called on one side at least.
        row_names = {
            name
            for name, (calls, baseline_calls) in calls_by_name.items()
            if baseline_calls or baseline_calls + calls
        }
        named_names = set(row_names)
        for pair in call_changes:
            if row_names.intersection(pair):
                named_names.update(pair)
        locations = {
            name: callgrind.SourceLine(
                derived.display(
                    function_diff["files"][diff_rows[name].file_index],
                    function_diff["images"][diff_rows[name].image_index],
                ),
                diff_rows[name].line_number,
            )
            for name in named_names
        }
        function_links = self.function_links(
            test_name,
            named_names,
            {name for name, location in locations.items() if location.line},
        )
        index_by_name = {
            link.name: index for index, link in enumerate(function_links)
        }
        callers: dict[str, list[BuildReport.DiffCallRow]] = {}
        callees: dict[str, list[BuildReport.DiffCallRow]] = {}
        for (caller_name, callee_name), (calls, baseline_calls) in sorted(
            call_changes.items(),
            key=lambda item: (-abs(item[1].calls), item[0]),
        ):
            if callee_name in row_names:
                callers.setdefault(callee_name, []).append(
                    BuildReport.DiffCallRow(
                        index_by_name[caller_name], calls, baseline_calls
                    )
                )
            if caller_name in row_names:
                callees.setdefault(caller_name, []).append(
                    BuildReport.DiffCallRow(
                        index_by_name[callee_name], calls, baseline_calls
                    )
                )
        counters = function_diff["counters"]
        counter_names = list(counters)
        row_order = sorted(row_names, key=lambda name: (locations[name], name))
        return {
            "counterNames": counter_names,
            "derivedCounters": callgrind.resolved_derived_counters(counters),
            "functions": function_links,
            "functionRows": [
                BuildReport.DiffFunctionRow(
                    index_by_name[name],
                    locations[name].file,
                    locations[name].line,
                    calls_by_name[name][0],
                    self.counter_values(
                        counters, diff_rows[name].self_costs, counter_names
                    ),
                    callers.get(name, []),
                    callees.get(name, []),
                    calls_by_name[name][1],
                    self.counter_values(
                        counters, diff_rows[name].baseline_costs, counter_names
                    ),
                )
                for name in row_order
            ],
        }

    # Returns a function's change of calls and its baseline calls.
    def diff_function_calls(
        self,
        function_name: str,
        caller_changes: Sequence[BuildReport.CallChange],
    ) -> tuple[int, int]:
        baseline_calls = self.function_calls(
            function_name,
            sum(change.baseline_calls for change in caller_changes),
        )
        modified_calls = self.function_calls(
            function_name,
            sum(
                change.baseline_calls + change.calls
                for change in caller_changes
            ),
        )
        return modified_calls - baseline_calls, baseline_calls

    # Writes the diff's overview page, a row of each test's change.
    def diff_overview(
        self, args: BuildReport.ReportArgs, has_readme_html: bool
    ) -> None:
        artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        test_names = artifacts.test_list_read(artifacts_dir)
        rows = self.diff_overview_rows(artifacts_dir, test_names)
        counters = callgrind.counters_read(
            artifacts_dir, "delta", test_names[0]
        )
        self.overview_page(
            args.report,
            test_names,
            rows,
            self.manifest_blocks_read(artifacts_dir, True),
            "",
            counters,
            True,
            has_readme_html,
        )

    # Returns a row per test, each timing value's change from its baseline.
    def diff_overview_rows(
        self, artifacts_dir: str, test_names: Sequence[str]
    ) -> list[list[theme.CellOrText]]:
        measure = perf_measure.PerfMeasure()
        baseline_document = measure.timing_data_read(
            artifacts.artifact_path(artifacts_dir, "baseline-profiles")
        )
        modified_document = measure.timing_data_read(
            artifacts.artifact_path(artifacts_dir, "modified-profiles")
        )
        rows: list[list[theme.CellOrText]] = []
        for test_name in test_names:
            rows.append(
                [
                    self.test_link_cell(test_name),
                    *(
                        self.timing_change_cell(
                            baseline_document[test_name][value_name],
                            modified_document[test_name][value_name],
                        )
                        for value_name in baseline_document[test_name]
                    ),
                ]
            )
        return rows

    # Returns the path the heat map shows for each file the profile names.
    def file_display_paths(self, profile: callgrind.Profile) -> dict[str, str]:
        raw_paths = (
            {key.file for key in profile.line_self}
            | {key.file for key in profile.line_calls}
            | {entry.file for entry in profile.function_entry.values()}
        )
        shown_paths: dict[str, str] = {}
        for raw_path in sorted(raw_paths):
            path_info = callgrind.path_norm(raw_path)
            shown_paths[raw_path] = callgrind.display_path(
                path_info.display,
                path_info.group,
                profile.file_image[raw_path],
            )
        return shown_paths

    # Returns the recorded calls, a settings count for an uncalled start.
    def function_calls(self, function_name: str, recorded_calls: int) -> int:
        if (
            function_name == _PROFILE_START_FUNCTION_NAME
            and not recorded_calls
        ):
            return _PROFILE_START_FUNCTION_UNRECORDED_CALLS
        return recorded_calls

    # Returns each named function, the linked ones with their heat map address.
    def function_links(
        self,
        test_name: str,
        function_names: set[str],
        linked_names: Container[str],
    ) -> list[BuildReport.FunctionLink]:
        return [
            BuildReport.FunctionLink(
                function_name,
                self.address(test_name, _HEAT_MAP_VIEW_KEY, function_name)
                if function_name in linked_names
                else "",
            )
            for function_name in sorted(function_names)
        ]

    # Returns the header tables, the run's own rows or each diffed report's.
    def manifest_blocks_read(
        self, artifacts_dir: str, is_diff: bool
    ) -> list[BuildReport.ManifestBlock]:
        if not is_diff:
            return [
                BuildReport.ManifestBlock(
                    theme.render_heading("", "overview-manifest-heading-"),
                    self.manifest_read(artifacts_dir, "header-rows"),
                )
            ]
        return [
            BuildReport.ManifestBlock(
                theme.render_heading(theme.render_html_escape(label)),
                self.manifest_read(artifacts_dir, kind),
            )
            for label, kind in (
                ("baseline", "baseline-header"),
                ("modified", "modified-header"),
            )
        ]

    def manifest_blocks_render(
        self, blocks: Sequence[BuildReport.ManifestBlock]
    ) -> str:
        return self.blank_line_render().join(
            block.heading_markup + self.manifest_table(block.pairs)
            for block in blocks
            if block.pairs
        )

    # Returns a header file's label and value rows, any other line left out.
    def manifest_read(
        self, artifacts_dir: str, kind: str
    ) -> list[BuildReport.ManifestRow]:
        with artifacts.artifact_open(artifacts_dir, kind) as handle:
            lines = handle.read().splitlines()
        return [
            BuildReport.ManifestRow(label.strip(), value)
            for label, _, value in (
                line.partition("=")
                for line in lines
                if line.strip() and "=" in line
            )
        ]

    # Writes the manifest rows as the text table the error page shows too.
    def manifest_table(self, pairs: Sequence[BuildReport.ManifestRow]) -> str:
        return theme.render_element(
            "pre",
            {},
            "\n".join(
                theme.render_element(
                    "span",
                    {"class": "overview-manifest-label-"},
                    theme.render_html_escape(label_cell),
                )
                + theme.render_html_escape(value_cell)
                for label_cell, value_cell in settings.manifest_table_rows(
                    [f"{pair.label}={pair.value}" for pair in pairs]
                )
            ),
        )

    # Writes the empty menu and preference strips, the menu holding the facts.
    def menu_render(
        self,
        test_names: Sequence[str],
        counters: Sequence[str],
        is_diff: bool,
        has_readme_html: bool,
    ) -> str:
        help_href = theme.href(
            _OVERVIEW_PAGE_SCRIPTS_DEPTH,
            _README_HTML_NAME if has_readme_html else _README_MARKDOWN_NAME,
        )
        names_text = json.dumps(list(test_names), ensure_ascii=False)
        menu_markup = theme.render_element(
            "nav",
            {
                "id": "menu-",
                "class": "strip-",
                "data-counter-names-": json.dumps(
                    callgrind.counter_names(counters)
                ),
                "data-help-href-": help_href,
                "data-regular-report-": str(int(not is_diff)),
                "data-test-names-": names_text,
            },
            "",
        )
        return menu_markup + theme.render_element(
            "div", {"id": "menu-preference-", "class": "strip-"}, ""
        )

    # Writes the overview page, a row of each test's timing page.
    def overview(
        self, args: BuildReport.ReportArgs, has_readme_html: bool
    ) -> None:
        artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        test_names = artifacts.test_list_read(artifacts_dir)
        rows = self.timing_rows(artifacts_dir, test_names)
        raw_data_path = artifacts.raw_data_archive_path(
            args.report, artifacts.recorded_time_read(artifacts_dir)
        )
        counters = callgrind.counters_read(
            artifacts_dir, "callgrind", test_names[0]
        )
        self.overview_page(
            args.report,
            test_names,
            rows,
            self.manifest_blocks_read(artifacts_dir, False),
            os.path.basename(raw_data_path),
            counters,
            False,
            has_readme_html,
        )

    def overview_page(
        self,
        report_dir: str,
        test_names: Sequence[str],
        rows: Sequence[Sequence[theme.CellOrText]],
        manifest_blocks: Sequence[BuildReport.ManifestBlock],
        raw_data_name: str,
        counters: Sequence[str],
        is_diff: bool,
        has_readme_html: bool,
    ) -> None:
        raw_data_markup = self.raw_data_render(raw_data_name)
        tests_markup = self.table_data_render(
            {"id": "overview-tests-table-"}, "overview.tests", rows
        )
        manifest_markup = self.manifest_blocks_render(manifest_blocks)
        menu_markup = self.menu_render(
            test_names, counters, is_diff, has_readme_html
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
        self.page_write(
            os.path.join(report_dir, _OVERVIEW_PAGE_PATH), page_content
        )

    def page_write(self, path: str, page: str) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(page)
        if self.verbose:
            print(f"wrote {path} ({len(page.encode('utf-8')):,} bytes)")

    # Writes the blank line and the raw data heading over the archive link.
    def raw_data_render(self, name: str) -> str:
        if not name:
            return ""
        raw_data_markup = theme.render_element(
            "div",
            {"id": "overview-raw-data-"},
            theme.render_element("a", {"href": name, "target": "_blank"}, ""),
        )
        return (
            self.blank_line_render()
            + theme.render_heading("", "overview-raw-data-heading-")
            + raw_data_markup
        )

    # Writes the report's one shared copy of the theme.
    def scripts_write(self, report_dir: str) -> None:
        theme.theme_scripts_write(
            os.path.join(report_dir, _REPORT_SCRIPTS_DIR_NAME)
        )

    # Writes the settings view, the settings relayed to it.
    def settings_page(self, report_dir: str) -> None:
        self.page_write(
            os.path.join(report_dir, _SETTINGS_VIEW_ENTRY[1]),
            theme.template_fill(
                _SETTINGS_PAGE,
                {
                    "__HELD_SCRIPT_TEMPLATE_ID__": theme.render_html_escape(
                        _SETTINGS_HELD_SCRIPT_TEMPLATE_ID
                    )
                },
            ),
        )

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
        return theme.Cell(name, href=self.address(name, _DATABASE_VIEW_KEY))

    # Returns a timing value's change from its baseline, none beside a 0.
    def timing_change_cell(
        self, baseline_value: float, modified_value: float
    ) -> theme.CellOrText:
        if not baseline_value or not modified_value:
            return ""
        change_share = theme.diff_share(
            modified_value - baseline_value, baseline_value
        )
        return theme.Cell(
            theme.num_signed_pct(change_share), heat_percent=change_share
        )

    # Returns a row per test, its timing document's time per loop and ratios.
    def timing_rows(
        self, artifacts_dir: str, test_names: Sequence[str]
    ) -> list[list[theme.CellOrText]]:
        measure = perf_measure.PerfMeasure()
        timing_document = measure.timing_data_read(artifacts_dir)
        rows: list[list[theme.CellOrText]] = []
        for test_name in test_names:
            rows.append(
                [
                    self.test_link_cell(test_name),
                    *(
                        text
                        for _, text in measure.timing_texts(
                            timing_document[test_name]
                        )
                    ),
                ]
            )
        return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    database_parser = subparsers.add_parser(
        "database", help="every listed test's callers page"
    )
    database_parser.add_argument(
        "--diff",
        action="store_true",
        help="the recordings are callgrind_diff.py deltas: each callee's"
        " change of calls and counters beside its baseline, signed",
    )

    call_graph_parser = subparsers.add_parser(
        "call-graph", help="every listed test's call graph page"
    )

    scripts_parser = subparsers.add_parser(
        "scripts", help="the report's one shared copy of the theme"
    )

    debug_parser = subparsers.add_parser(
        "debug", help="the report's debug script, holding its manifest table"
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

    overview_parser = subparsers.add_parser(
        "overview", help="the page over several tests"
    )
    overview_parser.add_argument(
        "--diff",
        action="store_true",
        help="the reports are callgrind_diff.py deltas: summarize each"
        " test's change instead of its native timing, which a diff does"
        " not have",
    )
    overview_parser.add_argument(
        "--readme-html",
        action="store_true",
        help=f"the report holds {_README_HTML_NAME}, which the help link"
        f" opens instead of {_README_MARKDOWN_NAME}",
    )

    for report_parser in (
        call_graph_parser,
        database_parser,
        scripts_parser,
        debug_parser,
        settings_parser,
        overview_parser,
    ):
        report_parser.add_argument(
            "--report",
            required=True,
            metavar="DIR",
            help="the report directory the files are written in",
        )
        report_parser.add_argument(
            "--verbose",
            action="count",
            default=0,
            help="print each file written; a quiet run prints nothing on"
            " success",
        )
    for artifacts_parser in (
        call_graph_parser,
        database_parser,
        overview_parser,
    ):
        artifacts_parser.add_argument(
            "--artifacts",
            required=True,
            metavar="DIR",
            help="the profiler artifacts directory, holding the report's own,"
            " whose test list names every test shown",
        )

    namespace = parser.parse_args()
    report = BuildReport(namespace.verbose)
    if namespace.cmd == "scripts":
        report.scripts_write(namespace.report)
    elif namespace.cmd == "debug":
        report.debug_script_write(namespace.report, namespace.manifest_line)
    elif namespace.cmd == "settings":
        report.settings_page(namespace.report)
    elif namespace.cmd == "call-graph":
        report.call_graph(
            BuildReport.CallGraphArgs(
                artifacts=namespace.artifacts, report=namespace.report
            )
        )
    elif namespace.cmd == "database":
        report.database(
            BuildReport.DatabaseArgs(
                artifacts=namespace.artifacts,
                report=namespace.report,
                diff=namespace.diff,
            )
        )
    else:
        (report.diff_overview if namespace.diff else report.overview)(
            BuildReport.ReportArgs(
                artifacts=namespace.artifacts,
                report=namespace.report,
                diff=namespace.diff,
            ),
            namespace.readme_html,
        )


if __name__ == "__main__":
    main()
