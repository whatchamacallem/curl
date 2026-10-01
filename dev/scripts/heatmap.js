window.catch_show_throw(function () {
  "use strict";

  const HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX = settings(
    "HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX",
  );
  const HEAT_MAP_HOME_LINES_LOCATION_MAX_CHARS = settings(
    "HEAT_MAP_HOME_LINES_LOCATION_MAX_CHARS",
  );
  const HEAT_MAP_HOME_LINES_SOURCE_COLUMN_MAX_CHARS = settings(
    "HEAT_MAP_HOME_LINES_SOURCE_COLUMN_MAX_CHARS",
  );
  const HEAT_MAP_HOME_LINES_SOURCE_SNIPPET_MAX_CHARS = settings(
    "HEAT_MAP_HOME_LINES_SOURCE_SNIPPET_MAX_CHARS",
  );
  const HEAT_MAP_HOME_TABLE_MAX_ROWS = settings(
    "HEAT_MAP_HOME_TABLE_MAX_ROWS",
  );
  const HEAT_MAP_MINIMAP_SOURCE_WIDTH_CHARS = settings(
    "HEAT_MAP_MINIMAP_SOURCE_WIDTH_CHARS",
  );
  const HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX = settings(
    "HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX",
  );
  const HEAT_MAP_MODEL_DIR_NAME = settings("HEAT_MAP_MODEL_DIR_NAME");
  const HEAT_MAP_MODEL_GLOBAL_NAME = settings("HEAT_MAP_MODEL_GLOBAL_NAME");
  const HEAT_MAP_SECONDARY_COUNTER_NAMES = settings(
    "HEAT_MAP_SECONDARY_COUNTER_NAMES",
  );
  const HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_LEAST_SHARE = settings(
    "HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_LEAST_SHARE",
  );
  const HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_MAX_COUNT = settings(
    "HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_MAX_COUNT",
  );
  const HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS = settings(
    "HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS",
  );
  const HEAT_MAP_TREE_AUTO_EXPAND_ABOVE_SHARE = settings(
    "HEAT_MAP_TREE_AUTO_EXPAND_ABOVE_SHARE",
  );
  const HEAT_MAP_VIEW_ENTRY = settings("HEAT_MAP_VIEW_ENTRY");
  const LAYOUT_RESIZE_SETTLE_DELAY_MS = settings(
    "LAYOUT_RESIZE_SETTLE_DELAY_MS",
  );
  const RANKING_COUNTER_NAME = settings("RANKING_COUNTER_NAME");
  const STYLE_DESIGN_FONT_CHARACTER_WIDTH_PX = settings(
    "STYLE_DESIGN_FONT_CHARACTER_WIDTH_PX",
  );
  const STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE = settings(
    "STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE",
  );
  const STYLE_HEAT_COLOR_FULL_SCALE_PERCENT = settings(
    "STYLE_HEAT_COLOR_FULL_SCALE_PERCENT",
  );
  const STYLE_HEAT_MAP_MENU_DROPDOWN_EXTRA_WIDTH_CHARS = settings(
    "STYLE_HEAT_MAP_MENU_DROPDOWN_EXTRA_WIDTH_CHARS",
  );
  const STYLE_HEAT_MAP_SOURCE_LINE_NUMBER_MARKER_WIDTH_CHARS = settings(
    "STYLE_HEAT_MAP_SOURCE_LINE_NUMBER_MARKER_WIDTH_CHARS",
  );
  const STYLE_HEAT_MAP_TREE_INDENT_PER_LEVEL_CHARS = settings(
    "STYLE_HEAT_MAP_TREE_INDENT_PER_LEVEL_CHARS",
  );
  const STYLE_HEAT_MAP_TREE_PANE_NARROWEST_PX = settings(
    "STYLE_HEAT_MAP_TREE_PANE_NARROWEST_PX",
  );
  const STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS = settings(
    "STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS",
  );
  const STYLE_TABLE_LOCATION_COLUMN_MAX_CHARS = settings(
    "STYLE_TABLE_LOCATION_COLUMN_MAX_CHARS",
  );
  const WIDGET_KEY_NAMES = settings("WIDGET_KEY_NAMES");
  // the model on show, its two tables and its test, each null until
  // model_switch puts the first model on show
  let profile_model = null,
    file_table = null,
    function_table = null,
    shown_test_name = null;
  const tree_panel = document.getElementById("heat-map-tree-");
  const main_panel = document.getElementById("heat-map-main-");
  const minimap_panel = document.getElementById("heat-map-minimap-");
  const minimap_box = document.getElementById("heat-map-minimap-box-");
  const minimap_viewport = document.getElementById(
    "heat-map-minimap-viewport-",
  );
  const view_storage = report_ui.view_storage;
  let sort_mode = null;
  let current_file_path = null,
    search_query = "";
  const sort_select = document.getElementById("heat-map-menu-tree-select-");
  // the tree order storage holds, else by heat
  const sort_mode_stored = () =>
    stored_choice_of(sort_select, "heat.sort", "heat");
  document.getElementById("heat-map-menu-counter-label-").textContent =
    window.ui_strings.text_of("str_heat_map_menu_counter");
  document.getElementById("heat-map-menu-scale-label-").textContent =
    window.ui_strings.text_of("str_heat_map_menu_scale");
  document.getElementById("heat-map-menu-tree-label-").textContent =
    window.ui_strings.text_of("str_heat_map_menu_tree");
  document.getElementById("heat-map-menu-search-label-").textContent =
    window.ui_strings.text_of("str_heat_map_menu_search");
  sort_select.options[0].textContent =
    window.ui_strings.text_of("str_sort_by_heat");
  sort_select.options[1].textContent =
    window.ui_strings.text_of("str_sort_by_name");
  document.getElementById("heat-map-menu-search-box-").placeholder =
    window.ui_strings.text_of("str_search_placeholder");
  tree_panel.setAttribute(
    "aria-label",
    window.ui_strings.text_of("str_heat_map_tree_label"),
  );
  main_panel.setAttribute(
    "aria-label",
    window.ui_strings.text_of("str_heat_map_main_label"),
  );
  sort_mode_apply(sort_mode_stored());
  tree_panel.style.minWidth = STYLE_HEAT_MAP_TREE_PANE_NARROWEST_PX + "px";
  report_ui.pane_splitter.attach(
    document.getElementById("heat-map-tree-resize-handle-"),
    tree_panel,
    "heat.tree",
    STYLE_HEAT_MAP_TREE_PANE_NARROWEST_PX,
  );

  const vector_at = (cost_vector, index) =>
    cost_vector && index < cost_vector.length ? cost_vector[index] : 0;
  // the model on show's counters, recorded then derived, and those shown
  // beside the selected one; counters_build makes both
  let counter_list = null,
    secondary_counters = null;
  const counter_find = (key) =>
    counter_list.find((counter) => counter.key === key);
  // the generator proved the default is a column that script emitted, and a
  // stored counter is shown only where the pulldown offers it
  let current_counter = null;

  const text_of = window.ui_strings.text_of;
  const text_fill = window.ui_strings.text_fill;
  const counter_label = (counter) =>
    text_of(
      HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX +
        counter.key.toLowerCase(),
    ) +
    " / " +
    counter.key;
  const counter_select = document.getElementById(
    "heat-map-menu-counter-select-",
  );
  // the counter storage holds, else the one the model opens on
  const counter_key_stored = () =>
    stored_choice_of(
      counter_select,
      "heat.counter",
      profile_model.heatMapTotals.defaultCounter,
    );
  // Build the model on show's counters and offer each in the counter
  // pulldown, sized to the longest.
  function counters_build() {
    counter_list = [];
    profile_model.heatMapTotals.counters.forEach((name, index) => {
      counter_list.push({
        key: name,
        get: (cost_vector) => vector_at(cost_vector, index),
        contributing_counters: [],
      });
    });
    for (const [name, terms] of profile_model.heatMapTotals.derived) {
      const get = (cost_vector) =>
        terms.reduce(
          (running_total, term) =>
            running_total + term[0] * vector_at(cost_vector, term[1]),
          0,
        );
      // the recorded counters fill counter_list's first slots in cost-vector
      // order, so a term's slot is the index of the counter it reads
      counter_list.push({
        key: name,
        get,
        derived: true,
        contributing_counters: terms.map((term) => counter_list[term[1]]),
      });
    }
    secondary_counters =
      HEAT_MAP_SECONDARY_COUNTER_NAMES.map(counter_find).filter(Boolean);
    let counter_label_width = 0;
    counter_select.replaceChildren();
    for (const counter of counter_list) {
      const option = document.createElement("option");
      option.value = counter.key;
      option.textContent = counter_label(counter);
      counter_label_width = Math.max(
        counter_label_width,
        option.textContent.length,
      );
      counter_select.appendChild(option);
    }
    counter_select.style.width =
      counter_label_width +
      STYLE_HEAT_MAP_MENU_DROPDOWN_EXTRA_WIDTH_CHARS +
      "ch";
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
  let share_text = report_ui.percent_text;
  const share_of_total_text = (value) => share_text(share_of_total(value));

  let human_text = report_ui.human_text;
  const cell_number = (value) => ({
    text: human_text(value),
  });
  let HEADING_PREFIX = text_of("str_heading_prefix_self"),
    TICKER_TAPE_HEADING = text_of("str_ticker_tape_heading_self");
  const SELF_COLUMN = {
    label: text_of("str_column_self"),
    numeric: true,
  };
  // whether the model on show records who called whom, set by model_switch
  let HAS_CALL_GRAPH = null;

  // whether the report is a diff, set from its first model by
  // report_kind_set, and the model on show's baseline costs
  let IS_DIFF = null;
  let function_baselines = null,
    file_baselines = null;
  let counter_baseline_of = () => null;
  let heat_position_of = (heat_value) => heat_value;
  let share_of_baseline = (value, baseline_cost) => share_of_total(value);
  let scope_choices_build = () => [
    ["global", text_of("str_scope_global")],
    ["file", text_of("str_scope_file")],
    ["function", text_of("str_scope_function")],
  ];
  let secondary_share = (value, counter, baseline_cost, line_number) =>
    share_in_scope(value, counter, line_number);
  let line_share = (value, baseline_cost, line_number) =>
    share_in_scope(value, current_counter, line_number);
  let line_share_text = (value, baseline_cost, line_number) =>
    share_in_scope_text(value, current_counter, line_number);
  let heat_signed = (curved) => curved;
  let secondary_percent_of_file = (self_cost, file_path, secondary) =>
    (100 * self_cost) / secondary_totals[secondary.key];
  let secondary_percent_of_cell = (
    self_cost,
    secondary,
    line_number,
    baseline_lookup,
  ) =>
    line_number != null
      ? share_in_scope(self_cost, secondary, line_number)
      : (100 * self_cost) / secondary_totals[secondary.key];
  // Set what a diff changes, then the scale pulldown its scopes decide, from
  // the first model, as every model one report holds is a diff, or none is.
  function report_kind_set(first_model) {
    IS_DIFF = !!first_model.heatMapTotals.diff;
    if (IS_DIFF) {
      share_text = report_ui.signed_percent_text;
      human_text = report_ui.signed_human_text;
      HEADING_PREFIX = text_of("str_heading_prefix_diff");
      TICKER_TAPE_HEADING = text_of("str_ticker_tape_heading_diff");
      counter_baseline_of = (cost_vector, counter) => {
        if (!cost_vector) return null;
        const baseline_cost = absolute(counter.get(cost_vector));
        return baseline_cost ? baseline_cost : null;
      };
      share_of_baseline = report_ui.diff_share_of;
      scope_choices_build = () => [["line", text_of("str_scope_line")]];
      secondary_share = (value, counter, baseline_cost) =>
        share_of_baseline(value, baseline_cost);
      line_share = (value, baseline_cost) =>
        share_of_baseline(value, baseline_cost);
      line_share_text = (value, baseline_cost) =>
        share_of_baseline_text(value, baseline_cost);
      heat_signed = (curved, percent) => (percent < 0 ? -curved : curved);
      heat_position_of = (heat_value) => (heat_value + 1) * 0.5;
      secondary_percent_of_file = (self_cost, file_path, secondary) =>
        share_of_baseline(
          self_cost,
          file_counter_baseline(file_path, secondary),
        );
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
    scale_pulldown_fill();
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

  const scale_select = document.getElementById("heat-map-menu-scale-select-");
  const CURVE_CHOICES = [
    ["log", text_of("str_scale_curve_log")],
    ["linear", text_of("str_scale_curve_linear")],
  ];
  // every curve with every scope the report's kind has, and the one on
  // show, from the first model on
  const SCALE_CHOICES = [];
  let active_scale = null;
  // the scale storage holds, else the first
  const scale_value_stored = () =>
    stored_choice_of(scale_select, "heat.scale", SCALE_CHOICES[0].value);
  // Offer every curve with every scope in the scale pulldown, sized to the
  // longest, on the stored one. Run once, by report_kind_set.
  function scale_pulldown_fill() {
    const scope_choices = scope_choices_build();
    CURVE_CHOICES.forEach((curve) => {
      scope_choices.forEach((scope) =>
        SCALE_CHOICES.push({
          value: curve[0] + "/" + scope[0],
          curve: curve[0],
          scope: scope[0],
          label:
            scope_choices.length > 1
              ? text_fill("str_scale_entry", {
                  curve: curve[1],
                  scope: scope[1],
                })
              : curve[1],
        }),
      );
    });
    let scale_label_width = 0;
    SCALE_CHOICES.forEach((entry) => {
      const option = document.createElement("option");
      option.value = entry.value;
      option.textContent = entry.label;
      scale_select.appendChild(option);
      scale_label_width = Math.max(scale_label_width, entry.label.length);
    });
    scale_select.style.width =
      scale_label_width +
      STYLE_HEAT_MAP_MENU_DROPDOWN_EXTRA_WIDTH_CHARS +
      "ch";
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
  const secondary_share_text = (value, counter, baseline_cost, line_number) =>
    value
      ? share_text(secondary_share(value, counter, baseline_cost, line_number))
      : "";
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

  const ramp_channels_at = report_ui.ramp_channels_at;
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
  // each function's call count in the model on show, and their sum
  let per_function_calls = null,
    CALLS_TOTAL = null;
  const call_count_cell = (call_count) =>
    call_count
      ? {
          text: human_text(call_count),
          style: cell_style(heat_of_share((100 * call_count) / CALLS_TOTAL)),
        }
      : "";

  // The hash of an address in the test on show, a file's line, the whole
  // file when line is left out or 0, or a function.
  const hash_for_line = (file_path, line) =>
    report_ui.address.hash_of({
      test: shown_test_name,
      view: HEAT_MAP_VIEW_ENTRY[0],
      file: file_path,
      line: line || null,
    });
  const hash_for_function = (name) =>
    report_ui.address.hash_of({
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
    const sources = window.report_sources;
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

  const cell_normalize = (value) =>
    value && typeof value === "object"
      ? value
      : { text: value == null ? "" : String(value) };

  function table_render(key, columns, rows, options) {
    options = options || {};
    const cell_rows = rows.map((row) => row.map(cell_normalize));
    const grow_index = options.fill
      ? columns.findIndex((column) => column.grow)
      : -1;
    const column_limit_list = report_ui
      .column_extents(columns, cell_rows, grow_index)
      .map(report_ui.column_limits);
    const table_classes = [
      "columns_",
      options.fill ? "fill_" : "",
      options.cls || "",
    ]
      .filter(Boolean)
      .join(" ");
    let markup = options.bare
      ? ""
      : `<div class="table-box-${options.fill ? " fill_" : ""}">`;
    markup +=
      `<div class="table-columns-"><table class="${table_classes}"` +
      ` data-key-="${html_escape(key)}"><colgroup>`;
    column_limit_list.forEach((limit, column_index) => {
      const column_classes = [
        column_index % 2 ? "alternate_" : "",
        column_index === grow_index ? "grow_" : "",
      ]
        .filter(Boolean)
        .join(" ");
      const width_text = report_ui.column_width_text(
        column_limit_list,
        column_index,
        grow_index,
      );
      markup +=
        `<col${column_classes ? ` class="${column_classes}"` : ""}` +
        ` data-min-="${limit[0]}ch" style="width:${width_text}">`;
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

  function table_markdown(columns, rows) {
    const cell_rows = rows.map((row) => row.map(cell_normalize));
    const column_width_list = columns.map((column, column_index) =>
      Math.max(
        column.label.length,
        report_ui.column_longest(cell_rows, column_index),
      ),
    );
    const pad = (text, width, numeric) =>
      numeric ? text.padStart(width) : text.padEnd(width);
    const line = (cells) =>
      "| " +
      cells
        .map((text, column_index) =>
          pad(
            text,
            column_width_list[column_index],
            columns[column_index].numeric,
          ),
        )
        .join(" | ") +
      " |";
    const output_parts = [line(columns.map((column) => column.label))];
    const rule = columns.map((column, column_index) =>
      column.numeric
        ? "-".repeat(column_width_list[column_index] - 1) + ":"
        : "-".repeat(column_width_list[column_index]),
    );
    output_parts.push("| " + rule.join(" | ") + " |");
    for (const row of cell_rows) {
      output_parts.push(
        line(
          columns.map(
            (column, column_index) =>
              (row[column_index] && row[column_index].text) || "",
          ),
        ),
      );
    }
    return output_parts.join("\n");
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
  function path_matches(file_path) {
    return !search_query || file_path.toLowerCase().includes(search_query);
  }
  function subtree_matches(tree_node) {
    if (!search_query) return true;
    for (const file of tree_node.files) {
      if (path_matches(file.path)) return true;
    }
    for (const directory_node of tree_node.dirs.values())
      if (subtree_matches(directory_node)) return true;
    return false;
  }
  const caret_of = (is_expanded) =>
    text_of(is_expanded ? "str_caret_down" : "str_caret_right");
  // a node's part in the tree view pattern, a treeitem at its level, a tab
  // stop only once tree_tab_stop_place or a focus makes that node the one
  const treeitem_attributes_of = (node_level) =>
    ` role="treeitem" aria-level="${node_level}" tabindex="-1"`;
  function tree_render() {
    const output_parts = [];
    function nodes_emit(tree_node, depth) {
      const indent_chars = depth * STYLE_HEAT_MAP_TREE_INDENT_PER_LEVEL_CHARS;
      const directories = [...tree_node.dirs.values()]
        .filter(subtree_matches)
        .sort(node_compare);
      for (const directory_node of directories) {
        const is_expanded = search_query
          ? true
          : expanded_directories.has(directory_node.path);
        const heat_style_attribute = cell_style(
          heat_of_delta(directory_node.self, directory_node.base),
        );
        output_parts.push(
          `<div class="heat-map-tree-node- dir_` +
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
      const file_list = tree_node.files
        .filter((file) => path_matches(file.path))
        .sort(node_compare);
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
        const is_expanded = search_query
          ? true
          : expanded_cold_groups.has(tree_node.path);
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
        // its files a group of its children, drawn at its own indent
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
  // the selector of the node focus was last on, kept across renders
  let tree_focus_selector = null;
  // the attribute each kind of node carries its key in, its path
  const TREE_NODE_KEY_ATTRIBUTE_NAMES = [
    "data-dir-",
    "data-file-",
    "data-more-",
  ];
  // The selector finding a node again after a render, by its key attribute.
  function tree_node_selector_of(tree_node) {
    const key_attribute_name = TREE_NODE_KEY_ATTRIBUTE_NAMES.find(
      (attribute_name) => tree_node.hasAttribute(attribute_name),
    );
    const key_value = CSS.escape(tree_node.getAttribute(key_attribute_name));
    return `.heat-map-tree-node-[${key_attribute_name}="${key_value}"]`;
  }
  // The tree's nodes on show, in order, none inside a closed group.
  function tree_visible_nodes() {
    return [...tree_panel.querySelectorAll(".heat-map-tree-node-")].filter(
      (tree_node) =>
        !tree_node.closest(".heat-map-tree-node-child-group-:not(.open_)"),
    );
  }
  // The node a node sits in, null at the tree's top level.
  function tree_parent_of(tree_node) {
    const holding_group = tree_node.parentElement.closest(
      ".heat-map-tree-node-child-group-",
    );
    return holding_group ? holding_group.previousElementSibling : null;
  }
  // The first node in an open node's group.
  const tree_first_child_of = (tree_node) =>
    tree_node.nextElementSibling.querySelector(
      ":scope > .heat-map-tree-node-",
    );
  // Put the tree's one tab stop on the node focus was on while the tree
  // holds it, else on the file on show, else on the first node on show.
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
    if (tab_stop) report_ui.tab_stop_move(null, tab_stop, takes_focus);
  }
  // A key on a node, the tree view pattern's. Up and Down walk the nodes on
  // show, Right and Left open, enter, close or leave one, Home and End.
  function tree_key_take(key_event, key_name, tree_node) {
    if (report_ui.widget_key.activates(key_name)) {
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
        // an open node closes as a click does, unless a search holds every
        // group open; any other goes to its parent
        if (is_open && !search_query) tree_node.click();
        else next_node = tree_parent_of(tree_node);
        break;
      case WIDGET_KEY_NAMES.right:
        // a closed node opens as a click does; an open one enters its group
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
    if (next_node) report_ui.tab_stop_move(tree_node, next_node, true);
  }
  // a focused node, by key or pointer, becomes the tree's one tab stop
  tree_panel.addEventListener(
    "focusin",
    window.catch_show_throw((focus_event) => {
      const tree_node = focus_event.target.closest(".heat-map-tree-node-");
      if (!tree_node) return;
      tree_focus_selector = tree_node_selector_of(tree_node);
      report_ui.tab_stop_move(
        tree_panel.querySelector('.heat-map-tree-node-[tabindex="0"]'),
        tree_node,
        false,
      );
    }),
  );
  tree_panel.addEventListener(
    "keydown",
    window.catch_show_throw((key_event) => {
      const key_name = report_ui.widget_key.of(key_event);
      const tree_node = key_event.target.closest(".heat-map-tree-node-");
      if (key_name && tree_node) tree_key_take(key_event, key_name, tree_node);
    }),
  );
  tree_panel.addEventListener(
    "click",
    window.catch_show_throw((click_event) => {
      const tree_node = click_event.target.closest(".heat-map-tree-node-");
      if (!tree_node) return;
      if (tree_node.getAttribute("data-dir-") != null) {
        const file_path = tree_node.getAttribute("data-dir-");
        if (expanded_directories.has(file_path)) {
          expanded_directories.delete(file_path);
        } else expanded_directories.add(file_path);
        tree_render();
        // a search shows every group open, so a click there reveals none
        if (!search_query && expanded_directories.has(file_path))
          group_opening_show(tree_node);
      } else if (tree_node.getAttribute("data-more-") != null) {
        const file_path = tree_node.getAttribute("data-more-");
        if (expanded_cold_groups.has(file_path)) {
          expanded_cold_groups.delete(file_path);
        } else expanded_cold_groups.add(file_path);
        tree_render();
        if (!search_query && expanded_cold_groups.has(file_path))
          group_opening_show(tree_node);
      } else if (tree_node.getAttribute("data-file-") != null) {
        if (tree_node.classList.contains("cold_")) return;
        report_ui.address.request(
          hash_for_line(tree_node.getAttribute("data-file-")),
        );
      }
    }),
  );
  // Scroll the group a node just opened to the tree's top when that group
  // runs past the tree's visible bottom, the rows above scrolled off the top.
  function group_opening_show(clicked_node) {
    const opened_node = tree_panel.querySelector(
      tree_node_selector_of(clicked_node),
    );
    const tree_rect = design_rect_of(tree_panel);
    const group_rect = design_rect_of(opened_node.nextElementSibling);
    if (group_rect.bottom <= tree_rect.top + tree_panel.clientHeight) return;
    tree_panel.scrollTop += group_rect.top - tree_rect.top;
  }
  function tree_reveal(file_path) {
    const path_parts = file_path.split("/");
    let accumulated_path = "";
    for (
      let part_index = 0;
      part_index < path_parts.length - 1;
      part_index++
    ) {
      accumulated_path = accumulated_path
        ? accumulated_path + "/" + path_parts[part_index]
        : path_parts[part_index];
      expanded_directories.add(accumulated_path);
    }
  }

  // the model on show's functions by the file and line each starts at
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
  function home_render() {
    current_file_path = null;
    scope_totals = null;
    let markup = `<div class="heat-map-home-">`;
    const line_rows = top_lines(HEAT_MAP_HOME_TABLE_MAX_ROWS);
    markup +=
      `<div class="page-heading-">${html_escape(
        text_fill("str_heading_lines_by_counter", {
          prefix: HEADING_PREFIX,
          counter: counter_label(current_counter),
        }),
      )}</div>` +
      table_render(
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
          const [
            file_path,
            line_number,
            cost,
            function_index,
            source_snippet,
          ] = entry;
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
          row_href: line_rows.map((entry) =>
            hash_for_line(entry[0], entry[1]),
          ),
        },
      );
    const top_functions = function_table
      .map((function_entry, index) => [
        index,
        current_value(function_entry.self),
      ])
      .filter((entry) => absolute(entry[1]) > 0)
      .sort((entry_a, entry_b) => absolute(entry_b[1]) - absolute(entry_a[1]))
      .slice(0, HEAT_MAP_HOME_TABLE_MAX_ROWS);
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
    markup +=
      `<div class="page-heading-">${html_escape(
        text_fill("str_heading_functions_by_self", {
          prefix: HEADING_PREFIX,
          counter: counter_label(current_counter),
        }),
      )}</div>` +
      table_render(
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
    markup += `</div>`;
    main_panel.innerHTML = markup;
    main_panel.scrollTop = 0;
    tree_render();
    report_ui.layout_activate(main_panel);
    minimap_clear();
  }

  function file_render(file_path, line) {
    const file = file_table[file_path];
    if (!file)
      throw new Error(
        window.ui_strings.text_fill("str_error_hash_file_unknown", [
          file_path,
        ]),
      );
    const is_first_view = current_file_path !== file_path,
      kept_scroll_top = is_first_view ? -1 : main_panel.scrollTop;
    current_file_path = file_path;
    tree_reveal(file_path);
    const lines = file.lines;
    scope_totals = scope_totals_build(file_path);
    let markup =
      `<div class="heat-map-source-">` +
      `<div class="heat-map-source-file-header- band_">` +
      `<span class="heat-map-source-file-header-path-">` +
      `${html_escape(file_path)}</span>`;
    const file_self_cost = current_value(file.self);
    const file_baseline_cost = file_baseline_of(file_path) || 0;
    const file_amount_text = human_text(file_self_cost);
    markup +=
      `<span class="heat-map-source-file-header-statistic-">` +
      `${html_escape(text_of("str_column_self"))} ` +
      `<span class="heat-map-source-file-header-statistic-share-">` +
      (share_of_baseline_text(file_self_cost, file_baseline_cost) ||
        text_of("str_share_zero")) +
      `</span>` +
      (file_amount_text
        ? ` (${file_amount_text}` +
          ` ${html_escape(counter_label(current_counter))})`
        : "") +
      `</span>`;
    for (const secondary of secondary_counters) {
      const self_cost = secondary.get(file.self);
      if (!self_cost) continue;
      const secondary_percent = secondary_percent_of_file(
        self_cost,
        file_path,
        secondary,
      );
      markup +=
        `<span class="heat-map-source-file-header-statistic-">` +
        `${html_escape(counter_label(secondary))}` +
        ` <span class="heat-map-source-file-header-statistic-share-">` +
        `${share_text(secondary_percent)}</span>` +
        ` (${human_text(self_cost)})</span>`;
    }
    if (file.group === "external") {
      const note = text_fill("str_not_in_repo", { path: file.raw });
      markup +=
        `<span class="heat-map-source-file-header-statistic-">` +
        `${html_escape(note)}</span>`;
    }
    markup += `</div>`;
    const file_source = source_text(file_path);
    if (file_source == null) {
      const note = html_escape(text_of("str_source_unavailable"));
      markup += `<div class="heat-map-source-unavailable-note-">${note}</div>`;
    }

    const hot_lines = Object.keys(lines)
      .map((line_key) => [+line_key, current_value(lines[line_key][0])])
      .filter((entry) => absolute(entry[1]) > 0)
      .sort((entry_a, entry_b) => absolute(entry_b[1]) - absolute(entry_a[1]));
    const ticker_tape_lines = hot_lines
      .filter(
        (entry) =>
          absolute(
            line_share(entry[1], line_baseline(file_path, entry[0]), entry[0]),
          ) >= HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_LEAST_SHARE,
      )
      .slice(0, HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_MAX_COUNT);
    // the toolbar pattern: the tape is one tab stop, its first entry at first
    if (ticker_tape_lines.length) {
      markup +=
        `<div class="heat-map-source-ticker-tape-" role="toolbar"` +
        ` aria-label="${html_escape(TICKER_TAPE_HEADING)}">` +
        `<span class="heat-map-source-ticker-tape-label-">` +
        `${html_escape(TICKER_TAPE_HEADING)}</span>`;
      ticker_tape_lines.forEach(([line_number, cost], entry_index) => {
        const baseline_cost = line_baseline(file_path, line_number);
        markup +=
          `<span class="heat-map-source-ticker-tape-entry-" role="link"` +
          ` tabindex="${entry_index ? -1 : 0}"` +
          ` data-goto-="${line_number}"` +
          ` style="${cell_style(
            heat_of_line(cost, baseline_cost, line_number),
          )}">` +
          `${line_number} -` +
          ` ${line_share_text(cost, baseline_cost, line_number)}</span>`;
      });
      markup += `</div>`;
    }

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
      // no address names line 0, so its row opens no panel
      const class_names = [
        line_costs && line_number ? "clickable_" : "",
        file.callees[line_number] ? "has-callee-" : "",
      ]
        .filter(Boolean)
        .join(" ");
      attrs.push(
        `id="L${line_number}_"` +
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
    // with no text on this box the lines that carry cost are the whole view,
    // line 0 (callgrind's no-line bucket) too: none of the file's cost hides
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
    markup += `<div class="heat-map-source-tail-"></div></div>`;
    main_panel.innerHTML = markup;
    tree_render();

    minimap_build();
    // the source's lines walk from the keyboard, a line detail's row left out
    report_ui.table_rows.attach(
      main_panel.querySelector("table.heat-map-source-table-"),
      "tr[data-line-number-]",
    );
    report_ui.layout_activate(main_panel);
    tail_fit();
    if (!is_first_view) main_panel.scrollTop = kept_scroll_top;
    else if (!line) {
      const hottest = hot_lines.length ? hot_lines[0][0] : 0;
      const hottest_row = hottest
        ? document.getElementById("L" + hottest + "_")
        : null;
      if (hottest_row) row_center(hottest_row);
      else main_panel.scrollTop = 0;
    }
    minimap_sync();
  }

  // An element's box in design px, the space scrollTop and clientHeight
  // count in. On a zoomed page a rect is in screen px.
  function design_rect_of(element) {
    const rect = element.getBoundingClientRect();
    return {
      bottom: report_ui.design_px(rect.bottom),
      height: report_ui.design_px(rect.height),
      top: report_ui.design_px(rect.top),
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

  function tail_fit() {
    const tail = main_panel.querySelector(".heat-map-source-tail-");
    const table_element = main_panel.querySelector(
      "table.heat-map-source-table-",
    );
    if (!tail || !table_element) return;
    const rows = table_element.tBodies[0].rows,
      last = rows[rows.length - 1];
    if (!last) return;
    const covered_px =
      covered_height(table_element) + design_rect_of(last).height;
    tail.style.height =
      Math.max(0, (main_panel.clientHeight - covered_px) / 2) + "px";
  }

  let scale_factor = 1,
    clone_height_px = 0;
  function minimap_clear() {
    minimap_panel.classList.add("empty_");
    minimap_box.innerHTML = "";
    minimap_viewport.hidden = true;
  }
  // Build the minimap as the source view's last column, the template's
  // element moved in after the source, unless the source fits on screen.
  function minimap_build() {
    main_panel.append(minimap_panel);
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
    // a rigid column as tall as main shows, wherever the source scrolls
    const band_width_px = minimap_panel.clientWidth,
      band_height_px = main_panel.clientHeight;
    minimap_panel.style.height = band_height_px + "px";

    // the font fit makes a ch the design ch, so the source's width is known
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
  main_panel.addEventListener("scroll", window.catch_show_throw(minimap_sync));
  minimap_panel.addEventListener(
    "click",
    window.catch_show_throw((click_event) => {
      if (click_event.target.closest("#heat-map-minimap-viewport-")) return;
      const geometry = geometry_measure(),
        scaled_height_px = clone_height_px * scale_factor;
      const offsetY =
        report_ui.design_px(click_event.clientY) -
        design_rect_of(minimap_panel).top;
      const row = (offsetY / scaled_height_px) * geometry.rows;
      scroll_to_row(row - (main_panel.clientHeight - geometry.cover) / 2);
    }),
  );
  minimap_viewport.addEventListener(
    "pointerdown",
    window.catch_show_throw((down_event) => {
      const start_client_y = down_event.clientY,
        start_top_px = minimap_viewport.offsetTop;
      const scaled_height_px = clone_height_px * scale_factor;
      minimap_viewport.classList.add("drag_");
      if (minimap_viewport.setPointerCapture) {
        minimap_viewport.setPointerCapture(down_event.pointerId);
      }
      const move = window.catch_show_throw((move_event) =>
        scroll_to_row(
          ((start_top_px +
            report_ui.design_px(move_event.clientY - start_client_y)) /
            scaled_height_px) *
            geometry_measure().rows,
        ),
      );
      const drag = (on) => {
        const method = on ? "addEventListener" : "removeEventListener";
        minimap_viewport[method]("pointermove", move);
        minimap_viewport[method]("pointerup", release);
        minimap_viewport[method]("pointercancel", release);
      };
      const release = window.catch_show_throw(() => {
        minimap_viewport.classList.remove("drag_");
        drag(false);
      });
      drag(true);
      down_event.preventDefault();
      down_event.stopPropagation();
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
    const row = line ? document.getElementById("L" + line + "_") : null;
    if (row) {
      detail_open(current_file_path, line, row);
      // Tab into the source lands on the line whose detail is open
      report_ui.table_rows.tab_stop_set(row, false);
      if (!row_is_visible(row)) row_center(row);
    }
    minimap_sync();
  }
  // Close the line detail and give the focus back to its line, as Escape
  // and the detail's two close links do.
  function detail_close(detail_row) {
    report_ui.table_rows.tab_stop_set(detail_row.previousElementSibling, true);
    report_ui.address.request(hash_for_line(current_file_path));
  }
  function detail_open(file_path, line_number, row) {
    const file = file_table[file_path];
    const callees = (file.callees[line_number] || [])
      .slice()
      .sort(
        (callee_a, callee_b) =>
          current_value(callee_b[3]) - current_value(callee_a[3]),
      );
    const function_index = (entry_line_index[file_path] || {})[line_number];
    const line_function_index = file.lineFunction[line_number];
    const line_costs = file.lines[line_number] || [[], [], 0];
    const function_column = (label) => ({
      label,
      width: STYLE_TABLE_FUNCTION_NAME_WIDTH_CHARS,
    });
    const location_column = {
      label: text_of("str_column_defined_at"),
      clip: STYLE_TABLE_LOCATION_COLUMN_MAX_CHARS,
    };
    const call_cost = current_value(line_costs[1]);
    const self_cost = current_value(line_costs[0]);
    const line_baseline_cost = line_baseline(file_path, line_number);
    const self_label = text_of(
      function_index != null ? "str_column_self" : "str_line_self",
    );
    const detail_counter_columns = [
      { label: text_of("str_column_counter") },
      { label: scope_share_label(), numeric: true },
      { label: text_of("str_column_count"), numeric: true },
    ];
    // a counter's row, its name, its share in the scale's scope, its count
    const counter_row_of = (counter) => {
      const counter_self = counter.get(line_costs[0]);
      return [
        { text: counter_label(counter) },
        secondary_share_text(
          counter_self,
          counter,
          line_counter_baseline(file_path, line_number, counter),
          line_number,
        ),
        counter_self ? cell_number(counter_self) : "",
      ];
    };
    // the selected counter, every other recorded one by name, then the
    // ranking counter last when another one is selected
    const ranking_counter = counter_find(RANKING_COUNTER_NAME);
    const listed_counters = counter_list
      .filter(
        (counter) =>
          !counter.derived &&
          counter !== current_counter &&
          counter !== ranking_counter,
      )
      .sort((counter_a, counter_b) =>
        counter_a.key.localeCompare(counter_b.key),
      );
    if (current_counter !== ranking_counter)
      listed_counters.push(ranking_counter);
    const detail_counter_rows = [
      [
        { text: `${self_label} ${counter_label(current_counter)}` },
        line_share_text(self_cost, line_baseline_cost, line_number),
        cell_number(self_cost),
      ],
      ...listed_counters.map(counter_row_of),
    ];
    if (call_cost) {
      detail_counter_rows.push([
        { text: text_of("str_column_calls") },
        line_share_text(call_cost, line_baseline_cost, line_number),
        cell_number(call_cost),
      ]);
      detail_counter_rows.push([
        { text: text_of("str_column_call_count") },
        "",
        call_count_cell(line_costs[2]),
      ]);
    }
    for (const secondary of secondary_counters) {
      const secondary_self = secondary.get(line_costs[0]);
      // a diff's derived delta can cancel to zero while its parts moved
      const contributor_moved = secondary.contributing_counters.some(
        (contributor) => contributor.get(line_costs[0]),
      );
      if (!secondary_self && !contributor_moved) continue;
      // an estimate never hides what it was summed from: a derived
      // counter's recorded contributors follow its row
      detail_counter_rows.push(
        counter_row_of(secondary),
        ...secondary.contributing_counters.map(counter_row_of),
      );
    }
    const in_function_note =
      line_function_index != null
        ? text_fill("str_in_function", {
            function: function_name(line_function_index),
          })
        : "";
    const heading_line = `${file_path}:${line_number}${in_function_note}`;
    const in_function_html =
      line_function_index != null
        ? text_fill("str_in_function", {
            function:
              `<span` +
              ` class="heat-map-source-line-detail-function-name-">` +
              `${html_escape(function_name(line_function_index))}</span>`,
          })
        : "";
    let markup = `<div class="heat-map-source-line-detail-">`;
    markup +=
      `<a href="#"` +
      ` class="heat-map-source-line-detail-close-symbol-">` +
      `${html_escape(text_of("str_detail_close_symbol"))}</a>`;
    markup +=
      `<div>${html_escape(file_path)}:` +
      `${line_number}${in_function_html}</div>`;
    markup += table_render(
      "heat.detail.stats",
      detail_counter_columns,
      detail_counter_rows,
    );
    const text_parts = [
      heading_line +
        "\n" +
        table_markdown(detail_counter_columns, detail_counter_rows),
    ];
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
      const heading = text_fill("str_detail_callees", {
        counter: counter_label(current_counter),
      });
      markup +=
        `<div class="heat-map-source-line-detail-heading-">` +
        `${html_escape(heading)}</div>` +
        table_render("heat.detail.callees", columns, rows);
      text_parts.push(heading + "\n" + table_markdown(columns, rows));
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
        ) || text_of("str_share_zero");
      const function_total_text =
        share_of_baseline_text(
          current_value(function_entry.self) +
            current_value(function_entry.calls),
          function_baseline_cost,
        ) || text_of("str_share_zero");
      const heading = HAS_CALL_GRAPH
        ? text_fill("str_detail_function_totals", {
            function: function_entry.name,
            self: function_self_text,
            total: function_total_text,
          })
        : text_fill("str_detail_function_self", {
            function: function_entry.name,
            self: function_self_text,
          });
      markup +=
        `<div class="heat-map-source-line-detail-heading-">` +
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
        text_parts.push(heading + "\n" + table_markdown(columns, rows));
      } else if (HAS_CALL_GRAPH) {
        const none = text_of("str_no_caller");
        markup += `<div class="dimmed_">${html_escape(none)}</div>`;
        text_parts.push(heading + "\n" + none);
      } else {
        text_parts.push(heading);
      }
    }
    markup +=
      `<div class="heat-map-source-line-detail-action-bar-">` +
      `<a href="#"` +
      ` class="heat-map-source-line-detail-action-bar-copy-link-">` +
      `${html_escape(text_of("str_detail_copy"))}</a>` +
      `<span` +
      ` class="heat-map-source-line-detail-action-bar-separator-">` +
      ` | </span>` +
      `<a href="#"` +
      ` class="heat-map-source-line-detail-action-bar-close-link-">` +
      `${html_escape(text_of("str_detail_close"))}</a></div>`;
    markup += `</div>`;
    const detail_row = document.createElement("tr");
    detail_row.className = "heat-map-source-line-detail-row-";
    detail_row.innerHTML =
      `<td colspan="${row.cells.length}">` + `${markup}</td>`;
    detail_row.detail_copy_text = text_parts.join("\n\n");
    row.after(detail_row);
    report_ui.layout_activate(detail_row);
  }

  main_panel.addEventListener(
    "click",
    window.catch_show_throw((click_event) => {
      // the minimap takes its own clicks: its copied rows open no line
      if (minimap_panel.contains(click_event.target)) return;
      const ticker_tape_entry = click_event.target.closest(
        ".heat-map-source-ticker-tape-entry-",
      );
      if (ticker_tape_entry) {
        report_ui.address.request(
          hash_for_line(
            current_file_path,
            +ticker_tape_entry.getAttribute("data-goto-"),
          ),
        );
        return;
      }
      const copy = click_event.target.closest(
        ".heat-map-source-line-detail-action-bar-copy-link-",
      );
      if (copy) {
        click_event.preventDefault();
        const detail_row = copy.closest("tr.heat-map-source-line-detail-row-");
        // returned, so a refused write reaches the wrapper as a rejection
        return navigator.clipboard.writeText(detail_row.detail_copy_text);
      }
      const close = click_event.target.closest(
        ".heat-map-source-line-detail-close-symbol-," +
          " .heat-map-source-line-detail-action-bar-close-link-",
      );
      if (close) {
        click_event.preventDefault();
        detail_close(close.closest("tr.heat-map-source-line-detail-row-"));
        return;
      }
      if (click_event.target.closest("a")) return;
      const link_row = click_event.target.closest("tr.row-link-");
      if (link_row) {
        report_ui.address.request(link_row.getAttribute("data-href-"));
        return;
      }
      const row = click_event.target.closest("tr.clickable_");
      if (row && current_file_path) {
        const line_number = +row.getAttribute("data-line-number-");
        report_ui.address.request(
          line_number === detail_line()
            ? hash_for_line(current_file_path)
            : hash_for_line(current_file_path, line_number),
        );
      }
    }),
  );
  // A key on a ticker tape entry, the toolbar pattern's. The arrows, Home and
  // End walk the entries, and Enter or the click key opens one as a click.
  function ticker_tape_key_take(key_event, key_name, ticker_tape_entry) {
    if (report_ui.widget_key.activates(key_name)) {
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
      report_ui.tab_stop_move(ticker_tape_entry, next_entry, true);
  }
  // a focused ticker tape entry, by key or pointer, becomes the tape's stop
  main_panel.addEventListener(
    "focusin",
    window.catch_show_throw((focus_event) => {
      const ticker_tape_entry = focus_event.target.closest(
        ".heat-map-source-ticker-tape-entry-",
      );
      if (!ticker_tape_entry) return;
      report_ui.tab_stop_move(
        ticker_tape_entry.parentElement.querySelector(
          ':scope > [tabindex="0"]',
        ),
        ticker_tape_entry,
        false,
      );
    }),
  );
  // the main panel's keys its tables leave: a ticker tape entry's, and
  // Escape on a line detail or its line, closing the detail back to the line
  main_panel.addEventListener(
    "keydown",
    window.catch_show_throw((key_event) => {
      const key_name = report_ui.widget_key.of(key_event);
      if (!key_name) return;
      const ticker_tape_entry = key_event.target.closest(
        ".heat-map-source-ticker-tape-entry-",
      );
      if (ticker_tape_entry) {
        ticker_tape_key_take(key_event, key_name, ticker_tape_entry);
        return;
      }
      const detail_row = main_panel.querySelector(
        "tr.heat-map-source-line-detail-row-",
      );
      if (key_name !== WIDGET_KEY_NAMES.close || !detail_row) return;
      const is_in_detail =
        detail_row.contains(key_event.target) ||
        detail_row.previousElementSibling === key_event.target;
      if (!is_in_detail) return;
      key_event.preventDefault();
      detail_close(detail_row);
    }),
  );

  // the line the address on show names, held to a row of its file, 0 for
  // none; address_recenter puts it back in the middle
  let rendered_line = 0;
  let rendered_key = "";
  function counter_apply(key) {
    current_counter = counter_find(key);
    counter_select.value = current_counter.key;
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
  // Put a scale on show in its pulldown. The caller redraws.
  function scale_apply(scale_value) {
    active_scale = SCALE_CHOICES.find((entry) => entry.value === scale_value);
    scale_select.value = active_scale.value;
  }
  // Put a tree order on show in its pulldown. The caller redraws.
  function sort_mode_apply(shown_sort_mode) {
    sort_mode = shown_sort_mode;
    sort_select.value = sort_mode;
  }
  // The value a strip pulldown shows, the stored one where the pulldown
  // offers it, else its default. Every report on file:// shares storage.
  function stored_choice_of(select_element, storage_key, default_value) {
    const stored_value = view_storage.value_read(storage_key);
    const is_offered = [...select_element.options].some(
      (offered_option) => offered_option.value === stored_value,
    );
    return is_offered ? stored_value : default_value;
  }
  // Show the strip's pulldowns as storage now holds them, redrawing what
  // changed, a reset cleared them, a scale change left them unchanged.
  function strip_preferences_apply() {
    // nothing is drawn before the first model, whose load reads them
    if (shown_test_name === null) return;
    const stored_sort_mode = sort_mode_stored();
    if (stored_sort_mode !== sort_mode) {
      sort_mode_apply(stored_sort_mode);
      tree_render();
    }
    const stored_scale_value = scale_value_stored(),
      stored_counter_key = counter_key_stored();
    if (
      stored_scale_value === active_scale.value &&
      stored_counter_key === current_counter.key
    )
      return;
    scale_apply(stored_scale_value);
    if (stored_counter_key !== current_counter.key)
      counter_apply(stored_counter_key);
    rendered_key = "";
    route_render();
  }
  // Whether the pulldowns list this file or function, so that an address
  // this test never sampled is a note rather than a bad address.
  function pulldown_text_lists(names_key, entry_name) {
    if (!window.report_pulldown_text)
      throw new Error(text_of("str_error_pulldown_text_missing"));
    return window.report_pulldown_text[names_key].includes(entry_name);
  }
  // Show in the main panel that this test recorded no samples for a name the
  // pulldowns list, with the tree still beside the note.
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
  // The line an address names, held to the rows of the file on show, which
  // run in line order, past line 0: the last at or before it, else the first.
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
  // Give back the focus a render took from the main panel, to the line the
  // address names, else to the panel, whose arrows then scroll that panel.
  function main_focus_restore(main_had_focus) {
    if (!main_had_focus || main_panel.contains(document.activeElement)) return;
    const addressed_row = rendered_line
      ? document.getElementById("L" + rendered_line + "_")
      : null;
    if (addressed_row) report_ui.table_rows.tab_stop_set(addressed_row, true);
    else main_panel.focus({ preventScroll: true });
  }
  // Render the address the page's hash names, a test not on show once
  // model_load has its model. A bad address throws rather than rendering.
  function route_render() {
    const main_had_focus =
      document.hasFocus() && main_panel.contains(document.activeElement);
    const page_address = report_ui.address.of_hash(location.hash);
    if (page_address.view !== HEAT_MAP_VIEW_ENTRY[0])
      throw new Error(
        window.ui_strings.text_fill("str_error_hash_view_mismatch", [
          HEAT_MAP_VIEW_ENTRY[0],
        ]),
      );
    if (page_address.test !== shown_test_name) {
      model_load(page_address.test);
      return;
    }
    // an address without a line is line 0, the row no address names
    let file = page_address.file,
      line = page_address.line === null ? 0 : page_address.line,
      fn = page_address.function;
    // a file or function the pulldowns list but this test never sampled is
    // a designed condition, a note under the address as written
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
          window.ui_strings.text_fill("str_error_hash_function_unknown", [fn]),
        );
      }
    } else if (file && !file_table[file]) {
      if (!pulldown_text_lists("files", file)) {
        throw new Error(
          window.ui_strings.text_fill("str_error_hash_file_unknown", [file]),
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
      if (file) file_render(file, line);
      else home_render();
    }
    if (file) {
      if (line) line = line_clamp(line);
      detail_set(line);
    }
    rendered_line = line;
    main_focus_restore(main_had_focus);
  }
  // Put a test's model on show and render the address, at once when its
  // data script ran before, else once the script inserted here has run.
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
      window.catch_show_throw(() => {
        throw new Error(
          window.ui_strings.text_fill("str_error_hash_test_unknown", [
            test_name,
          ]),
        );
      }),
    );
    // the address is taken again, as the hash may have moved on meanwhile
    model_script.addEventListener(
      "load",
      window.catch_show_throw(() => {
        const loaded_models = window[HEAT_MAP_MODEL_GLOBAL_NAME];
        if (!loaded_models || !loaded_models[test_name])
          throw new Error(
            window.ui_strings.text_fill("str_error_heat_map_unfiled", [
              test_name,
            ]),
          );
        route_render();
      }),
    );
    document.head.append(model_script);
  }
  // Rebuild everything drawn from a model, the report's kind from the first
  // one, and open its tree on the stored counter. The caller renders.
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
  }
  // Put the address back where it first opened: its line, or the function's,
  // in the middle, and a file without a line at its first view again.
  function address_recenter() {
    const addressed_row = rendered_line
      ? document.getElementById("L" + rendered_line + "_")
      : null;
    if (addressed_row) {
      row_center(addressed_row);
      return;
    }
    current_file_path = null;
    rendered_key = "";
    route_render();
  }
  window.addEventListener("hashchange", window.catch_show_throw(route_render));
  report_ui.view_activate({
    preferences_apply: strip_preferences_apply,
    recenter: address_recenter,
  });

  let resize_debounce_timer = null;
  window.addEventListener(
    "resize",
    window.catch_show_throw(() => {
      clearTimeout(resize_debounce_timer);
      resize_debounce_timer = setTimeout(
        window.catch_show_throw(() => {
          tail_fit();
          minimap_layout();
        }),
        LAYOUT_RESIZE_SETTLE_DELAY_MS,
      );
    }),
  );
  counter_select.addEventListener(
    "change",
    window.catch_show_throw((change_event) => {
      view_storage.value_write("heat.counter", change_event.target.value);
      counter_apply(change_event.target.value);
      route_render();
    }),
  );
  scale_select.addEventListener(
    "change",
    window.catch_show_throw((change_event) => {
      view_storage.value_write("heat.scale", change_event.target.value);
      scale_apply(change_event.target.value);
      rendered_key = "";
      route_render();
    }),
  );
  sort_select.addEventListener(
    "change",
    window.catch_show_throw((change_event) => {
      view_storage.value_write("heat.sort", change_event.target.value);
      sort_mode_apply(change_event.target.value);
      // no tree is drawn before the first model, whose render sorts by this
      if (shown_test_name !== null) tree_render();
    }),
  );
  document.getElementById("heat-map-menu-search-box-").addEventListener(
    "input",
    window.catch_show_throw((input_event) => {
      search_query = input_event.target.value.trim().toLowerCase();
      // no tree is drawn before the first model, whose render filters by this
      if (shown_test_name !== null) tree_render();
    }),
  );
  route_render();
})();
