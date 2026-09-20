window.report_ui = (function () {
  "use strict";
  const MINIMUM_COLUMN_PX = 24;

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
  function header_cells(table_element) {
    const header_row = table_element.tHead
      ? table_element.tHead.rows[0]
      : table_element.rows[0];
    return header_row ? [...header_row.cells] : [];
  }
  function minimum_width_px(column_element) {
    const floor_px = column_element.dataset.min || column_element.dataset.w;
    if (!floor_px) return MINIMUM_COLUMN_PX;
    const probe_element = column_element.ownerDocument.createElement("div");
    probe_element.style.cssText =
      "position:absolute;visibility:hidden;width:" + floor_px;
    column_element.ownerDocument.body.appendChild(probe_element);
    const width_px = probe_element.getBoundingClientRect().width;
    probe_element.remove();
    return Math.max(MINIMUM_COLUMN_PX, Math.ceil(width_px));
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
    const column_element =
      table_element.querySelectorAll("colgroup > col")[column_index];
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
    const column_elements = [
      ...table_element.querySelectorAll("colgroup > col"),
    ];
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

  function handles_create(table_element) {
    if (table_element.resize_handles) return;
    const column_wrapper = table_element.parentElement;
    if (!column_wrapper.classList.contains("tbl-cols")) return;
    const column_elements = [
      ...table_element.querySelectorAll("colgroup > col"),
    ];
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
      handle_bar.title = "drag to resize";
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

  const registered_panes = [];
  function layout_reset(root_element) {
    root_element = root_element || document.body;
    for (const table_element of root_element.querySelectorAll("table.cols")) {
      if (!table_element.resize_handles) continue;
      for (const column_element of table_element.querySelectorAll(
        "colgroup > col",
      )) {
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

  const view_storage = {
    value_read(storage_key) {
      try {
        return JSON.parse(localStorage.getItem(storage_key));
      } catch (storage_error) {
        return null;
      }
    },
    value_write(storage_key, stored_value) {
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
          minimum_px || 120,
          start_width_px + move_event.clientX - start_client_x,
        );
        pane_element.style.width =
          Math.min(window.innerWidth * 0.6, wanted_width_px) + "px";
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

  let resize_debounce_timer = null;
  window.addEventListener("resize", () => {
    clearTimeout(resize_debounce_timer);
    resize_debounce_timer = setTimeout(layout_refresh, 120);
  });
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => layout_activate());
  } else layout_activate();
  return {
    layout_activate,
    layout_refresh,
    layout_reset,
    pane_splitter: { attach: pane_splitter_attach },
    view_storage,
  };
})();
