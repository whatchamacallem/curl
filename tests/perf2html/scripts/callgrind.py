# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import collections, dataclasses, functools, json, os, posixpath, re, sys
from collections.abc import Callable, Sequence
from typing import NamedTuple, TypeAlias, TypeVar

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artifacts, settings

_CACHE_ROOT_DIR: str = ""
_CALLGRIND_FILE_DATA_ERROR_CODE: str = ""
_CALLGRIND_FILE_DATA_GIT_CODE: str = ""
_CALLGRIND_FILE_DATA_REPO_CODE: str = ""
_CALLGRIND_FILE_DATA_SYSTEM_CODE: str = ""
_CALLGRIND_ROOT_FUNCTION_NAME: str = ""
_DERIVED_COUNTER_TERMS: dict[str, dict[str, int]] = {}
_RANKING_COUNTER_NAME: str = ""
settings.load_into(__name__)

Costs: TypeAlias = list[int]

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


class CallerCalls(NamedTuple):
    calls: int
    line: int


class CallRecord(NamedTuple):
    key: SourceLine
    callee: str
    callee_file: str
    callee_object: str
    call_count: int
    target_line: int
    costs: Costs


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


class DerivedPath(NamedTuple):
    canonical: str
    group: str
    has_source: bool
    in_baseline: bool


# Holds each recorded path's category as a diff's two reports coded it.
class DerivedPaths:
    def __init__(self, baseline_dir: str, modified_dir: str) -> None:
        baseline = self.document_read(baseline_dir)
        baseline_document = artifacts.artifact_path(baseline_dir, "file-data")
        self.tracked = [
            path
            for path, code in baseline.items()
            if code == _CALLGRIND_FILE_DATA_GIT_CODE
        ]
        self.files: dict[str, DerivedPath] = {}
        codes = (
            _CALLGRIND_FILE_DATA_ERROR_CODE,
            _CALLGRIND_FILE_DATA_GIT_CODE,
            _CALLGRIND_FILE_DATA_REPO_CODE,
            _CALLGRIND_FILE_DATA_SYSTEM_CODE,
        )
        for document, read, in_baseline in (
            (baseline_document, baseline, True),
            (
                artifacts.artifact_path(modified_dir, "file-data"),
                self.document_read(modified_dir),
                False,
            ),
        ):
            for path, code in read.items():
                if code not in codes:
                    sys.exit(
                        f"error: {document} codes {path} as {code!r},"
                        f" which is none of {' '.join(codes)}"
                    )
                if code == _CALLGRIND_FILE_DATA_GIT_CODE:
                    continue
                shown = DerivedPath(
                    path,
                    code,
                    code != _CALLGRIND_FILE_DATA_ERROR_CODE,
                    in_baseline,
                )
                known = self.files.setdefault(path, shown)
                if known.group != shown.group:
                    sys.exit(
                        f"error: the two reports code {path} apart:"
                        f" {known.group} in {baseline_document},"
                        f" {shown.group} in {document}"
                    )

    def document_read(self, directory: str) -> dict[str, str]:
        with artifacts.artifact_open(directory, "file-data") as handle:
            return json.load(handle)

    def path_entry(self, path: str) -> DerivedPath:
        canonical = path_canonical(path)
        entry = self.files.get(canonical)
        if entry is None:
            sys.exit(
                f"error: neither report's file data names {canonical},"
                f" recorded as {path}"
            )
        return entry


