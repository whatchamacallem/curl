# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import collections, dataclasses, functools, os, posixpath, re, sys
from collections.abc import Callable, Sequence
from typing import Literal, NamedTuple, TypeAlias, TypeVar

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings

_CACHE_ROOT_DIR: str = ""
_DERIVED_COUNTER_TERMS: dict[str, dict[str, int]] = {}
_RANKING_COUNTER_NAME: str = ""
settings.load_into(__name__)

Costs: TypeAlias = list[int]
Group = Literal["repo", "system", "external"]

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)

_Key = TypeVar("_Key")

_CALLGRIND_UNKNOWN_NAME = "???"


@functools.cache
def external_source_roots() -> tuple[str, ...]:
    root = os.path.expanduser(_CACHE_ROOT_DIR)
    if not os.path.isdir(root):
        return ()
    found: list[str] = []
    for package in sorted(os.listdir(root)):
        versions = os.path.join(root, package)
        if not os.path.isdir(versions):
            continue
        for version in sorted(os.listdir(versions)):
            tree = os.path.join(versions, version)
            if os.path.isdir(tree):
                found.append(tree)
    return tuple(found)


class Caller(NamedTuple):
    function: str
    file: str
    line: int


class CallSite(NamedTuple):
    file: str
    line: int
    callee: str


class CounterSchema:
    def __init__(self, counters: Sequence[str]) -> None:
        self.counters = list(counters)
        self.recorded_slots = {
            name: slot for slot, name in enumerate(counters)
        }
        self.derived_counters = [
            ResolvedDerivedCounter(
                name,
                tuple(
                    ResolvedTerm(coefficient, self.recorded_slots[input_name])
                    for input_name, coefficient in terms.items()
                ),
            )
            for name, terms in _DERIVED_COUNTER_TERMS.items()
            if all(input_name in self.recorded_slots for input_name in terms)
        ]
        self.derived_terms = {
            entry.name: entry.terms for entry in self.derived_counters
        }

    def counter_names(self) -> list[str]:
        return list(self.counters) + [
            entry.name for entry in self.derived_counters
        ]

    def value(self, costs: Costs, name: str) -> int:
        slot = self.recorded_slots.get(name)
        if slot is not None:
            return costs[slot] if slot < len(costs) else 0
        terms = self.derived_terms.get(name)
        if terms is None:
            raise KeyError(name)
        return sum(
            term.coefficient
            * (
                costs[term.counter_index]
                if term.counter_index < len(costs)
                else 0
            )
            for term in terms
        )


@dataclasses.dataclass
class LineProfile:
    counters: list[str] = dataclasses.field(default_factory=list)
    command: str = ""
    summary: list[int] = dataclasses.field(default_factory=list)
    line_self: dict[SourceLine, Costs] = dataclasses.field(
        default_factory=dict
    )
    line_function: dict[SourceLine, str] = dataclasses.field(
        default_factory=dict
    )
    function_home: dict[str, str] = dataclasses.field(default_factory=dict)
    function_self: dict[str, Costs] = dataclasses.field(default_factory=dict)
    function_lines: collections.defaultdict[str, dict[SourceLine, Costs]] = (
        dataclasses.field(
            default_factory=lambda: collections.defaultdict(dict)
        )
    )
    function_entry: dict[str, SourceLine] = dataclasses.field(
        default_factory=dict
    )
    file_ob: dict[str, str] = dataclasses.field(default_factory=dict)

    def counter_names(self) -> list[str]:
        return counter_schema(tuple(self.counters)).counter_names()

    def resolved_derived_counters(self) -> list[ResolvedDerivedCounter]:
        return list(counter_schema(tuple(self.counters)).derived_counters)

    def totals(self) -> Costs:
        if not self.summary:
            raise ValueError(f"no summary: command={self.command!r}")
        return list(self.summary)

    def value(self, costs: Costs, name: str) -> int:
        return counter_schema(tuple(self.counters)).value(costs, name)

    def zeros(self) -> Costs:
        return [0] * len(self.counters)


class PathInfo(NamedTuple):
    display: str
    local: str | None
    group: Group


