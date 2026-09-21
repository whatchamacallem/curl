from __future__ import annotations

import argparse, json, os, re, sys
from typing import NamedTuple, get_origin, get_type_hints

# What the report's one shared copy of the theme is written as. Every page
# in a report renders the same stylesheet and the same script, so they are
# written once at the report root and linked, not inlined 19 times. The heat
# map's own stylesheet and runtime, and the frame script every summary and
# overview page runs, are the same on all of them too, so they are shared
# the same way. Each page links only the ones it uses. theme.css and the
# settings file are generated rather than copied. This list runs on past
# the template names below it, which sort into the middle of it.
ASSET_FRAME_SCRIPT_NAME = "frame.js"
ASSET_HEAT_MAP_SCRIPT_NAME = "heatmap.js"
ASSET_HEAT_MAP_STYLESHEET_NAME = "heatmap.css"
ASSET_SETTINGS_SCRIPT_NAME = "settings.js"

# The four scripts/ files a generator reads as a template rather than
# copying, interleaved here by name among the shared assets above. Each
# holds the markers that generator substitutes its own content into, and
# nothing writes them into a report under these names, so they are read
# but never shared. No generator holds a multi-line literal, which is why
# each of these is a real file. The settings runtime is this file's own
# template, so settings_script_write() reads it the way a generator reads
# the other three.
ASSET_TEMPLATE_FLAME_GRAPH_BOOTSTRAP_NAME = "flame_bootstrap.js"
ASSET_TEMPLATE_FLAME_GRAPH_PAGE_NAME = "flame_graph.html"
ASSET_TEMPLATE_HEAT_MAP_PAGE_NAME = "heatmap.html"
ASSET_TEMPLATE_SETTINGS_RUNTIME_NAME = "settings_runtime.js"

ASSET_THEME_SCRIPT_NAME = "theme.js"
ASSET_THEME_STYLESHEET_NAME = "theme.css"
ASSET_UI_STRINGS_SCRIPT_NAME = "ui_strings.js"

# Every counter callgrind never records, and the recorded ones each is
# added up from. The key is what a page calls the counter, and the value maps
# each recorded counter it needs to the whole number that counter is
# multiplied by. A run offers a derived counter only when it recorded every
# input named here, and nothing stores one: a derived counter is a pure
# function of the recorded slots, so a stored copy could only go stale.
# callgrind.py is the one reader, and these are the only place a coefficient
# is written down. Adding or dropping a counter is an edit here plus its
# description in ui_strings.js and README.md -- no code changes.
DERIVED_COUNTER_TERMS: dict[str, dict[str, int]] = {
    "D1m": {"D1mr": 1, "D1mw": 1},
    "DLm": {"DLmr": 1, "DLmw": 1},
    "L1m": {"I1mr": 1, "D1mr": 1, "D1mw": 1},
    "LLm": {"ILmr": 1, "DLmr": 1, "DLmw": 1},
    "Bm": {"Bcm": 1, "Bim": 1},
    "CEst": {
        "Ir": 1,
        "I1mr": 10,
        "D1mr": 10,
        "D1mw": 10,
        "ILmr": 100,
        "DLmr": 100,
        "DLmw": 100,
    },
}

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
# the cut lands on the top of that range. The eighth records 3,180 cheap
# calls. Retune if a test's shape changes.
FLAME_GRAPH_MAX_RECORDED_CALLS = 200

# All a per-test flame graph directory may hold: its own page, its own
# recorded profile, and the trace log. Everything else lives in the one
# shared bundle at the report root.
FLAME_GRAPH_PAGE_FILE_NAMES = ("index.html", "output.txt", "profile.js")

# What the bootstrap plus its embedded profile gets written as.
FLAME_GRAPH_PROFILE_SCRIPT_NAME = "profile.js"

