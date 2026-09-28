window.report_error_overlay = (function () {
  "use strict";

  const OVERLAY_MESSAGE_NAME = "report_error";
  const REPORT_MANIFEST_TABLE_GLOBAL_NAME = "report_manifest_table";
  const OVERLAY_BACKGROUND_COLOR = "#14171c";
  const OVERLAY_TEXT_COLOR = "#f2f4f6";
  const OVERLAY_LINK_COLOR = "#ff4427";
  const OVERLAY_COPY_LINK_TEXT = "copy";
  const OVERLAY_BACK_LINK_TEXT = "back";
  const OVERLAY_NO_MANIFEST_TEXT = "Report has no manifest";
  const DESIGN_COORDINATES_WIDTH_PX = 1920;
  const DESIGN_FONT_SIZE_PX = 16;
  const CALLSTACK_TABLE_LINE_CHARS = 79;
  const CALLSTACK_TABLE_FRAME_CHARS = 7;
  const CALLSTACK_LOCATION_COLUMN_SHARE = 1 / 3;

  let shown = false;

  function html_escape(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  function line_wrap(text, width) {
    const lines = [];
    for (let start = 0; start < text.length || !lines.length;) {
      lines.push(text.slice(start, start + width));
      start += width;
    }
    return lines.join("\n");
  }

  function callstack_row(line) {
    const bare = line.trim().replace(/^at\s+/, "");
    const braced = /^(.*?)\s*\((.*)\)$/.exec(bare);
    return braced ? [braced[2], braced[1]] : [bare, ""];
  }

  function callstack_table_row(location, function_name, widths) {
    const cells = [location, function_name].map(function (text, column) {
      const width = widths[column];
      const lines = [];
      for (let start = 0; start < text.length || !lines.length;) {
        lines.push(text.slice(start, start + width).padEnd(width));
        start += width;
      }
      return lines;
    });
    const row_lines = [];
    const line_count = Math.max(cells[0].length, cells[1].length);
    for (let index = 0; index < line_count; index += 1) {
      row_lines.push(
        `| ${cells[0][index] || " ".repeat(widths[0])} | ` +
          `${cells[1][index] || " ".repeat(widths[1])} |`,
      );
    }
    return row_lines.join("\n");
  }

  function callstack_table(stack_text) {
    const rows = String(stack_text || "")
      .split("\n")
      .filter((line) => line.trim())
      .map(callstack_row);
    if (!rows.length) return "";
    const budget = CALLSTACK_TABLE_LINE_CHARS - CALLSTACK_TABLE_FRAME_CHARS;
    const headings = ["Location", "Function"];
    const natural = [0, 1].map((column) =>
      Math.max(
        headings[column].length,
        ...rows.map((row) => row[column].length),
      ),
    );
    let widths = natural;
    if (natural[0] + natural[1] > budget) {
      const location_width = Math.min(
        natural[0],
        Math.floor(budget * CALLSTACK_LOCATION_COLUMN_SHARE),
      );
      widths = [location_width, budget - location_width];
    }
    const header = [
      callstack_table_row("Location", "Function", widths),
      callstack_table_row("-".repeat(widths[0]), "-".repeat(widths[1]), [
        widths[0],
        widths[1],
      ]),
    ];
    const body = rows.map((row) =>
      callstack_table_row(row[0], row[1], widths),
    );
    return header.concat(body).join("\n");
  }

  function overlay_show(reason) {
    report_render({
      address: location.href,
      message: String((reason && reason.message) || reason),
      stack: String((reason && reason.stack) || ""),
    });
  }

  function report_render(report) {
    if (shown) return;
    shown = true;
    if (window.parent !== window) {
      window.parent.postMessage(
        { report_ui: OVERLAY_MESSAGE_NAME, report: report },
        "*",
      );
      return;
    }
    setTimeout(page_write, 0, report);
  }

  function page_write(report) {
    const callstack_text = callstack_table(report.stack);
    const manifest_text =
      typeof window[REPORT_MANIFEST_TABLE_GLOBAL_NAME] === "undefined"
        ? OVERLAY_NO_MANIFEST_TEXT
        : window[REPORT_MANIFEST_TABLE_GLOBAL_NAME];
    const copy_text = `# perf2html error

${report.message}

${line_wrap(report.address, CALLSTACK_TABLE_LINE_CHARS)}

## Callstack

${callstack_text}

## Manifest

${manifest_text}`;
    const font_size =
      Math.round(
        (DESIGN_FONT_SIZE_PX * window.innerWidth) /
          DESIGN_COORDINATES_WIDTH_PX,
      ) + "px";
    const page_style =
      `margin:0;background:${OVERLAY_BACKGROUND_COLOR};` +
      `color:${OVERLAY_TEXT_COLOR};font:${font_size}/1.5 Monaco, monospace;` +
      `min-height:100vh;display:flex;align-items:center;` +
      `justify-content:center`;
    const block_style =
      "font:inherit;white-space:pre-wrap;overflow-wrap:anywhere";
    const link_style = "color:" + OVERLAY_LINK_COLOR;
    const copy_call =
      `navigator.clipboard.writeText(` + `${JSON.stringify(copy_text)})`;
    const link = (href, text) =>
      `<a style="${link_style}" href="javascript:${href}">${text}</a>`;
    const links_line =
      `${link(html_escape(copy_call), OVERLAY_COPY_LINK_TEXT)} | ` +
      `${link("history.back()", OVERLAY_BACK_LINK_TEXT)}`;
    const body = `${copy_text}

${links_line}`;
    document.open();
    // APPROVED USAGE. Error handlers are what this is for.
    document.write(`<!doctype html>
<title>perf2html error</title>
<body style="${page_style}"><pre style="${block_style}">${body}</pre>`);
    document.close();
  }

  window.addEventListener("error", function (browser_event) {
    overlay_show(browser_event.error || browser_event.message);
  });
  window.addEventListener("unhandledrejection", function (browser_event) {
    overlay_show(browser_event.reason);
  });
  window.addEventListener("message", function (browser_event) {
    const payload = browser_event.data;
    if (payload && payload.report_ui === OVERLAY_MESSAGE_NAME) {
      report_render(payload.report);
    }
  });

  return { overlay_show };
})();
