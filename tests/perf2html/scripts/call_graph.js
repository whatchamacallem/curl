// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const CALL_GRAPH_BRANCH_LAST_TEXT = settings_("CALL_GRAPH_BRANCH_LAST_TEXT");
  const CALL_GRAPH_BRANCH_MIDDLE_TEXT = settings_(
    "CALL_GRAPH_BRANCH_MIDDLE_TEXT",
  );
  const CALL_GRAPH_BRANCH_OPEN_TEXT = settings_("CALL_GRAPH_BRANCH_OPEN_TEXT");
  const CALL_GRAPH_BRANCH_PASS_TEXT = settings_("CALL_GRAPH_BRANCH_PASS_TEXT");
  const CALL_GRAPH_LINE_TEXT = settings_("CALL_GRAPH_LINE_TEXT");
  const CALL_GRAPH_MULTIPLE_TEMPLATE = settings_(
    "CALL_GRAPH_MULTIPLE_TEMPLATE",
  );
  const CALL_GRAPH_REVEAL_CLEARANCE_CHARS = settings_(
    "CALL_GRAPH_REVEAL_CLEARANCE_CHARS",
  );
  const CALL_GRAPH_REVEAL_CLEARANCE_LINES = settings_(
    "CALL_GRAPH_REVEAL_CLEARANCE_LINES",
  );
  const CALL_GRAPH_SHARE_TEMPLATE = settings_("CALL_GRAPH_SHARE_TEMPLATE");
  const CALL_GRAPH_SUBROUTINE_TEMPLATE = settings_(
    "CALL_GRAPH_SUBROUTINE_TEMPLATE",
  );
  const CALL_GRAPH_SYMBOL_TEMPLATE = settings_("CALL_GRAPH_SYMBOL_TEMPLATE");
  const NUMBER_FRACTION_DIGITS = settings_("NUMBER_FRACTION_DIGITS");

  const render_element = window.render_element_;
  const render_html_escape = window.render_html_escape_;
  const template_fill = window.report_ui_.template_fill;
  const EMPTY_CELL_MARKUP = render_element("td", {}, "");
  const OPEN_CELL_MARKUP = render_element(
    "td",
    {},
    render_html_escape(CALL_GRAPH_BRANCH_OPEN_TEXT),
  );
  const PASS_CELL_MARKUP = render_element(
    "td",
    {},
    render_html_escape(CALL_GRAPH_BRANCH_PASS_TEXT),
  );
  const page_scroll_box = document.getElementById("call-graph-page-");
  const graph_table = document.getElementById("call-graph-table-");
  const call_graph_model = JSON.parse(graph_table.getAttribute("data-model-"));
  const graph_body = window.render_element_of_(
    render_element("tbody", {}, ""),
  );
  const row_graph_nodes = new WeakMap();

  // Reads one function's row, its cumulative cost and calls summed below.
  function function_record_read(function_row) {
    return {
      name: function_row[0],
      self_cost: function_row[1],
      cumulative_cost: function_row[1],
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
  for (const call_root of call_roots)
    function_records[call_root.function_index].invocation_count +=
      call_root.calls;
  for (const call_edge of call_graph_model.edges.map(call_edge_read)) {
    const caller_record = function_records[call_edge.caller_index];
    caller_record.callee_edges.push(call_edge);
    function_records[call_edge.callee_index].invocation_count +=
      call_edge.calls;
    // A self call's cost is already inside the caller's own and other calls.
    if (call_edge.callee_index !== call_edge.caller_index)
      caller_record.cumulative_cost += call_edge.inclusive_cost;
  }

  // Returns an edge's share of its caller's cumulative cost, null for none.
  function edge_share(call_edge) {
    const caller_cost =
      function_records[call_edge.caller_index].cumulative_cost;
    if (!caller_cost || !call_edge.inclusive_cost) return null;
    return (100 * call_edge.inclusive_cost) / caller_cost;
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
  // Orders a caller's edges by share, as by inclusive cost, line and name.
  function heat_order(edge_a, edge_b) {
    return (
      edge_b.inclusive_cost - edge_a.inclusive_cost ||
      edge_a.call_line - edge_b.call_line ||
      name_order(edge_a, edge_b)
    );
  }
  // Orders a node's shown edges by the chosen sort, hottest first or by name.
  function edges_sort(callee_edges) {
    return callee_edges.toSorted(
      heat_sort_mode === "heat" ? heat_order : name_order,
    );
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
  // Returns a fresh open set: the hottest path's nodes with shown children.
  function call_graph_open_set() {
    const root_cost = (call_root) =>
      function_records[call_root.function_index].cumulative_cost;
    let hottest_root = call_roots[0];
    for (const call_root of call_roots)
      if (root_cost(call_root) > root_cost(hottest_root))
        hottest_root = call_root;
    const open_set = new Set();
    let node_path = [hottest_root.function_index];
    let shown_edges = shown_callee_edges(node_path);
    while (shown_edges.length) {
      open_set.add(path_key(node_path));
      const hottest_edge = shown_edges.toSorted(heat_order)[0];
      node_path = [...node_path, hottest_edge.callee_index];
      shown_edges = shown_callee_edges(node_path);
    }
    return open_set;
  }
  let heat_curve_name = null,
    heat_sort_mode = null,
    open_path_keys = call_graph_open_set(),
    rendered_preferences_text = null;

  // Makes a root's node, which draws no branch, share or multiple.
  function root_node(call_root) {
    return {
      node_path: [call_root.function_index],
      call_edge: null,
      later_sibling_flags: [],
    };
  }
  // Lists a node's shown children by the chosen sort, flagging later siblings.
  function node_children(graph_node) {
    const shown_edges = edges_sort(shown_callee_edges(graph_node.node_path));
    return shown_edges.map((call_edge, child_index) => ({
      node_path: [...graph_node.node_path, call_edge.callee_index],
      call_edge,
      later_sibling_flags: [
        ...graph_node.later_sibling_flags,
        child_index < shown_edges.length - 1,
      ],
    }));
  }
  // Returns whether a node is open.
  function node_is_open(graph_node) {
    return open_path_keys.has(path_key(graph_node.node_path));
  }

  // Writes a node's branch, the middle one before a later sibling.
  function branch_markup(graph_node) {
    if (graph_node.call_edge === null) return "";
    return render_html_escape(
      graph_node.later_sibling_flags.at(-1)
        ? CALL_GRAPH_BRANCH_MIDDLE_TEXT
        : CALL_GRAPH_BRANCH_LAST_TEXT,
    );
  }
  // Writes a node's share in its template, heat colored by the chosen curve.
  function share_markup(graph_node) {
    if (graph_node.call_edge === null) return "";
    const share_percent = edge_share(graph_node.call_edge);
    if (share_percent === null) return "";
    return template_fill(render_html_escape(CALL_GRAPH_SHARE_TEMPLATE), {
      __SHARE__: render_element(
        "span",
        {
          style: window.report_ui_.heat_cell_style(
            share_percent,
            heat_curve_name,
            false,
          ),
        },
        render_html_escape(window.report_ui_.percent_text(share_percent)),
      ),
    });
  }
  // Writes a node's symbol in its template, a button if it has shown children.
  function symbol_markup(graph_node, has_shown_children) {
    const name_markup = render_html_escape(
      path_function(graph_node.node_path).name,
    );
    return template_fill(render_html_escape(CALL_GRAPH_SYMBOL_TEMPLATE), {
      __SYMBOL__: has_shown_children
        ? window.render_menu_button_("action", name_markup, {
            tag_name: "span",
          })
        : name_markup,
    });
  }
  // Writes a node's calls multiple in its template, if it has one.
  function multiple_markup(graph_node) {
    if (graph_node.call_edge === null) return "";
    const calls_multiple = edge_multiple(graph_node.call_edge);
    if (calls_multiple === null) return "";
    return template_fill(render_html_escape(CALL_GRAPH_MULTIPLE_TEMPLATE), {
      __MULTIPLE__: render_html_escape(
        window.report_ui_.fixed_text(calls_multiple, NUMBER_FRACTION_DIGITS),
      ),
    });
  }
  // Writes a node's tail: the line when open, else its subroutine time.
  function tail_markup(graph_node, is_open) {
    if (is_open) return render_html_escape(CALL_GRAPH_LINE_TEXT);
    const function_record = path_function(graph_node.node_path);
    return template_fill(render_html_escape(CALL_GRAPH_SUBROUTINE_TEMPLATE), {
      __SUBROUTINE__: render_html_escape(
        window.report_ui_.human_text(
          function_record.cumulative_cost - function_record.self_cost,
        ),
      ),
    });
  }
  // Makes a node's row: its ancestors' pass texts, then its own cells.
  function node_row(graph_node) {
    const node_depth = graph_node.later_sibling_flags.length;
    const has_shown_children =
      shown_callee_edges(graph_node.node_path).length > 0;
    const is_open = node_is_open(graph_node);
    const row_cells = [];
    for (let group_depth = 0; group_depth < node_depth; group_depth++) {
      const is_passed =
        group_depth > 0 && graph_node.later_sibling_flags[group_depth - 1];
      row_cells.push(
        is_passed ? PASS_CELL_MARKUP : EMPTY_CELL_MARKUP,
        EMPTY_CELL_MARKUP,
        EMPTY_CELL_MARKUP,
        EMPTY_CELL_MARKUP,
        EMPTY_CELL_MARKUP,
      );
    }
    const own_multiple_markup = multiple_markup(graph_node);
    row_cells.push(
      render_element("td", {}, branch_markup(graph_node)),
      render_element(
        "td",
        { class: "call-graph-share-" },
        share_markup(graph_node),
      ),
      render_element("td", {}, symbol_markup(graph_node, has_shown_children)),
    );
    // A row ends at its last used cell, one with shown children at its tail.
    if (has_shown_children || own_multiple_markup)
      row_cells.push(render_element("td", {}, own_multiple_markup));
    if (has_shown_children)
      row_cells.push(
        render_element(
          "td",
          { class: "call-graph-tail-" },
          tail_markup(graph_node, is_open),
        ),
      );
    if (is_open) row_cells.push(OPEN_CELL_MARKUP);
    const graph_row = window.render_element_of_(
      render_element("tr", {}, row_cells.join("")),
    );
    row_graph_nodes.set(graph_row, graph_node);
    return graph_row;
  }
  // Makes a node's row, then the rows below it when it is open.
  function node_rows(graph_node) {
    const graph_row = node_row(graph_node);
    if (!node_is_open(graph_node)) return [graph_row];
    return [graph_row, ...rows_below(graph_node)];
  }
  // Makes the rows below an open node, each child's and those below it.
  function rows_below(graph_node) {
    return node_children(graph_node).flatMap(node_rows);
  }
  // Draws every root's row and the rows below each open node.
  function graph_render() {
    graph_body.replaceChildren(
      ...call_roots.flatMap((call_root) => node_rows(root_node(call_root))),
    );
    window.report_ui_.layout_activate();
  }

  // Removes the rows below a node's row, each deeper row that follows it.
  function rows_below_remove(graph_row) {
    const path_length = row_graph_nodes.get(graph_row).node_path.length;
    let next_row = graph_row.nextElementSibling;
    while (
      next_row &&
      row_graph_nodes.get(next_row).node_path.length > path_length
    ) {
      next_row.remove();
      next_row = graph_row.nextElementSibling;
    }
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
  // Scrolls the page the least that shows the rows just opened below a row.
  function rows_reveal(graph_row, shown_rows) {
    const design_px = window.report_ui_.design_px;
    const box_rect = page_scroll_box.getBoundingClientRect();
    const table_style = getComputedStyle(graph_table);
    const first_rect = shown_rows[0].getBoundingClientRect();
    const last_rect = shown_rows.at(-1).getBoundingClientRect();
    // The open text starts the column of the opened rows' branches.
    const span_left = graph_row.lastElementChild.getBoundingClientRect().left;
    const span_right = Math.max(
      ...shown_rows.map(
        (shown_row) =>
          shown_row.lastElementChild.getBoundingClientRect().right,
      ),
    );
    page_scroll_box.scrollTop += reveal_travel(
      design_px(first_rect.top - box_rect.top),
      design_px(last_rect.bottom - box_rect.top),
      page_scroll_box.clientHeight,
      parseFloat(table_style.scrollMarginTop),
    );
    page_scroll_box.scrollLeft += reveal_travel(
      design_px(span_left - box_rect.left),
      design_px(span_right - box_rect.left),
      page_scroll_box.clientWidth,
      parseFloat(table_style.scrollMarginLeft),
    );
  }
  // Lists the focused path of a node, each function's name from its root on.
  function focused_path_entries(graph_node) {
    return graph_node.node_path.map(
      (function_index) => function_records[function_index].name,
    );
  }
  // Opens or closes a symbol's node, then sends its path as the focused path.
  function node_toggle(symbol_button) {
    const graph_row = symbol_button.closest("tr");
    const graph_node = row_graph_nodes.get(graph_row);
    const tail_cell = graph_row.querySelector(":scope > .call-graph-tail-");
    if (node_is_open(graph_node)) {
      open_path_keys.delete(path_key(graph_node.node_path));
      rows_below_remove(graph_row);
      // The open text ends an open node's row.
      graph_row.lastElementChild.remove();
      tail_cell.innerHTML = tail_markup(graph_node, false);
    } else {
      open_path_keys.add(path_key(graph_node.node_path));
      tail_cell.innerHTML = tail_markup(graph_node, true);
      graph_row.append(window.render_element_of_(OPEN_CELL_MARKUP));
      const shown_rows = rows_below(graph_node);
      graph_row.after(...shown_rows);
      rows_reveal(graph_row, shown_rows);
    }
    window.report_ui_.layout_activate();
    window.report_ui_.focused_path_send(focused_path_entries(graph_node));
  }
  // Returns the symbol button an input reached, null for none.
  function symbol_button_of(browser_event) {
    return browser_event.target.closest(".menu-button-");
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
    heat_sort_mode = view_preferences.heat_sort_mode;
  }
  // Draws the graph again when the relayed preferences change what it shows.
  function preferences_apply() {
    preferences_handler();
    const preferences_text = JSON.stringify([heat_curve_name, heat_sort_mode]);
    if (preferences_text === rendered_preferences_text) return;
    rendered_preferences_text = preferences_text;
    graph_render();
  }
  // Opens the hottest path alone, draws every row and clears the focused path.
  function view_reset() {
    open_path_keys = call_graph_open_set();
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
