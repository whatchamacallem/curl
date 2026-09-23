#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, os, sys
from collections.abc import Sequence
from typing import NamedTuple, TextIO, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind, settings

# All constants needed from settings.py have to be loaded here before anything
# else.
_RANKING_COUNTER_NAME: str = ""
settings.load_into(__name__)


# CallgrindDiff - Subtracts one profile from another, per (function, file,
# line), and writes the result back out as a plain callgrind file.
class CallgrindDiff:
    # CallerDelta - How one caller's calls into one callee changed.
    class CallerDelta(NamedTuple):
        # who does the calling
        function: str
        # how many more (or fewer) times it called
        count_: int
        # how much more (or less) those calls cost
        cost: int

    # CallersDoc - The synthesized callers diff, because a delta file has no
    # calls= lines and so no call graph, and no baseline to be a share of.
    class CallersDoc(TypedDict):
        # the recorded counters the baseline vectors are written against, so
        # a reader can resolve any counter, derived ones included, from them
        counters: list[str]
        # per callee, its changed callers as [name, count, cost] rows
        callers: dict[str, list[list[object]]]
        # what every share divides by: the baseline cost vector per
        # "<function>" and per "<function>\n<file>\n<line>"
        baseline: dict[str, callgrind.Costs]
        # the baseline's summed cost vector, the overview's denominator
        baselineTotal: callgrind.Costs
        # per callee, how many times the baseline called it
        baselineCalls: dict[str, int]
        # per display path, the whole file's baseline cost vector, which file
        # and directory shares divide by -- not the changed lines alone
        fileBaseline: dict[str, callgrind.Costs]

    # DiffArgs - The two sides to subtract, and the two files to write.
    class DiffArgs(NamedTuple):
        # the "before" callgrind files, merged
        baseline: list[str]
        # the "after" callgrind files, merged
        modified: list[str]
        # where the delta callgrind file goes
        output: str
        # where the synthesized callers diff goes
        callers_output: str

    # Baseline cost per function and per line -- what each share divides by,
    # keyed as the subtraction is so an inlined body stays off its neighbour.
    def baseline_costs(
        self, baseline: callgrind.Profile
    ) -> dict[str, callgrind.Costs]:
        out: dict[str, callgrind.Costs] = {}
        for function, costs in baseline.function_self.items():
            if any(costs):
                out[function] = self.costs_fit(baseline, costs)
        for function, lines in baseline.function_lines.items():
            for key, costs in lines.items():
                if any(costs):
                    out[self.baseline_key(baseline, function, key)] = (
                        self.costs_fit(baseline, costs)
                    )
        return out

    # Baseline cost per display path -- the whole file's, not the changed
    # lines', which is what a tree's file and directory shares divide by.
    def baseline_files(
        self, baseline: callgrind.Profile
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
            display: self.costs_fit(baseline, costs)
            for display, costs in out.items()
            if any(costs)
        }

    # How the page spells one line's baseline slot -- the display path the
    # heat map keys its files by, through the one door.
    def baseline_key(
        self,
        baseline: callgrind.Profile,
        function: str,
        key: callgrind.SourceLine,
    ) -> str:
        return callgrind.baseline_line_key(
            function, self.display_path_of(baseline, key.file), key.line
        )

    # Read both sides, write the delta, then the synthesized callers diff.
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
        changed = sum(1 for costs in diff.function_self.values() if any(costs))
        print(
            f"wrote {args.output} ({os.path.getsize(args.output):,} bytes): "
            f"{len(diff.line_self):,} lines in {changed:,} functions changed",
            file=sys.stderr,
        )
        callers = self.callers_subtract(
            baseline, modified, _RANKING_COUNTER_NAME
        )
        self.callers_write(callers, args.callers_output, baseline)
        print(
            f"wrote {args.callers_output} "
            f"({os.path.getsize(args.callers_output):,} bytes): "
            f"{len(callers):,} function(s) with a caller change",
            file=sys.stderr,
        )

    # One callee's callers, summed per calling function: a caller calling
    # from several lines is several keys, and one of them is a fraction.
    def caller_tallies(
        self, profile: callgrind.Profile, callee: str, counter: str
    ) -> dict[str, tuple[int, int]]:
        out: dict[str, tuple[int, int]] = {}
        for caller, tally in profile.callers.get(callee, {}).items():
            count, cost = out.get(caller.function, (0, 0))
            out[caller.function] = (
                count + tally.count,
                cost + profile.value(tally.costs, counter),
            )
        return out

    # Per callee, which of its callers changed, biggest cost change first.
    def callers_subtract(
        self,
        baseline: callgrind.Profile,
        modified: callgrind.Profile,
        counter: str,
    ) -> dict[str, list[CallgrindDiff.CallerDelta]]:
        out: dict[str, list[CallgrindDiff.CallerDelta]] = {}
        for callee in sorted(set(baseline.callers) | set(modified.callers)):
            before = self.caller_tallies(baseline, callee, counter)
            after = self.caller_tallies(modified, callee, counter)
            deltas: list[CallgrindDiff.CallerDelta] = []
            for caller_name in sorted(set(before) | set(after)):
                before_count, before_cost = before.get(caller_name, (0, 0))
                after_count, after_cost = after.get(caller_name, (0, 0))
                count = after_count - before_count
                cost = after_cost - before_cost
                if count or cost:
                    deltas.append(
                        CallgrindDiff.CallerDelta(caller_name, count, cost)
                    )
            if deltas:
                deltas.sort(
                    key=lambda delta: (
                        -abs(delta.cost),
                        -abs(delta.count_),
                        delta.function,
                    )
                )
                out[callee] = deltas
        return out

    # Write the synthesized callers diff, as rows rather than objects to keep
    # it small.
    def callers_write(
        self,
        callers: dict[str, list[CallgrindDiff.CallerDelta]],
        path: str,
        baseline: callgrind.Profile,
    ) -> None:
        doc: CallgrindDiff.CallersDoc = {
            "counters": list(baseline.counters),
            "callers": {
                callee: [
                    [delta.function, delta.count_, delta.cost]
                    for delta in deltas
                ]
                for callee, deltas in callers.items()
            },
            "baseline": self.baseline_costs(baseline),
            "baselineTotal": self.costs_fit(baseline, baseline.totals()),
            "baselineCalls": {
                callee: sum(tally.count for tally in tallies.values())
                for callee, tallies in baseline.callers.items()
            },
            "fileBaseline": self.baseline_files(baseline),
        }
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(doc, handle)

    # Pad to the full recorded width so a slot's index never moves, then trim
    # trailing zeros. Stores no derived slot -- those are a function of these.
    def costs_fit(
        self, profile: callgrind.Profile, costs: callgrind.Costs
    ) -> callgrind.Costs:
        padded = list(costs) + [0] * (len(profile.counters) - len(costs))
        return self.costs_trim(padded)

    # Subtract two cost vectors, treating a missing slot as zero.
    def costs_sub(
        self, modified: callgrind.Costs, baseline: callgrind.Costs
    ) -> callgrind.Costs:
        return [
            (modified[index] if index < len(modified) else 0)
            - (baseline[index] if index < len(baseline) else 0)
            for index in range(max(len(modified), len(baseline)))
        ]

    # Drop trailing zeros -- the synthesized callers diff carries one vector
    # per line, so the slots nothing would divide by are not worth the bytes.
    def costs_trim(self, costs: callgrind.Costs) -> callgrind.Costs:
        length = len(costs)
        while length and costs[length - 1] == 0:
            length -= 1
        return costs[:length]

    # Refuse two sides recording different counters, or either unable to
    # supply the ranking counter -- never quietly substitute another.
    def counters_check(
        self, baseline: callgrind.Profile, modified: callgrind.Profile
    ) -> None:
        if baseline.counters != modified.counters:
            sys.exit(
                "error: the two profiles record different counters: "
                f"{' '.join(baseline.counters)} vs "
                f"{' '.join(modified.counters)}"
            )
        for side, profile in (("baseline", baseline), ("modified", modified)):
            if _RANKING_COUNTER_NAME not in profile.counter_names():
                sys.exit(
                    f"error: the {side} profile cannot supply"
                    f" {_RANKING_COUNTER_NAME}, the counter every diff share"
                    f" is counted in: it records"
                    f" {' '.join(profile.counters)}"
                )

    # A path as the page prints it, external files qualified by their
    # object, through the one door the page reads it back with.
    def display_path_of(self, profile: callgrind.Profile, file: str) -> str:
        return callgrind.display_path_of(file, profile.file_ob.get(file, ""))

    # Sum of every line delta's absolute value -- what a diff's shares divide
    # by, since the signed total is near zero.
    def magnitudes(self, profile: callgrind.Profile) -> callgrind.Costs:
        total = profile.zeros()
        for lines in profile.function_lines.values():
            for costs in lines.values():
                callgrind.costs_add(total, [abs(value) for value in costs])
        return total

    # Drop the checkout prefix, so the written file is copyable off-box.
    def path_strip(self, name: str) -> str:
        return name.replace(callgrind.REPO_ROOT + "/", "")

    # MODIFIED - BASELINE per (function, file, line) -- never per (file, line)
    # alone, which would hand an inlined function's cost to its neighbour.
    def subtract(
        self, baseline: callgrind.Profile, modified: callgrind.Profile
    ) -> callgrind.Profile:
        self.counters_check(baseline, modified)
        diff = callgrind.Profile(
            counters=list(modified.counters),
            command=modified.command,
        )
        for function in sorted(
            set(baseline.function_lines) | set(modified.function_lines)
        ):
            before = baseline.function_lines.get(function, {})
            after = modified.function_lines.get(function, {})
            for key in sorted(set(before) | set(after)):
                costs = self.costs_sub(
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

    # Write the delta as a callgrind file -- no calls= lines, so nothing
    # downstream believes it has a call graph.
    def write(
        self,
        profile: callgrind.Profile,
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

    # Write one function's lines, home file first, entry line first inside it.
    def write_function(
        self,
        handle: TextIO,
        profile: callgrind.Profile,
        function: str,
        current_ob: str,
    ) -> str:
        by_file: dict[str, list[tuple[int, callgrind.Costs]]] = {}
        for key, costs in profile.function_lines[function].items():
            by_file.setdefault(key.file, []).append((key.line, costs))
        home = profile.function_home.get(function, "")
        if home not in by_file:
            # its recorded home holds no changed line, so the file with most
            # of the change wins: sort order would move it where nothing did
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
                    # the entry line leads only when it changed: a zero row
                    # is a cost nothing measured, and every row is recorded
                    ordered = [
                        pair for pair in ordered if pair[0] == entry.line
                    ] + [pair for pair in ordered if pair[0] != entry.line]
            for line, costs in ordered:
                handle.write(
                    f"{line} {' '.join(str(value) for value in costs)}\n"
                )
        return current_ob


# profile_magnitudes - Sum of every line delta's absolute value -- the
# denominator a diff's shares use.
def profile_magnitudes(profile: callgrind.Profile) -> callgrind.Costs:
    return CallgrindDiff().magnitudes(profile)


# main - Subtract the two given sides and write both output files.
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
