#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, json, os, re, sys, urllib.parse
from collections.abc import Iterable, Sequence
from typing import NamedTuple, NotRequired, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artifacts, callgrind, callgrind_diff, settings, theme

_ASSET_DEBUG_SCRIPT_NAME: str = ""
_ASSET_TEMPLATE_CALL_GRAPH_PAGE_NAME: str = ""
_ASSET_TEMPLATE_CALLERS_PAGE_NAME: str = ""
_ASSET_TEMPLATE_OVERVIEW_PAGE_NAME: str = ""
_ASSET_TEMPLATE_SETTINGS_PAGE_NAME: str = ""
_CALL_GRAPH_PAGE_DIR_NAME: str = ""
_CALLERS_PAGE_DIR_NAME: str = ""
_CALLERS_TIME_SUFFIX_SECONDS: dict[str, float] = {}
_CALLGRIND_ROOT_FUNCTION_NAME: str = ""
_FLAME_GRAPH_LOCAL_PROFILE_PATH: str = ""
_FLAME_GRAPH_VIEW_ENTRY: tuple[str, str] = ("", "")
_HEAT_MAP_VIEW_ENTRY: tuple[str, str] = ("", "")
_OVERVIEW_PAGE_PATH: str = ""
_RANKING_COUNTER_NAME: str = ""
_README_HTML_NAME: str = ""
_README_MARKDOWN_NAME: str = ""
_REPORT_SCRIPTS_DIR_NAME: str = ""
_SETTINGS_VIEW_ENTRY: tuple[str, str] = ("", "")
settings.load_into(__name__)

