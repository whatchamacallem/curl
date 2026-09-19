#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Sequence
import json
import os
import sys
from typing import NamedTuple, TextIO, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind
from callgrind import Costs

EVENT = "Ir"


class CallerDelta(NamedTuple):
    function: str
    count_: int
    cost: int


class CallersDoc(TypedDict):
    event: str
    callers: dict[str, list[list[object]]]


class DiffArgs(NamedTuple):
    baseline: list[str]
    modified: list[str]
    output: str
    callers_output: str
    event: str


class CallgrindDiff:
    def build(self, args: DiffArgs) -> None:
        baseline = callgrind.profile_load(args.baseline)
        modified = callgrind.profile_load(args.modified)
        diff = self.subtract(baseline, modified)
        self.write(diff, args.output,
                   [f"Baseline: {' '.join(args.baseline)}", f"Modified: {' '.join(args.modified)}"])
        changed = sum(1 for costs in diff.function_self.values() if any(costs))
        print(f"wrote {args.output} ({os.path.getsize(args.output):,} bytes): "
              f"{len(diff.line_self):,} lines in {changed:,} functions changed", file=sys.stderr)
        callers = self.callers_subtract(baseline, modified, args.event)
        self.callers_write(callers, args.callers_output, args.event)
        print(f"wrote {args.callers_output} ({os.path.getsize(args.callers_output):,} bytes): "
              f"{len(callers):,} function(s) with a caller change", file=sys.stderr)

    def callers_subtract(self, baseline: callgrind.Profile, modified: callgrind.Profile,
                         event: str) -> dict[str, list[CallerDelta]]:
        out: dict[str, list[CallerDelta]] = {}
        for callee in sorted(set(baseline.callers) | set(modified.callers)):
            before = {caller.function: tally for caller, tally in baseline.callers.get(callee, {}).items()}
            after = {caller.function: tally for caller, tally in modified.callers.get(callee, {}).items()}
            deltas: list[CallerDelta] = []
            for caller_name in sorted(set(before) | set(after)):
                before_tally = before.get(caller_name)
                after_tally = after.get(caller_name)
                count = (after_tally.count if after_tally else 0) - (before_tally.count if before_tally else 0)
                cost = modified.value(after_tally.costs, event) if after_tally else 0
                cost -= baseline.value(before_tally.costs, event) if before_tally else 0
                if count or cost:
                    deltas.append(CallerDelta(caller_name, count, cost))
            if deltas:
                deltas.sort(key=lambda delta: (-abs(delta.cost), -abs(delta.count_), delta.function))
                out[callee] = deltas
        return out

    def callers_write(self, callers: dict[str, list[CallerDelta]], path: str, event: str) -> None:
        doc: CallersDoc = {"event": event,
                           "callers": {callee: [[delta.function, delta.count_, delta.cost] for delta in deltas]
                                       for callee, deltas in callers.items()}}
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(doc, handle)

    def costs_sub(self, modified: Costs, baseline: Costs) -> Costs:
        return [(modified[index] if index < len(modified) else 0) - (baseline[index] if index < len(baseline) else 0)
                for index in range(max(len(modified), len(baseline)))]

    def magnitudes(self, profile: callgrind.Profile) -> Costs:
        total = profile.zeros()
        for lines in profile.function_lines.values():
            for costs in lines.values():
                callgrind.costs_add(total, [abs(value) for value in costs])
        return total

    def path_strip(self, name: str) -> str:
        return name.replace(callgrind.REPO_ROOT + "/", "")

    def subtract(self, baseline: callgrind.Profile, modified: callgrind.Profile) -> callgrind.Profile:
        if baseline.events != modified.events:
            sys.exit(f"error: the two profiles record different events: "
                     f"{' '.join(baseline.events)} vs {' '.join(modified.events)}")
        diff = callgrind.Profile(events=list(modified.events), event_long=dict(modified.event_long),
                                 command=modified.command)
        for function in sorted(set(baseline.function_lines) | set(modified.function_lines)):
            before = baseline.function_lines.get(function, {})
            after = modified.function_lines.get(function, {})
            for key in sorted(set(before) | set(after)):
                costs = self.costs_sub(after.get(key, modified.zeros()), before.get(key, baseline.zeros()))
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

    def write(self, profile: callgrind.Profile, path: str, descriptions: Sequence[str]) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("# callgrind format\nversion: 1\ncreator: callgrind_diff.py\n")
            for description in descriptions:
                handle.write(f"desc: {self.path_strip(description)}\n")
            handle.write(f"cmd: {profile.command}\npositions: line\nevents: {' '.join(profile.events)}\n")
            handle.write("summary: " + " ".join(str(value) for value in profile.totals()) + "\n")
            current_ob = ""
            for function in sorted(profile.function_lines):
                current_ob = self.write_function(handle, profile, function, current_ob)

    def write_function(self, handle: TextIO, profile: callgrind.Profile, function: str, current_ob: str) -> str:
        by_file: dict[str, list[tuple[int, Costs]]] = {}
        for key, costs in profile.function_lines[function].items():
            by_file.setdefault(key.file, []).append((key.line, costs))
        home = profile.function_home.get(function, "")
        if home not in by_file:
            home = sorted(by_file)[0]
        entry = profile.function_entry.get(function)
        handle.write("\n")
        for file in [home] + sorted(name for name in by_file if name != home):
            ob = profile.file_ob.get(file, "")
            if ob and ob != current_ob:
                handle.write(f"ob={self.path_strip(ob)}\n")
                current_ob = ob
            handle.write(f"{'fl' if file == home else 'fi'}={self.path_strip(file)}\n")
            ordered = sorted(by_file[file])
            if file == home:
                handle.write(f"fn={function}\n")
                if entry is not None and entry.file == home and entry.line:
                    first = [pair for pair in ordered if pair[0] == entry.line] or [(entry.line, profile.zeros())]
                    ordered = first + [pair for pair in ordered if pair[0] != entry.line]
            for line, costs in ordered:
                handle.write(f"{line} {' '.join(str(value) for value in costs)}\n")
        return current_ob


def profile_magnitudes(profile: callgrind.Profile) -> Costs:
    return CallgrindDiff().magnitudes(profile)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="append", required=True, metavar="FILE",
                        help="the 'before' callgrind file (repeatable; several are merged)")
    parser.add_argument("--current", dest="modified", action="append", required=True, metavar="FILE",
                        help="the 'after' callgrind file (repeatable; several are merged)")
    parser.add_argument("-o", "--output", required=True, help="the callgrind-format delta file to write")
    parser.add_argument("--callers-output", required=True, metavar="FILE",
                        help="the JSON file of per-function caller deltas to write")
    namespace = parser.parse_args()
    CallgrindDiff().build(DiffArgs(baseline=namespace.baseline, modified=namespace.modified,
                                   output=namespace.output, callers_output=namespace.callers_output, event=EVENT))


if __name__ == "__main__":
    main()
