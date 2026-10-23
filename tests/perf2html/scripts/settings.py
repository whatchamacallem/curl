# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import json, math, os, re, sys
from collections.abc import Sequence
from typing import NoReturn, get_origin, get_type_hints


ASSET_CALL_GRAPH_SCRIPT_NAME = "call_graph.js"
ASSET_DARK_MODE_STYLESHEET_NAME = "dark_mode.css"
ASSET_DATABASE_SCRIPT_NAME = "database.js"
ASSET_ERROR_OVERLAY_SCRIPT_NAME = "error_overlay.js"
ASSET_FLAME_GRAPH_SCRIPT_NAME = "flame_graph.js"
ASSET_FRAME_SCRIPT_NAME = "frame.js"
ASSET_HEAT_MAP_SCRIPT_NAME = "heat_map.js"
ASSET_HEAT_MAP_STYLESHEET_NAME = "heat_map.css"
ASSET_LIGHT_MODE_STYLESHEET_NAME = "light_mode.css"
ASSET_MENU_SCRIPT_NAME = "menu.js"
ASSET_OVERVIEW_SCRIPT_NAME = "overview.js"
ASSET_PREFERENCES_SCRIPT_NAME = "preferences.js"
ASSET_SETTINGS_PAGE_SCRIPT_NAME = "settings_page.js"
ASSET_SETTINGS_SCRIPT_NAME = "settings.js"
ASSET_SOURCE_DATABASE_SCRIPT_NAME = "source_database.js"
ASSET_TEMPLATE_CALL_GRAPH_PAGE_NAME = "call_graph.html"
ASSET_TEMPLATE_DATABASE_PAGE_NAME = "database.html"
ASSET_TEMPLATE_FLAME_GRAPH_PAGE_NAME = "flame_graph.html"
ASSET_TEMPLATE_HEAT_MAP_PAGE_NAME = "heat_map.html"
ASSET_TEMPLATE_OVERVIEW_PAGE_NAME = "overview.html"
ASSET_TEMPLATE_README_PAGE_NAME = "readme_page.html"
ASSET_TEMPLATE_SETTINGS_PAGE_NAME = "settings_page.html"
ASSET_THEME_SCRIPT_NAME = "theme.js"
ASSET_THEME_STYLESHEET_NAME = "theme.css"
ASSET_UI_STRINGS_SCRIPT_NAME = "ui_strings.js"
ASSET_UTILITY_SCRIPT_NAME = "utility.js"

CALL_GRAPH_BRANCH_LAST_TEXT = "└ "
CALL_GRAPH_BRANCH_MIDDLE_TEXT = "├ "
CALL_GRAPH_BRANCH_OPEN_TEXT = "┬─"
CALL_GRAPH_BRANCH_PASS_TEXT = "│ "
CALL_GRAPH_LINE_TEXT = "─"
CALL_GRAPH_PAGE_DIR_NAME = "call-graph"
CALL_GRAPH_REVEAL_CLEARANCE_CHARS = 1
CALL_GRAPH_REVEAL_CLEARANCE_LINES = 0.5
CALL_GRAPH_VIEW_KEY = "call-graph"

CALLGRIND_FILE_DATA_ERROR_CODE = "err"
CALLGRIND_FILE_DATA_GIT_CODE = "git"
CALLGRIND_FILE_DATA_INDENT_CHARS = 2
CALLGRIND_FILE_DATA_REPO_CODE = "repo"
CALLGRIND_FILE_DATA_SYSTEM_CODE = "sys"
CALLGRIND_UNKNOWN_NAME = "???"

COUNTER_LIST_CALLEES_LINE_NAME = "callees"
COUNTER_LIST_CALLERS_LINE_NAME = "callers"
COUNTER_LIST_CALLS_LINE_NAME = "calls"

DARK_MODE_ATTRIBUTE_NAME = "data-dark-mode-"
DARK_MODE_DISABLED_VALUE = "disabled"
DARK_MODE_ENABLED_DEFAULT = True
DARK_MODE_ENABLED_VALUE = "enabled"
DARK_MODE_FRAME_QUERY_KEY_NAME = "dark-mode"
DARK_MODE_TOGGLE_QUERY_KEY_NAME = "toggle-dark"

