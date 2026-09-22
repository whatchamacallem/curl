from __future__ import annotations

import html, math, os
from collections.abc import Sequence
from typing import NamedTuple, TypeAlias, TypedDict

import settings

# All constants needed from settings.py have to be loaded here before anything
# else.
_ASSET_ERROR_OVERLAY_SCRIPT_NAME: str = ""
_ASSET_FRAME_SCRIPT_NAME: str = ""
_ASSET_HEAT_MAP_SCRIPT_NAME: str = ""
_ASSET_HEAT_MAP_STYLESHEET_NAME: str = ""
_ASSET_REPORT_MANIFEST_SCRIPT_NAME: str = ""
_ASSET_SETTINGS_SCRIPT_NAME: str = ""
_ASSET_THEME_SCRIPT_NAME: str = ""
_ASSET_THEME_STYLESHEET_NAME: str = ""
_ASSET_UI_STRINGS_SCRIPT_NAME: str = ""
_HEAT_COLOR_ALPHA_HIGHEST: float = 0.0
_HEAT_COLOR_ALPHA_LOWEST: float = 0.0
_HEAT_COLOR_LOGO_STOPS: list[str] = []
_HEAT_COLOR_SMALLEST_VISIBLE_SHARE: float = 0.0
_NUMBER_SMALLEST_PRINTED_PERCENT: float = 0.0
_PAGE_FONT_FAMILY: str = ""
_REPORT_ASSETS_DIR_NAME: str = ""
_STRIP_STATUS_ROW_WIDTH_CHARS: int = 0
_TABLE_COLUMN_EXTRA_WIDTH_CHARS: int = 0
_THEME_COLOR_PAIR_ENTRIES: list[str] = []
_THEME_COLOR_PAIR_NAMES: tuple[str, ...] = ()
_THEME_COLOR_ROLE_BACKGROUND_SHADE_FACTOR: float = 0.0
_THEME_COLOR_ROLE_SOURCES: dict[str, tuple[str, str]] = {}
_THEME_TIME_UNIT_ENTRIES: tuple[tuple[str, float], ...] = ()
settings.load_into(__name__)


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
    # the header text, and every column's width floor
    label: str
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
        # 2.1K / 2.0G -- short enough to fit a column.
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

        # An unsigned share, as a percentage up to 100% and a multiple
        # above it: 1.30x. Anything past 99.99x is just ">1000x".
        def multiple(self, percent: float) -> str:
            if percent <= 100:
                return self.percent(percent)
            times = percent / 100
            return f"{times:.2f}x" if times < 99.99 else ">1000x"

        # 63.2% / <0.01%, and an empty cell rather than a bare 0%.
        def percent(self, percent: float) -> str:
            if percent >= 9.95:
                return f"{percent:.1f}%"
            if percent >= _NUMBER_SMALLEST_PRINTED_PERCENT:
                return f"{percent:.2f}%"
            return "<0.01%" if percent > 0 else ""

        # A diff number: same as human(), and empty at zero. Only a drop
        # is marked, with "-". A rise carries no "+".
        def signed(self, number: float) -> str:
            if number == 0:
                return ""
            return ("-" if number < 0 else "") + self.human(abs(number))

        # A diff share: percent(), empty at zero, arrow-led, a drop keeping
        # its "-". A zero baseline is an infinite share, "∞%". "≈0.00%" and
        # ">1000x" are bounds, so take no sign. README.md's "Reading a Diff
        # Report" is the specification, and theme.js's signed_percent_text
        # is kept in step with this.
        def signed_percent(self, percent: float) -> str:
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
                    for candidate in _TIME_UNITS
                    if magnitude >= candidate.seconds
                ),
                _TIME_UNITS[-1],
            )
            return f"{sign}{magnitude / unit.seconds:.2f}{unit.suffix}"

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
            (_ASSET_SETTINGS_SCRIPT_NAME, settings.settings_script_write()),
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

    # Take bare text as a plain Cell, and leave a real Cell alone.
    def cell(self, value: CellOrText) -> Cell:
        return value if isinstance(value, Cell) else Cell(text=value)

    # How wide each column ends up: its title is always the floor.
    def column_widths(
        self,
        columns: Sequence[Column],
        rows: Sequence[Sequence[Cell]],
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
            widths.append(width + _TABLE_COLUMN_EXTRA_WIDTH_CHARS)
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
        stops = _HEAT_COLOR_LOGO_STOPS
        lines.append(f"  --hot: {stops[-1]};")
        lines.append(
            f"  --hot-fg: {self.contrast_foreground(self.rgb(stops[-1]))};"
        )
        lines.append(f"  --title-bg: {stops[2]};")
        lines.append(
            f"  --title-fg: {self.contrast_foreground(self.rgb(stops[2]))};"
        )
        lines.append(
            f"  --title-w: calc({_STRIP_STATUS_ROW_WIDTH_CHARS}ch + 16px);"
        )
        lines.append(f"  --font: {_PAGE_FONT_FAMILY};")
        lines.append("}")
        return (
            "\n".join(lines)
            + "\n"
            + self.asset_read(_ASSET_THEME_STYLESHEET_NAME)
        )

    # One page.
    def document(
        self,
        title: str,
        body: str,
        extra_js: Sequence[str] = (),
        body_class: str = "",
        depth: int = 0,
    ) -> str:
        assets_href = shared_href(depth, _REPORT_ASSETS_DIR_NAME)
        body_attr = f' class="{body_class}"' if body_class else ""
        head = (
            '<link rel="stylesheet" '
            f'href="{assets_href}/{_ASSET_THEME_STYLESHEET_NAME}">\n'
        )
        script = "".join(
            f'<script src="{assets_href}/{name}"></script>\n'
            for name in (
                *page_preamble_scripts(),
                _ASSET_SETTINGS_SCRIPT_NAME,
                _ASSET_THEME_SCRIPT_NAME,
                *extra_js,
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

    # Blend a heat position over the page background and pick readable text.
    def heat_style(self, heat: float, signed: bool = False) -> str:
        magnitude = abs(heat)
        if magnitude <= 0:
            return ""
        stops = [self.rgb(color) for color in _HEAT_COLOR_LOGO_STOPS]
        if signed:
            position = (heat + 1) * 0.5 * (len(stops) - 1)
        else:
            position = heat * (len(stops) - 1)
        index = min(max(int(position), 0), len(stops) - 2)
        fraction = position - index
        lowest = _HEAT_COLOR_ALPHA_LOWEST
        amount = lowest + (_HEAT_COLOR_ALPHA_HIGHEST - lowest) * magnitude
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
        smallest = _HEAT_COLOR_SMALLEST_VISIBLE_SHARE
        if magnitude < smallest:
            return 0.0
        top = max(max_share, smallest * 10) / smallest
        return sign * min(
            1.0, math.log10(magnitude / smallest) / math.log10(top)
        )

    # The shared page script, read straight off disk.
    def js(self) -> str:
        return self.asset_read(_ASSET_THEME_SCRIPT_NAME)

    # How bright a colour looks, 0..1 -- what contrast_foreground() decides on.
    def luminance(self, color: Theme.Rgb) -> float:
        return (
            0.2126 * color.red + 0.7152 * color.green + 0.0722 * color.blue
        ) / 255

    # Cut _THEME_COLOR_PAIR_ENTRIES into its named light/dark pairs.
    def pairs(self) -> dict[str, Theme.ColorPair]:
        entries = _THEME_COLOR_PAIR_ENTRIES
        names = _THEME_COLOR_PAIR_NAMES
        if len(entries) != 2 * len(names):
            raise ValueError(
                f"THEME_COLOR_PAIR_ENTRIES holds {len(entries)} colours, "
                f"which is not two for each of the {len(names)} "
                "THEME_COLOR_PAIR_NAMES"
            )
        return {
            name: Theme.ColorPair(entries[2 * index], entries[2 * index + 1])
            for index, name in enumerate(names)
        }

    # Split "#RRGGBB" into channels.
    def rgb(self, hex_color: str) -> Theme.Rgb:
        return Theme.Rgb(
            int(hex_color[1:3], 16),
            int(hex_color[3:5], 16),
            int(hex_color[5:7], 16),
        )

    # Resolve _THEME_COLOR_ROLE_SOURCES into each role's colour. "bg" alone
    # is not its pair's member, but that member shaded darker.
    def roles(self, pairs: dict[str, Theme.ColorPair]) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for role, (pair_name, member) in _THEME_COLOR_ROLE_SOURCES.items():
            color = getattr(pairs[pair_name], member)
            if role == "bg":
                color = self.shade(
                    color, _THEME_COLOR_ROLE_BACKGROUND_SHADE_FACTOR
                )
            resolved[role] = color
        return resolved

    # The handful of theme values the page's own JavaScript needs.
    def runtime(self) -> ThemeRuntime:
        return {
            "heat": _HEAT_COLOR_LOGO_STOPS,
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
        column_titles: bool = True,
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
            floor = len(columns[index].label) + _TABLE_COLUMN_EXTRA_WIDTH_CHARS
            out.append(
                f'<col{attr} data-min="{floor}ch" style="width:{width}ch">'
            )
        out.append("</colgroup>")
        if column_titles:
            out.append("<thead><tr>")
            for column in columns:
                attrs = ' class="n"' if column.numeric else ""
                out.append(f"<th{attrs}>{html_escape(column.label)}</th>")
            out.append("</tr></thead>")
        out.append("<tbody>")
        for row in cells:
            out.append("<tr>")
            for column, cell in zip(columns, row, strict=True):
                cell_classes = " ".join(
                    class_name
                    for class_name in ("n" if column.numeric else "", cell.cls)
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

    # Build _THEME_TIME_UNIT_ENTRIES into the ladder NumberFormat.time()
    # walks, largest unit first.
    def time_units(self) -> tuple[Theme.TimeUnit, ...]:
        return tuple(
            Theme.TimeUnit(suffix, seconds)
            for suffix, seconds in _THEME_TIME_UNIT_ENTRIES
        )


# The one renderer every page goes through. Named first because the four
# below are built from it.
_RENDERER = Theme()

# Every named colour, in both its light and dark form.
_COLOR_PAIR: dict[str, Theme.ColorPair] = _RENDERER.pairs()

# The one number formatter every printed number goes through.
_NUMBERS = Theme.NumberFormat()

# What each colour is actually for -- the names CSS and the pages use.
_ROLE: dict[str, str] = _RENDERER.roles(_COLOR_PAIR)

# Time units, largest first -- num_time() picks the first one a value reaches.
_TIME_UNITS: tuple[Theme.TimeUnit, ...] = _RENDERER.time_units()


# asset_text_read - One file from scripts/, to inline into a page.
def asset_text_read(name: str) -> str:
    return _RENDERER.asset_read(name)


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


# page_document - One whole page, linking the report's shared theme.
def page_document(
    title: str,
    body: str,
    extra_js: Sequence[str] = (),
    body_class: str = "",
    depth: int = 0,
) -> str:
    return _RENDERER.document(title, body, extra_js, body_class, depth)


# page_preamble_scripts - The scripts every page links before any other,
# in this order. The error overlay installs the window handlers that turn
# a thrown error into a readable page, so nothing that can throw may
# precede it; the manifest script only assigns a global, and sits second
# so the overlay has the report's identity to print. Both are shared
# assets, so the report carries one copy of each.
def page_preamble_scripts() -> tuple[str, ...]:
    return (
        _ASSET_ERROR_OVERLAY_SCRIPT_NAME,
        _ASSET_REPORT_MANIFEST_SCRIPT_NAME,
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
    return _RENDERER.table(key, columns, rows, fill, column_titles)


# theme_assets_write - Write the report's one shared copy of the theme.
def theme_assets_write(out_dir: str) -> None:
    _RENDERER.assets_write(out_dir)


# theme_runtime - The theme values a page's own JavaScript needs.
def theme_runtime() -> ThemeRuntime:
    return _RENDERER.runtime()