@dataclasses.dataclass
class Profile(LineProfile):
    line_calls: dict[SourceLine, Costs] = dataclasses.field(
        default_factory=dict
    )
    line_call_count: collections.defaultdict[SourceLine, int] = (
        dataclasses.field(default_factory=lambda: collections.defaultdict(int))
    )
    function_calls: dict[str, Costs] = dataclasses.field(default_factory=dict)
    callees: dict[CallSite, Tally] = dataclasses.field(default_factory=dict)
    callers: collections.defaultdict[str, dict[Caller, Tally]] = (
        dataclasses.field(
            default_factory=lambda: collections.defaultdict(dict)
        )
    )


class ResolvedDerivedCounter(NamedTuple):
    name: str
    terms: tuple[ResolvedTerm, ...]


class ResolvedTerm(NamedTuple):
    coefficient: int
    counter_index: int


class SourceLine(NamedTuple):
    file: str
    line: int


@dataclasses.dataclass
class Tally:
    count: int
    costs: Costs


class Callgrind:
    ADDRESS_NAME_RE = re.compile(r"0x[0-9a-f]+")
    NAME_COMPRESSION_RE = re.compile(r"^\((\d+)\)(?: (.*))?$")

    class CompressedNames:
        def __init__(self) -> None:
            self.names: dict[str, dict[str, str]] = {
                "fl": {},
                "fn": {},
                "ob": {},
            }

        def uncompress(self, kind: str, value: str) -> str:
            match = Callgrind.NAME_COMPRESSION_RE.match(value)
            if not match:
                return value
            ident, name = match.group(1), match.group(2)
            if name is not None:
                self.names[kind][ident] = name
                return name
            known = self.names[kind].get(ident)
            if known is None:
                sys.exit(
                    f"error: {kind}=({ident}) refers to a name this file"
                    " never spelled out"
                )
            return known

    class PendingCall(NamedTuple):
        call_count: int
        target_line: int

    class PositionDecoder:
        def __init__(self) -> None:
            self.count = 1
            self.line_index = 0
            self.previous: list[int] = [0]

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

        def reset(self, names: Sequence[str]) -> None:
            self.count = len(names)
            self.line_index = (
                names.index("line") if "line" in names else self.count - 1
            )
            self.previous = [0] * self.count

        def step(self, tokens: Sequence[str]) -> int:
            for position in range(self.count):
                self.previous[position] = self.decode(
                    tokens[position], position
                )
            return self.previous[self.line_index]

    # Renames each function spelled as an address, through its object or None.
    def address_names_resolve(
        self, text: str, name_of: Callable[[str | None, str], str | None]
    ) -> str:
        names = Callgrind.CompressedNames()
        lines = text.split("\n")
        current_object = _CALLGRIND_UNKNOWN_NAME
        current_callee_object: str | None = None
        for index, raw_line in enumerate(lines):
            key, _, specification_value = raw_line.partition("=")
            if key == "ob":
                current_object = names.uncompress("ob", specification_value)
            elif key == "cob":
                current_callee_object = names.uncompress(
                    "ob", specification_value
                )
            elif key in ("fn", "cfn"):
                object_path = (
                    (current_callee_object or current_object)
                    if key == "cfn"
                    else current_object
                )
                current_callee_object = None
                match = Callgrind.NAME_COMPRESSION_RE.match(
                    specification_value
                )
                if not match or not match.group(2):
                    continue
                name = match.group(2)
                if not Callgrind.ADDRESS_NAME_RE.fullmatch(name):
                    continue
                resolved = name_of(
                    None
                    if object_path == _CALLGRIND_UNKNOWN_NAME
                    else object_path,
                    name,
                )
                if resolved is not None:
                    lines[index] = f"{key}=({match.group(1)}) {resolved}"
        return "\n".join(lines)

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

    # Refuses a function in no object that is still named by its address.
    def function_name_of(
        self,
        names: Callgrind.CompressedNames,
        compressed_name: str,
        object_path: str,
        path: str,
    ) -> str:
        name = names.uncompress("fn", compressed_name)
        if object_path == _CALLGRIND_UNKNOWN_NAME and (
            Callgrind.ADDRESS_NAME_RE.fullmatch(name)
        ):
            sys.exit(
                f"error: {path}: function {name} in no object is named by its"
                " address, recorded before callgrind_symbols.py named it:"
                " measure again without --regenerate"
            )
        return name

    def load(self, paths: Sequence[str]) -> Profile:
        return self.merge([self.load_one(path) for path in paths])

    def load_one(self, path: str) -> Profile:
        with open(path, encoding="utf-8", errors="replace") as handle:
            profile = self.parse(handle.read(), path)
        if not profile.counters:
            sys.exit(
                f"error: no 'events:' line -- not a callgrind file? ({path})"
            )
        self_sum = sum(
            costs[0] for costs in profile.line_self.values() if costs
        )
        total = profile.totals()[0]
        if total == 0:
            sys.exit(f"error: callgrind summary total is 0 ({path})")
        ratio = self_sum / total
        print(
            f"ratio (must be 1.0000): {ratio:.4f}  {os.path.basename(path)}",
            file=sys.stderr,
        )
        if abs(ratio - 1.0) > 1e-6:
            sys.exit(
                "error: per-line self cost does not add up to"
                f" callgrind's summary ({path})"
            )
        return profile

    def merge(self, profiles: Sequence[Profile]) -> Profile:
        if len(profiles) == 1:
            return profiles[0]
        first = profiles[0]
        for other in profiles[1:]:
            if other.counters != first.counters:
                sys.exit(
                    "error: cannot merge profiles with different counters:"
                    f" {first.counters} vs {other.counters}"
                )
        merged = Profile(counters=list(first.counters))
        merged.command = self.merge_command(profiles)
        if not all(other.summary for other in profiles):
            sys.exit(
                "error: cannot merge profiles, one has no summary:"
                f" {[other.command for other in profiles]}"
            )
        merged.summary = [
            sum(
                other.summary[index] if index < len(other.summary) else 0
                for other in profiles
            )
            for index in range(max(len(other.summary) for other in profiles))
        ]
        for other in profiles:
            self.merge_one(merged, other)
        return merged

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

    def parse(self, text: str, path: str) -> Profile:
        profile = Profile()
        names = Callgrind.CompressedNames()
        positions = Callgrind.PositionDecoder()

        counter_count = 0
        current_file = "???"
        cur_function = "???"
        current_object = "???"
        current_callee_object: str | None = None
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
                if len(costs) < counter_count:
                    costs.extend([0] * (counter_count - len(costs)))
                key = SourceLine(current_file, line)
                if pending_call is not None:
                    callee = cur_callee_function or "???"
                    callee_file = (
                        cur_callee_file
                        if cur_callee_file is not None
                        else current_file
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
                        CallSite(current_file, line, callee),
                        pending_call.call_count,
                        costs,
                    )
                    tally_accumulate(
                        profile.callers[callee],
                        Caller(cur_function, current_file, line),
                        pending_call.call_count,
                        costs,
                    )
                    if callee not in profile.function_entry:
                        profile.function_entry[callee] = SourceLine(
                            callee_file, pending_call.target_line
                        )
                    profile.function_home.setdefault(callee, callee_file)
                    profile.file_ob.setdefault(
                        callee_file, current_callee_object or current_object
                    )
                    current_callee_object = None
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
                    profile.file_ob.setdefault(current_file, current_object)
                continue

            equals_index = raw_line.find("=")
            colon_index = raw_line.find(":")
            if equals_index != -1 and (
                colon_index == -1 or equals_index < colon_index
            ):
                key, specification_value = (
                    raw_line[:equals_index],
                    raw_line[equals_index + 1 :],
                )
                if key in ("fl", "fi", "fe"):
                    current_file = file_key_of(
                        names.uncompress("fl", specification_value),
                        current_object,
                    )
                elif key == "fn":
                    cur_function = self.function_name_of(
                        names, specification_value, current_object, path
                    )
                    profile.function_home.setdefault(
                        cur_function, current_file
                    )
                    cur_callee_file = None
                elif key == "ob":
                    current_object = names.uncompress(
                        "ob", specification_value
                    )
                elif key == "cob":
                    current_callee_object = names.uncompress(
                        "ob", specification_value
                    )
                elif key in ("cfl", "cfi"):
                    cur_callee_file = file_key_of(
                        names.uncompress("fl", specification_value),
                        current_callee_object or current_object,
                    )
                elif key == "cfn":
                    cur_callee_function = self.function_name_of(
                        names,
                        specification_value,
                        current_callee_object or current_object,
                        path,
                    )
                elif key in ("jfi", "jfn"):
                    names.uncompress(
                        "fl" if key == "jfi" else "fn", specification_value
                    )
                elif key == "calls":
                    parts = specification_value.split()
                    if len(parts) <= 1 + positions.line_index:
                        sys.exit(f"error: malformed 'calls=' line: {raw_line}")
                    target_line = positions.decode(
                        parts[1 + positions.line_index], positions.line_index
                    )
                    pending_call = Callgrind.PendingCall(
                        int(parts[0]), target_line
                    )
                continue
            if colon_index == -1:
                continue
            key, header_value = (
                raw_line[:colon_index],
                raw_line[colon_index + 1 :].strip(),
            )
            if key == "events":
                profile.counters = header_value.split()
                counter_count = len(profile.counters)
            elif key == "positions":
                positions.reset(header_value.split())
            elif key == "cmd":
                profile.command = header_value
            elif key in ("summary", "totals"):
                values = [int(v) for v in header_value.split()]
                if len(values) >= len(profile.summary):
                    profile.summary = values

        self.entries_fill(profile)
        return profile


