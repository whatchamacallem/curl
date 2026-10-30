# SPDX-FileCopyrightText: © 2026 Adrian Johnston.
# SPDX-License-Identifier: MIT
# This file is licensed under the terms of the LICENSE-MIT.md file.

from __future__ import annotations

import html.entities, re

COMMENT_BLOCK_MAX_LINES = 1
COMMENT_FIRST_WORD_REPLACEMENTS = {"Answers": "Returns"}

COMPARE_BACKGROUND_COLOR = (96, 96, 96)
COMPARE_BOX_LINE_PX = 4
COMPARE_CROP_MARGIN_PX = 8
COMPARE_GAP_PX = 8
COMPARE_HIGHLIGHT_COLOR = (255, 0, 255)
COMPARE_IMAGE_PREFIX = "compare_"
COMPARE_KEPT_BRIGHTNESS_SHARE = 0.25
COMPARE_LABEL_COLOR = (255, 255, 255)
COMPARE_LABEL_FONT_PX = 20
COMPARE_LISTED_REGION_COUNT = 4
COMPARE_PANELS_MAX_HEIGHT_SHARE = 2
COMPARE_REGION_TILE_PX = 16

DEBUG_SCRIPT_ASSET: tuple[str, ...] = ("scripts/debug.js",)

ENGLISH_PUNCT = """.,"'?:!()/"""

ENTRY_PAGE = "index.html"

ESCAPE_NAMED_ENTITY_PATTERN = "|".join(
    re.escape(name)
    for name, glyph in sorted(html.entities.html5.items())
    if name.endswith(";") and not glyph.isascii()
)
ESCAPE_PREFIX_PATTERN = r"(?<!\\)(?:\\\\)*"

FAULT_TAIL_CHARS = 400

HEAT_MAP_PAGE_TITLE = ""

IMAGE_SUFFIX = ".png"

INDEX_DATA_PATTERN = re.compile(
    r'<script id="shot-list-" type="application/json">(.*?)</script>',
    re.DOTALL,
)
INDEX_MARKER = "__SHOT_LIST__"
INDEX_PAGE_NAME = "test_index.html"
INDEX_REPORT_NAMES: tuple[str, ...] = (
    "perf2html_baseline_report",
    "perf2html_modified_report",
    "perf2html_diff_report",
)
INDEX_TEMPLATE_NAME = "test_template.html"

MARKDOWN_FENCE_INFO = "txt"
MARKDOWN_FENCE_MARK = "`"
MARKDOWN_FENCE_MIN_MARKS = 3

REPORT_CHECKSUM_COMMAND = (
    "find . -type f ! -name MANIFEST.txt -print"
    " | LC_ALL=C sort | LC_ALL=C tr '\\n' '\\0'"
    " | xargs -0 -r cksum --"
    " | LC_ALL=C sort | cksum"
)
REPORT_THEME_STYLESHEET_ASSET: tuple[str, ...] = ("scripts/theme.css",)

SCREENSHOT_DIR_NAME = "screenshots"
SCREENSHOT_LABEL_URL_PARAM = "screenshot"
SCREENSHOT_LABEL_URL_VALUE = "1"
SCREENSHOT_MENU_URL_PARAM = "screenshot-menu"
SCREENSHOT_RENDER_BUDGET_MS = 8000
SCREENSHOT_SCRATCH_DIR_PATH = "build/screenshots_scratch"
SCREENSHOT_TOGGLE_DARK_URL_PARAM = "toggle-dark"
# The default dark mode first, then that toggled to light.
SCREENSHOT_TOGGLE_DARK_VALUES: tuple[str, ...] = ("0", "1")
SCREENSHOT_TRACE_FILE_PATH = "build/screenshots_trace.json"
SCREENSHOT_VIEWPORTS: tuple[tuple[str, int, int], ...] = (
    ("720p", 1280, 720),
    ("4k", 3840, 2160),
)

SHOOT_DIFF_REPORT = 1 << 0
# Shoots the index page of the finished run at 4k, once.
SHOOT_INDEX_PAGE = 1 << 3
# Shoots 720p dark, once.
SHOOT_ONE_VARIANT = 1 << 1
SHOOT_REGULAR_REPORT = 1 << 2

SHOT_MODE_NAME_PARTS: dict[str, str] = {"0": "dark", "1": "light"}
SHOT_NAME_SEPARATOR = "-"
SHOT_NUMBER_DIGITS = 2

