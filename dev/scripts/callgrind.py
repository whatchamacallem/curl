from __future__ import annotations

import os
import posixpath
import re
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, NamedTuple, TypeAlias, TypeVar

Costs: TypeAlias = list[int]
Group = Literal["repo", "system", "external"]
Key = TypeVar("Key")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_NAME_COMPRESSION_RE = re.compile(r"^\((\d+)\)(?: (.*))?$")

EVENT_LONG: dict[str, str] = {
    "Bc": "conditional branches executed",
    "Bcm": "conditional branches mispredicted",
    "Bi": "indirect branches executed",
    "Bim": "indirect branches mispredicted",
    "D1mr": "L1 data cache read misses",
    "D1mw": "L1 data cache write misses",
    "DLmr": "LL (last-level) data read misses",
    "DLmw": "LL (last-level) data write misses",
    "Dr": "data reads",
    "Dw": "data writes",
    "I1mr": "L1 instruction cache misses",
    "ILmr": "LL (last-level) instruction cache misses",
    "Ir": "instructions executed",
}


class Caller(NamedTuple):
    function: str
    file: str
    line: int


class CallSite(NamedTuple):
    file: str
    line: int
    callee: str


class DerivedEvent(NamedTuple):
    name: str
    terms: tuple[Term, ...]
    long: str


class PathInfo(NamedTuple):
    display: str
    local: str | None
    group: Group


class ResolvedDerivedEvent(NamedTuple):
    name: str
    terms: tuple[ResolvedTerm, ...]
    long: str


class ResolvedTerm(NamedTuple):
    coefficient: int
    event_index: int


class SourceLine(NamedTuple):
    file: str
    line: int


class Term(NamedTuple):
    coefficient: int
    event_name: str


class _PendingCall(NamedTuple):
    call_count: int
    target_line: int


@dataclass
class Tally:
    count: int
    costs: Costs


@dataclass
class Profile:
    events: list[str] = field(default_factory=list)
    event_long: dict[str, str] = field(default_factory=dict)
    positions: list[str] = field(default_factory=lambda: ["line"])
    command: str = ""
    summary: list[int] = field(default_factory=list)
    line_self: dict[SourceLine, Costs] = field(default_factory=dict)
    line_calls: dict[SourceLine, Costs] = field(default_factory=dict)
    line_call_count: defaultdict[SourceLine, int] = field(default_factory=lambda: defaultdict(int))
    line_function: dict[SourceLine, str] = field(default_factory=dict)
    function_home: dict[str, str] = field(default_factory=dict)
    function_self: dict[str, Costs] = field(default_factory=dict)
    function_lines: defaultdict[str, dict[SourceLine, Costs]] = field(default_factory=lambda: defaultdict(dict))
    function_calls: dict[str, Costs] = field(default_factory=dict)
    function_entry: dict[str, SourceLine] = field(default_factory=dict)
    callees: dict[CallSite, Tally] = field(default_factory=dict)
    callers: defaultdict[str, dict[Caller, Tally]] = field(default_factory=lambda: defaultdict(dict))
    file_ob: dict[str, str] = field(default_factory=dict)

    def zeros(self) -> Costs:
        return [0] * len(self.events)

    def totals(self) -> Costs:
        if self.summary:
            return list(self.summary)
        total = self.zeros()
        for costs in self.line_self.values():
            costs_add(total, costs)
        return total

    def resolved_derived_events(self) -> list[ResolvedDerivedEvent]:
        return [ResolvedDerivedEvent(derived_event.name,
                                     tuple(ResolvedTerm(term.coefficient, self.events.index(term.event_name))
                                           for term in derived_event.terms),
                                     derived_event.long)
                for derived_event in DERIVED_DEFAULTS
                if all(term.event_name in self.events for term in derived_event.terms)]

    def value(self, costs: Costs, name: str) -> int:
        if name in self.events:
            event_index = self.events.index(name)
            return costs[event_index] if event_index < len(costs) else 0
        for derived_event in self.resolved_derived_events():
            if derived_event.name == name:
                return sum(term.coefficient * (costs[term.event_index] if term.event_index < len(costs) else 0)
                           for term in derived_event.terms)
        raise KeyError(name)

    def event_names(self) -> list[str]:
        return list(self.events) + [derived_event.name for derived_event in self.resolved_derived_events()]


DERIVED_DEFAULTS: tuple[DerivedEvent, ...] = (
    DerivedEvent("D1m", (Term(1, "D1mr"), Term(1, "D1mw")), "L1 data cache misses (D1mr + D1mw)"),
    DerivedEvent("DLm", (Term(1, "DLmr"), Term(1, "DLmw")), "LL data cache misses (DLmr + DLmw)"),
    DerivedEvent("L1m", (Term(1, "I1mr"), Term(1, "D1mr"), Term(1, "D1mw")), "L1 misses, all (I1mr + D1mr + D1mw)"),
    DerivedEvent("LLm", (Term(1, "ILmr"), Term(1, "DLmr"), Term(1, "DLmw")), "LL misses, all (ILmr + DLmr + DLmw)"),
    DerivedEvent("Bm", (Term(1, "Bcm"), Term(1, "Bim")), "branch mispredicts, all (Bcm + Bim)"),
    DerivedEvent("CEst", (Term(1, "Ir"), Term(10, "I1mr"), Term(10, "D1mr"), Term(10, "D1mw"),
                          Term(100, "ILmr"), Term(100, "DLmr"), Term(100, "DLmw")),
                 "cycle estimate (Ir + 10 L1m + 100 LLm)"),
)


