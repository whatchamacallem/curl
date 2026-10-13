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
_ASSET_ERROR_OVERLAY_SCRIPT_NAME: str = ""
_ASSET_FLAME_GRAPH_SCRIPT_NAME: str = ""
_ASSET_FRAME_SCRIPT_NAME: str = ""
_ASSET_HEAT_MAP_SCRIPT_NAME: str = ""
_ASSET_HEAT_MAP_STYLESHEET_NAME: str = ""
_ASSET_LIGHT_MODE_STYLESHEET_NAME: str = ""
_ASSET_MENU_SCRIPT_NAME: str = ""
_ASSET_MENU_STYLESHEET_NAME: str = ""
_ASSET_OVERVIEW_SCRIPT_NAME: str = ""
_ASSET_PREFERENCES_SCRIPT_NAME: str = ""
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
_STYLE_HEAT_MAP_SOURCE_LINE_NUMBER_MARKER_WIDTH_PROPERTY: str = ""
_STYLE_PAGE_FONT_FAMILY_PROPERTY: str = ""
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

_MENU_BUTTON_KIND_NAMES = ("link",)


class Cell(NamedTuple):
    text: str = ""
    href: str = ""


CellOrText: TypeAlias = Cell | str


class MenuButtonFields(NamedTuple):
    tag_name: str
    href: str = ""
    opens_new_tab: bool = False


