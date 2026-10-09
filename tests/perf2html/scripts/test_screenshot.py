#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

from typing import NamedTuple

import argparse, json, os, re, shutil, subprocess, sys, urllib.parse

import PIL.Image, PIL.ImageChops, PIL.ImageDraw, PIL.ImageEnhance
import PIL.ImageFont


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
    subview_name: str
    absent_files: tuple[str, ...]

    def shot_variants(self) -> tuple[ShotVariant, ...]:
        if self.shot_flags & _SHOOT_INDEX_PAGE:
            return _SHOT_INDEX_PAGE
        if self.shot_flags & _SHOOT_ONE_VARIANT:
            return _SHOT_ONE_VARIANT
        return _SHOT_REPORT_PERMUTATIONS


_COMPARE_BACKGROUND_COLOR = (96, 96, 96)
_COMPARE_BOX_LINE_PX = 4
_COMPARE_CROP_MARGIN_PX = 8
_COMPARE_GAP_PX = 8
_COMPARE_HIGHLIGHT_COLOR = (255, 0, 255)
_COMPARE_IMAGE_PREFIX = "compare_"
_COMPARE_KEPT_BRIGHTNESS_SHARE = 0.25
_COMPARE_LABEL_COLOR = (255, 255, 255)
_COMPARE_LABEL_FONT_PX = 20
_COMPARE_LISTED_REGION_COUNT = 4
_COMPARE_PANELS_MAX_HEIGHT_SHARE = 2
_COMPARE_REGION_TILE_PX = 16

_DEBUG_SCRIPT_ASSET: tuple[str, ...] = ("assets/debug.js",)

_ENTRY_PAGE = "index.html"

_FAULT_TAIL_CHARS = 400

_IMAGE_SUFFIX = ".png"

_INDEX_DATA_PATTERN = re.compile(
    r'<script id="shot-list-" type="application/json">(.*?)</script>',
    re.DOTALL,
)
_INDEX_MARKER = "__SHOT_LIST__"
_INDEX_PAGE_NAME = "test_index.html"
_INDEX_REPORT_NAMES: tuple[str, ...] = (
    "perf2html_baseline_report",
    "perf2html_modified_report",
    "perf2html_diff_report",
)
_INDEX_TEMPLATE_NAME = "test_template.html"

_REPORT_THEME_STYLESHEET_ASSET: tuple[str, ...] = ("assets/theme.css",)

_SCREENSHOT_BROWSER_CANDIDATES: tuple[str, ...] = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
)

_SCREENSHOT_DARK_URL_PARAM = "screenshot-mode"
_SCREENSHOT_DARK_VALUES: tuple[str, ...] = ("1", "0")

_SCREENSHOT_DIR_NAME = "screenshots"

_SCREENSHOT_MENU_URL_PARAM = "screenshot-menu"

_SCREENSHOT_RENDER_BUDGET_MS = 8000

_SCREENSHOT_SCRATCH_DIR_PATH = "build/screenshots_scratch"

_SCREENSHOT_VIEWPORTS: tuple[tuple[str, int, int], ...] = (
    ("720p", 1280, 720),
    ("4k", 3840, 2160),
)

_SHOOT_DIFF_REPORT = 1 << 0
# Shoots the index page of the finished run at 4k, once.
_SHOOT_INDEX_PAGE = 1 << 3
# Shoots 720p dark, once.
_SHOOT_ONE_VARIANT = 1 << 1
_SHOOT_REGULAR_REPORT = 1 << 2
_SHOOT_BOTH_REPORTS = _SHOOT_DIFF_REPORT | _SHOOT_REGULAR_REPORT