# The flame graph view a summary page links, as key, link label, page path.
# A test links it only where a trace was actually recorded, which is why it
# is named apart from the heat map view rather than sharing one list. The
# key is what the URL hash calls the view and what the frame script matches,
# so it is a boundary name. The label is rendered into the page by
# build_report.py, which is the one boundary ui_strings.js cannot cross.
FLAME_GRAPH_VIEW_ENTRY: tuple[str, str, str] = (
    "flame-graph",
    "flame graph",
    "flame-graph/index.html",
)

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
# Every heated cell blends one of these over the page background, and the
# outer strip's wordmark steps its letters across the ramp's upper half as
# plain text colour, so a retune moves both.
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

# The smallest share theme.heat_t() still paints, and the bottom of the
# log scale it measures against its caller's own maximum. Only the summary
# and overview tables that theme.py renders read it. It is not the "<0.01%"
# notation floor, which is NUMBER_SMALLEST_PRINTED_PERCENT, and the heat
# map's own heat_of_share() has no floor at all: that mapping measures
# nothing off the data, which is why the page never reads this.
HEAT_COLOR_SMALLEST_VISIBLE_SHARE = 0.001

# Width a <select> adds beyond its longest option text, so the chosen option
# is not clipped by the dropdown arrow.
HEAT_MAP_CONTROL_DROPDOWN_EXTRA_WIDTH_CHARS = 4

# How the page finds a counter's description: this prefix, then the counter
# name lowercased. So "CEst" reads str_counter_cest out of ui_strings.js,
# and a counter added to DERIVED_COUNTER_TERMS or recorded by a new
# callgrind run needs only its entry there, never a map in the page script.
# A counter with no entry falls back to showing its bare name.
HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX = "str_counter_"

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

# The counters the heat map shows beside the selected one, in the order the
# columns are drawn. A counter named here that the run cannot supply is
# simply left out, so naming one no profile records costs nothing.
HEAT_MAP_SECONDARY_COUNTER_NAMES: tuple[str, ...] = ("D1m", "DLm", "Bcm")

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

# The heat map view a summary page links, as key, link label, page path.
# Every test has one, recorded trace or not. Spelled the same way as
# FLAME_GRAPH_VIEW_ENTRY, and carrying a label for the same reason.
HEAT_MAP_VIEW_ENTRY: tuple[str, str, str] = (
    "heat-map",
    "heat map",
    "heat-map/index.html",
)

# Milliseconds a window resize settles for before the page re-measures. A
# drag fires resize continuously, and re-measuring every frame is what this
# delay exists to avoid.
LAYOUT_RESIZE_SETTLE_DELAY_MS = 120

# The smallest percentage a table prints as a number. Under it a full
# report renders "<0.01%" and a diff renders the arrow plus "≈0.00%", both
# of which state a bound rather than a value. It is a notation floor and
# nothing else: it picks no colour, hides no row and is never a
# denominator. It is not HEAT_COLOR_SMALLEST_VISIBLE_SHARE, which is the
# bottom of theme.heat_t()'s log colour scale. theme.py renders the number
# server-side and heatmap.js renders it on the page, so both read this one
# value and the two spellings of the notation cannot drift apart.
NUMBER_SMALLEST_PRINTED_PERCENT = 0.01

# The page font: Monaco first, then whatever else the box has.
PAGE_FONT_FAMILY = (
    'Monaco, Menlo, "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace'
)

# The global the generated settings file assigns its one statement to. A page
# links that file before every script that reads it, the way it links
# ui_strings.js. settings_script_write() fills the runtime template's name
# marker with this, so the page calls what is spelled here.
PAGE_SETTINGS_GLOBAL_NAME = "settings"

# The one counter every generator ranks, colours and divides by, recorded or
# derived. Point it at any counter callgrind.py knows and every page follows.
RANKING_COUNTER_NAME = "CEst"

# The report-root directory holding the shared copy of our own theme.
REPORT_ASSETS_DIR_NAME = "assets"

# The LABEL= row a report's MANIFEST.txt records its checksum on. The shell
# writes that row and reads it back, validate_report.py and reformat.sh
# check it, so the label is one spelling here rather than one per reader.
REPORT_MANIFEST_CHECKSUM_LABEL = "checksum"

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
# "perf2html". The inner one says the selection path, so the budget is the
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

