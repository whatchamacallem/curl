from __future__ import annotations

import html
import math
import os
from collections.abc import Sequence
from typing import NamedTuple, TypeAlias, TypedDict

HEAT: list[str] = ["#3E4A89", "#31688E", "#26828E", "#1F9E89", "#35B779", "#6DCD59",
                   "#B4DE2C", "#FDE725", "#FFC83B", "#FFA22C", "#FF7F21", "#F06142"]

THEME: list[str] = ["#00A8FF", "#0097E6", "#F5F6FA", "#DCDDE1", "#FBC531", "#E1B12C",
                    "#7F8FA6", "#718093", "#273C75", "#192A56", "#487EB0", "#40739E",
                    "#353B48", "#2F3640"]


class Pair(NamedTuple):
    light: str
    dark: str


PAIR: dict[str, Pair] = {name: Pair(THEME[2 * i], THEME[2 * i + 1]) for i, name in enumerate(
    ["blue", "white", "yellow", "gray", "navy", "steel", "slate"])}


class RGB(NamedTuple):
    r: int
    g: int
    b: int


def _rgb(hex_color: str) -> RGB:
    return RGB(int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16))


def _shade(hex_color: str, factor: float) -> str:
    return "#" + "".join(f"{round(c * factor):02X}" for c in _rgb(hex_color))


ROLE: dict[str, str] = {
    "bg": _shade(PAIR["slate"].dark, 0.90),
    "bg-alt": PAIR["slate"].light,
    "panel": PAIR["navy"].dark,
    "nav": PAIR["navy"].dark,
    "sel": PAIR["navy"].light,
    "fg": PAIR["white"].light,
    "fg-dim": PAIR["white"].dark,
    "muted": PAIR["gray"].light,
    "link": PAIR["blue"].light,
    "accent": PAIR["yellow"].light,
    "bar": PAIR["steel"].dark,
}

FONT = 'Monaco, Menlo, "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace'

TITLE_COLS = len("simpleformat / native timing")

_HERE = os.path.dirname(os.path.abspath(__file__))


def _read(name: str) -> str:
    with open(os.path.join(_HERE, name), encoding="utf-8") as f:
        return f.read()


def _luminance(c: RGB) -> float:
    return (0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b) / 255


def _contrast_fg(c: RGB) -> str:
    return ROLE["bg"] if _luminance(c) > 0.5 else ROLE["fg"]


def theme_css() -> str:
    lines = [":root {"]
    for name, pair in PAIR.items():
        lines.append(f"  --{name}: {pair.dark}; --{name}-l: {pair.light};")
    for role, color in ROLE.items():
        lines.append(f"  --{role}: {color};")
    lines.append(f"  --hot: {HEAT[-1]};")
    lines.append(f"  --hot-fg: {_contrast_fg(_rgb(HEAT[-1]))};")
    lines.append(f"  --title-bg: {HEAT[2]};")
    lines.append(f"  --title-fg: {_contrast_fg(_rgb(HEAT[2]))};")
    lines.append(f"  --title-w: calc({TITLE_COLS}ch + 16px);")
    lines.append(f"  --font: {FONT};")
    lines.append("}")
    return "\n".join(lines) + "\n" + _read("theme.css")


def theme_js() -> str:
    return _read("theme.js")


class ThemeRuntime(TypedDict):
    heat: list[str]
    bg: str
    fgLight: str
    fgDark: str


def theme_runtime() -> ThemeRuntime:
    return {"heat": HEAT, "bg": ROLE["bg"], "fgLight": ROLE["fg"], "fgDark": ROLE["bg"]}


HEAT_MIN_PCT = 0.001


def heat_t(pct: float, max_pct: float) -> float:
    if pct < HEAT_MIN_PCT:
        return 0.0
    top = max(max_pct, HEAT_MIN_PCT * 10) / HEAT_MIN_PCT
    return min(1.0, math.log10(pct / HEAT_MIN_PCT) / math.log10(top))


class Alpha(NamedTuple):
    lo: float
    hi: float


def heat_style(t: float, alpha: Alpha = Alpha(0.18, 0.92)) -> str:
    if t <= 0:
        return ""
    stops = [_rgb(c) for c in HEAT]
    x = t * (len(stops) - 1)
    i = min(int(x), len(stops) - 2)
    f = x - i
    a = alpha.lo + (alpha.hi - alpha.lo) * t
    bg = _rgb(ROLE["bg"])
    mix = RGB(*(round(bg[k] + (stops[i][k] + (stops[i + 1][k] - stops[i][k]) * f - bg[k]) * a) for k in range(3)))
    return f"background:rgb({mix.r},{mix.g},{mix.b});color:{_contrast_fg(mix)}"


