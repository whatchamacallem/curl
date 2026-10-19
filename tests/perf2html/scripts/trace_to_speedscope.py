#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, array, json, os, subprocess, sys
from typing import NamedTuple, NotRequired, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artifacts, callgrind, settings

_FLAME_GRAPH_EXPORTER_NAME: str = ""
_FLAME_GRAPH_MAX_RECORDED_CALLS: int = 0
_FLAME_GRAPH_PROFILE_NAME_FORMAT: str = ""
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
        artifacts: str
        report: str
        test: str

    class TraceRecording(NamedTuple):
        seen: int
        skip: int
        origin_tsc: int
        tsc_per_ns: float
        functions: list[int]
        stamps: list[int]

    def buildid_read(self, path: str) -> str:
        listing = self.command_output(["readelf", "-n", path])
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

    def buildids_read(
        self, artifacts_dir: str, test_name: str
    ) -> dict[str, str]:
        out: dict[str, str] = {}
        with artifacts.artifact_open(
            artifacts_dir, "trace-maps", test_name
        ) as handle:
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

    # Returns the stdout of a command whose stderr passes through.
    def command_output(self, command: list[str]) -> str:
        completed = subprocess.run(
            command, check=False, stdout=subprocess.PIPE, text=True
        )
        if completed.returncode != 0:
            print(
                f"error: {completed.returncode} returned {' '.join(command)}",
                file=sys.stderr,
            )
            sys.exit(completed.returncode)
        return completed.stdout

    # Writes the speedscope profile of the busiest run's first calls.
    def convert(self, args: TraceToSpeedscope.TraceArgs, loops: int) -> None:
        artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        trace = self.load(artifacts_dir, args.test)
        calls = self.kept_calls(artifacts_dir, args.test, trace)
        frames = self.frames(artifacts_dir, args.test, trace, calls)
        name = _FLAME_GRAPH_PROFILE_NAME_FORMAT % (args.test, loops)
        document = self.document(trace, calls, frames, name)
        self.document_write(
            artifacts.artifact_path(
                artifacts_dir, "trace-speedscope", args.test
            ),
            document,
            calls,
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

    # Writes the speedscope document, printing its size and span.
    def document_write(
        self,
        path: str,
        document: SpeedscopeDoc,
        calls: list[TraceToSpeedscope.CallSpan],
    ) -> None:
        text = json.dumps(document, separators=(",", ":"))
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        profile = document["profiles"][0]
        print(
            f"wrote {path} ({len(text):,} bytes, {len(calls):,} calls,"
            f" {profile['endValue'] - profile['startValue']:,} ns)",
            file=sys.stderr,
        )

    def frames(
        self,
        artifacts_dir: str,
        test_name: str,
        trace: TraceToSpeedscope.TraceRecording,
        calls: list[TraceToSpeedscope.CallSpan],
    ) -> dict[int, Frame]:
        functions = sorted(
            {
                trace.functions[record]
                for record in range(calls[0].first, calls[-1].last + 1)
            }
        )
        maps_file = artifacts.artifact_path(
            artifacts_dir, "trace-maps", test_name
        )
        mappings = self.mappings_read(artifacts_dir, test_name)
        recorded = self.buildids_read(artifacts_dir, test_name)
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
            lines = self.command_output(
                ["addr2line", "-f", "-C", "-e", path]
                + [f"{address:#x}" for address in virtual.values()]
            ).splitlines()
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

    # Returns the busiest run's first calls, printing what the trace holds.
    def kept_calls(
        self,
        artifacts_dir: str,
        test_name: str,
        trace: TraceToSpeedscope.TraceRecording,
    ) -> list[TraceToSpeedscope.CallSpan]:
        trace_file = artifacts.artifact_path(
            artifacts_dir, "trace-binary", test_name
        )
        print(
            f"{trace_file}: {trace.seen:,} events in the run,"
            f" {trace.skip:,} skipped, {len(trace.functions):,} kept,"
            f" {trace.tsc_per_ns:.6f} tsc/ns",
            file=sys.stderr,
        )
        calls = self.calls(trace)[:_FLAME_GRAPH_MAX_RECORDED_CALLS]
        if not calls:
            sys.exit(
                f"error: {trace_file}: no call both starts and ends"
                " inside the kept events"
            )
        return calls

    def load(
        self, artifacts_dir: str, test_name: str
    ) -> TraceToSpeedscope.TraceRecording:
        words = array.array("Q")
        with artifacts.artifact_open(
            artifacts_dir, "trace-binary", test_name, "rb"
        ) as handle:
            raw = handle.read()
        trace_file = artifacts.artifact_path(
            artifacts_dir, "trace-binary", test_name
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
        self, artifacts_dir: str, test_name: str
    ) -> list[TraceToSpeedscope.ExecutableMapping]:
        mappings: list[TraceToSpeedscope.ExecutableMapping] = []
        with artifacts.artifact_open(
            artifacts_dir, "trace-maps", test_name
        ) as handle:
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

    # Writes how many events the counting run saw into the test's seen file.
    def seen(self, args: TraceToSpeedscope.TraceArgs) -> None:
        artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        seen = self.load(artifacts_dir, args.test).seen
        path = artifacts.artifact_path(artifacts_dir, "trace-seen", args.test)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(f"{seen}\n")
        print(f"wrote {path} ({seen:,} events)", file=sys.stderr)

    def segments_read(self, path: str) -> list[TraceToSpeedscope.LoadSegment]:
        listing = self.command_output(["readelf", "-lW", path])
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
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    seen_parser = subparsers.add_parser(
        "seen", help="the seen file, how many events the counting run saw"
    )
    convert_parser = subparsers.add_parser(
        "convert", help="the speedscope profile of the busiest run's calls"
    )
    convert_parser.add_argument(
        "--loops",
        required=True,
        type=int,
        help="the loop count the traced run took, shown in the profile name",
    )
    for trace_parser in (seen_parser, convert_parser):
        trace_parser.add_argument(
            "--artifacts",
            required=True,
            metavar="DIR",
            help="the profiler artifacts directory, holding the report's own,"
            " where the test's trace sits",
        )
        trace_parser.add_argument(
            "--report",
            required=True,
            metavar="DIR",
            help="the report directory, naming its artifacts directory",
        )
        trace_parser.add_argument(
            "--test", required=True, help="the test whose trace is read"
        )
    namespace = parser.parse_args()
    trace_args = TraceToSpeedscope.TraceArgs(
        artifacts=namespace.artifacts,
        report=namespace.report,
        test=namespace.test,
    )
    if namespace.cmd == "seen":
        TraceToSpeedscope().seen(trace_args)
    else:
        TraceToSpeedscope().convert(trace_args, namespace.loops)


if __name__ == "__main__":
    main()
