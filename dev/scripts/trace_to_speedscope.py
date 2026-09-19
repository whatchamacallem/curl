#!/usr/bin/env python3
from __future__ import annotations

import argparse
from array import array
import json
import os
import subprocess
import sys
from typing import NamedTuple, NotRequired, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind

EXIT_BIT = 1 << 63
HEADER_WORDS = 8
MAGIC = 0x32475943
MAX_BYTES = 10240
MAX_CALLS = 10
RECORD_WORDS = 2
SCHEMA = "https://www.speedscope.app/file-format-schema.json"


class Call(NamedTuple):
    first: int
    last: int


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


class Mapping(NamedTuple):
    low: int
    high: int
    offset: int
    path: str


class Segment(NamedTuple):
    offset: int
    size: int
    address: int


class Shared(TypedDict):
    frames: list[Frame]


class Trace(NamedTuple):
    seen: int
    skip: int
    origin_tsc: int
    tsc_per_ns: float
    functions: list[int]
    stamps: list[int]


class TraceArgs(NamedTuple):
    trace_file: str
    output: str
    name: str


SpeedscopeDoc = TypedDict("SpeedscopeDoc", {
    "$schema": str, "shared": Shared, "profiles": list[EventedProfile], "name": str, "exporter": str})


class TraceToSpeedscope:
    def calls(self, trace: Trace) -> list[Call]:
        runs: list[list[Call]] = [[]]
        open_records: list[int] = []
        for record, function in enumerate(trace.functions):
            if not trace.stamps[record] & EXIT_BIT:
                open_records.append(record)
            elif not open_records:
                runs.append([])
            else:
                first = open_records.pop()
                if trace.functions[first] != function:
                    sys.exit(f"error: record {record}: exit of {function:#x} closes {trace.functions[first]:#x}")
                if not open_records:
                    runs[-1].append(Call(first, record))
        return max(runs, key=lambda run: sum(call.last - call.first + 1 for call in run))

    def document(self, trace: Trace, calls: list[Call], frames: dict[int, Frame], name: str) -> SpeedscopeDoc:
        first, last = calls[0].first, calls[-1].last
        order: dict[int, int] = {}
        events: list[Event] = []
        for record in range(first, last + 1):
            stamp = trace.stamps[record]
            frame = order.setdefault(trace.functions[record], len(order))
            at = round(((stamp & ~EXIT_BIT) - trace.origin_tsc) / trace.tsc_per_ns)
            events.append({"type": "C" if stamp & EXIT_BIT else "O", "frame": frame, "at": at})
        profile_name = (f"rdtsc trace (-finstrument-functions), {len(calls)} calls, events "
                        f"{trace.skip + first + 1:,}..{trace.skip + last + 1:,} of {trace.seen:,}")
        return {"$schema": SCHEMA, "shared": {"frames": [frames[function] for function in order]},
                "profiles": [{"type": "evented", "name": profile_name, "unit": "nanoseconds",
                              "startValue": events[0]["at"], "endValue": events[-1]["at"], "events": events}],
                "name": name, "exporter": "dev/scripts/trace_to_speedscope.py"}

    def frames(self, trace_file: str, functions: list[int]) -> dict[int, Frame]:
        mappings = self.mappings_read(trace_file + ".maps")
        segments: dict[str, list[Segment]] = {}
        by_object: dict[str, dict[int, int]] = {}
        for function in functions:
            mapping = next((m for m in mappings if m.low <= function < m.high), None)
            if mapping is None:
                sys.exit(f"error: {function:#x} is in no executable mapping of {trace_file}.maps")
            if mapping.path not in segments:
                segments[mapping.path] = self.segments_read(mapping.path)
            by_object.setdefault(mapping.path, {})[function] = \
                self.virtual_address(mapping, segments[mapping.path], function)
        frames: dict[int, Frame] = {}
        for path, virtual in by_object.items():
            lines = subprocess.run(["addr2line", "-f", "-C", "-e", path]
                                   + [f"{address:#x}" for address in virtual.values()],
                                   check=True, capture_output=True, text=True).stdout.splitlines()
            for position, address in enumerate(virtual):
                symbol, where = lines[2 * position], lines[2 * position + 1]
                file, _, line = where.partition(" ")[0].rpartition(":")
                frame: Frame = {"name": symbol if symbol != "??"
                                else f"{os.path.basename(path)}+{virtual[address]:#x}"}
                if file and file != "??":
                    frame["file"] = callgrind.path_norm(file).display
                    if line.isdigit():
                        frame["line"] = int(line)
                frames[address] = frame
        return frames

    def load(self, trace_file: str) -> Trace:
        words = array("Q")
        with open(trace_file, "rb") as handle:
            words.frombytes(handle.read())
        if len(words) < HEADER_WORDS or words[0] != MAGIC:
            sys.exit(f"error: {trace_file}: not a dev/cyg_callback.c trace")
        _, kept, seen, skip, t0_ns, t0_tsc, t1_ns, t1_tsc = words[:HEADER_WORDS]
        records = words[HEADER_WORDS:]
        if len(records) != kept * RECORD_WORDS or t1_ns <= t0_ns:
            sys.exit(f"error: {trace_file}: truncated, or no time passed between its two clock readings")
        return Trace(seen=seen, skip=skip, origin_tsc=t0_tsc, tsc_per_ns=(t1_tsc - t0_tsc) / (t1_ns - t0_ns),
                     functions=list(records[0::RECORD_WORDS]), stamps=list(records[1::RECORD_WORDS]))

    def mappings_read(self, maps_file: str) -> list[Mapping]:
        mappings: list[Mapping] = []
        with open(maps_file, encoding="utf-8") as handle:
            for line in handle:
                fields = line.split(None, 5)
                if len(fields) == 6 and "x" in fields[1] and fields[5].startswith("/"):
                    low, _, high = fields[0].partition("-")
                    mappings.append(Mapping(int(low, 16), int(high, 16), int(fields[2], 16), fields[5].strip()))
        return mappings

    def run(self, args: TraceArgs) -> None:
        trace = self.load(args.trace_file)
        print(f"{args.trace_file}: {trace.seen:,} events in the run, {trace.skip:,} skipped, "
              f"{len(trace.functions):,} kept, {trace.tsc_per_ns:.6f} tsc/ns", file=sys.stderr)
        calls = self.calls(trace)[:MAX_CALLS]
        if not calls:
            sys.exit(f"error: {args.trace_file}: no call both starts and ends inside the kept events")
        frames = self.frames(args.trace_file, sorted({trace.functions[record] for record
                                                      in range(calls[0].first, calls[-1].last + 1)}))
        text = ""
        for count in range(1, len(calls) + 1):
            longer = json.dumps(self.document(trace, calls[:count], frames, args.name), separators=(",", ":"))
            if text and len(longer) > MAX_BYTES:
                break
            text = longer
        if len(text) > MAX_BYTES:
            print(f"warning: one call alone is {len(text):,} bytes, over the {MAX_BYTES:,} budget", file=sys.stderr)
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"wrote {args.output} ({len(text):,} bytes)", file=sys.stderr)

    def seen(self, trace_file: str) -> int:
        return self.load(trace_file).seen

    def segments_read(self, path: str) -> list[Segment]:
        listing = subprocess.run(["readelf", "-lW", path], check=True, capture_output=True, text=True).stdout
        segments: list[Segment] = []
        for line in listing.splitlines():
            fields = line.split()
            if fields and fields[0] == "LOAD":
                segments.append(Segment(int(fields[1], 16), int(fields[4], 16), int(fields[2], 16)))
        return segments

    def virtual_address(self, mapping: Mapping, segments: list[Segment], address: int) -> int:
        offset = address - mapping.low + mapping.offset
        for segment in segments:
            if segment.offset <= offset < segment.offset + segment.size:
                return offset - segment.offset + segment.address
        sys.exit(f"error: {address:#x} (file offset {offset:#x}) is in no LOAD segment of {mapping.path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace_file", help="a dev/cyg_callback.c trace; its .maps file sits beside it")
    parser.add_argument("-o", "--output", default="", help="output .speedscope.json path")
    parser.add_argument("--name", default="", help="document name")
    parser.add_argument("--seen", action="store_true",
                        help="print how many events the run counted and write nothing")
    namespace = parser.parse_args()
    if namespace.seen:
        print(TraceToSpeedscope().seen(namespace.trace_file))
        return
    if not namespace.output:
        parser.error("-o is required without --seen")
    TraceToSpeedscope().run(TraceArgs(trace_file=namespace.trace_file, output=namespace.output,
                                      name=namespace.name or os.path.basename(namespace.trace_file)))


if __name__ == "__main__":
    main()
