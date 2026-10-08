// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const HELD_SCRIPT_TEMPLATE_ID = "page-held-script-";
  const SETTINGS_RELAY_MESSAGE_NAME = "settings_relay";
  const SETTINGS_REQUEST_MESSAGE_NAME = "settings_request";
  const is_framed = window.shared_is_framed_;
  let applied_values = {};
  let settings_object = null;

  function deep_freeze(value) {
    if (value === null || typeof value !== "object") return value;
    Object.values(value).forEach(deep_freeze);
    return Object.freeze(value);
  }
  // Writes each root value a stylesheet reads, from the window settings.
  function root_values_write() {
    const STYLE_DESIGN_COORDINATES_WIDTH_PX = settings_(
      "STYLE_DESIGN_COORDINATES_WIDTH_PX",
    );
    const STYLE_DESIGN_MINIMUM_WINDOW_WIDTH_PX = settings_(
      "STYLE_DESIGN_MINIMUM_WINDOW_WIDTH_PX",
    );
    const STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE = settings_(
      "STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE",
    );
    const root_values = {};
    for (const [name, value] of Object.entries(
      settings_("STYLE_VALUE_ENTRIES"),
    ))
      root_values["--" + name] = value;
    root_values[settings_("STYLE_DESIGN_DEVICE_PIXEL_WIDEST_PROPERTY")] =
      STYLE_DESIGN_COORDINATES_WIDTH_PX /
        (STYLE_DESIGN_MINIMUM_WINDOW_WIDTH_PX *
          STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE) +
      "px";
    root_values[settings_("STYLE_DESIGN_FONT_FIT_PROPERTY")] = String(
      settings_("STYLE_DESIGN_FONT_FIT_START_MULTIPLE"),
    );
    root_values[settings_("STYLE_DESIGN_FONT_SIZE_PROPERTY")] =
      settings_("STYLE_DESIGN_FONT_SIZE_PX") + "px";
    root_values[settings_("STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY")] =
      settings_("STYLE_DESIGN_VIEWPORT_HEIGHT_START_PERCENT") + "vh";
    root_values[
      settings_("STYLE_HEAT_MAP_SOURCE_LINE_NUMBER_MARKER_WIDTH_PROPERTY")
    ] =
      settings_("STYLE_HEAT_MAP_SOURCE_LINE_NUMBER_MARKER_WIDTH_CHARS") + "ch";
    root_values[settings_("STYLE_PAGE_FONT_FAMILY_PROPERTY")] = settings_(
      "STYLE_PAGE_FONT_FAMILY",
    );
    for (const palette_name of [
      "STYLE_COLOR_LIGHT_MODE",
      "STYLE_COLOR_DARK_MODE",
    ])
      for (const [color, roles] of Object.entries(settings_(palette_name)))
        for (const role of roles) root_values["--" + role] = color;
    for (const [name, value] of Object.entries(root_values))
      document.documentElement.style.setProperty(name, value);
  }
  // Answers whether the top page's query turns settings debugging on.
  function settings_debug_query_enabled(written_object) {
    const query_value = new URLSearchParams(location.search).get(
      written_object.SETTINGS_DEBUG_QUERY_KEY_NAME,
    );
    if (query_value === null) return false;
    if (query_value !== written_object.SETTINGS_DEBUG_QUERY_ENABLED_VALUE)
      throw new Error(
        window.ui_strings_.text_fill(
          "str_error_settings_debug_query_unusable",
          [
            written_object.SETTINGS_DEBUG_QUERY_KEY_NAME,
            query_value,
            written_object.SETTINGS_DEBUG_QUERY_ENABLED_VALUE,
          ],
        ),
      );
    return true;
  }
  // Answers the settings the top hash applies, an empty object for none.
  function settings_applied_values_of(written_object) {
    const key_prefix = written_object.SETTINGS_DEBUG_HASH_KEY_NAME + "=";
    const applied_part = location.hash
      .slice(1)
      .split("&")
      .find((hash_part) => hash_part.startsWith(key_prefix));
    if (applied_part === undefined) return {};
    const hash_values = JSON.parse(
      new TextDecoder(undefined, { fatal: true }).decode(
        Uint8Array.fromBase64(
          decodeURIComponent(applied_part.slice(key_prefix.length)),
        ),
      ),
    );
    if (
      hash_values === null ||
      typeof hash_values !== "object" ||
      Array.isArray(hash_values)
    )
      throw new Error(
        window.ui_strings_.text_fill("str_error_settings_values_unusable", [
          applied_part,
        ]),
      );
    for (const setting_name of Object.keys(hash_values)) {
      if (!Object.hasOwn(written_object, setting_name))
        throw new Error(
          window.ui_strings_.text_fill("str_error_setting_unknown", [
            setting_name,
          ]),
        );
    }
    return hash_values;
  }
  // Installs the window settings object, under debug with the hash's applied.
  function settings_install(written_object) {
    if (!is_framed) {
      const debug_enabled =
        settings_debug_query_enabled(written_object) ||
        written_object.SETTINGS_DEBUG_ENABLED;
      if (debug_enabled) {
        applied_values = settings_applied_values_of(written_object);
        Object.assign(written_object, applied_values);
      }
      written_object.SETTINGS_DEBUG_ENABLED = debug_enabled;
    }
    settings_object = deep_freeze(written_object);
    root_values_write();
  }
  // Reads one setting of the window settings object, refusing an unknown one.
  function settings_(setting_name) {
    if (!Object.hasOwn(settings_object, setting_name))
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    return settings_object[setting_name];
  }
  function settings_names_() {
    return Object.keys(settings_object);
  }
  // Answers a copy of the settings the top page's hash applied.
  function settings_applied_values_() {
    return { ...applied_values };
  }
  // Loads the scripts a framed page holds, in order, under its settings.
  function held_scripts_load() {
    const held_template = document.getElementById(HELD_SCRIPT_TEMPLATE_ID);
    if (!held_template)
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    for (const held_script of held_template.content.querySelectorAll(
      "script",
    )) {
      const loaded_script = document.createElement("script");
      loaded_script.async = false;
      loaded_script.src = held_script.getAttribute("src");
      held_template.before(loaded_script);
    }
  }
  // Answers a framed page asking for the window settings object.
  function settings_request_take(browser_event) {
    const payload = browser_event.data;
    if (payload && payload.report_ui === SETTINGS_REQUEST_MESSAGE_NAME)
      browser_event.source.postMessage(
        { report_ui: SETTINGS_RELAY_MESSAGE_NAME, settings_object },
        "*",
      );
  }
  // Installs the relayed settings object, then loads the held scripts.
  function settings_relay_take(browser_event) {
    const payload = browser_event.data;
    if (
      browser_event.source !== window.parent ||
      !payload ||
      payload.report_ui !== SETTINGS_RELAY_MESSAGE_NAME
    )
      return;
    settings_install(payload.settings_object);
    if (document.readyState !== "loading") held_scripts_load();
    else
      document.addEventListener(
        "DOMContentLoaded",
        window.try_catch_handler_(held_scripts_load),
      );
  }
  function held_scripts_unframed_check() {
    if (document.getElementById(HELD_SCRIPT_TEMPLATE_ID))
      throw new Error(
        window.ui_strings_.text_of("str_error_held_script_unframed"),
      );
  }

  window.settings_ = settings_;
  window.settings_applied_values_ = settings_applied_values_;
  window.settings_names_ = settings_names_;
  window.addEventListener(
    "message",
    window.try_catch_handler_(settings_request_take),
  );
  if (is_framed) {
    window.addEventListener(
      "message",
      window.try_catch_handler_(settings_relay_take),
    );
    window.parent.postMessage(
      { report_ui: SETTINGS_REQUEST_MESSAGE_NAME },
      "*",
    );
  } else {
    settings_install(__DATA__);
    document.addEventListener(
      "DOMContentLoaded",
      window.try_catch_handler_(held_scripts_unframed_check),
    );
  }
})();
