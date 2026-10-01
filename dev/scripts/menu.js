window.catch_show_throw(function () {
  "use strict";

  const CALLERS_VIEW_KEY = settings("CALLERS_VIEW_KEY");
  const FLAME_GRAPH_VIEW_ENTRY = settings("FLAME_GRAPH_VIEW_ENTRY");
  const HEAT_MAP_VIEW_ENTRY = settings("HEAT_MAP_VIEW_ENTRY");
  const MENU_BUTTON_ORDER = settings("MENU_BUTTON_ORDER");
  const MENU_PULLDOWN_KEY_NAMES = settings("MENU_PULLDOWN_KEY_NAMES");
  const MENU_PULLDOWN_LINE_NUMBER_PATTERN = settings(
    "MENU_PULLDOWN_LINE_NUMBER_PATTERN",
  );
  const MENU_PULLDOWN_MERGED_TEST_NAME = settings(
    "MENU_PULLDOWN_MERGED_TEST_NAME",
  );
  const MENU_SCALE_KEY_NAMES = settings("MENU_SCALE_KEY_NAMES");
  const STYLE_MENU_LOGO_START_FRACTION = settings(
    "STYLE_MENU_LOGO_START_FRACTION",
  );

  const CALLERS_LABEL_TEXT = window.ui_strings.text_of("str_view_callers");
  // how many numbered buttons the digit keys reach: 1 to 9, then 0
  const DIGIT_KEY_COUNT = 10;
  const FLAME_GRAPH_VIEW_KEY = FLAME_GRAPH_VIEW_ENTRY[0];
  const HEAT_MAP_VIEW_KEY = HEAT_MAP_VIEW_ENTRY[0];
  const MENU_LOGO_LETTER_CLASS = "menu-logo-letter-";
  const PULLDOWN_HIGHLIGHTED_ENTRY_CLASS = "highlighted-entry-";
  const REPORT_NAME_TEXT = window.ui_strings.text_of("str_report_name");
  const TITLE_PART_SEPARATOR = " / ";

  // what each numbered button says after its number, by the name in its id
  const BUTTON_LABEL_TEXTS = {
    [CALLERS_VIEW_KEY]: CALLERS_LABEL_TEXT,
    file: window.ui_strings.text_of("str_menu_file"),
    [FLAME_GRAPH_VIEW_KEY]: FLAME_GRAPH_VIEW_ENTRY[1],
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
    [CALLERS_VIEW_KEY]: CALLERS_LABEL_TEXT,
    [FLAME_GRAPH_VIEW_KEY]: FLAME_GRAPH_VIEW_ENTRY[1],
    [HEAT_MAP_VIEW_KEY]: HEAT_MAP_VIEW_ENTRY[1],
  };

  const files_pulldown_root = document.getElementById("menu-file-pulldown-");
  // the flame graph's button, which a diff lacks
  const flame_graph_button = document.getElementById(
    `menu-${FLAME_GRAPH_VIEW_KEY}-button-`,
  );
  const functions_pulldown_root = document.getElementById(
    "menu-function-pulldown-",
  );
  const home_title_text = document.title;
  const logo_link = document.getElementById("menu-logo-");
  const menu_strip = document.getElementById("menu_");
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
  const tests_pulldown_root = document.getElementById("menu-test-pulldown-");
  const tests_pulldown_entries = [
    ...tests_pulldown_root.querySelectorAll(
      ".menu-pulldown-entry-list- a[data-test-name-]",
    ),
  ];
  const title_cell = document.getElementById("menu-title-");
  // each view's button by its view key, the flame graph's null on a diff
  const view_buttons = {
    [CALLERS_VIEW_KEY]: document.getElementById(
      `menu-${CALLERS_VIEW_KEY}-button-`,
    ),
    [FLAME_GRAPH_VIEW_KEY]: flame_graph_button,
    [HEAT_MAP_VIEW_KEY]: document.getElementById(
      `menu-${HEAT_MAP_VIEW_KEY}-button-`,
    ),
  };

  // Every page links report_complete.js, written just before MANIFEST.txt.
  if (typeof window.report_manifest_table === "undefined")
    throw new Error(window.ui_strings.text_of("str_error_report_incomplete"));
  // the overview's pulldowns, the tests one among them
  let menu_pulldowns = [];
  let tests_pulldown = null;

  // The search box's text as a pattern. One that does not compile yet, a
  // lone "(" mid-typing, is null and matches nothing. Any other error throws.
  function pulldown_pattern_of(search_text) {
    try {
      return new RegExp(search_text, "i");
    } catch (pattern_error) {
      if (!(pattern_error instanceof SyntaxError)) throw pattern_error;
      return null;
    }
  }
  // A menu pulldown over root_element's parts. entries_of(line_number) gives
  // the links offered, opening at that line, on_close() running on each close.
  function pulldown_attach(
    root_element,
    label_text,
    entries_of,
    on_close,
    reads_line_number,
  ) {
    const entry_list = root_element.querySelector(
      ".menu-pulldown-entry-list-",
    );
    const menu_button = root_element.querySelector(".menu-pulldown-button-");
    const no_match_note = root_element.querySelector(
      ".menu-pulldown-no-match-note-",
    );
    const search_box = root_element.querySelector(
      ".menu-pulldown-search-box-",
    );
    let entries = [],
      entries_line_number = 0,
      highlight_index = 0,
      is_open = false,
      matches = [];

    function highlight_set(entry_index) {
      highlight_index = entry_index;
      for (const entry_link of entries) {
        entry_link.classList.toggle(
          PULLDOWN_HIGHLIGHTED_ENTRY_CLASS,
          entry_link === matches[highlight_index],
        );
      }
    }
    function highlight_step(step_count) {
      if (!matches.length) return;
      highlight_set(
        Math.min(
          Math.max(highlight_index + step_count, 0),
          matches.length - 1,
        ),
      );
      matches[highlight_index].scrollIntoView({ block: "nearest" });
    }
    // The search box's text as the pattern to filter by and the line its
    // entries open at, 0 for none. Only a pulldown reading lines splits one.
    function search_parts_of(search_text) {
      const line_pattern = new RegExp(MENU_PULLDOWN_LINE_NUMBER_PATTERN);
      const line_match = reads_line_number && line_pattern.exec(search_text);
      return line_match ? [line_match[1], +line_match[2]] : [search_text, 0];
    }
    // Offer the links opening at a line, 0 for none, in place of any before.
    function entries_offer(line_number) {
      entries_line_number = line_number;
      entries = entries_of(line_number);
      entry_list.replaceChildren(...entries, no_match_note);
    }
    function entries_filter() {
      const [filter_text, line_number] = search_parts_of(search_box.value);
      if (line_number !== entries_line_number) entries_offer(line_number);
      const search_pattern = pulldown_pattern_of(filter_text);
      matches = entries.filter(
        (entry_link) =>
          !!search_pattern && search_pattern.test(entry_link.textContent),
      );
      const matched_entries = new Set(matches);
      for (const entry_link of entries) {
        entry_link.hidden = !matched_entries.has(entry_link);
      }
      no_match_note.hidden = matches.length > 0;
      entry_list.scrollTop = 0;
      highlight_set(0);
    }
    // Focus the search box, out of a framed page if focus is there. A key's
    // user activation reaches the top page. A refusal would strand the keys.
    function search_box_focus() {
      search_box.focus();
      if (document.activeElement !== search_box)
        throw new Error(
          window.ui_strings.text_fill("str_error_pulldown_focus_refused", [
            document.activeElement.tagName.toLowerCase(),
          ]),
        );
    }
    // The search box takes the button's place while open, the list
    // dropping below the box, so the list sits aligned under the button.
    function pulldown_open(search_text) {
      is_open = true;
      entries_offer(search_parts_of(search_text)[1]);
      menu_button.hidden = true;
      search_box.hidden = false;
      search_box.value = search_text;
      entry_list.hidden = false;
      entries_filter();
      search_box_focus();
    }
    function closed_show() {
      is_open = false;
      search_box.hidden = true;
      search_box.value = "";
      menu_button.hidden = false;
      entry_list.hidden = true;
    }
    function pulldown_close() {
      closed_show();
      on_close();
    }
    // The one key handler, for a key typed in the box or handed over from
    // elsewhere on the page. True when the key is taken.
    function key_take(key_name, is_in_search_box) {
      const is_command_key =
        window.report_ui.pulldown_key.is_command(key_name);
      if (!is_open) {
        if (is_command_key) return false;
        pulldown_open(key_name);
        return true;
      }
      switch (key_name) {
        case MENU_PULLDOWN_KEY_NAMES.close:
          pulldown_close();
          return true;
        case MENU_PULLDOWN_KEY_NAMES.next:
          highlight_step(1);
          return true;
        case MENU_PULLDOWN_KEY_NAMES.previous:
          highlight_step(-1);
          return true;
        case MENU_PULLDOWN_KEY_NAMES.select:
          if (matches.length) matches[highlight_index].click();
          return true;
      }
      // the focused open box types for itself; a key from elsewhere is added
      if (is_in_search_box) return false;
      search_box.value += key_name;
      entries_filter();
      search_box_focus();
      return true;
    }

    menu_button.textContent = label_text;
    search_box.placeholder = window.ui_strings.text_of(
      "str_pulldown_placeholder",
    );
    no_match_note.textContent = window.ui_strings.text_of("str_no_match");
    for (const pointer_target of [menu_button, entry_list]) {
      pointer_target.addEventListener(
        "mousedown",
        window.catch_show_throw((pointer_event) =>
          pointer_event.preventDefault(),
        ),
      );
    }
    menu_button.addEventListener(
      "click",
      window.catch_show_throw(() => pulldown_open("")),
    );
    search_box.addEventListener(
      "blur",
      window.catch_show_throw(() => {
        if (is_open) pulldown_close();
      }),
    );
    search_box.addEventListener(
      "input",
      window.catch_show_throw(entries_filter),
    );
    search_box.addEventListener(
      "keydown",
      window.catch_show_throw((key_event) => {
        const key_name = window.report_ui.pulldown_key.of(key_event);
        if (key_name && key_take(key_name, true)) key_event.preventDefault();
      }),
    );
    entry_list.addEventListener(
      "click",
      window.catch_show_throw((click_event) => {
        if (!click_event.target.closest("a")) return;
        pulldown_close();
        search_box.blur();
      }),
    );
    closed_show();
    return { is_open: () => is_open, key_take };
  }

  // The test every pulldown works in: the one on show, else the merged one.
  function active_test_name() {
    return (
      window.report_frame.address_now().test ?? MENU_PULLDOWN_MERGED_TEST_NAME
    );
  }
  // The links the files or functions pulldown offers, one per name of its
  // kind, each the active test's heat map at the part part_of(name) names.
  function heat_map_entries_of(names_key, part_of) {
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
        window.report_ui.address.hash_of({
          test: entry_test_name,
          view: HEAT_MAP_VIEW_KEY,
          ...part_of(name),
        }),
      );
      entry_link.tabIndex = -1;
      entry_link.textContent = name;
      return entry_link;
    });
  }
  // Activate a numbered button as a click does, the scale button taking only
  // the focus its keys work from. A button absent or hidden takes no key.
  function button_activate(button_name) {
    const button_element = document.getElementById(
      `menu-${button_name}-button-`,
    );
    if (!button_element || button_element.hidden) return false;
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
    const button_name = menu_key_button_name(key_name);
    if (button_name) return button_activate(button_name);
    return (
      window.report_ui.view_key.opens_tests_pulldown(key_name) &&
      tests_pulldown.key_take(key_name, false)
    );
  }
  // A numbered button's number and key, its place in MENU_BUTTON_ORDER from
  // 1, the tenth 0, whether or not this report has the button.
  function button_number_of(button_name) {
    return (MENU_BUTTON_ORDER.indexOf(button_name) + 1) % DIGIT_KEY_COUNT;
  }
  // The numbered button a key activates, by the name in its id, or "".
  function menu_key_button_name(key_name) {
    return (
      MENU_BUTTON_ORDER.find(
        (button_name) => String(button_number_of(button_name)) === key_name,
      ) ?? ""
    );
  }
  // A numbered button's text: its number, then its label.
  function button_text_of(button_name) {
    if (!Object.prototype.hasOwnProperty.call(BUTTON_LABEL_TEXTS, button_name))
      throw new Error(
        window.ui_strings.text_fill("str_error_menu_button_unlabelled", [
          button_name,
        ]),
      );
    return window.ui_strings.text_fill("str_menu_button", {
      number: button_number_of(button_name),
      label: BUTTON_LABEL_TEXTS[button_name],
    });
  }
  // Write each numbered button's text. Past the digit keys two buttons would
  // share a key, and a name with no label would read as none.
  function buttons_label() {
    if (MENU_BUTTON_ORDER.length > DIGIT_KEY_COUNT)
      throw new Error(
        window.ui_strings.text_fill("str_error_menu_button_order_long", [
          MENU_BUTTON_ORDER.length,
          DIGIT_KEY_COUNT,
        ]),
      );
    for (const button_name of MENU_BUTTON_ORDER) {
      const button_text = button_text_of(button_name);
      const button_element = document.getElementById(
        `menu-${button_name}-button-`,
      );
      if (button_element) button_element.textContent = button_text;
    }
  }
  // The file pulldown alone reads a line off its search text, foo.c:3.
  function pulldowns_activate() {
    tests_pulldown = pulldown_attach(
      tests_pulldown_root,
      button_text_of("test"),
      () => tests_pulldown_entries,
      () => window.report_frame.view_post("report_ui:tests_pulldown_closed"),
      false,
    );
    menu_pulldowns = [
      tests_pulldown,
      pulldown_attach(
        files_pulldown_root,
        button_text_of("file"),
        (line_number) =>
          heat_map_entries_of("files", (file_name) => ({
            file: file_name,
            line: line_number || null,
          })),
        () => {},
        true,
      ),
      pulldown_attach(
        functions_pulldown_root,
        button_text_of("function"),
        () =>
          heat_map_entries_of("functions", (function_name) => ({
            function: function_name,
          })),
        () => {},
        false,
      ),
    ];
  }

  // One part of the title: a link reading as that part of the address and
  // opening where that part leads.
  function title_link_of(part_text, part_hash) {
    const part_link = document.createElement("a");
    part_link.setAttribute("href", part_hash);
    part_link.textContent = part_text;
    return part_link;
  }
  // The title's last part, the file or function a heat map opens: a click
  // puts it back where its address first opened it, opening nothing new.
  function recenter_link_of(part_text) {
    const recenter_link = title_link_of(
      part_text,
      window.report_ui.address.hash_of(window.report_frame.address_now()),
    );
    recenter_link.addEventListener(
      "click",
      window.catch_show_throw((click_event) => {
        click_event.preventDefault();
        window.report_frame.view_post("report_ui:recenter");
      }),
    );
    return recenter_link;
  }
  // What the title calls what a heat map opens: the function, or the file's
  // base name and any line. Nothing at the heat map's home.
  function heat_map_part_text(address) {
    if (address.function !== null) return address.function;
    if (address.file === null) return "";
    const base_name = address.file.split("/").pop();
    return address.line !== null ? base_name + ":" + address.line : base_name;
  }
  // The title's parts for a test's address: the test and the view, each a
  // link to its home, then on a heat map what that heat map opens.
  function title_links_of(address) {
    const part_links = [
      title_link_of(
        address.test,
        window.report_ui.address.home_hash_of(address.test, CALLERS_VIEW_KEY),
      ),
      title_link_of(
        VIEW_LABEL_TEXTS[address.view],
        window.report_ui.address.home_hash_of(address.test, address.view),
      ),
    ];
    const heat_map_text =
      address.view === HEAT_MAP_VIEW_KEY ? heat_map_part_text(address) : "";
    if (heat_map_text) part_links.push(recenter_link_of(heat_map_text));
    return part_links;
  }
  // Mark the button of the view on show and point each view button at the
  // test on show, else the merged one, which has no flame graph.
  function buttons_follow(address) {
    const button_test_name = address.test ?? MENU_PULLDOWN_MERGED_TEST_NAME;
    overview_button.classList.toggle("current_", address.view === null);
    for (const [view_key, view_button] of Object.entries(view_buttons)) {
      // a diff has no flame graph button
      if (!view_button) continue;
      view_button.classList.toggle("current_", address.view === view_key);
      view_button.setAttribute(
        "href",
        window.report_ui.address.home_hash_of(button_test_name, view_key),
      );
    }
    if (flame_graph_button)
      flame_graph_button.hidden =
        button_test_name === MENU_PULLDOWN_MERGED_TEST_NAME;
    for (const entry_link of tests_pulldown_entries) {
      entry_link.classList.toggle(
        "current_",
        entry_link.getAttribute("data-test-name-") === address.test,
      );
    }
  }
  // Describe the address on show: the title, each part a link to where it
  // leads, the tab's title, and the buttons following the test on show.
  function address_show() {
    const address = window.report_frame.address_now();
    const part_links = address.test !== null ? title_links_of(address) : [];
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
  // Move the scale to a stop, every column put back after it. The stop on
  // show changes nothing, so no slid column loses its width.
  function scale_stop_request(travel_stop) {
    if (travel_stop === window.report_ui.design_scale_travel_now()) return;
    window.report_ui.design_scale_travel_set(travel_stop);
    window.report_frame.view_post("report_ui:layout_reset");
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
    scale_button.addEventListener(
      "click",
      window.catch_show_throw((click_event) => {
        scale_button.focus();
        const clicked_stop = scale_stop_targets.indexOf(click_event.target);
        if (clicked_stop >= 0) scale_stop_request(clicked_stop);
      }),
    );
    // a key held with a modifier stays the browser's: Alt+Left is back
    scale_button.addEventListener(
      "keydown",
      window.catch_show_throw((key_event) => {
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
      }),
    );
  }

  function logo_color_at(fraction) {
    return `rgb(${window.report_ui.ramp_channels_at(fraction).join(",")})`;
  }
  function logo_letters_build(text, class_name, start_fraction) {
    const letters = [...text];
    return letters.map((letter, index) => {
      const letter_element = document.createElement("span");
      letter_element.className = class_name;
      letter_element.textContent = letter;
      letter_element.style.color = logo_color_at(
        letters.length > 1
          ? start_fraction +
              ((1 - start_fraction) * index) / (letters.length - 1)
          : 1,
      );
      return letter_element;
    });
  }
  function activate() {
    logo_link.replaceChildren(
      ...logo_letters_build(
        REPORT_NAME_TEXT,
        MENU_LOGO_LETTER_CLASS,
        STYLE_MENU_LOGO_START_FRACTION,
      ),
    );
    menu_strip.addEventListener(
      "keydown",
      window.catch_show_throw(window.report_ui.widget_key.link_click_take),
    );
    // what the views stored goes first, so each lays out on its defaults
    reset_button.addEventListener(
      "click",
      window.catch_show_throw(() => {
        window.report_ui.view_storage.preferences_clear();
        window.report_frame.view_post("report_ui:layout_reset");
      }),
    );
    buttons_label();
    pulldowns_activate();
    scale_activate();
    // a key typed on the top page outside a field is the menu's
    document.addEventListener(
      "keydown",
      window.catch_show_throw((key_event) => {
        const key_name = window.report_ui.view_key.of(key_event);
        if (key_name && menu_key_take(key_name)) key_event.preventDefault();
      }),
    );
    // every address link here, the menu's and the home panel's, is a request
    // to the model
    document.addEventListener(
      "click",
      window.catch_show_throw((click_event) => {
        const link_hash = window.report_ui.address.link_hash_of(click_event);
        if (!link_hash) return;
        click_event.preventDefault();
        window.report_frame.address_request(link_hash);
      }),
    );
  }

  window.report_menu = {
    address_show,
    menu_key_take,
  };

  activate();
  window.report_frame.activate();
})();
