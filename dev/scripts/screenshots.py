#!/usr/bin/env python3
# dev/scripts/screenshots.py REPORT PREFIX [--out=DIR] -- shoot a report.
#
# One PNG per entry in _VIEWS per viewport in _SCREENSHOT_VIEWPORTS, each
# hash naming a view the report renders a different way. The list is of
# views, not of data: two hashes differing only in which test or counter
# they name are one view and one shot. The viewports are there to be
# compared: a page is designed once and fitted to the window, so one view's
# three shots differ in size and in nothing else.
#
# Every anchor a hash names is from the timer framework rather than from
# what is timed -- tests/perf/first.c and lib/curlx/timeval.c are in every
# profile whatever TESTS_C holds, so no entry here names a test.
#
# Nothing here is a setting: enforcer.sh is the only caller, no report
# carries a shot, and a browser a page never sees is not the pages' to read.
from __future__ import annotations

import argparse, os, shutil, subprocess, sys

import PIL.Image


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

    # Shoot every view at every viewport, returning the count written.
    def shoot_all(self, prefix: str) -> int:
        written = 0
        for size_name, width_px, height_px in _SCREENSHOT_VIEWPORTS:
            for name, view_hash in _VIEWS:
                shot = f"{size_name}_{prefix}{name}"
                if self.shoot_one(shot, view_hash, width_px, height_px):
                    written += 1
        return written

    # Shoot one view at one viewport. A browser that writes no file is this
    # view's fault, collected rather than raised: the rest still get shot.
    def shoot_one(
        self, name: str, view_hash: str, width_px: int, height_px: int
    ) -> bool:
        out_path = os.path.join(self.out_dir, name + _IMAGE_SUFFIX)
        if os.path.exists(out_path):
            os.remove(out_path)
        window = f"{width_px},{height_px}"
        result = subprocess.run(
            [
                self.browser,
                "--headless=new",
                "--disable-gpu",
                "--no-sandbox",
                "--hide-scrollbars",
                # a shot is of the page as shipped: nothing a browser stored
                # (a moved slider, a dragged pane) may reach it
                "--incognito",
                f"--window-size={window}",
                f"--screenshot={self.browser_path_of(out_path)}",
                f"--virtual-time-budget={_SCREENSHOT_RENDER_BUDGET_MS}",
                self.page_url_of(view_hash),
            ],
            capture_output=True,
            text=True,
        )
        if os.path.exists(out_path) and os.path.getsize(out_path):
            return True
        self.faults.append(f"{name}: {view_hash or '(entry page)'}")
        print(result.stderr.strip()[-_FAULT_TAIL_CHARS:], file=sys.stderr)
        return False

    # One contact sheet per viewport, the shots in _VIEWS order laid left to
    # right. A sheet is temporary output for a person, covered by no checksum.
    def sheets_write(self, prefix: str) -> int:
        written = 0
        for size_name, _width_px, _height_px in _SCREENSHOT_VIEWPORTS:
            shots = [
                os.path.join(
                    self.out_dir,
                    f"{size_name}_{prefix}{name}{_IMAGE_SUFFIX}",
                )
                for name, _hash in _VIEWS[:_THUMBNAIL_SHEET_CELLS]
            ]
            shots = [path for path in shots if os.path.isfile(path)]
            if not shots:
                continue
            name = f"thumbnail_{size_name}_{prefix.rstrip('_')}"
            self.sheet_one(name + _IMAGE_SUFFIX, shots)
            written += 1
        return written

    # Draw one sheet: every cell the same box, each shot fitted inside it
    # whole, so a 720p and a 4k shot of one view sit at the same size.
    def sheet_one(self, name: str, shots: list[str]) -> None:
        cell_width = _THUMBNAIL_SHEET_WIDTH_PX // _THUMBNAIL_SHEET_COLUMNS
        cell_height = _THUMBNAIL_SHEET_HEIGHT_PX // _THUMBNAIL_SHEET_ROWS
        sheet = PIL.Image.new(
            "RGB",
            (_THUMBNAIL_SHEET_WIDTH_PX, _THUMBNAIL_SHEET_HEIGHT_PX),
            _THUMBNAIL_SHEET_BACKGROUND,
        )
        for index, path in enumerate(shots):
            shot = PIL.Image.open(path)
            shot.thumbnail(
                (cell_width, cell_height), PIL.Image.Resampling.LANCZOS
            )
            column = index % _THUMBNAIL_SHEET_COLUMNS
            row = index // _THUMBNAIL_SHEET_COLUMNS
            sheet.paste(
                shot,
                (
                    column * cell_width + (cell_width - shot.width) // 2,
                    row * cell_height + (cell_height - shot.height) // 2,
                ),
            )
        sheet.save(os.path.join(self.out_dir, name))

    # Whether the chosen browser is a Windows one reached through /mnt.
    def windows_browser_is(self) -> bool:
        return self.browser.lower().endswith(_WINDOWS_BROWSER_SUFFIX)


# The first candidate present, or none when this box has no browser.
def browser_find() -> str | None:
    for candidate in _SCREENSHOT_BROWSER_CANDIDATES:
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
        help=f"where the PNGs go (default dev/{_SCREENSHOT_DIR_NAME})",
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
            + ", ".join(_SCREENSHOT_BROWSER_CANDIDATES),
            file=sys.stderr,
        )
        print(
            "       sudo apt-get install -y chromium-browser",
            file=sys.stderr,
        )
        return 1

    out_dir = namespace.out or os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        _SCREENSHOT_DIR_NAME,
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

    shooter.sheets_write(namespace.prefix)
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

# Every browser this will drive, in the order it tries them. A WSL box has
# no linux browser of its own, so the Windows ones close the list.
_SCREENSHOT_BROWSER_CANDIDATES: tuple[str, ...] = (
    "chromium",
    "chromium-browser",
    "google-chrome",
    "google-chrome-stable",
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
    "/mnt/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
)

# Where the PNGs land, beside the scripts rather than in a report: a shot
# is of a report, not part of one, and no checksum covers it.
_SCREENSHOT_DIR_NAME = "screenshots"

# How long a page gets to render before the shot is taken. Virtual time,
# so it costs nothing when the page settles sooner.
_SCREENSHOT_RENDER_BUDGET_MS = 8000

# Every viewport each view is shot at, as (name, width, height). The name
# leads the file name, so one view's three shots sort together for comparing.
_SCREENSHOT_VIEWPORTS: tuple[tuple[str, int, int], ...] = (
    ("720p", 1280, 720),
    ("1080p", 1920, 1080),
    ("4k", 3840, 2160),
)

# What a sheet's empty cells are left as, the pages' own near-black so a
# part-filled sheet does not glare.
_THUMBNAIL_SHEET_BACKGROUND = (18, 20, 24)

# The grid one sheet lays its shots out in, and how many that holds. Nine
# cells is every view one viewport has, so a sheet is the whole set at once.
_THUMBNAIL_SHEET_COLUMNS = 3
_THUMBNAIL_SHEET_ROWS = 3
_THUMBNAIL_SHEET_CELLS = _THUMBNAIL_SHEET_COLUMNS * _THUMBNAIL_SHEET_ROWS

# A sheet is 4k whatever the shots on it are: it is read by a person on a
# screen, not compared against a report, and is temporary either way.
_THUMBNAIL_SHEET_HEIGHT_PX = 2160
_THUMBNAIL_SHEET_WIDTH_PX = 3840

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
    (
        "bad_function",
        f"#{_MERGED_TEST}/heat-map/fn=no_such_function",
    ),
)

if __name__ == "__main__":
    sys.exit(main())
