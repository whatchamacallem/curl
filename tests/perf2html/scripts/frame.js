// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.catch_show_throw_(function () {
  "use strict";

  const DARK_MODE_QUERY_KEY_NAME = settings_("DARK_MODE_QUERY_KEY_NAME");
  const DARK_MODE_QUERY_VALUES = settings_("DARK_MODE_QUERY_VALUES");
  const FLAME_GRAPH_VIEW_ENTRY = settings_("FLAME_GRAPH_VIEW_ENTRY");

  const home_panel = window.report_ui_.home_panel;
  const menu_strip = document.getElementById("menu-");
  const has_flame_graph = menu_strip.getAttribute("data-flame-graph-") === "1";
  const test_names = JSON.parse(menu_strip.getAttribute("data-test-names-"));
  const view_frame = window.report_ui_.view_frame;

  let current_address = null;
  let loaded_view_href = "";

  function address_now() {
    return current_address;
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
  }
  function view_show() {
    const shown_address = window.report_ui_.address.of_hash(location.hash);
    address_check(shown_address);
    current_address = shown_address;
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
    if (current_address.view !== null) view_post("report_ui:recenter");
  }
  function view_post(message_text) {
    if (message_text === "report_ui:layout_reset")
      window.report_ui_.layout_reset(home_panel);
    if (loaded_view_href)
      view_frame.contentWindow.postMessage(message_text, "*");
  }
  function view_message_take(message_event) {
    const message_data = message_event.data;
    if (message_event.source !== view_frame.contentWindow || !message_data)
      return;
    const message_tag = message_data.report_ui;
    if (message_tag === "address_request") address_request(message_data.hash);
    else if (message_tag === "menu_key_pressed") {
      if (
        !window.report_menu_.menu_key_take(
          message_data.key,
          message_data.repeat,
        )
      )
        view_post("report_ui:tests_pulldown_closed");
    } else if (message_tag !== undefined && message_tag !== "report_error")
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
      window.report_ui_.dark_mode_set_(true);
    else if (query_value === DARK_MODE_QUERY_VALUES.disabled)
      window.report_ui_.dark_mode_set_(false);
    else
      throw new Error(
        window.ui_strings_.text_fill("str_error_dark_mode_unusable", [
          query_value,
        ]),
      );
  }

  function activate() {
    dark_mode_query_apply_();
    window.addEventListener("hashchange", window.catch_show_throw_(view_show));
    window.addEventListener(
      "message",
      window.catch_show_throw_(view_message_take),
    );
    view_show();
  }

  window.report_frame_ = {
    activate,
    address_now,
    address_request,
    has_flame_graph,
    test_names,
    view_post,
  };
})();
