// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const FLAME_GRAPH_COLOR_SCHEME_KEY_NAME = settings_(
    "FLAME_GRAPH_COLOR_SCHEME_KEY_NAME",
  );
  const FLAME_GRAPH_LOCAL_PROFILE_URL_PREFIX = settings_(
    "FLAME_GRAPH_LOCAL_PROFILE_URL_PREFIX",
  );
  const FLAME_GRAPH_PROFILE_DIR_NAME = settings_(
    "FLAME_GRAPH_PROFILE_DIR_NAME",
  );
  const FLAME_GRAPH_PROFILE_GLOBAL_NAME = settings_(
    "FLAME_GRAPH_PROFILE_GLOBAL_NAME",
  );
  const FLAME_GRAPH_STARTUP_POLL_DELAY_MS = settings_(
    "FLAME_GRAPH_STARTUP_POLL_DELAY_MS",
  );
  const FLAME_GRAPH_STARTUP_POLL_MAX_ATTEMPTS = settings_(
    "FLAME_GRAPH_STARTUP_POLL_MAX_ATTEMPTS",
  );
  const FLAME_GRAPH_VIEW_ENTRY = settings_("FLAME_GRAPH_VIEW_ENTRY");

  const _FORWARDED_ADDRESS = window.report_ui_.address.of_hash(location.hash);
  const _profile_script = document.createElement("script");

  function profile_hand_over() {
    const filed_profiles = window[FLAME_GRAPH_PROFILE_GLOBAL_NAME];
    if (!filed_profiles || !filed_profiles[_FORWARDED_ADDRESS.test])
      window.throw_exception_("str_error_internal");
    const test_profile = filed_profiles[_FORWARDED_ADDRESS.test];
    let attempt_count = 0;
    const poll_timer = setInterval(
      window.try_catch_handler_(function () {
        if (window.speedscope && window.speedscope.loadFileFromBase64) {
          clearInterval(poll_timer);
          window.speedscope.loadFileFromBase64(
            test_profile.name,
            test_profile.base64,
          );
          return;
        }
        if (++attempt_count < FLAME_GRAPH_STARTUP_POLL_MAX_ATTEMPTS) return;
        clearInterval(poll_timer);
        window.throw_exception_("str_error_internal");
      }),
      FLAME_GRAPH_STARTUP_POLL_DELAY_MS,
    );
  }
  // Presses a key the menu relays on the window, where speedscope listens.
  function relayed_key_press(key_name) {
    window.dispatchEvent(new KeyboardEvent("keydown", { key: key_name }));
  }

  if (_FORWARDED_ADDRESS.view !== FLAME_GRAPH_VIEW_ENTRY[0])
    window.throw_exception_("str_error_internal");
  if (_FORWARDED_ADDRESS.localProfilePath === null)
    window.throw_exception_("str_error_hash_profile_path_missing");
  window.resource_failure_expect_(
    FLAME_GRAPH_LOCAL_PROFILE_URL_PREFIX + _FORWARDED_ADDRESS.localProfilePath,
  );
  document.title = window.ui_strings_.text("str_flame_graph_page_title");
  // Keeps speedscope on its system scheme, which the frame's scheme sets.
  window.report_ui_.view_storage.value_write(
    FLAME_GRAPH_COLOR_SCHEME_KEY_NAME,
    null,
  );
  window.addEventListener(
    "hashchange",
    window.try_catch_handler_(() => location.reload()),
  );
  window.report_ui_.view_activate({
    forwards_input: false,
    recenter: () => location.reload(),
    relayed_key_press,
  });
  const script_name = encodeURIComponent(_FORWARDED_ADDRESS.test) + ".js";
  _profile_script.src = FLAME_GRAPH_PROFILE_DIR_NAME + "/" + script_name;
  _profile_script.addEventListener(
    "load",
    window.try_catch_handler_(profile_hand_over),
  );
  document.head.append(_profile_script);
})();
