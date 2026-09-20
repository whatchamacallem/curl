from __future__ import annotations

import html
import math
import os
from collections.abc import Sequence
from typing import NamedTuple, TypeAlias, TypedDict

# The page font: Monaco first, then whatever else the box has.
_FONT = (
    'Monaco, Menlo, "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace'
)

# The 12-stop heat ramp, cold to hot. Exempt from the light/dark pair rule.
_HEAT: list[str] = [
    "#3E4A89",
    "#31688E",
    "#26828E",
    "#1F9E89",
    "#35B779",
    "#6DCD59",
    "#B4DE2C",
    "#FDE725",
    "#FFC83B",
    "#FFA22C",
    "#FF7F21",
    "#F06142",
]

# How opaque the hottest and coldest cells blend over the page background.
_HEAT_ALPHA_HIGH = 0.92
_HEAT_ALPHA_LOW = 0.18
# Below this share a cell gets no heat at all.
_HEAT_MINIMUM_SHARE = 0.001

# Breathing room added to every column width, in characters.
_PADDING_CHARS = 3

# Raw "User settings" THEME entries: odd index = dark member.
_THEME: list[str] = [
    "#1AB6FF",
    "#0097E6",
    "#F5F6FA",
    "#DCDDE1",
    "#FBC531",
    "#E1B12C",
    "#7F8FA6",
    "#718093",
    "#273C75",
    "#192A56",
    "#487EB0",
    "#40739E",
    "#353B48",
    "#2F3640",
]

# The title badge must fit the longest test name plus view label, or it
# clips mid-word.
TITLE_COLUMNS = len("|-------------------------------|")


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
    # hover text, defaulting to the full text when the column clips it
    title: str = ""


# Either a dressed-up Cell or bare text that becomes one.
CellOrText: TypeAlias = Cell | str


# Column - One table column: its title and how wide it is allowed to get.
class Column(NamedTuple):
    # the header text, and every column's width floor
    label: str
    # hover text on the header
    title: str = ""
    # right-align this column, because it holds numbers
    numeric: bool = False
    # a fixed width in characters, instead of measuring the rows
    width: int | None = None
    # the widest a measured column may get before it truncates
    clip: int | None = None
    # the column that soaks up the leftover width in a fill table
    grow: bool = False


# ThemeRuntime - The few theme values the page's JavaScript needs at runtime.
class ThemeRuntime(TypedDict):
    # the same 12 heat stops, for heat the JS computes itself
    heat: list[str]
    # the page background heat blends over
    bg: str
    # text colour to use on a light (hot) cell
    fgLight: str
    # text colour to use on a dark (cold) cell
    fgDark: str


