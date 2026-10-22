// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.report_ui_ = window.try_catch_handler_(function () {
  "use strict";

  const CALL_GRAPH_PAGE_DIR_NAME = settings_("CALL_GRAPH_PAGE_DIR_NAME");
  const CALL_GRAPH_VIEW_KEY = settings_("CALL_GRAPH_VIEW_KEY");
  const DARK_MODE_ENABLED_DEFAULT = settings_("DARK_MODE_ENABLED_DEFAULT");
  const DATABASE_PAGE_DIR_NAME = settings_("DATABASE_PAGE_DIR_NAME");
  const DATABASE_VIEW_KEY = settings_("DATABASE_VIEW_KEY");
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
  const MENU_PULLDOWN_SMALL_ENTRY_MAX_COUNT = settings_(
    "MENU_PULLDOWN_SMALL_ENTRY_MAX_COUNT",
  );
  const MENU_SCALE_KEY_STEPS = settings_("MENU_SCALE_KEY_STEPS");
  const NUMBER_FRACTION_DIGITS = settings_("NUMBER_FRACTION_DIGITS");
  const NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES = settings_(
    "NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES",
  );
  const OVERVIEW_PAGE_PATH = settings_("OVERVIEW_PAGE_PATH");
  const SETTINGS_DEBUG_HASH_KEY_NAME = settings_(
    "SETTINGS_DEBUG_HASH_KEY_NAME",
  );
  const SETTINGS_VIEW_ENTRY = settings_("SETTINGS_VIEW_ENTRY");
  const STORAGE_KEY_VIEW_DARK_MODE = settings_("STORAGE_KEY_VIEW_DARK_MODE");
  const STORAGE_KEY_VIEW_SCALE = settings_("STORAGE_KEY_VIEW_SCALE");
  const STYLE_DESIGN_COORDINATES_WIDTH_PX = settings_(
    "STYLE_DESIGN_COORDINATES_WIDTH_PX",
  );
  const STYLE_DESIGN_FONT_CHARACTER_WIDTH_SHARE = settings_(
    "STYLE_DESIGN_FONT_CHARACTER_WIDTH_SHARE",
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
  const STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE = settings_(
    "STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE",
  );
  const STYLE_HEAT_CELL_ON_BRIGHT_ROLE = settings_(
    "STYLE_HEAT_CELL_ON_BRIGHT_ROLE",
  );
  const STYLE_HEAT_CELL_ON_DARK_ROLE = settings_(
    "STYLE_HEAT_CELL_ON_DARK_ROLE",
  );
  const STYLE_HEAT_COLOR_FULL_SCALE_PERCENT = settings_(
    "STYLE_HEAT_COLOR_FULL_SCALE_PERCENT",
  );
  const STYLE_HEAT_COLOR_STOPS = settings_("STYLE_HEAT_COLOR_STOPS");
  const STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS = settings_(
    "STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS",
  );
  const STYLE_PAGE_FONT_FAMILY = settings_("STYLE_PAGE_FONT_FAMILY");
  const STYLE_TABLE_COLUMN_EDGE_GRAB_CHARS = settings_(
    "STYLE_TABLE_COLUMN_EDGE_GRAB_CHARS",
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
    [CALL_GRAPH_VIEW_KEY, []],
    [DATABASE_VIEW_KEY, []],
    [FLAME_GRAPH_VIEW_ENTRY[0], ["localProfilePath"]],
    [HEAT_MAP_VIEW_ENTRY[0], ["file", "line", "function"]],
    [SETTINGS_VIEW_ENTRY[0], ["setting"]],
  ]);
  // Tells per view whether an address of the view needs a test.
  const ADDRESS_VIEW_NEEDS_TEST = new Map([
    [CALL_GRAPH_VIEW_KEY, true],
    [DATABASE_VIEW_KEY, true],
    [FLAME_GRAPH_VIEW_ENTRY[0], true],
    [HEAT_MAP_VIEW_ENTRY[0], true],
    [SETTINGS_VIEW_ENTRY[0], false],
  ]);
  const CH_UNIT_GLYPH = "0";
  const CLIP_ELLIPSIS_TEXT = window.ui_strings_.text("str_clip_ellipsis");
  const DESIGN_CHARACTER_WIDTH_PX =
    STYLE_DESIGN_FONT_SIZE_PX * STYLE_DESIGN_FONT_CHARACTER_WIDTH_SHARE;
  const DESIGN_COLUMN_EDGE_GRAB_WIDTH_PX =
    STYLE_TABLE_COLUMN_EDGE_GRAB_CHARS * DESIGN_CHARACTER_WIDTH_PX;
  const DESIGN_SCALE_LAST_STOP = STYLE_DESIGN_SCALE_STOP_COUNT - 1;
  const DESIGN_SCALE_LOWER_TRAVEL_SHARE =
    STYLE_DESIGN_SCALE_DEFAULT_STOP / DESIGN_SCALE_LAST_STOP;
  const MENU_BUTTON_KIND_NAMES = ["action", "label", "link", "pulldown"];
  const PULLDOWN_COMMAND_KEY_NAMES = Object.values(MENU_PULLDOWN_KEY_NAMES);
  const PULLDOWN_HIGHLIGHTED_ENTRY_CLASS = "highlighted-entry-";
  const RAMP_CHANNEL_STOPS = STYLE_HEAT_COLOR_STOPS.map((hex) =>
    [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16)),
  );
  const REPORT_ROOT_HREF = new URL("..", document.currentScript.src).href;
  const REPORT_TOP_PAGE_HREF = new URL(OVERVIEW_PAGE_PATH, REPORT_ROOT_HREF)
    .href;
  const SIGNED_PERCENT_AMOUNT_CHARS = (
    fixed_text(-100, NUMBER_FRACTION_DIGITS) + "%"
  ).length;
  const SMALLEST_PRINTED_PERCENT = 1 / 10 ** NUMBER_FRACTION_DIGITS;
  const STRIP_ENTRY_KIND_NAMES = [
    "action",
    "label",
    "link",
    "pulldown",
    "text",
  ];
  const STRIP_GAP_TEXT = window.ui_strings_.text("str_strip_gap");
  const STRIP_STATUS_SEPARATOR_TEXT = window.ui_strings_.text(
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

  const is_framed = window.is_framed_;
  const home_panel = document.getElementById("overview-home-");
  const view_frame = document.getElementById("overview-view-frame-");
  const is_scaled = !is_framed && !!home_panel;
  const page_element = document.getElementById("overview-page-");
  const attached_headings = new WeakMap();
  const attached_scrollbars = new WeakMap();
  const drag_scroll_surfaces = new WeakSet();
  const wheel_taken_events = {
    horizontal: new WeakSet(),
    vertical: new WeakSet(),
  };
  const registered_panes = [];
  const rendered_strips = new WeakMap();
  const resize_settle_callbacks = [];
  const row_walks = new WeakMap();
  const table_column_move_callbacks = new Map();
  const table_sort_callbacks = new Map();
  const view_storage = window.report_view_storage_;
  let settle_animation_frame = 0;
  let window_resize_is_pending = false;
  let tests_pulldown_is_open = false;
  let dark_mode_is_enabled = null;
  let design_scale = 1;
  let design_scale_stop = null;
  let column_edge_hovered_element = null;
  let column_press_is_active = false;

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
  // Returns the heat of a share: clamped to full scale, divided, then curved.
  function heat_of_share(percent, curve_name, is_diff) {
    const magnitude = Math.min(
      Math.abs(percent),
      STYLE_HEAT_COLOR_FULL_SCALE_PERCENT,
    );
    if (magnitude <= 0) return 0;
    const fraction = magnitude / STYLE_HEAT_COLOR_FULL_SCALE_PERCENT;
    const curved =
      curve_name === "log" ? Math.log10(1 + 9 * fraction) : fraction;
    return is_diff && percent < 0 ? -curved : curved;
  }
  // Writes the heat colors of a cell by its share, the one heat color door.
  function heat_cell_style(percent, curve_name, is_diff) {
    const heat_value = heat_of_share(percent, curve_name, is_diff);
    if (Math.abs(heat_value) <= 0) return "";
    const mixed_channels = ramp_channels_at(
      is_diff ? (heat_value + 1) * 0.5 : heat_value,
    );
    const luminance =
      (0.2126 * mixed_channels[0] +
        0.7152 * mixed_channels[1] +
        0.0722 * mixed_channels[2]) /
      255;
    const foreground_role =
      luminance > STYLE_HEAT_CELL_ON_BRIGHT_ABOVE_LUMINANCE_SHARE
        ? STYLE_HEAT_CELL_ON_BRIGHT_ROLE
        : STYLE_HEAT_CELL_ON_DARK_ROLE;
    return (
      `background:rgb(${mixed_channels.join(",")});` +
      `color:var(--${foreground_role})`
    );
  }

  function design_scale_half(is_lower_half) {
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
  function design_scale_multiple(scale_stop) {
    const travel_fraction = scale_stop / DESIGN_SCALE_LAST_STOP;
    const half = design_scale_half(
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
      window.throw_exception_("str_error_internal");
    }
  }
  function design_scale_stop_nearest(wanted_multiple) {
    const distance = (scale_stop) =>
      Math.abs(design_scale_multiple(scale_stop) - wanted_multiple);
    let nearest_stop = 0;
    for (
      let scale_stop = 1;
      scale_stop <= DESIGN_SCALE_LAST_STOP;
      scale_stop++
    ) {
      if (distance(scale_stop) < distance(nearest_stop))
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
      window.throw_exception_("str_error_internal");
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
      scale_stop === null ? null : design_scale_multiple(scale_stop),
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
      window.throw_exception_("str_error_internal");
    }
    const measured_px = context.measureText(CH_UNIT_GLYPH).width;
    document.documentElement.style.setProperty(
      STYLE_DESIGN_FONT_FIT_PROPERTY,
      String(DESIGN_CHARACTER_WIDTH_PX / measured_px),
    );
  }
  function design_scale_root_zoom() {
    if (is_framed) return 1;
    const window_width_px = Math.max(
      document.documentElement.clientWidth,
      STYLE_DESIGN_MINIMUM_WINDOW_WIDTH_PX,
    );
    return window_width_px / STYLE_DESIGN_COORDINATES_WIDTH_PX;
  }
  function design_scale_apply() {
    const root_element = document.documentElement;
    const root_zoom = design_scale_root_zoom();
    const multiple = is_scaled ? design_scale_multiple(design_scale_stop) : 1;
    const wanted = root_zoom * multiple;
    if (!isFinite(wanted) || !(wanted > 0)) {
      window.throw_exception_("str_error_internal");
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
  // Shows a dark mode on the page, storing nothing.
  function dark_mode_show(is_enabled) {
    dark_mode_is_enabled = is_enabled;
    window.report_dark_mode_.root_show(is_enabled);
  }
  // Stores the dark mode the user chose, null the default, then shows it.
  function dark_mode_set_(is_enabled) {
    view_storage.value_write(
      STORAGE_KEY_VIEW_DARK_MODE,
      is_enabled === null
        ? null
        : window.report_dark_mode_.state_text(is_enabled),
    );
    dark_mode_show(
      is_enabled === null ? DARK_MODE_ENABLED_DEFAULT : is_enabled,
    );
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
  function diff_share(delta, baseline) {
    const baseline_count = baseline === null ? 0 : baseline;
    if (delta < -baseline_count) {
      window.throw_exception_("str_error_internal");
    }
    if (!delta) return 0;
    return baseline_count ? (100 * delta) / baseline_count : Infinity;
  }
  function signed_percent_text(percent, uses_whitespace = true) {
    if (!percent) return zero_percent_text();
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
    if (!uses_whitespace) return arrow + amount_text;
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

  function address_value_decode(part, encoded_value) {
    try {
      return decodeURIComponent(encoded_value);
    } catch (decode_error) {
      if (!(decode_error instanceof URIError)) throw decode_error;
      window.throw_exception_(
        "str_error_hash_part_unknown",
        part,
        decode_error,
      );
    }
  }
  function address_parts_check(parsed_address) {
    for (const key_name of ADDRESS_KEY_NAMES) {
      if (parsed_address[key_name] === "")
        window.throw_exception_("str_error_hash_value_empty", key_name);
    }
    const is_home = ADDRESS_KEY_NAMES.every(
      (key_name) =>
        parsed_address[key_name] === null ||
        key_name === SETTINGS_DEBUG_HASH_KEY_NAME,
    );
    if (is_home) return;
    if (parsed_address.view === null)
      window.throw_exception_(
        "str_error_hash_view_missing",
        parsed_address.test === null
          ? ADDRESS_KEY_NAMES.find(
              (key_name) => parsed_address[key_name] !== null,
            )
          : parsed_address.test,
      );
    if (!ADDRESS_VIEW_KEY_NAMES.has(parsed_address.view))
      window.throw_exception_(
        "str_error_hash_view_unknown",
        parsed_address.view,
      );
    for (const key_name of ADDRESS_KEY_NAMES.slice(2)) {
      if (
        parsed_address[key_name] !== null &&
        key_name !== SETTINGS_DEBUG_HASH_KEY_NAME &&
        !ADDRESS_VIEW_KEY_NAMES.get(parsed_address.view).includes(key_name)
      )
        window.throw_exception_(
          "str_error_hash_part_misplaced",
          key_name,
          parsed_address.view,
        );
    }
    if (parsed_address.line !== null && parsed_address.file === null)
      window.throw_exception_(
        "str_error_hash_file_missing",
        parsed_address.line,
      );
    if (
      parsed_address.function !== null &&
      (parsed_address.file !== null || parsed_address.line !== null)
    )
      window.throw_exception_(
        "str_error_hash_function_conflicting",
        parsed_address.function,
      );
    if (
      parsed_address.line !== null &&
      !/^[1-9][0-9]*$/.test(parsed_address.line)
    )
      window.throw_exception_(
        "str_error_hash_line_unusable",
        parsed_address.line,
      );
    if (
      parsed_address.view === HEAT_MAP_VIEW_ENTRY[0] &&
      (parsed_address.test === null ||
        (parsed_address.file === null && parsed_address.function === null))
    )
      window.throw_exception_("str_error_hash_heat_map_parts_missing");
    if (
      parsed_address.test === null &&
      ADDRESS_VIEW_NEEDS_TEST.get(parsed_address.view)
    )
      window.throw_exception_("str_error_hash_test_missing");
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
        window.throw_exception_("str_error_hash_part_unknown", part);
      if (parsed_address[key_name] !== null)
        window.throw_exception_("str_error_hash_part_repeated", key_name);
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
  function address_parts_hash(full_address) {
    const hash_parts = [];
    for (const key_name of ADDRESS_KEY_NAMES) {
      if (full_address[key_name] == null) continue;
      hash_parts.push(
        `${key_name}=${hash_value_encode(String(full_address[key_name]))}`,
      );
    }
    return "#" + hash_parts.join("&");
  }
  // Writes a hash, carrying the settings the page's own hash applies.
  function address_hash(partial_address) {
    return address_parts_hash({
      ...partial_address,
      [SETTINGS_DEBUG_HASH_KEY_NAME]:
        partial_address[SETTINGS_DEBUG_HASH_KEY_NAME] ??
        address_of_hash(location.hash)[SETTINGS_DEBUG_HASH_KEY_NAME],
    });
  }
  // Writes a hash of the address with no applied settings, carrying none.
  function address_settings_cleared_hash(partial_address) {
    return address_parts_hash({
      ...partial_address,
      [SETTINGS_DEBUG_HASH_KEY_NAME]: null,
    });
  }
  function address_home_hash(test_name, view_key) {
    return address_hash({
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
  // Returns the hash a plain press on a hash link or a link row asks for.
  function address_link_hash(click_event) {
    const link_element = click_event.target.closest("a[href]");
    const link_row = click_event.target.closest("tr.row-link-");
    const link_href = link_element
      ? !link_element.target && link_element.getAttribute("href")
      : link_row && link_row.getAttribute("data-href-");
    if (!link_href || !link_href.startsWith("#")) return "";
    return click_is_plain(click_event)
      ? address_hash(address_of_hash(link_href))
      : "";
  }
  // Returns the page of a test in a directory holding one page per test.
  function address_test_page_href(page_dir_name, test_name) {
    return page_dir_name + "/" + encodeURIComponent(test_name) + ".html";
  }
  function address_page_href(checked_address) {
    if (checked_address.view === CALL_GRAPH_VIEW_KEY)
      return address_test_page_href(
        CALL_GRAPH_PAGE_DIR_NAME,
        checked_address.test,
      );
    if (checked_address.view === DATABASE_VIEW_KEY)
      return address_test_page_href(
        DATABASE_PAGE_DIR_NAME,
        checked_address.test,
      );
    if (checked_address.view === HEAT_MAP_VIEW_ENTRY[0])
      return HEAT_MAP_VIEW_ENTRY[1];
    if (checked_address.view === FLAME_GRAPH_VIEW_ENTRY[0])
      return FLAME_GRAPH_VIEW_ENTRY[1];
    if (checked_address.view === SETTINGS_VIEW_ENTRY[0])
      return SETTINGS_VIEW_ENTRY[1];
    window.throw_exception_("str_error_internal");
  }
  // Returns the link to the top page at a hash, the address the menu shows.
  function address_top_href(hash) {
    return REPORT_TOP_PAGE_HREF + hash;
  }
  function address_request_send(hash) {
    const carried_hash = address_hash(address_of_hash(hash));
    if (is_framed)
      parent_post({ report_ui: "address_request", hash: carried_hash });
    else location.assign(address_top_href(carried_hash));
  }
  function settings_apply_send(setting_name, setting_value) {
    parent_post({ report_ui: "settings_apply", setting_name, setting_value });
  }
  // Asks the top page to load again with settings debugging switched over.
  function settings_debug_toggle_send() {
    parent_post({ report_ui: "settings_debug_toggle" });
  }
  // Asks the top page to keep this many history entries and relay them.
  function load_log_history_send(line_count) {
    parent_post({ report_ui: "load_log_history_set", line_count });
  }
  // Asks the top page to move a counters list line before or after another.
  function counter_line_move_send(
    list_key,
    line_name,
    anchor_name,
    lands_after,
  ) {
    parent_post({
      report_ui: "counter_line_move",
      list_key,
      line_name,
      anchor_name,
      lands_after,
    });
  }
  // Sends the call graph's focused path up, root first, for the status line.
  function focused_path_send(path_entries) {
    parent_post({ report_ui: "focused_path_set", path_entries });
  }
  // Returns the path of a report file from the report root, which a log names.
  function address_path(file_href) {
    const file_url = new URL(file_href);
    file_url.hash = "";
    file_url.search = "";
    if (!file_url.href.startsWith(REPORT_ROOT_HREF))
      window.throw_exception_("str_error_internal");
    return file_url.href.slice(REPORT_ROOT_HREF.length);
  }
  // Returns the href of a report file from its path from the report root.
  function address_file_href(report_path) {
    return new URL(report_path, REPORT_ROOT_HREF).href;
  }

  // Returns whether the key was typed in an editable field, which keeps it.
  function field_owns_key(key_event) {
    return (
      key_event.target.matches("input, textarea") ||
      key_event.target.isContentEditable
    );
  }
  function pulldown_key_is_command(key_name) {
    return PULLDOWN_COMMAND_KEY_NAMES.includes(key_name);
  }
  function pulldown_key(key_event) {
    const key_name = key_event.key;
    const is_plain =
      !key_event.defaultPrevented &&
      !key_event.isComposing &&
      !key_event.altKey &&
      !key_event.ctrlKey &&
      !key_event.metaKey &&
      !field_owns_key(key_event);
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
  function widget_key(key_event) {
    const is_plain =
      !key_event.defaultPrevented &&
      !key_event.isComposing &&
      !key_event.altKey &&
      !key_event.ctrlKey &&
      !key_event.metaKey &&
      !key_event.shiftKey &&
      !field_owns_key(key_event);
    return is_plain ? key_event.key : "";
  }
  function widget_key_activates(key_name) {
    return (
      key_name === WIDGET_KEY_NAMES.activate ||
      key_name === WIDGET_KEY_NAMES.click
    );
  }
  function link_click_key_handler(key_event) {
    if (
      widget_key(key_event) !== WIDGET_KEY_NAMES.click ||
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
          const link_hash = address_link_hash(click_event);
          if (!link_hash) return;
          click_event.preventDefault();
          address_request_send(link_hash);
        }),
      );
      document.addEventListener(
        "keydown",
        window.try_catch_handler_((key_event) => {
          link_click_key_handler(key_event);
          const key_name = pulldown_key(key_event);
          if (key_name && view_key_forward(key_name, key_event.repeat))
            key_event.preventDefault();
        }),
      );
    }
    parent_listen((message_data) => {
      const message_name = message_data.report_ui;
      if (message_name === "settings_relay") return;
      // The view takes what a message carries before the message acts.
      if (view_options.relay_handler) view_options.relay_handler(message_data);
      if (message_name === "layout_reset") {
        layout_reset();
        dark_mode_show(message_data.dark_mode_enabled);
        // A reset of the preferences changes the history count shown.
        if (view_options.load_log_show)
          parent_post({ report_ui: "load_log_request" });
      } else if (message_name === "dark_mode_show")
        dark_mode_show(message_data.dark_mode_enabled);
      else if (message_name === "load_log_relay")
        view_options.load_log_show(
          message_data.load_log_entries,
          message_data.load_log_line_count,
        );
      else if (message_name === "recenter") {
        if (view_options.recenter) view_options.recenter();
      } else if (message_name === "tests_pulldown_closed")
        view_key_tests_pulldown_closed();
      else if (
        message_name !== "preferences_apply" &&
        message_name !== "view_reset"
      )
        window.throw_exception_("str_error_internal");
    });
    parent_post({ report_ui: "dark_mode_request" });
    // Asks for the history at once, so its strip shows without a paint.
    if (view_options.load_log_show)
      parent_post({ report_ui: "load_log_request" });
    // The request follows the load render entry, so the history holds it.
    const load_render_log = () =>
      window.report_load_log_.page_render_log(() => {
        if (view_options.load_log_show)
          parent_post({ report_ui: "load_log_request" });
      });
    // A view drawing after its own loads logs its load render once drawn.
    if (view_options.load_render_defer)
      view_options.load_render_defer(load_render_log);
    else load_render_log();
  }

  // Escapes text for markup, the one escape the page scripts write through.
  function render_html_escape(text) {
    return String(text)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }
  // Writes one element, the one writer of a tag, a null inner a void tag.
  function render_element(tag_name, attributes, inner_markup) {
    const attribute_text = Object.entries(attributes)
      .map(([attribute_name, attribute_value]) => {
        if (!["number", "string"].includes(typeof attribute_value))
          window.throw_exception_("str_error_internal");
        return ` ${attribute_name}="${render_html_escape(attribute_value)}"`;
      })
      .join("");
    const start_tag = `<${tag_name}${attribute_text}>`;
    if (inner_markup === null) return start_tag;
    return `${start_tag}${inner_markup}</${tag_name}>`;
  }
  // Makes the one element a piece of markup holds.
  function render_element_of(markup) {
    const markup_template = document.createElement("template");
    markup_template.innerHTML = markup;
    const made_nodes = markup_template.content.childNodes;
    if (
      made_nodes.length !== 1 ||
      made_nodes[0].nodeType !== Node.ELEMENT_NODE
    )
      window.throw_exception_("str_error_internal");
    return made_nodes[0];
  }
  // Writes a menu button: menu colors, then a tab stop, link or role by kind.
  function render_menu_button(kind_name, label_markup, fields) {
    if (!MENU_BUTTON_KIND_NAMES.includes(kind_name))
      window.throw_exception_("str_error_internal");
    const own_attributes = {
      class: ["menu-button-", ...(fields.class_names || [])].join(" "),
    };
    let inner_markup = label_markup;
    if (kind_name === "link") {
      const link_attributes = { href: fields.href };
      if (fields.opens_new_tab) link_attributes.target = "_blank";
      if (fields.tag_name === "a")
        Object.assign(own_attributes, link_attributes);
      else {
        if (!fields.withholds_tab_stop) own_attributes.tabindex = 0;
        inner_markup = render_element(
          "a",
          { ...link_attributes, tabindex: -1 },
          label_markup,
        );
      }
    } else if (kind_name === "action") {
      own_attributes.role = "button";
      if (!fields.is_widget) own_attributes.tabindex = 0;
    }
    const extra_attributes = fields.attributes || {};
    for (const attribute_name of Object.keys(extra_attributes)) {
      if (Object.hasOwn(own_attributes, attribute_name))
        window.throw_exception_("str_error_internal");
    }
    return render_element(
      fields.tag_name,
      { ...own_attributes, ...extra_attributes },
      inner_markup,
    );
  }
  // Writes page emphasis: its colors and one space each side, in either mode.
  function render_page_emphasis(label_markup, fields) {
    return render_element(
      fields.tag_name,
      { class: "page-emphasis-", ...(fields.attributes || {}) },
      label_markup,
    );
  }

  function pulldown_pattern(search_text) {
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
    root_element.innerHTML =
      render_element("span", {}, "") +
      render_element(
        "span",
        {
          class: "menu-pulldown-search-box-",
          style: `width:${pulldown_options.box_width_chars}ch`,
        },
        "",
      ) +
      render_element(
        "span",
        { class: "menu-pulldown-entry-box-" },
        render_element(
          "span",
          { class: "menu-pulldown-entry-list-", role: "listbox" },
          "",
        ) +
          render_element(
            "span",
            { class: "text-scrollbar- vertical-", "aria-hidden": "true" },
            "",
          ),
      );
    const [label_box, search_box, entry_box] = root_element.children;
    const [entry_list, list_scrollbar] = entry_box.children;
    const no_match_note = render_element_of(
      render_element(
        "span",
        {},
        render_html_escape(window.ui_strings_.text("str_no_match")),
      ),
    );
    let entries = [],
      entries_line_number = 0,
      highlight_index = 0,
      is_open = false,
      is_small = false,
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
    function search_parts(typed_text) {
      const line_match =
        pulldown_options.reads_line_number &&
        new RegExp(MENU_PULLDOWN_LINE_NUMBER_PATTERN).exec(typed_text);
      return line_match ? [line_match[1], +line_match[2]] : [typed_text, 0];
    }
    function entries_offer(line_number) {
      entries_line_number = line_number;
      entries = pulldown_options.entries(line_number);
      is_small = entries.length <= MENU_PULLDOWN_SMALL_ENTRY_MAX_COUNT;
      for (const entry_element of entries) {
        entry_element.setAttribute("role", "option");
        entry_element.tabIndex = -1;
      }
    }
    function entries_filter() {
      const [filter_text, line_number] = search_parts(search_text);
      if (line_number !== entries_line_number) entries_offer(line_number);
      const search_pattern = pulldown_pattern(filter_text);
      matches = entries.filter(
        (entry_element) =>
          !!search_pattern && search_pattern.test(entry_element.textContent),
      );
      entry_list.replaceChildren(
        ...(matches.length ? matches : [no_match_note]),
      );
      search_box.textContent =
        search_text ||
        window.ui_strings_.text(
          pulldown_options.on_move
            ? "str_pulldown_drag_placeholder"
            : "str_pulldown_placeholder",
        );
      entry_list.scrollTop = 0;
      highlight_set(0);
      list_scrollbar_handle.refresh();
    }
    // Writes each offered entry's label again, the list kept as it stands.
    function entries_relabel() {
      const relabelled_entries = pulldown_options.entries(entries_line_number);
      if (relabelled_entries.length !== entries.length)
        window.throw_exception_("str_error_internal");
      entries.forEach((entry_element, entry_index) => {
        entry_element.textContent =
          relabelled_entries[entry_index].textContent;
      });
    }
    function root_focus() {
      root_element.focus({ preventScroll: true });
      if (document.activeElement !== root_element)
        window.throw_exception_("str_error_internal");
    }
    function pulldown_open(typed_text) {
      is_open = true;
      search_text = typed_text;
      root_element.classList.add("open-");
      root_element.setAttribute("aria-expanded", "true");
      entry_box.hidden = false;
      entries_offer(search_parts(search_text)[1]);
      // A small pulldown keeps its label, with no search box and no scrollbar.
      if (is_small) search_text = "";
      label_box.hidden = !is_small;
      search_box.hidden = is_small;
      list_scrollbar.hidden = is_small;
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
      // Every close leaves the cell unfocused, an Escape or a press away too.
      root_element.blur();
      pulldown_options.on_close();
    }
    function search_text_set(typed_text) {
      search_text = typed_text;
      entries_filter();
      root_focus();
    }
    function pulldown_key_handler(key_name) {
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
          if (!is_small)
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
      // A small pulldown takes a typed key and filters nothing.
      if (!is_small) search_text_set(search_text + key_name);
      return true;
    }
    function entry_value(entry_element) {
      return entry_element.getAttribute("data-entry-value-");
    }
    // Offers the entries again after a drop, the scroll kept, the line lit.
    function entries_reoffer(moved_value) {
      const kept_scroll_top = entry_list.scrollTop;
      entries_offer(entries_line_number);
      entries_filter();
      entry_list.scrollTop = kept_scroll_top;
      highlight_set(
        matches.findIndex(
          (entry_element) => entry_value(entry_element) === moved_value,
        ),
      );
    }
    // Moves a dragged line among the others, a drop moving it in the list.
    function entry_drag_press(press_event, dragged_entry) {
      const start_next_entry = dragged_entry.nextElementSibling;
      let has_left_box = false,
        is_dragging = false;
      const on_pointer_move = window.try_catch_handler_((move_event) => {
        if (move_event.pointerId !== press_event.pointerId || has_left_box)
          return;
        if (!is_dragging) {
          if (!drag_direction(press_event, move_event)) return;
          is_dragging = true;
          highlight_set(matches.indexOf(dragged_entry));
        }
        const box_rect = entry_box.getBoundingClientRect();
        if (
          move_event.clientX < box_rect.left ||
          move_event.clientX >= box_rect.right ||
          move_event.clientY < box_rect.top ||
          move_event.clientY >= box_rect.bottom
        ) {
          // A drag leaving the box closes the pulldown with no change.
          has_left_box = true;
          entry_list.insertBefore(dragged_entry, start_next_entry);
          pulldown_close();
          return;
        }
        const next_entry =
          [...entry_list.children].find((other_entry) => {
            if (other_entry === dragged_entry) return false;
            const entry_rect = other_entry.getBoundingClientRect();
            return move_event.clientY < entry_rect.top + entry_rect.height / 2;
          }) || null;
        if (dragged_entry.nextElementSibling !== next_entry)
          entry_list.insertBefore(dragged_entry, next_entry);
      });
      const on_pointer_release = window.try_catch_handler_((release_event) => {
        if (release_event.pointerId !== press_event.pointerId) return;
        listeners_bind(window, on_pointer_move, on_pointer_release, false);
        if (!is_dragging) return;
        if (release_event.type === "pointerup") click_swallow_next();
        if (has_left_box) return;
        const landed_next_entry = dragged_entry.nextElementSibling;
        if (
          release_event.type !== "pointerup" ||
          landed_next_entry === start_next_entry
        ) {
          entry_list.insertBefore(dragged_entry, start_next_entry);
          return;
        }
        const anchor_entry =
          landed_next_entry || dragged_entry.previousElementSibling;
        pulldown_options.on_move(
          entry_value(dragged_entry),
          entry_value(anchor_entry),
          !landed_next_entry,
        );
        entries_reoffer(entry_value(dragged_entry));
      });
      listeners_bind(window, on_pointer_move, on_pointer_release, true);
    }

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
        const key_name = widget_key(key_event) || pulldown_key(key_event);
        if (!is_open && widget_key_activates(key_name)) {
          key_event.preventDefault();
          if (!key_event.repeat) pulldown_open("");
        } else if (key_name && pulldown_key_handler(key_name))
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
      "pointerdown",
      window.try_catch_handler_((press_event) => {
        const entry_element = press_event.target.closest('[role="option"]');
        if (
          pulldown_options.on_move &&
          !press_event.button &&
          entry_element &&
          entry_element.parentElement === entry_list
        )
          entry_drag_press(press_event, entry_element);
      }),
    );
    entry_list.addEventListener(
      "click",
      window.try_catch_handler_((click_event) => {
        const entry_element = click_event.target.closest('[role="option"]');
        if (!entry_element || entry_element.parentElement !== entry_list)
          return;
        if (!pulldown_options.keeps_open) pulldown_close();
        if (!pulldown_options.on_select) return;
        click_event.preventDefault();
        pulldown_options.on_select(
          entry_element.getAttribute("data-entry-value-"),
        );
        if (pulldown_options.keeps_open) entries_relabel();
      }),
    );
    return {
      close: pulldown_close,
      is_open: () => is_open,
      key_handler: pulldown_key_handler,
      label_set: (label_text) => {
        label_box.textContent = label_text;
      },
      open: pulldown_open,
    };
  }

  function strip_entry(entries, entry_name) {
    const found_entry = entries.find(
      (candidate_entry) => candidate_entry.name === entry_name,
    );
    if (!found_entry) window.throw_exception_("str_error_internal");
    return found_entry;
  }
  function strip_number_text(numbered_index) {
    return String((numbered_index + 1) % MENU_DIGIT_KEY_COUNT);
  }
  // Returns the text label of an entry as the strip draws it, number included.
  function strip_label_text(entries, entry_name) {
    const entry = strip_entry(entries, entry_name);
    if (!entry.is_numbered) return entry.label;
    const numbered_entries = entries.filter(
      (other_entry) => other_entry.is_numbered,
    );
    return window.ui_strings_.text_fill("str_menu_button", {
      number: strip_number_text(numbered_entries.indexOf(entry)),
      label: entry.label,
    });
  }
  function strip_widget_cells_markup(widget_text) {
    return Array.from(widget_text, (widget_character) =>
      render_element("span", {}, render_html_escape(widget_character)),
    ).join("");
  }
  // Writes an entry cell, a title as page emphasis, else a menu button.
  function strip_cell_render(entry, label_markup) {
    if (!STRIP_ENTRY_KIND_NAMES.includes(entry.kind))
      window.throw_exception_("str_error_internal");
    const name_attributes = { "data-entry-name-": entry.name };
    if (entry.kind === "text")
      return render_page_emphasis(label_markup, {
        tag_name: "span",
        attributes: name_attributes,
      });
    const shown_markup = entry.kind === "pulldown" ? "" : label_markup;
    const widget_markup = entry.is_widget
      ? render_html_escape(STRIP_GAP_TEXT) +
        render_element(
          "span",
          { class: "menu-button-widget-" },
          strip_widget_cells_markup(entry.widget_text),
        )
      : "";
    return render_menu_button(entry.kind, shown_markup + widget_markup, {
      tag_name: "span",
      href: entry.href,
      opens_new_tab: entry.opens_new_tab,
      withholds_tab_stop: entry.withholds_tab_stop,
      is_widget: entry.is_widget,
      attributes: name_attributes,
    });
  }
  // Writes the status line as text, indented, each label separated.
  function strip_status_line_render(status_entries) {
    return render_element(
      "div",
      { class: "menu-status-bar-" },
      render_html_escape(
        STRIP_GAP_TEXT + status_entries.join(STRIP_STATUS_SEPARATOR_TEXT),
      ),
    );
  }
  // Renders a whole strip again from its entries, the one door for its cells.
  function strip_render(strip_element, entries, status_entries) {
    const numbered_entries = entries.filter((entry) => entry.is_numbered);
    if (numbered_entries.length > MENU_DIGIT_KEY_COUNT)
      window.throw_exception_("str_error_internal");
    const cells_by_name = new Map();
    const digit_entries = new Map();
    const entries_by_name = new Map();
    const previous_strip = rendered_strips.get(strip_element);
    const pulldowns_by_name = new Map();
    const cell_markups = [];
    let strip_line = null;

    function strip_cell_named(entry_name) {
      if (!cells_by_name.has(entry_name))
        window.throw_exception_("str_error_internal");
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
    function entry_click_handler(click_event) {
      const entry_cell = click_event.target.closest(".menu-button-");
      if (!entry_cell || entry_cell.parentElement !== strip_line) return;
      const entry = entries_by_name.get(
        entry_cell.getAttribute("data-entry-name-"),
      );
      if (entry.kind === "action") entry.on_activate(click_event);
      if (entry.kind !== "link" || !click_is_plain(click_event)) return;
      const entry_link = entry_cell.querySelector(":scope > a");
      if (!entry_link.contains(click_event.target)) entry_link.click();
      else if (entry.on_activate) entry.on_activate(click_event);
    }
    function entry_key_handler(key_event) {
      const entry_cell = key_event.target;
      if (
        entry_cell.parentElement !== strip_line ||
        !widget_key_activates(widget_key(key_event))
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
    function strip_key_handler(key_name, is_repeat) {
      for (const pulldown of pulldowns_by_name.values()) {
        if (pulldown.is_open()) return pulldown.key_handler(key_name);
      }
      if (!digit_entries.has(key_name)) return false;
      if (!is_repeat) entry_activate(digit_entries.get(key_name));
      return true;
    }
    // Focuses the entry a digit reaches, opening a pulldown as its key does.
    function strip_numbered_entry_focus(number_text) {
      if (!digit_entries.has(number_text))
        window.throw_exception_(
          "str_error_strip_number_unusable",
          number_text,
        );
      const entry = digit_entries.get(number_text);
      const entry_cell = cells_by_name.get(entry.name);
      if (entry.kind === "pulldown") entry_activate(entry);
      else entry_cell.focus({ focusVisible: true, preventScroll: true });
    }
    function strip_pulldown_open(entry_name, search_text) {
      strip_cell_named(entry_name);
      if (!pulldowns_by_name.has(entry_name))
        window.throw_exception_("str_error_internal");
      pulldowns_by_name.get(entry_name).open(search_text);
    }
    // Relabels a pulldown cell without a render, so focus stays where it is.
    function strip_pulldown_label_set(entry_name, label_text) {
      strip_cell_named(entry_name);
      if (!pulldowns_by_name.has(entry_name))
        window.throw_exception_("str_error_internal");
      const labelled_entries = entries.map((entry) =>
        entry.name === entry_name ? { ...entry, label: label_text } : entry,
      );
      pulldowns_by_name
        .get(entry_name)
        .label_set(strip_label_text(labelled_entries, entry_name));
    }
    function strip_widget_text_set(entry_name, widget_text) {
      const widget_box = strip_cell_named(entry_name).querySelector(
        ".menu-button-widget-",
      );
      if (!widget_box) window.throw_exception_("str_error_internal");
      widget_box.innerHTML = strip_widget_cells_markup(widget_text);
    }

    if (previous_strip) previous_strip.reset();
    for (const entry of entries) {
      if (entries_by_name.has(entry.name))
        window.throw_exception_("str_error_internal");
      entries_by_name.set(entry.name, entry);
      if (!entry.is_available) continue;
      const label_markup =
        entry.label_markup === null
          ? render_html_escape(strip_label_text(entries, entry.name))
          : entry.label_markup;
      if (cell_markups.length)
        cell_markups.push(render_html_escape(STRIP_GAP_TEXT));
      cell_markups.push(strip_cell_render(entry, label_markup));
    }
    numbered_entries.forEach((entry, numbered_index) => {
      if (entry.is_available && !entry.is_widget)
        digit_entries.set(strip_number_text(numbered_index), entry);
    });
    if (strip_element.contains(document.activeElement))
      document.activeElement.blur();
    strip_element.classList.add("strip-");
    strip_element.innerHTML =
      render_element("div", { class: "strip-line-" }, cell_markups.join("")) +
      (status_entries.length ? strip_status_line_render(status_entries) : "");
    strip_line = strip_element.firstElementChild;
    for (const entry_cell of strip_line.children) {
      if (entry_cell.hasAttribute("data-entry-name-"))
        cells_by_name.set(
          entry_cell.getAttribute("data-entry-name-"),
          entry_cell,
        );
    }
    strip_line.addEventListener(
      "click",
      window.try_catch_handler_(entry_click_handler),
    );
    strip_line.addEventListener(
      "keydown",
      window.try_catch_handler_(entry_key_handler),
    );
    for (const entry of entries) {
      if (entry.kind !== "pulldown" || !entry.is_available) continue;
      const pulldown = pulldown_attach(
        cells_by_name.get(entry.name),
        entry.pulldown_options,
      );
      pulldown.label_set(strip_label_text(entries, entry.name));
      pulldowns_by_name.set(entry.name, pulldown);
    }
    rendered_strips.set(strip_element, {
      reset: () => pulldowns_by_name.forEach((pulldown) => pulldown.close()),
    });
    return {
      flash: strip_flash,
      key_handler: strip_key_handler,
      numbered_entry_focus: strip_numbered_entry_focus,
      pulldown_label_set: strip_pulldown_label_set,
      pulldown_open: strip_pulldown_open,
      widget_text_set: strip_widget_text_set,
    };
  }

  function column_longest(cell_rows, column_index) {
    let longest = 0;
    for (const row of cell_rows) {
      longest = Math.max(longest, row[column_index].text.length);
    }
    return longest;
  }
  // Cuts text past a column's limit, the last character kept the ellipsis.
  function text_clip(text, clip_chars) {
    if (text.length <= clip_chars) return text;
    return text.slice(0, clip_chars - 1) + CLIP_ELLIPSIS_TEXT;
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
  function table_element_markdown(table_element) {
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
  // Writes a cell, its text clipped at the column's limit, a link plain.
  function table_cell_render(cell, column) {
    const cell_attributes = {};
    const class_names = [column.numeric ? "numeric-" : "", column.cls || ""]
      .filter(Boolean)
      .join(" ");
    if (class_names) cell_attributes.class = class_names;
    if (cell.style) cell_attributes.style = cell.style;
    const shown_text =
      column.clip != null ? text_clip(cell.text, column.clip) : cell.text;
    let inner_markup =
      cell.html != null ? cell.html : render_html_escape(shown_text);
    if (cell.href) {
      if (cell.html != null) window.throw_exception_("str_error_internal");
      inner_markup = render_element("a", { href: cell.href }, inner_markup);
    }
    return render_element("td", cell_attributes, inner_markup);
  }
  // Keeps the `on_sort` a click on a column title calls with its index.
  function table_sort_register(table_key, columns, table_options) {
    if (!table_options.on_sort) {
      table_sort_callbacks.delete(table_key);
      return -1;
    }
    const sorted_column_index = table_options.sorted_column_index;
    if (!columns[sorted_column_index])
      window.throw_exception_("str_error_internal");
    table_sort_callbacks.set(table_key, table_options.on_sort);
    return sorted_column_index;
  }
  // Keeps the `on_column_move` a column drop calls, needed by a moved column.
  function table_column_move_register(table_key, columns, table_options) {
    if (table_options.on_column_move) {
      table_column_move_callbacks.set(table_key, table_options.on_column_move);
      return;
    }
    if (columns.some((column) => column.move_name))
      window.throw_exception_("str_error_internal");
    table_column_move_callbacks.delete(table_key);
  }
  // Writes columns and rows as a table, the one table writer in JS.
  function render_table(table_key, columns, rows, table_options) {
    const cell_rows = rows.map((row) => row.map(cell_normalize));
    const sorted_column_index = table_sort_register(
      table_key,
      columns,
      table_options,
    );
    table_column_move_register(table_key, columns, table_options);
    const title_markup = render_element(
      "thead",
      {},
      render_element(
        "tr",
        {},
        columns
          .map((column, column_index) =>
            render_element(
              "th",
              {
                ...(column.numeric ? { class: "numeric-" } : {}),
                ...(column_index === sorted_column_index
                  ? {
                      "aria-sort": column.numeric ? "descending" : "ascending",
                    }
                  : {}),
                ...(column.move_name
                  ? { "data-column-move-name-": column.move_name }
                  : {}),
              },
              render_html_escape(column.label),
            ),
          )
          .join(""),
      ),
    );
    const body_markup = cell_rows
      .map((row, row_index) => {
        const row_href =
          table_options.row_href && table_options.row_href[row_index];
        const row_attributes = row_href
          ? { class: "row-link-", "data-href-": row_href }
          : table_options.row_attributes
            ? table_options.row_attributes[row_index]
            : {};
        return render_element(
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
    return render_element(
      "table",
      {
        class: ["table-", table_options.cls || ""].filter(Boolean).join(" "),
        "data-key-": table_key,
      },
      title_markup + render_element("tbody", {}, body_markup),
    );
  }
  // Pairs a table column with how its cells are written and its rows sorted.
  function table_sort_column(column, sort_name, sort_value, cell) {
    return { column, sort_name, sort_value, cell };
  }
  // Returns records ordered by a column, numbers largest first, text A to Z.
  function table_sort_records(records, sort_column) {
    const keyed_records = records.map((record) => [
      sort_column.sort_value(record),
      record,
    ]);
    keyed_records.sort(
      sort_column.column.numeric
        ? (keyed_record_a, keyed_record_b) =>
            keyed_record_b[0] - keyed_record_a[0]
        : (keyed_record_a, keyed_record_b) =>
            keyed_record_a[0].localeCompare(keyed_record_b[0]),
    );
    return keyed_records.map((keyed_record) => keyed_record[1]);
  }
  // Lists a sorted table's state: its rows, its sort direction, its measure.
  function table_sort_heading_labels(row_string_id, sort_column, is_diff) {
    const column_label =
      sort_column.column.measure ?? sort_column.column.label;
    const measure_text =
      is_diff && sort_column.column.numeric
        ? window.ui_strings_.text_fill("str_heading_measure_diff", {
            column: column_label,
          })
        : column_label;
    return [
      window.ui_strings_.text(row_string_id),
      window.ui_strings_.text(
        sort_column.column.numeric
          ? "str_heading_sort_descending"
          : "str_heading_sort_ascending",
      ),
      measure_text,
    ];
  }
  // Fills each marker with its markup, refusing a marker the template lacks.
  function template_fill(template_text, marker_values) {
    for (const marker of Object.keys(marker_values)) {
      if (!template_text.includes(marker))
        window.throw_exception_("str_error_template_marker_missing", marker);
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
  // Returns sideways or vertical once past the drag direction threshold.
  function drag_direction(press_event, move_event) {
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
  // Returns the title over the column holding an element of a table, or null.
  function column_title_of(target_element) {
    const table_cell = target_element.closest("td, th");
    if (!table_cell || table_cell.colSpan !== 1) return null;
    const table_element = table_cell.closest("table");
    if (!table_element.matches("table.table-")) return null;
    const title_row = table_element.tHead.rows[0];
    const cell_row = table_cell.parentElement;
    if (cell_row === title_row) return table_cell;
    // A row of another cell count, a detail row among them, has no columns.
    if (
      cell_row.parentElement !== table_element.tBodies[0] ||
      cell_row.cells.length !== title_row.cells.length
    )
      return null;
    return title_row.cells[table_cell.cellIndex];
  }
  // Returns the title of a moved column holding an element, or null.
  function column_moved_title(target_element) {
    const title_cell = column_title_of(target_element);
    return title_cell && title_cell.hasAttribute("data-column-move-name-")
      ? title_cell
      : null;
  }
  // Returns whether the pointer lies in the grab of an element's right edge.
  function edge_grab_holds(pointer_event, edge_element) {
    return (
      design_px(
        edge_element.getBoundingClientRect().right - pointer_event.clientX,
      ) <= DESIGN_COLUMN_EDGE_GRAB_WIDTH_PX
    );
  }
  // Returns the table's cell whose right edge grab holds the pointer, or null.
  function column_edge_cell(pointer_event, table_element) {
    if (pointer_event.target.closest(".text-scrollbar-")) return null;
    const table_cell = pointer_event.target.closest("td, th");
    if (
      !table_cell ||
      table_cell.closest("table") !== table_element ||
      !column_title_of(table_cell)
    )
      return null;
    return edge_grab_holds(pointer_event, table_cell) ? table_cell : null;
  }
  // Marks the cell or pane whose edge grab holds the pointer, unmarks others.
  function column_edge_hover_set(edge_element) {
    if (column_press_is_active || edge_element === column_edge_hovered_element)
      return;
    if (column_edge_hovered_element)
      column_edge_hovered_element.classList.remove("column-edge-grab-");
    column_edge_hovered_element = edge_element;
    if (edge_element) edge_element.classList.add("column-edge-grab-");
  }
  // Sizes a column title's min width or a pane's max width by its right edge.
  function column_edge_drag(
    press_event,
    grab_element,
    sized_element,
    size_property_name,
  ) {
    const start_width_px = design_px(
      sized_element.getBoundingClientRect().width,
    );
    let animation_frame = 0,
      has_travelled = false;
    const on_pointer_move = window.try_catch_handler_((move_event) => {
      if (move_event.pointerId !== press_event.pointerId) return;
      if (!has_travelled) {
        if (!drag_direction(press_event, move_event)) return;
        has_travelled = true;
        selection_drop();
        document.addEventListener("selectionchange", selection_drop);
      }
      const wanted_width_px =
        start_width_px + design_px(move_event.clientX - press_event.clientX);
      sized_element.style[size_property_name] =
        Math.max(0, wanted_width_px) + "px";
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
      // A capture another element loses ends nothing of this drag.
      if (
        release_event.type === "lostpointercapture" &&
        release_event.target !== grab_element
      )
        return;
      press_end();
      if (!has_travelled) return;
      document.removeEventListener("selectionchange", selection_drop);
      if (release_event.type === "pointerup") click_swallow_next();
    });
    function press_end() {
      column_press_is_active = false;
      listeners_bind(window, on_pointer_move, on_pointer_release, false);
      window.removeEventListener("dragstart", default_prevent, true);
    }
    column_press_is_active = true;
    grab_element.setPointerCapture(press_event.pointerId);
    listeners_bind(window, on_pointer_move, on_pointer_release, true);
    window.addEventListener("dragstart", default_prevent, true);
  }
  // Moves a column's cells in each row spanning the table to another index.
  function table_column_place(table_element, from_index, to_index) {
    if (from_index === to_index) return;
    const title_count = table_element.tHead.rows[0].cells.length;
    const before_index = to_index < from_index ? to_index : to_index + 1;
    for (const table_row of table_element.rows) {
      if (table_row.cells.length !== title_count) continue;
      table_row.insertBefore(
        table_row.cells[from_index],
        table_row.cells[before_index] || null,
      );
    }
  }
  // Returns the index a moved title lands at by the pointer's place.
  function column_landing_index(moved_title, pointer_x) {
    const moved_index = moved_title.cellIndex;
    const other_titles = [...moved_title.parentElement.cells].filter(
      (title_cell) =>
        title_cell !== moved_title &&
        title_cell.hasAttribute("data-column-move-name-"),
    );
    if (!other_titles.length) return moved_index;
    const next_title = other_titles.find((title_cell) => {
      const title_rect = title_cell.getBoundingClientRect();
      return pointer_x < title_rect.left + title_rect.width / 2;
    });
    if (next_title)
      return next_title.cellIndex < moved_index
        ? next_title.cellIndex
        : next_title.cellIndex - 1;
    const last_title = other_titles[other_titles.length - 1];
    return last_title.cellIndex < moved_index
      ? last_title.cellIndex + 1
      : last_title.cellIndex;
  }
  // Moves a column among the moved columns while a press in it drags sideways.
  function table_column_move_press(press_event, moved_title, on_column_move) {
    const table_element = moved_title.closest("table");
    const title_row = moved_title.parentElement;
    const start_index = moved_title.cellIndex;
    let is_moving = false;
    const on_pointer_move = window.try_catch_handler_((move_event) => {
      if (move_event.pointerId !== press_event.pointerId) return;
      if (!is_moving) {
        const move_direction = drag_direction(press_event, move_event);
        if (!move_direction) return;
        if (move_direction === "vertical") {
          press_end();
          return;
        }
        is_moving = true;
        column_edge_hover_set(null);
        column_press_is_active = true;
        selection_drop();
        document.addEventListener("selectionchange", selection_drop);
      }
      table_column_place(
        table_element,
        moved_title.cellIndex,
        column_landing_index(moved_title, move_event.clientX),
      );
    });
    const on_pointer_release = window.try_catch_handler_((release_event) => {
      if (release_event.pointerId !== press_event.pointerId) return;
      press_end();
      if (!is_moving) return;
      document.removeEventListener("selectionchange", selection_drop);
      if (release_event.type === "pointerup") click_swallow_next();
      // A release outside the window finds no element, so no title.
      const released_element = document.elementFromPoint(
        release_event.clientX,
        release_event.clientY,
      );
      const released_title =
        released_element && column_moved_title(released_element);
      if (
        release_event.type !== "pointerup" ||
        !released_title ||
        released_title.parentElement !== title_row ||
        moved_title.cellIndex === start_index
      ) {
        table_column_place(table_element, moved_title.cellIndex, start_index);
        return;
      }
      const next_title = moved_title.nextElementSibling;
      const lands_after =
        !next_title || !next_title.hasAttribute("data-column-move-name-");
      const anchor_title = lands_after
        ? moved_title.previousElementSibling
        : next_title;
      on_column_move(
        moved_title.getAttribute("data-column-move-name-"),
        anchor_title.getAttribute("data-column-move-name-"),
        lands_after,
      );
    });
    function press_end() {
      column_press_is_active = false;
      listeners_bind(window, on_pointer_move, on_pointer_release, false);
      window.removeEventListener("dragstart", default_prevent, true);
    }
    listeners_bind(window, on_pointer_move, on_pointer_release, true);
    window.addEventListener("dragstart", default_prevent, true);
  }
  // Hands a press in the table to an edge grab, else to its column's move.
  function table_column_press_attach(table_element) {
    if (table_element.is_column_press_attached) return;
    table_element.is_column_press_attached = true;
    // Taken while capturing, so an edge grab wins over a press inside a cell.
    table_element.addEventListener(
      "pointerdown",
      window.try_catch_handler_((press_event) => {
        if (
          press_event.button ||
          press_event.defaultPrevented ||
          press_event.target.closest(".text-scrollbar-")
        )
          return;
        const edge_cell = column_edge_cell(press_event, table_element);
        if (edge_cell) {
          press_event.preventDefault();
          column_edge_drag(
            press_event,
            edge_cell,
            column_title_of(edge_cell),
            "minWidth",
          );
          return;
        }
        const moved_title = column_moved_title(press_event.target);
        if (!moved_title || moved_title.closest("table") !== table_element)
          return;
        const on_column_move = table_column_move_callbacks.get(
          table_element.getAttribute("data-key-"),
        );
        if (!on_column_move) window.throw_exception_("str_error_internal");
        table_column_move_press(press_event, moved_title, on_column_move);
      }),
      true,
    );
    table_element.addEventListener(
      "pointermove",
      window.try_catch_handler_((move_event) => {
        const table_cell = move_event.target.closest("td, th");
        // A nested table marks its own cells.
        if (table_cell && table_cell.closest("table") !== table_element)
          return;
        column_edge_hover_set(column_edge_cell(move_event, table_element));
      }),
    );
    table_element.addEventListener(
      "pointerleave",
      window.try_catch_handler_(() => {
        if (table_element.contains(column_edge_hovered_element))
          column_edge_hover_set(null);
      }),
    );
  }
  // Hands a plain click on a column title to its table's sort callback.
  function table_sort_attach(table_element) {
    const on_sort = table_sort_callbacks.get(
      table_element.getAttribute("data-key-"),
    );
    if (!on_sort || table_element.is_sort_attached) return;
    table_element.is_sort_attached = true;
    table_element.tHead.addEventListener(
      "click",
      window.try_catch_handler_((click_event) => {
        const title_cell = click_event.target.closest("th");
        if (title_cell && click_is_plain(click_event))
          on_sort(title_cell.cellIndex);
      }),
    );
  }
  function layout_refresh(root_element) {
    root_element = root_element || document.body;
    for (const bar_element of root_element.querySelectorAll(
      ".text-scrollbar-",
    )) {
      const attached_scrollbar = attached_scrollbars.get(bar_element);
      if (attached_scrollbar) attached_scrollbar.refresh();
    }
  }
  // Attaches each table, heading and bar under the root, a bar by its name.
  function layout_activate(root_element) {
    root_element = root_element || document.body;
    for (const table_element of root_element.querySelectorAll(
      "table.table-",
    )) {
      table_column_press_attach(table_element);
      table_sort_attach(table_element);
      if (table_element.tBodies[0].querySelector("a[href]"))
        table_rows_attach(table_element, "tr");
    }
    for (const heading_element of root_element.querySelectorAll(
      ".page-heading-",
    )) {
      if (!attached_headings.has(heading_element))
        page_heading_attach(heading_element);
    }
    for (const bar_element of root_element.querySelectorAll(
      ".text-scrollbar-[data-scrolls-]",
    )) {
      if (attached_scrollbars.has(bar_element)) continue;
      const scrolled_element = document.getElementById(
        bar_element.getAttribute("data-scrolls-"),
      );
      if (!scrolled_element) window.throw_exception_("str_error_internal");
      text_scrollbar_attach(
        bar_element,
        scrolled_element,
        text_scrollbar_axis(bar_element),
      );
      if (bar_element.hasAttribute("data-sizes-"))
        pane_edge_attach(bar_sized_pane(bar_element));
    }
    layout_refresh(root_element);
    window.report_load_log_.event_render_log();
  }
  function layout_reset(root_element) {
    root_element = root_element || document.body;
    for (const title_cell of root_element.querySelectorAll(
      "table.table- > thead > tr > th",
    ))
      title_cell.style.minWidth = "";
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

  function scroller(focused_element) {
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
      scroller(focused_element).scrollTop -= design_px(hidden_px);
  }
  function tab_stop_move(previous_stop, next_stop, takes_focus) {
    if (previous_stop && previous_stop !== next_stop)
      previous_stop.tabIndex = -1;
    next_stop.tabIndex = 0;
    if (!takes_focus) return;
    next_stop.focus({ preventScroll: true });
    focus_reveal(next_stop);
  }
  function row_links(row_element) {
    return [...row_element.querySelectorAll("a[href]")].filter(
      (row_link) => row_link.closest("tr") === row_element,
    );
  }
  function walked_row(focused_element, table_body, row_selector) {
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
    if (!row_walk) window.throw_exception_("str_error_internal");
    tab_stop_move(
      row_element.parentElement.querySelector(':scope > tr[tabindex="0"]'),
      row_element,
      takes_focus,
    );
    row_walk.tab_stop_row = row_element;
  }
  function table_row_key_handler(key_event, table_body, row_selector) {
    const key_name = widget_key(key_event);
    const focused_element = key_event.target;
    const row_element = walked_row(focused_element, table_body, row_selector);
    if (!key_name || !row_element) return;
    const focused_row_links = row_links(row_element);
    const link_index = focused_row_links.indexOf(focused_element);
    if (link_index >= 0 && widget_key_activates(key_name)) {
      link_click_key_handler(key_event);
      return;
    }
    if (focused_element !== row_element && link_index < 0) return;
    if (widget_key_activates(key_name)) {
      key_event.preventDefault();
      const clicked_element = focused_row_links.length
        ? focused_row_links[0]
        : row_element;
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
          link_index > 0 ? focused_row_links[link_index - 1] : row_element;
        break;
      case WIDGET_KEY_NAMES.right:
        next_element = focused_row_links[link_index + 1];
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
      for (const row_link of row_links(walked_row)) row_link.tabIndex = -1;
    }
    walked_rows[0].tabIndex = 0;
    table_element.addEventListener(
      "focusin",
      window.try_catch_handler_((focus_event) => {
        const row_element = walked_row(
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
        table_row_key_handler(key_event, table_body, row_selector),
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
      for (const row_link of row_links(walked_row)) row_link.tabIndex = -1;
    }
    row_walk.tab_stop_row = stop_row;
    if (!walked_rows.includes(focus_row)) row_walk.focus_row = null;
    if (is_focus_lost && walked_rows.length)
      table_row_tab_stop_set(walked_rows[walked_rows.length - 1], true);
  }

  function row_count_checked(count_key, row_count) {
    if (!TABLE_ROW_COUNT_CHOICES.includes(row_count))
      window.throw_exception_("str_error_internal");
    return row_count;
  }
  function row_count_stored(count_key, default_count) {
    const stored_count = view_storage.value_read(count_key);
    if (stored_count === null) return default_count;
    return row_count_checked(count_key, stored_count);
  }
  function row_count_entries() {
    return strip_choice_entries(
      TABLE_ROW_COUNT_CHOICES.map((row_count) => ({
        label: String(row_count),
        value: String(row_count),
      })),
    );
  }
  // Makes one pulldown entry element per choice of a label and a value.
  function strip_choice_entries(choices) {
    return choices.map((choice) =>
      render_element_of(
        render_element(
          "span",
          { "data-entry-value-": choice.value },
          render_html_escape(choice.label),
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
      withholds_tab_stop: false,
      on_activate: null,
      pulldown_options: null,
      ...entry_fields,
    };
  }
  // Shows a heading as a strip, any title as page emphasis, state as labels.
  function page_heading_attach(heading_element) {
    const heading_text = heading_element.textContent;
    if (attached_headings.has(heading_element))
      window.throw_exception_("str_error_internal");
    const title_markup = heading_element.innerHTML;
    const count_key = heading_element.getAttribute("data-row-count-key-");
    const default_count_text = heading_element.getAttribute(
      "data-row-count-default-",
    );
    const state_labels = heading_element.hasAttribute("data-state-labels-")
      ? JSON.parse(heading_element.getAttribute("data-state-labels-"))
      : [];
    const shown_element = heading_element.nextElementSibling;
    if (!shown_element) window.throw_exception_("str_error_internal");
    const table_element = shown_element.matches("table.table-")
      ? shown_element
      : null;
    if ((count_key === null) !== (default_count_text === null))
      window.throw_exception_("str_error_internal");
    if (count_key !== null && !table_element)
      window.throw_exception_("str_error_internal");
    const default_count =
      count_key === null
        ? 0
        : row_count_checked(count_key, Number(default_count_text));
    const table_body = table_element ? table_element.tBodies[0] : null;
    const all_rows = table_body ? [...table_body.rows] : [];
    const copy_text = window.ui_strings_.text("str_table_heading_copy");
    const row_count_options = {
      box_width_chars: TABLE_HEADING_COUNT_BOX_WIDTH_CHARS,
      entries: row_count_entries,
      keeps_open: false,
      on_close: () => {},
      on_move: null,
      on_select: row_count_choose,
      reads_line_number: false,
    };
    let shown_count = default_count,
      strip_handle = null;

    function rows_show(row_count) {
      shown_count = row_count;
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
      for (const heading of document.querySelectorAll(
        ".page-heading-[data-row-count-key-]",
      )) {
        if (heading.getAttribute("data-row-count-key-") === count_key)
          attached_headings.get(heading).row_count_show(chosen_count);
      }
    }
    function count_entry() {
      return strip_entry_make("count", "pulldown", String(shown_count), {
        pulldown_options: row_count_options,
      });
    }
    // Writes a layout table a line per row, each cell padded to its column.
    function layout_table_text(layout_table) {
      const table_rows = [...layout_table.rows];
      const column_widths = new Array(
        Math.max(...table_rows.map((table_row) => table_row.cells.length)),
      ).fill(0);
      for (const table_row of table_rows)
        [...table_row.cells].forEach((table_cell, cell_index) => {
          column_widths[cell_index] = Math.max(
            column_widths[cell_index],
            table_cell.textContent.length,
          );
        });
      return table_rows
        .map((table_row) =>
          [...table_row.cells]
            .map((table_cell, cell_index) =>
              getComputedStyle(table_cell).textAlign === "right"
                ? table_cell.textContent.padStart(column_widths[cell_index])
                : table_cell.textContent.padEnd(column_widths[cell_index]),
            )
            .join("")
            .trimEnd(),
        )
        .join("\n");
    }
    // Copies tables as markdown or lines, a lone link its address, else text.
    function table_copy() {
      const lone_link = shown_element.querySelector(":scope > a:only-child");
      const is_link_line =
        lone_link !== null &&
        lone_link.textContent === shown_element.textContent;
      return navigator.clipboard.writeText(
        table_element
          ? table_element_markdown(table_element)
          : shown_element.matches("table")
            ? layout_table_text(shown_element)
            : is_link_line
              ? lone_link.href
              : shown_element.textContent,
      );
    }
    function heading_render() {
      const title_entries = heading_text
        ? [
            strip_entry_make("title", "text", heading_text, {
              label_markup: title_markup,
            }),
          ]
        : [];
      const count_entries = count_key === null ? [] : [count_entry()];
      const state_entries = state_labels.map((state_label, label_index) =>
        strip_entry_make(`state_${label_index}`, "label", state_label, {}),
      );
      strip_handle = strip_render(
        heading_element,
        [
          ...title_entries,
          ...count_entries,
          ...state_entries,
          strip_entry_make("copy", "action", copy_text, {
            on_activate: table_copy,
          }),
        ],
        [],
      );
    }
    // Shows the stored count, or the default one, and renders the cells again.
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

  // Narrows a pane that fills its room by its right edge, until a reset.
  function pane_edge_attach(pane_element) {
    if (pane_element.is_pane_edge_attached) return;
    pane_element.is_pane_edge_attached = true;
    registered_panes.push({
      pane_element,
      pane_width_forget: () => {
        pane_element.style.maxWidth = "";
      },
    });
    const holds_edge_grab = (pointer_event) =>
      !pointer_event.target.closest(".text-scrollbar-") &&
      edge_grab_holds(pointer_event, pane_element);
    // Taken while capturing, so the pane's edge wins over what lies under it.
    pane_element.addEventListener(
      "pointerdown",
      window.try_catch_handler_((press_event) => {
        if (
          press_event.button ||
          press_event.defaultPrevented ||
          !holds_edge_grab(press_event)
        )
          return;
        press_event.preventDefault();
        column_edge_drag(press_event, pane_element, pane_element, "maxWidth");
      }),
      true,
    );
    // Runs after a table inside marks its own cells, then marks the pane.
    pane_element.addEventListener(
      "pointermove",
      window.try_catch_handler_((move_event) => {
        if (holds_edge_grab(move_event)) column_edge_hover_set(pane_element);
        else if (column_edge_hovered_element === pane_element)
          column_edge_hover_set(null);
      }),
    );
    pane_element.addEventListener(
      "pointerleave",
      window.try_catch_handler_(() => {
        if (column_edge_hovered_element === pane_element)
          column_edge_hover_set(null);
      }),
    );
  }

  // Returns the pane a bar's `data-sizes-` names, refusing a missing one.
  function bar_sized_pane(bar_element) {
    const pane_element = document.getElementById(
      bar_element.getAttribute("data-sizes-"),
    );
    if (!pane_element) window.throw_exception_("str_error_internal");
    return pane_element;
  }
  function text_scrollbar_axis(bar_element) {
    const axis_names = Object.keys(TEXT_SCROLLBAR_AXES).filter((axis_name) =>
      bar_element.classList.contains(axis_name + "-"),
    );
    if (axis_names.length !== 1) window.throw_exception_("str_error_internal");
    return axis_names[0];
  }
  // Converts a wheel delta to characters, one pixel per delta unit.
  function wheel_chars(wheel_event, wheel_delta, page_size) {
    if (wheel_event.deltaMode === WheelEvent.DOM_DELTA_PIXEL)
      return (
        (wheel_delta * TEXT_SCROLLBAR_WHEEL_NOTCH_LINES) /
        TEXT_SCROLLBAR_WHEEL_DELTA_PER_NOTCH
      );
    if (wheel_event.deltaMode === WheelEvent.DOM_DELTA_LINE)
      return wheel_delta;
    if (wheel_event.deltaMode === WheelEvent.DOM_DELTA_PAGE)
      return wheel_delta * page_size;
    window.throw_exception_("str_error_internal");
  }
  // Shows and drives the target's scroll offset on one axis in text cells.
  function text_scrollbar_attach(bar_element, target_element, axis_name) {
    if (!Object.hasOwn(TEXT_SCROLLBAR_AXES, axis_name))
      window.throw_exception_("str_error_internal");
    if (attached_scrollbars.has(bar_element))
      window.throw_exception_("str_error_internal");
    const scroll_axis = TEXT_SCROLLBAR_AXES[axis_name];
    const gutter_text = window.ui_strings_.text("str_text_scrollbar_gutter");
    const thumb_text = window.ui_strings_.text("str_text_scrollbar_thumb");
    const taken_wheel_events = wheel_taken_events[axis_name];
    let draw_frame = 0,
      press_state = null;
    function cell_make() {
      return render_element_of(
        render_element("span", {}, render_html_escape(gutter_text)),
      );
    }
    // Returns whether the target holds more than it shows on the axis.
    function target_scrolls() {
      return (
        target_element[scroll_axis.scroll_size] >
        target_element[scroll_axis.client_size]
      );
    }
    // Measures in characters, null when the bar is not laid out.
    function geometry() {
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
      const is_scrolling = target_scrolls();
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
    function thumb_cells(bar_geometry) {
      return [
        Math.round(bar_geometry.thumb_position),
        Math.round(bar_geometry.thumb_position + bar_geometry.thumb_length),
      ];
    }
    // Hides the bar while its target fits, else draws its track and thumb.
    function scrollbar_draw() {
      bar_element.classList.toggle("target-fits-", !target_scrolls());
      const bar_geometry = geometry();
      if (!bar_geometry) return;
      const cell_count = Math.max(bar_geometry.track_length, 1);
      while (bar_element.children.length < cell_count)
        bar_element.append(cell_make());
      while (bar_element.children.length > cell_count)
        bar_element.lastElementChild.remove();
      const [thumb_first, thumb_end] = thumb_cells(bar_geometry);
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
    function pointer_cells(pointer_event, bar_geometry) {
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
    // Returns the column title or pane a sideways drag sizes, or null.
    function bar_sized_target() {
      const sized_title = column_title_of(bar_element);
      if (sized_title)
        return { element: sized_title, size_property_name: "minWidth" };
      if (!bar_element.hasAttribute("data-sizes-")) return null;
      return {
        element: bar_sized_pane(bar_element),
        size_property_name: "maxWidth",
      };
    }
    // Moves the thumb to a track press, then returns the grab in the thumb.
    function thumb_press_offset(press_event, bar_geometry) {
      if (!bar_geometry.is_scrolling) return 0;
      const pointer_position = pointer_cells(press_event, bar_geometry);
      const [thumb_first, thumb_end] = thumb_cells(bar_geometry);
      const pressed_cell = Math.floor(pointer_position);
      const is_thumb_press =
        pressed_cell >= thumb_first && pressed_cell < thumb_end;
      const centred_position =
        pointer_position - bar_geometry.thumb_length / 2;
      const thumb_position = is_thumb_press
        ? bar_geometry.thumb_position
        : thumb_place(bar_geometry, centred_position);
      return pointer_position - thumb_position;
    }
    const press_handler = window.try_catch_handler_((press_event) => {
      if (press_event.button || press_state) return;
      const bar_geometry = geometry();
      if (!bar_geometry) return;
      press_event.preventDefault();
      bar_element.setPointerCapture(press_event.pointerId);
      bar_element.classList.add("drag-");
      // A bar that sizes waits for the axis its drag travels further along.
      const sized_target = bar_sized_target();
      press_state = {
        grab_offset: sized_target
          ? 0
          : thumb_press_offset(press_event, bar_geometry),
        is_sizing: false,
        press_event,
        sized_target,
      };
    });
    const move_handler = window.try_catch_handler_((move_event) => {
      if (
        !press_state ||
        press_state.is_sizing ||
        move_event.pointerId !== press_state.press_event.pointerId
      )
        return;
      const bar_geometry = geometry();
      if (!bar_geometry) return;
      if (press_state.sized_target) {
        const move_direction = drag_direction(
          press_state.press_event,
          move_event,
        );
        if (!move_direction) return;
        if (move_direction === "sideways") {
          press_state.is_sizing = true;
          column_edge_drag(
            press_state.press_event,
            bar_element,
            press_state.sized_target.element,
            press_state.sized_target.size_property_name,
          );
          return;
        }
        press_state.grab_offset = thumb_press_offset(
          press_state.press_event,
          bar_geometry,
        );
        press_state.sized_target = null;
      }
      if (!bar_geometry.is_scrolling) return;
      thumb_place(
        bar_geometry,
        pointer_cells(move_event, bar_geometry) - press_state.grab_offset,
      );
    });
    const press_finish = window.try_catch_handler_((end_event) => {
      if (
        !press_state ||
        end_event.pointerId !== press_state.press_event.pointerId
      )
        return;
      // A press that waited and never travelled acts as a track press.
      if (
        press_state.sized_target &&
        !press_state.is_sizing &&
        end_event.type === "pointerup"
      ) {
        const bar_geometry = geometry();
        if (bar_geometry)
          thumb_press_offset(press_state.press_event, bar_geometry);
      }
      press_state = null;
      bar_element.classList.remove("drag-");
      click_swallow_next();
    });
    const wheel_handler = window.try_catch_handler_((wheel_event) => {
      const wheel_delta = wheel_event[scroll_axis.wheel_delta];
      if (
        !wheel_delta ||
        wheel_event.ctrlKey ||
        taken_wheel_events.has(wheel_event)
      )
        return;
      const bar_geometry = geometry();
      if (
        !bar_geometry ||
        !bar_geometry.is_scrolling ||
        !scroll_can_move(Math.sign(wheel_delta))
      )
        return;
      taken_wheel_events.add(wheel_event);
      wheel_event.preventDefault();
      scroll_step(
        wheel_chars(wheel_event, wheel_delta, bar_geometry.page_size),
        bar_geometry,
      );
    });
    const key_handler = window.try_catch_handler_((key_event) => {
      const key_name = widget_key(key_event);
      let step_direction = 0;
      if (key_name === scroll_axis.backward_key) step_direction = -1;
      else if (key_name === scroll_axis.forward_key) step_direction = 1;
      else return;
      const bar_geometry = geometry();
      if (
        !bar_geometry ||
        !bar_geometry.is_scrolling ||
        !scroll_can_move(step_direction)
      )
        return;
      key_event.preventDefault();
      scroll_step(step_direction, bar_geometry);
    });
    function frame_draw() {
      draw_frame = 0;
      scrollbar_draw();
    }
    // Draws a bar that shows or hides next frame, so no observed size changes.
    function resize_draw() {
      const is_shown = !bar_element.classList.contains("target-fits-");
      if (is_shown === target_scrolls()) scrollbar_draw();
      else if (!draw_frame)
        draw_frame = requestAnimationFrame(
          window.try_catch_handler_(frame_draw),
        );
    }
    bar_element.replaceChildren(cell_make());
    const resize_observer = new ResizeObserver(
      window.try_catch_handler_(resize_draw),
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
    target_element.addEventListener("keydown", key_handler);
    for (const wheel_surface of [bar_element, target_element])
      wheel_surface.addEventListener("wheel", wheel_handler, {
        passive: false,
      });
    bar_element.addEventListener("pointerdown", press_handler);
    listeners_bind(bar_element, move_handler, press_finish, true);
    const attached_scrollbar = { refresh: scrollbar_draw };
    attached_scrollbars.set(bar_element, attached_scrollbar);
    scrollbar_draw();
    return attached_scrollbar;
  }

  function drag_scroll_press(press_event, surface_element, target_element) {
    if (press_event.button || press_event.defaultPrevented) return;
    // A press in a surface nested in this one drags that surface alone.
    for (
      let pressed_element = press_event.target;
      pressed_element !== surface_element;
      pressed_element = pressed_element.parentElement
    )
      if (drag_scroll_surfaces.has(pressed_element)) return;
    // Yields a sideways drag to a column move, an edge grab already taken.
    const takes_column_drag = !!column_moved_title(press_event.target);
    const start_scroll_left = target_element.scrollLeft,
      start_scroll_top = target_element.scrollTop;
    let is_dragging = false,
      is_moving_target = false;
    const on_pointer_move = window.try_catch_handler_((move_event) => {
      if (move_event.pointerId !== press_event.pointerId) return;
      if (!is_dragging) {
        const move_direction = drag_direction(press_event, move_event);
        const is_column_drag =
          takes_column_drag && move_direction === "sideways";
        if (!move_event.buttons || is_column_drag) {
          press_end();
          return;
        }
        if (!move_direction) return;
        is_dragging = true;
        // A drag along an axis the target cannot scroll moves nothing.
        is_moving_target =
          move_direction === "sideways"
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
    drag_scroll_surfaces.add(surface_element);
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
    layout_activate();
  }
  // Runs the callback after the layout refresh in each window resize frame.
  function resize_settle_register(settle_callback) {
    resize_settle_callbacks.push(settle_callback);
  }

  window.render_element_ = render_element;
  window.render_element_of_ = render_element_of;
  window.render_html_escape_ = render_html_escape;
  window.render_menu_button_ = render_menu_button;
  window.render_page_emphasis_ = render_page_emphasis;
  font_fit_apply();
  dark_mode_show(window.report_dark_mode_.opening_enabled());
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
      file_href: address_file_href,
      hash: address_hash,
      home_hash: address_home_hash,
      link_hash: address_link_hash,
      of_hash: address_of_hash,
      page_href: address_page_href,
      path: address_path,
      request: address_request_send,
      settings_cleared_hash: address_settings_cleared_hash,
      top_href: address_top_href,
    },
    counter_line_move_send,
    dark_mode_enabled_now_,
    dark_mode_set_,
    design_character_width_px: DESIGN_CHARACTER_WIDTH_PX,
    design_px,
    design_scale_last_stop: DESIGN_SCALE_LAST_STOP,
    design_scale_stop_now,
    design_scale_stop_set,
    diff_share,
    drag_scroll: { attach: drag_scroll_attach },
    fixed_text,
    focused_path_send,
    heat_cell_style,
    home_panel,
    human_text,
    layout_activate,
    layout_refresh,
    layout_reset,
    listeners_bind,
    load_log_history_send,
    percent_text,
    ramp_channels_at,
    render_table,
    resize_settle_register,
    settings_apply_send,
    settings_debug_toggle_send,
    signed_human_text,
    signed_percent_text,
    strip: {
      choice_entries: strip_choice_entries,
      entry_make: strip_entry_make,
      render: strip_render,
    },
    tab_stop_move,
    table_markdown,
    table_rows: {
      attach: table_rows_attach,
      tab_stop_set: table_row_tab_stop_set,
    },
    table_sort: {
      column: table_sort_column,
      heading_labels: table_sort_heading_labels,
      records: table_sort_records,
    },
    template_fill,
    text_scrollbar: { attach: text_scrollbar_attach },
    view_activate,
    view_frame,
    view_key: {
      of: pulldown_key,
      opens_tests_pulldown: view_key_opens_tests_pulldown,
    },
    view_storage,
    widget_key: {
      activates: widget_key_activates,
      link_click_handler: link_click_key_handler,
      of: widget_key,
    },
    zero_percent_text,
  };
})();
