// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const COUNTER_LIST_CALLEES_LINE_NAME = settings_(
    "COUNTER_LIST_CALLEES_LINE_NAME",
  );
  const COUNTER_LIST_CALLERS_LINE_NAME = settings_(
    "COUNTER_LIST_CALLERS_LINE_NAME",
  );
  const COUNTER_LIST_CALLS_LINE_NAME = settings_(
    "COUNTER_LIST_CALLS_LINE_NAME",
  );
  const DATABASE_TOP_FUNCTION_ROWS = settings_("DATABASE_TOP_FUNCTION_ROWS");
  const DATABASE_VIEW_KEY = settings_("DATABASE_VIEW_KEY");
  const STORAGE_KEY_DATABASE_FUNCTION_ROWS = settings_(
    "STORAGE_KEY_DATABASE_FUNCTION_ROWS",
  );
  const STYLE_TABLE_FUNCTION_LIST_COLUMN_MAX_CHARS = settings_(
    "STYLE_TABLE_FUNCTION_LIST_COLUMN_MAX_CHARS",
  );
  const STYLE_TABLE_FUNCTION_NAME_MAX_CHARS = settings_(
    "STYLE_TABLE_FUNCTION_NAME_MAX_CHARS",
  );
  const STYLE_TABLE_LOCATION_COLUMN_MAX_CHARS = settings_(
    "STYLE_TABLE_LOCATION_COLUMN_MAX_CHARS",
  );
  const TABLE_ROW_COUNT_CHOICES = settings_("TABLE_ROW_COUNT_CHOICES");

  const text = window.ui_strings_.text;
  const render_element = window.render_element_;
  const line_column = window.report_preferences_.line_column;
  const table_sort_column = window.report_ui_.table_sort.column;
  const table_sort_records = window.report_ui_.table_sort.records;
  const page_scroll_box = document.getElementById("database-page-");
  const page_element = page_scroll_box.querySelector(":scope > .page-");
  const model_data = document.getElementById("database-model-");
  const is_diff = model_data.getAttribute("data-diff-") === "1";
  const database_model = JSON.parse(model_data.getAttribute("data-model-"));
  const counter_readers = window.report_preferences_.counter_readers(
    database_model.counterNames,
    database_model.derivedCounters,
  );
  const RENDERED_ROW_COUNT = Math.max(...TABLE_ROW_COUNT_CHOICES);
  const FUNCTIONS_TABLE_KEY = "database.functions";
  const count_text = is_diff
    ? window.report_ui_.signed_human_text
    : window.report_ui_.human_text;
  const share_text = is_diff
    ? window.report_ui_.signed_percent_text
    : window.report_ui_.percent_text;
  let shown_line_columns = null,
    heat_curve_name = null,
    rendered_preferences_text = null,
    chosen_sort_name = "",
    chosen_sort_direction = "",
    pressed_sort_name = null;

  // Returns a function the model names, with its heat map address or none.
  function function_link(function_index) {
    const function_entry = database_model.functions[function_index];
    return { name: function_entry[0], href: function_entry[1] };
  }
  // Reads one caller or callee of a listed function, a diff's baseline last.
  function call_record(call_row) {
    return {
      ...function_link(call_row[0]),
      calls: call_row[1],
      baseline_calls: call_row[2],
    };
  }
  // Reads one listed function from its row, a diff's baselines last in it.
  function function_record(function_row) {
    return {
      ...function_link(function_row[0]),
      file: function_row[1],
      line: function_row[2],
      calls: function_row[3],
      values: function_row[4],
      callers: function_row[5].map(call_record),
      callees: function_row[6].map(call_record),
      baseline_calls: function_row[7],
      baseline_values: function_row[8],
    };
  }
  const function_records = database_model.functionRows.map(function_record);
  const calls_total = function_records.reduce(
    (running_total, record) => running_total + record.calls,
    0,
  );

  // Returns the share of all calls a count is, a diff's its change.
  function calls_share(calls, baseline_calls) {
    if (is_diff) return window.report_ui_.diff_share(calls, baseline_calls);
    return (100 * calls) / calls_total;
  }
  // Returns the share of its test total a counter holds, a diff's its change.
  function counter_share(record, counter_reader) {
    const value = counter_reader.get(record.values);
    if (is_diff)
      return window.report_ui_.diff_share(
        value,
        counter_reader.get(record.baseline_values),
      );
    return value
      ? (100 * value) / counter_reader.get(database_model.counterTotals)
      : 0;
  }
  // Writes the heat colors of a cell by its share, on the chosen curve.
  const heat_style = (percent) =>
    window.report_ui_.heat_cell_style(percent, heat_curve_name, is_diff);
  const share_cell = (percent) => ({
    text: share_text(percent),
    style: heat_style(percent),
  });

  // Writes the callers or the callees of a function, each by its call share.
  function function_list_cell(call_records, clip_chars) {
    return window.report_ui_.function_list_cell(
      call_records.map((call_record) => ({
        name: call_record.name,
        href: call_record.href,
        share_text: share_text(
          calls_share(call_record.calls, call_record.baseline_calls),
          false,
        ),
      })),
      clip_chars,
    );
  }
  // Makes the column listing the callers or the callees of each function.
  function function_list_column(line_name, call_records_of) {
    const cell = (record, clip_chars) =>
      function_list_cell(call_records_of(record), clip_chars);
    return table_sort_column({
      column: {
        ...line_column(line_name),
        clip: STYLE_TABLE_FUNCTION_LIST_COLUMN_MAX_CHARS,
      },
      sort_name: line_name,
      sort_value: (record) =>
        cell(record, STYLE_TABLE_FUNCTION_LIST_COLUMN_MAX_CHARS).text,
      cell,
      first_direction: "descending",
    });
  }
  const FUNCTION_COLUMN = table_sort_column({
    column: {
      label: text("str_column_function"),
      clip: STYLE_TABLE_FUNCTION_NAME_MAX_CHARS,
    },
    sort_name: "function",
    sort_value: (record) => record.name,
    cell: (record) => ({ text: record.name, href: record.href }),
    first_direction: "ascending",
  });
  const FILE_COLUMN = table_sort_column({
    column: {
      label: text("str_column_file"),
      clip: STYLE_TABLE_LOCATION_COLUMN_MAX_CHARS,
    },
    sort_name: "file",
    sort_value: (record) => record.file,
    cell: (record) => ({ text: record.file }),
    first_direction: "ascending",
  });
  const LINE_COLUMN = table_sort_column({
    column: { label: text("str_column_line"), numeric: true },
    sort_name: "line",
    sort_value: (record) => record.line,
    cell: (record) => ({ text: record.line ? String(record.line) : "" }),
    first_direction: "ascending",
  });
  // Holds the columns each row draws first, none a line of the counters list.
  const FIXED_COLUMNS = [FUNCTION_COLUMN, FILE_COLUMN, LINE_COLUMN];
  // Holds the column of each line of calls, by its line name.
  const CALL_LINE_COLUMNS = {
    [COUNTER_LIST_CALLEES_LINE_NAME]: function_list_column(
      COUNTER_LIST_CALLEES_LINE_NAME,
      (record) => record.callees,
    ),
    [COUNTER_LIST_CALLERS_LINE_NAME]: function_list_column(
      COUNTER_LIST_CALLERS_LINE_NAME,
      (record) => record.callers,
    ),
    [COUNTER_LIST_CALLS_LINE_NAME]: table_sort_column({
      column: line_column(COUNTER_LIST_CALLS_LINE_NAME),
      sort_name: COUNTER_LIST_CALLS_LINE_NAME,
      sort_value: (record) => Math.abs(record.calls),
      cell: (record) => ({
        text: count_text(record.calls),
        style: heat_style(calls_share(record.calls, record.baseline_calls)),
      }),
      first_direction: "descending",
    }),
  };
  // Makes the column of one shown counter, its shares heat colored.
  function counter_column(counter_name) {
    const counter_reader = counter_readers.find(
      (listed_reader) => listed_reader.key === counter_name,
    );
    if (!counter_reader) window.throw_exception_("str_error_internal");
    return table_sort_column({
      column: line_column(counter_name),
      sort_name: counter_name,
      sort_value: (record) => Math.abs(counter_reader.get(record.values)),
      cell: (record) => share_cell(counter_share(record, counter_reader)),
      first_direction: "descending",
    });
  }

  // Takes the relayed preferences: the database list's shown lines and curve.
  function preferences_handler() {
    const view_preferences = window.report_preferences_.now();
    shown_line_columns = window.report_preferences_.shown_line_parts(
      DATABASE_VIEW_KEY,
      counter_column,
      CALL_LINE_COLUMNS,
    );
    const scale_choices = window.report_preferences_.heat_scale_choices();
    const scale_choice = scale_choices.find(
      (choice) => choice.value === view_preferences.heat_scale_value,
    );
    if (!scale_choice) window.throw_exception_("str_error_internal");
    heat_curve_name = scale_choice.curve;
  }
  // Returns the sort column: the one chosen, else the first numeric line's.
  function sorted_column_find(sort_columns) {
    const chosen_column = sort_columns.find(
      (sort_column) => sort_column.sort_name === chosen_sort_name,
    );
    if (chosen_column) return chosen_column;
    const first_column =
      shown_line_columns.find((sort_column) => sort_column.column.numeric) ||
      FUNCTION_COLUMN;
    // A sort whose column left the table, a line hidden, starts again.
    chosen_sort_name = "";
    chosen_sort_direction = first_column.first_direction;
    return first_column;
  }
  // Draws the table under its heading by its sort, each row linked.
  function page_render() {
    const sort_columns = [...FIXED_COLUMNS, ...shown_line_columns];
    const sorted_column = sorted_column_find(sort_columns);
    const shown_records = table_sort_records(
      function_records,
      sorted_column,
      chosen_sort_direction,
    ).slice(0, RENDERED_ROW_COUNT);
    const heading_markup = render_element(
      "div",
      {
        class: "page-heading-",
        "data-row-count-default-": String(DATABASE_TOP_FUNCTION_ROWS),
        "data-row-count-key-": STORAGE_KEY_DATABASE_FUNCTION_ROWS,
      },
      "",
    );
    const table_markup = window.report_ui_.render_record_table(
      FUNCTIONS_TABLE_KEY,
      sort_columns,
      shown_records,
      {
        counter_list_key: DATABASE_VIEW_KEY,
        heading_entries: window.report_ui_.table_sort.heading_entries({
          order_choices:
            window.report_preferences_.sort_order_choices(DATABASE_VIEW_KEY),
          sorted_column,
          sort_direction: chosen_sort_direction,
          is_diff,
          on_column_choose: column_choose,
          on_direction_choose: (sort_direction) =>
            sort_choose(sorted_column.sort_name, sort_direction),
        }),
        on_clip_change: page_render,
        on_sort: (column_index) => title_press(sort_columns[column_index]),
        row_href: shown_records.map((record) => record.href),
        sort_direction: chosen_sort_direction,
        sorted_column_index: sort_columns.indexOf(sorted_column),
      },
    );
    window.report_ui_.layout_replace(
      page_element,
      heading_markup + table_markup,
    );
  }
  // Sorts the table by a column in a direction, then draws the table again.
  function sort_choose(sort_name, sort_direction) {
    chosen_sort_name = sort_name;
    chosen_sort_direction = sort_direction;
    page_render();
  }
  // Sorts by a column the sort order pulldown chose, no title pressed last.
  function column_choose(sort_name) {
    pressed_sort_name = null;
    sort_choose(sort_name, chosen_sort_direction);
  }
  // Sorts by a pressed column title, a second press in a row reversing.
  function title_press(pressed_column) {
    const sort_direction = window.report_ui_.table_sort.pressed_direction(
      pressed_column,
      pressed_sort_name,
      chosen_sort_direction,
    );
    pressed_sort_name = pressed_column.sort_name;
    sort_choose(pressed_column.sort_name, sort_direction);
  }
  // Draws the table again when the relayed preferences change what it shows.
  function preferences_apply() {
    preferences_handler();
    const preferences_text = JSON.stringify([
      window.report_preferences_.shown_line_names(DATABASE_VIEW_KEY),
      heat_curve_name,
    ]);
    if (preferences_text === rendered_preferences_text) return;
    rendered_preferences_text = preferences_text;
    page_render();
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
    forwards_input: true,
    recenter: page_top_show,
    relay_handler,
  });
})();
