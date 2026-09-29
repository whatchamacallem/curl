from __future__ import annotations

import html, math, os, re
from collections.abc import Sequence
from typing import NamedTuple, TypeAlias, TypedDict

import settings

# All constants needed from settings.py have to be loaded here before anything
# else.
_ASSET_ERROR_OVERLAY_SCRIPT_NAME: str = ""
_ASSET_FRAME_SCRIPT_NAME: str = ""
_ASSET_HEAT_MAP_SCRIPT_NAME: str = ""
_ASSET_HEAT_MAP_STYLESHEET_NAME: str = ""
_ASSET_MENU_SCRIPT_NAME: str = ""
_ASSET_MENU_STYLESHEET_NAME: str = ""
_ASSET_REPORT_COMPLETE_SCRIPT_NAME: str = ""
_ASSET_SETTINGS_SCRIPT_NAME: str = ""
_ASSET_THEME_SCRIPT_NAME: str = ""
_ASSET_THEME_STYLESHEET_NAME: str = ""
_ASSET_UI_STRINGS_SCRIPT_NAME: str = ""
_NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES: float = 0.0
_NUMBER_SMALLEST_PRINTED_PERCENT: float = 0.0
_REPORT_ASSETS_DIR_NAME: str = ""
_STYLE_COLOR_PAIR_ENTRIES: dict[str, list[str]] = {}
_STYLE_DESIGN_FONT_FIT_PROPERTY: str = ""
_STYLE_DESIGN_FONT_SIZE_PX: int = 0
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


# Cell - One table cell: the text, plus every way a page can dress it up.
class Cell(NamedTuple):
    # what the cell says, and what its width is measured from
    text: str = ""
    # markup to print instead of the escaped text, e.g. a link
    html: str | None = None
    # inline style, which is how heat colouring gets applied
    style: str = ""
    # extra CSS classes for this one cell
    cls: str = ""


# Either a dressed-up Cell or bare text that becomes one.
CellOrText: TypeAlias = Cell | str


# Column - One table column: its label and how wide it is allowed to get.
class Column(NamedTuple):
    # the heading, which the column's widest width always fits
    label: str
    # right-align this column, because it holds numbers
    numeric: bool = False
    # a fixed width in characters, instead of measuring the rows
    width: int | None = None
    # the column that soaks up the leftover width in a fill table
    grow: bool = False


# ColumnExtent - How many characters one column's heading and cells ask for.
# theme.js's column_extents() builds the same pair under the same names.
class ColumnExtent(NamedTuple):
    # the heading's length, which only the column's widest width must fit
    heading_chars: int
    # the longest cell's length, the fixed width, or the grow column's floor
    content_chars: int


# ThemeRuntime - The few theme values the page's JavaScript needs at runtime.
class ThemeRuntime(TypedDict):
    # the same 12 heat stops, for heat the JS computes itself
    heat: list[str]
    # text colour to use on a dark (cold) cell
    fgLight: str
    # text colour to use on a light (hot) cell
    fgDark: str


# TableRenderer - Turns columns and rows into one table, every column
# width in exact characters. theme.js's report_ui is the page-side twin.
class TableRenderer:
    # Take bare text as a plain Cell, and leave a real Cell alone.
    def cell(self, value: CellOrText) -> Cell:
        return value if isinstance(value, Cell) else Cell(text=value)

    # What each column's heading and cells ask for, in characters. A grow
    # column is cut at its container, so it asks only its floor.
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

    # The narrowest and widest one column may be, in characters: the cells
    # alone (only a heading is ever cut), then heading and cells both.
    def column_limits(self, extent: ColumnExtent) -> tuple[int, int]:
        widest = max(extent.heading_chars, extent.content_chars)
        return (
            extent.content_chars + _STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS,
            widest + _STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS,
        )

    # The longest text any row holds in one column, 0 when there are no rows.
    def column_longest(
        self, rows: Sequence[Sequence[Cell]], index: int
    ) -> int:
        return max((len(row[index].text) for row in rows), default=0)

    # One column's <col> width: CSS automatic table layout on its container's
    # 100cqw, between its narrowest and widest.
    def column_width_text(
        self, limits: Sequence[tuple[int, int]], index: int, grow_index: int
    ) -> str:
        narrowest, widest = limits[index]
        shared = [
            limit for other, limit in enumerate(limits) if other != grow_index
        ]
        low_total = sum(limit[0] for limit in shared)
        high_total = sum(limit[1] for limit in shared)
        # the non-grow columns sum to clamp(low, 100cqw - grow, high); the
        # grow column takes the rest and never goes under its own narrowest
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

    # One whole table: a colgroup of character widths, then the rows.
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