# Theme - Everything that turns numbers and rows into one styled page.
class Theme:
    # Where theme.css and theme.js live.
    DIRECTORY = os.path.dirname(os.path.abspath(__file__))
    # The seven colour pairs of _THEME, in the order _THEME lists them.
    NAMES = ("blue", "white", "yellow", "gray", "navy", "steel", "slate")

    # ColorPair - One "User settings" colour in both its light and dark form.
    class ColorPair(NamedTuple):
        # the light member, exposed to CSS as --<name>-l
        light: str
        # the dark member, exposed to CSS as --<name>
        dark: str

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

    # NumberFormat - Every number a page prints, in its page-ready form.
    class NumberFormat:
        # 2.1K / 2.0G -- short enough to fit a column, exact in the tooltip.
        def human(self, number: float) -> str:
            value, unit = float(number), ""
            for candidate in ("K", "M", "G", "T"):
                if value < 999.5:
                    break
                value /= 1000
                unit = candidate
            return (
                f"{value:.1f}{unit}"
                if unit and value < 9.95
                else f"{value:.0f}{unit}"
            )

        # 63.2% / <0.01%, and an empty cell rather than a bare 0%.
        def percent(self, percent: float) -> str:
            if percent >= 9.95:
                return f"{percent:.1f}%"
            if percent >= 0.01:
                return f"{percent:.2f}%"
            return "<0.01%" if percent > 0 else ""

        # A diff number: same as human(), with a sign, and empty at zero.
        def signed(self, number: float) -> str:
            if number == 0:
                return ""
            return ("+" if number > 0 else "-") + self.human(abs(number))

        # A diff share: same as percent(), with a sign, and empty at zero.
        def signed_percent(self, percent: float) -> str:
            if percent == 0:
                return ""
            return ("+" if percent > 0 else "-") + self.percent(abs(percent))

        # A duration in the largest unit it reaches, e.g. 1.25ms.
        def time(self, seconds: float) -> str:
            if seconds == 0:
                return "0.00s"
            sign = "-" if seconds < 0 else ""
            magnitude = abs(seconds)
            unit = next(
                (
                    candidate
                    for candidate in _TIME_UNITS
                    if magnitude >= candidate.seconds
                ),
                _TIME_UNITS[-1],
            )
            return f"{sign}{magnitude / unit.seconds:.2f}{unit.suffix}"

    # Read theme.css or theme.js off disk, to inline into a page.
    def asset_read(self, name: str) -> str:
        with open(
            os.path.join(self.DIRECTORY, name), encoding="utf-8"
        ) as handle:
            return handle.read()

    # Take bare text as a plain Cell, and leave a real Cell alone.
    def cell(self, value: CellOrText) -> Cell:
        return value if isinstance(value, Cell) else Cell(text=value)

    # How wide each column ends up: its title is always the floor.
    def column_widths(
        self, columns: Sequence[Column], rows: Sequence[Sequence[Cell]]
    ) -> list[int]:
        widths: list[int] = []
        for index, column in enumerate(columns):
            width = len(column.label)
            if column.width is not None:
                width = max(width, column.width)
            else:
                for row in rows:
                    if index < len(row):
                        width = max(width, len(row[index].text))
                if column.clip is not None:
                    width = max(len(column.label), min(width, column.clip))
            widths.append(width + _PADDING_CHARS)
        return widths

    # Dark or light text, whichever the background can actually be read on.
    def contrast_foreground(self, color: Theme.Rgb) -> str:
        return _ROLE["bg"] if self.luminance(color) > 0.5 else _ROLE["fg"]

    # The whole stylesheet: the colour variables, then theme.css itself.
    def css(self) -> str:
        lines = [":root {"]
        for name, pair in _COLOR_PAIR.items():
            lines.append(f"  --{name}: {pair.dark}; --{name}-l: {pair.light};")
        for role, color in _ROLE.items():
            lines.append(f"  --{role}: {color};")
        lines.append(f"  --hot: {_HEAT[-1]};")
        lines.append(
            f"  --hot-fg: {self.contrast_foreground(self.rgb(_HEAT[-1]))};"
        )
        lines.append(f"  --title-bg: {_HEAT[2]};")
        lines.append(
            f"  --title-fg: {self.contrast_foreground(self.rgb(_HEAT[2]))};"
        )
        lines.append(f"  --title-w: calc({TITLE_COLUMNS}ch + 16px);")
        lines.append(f"  --font: {_FONT};")
        lines.append("}")
        return "\n".join(lines) + "\n" + self.asset_read("theme.css")

    # One standalone page, CSS and JS inlined -- nothing fetched.
    def document(
        self, title: str, body: str, extra_js: str = "", body_class: str = ""
    ) -> str:
        body_attr = f' class="{body_class}"' if body_class else ""
        return (
            '<!doctype html>\n<html lang="en">\n'
            '<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport"'
            ' content="width=device-width, initial-scale=1">\n'
            f"<title>{html_escape(title)}</title>\n"
            f"<style>\n{self.css()}</style>\n</head>\n"
            f"<body{body_attr}>\n{body}\n"
            f"<script>\n{self.js()}</script>\n"
            + (f"<script>\n{extra_js}</script>\n" if extra_js else "")
            + "</body>\n</html>\n"
        )

    # Blend a heat position over the page background and pick readable text.
    def heat_style(self, heat: float, signed: bool = False) -> str:
        magnitude = abs(heat)
        if magnitude <= 0:
            return ""
        stops = [self.rgb(color) for color in _HEAT]
        if signed:
            position = (heat + 1) * 0.5 * (len(stops) - 1)
        else:
            position = heat * (len(stops) - 1)
        index = min(max(int(position), 0), len(stops) - 2)
        fraction = position - index
        amount = (
            _HEAT_ALPHA_LOW + (_HEAT_ALPHA_HIGH - _HEAT_ALPHA_LOW) * magnitude
        )
        background = self.rgb(_ROLE["bg"])
        mixed = Theme.Rgb(
            *(
                round(
                    background[channel]
                    + (
                        stops[index][channel]
                        + (stops[index + 1][channel] - stops[index][channel])
                        * fraction
                        - background[channel]
                    )
                    * amount
                )
                for channel in range(3)
            )
        )
        return (
            f"background:rgb({mixed.red},{mixed.green},{mixed.blue});"
            f"color:{self.contrast_foreground(mixed)}"
        )

    # Where a share sits on the ramp: log-scaled, and signed for a diff.
    def heat_t(self, share: float, max_share: float) -> float:
        sign = -1.0 if share < 0 else 1.0
        magnitude = abs(share)
        if magnitude < _HEAT_MINIMUM_SHARE:
            return 0.0
        top = max(max_share, _HEAT_MINIMUM_SHARE * 10) / _HEAT_MINIMUM_SHARE
        return sign * min(
            1.0, math.log10(magnitude / _HEAT_MINIMUM_SHARE) / math.log10(top)
        )

    # The shared page script, read straight off disk.
    def js(self) -> str:
        return self.asset_read("theme.js")

    # How bright a colour looks, 0..1 -- what contrast_foreground() decides on.
    def luminance(self, color: Theme.Rgb) -> float:
        return (
            0.2126 * color.red + 0.7152 * color.green + 0.0722 * color.blue
        ) / 255

    # Cut _THEME into its named light/dark pairs.
    def pairs(self) -> dict[str, Theme.ColorPair]:
        return {
            name: Theme.ColorPair(_THEME[2 * index], _THEME[2 * index + 1])
            for index, name in enumerate(self.NAMES)
        }

    # Split "#RRGGBB" into channels.
    def rgb(self, hex_color: str) -> Theme.Rgb:
        return Theme.Rgb(
            int(hex_color[1:3], 16),
            int(hex_color[3:5], 16),
            int(hex_color[5:7], 16),
        )

    # The handful of theme values the page's own JavaScript needs.
    def runtime(self) -> ThemeRuntime:
        return {
            "heat": _HEAT,
            "bg": _ROLE["bg"],
            "fgLight": _ROLE["fg"],
            "fgDark": _ROLE["bg"],
        }

    # Darken or lighten a colour by a flat factor -- how --bg is derived.
    def shade(self, hex_color: str, factor: float) -> str:
        return "#" + "".join(
            f"{round(component * factor):02X}"
            for component in self.rgb(hex_color)
        )

    # One whole table: a colgroup of exact ch widths, then the rows.
    def table(
        self,
        key: str,
        columns: Sequence[Column],
        rows: Sequence[Sequence[CellOrText]],
        fill: bool = False,
        header: bool = True,
    ) -> str:
        cells = [[self.cell(value) for value in row] for row in rows]
        for row in cells:
            if len(row) > len(columns):
                raise ValueError(
                    f"table {key!r}: a row has {len(row)} cells "
                    f"for {len(columns)} columns"
                )
        grow_index = (
            next(
                (index for index, column in enumerate(columns) if column.grow),
                len(columns) - 1,
            )
            if fill
            else -1
        )
        widths = self.column_widths(columns, cells)
        out = [f'<div class="tbl{" fill" if fill else ""}">']
        table_classes = "cols" + (" fill" if fill else "")
        out.append(
            f'<div class="tbl-cols"><table class="{table_classes}" '
            f'data-key="{html_escape(key)}"><colgroup>'
        )
        for index, width in enumerate(widths):
            col_classes = " ".join(
                class_name
                for class_name in (
                    "alt" if index % 2 else "",
                    "grow" if index == grow_index else "",
                )
                if class_name
            )
            attr = f' class="{col_classes}"' if col_classes else ""
            floor = len(columns[index].label) + _PADDING_CHARS
            out.append(
                f'<col{attr} data-min="{floor}ch" style="width:{width}ch">'
            )
        out.append("</colgroup>")
        if header:
            out.append("<thead><tr>")
            for column in columns:
                attrs = (' class="n"' if column.numeric else "") + (
                    f' title="{html_escape(column.title)}"'
                    if column.title
                    else ""
                )
                out.append(f"<th{attrs}>{html_escape(column.label)}</th>")
            out.append("</tr></thead>")
        out.append("<tbody>")
        for row in cells:
            out.append("<tr>")
            for column, width, cell in zip(columns, widths, row, strict=True):
                cell_classes = " ".join(
                    class_name
                    for class_name in ("n" if column.numeric else "", cell.cls)
                    if class_name
                )
                title = cell.title or (
                    cell.text
                    if len(cell.text) + _PADDING_CHARS > width
                    else ""
                )
                attrs = (
                    (f' class="{cell_classes}"' if cell_classes else "")
                    + (f' style="{cell.style}"' if cell.style else "")
                    + (f' title="{html_escape(title)}"' if title else "")
                )
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