DATABASE_CELL_SEPARATOR_TEXT = ", "
DATABASE_COUNTER_LIST_DEFAULT_SHOWN_NAMES: tuple[str, ...] = (
    "CEst",
    COUNTER_LIST_CALLS_LINE_NAME,
    COUNTER_LIST_CALLERS_LINE_NAME,
)
DATABASE_PAGE_DIR_NAME = "database"
DATABASE_TIME_SUFFIX_SECONDS: dict[str, float] = {"ns": 1e-9, "usecs": 1e-6}
DATABASE_TOP_FUNCTION_ROWS = 50
DATABASE_VIEW_KEY = "database"

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

DRAG_DIRECTION_THRESHOLD_PX = 5

FLAME_GRAPH_COLOR_SCHEME_KEY_NAME = "speedscope-color-scheme"
FLAME_GRAPH_EXPORTER_NAME = "tests/perf2html/scripts/trace_to_speedscope.py"
FLAME_GRAPH_FILE_FORMAT_SCHEMA_URL = (
    "https://www.speedscope.app/file-format-schema.json"
)
FLAME_GRAPH_LOCAL_PROFILE_PATH = "profile"
FLAME_GRAPH_LOCAL_PROFILE_URL_PREFIX = "file:///"
FLAME_GRAPH_MAX_RECORDED_CALLS = 200
FLAME_GRAPH_PROFILE_DIR_NAME = "profiles"
FLAME_GRAPH_PROFILE_GLOBAL_NAME = "report_flame_graph_profiles_"
FLAME_GRAPH_PROFILE_NAME_FORMAT = "%s (loops=%s)"
FLAME_GRAPH_STARTUP_POLL_DELAY_MS = 50
FLAME_GRAPH_STARTUP_POLL_MAX_ATTEMPTS = 200
FLAME_GRAPH_VIEW_ENTRY: tuple[str, str] = (
    "flame-graph",
    "flame-graph/index.html",
)

HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX = "str_counter_"
HEAT_MAP_COUNTER_LIST_DEFAULT_SHOWN_NAMES: tuple[str, ...] = (
    COUNTER_LIST_CALLS_LINE_NAME,
    "Bcm",
    "D1m",
    "DLm",
)
HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX = 8
HEAT_MAP_MODEL_DIR_NAME = "data"
HEAT_MAP_MODEL_GLOBAL_NAME = "report_heat_map_models_"
HEAT_MAP_SCALE_DEFAULT_VALUE = "log"
HEAT_MAP_SORT_DEFAULT_MODE = "heat"
HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_LEAST_SHARE = 0.01
HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_MAX_COUNT = 10
HEAT_MAP_SOURCE_TAB_SIZE_CHARS = 4
HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS = 80
HEAT_MAP_TREE_ALWAYS_LISTED_DIRS = ("lib", "include", "src", "tests/perf")
HEAT_MAP_TREE_AUTO_EXPAND_ABOVE_SHARE = 0.05
HEAT_MAP_VIEW_ENTRY: tuple[str, str] = (
    "heat-map",
    "heat-map/index.html",
)

MENU_DIGIT_KEY_COUNT = 10
MENU_ENTRY_NEEDS: dict[str, list[str]] = {
    "counters": ["counter_list"],
    "heat_scale": ["view"],
    "heat_sort": ["view"],
    "str_menu_file": ["test"],
    "str_menu_function": ["test"],
    "str_view_call_graph": ["test", "view_page"],
    "str_view_database": ["test", "view_page"],
    "str_view_flame_graph": ["test", "view_page"],
}
MENU_FLASH_DURATION_MS = 500
MENU_PULLDOWN_KEY_NAMES: dict[str, str] = {
    "close": "Escape",
    "erase": "Backspace",
    "next": "ArrowDown",
    "previous": "ArrowUp",
    "select": "Enter",
}
MENU_PULLDOWN_LINE_NUMBER_PATTERN = "^(.*):([0-9]+)$"
MENU_PULLDOWN_OPENING_KEY_PATTERN = "^[a-zA-Z]$"
MENU_PULLDOWN_SKIPPED_KEY_NAMES: tuple[str, ...] = (" ",)
MENU_PULLDOWN_SMALL_ENTRY_MAX_COUNT = 3
MENU_SCALE_KEY_STEPS: dict[str, int] = {"+": 1, "=": 1, "-": -1}

