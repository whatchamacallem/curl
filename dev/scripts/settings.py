from __future__ import annotations

import json
import sys
import typing

# What the report's one shared copy of the theme is written as. Every page
# in a report renders the same stylesheet and the same script, so they are
# written once at the report root and linked, not inlined 19 times. The heat
# map's own stylesheet and runtime, and the frame script every summary and
# overview page runs, are the same on all of them too, so they are shared
# the same way; each page links only the ones it uses. theme.css and the
# settings file are generated rather than copied.
ASSET_FRAME_SCRIPT_NAME = "frame.js"
ASSET_HEAT_MAP_SCRIPT_NAME = "heatmap.js"
ASSET_HEAT_MAP_STYLESHEET_NAME = "heatmap.css"
ASSET_SETTINGS_SCRIPT_NAME = "settings.js"
ASSET_THEME_SCRIPT_NAME = "theme.js"
ASSET_THEME_STYLESHEET_NAME = "theme.css"
ASSET_UI_STRINGS_SCRIPT_NAME = "ui_strings.js"

# The immediately-invoked expression settings_script_write() wraps the
# settings object in, so the page's one control surface cannot be written to.
# It freezes to the leaves rather than calling Object.freeze on the top level
# alone: a shallow freeze leaves every nested object writable, and nesting
# is how a group would be spelled if the ids ever became one.
_DEEP_FREEZE = """(function deep_freeze(value) {
  if (value === null || typeof value !== "object") {
    return value;
  }
  Object.values(value).forEach(deep_freeze);
  return Object.freeze(value);
})"""

# What callgrind_diff.py's synthesized callers diff is named, next to the
# delta it describes. Written by perf2html_diff.sh, read back by
# build_report.py and skipped by validate_report.py.
DIFF_CALLER_COUNTS_FILE_SUFFIX = ".callers.json"

# The report-root directory holding the shared copy of speedscope, and the
# globs naming what it must hold: the engine, its stylesheet and the font
# the stylesheet names.
FLAME_GRAPH_APP_DIR_NAME = "flame-graph-app"
FLAME_GRAPH_APP_FILE_GLOBS = (
    "speedscope-*.js",
    "speedscope-*.css",
    "*.woff2",
)

# Only a flame graph our own tool exported counts -- a stale or hand-made
# one must fail.
FLAME_GRAPH_EXPORTER_NAME = "dev/scripts/trace_to_speedscope.py"

# The format a written speedscope document declares itself to be.
FLAME_GRAPH_FILE_FORMAT_SCHEMA_URL = (
    "https://www.speedscope.app/file-format-schema.json"
)

# The most complete calls one trace keeps. Measured against the current
# TESTS_C, whose recorded call counts run 79-202 for seven of the eight, so
# the cut lands on the top of that range; the eighth records 3,180 cheap
# calls. Retune if a test's shape changes.
FLAME_GRAPH_MAX_RECORDED_CALLS = 200

# All a per-test flame graph directory may hold: its own page, its own
# recorded profile, and the trace log. Everything else lives in the one
# shared bundle at the report root.
FLAME_GRAPH_PAGE_FILE_NAMES = ("index.html", "output.txt", "profile.js")

# What the bootstrap plus its embedded profile gets written as.
FLAME_GRAPH_PROFILE_SCRIPT_NAME = "profile.js"

# Blend alpha of the hottest cell, and of the coldest one that still carries
# colour.
HEAT_COLOR_ALPHA_HIGHEST = 0.92
HEAT_COLOR_ALPHA_LOWEST = 0.18

# A share at or past this is already fully lit, so the handful of diff lines
# reading millions of percent cannot flatten the scale.
HEAT_COLOR_FULL_SCALE_PERCENT = 100

# Heat above which a cell's text switches to the light-on-dark class, so the
# text stays readable once the cell behind it is bright.
HEAT_COLOR_LIGHT_TEXT_ABOVE_SHARE = 0.45

