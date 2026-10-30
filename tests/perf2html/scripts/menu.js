// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const CALL_GRAPH_VIEW_KEY = settings_("CALL_GRAPH_VIEW_KEY");
  const DATABASE_VIEW_KEY = settings_("DATABASE_VIEW_KEY");
  const FLAME_GRAPH_VIEW_ENTRY = settings_("FLAME_GRAPH_VIEW_ENTRY");
  const HEAT_MAP_VIEW_ENTRY = settings_("HEAT_MAP_VIEW_ENTRY");
  const MENU_ENTRY_NEEDS = settings_("MENU_ENTRY_NEEDS");
  const MENU_SCALE_KEY_STEPS = settings_("MENU_SCALE_KEY_STEPS");
  const SETTINGS_VIEW_ENTRY = settings_("SETTINGS_VIEW_ENTRY");
  const STYLE_MENU_LOGO_START_SHARE = settings_("STYLE_MENU_LOGO_START_SHARE");

  const FLAME_GRAPH_VIEW_KEY = FLAME_GRAPH_VIEW_ENTRY[0];
  const HEAT_MAP_VIEW_KEY = HEAT_MAP_VIEW_ENTRY[0];
  const REPORT_NAME_TEXT = window.ui_strings_.text("str_report_name");
  const SCALE_CELL_TEXTS = {
    after_stop: window.ui_strings_.text("str_menu_scale_cell_after_stop"),
    before_stop: window.ui_strings_.text("str_menu_scale_cell_before_stop"),
  };
  const SCALE_LAST_STOP = window.report_ui_.design_scale_last_stop;
  const SETTINGS_VIEW_KEY = SETTINGS_VIEW_ENTRY[0];
  const TITLE_PART_SEPARATOR = window.ui_strings_.text(
    "str_title_part_separator",
  );
  const VIEW_STRING_IDS = {
    [CALL_GRAPH_VIEW_KEY]: "str_view_call_graph",
    [DATABASE_VIEW_KEY]: "str_view_database",
    [FLAME_GRAPH_VIEW_KEY]: "str_view_flame_graph",
    [HEAT_MAP_VIEW_KEY]: "str_view_heat_map",
    [SETTINGS_VIEW_KEY]: "str_view_settings",
  };

  const menu_strip = document.getElementById("menu-");
  const help_href = menu_strip.getAttribute("data-help-href-");
  const preference_strip = document.getElementById("menu-preference-");

  if (typeof window.report_manifest_table_ === "undefined")
    window.throw_exception_("str_error_report_incomplete");
  if (!window.report_source_database_)
    window.throw_exception_("str_error_internal");
  const heat_scale_choices = window.report_preferences_.heat_scale_choices();
  const heat_sort_choices = window.report_preferences_.heat_sort_choices;
  let flash_entry_name = "";
  let menu_strip_handle = null;
  let preference_strip_handle = null;

  // Returns the test the address shows, null for none.
  function active_test_name() {
    return window.report_frame_.address_now().test;
  }
  function flash_request(entry_name) {
    return () => {
      flash_entry_name = entry_name;
    };
  }
  function pulldown_link(link_text, link_hash, entry_name) {
    const entry_link = window.render_element_of_(
      window.render_element_(
        "a",
        { href: link_hash },
        window.render_html_escape_(link_text),
      ),
    );
    entry_link.addEventListener(
      "click",
      window.try_catch_handler_((click_event) => {
        if (window.report_ui_.address.link_hash(click_event))
          flash_entry_name = entry_name;
      }),
    );
    return entry_link;
  }
  function heat_map_entries(names, entry_name, part) {
    const entry_test_name = active_test_name();
    return names.map((name) =>
      pulldown_link(
        name,
        window.report_ui_.address.hash({
          test: entry_test_name,
          view: HEAT_MAP_VIEW_KEY,
          ...part(name),
        }),
        entry_name,
      ),
    );
  }
  function files_entries(line_number) {
    return heat_map_entries(
      window.report_source_database_.filesWithSource,
      "str_menu_file",
      (file_name) => ({ file: file_name, line: line_number || null }),
    );
  }
  function functions_entries() {
    return heat_map_entries(
      window.report_source_database_.functions,
      "str_menu_function",
      (function_name) => ({ function: function_name }),
    );
  }
  // Returns the address with another test, the database from the overview.
  function test_entry_hash(test_name) {
    const address = window.report_frame_.address_now();
    return address.view === null
      ? window.report_ui_.address.home_hash(test_name, DATABASE_VIEW_KEY)
      : window.report_ui_.address.hash({ ...address, test: test_name });
  }
  // Lists each test, linked to the address with that test.
  function tests_entries() {
    return window.report_frame_.test_names.map((test_name) =>
      pulldown_link(test_name, test_entry_hash(test_name), "str_menu_test"),
    );
  }
  function tests_pulldown_closed() {
    window.report_frame_.view_post("tests_pulldown_closed");
  }
  function pulldown_options(entries, on_close, reads_line_number) {
    return {
      entries,
      keeps_open: false,
      on_close,
      on_move: null,
      on_select: null,
      reads_line_number,
    };
  }

  function logo_color_at(fraction) {
    return `rgb(${window.report_ui_.ramp_channels_at(fraction).join(",")})`;
  }
  function logo_letters_markup(text, start_share) {
    const letters = [...text];
    return letters
      .map((letter, index) =>
        window.render_element_(
          "span",
          {
            style: `color:${logo_color_at(
              letters.length > 1
                ? start_share +
                    ((1 - start_share) * index) / (letters.length - 1)
                : 1,
            )}`,
          },
          window.render_html_escape_(letter),
        ),
      )
      .join("");
  }
  function dark_mode_string_id() {
    return window.report_ui_.dark_mode_enabled_now_()
      ? "str_menu_dark_mode_enabled"
      : "str_menu_light_mode";
  }
  function dark_mode_toggle() {
    window.report_ui_.dark_mode_set_(
      !window.report_ui_.dark_mode_enabled_now_(),
    );
    window.report_frame_.view_post("dark_mode_show");
    menu_render();
  }
  // Resets every browser preference to its default, as the reset entry does.
  function user_preferences_reset() {
    window.report_ui_.view_storage.preferences_clear();
    window.report_ui_.design_scale_stop_set(null);
    window.report_ui_.dark_mode_set_(null);
    window.report_preferences_.seed();
    window.report_frame_.load_log_history();
    window.report_frame_.view_post("layout_reset");
    menu_render();
  }
  // Resets the preferences, then asks the view to reset its own state.
  function preferences_reset() {
    user_preferences_reset();
    window.report_frame_.view_post("view_reset");
    window.report_frame_.settings_debug_clear();
  }
  // Resets the preferences on the toggle query, then shows the mode it opens.
  function dark_mode_toggle_query_apply() {
    const toggle_value = window.report_dark_mode_.toggle_query_value();
    if (toggle_value === null) return;
    user_preferences_reset();
    if (toggle_value) dark_mode_toggle();
  }

  function choice_label(choices, choice_value) {
    return choices.find((choice) => choice.value === choice_value).label;
  }
  // Shows or hides one line of a counters list, unless the list keeps it.
  function counter_line_toggle(list_key, line_name) {
    if (!window.report_preferences_.counter_line_toggle(list_key, line_name))
      return;
    window.report_frame_.view_post("preferences_apply");
  }
  // Moves one line of a counters list next to its anchor, columns following.
  function counter_line_move(list_key, line_name, anchor_name, lands_after) {
    window.report_preferences_.counter_line_move(
      list_key,
      line_name,
      anchor_name,
      lands_after,
    );
    window.report_frame_.view_post("preferences_apply");
  }
  function heat_scale_choose(scale_value) {
    window.report_preferences_.heat_scale_choose(scale_value);
    window.report_frame_.view_post("preferences_apply");
    preference_strip_handle.pulldown_label_set(
      "heat_scale",
      choice_label(heat_scale_choices, scale_value),
    );
  }
  function heat_sort_choose(sort_mode) {
    window.report_preferences_.heat_sort_choose(sort_mode);
    window.report_frame_.view_post("preferences_apply");
    preference_strip_handle.pulldown_label_set(
      "heat_sort",
      choice_label(heat_sort_choices, sort_mode),
    );
  }

  function scale_text(scale_stop) {
    return (
      SCALE_CELL_TEXTS.before_stop.repeat(scale_stop) +
      SCALE_CELL_TEXTS.after_stop.repeat(SCALE_LAST_STOP - scale_stop)
    );
  }
  function scale_stop_request(scale_stop) {
    if (
      scale_stop < 0 ||
      scale_stop > SCALE_LAST_STOP ||
      scale_stop === window.report_ui_.design_scale_stop_now()
    )
      return;
    window.report_ui_.design_scale_stop_set(scale_stop);
    window.report_frame_.view_post("layout_reset");
    menu_strip_handle.widget_text_set(
      "str_menu_scale",
      scale_text(scale_stop),
    );
  }
  function scale_click_handler(click_event) {
    const cell_span = click_event.target.closest(
      ".menu-button-widget- > span",
    );
    if (!cell_span) return;
    const cell_index = Array.prototype.indexOf.call(
      cell_span.parentElement.children,
      cell_span,
    );
    const scale_stop = window.report_ui_.design_scale_stop_now();
    scale_stop_request(cell_index < scale_stop ? cell_index : cell_index + 1);
  }
  function scale_key_handler(key_name) {
    if (!Object.prototype.hasOwnProperty.call(MENU_SCALE_KEY_STEPS, key_name))
      return false;
    scale_stop_request(
      window.report_ui_.design_scale_stop_now() +
        MENU_SCALE_KEY_STEPS[key_name],
    );
    return true;
  }

  // Returns whether an entry shows, each need its settings row names met.
  function entry_available(entry_name, address, view_key) {
    if (!Object.hasOwn(MENU_ENTRY_NEEDS, entry_name)) return true;
    return MENU_ENTRY_NEEDS[entry_name].every((need_name) => {
      if (need_name === "counter_list")
        return Object.hasOwn(
          window.report_preferences_.now().counter_lists,
          address.view,
        );
      if (need_name === "test") return address.test !== null;
      if (need_name === "view") return address.view !== null;
      if (need_name === "view_page" && view_key !== null)
        return window.report_frame_.view_has_page(view_key);
      window.throw_exception_("str_error_internal");
    });
  }
  // Makes an entry named by its label's ui string, shown as its needs allow.
  function entry(string_id, kind_name, address, view_key, entry_fields) {
    return window.report_ui_.strip.entry_make(
      string_id,
      kind_name,
      window.ui_strings_.text(string_id),
      {
        is_available: entry_available(string_id, address, view_key),
        is_numbered: true,
        ...entry_fields,
      },
    );
  }
  function view_entry(string_id, view_hash, address, view_key) {
    return entry(string_id, "link", address, view_key, {
      href: view_hash,
      on_activate: flash_request(string_id),
    });
  }
  // Assembles every menu entry in strip order, the one place the menu changes.
  function menu_entries(address) {
    const view_hash = (view_key) =>
      window.report_ui_.address.home_hash(address.test, view_key);
    return [
      entry("str_report_name", "link", address, null, {
        is_numbered: false,
        href: view_hash(SETTINGS_VIEW_KEY),
        label_markup: logo_letters_markup(
          REPORT_NAME_TEXT,
          STYLE_MENU_LOGO_START_SHARE,
        ),
        withholds_tab_stop: true,
      }),
      view_entry(
        "str_view_overview",
        window.report_ui_.address.hash({}),
        address,
        null,
      ),
      entry("str_menu_test", "pulldown", address, null, {
        pulldown_options: pulldown_options(
          tests_entries,
          tests_pulldown_closed,
          false,
        ),
      }),
      entry("str_menu_file", "pulldown", address, null, {
        pulldown_options: pulldown_options(files_entries, () => {}, true),
      }),
      entry("str_menu_function", "pulldown", address, null, {
        pulldown_options: pulldown_options(functions_entries, () => {}, false),
      }),
      view_entry(
        VIEW_STRING_IDS[DATABASE_VIEW_KEY],
        view_hash(DATABASE_VIEW_KEY),
        address,
        DATABASE_VIEW_KEY,
      ),
      view_entry(
        VIEW_STRING_IDS[FLAME_GRAPH_VIEW_KEY],
        view_hash(FLAME_GRAPH_VIEW_KEY),
        address,
        FLAME_GRAPH_VIEW_KEY,
      ),
      view_entry(
        VIEW_STRING_IDS[CALL_GRAPH_VIEW_KEY],
        view_hash(CALL_GRAPH_VIEW_KEY),
        address,
        CALL_GRAPH_VIEW_KEY,
      ),
      entry("str_menu_reset", "action", address, null, {
        on_activate: preferences_reset,
      }),
      entry("str_menu_help", "link", address, null, {
        href: help_href,
        opens_new_tab: true,
      }),
      entry("str_menu_scale", "action", address, null, {
        is_numbered: false,
        is_widget: true,
        widget_text: scale_text(window.report_ui_.design_scale_stop_now()),
        on_activate: scale_click_handler,
      }),
    ];
  }
  // Builds a preference pulldown entry, its cell labelled with the choice.
  function preference_pulldown_entry(
    entry_name,
    address,
    label_text,
    choices,
    on_select,
    keeps_open,
    on_move,
  ) {
    return window.report_ui_.strip.entry_make(
      entry_name,
      "pulldown",
      label_text,
      {
        is_available: entry_available(entry_name, address, null),
        pulldown_options: {
          entries: () => window.report_ui_.strip.choice_entries(choices()),
          keeps_open,
          on_close: () => {},
          on_move,
          on_select,
          reads_line_number: false,
        },
      },
    );
  }
  // Builds the counters pulldown entry, editing the list of the page shown.
  function counters_entry(address) {
    const list_key = address.view;
    return preference_pulldown_entry(
      "counters",
      address,
      window.ui_strings_.text("str_menu_counters"),
      () => window.report_preferences_.counter_choices(list_key),
      (line_name) => counter_line_toggle(list_key, line_name),
      true,
      (line_name, anchor_name, lands_after) =>
        counter_line_move(list_key, line_name, anchor_name, lands_after),
    );
  }
  // Assembles the preference row, the counters entry built only where shown.
  function preference_entries(address) {
    const shown_preferences = window.report_preferences_.now();
    return [
      ...(entry_available("counters", address, null)
        ? [counters_entry(address)]
        : []),
      preference_pulldown_entry(
        "heat_scale",
        address,
        choice_label(heat_scale_choices, shown_preferences.heat_scale_value),
        () => heat_scale_choices,
        heat_scale_choose,
        false,
        null,
      ),
      preference_pulldown_entry(
        "heat_sort",
        address,
        choice_label(heat_sort_choices, shown_preferences.heat_sort_mode),
        () => heat_sort_choices,
        heat_sort_choose,
        false,
        null,
      ),
      entry(dark_mode_string_id(), "action", address, null, {
        is_numbered: false,
        on_activate: dark_mode_toggle,
      }),
    ];
  }

  function heat_map_part_text(address) {
    if (address.function !== null) return address.function;
    if (address.file === null) return "";
    const base_name = address.file.split("/").pop();
    return window.report_ui_.location_text(base_name, address.line);
  }
  // Lists the heat map's status label: a function, else a file and its line.
  function heat_map_status_entries(address) {
    const part_text = heat_map_part_text(address);
    return part_text ? [part_text] : [];
  }
  // Lists the focused path labels while the call graph shows, root first.
  function focused_path_status_entries(address) {
    if (address.view !== CALL_GRAPH_VIEW_KEY) return [];
    return window.report_frame_.focused_path_now();
  }
  // Lists the status labels: any test, view, heat map parts, focused path.
  function status_entries(address) {
    const view_label = window.ui_strings_.text(
      address.view === null
        ? "str_view_overview"
        : VIEW_STRING_IDS[address.view],
    );
    if (address.test === null) return [view_label];
    return [
      address.test,
      view_label,
      ...heat_map_status_entries(address),
      ...focused_path_status_entries(address),
    ];
  }
  function title_text(address) {
    if (address.view === null)
      return window.ui_strings_.text("str_view_overview");
    return [
      address.test,
      window.ui_strings_.text(VIEW_STRING_IDS[address.view]),
      heat_map_part_text(address),
    ]
      .filter((part_text) => part_text)
      .join(TITLE_PART_SEPARATOR);
  }
  function menu_render() {
    const address = window.report_frame_.address_now();
    const button_entries = menu_entries(address);
    menu_strip_handle = window.report_ui_.strip.render(
      menu_strip,
      button_entries,
      status_entries(address),
    );
    preference_strip_handle = window.report_ui_.strip.render(
      preference_strip,
      preference_entries(address),
      [],
    );
    document.title = title_text(address);
    const menu_entry_number = window.report_frame_.menu_entry_number_now();
    if (menu_entry_number !== null)
      menu_strip_handle.numbered_entry_focus(menu_entry_number);
  }
  function address_show() {
    menu_render();
    if (!flash_entry_name) return;
    menu_strip_handle.flash(flash_entry_name);
    flash_entry_name = "";
  }
  function menu_key_handler(key_name, is_repeat) {
    if (
      preference_strip_handle.key_handler(key_name, is_repeat) ||
      menu_strip_handle.key_handler(key_name, is_repeat) ||
      scale_key_handler(key_name)
    )
      return true;
    if (!window.report_ui_.view_key.opens_tests_pulldown(key_name))
      return false;
    menu_strip_handle.pulldown_open("str_menu_test", key_name);
    return true;
  }

  function activate() {
    window.report_preferences_.activate(window.report_frame_.counter_names);
    document.addEventListener(
      "keydown",
      window.try_catch_handler_((key_event) => {
        window.report_ui_.widget_key.link_click_handler(key_event);
        const key_name = window.report_ui_.view_key.of(key_event);
        if (key_name && menu_key_handler(key_name, key_event.repeat))
          key_event.preventDefault();
      }),
    );
    document.addEventListener(
      "click",
      window.try_catch_handler_((click_event) => {
        const link_hash = window.report_ui_.address.link_hash(click_event);
        if (!link_hash) return;
        click_event.preventDefault();
        window.report_frame_.address_request(link_hash);
      }),
    );
    window.report_ui_.resize_settle_register(menu_render);
  }

  window.report_menu_ = {
    address_show,
    counter_line_move,
    heat_sort_choose,
    menu_key_handler,
    menu_render,
  };

  activate();
  window.report_frame_.activate();
  dark_mode_toggle_query_apply();
})();
