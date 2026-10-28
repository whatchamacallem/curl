#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, dataclasses, json, os, shutil, subprocess, sys
from collections.abc import Container, Iterable, Iterator, Sequence
from typing import NamedTuple, NotRequired, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artifacts, callgrind, callgrind_diff, settings, theme

_ASSET_SOURCE_DATABASE_SCRIPT_NAME: str = ""
_ASSET_TEMPLATE_HEAT_MAP_PAGE_NAME: str = ""
_CALLGRIND_FILE_DATA_CODE_KEY: str = ""
_CALLGRIND_FILE_DATA_ERROR_CODE: str = ""
_CALLGRIND_FILE_DATA_GIT_CODE: str = ""
_CALLGRIND_FILE_DATA_PATH_KEY: str = ""
_HEAT_MAP_MODEL_DIR_NAME: str = ""
_HEAT_MAP_MODEL_GLOBAL_NAME: str = ""
_HEAT_MAP_TREE_ALWAYS_LISTED_DIRS: tuple[str, ...] = ()
_HEAT_MAP_VIEW_ENTRY: tuple[str, str] = ("", "")
_REPORT_SCRIPTS_DIR_NAME: str = ""
_REPORT_SOURCES_DIR_NAME: str = ""
_SETTINGS_HELD_SCRIPT_TEMPLATE_ID: str = ""
settings.load_into(__name__)

_HEAT_MAP_PAGE = theme.template_fill(
    theme.asset_text_read(_ASSET_TEMPLATE_HEAT_MAP_PAGE_NAME),
    {
        "__HELD_SCRIPT_TEMPLATE_ID__": theme.render_html_escape(
            _SETTINGS_HELD_SCRIPT_TEMPLATE_ID
        )
    },
)

_HEAT_MAP_PAGE_PATH = _HEAT_MAP_VIEW_ENTRY[1]