# The 12-stop heat ramp, cold to hot. Exempt from the light/dark pair rule.
HEAT_COLOR_RAMP_STOPS: list[str] = [
    "#3E4A89",
    "#31688E",
    "#26828E",
    "#1F9E89",
    "#35B779",
    "#6DCD59",
    "#B4DE2C",
    "#FDE725",
    "#FFC83B",
    "#FFA22C",
    "#FF7F21",
    "#F06142",
]

# The lowest a measured colour ceiling is allowed to fall to, so an event
# nothing recorded divides by a positive number rather than by 0.
HEAT_COLOR_SMALLEST_SCALE_TOP_SHARE = 0.0001

# The smallest share the log curve resolves; below it a cell is left cold.
HEAT_COLOR_SMALLEST_VISIBLE_SHARE = 0.001

# The ceiling a whole-profile percentage is coloured against: a line holding
# this much of the profile gets the full palette, so a whole-profile view is
# not dim just because no single line is a large share of a whole program.
HEAT_COLOR_WHOLE_PROFILE_SCALE_PERCENT = 10

# Width a <select> adds beyond its longest option text, so the chosen option
# is not clipped by the dropdown arrow.
HEAT_MAP_CONTROL_DROPDOWN_EXTRA_WIDTH_CHARS = 4

# In the home page's hot-lines table: how much of the "defined at" path a
# row keeps, how much of the source line itself it keeps, and how wide the
# column that source text is rendered in.
HEAT_MAP_HOME_LINES_LOCATION_MAX_CHARS = 28
HEAT_MAP_HOME_LINES_SOURCE_COLUMN_WIDTH_CHARS = 110
HEAT_MAP_HOME_LINES_SOURCE_TEXT_MAX_CHARS = 36

# Rows in each of the two home tables.
HEAT_MAP_HOME_TABLE_MAX_ROWS = 60

# The shortest file that gets a minimap at all. A file under this many lines
# fits on screen, so a scaled-down copy of it beside the source adds nothing.
HEAT_MAP_MINIMAP_SHOWN_ABOVE_FILE_LINES = 40

# The minimap's fixed column scale, the same 80 the source view uses. It is
# never widened to the file's longest line.
HEAT_MAP_MINIMAP_SOURCE_WIDTH_CHARS = 80

# Smallest the minimap's viewport box may be drawn, in pixels, so the box
# marking what is on screen stays visible in a very long file.
HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX = 8

# The share of the file a line must carry to earn a jump button above the
# source, and how many of those buttons a file view shows at most.
HEAT_MAP_SOURCE_HOT_LINE_BUTTON_LEAST_SHARE = 0.01
HEAT_MAP_SOURCE_HOT_LINE_BUTTON_MAX_COUNT = 10

# The standard width C source is rendered at. Not dev/'s own 79-column
# source limit -- this is the width of the profiled file's view.
HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS = 80

# Directories whose tracked .c/.h are listed even when nothing sampled them,
# so a file with no cost is visibly cold rather than simply missing.
HEAT_MAP_TREE_ALWAYS_LISTED_DIRS = ("lib", "include", "src", "tests/perf")

# The share of the profile a directory must hold to be expanded on first
# render, so a reader opens on the code that matters.
HEAT_MAP_TREE_AUTO_EXPAND_ABOVE_SHARE = 0.05

# The softer blend alphas the tree's file and directory rows carry, so a
# column of coloured rows does not overpower the source beside it.
HEAT_MAP_TREE_COLOR_ALPHA_HIGHEST = 0.55
HEAT_MAP_TREE_COLOR_ALPHA_LOWEST = 0.12

# How far the tree's first level is indented, and how much each level below
# it adds, in pixels.
HEAT_MAP_TREE_INDENT_FIRST_LEVEL_PX = 6
HEAT_MAP_TREE_INDENT_PER_LEVEL_PX = 14

# Narrowest the tree pane may be dragged, in pixels.
HEAT_MAP_TREE_PANE_NARROWEST_PX = 120

# Milliseconds a window resize settles for before the page re-measures. A
# drag fires resize continuously, and re-measuring every frame is what this
# delay exists to avoid.
LAYOUT_RESIZE_SETTLE_DELAY_MS = 120

