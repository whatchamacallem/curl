window.report_error_overlay = (function () {
  "use strict";

  const OVERLAY_HASH_MARKER = "#report-error";
  const OVERLAY_ROOT_ID = "reportErrorOverlay";
  const OVERLAY_STYLE_ID = "reportErrorOverlayStyle";
  const OVERLAY_STYLE_TEXT = [
    "html:has(#" + OVERLAY_ROOT_ID + ") {",
    "  overflow: auto;",
    "}",
    "body.report-error-shown {",
    "  overflow: auto;",
    "  height: auto;",
    "  margin: 0;",
    "  display: block;",
    "  background: var(--bg, #14171c);",
    "  color: var(--fg, #d6dae0);",
    "  font: 12px/1.5 var(--font, Monaco, monospace);",
    "}",
    "#" + OVERLAY_ROOT_ID + " {",
    "  padding: 24px 36px 48px;",
    "  background: var(--bg, #14171c);",
    "  color: var(--fg, #d6dae0);",
    "  font: 12px/1.5 var(--font, Monaco, monospace);",
    "}",
    "#" + OVERLAY_ROOT_ID + " .report-error-title {",
    "  font-size: 13px;",
    "  font-weight: 600;",
    "  color: var(--title-fg, #14171c);",
    "  background: var(--title-bg, #4ea1a6);",
    "  padding: 3px 8px;",
    "  margin: 0 0 14px;",
    "  display: inline-block;",
    "}",
    "#" + OVERLAY_ROOT_ID + " h2 {",
    "  font-size: 12px;",
    "  font-weight: 600;",
    "  color: var(--fg-dim, #9aa3ad);",
    "  margin: 22px 0 6px;",
    "}",
    "#" + OVERLAY_ROOT_ID + " p {",
    "  margin: 4px 0;",
    "  color: var(--muted, #79828d);",
    "  max-width: 96ch;",
    "}",
    "#" + OVERLAY_ROOT_ID + " pre {",
    "  font: inherit;",
    "  margin: 0;",
    "  padding: 8px 12px;",
    "  background: var(--panel, #1b1f26);",
    "  color: var(--fg, #d6dae0);",
    "  white-space: pre-wrap;",
    "  word-break: break-all;",
    "  overflow-x: auto;",
    "  max-height: 40vh;",
    "}",
    "#" + OVERLAY_ROOT_ID + " pre.report-error-message {",
    "  color: var(--hot, #d95f4b);",
    "}",
  ].join("\n");
  const REPORT_MANIFEST_GLOBAL_NAME = "report_manifest";
  const RESTORE_HASH_STORAGE_KEY = "error.restore-hash";

  let overlay_is_shown = false;
  let restore_hash = "";

  function element_append(parent, tag_name, class_name, text) {
    const element = document.createElement(tag_name);
    if (class_name) {
      element.className = class_name;
    }
    if (text !== undefined) {
      element.textContent = text;
    }
    parent.appendChild(element);
    return element;
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

  function handler_install() {
    window.addEventListener("error", function (browser_event) {
      if (browser_event.error || browser_event.message) {
        overlay_show(
          browser_event.error || browser_event.message,
          text_or_fallback("str_error_source_exception", "uncaught exception"),
        );
      }
    });
    window.addEventListener("unhandledrejection", function (browser_event) {
      overlay_show(
        browser_event.reason,
        text_or_fallback(
          "str_error_source_rejection",
          "unhandled promise rejection",
        ),
      );
    });
    window.addEventListener("popstate", function () {
      if (overlay_is_shown && location.hash !== OVERLAY_HASH_MARKER) {
        page_restore();
      }
    });
  }

  function manifest_text() {
    const shipped = window[REPORT_MANIFEST_GLOBAL_NAME];
    if (typeof shipped === "string" && shipped) {
      return shipped;
    }
    return "";
  }

  function overlay_build(described, source_label) {
    const root = document.createElement("div");
    root.id = OVERLAY_ROOT_ID;
    element_append(
      root,
      "div",
      "report-error-title",
      text_or_fallback("str_error_page_title", "report page error"),
    );
    element_append(
      root,
      "p",
      "",
      text_or_fallback(
        "str_error_page_explanation",
        "This page stopped because of an error it could not recover" +
          " from. Press Back to reload it at the address it was showing.",
      ),
    );
    element_append(
      root,
      "h2",
      "",
      text_or_fallback("str_error_heading_message", "message") +
        " (" +
        source_label +
        ")",
    );
    element_append(root, "pre", "report-error-message", described.message);
    element_append(
      root,
      "h2",
      "",
      text_or_fallback("str_error_heading_address", "page address"),
    );
    element_append(root, "pre", "", restore_hash || location.href);
    element_append(
      root,
      "h2",
      "",
      text_or_fallback("str_error_heading_callstack", "callstack"),
    );
    element_append(
      root,
      "pre",
      "",
      described.stack ||
        text_or_fallback(
          "str_error_callstack_unavailable",
          "(no callstack recorded)",
        ),
    );
    element_append(
      root,
      "h2",
      "",
      text_or_fallback("str_error_heading_manifest", "report manifest"),
    );
    element_append(
      root,
      "pre",
      "",
      manifest_text() ||
        text_or_fallback(
          "str_error_manifest_unavailable",
          "(this report ships no manifest script, so its MANIFEST.txt" +
            " cannot be read from a file:// page)",
        ),
    );
    return root;
  }

  function overlay_show(reason, source_label) {
    if (overlay_is_shown) {
      return;
    }
    overlay_is_shown = true;
    try {
      restore_hash = location.href;
      restore_hash_store(restore_hash);
      if (location.hash !== OVERLAY_HASH_MARKER) {
        history.pushState(null, "", OVERLAY_HASH_MARKER);
      }
      const described = error_describe(reason);
      const root = overlay_build(described, source_label);
      style_install();
      document.body.textContent = "";
      document.body.className = "report-error-shown";
      document.body.appendChild(root);
      document.title = text_or_fallback(
        "str_error_page_title",
        "report page error",
      );
    } catch (ignored) {
      overlay_is_shown = true;
    }
  }

  function page_restore() {
    const target = restore_hash || restore_hash_read();
    overlay_is_shown = false;
    if (target) {
      location.replace(target);
    } else {
      location.reload();
    }
  }

  function restore_hash_read() {
    try {
      return sessionStorage.getItem(RESTORE_HASH_STORAGE_KEY) || "";
    } catch (ignored) {
      return "";
    }
  }

  function restore_hash_store(href) {
    try {
      sessionStorage.setItem(RESTORE_HASH_STORAGE_KEY, href);
    } catch (ignored) {
      return;
    }
  }

  function style_install() {
    if (document.getElementById(OVERLAY_STYLE_ID)) {
      return;
    }
    const style = document.createElement("style");
    style.id = OVERLAY_STYLE_ID;
    style.textContent = OVERLAY_STYLE_TEXT;
    (document.head || document.documentElement).appendChild(style);
  }

  function text_or_fallback(string_id, fallback) {
    const strings = window.ui_strings;
    if (!strings || typeof strings.text_of !== "function") {
      return fallback;
    }
    try {
      return strings.text_of(string_id);
    } catch (ignored) {
      return fallback;
    }
  }

  handler_install();
  return { overlay_show };
})();
