// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const TIMING_COLUMN_NAMES = settings_("TIMING_COLUMN_NAMES");
  const TIMING_COLUMN_STRING_ID_PREFIX = settings_(
    "TIMING_COLUMN_STRING_ID_PREFIX",
  );

  const text = window.ui_strings_.text;
  const manifest_heading = document.getElementById(
    "overview-manifest-heading-",
  );
  const raw_data_heading = document.getElementById(
    "overview-raw-data-heading-",
  );
  const raw_data_link = document.querySelector("#overview-raw-data- > a");
  const tests_heading = document.getElementById("overview-tests-heading-");
  const tests_table_data = document.getElementById("overview-tests-table-");

  // Returns the tests table columns, both reports' alike.
  function tests_columns() {
    return [
      { label: text("str_column_report") },
      ...TIMING_COLUMN_NAMES.map((column_name) => ({
        label: text(TIMING_COLUMN_STRING_ID_PREFIX + column_name),
        numeric: true,
      })),
    ];
  }
  // Replaces table data with its table, answering each cell with a heat share.
  function table_data_replace(table_data, columns) {
    const table_rows = JSON.parse(table_data.getAttribute("data-rows-"));
    const table_element = window.render_element_of_(
      window.report_ui_.render_table(
        table_data.getAttribute("data-key-"),
        columns,
        table_rows,
        {
          cls: "overview-tests-table-",
          row_href: table_rows.map((table_row) => table_row[0].href),
        },
      ),
    );
    table_data.replaceWith(table_element);
    return table_rows.flatMap((table_row, row_index) =>
      table_row.flatMap((table_cell, column_index) =>
        table_cell.heat_percent === undefined
          ? []
          : [
              {
                cell_element:
                  table_element.tBodies[0].rows[row_index].cells[column_index],
                heat_percent: table_cell.heat_percent,
              },
            ],
      ),
    );
  }

  tests_heading.textContent = text("str_heading_tests");
  // A diff report holds no manifest heading or raw data.
  if (manifest_heading)
    manifest_heading.textContent = text("str_heading_manifest");
  if (raw_data_heading) {
    raw_data_heading.textContent = text("str_heading_raw_data");
    raw_data_link.textContent = raw_data_link
      .getAttribute("href")
      .split("/")
      .pop();
  }
  const heat_cells = table_data_replace(tests_table_data, tests_columns());

  // Writes each heat cell's colors on the chosen curve, every share a diff's.
  function heat_colors_apply() {
    const view_preferences = window.report_preferences_.now();
    const scale_choice = window.report_preferences_
      .heat_scale_choices()
      .find(
        (offered_choice) =>
          offered_choice.value === view_preferences.heat_scale_value,
      );
    if (!scale_choice) window.throw_exception_("str_error_internal");
    for (const heat_cell of heat_cells)
      heat_cell.cell_element.setAttribute(
        "style",
        window.report_ui_.heat_cell_style(
          heat_cell.heat_percent,
          scale_choice.curve,
          true,
        ),
      );
  }

  window.report_overview_ = { heat_colors_apply };
})();
