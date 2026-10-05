// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.ui_strings_ = (function () {
  "use strict";
  const STRINGS = {
    str_caret_right: "⯈",
    str_caret_down: "⯆",
    str_column_baseline_share: "vs baseline",
    str_column_call_count: "call count",
    str_column_called_at: "called at",
    str_column_callee: "callee",
    str_column_caller: "caller",
    str_column_calls: "calls",
    str_column_count: "count",
    str_column_counter: "counter",
    str_column_defined_at: "defined at",
    str_column_file_share: "file %",
    str_column_function: "function",
    str_column_function_share: "function %",
    str_column_global_share: "global %",
    str_column_inclusive: "incl",
    str_column_line: "line",
    str_column_rank: "#",
    str_column_self: "self",
    str_column_share_of_total: "% of total",
    str_column_source: "source",
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
    str_counter_llm: "last level cache misses, all",
    str_error_dark_mode_unusable:
      "the dark mode choice came out as {0}, naming neither state",
    str_error_diff_fall_past_baseline:
      "a change of {0} falls past its baseline of {1}",
    str_error_flame_graph_never_started:
      "flame graph viewer did not start within {0}s",
    str_error_flame_graph_unfiled:
      "the flame graph script for test {0} filed no profile",
    str_error_font_refused: "the browser refused the page font",
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
    str_error_hash_test_missing: "url names no test",
    str_error_hash_test_unknown:
      "url encodes a test this report does not have: {0}",
    str_error_hash_value_empty: "url part {0} holds no value",
    str_error_hash_view_mismatch:
      "url does not name view {0}, the one this page shows",
    str_error_hash_view_missing: "url names test {0} but no view",
    str_error_hash_view_unknown:
      "url encodes a view this report does not have: {0}",
    str_error_heading_attached_twice: "table heading {0} is attached twice",
    str_error_heading_count_missing:
      "table heading {0} names row count key {1} but shows no count",
    str_error_heading_table_missing:
      "table heading {0} sits immediately before no table",
    str_error_heat_map_unfiled:
      "the heat map script for test {0} filed no model",
    str_error_message_tag_unknown: "cross-frame message tag unrecognized: {0}",
    str_error_pane_width_unusable:
      "the stored pane width {0} came out as {1}, not a number of characters",
    str_error_pulldown_focus_refused:
      "the browser kept focus on {0}, so keys cannot reach the pulldown",
    str_error_pulldown_text_missing:
      "no file and function names were shipped for the pulldowns",
    str_error_report_incomplete:
      "report incomplete, assets/report_complete.js not written.",
    str_error_row_count_unusable:
      "the row count for {0} came out as {1}, not one of {2}",
    str_error_rows_unwalked:
      "table {0} walks no rows, so none of its rows can be a tab stop",
    str_error_scale_stop_unusable:
      "the scale bar stop came out as {0}, not a whole number from 0 to {1}",
    str_error_scale_stored_unusable:
      "the stored page scale came out as {0}, not a number from {1} to {2}",
    str_error_scale_unusable: "the page scale came out as {0}",
    str_error_strip_entry_kind_unknown:
      "strip entry {0} has kind {1}, which no strip cell draws",
    str_error_strip_entry_repeated: "the strip names entry {0} more than once",
    str_error_strip_entry_unknown: "the strip holds no entry named {0}",
    str_error_strip_entry_unusable: "strip entry {0} is no available {1}",
    str_error_text_scrollbar_attached_twice:
      "text scrollbar {0} inside {1} is attached twice",
    str_error_text_scrollbar_axis_unknown:
      "text scrollbar axis unrecognized: {0}",
    str_error_wheel_delta_mode_unknown: "wheel delta mode unrecognized: {0}",
    str_function_name_unknown: "?",
    str_heading_functions_by_counter: "top {count} functions by {measure}",
    str_heading_lines_by_counter: "top {count} lines by {measure}",
    str_heading_measure_diff: "change in self {counter}",
    str_heading_measure_self: "self {counter}",
    str_heat_map_main_label: "heat map view",
    str_heat_map_tree_label: "files",
    str_in_function: " in {function}",
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
    str_menu_light_mode: "light",
    str_menu_dark_mode_enabled: "dark",
    str_menu_file: "file",
    str_menu_function: "function",
    str_menu_help: "help",
    str_menu_overview: "overview",
    str_menu_reset: "reset",
    str_menu_scale: "scale",
    str_menu_scale_cell_after_stop: "▓",
    str_menu_scale_cell_before_stop: "▒",
    str_menu_status_line: "line {line}",
    str_menu_test: "test",
    str_menu_unavailable_fill: "▒",
    str_no_caller: "(no recorded caller)",
    str_no_match: "(no match)",
    str_no_samples: "no samples",
    str_no_samples_in_test: "This test recorded no samples for {name}.",
    str_not_in_repo: "not in this repo ({path})",
    str_pulldown_placeholder: "<type here>",
    str_report_name: "perf2html",
    str_scale_curve_linear: "linear scale",
    str_scale_curve_log: "log scale",
    str_scale_entry: "{curve}, {scope}",
    str_scope_file: "per file",
    str_scope_function: "per function",
    str_sort_alphabetical: "alphabetical",
    str_sort_hottest_first: "hottest first",
    str_source_beyond_end: "error: Line beyond end of file, source changed.",
    str_source_unavailable: "Source not available.",
    str_table_heading_copy: "copy",
    str_text_scrollbar_gutter: "▒",
    str_text_scrollbar_thumb: "▓",
    str_ticker_tape_heading_diff: "most changed lines",
    str_ticker_tape_heading_self: "hottest lines",
    str_view_callers: "callers",
  };
  function text_fill(string_id, replacements) {
    const template = text_of(string_id);
    return template.replace(/\{(\w+)\}/g, (marker, field_name) =>
      Object.prototype.hasOwnProperty.call(replacements, field_name)
        ? String(replacements[field_name])
        : marker,
    );
  }
  function text_of(string_id) {
    if (!Object.prototype.hasOwnProperty.call(STRINGS, string_id)) {
      throw new Error("missing ui string: " + string_id);
    }
    return STRINGS[string_id];
  }
  return { text_fill, text_of };
})();
