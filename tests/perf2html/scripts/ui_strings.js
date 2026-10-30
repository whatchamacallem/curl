// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.ui_strings_ = (function () {
  "use strict";
  const STRINGS = {
    str_caret_down: "▼",
    str_caret_right: "►",
    str_clip_ellipsis: "…",
    str_column_baseline_share: "vs baseline",
    str_column_branch_miss_ratio: "branch miss",
    str_column_call_count: "call count",
    str_column_called_at: "called at",
    str_column_callee: "callee",
    str_column_callees: "callees",
    str_column_caller: "caller",
    str_column_callers: "callers",
    str_column_calls: "calls",
    str_column_count: "count",
    str_column_counter: "counter",
    str_column_defined_at: "defined at",
    str_column_function: "function",
    str_column_instructions_per_cycle: "instructions/cycle",
    str_column_l1d_miss_ratio: "L1D miss",
    str_column_line: "line",
    str_column_loads_per_instruction: "loads/instruction",
    str_column_location: "location",
    str_column_report: "report",
    str_column_self: "self",
    str_column_source: "source",
    str_column_test_share: "test %",
    str_column_time_per_loop: "time/loop",
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
    str_counter_label: "{description} ({counter})",
    str_counter_llm: "last level cache misses, all",
    str_error_hash_file_missing: "url names line {0} but no file",
    str_error_hash_file_unknown:
      "url encodes a file this report never profiled: {0}",
    str_error_hash_function_conflicting:
      "url names function {0} together with a file or line",
    str_error_hash_function_unknown:
      "url encodes a function address this report never recorded: {0}",
    str_error_hash_heat_map_parts_missing:
      "heat map requires test and file or function",
    str_error_hash_line_unusable:
      "url encodes a line that is not a line number: {0}",
    str_error_hash_part_misplaced: "url part {0} is not one view {1} reads",
    str_error_hash_part_repeated: "url names {0} more than once",
    str_error_hash_part_unknown: "url part unrecognized: {0}",
    str_error_hash_profile_path_missing:
      "url names no local profile path, which the flame graph needs to start",
    str_error_hash_setting_unknown:
      "url encodes a setting this report does not have: {0}",
    str_error_hash_test_missing: "No test selected.",
    str_error_hash_test_unknown:
      "url encodes a test this report does not have: {0}",
    str_error_hash_value_empty: "url part {0} holds no value",
    str_error_hash_view_missing: "url names {0} but no view",
    str_error_hash_view_page_missing:
      "url encodes a view this diff report has no page for: {0}",
    str_error_hash_view_unknown:
      "url encodes a view this report does not have: {0}",
    str_error_held_script_unframed:
      "a view page opened outside the overview gets no settings to run under",
    str_error_internal: "internal error: halted and caught fire",
    str_error_report_incomplete:
      "report incomplete, scripts/debug.js not written.",
    str_error_screenshot_label_query_unusable:
      "the {0} query value came out as {1}, expected {2}",
    str_error_setting_choice_missing:
      "setting {0} leaves out a choice this report offers: {1}",
    str_error_setting_choice_repeated:
      "setting {0} names a choice more than once: {1}",
    str_error_setting_choice_unknown:
      "setting {0} names a choice this report does not offer: {1}",
    str_error_setting_unknown: "no such setting: {0}",
    str_error_settings_debug_query_unusable:
      "the {0} query value came out as {1}, expected {2} or {3}",
    str_error_settings_values_unusable:
      "url part {0} holds no object of setting values",
    str_error_strip_number_unusable:
      "no available strip entry is numbered {0}",
    str_flame_graph_page_title: "speedscope",
    str_function_list_cell_entry: "{function} ({share})",
    str_function_name_unknown: "?",
    str_heading_manifest: "manifest",
    str_heading_measure_diff: "change in {column}",
    str_heading_raw_data: "raw data",
    str_heading_sort_ascending: "ascending",
    str_heading_sort_descending: "descending",
    str_heading_tests: "tests",
    str_heat_map_main_label: "heat map view",
    str_heat_map_tree_label: "files",
    str_in_function: " in {function}",
    str_information_box_action_bar_separator: " | ",
    str_information_box_callees: "calls from this line (total {counter})",
    str_information_box_close: "close",
    str_information_box_close_symbol: "x",
    str_information_box_copy: "copy",
    str_information_box_function: "function",
    str_information_box_function_self: "{function}: self {self}.",
    str_information_box_function_totals:
      "{function} by call count: self {self}, total {total}.",
    str_information_line_link: "{path} self {share} info",
    str_line_self: "line self",
    str_load_log_asset_entry: "[{time}ms] {page} loaded {asset}",
    str_load_log_frame_entry:
      "[{time}ms] {page} long frame {span}ms, {render}ms rendering",
    str_load_log_input_entry:
      "[{time}ms] {page} {event} {target}, painted after {span}ms",
    str_load_log_load_entry: "[{time}ms] {page} load event",
    str_load_log_parse_entry:
      "[{time}ms] {page} parsed, {count} scripts loaded while parsing",
    str_load_log_render_entry:
      "[{time}ms] {page} {cause}, rendered after {span}ms",
    str_load_log_script_entry:
      "[{time}ms] {page} script {span}ms, {invoker}, {source}",
    str_load_log_script_function_entry:
      "[{time}ms] {page} script {span}ms, {invoker}, {function} in {source}",
    str_load_log_scripts_entry:
      "[{time}ms] {page} loaded {count} scripts in {span}ms, the last {asset}",
    str_location_cell: "{file}:{line}",
    str_menu_button: "{number} {label}",
    str_menu_counter_entry: "{mark}{label}",
    str_menu_counter_selected_mark: "◼ ",
    str_menu_counter_unselected_mark: "  ",
    str_menu_counters: "counters",
    str_menu_dark_mode_enabled: "dark",
    str_menu_file: "file",
    str_menu_function: "function",
    str_menu_help: "help",
    str_menu_light_mode: "light",
    str_menu_reset: "reset",
    str_menu_scale: "scale",
    str_menu_scale_cell_after_stop: "▓",
    str_menu_scale_cell_before_stop: "▒",
    str_menu_status_separator: " / ",
    str_menu_test: "test",
    str_no_caller: "(no recorded caller)",
    str_no_match: "(no match)",
    str_no_samples: "no samples",
    str_no_samples_in_test: "This test recorded no samples for {name}.",
    str_not_in_repo: "not in this repo ({path})",
    str_pulldown_drag_placeholder: "[search or drag]",
    str_pulldown_placeholder: "[search]",
    str_report_name: "perf2html",
    str_scale_curve_linear: "linear scale",
    str_scale_curve_log: "log scale",
    str_settings_apply: "apply",
    str_settings_copy: "copy",
    str_settings_debug_query: "{name}={value}",
    str_settings_load_log_history: "history: {count}",
    str_settings_paste: "paste",
    str_sort_alphabetical: "alphabetical",
    str_sort_hottest_first: "hottest first",
    str_source_beyond_end: "error: Line beyond end of file, source changed.",
    str_source_unavailable: "Source not available.",
    str_strip_gap: " ",
    str_table_heading_copy: "copy",
    str_text_scrollbar_chevron_down: "▼",
    str_text_scrollbar_chevron_left: "◄",
    str_text_scrollbar_chevron_right: "►",
    str_text_scrollbar_chevron_up: "▲",
    str_text_scrollbar_gutter: "▒",
    str_text_scrollbar_thumb: "▓",
    str_ticker_tape_entry: "{line} {share}",
    str_ticker_tape_heading_diff: "most changed lines",
    str_ticker_tape_heading_self: "hottest lines",
    str_title_part_separator: " / ",
    str_view_call_graph: "call graph",
    str_view_database: "database",
    str_view_flame_graph: "flame graph",
    str_view_heat_map: "heat map",
    str_view_overview: "overview",
    str_view_settings: "settings",
  };
  function text_fill(string_id, replacements) {
    const template = text(string_id);
    return template.replace(/\{(\w+)\}/g, (marker, field_name) => {
      if (!Object.prototype.hasOwnProperty.call(replacements, field_name))
        window.ui_error_throw_(`${string_id} ${marker}`);
      return String(replacements[field_name]);
    });
  }
  function text(string_id) {
    if (!Object.prototype.hasOwnProperty.call(STRINGS, string_id))
      window.ui_error_throw_(string_id);
    return STRINGS[string_id];
  }
  return { text_fill, text };
})();