_SHOT_INDEX_PAGE: tuple[ShotVariant, ...] = (
    ShotVariant(*_SCREENSHOT_VIEWPORTS[1], _SCREENSHOT_DARK_VALUES[0]),
)
_SHOT_ONE_VARIANT: tuple[ShotVariant, ...] = (
    ShotVariant(*_SCREENSHOT_VIEWPORTS[0], _SCREENSHOT_DARK_VALUES[0]),
)
_SHOT_REPORT_PERMUTATIONS: tuple[ShotVariant, ...] = tuple(
    ShotVariant(*viewport, dark_value)
    for viewport in _SCREENSHOT_VIEWPORTS
    for dark_value in _SCREENSHOT_DARK_VALUES
)

_SHOT_MODE_NAME_PARTS: dict[str, str] = {"1": "dark", "0": "light"}
_SHOT_NAME_SEPARATOR = "-"
_SHOT_NUMBER_DIGITS = 2

_VIEWS: tuple[ScreenshotSet, ...] = (
    ScreenshotSet(_SHOOT_BOTH_REPORTS, "", "4", "overview", "home", ()),
    ScreenshotSet(
        _SHOOT_REGULAR_REPORT,
        "#test=urlparser&view=callers",
        "7",
        "callers",
        "urlparser",
        (),
    ),
    ScreenshotSet(
        _SHOOT_DIFF_REPORT,
        "#test=all&view=callers",
        "",
        "callers",
        "all",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS,
        "#test=urlparser&view=heat-map",
        "",
        "heat_map",
        "home",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS,
        "#test=urlparser&view=heat-map"
        "&file=sysdeps/x86_64/multiarch/memchr-avx2.S",
        "",
        "heat_map",
        "file",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS,
        "#test=urlparser&view=heat-map"
        "&file=sysdeps/x86_64/multiarch/memchr-avx2.S&line=82",
        "",
        "heat_map",
        "line",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS,
        "#test=urlparser&view=heat-map&function=parseurl_and_replace",
        "",
        "heat_map",
        "function",
        (),
    ),
    ScreenshotSet(
        _SHOOT_REGULAR_REPORT,
        "#test=urlparser&view=flame-graph&localProfilePath=profile",
        "",
        "flame_graph",
        "profile",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS | _SHOOT_ONE_VARIANT,
        "#test=all&view=settings",
        "",
        "settings",
        "list",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS | _SHOOT_ONE_VARIANT,
        "#test=all&view=settings&setting=DARK_MODE_ENABLED_DEFAULT"
        "&setting-values=eyJEQVJLX01PREVfRU5BQkxFRF9ERUZBVUxUIjpmYWxzZX0%3D",
        "",
        "settings",
        "applied",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS | _SHOOT_ONE_VARIANT,
        "#test=urlparser&view=heat-map&function=no_such_function",
        "",
        "error",
        "bad_function",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS | _SHOOT_ONE_VARIANT,
        "",
        "",
        "error",
        "report_incomplete",
        _DEBUG_SCRIPT_ASSET,
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS | _SHOOT_ONE_VARIANT,
        "",
        "",
        "error",
        "stylesheet_missing",
        _REPORT_THEME_STYLESHEET_ASSET,
    ),
    ScreenshotSet(
        _SHOOT_DIFF_REPORT | _SHOOT_INDEX_PAGE, "", "", "index", "page", ()
    ),
)

_WINDOWS_BROWSER_SUFFIX = ".exe"


