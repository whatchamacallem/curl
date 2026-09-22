(function () {
  "use strict";

  const HOME_VIEW_LABEL = window.ui_strings.text_of("str_view_summary");
  const LAYOUT_RESET_RATE_LIMIT_CLICKS = 3;
  const LAYOUT_RESET_RATE_LIMIT_WINDOW_MS = 5000;
  const OUTER_STATUS_TEXT = window.ui_strings.text_of("str_report_name");
  const SELECTION_SEPARATOR = " / ";
  const WORDMARK_LETTER_CLASS = "wordmark-letter";
  const WORDMARK_LOGO_START_FRACTION = 0.5;

  const home_panel = document.getElementById("home");
  const is_framed = window.report_ui.is_framed;
  const reset_click_times = [];
  const reset_columns_link = document.getElementById("reset-cols");
  const strip_bar = document.getElementById("bar");
  const title_badge = document.getElementById("title");
  const utility_block = document.getElementById("util");
  const view_frame = document.getElementById("view");
  const view_links = [...strip_bar.querySelectorAll("a[data-view]")];
  const wordmark_letters = window.report_ui.logo_letters_build(
    OUTER_STATUS_TEXT,
    WORDMARK_LETTER_CLASS,
    WORDMARK_LOGO_START_FRACTION,
  );
  let current_inner_hash = "",
    current_page_href = "",
    current_title = title_badge.textContent;

  const hash_build = (view_key, inner_hash) =>
    view_key
      ? "#" + view_key + (inner_hash ? "/" + inner_hash.slice(1) : "")
      : "";
  function hash_for_href(link_href) {
    for (const link_element of view_links) {
      const link_base = link_element.getAttribute("href");
      if (link_element.dataset.view && link_href.startsWith(link_base)) {
        const remaining_hash = link_href.slice(link_base.length);
        return hash_build(
          link_element.dataset.view,
          remaining_hash.startsWith("#") ? remaining_hash : "",
        );
      }
    }
    return null;
  }
  function hash_parse(hash_text) {
    const hash_match = /^#([\w-]*)(?:\/(.*))?$/.exec(hash_text || "");
    return hash_match
      ? [hash_match[1], hash_match[2] ? "#" + hash_match[2] : ""]
      : ["", ""];
  }
  function selection_path(new_title) {
    return new_title && !new_title.includes(SELECTION_SEPARATOR)
      ? new_title + SELECTION_SEPARATOR + HOME_VIEW_LABEL
      : new_title;
  }
  function title_publish(new_title) {
    current_title = new_title;
    if (is_framed) title_badge.textContent = selection_path(new_title);
    else title_badge.replaceChildren(...wordmark_letters);
    document.title = new_title;
    window.report_ui.parent_post({
      report_ui: "title_changed",
      title: new_title,
    });
  }
  function view_show(target_hash) {
    const [view_key, inner_hash] = hash_parse(target_hash);
    const matched_link = view_links.find(
      (link_element) => link_element.dataset.view === view_key,
    );
    const active_link = matched_link || view_links[0];
    for (const link_element of view_links) {
      link_element.classList.toggle("on", link_element === active_link);
    }
    title_publish(active_link.dataset.title);
    utility_block.hidden =
      !is_framed && !!(matched_link && view_key && matched_link.dataset.frame);
    if (!matched_link || !view_key) {
      view_frame.hidden = true;
      home_panel.hidden = false;
      window.report_ui.layout_refresh(home_panel);
      window.report_ui.hash_publish("");
      return;
    }
    const link_href = matched_link.getAttribute("href");
    if (link_href !== current_page_href || inner_hash !== current_inner_hash) {
      view_frame.contentWindow.location.replace(
        link_href + (inner_hash || "#"),
      );
    } else
      view_frame.contentWindow.postMessage("report_ui:title_request", "*");
    current_page_href = link_href;
    current_inner_hash = inner_hash;
    home_panel.hidden = true;
    view_frame.hidden = false;
    window.report_ui.hash_publish(hash_build(view_key, inner_hash));
  }
  function reset_broadcast() {
    window.report_ui.layout_reset(home_panel);
    if (current_page_href)
      view_frame.contentWindow.postMessage("report_ui:reset_columns", "*");
  }

  reset_columns_link.addEventListener("click", (pointer_event) => {
    pointer_event.preventDefault();
    const click_time = Date.now();
    while (
      reset_click_times.length &&
      click_time - reset_click_times[0] > LAYOUT_RESET_RATE_LIMIT_WINDOW_MS
    ) {
      reset_click_times.shift();
    }
    reset_click_times.push(click_time);
    if (reset_click_times.length >= LAYOUT_RESET_RATE_LIMIT_CLICKS) {
      throw new Error(
        window.ui_strings.text_of("str_error_reset_columns_too_fast"),
      );
    }
    reset_broadcast();
  });
  document.addEventListener("click", (click_event) => {
    const link_element = click_event.target.closest("a[href]");
    if (
      !link_element ||
      link_element === reset_columns_link ||
      link_element.target
    )
      return;
    if (click_event.ctrlKey || click_event.metaKey || click_event.shiftKey)
      return;
    if (click_event.button) return;
    const link_href = link_element.getAttribute("href");
    const target_hash =
      link_element.dataset.view != null
        ? hash_build(link_element.dataset.view, "")
        : hash_for_href(link_href);
    if (target_hash == null) return;
    click_event.preventDefault();
    if (target_hash === (location.hash || "")) view_show(target_hash);
    else location.hash = target_hash;
  });
  window.addEventListener("message", (message_event) => {
    if (
      message_event.source !== view_frame.contentWindow ||
      !message_event.data
    )
      return;
    if (message_event.data.report_ui === "title_changed")
      title_publish(message_event.data.title);
    else if (
      message_event.data.report_ui === "hash_changed" &&
      current_page_href
    ) {
      current_inner_hash = message_event.data.hash;
      window.report_ui.hash_publish(
        hash_build(hash_parse(location.hash)[0], current_inner_hash),
      );
    }
  });
  window.report_ui.parent_listen((message_data) => {
    if (message_data === "report_ui:title_request")
      title_publish(current_title);
    else if (message_data === "report_ui:reset_columns") reset_broadcast();
  });
  window.addEventListener("hashchange", () => view_show(location.hash));
  view_show(location.hash);
})();
