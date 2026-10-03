# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import json, os, re, sys
from collections.abc import Sequence
from typing import NoReturn, get_origin, get_type_hints


ASSET_CALLERS_SCRIPT_NAME = "callers.js"
ASSET_LIGHT_MODE_STYLESHEET_NAME = "light_mode.css"
ASSET_DARK_MODE_ENABLED_STYLESHEET_NAME = "dark_mode.css"
ASSET_ERROR_OVERLAY_SCRIPT_NAME = "error_overlay.js"
ASSET_FLAME_GRAPH_SCRIPT_NAME = "flame_graph.js"
ASSET_FRAME_SCRIPT_NAME = "frame.js"
ASSET_HEAT_MAP_SCRIPT_NAME = "heat_map.js"
ASSET_HEAT_MAP_STYLESHEET_NAME = "heat_map.css"
ASSET_MENU_SCRIPT_NAME = "menu.js"
ASSET_MENU_STYLESHEET_NAME = "menu.css"

ASSET_PULLDOWN_TEXT_SCRIPT_NAME = "pulldown_text.js"

ASSET_SETTINGS_SCRIPT_NAME = "settings.js"

ASSET_TEMPLATE_FLAME_GRAPH_PAGE_NAME = "flame_graph.html"
ASSET_TEMPLATE_HEAT_MAP_PAGE_NAME = "heat_map.html"
ASSET_TEMPLATE_OVERVIEW_PAGE_NAME = "overview.html"
ASSET_TEMPLATE_SETTINGS_HANDLER_NAME = "settings.js"

ASSET_THEME_SCRIPT_NAME = "theme.js"
ASSET_THEME_STYLESHEET_NAME = "theme.css"
ASSET_UI_STRINGS_SCRIPT_NAME = "ui_strings.js"
ASSET_UTILITY_SCRIPT_NAME = "utility.js"

CALLERS_PERF_LOG_SKIPPED_HEAD_LINES = 9

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

CALLERS_TOP_FUNCTION_ROWS = 50

CALLERS_VIEW_KEY = "callers"

DARK_MODE_ATTRIBUTE_NAME = "data-dark-mode-"
DARK_MODE_DISABLED_VALUE = "disabled"
DARK_MODE_ENABLED_DEFAULT = True
DARK_MODE_ENABLED_VALUE = "enabled"
DARK_MODE_QUERY_KEY_NAME = "screenshot-dark"
DARK_MODE_QUERY_VALUES: dict[str, str] = {"disabled": "0", "enabled": "1"}

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

FLAME_GRAPH_EXPORTER_NAME = "tests/perf2html/scripts/trace_to_speedscope.py"

FLAME_GRAPH_LOCAL_PROFILE_PATH = "profile"
FLAME_GRAPH_LOCAL_PROFILE_URL_PREFIX = "file:///"

FLAME_GRAPH_MAX_RECORDED_CALLS = 200

FLAME_GRAPH_PROFILE_DIR_NAME = "profiles"
FLAME_GRAPH_PROFILE_GLOBAL_NAME = "report_flame_graph_profiles_"

FLAME_GRAPH_STARTUP_POLL_DELAY_MS = 50
FLAME_GRAPH_STARTUP_POLL_MAX_ATTEMPTS = 200

FLAME_GRAPH_VIEW_ENTRY: tuple[str, str, str] = (
    "flame-graph",
    "flame graph",
    "flame-graph/index.html",
)

HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX = "str_counter_"

HEAT_MAP_HOME_LINES_LOCATION_MAX_CHARS = 28
HEAT_MAP_HOME_LINES_SOURCE_COLUMN_MAX_CHARS = 36
HEAT_MAP_HOME_LINES_SOURCE_SNIPPET_MAX_CHARS = 110

HEAT_MAP_HOME_TABLE_MAX_ROWS = 60

HEAT_MAP_MINIMAP_SOURCE_WIDTH_CHARS = 80

HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX = 8

HEAT_MAP_MODEL_DIR_NAME = "data"
HEAT_MAP_MODEL_GLOBAL_NAME = "report_heat_map_models_"

HEAT_MAP_SECONDARY_COUNTER_NAMES: tuple[str, ...] = ("D1m", "DLm", "Bcm")

HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_LEAST_SHARE = 0.01
HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_MAX_COUNT = 10

HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS = 80

HEAT_MAP_TREE_ALWAYS_LISTED_DIRS = ("lib", "include", "src", "tests/perf")

HEAT_MAP_TREE_AUTO_EXPAND_ABOVE_SHARE = 0.05

