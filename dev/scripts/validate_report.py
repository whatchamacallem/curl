#!/usr/bin/env python3
"""Smoke test over a dev/profile.sh report directory: cheap structural and
content checks, not a re-parse of the profile data. Catches the failure mode
of a page silently missing (a step failed but the script kept going),
existing but truncated/empty, or leaking an absolute host path -- not
whether the numbers in it are correct.

Usage:
  validate_report.py OUTDIR [--test NAME ...]

  OUTDIR    a report directory written by dev/profile.sh: either one test's
            report (OUTDIR/index.html is a test page) or an "all" run
            (OUTDIR/index.html is the overview, OUTDIR/<test>/ and
            OUTDIR/all/ each hold a test page).
  --test    check only these tests under an overview OUTDIR (default: every
            test the overview links to, plus "all").

Prints one line per check that failed; exits 0 if everything passed, 1
otherwise. Prints nothing on full success besides a final "ok" summary line.
"""
from __future__ import annotations

import argparse
import os
import re
import sys

MIN_PAGE_BYTES = 500          # a page this small is missing its body
MIN_INDEX_BYTES = 2000        # a test/overview index with a real summary
MIN_HEATMAP_BYTES = 5000      # the heat map embeds source; near-empty means no samples matched
MIN_FLAME_JSON_BYTES = 200    # profile.speedscope.json / profile.js payload
SUBPAGES = ["flame-graph/index.html", "heat-map/index.html", "perf-tool/index.html"]

errors: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def check_exists(path: str, label: str) -> bool:
    if not os.path.isfile(path):
        fail(f"missing {label}: {path}")
        return False
    return True


def check_min_size(path: str, min_bytes: int, label: str) -> str:
    """Returns the file's text (for further checks), or "" if it failed size/read."""
    try:
        size = os.path.getsize(path)
    except OSError as e:
        fail(f"{label}: {path}: {e}")
        return ""
    if size < min_bytes:
        fail(f"{label} suspiciously small ({size} bytes < {min_bytes}): {path}")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as e:
        fail(f"{label}: {path}: {e}")
        return ""


def check_html_page(path: str, label: str, min_bytes: int = MIN_PAGE_BYTES,
                     want_title: str | None = None) -> str:
    if not check_exists(path, label):
        return ""
    text = check_min_size(path, min_bytes, label)
    if not text:
        return text
    if "<title>" not in text:
        fail(f"{label} has no <title>: {path}")
    elif want_title is not None:
        m = re.search(r"<title>(.*?)</title>", text, re.S)
        got = m.group(1) if m else ""
        if got != want_title:
            fail(f"{label} title is {got!r}, expected {want_title!r}: {path}")
    if "</html>" not in text:
        fail(f"{label} is not a closed HTML document (no </html>): {path}")
    for marker in ("{name}", "{data}", "Traceback (most recent call last)", "NaN%"):
        if marker in text:
            fail(f"{label} contains a leftover template/error marker {marker!r}: {path}")
    return text


def check_no_leaked_paths(path: str, repo_root: str, label: str) -> None:
    """raw/ files and generated pages should have the repo root stripped --
    an absolute path here means OUTDIR was not copied out safely, or the
    sed/relpath step that is supposed to strip it silently didn't run."""
    text = check_min_size(path, 0, label)
    if repo_root and repo_root in text:
        fail(f"{label} still contains the absolute repo root {repo_root!r}: {path}")


def check_raw_dir(test_dir: str, test_name: str) -> None:
    raw_dir = os.path.join(test_dir, "raw")
    if not os.path.isdir(raw_dir):
        fail(f"missing raw/ dir for test {test_name!r}: {raw_dir}")
        return
    files = [f for f in os.listdir(raw_dir) if os.path.isfile(os.path.join(raw_dir, f))]
    if not files:
        fail(f"raw/ dir has no callgrind file(s) for test {test_name!r}: {raw_dir}")
        return
    for f in files:
        p = os.path.join(raw_dir, f)
        if os.path.getsize(p) < MIN_PAGE_BYTES:
            fail(f"raw data file suspiciously small: {p}")
        with open(p, "rb") as fh:
            head = fh.read(64)
        if b"events:" not in open(p, "rb").read(4096):
            fail(f"raw data file does not look like a callgrind trace (no 'events:' near the top): {p}")


def check_perf_tool(test_dir: str, test_name: str, *, is_all: bool) -> None:
    out_txt = os.path.join(test_dir, "perf-tool", "output.txt")
    text = check_min_size(out_txt, 20, "perf-tool/output.txt")
    if not text:
        return
    if is_all:
        if not re.search(r"^Time:\s+\d+\s+usecs\s*$", text, re.M):
            fail(f"perf-tool/output.txt for 'all' has no summed 'Time:' line: {out_txt}")
    else:
        if not re.search(r"^Time(/\w+)?:\s+\d", text, re.M):
            fail(f"perf-tool/output.txt has no recognizable timing line: {out_txt}")
        if test_name == "urlparser" and "Errors:" not in text:
            fail(f"perf-tool/output.txt has no 'Errors:' line (urlparser is expected to print one): {out_txt}")
    check_html_page(os.path.join(test_dir, "perf-tool", "index.html"), "perf-tool/index.html",
                     want_title=f"{test_name} / native timing")


