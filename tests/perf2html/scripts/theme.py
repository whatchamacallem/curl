# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import json, math, os, re
from collections.abc import Sequence
from typing import NamedTuple, TypeAlias

import settings

_ASSET_CALLERS_SCRIPT_NAME: str = ""
_ASSET_DARK_MODE_STYLESHEET_NAME: str = ""
_ASSET_DEBUG_SCRIPT_NAME: str = ""
_ASSET_ERROR_OVERLAY_SCRIPT_NAME: str = ""
_ASSET_FLAME_GRAPH_SCRIPT_NAME: str = ""
_ASSET_FRAME_SCRIPT_NAME: str = ""
_ASSET_HEAT_MAP_SCRIPT_NAME: str = ""
_ASSET_HEAT_MAP_STYLESHEET_NAME: str = ""
_ASSET_LIGHT_MODE_STYLESHEET_NAME: str = ""
_ASSET_MENU_SCRIPT_NAME: str = ""
_ASSET_MENU_STYLESHEET_NAME: str = ""
_ASSET_SETTINGS_PAGE_SCRIPT_NAME: str = ""
_ASSET_SETTINGS_SCRIPT_NAME: str = ""
_ASSET_THEME_SCRIPT_NAME: str = ""
_ASSET_THEME_STYLESHEET_NAME: str = ""
_ASSET_UI_STRINGS_SCRIPT_NAME: str = ""
_ASSET_UTILITY_SCRIPT_NAME: str = ""
_DARK_MODE_ATTRIBUTE_NAME: str = ""
_DARK_MODE_DISABLED_VALUE: str = ""
_NUMBER_FRACTION_DIGITS: int = 0
_NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES: float = 0.0
_REPORT_ASSETS_DIR_NAME: str = ""
_STYLE_COLOR_DARK_MODE: dict[str, list[str]] = {}
_STYLE_COLOR_DARK_MODE_ROLE_PREFIX: str = ""
_STYLE_COLOR_LIGHT_MODE: dict[str, list[str]] = {}
_STYLE_COLOR_LIGHT_MODE_ROLE_PREFIX: str = ""
_STYLE_DESIGN_DEVICE_PIXEL_WIDEST_PROPERTY: str = ""
_STYLE_DESIGN_FONT_FIT_PROPERTY: str = ""
_STYLE_DESIGN_FONT_SIZE_PROPERTY: str = ""
_STYLE_DESIGN_SCALE_DEFAULT_MULTIPLE: int = 0
_STYLE_DESIGN_SCALE_LARGEST_MULTIPLE: int = 0
_STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE: float = 0.0
_STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY: str = ""
_STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE: float = 0.0
_STYLE_HEAT_CELL_ON_BRIGHT_ROLE: str = ""
_STYLE_HEAT_CELL_ON_DARK_ROLE: str = ""
_STYLE_HEAT_COLOR_FULL_SCALE_PERCENT: int = 0
_STYLE_HEAT_COLOR_STOPS: list[str] = []
_STYLE_HEAT_MAP_SOURCE_LINE_NUMBER_MARKER_WIDTH_PROPERTY: str = ""
_STYLE_PAGE_FONT_FAMILY_PROPERTY: str = ""
_STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS: int = 0
_STYLE_TABLE_GROW_COLUMN_NARROWEST_CHARS: int = 0
_STYLE_VALUE_ENTRIES: dict[str, str] = {}
_THEME_TIME_UNIT_ENTRIES: tuple[tuple[str, float], ...] = ()
settings.load_into(__name__)

if not (
    _STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE
    < _STYLE_DESIGN_SCALE_DEFAULT_MULTIPLE
    < _STYLE_DESIGN_SCALE_LARGEST_MULTIPLE
):
    raise ValueError(
        "STYLE_DESIGN_SCALE_* out of order: smallest"
        f" {_STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE}, default"
        f" {_STYLE_DESIGN_SCALE_DEFAULT_MULTIPLE}, largest"
        f" {_STYLE_DESIGN_SCALE_LARGEST_MULTIPLE}"
    )

