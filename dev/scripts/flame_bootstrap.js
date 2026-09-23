(function () {
  var FLAME_GRAPH_STARTUP_POLL_DELAY_MS = settings(
    "FLAME_GRAPH_STARTUP_POLL_DELAY_MS",
  );
  var FLAME_GRAPH_STARTUP_POLL_MAX_ATTEMPTS = settings(
    "FLAME_GRAPH_STARTUP_POLL_MAX_ATTEMPTS",
  );
  var STARTUP_FAILED_STRING_ID = "str_error_flame_graph_never_started";
  var document_name = __NAME__;
  var document_base64 = __DATA__;
  function load_attempt() {
    if (window.speedscope && window.speedscope.loadFileFromBase64) {
      window.speedscope.loadFileFromBase64(document_name, document_base64);
      return true;
    }
    return false;
  }
  function startup_failure() {
    var waited_seconds =
      (FLAME_GRAPH_STARTUP_POLL_MAX_ATTEMPTS *
        FLAME_GRAPH_STARTUP_POLL_DELAY_MS) /
      1000;
    return new Error(STARTUP_FAILED_STRING_ID + " " + waited_seconds);
  }
  if (!load_attempt()) {
    var retry_count = 0,
      retry_timer = setInterval(function () {
        if (load_attempt()) {
          clearInterval(retry_timer);
          return;
        }
        if (++retry_count >= FLAME_GRAPH_STARTUP_POLL_MAX_ATTEMPTS) {
          clearInterval(retry_timer);
          throw startup_failure();
        }
      }, FLAME_GRAPH_STARTUP_POLL_DELAY_MS);
  }
})();
