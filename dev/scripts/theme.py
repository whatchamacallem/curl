from __future__ import annotations

from collections.abc import Sequence
import html
import math
import os
from typing import NamedTuple, TypeAlias, TypedDict

FONT = 'Monaco, Menlo, "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace'

HEAT: list[str] = ["#3E4A89", "#31688E", "#26828E", "#1F9E89", "#35B779", "#6DCD59",
                   "#B4DE2C", "#FDE725", "#FFC83B", "#FFA22C", "#FF7F21", "#F06142"]

HEAT_ALPHA_HIGH = 0.92
HEAT_ALPHA_LOW = 0.18
HEAT_MINIMUM_SHARE = 0.001

PADDING_CHARS = 3

THEME: list[str] = ["#1AB6FF", "#0097E6", "#F5F6FA", "#DCDDE1", "#FBC531", "#E1B12C",
                    "#7F8FA6", "#718093", "#273C75", "#192A56", "#487EB0", "#40739E",
                    "#353B48", "#2F3640"]

TITLE_COLUMNS = len("simpleformat diff / native timing")

_HERE = os.path.dirname(os.path.abspath(__file__))


class Cell(NamedTuple):
    text: str = ""
    html: str | None = None
    style: str = ""
    cls: str = ""
    title: str = ""


CellOrText: TypeAlias = Cell | str


class Column(NamedTuple):
    label: str
    title: str = ""
    numeric: bool = False
    width: int | None = None
    clip: int | None = None
    grow: bool = False


class ColorPair(NamedTuple):
    light: str
    dark: str


class Rgb(NamedTuple):
    red: int
    green: int
    blue: int


class ThemeRuntime(TypedDict):
    heat: list[str]
    bg: str
    fgLight: str
    fgDark: str


class TimeUnit(NamedTuple):
    suffix: str
    seconds: float


TIME_UNITS: tuple[TimeUnit, ...] = (TimeUnit("s", 1.0), TimeUnit("ms", 1e-3), TimeUnit("µs", 1e-6),
                                    TimeUnit("ns", 1e-9), TimeUnit("ps", 1e-12))


def _color_pairs() -> dict[str, ColorPair]:
    names = ["blue", "white", "yellow", "gray", "navy", "steel", "slate"]
    return {name: ColorPair(THEME[2 * index], THEME[2 * index + 1]) for index, name in enumerate(names)}


COLOR_PAIR: dict[str, ColorPair] = _color_pairs()


def _contrast_foreground(color: Rgb) -> str:
    return ROLE["bg"] if _luminance(color) > 0.5 else ROLE["fg"]


def _luminance(color: Rgb) -> float:
    return (0.2126 * color.red + 0.7152 * color.green + 0.0722 * color.blue) / 255


def _read(name: str) -> str:
    with open(os.path.join(_HERE, name), encoding="utf-8") as handle:
        return handle.read()


def _rgb(hex_color: str) -> Rgb:
    return Rgb(int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16))


def _shade(hex_color: str, factor: float) -> str:
    return "#" + "".join(f"{round(component * factor):02X}" for component in _rgb(hex_color))


ROLE: dict[str, str] = {
    "bg": _shade(COLOR_PAIR["slate"].dark, 0.90),
    "bg-alt": COLOR_PAIR["slate"].light,
    "panel": COLOR_PAIR["navy"].dark,
    "nav": COLOR_PAIR["navy"].dark,
    "sel": COLOR_PAIR["navy"].light,
    "fg": COLOR_PAIR["white"].light,
    "fg-dim": COLOR_PAIR["white"].dark,
    "muted": COLOR_PAIR["white"].dark,
    "link": COLOR_PAIR["blue"].light,
    "accent": COLOR_PAIR["yellow"].light,
    "bar": COLOR_PAIR["steel"].dark,
}


def _cell(value: CellOrText) -> Cell:
    return value if isinstance(value, Cell) else Cell(text=value)


def heat_style(heat: float, signed: bool = False) -> str:
    magnitude = abs(heat)
    if magnitude <= 0:
        return ""
    stops = [_rgb(color) for color in HEAT]
    if signed:
        position = (heat + 1) * 0.5 * (len(stops) - 1)
    else:
        position = heat * (len(stops) - 1)
    index = min(max(int(position), 0), len(stops) - 2)
    fraction = position - index
    amount = HEAT_ALPHA_LOW + (HEAT_ALPHA_HIGH - HEAT_ALPHA_LOW) * magnitude
    background = _rgb(ROLE["bg"])
    mixed = Rgb(*(round(background[channel]
                        + (stops[index][channel] + (stops[index + 1][channel] - stops[index][channel]) * fraction
                           - background[channel]) * amount)
                 for channel in range(3)))
    return f"background:rgb({mixed.red},{mixed.green},{mixed.blue});color:{_contrast_foreground(mixed)}"


def heat_t(share: float, max_share: float) -> float:
    sign = -1.0 if share < 0 else 1.0
    magnitude = abs(share)
    if magnitude < HEAT_MINIMUM_SHARE:
        return 0.0
    top = max(max_share, HEAT_MINIMUM_SHARE * 10) / HEAT_MINIMUM_SHARE
    return sign * min(1.0, math.log10(magnitude / HEAT_MINIMUM_SHARE) / math.log10(top))