# The page font: Monaco first, then whatever else the box has.
PAGE_FONT_FAMILY = (
    'Monaco, Menlo, "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace'
)

# The global the generated settings file assigns its one statement to. A page
# links that file before every script that reads it, the way it links
# ui_strings.js.
PAGE_SETTINGS_GLOBAL_NAME = "settings"

# The one counter every generator ranks, colours and divides by, recorded or
# derived. Point it at any counter callgrind.py knows and every page follows.
RANKING_COUNTER_NAME = "CEst"

# The report-root directory holding the shared copy of our own theme.
REPORT_ASSETS_DIR_NAME = "assets"

# What a report's raw data is stored as, one archive per test.
REPORT_RAW_ARCHIVE_SUFFIX = "txz"

# The report-root directory holding every heat map's source text, one copy
# of each profiled file rather than one per page that references it.
REPORT_SOURCES_DIR_NAME = "sources"

# The diff vocabulary, spelled the same everywhere a reader sees it. These
# are the only non-ASCII characters a dev/ source file may contain.
SOURCE_SCAN_ALLOWED_NON_ASCII_CHARS = (
    "≈",  # almost equal to
    "∞",  # infinity
    "▲",  # up-pointing triangle
    "▶",  # right-pointing triangle, the heat map's collapsed caret
    "▼",  # down-pointing triangle
    "…",  # horizontal ellipsis
)

# Which files under dev/ the ASCII scan reads.
SOURCE_SCAN_FILE_EXTENSIONS = (
    ".py",
    ".js",
    ".css",
    ".sh",
    ".html",
    ".c",
    ".h",
)
SOURCE_SCAN_FILE_NAMES = ("README.md",)

# Generated output and caches, which the ASCII scan walks straight past.
SOURCE_SCAN_SKIPPED_DIRS = (
    "__pycache__",
    "perf2html_baseline_report",
    "perf2html_modified_report",
    "perf2html_diff_report",
)

# The "curl.se/perf" link in every page's util block.
STRIP_CURL_PERF_SITE_HREF = "https://curl.se/perf/index.html"

# Width of a strip's status row, its first cell. The outer one says
# "perf2html"; the inner one says the selection path, so the budget is the
# longest test name plus separator plus the longest view label --
# "simpleformat / flame graph" is 26 today, and "<test> / summary" is
# shorter. flex-wrap: nowrap means too small clips mid-word.
STRIP_STATUS_ROW_WIDTH_CHARS = len("|-------------------------------|")

# Valgrind's own preamble, dropped from the log a page shows.
SUMMARY_PERF_LOG_SKIPPED_HEAD_LINES = 9

# What each time suffix a perf log can print is worth in seconds.
SUMMARY_TIME_SUFFIX_SECONDS: dict[str, float] = {
    "msec": 1e-3,
    "msecs": 1e-3,
    "ms": 1e-3,
    "nsec": 1e-9,
    "nsecs": 1e-9,
    "ns": 1e-9,
    "sec": 1.0,
    "secs": 1.0,
    "s": 1.0,
    "usec": 1e-6,
    "usecs": 1e-6,
    "us": 1e-6,
}

# How many functions the summary's top table lists.
SUMMARY_TOP_FUNCTION_ROWS = 50

# Spaces added to every table column beyond its widest cell.
TABLE_COLUMN_EXTRA_WIDTH_CHARS = 3

# Narrowest a dragged table column may get, in pixels.
TABLE_COLUMN_NARROWEST_DRAG_PX = 24

# Width of a table's function-name column, in characters.
TABLE_FUNCTION_NAME_WIDTH_CHARS = 20

# Where a table cuts a long "defined at" path.
TABLE_LOCATION_COLUMN_MAX_CHARS = 48

# Raw "User settings" THEME entries: odd index = dark member.
THEME_COLOR_PAIR_ENTRIES: list[str] = [
    "#1AB6FF",
    "#0097E6",
    "#F5F6FA",
    "#DCDDE1",
    "#FBC531",
    "#E1B12C",
    "#7F8FA6",
    "#718093",
    "#273C75",
    "#192A56",
    "#487EB0",
    "#40739E",
    "#353B48",
    "#2F3640",
]

