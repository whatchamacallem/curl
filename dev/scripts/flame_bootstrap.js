(function () {
  var RETRY_LIMIT = 200;
  var RETRY_DELAY_MS = 50;
  var document_name = __NAME__;
  var document_base64 = __DATA__;
  function load_attempt() {
    if (window.speedscope && window.speedscope.loadFileFromBase64) {
      window.speedscope.loadFileFromBase64(document_name, document_base64);
      return true;
    }
    return false;
  }
  if (!load_attempt()) {
    var retry_count = 0,
      retry_timer = setInterval(function () {
        if (load_attempt() || ++retry_count >= RETRY_LIMIT)
          clearInterval(retry_timer);
      }, RETRY_DELAY_MS);
  }
})();
