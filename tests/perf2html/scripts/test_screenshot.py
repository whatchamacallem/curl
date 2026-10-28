#!/usr/bin/env python3
# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

from typing import Any, NamedTuple

import argparse, bisect, json, os, re, shutil, subprocess, sys, urllib.parse

import PIL.Image, PIL.ImageChops, PIL.ImageDraw, PIL.ImageEnhance
import PIL.ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_settings


class PageTiming(NamedTuple):
    # A report page's file, relative to the report.
    page_file: str
    # Load, or the phase a trace slice of the page counts to.
    phase_name: str
    # The phase name, then a script phase's own script file.
    phase_label: str
    duration_us: float
    shot: str


class ShotVariant(NamedTuple):
    size_name: str
    width_px: int
    height_px: int
    toggle_dark_value: str


class ScreenshotSet(NamedTuple):
    shot_flags: int
    view_hash: str
    # Digit of the menu entry the shot focuses or opens, empty for none.
    menu_entry_number: str
    view_name: str
    subview_name: str
    absent_files: tuple[str, ...]

    def shot_variants(self) -> tuple[ShotVariant, ...]:
        if self.shot_flags & test_settings.SHOOT_INDEX_PAGE:
            return _SHOT_INDEX_PAGE
        if self.shot_flags & test_settings.SHOOT_ONE_VARIANT:
            return _SHOT_ONE_VARIANT
        return _SHOT_REPORT_PERMUTATIONS


_SHOOT_BOTH_REPORTS = (
    test_settings.SHOOT_DIFF_REPORT | test_settings.SHOOT_REGULAR_REPORT
)

_SHOT_INDEX_PAGE: tuple[ShotVariant, ...] = (
    ShotVariant(
        *test_settings.SCREENSHOT_VIEWPORTS[1],
        test_settings.SCREENSHOT_TOGGLE_DARK_VALUES[0],
    ),
)
_SHOT_ONE_VARIANT: tuple[ShotVariant, ...] = (
    ShotVariant(
        *test_settings.SCREENSHOT_VIEWPORTS[0],
        test_settings.SCREENSHOT_TOGGLE_DARK_VALUES[0],
    ),
)
_SHOT_REPORT_PERMUTATIONS: tuple[ShotVariant, ...] = tuple(
    ShotVariant(*viewport, toggle_dark_value)
    for viewport in test_settings.SCREENSHOT_VIEWPORTS
    for toggle_dark_value in test_settings.SCREENSHOT_TOGGLE_DARK_VALUES
)

