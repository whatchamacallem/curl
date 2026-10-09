#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, dataclasses, json, os, subprocess, sys
from collections.abc import Sequence
from typing import NamedTuple, NotRequired, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind, callgrind_diff, settings, theme

_ASSET_DEBUG_SCRIPT_NAME: str = ""
_ASSET_HEAT_MAP_SCRIPT_NAME: str = ""
_ASSET_HEAT_MAP_STYLESHEET_NAME: str = ""
_ASSET_MENU_STYLESHEET_NAME: str = ""
_ASSET_PULLDOWN_TEXT_SCRIPT_NAME: str = ""
_ASSET_TEMPLATE_HEAT_MAP_MAIN_NAME: str = ""
_ASSET_TEMPLATE_HEAT_MAP_PAGE_NAME: str = ""
_ASSET_THEME_SCRIPT_NAME: str = ""
_HEAT_MAP_MODEL_DIR_NAME: str = ""
_HEAT_MAP_MODEL_GLOBAL_NAME: str = ""
_HEAT_MAP_TREE_ALWAYS_LISTED_DIRS: tuple[str, ...] = ()
_HEAT_MAP_VIEW_ENTRY: tuple[str, str] = ("", "")
_REPORT_ASSETS_DIR_NAME: str = ""
_REPORT_SOURCES_DIR_NAME: str = ""
_REPORT_TEST_SUITE_NAME: str = ""
settings.load_into(__name__)

BODY = theme.asset_text_read(_ASSET_TEMPLATE_HEAT_MAP_PAGE_NAME)

_HEAT_MAP_MAIN = theme.asset_text_read(_ASSET_TEMPLATE_HEAT_MAP_MAIN_NAME)

_HEAT_MAP_PAGE_PATH = _HEAT_MAP_VIEW_ENTRY[1]
_HEAT_MAP_PAGE_DEPTH = _HEAT_MAP_PAGE_PATH.count("/")