# What the seven THEME_COLOR_PAIR_ENTRIES pairs are called, in the order
# that list gives them. Each name becomes the CSS variables --<name> and
# --<name>-l, so these are boundary names, and there must be one name for
# every pair the entries hold.
THEME_COLOR_PAIR_NAMES: tuple[str, ...] = (
    "blue",
    "white",
    "yellow",
    "gray",
    "navy",
    "steel",
    "slate",
)

# How much darker than its named colour the page background is drawn. The
# whole page follows --bg: the scrollbar track, the minimap band and every
# heat blend, so this is the one number that moves them together.
THEME_COLOR_ROLE_BACKGROUND_SHADE_FACTOR = 0.90

# What each colour is actually for, as the CSS variable name every page
# reads, then which THEME_COLOR_PAIR_NAMES pair it is taken from and which
# member of that pair. The member is "light" or "dark". "bg" is the one
# entry the pair alone does not settle, because it is its pair's dark
# member darkened by THEME_COLOR_ROLE_BACKGROUND_SHADE_FACTOR. Renaming a
# role renames a CSS variable every stylesheet and page script reads, so
# these keys are boundary names.
THEME_COLOR_ROLE_SOURCES: dict[str, tuple[str, str]] = {
    "bg": ("slate", "dark"),
    "bg-alt": ("slate", "light"),
    "panel": ("navy", "dark"),
    "nav": ("navy", "dark"),
    "sel": ("navy", "light"),
    "fg": ("white", "light"),
    "fg-dim": ("white", "dark"),
    "muted": ("white", "dark"),
    "link": ("blue", "light"),
    "accent": ("yellow", "light"),
    "bar": ("steel", "dark"),
}

# The units a printed duration is measured in, largest first, each as the
# suffix to print and how many seconds one of them lasts. num_time() prints
# a value in the first unit it reaches, so the order is what decides
# whether 0.5 ms reads as 500.00us or 0.50ms. This is the printing ladder,
# not SUMMARY_TIME_SUFFIX_SECONDS, which reads suffixes a perf log already
# wrote.
THEME_TIME_UNIT_ENTRIES: tuple[tuple[str, float], ...] = (
    ("s", 1.0),
    ("ms", 1e-3),
    ("us", 1e-6),
    ("ns", 1e-9),
    ("ps", 1e-12),
)

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

# What a perf2html_diff.sh report is expected to contain, and what a
# perf2html.sh report is expected to contain. These two are the whole
# difference between checking a diff and checking a full report, which is
# why validate_report.py reads its checks off them rather than branching
# on which kind it was handed. Each holds:
#   subpages          the per-test view directories that must exist
#   heading           the pattern the top-N heading has to match
#   header_blocks     the header blocks the overview must carry
#   manifest_version  the exact first line of MANIFEST.txt, which is also
#                     the only thing that makes a directory a diff input
#   manifest_labels   the LABEL= rows MANIFEST.txt must have
#   test_has_rawdata  whether a test records runs of its own -- a perf
#                     log, a trace, a flame graph. never true of the
#                     synthesized "all"
#   all_has_archive   whether "all" stores an archive of its own, which it
#                     does only where its pages are built from data no
#                     other test's archive holds
VALIDATE_REPORT_LAYOUT_DIFF: dict[str, object] = {
    "subpages": ("heat-map",),
    "heading": r"<h2>top \d+ functions by change in self</h2>",
    "header_blocks": ("baseline", "modified"),
    "manifest_version": "curl/perf2html_diff.sh v1",
    "manifest_labels": ("baseline", "modified", "stamp"),
    "test_has_rawdata": False,
    "all_has_archive": True,
}
VALIDATE_REPORT_LAYOUT_FULL: dict[str, object] = {
    "subpages": ("flame-graph", "heat-map"),
    "heading": r"<h2>top \d+ functions by self</h2>",
    "header_blocks": (),
    "manifest_version": "curl/perf2html.sh v1",
    "manifest_labels": (
        "sampled",
        "revision",
        "cpu",
        "build",
        "executable",
        "stamp",
    ),
    "test_has_rawdata": True,
    "all_has_archive": False,
}

