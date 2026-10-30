#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, base64, contextlib, html, io, json, math, os, re
import subprocess, sys, tarfile, urllib.parse
from collections.abc import Sequence
from typing import Any, NamedTuple, NoReturn

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind, callgrind_diff, callgrind_to_heatmap, settings, test_settings

_FLAME_GRAPH_APP_DIR_NAME: str = ""
_FLAME_GRAPH_EXPORTER_NAME: str = ""
_FLAME_GRAPH_PROFILE_DIR_NAME: str = ""
_FLAME_GRAPH_PROFILE_GLOBAL_NAME: str = ""
_FLAME_GRAPH_VIEW_ENTRY: tuple[str, str] = ("", "")
_HEAT_MAP_MODEL_DIR_NAME: str = ""
_HEAT_MAP_MODEL_GLOBAL_NAME: str = ""
_HEAT_MAP_VIEW_ENTRY: tuple[str, str] = ("", "")
_REPORT_MANIFEST_CHECKSUM_LABEL: str = ""
_REPORT_MANIFEST_VERSION_DIFF: str = ""
_REPORT_MANIFEST_VERSION_FULL: str = ""
_REPORT_RAW_ARCHIVE_SUFFIX: str = ""
_REPORT_SOURCES_DIR_NAME: str = ""
settings.load_into(__name__)


