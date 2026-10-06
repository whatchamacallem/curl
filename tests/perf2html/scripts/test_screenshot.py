#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

from typing import NamedTuple

import argparse, math, os, shutil, subprocess, sys, urllib.parse

import PIL.Image


class ShotVariant(NamedTuple):
    size_name: str
    width_px: int
    height_px: int
    dark_value: str


class ScreenshotSet(NamedTuple):
    shot_flags: int
    view_hash: str
    # Digit of the menu entry the shot focuses or opens, empty for none.
    menu_entry_number: str
    view_name: str
    absent_files: tuple[str, ...]

    def shot_variants(self) -> tuple[ShotVariant, ...]:
        if self.shot_flags & _SHOOT_ERROR_HANDLER:
            return _SHOT_ERROR_HANDLER
        return _SHOT_REPORT_PERMUTATIONS


_ENTRY_PAGE = "index.html"

_FAULT_TAIL_CHARS = 400

_IMAGE_SUFFIX = ".png"

_REPORT_COMPLETE_ASSET: tuple[str, ...] = ("assets/report_complete.js",)

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

_SCREENSHOT_MENU_URL_PARAM = "screenshot_menu"

_SCREENSHOT_RENDER_BUDGET_MS = 8000

_SCREENSHOT_SCRATCH_DIR_PATH = "build/screenshots_scratch"

_SCREENSHOT_URL_PARAM = "screenshot"

_SCREENSHOT_VIEWPORTS: tuple[tuple[str, int, int], ...] = (
    ("720p", 1280, 720),
    ("4k", 3840, 2160),
)

_SHOOT_DIFF_REPORT = 1 << 0
_SHOOT_ERROR_HANDLER = 1 << 1
_SHOOT_REGULAR_REPORT = 1 << 2
_SHOOT_BOTH_REPORTS = _SHOOT_DIFF_REPORT | _SHOOT_REGULAR_REPORT

_SHOT_ERROR_HANDLER: tuple[ShotVariant, ...] = (
    ShotVariant(*_SCREENSHOT_VIEWPORTS[0], _SCREENSHOT_DARK_VALUES[0]),
)
_SHOT_REPORT_PERMUTATIONS: tuple[ShotVariant, ...] = tuple(
    ShotVariant(*viewport, dark_value)
    for viewport in _SCREENSHOT_VIEWPORTS
    for dark_value in _SCREENSHOT_DARK_VALUES
)

_SHOT_MODE_NAME_PARTS: dict[str, str] = {"1": "_dark", "0": "_light"}
_SHOT_NUMBER_DIGITS = 2

_THUMBNAIL_SHEET_BACKGROUND = (128, 128, 128)

_THUMBNAIL_SHEET_COLUMNS = 3

_THUMBNAIL_SHEET_HEIGHT_PX = 2160
_THUMBNAIL_SHEET_NUMBER_DIGITS = 2
_THUMBNAIL_SHEET_ROWS = 3
_THUMBNAIL_SHEET_WIDTH_PX = 3840

_VIEWS: tuple[ScreenshotSet, ...] = (
    ScreenshotSet(_SHOOT_BOTH_REPORTS, "", "4", "overview", ()),
    ScreenshotSet(
        _SHOOT_REGULAR_REPORT,
        "#test=urlparser&view=callers",
        "7",
        "callers",
        (),
    ),
    ScreenshotSet(
        _SHOOT_DIFF_REPORT,
        "#test=all&view=callers",
        "",
        "callers",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS,
        "#test=urlparser&view=heat-map",
        "",
        "heat_map_home",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS,
        "#test=urlparser&view=heat-map"
        "&file=sysdeps/x86_64/multiarch/memchr-avx2.S",
        "",
        "heat_map_file",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS,
        "#test=urlparser&view=heat-map"
        "&file=sysdeps/x86_64/multiarch/memchr-avx2.S&line=82",
        "",
        "heat_map_line",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS,
        "#test=urlparser&view=heat-map&function=parseurl_and_replace",
        "",
        "heat_map_function",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS | _SHOOT_ERROR_HANDLER,
        "#test=urlparser&view=heat-map&function=no_such_function",
        "",
        "bad_function",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS | _SHOOT_ERROR_HANDLER,
        "",
        "",
        "report_incomplete",
        _REPORT_COMPLETE_ASSET,
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS | _SHOOT_ERROR_HANDLER,
        "",
        "",
        "stylesheet_missing",
        _REPORT_THEME_STYLESHEET_ASSET,
    ),
    ScreenshotSet(
        _SHOOT_REGULAR_REPORT,
        "#test=urlparser&view=flame-graph&profiler_path=profile",
        "",
        "flame_graph",
        (),
    ),
)

