window.report_error_overlay = (function () {
  "use strict";

  const OVERLAY_ROOT_ID = "reportErrorOverlay";
  const OVERLAY_MESSAGE_NAME = "report_error";
  const REPORT_MANIFEST_GLOBAL_NAME = "report_manifest";
  const OVERLAY_BACKGROUND_COLOR = "#14171c";
  const OVERLAY_TEXT_COLOR = "#f2f4f6";
  const OVERLAY_LINK_COLOR = "#ff4427";
  const OVERLAY_FONT = "12px/1.5 Monaco, monospace";
  const OVERLAY_PADDING = "24px 36px 48px";
  const ROOT_INDEX_NAME = "index.html";
  const CONTROL_GAP = "18px";
  const OVERLAY_TABLE_TOTAL_CHARS = 120;

  let overlay_is_shown = false;

  function address_shorten(text, root_prefix) {
    if (!root_prefix) {
      return String(text);
    }
    return String(text).replace(/file:\/\/\S*/g, function (found) {
      return prefix_drop(found, root_prefix);
    });
  }

  function control_add(parent, label, action) {
    const link = document.createElement("a");
    link.textContent = label;
    link.style.color = OVERLAY_LINK_COLOR;
    link.style.textDecoration = "underline";
    link.style.cursor = "pointer";
    link.style.marginRight = CONTROL_GAP;
    link.addEventListener("click", function (click_event) {
      click_event.preventDefault();
      action();
    });
    parent.appendChild(link);
    return link;
  }

  function controls_build(document_text) {
    const bar = document.createElement("div");
    bar.style.marginTop = CONTROL_GAP;
    control_add(bar, text_of_or_id("str_error_control_copy"), function () {
      text_copy(document_text);
    });
    control_add(bar, text_of_or_id("str_error_control_reload"), function () {
      location.reload();
    });
    control_add(bar, text_of_or_id("str_error_control_restart"), function () {
      location.href = root_prefix_of() + ROOT_INDEX_NAME;
    });
    return bar;
  }

  function document_build(report) {
    const root_prefix = root_prefix_of();
    const lines = [
      "# " + text_of_or_id("str_error_page_heading"),
      "",
      String(report.source_label || ""),
      "",
      format_or_raw(report.message),
      "",
      "## " + text_of_or_id("str_error_heading_address"),
      "",
      address_shorten(report.address, root_prefix),
      "",
      "## " + text_of_or_id("str_error_heading_callstack"),
      "",
      stack_table(report.stack, root_prefix),
      "",
      "## " + text_of_or_id("str_error_heading_manifest"),
      "",
      manifest_table(report.manifest),
      "",
    ];
    return lines.join("\n");
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
    window.addEventListener("error", function (browser_event) {
      if (browser_event.error || browser_event.message) {
        overlay_show(
          browser_event.error || browser_event.message,
          text_of_or_id("str_error_source_exception"),
        );
      }
    });
    window.addEventListener("unhandledrejection", function (browser_event) {
      overlay_show(
        browser_event.reason,
        text_of_or_id("str_error_source_rejection"),
      );
    });
    window.addEventListener("message", function (browser_event) {
      const payload = browser_event.data;
      if (!payload || payload.report_ui !== OVERLAY_MESSAGE_NAME) {
        return;
      }
      report_render(payload.report);
    });
  }

  function manifest_table(manifest_text) {
    const text = String(manifest_text || "");
    const rows = [];
    for (const line of text.split("\n")) {
      if (!line.trim()) {
        continue;
      }
      const cut = line.indexOf("=");
      if (cut < 0) {
        rows.push([line.trim()]);
      } else {
        rows.push([line.slice(0, cut).trim(), line.slice(cut + 1).trim()]);
      }
    }
    if (!rows.length) {
      return text_of_or_id("str_error_manifest_unavailable");
    }
    return table_render(
      [
        text_of_or_id("str_error_column_label"),
        text_of_or_id("str_error_column_value"),
      ],
      rows,
    );
  }

  function manifest_text() {
    const shipped = window[REPORT_MANIFEST_GLOBAL_NAME];
    if (typeof shipped === "string" && shipped) {
      return shipped;
    }
    return "";
  }

  function overlay_build(report) {
    const document_text = document_build(report);
    const root = document.createElement("div");
    root.id = OVERLAY_ROOT_ID;
    root.style.background = OVERLAY_BACKGROUND_COLOR;
    root.style.color = OVERLAY_TEXT_COLOR;
    root.style.font = OVERLAY_FONT;
    root.style.padding = OVERLAY_PADDING;
    const block = document.createElement("pre");
    block.style.font = "inherit";
    block.style.margin = "0";
    block.style.whiteSpace = "pre-wrap";
    block.style.overflowX = "auto";
    block.textContent = document_text;
    root.appendChild(block);
    root.appendChild(controls_build(document_text));
    return root;
  }

  function overlay_show(reason, source_label) {
    if (overlay_is_shown) {
      return;
    }
    const described = error_describe(reason);
    report_render({
      address: location.href,
      manifest: manifest_text(),
      message: described.message,
      source_label: source_label,
      stack: described.stack,
    });
  }

  function report_render(report) {
    if (overlay_is_shown) {
      return;
    }
    overlay_is_shown = true;
    try {
      if (window.parent !== window) {
        window.parent.postMessage(
          { report_ui: OVERLAY_MESSAGE_NAME, report: report },
          "*",
        );
        return;
      }
      const root = overlay_build(report);
      document.body.textContent = "";
      document.body.style.margin = "0";
      document.body.style.background = OVERLAY_BACKGROUND_COLOR;
      document.body.style.color = OVERLAY_TEXT_COLOR;
      document.body.appendChild(root);
      document.title = text_of_or_id("str_error_page_title");
    } catch (ignored) {
      overlay_is_shown = true;
    }
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

  function root_prefix_of() {
    const here = String(location.href).split("#")[0].split("?")[0];
    const cut = here.lastIndexOf("/");
    return cut < 0 ? "" : here.slice(0, cut + 1);
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
    return [text];
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
    const all_rows = [titles].concat(rows);
    const widths = column_widths(
      column_longest(all_rows, 0),
      column_longest(all_rows, 1),
    );
    const written = [row_text(titles, widths), rule_text(widths)];
    for (const row of rows) {
      written.push(row_text(row, widths));
    }
    return written.join("\n");
  }

  function column_longest(rows, index) {
    let longest = 0;
    for (const row of rows) {
      longest = Math.max(longest, String(row[index] || "").length);
    }
    return longest;
  }

  function column_widths(longest_a, longest_b) {
    const sum = longest_a + longest_b;
    let width_a = longest_a;
    if (sum > OVERLAY_TABLE_TOTAL_CHARS) {
      width_a = Math.floor((OVERLAY_TABLE_TOTAL_CHARS * longest_a) / sum);
    }
    const width_b = Math.min(longest_b, OVERLAY_TABLE_TOTAL_CHARS - width_a);
    return [width_a, width_b];
  }

  function row_text(cells, widths) {
    const rest = cells.length > 1 ? cells[1] : "";
    return (
      "| " +
      cell_fit(cells[0], widths[0]) +
      " | " +
      cell_fit(rest, widths[1]) +
      " |"
    );
  }

  function rule_text(widths) {
    return row_text(["-".repeat(widths[0]), "-".repeat(widths[1])], widths);
  }

  function cell_fit(text, width) {
    const cell = String(text || "");
    if (cell.length > width) {
      return cell.slice(cell.length - width);
    }
    return cell + " ".repeat(width - cell.length);
  }

  function text_copy(text) {
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text);
        return;
      }
    } catch (ignored) {
      void ignored;
    }
    const holder = document.createElement("textarea");
    holder.value = text;
    document.body.appendChild(holder);
    holder.select();
    try {
      document.execCommand("copy");
    } catch (ignored) {
      void ignored;
    }
    document.body.removeChild(holder);
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

  handler_install();
  return { overlay_show };
})();