# Holds one function's cost lines as read, before the cut at the root.
@dataclasses.dataclass
class FunctionRecords:
    home: str
    self_records: list[SelfRecord] = dataclasses.field(default_factory=list)
    call_records: list[CallRecord] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class LineProfile:
    counters: list[str] = dataclasses.field(default_factory=list)
    command: str = ""
    summary: list[int] = dataclasses.field(default_factory=list)
    line_self: dict[SourceLine, Costs] = dataclasses.field(
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

    def resolved_derived_counters(self) -> list[ResolvedDerivedCounter]:
        return list(counter_schema(tuple(self.counters)).derived_counters)

    def totals(self) -> Costs:
        if not self.summary:
            raise ValueError(f"no summary: command={self.command!r}")
        return list(self.summary)

    def zeros(self) -> Costs:
        return [0] * len(self.counters)


class PathInfo(NamedTuple):
    display: str
    local: str | None
    group: str


@dataclasses.dataclass
class Profile(LineProfile):
    root_call_count: int = 0
    line_calls: dict[SourceLine, Costs] = dataclasses.field(
        default_factory=dict
    )
    line_call_count: collections.defaultdict[SourceLine, int] = (
        dataclasses.field(default_factory=lambda: collections.defaultdict(int))
    )
    function_calls: dict[str, Costs] = dataclasses.field(default_factory=dict)
    function_call_lines: collections.defaultdict[str, set[SourceLine]] = (
        dataclasses.field(default_factory=lambda: collections.defaultdict(set))
    )
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


class SelfRecord(NamedTuple):
    key: SourceLine
    object_path: str
    costs: Costs


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
        self,
        text: str,
        address_name_resolve: Callable[[str | None, str], str | None],
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
                resolved = address_name_resolve(
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
    def function_name(
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

    # Adds a kept function's records to the profile, in the order read.
    def function_accumulate(
        self, profile: Profile, function: str, records: FunctionRecords
    ) -> None:
        profile.function_home.setdefault(function, records.home)
        for self_record in records.self_records:
            costs_accumulate(
                profile.line_self, self_record.key, self_record.costs
            )
            costs_accumulate(
                profile.function_self, function, self_record.costs
            )
            costs_accumulate(
                profile.function_lines[function],
                self_record.key,
                self_record.costs,
            )
            profile.file_ob.setdefault(
                self_record.key.file, self_record.object_path
            )
        for call in records.call_records:
            costs_accumulate(profile.line_calls, call.key, call.costs)
            profile.line_call_count[call.key] += call.call_count
            costs_accumulate(profile.function_calls, function, call.costs)
            profile.function_call_lines[function].add(call.key)
            tally_accumulate(
                profile.callees,
                CallSite(call.key.file, call.key.line, call.callee),
                call.call_count,
                call.costs,
            )
            tally_accumulate(
                profile.callers[call.callee],
                Caller(function, call.key.file, call.key.line),
                call.call_count,
                call.costs,
            )
            if call.callee not in profile.function_entry:
                profile.function_entry[call.callee] = SourceLine(
                    call.callee_file, call.target_line
                )
            profile.function_home.setdefault(call.callee, call.callee_file)
            profile.file_ob.setdefault(call.callee_file, call.callee_object)

    # Loads a profile, a recording cut at the root, a delta of two as is.
    def load(self, directory: str, kind: str, test_name: str) -> Profile:
        path = artifacts.artifact_path(directory, kind, test_name)
        with artifacts.artifact_open(
            directory, kind, test_name, "rb"
        ) as handle:
            text = handle.read().decode("utf-8", errors="replace")
        return self.parse(text, path, kind == "callgrind")

    # Returns the profile of the text, cut at the root function when asked.
    def parse(self, text: str, path: str, is_cut: bool) -> Profile:
        profile = Profile()
        records = self.records_read(text, path, profile)
        if not profile.counters:
            sys.exit(
                f"error: no 'events:' line -- not a callgrind file? ({path})"
            )
        self.summary_check(profile, records, path)
        kept = self.root_reach(records, path) if is_cut else set(records)
        profile.root_call_count = sum(
            call.call_count
            for entry in records.values()
            for call in entry.call_records
            if call.callee == _CALLGRIND_ROOT_FUNCTION_NAME
        )
        for function, entry in records.items():
            if function in kept:
                self.function_accumulate(profile, function, entry)
        profile.summary = profile.zeros()
        for costs in profile.line_self.values():
            costs_add(profile.summary, costs)
        self.entries_fill(profile)
        return profile

    # Reads the header into the profile and each function's cost lines.
    def records_read(
        self, text: str, path: str, profile: Profile
    ) -> dict[str, FunctionRecords]:
        records: dict[str, FunctionRecords] = {}
        names = Callgrind.CompressedNames()
        positions = Callgrind.PositionDecoder()

        counter_count = 0
        current: FunctionRecords | None = None
        current_file = "???"
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
                if current is None:
                    sys.exit(
                        f"error: {path}: a cost line before the first fn="
                        f" line: {raw_line}"
                    )
                tokens = raw_line.split()
                line = positions.step(tokens)
                costs = [int(token) for token in tokens[positions.count :]]
                if len(costs) < counter_count:
                    costs.extend([0] * (counter_count - len(costs)))
                key = SourceLine(current_file, line)
                if pending_call is not None:
                    current.call_records.append(
                        CallRecord(
                            key,
                            cur_callee_function or "???",
                            cur_callee_file
                            if cur_callee_file is not None
                            else current_file,
                            current_callee_object or current_object,
                            pending_call.call_count,
                            pending_call.target_line,
                            costs,
                        )
                    )
                    cur_callee_file = None
                    current_callee_object = None
                    pending_call = None
                else:
                    current.self_records.append(
                        SelfRecord(key, current_object, costs)
                    )
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
                    current_file = file_key(
                        names.uncompress("fl", specification_value),
                        current_object,
                    )
                elif key == "fn":
                    function = self.function_name(
                        names, specification_value, current_object, path
                    )
                    current = records.get(function)
                    if current is None:
                        current = records[function] = FunctionRecords(
                            current_file
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
                    cur_callee_file = file_key(
                        names.uncompress("fl", specification_value),
                        current_callee_object or current_object,
                    )
                elif key == "cfn":
                    cur_callee_function = self.function_name(
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
        return records

    # Returns the root function and every function the calls reach from it.
    def root_reach(
        self, records: dict[str, FunctionRecords], path: str
    ) -> set[str]:
        root = _CALLGRIND_ROOT_FUNCTION_NAME
        if root not in records:
            sys.exit(
                f"error: {path} records no function {root}, the one the"
                " recording is cut at"
            )
        reached = {root}
        pending = [root]
        while pending:
            function = pending.pop()
            if function not in records:
                sys.exit(
                    f"error: {path} calls {function} but records no cost"
                    " block of that function"
                )
            for call in records[function].call_records:
                if call.callee not in reached:
                    reached.add(call.callee)
                    pending.append(call.callee)
        return reached

    # Refuses a recording whose cost lines do not add up to its summary.
    def summary_check(
        self,
        profile: Profile,
        records: dict[str, FunctionRecords],
        path: str,
    ) -> None:
        self_sum = sum(
            self_record.costs[0]
            for entry in records.values()
            for self_record in entry.self_records
            if self_record.costs
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


_profile_parser = Callgrind()


def address_names_resolve(
    text: str, address_name_resolve: Callable[[str | None, str], str | None]
) -> str:
    return _profile_parser.address_names_resolve(text, address_name_resolve)


def baseline_line_key(display: str, line: int | str) -> str:
    return f"{display}\n{line}"


# Returns each function calling the callee, its calls and first call line.
def caller_calls(profile: Profile, callee: str) -> dict[str, CallerCalls]:
    calls: dict[str, CallerCalls] = {}
    for caller, tally in profile.callers.get(callee, {}).items():
        known = calls.get(caller.function, CallerCalls(0, caller.line))
        calls[caller.function] = CallerCalls(
            known.calls + tally.count, min(known.line, caller.line)
        )
    return calls


def cached_source(display: str) -> str | None:
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


# Returns the counters a profile records, read no further than its events.
def counters_read(directory: str, kind: str, test_name: str) -> list[str]:
    with artifacts.artifact_open(directory, kind, test_name, "rb") as handle:
        for raw_line in handle:
            key, separator, header_value = raw_line.decode(
                "utf-8", errors="replace"
            ).partition(":")
            if separator and key == "events":
                return header_value.split()
    path = artifacts.artifact_path(directory, kind, test_name)
    sys.exit(f"error: no 'events:' line -- not a callgrind file? ({path})")


# Returns the path a page shows, an external one under its object's name.
def display_path(canonical: str, group: str, object_path: str) -> str:
    if group != _CALLGRIND_FILE_DATA_ERROR_CODE:
        return canonical
    owner = os.path.basename(object_path) or "(unknown object)"
    return f"{owner}/{canonical}"


def file_key(path: str, object_path: str) -> str:
    if path != _CALLGRIND_UNKNOWN_NAME:
        return path
    return f"{os.path.basename(object_path)}/{path}"


# There is no i18n path for Python yet. Just don't name your file "(unknown)".
def path_canonical(path: str) -> str:
    if posixpath.basename(path) == _CALLGRIND_UNKNOWN_NAME:
        return "(unknown)"
    return posixpath.normpath(repo_root_strip(path)).lstrip("/")


def path_norm(path: str) -> PathInfo:
    display = path_canonical(path)
    if posixpath.basename(path) == _CALLGRIND_UNKNOWN_NAME:
        return PathInfo(display, None, _CALLGRIND_FILE_DATA_ERROR_CODE)
    root = REPO_ROOT + "/"
    if os.path.isabs(path):
        path = posixpath.normpath(path)
    if path.startswith(root):
        local = os.path.join(REPO_ROOT, path[len(root) :])
        if os.path.isfile(local):
            return PathInfo(display, local, _CALLGRIND_FILE_DATA_REPO_CODE)
        return PathInfo(display, None, _CALLGRIND_FILE_DATA_ERROR_CODE)
    if os.path.isabs(path):
        if os.path.isfile(path):
            return PathInfo(display, path, _CALLGRIND_FILE_DATA_SYSTEM_CODE)
        return PathInfo(display, None, _CALLGRIND_FILE_DATA_ERROR_CODE)
    candidate = os.path.join(REPO_ROOT, path)
    if os.path.isfile(candidate):
        return PathInfo(display, candidate, _CALLGRIND_FILE_DATA_REPO_CODE)
    cached = cached_source(display)
    if cached is not None:
        return PathInfo(display, cached, _CALLGRIND_FILE_DATA_SYSTEM_CODE)
    return PathInfo(display, None, _CALLGRIND_FILE_DATA_ERROR_CODE)


def profile_load(directory: str, kind: str, test_name: str) -> Profile:
    return _profile_parser.load(directory, kind, test_name)


def ranking_counter_check(counters: Sequence[str], source: str) -> None:
    if _RANKING_COUNTER_NAME in counter_names(counters):
        return
    sys.exit(
        f"error: {source} cannot supply {_RANKING_COUNTER_NAME}, the"
        f" counter every page ranks and divides by: it records"
        f" {' '.join(counters)}"
    )


# Cuts the repository root as the archived recordings have it cut.
def repo_root_strip(text: str) -> str:
    return text.replace(REPO_ROOT + "/", "")


def tally_accumulate(
    table: dict[_Key, Tally], key: _Key, count: int, costs: Costs
) -> None:
    current = table.get(key)
    if current is None:
        table[key] = Tally(count, list(costs))
    else:
        current.count += count
        costs_add(current.costs, costs)
