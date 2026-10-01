#!/usr/bin/env python3
# dev/scripts/test_screenshot.py REPORT PREFIX [--out=DIR] -- shoot a report.
#
# One PNG per entry in _VIEWS per viewport in _SCREENSHOT_VIEWPORTS, each
# hash naming a view the report renders a different way. The list is of
# views, not of data: two hashes differing only in which test they name
# are one view and one shot. The viewports are there to be
# compared: a page is designed once and fitted to the window, so one view's
# three shots differ in size and in nothing else.
#
# Each hash is a golden bookmark, a string literal written out whole and
# formulated from nothing: changing the url format must require changing
# those string literals. A diff report has no flame graph, so that view is
# shot for a full report only, the kind of report read from its MANIFEST.txt
# line 1.
#
# A view lacking files (a report whose run stopped short) is shot from a
# copy of the report under dev/build/, removed once shot: verification
# never changes the report it checks.
#
# Nothing here is a setting: test_expected_behavior.sh is the only caller,
# no report carries a shot, and a browser a page never sees is not the
# pages' to read.
from __future__ import annotations

import argparse, os, shutil, subprocess, sys, urllib.parse

import PIL.Image

# The page every view's hash is appended to, the report's own entry point:
# shooting through that exercises the model frame.js and controller menu.js.
_ENTRY_PAGE = "index.html"

# trailing characters of a failed browser's stderr that get reprinted
_FAULT_TAIL_CHARS = 400

_IMAGE_SUFFIX = ".png"

# What a run writes last, so what a run that stopped short lacks.
_REPORT_COMPLETE_ASSET: tuple[str, ...] = ("assets/report_complete.js",)

# A report's manifest and the line 1 each kind of report writes there, then
# the kinds of report a view is shot for: only a full one has a flame graph.
_REPORT_MANIFEST_NAME = "MANIFEST.txt"
_REPORT_MANIFEST_VERSION_DIFF = "curl/perf2html_diff.sh v1"
_REPORT_MANIFEST_VERSION_FULL = "curl/perf2html.sh v1"

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

# Where a copy of a report lacking files is shot from, relative to dev/:
# gitignored and on disk rather than tmpfs, like test_error_handling.sh's.
_SCREENSHOT_SCRATCH_DIR_PATH = "build/screenshots_scratch"

# The query param report_complete.js reads to show the bottom-left label
# identifying, in a shot, the URL/state a headless browser was sent to.
_SCREENSHOT_URL_PARAM = "screenshot"

# Every viewport each view is shot at, as (name, width, height). The name
# leads the file name, so one view's three shots sort together for comparing.
_SCREENSHOT_VIEWPORTS: tuple[tuple[str, int, int], ...] = (
    ("720p", 1280, 720),
    ("4k", 3840, 2160),
)

_SHOOT_BOTH_REPORTS: tuple[str, ...] = (
    _REPORT_MANIFEST_VERSION_DIFF,
    _REPORT_MANIFEST_VERSION_FULL,
)
_SHOOT_REGULAR_REPORT_ONLY: tuple[str, ...] = (_REPORT_MANIFEST_VERSION_FULL,)

# What a sheet's empty cells are left as, the pages' own near-black so a
# part-filled sheet does not glare.
_THUMBNAIL_SHEET_BACKGROUND = (18, 20, 24)

# The grid one sheet lays its shots out in, and how many that holds. Nine
# cells is every view a full report has, so a sheet is the whole set at once.
_THUMBNAIL_SHEET_COLUMNS = 3
_THUMBNAIL_SHEET_ROWS = 3
_THUMBNAIL_SHEET_CELLS = _THUMBNAIL_SHEET_COLUMNS * _THUMBNAIL_SHEET_ROWS

# A sheet is 4k whatever the shots on it are: it is read by a person on a
# screen, not compared against a report, and is temporary either way.
_THUMBNAIL_SHEET_HEIGHT_PX = 2160
_THUMBNAIL_SHEET_WIDTH_PX = 3840

# Every view worth a shot, as (file name, bookmark, files its report lacks,
# report kinds it is shot for). Each takes a code path no earlier one takes.
_VIEWS: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("overview", "", (), _SHOOT_BOTH_REPORTS),
    ("callers", "#test=all&view=callers", (), _SHOOT_BOTH_REPORTS),
    (
        "heat_map_home",
        "#test=urlparser&view=heat-map",
        (),
        _SHOOT_BOTH_REPORTS,
    ),
    (
        "heat_map_file",
        "#test=urlparser&view=heat-map"
        "&file=sysdeps/x86_64/multiarch/memchr-avx2.S",
        (),
        _SHOOT_BOTH_REPORTS,
    ),
    (
        "heat_map_line",
        "#test=urlparser&view=heat-map"
        "&file=sysdeps/x86_64/multiarch/memchr-avx2.S&line=82",
        (),
        _SHOOT_BOTH_REPORTS,
    ),
    (
        "heat_map_function",
        "#test=urlparser&view=heat-map&function=parseurl_and_replace",
        (),
        _SHOOT_BOTH_REPORTS,
    ),
    (
        "flame_graph",
        "#test=urlparser&view=flame-graph&localProfilePath=profile",
        (),
        _SHOOT_REGULAR_REPORT_ONLY,
    ),
    (
        "bad_function",
        "#test=urlparser&view=heat-map&function=no_such_function",
        (),
        _SHOOT_BOTH_REPORTS,
    ),
    (
        "report_incomplete",
        "",
        _REPORT_COMPLETE_ASSET,
        _SHOOT_BOTH_REPORTS,
    ),
)

