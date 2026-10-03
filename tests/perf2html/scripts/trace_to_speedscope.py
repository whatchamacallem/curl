#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, array, json, os, subprocess, sys
from typing import NamedTuple, NotRequired, TextIO, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind, settings

_FLAME_GRAPH_EXPORTER_NAME: str = ""
_FLAME_GRAPH_MAX_RECORDED_CALLS: int = 0
settings.load_into(__name__)

_BUILDID_KEYWORD = "buildid"

_BUILDID_LABEL = "Build ID"

_FUNCTION_EXIT_BIT = 1 << 63

_FLAME_GRAPH_FILE_FORMAT_SCHEMA_URL = (
    "https://www.speedscope.app/file-format-schema.json"
)

_HEADER_WORDS = 8

_HEADER_MAGIC = 0xABCDEF0123456789

_RECORD_WORDS = 2


class Event(TypedDict):
    type: str
    frame: int
    at: int


class EventedProfile(TypedDict):
    type: str
    name: str
    unit: str
    startValue: int
    endValue: int
    events: list[Event]


class Frame(TypedDict):
    name: str
    file: NotRequired[str]
    line: NotRequired[int]


class Shared(TypedDict):
    frames: list[Frame]


SpeedscopeDoc = TypedDict(
    "SpeedscopeDoc",
    {
        "$schema": str,
        "shared": Shared,
        "profiles": list[EventedProfile],
        "name": str,
        "exporter": str,
    },
)