_DARK_MODE_ENABLED_SELECTOR = (
    f':root:not([{_DARK_MODE_ATTRIBUTE_NAME}="{_DARK_MODE_DISABLED_VALUE}"])'
)

_MENU_BUTTON_KIND_NAMES = ("action", "link")

_UI_STRINGS_BLOCK = re.compile(r"\n  const STRINGS = \{\n(.*?)\n  \};\n", re.S)

_UI_STRINGS_ENTRY = re.compile(r'\s*(str_\w+):\s*("(?:[^"\\\n]|\\.)*"),')

_UI_TEXT_MARKER = re.compile(r"\{(\w+)\}")


class Cell(NamedTuple):
    text: str = ""
    html: str | None = None
    style: str = ""


CellOrText: TypeAlias = Cell | str


class Column(NamedTuple):
    label: str
    numeric: bool = False
    width: int | None = None
    grow: bool = False


class ColumnExtent(NamedTuple):
    heading_chars: int
    content_chars: int


class MenuButtonFields(NamedTuple):
    tag_name: str
    href: str = ""
    opens_new_tab: bool = False


class TableRenderer:
    def cell(self, value: CellOrText) -> Cell:
        return value if isinstance(value, Cell) else Cell(text=value)

    def column_extents(
        self,
        columns: Sequence[Column],
        rows: Sequence[Sequence[Cell]],
        grow_index: int,
    ) -> list[ColumnExtent]:
        extents: list[ColumnExtent] = []
        for index, column in enumerate(columns):
            if column.width is not None:
                content_chars = column.width
            elif index == grow_index:
                content_chars = _STYLE_TABLE_GROW_COLUMN_NARROWEST_CHARS
            else:
                content_chars = self.column_longest(rows, index)
            extents.append(ColumnExtent(len(column.label), content_chars))
        return extents

    def column_limits(self, extent: ColumnExtent) -> tuple[int, int]:
        widest = max(extent.heading_chars, extent.content_chars)
        return (
            extent.content_chars,
            widest + _STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS,
        )

    def column_longest(
        self, rows: Sequence[Sequence[Cell]], index: int
    ) -> int:
        return max((len(row[index].text) for row in rows), default=0)

    def column_width_text(
        self, limits: Sequence[tuple[int, int]], index: int, grow_index: int
    ) -> str:
        narrowest, widest = limits[index]
        shared = [
            limit for other, limit in enumerate(limits) if other != grow_index
        ]
        low_total = sum(limit[0] for limit in shared)
        high_total = sum(limit[1] for limit in shared)
        if index == grow_index:
            return (
                f"max({narrowest}ch, 100cqw - clamp({low_total}ch, "
                f"100cqw - {narrowest}ch, {high_total}ch))"
            )
        if narrowest == widest:
            return f"{narrowest}ch"
        grow_narrowest = limits[grow_index][0] if grow_index >= 0 else 0
        return (
            f"clamp({narrowest}ch, {narrowest}ch + (100cqw - "
            f"{low_total + grow_narrowest}ch) * {widest - narrowest} / "
            f"{high_total - low_total}, {widest}ch)"
        )

    def numeric_attributes(self, column: Column) -> dict[str, str]:
        return {"class": "numeric-"} if column.numeric else {}

    def table(
        self,
        key: str,
        columns: Sequence[Column],
        rows: Sequence[Sequence[CellOrText]],
        fill: bool = False,
        column_titles: bool = True,
    ) -> str:
        cells = [[self.cell(value) for value in row] for row in rows]
        for row in cells:
            if len(row) != len(columns):
                raise ValueError(
                    f"table {key!r}: a row has {len(row)} cells "
                    f"for {len(columns)} columns"
                )
        grow_index = -1
        if fill:
            grow_index = next(
                (index for index, column in enumerate(columns) if column.grow),
                -1,
            )
            if grow_index < 0:
                raise ValueError(f"table {key!r}: fill but no grow column")
        extents = self.column_extents(columns, cells, grow_index)
        limits = [self.column_limits(extent) for extent in extents]
        column_markup = "".join(
            element_render(
                "col",
                {
                    "data-min-": f"{limit[0]}ch",
                    "style": "width:"
                    + self.column_width_text(limits, index, grow_index),
                },
                None,
            )
            for index, limit in enumerate(limits)
        )
        title_markup = (
            element_render(
                "thead",
                {},
                element_render(
                    "tr",
                    {},
                    "".join(
                        element_render(
                            "th",
                            self.numeric_attributes(column)
                            | {"title": column.label},
                            html_escape(column.label),
                        )
                        for column in columns
                    ),
                ),
            )
            if column_titles
            else ""
        )
        body_markup = "".join(
            element_render(
                "tr",
                {},
                "".join(
                    self.table_cell_render(cell, column)
                    for column, cell in zip(columns, row, strict=True)
                ),
            )
            for row in cells
        )
        return element_render(
            "div",
            {"class": "table-box-"},
            element_render(
                "div",
                {"class": "table-columns-"},
                element_render(
                    "table",
                    {"class": "columns-", "data-key-": key},
                    element_render("colgroup", {}, column_markup)
                    + title_markup
                    + element_render("tbody", {}, body_markup),
                ),
            ),
        )

    def table_cell_render(self, cell: Cell, column: Column) -> str:
        cell_attributes = self.numeric_attributes(column)
        if cell.style:
            cell_attributes["style"] = cell.style
        return element_render(
            "td",
            cell_attributes,
            cell.html if cell.html is not None else html_escape(cell.text),
        )


