#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import glob
import json
import os
import re
import sys
import tarfile
from collections.abc import Sequence
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind
import settings

# What a report's raw data is stored as, one archive per test.
_ARCHIVE_SUFFIX = ".tar.xz"

# The report's one shared copy of speedscope, and the globs naming what it
# must hold: the engine, its stylesheet and the font the stylesheet names.
_FLAME_APP_DIR = "flame-graph-app"
_FLAME_APP_GLOBS = ("speedscope-*.js", "speedscope-*.css", "*.woff2")

# Only a flame graph our own tool exported counts -- a stale or hand-made one
# must fail.
_FLAME_EXPORTER = "dev/scripts/trace_to_speedscope.py"

# All a per-test flame graph directory may hold: its own page, its own
# recorded profile, and the trace log. Everything else lives in the one
# shared bundle at the report root.
_FLAME_GRAPH_FILES = ("index.html", "output.txt", "profile.js")

# Smallest a file can be before it is plainly a failed generate rather than a
# small page. The flame graph page is a loader -- two script tags and a
# stylesheet link pointing at the shared bundle -- so it has a floor of its
# own, well under the one a page carrying real content must clear.
_MIN_FLAME_JS_BYTES = 200
_MIN_FLAME_PAGE_BYTES = 300
_MIN_HEATMAP_BYTES = 5000
_MIN_INDEX_BYTES = 2000
_MIN_PAGE_BYTES = 500
_MIN_RAW_BYTES = 100

# The diff vocabulary, spelled the same everywhere a reader sees it. These
# are the only non-ASCII characters a source file may contain.
_ALLOWED_UNICODE = (
    "≈",  # almost equal to
    "▲",  # up-pointing triangle
    "▶",  # right-pointing triangle, the heat map's collapsed caret
    "▼",  # down-pointing triangle
    "…",  # horizontal ellipsis
)

# Anything outside plain ASCII that is not in the allow list above.
_NON_ASCII_RE = re.compile(r"[^\x00-\x7F" + "".join(_ALLOWED_UNICODE) + r"]")

# Which files under dev/ the ASCII scan reads.
_UNICODE_SCAN_EXTS = (".py", ".js", ".css", ".sh", ".html", ".c", ".h")
_UNICODE_SCAN_NAMES = ("README.md",)

# Generated output and caches, which the ASCII scan walks straight past.
_UNICODE_SCAN_SKIP_DIRS = (
    "__pycache__",
    "perf2html_baseline_report",
    "perf2html_modified_report",
    "perf2html_diff_report",
)