NUMBER_FRACTION_DIGITS = 2
NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES = 999.99

PERF_TOOL_TIME_LABEL = "Time"

PROFILE_START_FUNCTION_UNRECORDED_CALLS = 1

RANKING_COUNTER_NAME = "CEst"

README_PAGE_BODY_MARKER = "__README_BODY__"
README_PAGE_CONVERTER_EXTENSION_ARGUMENTS: tuple[str, ...] = ("-e", "table")
README_PAGE_HEADING_ANCHOR_DROPPED_PATTERN = r"[^\w\- ]"
README_PAGE_HEADING_PATTERN = r"(?s)<h([1-6])>(.*?)</h\1>"
README_PAGE_HEADING_TEXT_DROPPED_PATTERN = r"<[^>]*>|&\w+;"
README_PAGE_ROOT_VALUES_MARKER = "__ROOT_VALUES__"

REGULAR_REPORT_VIEW_KEYS: list[str] = [
    CALL_GRAPH_VIEW_KEY,
    FLAME_GRAPH_VIEW_ENTRY[0],
]

SCREENSHOT_LABEL_QUERY_KEY_NAME = "screenshot"
SCREENSHOT_LABEL_QUERY_VALUE = "1"
SCREENSHOT_MENU_KEY_NUMBER = "screenshot-menu"

SETTINGS_DEBUG_ENABLED = False
SETTINGS_DEBUG_HASH_KEY_NAME = "setting-values"
SETTINGS_DEBUG_JSON_INDENT_CHARS = 2
SETTINGS_DEBUG_JSON_MAX_LENGTH_CHARS = 79
SETTINGS_DEBUG_JSON_SPACING_PATTERN = r'("(?:[^\\"]|\\.)*")|[:,]'
SETTINGS_DEBUG_QUERY_KEY_NAME = "debug"
SETTINGS_DEBUG_QUERY_VALUES: dict[str, str] = {"disabled": "0", "enabled": "1"}
SETTINGS_LOAD_LOG_HISTORY_DEFAULT_LINES = 0
SETTINGS_LOAD_LOG_HISTORY_LINE_CHOICES: tuple[int, ...] = (0, 10, 20, 50, 100)
SETTINGS_LOAD_LOG_HISTORY_MAX_LINES = 100
SETTINGS_VIEW_ENTRY: tuple[str, str] = ("settings", "settings/index.html")

SIGNAL_EXIT_CODE_BASE = 128

STORAGE_KEY_DATABASE_COUNTER_LIST = "database.counter_list"
STORAGE_KEY_DATABASE_FUNCTION_ROWS = "database.function_rows"
STORAGE_KEY_HEATMAP_COUNTER_LIST = "heatmap.counter_list"
STORAGE_KEY_HEATMAP_SCALE = "heatmap.scale"
STORAGE_KEY_HEATMAP_SORT = "heatmap.sort"
STORAGE_KEY_LOG_DISPLAY_LENGTH = "log.display_length"
STORAGE_KEY_VIEW_DARK_MODE = "view.dark_mode"
STORAGE_KEY_VIEW_SCALE = "view.scale"
STORAGE_OWNED_KEYS: tuple[str, ...] = (
    FLAME_GRAPH_COLOR_SCHEME_KEY_NAME,
    STORAGE_KEY_DATABASE_COUNTER_LIST,
    STORAGE_KEY_DATABASE_FUNCTION_ROWS,
    STORAGE_KEY_HEATMAP_COUNTER_LIST,
    STORAGE_KEY_HEATMAP_SCALE,
    STORAGE_KEY_HEATMAP_SORT,
    STORAGE_KEY_LOG_DISPLAY_LENGTH,
    STORAGE_KEY_VIEW_DARK_MODE,
    STORAGE_KEY_VIEW_SCALE,
)
STORAGE_VERSION = "perf2html v0"
STORAGE_VERSION_KEY = "perf2html.version"