# Theme - Everything that turns numbers into one styled page: the palette,
# the stylesheet, the page document and the report's shared asset copy.
class Theme:
    # Where theme.css and theme.js live.
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))

    # NumberFormat - Every number a page prints, in its page-ready form.
    class NumberFormat:
        # Take the time ladder once: the one state a formatter carries.
        def __init__(self, time_units: tuple[Theme.TimeUnit, ...]) -> None:
            self.time_units = time_units

        # A number at fixed decimal places, rounding a half away from zero,
        # not to even as round() and f-strings do.
        def fixed_text(self, value: float, digit_count: int) -> str:
            # theme.js's fixed_text() is the twin, agreeing digit for digit:
            # both scale, floor and compare in IEEE-754 doubles
            whole = self.rounded_units(value, digit_count)
            sign = "-" if value < 0 and whole else ""
            digits = str(whole).rjust(digit_count + 1, "0")
            if not digit_count:
                return sign + digits
            split_at = len(digits) - digit_count
            return sign + digits[:split_at] + "." + digits[split_at:]

        # 2.1K / 2.0G -- short enough to fit a column.
        def human(self, number: float) -> str:
            value, unit = float(number), ""
            for candidate in ("K", "M", "G", "T"):
                if value < 999.5:
                    break
                value /= 1000
                unit = candidate
            digit_count = 1 if unit and value < 9.95 else 0
            return self.fixed_text(value, digit_count) + unit

        # An unsigned share, as a percentage up to 100% and a multiple
        # above it: 1.30x. Past the upper bound it is just ">1000x".
        def multiple(self, percent: float) -> str:
            if percent <= 100:
                return self.percent(percent)
            times = percent / 100
            if times >= _NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES:
                return ">1000x"
            return self.fixed_text(times, 2) + "x"

        # 63.2% / <0.01%, and an empty cell rather than a bare 0%.
        def percent(self, percent: float) -> str:
            if percent >= 9.95:
                return self.fixed_text(percent, 1) + "%"
            if percent >= _NUMBER_SMALLEST_PRINTED_PERCENT:
                return self.fixed_text(percent, 2) + "%"
            return "<0.01%" if percent > 0 else ""

        # How many whole units of the last printed digit a value rounds to,
        # a half going away from zero.
        def rounded_units(self, value: float, digit_count: int) -> int:
            scaled = abs(value) * 10.0**digit_count
            whole = math.floor(scaled)
            return whole + 1 if scaled - whole >= 0.5 else whole

        # A diff number: same as human(), and empty at zero. Only a drop
        # is marked, with "-". A rise carries no "+".
        def signed(self, number: float) -> str:
            if number == 0:
                return ""
            return ("-" if number < 0 else "") + self.human(abs(number))

        # A diff share: empty at zero, arrow-led, a drop keeping its "-", a
        # zero baseline "∞%", and the two bounds unsigned.
        def signed_percent(self, percent: float) -> str:
            # README.md's "Reading a Diff Report" is the specification, and
            # theme.js's signed_percent_text is kept in step with this
            if percent == 0:
                return ""
            arrow = "▼" if percent < 0 else "▲"
            sign = "-" if percent < 0 else ""
            if math.isinf(percent):
                return arrow + sign + "∞%"
            if abs(percent) < _NUMBER_SMALLEST_PRINTED_PERCENT:
                return arrow + "≈0.00%"
            body = self.multiple(abs(percent))
            return arrow + ("" if body[0] == ">" else sign) + body

        # A duration in the largest unit it reaches, e.g. 1.25ms.
        def time(self, seconds: float) -> str:
            if seconds == 0:
                return "0.00s"
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
            return f"{sign}{magnitude / unit.seconds:.2f}{unit.suffix}"

    # Rgb - One colour split into channels, so it can be mixed and measured.
    class Rgb(NamedTuple):
        # 0..255
        red: int
        # 0..255
        green: int
        # 0..255
        blue: int

    # TimeUnit - One time suffix and how many seconds one of it is.
    class TimeUnit(NamedTuple):
        # what to print, e.g. "ms"
        suffix: str
        # how long one of them lasts
        seconds: float

    # Resolve the palette and the number formats once: every later lookup
    # is a plain field read, never a re-parse per cell.
    def __init__(self) -> None:
        self.color_roles = self.roles()
        self.heat_stops = [
            self.rgb(color) for color in _STYLE_HEAT_COLOR_STOPS
        ]
        self.number_format = Theme.NumberFormat(self.time_units())

    # Read one scripts/ file off disk, to inline into a page.
    def asset_read(self, name: str) -> str:
        with open(
            os.path.join(self.DIRECTORY, name), encoding="utf-8"
        ) as handle:
            return handle.read()

    # Write the report's one shared copy of the theme. The stylesheet and
    # settings.js are generated here, not copied -- copies lose their data.
    def assets_write(self, out_dir: str) -> None:
        os.makedirs(out_dir, exist_ok=True)
        heat_map_script = _ASSET_HEAT_MAP_SCRIPT_NAME
        heat_map_stylesheet = _ASSET_HEAT_MAP_STYLESHEET_NAME
        shared = (
            (
                _ASSET_ERROR_OVERLAY_SCRIPT_NAME,
                self.asset_read(_ASSET_ERROR_OVERLAY_SCRIPT_NAME),
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
        )
        for name, text in shared:
            with open(
                os.path.join(out_dir, name), "w", encoding="utf-8"
            ) as handle:
                handle.write(text)

    # The on-dark or on-bright role's colour, whichever reads on the colour.
    def contrast_foreground(
        self, color: Theme.Rgb, on_dark_role: str, on_bright_role: str
    ) -> str:
        if (
            self.luminance(color)
            > _STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE
        ):
            return self.color_roles[on_bright_role]
        return self.color_roles[on_dark_role]

    # The whole stylesheet: the colour and value variables, then theme.css.
    # A role no stylesheet names, such as a contrast role, is left out.
    def css(self) -> str:
        stylesheets_text = "".join(
            self.asset_read(name)
            for name in (
                _ASSET_HEAT_MAP_STYLESHEET_NAME,
                _ASSET_MENU_STYLESHEET_NAME,
                _ASSET_THEME_STYLESHEET_NAME,
            )
        )
        root_values = {
            f"--{role}": color
            for role, color in self.color_roles.items()
            if f"var(--{role})" in stylesheets_text
        }
        for name, value in _STYLE_VALUE_ENTRIES.items():
            if name in self.color_roles:
                raise ValueError(
                    f"STYLE_VALUE_ENTRIES names --{name}, a colour role too"
                )
            if f"var(--{name})" not in stylesheets_text:
                raise ValueError(
                    f"STYLE_VALUE_ENTRIES names --{name}, which no "
                    "stylesheet reads"
                )
            root_values[f"--{name}"] = value
        # theme.js replaces the fit of 1 and the window's full height with
        # the ones it measures
        root_values[_STYLE_DESIGN_FONT_FIT_PROPERTY] = "1"
        root_values["--design-font-size-px-"] = (
            f"{_STYLE_DESIGN_FONT_SIZE_PX}px"
        )
        root_values[_STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY] = "100vh"
        root_values["--page-font-family-"] = _STYLE_PAGE_FONT_FAMILY
        for name in re.findall(r"var\((--[\w-]+)", stylesheets_text):
            if name not in root_values:
                raise ValueError(f"a stylesheet reads {name}, unset in :root")
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

    # One page. A page linking its own stylesheet names it in extra_css,
    # which follows the theme's.
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
        head = "".join(
            f'<link rel="stylesheet" href="{assets_href}/{name}">\n'
            for name in (_ASSET_THEME_STYLESHEET_NAME, *extra_css)
        )
        # a body carrying its own block gets none here: the heat map's
        # __SCRIPTS__ sits where this would, and twice loads theme.js twice
        script = (
            ""
            if body_holds_scripts
            else script_tags(assets_href, page_preamble_scripts())
            + script_tags(
                assets_href,
                (
                    _ASSET_SETTINGS_SCRIPT_NAME,
                    _ASSET_THEME_SCRIPT_NAME,
                    *extra_js,
                ),
            )
        )
        return (
            '<!doctype html>\n<html lang="en">\n'
            '<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport"'
            ' content="width=device-width, initial-scale=1">\n'
            f"<title>{html_escape(title)}</title>\n"
            f"{head}</head>\n"
            f"<body{body_attr}>\n{body}\n"
            f"{script}</body>\n</html>\n"
        )

    # Where a share sits on the ramp, and the whole colour mapping: clamp to
    # full scale, divide, apply the log curve. heatmap.js is the twin.
    def heat_of_share(self, percent: float) -> float:
        # nothing is measured off the data, so a cell's colour depends only
        # on the number printed beside it. The sign rides along for a diff
        sign = -1.0 if percent < 0 else 1.0
        full_scale = float(_STYLE_HEAT_COLOR_FULL_SCALE_PERCENT)
        magnitude = min(abs(percent), full_scale)
        if magnitude <= 0:
            return 0.0
        fraction = magnitude / full_scale
        return sign * math.log10(1 + 9 * fraction)

    # The colour one heat position paints, and readable text over it. Opaque:
    # a cell carries the stop itself, never faded over the page background.
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
                "summary-heat-cell-on-dark-fg-",
                "summary-heat-cell-on-bright-fg-dim-",
            )
        )

    # The shared page script, read straight off disk.
    def js(self) -> str:
        return self.asset_read(_ASSET_THEME_SCRIPT_NAME)

    # How bright a colour looks, 0..1 -- what contrast_foreground() decides on.
    def luminance(self, color: Theme.Rgb) -> float:
        return (
            0.2126 * color.red + 0.7152 * color.green + 0.0722 * color.blue
        ) / 255

    # Split "#RRGGBB" into channels.
    def rgb(self, hex_color: str) -> Theme.Rgb:
        return Theme.Rgb(
            int(hex_color[1:3], 16),
            int(hex_color[3:5], 16),
            int(hex_color[5:7], 16),
        )

    # Invert _STYLE_COLOR_PAIR_ENTRIES into each role's one colour.
    def roles(self) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for color, roles in _STYLE_COLOR_PAIR_ENTRIES.items():
            for role in roles:
                if role in resolved:
                    raise ValueError(
                        f"STYLE_COLOR_PAIR_ENTRIES lists role {role} under "
                        f"both {resolved[role]} and {color}"
                    )
                resolved[role] = color
        return resolved

    # The handful of theme values the page's own JavaScript needs.
    def runtime(self) -> ThemeRuntime:
        return {
            "heat": _STYLE_HEAT_COLOR_STOPS,
            "fgLight": self.color_roles["heat-map-heat-cell-on-dark-fg-"],
            "fgDark": self.color_roles["heat-map-heat-cell-on-bright-fg-dim-"],
        }

    # Build _THEME_TIME_UNIT_ENTRIES into the ladder NumberFormat.time()
    # walks, largest unit first.
    def time_units(self) -> tuple[Theme.TimeUnit, ...]:
        return tuple(
            Theme.TimeUnit(suffix, seconds)
            for suffix, seconds in _THEME_TIME_UNIT_ENTRIES
        )