class Theme:
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))

    class NumberFormat:
        def __init__(self, time_units: tuple[Theme.TimeUnit, ...]) -> None:
            self.signed_percent_amount_chars = len(
                self.fixed_text(-100, _NUMBER_FRACTION_DIGITS) + "%"
            )
            self.smallest_printed_percent = 1 / 10**_NUMBER_FRACTION_DIGITS
            self.time_units = time_units

        def diff_share_of(self, delta: int, baseline: int | None) -> float:
            baseline_count = 0 if baseline is None else baseline
            if delta < -baseline_count:
                raise ValueError(
                    f"a change of {delta} falls past its baseline of "
                    f"{baseline_count}"
                )
            if delta == 0:
                return 0.0
            if baseline_count == 0:
                return math.inf
            return 100.0 * delta / baseline_count

        def fixed_text(self, value: float, digit_count: int) -> str:
            whole = self.rounded_units(value, digit_count)
            sign = "-" if value < 0 and whole else ""
            digits = str(whole).rjust(digit_count + 1, "0")
            if not digit_count:
                return sign + digits
            split_at = len(digits) - digit_count
            return sign + digits[:split_at] + "." + digits[split_at:]

        def human(self, number: float) -> str:
            value, unit = float(number), ""
            for candidate in ("K", "M", "G", "T"):
                if value < 999.5:
                    break
                value /= 1000
                unit = candidate
            digit_count = 1 if unit and value < 9.95 else 0
            return self.fixed_text(value, digit_count) + unit

        def percent(self, percent: float) -> str:
            digit_count = _NUMBER_FRACTION_DIGITS
            if percent >= self.smallest_printed_percent:
                return self.fixed_text(percent, digit_count) + "%"
            if percent > 0:
                return "≈" + self.fixed_text(0, digit_count) + "%"
            return ""

        def rounded_units(self, value: float, digit_count: int) -> int:
            scaled = abs(value) * 10.0**digit_count
            whole = math.floor(scaled)
            return whole + 1 if scaled - whole >= 0.5 else whole

        def signed(self, number: float) -> str:
            if number == 0:
                return ""
            return ("-" if number < 0 else "") + self.human(abs(number))

        def signed_percent(self, percent: float, is_line: bool = False) -> str:
            digit_count = _NUMBER_FRACTION_DIGITS
            if percent == 0:
                return "" if is_line else self.fixed_text(0, digit_count) + "%"
            arrow = "▼" if percent < 0 else "▲"
            times = percent / 100
            if percent == math.inf:
                amount_text = "∞%"
            elif abs(percent) < self.smallest_printed_percent:
                amount_text = "≈" + self.fixed_text(0, digit_count) + "%"
            elif percent <= 100:
                amount_text = self.fixed_text(percent, digit_count) + "%"
            elif times >= _NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES:
                amount_text = "≈∞%"
            else:
                amount_text = self.fixed_text(times, digit_count) + "x"
            if not is_line:
                return arrow + amount_text
            return arrow + amount_text.rjust(self.signed_percent_amount_chars)

        def time(self, seconds: float) -> str:
            digit_count = _NUMBER_FRACTION_DIGITS
            if seconds == 0:
                return self.fixed_text(0, digit_count) + "s"
            sign = "-" if seconds < 0 else ""
            magnitude = abs(seconds)
            unit = next(
                (
                    candidate
                    for candidate in self.time_units
                    if magnitude >= candidate.seconds
                ),
                self.time_units[-1],
            )
            return (
                sign
                + self.fixed_text(magnitude / unit.seconds, digit_count)
                + unit.suffix
            )

    class Rgb(NamedTuple):
        red: int
        green: int
        blue: int

    class TimeUnit(NamedTuple):
        suffix: str
        seconds: float

    def __init__(self) -> None:
        self.color_roles = self.roles(
            "STYLE_COLOR_DARK_MODE",
            _STYLE_COLOR_DARK_MODE,
            _STYLE_COLOR_DARK_MODE_ROLE_PREFIX,
        )
        self.light_mode_roles = self.roles(
            "STYLE_COLOR_LIGHT_MODE",
            _STYLE_COLOR_LIGHT_MODE,
            _STYLE_COLOR_LIGHT_MODE_ROLE_PREFIX,
        )
        self.heat_stops = [
            self.rgb(color) for color in _STYLE_HEAT_COLOR_STOPS
        ]
        self.number_format = Theme.NumberFormat(self.time_units())
        self.ui_strings = self.ui_strings_read()

    def asset_read(self, name: str) -> str:
        with open(
            os.path.join(self.DIRECTORY, name), encoding="utf-8"
        ) as handle:
            return handle.read()

    def assets_write(self, out_dir: str) -> None:
        self.root_value_names_check()
        os.makedirs(out_dir, exist_ok=True)
        heat_map_script = _ASSET_HEAT_MAP_SCRIPT_NAME
        heat_map_stylesheet = _ASSET_HEAT_MAP_STYLESHEET_NAME
        shared = (
            (
                _ASSET_CALLERS_SCRIPT_NAME,
                self.asset_read(_ASSET_CALLERS_SCRIPT_NAME),
            ),
            (
                _ASSET_LIGHT_MODE_STYLESHEET_NAME,
                self.asset_read(_ASSET_LIGHT_MODE_STYLESHEET_NAME),
            ),
            (
                _ASSET_DARK_MODE_STYLESHEET_NAME,
                self.mode_stylesheet_read(
                    _ASSET_DARK_MODE_STYLESHEET_NAME,
                    _DARK_MODE_ENABLED_SELECTOR,
                ),
            ),
            (
                _ASSET_ERROR_OVERLAY_SCRIPT_NAME,
                self.asset_read(_ASSET_ERROR_OVERLAY_SCRIPT_NAME),
            ),
            (
                _ASSET_FLAME_GRAPH_SCRIPT_NAME,
                self.asset_read(_ASSET_FLAME_GRAPH_SCRIPT_NAME),
            ),
            (
                _ASSET_FRAME_SCRIPT_NAME,
                self.asset_read(_ASSET_FRAME_SCRIPT_NAME),
            ),
            (heat_map_stylesheet, self.asset_read(heat_map_stylesheet)),
            (heat_map_script, self.asset_read(heat_map_script)),
            (
                _ASSET_MENU_SCRIPT_NAME,
                self.asset_read(_ASSET_MENU_SCRIPT_NAME),
            ),
            (
                _ASSET_MENU_STYLESHEET_NAME,
                self.asset_read(_ASSET_MENU_STYLESHEET_NAME),
            ),
            (
                _ASSET_SETTINGS_PAGE_SCRIPT_NAME,
                self.asset_read(_ASSET_SETTINGS_PAGE_SCRIPT_NAME),
            ),
            (
                _ASSET_SETTINGS_SCRIPT_NAME,
                settings.settings_script_write(),
            ),
            (
                _ASSET_THEME_STYLESHEET_NAME,
                self.asset_read(_ASSET_THEME_STYLESHEET_NAME),
            ),
            (_ASSET_THEME_SCRIPT_NAME, self.js()),
            (
                _ASSET_UI_STRINGS_SCRIPT_NAME,
                self.asset_read(_ASSET_UI_STRINGS_SCRIPT_NAME),
            ),
            (
                _ASSET_UTILITY_SCRIPT_NAME,
                self.asset_read(_ASSET_UTILITY_SCRIPT_NAME),
            ),
        )
        for name, text in shared:
            with open(
                os.path.join(out_dir, name), "w", encoding="utf-8"
            ) as handle:
                handle.write(text)

    def contrast_foreground(
        self, color: Theme.Rgb, on_dark_role: str, on_bright_role: str
    ) -> str:
        role = (
            on_bright_role
            if self.luminance(color)
            > _STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE
            else on_dark_role
        )
        if role not in self.color_roles:
            raise ValueError(f"{role} is no role of the dark palette")
        return f"var(--{role})"

    def document(
        self,
        title: str,
        body: str,
        extra_js: Sequence[str] = (),
        body_class: str = "",
        depth: int = 0,
        extra_css: Sequence[str] = (),
        body_holds_scripts: bool = False,
    ) -> str:
        assets_href = shared_href(depth, _REPORT_ASSETS_DIR_NAME)
        body_attributes = {"class": body_class} if body_class else {}
        html_attributes = {"lang": self.ui_text_of("str_page_language")}
        head_names = page_preamble_scripts()
        head_links = "".join(
            element_render(
                "link",
                {"rel": "stylesheet", "href": f"{assets_href}/{name}"},
                None,
            )
            + "\n"
            for name in (
                _ASSET_THEME_STYLESHEET_NAME,
                *extra_css,
                _ASSET_LIGHT_MODE_STYLESHEET_NAME,
                _ASSET_DARK_MODE_STYLESHEET_NAME,
            )
        )
        # A page below the report root is a framed view, its settings relayed.
        if body_holds_scripts:
            script = ""
        elif depth:
            script = held_script_tags(
                script_tags(
                    assets_href,
                    (
                        _ASSET_DEBUG_SCRIPT_NAME,
                        _ASSET_THEME_SCRIPT_NAME,
                        *extra_js,
                    ),
                )
            )
        else:
            html_attributes["data-top-page-"] = ""
            script = script_tags(
                assets_href,
                (
                    _ASSET_DEBUG_SCRIPT_NAME,
                    _ASSET_THEME_SCRIPT_NAME,
                    *extra_js,
                ),
            )
        head_scripts = script_tags(assets_href, head_names)
        head_markup = (
            "\n"
            + element_render("meta", {"charset": "utf-8"}, None)
            + "\n"
            + head_scripts
            + element_render(
                "meta",
                {
                    "name": "viewport",
                    "content": "width=device-width, initial-scale=1",
                },
                None,
            )
            + "\n"
            + element_render("title", {}, html_escape(title))
            + "\n"
            + head_links
        )
        page_markup = element_render(
            "html",
            html_attributes,
            "\n"
            + element_render("head", {}, head_markup)
            + "\n"
            + element_render("body", body_attributes, f"\n{body}\n{script}")
            + "\n",
        )
        return f"<!doctype html>\n{page_markup}\n"

    def heat_of_share(self, percent: float) -> float:
        sign = -1.0 if percent < 0 else 1.0
        full_scale = float(_STYLE_HEAT_COLOR_FULL_SCALE_PERCENT)
        magnitude = min(abs(percent), full_scale)
        if magnitude <= 0:
            return 0.0
        fraction = magnitude / full_scale
        return sign * math.log10(1 + 9 * fraction)

    def heat_style(self, heat: float, signed: bool = False) -> str:
        if abs(heat) <= 0:
            return ""
        stops = self.heat_stops
        if signed:
            position = (heat + 1) * 0.5 * (len(stops) - 1)
        else:
            position = heat * (len(stops) - 1)
        index = min(max(int(position), 0), len(stops) - 2)
        fraction = position - index
        mixed = Theme.Rgb(
            *(
                round(
                    stops[index][channel]
                    + (stops[index + 1][channel] - stops[index][channel])
                    * fraction
                )
                for channel in range(3)
            )
        )
        return (
            f"background:rgb({mixed.red},{mixed.green},{mixed.blue});"
            "color:"
            + self.contrast_foreground(
                mixed,
                _STYLE_HEAT_CELL_ON_DARK_ROLE,
                _STYLE_HEAT_CELL_ON_BRIGHT_ROLE,
            )
        )

    def js(self) -> str:
        return self.asset_read(_ASSET_THEME_SCRIPT_NAME)

    def luminance(self, color: Theme.Rgb) -> float:
        return (
            0.2126 * color.red + 0.7152 * color.green + 0.0722 * color.blue
        ) / 255

    def mode_stylesheet_read(self, name: str, selector: str) -> str:
        stylesheet_text = self.asset_read(name)
        if selector not in stylesheet_text:
            raise ValueError(f"{name} never names {selector}")
        return stylesheet_text

    def reads_check(self, stylesheet_text: str, names: set[str]) -> None:
        for name in re.findall(r"var\((--[\w-]+)", stylesheet_text):
            if name not in names:
                raise ValueError(f"a stylesheet reads {name}, not set for it")

    def rgb(self, hex_color: str) -> Theme.Rgb:
        return Theme.Rgb(
            int(hex_color[1:3], 16),
            int(hex_color[3:5], 16),
            int(hex_color[5:7], 16),
        )

    def roles(
        self,
        palette_name: str,
        palette: dict[str, list[str]],
        role_prefix: str,
    ) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for color, roles in palette.items():
            if not roles:
                raise ValueError(f"{palette_name} lists {color} with no role")
            for role in roles:
                if not role.startswith(role_prefix):
                    raise ValueError(
                        f"{palette_name} lists role {role}, which lacks "
                        f"the prefix {role_prefix}"
                    )
                if role in resolved:
                    raise ValueError(
                        f"{palette_name} lists role {role} under "
                        f"both {resolved[role]} and {color}"
                    )
                resolved[role] = color
        return resolved

    def root_value_names_check(self) -> None:
        names: set[str] = set()
        for name in _STYLE_VALUE_ENTRIES:
            if name in self.color_roles or name in self.light_mode_roles:
                raise ValueError(
                    f"STYLE_VALUE_ENTRIES names --{name}, a colour role too"
                )
            names.add(f"--{name}")
        names |= {
            _STYLE_DESIGN_DEVICE_PIXEL_WIDEST_PROPERTY,
            _STYLE_DESIGN_FONT_FIT_PROPERTY,
            _STYLE_DESIGN_FONT_SIZE_PROPERTY,
            _STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY,
            _STYLE_HEAT_MAP_SOURCE_LINE_NUMBER_MARKER_WIDTH_PROPERTY,
            _STYLE_PAGE_FONT_FAMILY_PROPERTY,
        }
        self.reads_check(self.shared_stylesheets_text(), names)
        self.reads_check(
            self.asset_read(_ASSET_DARK_MODE_STYLESHEET_NAME),
            names | {f"--{role}" for role in self.color_roles},
        )
        self.reads_check(
            self.asset_read(_ASSET_LIGHT_MODE_STYLESHEET_NAME),
            names | {f"--{role}" for role in self.light_mode_roles},
        )
        names |= {
            f"--{role}" for role in (self.light_mode_roles | self.color_roles)
        }
        stylesheets_text = self.stylesheets_text()
        for name in sorted(names):
            if f"var({name})" not in stylesheets_text:
                raise ValueError(
                    f"the root values set {name}, which no stylesheet reads"
                )

    def shared_stylesheets_text(self) -> str:
        return "".join(
            self.asset_read(name)
            for name in (
                _ASSET_HEAT_MAP_STYLESHEET_NAME,
                _ASSET_MENU_STYLESHEET_NAME,
                _ASSET_THEME_STYLESHEET_NAME,
            )
        )

    def stylesheets_text(self) -> str:
        return (
            self.shared_stylesheets_text()
            + self.asset_read(_ASSET_LIGHT_MODE_STYLESHEET_NAME)
            + self.asset_read(_ASSET_DARK_MODE_STYLESHEET_NAME)
        )

    def time_units(self) -> tuple[Theme.TimeUnit, ...]:
        return tuple(
            Theme.TimeUnit(suffix, seconds)
            for suffix, seconds in _THEME_TIME_UNIT_ENTRIES
        )

    # Reads every string of `ui_strings.js`, the one table of UI text.
    def ui_strings_read(self) -> dict[str, str]:
        script_text = self.asset_read(_ASSET_UI_STRINGS_SCRIPT_NAME)
        block = _UI_STRINGS_BLOCK.search(script_text)
        if block is None:
            raise ValueError(
                f"{_ASSET_UI_STRINGS_SCRIPT_NAME} holds no STRINGS block"
            )
        unread_text = _UI_STRINGS_ENTRY.sub("", block.group(1)).strip()
        if unread_text:
            raise ValueError(
                f"{_ASSET_UI_STRINGS_SCRIPT_NAME} holds a STRINGS line no"
                f" reader parses: {unread_text.splitlines()[0]}"
            )
        strings: dict[str, str] = {}
        for string_id, literal in _UI_STRINGS_ENTRY.findall(block.group(1)):
            if string_id in strings:
                raise ValueError(
                    f"{_ASSET_UI_STRINGS_SCRIPT_NAME} names {string_id} twice"
                )
            strings[string_id] = json.loads(literal)
        return strings

    def ui_text_fill(
        self, string_id: str, replacements: dict[str, str]
    ) -> str:
        def marker_value(marker: re.Match[str]) -> str:
            if marker.group(1) not in replacements:
                raise ValueError(
                    f"ui string {string_id} has no value for {marker.group(0)}"
                )
            return replacements[marker.group(1)]

        return _UI_TEXT_MARKER.sub(marker_value, self.ui_text_of(string_id))

    def ui_text_of(self, string_id: str) -> str:
        if string_id not in self.ui_strings:
            raise ValueError(f"missing ui string: {string_id}")
        return self.ui_strings[string_id]


