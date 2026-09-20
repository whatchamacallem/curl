from __future__ import annotations

import os
import posixpath
import re
import sys
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Literal, NamedTuple, TypeAlias, TypeVar

# One cost number per event, in the order the file's "events:" line names them.
Costs: TypeAlias = list[int]
# Where a source file came from, deciding whether the heat map shows it.
Group = Literal["repo", "system", "external"]
_Key = TypeVar("_Key")

# What callgrind's terse event abbreviations mean, spelled out for tooltips.
_EVENT_LONG: dict[str, str] = {
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

# The curl checkout, three levels up from here -- every path is
# reported relative to it.
REPO_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)


# Caller - The one place a function was called from.
class Caller(NamedTuple):
    # who did the calling
    function: str
    # the file that call sits in
    file: str
    # the line that call sits on
    line: int


# CallSite - One line that calls one callee -- the other end of a Caller.
class CallSite(NamedTuple):
    # the file doing the calling
    file: str
    # the line doing the calling
    line: int
    # who gets called
    callee: str


# DerivedEvent - An event callgrind never records, added up from ones it does.
class DerivedEvent(NamedTuple):
    # what to call it, e.g. CEst
    name: str
    # the recorded events to add up, with weights
    terms: tuple[Term, ...]
    # the spelled-out version, for tooltips
    long: str


# PathInfo - One source path, resolved three ways at once.
class PathInfo(NamedTuple):
    # repo-relative, safe to print into a page
    display: str
    # readable on this box, or None when the source is gone
    local: str | None
    # repo, system or external
    group: Group