# How a Windows browser binary is told apart from a linux one, so only it
# pays for a wslpath translation.
_WINDOWS_BROWSER_SUFFIX = ".exe"


# Screenshots - drives one headless browser over a report's views.
class Screenshots:
    def __init__(
        self, browser: str, report: str, out_dir: str, scratch_dir: str
    ) -> None:
        # the browser binary every shot is taken with
        self.browser = browser
        # the report directory being shot, absolute
        self.report = report
        # where the PNGs are written
        self.out_dir = out_dir
        # where a copy of the report lacking files is shot from, absolute
        self.scratch_dir = scratch_dir
        # the _VIEWS entries this kind of report is shot for
        self.report_views = self.report_views_select()

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

    # Shoot one view of a copy of the report lacking absent_files, the copy
    # replaced by each run and gone once shot. Returns the count written.
    def copy_shoot(
        self,
        prefix: str,
        name: str,
        view_hash: str,
        absent_files: tuple[str, ...],
    ) -> int:
        if os.path.exists(self.scratch_dir):
            shutil.rmtree(self.scratch_dir)
        shutil.copytree(self.report, self.scratch_dir)
        try:
            for relative_path in absent_files:
                os.remove(os.path.join(self.scratch_dir, relative_path))
            return self.view_shoot(self.scratch_dir, prefix, name, view_hash)
        finally:
            shutil.rmtree(self.scratch_dir)

    # The file:// URL of an entry page at one view's hash, carrying the
    # screenshot param a shot's own bottom-left label reads.
    def page_url_of(self, name: str, page_dir: str, view_hash: str) -> str:
        page = self.browser_path_of(os.path.join(page_dir, _ENTRY_PAGE))
        query = "?" + urllib.parse.urlencode(
            {_SCREENSHOT_URL_PARAM: name + view_hash}
        )
        if self.windows_browser_is():
            return "file://" + page.replace("\\", "/") + query + view_hash
        return "file://" + page + query + view_hash

    # The _VIEWS entries shot for the report's kind, its MANIFEST.txt line 1.
    # A line naming neither kind of report is a hard error.
    def report_views_select(
        self,
    ) -> list[tuple[str, str, tuple[str, ...], tuple[str, ...]]]:
        manifest_path = os.path.join(self.report, _REPORT_MANIFEST_NAME)
        with open(manifest_path, encoding="utf-8") as manifest_file:
            manifest_version = manifest_file.readline().rstrip("\n")
        if manifest_version not in _SHOOT_BOTH_REPORTS:
            raise RuntimeError(
                f"{manifest_path}: line 1 found {manifest_version!r},"
                f" expected one of {_SHOOT_BOTH_REPORTS!r}"
            )
        return [view for view in _VIEWS if manifest_version in view[3]]

    # Shoot every view at every viewport, returning the count written.
    def shoot_all(self, prefix: str) -> int:
        written = 0
        for name, view_hash, absent_files, _versions in self.report_views:
            if absent_files:
                written += self.copy_shoot(
                    prefix, name, view_hash, absent_files
                )
            else:
                written += self.view_shoot(
                    self.report, prefix, name, view_hash
                )
        return written

    # Shoot one view at one viewport. A browser that writes no file is a
    # hard error, raised immediately rather than tallied for later.
    def shoot_one(
        self,
        name: str,
        page_dir: str,
        view_hash: str,
        width_px: int,
        height_px: int,
    ) -> None:
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
                self.page_url_of(name, page_dir, view_hash),
            ],
            capture_output=True,
            text=True,
        )
        if os.path.exists(out_path) and os.path.getsize(out_path):
            return
        raise RuntimeError(
            f"{name}: {view_hash or '(entry page)'} wrote no image:"
            f" {result.stderr.strip()[-_FAULT_TAIL_CHARS:]}"
        )

    # One contact sheet per viewport, the shots in _VIEWS order laid left to
    # right. A sheet is temporary output for a person, covered by no checksum.
    def sheets_write(self, prefix: str) -> int:
        written = 0
        sheet_views = self.report_views[:_THUMBNAIL_SHEET_CELLS]
        for size_name, _width_px, _height_px in _SCREENSHOT_VIEWPORTS:
            shots = [
                os.path.join(
                    self.out_dir,
                    f"{size_name}_{prefix}{name}{_IMAGE_SUFFIX}",
                )
                for name, _hash, _absent, _versions in sheet_views
            ]
            for path in shots:
                assert os.path.isfile(path), f"missing shot: {path}"
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

    # Shoot one view of the report in page_dir at every viewport, returning
    # the count written.
    def view_shoot(
        self, page_dir: str, prefix: str, name: str, view_hash: str
    ) -> int:
        written = 0
        for size_name, width_px, height_px in _SCREENSHOT_VIEWPORTS:
            shot = f"{size_name}_{prefix}{name}"
            self.shoot_one(shot, page_dir, view_hash, width_px, height_px)
            written += 1
        return written

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
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print where the shots go and how many; a quiet run prints"
        " nothing on success",
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

    dev_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    out_dir = namespace.out or os.path.join(dev_dir, _SCREENSHOT_DIR_NAME)
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    scratch_dir = os.path.abspath(
        os.path.join(dev_dir, _SCREENSHOT_SCRATCH_DIR_PATH)
    )

    if namespace.verbose:
        print(f"{os.path.basename(report)} -> {out_dir}")
    shooter = Screenshots(browser, report, out_dir, scratch_dir)
    written = shooter.shoot_all(namespace.prefix)

    shooter.sheets_write(namespace.prefix)
    if namespace.verbose:
        print(f"{written} screenshot(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