SOURCE_SCAN_ALLOWED_NON_ASCII_CHARS = (
    "©",
    "≈",
    "∞",
    "▲",
    "◄",
    "►",
    "▼",
    "…",
    " ",
    "░",
    "▒",
    "▓",
    "█",
    "◼",
    "─",
    "│",
    "└",
    "├",
    "┬",
    "⊞",
)
SOURCE_SCAN_BANNED_TAG_NAMES = (
    "abbr",
    "address",
    "b",
    "big",
    "blockquote",
    "center",
    "cite",
    "code",
    "del",
    "dfn",
    "em",
    "font",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "ins",
    "kbd",
    "mark",
    "p",
    "q",
    "s",
    "samp",
    "small",
    "strike",
    "strong",
    "sub",
    "sup",
    "tt",
    "u",
    "var",
)
SOURCE_SCAN_COMMENT_MARKUP = (
    "<!--",
    "-->",
    "/*",
    "*/",
    "///",
    "//",
    "#",
    "*",
)

TEST_BELOW_MAIN_FUNCTION_NAME = "(below main)"

TEST_CALL_GRAPH_EDGE_CALLEE_FIELD = 1
TEST_CALL_GRAPH_EDGE_CALLER_FIELD = 0
TEST_CALL_GRAPH_EDGE_FIELDS = 5
TEST_CALL_GRAPH_EDGE_FUNCTION_FIELDS = (0, 1)
TEST_CALL_GRAPH_EDGE_INCLUSIVE_FIELD = 4
TEST_CALL_GRAPH_FUNCTION_FIELDS = 2
TEST_CALL_GRAPH_FUNCTION_NAME_FIELD = 0
TEST_CALL_GRAPH_FUNCTION_SELF_FIELD = 1
TEST_CALL_GRAPH_MODEL_KEYS = ("edges", "functions", "roots", "test_total")
TEST_CALL_GRAPH_PAGE_DIR_NAME = "call-graph"
TEST_CALL_GRAPH_PAGE_LEAST_BYTES = 2000
TEST_CALL_GRAPH_ROOT_CALLS_FIELD = 1
TEST_CALL_GRAPH_ROOT_FIELDS = 2
TEST_CALL_GRAPH_ROOT_FUNCTION_FIELD = 0
TEST_CALL_GRAPH_START_FUNCTION_CALLS = 1
TEST_CALL_GRAPH_START_FUNCTION_NAME = "main"
TEST_CALL_GRAPH_STOP_FUNCTION_NAME = "exit"
TEST_CALL_GRAPH_TABLE_ID = "call-graph-table-"

TEST_CALLGRIND_CALLS_PREFIX = "calls="
TEST_CALLGRIND_COST_LINE_PATTERN = r"[\d+*-]"
TEST_CALLGRIND_NAME_LINE_PATTERN = r"(c?)(?:(ob)|(fn))=(?:\((\d+)\))? ?(.*)"

TEST_DATABASE_CALL_COUNTS_START_FIELD = 1
TEST_DATABASE_CALLEE_ROWS_FIELD = 6
TEST_DATABASE_CALLER_ROWS_FIELD = 5
TEST_DATABASE_FUNCTION_HREF_FIELD = 1
TEST_DATABASE_FUNCTION_NAME_FIELD = 0
TEST_DATABASE_MODEL_ID = "database-model-"
TEST_DATABASE_PAGE_DIR_NAME = "database"
TEST_DATABASE_ROW_BASELINE_CALLS_FIELD = 7
TEST_DATABASE_ROW_CALLS_FIELD = 3
TEST_DATABASE_ROW_FILE_FIELD = 1
TEST_DATABASE_ROW_FUNCTION_FIELD = 0
TEST_DATABASE_ROW_LINE_FIELD = 2
TEST_DATABASE_VIEW_KEY = "database"

TEST_DELTA_HOME_FILE = "lib/home.c"
TEST_DELTA_HOME_FUNCTION_NAME = "inlined_only"
TEST_DELTA_HOME_INLINED_LINE = ("lib/inlined.h", 7)
TEST_DELTA_HOME_IMAGE = "/opt/line/libline.so"
TEST_DELTA_HOME_RECORDING_HEADER = "events: Ir\nsummary: 1\n"
TEST_DELTA_HOME_RECORDING_NAME = "delta_home.callgrind_diff.out"