def costs_add(dst: Costs, src: Costs) -> None:
    for index, value in enumerate(src):
        dst[index] += value


def costs_accumulate(table: dict[Key, Costs], key: Key, costs: Costs) -> None:
    current = table.get(key)
    if current is None:
        table[key] = list(costs)
    else:
        costs_add(current, costs)


def tally_accumulate(table: dict[Key, Tally], key: Key, count: int, costs: Costs) -> None:
    current = table.get(key)
    if current is None:
        table[key] = Tally(count, list(costs))
    else:
        current.count += count
        costs_add(current.costs, costs)


def path_norm(path: str) -> PathInfo:
    if path == "???":
        return PathInfo("(unknown)", None, "external")
    root = REPO_ROOT + "/"
    if os.path.isabs(path):
        path = posixpath.normpath(path)
    if path.startswith(root):
        relative = path[len(root):]
        local = os.path.join(REPO_ROOT, relative)
        return PathInfo(relative, local if os.path.isfile(local) else None, "repo")
    if os.path.isabs(path):
        if os.path.isfile(path):
            return PathInfo(path.lstrip("/"), path, "system")
        return PathInfo(path.lstrip("/"), None, "external")
    candidate = os.path.join(REPO_ROOT, path)
    if os.path.isfile(candidate):
        return PathInfo(posixpath.normpath(path), candidate, "repo")
    return PathInfo(posixpath.normpath(path), None, "external")


def _profile_load_one(path: str) -> Profile:
    with open(path, encoding="utf-8", errors="replace") as handle:
        profile = profile_parse(handle.read())
    if not profile.events:
        sys.exit(f"error: no 'events:' line -- not a callgrind file? ({path})")
    self_sum = sum(costs[0] for costs in profile.line_self.values() if costs)
    total = profile.summary[0] if profile.summary else self_sum
    ratio = self_sum / total if total else float("nan")
    print(f"ratio (must be 1.0000): {ratio:.4f}  {os.path.basename(path)}", file=sys.stderr)
    if total and abs(ratio - 1.0) > 1e-6:
        sys.exit(f"error: per-line self cost does not add up to callgrind's summary ({path})")
    return profile


def profile_load(paths: Sequence[str]) -> Profile:
    profiles = [_profile_load_one(path) for path in paths]
    return profile_merge(profiles)


def profile_merge(profiles: Sequence[Profile]) -> Profile:
    if len(profiles) == 1:
        return profiles[0]
    first = profiles[0]
    for other in profiles[1:]:
        if other.events != first.events:
            sys.exit(f"error: cannot merge profiles with different events: {first.events} vs {other.events}")
    merged = Profile(events=list(first.events), event_long=dict(first.event_long), positions=list(first.positions))
    commands = [other.command.split() for other in profiles]
    if all(command and command[0] == commands[0][0] for command in commands):
        merged.command = commands[0][0] + " " + ", ".join(" ".join(command[1:]) for command in commands)
    else:
        merged.command = " + ".join(other.command for other in profiles)
    if all(other.summary for other in profiles):
        merged.summary = [sum(other.summary[index] if index < len(other.summary) else 0 for other in profiles)
                          for index in range(max(len(other.summary) for other in profiles))]
    for other in profiles:
        for key, costs in other.line_self.items():
            costs_accumulate(merged.line_self, key, costs)
        for key, costs in other.line_calls.items():
            costs_accumulate(merged.line_calls, key, costs)
        for key, count in other.line_call_count.items():
            merged.line_call_count[key] += count
        for key, function in other.line_function.items():
            merged.line_function.setdefault(key, function)
        for function, home in other.function_home.items():
            merged.function_home.setdefault(function, home)
        for function, costs in other.function_self.items():
            costs_accumulate(merged.function_self, function, costs)
        for function, lines in other.function_lines.items():
            for key, costs in lines.items():
                costs_accumulate(merged.function_lines[function], key, costs)
        for function, costs in other.function_calls.items():
            costs_accumulate(merged.function_calls, function, costs)
        for function, entry in other.function_entry.items():
            merged.function_entry.setdefault(function, entry)
        for site, tally in other.callees.items():
            tally_accumulate(merged.callees, site, tally.count, tally.costs)
        for callee, callers in other.callers.items():
            for caller, tally in callers.items():
                tally_accumulate(merged.callers[callee], caller, tally.count, tally.costs)
        for file, ob in other.file_ob.items():
            merged.file_ob.setdefault(file, ob)
    for name in merged.events:
        merged.event_long[name] = EVENT_LONG.get(name, "")
    for derived_event in merged.resolved_derived_events():
        merged.event_long[derived_event.name] = derived_event.long
    return merged


