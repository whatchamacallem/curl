# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import collections, dataclasses, functools, json, os, posixpath, re, sys
from collections.abc import Collection, Iterable, Sequence
from typing import NamedTuple, TypeAlias, TypedDict, TypeVar

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artifacts, settings

_CACHE_ROOT_DIR: str = ""
_CALLGRIND_FILE_DATA_CODE_KEY: str = ""
_CALLGRIND_FILE_DATA_ERROR_CODE: str = ""
_CALLGRIND_FILE_DATA_GIT_CODE: str = ""
_CALLGRIND_FILE_DATA_PATH_KEY: str = ""
_CALLGRIND_FILE_DATA_REPO_CODE: str = ""
_CALLGRIND_FILE_DATA_SYSTEM_CODE: str = ""
_CALLGRIND_FORMAT_CALLEE_FILE_KEYS: tuple[str, ...] = ()
_CALLGRIND_FORMAT_CALLEE_FUNCTION_KEY: str = ""
_CALLGRIND_FORMAT_CALLEE_IMAGE_KEY: str = ""
_CALLGRIND_FORMAT_CALLS_KEY: str = ""
_CALLGRIND_FORMAT_COMMAND_KEY: str = ""
_CALLGRIND_FORMAT_COUNTERS_KEY: str = ""
_CALLGRIND_FORMAT_FILE_KEY: str = ""
_CALLGRIND_FORMAT_FUNCTION_KEY: str = ""
_CALLGRIND_FORMAT_IMAGE_KEY: str = ""
_CALLGRIND_FORMAT_INLINE_FILE_KEYS: tuple[str, ...] = ()
_CALLGRIND_FORMAT_JUMP_FILE_KEY: str = ""
_CALLGRIND_FORMAT_JUMP_FUNCTION_KEY: str = ""
_CALLGRIND_FORMAT_LINE_POSITION_NAME: str = ""
_CALLGRIND_FORMAT_POSITIONS_KEY: str = ""
_CALLGRIND_FORMAT_SUMMARY_KEYS: tuple[str, ...] = ()
_CALLGRIND_NAME_COMPRESSION_PATTERN: str = ""
_CALLGRIND_UNKNOWN_DISPLAY_PATH: str = ""
_CALLGRIND_UNKNOWN_NAME: str = ""
_DERIVED_COUNTER_TERMS: dict[str, dict[str, int]] = {}
_RANKING_COUNTER_NAME: str = ""
settings.load_into(__name__)

Costs: TypeAlias = list[int]

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
)

_Key = TypeVar("_Key")


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
    costs: Costs


class CallRecord(NamedTuple):
    key: SourceLine
    image_path: str
    callee: FunctionKey
    callee_file: str
    call_count: int
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
        baseline = file_data_read(baseline_dir)
        baseline_document = artifacts.artifact_path(baseline_dir, "file-data")
        self.tracked = [
            entry.path
            for entry in baseline
            if entry.code == _CALLGRIND_FILE_DATA_GIT_CODE
        ]
        self.files: dict[str, DerivedPath] = {}
        for document, entries, in_baseline in (
            (baseline_document, baseline, True),
            (
                artifacts.artifact_path(modified_dir, "file-data"),
                file_data_read(modified_dir),
                False,
            ),
        ):
            for entry in entries:
                if entry.code == _CALLGRIND_FILE_DATA_GIT_CODE:
                    continue
                shown = DerivedPath(
                    entry.path,
                    entry.code,
                    entry.code != _CALLGRIND_FILE_DATA_ERROR_CODE,
                    in_baseline,
                )
                known = self.files.setdefault(entry.path, shown)
                if known.group != shown.group:
                    sys.exit(
                        f"error: the two reports code {entry.path} apart:"
                        f" {known.group} in {baseline_document},"
                        f" {shown.group} in {document}"
                    )

    # Returns the path a diff shows of a recorded path of an image.
    def display(self, path: str, image_path: str) -> str:
        entry = self.path_entry(path)
        return display_path(entry.canonical, entry.group, image_path)

    def path_entry(self, path: str) -> DerivedPath:
        canonical = path_canonical(path)
        entry = self.files.get(canonical)
        if entry is None:
            sys.exit(
                f"error: neither report's file data names {canonical},"
                f" recorded as {path}"
            )
        return entry