STYLE_COLOR_DARK_MODE: dict[str, list[str]] = {
    "#effdff": [
        "dark-mode-menu-normal-fg-",
        "dark-mode-menu-normal-outline-",
        "dark-mode-menu-focus-bg-",
    ],
    "#D2691E": [
        "dark-mode-status-bar-fg-",
    ],
    "#20354a": [
        "dark-mode-panel-bg-",
        "dark-mode-status-bar-bg-",
    ],
    "#295987": [
        "dark-mode-menu-normal-bg-",
        "dark-mode-menu-focus-fg-",
    ],
    "#9fd9ff": [
        "dark-mode-page-fg-",
        "dark-mode-page-emphasis-bg-",
    ],
    "#0e171e": [
        "dark-mode-page-bg-",
        "dark-mode-page-emphasis-fg-",
    ],
    "#FFFFFF": ["dark-mode-screenshot-fg-"],
    "#000000": ["dark-mode-screenshot-bg-"],
}
STYLE_COLOR_DARK_MODE_ROLE_PREFIX = "dark-mode-"

STYLE_COLOR_LIGHT_MODE: dict[str, list[str]] = {
    "#000000": [
        "light-mode-menu-focus-bg-",
        "light-mode-menu-normal-fg-",
        "light-mode-menu-normal-outline-",
        "light-mode-page-emphasis-bg-",
        "light-mode-page-fg-",
        "light-mode-screenshot-bg-",
    ],
    "#FFFFFF": [
        "light-mode-menu-focus-fg-",
        "light-mode-page-emphasis-fg-",
        "light-mode-page-bg-",
        "light-mode-screenshot-fg-",
        "light-mode-status-bar-fg-",
    ],
    "#AAAAAA": [
        "light-mode-menu-normal-bg-",
    ],
    "#00AAAA": [
        "light-mode-status-bar-bg-",
    ],
}
STYLE_COLOR_LIGHT_MODE_ROLE_PREFIX = "light-mode-"
STYLE_DESIGN_COORDINATES_WIDTH_PX = 1920
STYLE_DESIGN_FONT_CHARACTER_WIDTH_SHARE = 0.6
STYLE_DESIGN_FONT_FIT_PROPERTY = "--design-font-fit-"
STYLE_DESIGN_FONT_FIT_START_MULTIPLE = 1
STYLE_DESIGN_FONT_SIZE_PROPERTY = "--design-font-size-px-"
STYLE_DESIGN_FONT_SIZE_PX = 20
STYLE_DESIGN_MINIMUM_WINDOW_WIDTH_PX = 1280
STYLE_DESIGN_SCALE_DEFAULT_MULTIPLE = 1
STYLE_DESIGN_SCALE_DEFAULT_STOP = 6
STYLE_DESIGN_SCALE_LARGEST_MULTIPLE = 2
STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE = 0.5
STYLE_DESIGN_SCALE_STOP_COUNT = 11
STYLE_DESIGN_SCALE_STOP_MULTIPLE_FRACTION_DIGITS = 2
STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY = "--design-viewport-height-"
STYLE_DESIGN_VIEWPORT_HEIGHT_START_PERCENT = 100
STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE = 0.5
STYLE_HEAT_CELL_ON_BRIGHT_ROLE = "dark-mode-page-bg-"
STYLE_HEAT_CELL_ON_DARK_ROLE = "dark-mode-page-fg-"
STYLE_HEAT_COLOR_FULL_SCALE_PERCENT = 100
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
STYLE_HEAT_MAP_SOURCE_LINE_NUMBER_MARKER_WIDTH_CHARS = 2
STYLE_HEAT_MAP_SOURCE_LINE_NUMBER_MARKER_WIDTH_PROPERTY = (
    "--heat-map-source-table-line-number-cell-callee-marker-width-"
)
STYLE_HEAT_MAP_TREE_INDENT_PER_LEVEL_CHARS = 2
STYLE_MENU_LOGO_START_SHARE = 0.5
STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS = 2
STYLE_PAGE_BACKGROUND_DARK_MODE_ROLE = "dark-mode-page-bg-"
STYLE_PAGE_BACKGROUND_EARLY_FILL_ENABLED = True
STYLE_PAGE_BACKGROUND_LIGHT_MODE_ROLE = "light-mode-page-bg-"
STYLE_PAGE_FONT_FAMILY = (
    'Monaco, Menlo, "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace'
)
STYLE_PAGE_FONT_FAMILY_PROPERTY = "--page-font-family-"
STYLE_README_PAGE_VALUE_ENTRIES: dict[str, str] = {
    "readme-page-bg-": "#D8C9A3",
    "readme-page-fg-": "#3A2A14",
    "readme-page-font-family-": "Arial",
}
STYLE_TABLE_COLUMN_EDGE_GRAB_CHARS = 0.5
STYLE_TABLE_FUNCTION_LIST_COLUMN_MAX_CHARS = 48
STYLE_TABLE_FUNCTION_NAME_MAX_CHARS = 20
STYLE_TABLE_LOCATION_COLUMN_MAX_CHARS = 48
STYLE_TEXT_SCROLLBAR_THUMB_SHORTEST_CHARS = 4
STYLE_VALUE_ENTRIES: dict[str, str] = {
    "call-graph-border-width-": "1ch",
    "heat-map-band-z-index-": "2",
    "heat-map-minimap-width-": "110px",
    "heat-map-source-band-height-": "1lh",
    "heat-map-source-table-line-number-cell-callee-marker-text-": '"►"',
    "heat-map-source-ticker-tape-gap-": "1ch",
    "heat-map-tree-node-hover-z-index-": "1",
    "heat-map-tree-node-padding-right-": "1ch",
    "heat-map-tree-node-share-percent-width-": "10ch",
    "heat-map-tree-width-": "39ch",
    "menu-button-padding-inline-": "1ch",
    "menu-pulldown-entry-list-max-height-share-": "0.6",
    "menu-pulldown-entry-list-z-index-": "3",
    "menu-pulldown-entry-padding-inline-": "1ch",
    "menu-pulldown-search-box-min-width-": "13ch",
    "menu-status-bar-padding-left-": "1ch",
    "menu-status-bar-padding-right-": "1ch",
    "menu-strip-blank-line-height-": "0.5lh",
    "menu-strip-padding-right-": "1ch",
    "page-body-line-height-": "1.1",
    "page-emphasis-padding-inline-": "1ch",
    "page-inset-block-": "1lh",
    "page-inset-inline-": "2ch",
    "page-line-width-": "0.1em",
    "page-table-cell-padding-inline-": "1ch",
    "page-table-title-z-index-": "1",
    "page-text-scrollbar-horizontal-height-": "1lh",
    "page-text-scrollbar-vertical-width-": "1ch",
    "screenshot-z-index-": "3",
}

