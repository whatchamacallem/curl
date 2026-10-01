window.catch_show_throw(function () {
  "use strict";

  const FLAME_GRAPH_VIEW_ENTRY = settings("FLAME_GRAPH_VIEW_ENTRY");

  // whether the report has the flame graph view: a diff's menu has no button
  const has_flame_graph = !!document.getElementById(
    `menu-${FLAME_GRAPH_VIEW_ENTRY[0]}-button-`,
  );
  const home_panel = window.report_ui.home_panel;
  // the tests the report holds, one tests pulldown entry each
  const test_names = Array.from(
    document.querySelectorAll("#menu-test-pulldown- a[data-test-name-]"),
    (entry_link) => entry_link.getAttribute("data-test-name-"),
  );
  const view_frame = window.report_ui.view_frame;

  // the address on show, recorded before the menu or the view hears of it
  let current_address = null;
  // the view page and hash last loaded into the frame, "" before the first
  let loaded_view_href = "";

  // The address on show, the parts of the top page's hash.
  function address_now() {
    return current_address;
  }
  // Refuse an address naming a test or a view this report lacks. The view
  // judges what only that view knows, a test's flame graph among them.
  function address_check(parsed_address) {
    if (
      parsed_address.test !== null &&
      !test_names.includes(parsed_address.test)
    )
      throw new Error(
        window.ui_strings.text_fill("str_error_hash_test_unknown", [
          parsed_address.test,
        ]),
      );
    if (parsed_address.view === FLAME_GRAPH_VIEW_ENTRY[0] && !has_flame_graph)
      throw new Error(
        window.ui_strings.text_fill("str_error_hash_view_unknown", [
          parsed_address.view,
        ]),
      );
  }
  // Show what the top page's hash names. Check it, record it, tell the
  // menu, then load its view with the hash unmodified, or show the home.
  function view_show() {
    const shown_address = window.report_ui.address.of_hash(location.hash);
    address_check(shown_address);
    current_address = shown_address;
    window.report_menu.address_show();
    if (shown_address.view === null) {
      // the focus the frame held goes on to the home's last tab stop, the
      // tests table's row, so Tab carries on from there
      const frame_had_focus = document.activeElement === view_frame;
      view_frame.hidden = true;
      home_panel.hidden = false;
      window.report_ui.layout_refresh(home_panel);
      if (frame_had_focus) {
        const tab_stops = home_panel.querySelectorAll('[tabindex="0"]');
        window.report_ui.tab_stop_move(
          null,
          tab_stops[tab_stops.length - 1],
          true,
        );
      }
      return;
    }
    const view_href =
      window.report_ui.address.page_href_of(shown_address) + location.hash;
    if (view_href !== loaded_view_href) {
      view_frame.contentWindow.location.replace(view_href);
      loaded_view_href = view_href;
    }
    // the focus the home panel held goes on to the view, not to the body,
    // so Tab carries on from there
    const home_had_focus = home_panel.contains(document.activeElement);
    home_panel.hidden = true;
    view_frame.hidden = false;
    if (home_had_focus) view_frame.focus();
  }
  // The one door every navigation takes, the menu's and a view's. A new
  // hash goes into the URL, and the hash on show is shown again.
  function address_request(requested_hash) {
    if (requested_hash === (location.hash || "#")) view_show();
    else location.hash = requested_hash;
  }
  // Hand a downward string to the views. The framed page gets each once one
  // loaded, and a layout reset puts the home panel's columns back too.
  function view_post(message_text) {
    if (message_text === "report_ui:layout_reset")
      window.report_ui.layout_reset(home_panel);
    if (loaded_view_href)
      view_frame.contentWindow.postMessage(message_text, "*");
  }
  // A message up from the view, an address the view asks for, or a key for
  // the menu, the view told no tests pulldown opened when the menu leaves it.
  function view_message_take(message_event) {
    const message_data = message_event.data;
    if (message_event.source !== view_frame.contentWindow || !message_data)
      return;
    const message_tag = message_data.report_ui;
    if (message_tag === "address_request") address_request(message_data.hash);
    else if (message_tag === "menu_key_pressed") {
      if (!window.report_menu.menu_key_take(message_data.key))
        view_post("report_ui:tests_pulldown_closed");
    }
    // report_error is error_overlay.js's own tag on this same channel
    else if (message_tag !== undefined && message_tag !== "report_error")
      throw new Error(
        window.ui_strings.text_fill("str_error_message_tag_unknown", [
          message_tag,
        ]),
      );
  }

  // Wiring and the first view_show wait for this: menu.js, loaded after,
  // calls activate once report_menu, which view_show tells, is ready.
  function activate() {
    window.addEventListener("hashchange", window.catch_show_throw(view_show));
    window.addEventListener(
      "message",
      window.catch_show_throw(view_message_take),
    );
    view_show();
  }

  window.report_frame = {
    activate,
    address_now,
    address_request,
    view_post,
  };
})();
