#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import argparse, base64, glob, html, json, os, re, subprocess, sys, tarfile
from collections.abc import Sequence
from typing import Any, NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind, settings

_CALLGRIND_OUTPUT_FILE_PREFIX: str = ""
_FLAME_GRAPH_APP_DIR_NAME: str = ""
_FLAME_GRAPH_APP_FILE_GLOBS: tuple[str, ...] = ()
_FLAME_GRAPH_EXPORTER_NAME: str = ""
_FLAME_GRAPH_PROFILE_DIR_NAME: str = ""
_FLAME_GRAPH_PROFILE_GLOBAL_NAME: str = ""
_FLAME_GRAPH_VIEW_ENTRY: tuple[str, str] = ("", "")
_HEAT_MAP_MODEL_DIR_NAME: str = ""
_HEAT_MAP_MODEL_GLOBAL_NAME: str = ""
_HEAT_MAP_VIEW_ENTRY: tuple[str, str] = ("", "")
_REPORT_MANIFEST_CHECKSUM_LABEL: str = ""
_REPORT_MANIFEST_VERSION_DIFF: str = ""
_REPORT_MANIFEST_VERSION_FULL: str = ""
_REPORT_RAW_ARCHIVE_SUFFIX: str = ""
_REPORT_SOURCES_DIR_NAME: str = ""
_TIMER_ARTIFACTS_NAME_PREFIX: str = ""
settings.load_into(__name__)