class CallgrindToHeatmap:
    class CallRow(NamedTuple):
        function: int
        file: str
        line: int
        cost: callgrind.Costs
        count_: int

    class DataArgs(NamedTuple):
        artifacts: str
        report: str
        baseline: str
        modified: str
        diff: bool

    class DatabaseFile(TypedDict):
        source: str | None
        group: str

    # Holds what every test shows so far, the source database being built.
    @dataclasses.dataclass
    class DatabaseTally:
        shown: dict[str, callgrind.PathInfo] = dataclasses.field(
            default_factory=dict
        )
        files: dict[str, CallgrindToHeatmap.DatabaseFile] = dataclasses.field(
            default_factory=dict
        )
        locations: set[str] = dataclasses.field(default_factory=set)
        cold: list[str] = dataclasses.field(default_factory=list)
        tests: list[CallgrindToHeatmap.ShownTest] = dataclasses.field(
            default_factory=list
        )

    class FileModel(TypedDict):
        self: callgrind.Costs
        calls: callgrind.Costs
        source: str | None
        lines: dict[str, CallgrindToHeatmap.LineCost]
        lineFunctions: dict[str, list[int]]
        baseline: NotRequired[dict[str, callgrind.Costs]]
        callees: dict[str, list[CallgrindToHeatmap.CallRow]]
        group: str
        raw: str

    @dataclasses.dataclass
    class FileTally:
        group: str
        raw: str
        self_cost: callgrind.Costs
        calls_cost: callgrind.Costs
        source_path: str | None = None
        lines: dict[str, CallgrindToHeatmap.LineTally] = dataclasses.field(
            default_factory=dict
        )
        line_functions: dict[str, list[int]] = dataclasses.field(
            default_factory=dict
        )
        callees: dict[str, list[CallgrindToHeatmap.CallRow]] = (
            dataclasses.field(default_factory=dict)
        )

        def emit(self) -> CallgrindToHeatmap.FileModel:
            trim = callgrind.costs_trim
            key = CallgrindToHeatmap.call_row_cost_key
            return {
                "self": trim(self.self_cost),
                "calls": trim(self.calls_cost),
                "source": self.source_script_name(),
                "lines": {
                    line: CallgrindToHeatmap.LineCost(
                        trim(record.self_cost),
                        trim(record.calls_cost),
                        record.count,
                    )
                    for line, record in self.lines.items()
                },
                "lineFunctions": self.line_functions,
                "callees": {
                    line: sorted(rows, key=key)
                    for line, rows in self.callees.items()
                },
                "group": self.group,
                "raw": self.raw,
            }

        def line(
            self, line_number: int, counter_count: int
        ) -> CallgrindToHeatmap.LineTally:
            record = self.lines.get(str(line_number))
            if record is None:
                record = self.lines[str(line_number)] = (
                    CallgrindToHeatmap.LineTally(
                        [0] * counter_count, [0] * counter_count
                    )
                )
            return record

        def source_script_name(self) -> str | None:
            if self.source_path is None:
                return None
            return CallgrindToHeatmap.source_name(self.raw)

    class FunctionModel(TypedDict):
        name: str
        file: str
        line: int
        self: callgrind.Costs
        calls: callgrind.Costs
        callers: list[CallgrindToHeatmap.CallRow]

    class Derive(NamedTuple):
        paths: callgrind.DerivedPaths
        baseline_sources_dir: str
        modified_sources_dir: str

    class HeatMapTotals(TypedDict):
        counters: list[str]
        derived: list[callgrind.ResolvedDerivedCounter]
        totals: callgrind.Costs
        diff: bool

    class HeatModel(TypedDict):
        heatMapTotals: CallgrindToHeatmap.HeatMapTotals
        files: dict[str, CallgrindToHeatmap.FileModel]
        functions: list[CallgrindToHeatmap.FunctionModel]
        cold: list[str]
        functionBaseline: NotRequired[list[callgrind.Costs]]
        fileBaseline: NotRequired[dict[str, callgrind.Costs]]

    class LineCost(NamedTuple):
        self_cost: callgrind.Costs
        calls_cost: callgrind.Costs
        count_: int

    @dataclasses.dataclass
    class LineTally:
        self_cost: callgrind.Costs
        calls_cost: callgrind.Costs
        count: int = 0

    # Holds a regular test's profile and paths for its function data.
    class ShownTest(NamedTuple):
        test_name: str
        profile: callgrind.Profile
        info: dict[str, callgrind.PathInfo]

    class SourceDatabase(TypedDict):
        files: list[str]
        functions: list[str]

    # Holds a diff's paths and a test's function data diff.
    class TestDiff(NamedTuple):
        derive: CallgrindToHeatmap.Derive
        function_diff: callgrind_diff.FunctionDiffDocument

    def __init__(self, verbose: int) -> None:
        self.verbose = verbose

    @staticmethod
    def call_row_cost_key(row: CallgrindToHeatmap.CallRow) -> int:
        return -(row.cost[0] if row.cost else 0)

    # Returns the tracked files no page shows, sorted.
    def cold_paths(
        self, tracked: Sequence[str], shown: Container[str]
    ) -> list[str]:
        return sorted(
            relative for relative in tracked if relative not in shown
        )

    def data_render(
        self, test_name: str, model: CallgrindToHeatmap.HeatModel
    ) -> str:
        data = json.dumps(model, separators=(",", ":"), ensure_ascii=False)
        head, tail = self.model_script_parts(test_name)
        return f"{head}{data}{tail}"

    # Writes every test's model and sources, the source database, the paths.
    def data_write(self, args: CallgrindToHeatmap.DataArgs) -> None:
        artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        test_names = artifacts.test_list_read(artifacts_dir)
        self.test_names_check(test_names)
        derive, tracked = self.derive_resolve(artifacts_dir, args)
        database = self.tests_write(
            args.report, artifacts_dir, test_names, derive, tracked
        )
        self.source_database_write(args.report, database)
        if derive is None:
            file_paths = self.paths_write(
                artifacts.artifact_path(artifacts_dir, "file-data"),
                database.shown,
                database.cold,
            )
            self.function_data_write(artifacts_dir, database.tests, file_paths)

    # Adds a test's files and functions with a line to the source database.
    def database_add(
        self,
        database: CallgrindToHeatmap.DatabaseTally,
        test_name: str,
        profile: callgrind.Profile,
        info: dict[str, callgrind.PathInfo],
        functions: Sequence[CallgrindToHeatmap.FunctionModel],
    ) -> None:
        for raw, path_info in info.items():
            known = database.shown.setdefault(raw, path_info)
            if known.group != path_info.group:
                sys.exit(
                    f"error: the test {test_name} codes {raw} as"
                    f" {path_info.group}, an earlier test as {known.group}"
                )
        tallies = self.file_tallies(info, len(profile.counters))
        for display, tally in tallies.items():
            entry: CallgrindToHeatmap.DatabaseFile = {
                "source": tally.source_script_name(),
                "group": tally.group,
            }
            known_entry = database.files.setdefault(display, entry)
            if known_entry != entry:
                sys.exit(
                    f"error: the test {test_name} shows {display} as"
                    f" {entry}, an earlier test as {known_entry}"
                )
        for function in functions:
            if function["line"]:
                database.locations.add(function["name"])

    # Returns the diff's path derive or None, and the tracked files.
    def derive_resolve(
        self, artifacts_dir: str, args: CallgrindToHeatmap.DataArgs
    ) -> tuple[CallgrindToHeatmap.Derive | None, Sequence[str]]:
        self.diff_reports_check(args.diff, args.baseline, args.modified)
        if not args.diff:
            return None, self.repo_tracked_files()
        derive = CallgrindToHeatmap.Derive(
            callgrind.DerivedPaths(
                artifacts.artifact_path(artifacts_dir, "baseline-profiles"),
                artifacts.artifact_path(artifacts_dir, "modified-profiles"),
            ),
            os.path.join(args.baseline, _REPORT_SOURCES_DIR_NAME),
            os.path.join(args.modified, _REPORT_SOURCES_DIR_NAME),
        )
        return derive, derive.paths.tracked

    def diff_model(
        self,
        model: CallgrindToHeatmap.HeatModel,
        profile: callgrind.LineProfile,
        function_diff: callgrind_diff.FunctionDiffDocument,
    ) -> None:
        totals = model["heatMapTotals"]
        totals["totals"] = callgrind_diff.profile_magnitudes(profile)
        totals["diff"] = True
        model["functionBaseline"] = [
            callgrind.costs_trim(row.baseline_costs)
            for row in function_diff["functions"]
        ]
        model["fileBaseline"] = {
            path: costs
            for path, costs in function_diff["fileBaseline"].items()
            if path in model["files"]
        }
        for path, entry in model["files"].items():
            lines: dict[str, callgrind.Costs] = {}
            for line in entry["lines"]:
                costs = function_diff["lineBaseline"].get(
                    callgrind.baseline_line_key(path, line)
                )
                if costs:
                    lines[line] = costs
            entry["baseline"] = lines

    # Returns the shown paths with each place of a function data diff added.
    def diff_place_infos(
        self,
        function_diff: callgrind_diff.FunctionDiffDocument,
        derive: CallgrindToHeatmap.Derive,
        recorded_info: dict[str, callgrind.PathInfo],
    ) -> dict[str, callgrind.PathInfo]:
        info = dict(recorded_info)
        for row in function_diff["functions"]:
            file_path = function_diff["files"][row.file_index]
            place_info = self.path_info(
                file_path,
                function_diff["objects"][row.object_index],
                derive,
            )
            known = info.setdefault(file_path, place_info)
            if known != place_info:
                sys.exit(
                    f"error: the diff shows {file_path} as {known.display}"
                    f" and as {place_info.display}"
                )
        return info

    # Returns each function's shown place, as its function data diff gives it.
    def diff_places(
        self,
        function_diff: callgrind_diff.FunctionDiffDocument,
        info: dict[str, callgrind.PathInfo],
    ) -> dict[str, callgrind.SourceLine]:
        return {
            row.function_name: callgrind.SourceLine(
                info[function_diff["files"][row.file_index]].display,
                row.line_number,
            )
            for row in function_diff["functions"]
        }

    # Refuses a diff without its two reports, or reports without a diff.
    def diff_reports_check(
        self, is_diff: bool, baseline_report: str, modified_report: str
    ) -> None:
        if (baseline_report or modified_report) and not is_diff:
            sys.exit("error: --baseline and --modified need --diff")
        if is_diff and (not baseline_report or not modified_report):
            sys.exit("error: --diff needs --baseline and --modified")

    # Returns one empty tally per path a page shows, keyed by that path.
    def file_tallies(
        self, info: dict[str, callgrind.PathInfo], counter_count: int
    ) -> dict[str, CallgrindToHeatmap.FileTally]:
        accumulators: dict[str, CallgrindToHeatmap.FileTally] = {}
        for raw, path_info in info.items():
            entry = accumulators.get(path_info.display)
            if entry is None:
                entry = accumulators[path_info.display] = (
                    CallgrindToHeatmap.FileTally(
                        group=path_info.group,
                        raw=raw
                        if path_info.group == _CALLGRIND_FILE_DATA_ERROR_CODE
                        else path_info.display,
                        self_cost=[0] * counter_count,
                        calls_cost=[0] * counter_count,
                    )
                )
            if entry.source_path is None and path_info.local:
                entry.source_path = path_info.local
        return accumulators

    def files_model(
        self,
        profile: callgrind.Profile,
        info: dict[str, callgrind.PathInfo],
        function_index: dict[str, int],
        locations: dict[str, callgrind.SourceLine],
    ) -> dict[str, CallgrindToHeatmap.FileModel]:
        counter_count = len(profile.counters)
        display = {raw: path_info.display for raw, path_info in info.items()}
        accumulators = self.file_tallies(info, counter_count)
        for key, costs in profile.line_self.items():
            entry = accumulators[display[key.file]]
            callgrind.costs_add(entry.self_cost, costs)
            callgrind.costs_add(
                entry.line(key.line, counter_count).self_cost, costs
            )
        for key, costs in profile.line_calls.items():
            entry = accumulators[display[key.file]]
            callgrind.costs_add(entry.calls_cost, costs)
            record = entry.line(key.line, counter_count)
            callgrind.costs_add(record.calls_cost, costs)
            record.count += profile.line_call_count[key]
        for function, index in function_index.items():
            for key in (
                *profile.function_lines.get(function, {}),
                *profile.function_call_lines.get(function, ()),
            ):
                listed = accumulators[display[key.file]].line_functions
                indexes = listed.setdefault(str(key.line), [])
                if index not in indexes:
                    indexes.append(index)
        for site, tally in profile.callees.items():
            if site.callee not in profile.function_home:
                raise KeyError(
                    f"callee {site.callee!r} is missing from function_home"
                )
            callee_location = locations[site.callee]
            accumulators[display[site.file]].callees.setdefault(
                str(site.line), []
            ).append(
                CallgrindToHeatmap.CallRow(
                    function_index[site.callee],
                    callee_location.file,
                    callee_location.line,
                    callgrind.costs_trim(tally.costs),
                    tally.count,
                )
            )
        return {name: entry.emit() for name, entry in accumulators.items()}

    # Returns a test's function data, each file by its paths document index.
    def function_data(
        self,
        profile: callgrind.Profile,
        info: dict[str, callgrind.PathInfo],
        file_indexes: dict[str, int],
    ) -> callgrind.FunctionDataDocument:
        function_names = sorted(profile.function_home)
        function_index = {
            name: index for index, name in enumerate(function_names)
        }
        objects = sorted(
            {
                callgrind.repo_root_strip(
                    profile.function_keys[name].object_path
                )
                for name in function_names
            }
        )
        object_index = {path: index for index, path in enumerate(objects)}
        caller_rows: dict[str, list[callgrind.CallCount]] = {}
        callee_rows: dict[str, list[callgrind.CallCount]] = {
            name: [] for name in function_names
        }
        for name in function_names:
            caller_rows[name] = []
            for caller_name, calls in sorted(
                callgrind.caller_calls(profile, name).items()
            ):
                caller_rows[name].append(
                    callgrind.CallCount(
                        function_index[caller_name], calls.calls
                    )
                )
                callee_rows[caller_name].append(
                    callgrind.CallCount(function_index[name], calls.calls)
                )
        rows: list[callgrind.FunctionDataRow] = []
        for name in function_names:
            key = profile.function_keys[name]
            object_path = callgrind.repo_root_strip(key.object_path)
            place = self.function_line(profile, name)
            path_info = info[place.file]
            file_path = callgrind.path_canonical(place.file)
            # An error coded file is shown under its object's file name.
            if (
                callgrind.display_path(file_path, path_info.group, object_path)
                != path_info.display
            ):
                sys.exit(
                    f"error: {name} of {object_path} is placed in"
                    f" {path_info.display}, which its function data would"
                    f" show under its own object as {file_path}"
                )
            rows.append(
                callgrind.FunctionDataRow(
                    object_index[object_path],
                    key.name,
                    file_indexes[file_path],
                    place.line,
                    list(profile.function_self.get(name, profile.zeros())),
                    caller_rows[name],
                    callee_rows[name],
                )
            )
        return {
            "counters": list(profile.counters),
            "objects": objects,
            "functions": rows,
        }

    # Writes each test's function data, its files indexed in the paths order.
    def function_data_write(
        self,
        artifacts_dir: str,
        shown_tests: Sequence[CallgrindToHeatmap.ShownTest],
        file_paths: Sequence[str],
    ) -> None:
        file_indexes = {
            file_path: index for index, file_path in enumerate(file_paths)
        }
        for shown_test in shown_tests:
            document = self.function_data(
                shown_test.profile, shown_test.info, file_indexes
            )
            text = json.dumps(
                document, separators=(",", ":"), ensure_ascii=False
            )
            path = artifacts.artifact_path(
                artifacts_dir, "function-data", shown_test.test_name
            )
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(f"{text}\n")
            if self.verbose:
                print(
                    f"wrote {path} ({len(text.encode('utf-8')) + 1:,} bytes)"
                )

    # Returns where a function is addressed, its entry line or the line before.
    def function_line(
        self, profile: callgrind.Profile, name: str
    ) -> callgrind.SourceLine:
        entry = profile.function_entry[name]
        before = callgrind.SourceLine(entry.file, entry.line - 1)
        if (
            entry.line <= 1
            or before in profile.line_self
            or before in profile.line_calls
        ):
            return entry
        own_lines = {
            *profile.function_lines.get(name, {}),
            *profile.function_call_lines.get(name, set()),
        }
        return before if len(own_lines) > 1 else entry

    # Returns each named function's shown file and the line it is addressed at.
    def function_locations(
        self,
        profile: callgrind.Profile,
        shown_paths: dict[str, str],
        function_names: Iterable[str],
    ) -> dict[str, callgrind.SourceLine]:
        locations: dict[str, callgrind.SourceLine] = {}
        for function_name in function_names:
            location = self.function_line(profile, function_name)
            locations[function_name] = callgrind.SourceLine(
                shown_paths[location.file], location.line
            )
        return locations

    def functions_model(
        self,
        profile: callgrind.Profile,
        info: dict[str, callgrind.PathInfo],
        function_names: Sequence[str],
        function_index: dict[str, int],
        locations: dict[str, callgrind.SourceLine],
        self_costs: dict[str, callgrind.Costs],
    ) -> list[CallgrindToHeatmap.FunctionModel]:
        display = {raw: path_info.display for raw, path_info in info.items()}
        functions: list[CallgrindToHeatmap.FunctionModel] = []
        for name in function_names:
            location = locations[name]
            callers = sorted(
                (
                    CallgrindToHeatmap.CallRow(
                        function_index[caller.function],
                        display.get(caller.file, caller.file),
                        caller.line,
                        callgrind.costs_trim(tally.costs),
                        tally.count,
                    )
                    for caller, tally in profile.callers.get(name, {}).items()
                ),
                key=self.call_row_cost_key,
            )
            functions.append(
                {
                    "name": name,
                    "file": location.file,
                    "line": location.line,
                    "self": callgrind.costs_trim(self_costs.get(name, [])),
                    "calls": callgrind.costs_trim(
                        profile.function_calls.get(name, [])
                    ),
                    "callers": callers,
                }
            )
        return functions

    def model(
        self,
        profile: callgrind.Profile,
        tracked: Sequence[str],
        test_diff: CallgrindToHeatmap.TestDiff | None,
    ) -> tuple[CallgrindToHeatmap.HeatModel, dict[str, callgrind.PathInfo]]:
        if test_diff is None:
            info = self.profile_path_infos(profile, None)
            function_names = sorted(profile.function_home)
            locations = self.function_locations(
                profile,
                {raw: path_info.display for raw, path_info in info.items()},
                function_names,
            )
            self_costs = dict(profile.function_self)
        else:
            function_diff = test_diff.function_diff
            info = self.diff_place_infos(
                function_diff,
                test_diff.derive,
                self.profile_path_infos(profile, test_diff.derive),
            )
            function_names = [
                row.function_name for row in function_diff["functions"]
            ]
            locations = self.diff_places(function_diff, info)
            self_costs = {
                row.function_name: row.self_costs
                for row in function_diff["functions"]
            }
        function_index = {name: i for i, name in enumerate(function_names)}
        files = self.files_model(profile, info, function_index, locations)
        functions = self.functions_model(
            profile,
            info,
            function_names,
            function_index,
            locations,
            self_costs,
        )
        callgrind.ranking_counter_check(profile.counters, "this profile")
        return {
            "heatMapTotals": {
                "counters": profile.counters,
                "derived": profile.resolved_derived_counters(),
                "totals": profile.totals(),
                "diff": False,
            },
            "files": files,
            "functions": functions,
            "cold": self.cold_paths(tracked, files),
        }, info

    # Returns the path of a test's model script in a report.
    def model_path(self, report_dir: str, test_name: str) -> str:
        return os.path.join(
            report_dir,
            os.path.dirname(_HEAT_MAP_PAGE_PATH),
            _HEAT_MAP_MODEL_DIR_NAME,
            f"{test_name}.js",
        )

    # Returns the text a test's model script holds before and after its model.
    def model_script_parts(self, test_name: str) -> tuple[str, str]:
        models_global = f"window.{_HEAT_MAP_MODEL_GLOBAL_NAME}"
        return (
            f"{models_global} = {models_global} || {{}};\n"
            f"{models_global}[{json.dumps(test_name)}] = ",
            ";\n",
        )

    # Writes a test's model script, printing what the model holds if verbose.
    def model_write(
        self,
        report_dir: str,
        test_name: str,
        model: CallgrindToHeatmap.HeatModel,
    ) -> None:
        model_script = self.data_render(test_name, model)
        path = self.model_path(report_dir, test_name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(model_script)
        if not self.verbose:
            return
        count = sum(
            1
            for entry in model["files"].values()
            if entry["source"] is not None
        )
        print(
            f"files with samples: {len(model['files'])}"
            f" ({count} with source shared),"
            f" cold files listed: {len(model['cold'])}, "
            f"functions: {len(model['functions'])}"
        )
        print(f"wrote {path} ({len(model_script.encode('utf-8')):,} bytes)")

    def page_write(self, report_dir: str) -> None:
        path = os.path.join(report_dir, _HEAT_MAP_PAGE_PATH)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(_HEAT_MAP_PAGE)
        if self.verbose:
            print(
                f"wrote {path} ({len(_HEAT_MAP_PAGE.encode('utf-8')):,} bytes)"
            )

    # Returns how a page shows a recorded path of an object.
    def path_info(
        self,
        raw: str,
        object_path: str,
        derive: CallgrindToHeatmap.Derive | None,
    ) -> callgrind.PathInfo:
        if derive is None:
            path_info = callgrind.path_norm(raw)
            return path_info._replace(
                display=callgrind.display_path(
                    path_info.display, path_info.group, object_path
                )
            )
        entry = derive.paths.path_entry(raw)
        display = derive.paths.display(raw, object_path)
        script = None
        if entry.has_source:
            script = os.path.join(
                derive.baseline_sources_dir
                if entry.in_baseline
                else derive.modified_sources_dir,
                self.source_name(display),
            )
        return callgrind.PathInfo(display, script, entry.group)

    # Writes the code of each path shown or kept cold, answering the paths.
    def paths_write(
        self,
        path: str,
        info: dict[str, callgrind.PathInfo],
        cold_files: Sequence[str],
    ) -> list[str]:
        coded: dict[str, tuple[str, str]] = {}
        for raw, path_info in info.items():
            code = path_info.group
            canonical = callgrind.path_canonical(raw)
            first_raw, first_code = coded.setdefault(canonical, (raw, code))
            if first_code != code:
                sys.exit(
                    f"error: {first_raw} and {raw} share the canonical path"
                    f" {canonical} but not the code: {first_code} vs {code}"
                )
        document = {canonical: code for canonical, (_, code) in coded.items()}
        for cold in cold_files:
            document.setdefault(cold, _CALLGRIND_FILE_DATA_GIT_CODE)
        file_paths = sorted(document)
        text = json.dumps(
            [
                {
                    _CALLGRIND_FILE_DATA_PATH_KEY: file_path,
                    _CALLGRIND_FILE_DATA_CODE_KEY: document[file_path],
                }
                for file_path in file_paths
            ],
            separators=(",", ":"),
            ensure_ascii=False,
        )
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f"{text}\n")
        if self.verbose:
            print(f"wrote {path} ({len(text.encode('utf-8')) + 1:,} bytes)")
        return file_paths

    # Returns how a page shows each path the profile records.
    def profile_path_infos(
        self,
        profile: callgrind.Profile,
        derive: CallgrindToHeatmap.Derive | None,
    ) -> dict[str, callgrind.PathInfo]:
        raw_files = sorted(
            {key.file for key in profile.line_self}
            | {key.file for key in profile.line_calls}
            | {entry.file for entry in profile.function_entry.values()}
        )
        return {
            raw: self.path_info(raw, profile.file_ob[raw], derive)
            for raw in raw_files
        }

    # Loads each test's profile in turn, refusing counters unlike the first's.
    def profiles_load(
        self, directory: str, kind: str, test_names: Iterable[str]
    ) -> Iterator[tuple[str, callgrind.Profile]]:
        first: tuple[str, list[str]] | None = None
        for test_name in test_names:
            profile = callgrind.profile_load(directory, kind, test_name)
            path = artifacts.artifact_path(directory, kind, test_name)
            if first is None:
                first = (path, profile.counters)
            elif profile.counters != first[1]:
                sys.exit(
                    f"error: {path} records the counters"
                    f" {' '.join(profile.counters)}, but {first[0]} records"
                    f" {' '.join(first[1])}"
                )
            yield test_name, profile

    def repo_tracked_files(self) -> list[str]:
        command = [
            "git",
            "-C",
            callgrind.REPO_ROOT,
            "ls-files",
            "--",
            *_HEAT_MAP_TREE_ALWAYS_LISTED_DIRS,
        ]
        completed = subprocess.run(
            command, check=False, stdout=subprocess.PIPE, text=True
        )
        if completed.returncode != 0:
            print(
                "error: cannot list the tracked files a cold tree needs:"
                f" exit {completed.returncode} from: {' '.join(command)}",
                file=sys.stderr,
            )
            sys.exit(completed.returncode)
        return [
            line
            for line in completed.stdout.split("\n")
            if line.endswith((".c", ".h"))
        ]

    # Writes every file the tests show and every function with a line.
    def source_database_write(
        self, report_dir: str, tally: CallgrindToHeatmap.DatabaseTally
    ) -> None:
        self.source_names(
            {
                display: entry["source"]
                for display, entry in tally.files.items()
            }
        )
        database: CallgrindToHeatmap.SourceDatabase = {
            "files": sorted(tally.files),
            "functions": sorted(tally.locations),
        }
        data = json.dumps(database, separators=(",", ":"), ensure_ascii=False)
        text = f"window.report_source_database_ = {data};\n"
        script_path = os.path.join(
            report_dir,
            _REPORT_SCRIPTS_DIR_NAME,
            _ASSET_SOURCE_DATABASE_SCRIPT_NAME,
        )
        with open(script_path, "w", encoding="utf-8") as handle:
            handle.write(text)
        if self.verbose:
            print(f"wrote {script_path} ({len(text.encode('utf-8')):,} bytes)")

    @staticmethod
    def source_name(display: str) -> str:
        flat = "".join(char if char.isalnum() else "_" for char in display)
        return f"{flat}.js"

    # Returns each source script name with its path, refusing a shared name.
    def source_names(self, sources: dict[str, str | None]) -> dict[str, str]:
        shared = [
            (name, display)
            for display, name in sources.items()
            if name is not None
        ]
        names = dict(shared)
        if len(names) != len(shared):
            collided: dict[str, list[str]] = {}
            for name, display in shared:
                collided.setdefault(name, []).append(display)
            pairs = sorted(
                (name, paths)
                for name, paths in collided.items()
                if len(paths) > 1
            )
            report = "\n".join(
                f"  {name}: {' and '.join(sorted(paths))}"
                for name, paths in pairs
            )
            sys.exit(
                "error: two source paths share one sources/ script"
                f" name:\n{report}"
            )
        return names

    def source_read(self, local: str) -> str:
        with open(local, "rb") as handle:
            return handle.read().decode("utf-8", errors="replace")

    def sources_write(
        self,
        out_dir: str,
        info: dict[str, callgrind.PathInfo],
        model: CallgrindToHeatmap.HeatModel,
        derive: CallgrindToHeatmap.Derive | None,
    ) -> None:
        names = self.source_names(
            {
                display: entry["source"]
                for display, entry in model["files"].items()
            }
        )
        local = {
            path_info.display: path_info.local
            for path_info in info.values()
            if path_info.local
        }
        os.makedirs(out_dir, exist_ok=True)
        for name, display in sorted(names.items()):
            path = os.path.join(out_dir, str(name))
            if derive is not None:
                shutil.copyfile(local[display], path)
                continue
            text = self.source_read(local[display])
            body = json.dumps(text, ensure_ascii=False).replace("</", "<\\/")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(
                    "window.report_sources_ = window.report_sources_ || {};\n"
                    f"window.report_sources_[{json.dumps(display)}] ="
                    f" {body};\n"
                )

    # Refuses a test named like a shipped script.
    def test_names_check(self, test_names: Iterable[str]) -> None:
        shipped_scripts = theme.shipped_script_names()
        for test_name in test_names:
            if f"{test_name}.js" in shipped_scripts:
                sys.exit(
                    f"error: the test {test_name} is named like the shipped"
                    f" script {test_name}.js"
                )

    # Writes each test's model and sources, tallying the source database.
    def tests_write(
        self,
        report_dir: str,
        artifacts_dir: str,
        test_names: Sequence[str],
        derive: CallgrindToHeatmap.Derive | None,
        tracked: Sequence[str],
    ) -> CallgrindToHeatmap.DatabaseTally:
        database = CallgrindToHeatmap.DatabaseTally()
        kind = "callgrind" if derive is None else "delta"
        sources_dir = os.path.join(report_dir, _REPORT_SOURCES_DIR_NAME)
        for test_name, profile in self.profiles_load(
            artifacts_dir, kind, test_names
        ):
            test_diff = (
                None
                if derive is None
                else CallgrindToHeatmap.TestDiff(
                    derive,
                    callgrind_diff.function_diff_load(
                        artifacts_dir, test_name
                    ),
                )
            )
            model, info = self.model(profile, tracked, test_diff)
            if test_diff is None:
                database.tests.append(
                    CallgrindToHeatmap.ShownTest(test_name, profile, info)
                )
            else:
                self.diff_model(model, profile, test_diff.function_diff)
            self.sources_write(sources_dir, info, model, derive)
            self.model_write(report_dir, test_name, model)
            self.database_add(
                database, test_name, profile, info, model["functions"]
            )
        database.cold = self.cold_paths(tracked, database.files)
        return database