TABLE_MARKDOWN_COLUMN_NARROWEST_CHARS = 3
TABLE_ROW_COUNT_CHOICES: tuple[int, ...] = (
    10,
    20,
    30,
    40,
    50,
    60,
    70,
    80,
    90,
    100,
)

TEXT_SCROLLBAR_WHEEL_DELTA_PER_NOTCH = 100
TEXT_SCROLLBAR_WHEEL_NOTCH_LINES = 2.5

THEME_TIME_UNIT_ENTRIES: tuple[tuple[str, float], ...] = (
    ("s", 1.0),
    ("ms", 1e-3),
    ("us", 1e-6),
    ("ns", 1e-9),
    ("ps", 1e-12),
)

TIMING_COLUMN_STRING_ID_PREFIX = "str_column_"
TIMING_COUNTER_RATIOS: tuple[tuple[str, str, str], ...] = (
    ("loads_per_instruction", "L1-dcache-loads", "instructions"),
)
TIMING_PERF_STAT_METRICS: tuple[tuple[str, str, str], ...] = (
    ("instructions_per_cycle", "instructions", "insn per cycle"),
    ("branch_miss_percent", "branch-misses", "of all branches"),
    ("l1d_miss_percent", "L1-dcache-load-misses", "of all L1-dcache accesses"),
)
TIMING_PERF_STAT_METRIC_FRACTION_DIGITS = 6
TIMING_PERF_STAT_NUMBER_PATTERN = r"[0-9]+(?:\.[0-9]+)?"
TIMING_PERF_STAT_UNCOUNTED_VALUES: tuple[str, ...] = (
    "<not counted>",
    "<not supported>",
)
TIMING_TIME_PER_LOOP_NAME = "time_per_loop"

