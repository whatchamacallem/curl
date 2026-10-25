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


class CallerDelta(NamedTuple):
    function: str
    count_: int
    baseline_count: int


class CallersDoc(TypedDict):
    counters: list[str]
    callers: dict[str, list[CallerDelta]]
    baseline: dict[str, callgrind.Costs]
    baselineCalls: dict[str, int]
    fileBaseline: dict[str, callgrind.Costs]


class CallgrindDiff:
    class DiffArgs(NamedTuple):
        artifacts: str
        report: str

    def __init__(self, args: CallgrindDiff.DiffArgs) -> None:
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

    def baseline_costs(
        self, baseline: callgrind.LineProfile, objects: dict[str, str]
    ) -> dict[str, callgrind.Costs]:
        out: dict[str, callgrind.Costs] = {}
        width = len(baseline.counters)
        for function, costs in baseline.function_self.items():
            if any(costs):
                out[function] = callgrind.costs_fit(costs, width)
        lines: dict[str, callgrind.Costs] = {}
        for key, costs in baseline.line_self.items():
            callgrind.costs_accumulate(
                lines, self.baseline_key(key, objects), costs
            )
        for line_key, costs in lines.items():
            if any(costs):
                out[line_key] = callgrind.costs_fit(costs, width)
        return out

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

    def build(self) -> None:
        for test_name in artifacts.test_list_read(self.artifacts_dir):
            self.test_write(test_name)

    # Keeps each callee with a changed caller, listing unchanged callers last.
    def callers_subtract(
        self,
        baseline: callgrind.Profile,
        modified: callgrind.Profile,
    ) -> dict[str, list[CallerDelta]]:
        out: dict[str, list[CallerDelta]] = {}
        uncalled = callgrind.CallerCalls(0, 0, [])
        for callee in sorted(set(baseline.callers) | set(modified.callers)):
            before = callgrind.caller_calls(baseline, callee)
            after = callgrind.caller_calls(modified, callee)
            deltas: list[CallerDelta] = []
            for caller_name in sorted(set(before) | set(after)):
                before_count = before.get(caller_name, uncalled).calls
                count = after.get(caller_name, uncalled).calls - before_count
                deltas.append(CallerDelta(caller_name, count, before_count))
            if any(delta.count_ for delta in deltas):
                deltas.sort(
                    key=lambda delta: (-abs(delta.count_), delta.function)
                )
                out[callee] = deltas
        return out

    def callers_write(
        self,
        callers: dict[str, list[CallerDelta]],
        path: str,
        baseline: callgrind.Profile,
        diff: callgrind.LineProfile,
    ) -> None:
        objects = diff.file_ob
        doc: CallersDoc = {
            "counters": list(baseline.counters),
            "callers": callers,
            "baseline": self.baseline_costs(baseline, objects),
            "baselineCalls": {
                callee: sum(tally.count for tally in tallies.values())
                for callee, tallies in baseline.callers.items()
            },
            "fileBaseline": self.baseline_files(baseline, objects),
        }
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(doc, handle)

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

    # Returns the path the diff heat map shows, from the delta's objects.
    def display_path(self, file: str, objects: dict[str, str]) -> str:
        entry = self.derived.path_entry(file)
        return callgrind.display_path(
            entry.canonical, entry.group, objects.get(file, "")
        )

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
            for function, entry in source.function_entry.items():
                diff.function_entry.setdefault(function, entry)
            for file, ob in source.file_ob.items():
                diff.file_ob.setdefault(file, ob)
        diff.summary = diff.zeros()
        for costs in diff.line_self.values():
            callgrind.costs_add(diff.summary, costs)
        return diff

    # Writes one test's delta and callers diff, modified minus baseline.
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
        callers_path = artifacts.artifact_path(
            self.artifacts_dir, "caller-counts", test_name
        )
        baseline = callgrind.profile_load(
            self.baseline_dir, "callgrind", test_name
        )
        modified = callgrind.profile_load(
            self.modified_dir, "callgrind", test_name
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
        lines_changed = sum(
            1 for costs in diff.line_self.values() if any(costs)
        )
        changed = sum(1 for costs in diff.function_self.values() if any(costs))
        print(
            f"wrote {delta_path} ({os.path.getsize(delta_path):,} bytes): "
            f"{lines_changed:,} lines changed, {changed:,} functions"
            " changed in any recorded counter",
            file=sys.stderr,
        )
        callers = self.callers_subtract(baseline, modified)
        self.callers_write(callers, callers_path, baseline, diff)
        print(
            f"wrote {callers_path} "
            f"({os.path.getsize(callers_path):,} bytes): "
            f"{len(callers):,} function(s) with a caller change",
            file=sys.stderr,
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

    def write_function(
        self,
        handle: TextIO,
        profile: callgrind.LineProfile,
        function: str,
        current_ob: str,
    ) -> str:
        by_file: dict[str, list[tuple[int, callgrind.Costs]]] = {}
        for key, costs in profile.function_lines[function].items():
            by_file.setdefault(key.file, []).append((key.line, costs))
        home = profile.function_home.get(function, "")
        if home not in by_file:
            home = max(
                by_file,
                key=lambda name: (
                    sum(
                        abs(value)
                        for _, costs in by_file[name]
                        for value in costs
                    ),
                    name,
                ),
            )
        entry = profile.function_entry.get(function)
        handle.write("\n")
        for file in [home] + sorted(name for name in by_file if name != home):
            ob = profile.file_ob.get(file, "")
            if ob and ob != current_ob:
                handle.write(f"ob={callgrind.repo_root_strip(ob)}\n")
                current_ob = ob
            handle.write(
                f"{'fl' if file == home else 'fi'}="
                f"{callgrind.repo_root_strip(file)}\n"
            )
            ordered = sorted(by_file[file])
            if file == home:
                handle.write(f"fn={function}\n")
                if entry is not None and entry.file == home and entry.line:
                    ordered = [
                        pair for pair in ordered if pair[0] == entry.line
                    ] + [pair for pair in ordered if pair[0] != entry.line]
            for line, costs in ordered:
                handle.write(
                    f"{line} {' '.join(str(value) for value in costs)}\n"
                )
        return current_ob


def callers_doc_load(directory: str, test_name: str) -> CallersDoc:
    with artifacts.artifact_open(
        directory, "caller-counts", test_name
    ) as handle:
        doc = json.load(handle)
    for key in (
        "counters",
        "callers",
        "baseline",
        "baselineCalls",
        "fileBaseline",
    ):
        if key not in doc:
            path = artifacts.artifact_path(
                directory, "caller-counts", test_name
            )
            sys.exit(
                f"error: {path} is not a synthesized callers diff:"
                f" the {key!r} key is missing"
            )
    doc["callers"] = {
        callee: [CallerDelta(*row) for row in rows]
        for callee, rows in doc["callers"].items()
    }
    return doc


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
    namespace = parser.parse_args()
    CallgrindDiff(
        CallgrindDiff.DiffArgs(
            artifacts=namespace.artifacts, report=namespace.report
        )
    ).build()


if __name__ == "__main__":
    main()