_CALL_GRAPH_PAGE = theme.asset_text_read(_ASSET_TEMPLATE_CALL_GRAPH_PAGE_NAME)

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

    class CallGraphEdge(NamedTuple):
        caller: int
        callee: int
        calls: int
        line: int

    class CallGraphModel(TypedDict):
        functions: list[BuildReport.FunctionLink]
        roots: (
            list[BuildReport.CallGraphRoot]
            | list[BuildReport.DiffCallGraphRoot]
        )
        edges: (
            list[BuildReport.CallGraphEdge]
            | list[BuildReport.DiffCallGraphEdge]
        )

    class CallGraphRoot(NamedTuple):
        function: int
        calls: int

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

    class DiffCallGraphEdge(NamedTuple):
        caller: int
        callee: int
        baseline_calls: int
        calls: int
        line: int

    class DiffCallGraphRoot(NamedTuple):
        function: int
        baseline_calls: int
        calls: int

    class FunctionLink(NamedTuple):
        name: str
        href: str

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

    # Writes every listed test's call graph page, a diff's of both sides.
    def call_graph(self, args: BuildReport.ReportArgs) -> None:
        artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        for test_name in artifacts.test_list_read(artifacts_dir):
            call_graph_model = (
                self.diff_call_graph_model(artifacts_dir, test_name)
                if args.diff
                else self.call_graph_model(
                    test_name,
                    callgrind.profile_load(
                        artifacts_dir, "callgrind", test_name
                    ),
                )
            )
            self.call_graph_page(
                args.report, test_name, args.diff, call_graph_model
            )

    # Returns each caller and callee pair's calls and its first call line.
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

    # Lists every function the test calls, its root and every call edge.
    def call_graph_model(
        self, test_name: str, profile: callgrind.Profile
    ) -> BuildReport.CallGraphModel:
        edges = self.call_graph_edges(profile)
        function_links = self.function_links(
            test_name, profile, {name for pair in edges for name in pair}
        )
        index_by_name = {
            link.name: index for index, link in enumerate(function_links)
        }
        return {
            "functions": function_links,
            "roots": [
                BuildReport.CallGraphRoot(
                    index_by_name[root_name], profile.root_call_count
                )
                for root_name in self.call_graph_roots(test_name, edges)
            ],
            "edges": [
                BuildReport.CallGraphEdge(
                    index_by_name[caller_name],
                    index_by_name[callee_name],
                    tally.calls,
                    tally.line,
                )
                for (caller_name, callee_name), tally in sorted(edges.items())
            ],
        }

    # Writes a test's call graph page, holding the model its script lays out.
    def call_graph_page(
        self,
        report_dir: str,
        test_name: str,
        is_diff: bool,
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
                    "pre",
                    {
                        "id": "call-graph-text-",
                        "data-diff-": str(int(is_diff)),
                        "data-model-": model_text,
                    },
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

    # Returns the root function alone, refusing a graph not cut there.
    def call_graph_roots(
        self, test_name: str, pairs: Iterable[tuple[str, str]]
    ) -> list[str]:
        called_names = {callee_name for _, callee_name in pairs}
        root_names = sorted(
            {caller_name for caller_name, _ in pairs} - called_names
        )
        if root_names != [_CALLGRIND_ROOT_FUNCTION_NAME]:
            sys.exit(
                f"error: {test_name}'s call graph starts at"
                f" {' '.join(root_names)}, not at"
                f" {_CALLGRIND_ROOT_FUNCTION_NAME} alone"
            )
        return root_names

    # Writes every listed test's callers page.
    def callers(self, args: BuildReport.ReportArgs) -> None:
        artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        test_page_write = self.diff_test if args.diff else self.test
        for test_name in artifacts.test_list_read(artifacts_dir):
            test_page_write(args.report, artifacts_dir, test_name)

    def callers_data_load(
        self, artifacts_dir: str, test_name: str
    ) -> BuildReport.CallersData:
        doc = callgrind_diff.callers_doc_load(artifacts_dir, test_name)
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
        for callee_name in profile.callers:
            count_by_caller = {
                caller_name: entry.calls
                for caller_name, entry in callgrind.caller_calls(
                    profile, callee_name
                ).items()
            }
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

    # Lists every function either side calls and each edge's calls on both.
    def diff_call_graph_model(
        self, artifacts_dir: str, test_name: str
    ) -> BuildReport.CallGraphModel:
        baseline, modified = (
            callgrind.profile_load(
                artifacts.artifact_path(artifacts_dir, kind),
                "callgrind",
                test_name,
            )
            for kind in ("baseline-profiles", "modified-profiles")
        )
        baseline_edges = self.call_graph_edges(baseline)
        modified_edges = self.call_graph_edges(modified)
        pairs = sorted(set(baseline_edges) | set(modified_edges))
        function_links = self.function_links(
            test_name,
            callgrind.profile_load(artifacts_dir, "delta", test_name),
            {name for pair in pairs for name in pair},
        )
        index_by_name = {
            link.name: index for index, link in enumerate(function_links)
        }
        uncalled_edge = callgrind.CallerCalls(0, 0)
        return {
            "functions": function_links,
            "roots": [
                BuildReport.DiffCallGraphRoot(
                    index_by_name[root_name],
                    baseline.root_call_count,
                    modified.root_call_count,
                )
                for root_name in self.call_graph_roots(test_name, pairs)
            ],
            "edges": [
                BuildReport.DiffCallGraphEdge(
                    index_by_name[pair[0]],
                    index_by_name[pair[1]],
                    baseline_edges.get(pair, uncalled_edge).calls,
                    modified_edges.get(pair, uncalled_edge).calls,
                    min(
                        side_edges[pair].line
                        for side_edges in (baseline_edges, modified_edges)
                        if pair in side_edges
                    ),
                )
                for pair in pairs
            ],
        }

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
            [],
            rows,
            self.manifest_blocks_read(artifacts_dir, True),
            "",
            callgrind.counter_names(counters),
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

    def diff_test(
        self, report_dir: str, artifacts_dir: str, test_name: str
    ) -> None:
        profile = callgrind.profile_load(artifacts_dir, "delta", test_name)
        callers_data = self.callers_data_load(artifacts_dir, test_name)
        self.report_page(
            report_dir,
            test_name,
            True,
            self.diff_callers_model(test_name, profile, callers_data),
        )

    def entry_link(
        self, test_name: str, profile: callgrind.LineProfile, function: str
    ) -> str:
        entry = profile.function_entry.get(function)
        if entry is None or not entry.line:
            return ""
        return self.address(test_name, _HEAT_MAP_VIEW_KEY, function)

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
                "data-counter-names-": json.dumps(list(counter_names)),
                "data-flame-graph-": str(int(not is_diff)),
                "data-help-href-": help_href,
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
        column_labels, rows = self.timing_rows(artifacts_dir, test_names)
        raw_data_path = artifacts.raw_data_archive_path(
            args.report, artifacts.recorded_time_read(artifacts_dir)
        )
        counters = callgrind.counters_read(
            artifacts_dir, "callgrind", test_names[0]
        )
        self.overview_page(
            args.report,
            test_names,
            column_labels,
            rows,
            self.manifest_blocks_read(artifacts_dir, False),
            os.path.basename(raw_data_path),
            callgrind.counter_names(counters),
            False,
            has_readme_html,
        )

    def overview_page(
        self,
        report_dir: str,
        test_names: Sequence[str],
        column_labels: Sequence[str],
        rows: Sequence[Sequence[theme.CellOrText]],
        manifest_blocks: Sequence[BuildReport.ManifestBlock],
        raw_data_name: str,
        counter_names: Sequence[str],
        is_diff: bool,
        has_readme_html: bool,
    ) -> None:
        raw_data_markup = self.raw_data_render(raw_data_name)
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
            test_names, counter_names, is_diff, has_readme_html
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

    def raw_data_render(self, name: str) -> str:
        if not name:
            return ""
        raw_data_markup = theme.render_element(
            "div",
            {"id": "overview-raw-data-"},
            theme.render_element("a", {"href": name, "target": "_blank"}, ""),
        )
        return raw_data_markup + self.blank_line_render()

    # Writes a test's callers page, holding the model its script draws.
    def report_page(
        self,
        report_dir: str,
        test_name: str,
        is_diff: bool,
        callers_model: BuildReport.CallersModel,
    ) -> None:
        model_text = json.dumps(
            callers_model, separators=(",", ":"), ensure_ascii=False
        )
        page_content = theme.template_fill(
            _CALLERS_PAGE,
            {
                "__PAGE_TITLE__": theme.render_html_escape(test_name),
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
                report_dir, _CALLERS_PAGE_DIR_NAME, f"{test_name}.html"
            ),
            page_content,
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

    def test(
        self, report_dir: str, artifacts_dir: str, test_name: str
    ) -> None:
        profile = callgrind.profile_load(artifacts_dir, "callgrind", test_name)
        self.report_page(
            report_dir,
            test_name,
            False,
            self.callers_model(test_name, profile),
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
        return theme.Cell(name, href=self.address(name, _HEAT_MAP_VIEW_KEY))

    def time_humanize(self, text: str) -> str:
        return _TIME_LINE.sub(self.time_line_rewrite, text)

    def time_line_rewrite(self, match: re.Match[str]) -> str:
        scale = _CALLERS_TIME_SUFFIX_SECONDS[match.group(3).lower()]
        return match.group(1) + theme.num_time(float(match.group(2)) * scale)

    # Returns the timing pages' labels in first seen order and a row per test.
    def timing_rows(
        self, artifacts_dir: str, test_names: Sequence[str]
    ) -> tuple[list[str], list[list[theme.CellOrText]]]:
        keys: list[str] = []
        numbers: dict[str, dict[str, str]] = {}
        for test_name in test_names:
            with artifacts.artifact_open(
                artifacts_dir, "timing-page", test_name
            ) as handle:
                lines = handle.read().splitlines()
            values: dict[str, str] = {}
            for line in lines:
                match = re.match(r"^([A-Za-z][^:]{0,30}):\s+(.+?)\s*$", line)
                if match:
                    values[match.group(1)] = self.value_humanize(
                        match.group(1), match.group(2)
                    )
                    if match.group(1) not in keys:
                        keys.append(match.group(1))
            numbers[test_name] = values
        rows: list[list[theme.CellOrText]] = [
            [self.test_link_cell(test_name)]
            + [numbers[test_name].get(key, "") for key in keys]
            for test_name in test_names
        ]
        return keys, rows

    def value_humanize(self, label: str, value: str) -> str:
        line = self.time_humanize(f"{label}: {value}")
        return line.split(": ", 1)[1] if line != f"{label}: {value}" else value


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    callers_parser = subparsers.add_parser(
        "callers", help="every listed test's callers page"
    )
    callers_parser.add_argument(
        "--diff",
        action="store_true",
        help="the recordings are callgrind_diff.py deltas: each callee's"
        " change of calls and counters beside its baseline, signed",
    )

    call_graph_parser = subparsers.add_parser(
        "call-graph", help="every listed test's call graph page"
    )
    call_graph_parser.add_argument(
        "--diff",
        action="store_true",
        help="the report is a diff: each edge carries its calls in the"
        " extracted baseline and modified recordings",
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
        callers_parser,
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
        callers_parser,
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
            BuildReport.ReportArgs(
                artifacts=namespace.artifacts,
                report=namespace.report,
                diff=namespace.diff,
            )
        )
    elif namespace.cmd == "callers":
        report.callers(
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