_renderer = Theme()

_table_renderer = TableRenderer()


def asset_text_read(name: str) -> str:
    return _renderer.asset_read(name)


def diff_share_of(delta: int, baseline: int | None) -> float:
    return _renderer.number_format.diff_share_of(delta, baseline)


# Writes one element, the one writer of a tag, a None inner a void tag.
def element_render(
    tag_name: str, attributes: dict[str, str], inner_markup: str | None
) -> str:
    attribute_text = "".join(
        f' {attribute_name}="{html_escape(attribute_value)}"'
        for attribute_name, attribute_value in attributes.items()
    )
    start_tag = f"<{tag_name}{attribute_text}>"
    if inner_markup is None:
        return start_tag
    return f"{start_tag}{inner_markup}</{tag_name}>"


# Writes a heading, the page scripts showing its title as page emphasis.
def heading_render(title_markup: str, count_key: str = "") -> str:
    count_attributes = {"data-row-count-key-": count_key} if count_key else {}
    return element_render(
        "div", {"class": "page-heading-"} | count_attributes, title_markup
    )


def heat_of_share(percent: float) -> float:
    return _renderer.heat_of_share(percent)


def heat_style(heat: float, signed: bool = False) -> str:
    return _renderer.heat_style(heat, signed)


# Holds a framed page's scripts until utility.js relays the settings down.
def held_script_tags(script_markup: str) -> str:
    return (
        element_render("template", {"id": "page-held-script-"}, script_markup)
        + "\n"
    )


