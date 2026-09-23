(function () {
  var RETRY_LIMIT = 200;
  var RETRY_DELAY_MS = 50;
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
    var strings = window.ui_strings;
    if (strings && typeof strings.text_fill === "function") {
      return new Error(
        strings.text_fill(STARTUP_FAILED_STRING_ID, {
          seconds: (RETRY_LIMIT * RETRY_DELAY_MS) / 1000,
        }),
      );
    }
    return new Error(STARTUP_FAILED_STRING_ID);
  }
  if (!load_attempt()) {
    var retry_count = 0,
      retry_timer = setInterval(function () {
        if (load_attempt()) {
          clearInterval(retry_timer);
          return;
        }
        if (++retry_count >= RETRY_LIMIT) {
          clearInterval(retry_timer);
          throw startup_failure();
        }
      }, RETRY_DELAY_MS);
  }
})();
