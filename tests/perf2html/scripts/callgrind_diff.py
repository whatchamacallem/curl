#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, json, os, sys
from collections.abc import Sequence
from typing import NamedTuple, TextIO, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind


class CallerDelta(NamedTuple):
    function: str
    count_: int
    baseline_count: int


class CallersDoc(TypedDict):
    counters: list[str]
    callers: dict[str, list[CallerDelta]]
    baseline: dict[str, callgrind.Costs]
    baselineTotal: callgrind.Costs
    baselineCalls: dict[str, int]
    fileBaseline: dict[str, callgrind.Costs]


class CallgrindDiff:
    class DiffArgs(NamedTuple):
        baseline: list[str]
        modified: list[str]
        output: str
        callers_output: str

    def baseline_costs(
        self, baseline: callgrind.LineProfile
    ) -> dict[str, callgrind.Costs]:
        out: dict[str, callgrind.Costs] = {}
        width = len(baseline.counters)
        for function, costs in baseline.function_self.items():
            if any(costs):
                out[function] = callgrind.costs_fit(costs, width)
        lines: dict[str, callgrind.Costs] = {}
        for key, costs in baseline.line_self.items():
            callgrind.costs_accumulate(
                lines, self.baseline_key(baseline, key), costs
            )
        for line_key, costs in lines.items():
            if any(costs):
                out[line_key] = callgrind.costs_fit(costs, width)
        return out

    def baseline_files(
        self, baseline: callgrind.LineProfile
    ) -> dict[str, callgrind.Costs]:
        out: dict[str, callgrind.Costs] = {}
        for lines in baseline.function_lines.values():
            for key, costs in lines.items():
                display = self.display_path_of(baseline, key.file)
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
        self,
        baseline: callgrind.LineProfile,
        key: callgrind.SourceLine,
    ) -> str:
        return callgrind.baseline_line_key(
            self.display_path_of(baseline, key.file), key.line
        )

    def build(self, args: CallgrindDiff.DiffArgs) -> None:
        baseline = callgrind.profile_load(args.baseline)
        modified = callgrind.profile_load(args.modified)
        diff = self.subtract(baseline, modified)
        self.write(
            diff,
            args.output,
            [
                f"Baseline: {' '.join(args.baseline)}",
                f"Modified: {' '.join(args.modified)}",
            ],
        )
        lines_changed = sum(
            1 for costs in diff.line_self.values() if any(costs)
        )
        changed = sum(1 for costs in diff.function_self.values() if any(costs))
        print(
            f"wrote {args.output} ({os.path.getsize(args.output):,} bytes): "
            f"{lines_changed:,} lines changed, {changed:,} functions"
            " changed in any recorded counter",
            file=sys.stderr,
        )
        callers = self.callers_subtract(baseline, modified)
        self.callers_write(callers, args.callers_output, baseline)
        print(
            f"wrote {args.callers_output} "
            f"({os.path.getsize(args.callers_output):,} bytes): "
            f"{len(callers):,} function(s) with a caller change",
            file=sys.stderr,
        )

    def caller_tallies(
        self, profile: callgrind.Profile, callee: str
    ) -> dict[str, int]:
        out: dict[str, int] = {}
        for caller, tally in profile.callers.get(callee, {}).items():
            out[caller.function] = out.get(caller.function, 0) + tally.count
        return out

    def callers_subtract(
        self,
        baseline: callgrind.Profile,
        modified: callgrind.Profile,
    ) -> dict[str, list[CallerDelta]]:
        out: dict[str, list[CallerDelta]] = {}
        for callee in sorted(set(baseline.callers) | set(modified.callers)):
            before = self.caller_tallies(baseline, callee)
            after = self.caller_tallies(modified, callee)
            deltas: list[CallerDelta] = []
            for caller_name in sorted(set(before) | set(after)):
                before_count = before.get(caller_name, 0)
                count = after.get(caller_name, 0) - before_count
                if count:
                    deltas.append(
                        CallerDelta(caller_name, count, before_count)
                    )
            if deltas:
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
    ) -> None:
        doc: CallersDoc = {
            "counters": list(baseline.counters),
            "callers": callers,
            "baseline": self.baseline_costs(baseline),
            "baselineTotal": callgrind.costs_fit(
                baseline.totals(), len(baseline.counters)
            ),
            "baselineCalls": {
                callee: sum(tally.count for tally in tallies.values())
                for callee, tallies in baseline.callers.items()
            },
            "fileBaseline": self.baseline_files(baseline),
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

    def display_path_of(
        self, profile: callgrind.LineProfile, file: str
    ) -> str:
        return callgrind.display_path_of(file, profile.file_ob.get(file, ""))

    def path_strip(self, name: str) -> str:
        return name.replace(callgrind.REPO_ROOT + "/", "")

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
                diff.line_function.setdefault(key, function)
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
                handle.write(f"desc: {self.path_strip(description)}\n")
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
                handle.write(f"ob={self.path_strip(ob)}\n")
                current_ob = ob
            handle.write(
                f"{'fl' if file == home else 'fi'}={self.path_strip(file)}\n"
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


def callers_doc_load(path: str) -> CallersDoc:
    try:
        with open(path, encoding="utf-8") as handle:
            doc = json.load(handle)
    except OSError as error:
        sys.exit(
            f"error: {path}: {error}: the synthesized callers diff"
            " cannot be read"
        )
    for key in (
        "counters",
        "callers",
        "baseline",
        "baselineTotal",
        "baselineCalls",
        "fileBaseline",
    ):
        if key not in doc:
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
        "--baseline",
        action="append",
        required=True,
        metavar="FILE",
        help="the 'before' callgrind file (repeatable; several are merged)",
    )
    parser.add_argument(
        "--current",
        dest="modified",
        action="append",
        required=True,
        metavar="FILE",
        help="the 'after' callgrind file (repeatable; several are merged)",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="the callgrind-format delta file to write",
    )
    parser.add_argument(
        "--callers-output",
        required=True,
        metavar="FILE",
        help="the JSON file of per-function caller deltas to write",
    )
    namespace = parser.parse_args()
    CallgrindDiff().build(
        CallgrindDiff.DiffArgs(
            baseline=namespace.baseline,
            modified=namespace.modified,
            output=namespace.output,
            callers_output=namespace.callers_output,
        )
    )


if __name__ == "__main__":
    main()
