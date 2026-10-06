// SPDX-FileCopyrightText: © 2026 Adrian Johnston.
// SPDX-License-Identifier: MIT
// This file is licensed under the terms of the LICENSE-MIT.md file.

window.try_catch_handler_(function () {
  "use strict";

  const page_scroll_box = document.querySelector("main.page-text-scroll-box-");

  // Shows the page from its top when its address is followed again.
  function page_top_show() {
    page_scroll_box.scrollTo(0, 0);
  }

  window.report_ui_.view_activate({
    dark_mode_apply: null,
    forwards_input: true,
    preferences_apply: null,
    recenter: page_top_show,
  });
})();