# The one renderer every page goes through, its palette resolved once.
_RENDERER = Theme()

# The one table builder every table goes through.
_TABLE_RENDERER = TableRenderer()


# asset_text_read - One file from scripts/, to inline into a page.
def asset_text_read(name: str) -> str:
    return _RENDERER.asset_read(name)


# heat_of_share - Turn a share into a position on the heat ramp.
def heat_of_share(percent: float) -> float:
    return _RENDERER.heat_of_share(percent)


# heat_style - The inline style one heat position paints a cell with.
def heat_style(heat: float, signed: bool = False) -> str:
    return _RENDERER.heat_style(heat, signed)


# html_escape - Make any value safe to drop into markup.
def html_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


# num_human - A big number shortened to fit a column, e.g. 2.1K.
def num_human(number: float) -> str:
    return _RENDERER.number_format.human(number)


# num_pct - A share as a percentage, e.g. 63.2%.
def num_pct(percent: float) -> str:
    return _RENDERER.number_format.percent(percent)


# num_signed - A diff number with its sign, empty when it is exactly zero.
def num_signed(number: float) -> str:
    return _RENDERER.number_format.signed(number)


# num_signed_pct - A diff share with its sign, empty when it is exactly zero.
def num_signed_pct(percent: float) -> str:
    return _RENDERER.number_format.signed_percent(percent)


