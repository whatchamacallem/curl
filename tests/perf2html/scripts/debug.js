// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.report_manifest_table_ = __MANIFEST_TABLE__;

window.try_catch_handler_(function () {
  "use strict";

  const DEBUG_TIP_IDLE_DELAY_MS = settings_("DEBUG_TIP_IDLE_DELAY_MS");
  const SCREENSHOT_LABEL_QUERY_KEY_NAME = settings_(
    "SCREENSHOT_LABEL_QUERY_KEY_NAME",
  );
  const SCREENSHOT_LABEL_QUERY_VALUE = settings_(
    "SCREENSHOT_LABEL_QUERY_VALUE",
  );
  const SCREENSHOT_LABEL_TITLE_TEXT = settings_("SCREENSHOT_LABEL_TITLE_TEXT");
  const SCREENSHOT_MENU_KEY_NUMBER = settings_("SCREENSHOT_MENU_KEY_NUMBER");
  const SETTINGS_DEBUG_ENABLED = settings_("SETTINGS_DEBUG_ENABLED");
  const STYLE_COLOR_DARK_MODE = settings_("STYLE_COLOR_DARK_MODE");
  const STYLE_COLOR_LIGHT_MODE = settings_("STYLE_COLOR_LIGHT_MODE");

  const NONE_TEXT = window.ui_strings_.text("str_debug_tip_none");
  const ROLE_NAMES = [STYLE_COLOR_DARK_MODE, STYLE_COLOR_LIGHT_MODE].flatMap(
    (palette) => Object.values(palette).flat(),
  );
  let delay_ms = DEBUG_TIP_IDLE_DELAY_MS;
  let idle_timer = null;
  let pointer_position = null;
  let tip = null;

  // Finds the nearest element whose background is not clear.
  function background_element(element) {
    for (; element; element = element.parentElement) {
      const color = getComputedStyle(element).backgroundColor;
      if (color !== "rgba(0, 0, 0, 0)" && color !== "transparent")
        return element;
    }
    return document.documentElement;
  }
  // Names the color roles that set a property, else gives the color shown.
  function color_text(element, property_name) {
    const root_style = document.documentElement.style;
    const shown_color = getComputedStyle(element)[property_name];
    const role_names = ROLE_NAMES.filter((role_name) => {
      const role_value = root_style.getPropertyValue("--" + role_name);
      root_style.setProperty("--" + role_name, "transparent");
      const is_set = getComputedStyle(element)[property_name] !== shown_color;
      root_style.setProperty("--" + role_name, role_value);
      return is_set;
    });
    return role_names.length ? role_names.join(" ") : shown_color;
  }
  // Restarts the wait for a still pointer, unless the pointer is on the tip.
  function pointer_move(pointer_event) {
    if (tip.contains(pointer_event.target)) return;
    pointer_wait(pointer_event);
  }
  // Stops the wait when the pointer leaves the page or enters a frame.
  function pointer_out(pointer_event) {
    if (
      pointer_event.relatedTarget === null ||
      pointer_event.relatedTarget instanceof HTMLIFrameElement
    )
      clearTimeout(idle_timer);
  }
  // Stores the pointer position and restarts the wait for a still pointer.
  function pointer_wait(pointer_event) {
    pointer_position = { x: pointer_event.clientX, y: pointer_event.clientY };
    clearTimeout(idle_timer);
    idle_timer = setTimeout(window.try_catch_handler_(tip_show), delay_ms);
  }
  // Shows the report page address in a screenshot corner, a click copies it.
  function screenshot_label_show() {
    const query_values = new URLSearchParams(location.search);
    const label_value = query_values.get(SCREENSHOT_LABEL_QUERY_KEY_NAME);
    if (label_value === null) return;
    if (label_value !== SCREENSHOT_LABEL_QUERY_VALUE)
      window.throw_exception_(
        "str_error_screenshot_label_query_unusable",
        SCREENSHOT_LABEL_QUERY_KEY_NAME,
        label_value,
        SCREENSHOT_LABEL_QUERY_VALUE,
      );
    // The address shown opens the page with no screenshot code running.
    query_values.delete(SCREENSHOT_LABEL_QUERY_KEY_NAME);
    query_values.delete(SCREENSHOT_MENU_KEY_NUMBER);
    const query_text = query_values.size ? "?" + query_values : "";
    const path_names = location.pathname.split("/");
    const page_name = path_names.pop();
    const report_name = path_names.pop();
    const page_path = `${report_name}/${page_name}`;
    const label = document.createElement("div");
    label.className = "screenshot-";
    label.textContent = page_path + query_text + location.hash;
    label.title = SCREENSHOT_LABEL_TITLE_TEXT;
    label.addEventListener(
      "click",
      window.try_catch_handler_(() =>
        navigator.clipboard.writeText(label.textContent),
      ),
    );
    document.body.appendChild(label);
  }
  // Copies the tip text, then hides the tip for the click delay.
  function tip_click(click_event) {
    tip_hide(DEBUG_TIP_IDLE_DELAY_MS);
    pointer_wait(click_event);
    return navigator.clipboard.writeText(tip.textContent);
  }
  // Hides the tip and makes the next one wait the given delay.
  function tip_hide(reappear_delay_ms) {
    tip.style.display = "";
    delay_ms = reappear_delay_ms;
  }
  // Makes the tip, a click copies it, and starts watching the pointer.
  function tip_install() {
    tip = document.createElement("div");
    tip.className = "debug-tip-";
    tip.addEventListener("click", window.try_catch_handler_(tip_click));
    tip.addEventListener("mouseleave", window.try_catch_handler_(tip_leave));
    document.body.appendChild(tip);
    document.addEventListener(
      "mousemove",
      window.try_catch_handler_(pointer_move),
    );
    document.addEventListener(
      "mouseout",
      window.try_catch_handler_(pointer_out),
    );
  }
  // Hides a shown tip for the leave delay, a click having hidden it already.
  function tip_leave() {
    if (tip.style.display) tip_hide(DEBUG_TIP_IDLE_DELAY_MS);
  }
  // Shows the tag, class, id and color roles of the element under the pointer.
  function tip_show() {
    const element = document.elementFromPoint(
      pointer_position.x,
      pointer_position.y,
    );
    if (element === document.body || element === document.documentElement)
      return;
    const id_element = element.closest("[id]");
    tip.textContent = window.ui_strings_.text_fill("str_debug_tip_text", {
      tag: element.tagName.toLowerCase(),
      class: element.className || NONE_TEXT,
      id: id_element ? id_element.id : NONE_TEXT,
      fg: color_text(element, "color"),
      bg: color_text(background_element(element), "backgroundColor"),
    });
    tip.style.display = "block";
    const tip_rect = tip.getBoundingClientRect();
    const left_px = Math.min(
      pointer_position.x - tip_rect.width / 2,
      innerWidth - tip_rect.width,
    );
    const top_px = Math.min(
      pointer_position.y - tip_rect.height / 2,
      innerHeight - tip_rect.height,
    );
    tip.style.left = window.report_ui_.design_px(Math.max(left_px, 0)) + "px";
    tip.style.top = window.report_ui_.design_px(Math.max(top_px, 0)) + "px";
  }

  screenshot_label_show();
  if (SETTINGS_DEBUG_ENABLED) tip_install();
})();
