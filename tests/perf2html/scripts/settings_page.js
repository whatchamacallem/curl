// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const NUMBER_FRACTION_DIGITS = settings_("NUMBER_FRACTION_DIGITS");
  const SETTINGS_DEBUG_ENABLED = settings_("SETTINGS_DEBUG_ENABLED");
  const SETTINGS_DEBUG_JSON_INDENT_CHARS = settings_(
    "SETTINGS_DEBUG_JSON_INDENT_CHARS",
  );
  const SETTINGS_DEBUG_JSON_MAX_LENGTH_CHARS = settings_(
    "SETTINGS_DEBUG_JSON_MAX_LENGTH_CHARS",
  );
  const SETTINGS_DEBUG_JSON_SPACING_PATTERN = settings_(
    "SETTINGS_DEBUG_JSON_SPACING_PATTERN",
  );
  const SETTINGS_DEBUG_QUERY_KEY_NAME = settings_(
    "SETTINGS_DEBUG_QUERY_KEY_NAME",
  );
  const SETTINGS_DEBUG_QUERY_VALUES = settings_("SETTINGS_DEBUG_QUERY_VALUES");
  const SETTINGS_LOAD_LOG_HISTORY_ENTRY_NAME = settings_(
    "SETTINGS_LOAD_LOG_HISTORY_ENTRY_NAME",
  );
  const SETTINGS_LOAD_LOG_HISTORY_LINE_CHOICES = settings_(
    "SETTINGS_LOAD_LOG_HISTORY_LINE_CHOICES",
  );

  const ACTION_LABEL_TEXTS = {
    apply: window.ui_strings_.text("str_settings_apply"),
    copy: window.ui_strings_.text("str_settings_copy"),
    paste: window.ui_strings_.text("str_settings_paste"),
  };
  // Names each setting's actions, none while settings debugging is off.
  const ACTION_NAMES = SETTINGS_DEBUG_ENABLED
    ? ["copy", "paste", "apply"]
    : [];
  const DEBUG_QUERY_TEXT = window.ui_strings_.text_fill(
    "str_settings_debug_query",
    {
      name: SETTINGS_DEBUG_QUERY_KEY_NAME,
      value: SETTINGS_DEBUG_ENABLED
        ? SETTINGS_DEBUG_QUERY_VALUES.enabled
        : SETTINGS_DEBUG_QUERY_VALUES.disabled,
    },
  );
  const INDENT_TEXT = " ".repeat(SETTINGS_DEBUG_JSON_INDENT_CHARS);
  // Writes each kind of line value: a file as its report path, a span in ms.
  const LOAD_LOG_VALUE_WRITERS = {
    files: (file_href) => window.report_ui_.address.path(file_href),
    spans: milliseconds_text,
    texts: (value_text) => value_text,
  };
  const SETTING_ACTIONS = {
    apply: setting_apply,
    copy: setting_copy,
    paste: setting_paste,
  };
  const debug_box = document.getElementById("settings-debug-");
  const load_log_box = document.getElementById("settings-load-log-");
  const load_log_menu = document.getElementById("settings-load-log-menu-");
  const page_scroll_box = document.getElementById("settings-page-");
  const settings_list = document.getElementById("settings-list-");
  const setting_boxes = new Map();
  const setting_titles = new Map();
  let load_log_strip = null;

  // Writes a value as JSON, each part that fits its line kept on one line.
  function compact_json(json_value, current_indent, reserved_chars) {
    const spaced_text = JSON.stringify(json_value).replace(
      new RegExp(SETTINGS_DEBUG_JSON_SPACING_PATTERN, "g"),
      (match_text, string_literal) => string_literal || match_text + " ",
    );
    const room_chars =
      SETTINGS_DEBUG_JSON_MAX_LENGTH_CHARS -
      current_indent.length -
      reserved_chars;
    if (
      spaced_text.length <= room_chars ||
      json_value === null ||
      typeof json_value !== "object" ||
      !Object.keys(json_value).length
    )
      return spaced_text;
    const is_list = Array.isArray(json_value);
    const next_indent = current_indent + INDENT_TEXT;
    const item_entries = Object.entries(json_value);
    const item_texts = item_entries.map(
      ([item_key, item_value], item_index) => {
        const key_text = is_list ? "" : JSON.stringify(item_key) + ": ";
        return (
          key_text +
          compact_json(
            item_value,
            next_indent,
            key_text.length + (item_index === item_entries.length - 1 ? 0 : 1),
          )
        );
      },
    );
    return [
      is_list ? "[" : "{",
      INDENT_TEXT + item_texts.join(",\n" + next_indent),
      is_list ? "]" : "}",
    ].join("\n" + current_indent);
  }
  // Writes the value as an editable box under settings debugging, else text.
  function value_markup(setting_name, json_text) {
    if (!SETTINGS_DEBUG_ENABLED) return window.render_html_escape_(json_text);
    return window.render_element_(
      "textarea",
      {
        class: "settings-value-box-",
        cols: SETTINGS_DEBUG_JSON_MAX_LENGTH_CHARS,
        rows: json_text.split("\n").length,
        spellcheck: "false",
        wrap: "off",
        "data-setting-name-": setting_name,
      },
      window.render_html_escape_(json_text),
    );
  }
  // Writes the title line, the name and its action buttons, then the value.
  function setting_markup(setting_name) {
    const json_text = compact_json(settings_(setting_name), "", 0);
    const button_markups = ACTION_NAMES.map((action_name) =>
      window.render_menu_button_(
        "action",
        window.render_html_escape_(ACTION_LABEL_TEXTS[action_name]),
        {
          tag_name: "span",
          attributes: { "data-setting-action-": action_name },
        },
      ),
    );
    return (
      window.render_element_(
        "span",
        { "data-setting-name-": setting_name },
        [
          window.render_page_emphasis_(
            window.render_html_escape_(setting_name),
            {
              tag_name: "span",
            },
          ),
          ...button_markups,
        ].join(" "),
      ) +
      "\n" +
      value_markup(setting_name, json_text) +
      "\n"
    );
  }
  function box_rows_fit(setting_box) {
    setting_box.rows = setting_box.value.split("\n").length;
  }
  function box_text_set(setting_name, box_text) {
    const setting_box = setting_boxes.get(setting_name);
    setting_box.value = box_text;
    box_rows_fit(setting_box);
  }
  // Hands the box's JSON up as the setting's new value.
  function setting_apply(setting_name) {
    window.report_ui_.settings_apply_send(
      setting_name,
      JSON.parse(setting_boxes.get(setting_name).value),
    );
  }
  function setting_copy(setting_name) {
    return navigator.clipboard.writeText(
      setting_boxes.get(setting_name).value,
    );
  }
  function setting_paste(setting_name) {
    return navigator.clipboard
      .readText()
      .then((pasted_text) => box_text_set(setting_name, pasted_text));
  }
  function action_button(browser_event) {
    return browser_event.target.closest(".menu-button-");
  }
  function action_handler(action_button) {
    return SETTING_ACTIONS[action_button.getAttribute("data-setting-action-")](
      action_button
        .closest("[data-setting-name-]")
        .getAttribute("data-setting-name-"),
    );
  }
  // Hands the taker each button of the box that a click or key activates.
  function box_actions_listen(action_box, button_handler) {
    action_box.addEventListener(
      "click",
      window.try_catch_handler_((click_event) => {
        const activated_button = action_button(click_event);
        if (activated_button) return button_handler(activated_button);
      }),
    );
    action_box.addEventListener(
      "keydown",
      window.try_catch_handler_((key_event) => {
        const activated_button = action_button(key_event);
        if (
          !activated_button ||
          !window.report_ui_.widget_key.activates(
            window.report_ui_.widget_key.of(key_event),
          )
        )
          return;
        key_event.preventDefault();
        return button_handler(activated_button);
      }),
    );
  }
  // Scrolls the named setting's title to the top, else shows the page top.
  function address_setting_show() {
    const page_address = window.report_ui_.address.of_hash(location.hash);
    if (page_address.setting === null) page_scroll_box.scrollTo(0, 0);
    else
      page_scroll_box.scrollTop +=
        setting_titles.get(page_address.setting).getBoundingClientRect().top -
        page_scroll_box.getBoundingClientRect().top;
  }
  function milliseconds_text(milliseconds) {
    return window.report_ui_.fixed_text(milliseconds, NUMBER_FRACTION_DIGITS);
  }
  // Writes one history line, its time on the clock the top page started.
  function load_log_line(log_entry) {
    const [string_id, log_milliseconds, page_href, line_values] = log_entry;
    const marker_values = {
      page: window.report_ui_.address.path(page_href),
      time: milliseconds_text(log_milliseconds),
    };
    for (const [value_kind, kind_values] of Object.entries(line_values)) {
      if (!Object.hasOwn(LOAD_LOG_VALUE_WRITERS, value_kind))
        window.throw_exception_("str_error_internal");
      for (const [marker_name, value] of Object.entries(kind_values))
        marker_values[marker_name] = LOAD_LOG_VALUE_WRITERS[value_kind](value);
    }
    return window.ui_strings_.text_fill(string_id, marker_values);
  }
  function history_label(line_count) {
    return window.ui_strings_.text_fill("str_settings_load_log_history", {
      count: String(line_count),
    });
  }
  // Writes the history pulldown, whose choice the top page keeps.
  function load_log_strip_render(line_count) {
    return window.report_ui_.strip.render(
      load_log_menu,
      [
        window.report_ui_.strip.entry_make(
          SETTINGS_LOAD_LOG_HISTORY_ENTRY_NAME,
          "pulldown",
          history_label(line_count),
          {
            pulldown_options: {
              entries: () =>
                window.report_ui_.strip.choice_entries(
                  SETTINGS_LOAD_LOG_HISTORY_LINE_CHOICES.map(
                    (choice_count) => ({
                      label: String(choice_count),
                      value: String(choice_count),
                    }),
                  ),
                ),
              keeps_open: false,
              on_close: () => {},
              on_move: null,
              on_select: (value_text) =>
                window.report_ui_.load_log_history_send(Number(value_text)),
              reads_line_number: false,
            },
          },
        ),
      ],
      [],
    );
  }
  // Shows the history newest first, scrolling to the setting the first time.
  function load_log_show(log_entries, line_count) {
    load_log_box.textContent =
      [...log_entries.toReversed().map(load_log_line), ""].join("\n") + "\n";
    if (load_log_strip !== null) {
      load_log_strip.pulldown_label_set(
        SETTINGS_LOAD_LOG_HISTORY_ENTRY_NAME,
        history_label(line_count),
      );
      return;
    }
    load_log_strip = load_log_strip_render(line_count);
    address_setting_show();
  }

  debug_box.innerHTML =
    window.render_menu_button_(
      "action",
      window.render_html_escape_(DEBUG_QUERY_TEXT),
      { tag_name: "span" },
    ) + "\n\n";
  settings_list.innerHTML = window
    .settings_names_()
    .map(setting_markup)
    .join("");
  for (const setting_box of settings_list.querySelectorAll("textarea"))
    setting_boxes.set(
      setting_box.getAttribute("data-setting-name-"),
      setting_box,
    );
  for (const setting_title of settings_list.querySelectorAll(
    "span[data-setting-name-]",
  ))
    setting_titles.set(
      setting_title.getAttribute("data-setting-name-"),
      setting_title,
    );
  settings_list.addEventListener(
    "input",
    window.try_catch_handler_((input_event) =>
      box_rows_fit(input_event.target),
    ),
  );
  box_actions_listen(settings_list, action_handler);
  box_actions_listen(debug_box, () =>
    window.report_ui_.settings_debug_toggle_send(),
  );
  window.addEventListener(
    "hashchange",
    window.try_catch_handler_(address_setting_show),
  );
  document.title = window.ui_strings_.text("str_view_settings");
  window.report_ui_.view_activate({
    forwards_input: false,
    load_log_show,
    recenter: address_setting_show,
  });
})();
