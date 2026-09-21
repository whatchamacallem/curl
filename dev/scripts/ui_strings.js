window.ui_strings = (function () {
  "use strict";
  const STRINGS = {
    str_caret_collapsed: "▶",
    str_caret_expanded: "▼",
    str_chip_heading_diff: "most changed lines",
    str_chip_heading_self: "hottest lines",
    str_column_call_count: "call count",
    str_column_called_at: "called at",
    str_column_callee: "callee",
    str_column_caller: "caller",
    str_column_calls: "calls",
    str_column_count: "count",
    str_column_defined_at: "defined at",
    str_column_event: "event",
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
    str_control_event: "event:",
    str_control_scale: "scale:",
    str_control_search: "search:",
    str_control_tree: "tree:",
    str_detail_close: "close",
    str_detail_close_symbol: "[X]",
    str_detail_copy: "copy",
    str_event_bc: "conditional branches executed",
    str_event_bcm: "conditional branches mispredicted",
    str_event_bi: "indirect branches executed",
    str_event_bim: "indirect branches mispredicted",
    str_event_bm: "branches mispredicted, all",
    str_event_cest: "cycle estimate",
    str_event_d1m: "L1 data cache misses",
    str_event_d1mr: "L1 data cache read misses",
    str_event_d1mw: "L1 data cache write misses",
    str_event_dlm: "last level data cache misses",
    str_event_dlmr: "last level data cache read misses",
    str_event_dlmw: "last level data cache write misses",
    str_event_dr: "data reads",
    str_event_dw: "data writes",
    str_event_i1mr: "L1 instruction cache misses",
    str_event_ilmr: "last level instruction cache misses",
    str_event_ir: "instructions executed",
    str_event_l1m: "L1 cache misses, all",
    str_event_llm: "last level cache misses, all",
    str_function_name_unknown: "?",
    str_heading_functions_by_self: "{prefix} functions by self {event}",
    str_heading_lines_by_event: "{prefix} lines by {event}",
    str_heading_prefix_diff: "Most changed",
    str_heading_prefix_self: "Hottest",
    str_in_function: " in {function}",
    str_line_self: "line self",
    str_no_caller: "(no recorded caller)",
    str_no_samples: "no samples",
    str_not_in_repo: "not in this repo ({path})",
    str_popup_callees: "calls from this line (total {event})",
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
    return Object.prototype.hasOwnProperty.call(STRINGS, string_id)
      ? STRINGS[string_id]
      : "(update ui_strings.js)";
  }
  return { text_fill, text_of };
})();
