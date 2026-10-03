# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import html, math, os, re
from collections.abc import Sequence
from typing import NamedTuple, TypeAlias, TypedDict

import settings

_ASSET_CALLERS_SCRIPT_NAME: str = ""
_ASSET_DARK_MODE_ENABLED_STYLESHEET_NAME: str = ""
_ASSET_ERROR_OVERLAY_SCRIPT_NAME: str = ""
_ASSET_FLAME_GRAPH_SCRIPT_NAME: str = ""
_ASSET_FRAME_SCRIPT_NAME: str = ""
_ASSET_HEAT_MAP_SCRIPT_NAME: str = ""
_ASSET_HEAT_MAP_STYLESHEET_NAME: str = ""
_ASSET_LIGHT_MODE_STYLESHEET_NAME: str = ""
_ASSET_MENU_SCRIPT_NAME: str = ""
_ASSET_MENU_STYLESHEET_NAME: str = ""
_ASSET_REPORT_COMPLETE_SCRIPT_NAME: str = ""
_ASSET_SETTINGS_SCRIPT_NAME: str = ""
_ASSET_THEME_SCRIPT_NAME: str = ""
_ASSET_THEME_STYLESHEET_NAME: str = ""
_ASSET_UI_STRINGS_SCRIPT_NAME: str = ""
_ASSET_UTILITY_SCRIPT_NAME: str = ""
_DARK_MODE_ATTRIBUTE_NAME: str = ""
_LIGHT_MODE_VALUE: str = ""
_NUMBER_FRACTION_DIGITS: int = 0
_NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES: float = 0.0
_NUMBER_SMALLEST_PRINTED_PERCENT: float = 0.0
_REPORT_ASSETS_DIR_NAME: str = ""
_STYLE_COLOR_DARK_MODE: dict[str, list[str]] = {}
_STYLE_COLOR_LIGHT_MODE: dict[str, list[str]] = {}
_STYLE_DESIGN_COORDINATES_WIDTH_PX: int = 0
_STYLE_DESIGN_FONT_FIT_PROPERTY: str = ""
_STYLE_DESIGN_FONT_SIZE_PX: int = 0
_STYLE_DESIGN_MINIMUM_WINDOW_WIDTH_PX: int = 0
_STYLE_DESIGN_SCALE_DEFAULT_MULTIPLE: int = 0
_STYLE_DESIGN_SCALE_LARGEST_MULTIPLE: int = 0
_STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE: float = 0.0
_STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY: str = ""
_STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE: float = 0.0
_STYLE_HEAT_COLOR_FULL_SCALE_PERCENT: int = 0
_STYLE_HEAT_COLOR_STOPS: list[str] = []
_STYLE_PAGE_FONT_FAMILY: str = ""
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

_LIGHT_MODE_BACKGROUND_ROLE = "light-mode-page-bg-"
_LIGHT_MODE_FOREGROUND_ROLE = "light-mode-page-fg-"
_DARK_MODE_ENABLED_SELECTOR = (
    f':root:not([{_DARK_MODE_ATTRIBUTE_NAME}="{_LIGHT_MODE_VALUE}"])'
)
_DARK_MODE_ROLE_PREFIX = "dark-mode-"
_LIGHT_MODE_ROLE_PREFIX = "light-mode-"
_ROLE_KIND_PATTERN = re.compile(r"-(bg|border|fg|outline)(-dim)?-$")


class Cell(NamedTuple):
    text: str = ""
    html: str | None = None
    style: str = ""
    cls: str = ""


CellOrText: TypeAlias = Cell | str


class Column(NamedTuple):
    label: str
    numeric: bool = False
    width: int | None = None
    grow: bool = False


class ColumnExtent(NamedTuple):
    heading_chars: int
    content_chars: int


