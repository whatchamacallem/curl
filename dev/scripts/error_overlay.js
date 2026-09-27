window.report_error_overlay = (function () {
  "use strict";

  const OVERLAY_MESSAGE_NAME = "report_error";
  const REPORT_MANIFEST_TABLE_GLOBAL_NAME = "report_manifest_table";
  const OVERLAY_BACKGROUND_COLOR = "#14171c";
  const OVERLAY_TEXT_COLOR = "#f2f4f6";
  const OVERLAY_LINK_COLOR = "#ff4427";
  const OVERLAY_PAGE_TITLE_TEXT = "perf2html error";
  const OVERLAY_COPY_LINK_TEXT = "copy";
  const OVERLAY_BACK_LINK_TEXT = "back";
  const OVERLAY_NO_MANIFEST_TEXT = "Report has no manifest.";
  // the design font size at DESIGN_COORDINATES_WIDTH_PX, scaled once in
  // page_write to the window it draws on: no resize listener, no restyle
  const DESIGN_COORDINATES_WIDTH_PX = 1920;
  const DESIGN_FONT_SIZE_PX = 16;

  let shown = false;

  // Make text safe inside the page's <pre> and its one quoted attribute:
  // the three characters markup or a quoted attribute reads specially.
  function html_escape(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/"/g, "&quot;");
  }

  // {address, message, stack} from an Error, a DOM event's message, or
  // anything else a listener handed us, so report_render always gets one.
  function overlay_show(reason) {
    report_render({
      address: location.href,
      message: String((reason && reason.message) || reason),
      stack: String((reason && reason.stack) || ""),
    });
  }

  // Replace the document with the error page, once. A file:// iframe is an
  // opaque origin, so posting the detail up is how it reaches the top.
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
    // document.open() mid-parse is a no-op per spec, so the write waits one
    // task: by then the parser has nothing left to detach
    setTimeout(page_write, 0, report);
  }

  function page_write(report) {
    const manifest_text =
      typeof window[REPORT_MANIFEST_TABLE_GLOBAL_NAME] === "undefined"
        ? OVERLAY_NO_MANIFEST_TEXT
        : window[REPORT_MANIFEST_TABLE_GLOBAL_NAME];
    const copy_text = [
      report.message,
      "",
      report.address,
      "",
      report.stack,
      "",
      manifest_text,
    ].join("\n");
    const font_size =
      Math.round(
        (DESIGN_FONT_SIZE_PX * window.innerWidth) /
          DESIGN_COORDINATES_WIDTH_PX,
      ) + "px";
    const page_style =
      `margin:0;background:${OVERLAY_BACKGROUND_COLOR};` +
      `color:${OVERLAY_TEXT_COLOR};font:${font_size}/1.5 Monaco, monospace`;
    const block_style =
      "font:inherit;white-space:pre-wrap;overflow-wrap:anywhere";
    const link_style = "color:" + OVERLAY_LINK_COLOR;
    const copy_call =
      `navigator.clipboard.writeText(` + `${JSON.stringify(copy_text)})`;
    const link = (href, text) =>
      `<a style="${link_style}" href="javascript:${href}">${text}</a>`;
    const body = [
      html_escape(report.message),
      "",
      html_escape(report.address),
      "",
      html_escape(report.stack),
      "",
      html_escape(manifest_text),
      "",
      link(html_escape(copy_call), OVERLAY_COPY_LINK_TEXT) +
        " | " +
        link("history.back()", OVERLAY_BACK_LINK_TEXT),
    ].join("\n");
    document.open();
    document.write(`<!doctype html>
<title>${OVERLAY_PAGE_TITLE_TEXT}</title>
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
