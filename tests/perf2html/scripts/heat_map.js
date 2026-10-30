// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const CALLGRIND_FILE_DATA_ERROR_CODE = settings_(
    "CALLGRIND_FILE_DATA_ERROR_CODE",
  );
  const COUNTER_LIST_CALLEES_LINE_NAME = settings_(
    "COUNTER_LIST_CALLEES_LINE_NAME",
  );
  const COUNTER_LIST_CALLERS_LINE_NAME = settings_(
    "COUNTER_LIST_CALLERS_LINE_NAME",
  );
  const COUNTER_LIST_CALLS_LINE_NAME = settings_(
    "COUNTER_LIST_CALLS_LINE_NAME",
  );
  const DATABASE_CELL_SEPARATOR_TEXT = settings_(
    "DATABASE_CELL_SEPARATOR_TEXT",
  );
  const HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX = settings_(
    "HEAT_MAP_MINIMAP_VIEWPORT_BOX_SMALLEST_PX",
  );
  const HEAT_MAP_MODEL_DIR_NAME = settings_("HEAT_MAP_MODEL_DIR_NAME");
  const HEAT_MAP_MODEL_GLOBAL_NAME = settings_("HEAT_MAP_MODEL_GLOBAL_NAME");
  const HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_LEAST_SHARE = settings_(
    "HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_LEAST_SHARE",
  );
  const HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_MAX_COUNT = settings_(
    "HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_MAX_COUNT",
  );
  const HEAT_MAP_SOURCE_TAB_SIZE_CHARS = settings_(
    "HEAT_MAP_SOURCE_TAB_SIZE_CHARS",
  );
  const HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS = settings_(
    "HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS",
  );
  const HEAT_MAP_TREE_AUTO_EXPAND_ABOVE_SHARE = settings_(
    "HEAT_MAP_TREE_AUTO_EXPAND_ABOVE_SHARE",
  );
  const HEAT_MAP_VIEW_ENTRY = settings_("HEAT_MAP_VIEW_ENTRY");
  const RANKING_COUNTER_NAME = settings_("RANKING_COUNTER_NAME");
  const REPORT_SOURCES_DIR_NAME = settings_("REPORT_SOURCES_DIR_NAME");
  const STYLE_HEAT_MAP_TREE_INDENT_PER_LEVEL_CHARS = settings_(
    "STYLE_HEAT_MAP_TREE_INDENT_PER_LEVEL_CHARS",
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
  const TABLE_COLUMN_FUNCTION_NAME = settings_("TABLE_COLUMN_FUNCTION_NAME");
  const TABLE_COLUMN_LINE_NAME = settings_("TABLE_COLUMN_LINE_NAME");
  const TABLE_COLUMN_LOCATION_NAME = settings_("TABLE_COLUMN_LOCATION_NAME");
  const TABLE_COLUMN_SOURCE_NAME = settings_("TABLE_COLUMN_SOURCE_NAME");
  const WIDGET_KEY_NAMES = settings_("WIDGET_KEY_NAMES");
  if (!window.report_source_database_)
    window.throw_exception_("str_error_internal");
  const source_database = window.report_source_database_;
  let profile_model = null,
    file_table = null,
    function_table = null,
    shown_test_name = null;
  // Holds the tree and its bar, hung from the source table's first title.
  const tree_track = document.getElementById("heat-map-tree-track-template-")
    .content.firstElementChild;
  const tree_panel = tree_track.querySelector("#heat-map-tree-");
  const main_panel = document.getElementById("heat-map-main-");
  const minimap_panel = document.getElementById("heat-map-minimap-");
  const minimap_box = document.getElementById("heat-map-minimap-box-");
  const minimap_viewport = document.getElementById(
    "heat-map-minimap-viewport-",
  );
  let current_file_path = null;
  tree_panel.setAttribute(
    "aria-label",
    window.ui_strings_.text("str_heat_map_tree_label"),
  );
  main_panel.setAttribute(
    "aria-label",
    window.ui_strings_.text("str_heat_map_main_label"),
  );
  document.title = window.ui_strings_.text("str_view_heat_map");

  const vector_at = (cost_vector, index) =>
    cost_vector && index < cost_vector.length ? cost_vector[index] : 0;
  let counter_list = null,
    ranking_counter = null;
  const counter_find = (key) =>
    counter_list.find((counter) => counter.key === key);

  const text = window.ui_strings_.text;
  const text_fill = window.ui_strings_.text_fill;
  const render_element = window.render_element_;
  const render_html_escape = window.render_html_escape_;
  const render_menu_button = window.render_menu_button_;
  let active_scale = null,
    shown_line_names = null,
    sort_mode = null;
  const counter_label = (counter) =>
    report_preferences_.counter_label(counter.key);
  function counters_build() {
    counter_list = report_preferences_.counter_readers(
      profile_model.heatMapTotals.counters,
      profile_model.heatMapTotals.derived,
    );
    ranking_counter = counter_find(RANKING_COUNTER_NAME);
  }
  const ranking_value = (cost_vector) => ranking_counter.get(cost_vector);
  const absolute = Math.abs;

  // Takes the relayed preferences: the columns, the scale and the tree order.
  function preferences_handler() {
    const view_preferences = report_preferences_.now();
    shown_line_names = report_preferences_.shown_line_names(
      HEAT_MAP_VIEW_ENTRY[0],
    );
    const scale_choices = report_preferences_.heat_scale_choices();
    active_scale = scale_choices.find(
      (choice) => choice.value === view_preferences.heat_scale_value,
    );
    if (!active_scale) window.throw_exception_("str_error_internal");
    sort_mode = view_preferences.heat_sort_mode;
  }

  // Returns a value as a share of the test's total of the counter.
  const share_of_test = (value, counter) =>
    report_ui_.share_of_test(
      value,
      counter.get(profile_model.heatMapTotals.totals),
    );
  // Returns the functions costing a line, refusing a line none costs.
  function line_functions(file_path, line_number) {
    const function_indexes = file_table[file_path].lineFunctions[line_number];
    if (!function_indexes || !function_indexes.length)
      window.throw_exception_("str_error_internal");
    return function_indexes;
  }
  let share_text = report_ui_.percent_text;
  const share_of_test_text = (value, counter) =>
    value ? share_text(share_of_test(value, counter)) : "";

  let human_text = report_ui_.human_text;
  const cell_number = (value) => ({
    text: human_text(value),
  });
  let TICKER_TAPE_HEADING = text("str_ticker_tape_heading_self");
  let HAS_CALL_GRAPH = null;

  let IS_DIFF = null;
  let function_baselines = null,
    file_baselines = null;
  let counter_baseline = () => null;
  let SHARE_LABEL = text("str_column_test_share");
  // Returns a file's, function's or line's share, a diff's of its baseline.
  let counter_share = (value, counter, baseline_cost) =>
    share_of_test(value, counter);
  function report_kind_set(first_model) {
    IS_DIFF = !!first_model.heatMapTotals.diff;
    if (IS_DIFF) {
      share_text = report_ui_.signed_percent_text;
      human_text = report_ui_.signed_human_text;
      TICKER_TAPE_HEADING = text("str_ticker_tape_heading_diff");
      SHARE_LABEL = text("str_column_baseline_share");
      counter_baseline = (cost_vector, counter) => {
        if (!cost_vector) return null;
        const baseline_cost = absolute(counter.get(cost_vector));
        return baseline_cost ? baseline_cost : null;
      };
      counter_share = (value, counter, baseline_cost) =>
        report_ui_.diff_share(value, baseline_cost);
    }
  }
  const baseline = (cost_vector) =>
    counter_baseline(cost_vector, ranking_counter);
  const ranking_share = (value, baseline_cost) =>
    counter_share(value, ranking_counter, baseline_cost);
  const ranking_share_text = (value, baseline_cost) =>
    share_text(ranking_share(value, baseline_cost));
  const line_baseline_vector = (file_path, line_number) => {
    const baseline_table =
      file_table[file_path] && file_table[file_path].baseline;
    return (baseline_table && baseline_table[line_number]) || null;
  };
  const line_baseline = (file_path, line_number) =>
    baseline(line_baseline_vector(file_path, line_number));
  const line_counter_baseline = (file_path, line_number, counter) =>
    counter_baseline(line_baseline_vector(file_path, line_number), counter);
  const function_baseline = (function_index) =>
    baseline(function_baselines[function_index]);
  const file_counter_baseline = (file_path, counter) =>
    counter_baseline(file_baselines[file_path], counter);
  const file_baseline = (file_path) =>
    file_counter_baseline(file_path, ranking_counter);

  // Writes the heat colors of a cell by its share, on the chosen curve.
  const heat_style = (percent) =>
    report_ui_.heat_cell_style(percent, active_scale.curve, IS_DIFF);

  let CALLS_TOTAL = null;
  const call_count_cell = (call_count) =>
    call_count
      ? {
          text: human_text(call_count),
          style: heat_style(report_ui_.share_of_test(call_count, CALLS_TOTAL)),
        }
      : "";

  const hash_for_line = (file_path, line) =>
    report_ui_.address.hash({
      test: shown_test_name,
      view: HEAT_MAP_VIEW_ENTRY[0],
      file: file_path,
      line: line || null,
    });
  const hash_for_function = (name) =>
    report_ui_.address.hash({
      test: shown_test_name,
      view: HEAT_MAP_VIEW_ENTRY[0],
      function: name,
    });
  // Returns the indexes of the functions a line declares, in name order.
  function declared_functions(file_path, line_number) {
    const file_lines = entry_line_index[file_path];
    return (file_lines && file_lines[line_number]) || [];
  }
  // Lists the lines of a file with a cost or a function, in line order.
  function known_lines(file_path) {
    const line_keys = new Set([
      ...Object.keys(file_table[file_path].lines),
      ...Object.keys(entry_line_index[file_path] || {}),
    ]);
    return [...line_keys]
      .map(Number)
      .sort((line_a, line_b) => line_a - line_b);
  }
  // Returns the hash of a line, the function's when the line declares one.
  function hash_for_location(file_path, line_number) {
    const function_indexes = declared_functions(file_path, line_number);
    return function_indexes.length === 1
      ? hash_for_function(function_table[function_indexes[0]].name)
      : hash_for_line(file_path, line_number);
  }
  // Adds cost vectors counter by counter.
  function cost_vectors_add(cost_vectors) {
    const vector_length = Math.max(
      ...cost_vectors.map((cost_vector) => cost_vector.length),
    );
    const summed_vector = [];
    for (let counter_index = 0; counter_index < vector_length; counter_index++)
      summed_vector.push(
        cost_vectors.reduce(
          (running_total, cost_vector) =>
            running_total + vector_at(cost_vector, counter_index),
          0,
        ),
      );
    return summed_vector;
  }
  // Sums the functions a line declares: self, calls and a diff's baselines.
  function declared_costs(function_indexes) {
    const vector_sum = (cost_vector_of) =>
      cost_vectors_add(function_indexes.map(cost_vector_of));
    return {
      self: vector_sum((index) => function_table[index].self),
      calls: vector_sum((index) => function_table[index].calls),
      baseline: IS_DIFF
        ? vector_sum((index) => function_baselines[index])
        : null,
    };
  }
  function function_name(index) {
    return index != null && function_table[index]
      ? function_table[index].name
      : text("str_function_name_unknown");
  }
  // Names the functions costing a line, one for most lines.
  function function_names(function_indexes) {
    return function_indexes
      .map(function_name)
      .join(DATABASE_CELL_SEPARATOR_TEXT);
  }

  function source_text(file_path) {
    const file = file_table[file_path];
    if (!file || file.source === null) return null;
    const sources = window.report_sources_;
    if (!sources || !Object.hasOwn(sources, file_path))
      window.throw_exception_("str_error_internal");
    return sources[file_path];
  }
  // Returns whether the file's source ran, else loads that source and routes.
  function sources_ready(file_path) {
    const script_name = file_table[file_path].source;
    if (script_name === null || source_scripts_loaded.has(script_name))
      return true;
    if (source_scripts_loading.has(script_name)) return false;
    source_scripts_loading.add(script_name);
    const source_script = document.createElement("script");
    source_script.src = report_ui_.address.file_href(
      REPORT_SOURCES_DIR_NAME + "/" + script_name,
    );
    source_script.addEventListener(
      "load",
      window.try_catch_handler_(() => {
        source_scripts_loading.delete(script_name);
        source_scripts_loaded.add(script_name);
        if (source_scripts_loading.size) return;
        rendered_key = "";
        route_render();
      }),
    );
    document.head.append(source_script);
    return false;
  }

  function line_link_cell(file_path, line, text) {
    if (!file_table[file_path] || !line) return { text };
    return { text, href: hash_for_location(file_path, line) };
  }

  const function_is_linkable = (function_index) =>
    function_index != null &&
    function_table[function_index] &&
    function_table[function_index].line &&
    file_table[function_table[function_index].file];
  function function_link_cell(function_index, text) {
    if (!function_is_linkable(function_index)) return { text };
    return {
      text,
      href: hash_for_function(function_table[function_index].name),
    };
  }

  const counter_column = (counter) => ({
    label: counter.key,
    measure: counter_label(counter),
    numeric: true,
  });
  const function_column = (label) => ({
    label,
    name: TABLE_COLUMN_FUNCTION_NAME,
    clip: STYLE_TABLE_FUNCTION_NAME_MAX_CHARS,
  });
  // Returns a column of the places functions are defined or called at.
  const location_column = (label) => ({
    label,
    name: TABLE_COLUMN_LOCATION_NAME,
    clip: STYLE_TABLE_LOCATION_COLUMN_MAX_CHARS,
  });
  // Holds the source table's first column, the tree and the bar sizing it.
  const TREE_COLUMN = {
    label: text("str_heat_map_tree_label"),
    cls: "heat-map-source-table-tree-cell-",
    is_sized_by_bar: true,
  };
  // Asks the top page for the other tree order at a click on the tree's title.
  function title_press(pressed_column) {
    if (pressed_column !== TREE_COLUMN) return;
    const other_choices = report_preferences_.heat_sort_choices.filter(
      (sort_choice) => sort_choice.value !== sort_mode,
    );
    if (other_choices.length !== 1)
      window.throw_exception_("str_error_internal");
    report_ui_.heat_sort_choose_send(other_choices[0].value);
  }
  // Returns the source table's column of a shown line, with its cell class.
  const source_line_column = (line_name, cls) => ({
    ...report_preferences_.line_column(line_name),
    cls,
  });
  // Writes the cell of one selected counter, its share heat colored.
  const secondary_cell = (percent) => ({
    text: percent ? share_text(percent) : "",
    style: heat_style(percent),
  });

  let tree_root = null;
  // Builds the tree of the test's files, each costing its ranking count.
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
        ranking_value(file_table[file_path].self),
        file_baseline(file_path),
        false,
      );
    }
    for (const file_path of profile_model.cold) {
      node_insert(file_path, 0, null, true);
    }
    // Sums each subtree, its baseline null when none of its nodes has one.
    (function subtree_sum(tree_node) {
      let running_total = 0;
      for (const directory_node of tree_node.dirs.values())
        running_total += subtree_sum(directory_node);
      for (const file of tree_node.files) running_total += file.self;
      const baseline_costs = [...tree_node.dirs.values(), ...tree_node.files]
        .map((child_node) => child_node.base)
        .filter((baseline_cost) => baseline_cost !== null);
      tree_node.self = running_total;
      tree_node.base = baseline_costs.length
        ? baseline_costs.reduce(
            (baseline_sum, baseline_cost) => baseline_sum + baseline_cost,
          )
        : null;
      return running_total;
    })(root);
    return root;
  }
  const expanded_directories = new Set(),
    expanded_cold_groups = new Set();
  // Orders tree nodes by heat when that sort is chosen, else by name.
  function node_compare(node_a, node_b) {
    const by_heat =
      sort_mode === "heat" ? absolute(node_b.self) - absolute(node_a.self) : 0;
    return by_heat || node_a.name.localeCompare(node_b.name);
  }
  const caret = (is_expanded) =>
    text(is_expanded ? "str_caret_down" : "str_caret_right");
  const treeitem_attributes = (node_level) => ({
    role: "treeitem",
    "aria-level": node_level,
    tabindex: -1,
  });
  // Writes the indented caret, name and share spans that one tree node holds.
  const tree_node_inner_markup = (caret_text, name_text, share_shown) =>
    render_element(
      "span",
      { class: "heat-map-tree-node-caret-" },
      render_html_escape(caret_text + " "),
    ) +
    render_element(
      "span",
      { class: "heat-map-tree-node-name-" },
      render_html_escape(name_text),
    ) +
    render_element(
      "span",
      { class: "heat-map-tree-node-share-percent-" },
      render_html_escape(share_shown),
    );
  function tree_render() {
    // Writes the heat colors of a node.
    const node_heat_style = (tree_node) =>
      heat_style(ranking_share(tree_node.self, tree_node.base));
    // Writes the share of a node.
    const node_share_text = (tree_node) =>
      ranking_share_text(tree_node.self, tree_node.base);
    function nodes_emit(tree_node, depth) {
      const output_parts = [];
      const indent_text = " ".repeat(
        depth * STYLE_HEAT_MAP_TREE_INDENT_PER_LEVEL_CHARS,
      );
      const directories = [...tree_node.dirs.values()].sort(node_compare);
      for (const directory_node of directories) {
        const is_expanded = expanded_directories.has(directory_node.path);
        const heat_style_attribute = node_heat_style(directory_node);
        output_parts.push(
          render_element(
            "div",
            {
              class:
                "heat-map-tree-node-" + (heat_style_attribute ? " heat-" : ""),
              ...treeitem_attributes(depth + 1),
              "aria-expanded": String(is_expanded),
              "data-dir-": directory_node.path,
              ...(heat_style_attribute ? { style: heat_style_attribute } : {}),
            },
            tree_node_inner_markup(
              indent_text + caret(is_expanded),
              directory_node.name + "/",
              node_share_text(directory_node),
            ),
          ),
        );
        output_parts.push(
          render_element(
            "div",
            {
              class:
                "heat-map-tree-node-child-group-" +
                (is_expanded ? " open-" : ""),
              role: "group",
            },
            nodes_emit(directory_node, depth + 1),
          ),
        );
      }
      const file_list = [...tree_node.files].sort(node_compare);
      const file_row_emit = (file, node_level) => {
        const is_selected = file.path === current_file_path;
        const heat_style_attribute = file.cold ? "" : node_heat_style(file);
        return render_element(
          "div",
          {
            class:
              "heat-map-tree-node- file-" +
              (file.cold ? " cold-" : "") +
              (heat_style_attribute ? " heat-" : "") +
              (is_selected ? " selected-" : ""),
            ...treeitem_attributes(node_level),
            ...(is_selected ? { "aria-selected": "true" } : {}),
            "data-file-": file.path,
            ...(heat_style_attribute ? { style: heat_style_attribute } : {}),
          },
          tree_node_inner_markup(
            indent_text + caret(false),
            file.name,
            node_share_text(file),
          ),
        );
      };
      const zero_cost_files = file_list.filter((file) => file.zero);
      for (const file of file_list)
        if (!file.zero) output_parts.push(file_row_emit(file, depth + 1));
      if (zero_cost_files.length) {
        const is_expanded = expanded_cold_groups.has(tree_node.path);
        output_parts.push(
          render_element(
            "div",
            {
              class: "heat-map-tree-node- more-",
              ...treeitem_attributes(depth + 1),
              "aria-expanded": String(is_expanded),
              "data-more-": tree_node.path,
            },
            tree_node_inner_markup(
              indent_text + caret(is_expanded),
              text("str_no_samples"),
              "",
            ),
          ),
        );
        if (is_expanded) {
          output_parts.push(
            render_element(
              "div",
              {
                class: "heat-map-tree-node-child-group- open-",
                role: "group",
              },
              zero_cost_files
                .map((file) => file_row_emit(file, depth + 2))
                .join(""),
            ),
          );
        }
      }
      return output_parts.join("");
    }
    const tree_had_focus =
      document.hasFocus() && tree_panel.contains(document.activeElement);
    tree_panel.innerHTML = nodes_emit(tree_root, 0);
    tree_tab_stop_place(tree_had_focus);
  }
  // Reads the tree's focus and scroll before the main box draws again.
  function tree_state_read() {
    return {
      had_focus:
        document.hasFocus() && tree_panel.contains(document.activeElement),
      scroll_top: tree_panel.scrollTop,
    };
  }
  // Hangs the tree from the drawn table's first title, its state kept.
  function tree_track_place(tree_state) {
    main_panel
      .querySelector("table.heat-map-source-table- > thead > tr > th")
      .append(tree_track);
    tree_render();
    tree_panel.scrollTop = tree_state.scroll_top;
    if (tree_state.had_focus) tree_tab_stop_place(true);
  }
  let tree_focus_selector = null;
  const TREE_NODE_KEY_ATTRIBUTE_NAMES = [
    "data-dir-",
    "data-file-",
    "data-more-",
  ];
  function tree_node_selector(tree_node) {
    const key_attribute_name = TREE_NODE_KEY_ATTRIBUTE_NAMES.find(
      (attribute_name) => tree_node.hasAttribute(attribute_name),
    );
    const key_value = CSS.escape(tree_node.getAttribute(key_attribute_name));
    return `.heat-map-tree-node-[${key_attribute_name}="${key_value}"]`;
  }
  function tree_visible_nodes() {
    return [...tree_panel.querySelectorAll(".heat-map-tree-node-")].filter(
      (tree_node) =>
        !tree_node.closest(".heat-map-tree-node-child-group-:not(.open-)"),
    );
  }
  function tree_parent(tree_node) {
    const holding_group = tree_node.parentElement.closest(
      ".heat-map-tree-node-child-group-",
    );
    return holding_group ? holding_group.previousElementSibling : null;
  }
  const tree_first_child = (tree_node) =>
    tree_node.nextElementSibling.querySelector(
      ":scope > .heat-map-tree-node-",
    );
  function tree_tab_stop_place(takes_focus) {
    const visible_nodes = tree_visible_nodes();
    const candidate_nodes = [
      takes_focus && tree_focus_selector
        ? tree_panel.querySelector(tree_focus_selector)
        : null,
      tree_panel.querySelector(".heat-map-tree-node-.selected-"),
      visible_nodes[0],
    ];
    const tab_stop = candidate_nodes.find((candidate_node) =>
      visible_nodes.includes(candidate_node),
    );
    if (tab_stop) report_ui_.tab_stop_move(null, tab_stop, takes_focus);
  }
  function tree_key_handler(key_event, key_name, tree_node) {
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
        else next_node = tree_parent(tree_node);
        break;
      case WIDGET_KEY_NAMES.right:
        if (is_closed) tree_node.click();
        else if (is_open) next_node = tree_first_child(tree_node);
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
    window.try_catch_handler_((focus_event) => {
      const tree_node = focus_event.target.closest(".heat-map-tree-node-");
      if (!tree_node) return;
      tree_focus_selector = tree_node_selector(tree_node);
      report_ui_.tab_stop_move(
        tree_panel.querySelector('.heat-map-tree-node-[tabindex="0"]'),
        tree_node,
        false,
      );
    }),
  );
  tree_panel.addEventListener(
    "keydown",
    window.try_catch_handler_((key_event) => {
      const key_name = report_ui_.widget_key.of(key_event);
      const tree_node = key_event.target.closest(".heat-map-tree-node-");
      if (key_name && tree_node)
        tree_key_handler(key_event, key_name, tree_node);
    }),
  );
  tree_panel.addEventListener(
    "click",
    window.try_catch_handler_((click_event) => {
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
        if (tree_node.classList.contains("cold-")) return;
        report_ui_.address.request(
          hash_for_line(tree_node.getAttribute("data-file-")),
        );
      }
    }),
  );
  function group_opening_show(clicked_node) {
    const opened_node = tree_panel.querySelector(
      tree_node_selector(clicked_node),
    );
    const tree_rect = design_rect(tree_panel);
    const group_rect = design_rect(opened_node.nextElementSibling);
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
      ".heat-map-tree-node-.selected-",
    );
    const tree_rect = design_rect(tree_panel);
    const node_rect = design_rect(selected_node);
    const box_bottom_px = tree_rect.top + tree_panel.clientHeight;
    if (node_rect.top < tree_rect.top)
      tree_panel.scrollTop -= tree_rect.top - node_rect.top;
    else if (node_rect.bottom > box_bottom_px)
      tree_panel.scrollTop += node_rect.bottom - box_bottom_px;
  }

  let entry_line_index = null;

  // Renders the hottest lines of a file, or of one function in the file.
  function hottest_lines_render(file_path, function_index) {
    const file = file_table[file_path];
    const tape_lines = Object.keys(file.lines)
      .map(Number)
      .filter(
        (line_number) =>
          function_index === null ||
          line_functions(file_path, line_number).includes(function_index),
      )
      .map((line_number) => {
        const self_cost = ranking_value(file.lines[line_number][0]);
        return {
          line_number,
          self_cost,
          percent: ranking_share(
            self_cost,
            line_baseline(file_path, line_number),
          ),
        };
      })
      .filter(
        (tape_line) =>
          absolute(tape_line.percent) >=
          HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_LEAST_SHARE,
      )
      .sort(
        (tape_line_a, tape_line_b) =>
          absolute(tape_line_b.self_cost) - absolute(tape_line_a.self_cost),
      )
      .slice(0, HEAT_MAP_SOURCE_TICKER_TAPE_ENTRY_MAX_COUNT);
    if (!tape_lines.length) return { markup: "", copy_text: "" };
    let entries_markup = "";
    const entry_texts = tape_lines.map((tape_line, entry_index) => {
      const entry_text = text_fill("str_ticker_tape_entry", {
        line: tape_line.line_number,
        share: share_text(tape_line.percent),
      });
      entries_markup += render_menu_button(
        "link",
        render_html_escape(entry_text),
        {
          tag_name: "a",
          href: hash_for_location(file_path, tape_line.line_number),
          class_names: ["heat-map-source-ticker-tape-entry-"],
          attributes: {
            tabindex: entry_index ? -1 : 0,
            style: heat_style(tape_line.percent),
          },
        },
      );
      return entry_text;
    });
    return {
      markup: render_element(
        "div",
        {
          class: "heat-map-source-ticker-tape-",
          role: "toolbar",
          "aria-label": TICKER_TAPE_HEADING,
        },
        render_element(
          "span",
          { class: "heat-map-source-ticker-tape-label-" },
          render_html_escape(TICKER_TAPE_HEADING),
        ) + entries_markup,
      ),
      copy_text: [TICKER_TAPE_HEADING, ...entry_texts].join("\n"),
    };
  }

  // Builds a control that only calls JS, copy or close.
  const box_control_markup = (action_name, string_id, extra_class_name) =>
    render_menu_button("action", render_html_escape(text(string_id)), {
      tag_name: "span",
      class_names: [
        "heat-map-source-information-box-control-",
        ...(extra_class_name ? [extra_class_name] : []),
      ],
      attributes: { "data-information-box-action-": action_name },
    });
  const box_separator_markup = render_element(
    "span",
    { class: "heat-map-source-information-box-action-bar-separator-" },
    render_html_escape(text("str_information_box_action_bar_separator")),
  );

  // Returns what a box's counter rows read: a line, its functions or a file.
  function box_counter_source(
    file_path,
    line_number,
    line_costs,
    function_costs,
  ) {
    if (line_costs)
      return {
        cost_vector: line_costs[0],
        self_label: text("str_line_self"),
        percent: (value, counter) =>
          counter_share(
            value,
            counter,
            line_counter_baseline(file_path, line_number, counter),
          ),
      };
    if (function_costs)
      return {
        cost_vector: function_costs.self,
        self_label: text("str_column_self"),
        percent: (value, counter) =>
          counter_share(
            value,
            counter,
            counter_baseline(function_costs.baseline, counter),
          ),
      };
    return {
      cost_vector: file_table[file_path].self,
      self_label: text("str_column_self"),
      percent: (value, counter) =>
        counter_share(
          value,
          counter,
          file_counter_baseline(file_path, counter),
        ),
    };
  }
  // Lists the counter table of a box, a line's calls rows after its counters.
  function box_counter_table(
    file_path,
    line_number,
    line_costs,
    function_costs,
  ) {
    const counter_source = box_counter_source(
      file_path,
      line_number,
      line_costs,
      function_costs,
    );
    const columns = [
      { label: text("str_column_counter") },
      { label: SHARE_LABEL, numeric: true },
      { label: text("str_column_count"), numeric: true },
    ];
    const listed_counters = [
      ranking_counter,
      ...counter_list
        .filter(
          (counter) =>
            !counter.derived &&
            counter !== ranking_counter &&
            counter.get(counter_source.cost_vector),
        )
        .sort((counter_a, counter_b) =>
          counter_a.key.localeCompare(counter_b.key),
        ),
    ];
    const rows = listed_counters.map((counter, row_index) => {
      const counter_value = counter.get(counter_source.cost_vector);
      return [
        {
          text:
            (row_index ? "" : counter_source.self_label + " ") +
            counter_label(counter),
        },
        counter_value
          ? share_text(counter_source.percent(counter_value, counter))
          : "",
        counter_value ? cell_number(counter_value) : "",
      ];
    });
    const row_attributes = listed_counters.map((counter) =>
      counter.derived
        ? { class: "heat-map-source-information-box-synthetic-row-" }
        : {},
    );
    const call_cost = line_costs ? ranking_value(line_costs[1]) : 0;
    if (call_cost) {
      rows.push([
        { text: text("str_column_calls") },
        ranking_share_text(call_cost, line_baseline(file_path, line_number)),
        cell_number(call_cost),
      ]);
      rows.push([
        { text: text("str_column_call_count") },
        "",
        call_count_cell(line_costs[2]),
      ]);
    }
    return { columns, rows, row_attributes };
  }
  // Renders a function's part of a box: its totals, hottest lines and callers.
  function function_part_render(file_path, function_index) {
    const function_entry = function_table[function_index];
    const callers = function_entry.callers
      .slice()
      .sort((caller_a, caller_b) => caller_b[4] - caller_a[4]);
    const function_baseline_cost = function_baseline(function_index);
    const function_self_text =
      ranking_share_text(
        ranking_value(function_entry.self),
        function_baseline_cost,
      ) || report_ui_.zero_percent_text();
    const function_total_text =
      ranking_share_text(
        ranking_value(function_entry.self) +
          ranking_value(function_entry.calls),
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
    const hottest_lines = hottest_lines_render(file_path, function_index);
    let markup =
      render_element(
        "div",
        { class: "heat-map-source-information-box-heading-" },
        render_html_escape(heading),
      ) + hottest_lines.markup;
    const text_parts = [heading];
    if (hottest_lines.copy_text) text_parts.push(hottest_lines.copy_text);
    if (callers.length) {
      const columns = [
        { label: text("str_column_call_count"), numeric: true },
        { label: text("str_column_test_share"), numeric: true },
        counter_column(ranking_counter),
        function_column(text("str_column_caller")),
        location_column(text("str_column_called_at")),
      ];
      const rows = callers.map(
        ([caller_index, call_file, call_line, cost_vector, call_count]) => {
          const location_text = report_ui_.location_text(call_file, call_line);
          return [
            call_count_cell(call_count),
            share_of_test_text(ranking_value(cost_vector), ranking_counter),
            cell_number(ranking_value(cost_vector)),
            {
              text: function_name(caller_index),
            },
            line_link_cell(call_file, call_line, location_text),
          ];
        },
      );
      markup += report_ui_.render_table(
        "heat.detail.callers",
        columns,
        rows,
        {},
      );
      text_parts.push(report_ui_.table_markdown(columns, rows));
    } else if (HAS_CALL_GRAPH) {
      const none = text("str_no_caller");
      markup += render_element("div", {}, render_html_escape(none));
      text_parts.push(none);
    }
    return { markup, copy_text: text_parts.join("\n\n") };
  }

  // Renders the information box of a file, or of a line when one is given.
  function information_box_render(file_path, line_number) {
    const file = file_table[file_path];
    const function_indexes = line_number
      ? declared_functions(file_path, line_number)
      : [];
    // A line declaring functions with no cost of its own shows their costs.
    const function_costs =
      function_indexes.length && !file.lines[line_number]
        ? declared_costs(function_indexes)
        : null;
    const line_costs =
      line_number && !function_costs
        ? file.lines[line_number] || [[], [], 0]
        : null;
    const line_function_indexes =
      (line_number && file.lineFunctions[line_number]) || [];
    const counter_table = box_counter_table(
      file_path,
      line_number,
      line_costs,
      function_costs,
    );
    const in_function_note = line_function_indexes.length
      ? text_fill("str_in_function", {
          function: function_names(line_function_indexes),
        })
      : "";
    const in_function_html = line_function_indexes.length
      ? text_fill("str_in_function", {
          function: render_element(
            "span",
            { class: "heat-map-source-information-box-function-name-" },
            render_html_escape(function_names(line_function_indexes)),
          ),
        })
      : "";
    const heading_line =
      report_ui_.location_text(file_path, line_number) + in_function_note;
    const note_texts = [];
    if (!line_number && file.group === CALLGRIND_FILE_DATA_ERROR_CODE)
      note_texts.push(text_fill("str_not_in_repo", { path: file.raw }));
    if (!line_number && source_text(file_path) == null)
      note_texts.push(text("str_source_unavailable"));
    const hottest_lines = !line_number
      ? hottest_lines_render(file_path, null)
      : { markup: "", copy_text: "" };
    // A file's box is part of the page, so no control closes it.
    let markup = line_number
      ? box_control_markup(
          "close",
          "str_information_box_close_symbol",
          "heat-map-source-information-box-close-symbol-",
        )
      : "";
    markup += render_element(
      "div",
      {},
      render_html_escape(report_ui_.location_text(file_path, line_number)) +
        in_function_html,
    );
    markup += report_ui_.render_table(
      "heat.detail.stats",
      counter_table.columns,
      counter_table.rows,
      { row_attributes: counter_table.row_attributes },
    );
    for (const note_text of note_texts) {
      markup += render_element(
        "div",
        { class: "heat-map-source-information-box-note-" },
        render_html_escape(note_text),
      );
    }
    markup += hottest_lines.markup;
    const text_parts = [
      heading_line +
        "\n" +
        report_ui_.table_markdown(counter_table.columns, counter_table.rows),
      ...note_texts,
    ];
    if (hottest_lines.copy_text) text_parts.push(hottest_lines.copy_text);
    const callees = line_number
      ? (file.callees[line_number] || [])
          .slice()
          .sort(
            (callee_a, callee_b) =>
              ranking_value(callee_b[3]) - ranking_value(callee_a[3]),
          )
      : [];
    if (callees.length) {
      const columns = [
        { label: text("str_column_test_share"), numeric: true },
        counter_column(ranking_counter),
        { label: text("str_column_call_count"), numeric: true },
        function_column(text("str_column_callee")),
        location_column(text("str_column_defined_at")),
      ];
      const rows = callees.map(
        ([callee_index, call_file, call_line, cost_vector, call_count]) => {
          const location_text = report_ui_.location_text(call_file, call_line);
          return [
            share_of_test_text(ranking_value(cost_vector), ranking_counter),
            cell_number(ranking_value(cost_vector)),
            call_count_cell(call_count),
            {
              text: function_name(callee_index),
            },
            function_link_cell(callee_index, location_text),
          ];
        },
      );
      const heading = text_fill("str_information_box_callees", {
        counter: counter_label(ranking_counter),
      });
      markup +=
        render_element(
          "div",
          { class: "heat-map-source-information-box-heading-" },
          render_html_escape(heading),
        ) + report_ui_.render_table("heat.detail.callees", columns, rows, {});
      text_parts.push(
        heading + "\n" + report_ui_.table_markdown(columns, rows),
      );
    }
    for (const function_index of function_indexes) {
      const function_part = function_part_render(file_path, function_index);
      markup += function_part.markup;
      text_parts.push(function_part.copy_text);
    }
    // A line in one function links it as "function", in several by name.
    const linked_indexes = function_indexes.length
      ? []
      : line_function_indexes.filter(function_is_linkable);
    const owner_link_markup = linked_indexes
      .map(
        (function_index) =>
          render_menu_button(
            "link",
            render_html_escape(
              line_function_indexes.length === 1
                ? text("str_information_box_function")
                : function_name(function_index),
            ),
            {
              tag_name: "a",
              href: hash_for_function(function_table[function_index].name),
              class_names: ["heat-map-source-information-box-control-"],
            },
          ) + box_separator_markup,
      )
      .join("");
    markup += render_element(
      "div",
      {},
      owner_link_markup +
        box_control_markup("copy", "str_information_box_copy") +
        (line_number
          ? box_separator_markup +
            box_control_markup("close", "str_information_box_close")
          : ""),
    );
    return {
      markup: render_element(
        "div",
        {
          class: "heat-map-source-information-box-",
          "data-information-box-line-": line_number,
        },
        markup,
      ),
      copy_text: text_parts.join("\n\n"),
    };
  }

  // Returns the self share of a file as the information line shows it.
  function information_line_share_text(file_path) {
    const self_cost = ranking_value(file_table[file_path].self);
    return self_cost
      ? share_text(ranking_share(self_cost, file_baseline(file_path)), false)
      : report_ui_.zero_percent_text();
  }
  // Renders the line that stands in for the file box while that box is away.
  function information_line_render(file_path) {
    const link_text = text_fill("str_information_line_link", {
      path: file_path,
      share: information_line_share_text(file_path),
    });
    return render_element(
      "div",
      {
        class: "heat-map-source-information-line- band- empty-",
        "data-information-box-line-": 0,
      },
      render_element(
        "a",
        { href: hash_for_line(file_path) },
        render_html_escape(link_text),
      ) +
        " " +
        box_control_markup("copy", "str_information_box_copy"),
    );
  }
  // Expands each tab to its stop, so a clip counts the columns shown.
  function tabs_expand(line_text) {
    let expanded_text = "";
    for (const character of line_text) {
      if (character !== "\t") expanded_text += character;
      else
        expanded_text += " ".repeat(
          HEAT_MAP_SOURCE_TAB_SIZE_CHARS -
            (expanded_text.length % HEAT_MAP_SOURCE_TAB_SIZE_CHARS),
        );
    }
    return expanded_text;
  }
  const file_box_row = () =>
    main_panel.querySelector("tr.heat-map-source-file-information-row-");
  // Opens the file's box above its first line, in the source column.
  function file_box_place(file_path) {
    const table_element = main_panel.querySelector(
      "table.heat-map-source-table-",
    );
    const title_cells = [...table_element.tHead.rows[0].cells];
    const source_title = table_element.tHead.querySelector(
      `th[data-column-name-="${TABLE_COLUMN_SOURCE_NAME}"]`,
    );
    if (!source_title) window.throw_exception_("str_error_internal");
    table_element.tBodies[0].insertAdjacentHTML(
      "afterbegin",
      render_element(
        "tr",
        { class: "heat-map-source-file-information-row-" },
        title_cells
          .map((title_cell, title_index) =>
            title_cell === source_title
              ? render_element(
                  "td",
                  {},
                  information_box_render(file_path, 0).markup,
                )
              : render_element(
                  "td",
                  title_index ? {} : { class: TREE_COLUMN.cls },
                  "",
                ),
          )
          .join(""),
      ),
    );
  }

  function file_render(file_path) {
    const file = file_table[file_path];
    if (!file) window.throw_exception_("str_error_internal");
    const is_first_view = current_file_path !== file_path,
      kept_scroll_top = is_first_view ? 0 : main_panel.scrollTop;
    current_file_path = file_path;
    let markup = information_line_render(file_path);
    const file_source = source_text(file_path);
    const source_calls_cell = (source_row) => {
      const calls_percent = source_row.share(
        source_row.calls,
        ranking_counter,
      );
      return {
        text: source_row.calls ? share_text(calls_percent) : "",
        style: heat_style(calls_percent),
      };
    };
    // Writes a row's callers or callees, hottest first, each by its share.
    const source_function_list_cell = (call_rows, clip_chars) =>
      report_ui_.function_list_cell(
        call_rows
          .slice()
          .sort(
            (call_a, call_b) =>
              ranking_value(call_b[3]) - ranking_value(call_a[3]),
          )
          .map(([function_index, , , cost_vector]) => ({
            name: function_name(function_index),
            href: function_is_linkable(function_index)
              ? hash_for_function(function_table[function_index].name)
              : "",
            share_text: share_text(
              share_of_test(ranking_value(cost_vector), ranking_counter),
              false,
            ),
          })),
        clip_chars,
      );
    // Makes the part of the callers or the callees line, the calls listed.
    const source_function_list_part = (line_name, call_rows_of) => ({
      column: {
        ...report_preferences_.line_column(line_name),
        clip: STYLE_TABLE_FUNCTION_LIST_COLUMN_MAX_CHARS,
      },
      cell: (source_row, clip_chars) =>
        source_function_list_cell(call_rows_of(source_row), clip_chars),
    });
    // Holds the part of each line of calls, none for a report with no calls.
    const call_parts = HAS_CALL_GRAPH
      ? {
          [COUNTER_LIST_CALLEES_LINE_NAME]: source_function_list_part(
            COUNTER_LIST_CALLEES_LINE_NAME,
            (source_row) => source_row.callees,
          ),
          [COUNTER_LIST_CALLERS_LINE_NAME]: source_function_list_part(
            COUNTER_LIST_CALLERS_LINE_NAME,
            (source_row) => source_row.callers,
          ),
          [COUNTER_LIST_CALLS_LINE_NAME]: {
            column: source_line_column(
              COUNTER_LIST_CALLS_LINE_NAME,
              "heat-map-source-table-calls-cell-",
            ),
            cell: source_calls_cell,
          },
        }
      : {
          [COUNTER_LIST_CALLEES_LINE_NAME]: null,
          [COUNTER_LIST_CALLERS_LINE_NAME]: null,
          [COUNTER_LIST_CALLS_LINE_NAME]: null,
        };
    // Makes the part of a shown counter, the ranking counter's the self costs.
    function source_counter_part(counter_name) {
      if (counter_name === RANKING_COUNTER_NAME)
        return {
          column: source_line_column(
            counter_name,
            "heat-map-source-table-self-cell-",
          ),
          cell: (source_row) => ({
            text: source_row.self_cost
              ? share_text(source_row.self_percent)
              : "",
            style: source_row.heat_style_attribute,
          }),
        };
      const secondary = counter_find(counter_name);
      if (!secondary) window.throw_exception_("str_error_internal");
      return {
        column: source_line_column(
          counter_name,
          "heat-map-source-table-secondary-counter-cell-",
        ),
        cell: (source_row) => {
          if (!source_row.costs) return "";
          const counter_value = secondary.get(source_row.costs[0]);
          return secondary_cell(source_row.share(counter_value, secondary));
        },
      };
    }
    const line_parts = report_preferences_.shown_line_parts(
      HEAT_MAP_VIEW_ENTRY[0],
      source_counter_part,
      call_parts,
    );

    const source_rows = [],
      attrs = [];
    const source_row_emit = (line_number, text) => {
      const line_costs = file.lines[line_number];
      const function_indexes = line_costs
        ? []
        : declared_functions(file_path, line_number);
      // A function line with no cost of its own shows its functions' costs.
      const function_costs = function_indexes.length
        ? declared_costs(function_indexes)
        : null;
      const row_costs = function_costs
        ? [function_costs.self, function_costs.calls]
        : line_costs;
      const row_share = (value, counter) =>
        counter_share(
          value,
          counter,
          function_costs
            ? counter_baseline(function_costs.baseline, counter)
            : line_counter_baseline(file_path, line_number, counter),
        );
      const self_cost = row_costs ? ranking_value(row_costs[0]) : 0,
        calls = row_costs ? ranking_value(row_costs[1]) : 0;
      const self_percent = row_share(self_cost, ranking_counter);
      const heat_style_attribute = heat_style(self_percent);
      const class_names = [
        row_costs && line_number ? "clickable-" : "",
        file.callees[line_number] ? "has-callee-" : "",
      ]
        .filter(Boolean)
        .join(" ");
      attrs.push({
        id: `L${line_number}-`,
        ...(class_names ? { class: class_names } : {}),
        "data-line-number-": line_number,
      });
      source_rows.push({
        calls,
        callees: file.callees[line_number] || [],
        callers: declared_functions(file_path, line_number).flatMap(
          (function_index) => function_table[function_index].callers,
        ),
        costs: row_costs,
        heat_style_attribute,
        line_number,
        self_cost,
        self_percent,
        share: row_share,
        text,
      });
    };
    const source_lines = file_source == null ? [] : file_source.split("\n");
    if (source_lines.length && source_lines[source_lines.length - 1] === "") {
      source_lines.pop();
    }
    for (let line_index = 0; line_index < source_lines.length; line_index++) {
      source_row_emit(line_index + 1, source_lines[line_index]);
    }
    const beyond_end_text =
      file_source == null ? "" : text("str_source_beyond_end");
    for (const line_number of known_lines(file_path)) {
      if (file_source != null && line_number <= source_lines.length) continue;
      source_row_emit(line_number, beyond_end_text);
    }

    const line_number_column = {
      label: text("str_column_line"),
      name: TABLE_COLUMN_LINE_NAME,
      numeric: true,
      cls: "heat-map-source-table-line-number-cell-",
    };
    const source_column = {
      label: text("str_column_source"),
      name: TABLE_COLUMN_SOURCE_NAME,
      clip: HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS,
      cls: "heat-map-source-table-code-cell-",
    };
    // Holds the parts no line of the counters list shows, first until moved.
    const fixed_parts = [
      { column: TREE_COLUMN, cell: () => "" },
      {
        column: line_number_column,
        cell: (source_row) => ({
          text: String(source_row.line_number),
          style: source_row.heat_style_attribute,
        }),
      },
      {
        column: source_column,
        cell: (source_row) => ({
          text: tabs_expand(source_row.text),
          style: source_row.heat_style_attribute,
        }),
      },
    ];
    const column_parts = [...fixed_parts, ...line_parts];
    markup += report_ui_.render_record_table(
      "heat.src",
      column_parts,
      source_rows,
      {
        row_attributes: attrs,
        cls: "heat-map-source-table-",
        counter_list_key: HEAT_MAP_VIEW_ENTRY[0],
        on_redraw: source_redraw,
        on_sort: (column_index) =>
          title_press(column_parts[column_index].column),
        sorted_column_index: null,
      },
    );
    const tree_state = tree_state_read();
    main_panel.innerHTML = render_element(
      "div",
      { class: "heat-map-source-" },
      markup,
    );
    file_box_place(file_path);
    tree_track_place(tree_state);

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

  // Shows the information line once the file box is scrolled under the titles.
  function information_line_refresh() {
    const information_line = main_panel.querySelector(
      ".heat-map-source-information-line-",
    );
    if (!information_line) return;
    const covered_bottom_px =
      design_rect(main_panel).top +
      covered_height(main_panel.querySelector("table.heat-map-source-table-"));
    information_line.classList.toggle(
      "empty-",
      design_rect(file_box_row()).bottom > covered_bottom_px,
    );
  }
  // Shows the file box at the top of the view.
  function file_box_show() {
    main_panel.scrollTop = 0;
    information_line_refresh();
    minimap_sync();
  }
  // Shows an address in a file: the tree node if asked, then the file box.
  function file_address_show(file_path, line, moves_tree) {
    if (moves_tree) {
      tree_reveal(file_path);
      tree_render();
      tree_selected_show();
    }
    if (!line) file_box_show();
  }

  function design_rect(element) {
    const rect = element.getBoundingClientRect();
    return {
      bottom: report_ui_.design_px(rect.bottom),
      height: report_ui_.design_px(rect.height),
      top: report_ui_.design_px(rect.top),
    };
  }

  function row_is_visible(row_element) {
    const row_rect = design_rect(row_element);
    const main_rect = design_rect(main_panel);
    return (
      row_rect.top >=
        main_rect.top + covered_height(row_element.closest("table")) &&
      row_rect.bottom <= main_rect.top + main_panel.clientHeight
    );
  }

  function covered_height(table_element) {
    let height = design_rect(table_element.tHead.rows[0].cells[0]).height;
    for (const band of main_panel.querySelectorAll(".band-")) {
      height += design_rect(band).height;
    }
    return height;
  }

  function row_center(row_element) {
    const cover = covered_height(row_element.closest("table"));
    const row_rect = design_rect(row_element);
    const main_rect = design_rect(main_panel);
    const detail_element = row_element.nextElementSibling;
    const block_bottom_px =
      detail_element &&
      detail_element.classList.contains("heat-map-source-line-detail-row-")
        ? design_rect(detail_element).bottom
        : row_rect.bottom;
    const block_height_px = block_bottom_px - row_rect.top;
    const slack = (main_panel.clientHeight - cover - block_height_px) / 2;
    main_panel.scrollTop += row_rect.top - main_rect.top - cover - slack;
  }

  let scale_factor = 1,
    clone_height_px = 0,
    minimap_build_number = 0;
  function minimap_clear() {
    minimap_build_number++;
    minimap_panel.classList.add("empty-");
    minimap_box.innerHTML = "";
    minimap_viewport.hidden = true;
  }
  // Holds the room of a source taller than the view, filled before the paint.
  function minimap_build() {
    minimap_clear();
    const table_element = main_panel.querySelector(
      "table.heat-map-source-table-",
    );
    const source_top_px = design_rect(
      main_panel.querySelector(".heat-map-source-"),
    ).top;
    if (
      design_rect(table_element).bottom - source_top_px <=
      main_panel.clientHeight
    )
      return;
    minimap_panel.classList.remove("empty-");
    const build_number = minimap_build_number;
    requestAnimationFrame(
      window.try_catch_handler_(() => {
        if (build_number === minimap_build_number) minimap_fill(table_element);
      }),
    );
  }
  function minimap_fill(table_element) {
    const table_body = table_element.tBodies[0];
    let clone_rows_markup = "";
    for (const row of table_body.rows) {
      if (row.classList.contains("heat-map-source-line-detail-row-")) continue;
      const code = row.querySelector("td.heat-map-source-table-code-cell-");
      if (!code) continue;
      clone_rows_markup += render_element(
        "tr",
        row.className ? { class: row.className } : {},
        code.outerHTML,
      );
    }
    minimap_box.innerHTML = render_element(
      "table",
      { class: "heat-map-source-table-" },
      render_element("tbody", {}, clone_rows_markup),
    );
    const clone_table = minimap_box.firstElementChild;
    minimap_viewport.hidden = false;
    clone_height_px = clone_table.offsetHeight;
    minimap_layout();
  }

  function minimap_layout() {
    if (minimap_viewport.hidden) return;
    const band_width_px = minimap_panel.clientWidth,
      band_height_px = main_panel.clientHeight;
    scale_factor = Math.min(
      1,
      band_width_px /
        (HEAT_MAP_SOURCE_VIEW_WIDTH_CHARS *
          report_ui_.design_character_width_px),
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
    const main = design_rect(main_panel);
    const body_bottom_px = design_rect(table_body).bottom;
    // The rows the minimap clones start below the file box's row.
    const code_top_px = design_rect(file_box_row()).bottom;
    const clone_body = {
      height: body_bottom_px - code_top_px,
      top: code_top_px,
    };
    const detail_element = table_body.querySelector(
      "tr.heat-map-source-line-detail-row-",
    );
    const detail = detail_element && design_rect(detail_element);
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
      head: design_rect(table_element.tHead.rows[0].cells[0]).bottom,
    };
  }
  function minimap_sync() {
    if (minimap_viewport.hidden) return;
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
    window.try_catch_handler_(minimap_sync),
  );
  main_panel.addEventListener(
    "scroll",
    window.try_catch_handler_(information_line_refresh),
  );
  // Centres the view on a pressed row outside the box, then drags the box.
  minimap_panel.addEventListener(
    "pointerdown",
    window.try_catch_handler_((press_event) => {
      if (press_event.button || minimap_viewport.hidden) return;
      press_event.preventDefault();
      const scaled_height_px = clone_height_px * scale_factor;
      if (!minimap_viewport.contains(press_event.target)) {
        const geometry = geometry_measure();
        const pressed_px =
          report_ui_.design_px(press_event.clientY) -
          design_rect(minimap_panel).top;
        scroll_to_row(
          (pressed_px / scaled_height_px) * geometry.rows -
            (main_panel.clientHeight - geometry.cover) / 2,
        );
        minimap_sync();
      }
      const start_top_px = minimap_viewport.offsetTop;
      minimap_viewport.classList.add("drag-");
      minimap_panel.setPointerCapture(press_event.pointerId);
      const pointer_move = window.try_catch_handler_((move_event) => {
        if (move_event.pointerId !== press_event.pointerId) return;
        scroll_to_row(
          ((start_top_px +
            report_ui_.design_px(move_event.clientY - press_event.clientY)) /
            scaled_height_px) *
            geometry_measure().rows,
        );
      });
      const pointer_release = window.try_catch_handler_((release_event) => {
        if (release_event.pointerId !== press_event.pointerId) return;
        minimap_viewport.classList.remove("drag-");
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

  // Shows a line, its box open below it.
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
  // Opens a line's box below its row, the tree's column left clear.
  function detail_open(file_path, line_number, row) {
    row.insertAdjacentHTML(
      "afterend",
      render_element(
        "tr",
        { class: "heat-map-source-line-detail-row-" },
        render_element("td", { class: TREE_COLUMN.cls }, "") +
          render_element(
            "td",
            { colspan: row.cells.length - 1 },
            information_box_render(file_path, line_number).markup,
          ),
      ),
    );
    const detail_row = row.nextElementSibling;
    report_ui_.layout_activate(detail_row);
  }
  // Copies or closes the information box that holds a control.
  function information_box_control_handler(box_control) {
    const box_line_number = +box_control
      .closest("[data-information-box-line-]")
      .getAttribute("data-information-box-line-");
    if (box_control.getAttribute("data-information-box-action-") === "copy")
      return navigator.clipboard.writeText(
        information_box_render(current_file_path, box_line_number).copy_text,
      );
    detail_close(box_control.closest("tr.heat-map-source-line-detail-row-"));
  }

  main_panel.addEventListener(
    "click",
    window.try_catch_handler_((click_event) => {
      const box_control = click_event.target.closest(
        "[data-information-box-action-]",
      );
      if (box_control) return information_box_control_handler(box_control);
      if (click_event.target.closest("a")) return;
      const row = click_event.target.closest("tr.clickable-");
      if (row && current_file_path) {
        const line_number = +row.getAttribute("data-line-number-");
        if (line_number === detail_line())
          detail_close(row.nextElementSibling);
        else
          report_ui_.address.request(
            hash_for_location(current_file_path, line_number),
          );
      }
    }),
  );
  function ticker_tape_key_handler(key_event, key_name, ticker_tape_entry) {
    if (report_ui_.widget_key.activates(key_name)) {
      key_event.preventDefault();
      if (!key_event.repeat) ticker_tape_entry.click();
      return true;
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
        return false;
    }
    key_event.preventDefault();
    const next_entry = tape_entries[next_index];
    if (next_entry)
      report_ui_.tab_stop_move(ticker_tape_entry, next_entry, true);
    return true;
  }
  main_panel.addEventListener(
    "focusin",
    window.try_catch_handler_((focus_event) => {
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
    window.try_catch_handler_((key_event) => {
      const key_name = report_ui_.widget_key.of(key_event);
      if (!key_name) return;
      const ticker_tape_entry = key_event.target.closest(
        ".heat-map-source-ticker-tape-entry-",
      );
      if (
        ticker_tape_entry &&
        ticker_tape_key_handler(key_event, key_name, ticker_tape_entry)
      )
        return;
      const box_control = key_event.target.closest(
        "[data-information-box-action-]",
      );
      if (box_control && report_ui_.widget_key.activates(key_name)) {
        key_event.preventDefault();
        if (!key_event.repeat)
          return information_box_control_handler(box_control);
        return;
      }
      if (key_name !== WIDGET_KEY_NAMES.close) return;
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

  const source_scripts_loaded = new Set();
  const source_scripts_loading = new Set();
  let rendered_line = 0;
  let rendered_key = "";
  let routed_hash = null;
  let is_routing = false;
  let load_render_log = null;
  // Builds the tree by the ranking counter, opening the hottest folders.
  function ranking_tree_build() {
    tree_root = tree_build();
    for (const directory_node of tree_root.dirs.values()) {
      if (
        share_of_test(absolute(directory_node.self), ranking_counter) / 100 >
        HEAT_MAP_TREE_AUTO_EXPAND_ABOVE_SHARE
      ) {
        expanded_directories.add(directory_node.path);
      }
    }
  }
  // Renders again what relayed preferences change, the first relay routing.
  function preferences_apply() {
    if (!is_routing) {
      is_routing = true;
      window.addEventListener(
        "hashchange",
        window.try_catch_handler_(route_render),
      );
      route_render();
      return;
    }
    if (profile_model === null) return;
    const tree_sort_mode = sort_mode,
      kept_key = rendered_key;
    preferences_handler();
    route_render();
    if (rendered_key === kept_key && sort_mode !== tree_sort_mode)
      tree_render();
  }
  // Takes a relayed message, rendering again when its preferences changed.
  function relay_handler(message_data) {
    if (report_preferences_.relay_handler(message_data)) preferences_apply();
  }
  // Writes the note of a file or function the test recorded no samples for.
  const no_samples_note_markup = (unsampled_name) =>
    render_html_escape(
      text_fill("str_no_samples_in_test", { name: unsampled_name }),
    );
  // Shows a note in place of a file's source, the tree kept in its column.
  function unavailable_note_render(note_markup) {
    current_file_path = null;
    const tree_state = tree_state_read();
    const note_columns = [TREE_COLUMN, { label: text("str_column_source") }];
    main_panel.innerHTML = report_ui_.render_table(
      "heat.note",
      note_columns,
      [["", { html: note_markup }]],
      {
        cls: "heat-map-source-table-",
        on_sort: (column_index) => title_press(note_columns[column_index]),
        sorted_column_index: null,
      },
    );
    main_panel.scrollTop = 0;
    tree_track_place(tree_state);
    report_ui_.layout_activate(main_panel);
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
    // The tree in the main box keeps its own focus through a draw.
    const main_had_focus =
      document.hasFocus() &&
      main_panel.contains(document.activeElement) &&
      !tree_panel.contains(document.activeElement);
    const page_address = report_ui_.address.of_hash(location.hash);
    if (page_address.view !== HEAT_MAP_VIEW_ENTRY[0])
      window.throw_exception_("str_error_internal");
    if (profile_model === null || page_address.test !== shown_test_name) {
      model_load(page_address.test);
      return;
    }
    const is_new_address = location.hash !== routed_hash,
      is_detail_closed = !is_new_address && !detail_line(),
      previous_file_path = current_file_path;
    let file = page_address.file,
      line = page_address.line === null ? 0 : page_address.line,
      fn = page_address.function;
    let note_markup = "";
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
      } else if (source_database.functions.includes(fn)) {
        note_markup = no_samples_note_markup(fn);
      } else {
        window.throw_exception_("str_error_hash_function_unknown", fn);
      }
    } else if (!file_table[file]) {
      if (!source_database.files.includes(file)) {
        window.throw_exception_("str_error_hash_file_unknown", file);
      }
      note_markup = no_samples_note_markup(file);
    }
    if (!note_markup && !sources_ready(file)) return;
    routed_hash = location.hash;
    if (note_markup) {
      rendered_key = "";
      unavailable_note_render(note_markup);
      rendered_line = line;
      main_focus_restore(main_had_focus);
      load_render_finish();
      return;
    }

    const key = [file, active_scale.value, ...shown_line_names].join("\n");
    if (key !== rendered_key) {
      rendered_key = key;
      file_render(file);
    }
    if (line) line = line_clamp(line);
    if (!is_detail_closed) detail_set(line);
    if (is_new_address)
      file_address_show(file, line, file !== previous_file_path);
    rendered_line = line;
    main_focus_restore(main_had_focus);
    load_render_finish();
  }
  // Draws the source again for a new clip or column place, its open line kept.
  function source_redraw() {
    rendered_key = "";
    route_render();
  }
  // Logs the view's load render once the first route has drawn.
  function load_render_finish() {
    if (load_render_log === null) return;
    load_render_log();
    load_render_log = null;
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
      window.try_catch_handler_(() => {
        window.throw_exception_("str_error_internal");
      }),
    );
    model_script.addEventListener(
      "load",
      window.try_catch_handler_(() => {
        const loaded_models = window[HEAT_MAP_MODEL_GLOBAL_NAME];
        if (!loaded_models || !loaded_models[test_name])
          window.throw_exception_("str_error_internal");
        route_render();
      }),
    );
    document.head.append(model_script);
  }
  function model_switch(test_name, test_model) {
    if (IS_DIFF === null) report_kind_set(test_model);
    shown_test_name = test_name;
    profile_model = test_model;
    file_table = test_model.files;
    function_table = test_model.functions;
    function_baselines = test_model.functionBaseline || [];
    file_baselines = test_model.fileBaseline || {};
    HAS_CALL_GRAPH = function_table.some(
      (function_entry) => function_entry.callers.length > 0,
    );
    const per_function_calls = function_table.map((function_entry) =>
      function_entry.callers.reduce(
        (running_total, caller) => running_total + caller[4],
        0,
      ),
    );
    CALLS_TOTAL = per_function_calls.reduce(
      (running_total, call_count) => running_total + call_count,
      0,
    );
    entry_line_index = {};
    function_table.forEach((function_entry, index) => {
      if (!function_entry.line) return;
      entry_line_index[function_entry.file] =
        entry_line_index[function_entry.file] || {};
      const file_lines = entry_line_index[function_entry.file];
      file_lines[function_entry.line] = file_lines[function_entry.line] || [];
      file_lines[function_entry.line].push(index);
    });
    counters_build();
    expanded_directories.clear();
    expanded_cold_groups.clear();
    current_file_path = null;
    rendered_key = "";
    preferences_handler();
    ranking_tree_build();
  }
  function address_recenter() {
    if (!current_file_path) {
      rendered_key = "";
      routed_hash = null;
      route_render();
      return;
    }
    file_address_show(current_file_path, rendered_line, true);
    if (!rendered_line) return;
    detail_set(rendered_line);
    row_center(document.getElementById("L" + rendered_line + "-"));
  }

  report_ui_.view_activate({
    forwards_input: true,
    load_render_defer: (render_log) => {
      load_render_log = render_log;
    },
    recenter: address_recenter,
    relay_handler,
  });

  report_ui_.resize_settle_register(() => {
    minimap_layout();
    information_line_refresh();
  });
})();
