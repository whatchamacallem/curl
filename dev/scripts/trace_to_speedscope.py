#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from array import array
from typing import NamedTuple, NotRequired, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind

# The high bit cyg.c sets on a timestamp to mark a function exit.
_EXIT_BIT = 1 << 63

# How many 64-bit words the trace file's header takes.
_HEADER_WORDS = 8

# "CYG2" -- the first word of a trace cyg.c wrote.
_MAGIC = 0x32475943

# Size budget for the written document, so the page stays quick to open.
_MAX_BYTES = 204800

# The most complete calls to keep, before the byte budget trims further.
_MAX_CALLS = 200

# How many 64-bit words one recorded event takes: the function, then the stamp.
_RECORD_WORDS = 2

# The format the written document declares itself to be.
_SCHEMA = "https://www.speedscope.app/file-format-schema.json"


# Event - One enter or exit, as speedscope's evented format spells it.
class Event(TypedDict):
    # "O" to open a frame, "C" to close one
    type: str
    # which frame of the shared list this is
    frame: int
    # nanoseconds since the run's first timestamp
    at: int


# EventedProfile - One timeline of enters and exits, and what it covers.
class EventedProfile(TypedDict):
    # always "evented" -- what validate_report.py insists on
    type: str
    # what the timeline is called in the page
    name: str
    # what `at` is measured in
    unit: str
    # the first event's time
    startValue: int
    # the last event's time
    endValue: int
    # the enters and exits themselves, in order
    events: list[Event]


# Frame - One function as the flame graph names it.
class Frame(TypedDict):
    # the demangled symbol, or object+offset when there is none
    name: str
    # the source file, repo-relative
    file: NotRequired[str]
    # the line it is declared on
    line: NotRequired[int]


# Shared - The one frame list every event indexes into.
class Shared(TypedDict):
    # every frame the profile mentions, in first-seen order
    frames: list[Frame]


# The whole written document. Spelled functionally because of "$schema".
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


# TraceToSpeedscope - Turns one rdtsc trace into a speedscope document,
# keeping the busiest run's first few complete calls.
class TraceToSpeedscope:
    # CallSpan - One top-level call, as a span of record numbers.
    class CallSpan(NamedTuple):
        # the record that entered it
        first: int
        # the record that exited it
        last: int

    # ExecutableMapping - One executable range of the traced process, and
    # which file it came from.
    class ExecutableMapping(NamedTuple):
        # first address in the range
        low: int
        # one past the last address
        high: int
        # where in the file that address maps from
        offset: int
        # the file itself, which addr2line reads
        path: str

    # LoadSegment - One LOAD segment of an ELF file, for turning a file offset
    # back into the address the debug info is keyed by.
    class LoadSegment(NamedTuple):
        # where the segment starts in the file
        offset: int
        # how long it is
        size: int
        # the virtual address it loads at
        address: int

    # TraceArgs - What this tool reads and what it writes.
    class TraceArgs(NamedTuple):
        # the .bin cyg.c wrote; its .maps sits beside it
        trace_file: str
        # where the speedscope document goes
        output: str
        # what to call the document in the page
        name: str

    # TraceRecording - One whole trace file, unpacked.
    class TraceRecording(NamedTuple):
        # how many events the run counted, kept or not
        seen: int
        # how many it dropped before the kept ones
        skip: int
        # the timestamp everything is measured from
        origin_tsc: int
        # the measured clock rate, for turning ticks into nanoseconds
        tsc_per_ns: float
        # the function address of each kept event
        functions: list[int]
        # the timestamp of each kept event, exit bit included
        stamps: list[int]

    # Pair enters with exits and hand back the busiest run's top-level calls.
    def calls(
        self, trace: TraceToSpeedscope.TraceRecording
    ) -> list[TraceToSpeedscope.CallSpan]:
        runs: list[list[TraceToSpeedscope.CallSpan]] = [[]]
        open_records: list[int] = []
        for record, function in enumerate(trace.functions):
            if not trace.stamps[record] & _EXIT_BIT:
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

    # Build the whole document from a chosen span of calls.
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
                ((stamp & ~_EXIT_BIT) - trace.origin_tsc) / trace.tsc_per_ns
            )
            events.append(
                {
                    "type": "C" if stamp & _EXIT_BIT else "O",
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
            "$schema": _SCHEMA,
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
            "exporter": "dev/scripts/trace_to_speedscope.py",
        }

    # Name every traced address, by asking addr2line once per object file.
    def frames(
        self, trace_file: str, functions: list[int]
    ) -> dict[int, Frame]:
        mappings = self.mappings_read(trace_file + ".maps")
        segments: dict[str, list[TraceToSpeedscope.LoadSegment]] = {}
        by_object: dict[str, dict[int, int]] = {}
        for function in functions:
            mapping = next(
                (m for m in mappings if m.low <= function < m.high), None
            )
            if mapping is None:
                sys.exit(
                    f"error: {function:#x} is in no executable mapping of "
                    f"{trace_file}.maps"
                )
            if mapping.path not in segments:
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

    # Read one trace file, and refuse anything that is not one.
    def load(self, trace_file: str) -> TraceToSpeedscope.TraceRecording:
        words = array("Q")
        with open(trace_file, "rb") as handle:
            words.frombytes(handle.read())
        if len(words) < _HEADER_WORDS or words[0] != _MAGIC:
            sys.exit(f"error: {trace_file}: not a dev/cyg_callback.c trace")
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

    # Read the executable mappings the traced process had.
    def mappings_read(
        self, maps_file: str
    ) -> list[TraceToSpeedscope.ExecutableMapping]:
        mappings: list[TraceToSpeedscope.ExecutableMapping] = []
        with open(maps_file, encoding="utf-8") as handle:
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

    # Read a trace and write the biggest document that fits the byte budget.
    def run(self, args: TraceToSpeedscope.TraceArgs) -> None:
        trace = self.load(args.trace_file)
        print(
            f"{args.trace_file}: {trace.seen:,} events in the run,"
            f" {trace.skip:,} skipped, {len(trace.functions):,} kept,"
            f" {trace.tsc_per_ns:.6f} tsc/ns",
            file=sys.stderr,
        )
        calls = self.calls(trace)[:_MAX_CALLS]
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
        text = ""
        for count in range(1, len(calls) + 1):
            longer = json.dumps(
                self.document(trace, calls[:count], frames, args.name),
                separators=(",", ":"),
            )
            if text and len(longer) > _MAX_BYTES:
                break
            text = longer
        if len(text) > _MAX_BYTES:
            print(
                f"warning: one call alone is {len(text):,} bytes, over the "
                f"{_MAX_BYTES:,} budget",
                file=sys.stderr,
            )
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"wrote {args.output} ({len(text):,} bytes)", file=sys.stderr)

    # How many events the run counted, without writing anything.
    def seen(self, trace_file: str) -> int:
        return self.load(trace_file).seen

    # Read one ELF file's LOAD segments, for the file-offset arithmetic.
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

    # Undo the load address, so addr2line sees the address it has debug info
    # for.
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


# main - Convert one trace, or just report how many events it counted.
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "trace_file",
        help="a dev/cyg_callback.c trace; its .maps file sits beside it",
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