TEST_DERIVED_COUNTER_NAMES = ("D1m", "DLm", "L1m", "LLm", "Bm", "CEst")

TEST_FLAME_GRAPH_PAGE_LEAST_BYTES = 300
TEST_FLAME_GRAPH_SCRIPT_LEAST_BYTES = 200

TEST_FUNCTION_DATA_CALL_COUNT_FIELD = 1
TEST_FUNCTION_DATA_CALL_PAIR_FIELDS = 2
TEST_FUNCTION_DATA_DOCUMENT = {
    "counters": ["Ir", "Dr"],
    "images": ["/opt/data/libdata.so", "/opt/other/libother.so"],
    "functions": [
        ["data_leaf", 0, 0, 19, [3, 0], [1, 2], []],
        ["data_start", 0, 0, 9, [2, 1], [], [0, 2, 2, 1]],
        ["other_leaf", 1, 1, 4, [2, 2], [1, 1], []],
    ],
}
TEST_FUNCTION_DATA_DOCUMENT_KEYS = ("counters", "functions", "images")
TEST_FUNCTION_DATA_FILE_PATHS = (
    "test_fixture/data.c",
    "test_fixture/other.c",
)
TEST_FUNCTION_DATA_FILE_SUFFIX = "_function_data.json"
TEST_FUNCTION_DATA_RECORDING = (
    "events: Ir Dr\n"
    "summary: 7 3\n"
    "ob=/opt/data/libdata.so\n"
    "fl=test_fixture/data.c\n"
    "fn=outer_start\n"
    "cfn=data_start\n"
    "calls=0 10\n"
    "1 7 3\n"
    "fn=data_start\n"
    "11 2 1\n"
    "cfn=data_leaf\n"
    "calls=2 20\n"
    "12 3 0\n"
    "cob=/opt/other/libother.so\n"
    "cfi=test_fixture/other.c\n"
    "cfn=other_leaf\n"
    "calls=1 5\n"
    "13 2 2\n"
    "fn=data_leaf\n"
    "20 1 0\n"
    "21 2 0\n"
    "ob=/opt/other/libother.so\n"
    "fl=test_fixture/other.c\n"
    "fn=other_leaf\n"
    "5 1 0\n"
    "6 1 2\n"
)
TEST_FUNCTION_DATA_RECORDING_NAME = "function_data.callgrind.out"
TEST_FUNCTION_DATA_ROW_CALLEES_FIELD = 6
TEST_FUNCTION_DATA_ROW_CALLERS_FIELD = 5
TEST_FUNCTION_DATA_ROW_FIELDS = 7
TEST_FUNCTION_DATA_ROW_FILE_FIELD = 2
TEST_FUNCTION_DATA_ROW_IMAGE_FIELD = 1
TEST_FUNCTION_DATA_ROW_LINE_FIELD = 3
TEST_FUNCTION_DATA_ROW_NAME_FIELD = 0
TEST_FUNCTION_DATA_ROW_SELF_FIELD = 4
TEST_FUNCTION_DIFF = {
    "counters": ["Ir", "Dr"],
    "images": [
        "/opt/b/libB.so",
        "build-x/tree-a/lib/libkept.so",
        "build-x/tree-b/bin/tool",
        "build-x/tree-b/lib/libkept.so",
    ],
    "files": [
        "lib/added.c",
        "lib/gone.c",
        "lib/kept.c",
        "lib/moved.c",
        "lib/twice.c",
    ],
    "functions": [
        ["gone", 1, 1, 5, [-2, 0], [2, 0], [[1, -1, 1]], []],
        [
            "kept_caller",
            3,
            2,
            9,
            [1, 0],
            [5, 1],
            [],
            [
                [0, -1, 1],
                [2, 0, 2],
                [3, 1, 0],
                [4, 1, 1],
                [5, 0, 1],
                [6, 0, 1],
            ],
        ],
        ["kept_steady", 3, 2, 19, [0, 0], [4, 0], [[1, 0, 2]], []],
        ["libkept.so/added", 3, 0, 49, [1, 0], [0, 0], [[1, 1, 0]], []],
        ["libkept.so/spread", 3, 4, 7, [0, 0], [1, 1], [[1, 1, 1]], []],
        ["libkept.so/twice", 3, 4, 3, [0, -1], [2, 2], [[1, 0, 1]], []],
        ["moved", 0, 3, 31, [0, 1], [3, 3], [[1, 0, 1]], []],
        ["tool/added", 2, 0, 49, [2, 0], [0, 0], [], []],
        ["tool/spread", 2, 4, 7, [3, 0], [0, 0], [], []],
        ["tool/twice", 2, 4, 3, [0, 0], [6, 0], [], []],
    ],
}
TEST_FUNCTION_DIFF_AMBIGUOUS_CASES = (
    (
        ("/opt/a/libA.so", "/opt/a/libC.so"),
        ("/opt/b/libB.so", "/opt/b/libD.so"),
    ),
    (("/opt/a/libA.so", "/opt/a/libC.so"), ("/opt/b/libB.so",)),
    (("/opt/a/libA.so",), ("/opt/b/libB.so", "/opt/b/libD.so")),
    (
        ("build-x/tree-a/lib/libX.so", "lib/libX.so"),
        ("build-x/tree-b/lib/libX.so",),
    ),
)
TEST_FUNCTION_DIFF_AMBIGUOUS_ERROR = (
    "error: ambiguous resolution of overloads of overload:"
)
TEST_FUNCTION_DIFF_AMBIGUOUS_NAME = "overload"
TEST_FUNCTION_DIFF_AMBIGUOUS_PATHS = ("lib/overload.c",)
TEST_FUNCTION_DIFF_BASELINE_DOCUMENT = {
    "counters": ["Ir", "Dr"],
    "images": [
        "/opt/a/libA.so",
        "build-x/tree-a/bin/tool",
        "build-x/tree-a/lib/libkept.so",
    ],
    "functions": [
        ["gone", 2, 0, 5, [2, 0], [1, 1], []],
        [
            "kept_caller",
            2,
            1,
            9,
            [5, 1],
            [],
            [0, 1, 2, 2, 3, 1, 4, 1, 5, 1],
        ],
        ["kept_steady", 2, 1, 19, [4, 0], [1, 2], []],
        ["moved", 0, 2, 29, [3, 3], [1, 1], []],
        ["spread", 2, 3, 7, [1, 1], [1, 1], []],
        ["twice", 2, 3, 3, [2, 2], [1, 1], []],
        ["twice", 1, 3, 3, [6, 0], [], []],
    ],
}
TEST_FUNCTION_DIFF_BASELINE_NAME = "baseline_function_data.json"
TEST_FUNCTION_DIFF_BASELINE_PATHS = (
    "lib/gone.c",
    "lib/kept.c",
    "lib/moved.c",
    "lib/twice.c",
)
TEST_FUNCTION_DIFF_BUILD_TREES = ("build-x/tree-a", "build-x/tree-b")
TEST_FUNCTION_DIFF_MODIFIED_DOCUMENT = {
    "counters": ["Ir", "Dr"],
    "images": [
        "/opt/b/libB.so",
        "build-x/tree-b/bin/tool",
        "build-x/tree-b/lib/libkept.so",
    ],
    "functions": [
        ["added", 2, 0, 49, [1, 0], [2, 1], []],
        ["added", 1, 0, 49, [2, 0], [], []],
        [
            "kept_caller",
            2,
            1,
            9,
            [6, 1],
            [],
            [0, 1, 3, 2, 4, 1, 5, 2, 7, 1],
        ],
        ["kept_steady", 2, 1, 19, [4, 0], [2, 2], []],
        ["moved", 0, 2, 31, [3, 4], [2, 1], []],
        ["spread", 2, 3, 7, [1, 1], [2, 2], []],
        ["spread", 1, 3, 7, [3, 0], [], []],
        ["twice", 2, 3, 3, [2, 1], [2, 1], []],
        ["twice", 1, 3, 3, [6, 0], [], []],
    ],
}
TEST_FUNCTION_DIFF_MODIFIED_NAME = "modified_function_data.json"
TEST_FUNCTION_DIFF_MODIFIED_PATHS = (
    "lib/added.c",
    "lib/kept.c",
    "lib/moved.c",
    "lib/twice.c",
)
TEST_FUNCTION_ENTRY_CONFLICT = (
    "cfi=lib/lines.c\ncfn=two_line_function\ncalls=1 31\n3 1\n"
)
TEST_FUNCTION_LINE_RECORDING = (
    "events: Ir\n"
    "summary: 10\n"
    "ob=/opt/line/libline.so\n"
    "fl=lib/lines.c\n"
    "fn=start_caller\n"
    "cfn=start_function\n"
    "calls=0 20\n"
    "5 10\n"
    "fn=start_function\n"
    "22 1\n"
    "cfn=two_line_function\n"
    "calls=1 30\n"
    "23 2\n"
    "cfn=one_line_function\n"
    "calls=1 39\n"
    "24 1\n"
    "cfn=blocked_function\n"
    "calls=1 40\n"
    "25 2\n"
    "cfn=inlined_function\n"
    "calls=1 50\n"
    "26 2\n"
    "cfi=lib/first.c\n"
    "cfn=line_one_function\n"
    "calls=1 1\n"
    "27 2\n"
    "fn=two_line_function\n"
    "30 1\n"
    "31 1\n"
    "fn=one_line_function\n"
    "39 1\n"
    "fn=blocked_function\n"
    "40 1\n"
    "41 1\n"
    "fn=inlined_function\n"
    "50 1\n"
    "fi=lib/inlined.h\n"
    "7 1\n"
    "fl=lib/first.c\n"
    "fn=line_one_function\n"
    "1 1\n"
    "2 1\n"
)
TEST_FUNCTION_LINE_RECORDING_NAME = "function_line.callgrind.out"
TEST_FUNCTION_LINES = {
    "blocked_function": ("lib/lines.c", 40),
    "inlined_function": ("lib/lines.c", 49),
    "line_one_function": ("lib/first.c", 1),
    "one_line_function": ("lib/lines.c", 39),
    "start_function": ("lib/lines.c", 19),
    "two_line_function": ("lib/lines.c", 29),
}

