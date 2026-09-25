window.report_ui = (function () {
  "use strict";

  const CSS_LAYOUT = settings("CSS_LAYOUT");
  const DESIGN_COORDINATES_WIDTH_PX = settings("DESIGN_COORDINATES_WIDTH_PX");
  const DESIGN_FONT_CHARACTER_WIDTH_PX = settings(
    "DESIGN_FONT_CHARACTER_WIDTH_PX",
  );
  const DESIGN_FONT_FIT_PROPERTY = settings("DESIGN_FONT_FIT_PROPERTY");
  const DESIGN_FONT_SIZE_PX = settings("DESIGN_FONT_SIZE_PX");
  const DESIGN_SCALE_DEFAULT_MULTIPLE = settings(
    "DESIGN_SCALE_DEFAULT_MULTIPLE",
  );
  const DESIGN_SCALE_DEFAULT_TRAVEL_SHARE = settings(
    "DESIGN_SCALE_DEFAULT_TRAVEL_SHARE",
  );
  const DESIGN_SCALE_LARGEST_MULTIPLE = settings(
    "DESIGN_SCALE_LARGEST_MULTIPLE",
  );
  const DESIGN_SCALE_SMALLEST_MULTIPLE = settings(
    "DESIGN_SCALE_SMALLEST_MULTIPLE",
  );
  const DESIGN_VIEWPORT_HEIGHT_PROPERTY = settings(
    "DESIGN_VIEWPORT_HEIGHT_PROPERTY",
  );
  const HEAT_COLOR_LOGO_STOPS = settings("HEAT_COLOR_LOGO_STOPS");
  const LAYOUT_RESIZE_SETTLE_DELAY_MS = settings(
    "LAYOUT_RESIZE_SETTLE_DELAY_MS",
  );
  const NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES = settings(
    "NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES",
  );
  const NUMBER_SMALLEST_PRINTED_PERCENT = settings(
    "NUMBER_SMALLEST_PRINTED_PERCENT",
  );
  const PAGE_FONT_FAMILY = settings("PAGE_FONT_FAMILY");
  const PANE_SPLITTER_WIDEST_WINDOW_SHARE = settings(
    "PANE_SPLITTER_WIDEST_WINDOW_SHARE",
  );
  const STORAGE_OWNED_KEYS = settings("STORAGE_OWNED_KEYS");
  const STORAGE_OWNED_PREFIXES = settings("STORAGE_OWNED_PREFIXES");
  const STORAGE_VERSION = settings("STORAGE_VERSION");
  const STORAGE_VERSION_KEY = settings("STORAGE_VERSION_KEY");
  const TABLE_COLUMN_EXTRA_WIDTH_CHARS = settings(
    "TABLE_COLUMN_EXTRA_WIDTH_CHARS",
  );
  const TABLE_COLUMN_NARROWEST_DRAG_PX = settings(
    "TABLE_COLUMN_NARROWEST_DRAG_PX",
  );
  const TABLE_GROW_COLUMN_NARROWEST_CHARS = settings(
    "TABLE_GROW_COLUMN_NARROWEST_CHARS",
  );

  // what CSS measures a ch as: the advance width of this glyph
  const CH_UNIT_GLYPH = "0";
  const RAMP_CHANNEL_STOPS = HEAT_COLOR_LOGO_STOPS.map((hex) =>
    [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16)),
  );

  const is_framed = window.parent !== window;
  const registered_panes = [];
  let resize_debounce_timer = null;
  let storage_is_checked = false;
  let design_scale = 1;
  // ends out of order would run a slider half backwards: a broken setting
  if (
    !(DESIGN_SCALE_SMALLEST_MULTIPLE < DESIGN_SCALE_DEFAULT_MULTIPLE) ||
    !(DESIGN_SCALE_DEFAULT_MULTIPLE < DESIGN_SCALE_LARGEST_MULTIPLE)
  ) {
    throw new Error(
      "str_error_scale_ends_disordered " +
        `${DESIGN_SCALE_SMALLEST_MULTIPLE} ${DESIGN_SCALE_DEFAULT_MULTIPLE} ` +
        `${DESIGN_SCALE_LARGEST_MULTIPLE}`,
    );
  }
  let design_scale_travel = design_scale_travel_of(
    DESIGN_SCALE_DEFAULT_MULTIPLE,
  );

  function ramp_channels_at(fraction) {
    const scaled_position = fraction * (RAMP_CHANNEL_STOPS.length - 1);
    const index = Math.min(
      Math.max(Math.floor(scaled_position), 0),
      RAMP_CHANNEL_STOPS.length - 2,
    );
    const step_fraction = scaled_position - index;
    return [0, 1, 2].map((channel) => {
      const low_channel = RAMP_CHANNEL_STOPS[index][channel],
        high_channel = RAMP_CHANNEL_STOPS[index + 1][channel];
      return Math.round(
        low_channel + (high_channel - low_channel) * step_fraction,
      );
    });
  }
  function logo_color_at(fraction) {
    return `rgb(${ramp_channels_at(fraction).join(",")})`;
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

  // One half of the slider: the multiples it runs between and the travel
  // it covers. The lower half ends at the default, the upper starts at it.
  function design_scale_half_of(is_lower_half) {
    return is_lower_half
      ? {
          from_multiple: DESIGN_SCALE_SMALLEST_MULTIPLE,
          to_multiple: DESIGN_SCALE_DEFAULT_MULTIPLE,
          travel_start: 0,
          travel_width: DESIGN_SCALE_DEFAULT_TRAVEL_SHARE,
        }
      : {
          from_multiple: DESIGN_SCALE_DEFAULT_MULTIPLE,
          to_multiple: DESIGN_SCALE_LARGEST_MULTIPLE,
          travel_start: DESIGN_SCALE_DEFAULT_TRAVEL_SHARE,
          travel_width: 1 - DESIGN_SCALE_DEFAULT_TRAVEL_SHARE,
        };
  }
  // The multiple of the window's own fit the slider is asking for: each
  // half climbs geometrically, so a step feels the same at either end.
  function design_scale_multiple_of(travel_fraction) {
    const half = design_scale_half_of(
      travel_fraction < DESIGN_SCALE_DEFAULT_TRAVEL_SHARE,
    );
    const half_fraction =
      (travel_fraction - half.travel_start) / half.travel_width;
    return (
      half.from_multiple *
      Math.pow(half.to_multiple / half.from_multiple, half_fraction)
    );
  }
  // The travel a multiple sits at, the inverse of the above. Only the two
  // ends' own span is a travel: anything past them is a broken setting.
  function design_scale_travel_of(multiple) {
    if (
      !(multiple >= DESIGN_SCALE_SMALLEST_MULTIPLE) ||
      !(multiple <= DESIGN_SCALE_LARGEST_MULTIPLE)
    ) {
      throw new Error(
        `str_error_scale_multiple_outside ${multiple} ` +
          `${DESIGN_SCALE_SMALLEST_MULTIPLE} ${DESIGN_SCALE_LARGEST_MULTIPLE}`,
      );
    }
    const half = design_scale_half_of(
      multiple < DESIGN_SCALE_DEFAULT_MULTIPLE,
    );
    const half_fraction =
      Math.log(multiple / half.from_multiple) /
      Math.log(half.to_multiple / half.from_multiple);
    return half.travel_start + half_fraction * half.travel_width;
  }
  function design_scale_of(viewport_width_px) {
    const fitted = viewport_width_px / DESIGN_COORDINATES_WIDTH_PX;
    return fitted * design_scale_multiple_of(design_scale_travel);
  }
  function design_scale_travel_now() {
    return design_scale_travel;
  }
  // Take the slider's new position and redraw at it, the way a resize does.
  // A framed page never calls this: it inherits its parent's zoom.
  function design_scale_travel_set(travel_fraction) {
    if (!isFinite(travel_fraction)) {
      throw new Error("str_error_scale_unusable " + travel_fraction);
    }
    design_scale_travel = Math.min(Math.max(travel_fraction, 0), 1);
    design_scale_settle();
  }
  // Fit the box's font to the design font: measure what its ch comes out
  // as at the design size, and scale every font size so a ch is the design ch.
  function font_fit_apply() {
    const context = document.createElement("canvas").getContext("2d");
    const wanted_font = `${DESIGN_FONT_SIZE_PX}px ${PAGE_FONT_FAMILY}`;
    const default_font = context.font;
    context.font = wanted_font;
    // a font string the canvas cannot read leaves its default in place
    if (context.font === default_font) {
      throw new Error("str_error_font_refused");
    }
    const measured_px = context.measureText(CH_UNIT_GLYPH).width;
    document.documentElement.style.setProperty(
      DESIGN_FONT_FIT_PROPERTY,
      String(DESIGN_FONT_CHARACTER_WIDTH_PX / measured_px),
    );
  }
  function design_scale_apply() {
    const root_element = document.documentElement;
    // a framed document is laid out inside an already-zoomed parent, so its
    // own box is design space already and it scales itself by 1
    const wanted = is_framed ? 1 : design_scale_of(root_element.clientWidth);
    if (!isFinite(wanted) || !(wanted > 0)) {
      throw new Error("str_error_scale_unusable " + wanted);
    }
    design_scale = wanted;
    root_element.style.zoom = String(wanted);
    // a vh resolves against the unzoomed window and is then zoomed with
    // everything else, so a full-height rule reads this design-space height
    root_element.style.setProperty(
      DESIGN_VIEWPORT_HEIGHT_PROPERTY,
      root_element.clientHeight / wanted + "px",
    );
  }
  function design_scale_now() {
    return design_scale;
  }
  function design_px(screen_px) {
    return screen_px / design_scale;
  }
  function screen_px(design_length_px) {
    return design_length_px * design_scale;
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
    return times < NUMBER_LARGEST_PRINTED_MULTIPLE_TIMES
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

  function width_total(widths) {
    return widths.reduce((total, width) => total + width, 0);
  }
  // theme.py's Theme has the twin of each column_ function below, under the
  // same name, doing the same arithmetic, so both kinds of page agree
  function column_longest(cell_rows, column_index) {
    let longest = 0;
    for (const row of cell_rows) {
      longest = Math.max(longest, row[column_index].text.length);
    }
    return longest;
  }
  function column_extents(columns, cell_rows, grow_index) {
    return columns.map((column, column_index) => {
      let content_chars;
      if (column.width != null) content_chars = column.width;
      else if (CSS_LAYOUT && column_index === grow_index) {
        content_chars = TABLE_GROW_COLUMN_NARROWEST_CHARS;
      } else {
        content_chars = column_longest(cell_rows, column_index);
        if (column.clip != null) {
          content_chars = Math.min(content_chars, column.clip);
        }
      }
      return { heading_chars: column.label.length, content_chars };
    });
  }
  function column_limits(extent) {
    const narrowest = CSS_LAYOUT ? extent.content_chars : extent.heading_chars;
    const widest = Math.max(extent.heading_chars, extent.content_chars);
    return [
      narrowest + TABLE_COLUMN_EXTRA_WIDTH_CHARS,
      widest + TABLE_COLUMN_EXTRA_WIDTH_CHARS,
    ];
  }
  // Under CSS_LAYOUT, automatic table layout on the container's 100cqw: all
  // widest if they fit, all narrowest if not even those, else between
  function column_width_text(limits, column_index, grow_index) {
    const [narrowest, widest] = limits[column_index];
    if (!CSS_LAYOUT) return widest + "ch";
    const shared = limits.filter(
      (limit, other_index) => other_index !== grow_index,
    );
    const low_total = width_total(shared.map((limit) => limit[0]));
    const high_total = width_total(shared.map((limit) => limit[1]));
    if (column_index === grow_index) {
      return (
        `max(${narrowest}ch, 100cqw - clamp(${low_total}ch, ` +
        `100cqw - ${narrowest}ch, ${high_total}ch))`
      );
    }
    if (narrowest === widest) return narrowest + "ch";
    const grow_narrowest = grow_index >= 0 ? limits[grow_index][0] : 0;
    return (
      `clamp(${narrowest}ch, ${narrowest}ch + (100cqw - ` +
      `${low_total + grow_narrowest}ch) * ${widest - narrowest} / ` +
      `${high_total - low_total}, ${widest}ch)`
    );
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
  // Both table emitters write data-min on every <col>: one without it is
  // markup this file does not know, so it throws
  function floor_text_read(column_element) {
    const floor_text = column_element.dataset.min;
    if (!floor_text) throw new Error("table <col> has no data-min");
    return floor_text;
  }
  function minimum_width_px(column_element) {
    const probe_element = column_element.ownerDocument.createElement("div");
    probe_element.style.cssText =
      "position:absolute;visibility:hidden;width:" +
      floor_text_read(column_element);
    column_element.ownerDocument.body.appendChild(probe_element);
    const width_px = design_px(probe_element.getBoundingClientRect().width);
    probe_element.remove();
    return Math.max(TABLE_COLUMN_NARROWEST_DRAG_PX, Math.ceil(width_px));
  }
  // A drag is in pixels. Under CSS_LAYOUT its floor stays the <col>'s own
  // characters, which CSS max() compares, where the old layout probes them
  function drag_width_formatter(column_element) {
    if (CSS_LAYOUT) {
      const floor_text = floor_text_read(column_element);
      return (width_px) => `max(${floor_text}, ${width_px}px)`;
    }
    const floor_px = minimum_width_px(column_element);
    return (width_px) => Math.max(floor_px, width_px) + "px";
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
      handle_bar.style.left = design_px(right - container_left_px) + "px";
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
      width_text_of = drag_width_formatter(column_element);
    // a rect and clientX are screen px on a zoomed page; a style is design px
    const start_width_px = design_px(
      header_cell.getBoundingClientRect().width,
    );
    handle_bar.classList.add("active");
    if (handle_bar.setPointerCapture) {
      handle_bar.setPointerCapture(pointer_event.pointerId);
    }
    const on_pointer_move = (move_event) => {
      const width =
        start_width_px + design_px(move_event.clientX - start_client_x);
      column_element.style.width = width_text_of(width);
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
      design_px(
        table_box.left - scroll_container.getBoundingClientRect().left,
      ) + scroll_container.scrollLeft;
    const target_width_px = Math.floor(
      scroll_container.clientWidth - 2 * edge_inset_px,
    );
    const other_columns_px = design_px(
      table_box.width - grow_column.getBoundingClientRect().width,
    );
    grow_column.style.width =
      Math.max(floor_px, target_width_px - other_columns_px) + "px";
  }

  function offsets_align(scroll_container) {
    let stacked_top_px = 0;
    for (const band_element of scroll_container.querySelectorAll(
      ":scope > .band",
    )) {
      band_element.style.top = stacked_top_px + "px";
      stacked_top_px += design_px(band_element.getBoundingClientRect().height);
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
        !CSS_LAYOUT &&
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
      if (!CSS_LAYOUT && table_element.classList.contains("fill")) {
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
      const start_width_px = design_px(
        pane_element.getBoundingClientRect().width,
      );
      handle_bar.classList.add("active");
      if (handle_bar.setPointerCapture) {
        handle_bar.setPointerCapture(pointer_event.pointerId);
      }
      let animation_frame = 0;
      const on_pointer_move = (move_event) => {
        const wanted_width_px = Math.max(
          minimum_px,
          start_width_px + design_px(move_event.clientX - start_client_x),
        );
        pane_element.style.width =
          Math.min(
            design_px(window.innerWidth) * PANE_SPLITTER_WIDEST_WINDOW_SHARE,
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
          design_px(pane_element.getBoundingClientRect().width),
        );
      };
      listeners_bind(handle_bar, on_pointer_move, on_pointer_release, true);
      pointer_event.preventDefault();
    });
  }

  // Redraw at the scale in force and settle the layout after it. The one
  // path a resize and a scale change both take.
  function design_scale_settle() {
    design_scale_apply();
    clearTimeout(resize_debounce_timer);
    resize_debounce_timer = setTimeout(
      layout_refresh,
      LAYOUT_RESIZE_SETTLE_DELAY_MS,
    );
  }

  font_fit_apply();
  design_scale_apply();
  window.addEventListener("resize", design_scale_settle);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => layout_activate());
  } else layout_activate();
  return {
    column_extents,
    column_limits,
    column_longest,
    column_width_text,
    design_px,
    design_scale_apply,
    design_scale_now,
    design_scale_travel_now,
    design_scale_travel_set,
    hash_publish,
    human_text,
    is_framed,
    layout_activate,
    layout_refresh,
    layout_reset,
    logo_color_at,
    logo_letters_build,
    multiple_text,
    pane_splitter: { attach: pane_splitter_attach },
    parent_listen,
    parent_post,
    percent_text,
    ramp_channels_at,
    screen_px,
    signed_human_text,
    signed_percent_text,
    view_storage,
  };
})();