def html_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def num_human(number: float) -> str:
    value, unit = float(number), ""
    for candidate in ("K", "M", "G", "T"):
        if value < 999.5:
            break
        value /= 1000
        unit = candidate
    return f"{value:.1f}{unit}" if unit and value < 9.95 else f"{value:.0f}{unit}"


def num_pct(percent: float) -> str:
    if percent >= 9.95:
        return f"{percent:.1f}%"
    if percent >= 0.01:
        return f"{percent:.2f}%"
    return "<0.01%" if percent > 0 else ""


def num_signed(number: float) -> str:
    if number == 0:
        return ""
    return ("+" if number > 0 else "-") + num_human(abs(number))


def num_signed_pct(percent: float) -> str:
    if percent == 0:
        return ""
    return ("+" if percent > 0 else "-") + num_pct(abs(percent))


def num_time(seconds: float) -> str:
    if seconds == 0:
        return "0.00s"
    sign = "-" if seconds < 0 else ""
    magnitude = abs(seconds)
    unit = next((candidate for candidate in TIME_UNITS if magnitude >= candidate.seconds), TIME_UNITS[-1])
    return f"{sign}{magnitude / unit.seconds:.2f}{unit.suffix}"


def page_document(title: str, body: str, extra_js: str = "", body_class: str = "") -> str:
    body_attr = f' class="{body_class}"' if body_class else ""
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{html_escape(title)}</title>\n<style>\n{theme_css()}</style>\n</head>\n"
            f"<body{body_attr}>\n{body}\n"
            f"<script>\n{theme_js()}</script>\n"
            + (f"<script>\n{extra_js}</script>\n" if extra_js else "")
            + "</body>\n</html>\n")


def table_render(key: str, columns: Sequence[Column], rows: Sequence[Sequence[CellOrText]], fill: bool = False,
                 header: bool = True) -> str:
    cells = [[_cell(value) for value in row] for row in rows]
    for row in cells:
        if len(row) > len(columns):
            raise ValueError(f"table {key!r}: a row has {len(row)} cells for {len(columns)} columns")
    grow_index = next((index for index, column in enumerate(columns) if column.grow), len(columns) - 1) \
        if fill else -1
    widths: list[int] = []
    for index, column in enumerate(columns):
        width = len(column.label)
        if column.width is not None:
            width = max(width, column.width)
        elif index != grow_index:
            for row in cells:
                if index < len(row):
                    width = max(width, len(row[index].text))
            if column.clip is not None:
                width = max(len(column.label), min(width, column.clip))
        widths.append(width + PADDING_CHARS)
    out = [f'<div class="tbl{" fill" if fill else ""}">']
    table_classes = "cols" + (" fill" if fill else "")
    out.append(f'<div class="tbl-cols"><table class="{table_classes}" data-key="{html_escape(key)}"><colgroup>')
    for index, width in enumerate(widths):
        col_classes = " ".join(class_name for class_name in
                               ("alt" if index % 2 else "", "grow" if index == grow_index else "") if class_name)
        attr = f' class="{col_classes}"' if col_classes else ""
        out.append(f'<col{attr} style="width:{width}ch">')
    out.append("</colgroup>")
    if header:
        out.append("<thead><tr>")
        for column in columns:
            attrs = (' class="n"' if column.numeric else "") + \
                (f' title="{html_escape(column.title)}"' if column.title else "")
            out.append(f"<th{attrs}>{html_escape(column.label)}</th>")
        out.append("</tr></thead>")
    out.append("<tbody>")
    for row in cells:
        out.append("<tr>")
        for column, width, cell in zip(columns, widths, row):
            cell_classes = " ".join(class_name for class_name in ("n" if column.numeric else "", cell.cls) if class_name)
            title = cell.title or (cell.text if len(cell.text) + PADDING_CHARS > width else "")
            attrs = (f' class="{cell_classes}"' if cell_classes else "") \
                + (f' style="{cell.style}"' if cell.style else "") \
                + (f' title="{html_escape(title)}"' if title else "")
            out.append(f"<td{attrs}>{cell.html if cell.html is not None else html_escape(cell.text)}</td>")
        out.append("</tr>")
    out.append("</tbody></table></div>")
    out.append("</div>")
    return "".join(out)


def theme_css() -> str:
    lines = [":root {"]
    for name, pair in COLOR_PAIR.items():
        lines.append(f"  --{name}: {pair.dark}; --{name}-l: {pair.light};")
    for role, color in ROLE.items():
        lines.append(f"  --{role}: {color};")
    lines.append(f"  --hot: {HEAT[-1]};")
    lines.append(f"  --hot-fg: {_contrast_foreground(_rgb(HEAT[-1]))};")
    lines.append(f"  --title-bg: {HEAT[2]};")
    lines.append(f"  --title-fg: {_contrast_foreground(_rgb(HEAT[2]))};")
    lines.append(f"  --title-w: calc({TITLE_COLUMNS}ch + 16px);")
    lines.append(f"  --font: {FONT};")
    lines.append("}")
    return "\n".join(lines) + "\n" + _read("theme.css")


def theme_js() -> str:
    return _read("theme.js")


def theme_runtime() -> ThemeRuntime:
    return {"heat": HEAT, "bg": ROLE["bg"], "fgLight": ROLE["fg"], "fgDark": ROLE["bg"]}