class FileEntry(NamedTuple):
    path: str
    code: str


# Holds a test's function data, each file and image by its list index.
class FunctionDataDocument(TypedDict):
    counters: list[str]
    images: list[str]
    functions: list[FunctionDataRow]


# Holds a function's name, image, place, self costs, callers and callees.
class FunctionDataRow(NamedTuple):
    function_name: str
    image_index: int
    file_index: int
    line_number: int
    self_costs: Costs
    # Each caller's row index then its calls, one caller after another.
    caller_pairs: list[int]
    # Each callee's row index then its calls, one callee after another.
    callee_pairs: list[int]


# Names a function as callgrind does, by its image and its name.
class FunctionKey(NamedTuple):
    image_path: str
    name: str


# Holds a diff function, its name, shown location and each report's key.
class FunctionPair(NamedTuple):
    name: str
    location: str
    baseline: FunctionKey | None
    modified: FunctionKey | None


# Holds one function's cost lines as read.
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
    file_image: dict[str, str] = dataclasses.field(default_factory=dict)

    def resolved_derived_counters(self) -> list[ResolvedDerivedCounter]:
        return resolved_derived_counters(self.counters)

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
    function_keys: dict[str, FunctionKey] = dataclasses.field(
        default_factory=dict
    )


# Holds a recording's header, cost lines and the line each callee is entered.
class Recording(NamedTuple):
    path: str
    profile: Profile
    records: dict[FunctionKey, FunctionRecords]
    entries: dict[FunctionKey, SourceLine]


class ResolvedDerivedCounter(NamedTuple):
    name: str
    terms: tuple[ResolvedTerm, ...]


class ResolvedTerm(NamedTuple):
    coefficient: int
    counter_index: int


class SelfRecord(NamedTuple):
    key: SourceLine
    image_path: str
    costs: Costs


class SourceLine(NamedTuple):
    file: str
    line: int


@dataclasses.dataclass
class Tally:
    count: int
    costs: Costs


