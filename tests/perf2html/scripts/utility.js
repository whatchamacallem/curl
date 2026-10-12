// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const INPUT_EVENT_NAMES = ["click", "keydown"];
  const LOAD_LOG_MESSAGE_NAME = "load_log_entry";
  const NAVIGATION_CAUSE_NAME = "navigation";
  const RELAY_MESSAGE_NAME = "report_error";
  const RESOURCE_FAILURE_TEXT = "resource failed: ";
  const RESOURCE_TAG_NAMES = ["LINK", "SCRIPT", "IMG"];
  const is_framed =
    window.parent !== window &&
    !document.documentElement.hasAttribute("data-top-page-");
  const report_error_overlay = window.report_error_overlay_;
  const expected_failure_sources = new Set();
  const load_log_entries = [];
  const long_frame_observer = new PerformanceObserver(
    window.try_catch_handler_((entry_list) =>
      long_frames_take(entry_list.getEntries()),
    ),
  );
  let load_log_kept_line_count = null;
  let page_render_is_logged = false;
  let parsed_asset_count = 0;
  let pending_assets = null;
  let pending_render = null;

  function report_relay(report) {
    if (!is_framed) return false;
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
    else if (payload && payload.report_ui === LOAD_LOG_MESSAGE_NAME)
      load_log_entry_add(payload.entry);
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

  // Drops the earliest history entries past the count the top page keeps.
  function load_log_trim() {
    if (load_log_kept_line_count === null) return;
    load_log_entries.splice(
      0,
      Math.max(load_log_entries.length - load_log_kept_line_count, 0),
    );
  }
  // Keeps an entry in time order on the top page, a framed page posting it up.
  function load_log_entry_add(log_entry) {
    if (is_framed) {
      window.parent.postMessage(
        { report_ui: LOAD_LOG_MESSAGE_NAME, entry: log_entry },
        "*",
      );
      return;
    }
    const [entry_kind, origin_milliseconds, ...entry_fields] = log_entry;
    const log_milliseconds = origin_milliseconds - performance.timeOrigin;
    let entry_index = load_log_entries.length;
    while (
      entry_index > 0 &&
      load_log_entries[entry_index - 1][1] > log_milliseconds
    )
      entry_index--;
    load_log_entries.splice(entry_index, 0, [
      entry_kind,
      log_milliseconds,
      ...entry_fields,
    ]);
    load_log_trim();
  }
  // Logs an entry on the shared clock, the time origin plus the page's time.
  function load_log_append(entry_kind, page_milliseconds, entry_fields) {
    load_log_entry_add([
      entry_kind,
      performance.timeOrigin + page_milliseconds,
      location.href,
      ...entry_fields,
    ]);
  }
  function load_log_kept_line_count_set(line_count) {
    load_log_kept_line_count = line_count;
    load_log_trim();
  }
  // Answers the newest entries kept, up to the count asked for.
  function load_log_newest_entries_of(line_count) {
    return load_log_entries.slice(
      Math.max(load_log_entries.length - line_count, 0),
    );
  }

  // Runs the callback in a task after the paint of the next animation frame.
  function after_paint_run(paint_callback) {
    requestAnimationFrame(
      window.try_catch_handler_(() =>
        setTimeout(window.try_catch_handler_(paint_callback)),
      ),
    );
  }
  // Logs a render from its cause to the next paint, once per frame.
  function render_log(cause_name, start_milliseconds, render_logged) {
    if (pending_render !== null) return;
    pending_render = { cause_name, start_milliseconds };
    after_paint_run(() => {
      const paint_milliseconds = performance.now();
      load_log_append("render", pending_render.start_milliseconds, [
        pending_render.cause_name,
        paint_milliseconds - pending_render.start_milliseconds,
      ]);
      pending_render = null;
      page_render_is_logged = true;
      render_logged();
    });
  }
  // Logs the page's load render from navigation start, then runs the callback.
  function page_render_log(render_logged) {
    if (page_render_is_logged) window.throw_exception_("str_error_internal");
    if (document.readyState !== "loading") {
      render_log(NAVIGATION_CAUSE_NAME, 0, render_logged);
      return;
    }
    // Listening after the page's own activation, the render then includes it.
    document.addEventListener(
      "DOMContentLoaded",
      window.try_catch_handler_(() =>
        render_log(NAVIGATION_CAUSE_NAME, 0, render_logged),
      ),
    );
  }
  // Logs a render after the page's load, the input log timing clicks and keys.
  function event_render_log() {
    if (!page_render_is_logged) return;
    if (!window.event) window.throw_exception_("str_error_internal");
    if (INPUT_EVENT_NAMES.includes(window.event.type)) return;
    render_log(window.event.type, window.event.timeStamp, () => {});
  }

  // Names an element by its tag, id and classes.
  function element_name_of(element) {
    return (
      element.tagName.toLowerCase() +
      (element.id ? "#" + element.id : "") +
      [...element.classList].map((class_name) => "." + class_name).join("")
    );
  }
  // Logs a click or key with what it reached, timed to the next paint.
  function input_take_(input_event) {
    if (!input_event.isTrusted) return;
    const target_name =
      input_event.type === "keydown"
        ? input_event.code
        : element_name_of(input_event.target);
    after_paint_run(() =>
      load_log_append("input", input_event.timeStamp, [
        input_event.type,
        target_name,
        performance.now() - input_event.timeStamp,
      ]),
    );
  }
  // Logs each long animation frame, then each script the browser names in it.
  function long_frames_take(frame_entries) {
    for (const frame_entry of frame_entries) {
      const frame_end = frame_entry.startTime + frame_entry.duration;
      // A frame that drew nothing has a render start of zero.
      const render_start =
        frame_entry.renderStart === 0 ? frame_end : frame_entry.renderStart;
      load_log_append("frame", frame_entry.startTime, [
        frame_entry.duration,
        frame_end - render_start,
      ]);
      for (const script_entry of frame_entry.scripts)
        load_log_append("script", script_entry.startTime, [
          script_entry.duration,
          script_entry.invokerType === "classic-script"
            ? script_entry.invokerType
            : script_entry.invoker,
          script_entry.sourceURL,
          script_entry.sourceFunctionName,
        ]);
    }
  }
  // Logs the page's own load event.
  function page_load_take_(browser_event) {
    if (browser_event.target !== document) return;
    load_log_append("load", browser_event.timeStamp, []);
  }
  // Counts an asset loaded while the page parses, then those between paints.
  function asset_load_take_(browser_event) {
    const target = browser_event.target;
    if (!RESOURCE_TAG_NAMES.includes(target.tagName)) return;
    if (document.readyState === "loading") {
      parsed_asset_count++;
      return;
    }
    if (pending_assets === null) {
      pending_assets = {
        asset_count: 0,
        start_milliseconds: browser_event.timeStamp,
      };
      after_paint_run(() => {
        load_log_append("asset", pending_assets.start_milliseconds, [
          pending_assets.asset_count,
          pending_assets.last_href,
          pending_assets.end_milliseconds - pending_assets.start_milliseconds,
        ]);
        pending_assets = null;
      });
    }
    pending_assets.asset_count++;
    pending_assets.last_href = target.href || target.src;
    pending_assets.end_milliseconds = browser_event.timeStamp;
  }
  // Logs the end of parsing with the count of assets it waited on.
  function page_parse_take_(browser_event) {
    load_log_append("parse", browser_event.timeStamp, [parsed_asset_count]);
  }

  window.report_load_log_ = {
    event_render_log,
    kept_line_count_set: load_log_kept_line_count_set,
    newest_entries_of: load_log_newest_entries_of,
    page_render_log,
  };
  window.resource_failure_expect_ = resource_failure_expect_;
  window.is_framed_ = is_framed;
  report_error_overlay.relay_set_(report_relay);
  window.addEventListener(
    "message",
    window.try_catch_handler_(relayed_report_take_),
  );
  window.addEventListener(
    "error",
    window.try_catch_handler_(resource_failure_take_),
    true,
  );
  window.addEventListener(
    "load",
    window.try_catch_handler_(page_load_take_),
    true,
  );
  // An element's load event skips the window, so the document takes it.
  document.addEventListener(
    "load",
    window.try_catch_handler_(asset_load_take_),
    true,
  );
  document.addEventListener(
    "DOMContentLoaded",
    window.try_catch_handler_(page_parse_take_),
  );
  for (const event_name of INPUT_EVENT_NAMES)
    window.addEventListener(
      event_name,
      window.try_catch_handler_(input_take_),
      true,
    );
  long_frame_observer.observe({
    type: "long-animation-frame",
    buffered: true,
  });
})();
