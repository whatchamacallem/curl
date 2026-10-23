// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const RANKING_COUNTER_NAME = settings_("RANKING_COUNTER_NAME");
  const TIMING_COLUMN_STRING_ID_PREFIX = settings_(
    "TIMING_COLUMN_STRING_ID_PREFIX",
  );
  const TIMING_COUNTER_RATIOS = settings_("TIMING_COUNTER_RATIOS");
  const TIMING_PERF_STAT_METRICS = settings_("TIMING_PERF_STAT_METRICS");
  const TIMING_TIME_PER_LOOP_NAME = settings_("TIMING_TIME_PER_LOOP_NAME");

  const text = window.ui_strings_.text;
  const text_fill = window.ui_strings_.text_fill;
  const manifest_heading = document.getElementById(
    "overview-manifest-heading-",
  );
  const raw_data_heading = document.getElementById(
    "overview-raw-data-heading-",
  );
  const raw_data_link = document.querySelector("#overview-raw-data- > a");
  const tests_heading = document.getElementById("overview-tests-heading-");
  const tests_table_data = document.getElementById("overview-tests-table-");

  // Returns the tests table columns, a diff's naming the ranking counter.
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
    return [
      { label: text("str_column_report") },
      ...[
        TIMING_TIME_PER_LOOP_NAME,
        ...TIMING_PERF_STAT_METRICS.map(([metric_name]) => metric_name),
        ...TIMING_COUNTER_RATIOS.map(([ratio_name]) => ratio_name),
      ].map((timing_name) => ({
        label: text(TIMING_COLUMN_STRING_ID_PREFIX + timing_name),
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
  table_data_replace(tests_table_data, tests_columns());
})();
