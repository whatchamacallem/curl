#!/usr/bin/env python3
"""The report pages around the flame graph and the heat map.

  build_report.py test CALLGRIND... -o OUT/index.html --test NAME [--log FILE ...]
      [--meta LABEL=VALUE ...] [--raw-data FILE ...] [--top 20] [--repo-root .]
      One perf test's index page: a strip with the page title and the links
      that switch between the summary and the sub-pages (loaded into a frame
      only when picked), and the summary itself -- meta, raw data (the
      callgrind files as relative links), the top-N functions by self cost
      with their callers, the valgrind log(s). Several callgrind files are
      merged into one profile (the "all" report).
  build_report.py timing -o OUT/perf-tool/index.html --test NAME --output-file FILE
      [--meta LABEL=VALUE ...]
      The native timing run: meta and the run's output.
  build_report.py overview -o OUT/index.html --test NAME[=DIR] ...
      [--meta LABEL=VALUE ...]
      The page over several tests: strip of tests (alphabetical), one row per
      test with the numbers its native run printed.

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
from theme import Cell, Col, html_esc  # noqa: E402

PERF_CHART = "https://curl.se/perf/index.html"
VIEWS = [  # (key, strip label, path relative to the test's index.html)
    ("flame-graph", "flame graph", "flame-graph/index.html"),
    ("heat-map", "heat map", "heat-map/index.html"),
    ("perf-tool", "native timing", "perf-tool/index.html"),
]
SYMBOL_CHARS = 20   # visible characters of a function name before it is cut off
LOG_SKIP = 9        # valgrind's banner: tool, copyright, version, command, parent
                    # pid, blank, cache warning, "For interactive control", blank

FRAME_JS = """\
// Strip: a link with data-view loads its page into the frame (only when
// picked, never up front); the first link shows this page again. The choice
// lives in the hash so it survives reload and can be linked to. Links inside
// the summary that point at a sub-page (a location in the heat map) open
// there. The title is the picked link's data-title ("urlparser / heat map");
// a page loaded into the frame that is itself a frame page sends its own
// title up and hides it, so the outermost strip carries the one title.
// [reset columns] drops every saved column width, here and (by message, the
// iframe is another file:// origin) in the page loaded into the frame.
(function () {
  const bar = document.getElementById("bar"), home = document.getElementById("home"), view = document.getElementById("view");
  const titleEl = document.getElementById("title"), links = [...bar.querySelectorAll("a[data-view]")];
  const framed = window.parent !== window;
  let title = titleEl.textContent;
  if (framed) titleEl.hidden = true;
  function setTitle(t) {
    title = t;
    titleEl.textContent = t;
    document.title = t;
    if (framed) window.parent.postMessage({ theme: "title", title: t }, "*");
  }
  const resetLink = bar.querySelector("a[data-reset]");
  if (resetLink) resetLink.addEventListener("click", e => {
    e.preventDefault();
    Theme.reset();
    if (view.contentWindow) view.contentWindow.postMessage("theme:reset", "*");
  });
  function show(hash) {
    const m = /^#([\\w-]+)(?:=(.*))?$/.exec(hash);
    const key = m ? m[1] : "", link = links.find(a => a.dataset.view === key), cur = link || links[0];
    for (const a of links) a.classList.toggle("on", a === cur);
    setTitle(cur.dataset.title);
    if (!link || !key) { view.hidden = true; home.hidden = false; return; }
    const src = link.getAttribute("href") + (m[2] ? "#" + decodeURIComponent(m[2]) : "");
    if (view.dataset.src !== src) { view.src = src; view.dataset.src = src; }
    else if (view.contentWindow) view.contentWindow.postMessage("theme:title?", "*");
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
  window.addEventListener("message", e => {
    if (e.data === "theme:title?") setTitle(title);
    else if (e.data && e.data.theme === "title" && e.source === view.contentWindow) setTitle(e.data.title);
  });
  window.addEventListener("hashchange", () => show(location.hash));
  show(location.hash);
})();
"""


def meta_parse_pairs(items: list[str]) -> list[tuple[str, str]]:
    out = []
    for item in items or []:
        if "=" not in item:
            sys.exit(f"error: --meta expects LABEL=VALUE, got {item!r}")
        label, _, value = item.partition("=")
        out.append((label.strip(), value))
    return out


def file_read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        print(f"warning: {path}: {e}", file=sys.stderr)
        return f"(missing: {path})"


def strip_render(title: str, links: list[tuple[str, str, str, str]], perf_link: bool = False, reset: bool = True) -> str:
    """The strip across the top: the title, then the links -- (view key or ""
    for the page itself, label, href, title to show when picked) -- then,
    unless `reset` is false, [reset columns], and on the top-level page only
    [curl.se/perf] pushed to the far right.

    Only one strip on screen at a time needs [reset columns] -- clicking it
    resets every table in the document plus, by posted message, every framed
    page below it, so it belongs on the outermost strip only: the overview
    page's (which is also the only strip when a single test's report is
    opened on its own). A per-test strip nested in the overview's iframe
    (report_test's own strip) omits it, since the overview strip above it
    already reaches down into that frame."""
    parts = [f'<b class="title" id="title">{html_esc(title)}</b>']
    parts += [f'<a href="{html_esc(href)}" data-view="{html_esc(key)}" data-title="{html_esc(t)}">[{html_esc(label)}]</a>'
              for key, label, href, t in links]
    if reset:
        parts.append('<a href="#" data-reset title="forget every saved column width">[reset columns]</a>')
    if perf_link:
        parts.append('<span class="sp"></span>')
        parts.append(f'<a href="{PERF_CHART}" target="_blank" rel="noopener">[curl.se/perf]</a>')
    return f'<nav id="bar" class="strip">{"".join(parts)}</nav>'


def meta_table(key: str, pairs: list[tuple[str, str]]) -> str:
    if not pairs:
        return ""
    rows = [[Cell(label, cls="dim"), value] for label, value in pairs]
    return theme.table_render(key, [Col("label"), Col("value", clip=100)], rows, header=False)


def rawdata_list(paths: list[str], out_dir: str) -> str:
    """The callgrind trace files as a plain list of links relative to the
    generated page, so the report directory can be copied elsewhere."""
    if not paths:
        return ""
    items = "".join(f'<li><a href="{html_esc(os.path.relpath(p, out_dir))}">{html_esc(os.path.basename(p))}</a></li>' for p in paths)
    return f'<p class="dim">raw data</p><ul class="rawdata">{items}</ul>'


def path_display(repo_root: str, path: str) -> str:
    root = os.path.abspath(repo_root).rstrip("/") + "/"
    if path == "???" or not path:
        return ""
    norm = os.path.normpath(path) if os.path.isabs(path) else path
    if norm.startswith(root):
        return norm[len(root):]
    if os.path.isabs(norm) and not os.path.isfile(norm):
        return os.path.basename(norm)
    return norm


def functions_table(p: cg.Profile, event: str, top: int, repo_root: str) -> str:
    """Top-N functions by self cost, one line each: share, symbol (a link to
    the heat map at its first line, cut off at SYMBOL_CHARS characters),
    times called, and its callers by share of those calls -- the last
    column takes the rest of the page and is cut off at the edge."""
    total = p.value(p.totals(), event) or 1

    def entry_link(fn: str) -> str:
        """Heat-map link to the function's first executed line, if the file is here."""
        ef, el = p.fn_entry.get(fn, (p.fn_home.get(fn, "???"), 0))
        f = path_display(repo_root, ef)
        if not f or not el or not (os.path.isfile(os.path.join(repo_root, f)) or os.path.isfile(f)):
            return ""
        return f"heat-map/index.html#f={html_esc(f)}&l={el}"

    ranked = sorted(((p.value(vec, event), fn) for fn, vec in p.fn_self.items() if p.value(vec, event) > 0),
                    key=lambda t: (-t[0], t[1]))[:top]
    max_pct = 100.0 * ranked[0][0] / total if ranked else 1.0
    cols = [Col("% self", f"share of all {event} spent in the function itself, not in what it calls", num=True),
            Col("symbol", f"the function, first {SYMBOL_CHARS} characters (drag the bar for more); "
                          "opens the heat map at its first line", width=SYMBOL_CHARS),
            Col("calls", "times the function was entered", num=True),
            Col("callers", "who called it, with the share of those calls; cut off at the edge, hover for all")]
    rows: list[list[object]] = []
    for s, fn in ranked:
        by_caller: dict[str, int] = {}
        for (cfn, _, _), (count, _) in p.callers.get(fn, {}).items():
            by_caller[cfn] = by_caller.get(cfn, 0) + count
        ncalls = sum(by_caller.values())
        share = 100.0 * s / total
        href = entry_link(fn)
        who = ", ".join(f"{cfn} ({theme.num_pct(100.0 * n / ncalls)})"
                        for cfn, n in sorted(by_caller.items(), key=lambda kv: (-kv[1], kv[0])))
        rows.append([Cell(theme.num_pct(share), style=theme.heat_style(theme.heat_t(share, max_pct))),
                     Cell(fn, title=fn, html=f'<a href="{href}">{html_esc(fn)}</a>' if href else None),
                     theme.num_human(ncalls) if ncalls else "",
                     Cell(who, title=who) if who else Cell("(no recorded caller)", cls="dim")])
    return theme.table_render("report.functions", cols, rows, fill=True, lines=True)


def log_block(path: str) -> str:
    """The valgrind log without its LOG_SKIP-line banner."""
    lines = file_read_text(path).rstrip().split("\n")[LOG_SKIP:]
    return f"<pre>{html_esc(chr(10).join(lines))}</pre>"


def page_write(path: str, page: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"wrote {path} ({len(page.encode('utf-8')):,} bytes)", file=sys.stderr)


# --------------------------------------------------------------------------


def report_test(args: argparse.Namespace) -> None:
    p = cg.profile_load(args.callgrind_file)
    if not p.events:
        sys.exit("error: no 'events:' line -- not a callgrind file?")
    if args.event not in p.event_names():
        sys.exit(f"error: event {args.event!r} not in this profile ({' '.join(p.event_names())})")
    self_sum, total, ratio = cg.profile_self_check(p)
    print(f"ratio (must be 1.0000): {ratio:.4f}", file=sys.stderr)
    if total and abs(ratio - 1.0) > 1e-6:
        sys.exit("error: per-line self cost does not add up to callgrind's summary")

    links = [("", "summary", "#", args.test)] + [(k, label, path, f"{args.test} / {label}") for k, label, path in VIEWS]
    body = strip_render(args.test, links, reset=False)
    out_dir = os.path.dirname(os.path.abspath(args.output))
    body += '<main id="home"><div class="page">' + meta_table("report.meta", meta_parse_pairs(args.meta))
    body += rawdata_list(args.raw_data, out_dir)
    body += f"<h2>top {args.top} functions by self</h2>" + functions_table(p, args.event, args.top, args.repo_root)
    if args.log:
        body += "<h2>valgrind log</h2>"
        for log in args.log:
            if len(args.log) > 1:
                body += f"<p>{html_esc(os.path.basename(log))}</p>"
            body += log_block(log)
    body += '</div></main><iframe id="view" hidden title="report page"></iframe>'
    page_write(args.output, theme.page_document(args.test, body, extra_js=FRAME_JS, body_class="frame"))


def report_timing(args: argparse.Namespace) -> None:
    body = '<div class="page">' + meta_table("timing.meta", meta_parse_pairs(args.meta))
    body += f"<h2>output</h2><pre>{html_esc(file_read_text(args.output_file).rstrip())}</pre></div>"
    page_write(args.output, theme.page_document(f"{args.test} / native timing", body))


def report_overview(args: argparse.Namespace) -> None:
    out_dir = os.path.dirname(os.path.abspath(args.output))
    tests: list[tuple[str, str]] = []
    for item in args.test:
        name, _, d = item.partition("=")
        tests.append((name, d or os.path.join(out_dir, name)))
    tests.sort()
    # every "label: value" line a native run printed, columns in first-seen order
    keys: list[str] = []
    numbers: dict[str, dict[str, str]] = {}
    for name, d in tests:
        vals: dict[str, str] = {}
        for line in file_read_text(os.path.join(d, "perf-tool", "output.txt")).splitlines():
            m = re.match(r"^([A-Za-z][^:]{0,30}):\s+(.+?)\s*$", line)
            if m:
                vals[m.group(1)] = m.group(2)
                if m.group(1) not in keys:
                    keys.append(m.group(1))
        numbers[name] = vals
    cols = [Col("one report per test")]
    cols += [Col(k, num=True) for k in keys]
    rows = [[Cell(name, html=f'<a href="{html_esc(name)}/index.html">{html_esc(name)}</a>')] + [numbers[name].get(k, "") for k in keys]
            for name, _ in tests]
    links = [("", "overview", "#", "overview")] + [(name, name, f"{name}/index.html", name) for name, _ in tests]
    body = strip_render("overview", links, perf_link=True)
    body += '<main id="home"><div class="page">' + meta_table("overview.meta", meta_parse_pairs(args.meta))
    body += "<h2>test suites</h2>" + theme.table_render("overview.tests", cols, rows)
    body += '</div></main><iframe id="view" hidden title="report page"></iframe>'
    page_write(args.output, theme.page_document("overview", body, extra_js=FRAME_JS, body_class="frame"))


def report_main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("test", help="one perf test's index page")
    t.add_argument("callgrind_file", nargs="+", help="callgrind output file(s); several are merged into one profile")
    t.add_argument("-o", "--output", required=True)
    t.add_argument("--test", required=True, help="perf test name")
    t.add_argument("--meta", action="append", metavar="LABEL=VALUE", default=[])
    t.add_argument("--raw-data", action="append", default=[], metavar="FILE",
                   help="callgrind trace file to link (repeatable); listed relative to -o")
    t.add_argument("--log", action="append", default=[], help="valgrind log to include (repeatable)")
    t.add_argument("--event", default="Ir", help="event that ranks the functions (default: Ir)")
    t.add_argument("--top", type=int, default=20)
    t.add_argument("--repo-root", default=".")
    t.set_defaults(run=report_test)

    n = sub.add_parser("timing", help="the native timing run page")
    n.add_argument("-o", "--output", required=True)
    n.add_argument("--test", required=True)
    n.add_argument("--output-file", required=True, help="the run's captured output")
    n.add_argument("--meta", action="append", metavar="LABEL=VALUE", default=[])
    n.set_defaults(run=report_timing)

    o = sub.add_parser("overview", help="the page over several tests")
    o.add_argument("-o", "--output", required=True)
    o.add_argument("--test", action="append", metavar="NAME[=DIR]", required=True,
                   help="a test and its report directory (default: NAME next to the output)")
    o.add_argument("--meta", action="append", metavar="LABEL=VALUE", default=[])
    o.set_defaults(run=report_overview)

    args = ap.parse_args()
    args.run(args)


if __name__ == "__main__":
    report_main()