class TestReport:
    class RawData(NamedTuple):
        archive_name: str
        path: str
        texts: dict[str, str]
        build_tree: str

    class ReportLayout(NamedTuple):
        is_regular_report: bool
        table_diff_value: str
        database_model_keys: tuple[str, ...]
        database_function_fields: int
        database_function_value_fields: tuple[int, ...]
        database_call_fields: int
        header_blocks: tuple[str, ...]
        manifest_version: str
        manifest_labels: tuple[str, ...]
        manifest_recorded_labels: tuple[str, ...]
        test_records_runs: bool
        has_timer_artifacts: bool
        has_baselines: bool

    class TestArgs(NamedTuple):
        out_dir: str
        diff: bool
        baseline: str
        modified: str
        readme_html: bool
        verbose: bool

    # Checks the rows, costs, total and window of a call graph.
    def call_graph_model_check(
        self,
        call_graph_model: dict[str, Any],
        label: str,
        path: str,
    ) -> None:
        function_names: list[str] = []
        self_total = 0
        for function_row in call_graph_model["functions"]:
            if (
                len(function_row)
                != test_settings.TEST_CALL_GRAPH_FUNCTION_FIELDS
            ):
                self.fail(
                    f"{label}'s call graph has a function of"
                    f" {len(function_row)} fields, expected"
                    f" {test_settings.TEST_CALL_GRAPH_FUNCTION_FIELDS}: {path}"
                )
            function_name = function_row[
                test_settings.TEST_CALL_GRAPH_FUNCTION_NAME_FIELD
            ]
            self_value = function_row[
                test_settings.TEST_CALL_GRAPH_FUNCTION_SELF_FIELD
            ]
            if not isinstance(self_value, int) or self_value < 0:
                self.fail(
                    f"{label}'s call graph gives {function_name!r} the self"
                    f" cost {self_value!r}, expected an integer of 0 or more:"
                    f" {path}"
                )
            function_names.append(function_name)
            self_total += self_value
        # A test's total holds the self costs of its functions.
        test_total = call_graph_model["test_total"]
        if (
            not isinstance(test_total, int)
            or test_total <= 0
            or test_total < self_total
        ):
            self.fail(
                f"{label}'s call graph gives the test total {test_total!r},"
                " expected an integer above 0 and of at least its functions'"
                f" summed self cost {self_total}: {path}"
            )
        function_count = len(function_names)
        caller_indexes: set[int] = set()
        called_indexes: set[int] = set()
        for edge_row in call_graph_model["edges"]:
            if len(edge_row) != test_settings.TEST_CALL_GRAPH_EDGE_FIELDS:
                self.fail(
                    f"{label}'s call graph has an edge of {len(edge_row)}"
                    " fields, expected"
                    f" {test_settings.TEST_CALL_GRAPH_EDGE_FIELDS}:"
                    f" {path}"
                )
            if not all(
                0 <= edge_row[field] < function_count
                for field in test_settings.TEST_CALL_GRAPH_EDGE_FUNCTION_FIELDS
            ):
                self.fail(
                    f"{label}'s call graph edge {edge_row} names a function"
                    f" past its {function_count} functions: {path}"
                )
            inclusive_value = edge_row[
                test_settings.TEST_CALL_GRAPH_EDGE_INCLUSIVE_FIELD
            ]
            if not isinstance(inclusive_value, int) or inclusive_value < 0:
                self.fail(
                    f"{label}'s call graph edge {edge_row} gives the inclusive"
                    f" cost {inclusive_value!r}, expected an integer of 0 or"
                    f" more: {path}"
                )
            caller_indexes.add(
                edge_row[test_settings.TEST_CALL_GRAPH_EDGE_CALLER_FIELD]
            )
            called_indexes.add(
                edge_row[test_settings.TEST_CALL_GRAPH_EDGE_CALLEE_FIELD]
            )
        for root_row in call_graph_model["roots"]:
            if len(root_row) != test_settings.TEST_CALL_GRAPH_ROOT_FIELDS:
                self.fail(
                    f"{label}'s call graph has a root of {len(root_row)}"
                    " fields, expected"
                    f" {test_settings.TEST_CALL_GRAPH_ROOT_FIELDS}:"
                    f" {path}"
                )
        root_indexes = [
            root_row[test_settings.TEST_CALL_GRAPH_ROOT_FUNCTION_FIELD]
            for root_row in call_graph_model["roots"]
        ]
        uncalled_indexes = sorted(caller_indexes - called_indexes)
        if root_indexes != uncalled_indexes:
            self.fail(
                f"{label}'s call graph roots {root_indexes} are"
                f" not its uncalled callers {uncalled_indexes}: {path}"
            )
        for root_row in call_graph_model["roots"]:
            root_name = function_names[
                root_row[test_settings.TEST_CALL_GRAPH_ROOT_FUNCTION_FIELD]
            ]
            # A root is uncalled, so only the start function counts calls.
            root_calls = (
                test_settings.TEST_CALL_GRAPH_START_FUNCTION_CALLS
                if root_name
                == test_settings.TEST_CALL_GRAPH_START_FUNCTION_NAME
                else 0
            )
            counted_calls = root_row[
                test_settings.TEST_CALL_GRAPH_ROOT_CALLS_FIELD
            ]
            if counted_calls != root_calls:
                self.fail(
                    f"{label}'s call graph root {root_name} counts the calls"
                    f" {counted_calls}, expected {root_calls}: {path}"
                )
        if (
            test_settings.TEST_CALL_GRAPH_START_FUNCTION_NAME
            not in function_names
        ):
            self.fail(
                f"{label}'s call graph names no"
                f" {test_settings.TEST_CALL_GRAPH_START_FUNCTION_NAME}, the"
                " function the"
                f" recording starts at: {path}"
            )
        if test_settings.TEST_CALL_GRAPH_STOP_FUNCTION_NAME in function_names:
            self.fail(
                f"{label}'s call graph names"
                f" {test_settings.TEST_CALL_GRAPH_STOP_FUNCTION_NAME}, the"
                " function the"
                f" recording stops at: {path}"
            )

    # Checks a test's call graph page and its model, or that a diff has none.
    def call_graph_page_check(
        self,
        out_dir: str,
        test_name: str,
        layout: TestReport.ReportLayout,
    ) -> None:
        label = (
            f"{test_settings.TEST_CALL_GRAPH_PAGE_DIR_NAME}/{test_name}.html"
        )
        path = os.path.join(out_dir, label)
        if not layout.is_regular_report:
            if os.path.lexists(path):
                self.fail(
                    f"{label} in a diff report, which has no call graph:"
                    f" {path}"
                )
            return
        self.page_check(
            path,
            label,
            test_settings.TEST_CALL_GRAPH_PAGE_LEAST_BYTES,
            test_name,
        )
        with open(path, encoding="utf-8") as handle:
            page_text = handle.read()
        attributes = self.element_attributes(
            page_text, test_settings.TEST_CALL_GRAPH_TABLE_ID
        )
        if attributes is None:
            self.fail(
                f"{label} has no {test_settings.TEST_CALL_GRAPH_TABLE_ID}:"
                f" {path}"
            )
        try:
            call_graph_model = json.loads(attributes.get("data-model-", ""))
        except ValueError as error:
            self.fail(f"{label} holds no JSON call graph: {error}: {path}")
        found_keys = (
            sorted(call_graph_model)
            if isinstance(call_graph_model, dict)
            else []
        )
        if found_keys != sorted(test_settings.TEST_CALL_GRAPH_MODEL_KEYS):
            self.fail(
                f"{label}'s call graph holds the keys {found_keys},"
                " expected"
                f" {sorted(test_settings.TEST_CALL_GRAPH_MODEL_KEYS)}: {path}"
            )
        self.call_graph_model_check(call_graph_model, label, path)

    def checksum_compute(self, out_dir: str) -> str:
        try:
            done = subprocess.run(
                ["sh", "-c", test_settings.REPORT_CHECKSUM_COMMAND],
                cwd=out_dir,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            self.fail(f"cannot checksum {out_dir}: {error}")
        if done.returncode != 0:
            self.fail(
                f"cannot checksum {out_dir}: cksum exited"
                f" {done.returncode}: {done.stderr.strip()}"
            )
        return done.stdout.split(" ", 1)[0]

    # Returns costs without their trailing zeros, as a page model holds them.
    def costs_trimmed(self, costs: Sequence[int]) -> list[int]:
        trimmed = list(costs)
        while trimmed and not trimmed[-1]:
            trimmed.pop()
        return trimmed

    # Checks the derived counter names and each term's recorded counter.
    def database_derived_check(
        self, database_model: dict[str, Any], label: str, path: str
    ) -> None:
        counter_count = len(database_model["counterNames"])
        derived_names: list[Any] = []
        for derived_name, terms in database_model["derivedCounters"]:
            derived_names.append(derived_name)
            for coefficient, counter_index in terms:
                if (
                    not isinstance(coefficient, int)
                    or not 0 <= counter_index < counter_count
                ):
                    self.fail(
                        f"{label}'s database model derives {derived_name}"
                        f" from {coefficient!r} of the counter"
                        f" {counter_index!r}, expected an integer of one of"
                        f" its {counter_count} counters: {path}"
                    )
        if derived_names != list(test_settings.TEST_DERIVED_COUNTER_NAMES):
            self.fail(
                f"{label}'s database model derives {derived_names}, expected"
                f" {list(test_settings.TEST_DERIVED_COUNTER_NAMES)}: {path}"
            )

    # Checks each call between listed functions shows in both of their rows.
    def database_edges_check(
        self, function_rows: list[list[Any]], label: str, path: str
    ) -> None:
        caller_edges, callee_edges = (
            self.database_side_edges(function_rows, rows_field)
            for rows_field in (
                test_settings.TEST_DATABASE_CALLER_ROWS_FIELD,
                test_settings.TEST_DATABASE_CALLEE_ROWS_FIELD,
            )
        )
        one_sided_edges = sorted(caller_edges ^ callee_edges)
        if one_sided_edges:
            self.fail(
                f"{label}'s database model lists {len(one_sided_edges)} calls"
                " between listed functions in the callers or the callees"
                f" alone, first {one_sided_edges[0]}: {path}"
            )

    # Checks every database link opens the test's heat map at what it names.
    def database_links_check(
        self,
        out_dir: str,
        test_name: str,
        database_model: dict[str, Any],
        label: str,
        path: str,
    ) -> None:
        heat_map_model = self.heat_map_model_read(out_dir, test_name)
        function_start = (
            f"#test={test_name}&view={_HEAT_MAP_VIEW_KEY}&function="
        )
        function_links = [
            function_link
            for function_link in database_model["functions"]
            if function_link[test_settings.TEST_DATABASE_FUNCTION_HREF_FIELD]
        ]
        if not function_links:
            self.fail(
                f"{label} links no function into the heat map"
                f" ({function_start}...): {path}"
            )
        for function_link in function_links:
            name = function_link[
                test_settings.TEST_DATABASE_FUNCTION_NAME_FIELD
            ]
            href = function_link[
                test_settings.TEST_DATABASE_FUNCTION_HREF_FIELD
            ]
            linked_name = urllib.parse.unquote(
                href.removeprefix(function_start)
            )
            if not href.startswith(function_start) or linked_name != name:
                self.fail(
                    f"{label} links {name} as {href!r}, expected"
                    f" {function_start} followed by the name: {path}"
                )
        function_names = [
            function_link[test_settings.TEST_DATABASE_FUNCTION_NAME_FIELD]
            for function_link in database_model["functions"]
        ]
        listed_names = {
            function_names[
                function_row[test_settings.TEST_DATABASE_ROW_FUNCTION_FIELD]
            ]
            for function_row in database_model["functionRows"]
        }
        linked_names = {
            function_link[test_settings.TEST_DATABASE_FUNCTION_NAME_FIELD]
            for function_link in function_links
        }
        heat_map_names = {
            function_entry["name"]
            for function_entry in heat_map_model["functions"]
        }
        # The start function is called, though no caller of it is recorded.
        called_names = {
            function_entry["name"]
            for function_entry in heat_map_model["functions"]
            if function_entry["name"]
            == test_settings.TEST_CALL_GRAPH_START_FUNCTION_NAME
            or any(
                caller_row[test_settings.TEST_HEAT_MAP_CALL_ROW_COUNT_FIELD]
                > 0
                for caller_row in function_entry["callers"]
            )
        }
        listed_files = {
            function_row[test_settings.TEST_DATABASE_ROW_FILE_FIELD]
            for function_row in database_model["functionRows"]
        }
        for problem, names in (
            (
                "lists no row of these called heat map functions",
                called_names - listed_names,
            ),
            (
                "links these functions the heat map lacks",
                linked_names - heat_map_names,
            ),
            (
                "places functions in these files the heat map lacks",
                listed_files - set(heat_map_model["files"]),
            ),
        ):
            if names:
                self.fail(
                    f"{label} {problem}, {len(names)} of them, first"
                    f" {sorted(names)[0]}: {path}"
                )

    # Checks the database model the page script draws, answering the model.
    def database_model_check(
        self,
        path: str,
        label: str,
        page_text: str,
        layout: TestReport.ReportLayout,
    ) -> dict[str, Any]:
        attributes = self.element_attributes(
            page_text, test_settings.TEST_DATABASE_MODEL_ID
        )
        if attributes is None:
            self.fail(
                f"{label} has no {test_settings.TEST_DATABASE_MODEL_ID} model"
                " element:"
                f" {path}"
            )
        if attributes.get("data-diff-") != layout.table_diff_value:
            self.fail(
                f"{label}'s model element holds data-diff-"
                f" {attributes.get('data-diff-')!r}, expected"
                f" {layout.table_diff_value!r}: {path}"
            )
        if "data-model-" not in attributes:
            self.fail(f"{label}'s model element holds no data-model-: {path}")
        try:
            database_model = json.loads(attributes["data-model-"])
        except ValueError as error:
            self.fail(
                f"{label}'s model element holds no JSON model: {error}: {path}"
            )
        found_keys = (
            sorted(database_model) if isinstance(database_model, dict) else []
        )
        if found_keys != sorted(layout.database_model_keys):
            self.fail(
                f"{label}'s database model holds the keys {found_keys},"
                f" expected {sorted(layout.database_model_keys)}: {path}"
            )
        self.database_rows_check(database_model, layout, label, path)
        return database_model

    def database_page_check(
        self,
        out_dir: str,
        test_name: str,
        layout: TestReport.ReportLayout,
        regular_data: Sequence[TestReport.RawData],
    ) -> None:
        label = self.database_page_path(test_name)
        path = os.path.join(out_dir, label)
        self.page_check(
            path,
            label,
            test_settings.TEST_OVERVIEW_PAGE_LEAST_BYTES,
            test_name,
        )
        with open(path, encoding="utf-8") as handle:
            page_text = handle.read()
        if '<nav id="menu-"' in page_text:
            self.fail(f"{label} draws the overview's menu: {path}")
        if test_settings.TEST_OVERVIEW_RAW_DATA_MARKUP in page_text:
            self.fail(
                f"{label} has a 'raw data' section, but it should not: {path}"
            )
        database_model = self.database_model_check(
            path, label, page_text, layout
        )
        self.function_names_check(database_model, label, path)
        self.database_links_check(
            out_dir, test_name, database_model, label, path
        )
        if layout.has_baselines:
            self.diff_functions_check(
                out_dir, test_name, database_model, regular_data
            )

    # Returns the report relative path of a test's database page.
    def database_page_path(self, test_name: str) -> str:
        return f"{test_settings.TEST_DATABASE_PAGE_DIR_NAME}/{test_name}.html"

    # Checks a function row holds its fields, its place, a call and counters.
    def database_row_check(
        self,
        function_row: list[Any],
        layout: TestReport.ReportLayout,
        counter_count: int,
        label: str,
        path: str,
    ) -> None:
        row_label = (
            f"{label}'s function row "
            f"{function_row[test_settings.TEST_DATABASE_ROW_FUNCTION_FIELD]!r}"
        )
        if len(function_row) != layout.database_function_fields:
            self.fail(
                f"{row_label} holds {len(function_row)} fields, expected"
                f" {layout.database_function_fields}: {path}"
            )
        for field_index in layout.database_function_value_fields:
            if len(function_row[field_index]) != counter_count:
                self.fail(
                    f"{row_label} gives {len(function_row[field_index])}"
                    f" counter values, expected {counter_count}: {path}"
                )
        file_path = function_row[test_settings.TEST_DATABASE_ROW_FILE_FIELD]
        line_number = function_row[test_settings.TEST_DATABASE_ROW_LINE_FIELD]
        if (
            not isinstance(file_path, str)
            or not isinstance(line_number, int)
            or line_number < 0
            or (not file_path and line_number)
        ):
            self.fail(
                f"{row_label} places its function at {file_path!r} line"
                f" {line_number!r}, expected a file path and a line of 0 or"
                f" more, 0 for no path: {path}"
            )
        calls = function_row[test_settings.TEST_DATABASE_ROW_CALLS_FIELD]
        side_calls = [calls]
        if layout.has_baselines:
            baseline_calls = function_row[
                test_settings.TEST_DATABASE_ROW_BASELINE_CALLS_FIELD
            ]
            side_calls = [baseline_calls, baseline_calls + calls]
        if max(side_calls) <= 0:
            self.fail(
                f"{row_label} lists an uncalled function, its calls on each"
                f" side {side_calls}: {path}"
            )

    # Checks the derived counters, then each function row and the row order.
    def database_rows_check(
        self,
        database_model: dict[str, Any],
        layout: TestReport.ReportLayout,
        label: str,
        path: str,
    ) -> None:
        counter_count = len(database_model["counterNames"])
        if "counterTotals" in layout.database_model_keys:
            totals_count = len(database_model["counterTotals"])
            if totals_count != counter_count:
                self.fail(
                    f"{label}'s database model totals {totals_count}"
                    f" counters, expected {counter_count}: {path}"
                )
        self.database_derived_check(database_model, label, path)
        function_count = len(database_model["functions"])
        function_rows = database_model["functionRows"]
        named_indexes: set[int] = set()
        for function_row in function_rows:
            self.database_row_check(
                function_row, layout, counter_count, label, path
            )
            call_rows = [
                *function_row[test_settings.TEST_DATABASE_CALLER_ROWS_FIELD],
                *function_row[test_settings.TEST_DATABASE_CALLEE_ROWS_FIELD],
            ]
            for call_row in call_rows:
                if len(call_row) != layout.database_call_fields:
                    self.fail(
                        f"{label}'s database model has a caller or callee"
                        f" row of {len(call_row)} fields, expected"
                        f" {layout.database_call_fields}: {path}"
                    )
            for indexed_row in (function_row, *call_rows):
                function_index = indexed_row[
                    test_settings.TEST_DATABASE_ROW_FUNCTION_FIELD
                ]
                if not 0 <= function_index < function_count:
                    self.fail(
                        f"{label}'s database model names the function"
                        f" {function_index} past its {function_count}"
                        f" functions: {path}"
                    )
                named_indexes.add(function_index)
        if len(named_indexes) != function_count:
            self.fail(
                f"{label}'s database model links"
                f" {function_count - len(named_indexes)} functions that no"
                f" row, caller or callee names: {path}"
            )
        function_names = [
            function_link[test_settings.TEST_DATABASE_FUNCTION_NAME_FIELD]
            for function_link in database_model["functions"]
        ]
        row_places = [
            (
                function_row[test_settings.TEST_DATABASE_ROW_FILE_FIELD],
                function_row[test_settings.TEST_DATABASE_ROW_LINE_FIELD],
                function_names[
                    function_row[
                        test_settings.TEST_DATABASE_ROW_FUNCTION_FIELD
                    ]
                ],
            )
            for function_row in function_rows
        ]
        if row_places != sorted(row_places):
            self.fail(
                f"{label}'s database model lists its function rows out of"
                f" file, line and name order: {path}"
            )
        self.database_edges_check(function_rows, label, path)

    # Returns the calls one side of each function row lists, among the rows.
    def database_side_edges(
        self, function_rows: list[list[Any]], rows_field: int
    ) -> set[tuple[Any, ...]]:
        listed_indexes = {
            function_row[test_settings.TEST_DATABASE_ROW_FUNCTION_FIELD]
            for function_row in function_rows
        }
        side_edges: set[tuple[Any, ...]] = set()
        for function_row in function_rows:
            row_index = function_row[
                test_settings.TEST_DATABASE_ROW_FUNCTION_FIELD
            ]
            for call_row in function_row[rows_field]:
                partner_index = call_row[
                    test_settings.TEST_DATABASE_ROW_FUNCTION_FIELD
                ]
                if partner_index not in listed_indexes:
                    continue
                call_counts = call_row[
                    test_settings.TEST_DATABASE_CALL_COUNTS_START_FIELD :
                ]
                side_edges.add(
                    (partner_index, row_index, *call_counts)
                    if rows_field
                    == test_settings.TEST_DATABASE_CALLER_ROWS_FIELD
                    else (row_index, partner_index, *call_counts)
                )
        return side_edges

    # Checks a delta homes a function whose changed lines lie in a header.
    def delta_home_check(self) -> None:
        delta = callgrind.LineProfile()
        delta.function_home[test_settings.TEST_DELTA_HOME_FUNCTION_NAME] = (
            test_settings.TEST_DELTA_HOME_FILE
        )
        delta.function_lines[test_settings.TEST_DELTA_HOME_FUNCTION_NAME][
            callgrind.SourceLine(*test_settings.TEST_DELTA_HOME_INLINED_LINE)
        ] = [1]
        home_image = test_settings.TEST_DELTA_HOME_IMAGE
        delta.file_image.update(
            {
                test_settings.TEST_DELTA_HOME_FILE: home_image,
                test_settings.TEST_DELTA_HOME_INLINED_LINE[0]: home_image,
            }
        )
        handle = io.StringIO()
        handle.write(test_settings.TEST_DELTA_HOME_RECORDING_HEADER)
        callgrind_diff.CallgrindDiff.write_function(
            handle, delta, test_settings.TEST_DELTA_HOME_FUNCTION_NAME, ""
        )
        try:
            profile = callgrind.Callgrind().parse(
                handle.getvalue(), test_settings.TEST_DELTA_HOME_RECORDING_NAME
            )
        except SystemExit as error:
            self.fail(
                "the parser refuses"
                f" {test_settings.TEST_DELTA_HOME_RECORDING_NAME},"
                f" the delta writer's: {error}"
            )
        found_home = profile.function_home[
            test_settings.TEST_DELTA_HOME_FUNCTION_NAME
        ]
        if found_home != test_settings.TEST_DELTA_HOME_FILE:
            self.fail(
                f"{test_settings.TEST_DELTA_HOME_RECORDING_NAME} homes"
                f" {test_settings.TEST_DELTA_HOME_FUNCTION_NAME} at"
                f" {found_home!r},"
                f" expected {test_settings.TEST_DELTA_HOME_FILE!r}, its"
                " changed line"
                f" lying in {test_settings.TEST_DELTA_HOME_INLINED_LINE[0]!r}:"
                f" {handle.getvalue()!r}"
            )

    def diff_baseline_check(self, filed_model: Any, label: str) -> None:
        width = len(filed_model["heatMapTotals"]["counters"])
        changes: list[tuple[str, list[int], list[int]]] = []
        for path, entry in filed_model["files"].items():
            file_baseline = filed_model["fileBaseline"].get(path, [])
            changes.append((path, entry["self"], file_baseline))
            for line, row in entry["lines"].items():
                line_baseline = entry["baseline"].get(line, [])
                changes.append((f"{path}:{line}", row[0], line_baseline))
        for function, function_baseline in zip(
            filed_model["functions"],
            filed_model["functionBaseline"],
            strict=True,
        ):
            changes.append(
                (function["name"], function["self"], function_baseline)
            )
        for place, change, baseline in changes:
            for slot in range(width):
                moved = change[slot] if slot < len(change) else 0
                count = baseline[slot] if slot < len(baseline) else 0
                if moved < -count:
                    self.fail(
                        f"{label}: {place} falls {moved} past its baseline"
                        f" of {count} in counter slot {slot}"
                    )

    # Checks a diff lists every function its reports' function data list.
    def diff_functions_check(
        self,
        out_dir: str,
        test_name: str,
        database_model: dict[str, Any],
        regular_data: Sequence[TestReport.RawData],
    ) -> None:
        file_name = (
            f"{test_name}{test_settings.TEST_FUNCTION_DATA_FILE_SUFFIX}"
        )
        sides: list[tuple[dict[str, Any], list[tuple[str, str]]]] = []
        for raw_data in regular_data:
            file_entries = self.paths_document_check(
                raw_data.texts.get(test_settings.TEST_PATHS_DOCUMENT_NAME),
                raw_data.archive_name,
                test_settings.TEST_PATHS_DOCUMENT_NAME,
                raw_data.path,
            )
            document = self.function_data_document_check(
                raw_data, file_name, len(file_entries)
            )
            sides.append((document, file_entries))
        side_names = self.function_data_pair_names(
            [document for document, _ in sides],
            [raw_data.build_tree for raw_data in regular_data],
            f"{test_name}{test_settings.TEST_FUNCTION_DATA_FILE_SUFFIX}",
        )
        places: dict[str, tuple[str, int]] = {}
        side_costs: list[dict[str, list[int]]] = []
        side_calls: list[dict[str, int]] = []
        count_field = test_settings.TEST_FUNCTION_DATA_CALL_COUNT_FIELD
        file_field = test_settings.TEST_FUNCTION_DATA_ROW_FILE_FIELD
        image_field = test_settings.TEST_FUNCTION_DATA_ROW_IMAGE_FIELD
        pair_fields = test_settings.TEST_FUNCTION_DATA_CALL_PAIR_FIELDS
        # The modified report, read last, places a function both list.
        for (document, file_entries), names in zip(
            sides, side_names, strict=True
        ):
            images = document["images"]
            side_costs.append({})
            side_calls.append({})
            for name, function_row in zip(
                names, document["functions"], strict=True
            ):
                places[name] = (
                    self.function_data_display(
                        file_entries[function_row[file_field]],
                        images[function_row[image_field]],
                    ),
                    function_row[
                        test_settings.TEST_FUNCTION_DATA_ROW_LINE_FIELD
                    ],
                )
                side_costs[-1][name] = function_row[
                    test_settings.TEST_FUNCTION_DATA_ROW_SELF_FIELD
                ]
                side_calls[-1][name] = sum(
                    function_row[
                        test_settings.TEST_FUNCTION_DATA_ROW_CALLERS_FIELD
                    ][count_field::pair_fields]
                )
        zeros = [0] * len(sides[0][0]["counters"])
        wanted_functions: dict[str, Any] = {}
        for name, place in places.items():
            baseline_costs = side_costs[0].get(name, zeros)
            modified_costs = side_costs[1].get(name, zeros)
            wanted_functions[name] = (
                place,
                self.costs_trimmed(
                    [
                        modified_value - baseline_value
                        for baseline_value, modified_value in zip(
                            baseline_costs, modified_costs, strict=True
                        )
                    ]
                ),
                self.costs_trimmed(baseline_costs),
            )
        heat_map_model = self.heat_map_model_read(out_dir, test_name)
        self.mappings_compare(
            {
                function_entry["name"]: (
                    (function_entry["file"], function_entry["line"]),
                    function_entry["self"],
                    function_baseline,
                )
                for function_entry, function_baseline in zip(
                    heat_map_model["functions"],
                    heat_map_model["functionBaseline"],
                    strict=True,
                )
            },
            wanted_functions,
            f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js's place, self change"
            " and baseline",
            out_dir,
        )
        function_names = [
            function_link[test_settings.TEST_DATABASE_FUNCTION_NAME_FIELD]
            for function_link in database_model["functions"]
        ]
        # The start function is called, though no caller of it is recorded.
        self.mappings_compare(
            {
                function_names[
                    function_row[
                        test_settings.TEST_DATABASE_ROW_FUNCTION_FIELD
                    ]
                ]: (
                    function_row[test_settings.TEST_DATABASE_ROW_FILE_FIELD],
                    function_row[test_settings.TEST_DATABASE_ROW_LINE_FIELD],
                )
                for function_row in database_model["functionRows"]
            },
            {
                name: place
                for name, place in places.items()
                if name == test_settings.TEST_CALL_GRAPH_START_FUNCTION_NAME
                or any(calls.get(name, 0) for calls in side_calls)
            },
            f"{self.database_page_path(test_name)}'s row place",
            out_dir,
        )

    # Returns the attributes of the element the id names, none without one.
    def element_attributes(
        self, page_text: str, element_id: str
    ) -> dict[str, str] | None:
        match = re.search(
            rf'<[a-z]+ id="{re.escape(element_id)}"([^>]*)>', page_text
        )
        if match is None:
            return None
        return {
            name: html.unescape(value)
            for name, value in re.findall(
                r'\s([\w-]+)="([^"]*)"', match.group(1)
            )
        }

    def fail(self, message: str) -> NoReturn:
        sys.exit(f"error: {message}")

    # Checks the speedscope bundle holds the files its page links, no other.
    def flame_app_check(self, out_dir: str) -> None:
        app_dir = os.path.join(out_dir, _FLAME_GRAPH_APP_DIR_NAME)
        if not os.path.isdir(app_dir):
            self.fail(f"no shared speedscope bundle: {app_dir}")
        page_label = f"{_FLAME_GRAPH_VIEW_KEY}/index.html"
        page_path = os.path.join(out_dir, page_label)
        page_text = self.size_check(
            page_path,
            test_settings.TEST_FLAME_GRAPH_PAGE_LEAST_BYTES,
            page_label,
        )
        app_href = re.escape(f"../{_FLAME_GRAPH_APP_DIR_NAME}/")
        script_names = re.findall(
            rf'<script[^>]*\ssrc="{app_href}([^"/]+)"', page_text
        )
        stylesheet_names = re.findall(
            rf'<link[^>]*\shref="{app_href}([^"/]+)"', page_text
        )
        if len(script_names) != 1 or len(stylesheet_names) != 1:
            self.fail(
                f"{page_label} links the scripts {script_names} and the"
                f" stylesheets {stylesheet_names} of"
                f" {_FLAME_GRAPH_APP_DIR_NAME}/, expected one of each:"
                f" {page_path}"
            )
        stylesheet_label = f"{_FLAME_GRAPH_APP_DIR_NAME}/{stylesheet_names[0]}"
        stylesheet_path = os.path.join(out_dir, stylesheet_label)
        try:
            with open(stylesheet_path, encoding="utf-8") as handle:
                stylesheet = handle.read()
        except OSError as error:
            self.fail(f"{stylesheet_label}: {stylesheet_path}: {error}")
        font_names = re.findall(r'url\("\./([^"/]+\.woff2)"\)', stylesheet)
        if len(font_names) != 1:
            self.fail(
                f"{stylesheet_label} loads the fonts {font_names}, expected"
                f" one: {stylesheet_path}"
            )
        wanted_names = sorted([*script_names, *stylesheet_names, *font_names])
        found_names = sorted(os.listdir(app_dir))
        if found_names != wanted_names:
            self.fail(
                f"{_FLAME_GRAPH_APP_DIR_NAME}/ holds {found_names}, expected"
                f" the files its page links {wanted_names}: {app_dir}"
            )

    def flame_graph_check(
        self,
        out_dir: str,
        traced_tests: Sequence[str],
        layout: TestReport.ReportLayout,
    ) -> None:
        flame_dir = os.path.join(out_dir, _FLAME_GRAPH_VIEW_KEY)
        if not layout.is_regular_report:
            if os.path.exists(flame_dir):
                self.fail(
                    f"{_FLAME_GRAPH_VIEW_KEY}/ in a report that records no"
                    f" trace: {flame_dir}"
                )
            return
        if not os.path.isdir(flame_dir):
            self.fail(f"no {_FLAME_GRAPH_VIEW_KEY}/ directory: {flame_dir}")
        page = self.page_check(
            os.path.join(flame_dir, "index.html"),
            f"{_FLAME_GRAPH_VIEW_KEY}/index.html",
            test_settings.TEST_FLAME_GRAPH_PAGE_LEAST_BYTES,
        )
        if f"{_FLAME_GRAPH_APP_DIR_NAME}/" not in page:
            self.fail(
                f"{_FLAME_GRAPH_VIEW_KEY}/index.html does not load the shared "
                f"{_FLAME_GRAPH_APP_DIR_NAME}/ bundle: {flame_dir}/index.html"
            )
        if "loadFileFromBase64" not in page:
            self.fail(
                f"{_FLAME_GRAPH_VIEW_KEY}/index.html and its scripts never"
                f" call loadFileFromBase64: {flame_dir}/index.html"
            )
        found_names = sorted(os.listdir(flame_dir))
        wanted_names = sorted(("index.html", _FLAME_GRAPH_PROFILE_DIR_NAME))
        if found_names != wanted_names:
            self.fail(
                f"{_FLAME_GRAPH_VIEW_KEY}/ holds {found_names}, expected"
                f" {wanted_names}: {flame_dir}"
            )
        profile_dir = os.path.join(flame_dir, _FLAME_GRAPH_PROFILE_DIR_NAME)
        found_names = sorted(os.listdir(profile_dir))
        wanted_names = sorted(f"{test_name}.js" for test_name in traced_tests)
        if found_names != wanted_names:
            self.fail(
                f"{_FLAME_GRAPH_PROFILE_DIR_NAME}/ holds {found_names},"
                f" expected one script per traced test {wanted_names}:"
                f" {profile_dir}"
            )
        for test_name in traced_tests:
            self.flame_graph_profile_check(profile_dir, test_name)

    def flame_graph_profile_check(
        self, profile_dir: str, test_name: str
    ) -> None:
        path = os.path.join(profile_dir, f"{test_name}.js")
        label = f"{_FLAME_GRAPH_PROFILE_DIR_NAME}/{test_name}.js"
        script = self.size_check(
            path, test_settings.TEST_FLAME_GRAPH_SCRIPT_LEAST_BYTES, label
        )
        filed_profile = self.script_value(
            script, _FLAME_GRAPH_PROFILE_GLOBAL_NAME, test_name, path
        )
        encoded_profile = filed_profile.get("base64")
        base64_text = (
            encoded_profile if isinstance(encoded_profile, str) else ""
        )
        if not re.fullmatch(r"[A-Za-z0-9+/=]+", base64_text):
            self.fail(f"{label} files no base64 profile: {path}")
        try:
            document = json.loads(base64.b64decode(base64_text))
        except ValueError as error:
            self.fail(f"{label} base64 is not JSON: {error}: {path}")
        kinds = [
            profile.get("type") for profile in document.get("profiles", [])
        ]
        if document.get("exporter") != _FLAME_GRAPH_EXPORTER_NAME or kinds != [
            "evented"
        ]:
            self.fail(
                f"{label} does not hold one recorded trace from"
                f" {_FLAME_GRAPH_EXPORTER_NAME} (exporter"
                f" {document.get('exporter')!r}, profiles {kinds}): {path}"
            )

    # Checks a golden recording's function data document.
    def function_data_builder_check(self) -> None:
        heat_map = callgrind_to_heatmap.CallgrindToHeatmap(0)
        try:
            profile = callgrind.Callgrind().parse(
                test_settings.TEST_FUNCTION_DATA_RECORDING,
                test_settings.TEST_FUNCTION_DATA_RECORDING_NAME,
            )
            document = heat_map.function_data(
                profile,
                heat_map.profile_path_infos(profile, None),
                {
                    file_path: file_index
                    for file_index, file_path in enumerate(
                        test_settings.TEST_FUNCTION_DATA_FILE_PATHS
                    )
                },
            )
        except SystemExit as error:
            self.fail(
                "the function data of"
                f" {test_settings.TEST_FUNCTION_DATA_RECORDING_NAME}"
                f" is refused: {error}"
            )
        found = json.loads(json.dumps(document))
        if found != test_settings.TEST_FUNCTION_DATA_DOCUMENT:
            self.fail(
                "the function data of"
                f" {test_settings.TEST_FUNCTION_DATA_RECORDING_NAME} is"
                f" {found}, expected"
                f" {test_settings.TEST_FUNCTION_DATA_DOCUMENT}"
            )

    # Checks a test's function data names and places as its heat map does.
    def function_data_check(
        self,
        raw_data: TestReport.RawData,
        file_entries: Sequence[tuple[str, str]],
        out_dir: str,
        test_name: str,
    ) -> None:
        file_name = (
            f"{test_name}{test_settings.TEST_FUNCTION_DATA_FILE_SUFFIX}"
        )
        document = self.function_data_document_check(
            raw_data, file_name, len(file_entries)
        )
        heat_map_model = self.heat_map_model_read(out_dir, test_name)
        if document["counters"] != heat_map_model["heatMapTotals"]["counters"]:
            self.fail(
                f"{raw_data.archive_name}'s {file_name} records the counters"
                f" {document['counters']}, its heat map model"
                f" {heat_map_model['heatMapTotals']['counters']}:"
                f" {raw_data.path}"
            )
        images = document["images"]
        names = self.function_data_names(document)
        file_field = test_settings.TEST_FUNCTION_DATA_ROW_FILE_FIELD
        image_field = test_settings.TEST_FUNCTION_DATA_ROW_IMAGE_FIELD
        self.mappings_compare(
            {
                name: (
                    self.function_data_display(
                        file_entries[function_row[file_field]],
                        images[function_row[image_field]],
                    ),
                    function_row[
                        test_settings.TEST_FUNCTION_DATA_ROW_LINE_FIELD
                    ],
                    self.costs_trimmed(
                        function_row[
                            test_settings.TEST_FUNCTION_DATA_ROW_SELF_FIELD
                        ]
                    ),
                )
                for name, function_row in zip(
                    names, document["functions"], strict=True
                )
            },
            {
                function_entry["name"]: (
                    function_entry["file"],
                    function_entry["line"],
                    function_entry["self"],
                )
                for function_entry in heat_map_model["functions"]
            },
            f"{raw_data.archive_name}'s {file_name}, against the heat map"
            " model's place and self,",
            raw_data.path,
        )

    # Returns the path a report shows of a function data row's file.
    def function_data_display(
        self, file_entry: tuple[str, str], image_path: str
    ) -> str:
        file_path, code = file_entry
        if code != test_settings.TEST_PATHS_DOCUMENT_ERROR_CODE:
            return file_path
        return f"{os.path.basename(image_path)}/{file_path}"

    # Returns a function data document, its indexes and calls checked.
    def function_data_document_check(
        self, raw_data: TestReport.RawData, file_name: str, file_count: int
    ) -> dict[str, Any]:
        label = f"{raw_data.archive_name}'s {file_name}"
        text = raw_data.texts.get(file_name)
        if text is None:
            self.fail(f"{raw_data.archive_name} holds no {file_name}")
        try:
            document = json.loads(text)
        except ValueError as error:
            self.fail(f"{label} holds no JSON: {error}: {raw_data.path}")
        found_keys = sorted(document) if isinstance(document, dict) else []
        if found_keys != sorted(
            test_settings.TEST_FUNCTION_DATA_DOCUMENT_KEYS
        ):
            self.fail(
                f"{label} holds the keys {found_keys}, expected"
                f" {sorted(test_settings.TEST_FUNCTION_DATA_DOCUMENT_KEYS)}:"
                f" {raw_data.path}"
            )
        counter_count = len(document["counters"])
        image_count = len(document["images"])
        function_rows = document["functions"]
        side_edges: list[set[tuple[int, int, int]]] = []
        for rows_field in (
            test_settings.TEST_FUNCTION_DATA_ROW_CALLERS_FIELD,
            test_settings.TEST_FUNCTION_DATA_ROW_CALLEES_FIELD,
        ):
            side_edges.append(set())
            for row_index, function_row in enumerate(function_rows):
                if (
                    len(function_row)
                    != test_settings.TEST_FUNCTION_DATA_ROW_FIELDS
                    or not 0
                    <= function_row[
                        test_settings.TEST_FUNCTION_DATA_ROW_IMAGE_FIELD
                    ]
                    < image_count
                    or not 0
                    <= function_row[
                        test_settings.TEST_FUNCTION_DATA_ROW_FILE_FIELD
                    ]
                    < file_count
                    or len(
                        function_row[
                            test_settings.TEST_FUNCTION_DATA_ROW_SELF_FIELD
                        ]
                    )
                    != counter_count
                ):
                    self.fail(
                        f"{label} holds the row {function_row}, expected"
                        f" {test_settings.TEST_FUNCTION_DATA_ROW_FIELDS}"
                        " fields, an image"
                        f" of its {image_count}, a file of the {file_count}"
                        f" of {test_settings.TEST_PATHS_DOCUMENT_NAME} and"
                        f" {counter_count} counters: {raw_data.path}"
                    )
                call_numbers = function_row[rows_field]
                pair_fields = test_settings.TEST_FUNCTION_DATA_CALL_PAIR_FIELDS
                if len(call_numbers) % pair_fields:
                    self.fail(
                        f"{label} gives the row {row_index} the"
                        f" {len(call_numbers)} call numbers {call_numbers},"
                        f" expected pairs of {pair_fields}: {raw_data.path}"
                    )
                for pair_start in range(0, len(call_numbers), pair_fields):
                    call_pair = call_numbers[
                        pair_start : pair_start + pair_fields
                    ]
                    partner_index, call_count = call_pair
                    if (
                        not 0 <= partner_index < len(function_rows)
                        or call_count <= 0
                    ):
                        self.fail(
                            f"{label} gives the row {row_index} the call"
                            f" {call_pair}, expected one of its"
                            f" {len(function_rows)} functions and a call:"
                            f" {raw_data.path}"
                        )
                    side_edges[-1].add(
                        (partner_index, row_index, call_count)
                        if rows_field
                        == test_settings.TEST_FUNCTION_DATA_ROW_CALLERS_FIELD
                        else (row_index, partner_index, call_count)
                    )
        one_sided_edges = sorted(side_edges[0] ^ side_edges[1])
        if one_sided_edges:
            self.fail(
                f"{label} lists {len(one_sided_edges)} calls in the callers or"
                f" the callees alone, first {one_sided_edges[0]}:"
                f" {raw_data.path}"
            )
        return document

    # Returns the name a report gives each row of function data documents.
    def function_data_names(self, document: dict[str, Any]) -> list[str]:
        images = document["images"]
        base_paths: dict[str, set[str]] = {}
        for image_path in images:
            base_paths.setdefault(os.path.basename(image_path), set()).add(
                image_path
            )
        image_names = {
            image_path: base_name if len(paths) == 1 else image_path
            for base_name, paths in base_paths.items()
            for image_path in paths
        }
        image_paths: dict[str, set[str]] = {}
        for function_row in document["functions"]:
            image_paths.setdefault(
                function_row[test_settings.TEST_FUNCTION_DATA_ROW_NAME_FIELD],
                set(),
            ).add(
                images[
                    function_row[
                        test_settings.TEST_FUNCTION_DATA_ROW_IMAGE_FIELD
                    ]
                ]
            )
        names: list[str] = []
        for function_row in document["functions"]:
            name = function_row[
                test_settings.TEST_FUNCTION_DATA_ROW_NAME_FIELD
            ]
            image_path = images[
                function_row[test_settings.TEST_FUNCTION_DATA_ROW_IMAGE_FIELD]
            ]
            names.append(
                f"{image_names[image_path]}/{name}"
                if len(image_paths[name]) > 1
                else name
            )
        return names

    # Returns each report's names of a diff's functions, paired by image.
    def function_data_pair_names(
        self,
        documents: Sequence[dict[str, Any]],
        build_trees: Sequence[str],
        label: str,
    ) -> list[list[str]]:
        side_rows: dict[str, tuple[dict[str, int], dict[str, int]]] = {}
        for side, (document, build_tree) in enumerate(
            zip(documents, build_trees, strict=True)
        ):
            for row_index, function_row in enumerate(document["functions"]):
                image_path = document["images"][
                    function_row[
                        test_settings.TEST_FUNCTION_DATA_ROW_IMAGE_FIELD
                    ]
                ]
                side_rows.setdefault(
                    function_row[
                        test_settings.TEST_FUNCTION_DATA_ROW_NAME_FIELD
                    ],
                    ({}, {}),
                )[side][image_path.removeprefix(f"{build_tree}/")] = row_index
        # Each diff function's name, shown image and row in each report.
        functions: list[tuple[str, str, tuple[int | None, int | None]]] = []
        for name, (baseline_rows, modified_rows) in side_rows.items():
            functions.extend(
                (name, location, (baseline_rows[location], row_index))
                for location, row_index in modified_rows.items()
                if location in baseline_rows
            )
            baseline_left = [
                location
                for location in baseline_rows
                if location not in modified_rows
            ]
            modified_left = [
                location
                for location in modified_rows
                if location not in baseline_rows
            ]
            if len(baseline_left) == 1 and len(modified_left) == 1:
                functions.append(
                    (
                        name,
                        modified_left[0],
                        (
                            baseline_rows[baseline_left[0]],
                            modified_rows[modified_left[0]],
                        ),
                    )
                )
            elif baseline_left and modified_left:
                self.fail(
                    f"{label}: {name} is left at {baseline_left} in the"
                    f" baseline and at {modified_left} in the modified"
                    " report, which no pairing resolves"
                )
            else:
                functions.extend(
                    (name, location, (baseline_rows[location], None))
                    for location in baseline_left
                )
                functions.extend(
                    (name, location, (None, modified_rows[location]))
                    for location in modified_left
                )
        base_locations: dict[str, set[str]] = {}
        name_counts: dict[str, int] = {}
        for name, location, _ in functions:
            base_locations.setdefault(os.path.basename(location), set()).add(
                location
            )
            name_counts[name] = name_counts.get(name, 0) + 1
        side_names = [
            [""] * len(document["functions"]) for document in documents
        ]
        for name, location, row_indexes in functions:
            base_name = os.path.basename(location)
            image_name = (
                base_name if len(base_locations[base_name]) == 1 else location
            )
            for names, row_index in zip(side_names, row_indexes, strict=True):
                if row_index is not None:
                    names[row_index] = (
                        f"{image_name}/{name}"
                        if name_counts[name] > 1
                        else name
                    )
        return side_names

    # Checks two golden function data documents' diff and its refusals.
    def function_diff_check(self) -> None:
        try:
            baseline_document, modified_document = (
                callgrind.function_data_parse(json.dumps(document), name)
                for document, name in (
                    (
                        test_settings.TEST_FUNCTION_DIFF_BASELINE_DOCUMENT,
                        test_settings.TEST_FUNCTION_DIFF_BASELINE_NAME,
                    ),
                    (
                        test_settings.TEST_FUNCTION_DIFF_MODIFIED_DOCUMENT,
                        test_settings.TEST_FUNCTION_DIFF_MODIFIED_NAME,
                    ),
                )
            )
            function_diff = callgrind_diff.CallgrindDiff.function_diff(
                baseline_document,
                modified_document,
                list(test_settings.TEST_FUNCTION_DIFF_BASELINE_PATHS),
                list(test_settings.TEST_FUNCTION_DIFF_MODIFIED_PATHS),
                test_settings.TEST_FUNCTION_DIFF_BUILD_TREES,
            )
        except SystemExit as error:
            self.fail(
                f"the diff of {test_settings.TEST_FUNCTION_DIFF_BASELINE_NAME}"
                " and"
                f" {test_settings.TEST_FUNCTION_DIFF_MODIFIED_NAME} is"
                f" refused: {error}"
            )
        found = json.loads(json.dumps(function_diff))
        if found != test_settings.TEST_FUNCTION_DIFF:
            self.fail(
                f"the diff of {test_settings.TEST_FUNCTION_DIFF_BASELINE_NAME}"
                " and"
                f" {test_settings.TEST_FUNCTION_DIFF_MODIFIED_NAME} is"
                f" {found}, expected"
                f" {test_settings.TEST_FUNCTION_DIFF}"
            )
        ambiguous_name = test_settings.TEST_FUNCTION_DIFF_AMBIGUOUS_NAME
        for image_sets in test_settings.TEST_FUNCTION_DIFF_AMBIGUOUS_CASES:
            baseline_document, modified_document = (
                callgrind.function_data_parse(
                    json.dumps(
                        {
                            "counters": ["Ir"],
                            "images": list(images),
                            "functions": [
                                [
                                    ambiguous_name,
                                    image_index,
                                    0,
                                    1,
                                    [1],
                                    [],
                                    [],
                                ]
                                for image_index in range(len(images))
                            ],
                        }
                    ),
                    name,
                )
                for images, name in zip(
                    image_sets,
                    (
                        test_settings.TEST_FUNCTION_DIFF_BASELINE_NAME,
                        test_settings.TEST_FUNCTION_DIFF_MODIFIED_NAME,
                    ),
                    strict=True,
                )
            )
            try:
                callgrind_diff.CallgrindDiff.function_diff(
                    baseline_document,
                    modified_document,
                    list(test_settings.TEST_FUNCTION_DIFF_AMBIGUOUS_PATHS),
                    list(test_settings.TEST_FUNCTION_DIFF_AMBIGUOUS_PATHS),
                    test_settings.TEST_FUNCTION_DIFF_BUILD_TREES,
                )
            except SystemExit as error:
                if str(error).startswith(
                    test_settings.TEST_FUNCTION_DIFF_AMBIGUOUS_ERROR
                ):
                    continue
                self.fail(
                    "the diff of"
                    f" {ambiguous_name} in"
                    f" {image_sets[0]} and in {image_sets[1]} is refused"
                    f" with {error}, expected"
                    f" {test_settings.TEST_FUNCTION_DIFF_AMBIGUOUS_ERROR}"
                )
            self.fail(
                "the diff takes"
                f" {ambiguous_name} in"
                f" {image_sets[0]} and in {image_sets[1]}, expected"
                f" {test_settings.TEST_FUNCTION_DIFF_AMBIGUOUS_ERROR}"
            )

    # Checks a name two images record is listed under each image, not alone.
    def function_images_check(
        self, profile_text: str, out_dir: str, test_name: str, file_name: str
    ) -> None:
        spelled_names: dict[str, dict[str, str]] = {}
        image_paths: dict[str, set[str]] = {}
        image_path = function_name = ""
        is_call_line = False
        for line in profile_text.split("\n"):
            name_match = re.fullmatch(
                test_settings.TEST_CALLGRIND_NAME_LINE_PATTERN, line
            )
            if name_match:
                callee_mark, image_key, function_key, ident, spelling = (
                    name_match.groups()
                )
                spelled = spelled_names.setdefault(
                    image_key or function_key, {}
                )
                if ident is None:
                    name = spelling
                elif spelling:
                    name = spelled[ident] = spelling
                else:
                    name = spelled[ident]
                if callee_mark:
                    continue
                if image_key:
                    image_path = name
                else:
                    function_name = name
            elif line.startswith(test_settings.TEST_CALLGRIND_CALLS_PREFIX):
                is_call_line = True
            elif re.match(
                test_settings.TEST_CALLGRIND_COST_LINE_PATTERN, line
            ):
                if not is_call_line:
                    image_paths.setdefault(function_name, set()).add(
                        image_path
                    )
                is_call_line = False
        base_paths: dict[str, set[str]] = {}
        for paths in image_paths.values():
            for path in paths:
                base_paths.setdefault(os.path.basename(path), set()).add(path)
        image_names = {
            path: base_name if len(paths) == 1 else path
            for base_name, paths in base_paths.items()
            for path in paths
        }
        heat_map_model = self.heat_map_model_read(out_dir, test_name)
        listed_names = {
            function_entry["name"]
            for function_entry in heat_map_model["functions"]
        }
        for name, paths in sorted(image_paths.items()):
            wanted_names = {f"{image_names[path]}/{name}" for path in paths}
            if len(paths) > 1 and (
                name in listed_names or not wanted_names <= listed_names
            ):
                self.fail(
                    f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js lists"
                    f" {sorted(listed_names & (wanted_names | {name}))},"
                    f" expected {sorted(wanted_names)}, as {file_name}"
                    f" records {name} in {sorted(paths)}: {out_dir}"
                )

    # Checks each function of a golden recording is placed at its line.
    def function_line_check(self) -> None:
        heat_map = callgrind_to_heatmap.CallgrindToHeatmap(0)
        try:
            profile = callgrind.Callgrind().parse(
                test_settings.TEST_FUNCTION_LINE_RECORDING,
                test_settings.TEST_FUNCTION_LINE_RECORDING_NAME,
            )
        except SystemExit as error:
            self.fail(
                "the parser refuses"
                f" {test_settings.TEST_FUNCTION_LINE_RECORDING_NAME}:"
                f" {error}"
            )
        found_lines = {
            name: tuple(heat_map.function_line(profile, name))
            for name in sorted(profile.function_home)
        }
        if found_lines != test_settings.TEST_FUNCTION_LINES:
            self.fail(
                f"{test_settings.TEST_FUNCTION_LINE_RECORDING_NAME} places its"
                " functions"
                f" at {found_lines}, expected"
                f" {test_settings.TEST_FUNCTION_LINES}"
            )
        try:
            callgrind.Callgrind().parse(
                test_settings.TEST_FUNCTION_LINE_RECORDING
                + test_settings.TEST_FUNCTION_ENTRY_CONFLICT,
                test_settings.TEST_FUNCTION_LINE_RECORDING_NAME,
            )
        except SystemExit:
            return
        self.fail(
            "the parser takes"
            f" {test_settings.TEST_FUNCTION_LINE_RECORDING_NAME} with"
            f" {test_settings.TEST_FUNCTION_ENTRY_CONFLICT!r} after it, two"
            " calls naming"
            " one function at two entry lines"
        )

    # Checks no function is listed both alone and under an image's name.
    def function_names_check(
        self, database_model: dict[str, Any], label: str, path: str
    ) -> None:
        names = {
            function_link[test_settings.TEST_DATABASE_FUNCTION_NAME_FIELD]
            for function_link in database_model["functions"]
        }
        for name in sorted(names):
            image_name, separator, bare_name = name.partition("/")
            if separator and bare_name in names:
                self.fail(
                    f"{label} lists {bare_name} both alone and under"
                    f" {image_name} as {name}: {path}"
                )

    # Checks each listed call was recorded and each function ran in a file.
    def heat_map_calls_check(self, filed_model: Any, label: str) -> None:
        files = filed_model["files"]
        functions = filed_model["functions"]
        call_rows = [
            (f"{path}:{line}", call_row)
            for path, file_entry in files.items()
            for line, line_rows in file_entry["callees"].items()
            for call_row in line_rows
        ] + [
            (function_entry["name"], call_row)
            for function_entry in functions
            for call_row in function_entry["callers"]
        ]
        for place, call_row in call_rows:
            count = call_row[test_settings.TEST_HEAT_MAP_CALL_ROW_COUNT_FIELD]
            if count <= 0:
                listed_function = functions[
                    call_row[
                        test_settings.TEST_HEAT_MAP_CALL_ROW_FUNCTION_FIELD
                    ]
                ]
                self.fail(
                    f"{label}: {place} lists a call row of"
                    f" {listed_function['name']} counting {count} calls"
                )
        for function_entry in functions:
            if not any(function_entry["self"]):
                self.fail(
                    f"{label}: {function_entry['name']} holds no self cost"
                )
            if function_entry["file"] not in files:
                self.fail(
                    f"{label}: {function_entry['name']} is placed in"
                    f" {function_entry['file']!r}, a file the model lacks"
                )

    def heat_map_check(
        self,
        out_dir: str,
        tests: Sequence[str],
        layout: TestReport.ReportLayout,
    ) -> None:
        heat_map_dir = os.path.join(out_dir, _HEAT_MAP_VIEW_KEY)
        path = os.path.join(heat_map_dir, "index.html")
        text = self.page_check(
            path,
            f"{_HEAT_MAP_VIEW_KEY}/index.html",
            test_settings.TEST_HEAT_MAP_PAGE_LEAST_BYTES,
            test_settings.HEAT_MAP_PAGE_TITLE,
        )
        if "report_ui_.layout_activate" not in text:
            self.fail(
                f"{_HEAT_MAP_VIEW_KEY}/index.html is missing its runtime"
                f" script (no report_ui_.layout_activate): {path}"
            )
        model_dir = os.path.join(heat_map_dir, _HEAT_MAP_MODEL_DIR_NAME)
        if not os.path.isdir(model_dir):
            self.fail(f"no heat map model scripts: {model_dir}")
        found_names = sorted(os.listdir(model_dir))
        wanted_names = sorted(f"{test_name}.js" for test_name in tests)
        if found_names != wanted_names:
            self.fail(
                f"{_HEAT_MAP_MODEL_DIR_NAME}/ holds {found_names}, expected"
                f" one script per test {wanted_names}: {model_dir}"
            )
        for test_name in tests:
            script_path = os.path.join(model_dir, f"{test_name}.js")
            script = self.size_check(
                script_path,
                test_settings.TEST_HEAT_MAP_MODEL_LEAST_BYTES,
                f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js",
            )
            filed_model = self.script_value(
                script, _HEAT_MAP_MODEL_GLOBAL_NAME, test_name, script_path
            )
            if (
                not {"heatMapTotals", "files", "functions"}
                <= filed_model.keys()
            ):
                self.fail(
                    f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js files a"
                    f" model lacking heatMapTotals, files or functions:"
                    f" {script_path}"
                )
            self.model_sources_check(
                out_dir,
                filed_model,
                f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js",
            )
            if layout.is_regular_report:
                self.heat_map_calls_check(
                    filed_model, f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js"
                )
            if layout.has_baselines:
                self.diff_baseline_check(
                    filed_model, f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js"
                )

    # Returns a test's heat map model.
    def heat_map_model_read(self, out_dir: str, test_name: str) -> Any:
        model_label = f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js"
        model_path = os.path.join(
            out_dir,
            _HEAT_MAP_VIEW_KEY,
            _HEAT_MAP_MODEL_DIR_NAME,
            f"{test_name}.js",
        )
        script = self.size_check(
            model_path,
            test_settings.TEST_HEAT_MAP_MODEL_LEAST_BYTES,
            model_label,
        )
        return self.script_value(
            script, _HEAT_MAP_MODEL_GLOBAL_NAME, test_name, model_path
        )

    def home_dir_check(self, out_dir: str) -> None:
        home = os.path.expanduser("~")
        if home == "~":
            self.fail("no home directory to check the report against")
        for root, _dirs, names in os.walk(out_dir):
            for name in names:
                path = os.path.join(root, name)
                with open(path, "rb") as handle:
                    data = handle.read()
                if home.encode("utf-8") in data:
                    self.fail(
                        f"{os.path.relpath(path, out_dir)} leaks the"
                        f" author's home directory {home!r} -- reports are"
                        f" copied around and must not reveal who made"
                        f" them: {path}"
                    )

    def manifest_check(
        self, out_dir: str, layout: TestReport.ReportLayout
    ) -> None:
        path = os.path.join(out_dir, "MANIFEST.txt")
        text = self.size_check(
            path, test_settings.TEST_MANIFEST_LEAST_BYTES, "MANIFEST.txt"
        )
        first = text.split("\n", 1)[0]
        if first != layout.manifest_version:
            self.fail(
                f"MANIFEST.txt line 1 found {first!r}, expected the"
                f" version line {layout.manifest_version!r}: {path}"
            )
        for label in layout.manifest_labels:
            if not re.search(rf"^{label}=.+$", text, re.M):
                self.fail(
                    f"MANIFEST.txt has no '{label}=' header row, so a"
                    f" reader of this report cannot show it: {path}"
                )
        for label in layout.manifest_recorded_labels:
            recorded_unix = self.manifest_recorded_value(text, label)
            if not recorded_unix.isdigit():
                self.fail(
                    f"MANIFEST.txt {label}= row starts {recorded_unix!r},"
                    f" expected the unix time: {path}"
                )
        recorded = self.manifest_value(text, _REPORT_MANIFEST_CHECKSUM_LABEL)
        if not recorded:
            self.fail(
                "MANIFEST.txt has no"
                f" '{_REPORT_MANIFEST_CHECKSUM_LABEL}=' row, so this"
                " report's files cannot be verified; expected one"
                f" beside the version line {layout.manifest_version!r}:"
                f" {path}"
            )
        found = self.checksum_compute(out_dir)
        if found != recorded:
            self.fail(
                "this report does not match its recorded"
                f" {_REPORT_MANIFEST_CHECKSUM_LABEL}: found {found!r},"
                f" expected {recorded!r} -- a file was added, removed or"
                " edited"
                f" after the report was written: {out_dir}"
            )

    # Returns a report's build tree, its executable's path less the tool's.
    def manifest_build_tree(self, text: str, path: str) -> str:
        executable = self.manifest_value(
            text, test_settings.TEST_MANIFEST_EXECUTABLE_LABEL
        )
        build_tree = executable.removesuffix(
            f"/{test_settings.TEST_PERF_TOOL_TREE_PATH}"
        )
        if not executable or build_tree == executable:
            self.fail(
                f"MANIFEST.txt {test_settings.TEST_MANIFEST_EXECUTABLE_LABEL}="
                " row is"
                f" {executable!r}, no path ending in"
                f" {test_settings.TEST_PERF_TOOL_TREE_PATH}: {path}"
            )
        return build_tree

    def manifest_recorded_value(self, text: str, label: str) -> str:
        return self.manifest_value(text, label).split(" ", 1)[0]

    def manifest_value(self, text: str, label: str) -> str:
        match = re.search(rf"^{re.escape(label)}=(.*)$", text, re.M)
        return match.group(1).strip() if match else ""

    # Faults the first name two mappings give apart.
    def mappings_compare(
        self,
        found: dict[str, Any],
        wanted: dict[str, Any],
        label: str,
        path: str,
    ) -> None:
        for name in sorted(found.keys() | wanted.keys()):
            if found.get(name) != wanted.get(name):
                self.fail(
                    f"{label} gives {name} {found.get(name)!r}, expected"
                    f" {wanted.get(name)!r}: {path}"
                )

    def member_text(
        self, archive: tarfile.TarFile, member: tarfile.TarInfo
    ) -> str:
        handle = archive.extractfile(member)
        if handle is None:
            raise ValueError(f"{member.name} in {archive.name} is not a file")
        return handle.read().decode("utf-8")

    def menu_check(
        self,
        path: str,
        page_text: str,
        tests: Sequence[str],
        layout: TestReport.ReportLayout,
        recorded_counter_names: Sequence[str],
        help_name: str,
    ) -> None:
        match = re.search(
            r'<nav id="menu-" class="strip-"([^>]*)></nav>', page_text
        )
        if not match:
            self.fail(f"overview index.html has no empty menu strip: {path}")
        found = {
            name: html.unescape(value)
            for name, value in re.findall(
                r'\s(data-[\w-]+)="([^"]*)"', match.group(1)
            )
        }
        wanted = {
            "data-counter-names-": json.dumps(
                [
                    *recorded_counter_names,
                    *test_settings.TEST_DERIVED_COUNTER_NAMES,
                ]
            ),
            "data-help-href-": help_name,
            "data-regular-report-": "1" if layout.is_regular_report else "0",
            "data-test-names-": json.dumps(list(tests), ensure_ascii=False),
        }
        if found != wanted:
            self.fail(
                f"overview index.html menu strip attributes are {found},"
                f" expected {wanted}: {path}"
            )

    def overview_check(
        self,
        out_dir: str,
        tests: Sequence[str],
        layout: TestReport.ReportLayout,
        help_name: str,
    ) -> None:
        path = os.path.join(out_dir, "index.html")
        self.page_check(
            path,
            "index.html",
            test_settings.TEST_OVERVIEW_PAGE_LEAST_BYTES,
            test_settings.TEST_OVERVIEW_PAGE_TITLE,
        )
        with open(path, encoding="utf-8") as handle:
            page_text = handle.read()
        if test_settings.TEST_OVERVIEW_TESTS_HEADING_MARKUP not in page_text:
            self.fail(f"overview index.html has no 'tests' section: {path}")
        tests_attributes = self.overview_tests_attributes(page_text, path)
        if "data-diff-" in tests_attributes:
            self.fail(
                "overview index.html's tests table data holds data-diff-,"
                f" which both reports' one column list leaves out: {path}"
            )
        self.overview_sections_check(page_text, layout, path)
        page_hrefs = self.overview_tests_hrefs(page_text, path)
        for test_name in tests:
            if (
                f"#test={test_name}&view="
                f"{test_settings.TEST_DATABASE_VIEW_KEY}" not in page_hrefs
            ):
                self.fail(
                    "overview index.html is missing its"
                    f" {test_name} database link: {path}"
                )
        self.menu_check(
            path,
            page_text,
            tests,
            layout,
            self.report_counter_names(out_dir, tests),
            help_name,
        )
        for heading in layout.header_blocks:
            if heading not in page_text:
                self.fail(
                    "overview index.html has no header block heading"
                    f" {heading!r}: {path}"
                )
        timing_document = self.timer_artifacts_check(
            out_dir, page_text, tests, layout
        )
        self.overview_columns_check(
            tests_attributes, layout, timing_document, path
        )

    # Checks each tests row, a regular one's values, a diff one's changes.
    def overview_columns_check(
        self,
        attributes: dict[str, str],
        layout: TestReport.ReportLayout,
        timing_document: dict[str, dict[str, float]] | None,
        path: str,
    ) -> None:
        ratio_fields = test_settings.TEST_OVERVIEW_RATIO_FIELDS
        value_fields = test_settings.TEST_OVERVIEW_VALUE_FIELDS
        for table_row in self.table_data_rows(
            attributes, "overview index.html", path
        ):
            if len(table_row) != test_settings.TEST_OVERVIEW_ROW_FIELD_COUNT:
                self.fail(
                    f"overview index.html's tests row {table_row} has"
                    f" {len(table_row)} cells, expected"
                    f" {test_settings.TEST_OVERVIEW_ROW_FIELD_COUNT}: {path}"
                )
            field_patterns = (
                [
                    (
                        test_settings.TEST_OVERVIEW_TIME_PER_LOOP_FIELD,
                        test_settings.TEST_OVERVIEW_TIME_PER_LOOP_PATTERN,
                    ),
                    *(
                        (
                            ratio_field,
                            test_settings.TEST_OVERVIEW_RATIO_PATTERN,
                        )
                        for ratio_field in ratio_fields
                    ),
                ]
                if layout.is_regular_report
                else [
                    (change_field, test_settings.TEST_OVERVIEW_CHANGE_PATTERN)
                    for change_field in value_fields
                ]
            )
            for value_field, value_pattern in field_patterns:
                value_text = (
                    table_row[value_field]
                    if layout.is_regular_report
                    else self.overview_change_text(table_row[value_field])
                )
                if not isinstance(value_text, str) or not re.fullmatch(
                    value_pattern, value_text
                ):
                    cell_text = (
                        ""
                        if layout.is_regular_report
                        else test_settings.TEST_OVERVIEW_CHANGE_CELL_TEXT
                    )
                    self.fail(
                        f"overview index.html's tests row {table_row} holds"
                        f" {table_row[value_field]!r} in cell {value_field},"
                        f" expected {value_pattern}{cell_text}: {path}"
                    )
            else:
                if timing_document is not None:
                    self.overview_values_check(
                        table_row, timing_document, path
                    )

    # Returns a diff change cell's text, none for a heat cell unlike its text.
    def overview_change_text(self, change_cell: Any) -> str | None:
        if change_cell == "":
            return change_cell
        if not isinstance(change_cell, dict) or set(change_cell) != {
            "text",
            "heat_percent",
        }:
            return None
        change_text, heat_percent = (
            change_cell["text"],
            change_cell["heat_percent"],
        )
        if (
            not isinstance(change_text, str)
            or type(heat_percent) not in (int, float)
            or not math.isfinite(heat_percent)
        ):
            return None
        arrow_sign = (
            1
            if change_text.startswith("▲")
            else -1
            if change_text.startswith("▼")
            else 0
        )
        if arrow_sign != (heat_percent > 0) - (heat_percent < 0):
            return None
        percent_match = re.fullmatch(r"[▲▼] *(-?\d+\.\d{2})%", change_text)
        if percent_match and (
            abs(float(percent_match.group(1)) - heat_percent)
            > test_settings.TEST_OVERVIEW_CHANGE_LARGEST_ERROR
        ):
            return None
        return change_text

    # Checks a regular row's cells print its timing document's values.
    def overview_values_check(
        self,
        table_row: list[Any],
        timing_document: dict[str, dict[str, float]],
        path: str,
    ) -> None:
        test_name = (
            table_row[0].get("text", "")
            if isinstance(table_row[0], dict)
            else ""
        )
        if test_name not in timing_document:
            self.fail(
                f"overview index.html's tests row {table_row} names no test"
                f" of {test_settings.TEST_TIMING_DOCUMENT_NAME}: {path}"
            )
        for value_field, value_name in zip(
            test_settings.TEST_OVERVIEW_VALUE_FIELDS,
            test_settings.TEST_TIMING_VALUE_NAMES,
            strict=True,
        ):
            value = timing_document[test_name][value_name]
            value_text = table_row[value_field]
            unit_seconds = 1.0
            largest_error = test_settings.TEST_OVERVIEW_RATIO_LARGEST_ERROR
            is_time = (
                value_field == test_settings.TEST_OVERVIEW_TIME_PER_LOOP_FIELD
            )
            if is_time and value_text:
                unit_text = value_text.lstrip("0123456789.")
                unit_seconds = test_settings.TEST_OVERVIEW_TIME_UNIT_SECONDS[
                    unit_text
                ]
                value_text = value_text.removesuffix(unit_text)
                largest_error = test_settings.TEST_OVERVIEW_TIME_LARGEST_ERROR
            if value:
                is_printed = bool(value_text) and (
                    abs(float(value_text) * unit_seconds - value)
                    <= largest_error * unit_seconds
                )
            else:
                is_printed = not value_text
            if not is_printed:
                self.fail(
                    f"overview index.html's tests row {table_row} prints"
                    f" {value_name} {value} of"
                    f" {test_settings.TEST_TIMING_DOCUMENT_NAME}"
                    f" as {table_row[value_field]!r}: {path}"
                )

    # Checks the overview shows its tests, then its manifest, then raw data.
    def overview_sections_check(
        self, page_text: str, layout: TestReport.ReportLayout, path: str
    ) -> None:
        section_markups = (
            test_settings.TEST_OVERVIEW_TESTS_HEADING_MARKUP,
            *layout.header_blocks,
            *(
                (test_settings.TEST_OVERVIEW_RAW_DATA_MARKUP,)
                if layout.has_timer_artifacts
                else ()
            ),
        )
        section_places = [page_text.find(markup) for markup in section_markups]
        if -1 in section_places or section_places != sorted(section_places):
            self.fail(
                f"overview index.html places the sections {section_markups}"
                f" at {section_places}, expected each in that order: {path}"
            )

    def overview_test_names(self, index_path: str, out_dir: str) -> list[str]:
        with open(index_path, encoding="utf-8") as handle:
            text = handle.read()
        names: list[str] = []
        linked_names: set[str] = set()
        for href in self.overview_tests_hrefs(text, index_path):
            match = re.fullmatch(
                r"#test=([\w.-]+)&view="
                f"{re.escape(test_settings.TEST_DATABASE_VIEW_KEY)}",
                href,
            )
            if not match or match.group(1) in linked_names:
                continue
            test_name = match.group(1)
            linked_names.add(test_name)
            database_page_path = self.database_page_path(test_name)
            if not os.path.isfile(os.path.join(out_dir, database_page_path)):
                self.fail(
                    f"overview index.html links {href}, and there is no"
                    f" {database_page_path}: {index_path}"
                )
            names.append(test_name)
        return names

    # Returns the attributes of the overview's tests table data.
    def overview_tests_attributes(
        self, page_text: str, path: str
    ) -> dict[str, str]:
        attributes = self.element_attributes(
            page_text, test_settings.TEST_OVERVIEW_TESTS_TABLE_DATA_ID
        )
        if attributes is None:
            self.fail(
                "overview index.html has no"
                f" {test_settings.TEST_OVERVIEW_TESTS_TABLE_DATA_ID} table"
                f" data: {path}"
            )
        return attributes

    # Returns every address the overview's tests table data links.
    def overview_tests_hrefs(self, page_text: str, path: str) -> list[str]:
        return self.table_data_hrefs(
            self.table_data_rows(
                self.overview_tests_attributes(page_text, path),
                "overview index.html",
                path,
            )
        )

    def page_check(
        self,
        path: str,
        label: str,
        min_bytes: int,
        want_title: str | None = None,
    ) -> str:
        text = self.size_check(path, min_bytes, label)
        if "<title>" not in text:
            self.fail(f"{label} has no <title>: {path}")
        elif want_title is not None:
            match = re.search(r"<title>(.*?)</title>", text, re.S)
            got = match.group(1) if match else ""
            if got != want_title:
                self.fail(
                    f"{label} title is {got!r}, expected"
                    f" {want_title!r}: {path}"
                )
        if "</html>" not in text:
            self.fail(
                f"{label} is not a closed HTML document (no </html>): {path}"
            )
        head_match = re.search(r"<head>(.*?)</head>", text, re.S)
        head_scripts = re.findall(
            r'<script src="(?:[^"]*/)?([^"/]+)"',
            head_match.group(1) if head_match else "",
        )
        preamble_count = len(test_settings.TEST_PAGE_PREAMBLE_SCRIPT_NAMES)
        if tuple(head_scripts[:preamble_count]) != (
            test_settings.TEST_PAGE_PREAMBLE_SCRIPT_NAMES
        ):
            self.fail(
                f"{label} head opens with the scripts {head_scripts}, expected"
                f" {list(test_settings.TEST_PAGE_PREAMBLE_SCRIPT_NAMES)}:"
                f" {path}"
            )
        for marker in (
            "__DATA__",
            "Traceback (most recent call last)",
            "NaN%",
        ):
            if marker in text:
                self.fail(
                    f"{label} contains a leftover template/error marker "
                    f"{marker!r}: {path}"
                )
        return self.page_scripts(path, text)

    def page_scripts(self, path: str, text: str) -> str:
        parts = [text]
        page_dir = os.path.dirname(path)
        for href in re.findall(
            r'<(?:script[^>]*\ssrc|link[^>]*\shref)="([^"]+)"', text
        ):
            asset = os.path.join(page_dir, href)
            try:
                with open(asset, encoding="utf-8") as handle:
                    parts.append(handle.read())
            except OSError as error:
                self.fail(f"{path} links {href}, which is unreadable: {error}")
        return "\n".join(parts)

    def page_title(self, index_path: str) -> str | None:
        with open(index_path, encoding="utf-8") as handle:
            match = re.search(r"<title>(.*?)</title>", handle.read())
        return match.group(1) if match else None

    # Returns the paths document a diff derives from the archive, in order.
    def paths_document_check(
        self, text: str | None, archive_name: str, paths_name: str, path: str
    ) -> list[tuple[str, str]]:
        if text is None:
            self.fail(f"{archive_name} holds no {paths_name}: {path}")
        try:
            document = json.loads(text)
        except ValueError as error:
            self.fail(f"{paths_name} holds no JSON: {error}: {path}")
        if not isinstance(document, list):
            self.fail(f"{paths_name} holds no array of paths: {path}")
        file_entries: list[tuple[str, str]] = []
        path_key, code_key = test_settings.TEST_PATHS_DOCUMENT_KEYS
        for file_entry in document:
            entry_keys = (
                sorted(file_entry) if isinstance(file_entry, dict) else []
            )
            if entry_keys != sorted(test_settings.TEST_PATHS_DOCUMENT_KEYS):
                self.fail(
                    f"{paths_name} holds {file_entry!r}, expected an object"
                    " of the keys"
                    f" {' '.join(test_settings.TEST_PATHS_DOCUMENT_KEYS)}:"
                    f" {path}"
                )
            file_path, code = file_entry[path_key], file_entry[code_key]
            if code not in test_settings.TEST_PATHS_DOCUMENT_CODES:
                self.fail(
                    f"{paths_name} codes {file_path} as {code!r}, not one of"
                    f" {' '.join(test_settings.TEST_PATHS_DOCUMENT_CODES)}:"
                    f" {path}"
                )
            if file_path != os.path.normpath(file_path).lstrip("/"):
                self.fail(
                    f"{paths_name} lists {file_path}, which is no canonical"
                    f" path: {path}"
                )
            if file_entries and file_path <= file_entries[-1][0]:
                self.fail(
                    f"{paths_name} lists {file_path} after"
                    f" {file_entries[-1][0]}, out of path order: {path}"
                )
            file_entries.append((file_path, code))
        return file_entries

    # Checks the parser reads a recording without writing to stderr.
    def profile_quiet_check(
        self, text: str, archive_name: str, file_name: str, path: str
    ) -> None:
        written = io.StringIO()
        with contextlib.redirect_stderr(written):
            callgrind.Callgrind().parse(text, file_name)
        if written.getvalue():
            self.fail(
                f"{archive_name}: parsing {file_name} wrote"
                f" {written.getvalue()!r} to stderr: {path}"
            )

    # Returns each file of a regular report's raw data archive by its name.
    def raw_data_texts(self, report_dir: str) -> TestReport.RawData:
        manifest_path = os.path.join(report_dir, "MANIFEST.txt")
        try:
            with open(manifest_path, encoding="utf-8") as handle:
                manifest_text = handle.read()
        except OSError as error:
            self.fail(f"no report manifest: {error}: {manifest_path}")
        recorded_time = self.manifest_recorded_value(
            manifest_text, _LAYOUT_FULL.manifest_recorded_labels[0]
        )
        archive_name = (
            f"{test_settings.TEST_TIMER_ARTIFACTS_PREFIX}{recorded_time}"
            f"{_REPORT_RAW_ARCHIVE_SUFFIX}"
        )
        path = os.path.join(report_dir, archive_name)
        try:
            with tarfile.open(path, "r:xz") as archive:
                texts = {
                    os.path.basename(member.name): self.member_text(
                        archive, member
                    )
                    for member in archive.getmembers()
                    if member.isfile()
                }
        except (OSError, tarfile.TarError) as error:
            self.fail(
                f"{archive_name} is not readable as tar.xz: {error}: {path}"
            )
        return TestReport.RawData(
            archive_name,
            path,
            texts,
            self.manifest_build_tree(manifest_text, manifest_path),
        )

    # Faults a README page missing or unasked for, returning the help link.
    def readme_check(self, out_dir: str, has_readme_html: bool) -> str:
        for name, is_wanted in (
            (test_settings.TEST_README_MARKDOWN_NAME, True),
            (test_settings.TEST_README_HTML_NAME, has_readme_html),
        ):
            if os.path.isfile(os.path.join(out_dir, name)) != is_wanted:
                self.fail(
                    f"{name} is {'missing' if is_wanted else 'unasked for'}:"
                    f" {out_dir}"
                )
        return (
            test_settings.TEST_README_HTML_NAME
            if has_readme_html
            else test_settings.TEST_README_MARKDOWN_NAME
        )

    # Returns the recorded counters the database pages draw, faulting changes.
    def report_counter_names(
        self, out_dir: str, tests: Sequence[str]
    ) -> list[str]:
        first_names: list[str] = []
        for test_name in tests:
            label = self.database_page_path(test_name)
            path = os.path.join(out_dir, label)
            with open(path, encoding="utf-8") as handle:
                attributes = self.element_attributes(
                    handle.read(), test_settings.TEST_DATABASE_MODEL_ID
                )
            if attributes is None or "data-model-" not in attributes:
                self.fail(f"{label} holds no database model: {path}")
            database_model = json.loads(attributes["data-model-"])
            counter_names = database_model["counterNames"]
            if test_name == tests[0]:
                first_names = counter_names
            elif counter_names != first_names:
                self.fail(
                    f"{label} draws the counters {counter_names}, expected"
                    f" {tests[0]}'s {first_names}: {path}"
                )
        return first_names

    def run(self, args: TestReport.TestArgs) -> int:
        out_dir = os.path.abspath(args.out_dir)
        index_path = os.path.join(out_dir, "index.html")
        if not os.path.isfile(index_path):
            print(
                f"error: no index.html in {out_dir}"
                " -- not a report directory?",
                file=sys.stderr,
            )
            return 2
        name = self.page_title(index_path)
        if name is None:
            print(f"error: no <title> in {index_path}", file=sys.stderr)
            return 1
        if name != test_settings.TEST_OVERVIEW_PAGE_TITLE:
            print(
                f"error: <title> {name!r}, expected"
                f" {test_settings.TEST_OVERVIEW_PAGE_TITLE!r}: {index_path}",
                file=sys.stderr,
            )
            return 1
        layout = _LAYOUT_DIFF if args.diff else _LAYOUT_FULL
        regular_dirs = [
            os.path.abspath(path)
            for path in (args.baseline, args.modified)
            if path
        ]
        if len(regular_dirs) != (2 if layout.has_baselines else 0):
            print(
                f"error: --baseline {args.baseline!r} and --modified"
                f" {args.modified!r} name a diff's two reports, a diff"
                f" needing both and a regular report neither: {out_dir}",
                file=sys.stderr,
            )
            return 2
        regular_data = [
            self.raw_data_texts(regular_dir) for regular_dir in regular_dirs
        ]

        self.shared_images_check()
        self.function_line_check()
        self.delta_home_check()
        self.function_data_builder_check()
        self.function_diff_check()
        self.home_dir_check(out_dir)
        self.manifest_check(out_dir, layout)
        tests = self.overview_test_names(index_path, out_dir)
        help_name = self.readme_check(out_dir, args.readme_html)
        self.overview_check(out_dir, tests, layout, help_name)
        if layout.is_regular_report:
            self.flame_app_check(out_dir)
        self.heat_map_check(out_dir, tests, layout)
        self.source_database_check(out_dir)
        traced_tests = tests if layout.test_records_runs else []
        self.flame_graph_check(out_dir, traced_tests, layout)
        for test_name in tests:
            self.test_report_check(out_dir, test_name, layout, regular_data)

        if args.verbose:
            print(f"test_report: ok ({out_dir})")
        return 0

    # Returns the object a script assigns, a test's entry when a test is named.
    def script_value(
        self, script: str, global_name: str, test_name: str | None, path: str
    ) -> dict[str, object]:
        assignment_target = f"window.{global_name}"
        if test_name is not None:
            assignment_target += f'["{test_name}"]'
        assignment_prefix = f"{assignment_target} = "
        for line in script.splitlines():
            if not line.startswith(assignment_prefix):
                continue
            try:
                filed_value = json.loads(
                    line.removeprefix(assignment_prefix).rstrip(";")
                )
            except ValueError as error:
                self.fail(
                    f"{assignment_prefix!r} holds no JSON: {error}: {path}"
                )
            if not isinstance(filed_value, dict):
                self.fail(
                    f"{assignment_prefix!r} holds no JSON object: {path}"
                )
            return filed_value
        self.fail(f"no {assignment_prefix!r} line: {path}")

    # Checks two images of one file name are told apart by their paths.
    def shared_images_check(self) -> None:
        try:
            profile = callgrind.Callgrind().parse(
                test_settings.TEST_SHARED_IMAGES_RECORDING,
                test_settings.TEST_SHARED_IMAGES_RECORDING_NAME,
            )
        except SystemExit as error:
            self.fail(
                "the parser refuses"
                f" {test_settings.TEST_SHARED_IMAGES_RECORDING_NAME},"
                f" two images of one file name recording one name: {error}"
            )
        found_names = sorted(profile.function_home)
        if found_names != sorted(
            test_settings.TEST_SHARED_IMAGES_FUNCTION_NAMES
        ):
            self.fail(
                f"the parser names the functions of"
                f" {test_settings.TEST_SHARED_IMAGES_RECORDING_NAME}"
                f" {found_names},"
                " expected"
                f" {sorted(test_settings.TEST_SHARED_IMAGES_FUNCTION_NAMES)}"
            )

    def size_check(self, path: str, min_bytes: int, label: str) -> str:
        try:
            size = os.path.getsize(path)
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except OSError as error:
            self.fail(f"{label}: {path}: {error}")
        if size < min_bytes:
            self.fail(
                f"{label} suspiciously small ({size} bytes <"
                f" {min_bytes}): {path}"
            )
        return text

    # Faults a source script a model names that the report lacks.
    def model_sources_check(
        self, out_dir: str, filed_model: dict[str, object], label: str
    ) -> None:
        files = filed_model["files"]
        if not isinstance(files, dict):
            self.fail(f"{label} files no file table")
        for display, file_entry in files.items():
            script_name = file_entry["source"]
            if script_name is None:
                continue
            path = os.path.join(out_dir, _REPORT_SOURCES_DIR_NAME, script_name)
            if not os.path.isfile(path):
                self.fail(f"{label} names {display!r} source {path}, absent")

    # Checks the list of every file and function the report's tests name.
    def source_database_check(self, out_dir: str) -> None:
        label = test_settings.TEST_SOURCE_DATABASE_SCRIPT_PATH
        path = os.path.join(out_dir, label)
        script = self.size_check(
            path, test_settings.TEST_SOURCE_DATABASE_LEAST_BYTES, label
        )
        database = self.script_value(
            script, test_settings.TEST_SOURCE_DATABASE_GLOBAL_NAME, None, path
        )
        found_keys = sorted(database)
        if found_keys != sorted(test_settings.TEST_SOURCE_DATABASE_KEYS):
            self.fail(
                f"{label} holds the keys {found_keys}, expected"
                f" {sorted(test_settings.TEST_SOURCE_DATABASE_KEYS)}: {path}"
            )
        listed: dict[str, list[str]] = {}
        for key in test_settings.TEST_SOURCE_DATABASE_KEYS:
            names = database[key]
            if not isinstance(names, list) or not all(
                isinstance(name, str) for name in names
            ):
                self.fail(f"{label} {key} holds no list of strings: {path}")
            listed[key] = names
        for file_name in listed["files"]:
            if (
                file_name.split("/")[0]
                in test_settings.TEST_UNKNOWN_IMAGE_NAMES
            ):
                self.fail(
                    f"{label} lists {file_name!r}, a file in no known image:"
                    f" {path}"
                )
        if test_settings.TEST_BELOW_MAIN_FUNCTION_NAME in listed["functions"]:
            self.fail(
                f"{label} lists"
                f" {test_settings.TEST_BELOW_MAIN_FUNCTION_NAME!r}, valgrind's"
                f" name for every function below main: {path}"
            )

    # Returns every address a table data's cells link.
    def table_data_hrefs(self, rows: Sequence[Sequence[Any]]) -> list[str]:
        hrefs: list[str] = []
        for row in rows:
            for cell in row:
                if not isinstance(cell, dict):
                    continue
                if "href" in cell:
                    hrefs.append(str(cell["href"]))
        return hrefs

    # Returns the rows a table data element files, each a list of cells.
    def table_data_rows(
        self, attributes: dict[str, str], label: str, path: str
    ) -> list[list[Any]]:
        if "data-rows-" not in attributes:
            self.fail(f"{label}'s table data holds no data-rows-: {path}")
        try:
            rows = json.loads(attributes["data-rows-"])
        except ValueError as error:
            self.fail(f"{label}'s table data holds no JSON: {error}: {path}")
        if not isinstance(rows, list) or not all(
            isinstance(row, list) for row in rows
        ):
            self.fail(f"{label}'s table data holds no list of rows: {path}")
        return rows

    # Checks the archive's test list holds the overview's tests, sorted.
    def test_list_check(
        self,
        text: str | None,
        archive_name: str,
        tests: Sequence[str],
        path: str,
    ) -> None:
        if text is None:
            self.fail(
                f"{archive_name} holds no {test_settings.TEST_LIST_FILE_NAME}:"
                f" {path}"
            )
        if text.split("\n") != [*sorted(tests), ""]:
            self.fail(
                f"{archive_name}'s {test_settings.TEST_LIST_FILE_NAME} lists"
                f" {text.splitlines()}, expected the overview's tests"
                f" {sorted(tests)}, one per line, sorted: {path}"
            )

    def test_report_check(
        self,
        out_dir: str,
        name: str,
        layout: TestReport.ReportLayout,
        regular_data: Sequence[TestReport.RawData],
    ) -> None:
        self.database_page_check(out_dir, name, layout, regular_data)
        self.call_graph_page_check(out_dir, name, layout)
        stray_dir = os.path.join(out_dir, name)
        if os.path.exists(stray_dir):
            self.fail(
                f"{name}/ at the report top, which no report keeps:"
                f" {stray_dir}"
            )

    def timer_artifacts_archive_check(
        self,
        out_dir: str,
        path: str,
        archive_name: str,
        tests: Sequence[str],
        layout: TestReport.ReportLayout,
        build_tree: str,
    ) -> dict[str, dict[str, float]]:
        size = os.path.getsize(path)
        if size < test_settings.TEST_RAW_ARCHIVE_LEAST_BYTES:
            self.fail(
                f"{archive_name} suspiciously small ({size} bytes <"
                f" {test_settings.TEST_RAW_ARCHIVE_LEAST_BYTES}): {path}"
            )
        root_name = archive_name.removesuffix(_REPORT_RAW_ARCHIVE_SUFFIX)
        try:
            with tarfile.open(path, "r:xz") as archive:
                archive_members = archive.getmembers()
                texts = {
                    member.name: self.member_text(archive, member)
                    for member in archive_members
                    if member.isfile()
                }
        except (OSError, tarfile.TarError) as error:
            self.fail(
                f"{archive_name} is not readable as tar.xz: {path}: {error}"
            )
        if not any(
            member.isdir() and member.name == root_name
            for member in archive_members
        ):
            self.fail(f"{archive_name} has no {root_name}/ root entry: {path}")
        for member in archive_members:
            if member.name == root_name or (
                member.isfile() and os.path.dirname(member.name) == root_name
            ):
                continue
            self.fail(
                f"{archive_name} holds {member.name!r}, which is no file"
                f" right under {root_name}/: {path}"
            )
        texts_by_name = {
            os.path.basename(member_name): text
            for member_name, text in texts.items()
        }
        profile_names = {
            test_name: f"{test_name}{test_settings.TEST_PROFILE_FILE_SUFFIX}"
            for test_name in tests
            if layout.test_records_runs
        }
        for test_name, file_name in profile_names.items():
            profile_text = texts_by_name.get(file_name, "")
            if "events:" not in profile_text[:4096]:
                self.fail(
                    f"{archive_name} holds no {file_name} of {test_name}"
                    f" with an 'events:' line near its top: {path}"
                )
            self.profile_quiet_check(
                profile_text, archive_name, file_name, path
            )
            self.function_images_check(
                profile_text, out_dir, test_name, file_name
            )
        self.test_list_check(
            texts_by_name.get(test_settings.TEST_LIST_FILE_NAME),
            archive_name,
            tests,
            path,
        )
        file_entries = self.paths_document_check(
            texts_by_name.get(test_settings.TEST_PATHS_DOCUMENT_NAME),
            archive_name,
            test_settings.TEST_PATHS_DOCUMENT_NAME,
            path,
        )
        function_data_names = {
            test_name: f"{test_name}"
            f"{test_settings.TEST_FUNCTION_DATA_FILE_SUFFIX}"
            for test_name in profile_names
        }
        for test_name in function_data_names:
            self.function_data_check(
                TestReport.RawData(
                    archive_name, path, texts_by_name, build_tree
                ),
                file_entries,
                out_dir,
                test_name,
            )
        timing_document = self.timing_document_check(
            texts_by_name.get(test_settings.TEST_TIMING_DOCUMENT_NAME),
            archive_name,
            tests,
            path,
        )
        wanted_names = {
            test_settings.TEST_LIST_FILE_NAME,
            test_settings.TEST_PATHS_DOCUMENT_NAME,
            test_settings.TEST_TIMING_DOCUMENT_NAME,
            *profile_names.values(),
            *function_data_names.values(),
        }
        for file_name in texts_by_name:
            if file_name not in wanted_names:
                self.fail(
                    f"{archive_name} holds {file_name}, which no diff"
                    f" reads: {path}"
                )
        for member_name, text in texts.items():
            if callgrind.REPO_ROOT in text:
                self.fail(
                    f"{archive_name} still contains the absolute repo root "
                    f"{callgrind.REPO_ROOT!r} in {member_name}: {path}"
                )
        return timing_document

    # Returns the regular report's timing document, none for a diff report.
    def timer_artifacts_check(
        self,
        out_dir: str,
        overview_text: str,
        tests: Sequence[str],
        layout: TestReport.ReportLayout,
    ) -> dict[str, dict[str, float]] | None:
        has_raw_data_line = (
            test_settings.TEST_OVERVIEW_RAW_DATA_MARKUP in overview_text
        )
        if layout.has_timer_artifacts and not has_raw_data_line:
            self.fail(f"overview index.html has no 'raw data' line: {out_dir}")
        elif has_raw_data_line and not layout.has_timer_artifacts:
            self.fail(
                "overview index.html has a 'raw data' line, but it should"
                f" not: {out_dir}"
            )
        manifest_path = os.path.join(out_dir, "MANIFEST.txt")
        try:
            with open(manifest_path, encoding="utf-8") as handle:
                manifest_text = handle.read()
        except OSError as error:
            self.fail(
                f"MANIFEST.txt names no raw data archive: {error}:"
                f" {manifest_path}"
            )
        timing_document = None
        for label in layout.manifest_recorded_labels:
            archive_name = (
                f"{test_settings.TEST_TIMER_ARTIFACTS_PREFIX}"
                f"{self.manifest_recorded_value(manifest_text, label)}"
                f"{_REPORT_RAW_ARCHIVE_SUFFIX}"
            )
            path = os.path.join(out_dir, archive_name)
            if not layout.has_timer_artifacts:
                if os.path.lexists(path):
                    self.fail(
                        f"{archive_name}, the raw data archive MANIFEST.txt's"
                        f" {label}= row names, in a report that keeps none:"
                        f" {path}"
                    )
                continue
            if not os.path.isfile(path):
                self.fail(
                    f"no {archive_name}, the raw data archive MANIFEST.txt's"
                    f" {label}= row names, at the report's top: {path}"
                )
            if f'href="{archive_name}"' not in overview_text:
                self.fail(
                    f"overview index.html does not link {archive_name}:"
                    f" {out_dir}"
                )
            timing_document = self.timer_artifacts_archive_check(
                out_dir,
                path,
                archive_name,
                tests,
                layout,
                self.manifest_build_tree(manifest_text, manifest_path),
            )
        return timing_document

    # Returns the archive's timing document of each test's overview values.
    def timing_document_check(
        self,
        text: str | None,
        archive_name: str,
        tests: Sequence[str],
        path: str,
    ) -> dict[str, dict[str, float]]:
        if text is None:
            self.fail(
                f"{archive_name} holds no"
                f" {test_settings.TEST_TIMING_DOCUMENT_NAME}: {path}"
            )
        try:
            document = json.loads(text)
        except ValueError as error:
            self.fail(
                f"{test_settings.TEST_TIMING_DOCUMENT_NAME} holds no JSON:"
                f" {error}: {path}"
            )
        if not isinstance(document, dict) or list(document) != sorted(tests):
            self.fail(
                f"{test_settings.TEST_TIMING_DOCUMENT_NAME} keys"
                f" {list(document) if isinstance(document, dict) else []},"
                f" expected the overview's tests {sorted(tests)}: {path}"
            )
        for test_name, values in document.items():
            if not isinstance(values, dict) or list(values) != list(
                test_settings.TEST_TIMING_VALUE_NAMES
            ):
                self.fail(
                    f"{test_settings.TEST_TIMING_DOCUMENT_NAME} gives"
                    f" {test_name} the"
                    f" values {values!r}, expected the names"
                    f" {list(test_settings.TEST_TIMING_VALUE_NAMES)}: {path}"
                )
            for value_name, value in values.items():
                if (
                    type(value) not in (int, float)
                    or value < 0
                    or not math.isfinite(value)
                ):
                    self.fail(
                        f"{test_settings.TEST_TIMING_DOCUMENT_NAME} gives"
                        f" {test_name}"
                        f" {value_name} {value!r}, expected a finite number"
                        f" not below 0: {path}"
                    )
        return document


_FLAME_GRAPH_VIEW_KEY = _FLAME_GRAPH_VIEW_ENTRY[0]

_HEAT_MAP_VIEW_KEY = _HEAT_MAP_VIEW_ENTRY[0]

_LAYOUT_DIFF = TestReport.ReportLayout(
    is_regular_report=False,
    table_diff_value="1",
    database_model_keys=(
        "counterNames",
        "derivedCounters",
        "functionRows",
        "functions",
    ),
    database_function_fields=9,
    database_function_value_fields=(4, 8),
    database_call_fields=3,
    header_blocks=(
        '<div class="page-heading-">baseline</div>',
        '<div class="page-heading-">modified</div>',
    ),
    manifest_version=_REPORT_MANIFEST_VERSION_DIFF,
    manifest_labels=(
        "baseline",
        "modified",
        "baseline_recorded",
        "modified_recorded",
    ),
    manifest_recorded_labels=("baseline_recorded", "modified_recorded"),
    test_records_runs=False,
    has_timer_artifacts=False,
    has_baselines=True,
)

_LAYOUT_FULL = TestReport.ReportLayout(
    is_regular_report=True,
    table_diff_value="0",
    database_model_keys=(
        "counterNames",
        "counterTotals",
        "derivedCounters",
        "functionRows",
        "functions",
    ),
    database_function_fields=7,
    database_function_value_fields=(4,),
    database_call_fields=2,
    header_blocks=(
        '<div id="overview-manifest-heading-" class="page-heading-"></div>',
    ),
    manifest_version=_REPORT_MANIFEST_VERSION_FULL,
    manifest_labels=(
        "revision",
        "cpu",
        "memory",
        "os",
        "compiler",
        "build",
        "executable",
        "recorded",
    ),
    manifest_recorded_labels=("recorded",),
    test_records_runs=True,
    has_timer_artifacts=True,
    has_baselines=False,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", help="a report directory")
    parser.add_argument(
        "--diff",
        action="store_true",
        help="a perf2html_diff.sh report: heat map only",
    )
    parser.add_argument(
        "--baseline",
        default="",
        metavar="DIR",
        help="the diff's baseline report, whose function places the diff"
        " copies (--diff only)",
    )
    parser.add_argument(
        "--modified",
        default="",
        metavar="DIR",
        help="the diff's modified report, whose function places the diff"
        " copies first (--diff only)",
    )
    parser.add_argument(
        "--readme-html",
        action="store_true",
        help=f"the report holds {test_settings.TEST_README_HTML_NAME},"
        " which its help link opens",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print the ok line; a quiet run prints nothing on success",
    )
    namespace = parser.parse_args()
    checker = TestReport()
    return checker.run(
        TestReport.TestArgs(
            out_dir=namespace.out_dir,
            diff=namespace.diff,
            baseline=namespace.baseline,
            modified=namespace.modified,
            readme_html=namespace.readme_html,
            verbose=namespace.verbose,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
