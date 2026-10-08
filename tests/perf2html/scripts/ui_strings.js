// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.ui_strings_ = (function () {
  "use strict";
  const STRINGS = {
    str_caret_down: "▼",
    str_caret_right: "►",
    str_column_baseline_share: "vs baseline",
    str_column_call_count: "call count",
    str_column_called_at: "called at",
    str_column_callee: "callee",
    str_column_caller: "caller",
    str_column_callers: "callers",
    str_column_calls: "calls",
    str_column_change_share: "% of change",
    str_column_count: "count",
    str_column_counter: "counter",
    str_column_defined_at: "defined at",
    str_column_file_share: "file %",
    str_column_function: "function",
    str_column_function_share: "function %",
    str_column_functions_changed: "functions changed in {counter}",
    str_column_global_share: "global %",
    str_column_inclusive: "incl",
    str_column_line: "line",
    str_column_rank: "#",
    str_column_report: "report",
    str_column_report_per_test: "one report per test",
    str_column_self: "self",
    str_column_share_of_total: "% of total",
    str_column_source: "source",
    str_column_symbol: "symbol",
    str_counter_bc: "conditional branches executed",
    str_counter_bcm: "conditional branches mispredicted",
    str_counter_bi: "indirect branches executed",
    str_counter_bim: "indirect branches mispredicted",
    str_counter_bm: "branches mispredicted, all",
    str_counter_cest: "cycle estimate",
    str_counter_d1m: "L1 data cache misses",
    str_counter_d1mr: "L1 data cache read misses",
    str_counter_d1mw: "L1 data cache write misses",
    str_counter_dlm: "last level data cache misses",
    str_counter_dlmr: "last level data cache read misses",
    str_counter_dlmw: "last level data cache write misses",
    str_counter_dr: "data reads",
    str_counter_dw: "data writes",
    str_counter_i1mr: "L1 instruction cache misses",
    str_counter_ilmr: "last level instruction cache misses",
    str_counter_ir: "instructions executed",
    str_counter_l1m: "L1 cache misses, all",
    str_counter_label: "{description} / {counter}",
    str_counter_llm: "last level cache misses, all",
    str_debug_tip_none: "(none)",
    str_debug_tip_text: "<{tag}> class={class}\nid={id}\nfg={fg}\nbg={bg}",
    str_error_dark_mode_unusable:
      "the dark mode choice came out as {0}, naming neither state",
    str_error_hash_file_missing: "url names line {0} but no file",
    str_error_hash_file_unknown:
      "url encodes a file this report never profiled: {0}",
    str_error_hash_flame_graph_missing:
      "url encodes a test this report has no flame graph for: {0}",
    str_error_hash_function_conflicting:
      "url names function {0} together with a file or line",
    str_error_hash_function_unknown:
      "url encodes a function address this report never recorded: {0}",
    str_error_hash_line_unusable:
      "url encodes a line that is not a line number: {0}",
    str_error_hash_part_misplaced: "url part {0} is not one view {1} reads",
    str_error_hash_part_repeated: "url names {0} more than once",
    str_error_hash_part_unknown: "url part unrecognized: {0}",
    str_error_hash_profile_path_missing:
      "url names no local profile path, which the flame graph needs to start",
    str_error_hash_setting_unknown:
      "url encodes a setting this report does not have: {0}",
    str_error_hash_test_missing: "url names no test",
    str_error_hash_test_unknown:
      "url encodes a test this report does not have: {0}",
    str_error_hash_value_empty: "url part {0} holds no value",
    str_error_hash_view_missing: "url names test {0} but no view",
    str_error_hash_view_unknown:
      "url encodes a view this report does not have: {0}",
    str_error_held_script_unframed:
      "a view page opened outside the overview gets no settings to run under",
    str_error_internal: "internal error: halted and caught fire",
    str_error_report_incomplete:
      "report incomplete, assets/debug.js not written.",
    str_error_setting_unknown: "no such setting: {0}",
    str_error_settings_debug_query_unusable:
      "the {0} query value came out as {1}, expected {2}",
    str_error_settings_values_unusable:
      "url part {0} holds no object of setting values",
    str_error_strip_number_unusable:
      "no available strip entry is numbered {0}",
    str_flame_graph_page_title: "speedscope",
    str_function_name_unknown: "?",
    str_heading_functions_by_counter: "top {count} functions by {measure}",
    str_heading_lines_by_counter: "top {count} lines by {measure}",
    str_heading_manifest: "manifest",
    str_heading_measure_calls: "calls",
    str_heading_measure_calls_diff: "change in calls",
    str_heading_measure_diff: "change in self {counter}",
    str_heading_measure_self: "self {counter}",
    str_heading_tests: "tests",
    str_heat_map_main_label: "heat map view",
    str_heat_map_tree_label: "files",
    str_in_function: " in {function}",
    str_information_box_action_bar_separator: " | ",
    str_information_box_callees: "calls from this line (total {counter})",
    str_information_box_close: "close",
    str_information_box_close_symbol: "[x]",
    str_information_box_copy: "copy",
    str_information_box_function: "function",
    str_information_box_function_self: "{function}: self {self}.",
    str_information_box_function_totals:
      "{function} by call count: self {self}, total {total}.",
    str_information_line_link: "{path} self {share} info",
    str_line_self: "line self",
    str_menu_button: "{number} {label}",
    str_menu_dark_mode_enabled: "dark",
    str_menu_file: "file",
    str_menu_function: "function",
    str_menu_help: "help",
    str_menu_light_mode: "light",
    str_menu_reset: "reset",
    str_menu_scale: "scale",
    str_menu_scale_cell_after_stop: "▓",
    str_menu_scale_cell_before_stop: "▒",
    str_menu_status_line: "line {line}",
    str_menu_status_separator: "/",
    str_menu_test: "test",
    str_menu_test_suite_name: "all",
    str_menu_unavailable_fill: "▒",
    str_no_caller: "(no recorded caller)",
    str_no_match: "(no match)",
    str_no_samples: "no samples",
    str_no_samples_in_test: "This test recorded no samples for {name}.",
    str_not_in_repo: "not in this repo ({path})",
    str_page_language: "en",
    str_pulldown_placeholder: "<type here>",
    str_raw_data_link: "raw data: {name}",
    str_report_name: "perf2html",
    str_scale_curve_linear: "linear scale",
    str_scale_curve_log: "log scale",
    str_scale_entry: "{curve}, {scope}",
    str_scope_file: "per file",
    str_scope_function: "per function",
    str_section_perf_log: "perf log",
    str_section_trace_log: "trace log",
    str_section_valgrind_log: "valgrind log",
    str_settings_apply: "apply",
    str_settings_copy: "copy",
    str_settings_paste: "paste",
    str_sort_alphabetical: "alphabetical",
    str_sort_hottest_first: "hottest first",
    str_source_beyond_end: "error: Line beyond end of file, source changed.",
    str_source_unavailable: "Source not available.",
    str_strip_gap: " ",
    str_table_heading_copy: "copy",
    str_text_scrollbar_gutter: "▒",
    str_text_scrollbar_thumb: "▓",
    str_ticker_tape_entry: "{line} - {share}",
    str_ticker_tape_heading_diff: "most changed lines",
    str_ticker_tape_heading_self: "hottest lines",
    str_title_part_separator: " / ",
    str_view_callers: "callers",
    str_view_flame_graph: "flame graph",
    str_view_frame_title: "report page",
    str_view_heat_map: "heat map",
    str_view_overview: "overview",
    str_view_settings: "settings",
  };
  function text_fill(string_id, replacements) {
    const template = text_of(string_id);
    return template.replace(/\{(\w+)\}/g, (marker, field_name) => {
      if (!Object.prototype.hasOwnProperty.call(replacements, field_name))
        throw new Error(
          "missing ui string value: " + string_id + " " + marker,
        );
      return String(replacements[field_name]);
    });
  }
  function text_of(string_id) {
    if (!Object.prototype.hasOwnProperty.call(STRINGS, string_id)) {
      throw new Error("missing ui string: " + string_id);
    }
    return STRINGS[string_id];
  }
  return { text_fill, text_of };
})();
