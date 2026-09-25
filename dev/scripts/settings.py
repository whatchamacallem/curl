from __future__ import annotations

import json, os, re, sys
from typing import NoReturn, get_origin, get_type_hints

# Every setting the tools have, then the reader that checks and assigns
# them. _SETTING_NAMES is the line between the two. See DECLAUDE.md 6.1.

# What the report's one shared copy of the theme is written as: written once
# at the report root and linked, never inlined. Each page links what it uses.
ASSET_ERROR_OVERLAY_SCRIPT_NAME = "error_overlay.js"
ASSET_FRAME_SCRIPT_NAME = "frame.js"
ASSET_HEAT_MAP_SCRIPT_NAME = "heatmap.js"
ASSET_HEAT_MAP_STYLESHEET_NAME = "heatmap.css"
ASSET_SETTINGS_SCRIPT_NAME = "settings.js"

# The four scripts/ files a generator reads as a template, each holding the
# markers it substitutes into. Read but never shared into a report.
ASSET_TEMPLATE_FLAME_GRAPH_BOOTSTRAP_NAME = "flame_bootstrap.js"
ASSET_TEMPLATE_FLAME_GRAPH_PAGE_NAME = "flame_graph.html"
ASSET_TEMPLATE_HEAT_MAP_PAGE_NAME = "heatmap.html"
ASSET_TEMPLATE_SETTINGS_HANDLER_NAME = "settings_handler.js"

ASSET_THEME_SCRIPT_NAME = "theme.js"
ASSET_THEME_STYLESHEET_NAME = "theme.css"
ASSET_UI_STRINGS_SCRIPT_NAME = "ui_strings.js"

# The character table layout: each <col> is a CSS clamp() on its container's
# 100cqw, automatic table layout in CSS. False keeps the pixel-fitted layout.
CSS_LAYOUT = True

# Every counter callgrind never records, as the recorded ones it sums from
# and each one's coefficient. Nothing stores one. See DECLAUDE.md 6.2.
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

# The width of the coordinate space every page is designed in: every length
# is written for this box, which report_ui.design_scale_apply() then fits.
DESIGN_COORDINATES_WIDTH_PX = 1920

# The design font, Monaco at this size, is this many px per ch. theme.js's
# font_fit_apply() scales the box's own font to it: a ch is the design ch.
DESIGN_FONT_CHARACTER_WIDTH_PX = 7.2
DESIGN_FONT_SIZE_PX = 12

# The CSS variable carrying the font fit, a multiplier on every font size
# the theme sets: 1 is the design font itself. Boundary.
DESIGN_FONT_FIT_PROPERTY = "--font-fit"

# What the scale slider multiplies the window's own fit by: on an untouched
# page (mid-travel whatever the ends, each half geometric), then at each end.
DESIGN_SCALE_DEFAULT_MULTIPLE = 1
DESIGN_SCALE_LARGEST_MULTIPLE = 2
DESIGN_SCALE_SMALLEST_MULTIPLE = 0.5

# Where along the slider's 0..1 travel the default multiple sits: the
# middle, so the knob starts centred whatever the two ends are.
DESIGN_SCALE_DEFAULT_TRAVEL_SHARE = 0.5

# The CSS variable carrying the window's height in design pixels. A vh is
# zoomed like any length, so a full-height rule reads this instead. Boundary.
DESIGN_VIEWPORT_HEIGHT_PROPERTY = "--design-vh"

# What callgrind_diff.py's synthesized callers diff is named, beside the
# delta. Written by perf2html_diff.sh, read back by build_report.py.
DIFF_CALLER_COUNTS_FILE_SUFFIX = ".callers.json"

# Only a flame graph our own tool exported counts -- a stale or hand-made
# one must fail.
FLAME_GRAPH_EXPORTER_NAME = "dev/scripts/trace_to_speedscope.py"

# The most complete calls one trace keeps, cut at the top of the current
# TESTS_C's 79-202 range. Retune if a test's shape changes.
FLAME_GRAPH_MAX_RECORDED_CALLS = 200

