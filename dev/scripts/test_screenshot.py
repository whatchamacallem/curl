#!/usr/bin/env python3
# `dev/scripts/test_screenshot.py REPORT PREFIX [--out=DIR]` shoots a report.
#
# One PNG per entry in `_VIEWS` per viewport in `_SCREENSHOT_VIEWPORTS` per
# dark mode value, each hash naming a view the report renders a different
# way. The list is of views, not of data: two hashes differing only in which
# test they name are one view and one shot. The viewports are there to be
# compared: a page is designed once and fitted to the window, so one view's
# shots in one dark mode differ in size and in nothing else.
#
# Each hash is a golden bookmark, a string literal written out whole and
# formulated from nothing: changing the url format must require changing
# those string literals. A diff report has no flame graph, so that view is
# shot for a full report only, the kind of report read from its MANIFEST.txt
# line 1.
#
# A view lacking files (a report whose run stopped short) is shot from a
# copy of the report under dev/build/, removed once shot: verification
# never changes the report it checks.
#
# Nothing here is a setting: `test_expected_behavior.sh` is the only caller,
# no report carries a shot, and a browser a page never sees is not the
# pages' to read.
from __future__ import annotations

import argparse, math, os, shutil, subprocess, sys, urllib.parse

import PIL.Image

_ENTRY_PAGE = "index.html"

_FAULT_TAIL_CHARS = 400

_IMAGE_SUFFIX = ".png"

_REPORT_COMPLETE_ASSET: tuple[str, ...] = ("assets/report_complete.js",)

_REPORT_MANIFEST_NAME = "MANIFEST.txt"
_REPORT_MANIFEST_VERSION_DIFF = "curl/perf2html_diff.sh v1"
_REPORT_MANIFEST_VERSION_FULL = "curl/perf2html.sh v1"
_REPORT_THEME_STYLESHEET_ASSET: tuple[str, ...] = ("assets/theme.css",)

_SCREENSHOT_BROWSER_CANDIDATES: tuple[str, ...] = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
)

_SCREENSHOT_DARK_URL_PARAM = "screenshot-dark"
_SCREENSHOT_DARK_VALUES: tuple[str, ...] = ("1", "0")

_SCREENSHOT_DIR_NAME = "screenshots"

_SCREENSHOT_RENDER_BUDGET_MS = 8000

_SCREENSHOT_SCRATCH_DIR_PATH = "build/screenshots_scratch"

_SCREENSHOT_URL_PARAM = "screenshot"

_SCREENSHOT_VIEWPORTS: tuple[tuple[str, int, int], ...] = (
    ("720p", 1280, 720),
    ("4k", 3840, 2160),
)

_SHOOT_BOTH_REPORTS: tuple[str, ...] = (
    _REPORT_MANIFEST_VERSION_DIFF,
    _REPORT_MANIFEST_VERSION_FULL,
)
_SHOOT_REGULAR_REPORT_ONLY: tuple[str, ...] = (_REPORT_MANIFEST_VERSION_FULL,)

_SHOT_DARK_NAME_PART = "_dark-"
_SHOT_NUMBER_DIGITS = 2

_THUMBNAIL_SHEET_BACKGROUND = (18, 20, 24)

_THUMBNAIL_SHEET_COLUMNS = 3

_THUMBNAIL_SHEET_HEIGHT_PX = 2160
_THUMBNAIL_SHEET_WIDTH_PX = 3840

_VIEWS: tuple[tuple[tuple[str, ...], str, str, tuple[str, ...]], ...] = (
    (_SHOOT_BOTH_REPORTS, "", "overview", ()),
    (_SHOOT_BOTH_REPORTS, "#test=all&view=callers", "callers", ()),
    (
        _SHOOT_BOTH_REPORTS,
        "#test=urlparser&view=heat-map",
        "heat_map_home",
        (),
    ),
    (
        _SHOOT_BOTH_REPORTS,
        "#test=urlparser&view=heat-map"
        "&file=sysdeps/x86_64/multiarch/memchr-avx2.S",
        "heat_map_file",
        (),
    ),
    (
        _SHOOT_BOTH_REPORTS,
        "#test=urlparser&view=heat-map"
        "&file=sysdeps/x86_64/multiarch/memchr-avx2.S&line=82",
        "heat_map_line",
        (),
    ),
    (
        _SHOOT_BOTH_REPORTS,
        "#test=urlparser&view=heat-map&function=parseurl_and_replace",
        "heat_map_function",
        (),
    ),
    (
        _SHOOT_BOTH_REPORTS,
        "#test=urlparser&view=heat-map&function=no_such_function",
        "bad_function",
        (),
    ),
    (
        _SHOOT_BOTH_REPORTS,
        "",
        "report_incomplete",
        _REPORT_COMPLETE_ASSET,
    ),
    (
        _SHOOT_BOTH_REPORTS,
        "",
        "stylesheet_missing",
        _REPORT_THEME_STYLESHEET_ASSET,
    ),
    (
        _SHOOT_REGULAR_REPORT_ONLY,
        "#test=urlparser&view=flame-graph&localProfilePath=profile",
        "flame_graph",
        (),
    ),
)

