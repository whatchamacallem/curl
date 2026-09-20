(function () {
  "use strict";
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
  document.getElementById("sort").value = sort_mode;
  report_ui.pane_splitter.attach(
    document.getElementById("split"),
    tree_panel,
    "heat.tree",
    120,
  );

  const vector_at = (cost_vector, index) =>
    cost_vector && index < cost_vector.length ? cost_vector[index] : 0;
  const event_list = [];
  profile_model.heatMapTotals.events.forEach((name, index) => {
    event_list.push({
      key: name,
      long: profile_model.heatMapTotals.eventLong[name] || "",
      get: (cost_vector) => vector_at(cost_vector, index),
    });
  });
  for (const [name, terms, long] of profile_model.heatMapTotals.derived) {
    const get = (cost_vector) =>
      terms.reduce(
        (running_total, term) =>
          running_total + term[0] * vector_at(cost_vector, term[1]),
        0,
      );
    event_list.push({
      key: name,
      long: long || profile_model.heatMapTotals.eventLong[name] || "",
      get,
      derived: true,
    });
  }
  const event_find = (key) => event_list.find((event) => event.key === key);
  let current_event =
    event_find(profile_model.heatMapTotals.defaultEvent) || event_list[0];
  const secondary_events = ["D1m", "DLm", "Bcm"]
    .map(event_find)
    .filter(Boolean);

  const EVENT_DESCRIPTIONS = {
    Ir: "instructions",
    Dr: "data reads",
    Dw: "data writes",
    I1mr: "L1 icache miss",
    D1mr: "L1 dcache read miss",
    D1mw: "L1 dcache write miss",
    ILmr: "L3 icache miss",
    DLmr: "L3 dcache read miss",
    DLmw: "L3 dcache write miss",
    Bc: "branches",
    Bcm: "misprediction",
    Bi: "indirect branches",
    Bim: "indirect misprediction",
    Ge: "bus events",
    sysCount: "syscalls",
    sysTime: "syscall time",
    sysCpuTime: "syscall cpu time",
    AcCost1: "L1 access cost",
    SpLoss1: "L1 spatial loss",
    AcCost2: "L3 access cost",
    SpLoss2: "L3 spatial loss",
    ILdmr: "L3 insn write-back",
    DLdmr: "L3 read write-back",
    DLdmw: "L3 write write-back",
    D1m: "L1 cache",
    DLm: "L3 cache",
    L1m: "L1 cache, all",
    LLm: "L3 cache, all",
    Bm: "misprediction, all",
    CEst: "cycle estimate",
  };
  const event_label = (event) =>
    EVENT_DESCRIPTIONS[event.key]
      ? EVENT_DESCRIPTIONS[event.key] + " / " + event.key
      : event.key;
  const event_description = (event) =>
    EVENT_DESCRIPTIONS[event.key] || event.long || event.key;
  const event_select = document.getElementById("event");
  let event_label_width = 0;
  for (const event of event_list) {
    const option = document.createElement("option");
    option.value = event.key;
    option.textContent = event.key + (event.long ? " - " + event.long : "");
    event_label_width = Math.max(event_label_width, option.textContent.length);
    event_select.appendChild(option);
  }
  event_select.value = current_event.key;

  event_select.style.width = event_label_width + 4 + "ch";
  let total_cost = 1,
    maximum_share = 1,
    secondary_maximums = {};
  const current_value = (cost_vector) => current_event.get(cost_vector);
  const absolute = Math.abs;

  function scale_recompute() {
    total_cost = current_event.get(profile_model.heatMapTotals.totals) || 1;
    let maximum = 0,
      maximum_percent = 0;
    for (const [file_path, file] of Object.entries(file_table)) {
      for (const [line_number, line_costs] of Object.entries(file.lines)) {
        const self_cost = absolute(current_value(line_costs[0]));
        if (self_cost > maximum) maximum = self_cost;
        if (IS_DIFF) {
          const baseline_cost = line_baseline(file_path, line_number);
          maximum_percent = Math.max(
            maximum_percent,
            absolute(
              share_of_baseline(current_value(line_costs[0]), baseline_cost),
            ),
          );
        }
      }
    }
    maximum_share = Math.max(
      IS_DIFF ? maximum_percent : (100 * maximum) / total_cost,
      0.0001,
    );
    secondary_maximums = {};
    for (const secondary of secondary_events) {
      let secondary_maximum = 0;
      for (const file of Object.values(file_table)) {
        for (const line_costs of Object.values(file.lines)) {
          const self_cost = absolute(secondary.get(line_costs[0]));
          if (self_cost > secondary_maximum) {
            secondary_maximum = self_cost;
          }
        }
      }
      const secondary_total =
        secondary.get(profile_model.heatMapTotals.totals) || 1;
      secondary_maximums[secondary.key] = {
        total: secondary_total,
        max_share: Math.max(
          (100 * secondary_maximum) / secondary_total,
          0.0001,
        ),
      };
    }
  }

  const html_escape = (value) =>
    String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  const share_of_total = (value) => (100 * value) / total_cost;
  let share_text = (percent) =>
    percent >= 9.95
      ? percent.toFixed(1) + "%"
      : percent >= 0.01
        ? percent.toFixed(2) + "%"
        : percent > 0
          ? "<0.01%"
          : "";
  const share_of_total_text = (value) => share_text(share_of_total(value));

  let human_text = (value) => {
    let unit = "";
    for (const next_unit of ["K", "M", "G", "T"]) {
      if (value < 999.5) break;
      value /= 1000;
      unit = next_unit;
    }
    return (unit && value < 9.95 ? value.toFixed(1) : value.toFixed(0)) + unit;
  };
  const cell_number = (value) => ({
    text: human_text(value),
  });
  let HEADING_PREFIX = "Hottest",
    CHIP_HEADING = "hottest lines";
  const SELF_COLUMN = {
    label: "self",
    num: true,
  };
  const HAS_CALL_GRAPH = function_table.some(
    (function_entry) => function_entry.callers.length > 0,
  );

  const IS_DIFF = !!profile_model.heatMapTotals.diff;
  const function_baselines = profile_model.functionBaseline || [];
  let baseline_of = () => null;
  let share_of_baseline = (value, baseline_cost) => share_of_total(value);
  let share_of_baseline_text = (value, baseline_cost) =>
    share_of_total_text(value);
  if (IS_DIFF) {
    const plain_share_text = share_text,
      plain_human_text = human_text;
    const multiple_text = (percent) =>
      percent / 100 < 99.99 ? (percent / 100).toFixed(2) + "x" : ">1000x";
    const magnitude_text = (percent) =>
      percent < 0.01
        ? "≈0.00%"
        : percent > 100
          ? multiple_text(percent)
          : plain_share_text(percent);
    const signed_text = (percent, text) =>
      text[0] === ">" || text[0] === "≈"
        ? text
        : (percent < 0 ? "-" : "") + text;
    share_text = (percent) =>
      percent
        ? (percent < 0 ? "▼" : "▲") +
          signed_text(percent, magnitude_text(absolute(percent)))
        : "";
    human_text = (value) =>
      !value
        ? "0"
        : (value < 0 ? "-" : "") + plain_human_text(absolute(value));
    HEADING_PREFIX = "Most changed";
    CHIP_HEADING = "most changed lines";
    baseline_of = (cost_vector) => {
      if (!cost_vector) return null;
      const baseline_cost = absolute(current_event.get(cost_vector));
      return baseline_cost ? baseline_cost : null;
    };
    share_of_baseline = (value, baseline_cost) =>
      baseline_cost ? (100 * value) / baseline_cost : value ? 100 : 0;
    share_of_baseline_text = (value, baseline_cost) =>
      baseline_cost
        ? share_text((100 * value) / baseline_cost)
        : value
          ? share_text(100)
          : "";
  }
  const line_baseline = (file_path, line_number) => {
    const baseline_table =
      file_table[file_path] && file_table[file_path].baseline;
    return baseline_of(baseline_table && baseline_table[line_number]);
  };
  const function_baseline_of = (function_index) =>
    baseline_of(function_baselines[function_index]);

  const scale_select = document.getElementById("scale");
  const SCOPE_CHOICES = IS_DIFF
    ? [["line", "per line"]]
    : [
        ["global", "global"],
        ["file", "per file"],
        ["function", "per function"],
      ];
  const SCALE_CHOICES = [];
  ["log", "linear"].forEach((curve) => {
    SCOPE_CHOICES.forEach((scope) =>
      SCALE_CHOICES.push({
        value: curve + "/" + scope[0],
        curve: curve,
        scope: scope[0],
        label: SCOPE_CHOICES.length > 1 ? curve + ", " + scope[1] : curve,
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
  scale_select.style.width = scale_label_width + 4 + "ch";

  const MINIMUM_SHARE = 0.001;
  const FULL_HEAT_PERCENT = 100;
  function heat_of_share(percent, max_share) {
    const heat_sign = IS_DIFF && percent < 0 ? -1 : 1;
    percent = absolute(percent);
    if (IS_DIFF) {
      percent = Math.min(percent, FULL_HEAT_PERCENT);
      max_share = Math.min(max_share, FULL_HEAT_PERCENT);
    }
    if (percent <= 0) return 0;
    if (active_scale.curve === "linear") {
      return heat_sign * Math.min(1, percent / max_share);
    }
    if (percent < MINIMUM_SHARE) return 0;
    const log_span = Math.log10(
      Math.max(max_share, MINIMUM_SHARE * 10) / MINIMUM_SHARE,
    );
    return (
      heat_sign * Math.min(1, Math.log10(percent / MINIMUM_SHARE) / log_span)
    );
  }
  function heat_of_cost(cost, max_share) {
    return heat_of_share(share_of_total(cost), max_share);
  }
  function heat_of_delta(cost, baseline_cost, max_share) {
    return heat_of_share(share_of_baseline(cost, baseline_cost), max_share);
  }

  const channels_of = (hex) =>
    [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16));
  const COLOR_STOPS = profile_model.theme.heat.map(channels_of),
    BACKGROUND_COLOR = channels_of(profile_model.theme.bg);
  function cell_style(heat_value, alpha_minimum, alpha_maximum) {
    const magnitude = absolute(heat_value);
    if (magnitude <= 0) return "";
    const scaled_position =
      (IS_DIFF ? (heat_value + 1) * 0.5 : heat_value) *
      (COLOR_STOPS.length - 1);
    const index = Math.min(
      Math.max(Math.floor(scaled_position), 0),
      COLOR_STOPS.length - 2,
    );
    const fraction = scaled_position - index;
    const alpha_value =
      alpha_minimum + (alpha_maximum - alpha_minimum) * magnitude;
    const mixed_channels = [0, 1, 2].map((channel) => {
      const low_channel = COLOR_STOPS[index][channel],
        high_channel = COLOR_STOPS[index + 1][channel];
      return Math.round(
        BACKGROUND_COLOR[channel] +
          (low_channel +
            (high_channel - low_channel) * fraction -
            BACKGROUND_COLOR[channel]) *
            alpha_value,
      );
    });
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
  const cell_style_strong = (heat_value) => cell_style(heat_value, 0.18, 0.92);
  const cell_style_soft = (heat_value) => cell_style(heat_value, 0.12, 0.55);

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
  const CALLS_MAXIMUM = per_function_calls.reduce(
    (maximum, call_count) => Math.max(maximum, call_count),
    0,
  );
  const CALLS_MAX_SHARE = Math.max(
    (100 * CALLS_MAXIMUM) / CALLS_TOTAL,
    0.0001,
  );
  const call_count_cell = (call_count) =>
    call_count
      ? {
          text: human_text(call_count),
          style: cell_style_strong(
            heat_of_share((100 * call_count) / CALLS_TOTAL, CALLS_MAX_SHARE),
          ),
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
    if (event_list.length > 1) {
      hash_parts.push("e=" + hash_encode(state.ev || current_event.key));
    }
    return hash_parts.length ? "#" + hash_parts.join("&") : "";
  }
  const hash_for_line = (file_path, line) =>
    hash_of_state({ file: file_path, line: line });
  const hash_for_function = (name) => hash_of_state({ fn: name });
  function function_name(index) {
    return index != null && function_table[index]
      ? function_table[index].name
      : "?";
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
  const SYMBOL_WIDTH = 20;
  const SOURCE_WIDTH = 80;
  const HOT_CHIP_LIMIT = 10;

  const COLUMN_PADDING = 3;

  const cell_normalize = (value) =>
    value && typeof value === "object"
      ? value
      : { text: value == null ? "" : String(value) };

  function column_widths(columns, cell_rows) {
    return columns.map((column, column_index) => {
      let width = column.label.length;
      if (column.width != null) width = Math.max(width, column.width);
      else {
        for (const row of cell_rows) {
          if (!row[column_index]) continue;
          width = Math.max(width, (row[column_index].text || "").length);
        }
        if (column.clip != null) {
          width = Math.max(column.label.length, Math.min(width, column.clip));
        }
      }
      return width + COLUMN_PADDING;
    });
  }
  function table_html(key, columns, rows, options) {
    options = options || {};
    const cell_rows = rows.map((row) => row.map(cell_normalize));
    const column_width_list = column_widths(columns, cell_rows);
    const table_classes = [
      "cols",
      options.fill ? "fill" : "",
      options.cls || "",
    ]
      .filter(Boolean)
      .join(" ");
    let markup = options.bare ? "" : `<div class="tbl">`;
    markup +=
      `<div class="tbl-cols"><table class="${table_classes}"` +
      ` data-key="${html_escape(key)}"><colgroup>`;
    columns.forEach((column, column_index) => {
      const column_classes = [
        column_index % 2 ? "alt" : "",
        column.grow ? "grow" : "",
      ]
        .filter(Boolean)
        .join(" ");
      markup +=
        `<col${column_classes ? ` class="${column_classes}"` : ""}` +
        ` data-min="${column.label.length + COLUMN_PADDING}ch"` +
        ` style="width:${column_width_list[column_index]}ch">`;
    });
    markup += `</colgroup><thead><tr>`;
    for (const column of columns) {
      markup +=
        `<th${column.num ? ' class="n"' : ""}>` +
        `${html_escape(column.label)}</th>`;
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
        const column = columns[column_index] || {};
        const class_names = [
          column.num ? "n" : "",
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
    const column_width_list = columns.map((column, column_index) => {
      let width = column.label.length;
      for (const row of cell_rows) {
        if (!row[column_index]) continue;
        width = Math.max(width, (row[column_index].text || "").length);
      }
      return width;
    });
    const pad = (text, width, numeric) =>
      numeric ? text.padStart(width) : text.padEnd(width);
    const line = (cells) =>
      "| " +
      cells
        .map((text, column_index) =>
          pad(
            text,
            column_width_list[column_index],
            columns[column_index].num,
          ),
        )
        .join(" | ") +
      " |";
    const output_parts = [line(columns.map((column) => column.label))];
    const rule = columns.map((column, column_index) =>
      column.num
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
  const event_column = (event, extra) =>
    Object.assign({ label: event.key, num: true }, extra || {});
  const secondary_columns = () =>
    secondary_events.map((secondary) =>
      event_column(secondary, {
        label: event_label(secondary),
        cls: "x",
      }),
    );
  function secondary_cells(cost_vector) {
    return secondary_events.map((secondary) => {
      const self_cost = secondary.get(cost_vector),
        maximum_entry = secondary_maximums[secondary.key];
      const percent = (100 * self_cost) / maximum_entry.total;
      const heat_value = heat_of_share(percent, maximum_entry.max_share);
      return {
        text: self_cost ? share_text(percent) : "",
        style: cell_style_strong(heat_value),
        cls: heat_value > 0.45 ? "hot" : "",
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
      let baseline_cost = 0;
      if (IS_DIFF) {
        const baseline_table = file_table[file_path].baseline || {};
        for (const cost_vector of Object.values(baseline_table)) {
          baseline_cost += absolute(current_event.get(cost_vector));
        }
      }
      node_insert(
        file_path,
        current_value(file_table[file_path].self),
        baseline_cost,
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
  const DIRECTORY_MAX_SHARE = 100;
  function tree_render() {
    const output_parts = [];
    function nodes_emit(tree_node, depth) {
      const directories = [...tree_node.dirs.values()]
        .filter(subtree_matches)
        .sort(node_compare);
      for (const directory_node of directories) {
        const is_expanded = search_query
          ? true
          : expanded_directories.has(directory_node.path);
        const heat_style_attribute = cell_style_soft(
          heat_of_delta(
            directory_node.self,
            directory_node.base,
            DIRECTORY_MAX_SHARE,
          ),
        );
        output_parts.push(
          `<div class="node dir${heat_style_attribute ? " heat" : ""}"` +
            ` data-dir="${html_escape(directory_node.path)}"` +
            ` style="padding-left:${6 + depth * 14}px;` +
            `${heat_style_attribute}">` +
            `<span class="caret">` +
            `${is_expanded ? "▼" : "▶"}</span>` +
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
          : cell_style_soft(
              heat_of_delta(file.self, file.base, DIRECTORY_MAX_SHARE),
            );
        output_parts.push(
          `<div class="node file${file.cold ? " cold" : ""}` +
            `${heat_style_attribute ? " heat" : ""}${selected_class}"` +
            ` data-file="${html_escape(file.path)}"` +
            ` style="padding-left:${6 + depth * 14}px;` +
            `${heat_style_attribute}">` +
            `<span class="caret">▶</span>` +
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
            ` style="padding-left:${6 + depth * 14}px">` +
            `<span class="caret">` +
            `${is_expanded ? "▼" : "▶"}</span>` +
            `<span class="name">no samples</span>` +
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
      if (file.source != null) {
        const source_lines = file.source.split("\n");
        if (entry[1] >= 1 && entry[1] <= source_lines.length) {
          source_snippet = source_lines[entry[1] - 1].trim().slice(0, 110);
        }
      }
      return [entry[0], entry[1], entry[2], entry[3], source_snippet];
    });
  }
  function home_render() {
    current_file_path = null;
    let markup = `<div class="home">`;
    const line_rows = top_lines(60);
    markup +=
      `<h2>${HEADING_PREFIX} lines by ` +
      `${html_escape(event_label(current_event))}</h2>` +
      table_html(
        "heat.home.lines",
        [
          { label: "#", num: true },
          SELF_COLUMN,
          {
            label: "function",
            width: SYMBOL_WIDTH,
          },
          {
            label: "defined at",
            clip: 28,
          },
          {
            label: "source",
            clip: 36,
          },
          event_column(current_event),
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
              style: cell_style_strong(
                heat_of_delta(cost, baseline_cost, maximum_share),
              ),
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
            ...secondary_cells(line_costs[0]),
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
      .slice(0, 60);
    const function_max_share = IS_DIFF
      ? Math.max(
          ...top_functions.map(([function_index, self_cost]) =>
            absolute(
              share_of_baseline(
                self_cost,
                function_baseline_of(function_index),
              ),
            ),
          ),
          0.0001,
        )
      : maximum_share;
    const call_columns = HAS_CALL_GRAPH
      ? [
          {
            label: "calls",
            num: true,
          },
          {
            label: "incl",
            num: true,
          },
        ]
      : [];
    markup +=
      `<h2>${HEADING_PREFIX} functions by self ` +
      `${html_escape(event_label(current_event))}</h2>` +
      table_html(
        "heat.home.functions",
        [
          { label: "#", num: true },
          SELF_COLUMN,
          {
            label: "function",
            width: SYMBOL_WIDTH,
          },
          {
            label: "defined at",
            clip: 48,
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
              style: cell_style_strong(
                heat_of_delta(self_cost, baseline_cost, function_max_share),
              ),
            },
            { text: function_entry.name },
            {
              text: location_text,
              html: function_link(function_index, location_text),
            },
            ...calls,
            ...secondary_cells(function_entry.self),
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
    if (!file) {
      home_render();
      return;
    }
    const is_first_view = current_file_path !== file_path,
      kept_scroll_top = is_first_view ? -1 : main_panel.scrollTop;
    current_file_path = file_path;
    tree_reveal(file_path);
    const lines = file.lines;
    let file_maximum_cost = 0;
    for (const line_costs of Object.values(lines)) {
      const self_cost = absolute(current_value(line_costs[0]));
      if (self_cost > file_maximum_cost) file_maximum_cost = self_cost;
    }
    const max_share =
      active_scale.scope === "line"
        ? FULL_HEAT_PERCENT
        : active_scale.scope === "file"
          ? Math.max(share_of_total(file_maximum_cost), 0.0001)
          : maximum_share;
    const function_max_shares = {};
    if (active_scale.scope === "function") {
      for (const [line_number, line_costs] of Object.entries(lines)) {
        const owner = file.lineFunction[line_number];
        if (owner == null) continue;
        function_max_shares[owner] = Math.max(
          function_max_shares[owner] || 0.0001,
          absolute(share_of_total(current_value(line_costs[0]))),
        );
      }
    }
    const max_share_for_line = (line_number) => {
      if (active_scale.scope !== "function") return max_share;
      const owner = file.lineFunction[line_number];
      return owner != null ? function_max_shares[owner] || 0.0001 : max_share;
    };
    let markup =
      `<div class="srcwrap"><div class="fhead band">` +
      `<span class="path">${html_escape(file_path)}</span>`;
    const file_self_cost = current_value(file.self);
    let file_baseline_cost = 0;
    if (IS_DIFF) {
      for (const cost_vector of Object.values(file.baseline || {})) {
        file_baseline_cost += absolute(current_event.get(cost_vector));
      }
    }
    markup +=
      `<span class="stat">` +
      `self <b>` +
      `${share_of_baseline_text(file_self_cost, file_baseline_cost) || "0%"}` +
      `</b>` +
      ` (${human_text(file_self_cost)}` +
      ` ${html_escape(event_label(current_event))})</span>`;
    for (const secondary of secondary_events) {
      const self_cost = secondary.get(file.self);
      if (!self_cost) continue;
      markup +=
        `<span class="stat">` +
        `${html_escape(event_label(secondary))}` +
        ` <b>${share_text(
          (100 * self_cost) / secondary_maximums[secondary.key].total,
        )}</b>` +
        ` (${human_text(self_cost)})</span>`;
    }
    if (file.group === "external") {
      const raw = html_escape(file.raw);
      markup += `<span class="stat">not in this repo (${raw})</span>`;
    }
    markup += `</div>`;
    if (file.source == null) {
      markup += `<div class="nosrc">Source not available.</div></div>`;
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
            share_of_baseline(entry[1], line_baseline(file_path, entry[0])),
          ) >= 0.01,
      )
      .slice(0, HOT_CHIP_LIMIT);
    if (chip_lines.length) {
      markup +=
        `<div class="chips">` + `<span class="lbl">${CHIP_HEADING}</span>`;
      for (const [line_number, cost] of chip_lines) {
        const baseline_cost = line_baseline(file_path, line_number);
        markup +=
          `<span class="chip" data-goto="${line_number}"` +
          ` style="${cell_style_strong(
            heat_of_delta(
              cost,
              baseline_cost,
              max_share_for_line(line_number),
            ),
          )}">` +
          `${line_number} -` +
          ` ${share_of_baseline_text(cost, baseline_cost)}</span>`;
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
      const row_max_share = max_share_for_line(line_number);
      const heat_value = heat_of_delta(
          self_cost,
          baseline_cost,
          row_max_share,
        ),
        heat_style_attribute = cell_style_strong(heat_value);
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
              text: calls ? share_of_baseline_text(calls, baseline_cost) : "",
              style: cell_style_strong(
                heat_of_delta(calls, baseline_cost, row_max_share),
              ),
            },
          ]
        : [];
      rows.push([
        {
          text: self_cost
            ? share_of_baseline_text(self_cost, baseline_cost)
            : "",
          style: heat_style_attribute,
          cls: heat_value > 0.45 ? "hot" : "",
        },
        { text: String(line_number), style: heat_style_attribute },
        { text, style: heat_style_attribute },
        ...call_cell,
        ...(line_costs
          ? secondary_cells(line_costs[0])
          : secondary_events.map(() => "")),
      ]);
    };
    const source_lines = file.source.split("\n");
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
      source_row_emit(
        +line_key,
        "(line beyond end of file: source changed since" +
          " the profile was taken)",
      );
    }

    const call_column = HAS_CALL_GRAPH
      ? [
          {
            label: "calls",
            num: true,
            cls: "incl",
          },
        ]
      : [];
    const columns = [
      event_column(current_event, {
        cls: "self",
      }),
      {
        label: "line",
        num: true,
        width: String(line_count).length + 2,
        cls: "ln",
      },
      { label: "source", width: SOURCE_WIDTH, grow: true, cls: "code" },
      ...call_column,
      ...secondary_columns(),
    ];
    markup += table_html("heat.src", columns, rows, {
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
    const cover = covered_height(table_element),
      row_height_px = last.getBoundingClientRect().height;
    tail.style.height =
      Math.max(0, (main_panel.clientHeight - cover - row_height_px) / 2) +
      "px";
  }

  const MINIMUM_COLUMNS = 80;
  const MINIMUM_LINES = 40;
  let character_width_px = 0,
    scale_factor = 1,
    clone_height_px = 0;
  function minimap_clear() {
    minimap_panel.classList.add("empty");
    minimap_box.innerHTML = "";
    minimap_viewport.hidden = true;
  }
  function minimap_build() {
    const table_element = main_panel.querySelector("table.src");
    const table_body = table_element && table_element.tBodies[0];
    if (!table_body || table_body.rows.length < MINIMUM_LINES) {
      minimap_clear();
      return;
    }

    const probe_cell = table_body.rows[0].querySelector("td.code");
    if (!probe_cell) {
      minimap_clear();
      return;
    }
    const probe_span = document.createElement("span");
    probe_span.textContent = "0123456789";
    probe_span.style.cssText =
      "position:absolute;visibility:hidden;white-space:pre;font:inherit";
    probe_cell.appendChild(probe_span);
    character_width_px = probe_span.getBoundingClientRect().width / 10 || 7.2;
    probe_cell.removeChild(probe_span);

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

    scale_factor = Math.min(
      1,
      band_width_px / (MINIMUM_COLUMNS * character_width_px),
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
      bottom: main.top + main_panel.clientHeight,
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
      8,
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
      width: SYMBOL_WIDTH,
    });
    const location_column = {
      label: "defined at",
      clip: 48,
    };
    const call_cost = current_value(line_costs[1]);
    const self_cost = current_value(line_costs[0]);
    const line_baseline_cost = line_baseline(file_path, line_number);
    const self_label = function_index != null ? "self" : "line self";
    const stat_columns = [
      { label: "event" },
      { label: "global %", num: true },
      { label: "count", num: true },
    ];
    const stat_rows = [
      [
        {
          text: `${self_label} ${event_label(current_event)}`,
        },
        share_of_baseline_text(self_cost, line_baseline_cost) || "0%",
        cell_number(self_cost),
      ],
    ];
    if (call_cost) {
      stat_rows.push([
        { text: "calls" },
        share_of_baseline_text(call_cost, line_baseline_cost),
        cell_number(call_cost),
      ]);
      stat_rows.push([
        { text: "call count" },
        "",
        call_count_cell(line_costs[2]),
      ]);
    }
    for (const secondary of secondary_events) {
      const secondary_self = secondary.get(line_costs[0]);
      if (!secondary_self) continue;
      stat_rows.push([
        { text: event_label(secondary) },
        share_text(
          (100 * secondary_self) / secondary_maximums[secondary.key].total,
        ),
        cell_number(secondary_self),
      ]);
    }
    const in_function_note =
      line_function_index != null
        ? " in " + function_name(line_function_index)
        : "";
    const heading_line = `${file_path}:${line_number}${in_function_note}`;
    const in_function_html =
      line_function_index != null
        ? " in <b>" + html_escape(function_name(line_function_index)) + "</b>"
        : "";
    let markup = `<div class="dbox">`;
    markup += `<a href="#" class="dclose">[X]</a>`;
    markup +=
      `<div>${html_escape(file_path)}:` +
      `${line_number}${in_function_html}</div>`;
    markup += table_html("heat.detail.stats", stat_columns, stat_rows);
    const text_parts = [
      heading_line + "\n" + table_markdown(stat_columns, stat_rows),
    ];
    if (callees.length) {
      const columns = [
        { label: "% of total", num: true },
        event_column(current_event),
        { label: "call count", num: true },
        function_column("callee"),
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
      const event_text = event_label(current_event);
      const heading = `calls from this line (total ${event_text})`;
      markup +=
        `<h4>${html_escape(heading)}</h4>` +
        table_html("heat.detail.callees", columns, rows);
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
        ) || "0%";
      const function_total_text =
        share_of_baseline_text(
          current_value(function_entry.self) +
            current_value(function_entry.calls),
          function_baseline_cost,
        ) || "0%";
      const heading = HAS_CALL_GRAPH
        ? `${function_entry.name} by call count:` +
          ` self ${function_self_text}, total ${function_total_text}.`
        : `${function_entry.name}: self ${function_self_text}.`;
      markup += `<h4>${html_escape(heading)}</h4>`;
      if (callers.length) {
        const columns = [
          { label: "call count", num: true },
          { label: "% of total", num: true },
          event_column(current_event),
          function_column("caller"),
          { label: "called at", clip: 48 },
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
        markup += table_html("heat.detail.callers", columns, rows);
        text_parts.push(heading + "\n" + table_markdown(columns, rows));
      } else if (HAS_CALL_GRAPH) {
        const none = "(no recorded caller - a root or a resolver stub)";
        markup += `<div class="dim">${none}</div>`;
        text_parts.push(heading + "\n" + none);
      } else {
        text_parts.push(heading);
      }
    }
    markup +=
      `<div class="dactions"><a href="#" class="dcopy">copy</a>` +
      ` <a href="#" class="dclose2">close</a></div>`;
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
  function state_of_hash(hash) {
    const parsed_state = { file: null, line: 0, fn: null, ev: null };
    for (const part of (hash || "").replace(/^#/, "").split("&")) {
      const equals_index = part.indexOf("=");
      if (equals_index < 0) continue;
      let value;
      try {
        value = decodeURIComponent(part.slice(equals_index + 1));
      } catch (decode_error) {
        continue;
      }
      const key = part.slice(0, equals_index);
      if (key === "f") parsed_state.file = value;
      else if (key === "l") parsed_state.line = +value || 0;
      else if (key === "fn") parsed_state.fn = value;
      else if (key === "e") parsed_state.ev = value;
    }
    return parsed_state;
  }
  function event_apply(key) {
    current_event = event_find(key) || event_list[0];
    event_select.value = current_event.key;
    scale_recompute();
    tree_root = tree_build();
    for (const directory_node of tree_root.dirs.values()) {
      if (absolute(directory_node.self) / total_cost > 0.05) {
        expanded_directories.add(directory_node.path);
      }
    }
  }
  function hash_canonicalize() {
    const hash = hash_of_state(current_state);
    if (hash !== location.hash) history.replaceState(null, "", hash || "#");
    if (window.parent !== window) {
      window.parent.postMessage(
        { report_ui: "hash_changed", hash: hash },
        "*",
      );
    }
  }
  function route_render() {
    const parsed_state = state_of_hash(location.hash);
    const event =
      event_find(parsed_state.ev) ||
      event_find(profile_model.heatMapTotals.defaultEvent) ||
      event_list[0];
    if (event.key !== current_event.key) event_apply(event.key);
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
        fn = null;
        file = null;
        line = 0;
      }
    }
    if (file && !file_table[file]) {
      file = null;
      line = 0;
    }

    const key =
      (file ? "file\n" + file : "home") +
      "\n" +
      current_event.key +
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
  window.addEventListener("message", (message_event) => {
    if (message_event.data === "report_ui:reset_columns") {
      report_ui.layout_reset();
    }
  });

  let resize_debounce_timer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resize_debounce_timer);
    resize_debounce_timer = setTimeout(() => {
      tail_fit();
      minimap_layout();
    }, 120);
  });
  event_select.addEventListener("change", (change_event) => {
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
  document
    .getElementById("sort")
    .addEventListener("change", (change_event) => {
      sort_mode = change_event.target.value;
      view_storage.value_write("heat.sort", sort_mode);
      tree_render();
    });
  document.getElementById("q").addEventListener("input", (input_event) => {
    search_query = input_event.target.value.trim().toLowerCase();
    tree_render();
  });
  event_apply(current_event.key);
  route_render();
})();
