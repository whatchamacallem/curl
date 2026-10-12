// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const DARK_MODE_QUERY_KEY_NAME = settings_("DARK_MODE_QUERY_KEY_NAME");
  const DARK_MODE_QUERY_VALUES = settings_("DARK_MODE_QUERY_VALUES");
  const FLAME_GRAPH_VIEW_ENTRY = settings_("FLAME_GRAPH_VIEW_ENTRY");
  const REPORT_TEST_SUITE_NAME = settings_("REPORT_TEST_SUITE_NAME");
  const SCREENSHOT_MENU_KEY_NUMBER = settings_("SCREENSHOT_MENU_KEY_NUMBER");
  const SETTINGS_DEBUG_ENABLED = settings_("SETTINGS_DEBUG_ENABLED");
  const SETTINGS_DEBUG_HASH_KEY_NAME = settings_(
    "SETTINGS_DEBUG_HASH_KEY_NAME",
  );
  const SETTINGS_DEBUG_QUERY_KEY_NAME = settings_(
    "SETTINGS_DEBUG_QUERY_KEY_NAME",
  );
  const SETTINGS_DEBUG_QUERY_VALUES = settings_("SETTINGS_DEBUG_QUERY_VALUES");
  const SETTINGS_LOAD_LOG_HISTORY_DEFAULT_LINES = settings_(
    "SETTINGS_LOAD_LOG_HISTORY_DEFAULT_LINES",
  );
  const SETTINGS_LOAD_LOG_HISTORY_LINE_CHOICES = settings_(
    "SETTINGS_LOAD_LOG_HISTORY_LINE_CHOICES",
  );
  const SETTINGS_LOAD_LOG_HISTORY_MAX_LINES = settings_(
    "SETTINGS_LOAD_LOG_HISTORY_MAX_LINES",
  );
  const SETTINGS_VIEW_ENTRY = settings_("SETTINGS_VIEW_ENTRY");
  const STORAGE_KEY_SETTINGS_HISTORY = settings_(
    "STORAGE_KEY_SETTINGS_HISTORY",
  );

  const home_panel = window.report_ui_.home_panel;
  const loaded_hash = location.hash;
  const loaded_address = window.report_ui_.address.of_hash(loaded_hash);
  const loaded_menu_entry_number = new URLSearchParams(location.search).get(
    SCREENSHOT_MENU_KEY_NUMBER,
  );
  const menu_strip = document.getElementById("menu-");
  const counter_names = JSON.parse(
    menu_strip.getAttribute("data-counter-names-"),
  );
  const has_flame_graph = menu_strip.getAttribute("data-flame-graph-") === "1";
  const is_diff = menu_strip.getAttribute("data-diff-") === "1";
  const test_names = JSON.parse(menu_strip.getAttribute("data-test-names-"));
  const view_frame = window.report_ui_.view_frame;

  let current_address = null;
  let load_log_shown_count = null;
  let loaded_view_href = "";

  function address_now() {
    return current_address;
  }
  // Answers whether the report holds a flame graph for the test.
  function flame_graph_exists(test_name) {
    return has_flame_graph && test_name !== REPORT_TEST_SUITE_NAME;
  }
  // Answers the query's menu entry number while the loaded address shows.
  function menu_entry_number_now() {
    return location.hash === loaded_hash ? loaded_menu_entry_number : null;
  }
  function address_check(parsed_address) {
    if (
      parsed_address.test !== null &&
      !test_names.includes(parsed_address.test)
    )
      window.throw_exception_(
        "str_error_hash_test_unknown",
        parsed_address.test,
      );
    if (
      parsed_address.view === FLAME_GRAPH_VIEW_ENTRY[0] &&
      !flame_graph_exists(parsed_address.test)
    )
      window.throw_exception_(
        "str_error_hash_flame_graph_missing",
        parsed_address.test,
      );
    if (
      parsed_address.setting !== null &&
      !window.settings_names_().includes(parsed_address.setting)
    )
      window.throw_exception_(
        "str_error_hash_setting_unknown",
        parsed_address.setting,
      );
  }
  // Loads the top page again under the debug query, off dropping the values.
  function settings_debug_load(debug_enabled) {
    const loaded_url = new URL(location.href);
    loaded_url.searchParams.set(
      SETTINGS_DEBUG_QUERY_KEY_NAME,
      debug_enabled
        ? SETTINGS_DEBUG_QUERY_VALUES.enabled
        : SETTINGS_DEBUG_QUERY_VALUES.disabled,
    );
    if (!debug_enabled)
      loaded_url.hash =
        window.report_ui_.address.settings_cleared_hash_of(current_address);
    location.replace(loaded_url.href);
  }
  // Clears any settings debug query and values, loading the top page again.
  function settings_debug_clear() {
    const cleared_url = new URL(location.href);
    if (
      !cleared_url.searchParams.has(SETTINGS_DEBUG_QUERY_KEY_NAME) &&
      current_address[SETTINGS_DEBUG_HASH_KEY_NAME] === null
    )
      return;
    cleared_url.searchParams.delete(SETTINGS_DEBUG_QUERY_KEY_NAME);
    cleared_url.hash =
      window.report_ui_.address.settings_cleared_hash_of(current_address);
    location.replace(cleared_url.href);
  }
  function view_show() {
    const shown_address = window.report_ui_.address.of_hash(location.hash);
    address_check(shown_address);
    current_address = shown_address;
    const applied_text = shown_address[SETTINGS_DEBUG_HASH_KEY_NAME];
    if (applied_text !== null && !SETTINGS_DEBUG_ENABLED) {
      settings_debug_load(true);
      return;
    }
    // Installs the settings again when the hash changes those it applies.
    if (applied_text !== loaded_address[SETTINGS_DEBUG_HASH_KEY_NAME]) {
      location.reload();
      return;
    }
    window.report_menu_.address_show();
    if (shown_address.view === null) {
      const frame_had_focus = document.activeElement === view_frame;
      view_frame.hidden = true;
      home_panel.hidden = false;
      window.report_ui_.layout_refresh(home_panel);
      if (frame_had_focus) {
        const tab_stops = home_panel.querySelectorAll('[tabindex="0"]');
        window.report_ui_.tab_stop_move(
          null,
          tab_stops[tab_stops.length - 1],
          true,
        );
      }
      return;
    }
    const view_href =
      window.report_ui_.address.page_href_of(shown_address) + location.hash;
    if (view_href !== loaded_view_href) {
      view_frame.contentWindow.location.replace(view_href);
      loaded_view_href = view_href;
    }
    const home_had_focus = home_panel.contains(document.activeElement);
    home_panel.hidden = true;
    view_frame.hidden = false;
    if (home_had_focus) view_frame.focus();
  }
  function address_request(requested_hash) {
    if (requested_hash !== (location.hash || "#")) {
      location.hash = requested_hash;
      return;
    }
    view_show();
    if (current_address.view !== null) view_post("recenter");
  }
  // Requests the settings view, the setting's new value among those applied.
  function settings_apply(setting_name, setting_value) {
    window.settings_(setting_name);
    const applied_values = window.settings_applied_values_();
    applied_values[setting_name] = setting_value;
    address_request(
      window.report_ui_.address.hash_of({
        test: current_address.test,
        view: SETTINGS_VIEW_ENTRY[0],
        setting: setting_name,
        [SETTINGS_DEBUG_HASH_KEY_NAME]: new TextEncoder()
          .encode(JSON.stringify(applied_values))
          .toBase64(),
      }),
    );
  }
  // Posts a message down carrying the dark mode and preferences shown.
  function view_post(message_name, message_fields = {}) {
    if (message_name === "layout_reset")
      window.report_ui_.layout_reset(home_panel);
    if (loaded_view_href)
      view_frame.contentWindow.postMessage(
        {
          report_ui: message_name,
          dark_mode_enabled: window.report_ui_.dark_mode_enabled_now_(),
          view_preferences: window.report_preferences_.now(),
          ...message_fields,
        },
        "*",
      );
  }
  // Shows the stored history count when offered, else its default.
  function load_log_history_seed() {
    const stored_count = window.report_ui_.view_storage.value_read(
      STORAGE_KEY_SETTINGS_HISTORY,
    );
    load_log_shown_count = SETTINGS_LOAD_LOG_HISTORY_LINE_CHOICES.includes(
      stored_count,
    )
      ? stored_count
      : SETTINGS_LOAD_LOG_HISTORY_DEFAULT_LINES;
  }
  // Relays the newest history entries the view shows, and their count.
  function load_log_relay_post() {
    view_post("load_log_relay", {
      load_log_entries: window.report_load_log_.newest_entries_of(
        load_log_shown_count,
      ),
      load_log_line_count: load_log_shown_count,
    });
  }
  // Stores the history count the view chose, then relays the history.
  function load_log_history_set(line_count) {
    if (!SETTINGS_LOAD_LOG_HISTORY_LINE_CHOICES.includes(line_count))
      window.throw_exception_("str_error_internal");
    window.report_ui_.view_storage.value_write(
      STORAGE_KEY_SETTINGS_HISTORY,
      line_count,
    );
    load_log_shown_count = line_count;
    load_log_relay_post();
  }
  function view_message_take(message_event) {
    const message_data = message_event.data;
    if (message_event.source !== view_frame.contentWindow || !message_data)
      return;
    const message_tag = message_data.report_ui;
    if (message_tag === "address_request") address_request(message_data.hash);
    else if (message_tag === "dark_mode_request") view_post("dark_mode_show");
    else if (message_tag === "load_log_history_set")
      load_log_history_set(message_data.line_count);
    else if (message_tag === "load_log_request") load_log_relay_post();
    else if (message_tag === "menu_key_pressed") {
      if (
        !window.report_menu_.menu_key_take(
          message_data.key,
          message_data.repeat,
        )
      )
        view_post("tests_pulldown_closed");
    } else if (message_tag === "settings_apply")
      settings_apply(message_data.setting_name, message_data.setting_value);
    else if (message_tag === "settings_debug_toggle")
      settings_debug_load(!SETTINGS_DEBUG_ENABLED);
    else if (
      message_tag !== undefined &&
      message_tag !== "load_log_entry" &&
      message_tag !== "report_error" &&
      message_tag !== "settings_request"
    )
      window.throw_exception_("str_error_internal");
  }

  function dark_mode_query_apply_() {
    const query_value = new URLSearchParams(location.search).get(
      DARK_MODE_QUERY_KEY_NAME,
    );
    if (query_value === null) return;
    if (
      query_value !== DARK_MODE_QUERY_VALUES.enabled &&
      query_value !== DARK_MODE_QUERY_VALUES.disabled
    )
      window.throw_exception_("str_error_dark_mode_unusable", query_value);
    if (!window.report_ui_.view_storage.preferences_ignored())
      window.report_ui_.dark_mode_show_(
        query_value === DARK_MODE_QUERY_VALUES.enabled,
      );
  }

  function activate() {
    if (
      !SETTINGS_LOAD_LOG_HISTORY_LINE_CHOICES.includes(
        SETTINGS_LOAD_LOG_HISTORY_DEFAULT_LINES,
      )
    )
      window.throw_exception_(
        "str_error_setting_choice_unknown",
        "SETTINGS_LOAD_LOG_HISTORY_DEFAULT_LINES",
        SETTINGS_LOAD_LOG_HISTORY_DEFAULT_LINES,
      );
    window.report_load_log_.kept_line_count_set(
      SETTINGS_LOAD_LOG_HISTORY_MAX_LINES,
    );
    load_log_history_seed();
    dark_mode_query_apply_();
    window.addEventListener(
      "hashchange",
      window.try_catch_handler_(view_show),
    );
    window.addEventListener(
      "message",
      window.try_catch_handler_(view_message_take),
    );
    view_show();
    window.report_load_log_.page_render_log(() => {});
  }

  window.report_frame_ = {
    activate,
    address_now,
    address_request,
    counter_names,
    flame_graph_exists,
    is_diff,
    load_log_history_seed,
    menu_entry_number_now,
    settings_debug_clear,
    test_names,
    view_post,
  };
})();
