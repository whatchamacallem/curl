#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import NamedTuple, NotRequired, TypedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind
import callgrind_diff
import settings
import theme
from callgrind import Costs, Group

# The page markup and its substitution markers, read from
# scripts/heatmap.html at generate time.
BODY = theme.theme_asset("heatmap.html")

# Directories whose tracked .c/.h are listed even when nothing sampled them,
# so a file with no cost is visibly cold rather than simply missing.
_TREE = ("lib", "include", "src", "tests/perf")


# CallgrindToHeatmap - Turns one profile into a page that shows cost per
# source line, linking the source text from the report's shared copy.
class CallgrindToHeatmap:
    # CallRow - One end of one call edge, as the page's script reads it. Used
    # for a line's callees and for a function's callers alike.
    class CallRow(NamedTuple):
        # the other function, as an index into the functions list
        function: int
        # the file to open when it is clicked
        file: str
        # the line to jump to there
        line: int
        # what the calls cost between them
        cost: Costs
        # how many calls
        count_: int

    # LineCost - One source line's numbers.
    class LineCost(NamedTuple):
        # cost on the line itself
        self_cost: Costs
        # cost below the calls it makes
        calls_cost: Costs
        # how many calls it makes
        count_: int

    # FileModel - One source file as the page's script sees it.
    class FileModel(TypedDict):
        # the file's own cost
        self: Costs
        # cost below what it calls
        calls: Costs
        # the name of this file's script in the report's shared
        # sources/ directory, or None when it is not on this box
        source: str | None
        # per line number, that line's numbers
        lines: dict[str, CallgrindToHeatmap.LineCost]
        # per line number, which function owns it
        lineFunction: dict[str, int]
        # per line number, its baseline cost vector -- a diff's denominator,
        # absent on a non-diff page and on a line the baseline never had
        baseline: NotRequired[dict[str, Costs]]
        # per line number, what that line calls
        callees: dict[str, list[CallgrindToHeatmap.CallRow]]
        # repo, system or external
        group: Group
        # the path as callgrind spelled it
        raw: str

    # FunctionModel - One function as the page's script sees it.
    class FunctionModel(TypedDict):
        # its name
        name: str
        # where to open it
        file: str
        # the line to jump to
        line: int
        # cost in the function itself
        self: Costs
        # cost below what it calls
        calls: Costs
        # who calls it, most expensive first
        callers: list[CallgrindToHeatmap.CallRow]

    # HeatMapTotals - What the heat map needs to label and scale everything.
    # Not the report's LABEL=VALUE rows -- those are build_report.py's
    # ManifestRow.
    class HeatMapTotals(TypedDict):
        # the recorded events, in cost-vector order
        events: list[str]
        # the events the page adds up itself
        derived: list[callgrind.ResolvedDerivedEvent]
        # which event the page opens on
        defaultEvent: str
        # what shares are taken against
        totals: Costs
        # signed numbers and a signed heat ramp
        diff: bool
        # the baseline run's total, what the page's own totals compare to
        baselineTotal: NotRequired[Costs]

    # HeatModel - The whole page's data, in one JSON blob.
    class HeatModel(TypedDict):
        # labels, totals and which event to show
        heatMapTotals: CallgrindToHeatmap.HeatMapTotals
        # the few theme values the script needs
        theme: theme.ThemeRuntime
        # every file that has samples, by display path
        files: dict[str, CallgrindToHeatmap.FileModel]
        # every function, indexed by the call rows
        functions: list[CallgrindToHeatmap.FunctionModel]
        # tracked files with no samples at all
        cold: list[str]
        # per function, its baseline cost vector, indexed like functions
        functionBaseline: NotRequired[list[Costs]]

    # HeatArgs - What this tool reads, and the page it writes.
    class HeatArgs(NamedTuple):
        # the callgrind file(s), merged into one profile
        callgrind_file: list[str]
        # where the page goes
        output: str
        # the page title
        title: str
        # the input is a callgrind_diff.py delta
        diff: bool
        # that delta's synthesized callers diff, holding what each share
        # divides by
        baseline_data: str
        # the report holds this test alone, so this page sits one
        # directory below its root rather than two
        single_test_report: bool

    # SynthesizedCallers - The part of callgrind_diff.py's synthesized callers
    # diff this tool reads: what every share on a diff page divides by. Its
    # vectors carry the recorded slots only, and the page's own script adds a
    # derived event up from them, so both kinds are handed straight through.
    class SynthesizedCallers(TypedDict):
        # keyed by function, and by "<function>\n<file>\n<line>"
        baseline: dict[str, Costs]
        # the baseline run's summed cost vector
        baselineTotal: Costs

    # FileTally - One file's numbers while they are still being added up.
    @dataclass
    class FileTally:
        # repo, system or external
        group: Group
        # the path as callgrind spelled it
        raw: str
        # the file's own cost so far
        self_cost: Costs
        # cost below what it calls, so far
        calls_cost: Costs
        # the source text once it has been read
        source: str | None = None
        # per line number, that line's tally
        lines: dict[str, CallgrindToHeatmap.LineTally] = field(
            default_factory=dict
        )
        # per line number, which function owns it
        line_function: dict[str, int] = field(default_factory=dict)
        # per line number, what that line calls
        callees: dict[str, list[CallgrindToHeatmap.CallRow]] = field(
            default_factory=dict
        )

        # Freeze the tally into the page's own shape, trailing zeros dropped.
        def emit(self) -> CallgrindToHeatmap.FileModel:
            def first(row: CallgrindToHeatmap.CallRow) -> int:
                return -(row.cost[0] if row.cost else 0)

            trim = CallgrindToHeatmap.costs_trim
            return {
                "self": trim(self.self_cost),
                "calls": trim(self.calls_cost),
                "source": (
                    None
                    if self.source is None
                    else CallgrindToHeatmap.source_name(self.raw)
                ),
                "lines": {
                    line: CallgrindToHeatmap.LineCost(
                        trim(record.self_cost),
                        trim(record.calls_cost),
                        record.count,
                    )
                    for line, record in self.lines.items()
                },
                "lineFunction": self.line_function,
                "callees": {
                    line: sorted(rows, key=first)
                    for line, rows in self.callees.items()
                },
                "group": self.group,
                "raw": self.raw,
            }

        # One line's tally, started at zero the first time it is asked for.
        def line(
            self, line_number: int, event_count: int
        ) -> CallgrindToHeatmap.LineTally:
            record = self.lines.get(str(line_number))
            if record is None:
                record = self.lines[str(line_number)] = (
                    CallgrindToHeatmap.LineTally(
                        [0] * event_count, [0] * event_count
                    )
                )
            return record

    # LineTally - One line's numbers while they are still being added up.
    @dataclass
    class LineTally:
        # cost on the line itself, so far
        self_cost: Costs
        # cost below the calls it makes, so far
        calls_cost: Costs
        # how many calls it makes, so far
        count: int = 0

    # Drop trailing zeros, because every cost vector is the full event width
    # and the page does not need what it would only render blank.
    @staticmethod
    def costs_trim(costs: Costs) -> Costs:
        length = len(costs)
        while length and costs[length - 1] == 0:
            length -= 1
        return costs[:length]

    # Turn a finished model into a diff one: shares go against the summed
    # magnitude of every change, since the signed total is near zero.
    def diff_model(
        self,
        model: CallgrindToHeatmap.HeatModel,
        profile: callgrind.Profile,
        baseline_data: str,
    ) -> None:
        synthesized = self.synthesized_callers_load(baseline_data)
        totals = model["heatMapTotals"]
        totals["totals"] = callgrind_diff.profile_magnitudes(profile)
        totals["diff"] = True
        totals["baselineTotal"] = synthesized["baselineTotal"]
        baseline = synthesized["baseline"]
        functions = model["functions"]
        model["functionBaseline"] = [
            baseline.get(func["name"], []) for func in functions
        ]
        for path, entry in model["files"].items():
            lines: dict[str, Costs] = {}
            for line, index in entry["lineFunction"].items():
                costs = baseline.get(
                    f"{functions[index]['name']}\n{path}\n{line}"
                )
                if costs:
                    lines[line] = costs
            entry["baseline"] = lines

    # Resolve every path once, qualifying an external file by its object so
    # two libraries' same-named headers stay apart.
    def display_paths(
        self, profile: callgrind.Profile, raw_files: Sequence[str]
    ) -> dict[str, callgrind.PathInfo]:
        info: dict[str, callgrind.PathInfo] = {}
        for raw in raw_files:
            path_info = callgrind.path_norm(raw)
            if path_info.group == "external":
                object_name = (
                    os.path.basename(profile.file_ob.get(raw, ""))
                    or "(unknown object)"
                )
                path_info = path_info._replace(
                    display=f"{object_name}/{path_info.display}"
                )
            info[raw] = path_info
        return info

    # Add every line, call and callee up per file, and read the source in.
    def files_model(
        self,
        profile: callgrind.Profile,
        info: dict[str, callgrind.PathInfo],
        function_index: dict[str, int],
    ) -> dict[str, CallgrindToHeatmap.FileModel]:
        event_count = len(profile.events)
        display = {raw: path_info.display for raw, path_info in info.items()}
        accumulators: dict[str, CallgrindToHeatmap.FileTally] = {}
        for raw, path_info in info.items():
            entry = accumulators.get(path_info.display)
            if entry is None:
                entry = accumulators[path_info.display] = (
                    CallgrindToHeatmap.FileTally(
                        group=path_info.group,
                        raw=raw
                        if path_info.group == "external"
                        else path_info.display,
                        self_cost=[0] * event_count,
                        calls_cost=[0] * event_count,
                    )
                )
            if entry.source is None and path_info.local:
                entry.source = self.source_read(path_info.local)
        for key, costs in profile.line_self.items():
            entry = accumulators[display[key.file]]
            callgrind.costs_add(entry.self_cost, costs)
            callgrind.costs_add(
                entry.line(key.line, event_count).self_cost, costs
            )
        for key, costs in profile.line_calls.items():
            entry = accumulators[display[key.file]]
            callgrind.costs_add(entry.calls_cost, costs)
            record = entry.line(key.line, event_count)
            callgrind.costs_add(record.calls_cost, costs)
            record.count += profile.line_call_count[key]
        for key, function in profile.line_function.items():
            accumulators[display[key.file]].line_function[str(key.line)] = (
                function_index[function]
            )
        for site, tally in profile.callees.items():
            entry_line = profile.function_entry.get(
                site.callee,
                callgrind.SourceLine(
                    profile.function_home.get(site.callee, "???"), 0
                ),
            )
            accumulators[display[site.file]].callees.setdefault(
                str(site.line), []
            ).append(
                CallgrindToHeatmap.CallRow(
                    function_index[site.callee],
                    display.get(entry_line.file, entry_line.file),
                    entry_line.line,
                    self.costs_trim(tally.costs),
                    tally.count,
                )
            )
        return {name: entry.emit() for name, entry in accumulators.items()}

    # Every function with its entry point and its callers, dearest first.
    def functions_model(
        self,
        profile: callgrind.Profile,
        info: dict[str, callgrind.PathInfo],
        function_names: Sequence[str],
        function_index: dict[str, int],
    ) -> list[CallgrindToHeatmap.FunctionModel]:
        display = {raw: path_info.display for raw, path_info in info.items()}
        functions: list[CallgrindToHeatmap.FunctionModel] = []
        for name in function_names:
            entry = profile.function_entry.get(
                name, callgrind.SourceLine(profile.function_home[name], 0)
            )
            callers = sorted(
                (
                    CallgrindToHeatmap.CallRow(
                        function_index[caller.function],
                        display.get(caller.file, caller.file),
                        caller.line,
                        self.costs_trim(tally.costs),
                        tally.count,
                    )
                    for caller, tally in profile.callers.get(name, {}).items()
                ),
                key=lambda row: -(row.cost[0] if row.cost else 0),
            )
            functions.append(
                {
                    "name": name,
                    "file": display.get(entry.file, entry.file),
                    "line": entry.line,
                    "self": self.costs_trim(
                        profile.function_self.get(name, [])
                    ),
                    "calls": self.costs_trim(
                        profile.function_calls.get(name, [])
                    ),
                    "callers": callers,
                }
            )
        return functions

    # The whole page's data.
    def model(
        self, profile: callgrind.Profile
    ) -> tuple[CallgrindToHeatmap.HeatModel, dict[str, callgrind.PathInfo]]:
        function_names = sorted(profile.function_home)
        function_index = {name: i for i, name in enumerate(function_names)}
        raw_files = sorted(
            {key.file for key in profile.line_self}
            | {key.file for key in profile.line_calls}
            | {entry.file for entry in profile.function_entry.values()}
        )
        info = self.display_paths(profile, raw_files)
        files = self.files_model(profile, info, function_index)
        functions = self.functions_model(
            profile, info, function_names, function_index
        )
        cold = sorted(
            relative
            for relative in self.repo_tracked_files()
            if relative not in files
        )
        default_event = (
            settings.EVENT
            if settings.EVENT in profile.event_names()
            else profile.events[0]
        )
        return {
            "heatMapTotals": {
                "events": profile.events,
                "derived": profile.resolved_derived_events(),
                "defaultEvent": default_event,
                "totals": profile.totals(),
                "diff": False,
            },
            "theme": theme.theme_runtime(),
            "files": files,
            "functions": functions,
            "cold": cold,
        }, info

    # Bake the model into the page.
    def render(
        self,
        model: CallgrindToHeatmap.HeatModel,
        title: str,
        depth: int,
    ) -> str:
        data = json.dumps(model, separators=(",", ":"), ensure_ascii=False)
        data = data.replace("</", "<\\/")
        assets_href = theme.shared_href(depth, theme.ASSETS_DIR)
        sources_href = theme.shared_href(depth, theme.SOURCES_DIR)
        scripts = "".join(
            f'<script src="{sources_href}/{name}"></script>\n'
            for name in sorted(
                entry["source"]
                for entry in model["files"].values()
                if entry["source"] is not None
            )
        )
        scripts += "".join(
            f'<script src="{assets_href}/{name}"></script>\n'
            for name in (theme.UI_STRINGS_JS, theme.THEME_JS, theme.HEATMAP_JS)
        )
        styles = "".join(
            f'<link rel="stylesheet" href="{assets_href}/{name}">\n'
            for name in (theme.THEME_CSS, theme.HEATMAP_CSS)
        )
        body = BODY.replace("__SCRIPTS__", scripts).replace("__DATA__", data)
        return (
            '<!doctype html>\n<html lang="en">\n'
            '<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport"'
            ' content="width=device-width, initial-scale=1">\n'
            f"<title>{theme.html_escape(title)}</title>\n"
            f"{styles}"
            "</head>\n<body>\n" + body + "</body>\n</html>\n"
        )

    # Every tracked .c/.h under _TREE, so a file with no samples still shows.
    def repo_tracked_files(self) -> list[str]:
        try:
            output = subprocess.run(
                ["git", "-C", callgrind.REPO_ROOT, "ls-files", "--", *_TREE],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
        except (OSError, subprocess.CalledProcessError):
            return []
        return [
            line for line in output.split("\n") if line.endswith((".c", ".h"))
        ]

    # Read the profile, build the model and write the one page.
    def run(self, args: CallgrindToHeatmap.HeatArgs) -> None:
        profile = callgrind.profile_load(args.callgrind_file)
        model, info = self.model(profile)
        if args.diff:
            self.diff_model(model, profile, args.baseline_data)
        depth = 1 if args.single_test_report else 2
        page_dir = os.path.dirname(os.path.abspath(args.output))
        self.sources_write(
            os.path.join(page_dir, *[".."] * depth, theme.SOURCES_DIR),
            info,
            model,
        )
        html = self.render(model, args.title, depth)
        os.makedirs(page_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(html)
        shared_count = sum(
            1
            for entry in model["files"].values()
            if entry["source"] is not None
        )
        print(
            f"files with samples: {len(model['files'])}"
            f" ({shared_count} with source shared),"
            f" cold files listed: {len(model['cold'])}, "
            f"functions: {len(model['functions'])}",
            file=sys.stderr,
        )
        print(
            f"wrote {args.output} ({len(html.encode('utf-8')):,} bytes)",
            file=sys.stderr,
        )

    @staticmethod
    def source_name(display: str) -> str:
        flat = "".join(char if char.isalnum() else "_" for char in display)
        return f"{flat}.js"

    # Read one source file, or None when it is not on this box.
    def source_read(self, local: str) -> str | None:
        try:
            with open(local, "rb") as handle:
                data = handle.read()
        except OSError:
            return None
        return data.decode("utf-8", errors="replace")

    def sources_write(
        self,
        out_dir: str,
        info: dict[str, callgrind.PathInfo],
        model: CallgrindToHeatmap.HeatModel,
    ) -> None:
        names = {
            entry["source"]: display
            for display, entry in model["files"].items()
            if entry["source"] is not None
        }
        if not names:
            return
        local_of = {
            path_info.display: path_info.local
            for path_info in info.values()
            if path_info.local
        }
        os.makedirs(out_dir, exist_ok=True)
        for name, display in sorted(names.items()):
            text = self.source_read(local_of.get(display, ""))
            if text is None:
                continue
            body = json.dumps(text, ensure_ascii=False).replace("</", "<\\/")
            with open(
                os.path.join(out_dir, str(name)), "w", encoding="utf-8"
            ) as handle:
                handle.write(
                    "window.report_sources = window.report_sources || {};\n"
                    f"window.report_sources[{json.dumps(display)}] ="
                    f" {body};\n"
                )

    # Read callgrind_diff.py's synthesized callers diff, or nothing when there
    # is none -- a diff built without one simply has no share to show.
    def synthesized_callers_load(
        self, path: str
    ) -> CallgrindToHeatmap.SynthesizedCallers:
        empty: CallgrindToHeatmap.SynthesizedCallers = {
            "baseline": {},
            "baselineTotal": [],
        }
        if not path or not os.path.isfile(path):
            return empty
        with open(path, encoding="utf-8") as handle:
            doc: CallgrindToHeatmap.SynthesizedCallers = json.load(handle)
        return doc


# main - Build one heat map page from the given callgrind file(s).
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "callgrind_file",
        nargs="+",
        help="callgrind output file(s). several are merged into one profile",
    )
    parser.add_argument(
        "--single-test-report",
        action="store_true",
        help="the report holds this test alone, so the shared assets"
        " sit one directory up rather than two",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="output .html path (directories are created)",
    )
    parser.add_argument("--title", required=True)
    parser.add_argument(
        "--diff",
        action="store_true",
        help="the callgrind file is a callgrind_diff.py delta: print "
        "signed numbers and take every share against what the same "
        "function or line cost in the baseline",
    )
    parser.add_argument(
        "--baseline-data",
        default="",
        metavar="FILE",
        help="callgrind_diff.py's synthesized callers diff, holding the "
        "baseline cost each share divides by (--diff only)",
    )
    namespace = parser.parse_args()
    CallgrindToHeatmap().run(
        CallgrindToHeatmap.HeatArgs(
            callgrind_file=namespace.callgrind_file,
            output=namespace.output,
            title=namespace.title,
            diff=namespace.diff,
            baseline_data=namespace.baseline_data,
            single_test_report=namespace.single_test_report,
        )
    )


if __name__ == "__main__":
    main()
