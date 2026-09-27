(function () {
  "use strict";

  const HEAT_MAP_VIEW_ENTRY = settings("HEAT_MAP_VIEW_ENTRY");
  const STRIP_PULLDOWN_MERGED_TEST_NAME = settings(
    "STRIP_PULLDOWN_MERGED_TEST_NAME",
  );
  const STRIP_WORDMARK_LOGO_START_FRACTION = settings(
    "STRIP_WORDMARK_LOGO_START_FRACTION",
  );

  const FILES_LABEL_TEXT = window.ui_strings.text_of("str_control_files");
  const FUNCTIONS_LABEL_TEXT = window.ui_strings.text_of(
    "str_control_functions",
  );
  const HEAT_MAP_VIEW_KEY = HEAT_MAP_VIEW_ENTRY[0];
  const HOME_VIEW_LABEL = window.ui_strings.text_of("str_view_summary");
  const OUTER_STATUS_TEXT = window.ui_strings.text_of("str_report_name");
  const SCALE_LABEL_TEXT = window.ui_strings.text_of("str_control_view_scale");
  const SELECTION_SEPARATOR = " / ";
  const TESTS_LABEL_TEXT = window.ui_strings.text_of("str_control_tests");
  const WORDMARK_LETTER_CLASS = "wordmark-letter";

  const files_pulldown_root = document.getElementById("files-pulldown");
  const functions_pulldown_root = document.getElementById(
    "functions-pulldown",
  );
  const home_panel = document.getElementById("home");
  const is_framed = window.report_ui.is_framed;
  const layout_reset_link = document.getElementById("layout-reset");
  const scale_label = document.getElementById("scale-label");
  const scale_slider = document.getElementById("scale-slider");
  const scale_text = document.getElementById("scale-text");
  const strip_bar = document.getElementById("bar");
  const tests_pulldown_root = document.getElementById("tests-pulldown");
  const tests_pulldown_entries = tests_pulldown_root
    ? [...tests_pulldown_root.querySelectorAll(".pulldown-list a[data-view]")]
    : [];
  const title_badge = document.getElementById("title");
  const utility_block = document.getElementById("util");
  const view_frame = document.getElementById("view");
  const view_links = [...strip_bar.querySelectorAll("a[data-view]")];
  const wordmark_letters = window.report_ui.logo_letters_build(
    OUTER_STATUS_TEXT,
    WORDMARK_LETTER_CLASS,
    STRIP_WORDMARK_LOGO_START_FRACTION,
  );
  // Only the overview has pulldowns. Without its manifest script, written
  // last, the report never finished: shown, as Chrome mutes a file:// throw
  if (tests_pulldown_root && window.report_manifest === undefined) {
    window.report_error_overlay.overlay_show(
      new Error("str_error_report_incomplete"),
    );
    return;
  }
  let active_test_name = STRIP_PULLDOWN_MERGED_TEST_NAME,
    current_inner_hash = "",
    current_page_href = "",
    current_title = title_badge.textContent,
    tests_pulldown = null;
  // On a framed summary, the top page's tests pulldown: open from the first
  // character forwarded up until report_ui:tests_pulldown_closed comes down.
  let tests_pulldown_is_open = false;

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
  // The test every pulldown works in: the framed one, else the merged one.
  // The tests pulldown reads it while closed.
  function active_test_show(matched_link) {
    active_test_name = tests_pulldown_entries.includes(matched_link)
      ? matched_link.dataset.view
      : STRIP_PULLDOWN_MERGED_TEST_NAME;
    if (tests_pulldown) tests_pulldown.closed_text_set(active_test_name);
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
      );
      return;
    }
    const [view_key, inner_hash] = parsed_hash;
    const active_link = matched_link || view_links[0];
    for (const link_element of view_links) {
      link_element.classList.toggle("on", link_element === active_link);
    }
    title_publish(active_link.dataset.title);
    active_test_show(matched_link);
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
  // The links the files or functions pulldown offers: each name of its kind
  // the active test's heat map opens, there, on the counter on show.
  function heat_map_entries_of(names_key, state_field) {
    const shipped_names = window.report_pulldown_names;
    if (
      !shipped_names ||
      !Object.prototype.hasOwnProperty.call(shipped_names, active_test_name)
    )
      throw new Error("str_error_pulldown_names_missing " + active_test_name);
    const counter_key = shown_counter_key();
    return shipped_names[active_test_name][names_key].map((name) => {
      const heat_map_hash = window.report_ui.heat_map_address.hash_of_state({
        [state_field]: name,
        ev: counter_key,
      });
      const entry_hash = hash_build(
        active_test_name,
        hash_build(HEAT_MAP_VIEW_KEY, heat_map_hash),
      );
      const entry_link = document.createElement("a");
      entry_link.setAttribute("href", entry_hash);
      entry_link.tabIndex = -1;
      entry_link.textContent = name;
      return entry_link;
    });
  }
  // Typing on the page reaches the tests pulldown from the overview's home,
  // or on top from a framed summary's home. A lone summary has none.
  function typing_reaches_tests_pulldown() {
    if (is_framed) return !home_panel.hidden;
    return !!tests_pulldown && (!home_panel.hidden || !current_inner_hash);
  }
  // A key for the tests pulldown, typed here or forwarded up by a framed
  // summary, which forwards it on. True when the key is taken.
  function tests_key_take(key_name) {
    if (!is_framed) return tests_pulldown.key_take(key_name, false);
    const is_command_key = window.report_ui.pulldown.key_is_command(key_name);
    if (is_command_key && !tests_pulldown_is_open) return false;
    if (!is_command_key) tests_pulldown_is_open = true;
    window.report_ui.parent_post({
      report_ui: "tests_pulldown_key_pressed",
      key: key_name,
    });
    return true;
  }
  function pulldowns_activate() {
    tests_pulldown = window.report_ui.pulldown.attach(
      tests_pulldown_root,
      TESTS_LABEL_TEXT,
      () => tests_pulldown_entries,
      () => {
        if (current_page_href)
          view_frame.contentWindow.postMessage(
            "report_ui:tests_pulldown_closed",
            "*",
          );
      },
    );
    window.report_ui.pulldown.attach(
      files_pulldown_root,
      FILES_LABEL_TEXT,
      () => heat_map_entries_of("files", "file"),
      () => {},
    );
    window.report_ui.pulldown.attach(
      functions_pulldown_root,
      FUNCTIONS_LABEL_TEXT,
      () => heat_map_entries_of("functions", "fn"),
      () => {},
    );
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
    const view_key = link_element.dataset.view;
    const target_hash =
      view_key != null
        ? hash_build(view_key, view_home_hash(view_key))
        : hash_for_href(link_href);
    if (target_hash == null) return;
    click_event.preventDefault();
    if (target_hash === (location.hash || "")) view_show(target_hash);
    else location.hash = target_hash;
  });
  // a key typed in a pulldown's own box is that pulldown's, taken before this
  document.addEventListener("keydown", (key_event) => {
    const key_name = window.report_ui.pulldown.key_of(key_event);
    if (!key_name || key_event.target.closest("input, select, textarea"))
      return;
    if (!typing_reaches_tests_pulldown()) return;
    if (tests_key_take(key_name)) key_event.preventDefault();
  });
  window.addEventListener("message", (message_event) => {
    if (
      message_event.source !== view_frame.contentWindow ||
      !message_event.data
    )
      return;
    const message_tag = message_event.data.report_ui;
    if (message_tag === "title_changed")
      title_publish(message_event.data.title);
    else if (message_tag === "scale_changed")
      scale_apply(Number(message_event.data.travel));
    else if (message_tag === "tests_pulldown_key_pressed")
      tests_key_take(message_event.data.key);
    else if (message_tag === "hash_changed") {
      if (!current_page_href) return;
      current_inner_hash = message_event.data.hash;
      window.report_ui.hash_publish(
        hash_build(hash_parse(location.hash)[0], current_inner_hash),
      );
    }
    // report_error is error_overlay.js's own tag on this same channel
    else if (message_tag !== undefined && message_tag !== "report_error")
      throw new Error("str_error_message_tag_unknown " + message_tag);
  });
  window.report_ui.parent_listen((message_data) => {
    if (message_data === "report_ui:title_request")
      title_publish(current_title);
    else if (message_data === "report_ui:layout_reset") reset_broadcast();
    else if (message_data === "report_ui:tests_pulldown_closed")
      tests_pulldown_is_open = false;
    else if (
      typeof message_data === "string" &&
      message_data.startsWith("report_ui:")
    )
      throw new Error("str_error_message_tag_unknown " + message_data);
  });
  window.addEventListener("hashchange", () => view_show(location.hash));
  if (tests_pulldown_root) pulldowns_activate();
  scale_activate();
  view_show(location.hash);
})();
