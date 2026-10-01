window.report_error_overlay = (function () {
  "use strict";

  const OVERLAY_MESSAGE_NAME = "report_error";
  const REPORT_MANIFEST_TABLE_GLOBAL_NAME = "report_manifest_table";
  const OVERLAY_BACKGROUND_COLOR = "#14171c";
  const OVERLAY_TEXT_COLOR = "#f2f4f6";
  const OVERLAY_LINK_COLOR = "#ff4427";
  const OVERLAY_TITLE_TEXT = "perf2html error";
  const OVERLAY_COPY_LINK_TEXT = "copy";
  const OVERLAY_BACK_LINK_TEXT = "back";
  const OVERLAY_NO_MANIFEST_TEXT = "Report has no assets/report_complete.js";
  const DESIGN_COORDINATES_WIDTH_PX = 1920;
  const DESIGN_FONT_SIZE_PX = 24;
  // The report's root URL, the directory above the assets/ holding this
  // script. Cut from every text shown, it leaves report-relative paths.
  const REPORT_ROOT_URL = new URL("..", document.currentScript.src).href;

  let shown = false;

  function html_escape(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // An Error as its stack, or its name and message, then its cause's text
  // below it; any other value as a string. Run in the realm that caught it.
  function error_text_of(thrown_value) {
    if (!(thrown_value instanceof Error)) return String(thrown_value);
    const error_text =
      thrown_value.stack ?? `${thrown_value.name}: ${thrown_value.message}`;
    if (thrown_value.cause !== undefined)
      return `${error_text}\n${error_text_of(thrown_value.cause)}`;
    return error_text;
  }

  function report_relative(shown_text) {
    return shown_text.replaceAll(REPORT_ROOT_URL, "");
  }

  // This page's address inside the report: its path under the root, then
  // its hash, the query left out.
  function page_address() {
    return report_relative(location.href.split(/[?#]/)[0] + location.hash);
  }

  // One link running a script. A javascript: URL is percent-decoded before
  // it runs, so the script goes in percent-encoded and runs as written.
  function link_render(script_text, link_text) {
    const link_href = "javascript:" + encodeURIComponent(script_text);
    return (
      `<a style="color:${OVERLAY_LINK_COLOR}" ` +
      `href="${html_escape(link_href)}">${html_escape(link_text)}</a>`
    );
  }

  // Wrap an entry point so its error reaches the overlay as the Error: a
  // file:// page sees another file's as "Script error.". Then rethrow.
  function catch_show_throw(entry_function) {
    return function (...entry_arguments) {
      try {
        const entry_result = entry_function.apply(this, entry_arguments);
        if (!(entry_result instanceof Promise)) return entry_result;
        return entry_result.catch(function (rejection_reason) {
          err_overlay_show(rejection_reason);
          throw rejection_reason;
        });
      } catch (thrown_value) {
        err_overlay_show(thrown_value);
        throw thrown_value;
      }
    };
  }

  // The door every error takes, its text made in the realm that caught it.
  function err_overlay_show(thrown_value) {
    const error_text = report_relative(error_text_of(thrown_value));
    report_render({ page: page_address(), text: error_text }, false);
  }

  // The first report of a load wins: a framed page posts it up as text, the
  // top writes it over itself one task later.
  function report_render(report, is_relayed) {
    if (shown) return;
    shown = true;
    if (window.parent !== window) {
      window.parent.postMessage(
        { report_ui: OVERLAY_MESSAGE_NAME, report: report },
        "*",
      );
      return;
    }
    setTimeout(page_write, 0, report, is_relayed);
  }

  // The top's address as it is now, the thrower's page when a frame posted
  // the report, its text, then the manifest.
  function page_write(report, is_relayed) {
    const manifest_text =
      typeof window[REPORT_MANIFEST_TABLE_GLOBAL_NAME] === "undefined"
        ? OVERLAY_NO_MANIFEST_TEXT
        : window[REPORT_MANIFEST_TABLE_GLOBAL_NAME];
    const place_lines = [`address  ${page_address()}`];
    if (is_relayed) place_lines.push(`page     ${report.page}`);
    const copy_text = [
      OVERLAY_TITLE_TEXT,
      "",
      ...place_lines,
      "",
      report.text,
      "",
      "manifest",
      manifest_text,
    ].join("\n");
    const font_size =
      Math.round(
        (DESIGN_FONT_SIZE_PX * window.innerWidth) /
          DESIGN_COORDINATES_WIDTH_PX,
      ) + "px";
    const page_style =
      `margin:0;background:${OVERLAY_BACKGROUND_COLOR};` +
      `color:${OVERLAY_TEXT_COLOR};font:${font_size}/1.1 Monaco, monospace;` +
      `min-height:100vh;display:flex;align-items:center;` +
      `justify-content:safe center`;
    const block_style = "font:inherit;white-space:pre";
    const copy_script =
      "navigator.clipboard.writeText(" + JSON.stringify(copy_text) + ")";
    const links_line =
      `${link_render(copy_script, OVERLAY_COPY_LINK_TEXT)} | ` +
      `${link_render("history.back()", OVERLAY_BACK_LINK_TEXT)}`;
    document.open();
    // APPROVED USAGE. Error handlers are what this is for.
    document.write(
      "<!doctype html>\n" +
        '<html><head><meta charset="utf-8">' +
        `<title>${html_escape(OVERLAY_TITLE_TEXT)}</title></head>` +
        `<body style="${page_style}"><pre style="${block_style}">` +
        `${html_escape(copy_text)}\n\n${links_line}</pre></body></html>`,
    );
    document.close();
    // document.open() dropped every listener: an address typed, or reached
    // by back, reloads the page into it.
    const address_reload = () => location.reload();
    window.addEventListener("hashchange", address_reload);
    window.addEventListener("popstate", address_reload);
  }

  window.addEventListener("error", function (browser_event) {
    err_overlay_show(browser_event.error || browser_event.message);
  });
  window.addEventListener("unhandledrejection", function (browser_event) {
    err_overlay_show(browser_event.reason);
  });
  window.addEventListener("message", function (browser_event) {
    const payload = browser_event.data;
    if (payload && payload.report_ui === OVERLAY_MESSAGE_NAME) {
      report_render(payload.report, true);
    }
  });

  window.catch_show_throw = catch_show_throw;
  return { err_overlay_show };
})();
