// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const text = window.ui_strings_.text;
  const text_fill = window.ui_strings_.text_fill;
  const render_element = window.render_element_;
  const render_html_escape = window.render_html_escape_;
  const BRANCH_TEXTS = {
    first: text("str_call_graph_branch_first"),
    last: text("str_call_graph_branch_last"),
    middle: text("str_call_graph_branch_middle"),
    only: text("str_call_graph_branch_only"),
    pass: text("str_call_graph_branch_pass"),
  };
  const HEAD_TEXT = " " + text("str_call_graph_line");
  const page_scroll_box = document.getElementById("call-graph-page-");
  const graph_box = document.getElementById("call-graph-text-");
  const is_diff = graph_box.getAttribute("data-diff-") === "1";
  const call_graph_model = JSON.parse(graph_box.getAttribute("data-model-"));
  const function_links = call_graph_model.functions.map((function_entry) => ({
    name: function_entry[0],
    href: function_entry[1],
  }));
  let heat_curve_name = null,
    heat_sort_mode = null,
    rendered_preferences_text = null;

  // Reads one call edge from its row, a diff's baseline calls before its own.
  function call_edge_read(edge_row) {
    if (is_diff)
      return {
        caller_index: edge_row[0],
        callee_index: edge_row[1],
        baseline_calls: edge_row[2],
        calls: edge_row[3],
        call_line: edge_row[4],
        share_percent: null,
      };
    return {
      caller_index: edge_row[0],
      callee_index: edge_row[1],
      baseline_calls: null,
      calls: edge_row[2],
      call_line: edge_row[3],
      share_percent: null,
    };
  }
  const call_edges = call_graph_model.edges.map(call_edge_read);
  // Reads one root from its row, a diff's baseline calls before its own.
  function root_read(root_row) {
    if (is_diff)
      return {
        function_index: root_row[0],
        baseline_calls: root_row[1],
        calls: root_row[2],
      };
    return {
      function_index: root_row[0],
      baseline_calls: null,
      calls: root_row[1],
    };
  }
  const graph_roots = call_graph_model.roots.map(root_read);
  const function_calls = function_links.map(() => 0);
  const function_baseline_calls = function_links.map(() => 0);
  const function_callee_edges = function_links.map(() => []);
  for (const call_edge of call_edges) {
    function_calls[call_edge.callee_index] += call_edge.calls;
    if (is_diff)
      function_baseline_calls[call_edge.callee_index] +=
        call_edge.baseline_calls;
    function_callee_edges[call_edge.caller_index].push(call_edge);
  }
  for (const graph_root of graph_roots) {
    function_calls[graph_root.function_index] += graph_root.calls;
    if (is_diff)
      function_baseline_calls[graph_root.function_index] +=
        graph_root.baseline_calls;
  }

  // Returns the calls of an edge per call of its caller, null for none.
  function call_frequency(edge_calls, caller_calls) {
    if (caller_calls) return (100 * edge_calls) / caller_calls;
    return edge_calls ? null : 0;
  }
  // Returns the share an edge shows, a diff's the change of its frequency.
  function edge_share(call_edge) {
    const edge_frequency = call_frequency(
      call_edge.calls,
      function_calls[call_edge.caller_index],
    );
    if (!is_diff) return edge_frequency;
    const baseline_frequency = call_frequency(
      call_edge.baseline_calls,
      function_baseline_calls[call_edge.caller_index],
    );
    if (edge_frequency === null || baseline_frequency === null) return null;
    return window.report_ui_.diff_share(
      edge_frequency - baseline_frequency,
      baseline_frequency,
    );
  }
  for (const call_edge of call_edges)
    call_edge.share_percent = edge_share(call_edge);

  // Returns the text of a share, none for a root's share or a zero one.
  function share_text(share_percent, uses_whitespace) {
    if (!share_percent) return "";
    return is_diff
      ? window.report_ui_.signed_percent_text(share_percent, uses_whitespace)
      : window.report_ui_.percent_text(share_percent);
  }
  // Writes the heat colors of a share by the chosen curve, none for a root's.
  function heat_style(share_percent) {
    if (share_percent === null) return "";
    return window.report_ui_.heat_cell_style(
      share_percent,
      heat_curve_name,
      is_diff,
    );
  }
  // Returns the size of an edge's share for the heat sort, a root's last.
  function heat_key(call_edge) {
    return call_edge.share_percent === null
      ? -1
      : Math.abs(call_edge.share_percent);
  }
  // Orders a caller's edges by the chosen sort, heat then call line or name.
  function edges_sort(callee_edges) {
    const name_order = (edge_a, edge_b) =>
      function_links[edge_a.callee_index].name.localeCompare(
        function_links[edge_b.callee_index].name,
      );
    if (heat_sort_mode !== "heat") return callee_edges.toSorted(name_order);
    return callee_edges.toSorted(
      (edge_a, edge_b) =>
        heat_key(edge_b) - heat_key(edge_a) ||
        edge_a.call_line - edge_b.call_line ||
        name_order(edge_a, edge_b),
    );
  }

  // Builds a function's printed node, expanding a function where first met.
  function node_build(function_index, expanded_indexes, referenced_indexes) {
    const callee_edges = function_callee_edges[function_index];
    if (!callee_edges.length)
      return { function_index, node_kind: "leaf", callee_entries: [] };
    if (expanded_indexes.has(function_index)) {
      referenced_indexes.add(function_index);
      return { function_index, node_kind: "reference", callee_entries: [] };
    }
    expanded_indexes.add(function_index);
    return {
      function_index,
      node_kind: "expansion",
      callee_entries: edges_sort(callee_edges).map((call_edge) => ({
        call_edge,
        graph_node: node_build(
          call_edge.callee_index,
          expanded_indexes,
          referenced_indexes,
        ),
      })),
    };
  }
  // Numbers each expansion that a reference refers back to, in printed order.
  function numbers_assign(graph_node, referenced_indexes, definition_numbers) {
    if (graph_node.node_kind !== "expansion") return;
    if (referenced_indexes.has(graph_node.function_index))
      definition_numbers.set(
        graph_node.function_index,
        definition_numbers.size + 1,
      );
    for (const callee_entry of graph_node.callee_entries)
      numbers_assign(
        callee_entry.graph_node,
        referenced_indexes,
        definition_numbers,
      );
  }

  function piece_text(text_piece) {
    if (typeof text_piece === "string") return text_piece;
    if (text_piece.pieces) return text_piece.pieces.map(piece_text).join("");
    return text_piece.text;
  }
  function pieces_length(text_pieces) {
    return text_pieces.map(piece_text).join("").length;
  }
  // Returns the pieces naming a node: its function, then any mark.
  function label_pieces(graph_node, definition_numbers) {
    const function_link = function_links[graph_node.function_index];
    const name_piece = { text: function_link.name, href: function_link.href };
    const definition_number = definition_numbers.get(
      graph_node.function_index,
    );
    if (graph_node.node_kind === "reference")
      return [
        name_piece,
        " ",
        {
          text: text_fill("str_call_graph_reference", {
            number: definition_number,
          }),
          reference: definition_number,
        },
      ];
    if (
      graph_node.node_kind === "expansion" &&
      definition_number !== undefined
    )
      return [
        {
          definition: definition_number,
          pieces: [
            name_piece,
            " ",
            {
              text: text_fill("str_call_graph_definition", {
                number: definition_number,
              }),
            },
          ],
        },
      ];
    return [name_piece];
  }
  // Lays out a node and its callees as lines, the shown shares aligned.
  function node_lines(graph_node, definition_numbers) {
    const node_label = label_pieces(graph_node, definition_numbers);
    if (graph_node.node_kind !== "expansion") return [node_label];
    const callee_entries = graph_node.callee_entries;
    const shown_share_count = callee_entries.filter((callee_entry) =>
      share_text(callee_entry.call_edge.share_percent, false),
    ).length;
    const share_texts = callee_entries.map((callee_entry) =>
      share_text(callee_entry.call_edge.share_percent, shown_share_count > 1),
    );
    const share_width = Math.max(
      ...share_texts.map((child_share_text) => child_share_text.length),
    );
    const branch_column = pieces_length(node_label) + HEAD_TEXT.length;
    const graph_lines = [];
    callee_entries.forEach((callee_entry, child_index) => {
      const is_last = child_index === callee_entries.length - 1;
      let branch_text = is_last ? BRANCH_TEXTS.last : BRANCH_TEXTS.middle;
      if (!child_index)
        branch_text = is_last ? BRANCH_TEXTS.only : BRANCH_TEXTS.first;
      const pass_text = is_last
        ? " ".repeat(BRANCH_TEXTS.pass.length)
        : BRANCH_TEXTS.pass;
      const lead_pieces = child_index
        ? [" ".repeat(branch_column) + branch_text + " "]
        : [...node_label, HEAD_TEXT + branch_text + " "];
      const share_pieces = share_texts[child_index]
        ? [
            {
              text: share_texts[child_index].padStart(share_width),
              style: heat_style(callee_entry.call_edge.share_percent),
            },
            " ",
          ]
        : [];
      const child_column =
        branch_column + branch_text.length + 1 + pieces_length(share_pieces);
      const child_lines = node_lines(
        callee_entry.graph_node,
        definition_numbers,
      );
      child_lines.forEach((child_line, line_index) => {
        if (line_index)
          graph_lines.push([
            " ".repeat(branch_column) +
              pass_text +
              " ".repeat(child_column - branch_column - pass_text.length),
            ...child_line,
          ]);
        else
          graph_lines.push([...lead_pieces, ...share_pieces, ...child_line]);
      });
    });
    return graph_lines;
  }

  // Writes one piece: a function link, a heat colored share, a mark or text.
  function piece_markup(text_piece) {
    if (typeof text_piece === "string") return render_html_escape(text_piece);
    if (text_piece.pieces)
      return render_element(
        "span",
        { "data-definition-number-": text_piece.definition },
        text_piece.pieces.map(piece_markup).join(""),
      );
    const text_markup = render_html_escape(text_piece.text);
    if (text_piece.href)
      return render_element("a", { href: text_piece.href }, text_markup);
    if (text_piece.style)
      return render_element("span", { style: text_piece.style }, text_markup);
    if (text_piece.reference)
      return render_element(
        "a",
        {
          role: "button",
          tabindex: 0,
          "data-reference-number-": text_piece.reference,
        },
        text_markup,
      );
    return text_markup;
  }
  // Draws every root's tree by the chosen sort and curve.
  function graph_render() {
    const expanded_indexes = new Set();
    const referenced_indexes = new Set();
    const root_nodes = graph_roots.map((graph_root) =>
      node_build(
        graph_root.function_index,
        expanded_indexes,
        referenced_indexes,
      ),
    );
    const definition_numbers = new Map();
    for (const root_node of root_nodes)
      numbers_assign(root_node, referenced_indexes, definition_numbers);
    graph_box.innerHTML = root_nodes
      .flatMap((root_node) => node_lines(root_node, definition_numbers))
      .map((graph_line) => graph_line.map(piece_markup).join(""))
      .join("\n");
    window.report_ui_.layout_activate();
  }

  // Shows the expansion a reference refers back to at the top of the page.
  function definition_show(reference_element) {
    const definition_element = graph_box.querySelector(
      `[data-definition-number-="${reference_element.getAttribute(
        "data-reference-number-",
      )}"]`,
    );
    const box_rect = page_scroll_box.getBoundingClientRect();
    const definition_rect = definition_element.getBoundingClientRect();
    page_scroll_box.scrollTop += definition_rect.top - box_rect.top;
    if (
      definition_rect.left < box_rect.left ||
      definition_rect.right > box_rect.right
    )
      page_scroll_box.scrollLeft += definition_rect.left - box_rect.left;
  }
  function reference_element_of(browser_event) {
    return browser_event.target.closest("[data-reference-number-]");
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
  // Takes a relayed message, drawing again when its preferences changed.
  function relay_handler(message_data) {
    if (window.report_preferences_.relay_handler(message_data))
      preferences_apply();
  }
  // Shows the page from its top left when its address is followed again.
  function page_top_show() {
    page_scroll_box.scrollTo(0, 0);
  }

  graph_box.addEventListener(
    "click",
    window.try_catch_handler_((click_event) => {
      const reference_element = reference_element_of(click_event);
      if (reference_element) definition_show(reference_element);
    }),
  );
  graph_box.addEventListener(
    "keydown",
    window.try_catch_handler_((key_event) => {
      const reference_element = reference_element_of(key_event);
      if (
        !reference_element ||
        !window.report_ui_.widget_key.activates(
          window.report_ui_.widget_key.of(key_event),
        )
      )
        return;
      key_event.preventDefault();
      if (!key_event.repeat) definition_show(reference_element);
    }),
  );
  window.report_ui_.view_activate({
    forwards_input: true,
    recenter: page_top_show,
    relay_handler,
  });
})();
