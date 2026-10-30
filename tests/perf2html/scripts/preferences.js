// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.report_preferences_ = window.try_catch_handler_(function () {
  "use strict";

  const COUNTER_LIST_CALLEES_LINE_NAME = settings_(
    "COUNTER_LIST_CALLEES_LINE_NAME",
  );
  const COUNTER_LIST_CALLERS_LINE_NAME = settings_(
    "COUNTER_LIST_CALLERS_LINE_NAME",
  );
  const COUNTER_LIST_CALLGRIND_LINE_NAMES = settings_(
    "COUNTER_LIST_CALLGRIND_LINE_NAMES",
  );
  const COUNTER_LIST_CALLS_LINE_NAME = settings_(
    "COUNTER_LIST_CALLS_LINE_NAME",
  );
  const COUNTER_LIST_NON_CALLGRIND_LINE_NAMES = settings_(
    "COUNTER_LIST_NON_CALLGRIND_LINE_NAMES",
  );
  const DATABASE_COUNTER_LIST_DEFAULT_SHOWN_NAMES = settings_(
    "DATABASE_COUNTER_LIST_DEFAULT_SHOWN_NAMES",
  );
  const DATABASE_VIEW_KEY = settings_("DATABASE_VIEW_KEY");
  const HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX = settings_(
    "HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX",
  );
  const HEAT_MAP_COUNTER_LIST_DEFAULT_SHOWN_NAMES = settings_(
    "HEAT_MAP_COUNTER_LIST_DEFAULT_SHOWN_NAMES",
  );
  const HEAT_MAP_SCALE_DEFAULT_VALUE = settings_(
    "HEAT_MAP_SCALE_DEFAULT_VALUE",
  );
  const HEAT_MAP_SORT_DEFAULT_MODE = settings_("HEAT_MAP_SORT_DEFAULT_MODE");
  const HEAT_MAP_VIEW_ENTRY = settings_("HEAT_MAP_VIEW_ENTRY");
  const RANKING_COUNTER_NAME = settings_("RANKING_COUNTER_NAME");
  const STORAGE_KEY_DATABASE_COUNTER_LIST = settings_(
    "STORAGE_KEY_DATABASE_COUNTER_LIST",
  );
  const STORAGE_KEY_HEATMAP_COUNTER_LIST = settings_(
    "STORAGE_KEY_HEATMAP_COUNTER_LIST",
  );
  const STORAGE_KEY_HEATMAP_SCALE = settings_("STORAGE_KEY_HEATMAP_SCALE");
  const STORAGE_KEY_HEATMAP_SORT = settings_("STORAGE_KEY_HEATMAP_SORT");

  const HEAT_SORT_CHOICES = [
    {
      value: "heat",
      label: window.ui_strings_.text("str_sort_hottest_first"),
    },
    {
      value: "name",
      label: window.ui_strings_.text("str_sort_alphabetical"),
    },
  ];
  // Holds each line that is not a callgrind counter: its title and its kind.
  const NON_CALLGRIND_LINES = {
    [COUNTER_LIST_CALLEES_LINE_NAME]: {
      is_numeric: false,
      string_id: "str_column_callees",
    },
    [COUNTER_LIST_CALLERS_LINE_NAME]: {
      is_numeric: false,
      string_id: "str_column_callers",
    },
    [COUNTER_LIST_CALLS_LINE_NAME]: {
      is_numeric: true,
      string_id: "str_column_calls",
    },
  };
  // Lists every line of a counters list in its default order, the settings'.
  const DEFAULT_LINE_NAMES = [
    ...COUNTER_LIST_CALLGRIND_LINE_NAMES,
    ...COUNTER_LIST_NON_CALLGRIND_LINE_NAMES,
  ];
  // Holds each counters list kind: its defaults, kept line and storage.
  const COUNTER_LIST_KINDS = {
    [DATABASE_VIEW_KEY]: {
      default_setting_name: "DATABASE_COUNTER_LIST_DEFAULT_SHOWN_NAMES",
      default_shown_names: DATABASE_COUNTER_LIST_DEFAULT_SHOWN_NAMES,
      keeps_ranking_shown: false,
      storage_key: STORAGE_KEY_DATABASE_COUNTER_LIST,
    },
    [HEAT_MAP_VIEW_ENTRY[0]]: {
      default_setting_name: "HEAT_MAP_COUNTER_LIST_DEFAULT_SHOWN_NAMES",
      default_shown_names: HEAT_MAP_COUNTER_LIST_DEFAULT_SHOWN_NAMES,
      keeps_ranking_shown: true,
      storage_key: STORAGE_KEY_HEATMAP_COUNTER_LIST,
    },
  };

  let shown_preferences = null;

  // Returns the description of a counter, the words its label leads with.
  function counter_description(counter_name) {
    return window.ui_strings_.text(
      HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX +
        counter_name.toLowerCase(),
    );
  }
  // Returns the label of a counter, its description and then its name.
  function counter_label(counter_name) {
    return window.ui_strings_.text_fill("str_counter_label", {
      description: counter_description(counter_name),
      counter: counter_name,
    });
  }
  // Returns the reader of each counter, the recorded ones first, then derived.
  function counter_readers(counter_names, derived_counters) {
    const vector_value = (cost_vector, counter_index) =>
      cost_vector && counter_index < cost_vector.length
        ? cost_vector[counter_index]
        : 0;
    return [
      ...counter_names.map((counter_name, counter_index) => ({
        key: counter_name,
        get: (cost_vector) => vector_value(cost_vector, counter_index),
        derived: false,
      })),
      ...derived_counters.map(([counter_name, derived_terms]) => ({
        key: counter_name,
        get: (cost_vector) =>
          derived_terms.reduce(
            (running_total, [term_coefficient, term_index]) =>
              running_total +
              term_coefficient * vector_value(cost_vector, term_index),
            0,
          ),
        derived: true,
      })),
    ];
  }
  // Lists the heat scale choices, one per curve.
  function heat_scale_choices() {
    const text = window.ui_strings_.text;
    const curve_choices = [
      ["log", text("str_scale_curve_log")],
      ["linear", text("str_scale_curve_linear")],
    ];
    return curve_choices.map(([curve_name, curve_label]) => ({
      value: curve_name,
      curve: curve_name,
      label: curve_label,
    }));
  }
  // Returns whether a line is a callgrind counter, not a line of calls.
  function is_callgrind_line(line_name) {
    return !Object.hasOwn(NON_CALLGRIND_LINES, line_name);
  }
  // Returns the column title of a line, a counter's name or the line's string.
  function line_title(line_name) {
    return is_callgrind_line(line_name)
      ? line_name
      : window.ui_strings_.text(NON_CALLGRIND_LINES[line_name].string_id);
  }
  // Returns the label of a line, a counter's label or the line's title.
  function line_label(line_name) {
    return is_callgrind_line(line_name)
      ? counter_label(line_name)
      : line_title(line_name);
  }
  // Returns a line's column: its title, its label, its name and its kind.
  function line_column(line_name) {
    return {
      is_counter_line: true,
      label: line_title(line_name),
      measure: line_label(line_name),
      name: line_name,
      numeric:
        is_callgrind_line(line_name) ||
        NON_CALLGRIND_LINES[line_name].is_numeric,
    };
  }

  // Returns the preferences the page shows, a view's those last relayed.
  function now() {
    if (shown_preferences === null)
      window.throw_exception_("str_error_internal");
    return shown_preferences;
  }
  // Returns the lines of a counters list in order, refusing an unknown list.
  function counter_lines_of(list_key) {
    const counter_lines = now().counter_lists[list_key];
    if (!counter_lines) window.throw_exception_("str_error_internal");
    return counter_lines;
  }
  // Returns the names of the shown lines of a counters list, in its order.
  function shown_line_names(list_key) {
    return counter_lines_of(list_key)
      .filter((counter_line) => counter_line.is_shown)
      .map((counter_line) => counter_line.line_name);
  }
  // Lists the parts a page makes of a list's shown lines, in the list order.
  function shown_line_parts(list_key, callgrind_part, call_parts) {
    return shown_line_names(list_key)
      .map((line_name) => {
        if (is_callgrind_line(line_name)) return callgrind_part(line_name);
        if (!Object.hasOwn(call_parts, line_name))
          window.throw_exception_("str_error_internal");
        return call_parts[line_name];
      })
      .filter((line_part) => line_part !== null);
  }
  // Lists the lines of a list as choices, the one door to their order.
  function line_choices(list_key) {
    return counter_lines_of(list_key).map((counter_line) => ({
      is_shown: counter_line.is_shown,
      label: line_label(counter_line.line_name),
      value: counter_line.line_name,
    }));
  }
  // Lists the counters pulldown's choices, each line of the list, marked.
  function counter_choices(list_key) {
    return line_choices(list_key).map((line_choice) => ({
      label: window.ui_strings_.text_fill("str_menu_counter_entry", {
        mark: window.ui_strings_.text(
          line_choice.is_shown
            ? "str_menu_counter_selected_mark"
            : "str_menu_counter_unselected_mark",
        ),
        label: line_choice.label,
      }),
      value: line_choice.value,
    }));
  }
  // Lists the sort order pulldown's choices, the shown lines of the list.
  function sort_order_choices(list_key) {
    return line_choices(list_key)
      .filter((line_choice) => line_choice.is_shown)
      .map((line_choice) => ({
        label: line_choice.label,
        value: line_choice.value,
      }));
  }
  // Copies the lines of a counters list, each frozen as the page shows it.
  function counter_lines_freeze(counter_lines) {
    return Object.freeze(
      counter_lines.map((counter_line) =>
        Object.freeze({
          line_name: counter_line.line_name,
          is_shown: counter_line.is_shown,
        }),
      ),
    );
  }
  // Shows preferences on the page, storing nothing, answering if they changed.
  function show(wanted_preferences) {
    const next_preferences = Object.freeze({
      counter_lists: Object.freeze(
        Object.fromEntries(
          Object.entries(wanted_preferences.counter_lists).map(
            ([list_key, counter_lines]) => [
              list_key,
              counter_lines_freeze(counter_lines),
            ],
          ),
        ),
      ),
      heat_scale_value: wanted_preferences.heat_scale_value,
      heat_sort_mode: wanted_preferences.heat_sort_mode,
    });
    const is_changed =
      JSON.stringify(next_preferences) !== JSON.stringify(shown_preferences);
    shown_preferences = next_preferences;
    return is_changed;
  }
  // Takes the preferences a frame message relays, answering if they changed.
  function relay_handler(message_data) {
    return show(message_data.view_preferences);
  }

  function choice_values(choices) {
    return choices.map((choice) => choice.value);
  }
  // Refuses a setting that names a choice this report does not offer.
  function setting_choices_check(setting_name, chosen_values, offered_values) {
    for (const chosen_value of chosen_values) {
      if (!offered_values.includes(chosen_value))
        window.throw_exception_(
          "str_error_setting_choice_unknown",
          setting_name,
          chosen_value,
        );
    }
  }
  // Refuses an order setting naming an offered choice other than once.
  function setting_order_check(setting_name, ordered_values, offered_values) {
    setting_choices_check(setting_name, ordered_values, offered_values);
    const repeated_value = ordered_values.find(
      (ordered_value, value_index) =>
        ordered_values.indexOf(ordered_value) !== value_index,
    );
    if (repeated_value !== undefined)
      window.throw_exception_(
        "str_error_setting_choice_repeated",
        setting_name,
        repeated_value,
      );
    const missing_value = offered_values.find(
      (offered_value) => !ordered_values.includes(offered_value),
    );
    if (missing_value !== undefined)
      window.throw_exception_(
        "str_error_setting_choice_missing",
        setting_name,
        missing_value,
      );
  }
  // Returns whether a list keeps a line shown, its ranking counter alone.
  function is_line_kept_shown(list_kind, line_name) {
    return list_kind.keeps_ranking_shown && line_name === RANKING_COUNTER_NAME;
  }
  // Lists the lines a user can hide, each but a line the list keeps shown.
  function toggled_line_names(list_kind) {
    return DEFAULT_LINE_NAMES.filter(
      (line_name) => !is_line_kept_shown(list_kind, line_name),
    );
  }
  // Returns the default lines of a list, those its setting names shown.
  function default_counter_lines(list_kind) {
    return DEFAULT_LINE_NAMES.map((line_name) => ({
      line_name,
      is_shown:
        is_line_kept_shown(list_kind, line_name) ||
        list_kind.default_shown_names.includes(line_name),
    }));
  }
  // Returns the stored list when that names each offered line, else default.
  function stored_counter_lines(list_kind) {
    const stored_lines = window.report_ui_.view_storage.value_read(
      list_kind.storage_key,
    );
    const sorted_text = (line_names) => JSON.stringify([...line_names].sort());
    const stored_names = Array.isArray(stored_lines)
      ? stored_lines.map((stored_line) => stored_line.line_name)
      : [];
    const is_offered =
      sorted_text(stored_names) === sorted_text(DEFAULT_LINE_NAMES);
    return is_offered ? stored_lines : default_counter_lines(list_kind);
  }
  // Returns the stored choice when this report offers it, else the default.
  function stored_choice(storage_key, offered_values, default_value) {
    const stored_value =
      window.report_ui_.view_storage.value_read(storage_key);
    return offered_values.includes(stored_value)
      ? stored_value
      : default_value;
  }
  // Shows the stored preferences, each one the user never chose its default.
  function seed() {
    show({
      counter_lists: Object.fromEntries(
        Object.entries(COUNTER_LIST_KINDS).map(([list_key, list_kind]) => [
          list_key,
          stored_counter_lines(list_kind),
        ]),
      ),
      heat_scale_value: stored_choice(
        STORAGE_KEY_HEATMAP_SCALE,
        choice_values(heat_scale_choices()),
        HEAT_MAP_SCALE_DEFAULT_VALUE,
      ),
      heat_sort_mode: stored_choice(
        STORAGE_KEY_HEATMAP_SORT,
        choice_values(HEAT_SORT_CHOICES),
        HEAT_MAP_SORT_DEFAULT_MODE,
      ),
    });
  }
  // Refuses a line order or default preferences this report does not offer.
  function preference_settings_check(counter_names) {
    setting_order_check(
      "COUNTER_LIST_CALLGRIND_LINE_NAMES",
      COUNTER_LIST_CALLGRIND_LINE_NAMES,
      counter_names,
    );
    setting_order_check(
      "COUNTER_LIST_NON_CALLGRIND_LINE_NAMES",
      COUNTER_LIST_NON_CALLGRIND_LINE_NAMES,
      Object.keys(NON_CALLGRIND_LINES),
    );
    for (const list_kind of Object.values(COUNTER_LIST_KINDS))
      setting_choices_check(
        list_kind.default_setting_name,
        list_kind.default_shown_names,
        toggled_line_names(list_kind),
      );
    setting_choices_check(
      "HEAT_MAP_SCALE_DEFAULT_VALUE",
      [HEAT_MAP_SCALE_DEFAULT_VALUE],
      choice_values(heat_scale_choices()),
    );
    setting_choices_check(
      "HEAT_MAP_SORT_DEFAULT_MODE",
      [HEAT_MAP_SORT_DEFAULT_MODE],
      choice_values(HEAT_SORT_CHOICES),
    );
  }
  // Checks the settings against the report's counters, then seeds.
  function activate(counter_names) {
    preference_settings_check(counter_names);
    seed();
  }

  // Shows a chosen preference and stores it as the user's.
  function preference_choose(chosen_fields, storage_key, stored_value) {
    window.report_ui_.view_storage.value_write(storage_key, stored_value);
    show({ ...now(), ...chosen_fields });
  }
  // Returns a counters list, refusing a list or a line the report lacks.
  function counter_lines_holding(list_key, line_name) {
    const counter_lines = counter_lines_of(list_key);
    if (
      !counter_lines.some(
        (counter_line) => counter_line.line_name === line_name,
      )
    )
      window.throw_exception_("str_error_internal");
    return counter_lines;
  }
  // Shows a counters list as chosen and stores that list.
  function counter_lines_choose(list_key, counter_lines) {
    preference_choose(
      { counter_lists: { ...now().counter_lists, [list_key]: counter_lines } },
      COUNTER_LIST_KINDS[list_key].storage_key,
      counter_lines,
    );
  }
  // Shows or hides a line, answering false for a line the list keeps shown.
  function counter_line_toggle(list_key, line_name) {
    const counter_lines = counter_lines_holding(list_key, line_name);
    if (is_line_kept_shown(COUNTER_LIST_KINDS[list_key], line_name))
      return false;
    counter_lines_choose(
      list_key,
      counter_lines.map((counter_line) =>
        counter_line.line_name === line_name
          ? { line_name, is_shown: !counter_line.is_shown }
          : counter_line,
      ),
    );
    return true;
  }
  // Moves a line before or after its anchor line, storing the list.
  function counter_line_move(list_key, line_name, anchor_name, lands_after) {
    const counter_lines = counter_lines_holding(list_key, line_name);
    const moved_line = counter_lines.find(
      (counter_line) => counter_line.line_name === line_name,
    );
    const kept_lines = counter_lines.filter(
      (counter_line) => counter_line !== moved_line,
    );
    const anchor_index = kept_lines.findIndex(
      (counter_line) => counter_line.line_name === anchor_name,
    );
    if (anchor_index < 0) window.throw_exception_("str_error_internal");
    kept_lines.splice(anchor_index + (lands_after ? 1 : 0), 0, moved_line);
    counter_lines_choose(list_key, kept_lines);
  }
  function heat_scale_choose(scale_value) {
    preference_choose(
      { heat_scale_value: scale_value },
      STORAGE_KEY_HEATMAP_SCALE,
      scale_value,
    );
  }
  function heat_sort_choose(sort_mode) {
    preference_choose(
      { heat_sort_mode: sort_mode },
      STORAGE_KEY_HEATMAP_SORT,
      sort_mode,
    );
  }

  return {
    activate,
    counter_choices,
    counter_label,
    counter_line_move,
    counter_line_toggle,
    counter_readers,
    heat_scale_choices,
    heat_scale_choose,
    heat_sort_choices: HEAT_SORT_CHOICES,
    heat_sort_choose,
    line_column,
    now,
    relay_handler,
    seed,
    shown_line_names,
    shown_line_parts,
    sort_order_choices,
  };
})();