def check_flame_graph(test_dir: str) -> None:
    fg = os.path.join(test_dir, "flame-graph")
    if not os.path.isdir(fg):
        fail(f"missing flame-graph/ dir: {fg}")
        return
    check_exists(os.path.join(fg, "index.html"), "flame-graph/index.html")
    check_min_size(os.path.join(fg, "index.html"), MIN_PAGE_BYTES, "flame-graph/index.html")
    check_min_size(os.path.join(fg, "profile.js"), MIN_FLAME_JSON_BYTES, "flame-graph/profile.js")
    js = check_min_size(os.path.join(fg, "profile.js"), 0, "flame-graph/profile.js")
    if js and "loadFileFromBase64" not in js:
        fail(f"flame-graph/profile.js does not call loadFileFromBase64: {fg}/profile.js")


def check_heat_map(test_dir: str, test_name: str) -> None:
    path = os.path.join(test_dir, "heat-map", "index.html")
    text = check_html_page(path, "heat-map/index.html", min_bytes=MIN_HEATMAP_BYTES,
                            want_title=f"{test_name} / heat map")
    if text and "heatStyle" not in text:
        fail(f"heat-map/index.html is missing its runtime script (no heatStyle): {path}")


def check_test_index(test_dir: str, test_name: str) -> None:
    path = os.path.join(test_dir, "index.html")
    text = check_html_page(path, "index.html", min_bytes=MIN_INDEX_BYTES, want_title=test_name)
    if not text:
        return
    if not re.search(r"<h2>top \d+ functions by self</h2>", text):
        fail(f"index.html has no 'top N functions by self' section: {path}")
    for key, _, href in [("flame-graph", "flame graph", "flame-graph/index.html"),
                          ("heat-map", "heat map", "heat-map/index.html"),
                          ("perf-tool", "native timing", "perf-tool/index.html")]:
        if f'href="{href}"' not in text:
            fail(f"index.html is missing its {key} strip link ({href}): {path}")
    if "raw data" not in text:
        fail(f"index.html has no 'raw data' section: {path}")


def check_test_report(test_dir: str, test_name: str, *, is_all: bool) -> None:
    if not os.path.isdir(test_dir):
        fail(f"missing report directory for test {test_name!r}: {test_dir}")
        return
    check_test_index(test_dir, test_name)
    check_flame_graph(test_dir)
    check_heat_map(test_dir, test_name)
    check_perf_tool(test_dir, test_name, is_all=is_all)
    check_raw_dir(test_dir, test_name)


def check_overview(out_dir: str, only_tests: list[str] | None) -> list[str]:
    """Returns the list of test names the overview links to (so the caller
    can also check each one), after validating the overview page itself."""
    path = os.path.join(out_dir, "index.html")
    text = check_html_page(path, "index.html (overview)", min_bytes=MIN_INDEX_BYTES, want_title="overview")
    if not text:
        return []
    names = sorted(set(re.findall(r'href="([a-z0-9_]+)/index\.html"', text)))
    if "all" not in names:
        fail(f"overview index.html has no link to 'all/': {path}")
    if not names:
        fail(f"overview index.html links to no test reports at all: {path}")
    if "<h2>test suites</h2>" not in text:
        fail(f"overview index.html has no 'test suites' table: {path}")
    return [n for n in names if only_tests is None or n in only_tests or n == "all"]


def repo_root_guess(out_dir: str) -> str:
    d = os.path.abspath(out_dir)
    for _ in range(6):
        if os.path.isdir(os.path.join(d, ".git")):
            return d
        d = os.path.dirname(d)
    return ""


def validate_main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir", help="report directory (dev/profile.sh's OUTDIR)")
    ap.add_argument("--test", action="append", default=None, metavar="NAME",
                     help="check only this test under an overview OUTDIR (repeatable; default: every linked test)")
    args = ap.parse_args()

    out_dir = os.path.abspath(args.out_dir)
    if not os.path.isdir(out_dir):
        print(f"error: no such directory: {out_dir}", file=sys.stderr)
        return 1
    repo_root = repo_root_guess(out_dir)

    index_path = os.path.join(out_dir, "index.html")
    if not os.path.isfile(index_path):
        print(f"error: no index.html in {out_dir} -- not a report directory?", file=sys.stderr)
        return 1
    with open(index_path, encoding="utf-8", errors="replace") as f:
        head = f.read()
    is_overview = "test suites" in head or bool(re.search(r'href="[a-z0-9_]+/index\.html"', head))

    checked = 0
    if is_overview:
        names = check_overview(out_dir, args.test)
        for name in names:
            check_test_report(os.path.join(out_dir, name), name, is_all=(name == "all"))
            checked += 1
    else:
        # single-test report: OUTDIR itself is the test page.
        m = re.search(r"<title>(.*?)</title>", head)
        name = m.group(1) if m else os.path.basename(out_dir)
        check_test_report(out_dir, name, is_all=(name == "all"))
        checked = 1

    if repo_root:
        for dirpath, _, filenames in os.walk(out_dir):
            if os.path.basename(dirpath) != "raw":
                continue
            for fn in filenames:
                check_no_leaked_paths(os.path.join(dirpath, fn), repo_root, f"raw/{fn}")

    if errors:
        print(f"validate_report: {len(errors)} problem(s) in {out_dir}:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print(f"validate_report: ok ({checked} test report(s) checked in {out_dir})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(validate_main())