def num_human(n: float) -> str:
    v, unit = float(n), ""
    for u in ("K", "M", "G", "T"):
        if v < 999.5:
            break
        v /= 1000
        unit = u
    return f"{v:.1f}{unit}" if unit and v < 9.95 else f"{v:.0f}{unit}"


def num_pct(p: float) -> str:
    if p >= 9.95:
        return f"{p:.1f}%"
    if p >= 0.01:
        return f"{p:.2f}%"
    return "<0.01%" if p > 0 else ""


class TimeUnit(NamedTuple):
    suffix: str
    seconds: float


TIME_UNITS: tuple[TimeUnit, ...] = (TimeUnit("s", 1.0), TimeUnit("ms", 1e-3), TimeUnit("µs", 1e-6),
                                    TimeUnit("ns", 1e-9), TimeUnit("ps", 1e-12))


def num_time(seconds: float) -> str:
    if seconds == 0:
        return "0.00s"
    sign = "-" if seconds < 0 else ""
    v = abs(seconds)
    unit = next((u for u in TIME_UNITS if v >= u.seconds), TIME_UNITS[-1])
    return f"{sign}{v / unit.seconds:.2f}{unit.suffix}"


def html_esc(s: object) -> str:
    return html.escape(str(s), quote=True)


class Col(NamedTuple):
    label: str
    title: str = ""
    num: bool = False
    width: int | None = None
    clip: int | None = None
    cls: str = ""
    grow: bool = False


class Cell(NamedTuple):
    text: str = ""
    html: str | None = None
    style: str = ""
    cls: str = ""
    title: str = ""


CellLike: TypeAlias = Cell | str


def _cell(c: CellLike) -> Cell:
    return c if isinstance(c, Cell) else Cell(text=c)


PAD = 3


def table_render(key: str, cols: Sequence[Col], rows: Sequence[Sequence[CellLike]], fill: bool = False,
                 header: bool = True, lines: bool = False) -> str:
    cells = [[_cell(c) for c in r] for r in rows]
    for r in cells:
        if len(r) > len(cols):
            raise ValueError(f"table {key!r}: a row has {len(r)} cells for {len(cols)} columns")
    grow = next((i for i, c in enumerate(cols) if c.grow), len(cols) - 1) if fill else -1
    widths: list[int] = []
    for i, col in enumerate(cols):
        n = len(col.label)
        if col.width is not None:
            n = max(n, col.width)
        elif i != grow:
            for r in cells:
                if i < len(r):
                    n = max(n, len(r[i].text))
            if col.clip is not None:
                n = max(len(col.label), min(n, col.clip))
        widths.append(n + PAD)
    out = [f'<div class="tbl{" fill" if fill else ""}">']
    classes = "cols" + (" fill" if fill else "") + (" lines" if lines else "")
    out.append(f'<div class="tbl-cols"><table class="{classes}" data-key="{html_esc(key)}"><colgroup>')
    for i, w in enumerate(widths):
        cls = " ".join(x for x in ("alt" if i % 2 else "", "grow" if i == grow else "") if x)
        attr = f' class="{cls}"' if cls else ""
        out.append(f'<col{attr} style="width:{w}ch">')
    out.append("</colgroup>")
    if header:
        out.append("<thead><tr>")
        for c in cols:
            attrs = (' class="n"' if c.num else "") + (f' title="{html_esc(c.title)}"' if c.title else "")
            out.append(f"<th{attrs}>{html_esc(c.label)}</th>")
        out.append("</tr></thead>")
    out.append("<tbody>")
    for r in cells:
        out.append("<tr>")
        for col, w, c in zip(cols, widths, r):
            cls = " ".join(x for x in ("n" if col.num else "", col.cls, c.cls) if x)
            title = c.title or (c.text if len(c.text) + PAD > w else "")
            attrs = (f' class="{cls}"' if cls else "") + (f' style="{c.style}"' if c.style else "") \
                + (f' title="{html_esc(title)}"' if title else "")
            out.append(f"<td{attrs}>{c.html if c.html is not None else html_esc(c.text)}</td>")
        out.append("</tr>")
    out.append("</tbody></table></div>")
    out.append("</div>")
    return "".join(out)


def page_document(title: str, body: str, extra_css: str = "", extra_js: str = "", body_class: str = "") -> str:
    body_attr = f' class="{body_class}"' if body_class else ""
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{html_esc(title)}</title>\n<style>\n{theme_css()}{extra_css}</style>\n</head>\n"
            f"<body{body_attr}>\n{body}\n"
            f"<script>\n{theme_js()}</script>\n"
            + (f"<script>\n{extra_js}</script>\n" if extra_js else "")
            + "</body>\n</html>\n")
