(function () {
  "use strict";

  const FLAME_GRAPH_VIEW_ENTRY = settings("FLAME_GRAPH_VIEW_ENTRY");
  const HEAT_MAP_VIEW_ENTRY = settings("HEAT_MAP_VIEW_ENTRY");
  const MENU_BUTTON_NUMBERS = settings("MENU_BUTTON_NUMBERS");
  const MENU_PULLDOWN_MERGED_TEST_NAME = settings(
    "MENU_PULLDOWN_MERGED_TEST_NAME",
  );
  const MENU_SCALE_KEY_NAMES = settings("MENU_SCALE_KEY_NAMES");
  const STYLE_MENU_LOGO_START_FRACTION = settings(
    "STYLE_MENU_LOGO_START_FRACTION",
  );

  const CALLERS_LABEL_TEXT = window.ui_strings.text_of("str_view_callers");
  const FLAME_GRAPH_VIEW_KEY = FLAME_GRAPH_VIEW_ENTRY[0];
  const HEAT_MAP_VIEW_KEY = HEAT_MAP_VIEW_ENTRY[0];
  const MENU_LOGO_LETTER_CLASS = "menu-logo-letter-";
  const REPORT_NAME_TEXT = window.ui_strings.text_of("str_report_name");
  const TITLE_PART_SEPARATOR = " / ";

  // what each numbered button says after its number, by the name in its id
  const BUTTON_LABEL_TEXTS = {
    callers: CALLERS_LABEL_TEXT,
    file: window.ui_strings.text_of("str_menu_file"),
    function: window.ui_strings.text_of("str_menu_function"),
    [HEAT_MAP_VIEW_KEY]: HEAT_MAP_VIEW_ENTRY[1],
    help: window.ui_strings.text_of("str_menu_help"),
    overview: window.ui_strings.text_of("str_menu_overview"),
    reset: window.ui_strings.text_of("str_menu_reset"),
    scale: window.ui_strings.text_of("str_menu_scale"),
    test: window.ui_strings.text_of("str_menu_test"),
  };
  // the glyphs of the scale bar's filled and empty cells
  const SCALE_BAR_TEXTS = {
    empty: window.ui_strings.text_of("str_menu_scale_bar_empty"),
    filled: window.ui_strings.text_of("str_menu_scale_bar_filled"),
  };
  // how many stops each scale key moves the bar by
  const SCALE_KEY_STEPS = {
    [MENU_SCALE_KEY_NAMES.larger]: 1,
    [MENU_SCALE_KEY_NAMES.smaller]: -1,
  };
  // what the title calls each view of a test, by its view key
  const VIEW_LABEL_TEXTS = {
    "": CALLERS_LABEL_TEXT,
    [FLAME_GRAPH_VIEW_KEY]: FLAME_GRAPH_VIEW_ENTRY[1],
    [HEAT_MAP_VIEW_KEY]: HEAT_MAP_VIEW_ENTRY[1],
  };

  const callers_button = document.getElementById("menu-callers-button-");
  const files_pulldown_root = document.getElementById("menu-file-pulldown-");
  const functions_pulldown_root = document.getElementById(
    "menu-function-pulldown-",
  );
  const heat_map_button = document.getElementById(
    `menu-${HEAT_MAP_VIEW_KEY}-button-`,
  );
  const home_panel = window.report_ui.home_panel;
  const home_title_text = document.title;
  const is_framed = window.report_frame.is_framed;
  const logo_cell = document.getElementById("menu-logo-");
  const menu_bar = document.getElementById("menu_");
  const overview_button = document.getElementById("menu-overview-button-");
  const reset_button = document.getElementById("menu-reset-button-");
  // the scale button's parts: its text either side of the bar, the bar's
  // start, then one span per stop past the first, which fills none
  const scale_bar_cells = Array.from(
    { length: window.report_ui.design_scale_last_stop },
    () => document.createElement("span"),
  );
  const scale_bar_lead = document.createTextNode("");
  const scale_bar_start = document.createElement("span");
  const scale_bar_trail = document.createTextNode("");
  const scale_button = document.getElementById("menu-scale-button-");
  // what a click on each sets the scale to: the start 0, cell k stop k
  const scale_stop_targets = [scale_bar_start, ...scale_bar_cells];
  const tests_pulldown_root = window.report_frame.tests_pulldown_root;
  const title_cell = document.getElementById("menu-title-");
  // every link frame.js opens a page's view by: the menu's view buttons,
  // the overview's tests and a callers page's flame graph link
  const view_links = [...document.querySelectorAll("a[data-view-]")];
  const tests_pulldown_entries = tests_pulldown_root
    ? [
        ...tests_pulldown_root.querySelectorAll(
          ".menu-pulldown-entry-list- a[data-view-]",
        ),
      ]
    : [];

  // Every page links report_complete.js, written just before MANIFEST.txt.
  // Shown before thrown: a throw alone reaches the overlay as Script error.
  if (typeof window.report_manifest_table === "undefined") {
    const incomplete_error = new Error(
      window.ui_strings.text_of("str_error_report_incomplete"),
    );
    window.report_error_overlay.overlay_show(incomplete_error);
    throw incomplete_error;
  }
  // the overview's pulldowns, the tests one among them; a callers page has
  // none
  let menu_pulldowns = [];
  let tests_pulldown = null;

  // The test every pulldown works in: the one on show, else the merged one.
  function active_test_name() {
    return (
      window.report_frame.address_now().test_name ||
      MENU_PULLDOWN_MERGED_TEST_NAME
    );
  }
  // The links the files or functions pulldown offers, one per name of its
  // kind, each opening that name, at any line, in the active test's heat map.
  function heat_map_entries_of(names_key, state_field, line_number) {
    const pulldown_text = window.report_pulldown_text;
    if (!pulldown_text)
      throw new Error(
        window.ui_strings.text_of("str_error_pulldown_text_missing"),
      );
    const entry_test_name = active_test_name();
    return pulldown_text[names_key].map((name) => {
      const entry_link = document.createElement("a");
      entry_link.setAttribute(
        "href",
        window.report_frame.heat_map_entry_hash(
          entry_test_name,
          state_field,
          name,
          line_number,
        ),
      );
      entry_link.tabIndex = -1;
      entry_link.textContent = name;
      return entry_link;
    });
  }
  // Activate a numbered button as a click does, the scale button taking only
  // the focus its keys work from. A button this page lacks takes no key.
  function button_activate(button_name) {
    const button_element = document.getElementById(
      `menu-${button_name}-button-`,
    );
    if (!button_element) return false;
    if (button_element === scale_button) scale_button.focus();
    else button_element.click();
    return true;
  }
  // A key typed on the top page or sent up to it: an open pulldown's, else
  // a digit activates its button and a letter opens the tests pulldown.
  function menu_key_take(key_name) {
    const open_pulldown = menu_pulldowns.find((candidate_pulldown) =>
      candidate_pulldown.is_open(),
    );
    if (open_pulldown) return open_pulldown.key_take(key_name, false);
    const button_name = window.report_ui.menu_key.button_name(key_name);
    if (button_name) return button_activate(button_name);
    return (
      !!tests_pulldown &&
      window.report_ui.menu_key.opens_tests_pulldown(key_name) &&
      tests_pulldown.key_take(key_name, false)
    );
  }
  // A numbered button's text: its number, then its label.
  function button_text_of(button_name) {
    return window.ui_strings.text_fill("str_menu_button", {
      number: MENU_BUTTON_NUMBERS[button_name],
      label: BUTTON_LABEL_TEXTS[button_name],
    });
  }
  // Write each numbered button's text. A callers page draws no pulldowns.
  function buttons_label() {
    for (const button_name of Object.keys(MENU_BUTTON_NUMBERS)) {
      const button_element = document.getElementById(
        `menu-${button_name}-button-`,
      );
      if (button_element)
        button_element.textContent = button_text_of(button_name);
    }
  }
  // The file pulldown alone reads a line off its search text, foo.c:3.
  function pulldowns_activate() {
    tests_pulldown = window.report_ui.pulldown.attach(
      tests_pulldown_root,
      button_text_of("test"),
      () => tests_pulldown_entries,
      window.report_frame.tests_pulldown_closed_notify,
      false,
    );
    menu_pulldowns = [
      tests_pulldown,
      window.report_ui.pulldown.attach(
        files_pulldown_root,
        button_text_of("file"),
        (line_number) => heat_map_entries_of("files", "file", line_number),
        () => {},
        true,
      ),
      window.report_ui.pulldown.attach(
        functions_pulldown_root,
        button_text_of("function"),
        () => heat_map_entries_of("functions", "fn", 0),
        () => {},
        false,
      ),
    ];
  }

  // One part of the title: a link reading as that part of the address and
  // opening where it leads. An empty address is "#", as "" reloads the page.
  function title_link_of(part_text, part_hash) {
    const part_link = document.createElement("a");
    part_link.setAttribute("href", part_hash || "#");
    part_link.textContent = part_text;
    return part_link;
  }
  // The title's last part, the file or function a heat map opens: a click
  // puts it back where its address first opened it, opening nothing new.
  function recenter_link_of(part_text) {
    const recenter_link = title_link_of(part_text, location.hash);
    recenter_link.addEventListener("click", (click_event) => {
      click_event.preventDefault();
      window.report_frame.recenter_broadcast();
    });
    return recenter_link;
  }
  // What the title calls what a heat map opens: the function, or the file's
  // base name and any line. Nothing at the heat map's home.
  function heat_map_part_text(heat_map_state) {
    if (heat_map_state.fn) return heat_map_state.fn;
    if (!heat_map_state.file) return "";
    const base_name = heat_map_state.file.split("/").pop();
    return heat_map_state.line
      ? base_name + ":" + heat_map_state.line
      : base_name;
  }
  // The title's parts for a test's address: the test and the view, each a
  // link to its home, then on a heat map what that heat map opens.
  function title_links_of(address) {
    const part_links = [
      title_link_of(
        address.test_name,
        window.report_frame.view_address_hash(address.test_name, ""),
      ),
      title_link_of(
        VIEW_LABEL_TEXTS[address.view_key],
        window.report_frame.view_address_hash(
          address.test_name,
          address.view_key,
        ),
      ),
    ];
    const heat_map_text = address.heat_map_state
      ? heat_map_part_text(address.heat_map_state)
      : "";
    if (heat_map_text) part_links.push(recenter_link_of(heat_map_text));
    return part_links;
  }
  // Mark the button of the view on show, and on the overview point the heat
  // map and callers buttons at the test on show, else at the merged one.
  function buttons_follow(address) {
    const is_test_shown = !!address.test_name;
    overview_button.classList.toggle("current_", !is_test_shown);
    heat_map_button.classList.toggle(
      "current_",
      is_test_shown && address.view_key === HEAT_MAP_VIEW_KEY,
    );
    callers_button.classList.toggle(
      "current_",
      is_test_shown && !address.view_key,
    );
    for (const entry_link of tests_pulldown_entries) {
      entry_link.classList.toggle(
        "current_",
        entry_link.getAttribute("data-view-") === address.test_name,
      );
    }
    if (!tests_pulldown_root) return;
    const button_test_name =
      address.test_name || MENU_PULLDOWN_MERGED_TEST_NAME;
    heat_map_button.setAttribute(
      "href",
      window.report_frame.view_address_hash(
        button_test_name,
        HEAT_MAP_VIEW_KEY,
      ),
    );
    callers_button.setAttribute(
      "href",
      window.report_frame.view_address_hash(button_test_name, ""),
    );
  }
  // Describe the address on show: the title, each part a link to where it
  // leads, the tab's title, and the buttons following the test on show.
  function address_show() {
    if (is_framed) return;
    const address = window.report_frame.address_now();
    const part_links = address.test_name ? title_links_of(address) : [];
    const part_texts = part_links.map((part_link) => part_link.textContent);
    const title_nodes = [];
    for (const part_link of part_links) {
      if (title_nodes.length) title_nodes.push(TITLE_PART_SEPARATOR);
      title_nodes.push(part_link);
    }
    title_cell.replaceChildren(...title_nodes);
    // the overview's home has no address to describe: its page title stands
    document.title = part_texts.join(TITLE_PART_SEPARATOR) || home_title_text;
    buttons_follow(address);
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
  // Draw the scale bar at a stop: a filled cell for each stop up to it,
  // then the multiple it zooms the main page contents by.
  function scale_bar_show(travel_stop) {
    scale_bar_cells.forEach((cell_span, cell_index) => {
      cell_span.textContent =
        cell_index < travel_stop
          ? SCALE_BAR_TEXTS.filled
          : SCALE_BAR_TEXTS.empty;
    });
    scale_bar_trail.textContent = window.ui_strings.text_fill(
      "str_menu_scale_bar_end",
      { multiple: window.report_ui.design_scale_multiple_text(travel_stop) },
    );
  }
  // Move the scale to a stop. The stop already on show changes nothing, so
  // no column loses the width it was slid to.
  function scale_stop_request(travel_stop) {
    if (travel_stop === window.report_ui.design_scale_travel_now()) return;
    window.report_frame.scale_apply(travel_stop);
    scale_bar_show(travel_stop);
  }
  function scale_activate() {
    scale_bar_lead.textContent = window.ui_strings.text_fill(
      "str_menu_scale_bar_lead",
      { button: button_text_of("scale") },
    );
    scale_bar_start.textContent = window.ui_strings.text_of(
      "str_menu_scale_bar_start",
    );
    scale_button.replaceChildren(
      scale_bar_lead,
      ...scale_stop_targets,
      scale_bar_trail,
    );
    scale_bar_show(window.report_ui.design_scale_travel_now());
    // a click on the bar's start or a cell moves it there; anywhere else on
    // the button only takes the focus the scale keys work from
    scale_button.addEventListener("click", (click_event) => {
      scale_button.focus();
      const clicked_stop = scale_stop_targets.indexOf(click_event.target);
      if (clicked_stop >= 0) scale_stop_request(clicked_stop);
    });
    // a key held with a modifier stays the browser's: Alt+Left is back
    scale_button.addEventListener("keydown", (key_event) => {
      const stop_step = SCALE_KEY_STEPS[key_event.key];
      if (
        !stop_step ||
        key_event.altKey ||
        key_event.ctrlKey ||
        key_event.metaKey
      )
        return;
      key_event.preventDefault();
      const wanted_stop =
        window.report_ui.design_scale_travel_now() + stop_step;
      // a step past either end of the bar has no stop to move to
      if (scale_stop_targets[wanted_stop]) scale_stop_request(wanted_stop);
    });
  }

  function activate() {
    // a framed callers page draws no menu: the top page's controls it
    menu_bar.hidden = is_framed;
    if (is_framed) return;
    logo_cell.replaceChildren(
      ...window.report_ui.logo_letters_build(
        REPORT_NAME_TEXT,
        MENU_LOGO_LETTER_CLASS,
        STYLE_MENU_LOGO_START_FRACTION,
      ),
    );
    logo_cell.addEventListener("click", () =>
      location.assign(logo_cell.getAttribute("data-root-href-")),
    );
    reset_button.addEventListener("click", () =>
      window.report_frame.reset_broadcast(),
    );
    buttons_label();
    if (tests_pulldown_root) pulldowns_activate();
    scale_activate();
  }

  window.report_menu = {
    address_show,
    home_panel_hide,
    home_panel_reset,
    home_panel_show,
    menu_key_take,
    view_links,
  };

  activate();
  window.report_frame.activate();
})();