class Screenshots:
    def __init__(
        self,
        browser: str | None,
        report: str,
        report_flag: int,
        out_dir: str,
        compare_dir: str,
        scratch_dir: str,
    ) -> None:
        self.browser = browser
        self.report = report
        self.report_flag = report_flag
        self.out_dir = out_dir
        self.compare_dir = compare_dir
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

    # Groups changed pixels into boxes, a tile touching another joining it.
    def changed_regions_of(
        self, changed_mask: PIL.Image.Image
    ) -> list[tuple[int, int, int, int]]:
        tile_mask = changed_mask.reduce(_COMPARE_REGION_TILE_PX)
        marked_tiles = {
            (tile_index % tile_mask.width, tile_index // tile_mask.width)
            for tile_index, tile_value in enumerate(tile_mask.tobytes())
            if tile_value
        }
        changed_regions: list[tuple[int, int, int, int]] = []
        while marked_tiles:
            pending_tiles = [marked_tiles.pop()]
            region_columns: list[int] = []
            region_rows: list[int] = []
            while pending_tiles:
                tile_column, tile_row = pending_tiles.pop()
                region_columns.append(tile_column)
                region_rows.append(tile_row)
                for neighbour_tile in (
                    (tile_column + column_step, tile_row + row_step)
                    for column_step in (-1, 0, 1)
                    for row_step in (-1, 0, 1)
                ):
                    if neighbour_tile in marked_tiles:
                        marked_tiles.remove(neighbour_tile)
                        pending_tiles.append(neighbour_tile)
            tile_left = min(region_columns) * _COMPARE_REGION_TILE_PX
            tile_top = min(region_rows) * _COMPARE_REGION_TILE_PX
            inner_box = changed_mask.crop(
                (
                    tile_left,
                    tile_top,
                    (max(region_columns) + 1) * _COMPARE_REGION_TILE_PX,
                    (max(region_rows) + 1) * _COMPARE_REGION_TILE_PX,
                )
            ).getbbox()
            assert inner_box is not None, "a marked tile holds no change"
            inner_left, inner_top, inner_right, inner_bottom = inner_box
            changed_regions.append(
                (
                    tile_left + inner_left,
                    tile_top + inner_top,
                    tile_left + inner_right,
                    tile_top + inner_bottom,
                )
            )
        return sorted(
            changed_regions,
            key=lambda changed_region: (changed_region[1], changed_region[0]),
        )

    # Writes the dimmed shot with boxes, then each region gold and new.
    def compare_image_write(
        self,
        new_shot: PIL.Image.Image,
        gold_shot: PIL.Image.Image,
        changed_mask: PIL.Image.Image,
        changed_regions: list[tuple[int, int, int, int]],
        compare_path: str,
    ) -> None:
        overview_image = PIL.ImageEnhance.Brightness(new_shot).enhance(
            _COMPARE_KEPT_BRIGHTNESS_SHARE
        )
        overview_image.paste(_COMPARE_HIGHLIGHT_COLOR, mask=changed_mask)
        box_drawing = PIL.ImageDraw.Draw(overview_image)
        label_font = PIL.ImageFont.load_default(size=_COMPARE_LABEL_FONT_PX)
        for region_number, (
            region_left,
            region_top,
            region_right,
            region_bottom,
        ) in enumerate(changed_regions, 1):
            box_drawing.rectangle(
                (
                    region_left - _COMPARE_BOX_LINE_PX,
                    region_top - _COMPARE_BOX_LINE_PX,
                    region_right - 1 + _COMPARE_BOX_LINE_PX,
                    region_bottom - 1 + _COMPARE_BOX_LINE_PX,
                ),
                outline=_COMPARE_HIGHLIGHT_COLOR,
                width=_COMPARE_BOX_LINE_PX,
            )
            box_drawing.text(
                (
                    max(region_left - _COMPARE_BOX_LINE_PX, 0),
                    max(
                        region_top
                        - _COMPARE_BOX_LINE_PX
                        - _COMPARE_LABEL_FONT_PX,
                        0,
                    ),
                ),
                str(region_number),
                fill=_COMPARE_HIGHLIGHT_COLOR,
                font=label_font,
            )
        region_panels: list[PIL.Image.Image] = []
        panels_height = 0
        for region_number, changed_region in enumerate(changed_regions, 1):
            if any(
                self.region_holds(other_region, changed_region)
                for other_region in changed_regions
                if other_region != changed_region
            ):
                continue
            region_panel = self.region_panel_of(
                region_number, changed_region, gold_shot, new_shot, label_font
            )
            if (
                panels_height + region_panel.height
                > _COMPARE_PANELS_MAX_HEIGHT_SHARE * new_shot.height
            ):
                continue
            region_panels.append(region_panel)
            panels_height += region_panel.height + _COMPARE_GAP_PX
        compare_image = PIL.Image.new(
            "RGB",
            (
                max(
                    [overview_image.width]
                    + [region_panel.width for region_panel in region_panels]
                ),
                overview_image.height + panels_height,
            ),
            _COMPARE_BACKGROUND_COLOR,
        )
        compare_image.paste(overview_image, (0, 0))
        panel_top = overview_image.height
        for region_panel in region_panels:
            compare_image.paste(region_panel, (0, panel_top))
            panel_top += region_panel.height + _COMPARE_GAP_PX
        os.makedirs(self.compare_dir, exist_ok=True)
        compare_image.save(compare_path)

    # Answers the address of a report's entry page relative to the index.
    def entry_href_of(self, report_dir: str, index_path: str) -> str:
        return urllib.parse.quote(
            os.path.relpath(
                os.path.join(report_dir, _ENTRY_PAGE),
                os.path.dirname(index_path),
            )
        )

    # Names each shot that differs from its gold twin, each one missing.
    def gold_compare(
        self, gold_dir: str, prefix: str, is_verbose: bool
    ) -> bool:
        shot_pattern = re.compile(
            f"[0-9]{{{_SHOT_NUMBER_DIGITS}}}-[^-]+-[^-]+-[^-]+"
            f"-{re.escape(prefix.rstrip('_'))}-.*" + re.escape(_IMAGE_SUFFIX)
        )
        if os.path.isdir(self.compare_dir):
            for file_name in os.listdir(self.compare_dir):
                if file_name.startswith(
                    _COMPARE_IMAGE_PREFIX
                ) and shot_pattern.fullmatch(
                    file_name.removeprefix(_COMPARE_IMAGE_PREFIX)
                ):
                    os.remove(os.path.join(self.compare_dir, file_name))
        shot_names = self.shot_names_of(prefix)
        is_same = True
        for shot_name in shot_names:
            if not self.gold_compare_one(
                shot_name + _IMAGE_SUFFIX, gold_dir, is_verbose
            ):
                is_same = False
        for file_name in sorted(os.listdir(gold_dir)):
            if (
                shot_pattern.fullmatch(file_name)
                and file_name.removesuffix(_IMAGE_SUFFIX) not in shot_names
            ):
                print(
                    f"{file_name}: in {gold_dir}, not among this run's shots",
                    file=sys.stderr,
                )
                is_same = False
        if not is_same:
            os.makedirs(self.compare_dir, exist_ok=True)
        return is_same

    def gold_compare_one(
        self, file_name: str, gold_dir: str, is_verbose: bool
    ) -> bool:
        gold_path = os.path.join(gold_dir, file_name)
        if not os.path.isfile(gold_path):
            print(f"{file_name}: absent from {gold_dir}", file=sys.stderr)
            return False
        new_path = os.path.join(self.out_dir, file_name)
        if not os.path.isfile(new_path):
            print(f"{file_name}: absent from {self.out_dir}", file=sys.stderr)
            return False
        new_shot = PIL.Image.open(new_path).convert("RGB")
        gold_shot = PIL.Image.open(gold_path).convert("RGB")
        if new_shot.size != gold_shot.size:
            print(
                f"{file_name}: {new_shot.width}x{new_shot.height}, gold"
                f" {gold_shot.width}x{gold_shot.height}",
                file=sys.stderr,
            )
            return False
        red_change, green_change, blue_change = PIL.ImageChops.difference(
            new_shot, gold_shot
        ).split()
        channel_change = PIL.ImageChops.lighter(
            PIL.ImageChops.lighter(red_change, green_change), blue_change
        )
        if channel_change.getbbox() is None:
            if is_verbose:
                print(f"{file_name}: same as gold")
            return True
        changed_mask = channel_change.point(
            lambda channel_value: 255 if channel_value else 0
        )
        changed_count = changed_mask.histogram()[255]
        changed_regions = self.changed_regions_of(changed_mask)
        compare_path = os.path.join(
            self.compare_dir, _COMPARE_IMAGE_PREFIX + file_name
        )
        self.compare_image_write(
            new_shot, gold_shot, changed_mask, changed_regions, compare_path
        )
        listed_regions = "; ".join(
            f"{region_left},{region_top} to {region_right},{region_bottom}"
            for region_left, region_top, region_right, region_bottom in (
                changed_regions[:_COMPARE_LISTED_REGION_COUNT]
            )
        )
        unlisted_count = len(changed_regions) - _COMPARE_LISTED_REGION_COUNT
        if unlisted_count > 0:
            listed_regions += f"; {unlisted_count} more"
        changed_percent = (
            100 * changed_count / (new_shot.width * new_shot.height)
        )
        print(
            f"{file_name}: {changed_count} pixels differ"
            f" ({changed_percent:.2f}%),"
            f" largest channel change {channel_change.getextrema()[1]},"
            f" {len(changed_regions)} region(s) {listed_regions},"
            f" see {compare_path}",
            file=sys.stderr,
        )
        return False

    # Merges this report's pages into the index, keeping other reports'.
    def index_write(self, prefix: str, index_path: str, template: str) -> None:
        assert template.count(_INDEX_MARKER) == 1, _INDEX_MARKER
        report_name = prefix.rstrip("_")
        report_href = self.entry_href_of(self.report, index_path)
        index_reports: list[dict[str, str]] = []
        for listed_report in _INDEX_REPORT_NAMES:
            listed_dir = os.path.join(
                os.path.dirname(index_path), listed_report
            )
            if not os.path.isfile(os.path.join(listed_dir, _ENTRY_PAGE)):
                raise RuntimeError(f"{listed_dir} holds no {_ENTRY_PAGE}")
            index_reports.append(
                {
                    "name": listed_report,
                    "href": self.entry_href_of(listed_dir, index_path),
                }
            )
        width_px, height_px = _SCREENSHOT_VIEWPORTS[0][1:]
        pages: dict[str, str] = {}
        if os.path.isfile(index_path):
            with open(index_path) as index_file:
                found = _INDEX_DATA_PATTERN.search(index_file.read())
            assert found, f"{index_path} holds no shot list"
            for page in json.loads(found.group(1))["pages"]:
                if page["report"] != report_name:
                    pages[page["name"]] = page["href"]
        for view_index, view in self.report_views:
            if view.absent_files or view.shot_flags & _SHOOT_INDEX_PAGE:
                continue
            for dark_value in dict.fromkeys(
                variant.dark_value for variant in view.shot_variants()
            ):
                pages[
                    self.shot_name_of(view_index, "", prefix, view, dark_value)
                ] = report_href + self.page_address_of(
                    view.view_hash, view.menu_entry_number, dark_value
                )
        data = {
            "width": width_px,
            "height": height_px,
            "pages": [
                {
                    "name": name,
                    "report": name.split(_SHOT_NAME_SEPARATOR)[-2],
                    "href": pages[name],
                }
                for name in sorted(pages)
            ],
            "reports": index_reports,
        }
        data_script = (
            '<script id="shot-list-" type="application/json">'
            + json.dumps(data, indent=1)
            + "</script>"
        )
        with open(index_path, "w") as index_file:
            index_file.write(template.replace(_INDEX_MARKER, data_script))

    # Answers the query and hash a page is shot at.
    def page_address_of(
        self, view_hash: str, menu_entry_number: str, dark_value: str
    ) -> str:
        query_values = {_SCREENSHOT_DARK_URL_PARAM: dark_value}
        if menu_entry_number:
            query_values[_SCREENSHOT_MENU_URL_PARAM] = menu_entry_number
        return "?" + urllib.parse.urlencode(query_values) + view_hash

    def page_url_of(
        self,
        page_dir: str,
        view_hash: str,
        menu_entry_number: str,
        dark_value: str,
    ) -> str:
        page = self.browser_path_of(
            page_dir
            if os.path.isfile(page_dir)
            else os.path.join(page_dir, _ENTRY_PAGE)
        )
        address = self.page_address_of(
            view_hash, menu_entry_number, dark_value
        )
        if self.windows_browser_is():
            # A share path (//host/dir) names the host, a drive needs a slash.
            slashed = page.replace("\\", "/")
            lead = "file:" if slashed.startswith("//") else "file:///"
            return lead + slashed + address
        return "file://" + page + address

    # Answers whether the outer region holds the whole inner region.
    def region_holds(
        self,
        outer_region: tuple[int, int, int, int],
        inner_region: tuple[int, int, int, int],
    ) -> bool:
        return (
            outer_region[0] <= inner_region[0]
            and outer_region[1] <= inner_region[1]
            and inner_region[2] <= outer_region[2]
            and inner_region[3] <= outer_region[3]
        )

    # Sets the gold and the new cut of one region side by side under a label.
    def region_panel_of(
        self,
        region_number: int,
        changed_region: tuple[int, int, int, int],
        gold_shot: PIL.Image.Image,
        new_shot: PIL.Image.Image,
        label_font: PIL.ImageFont.FreeTypeFont | PIL.ImageFont.ImageFont,
    ) -> PIL.Image.Image:
        region_left, region_top, region_right, region_bottom = changed_region
        crop_box = (
            max(region_left - _COMPARE_CROP_MARGIN_PX, 0),
            max(region_top - _COMPARE_CROP_MARGIN_PX, 0),
            min(region_right + _COMPARE_CROP_MARGIN_PX, new_shot.width),
            min(region_bottom + _COMPARE_CROP_MARGIN_PX, new_shot.height),
        )
        crop_width = crop_box[2] - crop_box[0]
        crop_height = crop_box[3] - crop_box[1]
        gold_label = (
            f"{region_number} gold {region_left},{region_top}"
            f" to {region_right},{region_bottom}"
        )
        gold_label_width = int(label_font.getlength(gold_label)) + 1
        column_width = max(crop_width, gold_label_width)
        label_height = _COMPARE_LABEL_FONT_PX + _COMPARE_GAP_PX
        new_left = column_width + _COMPARE_GAP_PX
        region_panel = PIL.Image.new(
            "RGB",
            (new_left + column_width, label_height + crop_height),
            _COMPARE_BACKGROUND_COLOR,
        )
        region_panel.paste(gold_shot.crop(crop_box), (0, label_height))
        region_panel.paste(new_shot.crop(crop_box), (new_left, label_height))
        panel_drawing = PIL.ImageDraw.Draw(region_panel)
        panel_drawing.text(
            (0, 0), gold_label, fill=_COMPARE_LABEL_COLOR, font=label_font
        )
        panel_drawing.text(
            (new_left, 0),
            f"{region_number} new",
            fill=_COMPARE_LABEL_COLOR,
            font=label_font,
        )
        return region_panel

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
            if view.shot_flags & _SHOOT_INDEX_PAGE:
                continue
            if view.absent_files:
                written += self.copy_shoot(view_index, prefix, view)
            else:
                written += self.view_shoot(
                    self.report, view_index, prefix, view
                )
        return written

    def index_shoot(self, prefix: str, index_path: str) -> int:
        written = 0
        for view_index, view in self.report_views:
            if view.shot_flags & _SHOOT_INDEX_PAGE:
                written += self.view_shoot(
                    index_path, view_index, prefix, view
                )
        return written

    def shoot_one(
        self,
        shot: str,
        page_dir: str,
        view_hash: str,
        menu_entry_number: str,
        dark_value: str,
        width_px: int,
        height_px: int,
    ) -> None:
        out_path = os.path.join(self.out_dir, shot + _IMAGE_SUFFIX)
        if os.path.exists(out_path):
            os.remove(out_path)
        assert self.browser is not None, "a compare only run shoots nothing"
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
                    page_dir, view_hash, menu_entry_number, dark_value
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

    # Names a shot, leaving out the resolution when the size is empty.
    def shot_name_of(
        self,
        view_index: int,
        size_name: str,
        prefix: str,
        view: ScreenshotSet,
        dark_value: str,
    ) -> str:
        return _SHOT_NAME_SEPARATOR.join(
            name_part
            for name_part in (
                f"{view_index:0{_SHOT_NUMBER_DIGITS}d}",
                size_name,
                view.view_name,
                view.subview_name,
                prefix.rstrip("_"),
                _SHOT_MODE_NAME_PARTS[dark_value],
            )
            if name_part
        )

    # Names every shot of this report, the index page's too.
    def shot_names_of(self, prefix: str) -> list[str]:
        return [
            self.shot_name_of(
                view_index, variant.size_name, prefix, view, variant.dark_value
            )
            for view_index, view in self.report_views
            for variant in view.shot_variants()
        ]

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
                view_index, variant.size_name, prefix, view, variant.dark_value
            )
            self.shoot_one(
                shot,
                page_dir,
                view.view_hash,
                view.menu_entry_number,
                variant.dark_value,
                variant.width_px,
                variant.height_px,
            )
        return len(shot_variants)

    def windows_browser_is(self) -> bool:
        assert self.browser is not None, "a compare only run shoots nothing"
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
        "--compare-gold",
        default="",
        metavar="DIR",
        help="compare each new shot with the same named shot in DIR, naming"
        " every difference and writing a compare_ image of it; exit 1 if"
        " any shot differs or is missing",
    )
    parser.add_argument(
        "--compare-only",
        action="store_true",
        help="shoot nothing and compare the shots already in the --out"
        " directory; needs --compare-gold",
    )
    parser.add_argument(
        "--compare-out",
        default="",
        metavar="DIR",
        help="where the compare_ images go, made when a shot differs"
        " (default the --out directory)",
    )
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

    gold_dir = os.path.abspath(namespace.compare_gold)
    if namespace.compare_gold and not os.path.isdir(gold_dir):
        print(
            f"error: --compare-gold {gold_dir} is no directory",
            file=sys.stderr,
        )
        return 1

    if namespace.compare_out and not namespace.compare_gold:
        print("error: --compare-out needs --compare-gold", file=sys.stderr)
        return 1

    if namespace.compare_only and not namespace.compare_gold:
        print("error: --compare-only needs --compare-gold", file=sys.stderr)
        return 1

    browser = None if namespace.compare_only else browser_find()
    if browser is None and not namespace.compare_only:
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
    scratch_dir = os.path.abspath(
        os.path.join(perf2html_dir, _SCREENSHOT_SCRATCH_DIR_PATH)
    )

    report_flag = (
        _SHOOT_DIFF_REPORT if namespace.diff else _SHOOT_REGULAR_REPORT
    )
    compare_dir = os.path.abspath(namespace.compare_out or out_dir)
    shooter = Screenshots(
        browser, report, report_flag, out_dir, compare_dir, scratch_dir
    )
    if namespace.compare_only:
        is_same = shooter.gold_compare(
            gold_dir, namespace.prefix, namespace.verbose
        )
        return 0 if is_same else 1

    os.makedirs(out_dir, exist_ok=True)
    if namespace.verbose:
        print(f"{os.path.basename(report)} -> {out_dir}")
    written = shooter.shoot_all(namespace.prefix)

    with open(
        os.path.join(perf2html_dir, "scripts", _INDEX_TEMPLATE_NAME)
    ) as template_file:
        index_template = template_file.read()
    shooter.index_write(
        namespace.prefix,
        os.path.join(perf2html_dir, _INDEX_PAGE_NAME),
        index_template,
    )
    written += shooter.index_shoot(
        namespace.prefix, os.path.join(perf2html_dir, _INDEX_PAGE_NAME)
    )
    if namespace.verbose:
        print(f"{written} screenshot(s)")
    if namespace.compare_gold and not shooter.gold_compare(
        gold_dir, namespace.prefix, namespace.verbose
    ):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