# Escapes text for markup, the one escape the page builders write through.
def html_escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# Writes a menu button: menu colours, then a tab stop, link or role by kind.
def menu_button_render(
    kind_name: str, label_markup: str, fields: MenuButtonFields
) -> str:
    if kind_name not in _MENU_BUTTON_KIND_NAMES:
        raise ValueError(f"menu button kind unrecognized: {kind_name}")
    own_attributes = {"class": "menu-button-"}
    inner_markup = label_markup
    if kind_name == "link":
        link_attributes = {"href": fields.href}
        if fields.opens_new_tab:
            link_attributes["target"] = "_blank"
        if fields.tag_name == "a":
            own_attributes |= link_attributes
        else:
            own_attributes["tabindex"] = "0"
            inner_markup = element_render(
                "a", link_attributes | {"tabindex": "-1"}, label_markup
            )
    elif fields.tag_name != "summary":
        own_attributes |= {"role": "button", "tabindex": "0"}
    return element_render(fields.tag_name, own_attributes, inner_markup)


def num_human(number: float) -> str:
    return _renderer.number_format.human(number)


def num_pct(percent: float) -> str:
    return _renderer.number_format.percent(percent)


def num_signed(number: float) -> str:
    return _renderer.number_format.signed(number)


def num_signed_pct(percent: float, is_line: bool = False) -> str:
    return _renderer.number_format.signed_percent(percent, is_line)


