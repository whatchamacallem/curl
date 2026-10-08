// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const CALLERS_VIEW_KEY = settings_("CALLERS_VIEW_KEY");
  const FLAME_GRAPH_VIEW_ENTRY = settings_("FLAME_GRAPH_VIEW_ENTRY");
  const HEAT_MAP_VIEW_ENTRY = settings_("HEAT_MAP_VIEW_ENTRY");
  const MENU_SCALE_KEY_STEPS = settings_("MENU_SCALE_KEY_STEPS");
  const REPORT_TEST_SUITE_NAME = settings_("REPORT_TEST_SUITE_NAME");
  const SETTINGS_VIEW_ENTRY = settings_("SETTINGS_VIEW_ENTRY");
  const STYLE_MENU_LOGO_START_SHARE = settings_("STYLE_MENU_LOGO_START_SHARE");
  const STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS = settings_(
    "STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS",
  );

  const ENTRY_LABEL_TEXTS = {
    file: window.ui_strings_.text_of("str_menu_file"),
    function: window.ui_strings_.text_of("str_menu_function"),
    help: window.ui_strings_.text_of("str_menu_help"),
    overview: window.ui_strings_.text_of("str_view_overview"),
    reset: window.ui_strings_.text_of("str_menu_reset"),
    scale: window.ui_strings_.text_of("str_menu_scale"),
    test: window.ui_strings_.text_of("str_menu_test"),
  };
  const FLAME_GRAPH_VIEW_KEY = FLAME_GRAPH_VIEW_ENTRY[0];
  const HEAT_MAP_VIEW_KEY = HEAT_MAP_VIEW_ENTRY[0];
  const OVERVIEW_ENTRY_NAME = "overview";
  const REPORT_NAME_TEXT = window.ui_strings_.text_of("str_report_name");
  const SCALE_CELL_TEXTS = {
    after_stop: window.ui_strings_.text_of("str_menu_scale_cell_after_stop"),
    before_stop: window.ui_strings_.text_of("str_menu_scale_cell_before_stop"),
  };
  const SCALE_ENTRY_NAME = "scale";
  const SCALE_LAST_STOP = window.report_ui_.design_scale_last_stop;
  const SETTINGS_VIEW_KEY = SETTINGS_VIEW_ENTRY[0];
  const TEST_ENTRY_NAME = "test";
  const TEST_SUITE_NAME_TEXT = window.ui_strings_.text_of(
    "str_menu_test_suite_name",
  );
  const TITLE_PART_SEPARATOR = window.ui_strings_.text_of(
    "str_title_part_separator",
  );
  const VIEW_LABEL_TEXTS = {
    [CALLERS_VIEW_KEY]: window.ui_strings_.text_of("str_view_callers"),
    [FLAME_GRAPH_VIEW_KEY]: window.ui_strings_.text_of("str_view_flame_graph"),
    [HEAT_MAP_VIEW_KEY]: window.ui_strings_.text_of("str_view_heat_map"),
    [SETTINGS_VIEW_KEY]: window.ui_strings_.text_of("str_view_settings"),
  };

  const home_title_text = document.title;
  const menu_strip = document.getElementById("menu-");
  const help_href = menu_strip.getAttribute("data-help-href-");
  const pulldown_box_width_chars =
    Math.max(
      ...window.report_frame_.test_names.map(
        (test_name) => test_name_text_of(test_name).length,
      ),
    ) + STYLE_MENU_PULLDOWN_EXTRA_WIDTH_CHARS;

  if (typeof window.report_manifest_table_ === "undefined")
    throw new Error(window.ui_strings_.text_of("str_error_report_incomplete"));
  let flash_entry_name = "";
  let menu_strip_handle = null;

  function active_test_name() {
    return window.report_frame_.address_now().test ?? REPORT_TEST_SUITE_NAME;
  }
  function test_name_text_of(test_name) {
    return test_name === REPORT_TEST_SUITE_NAME
      ? TEST_SUITE_NAME_TEXT
      : test_name;
  }
  function flash_request_of(entry_name) {
    return () => {
      flash_entry_name = entry_name;
    };
  }
  function pulldown_link_of(link_text, link_hash, entry_name) {
    const entry_link = window.shared_element_of_(
      window.shared_element_render_(
        "a",
        { href: link_hash },
        window.shared_html_escape_(link_text),
      ),
    );
    entry_link.addEventListener(
      "click",
      window.try_catch_handler_((click_event) => {
        if (window.report_ui_.address.link_hash_of(click_event))
          flash_entry_name = entry_name;
      }),
    );
    return entry_link;
  }
  function heat_map_entries_of(names_key, entry_name, part_of) {
    const pulldown_text = window.report_pulldown_text_;
    if (!pulldown_text)
      throw new Error(
        window.ui_strings_.text_of("str_error_pulldown_text_missing"),
      );
    const entry_test_name = active_test_name();
    return pulldown_text[names_key].map((name) =>
      pulldown_link_of(
        name,
        window.report_ui_.address.hash_of({
          test: entry_test_name,
          view: HEAT_MAP_VIEW_KEY,
          ...part_of(name),
        }),
        entry_name,
      ),
    );
  }
  function files_entries_of(line_number) {
    return heat_map_entries_of("files", "file", (file_name) => ({
      file: file_name,
      line: line_number || null,
    }));
  }
  function functions_entries_of() {
    return heat_map_entries_of("functions", "function", (function_name) => ({
      function: function_name,
    }));
  }
  function tests_entries_of() {
    return window.report_frame_.test_names.map((test_name) =>
      pulldown_link_of(
        test_name_text_of(test_name),
        window.report_ui_.address.home_hash_of(test_name, HEAT_MAP_VIEW_KEY),
        TEST_ENTRY_NAME,
      ),
    );
  }
  function tests_pulldown_closed() {
    window.report_frame_.view_post("tests_pulldown_closed");
  }
  function pulldown_options_of(entries_of, on_close, reads_line_number) {
    return {
      box_width_chars: pulldown_box_width_chars,
      entries_of,
      on_close,
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
        window.shared_element_render_(
          "span",
          {
            style: `color:${logo_color_at(
              letters.length > 1
                ? start_share +
                    ((1 - start_share) * index) / (letters.length - 1)
                : 1,
            )}`,
          },
          window.shared_html_escape_(letter),
        ),
      )
      .join("");
  }
  function dark_mode_label_text() {
    return window.ui_strings_.text_of(
      window.report_ui_.dark_mode_enabled_now_()
        ? "str_menu_dark_mode_enabled"
        : "str_menu_light_mode",
    );
  }
  function dark_mode_toggle() {
    window.report_ui_.dark_mode_set_(
      !window.report_ui_.dark_mode_enabled_now_(),
    );
    window.report_frame_.view_post("dark_mode_apply");
    menu_render();
  }
  function preferences_reset() {
    window.report_ui_.view_storage.preferences_clear();
    window.report_ui_.design_scale_stop_set(null);
    window.report_ui_.dark_mode_set_(null);
    window.report_frame_.view_post("layout_reset");
    menu_render();
  }

  function scale_text_of(scale_stop) {
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
      SCALE_ENTRY_NAME,
      scale_text_of(scale_stop),
    );
  }
  function scale_click_take(click_event) {
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
  function scale_key_take(key_name) {
    if (!Object.prototype.hasOwnProperty.call(MENU_SCALE_KEY_STEPS, key_name))
      return false;
    scale_stop_request(
      window.report_ui_.design_scale_stop_now() +
        MENU_SCALE_KEY_STEPS[key_name],
    );
    return true;
  }

  function entry_of(entry_name, kind_name, label, entry_fields) {
    return window.report_ui_.strip.entry_make(entry_name, kind_name, label, {
      is_numbered: true,
      ...entry_fields,
    });
  }
  function view_entry_of(entry_name, label_text, view_hash, is_available) {
    return entry_of(entry_name, "link", label_text, {
      is_available,
      href: view_hash,
      on_activate: flash_request_of(entry_name),
    });
  }
  // Assembles every menu entry in strip order, the one place the menu changes.
  function menu_entries_of(address) {
    const test_name = address.test ?? REPORT_TEST_SUITE_NAME;
    const view_hash_of = (view_key) =>
      window.report_ui_.address.home_hash_of(test_name, view_key);
    return [
      entry_of("logo", "link", REPORT_NAME_TEXT, {
        is_numbered: false,
        href: view_hash_of(SETTINGS_VIEW_KEY),
        label_markup: logo_letters_markup(
          REPORT_NAME_TEXT,
          STYLE_MENU_LOGO_START_SHARE,
        ),
      }),
      view_entry_of(
        OVERVIEW_ENTRY_NAME,
        ENTRY_LABEL_TEXTS.overview,
        window.report_ui_.address.hash_of({}),
        true,
      ),
      entry_of(TEST_ENTRY_NAME, "pulldown", ENTRY_LABEL_TEXTS.test, {
        pulldown_options: pulldown_options_of(
          tests_entries_of,
          tests_pulldown_closed,
          false,
        ),
      }),
      entry_of("file", "pulldown", ENTRY_LABEL_TEXTS.file, {
        pulldown_options: pulldown_options_of(
          files_entries_of,
          () => {},
          true,
        ),
      }),
      entry_of("function", "pulldown", ENTRY_LABEL_TEXTS.function, {
        pulldown_options: pulldown_options_of(
          functions_entries_of,
          () => {},
          false,
        ),
      }),
      view_entry_of(
        HEAT_MAP_VIEW_KEY,
        VIEW_LABEL_TEXTS[HEAT_MAP_VIEW_KEY],
        view_hash_of(HEAT_MAP_VIEW_KEY),
        true,
      ),
      view_entry_of(
        CALLERS_VIEW_KEY,
        VIEW_LABEL_TEXTS[CALLERS_VIEW_KEY],
        view_hash_of(CALLERS_VIEW_KEY),
        true,
      ),
      view_entry_of(
        FLAME_GRAPH_VIEW_KEY,
        VIEW_LABEL_TEXTS[FLAME_GRAPH_VIEW_KEY],
        view_hash_of(FLAME_GRAPH_VIEW_KEY),
        window.report_frame_.has_flame_graph &&
          test_name !== REPORT_TEST_SUITE_NAME,
      ),
      entry_of("dark-mode", "action", dark_mode_label_text(), {
        on_activate: dark_mode_toggle,
      }),
      entry_of("reset", "action", ENTRY_LABEL_TEXTS.reset, {
        on_activate: preferences_reset,
      }),
      entry_of("help", "link", ENTRY_LABEL_TEXTS.help, {
        href: help_href,
        opens_new_tab: true,
      }),
      entry_of(SCALE_ENTRY_NAME, "action", ENTRY_LABEL_TEXTS.scale, {
        is_numbered: false,
        is_widget: true,
        widget_text: scale_text_of(window.report_ui_.design_scale_stop_now()),
        on_activate: scale_click_take,
      }),
    ];
  }

  function heat_map_part_text(address) {
    if (address.function !== null) return address.function;
    if (address.file === null) return "";
    const base_name = address.file.split("/").pop();
    return address.line !== null ? base_name + ":" + address.line : base_name;
  }
  function status_entry_of(label_text, status_hash) {
    return { label: label_text, href: status_hash };
  }
  function heat_map_status_entries_of(address) {
    const heat_map_hash_of = (address_parts) =>
      window.report_ui_.address.hash_of({
        test: address.test,
        view: HEAT_MAP_VIEW_KEY,
        ...address_parts,
      });
    if (address.function !== null)
      return [
        status_entry_of(
          address.function,
          heat_map_hash_of({ function: address.function }),
        ),
      ];
    if (address.file === null) return [];
    const file_entry = status_entry_of(
      address.file.split("/").pop(),
      heat_map_hash_of({ file: address.file }),
    );
    if (address.line === null) return [file_entry];
    return [
      file_entry,
      status_entry_of(
        window.ui_strings_.text_fill("str_menu_status_line", {
          line: address.line,
        }),
        heat_map_hash_of({ file: address.file, line: address.line }),
      ),
    ];
  }
  // Lists the status components: the test, the view, the heat map parts.
  function status_entries_of(address) {
    const view_entry =
      address.view === null
        ? status_entry_of(
            ENTRY_LABEL_TEXTS.overview,
            window.report_ui_.address.hash_of({}),
          )
        : status_entry_of(
            VIEW_LABEL_TEXTS[address.view],
            window.report_ui_.address.home_hash_of(address.test, address.view),
          );
    if (address.test === null) return [view_entry];
    return [
      status_entry_of(
        test_name_text_of(address.test),
        window.report_ui_.address.home_hash_of(address.test, CALLERS_VIEW_KEY),
      ),
      view_entry,
      ...heat_map_status_entries_of(address),
    ];
  }
  function title_text_of(address) {
    if (address.test === null) return home_title_text;
    return [
      test_name_text_of(address.test),
      VIEW_LABEL_TEXTS[address.view],
      heat_map_part_text(address),
    ]
      .filter((part_text) => part_text)
      .join(TITLE_PART_SEPARATOR);
  }
  function menu_render() {
    const address = window.report_frame_.address_now();
    const button_entries = menu_entries_of(address);
    menu_strip_handle = window.report_ui_.strip.render(
      menu_strip,
      button_entries,
      status_entries_of(address),
    );
    document.title = title_text_of(address);
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
  function menu_key_take(key_name, is_repeat) {
    if (
      menu_strip_handle.key_take(key_name, is_repeat) ||
      scale_key_take(key_name)
    )
      return true;
    if (!window.report_ui_.view_key.opens_tests_pulldown(key_name))
      return false;
    menu_strip_handle.pulldown_open(TEST_ENTRY_NAME, key_name);
    return true;
  }

  function activate() {
    document.addEventListener(
      "keydown",
      window.try_catch_handler_((key_event) => {
        window.report_ui_.widget_key.link_click_take(key_event);
        const key_name = window.report_ui_.view_key.of(key_event);
        if (key_name && menu_key_take(key_name, key_event.repeat))
          key_event.preventDefault();
      }),
    );
    document.addEventListener(
      "click",
      window.try_catch_handler_((click_event) => {
        const link_hash = window.report_ui_.address.link_hash_of(click_event);
        if (!link_hash) return;
        click_event.preventDefault();
        window.report_frame_.address_request(link_hash);
      }),
    );
    window.report_ui_.resize_settle_register(menu_render);
  }

  window.report_menu_ = {
    address_show,
    menu_key_take,
  };

  activate();
  window.report_frame_.activate();
})();
