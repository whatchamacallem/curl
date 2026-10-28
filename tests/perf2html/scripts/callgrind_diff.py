#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, json, os, sys
from collections.abc import Sequence
from typing import NamedTuple, TextIO, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artifacts, callgrind


class CallChange(NamedTuple):
    function_index: int
    call_count: int
    baseline_count: int


# Holds a test's function data diff, each file and object by its list index.
class FunctionDiff(TypedDict):
    counters: list[str]
    objects: list[str]
    files: list[str]
    functions: list[FunctionDiffRow]


# Holds the function data diff beside the baseline costs of lines and files.
class FunctionDiffDocument(FunctionDiff):
    lineBaseline: dict[str, callgrind.Costs]
    fileBaseline: dict[str, callgrind.Costs]


# Holds a function's place, self change and baseline, callers and callees.
class FunctionDiffRow(NamedTuple):
    function_name: str
    object_index: int
    file_index: int
    line_number: int
    self_costs: callgrind.Costs
    baseline_costs: callgrind.Costs
    caller_rows: list[CallChange]
    callee_rows: list[CallChange]


class CallgrindDiff:
    class DiffArgs(NamedTuple):
        artifacts: str
        report: str
        verbose: int

    def __init__(self, args: CallgrindDiff.DiffArgs) -> None:
        self.verbose = args.verbose
        self.artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        self.baseline_dir = artifacts.artifact_path(
            self.artifacts_dir, "baseline-profiles"
        )
        self.modified_dir = artifacts.artifact_path(
            self.artifacts_dir, "modified-profiles"
        )
        self.derived = callgrind.DerivedPaths(
            self.baseline_dir, self.modified_dir
        )
        self.baseline_paths, self.modified_paths = (
            [entry.path for entry in callgrind.file_data_read(directory)]
            for directory in (self.baseline_dir, self.modified_dir)
        )
        self.build_trees = (
            artifacts.build_tree_read(self.artifacts_dir, "baseline-header"),
            artifacts.build_tree_read(self.artifacts_dir, "modified-header"),
        )

    def baseline_files(
        self, baseline: callgrind.LineProfile, objects: dict[str, str]
    ) -> dict[str, callgrind.Costs]:
        out: dict[str, callgrind.Costs] = {}
        for lines in baseline.function_lines.values():
            for key, costs in lines.items():
                display = self.display_path(key.file, objects)
                total = out.get(display)
                if total is None:
                    out[display] = list(costs)
                else:
                    callgrind.costs_add(total, costs)
        return {
            display: callgrind.costs_fit(costs, len(baseline.counters))
            for display, costs in out.items()
            if any(costs)
        }

    def baseline_key(
        self, key: callgrind.SourceLine, objects: dict[str, str]
    ) -> str:
        return callgrind.baseline_line_key(
            self.display_path(key.file, objects), key.line
        )

    # Returns the baseline costs of each line, keyed by its shown place.
    def baseline_lines(
        self, baseline: callgrind.LineProfile, objects: dict[str, str]
    ) -> dict[str, callgrind.Costs]:
        lines: dict[str, callgrind.Costs] = {}
        for key, costs in baseline.line_self.items():
            callgrind.costs_accumulate(
                lines, self.baseline_key(key, objects), costs
            )
        return {
            line_key: callgrind.costs_fit(costs, len(baseline.counters))
            for line_key, costs in lines.items()
            if any(costs)
        }

    def build(self) -> None:
        for test_name in artifacts.test_list_read(self.artifacts_dir):
            self.test_write(test_name)

    # Returns each call's change and baseline calls, by its function's index.
    @staticmethod
    def call_changes(
        baseline_counts: dict[str, int],
        modified_counts: dict[str, int],
        function_index: dict[str, int],
    ) -> list[CallChange]:
        return sorted(
            CallChange(
                function_index[name],
                modified_counts.get(name, 0) - baseline_counts.get(name, 0),
                baseline_counts.get(name, 0),
            )
            for name in baseline_counts.keys() | modified_counts.keys()
        )

    def counters_check(
        self,
        baseline: callgrind.LineProfile,
        modified: callgrind.LineProfile,
    ) -> None:
        if baseline.counters != modified.counters:
            sys.exit(
                "error: the two profiles record different counters: "
                f"{' '.join(baseline.counters)} vs "
                f"{' '.join(modified.counters)}"
            )
        for side, profile in (("baseline", baseline), ("modified", modified)):
            callgrind.ranking_counter_check(
                profile.counters, f"the {side} profile"
            )

    # Refuses a delta changing a function otherwise than its function data.
    def delta_check(
        self,
        delta: callgrind.LineProfile,
        function_diff: FunctionDiff,
        delta_path: str,
    ) -> None:
        changes = {
            row.function_name: callgrind.costs_trim(row.self_costs)
            for row in function_diff["functions"]
        }
        for function in sorted(changes.keys() | delta.function_self.keys()):
            delta_costs = callgrind.costs_trim(
                delta.function_self.get(function, [])
            )
            if changes.get(function) != delta_costs:
                sys.exit(
                    f"error: {delta_path} changes {function} by"
                    f" {delta_costs}, the function data by"
                    f" {changes.get(function)}"
                )

    # Returns the path the diff heat map shows, from the delta's objects.
    def display_path(self, file: str, objects: dict[str, str]) -> str:
        return self.derived.display(file, objects[file])

    # Returns every function two function data documents list, 0 changes kept.
    @staticmethod
    def function_diff(
        baseline: callgrind.FunctionDataDocument,
        modified: callgrind.FunctionDataDocument,
        baseline_paths: Sequence[str],
        modified_paths: Sequence[str],
        build_trees: tuple[str, str],
    ) -> FunctionDiff:
        if baseline["counters"] != modified["counters"]:
            sys.exit(
                "error: the two function data documents record different"
                f" counters: {' '.join(baseline['counters'])} vs"
                f" {' '.join(modified['counters'])}"
            )
        sides = (baseline, modified)
        baseline_keys, modified_keys = (
            [
                callgrind.FunctionKey(
                    document["objects"][row.object_index], row.function_name
                )
                for row in document["functions"]
            ]
            for document in sides
        )
        side_names = [
            [names[key] for key in keys]
            for keys, names in zip(
                (baseline_keys, modified_keys),
                callgrind.function_pair_names(
                    (baseline_keys, modified_keys), build_trees
                ),
                strict=True,
            )
        ]
        places: dict[str, tuple[str, str, int]] = {}
        self_costs: list[dict[str, callgrind.Costs]] = []
        caller_counts: list[dict[str, dict[str, int]]] = []
        callee_counts: list[dict[str, dict[str, int]]] = []
        # The modified side, read last, places a function both list.
        for document, names, paths in zip(
            sides, side_names, (baseline_paths, modified_paths), strict=True
        ):
            self_costs.append({})
            caller_counts.append({})
            callee_counts.append({})
            for row, name in zip(document["functions"], names, strict=True):
                places[name] = (
                    document["objects"][row.object_index],
                    paths[row.file_index],
                    row.line_number,
                )
                self_costs[-1][name] = row.self_costs
                caller_counts[-1][name] = {
                    names[call_row.function_index]: call_row.call_count
                    for call_row in row.caller_rows
                }
                callee_counts[-1][name] = {
                    names[call_row.function_index]: call_row.call_count
                    for call_row in row.callee_rows
                }
        function_names = sorted(places)
        function_index = {
            name: index for index, name in enumerate(function_names)
        }
        objects = sorted({place[0] for place in places.values()})
        object_index = {path: index for index, path in enumerate(objects)}
        files = sorted({place[1] for place in places.values()})
        file_index = {path: index for index, path in enumerate(files)}
        zeros = [0] * len(baseline["counters"])
        rows: list[FunctionDiffRow] = []
        for name in function_names:
            object_path, file_path, line_number = places[name]
            baseline_costs = self_costs[0].get(name, zeros)
            caller_rows, callee_rows = (
                CallgrindDiff.call_changes(
                    counts[0].get(name, {}),
                    counts[1].get(name, {}),
                    function_index,
                )
                for counts in (caller_counts, callee_counts)
            )
            rows.append(
                FunctionDiffRow(
                    name,
                    object_index[object_path],
                    file_index[file_path],
                    line_number,
                    callgrind.costs_sub(
                        self_costs[1].get(name, zeros), baseline_costs
                    ),
                    list(baseline_costs),
                    caller_rows,
                    callee_rows,
                )
            )
        return {
            "counters": list(baseline["counters"]),
            "objects": objects,
            "files": files,
            "functions": rows,
        }

    def subtract(
        self,
        baseline: callgrind.LineProfile,
        modified: callgrind.LineProfile,
    ) -> callgrind.LineProfile:
        self.counters_check(baseline, modified)
        diff = callgrind.LineProfile(
            counters=list(modified.counters),
            command=modified.command,
        )
        for function in sorted(
            set(baseline.function_lines) | set(modified.function_lines)
        ):
            before = baseline.function_lines.get(function, {})
            after = modified.function_lines.get(function, {})
            for key in sorted(set(before) | set(after)):
                costs = callgrind.costs_sub(
                    after.get(key, modified.zeros()),
                    before.get(key, baseline.zeros()),
                )
                if not any(costs):
                    continue
                diff.function_lines[function][key] = costs
                callgrind.costs_accumulate(diff.line_self, key, costs)
                callgrind.costs_accumulate(diff.function_self, function, costs)
        for source in (modified, baseline):
            for function, home in source.function_home.items():
                diff.function_home.setdefault(function, home)
            for file, ob in source.file_ob.items():
                diff.file_ob.setdefault(file, ob)
        diff.summary = diff.zeros()
        for costs in diff.line_self.values():
            callgrind.costs_add(diff.summary, costs)
        return diff

    # Writes one test's delta and function data diff, modified minus baseline.
    def test_write(self, test_name: str) -> None:
        baseline_path = artifacts.artifact_path(
            self.baseline_dir, "callgrind", test_name
        )
        modified_path = artifacts.artifact_path(
            self.modified_dir, "callgrind", test_name
        )
        delta_path = artifacts.artifact_path(
            self.artifacts_dir, "delta", test_name
        )
        function_diff_path = artifacts.artifact_path(
            self.artifacts_dir, "function-diff", test_name
        )
        baseline, modified = callgrind.profile_pair_load(
            self.baseline_dir, self.modified_dir, test_name, self.build_trees
        )
        diff = self.subtract(baseline, modified)
        if not any(diff.summary):
            sys.exit(
                "error: Report contains identical recordings."
                f" {baseline_path} vs {modified_path}"
            )
        self.write(
            diff,
            delta_path,
            [f"Baseline: {baseline_path}", f"Modified: {modified_path}"],
        )
        function_diff = self.function_diff(
            callgrind.function_data_read(self.baseline_dir, test_name),
            callgrind.function_data_read(self.modified_dir, test_name),
            self.baseline_paths,
            self.modified_paths,
            self.build_trees,
        )
        self.delta_check(diff, function_diff, delta_path)
        document: FunctionDiffDocument = {
            "counters": function_diff["counters"],
            "objects": function_diff["objects"],
            "files": function_diff["files"],
            "functions": function_diff["functions"],
            "lineBaseline": self.baseline_lines(baseline, diff.file_ob),
            "fileBaseline": self.baseline_files(baseline, diff.file_ob),
        }
        text = json.dumps(document, separators=(",", ":"), ensure_ascii=False)
        with open(function_diff_path, "w", encoding="utf-8") as handle:
            handle.write(f"{text}\n")
        if not self.verbose:
            return
        lines_changed = sum(
            1 for costs in diff.line_self.values() if any(costs)
        )
        changed = sum(1 for costs in diff.function_self.values() if any(costs))
        print(
            f"wrote {delta_path} ({os.path.getsize(delta_path):,} bytes): "
            f"{lines_changed:,} lines changed, {changed:,} functions"
            " changed in any recorded counter"
        )
        print(
            f"wrote {function_diff_path}"
            f" ({os.path.getsize(function_diff_path):,} bytes):"
            f" {len(function_diff['functions']):,} functions"
        )

    def write(
        self,
        profile: callgrind.LineProfile,
        path: str,
        descriptions: Sequence[str],
    ) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(
                "# callgrind format\nversion: 1\ncreator: callgrind_diff.py\n"
            )
            for description in descriptions:
                handle.write(
                    f"desc: {callgrind.repo_root_strip(description)}\n"
                )
            handle.write(
                f"cmd: {profile.command}\npositions: line\n"
                f"events: {' '.join(profile.counters)}\n"
            )
            handle.write(
                "summary: "
                + " ".join(str(value) for value in profile.totals())
                + "\n"
            )
            current_ob = ""
            for function in sorted(profile.function_lines):
                current_ob = self.write_function(
                    handle, profile, function, current_ob
                )

    @staticmethod
    def write_function(
        handle: TextIO,
        profile: callgrind.LineProfile,
        function: str,
        current_ob: str,
    ) -> str:
        home = profile.function_home[function]
        # The home opens the block, whether or not a changed line lies in it.
        by_file: dict[str, list[tuple[int, callgrind.Costs]]] = {home: []}
        for key, costs in profile.function_lines[function].items():
            by_file.setdefault(key.file, []).append((key.line, costs))
        handle.write("\n")
        for file in [home] + sorted(name for name in by_file if name != home):
            ob = profile.file_ob[file]
            if ob != current_ob:
                handle.write(f"ob={callgrind.repo_root_strip(ob)}\n")
                current_ob = ob
            handle.write(
                f"{'fl' if file == home else 'fi'}="
                f"{callgrind.repo_root_strip(file)}\n"
            )
            if file == home:
                handle.write(f"fn={function}\n")
            for line, costs in sorted(by_file[file]):
                handle.write(
                    f"{line} {' '.join(str(value) for value in costs)}\n"
                )
        return current_ob