# Smallest a file can be before it is plainly a failed generate rather than
# a small page. The flame graph page is a loader -- two script tags and a
# stylesheet link pointing at the shared bundle -- so it has a floor of its
# own, well under the one a page carrying real content must clear.
VALIDATE_ANY_PAGE_LEAST_BYTES = 500
VALIDATE_FLAME_GRAPH_PAGE_LEAST_BYTES = 300
VALIDATE_FLAME_GRAPH_SCRIPT_LEAST_BYTES = 200
VALIDATE_HEAT_MAP_PAGE_LEAST_BYTES = 5000
VALIDATE_OVERVIEW_PAGE_LEAST_BYTES = 2000
VALIDATE_RAW_ARCHIVE_LEAST_BYTES = 100

# Every setting the report's JavaScript reads, by name. The value itself is
# the module-level setting above, so a value the page and Python both use is
# written once and this list only says who else can see it. A page reads a
# name off the frozen object this list builds; Python reads the same name
# through load_into().
_BROWSER_SETTING_NAMES = (
    "HEAT_COLOR_ALPHA_HIGHEST",
    "HEAT_COLOR_ALPHA_LOWEST",
    "HEAT_COLOR_FULL_SCALE_PERCENT",
    "HEAT_COLOR_LIGHT_TEXT_ABOVE_SHARE",
    "HEAT_COLOR_SMALLEST_SCALE_TOP_SHARE",
    "HEAT_COLOR_SMALLEST_VISIBLE_SHARE",
    "HEAT_COLOR_WHOLE_PROFILE_SCALE_PERCENT",
    "HEAT_MAP_CONTROL_DROPDOWN_EXTRA_WIDTH_CHARS",
    "HEAT_MAP_HOME_LINES_LOCATION_MAX_CHARS",
    "HEAT_MAP_HOME_LINES_SOURCE_COLUMN_WIDTH_CHARS",
    "HEAT_MAP_HOME_LINES_SOURCE_TEXT_MAX_CHARS",
    "HEAT_MAP_HOME_TABLE_MAX_ROWS",
    "HEAT_MAP_MINIMAP_SHOWN_ABOVE_FILE_LINES",
    "HEAT_MAP_MINIMAP_SOURCE_WIDTH_CHARS",
    "HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX",
    "HEAT_MAP_SOURCE_HOT_LINE_BUTTON_LEAST_SHARE",
    "HEAT_MAP_SOURCE_HOT_LINE_BUTTON_MAX_COUNT",
    "HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS",
    "HEAT_MAP_TREE_AUTO_EXPAND_ABOVE_SHARE",
    "HEAT_MAP_TREE_COLOR_ALPHA_HIGHEST",
    "HEAT_MAP_TREE_COLOR_ALPHA_LOWEST",
    "HEAT_MAP_TREE_INDENT_FIRST_LEVEL_PX",
    "HEAT_MAP_TREE_INDENT_PER_LEVEL_PX",
    "HEAT_MAP_TREE_PANE_NARROWEST_PX",
    "LAYOUT_RESIZE_SETTLE_DELAY_MS",
    "TABLE_COLUMN_EXTRA_WIDTH_CHARS",
    "TABLE_COLUMN_NARROWEST_DRAG_PX",
    "TABLE_FUNCTION_NAME_WIDTH_CHARS",
    "TABLE_LOCATION_COLUMN_MAX_CHARS",
)

# The scalar types load_into() checks exactly. bool sits before int because
# bool is an int subclass, so an int annotation must not accept True.
_SCALAR_TYPES = (bool, int, float, str)


