// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const CALLERS_CELL_SEPARATOR_TEXT = settings_("CALLERS_CELL_SEPARATOR_TEXT");
  const CALLERS_TOP_FUNCTION_ROWS = settings_("CALLERS_TOP_FUNCTION_ROWS");
  const RANKING_COUNTER_NAME = settings_("RANKING_COUNTER_NAME");
  const STORAGE_KEY_CALLERS_ROWS = settings_("STORAGE_KEY_CALLERS_ROWS");
  const STYLE_TABLE_CALLERS_COLUMN_MAX_CHARS = settings_(
    "STYLE_TABLE_CALLERS_COLUMN_MAX_CHARS",
  );
  const STYLE_TABLE_FUNCTION_NAME_MAX_CHARS = settings_(
    "STYLE_TABLE_FUNCTION_NAME_MAX_CHARS",
  );
  const TABLE_ROW_COUNT_CHOICES = settings_("TABLE_ROW_COUNT_CHOICES");

  const text = window.ui_strings_.text;
  const text_fill = window.ui_strings_.text_fill;
  const render_element = window.render_element_;
  const render_html_escape = window.render_html_escape_;
  const table_sort_column = window.report_ui_.table_sort.column;
  const table_sort_records = window.report_ui_.table_sort.records;
  const CLIP_ELLIPSIS_TEXT = text("str_clip_ellipsis");
  const page_scroll_box = document.getElementById("callers-page-");
  const page_element = page_scroll_box.querySelector(":scope > .page-");
  const table_data = document.getElementById("callers-functions-table-");
  const is_diff = table_data.getAttribute("data-diff-") === "1";
  const callers_model = JSON.parse(table_data.getAttribute("data-model-"));
  const RENDERED_ROW_COUNT = Math.max(...TABLE_ROW_COUNT_CHOICES);
  const SORT_DEFAULT_NAME = "calls";
  const count_text = is_diff
    ? window.report_ui_.signed_human_text
    : window.report_ui_.human_text;
  const share_text = is_diff
    ? window.report_ui_.signed_percent_text
    : window.report_ui_.percent_text;
  let shown_counter_indexes = null,
    shows_calls = null,
    heat_curve_name = null,
    rendered_preferences_text = null,
    sort_name = SORT_DEFAULT_NAME;

  // Answers a function the model names, with its heat map address or none.
  function function_link(function_index) {
    const function_entry = callers_model.functions[function_index];
    return { name: function_entry[0], href: function_entry[1] };
  }
  // Reads one caller of a listed function, a diff's baseline calls last.
  function caller(caller_row) {
    return {
      ...function_link(caller_row[0]),
      calls: caller_row[1],
      baseline_calls: caller_row[2],
    };
  }
  // Reads one listed function from its row, a diff's baselines last in it.
  function record(callee_row) {
    return {
      ...function_link(callee_row[0]),
      calls: callee_row[1],
      values: callee_row[2],
      callers: callee_row[3].map(caller),
      baseline_calls: callee_row[4],
      baseline_values: callee_row[5],
    };
  }
  const function_records = callers_model.callees.map(record);
  const calls_total = function_records.reduce(
    (running_total, record) => running_total + record.calls,
    0,
  );

  // Answers the share of all calls a count is, a diff's its change.
  function calls_share(calls, baseline_calls) {
    if (is_diff) return window.report_ui_.diff_share(calls, baseline_calls);
    return (100 * calls) / calls_total;
  }
  // Answers the share of a counter a function holds, a diff's its change.
  function counter_share(record, counter_index) {
    const value = record.values[counter_index];
    if (is_diff)
      return window.report_ui_.diff_share(
        value,
        record.baseline_values[counter_index],
      );
    return value
      ? (100 * value) / callers_model.counterTotals[counter_index]
      : 0;
  }
  // Writes the heat colors of a cell by its share, on the chosen curve.
  const heat_style = (percent) =>
    window.report_ui_.heat_cell_style(percent, heat_curve_name, is_diff);
  const share_cell = (percent) => ({
    text: share_text(percent),
    style: heat_style(percent),
  });

  // Lists each caller with its share of calls, linked, cut at the limit.
  function callers_cell(record) {
    const caller_labels = record.callers.map((caller) =>
      text_fill("str_callers_cell_entry", {
        function: caller.name,
        share: share_text(
          calls_share(caller.calls, caller.baseline_calls),
          true,
        ),
      }),
    );
    const separator_markup = render_html_escape(CALLERS_CELL_SEPARATOR_TEXT);
    const shown_markups = [];
    let shown_text = "";
    for (const [caller_index, caller] of record.callers.entries()) {
      const label_text = caller_labels[caller_index];
      const next_text = shown_text
        ? shown_text + CALLERS_CELL_SEPARATOR_TEXT + label_text
        : label_text;
      if (
        shown_text &&
        next_text.length > STYLE_TABLE_CALLERS_COLUMN_MAX_CHARS
      )
        break;
      shown_text = next_text;
      const label_markup = render_html_escape(label_text);
      shown_markups.push(
        caller.href
          ? render_element("a", { href: caller.href }, label_markup)
          : label_markup,
      );
    }
    if (shown_markups.length < record.callers.length)
      shown_markups.push(render_html_escape(CLIP_ELLIPSIS_TEXT));
    return {
      text: caller_labels.join(CALLERS_CELL_SEPARATOR_TEXT),
      html: shown_markups.join(separator_markup),
    };
  }
  const RANK_COLUMN = table_sort_column(
    { label: text("str_column_rank"), numeric: true },
    "",
    null,
    (record, row_index) => String(row_index + 1),
  );
  const SYMBOL_COLUMN = table_sort_column(
    {
      label: text("str_column_symbol"),
      clip: STYLE_TABLE_FUNCTION_NAME_MAX_CHARS,
    },
    "symbol",
    (record) => record.name,
    (record) => ({ text: record.name, href: record.href }),
  );
  const CALLS_COLUMN = table_sort_column(
    { label: text("str_column_calls"), numeric: true },
    SORT_DEFAULT_NAME,
    (record) => Math.abs(record.calls),
    (record) => ({
      text: count_text(record.calls),
      style: heat_style(calls_share(record.calls, record.baseline_calls)),
    }),
  );
  const CALLERS_COLUMN = table_sort_column(
    { label: text("str_column_callers") },
    "callers",
    (record) => callers_cell(record).text,
    callers_cell,
  );
  // Makes the column of one chosen counter, its shares heat colored.
  function counter_column(counter_index) {
    const counter_name = callers_model.counterNames[counter_index];
    return table_sort_column(
      {
        label: counter_name,
        measure: window.report_preferences_.counter_label(counter_name),
        numeric: true,
      },
      counter_name,
      (record) => Math.abs(record.values[counter_index]),
      (record) => share_cell(counter_share(record, counter_index)),
    );
  }

  // Answers where a counter's values sit in each function's row.
  function counter_index(counter_name) {
    const found_index = callers_model.counterNames.indexOf(counter_name);
    if (found_index < 0) window.throw_exception_("str_error_internal");
    return found_index;
  }
  // Takes the relayed preferences: the calls and counter columns, the curve.
  function preferences_handler() {
    const view_preferences = window.report_preferences_.now();
    const counter_names = view_preferences.counter_names;
    shown_counter_indexes = counter_names.map(counter_index);
    shows_calls = view_preferences.shows_calls;
    const scale_choices =
      window.report_preferences_.heat_scale_choices(is_diff);
    const scale_choice = scale_choices.find(
      (choice) => choice.value === view_preferences.heat_scale_value,
    );
    if (!scale_choice) window.throw_exception_("str_error_internal");
    heat_curve_name = scale_choice.curve;
  }
  // Draws the heading and the table by the chosen sort, the row count kept.
  function table_render() {
    const sort_columns = [
      RANK_COLUMN,
      SYMBOL_COLUMN,
      ...(shows_calls ? [CALLS_COLUMN] : []),
      ...shown_counter_indexes.map(counter_column),
      CALLERS_COLUMN,
    ];
    const column_named = (column_sort_name) =>
      sort_columns.find(
        (sort_column) => sort_column.sort_name === column_sort_name,
      );
    // A sort whose column left the table, a counter unselected, resets.
    if (!column_named(sort_name)) sort_name = SORT_DEFAULT_NAME;
    // With calls hidden the default sort is by the ranking counter.
    const sorted_column = column_named(
      sort_name === SORT_DEFAULT_NAME && !shows_calls
        ? RANKING_COUNTER_NAME
        : sort_name,
    );
    const shown_records = table_sort_records(
      table_sort_records(function_records, CALLS_COLUMN),
      sorted_column,
    ).slice(0, RENDERED_ROW_COUNT);
    const heading_markup = render_element(
      "div",
      {
        class: "page-heading-",
        "data-row-count-key-": STORAGE_KEY_CALLERS_ROWS,
      },
      window.report_ui_.table_sort.heading_markup(
        "str_heading_functions_by_counter",
        CALLERS_TOP_FUNCTION_ROWS,
        sorted_column,
        is_diff,
      ),
    );
    const table_markup = window.report_ui_.render_table(
      table_data.getAttribute("data-key-"),
      sort_columns.map((sort_column) => sort_column.column),
      shown_records.map((record, row_index) =>
        sort_columns.map((sort_column) => sort_column.cell(record, row_index)),
      ),
      {
        on_sort: (column_index) => sort_choose(sort_columns[column_index]),
        sorted_column_index: sort_columns.indexOf(sorted_column),
      },
    );
    page_element.innerHTML = heading_markup + table_markup;
    window.report_ui_.layout_activate(page_element);
  }
  // Sorts the table by a column, the rank column restoring the default.
  function sort_choose(sort_column) {
    sort_name = sort_column.sort_value
      ? sort_column.sort_name
      : SORT_DEFAULT_NAME;
    table_render();
  }
  // Draws the table again when the relayed preferences change what it shows.
  function preferences_apply() {
    preferences_handler();
    const preferences_text = JSON.stringify([
      shown_counter_indexes,
      shows_calls,
      heat_curve_name,
    ]);
    if (preferences_text === rendered_preferences_text) return;
    rendered_preferences_text = preferences_text;
    table_render();
  }
  // Takes a relayed message, drawing again when its preferences changed.
  function relay_handler(message_data) {
    if (window.report_preferences_.relay_handler(message_data))
      preferences_apply();
  }
  // Shows the page from its top when its address is followed again.
  function page_top_show() {
    page_scroll_box.scrollTo(0, 0);
  }

  window.report_ui_.view_activate({
    dark_mode_apply: null,
    forwards_input: true,
    recenter: page_top_show,
    relay_handler,
  });
})();
