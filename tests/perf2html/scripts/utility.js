// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const MENU_BUTTON_KIND_NAMES = ["action", "link", "pulldown"];
  const RELAY_MESSAGE_NAME = "report_error";
  const RESOURCE_FAILURE_TEXT = "resource failed: ";
  const RESOURCE_TAG_NAMES = ["LINK", "SCRIPT", "IMG"];
  const is_framed =
    window.parent !== window &&
    !document.documentElement.hasAttribute("data-top-page-");
  const report_error_overlay = window.report_error_overlay_;
  const expected_failure_sources = new Set();

  // Escapes text for markup, the one escape the page scripts write through.
  function shared_html_escape_(text) {
    return String(text)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;");
  }
  // Writes one element, the one writer of a tag, a null inner a void tag.
  function shared_element_render_(tag_name, attributes, inner_markup) {
    const attribute_text = Object.entries(attributes)
      .map(([attribute_name, attribute_value]) => {
        if (!["number", "string"].includes(typeof attribute_value))
          throw new Error(
            window.ui_strings_.text_fill(
              "str_error_markup_attribute_unusable",
              [attribute_name, String(attribute_value)],
            ),
          );
        return ` ${attribute_name}="${shared_html_escape_(attribute_value)}"`;
      })
      .join("");
    const start_tag = `<${tag_name}${attribute_text}>`;
    if (inner_markup === null) return start_tag;
    return `${start_tag}${inner_markup}</${tag_name}>`;
  }
  // Makes the one element a piece of markup holds.
  function shared_element_of_(markup) {
    const markup_template = document.createElement("template");
    markup_template.innerHTML = markup;
    const made_nodes = markup_template.content.childNodes;
    if (
      made_nodes.length !== 1 ||
      made_nodes[0].nodeType !== Node.ELEMENT_NODE
    )
      throw new Error(
        window.ui_strings_.text_fill("str_error_markup_element_count", [
          markup,
        ]),
      );
    return made_nodes[0];
  }
  // Writes a menu button: menu colours, then a tab stop, link or role by kind.
  function shared_menu_button_render_(kind_name, label_markup, fields) {
    if (!MENU_BUTTON_KIND_NAMES.includes(kind_name))
      throw new Error(
        window.ui_strings_.text_fill("str_error_menu_button_kind_unknown", [
          kind_name,
        ]),
      );
    const own_attributes = {
      class: ["menu-button-", ...(fields.class_names || [])].join(" "),
    };
    let inner_markup = label_markup;
    if (!fields.is_unavailable && kind_name === "link") {
      const link_attributes = { href: fields.href };
      if (fields.opens_new_tab) link_attributes.target = "_blank";
      if (fields.tag_name === "a")
        Object.assign(own_attributes, link_attributes);
      else {
        own_attributes.tabindex = 0;
        inner_markup = shared_element_render_(
          "a",
          { ...link_attributes, tabindex: -1 },
          label_markup,
        );
      }
    } else if (
      !fields.is_unavailable &&
      kind_name === "action" &&
      fields.tag_name !== "summary"
    ) {
      own_attributes.role = "button";
      if (!fields.is_widget) own_attributes.tabindex = 0;
    }
    const extra_attributes = fields.attributes || {};
    for (const attribute_name of Object.keys(extra_attributes)) {
      if (Object.hasOwn(own_attributes, attribute_name))
        throw new Error(
          window.ui_strings_.text_fill(
            "str_error_menu_button_attribute_owned",
            [attribute_name],
          ),
        );
    }
    return shared_element_render_(
      fields.tag_name,
      { ...own_attributes, ...extra_attributes },
      inner_markup,
    );
  }
  // Writes page emphasis: its colours and one space each side, in either mode.
  function shared_page_emphasis_render_(label_markup, fields) {
    return shared_element_render_(
      fields.tag_name,
      { class: "page-emphasis-", ...(fields.attributes || {}) },
      label_markup,
    );
  }

  function report_relay_(report) {
    if (!is_framed) return false;
    window.parent.postMessage(
      { report_ui: RELAY_MESSAGE_NAME, report: report },
      "*",
    );
    return true;
  }

  function relayed_report_take_(browser_event) {
    const payload = browser_event.data;
    if (payload && payload.report_ui === RELAY_MESSAGE_NAME)
      report_error_overlay.relayed_report_show_(payload.report);
  }

  function resource_failure_expect_(source) {
    expected_failure_sources.add(source);
  }

  function resource_failure_take_(browser_event) {
    const target = browser_event.target;
    if (
      target &&
      target !== window &&
      RESOURCE_TAG_NAMES.includes(target.tagName) &&
      !expected_failure_sources.has(target.href || target.src)
    )
      report_error_overlay.err_overlay_show_(
        new Error(RESOURCE_FAILURE_TEXT + (target.href || target.src)),
      );
  }

  window.resource_failure_expect_ = resource_failure_expect_;
  window.shared_element_of_ = shared_element_of_;
  window.shared_element_render_ = shared_element_render_;
  window.shared_html_escape_ = shared_html_escape_;
  window.shared_is_framed_ = is_framed;
  window.shared_menu_button_render_ = shared_menu_button_render_;
  window.shared_page_emphasis_render_ = shared_page_emphasis_render_;
  report_error_overlay.relay_set_(report_relay_);
  window.addEventListener(
    "message",
    window.try_catch_handler_(relayed_report_take_),
  );
  window.addEventListener(
    "error",
    window.try_catch_handler_(resource_failure_take_),
    true,
  );
})();
