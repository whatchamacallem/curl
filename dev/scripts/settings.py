from __future__ import annotations

import json, os, re, sys
from collections.abc import Sequence
from typing import NoReturn, get_origin, get_type_hints

# Every setting the tools have, then the reader that checks and assigns
# them. _SETTING_NAMES is the line between the two.

# What the report's one shared copy of the theme is written as: written once
# at the report root and linked, never inlined. Each page links what it uses.
ASSET_CALLERS_SCRIPT_NAME = "callers.js"
ASSET_ERROR_OVERLAY_SCRIPT_NAME = "error_overlay.js"
ASSET_FLAME_GRAPH_SCRIPT_NAME = "flame_graph.js"
ASSET_FRAME_SCRIPT_NAME = "frame.js"
ASSET_HEAT_MAP_SCRIPT_NAME = "heatmap.js"
ASSET_HEAT_MAP_STYLESHEET_NAME = "heatmap.css"
ASSET_MENU_SCRIPT_NAME = "menu.js"
ASSET_MENU_STYLESHEET_NAME = "menu.css"

# The one script in assets/ naming every file and function the merged test's
# heat map opens, which the pulldowns offer whichever test is active.
ASSET_PULLDOWN_TEXT_SCRIPT_NAME = "pulldown_text.js"

ASSET_SETTINGS_SCRIPT_NAME = "settings.js"

# The four scripts/ files a generator reads as a template, each holding the
# markers it substitutes into. Read but never shared into a report.
ASSET_TEMPLATE_FLAME_GRAPH_PAGE_NAME = "flame_graph.html"
ASSET_TEMPLATE_HEAT_MAP_PAGE_NAME = "heatmap.html"
ASSET_TEMPLATE_OVERVIEW_PAGE_NAME = "overview.html"
ASSET_TEMPLATE_SETTINGS_HANDLER_NAME = "settings.js"

ASSET_THEME_SCRIPT_NAME = "theme.js"
ASSET_THEME_STYLESHEET_NAME = "theme.css"
ASSET_UI_STRINGS_SCRIPT_NAME = "ui_strings.js"

# Valgrind's own preamble, dropped from the log a page shows.
CALLERS_PERF_LOG_SKIPPED_HEAD_LINES = 9

