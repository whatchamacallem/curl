// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.report_error_overlay_ = (function () {
  "use strict";

  const REPORT_MANIFEST_TABLE_GLOBAL_NAME = "report_manifest_table_";
  const OVERLAY_BACKGROUND_COLOR = "#14171c";
  const OVERLAY_TEXT_COLOR = "#f2f4f6";
  const OVERLAY_LINK_COLOR = "#ff4427";
  const OVERLAY_TITLE_TEXT = "perf2html error";
  const OVERLAY_COPY_LINK_TEXT = "copy";
  const OVERLAY_BACK_LINK_TEXT = "back";
  const OVERLAY_NO_MANIFEST_TEXT = "Report has no assets/debug.js";
  const DESIGN_COORDINATES_WIDTH_PX = 1920;
  const DESIGN_FONT_SIZE_PX = 24;
  const REPORT_ROOT_URL = new URL("..", document.currentScript.src).href;

  let shown = false;
  let report_relay = null;

  function html_escape_(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function error_text_of_(thrown_value) {
    if (!(thrown_value instanceof Error)) return String(thrown_value);
    const error_text =
      thrown_value.stack ?? `${thrown_value.name}: ${thrown_value.message}`;
    if (thrown_value.cause !== undefined)
      return `${error_text}\n${error_text_of_(thrown_value.cause)}`;
    return error_text;
  }

  function report_relative_(shown_text) {
    return shown_text.replaceAll(REPORT_ROOT_URL, "");
  }

  function page_address_() {
    return report_relative_(location.href.split(/[?#]/)[0] + location.hash);
  }

  function link_render_(script_text, link_text) {
    const link_href = "javascript:" + encodeURIComponent(script_text);
    return (
      `<a style="color:${OVERLAY_LINK_COLOR}" ` +
      `href="${html_escape_(link_href)}">${html_escape_(link_text)}</a>`
    );
  }

  function try_catch_handler_(entry_function) {
    return function (...entry_arguments) {
      try {
        const entry_result = entry_function.apply(this, entry_arguments);
        if (!(entry_result instanceof Promise)) return entry_result;
        return entry_result.catch(function (rejection_reason) {
          err_overlay_show_(rejection_reason);
          throw rejection_reason;
        });
      } catch (thrown_value) {
        err_overlay_show_(thrown_value);
        throw thrown_value;
      }
    };
  }

  // Throws the filled UI string or its id, a trailing Error value its cause.
  function throw_exception_(string_id, ...fill_values) {
    const error_options =
      fill_values.at(-1) instanceof Error
        ? { cause: fill_values.pop() }
        : undefined;
    if (window.ui_strings_ === undefined)
      throw new Error(
        "error (and missing ui string): " + string_id,
        error_options,
      );
    throw new Error(
      window.ui_strings_.text_fill(string_id, fill_values),
      error_options,
    );
  }

  function err_overlay_show_(thrown_value) {
    const error_text = report_relative_(error_text_of_(thrown_value));
    report_render_({ page: page_address_(), text: error_text }, false);
  }

  function report_render_(report, is_relayed) {
    if (shown) return;
    shown = true;
    if (report_relay !== null && report_relay(report)) return;
    setTimeout(page_write_, 0, report, is_relayed);
  }

  function relay_set_(relay_function) {
    report_relay = relay_function;
  }

  function relayed_report_show_(report) {
    report_render_(report, true);
  }

  function page_write_(report, is_relayed) {
    const manifest_text =
      typeof window[REPORT_MANIFEST_TABLE_GLOBAL_NAME] === "undefined"
        ? OVERLAY_NO_MANIFEST_TEXT
        : window[REPORT_MANIFEST_TABLE_GLOBAL_NAME];
    const place_lines = [`address  ${page_address_()}`];
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
      `${link_render_(copy_script, OVERLAY_COPY_LINK_TEXT)} | ` +
      `${link_render_("history.back()", OVERLAY_BACK_LINK_TEXT)}`;
    document.open();
    document.write(
      "<!doctype html>\n" +
        '<html><head><meta charset="utf-8">' +
        `<title>${html_escape_(OVERLAY_TITLE_TEXT)}</title></head>` +
        `<body style="${page_style}"><pre style="${block_style}">` +
        `${html_escape_(copy_text)}\n\n${links_line}</pre></body></html>`,
    );
    document.close();
    const address_reload_ = () => location.reload();
    window.addEventListener("hashchange", address_reload_);
    window.addEventListener("popstate", address_reload_);
  }

  window.addEventListener("error", function (browser_event) {
    err_overlay_show_(browser_event.error || browser_event.message);
  });
  window.addEventListener("unhandledrejection", function (browser_event) {
    err_overlay_show_(browser_event.reason);
  });

  window.throw_exception_ = throw_exception_;
  window.try_catch_handler_ = try_catch_handler_;
  return { err_overlay_show_, relay_set_, relayed_report_show_ };
})();