class TraceToSpeedscope:
    class CallSpan(NamedTuple):
        first: int
        last: int

    class ExecutableMapping(NamedTuple):
        low: int
        high: int
        offset: int
        path: str

    class LoadSegment(NamedTuple):
        offset: int
        size: int
        address: int

    class TraceArgs(NamedTuple):
        trace_file: str
        output: str
        name: str

    class TraceRecording(NamedTuple):
        seen: int
        skip: int
        origin_tsc: int
        tsc_per_ns: float
        functions: list[int]
        stamps: list[int]

    def buildid_read(self, path: str) -> str:
        listing = subprocess.run(
            ["readelf", "-n", path],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        for line in listing.splitlines():
            label, separator, value = line.partition(":")
            if separator and label.strip() == _BUILDID_LABEL:
                return value.strip().lower()
        return ""

    def buildid_verify(
        self, maps_file: str, recorded: dict[str, str], path: str
    ) -> None:
        want = recorded.get(path)
        if want is None:
            sys.exit(
                f"error: {maps_file} records no build-id for {path}, so the"
                " trace cannot be shown to have come from the build on disk"
            )
        found = self.buildid_read(path)
        if found != want:
            sys.exit(
                f"error: {path} was rebuilt since the trace was recorded:"
                f" it now has build-id {found or '(none)'}, the trace was"
                f" recorded against {want}. Re-record the trace"
            )

    def buildids_read(self, maps_file: str) -> dict[str, str]:
        out: dict[str, str] = {}
        with self.text_open(maps_file) as handle:
            for line in handle:
                fields = line.split(None, 2)
                if len(fields) == 3 and fields[0] == _BUILDID_KEYWORD:
                    out[fields[2].strip()] = fields[1].lower()
        return out

    def calls(
        self, trace: TraceToSpeedscope.TraceRecording
    ) -> list[TraceToSpeedscope.CallSpan]:
        runs: list[list[TraceToSpeedscope.CallSpan]] = [[]]
        open_records: list[int] = []
        for record, function in enumerate(trace.functions):
            if not trace.stamps[record] & _FUNCTION_EXIT_BIT:
                open_records.append(record)
            elif not open_records:
                runs.append([])
            else:
                first = open_records.pop()
                if trace.functions[first] != function:
                    sys.exit(
                        f"error: record {record}: exit of {function:#x}"
                        f" closes {trace.functions[first]:#x}"
                    )
                if not open_records:
                    runs[-1].append(TraceToSpeedscope.CallSpan(first, record))
        return max(
            runs,
            key=lambda run: sum(call.last - call.first + 1 for call in run),
        )

    def document(
        self,
        trace: TraceToSpeedscope.TraceRecording,
        calls: list[TraceToSpeedscope.CallSpan],
        frames: dict[int, Frame],
        name: str,
    ) -> SpeedscopeDoc:
        first, last = calls[0].first, calls[-1].last
        order: dict[int, int] = {}
        events: list[Event] = []
        for record in range(first, last + 1):
            stamp = trace.stamps[record]
            frame = order.setdefault(trace.functions[record], len(order))
            at = round(
                ((stamp & ~_FUNCTION_EXIT_BIT) - trace.origin_tsc)
                / trace.tsc_per_ns
            )
            events.append(
                {
                    "type": "C" if stamp & _FUNCTION_EXIT_BIT else "O",
                    "frame": frame,
                    "at": at,
                }
            )
        profile_name = (
            f"rdtsc trace (-finstrument-functions), {len(calls)} calls,"
            f" events {trace.skip + first + 1:,}"
            f"..{trace.skip + last + 1:,} of {trace.seen:,}"
        )
        return {
            "$schema": _FLAME_GRAPH_FILE_FORMAT_SCHEMA_URL,
            "shared": {"frames": [frames[function] for function in order]},
            "profiles": [
                {
                    "type": "evented",
                    "name": profile_name,
                    "unit": "nanoseconds",
                    "startValue": events[0]["at"],
                    "endValue": events[-1]["at"],
                    "events": events,
                }
            ],
            "name": name,
            "exporter": _FLAME_GRAPH_EXPORTER_NAME,
        }

    def frames(
        self, trace_file: str, functions: list[int]
    ) -> dict[int, Frame]:
        maps_file = trace_file + ".maps"
        mappings = self.mappings_read(maps_file)
        recorded = self.buildids_read(maps_file)
        segments: dict[str, list[TraceToSpeedscope.LoadSegment]] = {}
        by_object: dict[str, dict[int, int]] = {}
        for function in functions:
            mapping = next(
                (m for m in mappings if m.low <= function < m.high), None
            )
            if mapping is None:
                sys.exit(
                    f"error: {function:#x} is in no executable mapping of "
                    f"{maps_file}"
                )
            if mapping.path not in segments:
                self.buildid_verify(maps_file, recorded, mapping.path)
                segments[mapping.path] = self.segments_read(mapping.path)
            by_object.setdefault(mapping.path, {})[function] = (
                self.virtual_address(mapping, segments[mapping.path], function)
            )
        frames: dict[int, Frame] = {}
        for path, virtual in by_object.items():
            lines = subprocess.run(
                ["addr2line", "-f", "-C", "-e", path]
                + [f"{address:#x}" for address in virtual.values()],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.splitlines()
            for position, address in enumerate(virtual):
                symbol, where = lines[2 * position], lines[2 * position + 1]
                file, _, line = where.partition(" ")[0].rpartition(":")
                frame: Frame = {
                    "name": symbol
                    if symbol != "??"
                    else f"{os.path.basename(path)}+{virtual[address]:#x}"
                }
                if file and file != "??":
                    frame["file"] = callgrind.path_norm(file).display
                    if line.isdigit():
                        frame["line"] = int(line)
                frames[address] = frame
        return frames

    def load(self, trace_file: str) -> TraceToSpeedscope.TraceRecording:
        words = array.array("Q")
        try:
            with open(trace_file, "rb") as handle:
                raw = handle.read()
        except OSError as error:
            sys.exit(
                f"error: {trace_file}: {error.strerror or error}: the trace"
                " cyg_callback.c writes at exit. Check the traced run's own"
                " output for the error it printed"
            )
        if len(raw) % words.itemsize:
            sys.exit(
                f"error: {trace_file}: {len(raw):,} bytes is not a whole"
                f" number of {words.itemsize}-byte words, so the traced run"
                " was cut off while writing it"
            )
        words.frombytes(raw)
        if len(words) < _HEADER_WORDS or words[0] != _HEADER_MAGIC:
            sys.exit(f"error: {trace_file}: not a cyg_callback.c trace")
        _, kept, seen, skip, t0_ns, t0_tsc, t1_ns, t1_tsc = words[
            :_HEADER_WORDS
        ]
        records = words[_HEADER_WORDS:]
        if len(records) != kept * _RECORD_WORDS or t1_ns <= t0_ns:
            sys.exit(
                f"error: {trace_file}: truncated, or no time passed"
                " between its two clock readings"
            )
        return TraceToSpeedscope.TraceRecording(
            seen=seen,
            skip=skip,
            origin_tsc=t0_tsc,
            tsc_per_ns=(t1_tsc - t0_tsc) / (t1_ns - t0_ns),
            functions=list(records[0::_RECORD_WORDS]),
            stamps=list(records[1::_RECORD_WORDS]),
        )

    def mappings_read(
        self, maps_file: str
    ) -> list[TraceToSpeedscope.ExecutableMapping]:
        mappings: list[TraceToSpeedscope.ExecutableMapping] = []
        with self.text_open(maps_file) as handle:
            for line in handle:
                fields = line.split(None, 5)
                if (
                    len(fields) == 6
                    and "x" in fields[1]
                    and fields[5].startswith("/")
                ):
                    low, _, high = fields[0].partition("-")
                    mappings.append(
                        TraceToSpeedscope.ExecutableMapping(
                            int(low, 16),
                            int(high, 16),
                            int(fields[2], 16),
                            fields[5].strip(),
                        )
                    )
        return mappings

    def run(self, args: TraceToSpeedscope.TraceArgs) -> None:
        trace = self.load(args.trace_file)
        print(
            f"{args.trace_file}: {trace.seen:,} events in the run,"
            f" {trace.skip:,} skipped, {len(trace.functions):,} kept,"
            f" {trace.tsc_per_ns:.6f} tsc/ns",
            file=sys.stderr,
        )
        calls = self.calls(trace)[:_FLAME_GRAPH_MAX_RECORDED_CALLS]
        if not calls:
            sys.exit(
                f"error: {args.trace_file}: no call both starts and ends"
                " inside the kept events"
            )
        frames = self.frames(
            args.trace_file,
            sorted(
                {
                    trace.functions[record]
                    for record in range(calls[0].first, calls[-1].last + 1)
                }
            ),
        )
        document = self.document(trace, calls, frames, args.name)
        text = json.dumps(document, separators=(",", ":"))
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
        profile = document["profiles"][0]
        print(
            f"wrote {args.output} ({len(text):,} bytes, {len(calls):,} calls,"
            f" {profile['endValue'] - profile['startValue']:,} ns)",
            file=sys.stderr,
        )

    def seen(self, trace_file: str) -> int:
        return self.load(trace_file).seen

    def segments_read(self, path: str) -> list[TraceToSpeedscope.LoadSegment]:
        listing = subprocess.run(
            ["readelf", "-lW", path],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        segments: list[TraceToSpeedscope.LoadSegment] = []
        for line in listing.splitlines():
            fields = line.split()
            if fields and fields[0] == "LOAD":
                segments.append(
                    TraceToSpeedscope.LoadSegment(
                        int(fields[1], 16),
                        int(fields[4], 16),
                        int(fields[2], 16),
                    )
                )
        return segments

    def text_open(self, path: str) -> TextIO:
        try:
            return open(path, encoding="utf-8")
        except OSError as error:
            sys.exit(
                f"error: {path}: {error.strerror or error}: cyg_callback.c"
                " writes it beside the trace at exit"
            )

    def virtual_address(
        self,
        mapping: TraceToSpeedscope.ExecutableMapping,
        segments: list[TraceToSpeedscope.LoadSegment],
        address: int,
    ) -> int:
        offset = address - mapping.low + mapping.offset
        for segment in segments:
            if segment.offset <= offset < segment.offset + segment.size:
                return offset - segment.offset + segment.address
        sys.exit(
            f"error: {address:#x} (file offset {offset:#x}) is in no"
            f" LOAD segment of {mapping.path}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "trace_file",
        help="a cyg_callback.c trace. its .maps file sits beside it",
    )
    parser.add_argument(
        "-o", "--output", default="", help="output .speedscope.json path"
    )
    parser.add_argument("--name", default="", help="document name")
    parser.add_argument(
        "--seen",
        action="store_true",
        help="print how many events the run counted and write nothing",
    )
    namespace = parser.parse_args()
    if namespace.seen:
        print(TraceToSpeedscope().seen(namespace.trace_file))
        return
    if not namespace.output:
        parser.error("-o is required without --seen")
    TraceToSpeedscope().run(
        TraceToSpeedscope.TraceArgs(
            trace_file=namespace.trace_file,
            output=namespace.output,
            name=namespace.name or os.path.basename(namespace.trace_file),
        )
    )


if __name__ == "__main__":
    main()