def profile_parse(text: str) -> Profile:
    profile = Profile()
    names: dict[str, dict[str, str]] = {"fl": {}, "fn": {}, "ob": {}}

    def name_uncompress(kind: str, val: str) -> str:
        match = _NAME_COMPRESSION_RE.match(val)
        if not match:
            return val
        ident, name = match.group(1), match.group(2)
        if name is not None:
            names[kind][ident] = name
            return name
        return names[kind].get(ident, f"({ident})")

    event_count = 0
    position_count = 1
    line_position = 0
    previous: list[int] = [0]
    cur_file = "???"
    cur_function = "???"
    cur_ob = "???"
    cur_callee_ob: str | None = None
    cur_callee_file: str | None = None
    cur_callee_function: str | None = None
    pending_call: _PendingCall | None = None

    def position_decode(token: str, position: int) -> int:
        if token == "*":
            return previous[position]
        if token[0] == "+":
            return previous[position] + int(token[1:])
        if token[0] == "-":
            return previous[position] - int(token[1:])
        if token.startswith("0x") or token.startswith("0X"):
            return int(token, 16)
        return int(token)

    for raw_line in text.split("\n"):
        if not raw_line or raw_line[0] == "#":
            continue
        first_char = raw_line[0]
        if first_char.isdigit() or first_char in "+-*":
            tokens = raw_line.split()
            for position in range(position_count):
                previous[position] = position_decode(tokens[position], position)
            line = previous[line_position]
            costs = [int(token) for token in tokens[position_count:]]
            if len(costs) < event_count:
                costs.extend([0] * (event_count - len(costs)))
            key = SourceLine(cur_file, line)
            if pending_call is not None:
                callee = cur_callee_function or "???"
                callee_file = cur_callee_file if cur_callee_file is not None else cur_file
                cur_callee_file = None
                costs_accumulate(profile.line_calls, key, costs)
                profile.line_call_count[key] += pending_call.call_count
                profile.line_function.setdefault(key, cur_function)
                costs_accumulate(profile.function_calls, cur_function, costs)
                tally_accumulate(profile.callees, CallSite(cur_file, line, callee), pending_call.call_count, costs)
                tally_accumulate(profile.callers[callee], Caller(cur_function, cur_file, line),
                                 pending_call.call_count, costs)
                if callee not in profile.function_entry:
                    profile.function_entry[callee] = SourceLine(callee_file, pending_call.target_line)
                profile.function_home.setdefault(callee, callee_file)
                profile.file_ob.setdefault(callee_file, cur_callee_ob or cur_ob)
                cur_callee_ob = None
                pending_call = None
            else:
                costs_accumulate(profile.line_self, key, costs)
                profile.line_function.setdefault(key, cur_function)
                costs_accumulate(profile.function_self, cur_function, costs)
                costs_accumulate(profile.function_lines[cur_function], key, costs)
                profile.file_ob.setdefault(cur_file, cur_ob)
            continue

        equals_index = raw_line.find("=")
        colon_index = raw_line.find(":")
        if equals_index != -1 and (colon_index == -1 or equals_index < colon_index):
            key, val = raw_line[:equals_index], raw_line[equals_index + 1:]
            if key in ("fl", "fi", "fe"):
                cur_file = name_uncompress("fl", val)
            elif key == "fn":
                cur_function = name_uncompress("fn", val)
                profile.function_home.setdefault(cur_function, cur_file)
                cur_callee_file = None
            elif key == "ob":
                cur_ob = name_uncompress("ob", val)
            elif key == "cob":
                cur_callee_ob = name_uncompress("ob", val)
            elif key in ("cfl", "cfi"):
                cur_callee_file = name_uncompress("fl", val)
            elif key == "cfn":
                cur_callee_function = name_uncompress("fn", val)
            elif key == "calls":
                parts = val.split()
                target_line = position_decode(parts[1 + line_position], line_position) \
                    if len(parts) > 1 + line_position else 0
                pending_call = _PendingCall(int(parts[0]), target_line)
            continue
        if colon_index == -1:
            continue
        key, val = raw_line[:colon_index], raw_line[colon_index + 1:].strip()
        if key == "events":
            profile.events = val.split()
            event_count = len(profile.events)
        elif key == "positions":
            profile.positions = val.split()
            position_count = len(profile.positions)
            line_position = profile.positions.index("line") if "line" in profile.positions else position_count - 1
            previous = [0] * position_count
        elif key == "cmd":
            profile.command = val
        elif key in ("summary", "totals"):
            values = [int(v) for v in val.split()]
            if len(values) >= len(profile.summary):
                profile.summary = values

    for name in profile.events:
        profile.event_long[name] = EVENT_LONG.get(name, "")
    for derived_event in profile.resolved_derived_events():
        profile.event_long[derived_event.name] = derived_event.long
    for function, lines in profile.function_lines.items():
        home = profile.function_home.get(function)
        if function in profile.function_entry or home is None:
            continue
        line = next((key.line for key in lines if key.file == home and key.line), 0)
        if line:
            profile.function_entry[function] = SourceLine(home, line)
    return profile