TRACE_BUILDID_KEYWORD = "buildid"
TRACE_BUILDID_LABEL = "Build ID"
TRACE_FUNCTION_EXIT_BIT = 1 << 63
# Uses json compatible precision.
TRACE_HEADER_MAGIC = 0xABCDEF0123456000
TRACE_HEADER_WORDS = 8
TRACE_RECORD_WORDS = 2

VALGRIND_DEBUG_LINE_PATTERN = "^--[0-9]+--"

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

_SETTING_NAMES: frozenset[str] = frozenset()

_MANIFEST_TABLE_COLUMN_GAP_CHARS = 2

_SCALAR_TYPES = (bool, int, float, str)

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

_SENTINEL_TEXT = 'False, 0, 0.0, "", (), [], {}'

_SETTINGS_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
_SETTINGS_PAGE_DATA_MARKER = "__DATA__"

_SHELL_INTEGER_PATTERN = re.compile(r"-?[0-9]+")
_SHELL_MAP_KEY_PATTERN = re.compile(r"\[\"?([A-Za-z0-9_.+-]+)\"?\]=")
_SHELL_PRODUCT_PATTERN = re.compile(
    r"\$\(\(([A-Za-z_][A-Za-z0-9_]*)((?: \* -?[0-9]+)+)\)\)"
)
_SHELL_SETTINGS_FILE_NAME = "settings.sh"
_SHELL_STATEMENT_PATTERN = re.compile(
    r"(declare -A )?([A-Za-z_][A-Za-z0-9_]*)=(.*)"
)
_SHELL_WORD_PATTERN = re.compile(r"'([^']*)'|\"([^\"]*)\"|([^\s)]+)")


def _is_setting_name(name: str) -> bool:
    bare = name.lstrip("_")
    return bool(bare) and bare[0].isupper() and bare.isupper()