# All a per-test flame graph directory may hold: its page, its profile, the
# trace log. Everything else is the shared bundle at the report root.
FLAME_GRAPH_PAGE_FILE_NAMES = ("index.html", "output.txt", "profile.js")

# What the bootstrap plus its embedded profile gets written as.
FLAME_GRAPH_PROFILE_SCRIPT_NAME = "profile.js"

# How the flame graph page polls for speedscope, which defines its global
# only once its script ran. The two multiply into the failure's seconds.
FLAME_GRAPH_STARTUP_POLL_DELAY_MS = 50
FLAME_GRAPH_STARTUP_POLL_MAX_ATTEMPTS = 200

# The flame graph view a summary page links, as key, link label, page path.
# Linked only where a trace was recorded. The key is a boundary name.
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

# The 12-stop heat ramp, cold to hot, exempt from the light/dark pair rule.
# Carried opaque by a cell, stepped across by the wordmark: a retune hits both.
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

# The shortest file that gets a minimap at all. A file under this many lines
# fits on screen, so a scaled-down copy of it beside the source adds nothing.
HEAT_MAP_MINIMAP_SHOWN_ABOVE_FILE_LINES = 40

# The minimap's fixed column scale, the same 80 the source view uses. It is
# never widened to the file's longest line.
HEAT_MAP_MINIMAP_SOURCE_WIDTH_CHARS = 80

# Smallest the minimap's viewport box may be drawn, in pixels, so the box
# marking what is on screen stays visible in a very long file.
HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX = 8

# The counters the heat map shows beside the selected one, in column order.
# One the run cannot supply is left out, so naming an unrecorded one is free.
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
# Every test has one. Spelled the same way as FLAME_GRAPH_VIEW_ENTRY.
HEAT_MAP_VIEW_ENTRY: tuple[str, str, str] = (
    "heat-map",
    "heat map",
    "heat-map/index.html",
)

# Milliseconds a window resize settles for before the page re-measures: a
# drag fires resize continuously, and every frame is what this avoids.
LAYOUT_RESIZE_SETTLE_DELAY_MS = 120

# The multiple a rise stops printing at, becoming the ">1000x" bound. A drop
# cannot pass -100%, so only a rise reaches it. theme.py and theme.js read it.
NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES = 999.99

# The smallest percentage a table prints as a number, under which it states
# a bound. A notation floor only: no colour, no filter, never a denominator.
NUMBER_SMALLEST_PRINTED_PERCENT = 0.01

# The page font: Monaco first, then whatever else the box has.
PAGE_FONT_FAMILY = (
    'Monaco, Menlo, "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace'
)

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
    "heat.scale",
    "heat.sort",
    "view.scale",
)
STORAGE_OWNED_PREFIXES: tuple[str, ...] = ("split.",)

# What a report writes under STORAGE_VERSION_KEY, a bare string, not JSON.
# Anything but exactly it sweeps every owned key: that is how a bump rolls out.
STORAGE_VERSION = "perf2html v2"
STORAGE_VERSION_KEY = "perf2html.version"

# The "curl.se/perf" link in every page's util block.
STRIP_CURL_PERF_SITE_HREF = "https://curl.se/perf/index.html"

# Width of a strip's status row, its first cell: the longest "<test> /
# <label>" is 26 today, plus margin. Too small clips mid-word.
STRIP_STATUS_ROW_WIDTH_CHARS = 33

# Spaces the overview's test menu box adds beyond its longest test name,
# shared either side of the centered name.
STRIP_TEST_MENU_EXTRA_WIDTH_CHARS = 2

# The keys the open test menu answers, and a framed summary forwards up to
# it, as KeyboardEvent.key names. "next" also opens a closed, focused menu.
STRIP_TEST_MENU_KEY_NAMES: dict[str, str] = {
    "close": "Escape",
    "next": "ArrowDown",
    "previous": "ArrowUp",
    "select": "Enter",
}

