window.report_ui = (function () {
  "use strict";

  const HEAT_COLOR_LOGO_STOPS = settings("HEAT_COLOR_LOGO_STOPS");
  const NUMBER_SMALLEST_PRINTED_PERCENT = settings(
    "NUMBER_SMALLEST_PRINTED_PERCENT",
  );
  const TABLE_COLUMN_NARROWEST_DRAG_PX = settings(
    "TABLE_COLUMN_NARROWEST_DRAG_PX",
  );

  const LAYOUT_RESIZE_SETTLE_DELAY_MS = 120;
  const LOGO_CHANNEL_STOPS = HEAT_COLOR_LOGO_STOPS.map((hex) =>
    [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16)),
  );
  const MULTIPLE_UPPER_BOUND_TIMES = 999.99;
  const PANE_SPLITTER_NARROWEST_PX = 120;
  const PANE_SPLITTER_WIDEST_WINDOW_SHARE = 0.6;
  const STORAGE_OWNED_KEYS = ["heat.scale", "heat.sort"];
  const STORAGE_OWNED_PREFIXES = ["split."];
  const STORAGE_VERSION = "perf2html v1";
  const STORAGE_VERSION_KEY = "perf2html.version";

  const is_framed = window.parent !== window;
  const registered_panes = [];
  let resize_debounce_timer = null;
  let storage_is_checked = false;

  function logo_color_at(fraction) {
    const scaled_position = fraction * (LOGO_CHANNEL_STOPS.length - 1);
    const index = Math.min(
      Math.max(Math.floor(scaled_position), 0),
      LOGO_CHANNEL_STOPS.length - 2,
    );
    const step_fraction = scaled_position - index;
    const mixed_channels = [0, 1, 2].map((channel) => {
      const low_channel = LOGO_CHANNEL_STOPS[index][channel],
        high_channel = LOGO_CHANNEL_STOPS[index + 1][channel];
      return Math.round(
        low_channel + (high_channel - low_channel) * step_fraction,
      );
    });
    return `rgb(${mixed_channels.join(",")})`;
  }
  function logo_letters_build(text, class_name, start_fraction) {
    const letters = [...text];
    return letters.map((letter, index) => {
      const letter_element = document.createElement("span");
      letter_element.className = class_name;
      letter_element.textContent = letter;
      letter_element.style.color = logo_color_at(
        letters.length > 1
          ? start_fraction +
              ((1 - start_fraction) * index) / (letters.length - 1)
          : 1,
      );
      return letter_element;
    });
  }

  function rounded_units(value, digit_count) {
    const scaled = Math.abs(value) * Math.pow(10, digit_count);
    const whole = Math.floor(scaled);
    return scaled - whole >= 0.5 ? whole + 1 : whole;
  }
  function fixed_text(value, digit_count) {
    const whole = rounded_units(value, digit_count);
    const sign = value < 0 && whole !== 0 ? "-" : "";
    const digits = String(whole).padStart(digit_count + 1, "0");
    if (!digit_count) return sign + digits;
    return (
      sign +
      digits.slice(0, digits.length - digit_count) +
      "." +
      digits.slice(digits.length - digit_count)
    );
  }
  function human_text(number) {
    let value = number,
      unit = "";
    for (const candidate of ["K", "M", "G", "T"]) {
      if (value < 999.5) break;
      value /= 1000;
      unit = candidate;
    }
    return (
      (unit && value < 9.95 ? fixed_text(value, 1) : fixed_text(value, 0)) +
      unit
    );
  }
  function percent_text(percent) {
    if (percent >= 9.95) return fixed_text(percent, 1) + "%";
    if (percent >= NUMBER_SMALLEST_PRINTED_PERCENT) {
      return fixed_text(percent, 2) + "%";
    }
    return percent > 0 ? "<0.01%" : "";
  }
  function multiple_text(percent) {
    if (percent <= 100) return percent_text(percent);
    const times = percent / 100;
    return times < MULTIPLE_UPPER_BOUND_TIMES
      ? fixed_text(times, 2) + "x"
      : ">1000x";
  }
  function signed_human_text(number) {
    if (!number) return "";
    return (number < 0 ? "-" : "") + human_text(Math.abs(number));
  }
  function signed_percent_text(percent) {
    if (!percent) return "";
    const arrow = percent < 0 ? "▼" : "▲";
    const sign = percent < 0 ? "-" : "";
    if (!Number.isFinite(percent)) return arrow + sign + "∞%";
    if (Math.abs(percent) < NUMBER_SMALLEST_PRINTED_PERCENT) {
      return arrow + "≈0.00%";
    }
    const body = multiple_text(Math.abs(percent));
    return arrow + (body[0] === ">" ? "" : sign) + body;
  }

  function parent_post(payload) {
    if (is_framed) window.parent.postMessage(payload, "*");
  }
  function hash_publish(canonical_hash) {
    if (canonical_hash !== location.hash) {
      history.replaceState(null, "", canonical_hash || "#");
    }
    parent_post({ report_ui: "hash_changed", hash: canonical_hash });
  }
  function parent_listen(on_parent_message) {
    window.addEventListener("message", (message_event) => {
      if (is_framed && message_event.source === window.parent) {
        on_parent_message(message_event.data);
      }
    });
  }

  function header_cells(table_element) {
    const header_row = table_element.tHead
      ? table_element.tHead.rows[0]
      : table_element.rows[0];
    return header_row ? [...header_row.cells] : [];
  }
  function listeners_bind(
    handle_bar,
    on_pointer_move,
    on_pointer_release,
    is_attaching,
  ) {
    const listener_method = is_attaching
      ? "addEventListener"
      : "removeEventListener";
    handle_bar[listener_method]("pointermove", on_pointer_move);
    handle_bar[listener_method]("pointerup", on_pointer_release);
    handle_bar[listener_method]("pointercancel", on_pointer_release);
  }
  function minimum_width_px(column_element) {
    const floor_px = column_element.dataset.min || column_element.dataset.w;
    if (!floor_px) return TABLE_COLUMN_NARROWEST_DRAG_PX;
    const probe_element = column_element.ownerDocument.createElement("div");
    probe_element.style.cssText =
      "position:absolute;visibility:hidden;width:" + floor_px;
    column_element.ownerDocument.body.appendChild(probe_element);
    const width_px = probe_element.getBoundingClientRect().width;
    probe_element.remove();
    return Math.max(TABLE_COLUMN_NARROWEST_DRAG_PX, Math.ceil(width_px));
  }
  function column_elements_of(table_element) {
    return [...table_element.querySelectorAll("colgroup > col")];
  }
  function handles_position(table_element) {
    const container_left_px =
      table_element.parentElement.getBoundingClientRect().left;
    const cells = header_cells(table_element);
    table_element.resize_handles.forEach((handle_bar, column_index) => {
      handle_bar.hidden = !cells[column_index];
      if (!cells[column_index]) return;
      const right = cells[column_index].getBoundingClientRect().right;
      handle_bar.style.left = right - container_left_px + "px";
    });
  }
  function handle_drag_begin(
    pointer_event,
    table_element,
    column_index,
    handle_bar,
  ) {
    const column_element = column_elements_of(table_element)[column_index];
    const header_cell = header_cells(table_element)[column_index];
    if (!column_element || !header_cell) return;
    table_element.was_hand_resized = true;
    const start_client_x = pointer_event.clientX,
      floor_px = minimum_width_px(column_element);
    const start_width_px = header_cell.getBoundingClientRect().width;
    handle_bar.classList.add("active");
    if (handle_bar.setPointerCapture) {
      handle_bar.setPointerCapture(pointer_event.pointerId);
    }
    const on_pointer_move = (move_event) => {
      const width = start_width_px + move_event.clientX - start_client_x;
      column_element.style.width = Math.max(floor_px, width) + "px";
      handles_position(table_element);
    };
    const on_pointer_release = () => {
      handle_bar.classList.remove("active");
      listeners_bind(handle_bar, on_pointer_move, on_pointer_release, false);
    };
    listeners_bind(handle_bar, on_pointer_move, on_pointer_release, true);
    pointer_event.preventDefault();
  }
  function handles_create(table_element) {
    if (table_element.resize_handles) return;
    const column_wrapper = table_element.parentElement;
    if (!column_wrapper.classList.contains("tbl-cols")) return;
    const column_elements = column_elements_of(table_element);
    for (const column_element of column_elements) {
      column_element.dataset.w = column_element.style.width;
    }
    table_element.resize_handles = [];
    for (
      let column_index = 0;
      column_index < column_elements.length;
      column_index++
    ) {
      const handle_bar = document.createElement("div");
      handle_bar.className = "bar";
      handle_bar.addEventListener("pointerdown", (pointer_event) =>
        handle_drag_begin(
          pointer_event,
          table_element,
          column_index,
          handle_bar,
        ),
      );
      column_wrapper.appendChild(handle_bar);
      table_element.resize_handles.push(handle_bar);
    }
  }
  function nearest_scroller(start_element) {
    let ancestor_element = start_element.parentElement;
    for (
      ;
      ancestor_element;
      ancestor_element = ancestor_element.parentElement
    ) {
      const overflow_y = getComputedStyle(ancestor_element).overflowY;
      if (overflow_y === "auto" || overflow_y === "scroll") {
        return ancestor_element;
      }
    }
    return document.documentElement;
  }
  function grow_column_fill(table_element) {
    if (!table_element.offsetWidth) return;
    const column_elements = column_elements_of(table_element);
    if (!column_elements.length) return;
    const grow_column =
      column_elements.find((column_element) =>
        column_element.classList.contains("grow"),
      ) || column_elements[column_elements.length - 1];
    grow_column.style.width = grow_column.dataset.w;
    const floor_px = minimum_width_px(grow_column);
    const scroll_container = nearest_scroller(table_element);
    const table_box = table_element.getBoundingClientRect();
    const edge_inset_px =
      table_box.left -
      scroll_container.getBoundingClientRect().left +
      scroll_container.scrollLeft;
    const target_width_px = Math.floor(
      scroll_container.clientWidth - 2 * edge_inset_px,
    );
    const other_columns_px =
      table_box.width - grow_column.getBoundingClientRect().width;
    grow_column.style.width =
      Math.max(floor_px, target_width_px - other_columns_px) + "px";
  }

  function offsets_align(scroll_container) {
    let stacked_top_px = 0;
    for (const band_element of scroll_container.querySelectorAll(
      ":scope > .band",
    )) {
      band_element.style.top = stacked_top_px + "px";
      stacked_top_px += band_element.getBoundingClientRect().height;
    }
    for (const header_cell of scroll_container.querySelectorAll("th")) {
      const owning_table = header_cell.closest(".tbl") || scroll_container;
      if (owning_table === scroll_container) {
        header_cell.style.top = stacked_top_px + "px";
      }
    }
  }
  function layout_refresh(root_element) {
    root_element = root_element || document.body;
    for (const table_element of root_element.querySelectorAll("table.cols")) {
      if (!table_element.resize_handles) continue;
      if (
        table_element.classList.contains("fill") &&
        !table_element.was_hand_resized
      ) {
        grow_column_fill(table_element);
      }
      handles_position(table_element);
    }
    const band_elements = [...root_element.querySelectorAll(".band")];
    new Set(
      band_elements.map((band_element) => band_element.parentElement),
    ).forEach(offsets_align);
  }
  function layout_activate(root_element) {
    root_element = root_element || document.body;
    for (const table_element of root_element.querySelectorAll("table.cols")) {
      handles_create(table_element);
    }
    layout_refresh(root_element);
  }
  function layout_reset(root_element) {
    root_element = root_element || document.body;
    for (const table_element of root_element.querySelectorAll("table.cols")) {
      if (!table_element.resize_handles) continue;
      for (const column_element of column_elements_of(table_element)) {
        column_element.style.width = column_element.dataset.w;
      }
      table_element.was_hand_resized = false;
      if (table_element.classList.contains("fill")) {
        grow_column_fill(table_element);
      }
      handles_position(table_element);
    }
    for (const pane_entry of registered_panes) {
      if (!root_element.contains(pane_entry.pane_element)) continue;
      pane_entry.pane_element.style.width = "";
      view_storage.value_write(pane_entry.storage_key, null);
    }
    layout_refresh(root_element);
  }

  function storage_sweep() {
    const doomed_keys = [];
    for (let index = 0; index < localStorage.length; index++) {
      const storage_key = localStorage.key(index);
      if (storage_key === null) continue;
      const is_owned =
        STORAGE_OWNED_KEYS.indexOf(storage_key) !== -1 ||
        STORAGE_OWNED_PREFIXES.some((prefix) =>
          storage_key.startsWith(prefix),
        );
      if (is_owned) doomed_keys.push(storage_key);
    }
    for (const storage_key of doomed_keys) {
      localStorage.removeItem(storage_key);
    }
  }
  function storage_version_check() {
    if (storage_is_checked) return;
    storage_is_checked = true;
    try {
      if (localStorage.getItem(STORAGE_VERSION_KEY) === STORAGE_VERSION) {
        return;
      }
      storage_sweep();
      localStorage.setItem(STORAGE_VERSION_KEY, STORAGE_VERSION);
    } catch (storage_error) {}
  }
  const view_storage = {
    value_read(storage_key) {
      storage_version_check();
      try {
        return JSON.parse(localStorage.getItem(storage_key));
      } catch (storage_error) {
        return null;
      }
    },
    value_write(storage_key, stored_value) {
      storage_version_check();
      try {
        if (stored_value == null) localStorage.removeItem(storage_key);
        else {
          localStorage.setItem(storage_key, JSON.stringify(stored_value));
        }
      } catch (storage_error) {}
    },
  };

  function pane_splitter_attach(
    handle_bar,
    pane_element,
    storage_key,
    minimum_px,
  ) {
    storage_key = "split." + storage_key;
    registered_panes.push({ pane_element, storage_key });
    const saved_width = view_storage.value_read(storage_key);
    if (saved_width) pane_element.style.width = saved_width + "px";
    handle_bar.addEventListener("pointerdown", (pointer_event) => {
      const start_client_x = pointer_event.clientX;
      const start_width_px = pane_element.getBoundingClientRect().width;
      handle_bar.classList.add("active");
      if (handle_bar.setPointerCapture) {
        handle_bar.setPointerCapture(pointer_event.pointerId);
      }
      let animation_frame = 0;
      const on_pointer_move = (move_event) => {
        const wanted_width_px = Math.max(
          minimum_px || PANE_SPLITTER_NARROWEST_PX,
          start_width_px + move_event.clientX - start_client_x,
        );
        pane_element.style.width =
          Math.min(
            window.innerWidth * PANE_SPLITTER_WIDEST_WINDOW_SHARE,
            wanted_width_px,
          ) + "px";
        if (animation_frame) return;
        animation_frame = requestAnimationFrame(() => {
          animation_frame = 0;
          layout_refresh();
        });
      };
      const on_pointer_release = () => {
        handle_bar.classList.remove("active");
        listeners_bind(handle_bar, on_pointer_move, on_pointer_release, false);
        view_storage.value_write(
          storage_key,
          pane_element.getBoundingClientRect().width,
        );
      };
      listeners_bind(handle_bar, on_pointer_move, on_pointer_release, true);
      pointer_event.preventDefault();
    });
  }

  window.addEventListener("resize", () => {
    clearTimeout(resize_debounce_timer);
    resize_debounce_timer = setTimeout(
      layout_refresh,
      LAYOUT_RESIZE_SETTLE_DELAY_MS,
    );
  });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => layout_activate());
  } else layout_activate();
  return {
    hash_publish,
    human_text,
    is_framed,
    layout_activate,
    layout_refresh,
    layout_reset,
    multiple_text,
    pane_splitter: { attach: pane_splitter_attach },
    parent_listen,
    parent_post,
    percent_text,
    logo_color_at,
    logo_letters_build,
    signed_human_text,
    signed_percent_text,
    view_storage,
  };
})();