_profile_parser = Callgrind()


def address_names_resolve(
    text: str, name_of: Callable[[str | None, str], str | None]
) -> str:
    return _profile_parser.address_names_resolve(text, name_of)


def baseline_line_key(display: str, line: int | str) -> str:
    return f"{display}\n{line}"


def cached_source_of(display: str) -> str | None:
    if display.startswith(".."):
        return None
    parts = display.split("/")
    wanted = [display]
    if len(parts) > 1 and parts[0] == parts[1]:
        wanted.append("/".join(parts[1:]))
    for tree in external_source_roots():
        for relative in wanted:
            local = os.path.join(tree, relative)
            if os.path.isfile(local):
                return local
    return None


def costs_accumulate(
    table: dict[_Key, Costs], key: _Key, costs: Costs
) -> None:
    current = table.get(key)
    if current is None:
        table[key] = list(costs)
    else:
        costs_add(current, costs)


def costs_add(dst: Costs, src: Costs) -> None:
    for index, value in enumerate(src):
        dst[index] += value


def costs_fit(costs: Costs, width: int) -> Costs:
    return costs_trim(list(costs) + [0] * (width - len(costs)))


def costs_sub(modified: Costs, baseline: Costs) -> Costs:
    return [
        (modified[index] if index < len(modified) else 0)
        - (baseline[index] if index < len(baseline) else 0)
        for index in range(max(len(modified), len(baseline)))
    ]


