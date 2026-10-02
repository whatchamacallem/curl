window.catch_show_throw_(function () {
  "use strict";

  const CALLERS_VIEW_KEY = settings_("CALLERS_VIEW_KEY");
  const DARK_MODE_ENABLED_DEFAULT = settings_("DARK_MODE_ENABLED_DEFAULT");
  const FLAME_GRAPH_VIEW_ENTRY = settings_("FLAME_GRAPH_VIEW_ENTRY");
  const HEAT_MAP_VIEW_ENTRY = settings_("HEAT_MAP_VIEW_ENTRY");
  const MENU_BUTTON_ORDER = settings_("MENU_BUTTON_ORDER");
  const MENU_PULLDOWN_KEY_NAMES = settings_("MENU_PULLDOWN_KEY_NAMES");
  const MENU_PULLDOWN_LINE_NUMBER_PATTERN = settings_(
    "MENU_PULLDOWN_LINE_NUMBER_PATTERN",
  );
  const MENU_PULLDOWN_MERGED_TEST_NAME = settings_(
    "MENU_PULLDOWN_MERGED_TEST_NAME",
  );
  const MENU_SCALE_KEY_NAMES = settings_("MENU_SCALE_KEY_NAMES");
  const STYLE_MENU_LOGO_START_FRACTION = settings_(
    "STYLE_MENU_LOGO_START_FRACTION",
  );

  const CALLERS_LABEL_TEXT = window.ui_strings_.text_of("str_view_callers");
  const DARK_MODE_BUTTON_NAME = "dark-mode";
  const DIGIT_KEY_COUNT = 10;
  const FLAME_GRAPH_VIEW_KEY = FLAME_GRAPH_VIEW_ENTRY[0];
  const HEAT_MAP_VIEW_KEY = HEAT_MAP_VIEW_ENTRY[0];
  const MENU_LOGO_LETTER_CLASS = "menu-logo-letter-";
  const NUMBERED_BUTTON_NAMES = MENU_BUTTON_ORDER.filter(
    (button_name) => button_name !== DARK_MODE_BUTTON_NAME,
  );
  const PULLDOWN_HIGHLIGHTED_ENTRY_CLASS = "highlighted-entry-";
  const REPORT_NAME_TEXT = window.ui_strings_.text_of("str_report_name");
  const TITLE_PART_SEPARATOR = " / ";

  const BUTTON_LABEL_TEXTS = {
    [CALLERS_VIEW_KEY]: CALLERS_LABEL_TEXT,
    file: window.ui_strings_.text_of("str_menu_file"),
    [FLAME_GRAPH_VIEW_KEY]: FLAME_GRAPH_VIEW_ENTRY[1],
    function: window.ui_strings_.text_of("str_menu_function"),
    [HEAT_MAP_VIEW_KEY]: HEAT_MAP_VIEW_ENTRY[1],
    help: window.ui_strings_.text_of("str_menu_help"),
    overview: window.ui_strings_.text_of("str_menu_overview"),
    reset: window.ui_strings_.text_of("str_menu_reset"),
    scale: window.ui_strings_.text_of("str_menu_scale"),
    test: window.ui_strings_.text_of("str_menu_test"),
  };
  const SCALE_BAR_TEXTS = {
    empty: window.ui_strings_.text_of("str_menu_scale_bar_empty"),
    filled: window.ui_strings_.text_of("str_menu_scale_bar_filled"),
  };
  const SCALE_KEY_STEPS = {
    [MENU_SCALE_KEY_NAMES.larger]: 1,
    [MENU_SCALE_KEY_NAMES.smaller]: -1,
  };
  const VIEW_LABEL_TEXTS = {
    [CALLERS_VIEW_KEY]: CALLERS_LABEL_TEXT,
    [FLAME_GRAPH_VIEW_KEY]: FLAME_GRAPH_VIEW_ENTRY[1],
    [HEAT_MAP_VIEW_KEY]: HEAT_MAP_VIEW_ENTRY[1],
  };

  const dark_mode_button = document.getElementById(
    `menu-${DARK_MODE_BUTTON_NAME}-button-`,
  );
  const files_pulldown_root = document.getElementById("menu-file-pulldown-");
  const flame_graph_button = document.getElementById(
    `menu-${FLAME_GRAPH_VIEW_KEY}-button-`,
  );
  const functions_pulldown_root = document.getElementById(
    "menu-function-pulldown-",
  );
  const home_title_text = document.title;
  const logo_link = document.getElementById("menu-logo-");
  const menu_strip = document.getElementById("menu-");
  const overview_button = document.getElementById("menu-overview-button-");
  const reset_button = document.getElementById("menu-reset-button-");
  const scale_bar_cells = Array.from(
    { length: window.report_ui_.design_scale_last_stop },
    () => document.createElement("span"),
  );
  const scale_bar_lead = document.createTextNode("");
  const scale_bar_start = document.createElement("span");
  const scale_bar_trail = document.createTextNode("");
  const scale_button = document.getElementById("menu-scale-button-");
  const scale_stop_targets = [scale_bar_start, ...scale_bar_cells];
  const tests_pulldown_root = document.getElementById("menu-test-pulldown-");
  const tests_pulldown_entries = [
    ...tests_pulldown_root.querySelectorAll(
      ".menu-pulldown-entry-list- a[data-test-name-]",
    ),
  ];
  const title_cell = document.getElementById("menu-title-");
  const view_buttons = {
    [CALLERS_VIEW_KEY]: document.getElementById(
      `menu-${CALLERS_VIEW_KEY}-button-`,
    ),
    [FLAME_GRAPH_VIEW_KEY]: flame_graph_button,
    [HEAT_MAP_VIEW_KEY]: document.getElementById(
      `menu-${HEAT_MAP_VIEW_KEY}-button-`,
    ),
  };

  if (typeof window.report_manifest_table_ === "undefined")
    throw new Error(window.ui_strings_.text_of("str_error_report_incomplete"));
  let menu_pulldowns = [];
  let tests_pulldown = null;

  function pulldown_pattern_of(search_text) {
    try {
      return new RegExp(search_text, "i");
    } catch (pattern_error) {
      if (!(pattern_error instanceof SyntaxError)) throw pattern_error;
      return null;
    }
  }
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
    function search_parts_of(search_text) {
      const line_pattern = new RegExp(MENU_PULLDOWN_LINE_NUMBER_PATTERN);
      const line_match = reads_line_number && line_pattern.exec(search_text);
      return line_match ? [line_match[1], +line_match[2]] : [search_text, 0];
    }
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
    function search_box_focus() {
      search_box.focus();
      if (document.activeElement !== search_box)
        throw new Error(
          window.ui_strings_.text_fill("str_error_pulldown_focus_refused", [
            document.activeElement.tagName.toLowerCase(),
          ]),
        );
    }
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
    function key_take(key_name, is_in_search_box) {
      const is_command_key =
        window.report_ui_.pulldown_key.is_command(key_name);
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
      if (is_in_search_box) return false;
      search_box.value += key_name;
      entries_filter();
      search_box_focus();
      return true;
    }

    menu_button.textContent = label_text;
    search_box.placeholder = window.ui_strings_.text_of(
      "str_pulldown_placeholder",
    );
    no_match_note.textContent = window.ui_strings_.text_of("str_no_match");
    for (const pointer_target of [menu_button, entry_list]) {
      pointer_target.addEventListener(
        "mousedown",
        window.catch_show_throw_((pointer_event) =>
          pointer_event.preventDefault(),
        ),
      );
    }
    menu_button.addEventListener(
      "click",
      window.catch_show_throw_(() => pulldown_open("")),
    );
    search_box.addEventListener(
      "blur",
      window.catch_show_throw_(() => {
        if (is_open) pulldown_close();
      }),
    );
    search_box.addEventListener(
      "input",
      window.catch_show_throw_(entries_filter),
    );
    search_box.addEventListener(
      "keydown",
      window.catch_show_throw_((key_event) => {
        const key_name = window.report_ui_.pulldown_key.of(key_event);
        if (key_name && key_take(key_name, true)) key_event.preventDefault();
      }),
    );
    entry_list.addEventListener(
      "click",
      window.catch_show_throw_((click_event) => {
        if (!click_event.target.closest("a")) return;
        pulldown_close();
        search_box.blur();
      }),
    );
    closed_show();
    return { is_open: () => is_open, key_take };
  }

  function active_test_name() {
    return (
      window.report_frame_.address_now().test ?? MENU_PULLDOWN_MERGED_TEST_NAME
    );
  }
  function heat_map_entries_of(names_key, part_of) {
    const pulldown_text = window.report_pulldown_text_;
    if (!pulldown_text)
      throw new Error(
        window.ui_strings_.text_of("str_error_pulldown_text_missing"),
      );
    const entry_test_name = active_test_name();
    return pulldown_text[names_key].map((name) => {
      const entry_link = document.createElement("a");
      entry_link.setAttribute(
        "href",
        window.report_ui_.address.hash_of({
          test: entry_test_name,
          view: HEAT_MAP_VIEW_KEY,
          ...part_of(name),
        }),
      );
      entry_link.tabIndex = -1;
      entry_link.textContent = name;
      return entry_link;
    });
  }
  function button_activate(button_name) {
    const button_element = document.getElementById(
      `menu-${button_name}-button-`,
    );
    if (!button_element || button_element.hidden) return false;
    if (button_element === scale_button) scale_button.focus();
    else button_element.click();
    return true;
  }
  function menu_key_take(key_name) {
    const open_pulldown = menu_pulldowns.find((candidate_pulldown) =>
      candidate_pulldown.is_open(),
    );
    if (open_pulldown) return open_pulldown.key_take(key_name, false);
    const button_name = menu_key_button_name(key_name);
    if (button_name) return button_activate(button_name);
    return (
      window.report_ui_.view_key.opens_tests_pulldown(key_name) &&
      tests_pulldown.key_take(key_name, false)
    );
  }
  function button_number_of(button_name) {
    return (NUMBERED_BUTTON_NAMES.indexOf(button_name) + 1) % DIGIT_KEY_COUNT;
  }
  function menu_key_button_name(key_name) {
    return (
      NUMBERED_BUTTON_NAMES.find(
        (button_name) => String(button_number_of(button_name)) === key_name,
      ) ?? ""
    );
  }
  function button_text_of(button_name) {
    if (!Object.prototype.hasOwnProperty.call(BUTTON_LABEL_TEXTS, button_name))
      throw new Error(
        window.ui_strings_.text_fill("str_error_menu_button_unlabelled", [
          button_name,
        ]),
      );
    return window.ui_strings_.text_fill("str_menu_button", {
      number: button_number_of(button_name),
      label: BUTTON_LABEL_TEXTS[button_name],
    });
  }
  function buttons_label() {
    if (NUMBERED_BUTTON_NAMES.length > DIGIT_KEY_COUNT)
      throw new Error(
        window.ui_strings_.text_fill("str_error_menu_button_order_long", [
          NUMBERED_BUTTON_NAMES.length,
          DIGIT_KEY_COUNT,
        ]),
      );
    for (const button_name of NUMBERED_BUTTON_NAMES) {
      const button_text = button_text_of(button_name);
      const button_element = document.getElementById(
        `menu-${button_name}-button-`,
      );
      if (button_element) button_element.textContent = button_text;
    }
  }
  function dark_mode_show_() {
    dark_mode_button.textContent = window.ui_strings_.text_of(
      window.report_ui_.dark_mode_enabled_now_()
        ? "str_menu_dark_mode_enabled"
        : "str_menu_light_mode",
    );
  }
  function pulldowns_activate() {
    tests_pulldown = pulldown_attach(
      tests_pulldown_root,
      button_text_of("test"),
      () => tests_pulldown_entries,
      () => window.report_frame_.view_post("report_ui:tests_pulldown_closed"),
      false,
    );
    menu_pulldowns = [
      tests_pulldown,
      pulldown_attach(
        files_pulldown_root,
        button_text_of("file"),
        (line_number) =>
          heat_map_entries_of("files", (file_name) => ({
            file: file_name,
            line: line_number || null,
          })),
        () => {},
        true,
      ),
      pulldown_attach(
        functions_pulldown_root,
        button_text_of("function"),
        () =>
          heat_map_entries_of("functions", (function_name) => ({
            function: function_name,
          })),
        () => {},
        false,
      ),
    ];
  }

  function title_link_of(part_text, part_hash) {
    const part_link = document.createElement("a");
    part_link.setAttribute("href", part_hash);
    part_link.textContent = part_text;
    return part_link;
  }
  function recenter_link_of(part_text) {
    const recenter_link = title_link_of(
      part_text,
      window.report_ui_.address.hash_of(window.report_frame_.address_now()),
    );
    recenter_link.addEventListener(
      "click",
      window.catch_show_throw_((click_event) => {
        click_event.preventDefault();
        window.report_frame_.view_post("report_ui:recenter");
      }),
    );
    return recenter_link;
  }
  function heat_map_part_text(address) {
    if (address.function !== null) return address.function;
    if (address.file === null) return "";
    const base_name = address.file.split("/").pop();
    return address.line !== null ? base_name + ":" + address.line : base_name;
  }
  function title_links_of(address) {
    const part_links = [
      title_link_of(
        address.test,
        window.report_ui_.address.home_hash_of(address.test, CALLERS_VIEW_KEY),
      ),
      title_link_of(
        VIEW_LABEL_TEXTS[address.view],
        window.report_ui_.address.home_hash_of(address.test, address.view),
      ),
    ];
    const heat_map_text =
      address.view === HEAT_MAP_VIEW_KEY ? heat_map_part_text(address) : "";
    if (heat_map_text) part_links.push(recenter_link_of(heat_map_text));
    return part_links;
  }
  function buttons_follow(address) {
    const button_test_name = address.test ?? MENU_PULLDOWN_MERGED_TEST_NAME;
    overview_button.classList.toggle("current_", address.view === null);
    for (const [view_key, view_button] of Object.entries(view_buttons)) {
      if (!view_button) continue;
      view_button.classList.toggle("current_", address.view === view_key);
      view_button.setAttribute(
        "href",
        window.report_ui_.address.home_hash_of(button_test_name, view_key),
      );
    }
    if (flame_graph_button)
      flame_graph_button.hidden =
        button_test_name === MENU_PULLDOWN_MERGED_TEST_NAME;
    for (const entry_link of tests_pulldown_entries) {
      entry_link.classList.toggle(
        "current_",
        entry_link.getAttribute("data-test-name-") === address.test,
      );
    }
  }
  function address_show() {
    const address = window.report_frame_.address_now();
    const part_links = address.test !== null ? title_links_of(address) : [];
    const part_texts = part_links.map((part_link) => part_link.textContent);
    const title_nodes = [];
    for (const part_link of part_links) {
      if (title_nodes.length) title_nodes.push(TITLE_PART_SEPARATOR);
      title_nodes.push(part_link);
    }
    title_cell.replaceChildren(...title_nodes);
    document.title = part_texts.join(TITLE_PART_SEPARATOR) || home_title_text;
    buttons_follow(address);
  }
  function scale_bar_show(travel_stop) {
    scale_bar_cells.forEach((cell_span, cell_index) => {
      cell_span.textContent =
        cell_index < travel_stop
          ? SCALE_BAR_TEXTS.filled
          : SCALE_BAR_TEXTS.empty;
    });
    scale_bar_trail.textContent = window.ui_strings_.text_fill(
      "str_menu_scale_bar_end",
      { multiple: window.report_ui_.design_scale_multiple_text(travel_stop) },
    );
  }
  function scale_stop_request(travel_stop) {
    if (travel_stop === window.report_ui_.design_scale_travel_now()) return;
    window.report_ui_.design_scale_travel_set(travel_stop);
    window.report_frame_.view_post("report_ui:layout_reset");
    scale_bar_show(travel_stop);
  }
  function scale_activate() {
    scale_bar_lead.textContent = window.ui_strings_.text_fill(
      "str_menu_scale_bar_lead",
      { button: button_text_of("scale") },
    );
    scale_bar_start.textContent = window.ui_strings_.text_of(
      "str_menu_scale_bar_start",
    );
    scale_button.replaceChildren(
      scale_bar_lead,
      ...scale_stop_targets,
      scale_bar_trail,
    );
    scale_bar_show(window.report_ui_.design_scale_travel_now());
    scale_button.addEventListener(
      "click",
      window.catch_show_throw_((click_event) => {
        scale_button.focus();
        const clicked_stop = scale_stop_targets.indexOf(click_event.target);
        if (clicked_stop >= 0) scale_stop_request(clicked_stop);
      }),
    );
    scale_button.addEventListener(
      "keydown",
      window.catch_show_throw_((key_event) => {
        const stop_step = SCALE_KEY_STEPS[key_event.key];
        if (
          !stop_step ||
          key_event.altKey ||
          key_event.ctrlKey ||
          key_event.metaKey
        )
          return;
        key_event.preventDefault();
        const wanted_stop =
          window.report_ui_.design_scale_travel_now() + stop_step;
        if (scale_stop_targets[wanted_stop]) scale_stop_request(wanted_stop);
      }),
    );
  }

  function logo_color_at(fraction) {
    return `rgb(${window.report_ui_.ramp_channels_at(fraction).join(",")})`;
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
  function activate() {
    logo_link.replaceChildren(
      ...logo_letters_build(
        REPORT_NAME_TEXT,
        MENU_LOGO_LETTER_CLASS,
        STYLE_MENU_LOGO_START_FRACTION,
      ),
    );
    menu_strip.addEventListener(
      "keydown",
      window.catch_show_throw_(window.report_ui_.widget_key.link_click_take),
    );
    reset_button.addEventListener(
      "click",
      window.catch_show_throw_(() => {
        window.report_ui_.view_storage.preferences_clear();
        const default_stop = window.report_ui_.design_scale_default_stop_();
        window.report_ui_.design_scale_travel_set(default_stop);
        scale_bar_show(default_stop);
        window.report_ui_.dark_mode_set_(DARK_MODE_ENABLED_DEFAULT);
        dark_mode_show_();
        window.report_frame_.view_post("report_ui:layout_reset");
      }),
    );
    dark_mode_button.addEventListener(
      "click",
      window.catch_show_throw_(() => {
        window.report_ui_.dark_mode_set_(
          !window.report_ui_.dark_mode_enabled_now_(),
        );
        window.report_frame_.view_post("report_ui:dark_mode_apply");
        dark_mode_show_();
      }),
    );
    buttons_label();
    dark_mode_show_();
    pulldowns_activate();
    scale_activate();
    document.addEventListener(
      "keydown",
      window.catch_show_throw_((key_event) => {
        const key_name = window.report_ui_.view_key.of(key_event);
        if (key_name && menu_key_take(key_name)) key_event.preventDefault();
      }),
    );
    document.addEventListener(
      "click",
      window.catch_show_throw_((click_event) => {
        const link_hash = window.report_ui_.address.link_hash_of(click_event);
        if (!link_hash) return;
        click_event.preventDefault();
        window.report_frame_.address_request(link_hash);
      }),
    );
  }

  window.report_menu_ = {
    address_show,
    dark_mode_show_,
    menu_key_take,
  };

  activate();
  window.report_frame_.activate();
})();
5;
