(function () {
  "use strict";

  const HEAT_COLOR_RAMP_STOPS = settings("HEAT_COLOR_RAMP_STOPS");

  const strip_bar = document.getElementById("bar");
  const home_panel = document.getElementById("home");
  const view_frame = document.getElementById("view");
  const title_badge = document.getElementById("title");
  const view_links = [...strip_bar.querySelectorAll("a[data-view]")];
  const utility_block = document.getElementById("util");
  const is_framed = window.parent !== window;
  const text_of = window.ui_strings.text_of;
  const OUTER_STATUS_TEXT = text_of("str_report_name");
  const SELECTION_SEPARATOR = " / ";
  const HOME_VIEW_LABEL = text_of("str_view_summary");
  let current_page_href = "",
    current_inner_hash = "",
    current_title = title_badge.textContent;
  const channels_of = (hex) =>
    [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16));
  const RAMP_STOPS = HEAT_COLOR_RAMP_STOPS.map(channels_of);
  function ramp_color_at(fraction) {
    const scaled_position = fraction * (RAMP_STOPS.length - 1);
    const index = Math.min(
      Math.max(Math.floor(scaled_position), 0),
      RAMP_STOPS.length - 2,
    );
    const step_fraction = scaled_position - index;
    const mixed_channels = [0, 1, 2].map((channel) => {
      const low_channel = RAMP_STOPS[index][channel],
        high_channel = RAMP_STOPS[index + 1][channel];
      return Math.round(
        low_channel + (high_channel - low_channel) * step_fraction,
      );
    });
    return `rgb(${mixed_channels.join(",")})`;
  }
  const WORDMARK_LETTERS = [...OUTER_STATUS_TEXT].map((letter, index, all) => {
    const letter_element = document.createElement("span");
    letter_element.className = "wordmark-letter";
    letter_element.textContent = letter;
    letter_element.style.color = ramp_color_at(
      all.length > 1 ? 0.5 + (0.5 * index) / (all.length - 1) : 1,
    );
    return letter_element;
  });
  function wordmark_paint() {
    title_badge.replaceChildren(...WORDMARK_LETTERS);
  }
  if (!is_framed) wordmark_paint();
  function selection_path(new_title) {
    return new_title && !new_title.includes(SELECTION_SEPARATOR)
      ? new_title + SELECTION_SEPARATOR + HOME_VIEW_LABEL
      : new_title;
  }
  function title_publish(new_title) {
    current_title = new_title;
    if (is_framed) title_badge.textContent = selection_path(new_title);
    else wordmark_paint();
    document.title = new_title;
    if (!is_framed) return;
    window.parent.postMessage(
      { report_ui: "title_changed", title: new_title },
      "*",
    );
  }

  function hash_parse(hash_text) {
    const hash_match = /^#([\w-]*)(?:\/(.*))?$/.exec(hash_text || "");
    return hash_match
      ? [hash_match[1], hash_match[2] ? "#" + hash_match[2] : ""]
      : ["", ""];
  }
  const hash_build = (view_key, inner_hash) =>
    view_key
      ? "#" + view_key + (inner_hash ? "/" + inner_hash.slice(1) : "")
      : "";
  function hash_canonicalize(canonical_hash) {
    if (canonical_hash !== location.hash)
      history.replaceState(null, "", canonical_hash || "#");
    if (is_framed)
      window.parent.postMessage(
        { report_ui: "hash_changed", hash: canonical_hash },
        "*",
      );
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
      hash_canonicalize("");
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
    hash_canonicalize(hash_build(view_key, inner_hash));
  }
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
  const reset_columns_link = document.getElementById("reset-cols");
  function reset_broadcast() {
    window.report_ui.layout_reset(home_panel);
    if (current_page_href)
      view_frame.contentWindow.postMessage("report_ui:reset_columns", "*");
  }
  reset_columns_link.addEventListener("click", (pointer_event) => {
    pointer_event.preventDefault();
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
      message_event.source === view_frame.contentWindow &&
      message_event.data
    ) {
      if (message_event.data.report_ui === "title_changed")
        title_publish(message_event.data.title);
      else if (
        message_event.data.report_ui === "hash_changed" &&
        current_page_href
      ) {
        current_inner_hash = message_event.data.hash;
        hash_canonicalize(
          hash_build(hash_parse(location.hash)[0], current_inner_hash),
        );
      }
      return;
    }
    if (is_framed && message_event.source === window.parent) {
      if (message_event.data === "report_ui:title_request")
        title_publish(current_title);
      else if (message_event.data === "report_ui:reset_columns")
        reset_broadcast();
    }
  });
  window.addEventListener("hashchange", () => view_show(location.hash));
  view_show(location.hash);
})();