def costs_trim(costs: Costs) -> Costs:
    length = len(costs)
    while length and costs[length - 1] == 0:
        length -= 1
    return costs[:length]


def counter_names(counters: Sequence[str]) -> list[str]:
    return counter_schema(tuple(counters)).counter_names()


@functools.cache
def counter_schema(counters: tuple[str, ...]) -> CounterSchema:
    return CounterSchema(counters)


def counter_value(counters: Sequence[str], costs: Costs, name: str) -> int:
    return counter_schema(tuple(counters)).value(costs, name)


def display_path_of(path: str, object_path: str) -> str:
    info = path_norm(path)
    if info.group != "external":
        return info.display
    owner = os.path.basename(object_path) or "(unknown object)"
    return f"{owner}/{info.display}"


def file_key_of(path: str, object_path: str) -> str:
    if path != _CALLGRIND_UNKNOWN_NAME:
        return path
    return f"{os.path.basename(object_path)}/{path}"


def path_norm(path: str) -> PathInfo:
    if posixpath.basename(path) == _CALLGRIND_UNKNOWN_NAME:
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
    display = posixpath.normpath(path)
    cached = cached_source_of(display)
    if cached is not None:
        return PathInfo(display, cached, "system")
    return PathInfo(display, None, "external")


def profile_load(paths: Sequence[str]) -> Profile:
    return _profile_parser.load(paths)


def ranking_counter_check(counters: Sequence[str], source: str) -> None:
    if _RANKING_COUNTER_NAME in counter_names(counters):
        return
    sys.exit(
        f"error: {source} cannot supply {_RANKING_COUNTER_NAME}, the"
        f" counter every page ranks and divides by: it records"
        f" {' '.join(counters)}"
    )


def tally_accumulate(
    table: dict[_Key, Tally], key: _Key, count: int, costs: Costs
) -> None:
    current = table.get(key)
    if current is None:
        table[key] = Tally(count, list(costs))
    else:
        current.count += count
        costs_add(current.costs, costs)
