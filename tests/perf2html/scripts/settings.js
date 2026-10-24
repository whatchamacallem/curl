// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const is_framed = window.is_framed_;
  const written_object = __DATA__;
  let applied_values = {};
  // Holds the settings a page opens under, before a framed page's relay.
  let opening_object = written_object;
  let preferences_are_ignored = false;
  let settings_object = null;
  let storage_is_checked = false;

  function deep_freeze(value) {
    if (value === null || typeof value !== "object") return value;
    Object.values(value).forEach(deep_freeze);
    return Object.freeze(value);
  }
  // Reads one setting of the settings given, refusing an unknown one.
  function setting_read(settings_values, setting_name) {
    if (!Object.hasOwn(settings_values, setting_name))
      window.throw_exception_("str_error_internal");
    return settings_values[setting_name];
  }
  // Writes each palette role's color as the root value a stylesheet reads.
  function palette_values_write(settings_values) {
    for (const palette_name of [
      "STYLE_COLOR_LIGHT_MODE",
      "STYLE_COLOR_DARK_MODE",
    ])
      for (const [color, roles] of Object.entries(
        setting_read(settings_values, palette_name),
      ))
        for (const role of roles)
          document.documentElement.style.setProperty("--" + role, color);
  }
  // Writes each root value a stylesheet reads, from the window settings.
  function root_values_write() {
    const root_values = {};
    for (const [name, value] of Object.entries(
      settings_("STYLE_VALUE_ENTRIES"),
    ))
      root_values["--" + name] = value;
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
    for (const [name, value] of Object.entries(root_values))
      document.documentElement.style.setProperty(name, value);
    palette_values_write(settings_object);
  }
  // Returns whether settings debugging is on, the top page's query deciding.
  function settings_debug_enabled(written_object) {
    const query_values = written_object.SETTINGS_DEBUG_QUERY_VALUES;
    const query_value = new URLSearchParams(location.search).get(
      written_object.SETTINGS_DEBUG_QUERY_KEY_NAME,
    );
    if (query_value === null) return written_object.SETTINGS_DEBUG_ENABLED;
    if (
      query_value !== query_values.enabled &&
      query_value !== query_values.disabled
    )
      window.throw_exception_(
        "str_error_settings_debug_query_unusable",
        written_object.SETTINGS_DEBUG_QUERY_KEY_NAME,
        query_value,
        query_values.disabled,
        query_values.enabled,
      );
    return query_value === query_values.enabled;
  }
  // Turns the debug query on in place when the top hash applies settings.
  function settings_debug_query_enable(written_object) {
    if (
      settings_applied_part(written_object) === undefined ||
      settings_debug_enabled(written_object)
    )
      return;
    const debug_url = new URL(location.href);
    debug_url.searchParams.set(
      written_object.SETTINGS_DEBUG_QUERY_KEY_NAME,
      written_object.SETTINGS_DEBUG_QUERY_VALUES.enabled,
    );
    history.replaceState(history.state, "", debug_url.href);
  }
  // Returns the hash part applying settings, undefined for none.
  function settings_applied_part(settings_values) {
    const key_prefix =
      setting_read(settings_values, "SETTINGS_DEBUG_HASH_KEY_NAME") + "=";
    return location.hash
      .slice(1)
      .split("&")
      .find((hash_part) => hash_part.startsWith(key_prefix));
  }
  // Returns the settings the top hash applies, an empty object for none.
  function settings_applied_values(written_object) {
    const applied_part = settings_applied_part(written_object);
    if (applied_part === undefined) return {};
    const hash_values = JSON.parse(
      new TextDecoder(undefined, { fatal: true }).decode(
        Uint8Array.fromBase64(
          decodeURIComponent(
            applied_part.slice(applied_part.indexOf("=") + 1),
          ),
        ),
      ),
    );
    if (
      hash_values === null ||
      typeof hash_values !== "object" ||
      Array.isArray(hash_values)
    )
      window.throw_exception_(
        "str_error_settings_values_unusable",
        applied_part,
      );
    for (const setting_name of Object.keys(hash_values)) {
      if (!Object.hasOwn(written_object, setting_name))
        window.throw_exception_("str_error_setting_unknown", setting_name);
    }
    return hash_values;
  }
  // Installs the window settings object, under debug with the hash's applied.
  function settings_install(written_object) {
    if (!is_framed) {
      settings_debug_query_enable(written_object);
      const debug_enabled = settings_debug_enabled(written_object);
      if (debug_enabled) {
        applied_values = settings_applied_values(written_object);
        Object.assign(written_object, applied_values);
      }
      written_object.SETTINGS_DEBUG_ENABLED = debug_enabled;
    }
    settings_object = deep_freeze(written_object);
    root_values_write();
  }
  // Reads one setting of the window settings object, refusing an unknown one.
  function settings_(setting_name) {
    return setting_read(settings_object, setting_name);
  }
  // Reads one setting the page opens under, a framed page's before its relay.
  function settings_opening_(setting_name) {
    return setting_read(opening_object, setting_name);
  }
  function settings_names_() {
    return Object.keys(settings_object);
  }
  // Returns a copy of the settings the top page's hash applied.
  function settings_applied_values_() {
    return { ...applied_values };
  }
  // Loads the scripts a framed page holds, in order, under its settings.
  function held_scripts_load() {
    const held_template = document.getElementById(
      settings_("SETTINGS_HELD_SCRIPT_TEMPLATE_ID"),
    );
    if (!held_template) window.throw_exception_("str_error_internal");
    for (const held_script of held_template.content.querySelectorAll(
      "script",
    )) {
      const loaded_script = document.createElement("script");
      loaded_script.async = false;
      loaded_script.src = held_script.getAttribute("src");
      held_template.before(loaded_script);
    }
  }
  // Relays the window settings object to a framed page asking for it.
  function settings_request_handler(browser_event) {
    const payload = browser_event.data;
    if (
      payload &&
      payload.report_ui ===
        setting_read(opening_object, "SETTINGS_REQUEST_MESSAGE_NAME")
    )
      browser_event.source.postMessage(
        {
          report_ui: setting_read(
            opening_object,
            "SETTINGS_RELAY_MESSAGE_NAME",
          ),
          settings_object,
        },
        "*",
      );
  }
  // Installs the relayed settings object, then loads the held scripts.
  function settings_relay_handler(browser_event) {
    const payload = browser_event.data;
    if (
      browser_event.source !== window.parent ||
      !payload ||
      payload.report_ui !==
        setting_read(opening_object, "SETTINGS_RELAY_MESSAGE_NAME")
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
    if (document.getElementById(settings_("SETTINGS_HELD_SCRIPT_TEMPLATE_ID")))
      window.throw_exception_("str_error_held_script_unframed");
  }

  // Stores null in every owned key, each preference one the user never set.
  function storage_sweep(owned_keys) {
    for (const storage_key of owned_keys) {
      localStorage.setItem(storage_key, JSON.stringify(null));
    }
  }
  function storage_version_check(settings_values) {
    if (storage_is_checked) return;
    storage_is_checked = true;
    const owned_keys = setting_read(settings_values, "STORAGE_OWNED_KEYS");
    const storage_version = setting_read(settings_values, "STORAGE_VERSION");
    const version_key = setting_read(settings_values, "STORAGE_VERSION_KEY");
    preferences_are_ignored =
      settings_applied_part(settings_values) !== undefined;
    if (preferences_are_ignored) {
      storage_sweep(owned_keys);
      return;
    }
    if (localStorage.getItem(version_key) === storage_version) {
      return;
    }
    storage_sweep(owned_keys);
    localStorage.setItem(version_key, storage_version);
  }
  // Reads a stored preference, null for none or under ignored preferences.
  function stored_value_read(settings_values, storage_key) {
    storage_version_check(settings_values);
    if (preferences_are_ignored) return null;
    return JSON.parse(localStorage.getItem(storage_key));
  }
  const view_storage = {
    preferences_clear() {
      storage_version_check(settings_object);
      storage_sweep(settings_("STORAGE_OWNED_KEYS"));
    },
    value_read(storage_key) {
      return stored_value_read(settings_object, storage_key);
    },
    value_write(storage_key, stored_value) {
      storage_version_check(settings_object);
      if (preferences_are_ignored) return;
      localStorage.setItem(storage_key, JSON.stringify(stored_value));
    },
  };

  // Returns a dark mode query's text as a number, null for none.
  function dark_mode_query_value(settings_values, key_setting_name) {
    const query_value = new URLSearchParams(location.search).get(
      setting_read(settings_values, key_setting_name),
    );
    return query_value === null ? null : Number(query_value);
  }
  // Returns a truthy value when a page opens in dark mode, the one door.
  function dark_mode_opening_enabled(settings_values) {
    if (is_framed)
      return dark_mode_query_value(
        settings_values,
        "DARK_MODE_FRAME_QUERY_KEY_NAME",
      );
    const default_enabled = setting_read(
      settings_values,
      "DARK_MODE_ENABLED_DEFAULT",
    );
    const toggle_value = dark_mode_query_value(
      settings_values,
      "DARK_MODE_TOGGLE_QUERY_KEY_NAME",
    );
    // The query resets the preferences, then toggles on a truthy value.
    if (toggle_value !== null)
      return toggle_value ? !default_enabled : default_enabled;
    const stored_value = stored_value_read(
      settings_values,
      setting_read(settings_values, "STORAGE_KEY_VIEW_DARK_MODE"),
    );
    return stored_value === null ? default_enabled : stored_value;
  }
  function early_fill_enabled(settings_values) {
    return setting_read(
      settings_values,
      "STYLE_PAGE_BACKGROUND_EARLY_FILL_ENABLED",
    );
  }
  // Returns a mode's page background role, refusing one its palette lacks.
  function page_background_role(settings_values, is_enabled) {
    const [role_setting_name, palette_name] = is_enabled
      ? ["STYLE_PAGE_BACKGROUND_DARK_MODE_ROLE", "STYLE_COLOR_DARK_MODE"]
      : ["STYLE_PAGE_BACKGROUND_LIGHT_MODE_ROLE", "STYLE_COLOR_LIGHT_MODE"];
    const role_name = setting_read(settings_values, role_setting_name);
    const palette_roles = Object.values(
      setting_read(settings_values, palette_name),
    ).flat();
    if (!palette_roles.includes(role_name))
      window.throw_exception_(
        "str_error_setting_choice_unknown",
        role_setting_name,
        role_name,
      );
    return role_name;
  }
  // Shows a dark mode on the root, under early fill its page background too.
  function dark_mode_root_show(settings_values, is_enabled) {
    const root_element = document.documentElement;
    root_element.setAttribute(
      setting_read(settings_values, "DARK_MODE_ATTRIBUTE_NAME"),
      setting_read(
        settings_values,
        is_enabled ? "DARK_MODE_ENABLED_VALUE" : "DARK_MODE_DISABLED_VALUE",
      ),
    );
    if (!early_fill_enabled(settings_values)) return;
    root_element.style.background =
      "var(--" + page_background_role(settings_values, is_enabled) + ")";
  }
  // Shows the opening mode and its page background before the body parses.
  function page_early_fill(settings_values) {
    if (!early_fill_enabled(settings_values)) return;
    if (is_framed) palette_values_write(settings_values);
    dark_mode_root_show(
      settings_values,
      dark_mode_opening_enabled(settings_values),
    );
  }

  window.report_dark_mode_ = {
    opening_enabled: () => dark_mode_opening_enabled(settings_object),
    root_show: (is_enabled) =>
      dark_mode_root_show(settings_object, is_enabled),
    toggle_query_value: () =>
      dark_mode_query_value(
        settings_object,
        "DARK_MODE_TOGGLE_QUERY_KEY_NAME",
      ),
  };
  window.report_view_storage_ = view_storage;
  window.settings_ = settings_;
  window.settings_applied_values_ = settings_applied_values_;
  window.settings_names_ = settings_names_;
  window.settings_opening_ = settings_opening_;
  window.addEventListener(
    "message",
    window.try_catch_handler_(settings_request_handler),
  );
  if (is_framed) {
    // Fills under the written settings and those the address applies.
    opening_object = {
      ...written_object,
      ...settings_applied_values(written_object),
    };
    page_early_fill(opening_object);
    window.addEventListener(
      "message",
      window.try_catch_handler_(settings_relay_handler),
    );
    window.parent.postMessage(
      {
        report_ui: setting_read(
          opening_object,
          "SETTINGS_REQUEST_MESSAGE_NAME",
        ),
      },
      "*",
    );
  } else {
    settings_install(written_object);
    page_early_fill(settings_object);
    document.addEventListener(
      "DOMContentLoaded",
      window.try_catch_handler_(held_scripts_unframed_check),
    );
  }
})();
