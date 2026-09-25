#!/usr/bin/env python3
from __future__ import annotations

import argparse, base64, glob, json, os, re, subprocess, sys, tarfile
from collections.abc import Sequence
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind, settings

# All constants needed from settings.py have to be loaded here before anything
# else.
_DIFF_CALLER_COUNTS_FILE_SUFFIX: str = ""
_FLAME_GRAPH_APP_DIR_NAME: str = ""
_FLAME_GRAPH_APP_FILE_GLOBS: tuple[str, ...] = ()
_FLAME_GRAPH_EXPORTER_NAME: str = ""
_FLAME_GRAPH_PAGE_FILE_NAMES: tuple[str, ...] = ()
_FLAME_GRAPH_VIEW_ENTRY: tuple[str, str, str] = ("", "", "")
_HEAT_MAP_VIEW_ENTRY: tuple[str, str, str] = ("", "", "")
_REPORT_MANIFEST_CHECKSUM_LABEL: str = ""
_REPORT_MANIFEST_VERSION_DIFF: str = ""
_REPORT_MANIFEST_VERSION_FULL: str = ""
_REPORT_RAW_ARCHIVE_SUFFIX: str = ""
_REPORT_SOURCES_DIR_NAME: str = ""
settings.load_into(__name__)


# ValidateReport - A structural smoke test over a finished report directory:
# every page present, closed, titled, and free of leftover markers.
class ValidateReport:
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
        # every problem found so far, printed together at the end
        self.errors: list[str] = []

    # The POSIX cksum of every file except MANIFEST.txt, run through the
    # very pipeline scripts/shared.sh wrote the row with, never our own.
    def checksum_compute(self, out_dir: str) -> str:
        try:
            done = subprocess.run(
                ["sh", "-c", _REPORT_CHECKSUM_COMMAND],
                cwd=out_dir,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as error:
            self.fail(f"cannot checksum {out_dir}: {error}")
            return ""
        if done.returncode != 0:
            self.fail(
                f"cannot checksum {out_dir}: cksum exited"
                f" {done.returncode}: {done.stderr.strip()}"
            )
            return ""
        return done.stdout.strip()

    # Record one problem -- every check runs, so one page cannot hide another.
    def fail(self, message: str) -> None:
        self.errors.append(message)

    # The one shared speedscope bundle every flame graph page loads. It holds
    # exactly one file per glob, so a page can name it without a version.
    def flame_app_check(self, out_dir: str) -> None:
        app_dir = os.path.join(out_dir, _FLAME_GRAPH_APP_DIR_NAME)
        if not os.path.isdir(app_dir):
            self.fail(f"no shared speedscope bundle: {app_dir}")
            return
        for pattern in _FLAME_GRAPH_APP_FILE_GLOBS:
            found = sorted(glob.glob(os.path.join(app_dir, pattern)))
            if len(found) != 1:
                self.fail(
                    f"{_FLAME_GRAPH_APP_DIR_NAME}/ holds {len(found)} files"
                    f" matching {pattern}, expected exactly 1: {app_dir}"
                )

    # A flame graph must hold exactly one evented profile our own tool wrote,
    # and must be absent entirely when no trace was recorded.
    def flame_graph_check(self, out_dir: str, has_trace: bool) -> None:
        flame_dir = os.path.join(out_dir, _FLAME_GRAPH_VIEW_KEY)
        index_text = self.size_check(
            os.path.join(out_dir, "index.html"),
            _VALIDATE_OVERVIEW_PAGE_LEAST_BYTES,
            "index.html",
        )
        if not has_trace:
            if os.path.exists(flame_dir) or "<h2>trace log</h2>" in index_text:
                self.fail(
                    "a flame graph where no trace was recorded"
                    f" ({_FLAME_GRAPH_VIEW_KEY}/ or a 'trace log'"
                    f" section): {out_dir}"
                )
            return
        if index_text and "<h2>trace log</h2>" not in index_text:
            self.fail(
                "index.html has no 'trace log' section: "
                f"{os.path.join(out_dir, 'index.html')}"
            )
        # page_check follows every href itself, so an asset that is not
        # there has already failed by the time this returns
        page = self.page_check(
            os.path.join(flame_dir, "index.html"),
            f"{_FLAME_GRAPH_VIEW_KEY}/index.html",
            _VALIDATE_FLAME_GRAPH_PAGE_LEAST_BYTES,
        )
        # the engine is not here, so the page is only a page if it reaches
        # the shared bundle
        if f"{_FLAME_GRAPH_APP_DIR_NAME}/" not in page:
            self.fail(
                f"{_FLAME_GRAPH_VIEW_KEY}/index.html does not load the shared "
                f"{_FLAME_GRAPH_APP_DIR_NAME}/ bundle: {flame_dir}/index.html"
            )
        self.size_check(
            os.path.join(flame_dir, "output.txt"),
            _VALIDATE_FLAME_GRAPH_LOG_LEAST_BYTES,
            f"{_FLAME_GRAPH_VIEW_KEY}/output.txt",
        )
        script = self.size_check(
            os.path.join(flame_dir, "profile.js"),
            _VALIDATE_FLAME_GRAPH_SCRIPT_LEAST_BYTES,
            f"{_FLAME_GRAPH_VIEW_KEY}/profile.js",
        )
        if not script:
            return
        if "loadFileFromBase64" not in script:
            self.fail(
                f"{_FLAME_GRAPH_VIEW_KEY}/profile.js does not call"
                f" loadFileFromBase64: {flame_dir}/profile.js"
            )
        # the engine is shared at the report root, so a copy of it here is
        # the per-test duplication that sharing exists to remove
        for stray in sorted(os.listdir(flame_dir)):
            if stray not in _FLAME_GRAPH_PAGE_FILE_NAMES:
                self.fail(
                    f"{_FLAME_GRAPH_VIEW_KEY}/{stray} duplicates the shared "
                    f"{_FLAME_GRAPH_APP_DIR_NAME}/ bundle: {flame_dir}"
                )
        match = re.search(r'var document_base64 = "([A-Za-z0-9+/=]+)"', script)
        if not match:
            self.fail(
                f"{_FLAME_GRAPH_VIEW_KEY}/profile.js has no"
                f" document_base64 line: {flame_dir}/profile.js"
            )
            return
        try:
            document = json.loads(base64.b64decode(match.group(1)))
        except ValueError as error:
            self.fail(
                f"{_FLAME_GRAPH_VIEW_KEY}/profile.js document_base64 is not"
                f" JSON: {error}: {flame_dir}/profile.js"
            )
            return
        kinds = [
            profile.get("type") for profile in document.get("profiles", [])
        ]
        if document.get("exporter") != _FLAME_GRAPH_EXPORTER_NAME or kinds != [
            "evented"
        ]:
            self.fail(
                f"{_FLAME_GRAPH_VIEW_KEY}/profile.js does not hold one"
                f" recorded trace from {_FLAME_GRAPH_EXPORTER_NAME} (exporter"
                f" {document.get('exporter')!r}, "
                f"profiles {kinds}): {flame_dir}/profile.js"
            )

    # The heat map must be there, and must carry its own runtime script.
    def heat_map_check(self, out_dir: str, test_name: str) -> None:
        path = os.path.join(out_dir, _HEAT_MAP_VIEW_KEY, "index.html")
        text = self.page_check(
            path,
            f"{_HEAT_MAP_VIEW_KEY}/index.html",
            _VALIDATE_HEAT_MAP_PAGE_LEAST_BYTES,
            f"{test_name} / {_HEAT_MAP_VIEW_LABEL}",
        )
        if text and "report_ui.layout_activate" not in text:
            self.fail(
                f"{_HEAT_MAP_VIEW_KEY}/index.html is missing its runtime"
                f" script (no report_ui.layout_activate): {path}"
            )

    # Nothing anywhere may name the author's home directory -- a report gets
    # copied off this box. Bytes: the archives are not text.
    def home_dir_check(self, out_dir: str) -> None:
        home = os.path.expanduser("~")
        if home == "~":
            self.fail("no home directory to check the report against")
            return
        for root, _dirs, names in os.walk(out_dir):
            for name in names:
                path = os.path.join(root, name)
                with open(path, "rb") as handle:
                    data = handle.read()
                if home.encode("utf-8") in data:
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
        text = self.page_check(
            path, "index.html", _VALIDATE_OVERVIEW_PAGE_LEAST_BYTES, test_name
        )
        if not text:
            return
        if not re.search(layout.heading, text):
            self.fail(
                "index.html has no 'top N functions' section matching "
                f"{layout.heading!r}: {path}"
            )
        for key in layout.subpages:
            wanted = key != _FLAME_GRAPH_VIEW_KEY or has_rawdata
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

    # MANIFEST.txt line 1 must be exact and its checksum row must still
    # match the files beside it. Both failures name found and expected.
    def manifest_check(
        self, out_dir: str, layout: ValidateReport.ReportLayout
    ) -> None:
        path = os.path.join(out_dir, "MANIFEST.txt")
        text = self.size_check(
            path, _VALIDATE_MANIFEST_LEAST_BYTES, "MANIFEST.txt"
        )
        if not text:
            self.fail(
                "MANIFEST.txt is missing or unreadable, so this is not a"
                f" finished report; expected its first line to be"
                f" {layout.manifest_version!r}: {path}"
            )
            return
        first = text.split("\n", 1)[0]
        if first != layout.manifest_version:
            self.fail(
                f"MANIFEST.txt line 1 found {first!r}, expected the"
                f" version line {layout.manifest_version!r}: {path}"
            )
        for label in layout.manifest_labels:
            if not re.search(rf"^{label}=.+$", text, re.M):
                self.fail(
                    f"MANIFEST.txt has no '{label}=' header row, so a"
                    f" reader of this report cannot show it: {path}"
                )
        stamp = self.manifest_stamp_value(text)
        if not stamp.isdigit():
            self.fail(
                f"MANIFEST.txt stamp= row starts {stamp!r}, expected the"
                f" unix time: {path}"
            )
        recorded = self.manifest_value(text, _REPORT_MANIFEST_CHECKSUM_LABEL)
        if not recorded:
            self.fail(
                "MANIFEST.txt has no"
                f" '{_REPORT_MANIFEST_CHECKSUM_LABEL}=' row, so this"
                " report's files cannot be verified; expected one"
                f" beside the version line {layout.manifest_version!r}:"
                f" {path}"
            )
            return
        found = self.checksum_compute(out_dir)
        if found and found != recorded:
            self.fail(
                "this report does not match its recorded"
                f" {_REPORT_MANIFEST_CHECKSUM_LABEL}: found {found!r},"
                f" expected {recorded!r} -- a file was added, removed or"
                " edited"
                f" after the report was written: {out_dir}"
            )

    # The unix time out of a stamp= row, whose human tail nothing parses.
    def manifest_stamp_value(self, text: str) -> str:
        return self.manifest_value(text, "stamp").split(" ", 1)[0]

    # One LABEL= row out of a manifest's text.
    def manifest_value(self, text: str, label: str) -> str:
        match = re.search(rf"^{re.escape(label)}=(.*)$", text, re.M)
        return match.group(1).strip() if match else ""

    # One file out of an open archive, as text a scan can search.
    def member_text(
        self, archive: tarfile.TarFile, member: tarfile.TarInfo
    ) -> str:
        handle = archive.extractfile(member)
        if handle is None:
            raise ValueError(f"{member.name} in {archive.name} is not a file")
        return handle.read().decode("utf-8")

    # The overview page: its test-suites table, one link per test, its blocks.
    def overview_check(
        self,
        out_dir: str,
        tests: Sequence[str],
        layout: ValidateReport.ReportLayout,
    ) -> None:
        path = os.path.join(out_dir, "index.html")
        text = self.page_check(
            path, "index.html", _VALIDATE_OVERVIEW_PAGE_LEAST_BYTES, "overview"
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

    # Which tests this report holds, taken from the overview's own links. A
    # link to a directory that is not there is a broken test link.
    def overview_test_names(self, index_path: str, out_dir: str) -> list[str]:
        with open(index_path, encoding="utf-8") as handle:
            text = handle.read()
        names: list[str] = []
        for match in re.finditer(r'href="([\w.-]+)/index\.html"', text):
            test_name = match.group(1)
            if not os.path.isdir(os.path.join(out_dir, test_name)):
                self.fail(
                    f"overview index.html links {test_name}/index.html, and"
                    f" there is no {test_name}/ directory: {index_path}"
                )
                continue
            names.append(test_name)
        return names

    # Any page at all: big enough, titled, closed, no template leftovers.
    # Returns the page plus every asset it links, for a caller to grep.
    def page_check(
        self,
        path: str,
        label: str,
        min_bytes: int,
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
        # every page follows its own hrefs, not heat maps alone: a
        # misspelled assets/ link looks right until the browser opens it.
        return self.page_scripts(path, text)

    # Everything a page runs or styles itself with, inline or linked. Each
    # linked asset is read off disk, so a wrong relative href fails loudly.
    def page_scripts(self, path: str, text: str) -> str:
        parts = [text]
        page_dir = os.path.dirname(path)
        for href in re.findall(
            r'<(?:script[^>]*\ssrc|link[^>]*\shref)="([^"]+)"', text
        ):
            asset = os.path.join(page_dir, href)
            try:
                with open(asset, encoding="utf-8") as handle:
                    parts.append(handle.read())
            except OSError as error:
                self.fail(f"{path} links {href}, which is unreadable: {error}")
        return "\n".join(parts)

    # A page's title, which is how we tell an overview from a test page.
    # None when it has none, which run() stops on: no title, no layout.
    def page_title(self, index_path: str) -> str | None:
        with open(index_path, encoding="utf-8") as handle:
            match = re.search(r"<title>(.*?)</title>", handle.read())
        return match.group(1) if match else None

    # The perf log: a real timing line, and a section only where one exists.
    def perf_tool_check(self, out_dir: str, has_perf_log: bool) -> None:
        out_txt = os.path.join(out_dir, "perf-tool", "output.txt")
        text = self.size_check(
            out_txt, _VALIDATE_PERF_LOG_LEAST_BYTES, "perf-tool/output.txt"
        )
        if text and not re.search(r"^Time(/\w+)?:\s+\d", text, re.M):
            self.fail(
                "perf-tool/output.txt has no recognizable timing"
                f" line: {out_txt}"
            )
        index_text = self.size_check(
            os.path.join(out_dir, "index.html"),
            _VALIDATE_OVERVIEW_PAGE_LEAST_BYTES,
            "index.html",
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
        # bytes, never size_check's text: an archive is not utf-8
        size = os.path.getsize(path)
        if size < _VALIDATE_RAW_ARCHIVE_LEAST_BYTES:
            self.fail(
                f"raw/{name} suspiciously small ({size} bytes <"
                f" {_VALIDATE_RAW_ARCHIVE_LEAST_BYTES}): {path}"
            )
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
            and not inner.endswith(_DIFF_CALLER_COUNTS_FILE_SUFFIX)
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

    # Raw data is one tar.xz per test. A test storing nothing of its own
    # must have no raw/ at all, and nothing uncompressed may sit beside it.
    def raw_dir_check(self, out_dir: str, has_rawdata: bool) -> None:
        raw_dir = os.path.join(out_dir, "raw")
        if not has_rawdata:
            if os.path.exists(raw_dir):
                self.fail(
                    "raw/ in a test that records nothing of its own"
                    f": {raw_dir}"
                )
            return
        if not os.path.isdir(raw_dir):
            self.fail(f"no raw/ where a test records its own data: {raw_dir}")
            return
        names = sorted(os.listdir(raw_dir))
        archives = [
            name for name in names if name.endswith(_REPORT_RAW_ARCHIVE_SUFFIX)
        ]
        if not archives:
            self.fail(
                f"raw/ has no {_REPORT_RAW_ARCHIVE_SUFFIX} archive: {raw_dir}"
            )
        for name in names:
            if name not in archives:
                self.fail(
                    f"raw/{name} is not a {_REPORT_RAW_ARCHIVE_SUFFIX}"
                    " archive -- raw"
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
        if name is None:
            print(f"error: no <title> in {index_path}", file=sys.stderr)
            return 1
        layout = _LAYOUT_DIFF if args.diff else _LAYOUT_FULL

        self.home_dir_check(out_dir)
        self.manifest_check(out_dir, layout)
        if name == "overview":
            tests = self.overview_test_names(index_path, out_dir)
            self.overview_check(out_dir, tests, layout)
            if _FLAME_GRAPH_VIEW_KEY in layout.subpages:
                self.flame_app_check(out_dir)
            self.sources_check(out_dir, tests)
            for test_name in tests:
                self.test_report_check(
                    os.path.join(out_dir, test_name), test_name, layout
                )
        else:
            self.test_report_check(out_dir, name, layout)

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

    # Read a text file, complaining if it is missing or implausibly small.
    def size_check(self, path: str, min_bytes: int, label: str) -> str:
        try:
            size = os.path.getsize(path)
            with open(path, encoding="utf-8") as handle:
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

    # Every heat map's source text sits in the report's one sources/
    # directory. Confirm.
    def sources_check(self, out_dir: str, tests: Sequence[str]) -> None:
        sources_dir = os.path.join(out_dir, _REPORT_SOURCES_DIR_NAME)
        linked = False
        for test_name in tests:
            path = os.path.join(
                out_dir, test_name, _HEAT_MAP_VIEW_KEY, "index.html"
            )
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as handle:
                if f"/{_REPORT_SOURCES_DIR_NAME}/" in handle.read():
                    linked = True
                    break
        if linked and not os.path.isdir(sources_dir):
            self.fail(f"no shared source directory: {sources_dir}")

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
        if _FLAME_GRAPH_VIEW_KEY in layout.subpages:
            self.flame_graph_check(out_dir, has_rawdata)
        if layout.test_has_rawdata:
            self.perf_tool_check(out_dir, has_rawdata)


# What each view's directory is called, from the entry production builds
# with. Element 0 is the key: the URL hash's name and the page's directory.
_FLAME_GRAPH_VIEW_KEY = _FLAME_GRAPH_VIEW_ENTRY[0]

# The heat map's key and link label, element 1 of the same entry. Checking
# the title against it is what keeps this a check, not a second spelling.
_HEAT_MAP_VIEW_KEY = _HEAT_MAP_VIEW_ENTRY[0]
_HEAT_MAP_VIEW_LABEL = _HEAT_MAP_VIEW_ENTRY[1]

# What a perf2html_diff.sh report must contain: no flame graph, no timing.
# The version line comes from settings.py, so this checks what wrote it.
_LAYOUT_DIFF = ValidateReport.ReportLayout(
    subpages=(_HEAT_MAP_VIEW_KEY,),
    heading=r"<h2>top \d+ functions by change in self</h2>",
    header_blocks=("baseline", "modified"),
    manifest_version=_REPORT_MANIFEST_VERSION_DIFF,
    manifest_labels=("baseline", "modified", "stamp"),
    test_has_rawdata=False,
    all_has_archive=True,
)

# What a perf2html.sh report must contain.
_LAYOUT_FULL = ValidateReport.ReportLayout(
    subpages=(_FLAME_GRAPH_VIEW_KEY, _HEAT_MAP_VIEW_KEY),
    heading=r"<h2>top \d+ functions by self</h2>",
    header_blocks=(),
    manifest_version=_REPORT_MANIFEST_VERSION_FULL,
    manifest_labels=(
        "sampled",
        "revision",
        "cpu",
        "build",
        "executable",
        "stamp",
    ),
    test_has_rawdata=True,
    all_has_archive=False,
)

# The POSIX pipeline this file re-derives the checksum row with, spelled
# out separately from shared.sh's on purpose. See DECLAUDE.md: not a twin.
_REPORT_CHECKSUM_COMMAND = (
    "find . -type f ! -name MANIFEST.txt -print"
    " | LC_ALL=C sort | LC_ALL=C tr '\\n' '\\0'"
    " | xargs -0 -r cksum --"
    " | LC_ALL=C sort | cksum"
)

# Smallest a file can be before it is plainly a failed generate. The flame
# graph page is a loader and the logs are appended text, so each has its own.
_VALIDATE_FLAME_GRAPH_LOG_LEAST_BYTES = 20
_VALIDATE_FLAME_GRAPH_PAGE_LEAST_BYTES = 300
_VALIDATE_FLAME_GRAPH_SCRIPT_LEAST_BYTES = 200
_VALIDATE_HEAT_MAP_PAGE_LEAST_BYTES = 5000
_VALIDATE_MANIFEST_LEAST_BYTES = 40
_VALIDATE_OVERVIEW_PAGE_LEAST_BYTES = 2000
_VALIDATE_PERF_LOG_LEAST_BYTES = 20
_VALIDATE_RAW_ARCHIVE_LEAST_BYTES = 100


# main - Check one report. Source is source_scan.py's, never this file's.
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
    return validator.run(
        ValidateReport.ValidateArgs(
            out_dir=namespace.out_dir, diff=namespace.diff
        )
    )


if __name__ == "__main__":
    sys.exit(main())