_WINDOWS_BROWSER_SUFFIX = ".exe"


class Screenshots:
    def __init__(
        self,
        browser: str,
        report: str,
        report_flag: int,
        out_dir: str,
        scratch_dir: str,
    ) -> None:
        self.browser = browser
        self.report = report
        self.report_flag = report_flag
        self.out_dir = out_dir
        self.scratch_dir = scratch_dir
        self.report_views = self.report_views_select()

    def browser_path_of(self, path: str) -> str:
        if not self.windows_browser_is():
            return path
        return subprocess.run(
            ["wslpath", "-w", os.path.realpath(path)],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    def copy_shoot(
        self,
        view_index: int,
        prefix: str,
        view: ScreenshotSet,
    ) -> int:
        if os.path.exists(self.scratch_dir):
            shutil.rmtree(self.scratch_dir)
        shutil.copytree(self.report, self.scratch_dir)
        try:
            for relative_path in view.absent_files:
                os.remove(os.path.join(self.scratch_dir, relative_path))
            return self.view_shoot(self.scratch_dir, view_index, prefix, view)
        finally:
            shutil.rmtree(self.scratch_dir)

    def page_url_of(
        self,
        name: str,
        page_dir: str,
        view_hash: str,
        menu_entry_number: str,
        dark_value: str,
    ) -> str:
        page = self.browser_path_of(os.path.join(page_dir, _ENTRY_PAGE))
        query_values = {_SCREENSHOT_DARK_URL_PARAM: dark_value}
        if menu_entry_number:
            query_values[_SCREENSHOT_MENU_URL_PARAM] = menu_entry_number
        label_text = (
            (view_hash + "&" if view_hash else "#")
            + f"{_SCREENSHOT_URL_PARAM}={name}&"
            + urllib.parse.urlencode(query_values)
        )
        query = "?" + urllib.parse.urlencode(
            {_SCREENSHOT_URL_PARAM: label_text, **query_values}
        )
        if self.windows_browser_is():
            return "file://" + page.replace("\\", "/") + query + view_hash
        return "file://" + page + query + view_hash

    def report_views_select(
        self,
    ) -> list[tuple[int, ScreenshotSet]]:
        return [
            (view_index, view)
            for view_index, view in enumerate(_VIEWS, 1)
            if view.shot_flags & self.report_flag
        ]

    def shoot_all(self, prefix: str) -> int:
        written = 0
        for view_index, view in self.report_views:
            if view.absent_files:
                written += self.copy_shoot(view_index, prefix, view)
            else:
                written += self.view_shoot(
                    self.report, view_index, prefix, view
                )
        return written

    def shoot_one(
        self,
        shot: str,
        page_dir: str,
        name: str,
        view_hash: str,
        menu_entry_number: str,
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
                # Draws a frame only after the page's own work for it.
                "--run-all-compositor-stages-before-draw",
                f"--window-size={window}",
                f"--screenshot={self.browser_path_of(out_path)}",
                f"--virtual-time-budget={_SCREENSHOT_RENDER_BUDGET_MS}",
                self.page_url_of(
                    name, page_dir, view_hash, menu_entry_number, dark_value
                ),
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
            f"{name}{_SHOT_MODE_NAME_PARTS[dark_value]}"
        )

    def sheets_write(self, prefix: str) -> int:
        written = 0
        sheet_cells = _THUMBNAIL_SHEET_COLUMNS * _THUMBNAIL_SHEET_ROWS
        for variant in _SHOT_REPORT_PERMUTATIONS:
            shots = [
                os.path.join(
                    self.out_dir,
                    self.shot_name_of(
                        view_index,
                        variant.size_name,
                        prefix,
                        view.view_name,
                        variant.dark_value,
                    )
                    + _IMAGE_SUFFIX,
                )
                for view_index, view in self.report_views
                if variant in view.shot_variants()
            ]
            for path in shots:
                assert os.path.isfile(path), f"missing shot: {path}"
            for sheet_index in range(math.ceil(len(shots) / sheet_cells)):
                name = (
                    f"thumbnail_{variant.size_name}_{prefix.rstrip('_')}"
                    f"_{sheet_index + 1:0{_THUMBNAIL_SHEET_NUMBER_DIGITS}d}"
                    f"{_SHOT_MODE_NAME_PARTS[variant.dark_value]}"
                )
                first_shot = sheet_index * sheet_cells
                self.sheet_one(
                    name + _IMAGE_SUFFIX,
                    shots[first_shot : first_shot + sheet_cells],
                )
                written += 1
        return written

    def sheet_one(self, name: str, shots: list[str]) -> None:
        cell_width = _THUMBNAIL_SHEET_WIDTH_PX // _THUMBNAIL_SHEET_COLUMNS
        cell_height = _THUMBNAIL_SHEET_HEIGHT_PX // _THUMBNAIL_SHEET_ROWS
        sheet = PIL.Image.new(
            "RGB",
            (_THUMBNAIL_SHEET_WIDTH_PX, _THUMBNAIL_SHEET_HEIGHT_PX),
            _THUMBNAIL_SHEET_BACKGROUND,
        )
        for index, path in enumerate(shots):
            shot = PIL.Image.open(path)
            fit = min(cell_width / shot.width, cell_height / shot.height)
            shot = shot.resize(
                (round(shot.width * fit), round(shot.height * fit)),
                PIL.Image.Resampling.LANCZOS,
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
        view: ScreenshotSet,
    ) -> int:
        shot_variants = view.shot_variants()
        for variant in shot_variants:
            shot = self.shot_name_of(
                view_index,
                variant.size_name,
                prefix,
                view.view_name,
                variant.dark_value,
            )
            self.shoot_one(
                shot,
                page_dir,
                view.view_name,
                view.view_hash,
                view.menu_entry_number,
                variant.dark_value,
                variant.width_px,
                variant.height_px,
            )
        return len(shot_variants)

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
        "--diff", action="store_true", help="the report is a diff report"
    )
    parser.add_argument(
        "--out",
        default="",
        help="where the PNGs go (default"
        f" tests/perf2html/{_SCREENSHOT_DIR_NAME})",
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

    perf2html_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".."
    )
    out_dir = namespace.out or os.path.join(
        perf2html_dir, _SCREENSHOT_DIR_NAME
    )
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    scratch_dir = os.path.abspath(
        os.path.join(perf2html_dir, _SCREENSHOT_SCRATCH_DIR_PATH)
    )

    if namespace.verbose:
        print(f"{os.path.basename(report)} -> {out_dir}")
    report_flag = (
        _SHOOT_DIFF_REPORT if namespace.diff else _SHOOT_REGULAR_REPORT
    )
    shooter = Screenshots(browser, report, report_flag, out_dir, scratch_dir)
    written = shooter.shoot_all(namespace.prefix)

    shooter.sheets_write(namespace.prefix)
    if namespace.verbose:
        print(f"{written} screenshot(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
