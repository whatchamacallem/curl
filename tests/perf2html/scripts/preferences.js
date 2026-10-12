// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.report_preferences_ = window.try_catch_handler_(function () {
  "use strict";

  const COUNTER_SELECTION_CALLS_SHOWN_DEFAULT = settings_(
    "COUNTER_SELECTION_CALLS_SHOWN_DEFAULT",
  );
  const COUNTER_SELECTION_DEFAULT_NAMES = settings_(
    "COUNTER_SELECTION_DEFAULT_NAMES",
  );
  const HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX = settings_(
    "HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX",
  );
  const HEAT_MAP_SCALE_DEFAULT_VALUE = settings_(
    "HEAT_MAP_SCALE_DEFAULT_VALUE",
  );
  const HEAT_MAP_SCALE_DIFF_DEFAULT_VALUE = settings_(
    "HEAT_MAP_SCALE_DIFF_DEFAULT_VALUE",
  );
  const HEAT_MAP_SORT_DEFAULT_MODE = settings_("HEAT_MAP_SORT_DEFAULT_MODE");
  const RANKING_COUNTER_NAME = settings_("RANKING_COUNTER_NAME");
  const STORAGE_KEY_HEAT_SCALE = settings_("STORAGE_KEY_HEAT_SCALE");
  const STORAGE_KEY_HEAT_SORT = settings_("STORAGE_KEY_HEAT_SORT");
  const STORAGE_KEY_VIEW_CALLS = settings_("STORAGE_KEY_VIEW_CALLS");
  const STORAGE_KEY_VIEW_COUNTERS = settings_("STORAGE_KEY_VIEW_COUNTERS");

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
  const SHOWS_CALLS_VALUES = [true, false];

  let report_counter_names = null;
  let toggled_counter_names = null;
  let report_heat_scale_choices = null;
  let heat_scale_default_value = null;
  let shown_preferences = null;

  // Answers the description of a counter, the words its label leads with.
  function counter_description(counter_name) {
    return window.ui_strings_.text(
      HEAT_MAP_COUNTER_DESCRIPTION_STRING_ID_PREFIX +
        counter_name.toLowerCase(),
    );
  }
  // Answers the label of a counter, its description and then its name.
  function counter_label(counter_name) {
    return window.ui_strings_.text_fill("str_counter_label", {
      description: counter_description(counter_name),
      counter: counter_name,
    });
  }
  // Lists the heat scale choices, each curve by each scope the report has.
  function heat_scale_choices(is_diff) {
    const text = window.ui_strings_.text;
    const curve_choices = [
      ["log", text("str_scale_curve_log")],
      ["linear", text("str_scale_curve_linear")],
    ];
    const scope_choices = is_diff
      ? [["line", null]]
      : [
          ["global", null],
          ["file", text("str_scope_file")],
          ["function", text("str_scope_function")],
        ];
    return curve_choices.flatMap(([curve_name, curve_label]) =>
      scope_choices.map(([scope_name, scope_label]) => ({
        value: curve_name + "/" + scope_name,
        curve: curve_name,
        scope: scope_name,
        label:
          scope_label === null
            ? curve_label
            : window.ui_strings_.text_fill("str_scale_entry", {
                curve: curve_label,
                scope: scope_label,
              }),
      })),
    );
  }

  // Answers the preferences the page shows, a view's those last relayed.
  function now() {
    if (shown_preferences === null)
      window.throw_exception_("str_error_internal");
    return shown_preferences;
  }
  // Shows preferences on the page, storing nothing, answering if they changed.
  function show(wanted_preferences) {
    const next_preferences = Object.freeze({
      counter_names: Object.freeze([...wanted_preferences.counter_names]),
      heat_scale_value: wanted_preferences.heat_scale_value,
      heat_sort_mode: wanted_preferences.heat_sort_mode,
      shows_calls: wanted_preferences.shows_calls,
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
  // Answers the counters shown: the ranking counter, then those chosen.
  function shown_counter_names(chosen_names) {
    return report_counter_names.filter(
      (counter_name) =>
        counter_name === RANKING_COUNTER_NAME ||
        chosen_names.includes(counter_name),
    );
  }
  // Answers the stored choice when this report offers it, else the default.
  function stored_choice(storage_key, offered_values, default_value) {
    const stored_value =
      window.report_ui_.view_storage.value_read(storage_key);
    return offered_values.includes(stored_value)
      ? stored_value
      : default_value;
  }
  // Answers the counters stored as chosen when this report offers each one.
  function stored_counter_names() {
    const stored_names = window.report_ui_.view_storage.value_read(
      STORAGE_KEY_VIEW_COUNTERS,
    );
    const is_offered =
      Array.isArray(stored_names) &&
      stored_names.every((stored_name) =>
        toggled_counter_names.includes(stored_name),
      );
    return is_offered ? stored_names : COUNTER_SELECTION_DEFAULT_NAMES;
  }
  // Shows the stored preferences, each one the user never chose its default.
  function seed() {
    show({
      counter_names: shown_counter_names(stored_counter_names()),
      heat_scale_value: stored_choice(
        STORAGE_KEY_HEAT_SCALE,
        choice_values(report_heat_scale_choices),
        heat_scale_default_value,
      ),
      heat_sort_mode: stored_choice(
        STORAGE_KEY_HEAT_SORT,
        choice_values(HEAT_SORT_CHOICES),
        HEAT_MAP_SORT_DEFAULT_MODE,
      ),
      shows_calls: stored_choice(
        STORAGE_KEY_VIEW_CALLS,
        SHOWS_CALLS_VALUES,
        COUNTER_SELECTION_CALLS_SHOWN_DEFAULT,
      ),
    });
  }
  // Refuses default preferences naming choices this report does not offer.
  function preference_settings_check(is_diff) {
    setting_choices_check(
      "COUNTER_SELECTION_CALLS_SHOWN_DEFAULT",
      [COUNTER_SELECTION_CALLS_SHOWN_DEFAULT],
      SHOWS_CALLS_VALUES,
    );
    setting_choices_check(
      "COUNTER_SELECTION_DEFAULT_NAMES",
      COUNTER_SELECTION_DEFAULT_NAMES,
      toggled_counter_names,
    );
    setting_choices_check(
      is_diff
        ? "HEAT_MAP_SCALE_DIFF_DEFAULT_VALUE"
        : "HEAT_MAP_SCALE_DEFAULT_VALUE",
      [heat_scale_default_value],
      choice_values(report_heat_scale_choices),
    );
    setting_choices_check(
      "HEAT_MAP_SORT_DEFAULT_MODE",
      [HEAT_MAP_SORT_DEFAULT_MODE],
      choice_values(HEAT_SORT_CHOICES),
    );
  }
  // Takes the report's counters and kind, checks the defaults, then seeds.
  function activate(counter_names, is_diff) {
    report_counter_names = counter_names;
    toggled_counter_names = counter_names.filter(
      (counter_name) => counter_name !== RANKING_COUNTER_NAME,
    );
    report_heat_scale_choices = heat_scale_choices(is_diff);
    heat_scale_default_value = is_diff
      ? HEAT_MAP_SCALE_DIFF_DEFAULT_VALUE
      : HEAT_MAP_SCALE_DEFAULT_VALUE;
    preference_settings_check(is_diff);
    seed();
  }

  // Shows a chosen preference and stores it as the user's.
  function preference_choose(chosen_fields, storage_key, stored_value) {
    window.report_ui_.view_storage.value_write(storage_key, stored_value);
    show({ ...now(), ...chosen_fields });
  }
  // Shows or hides the calls columns, storing the choice.
  function calls_toggle() {
    const shows_calls = !now().shows_calls;
    preference_choose({ shows_calls }, STORAGE_KEY_VIEW_CALLS, shows_calls);
  }
  // Turns one counter on or off, answering false for the ranking counter.
  function counter_toggle(counter_name) {
    if (!toggled_counter_names.includes(counter_name)) return false;
    const shown_names = now().counter_names;
    const chosen_names = toggled_counter_names.filter((toggled_name) =>
      toggled_name === counter_name
        ? !shown_names.includes(toggled_name)
        : shown_names.includes(toggled_name),
    );
    preference_choose(
      { counter_names: shown_counter_names(chosen_names) },
      STORAGE_KEY_VIEW_COUNTERS,
      chosen_names,
    );
    return true;
  }
  function heat_scale_choose(scale_value) {
    preference_choose(
      { heat_scale_value: scale_value },
      STORAGE_KEY_HEAT_SCALE,
      scale_value,
    );
  }
  function heat_sort_choose(sort_mode) {
    preference_choose(
      { heat_sort_mode: sort_mode },
      STORAGE_KEY_HEAT_SORT,
      sort_mode,
    );
  }

  return {
    activate,
    calls_toggle,
    counter_description,
    counter_label,
    counter_toggle,
    heat_scale_choices,
    heat_scale_choose,
    heat_sort_choices: HEAT_SORT_CHOICES,
    heat_sort_choose,
    now,
    relay_handler,
    seed,
  };
})();