# Profile - Everything one callgrind run measured, indexed every way
# the pages ask for.
@dataclass
class Profile:
    # the recorded events, in cost-vector order
    events: list[str] = field(default_factory=list)
    # each event spelled out, for tooltips
    event_long: dict[str, str] = field(default_factory=dict)
    # what a cost line's leading columns mean
    positions: list[str] = field(default_factory=lambda: ["line"])
    # the profiled command line
    command: str = ""
    # callgrind's own total -- the self-check divides by it
    summary: list[int] = field(default_factory=list)
    # cost spent on the line itself
    line_self: dict[SourceLine, Costs] = field(default_factory=dict)
    # cost spent below the calls made from it
    line_calls: dict[SourceLine, Costs] = field(default_factory=dict)
    # how many calls the line made
    line_call_count: defaultdict[SourceLine, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    # which function owns the line
    line_function: dict[SourceLine, str] = field(default_factory=dict)
    # the file a function is declared in
    function_home: dict[str, str] = field(default_factory=dict)
    # cost in the function itself, not in what it calls
    function_self: dict[str, Costs] = field(default_factory=dict)
    # per (function, line) cost -- the only per-context table, and
    # what a diff subtracts
    function_lines: defaultdict[str, dict[SourceLine, Costs]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    # cost below everything the function calls
    function_calls: dict[str, Costs] = field(default_factory=dict)
    # the line to jump to when opening a function
    function_entry: dict[str, SourceLine] = field(default_factory=dict)
    # per call site, how many calls and what they cost
    callees: dict[CallSite, Tally] = field(default_factory=dict)
    # the same the other way round: per callee, who called it
    callers: defaultdict[str, dict[Caller, Tally]] = field(
        default_factory=lambda: defaultdict(dict)
    )
    # the binary each file was compiled into
    file_ob: dict[str, str] = field(default_factory=dict)

    # Every event a page may show: recorded first, then the ones we add up.
    def event_names(self) -> list[str]:
        return list(self.events) + [
            derived_event.name
            for derived_event in self.resolved_derived_events()
        ]

    # The derived events this run can supply, with names swapped for
    # cost-vector indexes.
    def resolved_derived_events(self) -> list[ResolvedDerivedEvent]:
        return [
            ResolvedDerivedEvent(
                derived_event.name,
                tuple(
                    ResolvedTerm(
                        term.coefficient, self.events.index(term.event_name)
                    )
                    for term in derived_event.terms
                ),
                derived_event.long,
            )
            for derived_event in _DERIVED_DEFAULTS
            if all(
                term.event_name in self.events for term in derived_event.terms
            )
        ]

    # The whole run's cost: callgrind's own summary, or every line
    # added up when it wrote none.
    def totals(self) -> Costs:
        if self.summary:
            return list(self.summary)
        total = self.zeros()
        for costs in self.line_self.values():
            costs_add(total, costs)
        return total

    # Pull one named event out of a cost vector, recorded or derived.
    def value(self, costs: Costs, name: str) -> int:
        if name in self.events:
            event_index = self.events.index(name)
            return costs[event_index] if event_index < len(costs) else 0
        for derived_event in self.resolved_derived_events():
            if derived_event.name == name:
                return sum(
                    term.coefficient
                    * (
                        costs[term.event_index]
                        if term.event_index < len(costs)
                        else 0
                    )
                    for term in derived_event.terms
                )
        raise KeyError(name)

    # An all-zero cost vector of the right width for this profile.
    def zeros(self) -> Costs:
        return [0] * len(self.events)


# ResolvedDerivedEvent - A DerivedEvent whose terms now point at
# cost-vector slots, ready to sum.
class ResolvedDerivedEvent(NamedTuple):
    # what to call it
    name: str
    # the slots to add up, with weights
    terms: tuple[ResolvedTerm, ...]
    # the spelled-out version
    long: str


# ResolvedTerm - One weighted slot of a cost vector.
class ResolvedTerm(NamedTuple):
    # what to multiply it by
    coefficient: int
    # which slot of the cost vector
    event_index: int


# SourceLine - One line of one file -- the key most tables here are keyed by.
class SourceLine(NamedTuple):
    # the file, exactly as callgrind spelled it
    file: str
    # 1-based line number
    line: int


# Tally - A cost plus how many calls produced it.
@dataclass
class Tally:
    # how many calls
    count: int
    # what they cost between them
    costs: Costs


# Term - One weighted event, named before we know its slot.
class Term(NamedTuple):
    # what to multiply it by
    coefficient: int
    # which recorded event
    event_name: str


# The derived events we offer whenever the run recorded everything they need.
_DERIVED_DEFAULTS: tuple[DerivedEvent, ...] = (
    DerivedEvent(
        "D1m",
        (Term(1, "D1mr"), Term(1, "D1mw")),
        "L1 data cache misses (D1mr + D1mw)",
    ),
    DerivedEvent(
        "DLm",
        (Term(1, "DLmr"), Term(1, "DLmw")),
        "LL data cache misses (DLmr + DLmw)",
    ),
    DerivedEvent(
        "L1m",
        (Term(1, "I1mr"), Term(1, "D1mr"), Term(1, "D1mw")),
        "L1 misses, all (I1mr + D1mr + D1mw)",
    ),
    DerivedEvent(
        "LLm",
        (Term(1, "ILmr"), Term(1, "DLmr"), Term(1, "DLmw")),
        "LL misses, all (ILmr + DLmr + DLmw)",
    ),
    DerivedEvent(
        "Bm",
        (Term(1, "Bcm"), Term(1, "Bim")),
        "branch mispredicts, all (Bcm + Bim)",
    ),
    DerivedEvent(
        "CEst",
        (
            Term(1, "Ir"),
            Term(10, "I1mr"),
            Term(10, "D1mr"),
            Term(10, "D1mw"),
            Term(100, "ILmr"),
            Term(100, "DLmr"),
            Term(100, "DLmw"),
        ),
        "cycle estimate (Ir + 10 L1m + 100 LLm)",
    ),
)


# Callgrind - Reads callgrind's output format into a Profile, and
# resolves the paths in it.
class Callgrind:
    NAME_COMPRESSION_RE = re.compile(r"^\((\d+)\)(?: (.*))?$")

    # CompressedNames - Callgrind writes "(7) name" once, then just
    # "(7)" -- this remembers which is which.
    class CompressedNames:
        def __init__(self) -> None:
            self.names: dict[str, dict[str, str]] = {
                "fl": {},
                "fn": {},
                "ob": {},
            }

        # Expand one "(7)" back to its name, learning the name when
        # this is where it is spelled out.
        def uncompress(self, kind: str, value: str) -> str:
            match = Callgrind.NAME_COMPRESSION_RE.match(value)
            if not match:
                return value
            ident, name = match.group(1), match.group(2)
            if name is not None:
                self.names[kind][ident] = name
                return name
            return self.names[kind].get(ident, f"({ident})")

    # PendingCall - A "calls=" line, waiting for the cost line that follows it.
    class PendingCall(NamedTuple):
        # how many times
        call_count: int
        # the line jumped to
        target_line: int

    # PositionDecoder - Cost lines give positions relative to the last
    # one -- this tracks the running value.
    class PositionDecoder:
        def __init__(self) -> None:
            self.count = 1
            self.line_index = 0
            self.previous: list[int] = [0]

        # Read one position token: "*" repeats, "+n"/"-n" step,
        # anything else is absolute.
        def decode(self, token: str, position: int) -> int:
            if token == "*":
                return self.previous[position]
            if token[0] == "+":
                return self.previous[position] + int(token[1:])
            if token[0] == "-":
                return self.previous[position] - int(token[1:])
            if token.startswith("0x") or token.startswith("0X"):
                return int(token, 16)
            return int(token)

        # Start over for a new "positions:" line, finding which column
        # holds the line number.
        def reset(self, names: Sequence[str]) -> None:
            self.count = len(names)
            self.line_index = (
                names.index("line") if "line" in names else self.count - 1
            )
            self.previous = [0] * self.count

        # Advance past one cost line's positions and hand back the
        # line number it lands on.
        def step(self, tokens: Sequence[str]) -> int:
            for position in range(self.count):
                self.previous[position] = self.decode(
                    tokens[position], position
                )
            return self.previous[self.line_index]

    # Give every still-unplaced function an entry line, so the pages
    # can link to it.
    def entries_fill(self, profile: Profile) -> None:
        for function, lines in profile.function_lines.items():
            home = profile.function_home.get(function)
            if function in profile.function_entry or home is None:
                continue
            line = next(
                (key.line for key in lines if key.file == home and key.line), 0
            )
            if line:
                profile.function_entry[function] = SourceLine(home, line)

    # Spell out every event name, recorded and derived, for the tooltips.
    def labels_fill(self, profile: Profile) -> None:
        for name in profile.events:
            profile.event_long[name] = _EVENT_LONG.get(name, "")
        for derived_event in profile.resolved_derived_events():
            profile.event_long[derived_event.name] = derived_event.long

    # Read every given file and merge them into one profile.
    def load(self, paths: Sequence[str]) -> Profile:
        return self.merge([self.load_one(path) for path in paths])

    # Read one file, and refuse it unless its per-line costs add up
    # to its own summary.
    def load_one(self, path: str) -> Profile:
        with open(path, encoding="utf-8", errors="replace") as handle:
            profile = self.parse(handle.read())
        if not profile.events:
            sys.exit(
                f"error: no 'events:' line -- not a callgrind file? ({path})"
            )
        self_sum = sum(
            costs[0] for costs in profile.line_self.values() if costs
        )
        total = profile.summary[0] if profile.summary else self_sum
        ratio = self_sum / total if total else float("nan")
        print(
            f"ratio (must be 1.0000): {ratio:.4f}  {os.path.basename(path)}",
            file=sys.stderr,
        )
        if total and abs(ratio - 1.0) > 1e-6:
            sys.exit(
                "error: per-line self cost does not add up to"
                f" callgrind's summary ({path})"
            )
        return profile

    # Add several profiles of the same events together.
    def merge(self, profiles: Sequence[Profile]) -> Profile:
        if len(profiles) == 1:
            return profiles[0]
        first = profiles[0]
        for other in profiles[1:]:
            if other.events != first.events:
                sys.exit(
                    "error: cannot merge profiles with different events:"
                    f" {first.events} vs {other.events}"
                )
        merged = Profile(
            events=list(first.events),
            event_long=dict(first.event_long),
            positions=list(first.positions),
        )
        merged.command = self.merge_command(profiles)
        if all(other.summary for other in profiles):
            merged.summary = [
                sum(
                    other.summary[index] if index < len(other.summary) else 0
                    for other in profiles
                )
                for index in range(
                    max(len(other.summary) for other in profiles)
                )
            ]
        for other in profiles:
            self.merge_one(merged, other)
        self.labels_fill(merged)
        return merged

    # One command line standing for all of them, sharing the program
    # name when they agree on it.
    def merge_command(self, profiles: Sequence[Profile]) -> str:
        commands = [other.command.split() for other in profiles]
        if all(
            command and command[0] == commands[0][0] for command in commands
        ):
            return (
                commands[0][0]
                + " "
                + ", ".join(" ".join(command[1:]) for command in commands)
            )
        return " + ".join(other.command for other in profiles)

    # Fold one profile's every table into the one being built.
    def merge_one(self, merged: Profile, other: Profile) -> None:
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
                tally_accumulate(
                    merged.callers[callee], caller, tally.count, tally.costs
                )
        for file, ob in other.file_ob.items():
            merged.file_ob.setdefault(file, ob)

    # Walk the file once, carrying the current file/function/object
    # as callgrind's headers change them.
    def parse(self, text: str) -> Profile:
        profile = Profile()
        names = Callgrind.CompressedNames()
        positions = Callgrind.PositionDecoder()

        event_count = 0
        cur_file = "???"
        cur_function = "???"
        cur_ob = "???"
        cur_callee_ob: str | None = None
        cur_callee_file: str | None = None
        cur_callee_function: str | None = None
        pending_call: Callgrind.PendingCall | None = None

        for raw_line in text.split("\n"):
            if not raw_line or raw_line[0] == "#":
                continue
            first_char = raw_line[0]
            if first_char.isdigit() or first_char in "+-*":
                tokens = raw_line.split()
                line = positions.step(tokens)
                costs = [int(token) for token in tokens[positions.count :]]
                if len(costs) < event_count:
                    costs.extend([0] * (event_count - len(costs)))
                key = SourceLine(cur_file, line)
                if pending_call is not None:
                    callee = cur_callee_function or "???"
                    callee_file = (
                        cur_callee_file
                        if cur_callee_file is not None
                        else cur_file
                    )
                    cur_callee_file = None
                    costs_accumulate(profile.line_calls, key, costs)
                    profile.line_call_count[key] += pending_call.call_count
                    profile.line_function.setdefault(key, cur_function)
                    costs_accumulate(
                        profile.function_calls, cur_function, costs
                    )
                    tally_accumulate(
                        profile.callees,
                        CallSite(cur_file, line, callee),
                        pending_call.call_count,
                        costs,
                    )
                    tally_accumulate(
                        profile.callers[callee],
                        Caller(cur_function, cur_file, line),
                        pending_call.call_count,
                        costs,
                    )
                    if callee not in profile.function_entry:
                        profile.function_entry[callee] = SourceLine(
                            callee_file, pending_call.target_line
                        )
                    profile.function_home.setdefault(callee, callee_file)
                    profile.file_ob.setdefault(
                        callee_file, cur_callee_ob or cur_ob
                    )
                    cur_callee_ob = None
                    pending_call = None
                else:
                    costs_accumulate(profile.line_self, key, costs)
                    profile.line_function.setdefault(key, cur_function)
                    costs_accumulate(
                        profile.function_self, cur_function, costs
                    )
                    costs_accumulate(
                        profile.function_lines[cur_function], key, costs
                    )
                    profile.file_ob.setdefault(cur_file, cur_ob)
                continue

            equals_index = raw_line.find("=")
            colon_index = raw_line.find(":")
            if equals_index != -1 and (
                colon_index == -1 or equals_index < colon_index
            ):
                key, val = (
                    raw_line[:equals_index],
                    raw_line[equals_index + 1 :],
                )
                if key in ("fl", "fi", "fe"):
                    cur_file = names.uncompress("fl", val)
                elif key == "fn":
                    cur_function = names.uncompress("fn", val)
                    profile.function_home.setdefault(cur_function, cur_file)
                    cur_callee_file = None
                elif key == "ob":
                    cur_ob = names.uncompress("ob", val)
                elif key == "cob":
                    cur_callee_ob = names.uncompress("ob", val)
                elif key in ("cfl", "cfi"):
                    cur_callee_file = names.uncompress("fl", val)
                elif key == "cfn":
                    cur_callee_function = names.uncompress("fn", val)
                elif key == "calls":
                    parts = val.split()
                    target_line = (
                        positions.decode(
                            parts[1 + positions.line_index],
                            positions.line_index,
                        )
                        if len(parts) > 1 + positions.line_index
                        else 0
                    )
                    pending_call = Callgrind.PendingCall(
                        int(parts[0]), target_line
                    )
                continue
            if colon_index == -1:
                continue
            key, val = (
                raw_line[:colon_index],
                raw_line[colon_index + 1 :].strip(),
            )
            if key == "events":
                profile.events = val.split()
                event_count = len(profile.events)
            elif key == "positions":
                profile.positions = val.split()
                positions.reset(profile.positions)
            elif key == "cmd":
                profile.command = val
            elif key in ("summary", "totals"):
                values = [int(v) for v in val.split()]
                if len(values) >= len(profile.summary):
                    profile.summary = values

        self.labels_fill(profile)
        self.entries_fill(profile)
        return profile

    # Work out how to print a path, whether we can still read it, and
    # where it came from.
    def path_norm(self, path: str) -> PathInfo:
        if path == "???":
            return PathInfo("(unknown)", None, "external")
        root = REPO_ROOT + "/"
        if os.path.isabs(path):
            path = posixpath.normpath(path)
        if path.startswith(root):
            relative = path[len(root) :]
            local = os.path.join(REPO_ROOT, relative)
            return PathInfo(
                relative, local if os.path.isfile(local) else None, "repo"
            )
        if os.path.isabs(path):
            if os.path.isfile(path):
                return PathInfo(path.lstrip("/"), path, "system")
            return PathInfo(path.lstrip("/"), None, "external")
        candidate = os.path.join(REPO_ROOT, path)
        if os.path.isfile(candidate):
            return PathInfo(posixpath.normpath(path), candidate, "repo")
        return PathInfo(posixpath.normpath(path), None, "external")


# Add a cost vector into a table, starting a fresh entry when the key is new.
def costs_accumulate(
    table: dict[_Key, Costs], key: _Key, costs: Costs
) -> None:
    current = table.get(key)
    if current is None:
        table[key] = list(costs)
    else:
        costs_add(current, costs)


# Add one cost vector into another, in place.
def costs_add(dst: Costs, src: Costs) -> None:
    for index, value in enumerate(src):
        dst[index] += value


# Work out how to print a path, whether we can still read it, and
# where it came from.
def path_norm(path: str) -> PathInfo:
    return Callgrind().path_norm(path)


# Read callgrind files into one profile, refusing any that do not add up.
def profile_load(paths: Sequence[str]) -> Profile:
    return Callgrind().load(paths)


# Add several profiles of the same events together.
def profile_merge(profiles: Sequence[Profile]) -> Profile:
    return Callgrind().merge(profiles)


# Parse callgrind-format text that is already in hand.
def profile_parse(text: str) -> Profile:
    return Callgrind().parse(text)


# Add a call count and its cost into a table, starting a fresh entry
# when the key is new.
def tally_accumulate(
    table: dict[_Key, Tally], key: _Key, count: int, costs: Costs
) -> None:
    current = table.get(key)
    if current is None:
        table[key] = Tally(count, list(costs))
    else:
        current.count += count
        costs_add(current.costs, costs)
