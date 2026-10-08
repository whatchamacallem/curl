// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.report_ui_ = window.try_catch_handler_(function () {
  "use strict";

  const CALLERS_VIEW_KEY = settings_("CALLERS_VIEW_KEY");
  const DARK_MODE_ATTRIBUTE_NAME = settings_("DARK_MODE_ATTRIBUTE_NAME");
  const DARK_MODE_DISABLED_VALUE = settings_("DARK_MODE_DISABLED_VALUE");
  const DARK_MODE_ENABLED_DEFAULT = settings_("DARK_MODE_ENABLED_DEFAULT");
  const DARK_MODE_ENABLED_VALUE = settings_("DARK_MODE_ENABLED_VALUE");
  const DRAG_DIRECTION_THRESHOLD_PX = settings_("DRAG_DIRECTION_THRESHOLD_PX");
  const FLAME_GRAPH_LOCAL_PROFILE_PATH = settings_(
    "FLAME_GRAPH_LOCAL_PROFILE_PATH",
  );
  const FLAME_GRAPH_VIEW_ENTRY = settings_("FLAME_GRAPH_VIEW_ENTRY");
  const HEAT_MAP_VIEW_ENTRY = settings_("HEAT_MAP_VIEW_ENTRY");
  const MENU_DIGIT_KEY_COUNT = settings_("MENU_DIGIT_KEY_COUNT");
  const MENU_FLASH_DURATION_MS = settings_("MENU_FLASH_DURATION_MS");
  const MENU_PULLDOWN_KEY_NAMES = settings_("MENU_PULLDOWN_KEY_NAMES");
  const MENU_PULLDOWN_LINE_NUMBER_PATTERN = settings_(
    "MENU_PULLDOWN_LINE_NUMBER_PATTERN",
  );
  const MENU_PULLDOWN_OPENING_KEY_PATTERN = settings_(
    "MENU_PULLDOWN_OPENING_KEY_PATTERN",
  );
  const MENU_PULLDOWN_SKIPPED_KEY_NAMES = settings_(
    "MENU_PULLDOWN_SKIPPED_KEY_NAMES",
  );
  const MENU_SCALE_KEY_STEPS = settings_("MENU_SCALE_KEY_STEPS");
  const NUMBER_FRACTION_DIGITS = settings_("NUMBER_FRACTION_DIGITS");
  const NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES = settings_(
    "NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES",
  );
  const SETTINGS_DEBUG_HASH_KEY_NAME = settings_(
    "SETTINGS_DEBUG_HASH_KEY_NAME",
  );
  const SETTINGS_VIEW_ENTRY = settings_("SETTINGS_VIEW_ENTRY");
  const STORAGE_KEY_VIEW_DARK_MODE = settings_("STORAGE_KEY_VIEW_DARK_MODE");
  const STORAGE_KEY_VIEW_SCALE = settings_("STORAGE_KEY_VIEW_SCALE");
  const STORAGE_OWNED_KEYS = settings_("STORAGE_OWNED_KEYS");
  const STORAGE_VERSION = settings_("STORAGE_VERSION");
  const STORAGE_VERSION_KEY = settings_("STORAGE_VERSION_KEY");
  const STYLE_DESIGN_COORDINATES_WIDTH_PX = settings_(
    "STYLE_DESIGN_COORDINATES_WIDTH_PX",
  );
  const STYLE_DESIGN_FONT_CHARACTER_WIDTH_PX = settings_(
    "STYLE_DESIGN_FONT_CHARACTER_WIDTH_PX",
  );
  const STYLE_DESIGN_FONT_FIT_PROPERTY = settings_(
    "STYLE_DESIGN_FONT_FIT_PROPERTY",
  );
  const STYLE_DESIGN_FONT_SIZE_PX = settings_("STYLE_DESIGN_FONT_SIZE_PX");
  const STYLE_DESIGN_MINIMUM_WINDOW_WIDTH_PX = settings_(
    "STYLE_DESIGN_MINIMUM_WINDOW_WIDTH_PX",
  );
  const STYLE_DESIGN_SCALE_DEFAULT_MULTIPLE = settings_(
    "STYLE_DESIGN_SCALE_DEFAULT_MULTIPLE",
  );
  const STYLE_DESIGN_SCALE_DEFAULT_STOP = settings_(
    "STYLE_DESIGN_SCALE_DEFAULT_STOP",
  );
  const STYLE_DESIGN_SCALE_LARGEST_MULTIPLE = settings_(
    "STYLE_DESIGN_SCALE_LARGEST_MULTIPLE",
  );
  const STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE = settings_(
    "STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE",
  );
  const STYLE_DESIGN_SCALE_STOP_COUNT = settings_(
    "STYLE_DESIGN_SCALE_STOP_COUNT",
  );
  const STYLE_DESIGN_SCALE_STOP_MULTIPLE_FRACTION_DIGITS = settings_(
    "STYLE_DESIGN_SCALE_STOP_MULTIPLE_FRACTION_DIGITS",
  );
  const STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY = settings_(
    "STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY",
  );
  const STYLE_HEAT_COLOR_STOPS = settings_("STYLE_HEAT_COLOR_STOPS");
  const STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS = settings_(
    "STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS",
  );
  const STYLE_PAGE_FONT_FAMILY = settings_("STYLE_PAGE_FONT_FAMILY");
  const STYLE_PANE_SPLITTER_KEY_STEP_CHARS = settings_(
    "STYLE_PANE_SPLITTER_KEY_STEP_CHARS",
  );
  const STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS = settings_(
    "STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS",
  );
  const STYLE_TABLE_GROW_COLUMN_NARROWEST_CHARS = settings_(
    "STYLE_TABLE_GROW_COLUMN_NARROWEST_CHARS",
  );
  const STYLE_TEXT_SCROLLBAR_THUMB_SHORTEST_CHARS = settings_(
    "STYLE_TEXT_SCROLLBAR_THUMB_SHORTEST_CHARS",
  );
  const TABLE_MARKDOWN_COLUMN_NARROWEST_CHARS = settings_(
    "TABLE_MARKDOWN_COLUMN_NARROWEST_CHARS",
  );
  const TABLE_ROW_COUNT_CHOICES = settings_("TABLE_ROW_COUNT_CHOICES");
  const TEXT_SCROLLBAR_WHEEL_DELTA_PER_NOTCH = settings_(
    "TEXT_SCROLLBAR_WHEEL_DELTA_PER_NOTCH",
  );
  const TEXT_SCROLLBAR_WHEEL_NOTCH_LINES = settings_(
    "TEXT_SCROLLBAR_WHEEL_NOTCH_LINES",
  );
  const WIDGET_KEY_NAMES = settings_("WIDGET_KEY_NAMES");

  const ADDRESS_KEY_NAMES = [
    "test",
    "view",
    "file",
    "line",
    "function",
    "localProfilePath",
    "setting",
    SETTINGS_DEBUG_HASH_KEY_NAME,
  ];
  const ADDRESS_VIEW_KEY_NAMES = new Map([
    [CALLERS_VIEW_KEY, []],
    [FLAME_GRAPH_VIEW_ENTRY[0], ["localProfilePath"]],
    [HEAT_MAP_VIEW_ENTRY[0], ["file", "line", "function"]],
    [SETTINGS_VIEW_ENTRY[0], ["setting"]],
  ]);
  const CH_UNIT_GLYPH = "0";
  const DESIGN_SCALE_LAST_STOP = STYLE_DESIGN_SCALE_STOP_COUNT - 1;
  const DESIGN_SCALE_LOWER_TRAVEL_SHARE =
    STYLE_DESIGN_SCALE_DEFAULT_STOP / DESIGN_SCALE_LAST_STOP;
  const PULLDOWN_COMMAND_KEY_NAMES = Object.values(MENU_PULLDOWN_KEY_NAMES);
  const PULLDOWN_HIGHLIGHTED_ENTRY_CLASS = "highlighted-entry-";
  const RAMP_CHANNEL_STOPS = STYLE_HEAT_COLOR_STOPS.map((hex) =>
    [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16)),
  );
  const REPORT_TOP_PAGE_HREF = new URL(
    "../index.html",
    document.currentScript.src,
  ).href;
  const SIGNED_PERCENT_AMOUNT_CHARS = (
    fixed_text(-100, NUMBER_FRACTION_DIGITS) + "%"
  ).length;
  const SMALLEST_PRINTED_PERCENT = 1 / 10 ** NUMBER_FRACTION_DIGITS;
  const STRIP_ENTRY_KIND_NAMES = ["action", "link", "pulldown", "text"];
  const STRIP_GAP_TEXT = window.ui_strings_.text_of("str_strip_gap");
  const STRIP_STATUS_SEPARATOR_TEXT = window.ui_strings_.text_of(
    "str_menu_status_separator",
  );
  const TABLE_HEADING_COUNT_BOX_WIDTH_CHARS =
    Math.max(
      ...TABLE_ROW_COUNT_CHOICES.map((row_count) => String(row_count).length),
    ) + STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS;
  const TEXT_SCROLLBAR_AXES = {
    horizontal: {
      backward_key: WIDGET_KEY_NAMES.left,
      client_size: "clientWidth",
      forward_key: WIDGET_KEY_NAMES.right,
      layout_size: "offsetWidth",
      pointer_along: "clientX",
      rect_size: "width",
      rect_start: "left",
      scroll_offset: "scrollLeft",
      scroll_size: "scrollWidth",
      wheel_delta: "deltaX",
    },
    vertical: {
      backward_key: WIDGET_KEY_NAMES.up,
      client_size: "clientHeight",
      forward_key: WIDGET_KEY_NAMES.down,
      layout_size: "offsetHeight",
      pointer_along: "clientY",
      rect_size: "height",
      rect_start: "top",
      scroll_offset: "scrollTop",
      scroll_size: "scrollHeight",
      wheel_delta: "deltaY",
    },
  };

  const is_framed = window.shared_is_framed_;
  const home_panel = document.getElementById("overview-home-");
  const view_frame = document.getElementById("overview-view-frame-");
  const is_scaled = !is_framed && !!home_panel;
  const page_element = document.getElementById("overview-page-");
  const page_scroll_box = document.getElementById("overview-page-scroll-box-");
  const page_scrollbar = document.querySelector(
    "#overview-page-scroll-box- ~ .page-text-scrollbar-",
  );
  const attached_headings = new WeakMap();
  const attached_scrollbars = new WeakMap();
  const wheel_taken_events = {
    horizontal: new WeakSet(),
    vertical: new WeakSet(),
  };
  const registered_panes = [];
  const rendered_strips = new WeakMap();
  const resize_settle_callbacks = [];
  const row_walks = new WeakMap();
  let settle_animation_frame = 0;
  let window_resize_is_pending = false;
  let storage_is_checked = false;
  let tests_pulldown_is_open = false;
  let dark_mode_is_enabled = null;
  let design_scale = 1;
  let design_scale_stop = null;

  function ramp_channels_at(fraction) {
    const scaled_position = fraction * (RAMP_CHANNEL_STOPS.length - 1);
    const index = Math.min(
      Math.max(Math.floor(scaled_position), 0),
      RAMP_CHANNEL_STOPS.length - 2,
    );
    const step_fraction = scaled_position - index;
    return [0, 1, 2].map((channel) => {
      const low_channel = RAMP_CHANNEL_STOPS[index][channel],
        high_channel = RAMP_CHANNEL_STOPS[index + 1][channel];
      return Math.round(
        low_channel + (high_channel - low_channel) * step_fraction,
      );
    });
  }

  function design_scale_half_of(is_lower_half) {
    return is_lower_half
      ? {
          from_multiple: STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE,
          to_multiple: STYLE_DESIGN_SCALE_DEFAULT_MULTIPLE,
          travel_start: 0,
          travel_width: DESIGN_SCALE_LOWER_TRAVEL_SHARE,
        }
      : {
          from_multiple: STYLE_DESIGN_SCALE_DEFAULT_MULTIPLE,
          to_multiple: STYLE_DESIGN_SCALE_LARGEST_MULTIPLE,
          travel_start: DESIGN_SCALE_LOWER_TRAVEL_SHARE,
          travel_width: 1 - DESIGN_SCALE_LOWER_TRAVEL_SHARE,
        };
  }
  function design_scale_multiple_of(scale_stop) {
    const travel_fraction = scale_stop / DESIGN_SCALE_LAST_STOP;
    const half = design_scale_half_of(
      travel_fraction < DESIGN_SCALE_LOWER_TRAVEL_SHARE,
    );
    const half_fraction =
      (travel_fraction - half.travel_start) / half.travel_width;
    const multiple =
      half.from_multiple *
      Math.pow(half.to_multiple / half.from_multiple, half_fraction);
    const digit_count = STYLE_DESIGN_SCALE_STOP_MULTIPLE_FRACTION_DIGITS;
    return rounded_units(multiple, digit_count) / Math.pow(10, digit_count);
  }
  function design_scale_stop_now() {
    return design_scale_stop;
  }
  function design_scale_stop_check(scale_stop) {
    if (
      !Number.isInteger(scale_stop) ||
      scale_stop < 0 ||
      scale_stop > DESIGN_SCALE_LAST_STOP
    ) {
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    }
  }
  function design_scale_stop_nearest(wanted_multiple) {
    const distance_of = (scale_stop) =>
      Math.abs(design_scale_multiple_of(scale_stop) - wanted_multiple);
    let nearest_stop = 0;
    for (
      let scale_stop = 1;
      scale_stop <= DESIGN_SCALE_LAST_STOP;
      scale_stop++
    ) {
      if (distance_of(scale_stop) < distance_of(nearest_stop))
        nearest_stop = scale_stop;
    }
    return nearest_stop;
  }
  // Reads the stored scale itself and answers the stop nearest to it.
  function design_scale_stored_stop() {
    const stored_multiple = view_storage.value_read(STORAGE_KEY_VIEW_SCALE);
    if (stored_multiple === null) return STYLE_DESIGN_SCALE_DEFAULT_STOP;
    if (
      typeof stored_multiple !== "number" ||
      stored_multiple < STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE ||
      stored_multiple > STYLE_DESIGN_SCALE_LARGEST_MULTIPLE
    ) {
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    }
    return design_scale_stop_nearest(stored_multiple);
  }
  // Moves the scale to a stop, null the default, storing the scale itself.
  function design_scale_stop_set(scale_stop) {
    const shown_stop =
      scale_stop === null ? STYLE_DESIGN_SCALE_DEFAULT_STOP : scale_stop;
    design_scale_stop_check(shown_stop);
    design_scale_stop = shown_stop;
    view_storage.value_write(
      STORAGE_KEY_VIEW_SCALE,
      scale_stop === null ? null : design_scale_multiple_of(scale_stop),
    );
    design_scale_settle();
  }
  function font_fit_apply() {
    const context = document.createElement("canvas").getContext("2d");
    const wanted_font =
      STYLE_DESIGN_FONT_SIZE_PX + "px " + STYLE_PAGE_FONT_FAMILY;
    const default_font = context.font;
    context.font = wanted_font;
    if (context.font === default_font) {
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    }
    const measured_px = context.measureText(CH_UNIT_GLYPH).width;
    document.documentElement.style.setProperty(
      STYLE_DESIGN_FONT_FIT_PROPERTY,
      String(STYLE_DESIGN_FONT_CHARACTER_WIDTH_PX / measured_px),
    );
  }
  function design_scale_root_zoom_of() {
    if (is_framed) return 1;
    const window_width_px = Math.max(
      document.documentElement.clientWidth,
      STYLE_DESIGN_MINIMUM_WINDOW_WIDTH_PX,
    );
    return window_width_px / STYLE_DESIGN_COORDINATES_WIDTH_PX;
  }
  function design_scale_apply() {
    const root_element = document.documentElement;
    const root_zoom = design_scale_root_zoom_of();
    const multiple = is_scaled
      ? design_scale_multiple_of(design_scale_stop)
      : 1;
    const wanted = root_zoom * multiple;
    if (!isFinite(wanted) || !(wanted > 0)) {
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    }
    design_scale = wanted;
    root_element.style.zoom = String(root_zoom);
    root_element.style.setProperty(
      STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY,
      root_element.clientHeight / root_zoom + "px",
    );
    if (!is_scaled) return;
    page_element.style.minWidth = STYLE_DESIGN_COORDINATES_WIDTH_PX + "px";
    home_panel.style.zoom = String(multiple);
    view_frame.style.zoom = String(multiple);
    home_panel.style.setProperty(
      STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY,
      root_element.clientHeight / wanted + "px",
    );
  }
  function design_px(screen_px) {
    return screen_px / design_scale;
  }

  function dark_mode_enabled_now_() {
    return dark_mode_is_enabled;
  }
  function dark_mode_state_of(is_enabled) {
    return is_enabled ? DARK_MODE_ENABLED_VALUE : DARK_MODE_DISABLED_VALUE;
  }
  // Shows a dark mode on the page, storing nothing.
  function dark_mode_show(is_enabled) {
    dark_mode_is_enabled = is_enabled;
    document.documentElement.setAttribute(
      DARK_MODE_ATTRIBUTE_NAME,
      dark_mode_state_of(is_enabled),
    );
  }
  // Stores the dark mode the user chose, null the default, then shows it.
  function dark_mode_set_(is_enabled) {
    view_storage.value_write(
      STORAGE_KEY_VIEW_DARK_MODE,
      is_enabled === null ? null : dark_mode_state_of(is_enabled),
    );
    dark_mode_show(
      is_enabled === null ? DARK_MODE_ENABLED_DEFAULT : is_enabled,
    );
  }
  function dark_mode_stored_enabled_() {
    const stored_value = view_storage.value_read(STORAGE_KEY_VIEW_DARK_MODE);
    if (stored_value === null) return DARK_MODE_ENABLED_DEFAULT;
    if (stored_value === DARK_MODE_ENABLED_VALUE) return true;
    if (stored_value === DARK_MODE_DISABLED_VALUE) return false;
    throw new Error(window.ui_strings_.text_of("str_error_internal"));
  }
  function dark_mode_stored_apply_() {
    dark_mode_show(dark_mode_stored_enabled_());
  }

  function rounded_units(value, digit_count) {
    const scaled = Math.abs(value) * Math.pow(10, digit_count);
    const whole = Math.floor(scaled);
    return scaled - whole >= 0.5 ? whole + 1 : whole;
  }
  function fixed_text(value, digit_count) {
    const whole = rounded_units(value, digit_count);
    const sign = value < 0 && whole !== 0 ? "-" : "";
    const digits = String(whole).padStart(digit_count + 1, "0");
    if (!digit_count) return sign + digits;
    return (
      sign +
      digits.slice(0, digits.length - digit_count) +
      "." +
      digits.slice(digits.length - digit_count)
    );
  }
  function human_text(number) {
    let value = number,
      unit = "";
    for (const candidate of ["K", "M", "G", "T"]) {
      if (value < 999.5) break;
      value /= 1000;
      unit = candidate;
    }
    return (
      (unit && value < 9.95 ? fixed_text(value, 1) : fixed_text(value, 0)) +
      unit
    );
  }
  function percent_text(percent) {
    if (percent >= SMALLEST_PRINTED_PERCENT) {
      return fixed_text(percent, NUMBER_FRACTION_DIGITS) + "%";
    }
    if (percent > 0) {
      return "≈" + fixed_text(0, NUMBER_FRACTION_DIGITS) + "%";
    }
    return "";
  }
  function signed_human_text(number) {
    if (!number) return "";
    return (number < 0 ? "-" : "") + human_text(Math.abs(number));
  }
  function diff_share_of(delta, baseline) {
    const baseline_count = baseline === null ? 0 : baseline;
    if (delta < -baseline_count) {
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    }
    if (!delta) return 0;
    return baseline_count ? (100 * delta) / baseline_count : Infinity;
  }
  function signed_percent_text(percent, is_line = false) {
    if (!percent) return is_line ? "" : zero_percent_text();
    const arrow = percent < 0 ? "▼" : "▲";
    const times = percent / 100;
    let amount_text;
    if (percent === Infinity) {
      amount_text = "∞%";
    } else if (Math.abs(percent) < SMALLEST_PRINTED_PERCENT) {
      amount_text = "≈" + fixed_text(0, NUMBER_FRACTION_DIGITS) + "%";
    } else if (percent <= 100) {
      amount_text = fixed_text(percent, NUMBER_FRACTION_DIGITS) + "%";
    } else if (times >= NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES) {
      amount_text = "≈∞%";
    } else {
      amount_text = fixed_text(times, NUMBER_FRACTION_DIGITS) + "x";
    }
    if (!is_line) return arrow + amount_text;
    return arrow + amount_text.padStart(SIGNED_PERCENT_AMOUNT_CHARS);
  }
  function zero_percent_text() {
    return fixed_text(0, NUMBER_FRACTION_DIGITS) + "%";
  }

  function parent_post(payload) {
    if (is_framed) window.parent.postMessage(payload, "*");
  }
  function parent_listen(on_parent_message) {
    window.addEventListener(
      "message",
      window.try_catch_handler_((message_event) => {
        if (is_framed && message_event.source === window.parent) {
          on_parent_message(message_event.data);
        }
      }),
    );
  }
  function hash_value_encode(value) {
    return encodeURIComponent(value).replace(/%2F/g, "/");
  }

  function address_error(string_id, fill_values) {
    return new Error(window.ui_strings_.text_fill(string_id, fill_values));
  }
  function address_value_decode(part, encoded_value) {
    try {
      return decodeURIComponent(encoded_value);
    } catch (decode_error) {
      if (!(decode_error instanceof URIError)) throw decode_error;
      throw new Error(
        window.ui_strings_.text_fill("str_error_hash_part_unknown", [part]),
        { cause: decode_error },
      );
    }
  }
  function address_parts_check(parsed_address) {
    for (const key_name of ADDRESS_KEY_NAMES) {
      if (parsed_address[key_name] === "")
        throw address_error("str_error_hash_value_empty", [key_name]);
    }
    const is_home = ADDRESS_KEY_NAMES.every(
      (key_name) =>
        parsed_address[key_name] === null ||
        key_name === SETTINGS_DEBUG_HASH_KEY_NAME,
    );
    if (parsed_address.test === null && !is_home)
      throw address_error("str_error_hash_test_missing", []);
    if (parsed_address.test !== null && parsed_address.view === null)
      throw address_error("str_error_hash_view_missing", [
        parsed_address.test,
      ]);
    if (is_home) return;
    if (!ADDRESS_VIEW_KEY_NAMES.has(parsed_address.view))
      throw address_error("str_error_hash_view_unknown", [
        parsed_address.view,
      ]);
    for (const key_name of ADDRESS_KEY_NAMES.slice(2)) {
      if (
        parsed_address[key_name] !== null &&
        key_name !== SETTINGS_DEBUG_HASH_KEY_NAME &&
        !ADDRESS_VIEW_KEY_NAMES.get(parsed_address.view).includes(key_name)
      )
        throw address_error("str_error_hash_part_misplaced", [
          key_name,
          parsed_address.view,
        ]);
    }
    if (parsed_address.line !== null && parsed_address.file === null)
      throw address_error("str_error_hash_file_missing", [
        parsed_address.line,
      ]);
    if (
      parsed_address.function !== null &&
      (parsed_address.file !== null || parsed_address.line !== null)
    )
      throw address_error("str_error_hash_function_conflicting", [
        parsed_address.function,
      ]);
    if (
      parsed_address.line !== null &&
      !/^[1-9][0-9]*$/.test(parsed_address.line)
    )
      throw address_error("str_error_hash_line_unusable", [
        parsed_address.line,
      ]);
  }
  function address_of_hash(hash) {
    const parsed_address = Object.fromEntries(
      ADDRESS_KEY_NAMES.map((key_name) => [key_name, null]),
    );
    const address_text = hash.replace(/^#/, "");
    for (const part of address_text ? address_text.split("&") : []) {
      const equals_index = part.indexOf("=");
      const key_name = part.slice(0, equals_index);
      if (equals_index < 0 || !ADDRESS_KEY_NAMES.includes(key_name))
        throw address_error("str_error_hash_part_unknown", [part]);
      if (parsed_address[key_name] !== null)
        throw address_error("str_error_hash_part_repeated", [key_name]);
      parsed_address[key_name] = address_value_decode(
        part,
        part.slice(equals_index + 1),
      );
    }
    address_parts_check(parsed_address);
    if (parsed_address.line !== null)
      parsed_address.line = Number(parsed_address.line);
    return Object.freeze(parsed_address);
  }
  // Writes a hash, carrying the settings the page's own hash applies.
  function address_hash_of(partial_address) {
    const full_address = {
      ...partial_address,
      [SETTINGS_DEBUG_HASH_KEY_NAME]:
        partial_address[SETTINGS_DEBUG_HASH_KEY_NAME] ??
        address_of_hash(location.hash)[SETTINGS_DEBUG_HASH_KEY_NAME],
    };
    const hash_parts = [];
    for (const key_name of ADDRESS_KEY_NAMES) {
      if (full_address[key_name] == null) continue;
      hash_parts.push(
        `${key_name}=${hash_value_encode(String(full_address[key_name]))}`,
      );
    }
    return "#" + hash_parts.join("&");
  }
  function address_home_hash_of(test_name, view_key) {
    return address_hash_of({
      test: test_name,
      view: view_key,
      localProfilePath:
        view_key === FLAME_GRAPH_VIEW_ENTRY[0]
          ? FLAME_GRAPH_LOCAL_PROFILE_PATH
          : null,
    });
  }
  function click_is_plain(click_event) {
    return (
      !click_event.defaultPrevented &&
      !click_event.button &&
      !click_event.altKey &&
      !click_event.ctrlKey &&
      !click_event.metaKey &&
      !click_event.shiftKey
    );
  }
  function address_link_hash_of(click_event) {
    const link_element = click_event.target.closest('a[href^="#"]');
    return link_element && !link_element.target && click_is_plain(click_event)
      ? address_hash_of(address_of_hash(link_element.getAttribute("href")))
      : "";
  }
  function address_page_href_of(checked_address) {
    if (checked_address.view === CALLERS_VIEW_KEY)
      return encodeURIComponent(checked_address.test) + "/index.html";
    if (checked_address.view === HEAT_MAP_VIEW_ENTRY[0])
      return HEAT_MAP_VIEW_ENTRY[1];
    if (checked_address.view === FLAME_GRAPH_VIEW_ENTRY[0])
      return FLAME_GRAPH_VIEW_ENTRY[1];
    if (checked_address.view === SETTINGS_VIEW_ENTRY[0])
      return SETTINGS_VIEW_ENTRY[1];
    throw new Error(window.ui_strings_.text_of("str_error_internal"));
  }
  // Answers the link to the top page at a hash, the address the menu shows.
  function address_top_href_of(hash) {
    return REPORT_TOP_PAGE_HREF + hash;
  }
  function address_request_send(hash) {
    const carried_hash = address_hash_of(address_of_hash(hash));
    if (is_framed)
      parent_post({ report_ui: "address_request", hash: carried_hash });
    else location.assign(address_top_href_of(carried_hash));
  }
  function settings_apply_send(setting_name, setting_value) {
    parent_post({ report_ui: "settings_apply", setting_name, setting_value });
  }

  function pulldown_key_is_command(key_name) {
    return PULLDOWN_COMMAND_KEY_NAMES.includes(key_name);
  }
  function pulldown_key_of(key_event) {
    const key_name = key_event.key;
    const is_plain =
      !key_event.defaultPrevented &&
      !key_event.isComposing &&
      !key_event.altKey &&
      !key_event.ctrlKey &&
      !key_event.metaKey;
    const is_typed =
      key_name.length === 1 &&
      !MENU_PULLDOWN_SKIPPED_KEY_NAMES.includes(key_name);
    return is_plain && (is_typed || pulldown_key_is_command(key_name))
      ? key_name
      : "";
  }
  function view_key_opens_tests_pulldown(key_name) {
    return new RegExp(MENU_PULLDOWN_OPENING_KEY_PATTERN).test(key_name);
  }
  function view_key_forward(key_name, is_repeat) {
    const is_command_key = pulldown_key_is_command(key_name);
    if (!is_framed || (is_command_key && !tests_pulldown_is_open))
      return false;
    if (view_key_opens_tests_pulldown(key_name)) tests_pulldown_is_open = true;
    parent_post({
      report_ui: "menu_key_pressed",
      key: key_name,
      repeat: is_repeat,
    });
    return true;
  }
  function view_key_tests_pulldown_closed() {
    tests_pulldown_is_open = false;
  }
  function widget_key_of(key_event) {
    const is_plain =
      !key_event.defaultPrevented &&
      !key_event.isComposing &&
      !key_event.altKey &&
      !key_event.ctrlKey &&
      !key_event.metaKey &&
      !key_event.shiftKey;
    return is_plain ? key_event.key : "";
  }
  function widget_key_activates(key_name) {
    return (
      key_name === WIDGET_KEY_NAMES.activate ||
      key_name === WIDGET_KEY_NAMES.click
    );
  }
  function link_click_key_take(key_event) {
    if (
      widget_key_of(key_event) !== WIDGET_KEY_NAMES.click ||
      !key_event.target.matches("a[href]")
    )
      return;
    key_event.preventDefault();
    if (!key_event.repeat) key_event.target.click();
  }
  // Meets the frame's downward strings, and sends input up when asked.
  function view_activate(view_options) {
    if (view_options.forwards_input) {
      document.addEventListener(
        "click",
        window.try_catch_handler_((click_event) => {
          const link_hash = address_link_hash_of(click_event);
          if (!link_hash) return;
          click_event.preventDefault();
          address_request_send(link_hash);
        }),
      );
      document.addEventListener(
        "keydown",
        window.try_catch_handler_((key_event) => {
          link_click_key_take(key_event);
          const key_name = pulldown_key_of(key_event);
          if (key_name && view_key_forward(key_name, key_event.repeat))
            key_event.preventDefault();
        }),
      );
    }
    parent_listen((message_data) => {
      const message_name = message_data.report_ui;
      if (message_name === "layout_reset") {
        layout_reset();
        dark_mode_show(message_data.dark_mode_enabled);
        if (view_options.dark_mode_apply) view_options.dark_mode_apply();
        if (view_options.preferences_apply) view_options.preferences_apply();
      } else if (message_name === "dark_mode_show") {
        dark_mode_show(message_data.dark_mode_enabled);
        if (view_options.dark_mode_arrive) view_options.dark_mode_arrive();
      } else if (message_name === "dark_mode_apply") {
        dark_mode_show(message_data.dark_mode_enabled);
        if (view_options.dark_mode_apply) view_options.dark_mode_apply();
      } else if (message_name === "recenter") {
        if (view_options.recenter) view_options.recenter();
      } else if (message_name === "tests_pulldown_closed")
        view_key_tests_pulldown_closed();
      else if (message_name !== "settings_relay")
        throw new Error(window.ui_strings_.text_of("str_error_internal"));
    });
    parent_post({ report_ui: "dark_mode_request" });
  }

  function pulldown_pattern_of(search_text) {
    try {
      return new RegExp(search_text, "i");
    } catch (pattern_error) {
      if (!(pattern_error instanceof SyntaxError)) throw pattern_error;
      return null;
    }
  }
  function pulldown_opening_key_is(key_name) {
    return (
      key_name.length === 1 &&
      !Object.prototype.hasOwnProperty.call(MENU_SCALE_KEY_STEPS, key_name)
    );
  }
  // Turns a cell into a text pulldown whose typed box is the cell itself.
  function pulldown_attach(root_element, pulldown_options) {
    const element_render = window.shared_element_render_;
    root_element.innerHTML =
      element_render("span", {}, "") +
      element_render(
        "span",
        {
          class: "menu-pulldown-search-box-",
          style: `width:${pulldown_options.box_width_chars}ch`,
        },
        "",
      ) +
      element_render(
        "span",
        { class: "menu-pulldown-entry-box-" },
        element_render(
          "span",
          { class: "menu-pulldown-entry-list-", role: "listbox" },
          "",
        ) +
          element_render(
            "span",
            { class: "page-text-scrollbar- vertical-", "aria-hidden": "true" },
            "",
          ),
      );
    const [label_box, search_box, entry_box] = root_element.children;
    const [entry_list, list_scrollbar] = entry_box.children;
    const no_match_note = window.shared_element_of_(
      element_render(
        "span",
        {},
        window.shared_html_escape_(window.ui_strings_.text_of("str_no_match")),
      ),
    );
    let entries = [],
      entries_line_number = 0,
      highlight_index = 0,
      is_open = false,
      matches = [],
      search_text = "";

    function highlight_set(entry_index) {
      highlight_index = entry_index;
      for (const entry_element of entries) {
        const is_highlighted = entry_element === matches[highlight_index];
        entry_element.classList.toggle(
          PULLDOWN_HIGHLIGHTED_ENTRY_CLASS,
          is_highlighted,
        );
        entry_element.setAttribute("aria-selected", String(is_highlighted));
      }
    }
    function highlight_step(step_count) {
      if (!matches.length) return;
      highlight_set(
        Math.min(
          Math.max(highlight_index + step_count, 0),
          matches.length - 1,
        ),
      );
      matches[highlight_index].scrollIntoView({ block: "nearest" });
    }
    function search_parts_of(typed_text) {
      const line_match =
        pulldown_options.reads_line_number &&
        new RegExp(MENU_PULLDOWN_LINE_NUMBER_PATTERN).exec(typed_text);
      return line_match ? [line_match[1], +line_match[2]] : [typed_text, 0];
    }
    function entries_offer(line_number) {
      entries_line_number = line_number;
      entries = pulldown_options.entries_of(line_number);
      for (const entry_element of entries) {
        entry_element.setAttribute("role", "option");
        entry_element.tabIndex = -1;
      }
    }
    function entries_filter() {
      const [filter_text, line_number] = search_parts_of(search_text);
      if (line_number !== entries_line_number) entries_offer(line_number);
      const search_pattern = pulldown_pattern_of(filter_text);
      matches = entries.filter(
        (entry_element) =>
          !!search_pattern && search_pattern.test(entry_element.textContent),
      );
      entry_list.replaceChildren(
        ...(matches.length ? matches : [no_match_note]),
      );
      search_box.textContent =
        search_text || window.ui_strings_.text_of("str_pulldown_placeholder");
      entry_list.scrollTop = 0;
      highlight_set(0);
      list_scrollbar_handle.refresh();
    }
    function root_focus() {
      root_element.focus({ preventScroll: true });
      if (document.activeElement !== root_element)
        throw new Error(window.ui_strings_.text_of("str_error_internal"));
    }
    function pulldown_open(typed_text) {
      is_open = true;
      search_text = typed_text;
      root_element.classList.add("open-");
      root_element.setAttribute("aria-expanded", "true");
      label_box.hidden = true;
      search_box.hidden = false;
      entry_box.hidden = false;
      entries_offer(search_parts_of(search_text)[1]);
      entries_filter();
      root_focus();
    }
    function closed_show() {
      is_open = false;
      search_text = "";
      root_element.classList.remove("open-");
      root_element.setAttribute("aria-expanded", "false");
      label_box.hidden = false;
      search_box.hidden = true;
      entry_box.hidden = true;
    }
    function pulldown_close() {
      if (!is_open) return;
      closed_show();
      pulldown_options.on_close();
    }
    function search_text_set(typed_text) {
      search_text = typed_text;
      entries_filter();
      root_focus();
    }
    function pulldown_key_take(key_name) {
      if (!is_open) {
        if (!pulldown_opening_key_is(key_name)) return false;
        pulldown_open(key_name);
        return true;
      }
      switch (key_name) {
        case MENU_PULLDOWN_KEY_NAMES.close:
          pulldown_close();
          return true;
        case MENU_PULLDOWN_KEY_NAMES.erase:
          search_text_set([...search_text].slice(0, -1).join(""));
          return true;
        case MENU_PULLDOWN_KEY_NAMES.next:
          highlight_step(1);
          return true;
        case MENU_PULLDOWN_KEY_NAMES.previous:
          highlight_step(-1);
          return true;
        case MENU_PULLDOWN_KEY_NAMES.select:
          if (matches.length) matches[highlight_index].click();
          return true;
      }
      if (key_name.length !== 1) return false;
      search_text_set(search_text + key_name);
      return true;
    }

    root_element.classList.add("menu-pulldown-");
    root_element.setAttribute("role", "combobox");
    root_element.setAttribute("aria-haspopup", "listbox");
    root_element.tabIndex = 0;
    closed_show();
    const list_scrollbar_handle = text_scrollbar_attach(
      list_scrollbar,
      entry_list,
      "vertical",
    );
    root_element.addEventListener(
      "keydown",
      window.try_catch_handler_((key_event) => {
        const key_name =
          widget_key_of(key_event) || pulldown_key_of(key_event);
        if (!is_open && widget_key_activates(key_name)) {
          key_event.preventDefault();
          if (!key_event.repeat) pulldown_open("");
        } else if (key_name && pulldown_key_take(key_name))
          key_event.preventDefault();
      }),
    );
    root_element.addEventListener(
      "click",
      window.try_catch_handler_((click_event) => {
        if (!is_open && !entry_box.contains(click_event.target))
          pulldown_open("");
      }),
    );
    root_element.addEventListener(
      "focusout",
      window.try_catch_handler_((focus_event) => {
        if (!is_open || root_element.contains(focus_event.relatedTarget))
          return;
        // A page losing focus to another frame or window keeps the list open.
        setTimeout(
          window.try_catch_handler_(() => {
            if (
              is_open &&
              document.hasFocus() &&
              !root_element.contains(document.activeElement)
            )
              pulldown_close();
          }),
        );
      }),
    );
    entry_box.addEventListener("mousedown", default_prevent);
    entry_list.addEventListener(
      "click",
      window.try_catch_handler_((click_event) => {
        const entry_element = click_event.target.closest('[role="option"]');
        if (!entry_element || entry_element.parentElement !== entry_list)
          return;
        pulldown_close();
        if (!pulldown_options.on_select) return;
        click_event.preventDefault();
        pulldown_options.on_select(
          entry_element.getAttribute("data-entry-value-"),
        );
      }),
    );
    return {
      close: pulldown_close,
      is_open: () => is_open,
      key_take: pulldown_key_take,
      label_set: (label_text) => {
        label_box.textContent = label_text;
      },
      open: pulldown_open,
    };
  }

  function strip_entry_of(entries, entry_name) {
    const found_entry = entries.find(
      (candidate_entry) => candidate_entry.name === entry_name,
    );
    if (!found_entry)
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    return found_entry;
  }
  function strip_number_text_of(numbered_index) {
    if (numbered_index >= MENU_DIGIT_KEY_COUNT)
      return window.ui_strings_.text_of("str_menu_unavailable_fill");
    return String((numbered_index + 1) % MENU_DIGIT_KEY_COUNT);
  }
  // Answers the text label of an entry as the strip draws it, number included.
  function strip_label_text_of(entries, entry_name) {
    const entry = strip_entry_of(entries, entry_name);
    const shown_text = entry.is_available
      ? entry.label
      : window.ui_strings_
          .text_of("str_menu_unavailable_fill")
          .repeat([...entry.label].length);
    if (!entry.is_numbered) return shown_text;
    const numbered_entries = entries.filter(
      (other_entry) => other_entry.is_numbered,
    );
    return window.ui_strings_.text_fill("str_menu_button", {
      number: strip_number_text_of(numbered_entries.indexOf(entry)),
      label: shown_text,
    });
  }
  function strip_widget_cells_markup(widget_text) {
    return Array.from(widget_text, (widget_character) =>
      window.shared_element_render_(
        "span",
        {},
        window.shared_html_escape_(widget_character),
      ),
    ).join("");
  }
  function strip_gap_cell_render() {
    return window.shared_element_render_(
      "td",
      { class: "menu-strip-gap-" },
      window.shared_html_escape_(STRIP_GAP_TEXT),
    );
  }
  // Writes an entry cell, a title as page emphasis, else a menu button.
  function strip_cell_render(entry, label_markup) {
    if (!STRIP_ENTRY_KIND_NAMES.includes(entry.kind))
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    const name_attributes = { "data-entry-name-": entry.name };
    if (entry.kind === "text")
      return window.shared_page_emphasis_render_(label_markup, {
        tag_name: "td",
        attributes: name_attributes,
      });
    const shown_markup =
      entry.kind === "pulldown" && entry.is_available ? "" : label_markup;
    const widget_markup = entry.is_widget
      ? window.shared_html_escape_(STRIP_GAP_TEXT) +
        window.shared_element_render_(
          "span",
          { class: "menu-button-widget-" },
          strip_widget_cells_markup(entry.widget_text),
        )
      : "";
    return window.shared_menu_button_render_(
      entry.kind,
      shown_markup + widget_markup,
      {
        tag_name: "td",
        href: entry.href,
        opens_new_tab: entry.opens_new_tab,
        is_unavailable: !entry.is_available,
        is_widget: entry.is_widget,
        attributes: name_attributes,
      },
    );
  }
  // Writes the status bar, one cell of links apart from the entry cells.
  function strip_status_cell_render(status_entries) {
    const link_markups = status_entries.map((status_entry) =>
      window.shared_element_render_(
        "a",
        { href: status_entry.href },
        window.shared_html_escape_(status_entry.label),
      ),
    );
    return window.shared_element_render_(
      "td",
      { class: "menu-status-bar-" },
      window.shared_html_escape_(STRIP_GAP_TEXT) +
        link_markups.join(
          window.shared_html_escape_(STRIP_STATUS_SEPARATOR_TEXT),
        ),
    );
  }
  // Renders a whole strip again from its entries, the one door for its cells.
  function strip_render(strip_element, entries, status_entries) {
    const cells_by_name = new Map();
    const digit_entries = new Map();
    const entries_by_name = new Map();
    const previous_strip = rendered_strips.get(strip_element);
    const pulldowns_by_name = new Map();
    const row_markups = [];
    let strip_row = null;

    function strip_cell_named(entry_name) {
      if (!cells_by_name.has(entry_name))
        throw new Error(window.ui_strings_.text_of("str_error_internal"));
      return cells_by_name.get(entry_name);
    }
    function entry_activate(entry) {
      const entry_cell = cells_by_name.get(entry.name);
      if (entry.kind === "pulldown")
        pulldowns_by_name.get(entry.name).open("");
      else if (entry.kind === "link")
        entry_cell.querySelector(":scope > a").click();
      else entry_cell.click();
    }
    function entry_click_take(click_event) {
      const entry_cell = click_event.target.closest("td.menu-button-");
      if (!entry_cell || entry_cell.parentElement !== strip_row) return;
      const entry = entries_by_name.get(
        entry_cell.getAttribute("data-entry-name-"),
      );
      if (!entry.is_available) return;
      if (entry.kind === "action") entry.on_activate(click_event);
      if (entry.kind !== "link" || !click_is_plain(click_event)) return;
      const entry_link = entry_cell.querySelector(":scope > a");
      if (!entry_link.contains(click_event.target)) entry_link.click();
      else if (entry.on_activate) entry.on_activate(click_event);
    }
    function entry_key_take(key_event) {
      const entry_cell = key_event.target;
      if (
        entry_cell.parentElement !== strip_row ||
        !widget_key_activates(widget_key_of(key_event))
      )
        return;
      const entry = entries_by_name.get(
        entry_cell.getAttribute("data-entry-name-"),
      );
      if (entry.kind === "pulldown") return;
      key_event.preventDefault();
      if (!key_event.repeat) entry_activate(entry);
    }
    function strip_flash(entry_name) {
      const entry_cell = strip_cell_named(entry_name);
      entry_cell.classList.add("flash-");
      setTimeout(
        window.try_catch_handler_(() => entry_cell.classList.remove("flash-")),
        MENU_FLASH_DURATION_MS,
      );
    }
    function strip_key_take(key_name, is_repeat) {
      for (const pulldown of pulldowns_by_name.values()) {
        if (pulldown.is_open()) return pulldown.key_take(key_name);
      }
      if (!digit_entries.has(key_name)) return false;
      if (!is_repeat) entry_activate(digit_entries.get(key_name));
      return true;
    }
    // Focuses the entry a digit reaches, opening a pulldown as its key does.
    function strip_numbered_entry_focus(number_text) {
      if (!digit_entries.has(number_text))
        throw new Error(
          window.ui_strings_.text_fill("str_error_strip_number_unusable", [
            number_text,
          ]),
        );
      const entry = digit_entries.get(number_text);
      const entry_cell = cells_by_name.get(entry.name);
      if (entry.kind === "pulldown") entry_activate(entry);
      else entry_cell.focus({ focusVisible: true, preventScroll: true });
    }
    function strip_pulldown_open(entry_name, search_text) {
      strip_cell_named(entry_name);
      if (!pulldowns_by_name.has(entry_name))
        throw new Error(window.ui_strings_.text_of("str_error_internal"));
      pulldowns_by_name.get(entry_name).open(search_text);
    }
    // Relabels a pulldown cell without a render, so focus stays where it is.
    function strip_pulldown_label_set(entry_name, label_text) {
      strip_cell_named(entry_name);
      if (!pulldowns_by_name.has(entry_name))
        throw new Error(window.ui_strings_.text_of("str_error_internal"));
      const labelled_entries = entries.map((entry) =>
        entry.name === entry_name ? { ...entry, label: label_text } : entry,
      );
      pulldowns_by_name
        .get(entry_name)
        .label_set(strip_label_text_of(labelled_entries, entry_name));
    }
    function strip_widget_text_set(entry_name, widget_text) {
      const widget_box = strip_cell_named(entry_name).querySelector(
        ".menu-button-widget-",
      );
      if (!widget_box)
        throw new Error(window.ui_strings_.text_of("str_error_internal"));
      widget_box.innerHTML = strip_widget_cells_markup(widget_text);
    }

    if (previous_strip) previous_strip.reset();
    for (const entry of entries) {
      if (entries_by_name.has(entry.name))
        throw new Error(window.ui_strings_.text_of("str_error_internal"));
      entries_by_name.set(entry.name, entry);
      const label_markup =
        entry.label_markup === null
          ? window.shared_html_escape_(
              strip_label_text_of(entries, entry.name),
            )
          : entry.label_markup;
      if (row_markups.length) row_markups.push(strip_gap_cell_render());
      row_markups.push(strip_cell_render(entry, label_markup));
    }
    if (status_entries.length)
      row_markups.push(
        strip_gap_cell_render(),
        strip_status_cell_render(status_entries),
      );
    entries
      .filter((entry) => entry.is_numbered)
      .forEach((entry, numbered_index) => {
        if (
          numbered_index < MENU_DIGIT_KEY_COUNT &&
          entry.is_available &&
          !entry.is_widget
        )
          digit_entries.set(strip_number_text_of(numbered_index), entry);
      });
    if (strip_element.contains(document.activeElement))
      document.activeElement.blur();
    strip_element.innerHTML = window.shared_element_render_(
      "table",
      { class: "menu-strip-table-" },
      window.shared_element_render_(
        "tbody",
        {},
        window.shared_element_render_("tr", {}, row_markups.join("")),
      ),
    );
    const strip_table = strip_element.firstElementChild;
    strip_row = strip_table.tBodies[0].rows[0];
    for (const entry_cell of strip_row.cells) {
      if (entry_cell.hasAttribute("data-entry-name-"))
        cells_by_name.set(
          entry_cell.getAttribute("data-entry-name-"),
          entry_cell,
        );
    }
    strip_table.addEventListener(
      "click",
      window.try_catch_handler_(entry_click_take),
    );
    strip_table.addEventListener(
      "keydown",
      window.try_catch_handler_(entry_key_take),
    );
    for (const entry of entries) {
      if (entry.kind !== "pulldown" || !entry.is_available) continue;
      const pulldown = pulldown_attach(
        cells_by_name.get(entry.name),
        entry.pulldown_options,
      );
      pulldown.label_set(strip_label_text_of(entries, entry.name));
      pulldowns_by_name.set(entry.name, pulldown);
    }
    rendered_strips.set(strip_element, {
      reset: () => pulldowns_by_name.forEach((pulldown) => pulldown.close()),
    });
    return {
      flash: strip_flash,
      key_take: strip_key_take,
      numbered_entry_focus: strip_numbered_entry_focus,
      pulldown_label_set: strip_pulldown_label_set,
      pulldown_open: strip_pulldown_open,
      widget_text_set: strip_widget_text_set,
    };
  }

  function width_total(widths) {
    return widths.reduce((total, width) => total + width, 0);
  }
  function column_longest(cell_rows, column_index) {
    let longest = 0;
    for (const row of cell_rows) {
      longest = Math.max(longest, row[column_index].text.length);
    }
    return longest;
  }
  function column_extents(columns, cell_rows, grow_index) {
    return columns.map((column, column_index) => {
      let content_chars;
      if (column.width != null) content_chars = column.width;
      else if (column_index === grow_index) {
        content_chars = STYLE_TABLE_GROW_COLUMN_NARROWEST_CHARS;
      } else {
        content_chars = column_longest(cell_rows, column_index);
        if (column.clip != null) {
          content_chars = Math.min(content_chars, column.clip);
        }
      }
      return { heading_chars: column.label.length, content_chars };
    });
  }
  function column_limits(extent) {
    const widest = Math.max(extent.heading_chars, extent.content_chars);
    return [
      extent.content_chars,
      widest + STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS,
    ];
  }
  function column_width_text(limits, column_index, grow_index) {
    const [narrowest, widest] = limits[column_index];
    const shared = limits.filter(
      (limit, other_index) => other_index !== grow_index,
    );
    const low_total = width_total(shared.map((limit) => limit[0]));
    const high_total = width_total(shared.map((limit) => limit[1]));
    if (column_index === grow_index) {
      return (
        `max(${narrowest}ch, 100cqw - clamp(${low_total}ch, ` +
        `100cqw - ${narrowest}ch, ${high_total}ch))`
      );
    }
    if (narrowest === widest) return narrowest + "ch";
    const grow_narrowest = grow_index >= 0 ? limits[grow_index][0] : 0;
    return (
      `clamp(${narrowest}ch, ${narrowest}ch + (100cqw - ` +
      `${low_total + grow_narrowest}ch) * ${widest - narrowest} / ` +
      `${high_total - low_total}, ${widest}ch)`
    );
  }

  const cell_normalize = (value) =>
    value && typeof value === "object"
      ? value
      : { text: value == null ? "" : String(value) };
  // Writes columns and rows as a markdown table, numbers right aligned.
  function table_markdown(columns, rows) {
    const cell_rows = rows.map((row) =>
      row.map((value) => ({
        text: cell_normalize(value).text.replaceAll("|", "\\|"),
      })),
    );
    const column_width_list = columns.map((column, column_index) =>
      Math.max(
        TABLE_MARKDOWN_COLUMN_NARROWEST_CHARS,
        column.label.length,
        column_longest(cell_rows, column_index),
      ),
    );
    const pad = (text, width, numeric) =>
      numeric ? text.padStart(width) : text.padEnd(width);
    const line = (cells) =>
      "| " +
      cells
        .map((text, column_index) =>
          pad(
            text,
            column_width_list[column_index],
            columns[column_index].numeric,
          ),
        )
        .join(" | ") +
      " |";
    const output_parts = [line(columns.map((column) => column.label))];
    const rule = columns.map((column, column_index) =>
      column.numeric
        ? "-".repeat(column_width_list[column_index] - 1) + ":"
        : "-".repeat(column_width_list[column_index]),
    );
    output_parts.push("| " + rule.join(" | ") + " |");
    for (const row of cell_rows) {
      output_parts.push(
        line(columns.map((column, column_index) => row[column_index].text)),
      );
    }
    return output_parts.join("\n");
  }
  // Reads the column titles and the rows a table shows into a markdown table.
  function table_markdown_of(table_element) {
    const title_row = table_element.tHead ? table_element.tHead.rows[0] : null;
    const body_rows = [...table_element.tBodies[0].rows];
    const sample_cells = [...(title_row || body_rows[0]).cells];
    const markdown_columns = sample_cells.map((sample_cell) => ({
      label: title_row ? sample_cell.textContent : "",
      numeric: sample_cell.classList.contains("numeric-"),
    }));
    const markdown_rows = body_rows.map((body_row) =>
      [...body_row.cells].map((body_cell) => body_cell.textContent),
    );
    return table_markdown(markdown_columns, markdown_rows);
  }
  function table_cell_render(cell, column) {
    const cell_attributes = {};
    const class_names = [column.numeric ? "numeric-" : "", column.cls || ""]
      .filter(Boolean)
      .join(" ");
    if (class_names) cell_attributes.class = class_names;
    if (cell.style) cell_attributes.style = cell.style;
    return window.shared_element_render_(
      "td",
      cell_attributes,
      cell.html != null ? cell.html : window.shared_html_escape_(cell.text),
    );
  }
  // Writes columns and rows as a table, the one table writer in JS.
  function table_render(table_key, columns, rows, table_options) {
    const element_render = window.shared_element_render_;
    const cell_rows = rows.map((row) => row.map(cell_normalize));
    const grow_index = table_options.fill
      ? columns.findIndex((column) => column.grow)
      : -1;
    const column_limit_list = column_extents(
      columns,
      cell_rows,
      grow_index,
    ).map(column_limits);
    const column_markup = column_limit_list
      .map((limit, column_index) => {
        const width_text = column_width_text(
          column_limit_list,
          column_index,
          grow_index,
        );
        return element_render(
          "col",
          { "data-min-": `${limit[0]}ch`, style: `width:${width_text}` },
          null,
        );
      })
      .join("");
    const title_markup = columns
      .map((column) =>
        element_render(
          "th",
          {
            ...(column.numeric ? { class: "numeric-" } : {}),
            title: column.label,
          },
          window.shared_html_escape_(column.label),
        ),
      )
      .join("");
    const body_markup = cell_rows
      .map((row, row_index) => {
        const row_href =
          table_options.row_href && table_options.row_href[row_index];
        const row_attributes = row_href
          ? { class: "row-link-", "data-href-": row_href }
          : table_options.row_attributes
            ? table_options.row_attributes[row_index]
            : {};
        return element_render(
          "tr",
          row_attributes,
          row
            .map((cell, column_index) =>
              table_cell_render(cell, columns[column_index]),
            )
            .join(""),
        );
      })
      .join("");
    const table_markup = element_render(
      "div",
      { class: "table-columns-" },
      element_render(
        "table",
        {
          class: ["columns-", table_options.cls || ""]
            .filter(Boolean)
            .join(" "),
          "data-key-": table_key,
        },
        element_render("colgroup", {}, column_markup) +
          element_render("thead", {}, element_render("tr", {}, title_markup)) +
          element_render("tbody", {}, body_markup),
      ),
    );
    if (table_options.bare) return table_markup;
    return element_render("div", { class: "table-box-" }, table_markup);
  }
  // Fills each marker with its markup, refusing a marker the template lacks.
  function template_fill(template_text, marker_values) {
    for (const marker of Object.keys(marker_values)) {
      if (!template_text.includes(marker))
        throw new Error(window.ui_strings_.text_of("str_error_internal"));
    }
    let filled_text = template_text;
    for (const [marker, markup] of Object.entries(marker_values))
      filled_text = filled_text.replaceAll(marker, () => markup);
    return filled_text;
  }

  // Binds or unbinds a press's move and every way that press can end.
  function listeners_bind(
    event_target,
    on_pointer_move,
    on_pointer_release,
    is_attaching,
  ) {
    const listener_method = is_attaching
      ? "addEventListener"
      : "removeEventListener";
    event_target[listener_method]("pointermove", on_pointer_move);
    event_target[listener_method]("pointerup", on_pointer_release);
    event_target[listener_method]("pointercancel", on_pointer_release);
    event_target[listener_method]("lostpointercapture", on_pointer_release);
  }
  function column_elements_of(table_element) {
    return [...table_element.querySelectorAll(":scope > colgroup > col")];
  }
  const default_prevent = window.try_catch_handler_((any_event) => {
    any_event.preventDefault();
  });
  const click_swallow = window.try_catch_handler_((click_event) => {
    click_event.preventDefault();
    click_event.stopPropagation();
  });
  const selection_drop = window.try_catch_handler_(() => {
    window.getSelection().removeAllRanges();
  });
  function click_swallow_next() {
    window.addEventListener("click", click_swallow, true);
    setTimeout(
      window.try_catch_handler_(() => {
        window.removeEventListener("click", click_swallow, true);
      }),
    );
  }
  // Answers sideways or vertical once past the drag direction threshold.
  function drag_direction_of(press_event, move_event) {
    const sideways_travel_px = design_px(
      move_event.clientX - press_event.clientX,
    );
    const vertical_travel_px = design_px(
      move_event.clientY - press_event.clientY,
    );
    const travel_px = Math.hypot(sideways_travel_px, vertical_travel_px);
    if (travel_px <= DRAG_DIRECTION_THRESHOLD_PX) return "";
    return Math.abs(vertical_travel_px) >= Math.abs(sideways_travel_px)
      ? "vertical"
      : "sideways";
  }
  // Answers the cell a column slide takes if this press moves sideways.
  function slide_cell_of(press_event) {
    const pressed_cell = press_event.target.closest("td, th");
    const is_slidable =
      !!pressed_cell &&
      pressed_cell.cellIndex >= 1 &&
      !!pressed_cell.closest("table").is_slide_attached;
    return is_slidable ? pressed_cell : null;
  }
  function table_slide_press(press_event, table_element) {
    const pressed_cell = slide_cell_of(press_event);
    if (
      press_event.button ||
      !pressed_cell ||
      pressed_cell.closest("table") !== table_element
    )
      return;
    const column_index = pressed_cell.cellIndex;
    const left_column = column_elements_of(table_element)[column_index - 1];
    const floor_text = left_column.getAttribute("data-min-");
    const start_width_px = design_px(
      pressed_cell.previousElementSibling.getBoundingClientRect().width,
    );
    let animation_frame = 0,
      is_sliding = false;
    const on_pointer_move = window.try_catch_handler_((move_event) => {
      if (move_event.pointerId !== press_event.pointerId) return;
      if (!is_sliding) {
        const drag_direction = drag_direction_of(press_event, move_event);
        if (!drag_direction) return;
        if (drag_direction === "vertical") {
          press_end();
          return;
        }
        is_sliding = true;
        selection_drop();
        document.addEventListener("selectionchange", selection_drop);
      }
      const wanted_width_px =
        start_width_px + design_px(move_event.clientX - press_event.clientX);
      left_column.style.width = `max(${floor_text}, ${wanted_width_px}px)`;
      if (animation_frame) return;
      animation_frame = requestAnimationFrame(
        window.try_catch_handler_(() => {
          animation_frame = 0;
          layout_refresh();
        }),
      );
    });
    const on_pointer_release = window.try_catch_handler_((release_event) => {
      if (release_event.pointerId !== press_event.pointerId) return;
      press_end();
      if (!is_sliding) return;
      document.removeEventListener("selectionchange", selection_drop);
      if (release_event.type === "pointerup") click_swallow_next();
    });
    function press_end() {
      listeners_bind(window, on_pointer_move, on_pointer_release, false);
      window.removeEventListener("dragstart", default_prevent, true);
    }
    listeners_bind(window, on_pointer_move, on_pointer_release, true);
    window.addEventListener("dragstart", default_prevent, true);
  }
  function table_slide_attach(table_element) {
    if (table_element.is_slide_attached) return;
    table_element.is_slide_attached = true;
    for (const column_element of column_elements_of(table_element)) {
      column_element.setAttribute(
        "data-start-width-",
        column_element.style.width,
      );
    }
    table_element.addEventListener(
      "pointerdown",
      window.try_catch_handler_((press_event) =>
        table_slide_press(press_event, table_element),
      ),
    );
  }
  function offsets_align(scroll_container) {
    let stacked_top_px = 0;
    for (const band_element of scroll_container.querySelectorAll(
      ":scope > .band-",
    )) {
      band_element.style.top = stacked_top_px + "px";
      stacked_top_px += design_px(band_element.getBoundingClientRect().height);
    }
    for (const header_cell of scroll_container.querySelectorAll("th")) {
      const owning_table =
        header_cell.closest(".table-box-") || scroll_container;
      if (owning_table === scroll_container) {
        header_cell.style.top = stacked_top_px + "px";
      }
    }
  }
  function layout_refresh(root_element) {
    root_element = root_element || document.body;
    const band_elements = [...root_element.querySelectorAll(".band-")];
    new Set(
      band_elements.map((band_element) => band_element.parentElement),
    ).forEach(offsets_align);
    for (const bar_element of root_element.querySelectorAll(
      ".page-text-scrollbar-",
    )) {
      const attached_scrollbar = attached_scrollbars.get(bar_element);
      if (attached_scrollbar) attached_scrollbar.refresh();
    }
  }
  function layout_activate(root_element) {
    root_element = root_element || document.body;
    const table_elements = root_element.querySelectorAll(
      ".table-columns- > table.columns-",
    );
    for (const table_element of table_elements) {
      table_slide_attach(table_element);
      if (table_element.tBodies[0].querySelector("a[href]"))
        table_rows_attach(table_element, "tr");
    }
    const heading_elements = root_element.querySelectorAll(".page-heading-");
    for (const heading_element of heading_elements) {
      if (!attached_headings.has(heading_element))
        page_heading_attach(heading_element, []);
    }
    const bar_elements = root_element.querySelectorAll(
      ":has(> .page-text-scroll-box-) > .page-text-scrollbar-",
    );
    for (const bar_element of bar_elements) {
      if (attached_scrollbars.has(bar_element)) continue;
      text_scrollbar_attach(
        bar_element,
        bar_element.parentElement.querySelector(
          ":scope > .page-text-scroll-box-",
        ),
        text_scrollbar_axis_of(bar_element),
      );
    }
    layout_refresh(root_element);
  }
  function layout_reset(root_element) {
    root_element = root_element || document.body;
    const column_elements = root_element.querySelectorAll(
      "col[data-start-width-]",
    );
    for (const column_element of column_elements) {
      column_element.style.width =
        column_element.getAttribute("data-start-width-");
    }
    for (const pane_entry of registered_panes) {
      if (!root_element.contains(pane_entry.pane_element)) continue;
      pane_entry.pane_width_forget();
    }
    const heading_elements = root_element.querySelectorAll(".page-heading-");
    for (const heading_element of heading_elements) {
      const attached_heading = attached_headings.get(heading_element);
      if (attached_heading) attached_heading.reset();
    }
    layout_refresh(root_element);
  }

  function scroller_of(focused_element) {
    let scrolling_box = focused_element.parentElement;
    while (!/^(auto|scroll)$/.test(getComputedStyle(scrolling_box).overflowY))
      scrolling_box = scrolling_box.parentElement;
    return scrolling_box;
  }
  function focus_reveal(focused_element) {
    focused_element.scrollIntoView({ block: "nearest", inline: "nearest" });
    const owning_table = focused_element.closest("table");
    if (!owning_table || !owning_table.tHead) return;
    const hidden_px =
      owning_table.tHead.rows[0].cells[0].getBoundingClientRect().bottom -
      focused_element.getBoundingClientRect().top;
    if (hidden_px > 0)
      scroller_of(focused_element).scrollTop -= design_px(hidden_px);
  }
  function tab_stop_move(previous_stop, next_stop, takes_focus) {
    if (previous_stop && previous_stop !== next_stop)
      previous_stop.tabIndex = -1;
    next_stop.tabIndex = 0;
    if (!takes_focus) return;
    next_stop.focus({ preventScroll: true });
    focus_reveal(next_stop);
  }
  function row_links_of(row_element) {
    return [...row_element.querySelectorAll("a[href]")].filter(
      (row_link) => row_link.closest("tr") === row_element,
    );
  }
  function walked_row_of(focused_element, table_body, row_selector) {
    const row_element = focused_element.closest("tr");
    const is_walked =
      !!row_element &&
      row_element.parentElement === table_body &&
      row_element.matches(row_selector);
    return is_walked ? row_element : null;
  }
  function walked_row_beside(row_element, row_selector, step_direction) {
    const sibling_name =
      step_direction > 0 ? "nextElementSibling" : "previousElementSibling";
    let sibling_row = row_element[sibling_name];
    while (sibling_row && !sibling_row.matches(row_selector))
      sibling_row = sibling_row[sibling_name];
    return sibling_row;
  }
  function walked_rows_in(table_body, row_selector) {
    return [...table_body.rows].filter((walked_row) =>
      walked_row.matches(row_selector),
    );
  }
  function table_row_tab_stop_set(row_element, takes_focus) {
    const owning_table = row_element.closest("table");
    const row_walk = row_walks.get(owning_table);
    if (!row_walk)
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    tab_stop_move(
      row_element.parentElement.querySelector(':scope > tr[tabindex="0"]'),
      row_element,
      takes_focus,
    );
    row_walk.tab_stop_row = row_element;
  }
  function table_row_key_take(key_event, table_body, row_selector) {
    const key_name = widget_key_of(key_event);
    const focused_element = key_event.target;
    const row_element = walked_row_of(
      focused_element,
      table_body,
      row_selector,
    );
    if (!key_name || !row_element) return;
    const row_links = row_links_of(row_element);
    const link_index = row_links.indexOf(focused_element);
    if (link_index >= 0 && widget_key_activates(key_name)) {
      link_click_key_take(key_event);
      return;
    }
    if (focused_element !== row_element && link_index < 0) return;
    if (widget_key_activates(key_name)) {
      key_event.preventDefault();
      const clicked_element = row_links.length ? row_links[0] : row_element;
      if (!key_event.repeat) clicked_element.click();
      return;
    }
    let next_element = null;
    switch (key_name) {
      case WIDGET_KEY_NAMES.down:
        next_element = walked_row_beside(row_element, row_selector, 1);
        break;
      case WIDGET_KEY_NAMES.first:
        next_element = walked_rows_in(table_body, row_selector)[0];
        break;
      case WIDGET_KEY_NAMES.last:
        next_element = walked_rows_in(table_body, row_selector).pop();
        break;
      case WIDGET_KEY_NAMES.left:
        next_element =
          link_index > 0 ? row_links[link_index - 1] : row_element;
        break;
      case WIDGET_KEY_NAMES.right:
        next_element = row_links[link_index + 1];
        break;
      case WIDGET_KEY_NAMES.up:
        next_element = walked_row_beside(row_element, row_selector, -1);
        break;
      default:
        return;
    }
    key_event.preventDefault();
    if (!next_element) return;
    if (next_element.matches("tr")) {
      table_row_tab_stop_set(next_element, true);
      return;
    }
    next_element.focus({ preventScroll: true });
    focus_reveal(next_element);
  }
  function table_rows_attach(table_element, row_selector) {
    if (table_element.is_row_walk_attached) return;
    table_element.is_row_walk_attached = true;
    const table_body = table_element.tBodies[0];
    const walked_rows = walked_rows_in(table_body, row_selector);
    if (!walked_rows.length) return;
    const row_walk = {
      focus_row: null,
      row_selector,
      tab_stop_row: walked_rows[0],
      table_body,
    };
    row_walks.set(table_element, row_walk);
    table_element.setAttribute("role", "treegrid");
    for (const walked_row of walked_rows) {
      walked_row.tabIndex = -1;
      for (const row_link of row_links_of(walked_row)) row_link.tabIndex = -1;
    }
    walked_rows[0].tabIndex = 0;
    table_element.addEventListener(
      "focusin",
      window.try_catch_handler_((focus_event) => {
        const row_element = walked_row_of(
          focus_event.target,
          table_body,
          row_selector,
        );
        row_walk.focus_row = row_element;
        if (row_element) table_row_tab_stop_set(row_element, false);
      }),
    );
    table_element.addEventListener(
      "focusout",
      window.try_catch_handler_((focus_event) => {
        const next_target = focus_event.relatedTarget;
        if (next_target && !table_element.contains(next_target))
          row_walk.focus_row = null;
      }),
    );
    table_element.addEventListener(
      "keydown",
      window.try_catch_handler_((key_event) =>
        table_row_key_take(key_event, table_body, row_selector),
      ),
    );
  }
  // Repairs the walk after rows leave or return, if the table has a walk.
  function table_rows_refresh(table_element) {
    const row_walk = row_walks.get(table_element);
    if (!row_walk) return;
    const { focus_row, row_selector, table_body, tab_stop_row } = row_walk;
    const walked_rows = walked_rows_in(table_body, row_selector);
    const is_focus_lost =
      focus_row !== null &&
      !walked_rows.includes(focus_row) &&
      [null, document.body].includes(document.activeElement);
    const stop_row = walked_rows.includes(tab_stop_row)
      ? tab_stop_row
      : walked_rows[0];
    for (const walked_row of walked_rows) {
      walked_row.tabIndex = walked_row === stop_row ? 0 : -1;
      for (const row_link of row_links_of(walked_row)) row_link.tabIndex = -1;
    }
    row_walk.tab_stop_row = stop_row;
    if (!walked_rows.includes(focus_row)) row_walk.focus_row = null;
    if (is_focus_lost && walked_rows.length)
      table_row_tab_stop_set(walked_rows[walked_rows.length - 1], true);
  }

  function row_count_checked(count_key, row_count) {
    if (!TABLE_ROW_COUNT_CHOICES.includes(row_count))
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    return row_count;
  }
  function row_count_stored(count_key, default_count) {
    const stored_count = view_storage.value_read(count_key);
    if (stored_count === null) return default_count;
    return row_count_checked(count_key, stored_count);
  }
  function row_count_entries_of() {
    return strip_choice_entries_of(
      TABLE_ROW_COUNT_CHOICES.map((row_count) => ({
        label: String(row_count),
        value: String(row_count),
      })),
    );
  }
  // Makes one pulldown entry element per choice of a label and a value.
  function strip_choice_entries_of(choices) {
    return choices.map((choice) =>
      window.shared_element_of_(
        window.shared_element_render_(
          "span",
          { "data-entry-value-": choice.value },
          window.shared_html_escape_(choice.label),
        ),
      ),
    );
  }
  // Fills every strip entry field the caller leaves out.
  function strip_entry_make(entry_name, kind_name, label, entry_fields) {
    return {
      name: entry_name,
      label,
      label_markup: null,
      kind: kind_name,
      is_numbered: false,
      is_available: true,
      is_widget: false,
      widget_text: "",
      href: "",
      opens_new_tab: false,
      on_activate: null,
      pulldown_options: null,
      ...entry_fields,
    };
  }
  // Shows a heading title as page emphasis, over a table as the strip's title.
  function page_heading_attach(heading_element, extra_entries) {
    const heading_text = heading_element.textContent;
    if (attached_headings.has(heading_element))
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    const title_markup = heading_element.innerHTML;
    const count_key = heading_element.getAttribute("data-row-count-key-");
    const count_span_of = () =>
      heading_element.querySelector(".page-heading-row-count-");
    const table_box = heading_element.nextElementSibling;
    const table_element =
      table_box && table_box.matches(".table-box-")
        ? table_box.querySelector(":scope > .table-columns- > table.columns-")
        : null;
    if (!table_element && (count_key !== null || extra_entries.length))
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    if (!table_element) {
      heading_element.innerHTML = window.shared_page_emphasis_render_(
        title_markup,
        { tag_name: "span" },
      );
      attached_headings.set(heading_element, { reset: () => {} });
      return;
    }
    if (count_key !== null && !count_span_of())
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    const default_count =
      count_key === null
        ? 0
        : row_count_checked(count_key, Number(count_span_of().textContent));
    const table_body = table_element.tBodies[0];
    const all_rows = [...table_body.rows];
    const copy_text = window.ui_strings_.text_of("str_table_heading_copy");
    const row_count_options = {
      box_width_chars: TABLE_HEADING_COUNT_BOX_WIDTH_CHARS,
      entries_of: row_count_entries_of,
      on_close: () => {},
      on_select: row_count_choose,
      reads_line_number: false,
    };
    let shown_count = default_count,
      strip_handle = null;

    function rows_show(row_count) {
      shown_count = row_count;
      count_span_of().textContent = String(row_count);
      all_rows.forEach((table_row, row_index) => {
        if (row_index >= row_count) table_row.remove();
        else if (table_row.parentElement !== table_body)
          table_body.append(table_row);
      });
      table_rows_refresh(table_element);
    }
    function row_count_show(row_count) {
      rows_show(row_count);
      strip_handle.pulldown_label_set("count", String(row_count));
    }
    // Stores the chosen count and shows it in every heading sharing its key.
    function row_count_choose(value_text) {
      const chosen_count = row_count_checked(count_key, Number(value_text));
      view_storage.value_write(count_key, chosen_count);
      for (const shared_heading of document.querySelectorAll(
        ".page-heading-[data-row-count-key-]",
      )) {
        if (shared_heading.getAttribute("data-row-count-key-") === count_key)
          attached_headings.get(shared_heading).row_count_show(chosen_count);
      }
    }
    function count_entry_of() {
      return strip_entry_make("count", "pulldown", String(shown_count), {
        pulldown_options: row_count_options,
      });
    }
    function table_copy() {
      return navigator.clipboard.writeText(table_markdown_of(table_element));
    }
    function heading_render() {
      const count_entries = count_key === null ? [] : [count_entry_of()];
      strip_handle = strip_render(
        heading_element,
        [
          strip_entry_make("title", "text", heading_text, {
            label_markup: title_markup,
          }),
          ...count_entries,
          ...extra_entries,
          strip_entry_make("copy", "action", copy_text, {
            on_activate: table_copy,
          }),
        ],
        [],
      );
      if (count_key !== null)
        count_span_of().textContent = String(shown_count);
    }
    // Shows the stored count, or the printed one, and renders the cells again.
    function heading_reset() {
      if (count_key !== null)
        rows_show(row_count_stored(count_key, default_count));
      heading_render();
    }

    attached_headings.set(heading_element, {
      reset: heading_reset,
      row_count_show,
    });
    heading_reset();
  }

  // Stores null in every owned key, each preference one the user never set.
  function storage_sweep() {
    for (const storage_key of STORAGE_OWNED_KEYS) {
      localStorage.setItem(storage_key, JSON.stringify(null));
    }
  }
  function storage_version_check() {
    if (storage_is_checked) return;
    storage_is_checked = true;
    try {
      if (localStorage.getItem(STORAGE_VERSION_KEY) === STORAGE_VERSION) {
        return;
      }
      storage_sweep();
      localStorage.setItem(STORAGE_VERSION_KEY, STORAGE_VERSION);
    } catch (storage_error) {}
  }
  const view_storage = {
    preferences_clear() {
      storage_version_check();
      try {
        storage_sweep();
      } catch (storage_error) {}
    },
    value_read(storage_key) {
      storage_version_check();
      try {
        return JSON.parse(localStorage.getItem(storage_key));
      } catch (storage_error) {
        return null;
      }
    },
    value_write(storage_key, stored_value) {
      storage_version_check();
      try {
        localStorage.setItem(storage_key, JSON.stringify(stored_value));
      } catch (storage_error) {}
    },
  };

  function pane_splitter_attach(
    handle_bar,
    pane_element,
    narrowest_chars,
    widest_chars,
  ) {
    let width_chars = null;
    const pane_width_of = (wanted_chars) =>
      Math.min(widest_chars, Math.max(narrowest_chars, wanted_chars));
    const pane_width_now = () =>
      width_chars === null
        ? pane_element.offsetWidth / STYLE_DESIGN_FONT_CHARACTER_WIDTH_PX
        : width_chars;
    function splitter_values_show() {
      handle_bar.setAttribute("aria-valuemin", String(narrowest_chars));
      handle_bar.setAttribute("aria-valuemax", String(widest_chars));
      handle_bar.setAttribute(
        "aria-valuenow",
        String(Math.round(pane_width_now())),
      );
    }
    function pane_width_set(wanted_chars) {
      width_chars = pane_width_of(wanted_chars);
      pane_element.style.width = width_chars + "ch";
    }
    function pane_width_forget() {
      width_chars = null;
      pane_element.style.width = "";
      splitter_values_show();
    }
    registered_panes.push({ pane_element, pane_width_forget });
    handle_bar.tabIndex = 0;
    handle_bar.setAttribute("role", "separator");
    handle_bar.setAttribute("aria-orientation", "vertical");
    handle_bar.setAttribute("aria-controls", pane_element.id);
    handle_bar.setAttribute("aria-labelledby", pane_element.id);
    splitter_values_show();
    const on_key_down = window.try_catch_handler_((key_event) => {
      let wanted_chars = 0;
      switch (widget_key_of(key_event)) {
        case WIDGET_KEY_NAMES.first:
          wanted_chars = narrowest_chars;
          break;
        case WIDGET_KEY_NAMES.last:
          wanted_chars = widest_chars;
          break;
        case WIDGET_KEY_NAMES.left:
          wanted_chars = pane_width_now() - STYLE_PANE_SPLITTER_KEY_STEP_CHARS;
          break;
        case WIDGET_KEY_NAMES.right:
          wanted_chars = pane_width_now() + STYLE_PANE_SPLITTER_KEY_STEP_CHARS;
          break;
        default:
          return;
      }
      key_event.preventDefault();
      pane_width_set(wanted_chars);
      layout_refresh();
      splitter_values_show();
    });
    handle_bar.addEventListener("keydown", on_key_down);
    handle_bar.addEventListener(
      "focus",
      window.try_catch_handler_(splitter_values_show),
    );
  }

  function text_scrollbar_axis_of(bar_element) {
    const axis_names = Object.keys(TEXT_SCROLLBAR_AXES).filter((axis_name) =>
      bar_element.classList.contains(axis_name + "-"),
    );
    if (axis_names.length !== 1)
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    return axis_names[0];
  }
  // Converts a wheel delta to characters, one pixel per delta unit.
  function wheel_chars_of(wheel_event, wheel_delta, page_size) {
    if (wheel_event.deltaMode === WheelEvent.DOM_DELTA_PIXEL)
      return (
        (wheel_delta * TEXT_SCROLLBAR_WHEEL_NOTCH_LINES) /
        TEXT_SCROLLBAR_WHEEL_DELTA_PER_NOTCH
      );
    if (wheel_event.deltaMode === WheelEvent.DOM_DELTA_LINE)
      return wheel_delta;
    if (wheel_event.deltaMode === WheelEvent.DOM_DELTA_PAGE)
      return wheel_delta * page_size;
    throw new Error(window.ui_strings_.text_of("str_error_internal"));
  }
  // Shows and drives the target's scroll offset on one axis in text cells.
  function text_scrollbar_attach(bar_element, target_element, axis_name) {
    if (!Object.hasOwn(TEXT_SCROLLBAR_AXES, axis_name))
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    if (attached_scrollbars.has(bar_element))
      throw new Error(window.ui_strings_.text_of("str_error_internal"));
    const scroll_axis = TEXT_SCROLLBAR_AXES[axis_name];
    const gutter_text = window.ui_strings_.text_of(
      "str_text_scrollbar_gutter",
    );
    const thumb_text = window.ui_strings_.text_of("str_text_scrollbar_thumb");
    const taken_wheel_events = wheel_taken_events[axis_name];
    let press_state = null;
    function cell_make() {
      return window.shared_element_of_(
        window.shared_element_render_(
          "span",
          {},
          window.shared_html_escape_(gutter_text),
        ),
      );
    }
    // Measures in characters, null when the bar is not laid out.
    function geometry_of() {
      const bar_rect = bar_element.getBoundingClientRect();
      const cell_rect = bar_element.firstElementChild.getBoundingClientRect();
      const target_rect = target_element.getBoundingClientRect();
      const cell_screen_px = cell_rect[scroll_axis.rect_size];
      const target_screen_px = target_rect[scroll_axis.rect_size];
      if (!cell_screen_px || !target_screen_px) return null;
      const units_per_char =
        (cell_screen_px * target_element[scroll_axis.layout_size]) /
        target_screen_px;
      const content_min = 0;
      const content_size =
        target_element[scroll_axis.scroll_size] / units_per_char;
      const content_max = content_min + content_size - 1;
      const page_size =
        target_element[scroll_axis.client_size] / units_per_char;
      const scroll_position =
        content_min +
        target_element[scroll_axis.scroll_offset] / units_per_char;
      const scroll_span = content_max - page_size + 1 - content_min;
      const track_length = Math.floor(
        bar_rect[scroll_axis.rect_size] / cell_screen_px,
      );
      const thumb_length = Math.min(
        track_length,
        Math.max(
          STYLE_TEXT_SCROLLBAR_THUMB_SHORTEST_CHARS,
          (track_length * page_size) / content_size,
        ),
      );
      const thumb_room = track_length - thumb_length;
      const is_scrolling = content_size > page_size;
      const unclamped_position = is_scrolling
        ? (thumb_room * (scroll_position - content_min)) / scroll_span
        : 0;
      return {
        bar_start: bar_rect[scroll_axis.rect_start],
        cell_screen_px,
        content_min,
        is_scrolling,
        page_size,
        scroll_span,
        thumb_length,
        thumb_position: Math.min(thumb_room, Math.max(0, unclamped_position)),
        thumb_room,
        track_length,
        units_per_char,
      };
    }
    function thumb_cells_of(bar_geometry) {
      return [
        Math.round(bar_geometry.thumb_position),
        Math.round(bar_geometry.thumb_position + bar_geometry.thumb_length),
      ];
    }
    function scrollbar_draw() {
      const bar_geometry = geometry_of();
      if (!bar_geometry) return;
      const cell_count = Math.max(bar_geometry.track_length, 1);
      while (bar_element.children.length < cell_count)
        bar_element.append(cell_make());
      while (bar_element.children.length > cell_count)
        bar_element.lastElementChild.remove();
      const [thumb_first, thumb_end] = thumb_cells_of(bar_geometry);
      [...bar_element.children].forEach((cell_element, cell_index) => {
        const is_thumb =
          bar_geometry.is_scrolling &&
          cell_index >= thumb_first &&
          cell_index < thumb_end;
        const cell_text = is_thumb ? thumb_text : gutter_text;
        if (cell_element.textContent !== cell_text)
          cell_element.textContent = cell_text;
      });
    }
    function thumb_place(bar_geometry, wanted_position) {
      const { content_min, scroll_span, thumb_room, units_per_char } =
        bar_geometry;
      const thumb_position = Math.min(
        thumb_room,
        Math.max(0, wanted_position),
      );
      if (thumb_room > 0) {
        const scroll_position =
          content_min + (thumb_position * scroll_span) / thumb_room;
        target_element[scroll_axis.scroll_offset] =
          (scroll_position - content_min) * units_per_char;
      }
      return thumb_position;
    }
    function pointer_cells_of(pointer_event, bar_geometry) {
      return (
        (pointer_event[scroll_axis.pointer_along] - bar_geometry.bar_start) /
        bar_geometry.cell_screen_px
      );
    }
    function scroll_can_move(step_direction) {
      const scroll_offset = target_element[scroll_axis.scroll_offset];
      const scroll_limit =
        target_element[scroll_axis.scroll_size] -
        target_element[scroll_axis.client_size];
      return step_direction < 0
        ? Math.floor(scroll_offset) > 0
        : Math.ceil(scroll_offset) < scroll_limit;
    }
    function scroll_step(step_chars, bar_geometry) {
      target_element[scroll_axis.scroll_offset] +=
        step_chars * bar_geometry.units_per_char;
    }
    const press_take = window.try_catch_handler_((press_event) => {
      if (press_event.button || press_state) return;
      const bar_geometry = geometry_of();
      if (!bar_geometry) return;
      press_event.preventDefault();
      bar_element.setPointerCapture(press_event.pointerId);
      bar_element.classList.add("drag-");
      let grab_offset = 0;
      if (bar_geometry.is_scrolling) {
        const pointer_cells = pointer_cells_of(press_event, bar_geometry);
        const [thumb_first, thumb_end] = thumb_cells_of(bar_geometry);
        const pressed_cell = Math.floor(pointer_cells);
        const is_thumb_press =
          pressed_cell >= thumb_first && pressed_cell < thumb_end;
        const centred_position = pointer_cells - bar_geometry.thumb_length / 2;
        const thumb_position = is_thumb_press
          ? bar_geometry.thumb_position
          : thumb_place(bar_geometry, centred_position);
        grab_offset = pointer_cells - thumb_position;
      }
      press_state = { grab_offset, press_event };
    });
    const move_take = window.try_catch_handler_((move_event) => {
      if (
        !press_state ||
        move_event.pointerId !== press_state.press_event.pointerId
      )
        return;
      const bar_geometry = geometry_of();
      if (!bar_geometry || !bar_geometry.is_scrolling) return;
      thumb_place(
        bar_geometry,
        pointer_cells_of(move_event, bar_geometry) - press_state.grab_offset,
      );
    });
    const press_finish = window.try_catch_handler_((end_event) => {
      if (
        !press_state ||
        end_event.pointerId !== press_state.press_event.pointerId
      )
        return;
      press_state = null;
      bar_element.classList.remove("drag-");
      click_swallow_next();
    });
    const wheel_take = window.try_catch_handler_((wheel_event) => {
      const wheel_delta = wheel_event[scroll_axis.wheel_delta];
      if (
        !wheel_delta ||
        wheel_event.ctrlKey ||
        taken_wheel_events.has(wheel_event)
      )
        return;
      const bar_geometry = geometry_of();
      if (
        !bar_geometry ||
        !bar_geometry.is_scrolling ||
        !scroll_can_move(Math.sign(wheel_delta))
      )
        return;
      taken_wheel_events.add(wheel_event);
      wheel_event.preventDefault();
      scroll_step(
        wheel_chars_of(wheel_event, wheel_delta, bar_geometry.page_size),
        bar_geometry,
      );
    });
    const key_take = window.try_catch_handler_((key_event) => {
      const key_name = widget_key_of(key_event);
      let step_direction = 0;
      if (key_name === scroll_axis.backward_key) step_direction = -1;
      else if (key_name === scroll_axis.forward_key) step_direction = 1;
      else return;
      const bar_geometry = geometry_of();
      if (
        !bar_geometry ||
        !bar_geometry.is_scrolling ||
        !scroll_can_move(step_direction)
      )
        return;
      key_event.preventDefault();
      scroll_step(step_direction, bar_geometry);
    });
    bar_element.replaceChildren(cell_make());
    const resize_observer = new ResizeObserver(
      window.try_catch_handler_(scrollbar_draw),
    );
    resize_observer.observe(bar_element);
    resize_observer.observe(target_element);
    for (const child_element of target_element.children)
      resize_observer.observe(child_element);
    const mutation_observer = new MutationObserver(
      window.try_catch_handler_((mutation_records) => {
        for (const mutation_record of mutation_records) {
          for (const removed_node of mutation_record.removedNodes)
            if (removed_node instanceof Element)
              resize_observer.unobserve(removed_node);
          for (const added_node of mutation_record.addedNodes)
            if (added_node instanceof Element)
              resize_observer.observe(added_node);
        }
        scrollbar_draw();
      }),
    );
    mutation_observer.observe(target_element, { childList: true });
    target_element.addEventListener(
      "scroll",
      window.try_catch_handler_(scrollbar_draw),
    );
    target_element.addEventListener("keydown", key_take);
    for (const wheel_surface of [bar_element, target_element])
      wheel_surface.addEventListener("wheel", wheel_take, { passive: false });
    bar_element.addEventListener("pointerdown", press_take);
    listeners_bind(bar_element, move_take, press_finish, true);
    const attached_scrollbar = { refresh: scrollbar_draw };
    attached_scrollbars.set(bar_element, attached_scrollbar);
    scrollbar_draw();
    return attached_scrollbar;
  }

  function drag_scroll_press(press_event, surface_element, target_element) {
    if (press_event.button || press_event.defaultPrevented) return;
    const slide_cell = slide_cell_of(press_event);
    const start_scroll_left = target_element.scrollLeft,
      start_scroll_top = target_element.scrollTop;
    let is_dragging = false,
      is_moving_target = false;
    const on_pointer_move = window.try_catch_handler_((move_event) => {
      if (move_event.pointerId !== press_event.pointerId) return;
      if (!is_dragging) {
        const drag_direction = drag_direction_of(press_event, move_event);
        const is_column_slide = !!slide_cell && drag_direction === "sideways";
        if (!move_event.buttons || is_column_slide) {
          press_end();
          return;
        }
        if (!drag_direction) return;
        is_dragging = true;
        // A drag along an axis the target cannot scroll moves nothing.
        is_moving_target =
          drag_direction === "sideways"
            ? target_element.scrollWidth > target_element.clientWidth
            : target_element.scrollHeight > target_element.clientHeight;
        selection_drop();
        document.addEventListener("selectionchange", selection_drop);
        surface_element.setPointerCapture(press_event.pointerId);
      }
      if (!is_moving_target) return;
      const target_rect = target_element.getBoundingClientRect();
      const sideways_travel =
        (target_element.offsetWidth / target_rect.width) *
        (move_event.clientX - press_event.clientX);
      const vertical_travel =
        (target_element.offsetHeight / target_rect.height) *
        (move_event.clientY - press_event.clientY);
      target_element.scrollLeft = start_scroll_left - sideways_travel;
      target_element.scrollTop = start_scroll_top - vertical_travel;
    });
    const on_pointer_release = window.try_catch_handler_((release_event) => {
      if (release_event.pointerId !== press_event.pointerId) return;
      press_end();
      if (!is_dragging) return;
      document.removeEventListener("selectionchange", selection_drop);
      click_swallow_next();
    });
    function press_end() {
      listeners_bind(window, on_pointer_move, on_pointer_release, false);
      window.removeEventListener("dragstart", default_prevent, true);
    }
    listeners_bind(window, on_pointer_move, on_pointer_release, true);
    window.addEventListener("dragstart", default_prevent, true);
  }
  // Drags the target's view by the surface, a moved press swallows its click.
  function drag_scroll_attach(surface_element, target_element) {
    surface_element.addEventListener(
      "pointerdown",
      window.try_catch_handler_((press_event) =>
        drag_scroll_press(press_event, surface_element, target_element),
      ),
    );
  }

  function design_scale_settle() {
    design_scale_apply();
    if (!settle_animation_frame)
      settle_animation_frame = requestAnimationFrame(
        window.try_catch_handler_(layout_settle),
      );
  }
  // Refreshes the layout next frame, then callbacks after a window resize.
  function layout_settle() {
    settle_animation_frame = 0;
    layout_refresh();
    if (!window_resize_is_pending) return;
    window_resize_is_pending = false;
    for (const settle_callback of resize_settle_callbacks) settle_callback();
  }
  function page_activate() {
    if (is_scaled)
      text_scrollbar_attach(page_scrollbar, page_scroll_box, "horizontal");
    layout_activate();
  }
  // Runs the callback after the layout refresh in each window resize frame.
  function resize_settle_register(settle_callback) {
    resize_settle_callbacks.push(settle_callback);
  }

  font_fit_apply();
  dark_mode_stored_apply_();
  if (is_scaled) design_scale_stop = design_scale_stored_stop();
  design_scale_apply();
  window.addEventListener(
    "resize",
    window.try_catch_handler_(() => {
      window_resize_is_pending = true;
      design_scale_settle();
    }),
  );
  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      window.try_catch_handler_(page_activate),
    );
  } else page_activate();
  return {
    address: {
      hash_of: address_hash_of,
      home_hash_of: address_home_hash_of,
      link_hash_of: address_link_hash_of,
      of_hash: address_of_hash,
      page_href_of: address_page_href_of,
      request: address_request_send,
      top_href_of: address_top_href_of,
    },
    dark_mode_enabled_now_,
    dark_mode_set_,
    dark_mode_show_: dark_mode_show,
    design_px,
    design_scale_last_stop: DESIGN_SCALE_LAST_STOP,
    design_scale_stop_now,
    design_scale_stop_set,
    diff_share_of,
    drag_scroll: { attach: drag_scroll_attach },
    home_panel,
    human_text,
    layout_activate,
    layout_refresh,
    layout_reset,
    listeners_bind,
    page_heading: { attach: page_heading_attach },
    pane_splitter: { attach: pane_splitter_attach },
    percent_text,
    ramp_channels_at,
    resize_settle_register,
    settings_apply_send,
    signed_human_text,
    signed_percent_text,
    strip: {
      choice_entries_of: strip_choice_entries_of,
      entry_make: strip_entry_make,
      render: strip_render,
    },
    tab_stop_move,
    table_markdown,
    table_render,
    table_rows: {
      attach: table_rows_attach,
      tab_stop_set: table_row_tab_stop_set,
    },
    template_fill,
    text_scrollbar: { attach: text_scrollbar_attach },
    view_activate,
    view_frame,
    view_key: {
      of: pulldown_key_of,
      opens_tests_pulldown: view_key_opens_tests_pulldown,
    },
    view_storage,
    widget_key: {
      activates: widget_key_activates,
      link_click_take: link_click_key_take,
      of: widget_key_of,
    },
    zero_percent_text,
  };
})();
