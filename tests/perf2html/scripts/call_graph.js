// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const CALL_GRAPH_BRANCH_FIRST_TEXT = settings_(
    "CALL_GRAPH_BRANCH_FIRST_TEXT",
  );
  const CALL_GRAPH_BRANCH_LAST_TEXT = settings_("CALL_GRAPH_BRANCH_LAST_TEXT");
  const CALL_GRAPH_BRANCH_MIDDLE_TEXT = settings_(
    "CALL_GRAPH_BRANCH_MIDDLE_TEXT",
  );
  const CALL_GRAPH_BRANCH_ONLY_TEXT = settings_("CALL_GRAPH_BRANCH_ONLY_TEXT");
  const CALL_GRAPH_BRANCH_PASS_TEXT = settings_("CALL_GRAPH_BRANCH_PASS_TEXT");
  const CALL_GRAPH_CLOSED_TEXT = settings_("CALL_GRAPH_CLOSED_TEXT");
  const CALL_GRAPH_LINE_TEXT = settings_("CALL_GRAPH_LINE_TEXT");
  const CALL_GRAPH_OPEN_LEAST_CUMULATIVE_PERCENT = settings_(
    "CALL_GRAPH_OPEN_LEAST_CUMULATIVE_PERCENT",
  );
  const CALL_GRAPH_PAD_TEXT = settings_("CALL_GRAPH_PAD_TEXT");
  const CALL_GRAPH_REVEAL_CLEARANCE_CHARS = settings_(
    "CALL_GRAPH_REVEAL_CLEARANCE_CHARS",
  );
  const CALL_GRAPH_REVEAL_CLEARANCE_LINES = settings_(
    "CALL_GRAPH_REVEAL_CLEARANCE_LINES",
  );
  const NUMBER_FRACTION_DIGITS = settings_("NUMBER_FRACTION_DIGITS");
  const NUMBER_MULTIPLE_SUFFIX_TEXT = settings_("NUMBER_MULTIPLE_SUFFIX_TEXT");

  const render_element = window.render_element_;
  const render_html_escape = window.render_html_escape_;
  // Holds the width of a multiple at full precision, zero's.
  const MULTIPLE_WIDTH_CHARS = window.report_ui_.fixed_text(
    0,
    NUMBER_FRACTION_DIGITS,
  ).length;
  // Writes a share cell, the share on its heat color, empty for no share.
  function share_cell_markup(share_percent) {
    const cell_attributes = { class: "call-graph-share-" };
    if (!share_percent) return render_element("td", cell_attributes, "");
    return render_element(
      "td",
      {
        ...cell_attributes,
        style: window.report_ui_.heat_cell_style(
          share_percent,
          heat_curve_name,
          false,
        ),
      },
      render_html_escape(window.report_ui_.percent_text(share_percent)),
    );
  }
  // Writes a group's cells: branch, multiple, share and symbol.
  function group_markup(
    branch_cell_markup,
    multiple_cell_markup,
    share_percent,
    symbol_cell_markup,
  ) {
    return (
      render_element("td", {}, branch_cell_markup) +
      render_element(
        "td",
        { class: "call-graph-multiple-" },
        multiple_cell_markup,
      ) +
      share_cell_markup(share_percent) +
      render_element("td", { class: "call-graph-symbol-" }, symbol_cell_markup)
    );
  }
  // Marks a layout group a branch passes through, holding no node.
  const PASS_PLACE = {};
  const page_scroll_box = document.getElementById("call-graph-page-");
  const page_heading = page_scroll_box.querySelector(".page-heading-");
  const shown_test_name = window.report_ui_.address.of_hash(
    location.hash,
  ).test;
  const graph_table = document.getElementById("call-graph-table-");
  const call_graph_model = JSON.parse(graph_table.getAttribute("data-model-"));
  const graph_body = window.render_element_of_(
    render_element("tbody", {}, ""),
  );

  // Reads one function's row, its calls summed below.
  function function_record_read(function_row) {
    return {
      name: function_row[0],
      self_cost: function_row[1],
      invocation_count: 0,
      callee_edges: [],
    };
  }
  // Reads one call edge from its row.
  function call_edge_read(edge_row) {
    return {
      caller_index: edge_row[0],
      callee_index: edge_row[1],
      calls: edge_row[2],
      call_line: edge_row[3],
      inclusive_cost: edge_row[4],
    };
  }
  // Reads one root from its row.
  function call_root_read(root_row) {
    return { function_index: root_row[0], calls: root_row[1] };
  }
  const function_records = call_graph_model.functions.map(
    function_record_read,
  );
  const call_roots = call_graph_model.roots.map(call_root_read);
  const test_total = call_graph_model.test_total;
  for (const call_root of call_roots)
    function_records[call_root.function_index].invocation_count +=
      call_root.calls;
  for (const call_edge of call_graph_model.edges.map(call_edge_read)) {
    function_records[call_edge.caller_index].callee_edges.push(call_edge);
    function_records[call_edge.callee_index].invocation_count +=
      call_edge.calls;
  }

  // Returns a function's self cost as a percent of the test's total cost.
  function self_share_of_test(function_record) {
    return window.report_ui_.share_of_test(
      function_record.self_cost,
      test_total,
    );
  }
  // Returns an edge's calls per invocation of its caller, null for none.
  function edge_multiple(call_edge) {
    const caller_count =
      function_records[call_edge.caller_index].invocation_count;
    return caller_count ? call_edge.calls / caller_count : null;
  }
  // Orders two edges by their callees' names.
  function name_order(edge_a, edge_b) {
    return function_records[edge_a.callee_index].name.localeCompare(
      function_records[edge_b.callee_index].name,
    );
  }
  // Orders a caller's edges by their calls' cumulative cost, line, then name.
  function cumulative_order(edge_a, edge_b) {
    return (
      edge_b.inclusive_cost - edge_a.inclusive_cost ||
      edge_a.call_line - edge_b.call_line ||
      name_order(edge_a, edge_b)
    );
  }
  // Orders a caller's edges by their callees' self cost, then cumulative.
  function heat_order(edge_a, edge_b) {
    return (
      function_records[edge_b.callee_index].self_cost -
        function_records[edge_a.callee_index].self_cost ||
      cumulative_order(edge_a, edge_b)
    );
  }
  // Holds the edge order of each call graph sort, by its value.
  const SORT_ORDERS = {
    cumulative: cumulative_order,
    heat: heat_order,
    name: name_order,
  };
  // Orders a node's shown edges by the chosen sort.
  function edges_sort(callee_edges) {
    if (!Object.hasOwn(SORT_ORDERS, sort_mode))
      window.throw_exception_("str_error_internal");
    return callee_edges.toSorted(SORT_ORDERS[sort_mode]);
  }

  // Returns the key of a node's path in the open set.
  function path_key(node_path) {
    return JSON.stringify(node_path);
  }
  // Returns the record of the function a node's path ends at.
  function path_function(node_path) {
    return function_records[node_path.at(-1)];
  }
  // Lists the edges a node's path shows, each callee already on it skipped.
  function shown_callee_edges(node_path) {
    return path_function(node_path).callee_edges.filter(
      (call_edge) => !node_path.includes(call_edge.callee_index),
    );
  }
  // Returns whether a call's cumulative share of the test opens its caller.
  function edge_opens_caller(call_edge) {
    return (
      window.report_ui_.share_of_test(call_edge.inclusive_cost, test_total) >=
      CALL_GRAPH_OPEN_LEAST_CUMULATIVE_PERCENT
    );
  }
  // Returns a fresh open set: each shown node with a child of enough cost.
  function call_graph_open_set() {
    const open_set = new Set();
    // Opens a node with a shown child of enough cost, then each child.
    function node_open(node_path) {
      const shown_edges = shown_callee_edges(node_path);
      if (!shown_edges.some(edge_opens_caller)) return;
      open_set.add(path_key(node_path));
      for (const call_edge of shown_edges)
        node_open([...node_path, call_edge.callee_index]);
    }
    for (const call_root of call_roots) node_open([call_root.function_index]);
    return open_set;
  }
  let button_graph_nodes = new WeakMap(),
    cell_symbol_buttons = new WeakMap(),
    heat_curve_name = null,
    node_places = new Map(),
    open_path_keys = call_graph_open_set(),
    rendered_preferences_text = null,
    selected_function_name = null,
    sort_mode = null;

  // Makes a root's node, which draws no branch, share or multiple.
  function root_node(call_root) {
    return {
      node_path: [call_root.function_index],
      call_edge: null,
      branch_text: "",
    };
  }
  // Lists a node's shown children by the chosen sort, each with its branch.
  function node_children(graph_node) {
    const shown_edges = edges_sort(shown_callee_edges(graph_node.node_path));
    const last_index = shown_edges.length - 1;
    return shown_edges.map((call_edge, child_index) => ({
      node_path: [...graph_node.node_path, call_edge.callee_index],
      call_edge,
      branch_text:
        child_index === 0
          ? last_index === 0
            ? CALL_GRAPH_BRANCH_ONLY_TEXT
            : CALL_GRAPH_BRANCH_FIRST_TEXT
          : child_index < last_index
            ? CALL_GRAPH_BRANCH_MIDDLE_TEXT
            : CALL_GRAPH_BRANCH_LAST_TEXT,
    }));
  }
  // Returns whether a node is open.
  function node_is_open(graph_node) {
    return open_path_keys.has(path_key(graph_node.node_path));
  }
  // Returns whether a node is closed and has shown children to open.
  function node_is_closed(graph_node) {
    return (
      !node_is_open(graph_node) &&
      shown_callee_edges(graph_node.node_path).length > 0
    );
  }

  // Places every drawn node in a row and a group, one group per depth.
  function graph_layout() {
    const layout_rows = [];
    const next_free_rows = [];
    // Places a node, then its children when open, and returns its row.
    function node_place(graph_node, least_row) {
      const group_index = graph_node.node_path.length - 1;
      const is_open = node_is_open(graph_node);
      // An open node sits below every branch right of it, any other beside.
      const node_row = Math.max(
        least_row,
        ...next_free_rows.slice(
          group_index,
          is_open ? next_free_rows.length : group_index + 1,
        ),
      );
      (layout_rows[node_row] ??= [])[group_index] = graph_node;
      next_free_rows[group_index] = node_row + 1;
      // A row keeps a group right of a closed node, its mark's place if empty.
      if (node_is_closed(graph_node))
        layout_rows[node_row].length = Math.max(
          layout_rows[node_row].length,
          group_index + 2,
        );
      if (!is_open) return node_row;
      const child_rows = node_children(graph_node).map((child_node) =>
        node_place(child_node, node_row),
      );
      for (
        let pass_row = child_rows[0] + 1;
        pass_row < child_rows.at(-1);
        pass_row++
      )
        if (!child_rows.includes(pass_row))
          layout_rows[pass_row][group_index + 1] = PASS_PLACE;
      return node_row;
    }
    for (const call_root of call_roots) node_place(root_node(call_root), 0);
    // Every row holds every group, so each column runs the table's height.
    const group_count = Math.max(
      ...layout_rows.map((layout_row) => layout_row.length),
    );
    for (const layout_row of layout_rows) layout_row.length = group_count;
    return layout_rows;
  }

  // Returns whether a row's closed node has its mark in the empty place right.
  function mark_fits_right(layout_row, group_index) {
    const layout_place = layout_row[group_index];
    return (
      layout_place !== undefined &&
      layout_place !== PASS_PLACE &&
      node_is_closed(layout_place) &&
      layout_row[group_index + 1] === undefined
    );
  }
  // Returns a place's branch text: a node's, a passing branch's, or none.
  function place_branch_text(layout_place) {
    if (layout_place === undefined) return "";
    if (layout_place === PASS_PLACE) return CALL_GRAPH_BRANCH_PASS_TEXT;
    return layout_place.branch_text;
  }
  // Returns a node's self share of the test, null for a root.
  function node_share_percent(graph_node) {
    if (graph_node.call_edge === null) return null;
    return self_share_of_test(path_function(graph_node.node_path));
  }
  // Returns a placed node's name and bar end texts, and whether bars follow.
  function symbol_parts(layout_row, group_index) {
    const graph_node = layout_row[group_index];
    const name_text =
      CALL_GRAPH_PAD_TEXT +
      path_function(graph_node.node_path).name +
      CALL_GRAPH_PAD_TEXT;
    if (node_is_open(graph_node) || mark_fits_right(layout_row, group_index))
      return { name_text, has_bars: true, end_text: "" };
    if (node_is_closed(graph_node))
      return {
        name_text,
        has_bars: true,
        end_text: CALL_GRAPH_CLOSED_TEXT + CALL_GRAPH_PAD_TEXT,
      };
    return { name_text, has_bars: false, end_text: "" };
  }
  // Returns the fewest characters a placed node's symbol takes, one bar long.
  function symbol_least_width(layout_row, group_index) {
    const symbol_part = symbol_parts(layout_row, group_index);
    if (!symbol_part.has_bars) return symbol_part.name_text.length;
    return (
      symbol_part.name_text.length +
      CALL_GRAPH_LINE_TEXT.length +
      symbol_part.end_text.length
    );
  }
  // Lists each group's symbol column width, its widest symbol's characters.
  function symbol_column_widths(layout_rows) {
    const column_widths = new Array(layout_rows[0].length).fill(0);
    for (const layout_row of layout_rows)
      layout_row.forEach((layout_place, group_index) => {
        if (layout_place === undefined || layout_place === PASS_PLACE) return;
        column_widths[group_index] = Math.max(
          column_widths[group_index],
          symbol_least_width(layout_row, group_index),
        );
      });
    return column_widths;
  }
  // Writes a node's symbol, a button if it toggles, its bars to the width.
  function symbol_markup(layout_row, group_index, symbol_width) {
    const graph_node = layout_row[group_index];
    const symbol_part = symbol_parts(layout_row, group_index);
    const name_markup = render_html_escape(symbol_part.name_text);
    const shown_name_markup =
      shown_callee_edges(graph_node.node_path).length > 0
        ? window.render_menu_button_("action", name_markup, {
            tag_name: "span",
          })
        : name_markup;
    if (!symbol_part.has_bars) return shown_name_markup;
    const bar_width =
      symbol_width -
      symbol_part.name_text.length -
      symbol_part.end_text.length;
    return (
      shown_name_markup +
      render_html_escape(
        CALL_GRAPH_LINE_TEXT.repeat(bar_width) + symbol_part.end_text,
      )
    );
  }
  // Returns a multiple with the most fraction digits its width holds.
  function multiple_text(calls_multiple) {
    let digit_count = NUMBER_FRACTION_DIGITS;
    let fitted_text = window.report_ui_.fixed_text(
      calls_multiple,
      digit_count,
    );
    while (digit_count > 0 && fitted_text.length > MULTIPLE_WIDTH_CHARS) {
      digit_count--;
      fitted_text = window.report_ui_.fixed_text(calls_multiple, digit_count);
    }
    return fitted_text;
  }
  // Writes a node's calls multiple and its suffix between pads, if it has one.
  function multiple_markup(graph_node) {
    if (graph_node.call_edge === null) return "";
    const calls_multiple = edge_multiple(graph_node.call_edge);
    if (calls_multiple === null) return "";
    return render_html_escape(
      CALL_GRAPH_PAD_TEXT +
        multiple_text(calls_multiple) +
        NUMBER_MULTIPLE_SUFFIX_TEXT +
        CALL_GRAPH_PAD_TEXT,
    );
  }
  // Writes a layout row's groups: a node's, a passing branch's, or empty.
  function layout_row_markup(layout_row, symbol_widths) {
    return Array.from(layout_row, (layout_place, group_index) => {
      // A closed node's mark takes the empty branch cell right of it.
      const branch_cell_markup = render_html_escape(
        mark_fits_right(layout_row, group_index - 1)
          ? CALL_GRAPH_CLOSED_TEXT
          : place_branch_text(layout_place),
      );
      if (layout_place === undefined || layout_place === PASS_PLACE)
        return group_markup(branch_cell_markup, "", null, "");
      return group_markup(
        branch_cell_markup,
        multiple_markup(layout_place),
        node_share_percent(layout_place),
        symbol_markup(layout_row, group_index, symbol_widths[group_index]),
      );
    }).join("");
  }
  // Draws every layout row, keeping each placed node's cells and button.
  function graph_render() {
    button_graph_nodes = new WeakMap();
    cell_symbol_buttons = new WeakMap();
    node_places = new Map();
    const layout_rows = graph_layout();
    const symbol_widths = symbol_column_widths(layout_rows);
    const graph_rows = layout_rows.map((layout_row) => {
      const graph_row = window.render_element_of_(
        render_element("tr", {}, layout_row_markup(layout_row, symbol_widths)),
      );
      const row_cells = [...graph_row.cells];
      const group_size = row_cells.length / layout_row.length;
      layout_row.forEach((layout_place, group_index) => {
        if (layout_place === PASS_PLACE) return;
        // A node's cells end with the next group's branch cell if its mark's.
        const node_cells = row_cells.slice(
          group_index * group_size,
          (group_index + 1) * group_size +
            (mark_fits_right(layout_row, group_index) ? 1 : 0),
        );
        const symbol_button = node_cells
          .map((node_cell) => node_cell.querySelector(".menu-button-"))
          .find((found_button) => found_button);
        node_places.set(path_key(layout_place.node_path), {
          node_cells,
          symbol_button,
        });
        if (!symbol_button) return;
        button_graph_nodes.set(symbol_button, layout_place);
        // Each of a symbol's cells takes the click its button takes.
        for (const node_cell of node_cells) {
          node_cell.classList.add("clickable-");
          cell_symbol_buttons.set(node_cell, symbol_button);
        }
      });
      return graph_row;
    });
    graph_body.replaceChildren(...graph_rows);
    window.report_ui_.layout_activate();
  }

  // Returns the least scroll showing a span with clearance, its start first.
  function reveal_travel(span_start, span_end, window_size, clearance_size) {
    const start_travel = span_start - clearance_size;
    if (start_travel < 0) return start_travel;
    return Math.min(
      start_travel,
      Math.max(0, span_end + clearance_size - window_size),
    );
  }
  // Scrolls the page the least that shows the cells, with the clearance.
  function cells_reveal(span_cells) {
    const design_px = window.report_ui_.design_px;
    const box_rect = page_scroll_box.getBoundingClientRect();
    const table_style = getComputedStyle(graph_table);
    const cell_rects = span_cells.map((span_cell) =>
      span_cell.getBoundingClientRect(),
    );
    const span_edge = (pick_edge, edge_name) =>
      pick_edge(...cell_rects.map((cell_rect) => cell_rect[edge_name]));
    page_scroll_box.scrollTop += reveal_travel(
      design_px(span_edge(Math.min, "top") - box_rect.top),
      design_px(span_edge(Math.max, "bottom") - box_rect.top),
      page_scroll_box.clientHeight,
      parseFloat(table_style.scrollMarginTop),
    );
    page_scroll_box.scrollLeft += reveal_travel(
      design_px(span_edge(Math.min, "left") - box_rect.left),
      design_px(span_edge(Math.max, "right") - box_rect.left),
      page_scroll_box.clientWidth,
      parseFloat(table_style.scrollMarginLeft),
    );
  }
  // Shows the selected function after the heading's copy and download.
  function heading_tail_show() {
    const selected_entries =
      selected_function_name === null
        ? []
        : [
            window.report_ui_.strip.entry_make(
              "selected_function",
              "link",
              selected_function_name,
              {
                href: window.report_ui_.address.function_hash(
                  shown_test_name,
                  selected_function_name,
                ),
              },
            ),
          ];
    window.report_ui_.page_heading_tail_set(page_heading, selected_entries);
  }
  // Opens or closes a symbol's node, draws again, shows it, selects it.
  function node_toggle(symbol_button) {
    const graph_node = button_graph_nodes.get(symbol_button);
    selected_function_name = path_function(graph_node.node_path).name;
    heading_tail_show();
    const node_key = path_key(graph_node.node_path);
    const is_opening = !open_path_keys.has(node_key);
    if (is_opening) open_path_keys.add(node_key);
    else open_path_keys.delete(node_key);
    const had_focus = document.activeElement === symbol_button;
    graph_render();
    const toggled_place = node_places.get(node_key);
    // The redraw replaced the button, so its new one takes the focus.
    if (had_focus) toggled_place.symbol_button.focus({ preventScroll: true });
    cells_reveal(
      is_opening
        ? node_children(graph_node).flatMap(
            (child_node) =>
              node_places.get(path_key(child_node.node_path)).node_cells,
          )
        : toggled_place.node_cells,
    );
    window.report_ui_.focused_path_send([selected_function_name]);
  }
  // Returns the symbol button of the cell an input reached, if any.
  function symbol_button_of(browser_event) {
    return cell_symbol_buttons.get(browser_event.target.closest("td"));
  }

  // Takes the relayed preferences: the heat curve and the sort.
  function preferences_handler() {
    const view_preferences = window.report_preferences_.now();
    const scale_choice = window.report_preferences_
      .heat_scale_choices()
      .find(
        (offered_choice) =>
          offered_choice.value === view_preferences.heat_scale_value,
      );
    if (!scale_choice) window.throw_exception_("str_error_internal");
    heat_curve_name = scale_choice.curve;
    sort_mode = view_preferences.call_graph_sort_mode;
  }
  // Draws the graph and its heading's tail when the preferences change it.
  function preferences_apply() {
    preferences_handler();
    const preferences_text = JSON.stringify([heat_curve_name, sort_mode]);
    if (preferences_text === rendered_preferences_text) return;
    rendered_preferences_text = preferences_text;
    graph_render();
    heading_tail_show();
  }
  // Opens a fresh open set, draws every row and clears the selection.
  function view_reset() {
    open_path_keys = call_graph_open_set();
    selected_function_name = null;
    // Forgets the drawn preferences, so the graph draws again.
    rendered_preferences_text = null;
    preferences_apply();
    window.report_ui_.focused_path_send([]);
  }
  // Takes a relayed message: a view reset, else a change of its preferences.
  function relay_handler(message_data) {
    const is_changed = window.report_preferences_.relay_handler(message_data);
    if (message_data.report_ui === "view_reset") view_reset();
    else if (is_changed) preferences_apply();
  }
  // Shows the page from its top left when its address is followed again.
  function page_top_show() {
    page_scroll_box.scrollTo(0, 0);
  }

  // Keeps the reveal clearance as the table's scroll margin, in page units.
  graph_table.style.scrollMarginTop = CALL_GRAPH_REVEAL_CLEARANCE_LINES + "lh";
  graph_table.style.scrollMarginLeft =
    CALL_GRAPH_REVEAL_CLEARANCE_CHARS + "ch";
  graph_table.append(graph_body);
  graph_table.addEventListener(
    "click",
    window.try_catch_handler_((click_event) => {
      const symbol_button = symbol_button_of(click_event);
      if (symbol_button) node_toggle(symbol_button);
    }),
  );
  graph_table.addEventListener(
    "keydown",
    window.try_catch_handler_((key_event) => {
      const symbol_button = symbol_button_of(key_event);
      if (
        !symbol_button ||
        !window.report_ui_.widget_key.activates(
          window.report_ui_.widget_key.of(key_event),
        )
      )
        return;
      key_event.preventDefault();
      if (!key_event.repeat) node_toggle(symbol_button);
    }),
  );
  window.report_ui_.view_activate({
    forwards_input: true,
    recenter: page_top_show,
    relay_handler,
  });
})();