class CallgrindToHeatmap:
    class CallRow(NamedTuple):
        function: int
        file: str
        line: int
        cost: callgrind.Costs
        count_: int

    class DataArgs(NamedTuple):
        callgrind_file: list[str]
        report_dir: str
        test: str
        diff: bool
        baseline_data: str

    class FileModel(TypedDict):
        self: callgrind.Costs
        calls: callgrind.Costs
        source: str | None
        lines: dict[str, CallgrindToHeatmap.LineCost]
        lineFunction: dict[str, int]
        baseline: NotRequired[dict[str, callgrind.Costs]]
        callees: dict[str, list[CallgrindToHeatmap.CallRow]]
        group: callgrind.Group
        raw: str

    @dataclasses.dataclass
    class FileTally:
        group: callgrind.Group
        raw: str
        self_cost: callgrind.Costs
        calls_cost: callgrind.Costs
        source: str | None = None
        lines: dict[str, CallgrindToHeatmap.LineTally] = dataclasses.field(
            default_factory=dict
        )
        line_function: dict[str, int] = dataclasses.field(default_factory=dict)
        callees: dict[str, list[CallgrindToHeatmap.CallRow]] = (
            dataclasses.field(default_factory=dict)
        )

        def emit(self) -> CallgrindToHeatmap.FileModel:
            trim = callgrind.costs_trim
            key = CallgrindToHeatmap.call_row_cost_key
            return {
                "self": trim(self.self_cost),
                "calls": trim(self.calls_cost),
                "source": (
                    None
                    if self.source is None
                    else CallgrindToHeatmap.source_name(self.raw)
                ),
                "lines": {
                    line: CallgrindToHeatmap.LineCost(
                        trim(record.self_cost),
                        trim(record.calls_cost),
                        record.count,
                    )
                    for line, record in self.lines.items()
                },
                "lineFunction": self.line_function,
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

    class FunctionModel(TypedDict):
        name: str
        file: str
        line: int
        self: callgrind.Costs
        calls: callgrind.Costs
        callers: list[CallgrindToHeatmap.CallRow]

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

    @staticmethod
    def call_row_cost_key(row: CallgrindToHeatmap.CallRow) -> int:
        return -(row.cost[0] if row.cost else 0)

    def data_render(
        self, test_name: str, model: CallgrindToHeatmap.HeatModel
    ) -> str:
        data = json.dumps(model, separators=(",", ":"), ensure_ascii=False)
        models_global = f"window.{_HEAT_MAP_MODEL_GLOBAL_NAME}"
        return (
            f"{models_global} = {models_global} || {{}};\n"
            f"{models_global}[{json.dumps(test_name)}] = {data};\n"
        )

    def data_write(self, args: CallgrindToHeatmap.DataArgs) -> None:
        profile = callgrind.profile_load(args.callgrind_file)
        model, info = self.model(profile)
        if args.diff:
            self.diff_model(model, profile, args.baseline_data)
        self.sources_write(
            os.path.join(args.report_dir, _REPORT_SOURCES_DIR_NAME),
            info,
            model,
        )
        if args.test == _REPORT_TEST_SUITE_NAME:
            self.pulldown_text_write(args.report_dir, model)
        model_script = self.data_render(args.test, model)
        data_dir = os.path.join(
            args.report_dir,
            os.path.dirname(_HEAT_MAP_PAGE_PATH),
            _HEAT_MAP_MODEL_DIR_NAME,
        )
        os.makedirs(data_dir, exist_ok=True)
        path = os.path.join(data_dir, f"{args.test}.js")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(model_script)
        count = sum(
            1
            for entry in model["files"].values()
            if entry["source"] is not None
        )
        print(
            f"files with samples: {len(model['files'])}"
            f" ({count} with source shared),"
            f" cold files listed: {len(model['cold'])}, "
            f"functions: {len(model['functions'])}",
            file=sys.stderr,
        )
        print(
            f"wrote {path} ({len(model_script.encode('utf-8')):,} bytes)",
            file=sys.stderr,
        )

    def diff_model(
        self,
        model: CallgrindToHeatmap.HeatModel,
        profile: callgrind.LineProfile,
        baseline_data: str,
    ) -> None:
        if not baseline_data:
            sys.exit("error: --diff needs --baseline-data FILE")
        synthesized = callgrind_diff.callers_doc_load(baseline_data)
        totals = model["heatMapTotals"]
        totals["totals"] = callgrind_diff.profile_magnitudes(profile)
        totals["diff"] = True
        baseline = synthesized["baseline"]
        functions = model["functions"]
        model["functionBaseline"] = [
            baseline.get(func["name"], []) for func in functions
        ]
        model["fileBaseline"] = {
            path: costs
            for path, costs in synthesized["fileBaseline"].items()
            if path in model["files"]
        }
        for path, entry in model["files"].items():
            lines: dict[str, callgrind.Costs] = {}
            for line in entry["lines"]:
                costs = baseline.get(callgrind.baseline_line_key(path, line))
                if costs:
                    lines[line] = costs
            entry["baseline"] = lines

    def display_paths(
        self,
        profile: callgrind.Profile,
        raw_files: Sequence[str],
    ) -> dict[str, callgrind.PathInfo]:
        info: dict[str, callgrind.PathInfo] = {}
        for raw in raw_files:
            info[raw] = callgrind.path_norm(raw)._replace(
                display=callgrind.display_path_of(
                    raw, profile.file_ob.get(raw, "")
                )
            )
        return info

    def files_model(
        self,
        profile: callgrind.Profile,
        info: dict[str, callgrind.PathInfo],
        function_index: dict[str, int],
    ) -> dict[str, CallgrindToHeatmap.FileModel]:
        counter_count = len(profile.counters)
        display = {raw: path_info.display for raw, path_info in info.items()}
        accumulators: dict[str, CallgrindToHeatmap.FileTally] = {}
        for raw, path_info in info.items():
            entry = accumulators.get(path_info.display)
            if entry is None:
                entry = accumulators[path_info.display] = (
                    CallgrindToHeatmap.FileTally(
                        group=path_info.group,
                        raw=raw
                        if path_info.group == "external"
                        else path_info.display,
                        self_cost=[0] * counter_count,
                        calls_cost=[0] * counter_count,
                    )
                )
            if entry.source is None and path_info.local:
                entry.source = self.source_read(path_info.local)
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
        for key, function in profile.line_function.items():
            accumulators[display[key.file]].line_function[str(key.line)] = (
                function_index[function]
            )
        for site, tally in profile.callees.items():
            if site.callee not in profile.function_home:
                raise KeyError(
                    f"callee {site.callee!r} is missing from function_home"
                )
            entry_line = profile.function_entry.get(
                site.callee,
                callgrind.SourceLine(profile.function_home[site.callee], 0),
            )
            accumulators[display[site.file]].callees.setdefault(
                str(site.line), []
            ).append(
                CallgrindToHeatmap.CallRow(
                    function_index[site.callee],
                    display.get(entry_line.file, entry_line.file),
                    entry_line.line,
                    callgrind.costs_trim(tally.costs),
                    tally.count,
                )
            )
        return {name: entry.emit() for name, entry in accumulators.items()}

    def function_is_linkable(
        self,
        function: CallgrindToHeatmap.FunctionModel,
        files: dict[str, CallgrindToHeatmap.FileModel],
    ) -> bool:
        return bool(function["line"]) and function["file"] in files

    def functions_model(
        self,
        profile: callgrind.Profile,
        info: dict[str, callgrind.PathInfo],
        function_names: Sequence[str],
        function_index: dict[str, int],
    ) -> list[CallgrindToHeatmap.FunctionModel]:
        display = {raw: path_info.display for raw, path_info in info.items()}
        functions: list[CallgrindToHeatmap.FunctionModel] = []
        for name in function_names:
            entry = profile.function_entry.get(
                name, callgrind.SourceLine(profile.function_home[name], 0)
            )
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
                    "file": display.get(entry.file, entry.file),
                    "line": entry.line,
                    "self": callgrind.costs_trim(
                        profile.function_self.get(name, [])
                    ),
                    "calls": callgrind.costs_trim(
                        profile.function_calls.get(name, [])
                    ),
                    "callers": callers,
                }
            )
        return functions

    def model(
        self, profile: callgrind.Profile
    ) -> tuple[CallgrindToHeatmap.HeatModel, dict[str, callgrind.PathInfo]]:
        function_names = sorted(profile.function_home)
        function_index = {name: i for i, name in enumerate(function_names)}
        raw_files = sorted(
            {key.file for key in profile.line_self}
            | {key.file for key in profile.line_calls}
            | {entry.file for entry in profile.function_entry.values()}
        )
        info = self.display_paths(profile, raw_files)
        files = self.files_model(profile, info, function_index)
        functions = self.functions_model(
            profile, info, function_names, function_index
        )
        cold = sorted(
            relative
            for relative in self.repo_tracked_files()
            if relative not in files
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
            "cold": cold,
        }, info

    def page_render(self, source_names: Sequence[str]) -> str:
        assets_href = theme.href(_HEAT_MAP_PAGE_DEPTH, _REPORT_ASSETS_DIR_NAME)
        sources_href = theme.href(
            _HEAT_MAP_PAGE_DEPTH, _REPORT_SOURCES_DIR_NAME
        )
        scripts = theme.script_tags(sources_href, source_names)
        scripts += theme.script_tags(
            assets_href, (_ASSET_PULLDOWN_TEXT_SCRIPT_NAME,)
        )
        scripts += theme.held_script_tags(
            theme.script_tags(
                assets_href,
                (
                    _ASSET_DEBUG_SCRIPT_NAME,
                    _ASSET_THEME_SCRIPT_NAME,
                    _ASSET_HEAT_MAP_SCRIPT_NAME,
                ),
            )
        )
        return theme.page_document(
            "",
            theme.template_fill(
                BODY,
                {"__HEAT_MAP_MAIN__": _HEAT_MAP_MAIN, "__SCRIPTS__": scripts},
            ),
            depth=_HEAT_MAP_PAGE_DEPTH,
            extra_css=(
                _ASSET_MENU_STYLESHEET_NAME,
                _ASSET_HEAT_MAP_STYLESHEET_NAME,
            ),
            body_holds_scripts=True,
        )

    def page_write(self, report_dir: str) -> None:
        source_names = sorted(
            os.listdir(os.path.join(report_dir, _REPORT_SOURCES_DIR_NAME))
        )
        html = self.page_render(source_names)
        path = os.path.join(report_dir, _HEAT_MAP_PAGE_PATH)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(html)
        print(
            f"wrote {path} ({len(html.encode('utf-8')):,} bytes,"
            f" {len(source_names)} sources linked)",
            file=sys.stderr,
        )

    def pulldown_text_write(
        self, report_dir: str, model: CallgrindToHeatmap.HeatModel
    ) -> None:
        files = model["files"]
        names = {
            "files": sorted(files),
            "functions": [
                function["name"]
                for function in model["functions"]
                if self.function_is_linkable(function, files)
            ],
        }
        path = os.path.join(
            report_dir,
            _REPORT_ASSETS_DIR_NAME,
            _ASSET_PULLDOWN_TEXT_SCRIPT_NAME,
        )
        data = json.dumps(names, separators=(",", ":"), ensure_ascii=False)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f"window.report_pulldown_text_ = {data};\n")

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
            sys.exit(
                "error: cannot list the tracked files a cold tree needs:"
                f" exit {completed.returncode} from: {' '.join(command)}"
            )
        return [
            line
            for line in completed.stdout.split("\n")
            if line.endswith((".c", ".h"))
        ]

    @staticmethod
    def source_name(display: str) -> str:
        flat = "".join(char if char.isalnum() else "_" for char in display)
        return f"{flat}.js"

    def source_read(self, local: str) -> str | None:
        try:
            with open(local, "rb") as handle:
                data = handle.read()
        except OSError:
            return None
        return data.decode("utf-8", errors="replace")

    def sources_write(
        self,
        out_dir: str,
        info: dict[str, callgrind.PathInfo],
        model: CallgrindToHeatmap.HeatModel,
    ) -> None:
        shared = [
            (entry["source"], display)
            for display, entry in model["files"].items()
            if entry["source"] is not None
        ]
        names = dict(shared)
        if len(names) != len(shared):
            collided: dict[str, list[str]] = {}
            for name, display in shared:
                collided.setdefault(str(name), []).append(display)
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
        local_of = {
            path_info.display: path_info.local
            for path_info in info.values()
            if path_info.local
        }
        os.makedirs(out_dir, exist_ok=True)
        for name, display in sorted(names.items()):
            text = self.source_read(local_of[display])
            if text is None:
                raise RuntimeError(
                    f"source for {display!r} was readable earlier but"
                    " is not now"
                )
            body = json.dumps(text, ensure_ascii=False).replace("</", "<\\/")
            with open(
                os.path.join(out_dir, str(name)), "w", encoding="utf-8"
            ) as handle:
                handle.write(
                    "window.report_sources_ = window.report_sources_ || {};\n"
                    f"window.report_sources_[{json.dumps(display)}] ="
                    f" {body};\n"
                )


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
        "data", help="one test's model script and the sources it shows"
    )
    data_parser.add_argument(
        "callgrind_file",
        nargs="+",
        help="callgrind output file(s). several are merged into one profile",
    )
    data_parser.add_argument(
        "--report-dir",
        required=True,
        help="the report directory the script and sources are written in",
    )
    data_parser.add_argument(
        "--test",
        required=True,
        help="the test the model is filed under and its script named after",
    )
    data_parser.add_argument(
        "--diff",
        action="store_true",
        help="the callgrind file is a callgrind_diff.py delta: print "
        "signed numbers and take every share against what the same "
        "function or line cost in the baseline",
    )
    data_parser.add_argument(
        "--baseline-data",
        default="",
        metavar="FILE",
        help="callgrind_diff.py's synthesized callers diff, holding the "
        "baseline cost each share divides by (--diff only)",
    )

    page_parser = subparsers.add_parser(
        "page",
        help="the one heat map page, once every test's model script is"
        " written",
    )
    page_parser.add_argument(
        "--report-dir",
        required=True,
        help="the report directory the page is written in",
    )

    namespace = parser.parse_args()
    heat_map = CallgrindToHeatmap()
    if namespace.cmd == "page":
        heat_map.page_write(namespace.report_dir)
    else:
        heat_map.data_write(
            CallgrindToHeatmap.DataArgs(
                callgrind_file=namespace.callgrind_file,
                report_dir=namespace.report_dir,
                test=namespace.test,
                diff=namespace.diff,
                baseline_data=namespace.baseline_data,
            )
        )


if __name__ == "__main__":
    main()
