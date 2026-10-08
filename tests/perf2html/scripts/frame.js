// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const DARK_MODE_QUERY_KEY_NAME = settings_("DARK_MODE_QUERY_KEY_NAME");
  const DARK_MODE_QUERY_VALUES = settings_("DARK_MODE_QUERY_VALUES");
  const FLAME_GRAPH_VIEW_ENTRY = settings_("FLAME_GRAPH_VIEW_ENTRY");
  const SCREENSHOT_MENU_ENTRY_KEY_NAME = settings_(
    "SCREENSHOT_MENU_ENTRY_KEY_NAME",
  );
  const SETTINGS_DEBUG_ENABLED = settings_("SETTINGS_DEBUG_ENABLED");
  const SETTINGS_DEBUG_HASH_KEY_NAME = settings_(
    "SETTINGS_DEBUG_HASH_KEY_NAME",
  );
  const SETTINGS_DEBUG_QUERY_ENABLED_VALUE = settings_(
    "SETTINGS_DEBUG_QUERY_ENABLED_VALUE",
  );
  const SETTINGS_DEBUG_QUERY_KEY_NAME = settings_(
    "SETTINGS_DEBUG_QUERY_KEY_NAME",
  );
  const SETTINGS_VIEW_ENTRY = settings_("SETTINGS_VIEW_ENTRY");

  const home_panel = window.report_ui_.home_panel;
  const loaded_hash = location.hash;
  const loaded_address = window.report_ui_.address.of_hash(loaded_hash);
  const loaded_menu_entry_number = new URLSearchParams(location.search).get(
    SCREENSHOT_MENU_ENTRY_KEY_NAME,
  );
  const menu_strip = document.getElementById("menu-");
  const has_flame_graph = menu_strip.getAttribute("data-flame-graph-") === "1";
  const test_names = JSON.parse(menu_strip.getAttribute("data-test-names-"));
  const view_frame = window.report_ui_.view_frame;

  let current_address = null;
  let loaded_view_href = "";

  function address_now() {
    return current_address;
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
      throw new Error(
        window.ui_strings_.text_fill("str_error_hash_test_unknown", [
          parsed_address.test,
        ]),
      );
    if (parsed_address.view === FLAME_GRAPH_VIEW_ENTRY[0] && !has_flame_graph)
      throw new Error(
        window.ui_strings_.text_fill("str_error_hash_view_unknown", [
          parsed_address.view,
        ]),
      );
    if (
      parsed_address.setting !== null &&
      !window.settings_names_().includes(parsed_address.setting)
    )
      throw new Error(
        window.ui_strings_.text_fill("str_error_hash_setting_unknown", [
          parsed_address.setting,
        ]),
      );
  }
  // Loads the top page again at its hash under the settings debug query.
  function settings_debug_reload() {
    const query_values = new URLSearchParams(location.search);
    query_values.set(
      SETTINGS_DEBUG_QUERY_KEY_NAME,
      SETTINGS_DEBUG_QUERY_ENABLED_VALUE,
    );
    location.replace("?" + query_values + location.hash);
  }
  function view_show() {
    const shown_address = window.report_ui_.address.of_hash(location.hash);
    address_check(shown_address);
    current_address = shown_address;
    const applied_text = shown_address[SETTINGS_DEBUG_HASH_KEY_NAME];
    const needs_debug =
      shown_address.view === SETTINGS_VIEW_ENTRY[0] || applied_text !== null;
    if (needs_debug && !SETTINGS_DEBUG_ENABLED) {
      settings_debug_reload();
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
  // Posts a message down carrying the dark mode the top page shows.
  function view_post(message_name) {
    if (message_name === "layout_reset")
      window.report_ui_.layout_reset(home_panel);
    if (loaded_view_href)
      view_frame.contentWindow.postMessage(
        {
          report_ui: message_name,
          dark_mode_enabled: window.report_ui_.dark_mode_enabled_now_(),
        },
        "*",
      );
  }
  function view_message_take(message_event) {
    const message_data = message_event.data;
    if (message_event.source !== view_frame.contentWindow || !message_data)
      return;
    const message_tag = message_data.report_ui;
    if (message_tag === "address_request") address_request(message_data.hash);
    else if (message_tag === "dark_mode_request") view_post("dark_mode_show");
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
    else if (
      message_tag !== undefined &&
      message_tag !== "report_error" &&
      message_tag !== "settings_request"
    )
      throw new Error(
        window.ui_strings_.text_fill("str_error_message_tag_unknown", [
          message_tag,
        ]),
      );
  }

  function dark_mode_query_apply_() {
    const query_value = new URLSearchParams(location.search).get(
      DARK_MODE_QUERY_KEY_NAME,
    );
    if (query_value === null) return;
    if (query_value === DARK_MODE_QUERY_VALUES.enabled)
      window.report_ui_.dark_mode_show_(true);
    else if (query_value === DARK_MODE_QUERY_VALUES.disabled)
      window.report_ui_.dark_mode_show_(false);
    else
      throw new Error(
        window.ui_strings_.text_fill("str_error_dark_mode_unusable", [
          query_value,
        ]),
      );
  }

  function activate() {
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
  }

  window.report_frame_ = {
    activate,
    address_now,
    address_request,
    has_flame_graph,
    menu_entry_number_now,
    test_names,
    view_post,
  };
})();
