// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const CALLERS_TOP_FUNCTION_ROWS = settings_("CALLERS_TOP_FUNCTION_ROWS");
  const STORAGE_KEY_CALLERS_ROWS = settings_("STORAGE_KEY_CALLERS_ROWS");
  const STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS = settings_(
    "STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS",
  );

  const text_of = window.ui_strings_.text_of;
  const text_fill = window.ui_strings_.text_fill;
  const render_element = window.render_element_;
  const render_html_escape = window.render_html_escape_;
  const page_scroll_box = document.querySelector("main.page-text-scroll-box-");
  const page_element = page_scroll_box.querySelector(":scope > .page-");
  const table_data = document.getElementById("callers-functions-table-");
  const is_diff = table_data.getAttribute("data-diff-") === "1";

  // Writes the functions table heading, its row count a span.
  function heading_markup_of() {
    const row_count_markup = render_element(
      "span",
      { class: "page-heading-row-count-" },
      String(CALLERS_TOP_FUNCTION_ROWS),
    );
    const measure_text = text_of(
      is_diff ? "str_heading_measure_calls_diff" : "str_heading_measure_calls",
    );
    return render_element(
      "div",
      {
        class: "page-heading-",
        "data-row-count-key-": STORAGE_KEY_CALLERS_ROWS,
      },
      text_fill("str_heading_functions_by_counter", {
        count: row_count_markup,
        measure: render_html_escape(measure_text),
      }),
    );
  }
  function table_markup_of() {
    return window.report_ui_.render_table(
      table_data.getAttribute("data-key-"),
      [
        { label: text_of("str_column_rank"), numeric: true },
        {
          label: text_of("str_column_symbol"),
          width: STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS,
        },
        { label: text_of("str_column_calls"), numeric: true },
        { label: text_of("str_column_callers"), grow: true },
      ],
      JSON.parse(table_data.getAttribute("data-rows-")),
      { fill: true },
    );
  }
  // Shows the page from its top when its address is followed again.
  function page_top_show() {
    page_scroll_box.scrollTo(0, 0);
  }

  page_element.innerHTML = heading_markup_of() + table_markup_of();
  window.report_ui_.layout_activate(page_element);
  window.report_ui_.view_activate({
    dark_mode_apply: null,
    forwards_input: true,
    preferences_apply: null,
    recenter: page_top_show,
  });
})();
