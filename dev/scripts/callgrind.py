from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import NamedTuple, TypeAlias, TypeVar

Costs: TypeAlias = list[int]
Key = TypeVar("Key")

_NAME_COMPRESSION_RE = re.compile(r"^\((\d+)\)(?: (.*))?$")

EVENT_LONG: dict[str, str] = {
    "AcCost1": "L1 cache-block access cost",
    "AcCost2": "LL cache-block access cost",
    "Bc": "conditional branches executed",
    "Bcm": "conditional branches mispredicted",
    "Bi": "indirect branches executed",
    "Bim": "indirect branches mispredicted",
    "D1mr": "L1 data cache read misses",
    "D1mw": "L1 data cache write misses",
    "DLdmr": "LL data read write-backs",
    "DLdmw": "LL data write write-backs",
    "DLmr": "LL (last-level) data read misses",
    "DLmw": "LL (last-level) data write misses",
    "Dr": "data reads",
    "Dw": "data writes",
    "Ge": "global bus events",
    "I1mr": "L1 instruction cache misses",
    "ILdmr": "LL instruction write-backs",
    "ILmr": "LL (last-level) instruction cache misses",
    "Ir": "instructions executed",
    "SpLoss1": "L1 cache-block spatial loss",
    "SpLoss2": "LL cache-block spatial loss",
    "sysCount": "system calls",
    "sysCpuTime": "system call cpu time",
    "sysTime": "system call time",
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


class EventHeader(NamedTuple):
    name: str
    terms: tuple[Term, ...] | None
    long: str


class ResolvedDerivedEvent(NamedTuple):
    name: str
    terms: tuple[ResolvedTerm, ...]
    long: str


class ResolvedTerm(NamedTuple):
    coefficient: int
    event_index: int


class SelfCheck(NamedTuple):
    self_sum: int
    total: int
    ratio: float


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
    derived: list[DerivedEvent] = field(default_factory=list)
    descriptions: list[str] = field(default_factory=list)
    positions: list[str] = field(default_factory=lambda: ["line"])
    command: str = ""
    summary: list[int] = field(default_factory=list)
    line_self: dict[SourceLine, Costs] = field(default_factory=dict)
    line_calls: dict[SourceLine, Costs] = field(default_factory=dict)
    line_call_count: defaultdict[SourceLine, int] = field(default_factory=lambda: defaultdict(int))
    line_function: dict[SourceLine, str] = field(default_factory=dict)
    function_home: dict[str, str] = field(default_factory=dict)
    function_self: dict[str, Costs] = field(default_factory=dict)
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
        resolved: list[ResolvedDerivedEvent] = []
        for derived_event in self.derived:
            if all(term.event_name in self.events for term in derived_event.terms):
                resolved.append(ResolvedDerivedEvent(
                    derived_event.name,
                    tuple(ResolvedTerm(term.coefficient, self.events.index(term.event_name))
                          for term in derived_event.terms),
                    derived_event.long))
        return resolved

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


def profile_load(paths: Sequence[str]) -> Profile:
    profiles: list[Profile] = []
    for path in paths:
        with open(path, encoding="utf-8", errors="replace") as handle:
            profiles.append(profile_parse(handle.read()))
    return profile_merge(profiles)


def profile_merge(profiles: Sequence[Profile]) -> Profile:
    if not profiles:
        raise ValueError("no profiles to merge")
    if len(profiles) == 1:
        return profiles[0]
    first = profiles[0]
    for other in profiles[1:]:
        if other.events != first.events:
            raise ValueError(f"cannot merge profiles with different events: {first.events} vs {other.events}")
    merged = Profile(events=list(first.events), event_long=dict(first.event_long), derived=list(first.derived),
                     descriptions=list(first.descriptions), positions=list(first.positions))
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
                profile.file_ob.setdefault(cur_file, cur_ob)
            continue

        equals_index = raw_line.find("=")
        colon_index = raw_line.find(":")
        if equals_index != -1 and (colon_index == -1 or equals_index < colon_index):
            key, val = raw_line[:equals_index], raw_line[equals_index + 1:]
            if key == "fl":
                cur_file = name_uncompress("fl", val)
            elif key in ("fi", "fe"):
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
            elif key in ("jfi", "jfn"):
                name_uncompress("fl" if key == "jfi" else "fn", val)
            continue
        if colon_index == -1:
            continue
        key, val = raw_line[:colon_index], raw_line[colon_index + 1:].strip()
        if key == "events":
            profile.events = val.split()
            event_count = len(profile.events)
        elif key == "event":
            header = _event_header_parse(val)
            if header.long:
                profile.event_long[header.name] = header.long
            if header.terms is not None:
                profile.derived.append(DerivedEvent(header.name, header.terms, header.long))
        elif key == "positions":
            profile.positions = val.split()
            position_count = len(profile.positions)
            line_position = profile.positions.index("line") if "line" in profile.positions else position_count - 1
            previous = [0] * position_count
        elif key == "cmd":
            profile.command = val
        elif key == "desc":
            profile.descriptions.append(val)
        elif key in ("summary", "totals"):
            values = [int(v) for v in val.split()]
            if len(values) >= len(profile.summary):
                profile.summary = values

    for name in profile.events:
        profile.event_long.setdefault(name, EVENT_LONG.get(name, ""))
    defined = {derived_event.name for derived_event in profile.derived}
    for derived_event in DERIVED_DEFAULTS:
        if derived_event.name not in defined and all(term.event_name in profile.events
                                                       for term in derived_event.terms):
            profile.derived.append(derived_event)
    for derived_event in profile.derived:
        profile.event_long.setdefault(derived_event.name, derived_event.long)
    return profile


def profile_self_check(profile: Profile) -> SelfCheck:
    self_sum = sum(costs[0] for costs in profile.line_self.values() if costs)
    total = profile.summary[0] if profile.summary else self_sum
    ratio = self_sum / total if total else float("nan")
    return SelfCheck(self_sum, total, ratio)


def _event_header_parse(val: str) -> EventHeader:
    head, _, long = val.partition(":")
    name, has_expr, expr = head.partition("=")
    if not has_expr:
        return EventHeader(name.strip(), None, long.strip())
    terms: list[Term] = []
    for term in expr.split("+"):
        parts = term.replace("*", " ").split()
        if len(parts) == 1:
            terms.append(Term(1, parts[0]))
        elif len(parts) == 2:
            terms.append(Term(int(parts[0], 0), parts[1]))
    return EventHeader(name.strip(), tuple(terms), long.strip())