# Every setting the report's JavaScript reads, by name. The value itself is
# the module-level setting above, so a value the page and Python both use is
# written once and this list only says who else can see it. A page reads a
# name off the frozen object this list builds. Python reads the same name
# through load_into().
_BROWSER_SETTING_NAMES = (
    "HEAT_COLOR_ALPHA_HIGHEST",
    "HEAT_COLOR_ALPHA_LOWEST",
    "HEAT_COLOR_FULL_SCALE_PERCENT",
    "HEAT_COLOR_LIGHT_TEXT_ABOVE_SHARE",
    "HEAT_COLOR_RAMP_STOPS",
    "HEAT_MAP_CONTROL_DROPDOWN_EXTRA_WIDTH_CHARS",
    "HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX",
    "HEAT_MAP_HOME_LINES_LOCATION_MAX_CHARS",
    "HEAT_MAP_HOME_LINES_SOURCE_COLUMN_WIDTH_CHARS",
    "HEAT_MAP_HOME_LINES_SOURCE_TEXT_MAX_CHARS",
    "HEAT_MAP_HOME_TABLE_MAX_ROWS",
    "HEAT_MAP_MINIMAP_SHOWN_ABOVE_FILE_LINES",
    "HEAT_MAP_MINIMAP_SOURCE_WIDTH_CHARS",
    "HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX",
    "HEAT_MAP_SECONDARY_COUNTER_NAMES",
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
    "NUMBER_SMALLEST_PRINTED_PERCENT",
    "TABLE_COLUMN_EXTRA_WIDTH_CHARS",
    "TABLE_COLUMN_NARROWEST_DRAG_PX",
    "TABLE_FUNCTION_NAME_WIDTH_CHARS",
    "TABLE_LOCATION_COLUMN_MAX_CHARS",
)

# The scalar types load_into() checks exactly. bool sits before int because
# bool is an int subclass, so an int annotation must not accept True.
_SCALAR_TYPES = (bool, int, float, str)

# The field of a report layout that holds its MANIFEST.txt version line,
# which is the value the shell wants out of the two layout settings.
_SHELL_SETTING_LAYOUT_FIELD = "manifest_version"

# Every setting report_manifest.sh reads, by name, and the shell variable
# each one is assigned to. Shell cannot import this module, so it runs
# "python3 settings.py --shell" once as it is sourced and evals what comes
# back. The names differ because a shell variable is read bare, with no
# module in front of it, so REPORT_MANIFEST says which manifest it is where
# a bare CHECKSUM_LABEL would not. The values are the ones Python reads, so
# the writer of a MANIFEST.txt and every reader that checks one back spell
# the same strings.
_SHELL_SETTING_VARIABLES = (
    ("CHECKSUM_LABEL", "REPORT_MANIFEST_CHECKSUM_LABEL"),
    ("DIFF_MANIFEST", "VALIDATE_REPORT_LAYOUT_DIFF"),
    ("REPORT_MANIFEST", "VALIDATE_REPORT_LAYOUT_FULL"),
)


