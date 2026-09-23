#!/usr/bin/env python3
# dev/scripts/screenshots.py REPORT PREFIX [--out=DIR] -- shoot a report.
#
# One PNG per entry in _VIEWS, each a hash naming a view the report renders
# a different way. The list is of views, not of data: two hashes differing
# only in which test or counter they name are one view and one shot.
#
# Every anchor a hash names is from the timer framework rather than from
# what is timed -- tests/perf/first.c and lib/curlx/timeval.c are in every
# profile whatever TESTS_C holds, so no entry here names a test.
from __future__ import annotations

import argparse, os, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import settings

SCREENSHOT_BROWSER_CANDIDATES: tuple[str, ...] = ()
SCREENSHOT_DIR_NAME: str = ""
SCREENSHOT_RENDER_BUDGET_MS: int = 0
SCREENSHOT_VIEWPORT_HEIGHT_PX: int = 0
SCREENSHOT_VIEWPORT_WIDTH_PX: int = 0
settings.load_into(__name__)


# Screenshots - drives one headless browser over a report's views.
class Screenshots:
    def __init__(self, browser: str, report: str, out_dir: str) -> None:
        # the browser binary every shot is taken with
        self.browser = browser
        # the report directory being shot, absolute
        self.report = report
        # where the PNGs are written
        self.out_dir = out_dir
        # every view that failed to render, reported together at the end
        self.faults: list[str] = []

    # A path the browser will open, translating for a Windows browser that
    # cannot read a linux path. wslpath is the translator, never a guess.
    def browser_path_of(self, path: str) -> str:
        if not self.windows_browser_is():
            return path
        return subprocess.run(
            ["wslpath", "-w", path],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

    # The file:// URL of the entry page at one view's hash. A UNC path keeps
    # every slash wslpath gave it: two fewer names a disk Windows cannot read.
    def page_url_of(self, view_hash: str) -> str:
        page = self.browser_path_of(os.path.join(self.report, _ENTRY_PAGE))
        if self.windows_browser_is():
            return "file://" + page.replace("\\", "/") + view_hash
        return "file://" + page + view_hash

    # Shoot every view, returning the count written.
    def shoot_all(self, prefix: str) -> int:
        written = 0
        for name, view_hash in _VIEWS:
            if self.shoot_one(prefix + name, view_hash):
                written += 1
        return written

    # Shoot one view. A browser that writes no file is this view's fault,
    # collected rather than raised: the later views still get their shot.
    def shoot_one(self, name: str, view_hash: str) -> bool:
        out_path = os.path.join(self.out_dir, name + _IMAGE_SUFFIX)
        if os.path.exists(out_path):
            os.remove(out_path)
        window = (
            f"{SCREENSHOT_VIEWPORT_WIDTH_PX},{SCREENSHOT_VIEWPORT_HEIGHT_PX}"
        )
        result = subprocess.run(
            [
                self.browser,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--hide-scrollbars",
                f"--window-size={window}",
                f"--screenshot={self.browser_path_of(out_path)}",
                f"--virtual-time-budget={SCREENSHOT_RENDER_BUDGET_MS}",
                self.page_url_of(view_hash),
            ],
            capture_output=True,
            text=True,
        )
        if os.path.exists(out_path) and os.path.getsize(out_path):
            print(f"  {os.path.basename(out_path)}")
            return True
        self.faults.append(f"{name}: {view_hash or '(entry page)'}")
        print(result.stderr.strip()[-_FAULT_TAIL_CHARS:], file=sys.stderr)
        return False

    # Whether the chosen browser is a Windows one reached through /mnt.
    def windows_browser_is(self) -> bool:
        return self.browser.lower().endswith(_WINDOWS_BROWSER_SUFFIX)


# The first candidate present, or none when this box has no browser.
def browser_find() -> str | None:
    for candidate in SCREENSHOT_BROWSER_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
        found = shutil.which(candidate)
        if found:
            return found
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", help="a report directory to shoot")
    parser.add_argument("prefix", help="what every file name starts with")
    parser.add_argument(
        "--out",
        default="",
        help=f"where the PNGs go (default dev/{SCREENSHOT_DIR_NAME})",
    )
    namespace = parser.parse_args()

    report = os.path.abspath(namespace.report)
    if not os.path.isfile(os.path.join(report, _ENTRY_PAGE)):
        print(f"error: {report} holds no {_ENTRY_PAGE}", file=sys.stderr)
        return 1

    browser = browser_find()
    if browser is None:
        print(
            "error: no browser found. Tried: "
            + ", ".join(SCREENSHOT_BROWSER_CANDIDATES),
            file=sys.stderr,
        )
        print(
            "       sudo apt-get install -y chromium-browser",
            file=sys.stderr,
        )
        return 1

    out_dir = namespace.out or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", SCREENSHOT_DIR_NAME
    )
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    print(f"{os.path.basename(report)} -> {out_dir}")
    shooter = Screenshots(browser, report, out_dir)
    written = shooter.shoot_all(namespace.prefix)

    if shooter.faults:
        print(
            f"error: {len(shooter.faults)} view(s) wrote no image:",
            file=sys.stderr,
        )
        for fault in shooter.faults:
            print(f"  {fault}", file=sys.stderr)
        return 1
    print(f"{written} screenshot(s)")
    return 0


# The page every view's hash is appended to, the report's own entry point:
# shooting through it is what exercises the frame controller.
_ENTRY_PAGE = "index.html"

# trailing characters of a failed browser's stderr that get reprinted
_FAULT_TAIL_CHARS = 400

_IMAGE_SUFFIX = ".png"

# How a Windows browser binary is told apart from a linux one, so only it
# pays for a wslpath translation.
_WINDOWS_BROWSER_SUFFIX = ".exe"

# Anchors from the timer framework, in every profile whatever TESTS_C
# holds. A hash naming what is timed would rot the day a test is renamed.
_ANCHOR_FILE = "lib/curlx/timeval.c"
_ANCHOR_FUNCTION = "curlx_now"

# The synthetic test merging every real one. It is a view of the report
# rather than a test name, so it survives any change to TESTS_C.
_MERGED_TEST = "all"

# Every view worth a shot, as (file name, hash). Each renders through a
# code path no earlier entry reaches; a view showing other data does not.
_VIEWS: tuple[tuple[str, str], ...] = (
    ("overview", ""),
    ("summary", f"#{_MERGED_TEST}"),
    ("heat_map_home", f"#{_MERGED_TEST}/heat-map/"),
    ("heat_map_file", f"#{_MERGED_TEST}/heat-map/f={_ANCHOR_FILE}"),
    (
        "heat_map_line",
        f"#{_MERGED_TEST}/heat-map/f={_ANCHOR_FILE}&l=1",
    ),
    ("heat_map_function", f"#{_MERGED_TEST}/heat-map/fn={_ANCHOR_FUNCTION}"),
    ("error_bad_view", "#no-such-view"),
    (
        "error_bad_counter",
        f"#{_MERGED_TEST}/heat-map/e=NoSuchCounter",
    ),
    (
        "error_bad_function",
        f"#{_MERGED_TEST}/heat-map/fn=no_such_function",
    ),
    (
        "error_bad_file",
        f"#{_MERGED_TEST}/heat-map/f=no/such/file.c",
    ),
)

if __name__ == "__main__":
    sys.exit(main())