# Settings - the reader for the annotated settings a module declares.
class Settings:
    # Every setting this module exports, by name.
    def all_named(self) -> dict[str, object]:
        return {
            name: value
            for name, value in globals().items()
            if self.is_setting_name(name)
        }

    # Whether a module-level name is spelled the way a setting is: SCREAMING
    # snake case, with the leading underscore a private one keeps.
    def is_setting_name(self, name: str) -> bool:
        bare = name.lstrip("_")
        return bool(bare) and bare[0].isupper() and bare.isupper()

    # Read one module's declared settings and assign them into it. The
    # module declares each one as a bare annotation and names no value, so
    # the annotation is the whole request: it says which setting is wanted
    # and what type the module expects it to be.
    #
    # Until this returns, the whole SCREAMING_SNAKE namespace belongs to the
    # settings reader, so that what it walks is a clean list of names it was
    # asked for. A module's own constants are assigned after the call.
    def load_into(self, module_name: str) -> None:
        module = sys.modules[module_name]
        wanted = typing.get_type_hints(module)
        self.namespace_check(module_name, vars(module))
        for name, expected in wanted.items():
            if not self.is_setting_name(name):
                continue
            value = self.value_of(module_name, name)
            self.type_check(module_name, name, value, expected)
            setattr(module, name, value)

    # Stop a module that has already filled part of the reserved namespace.
    # Anything spelled like a setting and holding a value at this point is
    # either a setting this reader does not know or, far more often, one of
    # the module's own constants written above the settings instead of
    # below them.
    def namespace_check(
        self, module_name: str, scope: dict[str, object]
    ) -> None:
        taken = sorted(name for name in scope if self.is_setting_name(name))
        if not taken:
            return
        raise NameError(
            f"{module_name} already defines {', '.join(taken)}, which "
            "load_into() does not recognise as settings it was asked for. "
            "Every SCREAMING_SNAKE name belongs to the settings reader "
            "until load_into() returns, so that it walks a clean list of "
            "names. Move the file's own constants below the load_into() "
            "call. If one of these is meant to be a setting, declare it as "
            "a bare annotation here and define it in settings.py."
        )

    # Confirm a setting's value is the type the module annotated it with.
    # Scalars must match exactly -- no conversion, ever, so an annotation
    # that disagrees with settings.py is a hard error one of the two sides
    # has to fix. A container is checked to the container only; what it
    # holds is not walked.
    def type_check(
        self, module_name: str, name: str, value: object, expected: object
    ) -> None:
        wanted = typing.get_origin(expected) or expected
        if not isinstance(wanted, type):
            return
        found = type(value)
        if wanted in _SCALAR_TYPES or found in _SCALAR_TYPES:
            if found is not wanted:
                raise TypeError(
                    f"{module_name}.{name} is annotated "
                    f"{getattr(wanted, '__name__', wanted)}, but the "
                    f"setting is {found.__name__}. Settings are never "
                    "converted: correct the annotation, or change the "
                    "value in settings.py."
                )
            return
        if not isinstance(value, wanted):
            raise TypeError(
                f"{module_name}.{name} is annotated "
                f"{getattr(wanted, '__name__', wanted)}, but the setting is "
                f"{found.__name__}. Correct the annotation, or change the "
                "value in settings.py."
            )

    # The value of one setting, named as the declaring module spells it.
    def value_of(self, module_name: str, name: str) -> object:
        setting = name.lstrip("_")
        if setting not in globals() or not self.is_setting_name(setting):
            raise NameError(
                f"{module_name} declares {name}, so it is asking for the "
                f"setting {setting}, which settings.py does not define. Add "
                "it there, or correct the spelling here."
            )
        return globals()[setting]


_READER = Settings()


# Assign a module's declared settings into it, checking each one's type
# against the annotation the module declared it with.
def load_into(module_name: str) -> None:
    _READER.load_into(module_name)


# Build the generated assets/settings.js: the settings the browser reads, as
# one JSON literal frozen to its leaves and assigned to one global.
def settings_script_write() -> str:
    values = {name: globals()[name] for name in _BROWSER_SETTING_NAMES}
    data = json.dumps(values, indent=2, sort_keys=True, ensure_ascii=False)
    return f"const {PAGE_SETTINGS_GLOBAL_NAME} = {_DEEP_FREEZE}({data});\n"
