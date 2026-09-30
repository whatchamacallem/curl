(function () {
  "use strict";

  const HEAT_MAP_VIEW_ENTRY = settings("HEAT_MAP_VIEW_ENTRY");
  const HEAT_MAP_VIEW_KEY = HEAT_MAP_VIEW_ENTRY[0];

  const is_framed = window.report_ui.is_framed;
  const menu_bar = document.getElementById("menu_");
  const tests_pulldown_root = document.getElementById("menu-test-pulldown-");
  const view_frame = window.report_ui.view_frame;

  let current_inner_hash = "",
    current_page_href = "";

  const hash_build = (view_key, inner_hash) =>
    view_key
      ? "#" + view_key + (inner_hash ? "/" + inner_hash.slice(1) : "")
      : "";
  // The hash a link into a keyed page opens: the address the link names in
  // that page, or where the page's own key opens when it names none.
  function hash_for_href(link_href) {
    for (const link_element of window.report_menu.view_links) {
      const link_base = link_element.getAttribute("href");
      const view_key = link_element.getAttribute("data-view-");
      if (view_key && link_href.startsWith(link_base)) {
        const remaining_hash = link_href.slice(link_base.length);
        return remaining_hash.startsWith("#")
          ? hash_build(view_key, remaining_hash)
          : key_home_hash(view_key);
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
  function view_show(target_hash) {
    const view_links = window.report_menu.view_links;
    const parsed_hash = hash_parse(target_hash);
    const matched_link =
      parsed_hash &&
      view_links.find(
        (link_element) =>
          link_element.getAttribute("data-view-") === parsed_hash[0],
      );
    // the overview's title describes the test's own address under its key
    const view_is_unreadable =
      !!parsed_hash && !!tests_pulldown_root && !hash_parse(parsed_hash[1]);
    // an empty key is the home view and canonical. A hash this cannot read,
    // or naming a view this report does not have, is a bad address
    if (
      !parsed_hash ||
      view_is_unreadable ||
      (parsed_hash[0] && !matched_link)
    ) {
      window.report_error_overlay.overlay_show(
        window.ui_strings.text_fill("str_error_hash_view_unknown", [
          target_hash,
        ]),
      );
      return;
    }
    const [view_key, inner_hash] = parsed_hash;
    if (!view_key) {
      view_frame.hidden = true;
      window.report_menu.home_panel_show();
      address_publish("");
      return;
    }
    const link_href = matched_link.getAttribute("href");
    if (link_href !== current_page_href || inner_hash !== current_inner_hash) {
      view_frame.contentWindow.location.replace(
        link_href + (inner_hash || "#"),
      );
    }
    current_page_href = link_href;
    current_inner_hash = inner_hash;
    window.report_menu.home_panel_hide();
    view_frame.hidden = false;
    address_publish(hash_build(view_key, inner_hash));
  }
  // Publish this page's address, then describe it in the menu: the one
  // path every change of view, or of the framed view's address, takes.
  function address_publish(page_hash) {
    window.report_ui.hash_publish(page_hash);
    window.report_menu.address_show();
  }
  // The address on show, as the menu describes it: the test, "" at the
  // overview's home, the view in it, and a heat map's state on a heat map.
  function address_now() {
    const [test_name, view_hash] = tests_pulldown_root
      ? hash_parse(location.hash)
      : [menu_bar.getAttribute("data-test-name-"), location.hash];
    const [view_key, heat_map_hash] = hash_parse(view_hash);
    return {
      test_name,
      view_key,
      heat_map_state:
        view_key === HEAT_MAP_VIEW_KEY
          ? window.report_ui.heat_map_address.state_of_hash(heat_map_hash)
          : null,
    };
  }
  // Put the heat map on show back where its address first opened it. A
  // callers page hands the request on to the heat map it frames.
  function recenter_broadcast() {
    view_frame.contentWindow.postMessage("report_ui:recenter", "*");
  }
  function reset_broadcast() {
    window.report_menu.home_panel_reset();
    if (current_page_href)
      view_frame.contentWindow.postMessage("report_ui:layout_reset", "*");
  }

  // Move the scale to a stop: this page's main contents and its frame, the
  // page in it zoomed with the frame, then every column back.
  function scale_apply(travel_stop) {
    window.report_ui.design_scale_travel_set(travel_stop);
    reset_broadcast();
  }

  // The counter the heat map on show reads, as its address names it: null
  // when it names none or no heat map shows, and a jump opens the default.
  function shown_counter_key() {
    const heat_map_state = address_now().heat_map_state;
    return heat_map_state ? heat_map_state.ev : null;
  }
  // Where a view opens at its home: the heat map on the counter on show,
  // any other view with no address of its own.
  function view_home_hash(view_key) {
    return view_key === HEAT_MAP_VIEW_KEY
      ? window.report_ui.heat_map_address.hash_of_state({
          ev: shown_counter_key(),
        })
      : "";
  }
  // The address opening one test's view at its home. The overview's names
  // the test first; a callers page's is its own test's.
  function view_address_hash(test_name, view_key) {
    const view_hash = hash_build(view_key, view_home_hash(view_key));
    return tests_pulldown_root ? hash_build(test_name, view_hash) : view_hash;
  }
  // Where a link keyed to this page opens: on a callers page that view at its
  // home, and on the overview that test, on its heat map's home.
  function key_home_hash(view_key) {
    return tests_pulldown_root && view_key
      ? view_address_hash(view_key, HEAT_MAP_VIEW_KEY)
      : hash_build(view_key, view_home_hash(view_key));
  }
  // The hash a heat map entry opens: the test, its heat map, the named file
  // at any line, or function, there on the counter on show. The one door in.
  function heat_map_entry_hash(
    active_test_name,
    state_field,
    name,
    line_number,
  ) {
    const heat_map_hash = window.report_ui.heat_map_address.hash_of_state({
      [state_field]: name,
      line: line_number,
      ev: shown_counter_key(),
    });
    return hash_build(
      active_test_name,
      hash_build(HEAT_MAP_VIEW_KEY, heat_map_hash),
    );
  }
  // The menu's one door onto the frame's URL: a new hash from a pulldown
  // selection, applied exactly as if it had changed outside this page.
  function hash_update_request(target_hash) {
    if (target_hash === (location.hash || "")) view_show(target_hash);
    else location.hash = target_hash;
  }
  // The tests pulldown closed: tell the framed page underneath, if any.
  function tests_pulldown_closed_notify() {
    if (current_page_href)
      view_frame.contentWindow.postMessage(
        "report_ui:tests_pulldown_closed",
        "*",
      );
  }
  // A key a framed page sent up: a framed callers page hands it on up, the
  // top page's menu takes it, or tells the pages below no pulldown is open.
  function menu_key_relay(message_data) {
    if (is_framed) window.report_ui.parent_post(message_data);
    else if (!window.report_menu.menu_key_take(message_data.key))
      tests_pulldown_closed_notify();
  }

  // Wiring and the first view_show wait for this: menu.js, loaded after,
  // must be ready before view_show can reach into it.
  function activate() {
    document.addEventListener("click", (click_event) => {
      const link_element = click_event.target.closest("a[href]");
      // a click the menu already took, the title's recentring part, opens
      // nothing
      if (!link_element || link_element.target || click_event.defaultPrevented)
        return;
      if (click_event.ctrlKey || click_event.metaKey || click_event.shiftKey)
        return;
      if (click_event.button) return;
      const link_href = link_element.getAttribute("href");
      const view_key = link_element.getAttribute("data-view-");
      const target_hash =
        view_key != null ? key_home_hash(view_key) : hash_for_href(link_href);
      if (target_hash == null) return;
      click_event.preventDefault();
      hash_update_request(target_hash);
    });
    // the top page's menu takes a key typed on it; a framed page sends it up
    document.addEventListener("keydown", (key_event) => {
      const key_name = window.report_ui.menu_key.of(key_event);
      if (!key_name) return;
      const is_taken = is_framed
        ? window.report_ui.menu_key.forward(key_name)
        : window.report_menu.menu_key_take(key_name);
      if (is_taken) key_event.preventDefault();
    });
    window.addEventListener("message", (message_event) => {
      if (
        message_event.source !== view_frame.contentWindow ||
        !message_event.data
      )
        return;
      const message_tag = message_event.data.report_ui;
      if (message_tag === "menu_key_pressed")
        menu_key_relay(message_event.data);
      else if (message_tag === "hash_changed") {
        if (!current_page_href) return;
        current_inner_hash = message_event.data.hash;
        address_publish(
          hash_build(hash_parse(location.hash)[0], current_inner_hash),
        );
      }
      // report_error is error_overlay.js's own tag on this same channel
      else if (message_tag !== undefined && message_tag !== "report_error")
        throw new Error(
          window.ui_strings.text_fill("str_error_message_tag_unknown", [
            message_tag,
          ]),
        );
    });
    window.report_ui.parent_listen((message_data) => {
      if (message_data === "report_ui:layout_reset") reset_broadcast();
      else if (message_data === "report_ui:recenter") recenter_broadcast();
      else if (message_data === "report_ui:tests_pulldown_closed") {
        window.report_ui.menu_key.tests_pulldown_closed();
        tests_pulldown_closed_notify();
      } else if (
        typeof message_data === "string" &&
        message_data.startsWith("report_ui:")
      )
        throw new Error(
          window.ui_strings.text_fill("str_error_message_tag_unknown", [
            message_data,
          ]),
        );
    });
    window.addEventListener("hashchange", () => view_show(location.hash));
    view_show(location.hash);
  }

  window.report_frame = {
    activate,
    address_now,
    hash_update_request,
    heat_map_entry_hash,
    is_framed,
    recenter_broadcast,
    reset_broadcast,
    scale_apply,
    tests_pulldown_closed_notify,
    tests_pulldown_root,
    view_address_hash,
  };
})();