HEAT_MAP_VIEW_ENTRY: tuple[str, str, str] = (
    "heat-map",
    "heatmap",
    "heat-map/index.html",
)

LAYOUT_RESIZE_SETTLE_DELAY_MS = 120

MENU_BUTTON_ORDER: tuple[str, ...] = (
    "overview",
    "test",
    "file",
    "function",
    "heat-map",
    "callers",
    "flame-graph",
    "dark-mode",
    "reset",
    "help",
    "scale",
)

MENU_PULLDOWN_KEY_NAMES: dict[str, str] = {
    "close": "Escape",
    "next": "ArrowDown",
    "previous": "ArrowUp",
    "select": "Enter",
}

MENU_PULLDOWN_LINE_NUMBER_PATTERN = "^(.*):([0-9]+)$"

MENU_PULLDOWN_MERGED_TEST_NAME = "all"

MENU_PULLDOWN_OPENING_KEY_PATTERN = "^[a-zA-Z]$"

MENU_PULLDOWN_SKIPPED_KEY_NAMES: tuple[str, ...] = (" ",)

MENU_SCALE_KEY_NAMES: dict[str, str] = {
    "larger": "ArrowRight",
    "smaller": "ArrowLeft",
}

NUMBER_FRACTION_DIGITS = 2

NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES = 999.99

NUMBER_SMALLEST_PRINTED_PERCENT = 0.01

PAGE_SETTINGS_GLOBAL_NAME = "settings_"

PANE_SPLITTER_WIDEST_WINDOW_SHARE = 0.6

RANKING_COUNTER_NAME = "CEst"

REPORT_SOURCES_DIR_NAME = "sources"

STORAGE_OWNED_KEYS: tuple[str, ...] = (
    "heat.counter",
    "heat.scale",
    "heat.sort",
    "view.dark_mode",
    "view.scale",
)
STORAGE_OWNED_PREFIXES: tuple[str, ...] = ("split.",)

STORAGE_VERSION = "perf2html v5"
STORAGE_VERSION_KEY = "perf2html.version"

STYLE_COLOR_DARK_MODE: dict[str, list[str]] = {
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
        "dark-mode-menu-focus-bg-",
        "dark-mode-menu-normal-fg-",
        "dark-mode-page-highlight-fg-",
        "dark-mode-page-normal-fg-",
        "dark-mode-status-bar-fg-",
        "heat-map-heat-cell-on-dark-fg-",
        "heat-map-menu-field-fg-",
        "heat-map-source-line-detail-function-name-fg-",
        "heat-map-source-table-row-focus-fg-",
        "heat-map-source-ticker-tape-entry-focus-fg-",
        "heat-map-tree-node-focus-fg-",
        "menu-button-current-bg-",
        "page-link-focus-fg-",
        "page-table-row-focus-fg-",
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
        "dark-mode-page-highlight-bg-",
        "heat-map-main-focus-bg-",
        "heat-map-menu-field-focus-bg-",
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
        "dark-mode-menu-focus-fg-",
        "heat-map-menu-field-bg-dim-",
        "heat-map-menu-strip-bg-dim-",
        "heat-map-source-line-detail-bg-dim-",
        "menu-button-current-fg-dim-",
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
        "dark-mode-menu-normal-bg-",
        "dark-mode-page-normal-bg-",
        "dark-mode-status-bar-bg-",
        "heat-map-heat-cell-on-bright-fg-dim-",
        "heat-map-main-bg-dim-",
        "heat-map-minimap-bg-dim-",
        "heat-map-source-line-detail-table-bg-dim-",
        "overview-view-frame-bg-dim-",
        "page-scrollbar-corner-bg-dim-",
        "page-scrollbar-track-bg-dim-",
    ],
}

STYLE_COLOR_LIGHT_MODE: dict[str, list[str]] = {
    "#000000": [
        "light-mode-menu-focus-bg-",
        "light-mode-menu-normal-fg-",
        "light-mode-page-highlight-bg-",
        "light-mode-page-normal-fg-",
        "light-mode-status-bar-fg-",
    ],
    "#FFFFFF": [
        "light-mode-menu-focus-fg-",
        "light-mode-page-highlight-fg-",
        "light-mode-page-normal-bg-",
    ],
    "#AAAAAA": [
        "light-mode-menu-normal-bg-",
    ],
    "#00AAAA": [
        "light-mode-status-bar-bg-",
    ],
    "#F5F6FA": [
        "light-mode-page-bg-",
    ],
    "#2F3640": [
        "light-mode-page-fg-",
    ],
}

STYLE_DESIGN_COORDINATES_WIDTH_PX = 1920