class ThemeRuntime(TypedDict):
    heat: list[str]
    fgLight: str
    fgDark: str


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
        out = [f'<div class="table-box-{" fill_" if fill else ""}">']
        table_classes = "columns_" + (" fill_" if fill else "")
        out.append(
            f'<div class="table-columns-"><table class="{table_classes}" '
            f'data-key-="{html_escape(key)}"><colgroup>'
        )
        for index, limit in enumerate(limits):
            col_classes = " ".join(
                class_name
                for class_name in (
                    "alternate_" if index % 2 else "",
                    "grow_" if index == grow_index else "",
                )
                if class_name
            )
            attr = f' class="{col_classes}"' if col_classes else ""
            width = self.column_width_text(limits, index, grow_index)
            out.append(
                f'<col{attr} data-min-="{limit[0]}ch" style="width:{width}">'
            )
        out.append("</colgroup>")
        if column_titles:
            out.append("<thead><tr>")
            for column in columns:
                attrs = ' class="numeric_"' if column.numeric else ""
                label = html_escape(column.label)
                out.append(f'<th{attrs} title="{label}">{label}</th>')
            out.append("</tr></thead>")
        out.append("<tbody>")
        for row in cells:
            out.append("<tr>")
            for column, cell in zip(columns, row, strict=True):
                cell_classes = " ".join(
                    class_name
                    for class_name in (
                        "numeric_" if column.numeric else "",
                        cell.cls,
                    )
                    if class_name
                )
                attrs = (
                    f' class="{cell_classes}"' if cell_classes else ""
                ) + (f' style="{cell.style}"' if cell.style else "")
                inner = (
                    cell.html
                    if cell.html is not None
                    else html_escape(cell.text)
                )
                out.append(f"<td{attrs}>{inner}</td>")
            out.append("</tr>")
        out.append("</tbody></table></div>")
        out.append("</div>")
        return "".join(out)


