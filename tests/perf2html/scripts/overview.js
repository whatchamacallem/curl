// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const RANKING_COUNTER_NAME = settings_("RANKING_COUNTER_NAME");

  const MANIFEST_TABLE_COLUMNS = [{ label: "" }, { label: "", grow: true }];
  const OPTIONAL_SLOT_STRING_IDS = {
    "#overview-collapsed-section-perf-log- > summary": "str_section_perf_log",
    "#overview-collapsed-section-trace-log- > summary":
      "str_section_trace_log",
    "#overview-collapsed-section-valgrind-log- > summary":
      "str_section_valgrind_log",
    "#overview-manifest-heading-": "str_heading_manifest",
  };

  const text_of = window.ui_strings_.text_of;
  const text_fill = window.ui_strings_.text_fill;
  const raw_data_link = document.querySelector("#overview-raw-data- > a");
  const tests_heading = document.getElementById("overview-tests-heading-");
  const tests_table_data = document.getElementById("overview-tests-table-");
  const title_heading = document.getElementById("overview-title-heading-");

  // Answers the tests table columns, a diff's naming the ranking counter.
  function tests_columns_of() {
    if (tests_table_data.getAttribute("data-diff-") === "1")
      return [
        { label: text_of("str_column_report_per_test") },
        { label: RANKING_COUNTER_NAME, numeric: true },
        { label: text_of("str_column_change_share"), numeric: true },
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
      { label: text_of("str_column_report") },
      ...column_labels.map((column_label) => ({
        label: column_label,
        numeric: true,
      })),
    ];
  }
  // Replaces the rows a table data element holds with the table drawn of them.
  function table_data_replace(table_data, columns, table_options) {
    table_data.replaceWith(
      window.render_element_of_(
        window.report_ui_.render_table(
          table_data.getAttribute("data-key-"),
          columns,
          JSON.parse(table_data.getAttribute("data-rows-")),
          table_options,
        ),
      ),
    );
  }

  title_heading.textContent = text_of("str_view_overview");
  tests_heading.textContent = text_of("str_heading_tests");
  window.report_ui_.view_frame.setAttribute(
    "title",
    text_of("str_view_frame_title"),
  );
  // A diff report holds no manifest heading, raw data or log section.
  for (const [slot_selector, string_id] of Object.entries(
    OPTIONAL_SLOT_STRING_IDS,
  )) {
    const slot_element = document.querySelector(slot_selector);
    if (slot_element) slot_element.textContent = text_of(string_id);
  }
  if (raw_data_link)
    raw_data_link.textContent = text_fill("str_raw_data_link", {
      name: raw_data_link.getAttribute("href").split("/").pop(),
    });
  table_data_replace(tests_table_data, tests_columns_of(), {});
  for (const table_data of document.querySelectorAll(
    ".overview-manifest-table-",
  ))
    table_data_replace(table_data, MANIFEST_TABLE_COLUMNS, {
      fill: true,
      omits_column_titles: true,
    });
})();