STYLE_DESIGN_FONT_CHARACTER_WIDTH_PX = 7.2

STYLE_DESIGN_FONT_FIT_PROPERTY = "--design-font-fit-"

STYLE_DESIGN_FONT_SIZE_PX = 12

STYLE_DESIGN_MINIMUM_WINDOW_WIDTH_PX = 1280

STYLE_DESIGN_SCALE_DEFAULT_MULTIPLE = 1

STYLE_DESIGN_SCALE_DEFAULT_TRAVEL_SHARE = 0.5

STYLE_DESIGN_SCALE_LARGEST_MULTIPLE = 2
STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE = 0.5

STYLE_DESIGN_SCALE_STOP_COUNT = 21

STYLE_DESIGN_SCALE_STOP_MULTIPLE_FRACTION_DIGITS = 2

STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY = "--design-viewport-height-"

STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE = 0.5

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

STYLE_HEAT_MAP_MENU_DROPDOWN_EXTRA_WIDTH_CHARS = 4

STYLE_HEAT_MAP_SOURCE_LINE_NUMBER_MARKER_WIDTH_CHARS = 2

STYLE_HEAT_MAP_TREE_INDENT_PER_LEVEL_CHARS = 2

STYLE_HEAT_MAP_TREE_PANE_NARROWEST_PX = 120

STYLE_MENU_LOGO_START_FRACTION = 0.5

STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS = 2

STYLE_PAGE_FONT_FAMILY = (
    'Monaco, Menlo, "DejaVu Sans Mono", "Liberation Mono", Consolas, monospace'
)

STYLE_PANE_SPLITTER_KEY_STEP_PX = 36

STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS = 2

STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS = 20

STYLE_TABLE_GROW_COLUMN_NARROWEST_CHARS = 20

STYLE_TABLE_LOCATION_COLUMN_MAX_CHARS = 48

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
    "heat-map-tree-node-padding-right-": "1ch",
    "heat-map-tree-node-share-percent-width-": "10ch",
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
    "light-mode-page-border-width-": "0.125ch",
    "page-scrollbar-thickness-": "14px",
    "page-table-cell-padding-inline-": "1ch",
    "page-table-column-title-z-index-": "1",
    "screenshot-label-border-width-": "1ch",
    "screenshot-label-font-size-": "1.5em",
    "screenshot-label-z-index-": "3",
}

TABLE_COLUMN_SLIDE_THRESHOLD_PX = 5

THEME_TIME_UNIT_ENTRIES: tuple[tuple[str, float], ...] = (
    ("s", 1.0),
    ("ms", 1e-3),
    ("us", 1e-6),
    ("ns", 1e-9),
    ("ps", 1e-12),
)

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


def _is_setting_name(name: str) -> bool:
    bare = name.lstrip("_")
    return bool(bare) and bare[0].isupper() and bare.isupper()


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
_SETTINGS_PAGE_NAME_MARKER = "__NAME__"

_SHELL_INTEGER_PATTERN = re.compile(r"-?[0-9]+")

_SHELL_MAP_KEY_PATTERN = re.compile(r"\[\"?([A-Za-z0-9_.+-]+)\"?\]=")

_SHELL_SETTINGS_FILE_NAME = "settings.sh"

_SHELL_STATEMENT_PATTERN = re.compile(
    r"(declare -A )?([A-Za-z_][A-Za-z0-9_]*)=(.*)"
)

_SHELL_WORD_PATTERN = re.compile(r"'([^']*)'|\"([^\"]*)\"|([^\s)]+)")


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
            value = self.value_of(name)
            self.type_check(module_name, name, value, expected)
            setattr(module, name, value)

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
            f"{found.__name__}. Correct the annotation, or change the value "
            "in settings.py."
        )

    def value_of(self, name: str) -> object:
        return globals()[name.lstrip("_")]


class SettingsWriter:
    def all_named(self) -> dict[str, object]:
        scope = globals()
        return {name: scope[name] for name in sorted(_SETTING_NAMES)}

    def manifest_table(self, lines: Sequence[str]) -> str:
        rows = [("", "", lines[0])]
        rows += [line.partition("=") for line in lines[1:]]
        label_width = max(len(label) for label, _, _ in rows)
        column_gap = " " * _MANIFEST_TABLE_COLUMN_GAP_CHARS
        return "\n".join(
            f"{label.ljust(label_width)}{column_gap}{value}"
            for label, _, value in rows
        )

    def script_write(self) -> str:
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


def settings_script_write() -> str:
    return _writer.script_write()