# The test merging every other, named as perf2html.sh names its directory.
# The test menu reads it while the overview shows: data, not a UI word.
STRIP_TEST_MENU_MERGED_TEST_NAME = "all"

# Printable keys that, typed outside a field, stay with the page instead of
# opening the test menu: space scrolls it.
STRIP_TEST_MENU_SKIPPED_KEY_NAMES: tuple[str, ...] = (" ",)

# Where on the heat ramp the wordmark starts, its last letter always on the
# hot end. Half way up reads as the ramp's warm half, not the whole of it.
STRIP_WORDMARK_LOGO_START_FRACTION = 0.5

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

# Pixels no table column is dragged or filled narrower than when CSS_LAYOUT
# is False: a floor under the width each <col>'s data-min probes to.
TABLE_COLUMN_NARROWEST_DRAG_PX = 24

# Width of a table's function-name column, in characters.
TABLE_FUNCTION_NAME_WIDTH_CHARS = 20

# Under CSS_LAYOUT, the fewest characters a fill table's grow column without a
# fixed width keeps, so it never looks gone: one function name's worth.
TABLE_GROW_COLUMN_NARROWEST_CHARS = 20

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

# What the seven THEME_COLOR_PAIR_ENTRIES pairs are called, in their order.
# Each becomes --<name> and --<name>-l, so these are boundary names.
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
# one number moving --bg, scrollbar and minimap; a heated cell follows none.
THEME_COLOR_ROLE_BACKGROUND_SHADE_FACTOR = 0.90

# What each colour is for, as its CSS variable, then the pair and member
# ("light"/"dark") it comes from. "bg" alone is shaded. Boundary names.
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

# The units a printed duration uses, largest first, as suffix and seconds.
# The printing ladder, not SUMMARY_TIME_SUFFIX_SECONDS, which reads a log.
THEME_TIME_UNIT_ENTRIES: tuple[tuple[str, float], ...] = (
    ("s", 1.0),
    ("ms", 1e-3),
    ("us", 1e-6),
    ("ns", 1e-9),
    ("ps", 1e-12),
)


# The whole list of settings, taken at the line between them and the
# reader's own constants, after the shell's are bound and before any of those.
_SETTING_NAMES: frozenset[str] = frozenset()


# Whether a module-level name is spelled the way a setting is: SCREAMING
# snake case, with the leading underscore a private one keeps.
def _is_setting_name(name: str) -> bool:
    bare = name.lstrip("_")
    return bool(bare) and bare[0].isupper() and bare.isupper()


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

# How the accepted sentinels are spelled in every message naming them, so
# the errors and DECLAUDE.md say one list. None and Ellipsis are not on it.
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

# The [key]= in front of each element of a declare -A map.
_SHELL_MAP_KEY_PATTERN = re.compile(r"\[([A-Za-z0-9_.+-]+)\]=")

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
    # Every setting this module exports, by name.
    def all_named(self) -> dict[str, object]:
        scope = globals()
        return {name: scope[name] for name in sorted(_SETTING_NAMES)}

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

    # Build assets/settings.js: every setting as one frozen JSON literal in
    # settings_handler.js, wholesale, with no list of what a page may see.
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


# The reader, then the cut: the shell's settings bind first, so every one
# is bound before the list is taken. See DECLAUDE.md 6.1 for the spelling.
_reader = SettingsReader()
globals().update(_reader.shell_settings_read())
_SETTING_NAMES = frozenset(
    name
    for name in globals()
    if not name.startswith("_") and _is_setting_name(name)
)


# Assign a module's declared settings into it, checking each one's type
# against the annotation the module declared it with.
def load_into(module_name: str) -> None:
    _reader.load_into(module_name)


# Build assets/settings.js: every setting this module holds, shipped to the
# browser as one frozen object, with no list of which a page may see.
def settings_script_write() -> str:
    return _reader.script_write()
