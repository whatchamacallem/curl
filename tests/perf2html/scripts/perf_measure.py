#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, os, re, subprocess, sys
from collections.abc import Sequence
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artifacts, settings, trace_to_speedscope

_CALLGRIND_LAST_LEVEL_CACHE: str = ""
_DATABASE_TIME_SUFFIX_SECONDS: dict[str, float] = {}
_PERF_TOOL_ERRORS_LABEL: str = ""
_PERF_TOOL_TIME_LABEL: str = ""
_PROFILE_PINNED_CPU: int = 0
_PROFILE_START_FUNCTION_NAME: str = ""
_PROFILE_STOP_FUNCTION_NAME: str = ""
_TEST_LOOPS: int = 0
_TIMING_COUNTER_LABELS: dict[str, str] = {}
_TIMING_COUNTER_RATIO_DIVIDEND: str = ""
_TIMING_COUNTER_RATIO_DIVISOR: str = ""
_TIMING_PERF_STAT_EVENTS: str = ""
_TRACE_SKIP_ALL: int = 0
settings.load_into(__name__)

_PERF_TOOL_TIME_LINE = re.compile(
    rf"{re.escape(_PERF_TOOL_TIME_LABEL)}:\s+(\d+(?:\.\d+)?)\s*("
    + "|".join(map(re.escape, sorted(_DATABASE_TIME_SUFFIX_SECONDS)))
    + r")\s*"
)

_PERF_TOOL_TIME_PER_UNIT_PREFIX = _PERF_TOOL_TIME_LABEL + "/"

_PINNED_COMMAND = ("taskset", "-c", str(_PROFILE_PINNED_CPU))

_SIGNAL_EXIT_CODE_BASE = 128

_TRACE_OUT_VARIABLE = "PERF_TRACE_OUT"

_TRACE_SKIP_VARIABLE = "PERF_TRACE_SKIP"


