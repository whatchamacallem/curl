"""Shared look and feel for every page dev/profile.sh writes.

The two palettes are the ones pinned in dev/CLAUDE.md under "User settings":

* HEAT is the 12-stop cold-to-hot ramp used wherever a number is colored by
  its share of a total (heat-map lines, the file tree, hottest-line and
  hottest-function tables). Speedscope keeps its own colors.
* THEME is the 20-color UI palette, ten light/dark pairs. The dark member
  of each pair is the default; the light member shades alternating table
  columns and lifts contrast where the dark one would be hard to read on
  the dark background.

theme.css and theme.js next to this file are the shared stylesheet and
script. css() and js() return them (the palette expanded into CSS
variables) so each generator can inline them into its page: reports are
opened from file:// and nothing may be fetched at view time, so there is
no shared file to link to. table() renders the one table markup every page
uses (fixed layout, widths in characters, alternating column shading, a
plain-language legend, draggable divider bars via theme.js).
"""
from __future__ import annotations

import html
import math
import os
from dataclasses import dataclass

HEAT = ["#3E4A89", "#31688E", "#26828E", "#1F9E89", "#35B779", "#6DCD59",
        "#B4DE2C", "#FDE725", "#FFC83B", "#FFA22C", "#FF7F21", "#F06142"]

THEME = ["#00A8FF", "#0097E6", "#E84118", "#C23616", "#9C88FF", "#8C7AE6",
         "#F5F6FA", "#DCDDE1", "#FBC531", "#E1B12C", "#7F8FA6", "#718093",
         "#4CD137", "#44BD32", "#273C75", "#192A56", "#487EB0", "#40739E",
         "#353B48", "#2F3640"]

# (light, dark) pairs, in THEME order
PAIR = {name: (THEME[2 * i], THEME[2 * i + 1]) for i, name in enumerate(
    ["blue", "red", "purple", "white", "yellow", "gray", "green", "navy", "steel", "slate"])}

# semantic roles -> palette member
ROLE = {
    "bg": PAIR["slate"][1],       # page background
    "bg-alt": PAIR["slate"][0],   # alternating table columns
    "panel": PAIR["navy"][1],     # table headers, legends, header bars
    "nav": PAIR["navy"][1],       # toolbar strip
    "sel": PAIR["navy"][0],       # selected row
    "fg": PAIR["white"][0],       # body text (light member: contrast on the dark background)
    "fg-dim": PAIR["white"][1],   # headings, table headers
    "muted": PAIR["gray"][0],     # secondary text (light member, same reason)
    "link": PAIR["blue"][0],      # links (light member, same reason)
    "link-bg": PAIR["blue"][1],   # link hover background
    "accent": PAIR["yellow"][0],  # title, active toolbar link, active divider
    "bar": PAIR["steel"][1],      # column divider bars, borders
    "bar-hot": PAIR["yellow"][0],
    "good": PAIR["green"][1],
    "bad": PAIR["red"][1],
}

FONT = 'Monaco, Menlo, "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace'

_HERE = os.path.dirname(os.path.abspath(__file__))


def _read(name: str) -> str:
    with open(os.path.join(_HERE, name), encoding="utf-8") as f:
        return f.read()


def css() -> str:
    """The :root palette plus theme.css, ready to inline in a <style>."""
    lines = [":root {"]
    for name, (light, dark) in PAIR.items():
        lines.append(f"  --{name}: {dark}; --{name}-l: {light};")
    for role, color in ROLE.items():
        lines.append(f"  --{role}: {color};")
    lines.append(f"  --heat: linear-gradient(90deg, {', '.join(HEAT)});")
    lines.append(f"  --font: {FONT};")
    lines.append("}")
    return "\n".join(lines) + "\n" + _read("theme.css")


def js() -> str:
    """theme.js, ready to inline in a <script>."""
    return _read("theme.js")


def runtime() -> dict:
    """What a page that colors at runtime needs (see heatStyle in theme.js)."""
    return {"heat": HEAT, "bg": ROLE["bg"], "fgLight": ROLE["fg"], "fgDark": ROLE["bg"]}


# --------------------------------------------------------------------------
# Heat coloring (theme.js carries the same math for pages that color at
# runtime; keep the two in step)
# --------------------------------------------------------------------------

HEAT_MIN_PCT = 0.001  # shares below this stay uncolored on the log scale


def heat_t(pct: float, max_pct: float) -> float:
    """Position on the ramp, 0..1, log scale from HEAT_MIN_PCT to max_pct."""
    if pct <= 0 or pct < HEAT_MIN_PCT:
        return 0.0
    top = max(max_pct, HEAT_MIN_PCT * 10) / HEAT_MIN_PCT
    return min(1.0, math.log10(pct / HEAT_MIN_PCT) / math.log10(top))