TEST_HEAT_MAP_CALL_ROW_COUNT_FIELD = 4
TEST_HEAT_MAP_CALL_ROW_FUNCTION_FIELD = 0
TEST_HEAT_MAP_MODEL_LEAST_BYTES = 5000
TEST_HEAT_MAP_PAGE_LEAST_BYTES = 1000

TEST_LIST_FILE_NAME = "test_list.txt"

TEST_MANIFEST_EXECUTABLE_LABEL = "executable"
TEST_MANIFEST_LEAST_BYTES = 40

TEST_OVERVIEW_CHANGE_CELL_TEXT = (
    " in a cell whose heat_percent agrees with it, else an empty text"
)
TEST_OVERVIEW_CHANGE_LARGEST_ERROR = 0.0050001
TEST_OVERVIEW_CHANGE_PATTERN = (
    r"(?:0\.00%|[▲▼] *(?:≈0\.00%|-?\d+\.\d{2}%|∞%|≈∞%|\d+\.\d{2}x))?"
)
TEST_OVERVIEW_PAGE_LEAST_BYTES = 2000
TEST_OVERVIEW_PAGE_TITLE = ""
TEST_OVERVIEW_RATIO_FIELDS = (2, 3, 4, 5)
TEST_OVERVIEW_RATIO_LARGEST_ERROR = 0.00000050001
TEST_OVERVIEW_RATIO_PATTERN = r"(?:\d+\.\d{6})?"
TEST_OVERVIEW_RAW_DATA_MARKUP = '<div id="overview-raw-data-">'
TEST_OVERVIEW_ROW_FIELD_COUNT = 6
TEST_OVERVIEW_TESTS_HEADING_MARKUP = (
    '<div id="overview-tests-heading-" class="page-heading-"></div>'
)
TEST_OVERVIEW_TESTS_TABLE_DATA_ID = "overview-tests-table-"
TEST_OVERVIEW_TIME_LARGEST_ERROR = 0.0050001
TEST_OVERVIEW_TIME_PER_LOOP_FIELD = 1
TEST_OVERVIEW_TIME_PER_LOOP_PATTERN = r"(?:\d+\.\d{2}(?:s|ms|us|ns|ps))?"
TEST_OVERVIEW_TIME_UNIT_SECONDS = {
    "s": 1.0,
    "ms": 1e-3,
    "us": 1e-6,
    "ns": 1e-9,
    "ps": 1e-12,
}
TEST_OVERVIEW_VALUE_FIELDS = (1, 2, 3, 4, 5)

