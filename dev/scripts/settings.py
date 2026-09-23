from __future__ import annotations

import json, os, re, sys, time
from typing import NoReturn, get_origin, get_type_hints

# What the report's one shared copy of the theme is written as. Every page
# in a report renders the same stylesheet and the same script, so they are
# written once at the report root and linked, not inlined 19 times. The heat
# map's own stylesheet and runtime, and the frame script every summary and
# overview page runs, are the same on all of them too, so they are shared
# the same way. Each page links only the ones it uses. theme.css and the
# settings file are generated rather than copied. This list runs on past
# the template names below it, which sort into the middle of it.
ASSET_ERROR_OVERLAY_SCRIPT_NAME = "error_overlay.js"
ASSET_FRAME_SCRIPT_NAME = "frame.js"
ASSET_HEAT_MAP_SCRIPT_NAME = "heatmap.js"
ASSET_HEAT_MAP_STYLESHEET_NAME = "heatmap.css"
ASSET_SETTINGS_SCRIPT_NAME = "settings.js"

# The four scripts/ files a generator reads as a template rather than
# copying, interleaved here by name among the shared assets above. Each
# holds the markers that generator substitutes its own content into, and
# nothing writes them into a report under these names, so they are read
# but never shared. No generator holds a multi-line literal, which is why
# each of these is a real file. The settings handler is this file's own
# template, so settings_script_write() reads it the way a generator reads
# the other three.
ASSET_TEMPLATE_FLAME_GRAPH_BOOTSTRAP_NAME = "flame_bootstrap.js"
ASSET_TEMPLATE_FLAME_GRAPH_PAGE_NAME = "flame_graph.html"
ASSET_TEMPLATE_HEAT_MAP_PAGE_NAME = "heatmap.html"
ASSET_TEMPLATE_SETTINGS_HANDLER_NAME = "settings_handler.js"

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

# A share at or past this is already fully lit, so the handful of diff lines
# reading millions of percent cannot flatten the scale.
HEAT_COLOR_FULL_SCALE_PERCENT = 100

# Heat above which a cell's text switches to the light-on-dark class, so the
# text stays readable once the cell behind it is bright.
HEAT_COLOR_LIGHT_TEXT_ABOVE_SHARE = 0.45

