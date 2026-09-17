#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Sequence
import os
import sys
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind
from callgrind import Costs

BASELINE_TOTALS = "Baseline totals:"


class DiffArgs(NamedTuple):
    baseline: list[str]
    current: list[str]
    output: str
    repo_root: str


def costs_sub(current: Costs, baseline: Costs) -> Costs:
    return [(current[index] if index < len(current) else 0) - (baseline[index] if index < len(baseline) else 0)
            for index in range(max(len(current), len(baseline)))]


def profile_baseline_total(profile: callgrind.Profile, event: str) -> int:
    for description in profile.descriptions:
        if not description.startswith(BASELINE_TOTALS):
            continue
        fields = description[len(BASELINE_TOTALS):].split()
        totals = {name: int(value) for name, value in zip(fields[0::2], fields[1::2])}
        try:
            return profile.value([totals.get(name, 0) for name in profile.events], event)
        except KeyError:
            return 0
    return 0


def profile_diff(baseline: callgrind.Profile, current: callgrind.Profile) -> callgrind.Profile:
    if baseline.events != current.events:
        sys.exit(f"error: the two profiles record different events: "
                 f"{' '.join(baseline.events)} vs {' '.join(current.events)}")
    diff = callgrind.Profile(events=list(current.events), event_long=dict(current.event_long),
                             derived=list(current.derived), command=current.command)
    for function in sorted(set(baseline.function_lines) | set(current.function_lines)):
        before = baseline.function_lines.get(function, {})
        after = current.function_lines.get(function, {})
        for key in sorted(set(before) | set(after)):
            costs = costs_sub(after.get(key, current.zeros()), before.get(key, baseline.zeros()))
            if not any(costs):
                continue
            diff.function_lines[function][key] = costs
            diff.line_function.setdefault(key, function)
            callgrind.costs_accumulate(diff.line_self, key, costs)
            callgrind.costs_accumulate(diff.function_self, function, costs)
    for source in (current, baseline):
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


def profile_magnitudes(profile: callgrind.Profile) -> Costs:
    total = profile.zeros()
    for lines in profile.function_lines.values():
        for costs in lines.values():
            callgrind.costs_add(total, [abs(value) for value in costs])
    return total


def profile_read(paths: Sequence[str]) -> callgrind.Profile:
    profile = callgrind.profile_load(paths)
    if not profile.events:
        sys.exit(f"error: no 'events:' line -- not a callgrind file? ({paths[0]})")
    balance = callgrind.profile_self_check(profile)
    print(f"ratio (must be 1.0000): {balance.ratio:.4f}  {os.path.basename(paths[0])}", file=sys.stderr)
    if balance.total and abs(balance.ratio - 1.0) > 1e-6:
        sys.exit("error: per-line self cost does not add up to callgrind's summary")
    return profile


def profile_write(profile: callgrind.Profile, path: str, descriptions: Sequence[str], repo_root: str) -> None:
    root = os.path.abspath(repo_root).rstrip("/") + "/"

    def strip(name: str) -> str:
        return name.replace(root, "")

    def costs_line(line: int, costs: Costs) -> str:
        return f"{line} {' '.join(str(value) for value in costs)}\n"

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("# callgrind format\nversion: 1\ncreator: callgrind_diff.py\n")
        for description in descriptions:
            handle.write(f"desc: {strip(description)}\n")
        handle.write(f"cmd: {profile.command}\npositions: line\nevents: {' '.join(profile.events)}\n")
        handle.write("summary: " + " ".join(str(value) for value in profile.totals()) + "\n")
        current_ob = ""
        for function in sorted(profile.function_lines):
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
                    handle.write(f"ob={strip(ob)}\n")
                    current_ob = ob
                handle.write(f"{'fl' if file == home else 'fi'}={strip(file)}\n")
                ordered = sorted(by_file[file])
                if file == home:
                    handle.write(f"fn={function}\n")
                    if entry is not None and entry.file == home and entry.line:
                        first = [pair for pair in ordered if pair[0] == entry.line] or [(entry.line, profile.zeros())]
                        ordered = first + [pair for pair in ordered if pair[0] != entry.line]
                for line, costs in ordered:
                    handle.write(costs_line(line, costs))


def diff_build(args: DiffArgs) -> None:
    baseline = profile_read(args.baseline)
    current = profile_read(args.current)
    diff = profile_diff(baseline, current)
    descriptions = [f"Baseline: {', '.join(args.baseline)}", f"Current: {', '.join(args.current)}",
                    BASELINE_TOTALS + " " + " ".join(f"{name} {value}" for name, value
                                                     in zip(baseline.events, baseline.totals()))]
    profile_write(diff, args.output, descriptions, args.repo_root)
    changed = sum(1 for costs in diff.function_self.values() if any(costs))
    print(f"wrote {args.output} ({os.path.getsize(args.output):,} bytes): "
          f"{len(diff.line_self):,} lines in {changed:,} functions changed", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--baseline", action="append", required=True, metavar="FILE",
                        help="the 'before' callgrind file (repeatable; several are merged first)")
    parser.add_argument("--current", action="append", required=True, metavar="FILE",
                        help="the 'after' callgrind file (repeatable; several are merged first)")
    parser.add_argument("-o", "--output", required=True, help="the callgrind-format delta file to write")
    parser.add_argument("--repo-root", default=".", help="repository root stripped from the written paths")
    namespace = parser.parse_args()
    diff_build(DiffArgs(baseline=namespace.baseline, current=namespace.current,
                        output=namespace.output, repo_root=namespace.repo_root))


if __name__ == "__main__":
    main()