class PerfMeasure:
    class MeasureArgs(NamedTuple):
        artifacts: str
        report: str
        test: str
        executable: str

    class Timing(NamedTuple):
        seconds_per_loop: float
        counter_ratio: float
        summary_rows: list[tuple[str, str]]

    # Records the test under callgrind, the profiled window alone.
    def callgrind_measure(self, args: PerfMeasure.MeasureArgs) -> None:
        artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        callgrind_path = artifacts.artifact_path(
            artifacts_dir, "callgrind", args.test
        )
        log_path = artifacts.artifact_path(
            artifacts_dir, "valgrind-log", args.test
        )
        # `--collect-atstart` follows `--toggle-collect`, which implies `no`.
        command_words = [
            *_PINNED_COMMAND,
            "valgrind",
            "--tool=callgrind",
            "--cache-sim=yes",
            "--branch-sim=yes",
            "--trace-redir=yes",
            f"--zero-before={_PROFILE_START_FUNCTION_NAME}",
            f"--toggle-collect={_PROFILE_STOP_FUNCTION_NAME}",
            "--collect-atstart=yes",
            f"--LL={_CALLGRIND_LAST_LEVEL_CACHE}",
            f"--callgrind-out-file={callgrind_path}",
            f"--log-file={log_path}",
            args.executable,
            args.test,
            str(_TEST_LOOPS),
        ]
        self.line_print(" ".join(["$", *command_words]))
        completed = subprocess.run(command_words, check=False)
        self.exit_check(completed.returncode, command_words)

    # Returns a line per perf stat event, its label and the value perf wrote.
    def counter_lines(self, artifacts_dir: str, test_name: str) -> list[str]:
        stat_path = artifacts.artifact_path(
            artifacts_dir, "timing-csv", test_name
        )
        with artifacts.artifact_open(
            artifacts_dir, "timing-csv", test_name
        ) as handle:
            stat_rows = [
                stat_line.split(",")
                for stat_line in handle.read().splitlines()
                if stat_line and not stat_line.startswith("#")
            ]
        labeled_lines: list[str] = []
        for event_name in _TIMING_PERF_STAT_EVENTS.split(","):
            event_values = [
                row_fields[0]
                for row_fields in stat_rows
                if row_fields[2:3] == [event_name]
            ]
            if len(event_values) != 1:
                sys.exit(
                    f"error: {stat_path} holds {len(event_values)}"
                    f" {event_name} rows, expected 1"
                )
            counter_key = event_name.partition(":")[0]
            if counter_key not in _TIMING_COUNTER_LABELS:
                sys.exit(
                    f"error: TIMING_COUNTER_LABELS holds no {counter_key}"
                    f" key: {sorted(_TIMING_COUNTER_LABELS)}"
                )
            labeled_lines.append(
                f"{_TIMING_COUNTER_LABELS[counter_key]}: {event_values[0]}"
            )
        return labeled_lines

    # Exits as the shell would after a failed command, naming the command.
    def exit_check(self, exit_code: int, command_words: Sequence[str]) -> None:
        if not exit_code:
            return
        shell_exit_code = (
            exit_code if exit_code > 0 else _SIGNAL_EXIT_CODE_BASE - exit_code
        )
        print(
            f"error: exit {shell_exit_code} from: {' '.join(command_words)}",
            file=sys.stderr,
        )
        sys.exit(shell_exit_code)

    # Prints one line of the page the caller keeps, returning that line.
    def line_print(self, page_line: str) -> str:
        print(page_line, flush=True)
        return page_line

    # Returns the perf tool's time over its loops, its other output left out.
    def perf_tool_time_per_loop(
        self, page_path: str, page_lines: Sequence[str], test_name: str
    ) -> float:
        command_words = page_lines[0].split() if page_lines else []
        if (
            len(command_words) < 2
            or command_words[-2] != test_name
            or not command_words[-1].isdigit()
            or not int(command_words[-1])
        ):
            sys.exit(
                f"error: {page_path} opens with no {test_name} command ending"
                f" in its loop count: {page_lines[:1]}"
            )
        time_matches = [
            line_match
            for line_match in map(_PERF_TOOL_TIME_LINE.fullmatch, page_lines)
            if line_match
        ]
        if len(time_matches) != 1:
            sys.exit(
                f"error: {page_path} holds {len(time_matches)}"
                f" {_PERF_TOOL_TIME_LABEL}: lines with a time unit"
                f" of {sorted(_DATABASE_TIME_SUFFIX_SECONDS)}, expected 1"
            )
        time_match = time_matches[0]
        run_seconds = (
            float(time_match.group(1))
            * (_DATABASE_TIME_SUFFIX_SECONDS[time_match.group(2)])
        )
        return run_seconds / int(command_words[-1])

    # Returns the time per unit and errors lines of a page, in page order.
    def summary_rows(
        self, page_path: str, page_lines: Sequence[str]
    ) -> list[tuple[str, str]]:
        label_values: list[tuple[str, str]] = []
        for page_line in page_lines:
            line_label, label_separator, line_value = page_line.partition(":")
            if label_separator and (
                line_label.startswith(_PERF_TOOL_TIME_PER_UNIT_PREFIX)
                or line_label == _PERF_TOOL_ERRORS_LABEL
            ):
                label_values.append((line_label, line_value.strip()))
        time_rows = [
            label_value
            for label_value in label_values
            if label_value[0].startswith(_PERF_TOOL_TIME_PER_UNIT_PREFIX)
        ]
        if len(time_rows) != 1:
            sys.exit(
                f"error: {page_path} holds {len(time_rows)}"
                f" {_PERF_TOOL_TIME_PER_UNIT_PREFIX}<unit>: lines, expected 1"
            )
        return label_values

    # Returns a timing page's dividend counter over its divisor counter.
    def timing_counter_ratio(
        self, page_path: str, page_lines: Sequence[str]
    ) -> float:
        counter_values = self.timing_counters(page_path, page_lines)
        ratio_terms: list[int] = []
        for counter_key in (
            _TIMING_COUNTER_RATIO_DIVIDEND,
            _TIMING_COUNTER_RATIO_DIVISOR,
        ):
            if counter_key not in _TIMING_COUNTER_LABELS:
                sys.exit(
                    f"error: TIMING_COUNTER_LABELS holds no {counter_key}"
                    f" key: {sorted(_TIMING_COUNTER_LABELS)}"
                )
            counter_label = _TIMING_COUNTER_LABELS[counter_key]
            counter_text = counter_values[counter_label]
            if not counter_text.isdigit() or not int(counter_text):
                sys.exit(
                    f"error: {page_path} holds {counter_label}:"
                    f" {counter_text!r}, expected a count above 0"
                )
            ratio_terms.append(int(counter_text))
        return ratio_terms[0] / ratio_terms[1]

    # Returns each perf stat counter line's value of a timing page by label.
    def timing_counters(
        self, page_path: str, page_lines: Sequence[str]
    ) -> dict[str, str]:
        counter_values: dict[str, list[str]] = {
            counter_label: []
            for counter_label in _TIMING_COUNTER_LABELS.values()
        }
        for page_line in page_lines:
            line_label, label_separator, line_value = page_line.partition(":")
            if label_separator and line_label in counter_values:
                counter_values[line_label].append(line_value.strip())
        for counter_label, label_values in counter_values.items():
            if len(label_values) != 1:
                sys.exit(
                    f"error: {page_path} holds {len(label_values)}"
                    f" {counter_label}: lines, expected 1"
                )
        return {
            counter_label: label_values[0]
            for counter_label, label_values in counter_values.items()
        }

    # Records the test's perf stat run and writes its timing summary rows.
    def timing_measure(
        self, args: PerfMeasure.MeasureArgs, executable_shown: str
    ) -> None:
        artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        stat_path = artifacts.artifact_path(
            artifacts_dir, "timing-csv", args.test
        )
        event_words = ["perf", "stat", "-e", _TIMING_PERF_STAT_EVENTS]
        loop_words = [args.test, str(_TEST_LOOPS)]
        page_lines = [
            self.line_print(
                " ".join(
                    [
                        "$",
                        *event_words,
                        *_PINNED_COMMAND,
                        executable_shown,
                        *loop_words,
                    ]
                )
            )
        ]
        command_words = [
            *event_words,
            "-x,",
            "-o",
            stat_path,
            *_PINNED_COMMAND,
            args.executable,
            *loop_words,
        ]
        with subprocess.Popen(
            command_words,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        ) as stat_process:
            assert stat_process.stdout is not None, "stdout is a pipe"
            for output_line in stat_process.stdout:
                page_lines.append(self.line_print(output_line.rstrip("\n")))
        self.exit_check(stat_process.returncode, command_words)
        page_lines += [
            self.line_print(counter_line)
            for counter_line in self.counter_lines(artifacts_dir, args.test)
        ]
        page_path = artifacts.artifact_path(
            artifacts_dir, "timing-page", args.test
        )
        timing = self.timing_parse(page_path, page_lines, args.test)
        with artifacts.artifact_open(
            artifacts_dir, "timing-summary", args.test, "w"
        ) as handle:
            handle.writelines(
                f"{row_label}={row_value}\n"
                for row_label, row_value in timing.summary_rows
            )

    # Returns the time per loop, counter ratio and summary rows of a page.
    def timing_parse(
        self, page_path: str, page_lines: Sequence[str], test_name: str
    ) -> PerfMeasure.Timing:
        return PerfMeasure.Timing(
            seconds_per_loop=self.perf_tool_time_per_loop(
                page_path, page_lines, test_name
            ),
            counter_ratio=self.timing_counter_ratio(page_path, page_lines),
            summary_rows=self.summary_rows(page_path, page_lines),
        )

    # Returns a test's timing, read from the timing page of its perf run.
    def timing_read(
        self, artifacts_dir: str, test_name: str
    ) -> PerfMeasure.Timing:
        with artifacts.artifact_open(
            artifacts_dir, "timing-page", test_name
        ) as handle:
            page_lines = handle.read().splitlines()
        return self.timing_parse(
            artifacts.artifact_path(artifacts_dir, "timing-page", test_name),
            page_lines,
            test_name,
        )

    # Records the counting run and the sampled run, then converts the trace.
    def trace_measure(
        self, args: PerfMeasure.MeasureArgs, executable_shown: str
    ) -> None:
        artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        trace_path = artifacts.artifact_path(
            artifacts_dir, "trace-binary", args.test
        )
        trace_converter = trace_to_speedscope.TraceToSpeedscope()
        self.trace_run(args, executable_shown, trace_path, _TRACE_SKIP_ALL)
        seen_events = trace_converter.load(artifacts_dir, args.test).seen
        self.trace_run(args, executable_shown, trace_path, seen_events // 2)
        trace_converter.convert(artifacts_dir, args.test, _TEST_LOOPS)

    # Runs the traced test once, recording after its skipped events.
    def trace_run(
        self,
        args: PerfMeasure.MeasureArgs,
        executable_shown: str,
        trace_path: str,
        skipped_events: int,
    ) -> None:
        loop_words = [args.test, str(_TEST_LOOPS)]
        skip_word = f"{_TRACE_SKIP_VARIABLE}={skipped_events}"
        self.line_print(
            " ".join(
                [
                    "$",
                    f"{_TRACE_OUT_VARIABLE}={os.path.basename(trace_path)}",
                    skip_word,
                    *_PINNED_COMMAND,
                    executable_shown,
                    *loop_words,
                ]
            )
        )
        command_words = [*_PINNED_COMMAND, args.executable, *loop_words]
        completed = subprocess.run(
            command_words,
            check=False,
            env=os.environ
            | {
                _TRACE_OUT_VARIABLE: trace_path,
                _TRACE_SKIP_VARIABLE: str(skipped_events),
            },
        )
        self.exit_check(
            completed.returncode,
            [f"{_TRACE_OUT_VARIABLE}={trace_path}", skip_word, *command_words],
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Runs the perf test executable under each measuring tool, the"
            " one caller of perf, and writes what each run records."
        )
    )
    subparsers = parser.add_subparsers(dest="cmd", required=True)
    callgrind_parser = subparsers.add_parser(
        "callgrind",
        help="the callgrind recording and valgrind log of the profiled window",
    )
    timing_parser = subparsers.add_parser(
        "timing",
        help="the perf stat counters, the timing page and its summary rows",
    )
    trace_parser = subparsers.add_parser(
        "trace",
        help="the function trace of the sampled run and its speedscope"
        " profile",
    )
    for measure_parser in (callgrind_parser, timing_parser, trace_parser):
        measure_parser.add_argument(
            "--artifacts",
            required=True,
            metavar="DIR",
            help="the profiler artifacts directory, holding the report's own,"
            " where the test's recordings go",
        )
        measure_parser.add_argument(
            "--report",
            required=True,
            metavar="DIR",
            help="the report directory, naming its artifacts directory",
        )
        measure_parser.add_argument(
            "--test", required=True, help="the test the executable runs"
        )
        measure_parser.add_argument(
            "--executable",
            required=True,
            metavar="PATH",
            help="the perf test executable the run measures",
        )
    for page_parser in (timing_parser, trace_parser):
        page_parser.add_argument(
            "--executable-shown",
            required=True,
            metavar="PATH",
            help="the executable as the page shows it",
        )
    namespace = parser.parse_args()
    measure_args = PerfMeasure.MeasureArgs(
        artifacts=namespace.artifacts,
        report=namespace.report,
        test=namespace.test,
        executable=namespace.executable,
    )
    if namespace.cmd == "callgrind":
        PerfMeasure().callgrind_measure(measure_args)
    elif namespace.cmd == "timing":
        PerfMeasure().timing_measure(measure_args, namespace.executable_shown)
    else:
        PerfMeasure().trace_measure(measure_args, namespace.executable_shown)


if __name__ == "__main__":
    main()
