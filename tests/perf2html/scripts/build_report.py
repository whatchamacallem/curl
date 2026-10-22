#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, json, os, re, sys, urllib.parse
from collections.abc import Iterable, Sequence
from typing import NamedTuple, NotRequired, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artifacts, callgrind, callgrind_diff, callgrind_to_heatmap
import settings, theme

_ASSET_DEBUG_SCRIPT_NAME: str = ""
_ASSET_TEMPLATE_CALL_GRAPH_PAGE_NAME: str = ""
_ASSET_TEMPLATE_DATABASE_PAGE_NAME: str = ""
_ASSET_TEMPLATE_OVERVIEW_PAGE_NAME: str = ""
_ASSET_TEMPLATE_SETTINGS_PAGE_NAME: str = ""
_CALL_GRAPH_PAGE_DIR_NAME: str = ""
_DATABASE_PAGE_DIR_NAME: str = ""
_DATABASE_TIME_SUFFIX_SECONDS: dict[str, float] = {}
_DATABASE_VIEW_KEY: str = ""
_FLAME_GRAPH_LOCAL_PROFILE_PATH: str = ""
_FLAME_GRAPH_VIEW_ENTRY: tuple[str, str] = ("", "")
_HEAT_MAP_VIEW_ENTRY: tuple[str, str] = ("", "")
_OVERVIEW_PAGE_PATH: str = ""
_PERF_TOOL_TIME_LABEL: str = ""
_PROFILE_START_FUNCTION_NAME: str = ""
_PROFILE_START_FUNCTION_UNRECORDED_CALLS: int = 0
_RANKING_COUNTER_NAME: str = ""
_README_HTML_NAME: str = ""
_README_MARKDOWN_NAME: str = ""
_REPORT_SCRIPTS_DIR_NAME: str = ""
_SETTINGS_VIEW_ENTRY: tuple[str, str] = ("", "")
_TIMING_COUNTER_LABELS: dict[str, str] = {}
_TIMING_COUNTER_RATIO_DIVIDEND: str = ""
_TIMING_COUNTER_RATIO_DIVISOR: str = ""
settings.load_into(__name__)

_CALL_GRAPH_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_CALL_GRAPH_PAGE_NAME)

_DATABASE_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_DATABASE_PAGE_NAME)

_DEBUG_SCRIPT = theme.asset_text_read(_ASSET_DEBUG_SCRIPT_NAME)

_FLAME_GRAPH_VIEW_KEY = _FLAME_GRAPH_VIEW_ENTRY[0]

_HEAT_MAP_VIEW_KEY = _HEAT_MAP_VIEW_ENTRY[0]

_SETTINGS_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_SETTINGS_PAGE_NAME)

_OVERVIEW_PAGE_SCRIPTS_DEPTH = 0

_OVERVIEW_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_OVERVIEW_PAGE_NAME)

