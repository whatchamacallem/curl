// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.catch_show_throw_(function () {
  "use strict";

  const RELAY_MESSAGE_NAME = "report_error";
  const RESOURCE_FAILURE_TEXT = "resource failed: ";
  const RESOURCE_TAG_NAMES = ["LINK", "SCRIPT", "IMG"];
  const report_error_overlay = window.report_error_overlay_;
  const expected_failure_sources = new Set();

  function report_relay_(report) {
    if (window.parent === window) return false;
    window.parent.postMessage(
      { report_ui: RELAY_MESSAGE_NAME, report: report },
      "*",
    );
    return true;
  }

  function relayed_report_take_(browser_event) {
    const payload = browser_event.data;
    if (payload && payload.report_ui === RELAY_MESSAGE_NAME)
      report_error_overlay.relayed_report_show_(payload.report);
  }

  function resource_failure_expect_(source) {
    expected_failure_sources.add(source);
  }

  function resource_failure_take_(browser_event) {
    const target = browser_event.target;
    if (
      target &&
      target !== window &&
      RESOURCE_TAG_NAMES.includes(target.tagName) &&
      !expected_failure_sources.has(target.href || target.src)
    )
      report_error_overlay.err_overlay_show_(
        new Error(RESOURCE_FAILURE_TEXT + (target.href || target.src)),
      );
  }

  window.resource_failure_expect_ = resource_failure_expect_;
  report_error_overlay.relay_set_(report_relay_);
  window.addEventListener(
    "message",
    window.catch_show_throw_(relayed_report_take_),
  );
  window.addEventListener(
    "error",
    window.catch_show_throw_(resource_failure_take_),
    true,
  );
})();
