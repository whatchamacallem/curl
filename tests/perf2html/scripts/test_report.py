#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, base64, html, json, math, os, re, subprocess, sys, tarfile
import urllib.parse
from collections.abc import Sequence
from typing import Any, NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind, settings

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
        readme_html: bool
        verbose: bool

    def __init__(self) -> None:
        self.errors: list[str] = []

    # Checks the rows, costs and window of a call graph.
    def call_graph_model_check(
        self,
        call_graph_model: dict[str, Any],
        label: str,
        path: str,
    ) -> None:
        function_names: list[str] = []
        for function_row in call_graph_model["functions"]:
            if len(function_row) != _TEST_CALL_GRAPH_FUNCTION_FIELDS:
                self.fail(
                    f"{label}'s call graph has a function of"
                    f" {len(function_row)} fields, expected"
                    f" {_TEST_CALL_GRAPH_FUNCTION_FIELDS}: {path}"
                )
                return
            function_name = function_row[_TEST_CALL_GRAPH_FUNCTION_NAME_FIELD]
            self_value = function_row[_TEST_CALL_GRAPH_FUNCTION_SELF_FIELD]
            if not isinstance(self_value, int) or self_value < 0:
                self.fail(
                    f"{label}'s call graph gives {function_name!r} the self"
                    f" cost {self_value!r}, expected an integer of 0 or more:"
                    f" {path}"
                )
                return
            function_names.append(function_name)
        function_count = len(function_names)
        caller_indexes: set[int] = set()
        called_indexes: set[int] = set()
        for edge_row in call_graph_model["edges"]:
            if len(edge_row) != _TEST_CALL_GRAPH_EDGE_FIELDS:
                self.fail(
                    f"{label}'s call graph has an edge of {len(edge_row)}"
                    f" fields, expected {_TEST_CALL_GRAPH_EDGE_FIELDS}:"
                    f" {path}"
                )
                return
            if not all(
                0 <= edge_row[field] < function_count
                for field in _TEST_CALL_GRAPH_EDGE_FUNCTION_FIELDS
            ):
                self.fail(
                    f"{label}'s call graph edge {edge_row} names a function"
                    f" past its {function_count} functions: {path}"
                )
                return
            inclusive_value = edge_row[_TEST_CALL_GRAPH_EDGE_INCLUSIVE_FIELD]
            if not isinstance(inclusive_value, int) or inclusive_value < 0:
                self.fail(
                    f"{label}'s call graph edge {edge_row} gives the inclusive"
                    f" cost {inclusive_value!r}, expected an integer of 0 or"
                    f" more: {path}"
                )
                return
            caller_indexes.add(edge_row[_TEST_CALL_GRAPH_EDGE_CALLER_FIELD])
            called_indexes.add(edge_row[_TEST_CALL_GRAPH_EDGE_CALLEE_FIELD])
        for root_row in call_graph_model["roots"]:
            if len(root_row) != _TEST_CALL_GRAPH_ROOT_FIELDS:
                self.fail(
                    f"{label}'s call graph has a root of {len(root_row)}"
                    f" fields, expected {_TEST_CALL_GRAPH_ROOT_FIELDS}:"
                    f" {path}"
                )
                return
        root_indexes = [
            root_row[_TEST_CALL_GRAPH_ROOT_FUNCTION_FIELD]
            for root_row in call_graph_model["roots"]
        ]
        uncalled_indexes = sorted(caller_indexes - called_indexes)
        if root_indexes != uncalled_indexes:
            self.fail(
                f"{label}'s call graph roots {root_indexes} are"
                f" not its uncalled callers {uncalled_indexes}: {path}"
            )
            return
        for root_row in call_graph_model["roots"]:
            root_name = function_names[
                root_row[_TEST_CALL_GRAPH_ROOT_FUNCTION_FIELD]
            ]
            # A root is uncalled, so only the start function counts calls.
            root_calls = (
                _TEST_CALL_GRAPH_START_FUNCTION_CALLS
                if root_name == _TEST_CALL_GRAPH_START_FUNCTION_NAME
                else 0
            )
            counted_calls = root_row[_TEST_CALL_GRAPH_ROOT_CALLS_FIELD]
            if counted_calls != root_calls:
                self.fail(
                    f"{label}'s call graph root {root_name} counts the calls"
                    f" {counted_calls}, expected {root_calls}: {path}"
                )
        if _TEST_CALL_GRAPH_START_FUNCTION_NAME not in function_names:
            self.fail(
                f"{label}'s call graph names no"
                f" {_TEST_CALL_GRAPH_START_FUNCTION_NAME}, the function the"
                f" recording starts at: {path}"
            )
        if _TEST_CALL_GRAPH_STOP_FUNCTION_NAME in function_names:
            self.fail(
                f"{label}'s call graph names"
                f" {_TEST_CALL_GRAPH_STOP_FUNCTION_NAME}, the function the"
                f" recording stops at: {path}"
            )

    # Checks a test's call graph page and its model, or that a diff has none.
    def call_graph_page_check(
        self,
        out_dir: str,
        test_name: str,
        layout: TestReport.ReportLayout,
    ) -> None:
        label = f"{_TEST_CALL_GRAPH_PAGE_DIR_NAME}/{test_name}.html"
        path = os.path.join(out_dir, label)
        if not layout.is_regular_report:
            if os.path.lexists(path):
                self.fail(
                    f"{label} in a diff report, which has no call graph:"
                    f" {path}"
                )
            return
        text = self.page_check(
            path, label, _TEST_CALL_GRAPH_PAGE_LEAST_BYTES, test_name
        )
        if not text:
            return
        with open(path, encoding="utf-8") as handle:
            page_text = handle.read()
        attributes = self.element_attributes(
            page_text, _TEST_CALL_GRAPH_TABLE_ID
        )
        if attributes is None:
            self.fail(f"{label} has no {_TEST_CALL_GRAPH_TABLE_ID}: {path}")
            return
        try:
            call_graph_model = json.loads(attributes.get("data-model-", ""))
        except ValueError as error:
            self.fail(f"{label} holds no JSON call graph: {error}: {path}")
            return
        found_keys = (
            sorted(call_graph_model)
            if isinstance(call_graph_model, dict)
            else []
        )
        if found_keys != sorted(_TEST_CALL_GRAPH_MODEL_KEYS):
            self.fail(
                f"{label}'s call graph holds the keys {found_keys},"
                f" expected {sorted(_TEST_CALL_GRAPH_MODEL_KEYS)}: {path}"
            )
            return
        self.call_graph_model_check(call_graph_model, label, path)

    def checksum_compute(self, out_dir: str) -> str:
        try:
            done = subprocess.run(
                ["sh", "-c", _REPORT_CHECKSUM_COMMAND],
                cwd=out_dir,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            self.fail(f"cannot checksum {out_dir}: {error}")
            return ""
        if done.returncode != 0:
            self.fail(
                f"cannot checksum {out_dir}: cksum exited"
                f" {done.returncode}: {done.stderr.strip()}"
            )
            return ""
        return done.stdout.split(" ", 1)[0]

    # Checks the derived counter names and each term's recorded counter.
    def database_derived_check(
        self, database_model: dict[str, Any], label: str, path: str
    ) -> bool:
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
                    return False
        if derived_names != list(_TEST_DERIVED_COUNTER_NAMES):
            self.fail(
                f"{label}'s database model derives {derived_names}, expected"
                f" {list(_TEST_DERIVED_COUNTER_NAMES)}: {path}"
            )
            return False
        return True

    # Checks each call between listed functions shows in both of their rows.
    def database_edges_check(
        self, function_rows: list[list[Any]], label: str, path: str
    ) -> bool:
        caller_edges, callee_edges = (
            self.database_side_edges(function_rows, rows_field)
            for rows_field in (
                _TEST_DATABASE_CALLER_ROWS_FIELD,
                _TEST_DATABASE_CALLEE_ROWS_FIELD,
            )
        )
        one_sided_edges = sorted(caller_edges ^ callee_edges)
        if not one_sided_edges:
            return True
        self.fail(
            f"{label}'s database model lists {len(one_sided_edges)} calls"
            " between listed functions in the callers or the callees alone,"
            f" first {one_sided_edges[0]}: {path}"
        )
        return False

    # Checks every database link opens the test's heat map at what it names.
    def database_links_check(
        self,
        out_dir: str,
        test_name: str,
        database_model: dict[str, Any],
        label: str,
        path: str,
    ) -> None:
        model_label = f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js"
        model_path = os.path.join(
            out_dir,
            _HEAT_MAP_VIEW_KEY,
            _HEAT_MAP_MODEL_DIR_NAME,
            f"{test_name}.js",
        )
        script = self.size_check(
            model_path, _TEST_HEAT_MAP_MODEL_LEAST_BYTES, model_label
        )
        if not script:
            return
        heat_map_model: Any = self.script_value(
            script, _HEAT_MAP_MODEL_GLOBAL_NAME, test_name, model_path
        )
        if heat_map_model is None:
            return
        function_start = (
            f"#test={test_name}&view={_HEAT_MAP_VIEW_KEY}&function="
        )
        function_links = [
            function_link
            for function_link in database_model["functions"]
            if function_link[_TEST_DATABASE_FUNCTION_HREF_FIELD]
        ]
        if not function_links:
            self.fail(
                f"{label} links no function into the heat map"
                f" ({function_start}...): {path}"
            )
        for function_link in function_links:
            name = function_link[_TEST_DATABASE_FUNCTION_NAME_FIELD]
            href = function_link[_TEST_DATABASE_FUNCTION_HREF_FIELD]
            linked_name = urllib.parse.unquote(
                href.removeprefix(function_start)
            )
            if not href.startswith(function_start) or linked_name != name:
                self.fail(
                    f"{label} links {name} as {href!r}, expected"
                    f" {function_start} followed by the name: {path}"
                )
                return
        function_names = [
            function_link[_TEST_DATABASE_FUNCTION_NAME_FIELD]
            for function_link in database_model["functions"]
        ]
        listed_names = {
            function_names[function_row[_TEST_DATABASE_ROW_FUNCTION_FIELD]]
            for function_row in database_model["functionRows"]
        }
        linked_names = {
            function_link[_TEST_DATABASE_FUNCTION_NAME_FIELD]
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
            if function_entry["name"] == _TEST_CALL_GRAPH_START_FUNCTION_NAME
            or any(
                caller_row[_TEST_HEAT_MAP_CALLER_COUNT_FIELD] > 0
                for caller_row in function_entry["callers"]
            )
        }
        listed_files = {
            function_row[_TEST_DATABASE_ROW_FILE_FIELD]
            for function_row in database_model["functionRows"]
            if function_row[_TEST_DATABASE_ROW_FILE_FIELD]
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
    ) -> dict[str, Any] | None:
        attributes = self.element_attributes(
            page_text, _TEST_DATABASE_MODEL_ID
        )
        if attributes is None:
            self.fail(
                f"{label} has no {_TEST_DATABASE_MODEL_ID} model element:"
                f" {path}"
            )
            return None
        if attributes.get("data-diff-") != layout.table_diff_value:
            self.fail(
                f"{label}'s model element holds data-diff-"
                f" {attributes.get('data-diff-')!r}, expected"
                f" {layout.table_diff_value!r}: {path}"
            )
        if "data-model-" not in attributes:
            self.fail(f"{label}'s model element holds no data-model-: {path}")
            return None
        try:
            database_model = json.loads(attributes["data-model-"])
        except ValueError as error:
            self.fail(
                f"{label}'s model element holds no JSON model: {error}: {path}"
            )
            return None
        found_keys = (
            sorted(database_model) if isinstance(database_model, dict) else []
        )
        if found_keys != sorted(layout.database_model_keys):
            self.fail(
                f"{label}'s database model holds the keys {found_keys},"
                f" expected {sorted(layout.database_model_keys)}: {path}"
            )
            return None
        if not self.database_rows_check(database_model, layout, label, path):
            return None
        return database_model

    def database_page_check(
        self,
        out_dir: str,
        test_name: str,
        layout: TestReport.ReportLayout,
    ) -> None:
        label = self.database_page_path(test_name)
        path = os.path.join(out_dir, label)
        text = self.page_check(
            path, label, _TEST_OVERVIEW_PAGE_LEAST_BYTES, test_name
        )
        if not text:
            return
        with open(path, encoding="utf-8") as handle:
            page_text = handle.read()
        if '<nav id="menu-"' in page_text:
            self.fail(f"{label} draws the overview's menu: {path}")
        if _TEST_OVERVIEW_RAW_DATA_MARKUP in page_text:
            self.fail(
                f"{label} has a 'raw data' section, but it should not: {path}"
            )
        database_model = self.database_model_check(
            path, label, page_text, layout
        )
        if database_model is not None:
            self.database_links_check(
                out_dir, test_name, database_model, label, path
            )

    # Returns the report relative path of a test's database page.
    def database_page_path(self, test_name: str) -> str:
        return f"{_TEST_DATABASE_PAGE_DIR_NAME}/{test_name}.html"

    # Checks a function row holds its fields, its place, a call and counters.
    def database_row_check(
        self,
        function_row: list[Any],
        layout: TestReport.ReportLayout,
        counter_count: int,
        label: str,
        path: str,
    ) -> bool:
        row_label = (
            f"{label}'s function row"
            f" {function_row[_TEST_DATABASE_ROW_FUNCTION_FIELD]!r}"
        )
        if len(function_row) != layout.database_function_fields:
            self.fail(
                f"{row_label} holds {len(function_row)} fields, expected"
                f" {layout.database_function_fields}: {path}"
            )
            return False
        for field_index in layout.database_function_value_fields:
            if len(function_row[field_index]) != counter_count:
                self.fail(
                    f"{row_label} gives {len(function_row[field_index])}"
                    f" counter values, expected {counter_count}: {path}"
                )
                return False
        file_path = function_row[_TEST_DATABASE_ROW_FILE_FIELD]
        line_number = function_row[_TEST_DATABASE_ROW_LINE_FIELD]
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
            return False
        calls = function_row[_TEST_DATABASE_ROW_CALLS_FIELD]
        side_calls = [calls]
        if layout.has_baselines:
            baseline_calls = function_row[
                _TEST_DATABASE_ROW_BASELINE_CALLS_FIELD
            ]
            side_calls = [baseline_calls, baseline_calls + calls]
        if max(side_calls) <= 0:
            self.fail(
                f"{row_label} lists an uncalled function, its calls on each"
                f" side {side_calls}: {path}"
            )
            return False
        return True

    # Checks the derived counters, then each function row and the row order.
    def database_rows_check(
        self,
        database_model: dict[str, Any],
        layout: TestReport.ReportLayout,
        label: str,
        path: str,
    ) -> bool:
        counter_count = len(database_model["counterNames"])
        if "counterTotals" in layout.database_model_keys:
            totals_count = len(database_model["counterTotals"])
            if totals_count != counter_count:
                self.fail(
                    f"{label}'s database model totals {totals_count}"
                    f" counters, expected {counter_count}: {path}"
                )
                return False
        if not self.database_derived_check(database_model, label, path):
            return False
        function_count = len(database_model["functions"])
        function_rows = database_model["functionRows"]
        named_indexes: set[int] = set()
        for function_row in function_rows:
            if not self.database_row_check(
                function_row, layout, counter_count, label, path
            ):
                return False
            call_rows = [
                *function_row[_TEST_DATABASE_CALLER_ROWS_FIELD],
                *function_row[_TEST_DATABASE_CALLEE_ROWS_FIELD],
            ]
            for call_row in call_rows:
                if len(call_row) != layout.database_call_fields:
                    self.fail(
                        f"{label}'s database model has a caller or callee"
                        f" row of {len(call_row)} fields, expected"
                        f" {layout.database_call_fields}: {path}"
                    )
                    return False
            for indexed_row in (function_row, *call_rows):
                function_index = indexed_row[_TEST_DATABASE_ROW_FUNCTION_FIELD]
                if not 0 <= function_index < function_count:
                    self.fail(
                        f"{label}'s database model names the function"
                        f" {function_index} past its {function_count}"
                        f" functions: {path}"
                    )
                    return False
                named_indexes.add(function_index)
        if len(named_indexes) != function_count:
            self.fail(
                f"{label}'s database model links"
                f" {function_count - len(named_indexes)} functions that no"
                f" row, caller or callee names: {path}"
            )
            return False
        function_names = [
            function_link[_TEST_DATABASE_FUNCTION_NAME_FIELD]
            for function_link in database_model["functions"]
        ]
        row_places = [
            (
                function_row[_TEST_DATABASE_ROW_FILE_FIELD],
                function_row[_TEST_DATABASE_ROW_LINE_FIELD],
                function_names[
                    function_row[_TEST_DATABASE_ROW_FUNCTION_FIELD]
                ],
            )
            for function_row in function_rows
        ]
        if row_places != sorted(row_places):
            self.fail(
                f"{label}'s database model lists its function rows out of"
                f" file, line and name order: {path}"
            )
            return False
        return self.database_edges_check(function_rows, label, path)

    # Returns the calls one side of each function row lists, among the rows.
    def database_side_edges(
        self, function_rows: list[list[Any]], rows_field: int
    ) -> set[tuple[Any, ...]]:
        listed_indexes = {
            function_row[_TEST_DATABASE_ROW_FUNCTION_FIELD]
            for function_row in function_rows
        }
        side_edges: set[tuple[Any, ...]] = set()
        for function_row in function_rows:
            row_index = function_row[_TEST_DATABASE_ROW_FUNCTION_FIELD]
            for call_row in function_row[rows_field]:
                partner_index = call_row[_TEST_DATABASE_ROW_FUNCTION_FIELD]
                if partner_index not in listed_indexes:
                    continue
                call_counts = call_row[_TEST_DATABASE_CALL_COUNTS_START_FIELD:]
                side_edges.add(
                    (partner_index, row_index, *call_counts)
                    if rows_field == _TEST_DATABASE_CALLER_ROWS_FIELD
                    else (row_index, partner_index, *call_counts)
                )
        return side_edges

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
                    return

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

    def fail(self, message: str) -> None:
        self.errors.append(message)

    # Checks the speedscope bundle holds the files its page links, no other.
    def flame_app_check(self, out_dir: str) -> None:
        app_dir = os.path.join(out_dir, _FLAME_GRAPH_APP_DIR_NAME)
        if not os.path.isdir(app_dir):
            self.fail(f"no shared speedscope bundle: {app_dir}")
            return
        page_label = f"{_FLAME_GRAPH_VIEW_KEY}/index.html"
        page_path = os.path.join(out_dir, page_label)
        page_text = self.size_check(
            page_path, _TEST_FLAME_GRAPH_PAGE_LEAST_BYTES, page_label
        )
        if not page_text:
            return
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
            return
        stylesheet_label = f"{_FLAME_GRAPH_APP_DIR_NAME}/{stylesheet_names[0]}"
        stylesheet_path = os.path.join(out_dir, stylesheet_label)
        try:
            with open(stylesheet_path, encoding="utf-8") as handle:
                stylesheet = handle.read()
        except OSError as error:
            self.fail(f"{stylesheet_label}: {stylesheet_path}: {error}")
            return
        font_names = re.findall(r'url\("\./([^"/]+\.woff2)"\)', stylesheet)
        if len(font_names) != 1:
            self.fail(
                f"{stylesheet_label} loads the fonts {font_names}, expected"
                f" one: {stylesheet_path}"
            )
            return
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
            return
        page = self.page_check(
            os.path.join(flame_dir, "index.html"),
            f"{_FLAME_GRAPH_VIEW_KEY}/index.html",
            _TEST_FLAME_GRAPH_PAGE_LEAST_BYTES,
        )
        if page and f"{_FLAME_GRAPH_APP_DIR_NAME}/" not in page:
            self.fail(
                f"{_FLAME_GRAPH_VIEW_KEY}/index.html does not load the shared "
                f"{_FLAME_GRAPH_APP_DIR_NAME}/ bundle: {flame_dir}/index.html"
            )
        if page and "loadFileFromBase64" not in page:
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
            return
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
            path, _TEST_FLAME_GRAPH_SCRIPT_LEAST_BYTES, label
        )
        if not script:
            return
        filed_profile = self.script_value(
            script, _FLAME_GRAPH_PROFILE_GLOBAL_NAME, test_name, path
        )
        if filed_profile is None:
            return
        encoded_profile = filed_profile.get("base64")
        base64_text = (
            encoded_profile if isinstance(encoded_profile, str) else ""
        )
        if not re.fullmatch(r"[A-Za-z0-9+/=]+", base64_text):
            self.fail(f"{label} files no base64 profile: {path}")
            return
        try:
            document = json.loads(base64.b64decode(base64_text))
        except ValueError as error:
            self.fail(f"{label} base64 is not JSON: {error}: {path}")
            return
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
            _TEST_HEAT_MAP_PAGE_LEAST_BYTES,
            _HEAT_MAP_PAGE_TITLE,
        )
        if text and "report_ui_.layout_activate" not in text:
            self.fail(
                f"{_HEAT_MAP_VIEW_KEY}/index.html is missing its runtime"
                f" script (no report_ui_.layout_activate): {path}"
            )
        model_dir = os.path.join(heat_map_dir, _HEAT_MAP_MODEL_DIR_NAME)
        if not os.path.isdir(model_dir):
            self.fail(f"no heat map model scripts: {model_dir}")
            return
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
                _TEST_HEAT_MAP_MODEL_LEAST_BYTES,
                f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js",
            )
            if not script:
                continue
            filed_model = self.script_value(
                script, _HEAT_MAP_MODEL_GLOBAL_NAME, test_name, script_path
            )
            if filed_model is None:
                continue
            if (
                not {"heatMapTotals", "files", "functions"}
                <= filed_model.keys()
            ):
                self.fail(
                    f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js files a"
                    f" model lacking heatMapTotals, files or functions:"
                    f" {script_path}"
                )
                continue
            self.model_sources_check(
                out_dir,
                filed_model,
                f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js",
            )
            if layout.has_baselines:
                self.diff_baseline_check(
                    filed_model, f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js"
                )

    def home_dir_check(self, out_dir: str) -> None:
        home = os.path.expanduser("~")
        if home == "~":
            self.fail("no home directory to check the report against")
            return
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
            path, _TEST_MANIFEST_LEAST_BYTES, "MANIFEST.txt"
        )
        if not text:
            self.fail(
                "MANIFEST.txt is missing or unreadable, so this is not a"
                f" finished report; expected its first line to be"
                f" {layout.manifest_version!r}: {path}"
            )
            return
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
            return
        found = self.checksum_compute(out_dir)
        if found and found != recorded:
            self.fail(
                "this report does not match its recorded"
                f" {_REPORT_MANIFEST_CHECKSUM_LABEL}: found {found!r},"
                f" expected {recorded!r} -- a file was added, removed or"
                " edited"
                f" after the report was written: {out_dir}"
            )

    def manifest_recorded_value(self, text: str, label: str) -> str:
        return self.manifest_value(text, label).split(" ", 1)[0]

    def manifest_value(self, text: str, label: str) -> str:
        match = re.search(rf"^{re.escape(label)}=(.*)$", text, re.M)
        return match.group(1).strip() if match else ""

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
            return
        found = {
            name: html.unescape(value)
            for name, value in re.findall(
                r'\s(data-[\w-]+)="([^"]*)"', match.group(1)
            )
        }
        wanted = {
            "data-counter-names-": json.dumps(
                [*recorded_counter_names, *_TEST_DERIVED_COUNTER_NAMES]
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
        text = self.page_check(
            path,
            "index.html",
            _TEST_OVERVIEW_PAGE_LEAST_BYTES,
            _TEST_OVERVIEW_PAGE_TITLE,
        )
        if not text:
            return
        with open(path, encoding="utf-8") as handle:
            page_text = handle.read()
        if _TEST_OVERVIEW_TESTS_HEADING_MARKUP not in page_text:
            self.fail(f"overview index.html has no 'tests' section: {path}")
        tests_attributes = self.element_attributes(
            page_text, _TEST_OVERVIEW_TESTS_TABLE_DATA_ID
        )
        if tests_attributes is not None and "data-diff-" in tests_attributes:
            self.fail(
                "overview index.html's tests table data holds data-diff-,"
                f" which both reports' one column list leaves out: {path}"
            )
        self.overview_sections_check(page_text, layout, path)
        page_hrefs = self.overview_tests_hrefs(page_text, path)
        for test_name in tests:
            if (
                f"#test={test_name}&view={_TEST_DATABASE_VIEW_KEY}"
                not in page_hrefs
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
        if tests_attributes is not None:
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
        for table_row in self.table_data_rows(
            attributes, "overview index.html", path
        ):
            if len(table_row) != _TEST_OVERVIEW_ROW_FIELD_COUNT:
                self.fail(
                    f"overview index.html's tests row {table_row} has"
                    f" {len(table_row)} cells, expected"
                    f" {_TEST_OVERVIEW_ROW_FIELD_COUNT}: {path}"
                )
                continue
            field_patterns = (
                [
                    (
                        _TEST_OVERVIEW_TIME_PER_LOOP_FIELD,
                        _TEST_OVERVIEW_TIME_PER_LOOP_PATTERN,
                    ),
                    *(
                        (ratio_field, _TEST_OVERVIEW_RATIO_PATTERN)
                        for ratio_field in _TEST_OVERVIEW_RATIO_FIELDS
                    ),
                ]
                if layout.is_regular_report
                else [
                    (change_field, _TEST_OVERVIEW_CHANGE_PATTERN)
                    for change_field in _TEST_OVERVIEW_VALUE_FIELDS
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
                        else _TEST_OVERVIEW_CHANGE_CELL_TEXT
                    )
                    self.fail(
                        f"overview index.html's tests row {table_row} holds"
                        f" {table_row[value_field]!r} in cell {value_field},"
                        f" expected {value_pattern}{cell_text}: {path}"
                    )
                    break
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
            > _TEST_OVERVIEW_CHANGE_LARGEST_ERROR
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
                f" of {_TEST_TIMING_DOCUMENT_NAME}: {path}"
            )
            return
        for value_field, value_name in zip(
            _TEST_OVERVIEW_VALUE_FIELDS, _TEST_TIMING_VALUE_NAMES, strict=True
        ):
            value = timing_document[test_name][value_name]
            value_text = table_row[value_field]
            unit_seconds = 1.0
            largest_error = _TEST_OVERVIEW_RATIO_LARGEST_ERROR
            is_time = value_field == _TEST_OVERVIEW_TIME_PER_LOOP_FIELD
            if is_time and value_text:
                unit_text = value_text.lstrip("0123456789.")
                unit_seconds = _TEST_OVERVIEW_TIME_UNIT_SECONDS[unit_text]
                value_text = value_text.removesuffix(unit_text)
                largest_error = _TEST_OVERVIEW_TIME_LARGEST_ERROR
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
                    f" {value_name} {value} of {_TEST_TIMING_DOCUMENT_NAME}"
                    f" as {table_row[value_field]!r}: {path}"
                )

    # Checks the overview shows its tests, then its manifest, then raw data.
    def overview_sections_check(
        self, page_text: str, layout: TestReport.ReportLayout, path: str
    ) -> None:
        section_markups = (
            _TEST_OVERVIEW_TESTS_HEADING_MARKUP,
            *layout.header_blocks,
            *(
                (_TEST_OVERVIEW_RAW_DATA_MARKUP,)
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
                rf"#test=([\w.-]+)&view={re.escape(_TEST_DATABASE_VIEW_KEY)}",
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
                continue
            names.append(test_name)
        return names

    # Returns every address the overview's tests table data links.
    def overview_tests_hrefs(self, page_text: str, path: str) -> list[str]:
        attributes = self.element_attributes(
            page_text, _TEST_OVERVIEW_TESTS_TABLE_DATA_ID
        )
        if attributes is None:
            self.fail(
                "overview index.html has no"
                f" {_TEST_OVERVIEW_TESTS_TABLE_DATA_ID} table data: {path}"
            )
            return []
        return self.table_data_hrefs(
            self.table_data_rows(attributes, "overview index.html", path)
        )

    def page_check(
        self,
        path: str,
        label: str,
        min_bytes: int,
        want_title: str | None = None,
    ) -> str:
        text = self.size_check(path, min_bytes, label)
        if not text:
            return text
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
        preamble_count = len(_TEST_PAGE_PREAMBLE_SCRIPT_NAMES)
        if tuple(head_scripts[:preamble_count]) != (
            _TEST_PAGE_PREAMBLE_SCRIPT_NAMES
        ):
            self.fail(
                f"{label} head opens with the scripts {head_scripts}, expected"
                f" {list(_TEST_PAGE_PREAMBLE_SCRIPT_NAMES)}: {path}"
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

    # Checks the paths document a diff derives from the archive.
    def paths_document_check(
        self, text: str | None, archive_name: str, paths_name: str, path: str
    ) -> None:
        if text is None:
            self.fail(f"{archive_name} holds no {paths_name}: {path}")
            return
        try:
            document = json.loads(text)
        except ValueError as error:
            self.fail(f"{paths_name} holds no JSON: {error}: {path}")
            return
        if not isinstance(document, dict):
            self.fail(f"{paths_name} holds no path to code map: {path}")
            return
        for file_path, code in sorted(document.items()):
            if code not in _TEST_PATHS_DOCUMENT_CODES:
                self.fail(
                    f"{paths_name} codes {file_path} as {code!r}, not one of"
                    f" {' '.join(_TEST_PATHS_DOCUMENT_CODES)}: {path}"
                )
                return
            if file_path != os.path.normpath(file_path).lstrip("/"):
                self.fail(
                    f"{paths_name} keys {file_path}, which is no canonical"
                    f" path: {path}"
                )
                return

    # Faults a README page missing or unasked for, returning the help link.
    def readme_check(self, out_dir: str, has_readme_html: bool) -> str:
        for name, is_wanted in (
            (_TEST_README_MARKDOWN_NAME, True),
            (_TEST_README_HTML_NAME, has_readme_html),
        ):
            if os.path.isfile(os.path.join(out_dir, name)) != is_wanted:
                self.fail(
                    f"{name} is {'missing' if is_wanted else 'unasked for'}:"
                    f" {out_dir}"
                )
        return (
            _TEST_README_HTML_NAME
            if has_readme_html
            else _TEST_README_MARKDOWN_NAME
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
                    handle.read(), _TEST_DATABASE_MODEL_ID
                )
            if attributes is None or "data-model-" not in attributes:
                self.fail(f"{label} holds no database model: {path}")
                break
            database_model = json.loads(attributes["data-model-"])
            counter_names = database_model["counterNames"]
            if test_name == tests[0]:
                first_names = counter_names
            elif counter_names != first_names:
                self.fail(
                    f"{label} draws the counters {counter_names}, expected"
                    f" {tests[0]}'s {first_names}: {path}"
                )
                break
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
        if name != _TEST_OVERVIEW_PAGE_TITLE:
            print(
                f"error: <title> {name!r}, expected"
                f" {_TEST_OVERVIEW_PAGE_TITLE!r}: {index_path}",
                file=sys.stderr,
            )
            return 1
        layout = _LAYOUT_DIFF if args.diff else _LAYOUT_FULL

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
            self.test_report_check(out_dir, test_name, layout)

        if self.errors:
            print(
                f"test_report: {len(self.errors)} problem(s) in {out_dir}:",
                file=sys.stderr,
            )
            for error in self.errors:
                print(f"  - {error}", file=sys.stderr)
            return 1
        if args.verbose:
            print(f"test_report: ok ({out_dir})")
        return 0

    # Returns the object a script assigns, a test's entry when a test is named.
    def script_value(
        self, script: str, global_name: str, test_name: str | None, path: str
    ) -> dict[str, object] | None:
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
                return None
            if not isinstance(filed_value, dict):
                self.fail(
                    f"{assignment_prefix!r} holds no JSON object: {path}"
                )
                return None
            return filed_value
        self.fail(f"no {assignment_prefix!r} line: {path}")
        return None

    def size_check(self, path: str, min_bytes: int, label: str) -> str:
        try:
            size = os.path.getsize(path)
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
        except OSError as error:
            self.fail(f"{label}: {path}: {error}")
            return ""
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
            return
        for display, file_entry in files.items():
            script_name = file_entry["source"]
            if script_name is None:
                continue
            path = os.path.join(out_dir, _REPORT_SOURCES_DIR_NAME, script_name)
            if not os.path.isfile(path):
                self.fail(f"{label} names {display!r} source {path}, absent")

    # Checks the list of every file and function the report's tests name.
    def source_database_check(self, out_dir: str) -> None:
        label = _TEST_SOURCE_DATABASE_SCRIPT_PATH
        path = os.path.join(out_dir, label)
        script = self.size_check(
            path, _TEST_SOURCE_DATABASE_LEAST_BYTES, label
        )
        if not script:
            return
        database = self.script_value(
            script, _TEST_SOURCE_DATABASE_GLOBAL_NAME, None, path
        )
        if database is None:
            return
        found_keys = sorted(database)
        if found_keys != sorted(_TEST_SOURCE_DATABASE_KEYS):
            self.fail(
                f"{label} holds the keys {found_keys}, expected"
                f" {sorted(_TEST_SOURCE_DATABASE_KEYS)}: {path}"
            )
            return
        for key in _TEST_SOURCE_DATABASE_KEYS:
            names = database[key]
            if not isinstance(names, list) or not all(
                isinstance(name, str) for name in names
            ):
                self.fail(f"{label} {key} holds no list of strings: {path}")
                return

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
            return []
        try:
            rows = json.loads(attributes["data-rows-"])
        except ValueError as error:
            self.fail(f"{label}'s table data holds no JSON: {error}: {path}")
            return []
        if not isinstance(rows, list) or not all(
            isinstance(row, list) for row in rows
        ):
            self.fail(f"{label}'s table data holds no list of rows: {path}")
            return []
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
                f"{archive_name} holds no {_TEST_LIST_FILE_NAME}: {path}"
            )
            return
        if text.split("\n") != [*sorted(tests), ""]:
            self.fail(
                f"{archive_name}'s {_TEST_LIST_FILE_NAME} lists"
                f" {text.splitlines()}, expected the overview's tests"
                f" {sorted(tests)}, one per line, sorted: {path}"
            )

    def test_report_check(
        self, out_dir: str, name: str, layout: TestReport.ReportLayout
    ) -> None:
        self.database_page_check(out_dir, name, layout)
        self.call_graph_page_check(out_dir, name, layout)
        stray_dir = os.path.join(out_dir, name)
        if os.path.exists(stray_dir):
            self.fail(
                f"{name}/ at the report top, which no report keeps:"
                f" {stray_dir}"
            )

    def timer_artifacts_archive_check(
        self,
        path: str,
        archive_name: str,
        tests: Sequence[str],
        layout: TestReport.ReportLayout,
    ) -> dict[str, dict[str, float]] | None:
        size = os.path.getsize(path)
        if size < _TEST_RAW_ARCHIVE_LEAST_BYTES:
            self.fail(
                f"{archive_name} suspiciously small ({size} bytes <"
                f" {_TEST_RAW_ARCHIVE_LEAST_BYTES}): {path}"
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
            return None
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
            test_name: f"{test_name}{_TEST_PROFILE_FILE_SUFFIX}"
            for test_name in tests
            if layout.test_records_runs
        }
        for test_name, file_name in profile_names.items():
            if "events:" not in texts_by_name.get(file_name, "")[:4096]:
                self.fail(
                    f"{archive_name} holds no {file_name} of {test_name}"
                    f" with an 'events:' line near its top: {path}"
                )
        self.test_list_check(
            texts_by_name.get(_TEST_LIST_FILE_NAME), archive_name, tests, path
        )
        self.paths_document_check(
            texts_by_name.get(_TEST_PATHS_DOCUMENT_NAME),
            archive_name,
            _TEST_PATHS_DOCUMENT_NAME,
            path,
        )
        timing_document = self.timing_document_check(
            texts_by_name.get(_TEST_TIMING_DOCUMENT_NAME),
            archive_name,
            tests,
            path,
        )
        wanted_names = {
            _TEST_LIST_FILE_NAME,
            _TEST_PATHS_DOCUMENT_NAME,
            _TEST_TIMING_DOCUMENT_NAME,
            *profile_names.values(),
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
        has_raw_data_line = _TEST_OVERVIEW_RAW_DATA_MARKUP in overview_text
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
            return None
        timing_document = None
        for label in layout.manifest_recorded_labels:
            archive_name = (
                f"{_TEST_TIMER_ARTIFACTS_PREFIX}"
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
                continue
            if f'href="{archive_name}"' not in overview_text:
                self.fail(
                    f"overview index.html does not link {archive_name}:"
                    f" {out_dir}"
                )
            timing_document = self.timer_artifacts_archive_check(
                path, archive_name, tests, layout
            )
        return timing_document

    # Returns the archive's timing document of each test's overview values.
    def timing_document_check(
        self,
        text: str | None,
        archive_name: str,
        tests: Sequence[str],
        path: str,
    ) -> dict[str, dict[str, float]] | None:
        if text is None:
            self.fail(
                f"{archive_name} holds no {_TEST_TIMING_DOCUMENT_NAME}: {path}"
            )
            return None
        try:
            document = json.loads(text)
        except ValueError as error:
            self.fail(
                f"{_TEST_TIMING_DOCUMENT_NAME} holds no JSON: {error}: {path}"
            )
            return None
        if not isinstance(document, dict) or list(document) != sorted(tests):
            self.fail(
                f"{_TEST_TIMING_DOCUMENT_NAME} keys"
                f" {list(document) if isinstance(document, dict) else []},"
                f" expected the overview's tests {sorted(tests)}: {path}"
            )
            return None
        for test_name, values in document.items():
            if not isinstance(values, dict) or list(values) != list(
                _TEST_TIMING_VALUE_NAMES
            ):
                self.fail(
                    f"{_TEST_TIMING_DOCUMENT_NAME} gives {test_name} the"
                    f" values {values!r}, expected the names"
                    f" {list(_TEST_TIMING_VALUE_NAMES)}: {path}"
                )
                return None
            for value_name, value in values.items():
                if (
                    type(value) not in (int, float)
                    or value < 0
                    or not math.isfinite(value)
                ):
                    self.fail(
                        f"{_TEST_TIMING_DOCUMENT_NAME} gives {test_name}"
                        f" {value_name} {value!r}, expected a finite number"
                        f" not below 0: {path}"
                    )
                    return None
        return document


_FLAME_GRAPH_VIEW_KEY = _FLAME_GRAPH_VIEW_ENTRY[0]

_HEAT_MAP_VIEW_KEY = _HEAT_MAP_VIEW_ENTRY[0]
_HEAT_MAP_PAGE_TITLE = ""

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

_REPORT_CHECKSUM_COMMAND = (
    "find . -type f ! -name MANIFEST.txt -print"
    " | LC_ALL=C sort | LC_ALL=C tr '\\n' '\\0'"
    " | xargs -0 -r cksum --"
    " | LC_ALL=C sort | cksum"
)

_TEST_CALL_GRAPH_EDGE_CALLEE_FIELD = 1
_TEST_CALL_GRAPH_EDGE_CALLER_FIELD = 0
_TEST_CALL_GRAPH_EDGE_FIELDS = 5
_TEST_CALL_GRAPH_EDGE_FUNCTION_FIELDS = (0, 1)
_TEST_CALL_GRAPH_EDGE_INCLUSIVE_FIELD = 4
_TEST_CALL_GRAPH_FUNCTION_FIELDS = 2
_TEST_CALL_GRAPH_FUNCTION_NAME_FIELD = 0
_TEST_CALL_GRAPH_FUNCTION_SELF_FIELD = 1
_TEST_CALL_GRAPH_MODEL_KEYS = ("edges", "functions", "roots")
_TEST_CALL_GRAPH_PAGE_DIR_NAME = "call-graph"
_TEST_CALL_GRAPH_PAGE_LEAST_BYTES = 2000
_TEST_CALL_GRAPH_ROOT_CALLS_FIELD = 1
_TEST_CALL_GRAPH_ROOT_FIELDS = 2
_TEST_CALL_GRAPH_ROOT_FUNCTION_FIELD = 0
_TEST_CALL_GRAPH_START_FUNCTION_CALLS = 1
_TEST_CALL_GRAPH_START_FUNCTION_NAME = "main"
_TEST_CALL_GRAPH_STOP_FUNCTION_NAME = "exit"
_TEST_CALL_GRAPH_TABLE_ID = "call-graph-table-"
_TEST_DATABASE_CALL_COUNTS_START_FIELD = 1
_TEST_DATABASE_CALLEE_ROWS_FIELD = 6
_TEST_DATABASE_CALLER_ROWS_FIELD = 5
_TEST_DATABASE_FUNCTION_HREF_FIELD = 1
_TEST_DATABASE_FUNCTION_NAME_FIELD = 0
_TEST_DATABASE_MODEL_ID = "database-model-"
_TEST_DATABASE_PAGE_DIR_NAME = "database"
_TEST_DATABASE_ROW_BASELINE_CALLS_FIELD = 7
_TEST_DATABASE_ROW_CALLS_FIELD = 3
_TEST_DATABASE_ROW_FILE_FIELD = 1
_TEST_DATABASE_ROW_FUNCTION_FIELD = 0
_TEST_DATABASE_ROW_LINE_FIELD = 2
_TEST_DATABASE_VIEW_KEY = "database"
_TEST_DERIVED_COUNTER_NAMES = ("D1m", "DLm", "L1m", "LLm", "Bm", "CEst")
_TEST_FLAME_GRAPH_PAGE_LEAST_BYTES = 300
_TEST_FLAME_GRAPH_SCRIPT_LEAST_BYTES = 200
_TEST_HEAT_MAP_CALLER_COUNT_FIELD = 4
_TEST_HEAT_MAP_MODEL_LEAST_BYTES = 5000
_TEST_HEAT_MAP_PAGE_LEAST_BYTES = 1000
_TEST_LIST_FILE_NAME = "test_list.txt"
_TEST_MANIFEST_LEAST_BYTES = 40
_TEST_OVERVIEW_CHANGE_CELL_TEXT = (
    " in a cell whose heat_percent agrees with it, else an empty text"
)
_TEST_OVERVIEW_CHANGE_LARGEST_ERROR = 0.0050001
_TEST_OVERVIEW_CHANGE_PATTERN = (
    r"(?:0\.00%|[▲▼] *(?:≈0\.00%|-?\d+\.\d{2}%|∞%|≈∞%|\d+\.\d{2}x))?"
)
_TEST_OVERVIEW_PAGE_LEAST_BYTES = 2000
_TEST_OVERVIEW_PAGE_TITLE = ""
_TEST_OVERVIEW_RATIO_FIELDS = (2, 3, 4, 5)
_TEST_OVERVIEW_RATIO_LARGEST_ERROR = 0.00000050001
_TEST_OVERVIEW_RATIO_PATTERN = r"(?:\d+\.\d{6})?"
_TEST_OVERVIEW_RAW_DATA_MARKUP = '<div id="overview-raw-data-">'
_TEST_OVERVIEW_ROW_FIELD_COUNT = 6
_TEST_OVERVIEW_TESTS_HEADING_MARKUP = (
    '<div id="overview-tests-heading-" class="page-heading-"></div>'
)
_TEST_OVERVIEW_TESTS_TABLE_DATA_ID = "overview-tests-table-"
_TEST_OVERVIEW_TIME_LARGEST_ERROR = 0.0050001
_TEST_OVERVIEW_TIME_PER_LOOP_FIELD = 1
_TEST_OVERVIEW_TIME_PER_LOOP_PATTERN = r"(?:\d+\.\d{2}(?:s|ms|us|ns|ps))?"
_TEST_OVERVIEW_TIME_UNIT_SECONDS = {
    "s": 1.0,
    "ms": 1e-3,
    "us": 1e-6,
    "ns": 1e-9,
    "ps": 1e-12,
}
_TEST_OVERVIEW_VALUE_FIELDS = (1, 2, 3, 4, 5)
_TEST_PAGE_PREAMBLE_SCRIPT_NAMES = (
    "error_overlay.js",
    "settings.js",
    "utility.js",
    "ui_strings.js",
)
_TEST_PATHS_DOCUMENT_CODES = ("err", "git", "repo", "sys")
_TEST_PATHS_DOCUMENT_NAME = "0_file_data.json"
_TEST_PROFILE_FILE_SUFFIX = ".callgrind.out"
_TEST_RAW_ARCHIVE_LEAST_BYTES = 100
_TEST_README_HTML_NAME = "README.html"
_TEST_README_MARKDOWN_NAME = "README.md"
_TEST_SOURCE_DATABASE_GLOBAL_NAME = "report_source_database_"
_TEST_SOURCE_DATABASE_KEYS = ("files", "functions")
_TEST_SOURCE_DATABASE_LEAST_BYTES = 1000
_TEST_SOURCE_DATABASE_SCRIPT_PATH = "scripts/source_database.js"
_TEST_TIMER_ARTIFACTS_PREFIX = "timer-artifacts-"
_TEST_TIMING_DOCUMENT_NAME = "0_timing_data.json"
_TEST_TIMING_VALUE_NAMES = (
    "time_per_loop",
    "instructions_per_cycle",
    "loads_per_instruction",
    "branch_miss_ratio",
    "l1d_miss_ratio",
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
        "--readme-html",
        action="store_true",
        help=f"the report holds {_TEST_README_HTML_NAME}, which its help link"
        " opens",
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
            readme_html=namespace.readme_html,
            verbose=namespace.verbose,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