# The one renderer every page goes through. Named first because the three
# below are built from it.
_RENDERER = Theme()

# Every named colour, in both its light and dark form.
_COLOR_PAIR: dict[str, Theme.ColorPair] = _RENDERER.pairs()

# The one number formatter every printed number goes through.
_NUMBERS = Theme.NumberFormat()

# What each colour is actually for -- the names CSS and the pages use.
_ROLE: dict[str, str] = {
    "bg": _RENDERER.shade(_COLOR_PAIR["slate"].dark, 0.90),
    "bg-alt": _COLOR_PAIR["slate"].light,
    "panel": _COLOR_PAIR["navy"].dark,
    "nav": _COLOR_PAIR["navy"].dark,
    "sel": _COLOR_PAIR["navy"].light,
    "fg": _COLOR_PAIR["white"].light,
    "fg-dim": _COLOR_PAIR["white"].dark,
    "muted": _COLOR_PAIR["white"].dark,
    "link": _COLOR_PAIR["blue"].light,
    "accent": _COLOR_PAIR["yellow"].light,
    "bar": _COLOR_PAIR["steel"].dark,
}

# Time units, largest first -- num_time() picks the first one a value reaches.
_TIME_UNITS: tuple[Theme.TimeUnit, ...] = (
    Theme.TimeUnit("s", 1.0),
    Theme.TimeUnit("ms", 1e-3),
    Theme.TimeUnit("us", 1e-6),
    Theme.TimeUnit("ns", 1e-9),
    Theme.TimeUnit("ps", 1e-12),
)