_VIEWS: tuple[ScreenshotSet, ...] = (
    ScreenshotSet(
        test_settings.SHOOT_REGULAR_REPORT,
        "#test=urlparser&view=flame-graph&localProfilePath=profile",
        "",
        "flame_graph",
        "profile",
        (),
    ),
    ScreenshotSet(
        test_settings.SHOOT_DIFF_REPORT, "", "2", "overview", "home", ()
    ),
    ScreenshotSet(
        test_settings.SHOOT_REGULAR_REPORT, "", "", "overview", "home", ()
    ),
    ScreenshotSet(
        test_settings.SHOOT_REGULAR_REPORT,
        "#test=urlparser&view=database",
        "5",
        "database",
        "urlparser",
        (),
    ),
    ScreenshotSet(
        test_settings.SHOOT_REGULAR_REPORT | test_settings.SHOOT_ONE_VARIANT,
        "#test=urlparser&view=heat-map",
        "",
        "error",
        "no_file_or_function_heat_map",
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
        _SHOOT_BOTH_REPORTS | test_settings.SHOOT_ONE_VARIANT,
        "#view=settings",
        "",
        "settings",
        "list",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS | test_settings.SHOOT_ONE_VARIANT,
        "#view=settings&setting=DARK_MODE_ENABLED_DEFAULT"
        "&setting-values=eyJEQVJLX01PREVfRU5BQkxFRF9ERUZBVUxUIjpmYWxzZX0%3D",
        "",
        "settings",
        "applied",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS | test_settings.SHOOT_ONE_VARIANT,
        "#test=urlparser&view=heat-map&function=no_such_function",
        "",
        "error",
        "bad_function",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS | test_settings.SHOOT_ONE_VARIANT,
        "",
        "",
        "error",
        "report_incomplete",
        test_settings.DEBUG_SCRIPT_ASSET,
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS | test_settings.SHOOT_ONE_VARIANT,
        "",
        "",
        "error",
        "stylesheet_missing",
        test_settings.REPORT_THEME_STYLESHEET_ASSET,
    ),
    ScreenshotSet(
        test_settings.SHOOT_DIFF_REPORT | test_settings.SHOOT_INDEX_PAGE,
        "",
        "",
        "index",
        "page",
        (),
    ),
    ScreenshotSet(
        test_settings.SHOOT_REGULAR_REPORT,
        "#test=urlparser&view=database"
        "&setting-values=eyJEQVRBQkFTRV9DT1VOVEVSX0xJU1RfREVGQVVMVF9TSE9X"
        "Tl9OQU1FUyI6WyJjYWxscyIsIklyIiwiRDFtciIsIkRMbXIiLCJCY20iXX0%3D",
        "",
        "database",
        "urlparser_counters_four",
        (),
    ),
    ScreenshotSet(
        test_settings.SHOOT_REGULAR_REPORT | test_settings.SHOOT_ONE_VARIANT,
        "#view=heat-map",
        "",
        "error",
        "no_test_heat_map",
        (),
    ),
    ScreenshotSet(
        _SHOOT_BOTH_REPORTS,
        "#test=urlparser&view=heat-map"
        "&file=sysdeps/x86_64/multiarch/memchr-avx2.S&line=82"
        "&setting-values=eyJIRUFUX01BUF9DT1VOVEVSX0xJU1RfREVGQVVMVF9TSE9X"
        "Tl9OQU1FUyI6WyJjYWxscyIsIklyIiwiTDFtIiwiTExtIiwiQm0iXX0%3D",
        "",
        "heat_map",
        "line_counters_four",
        (),
    ),
    ScreenshotSet(
        test_settings.SHOOT_REGULAR_REPORT | test_settings.SHOOT_ONE_VARIANT,
        "#view=database",
        "",
        "error",
        "no_test_database",
        (),
    ),
    ScreenshotSet(
        test_settings.SHOOT_REGULAR_REPORT | test_settings.SHOOT_ONE_VARIANT,
        "#view=flame-graph",
        "",
        "error",
        "no_test_flame_graph",
        (),
    ),
    ScreenshotSet(
        test_settings.SHOOT_REGULAR_REPORT,
        "#test=urlparser&view=call-graph",
        "7",
        "call_graph",
        "urlparser",
        (),
    ),
    ScreenshotSet(
        test_settings.SHOOT_REGULAR_REPORT | test_settings.SHOOT_ONE_VARIANT,
        "#view=call-graph",
        "",
        "error",
        "no_test_call_graph",
        (),
    ),
)