_WIRE_FIELD_ORDERS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (
        CallgrindToHeatmap.CallRow._fields,
        ("function", "file", "line", "cost", "count_"),
    ),
    (
        CallgrindToHeatmap.LineCost._fields,
        ("self_cost", "calls_cost", "count_"),
    ),
    (callgrind.ResolvedDerivedCounter._fields, ("name", "terms")),
    (callgrind.ResolvedTerm._fields, ("coefficient", "counter_index")),
)
for _record_fields, _wire_fields in _WIRE_FIELD_ORDERS:
    if _record_fields != _wire_fields:
        raise ValueError(
            "a page record's fields moved off the wire order heat_map.js"
            f" reads: {_record_fields} vs {_wire_fields}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    data_parser = subparsers.add_parser(
        "data",
        help="every listed test's model script and sources, the source"
        " database, and the paths document of a regular report",
    )
    data_parser.add_argument(
        "--artifacts",
        required=True,
        metavar="DIR",
        help="the profiler artifacts directory, holding the report's own,"
        " whose test list names every test modeled",
    )
    data_parser.add_argument(
        "--report",
        required=True,
        metavar="DIR",
        help="the report directory the scripts and sources are written in",
    )
    data_parser.add_argument(
        "--diff",
        action="store_true",
        help="the recordings are callgrind_diff.py deltas: each model"
        " carries the baseline costs every share divides by, and the"
        " sources are copied from the baseline report",
    )
    data_parser.add_argument(
        "--baseline",
        default="",
        metavar="DIR",
        help="the baseline report, whose sources are copied for each file"
        " the diff shows that the baseline shows (--diff only)",
    )
    data_parser.add_argument(
        "--modified",
        default="",
        metavar="DIR",
        help="the modified report, whose sources are copied for each file"
        " the diff shows that the baseline does not (--diff only)",
    )

    page_parser = subparsers.add_parser(
        "page",
        help="the one heat map page, once every test's model script is"
        " written",
    )
    page_parser.add_argument(
        "--report",
        required=True,
        metavar="DIR",
        help="the report directory the page is written in",
    )
    for written_parser in (data_parser, page_parser):
        written_parser.add_argument(
            "--verbose",
            action="count",
            default=0,
            help="print each file written; a quiet run prints nothing on"
            " success",
        )

    namespace = parser.parse_args()
    heat_map = CallgrindToHeatmap(namespace.verbose)
    if namespace.cmd == "page":
        heat_map.page_write(namespace.report)
    else:
        heat_map.data_write(
            CallgrindToHeatmap.DataArgs(
                artifacts=namespace.artifacts,
                report=namespace.report,
                baseline=namespace.baseline,
                modified=namespace.modified,
                diff=namespace.diff,
            )
        )


if __name__ == "__main__":
    main()
