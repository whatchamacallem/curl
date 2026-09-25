(function () {
  "use strict";

  const STRIP_TEST_MENU_KEY_NAMES = settings("STRIP_TEST_MENU_KEY_NAMES");
  const STRIP_TEST_MENU_MERGED_TEST_NAME = settings(
    "STRIP_TEST_MENU_MERGED_TEST_NAME",
  );
  const STRIP_TEST_MENU_SKIPPED_KEY_NAMES = settings(
    "STRIP_TEST_MENU_SKIPPED_KEY_NAMES",
  );
  const STRIP_WORDMARK_LOGO_START_FRACTION = settings(
    "STRIP_WORDMARK_LOGO_START_FRACTION",
  );

  const CARET_COLLAPSED_TEXT = window.ui_strings.text_of(
    "str_caret_collapsed",
  );
  const CARET_EXPANDED_TEXT = window.ui_strings.text_of("str_caret_expanded");
  const HIGHLIGHTED_ENTRY_CLASS = "highlighted-entry";
  const HOME_VIEW_LABEL = window.ui_strings.text_of("str_view_summary");
  const MENU_COMMAND_KEY_NAMES = Object.values(STRIP_TEST_MENU_KEY_NAMES);
  const NO_MATCH_TEXT = window.ui_strings.text_of("str_no_match");
  const OUTER_STATUS_TEXT = window.ui_strings.text_of("str_report_name");
  const SCALE_LABEL_TEXT = window.ui_strings.text_of("str_control_view_scale");
  const SELECTION_SEPARATOR = " / ";
  const WORDMARK_LETTER_CLASS = "wordmark-letter";

  const home_panel = document.getElementById("home");
  const is_framed = window.report_ui.is_framed;
  const layout_reset_link = document.getElementById("layout-reset");
  const scale_label = document.getElementById("scale-label");
  const scale_slider = document.getElementById("scale-slider");
  const scale_text = document.getElementById("scale-text");
  const strip_bar = document.getElementById("bar");
  const test_menu_button = document.getElementById("test-menu-button");
  const test_menu_entries = [
    ...strip_bar.querySelectorAll("#test-menu-list a[data-view]"),
  ];
  const test_menu_list = document.getElementById("test-menu-list");
  const test_menu_no_match = document.getElementById("test-menu-no-match");
  const test_menu_search = document.getElementById("test-menu-search");
  const title_badge = document.getElementById("title");
  const utility_block = document.getElementById("util");
  const view_frame = document.getElementById("view");
  const view_links = [...strip_bar.querySelectorAll("a[data-view]")];
  const wordmark_letters = window.report_ui.logo_letters_build(
    OUTER_STATUS_TEXT,
    WORDMARK_LETTER_CLASS,
    STRIP_WORDMARK_LOGO_START_FRACTION,
  );
  let current_inner_hash = "",
    current_page_href = "",
    current_title = title_badge.textContent;
  // On a framed summary, menu_is_open is the top page's menu: open from the
  // first character forwarded up until report_ui:test_menu_closed comes down.
  let highlight_index = 0,
    menu_is_open = false,
    menu_label_text = STRIP_TEST_MENU_MERGED_TEST_NAME,
    menu_matches = [];

  const hash_build = (view_key, inner_hash) =>
    view_key
      ? "#" + view_key + (inner_hash ? "/" + inner_hash.slice(1) : "")
      : "";
  function hash_for_href(link_href) {
    for (const link_element of view_links) {
      const link_base = link_element.getAttribute("href");
      if (link_element.dataset.view && link_href.startsWith(link_base)) {
        const remaining_hash = link_href.slice(link_base.length);
        return hash_build(
          link_element.dataset.view,
          remaining_hash.startsWith("#") ? remaining_hash : "",
        );
      }
    }
    return null;
  }
  // An outer hash's view key and inner hash: "" is home, and one this cannot
  // read is null, the bad address view_show reports.
  function hash_parse(hash_text) {
    if (hash_text === "") return ["", ""];
    const hash_match = /^#([\w-]*)(?:\/(.*))?$/.exec(hash_text);
    return hash_match
      ? [hash_match[1], hash_match[2] ? "#" + hash_match[2] : ""]
      : null;
  }
  function selection_path(new_title) {
    return new_title && !new_title.includes(SELECTION_SEPARATOR)
      ? new_title + SELECTION_SEPARATOR + HOME_VIEW_LABEL
      : new_title;
  }
  function title_publish(new_title) {
    current_title = new_title;
    if (is_framed) title_badge.textContent = selection_path(new_title);
    else title_badge.replaceChildren(...wordmark_letters);
    document.title = new_title;
    window.report_ui.parent_post({
      report_ui: "title_changed",
      title: new_title,
    });
  }
  function menu_label_show(matched_link) {
    // only the overview's strip has a test menu; a summary's has none
    if (!test_menu_search) return;
    menu_label_text = test_menu_entries.includes(matched_link)
      ? matched_link.textContent
      : STRIP_TEST_MENU_MERGED_TEST_NAME;
    if (!menu_is_open) test_menu_search.value = menu_label_text;
  }
  function view_show(target_hash) {
    const parsed_hash = hash_parse(target_hash);
    const matched_link =
      parsed_hash &&
      view_links.find(
        (link_element) => link_element.dataset.view === parsed_hash[0],
      );
    // an empty key is the home view and canonical. A hash this cannot read,
    // or naming a view this report does not have, is a bad address
    if (!parsed_hash || (parsed_hash[0] && !matched_link)) {
      window.report_error_overlay.overlay_show(
        new Error("str_error_hash_view_unknown " + target_hash),
        window.ui_strings.text_of("str_error_source_address"),
      );
      return;
    }
    const [view_key, inner_hash] = parsed_hash;
    const active_link = matched_link || view_links[0];
    for (const link_element of view_links) {
      link_element.classList.toggle("on", link_element === active_link);
    }
    title_publish(active_link.dataset.title);
    menu_label_show(matched_link);
    utility_block.hidden =
      !is_framed && !!(matched_link && view_key && matched_link.dataset.frame);
    scale_label.hidden = utility_block.hidden;
    if (!matched_link || !view_key) {
      view_frame.hidden = true;
      home_panel.hidden = false;
      window.report_ui.layout_refresh(home_panel);
      window.report_ui.hash_publish("");
      return;
    }
    const link_href = matched_link.getAttribute("href");
    if (link_href !== current_page_href || inner_hash !== current_inner_hash) {
      view_frame.contentWindow.location.replace(
        link_href + (inner_hash || "#"),
      );
    } else
      view_frame.contentWindow.postMessage("report_ui:title_request", "*");
    current_page_href = link_href;
    current_inner_hash = inner_hash;
    home_panel.hidden = true;
    view_frame.hidden = false;
    window.report_ui.hash_publish(hash_build(view_key, inner_hash));
  }
  function reset_broadcast() {
    window.report_ui.layout_reset(home_panel);
    if (current_page_href)
      view_frame.contentWindow.postMessage("report_ui:layout_reset", "*");
  }

  function scale_apply(travel) {
    if (is_framed) {
      window.report_ui.parent_post({
        report_ui: "scale_changed",
        travel: travel,
      });
      return;
    }
    window.report_ui.design_scale_travel_set(travel);
    window.report_ui.view_storage.value_write("view.scale", travel);
    reset_broadcast();
  }
  function scale_activate() {
    scale_text.textContent = SCALE_LABEL_TEXT;
    const saved_travel =
      window.report_ui.view_storage.value_read("view.scale");
    if (saved_travel != null && !is_framed)
      window.report_ui.design_scale_travel_set(saved_travel);
    scale_slider.value = String(
      saved_travel != null
        ? saved_travel
        : window.report_ui.design_scale_travel_now(),
    );
    scale_slider.addEventListener("input", () => {
      scale_apply(Number(scale_slider.value));
    });
  }

  // The search box's text as a pattern. One that does not compile yet (a
  // lone "(" mid-typing) is null and matches nothing; any other error throws.
  function search_pattern_of(search_text) {
    try {
      return new RegExp(search_text, "i");
    } catch (pattern_error) {
      if (!(pattern_error instanceof SyntaxError)) throw pattern_error;
      return null;
    }
  }
  function highlight_set(entry_index) {
    highlight_index = entry_index;
    for (const entry_link of test_menu_entries) {
      entry_link.classList.toggle(
        HIGHLIGHTED_ENTRY_CLASS,
        entry_link === menu_matches[highlight_index],
      );
    }
  }
  function highlight_step(step_count) {
    if (!menu_matches.length) return;
    highlight_set(
      Math.min(
        Math.max(highlight_index + step_count, 0),
        menu_matches.length - 1,
      ),
    );
    menu_matches[highlight_index].scrollIntoView({ block: "nearest" });
  }
  function menu_filter() {
    const search_pattern = search_pattern_of(test_menu_search.value);
    menu_matches = test_menu_entries.filter(
      (entry_link) =>
        !!search_pattern && search_pattern.test(entry_link.textContent),
    );
    for (const entry_link of test_menu_entries) {
      entry_link.hidden = !menu_matches.includes(entry_link);
    }
    test_menu_no_match.hidden = menu_matches.length > 0;
    test_menu_list.scrollTop = 0;
    highlight_set(0);
  }
  // Focus the search box, out of the framed page if focus is there: a key's
  // user activation reaches the top page. A refusal would strand the keys.
  function search_box_focus() {
    test_menu_search.focus();
    if (document.activeElement !== test_menu_search)
      throw new Error(
        "str_error_test_menu_focus_refused " +
          document.activeElement.tagName.toLowerCase(),
      );
  }
  function menu_open(search_text) {
    menu_is_open = true;
    test_menu_search.readOnly = false;
    test_menu_search.value = search_text;
    test_menu_button.textContent = CARET_EXPANDED_TEXT;
    test_menu_list.hidden = false;
    menu_filter();
    search_box_focus();
  }
  function menu_close() {
    menu_is_open = false;
    test_menu_search.readOnly = true;
    test_menu_search.value = menu_label_text;
    test_menu_button.textContent = CARET_COLLAPSED_TEXT;
    test_menu_list.hidden = true;
    if (current_page_href)
      view_frame.contentWindow.postMessage("report_ui:test_menu_closed", "*");
  }
  function menu_select() {
    if (!menu_matches.length) return;
    menu_matches[highlight_index].click();
  }
  // What this keydown gives the test menu: a typed character or one of
  // STRIP_TEST_MENU_KEY_NAMES, or "" for a key that stays the page's.
  function menu_key_of(key_event) {
    const key_name = key_event.key;
    const is_plain =
      !key_event.defaultPrevented &&
      !key_event.isComposing &&
      !key_event.altKey &&
      !key_event.ctrlKey &&
      !key_event.metaKey;
    const is_typed =
      key_name.length === 1 &&
      !STRIP_TEST_MENU_SKIPPED_KEY_NAMES.includes(key_name);
    return is_plain && (is_typed || MENU_COMMAND_KEY_NAMES.includes(key_name))
      ? key_name
      : "";
  }
  // Keys go to the test menu from this page's own home, or on top from a
  // framed summary's home. A summary opened on its own has no menu.
  function typing_opens_menu() {
    if (!is_framed && !test_menu_search) return false;
    return !home_panel.hidden || (!is_framed && !current_inner_hash);
  }
  // The test menu's one key handler, for a key pressed here or forwarded up
  // by a framed summary, which forwards it on. True when the key is taken.
  function menu_key_take(key_name, is_in_search_box) {
    const is_command_key = MENU_COMMAND_KEY_NAMES.includes(key_name);
    if (is_framed) {
      if (is_command_key && !menu_is_open) return false;
      if (!is_command_key) menu_is_open = true;
      window.report_ui.parent_post({
        report_ui: "test_menu_key_pressed",
        key: key_name,
      });
      return true;
    }
    if (!menu_is_open) {
      const is_opening_key =
        !is_command_key ||
        (is_in_search_box && key_name === STRIP_TEST_MENU_KEY_NAMES.next);
      if (!is_opening_key) return false;
      menu_open(is_command_key ? "" : key_name);
      return true;
    }
    switch (key_name) {
      case STRIP_TEST_MENU_KEY_NAMES.close:
        menu_close();
        return true;
      case STRIP_TEST_MENU_KEY_NAMES.next:
        highlight_step(1);
        return true;
      case STRIP_TEST_MENU_KEY_NAMES.previous:
        highlight_step(-1);
        return true;
      case STRIP_TEST_MENU_KEY_NAMES.select:
        menu_select();
        return true;
    }
    // the focused open box types for itself; a key from elsewhere is appended
    if (is_in_search_box) return false;
    test_menu_search.value += key_name;
    menu_filter();
    search_box_focus();
    return true;
  }
  function menu_activate() {
    test_menu_no_match.textContent = NO_MATCH_TEXT;
    menu_close();
    for (const menu_control of [test_menu_button, test_menu_list]) {
      menu_control.addEventListener("mousedown", (pointer_event) =>
        pointer_event.preventDefault(),
      );
    }
    test_menu_button.addEventListener("click", () => {
      if (menu_is_open) menu_close();
      else menu_open("");
    });
    test_menu_search.addEventListener("click", () => {
      if (!menu_is_open) menu_open("");
    });
    test_menu_search.addEventListener("blur", () => {
      if (menu_is_open) menu_close();
    });
    test_menu_search.addEventListener("input", menu_filter);
    test_menu_list.addEventListener("pointermove", (pointer_event) => {
      const entry_index = menu_matches.indexOf(
        pointer_event.target.closest("a"),
      );
      if (entry_index >= 0 && entry_index !== highlight_index)
        highlight_set(entry_index);
    });
    test_menu_list.addEventListener("click", (click_event) => {
      if (!click_event.target.closest("a")) return;
      menu_close();
      test_menu_search.blur();
    });
  }

  layout_reset_link.addEventListener("click", (pointer_event) => {
    pointer_event.preventDefault();
    reset_broadcast();
  });
  if (!is_framed) {
    title_badge.addEventListener("click", () =>
      location.assign(title_badge.dataset.rootHref),
    );
  }
  document.addEventListener("click", (click_event) => {
    const link_element = click_event.target.closest("a[href]");
    if (
      !link_element ||
      link_element === layout_reset_link ||
      link_element.target
    )
      return;
    if (click_event.ctrlKey || click_event.metaKey || click_event.shiftKey)
      return;
    if (click_event.button) return;
    const link_href = link_element.getAttribute("href");
    const target_hash =
      link_element.dataset.view != null
        ? hash_build(link_element.dataset.view, "")
        : hash_for_href(link_href);
    if (target_hash == null) return;
    click_event.preventDefault();
    if (target_hash === (location.hash || "")) view_show(target_hash);
    else location.hash = target_hash;
  });
  document.addEventListener("keydown", (key_event) => {
    const key_name = menu_key_of(key_event);
    const is_in_search_box = key_event.target === test_menu_search;
    const is_in_field = !!key_event.target.closest("input, select, textarea");
    if (!key_name) return;
    if (!is_in_search_box && (is_in_field || !typing_opens_menu())) return;
    if (menu_key_take(key_name, is_in_search_box)) key_event.preventDefault();
  });
  window.addEventListener("message", (message_event) => {
    if (
      message_event.source !== view_frame.contentWindow ||
      !message_event.data
    )
      return;
    if (message_event.data.report_ui === "title_changed")
      title_publish(message_event.data.title);
    else if (message_event.data.report_ui === "scale_changed")
      scale_apply(Number(message_event.data.travel));
    else if (message_event.data.report_ui === "test_menu_key_pressed")
      menu_key_take(message_event.data.key, false);
    else if (
      message_event.data.report_ui === "hash_changed" &&
      current_page_href
    ) {
      current_inner_hash = message_event.data.hash;
      window.report_ui.hash_publish(
        hash_build(hash_parse(location.hash)[0], current_inner_hash),
      );
    }
  });
  window.report_ui.parent_listen((message_data) => {
    if (message_data === "report_ui:title_request")
      title_publish(current_title);
    else if (message_data === "report_ui:layout_reset") reset_broadcast();
    else if (message_data === "report_ui:test_menu_closed")
      menu_is_open = false;
  });
  window.addEventListener("hashchange", () => view_show(location.hash));
  if (test_menu_search) menu_activate();
  scale_activate();
  view_show(location.hash);
})();
