window.report_ui = (function () {
  "use strict";

  const LAYOUT_RESIZE_SETTLE_DELAY_MS = settings(
    "LAYOUT_RESIZE_SETTLE_DELAY_MS",
  );
  const MENU_BUTTON_NUMBERS = settings("MENU_BUTTON_NUMBERS");
  const MENU_PULLDOWN_KEY_NAMES = settings("MENU_PULLDOWN_KEY_NAMES");
  const MENU_PULLDOWN_LINE_NUMBER_PATTERN = settings(
    "MENU_PULLDOWN_LINE_NUMBER_PATTERN",
  );
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
  const STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS = settings(
    "STYLE_TABLE_COLUMN_EXTRA_WIDTH_CHARS",
  );
  const STYLE_TABLE_GROW_COLUMN_NARROWEST_CHARS = settings(
    "STYLE_TABLE_GROW_COLUMN_NARROWEST_CHARS",
  );
  const TABLE_COLUMN_SLIDE_THRESHOLD_PX = settings(
    "TABLE_COLUMN_SLIDE_THRESHOLD_PX",
  );

  // what CSS measures a ch as: the advance width of this glyph
  const CH_UNIT_GLYPH = "0";
  const DESIGN_SCALE_LAST_STOP = STYLE_DESIGN_SCALE_STOP_COUNT - 1;
  const DESIGN_SCALE_STORAGE_KEY = "view.scale";
  const PULLDOWN_COMMAND_KEY_NAMES = Object.values(MENU_PULLDOWN_KEY_NAMES);
  const PULLDOWN_HIGHLIGHTED_ENTRY_CLASS = "highlighted-entry-";
  const RAMP_CHANNEL_STOPS = STYLE_HEAT_COLOR_STOPS.map((hex) =>
    [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16)),
  );

  const is_framed = window.parent !== window;
  // a page's home under its menu and the frame beside it, which menu.js and
  // frame.js read from here. Only an overview or a callers page has them.
  const home_panel = document.getElementById("callers-overview-home-");
  const view_frame = document.getElementById("callers-overview-view-frame-");
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
  function logo_color_at(fraction) {
    return `rgb(${ramp_channels_at(fraction).join(",")})`;
  }
  function logo_letters_build(text, class_name, start_fraction) {
    const letters = [...text];
    return letters.map((letter, index) => {
      const letter_element = document.createElement("span");
      letter_element.className = class_name;
      letter_element.textContent = letter;
      letter_element.style.color = logo_color_at(
        letters.length > 1
          ? start_fraction +
              ((1 - start_fraction) * index) / (letters.length - 1)
          : 1,
      );
      return letter_element;
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
  function signed_percent_text(percent) {
    if (!percent) return "";
    const arrow = percent < 0 ? "▼" : "▲";
    const sign = percent < 0 ? "-" : "";
    if (!Number.isFinite(percent)) return arrow + sign + "∞%";
    if (Math.abs(percent) < NUMBER_SMALLEST_PRINTED_PERCENT) {
      return arrow + "≈0.00%";
    }
    const body = multiple_text(Math.abs(percent));
    return arrow + (body[0] === ">" ? "" : sign) + body;
  }

  function parent_post(payload) {
    if (is_framed) window.parent.postMessage(payload, "*");
  }
  function hash_publish(canonical_hash) {
    if (canonical_hash !== location.hash) {
      history.replaceState(null, "", canonical_hash || "#");
    }
    parent_post({ report_ui: "hash_changed", hash: canonical_hash });
  }
  function parent_listen(on_parent_message) {
    window.addEventListener("message", (message_event) => {
      if (is_framed && message_event.source === window.parent) {
        on_parent_message(message_event.data);
      }
    });
  }
  // One hash part's value as the heat map writes it: escaped, a "/" kept
  // readable. state_of_hash decodes it back.
  function hash_value_encode(value) {
    return encodeURIComponent(value).replace(/%2F/g, "/");
  }
  // The heat map's address, its whole state: fn=<name>, or f=<file> and any
  // l=<line>, then e=<counter> when the state names one. The one writer.
  function hash_of_state(state) {
    const hash_parts = [];
    if (state.fn) hash_parts.push("fn=" + hash_value_encode(state.fn));
    else if (state.file) {
      hash_parts.push("f=" + hash_value_encode(state.file));
      if (state.line) hash_parts.push("l=" + state.line);
    }
    if (state.ev) hash_parts.push("e=" + hash_value_encode(state.ev));
    return hash_parts.length ? "#" + hash_parts.join("&") : "";
  }
  // The heat map address's parts. An empty hash is home; a part this cannot
  // read (no "=", a key it has no field for, a bad escape or line) is bad.
  function state_of_hash(hash) {
    const parsed_state = { file: null, line: 0, fn: null, ev: null };
    for (const part of hash.replace(/^#/, "").split("&")) {
      if (part === "") continue;
      const equals_index = part.indexOf("=");
      const key = part.slice(0, equals_index);
      const value = decodeURIComponent(part.slice(equals_index + 1));
      if (equals_index < 0 || (key === "l" && !Number.isInteger(+value))) {
        throw new Error(
          window.ui_strings.text_fill("str_error_hash_part_unknown", [part]),
        );
      }
      if (key === "f") parsed_state.file = value;
      else if (key === "l") parsed_state.line = +value;
      else if (key === "fn") parsed_state.fn = value;
      else if (key === "e") parsed_state.ev = value;
      else
        throw new Error(
          window.ui_strings.text_fill("str_error_hash_part_unknown", [part]),
        );
    }
    return parsed_state;
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
  // What this keydown gives the menu: its pulldown key, unless typed in a
  // field, which types for itself, as an open pulldown's search box does.
  function menu_key_of(key_event) {
    return key_event.target.closest("input, select, textarea")
      ? ""
      : pulldown_key_of(key_event);
  }
  // The numbered button a key activates, by the name in its id, or "".
  function menu_key_button_name(key_name) {
    const button_entry = Object.entries(MENU_BUTTON_NUMBERS).find(
      (candidate_entry) => String(candidate_entry[1]) === key_name,
    );
    return button_entry ? button_entry[0] : "";
  }
  // Whether a key opens the tests pulldown with itself in the search box.
  function menu_key_opens_tests_pulldown(key_name) {
    return new RegExp(MENU_PULLDOWN_OPENING_KEY_PATTERN).test(key_name);
  }
  // Send a key typed on a framed page up to the top page's menu: a button's
  // digit, a letter, any key while the tests pulldown is open. True if sent.
  function menu_key_forward(key_name) {
    const opens_tests_pulldown = menu_key_opens_tests_pulldown(key_name);
    const is_menu_key =
      opens_tests_pulldown || !!menu_key_button_name(key_name);
    if (!is_framed || !(is_menu_key || tests_pulldown_is_open)) return false;
    if (opens_tests_pulldown) tests_pulldown_is_open = true;
    parent_post({ report_ui: "menu_key_pressed", key: key_name });
    return true;
  }
  // The top page's tests pulldown closed: keys typed here stop going to it.
  function menu_key_tests_pulldown_closed() {
    tests_pulldown_is_open = false;
  }
  // The search box's text as a pattern. One that does not compile yet (a
  // lone "(" mid-typing) is null and matches nothing; any other error throws.
  function pulldown_pattern_of(search_text) {
    try {
      return new RegExp(search_text, "i");
    } catch (pattern_error) {
      if (!(pattern_error instanceof SyntaxError)) throw pattern_error;
      return null;
    }
  }
  // A menu pulldown over root_element's parts. entries_of(line_number) gives
  // the links it offers, opening at that line; on_close() runs on each close.
  function pulldown_attach(
    root_element,
    label_text,
    entries_of,
    on_close,
    reads_line_number,
  ) {
    const entry_list = root_element.querySelector(
      ".menu-pulldown-entry-list-",
    );
    const menu_button = root_element.querySelector(".menu-pulldown-button-");
    const no_match_note = root_element.querySelector(
      ".menu-pulldown-no-match-note-",
    );
    const search_box = root_element.querySelector(
      ".menu-pulldown-search-box-",
    );
    let entries = [],
      entries_line_number = 0,
      highlight_index = 0,
      is_open = false,
      matches = [];

    function highlight_set(entry_index) {
      highlight_index = entry_index;
      for (const entry_link of entries) {
        entry_link.classList.toggle(
          PULLDOWN_HIGHLIGHTED_ENTRY_CLASS,
          entry_link === matches[highlight_index],
        );
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
    // The search box's text as the pattern it filters by and the line its
    // entries open at, 0 for none. Only a pulldown reading lines splits one.
    function search_parts_of(search_text) {
      const line_pattern = new RegExp(MENU_PULLDOWN_LINE_NUMBER_PATTERN);
      const line_match = reads_line_number && line_pattern.exec(search_text);
      return line_match ? [line_match[1], +line_match[2]] : [search_text, 0];
    }
    // Offer the links opening at a line, 0 for none, in place of any before.
    function entries_offer(line_number) {
      entries_line_number = line_number;
      entries = entries_of(line_number);
      entry_list.replaceChildren(...entries, no_match_note);
    }
    function entries_filter() {
      const [filter_text, line_number] = search_parts_of(search_box.value);
      if (line_number !== entries_line_number) entries_offer(line_number);
      const search_pattern = pulldown_pattern_of(filter_text);
      matches = entries.filter(
        (entry_link) =>
          !!search_pattern && search_pattern.test(entry_link.textContent),
      );
      const matched_entries = new Set(matches);
      for (const entry_link of entries) {
        entry_link.hidden = !matched_entries.has(entry_link);
      }
      no_match_note.hidden = matches.length > 0;
      entry_list.scrollTop = 0;
      highlight_set(0);
    }
    // Focus the search box, out of a framed page if focus is there: a key's
    // user activation reaches the top page. A refusal would strand the keys.
    function search_box_focus() {
      search_box.focus();
      if (document.activeElement !== search_box)
        throw new Error(
          window.ui_strings.text_fill("str_error_pulldown_focus_refused", [
            document.activeElement.tagName.toLowerCase(),
          ]),
        );
    }
    // The search box takes the button's place while open, the list
    // dropping below it, so the list sits aligned under the button.
    function pulldown_open(search_text) {
      is_open = true;
      entries_offer(search_parts_of(search_text)[1]);
      menu_button.hidden = true;
      search_box.hidden = false;
      search_box.value = search_text;
      entry_list.hidden = false;
      entries_filter();
      search_box_focus();
    }
    function closed_show() {
      is_open = false;
      search_box.hidden = true;
      search_box.value = "";
      menu_button.hidden = false;
      entry_list.hidden = true;
    }
    function pulldown_close() {
      closed_show();
      on_close();
    }
    // The one key handler, for a key typed in the box or handed over from
    // elsewhere on the page. True when the key is taken.
    function key_take(key_name, is_in_search_box) {
      const is_command_key = pulldown_key_is_command(key_name);
      if (!is_open) {
        if (is_command_key) return false;
        pulldown_open(key_name);
        return true;
      }
      switch (key_name) {
        case MENU_PULLDOWN_KEY_NAMES.close:
          pulldown_close();
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
      // the focused open box types for itself; a key from elsewhere is added
      if (is_in_search_box) return false;
      search_box.value += key_name;
      entries_filter();
      search_box_focus();
      return true;
    }

    menu_button.textContent = label_text;
    search_box.placeholder = window.ui_strings.text_of(
      "str_pulldown_placeholder",
    );
    no_match_note.textContent = window.ui_strings.text_of("str_no_match");
    for (const pointer_target of [menu_button, entry_list]) {
      pointer_target.addEventListener("mousedown", (pointer_event) =>
        pointer_event.preventDefault(),
      );
    }
    menu_button.addEventListener("click", () => pulldown_open(""));
    search_box.addEventListener("blur", () => {
      if (is_open) pulldown_close();
    });
    search_box.addEventListener("input", entries_filter);
    search_box.addEventListener("keydown", (key_event) => {
      const key_name = pulldown_key_of(key_event);
      if (key_name && key_take(key_name, true)) key_event.preventDefault();
    });
    entry_list.addEventListener("click", (click_event) => {
      if (!click_event.target.closest("a")) return;
      pulldown_close();
      search_box.blur();
    });
    closed_show();
    return { is_open: () => is_open, key_take };
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
  function default_prevent(any_event) {
    any_event.preventDefault();
  }
  // The click a slide's pointerup brings is taken before any handler sees
  // it, so a slide never follows a link or opens a row.
  function click_swallow(click_event) {
    click_event.preventDefault();
    click_event.stopPropagation();
  }
  function selection_drop() {
    window.getSelection().removeAllRanges();
  }
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
    const on_pointer_move = (move_event) => {
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
      animation_frame = requestAnimationFrame(() => {
        animation_frame = 0;
        layout_refresh();
      });
    };
    const on_pointer_release = (release_event) => {
      if (release_event.pointerId !== press_event.pointerId) return;
      press_end();
      if (!is_sliding) return;
      document.removeEventListener("selectionchange", selection_drop);
      if (release_event.type !== "pointerup") return;
      // the click is sent in the same task as its pointerup, so this
      // listener is gone again before any later click
      window.addEventListener("click", click_swallow, true);
      setTimeout(() => {
        window.removeEventListener("click", click_swallow, true);
      });
    };
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
    table_element.addEventListener("pointerdown", (press_event) =>
      table_slide_press(press_event, table_element),
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
  function layout_activate(root_element) {
    root_element = root_element || document.body;
    const table_elements = root_element.querySelectorAll(
      ".table-columns- > table.columns_",
    );
    for (const table_element of table_elements) {
      table_slide_attach(table_element);
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
    }
    layout_refresh(root_element);
  }

  function storage_sweep() {
    const doomed_keys = [];
    for (let index = 0; index < localStorage.length; index++) {
      const storage_key = localStorage.key(index);
      if (storage_key === null) continue;
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
      storage_sweep();
      localStorage.setItem(STORAGE_VERSION_KEY, STORAGE_VERSION);
    } catch (storage_error) {}
  }
  const view_storage = {
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

  function pane_splitter_attach(
    handle_bar,
    pane_element,
    storage_key,
    minimum_px,
  ) {
    storage_key = "split." + storage_key;
    registered_panes.push({ pane_element, storage_key });
    const saved_width = view_storage.value_read(storage_key);
    if (saved_width) pane_element.style.width = saved_width + "px";
    handle_bar.addEventListener("pointerdown", (pointer_event) => {
      const start_client_x = pointer_event.clientX;
      const start_width_px = design_px(
        pane_element.getBoundingClientRect().width,
      );
      if (handle_bar.setPointerCapture) {
        handle_bar.setPointerCapture(pointer_event.pointerId);
      }
      let animation_frame = 0;
      const on_pointer_move = (move_event) => {
        const wanted_width_px = Math.max(
          minimum_px,
          start_width_px + design_px(move_event.clientX - start_client_x),
        );
        pane_element.style.width =
          Math.min(
            design_px(window.innerWidth) * PANE_SPLITTER_WIDEST_WINDOW_SHARE,
            wanted_width_px,
          ) + "px";
        if (animation_frame) return;
        animation_frame = requestAnimationFrame(() => {
          animation_frame = 0;
          layout_refresh();
        });
      };
      const on_pointer_release = () => {
        listeners_bind(handle_bar, on_pointer_move, on_pointer_release, false);
        view_storage.value_write(
          storage_key,
          design_px(pane_element.getBoundingClientRect().width),
        );
      };
      listeners_bind(handle_bar, on_pointer_move, on_pointer_release, true);
      pointer_event.preventDefault();
    });
  }

  // Redraw at the scale in force and settle the layout after it. The one
  // path a resize and a scale change both take.
  function design_scale_settle() {
    design_scale_apply();
    clearTimeout(resize_debounce_timer);
    resize_debounce_timer = setTimeout(
      layout_refresh,
      LAYOUT_RESIZE_SETTLE_DELAY_MS,
    );
  }

  font_fit_apply();
  if (is_scaled) design_scale_travel_stop = design_scale_stored_stop();
  design_scale_apply();
  window.addEventListener("resize", design_scale_settle);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => layout_activate());
  } else layout_activate();
  return {
    column_extents,
    column_limits,
    column_longest,
    column_width_text,
    design_px,
    design_scale_last_stop: DESIGN_SCALE_LAST_STOP,
    design_scale_multiple_text,
    design_scale_travel_now,
    design_scale_travel_set,
    hash_publish,
    heat_map_address: { hash_of_state, state_of_hash },
    home_panel,
    human_text,
    is_framed,
    layout_activate,
    layout_refresh,
    layout_reset,
    logo_color_at,
    logo_letters_build,
    menu_key: {
      button_name: menu_key_button_name,
      forward: menu_key_forward,
      of: menu_key_of,
      opens_tests_pulldown: menu_key_opens_tests_pulldown,
      tests_pulldown_closed: menu_key_tests_pulldown_closed,
    },
    multiple_text,
    pane_splitter: { attach: pane_splitter_attach },
    parent_listen,
    parent_post,
    percent_text,
    pulldown: {
      attach: pulldown_attach,
    },
    ramp_channels_at,
    signed_human_text,
    signed_percent_text,
    view_frame,
    view_storage,
  };
})();