class Theme:
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))

    class NumberFormat:
        def __init__(self, time_units: tuple[Theme.TimeUnit, ...]) -> None:
            self.signed_percent_amount_chars = len(
                self.fixed_text(-100, _NUMBER_FRACTION_DIGITS) + "%"
            )
            self.smallest_printed_percent = 1 / 10**_NUMBER_FRACTION_DIGITS
            self.time_units = time_units

        def diff_share(self, delta: int, baseline: int | None) -> float:
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
        self.number_format = Theme.NumberFormat(self.time_units())

    def asset_read(self, name: str) -> str:
        with open(
            os.path.join(self.DIRECTORY, name), encoding="utf-8"
        ) as handle:
            return handle.read()

    def scripts_write(self, out_dir: str) -> None:
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
                _ASSET_OVERVIEW_SCRIPT_NAME,
                self.asset_read(_ASSET_OVERVIEW_SCRIPT_NAME),
            ),
            (
                _ASSET_PREFERENCES_SCRIPT_NAME,
                self.asset_read(_ASSET_PREFERENCES_SCRIPT_NAME),
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

    # Answers a cell as the JS table writer's fields, defaults left out.
    def cell_fields(self, value: CellOrText) -> str | dict[str, str]:
        if isinstance(value, str):
            return value
        fields = {"text": value.text}
        if value.href:
            fields["href"] = value.href
        return fields

    def js(self) -> str:
        return self.asset_read(_ASSET_THEME_SCRIPT_NAME)

    def mode_stylesheet_read(self, name: str, selector: str) -> str:
        stylesheet_text = self.asset_read(name)
        if selector not in stylesheet_text:
            raise ValueError(f"{name} never names {selector}")
        return stylesheet_text

    def reads_check(self, stylesheet_text: str, names: set[str]) -> None:
        for name in re.findall(r"var\((--[\w-]+)", stylesheet_text):
            if name not in names:
                raise ValueError(f"a stylesheet reads {name}, not set for it")

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
                    f"STYLE_VALUE_ENTRIES names --{name}, a color role too"
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
        common_stylesheets_text = "".join(
            self.asset_read(name)
            for name in (
                _ASSET_HEAT_MAP_STYLESHEET_NAME,
                _ASSET_MENU_STYLESHEET_NAME,
                _ASSET_THEME_STYLESHEET_NAME,
            )
        )
        dark_mode_text = self.asset_read(_ASSET_DARK_MODE_STYLESHEET_NAME)
        light_mode_text = self.asset_read(_ASSET_LIGHT_MODE_STYLESHEET_NAME)
        self.reads_check(common_stylesheets_text, names)
        self.reads_check(
            dark_mode_text,
            names | {f"--{role}" for role in self.color_roles},
        )
        self.reads_check(
            light_mode_text,
            names | {f"--{role}" for role in self.light_mode_roles},
        )
        names |= {
            f"--{role}" for role in (self.light_mode_roles | self.color_roles)
        }
        stylesheets_text = (
            common_stylesheets_text + light_mode_text + dark_mode_text
        )
        for name in sorted(names):
            if f"var({name})" not in stylesheets_text:
                raise ValueError(
                    f"the root values set {name}, which no stylesheet reads"
                )

    def time_units(self) -> tuple[Theme.TimeUnit, ...]:
        return tuple(
            Theme.TimeUnit(suffix, seconds)
            for suffix, seconds in _THEME_TIME_UNIT_ENTRIES
        )


_renderer = Theme()


def asset_text_read(name: str) -> str:
    return _renderer.asset_read(name)


def diff_share(delta: int, baseline: int | None) -> float:
    return _renderer.number_format.diff_share(delta, baseline)


def href(depth: int, name: str) -> str:
    return "../" * depth + name


def num_human(number: float) -> str:
    return _renderer.number_format.human(number)


def num_signed(number: float) -> str:
    return _renderer.number_format.signed(number)


def num_signed_pct(percent: float, is_line: bool = False) -> str:
    return _renderer.number_format.signed_percent(percent, is_line)


def num_time(seconds: float) -> str:
    return _renderer.number_format.time(seconds)


# Writes one element, the one writer of a tag, a None inner a void tag.
def render_element(
    tag_name: str, attributes: dict[str, str], inner_markup: str | None
) -> str:
    attribute_text = "".join(
        f' {attribute_name}="{render_html_escape(attribute_value)}"'
        for attribute_name, attribute_value in attributes.items()
    )
    start_tag = f"<{tag_name}{attribute_text}>"
    if inner_markup is None:
        return start_tag
    return f"{start_tag}{inner_markup}</{tag_name}>"


# Writes a heading, the page scripts showing its title as page emphasis.
def render_heading(title_markup: str, heading_id: str = "") -> str:
    id_attributes = {"id": heading_id} if heading_id else {}
    return render_element(
        "div", id_attributes | {"class": "page-heading-"}, title_markup
    )


# Escapes text for markup, the one escape the page builders write through.
def render_html_escape(value: object) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# Writes a menu button: menu colors, then a link, a tab stop unless an anchor.
def render_menu_button(
    kind_name: str, label_markup: str, fields: MenuButtonFields
) -> str:
    if kind_name not in _MENU_BUTTON_KIND_NAMES:
        raise ValueError(f"menu button kind unrecognized: {kind_name}")
    own_attributes = {"class": "menu-button-"}
    inner_markup = label_markup
    link_attributes = {"href": fields.href}
    if fields.opens_new_tab:
        link_attributes["target"] = "_blank"
    if fields.tag_name == "a":
        own_attributes |= link_attributes
    else:
        own_attributes["tabindex"] = "0"
        inner_markup = render_element(
            "a", link_attributes | {"tabindex": "-1"}, label_markup
        )
    return render_element(fields.tag_name, own_attributes, inner_markup)


# Answers rows as the JSON a page script hands the table writer.
def table_rows_text(rows: Sequence[Sequence[CellOrText]]) -> str:
    return json.dumps(
        [[_renderer.cell_fields(value) for value in row] for row in rows],
        ensure_ascii=False,
    )


# Fills each marker with its markup, refusing a marker the template lacks.
def template_fill(template_text: str, marker_values: dict[str, str]) -> str:
    for marker in marker_values:
        if marker not in template_text:
            raise ValueError(f"the template holds no marker {marker}")
    filled_text = template_text
    for marker, markup in marker_values.items():
        filled_text = filled_text.replace(marker, markup)
    return filled_text


def theme_scripts_write(out_dir: str) -> None:
    _renderer.scripts_write(out_dir)