TEST_PAGE_PREAMBLE_SCRIPT_NAMES = (
    "error_overlay.js",
    "settings.js",
    "utility.js",
    "ui_strings.js",
)

TEST_PATHS_DOCUMENT_CODES = ("err", "git", "repo", "sys")
TEST_PATHS_DOCUMENT_ERROR_CODE = "err"
TEST_PATHS_DOCUMENT_KEYS = ("p", "t")
TEST_PATHS_DOCUMENT_NAME = "0_file_data.json"

TEST_PERF_TOOL_TREE_PATH = "tests/perf/perf"

TEST_PROFILE_FILE_SUFFIX = ".callgrind.out"

TEST_RAW_ARCHIVE_LEAST_BYTES = 100

TEST_README_HTML_NAME = "README.html"
TEST_README_MARKDOWN_NAME = "README.md"

TEST_SHARED_IMAGES_FUNCTION_NAMES = (
    "/opt/one/libsame.so/shared_name",
    "/opt/two/libsame.so/shared_name",
    "libother.so/shared_name",
    "lone_name",
    "other_name",
)
TEST_SHARED_IMAGES_RECORDING = (
    "events: Ir\n"
    "summary: 5\n"
    "ob=/opt/one/libsame.so\n"
    "fl=one.c\n"
    "fn=shared_name\n"
    "1 1\n"
    "fn=lone_name\n"
    "2 1\n"
    "ob=/opt/two/libsame.so\n"
    "fl=two.c\n"
    "fn=shared_name\n"
    "3 1\n"
    "ob=/opt/other/libother.so\n"
    "fl=other.c\n"
    "fn=shared_name\n"
    "4 1\n"
    "fn=other_name\n"
    "5 1\n"
)
TEST_SHARED_IMAGES_RECORDING_NAME = "shared_images.callgrind.out"

