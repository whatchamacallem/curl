#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from typing import NamedTuple

MIN_FLAME_JSON_BYTES = 200
MIN_HEATMAP_BYTES = 5000
MIN_INDEX_BYTES = 2000
MIN_PAGE_BYTES = 500


class SubPage(NamedTuple):
    key: str
    href: str


class ValidateArgs(NamedTuple):
    out_dir: str
    test: list[str] | None


SUBPAGES: tuple[SubPage, ...] = (SubPage("flame-graph", "flame-graph/index.html"),
                                 SubPage("heat-map", "heat-map/index.html"),
                                 SubPage("perf-tool", "perf-tool/index.html"))

errors: list[str] = []


def check_exists(path: str, label: str) -> bool:
    if not os.path.isfile(path):
        fail(f"missing {label}: {path}")
        return False
    return True


def check_flame_graph(test_dir: str) -> None:
    flame_dir = os.path.join(test_dir, "flame-graph")
    if not os.path.isdir(flame_dir):
        fail(f"missing flame-graph/ dir: {flame_dir}")
        return
    index = os.path.join(flame_dir, "index.html")
    if check_exists(index, "flame-graph/index.html"):
        check_min_size(index, MIN_PAGE_BYTES, "flame-graph/index.html")
    script = check_min_size(os.path.join(flame_dir, "profile.js"), MIN_FLAME_JSON_BYTES, "flame-graph/profile.js")
    if script and "loadFileFromBase64" not in script:
        fail(f"flame-graph/profile.js does not call loadFileFromBase64: {flame_dir}/profile.js")


def check_heat_map(test_dir: str, test_name: str) -> None:
    path = os.path.join(test_dir, "heat-map", "index.html")
    text = check_html_page(path, "heat-map/index.html", min_bytes=MIN_HEATMAP_BYTES,
                           want_title=f"{test_name} / heat map")
    if text and "heatStyle" not in text:
        fail(f"heat-map/index.html is missing its runtime script (no heatStyle): {path}")


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
        match = re.search(r"<title>(.*?)</title>", text, re.S)
        got = match.group(1) if match else ""
        if got != want_title:
            fail(f"{label} title is {got!r}, expected {want_title!r}: {path}")
    if "</html>" not in text:
        fail(f"{label} is not a closed HTML document (no </html>): {path}")
    for marker in ("{name}", "{data}", "Traceback (most recent call last)", "NaN%"):
        if marker in text:
            fail(f"{label} contains a leftover template/error marker {marker!r}: {path}")
    return text


def check_min_size(path: str, min_bytes: int, label: str) -> str:
    try:
        size = os.path.getsize(path)
    except OSError as error:
        fail(f"{label}: {path}: {error}")
        return ""
    if size < min_bytes:
        fail(f"{label} suspiciously small ({size} bytes < {min_bytes}): {path}")
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    except OSError as error:
        fail(f"{label}: {path}: {error}")
        return ""


def check_no_leaked_paths(path: str, repo_root: str, label: str) -> None:
    text = check_min_size(path, 0, label)
    if repo_root and repo_root in text:
        fail(f"{label} still contains the absolute repo root {repo_root!r}: {path}")


def check_overview(out_dir: str, only_tests: list[str] | None) -> list[str]:
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
    return [name for name in names if only_tests is None or name in only_tests or name == "all"]


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


def check_raw_dir(test_dir: str, test_name: str) -> None:
    raw_dir = os.path.join(test_dir, "raw")
    if not os.path.isdir(raw_dir):
        fail(f"missing raw/ dir for test {test_name!r}: {raw_dir}")
        return
    files = [name for name in os.listdir(raw_dir) if os.path.isfile(os.path.join(raw_dir, name))]
    if not files:
        fail(f"raw/ dir has no callgrind file(s) for test {test_name!r}: {raw_dir}")
        return
    for name in files:
        path = os.path.join(raw_dir, name)
        if os.path.getsize(path) < MIN_PAGE_BYTES:
            fail(f"raw data file suspiciously small: {path}")
        with open(path, "rb") as handle:
            head = handle.read(4096)
        if b"events:" not in head:
            fail(f"raw data file does not look like a callgrind trace (no 'events:' near the top): {path}")


def check_test_index(test_dir: str, test_name: str) -> None:
    path = os.path.join(test_dir, "index.html")
    text = check_html_page(path, "index.html", min_bytes=MIN_INDEX_BYTES, want_title=test_name)
    if not text:
        return
    if not re.search(r"<h2>top \d+ functions by self</h2>", text):
        fail(f"index.html has no 'top N functions by self' section: {path}")
    for sub in SUBPAGES:
        if f'href="{sub.href}"' not in text:
            fail(f"index.html is missing its {sub.key} strip link ({sub.href}): {path}")
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


def fail(msg: str) -> None:
    errors.append(msg)


def repo_root_guess(out_dir: str) -> str:
    directory = os.path.abspath(out_dir)
    for _ in range(6):
        if os.path.isdir(os.path.join(directory, ".git")):
            return directory
        directory = os.path.dirname(directory)
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out_dir", help="report directory (dev/perf2html.sh's OUTDIR)")
    parser.add_argument("--test", action="append", default=None, metavar="NAME",
                        help="check only this test under an overview OUTDIR (repeatable; default: every linked test)")
    namespace = parser.parse_args()
    args = ValidateArgs(out_dir=namespace.out_dir, test=namespace.test)

    out_dir = os.path.abspath(args.out_dir)
    if not os.path.isdir(out_dir):
        print(f"error: no such directory: {out_dir}", file=sys.stderr)
        return 1
    repo_root = repo_root_guess(out_dir)

    index_path = os.path.join(out_dir, "index.html")
    if not os.path.isfile(index_path):
        print(f"error: no index.html in {out_dir} -- not a report directory?", file=sys.stderr)
        return 1
    with open(index_path, encoding="utf-8", errors="replace") as handle:
        head = handle.read()
    is_overview = "test suites" in head or bool(re.search(r'href="[a-z0-9_]+/index\.html"', head))

    checked = 0
    if is_overview:
        names = check_overview(out_dir, args.test)
        for name in names:
            check_test_report(os.path.join(out_dir, name), name, is_all=(name == "all"))
            checked += 1
    else:
        match = re.search(r"<title>(.*?)</title>", head)
        name = match.group(1) if match else os.path.basename(out_dir)
        check_test_report(out_dir, name, is_all=(name == "all"))
        checked = 1

    if repo_root:
        for dirpath, _, filenames in os.walk(out_dir):
            if os.path.basename(dirpath) != "raw":
                continue
            for filename in filenames:
                check_no_leaked_paths(os.path.join(dirpath, filename), repo_root, f"raw/{filename}")

    if errors:
        print(f"validate_report: {len(errors)} problem(s) in {out_dir}:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(f"validate_report: ok ({checked} test report(s) checked in {out_dir})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