# heat_style - The inline style one heat position paints a cell with.
def heat_style(heat: float, signed: bool = False) -> str:
    return _RENDERER.heat_style(heat, signed)


# heat_t - Turn a share into a position on the heat ramp.
def heat_t(share: float, max_share: float) -> float:
    return _RENDERER.heat_t(share, max_share)


# html_escape - Make any value safe to drop into markup.
def html_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


# num_human - A big number shortened to fit a column, e.g. 2.1K.
def num_human(number: float) -> str:
    return _NUMBERS.human(number)


# num_pct - A share as a percentage, e.g. 63.2%.
def num_pct(percent: float) -> str:
    return _NUMBERS.percent(percent)


# num_signed - A diff number with its sign, empty when it is exactly zero.
def num_signed(number: float) -> str:
    return _NUMBERS.signed(number)


# num_signed_pct - A diff share with its sign, empty when it is exactly zero.
def num_signed_pct(percent: float) -> str:
    return _NUMBERS.signed_percent(percent)


# num_time - A duration in the largest unit it reaches, e.g. 1.25ms.
def num_time(seconds: float) -> str:
    return _NUMBERS.time(seconds)


# page_document - One whole standalone page, CSS and JS inlined.
def page_document(
    title: str, body: str, extra_js: str = "", body_class: str = ""
) -> str:
    return _RENDERER.document(title, body, extra_js, body_class)


# table_render - One whole table, columns sized in exact characters.
def table_render(
    key: str,
    columns: Sequence[Column],
    rows: Sequence[Sequence[CellOrText]],
    fill: bool = False,
    header: bool = True,
) -> str:
    return _RENDERER.table(key, columns, rows, fill, header)


# theme_css - The whole stylesheet, colour variables first.
def theme_css() -> str:
    return _RENDERER.css()


# theme_js - The shared page script.
def theme_js() -> str:
    return _RENDERER.js()


# theme_runtime - The theme values a page's own JavaScript needs.
def theme_runtime() -> ThemeRuntime:
    return _RENDERER.runtime()
