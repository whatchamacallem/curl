#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections.abc import Sequence
import os
import re
import sys
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind

MIN_FLAME_JS_BYTES = 200
MIN_HEATMAP_BYTES = 5000
MIN_INDEX_BYTES = 2000
MIN_PAGE_BYTES = 500
MIN_RAW_BYTES = 100

NON_ASCII_RE = re.compile(r"[^\x00-\x7F]")
UNICODE_SCAN_EXTS = (".py", ".js", ".css", ".sh")
UNICODE_SCAN_NAMES = ("README.md",)
UNICODE_SCAN_SKIP_DIRS = ("__pycache__", "perf2html_baseline_report", "perf2html_modified_report",
                         "perf2html_diff_report")


class Layout(NamedTuple):
    subpages: tuple[str, ...]
    heading: str
    header_blocks: tuple[str, ...]
    manifest_version: str
    manifest_labels: tuple[str, ...]
    test_has_rawdata: bool


class NonAsciiLine(NamedTuple):
    path: str
    line_no: int
    line: str


class ValidateArgs(NamedTuple):
    out_dir: str
    diff: bool


LAYOUT_FULL = Layout(("flame-graph", "heat-map"), r"<h2>top \d+ functions by self</h2>", (),
                     "curl/perf2html.sh v1", ("sampled", "revision", "cpu", "build", "executable"), True)
LAYOUT_DIFF = Layout(("heat-map",), r"<h2>top \d+ functions by change in self</h2>",
                     ("baseline", "modified"),
                     "curl/perf2html_diff.sh v1", ("baseline", "modified"), False)


