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
from urllib.parse import quote

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
// picked, never up front); the first link shows this page again. The hash
// is the whole state of this page, and of the page in the frame after it:
//   #<view>                the strip's pick, its page at its start
//   #<view>/<state>        that page at <state>: its own hash without the
//                          "#" (the heat map's f=...&l=...&e=..., or, for
//                          the overview's per-test pages, which are frame
//                          pages themselves, again <view>/<state>)
// so #urlparser/heat-map/f=lib/urlapi.c&l=1290&e=Ir reopens exactly that.
// show() renders a hash: it lights the link and puts the page into the
// frame at <state> -- with location.replace on the frame's window, never
// iframe.src, which would add a history entry of its own on top of the
// one the hash change already made, so every strip click is one "back"
// step. The frame's page is a plain hash-routed page and needs nothing
// else from here. The other way round, a page in the frame that navigates
// on its own (the heat map's file/line/event picks) posts its hash up via
// {theme:"hash", hash} after every render; sync() mirrors that into this
// page's hash with history.replaceState (a refinement of the same view,
// never a new entry) and, when this page is itself in a frame, posts the
// result on up -- so the address bar of the outermost page always spells
// out what is on screen, whichever level changed it. Links inside the
// summary that point at a sub-page (heat-map/index.html#fn=...) turn into
// that hash. The title is the picked link's data-title ("urlparser / heat
// map"); a frame page inside the frame sends its own title up and hides
// its own, so the outermost strip carries the one title; "theme:title?"
// asks it to send it again after a show() that re-lit its link without
// navigating it. "reset columns" resets every table on this page and
// posts "theme:reset-cols" into the frame for the page there.
(function () {
  const bar = document.getElementById("bar"), home = document.getElementById("home"), view = document.getElementById("view");
  const titleEl = document.getElementById("title"), links = [...bar.querySelectorAll("a[data-view]")];
  const framed = window.parent !== window;
  let title = titleEl.textContent, page = "", state = "";
  if (framed) titleEl.hidden = true;
  function setTitle(t) {
    title = t;
    titleEl.textContent = t;
    document.title = t;
    if (framed) window.parent.postMessage({ theme: "title", title: t }, "*");
  }
  // #<view>/<state> <-> [view, "#<state>"]
  function parse(hash) {
    const m = /^#([\\w-]*)(?:\\/(.*))?$/.exec(hash || "");
    return m ? [m[1], m[2] ? "#" + m[2] : ""] : ["", ""];
  }
  const build = (key, sub) => key ? "#" + key + (sub ? "/" + sub.slice(1) : "") : "";
  function sync(hash) {
    if (hash !== location.hash) history.replaceState(null, "", hash || "#");
    if (framed) window.parent.postMessage({ theme: "hash", hash: hash }, "*");
  }
  function show(hash) {
    const [key, sub] = parse(hash);
    const link = links.find(a => a.dataset.view === key), cur = link || links[0];
    for (const a of links) a.classList.toggle("on", a === cur);
    setTitle(cur.dataset.title);
    if (!link || !key) { view.hidden = true; home.hidden = false; sync(""); return; }
    const href = link.getAttribute("href");
    if (href !== page || sub !== state) view.contentWindow.location.replace(href + (sub || "#"));
    if (href === page) view.contentWindow.postMessage("theme:title?", "*");
    page = href; state = sub;
    home.hidden = true; view.hidden = false;
    sync(build(key, sub));
  }
  function hashFor(href) {
    for (const a of links) {
      const base = a.getAttribute("href");
      if (a.dataset.view && href.startsWith(base)) {
        const rest = href.slice(base.length);
        return build(a.dataset.view, rest.startsWith("#") ? rest : "");
      }
    }
    return null;
  }
  const resetCols = document.getElementById("reset-cols");
  if (resetCols) resetCols.addEventListener("click", e => {
    e.preventDefault();
    window.Theme.resetCols(home);
    if (page) view.contentWindow.postMessage("theme:reset-cols", "*");
  });
  document.addEventListener("click", e => {
    const a = e.target.closest("a[href]");
    if (!a || a === resetCols || a.target || e.ctrlKey || e.metaKey || e.shiftKey || e.button) return;
    const href = a.getAttribute("href");
    const hash = a.dataset.view != null ? build(a.dataset.view, "") : hashFor(href);
    if (hash == null) return;
    e.preventDefault();
    if (hash === (location.hash || "")) show(hash); else location.hash = hash;
  });
  window.addEventListener("message", e => {
    if (e.source === view.contentWindow) {
      if (e.data && e.data.theme === "title") setTitle(e.data.title);
      else if (e.data && e.data.theme === "hash" && page) { state = e.data.hash; sync(build(parse(location.hash)[0], state)); }
    } else if (framed && e.source === window.parent) {
      if (e.data === "theme:title?") setTitle(title);
      else if (e.data === "theme:reset-cols") {
        window.Theme.resetCols(home);
        if (page) view.contentWindow.postMessage("theme:reset-cols", "*");
      }
    }
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


def strip_render(title: str, links: list[tuple[str, str, str, str]], perf_link: bool = False) -> str:
    """The strip across the top: the title, then the links -- (view key or ""
    for the page itself, label, href, title to show when picked), each pair
    separated by its own "|" cell so highlighting a link's background never
    bleeds into the divider -- then, on the top-level page only, "reset
    columns" (restores every table on the page to its default widths;
    dragged widths themselves are still not persisted across reloads, only
    resettable within one), "help" and "curl.se/perf", pushed to the far
    right. A per-test strip nested in the overview's iframe (report_test's
    own strip) has none of those three, since the overview strip above it
    already carries them."""
    def sep() -> str:
        return '<span class="sep">|</span>'
    parts = [f'<b class="title" id="title">{html_esc(title)}</b>']
    for key, label, href, t in links:
        parts.append(sep())
        parts.append(f'<a href="{html_esc(href)}" data-view="{html_esc(key)}" data-title="{html_esc(t)}">{html_esc(label)}</a>')
    if perf_link:
        parts.append('<span class="sp"></span>')
        parts.append('<a href="#" id="reset-cols">reset columns</a>')
        parts.append(sep())
        parts.append('<a href="README.md" target="_blank">help</a>')
        parts.append(sep())
        parts.append(f'<a href="{PERF_CHART}" target="_blank" rel="noopener">curl.se/perf</a>')
    return f'<nav id="bar" class="strip">{"".join(parts)}</nav>'


def meta_table(key: str, pairs: list[tuple[str, str]]) -> str:
    if not pairs:
        return ""
    rows = [[Cell(label, cls="dim"), value] for label, value in pairs]
    return theme.table_render(key, [Col("label"), Col("value", clip=100)], rows, header=False)


def rawdata_list(paths: list[str], out_dir: str) -> str:
    """The callgrind trace files as a plain list of links relative to the
    generated page, so the report directory can be copied elsewhere.
    Collapsed under a <details> by default, matching "top N functions"'
    header color instead of a muted <p>."""
    if not paths:
        return ""
    items = "".join(f'<li><a href="{html_esc(os.path.relpath(p, out_dir))}">{html_esc(os.path.basename(p))}</a></li>' for p in paths)
    return f'<details class="sec"><summary><h2>raw data</h2></summary><ul class="rawdata">{items}</ul></details>'


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
        """Heat-map link to the function (it opens at its first executed
        line), if that line's file is here. Spelled the way the heat map's
        own enc() spells a hash value."""
        ef, el = p.fn_entry.get(fn, (p.fn_home.get(fn, "???"), 0))
        f = path_display(repo_root, ef)
        if not f or not el or not (os.path.isfile(os.path.join(repo_root, f)) or os.path.isfile(f)):
            return ""
        return "heat-map/index.html#fn=" + html_esc(quote(fn, safe="/-_.!~*'()"))

    ranked = sorted(((p.value(vec, event), fn) for fn, vec in p.fn_self.items() if p.value(vec, event) > 0),
                    key=lambda t: (-t[0], t[1]))[:top]
    max_pct = 100.0 * ranked[0][0] / total if ranked else 1.0
    # call counts are a metric of their own, colored like every other one: a
    # count's heat is its share of every call the profile recorded (each call
    # site's count, summed), log-scaled to the most-called function -- the
    # heat map's numCalls() applies the same rule
    fn_calls = {fn: sum(count for count, _ in callers.values()) for fn, callers in p.callers.items()}
    calls_total = sum(fn_calls.values()) or 1
    calls_max_pct = 100.0 * max(fn_calls.values(), default=0) / calls_total
    cols = [Col("#", "rank", num=True),
            Col("% self", f"share of all {event} spent in the function itself, not in what it calls", num=True),
            Col("symbol", f"the function, first {SYMBOL_CHARS} characters (drag the bar for more); "
                          "opens the heat map at its first line", width=SYMBOL_CHARS),
            Col("calls", "times the function was entered", num=True),
            Col("callers", "who called it, with the share of those calls; cut off at the edge, hover for all")]
    rows: list[list[object]] = []
    for rank, (s, fn) in enumerate(ranked, 1):
        by_caller: dict[str, int] = {}
        for (cfn, _, _), (count, _) in p.callers.get(fn, {}).items():
            by_caller[cfn] = by_caller.get(cfn, 0) + count
        ncalls = sum(by_caller.values())
        share = 100.0 * s / total
        href = entry_link(fn)
        by_caller_sorted = sorted(by_caller.items(), key=lambda kv: (-kv[1], kv[0]))
        who = ", ".join(f"{cfn} ({theme.num_pct(100.0 * n / ncalls)})" for cfn, n in by_caller_sorted)

        def caller_html(cfn: str, n: int) -> str:
            chref = entry_link(cfn)
            label = f"{html_esc(cfn)} ({theme.num_pct(100.0 * n / ncalls)})"
            return f'<a href="{chref}">{label}</a>' if chref else label

        who_html = ", ".join(caller_html(cfn, n) for cfn, n in by_caller_sorted)
        rows.append([str(rank),
                     Cell(theme.num_pct(share), style=theme.heat_style(theme.heat_t(share, max_pct))),
                     Cell(fn, title=fn, html=f'<a href="{href}">{html_esc(fn)}</a>' if href else None),
                     Cell(theme.num_human(ncalls), title=f"{ncalls:,} calls",
                          style=theme.heat_style(theme.heat_t(100.0 * ncalls / calls_total, calls_max_pct))) if ncalls else "",
                     Cell(who, title=who, html=who_html) if who else Cell("(no recorded caller)", cls="dim")])
    return theme.table_render("report.functions", cols, rows, fill=True, lines=True)


PID_PREFIX = re.compile(r"^==\d+==\s?")


def log_block(path: str) -> str:
    """The valgrind log without its LOG_SKIP-line banner or each line's
    "==PID==" prefix, in a single-cell box styled like the functions table."""
    lines = file_read_text(path).rstrip().split("\n")[LOG_SKIP:]
    text = "\n".join(PID_PREFIX.sub("", ln) for ln in lines)
    return f'<div class="tbl"><pre class="logbox">{html_esc(text)}</pre></div>'


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
    body = strip_render(args.test, links)
    out_dir = os.path.dirname(os.path.abspath(args.output))
    body += '<main id="home"><div class="page">'
    if args.log and not args.no_log:
        body += '<details class="sec"><summary><h2>valgrind log</h2></summary>'
        for log in args.log:
            if len(args.log) > 1:
                body += f"<p>{html_esc(os.path.basename(log))}</p>"
            body += log_block(log)
        body += "</details>"
    body += rawdata_list(args.raw_data, out_dir)
    body += f"<h2>top {args.top} functions by self</h2>" + functions_table(p, args.event, args.top, args.repo_root)
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
    t.add_argument("--no-log", action="store_true", help="omit the valgrind log section even if --log was given")
    t.add_argument("--event", default="Ir", help="event that ranks the functions (default: Ir)")
    t.add_argument("--top", type=int, default=50)
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