class Callgrind:
    NAME_COMPRESSION_RE = re.compile(_CALLGRIND_NAME_COMPRESSION_PATTERN)

    class CompressedNames:
        def __init__(self) -> None:
            self.names: dict[str, dict[str, str]] = {
                _CALLGRIND_FORMAT_FILE_KEY: {},
                _CALLGRIND_FORMAT_FUNCTION_KEY: {},
                _CALLGRIND_FORMAT_IMAGE_KEY: {},
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
        callee: FunctionKey

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
                names.index(_CALLGRIND_FORMAT_LINE_POSITION_NAME)
                if _CALLGRIND_FORMAT_LINE_POSITION_NAME in names
                else self.count - 1
            )
            self.previous = [0] * self.count

        def step(self, tokens: Sequence[str]) -> int:
            for position in range(self.count):
                self.previous[position] = self.decode(
                    tokens[position], position
                )
            return self.previous[self.line_index]

    # Refuses a recording calling a function it records no cost block of.
    def callees_check(
        self, records: dict[FunctionKey, FunctionRecords], path: str
    ) -> None:
        for entry in records.values():
            for call in entry.call_records:
                if call.callee not in records:
                    sys.exit(
                        f"error: {path} calls {call.callee.name} of"
                        f" {call.callee.image_path} but records no cost block"
                        " of that function"
                    )

    # Records the line a call enters its callee at, refusing a second line.
    def entry_record(
        self,
        entries: dict[FunctionKey, SourceLine],
        callee: FunctionKey,
        line: SourceLine,
        path: str,
    ) -> None:
        known = entries.setdefault(callee, line)
        if known != line:
            sys.exit(
                f"error: {path}: calls enter {callee.name} of"
                f" {callee.image_path} at {known.file}:{known.line} and at"
                f" {line.file}:{line.line}"
            )

    # Adds a function's records to the profile, in the order read.
    def function_accumulate(
        self,
        profile: Profile,
        function: str,
        records: FunctionRecords,
        names: dict[FunctionKey, str],
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
            profile.file_image.setdefault(
                self_record.key.file, self_record.image_path
            )
        for call in records.call_records:
            costs_accumulate(profile.line_calls, call.key, call.costs)
            profile.line_call_count[call.key] += call.call_count
            profile.file_image.setdefault(call.key.file, call.image_path)
            costs_accumulate(profile.function_calls, function, call.costs)
            profile.function_call_lines[function].add(call.key)
            callee = names[call.callee]
            tally_accumulate(
                profile.callees,
                CallSite(call.key.file, call.key.line, callee),
                call.call_count,
                call.costs,
            )
            tally_accumulate(
                profile.callers[callee],
                Caller(function, call.key.file, call.key.line),
                call.call_count,
                call.costs,
            )
            profile.function_home.setdefault(callee, call.callee_file)
            profile.file_image.setdefault(
                call.callee_file, call.callee.image_path
            )

    # Refuses a function in no image, which the recording bills to its caller.
    def function_key(
        self,
        names: Callgrind.CompressedNames,
        compressed_name: str,
        image_path: str,
        path: str,
    ) -> FunctionKey:
        name = names.uncompress(
            _CALLGRIND_FORMAT_FUNCTION_KEY, compressed_name
        )
        if image_path == _CALLGRIND_UNKNOWN_NAME:
            sys.exit(f"error: {path}: function {name} lies in no image")
        return FunctionKey(image_path, name)

    # Returns each function's shown name, a shared one under its image's.
    def function_names(
        self, keys: Collection[FunctionKey]
    ) -> dict[FunctionKey, str]:
        image_names = self.image_names(keys)
        shared_names = self.shared_names(keys)
        return {
            key: (
                f"{image_names[key.image_path]}/{key.name}"
                if key.name in shared_names
                else key.name
            )
            for key in keys
        }

    # Returns each image's file name, its path when two images share one.
    def image_names(self, keys: Iterable[FunctionKey]) -> dict[str, str]:
        base_paths: dict[str, set[str]] = {}
        for key in keys:
            base_paths.setdefault(os.path.basename(key.image_path), set()).add(
                key.image_path
            )
        return {
            path: base_name if len(paths) == 1 else repo_root_strip(path)
            for base_name, paths in base_paths.items()
            for path in paths
        }

    # Returns the profile of the text, refusing one that does not add up.
    def parse(self, text: str, path: str) -> Profile:
        recording = self.recording_read(text, path)
        return self.profile_name(
            recording, self.function_names(recording.records)
        )

    # Returns a recording's profile, each function under its shown name.
    def profile_name(
        self, recording: Recording, names: dict[FunctionKey, str]
    ) -> Profile:
        for key, entry in recording.records.items():
            self.function_accumulate(
                recording.profile, names[key], entry, names
            )
            recording.profile.function_keys[names[key]] = key
        # A call made before collection names a function holding no record.
        for key, line in recording.entries.items():
            if key in recording.records:
                recording.profile.function_entry[names[key]] = line
                recording.profile.file_image.setdefault(
                    line.file, key.image_path
                )
        return recording.profile

    # Reads a test's recording or delta of a directory.
    def recording_load(
        self, directory: str, kind: str, test_name: str
    ) -> Recording:
        with artifacts.artifact_open(
            directory, kind, test_name, "rb"
        ) as handle:
            text = handle.read().decode("utf-8", errors="replace")
        return self.recording_read(
            text, artifacts.artifact_path(directory, kind, test_name)
        )

    # Reads a recording, refusing one that does not add up.
    def recording_read(self, text: str, path: str) -> Recording:
        profile = Profile()
        entries: dict[FunctionKey, SourceLine] = {}
        records = self.records_read(text, path, profile, entries)
        if not profile.counters:
            sys.exit(
                f"error: no 'events:' line -- not a callgrind file? ({path})"
            )
        self.summary_check(profile, records, path)
        self.callees_check(records, path)
        return Recording(path, profile, records, entries)

    # Reads the header, each function's cost lines and the line calls enter.
    def records_read(
        self,
        text: str,
        path: str,
        profile: Profile,
        entries: dict[FunctionKey, SourceLine],
    ) -> dict[FunctionKey, FunctionRecords]:
        records: dict[FunctionKey, FunctionRecords] = {}
        names = Callgrind.CompressedNames()
        positions = Callgrind.PositionDecoder()

        counter_count = 0
        current: FunctionRecords | None = None
        current_function: FunctionKey | None = None
        current_home = _CALLGRIND_UNKNOWN_NAME
        current_file = _CALLGRIND_UNKNOWN_NAME
        current_image = _CALLGRIND_UNKNOWN_NAME
        current_callee_image: str | None = None
        cur_callee_file: str | None = None
        cur_callee_function: FunctionKey | None = None
        pending_call: Callgrind.PendingCall | None = None

        for raw_line in text.split("\n"):
            if not raw_line or raw_line[0] == "#":
                continue
            first_char = raw_line[0]
            if first_char.isdigit() or first_char in "+-*":
                if current_function is None:
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
                call_record: CallRecord | None = None
                if pending_call is not None:
                    callee_file = (
                        cur_callee_file
                        if cur_callee_file is not None
                        else current_file
                    )
                    self.entry_record(
                        entries,
                        pending_call.callee,
                        SourceLine(callee_file, pending_call.target_line),
                        path,
                    )
                    call_record = CallRecord(
                        key,
                        current_image,
                        pending_call.callee,
                        callee_file,
                        pending_call.call_count,
                        costs,
                    )
                    cur_callee_file = None
                    current_callee_image = None
                    cur_callee_function = None
                    pending_call = None
                    # A call counting no calls began before collection did.
                    if not call_record.call_count:
                        continue
                # Homes a function where its first block with a record starts.
                if current is None:
                    current = records[current_function] = FunctionRecords(
                        current_home
                    )
                if call_record is None:
                    current.self_records.append(
                        SelfRecord(key, current_image, costs)
                    )
                else:
                    current.call_records.append(call_record)
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
                if (
                    key == _CALLGRIND_FORMAT_FILE_KEY
                    or key in _CALLGRIND_FORMAT_INLINE_FILE_KEYS
                ):
                    current_file = file_key(
                        names.uncompress(
                            _CALLGRIND_FORMAT_FILE_KEY, specification_value
                        ),
                        current_image,
                    )
                elif key == _CALLGRIND_FORMAT_FUNCTION_KEY:
                    current_function = self.function_key(
                        names, specification_value, current_image, path
                    )
                    current = records.get(current_function)
                    current_home = current_file
                    cur_callee_file = None
                elif key == _CALLGRIND_FORMAT_IMAGE_KEY:
                    current_image = names.uncompress(
                        _CALLGRIND_FORMAT_IMAGE_KEY, specification_value
                    )
                elif key == _CALLGRIND_FORMAT_CALLEE_IMAGE_KEY:
                    current_callee_image = names.uncompress(
                        _CALLGRIND_FORMAT_IMAGE_KEY, specification_value
                    )
                elif key in _CALLGRIND_FORMAT_CALLEE_FILE_KEYS:
                    cur_callee_file = file_key(
                        names.uncompress(
                            _CALLGRIND_FORMAT_FILE_KEY, specification_value
                        ),
                        current_callee_image or current_image,
                    )
                elif key == _CALLGRIND_FORMAT_CALLEE_FUNCTION_KEY:
                    cur_callee_function = self.function_key(
                        names,
                        specification_value,
                        current_callee_image or current_image,
                        path,
                    )
                elif key == _CALLGRIND_FORMAT_JUMP_FILE_KEY:
                    names.uncompress(
                        _CALLGRIND_FORMAT_FILE_KEY, specification_value
                    )
                elif key == _CALLGRIND_FORMAT_JUMP_FUNCTION_KEY:
                    names.uncompress(
                        _CALLGRIND_FORMAT_FUNCTION_KEY, specification_value
                    )
                elif key == _CALLGRIND_FORMAT_CALLS_KEY:
                    parts = specification_value.split()
                    if len(parts) <= 1 + positions.line_index:
                        sys.exit(f"error: malformed 'calls=' line: {raw_line}")
                    if cur_callee_function is None:
                        sys.exit(
                            f"error: {path}: a {_CALLGRIND_FORMAT_CALLS_KEY}="
                            " line with no"
                            f" {_CALLGRIND_FORMAT_CALLEE_FUNCTION_KEY}= line"
                            f" since the last call: {raw_line}"
                        )
                    target_line = positions.decode(
                        parts[1 + positions.line_index], positions.line_index
                    )
                    pending_call = Callgrind.PendingCall(
                        int(parts[0]), target_line, cur_callee_function
                    )
                continue
            if colon_index == -1:
                continue
            key, header_value = (
                raw_line[:colon_index],
                raw_line[colon_index + 1 :].strip(),
            )
            if key == _CALLGRIND_FORMAT_COUNTERS_KEY:
                profile.counters = header_value.split()
                counter_count = len(profile.counters)
            elif key == _CALLGRIND_FORMAT_POSITIONS_KEY:
                positions.reset(header_value.split())
            elif key == _CALLGRIND_FORMAT_COMMAND_KEY:
                profile.command = header_value
            elif key in _CALLGRIND_FORMAT_SUMMARY_KEYS:
                values = [int(v) for v in header_value.split()]
                if len(values) >= len(profile.summary):
                    profile.summary = values
        return records

    # Returns the names two images record.
    def shared_names(self, keys: Iterable[FunctionKey]) -> set[str]:
        image_paths: dict[str, set[str]] = {}
        for key in keys:
            image_paths.setdefault(key.name, set()).add(key.image_path)
        return {name for name, paths in image_paths.items() if len(paths) > 1}

    # Refuses a recording whose cost lines do not add up to its summary.
    def summary_check(
        self,
        profile: Profile,
        records: dict[FunctionKey, FunctionRecords],
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
        if abs(ratio - 1.0) > 1e-6:
            sys.exit(
                f"error: per-line self cost {self_sum} is {ratio:.4f} of"
                f" callgrind's summary {total}, expected 1.0000 ({path})"
            )


_profile_parser = Callgrind()


def baseline_line_key(display: str, line: int | str) -> str:
    return f"{display}\n{line}"


# Returns each caller of the callee, its calls, first call line and costs.
def caller_calls(profile: Profile, callee: str) -> dict[str, CallerCalls]:
    calls: dict[str, CallerCalls] = {}
    for caller, tally in profile.callers.get(callee, {}).items():
        known = calls.get(
            caller.function, CallerCalls(0, caller.line, profile.zeros())
        )
        costs_add(known.costs, tally.costs)
        calls[caller.function] = CallerCalls(
            known.calls + tally.count,
            min(known.line, caller.line),
            known.costs,
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
            if separator and key == _CALLGRIND_FORMAT_COUNTERS_KEY:
                return header_value.split()
    path = artifacts.artifact_path(directory, kind, test_name)
    sys.exit(f"error: no 'events:' line -- not a callgrind file? ({path})")


# Returns the path a page shows, an external one under its image's name.
def display_path(canonical: str, group: str, image_path: str) -> str:
    if group != _CALLGRIND_FILE_DATA_ERROR_CODE:
        return canonical
    return f"{os.path.basename(image_path)}/{canonical}"


# Returns a report's paths document in index order, refusing a malformed one.
def file_data_read(directory: str) -> list[FileEntry]:
    path = artifacts.artifact_path(directory, "file-data")
    with artifacts.artifact_open(directory, "file-data") as handle:
        document = json.load(handle)
    keys = sorted(
        (_CALLGRIND_FILE_DATA_CODE_KEY, _CALLGRIND_FILE_DATA_PATH_KEY)
    )
    codes = (
        _CALLGRIND_FILE_DATA_ERROR_CODE,
        _CALLGRIND_FILE_DATA_GIT_CODE,
        _CALLGRIND_FILE_DATA_REPO_CODE,
        _CALLGRIND_FILE_DATA_SYSTEM_CODE,
    )
    entries: list[FileEntry] = []
    for item in document:
        if not isinstance(item, dict) or sorted(item) != keys:
            sys.exit(
                f"error: {path} holds {item!r}, which is no object of the"
                f" keys {' '.join(keys)}"
            )
        entry = FileEntry(
            item[_CALLGRIND_FILE_DATA_PATH_KEY],
            item[_CALLGRIND_FILE_DATA_CODE_KEY],
        )
        if entry.code not in codes:
            sys.exit(
                f"error: {path} codes {entry.path} as {entry.code!r}, which"
                f" is none of {' '.join(codes)}"
            )
        if entries and entry.path <= entries[-1].path:
            sys.exit(
                f"error: {path} lists {entry.path} after {entries[-1].path},"
                " out of path order"
            )
        entries.append(entry)
    return entries


def file_key(path: str, image_path: str) -> str:
    if path != _CALLGRIND_UNKNOWN_NAME:
        return path
    return f"{os.path.basename(image_path)}/{path}"


# Returns a test's function data document, refusing one of other keys.
def function_data_parse(text: str, path: str) -> FunctionDataDocument:
    document = json.loads(text)
    keys = sorted(FunctionDataDocument.__required_keys__)
    found_keys = sorted(document) if isinstance(document, dict) else []
    if found_keys != keys:
        sys.exit(f"error: {path} holds no object of the keys {' '.join(keys)}")
    function_rows = [
        FunctionDataRow(*function_row)
        for function_row in document["functions"]
    ]
    return {
        "counters": document["counters"],
        "images": document["images"],
        "functions": function_rows,
    }


# Returns a test's function data document of a report's archive.
def function_data_read(directory: str, test_name: str) -> FunctionDataDocument:
    with artifacts.artifact_open(
        directory, "function-data", test_name
    ) as handle:
        return function_data_parse(
            handle.read(),
            artifacts.artifact_path(directory, "function-data", test_name),
        )


# Returns each report's shown names of a diff's paired functions.
def function_pair_names(
    key_sets: tuple[Collection[FunctionKey], Collection[FunctionKey]],
    build_trees: tuple[str, str],
) -> tuple[dict[FunctionKey, str], dict[FunctionKey, str]]:
    pairs = function_pairs(key_sets, build_trees)
    name_counts = collections.Counter(pair.name for pair in pairs)
    base_locations: dict[str, set[str]] = {}
    for pair in pairs:
        base_locations.setdefault(os.path.basename(pair.location), set()).add(
            pair.location
        )
    names: tuple[dict[FunctionKey, str], dict[FunctionKey, str]] = ({}, {})
    for pair in pairs:
        base_name = os.path.basename(pair.location)
        image_name = (
            base_name if len(base_locations[base_name]) == 1 else pair.location
        )
        shown_name = (
            f"{image_name}/{pair.name}"
            if name_counts[pair.name] > 1
            else pair.name
        )
        for side_names, key in zip(
            names, (pair.baseline, pair.modified), strict=True
        ):
            if key is not None:
                side_names[key] = shown_name
    return names


# Pairs a diff's functions of a name by location, a lone rest of each moved.
def function_pairs(
    key_sets: tuple[Collection[FunctionKey], Collection[FunctionKey]],
    build_trees: tuple[str, str],
) -> list[FunctionPair]:
    located: dict[
        str, tuple[dict[str, FunctionKey], dict[str, FunctionKey]]
    ] = {}
    for side, (keys, build_tree) in enumerate(
        zip(key_sets, build_trees, strict=True)
    ):
        for key in keys:
            location = image_location(key.image_path, build_tree)
            known = located.setdefault(key.name, ({}, {}))[side].setdefault(
                location, key
            )
            if known != key:
                sys.exit(
                    f"error: ambiguous resolution of overloads of {key.name}:"
                    f" {known.image_path} and {key.image_path} lie at"
                    f" {location}"
                )
    pairs: list[FunctionPair] = []
    for name in sorted(located):
        baseline_at, modified_at = located[name]
        pairs.extend(
            FunctionPair(
                name, location, baseline_at[location], modified_at[location]
            )
            for location in sorted(baseline_at.keys() & modified_at.keys())
        )
        baseline_left = sorted(baseline_at.keys() - modified_at.keys())
        modified_left = sorted(modified_at.keys() - baseline_at.keys())
        if len(baseline_left) == 1 and len(modified_left) == 1:
            pairs.append(
                FunctionPair(
                    name,
                    modified_left[0],
                    baseline_at[baseline_left[0]],
                    modified_at[modified_left[0]],
                )
            )
        elif baseline_left and modified_left:
            sys.exit(
                f"error: ambiguous resolution of overloads of {name}:"
                f" {' '.join(baseline_left)} in the baseline,"
                f" {' '.join(modified_left)} in the modified build"
            )
        else:
            pairs.extend(
                FunctionPair(name, location, baseline_at[location], None)
                for location in baseline_left
            )
            pairs.extend(
                FunctionPair(name, location, None, modified_at[location])
                for location in modified_left
            )
    return pairs


# Returns an image's location, its path less its report's build tree.
def image_location(image_path: str, build_tree: str) -> str:
    return image_path.removeprefix(f"{build_tree}/")


# There is no i18n path for Python yet. Just don't name your file "(unknown)".
def path_canonical(path: str) -> str:
    if posixpath.basename(path) == _CALLGRIND_UNKNOWN_NAME:
        return _CALLGRIND_UNKNOWN_DISPLAY_PATH
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
    recording = _profile_parser.recording_load(directory, kind, test_name)
    return _profile_parser.profile_name(
        recording, _profile_parser.function_names(recording.records)
    )


# Loads a diff's two recordings of a test, named by their paired functions.
def profile_pair_load(
    baseline_dir: str,
    modified_dir: str,
    test_name: str,
    build_trees: tuple[str, str],
) -> tuple[Profile, Profile]:
    baseline, modified = (
        _profile_parser.recording_load(directory, "callgrind", test_name)
        for directory in (baseline_dir, modified_dir)
    )
    baseline_names, modified_names = function_pair_names(
        (baseline.records, modified.records), build_trees
    )
    return (
        _profile_parser.profile_name(baseline, baseline_names),
        _profile_parser.profile_name(modified, modified_names),
    )


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


# Returns each derived counter the recorded counters supply, with its terms.
def resolved_derived_counters(
    counters: Sequence[str],
) -> list[ResolvedDerivedCounter]:
    return list(counter_schema(tuple(counters)).derived_counters)


def tally_accumulate(
    table: dict[_Key, Tally], key: _Key, count: int, costs: Costs
) -> None:
    current = table.get(key)
    if current is None:
        table[key] = Tally(count, list(costs))
    else:
        current.count += count
        costs_add(current.costs, costs)
