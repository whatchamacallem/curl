// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.catch_show_throw_(function () {
  "use strict";

  const HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX = settings_(
    "HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX",
  );
  const HEAT_MAP_HOME_LINES_LOCATION_MAX_CHARS = settings_(
    "HEAT_MAP_HOME_LINES_LOCATION_MAX_CHARS",
  );
  const HEAT_MAP_HOME_LINES_SOURCE_COLUMN_MAX_CHARS = settings_(
    "HEAT_MAP_HOME_LINES_SOURCE_COLUMN_MAX_CHARS",
  );
  const HEAT_MAP_HOME_LINES_SOURCE_SNIPPET_MAX_CHARS = settings_(
    "HEAT_MAP_HOME_LINES_SOURCE_SNIPPET_MAX_CHARS",
  );
  const HEAT_MAP_HOME_TABLE_DEFAULT_ROWS = settings_(
    "HEAT_MAP_HOME_TABLE_DEFAULT_ROWS",
  );
  const HEAT_MAP_MINIMAP_SOURCE_WIDTH_CHARS = settings_(
    "HEAT_MAP_MINIMAP_SOURCE_WIDTH_CHARS",
  );
  const HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX = settings_(
    "HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX",
  );
  const HEAT_MAP_MODEL_DIR_NAME = settings_("HEAT_MAP_MODEL_DIR_NAME");
  const HEAT_MAP_MODEL_GLOBAL_NAME = settings_("HEAT_MAP_MODEL_GLOBAL_NAME");
  const HEAT_MAP_SECONDARY_COUNTER_NAMES = settings_(
    "HEAT_MAP_SECONDARY_COUNTER_NAMES",
  );
  const HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_LEAST_SHARE = settings_(
    "HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_LEAST_SHARE",
  );
  const HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_MAX_COUNT = settings_(
    "HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_MAX_COUNT",
  );
  const HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS = settings_(
    "HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS",
  );
  const HEAT_MAP_TREE_AUTO_EXPAND_ABOVE_SHARE = settings_(
    "HEAT_MAP_TREE_AUTO_EXPAND_ABOVE_SHARE",
  );
  const HEAT_MAP_VIEW_ENTRY = settings_("HEAT_MAP_VIEW_ENTRY");
  const LAYOUT_RESIZE_SETTLE_DELAY_MS = settings_(
    "LAYOUT_RESIZE_SETTLE_DELAY_MS",
  );
  const RANKING_COUNTER_NAME = settings_("RANKING_COUNTER_NAME");
  const STYLE_DESIGN_FONT_CHARACTER_WIDTH_PX = settings_(
    "STYLE_DESIGN_FONT_CHARACTER_WIDTH_PX",
  );
  const STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE = settings_(
    "STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE",
  );
  const STYLE_HEAT_COLOR_FULL_SCALE_PERCENT = settings_(
    "STYLE_HEAT_COLOR_FULL_SCALE_PERCENT",
  );
  const STYLE_HEAT_MAP_SOURCE_LINE_NUMBER_MARKER_WIDTH_CHARS = settings_(
    "STYLE_HEAT_MAP_SOURCE_LINE_NUMBER_MARKER_WIDTH_CHARS",
  );
  const STYLE_HEAT_MAP_TREE_INDENT_PER_LEVEL_CHARS = settings_(
    "STYLE_HEAT_MAP_TREE_INDENT_PER_LEVEL_CHARS",
  );
  const STYLE_HEAT_MAP_TREE_PANE_NARROWEST_CHARS = settings_(
    "STYLE_HEAT_MAP_TREE_PANE_NARROWEST_CHARS",
  );
  const STYLE_HEAT_MAP_TREE_PANE_WIDEST_CHARS = settings_(
    "STYLE_HEAT_MAP_TREE_PANE_WIDEST_CHARS",
  );
  const STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS = settings_(
    "STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS",
  );
  const STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS = settings_(
    "STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS",
  );
  const STYLE_TABLE_LOCATION_COLUMN_MAX_CHARS = settings_(
    "STYLE_TABLE_LOCATION_COLUMN_MAX_CHARS",
  );
  const TABLE_ROW_COUNT_CHOICES = settings_("TABLE_ROW_COUNT_CHOICES");
  const WIDGET_KEY_NAMES = settings_("WIDGET_KEY_NAMES");
  const HOME_TABLE_RENDERED_ROW_COUNT = Math.max(...TABLE_ROW_COUNT_CHOICES);
  let profile_model = null,
    file_table = null,
    function_table = null,
    shown_test_name = null;
  const layout_box = document.getElementById("heat-map-layout-");
  const tree_pane = document.getElementById("heat-map-tree-pane-");
  const tree_panel = document.getElementById("heat-map-tree-");
  const tree_scrollbar = document.getElementById("heat-map-tree-scrollbar-");
  const main_panel = document.getElementById("heat-map-main-");
  const main_scrollbar = document.getElementById("heat-map-main-scrollbar-");
  const minimap_panel = document.getElementById("heat-map-minimap-");
  const minimap_box = document.getElementById("heat-map-minimap-box-");
  const minimap_viewport = document.getElementById(
    "heat-map-minimap-viewport-",
  );
  const view_storage = report_ui_.view_storage;
  const heat_strip = document.getElementById("heat-map-menu-");
  const home_template_text = document.getElementById(
    "heat-map-main-template-",
  ).innerHTML;
  let heat_strip_handle = null;
  let current_file_path = null;
  tree_panel.setAttribute(
    "aria-label",
    window.ui_strings_.text_of("str_heat_map_tree_label"),
  );
  main_panel.setAttribute(
    "aria-label",
    window.ui_strings_.text_of("str_heat_map_main_label"),
  );

  const vector_at = (cost_vector, index) =>
    cost_vector && index < cost_vector.length ? cost_vector[index] : 0;
  let counter_choices = null,
    counter_list = null,
    secondary_counters = null;
  const counter_find = (key) =>
    counter_list.find((counter) => counter.key === key);
  let current_counter = null;

  const text_of = window.ui_strings_.text_of;
  const text_fill = window.ui_strings_.text_fill;
  const SORT_CHOICES = [
    { value: "heat", label: text_of("str_sort_hottest_first") },
    { value: "name", label: text_of("str_sort_alphabetical") },
  ];
  const sort_mode_stored = () =>
    stored_choice_of(SORT_CHOICES, "heat.sort", SORT_CHOICES[0].value);
  let sort_mode = sort_mode_stored();
  const counter_label = (counter) =>
    text_of(
      HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX +
        counter.key.toLowerCase(),
    ) +
    " / " +
    counter.key;
  const counter_key_stored = () =>
    stored_choice_of(
      counter_choices,
      "heat.counter",
      profile_model.heatMapTotals.defaultCounter,
    );
  function counters_build() {
    counter_list = [];
    profile_model.heatMapTotals.counters.forEach((name, index) => {
      counter_list.push({
        key: name,
        get: (cost_vector) => vector_at(cost_vector, index),
      });
    });
    for (const [name, terms] of profile_model.heatMapTotals.derived) {
      const get = (cost_vector) =>
        terms.reduce(
          (running_total, term) =>
            running_total + term[0] * vector_at(cost_vector, term[1]),
          0,
        );
      counter_list.push({
        key: name,
        get,
        derived: true,
      });
    }
    secondary_counters =
      HEAT_MAP_SECONDARY_COUNTER_NAMES.map(counter_find).filter(Boolean);
    counter_choices = counter_list.map((counter) => ({
      value: counter.key,
      label: counter_label(counter),
    }));
  }
  let total_cost = 1,
    secondary_totals = {};
  const current_value = (cost_vector) => current_counter.get(cost_vector);
  const absolute = Math.abs;

  function scale_recompute() {
    total_cost = current_counter.get(profile_model.heatMapTotals.totals) || 1;
    secondary_totals = {};
    for (const secondary of secondary_counters) {
      secondary_totals[secondary.key] =
        secondary.get(profile_model.heatMapTotals.totals) || 1;
    }
  }

  const html_escape = (value) =>
    String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  const share_of_total = (value) => (100 * value) / total_cost;
  let share_text = report_ui_.percent_text;
  const share_of_total_text = (value) => share_text(share_of_total(value));

  let human_text = report_ui_.human_text;
  const cell_number = (value) => ({
    text: human_text(value),
  });
  let HEADING_MEASURE_STRING_ID = "str_heading_measure_self",
    TICKER_TAPE_HEADING = text_of("str_ticker_tape_heading_self");
  const SELF_COLUMN = {
    label: text_of("str_column_self"),
    numeric: true,
  };
  let HAS_CALL_GRAPH = null;

  let IS_DIFF = null;
  let function_baselines = null,
    file_baselines = null;
  let counter_baseline_of = () => null;
  let heat_position_of = (heat_value) => heat_value;
  let share_of_baseline = (value, baseline_cost) => share_of_total(value);
  let scope_choices_build = () => [
    ["global", null],
    ["file", text_of("str_scope_file")],
    ["function", text_of("str_scope_function")],
  ];
  let line_counter_share = (value, counter, baseline_cost, line_number) =>
    share_in_scope(value, counter, line_number);
  let line_share = (value, baseline_cost, line_number) =>
    share_in_scope(value, current_counter, line_number);
  let line_share_text = (value, baseline_cost, line_number) =>
    share_in_scope_text(value, current_counter, line_number);
  let heat_signed = (curved) => curved;
  let file_counter_share = (value, counter, file_path) =>
    (100 * value) / counter.get(profile_model.heatMapTotals.totals);
  let secondary_percent_of_cell = (
    self_cost,
    secondary,
    line_number,
    baseline_lookup,
  ) =>
    line_number != null
      ? share_in_scope(self_cost, secondary, line_number)
      : (100 * self_cost) / secondary_totals[secondary.key];
  function report_kind_set(first_model) {
    IS_DIFF = !!first_model.heatMapTotals.diff;
    if (IS_DIFF) {
      share_text = report_ui_.signed_percent_text;
      human_text = report_ui_.signed_human_text;
      HEADING_MEASURE_STRING_ID = "str_heading_measure_diff";
      TICKER_TAPE_HEADING = text_of("str_ticker_tape_heading_diff");
      counter_baseline_of = (cost_vector, counter) => {
        if (!cost_vector) return null;
        const baseline_cost = absolute(counter.get(cost_vector));
        return baseline_cost ? baseline_cost : null;
      };
      share_of_baseline = report_ui_.diff_share_of;
      scope_choices_build = () => [["line", null]];
      line_counter_share = (value, counter, baseline_cost) =>
        share_of_baseline(value, baseline_cost);
      line_share = (value, baseline_cost) =>
        share_of_baseline(value, baseline_cost);
      line_share_text = (value, baseline_cost) =>
        share_of_baseline_text(value, baseline_cost);
      heat_signed = (curved, percent) => (percent < 0 ? -curved : curved);
      heat_position_of = (heat_value) => (heat_value + 1) * 0.5;
      file_counter_share = (value, counter, file_path) =>
        share_of_baseline(value, file_counter_baseline(file_path, counter));
      secondary_percent_of_cell = (
        self_cost,
        secondary,
        line_number,
        baseline_lookup,
      ) =>
        share_of_baseline(
          self_cost,
          baseline_lookup ? baseline_lookup(secondary) : null,
        );
    }
    scale_choices_fill();
  }
  const baseline_of = (cost_vector) =>
    counter_baseline_of(cost_vector, current_counter);
  const share_of_baseline_text = (value, baseline_cost) =>
    share_text(share_of_baseline(value, baseline_cost));
  const line_baseline_vector = (file_path, line_number) => {
    const baseline_table =
      file_table[file_path] && file_table[file_path].baseline;
    return (baseline_table && baseline_table[line_number]) || null;
  };
  const line_baseline = (file_path, line_number) =>
    baseline_of(line_baseline_vector(file_path, line_number));
  const line_counter_baseline = (file_path, line_number, counter) =>
    counter_baseline_of(line_baseline_vector(file_path, line_number), counter);
  const function_baseline_of = (function_index) =>
    baseline_of(function_baselines[function_index]);
  const function_counter_baseline = (function_index, counter) =>
    counter_baseline_of(function_baselines[function_index], counter);
  const file_counter_baseline = (file_path, counter) =>
    counter_baseline_of(file_baselines[file_path], counter);
  const file_baseline_of = (file_path) =>
    file_counter_baseline(file_path, current_counter);

  const CURVE_CHOICES = [
    ["log", text_of("str_scale_curve_log")],
    ["linear", text_of("str_scale_curve_linear")],
  ];
  const SCALE_CHOICES = [];
  let active_scale = null;
  const scale_value_stored = () =>
    stored_choice_of(SCALE_CHOICES, "heat.scale", SCALE_CHOICES[0].value);
  function scale_choices_fill() {
    const scope_choices = scope_choices_build();
    CURVE_CHOICES.forEach((curve) => {
      scope_choices.forEach((scope) =>
        SCALE_CHOICES.push({
          value: curve[0] + "/" + scope[0],
          curve: curve[0],
          scope: scope[0],
          label:
            scope[1] === null
              ? curve[1]
              : text_fill("str_scale_entry", {
                  curve: curve[1],
                  scope: scope[1],
                }),
        }),
      );
    });
    scale_apply(scale_value_stored());
  }

  let scope_totals = null;
  const SCOPE_SHARE_STRING_IDS = {
    global: "str_column_global_share",
    file: "str_column_file_share",
    function: "str_column_function_share",
    line: "str_column_baseline_share",
  };
  function scope_totals_build(file_path) {
    const file = file_table[file_path];
    const totals = { file: {}, function: {} };
    for (const [line_number, line_costs] of Object.entries(file.lines)) {
      const owner = file.lineFunction[line_number];
      for (const counter of counter_list) {
        const self_cost = absolute(counter.get(line_costs[0]));
        if (!self_cost) continue;
        totals.file[counter.key] = (totals.file[counter.key] || 0) + self_cost;
        if (owner == null) continue;
        const owner_key = owner + "\n" + counter.key;
        totals.function[owner_key] =
          (totals.function[owner_key] || 0) + self_cost;
      }
    }
    return totals;
  }
  function scope_total_of(counter, line_number) {
    const scope = active_scale.scope;
    if (scope === "file" && scope_totals) {
      return scope_totals.file[counter.key] || 0;
    }
    if (scope === "function" && scope_totals && current_file_path) {
      const owner = file_table[current_file_path].lineFunction[line_number];
      if (owner == null) return 0;
      return scope_totals.function[owner + "\n" + counter.key] || 0;
    }
    return counter.get(profile_model.heatMapTotals.totals) || 1;
  }
  const share_in_scope = (value, counter, line_number) => {
    const scope_total = scope_total_of(counter, line_number);
    return scope_total ? (100 * value) / scope_total : 0;
  };
  const share_in_scope_text = (value, counter, line_number) =>
    value ? share_text(share_in_scope(value, counter, line_number)) : "";
  const scope_share_label = () =>
    text_of(SCOPE_SHARE_STRING_IDS[active_scale.scope]);
  const heat_of_line = (value, baseline_cost, line_number) =>
    heat_of_share(line_share(value, baseline_cost, line_number));

  function heat_of_share(percent) {
    const magnitude = Math.min(
      absolute(percent),
      STYLE_HEAT_COLOR_FULL_SCALE_PERCENT,
    );
    if (magnitude <= 0) return 0;
    const fraction = magnitude / STYLE_HEAT_COLOR_FULL_SCALE_PERCENT;
    const curved =
      active_scale.curve === "log" ? Math.log10(1 + 9 * fraction) : fraction;
    return heat_signed(curved, percent);
  }
  function heat_of_delta(cost, baseline_cost) {
    return heat_of_share(share_of_baseline(cost, baseline_cost));
  }

  const ramp_channels_at = report_ui_.ramp_channels_at;
  function cell_style(heat_value) {
    if (absolute(heat_value) <= 0) return "";
    const mixed_channels = ramp_channels_at(heat_position_of(heat_value));
    const luminance =
      (0.2126 * mixed_channels[0] +
        0.7152 * mixed_channels[1] +
        0.0722 * mixed_channels[2]) /
      255;
    const foreground_color =
      luminance > STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE
        ? profile_model.theme.fgDark
        : profile_model.theme.fgLight;
    return (
      `background:rgb(${mixed_channels.join(",")});` +
      `color:${foreground_color}`
    );
  }
  let per_function_calls = null,
    CALLS_TOTAL = null;
  const call_count_cell = (call_count) =>
    call_count
      ? {
          text: human_text(call_count),
          style: cell_style(heat_of_share((100 * call_count) / CALLS_TOTAL)),
        }
      : "";

  const hash_for_line = (file_path, line) =>
    report_ui_.address.hash_of({
      test: shown_test_name,
      view: HEAT_MAP_VIEW_ENTRY[0],
      file: file_path,
      line: line || null,
    });
  const hash_for_function = (name) =>
    report_ui_.address.hash_of({
      test: shown_test_name,
      view: HEAT_MAP_VIEW_ENTRY[0],
      function: name,
    });
  function function_name(index) {
    return index != null && function_table[index]
      ? function_table[index].name
      : text_of("str_function_name_unknown");
  }

  function source_text(file_path) {
    const file = file_table[file_path];
    if (!file || file.source == null) return null;
    const sources = window.report_sources_;
    return (sources && sources[file_path]) != null ? sources[file_path] : null;
  }

  function line_link(file_path, line, text) {
    if (!file_table[file_path] || !line) return html_escape(text);
    return (
      `<a href="${hash_for_line(file_path, line)}">` +
      `${html_escape(text)}</a>`
    );
  }

  const function_is_linkable = (function_index) =>
    function_index != null &&
    function_table[function_index] &&
    function_table[function_index].line &&
    file_table[function_table[function_index].file];
  function function_link(function_index, text) {
    if (!function_is_linkable(function_index)) return html_escape(text);
    const href = hash_for_function(function_table[function_index].name);
    return `<a href="${href}">${html_escape(text)}</a>`;
  }

  function table_render(key, columns, rows, options) {
    options = options || {};
    const cell_rows = rows.map((row) => row.map(report_ui_.cell_normalize));
    const grow_index = options.fill
      ? columns.findIndex((column) => column.grow)
      : -1;
    const column_limit_list = report_ui_
      .column_extents(columns, cell_rows, grow_index)
      .map(report_ui_.column_limits);
    const table_classes = ["columns_", options.cls || ""]
      .filter(Boolean)
      .join(" ");
    let markup = options.bare ? "" : `<div class="table-box-">`;
    markup +=
      `<div class="table-columns-"><table class="${table_classes}"` +
      ` data-key-="${html_escape(key)}"><colgroup>`;
    column_limit_list.forEach((limit, column_index) => {
      const width_text = report_ui_.column_width_text(
        column_limit_list,
        column_index,
        grow_index,
      );
      markup += `<col data-min-="${limit[0]}ch" style="width:${width_text}">`;
    });
    markup += `</colgroup><thead><tr>`;
    for (const column of columns) {
      const heading = html_escape(column.label);
      markup +=
        `<th${column.numeric ? ' class="numeric_"' : ""}` +
        ` title="${heading}">` +
        `${heading}</th>`;
    }
    markup += `</tr></thead><tbody>`;
    cell_rows.forEach((row, row_index) => {
      const href = options.row_href && options.row_href[row_index];
      const row_attribute_text =
        options.row_attributes && options.row_attributes[row_index];
      markup += href
        ? `<tr class="row-link-" data-href-="${html_escape(href)}">`
        : row_attribute_text
          ? `<tr ${row_attribute_text}>`
          : "<tr>";
      row.forEach((cell, column_index) => {
        const column = columns[column_index];
        const class_names = [
          column.numeric ? "numeric_" : "",
          column.cls || "",
        ]
          .filter(Boolean)
          .join(" ");
        const text = cell.text || "";
        markup +=
          `<td${class_names ? ` class="${class_names}"` : ""}` +
          `${cell.style ? ` style="${cell.style}"` : ""}>` +
          `${cell.html != null ? cell.html : html_escape(text)}</td>`;
      });
      markup += "</tr>";
    });
    markup += `</tbody></table></div>`;
    return options.bare ? markup : markup + `</div>`;
  }

  const counter_column = (counter, extra) =>
    Object.assign({ label: counter.key, numeric: true }, extra || {});
  const secondary_columns = () =>
    secondary_counters.map((secondary) =>
      counter_column(secondary, {
        label: counter_label(secondary),
        cls: "heat-map-source-table-secondary-counter-cell-",
      }),
    );
  function secondary_cells(cost_vector, line_number, baseline_lookup) {
    return secondary_counters.map((secondary) => {
      const self_cost = secondary.get(cost_vector);
      const percent = secondary_percent_of_cell(
        self_cost,
        secondary,
        line_number,
        baseline_lookup,
      );
      return {
        text: self_cost ? share_text(percent) : "",
        style: cell_style(heat_of_share(percent)),
      };
    });
  }

  let tree_root = null;
  function tree_build() {
    const root = { name: "", path: "", dirs: new Map(), files: [], self: 0 };
    function node_insert(file_path, self_cost, baseline_cost, cold) {
      const path_parts = file_path.split("/");
      let tree_node = root;
      for (
        let part_index = 0;
        part_index < path_parts.length - 1;
        part_index++
      ) {
        const segment = path_parts[part_index];
        if (!tree_node.dirs.has(segment)) {
          tree_node.dirs.set(segment, {
            name: segment,
            path: tree_node.path ? tree_node.path + "/" + segment : segment,
            dirs: new Map(),
            files: [],
            self: 0,
            base: 0,
          });
        }
        tree_node = tree_node.dirs.get(segment);
      }
      tree_node.files.push({
        name: path_parts[path_parts.length - 1],
        path: file_path,
        self: self_cost,
        base: baseline_cost,
        cold,
        zero: self_cost === 0,
      });
    }
    for (const file_path of Object.keys(file_table)) {
      node_insert(
        file_path,
        current_value(file_table[file_path].self),
        file_baseline_of(file_path) || 0,
        false,
      );
    }
    for (const file_path of profile_model.cold) {
      node_insert(file_path, 0, 0, true);
    }
    (function subtree_sum(tree_node) {
      let running_total = 0,
        baseline_cost = 0;
      for (const directory_node of tree_node.dirs.values()) {
        running_total += subtree_sum(directory_node);
        baseline_cost += directory_node.base;
      }
      for (const file of tree_node.files) {
        running_total += file.self;
        baseline_cost += file.base;
      }
      tree_node.self = running_total;
      tree_node.base = baseline_cost;
      return running_total;
    })(root);
    return root;
  }
  const expanded_directories = new Set(),
    expanded_cold_groups = new Set();
  function node_compare(node_a, node_b) {
    const by_name = node_a.name.localeCompare(node_b.name);
    if (sort_mode !== "heat") return by_name;
    return absolute(node_b.self) - absolute(node_a.self) || by_name;
  }
  const caret_of = (is_expanded) =>
    text_of(is_expanded ? "str_caret_down" : "str_caret_right");
  const treeitem_attributes_of = (node_level) =>
    ` role="treeitem" aria-level="${node_level}" tabindex="-1"`;
  function tree_render() {
    const output_parts = [];
    function nodes_emit(tree_node, depth) {
      const indent_chars = depth * STYLE_HEAT_MAP_TREE_INDENT_PER_LEVEL_CHARS;
      const directories = [...tree_node.dirs.values()].sort(node_compare);
      for (const directory_node of directories) {
        const is_expanded = expanded_directories.has(directory_node.path);
        const heat_style_attribute = cell_style(
          heat_of_delta(directory_node.self, directory_node.base),
        );
        output_parts.push(
          `<div class="heat-map-tree-node-` +
            `${heat_style_attribute ? " heat_" : ""}"` +
            `${treeitem_attributes_of(depth + 1)}` +
            ` aria-expanded="${is_expanded}"` +
            ` data-dir-="${html_escape(directory_node.path)}"` +
            ` style="padding-left:${indent_chars}ch;` +
            `${heat_style_attribute}">` +
            `<span class="heat-map-tree-node-caret-">` +
            `${caret_of(is_expanded)}</span>` +
            `<span class="heat-map-tree-node-name-">` +
            `${html_escape(directory_node.name)}/</span>` +
            `<span class="heat-map-tree-node-share-percent-">` +
            `${share_of_baseline_text(
              directory_node.self,
              directory_node.base,
            )}` +
            `</span></div>`,
        );
        output_parts.push(
          `<div class="heat-map-tree-node-child-group-` +
            `${is_expanded ? " open_" : ""}" role="group">`,
        );
        nodes_emit(directory_node, depth + 1);
        output_parts.push(`</div>`);
      }
      const file_list = [...tree_node.files].sort(node_compare);
      const file_row_emit = (file, node_level) => {
        const selected_class =
          file.path === current_file_path ? " selected_" : "";
        const selected_attribute = selected_class
          ? ' aria-selected="true"'
          : "";
        const heat_style_attribute = file.cold
          ? ""
          : cell_style(heat_of_delta(file.self, file.base));
        output_parts.push(
          `<div class="heat-map-tree-node- file_${file.cold ? " cold_" : ""}` +
            `${heat_style_attribute ? " heat_" : ""}${selected_class}"` +
            `${treeitem_attributes_of(node_level)}${selected_attribute}` +
            ` data-file-="${html_escape(file.path)}"` +
            ` style="padding-left:${indent_chars}ch;` +
            `${heat_style_attribute}">` +
            `<span class="heat-map-tree-node-caret-">` +
            `${caret_of(false)}</span>` +
            `<span class="heat-map-tree-node-name-">` +
            `${html_escape(file.name)}</span>` +
            `<span class="heat-map-tree-node-share-percent-">` +
            `${share_of_baseline_text(file.self, file.base)}` +
            `</span></div>`,
        );
      };
      const zero_cost_files = file_list.filter((file) => file.zero);
      for (const file of file_list)
        if (!file.zero) file_row_emit(file, depth + 1);
      if (zero_cost_files.length) {
        const is_expanded = expanded_cold_groups.has(tree_node.path);
        output_parts.push(
          `<div class="heat-map-tree-node- more_"` +
            `${treeitem_attributes_of(depth + 1)}` +
            ` aria-expanded="${is_expanded}"` +
            ` data-more-="${html_escape(tree_node.path)}"` +
            ` style="padding-left:${indent_chars}ch">` +
            `<span class="heat-map-tree-node-caret-">` +
            `${caret_of(is_expanded)}</span>` +
            `<span class="heat-map-tree-node-name-">` +
            `${text_of("str_no_samples")}</span>` +
            `<span class="heat-map-tree-node-share-percent-"></span></div>`,
        );
        if (is_expanded) {
          output_parts.push(
            `<div class="heat-map-tree-node-child-group- open_"` +
              ` role="group">`,
          );
          for (const file of zero_cost_files) file_row_emit(file, depth + 2);
          output_parts.push(`</div>`);
        }
      }
    }
    const tree_had_focus =
      document.hasFocus() && tree_panel.contains(document.activeElement);
    nodes_emit(tree_root, 0);
    tree_panel.innerHTML = output_parts.join("");
    tree_tab_stop_place(tree_had_focus);
  }
  let tree_focus_selector = null;
  const TREE_NODE_KEY_ATTRIBUTE_NAMES = [
    "data-dir-",
    "data-file-",
    "data-more-",
  ];
  function tree_node_selector_of(tree_node) {
    const key_attribute_name = TREE_NODE_KEY_ATTRIBUTE_NAMES.find(
      (attribute_name) => tree_node.hasAttribute(attribute_name),
    );
    const key_value = CSS.escape(tree_node.getAttribute(key_attribute_name));
    return `.heat-map-tree-node-[${key_attribute_name}="${key_value}"]`;
  }
  function tree_visible_nodes() {
    return [...tree_panel.querySelectorAll(".heat-map-tree-node-")].filter(
      (tree_node) =>
        !tree_node.closest(".heat-map-tree-node-child-group-:not(.open_)"),
    );
  }
  function tree_parent_of(tree_node) {
    const holding_group = tree_node.parentElement.closest(
      ".heat-map-tree-node-child-group-",
    );
    return holding_group ? holding_group.previousElementSibling : null;
  }
  const tree_first_child_of = (tree_node) =>
    tree_node.nextElementSibling.querySelector(
      ":scope > .heat-map-tree-node-",
    );
  function tree_tab_stop_place(takes_focus) {
    const visible_nodes = tree_visible_nodes();
    const candidate_nodes = [
      takes_focus && tree_focus_selector
        ? tree_panel.querySelector(tree_focus_selector)
        : null,
      tree_panel.querySelector(".heat-map-tree-node-.selected_"),
      visible_nodes[0],
    ];
    const tab_stop = candidate_nodes.find((candidate_node) =>
      visible_nodes.includes(candidate_node),
    );
    if (tab_stop) report_ui_.tab_stop_move(null, tab_stop, takes_focus);
  }
  function tree_key_take(key_event, key_name, tree_node) {
    if (report_ui_.widget_key.activates(key_name)) {
      key_event.preventDefault();
      if (!key_event.repeat) tree_node.click();
      return;
    }
    const visible_nodes = tree_visible_nodes();
    const node_index = visible_nodes.indexOf(tree_node);
    const is_open = tree_node.getAttribute("aria-expanded") === "true";
    const is_closed = tree_node.getAttribute("aria-expanded") === "false";
    let next_node = null;
    switch (key_name) {
      case WIDGET_KEY_NAMES.down:
        next_node = visible_nodes[node_index + 1];
        break;
      case WIDGET_KEY_NAMES.first:
        next_node = visible_nodes[0];
        break;
      case WIDGET_KEY_NAMES.last:
        next_node = visible_nodes[visible_nodes.length - 1];
        break;
      case WIDGET_KEY_NAMES.left:
        if (is_open) tree_node.click();
        else next_node = tree_parent_of(tree_node);
        break;
      case WIDGET_KEY_NAMES.right:
        if (is_closed) tree_node.click();
        else if (is_open) next_node = tree_first_child_of(tree_node);
        break;
      case WIDGET_KEY_NAMES.up:
        next_node = visible_nodes[node_index - 1];
        break;
      default:
        return;
    }
    key_event.preventDefault();
    if (next_node) report_ui_.tab_stop_move(tree_node, next_node, true);
  }
  tree_panel.addEventListener(
    "focusin",
    window.catch_show_throw_((focus_event) => {
      const tree_node = focus_event.target.closest(".heat-map-tree-node-");
      if (!tree_node) return;
      tree_focus_selector = tree_node_selector_of(tree_node);
      report_ui_.tab_stop_move(
        tree_panel.querySelector('.heat-map-tree-node-[tabindex="0"]'),
        tree_node,
        false,
      );
    }),
  );
  tree_panel.addEventListener(
    "keydown",
    window.catch_show_throw_((key_event) => {
      const key_name = report_ui_.widget_key.of(key_event);
      const tree_node = key_event.target.closest(".heat-map-tree-node-");
      if (key_name && tree_node) tree_key_take(key_event, key_name, tree_node);
    }),
  );
  tree_panel.addEventListener(
    "click",
    window.catch_show_throw_((click_event) => {
      const tree_node = click_event.target.closest(".heat-map-tree-node-");
      if (!tree_node) return;
      if (tree_node.getAttribute("data-dir-") != null) {
        const file_path = tree_node.getAttribute("data-dir-");
        if (expanded_directories.has(file_path)) {
          expanded_directories.delete(file_path);
        } else expanded_directories.add(file_path);
        tree_render();
        if (expanded_directories.has(file_path)) group_opening_show(tree_node);
      } else if (tree_node.getAttribute("data-more-") != null) {
        const file_path = tree_node.getAttribute("data-more-");
        if (expanded_cold_groups.has(file_path)) {
          expanded_cold_groups.delete(file_path);
        } else expanded_cold_groups.add(file_path);
        tree_render();
        if (expanded_cold_groups.has(file_path)) group_opening_show(tree_node);
      } else if (tree_node.getAttribute("data-file-") != null) {
        if (tree_node.classList.contains("cold_")) return;
        report_ui_.address.request(
          hash_for_line(tree_node.getAttribute("data-file-")),
        );
      }
    }),
  );
  function group_opening_show(clicked_node) {
    const opened_node = tree_panel.querySelector(
      tree_node_selector_of(clicked_node),
    );
    const tree_rect = design_rect_of(tree_panel);
    const group_rect = design_rect_of(opened_node.nextElementSibling);
    if (group_rect.bottom <= tree_rect.top + tree_panel.clientHeight) return;
    tree_panel.scrollTop += group_rect.top - tree_rect.top;
  }
  // Opens every folder above a file and the no samples group holding the file.
  function tree_reveal(file_path) {
    const path_parts = file_path.split("/");
    let tree_node = tree_root;
    for (const segment of path_parts.slice(0, -1)) {
      tree_node = tree_node.dirs.get(segment);
      expanded_directories.add(tree_node.path);
    }
    const file_node = tree_node.files.find((file) => file.path === file_path);
    if (file_node.zero) expanded_cold_groups.add(tree_node.path);
  }
  // Scrolls the tree until the selected node sits inside the shown part.
  function tree_selected_show() {
    const selected_node = tree_panel.querySelector(
      ".heat-map-tree-node-.selected_",
    );
    const tree_rect = design_rect_of(tree_panel);
    const node_rect = design_rect_of(selected_node);
    const box_bottom_px = tree_rect.top + tree_panel.clientHeight;
    if (node_rect.top < tree_rect.top)
      tree_panel.scrollTop -= tree_rect.top - node_rect.top;
    else if (node_rect.bottom > box_bottom_px)
      tree_panel.scrollTop += node_rect.bottom - box_bottom_px;
  }

  let entry_line_index = null;

  function top_lines(count) {
    const all = [];
    for (const [file_path, file] of Object.entries(file_table)) {
      for (const [line_number, line_costs] of Object.entries(file.lines)) {
        const self_cost = current_value(line_costs[0]);
        if (absolute(self_cost) <= 0) continue;
        all.push([
          file_path,
          +line_number,
          self_cost,
          file.lineFunction[line_number],
        ]);
      }
    }
    all.sort((row_a, row_b) => absolute(row_b[2]) - absolute(row_a[2]));
    return all.slice(0, count).map((entry) => {
      const file = file_table[entry[0]];
      let source_snippet = "";
      const snippet_source = source_text(entry[0]);
      if (snippet_source != null) {
        const source_lines = snippet_source.split("\n");
        if (entry[1] >= 1 && entry[1] <= source_lines.length) {
          source_snippet = source_lines[entry[1] - 1]
            .trim()
            .slice(0, HEAT_MAP_HOME_LINES_SOURCE_SNIPPET_MAX_CHARS);
        }
      }
      return [entry[0], entry[1], entry[2], entry[3], source_snippet];
    });
  }
  // Writes the text of a home table heading, its row count a span.
  function home_heading_markup(string_id) {
    const row_count_markup =
      `<span class="page-heading-row-count-">` +
      `${HEAT_MAP_HOME_TABLE_DEFAULT_ROWS}</span>`;
    const measure_text = text_fill(HEADING_MEASURE_STRING_ID, {
      counter: current_counter.key,
    });
    return text_fill(string_id, {
      count: row_count_markup,
      measure: html_escape(measure_text),
    });
  }
  function home_render() {
    current_file_path = null;
    scope_totals = null;
    const line_rows = top_lines(HOME_TABLE_RENDERED_ROW_COUNT);
    const lines_table_markup = table_render(
      "heat.home.lines",
      [
        { label: text_of("str_column_rank"), numeric: true },
        SELF_COLUMN,
        {
          label: text_of("str_column_function"),
          width: STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS,
        },
        {
          label: text_of("str_column_defined_at"),
          clip: HEAT_MAP_HOME_LINES_LOCATION_MAX_CHARS,
        },
        {
          label: text_of("str_column_source"),
          clip: HEAT_MAP_HOME_LINES_SOURCE_COLUMN_MAX_CHARS,
        },
        counter_column(current_counter),
        ...secondary_columns(),
      ],
      line_rows.map((entry, index) => {
        const [file_path, line_number, cost, function_index, source_snippet] =
          entry;
        const line_costs = file_table[file_path].lines[line_number];
        const location_text = file_path + ":" + line_number;
        const baseline_cost = line_baseline(file_path, line_number);
        return [
          String(index + 1),
          {
            text: share_of_baseline_text(cost, baseline_cost),
            style: cell_style(heat_of_delta(cost, baseline_cost)),
          },
          {
            text: function_name(function_index),
          },
          {
            text: location_text,
            html: line_link(file_path, line_number, location_text),
          },
          source_snippet,
          cell_number(cost),
          ...secondary_cells(line_costs[0], null, (secondary) =>
            line_counter_baseline(file_path, line_number, secondary),
          ),
        ];
      }),
      {
        row_href: line_rows.map((entry) => hash_for_line(entry[0], entry[1])),
      },
    );
    const top_functions = function_table
      .map((function_entry, index) => [
        index,
        current_value(function_entry.self),
      ])
      .filter((entry) => absolute(entry[1]) > 0)
      .sort((entry_a, entry_b) => absolute(entry_b[1]) - absolute(entry_a[1]))
      .slice(0, HOME_TABLE_RENDERED_ROW_COUNT);
    const call_columns = HAS_CALL_GRAPH
      ? [
          {
            label: text_of("str_column_calls"),
            numeric: true,
          },
          {
            label: text_of("str_column_inclusive"),
            numeric: true,
          },
        ]
      : [];
    const functions_table_markup = table_render(
      "heat.home.functions",
      [
        { label: text_of("str_column_rank"), numeric: true },
        SELF_COLUMN,
        {
          label: text_of("str_column_function"),
          width: STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS,
        },
        {
          label: text_of("str_column_defined_at"),
          clip: STYLE_TABLE_LOCATION_COLUMN_MAX_CHARS,
        },
        ...call_columns,
        ...secondary_columns(),
      ],
      top_functions.map(([function_index, self_cost], index) => {
        const function_entry = function_table[function_index];
        const location_text = function_entry.line
          ? function_entry.file + ":" + function_entry.line
          : function_entry.file;
        const baseline_cost = function_baseline_of(function_index);
        const calls = HAS_CALL_GRAPH
          ? [
              call_count_cell(per_function_calls[function_index]),
              share_of_baseline_text(
                self_cost + current_value(function_entry.calls),
                baseline_cost,
              ),
            ]
          : [];
        return [
          String(index + 1),
          {
            text: share_of_baseline_text(self_cost, baseline_cost),
            style: cell_style(heat_of_delta(self_cost, baseline_cost)),
          },
          { text: function_entry.name },
          {
            text: location_text,
            html: function_link(function_index, location_text),
          },
          ...calls,
          ...secondary_cells(function_entry.self, null, (secondary) =>
            function_counter_baseline(function_index, secondary),
          ),
        ];
      }),
      {
        row_href: top_functions.map(([function_index]) =>
          function_is_linkable(function_index)
            ? hash_for_function(function_table[function_index].name)
            : "",
        ),
      },
    );
    main_panel.innerHTML = home_template_text
      .replace("__LINES_TABLE__", () => lines_table_markup)
      .replace("__FUNCTIONS_TABLE__", () => functions_table_markup);
    const [lines_heading, functions_heading] = main_panel.querySelectorAll(
      ".heat-map-home- > .page-heading-",
    );
    lines_heading.innerHTML = home_heading_markup(
      "str_heading_lines_by_counter",
    );
    functions_heading.innerHTML = home_heading_markup(
      "str_heading_functions_by_counter",
    );
    const counter_entry = counter_entry_of(current_counter.key);
    for (const heading_element of [lines_heading, functions_heading])
      report_ui_.table_heading.attach(heading_element, [counter_entry]);
    main_panel.scrollTop = 0;
    tree_render();
    report_ui_.layout_activate(main_panel);
    minimap_clear();
  }

  // Renders the hottest lines strip of a file, or of one function in the file.
  function hottest_lines_render(file_path, function_index) {
    const file = file_table[file_path];
    const line_share_of = (line_number, cost) =>
      line_share(cost, line_baseline(file_path, line_number), line_number);
    const tape_lines = Object.keys(file.lines)
      .filter(
        (line_key) =>
          function_index == null ||
          file.lineFunction[line_key] === function_index,
      )
      .map((line_key) => [+line_key, current_value(file.lines[line_key][0])])
      .filter(
        ([line_number, cost]) =>
          absolute(line_share_of(line_number, cost)) >=
          HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_LEAST_SHARE,
      )
      .sort((entry_a, entry_b) => absolute(entry_b[1]) - absolute(entry_a[1]))
      .slice(0, HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_MAX_COUNT);
    if (!tape_lines.length) return { markup: "", copy_text: "" };
    let markup =
      `<div class="heat-map-source-ticker-tape-" role="toolbar"` +
      ` aria-label="${html_escape(TICKER_TAPE_HEADING)}">` +
      `<span class="heat-map-source-ticker-tape-label-">` +
      `${html_escape(TICKER_TAPE_HEADING)}</span>`;
    const entry_texts = tape_lines.map(([line_number, cost], entry_index) => {
      const baseline_cost = line_baseline(file_path, line_number);
      const entry_text =
        `${line_number} -` +
        ` ${line_share_text(cost, baseline_cost, line_number)}`;
      markup +=
        `<a class="heat-map-source-ticker-tape-entry-"` +
        ` href="${hash_for_line(file_path, line_number)}"` +
        ` tabindex="${entry_index ? -1 : 0}"` +
        ` style="${cell_style(
          heat_of_line(cost, baseline_cost, line_number),
        )}">` +
        `${html_escape(entry_text)}</a>`;
      return entry_text;
    });
    markup += `</div>`;
    return {
      markup,
      copy_text: [TICKER_TAPE_HEADING, ...entry_texts].join("\n"),
    };
  }

  // Builds a control that only calls JavaScript, copy or close.
  const box_control_markup = (action_name, string_id, extra_class_name) =>
    `<span class="heat-map-source-information-box-control-` +
    `${extra_class_name ? " " + extra_class_name : ""}"` +
    ` role="button" tabindex="0"` +
    ` data-information-box-action-="${action_name}">` +
    `${html_escape(text_of(string_id))}</span>`;
  const box_separator_markup =
    `<span class="heat-map-source-information-box-action-bar-separator-">` +
    ` | </span>`;

  // Renders the information box of a file, or of a line when one is given.
  function information_box_render(file_path, line_number) {
    const file = file_table[file_path];
    const function_index = line_number
      ? (entry_line_index[file_path] || {})[line_number]
      : null;
    const line_function_index = line_number
      ? file.lineFunction[line_number]
      : null;
    const line_costs = line_number
      ? file.lines[line_number] || [[], [], 0]
      : null;
    const cost_vector = line_number ? line_costs[0] : file.self;
    const counter_share_text = (value, counter) => {
      if (!value) return "";
      return share_text(
        line_number
          ? line_counter_share(
              value,
              counter,
              line_counter_baseline(file_path, line_number, counter),
              line_number,
            )
          : file_counter_share(value, counter, file_path),
      );
    };
    const function_column = (label) => ({
      label,
      width: STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS,
    });
    const location_column = {
      label: text_of("str_column_defined_at"),
      clip: STYLE_TABLE_LOCATION_COLUMN_MAX_CHARS,
    };
    const self_label = text_of(
      line_number && function_index == null
        ? "str_line_self"
        : "str_column_self",
    );
    const counter_columns = [
      { label: text_of("str_column_counter") },
      {
        label: line_number
          ? scope_share_label()
          : text_of(SCOPE_SHARE_STRING_IDS[IS_DIFF ? "line" : "global"]),
        numeric: true,
      },
      { label: text_of("str_column_count"), numeric: true },
    ];
    const ranking_counter = counter_find(RANKING_COUNTER_NAME);
    const listed_counters = [
      current_counter,
      ...counter_list
        .filter(
          (counter) =>
            !counter.derived &&
            counter !== current_counter &&
            counter.get(cost_vector),
        )
        .sort((counter_a, counter_b) =>
          counter_a.key.localeCompare(counter_b.key),
        ),
    ];
    if (
      current_counter !== ranking_counter &&
      ranking_counter.get(cost_vector)
    )
      listed_counters.push(ranking_counter);
    const counter_rows = listed_counters.map((counter, row_index) => {
      const counter_value = counter.get(cost_vector);
      return [
        {
          text: (row_index ? "" : self_label + " ") + counter_label(counter),
        },
        counter_share_text(counter_value, counter),
        counter_value ? cell_number(counter_value) : "",
      ];
    });
    const counter_row_attributes = listed_counters.map((counter) =>
      counter.derived
        ? 'class="heat-map-source-information-box-synthetic-row-"'
        : "",
    );
    if (line_number) {
      const call_cost = current_value(line_costs[1]);
      const line_baseline_cost = line_baseline(file_path, line_number);
      if (call_cost) {
        counter_rows.push([
          { text: text_of("str_column_calls") },
          line_share_text(call_cost, line_baseline_cost, line_number),
          cell_number(call_cost),
        ]);
        counter_rows.push([
          { text: text_of("str_column_call_count") },
          "",
          call_count_cell(line_costs[2]),
        ]);
      }
    }
    const in_function_note =
      line_function_index != null
        ? text_fill("str_in_function", {
            function: function_name(line_function_index),
          })
        : "";
    const in_function_html =
      line_function_index != null
        ? text_fill("str_in_function", {
            function:
              `<span` +
              ` class="heat-map-source-information-box-function-name-">` +
              `${html_escape(function_name(line_function_index))}</span>`,
          })
        : "";
    const heading_line = line_number
      ? `${file_path}:${line_number}${in_function_note}`
      : file_path;
    const note_texts = [];
    if (!line_number && file.group === "external")
      note_texts.push(text_fill("str_not_in_repo", { path: file.raw }));
    if (!line_number && source_text(file_path) == null)
      note_texts.push(text_of("str_source_unavailable"));
    const hottest_lines =
      !line_number || function_index != null
        ? hottest_lines_render(file_path, function_index)
        : { markup: "", copy_text: "" };
    let markup =
      `<div class="heat-map-source-information-box-"` +
      ` data-information-box-line-="${line_number}">` +
      box_control_markup(
        "close",
        "str_information_box_close_symbol",
        "heat-map-source-information-box-close-symbol-",
      );
    markup +=
      `<div>${html_escape(file_path)}` +
      `${line_number ? ":" + line_number : ""}${in_function_html}</div>`;
    markup += table_render(
      "heat.detail.stats",
      counter_columns,
      counter_rows,
      { row_attributes: counter_row_attributes },
    );
    for (const note_text of note_texts) {
      markup +=
        `<div class="heat-map-source-information-box-note-">` +
        `${html_escape(note_text)}</div>`;
    }
    markup += hottest_lines.markup;
    const text_parts = [
      heading_line +
        "\n" +
        report_ui_.table_markdown(counter_columns, counter_rows),
      ...note_texts,
    ];
    if (hottest_lines.copy_text) text_parts.push(hottest_lines.copy_text);
    const callees = line_number
      ? (file.callees[line_number] || [])
          .slice()
          .sort(
            (callee_a, callee_b) =>
              current_value(callee_b[3]) - current_value(callee_a[3]),
          )
      : [];
    if (callees.length) {
      const columns = [
        { label: text_of("str_column_share_of_total"), numeric: true },
        counter_column(current_counter),
        { label: text_of("str_column_call_count"), numeric: true },
        function_column(text_of("str_column_callee")),
        location_column,
      ];
      const rows = callees.map(
        ([callee_index, call_file, call_line, cost_vector, call_count]) => {
          const location_text = call_line
            ? call_file + ":" + call_line
            : call_file;
          return [
            share_of_total_text(current_value(cost_vector)),
            cell_number(current_value(cost_vector)),
            call_count_cell(call_count),
            {
              text: function_name(callee_index),
            },
            {
              text: location_text,
              html: function_link(callee_index, location_text),
            },
          ];
        },
      );
      const heading = text_fill("str_information_box_callees", {
        counter: counter_label(current_counter),
      });
      markup +=
        `<div class="heat-map-source-information-box-heading-">` +
        `${html_escape(heading)}</div>` +
        table_render("heat.detail.callees", columns, rows);
      text_parts.push(
        heading + "\n" + report_ui_.table_markdown(columns, rows),
      );
    }
    if (function_index != null) {
      const function_entry = function_table[function_index];
      const callers = function_entry.callers
        .slice()
        .sort((caller_a, caller_b) => caller_b[4] - caller_a[4]);
      const function_baseline_cost = function_baseline_of(function_index);
      const function_self_text =
        share_of_baseline_text(
          current_value(function_entry.self),
          function_baseline_cost,
        ) || report_ui_.zero_percent_text();
      const function_total_text =
        share_of_baseline_text(
          current_value(function_entry.self) +
            current_value(function_entry.calls),
          function_baseline_cost,
        ) || report_ui_.zero_percent_text();
      const heading = HAS_CALL_GRAPH
        ? text_fill("str_information_box_function_totals", {
            function: function_entry.name,
            self: function_self_text,
            total: function_total_text,
          })
        : text_fill("str_information_box_function_self", {
            function: function_entry.name,
            self: function_self_text,
          });
      markup +=
        `<div class="heat-map-source-information-box-heading-">` +
        `${html_escape(heading)}</div>`;
      if (callers.length) {
        const columns = [
          { label: text_of("str_column_call_count"), numeric: true },
          { label: text_of("str_column_share_of_total"), numeric: true },
          counter_column(current_counter),
          function_column(text_of("str_column_caller")),
          {
            label: text_of("str_column_called_at"),
            clip: STYLE_TABLE_LOCATION_COLUMN_MAX_CHARS,
          },
        ];
        const rows = callers.map(
          ([caller_index, call_file, call_line, cost_vector, call_count]) => {
            const location_text = call_line
              ? call_file + ":" + call_line
              : call_file;
            return [
              call_count_cell(call_count),
              share_of_total_text(current_value(cost_vector)),
              cell_number(current_value(cost_vector)),
              {
                text: function_name(caller_index),
              },
              {
                text: location_text,
                html: line_link(call_file, call_line, location_text),
              },
            ];
          },
        );
        markup += table_render("heat.detail.callers", columns, rows);
        text_parts.push(
          heading + "\n" + report_ui_.table_markdown(columns, rows),
        );
      } else if (HAS_CALL_GRAPH) {
        const none = text_of("str_no_caller");
        markup += `<div>${html_escape(none)}</div>`;
        text_parts.push(heading + "\n" + none);
      } else {
        text_parts.push(heading);
      }
    }
    const owner_link_markup =
      line_number &&
      function_index == null &&
      function_is_linkable(line_function_index)
        ? `<a class="heat-map-source-information-box-control-"` +
          ` href="${hash_for_function(
            function_table[line_function_index].name,
          )}">` +
          `${html_escape(text_of("str_information_box_function"))}</a>` +
          box_separator_markup
        : "";
    markup +=
      `<div>` +
      owner_link_markup +
      box_control_markup("copy", "str_information_box_copy") +
      box_separator_markup +
      box_control_markup("close", "str_information_box_close") +
      `</div></div>`;
    return { markup, copy_text: text_parts.join("\n\n") };
  }

  // Renders the line that stands in for the file box while that box is away.
  function information_line_render(file_path, has_file_box) {
    const self_cost = current_value(file_table[file_path].self);
    const share_shown = self_cost
      ? share_text(file_counter_share(self_cost, current_counter, file_path))
      : report_ui_.zero_percent_text();
    const link_text = text_fill("str_information_line_link", {
      path: file_path,
      share: share_shown,
    });
    return (
      `<div class="heat-map-source-information-line- band_` +
      `${has_file_box ? " empty_" : ""}" data-information-box-line-="0">` +
      `<a href="${hash_for_line(file_path)}">${html_escape(link_text)}</a> ` +
      box_control_markup("copy", "str_information_box_copy") +
      `</div>`
    );
  }
  const file_box_of = () =>
    main_panel.querySelector(
      ".heat-map-source- > .heat-map-source-information-box-",
    );

  function file_render(file_path) {
    const file = file_table[file_path];
    if (!file)
      throw new Error(
        window.ui_strings_.text_fill("str_error_hash_file_unknown", [
          file_path,
        ]),
      );
    const is_first_view = current_file_path !== file_path,
      kept_scroll_top = is_first_view ? 0 : main_panel.scrollTop,
      has_file_box = is_first_view || !!file_box_of();
    current_file_path = file_path;
    const lines = file.lines;
    scope_totals = scope_totals_build(file_path);
    let markup =
      `<div class="heat-map-source-">` +
      (has_file_box ? information_box_render(file_path, 0).markup : "") +
      information_line_render(file_path, has_file_box);
    const file_source = source_text(file_path);

    const rows = [],
      attrs = [];
    const source_row_emit = (line_number, text) => {
      const line_costs = lines[line_number];
      const self_cost = line_costs ? current_value(line_costs[0]) : 0,
        calls = line_costs ? current_value(line_costs[1]) : 0;
      const baseline_cost = line_baseline(file_path, line_number);
      const heat_style_attribute = cell_style(
        heat_of_line(self_cost, baseline_cost, line_number),
      );
      const class_names = [
        line_costs && line_number ? "clickable_" : "",
        file.callees[line_number] ? "has-callee-" : "",
      ]
        .filter(Boolean)
        .join(" ");
      attrs.push(
        `id="L${line_number}-"` +
          `${class_names ? ` class="${class_names}"` : ""}` +
          ` data-line-number-="${line_number}"`,
      );
      const call_cell = HAS_CALL_GRAPH
        ? [
            {
              text: line_share_text(calls, baseline_cost, line_number),
              style: cell_style(
                heat_of_line(calls, baseline_cost, line_number),
              ),
            },
          ]
        : [];
      rows.push([
        {
          text: line_share_text(self_cost, baseline_cost, line_number),
          style: heat_style_attribute,
        },
        { text: String(line_number), style: heat_style_attribute },
        { text, style: heat_style_attribute },
        ...call_cell,
        ...(line_costs
          ? secondary_cells(line_costs[0], line_number, (secondary) =>
              line_counter_baseline(file_path, line_number, secondary),
            )
          : secondary_counters.map(() => "")),
      ]);
    };
    const source_lines = file_source == null ? [] : file_source.split("\n");
    if (source_lines.length && source_lines[source_lines.length - 1] === "") {
      source_lines.pop();
    }
    let line_count = source_lines.length;
    for (let line_index = 0; line_index < source_lines.length; line_index++) {
      source_row_emit(line_index + 1, source_lines[line_index]);
    }
    const beyond_end_text =
      file_source == null ? "" : text_of("str_source_beyond_end");
    for (const line_key of Object.keys(lines)) {
      if (file_source != null && +line_key <= source_lines.length) continue;
      line_count = Math.max(line_count, +line_key);
      source_row_emit(+line_key, beyond_end_text);
    }

    const call_column = HAS_CALL_GRAPH
      ? [
          {
            label: text_of("str_column_calls"),
            numeric: true,
            cls: "heat-map-source-table-calls-cell-",
          },
        ]
      : [];
    const columns = [
      counter_column(current_counter, {
        cls: "heat-map-source-table-self-cell-",
      }),
      {
        label: text_of("str_column_line"),
        numeric: true,
        width:
          String(line_count).length +
          STYLE_HEAT_MAP_SOURCE_LINE_NUMBER_MARKER_WIDTH_CHARS,
        cls: "heat-map-source-table-line-number-cell-",
      },
      {
        label: text_of("str_column_source"),
        width: HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS,
        grow: true,
        cls: "heat-map-source-table-code-cell-",
      },
      ...call_column,
      ...secondary_columns(),
    ];
    markup += table_render("heat.src", columns, rows, {
      row_attributes: attrs,
      fill: 1,
      cls: "heat-map-source-table-",
      bare: true,
    });
    markup += `</div>`;
    main_panel.innerHTML = markup;
    tree_render();

    minimap_build();
    report_ui_.table_rows.attach(
      main_panel.querySelector("table.heat-map-source-table-"),
      "tr[data-line-number-]",
    );
    report_ui_.layout_activate(main_panel);
    main_panel.scrollTop = kept_scroll_top;
    information_line_refresh();
    minimap_sync();
  }

  // Shows the information line once the file box is closed or scrolled away.
  function information_line_refresh() {
    const information_line = main_panel.querySelector(
      ".heat-map-source-information-line-",
    );
    if (!information_line) return;
    const file_box = file_box_of();
    const is_box_shown =
      !!file_box &&
      design_rect_of(file_box).bottom > design_rect_of(main_panel).top;
    information_line.classList.toggle("empty_", is_box_shown);
  }
  // Opens the file box again if closed and shows the top of the view.
  function file_box_show() {
    if (!file_box_of()) {
      main_panel
        .querySelector(".heat-map-source-information-line-")
        .insertAdjacentHTML(
          "beforebegin",
          information_box_render(current_file_path, 0).markup,
        );
      report_ui_.layout_activate(file_box_of());
    }
    main_panel.scrollTop = 0;
    information_line_refresh();
    minimap_sync();
  }
  // Closes the file box and leaves the address as the address was.
  function file_box_close(file_box) {
    const box_had_focus = file_box.contains(document.activeElement);
    file_box.remove();
    information_line_refresh();
    if (box_had_focus)
      main_panel
        .querySelector(".heat-map-source-information-line- a")
        .focus({ preventScroll: true });
    minimap_sync();
  }
  // Shows what an address names in a file: the tree node, then the file box.
  function file_address_show(file_path, line) {
    tree_reveal(file_path);
    tree_render();
    tree_selected_show();
    if (!line) file_box_show();
  }

  function design_rect_of(element) {
    const rect = element.getBoundingClientRect();
    return {
      bottom: report_ui_.design_px(rect.bottom),
      height: report_ui_.design_px(rect.height),
      top: report_ui_.design_px(rect.top),
    };
  }

  function row_is_visible(row_element) {
    const row_rect = design_rect_of(row_element);
    const main_rect = design_rect_of(main_panel);
    return (
      row_rect.top >=
        main_rect.top + covered_height(row_element.closest("table")) &&
      row_rect.bottom <= main_rect.top + main_panel.clientHeight
    );
  }

  function covered_height(table_element) {
    let height = design_rect_of(table_element.tHead.rows[0].cells[0]).height;
    for (const band of main_panel.querySelectorAll(".band_")) {
      height += design_rect_of(band).height;
    }
    return height;
  }

  function row_center(row_element) {
    const cover = covered_height(row_element.closest("table"));
    const row_rect = design_rect_of(row_element);
    const main_rect = design_rect_of(main_panel);
    const detail_element = row_element.nextElementSibling;
    const block_bottom_px =
      detail_element &&
      detail_element.classList.contains("heat-map-source-line-detail-row-")
        ? design_rect_of(detail_element).bottom
        : row_rect.bottom;
    const block_height_px = block_bottom_px - row_rect.top;
    const slack = (main_panel.clientHeight - cover - block_height_px) / 2;
    main_panel.scrollTop += row_rect.top - main_rect.top - cover - slack;
  }

  let scale_factor = 1,
    clone_height_px = 0;
  function minimap_clear() {
    minimap_panel.classList.add("empty_");
    minimap_box.innerHTML = "";
    minimap_viewport.hidden = true;
  }
  function minimap_build() {
    minimap_clear();
    const table_element = main_panel.querySelector(
      "table.heat-map-source-table-",
    );
    const source_top_px = design_rect_of(
      main_panel.querySelector(".heat-map-source-"),
    ).top;
    if (
      design_rect_of(table_element).bottom - source_top_px <=
      main_panel.clientHeight
    )
      return;

    const table_body = table_element.tBodies[0];
    const clone_table = document.createElement("table");
    clone_table.className = "heat-map-source-table-";
    const clone_body = document.createElement("tbody");
    for (const row of table_body.rows) {
      if (row.classList.contains("heat-map-source-line-detail-row-")) continue;
      const code = row.querySelector("td.heat-map-source-table-code-cell-");
      if (!code) continue;
      const clone_row = document.createElement("tr");
      clone_row.className = row.className;
      clone_row.appendChild(code.cloneNode(true));
      clone_body.appendChild(clone_row);
    }
    clone_table.appendChild(clone_body);
    minimap_box.appendChild(clone_table);
    minimap_panel.classList.remove("empty_");
    minimap_viewport.hidden = false;
    clone_height_px = clone_table.offsetHeight;
    minimap_layout();
  }

  function minimap_layout() {
    if (minimap_panel.classList.contains("empty_")) return;
    const band_width_px = minimap_panel.clientWidth,
      band_height_px = main_panel.clientHeight;
    scale_factor = Math.min(
      1,
      band_width_px /
        (HEAT_MAP_MINIMAP_SOURCE_WIDTH_CHARS *
          STYLE_DESIGN_FONT_CHARACTER_WIDTH_PX),
      band_height_px / clone_height_px,
    );
    minimap_box.style.transform = `scale(${scale_factor})`;
    minimap_box.style.transformOrigin = "top left";
    minimap_box.style.width = band_width_px / scale_factor + "px";
    minimap_sync();
  }

  function geometry_measure() {
    const table_element = main_panel.querySelector(
        "table.heat-map-source-table-",
      ),
      table_body = table_element.tBodies[0];
    const main = design_rect_of(main_panel);
    const clone_body = design_rect_of(table_body);
    const detail_element = table_body.querySelector(
      "tr.heat-map-source-line-detail-row-",
    );
    const detail = detail_element && design_rect_of(detail_element);
    const rows = clone_body.height - (detail ? detail.height : 0);
    const rows_above = (y_position_px) => {
      let pixels = y_position_px - clone_body.top;
      if (detail) {
        pixels -= Math.max(
          0,
          Math.min(y_position_px, detail.bottom) - detail.top,
        );
      }
      return Math.max(0, Math.min(rows, pixels));
    };
    return {
      rows,
      above: rows_above,
      cover: covered_height(table_element),
      body: clone_body,
      detail,
      top: main.top,
      bottom: main.top + main_panel.clientHeight,
      head: design_rect_of(table_element.tHead.rows[0].cells[0]).bottom,
    };
  }
  function minimap_sync() {
    if (minimap_panel.classList.contains("empty_")) return;
    const geometry = geometry_measure(),
      scaled_height_px = clone_height_px * scale_factor;
    const row_start = geometry.above(geometry.head),
      row_end = geometry.above(geometry.bottom);
    const box_height_px = Math.max(
      HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX,
      (scaled_height_px * (row_end - row_start)) / geometry.rows,
    );
    const box_top_px = Math.min(
      scaled_height_px - box_height_px,
      (scaled_height_px * row_start) / geometry.rows,
    );
    minimap_viewport.style.top = Math.max(0, box_top_px) + "px";
    minimap_viewport.style.height = box_height_px + "px";
  }

  function scroll_to_row(row) {
    const geometry = geometry_measure();
    row = Math.max(0, Math.min(geometry.rows, row));
    let y_position_px =
      geometry.body.top -
      geometry.top +
      main_panel.scrollTop +
      row -
      geometry.cover;
    if (geometry.detail && geometry.detail.top - geometry.body.top < row) {
      y_position_px += geometry.detail.height;
    }
    const maximum_scroll_px =
      main_panel.scrollHeight - main_panel.clientHeight;
    main_panel.scrollTop = Math.max(
      0,
      Math.min(maximum_scroll_px, y_position_px),
    );
  }
  main_panel.addEventListener(
    "scroll",
    window.catch_show_throw_(minimap_sync),
  );
  main_panel.addEventListener(
    "scroll",
    window.catch_show_throw_(information_line_refresh),
  );
  // Centres the view on a pressed row outside the box, then drags the box.
  minimap_panel.addEventListener(
    "pointerdown",
    window.catch_show_throw_((press_event) => {
      if (press_event.button) return;
      press_event.preventDefault();
      const scaled_height_px = clone_height_px * scale_factor;
      if (!minimap_viewport.contains(press_event.target)) {
        const geometry = geometry_measure();
        const pressed_px =
          report_ui_.design_px(press_event.clientY) -
          design_rect_of(minimap_panel).top;
        scroll_to_row(
          (pressed_px / scaled_height_px) * geometry.rows -
            (main_panel.clientHeight - geometry.cover) / 2,
        );
        minimap_sync();
      }
      const start_top_px = minimap_viewport.offsetTop;
      minimap_viewport.classList.add("drag_");
      minimap_panel.setPointerCapture(press_event.pointerId);
      const pointer_move = window.catch_show_throw_((move_event) => {
        if (move_event.pointerId !== press_event.pointerId) return;
        scroll_to_row(
          ((start_top_px +
            report_ui_.design_px(move_event.clientY - press_event.clientY)) /
            scaled_height_px) *
            geometry_measure().rows,
        );
      });
      const pointer_release = window.catch_show_throw_((release_event) => {
        if (release_event.pointerId !== press_event.pointerId) return;
        minimap_viewport.classList.remove("drag_");
        report_ui_.listeners_bind(
          minimap_panel,
          pointer_move,
          pointer_release,
          false,
        );
      });
      report_ui_.listeners_bind(
        minimap_panel,
        pointer_move,
        pointer_release,
        true,
      );
    }),
  );

  function detail_line() {
    const detail_row = main_panel.querySelector(
      "tr.heat-map-source-line-detail-row-",
    );
    if (!detail_row) return 0;
    return +detail_row.previousElementSibling.getAttribute(
      "data-line-number-",
    );
  }

  function detail_set(line) {
    if (line === detail_line()) return;
    for (const detail_row of main_panel.querySelectorAll(
      "tr.heat-map-source-line-detail-row-",
    )) {
      detail_row.remove();
    }
    const row = line ? document.getElementById("L" + line + "-") : null;
    if (row) {
      detail_open(current_file_path, line, row);
      report_ui_.table_rows.tab_stop_set(row, false);
      if (!row_is_visible(row)) row_center(row);
    }
    minimap_sync();
  }
  function detail_close(detail_row) {
    report_ui_.table_rows.tab_stop_set(
      detail_row.previousElementSibling,
      true,
    );
    detail_row.remove();
    minimap_sync();
  }
  function detail_open(file_path, line_number, row) {
    const detail_row = document.createElement("tr");
    detail_row.className = "heat-map-source-line-detail-row-";
    detail_row.innerHTML =
      `<td colspan="${row.cells.length}">` +
      `${information_box_render(file_path, line_number).markup}</td>`;
    row.after(detail_row);
    report_ui_.layout_activate(detail_row);
  }
  // Copies or closes the information box that holds a control.
  function information_box_control_take(box_control) {
    const box_line_number = +box_control
      .closest("[data-information-box-line-]")
      .getAttribute("data-information-box-line-");
    if (box_control.getAttribute("data-information-box-action-") === "copy")
      return navigator.clipboard.writeText(
        information_box_render(current_file_path, box_line_number).copy_text,
      );
    if (box_line_number)
      detail_close(box_control.closest("tr.heat-map-source-line-detail-row-"));
    else file_box_close(file_box_of());
  }

  main_panel.addEventListener(
    "click",
    window.catch_show_throw_((click_event) => {
      const box_control = click_event.target.closest(
        "[data-information-box-action-]",
      );
      if (box_control) return information_box_control_take(box_control);
      if (click_event.target.closest("a")) return;
      const link_row = click_event.target.closest("tr.row-link-");
      if (link_row) {
        report_ui_.address.request(link_row.getAttribute("data-href-"));
        return;
      }
      const row = click_event.target.closest("tr.clickable_");
      if (row && current_file_path) {
        const line_number = +row.getAttribute("data-line-number-");
        if (line_number === detail_line())
          detail_close(row.nextElementSibling);
        else
          report_ui_.address.request(
            hash_for_line(current_file_path, line_number),
          );
      }
    }),
  );
  function ticker_tape_key_take(key_event, key_name, ticker_tape_entry) {
    if (report_ui_.widget_key.activates(key_name)) {
      key_event.preventDefault();
      if (!key_event.repeat) ticker_tape_entry.click();
      return;
    }
    const tape_entries = [
      ...ticker_tape_entry.parentElement.querySelectorAll(
        ".heat-map-source-ticker-tape-entry-",
      ),
    ];
    const entry_index = tape_entries.indexOf(ticker_tape_entry);
    let next_index = 0;
    switch (key_name) {
      case WIDGET_KEY_NAMES.down:
      case WIDGET_KEY_NAMES.right:
        next_index = entry_index + 1;
        break;
      case WIDGET_KEY_NAMES.first:
        next_index = 0;
        break;
      case WIDGET_KEY_NAMES.last:
        next_index = tape_entries.length - 1;
        break;
      case WIDGET_KEY_NAMES.left:
      case WIDGET_KEY_NAMES.up:
        next_index = entry_index - 1;
        break;
      default:
        return;
    }
    key_event.preventDefault();
    const next_entry = tape_entries[next_index];
    if (next_entry)
      report_ui_.tab_stop_move(ticker_tape_entry, next_entry, true);
  }
  main_panel.addEventListener(
    "focusin",
    window.catch_show_throw_((focus_event) => {
      const ticker_tape_entry = focus_event.target.closest(
        ".heat-map-source-ticker-tape-entry-",
      );
      if (!ticker_tape_entry) return;
      report_ui_.tab_stop_move(
        ticker_tape_entry.parentElement.querySelector(
          ':scope > [tabindex="0"]',
        ),
        ticker_tape_entry,
        false,
      );
    }),
  );
  main_panel.addEventListener(
    "keydown",
    window.catch_show_throw_((key_event) => {
      const key_name = report_ui_.widget_key.of(key_event);
      if (!key_name) return;
      const ticker_tape_entry = key_event.target.closest(
        ".heat-map-source-ticker-tape-entry-",
      );
      if (ticker_tape_entry) {
        ticker_tape_key_take(key_event, key_name, ticker_tape_entry);
        return;
      }
      const box_control = key_event.target.closest(
        "[data-information-box-action-]",
      );
      if (box_control && report_ui_.widget_key.activates(key_name)) {
        key_event.preventDefault();
        if (!key_event.repeat)
          return information_box_control_take(box_control);
        return;
      }
      if (key_name !== WIDGET_KEY_NAMES.close) return;
      const file_box = file_box_of();
      if (file_box && file_box.contains(key_event.target)) {
        key_event.preventDefault();
        file_box_close(file_box);
        return;
      }
      const detail_row = main_panel.querySelector(
        "tr.heat-map-source-line-detail-row-",
      );
      if (!detail_row) return;
      const is_in_detail =
        detail_row.contains(key_event.target) ||
        detail_row.previousElementSibling === key_event.target;
      if (!is_in_detail) return;
      key_event.preventDefault();
      detail_close(detail_row);
    }),
  );

  let rendered_line = 0;
  let rendered_key = "";
  let routed_hash = null;
  function counter_apply(key) {
    current_counter = counter_find(key);
    scale_recompute();
    tree_root = tree_build();
    for (const directory_node of tree_root.dirs.values()) {
      if (
        absolute(directory_node.self) / total_cost >
        HEAT_MAP_TREE_AUTO_EXPAND_ABOVE_SHARE
      ) {
        expanded_directories.add(directory_node.path);
      }
    }
  }
  function scale_apply(scale_value) {
    active_scale = SCALE_CHOICES.find((entry) => entry.value === scale_value);
  }
  function stored_choice_of(choices, storage_key, default_value) {
    const stored_value = view_storage.value_read(storage_key);
    const is_offered = choices.some((choice) => choice.value === stored_value);
    return is_offered ? stored_value : default_value;
  }
  function strip_preferences_apply() {
    if (shown_test_name === null) return;
    const stored_sort_mode = sort_mode_stored();
    if (stored_sort_mode !== sort_mode) {
      sort_mode = stored_sort_mode;
      tree_render();
    }
    const stored_scale_value = scale_value_stored(),
      stored_counter_key = counter_key_stored();
    if (
      stored_scale_value !== active_scale.value ||
      stored_counter_key !== current_counter.key
    ) {
      scale_apply(stored_scale_value);
      if (stored_counter_key !== current_counter.key)
        counter_apply(stored_counter_key);
      rendered_key = "";
      route_render();
    }
    heat_strip_render();
  }
  // Builds a strip entry whose cell is a text pulldown of choices.
  function strip_pulldown_entry_of(
    entry_name,
    label_text,
    choices,
    on_select,
  ) {
    return report_ui_.strip.entry_make(entry_name, "pulldown", label_text, {
      pulldown_options: {
        box_width_chars:
          Math.max(...choices.map((choice) => choice.label.length)) +
          STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS,
        entries_of: () => report_ui_.strip.choice_entries_of(choices),
        on_close: () => {},
        on_select,
        reads_line_number: false,
      },
    });
  }
  // Builds the counter pulldown entry the strip and the home headings share.
  function counter_entry_of(label_text) {
    return strip_pulldown_entry_of(
      "counter",
      label_text,
      counter_choices,
      counter_choose,
    );
  }
  const sort_label_of = (shown_sort_mode) =>
    SORT_CHOICES.find((choice) => choice.value === shown_sort_mode).label;
  // Renders the strip again, which closes its pulldowns and drops its focus.
  function heat_strip_render() {
    heat_strip_handle = report_ui_.strip.render(
      heat_strip,
      [
        counter_entry_of(counter_label(current_counter)),
        strip_pulldown_entry_of(
          "scale",
          active_scale.label,
          SCALE_CHOICES,
          scale_choose,
        ),
        strip_pulldown_entry_of(
          "sort",
          sort_label_of(sort_mode),
          SORT_CHOICES,
          sort_choose,
        ),
      ],
      [],
    );
  }
  // Stores and shows a counter chosen in the strip or in a home heading.
  function counter_choose(counter_key) {
    view_storage.value_write("heat.counter", counter_key);
    counter_apply(counter_key);
    route_render();
    heat_strip_handle.pulldown_label_set(
      "counter",
      counter_label(current_counter),
    );
  }
  // Stores and shows a scale chosen in the strip.
  function scale_choose(scale_value) {
    view_storage.value_write("heat.scale", scale_value);
    scale_apply(scale_value);
    rendered_key = "";
    route_render();
    heat_strip_handle.pulldown_label_set("scale", active_scale.label);
  }
  // Stores and shows a tree order chosen in the strip.
  function sort_choose(chosen_sort_mode) {
    view_storage.value_write("heat.sort", chosen_sort_mode);
    sort_mode = chosen_sort_mode;
    tree_render();
    heat_strip_handle.pulldown_label_set("sort", sort_label_of(sort_mode));
  }
  function pulldown_text_lists(names_key, entry_name) {
    if (!window.report_pulldown_text_)
      throw new Error(text_of("str_error_pulldown_text_missing"));
    return window.report_pulldown_text_[names_key].includes(entry_name);
  }
  function no_samples_note_render(unsampled_name) {
    current_file_path = null;
    scope_totals = null;
    const note = text_fill("str_no_samples_in_test", { name: unsampled_name });
    main_panel.innerHTML =
      `<div class="heat-map-source-unavailable-note-">` +
      `${html_escape(note)}</div>`;
    main_panel.scrollTop = 0;
    tree_render();
    minimap_clear();
  }
  function line_clamp(addressed_line) {
    const source_rows = main_panel.querySelectorAll("tr[data-line-number-]");
    let clamped_line = 0;
    for (const source_row of source_rows) {
      const row_line = +source_row.getAttribute("data-line-number-");
      if (row_line > 0 && (row_line <= addressed_line || !clamped_line))
        clamped_line = row_line;
    }
    return clamped_line;
  }
  function main_focus_restore(main_had_focus) {
    if (!main_had_focus || main_panel.contains(document.activeElement)) return;
    const addressed_row = rendered_line
      ? document.getElementById("L" + rendered_line + "-")
      : null;
    if (addressed_row) report_ui_.table_rows.tab_stop_set(addressed_row, true);
    else main_panel.focus({ preventScroll: true });
  }
  function route_render() {
    const main_had_focus =
      document.hasFocus() && main_panel.contains(document.activeElement);
    const page_address = report_ui_.address.of_hash(location.hash);
    if (page_address.view !== HEAT_MAP_VIEW_ENTRY[0])
      throw new Error(
        window.ui_strings_.text_fill("str_error_hash_view_mismatch", [
          HEAT_MAP_VIEW_ENTRY[0],
        ]),
      );
    if (page_address.test !== shown_test_name) {
      model_load(page_address.test);
      return;
    }
    const is_new_address = location.hash !== routed_hash;
    routed_hash = location.hash;
    let file = page_address.file,
      line = page_address.line === null ? 0 : page_address.line,
      fn = page_address.function;
    let unsampled_name = null;
    if (fn) {
      const function_entry = function_table.find(
        (candidate) => candidate.name === fn,
      );
      if (
        function_entry &&
        function_entry.line &&
        file_table[function_entry.file]
      ) {
        file = function_entry.file;
        line = function_entry.line;
      } else if (pulldown_text_lists("functions", fn)) {
        unsampled_name = fn;
      } else {
        throw new Error(
          window.ui_strings_.text_fill("str_error_hash_function_unknown", [
            fn,
          ]),
        );
      }
    } else if (file && !file_table[file]) {
      if (!pulldown_text_lists("files", file)) {
        throw new Error(
          window.ui_strings_.text_fill("str_error_hash_file_unknown", [file]),
        );
      }
      unsampled_name = file;
    }
    if (unsampled_name) {
      rendered_key = "";
      no_samples_note_render(unsampled_name);
      rendered_line = line;
      main_focus_restore(main_had_focus);
      return;
    }

    const key =
      (file ? "file\n" + file : "home") +
      "\n" +
      current_counter.key +
      "\n" +
      active_scale.value;
    if (key !== rendered_key) {
      rendered_key = key;
      if (file) file_render(file);
      else home_render();
    }
    if (file) {
      if (line) line = line_clamp(line);
      detail_set(line);
      if (is_new_address) file_address_show(file, line);
    }
    rendered_line = line;
    main_focus_restore(main_had_focus);
  }
  function model_load(test_name) {
    const held_models = window[HEAT_MAP_MODEL_GLOBAL_NAME];
    if (held_models && held_models[test_name]) {
      model_switch(test_name, held_models[test_name]);
      route_render();
      return;
    }
    const model_script = document.createElement("script");
    model_script.src =
      HEAT_MAP_MODEL_DIR_NAME + "/" + encodeURIComponent(test_name) + ".js";
    model_script.addEventListener(
      "error",
      window.catch_show_throw_(() => {
        throw new Error(
          window.ui_strings_.text_fill("str_error_hash_test_unknown", [
            test_name,
          ]),
        );
      }),
    );
    model_script.addEventListener(
      "load",
      window.catch_show_throw_(() => {
        const loaded_models = window[HEAT_MAP_MODEL_GLOBAL_NAME];
        if (!loaded_models || !loaded_models[test_name])
          throw new Error(
            window.ui_strings_.text_fill("str_error_heat_map_unfiled", [
              test_name,
            ]),
          );
        route_render();
      }),
    );
    document.head.append(model_script);
  }
  function model_switch(test_name, test_model) {
    if (shown_test_name === null) report_kind_set(test_model);
    shown_test_name = test_name;
    profile_model = test_model;
    file_table = test_model.files;
    function_table = test_model.functions;
    function_baselines = test_model.functionBaseline || [];
    file_baselines = test_model.fileBaseline || {};
    HAS_CALL_GRAPH = function_table.some(
      (function_entry) => function_entry.callers.length > 0,
    );
    per_function_calls = function_table.map((function_entry) =>
      function_entry.callers.reduce(
        (running_total, caller) => running_total + caller[4],
        0,
      ),
    );
    CALLS_TOTAL =
      per_function_calls.reduce(
        (running_total, call_count) => running_total + call_count,
        0,
      ) || 1;
    entry_line_index = {};
    function_table.forEach((function_entry, index) => {
      if (!function_entry.line) return;
      entry_line_index[function_entry.file] =
        entry_line_index[function_entry.file] || {};
      entry_line_index[function_entry.file][function_entry.line] = index;
    });
    counters_build();
    expanded_directories.clear();
    expanded_cold_groups.clear();
    current_file_path = null;
    scope_totals = null;
    rendered_key = "";
    counter_apply(counter_key_stored());
    heat_strip_render();
  }
  function address_recenter() {
    if (!current_file_path) {
      rendered_key = "";
      route_render();
      return;
    }
    file_address_show(current_file_path, rendered_line);
    if (!rendered_line) return;
    detail_set(rendered_line);
    row_center(document.getElementById("L" + rendered_line + "-"));
  }

  let tree_push_off_px = 0,
    press_push_off_px = null;
  // Shifts the layout left so the left part of the tree leaves the window.
  function tree_push_off_set(push_off_px) {
    tree_push_off_px = Math.min(
      tree_pane.offsetWidth,
      Math.max(0, push_off_px),
    );
    layout_box.style.marginLeft = -tree_push_off_px + "px";
  }
  // Pushes the tree off the left edge by a sideways drag on the tree itself.
  function tree_surface_travel_take(travel_screen_px, is_release) {
    if (press_push_off_px === null) press_push_off_px = tree_push_off_px;
    tree_push_off_set(
      press_push_off_px - report_ui_.design_px(travel_screen_px),
    );
    if (is_release) press_push_off_px = null;
  }
  // Feeds the sideways travel of a drag on a surface to a taker.
  function sideways_drag_attach(surface_element, travel_take) {
    surface_element.addEventListener(
      "pointerdown",
      window.catch_show_throw_((press_event) => {
        if (
          press_event.button ||
          press_event.defaultPrevented ||
          report_ui_.slide_cell_of(press_event)
        )
          return;
        let is_sideways = false,
          travel_screen_px = 0;
        const pointer_move = window.catch_show_throw_((move_event) => {
          if (move_event.pointerId !== press_event.pointerId) return;
          if (!move_event.buttons) return pointer_release(move_event);
          travel_screen_px = move_event.clientX - press_event.clientX;
          if (!is_sideways) {
            const drag_direction = report_ui_.drag_direction_of(
              press_event,
              move_event,
            );
            if (!drag_direction) return;
            if (drag_direction === "vertical") return listeners_set(false);
            is_sideways = true;
          }
          travel_take(travel_screen_px, false);
        });
        const pointer_release = window.catch_show_throw_((release_event) => {
          if (release_event.pointerId !== press_event.pointerId) return;
          listeners_set(false);
          if (is_sideways) travel_take(travel_screen_px, true);
        });
        function listeners_set(is_listening) {
          report_ui_.listeners_bind(
            window,
            pointer_move,
            pointer_release,
            is_listening,
          );
        }
        listeners_set(true);
      }),
    );
  }
  // Takes the tree back to the left edge, then applies the stored choices.
  function layout_reset_apply() {
    tree_push_off_set(0);
    strip_preferences_apply();
  }
  const tree_splitter = report_ui_.pane_splitter.attach(
    tree_scrollbar,
    tree_pane,
    "heat.tree",
    STYLE_HEAT_MAP_TREE_PANE_NARROWEST_CHARS,
    STYLE_HEAT_MAP_TREE_PANE_WIDEST_CHARS,
  );
  report_ui_.text_scrollbar.attach(tree_scrollbar, tree_panel, "vertical");
  report_ui_.text_scrollbar.attach(main_scrollbar, main_panel, "vertical");
  report_ui_.drag_scroll.attach(tree_panel, tree_panel);
  report_ui_.drag_scroll.attach(main_panel, main_panel);
  sideways_drag_attach(tree_panel, tree_surface_travel_take);
  sideways_drag_attach(main_panel, tree_splitter.travel_take);
  // Keeps the push off within the tree whenever the tree pane changes width.
  new ResizeObserver(
    window.catch_show_throw_(() => tree_push_off_set(tree_push_off_px)),
  ).observe(tree_pane);

  window.addEventListener(
    "hashchange",
    window.catch_show_throw_(route_render),
  );
  report_ui_.view_activate({
    forwards_input: true,
    preferences_apply: layout_reset_apply,
    recenter: address_recenter,
  });

  let resize_debounce_timer = null;
  window.addEventListener(
    "resize",
    window.catch_show_throw_(() => {
      clearTimeout(resize_debounce_timer);
      resize_debounce_timer = setTimeout(
        window.catch_show_throw_(() => {
          minimap_layout();
          information_line_refresh();
          if (shown_test_name !== null) heat_strip_render();
        }),
        LAYOUT_RESIZE_SETTLE_DELAY_MS,
      );
    }),
  );
  route_render();
})();
