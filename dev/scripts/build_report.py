#!/usr/bin/env python3
"""The report pages around the flame graph and the heat map.

  build_report.py test CALLGRIND -o OUT/index.html --test NAME [--log FILE]
      [--meta LABEL=VALUE ...] [--top 20] [--callers 6] [--repo-root .]
      One perf test's index page: a toolbar strip that switches between the
      summary and the sub-pages (loaded into a frame only when picked), and
      the summary itself -- meta, callgrind totals, the top-N functions by
      self cost with their callers, the valgrind log.
  build_report.py timing -o OUT/perf-tool/index.html --test NAME --output FILE
      [--meta LABEL=VALUE ...]
      The native timing run: meta and the run's output.
  build_report.py overview -o OUT/index.html --test NAME[=DIR] ...
      [--meta LABEL=VALUE ...]
      The page over several tests: toolbar of tests, one row per test with
      the numbers its native run printed.

Every page inlines dev/scripts/theme.css and theme.js; nothing is fetched
when a page is opened.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import callgrind as cg  # noqa: E402
import theme  # noqa: E402
from theme import Cell, Col, esc  # noqa: E402

TITLE = "curl performance analyzer"
PERF_CHART = "https://curl.se/perf/index.html"
VIEWS = [  # (key, toolbar label, path relative to the test's index.html)
    ("flame-graph", "flame graph", "flame-graph/index.html"),
    ("heat-map", "heat map", "heat-map/index.html"),
    ("perf-tool", "native timing", "perf-tool/index.html"),
]
EXTRA_EVENTS = ["D1m", "DLm", "Bcm"]  # per-function miss columns, when the profile has them
SYMBOL_CHARS = 20                     # visible characters of a function name before it is cut off

FRAME_JS = """\
// Toolbar: a link with data-view loads its page into the frame (only when
// picked, never up front); [summary] shows this page again. The choice lives
// in the hash so it survives reload and can be linked to. Links inside the
// summary that point at a sub-page (a location in the heat map) open there.
// [reset columns] drops every saved column width, here and (by message, the
// iframe is another file:// origin) in the page loaded into the frame.
(function () {
  const bar = document.getElementById("bar"), home = document.getElementById("home"), view = document.getElementById("view");
  const links = [...bar.querySelectorAll("a[data-view]")];
  bar.querySelector("a[data-reset]").addEventListener("click", e => {
    e.preventDefault();
    Theme.reset();
    if (view.contentWindow) view.contentWindow.postMessage("theme:reset", "*");
  });
  function show(hash) {
    const m = /^#([\\w-]+)(?:=(.*))?$/.exec(hash);
    const key = m ? m[1] : "", link = links.find(a => a.dataset.view === key);
    for (const a of links) a.classList.toggle("on", a === (link || links[0]));
    if (!link || !key) { view.hidden = true; home.hidden = false; return; }
    const src = link.getAttribute("href") + (m[2] ? "#" + decodeURIComponent(m[2]) : "");
    if (view.dataset.src !== src) { view.src = src; view.dataset.src = src; }
    home.hidden = true; view.hidden = false;
  }
  function hashFor(href) {
    for (const a of links) {
      const base = a.getAttribute("href");
      if (a.dataset.view && href.startsWith(base)) {
        const rest = href.slice(base.length);
        return "#" + a.dataset.view + (rest.startsWith("#") ? "=" + encodeURIComponent(rest.slice(1)) : "");
      }
    }
    return null;
  }
  document.addEventListener("click", e => {
    const a = e.target.closest("a[href]");
    if (!a || a.target || e.ctrlKey || e.metaKey || e.shiftKey || e.button) return;
    const href = a.getAttribute("href");
    const hash = a.dataset.view != null ? (a.dataset.view ? "#" + a.dataset.view : "") : hashFor(href);
    if (hash == null) return;
    e.preventDefault();
    if (hash === (location.hash || "")) show(hash); else location.hash = hash;
  });
  window.addEventListener("hashchange", () => show(location.hash));
  show(location.hash);
})();
"""


def meta_pairs(items: list[str]) -> list[tuple[str, str]]:
    out = []
    for item in items or []:
        if "=" not in item:
            sys.exit(f"error: --meta expects LABEL=VALUE, got {item!r}")
        label, _, value = item.partition("=")
        out.append((label.strip(), value))
    return out


def read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        print(f"warning: {path}: {e}", file=sys.stderr)
        return f"(missing: {path})"


def toolbar(links: list[tuple[str, str, str]]) -> str:
    """links: (view key or "" for the summary, label, href). Then [reset columns],
    and [curl.se/perf] pushed to the far right."""
    parts = [f'<a href="{esc(href)}" data-view="{esc(key)}">[{esc(label)}]</a>' for key, label, href in links]
    parts.append('<a href="#" data-reset title="forget every saved column width">[reset columns]</a>')
    parts.append('<span class="sp"></span>')
    parts.append(f'<a href="{PERF_CHART}" target="_blank" rel="noopener">[curl.se/perf]</a>')
    return f'<nav id="bar">{"".join(parts)}</nav>'


def heading(subtitle: str) -> str:
    return (f'<header><h1>{esc(TITLE)}</h1><a href="{PERF_CHART}">{esc(PERF_CHART)}</a></header>'
            f"<h2>{esc(subtitle)}</h2>")


def meta_table(key: str, pairs: list[tuple[str, str]]) -> str:
    if not pairs:
        return ""
    rows = [[Cell(label, cls="dim"), value] for label, value in pairs]
    return theme.table(key, [Col("label"), Col("value", clip=100)], rows, header=False)


TOTALS_GROUPS = "I instruction cache, D data cache, LL last-level cache; events: every total; simulation: cache geometry used"


def totals_table(p: cg.Profile) -> str:
    cols = [Col("group", TOTALS_GROUPS), Col("metric"), Col("value", num=True), Col("detail", clip=72)]
    rows = [[Cell(g, cls="dim"), m, v, Cell(d, cls="dim")] for g, m, v, d in cg.totals_rows(p)]
    return theme.table("report.totals", cols, rows)


def display_path(repo_root: str, path: str) -> str:
    root = os.path.abspath(repo_root).rstrip("/") + "/"
    if path == "???" or not path:
        return ""
    norm = os.path.normpath(path) if os.path.isabs(path) else path
    if norm.startswith(root):
        return norm[len(root):]
    if os.path.isabs(norm) and not os.path.isfile(norm):
        return os.path.basename(norm)
    return norm


def functions_table(p: cg.Profile, event: str, top: int, ncallers: int, repo_root: str) -> str:
    """Top-N functions by self cost; under each, its callers by call count.
    The function/caller column is cut off at SYMBOL_CHARS characters; the
    divider bars are draggable (theme.js)."""
    total = p.value(p.totals(), event) or 1
    extras = [e for e in EXTRA_EVENTS if e in p.event_names() and p.value(p.totals(), e) > 0]

    def where(fn: str) -> tuple[str, str]:
        """(display text, heat-map link) for a function's entry line."""
        ef, el = p.fn_entry.get(fn, (p.fn_home.get(fn, "???"), 0))
        f = display_path(repo_root, ef)
        if not f:
            ob = os.path.basename(p.file_ob.get(ef, "") or "")
            return (f"[{ob}]" if ob else "", "")
        return (f"{f}:{el}" if el else f, site_link(ef, el))

    def site_link(file: str, line: int) -> str:
        f = display_path(repo_root, file)
        if not f or not line or not (os.path.isfile(os.path.join(repo_root, f)) or os.path.isfile(f)):
            return ""
        return f"heat-map/index.html#f={esc(f)}&l={line}"

    def loc_cell(text: str, href: str) -> Cell:
        return Cell(text, html=f'<a href="{href}">{esc(text)}</a>' if href else None)

    ranked = sorted(((p.value(vec, event), fn) for fn, vec in p.fn_self.items() if p.value(vec, event) > 0),
                    key=lambda t: (-t[0], t[1]))[:top]
    max_pct = 100.0 * ranked[0][0] / total if ranked else 1.0
    cols = [Col("#", "rank by self cost", num=True),
            Col("self%", f"share of all {event} spent in the function itself, not in what it calls", num=True),
            Col(event, p.event_long.get(event, ""), num=True)]
    cols += [Col(e, p.event_long.get(e, ""), num=True) for e in extras]
    cols += [Col("calls", "times the function was entered; on a caller row, calls from that caller and their share",
                 num=True),
             Col("function", f"the function, then its callers (first {SYMBOL_CHARS} characters; drag the bar for more)",
                 width=SYMBOL_CHARS),
             Col("defined at", "file:line of the function's first executed line; links open the heat map there",
                 clip=48)]
    rows: list[list[object]] = []
    for rank, (s, fn) in enumerate(ranked, 1):
        ncalls = sum(c for c, _ in p.callers.get(fn, {}).values())
        pct = 100.0 * s / total
        row: list[object] = [str(rank), Cell(f"{pct:.2f}%", style=theme.heat_style(theme.heat_t(pct, max_pct))),
                             f"{s:,}"]
        row += [f"{p.value(p.fn_self[fn], e):,}" for e in extras]
        row += [f"{ncalls:,}×" if ncalls else "", Cell(fn, title=fn), loc_cell(*where(fn))]
        rows.append(row)
        callers = sorted(p.callers.get(fn, {}).items(), key=lambda kv: (-kv[1][0], kv[0][0]))
        if not callers:
            rows.append(["", "", ""] + [""] * len(extras) + ["", Cell("(no recorded caller)", cls="dim"), ""])
        for (cfn, cfile, cline), (count, _) in callers[:ncallers]:
            share = 100.0 * count / ncalls if ncalls else 0.0
            text = display_path(repo_root, cfile)
            text = f"{text}:{cline}" if text and cline else text
            rows.append(["", "", ""] + [""] * len(extras)
                        + [Cell(f"{count:,}× {share:5.1f}%", cls="dim"), Cell(f"↳ {cfn}", cls="dim", title=cfn),
                           Cell(text, cls="dim", html=(f'<a href="{site_link(cfile, cline)}">{esc(text)}</a>'
                                                       if site_link(cfile, cline) else None))])
        if len(callers) > ncallers:
            rest = sum(c for _, (c, _) in callers[ncallers:])
            rows.append(["", "", ""] + [""] * len(extras)
                        + [Cell(f"{rest:,}×", cls="dim"),
                           Cell(f"↳ +{len(callers) - ncallers} more callers", cls="dim"), ""])
    return theme.table("report.functions", cols, rows)