def num_time(seconds: float) -> str:
    return _renderer.number_format.time(seconds)


def page_document(
    title: str,
    body: str,
    extra_js: Sequence[str] = (),
    body_class: str = "",
    depth: int = 0,
    extra_css: Sequence[str] = (),
    body_holds_scripts: bool = False,
) -> str:
    return _renderer.document(
        title,
        body,
        extra_js,
        body_class,
        depth,
        extra_css,
        body_holds_scripts,
    )


def page_preamble_scripts() -> tuple[str, ...]:
    return (
        _ASSET_ERROR_OVERLAY_SCRIPT_NAME,
        _ASSET_UTILITY_SCRIPT_NAME,
        _ASSET_UI_STRINGS_SCRIPT_NAME,
        _ASSET_SETTINGS_SCRIPT_NAME,
    )


def script_tags(href: str, names: Sequence[str]) -> str:
    return "".join(
        element_render("script", {"src": f"{href}/{name}"}, "") + "\n"
        for name in names
    )


def shared_href(depth: int, name: str) -> str:
    return "../" * depth + name


def table_render(
    key: str,
    columns: Sequence[Column],
    rows: Sequence[Sequence[CellOrText]],
    fill: bool = False,
    column_titles: bool = True,
) -> str:
    return _table_renderer.table(key, columns, rows, fill, column_titles)


# Fills each marker with its markup, refusing a marker the template lacks.
def template_fill(template_text: str, marker_values: dict[str, str]) -> str:
    for marker in marker_values:
        if marker not in template_text:
            raise ValueError(f"the template holds no marker {marker}")
    filled_text = template_text
    for marker, markup in marker_values.items():
        filled_text = filled_text.replace(marker, markup)
    return filled_text


def theme_assets_write(out_dir: str) -> None:
    _renderer.assets_write(out_dir)


def ui_text_fill(string_id: str, replacements: dict[str, str]) -> str:
    return _renderer.ui_text_fill(string_id, replacements)


def ui_text_of(string_id: str) -> str:
    return _renderer.ui_text_of(string_id)