class TestReport:
    class ReportLayout(NamedTuple):
        has_flame_graph: bool
        table_diff_value: str
        header_blocks: tuple[str, ...]
        manifest_version: str
        manifest_labels: tuple[str, ...]
        manifest_recorded_labels: tuple[str, ...]
        test_records_runs: bool
        has_timer_artifacts: bool
        has_baselines: bool

    class TestArgs(NamedTuple):
        out_dir: str
        diff: bool
        verbose: bool

    def __init__(self) -> None:
        self.errors: list[str] = []

    def anchor_hrefs(self, page_text: str) -> list[str]:
        return [
            html.unescape(href)
            for href in re.findall(r'<a\s[^>]*href="([^"]*)"', page_text)
        ]

    def callers_page_check(
        self,
        out_dir: str,
        test_name: str,
        layout: TestReport.ReportLayout,
    ) -> None:
        label = self.callers_page_path_of(test_name)
        path = os.path.join(out_dir, label)
        text = self.page_check(
            path, label, _TEST_OVERVIEW_PAGE_LEAST_BYTES, test_name
        )
        if not text:
            return
        with open(path, encoding="utf-8") as handle:
            page_text = handle.read()
        rows = self.callers_table_check(path, label, page_text, layout)
        if '<nav id="menu-"' in page_text:
            self.fail(f"{label} draws the overview's menu: {path}")
        page_hrefs = self.table_data_hrefs(rows)
        address_start = f"#test={test_name}&view="
        for href in page_hrefs:
            if not href.startswith(address_start):
                self.fail(
                    f"{label} links {href!r}, which is no address of"
                    f" {test_name} ({address_start}...): {path}"
                )
        function_start = (
            f"#test={test_name}&view={_HEAT_MAP_VIEW_KEY}&function="
        )
        if not any(href.startswith(function_start) for href in page_hrefs):
            self.fail(
                f"{label} links no function into the heat map"
                f" ({function_start}...): {path}"
            )
        if "<details" in page_text:
            self.fail(
                f"{label} holds a log section, which the overview holds:"
                f" {path}"
            )
        if _TEST_OVERVIEW_RAW_DATA_MARKUP in page_text:
            self.fail(
                f"{label} has a 'raw data' section, but it should not: {path}"
            )

    # Answers the report relative path of a test's callers page.
    def callers_page_path_of(self, test_name: str) -> str:
        return f"{_TEST_CALLERS_PAGE_DIR_NAME}/{test_name}.html"

    # Checks the callers table data the page script draws, answering its rows.
    def callers_table_check(
        self,
        path: str,
        label: str,
        page_text: str,
        layout: TestReport.ReportLayout,
    ) -> list[list[Any]]:
        attributes = self.element_attributes(
            page_text, _TEST_CALLERS_TABLE_DATA_ID
        )
        if attributes is None:
            self.fail(
                f"{label} has no {_TEST_CALLERS_TABLE_DATA_ID} table data:"
                f" {path}"
            )
            return []
        if attributes.get("data-diff-") != layout.table_diff_value:
            self.fail(
                f"{label}'s table data holds data-diff-"
                f" {attributes.get('data-diff-')!r}, expected"
                f" {layout.table_diff_value!r}: {path}"
            )
        if attributes.get("data-key-") != _TEST_CALLERS_TABLE_KEY:
            self.fail(
                f"{label}'s table data holds data-key-"
                f" {attributes.get('data-key-')!r}, expected"
                f" {_TEST_CALLERS_TABLE_KEY!r}: {path}"
            )
        rows = self.table_data_rows(attributes, label, path)
        for row in rows:
            if len(row) != _TEST_CALLERS_TABLE_CELLS:
                self.fail(
                    f"{label}'s table data has a row of {len(row)} cells,"
                    f" expected {_TEST_CALLERS_TABLE_CELLS}: {path}"
                )
                return []
        return rows

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
        return done.stdout.split(" ", 1)[0]

    def diff_baseline_check(self, filed_model: Any, label: str) -> None:
        width = len(filed_model["heatMapTotals"]["counters"])
        changes: list[tuple[str, list[int], list[int]]] = []
        for path, entry in filed_model["files"].items():
            file_baseline = filed_model["fileBaseline"].get(path, [])
            changes.append((path, entry["self"], file_baseline))
            for line, row in entry["lines"].items():
                line_baseline = entry["baseline"].get(line, [])
                changes.append((f"{path}:{line}", row[0], line_baseline))
        for function, function_baseline in zip(
            filed_model["functions"],
            filed_model["functionBaseline"],
            strict=True,
        ):
            changes.append(
                (function["name"], function["self"], function_baseline)
            )
        for place, change, baseline in changes:
            for slot in range(width):
                moved = change[slot] if slot < len(change) else 0
                count = baseline[slot] if slot < len(baseline) else 0
                if moved < -count:
                    self.fail(
                        f"{label}: {place} falls {moved} past its baseline"
                        f" of {count} in counter slot {slot}"
                    )
                    return

    # Answers the attributes of the div the id names, none when no div has it.
    def element_attributes(
        self, page_text: str, element_id: str
    ) -> dict[str, str] | None:
        match = re.search(
            rf'<div id="{re.escape(element_id)}"([^>]*)>', page_text
        )
        if match is None:
            return None
        return {
            name: html.unescape(value)
            for name, value in re.findall(
                r'\s([\w-]+)="([^"]*)"', match.group(1)
            )
        }

    def fail(self, message: str) -> None:
        self.errors.append(message)

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

    def flame_graph_check(
        self,
        out_dir: str,
        traced_tests: Sequence[str],
        layout: TestReport.ReportLayout,
    ) -> None:
        flame_dir = os.path.join(out_dir, _FLAME_GRAPH_VIEW_KEY)
        if not layout.has_flame_graph:
            if os.path.exists(flame_dir):
                self.fail(
                    f"{_FLAME_GRAPH_VIEW_KEY}/ in a report that records no"
                    f" trace: {flame_dir}"
                )
            return
        if not os.path.isdir(flame_dir):
            self.fail(f"no {_FLAME_GRAPH_VIEW_KEY}/ directory: {flame_dir}")
            return
        page = self.page_check(
            os.path.join(flame_dir, "index.html"),
            f"{_FLAME_GRAPH_VIEW_KEY}/index.html",
            _TEST_FLAME_GRAPH_PAGE_LEAST_BYTES,
        )
        if page and f"{_FLAME_GRAPH_APP_DIR_NAME}/" not in page:
            self.fail(
                f"{_FLAME_GRAPH_VIEW_KEY}/index.html does not load the shared "
                f"{_FLAME_GRAPH_APP_DIR_NAME}/ bundle: {flame_dir}/index.html"
            )
        if page and "loadFileFromBase64" not in page:
            self.fail(
                f"{_FLAME_GRAPH_VIEW_KEY}/index.html and its scripts never"
                f" call loadFileFromBase64: {flame_dir}/index.html"
            )
        found_names = sorted(os.listdir(flame_dir))
        wanted_names = sorted(("index.html", _FLAME_GRAPH_PROFILE_DIR_NAME))
        if found_names != wanted_names:
            self.fail(
                f"{_FLAME_GRAPH_VIEW_KEY}/ holds {found_names}, expected"
                f" {wanted_names}: {flame_dir}"
            )
            return
        profile_dir = os.path.join(flame_dir, _FLAME_GRAPH_PROFILE_DIR_NAME)
        found_names = sorted(os.listdir(profile_dir))
        wanted_names = sorted(f"{test_name}.js" for test_name in traced_tests)
        if found_names != wanted_names:
            self.fail(
                f"{_FLAME_GRAPH_PROFILE_DIR_NAME}/ holds {found_names},"
                f" expected one script per traced test {wanted_names}:"
                f" {profile_dir}"
            )
        for test_name in traced_tests:
            self.flame_graph_profile_check(profile_dir, test_name)

    def flame_graph_profile_check(
        self, profile_dir: str, test_name: str
    ) -> None:
        path = os.path.join(profile_dir, f"{test_name}.js")
        label = f"{_FLAME_GRAPH_PROFILE_DIR_NAME}/{test_name}.js"
        script = self.size_check(
            path, _TEST_FLAME_GRAPH_SCRIPT_LEAST_BYTES, label
        )
        if not script:
            return
        filed_profile = self.script_value(
            script, _FLAME_GRAPH_PROFILE_GLOBAL_NAME, test_name, path
        )
        if filed_profile is None:
            return
        encoded_profile = filed_profile.get("base64")
        base64_text = (
            encoded_profile if isinstance(encoded_profile, str) else ""
        )
        if not re.fullmatch(r"[A-Za-z0-9+/=]+", base64_text):
            self.fail(f"{label} files no base64 profile: {path}")
            return
        try:
            document = json.loads(base64.b64decode(base64_text))
        except ValueError as error:
            self.fail(f"{label} base64 is not JSON: {error}: {path}")
            return
        kinds = [
            profile.get("type") for profile in document.get("profiles", [])
        ]
        if document.get("exporter") != _FLAME_GRAPH_EXPORTER_NAME or kinds != [
            "evented"
        ]:
            self.fail(
                f"{label} does not hold one recorded trace from"
                f" {_FLAME_GRAPH_EXPORTER_NAME} (exporter"
                f" {document.get('exporter')!r}, profiles {kinds}): {path}"
            )

    def heat_map_check(
        self,
        out_dir: str,
        tests: Sequence[str],
        layout: TestReport.ReportLayout,
    ) -> None:
        heat_map_dir = os.path.join(out_dir, _HEAT_MAP_VIEW_KEY)
        path = os.path.join(heat_map_dir, "index.html")
        text = self.page_check(
            path,
            f"{_HEAT_MAP_VIEW_KEY}/index.html",
            _TEST_HEAT_MAP_PAGE_LEAST_BYTES,
            _HEAT_MAP_PAGE_TITLE,
        )
        if text and "report_ui_.layout_activate" not in text:
            self.fail(
                f"{_HEAT_MAP_VIEW_KEY}/index.html is missing its runtime"
                f" script (no report_ui_.layout_activate): {path}"
            )
        model_dir = os.path.join(heat_map_dir, _HEAT_MAP_MODEL_DIR_NAME)
        if not os.path.isdir(model_dir):
            self.fail(f"no heat map model scripts: {model_dir}")
            return
        found_names = sorted(os.listdir(model_dir))
        wanted_names = sorted(f"{test_name}.js" for test_name in tests)
        if found_names != wanted_names:
            self.fail(
                f"{_HEAT_MAP_MODEL_DIR_NAME}/ holds {found_names}, expected"
                f" one script per test {wanted_names}: {model_dir}"
            )
        for test_name in tests:
            script_path = os.path.join(model_dir, f"{test_name}.js")
            script = self.size_check(
                script_path,
                _TEST_HEAT_MAP_MODEL_LEAST_BYTES,
                f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js",
            )
            if not script:
                continue
            filed_model = self.script_value(
                script, _HEAT_MAP_MODEL_GLOBAL_NAME, test_name, script_path
            )
            if filed_model is None:
                continue
            if (
                not {"heatMapTotals", "files", "functions"}
                <= filed_model.keys()
            ):
                self.fail(
                    f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js files a"
                    f" model lacking heatMapTotals, files or functions:"
                    f" {script_path}"
                )
                continue
            if layout.has_baselines:
                self.diff_baseline_check(
                    filed_model, f"{_HEAT_MAP_MODEL_DIR_NAME}/{test_name}.js"
                )

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

    def manifest_check(
        self, out_dir: str, layout: TestReport.ReportLayout
    ) -> None:
        path = os.path.join(out_dir, "MANIFEST.txt")
        text = self.size_check(
            path, _TEST_MANIFEST_LEAST_BYTES, "MANIFEST.txt"
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
        for label in layout.manifest_recorded_labels:
            recorded_unix = self.manifest_recorded_value(text, label)
            if not recorded_unix.isdigit():
                self.fail(
                    f"MANIFEST.txt {label}= row starts {recorded_unix!r},"
                    f" expected the unix time: {path}"
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

    def manifest_recorded_value(self, text: str, label: str) -> str:
        return self.manifest_value(text, label).split(" ", 1)[0]

    def manifest_value(self, text: str, label: str) -> str:
        match = re.search(rf"^{re.escape(label)}=(.*)$", text, re.M)
        return match.group(1).strip() if match else ""

    def member_text(
        self, archive: tarfile.TarFile, member: tarfile.TarInfo
    ) -> str:
        handle = archive.extractfile(member)
        if handle is None:
            raise ValueError(f"{member.name} in {archive.name} is not a file")
        return handle.read().decode("utf-8")

    def menu_check(
        self,
        path: str,
        page_text: str,
        tests: Sequence[str],
        layout: TestReport.ReportLayout,
    ) -> None:
        match = re.search(
            r'<nav id="menu-" class="menu-strip-"([^>]*)></nav>', page_text
        )
        if not match:
            self.fail(f"overview index.html has no empty menu strip: {path}")
            return
        found = {
            name: html.unescape(value)
            for name, value in re.findall(
                r'\s(data-[\w-]+)="([^"]*)"', match.group(1)
            )
        }
        wanted = {
            "data-flame-graph-": "1" if layout.has_flame_graph else "0",
            "data-help-href-": "README.md",
            "data-test-names-": json.dumps(list(tests), ensure_ascii=False),
        }
        if found != wanted:
            self.fail(
                f"overview index.html menu strip attributes are {found},"
                f" expected {wanted}: {path}"
            )

    def overview_check(
        self,
        out_dir: str,
        tests: Sequence[str],
        layout: TestReport.ReportLayout,
    ) -> None:
        path = os.path.join(out_dir, "index.html")
        text = self.page_check(
            path,
            "index.html",
            _TEST_OVERVIEW_PAGE_LEAST_BYTES,
            _TEST_OVERVIEW_PAGE_TITLE,
        )
        if not text:
            return
        with open(path, encoding="utf-8") as handle:
            page_text = handle.read()
        if _TEST_OVERVIEW_TESTS_HEADING_MARKUP not in page_text:
            self.fail(f"overview index.html has no 'tests' section: {path}")
        tests_attributes = self.element_attributes(
            page_text, _TEST_OVERVIEW_TESTS_TABLE_DATA_ID
        )
        if (
            tests_attributes is not None
            and tests_attributes.get("data-diff-") != layout.table_diff_value
        ):
            self.fail(
                "overview index.html's tests table data holds data-diff-"
                f" {tests_attributes.get('data-diff-')!r}, expected"
                f" {layout.table_diff_value!r}: {path}"
            )
        page_hrefs = self.overview_tests_hrefs(page_text, path)
        for test_name in tests:
            if (
                f"#test={test_name}&view={_HEAT_MAP_VIEW_KEY}"
                not in page_hrefs
            ):
                self.fail(
                    "overview index.html is missing its"
                    f" {test_name} heat map link: {path}"
                )
        self.menu_check(path, page_text, tests, layout)
        self.logs_check(path, page_text, layout.test_records_runs)
        for heading in layout.header_blocks:
            if heading not in page_text:
                self.fail(
                    "overview index.html has no header block heading"
                    f" {heading!r}: {path}"
                )
        self.timer_artifacts_check(out_dir, page_text, tests, layout)

    def overview_test_names(self, index_path: str, out_dir: str) -> list[str]:
        with open(index_path, encoding="utf-8") as handle:
            text = handle.read()
        names: list[str] = []
        linked_names: set[str] = set()
        for href in self.overview_tests_hrefs(text, index_path):
            match = re.fullmatch(
                rf"#test=([\w.-]+)&view={re.escape(_HEAT_MAP_VIEW_KEY)}", href
            )
            if not match or match.group(1) in linked_names:
                continue
            test_name = match.group(1)
            linked_names.add(test_name)
            callers_page_path = self.callers_page_path_of(test_name)
            if not os.path.isfile(os.path.join(out_dir, callers_page_path)):
                self.fail(
                    f"overview index.html links {href}, and there is no"
                    f" {callers_page_path}: {index_path}"
                )
                continue
            names.append(test_name)
        return names

    # Answers every address the overview's tests table data links.
    def overview_tests_hrefs(self, page_text: str, path: str) -> list[str]:
        attributes = self.element_attributes(
            page_text, _TEST_OVERVIEW_TESTS_TABLE_DATA_ID
        )
        if attributes is None:
            self.fail(
                "overview index.html has no"
                f" {_TEST_OVERVIEW_TESTS_TABLE_DATA_ID} table data: {path}"
            )
            return []
        return self.table_data_hrefs(
            self.table_data_rows(attributes, "overview index.html", path)
        )

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
            "Traceback (most recent call last)",
            "NaN%",
        ):
            if marker in text:
                self.fail(
                    f"{label} contains a leftover template/error marker "
                    f"{marker!r}: {path}"
                )
        return self.page_scripts(path, text)

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

    def page_title(self, index_path: str) -> str | None:
        with open(index_path, encoding="utf-8") as handle:
            match = re.search(r"<title>(.*?)</title>", handle.read())
        return match.group(1) if match else None

    # Checks the overview's log sections, which a report recording runs has.
    def logs_check(self, path: str, page_text: str, has_logs: bool) -> None:
        for title, section_id in _TEST_OVERVIEW_LOG_SECTIONS:
            if has_logs != (f'<details id="{section_id}"' in page_text):
                lack = "has no" if has_logs else "should not have a"
                self.fail(
                    f"overview index.html {lack} '{title}' section: {path}"
                )
        if has_logs and not re.search(r"^Time(/\w+)?:\s+\d", page_text, re.M):
            self.fail(
                "overview index.html's 'perf log' section has no"
                f" recognizable timing line: {path}"
            )

    def run(self, args: TestReport.TestArgs) -> int:
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
        if name != _TEST_OVERVIEW_PAGE_TITLE:
            print(
                f"error: <title> {name!r}, expected"
                f" {_TEST_OVERVIEW_PAGE_TITLE!r}: {index_path}",
                file=sys.stderr,
            )
            return 1
        layout = _LAYOUT_DIFF if args.diff else _LAYOUT_FULL

        self.home_dir_check(out_dir)
        self.manifest_check(out_dir, layout)
        tests = self.overview_test_names(index_path, out_dir)
        self.overview_check(out_dir, tests, layout)
        if layout.has_flame_graph:
            self.flame_app_check(out_dir)
        self.sources_check(out_dir)
        self.heat_map_check(out_dir, tests, layout)
        traced_tests = [
            test_name
            for test_name in tests
            if self.runs_recorded(layout, test_name)
        ]
        self.flame_graph_check(out_dir, traced_tests, layout)
        for test_name in tests:
            self.test_report_check(out_dir, test_name, layout)

        if self.errors:
            print(
                f"test_report: {len(self.errors)} problem(s) in {out_dir}:",
                file=sys.stderr,
            )
            for error in self.errors:
                print(f"  - {error}", file=sys.stderr)
            return 1
        if args.verbose:
            print(f"test_report: ok ({out_dir})")
        return 0

    def runs_recorded(
        self, layout: TestReport.ReportLayout, test_name: str
    ) -> bool:
        return layout.test_records_runs and test_name != "all"

    def script_value(
        self, script: str, global_name: str, test_name: str, path: str
    ) -> dict[str, object] | None:
        assignment_prefix = f'window.{global_name}["{test_name}"] = '
        for line in script.splitlines():
            if not line.startswith(assignment_prefix):
                continue
            try:
                filed_value = json.loads(
                    line.removeprefix(assignment_prefix).rstrip(";")
                )
            except ValueError as error:
                self.fail(
                    f"{assignment_prefix!r} holds no JSON: {error}: {path}"
                )
                return None
            if not isinstance(filed_value, dict):
                self.fail(
                    f"{assignment_prefix!r} holds no JSON object: {path}"
                )
                return None
            return filed_value
        self.fail(f"no {assignment_prefix!r} line: {path}")
        return None

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

    def sources_check(self, out_dir: str) -> None:
        sources_dir = os.path.join(out_dir, _REPORT_SOURCES_DIR_NAME)
        path = os.path.join(out_dir, _HEAT_MAP_VIEW_KEY, "index.html")
        if not os.path.isfile(path):
            return
        with open(path, encoding="utf-8") as handle:
            linked = f"/{_REPORT_SOURCES_DIR_NAME}/" in handle.read()
        if linked and not os.path.isdir(sources_dir):
            self.fail(f"no shared source directory: {sources_dir}")

    # Answers every address a table data's cells link, plain or in markup.
    def table_data_hrefs(self, rows: Sequence[Sequence[Any]]) -> list[str]:
        hrefs: list[str] = []
        for row in rows:
            for cell in row:
                if not isinstance(cell, dict):
                    continue
                if "href" in cell:
                    hrefs.append(str(cell["href"]))
                if "html" in cell:
                    hrefs += self.anchor_hrefs(str(cell["html"]))
        return hrefs

    # Answers the rows a table data element files, each a list of cells.
    def table_data_rows(
        self, attributes: dict[str, str], label: str, path: str
    ) -> list[list[Any]]:
        if "data-rows-" not in attributes:
            self.fail(f"{label}'s table data holds no data-rows-: {path}")
            return []
        try:
            rows = json.loads(attributes["data-rows-"])
        except ValueError as error:
            self.fail(f"{label}'s table data holds no JSON: {error}: {path}")
            return []
        if not isinstance(rows, list) or not all(
            isinstance(row, list) for row in rows
        ):
            self.fail(f"{label}'s table data holds no list of rows: {path}")
            return []
        return rows

    def test_report_check(
        self, out_dir: str, name: str, layout: TestReport.ReportLayout
    ) -> None:
        self.callers_page_check(out_dir, name, layout)
        stray_dir = os.path.join(out_dir, name)
        if os.path.exists(stray_dir):
            self.fail(
                f"{name}/ at the report top, which no report keeps:"
                f" {stray_dir}"
            )

    def timer_artifacts_archive_check(
        self,
        path: str,
        archive_name: str,
        tests: Sequence[str],
        layout: TestReport.ReportLayout,
    ) -> None:
        size = os.path.getsize(path)
        if size < _TEST_RAW_ARCHIVE_LEAST_BYTES:
            self.fail(
                f"{archive_name} suspiciously small ({size} bytes <"
                f" {_TEST_RAW_ARCHIVE_LEAST_BYTES}): {path}"
            )
        root_name = archive_name.removesuffix(_REPORT_RAW_ARCHIVE_SUFFIX)
        try:
            with tarfile.open(path, "r:xz") as archive:
                archive_members = archive.getmembers()
                texts = {
                    member.name: self.member_text(archive, member)
                    for member in archive_members
                    if member.isfile()
                }
        except (OSError, tarfile.TarError) as error:
            self.fail(
                f"{archive_name} is not readable as tar.xz: {path}: {error}"
            )
            return
        if not any(
            member.isdir() and member.name == root_name
            for member in archive_members
        ):
            self.fail(f"{archive_name} has no {root_name}/ root entry: {path}")
        for member in archive_members:
            if member.name == root_name or (
                member.isfile() and os.path.dirname(member.name) == root_name
            ):
                continue
            self.fail(
                f"{archive_name} holds {member.name!r}, which is no file"
                f" right under {root_name}/: {path}"
            )
        texts_by_name = {
            os.path.basename(member_name): text
            for member_name, text in texts.items()
        }
        for test_name in tests:
            if not self.runs_recorded(layout, test_name):
                continue
            if not any(
                file_name == f"{_CALLGRIND_OUTPUT_FILE_PREFIX}.{test_name}"
                and "events:" in text[:4096]
                for file_name, text in texts_by_name.items()
            ):
                self.fail(
                    f"{archive_name} holds no callgrind file of {test_name}"
                    f" with an 'events:' line near its top: {path}"
                )
        for member_name, text in texts.items():
            if callgrind.REPO_ROOT in text:
                self.fail(
                    f"{archive_name} still contains the absolute repo root "
                    f"{callgrind.REPO_ROOT!r} in {member_name}: {path}"
                )

    def timer_artifacts_check(
        self,
        out_dir: str,
        overview_text: str,
        tests: Sequence[str],
        layout: TestReport.ReportLayout,
    ) -> None:
        archive_pattern = (
            f"{_TIMER_ARTIFACTS_NAME_PREFIX}*{_REPORT_RAW_ARCHIVE_SUFFIX}"
        )
        archive_names = sorted(
            os.path.basename(path)
            for path in glob.glob(os.path.join(out_dir, archive_pattern))
        )
        wanted_count = 1 if layout.has_timer_artifacts else 0
        if len(archive_names) != wanted_count:
            self.fail(
                f"{len(archive_names)} {archive_pattern} at the report's top,"
                f" expected {wanted_count}: {out_dir}"
            )
        has_raw_data_line = _TEST_OVERVIEW_RAW_DATA_MARKUP in overview_text
        if layout.has_timer_artifacts and not has_raw_data_line:
            self.fail(f"overview index.html has no 'raw data' line: {out_dir}")
        elif has_raw_data_line and not layout.has_timer_artifacts:
            self.fail(
                "overview index.html has a 'raw data' line, but it should"
                f" not: {out_dir}"
            )
        for archive_name in archive_names:
            if f'href="{archive_name}"' not in overview_text:
                self.fail(
                    f"overview index.html does not link {archive_name}:"
                    f" {out_dir}"
                )
            self.timer_artifacts_archive_check(
                os.path.join(out_dir, archive_name),
                archive_name,
                tests,
                layout,
            )


_FLAME_GRAPH_VIEW_KEY = _FLAME_GRAPH_VIEW_ENTRY[0]

_HEAT_MAP_VIEW_KEY = _HEAT_MAP_VIEW_ENTRY[0]
_HEAT_MAP_PAGE_TITLE = ""

_LAYOUT_DIFF = TestReport.ReportLayout(
    has_flame_graph=False,
    table_diff_value="1",
    header_blocks=(
        '<div class="page-heading-">baseline</div>',
        '<div class="page-heading-">modified</div>',
    ),
    manifest_version=_REPORT_MANIFEST_VERSION_DIFF,
    manifest_labels=(
        "baseline",
        "modified",
        "baseline_recorded",
        "modified_recorded",
    ),
    manifest_recorded_labels=("baseline_recorded", "modified_recorded"),
    test_records_runs=False,
    has_timer_artifacts=False,
    has_baselines=True,
)

_LAYOUT_FULL = TestReport.ReportLayout(
    has_flame_graph=True,
    table_diff_value="0",
    header_blocks=(
        '<div id="overview-manifest-heading-" class="page-heading-"></div>',
    ),
    manifest_version=_REPORT_MANIFEST_VERSION_FULL,
    manifest_labels=(
        "revision",
        "cpu",
        "build",
        "executable",
        "recorded",
    ),
    manifest_recorded_labels=("recorded",),
    test_records_runs=True,
    has_timer_artifacts=True,
    has_baselines=False,
)

_REPORT_CHECKSUM_COMMAND = (
    "find . -type f ! -name MANIFEST.txt -print"
    " | LC_ALL=C sort | LC_ALL=C tr '\\n' '\\0'"
    " | xargs -0 -r cksum --"
    " | LC_ALL=C sort | cksum"
)

_TEST_CALLERS_PAGE_DIR_NAME = "callers"
_TEST_CALLERS_TABLE_CELLS = 4
_TEST_CALLERS_TABLE_DATA_ID = "callers-functions-table-"
_TEST_CALLERS_TABLE_KEY = "report.functions"
_TEST_FLAME_GRAPH_PAGE_LEAST_BYTES = 300
_TEST_FLAME_GRAPH_SCRIPT_LEAST_BYTES = 200
_TEST_HEAT_MAP_MODEL_LEAST_BYTES = 5000
_TEST_HEAT_MAP_PAGE_LEAST_BYTES = 1000
_TEST_MANIFEST_LEAST_BYTES = 40
_TEST_OVERVIEW_LOG_SECTIONS = (
    ("perf log", "overview-collapsed-section-perf-log-"),
    ("trace log", "overview-collapsed-section-trace-log-"),
    ("valgrind log", "overview-collapsed-section-valgrind-log-"),
)
_TEST_OVERVIEW_PAGE_LEAST_BYTES = 2000
_TEST_OVERVIEW_PAGE_TITLE = ""
_TEST_OVERVIEW_RAW_DATA_MARKUP = '<div id="overview-raw-data-">'
_TEST_OVERVIEW_TESTS_HEADING_MARKUP = (
    '<div id="overview-tests-heading-" class="page-heading-"></div>'
)
_TEST_OVERVIEW_TESTS_TABLE_DATA_ID = "overview-tests-table-"
_TEST_RAW_ARCHIVE_LEAST_BYTES = 100


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir", help="a report directory")
    parser.add_argument(
        "--diff",
        action="store_true",
        help="a perf2html_diff.sh report: heat map only",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print the ok line; a quiet run prints nothing on success",
    )
    namespace = parser.parse_args()
    checker = TestReport()
    return checker.run(
        TestReport.TestArgs(
            out_dir=namespace.out_dir,
            diff=namespace.diff,
            verbose=namespace.verbose,
        )
    )


if __name__ == "__main__":
    sys.exit(main())