_PERF_TOOL_TIME_LINE = re.compile(
    rf"{re.escape(_PERF_TOOL_TIME_LABEL)}:\s+(\d+(?:\.\d+)?)\s*("
    + "|".join(map(re.escape, sorted(_DATABASE_TIME_SUFFIX_SECONDS)))
    + r")\s*"
)


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

    class CallGraphRoot(NamedTuple):
        function: int
        calls: int

    class CallRow(NamedTuple):
        function: int
        calls: int

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
                if entry.calls:
                    edges[(caller_name, callee_name)] = entry
        return edges

    # Lists the test's functions and call edges, their costs, and its roots.
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
    def database(self, args: BuildReport.ReportArgs) -> None:
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
        function_links = self.function_links(
            test_name,
            profile,
            row_names | {name for pair in edges for name in pair},
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
        locations = self.function_locations(
            profile, self.file_display_paths(profile, None), row_names
        )
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

    # Lists each changed function either side calls, beside its baselines.
    def diff_database_model(
        self, artifacts_dir: str, test_name: str
    ) -> BuildReport.DatabaseModel:
        delta = callgrind.profile_load(artifacts_dir, "delta", test_name)
        callers_doc = callgrind_diff.callers_doc_load(artifacts_dir, test_name)
        baseline_dir, modified_dir = (
            artifacts.artifact_path(artifacts_dir, kind)
            for kind in ("baseline-profiles", "modified-profiles")
        )
        baseline_edges, modified_edges = (
            self.call_graph_edges(
                callgrind.profile_load(profiles_dir, "callgrind", test_name)
            )
            for profiles_dir in (baseline_dir, modified_dir)
        )
        uncalled_edge = callgrind.CallerCalls(0, 0, [])
        call_changes: dict[tuple[str, str], BuildReport.CallChange] = {}
        for pair in set(baseline_edges) | set(modified_edges):
            baseline_calls = baseline_edges.get(pair, uncalled_edge).calls
            call_changes[pair] = BuildReport.CallChange(
                modified_edges.get(pair, uncalled_edge).calls - baseline_calls,
                baseline_calls,
            )
        listed_names = set(delta.function_home)
        caller_changes: dict[str, list[BuildReport.CallChange]] = {}
        for (caller_name, callee_name), change in call_changes.items():
            if change.calls:
                listed_names.update((caller_name, callee_name))
            caller_changes.setdefault(callee_name, []).append(change)
        calls_by_name = {
            name: self.diff_function_calls(name, caller_changes.get(name, []))
            for name in listed_names
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
        function_links = self.function_links(test_name, delta, named_names)
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
        counter_names = list(delta.counters)
        locations = self.function_locations(
            delta,
            self.file_display_paths(
                delta, callgrind.DerivedPaths(baseline_dir, modified_dir)
            ),
            row_names.intersection(delta.function_home),
        )
        # The delta holds no record of a function none of whose lines changed.
        for name in row_names.difference(locations):
            locations[name] = callgrind.SourceLine("", 0)
        row_order = sorted(row_names, key=lambda name: (locations[name], name))
        return {
            "counterNames": counter_names,
            "derivedCounters": delta.resolved_derived_counters(),
            "functions": function_links,
            "functionRows": [
                BuildReport.DiffFunctionRow(
                    index_by_name[name],
                    locations[name].file,
                    locations[name].line,
                    calls_by_name[name][0],
                    self.counter_values(
                        delta.counters,
                        delta.function_self.get(name, []),
                        counter_names,
                    ),
                    callers.get(name, []),
                    callees.get(name, []),
                    calls_by_name[name][1],
                    self.counter_values(
                        callers_doc["counters"],
                        callers_doc["baseline"].get(name, []),
                        counter_names,
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

    def diff_overview_rows(
        self, artifacts_dir: str, test_names: Sequence[str]
    ) -> list[list[theme.CellOrText]]:
        rows: list[list[theme.CellOrText]] = []
        for test_name in test_names:
            doc = callgrind_diff.callers_doc_load(artifacts_dir, test_name)
            counters = doc["counters"]
            callgrind.ranking_counter_check(
                counters,
                artifacts.artifact_path(
                    artifacts_dir, "caller-counts", test_name
                ),
            )
            delta = callgrind.counter_value(
                counters, doc["deltaTotal"], _RANKING_COUNTER_NAME
            )
            baseline_total = callgrind.counter_value(
                counters, doc["baselineTotal"], _RANKING_COUNTER_NAME
            )
            share = theme.diff_share(delta, baseline_total)
            rows.append(
                [
                    self.test_link_cell(test_name),
                    theme.num_signed(delta),
                    theme.num_signed_pct(share),
                    theme.num_human(doc["changedFunctions"]),
                ]
            )
        return rows

    def entry_link(
        self, test_name: str, profile: callgrind.LineProfile, function: str
    ) -> str:
        entry = profile.function_entry.get(function)
        if entry is None or not entry.line:
            return ""
        return self.address(test_name, _HEAT_MAP_VIEW_KEY, function)

    # Returns the path the heat map shows for each file the profile names.
    def file_display_paths(
        self,
        profile: callgrind.Profile,
        derived_paths: callgrind.DerivedPaths | None,
    ) -> dict[str, str]:
        raw_paths = (
            {key.file for key in profile.line_self}
            | {key.file for key in profile.line_calls}
            | {entry.file for entry in profile.function_entry.values()}
        )
        shown_paths: dict[str, str] = {}
        for raw_path in sorted(raw_paths):
            object_path = profile.file_ob.get(raw_path, "")
            if derived_paths is None:
                path_info = callgrind.path_norm(raw_path)
                shown_paths[raw_path] = callgrind.display_path(
                    path_info.display, path_info.group, object_path
                )
                continue
            entry = derived_paths.path_entry(raw_path)
            shown_paths[raw_path] = callgrind.display_path(
                entry.canonical, entry.group, object_path
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

    # Returns each named function's shown file and the line it is addressed at.
    def function_locations(
        self,
        profile: callgrind.Profile,
        shown_paths: dict[str, str],
        function_names: Iterable[str],
    ) -> dict[str, callgrind.SourceLine]:
        heat_map = callgrind_to_heatmap.CallgrindToHeatmap()
        locations: dict[str, callgrind.SourceLine] = {}
        for function_name in function_names:
            location = heat_map.function_line(profile, function_name)
            locations[function_name] = callgrind.SourceLine(
                shown_paths[location.file], location.line
            )
        return locations

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
            {
                "id": "overview-tests-table-",
                "data-diff-": str(int(is_diff)),
            },
            "overview.tests",
            rows,
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
        print(
            f"wrote {path} ({len(page.encode('utf-8')):,} bytes)",
            file=sys.stderr,
        )

    # Returns the perf tool's time over its loops, its other output left out.
    def perf_tool_time_per_loop(
        self, page_path: str, page_lines: Sequence[str], test_name: str
    ) -> float:
        command_words = page_lines[0].split() if page_lines else []
        if (
            len(command_words) < 2
            or command_words[-2] != test_name
            or not command_words[-1].isdigit()
            or not int(command_words[-1])
        ):
            sys.exit(
                f"error: {page_path} opens with no {test_name} command ending"
                f" in its loop count: {page_lines[:1]}"
            )
        time_matches = [
            line_match
            for line_match in map(_PERF_TOOL_TIME_LINE.fullmatch, page_lines)
            if line_match
        ]
        if len(time_matches) != 1:
            sys.exit(
                f"error: {page_path} holds {len(time_matches)}"
                f" {_PERF_TOOL_TIME_LABEL}: lines with a time unit"
                f" of {sorted(_DATABASE_TIME_SUFFIX_SECONDS)}, expected 1"
            )
        time_match = time_matches[0]
        run_seconds = (
            float(time_match.group(1))
            * (_DATABASE_TIME_SUFFIX_SECONDS[time_match.group(2)])
        )
        return run_seconds / int(command_words[-1])

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
            os.path.join(report_dir, _SETTINGS_VIEW_ENTRY[1]), _SETTINGS_PAGE
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

    # Returns a timing page's dividend counter over its divisor counter.
    def timing_counter_ratio(
        self, page_path: str, page_lines: Sequence[str]
    ) -> float:
        counter_values = self.timing_counters(page_path, page_lines)
        ratio_terms: list[int] = []
        for counter_key in (
            _TIMING_COUNTER_RATIO_DIVIDEND,
            _TIMING_COUNTER_RATIO_DIVISOR,
        ):
            if counter_key not in _TIMING_COUNTER_LABELS:
                sys.exit(
                    f"error: TIMING_COUNTER_LABELS holds no {counter_key}"
                    f" key: {sorted(_TIMING_COUNTER_LABELS)}"
                )
            counter_label = _TIMING_COUNTER_LABELS[counter_key]
            counter_text = counter_values[counter_label]
            if not counter_text.isdigit() or not int(counter_text):
                sys.exit(
                    f"error: {page_path} holds {counter_label}:"
                    f" {counter_text!r}, expected a count above 0"
                )
            ratio_terms.append(int(counter_text))
        return ratio_terms[0] / ratio_terms[1]

    # Returns each perf stat counter line's value of a timing page by label.
    def timing_counters(
        self, page_path: str, page_lines: Sequence[str]
    ) -> dict[str, str]:
        counter_values: dict[str, list[str]] = {
            counter_label: []
            for counter_label in _TIMING_COUNTER_LABELS.values()
        }
        for page_line in page_lines:
            line_label, label_separator, line_value = page_line.partition(":")
            if label_separator and line_label in counter_values:
                counter_values[line_label].append(line_value.strip())
        for counter_label, label_values in counter_values.items():
            if len(label_values) != 1:
                sys.exit(
                    f"error: {page_path} holds {len(label_values)}"
                    f" {counter_label}: lines, expected 1"
                )
        return {
            counter_label: label_values[0]
            for counter_label, label_values in counter_values.items()
        }

    # Returns a row per test, its time per loop and instructions per cycle.
    def timing_rows(
        self, artifacts_dir: str, test_names: Sequence[str]
    ) -> list[list[theme.CellOrText]]:
        rows: list[list[theme.CellOrText]] = []
        for test_name in test_names:
            page_path = artifacts.artifact_path(
                artifacts_dir, "timing-page", test_name
            )
            with artifacts.artifact_open(
                artifacts_dir, "timing-page", test_name
            ) as handle:
                page_lines = handle.read().splitlines()
            rows.append(
                [
                    self.test_link_cell(test_name),
                    theme.num_time(
                        self.perf_tool_time_per_loop(
                            page_path, page_lines, test_name
                        )
                    ),
                    theme.fixed_text(
                        self.timing_counter_ratio(page_path, page_lines)
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
    report = BuildReport()
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
            BuildReport.ReportArgs(
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