# LostSetting - one SCREAMING_SNAKE constant a file assigns below its
# load_into() call, where a reader of the file's head does not see it.
class LostSetting(NamedTuple):
    # How the constant is spelled, leading underscore kept.
    name: str
    # The file holding it.
    path: str
    # The 1-based line the assignment sits on.
    line: int


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

    # A bare annotation is the whole request: which setting, and the type
    # expected. The SCREAMING_SNAKE namespace is ours until this returns.
    def load_into(self, module_name: str) -> None:
        module = sys.modules[module_name]
        wanted = get_type_hints(module)
        self.namespace_check(module_name, vars(module))
        for name, expected in wanted.items():
            if not self.is_setting_name(name):
                continue
            value = self.value_of(module_name, name)
            self.type_check(module_name, name, value, expected)
            setattr(module, name, value)

    # Stop a module that already filled part of the reserved namespace --
    # almost always its own constants written above load_into(), not below.
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

    # The settings report_manifest.sh evals as it is sourced. A layout hands
    # over its version line only. Every value is quoted so none runs as shell.
    def shell_script_write(self) -> str:
        lines: list[str] = []
        for variable, name in _SHELL_SETTING_VARIABLES:
            value = globals()[name]
            if isinstance(value, dict):
                value = value[_SHELL_SETTING_LAYOUT_FIELD]
            quoted = str(value).replace("'", "'\\''")
            lines.append(f"{variable}='{quoted}'")
        return "\n".join(lines) + "\n"

    # Confirm a value matches its annotation. Scalars exactly, never
    # converted. A container is checked to the container, not walked.
    def type_check(
        self, module_name: str, name: str, value: object, expected: object
    ) -> None:
        wanted = get_origin(expected) or expected
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

    # Every SCREAMING_SNAKE assignment a file makes below its load_into()
    # call, in written order: its own constants, invisible from the head.
    def lost_settings(self, path: str) -> list[LostSetting]:
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().split("\n")
        call_line = 0
        for index, text in enumerate(lines, start=1):
            if text.startswith(_LOAD_INTO_CALL_TEXT):
                call_line = index
                break
        if not call_line:
            return []
        found: list[LostSetting] = []
        for index, text in enumerate(lines[call_line:], start=call_line + 1):
            matched = _ASSIGNED_NAME_RE.match(text)
            if matched and self.is_setting_name(matched.group(1)):
                found.append(LostSetting(matched.group(1), path, index))
        return found

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


# A module-level assignment, capturing the name being assigned. Anchored,
# so an indented assignment inside a class or function is not one.
_ASSIGNED_NAME_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s*(?::[^=]+)?=")

# The scripts/ directory this module was loaded from, which is also where
# the runtime template sits.
_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# How the load_into() call is written at the top of every file that has
# one, matched at the start of the line.
_LOAD_INTO_CALL_TEXT = "settings.load_into("

# What settings_script_write() substitutes in the runtime template: the
# JSON literal of every setting the browser reads, and the name the page
# calls the reader by. Both are bare identifiers in the template, so
# node --check parses the file before anything is filled in.
_PAGE_SETTINGS_DATA_MARKER = "__DATA__"
_PAGE_SETTINGS_NAME_MARKER = "__NAME__"

_READER = Settings()


# Assign a module's declared settings into it, checking each one's type
# against the annotation the module declared it with.
def load_into(module_name: str) -> None:
    _READER.load_into(module_name)


# Every SCREAMING_SNAKE constant one source file assigns below its
# load_into() call.
def lost_settings(path: str) -> list[LostSetting]:
    return _READER.lost_settings(path)


# Build assets/settings.js: the browser's settings as one frozen JSON
# literal in settings_runtime.js, opened here -- theme.py would cycle.
def settings_script_write() -> str:
    values = {name: globals()[name] for name in _BROWSER_SETTING_NAMES}
    data = json.dumps(values, indent=2, sort_keys=True, ensure_ascii=False)
    with open(
        os.path.join(_DIRECTORY, ASSET_TEMPLATE_SETTINGS_RUNTIME_NAME),
        encoding="utf-8",
    ) as handle:
        runtime = handle.read()
    return runtime.replace(
        _PAGE_SETTINGS_NAME_MARKER, PAGE_SETTINGS_GLOBAL_NAME
    ).replace(_PAGE_SETTINGS_DATA_MARKER, data)


# Build the shell assignments report_manifest.sh evals while it is sourced.
def shell_script_write() -> str:
    return _READER.shell_script_write()


# main - Print the settings the shell reads. The whole command-line
# surface: nothing here writes a file or takes a path.
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--shell",
        action="store_true",
        help="print the settings report_manifest.sh reads",
    )
    args = parser.parse_args()
    if not args.shell:
        parser.print_usage(sys.stderr)
        return 2
    sys.stdout.write(shell_script_write())
    return 0


if __name__ == "__main__":
    sys.exit(main())
