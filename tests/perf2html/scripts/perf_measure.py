#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, decimal, json, math, os, re, shlex, statistics, subprocess
import sys, typing
from collections.abc import Sequence
from typing import Any, NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artifacts, settings, theme, trace_to_speedscope

_CALLGRIND_LAST_LEVEL_CACHE: str = ""
_DATABASE_TIME_SUFFIX_SECONDS: dict[str, float] = {}
_PERF_TOOL_TIME_LABEL: str = ""
_PROFILE_PINNED_CPU: int = 0
_PROFILE_START_FUNCTION_NAME: str = ""
_PROFILE_STOP_FUNCTION_NAME: str = ""
_SIGNAL_EXIT_CODE_BASE: int = 0
_TEST_LOOPS: int = 0
_TIMING_COLUMN_NAMES: tuple[str, ...] = ()
_TIMING_COUNTER_RATIOS: tuple[tuple[str, str, str], ...] = ()
_TIMING_DATA_INDENT_CHARS: int = 0
_TIMING_PERF_STAT_EVENTS: tuple[str, ...] = ()
_TIMING_PERF_STAT_METRIC_FRACTION_DIGITS: int = 0
_TIMING_PERF_STAT_METRICS: tuple[tuple[str, str, str, int], ...] = ()
_TIMING_PERF_STAT_NUMBER_PATTERN: str = ""
_TIMING_PERF_STAT_RUNS: int = 0
_TIMING_PERF_STAT_UNCOUNTED_VALUES: tuple[str, ...] = ()
_TIMING_TIME_PER_LOOP_NAME: str = ""
_TRACE_OUT_VARIABLE: str = ""
_TRACE_SKIP_ALL: int = 0
_TRACE_SKIP_VARIABLE: str = ""
_VERBOSE_RAW_LEVEL: int = 0
settings.load_into(__name__)

_PERF_STAT_EVENT_NAMES = tuple(
    event.partition(":")[0] for event in _TIMING_PERF_STAT_EVENTS
)

_PERF_TOOL_TIME_LINE = re.compile(
    rf"{re.escape(_PERF_TOOL_TIME_LABEL)}:\s+(\d+(?:\.\d+)?)\s*("
    + "|".join(map(re.escape, sorted(_DATABASE_TIME_SUFFIX_SECONDS)))
    + r")\s*"
)

_PINNED_COMMAND = ("taskset", "-c", str(_PROFILE_PINNED_CPU))

_TIMING_VALUE_NAMES = (
    _TIMING_TIME_PER_LOOP_NAME,
    *(metric_entry[0] for metric_entry in _TIMING_PERF_STAT_METRICS),
    *(ratio_entry[0] for ratio_entry in _TIMING_COUNTER_RATIOS),
)