class SettingsReader:
    def is_sentinel(self, written: object) -> bool:
        if type(written) not in _SENTINEL_EMPTY_TYPES:
            return False
        if not written:
            return True
        return type(written) is tuple and all(
            self.is_sentinel(item) for item in written
        )

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
            value = self.value(name)
            self.type_check(module_name, name, value, expected)
            setattr(module, name, value)

    def match_check(self, module_name: str, name: str) -> None:
        setting = name.lstrip("_")
        if setting in _SETTING_NAMES:
            return
        raise NameError(
            f"error: constant doesn't match any setting: "
            f"{module_name}.{name} asks for the setting {setting}, which "
            "neither settings.py nor settings.sh defines"
        )

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
                "no annotation"
            )
        if self.is_sentinel(written):
            return
        raise TypeError(
            f"error: settings must have sentinels {_SENTINEL_TEXT}: "
            f"{module_name}.{name} is written with {written!r}"
        )

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

    def shell_scalar_parse(
        self, number: int, text: str, found: dict[str, object]
    ) -> int | str:
        product = _SHELL_PRODUCT_PATTERN.fullmatch(text)
        if product is not None:
            factor = found.get(product.group(1))
            if not isinstance(factor, int):
                self.shell_settings_fail(
                    number,
                    f"{product.group(1)} is not an integer setting assigned "
                    "above",
                )
            factor_texts = _SHELL_INTEGER_PATTERN.findall(product.group(2))
            return factor * math.prod(map(int, factor_texts))
        pairs, closed = self.shell_words_parse(number, text, False)
        if closed or len(pairs) != 1:
            self.shell_settings_fail(
                number,
                "a scalar is exactly one bare or quoted word, or "
                "$((NAME * INTEGER [* INTEGER ...]))",
            )
        value = pairs[0][1]
        if _SHELL_INTEGER_PATTERN.fullmatch(value):
            return int(value)
        return value

    def shell_settings_fail(self, number: int, problem: str) -> NoReturn:
        raise SystemExit(
            f"error: {_SHELL_SETTINGS_FILE_NAME} line {number}: {problem}"
        )

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
                    found[name] = self.shell_scalar_parse(number, text, found)
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
            word = next(
                group for group in word_match.groups() if group is not None
            )
            pairs.append((key, word))

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
            f"{found.__name__}"
        )

    def value(self, name: str) -> object:
        return globals()[name.lstrip("_")]


class SettingsWriter:
    def all_named(self) -> dict[str, object]:
        scope = globals()
        return {name: scope[name] for name in sorted(_SETTING_NAMES)}

    def manifest_table(self, lines: Sequence[str]) -> str:
        return "\n".join(
            label_cell + value_cell
            for label_cell, value_cell in self.manifest_table_rows(lines)
        )

    # Splits each manifest row into its padded label and its gapped value.
    def manifest_table_rows(
        self, lines: Sequence[str]
    ) -> list[tuple[str, str]]:
        for line in lines:
            if "=" not in line:
                raise ValueError(
                    f"error: manifest row {line!r} is not LABEL=VALUE"
                )
        rows = [line.partition("=") for line in lines]
        label_width = max(len(label) for label, _, _ in rows)
        column_gap = " " * _MANIFEST_TABLE_COLUMN_GAP_CHARS
        return [
            (label.ljust(label_width), f"{column_gap}{value}")
            for label, _, value in rows
        ]

    # Refuses a settings number the page's 64 bit float would round.
    def number_exact_check(self, name: str, value: object) -> None:
        if isinstance(value, int) and int(float(value)) != value:
            raise ValueError(
                f"error: a 64 bit float rounds the setting {name}: {value}"
            )
        if isinstance(value, (tuple, list)):
            for item in value:
                self.number_exact_check(name, item)
        if isinstance(value, dict):
            for item in value.values():
                self.number_exact_check(name, item)

    def script_write(self) -> str:
        values = self.all_named()
        for name, value in values.items():
            self.number_exact_check(name, value)
        data = json.dumps(values, indent=2, sort_keys=True, ensure_ascii=False)
        path = os.path.join(_SETTINGS_DIRECTORY, ASSET_SETTINGS_SCRIPT_NAME)
        with open(path, encoding="utf-8") as handle:
            runtime = handle.read()
        if _SETTINGS_PAGE_DATA_MARKER not in runtime:
            raise ValueError(
                f"{path} holds no marker {_SETTINGS_PAGE_DATA_MARKER}"
            )
        return runtime.replace(_SETTINGS_PAGE_DATA_MARKER, data)


_reader = SettingsReader()
globals().update(_reader.shell_settings_read())
_SETTING_NAMES = frozenset(
    name
    for name in globals()
    if not name.startswith("_") and _is_setting_name(name)
)
_writer = SettingsWriter()


def load_into(module_name: str) -> None:
    _reader.load_into(module_name)


def manifest_table(lines: Sequence[str]) -> str:
    return _writer.manifest_table(lines)


def manifest_table_rows(lines: Sequence[str]) -> list[tuple[str, str]]:
    return _writer.manifest_table_rows(lines)


def settings_script_write() -> str:
    return _writer.script_write()