# What each time suffix a perf log can print is worth in seconds.
CALLERS_TIME_SUFFIX_SECONDS: dict[str, float] = {
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

# How many functions the callers page's top table lists.
CALLERS_TOP_FUNCTION_ROWS = 50

# The callers view's key, an address's view for a test's own page at
# <test>/index.html. Its label is ui_strings.js's str_view_callers.
CALLERS_VIEW_KEY = "callers"

# Every counter callgrind never records, as the recorded ones it sums from
# and each one's coefficient. Nothing stores one.
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

# What callgrind_diff.py's synthesized callers diff is named, beside the
# delta. Written by perf2html_diff.sh, read back by build_report.py.
DIFF_CALLER_COUNTS_FILE_SUFFIX = ".callers.json"

# Only a flame graph our own tool exported counts -- a stale or hand-made
# one must fail.
FLAME_GRAPH_EXPORTER_NAME = "dev/scripts/trace_to_speedscope.py"

# The localProfilePath a flame graph address names: speedscope defines its
# loader only when the address holds one, and finds nothing at the name.
FLAME_GRAPH_LOCAL_PROFILE_PATH = "profile"

# The most complete calls one trace keeps, cut at the top of the current
# TESTS_C's 79-202 range. Retune if a test's shape changes.
FLAME_GRAPH_MAX_RECORDED_CALLS = 200

# The flame graph page's directory of profile scripts, one <test>.js per
# traced test, each adding its {name, base64} to the global under its test.
FLAME_GRAPH_PROFILE_DIR_NAME = "profiles"
FLAME_GRAPH_PROFILE_GLOBAL_NAME = "report_flame_graph_profiles"

# How the flame graph page polls for speedscope, which defines its global
# only once its script ran. The two multiply into the failure's seconds.
FLAME_GRAPH_STARTUP_POLL_DELAY_MS = 50
FLAME_GRAPH_STARTUP_POLL_MAX_ATTEMPTS = 200

# The flame graph view as key, label, and its one page's path from the report
# root. A full report has that view, a test only where a trace was recorded.
FLAME_GRAPH_VIEW_ENTRY: tuple[str, str, str] = (
    "flame-graph",
    "flame graph",
    "flame-graph/index.html",
)

# How the page finds a counter's description: this prefix then the name
# lowercased, so "CEst" reads str_counter_cest out of ui_strings.js.
HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX = "str_counter_"

# In the home page's hot-lines table: the widest the "defined at" and source
# columns measure (each one's clip), and how much of a source line a row keeps.
HEAT_MAP_HOME_LINES_LOCATION_MAX_CHARS = 28
HEAT_MAP_HOME_LINES_SOURCE_COLUMN_MAX_CHARS = 36
HEAT_MAP_HOME_LINES_SOURCE_SNIPPET_MAX_CHARS = 110

# Rows in each of the two home tables.
HEAT_MAP_HOME_TABLE_MAX_ROWS = 60

# The minimap's fixed column scale, the same 80 the source view uses. It is
# never widened to the file's longest line.
HEAT_MAP_MINIMAP_SOURCE_WIDTH_CHARS = 80

# Smallest the minimap's viewport box may be drawn, in pixels, so the box
# marking what is on screen stays visible in a very long file.
HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX = 8

# The heat map page's directory of model scripts, one <test>.js per test,
# the merged one too, each adding its model to the global under its test.
HEAT_MAP_MODEL_DIR_NAME = "data"
HEAT_MAP_MODEL_GLOBAL_NAME = "report_heat_map_models"

# The counters the heat map shows beside the selected one, in column order.
# One the run cannot supply is left out, so naming an unrecorded one is free.
HEAT_MAP_SECONDARY_COUNTER_NAMES: tuple[str, ...] = ("D1m", "DLm", "Bcm")

# The share of the file a line must carry to earn a ticker tape entry above
# the source, and how many entries a file view's ticker tape shows at most.
HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_LEAST_SHARE = 0.01
HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_MAX_COUNT = 10

# The standard width C source is rendered at. Not dev/'s own 79-column
# source limit -- this is the width of the profiled file's view.
HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS = 80

# Directories whose tracked .c/.h are listed even when nothing sampled them,
# so a file with no cost is visibly cold rather than simply missing.
HEAT_MAP_TREE_ALWAYS_LISTED_DIRS = ("lib", "include", "src", "tests/perf")

# The share of the profile a directory must hold to be expanded on first
# render, so a reader opens on the code that matters.
HEAT_MAP_TREE_AUTO_EXPAND_ABOVE_SHARE = 0.05

# The heat map view as key, label, and its one page's path from the report
# root. The label is its menu button's and its title's. Every test has one.
HEAT_MAP_VIEW_ENTRY: tuple[str, str, str] = (
    "heat-map",
    "heatmap",
    "heat-map/index.html",
)

# Milliseconds a window resize settles for before the page re-measures: a
# drag fires resize continuously, and every frame is what this avoids.
LAYOUT_RESIZE_SETTLE_DELAY_MS = 120

# Each numbered menu button by the name in its id, menu-<name>-button-, in
# bar order. Its place is its number and key, 1 to 9 then 0, shown or not.
MENU_BUTTON_ORDER: tuple[str, ...] = (
    "overview",
    "test",
    "file",
    "function",
    "heat-map",
    "callers",
    "flame-graph",
    "reset",
    "help",
    "scale",
)

# The keys an open pulldown answers, which a framed page sends up while the
# tests one is open, as KeyboardEvent.key names.
MENU_PULLDOWN_KEY_NAMES: dict[str, str] = {
    "close": "Escape",
    "next": "ArrowDown",
    "previous": "ArrowUp",
    "select": "Enter",
}

# The file pulldown's search text naming a line, as a JavaScript pattern:
# group 1 is the text it filters by, group 2 the line its entries open at.
MENU_PULLDOWN_LINE_NUMBER_PATTERN = "^(.*):([0-9]+)$"

# The test merging every other, named as perf2html.sh names its directory.
# The pulldowns work in it at the overview's home: data, not a UI word.
MENU_PULLDOWN_MERGED_TEST_NAME = "all"

# A KeyboardEvent.key typed outside a field that opens the tests pulldown
# with itself in the search box, as a JavaScript pattern.
MENU_PULLDOWN_OPENING_KEY_PATTERN = "^[a-zA-Z]$"

# Printable keys no pulldown takes as typed: outside a field they stay with
# the page (space scrolls it), in an open box they type themselves.
MENU_PULLDOWN_SKIPPED_KEY_NAMES: tuple[str, ...] = (" ",)

# The keys the focused scale button moves its bar by, one stop each, as
# KeyboardEvent.key names.
MENU_SCALE_KEY_NAMES: dict[str, str] = {
    "larger": "ArrowRight",
    "smaller": "ArrowLeft",
}

# The multiple a rise stops printing at, becoming the ">1000x" bound. A drop
# cannot pass -100%, so only a rise reaches it. theme.py and theme.js read it.
NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES = 999.99

# The smallest percentage a table prints as a number, under which it states
# a bound. A notation floor only: no colour, no filter, never a denominator.
NUMBER_SMALLEST_PRINTED_PERCENT = 0.01

# The global the generated settings file assigns to, linked before every
# script reading it. settings_script_write() fills the template's marker.
PAGE_SETTINGS_GLOBAL_NAME = "settings"

# The window share a dragged pane may not pass: the wide end stops a drag
# closing the far pane. Each pane's own floor is its caller's setting.
PANE_SPLITTER_WIDEST_WINDOW_SHARE = 0.6

# The one counter every generator ranks, colours and divides by, recorded or
# derived. Point it at any counter callgrind.py knows and every page follows.
RANKING_COUNTER_NAME = "CEst"

# The report-root directory holding every heat map's source text, one copy
# of each profiled file rather than one per page that references it.
REPORT_SOURCES_DIR_NAME = "sources"

# Every localStorage key a report owns, exact keys and shared prefixes. One
# missing from both outlives every bump. Browser keys, so boundary names.
STORAGE_OWNED_KEYS: tuple[str, ...] = (
    "heat.counter",
    "heat.scale",
    "heat.sort",
    "view.scale",
)
STORAGE_OWNED_PREFIXES: tuple[str, ...] = ("split.",)

# What a report writes under STORAGE_VERSION_KEY, a bare string, not JSON.
# Anything but exactly it sweeps every owned key: that is how a bump rolls out.
STORAGE_VERSION = "perf2html v4"
STORAGE_VERSION_KEY = "perf2html.version"

# Each palette colour and the roles it paints, one role under one colour.
# Each role becomes the CSS variable --<role>, so roles are boundary names.
STYLE_COLOR_PAIR_ENTRIES: dict[str, list[str]] = {
    "#1AB6FF": [
        "heat-map-source-line-detail-action-bar-link-fg-",
        "heat-map-source-table-line-number-cell-callee-marker-fg-",
        "menu-button-fg-",
        "menu-pulldown-entry-current-fg-",
        "menu-pulldown-entry-highlighted-bg-",
        "page-link-fg-",
    ],
    "#0097E6": [
        "page-scrollbar-thumb-bg-dim-",
    ],
    "#F5F6FA": [
        "callers-collapsed-section-title-focus-fg-",
        "callers-heat-cell-on-dark-fg-",
        "heat-map-heat-cell-on-dark-fg-",
        "heat-map-menu-field-fg-",
        "heat-map-source-file-header-statistic-share-fg-",
        "heat-map-source-line-detail-function-name-fg-",
        "heat-map-source-table-row-focus-fg-",
        "heat-map-source-ticker-tape-entry-focus-fg-",
        "heat-map-tree-node-focus-fg-",
        "menu-button-current-bg-",
        "menu-button-focus-bg-",
        "menu-strip-fg-",
        "menu-title-fg-",
        "page-body-fg-",
        "page-link-focus-fg-",
        "page-table-row-focus-fg-",
        "screenshot-label-fg-",
    ],
    "#DCDDE1": [
        "callers-collapsed-section-file-name-fg-dim-",
        "callers-collapsed-section-title-fg-dim-",
        "callers-collapsed-section-title-marker-fg-dim-",
        "heat-map-menu-label-fg-dim-",
        "heat-map-menu-search-box-placeholder-fg-dim-",
        "heat-map-source-file-header-statistic-fg-dim-",
        "heat-map-source-line-detail-action-bar-separator-fg-dim-",
        "heat-map-source-line-detail-close-symbol-fg-dim-",
        "heat-map-source-line-detail-heading-fg-dim-",
        "heat-map-source-table-counter-cell-fg-dim-",
        "heat-map-source-table-line-number-cell-fg-dim-",
        "heat-map-source-ticker-tape-label-fg-dim-",
        "heat-map-source-unavailable-note-fg-dim-",
        "heat-map-tree-node-caret-fg-dim-",
        "heat-map-tree-node-name-cold-fg-dim-",
        "heat-map-tree-node-name-more-fg-dim-",
        "heat-map-tree-node-share-percent-fg-dim-",
        "menu-pulldown-no-match-note-fg-dim-",
        "menu-pulldown-search-box-placeholder-fg-dim-",
        "page-heading-fg-dim-",
        "page-table-column-title-fg-dim-",
        "page-table-dimmed-text-fg-dim-",
    ],
    "#FBC531": [],
    "#E1B12C": [],
    "#7F8FA6": [],
    "#718093": [],
    "#273C75": [
        "callers-collapsed-section-log-box-focus-bg-",
        "callers-collapsed-section-title-focus-bg-",
        "heat-map-main-focus-bg-",
        "heat-map-menu-field-focus-bg-",
        "heat-map-source-file-header-bg-",
        "heat-map-source-table-column-title-bg-",
        "heat-map-source-table-row-focus-bg-",
        "heat-map-source-ticker-tape-bg-",
        "heat-map-source-ticker-tape-entry-focus-bg-",
        "heat-map-tree-node-focus-bg-",
        "heat-map-tree-node-selected-bg-",
        "heat-map-tree-resize-handle-focus-bg-",
        "menu-button-bg-",
        "menu-pulldown-entry-current-bg-",
        "page-link-focus-bg-",
        "page-table-row-focus-bg-",
    ],
    "#192A56": [
        "callers-collapsed-section-log-box-bg-dim-",
        "callers-collapsed-section-log-box-scrollbar-bg-dim-",
        "heat-map-menu-field-bg-dim-",
        "heat-map-menu-strip-bg-dim-",
        "heat-map-source-line-detail-bg-dim-",
        "menu-button-current-fg-dim-",
        "menu-button-focus-fg-dim-",
        "menu-pulldown-entry-highlighted-fg-dim-",
        "menu-pulldown-entry-list-bg-dim-",
        "page-table-column-title-bg-dim-",
    ],
    "#487EB0": [],
    "#40739E": [],
    "#353B48": [
        "heat-map-source-ticker-tape-entry-bg-",
        "page-table-alternate-column-bg-",
    ],
    "#2F3640": [
        "callers-heat-cell-on-bright-fg-dim-",
        "heat-map-heat-cell-on-bright-fg-dim-",
        "heat-map-main-bg-dim-",
        "heat-map-minimap-bg-dim-",
        "heat-map-source-line-detail-table-bg-dim-",
        "menu-strip-bg-dim-",
        "menu-title-bg-dim-",
        "overview-view-frame-bg-dim-",
        "page-body-bg-dim-",
        "page-scrollbar-corner-bg-dim-",
        "page-scrollbar-track-bg-dim-",
    ],
    "#000000": [
        "screenshot-label-bg-",
        "screenshot-label-border-",
    ],
}

# The width of the coordinate space every page is designed in: every length
# is written for this box, which theme.js's design_scale_apply() then fits.
STYLE_DESIGN_COORDINATES_WIDTH_PX = 1920

# The design font, Monaco at STYLE_DESIGN_FONT_SIZE_PX, is this many px per
# ch. theme.js's font_fit_apply() scales the box's font to it: ch is design ch.
STYLE_DESIGN_FONT_CHARACTER_WIDTH_PX = 7.2

# The CSS variable carrying the font fit, a multiplier on every font size
# the theme sets: 1 is the design font itself.
STYLE_DESIGN_FONT_FIT_PROPERTY = "--design-font-fit-"

# The design font size, written as --design-font-size-px-, which the font fit
# multiplies.
STYLE_DESIGN_FONT_SIZE_PX = 12

# Below this window width design_scale_apply() stops shrinking the zoom, and
# an unframed page's root keeps the design width: the window scrolls sideways.
STYLE_DESIGN_MINIMUM_WINDOW_WIDTH_PX = 1280

# What the scale bar zooms the main page contents by on an untouched page,
# mid-travel whatever the ends, each half geometric. The menu never scales.
STYLE_DESIGN_SCALE_DEFAULT_MULTIPLE = 1

# Where along the scale bar the default multiple sits, as a share of its
# last stop: the middle, so the bar starts half full whatever the ends are.
STYLE_DESIGN_SCALE_DEFAULT_TRAVEL_SHARE = 0.5

# What the scale bar zooms the main page contents by at each end.
STYLE_DESIGN_SCALE_LARGEST_MULTIPLE = 2
STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE = 0.5

# The scale bar's stops, the first with no cell filled and each one after
# filling one more. at 21 all bars are filled.
STYLE_DESIGN_SCALE_STOP_COUNT = 21

# How many decimals a stop's multiple keeps. The zoom is rounded to the
# number the scale button prints, so printing cuts no fraction off.
STYLE_DESIGN_SCALE_STOP_MULTIPLE_FRACTION_DIGITS = 2

# The CSS variable carrying the window's height in design pixels. A vh is
# zoomed like any length, so a full-height rule reads this instead.
STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY = "--design-viewport-height-"

# The luminance above which a heat cell counts as bright, its text taking
# the cell's on-bright role instead of its on-dark one.
STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE = 0.5

# A share at or past this is already fully lit, so the handful of diff lines
# reading millions of percent cannot flatten the scale.
STYLE_HEAT_COLOR_FULL_SCALE_PERCENT = 100

# The 12-stop heat ramp, cold to hot, kept apart from the theme palette.
# Carried opaque by a cell, stepped across by the logo: a retune hits both.
STYLE_HEAT_COLOR_STOPS: list[str] = [
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

# Width a <select> adds beyond its longest option text, so the chosen option
# is not clipped by the dropdown arrow.
STYLE_HEAT_MAP_MENU_DROPDOWN_EXTRA_WIDTH_CHARS = 4

# Room a source line number keeps for the callee marker drawn before it.
STYLE_HEAT_MAP_SOURCE_LINE_NUMBER_MARKER_WIDTH_CHARS = 2

# How many characters each level of the heat map's tree is indented by.
STYLE_HEAT_MAP_TREE_INDENT_PER_LEVEL_CHARS = 2

# Narrowest the heat map's tree pane is drawn or may be dragged, in pixels.
STYLE_HEAT_MAP_TREE_PANE_NARROWEST_PX = 120

# Where on the heat ramp the menu's logo starts, its last letter on the hot
# end. Half way up reads as the ramp's warm half, not all of it.
STYLE_MENU_LOGO_START_FRACTION = 0.5

# Spaces each overview pulldown's open search box adds beyond the longest
# test name. All three boxes are this one width.
STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS = 2

# The page font, written as --page-font-family-: Monaco first, then whatever
# else the box has.
STYLE_PAGE_FONT_FAMILY = (
    'Monaco, Menlo, "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace'
)

# Design pixels one arrow key moves a focused pane splitter's pane edge by,
# five design ch.
STYLE_PANE_SPLITTER_KEY_STEP_PX = 36

# Spaces added to every table column beyond its widest cell.
STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS = 3

# Width of a table's function-name column, in characters.
STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS = 20

# The fewest characters a fill table's grow column without a fixed width
# keeps, so it never looks gone: one function name's worth.
STYLE_TABLE_GROW_COLUMN_NARROWEST_CHARS = 20

# Where a table cuts a long "defined at" path.
STYLE_TABLE_LOCATION_COLUMN_MAX_CHARS = 48

# Every other value a stylesheet draws with, written as the CSS variable
# --<name>: <value>. Zero, none and hidden stay in the stylesheet itself.
STYLE_VALUE_ENTRIES: dict[str, str] = {
    "callers-collapsed-section-file-name-max-width-": "96ch",
    "callers-collapsed-section-log-box-max-height-share-": "0.6",
    "heat-map-band-z-index-": "2",
    "heat-map-menu-column-gap-": "1ch",
    "heat-map-menu-search-box-width-": "36ch",
    "heat-map-minimap-width-": "110px",
    "heat-map-source-file-header-column-gap-": "2ch",
    "heat-map-source-table-code-cell-tab-size-": "4",
    "heat-map-source-table-line-number-cell-callee-marker-text-": '"\\25B8 "',
    "heat-map-source-ticker-tape-entry-padding-inline-": "1ch",
    "heat-map-source-ticker-tape-gap-": "1ch",
    "heat-map-tree-node-caret-width-": "2ch",
    "heat-map-tree-node-gap-": "1ch",
    "heat-map-tree-node-share-percent-width-": "7ch",
    "heat-map-tree-resize-handle-margin-left-": "-3px",
    "heat-map-tree-resize-handle-margin-right-": "-4px",
    "heat-map-tree-resize-handle-width-": "7px",
    "heat-map-tree-resize-handle-z-index-": "1",
    "heat-map-tree-width-": "280px",
    "menu-button-margin-left-": "1ch",
    "menu-button-padding-inline-": "1ch",
    "menu-logo-padding-inline-": "1ch",
    "menu-pulldown-entry-list-max-height-share-": "0.6",
    "menu-pulldown-entry-list-z-index-": "3",
    "menu-pulldown-entry-padding-inline-": "1ch",
    "menu-pulldown-search-box-min-width-": "13ch",
    "menu-title-width-": "66ch",
    "page-body-line-height-": "1.1",
    "page-scrollbar-thickness-": "14px",
    "page-table-cell-padding-inline-": "1ch",
    "page-table-column-title-z-index-": "1",
    "screenshot-label-border-width-": "1ch",
    "screenshot-label-font-size-": "2em",
    "screenshot-label-z-index-": "3",
}

# Design pixels a press on a table cell travels before it slides that column
# and every one right of it. A press that stays within is a plain click.
TABLE_COLUMN_SLIDE_THRESHOLD_PX = 5

# The units a printed duration uses, largest first, as suffix and seconds.
# The printing ladder, not CALLERS_TIME_SUFFIX_SECONDS, which reads a log.
THEME_TIME_UNIT_ENTRIES: tuple[tuple[str, float], ...] = (
    ("s", 1.0),
    ("ms", 1e-3),
    ("us", 1e-6),
    ("ns", 1e-9),
    ("ps", 1e-12),
)

# The keys a focused tree, table row, pane splitter, ticker tape, line detail
# or link answers, as KeyboardEvent.key names, click the key a link lacks.
WIDGET_KEY_NAMES: dict[str, str] = {
    "activate": "Enter",
    "click": " ",
    "close": "Escape",
    "down": "ArrowDown",
    "first": "Home",
    "last": "End",
    "left": "ArrowLeft",
    "right": "ArrowRight",
    "up": "ArrowUp",
}


# The whole list of settings, taken at the line between them and the
# reader's own constants, after the shell's are bound and before any of those.
_SETTING_NAMES: frozenset[str] = frozenset()


# Whether a module-level name is spelled the way a setting is: SCREAMING
# snake case, with the leading underscore a private one keeps.
def _is_setting_name(name: str) -> bool:
    bare = name.lstrip("_")
    return bool(bare) and bare[0].isupper() and bare.isupper()


# manifest_table's spaces between the label column and the value.
_MANIFEST_TABLE_COLUMN_GAP_CHARS = 2

# The scalar types the type check tests exactly. bool sits before int, being
# an int subclass, so an int annotation must not accept True.
_SCALAR_TYPES = (bool, int, float, str)

# The types a declaration's sentinel may be written as, accepted only while
# empty: False, "", 0, 0.0, (), [], {}. Matched by exact type, not isinstance.
_SENTINEL_EMPTY_TYPES = (
    bool,
    bytes,
    dict,
    float,
    frozenset,
    int,
    list,
    set,
    str,
    tuple,
)

# How the accepted sentinels are spelled, so every message naming them says
# one list. None and Ellipsis are not on it.
_SENTINEL_TEXT = 'False, 0, 0.0, "", (), [], {}'

# The scripts/ directory, which is where this file, settings.sh and the
# handler template all sit.
_SETTINGS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# What settings_script_write() substitutes in the handler template. Both are
# bare identifiers there, so node --check parses it before anything fills in.
_SETTINGS_PAGE_DATA_MARKER = "__DATA__"
_SETTINGS_PAGE_NAME_MARKER = "__NAME__"

# The one scalar spelling settings.sh turns into an int rather than a str.
_SHELL_INTEGER_PATTERN = re.compile(r"-?[0-9]+")

# The [key]= in front of each element of a declare -A map. A key holding a
# "-" is written quoted, which is what shfmt leaves alone.
_SHELL_MAP_KEY_PATTERN = re.compile(r"\[\"?([A-Za-z0-9_.+-]+)\"?\]=")

# The shell's settings file, beside this one.
_SHELL_SETTINGS_FILE_NAME = "settings.sh"

# One settings.sh statement: an optional declare -A, the name, then what
# follows the "=", which is a scalar word or the "(" opening a container.
_SHELL_STATEMENT_PATTERN = re.compile(
    r"(declare -A )?([A-Za-z_][A-Za-z0-9_]*)=(.*)"
)

# One settings.sh word: single-quoted, double-quoted, or bare to the
# whitespace or ")". What it may hold is bash's question, not this reader's.
_SHELL_WORD_PATTERN = re.compile(r"'([^']*)'|\"([^\"]*)\"|([^\s)]+)")


# SettingsReader - the reader for the annotated settings a module declares.
class SettingsReader:
    # Whether one initializer is an empty sentinel of a type the annotation
    # could name. A fixed-length tuple counts when every element is one.
    def is_sentinel(self, written: object) -> bool:
        if type(written) not in _SENTINEL_EMPTY_TYPES:
            return False
        if not written:
            return True
        return type(written) is tuple and all(
            self.is_sentinel(item) for item in written
        )

    # An annotation is the whole request: which setting and what type. Every
    # SCREAMING_SNAKE name bound above this call is one being asked for.
    def load_into(self, module_name: str) -> None:
        module = sys.modules[module_name]
        scope = vars(module)
        wanted = get_type_hints(module)
        for name in sorted(scope):
            if not _is_setting_name(name):
                continue
            expected = wanted.get(name)
            self.match_check(module_name, name)
            self.sentinel_check(module_name, name, scope[name], expected)
            value = self.value_of(name)
            self.type_check(module_name, name, value, expected)
            setattr(module, name, value)

    # The first check: a name bound above the call must be a setting this
    # file holds. A file's own constant written above lands here too.
    def match_check(self, module_name: str, name: str) -> None:
        setting = name.lstrip("_")
        if setting in _SETTING_NAMES:
            return
        raise NameError(
            f"error: constant doesn't match any setting: "
            f"{module_name}.{name} asks for the setting {setting}, which "
            "neither settings.py nor settings.sh defines. Define it in one "
            "of them, correct the spelling here, or -- if this is the "
            "file's own constant -- move it below the load_into() call."
        )

    # The second check: a declaration is written with an empty sentinel of
    # its own type. Anything else is a value meant to be read, and is lost.
    def sentinel_check(
        self,
        module_name: str,
        name: str,
        written: object,
        expected: object,
    ) -> None:
        if expected is None:
            raise NameError(
                f"error: settings must have sentinels "
                f"{_SENTINEL_TEXT}: {module_name}.{name} is assigned with "
                "no annotation, so it declares no type. Write it as an "
                "annotation naming the type plus an empty sentinel of that "
                "type."
            )
        if self.is_sentinel(written):
            return
        raise TypeError(
            f"error: settings must have sentinels {_SENTINEL_TEXT}: "
            f"{module_name}.{name} is written with {written!r}. The value "
            "comes from settings.py and overwrites whatever is here, so a "
            "declaration carries an empty sentinel of its own type and "
            "nothing else."
        )

    # A settings.sh name is spelled like every other setting and bound
    # nowhere else: a second definition is the twin this reader exists to end.
    def shell_name_check(
        self, number: int, name: str, found: dict[str, object]
    ) -> None:
        if not _is_setting_name(name):
            self.shell_settings_fail(
                number, f"{name} is not a setting name (SCREAMING_SNAKE)"
            )
        if name in found:
            self.shell_settings_fail(
                number, f"{name} is assigned twice; keep one of them"
            )
        if name in globals():
            self.shell_settings_fail(
                number,
                f"{name} is also defined in settings.py; a setting has one "
                "definition, in one of the two files",
            )

    # One scalar: exactly one word, an int when it matches -?[0-9]+.
    def shell_scalar_parse(self, number: int, text: str) -> int | str:
        pairs, closed = self.shell_words_parse(number, text, False)
        if closed or len(pairs) != 1:
            self.shell_settings_fail(
                number, "a scalar is exactly one bare or quoted word"
            )
        value = pairs[0][1]
        if _SHELL_INTEGER_PATTERN.fullmatch(value):
            return int(value)
        return value

    # Stop the import on one settings.sh line, naming it and the fix.
    def shell_settings_fail(self, number: int, problem: str) -> NoReturn:
        raise SystemExit(
            f"error: {_SHELL_SETTINGS_FILE_NAME} line {number}: {problem}"
        )

    # Every setting settings.sh holds, by name. Only what shell and Python
    # read alike is accepted; the grammar is settings.sh's own header.
    def shell_settings_read(self) -> dict[str, object]:
        path = os.path.join(_SETTINGS_DIRECTORY, _SHELL_SETTINGS_FILE_NAME)
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        found: dict[str, object] = {}
        opened: tuple[str, int, bool, list[tuple[str, str]]] | None = None
        for number, line in enumerate(lines, 1):
            text = line.strip()
            if not text or text.startswith("#"):
                continue
            if opened is None:
                statement = _SHELL_STATEMENT_PATTERN.fullmatch(text)
                if statement is None:
                    self.shell_settings_fail(
                        number,
                        "expected NAME=word, NAME=(...) or "
                        "declare -A NAME=(...)",
                    )
                keyed = statement.group(1) is not None
                name = statement.group(2)
                text = statement.group(3)
                self.shell_name_check(number, name, found)
                if not text.startswith("("):
                    if keyed:
                        self.shell_settings_fail(
                            number, "declare -A NAME takes =([key]=word ...)"
                        )
                    found[name] = self.shell_scalar_parse(number, text)
                    continue
                opened = (name, number, keyed, [])
                text = text[1:]
            name, start, keyed, pairs = opened
            more, closed = self.shell_words_parse(number, text, keyed)
            pairs.extend(more)
            if closed:
                if keyed:
                    found[name] = dict(pairs)
                else:
                    found[name] = tuple(value for _, value in pairs)
                opened = None
        if opened is not None:
            self.shell_settings_fail(
                opened[1], f'{opened[0]}=( is never closed by ")"'
            )
        return found

    # One line of a container body as (key, word) pairs, the key empty in a
    # list, and whether it closed. 'a'b is refused at the end, never joined.
    def shell_words_parse(
        self, number: int, text: str, keyed: bool
    ) -> tuple[list[tuple[str, str]], bool]:
        pairs: list[tuple[str, str]] = []
        position = 0
        while True:
            while position < len(text) and text[position].isspace():
                position += 1
            if position == len(text):
                return pairs, False
            if text[position] == ")":
                if text[position + 1 :].strip():
                    self.shell_settings_fail(
                        number, 'nothing may follow the closing ")"'
                    )
                return pairs, True
            key = ""
            if keyed:
                keyed_match = _SHELL_MAP_KEY_PATTERN.match(text, position)
                if keyed_match is None:
                    self.shell_settings_fail(number, "expected [key]=word")
                key = keyed_match.group(1)
                position = keyed_match.end()
            word_match = _SHELL_WORD_PATTERN.match(text, position)
            if word_match is None:
                self.shell_settings_fail(
                    number,
                    "expected a bare word, 'single-quoted' or "
                    '"double-quoted"',
                )
            position = word_match.end()
            if position < len(text) and text[position] not in " \t)":
                self.shell_settings_fail(
                    number, 'a word ends at whitespace or the closing ")"'
                )
            # Whichever of the three quoting forms matched holds the word.
            word = next(
                group for group in word_match.groups() if group is not None
            )
            pairs.append((key, word))

    # The third check: the value must be the type the annotation names.
    # Scalars exactly, never converted; a container is not walked.
    def type_check(
        self, module_name: str, name: str, value: object, expected: object
    ) -> None:
        wanted = get_origin(expected) or expected
        if not isinstance(wanted, type):
            return
        found = type(value)
        exact = wanted in _SCALAR_TYPES or found in _SCALAR_TYPES
        if found is wanted or (not exact and isinstance(value, wanted)):
            return
        raise TypeError(
            f"error: settings must not be coerced to another type: "
            f"{module_name}.{name} is annotated "
            f"{getattr(wanted, '__name__', wanted)}, but the setting is "
            f"{found.__name__}. Correct the annotation, or change the value "
            "in settings.py."
        )

    # The value of one setting, named as the declaring module spells it.
    # match_check has already confirmed this file defines it.
    def value_of(self, name: str) -> object:
        return globals()[name.lstrip("_")]


# SettingsWriter - the page text this module emits: the frozen settings
# script, and the manifest table string report_complete.js carries.
class SettingsWriter:
    # Every setting this module exports, by name.
    def all_named(self) -> dict[str, object]:
        scope = globals()
        return {name: scope[name] for name in sorted(_SETTING_NAMES)}

    # The manifest as plain lines, the version under an empty label, then
    # each row split at its first "=", labels padded to one column. No wrap.
    def manifest_table(self, lines: Sequence[str]) -> str:
        rows = [("", "", lines[0])]
        rows += [line.partition("=") for line in lines[1:]]
        label_width = max(len(label) for label, _, _ in rows)
        column_gap = " " * _MANIFEST_TABLE_COLUMN_GAP_CHARS
        return "\n".join(
            f"{label.ljust(label_width)}{column_gap}{value}"
            for label, _, value in rows
        )

    # Build assets/settings.js: every setting as one frozen JSON literal,
    # wholesale, with no list of what a page may see.
    def script_write(self) -> str:
        # Plain open(), never theme.asset_text_read(): theme.py imports this
        # module, so reaching for theme here would cycle.
        values = self.all_named()
        data = json.dumps(values, indent=2, sort_keys=True, ensure_ascii=False)
        path = os.path.join(
            _SETTINGS_DIRECTORY, ASSET_TEMPLATE_SETTINGS_HANDLER_NAME
        )
        with open(path, encoding="utf-8") as handle:
            runtime = handle.read()
        return runtime.replace(
            _SETTINGS_PAGE_NAME_MARKER, PAGE_SETTINGS_GLOBAL_NAME
        ).replace(_SETTINGS_PAGE_DATA_MARKER, data)


# The reader, then the cut: the shell's settings bind first, so every one
# is bound before the list is taken. The writer reads the finished list.
_reader = SettingsReader()
globals().update(_reader.shell_settings_read())
_SETTING_NAMES = frozenset(
    name
    for name in globals()
    if not name.startswith("_") and _is_setting_name(name)
)
_writer = SettingsWriter()


# Assign a module's declared settings into it, checking each one's type
# against the annotation the module declared it with.
def load_into(module_name: str) -> None:
    _reader.load_into(module_name)


# The manifest as plain label and value lines, for report_complete.js.
def manifest_table(lines: Sequence[str]) -> str:
    return _writer.manifest_table(lines)


# Build assets/settings.js: every setting this module holds, shipped to
# the browser as one frozen object.
def settings_script_write() -> str:
    return _writer.script_write()
