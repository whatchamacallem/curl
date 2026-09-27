window.report_error_overlay = (function () {
  "use strict";

  const OVERLAY_MESSAGE_NAME = "report_error";
  const REPORT_MANIFEST_GLOBAL_NAME = "report_manifest";
  const OVERLAY_BACKGROUND_COLOR = "#14171c";
  const OVERLAY_TEXT_COLOR = "#f2f4f6";
  const OVERLAY_LINK_COLOR = "#ff4427";
  const OVERLAY_FONT_FAMILY = "Monaco, monospace";
  const OVERLAY_LINE_HEIGHT = "1.5";
  const DESIGN_COORDINATES_WIDTH_PX = 1920;
  const DESIGN_FONT_SIZE_PX = 12;
  // every line the page and copy write, so an error survives a few forwards
  const OVERLAY_TEXT_WIDTH_CHARS = 79;
  const WRAP_INDENT_TEXT = "  ";
  const CONTROL_SEPARATOR_TEXT = " | ";
  const COPY_FAILED_SUFFIX_TEXT = "(failed)";
  const TABLE_CELL_JOINS = ["| ", " | ", " |"];
  const TABLE_FRAME_COLUMN_SHARE = 1 / 3;
  // a manifest value part shaped as code: an assignment, a path, a
  // placeholder, a bracket, or one word (a hash, a name)
  const CODE_SHAPE_PATTERN = /[=_<>[\]{}]|\S\/\S|^\S+$/;
  // where a manifest writer joins a value's parts, never inside brackets
  const VALUE_JOINT_PATTERN = /(, | {2,})(?![^()[\]]*[)\]])/;
  // what wrapping folds to one space: a blank run holding a line break, a
  // tab or other blank, since wrapping alone breaks lines and counts width
  const WRAP_FOLDED_BLANKS_PATTERN = /\s*[^\S ]\s*/g;
  // what wrapping moves whole to a new line when it fits there: a word, a
  // code span or a bracketed group, with what touches it
  const WRAP_UNIT_PATTERN = /((?:`[^`]*`|\([^()]*\)|\[[^[\]]*\]|\S)+)(\s*)/g;
  // every event a listener left on window or document may wait for; the
  // listeners on the page's elements leave with its elements
  const EVENT_TYPES_STOPPED = [
    "DOMContentLoaded",
    "click",
    "hashchange",
    "keydown",
    "keyup",
    "load",
    "message",
    "pointerdown",
    "pointermove",
    "pointerup",
    "popstate",
    "resize",
    "storage",
    "wheel",
  ];

  const control_actions = new Map();
  let overlay_is_shown = false;

  // The address link's click: that page loaded whole. One differing in its
  // hash alone arrives as a popstate, which event_gate reloads
  function address_open(address) {
    if (address === location.href) location.reload();
    else location.assign(address);
  }

  function address_shorten(text, root_prefix) {
    return String(text).replace(/file:\/\/\S*/g, function (found) {
      return prefix_drop(found, root_prefix);
    });
  }

  // Each column its longest cell while the table fits the line; past it the
  // frame gets its share, a column needing less giving the other the rest
  function column_widths(rows) {
    const longest_cells = [0, 1].map(function (column) {
      return Math.max(
        ...rows.map(function (row) {
          return row[column].length;
        }),
      );
    });
    const cells_room =
      OVERLAY_TEXT_WIDTH_CHARS - TABLE_CELL_JOINS.join("").length;
    if (longest_cells[0] + longest_cells[1] <= cells_room) {
      return longest_cells;
    }
    const frame_width = Math.min(
      longest_cells[0],
      Math.max(
        Math.floor(cells_room * TABLE_FRAME_COLUMN_SHARE),
        cells_room - longest_cells[1],
      ),
    );
    return [frame_width, cells_room - frame_width];
  }

  function control_add(parent, label, action) {
    const link = document.createElement("a");
    link.textContent = label;
    link.style.color = OVERLAY_LINK_COLOR;
    link.style.textDecoration = "underline";
    link.style.cursor = "pointer";
    control_actions.set(link, action);
    parent.appendChild(link);
    return link;
  }

  // The page as markdown, cut around the address so it can be a link;
  // copy puts the three parts on the clipboard joined
  function document_parts(report) {
    const root_prefix = root_prefix_of();
    const later_sections = [
      "",
      "## " +
        text_of_or_id("str_error_heading_callstack") +
        "\n\n" +
        stack_table(report.stack, root_prefix),
    ];
    const manifest_text = window[REPORT_MANIFEST_GLOBAL_NAME];
    // a report that never finished has no manifest script, so no section
    if (manifest_text !== undefined) {
      later_sections.push(
        "## " +
          text_of_or_id("str_error_heading_manifest") +
          "\n\n" +
          manifest_list(manifest_text),
      );
    }
    return [
      [
        "# " + text_of_or_id("str_error_page_heading"),
        text_wrap(
          format_or_raw(report.message),
          OVERLAY_TEXT_WIDTH_CHARS,
          WRAP_INDENT_TEXT,
        ),
        "## " + text_of_or_id("str_error_heading_address"),
        "",
      ].join("\n\n"),
      text_wrap(
        "./" + prefix_drop(report.address, root_prefix),
        OVERLAY_TEXT_WIDTH_CHARS,
        WRAP_INDENT_TEXT,
      ),
      later_sections.join("\n\n") + "\n",
    ];
  }

  function error_describe(reason) {
    if (reason instanceof Error) {
      return {
        message: String(reason.message || reason),
        stack: String(reason.stack || ""),
      };
    }
    if (reason && typeof reason === "object") {
      let printed = "";
      try {
        printed = JSON.stringify(reason);
      } catch (ignored) {
        printed = String(reason);
      }
      return { message: printed, stack: String(reason.stack || "") };
    }
    return { message: String(reason), stack: "" };
  }

  // Once the error owns the tab no other listener runs: this one is first
  // on window and stops each event, running only the overlay's own links
  function event_gate(browser_event) {
    if (!overlay_is_shown) return;
    browser_event.stopImmediatePropagation();
    // arriving at another entry of this page by history loads it whole
    if (browser_event.type === "popstate") location.reload();
    const control_action = control_actions.get(browser_event.target);
    if (browser_event.type !== "click" || !control_action) return;
    // a click with a modifier opens the address link the browser's way
    if (browser_event.ctrlKey || browser_event.metaKey) return;
    if (browser_event.shiftKey) return;
    browser_event.preventDefault();
    control_action();
  }

  function format_or_raw(message) {
    const text = String(message);
    const tokens = text.split(/\s+/).filter(function (token) {
      return token !== "";
    });
    const strings = window.ui_strings;
    if (!tokens.length || !strings) {
      return text;
    }
    if (typeof strings.text_over_args !== "function") {
      return text;
    }
    let formatted = null;
    try {
      formatted = strings.text_over_args(tokens[0], tokens.slice(1));
    } catch (ignored) {
      return text;
    }
    if (formatted === null) {
      return text;
    }
    return tokens[0] + ":  " + formatted;
  }

  function handler_install() {
    for (const event_type of EVENT_TYPES_STOPPED) {
      window.addEventListener(event_type, event_gate, true);
    }
    window.addEventListener("error", function (browser_event) {
      overlay_show(browser_event.error || browser_event.message);
    });
    window.addEventListener("unhandledrejection", function (browser_event) {
      overlay_show(browser_event.reason);
    });
    window.addEventListener("message", function (browser_event) {
      const payload = browser_event.data;
      if (!payload || payload.report_ui !== OVERLAY_MESSAGE_NAME) {
        return;
      }
      report_render(payload.report);
    });
  }

  // The manifest as a markdown list: the version line bold, then each
  // LABEL=value row as a bold label and its value
  function manifest_list(manifest_text) {
    const list_items = [];
    for (const manifest_row of manifest_text.split("\n")) {
      const cut = manifest_row.indexOf("=");
      const row_label =
        cut < 0 ? manifest_row : manifest_row.slice(0, cut) + ":";
      const row_value =
        cut < 0 ? "" : " " + value_markdown(manifest_row.slice(cut + 1));
      list_items.push(
        text_wrap(
          "- **" + row_label + "**" + row_value,
          OVERLAY_TEXT_WIDTH_CHARS,
          WRAP_INDENT_TEXT,
        ),
      );
    }
    return list_items.join("\n");
  }

  function overlay_show(reason) {
    const described = error_describe(reason);
    report_render({
      address: location.href,
      message: described.message,
      stack: described.stack,
    });
  }

  // Swap the whole page for the error: its styles, zoom and font fit, its
  // frames and the listeners on its elements leave with the old root
  function page_replace(report) {
    const page_parts = document_parts(report);
    const page_root = document.createElement("html");
    const page_head = page_root.appendChild(document.createElement("head"));
    const page_title = page_head.appendChild(document.createElement("title"));
    page_title.textContent = text_of_or_id("str_error_page_title");
    const page_body = page_root.appendChild(document.createElement("body"));
    page_body.style.margin = "0";
    page_body.style.background = OVERLAY_BACKGROUND_COLOR;
    page_body.style.color = OVERLAY_TEXT_COLOR;
    page_body.style.fontFamily = OVERLAY_FONT_FAMILY;
    // the design font size at the design width, scaled to the window's
    page_body.style.fontSize =
      "calc(100vw * " +
      DESIGN_FONT_SIZE_PX +
      " / " +
      DESIGN_COORDINATES_WIDTH_PX +
      ")";
    page_body.style.lineHeight = OVERLAY_LINE_HEIGHT;
    const block = page_body.appendChild(document.createElement("pre"));
    block.style.font = "inherit";
    block.style.width = OVERLAY_TEXT_WIDTH_CHARS + "ch";
    block.style.margin = "0 auto";
    // a blank line keeps the text off the top edge; copy leaves it out
    block.append("\n" + page_parts[0]);
    const address_link = control_add(block, page_parts[1], function () {
      address_open(report.address);
    });
    address_link.href = report.address;
    block.append(page_parts[2] + "\n");
    const copy_label = text_of_or_id("str_error_control_copy");
    const copy_link = control_add(block, copy_label, function () {
      text_copy(page_parts.join("")).catch(function () {
        copy_link.textContent = copy_label + " " + COPY_FAILED_SUFFIX_TEXT;
      });
    });
    block.append(CONTROL_SEPARATOR_TEXT);
    control_add(block, text_of_or_id("str_error_control_back"), function () {
      history.back();
    });
    document.replaceChild(page_root, document.documentElement);
  }

  function prefix_drop(path_text, root_prefix) {
    if (path_text.indexOf(root_prefix) === 0) {
      return path_text.slice(root_prefix.length);
    }
    const wanted = root_prefix.split("/");
    const found = path_text.split("/");
    let shared = 0;
    while (shared < wanted.length && shared < found.length) {
      if (wanted[shared] !== found[shared]) {
        break;
      }
      shared += 1;
    }
    return found.slice(shared).join("/");
  }

  function report_render(report) {
    if (overlay_is_shown) {
      return;
    }
    overlay_is_shown = true;
    // construction/DOM/postMessage has nowhere else to surface a failure:
    // a raw write is the one fallback guaranteed to still show the error
    try {
      if (window.parent !== window) {
        window.parent.postMessage(
          { report_ui: OVERLAY_MESSAGE_NAME, report: report },
          "*",
        );
        return;
      }
      // nothing the broken page left runs on: a script parsed after this
      // lands in the detached old root, which never runs it
      timers_clear();
      page_replace(report);
    } catch (page_replace_failure) {
      console.error(page_replace_failure);
      const raw_text = String(report.message) + "\n\n" + String(report.stack);
      document.write("<pre></pre>");
      document.querySelector("pre").textContent = raw_text;
    }
  }

  function root_prefix_of() {
    const here = String(location.href).split("#")[0].split("?")[0];
    const cut = here.lastIndexOf("/");
    return cut < 0 ? "" : here.slice(0, cut + 1);
  }

  // One table row, each cell wrapped to its column's width; a cell longer
  // than its column continues on the rows below
  function row_text(cells, widths) {
    const cell_lines = cells.map(function (cell, column) {
      return text_wrap(cell, widths[column], "").split("\n");
    });
    const written = [];
    const line_count = Math.max(cell_lines[0].length, cell_lines[1].length);
    for (let line_index = 0; line_index < line_count; line_index += 1) {
      written.push(
        TABLE_CELL_JOINS[0] +
          (cell_lines[0][line_index] || "").padEnd(widths[0]) +
          TABLE_CELL_JOINS[1] +
          (cell_lines[1][line_index] || "").padEnd(widths[1]) +
          TABLE_CELL_JOINS[2],
      );
    }
    return written.join("\n");
  }

  function stack_row_of(line, root_prefix) {
    const bare = line.trim().replace(/^at\s+/, "");
    const text = address_shorten(bare, root_prefix);
    const braced = /^(.*?)\s*\((.*)\)$/.exec(text);
    if (braced) {
      return [braced[1], braced[2]];
    }
    const at_sign = text.indexOf("@");
    if (at_sign > 0) {
      return [text.slice(0, at_sign), text.slice(at_sign + 1)];
    }
    return [text, ""];
  }

  function stack_table(stack_text, root_prefix) {
    const rows = [];
    for (const line of String(stack_text || "").split("\n")) {
      if (line.trim()) {
        rows.push(stack_row_of(line, root_prefix));
      }
    }
    if (!rows.length) {
      return text_of_or_id("str_error_callstack_unavailable");
    }
    return table_render(
      [
        text_of_or_id("str_error_column_frame"),
        text_of_or_id("str_error_column_location"),
      ],
      rows,
    );
  }

  function table_render(titles, rows) {
    const widths = column_widths([titles].concat(rows));
    const rule_cells = widths.map(function (width) {
      return "-".repeat(width);
    });
    const written = [row_text(titles, widths), row_text(rule_cells, widths)];
    for (const row of rows) {
      written.push(row_text(row, widths));
    }
    return written.join("\n");
  }

  // Resolves once text is on the clipboard, rejects otherwise; the caller
  // shows the failure, so neither copy path hides one
  function text_copy(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve) {
      const holder = document.createElement("textarea");
      holder.value = text;
      document.body.appendChild(holder);
      holder.select();
      const copied = document.execCommand("copy");
      document.body.removeChild(holder);
      if (!copied) {
        throw new Error("execCommand copy returned false");
      }
      resolve();
    });
  }

  function text_of_or_id(string_id) {
    const strings = window.ui_strings;
    if (!strings || typeof strings.text_of !== "function") {
      return string_id;
    }
    try {
      return strings.text_of(string_id);
    } catch (ignored) {
      return string_id;
    }
  }

  // Lines of at most width characters broken at blanks, each after the
  // first under indent; a unit fitting on a line is never broken
  function text_wrap(text, width, indent) {
    const folded_text = text.replace(WRAP_FOLDED_BLANKS_PATTERN, " ");
    const wrapped_lines = [];
    let current_line = "";
    let line_is_empty = true;
    let pending_gap = "";
    function word_place(word) {
      const joined = current_line + pending_gap + word;
      if (!line_is_empty && joined.length > width) {
        wrapped_lines.push(current_line);
        current_line = indent;
        line_is_empty = true;
      }
      let word_rest = line_is_empty ? word : pending_gap + word;
      // a word longer than a whole line is cut: nothing else keeps width
      while (current_line.length + word_rest.length > width) {
        const line_room = width - current_line.length;
        wrapped_lines.push(current_line + word_rest.slice(0, line_room));
        word_rest = word_rest.slice(line_room);
        current_line = indent;
      }
      current_line += word_rest;
      line_is_empty = false;
    }
    for (const unit_match of folded_text.matchAll(WRAP_UNIT_PATTERN)) {
      if (indent.length + unit_match[1].length <= width) {
        word_place(unit_match[1]);
      } else {
        for (const word_match of unit_match[1].matchAll(/(\S+)(\s*)/g)) {
          word_place(word_match[1]);
          pending_gap = word_match[2];
        }
      }
      pending_gap = unit_match[2];
    }
    wrapped_lines.push(current_line);
    return wrapped_lines.join("\n");
  }

  // Clear every timer and animation frame the page set: ids count up from
  // one, so every id to a fresh one is cleared, intervals with timeouts
  function timers_clear() {
    const newest_timer = setTimeout(function () {}, 0);
    for (let timer_id = 1; timer_id <= newest_timer; timer_id += 1) {
      clearTimeout(timer_id);
    }
    const newest_frame = requestAnimationFrame(function () {});
    for (let frame_id = 1; frame_id <= newest_frame; frame_id += 1) {
      cancelAnimationFrame(frame_id);
    }
  }

  // A manifest value as markdown: cut at the joints its writer put between
  // parts (split keeps each joint), a part shaped as code in a code span
  function value_markdown(value) {
    return value
      .split(VALUE_JOINT_PATTERN)
      .map(function (value_part, part_index) {
        if (part_index % 2) return value_part === ", " ? value_part : " ";
        return CODE_SHAPE_PATTERN.test(value_part)
          ? "`" + value_part + "`"
          : value_part;
      })
      .join("");
  }

  handler_install();
  return { overlay_show };
})();
