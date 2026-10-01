window.report_ui = window.catch_show_throw(function () {
  "use strict";

  const CALLERS_VIEW_KEY = settings("CALLERS_VIEW_KEY");
  const FLAME_GRAPH_LOCAL_PROFILE_PATH = settings(
    "FLAME_GRAPH_LOCAL_PROFILE_PATH",
  );
  const FLAME_GRAPH_VIEW_ENTRY = settings("FLAME_GRAPH_VIEW_ENTRY");
  const HEAT_MAP_VIEW_ENTRY = settings("HEAT_MAP_VIEW_ENTRY");
  const LAYOUT_RESIZE_SETTLE_DELAY_MS = settings(
    "LAYOUT_RESIZE_SETTLE_DELAY_MS",
  );
  const MENU_PULLDOWN_KEY_NAMES = settings("MENU_PULLDOWN_KEY_NAMES");
  const MENU_PULLDOWN_OPENING_KEY_PATTERN = settings(
    "MENU_PULLDOWN_OPENING_KEY_PATTERN",
  );
  const MENU_PULLDOWN_SKIPPED_KEY_NAMES = settings(
    "MENU_PULLDOWN_SKIPPED_KEY_NAMES",
  );
  const NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES = settings(
    "NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES",
  );
  const NUMBER_SMALLEST_PRINTED_PERCENT = settings(
    "NUMBER_SMALLEST_PRINTED_PERCENT",
  );
  const PANE_SPLITTER_WIDEST_WINDOW_SHARE = settings(
    "PANE_SPLITTER_WIDEST_WINDOW_SHARE",
  );
  const STORAGE_OWNED_KEYS = settings("STORAGE_OWNED_KEYS");
  const STORAGE_OWNED_PREFIXES = settings("STORAGE_OWNED_PREFIXES");
  const STORAGE_VERSION = settings("STORAGE_VERSION");
  const STORAGE_VERSION_KEY = settings("STORAGE_VERSION_KEY");
  const STYLE_DESIGN_COORDINATES_WIDTH_PX = settings(
    "STYLE_DESIGN_COORDINATES_WIDTH_PX",
  );
  const STYLE_DESIGN_FONT_CHARACTER_WIDTH_PX = settings(
    "STYLE_DESIGN_FONT_CHARACTER_WIDTH_PX",
  );
  const STYLE_DESIGN_FONT_FIT_PROPERTY = settings(
    "STYLE_DESIGN_FONT_FIT_PROPERTY",
  );
  const STYLE_DESIGN_FONT_SIZE_PX = settings("STYLE_DESIGN_FONT_SIZE_PX");
  const STYLE_DESIGN_MINIMUM_WINDOW_WIDTH_PX = settings(
    "STYLE_DESIGN_MINIMUM_WINDOW_WIDTH_PX",
  );
  const STYLE_DESIGN_SCALE_DEFAULT_MULTIPLE = settings(
    "STYLE_DESIGN_SCALE_DEFAULT_MULTIPLE",
  );
  const STYLE_DESIGN_SCALE_DEFAULT_TRAVEL_SHARE = settings(
    "STYLE_DESIGN_SCALE_DEFAULT_TRAVEL_SHARE",
  );
  const STYLE_DESIGN_SCALE_LARGEST_MULTIPLE = settings(
    "STYLE_DESIGN_SCALE_LARGEST_MULTIPLE",
  );
  const STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE = settings(
    "STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE",
  );
  const STYLE_DESIGN_SCALE_STOP_COUNT = settings(
    "STYLE_DESIGN_SCALE_STOP_COUNT",
  );
  const STYLE_DESIGN_SCALE_STOP_MULTIPLE_FRACTION_DIGITS = settings(
    "STYLE_DESIGN_SCALE_STOP_MULTIPLE_FRACTION_DIGITS",
  );
  const STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY = settings(
    "STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY",
  );
  const STYLE_HEAT_COLOR_STOPS = settings("STYLE_HEAT_COLOR_STOPS");
  const STYLE_PAGE_FONT_FAMILY = settings("STYLE_PAGE_FONT_FAMILY");
  const STYLE_PANE_SPLITTER_KEY_STEP_PX = settings(
    "STYLE_PANE_SPLITTER_KEY_STEP_PX",
  );
  const STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS = settings(
    "STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS",
  );
  const STYLE_TABLE_GROW_COLUMN_NARROWEST_CHARS = settings(
    "STYLE_TABLE_GROW_COLUMN_NARROWEST_CHARS",
  );
  const TABLE_COLUMN_SLIDE_THRESHOLD_PX = settings(
    "TABLE_COLUMN_SLIDE_THRESHOLD_PX",
  );
  const WIDGET_KEY_NAMES = settings("WIDGET_KEY_NAMES");

  // an address's keys in the order a hash writes them, spelled here alone on
  // this side; build_report.py's address_of spells them for Python
  const ADDRESS_KEY_NAMES = [
    "test",
    "view",
    "file",
    "line",
    "function",
    "localProfilePath",
  ];
  // the keys each view reads past test and view
  const ADDRESS_VIEW_KEY_NAMES = new Map([
    [CALLERS_VIEW_KEY, []],
    [FLAME_GRAPH_VIEW_ENTRY[0], ["localProfilePath"]],
    [HEAT_MAP_VIEW_ENTRY[0], ["file", "line", "function"]],
  ]);
  // what CSS measures a ch as: the advance width of this glyph
  const CH_UNIT_GLYPH = "0";
  const DESIGN_SCALE_LAST_STOP = STYLE_DESIGN_SCALE_STOP_COUNT - 1;
  const DESIGN_SCALE_STORAGE_KEY = "view.scale";
  const PULLDOWN_COMMAND_KEY_NAMES = Object.values(MENU_PULLDOWN_KEY_NAMES);
  const RAMP_CHANNEL_STOPS = STYLE_HEAT_COLOR_STOPS.map((hex) =>
    [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16)),
  );
  // the report's top page, found from this script's place in assets/: where
  // a view opened alone opens every address that view is asked for
  const REPORT_TOP_PAGE_HREF = new URL(
    "../index.html",
    document.currentScript.src,
  ).href;

  const is_framed = window.parent !== window;
  // the overview's home under its menu and the frame beside the home, which
  // frame.js shows and the scale zooms. Only the overview has them.
  const home_panel = document.getElementById("overview-home-");
  const view_frame = document.getElementById("overview-view-frame-");
  // whether the scale bar zooms those two: a framed page inherits their zoom
  const is_scaled = !is_framed && !!home_panel;
  const registered_panes = [];
  let resize_debounce_timer = null;
  let storage_is_checked = false;
  // on a framed page, whether keys typed here go on to the top page's open
  // tests pulldown: from a letter sent up until it says the pulldown closed
  let tests_pulldown_is_open = false;
  let design_scale = 1;
  // a scaled page's stop on the scale bar, read once view_storage exists
  let design_scale_travel_stop = null;

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

  // One half of the scale bar: the multiples it runs between and the travel
  // it covers. The lower half ends at the default, the upper starts at it.
  function design_scale_half_of(is_lower_half) {
    return is_lower_half
      ? {
          from_multiple: STYLE_DESIGN_SCALE_SMALLEST_MULTIPLE,
          to_multiple: STYLE_DESIGN_SCALE_DEFAULT_MULTIPLE,
          travel_start: 0,
          travel_width: STYLE_DESIGN_SCALE_DEFAULT_TRAVEL_SHARE,
        }
      : {
          from_multiple: STYLE_DESIGN_SCALE_DEFAULT_MULTIPLE,
          to_multiple: STYLE_DESIGN_SCALE_LARGEST_MULTIPLE,
          travel_start: STYLE_DESIGN_SCALE_DEFAULT_TRAVEL_SHARE,
          travel_width: 1 - STYLE_DESIGN_SCALE_DEFAULT_TRAVEL_SHARE,
        };
  }
  // The multiple a stop of the scale bar zooms the main page contents by:
  // each half climbs geometrically, rounded to the decimals the bar prints.
  function design_scale_multiple_of(travel_stop) {
    const travel_fraction = travel_stop / DESIGN_SCALE_LAST_STOP;
    const half = design_scale_half_of(
      travel_fraction < STYLE_DESIGN_SCALE_DEFAULT_TRAVEL_SHARE,
    );
    const half_fraction =
      (travel_fraction - half.travel_start) / half.travel_width;
    const multiple =
      half.from_multiple *
      Math.pow(half.to_multiple / half.from_multiple, half_fraction);
    const digit_count = STYLE_DESIGN_SCALE_STOP_MULTIPLE_FRACTION_DIGITS;
    return rounded_units(multiple, digit_count) / Math.pow(10, digit_count);
  }
  // The multiple a stop zooms the main page contents by, as the bar prints it.
  function design_scale_multiple_text(travel_stop) {
    return (
      fixed_text(
        design_scale_multiple_of(travel_stop),
        STYLE_DESIGN_SCALE_STOP_MULTIPLE_FRACTION_DIGITS,
      ) + "x"
    );
  }
  function design_scale_travel_now() {
    return design_scale_travel_stop;
  }
  // Refuse anything but one of the scale bar's stops, naming it.
  function design_scale_stop_check(travel_stop) {
    if (
      !Number.isInteger(travel_stop) ||
      travel_stop < 0 ||
      travel_stop > DESIGN_SCALE_LAST_STOP
    ) {
      throw new Error(
        window.ui_strings.text_fill("str_error_scale_stop_unusable", [
          travel_stop,
          DESIGN_SCALE_LAST_STOP,
        ]),
      );
    }
  }
  // The stop view_storage holds, else the default one. Anything else is
  // refused: the STORAGE_VERSION bump swept what an older report stored.
  function design_scale_stored_stop() {
    const stored_stop = view_storage.value_read(DESIGN_SCALE_STORAGE_KEY);
    const travel_stop =
      stored_stop === null
        ? STYLE_DESIGN_SCALE_DEFAULT_TRAVEL_SHARE * DESIGN_SCALE_LAST_STOP
        : stored_stop;
    design_scale_stop_check(travel_stop);
    return travel_stop;
  }
  // Put the scale bar on a stop, store it and redraw at it, the way a
  // resize does. The one door every change of scale takes.
  function design_scale_travel_set(travel_stop) {
    design_scale_stop_check(travel_stop);
    design_scale_travel_stop = travel_stop;
    view_storage.value_write(DESIGN_SCALE_STORAGE_KEY, travel_stop);
    design_scale_settle();
  }
  // Fit the box's font to the design font: measure what its ch comes out
  // as at the design size, and scale every font size so a ch is the design ch.
  function font_fit_apply() {
    const context = document.createElement("canvas").getContext("2d");
    const wanted_font =
      STYLE_DESIGN_FONT_SIZE_PX + "px " + STYLE_PAGE_FONT_FAMILY;
    const default_font = context.font;
    context.font = wanted_font;
    // a font string the canvas cannot read leaves its default in place
    if (context.font === default_font) {
      throw new Error(window.ui_strings.text_of("str_error_font_refused"));
    }
    const measured_px = context.measureText(CH_UNIT_GLYPH).width;
    document.documentElement.style.setProperty(
      STYLE_DESIGN_FONT_FIT_PROPERTY,
      String(STYLE_DESIGN_FONT_CHARACTER_WIDTH_PX / measured_px),
    );
  }
  // The zoom of the page's own root: the window's fit on top, 1 on a framed
  // page, laid out inside its already-zoomed frame, so design space already.
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
    // a scaled page's home panel and view frame take the multiple; the home
    // panel holds every length a pointer measures, so design_px() has both
    const multiple = is_scaled
      ? design_scale_multiple_of(design_scale_travel_stop)
      : 1;
    const wanted = root_zoom * multiple;
    if (!isFinite(wanted) || !(wanted > 0)) {
      throw new Error(
        window.ui_strings.text_fill("str_error_scale_unusable", [wanted]),
      );
    }
    design_scale = wanted;
    root_element.style.zoom = String(root_zoom);
    // an unframed page holds the design width, the window's own at the zoom
    // floor's window width and wider; below that the window scrolls sideways
    if (!is_framed)
      root_element.style.minWidth = STYLE_DESIGN_COORDINATES_WIDTH_PX + "px";
    // a vh resolves against the unzoomed window and is then zoomed with
    // everything else, so a full-height rule reads this design-space height
    root_element.style.setProperty(
      STYLE_DESIGN_VIEWPORT_HEIGHT_PROPERTY,
      root_element.clientHeight / root_zoom + "px",
    );
    if (!is_scaled) return;
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
    if (percent >= 9.95) return fixed_text(percent, 1) + "%";
    if (percent >= NUMBER_SMALLEST_PRINTED_PERCENT) {
      return fixed_text(percent, 2) + "%";
    }
    return percent > 0 ? "<0.01%" : "";
  }
  function multiple_text(percent) {
    if (percent <= 100) return percent_text(percent);
    const times = percent / 100;
    return times < NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES
      ? fixed_text(times, 2) + "x"
      : ">1000x";
  }
  function signed_human_text(number) {
    if (!number) return "";
    return (number < 0 ? "-" : "") + human_text(Math.abs(number));
  }
  // A diff share: a change against that thing's own baseline count, null
  // when the baseline never had it. A fall past the baseline is refused.
  function diff_share_of(delta, baseline) {
    const baseline_count = baseline === null ? 0 : baseline;
    if (delta < -baseline_count) {
      throw new Error(
        window.ui_strings.text_fill("str_error_diff_fall_past_baseline", [
          delta,
          baseline_count,
        ]),
      );
    }
    if (!delta) return 0;
    return baseline_count ? (100 * delta) / baseline_count : Infinity;
  }
  function signed_percent_text(percent) {
    if (!percent) return "";
    if (percent === Infinity) return "▲∞%";
    const arrow = percent < 0 ? "▼" : "▲";
    const sign = percent < 0 ? "-" : "";
    if (Math.abs(percent) < NUMBER_SMALLEST_PRINTED_PERCENT) {
      return arrow + "≈0.00%";
    }
    const body = multiple_text(Math.abs(percent));
    return arrow + (body[0] === ">" ? "" : sign) + body;
  }

  function parent_post(payload) {
    if (is_framed) window.parent.postMessage(payload, "*");
  }
  function parent_listen(on_parent_message) {
    window.addEventListener(
      "message",
      window.catch_show_throw((message_event) => {
        if (is_framed && message_event.source === window.parent) {
          on_parent_message(message_event.data);
        }
      }),
    );
  }
  // One address value as every page writes it, escaped as by
  // encodeURIComponent, a "/" kept readable. Decoding reads it back.
  function hash_value_encode(value) {
    return encodeURIComponent(value).replace(/%2F/g, "/");
  }

  // An address fault's Error, its text a ui string filled with the values.
  function address_error(string_id, fill_values) {
    return new Error(window.ui_strings.text_fill(string_id, fill_values));
  }
  // One value a hash part holds, decoded. A bad escape is that part's fault,
  // the browser's own error kept as the cause.
  function address_value_decode(part, encoded_value) {
    try {
      return decodeURIComponent(encoded_value);
    } catch (decode_error) {
      if (!(decode_error instanceof URIError)) throw decode_error;
      throw new Error(
        window.ui_strings.text_fill("str_error_hash_part_unknown", [part]),
        { cause: decode_error },
      );
    }
  }
  // Refuse an address no page shows. No empty value, a test with a known
  // view, keys that view reads, a line in a file, a function on its own.
  function address_parts_check(parsed_address) {
    for (const key_name of ADDRESS_KEY_NAMES) {
      if (parsed_address[key_name] === "")
        throw address_error("str_error_hash_value_empty", [key_name]);
    }
    const is_home = ADDRESS_KEY_NAMES.every(
      (key_name) => parsed_address[key_name] === null,
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
  // An address's parts from a hash, in any order, each key it leaves out
  // null, "" and "#" being the overview's home. Each fault throws its own.
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
  // The hash naming an address, its keys in ADDRESS_KEY_NAMES order, a key
  // left out or null not written. The home is "#", as "" reloads a page.
  function address_hash_of(partial_address) {
    const hash_parts = [];
    for (const key_name of ADDRESS_KEY_NAMES) {
      if (partial_address[key_name] == null) continue;
      hash_parts.push(
        `${key_name}=${hash_value_encode(String(partial_address[key_name]))}`,
      );
    }
    return "#" + hash_parts.join("&");
  }
  // The hash opening a view of a test at its home, the twin of
  // build_report.py's address_of. A flame graph's names localProfilePath.
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
  // The address a plain click on an address link asks for, else "" for a click
  // a page already took, not the main button's, with a key held, to a tab.
  function address_link_hash_of(click_event) {
    const link_element = click_event.target.closest('a[href^="#"]');
    const is_plain_click =
      !click_event.defaultPrevented &&
      !click_event.button &&
      !click_event.altKey &&
      !click_event.ctrlKey &&
      !click_event.metaKey &&
      !click_event.shiftKey;
    return link_element && !link_element.target && is_plain_click
      ? link_element.getAttribute("href")
      : "";
  }
  // The page showing an address's view, from the report root, the test's
  // own callers page, else the one page of the heat map or flame graph.
  function address_page_href_of(checked_address) {
    if (checked_address.view === CALLERS_VIEW_KEY)
      return encodeURIComponent(checked_address.test) + "/index.html";
    if (checked_address.view === HEAT_MAP_VIEW_ENTRY[0])
      return HEAT_MAP_VIEW_ENTRY[2];
    if (checked_address.view === FLAME_GRAPH_VIEW_ENTRY[0])
      return FLAME_GRAPH_VIEW_ENTRY[2];
    throw address_error("str_error_hash_view_unknown", [checked_address.view]);
  }
  // Ask for an address. A framed view asks the top page's frame.js, and a
  // view opened alone opens the report's top page at it.
  function address_request_send(hash) {
    if (is_framed) parent_post({ report_ui: "address_request", hash });
    else location.assign(REPORT_TOP_PAGE_HREF + hash);
  }

  function pulldown_key_is_command(key_name) {
    return PULLDOWN_COMMAND_KEY_NAMES.includes(key_name);
  }
  // What this keydown gives a pulldown: a typed character or one of
  // MENU_PULLDOWN_KEY_NAMES, or "" for a key that stays the page's.
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
  // What a keydown gives the menu, on the top page or on a view, its pulldown
  // key, unless typed in a field, which types for itself. Never Tab.
  function view_key_of(key_event) {
    return key_event.target.closest("input, select, textarea")
      ? ""
      : pulldown_key_of(key_event);
  }
  // Whether a key opens the tests pulldown with itself in the search box.
  function view_key_opens_tests_pulldown(key_name) {
    return new RegExp(MENU_PULLDOWN_OPENING_KEY_PATTERN).test(key_name);
  }
  // Send a key typed on a framed view up to the top page's menu, a typed
  // character always, a command key while the tests pulldown is open.
  function view_key_forward(key_name) {
    const is_command_key = pulldown_key_is_command(key_name);
    if (!is_framed || (is_command_key && !tests_pulldown_is_open))
      return false;
    if (view_key_opens_tests_pulldown(key_name)) tests_pulldown_is_open = true;
    parent_post({ report_ui: "menu_key_pressed", key: key_name });
    return true;
  }
  // The top page's tests pulldown closed: keys typed here stop going to it.
  function view_key_tests_pulldown_closed() {
    tests_pulldown_is_open = false;
  }
  // The key a focused widget may take from this keydown, or "" for one a
  // page took already, one composing text, or one held with a modifier.
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
  // Whether a key opens a focused widget's item as a click on that item does.
  function widget_key_activates(key_name) {
    return (
      key_name === WIDGET_KEY_NAMES.activate ||
      key_name === WIDGET_KEY_NAMES.click
    );
  }
  // A focused link answers WIDGET_KEY_NAMES.click as a button does, once a
  // press, as the browser gives a link Enter alone.
  function link_click_key_take(key_event) {
    if (
      widget_key_of(key_event) !== WIDGET_KEY_NAMES.click ||
      !key_event.target.matches("a[href]")
    )
      return;
    key_event.preventDefault();
    if (!key_event.repeat) key_event.target.click();
  }
  // Wire a view to the top page. An address link asks for its address, a
  // focused link takes the click key, other keys go up, strings come down.
  function view_activate(view_options) {
    document.addEventListener(
      "click",
      window.catch_show_throw((click_event) => {
        const link_hash = address_link_hash_of(click_event);
        if (!link_hash) return;
        click_event.preventDefault();
        address_request_send(link_hash);
      }),
    );
    // a widget's own keydown ran first: a key taken there is default-prevented
    document.addEventListener(
      "keydown",
      window.catch_show_throw((key_event) => {
        link_click_key_take(key_event);
        const key_name = view_key_of(key_event);
        if (key_name && view_key_forward(key_name)) key_event.preventDefault();
      }),
    );
    // recenter is the view's own, null on a view with nothing to recenter,
    // and preferences_apply, where given, shows its stored choices again
    parent_listen((message_data) => {
      if (message_data === "report_ui:layout_reset") {
        layout_reset();
        if (view_options.preferences_apply) view_options.preferences_apply();
      } else if (
        message_data === "report_ui:recenter" &&
        view_options.recenter
      )
        view_options.recenter();
      else if (message_data === "report_ui:tests_pulldown_closed")
        view_key_tests_pulldown_closed();
      else if (
        typeof message_data === "string" &&
        message_data.startsWith("report_ui:")
      )
        throw new Error(
          window.ui_strings.text_fill("str_error_message_tag_unknown", [
            message_data,
          ]),
        );
    });
  }

  function width_total(widths) {
    return widths.reduce((total, width) => total + width, 0);
  }
  // theme.py's Theme has the twin of each column_ function below, under the
  // same name, doing the same arithmetic, so both kinds of page agree
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
      extent.content_chars + STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS,
      widest + STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS,
    ];
  }
  // Automatic table layout on the container's 100cqw: all widest if they
  // fit, all narrowest if not even those, else between
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
  }
  function column_elements_of(table_element) {
    return [...table_element.querySelectorAll(":scope > colgroup > col")];
  }
  const default_prevent = window.catch_show_throw((any_event) => {
    any_event.preventDefault();
  });
  // The click a slide's pointerup brings is taken before any handler sees
  // it, so a slide never follows a link or opens a row.
  const click_swallow = window.catch_show_throw((click_event) => {
    click_event.preventDefault();
    click_event.stopPropagation();
  });
  const selection_drop = window.catch_show_throw(() => {
    window.getSelection().removeAllRanges();
  });
  // A press on column N, N from 1, slides it and every column right of it
  // once it travels past the threshold more sideways than up or down.
  function table_slide_press(press_event, table_element) {
    const pressed_cell = press_event.target.closest("td, th");
    if (
      press_event.button ||
      !pressed_cell ||
      pressed_cell.closest("table") !== table_element ||
      pressed_cell.cellIndex < 1
    )
      return;
    const column_index = pressed_cell.cellIndex;
    const left_column = column_elements_of(table_element)[column_index - 1];
    const floor_text = left_column.getAttribute("data-min-");
    const start_client_x = press_event.clientX,
      start_client_y = press_event.clientY;
    // a rect and clientX are screen px on a zoomed page; a style is design px
    const start_width_px = design_px(
      pressed_cell.previousElementSibling.getBoundingClientRect().width,
    );
    let animation_frame = 0,
      is_sliding = false;
    const on_pointer_move = window.catch_show_throw((move_event) => {
      if (move_event.pointerId !== press_event.pointerId) return;
      const sideways_travel_px = design_px(
        move_event.clientX - start_client_x,
      );
      const vertical_travel_px = design_px(
        move_event.clientY - start_client_y,
      );
      if (!is_sliding) {
        const travel_px = Math.hypot(sideways_travel_px, vertical_travel_px);
        if (travel_px <= TABLE_COLUMN_SLIDE_THRESHOLD_PX) return;
        // a press leaving more up or down than sideways stays the page's
        if (Math.abs(vertical_travel_px) >= Math.abs(sideways_travel_px)) {
          press_end();
          return;
        }
        is_sliding = true;
        selection_drop();
        document.addEventListener("selectionchange", selection_drop);
      }
      // the floor is the <col>'s own characters, which CSS max() compares
      const wanted_width_px = start_width_px + sideways_travel_px;
      left_column.style.width = `max(${floor_text}, ${wanted_width_px}px)`;
      if (animation_frame) return;
      animation_frame = requestAnimationFrame(
        window.catch_show_throw(() => {
          animation_frame = 0;
          layout_refresh();
        }),
      );
    });
    const on_pointer_release = window.catch_show_throw((release_event) => {
      if (release_event.pointerId !== press_event.pointerId) return;
      press_end();
      if (!is_sliding) return;
      document.removeEventListener("selectionchange", selection_drop);
      if (release_event.type !== "pointerup") return;
      // the click is sent in the same task as its pointerup, so this
      // listener is gone again before any later click
      window.addEventListener("click", click_swallow, true);
      setTimeout(
        window.catch_show_throw(() => {
          window.removeEventListener("click", click_swallow, true);
        }),
      );
    });
    function press_end() {
      listeners_bind(window, on_pointer_move, on_pointer_release, false);
      window.removeEventListener("dragstart", default_prevent, true);
    }
    listeners_bind(window, on_pointer_move, on_pointer_release, true);
    // a link or selection dragged natively would take the pointer away
    window.addEventListener("dragstart", default_prevent, true);
  }
  // Let a table's columns slide, keeping each <col>'s emitted width for
  // layout_reset(). A table already reached is left as it is.
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
      window.catch_show_throw((press_event) =>
        table_slide_press(press_event, table_element),
      ),
    );
  }
  function offsets_align(scroll_container) {
    let stacked_top_px = 0;
    for (const band_element of scroll_container.querySelectorAll(
      ":scope > .band_",
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
    const band_elements = [...root_element.querySelectorAll(".band_")];
    new Set(
      band_elements.map((band_element) => band_element.parentElement),
    ).forEach(offsets_align);
  }
  // Wire every table under a root. Its columns slide, and one whose body
  // holds links walks its rows from the keyboard as one tab stop.
  function layout_activate(root_element) {
    root_element = root_element || document.body;
    const table_elements = root_element.querySelectorAll(
      ".table-columns- > table.columns_",
    );
    for (const table_element of table_elements) {
      table_slide_attach(table_element);
      if (table_element.tBodies[0].querySelector("a[href]"))
        table_rows_attach(table_element, "tr");
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
      pane_entry.pane_element.style.width = "";
      view_storage.value_write(pane_entry.storage_key, null);
      pane_entry.splitter_values_show();
    }
    layout_refresh(root_element);
  }

  // The nearest box scrolling a focused element up and down.
  function scroller_of(focused_element) {
    let scrolling_box = focused_element.parentElement;
    while (!/^(auto|scroll)$/.test(getComputedStyle(scrolling_box).overflowY))
      scrolling_box = scrolling_box.parentElement;
    return scrolling_box;
  }
  // Show a focused element whole in its scrolling box, at its nearest
  // edge, then out from under its table's column titles where those stick.
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
  // Make an item its widget's one tab stop in place of the previous one,
  // null for none, focused and shown when that item takes the focus.
  function tab_stop_move(previous_stop, next_stop, takes_focus) {
    if (previous_stop && previous_stop !== next_stop)
      previous_stop.tabIndex = -1;
    next_stop.tabIndex = 0;
    if (!takes_focus) return;
    next_stop.focus({ preventScroll: true });
    focus_reveal(next_stop);
  }
  // A row's own links, not those of a table nested in one of its cells.
  function row_links_of(row_element) {
    return [...row_element.querySelectorAll("a[href]")].filter(
      (row_link) => row_link.closest("tr") === row_element,
    );
  }
  // The walked row of a table body an element sits in, else null.
  function walked_row_of(focused_element, table_body, row_selector) {
    const row_element = focused_element.closest("tr");
    const is_walked =
      !!row_element &&
      row_element.parentElement === table_body &&
      row_element.matches(row_selector);
    return is_walked ? row_element : null;
  }
  // The walked row a step from a row, 1 the next and -1 the one before, or
  // null past either end.
  function walked_row_beside(row_element, row_selector, step_direction) {
    const sibling_name =
      step_direction > 0 ? "nextElementSibling" : "previousElementSibling";
    let sibling_row = row_element[sibling_name];
    while (sibling_row && !sibling_row.matches(row_selector))
      sibling_row = sibling_row[sibling_name];
    return sibling_row;
  }
  // Make a walked row its table's one tab stop, focused and shown when that
  // row takes the focus.
  function table_row_tab_stop_set(row_element, takes_focus) {
    tab_stop_move(
      row_element.parentElement.querySelector(':scope > tr[tabindex="0"]'),
      row_element,
      takes_focus,
    );
  }
  // A key on a walked row or one of its links, the treegrid pattern's. Up,
  // Down, Home and End between rows, Right and Left through a row's links.
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
    // a focused link opens itself, Enter natively, the click key as a click
    if (link_index >= 0 && widget_key_activates(key_name)) {
      link_click_key_take(key_event);
      return;
    }
    if (focused_element !== row_element && link_index < 0) return;
    if (widget_key_activates(key_name)) {
      key_event.preventDefault();
      // a row opens as a click on its first link does, else as one on the row
      const clicked_element = row_links.length ? row_links[0] : row_element;
      if (!key_event.repeat) clicked_element.click();
      return;
    }
    const walked_rows_of = () =>
      [...table_body.rows].filter((walked_row) =>
        walked_row.matches(row_selector),
      );
    let next_element = null;
    switch (key_name) {
      case WIDGET_KEY_NAMES.down:
        next_element = walked_row_beside(row_element, row_selector, 1);
        break;
      case WIDGET_KEY_NAMES.first:
        next_element = walked_rows_of()[0];
        break;
      case WIDGET_KEY_NAMES.last:
        next_element = walked_rows_of().pop();
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
    // a link takes the focus while its row stays the table's tab stop
    next_element.focus({ preventScroll: true });
    focus_reveal(next_element);
  }
  // Make a table whose rows open something one tab stop. Its walked rows,
  // those of its body matching row_selector, take table_row_key_take's keys.
  function table_rows_attach(table_element, row_selector) {
    if (table_element.is_row_walk_attached) return;
    table_element.is_row_walk_attached = true;
    const table_body = table_element.tBodies[0];
    const walked_rows = [...table_body.rows].filter((walked_row) =>
      walked_row.matches(row_selector),
    );
    if (!walked_rows.length) return;
    table_element.setAttribute("role", "treegrid");
    for (const walked_row of walked_rows) {
      walked_row.tabIndex = -1;
      for (const row_link of row_links_of(walked_row)) row_link.tabIndex = -1;
    }
    walked_rows[0].tabIndex = 0;
    // focus on a row or its link, by key or pointer, makes the row the stop
    table_element.addEventListener(
      "focusin",
      window.catch_show_throw((focus_event) => {
        const row_element = walked_row_of(
          focus_event.target,
          table_body,
          row_selector,
        );
        if (row_element) table_row_tab_stop_set(row_element, false);
      }),
    );
    table_element.addEventListener(
      "keydown",
      window.catch_show_throw((key_event) =>
        table_row_key_take(key_event, table_body, row_selector),
      ),
    );
  }

  // Remove every key the report owns but kept_key. A version change sweeps
  // them all, the reset button all but the scale bar's stop.
  function storage_sweep(kept_key) {
    const doomed_keys = [];
    for (let index = 0; index < localStorage.length; index++) {
      const storage_key = localStorage.key(index);
      if (storage_key === null || storage_key === kept_key) continue;
      const is_owned =
        STORAGE_OWNED_KEYS.indexOf(storage_key) !== -1 ||
        STORAGE_OWNED_PREFIXES.some((prefix) =>
          storage_key.startsWith(prefix),
        );
      if (is_owned) doomed_keys.push(storage_key);
    }
    for (const storage_key of doomed_keys) {
      localStorage.removeItem(storage_key);
    }
  }
  function storage_version_check() {
    if (storage_is_checked) return;
    storage_is_checked = true;
    try {
      if (localStorage.getItem(STORAGE_VERSION_KEY) === STORAGE_VERSION) {
        return;
      }
      storage_sweep(null);
      localStorage.setItem(STORAGE_VERSION_KEY, STORAGE_VERSION);
    } catch (storage_error) {}
  }
  const view_storage = {
    // The reset button's door. Every owned key but the scale bar's goes,
    // heat.* and split.*, so each view shows its defaults again.
    preferences_clear() {
      storage_version_check();
      try {
        storage_sweep(DESIGN_SCALE_STORAGE_KEY);
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
        if (stored_value == null) localStorage.removeItem(storage_key);
        else {
          localStorage.setItem(storage_key, JSON.stringify(stored_value));
        }
      } catch (storage_error) {}
    },
  };

  // Make a handle the window splitter of the preceding pane, the pattern's
  // separator. A pointer's drag, an arrow's step, Home and End to its ends.
  function pane_splitter_attach(
    handle_bar,
    pane_element,
    storage_key,
    minimum_px,
  ) {
    storage_key = "split." + storage_key;
    // the widest the pane may be, the window's share, the narrowest its own
    const pane_widest_px = () =>
      design_px(window.innerWidth) * PANE_SPLITTER_WIDEST_WINDOW_SHARE;
    const pane_width_of = (wanted_width_px) =>
      Math.min(pane_widest_px(), Math.max(minimum_px, wanted_width_px));
    const pane_width_now = () =>
      design_px(pane_element.getBoundingClientRect().width);
    // where the splitter sits as a screen reader reads it, the pane's width
    // in design px between its narrowest and widest
    function splitter_values_show() {
      handle_bar.setAttribute("aria-valuemin", String(minimum_px));
      handle_bar.setAttribute(
        "aria-valuemax",
        String(Math.round(pane_widest_px())),
      );
      handle_bar.setAttribute(
        "aria-valuenow",
        String(Math.round(pane_width_now())),
      );
    }
    // the width a drag or a key left, stored as the pane's own
    function pane_width_store() {
      view_storage.value_write(storage_key, pane_width_now());
      splitter_values_show();
    }
    registered_panes.push({ pane_element, splitter_values_show, storage_key });
    const saved_width = view_storage.value_read(storage_key);
    if (saved_width) pane_element.style.width = saved_width + "px";
    handle_bar.tabIndex = 0;
    handle_bar.setAttribute("role", "separator");
    handle_bar.setAttribute("aria-orientation", "vertical");
    handle_bar.setAttribute("aria-controls", pane_element.id);
    handle_bar.setAttribute("aria-labelledby", pane_element.id);
    splitter_values_show();
    const on_pointer_down = window.catch_show_throw((pointer_event) => {
      const start_client_x = pointer_event.clientX;
      const start_width_px = pane_width_now();
      if (handle_bar.setPointerCapture) {
        handle_bar.setPointerCapture(pointer_event.pointerId);
      }
      let animation_frame = 0;
      const on_pointer_move = window.catch_show_throw((move_event) => {
        pane_element.style.width =
          pane_width_of(
            start_width_px + design_px(move_event.clientX - start_client_x),
          ) + "px";
        if (animation_frame) return;
        animation_frame = requestAnimationFrame(
          window.catch_show_throw(() => {
            animation_frame = 0;
            layout_refresh();
          }),
        );
      });
      const on_pointer_release = window.catch_show_throw(() => {
        listeners_bind(handle_bar, on_pointer_move, on_pointer_release, false);
        pane_width_store();
      });
      listeners_bind(handle_bar, on_pointer_move, on_pointer_release, true);
      pointer_event.preventDefault();
    });
    const on_key_down = window.catch_show_throw((key_event) => {
      let wanted_width_px = 0;
      switch (widget_key_of(key_event)) {
        case WIDGET_KEY_NAMES.first:
          wanted_width_px = minimum_px;
          break;
        case WIDGET_KEY_NAMES.last:
          wanted_width_px = pane_widest_px();
          break;
        case WIDGET_KEY_NAMES.left:
          wanted_width_px = pane_width_now() - STYLE_PANE_SPLITTER_KEY_STEP_PX;
          break;
        case WIDGET_KEY_NAMES.right:
          wanted_width_px = pane_width_now() + STYLE_PANE_SPLITTER_KEY_STEP_PX;
          break;
        default:
          return;
      }
      key_event.preventDefault();
      pane_element.style.width = pane_width_of(wanted_width_px) + "px";
      layout_refresh();
      pane_width_store();
    });
    handle_bar.addEventListener("pointerdown", on_pointer_down);
    handle_bar.addEventListener("keydown", on_key_down);
    // a resize moves the pane's widest, so each focus reads the values again
    handle_bar.addEventListener(
      "focus",
      window.catch_show_throw(splitter_values_show),
    );
  }

  // Redraw at the scale in force and settle the layout after it. The one
  // path a resize and a scale change both take.
  function design_scale_settle() {
    design_scale_apply();
    clearTimeout(resize_debounce_timer);
    resize_debounce_timer = setTimeout(
      window.catch_show_throw(layout_refresh),
      LAYOUT_RESIZE_SETTLE_DELAY_MS,
    );
  }

  font_fit_apply();
  if (is_scaled) design_scale_travel_stop = design_scale_stored_stop();
  design_scale_apply();
  window.addEventListener(
    "resize",
    window.catch_show_throw(design_scale_settle),
  );
  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      window.catch_show_throw(() => layout_activate()),
    );
  } else layout_activate();
  return {
    address: {
      hash_of: address_hash_of,
      home_hash_of: address_home_hash_of,
      link_hash_of: address_link_hash_of,
      of_hash: address_of_hash,
      page_href_of: address_page_href_of,
      request: address_request_send,
    },
    column_extents,
    column_limits,
    column_longest,
    column_width_text,
    design_px,
    design_scale_last_stop: DESIGN_SCALE_LAST_STOP,
    design_scale_multiple_text,
    design_scale_travel_now,
    design_scale_travel_set,
    diff_share_of,
    home_panel,
    human_text,
    layout_activate,
    layout_refresh,
    layout_reset,
    multiple_text,
    pane_splitter: { attach: pane_splitter_attach },
    percent_text,
    pulldown_key: {
      is_command: pulldown_key_is_command,
      of: pulldown_key_of,
    },
    ramp_channels_at,
    signed_human_text,
    signed_percent_text,
    tab_stop_move,
    table_rows: {
      attach: table_rows_attach,
      tab_stop_set: table_row_tab_stop_set,
    },
    view_activate,
    view_frame,
    view_key: {
      of: view_key_of,
      opens_tests_pulldown: view_key_opens_tests_pulldown,
    },
    view_storage,
    widget_key: {
      activates: widget_key_activates,
      link_click_take: link_click_key_take,
      of: widget_key_of,
    },
  };
})();