class PerfMeasure:
    class DataArgs(NamedTuple):
        artifacts: str
        report: str

    class MeasureArgs(NamedTuple):
        artifacts: str
        report: str
        test: str
        executable: str

    class PerfStat(NamedTuple):
        counters: dict[str, float]
        metric_texts: list[str]

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

    # Returns each counter ratio, one over a 0 being 0.
    def counter_ratios(self, counters: dict[str, float]) -> list[float]:
        ratios: list[float] = []
        for ratio_name, dividend, divisor in _TIMING_COUNTER_RATIOS:
            for event_name in (dividend, divisor):
                self.event_name_check(
                    "TIMING_COUNTER_RATIOS", ratio_name, event_name
                )
            ratios.append(
                counters[dividend] / counters[divisor]
                if counters[divisor]
                else 0.0
            )
        return ratios

    # Returns the count of one perf stat line, an uncounted event's 0.
    def counter_value(self, stat_path: str, stat_record: Any) -> float:
        count_text = stat_record["counter-value"]
        if count_text in _TIMING_PERF_STAT_UNCOUNTED_VALUES:
            return 0.0
        if not re.fullmatch(_TIMING_PERF_STAT_NUMBER_PATTERN, count_text):
            sys.exit(
                f"error: {stat_path} counts {stat_record['event']} as"
                f" {count_text!r}, expected a count or one of"
                f" {list(_TIMING_PERF_STAT_UNCOUNTED_VALUES)}"
            )
        return float(count_text)

    # Exits when a setting entry names an event perf stat does not count.
    def event_name_check(
        self, setting_name: str, entry_name: str, event_name: str
    ) -> None:
        if event_name not in _PERF_STAT_EVENT_NAMES:
            sys.exit(
                f"error: {setting_name} {entry_name!r} names {event_name},"
                " which TIMING_PERF_STAT_EVENTS does not count:"
                f" {list(_PERF_STAT_EVENT_NAMES)}"
            )

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

    # Returns each perf metric as a ratio, an absent metric 0.
    def metric_ratios(self, metric_texts: Sequence[str]) -> list[float]:
        return [
            (
                float(decimal.Decimal(metric_text) / units_per_ratio)
                if metric_text
                else 0.0
            )
            for (*_, units_per_ratio), metric_text in zip(
                _TIMING_PERF_STAT_METRICS, metric_texts, strict=True
            )
        ]

    # Returns perf's own metric text of one perf stat line, none if absent.
    def metric_text(
        self, stat_path: str, stat_record: Any, metric_unit: str
    ) -> str:
        if "metric-value" not in stat_record:
            return ""
        if stat_record["metric-unit"] != metric_unit or not re.fullmatch(
            _TIMING_PERF_STAT_NUMBER_PATTERN, stat_record["metric-value"]
        ):
            sys.exit(
                f"error: {stat_path} gives {stat_record['event']} the metric"
                f" {stat_record['metric-value']!r}"
                f" {stat_record['metric-unit']!r}, expected a number"
                f" {metric_unit!r}"
            )
        return stat_record["metric-value"]

    # Runs a command, writing its shown line and its output to the page.
    def page_command_run(
        self,
        page_file: typing.IO[str],
        verbose_level: int,
        shown_words: Sequence[str],
        command_words: Sequence[str],
    ) -> tuple[list[str], int]:
        page_lines = [
            self.page_line_write(
                page_file, verbose_level, "$ " + shlex.join(shown_words)
            )
        ]
        with subprocess.Popen(
            command_words,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        ) as page_process:
            assert page_process.stdout is not None, "stdout is a pipe"
            for output_line in page_process.stdout:
                page_lines.append(
                    self.page_line_write(
                        page_file, verbose_level, output_line.rstrip("\n")
                    )
                )
        return page_lines, page_process.returncode

    # Writes one timing page line, printing it at the raw verbose level.
    def page_line_write(
        self, page_file: typing.IO[str], verbose_level: int, page_line: str
    ) -> str:
        page_file.write(page_line + "\n")
        page_file.flush()
        if verbose_level >= _VERBOSE_RAW_LEVEL:
            self.line_print(page_line)
        return page_line

    # Returns the perf stat counts by event name and perf's own metric texts.
    def perf_stat_read(
        self, artifacts_dir: str, test_name: str
    ) -> PerfMeasure.PerfStat:
        for metric_name, event_name, _, _ in _TIMING_PERF_STAT_METRICS:
            self.event_name_check(
                "TIMING_PERF_STAT_METRICS", metric_name, event_name
            )
        stat_path = artifacts.artifact_path(
            artifacts_dir, "timing-json", test_name
        )
        with artifacts.artifact_open(
            artifacts_dir, "timing-json", test_name
        ) as handle:
            stat_records = [
                json.loads(stat_line)
                for stat_line in handle.read().splitlines()
            ]
        if not stat_records:
            return PerfMeasure.PerfStat(
                counters=dict.fromkeys(_PERF_STAT_EVENT_NAMES, 0.0),
                metric_texts=["" for _ in _TIMING_PERF_STAT_METRICS],
            )
        event_records: dict[str, list[Any]] = {
            event_name: [] for event_name in _PERF_STAT_EVENT_NAMES
        }
        for stat_record in stat_records:
            event_name = stat_record["event"].partition(":")[0]
            if event_name not in event_records:
                sys.exit(
                    f"error: {stat_path} counts {stat_record['event']}, which"
                    f" TIMING_PERF_STAT_EVENTS does not name:"
                    f" {list(_TIMING_PERF_STAT_EVENTS)}"
                )
            event_records[event_name].append(stat_record)
        for event_name, records in event_records.items():
            if len(records) != 1:
                sys.exit(
                    f"error: {stat_path} holds {len(records)} {event_name}"
                    " lines, expected 1"
                )
        return PerfMeasure.PerfStat(
            counters={
                event_name: self.counter_value(stat_path, records[0])
                for event_name, records in event_records.items()
            },
            metric_texts=[
                self.metric_text(
                    stat_path, event_records[event_name][0], metric_unit
                )
                for _, event_name, metric_unit, _ in _TIMING_PERF_STAT_METRICS
            ],
        )

    # Returns the median over the runs of the perf tool's time over its loops.
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
        if len(time_matches) != _TIMING_PERF_STAT_RUNS:
            sys.exit(
                f"error: {page_path} holds {len(time_matches)}"
                f" {_PERF_TOOL_TIME_LABEL}: lines with a time unit"
                f" of {sorted(_DATABASE_TIME_SUFFIX_SECONDS)}, expected"
                f" {_TIMING_PERF_STAT_RUNS}"
            )
        run_seconds = [
            float(time_match.group(1))
            * _DATABASE_TIME_SUFFIX_SECONDS[time_match.group(2)]
            for time_match in time_matches
        ]
        return statistics.median(run_seconds) / int(command_words[-1])

    # Returns a timing document, refusing one unlike its tests or values.
    def timing_data_read(self, directory: str) -> dict[str, dict[str, float]]:
        with artifacts.artifact_open(directory, "timing-data") as handle:
            timing_document = json.load(handle)
        path = artifacts.artifact_path(directory, "timing-data")
        test_names = artifacts.test_list_read(directory)
        if (
            not isinstance(timing_document, dict)
            or list(timing_document) != test_names
        ):
            found_names = (
                list(timing_document)
                if isinstance(timing_document, dict)
                else timing_document
            )
            print(
                f"error: {path} names the tests {found_names!r}, expected"
                f" {test_names}",
                file=sys.stderr,
            )
            sys.exit(2)
        for test_name, timing in timing_document.items():
            if not isinstance(timing, dict) or list(timing) != list(
                _TIMING_COLUMN_NAMES
            ):
                print(
                    f"error: {path} gives {test_name} values other than"
                    f" {list(_TIMING_COLUMN_NAMES)}: {timing!r}",
                    file=sys.stderr,
                )
                sys.exit(2)
            for value_name, value in timing.items():
                if type(value) not in (int, float) or not (
                    0 <= value < math.inf
                ):
                    print(
                        f"error: {path} gives {test_name} the {value_name}"
                        f" {value!r}, expected a finite number not below 0",
                        file=sys.stderr,
                    )
                    sys.exit(2)
        return timing_document

    # Writes the timing document, each test's overview values by name.
    def timing_data_write(self, args: PerfMeasure.DataArgs) -> None:
        artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        timing_document = {
            test_name: self.timing_read(artifacts_dir, test_name)
            for test_name in artifacts.test_list_read(artifacts_dir)
        }
        with artifacts.artifact_open(
            artifacts_dir, "timing-data", "", "w"
        ) as handle:
            handle.write(
                json.dumps(timing_document, indent=_TIMING_DATA_INDENT_CHARS)
                + "\n"
            )

    # Records the test's runs under perf stat, else directly, and its summary.
    def timing_measure(
        self,
        args: PerfMeasure.MeasureArgs,
        executable_shown: str,
        verbose_level: int,
    ) -> None:
        artifacts_dir = artifacts.report_artifacts_dir(
            args.artifacts, args.report
        )
        stat_path = artifacts.artifact_path(
            artifacts_dir, "timing-json", args.test
        )
        page_path = artifacts.artifact_path(
            artifacts_dir, "timing-page", args.test
        )
        stat_words = ["perf", "stat", "-j", "-r", str(_TIMING_PERF_STAT_RUNS)]
        event_words = [
            "-e",
            "{" + ",".join(_TIMING_PERF_STAT_EVENTS) + "}",
            "--",
            *_PINNED_COMMAND,
        ]
        loop_words = [args.test, str(_TEST_LOOPS)]
        command_words = [
            *stat_words,
            "-o",
            stat_path,
            *event_words,
            args.executable,
            *loop_words,
        ]
        page_lines: list[str] = []
        try:
            with artifacts.artifact_open(
                artifacts_dir, "timing-page", args.test, "w"
            ) as page_file:
                run_lines, stat_exit_code = self.page_command_run(
                    page_file,
                    verbose_level,
                    [
                        *stat_words,
                        "-o",
                        os.path.basename(stat_path),
                        *event_words,
                        executable_shown,
                        *loop_words,
                    ],
                    command_words,
                )
                page_lines += run_lines
                # A refused perf writes empty JSON, then curl perf runs alone.
                if os.path.isfile(stat_path) and not os.path.getsize(
                    stat_path
                ):
                    run_words = [
                        *_PINNED_COMMAND,
                        args.executable,
                        *loop_words,
                    ]
                    for _ in range(_TIMING_PERF_STAT_RUNS):
                        run_lines, run_exit_code = self.page_command_run(
                            page_file,
                            verbose_level,
                            [*_PINNED_COMMAND, executable_shown, *loop_words],
                            run_words,
                        )
                        page_lines += run_lines
                        self.exit_check(run_exit_code, run_words)
                else:
                    self.exit_check(stat_exit_code, command_words)
            timing = self.timing_parse(
                page_path,
                page_lines,
                args.test,
                self.perf_stat_read(artifacts_dir, args.test),
            )
        except SystemExit:
            # No page line printed below the raw level, so the exit logs them.
            if verbose_level < _VERBOSE_RAW_LEVEL:
                print(*page_lines, sep="\n", file=sys.stderr, flush=True)
            raise
        timing_rows = self.timing_texts(timing)
        summary_lines = [
            f"{value_name}={value_text}"
            for value_name, value_text in timing_rows
        ]
        with artifacts.artifact_open(
            artifacts_dir, "timing-summary", args.test, "w"
        ) as handle:
            handle.writelines(
                f"{summary_line}\n" for summary_line in summary_lines
            )
        if verbose_level >= _VERBOSE_RAW_LEVEL:
            with artifacts.artifact_open(
                artifacts_dir, "timing-json", args.test
            ) as handle:
                stat_lines = handle.read().splitlines()
            print(*stat_lines, *summary_lines, sep="\n", flush=True)
        elif verbose_level:
            self.timing_table_print(timing_rows)

    # Returns the overview values by name, in the overview's column order.
    def timing_parse(
        self,
        page_path: str,
        page_lines: Sequence[str],
        test_name: str,
        perf_stat: PerfMeasure.PerfStat,
    ) -> dict[str, float]:
        timing: dict[str, float] = dict(
            zip(
                _TIMING_VALUE_NAMES,
                [
                    self.perf_tool_time_per_loop(
                        page_path, page_lines, test_name
                    ),
                    *self.metric_ratios(perf_stat.metric_texts),
                    *self.counter_ratios(perf_stat.counters),
                ],
                strict=True,
            )
        )
        if sorted(_TIMING_COLUMN_NAMES) != sorted(timing):
            sys.exit(
                f"error: TIMING_COLUMN_NAMES {list(_TIMING_COLUMN_NAMES)}"
                f" names other than each timing value once: {list(timing)}"
            )
        return {
            column_name: timing[column_name]
            for column_name in _TIMING_COLUMN_NAMES
        }

    # Returns a test's timing, read from its timing page and perf counters.
    def timing_read(
        self, artifacts_dir: str, test_name: str
    ) -> dict[str, float]:
        with artifacts.artifact_open(
            artifacts_dir, "timing-page", test_name
        ) as handle:
            page_lines = handle.read().splitlines()
        return self.timing_parse(
            artifacts.artifact_path(artifacts_dir, "timing-page", test_name),
            page_lines,
            test_name,
            self.perf_stat_read(artifacts_dir, test_name),
        )

    # Prints the timing row the report shows, as a Markdown table.
    def timing_table_print(
        self, timing_rows: Sequence[tuple[str, str]]
    ) -> None:
        value_names = [value_name for value_name, _ in timing_rows]
        value_cells = [
            f"`{value_text}`" if value_text else ""
            for _, value_text in timing_rows
        ]
        column_widths = [
            max(len(value_name), len(value_cell))
            for value_name, value_cell in zip(
                value_names, value_cells, strict=True
            )
        ]
        table_rows = [
            value_names,
            ["-" * column_width for column_width in column_widths],
            value_cells,
        ]
        print(
            "",
            *(
                "| "
                + " | ".join(
                    table_cell.ljust(column_width)
                    for table_cell, column_width in zip(
                        table_row, column_widths, strict=True
                    )
                )
                + " |"
                for table_row in table_rows
            ),
            sep="\n",
            flush=True,
        )

    # Returns each timing value's name and printed text, a 0 printed empty.
    def timing_texts(self, timing: dict[str, float]) -> list[tuple[str, str]]:
        timing_rows: list[tuple[str, str]] = []
        for value_name, value in timing.items():
            if not value:
                value_text = ""
            elif value_name == _TIMING_TIME_PER_LOOP_NAME:
                value_text = theme.num_time(value)
            else:
                value_text = theme.fixed_text(
                    value, _TIMING_PERF_STAT_METRIC_FRACTION_DIGITS
                )
            timing_rows.append((value_name, value_text))
        return timing_rows

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
    timing_data_parser = subparsers.add_parser(
        "timing-data",
        help="the timing document of every test's overview values, which"
        " the raw data archive holds",
    )
    trace_parser = subparsers.add_parser(
        "trace",
        help="the function trace of the sampled run and its speedscope"
        " profile",
    )
    for report_parser in (
        callgrind_parser,
        timing_parser,
        timing_data_parser,
        trace_parser,
    ):
        report_parser.add_argument(
            "--artifacts",
            required=True,
            metavar="DIR",
            help="the profiler artifacts directory, holding the report's own,"
            " where the test's recordings go",
        )
        report_parser.add_argument(
            "--report",
            required=True,
            metavar="DIR",
            help="the report directory, naming its artifacts directory",
        )
    for measure_parser in (callgrind_parser, timing_parser, trace_parser):
        measure_parser.add_argument(
            "--test", required=True, help="the test the executable runs"
        )
        measure_parser.add_argument(
            "--executable",
            required=True,
            metavar="PATH",
            help="the perf test executable the run measures",
        )
    timing_parser.add_argument("--verbose", action="count", default=0)
    for page_parser in (timing_parser, trace_parser):
        page_parser.add_argument(
            "--executable-shown",
            required=True,
            metavar="PATH",
            help="the executable as the page shows it",
        )
    namespace = parser.parse_args()
    if namespace.cmd == "timing-data":
        PerfMeasure().timing_data_write(
            PerfMeasure.DataArgs(
                artifacts=namespace.artifacts, report=namespace.report
            )
        )
        return
    measure_args = PerfMeasure.MeasureArgs(
        artifacts=namespace.artifacts,
        report=namespace.report,
        test=namespace.test,
        executable=namespace.executable,
    )
    if namespace.cmd == "callgrind":
        PerfMeasure().callgrind_measure(measure_args)
    elif namespace.cmd == "timing":
        PerfMeasure().timing_measure(
            measure_args, namespace.executable_shown, namespace.verbose
        )
    else:
        PerfMeasure().trace_measure(measure_args, namespace.executable_shown)


if __name__ == "__main__":
    main()
