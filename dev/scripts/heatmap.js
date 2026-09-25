(function () {
  "use strict";

  const DESIGN_FONT_CHARACTER_WIDTH_PX = settings(
    "DESIGN_FONT_CHARACTER_WIDTH_PX",
  );
  const HEAT_COLOR_FULL_SCALE_PERCENT = settings(
    "HEAT_COLOR_FULL_SCALE_PERCENT",
  );
  const HEAT_COLOR_LIGHT_TEXT_ABOVE_SHARE = settings(
    "HEAT_COLOR_LIGHT_TEXT_ABOVE_SHARE",
  );
  const HEAT_MAP_CONTROL_DROPDOWN_EXTRA_WIDTH_CHARS = settings(
    "HEAT_MAP_CONTROL_DROPDOWN_EXTRA_WIDTH_CHARS",
  );
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
  const HEAT_MAP_MINIMAP_SHOWN_ABOVE_FILE_LINES = settings(
    "HEAT_MAP_MINIMAP_SHOWN_ABOVE_FILE_LINES",
  );
  const HEAT_MAP_MINIMAP_SOURCE_WIDTH_CHARS = settings(
    "HEAT_MAP_MINIMAP_SOURCE_WIDTH_CHARS",
  );
  const HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX = settings(
    "HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX",
  );
  const HEAT_MAP_SECONDARY_COUNTER_NAMES = settings(
    "HEAT_MAP_SECONDARY_COUNTER_NAMES",
  );
  const HEAT_MAP_SOURCE_HOT_LINE_BUTTON_LEAST_SHARE = settings(
    "HEAT_MAP_SOURCE_HOT_LINE_BUTTON_LEAST_SHARE",
  );
  const HEAT_MAP_SOURCE_HOT_LINE_BUTTON_MAX_COUNT = settings(
    "HEAT_MAP_SOURCE_HOT_LINE_BUTTON_MAX_COUNT",
  );
  const HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS = settings(
    "HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS",
  );
  const HEAT_MAP_TREE_AUTO_EXPAND_ABOVE_SHARE = settings(
    "HEAT_MAP_TREE_AUTO_EXPAND_ABOVE_SHARE",
  );
  const HEAT_MAP_TREE_INDENT_FIRST_LEVEL_PX = settings(
    "HEAT_MAP_TREE_INDENT_FIRST_LEVEL_PX",
  );
  const HEAT_MAP_TREE_INDENT_PER_LEVEL_PX = settings(
    "HEAT_MAP_TREE_INDENT_PER_LEVEL_PX",
  );
  const HEAT_MAP_TREE_PANE_NARROWEST_PX = settings(
    "HEAT_MAP_TREE_PANE_NARROWEST_PX",
  );
  const LAYOUT_RESIZE_SETTLE_DELAY_MS = settings(
    "LAYOUT_RESIZE_SETTLE_DELAY_MS",
  );
  const TABLE_FUNCTION_NAME_WIDTH_CHARS = settings(
    "TABLE_FUNCTION_NAME_WIDTH_CHARS",
  );
  const TABLE_LOCATION_COLUMN_MAX_CHARS = settings(
    "TABLE_LOCATION_COLUMN_MAX_CHARS",
  );
  const profile_model = JSON.parse(
    document.getElementById("heatdata").textContent,
  );
  const file_table = profile_model.files,
    function_table = profile_model.functions;
  const tree_panel = document.getElementById("tree");
  const main_panel = document.getElementById("main");
  const minimap_panel = document.getElementById("minimap");
  const minimap_box = document.getElementById("mmBox");
  const minimap_viewport = document.getElementById("mmViewport");
  const view_storage = report_ui.view_storage;
  let sort_mode = view_storage.value_read("heat.sort") || "heat";
  let current_file_path = null,
    search_query = "";
  const sort_select = document.getElementById("sort");
  document.getElementById("counterLabel").textContent =
    window.ui_strings.text_of("str_control_counter");
  document.getElementById("scaleLabel").textContent =
    window.ui_strings.text_of("str_control_scale");
  document.getElementById("sortLabel").textContent =
    window.ui_strings.text_of("str_control_tree");
  document.getElementById("searchLabel").textContent =
    window.ui_strings.text_of("str_control_search");
  sort_select.options[0].textContent =
    window.ui_strings.text_of("str_sort_by_heat");
  sort_select.options[1].textContent =
    window.ui_strings.text_of("str_sort_by_name");
  document.getElementById("q").placeholder = window.ui_strings.text_of(
    "str_search_placeholder",
  );
  sort_select.value = sort_mode;
  tree_panel.style.minWidth = HEAT_MAP_TREE_PANE_NARROWEST_PX + "px";
  report_ui.pane_splitter.attach(
    document.getElementById("split"),
    tree_panel,
    "heat.tree",
    HEAT_MAP_TREE_PANE_NARROWEST_PX,
  );

  const vector_at = (cost_vector, index) =>
    cost_vector && index < cost_vector.length ? cost_vector[index] : 0;
  const counter_list = [];
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
  const counter_find = (key) =>
    counter_list.find((counter) => counter.key === key);
  // a key the column list must hold: the ranking counter, a select entry,
  // or the one an address names once route_render has checked it
  function counter_of(key) {
    const counter = counter_find(key);
    if (!counter) throw new Error("str_error_counter_unknown " + key);
    return counter;
  }
  let current_counter = counter_of(profile_model.heatMapTotals.defaultCounter);
  const secondary_counters =
    HEAT_MAP_SECONDARY_COUNTER_NAMES.map(counter_find).filter(Boolean);

  const text_of = window.ui_strings.text_of;
  const text_fill = window.ui_strings.text_fill;
  const counter_label = (counter) =>
    text_of(
      HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX +
        counter.key.toLowerCase(),
    ) +
    " / " +
    counter.key;
  const counter_select = document.getElementById("counter");
  let counter_label_width = 0;
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
  counter_select.value = current_counter.key;

  counter_select.style.width =
    counter_label_width + HEAT_MAP_CONTROL_DROPDOWN_EXTRA_WIDTH_CHARS + "ch";
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
    CHIP_HEADING = text_of("str_chip_heading_self");
  const SELF_COLUMN = {
    label: text_of("str_column_self"),
    numeric: true,
  };
  const HAS_CALL_GRAPH = function_table.some(
    (function_entry) => function_entry.callers.length > 0,
  );

  const IS_DIFF = !!profile_model.heatMapTotals.diff;
  const function_baselines = profile_model.functionBaseline || [];
  const file_baselines = profile_model.fileBaseline || {};
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
  if (IS_DIFF) {
    share_text = report_ui.signed_percent_text;
    human_text = report_ui.signed_human_text;
    HEADING_PREFIX = text_of("str_heading_prefix_diff");
    CHIP_HEADING = text_of("str_chip_heading_diff");
    counter_baseline_of = (cost_vector, counter) => {
      if (!cost_vector) return null;
      const baseline_cost = absolute(counter.get(cost_vector));
      return baseline_cost ? baseline_cost : null;
    };
    share_of_baseline = (value, baseline_cost) =>
      baseline_cost
        ? (100 * value) / baseline_cost
        : value
          ? Math.sign(value) * Infinity
          : 0;
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

  const scale_select = document.getElementById("scale");
  const SCOPE_CHOICES = scope_choices_build();
  const CURVE_CHOICES = [
    ["log", text_of("str_scale_curve_log")],
    ["linear", text_of("str_scale_curve_linear")],
  ];
  const SCALE_CHOICES = [];
  CURVE_CHOICES.forEach((curve) => {
    SCOPE_CHOICES.forEach((scope) =>
      SCALE_CHOICES.push({
        value: curve[0] + "/" + scope[0],
        curve: curve[0],
        scope: scope[0],
        label:
          SCOPE_CHOICES.length > 1
            ? text_fill("str_scale_entry", {
                curve: curve[1],
                scope: scope[1],
              })
            : curve[1],
      }),
    );
  });
  let active_scale =
    SCALE_CHOICES.find(
      (entry) => entry.value === view_storage.value_read("heat.scale"),
    ) || SCALE_CHOICES[0];
  let scale_label_width = 0;
  SCALE_CHOICES.forEach((entry) => {
    const option = document.createElement("option");
    option.value = entry.value;
    option.textContent = entry.label;
    scale_select.appendChild(option);
    scale_label_width = Math.max(scale_label_width, entry.label.length);
  });
  scale_select.value = active_scale.value;
  scale_select.style.width =
    scale_label_width + HEAT_MAP_CONTROL_DROPDOWN_EXTRA_WIDTH_CHARS + "ch";

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
    if (!file) return totals;
    for (const [line_number, line_costs] of Object.entries(file.lines)) {
      const owner = file.lineFunction[line_number];
      for (const counter of [current_counter].concat(secondary_counters)) {
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
      HEAT_COLOR_FULL_SCALE_PERCENT,
    );
    if (magnitude <= 0) return 0;
    const fraction = magnitude / HEAT_COLOR_FULL_SCALE_PERCENT;
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
      luminance > 0.5
        ? profile_model.theme.fgDark
        : profile_model.theme.fgLight;
    return (
      `background:rgb(${mixed_channels.join(",")});` +
      `color:${foreground_color}`
    );
  }
  const per_function_calls = function_table.map((function_entry) =>
    function_entry.callers.reduce(
      (running_total, caller) => running_total + caller[4],
      0,
    ),
  );
  const CALLS_TOTAL =
    per_function_calls.reduce(
      (running_total, call_count) => running_total + call_count,
      0,
    ) || 1;
  const call_count_cell = (call_count) =>
    call_count
      ? {
          text: human_text(call_count),
          style: cell_style(heat_of_share((100 * call_count) / CALLS_TOTAL)),
        }
      : "";

  const hash_encode = (value) =>
    encodeURIComponent(value).replace(/%2F/g, "/");
  function hash_of_state(state) {
    const hash_parts = [];
    if (state.fn) hash_parts.push("fn=" + hash_encode(state.fn));
    else if (state.file) {
      hash_parts.push("f=" + hash_encode(state.file));
      if (state.line) hash_parts.push("l=" + state.line);
    }
    if (counter_list.length > 1) {
      hash_parts.push("e=" + hash_encode(state.ev || current_counter.key));
    }
    return hash_parts.length ? "#" + hash_parts.join("&") : "";
  }
  const hash_for_line = (file_path, line) =>
    hash_of_state({ file: file_path, line: line });
  const hash_for_function = (name) => hash_of_state({ fn: name });
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
    for (const row of cell_rows) {
      if (row.length !== columns.length) {
        throw new Error(
          `table ${key}: a row has ${row.length} cells ` +
            `for ${columns.length} columns`,
        );
      }
    }
    let grow_index = -1;
    if (options.fill) {
      grow_index = columns.findIndex((column) => column.grow);
      if (grow_index < 0) {
        throw new Error(`table ${key}: fill but no grow column`);
      }
    }
    const column_limit_list = report_ui
      .column_extents(columns, cell_rows, grow_index)
      .map(report_ui.column_limits);
    const table_classes = [
      "cols",
      options.fill ? "fill" : "",
      options.cls || "",
    ]
      .filter(Boolean)
      .join(" ");
    let markup = options.bare
      ? ""
      : `<div class="tbl${options.fill ? " fill" : ""}">`;
    markup +=
      `<div class="tbl-cols"><table class="${table_classes}"` +
      ` data-key="${html_escape(key)}"><colgroup>`;
    column_limit_list.forEach((limit, column_index) => {
      const column_classes = [
        column_index % 2 ? "alt" : "",
        column_index === grow_index ? "grow" : "",
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
        ` data-min="${limit[0]}ch" style="width:${width_text}">`;
    });
    markup += `</colgroup><thead><tr>`;
    for (const column of columns) {
      const heading = html_escape(column.label);
      markup +=
        `<th${column.numeric ? ' class="n"' : ""} title="${heading}">` +
        `${heading}</th>`;
    }
    markup += `</tr></thead><tbody>`;
    cell_rows.forEach((row, row_index) => {
      const href = options.row_href && options.row_href[row_index];
      markup += href
        ? `<tr class="rowlink" data-href="${html_escape(href)}">`
        : options.row_attributes
          ? `<tr ${options.row_attributes[row_index]}>`
          : "<tr>";
      row.forEach((cell, column_index) => {
        const column = columns[column_index];
        const class_names = [
          column.numeric ? "n" : "",
          column.cls || "",
          cell.cls || "",
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
        cls: "x",
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
      const heat_value = heat_of_share(percent);
      return {
        text: self_cost ? share_text(percent) : "",
        style: cell_style(heat_value),
        cls: heat_value > HEAT_COLOR_LIGHT_TEXT_ABOVE_SHARE ? "hot" : "",
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
    text_of(is_expanded ? "str_caret_expanded" : "str_caret_collapsed");
  function tree_render() {
    const output_parts = [];
    function nodes_emit(tree_node, depth) {
      const indent_px =
        HEAT_MAP_TREE_INDENT_FIRST_LEVEL_PX +
        depth * HEAT_MAP_TREE_INDENT_PER_LEVEL_PX;
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
          `<div class="node dir${heat_style_attribute ? " heat" : ""}"` +
            ` data-dir="${html_escape(directory_node.path)}"` +
            ` style="padding-left:${indent_px}px;` +
            `${heat_style_attribute}">` +
            `<span class="caret">` +
            `${caret_of(is_expanded)}</span>` +
            `<span class="name">` +
            `${html_escape(directory_node.name)}/</span>` +
            `<span class="pct">` +
            `${share_of_baseline_text(
              directory_node.self,
              directory_node.base,
            )}` +
            `</span></div>`,
        );
        output_parts.push(`<div class="kids${is_expanded ? " open" : ""}">`);
        nodes_emit(directory_node, depth + 1);
        output_parts.push(`</div>`);
      }
      const file_list = tree_node.files
        .filter((file) => path_matches(file.path))
        .sort(node_compare);
      const file_row_emit = (file) => {
        const selected_class = file.path === current_file_path ? " sel" : "";
        const heat_style_attribute = file.cold
          ? ""
          : cell_style(heat_of_delta(file.self, file.base));
        output_parts.push(
          `<div class="node file${file.cold ? " cold" : ""}` +
            `${heat_style_attribute ? " heat" : ""}${selected_class}"` +
            ` data-file="${html_escape(file.path)}"` +
            ` style="padding-left:${indent_px}px;` +
            `${heat_style_attribute}">` +
            `<span class="caret">` +
            `${caret_of(false)}</span>` +
            `<span class="name">` +
            `${html_escape(file.name)}</span>` +
            `<span class="pct">` +
            `${share_of_baseline_text(file.self, file.base)}` +
            `</span></div>`,
        );
      };
      const zero_cost_files = file_list.filter((file) => file.zero);
      for (const file of file_list) if (!file.zero) file_row_emit(file);
      if (zero_cost_files.length) {
        const is_expanded = search_query
          ? true
          : expanded_cold_groups.has(tree_node.path);
        output_parts.push(
          `<div class="node more"` +
            ` data-more="${html_escape(tree_node.path)}"` +
            ` style="padding-left:${indent_px}px">` +
            `<span class="caret">` +
            `${caret_of(is_expanded)}</span>` +
            `<span class="name">` +
            `${text_of("str_no_samples")}</span>` +
            `<span class="pct"></span></div>`,
        );
        if (is_expanded) {
          for (const file of zero_cost_files) file_row_emit(file);
        }
      }
    }
    nodes_emit(tree_root, 0);
    tree_panel.innerHTML = output_parts.join("");
  }
  tree_panel.addEventListener("click", (click_event) => {
    const tree_node = click_event.target.closest(".node");
    if (!tree_node) return;
    if (tree_node.dataset.dir != null) {
      const file_path = tree_node.dataset.dir;
      if (expanded_directories.has(file_path)) {
        expanded_directories.delete(file_path);
      } else expanded_directories.add(file_path);
      tree_render();
    } else if (tree_node.dataset.more != null) {
      const file_path = tree_node.dataset.more;
      if (expanded_cold_groups.has(file_path)) {
        expanded_cold_groups.delete(file_path);
      } else expanded_cold_groups.add(file_path);
      tree_render();
    } else if (tree_node.dataset.file != null) {
      if (tree_node.classList.contains("cold")) return;
      location.hash = hash_for_line(tree_node.dataset.file);
    }
  });
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

  const entry_line_index = {};
  function_table.forEach((function_entry, index) => {
    if (!function_entry.line) return;
    entry_line_index[function_entry.file] =
      entry_line_index[function_entry.file] || {};
    entry_line_index[function_entry.file][function_entry.line] = index;
  });

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
    let markup = `<div class="home">`;
    const line_rows = top_lines(HEAT_MAP_HOME_TABLE_MAX_ROWS);
    markup +=
      `<h2>${html_escape(
        text_fill("str_heading_lines_by_counter", {
          prefix: HEADING_PREFIX,
          counter: counter_label(current_counter),
        }),
      )}</h2>` +
      table_render(
        "heat.home.lines",
        [
          { label: text_of("str_column_rank"), numeric: true },
          SELF_COLUMN,
          {
            label: text_of("str_column_function"),
            width: TABLE_FUNCTION_NAME_WIDTH_CHARS,
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
      `<h2>${html_escape(
        text_fill("str_heading_functions_by_self", {
          prefix: HEADING_PREFIX,
          counter: counter_label(current_counter),
        }),
      )}</h2>` +
      table_render(
        "heat.home.functions",
        [
          { label: text_of("str_column_rank"), numeric: true },
          SELF_COLUMN,
          {
            label: text_of("str_column_function"),
            width: TABLE_FUNCTION_NAME_WIDTH_CHARS,
          },
          {
            label: text_of("str_column_defined_at"),
            clip: TABLE_LOCATION_COLUMN_MAX_CHARS,
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
    if (!file) throw new Error("str_error_hash_file_unknown " + file_path);
    const is_first_view = current_file_path !== file_path,
      kept_scroll_top = is_first_view ? -1 : main_panel.scrollTop;
    current_file_path = file_path;
    tree_reveal(file_path);
    const lines = file.lines;
    scope_totals = scope_totals_build(file_path);
    let markup =
      `<div class="srcwrap"><div class="fhead band">` +
      `<span class="path">${html_escape(file_path)}</span>`;
    const file_self_cost = current_value(file.self);
    const file_baseline_cost = file_baseline_of(file_path) || 0;
    const file_amount_text = human_text(file_self_cost);
    markup +=
      `<span class="stat">` +
      `${html_escape(text_of("str_column_self"))} <b>` +
      `${
        share_of_baseline_text(file_self_cost, file_baseline_cost) ||
        text_of("str_share_zero")
      }` +
      `</b>` +
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
        `<span class="stat">` +
        `${html_escape(counter_label(secondary))}` +
        ` <b>${share_text(secondary_percent)}</b>` +
        ` (${human_text(self_cost)})</span>`;
    }
    if (file.group === "external") {
      const note = text_fill("str_not_in_repo", { path: file.raw });
      markup += `<span class="stat">${html_escape(note)}</span>`;
    }
    markup += `</div>`;
    const file_source = source_text(file_path);
    if (file_source == null) {
      const note = html_escape(text_of("str_source_unavailable"));
      markup += `<div class="nosrc">${note}</div></div>`;
      main_panel.innerHTML = markup;
      tree_render();
      report_ui.layout_activate(main_panel);
      minimap_clear();
      return;
    }

    const hot_lines = Object.keys(lines)
      .map((line_key) => [+line_key, current_value(lines[line_key][0])])
      .filter((entry) => absolute(entry[1]) > 0)
      .sort((entry_a, entry_b) => absolute(entry_b[1]) - absolute(entry_a[1]));
    const chip_lines = hot_lines
      .filter(
        (entry) =>
          absolute(
            line_share(entry[1], line_baseline(file_path, entry[0]), entry[0]),
          ) >= HEAT_MAP_SOURCE_HOT_LINE_BUTTON_LEAST_SHARE,
      )
      .slice(0, HEAT_MAP_SOURCE_HOT_LINE_BUTTON_MAX_COUNT);
    if (chip_lines.length) {
      markup +=
        `<div class="chips">` +
        `<span class="lbl">${html_escape(CHIP_HEADING)}</span>`;
      for (const [line_number, cost] of chip_lines) {
        const baseline_cost = line_baseline(file_path, line_number);
        markup +=
          `<span class="chip" data-goto="${line_number}"` +
          ` style="${cell_style(
            heat_of_line(cost, baseline_cost, line_number),
          )}">` +
          `${line_number} -` +
          ` ${line_share_text(cost, baseline_cost, line_number)}</span>`;
      }
      markup += `</div>`;
    }

    const rows = [],
      attrs = [];
    const source_row_emit = (line_number, text) => {
      const line_costs = lines[line_number];
      const self_cost = line_costs ? current_value(line_costs[0]) : 0,
        calls = line_costs ? current_value(line_costs[1]) : 0;
      const baseline_cost = line_baseline(file_path, line_number);
      const heat_value = heat_of_line(self_cost, baseline_cost, line_number),
        heat_style_attribute = cell_style(heat_value);
      const class_names = [
        line_costs ? "clickable" : "",
        file.callees[line_number] ? "hasc" : "",
      ]
        .filter(Boolean)
        .join(" ");
      attrs.push(
        `id="L${line_number}"` +
          `${class_names ? ` class="${class_names}"` : ""}` +
          ` data-ln="${line_number}"`,
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
          cls: heat_value > HEAT_COLOR_LIGHT_TEXT_ABOVE_SHARE ? "hot" : "",
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
    const source_lines = file_source.split("\n");
    if (source_lines.length && source_lines[source_lines.length - 1] === "") {
      source_lines.pop();
    }
    let line_count = source_lines.length;
    for (let line_index = 0; line_index < source_lines.length; line_index++) {
      source_row_emit(line_index + 1, source_lines[line_index]);
    }
    for (const line_key of Object.keys(lines)) {
      if (+line_key <= source_lines.length) continue;
      line_count = Math.max(line_count, +line_key);
      source_row_emit(+line_key, text_of("str_source_beyond_end"));
    }

    const call_column = HAS_CALL_GRAPH
      ? [
          {
            label: text_of("str_column_calls"),
            numeric: true,
            cls: "incl",
          },
        ]
      : [];
    const columns = [
      counter_column(current_counter, {
        cls: "self",
      }),
      {
        label: text_of("str_column_line"),
        numeric: true,
        width: String(line_count).length + 2,
        cls: "ln",
      },
      {
        label: text_of("str_column_source"),
        width: HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS,
        grow: true,
        cls: "code",
      },
      ...call_column,
      ...secondary_columns(),
    ];
    markup += table_render("heat.src", columns, rows, {
      row_attributes: attrs,
      fill: 1,
      cls: "src",
      bare: true,
    });
    markup += `<div class="srctail"></div></div>`;
    main_panel.innerHTML = markup;
    tree_render();

    minimap_build();
    report_ui.layout_activate(main_panel);
    tail_fit();
    if (!is_first_view) main_panel.scrollTop = kept_scroll_top;
    else if (!line) {
      const hottest = hot_lines.length ? hot_lines[0][0] : 0;
      const hottest_row = hottest
        ? document.getElementById("L" + hottest)
        : null;
      if (hottest_row) row_center(hottest_row);
      else main_panel.scrollTop = 0;
    }
    minimap_sync();
  }

  function row_is_visible(row_element) {
    const row_rect = row_element.getBoundingClientRect();
    const main_rect = main_panel.getBoundingClientRect();
    return (
      row_rect.top >=
        main_rect.top + covered_height(row_element.closest("table")) &&
      row_rect.bottom <= main_rect.top + main_panel.clientHeight
    );
  }

  function covered_height(table_element) {
    let height =
      table_element.tHead.rows[0].cells[0].getBoundingClientRect().height;
    for (const band of main_panel.querySelectorAll(".band")) {
      height += band.getBoundingClientRect().height;
    }
    return height;
  }

  function row_center(row_element) {
    const cover = covered_height(row_element.closest("table"));
    const row_rect = row_element.getBoundingClientRect();
    const main_rect = main_panel.getBoundingClientRect();
    const detail_element = row_element.nextElementSibling;
    const block_bottom_px =
      detail_element && detail_element.classList.contains("detail")
        ? detail_element.getBoundingClientRect().bottom
        : row_rect.bottom;
    const block_height_px = block_bottom_px - row_rect.top;
    const slack = (main_panel.clientHeight - cover - block_height_px) / 2;
    main_panel.scrollTop += row_rect.top - main_rect.top - cover - slack;
  }

  function tail_fit() {
    const tail = main_panel.querySelector(".srctail");
    const table_element = main_panel.querySelector("table.src");
    if (!tail || !table_element) return;
    const rows = table_element.tBodies[0].rows,
      last = rows[rows.length - 1];
    if (!last) return;
    const covered_px = report_ui.design_px(
      covered_height(table_element) + last.getBoundingClientRect().height,
    );
    tail.style.height =
      Math.max(0, (main_panel.clientHeight - covered_px) / 2) + "px";
  }

  let scale_factor = 1,
    clone_height_px = 0;
  function minimap_clear() {
    minimap_panel.classList.add("empty");
    minimap_box.innerHTML = "";
    minimap_viewport.hidden = true;
  }
  function minimap_build() {
    const table_element = main_panel.querySelector("table.src");
    const table_body = table_element && table_element.tBodies[0];
    if (
      !table_body ||
      table_body.rows.length < HEAT_MAP_MINIMAP_SHOWN_ABOVE_FILE_LINES
    ) {
      minimap_clear();
      return;
    }

    const clone_table = document.createElement("table");
    clone_table.className = "src";
    const clone_body = document.createElement("tbody");
    for (const row of table_body.rows) {
      if (row.classList.contains("detail")) continue;
      const code = row.querySelector("td.code");
      if (!code) continue;
      const clone_row = document.createElement("tr");
      clone_row.className = row.className;
      clone_row.appendChild(code.cloneNode(true));
      clone_body.appendChild(clone_row);
    }
    clone_table.appendChild(clone_body);
    minimap_box.innerHTML = "";
    minimap_box.appendChild(clone_table);
    minimap_panel.classList.remove("empty");
    minimap_viewport.hidden = false;
    clone_height_px = clone_table.offsetHeight;
    minimap_layout();
  }

  function minimap_layout() {
    if (minimap_panel.classList.contains("empty")) return;
    const band_width_px = minimap_panel.clientWidth,
      band_height_px = minimap_panel.clientHeight;

    // the font fit makes a ch the design ch, so the source's width is known
    scale_factor = Math.min(
      1,
      band_width_px /
        (HEAT_MAP_MINIMAP_SOURCE_WIDTH_CHARS * DESIGN_FONT_CHARACTER_WIDTH_PX),
      band_height_px / clone_height_px,
    );
    minimap_box.style.transform = `scale(${scale_factor})`;
    minimap_box.style.transformOrigin = "top left";
    minimap_box.style.width = band_width_px / scale_factor + "px";
    minimap_sync();
  }

  function geometry_measure() {
    const table_element = main_panel.querySelector("table.src"),
      table_body = table_element.tBodies[0];
    const main = main_panel.getBoundingClientRect();
    const clone_body = table_body.getBoundingClientRect();
    const detail_element = table_body.querySelector("tr.detail");
    const detail = detail_element && detail_element.getBoundingClientRect();
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
      bottom: main.top + report_ui.screen_px(main_panel.clientHeight),
      head: table_element.tHead.rows[0].cells[0].getBoundingClientRect()
        .bottom,
    };
  }
  function minimap_sync() {
    if (minimap_panel.classList.contains("empty")) return;
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
  main_panel.addEventListener("scroll", minimap_sync);
  minimap_panel.addEventListener("click", (click_event) => {
    if (click_event.target.closest("#mmViewport")) return;
    const geometry = geometry_measure(),
      scaled_height_px = clone_height_px * scale_factor;
    const offsetY =
      click_event.clientY - minimap_panel.getBoundingClientRect().top;
    const row = (offsetY / scaled_height_px) * geometry.rows;
    scroll_to_row(row - (main_panel.clientHeight - geometry.cover) / 2);
  });
  minimap_viewport.addEventListener("pointerdown", (down_event) => {
    const start_client_y = down_event.clientY,
      start_top_px = minimap_viewport.offsetTop;
    const scaled_height_px = clone_height_px * scale_factor;
    minimap_viewport.classList.add("drag");
    if (minimap_viewport.setPointerCapture) {
      minimap_viewport.setPointerCapture(down_event.pointerId);
    }
    const move = (move_event) =>
      scroll_to_row(
        ((start_top_px + move_event.clientY - start_client_y) /
          scaled_height_px) *
          geometry_measure().rows,
      );
    const drag = (on) => {
      const method = on ? "addEventListener" : "removeEventListener";
      minimap_viewport[method]("pointermove", move);
      minimap_viewport[method]("pointerup", release);
      minimap_viewport[method]("pointercancel", release);
    };
    const release = () => {
      minimap_viewport.classList.remove("drag");
      drag(false);
    };
    drag(true);
    down_event.preventDefault();
    down_event.stopPropagation();
  });

  function detail_line() {
    const detail_row = main_panel.querySelector("tr.detail");
    return detail_row ? +detail_row.previousElementSibling.dataset.ln : 0;
  }

  function detail_set(line) {
    if (line === detail_line()) return;
    for (const detail_row of main_panel.querySelectorAll("tr.detail")) {
      detail_row.remove();
    }
    const row = line ? document.getElementById("L" + line) : null;
    if (row) {
      detail_open(current_file_path, line, row);
      if (!row_is_visible(row)) row_center(row);
    }
    minimap_sync();
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
      width: TABLE_FUNCTION_NAME_WIDTH_CHARS,
    });
    const location_column = {
      label: text_of("str_column_defined_at"),
      clip: TABLE_LOCATION_COLUMN_MAX_CHARS,
    };
    const call_cost = current_value(line_costs[1]);
    const self_cost = current_value(line_costs[0]);
    const line_baseline_cost = line_baseline(file_path, line_number);
    const self_label = text_of(
      function_index != null ? "str_column_self" : "str_line_self",
    );
    const popup_counter_columns = [
      { label: text_of("str_column_counter") },
      { label: scope_share_label(), numeric: true },
      { label: text_of("str_column_count"), numeric: true },
    ];
    const popup_counter_rows = [
      [
        {
          text: `${self_label} ${counter_label(current_counter)}`,
        },
        line_share_text(self_cost, line_baseline_cost, line_number),
        cell_number(self_cost),
      ],
    ];
    if (call_cost) {
      popup_counter_rows.push([
        { text: text_of("str_column_calls") },
        line_share_text(call_cost, line_baseline_cost, line_number),
        cell_number(call_cost),
      ]);
      popup_counter_rows.push([
        { text: text_of("str_column_call_count") },
        "",
        call_count_cell(line_costs[2]),
      ]);
    }
    for (const secondary of secondary_counters) {
      const secondary_self = secondary.get(line_costs[0]);
      if (!secondary_self) continue;
      popup_counter_rows.push([
        { text: counter_label(secondary) },
        secondary_share_text(
          secondary_self,
          secondary,
          line_counter_baseline(file_path, line_number, secondary),
          line_number,
        ),
        cell_number(secondary_self),
      ]);
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
              "<b>" + html_escape(function_name(line_function_index)) + "</b>",
          })
        : "";
    let markup = `<div class="dbox">`;
    markup +=
      `<a href="#" class="dclose">` +
      `${html_escape(text_of("str_detail_close_symbol"))}</a>`;
    markup +=
      `<div>${html_escape(file_path)}:` +
      `${line_number}${in_function_html}</div>`;
    markup += table_render(
      "heat.detail.stats",
      popup_counter_columns,
      popup_counter_rows,
    );
    const text_parts = [
      heading_line +
        "\n" +
        table_markdown(popup_counter_columns, popup_counter_rows),
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
      const heading = text_fill("str_popup_callees", {
        counter: counter_label(current_counter),
      });
      markup +=
        `<h4>${html_escape(heading)}</h4>` +
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
        ? text_fill("str_popup_function_totals", {
            function: function_entry.name,
            self: function_self_text,
            total: function_total_text,
          })
        : text_fill("str_popup_function_self", {
            function: function_entry.name,
            self: function_self_text,
          });
      markup += `<h4>${html_escape(heading)}</h4>`;
      if (callers.length) {
        const columns = [
          { label: text_of("str_column_call_count"), numeric: true },
          { label: text_of("str_column_share_of_total"), numeric: true },
          counter_column(current_counter),
          function_column(text_of("str_column_caller")),
          {
            label: text_of("str_column_called_at"),
            clip: TABLE_LOCATION_COLUMN_MAX_CHARS,
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
        markup += `<div class="dim">${html_escape(none)}</div>`;
        text_parts.push(heading + "\n" + none);
      } else {
        text_parts.push(heading);
      }
    }
    markup +=
      `<div class="dactions"><a href="#" class="dcopy">` +
      `${html_escape(text_of("str_detail_copy"))}</a>` +
      ` <a href="#" class="dclose2">` +
      `${html_escape(text_of("str_detail_close"))}</a></div>`;
    markup += `</div>`;
    const detail_row = document.createElement("tr");
    detail_row.className = "detail";
    detail_row.innerHTML =
      `<td colspan="${row.cells.length}">` + `${markup}</td>`;
    detail_row.detail_copy_text = text_parts.join("\n\n");
    row.after(detail_row);
    report_ui.layout_activate(detail_row);
  }

  main_panel.addEventListener("click", (click_event) => {
    const chip = click_event.target.closest(".chip");
    if (chip) {
      location.hash = hash_for_line(current_file_path, +chip.dataset.goto);
      return;
    }
    const copy = click_event.target.closest(".dcopy");
    if (copy) {
      click_event.preventDefault();
      navigator.clipboard.writeText(
        copy.closest("tr.detail").detail_copy_text,
      );
      return;
    }
    const close = click_event.target.closest(".dclose, .dclose2");
    if (close) {
      click_event.preventDefault();
      location.hash = hash_for_line(current_file_path);
      return;
    }
    if (click_event.target.closest("a")) return;
    const link_row = click_event.target.closest("tr.rowlink");
    if (link_row) {
      location.hash = link_row.dataset.href;
      return;
    }
    const row = click_event.target.closest("tr.clickable");
    if (row && current_file_path) {
      const line_number = +row.dataset.ln;
      location.hash =
        line_number === detail_line()
          ? hash_for_line(current_file_path)
          : hash_for_line(current_file_path, line_number);
    }
  });

  let current_state = { file: null, line: 0, fn: null };
  let rendered_key = "";
  // The address's parts. An empty hash is home; a part this cannot read (no
  // "=", a key it has no field for, a bad escape or line) is a bad address.
  function state_of_hash(hash) {
    const parsed_state = { file: null, line: 0, fn: null, ev: null };
    for (const part of hash.replace(/^#/, "").split("&")) {
      if (part === "") continue;
      const equals_index = part.indexOf("=");
      const key = part.slice(0, equals_index);
      const value = decodeURIComponent(part.slice(equals_index + 1));
      if (equals_index < 0 || (key === "l" && !Number.isInteger(+value))) {
        throw new Error("str_error_hash_part_unknown " + part);
      }
      if (key === "f") parsed_state.file = value;
      else if (key === "l") parsed_state.line = +value;
      else if (key === "fn") parsed_state.fn = value;
      else if (key === "e") parsed_state.ev = value;
      else throw new Error("str_error_hash_part_unknown " + part);
    }
    return parsed_state;
  }
  function counter_apply(key) {
    current_counter = counter_of(key);
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
  function hash_canonicalize() {
    report_ui.hash_publish(hash_of_state(current_state));
  }
  // A bad address is shown, not thrown: a file:// page is its own opaque
  // origin, so an exception reaches a parent frame stripped to "Script error."
  function hash_fault_show(message) {
    window.report_error_overlay.overlay_show(
      new Error(message),
      text_of("str_error_source_address"),
    );
  }
  function route_render() {
    const parsed_state = state_of_hash(location.hash);
    // a hash naming a counter, file or function this report does not hold is
    // a bad address: it surfaces rather than rendering something else
    if (parsed_state.ev && !counter_find(parsed_state.ev)) {
      hash_fault_show("str_error_hash_counter_unknown " + parsed_state.ev);
      return;
    }
    const counter = counter_of(
      parsed_state.ev || profile_model.heatMapTotals.defaultCounter,
    );
    if (counter.key !== current_counter.key) counter_apply(counter.key);
    let file = parsed_state.file,
      line = parsed_state.line,
      fn = parsed_state.fn;
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
      } else {
        hash_fault_show("str_error_hash_function_unknown " + fn);
        return;
      }
    }
    if (file && !file_table[file]) {
      hash_fault_show("str_error_hash_file_unknown " + file);
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
      if (line && !document.getElementById("L" + line)) line = 0;
      detail_set(line);
    }
    current_state = { file: file, line: line, fn: fn };
    hash_canonicalize();
  }
  window.addEventListener("hashchange", route_render);
  report_ui.parent_listen((message_data) => {
    if (message_data === "report_ui:layout_reset") {
      report_ui.layout_reset();
    }
  });

  let resize_debounce_timer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resize_debounce_timer);
    resize_debounce_timer = setTimeout(() => {
      tail_fit();
      minimap_layout();
    }, LAYOUT_RESIZE_SETTLE_DELAY_MS);
  });
  counter_select.addEventListener("change", (change_event) => {
    location.hash = hash_of_state(
      Object.assign({}, current_state, { ev: change_event.target.value }),
    );
  });
  scale_select.addEventListener("change", (change_event) => {
    active_scale = SCALE_CHOICES.find(
      (entry) => entry.value === change_event.target.value,
    );
    view_storage.value_write("heat.scale", active_scale.value);
    rendered_key = "";
    route_render();
  });
  sort_select.addEventListener("change", (change_event) => {
    sort_mode = change_event.target.value;
    view_storage.value_write("heat.sort", sort_mode);
    tree_render();
  });
  document.getElementById("q").addEventListener("input", (input_event) => {
    search_query = input_event.target.value.trim().toLowerCase();
    tree_render();
  });
  counter_apply(current_counter.key);
  route_render();
})();
