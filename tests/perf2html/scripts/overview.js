// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const RANKING_COUNTER_NAME = settings_("RANKING_COUNTER_NAME");

  const text = window.ui_strings_.text;
  const text_fill = window.ui_strings_.text_fill;
  const manifest_heading = document.getElementById(
    "overview-manifest-heading-",
  );
  const raw_data_link = document.querySelector("#overview-raw-data- > a");
  const tests_heading = document.getElementById("overview-tests-heading-");
  const tests_table_data = document.getElementById("overview-tests-table-");

  // Answers the tests table columns, a diff's naming the ranking counter.
  function tests_columns() {
    if (tests_table_data.getAttribute("data-diff-") === "1")
      return [
        { label: text("str_column_report_per_test") },
        { label: RANKING_COUNTER_NAME, numeric: true },
        { label: text("str_column_change_share"), numeric: true },
        {
          label: text_fill("str_column_functions_changed", {
            counter: RANKING_COUNTER_NAME,
          }),
          numeric: true,
        },
      ];
    const column_labels = JSON.parse(
      tests_table_data.getAttribute("data-column-labels-"),
    );
    return [
      { label: text("str_column_report") },
      ...column_labels.map((column_label) => ({
        label: column_label,
        numeric: true,
      })),
    ];
  }
  // Replaces table data with its table, each row leading to its first link.
  function table_data_replace(table_data, columns) {
    const table_rows = JSON.parse(table_data.getAttribute("data-rows-"));
    table_data.replaceWith(
      window.render_element_of_(
        window.report_ui_.render_table(
          table_data.getAttribute("data-key-"),
          columns,
          table_rows,
          { row_href: table_rows.map((table_row) => table_row[0].href) },
        ),
      ),
    );
  }

  tests_heading.textContent = text("str_heading_tests");
  window.report_ui_.view_frame.setAttribute(
    "title",
    text("str_view_frame_title"),
  );
  // A diff report holds no manifest heading or raw data.
  if (manifest_heading)
    manifest_heading.textContent = text("str_heading_manifest");
  if (raw_data_link)
    raw_data_link.textContent = text_fill("str_raw_data_link", {
      name: raw_data_link.getAttribute("href").split("/").pop(),
    });
  table_data_replace(tests_table_data, tests_columns());
})();