def _rgb(hex_color: str) -> tuple[int, int, int]:
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def heat_style(t: float, alpha: tuple[float, float] = (0.18, 0.92)) -> str:
    """Inline style for a cell at ramp position t: the ramp color blended
    over the page background (alpha grows with t) and a text color chosen
    for contrast against the result."""
    if t <= 0:
        return ""
    stops = [_rgb(c) for c in HEAT]
    x = t * (len(stops) - 1)
    i = min(int(x), len(stops) - 2)
    f = x - i
    a = alpha[0] + (alpha[1] - alpha[0]) * t
    bg = _rgb(ROLE["bg"])
    mix = []
    for k in range(3):
        c = stops[i][k] + (stops[i + 1][k] - stops[i][k]) * f
        mix.append(round(bg[k] + (c - bg[k]) * a))
    lum = (0.2126 * mix[0] + 0.7152 * mix[1] + 0.0722 * mix[2]) / 255
    fg = ROLE["bg"] if lum > 0.5 else ROLE["fg"]
    return f"background:rgb({mix[0]},{mix[1]},{mix[2]});color:{fg}"


# --------------------------------------------------------------------------
# Markup
# --------------------------------------------------------------------------


def esc(s: object) -> str:
    return html.escape(str(s), quote=True)


@dataclass
class Col:
    label: str
    title: str = ""            # plain-language meaning; shown in the legend
    num: bool = False          # right-aligned
    width: int | None = None   # visible characters (cell padding is added)
    clip: int | None = None    # cap the content-derived width at this many characters
    cls: str = ""


@dataclass
class Cell:
    text: str = ""
    html: str | None = None    # pre-escaped markup instead of text
    style: str = ""
    cls: str = ""
    title: str = ""


def _cell(c: object) -> Cell:
    return c if isinstance(c, Cell) else Cell(text="" if c is None else str(c))


# characters added to a column's visible width: 1ch padding each side plus
# 1ch of slack for the divider bar's pixel and fractional ch rounding
PAD = 3


def table(key: str, cols: list[Col], rows: list[list[object]], fill: bool = False,
          header: bool = True, legend: bool = True) -> str:
    """A .tbl box: legend banner (from the columns' titles), then the table.

    Column widths are derived from the longest text in each column, in
    characters (everything is monospace, so this is exact), unless the
    column sets `width`; `clip` caps the derived width and clipped cells get
    their full text as a tooltip. With `fill` the last column takes the
    remaining width and the table spans its container.
    """
    cells = [[_cell(c) for c in r] for r in rows]
    widths: list[int] = []
    for i, col in enumerate(cols):
        if col.width is not None:
            widths.append(col.width + PAD)
            continue
        n = len(col.label)
        for r in cells:
            if i < len(r):
                n = max(n, len(r[i].text))
        if col.clip is not None:
            n = min(n, col.clip)
        widths.append(n + PAD)
    out = ['<div class="tbl">']
    entries = [f"<span><b>{esc(c.label)}</b> {esc(c.title)}</span>" for c in cols if c.title]
    if legend and entries:
        out.append(f'<div class="tbl-legend band">{"".join(entries)}</div>')
    out.append(f'<div class="tbl-cols"><table class="cols{" fill" if fill else ""}" data-key="{esc(key)}"><colgroup>')
    for i, w in enumerate(widths):
        alt = ' class="alt"' if i % 2 else ""
        style = "" if fill and i == len(widths) - 1 else f' style="width:{w}ch"'
        out.append(f"<col{alt}{style}>")
    out.append("</colgroup>")
    if header:
        out.append("<thead><tr>")
        for c in cols:
            attrs = (' class="n"' if c.num else "") + (f' title="{esc(c.title)}"' if c.title else "")
            out.append(f"<th{attrs}>{esc(c.label)}</th>")
        out.append("</tr></thead>")
    out.append("<tbody>")
    for r in cells:
        out.append("<tr>")
        for i, c in enumerate(r):
            col = cols[i] if i < len(cols) else Col("")
            cls = " ".join(x for x in ("n" if col.num else "", col.cls, c.cls) if x)
            title = c.title or (c.text if len(c.text) + PAD > widths[i] else "")
            attrs = (f' class="{cls}"' if cls else "") + (f' style="{c.style}"' if c.style else "") \
                + (f' title="{esc(title)}"' if title else "")
            out.append(f"<td{attrs}>{c.html if c.html is not None else esc(c.text)}</td>")
        out.append("</tr>")
    out.append("</tbody></table></div></div>")
    return "".join(out)


def document(title: str, body: str, extra_css: str = "", extra_js: str = "", body_class: str = "") -> str:
    """A complete page: shared style and script inlined, then `body`."""
    body_attr = f' class="{body_class}"' if body_class else ""
    return ("<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
            f"<title>{esc(title)}</title>\n<style>\n{css()}{extra_css}</style>\n</head>\n"
            f"<body{body_attr}>\n{body}\n"
            f"<script>\n{js()}</script>\n"
            + (f"<script>\n{extra_js}</script>\n" if extra_js else "")
            + "</body>\n</html>\n")
