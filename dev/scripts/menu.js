(function () {
  "use strict";

  const STRIP_PULLDOWN_MERGED_TEST_NAME = settings(
    "STRIP_PULLDOWN_MERGED_TEST_NAME",
  );
  const HOME_VIEW_LABEL = window.ui_strings.text_of("str_view_summary");
  const LOGO_LETTER_CLASS = "logo-letter";
  const LOGO_START_FRACTION = settings("LOGO_START_FRACTION");
  const OUTER_STATUS_TEXT = window.ui_strings.text_of("str_report_name");
  const SCALE_LABEL_TEXT = window.ui_strings.text_of("str_control_view_scale");
  const SELECTION_SEPARATOR = " / ";

  const FILES_LABEL_TEXT = window.ui_strings.text_of("str_control_files");
  const FUNCTIONS_LABEL_TEXT = window.ui_strings.text_of(
    "str_control_functions",
  );
  const TESTS_LABEL_TEXT = window.ui_strings.text_of("str_control_tests");

  const files_pulldown_root = document.getElementById("files-pulldown");
  const functions_pulldown_root = document.getElementById(
    "functions-pulldown",
  );
  const home_panel = document.getElementById("home");
  const is_framed = window.report_frame.is_framed;
  const layout_reset_link = document.getElementById("layout-reset");
  const logo_letters = window.report_ui.logo_letters_build(
    OUTER_STATUS_TEXT,
    LOGO_LETTER_CLASS,
    LOGO_START_FRACTION,
  );
  const scale_label = document.getElementById("scale-label");
  const scale_slider = document.getElementById("scale-slider");
  const scale_text = document.getElementById("scale-text");
  const strip_bar = document.getElementById("strip_bar");
  const tests_pulldown_root = window.report_frame.tests_pulldown_root;
  const title_badge = document.getElementById("title");
  const utility_block = document.getElementById("utility_links");
  const view_links = [...strip_bar.querySelectorAll("a[data-view]")];
  const tests_pulldown_entries = tests_pulldown_root
    ? [...tests_pulldown_root.querySelectorAll(".pulldown-list a[data-view]")]
    : [];

  let current_title = title_badge.textContent;
  // Only the overview has pulldowns. report_complete.js is written second
  // to last, right before MANIFEST.txt: missing it, the report never finished
  if (
    tests_pulldown_root &&
    typeof window.report_manifest_table === "undefined"
  ) {
    window.report_error_overlay.overlay_show(
      window.ui_strings.text_of("str_error_report_incomplete"),
    );
    return;
  }
  let active_test_name = STRIP_PULLDOWN_MERGED_TEST_NAME,
    tests_pulldown = null;
  // On a framed summary, the top page's tests pulldown: open from the first
  // character forwarded up until report_ui:tests_pulldown_closed comes down.
  let tests_pulldown_is_open = false;

  // The test every pulldown works in: the framed one, else the merged one.
  // The open tests list shows it as the one differently coloured entry.
  function active_test_show(matched_link) {
    active_test_name = tests_pulldown_entries.includes(matched_link)
      ? matched_link.dataset.view
      : STRIP_PULLDOWN_MERGED_TEST_NAME;
  }
  // The links the files or functions pulldown offers: each name of its kind
  // the active test's heat map opens, there, on the counter on show.
  function heat_map_entries_of(names_key, state_field) {
    const shipped_names = window.report_pulldown_names;
    if (
      !shipped_names ||
      !Object.prototype.hasOwnProperty.call(shipped_names, active_test_name)
    )
      throw new Error(
        window.ui_strings.text_fill("str_error_pulldown_names_missing", [
          active_test_name,
        ]),
      );
    return shipped_names[active_test_name][names_key].map((name) => {
      const entry_link = document.createElement("a");
      entry_link.setAttribute(
        "href",
        window.report_frame.heat_map_entry_hash(
          active_test_name,
          state_field,
          name,
        ),
      );
      entry_link.tabIndex = -1;
      entry_link.textContent = name;
      return entry_link;
    });
  }
  // Typing on the page reaches the tests pulldown from the overview's home,
  // or on top from a framed summary's home. A lone summary has none.
  function typing_reaches_tests_pulldown() {
    if (is_framed) return !home_panel.hidden;
    return (
      !!tests_pulldown &&
      (!home_panel.hidden || !window.report_frame.current_inner_hash())
    );
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
  function tests_pulldown_closed() {
    tests_pulldown_is_open = false;
  }
  function pulldowns_activate() {
    tests_pulldown = window.report_ui.pulldown.attach(
      tests_pulldown_root,
      TESTS_LABEL_TEXT,
      () => tests_pulldown_entries,
      window.report_frame.tests_pulldown_closed_notify,
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

  function selection_path(new_title) {
    return new_title && !new_title.includes(SELECTION_SEPARATOR)
      ? new_title + SELECTION_SEPARATOR + HOME_VIEW_LABEL
      : new_title;
  }
  function title_publish(new_title) {
    current_title = new_title;
    if (is_framed) title_badge.textContent = selection_path(new_title);
    else title_badge.replaceChildren(...logo_letters);
    document.title = new_title;
    window.report_ui.parent_post({
      report_ui: "title_changed",
      title: new_title,
    });
  }
  function title_publish_current() {
    title_publish(current_title);
  }
  function view_links_activate(active_link) {
    for (const link_element of view_links) {
      link_element.classList.toggle("on", link_element === active_link);
    }
  }
  function utility_visibility_set(utility_shown) {
    utility_block.hidden = !utility_shown;
    scale_label.hidden = utility_block.hidden;
  }
  function home_panel_show() {
    home_panel.hidden = false;
    window.report_ui.layout_refresh(home_panel);
  }
  function home_panel_hide() {
    home_panel.hidden = true;
  }
  function home_panel_reset() {
    window.report_ui.layout_reset(home_panel);
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
      window.report_frame.scale_apply(Number(scale_slider.value));
    });
  }

  function activate() {
    layout_reset_link.addEventListener("click", (pointer_event) => {
      pointer_event.preventDefault();
      window.report_frame.reset_broadcast();
    });
    if (!is_framed) {
      title_badge.addEventListener("click", () =>
        location.assign(title_badge.dataset.rootHref),
      );
    }
    if (tests_pulldown_root) pulldowns_activate();
    scale_activate();
  }

  window.report_menu = {
    active_test_show,
    home_panel_hide,
    home_panel_reset,
    home_panel_show,
    layout_reset_link,
    tests_key_take,
    tests_pulldown_closed,
    title_publish,
    title_publish_current,
    typing_reaches_tests_pulldown,
    utility_visibility_set,
    view_links,
    view_links_activate,
  };

  activate();
  window.report_frame.activate();
})();