# Returns a test's function data diff, refusing a document of other keys.
def function_diff_load(directory: str, test_name: str) -> FunctionDiffDocument:
    path = artifacts.artifact_path(directory, "function-diff", test_name)
    with artifacts.artifact_open(
        directory, "function-diff", test_name
    ) as handle:
        document = json.load(handle)
    keys = sorted(FunctionDiffDocument.__required_keys__)
    if sorted(document) != keys:
        sys.exit(
            f"error: {path} is not a function data diff: it holds the keys"
            f" {' '.join(sorted(document))}, expected {' '.join(keys)}"
        )
    document["functions"] = [
        FunctionDiffRow(
            function_name,
            object_index,
            file_index,
            line_number,
            self_costs,
            baseline_costs,
            [CallChange(*call_row) for call_row in caller_rows],
            [CallChange(*call_row) for call_row in callee_rows],
        )
        for (
            function_name,
            object_index,
            file_index,
            line_number,
            self_costs,
            baseline_costs,
            caller_rows,
            callee_rows,
        ) in document["functions"]
    ]
    return document


def profile_magnitudes(profile: callgrind.LineProfile) -> callgrind.Costs:
    total = profile.zeros()
    for lines in profile.function_lines.values():
        for costs in lines.values():
            callgrind.costs_add(total, [abs(value) for value in costs])
    return total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--artifacts",
        required=True,
        metavar="DIR",
        help="the profiler artifacts directory, holding the diff report's"
        " own, where each test's delta and callers diff are written",
    )
    parser.add_argument(
        "--report",
        required=True,
        metavar="DIR",
        help="the diff report directory, naming its artifacts directory",
    )
    parser.add_argument(
        "--verbose",
        action="count",
        default=0,
        help="print each file written; a quiet run prints nothing on success",
    )
    namespace = parser.parse_args()
    CallgrindDiff(
        CallgrindDiff.DiffArgs(
            artifacts=namespace.artifacts,
            report=namespace.report,
            verbose=namespace.verbose,
        )
    ).build()


if __name__ == "__main__":
    main()