class Theme:
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))

    class NumberFormat:
        def __init__(self, time_units: tuple[Theme.TimeUnit, ...]) -> None:
            self.signed_percent_amount_chars = len(
                self.fixed_text(-100, _NUMBER_FRACTION_DIGITS) + "%"
            )
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
            if percent >= _NUMBER_SMALLEST_PRINTED_PERCENT:
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

        def signed_percent(self, percent: float) -> str:
            if percent == 0:
                return ""
            arrow = "▼" if percent < 0 else "▲"
            digit_count = _NUMBER_FRACTION_DIGITS
            times = percent / 100
            if percent == math.inf:
                amount_text = "∞%"
            elif abs(percent) < _NUMBER_SMALLEST_PRINTED_PERCENT:
                amount_text = "≈" + self.fixed_text(0, digit_count) + "%"
            elif percent <= 100:
                amount_text = self.fixed_text(percent, digit_count) + "%"
            elif times >= _NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES:
                amount_text = "≈∞%"
            else:
                amount_text = self.fixed_text(times, digit_count) + "x"
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
            "STYLE_COLOR_DARK_MODE", _STYLE_COLOR_DARK_MODE
        )
        self.light_mode_roles = self.roles(
            "STYLE_COLOR_LIGHT_MODE", _STYLE_COLOR_LIGHT_MODE
        )
        self.heat_stops = [
            self.rgb(color) for color in _STYLE_HEAT_COLOR_STOPS
        ]
        self.number_format = Theme.NumberFormat(self.time_units())

    def asset_read(self, name: str) -> str:
        with open(
            os.path.join(self.DIRECTORY, name), encoding="utf-8"
        ) as handle:
            return handle.read()

    def assets_write(self, out_dir: str) -> None:
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
                self.light_mode_css(),
            ),
            (
                _ASSET_DARK_MODE_ENABLED_STYLESHEET_NAME,
                self.dark_mode_css(),
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
                _ASSET_SETTINGS_SCRIPT_NAME,
                settings.settings_script_write(),
            ),
            (_ASSET_THEME_STYLESHEET_NAME, self.css()),
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
        if (
            self.luminance(color)
            > _STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE
        ):
            return self.color_roles[on_bright_role]
        return self.color_roles[on_dark_role]

    def css(self) -> str:
        stylesheets_text = self.stylesheets_text()
        root_values: dict[str, str] = {}
        for name, value in _STYLE_VALUE_ENTRIES.items():
            if name in self.color_roles or name in self.light_mode_roles:
                raise ValueError(
                    f"STYLE_VALUE_ENTRIES names --{name}, a colour role too"
                )
            if f"var(--{name})" not in stylesheets_text:
                raise ValueError(
                    f"STYLE_VALUE_ENTRIES names --{name}, which no "
                    "stylesheet reads"
                )
            root_values[f"--{name}"] = value
        design_device_pixel_widest_px = _STYLE_DESIGN_COORDINATES_WIDTH_PX / (
            _STYLE_DESIGN_MINIMUM_WINDOW_WIDTH_PX
            * _STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE
        )
        root_values["--design-device-pixel-widest-px-"] = (
            f"{design_device_pixel_widest_px}px"
        )
        root_values[_STYLE_DESIGN_FONT_FIT_PROPERTY] = "1"
        root_values["--design-font-size-px-"] = (
            f"{_STYLE_DESIGN_FONT_SIZE_PX}px"
        )
        root_values[_STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY] = "100vh"
        root_values["--page-font-family-"] = _STYLE_PAGE_FONT_FAMILY
        dark_names = {f"--{role}" for role in self.dark_mode_roles()}
        self.reads_check(
            self.shared_stylesheets_text(), set(root_values) | dark_names
        )
        self.reads_check(
            self.asset_read(_ASSET_DARK_MODE_ENABLED_STYLESHEET_NAME),
            set(root_values) | dark_names,
        )
        light_text = self.asset_read(_ASSET_LIGHT_MODE_STYLESHEET_NAME)
        self.reads_check(
            light_text,
            set(root_values) | {f"--{role}" for role in self.light_mode_roles},
        )
        lines = [":root {"]
        lines.extend(
            f"  {name}: {value};" for name, value in root_values.items()
        )
        lines.append("}")
        return (
            "\n".join(lines)
            + "\n"
            + self.asset_read(_ASSET_THEME_STYLESHEET_NAME)
        )

    def dark_mode_css(self) -> str:
        stylesheet_text = self.mode_stylesheet_read(
            _ASSET_DARK_MODE_ENABLED_STYLESHEET_NAME,
            _DARK_MODE_ENABLED_SELECTOR,
        )
        lines = [f"{_DARK_MODE_ENABLED_SELECTOR} {{"]
        lines.extend(
            f"  --{role}: {color};"
            for role, color in self.dark_mode_roles().items()
        )
        lines.append("}")
        return "\n".join(lines) + "\n" + stylesheet_text

    # Finds the dark roles that the shared or dark mode stylesheets read.
    def dark_mode_roles(self) -> dict[str, str]:
        return self.stylesheet_roles(
            self.shared_stylesheets_text()
            + self.asset_read(_ASSET_DARK_MODE_ENABLED_STYLESHEET_NAME)
        )

    def light_mode_css(self) -> str:
        stylesheet_text = self.asset_read(
            _ASSET_LIGHT_MODE_STYLESHEET_NAME
        )
        lines = [":root {"]
        lines.extend(
            f"  --{role}: {color};"
            for role, color in self.light_mode_roles.items()
        )
        for role in self.stylesheet_roles(self.shared_stylesheets_text()):
            lines.append(
                f"  --{role}: var(--{self.light_mode_role_of(role)});"
            )
        lines.append("}")
        return "\n".join(lines) + "\n" + stylesheet_text

    def light_mode_role_of(self, role: str) -> str:
        role_kind = _ROLE_KIND_PATTERN.search(role)
        if role_kind is None:
            raise ValueError(
                f"role {role} ends in none of bg, fg, outline or border"
            )
        if role_kind.group(1) == "bg":
            return _LIGHT_MODE_BACKGROUND_ROLE
        return _LIGHT_MODE_FOREGROUND_ROLE

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
        body_attr = f' class="{body_class}"' if body_class else ""
        head_scripts = script_tags(assets_href, page_preamble_scripts())
        head = "".join(
            f'<link rel="stylesheet" href="{assets_href}/{name}">\n'
            for name in (
                _ASSET_THEME_STYLESHEET_NAME,
                *extra_css,
                _ASSET_LIGHT_MODE_STYLESHEET_NAME,
                _ASSET_DARK_MODE_ENABLED_STYLESHEET_NAME,
            )
        )
        script = (
            ""
            if body_holds_scripts
            else script_tags(
                assets_href,
                (
                    _ASSET_REPORT_COMPLETE_SCRIPT_NAME,
                    _ASSET_SETTINGS_SCRIPT_NAME,
                    _ASSET_THEME_SCRIPT_NAME,
                    *extra_js,
                ),
            )
        )
        return (
            '<!doctype html>\n<html lang="en">\n'
            '<head>\n<meta charset="utf-8">\n'
            f"{head_scripts}"
            '<meta name="viewport"'
            ' content="width=device-width, initial-scale=1">\n'
            f"<title>{html_escape(title)}</title>\n"
            f"{head}</head>\n"
            f"<body{body_attr}>\n{body}\n"
            f"{script}</body>\n</html>\n"
        )

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
                "callers-heat-cell-on-dark-fg-",
                "callers-heat-cell-on-bright-fg-dim-",
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
                raise ValueError(f"a stylesheet reads {name}, never set")

    def rgb(self, hex_color: str) -> Theme.Rgb:
        return Theme.Rgb(
            int(hex_color[1:3], 16),
            int(hex_color[3:5], 16),
            int(hex_color[5:7], 16),
        )

    def roles(
        self, palette_name: str, palette: dict[str, list[str]]
    ) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for color, roles in palette.items():
            for role in roles:
                if role in resolved:
                    raise ValueError(
                        f"{palette_name} lists role {role} under "
                        f"both {resolved[role]} and {color}"
                    )
                resolved[role] = color
        return resolved

    def runtime(self) -> ThemeRuntime:
        return {
            "heat": _STYLE_HEAT_COLOR_STOPS,
            "fgLight": self.color_roles["heat-map-heat-cell-on-dark-fg-"],
            "fgDark": self.color_roles["heat-map-heat-cell-on-bright-fg-dim-"],
        }

    def shared_stylesheets_text(self) -> str:
        return "".join(
            self.asset_read(name)
            for name in (
                _ASSET_HEAT_MAP_STYLESHEET_NAME,
                _ASSET_MENU_STYLESHEET_NAME,
                _ASSET_THEME_STYLESHEET_NAME,
            )
        )

    def stylesheet_roles(self, stylesheets_text: str) -> dict[str, str]:
        return {
            role: color
            for role, color in self.color_roles.items()
            if f"var(--{role})" in stylesheets_text
        }

    def stylesheets_text(self) -> str:
        return (
            self.shared_stylesheets_text()
            + self.asset_read(_ASSET_LIGHT_MODE_STYLESHEET_NAME)
            + self.asset_read(_ASSET_DARK_MODE_ENABLED_STYLESHEET_NAME)
        )

    def time_units(self) -> tuple[Theme.TimeUnit, ...]:
        return tuple(
            Theme.TimeUnit(suffix, seconds)
            for suffix, seconds in _THEME_TIME_UNIT_ENTRIES
        )


_renderer = Theme()

_table_renderer = TableRenderer()


def asset_text_read(name: str) -> str:
    return _renderer.asset_read(name)


def diff_share_of(delta: int, baseline: int | None) -> float:
    return _renderer.number_format.diff_share_of(delta, baseline)


def heat_of_share(percent: float) -> float:
    return _renderer.heat_of_share(percent)


def heat_style(heat: float, signed: bool = False) -> str:
    return _renderer.heat_style(heat, signed)


def html_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def num_human(number: float) -> str:
    return _renderer.number_format.human(number)


def num_pct(percent: float) -> str:
    return _renderer.number_format.percent(percent)


def num_signed(number: float) -> str:
    return _renderer.number_format.signed(number)


def num_signed_pct(percent: float) -> str:
    return _renderer.number_format.signed_percent(percent)


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
    )


def script_tags(href: str, names: Sequence[str]) -> str:
    return "".join(
        f'<script src="{href}/{name}"></script>\n' for name in names
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


def theme_assets_write(out_dir: str) -> None:
    _renderer.assets_write(out_dir)


def theme_runtime() -> ThemeRuntime:
    return _renderer.runtime()