class ValidateReport:
    def __init__(self) -> None:
        self.errors: list[str] = []

    def fail(self, message: str) -> None:
        self.errors.append(message)

    def flame_graph_check(self, out_dir: str) -> None:
        flame_dir = os.path.join(out_dir, "flame-graph")
        self.page_check(os.path.join(flame_dir, "index.html"), "flame-graph/index.html")
        script = self.size_check(os.path.join(flame_dir, "profile.js"), MIN_FLAME_JS_BYTES, "flame-graph/profile.js")
        if script and "loadFileFromBase64" not in script:
            self.fail(f"flame-graph/profile.js does not call loadFileFromBase64: {flame_dir}/profile.js")

    def heat_map_check(self, out_dir: str, test_name: str) -> None:
        path = os.path.join(out_dir, "heat-map", "index.html")
        text = self.page_check(path, "heat-map/index.html", MIN_HEATMAP_BYTES, f"{test_name} / heat map")
        if text and "heatStyle" not in text:
            self.fail(f"heat-map/index.html is missing its runtime script (no heatStyle): {path}")

    def home_dir_check(self, out_dir: str) -> None:
        home = os.path.expanduser("~")
        if home == "~":
            return
        for root, _dirs, names in os.walk(out_dir):
            for name in names:
                path = os.path.join(root, name)
                try:
                    with open(path, encoding="utf-8", errors="replace") as handle:
                        text = handle.read()
                except OSError:
                    continue
                if home in text:
                    self.fail(f"{os.path.relpath(path, out_dir)} leaks the author's home directory {home!r} -- "
                              f"reports are copied around and must not reveal who made them: {path}")

    def index_check(self, out_dir: str, test_name: str, layout: Layout) -> None:
        path = os.path.join(out_dir, "index.html")
        text = self.page_check(path, "index.html", MIN_INDEX_BYTES, test_name)
        if not text:
            return
        if not re.search(layout.heading, text):
            self.fail(f"index.html has no 'top N functions' section matching {layout.heading!r}: {path}")
        for key in layout.subpages:
            if f'href="{key}/index.html"' not in text:
                self.fail(f"index.html is missing its {key} strip link: {path}")
        if layout.test_has_rawdata and "raw data" not in text:
            self.fail(f"index.html has no 'raw data' section: {path}")
        elif not layout.test_has_rawdata and "raw data" in text:
            self.fail(f"index.html has a 'raw data' section, but a diff summary page should not: {path}")

    def manifest_check(self, out_dir: str, layout: Layout) -> None:
        path = os.path.join(out_dir, "MANIFEST.txt")
        text = self.size_check(path, 40, "MANIFEST.txt")
        if not text:
            return
        first = text.split("\n", 1)[0]
        if first != layout.manifest_version:
            self.fail(f"MANIFEST.txt starts with {first!r}, expected the version line "
                      f"{layout.manifest_version!r}: {path}")
        for label in layout.manifest_labels:
            if not re.search(rf"^{label}=.+$", text, re.M):
                self.fail(f"MANIFEST.txt has no '{label}=' header row, so a reader of this report cannot "
                          f"show it: {path}")

    def overview_check(self, out_dir: str, tests: Sequence[str], layout: Layout) -> None:
        path = os.path.join(out_dir, "index.html")
        text = self.page_check(path, "index.html", MIN_INDEX_BYTES, "overview")
        if not text:
            return
        if "<h2>test suites</h2>" not in text:
            self.fail(f"overview index.html has no 'test suites' section: {path}")
        for test_name in tests:
            if f'href="{test_name}/index.html"' not in text:
                self.fail(f"overview index.html is missing its {test_name} strip link: {path}")
        for heading in layout.header_blocks:
            if f"<h2>{heading}</h2>" not in text:
                self.fail(f"overview index.html has no '{heading}' header block: {path}")

    def overview_test_names(self, index_path: str, out_dir: str) -> list[str]:
        with open(index_path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        names: list[str] = []
        for match in re.finditer(r'href="([\w.-]+)/index\.html"', text):
            test_name = match.group(1)
            if os.path.isdir(os.path.join(out_dir, test_name)):
                names.append(test_name)
        return names

    def page_check(self, path: str, label: str, min_bytes: int = MIN_PAGE_BYTES,
                   want_title: str | None = None) -> str:
        text = self.size_check(path, min_bytes, label)
        if not text:
            return text
        if "<title>" not in text:
            self.fail(f"{label} has no <title>: {path}")
        elif want_title is not None:
            match = re.search(r"<title>(.*?)</title>", text, re.S)
            got = match.group(1) if match else ""
            if got != want_title:
                self.fail(f"{label} title is {got!r}, expected {want_title!r}: {path}")
        if "</html>" not in text:
            self.fail(f"{label} is not a closed HTML document (no </html>): {path}")
        for marker in ("__DATA__", "__NAME__", "Traceback (most recent call last)", "NaN%"):
            if marker in text:
                self.fail(f"{label} contains a leftover template/error marker {marker!r}: {path}")
        return text

    def page_title(self, index_path: str) -> str:
        with open(index_path, encoding="utf-8", errors="replace") as handle:
            match = re.search(r"<title>(.*?)</title>", handle.read())
        return match.group(1) if match else ""

    def perf_tool_check(self, out_dir: str, test_name: str) -> None:
        out_txt = os.path.join(out_dir, "perf-tool", "output.txt")
        text = self.size_check(out_txt, 20, "perf-tool/output.txt")
        if text:
            if not re.search(r"^Time(/\w+)?:\s+\d", text, re.M):
                self.fail(f"perf-tool/output.txt has no recognizable timing line: {out_txt}")
            if test_name == "urlparser" and "Errors:" not in text:
                self.fail(f"perf-tool/output.txt has no 'Errors:' line (urlparser is expected to print one): {out_txt}")
        index_text = self.size_check(os.path.join(out_dir, "index.html"), MIN_INDEX_BYTES, "index.html")
        if index_text and "<h2>perf log</h2>" not in index_text:
            self.fail(f"index.html has no 'perf log' section: {os.path.join(out_dir, 'index.html')}")

    def raw_dir_check(self, out_dir: str) -> None:
        raw_dir = os.path.join(out_dir, "raw")
        files = sorted(os.listdir(raw_dir)) if os.path.isdir(raw_dir) else []
        if not files:
            self.fail(f"raw/ has no callgrind file: {raw_dir}")
            return
        for name in files:
            path = os.path.join(raw_dir, name)
            text = self.size_check(path, MIN_RAW_BYTES, f"raw/{name}")
            if "events:" not in text[:4096]:
                self.fail(f"raw data file does not look like a callgrind trace (no 'events:' near the top): {path}")
            if callgrind.REPO_ROOT in text:
                self.fail(f"raw/{name} still contains the absolute repo root {callgrind.REPO_ROOT!r}: {path}")

    def run(self, args: ValidateArgs) -> int:
        out_dir = os.path.abspath(args.out_dir)
        index_path = os.path.join(out_dir, "index.html")
        if not os.path.isfile(index_path):
            print(f"error: no index.html in {out_dir} -- not a report directory?", file=sys.stderr)
            return 1
        name = self.page_title(index_path)
        layout = LAYOUT_DIFF if args.diff else LAYOUT_FULL

        self.home_dir_check(out_dir)
        self.manifest_check(out_dir, layout)
        if name == "overview":
            tests = self.overview_test_names(index_path, out_dir)
            self.overview_check(out_dir, tests, layout)
            for test_name in tests:
                self.test_report_check(os.path.join(out_dir, test_name), test_name, layout)
        else:
            self.test_report_check(out_dir, name or os.path.basename(out_dir), layout)

        if self.errors:
            print(f"validate_report: {len(self.errors)} problem(s) in {out_dir}:", file=sys.stderr)
            for error in self.errors:
                print(f"  - {error}", file=sys.stderr)
            return 1
        print(f"validate_report: ok ({out_dir})", file=sys.stderr)
        return 0

    def size_check(self, path: str, min_bytes: int, label: str) -> str:
        try:
            size = os.path.getsize(path)
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError as error:
            self.fail(f"{label}: {path}: {error}")
            return ""
        if size < min_bytes:
            self.fail(f"{label} suspiciously small ({size} bytes < {min_bytes}): {path}")
        return text

    def test_report_check(self, out_dir: str, name: str, layout: Layout) -> None:
        self.index_check(out_dir, name, layout)
        self.heat_map_check(out_dir, name)
        self.raw_dir_check(out_dir)
        if "flame-graph" in layout.subpages:
            self.flame_graph_check(out_dir)
        if layout.test_has_rawdata:
            self.perf_tool_check(out_dir, name)

    def unicode_check(self) -> None:
        for path in self.unicode_scan_paths():
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    lines = handle.readlines()
            except OSError:
                continue
            for line_no, line in enumerate(lines, start=1):
                match = NON_ASCII_RE.search(line)
                if match:
                    found = NonAsciiLine(path=path, line_no=line_no, line=line.rstrip("\n"))
                    self.fail(f"{os.path.relpath(found.path, callgrind.REPO_ROOT)}:{found.line_no} "
                              f"contains a non-ASCII character {match.group()!r}: {found.line.strip()}")

    def unicode_scan_paths(self) -> list[str]:
        dev_dir = os.path.join(callgrind.REPO_ROOT, "dev")
        paths: list[str] = []
        for root, dirs, names in os.walk(dev_dir):
            dirs[:] = [d for d in dirs if d not in UNICODE_SCAN_SKIP_DIRS and not d.startswith(".")]
            for name in names:
                if name.endswith(UNICODE_SCAN_EXTS) or name in UNICODE_SCAN_NAMES:
                    paths.append(os.path.join(root, name))
        return sorted(paths)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", help="a report directory")
    parser.add_argument("--diff", action="store_true", help="a perf2html_diff.sh report: heat map only")
    namespace = parser.parse_args()
    validator = ValidateReport()
    validator.unicode_check()
    return validator.run(ValidateArgs(out_dir=namespace.out_dir, diff=namespace.diff))


if __name__ == "__main__":
    sys.exit(main())
