(function () {
  var NAME = __NAME__;
  var DATA = __DATA__;
  function load() {
    if (window.speedscope && window.speedscope.loadFileFromBase64) {
      window.speedscope.loadFileFromBase64(NAME, DATA);
      return true;
    }
    return false;
  }
  if (!load()) {
    var tries = 0,
      timer = setInterval(function () {
        if (load() || ++tries >= 200) clearInterval(timer);
      }, 50);
  }
})();
