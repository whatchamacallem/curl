window.ui_strings = (function () {
  "use strict";
  const STRINGS = {
    str_caret_collapsed: "▶",
    str_caret_expanded: "▼",
    str_chip_heading_diff: "most changed lines",
    str_chip_heading_self: "hottest lines",
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
    str_control_counter: "counter:",
    str_control_scale: "scale:",
    str_control_search: "search:",
    str_control_view_scale: "scale:",
    str_control_tree: "tree:",
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
    str_detail_close: "close",
    str_detail_close_symbol: "[X]",
    str_detail_copy: "copy",
    str_error_callstack_unavailable: "(no callstack recorded)",
    str_error_column_frame: "frame",
    str_error_column_label: "label",
    str_error_column_location: "location",
    str_error_column_value: "value",
    str_error_control_copy: "copy",
    str_error_control_reload: "reload",
    str_error_control_restart: "restart",
    str_error_counter_unknown: "this report has no column for counter {0}",
    str_error_flame_graph_never_started:
      "flame graph viewer did not start within {0}s",
    str_error_font_refused:
      "the browser refused the page font",
    str_error_hash_counter_unknown:
      "url encodes counter this report has no column for: {0}",
    str_error_hash_file_unknown:
      "url encodes a file this report has no source for: {0}",
    str_error_hash_function_unknown:
      "url encodes a function address this report never recorded: {0}",
    str_error_hash_part_unknown: "url part unrecognized: {0}",
    str_error_hash_view_unknown:
      "url encodes a view this report does not have: {0}",
    str_error_heading_address: "address",
    str_error_heading_callstack: "callstack",
    str_error_heading_manifest: "manifest",
    str_error_manifest_unavailable: "MANIFEST.txt not found",
    str_error_page_heading: "perf2html error",
    str_error_page_title: "perf2html error page",
    str_error_scale_ends_disordered:
      "DESIGN_SCALE_* out of order: smallest {0}, default {1}, largest {2}",
    str_error_scale_multiple_outside: "scale multiple {0} is outside {1}..{2}",
    str_error_scale_unusable: "the page scale came out as {0}",
    str_error_source_address: "bad address",
    str_error_source_exception: "uncaught exception",
    str_error_source_rejection: "internal error",
    str_error_test_menu_focus_refused:
      "the browser kept focus on {0}, so keys cannot reach the test menu",
    str_function_name_unknown: "?",
    str_heading_functions_by_self: "{prefix} functions by self {counter}",
    str_heading_lines_by_counter: "{prefix} lines by {counter}",
    str_heading_prefix_diff: "Most changed",
    str_heading_prefix_self: "Hottest",
    str_in_function: " in {function}",
    str_line_self: "line self",
    str_no_caller: "(no recorded caller)",
    str_no_match: "(no match)",
    str_no_samples: "no samples",
    str_not_in_repo: "not in this repo ({path})",
    str_popup_callees: "calls from this line (total {counter})",
    str_popup_function_self: "{function}: self {self}.",
    str_popup_function_totals:
      "{function} by call count: self {self}, total {total}.",
    str_report_name: "perf2html",
    str_scale_curve_linear: "linear",
    str_scale_curve_log: "log",
    str_scale_entry: "{curve}, {scope}",
    str_scope_file: "per file",
    str_scope_function: "per function",
    str_scope_global: "global",
    str_scope_line: "per line",
    str_search_placeholder: "file name…",
    str_share_zero: "0%",
    str_sort_by_heat: "by heat",
    str_sort_by_name: "by name",
    str_source_beyond_end:
      "(line beyond end of file: source changed since the profile was" +
      " taken)",
    str_source_unavailable: "Source not available.",
    str_view_summary: "summary",
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
  function text_over_args(string_id, args) {
    const template = text_of(string_id);
    let every_marker_filled = true;
    const filled = template.replace(/\{(\d+)\}/g, (marker, index_text) => {
      const index = Number(index_text);
      if (index >= args.length) {
        every_marker_filled = false;
        return marker;
      }
      return String(args[index]);
    });
    return every_marker_filled ? filled : null;
  }
  return { text_fill, text_of, text_over_args };
})();