_WINDOWS_BROWSER_SUFFIX = ".exe"


class Screenshots:
    def __init__(
        self, browser: str, report: str, out_dir: str, scratch_dir: str
    ) -> None:
        self.browser = browser
        self.report = report
        self.out_dir = out_dir
        self.scratch_dir = scratch_dir
        self.report_views = self.report_views_select()

    def browser_path_of(self, path: str) -> str:
        if not self.windows_browser_is():
            return path
        return subprocess.run(
            ["wslpath", "-w", path],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    def copy_shoot(
        self,
        view_index: int,
        prefix: str,
        name: str,
        view_hash: str,
        absent_files: tuple[str, ...],
    ) -> int:
        if os.path.exists(self.scratch_dir):
            shutil.rmtree(self.scratch_dir)
        shutil.copytree(self.report, self.scratch_dir)
        try:
            for relative_path in absent_files:
                os.remove(os.path.join(self.scratch_dir, relative_path))
            return self.view_shoot(
                self.scratch_dir, view_index, prefix, name, view_hash
            )
        finally:
            shutil.rmtree(self.scratch_dir)

    def page_url_of(
        self, name: str, page_dir: str, view_hash: str, dark_value: str
    ) -> str:
        page = self.browser_path_of(os.path.join(page_dir, _ENTRY_PAGE))
        label_text = (
            (view_hash + "&" if view_hash else "#")
            + f"{_SCREENSHOT_URL_PARAM}={name}"
            + f"&{_SCREENSHOT_DARK_URL_PARAM}={dark_value}"
        )
        query = "?" + urllib.parse.urlencode(
            {
                _SCREENSHOT_URL_PARAM: label_text,
                _SCREENSHOT_DARK_URL_PARAM: dark_value,
            }
        )
        if self.windows_browser_is():
            return "file://" + page.replace("\\", "/") + query + view_hash
        return "file://" + page + query + view_hash

    def report_views_select(
        self,
    ) -> list[tuple[int, tuple[tuple[str, ...], str, str, tuple[str, ...]]]]:
        manifest_path = os.path.join(self.report, _REPORT_MANIFEST_NAME)
        with open(manifest_path, encoding="utf-8") as manifest_file:
            manifest_version = manifest_file.readline().rstrip("\n")
        if manifest_version not in _SHOOT_BOTH_REPORTS:
            raise RuntimeError(
                f"{manifest_path}: line 1 found {manifest_version!r},"
                f" expected one of {_SHOOT_BOTH_REPORTS!r}"
            )
        return [
            (view_index, view)
            for view_index, view in enumerate(_VIEWS, 1)
            if manifest_version in view[0]
        ]

    def shoot_all(self, prefix: str) -> int:
        written = 0
        for view_index, view in self.report_views:
            _versions, view_hash, name, absent_files = view
            if absent_files:
                written += self.copy_shoot(
                    view_index, prefix, name, view_hash, absent_files
                )
            else:
                written += self.view_shoot(
                    self.report, view_index, prefix, name, view_hash
                )
        return written

    def shoot_one(
        self,
        shot: str,
        page_dir: str,
        name: str,
        view_hash: str,
        dark_value: str,
        width_px: int,
        height_px: int,
    ) -> None:
        out_path = os.path.join(self.out_dir, shot + _IMAGE_SUFFIX)
        if os.path.exists(out_path):
            os.remove(out_path)
        window = f"{width_px},{height_px}"
        result = subprocess.run(
            [
                self.browser,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--hide-scrollbars",
                "--incognito",
                f"--window-size={window}",
                f"--screenshot={self.browser_path_of(out_path)}",
                f"--virtual-time-budget={_SCREENSHOT_RENDER_BUDGET_MS}",
                self.page_url_of(name, page_dir, view_hash, dark_value),
            ],
            capture_output=True,
            text=True,
        )
        if os.path.exists(out_path) and os.path.getsize(out_path):
            return
        raise RuntimeError(
            f"{shot}: {view_hash or '(entry page)'} wrote no image:"
            f" {result.stderr.strip()[-_FAULT_TAIL_CHARS:]}"
        )

    def shot_name_of(
        self,
        view_index: int,
        size_name: str,
        prefix: str,
        name: str,
        dark_value: str,
    ) -> str:
        return (
            f"{view_index:0{_SHOT_NUMBER_DIGITS}d}_{size_name}_{prefix}"
            f"{name}{_SHOT_DARK_NAME_PART}{dark_value}"
        )

    def sheets_write(self, prefix: str) -> int:
        written = 0
        for size_name, _width_px, _height_px in _SCREENSHOT_VIEWPORTS:
            for dark_value in _SCREENSHOT_DARK_VALUES:
                shots = [
                    os.path.join(
                        self.out_dir,
                        self.shot_name_of(
                            view_index, size_name, prefix, view[2], dark_value
                        )
                        + _IMAGE_SUFFIX,
                    )
                    for view_index, view in self.report_views
                ]
                for path in shots:
                    assert os.path.isfile(path), f"missing shot: {path}"
                name = (
                    f"thumbnail_{size_name}_{prefix.rstrip('_')}"
                    f"{_SHOT_DARK_NAME_PART}{dark_value}"
                )
                self.sheet_one(name + _IMAGE_SUFFIX, shots)
                written += 1
        return written

    def sheet_one(self, name: str, shots: list[str]) -> None:
        sheet_rows = math.ceil(len(shots) / _THUMBNAIL_SHEET_COLUMNS)
        cell_width = _THUMBNAIL_SHEET_WIDTH_PX // _THUMBNAIL_SHEET_COLUMNS
        cell_height = _THUMBNAIL_SHEET_HEIGHT_PX // sheet_rows
        sheet = PIL.Image.new(
            "RGB",
            (_THUMBNAIL_SHEET_WIDTH_PX, _THUMBNAIL_SHEET_HEIGHT_PX),
            _THUMBNAIL_SHEET_BACKGROUND,
        )
        for index, path in enumerate(shots):
            shot = PIL.Image.open(path)
            shot.thumbnail(
                (cell_width, cell_height), PIL.Image.Resampling.LANCZOS
            )
            column = index % _THUMBNAIL_SHEET_COLUMNS
            row = index // _THUMBNAIL_SHEET_COLUMNS
            sheet.paste(
                shot,
                (
                    column * cell_width + (cell_width - shot.width) // 2,
                    row * cell_height + (cell_height - shot.height) // 2,
                ),
            )
        sheet.save(os.path.join(self.out_dir, name))

    def view_shoot(
        self,
        page_dir: str,
        view_index: int,
        prefix: str,
        name: str,
        view_hash: str,
    ) -> int:
        written = 0
        for size_name, width_px, height_px in _SCREENSHOT_VIEWPORTS:
            for dark_value in _SCREENSHOT_DARK_VALUES:
                shot = self.shot_name_of(
                    view_index, size_name, prefix, name, dark_value
                )
                self.shoot_one(
                    shot,
                    page_dir,
                    name,
                    view_hash,
                    dark_value,
                    width_px,
                    height_px,
                )
                written += 1
        return written

    def windows_browser_is(self) -> bool:
        return self.browser.lower().endswith(_WINDOWS_BROWSER_SUFFIX)


def browser_find() -> str | None:
    for candidate in _SCREENSHOT_BROWSER_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", help="a report directory to shoot")
    parser.add_argument("prefix", help="what every file name starts with")
    parser.add_argument(
        "--out",
        default="",
        help=f"where the PNGs go (default dev/{_SCREENSHOT_DIR_NAME})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print where the shots go and how many; a quiet run prints"
        " nothing on success",
    )
    namespace = parser.parse_args()

    report = os.path.abspath(namespace.report)
    if not os.path.isfile(os.path.join(report, _ENTRY_PAGE)):
        print(f"error: {report} holds no {_ENTRY_PAGE}", file=sys.stderr)
        return 1

    browser = browser_find()
    if browser is None:
        print(
            "error: no browser found. Tried: "
            + ", ".join(_SCREENSHOT_BROWSER_CANDIDATES),
            file=sys.stderr,
        )
        print(
            "       sudo apt-get install -y chromium-browser",
            file=sys.stderr,
        )
        return 1

    dev_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    out_dir = namespace.out or os.path.join(dev_dir, _SCREENSHOT_DIR_NAME)
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    scratch_dir = os.path.abspath(
        os.path.join(dev_dir, _SCREENSHOT_SCRATCH_DIR_PATH)
    )

    if namespace.verbose:
        print(f"{os.path.basename(report)} -> {out_dir}")
    shooter = Screenshots(browser, report, out_dir, scratch_dir)
    written = shooter.shoot_all(namespace.prefix)

    shooter.sheets_write(namespace.prefix)
    if namespace.verbose:
        print(f"{written} screenshot(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