# ValidateReport - A structural smoke test over a finished report directory:
# every page present, closed, titled, and free of leftover markers.
class ValidateReport:
    # NonAsciiLine - One line of one file that broke the ASCII rule.
    class NonAsciiLine(NamedTuple):
        # the file it is in
        path: str
        # which line, 1-based
        line_no: int
        # the line itself, for the message
        line: str

    # ReportLayout - What one kind of report is expected to contain -- this is
    # the whole difference between checking a full report and a diff.
    class ReportLayout(NamedTuple):
        # the per-test views that must exist
        subpages: tuple[str, ...]
        # the pattern the top-N heading has to match
        heading: str
        # header blocks the overview must carry
        header_blocks: tuple[str, ...]
        # the exact first line of MANIFEST.txt
        manifest_version: str
        # the LABEL= rows MANIFEST.txt must have
        manifest_labels: tuple[str, ...]
        # whether a test records runs of its own: a perf log, a trace, a
        # flame graph. never true of the synthesized "all"
        test_has_rawdata: bool
        # whether "all" stores an archive of its own, which it does only
        # where its pages are built from data no other test's archive holds
        all_has_archive: bool

    # ValidateArgs - Which report to check, and which layout to check it as.
    class ValidateArgs(NamedTuple):
        # the report directory
        out_dir: str
        # check it as a diff report rather than a full one
        diff: bool

    def __init__(self) -> None:
        self.errors: list[str] = []

    # Record one problem -- every check runs, so one page cannot hide another.
    def fail(self, message: str) -> None:
        self.errors.append(message)

    # The one shared speedscope bundle every flame graph page loads. It holds
    # exactly one file per glob, so a page can name it without a version.
    def flame_app_check(self, out_dir: str) -> None:
        app_dir = os.path.join(out_dir, _FLAME_APP_DIR)
        if not os.path.isdir(app_dir):
            self.fail(f"no shared speedscope bundle: {app_dir}")
            return
        for pattern in _FLAME_APP_GLOBS:
            found = sorted(glob.glob(os.path.join(app_dir, pattern)))
            if len(found) != 1:
                self.fail(
                    f"{_FLAME_APP_DIR}/ holds {len(found)} files matching "
                    f"{pattern}, expected exactly 1: {app_dir}"
                )

    # A flame graph must hold exactly one evented profile our own tool wrote,
    # and must be absent entirely when no trace was recorded.
    def flame_graph_check(self, out_dir: str, has_trace: bool) -> None:
        flame_dir = os.path.join(out_dir, "flame-graph")
        index_text = self.size_check(
            os.path.join(out_dir, "index.html"), _MIN_INDEX_BYTES, "index.html"
        )
        if not has_trace:
            if os.path.exists(flame_dir) or "<h2>trace log</h2>" in index_text:
                self.fail(
                    "a flame graph where no trace was recorded"
                    f" (flame-graph/ or a 'trace log' section): {out_dir}"
                )
            return
        if index_text and "<h2>trace log</h2>" not in index_text:
            self.fail(
                "index.html has no 'trace log' section: "
                f"{os.path.join(out_dir, 'index.html')}"
            )
        page = self.page_check(
            os.path.join(flame_dir, "index.html"),
            "flame-graph/index.html",
            _MIN_FLAME_PAGE_BYTES,
        )
        # the engine is not here, so the page is only a page if it reaches
        # the shared bundle -- and every asset it names must exist
        for href in re.findall(r'(?:src|href)="([^"]+)"', page):
            if not os.path.isfile(os.path.join(flame_dir, href)):
                self.fail(
                    f"flame-graph/index.html names {href}, which is not"
                    f" there: {flame_dir}"
                )
        if f"{_FLAME_APP_DIR}/" not in page:
            self.fail(
                "flame-graph/index.html does not load the shared "
                f"{_FLAME_APP_DIR}/ bundle: {flame_dir}/index.html"
            )
        self.size_check(
            os.path.join(flame_dir, "output.txt"), 20, "flame-graph/output.txt"
        )
        script = self.size_check(
            os.path.join(flame_dir, "profile.js"),
            _MIN_FLAME_JS_BYTES,
            "flame-graph/profile.js",
        )
        if not script:
            return
        if "loadFileFromBase64" not in script:
            self.fail(
                "flame-graph/profile.js does not call loadFileFromBase64: "
                f"{flame_dir}/profile.js"
            )
        match = re.search(r'var document_base64 = "([A-Za-z0-9+/=]+)"', script)
        try:
            document = (
                json.loads(base64.b64decode(match.group(1))) if match else {}
            )
        except ValueError:
            document = {}
        kinds = [
            profile.get("type") for profile in document.get("profiles", [])
        ]
        if document.get("exporter") != _FLAME_EXPORTER or kinds != ["evented"]:
            self.fail(
                "flame-graph/profile.js does not hold one recorded trace from "
                f"{_FLAME_EXPORTER} (exporter {document.get('exporter')!r}, "
                f"profiles {kinds}): {flame_dir}/profile.js"
            )
        # the engine is shared at the report root, so a copy of it here is
        # the per-test duplication that sharing exists to remove
        for stray in sorted(os.listdir(flame_dir)):
            if stray not in _FLAME_GRAPH_FILES:
                self.fail(
                    f"flame-graph/{stray} duplicates the shared "
                    f"{_FLAME_APP_DIR}/ bundle: {flame_dir}"
                )

    # The heat map must be there, and must carry its own runtime script.
    def heat_map_check(self, out_dir: str, test_name: str) -> None:
        path = os.path.join(out_dir, "heat-map", "index.html")
        text = self.page_check(
            path,
            "heat-map/index.html",
            _MIN_HEATMAP_BYTES,
            f"{test_name} / heat map",
        )
        if text and "report_ui.layout_activate" not in self.page_scripts(
            path, text
        ):
            self.fail(
                "heat-map/index.html is missing its runtime script"
                f" (no report_ui.layout_activate): {path}"
            )

    # Nothing anywhere may name the author's home directory -- a report gets
    # copied off this box.
    def home_dir_check(self, out_dir: str) -> None:
        home = os.path.expanduser("~")
        if home == "~":
            return
        for root, _dirs, names in os.walk(out_dir):
            for name in names:
                path = os.path.join(root, name)
                try:
                    with open(
                        path, encoding="utf-8", errors="replace"
                    ) as handle:
                        text = handle.read()
                except OSError:
                    continue
                if home in text:
                    self.fail(
                        f"{os.path.relpath(path, out_dir)} leaks the"
                        f" author's home directory {home!r} -- reports are"
                        f" copied around and must not reveal who made"
                        f" them: {path}"
                    )

    # One test's summary page: its top-N table, its view links, its raw data.
    def index_check(
        self,
        out_dir: str,
        test_name: str,
        layout: ValidateReport.ReportLayout,
        has_rawdata: bool,
        has_archive: bool,
    ) -> None:
        path = os.path.join(out_dir, "index.html")
        text = self.page_check(path, "index.html", _MIN_INDEX_BYTES, test_name)
        if not text:
            return
        if not re.search(layout.heading, text):
            self.fail(
                "index.html has no 'top N functions' section matching "
                f"{layout.heading!r}: {path}"
            )
        for key in layout.subpages:
            wanted = key != "flame-graph" or has_rawdata
            if wanted != (f'href="{key}/index.html"' in text):
                lack = "is missing its" if wanted else "should not have a"
                self.fail(f"index.html {lack} {key} strip link: {path}")
        if has_archive and "raw data" not in text:
            self.fail(f"index.html has no 'raw data' section: {path}")
        elif not has_archive and "raw data" in text:
            self.fail(
                "index.html has a 'raw data' section, but it should"
                f" not: {path}"
            )

    # MANIFEST.txt's first line is what makes a directory a diff input, so it
    # has to be exact.
    def manifest_check(
        self, out_dir: str, layout: ValidateReport.ReportLayout
    ) -> None:
        path = os.path.join(out_dir, "MANIFEST.txt")
        text = self.size_check(path, 40, "MANIFEST.txt")
        if not text:
            return
        first = text.split("\n", 1)[0]
        if first != layout.manifest_version:
            self.fail(
                f"MANIFEST.txt starts with {first!r}, expected the"
                f" version line {layout.manifest_version!r}: {path}"
            )
        for label in layout.manifest_labels:
            if not re.search(rf"^{label}=.+$", text, re.M):
                self.fail(
                    f"MANIFEST.txt has no '{label}=' header row, so a"
                    f" reader of this report cannot show it: {path}"
                )

    # One file out of an open archive, as text a scan can search.
    def member_text(
        self, archive: tarfile.TarFile, member: tarfile.TarInfo
    ) -> str:
        handle = archive.extractfile(member)
        if handle is None:
            return ""
        return handle.read().decode("utf-8", errors="replace")

    # The overview page: its test-suites table, one link per test, its blocks.
    def overview_check(
        self,
        out_dir: str,
        tests: Sequence[str],
        layout: ValidateReport.ReportLayout,
    ) -> None:
        path = os.path.join(out_dir, "index.html")
        text = self.page_check(
            path, "index.html", _MIN_INDEX_BYTES, "overview"
        )
        if not text:
            return
        if "<h2>test suites</h2>" not in text:
            self.fail(
                f"overview index.html has no 'test suites' section: {path}"
            )
        for test_name in tests:
            if f'href="{test_name}/index.html"' not in text:
                self.fail(
                    "overview index.html is missing its"
                    f" {test_name} strip link: {path}"
                )
        for heading in layout.header_blocks:
            if f"<h2>{heading}</h2>" not in text:
                self.fail(
                    f"overview index.html has no '{heading}'"
                    f" header block: {path}"
                )

    # Which tests this report holds, taken from the overview's own links.
    def overview_test_names(self, index_path: str, out_dir: str) -> list[str]:
        with open(index_path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        names: list[str] = []
        for match in re.finditer(r'href="([\w.-]+)/index\.html"', text):
            test_name = match.group(1)
            if os.path.isdir(os.path.join(out_dir, test_name)):
                names.append(test_name)
        return names

    # Any page at all: big enough, titled, closed, and no template leftovers.
    def page_check(
        self,
        path: str,
        label: str,
        min_bytes: int = _MIN_PAGE_BYTES,
        want_title: str | None = None,
    ) -> str:
        text = self.size_check(path, min_bytes, label)
        if not text:
            return text
        if "<title>" not in text:
            self.fail(f"{label} has no <title>: {path}")
        elif want_title is not None:
            match = re.search(r"<title>(.*?)</title>", text, re.S)
            got = match.group(1) if match else ""
            if got != want_title:
                self.fail(
                    f"{label} title is {got!r}, expected"
                    f" {want_title!r}: {path}"
                )
        if "</html>" not in text:
            self.fail(
                f"{label} is not a closed HTML document (no </html>): {path}"
            )
        for marker in (
            "__DATA__",
            "__NAME__",
            "Traceback (most recent call last)",
            "NaN%",
        ):
            if marker in text:
                self.fail(
                    f"{label} contains a leftover template/error marker "
                    f"{marker!r}: {path}"
                )
        return text

    # Everything a page runs or styles itself with, inline or linked. A
    # linked asset is read off disk and a missing one fails, so a page whose
    # relative href into the shared theme is wrong cannot pass by looking
    # like a page that simply inlines less.
    def page_scripts(self, path: str, text: str) -> str:
        parts = [text]
        page_dir = os.path.dirname(path)
        for href in re.findall(
            r'<(?:script[^>]*\ssrc|link[^>]*\shref)="([^"]+)"', text
        ):
            asset = os.path.join(page_dir, href)
            try:
                with open(asset, encoding="utf-8", errors="replace") as handle:
                    parts.append(handle.read())
            except OSError as error:
                self.fail(f"{path} links {href}, which is unreadable: {error}")
        return "\n".join(parts)

    # A page's title, which is how we tell an overview from a test page.
    def page_title(self, index_path: str) -> str:
        with open(index_path, encoding="utf-8", errors="replace") as handle:
            match = re.search(r"<title>(.*?)</title>", handle.read())
        return match.group(1) if match else ""

    # The perf log: a real timing line, and a section only where one exists.
    def perf_tool_check(self, out_dir: str, has_perf_log: bool) -> None:
        out_txt = os.path.join(out_dir, "perf-tool", "output.txt")
        text = self.size_check(out_txt, 20, "perf-tool/output.txt")
        if text and not re.search(r"^Time(/\w+)?:\s+\d", text, re.M):
            self.fail(
                "perf-tool/output.txt has no recognizable timing"
                f" line: {out_txt}"
            )
        index_text = self.size_check(
            os.path.join(out_dir, "index.html"), _MIN_INDEX_BYTES, "index.html"
        )
        if index_text:
            if has_perf_log and "<h2>perf log</h2>" not in index_text:
                self.fail(
                    "index.html has no 'perf log' section: "
                    f"{os.path.join(out_dir, 'index.html')}"
                )
            elif not has_perf_log and "<h2>perf log</h2>" in index_text:
                self.fail(
                    f"index.html has a 'perf log' section, but it should not: "
                    f"{os.path.join(out_dir, 'index.html')}"
                )

    # One archive: openable, holding a callgrind file, and naming no
    # absolute path from the box that made it.
    def raw_archive_check(self, path: str, name: str) -> None:
        self.size_check(path, _MIN_RAW_BYTES, f"raw/{name}")
        try:
            with tarfile.open(path, "r:xz") as archive:
                texts = {
                    member.name.lstrip("./"): self.member_text(archive, member)
                    for member in archive.getmembers()
                    if member.isfile()
                }
        except (OSError, tarfile.TarError) as error:
            self.fail(f"raw/{name} is not readable as tar.xz: {path}: {error}")
            return
        if not any(
            inner.startswith("callgrind.")
            and not inner.endswith(settings.CALLERS_SUFFIX)
            and "events:" in text[:4096]
            for inner, text in texts.items()
        ):
            self.fail(
                f"raw/{name} holds no callgrind file with an 'events:' line"
                f" near its top: {path}"
            )
        for inner, text in texts.items():
            if callgrind.REPO_ROOT in text:
                self.fail(
                    f"raw/{name} still contains the absolute repo root "
                    f"{callgrind.REPO_ROOT!r} in {inner}: {path}"
                )

    # Raw data is one tar.xz per test, holding a real callgrind file with the
    # repo root stripped. "all" synthesizes its pages from the other tests'
    # profiles and stores nothing of its own, so it has no raw/ at all.
    def raw_dir_check(self, out_dir: str, has_rawdata: bool) -> None:
        raw_dir = os.path.join(out_dir, "raw")
        if not has_rawdata:
            if os.path.exists(raw_dir):
                self.fail(
                    "raw/ in a test that records nothing of its own"
                    f": {raw_dir}"
                )
            return
        names = sorted(os.listdir(raw_dir)) if os.path.isdir(raw_dir) else []
        archives = [name for name in names if name.endswith(_ARCHIVE_SUFFIX)]
        if not archives:
            self.fail(f"raw/ has no {_ARCHIVE_SUFFIX} archive: {raw_dir}")
        for name in names:
            if name not in archives:
                self.fail(
                    f"raw/{name} is not a {_ARCHIVE_SUFFIX} archive -- raw"
                    f" data is stored compressed: {raw_dir}"
                )
        for name in archives:
            self.raw_archive_check(os.path.join(raw_dir, name), name)

    # Check one whole report, overview or single test, and report every
    # problem at once.
    def run(self, args: ValidateReport.ValidateArgs) -> int:
        out_dir = os.path.abspath(args.out_dir)
        index_path = os.path.join(out_dir, "index.html")
        if not os.path.isfile(index_path):
            print(
                f"error: no index.html in {out_dir}"
                " -- not a report directory?",
                file=sys.stderr,
            )
            return 1
        name = self.page_title(index_path)
        layout = _LAYOUT_DIFF if args.diff else _LAYOUT_FULL

        self.home_dir_check(out_dir)
        self.manifest_check(out_dir, layout)
        if name == "overview":
            tests = self.overview_test_names(index_path, out_dir)
            self.overview_check(out_dir, tests, layout)
            if "flame-graph" in layout.subpages:
                self.flame_app_check(out_dir)
            for test_name in tests:
                self.test_report_check(
                    os.path.join(out_dir, test_name), test_name, layout
                )
        else:
            self.test_report_check(
                out_dir, name or os.path.basename(out_dir), layout
            )

        if self.errors:
            print(
                f"validate_report: {len(self.errors)} problem(s)"
                f" in {out_dir}:",
                file=sys.stderr,
            )
            for error in self.errors:
                print(f"  - {error}", file=sys.stderr)
            return 1
        print(f"validate_report: ok ({out_dir})", file=sys.stderr)
        return 0

    # Read a file, complaining if it is missing or implausibly small.
    def size_check(self, path: str, min_bytes: int, label: str) -> str:
        try:
            size = os.path.getsize(path)
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError as error:
            self.fail(f"{label}: {path}: {error}")
            return ""
        if size < min_bytes:
            self.fail(
                f"{label} suspiciously small ({size} bytes <"
                f" {min_bytes}): {path}"
            )
        return text

    # Everything one test's directory should hold, per the layout.
    def test_report_check(
        self, out_dir: str, name: str, layout: ValidateReport.ReportLayout
    ) -> None:
        has_rawdata = layout.test_has_rawdata and name != "all"
        # a diff stores one delta per test, "all" included, because it
        # subtracts the merged profiles rather than re-reading each test's
        has_archive = layout.all_has_archive or name != "all"
        self.index_check(out_dir, name, layout, has_rawdata, has_archive)
        self.heat_map_check(out_dir, name)
        self.raw_dir_check(out_dir, has_archive)
        if "flame-graph" in layout.subpages:
            self.flame_graph_check(out_dir, has_rawdata)
        if layout.test_has_rawdata:
            self.perf_tool_check(out_dir, has_rawdata)

    # The sources themselves must stay plain ASCII.
    def unicode_check(self) -> None:
        for path in self.unicode_scan_paths():
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    lines = handle.readlines()
            except OSError:
                continue
            for line_no, line in enumerate(lines, start=1):
                match = _NON_ASCII_RE.search(line)
                if match:
                    found = ValidateReport.NonAsciiLine(
                        path=path, line_no=line_no, line=line.rstrip("\n")
                    )
                    self.fail(
                        f"{os.path.relpath(found.path, callgrind.REPO_ROOT)}:"
                        f"{found.line_no} contains a non-ASCII character "
                        f"{match.group()!r}: {found.line.strip()}"
                    )

    # Every source file under dev/ the ASCII scan covers.
    def unicode_scan_paths(self) -> list[str]:
        dev_dir = os.path.join(callgrind.REPO_ROOT, "dev")
        paths: list[str] = []
        for root, dirs, names in os.walk(dev_dir):
            dirs[:] = [
                d
                for d in dirs
                if d not in _UNICODE_SCAN_SKIP_DIRS and not d.startswith(".")
            ]
            for name in names:
                if (
                    name.endswith(_UNICODE_SCAN_EXTS)
                    or name in _UNICODE_SCAN_NAMES
                ):
                    paths.append(os.path.join(root, name))
        return sorted(paths)


# What a perf2html_diff.sh report must contain: no flame graph, no timing.
_LAYOUT_DIFF = ValidateReport.ReportLayout(
    ("heat-map",),
    r"<h2>top \d+ functions by change in self</h2>",
    ("baseline", "modified"),
    "curl/perf2html_diff.sh v1",
    ("baseline", "modified", "stamp"),
    False,
    True,
)

# What a perf2html.sh report must contain.
_LAYOUT_FULL = ValidateReport.ReportLayout(
    ("flame-graph", "heat-map"),
    r"<h2>top \d+ functions by self</h2>",
    (),
    "curl/perf2html.sh v1",
    ("sampled", "revision", "cpu", "build", "executable", "stamp"),
    True,
    False,
)


# main - Check the sources are ASCII, then check the given report.
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", help="a report directory")
    parser.add_argument(
        "--diff",
        action="store_true",
        help="a perf2html_diff.sh report: heat map only",
    )
    namespace = parser.parse_args()
    validator = ValidateReport()
    validator.unicode_check()
    return validator.run(
        ValidateReport.ValidateArgs(
            out_dir=namespace.out_dir, diff=namespace.diff
        )
    )


if __name__ == "__main__":
    sys.exit(main())