# The 12-stop heat ramp, cold to hot. Exempt from the light/dark pair rule.
# Every heated cell carries one of these opaque, interpolated between the two
# it sits between and never faded, and the outer strip's wordmark steps its
# letters across the ramp's upper half as plain text colour, so a retune
# moves both.
HEAT_COLOR_LOGO_STOPS: list[str] = [
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
# denominator. theme.py renders the number server-side and heatmap.js
# renders it on the page, so both read this one value and the two
# spellings of the notation cannot drift apart.
NUMBER_SMALLEST_PRINTED_PERCENT = 0.01

# The page font: Monaco first, then whatever else the box has.
PAGE_FONT_FAMILY = (
    'Monaco, Menlo, "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace'
)

# The global the generated settings file assigns its one statement to. A page
# links that file before every script that reads it, the way it links
# ui_strings.js. settings_script_write() fills the handler template's name
# marker with this, so the page calls what is spelled here.
PAGE_SETTINGS_GLOBAL_NAME = "settings"

# The one counter every generator ranks, colours and divides by, recorded or
# derived. Point it at any counter callgrind.py knows and every page follows.
RANKING_COUNTER_NAME = "CEst"

# The report-root directory holding every heat map's source text, one copy
# of each profiled file rather than one per page that references it.
REPORT_SOURCES_DIR_NAME = "sources"

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
# whole page follows --bg: the scrollbar track and the minimap band, so this
# is the one number that moves them together. A heated cell does not -- it
# carries its ramp stop opaque.
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

# Every setting the report's JavaScript reads, by name. The value itself is
# the module-level setting above, so a value the page and Python both use is
# written once and this list only says who else can see it. A page reads a
# name off the frozen object this list builds. Python reads the same name
# through load_into().
_BROWSER_SETTING_NAMES = (
    "HEAT_COLOR_FULL_SCALE_PERCENT",
    "HEAT_COLOR_LIGHT_TEXT_ABOVE_SHARE",
    "HEAT_COLOR_LOGO_STOPS",
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
    "HEAT_MAP_TREE_INDENT_FIRST_LEVEL_PX",
    "HEAT_MAP_TREE_INDENT_PER_LEVEL_PX",
    "HEAT_MAP_TREE_PANE_NARROWEST_PX",
    "LAYOUT_RESET_RATE_LIMIT_CLICKS",
    "LAYOUT_RESET_RATE_LIMIT_WINDOW_MS",
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

# The types a declaration's sentinel may be written as, each accepted only
# while it is empty: "", 0, 0.0, (), [], {}. bool is left out -- False is
# an int to Python, and no declaration has wanted one. set() and frozenset()
# are here so a set-typed setting has a sentinel to be declared with.
_SENTINEL_EMPTY_TYPES = (
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

# The sentinels that are not empty containers but are still empty values,
# compared by identity because neither has a falsy test of its own.
_SENTINEL_SINGLETONS = (None, ...)

# How the accepted sentinels are spelled back in every message naming them,
# so the three errors and DECLAUDE.md say the same list.
_SENTINEL_TEXT = 'false, 0, 0.0, ""...'

# The one scalar spelling settings.sh turns into an int rather than a str.
_SHELL_INTEGER_PATTERN = re.compile(r"-?[0-9]+")

# The [key]= in front of each element of a declare -A map.
_SHELL_MAP_KEY_PATTERN = re.compile(r"\[([A-Za-z0-9_.+-]+)\]=")

# The shell's settings file, beside this one. Every name it assigns is
# bound into this module by shell_settings_read(), so a setting the shell
# reads is a setting like any other here, under the same spelling.
_SHELL_SETTINGS_FILE_NAME = "settings.sh"

# One settings.sh statement: an optional declare -A, the name, then what
# follows the "=", which is a scalar word or the "(" opening a container.
_SHELL_STATEMENT_PATTERN = re.compile(
    r"(declare -A )?([A-Za-z_][A-Za-z0-9_]*)=(.*)"
)

# One settings.sh word: single-quoted, double-quoted, or bare up to the
# whitespace or ")" that ends it. What a word may hold is bash's question,
# not this reader's -- every script sources the file before anything parses
# it, so bash has already refused whatever it would refuse.
_SHELL_WORD_PATTERN = re.compile(r"'([^']*)'|\"([^\"]*)\"|([^\s)]+)")

# What makes a word one bash would expand rather than read literally.
_SHELL_EXPANSION_MARKS = ("$", "`")

# Each such word this file answers for itself, spelled exactly as
# settings.sh writes it, and what Python computes to match bash. Seconds
# since the epoch is the one so far: a plain unix integer either language
# reads the same way.
_SHELL_EXPANSION_VALUES = {
    "$(date +%s)": lambda: str(int(time.time())),
}


# Settings - the reader for the annotated settings a module declares.
class Settings:
    # Every setting this module exports, by name.
    def all_named(self) -> dict[str, object]:
        return {
            name: value
            for name, value in globals().items()
            if self.is_setting_name(name)
        }

    # Whether one written initializer is an empty sentinel. A fixed-length
    # tuple annotation has no empty form -- tuple[str, str, str] cannot be
    # written () without pyright rejecting it -- so a tuple is also a
    # sentinel when every element it holds is one.
    def is_sentinel(self, written: object) -> bool:
        if any(written is one for one in _SENTINEL_SINGLETONS):
            return True
        if type(written) not in _SENTINEL_EMPTY_TYPES:
            return False
        if not written:
            return True
        return type(written) is tuple and all(
            self.is_sentinel(item) for item in written
        )

    # Whether a module-level name is spelled the way a setting is: SCREAMING
    # snake case, with the leading underscore a private one keeps.
    def is_setting_name(self, name: str) -> bool:
        bare = name.lstrip("_")
        return bool(bare) and bare[0].isupper() and bare.isupper()

    # An annotation is the whole request: which setting, and the type
    # expected. Its initializer is a sentinel of that type and is always
    # overwritten here, so nothing reads one. Every SCREAMING_SNAKE name the
    # module has bound above this call is a setting it is asking for, and
    # the three checks run in the order a mistake is best explained in:
    # does the name match a setting at all, was it written with a sentinel,
    # does its type agree. The namespace is ours until this returns.
    def load_into(self, module_name: str) -> None:
        module = sys.modules[module_name]
        scope = vars(module)
        wanted = get_type_hints(module)
        for name in sorted(scope):
            if not self.is_setting_name(name):
                continue
            expected = wanted.get(name)
            self.match_check(module_name, name)
            self.sentinel_check(module_name, name, scope[name], expected)
            value = self.value_of(name)
            self.type_check(module_name, name, value, expected)
            setattr(module, name, value)

    # The first check: a SCREAMING_SNAKE name bound above the call is a
    # setting being asked for, so settings.py has to have one by that name.
    # A file's own constant written above the call lands here, because it
    # matches nothing, and so does a misspelled or undefined setting.
    def match_check(self, module_name: str, name: str) -> None:
        setting = name.lstrip("_")
        if setting in globals() and self.is_setting_name(setting):
            return
        raise NameError(
            f"error: constant doesn't match any setting: "
            f"{module_name}.{name} asks for the setting {setting}, which "
            "neither settings.py nor settings.sh defines. Define it in one "
            "of them, correct the spelling here, or -- if this is the "
            "file's own constant -- move it below the load_into() call."
        )

    # The second check: the name matches a setting, so it is a declaration,
    # and a declaration is written with an empty sentinel of its own type.
    # Anything else is a value someone meant to be read, and load_into()
    # overwrites every one of them.
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

    # A settings.sh name is spelled like every other setting and is bound
    # nowhere else: not twice there, and not in this module, where a second
    # definition would be the hand-matched twin this reader exists to end.
    def shell_name_check(
        self, number: int, name: str, found: dict[str, object]
    ) -> None:
        if not self.is_setting_name(name):
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

    # The value bash would give one word. A word holding no $ or backtick
    # is already that value; one that does is looked up in the handful this
    # file knows how to answer for itself, spelled the way settings.sh
    # writes it. Nothing is run here -- the shell is what sources the file.
    #
    # DO NOT USE IN PYTHON. This is computed at import, the shell's at
    # source, so TIMESTAMP can land a second off the run's real stamp.
    # It exists to keep the parser whole, not to be read: the stamp a
    # generator uses arrives as the shell's stamp= manifest row. Reading
    # settings.TIMESTAMP would silently name a different run.
    def shell_word_expand(self, number: int, word: str) -> str:
        if not any(mark in word for mark in _SHELL_EXPANSION_MARKS):
            return word
        if word not in _SHELL_EXPANSION_VALUES:
            self.shell_settings_fail(
                number,
                f"{word} is not one settings.py can expand; add it to "
                "_SHELL_EXPANSION_VALUES, or write a literal word",
            )
        return _SHELL_EXPANSION_VALUES[word]()

    # Stop the import on one settings.sh line, naming it and the fix.
    def shell_settings_fail(self, number: int, problem: str) -> NoReturn:
        raise SystemExit(
            f"error: {_SHELL_SETTINGS_FILE_NAME} line {number}: {problem}"
        )

    # Every setting settings.sh holds, by name. The file is sourced by the
    # shell and parsed here, so only what both read the same way is
    # accepted, and anything else stops the import naming its line: blank
    # and # comment lines; NAME=word; NAME=(word ...) and declare -A
    # NAME=([key]=word ...), each over one or more lines up to the closing
    # ")", giving tuple[str, ...] and dict[str, str]. A word is bare,
    # single-quoted or double-quoted, and its contents are bash's business:
    # every script sources the file before this runs. A scalar matching
    # -?[0-9]+ is an int, every other scalar a str, and elements stay str.
    # A name is a setting name and is bound in neither file already.
    def shell_settings_read(self) -> dict[str, object]:
        path = os.path.join(_DIRECTORY, _SHELL_SETTINGS_FILE_NAME)
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

    # One line of a container body as (key, word) pairs -- the key is empty
    # in a list -- and whether the line closed the container. A word ends
    # at whitespace or the closing ")", so 'a'b is refused, never joined.
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
            # Group 1 is the 'single-quoted' form, which bash reads
            # literally, so a $ inside one is text and never expanded.
            word = next(
                group for group in word_match.groups() if group is not None
            )
            if word_match.group(1) is None:
                word = self.shell_word_expand(number, word)
            pairs.append((key, word))

    # The third check: the value settings.py holds has to be the type the
    # annotation names. Scalars exactly, never converted. A container is
    # checked to the container, not walked.
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
    # match_check has already confirmed settings.py defines it.
    def value_of(self, name: str) -> object:
        return globals()[name.lstrip("_")]


# The scripts/ directory this module was loaded from, which is also where
# the handler template and settings.sh sit.
_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# What settings_script_write() substitutes in the handler template: the
# JSON literal of every setting the browser reads, and the name the page
# calls the reader by. Both are bare identifiers in the template, so
# node --check parses the file before anything is filled in.
_PAGE_SETTINGS_DATA_MARKER = "__DATA__"
_PAGE_SETTINGS_NAME_MARKER = "__NAME__"

_READER = Settings()

# Every setting settings.sh holds, bound here under its own name: the
# shell's settings are settings of this module like any other, so
# load_into() resolves them and validate_report.py reads them the same way.
globals().update(_READER.shell_settings_read())


# Assign a module's declared settings into it, checking each one's type
# against the annotation the module declared it with.
def load_into(module_name: str) -> None:
    _READER.load_into(module_name)


# Build assets/settings.js: the browser's settings as one frozen JSON
# literal in settings_handler.js, opened here -- theme.py would cycle.
def settings_script_write() -> str:
    values = {name: globals()[name] for name in _BROWSER_SETTING_NAMES}
    data = json.dumps(values, indent=2, sort_keys=True, ensure_ascii=False)
    with open(
        os.path.join(_DIRECTORY, ASSET_TEMPLATE_SETTINGS_HANDLER_NAME),
        encoding="utf-8",
    ) as handle:
        runtime = handle.read()
    return runtime.replace(
        _PAGE_SETTINGS_NAME_MARKER, PAGE_SETTINGS_GLOBAL_NAME
    ).replace(_PAGE_SETTINGS_DATA_MARKER, data)