def write(path: str, page: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {path} ({len(page.encode('utf-8')):,} bytes)", file=sys.stderr)


# --------------------------------------------------------------------------


def cmd_test(args: argparse.Namespace) -> None:
    with open(args.callgrind_file, encoding="utf-8", errors="replace") as f:
        p = cg.parse_callgrind(f.read())
    if not p.events:
        sys.exit("error: no 'events:' line -- not a callgrind file?")
    if args.event not in p.event_names():
        sys.exit(f"error: event {args.event!r} not in this profile ({' '.join(p.event_names())})")
    self_sum, total, ratio = cg.self_check(p)
    print(f"ratio (must be 1.0000): {ratio:.4f}", file=sys.stderr)
    if total and abs(ratio - 1.0) > 1e-6:
        sys.exit("error: per-line self cost does not add up to callgrind's summary")

    body = toolbar([("", "summary", "#")] + [(k, label, path) for k, label, path in VIEWS])
    body += '<main id="home"><div class="page">' + heading(args.test)
    body += meta_table("report.meta", meta_pairs(args.meta))
    body += "<h2>callgrind totals</h2>" + totals_table(p)
    body += (f"<h2>top {args.top} functions by self {esc(args.event)}</h2>"
             + functions_table(p, args.event, args.top, args.callers, args.repo_root))
    if args.log:
        body += f"<details><summary>valgrind log</summary><pre>{esc(read_text(args.log).rstrip())}</pre></details>"
    body += '</div></main><iframe id="view" hidden title="report page"></iframe>'
    write(args.output, theme.document(f"{TITLE}: {args.test}", body, extra_js=FRAME_JS, body_class="frame"))


def cmd_timing(args: argparse.Namespace) -> None:
    body = '<div class="page">' + heading(f"{args.test}: native timing run")
    body += meta_table("timing.meta", meta_pairs(args.meta))
    body += f"<h2>output</h2><pre>{esc(read_text(args.output_file).rstrip())}</pre></div>"
    write(args.output, theme.document(f"{TITLE}: {args.test} timing", body))


def cmd_overview(args: argparse.Namespace) -> None:
    out_dir = os.path.dirname(os.path.abspath(args.output))
    tests: list[tuple[str, str]] = []
    for item in args.test:
        name, _, d = item.partition("=")
        tests.append((name, d or os.path.join(out_dir, name)))
    # every "label: value" line a native run printed, columns in first-seen order
    keys: list[str] = []
    numbers: dict[str, dict[str, str]] = {}
    for name, d in tests:
        vals: dict[str, str] = {}
        for line in read_text(os.path.join(d, "perf-tool", "output.txt")).splitlines():
            m = re.match(r"^([A-Za-z][^:]{0,30}):\s+(.+?)\s*$", line)
            if m:
                vals[m.group(1)] = m.group(2)
                if m.group(1) not in keys:
                    keys.append(m.group(1))
        numbers[name] = vals
    cols = [Col("test", "one report per test; the toolbar switches between them")]
    cols += [Col(k, num=True) for k in keys]
    rows = [[Cell(name, html=f'<a href="{esc(name)}/index.html">{esc(name)}</a>')] + [numbers[name].get(k, "") for k in keys]
            for name, _ in tests]
    body = toolbar([("", "overview", "#")] + [(name, name, f"{name}/index.html") for name, _ in tests])
    body += '<main id="home"><div class="page">' + heading("all perf tests")
    body += meta_table("overview.meta", meta_pairs(args.meta))
    body += "<h2>native timing runs</h2>" + theme.table("overview.tests", cols, rows)
    body += '</div></main><iframe id="view" hidden title="report page"></iframe>'
    write(args.output, theme.document(TITLE, body, extra_js=FRAME_JS, body_class="frame"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("test", help="one perf test's index page")
    t.add_argument("callgrind_file")
    t.add_argument("-o", "--output", required=True)
    t.add_argument("--test", required=True, help="perf test name")
    t.add_argument("--meta", action="append", metavar="LABEL=VALUE", default=[])
    t.add_argument("--log", help="valgrind log to include")
    t.add_argument("--event", default="Ir", help="event that ranks the functions (default: Ir)")
    t.add_argument("--top", type=int, default=20)
    t.add_argument("--callers", type=int, default=6, help="callers listed per function (default: 6)")
    t.add_argument("--repo-root", default=".")
    t.set_defaults(run=cmd_test)

    n = sub.add_parser("timing", help="the native timing run page")
    n.add_argument("-o", "--output", required=True)
    n.add_argument("--test", required=True)
    n.add_argument("--output-file", required=True, help="the run's captured output")
    n.add_argument("--meta", action="append", metavar="LABEL=VALUE", default=[])
    n.set_defaults(run=cmd_timing)

    o = sub.add_parser("overview", help="the page over several tests")
    o.add_argument("-o", "--output", required=True)
    o.add_argument("--test", action="append", metavar="NAME[=DIR]", required=True,
                   help="a test and its report directory (default: NAME next to the output)")
    o.add_argument("--meta", action="append", metavar="LABEL=VALUE", default=[])
    o.set_defaults(run=cmd_overview)

    args = ap.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