class Screenshots:
    def __init__(
        self,
        browser: str,
        report: str,
        report_flag: int,
        out_dir: str,
        compare_dir: str,
        scratch_dir: str,
        trace_path: str,
    ) -> None:
        self.browser = browser
        self.report = report
        self.report_flag = report_flag
        self.out_dir = out_dir
        self.compare_dir = compare_dir
        self.scratch_dir = scratch_dir
        self.trace_path = trace_path
        self.report_views = self.report_views_select()
        self.page_timings: list[PageTiming] = []

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
    def changed_regions(
        self, changed_mask: PIL.Image.Image
    ) -> list[tuple[int, int, int, int]]:
        tile_mask = changed_mask.reduce(test_settings.COMPARE_REGION_TILE_PX)
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
            tile_left = (
                min(region_columns) * test_settings.COMPARE_REGION_TILE_PX
            )
            tile_top = min(region_rows) * test_settings.COMPARE_REGION_TILE_PX
            inner_box = changed_mask.crop(
                (
                    tile_left,
                    tile_top,
                    (max(region_columns) + 1)
                    * test_settings.COMPARE_REGION_TILE_PX,
                    (max(region_rows) + 1)
                    * test_settings.COMPARE_REGION_TILE_PX,
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

    # Returns the commit of a frame a time falls after, minus one for none.
    def commit_index_at(
        self, commit_times: dict[str, list[float]], frame: str, at_time: float
    ) -> int:
        return bisect.bisect_right(commit_times.get(frame, []), at_time) - 1

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
            test_settings.COMPARE_KEPT_BRIGHTNESS_SHARE
        )
        overview_image.paste(
            test_settings.COMPARE_HIGHLIGHT_COLOR, mask=changed_mask
        )
        box_drawing = PIL.ImageDraw.Draw(overview_image)
        label_font = PIL.ImageFont.load_default(
            size=test_settings.COMPARE_LABEL_FONT_PX
        )
        for region_number, (
            region_left,
            region_top,
            region_right,
            region_bottom,
        ) in enumerate(changed_regions, 1):
            box_drawing.rectangle(
                (
                    region_left - test_settings.COMPARE_BOX_LINE_PX,
                    region_top - test_settings.COMPARE_BOX_LINE_PX,
                    region_right - 1 + test_settings.COMPARE_BOX_LINE_PX,
                    region_bottom - 1 + test_settings.COMPARE_BOX_LINE_PX,
                ),
                outline=test_settings.COMPARE_HIGHLIGHT_COLOR,
                width=test_settings.COMPARE_BOX_LINE_PX,
            )
            box_drawing.text(
                (
                    max(region_left - test_settings.COMPARE_BOX_LINE_PX, 0),
                    max(
                        region_top
                        - test_settings.COMPARE_BOX_LINE_PX
                        - test_settings.COMPARE_LABEL_FONT_PX,
                        0,
                    ),
                ),
                str(region_number),
                fill=test_settings.COMPARE_HIGHLIGHT_COLOR,
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
            region_panel = self.region_panel(
                region_number, changed_region, gold_shot, new_shot, label_font
            )
            if (
                panels_height + region_panel.height
                > test_settings.COMPARE_PANELS_MAX_HEIGHT_SHARE
                * new_shot.height
            ):
                continue
            region_panels.append(region_panel)
            panels_height += region_panel.height + test_settings.COMPARE_GAP_PX
        compare_image = PIL.Image.new(
            "RGB",
            (
                max(
                    [overview_image.width]
                    + [region_panel.width for region_panel in region_panels]
                ),
                overview_image.height + panels_height,
            ),
            test_settings.COMPARE_BACKGROUND_COLOR,
        )
        compare_image.paste(overview_image, (0, 0))
        panel_top = overview_image.height
        for region_panel in region_panels:
            compare_image.paste(region_panel, (0, panel_top))
            panel_top += region_panel.height + test_settings.COMPARE_GAP_PX
        os.makedirs(self.compare_dir, exist_ok=True)
        compare_image.save(compare_path)

    # Returns the address of a report's entry page relative to the index.
    def entry_href(self, report_dir: str, index_path: str) -> str:
        return urllib.parse.quote(
            os.path.relpath(
                os.path.join(report_dir, test_settings.ENTRY_PAGE),
                os.path.dirname(index_path),
            )
        )

    # Returns the address the browser opens a file or directory at.
    def file_url(self, path: str) -> str:
        return "file://" + path

    # Names each shot that differs from its gold twin, each one missing.
    def gold_compare(
        self, gold_dir: str, prefix: str, verbose_level: int
    ) -> bool:
        shot_pattern = re.compile(
            f"[0-9]{{{test_settings.SHOT_NUMBER_DIGITS}}}-[^-]+-[^-]+-[^-]+"
            f"-{re.escape(prefix.rstrip('_'))}-.*"
            + re.escape(test_settings.IMAGE_SUFFIX)
        )
        if os.path.isdir(self.compare_dir):
            for file_name in os.listdir(self.compare_dir):
                if file_name.startswith(
                    test_settings.COMPARE_IMAGE_PREFIX
                ) and shot_pattern.fullmatch(
                    file_name.removeprefix(test_settings.COMPARE_IMAGE_PREFIX)
                ):
                    os.remove(os.path.join(self.compare_dir, file_name))
        shot_names = self.shot_names(prefix)
        is_same = True
        for shot_name in shot_names:
            if not self.gold_compare_one(
                shot_name + test_settings.IMAGE_SUFFIX, gold_dir, verbose_level
            ):
                is_same = False
        for file_name in sorted(os.listdir(gold_dir)):
            if (
                shot_pattern.fullmatch(file_name)
                and file_name.removesuffix(test_settings.IMAGE_SUFFIX)
                not in shot_names
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
        self, file_name: str, gold_dir: str, verbose_level: int
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
            if verbose_level:
                verbose_print(verbose_level, [f"{file_name}: same as gold"])
            return True
        changed_mask = channel_change.point(
            lambda channel_value: 255 if channel_value else 0
        )
        changed_count = changed_mask.histogram()[255]
        changed_regions = self.changed_regions(changed_mask)
        compare_path = os.path.join(
            self.compare_dir, test_settings.COMPARE_IMAGE_PREFIX + file_name
        )
        self.compare_image_write(
            new_shot, gold_shot, changed_mask, changed_regions, compare_path
        )
        listed_regions = "; ".join(
            f"{region_left},{region_top} to {region_right},{region_bottom}"
            for region_left, region_top, region_right, region_bottom in (
                changed_regions[: test_settings.COMPARE_LISTED_REGION_COUNT]
            )
        )
        unlisted_count = (
            len(changed_regions) - test_settings.COMPARE_LISTED_REGION_COUNT
        )
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
            f" compare image {compare_path}",
            file=sys.stderr,
        )
        return False

    # Merges this report's pages and timings into the index, keeping others'.
    def index_write(
        self,
        prefix: str,
        index_path: str,
        template: str,
        timing_lines: list[str],
    ) -> None:
        assert template.count(test_settings.INDEX_MARKER) == 1, (
            test_settings.INDEX_MARKER
        )
        report_name = prefix.rstrip("_")
        report_href = self.entry_href(self.report, index_path)
        index_reports: list[dict[str, str]] = []
        for listed_report in test_settings.INDEX_REPORT_NAMES:
            listed_dir = os.path.join(
                os.path.dirname(index_path), listed_report
            )
            if not os.path.isfile(
                os.path.join(listed_dir, test_settings.ENTRY_PAGE)
            ):
                raise RuntimeError(
                    f"{listed_dir} holds no {test_settings.ENTRY_PAGE}"
                )
            index_reports.append(
                {
                    "name": listed_report,
                    "href": self.entry_href(listed_dir, index_path),
                }
            )
        width_px, height_px = test_settings.SCREENSHOT_VIEWPORTS[0][1:]
        pages: dict[str, str] = {}
        page_timings: list[dict[str, str]] = []
        if os.path.isfile(index_path):
            with open(index_path) as index_file:
                found = test_settings.INDEX_DATA_PATTERN.search(
                    index_file.read()
                )
            assert found, f"{index_path} holds no shot list"
            index_data = json.loads(found.group(1))
            if "page_timings" not in index_data:
                raise RuntimeError(f"{index_path} holds no page timings")
            for page in index_data["pages"]:
                if page["report"] != report_name:
                    pages[page["name"]] = page["href"]
            page_timings = [
                page_timing
                for page_timing in index_data["page_timings"]
                if page_timing["report"] != report_name
            ]
        page_timings += [
            {"report": report_name, "line": timing_line}
            for timing_line in timing_lines
        ]
        for view_index, view in self.report_views:
            if (
                view.absent_files
                or view.shot_flags & test_settings.SHOOT_INDEX_PAGE
            ):
                continue
            for toggle_dark_value in dict.fromkeys(
                variant.toggle_dark_value for variant in view.shot_variants()
            ):
                pages[
                    self.shot_name(
                        view_index, "", prefix, view, toggle_dark_value
                    )
                ] = report_href + self.page_address(
                    view.view_hash, view.menu_entry_number, toggle_dark_value
                )
        data = {
            "width": width_px,
            "height": height_px,
            "screenshot_keys": [
                test_settings.SCREENSHOT_LABEL_URL_PARAM,
                test_settings.SCREENSHOT_MENU_URL_PARAM,
            ],
            "pages": [
                {
                    "name": name,
                    "report": name.split(test_settings.SHOT_NAME_SEPARATOR)[
                        -2
                    ],
                    "href": pages[name],
                }
                for name in sorted(pages)
            ],
            "reports": index_reports,
            "page_timings": sorted(
                page_timings, key=lambda page_timing: page_timing["report"]
            ),
        }
        data_script = (
            '<script id="shot-list-" type="application/json">'
            + json.dumps(data, indent=1)
            + "</script>"
        )
        with open(index_path, "w") as index_file:
            index_file.write(
                template.replace(test_settings.INDEX_MARKER, data_script)
            )

    # Returns the query and hash a page is shot at.
    def page_address(
        self, view_hash: str, menu_entry_number: str, toggle_dark_value: str
    ) -> str:
        query_values = {
            test_settings.SCREENSHOT_TOGGLE_DARK_URL_PARAM: toggle_dark_value,
        }
        query_values[test_settings.SCREENSHOT_LABEL_URL_PARAM] = (
            test_settings.SCREENSHOT_LABEL_URL_VALUE
        )
        if menu_entry_number:
            query_values[test_settings.SCREENSHOT_MENU_URL_PARAM] = (
                menu_entry_number
            )
        return "?" + urllib.parse.urlencode(query_values) + view_hash

    # Keeps the longer of the timings of one page file and phase.
    def page_timing_keep(
        self,
        page_timings: dict[tuple[str, str], PageTiming],
        page_timing: PageTiming,
    ) -> None:
        timing_key = (page_timing.page_file, page_timing.phase_name)
        if (
            timing_key not in page_timings
            or page_timing.duration_us > page_timings[timing_key].duration_us
        ):
            page_timings[timing_key] = page_timing

    def page_url(
        self,
        page_dir: str,
        view_hash: str,
        menu_entry_number: str,
        toggle_dark_value: str,
    ) -> str:
        page = (
            page_dir
            if os.path.isfile(page_dir)
            else os.path.join(page_dir, test_settings.ENTRY_PAGE)
        )
        address = self.page_address(
            view_hash, menu_entry_number, toggle_dark_value
        )
        return self.file_url(page) + address

    # Returns whether the outer region holds the whole inner region.
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
    def region_panel(
        self,
        region_number: int,
        changed_region: tuple[int, int, int, int],
        gold_shot: PIL.Image.Image,
        new_shot: PIL.Image.Image,
        label_font: PIL.ImageFont.FreeTypeFont | PIL.ImageFont.ImageFont,
    ) -> PIL.Image.Image:
        region_left, region_top, region_right, region_bottom = changed_region
        crop_box = (
            max(region_left - test_settings.COMPARE_CROP_MARGIN_PX, 0),
            max(region_top - test_settings.COMPARE_CROP_MARGIN_PX, 0),
            min(
                region_right + test_settings.COMPARE_CROP_MARGIN_PX,
                new_shot.width,
            ),
            min(
                region_bottom + test_settings.COMPARE_CROP_MARGIN_PX,
                new_shot.height,
            ),
        )
        crop_width = crop_box[2] - crop_box[0]
        crop_height = crop_box[3] - crop_box[1]
        gold_label = (
            f"{region_number} gold {region_left},{region_top}"
            f" to {region_right},{region_bottom}"
        )
        gold_label_width = int(label_font.getlength(gold_label)) + 1
        column_width = max(crop_width, gold_label_width)
        label_height = (
            test_settings.COMPARE_LABEL_FONT_PX + test_settings.COMPARE_GAP_PX
        )
        new_left = column_width + test_settings.COMPARE_GAP_PX
        region_panel = PIL.Image.new(
            "RGB",
            (new_left + column_width, label_height + crop_height),
            test_settings.COMPARE_BACKGROUND_COLOR,
        )
        region_panel.paste(gold_shot.crop(crop_box), (0, label_height))
        region_panel.paste(new_shot.crop(crop_box), (new_left, label_height))
        panel_drawing = PIL.ImageDraw.Draw(region_panel)
        panel_drawing.text(
            (0, 0),
            gold_label,
            fill=test_settings.COMPARE_LABEL_COLOR,
            font=label_font,
        )
        panel_drawing.text(
            (new_left, 0),
            f"{region_number} new",
            fill=test_settings.COMPARE_LABEL_COLOR,
            font=label_font,
        )
        return region_panel

    # Returns the file an address names under a root, empty outside that.
    def relative_file_of(self, url: str, root_url: str) -> str:
        split_url = urllib.parse.urlsplit(url)
        split_root = urllib.parse.urlsplit(root_url)
        url_place = (split_url.scheme, split_url.netloc.lower())
        root_place = (split_root.scheme, split_root.netloc.lower())
        url_path = urllib.parse.unquote(split_url.path)
        root_path = urllib.parse.unquote(split_root.path) + "/"
        if url_place != root_place or not url_path.startswith(root_path):
            return ""
        return url_path.removeprefix(root_path)

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
            if view.shot_flags & test_settings.SHOOT_INDEX_PAGE:
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
            if view.shot_flags & test_settings.SHOOT_INDEX_PAGE:
                written += self.view_shoot(
                    index_path, view_index, prefix, view
                )
        return written

    # Shoots a page, writing its trace too when a trace path is given.
    def shoot_one(
        self,
        shot: str,
        page_dir: str,
        view_hash: str,
        menu_entry_number: str,
        toggle_dark_value: str,
        width_px: int,
        height_px: int,
        trace_path: str,
    ) -> None:
        out_path = os.path.join(
            self.out_dir, shot + test_settings.IMAGE_SUFFIX
        )
        if os.path.exists(out_path):
            os.remove(out_path)
        assert self.browser, "a compare only run shoots nothing"
        window = f"{width_px},{height_px}"
        trace_flags: list[str] = []
        if trace_path:
            if os.path.exists(trace_path):
                os.remove(trace_path)
            trace_flags = [
                f"--trace-startup={test_settings.TRACE_CATEGORIES}",
                f"--trace-startup-file={trace_path}",
                f"--trace-startup-format={test_settings.TRACE_FORMAT}",
                # Zero traces until the browser exits after the shot.
                "--trace-startup-duration=0",
            ]
        result = subprocess.run(
            [
                self.browser,
                "--disable-gpu",
                "--no-sandbox",
                "--hide-scrollbars",
                "--incognito",
                # Draws a frame only after the page's own work for it.
                "--run-all-compositor-stages-before-draw",
                f"--window-size={window}",
                f"--screenshot={out_path}",
                "--virtual-time-budget="
                f"{test_settings.SCREENSHOT_RENDER_BUDGET_MS}",
                *trace_flags,
                self.page_url(
                    page_dir, view_hash, menu_entry_number, toggle_dark_value
                ),
            ],
            capture_output=True,
            text=True,
        )
        if os.path.exists(out_path) and os.path.getsize(out_path):
            return
        raise RuntimeError(
            f"{shot}: {view_hash or '(entry page)'} wrote no image:"
            f" {result.stderr.strip()[-test_settings.FAULT_TAIL_CHARS :]}"
        )

    # Names a shot, leaving out the resolution when the size is empty.
    def shot_name(
        self,
        view_index: int,
        size_name: str,
        prefix: str,
        view: ScreenshotSet,
        toggle_dark_value: str,
    ) -> str:
        return test_settings.SHOT_NAME_SEPARATOR.join(
            name_part
            for name_part in (
                f"{view_index:0{test_settings.SHOT_NUMBER_DIGITS}d}",
                size_name,
                view.view_name,
                view.subview_name,
                prefix.rstrip("_"),
                test_settings.SHOT_MODE_NAME_PARTS[toggle_dark_value],
            )
            if name_part
        )

    # Names every shot of this report, the index page's too.
    def shot_names(self, prefix: str) -> list[str]:
        return [
            self.shot_name(
                view_index,
                variant.size_name,
                prefix,
                view,
                variant.toggle_dark_value,
            )
            for view_index, view in self.report_views
            for variant in view.shot_variants()
        ]

    # Returns each page file's slowest load, then its largest phases.
    def timing_lines(self) -> list[str]:
        largest_timings: dict[tuple[str, str], PageTiming] = {}
        for page_timing in self.page_timings:
            self.page_timing_keep(largest_timings, page_timing)
        file_timings: dict[str, list[PageTiming]] = {}
        for page_timing in sorted(
            largest_timings.values(),
            key=lambda page_timing: (
                page_timing.phase_name != test_settings.TIMING_LOAD_PHASE_NAME,
                -page_timing.duration_us,
            ),
        ):
            file_timings.setdefault(page_timing.page_file, []).append(
                page_timing
            )
        kept_lines: list[str] = []
        for page_file, page_file_timings in sorted(
            file_timings.items(),
            key=lambda file_entry: -file_entry[1][0].duration_us,
        ):
            for page_timing in page_file_timings[
                : test_settings.TIMING_FILE_LINES_MAX
            ]:
                duration_ms = (
                    page_timing.duration_us
                    / test_settings.TIMING_MICROSECONDS_PER_MILLISECOND
                )
                kept_lines.append(
                    f"{page_file}: {page_timing.phase_label}"
                    f" {duration_ms:.1f} ms, {page_timing.shot}"
                )
        return kept_lines

    # Returns the longest load and phase slice of each page file a trace shows.
    def trace_page_timings(
        self, trace_events: list[Any], root_url: str, shot: str
    ) -> list[PageTiming]:
        timed_events = [
            trace_event
            for trace_event in trace_events
            if trace_event["ph"] in test_settings.TRACE_SLICE_TYPES
            or trace_event["name"] in test_settings.TRACE_MARK_NAMES
        ]
        timed_events.sort(key=lambda trace_event: trace_event["ts"])
        commit_times: dict[str, list[float]] = {}
        commit_files: dict[str, list[str]] = {}
        load_marks: list[tuple[str, float]] = []
        phase_slices: list[tuple[Any, float]] = []
        begun_slices: dict[tuple[int, int], list[Any]] = {}
        for trace_event in timed_events:
            event_type = trace_event["ph"]
            thread = (trace_event["pid"], trace_event["tid"])
            if event_type == test_settings.TRACE_END_TYPE:
                begun_event = begun_slices[thread].pop()
                if begun_event["name"] in test_settings.TRACE_PHASES:
                    phase_slices.append(
                        (begun_event, trace_event["ts"] - begun_event["ts"])
                    )
                continue
            if event_type == test_settings.TRACE_BEGIN_TYPE:
                begun_slices.setdefault(thread, []).append(trace_event)
            elif (
                event_type == test_settings.TRACE_COMPLETE_TYPE
                and trace_event["name"] in test_settings.TRACE_PHASES
            ):
                phase_slices.append((trace_event, trace_event["dur"]))
            if trace_event["name"] == test_settings.TRACE_COMMIT_NAME:
                commit_data = trace_event["args"]["data"]
                commit_times.setdefault(commit_data["frame"], []).append(
                    trace_event["ts"]
                )
                commit_files.setdefault(commit_data["frame"], []).append(
                    self.relative_file_of(commit_data["url"], root_url)
                )
            elif trace_event["name"] == test_settings.TRACE_LOAD_NAME:
                load_marks.append(
                    (trace_event["args"]["data"]["frame"], trace_event["ts"])
                )
        page_timings: dict[tuple[str, str], PageTiming] = {}
        loaded_commits: set[tuple[str, int]] = set()
        for frame, load_time in load_marks:
            commit_index = self.commit_index_at(commit_times, frame, load_time)
            if commit_index < 0 or (frame, commit_index) in loaded_commits:
                continue
            loaded_commits.add((frame, commit_index))
            if not commit_files[frame][commit_index]:
                continue
            self.page_timing_keep(
                page_timings,
                PageTiming(
                    commit_files[frame][commit_index],
                    test_settings.TIMING_LOAD_PHASE_NAME,
                    test_settings.TIMING_LOAD_PHASE_NAME,
                    load_time - commit_times[frame][commit_index],
                    shot,
                ),
            )
        for begun_event, duration_us in phase_slices:
            phase_name, data_key = test_settings.TRACE_PHASES[
                begun_event["name"]
            ]
            slice_data = begun_event["args"][data_key]
            frame = slice_data["frame"]
            commit_index = self.commit_index_at(
                commit_times, frame, begun_event["ts"]
            )
            if commit_index < 0 or not commit_files[frame][commit_index]:
                continue
            if (
                begun_event["name"] == test_settings.TRACE_FUNCTION_CALL_NAME
                and slice_data["scriptId"] == test_settings.TRACE_NO_SCRIPT_ID
            ):
                continue
            phase_label = phase_name
            if phase_name == test_settings.TIMING_SCRIPT_PHASE_NAME:
                script_file = self.relative_file_of(
                    slice_data["url"], root_url
                )
                if not script_file:
                    raise ValueError(
                        f"{begun_event['name']} runs {slice_data['url']!r}"
                        f" outside {root_url}"
                    )
                phase_label = f"{phase_name} {script_file}"
            self.page_timing_keep(
                page_timings,
                PageTiming(
                    commit_files[frame][commit_index],
                    phase_name,
                    phase_label,
                    duration_us,
                    shot,
                ),
            )
        return list(page_timings.values())

    # Returns each report page's load and largest phase slices in a trace.
    def trace_timings(
        self, trace_path: str, page_dir: str, shot: str
    ) -> list[PageTiming]:
        if not os.path.isfile(trace_path):
            raise RuntimeError(f"{shot}: the browser wrote no {trace_path}")
        with open(trace_path) as trace_file:
            trace_text = trace_file.read()
        try:
            page_timings = self.trace_page_timings(
                json.loads(trace_text)["traceEvents"],
                self.file_url(page_dir),
                shot,
            )
        except (IndexError, KeyError, TypeError, ValueError) as error:
            raise RuntimeError(f"{trace_path}: {error!r}") from error
        if not any(
            page_timing.page_file == test_settings.ENTRY_PAGE
            and page_timing.phase_name == test_settings.TIMING_LOAD_PHASE_NAME
            for page_timing in page_timings
        ):
            raise RuntimeError(
                f"{trace_path}: no {test_settings.TRACE_LOAD_NAME} of"
                f" {test_settings.ENTRY_PAGE} after"
                f" its {test_settings.TRACE_COMMIT_NAME}"
            )
        os.remove(trace_path)
        return page_timings

    def view_shoot(
        self,
        page_dir: str,
        view_index: int,
        prefix: str,
        view: ScreenshotSet,
    ) -> int:
        shot_variants = view.shot_variants()
        # The index page frames report pages, so only the report shots trace.
        trace_path = (
            ""
            if view.shot_flags & test_settings.SHOOT_INDEX_PAGE
            else self.trace_path
        )
        for variant in shot_variants:
            shot = self.shot_name(
                view_index,
                variant.size_name,
                prefix,
                view,
                variant.toggle_dark_value,
            )
            self.shoot_one(
                shot,
                page_dir,
                view.view_hash,
                view.menu_entry_number,
                variant.toggle_dark_value,
                variant.width_px,
                variant.height_px,
                trace_path,
            )
            if trace_path:
                self.page_timings += self.trace_timings(
                    trace_path, page_dir, shot
                )
        return len(shot_variants)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", help="a report directory to shoot")
    parser.add_argument("prefix", help="what every file name starts with")
    parser.add_argument("--browser", default="", metavar="PATH")
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
        f" tests/perf2html/{test_settings.SCREENSHOT_DIR_NAME})",
    )
    parser.add_argument(
        "--verbose",
        action="count",
        default=0,
        help="print where the shots go and how many; a quiet run prints"
        " nothing on success",
    )
    namespace = parser.parse_args()

    report = os.path.abspath(namespace.report)
    if not os.path.isfile(os.path.join(report, test_settings.ENTRY_PAGE)):
        print(
            f"error: {report} holds no {test_settings.ENTRY_PAGE}",
            file=sys.stderr,
        )
        return 2

    gold_dir = os.path.abspath(namespace.compare_gold)
    if namespace.compare_gold and not os.path.isdir(gold_dir):
        print(
            f"error: --compare-gold {gold_dir} is no directory",
            file=sys.stderr,
        )
        return 2

    if namespace.compare_out and not namespace.compare_gold:
        print("error: --compare-out needs --compare-gold", file=sys.stderr)
        return 2

    if namespace.compare_only and not namespace.compare_gold:
        print("error: --compare-only needs --compare-gold", file=sys.stderr)
        return 2

    if not namespace.browser and not namespace.compare_only:
        print("error: shooting needs --browser", file=sys.stderr)
        return 2

    perf2html_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".."
    )
    out_dir = namespace.out or os.path.join(
        perf2html_dir, test_settings.SCREENSHOT_DIR_NAME
    )
    out_dir = os.path.abspath(out_dir)
    scratch_dir = os.path.abspath(
        os.path.join(perf2html_dir, test_settings.SCREENSHOT_SCRATCH_DIR_PATH)
    )
    trace_path = os.path.abspath(
        os.path.join(perf2html_dir, test_settings.SCREENSHOT_TRACE_FILE_PATH)
    )

    report_flag = (
        test_settings.SHOOT_DIFF_REPORT
        if namespace.diff
        else test_settings.SHOOT_REGULAR_REPORT
    )
    compare_dir = os.path.abspath(namespace.compare_out or out_dir)
    shooter = Screenshots(
        namespace.browser,
        report,
        report_flag,
        out_dir,
        compare_dir,
        scratch_dir,
        trace_path,
    )
    if namespace.compare_only:
        is_same = shooter.gold_compare(
            gold_dir, namespace.prefix, namespace.verbose
        )
        return 0 if is_same else 1

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(trace_path), exist_ok=True)
    if namespace.verbose:
        verbose_print(
            namespace.verbose, [f"{os.path.basename(report)} -> {out_dir}"]
        )
    written = shooter.shoot_all(namespace.prefix)
    timing_lines = shooter.timing_lines()

    with open(
        os.path.join(
            perf2html_dir, "scripts", test_settings.INDEX_TEMPLATE_NAME
        )
    ) as template_file:
        index_template = template_file.read()
    shooter.index_write(
        namespace.prefix,
        os.path.join(perf2html_dir, test_settings.INDEX_PAGE_NAME),
        index_template,
        timing_lines,
    )
    written += shooter.index_shoot(
        namespace.prefix,
        os.path.join(perf2html_dir, test_settings.INDEX_PAGE_NAME),
    )
    if namespace.verbose:
        verbose_print(namespace.verbose, [f"{written} screenshot(s)"])
    if namespace.compare_gold and not shooter.gold_compare(
        gold_dir, namespace.prefix, namespace.verbose
    ):
        return 1
    if namespace.verbose:
        verbose_print(namespace.verbose, timing_lines)
    return 0


# Prints success lines, below the raw level as one Markdown text block.
def verbose_print(verbose_level: int, lines: list[str]) -> None:
    if verbose_level >= test_settings.VERBOSE_RAW_LEVEL:
        print("\n".join(lines), flush=True)
        return
    mark_run = max(
        (
            len(marks)
            for line in lines
            for marks in re.findall(
                f"{test_settings.MARKDOWN_FENCE_MARK}+", line
            )
        ),
        default=0,
    )
    fence = test_settings.MARKDOWN_FENCE_MARK * max(
        test_settings.MARKDOWN_FENCE_MIN_MARKS, mark_run + 1
    )
    fenced_lines = [fence + test_settings.MARKDOWN_FENCE_INFO, *lines, fence]
    print("\n" + "\n".join(fenced_lines), flush=True)


if __name__ == "__main__":
    sys.exit(main())
