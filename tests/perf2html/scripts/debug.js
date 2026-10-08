// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.report_manifest_table_ = __MANIFEST_TABLE__;

window.try_catch_handler_(function () {
  "use strict";

  const DEBUG_TIP_CURSOR_OFFSET_PX = settings_("DEBUG_TIP_CURSOR_OFFSET_PX");
  const DEBUG_TIP_HEIGHT_PX = settings_("DEBUG_TIP_HEIGHT_PX");
  const DEBUG_TIP_WIDTH_PX = settings_("DEBUG_TIP_WIDTH_PX");
  const SETTINGS_DEBUG_ENABLED = settings_("SETTINGS_DEBUG_ENABLED");

  const NONE_TEXT = window.ui_strings_.text_of("str_debug_tip_none");
  let tip = null;

  // Finds the nearest background that is not clear.
  function effective_background(element) {
    for (; element; element = element.parentElement) {
      const color = getComputedStyle(element).backgroundColor;
      if (color !== "rgba(0, 0, 0, 0)" && color !== "transparent")
        return color;
    }
    return "transparent";
  }
  // Shows the tag, class, id and colours of the element under the pointer.
  function tip_show(pointer_event) {
    if (!tip) {
      tip = document.createElement("div");
      tip.className = "debug-tip-";
      document.body.appendChild(tip);
    }
    const element = pointer_event.target;
    if (element === document.body || element === document.documentElement) {
      tip.style.display = "";
      return;
    }
    const id_element = element.closest("[id]");
    tip.textContent = window.ui_strings_.text_fill("str_debug_tip_text", {
      tag: element.tagName.toLowerCase(),
      class: element.className || NONE_TEXT,
      id: id_element ? id_element.id : NONE_TEXT,
      fg: getComputedStyle(element).color,
      bg: effective_background(element),
    });
    tip.style.left =
      Math.min(
        pointer_event.clientX + DEBUG_TIP_CURSOR_OFFSET_PX,
        innerWidth - DEBUG_TIP_WIDTH_PX,
      ) + "px";
    tip.style.top =
      Math.min(
        pointer_event.clientY + DEBUG_TIP_CURSOR_OFFSET_PX,
        innerHeight - DEBUG_TIP_HEIGHT_PX,
      ) + "px";
    tip.style.display = "block";
  }

  if (SETTINGS_DEBUG_ENABLED)
    document.addEventListener(
      "mousemove",
      window.try_catch_handler_(tip_show),
    );
})();