TEST_SOURCE_DATABASE_GLOBAL_NAME = "report_source_database_"
TEST_SOURCE_DATABASE_KEYS = ("files", "functions")
TEST_SOURCE_DATABASE_LEAST_BYTES = 1000
TEST_SOURCE_DATABASE_SCRIPT_PATH = "scripts/source_database.js"

TEST_TIMER_ARTIFACTS_PREFIX = "timer-artifacts-"

TEST_TIMING_DOCUMENT_NAME = "0_timing_data.json"
TEST_TIMING_VALUE_NAMES = (
    "time_per_loop",
    "instructions_per_cycle",
    "loads_per_instruction",
    "branch_miss_ratio",
    "l1d_miss_ratio",
)

TEST_UNKNOWN_IMAGE_NAMES = ("???", "(unknown image)")

TIMING_FILE_LINES_MAX = 3
TIMING_LOAD_PHASE_NAME = "load"
TIMING_MICROSECONDS_PER_MILLISECOND = 1000
TIMING_SCRIPT_PHASE_NAME = "script"

TRACE_BEGIN_TYPE = "B"
TRACE_CATEGORIES = "devtools.timeline"
# navigationStart is stamped in virtual time, so loads count from the commit.
TRACE_COMMIT_NAME = "CommitLoad"
TRACE_COMPLETE_TYPE = "X"
TRACE_END_TYPE = "E"
TRACE_FORMAT = "json"
TRACE_FUNCTION_CALL_NAME = "FunctionCall"
TRACE_LOAD_NAME = "MarkLoad"
TRACE_MARK_NAMES: tuple[str, ...] = (TRACE_COMMIT_NAME, TRACE_LOAD_NAME)
# A function call of this script id runs no page script, so no file owns it.
TRACE_NO_SCRIPT_ID = "0"
# The phase each traced slice counts to and the argument naming its frame.
TRACE_PHASES: dict[str, tuple[str, str]] = {
    "EvaluateScript": (TIMING_SCRIPT_PHASE_NAME, "data"),
    TRACE_FUNCTION_CALL_NAME: (TIMING_SCRIPT_PHASE_NAME, "data"),
    "Layout": ("layout", "beginData"),
    "Paint": ("paint", "data"),
    "UpdateLayoutTree": ("style", "beginData"),
}
TRACE_SLICE_TYPES: tuple[str, ...] = (
    TRACE_BEGIN_TYPE,
    TRACE_COMPLETE_TYPE,
    TRACE_END_TYPE,
)

VERBOSE_RAW_LEVEL = 2
