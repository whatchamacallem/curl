(function () {
  "use strict";

  const HEAT_MAP_VIEW_ENTRY = settings("HEAT_MAP_VIEW_ENTRY");
  const HEAT_MAP_VIEW_KEY = HEAT_MAP_VIEW_ENTRY[0];

  const is_framed = window.report_ui.is_framed;
  const tests_pulldown_root = document.getElementById("tests-pulldown");
  const view_frame = document.getElementById("view");

  let current_inner_hash = "",
    current_page_href = "";

  const hash_build = (view_key, inner_hash) =>
    view_key
      ? "#" + view_key + (inner_hash ? "/" + inner_hash.slice(1) : "")
      : "";
  function hash_for_href(link_href) {
    for (const link_element of window.report_menu.view_links) {
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
  function view_show(target_hash) {
    const view_links = window.report_menu.view_links;
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
        window.ui_strings.text_fill("str_error_hash_view_unknown", [
          target_hash,
        ]),
      );
      return;
    }
    const [view_key, inner_hash] = parsed_hash;
    const active_link = matched_link || view_links[0];
    window.report_menu.view_links_activate(active_link);
    window.report_menu.title_publish(active_link.dataset.title);
    window.report_menu.active_test_show(matched_link);
    window.report_menu.utility_visibility_set(
      !is_framed && !!(matched_link && view_key && matched_link.dataset.frame),
    );
    if (!matched_link || !view_key) {
      view_frame.hidden = true;
      window.report_menu.home_panel_show();
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
    window.report_menu.home_panel_hide();
    view_frame.hidden = false;
    window.report_ui.hash_publish(hash_build(view_key, inner_hash));
  }
  function reset_broadcast() {
    window.report_menu.home_panel_reset();
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

  // The counter the heat map on show reads, as its address names it: null
  // when it names none or no heat map shows, and a jump opens the default.
  function shown_counter_key() {
    // the overview's own address names the framed test before its view
    const view_hash = tests_pulldown_root
      ? hash_parse(location.hash)[1]
      : location.hash;
    const [view_key, heat_map_hash] = hash_parse(view_hash);
    return view_key === HEAT_MAP_VIEW_KEY
      ? window.report_ui.heat_map_address.state_of_hash(heat_map_hash).ev
      : null;
  }
  // Where a view link opens its view: its home, the heat map's on the counter
  // on show. The overview's view keys are tests, not views.
  function view_home_hash(view_key) {
    return view_key === HEAT_MAP_VIEW_KEY && !tests_pulldown_root
      ? window.report_ui.heat_map_address.hash_of_state({
          ev: shown_counter_key(),
        })
      : "";
  }
  // The hash a heat map entry opens: the test, its heat map, the named
  // file or function there, on the counter on show. The menu's one door in.
  function heat_map_entry_hash(active_test_name, state_field, name) {
    const heat_map_hash = window.report_ui.heat_map_address.hash_of_state({
      [state_field]: name,
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

  // Wiring and the first view_show wait for this: menu.js, loaded after,
  // must be ready before view_show can reach into it.
  function activate() {
    document.addEventListener("click", (click_event) => {
      const link_element = click_event.target.closest("a[href]");
      if (
        !link_element ||
        link_element === window.report_menu.layout_reset_link ||
        link_element.target
      )
        return;
      if (click_event.ctrlKey || click_event.metaKey || click_event.shiftKey)
        return;
      if (click_event.button) return;
      const link_href = link_element.getAttribute("href");
      const view_key = link_element.dataset.view;
      const target_hash =
        view_key != null
          ? hash_build(view_key, view_home_hash(view_key))
          : hash_for_href(link_href);
      if (target_hash == null) return;
      click_event.preventDefault();
      hash_update_request(target_hash);
    });
    // a key typed in a pulldown's own box is that pulldown's, taken first
    document.addEventListener("keydown", (key_event) => {
      const key_name = window.report_ui.pulldown.key_of(key_event);
      if (!key_name || key_event.target.closest("input, select, textarea"))
        return;
      if (!window.report_menu.typing_reaches_tests_pulldown()) return;
      if (window.report_menu.tests_key_take(key_name)) {
        key_event.preventDefault();
      }
    });
    window.addEventListener("message", (message_event) => {
      if (
        message_event.source !== view_frame.contentWindow ||
        !message_event.data
      )
        return;
      const message_tag = message_event.data.report_ui;
      if (message_tag === "title_changed")
        window.report_menu.title_publish(message_event.data.title);
      else if (message_tag === "scale_changed")
        scale_apply(Number(message_event.data.travel));
      else if (message_tag === "tests_pulldown_key_pressed")
        window.report_menu.tests_key_take(message_event.data.key);
      else if (message_tag === "hash_changed") {
        if (!current_page_href) return;
        current_inner_hash = message_event.data.hash;
        window.report_ui.hash_publish(
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
      if (message_data === "report_ui:title_request")
        window.report_menu.title_publish_current();
      else if (message_data === "report_ui:layout_reset") reset_broadcast();
      else if (message_data === "report_ui:tests_pulldown_closed")
        window.report_menu.tests_pulldown_closed();
      else if (
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
    current_inner_hash: () => current_inner_hash,
    hash_update_request,
    heat_map_entry_hash,
    is_framed,
    reset_broadcast,
    scale_apply,
    tests_pulldown_closed_notify,
    tests_pulldown_root,
  };
})();
