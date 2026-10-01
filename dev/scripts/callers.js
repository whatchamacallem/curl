window.catch_show_throw(function () {
  "use strict";

  // a test's callers page is a view: its address links ask the top page,
  // its keys go up to the menu, and that page stores and recenters nothing
  window.report_ui.view_activate({ preferences_apply: null, recenter: null });
})();