# num_time - A duration in the largest unit it reaches, e.g. 1.25ms.
def num_time(seconds: float) -> str:
    return _RENDERER.number_format.time(seconds)


# page_document - One whole page, linking the report's shared theme.
def page_document(
    title: str,
    body: str,
    extra_js: Sequence[str] = (),
    body_class: str = "",
    depth: int = 0,
    extra_css: Sequence[str] = (),
    body_holds_scripts: bool = False,
) -> str:
    return _RENDERER.document(
        title,
        body,
        extra_js,
        body_class,
        depth,
        extra_css,
        body_holds_scripts,
    )


# page_preamble_scripts - The scripts every page links before any other, in
# this order. Each is a shared asset, one copy per report.
def page_preamble_scripts() -> tuple[str, ...]:
    # the overlay's handlers first; the strings next, needing nothing, so a
    # fault in any later script reads as text; the manifest names the report
    return (
        _ASSET_ERROR_OVERLAY_SCRIPT_NAME,
        _ASSET_UI_STRINGS_SCRIPT_NAME,
        _ASSET_REPORT_COMPLETE_SCRIPT_NAME,
    )


# script_tags - Script tags for the named assets, under one href, in order.
def script_tags(href: str, names: Sequence[str]) -> str:
    return "".join(
        f'<script src="{href}/{name}"></script>\n' for name in names
    )


# shared_href - A page's href to one of the report's shared directories.
def shared_href(depth: int, name: str) -> str:
    return "../" * depth + name


# table_render - One whole table, columns sized in exact characters.
def table_render(
    key: str,
    columns: Sequence[Column],
    rows: Sequence[Sequence[CellOrText]],
    fill: bool = False,
    column_titles: bool = True,
) -> str:
    return _TABLE_RENDERER.table(key, columns, rows, fill, column_titles)


# theme_assets_write - Write the report's one shared copy of the theme.
def theme_assets_write(out_dir: str) -> None:
    _RENDERER.assets_write(out_dir)


# theme_runtime - The theme values a page's own JavaScript needs.
def theme_runtime() -> ThemeRuntime:
    return _RENDERER.runtime()
