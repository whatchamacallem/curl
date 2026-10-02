window.catch_show_throw_(function () {
  "use strict";

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

  function startup_failure() {
    const waited_seconds =
      (FLAME_GRAPH_STARTUP_POLL_MAX_ATTEMPTS *
        FLAME_GRAPH_STARTUP_POLL_DELAY_MS) /
      1000;
    return new Error(
      window.ui_strings_.text_fill("str_error_flame_graph_never_started", [
        waited_seconds,
      ]),
    );
  }
  function profile_hand_over() {
    const filed_profiles = window[FLAME_GRAPH_PROFILE_GLOBAL_NAME];
    if (!filed_profiles || !filed_profiles[_FORWARDED_ADDRESS.test])
      throw new Error(
        window.ui_strings_.text_fill("str_error_flame_graph_unfiled", [
          _FORWARDED_ADDRESS.test,
        ]),
      );
    const test_profile = filed_profiles[_FORWARDED_ADDRESS.test];
    let attempt_count = 0;
    const poll_timer = setInterval(
      window.catch_show_throw_(function () {
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
        throw startup_failure();
      }),
      FLAME_GRAPH_STARTUP_POLL_DELAY_MS,
    );
  }

  if (_FORWARDED_ADDRESS.view !== FLAME_GRAPH_VIEW_ENTRY[0])
    throw new Error(
      window.ui_strings_.text_fill("str_error_hash_view_mismatch", [
        FLAME_GRAPH_VIEW_ENTRY[0],
      ]),
    );
  if (_FORWARDED_ADDRESS.localProfilePath === null)
    throw new Error(
      window.ui_strings_.text_of("str_error_hash_profile_path_missing"),
    );
  window.addEventListener(
    "hashchange",
    window.catch_show_throw_(() => location.reload()),
  );
  const script_name = encodeURIComponent(_FORWARDED_ADDRESS.test) + ".js";
  _profile_script.src = FLAME_GRAPH_PROFILE_DIR_NAME + "/" + script_name;
  _profile_script.addEventListener(
    "error",
    window.catch_show_throw_(() => {
      throw new Error(
        window.ui_strings_.text_fill("str_error_hash_flame_graph_missing", [
          _FORWARDED_ADDRESS.test,
        ]),
      );
    }),
  );
  _profile_script.addEventListener(
    "load",
    window.catch_show_throw_(profile_hand_over),
  );
  document.head.append(_profile_script);
})();
