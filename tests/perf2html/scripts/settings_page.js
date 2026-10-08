// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const SETTINGS_DEBUG_JSON_INDENT_CHARS = settings_(
    "SETTINGS_DEBUG_JSON_INDENT_CHARS",
  );
  const SETTINGS_DEBUG_JSON_MAX_LENGTH_CHARS = settings_(
    "SETTINGS_DEBUG_JSON_MAX_LENGTH_CHARS",
  );
  const SETTINGS_DEBUG_JSON_SPACING_PATTERN = settings_(
    "SETTINGS_DEBUG_JSON_SPACING_PATTERN",
  );

  const ACTION_LABEL_TEXTS = {
    apply: window.ui_strings_.text_of("str_settings_apply"),
    copy: window.ui_strings_.text_of("str_settings_copy"),
    paste: window.ui_strings_.text_of("str_settings_paste"),
  };
  const ACTION_NAMES = ["copy", "paste", "apply"];
  const INDENT_TEXT = " ".repeat(SETTINGS_DEBUG_JSON_INDENT_CHARS);
  const SETTING_ACTIONS = {
    apply: setting_apply,
    copy: setting_copy,
    paste: setting_paste,
  };
  const page_scroll_box = document.querySelector("main.page-text-scroll-box-");
  const settings_list = document.getElementById("settings-list-");
  const setting_boxes = new Map();
  const setting_titles = new Map();

  // Writes a value as JSON, each part that fits its line kept on one line.
  function compact_json_of(json_value, current_indent, reserved_chars) {
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
          compact_json_of(
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
  // Writes the title line, the name and its action buttons, then the box.
  function setting_markup_of(setting_name) {
    const json_text = compact_json_of(settings_(setting_name), "", 0);
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
      window.render_element_(
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
      ) +
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
  function action_button_of(browser_event) {
    return browser_event.target.closest(".menu-button-[data-setting-action-]");
  }
  function action_take(action_button) {
    return SETTING_ACTIONS[action_button.getAttribute("data-setting-action-")](
      action_button
        .closest("[data-setting-name-]")
        .getAttribute("data-setting-name-"),
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

  settings_list.innerHTML = window
    .settings_names_()
    .map(setting_markup_of)
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
  settings_list.addEventListener(
    "click",
    window.try_catch_handler_((click_event) => {
      const action_button = action_button_of(click_event);
      if (action_button) return action_take(action_button);
    }),
  );
  settings_list.addEventListener(
    "keydown",
    window.try_catch_handler_((key_event) => {
      const action_button = action_button_of(key_event);
      if (
        !action_button ||
        !window.report_ui_.widget_key.activates(
          window.report_ui_.widget_key.of(key_event),
        )
      )
        return;
      key_event.preventDefault();
      return action_take(action_button);
    }),
  );
  window.addEventListener(
    "hashchange",
    window.try_catch_handler_(address_setting_show),
  );
  window.report_ui_.view_activate({
    dark_mode_apply: null,
    forwards_input: false,
    preferences_apply: null,
    recenter: address_setting_show,
  });
  address_setting_show();
})();
