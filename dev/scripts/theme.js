window.Theme = (function () {
  "use strict";
  const MIN_COL = 24;

  function headerCells(table) {
    const row = table.tHead ? table.tHead.rows[0] : table.rows[0];
    return row ? [...row.cells] : [];
  }
  function layoutBars(table) {
    const left0 = table.parentElement.getBoundingClientRect().left;
    const cells = headerCells(table);
    table._bars.forEach((bar, index) => {
      bar.hidden = !cells[index];
      if (cells[index]) bar.style.left = (cells[index].getBoundingClientRect().right - left0) + "px";
    });
  }
  function drag(event, table, index, bar) {
    const col = table.querySelectorAll("colgroup > col")[index], cell = headerCells(table)[index];
    if (!col || !cell) return;
    table._dragged = true;
    const x0 = event.clientX, width0 = cell.getBoundingClientRect().width;
    bar.classList.add("active");
    if (bar.setPointerCapture) bar.setPointerCapture(event.pointerId);
    const move = moveEvent => { col.style.width = Math.max(MIN_COL, width0 + moveEvent.clientX - x0) + "px"; layoutBars(table); };
    const up = () => {
      bar.classList.remove("active");
      for (const [type, handler] of [["pointermove", move], ["pointerup", up], ["pointercancel", up]]) bar.removeEventListener(type, handler);
    };
    for (const [type, handler] of [["pointermove", move], ["pointerup", up], ["pointercancel", up]]) bar.addEventListener(type, handler);
    event.preventDefault();
  }


  function scrollerOf(el) {
    for (let ancestor = el.parentElement; ancestor; ancestor = ancestor.parentElement) {
      const overflowY = getComputedStyle(ancestor).overflowY;
      if (overflowY === "auto" || overflowY === "scroll") return ancestor;
    }
    return document.documentElement;
  }


  function fillTable(table) {
    if (!table.offsetWidth) return;
    const cols = [...table.querySelectorAll("colgroup > col")];
    if (!cols.length) return;
    const grow = cols.find(col => col.classList.contains("grow")) || cols[cols.length - 1];
    grow.style.width = grow.dataset.w;
    const min = grow.dataset.w ? grow.getBoundingClientRect().width : MIN_COL;
    const target = Math.floor(scrollerOf(table).clientWidth * (+table.dataset.fill || 0.9));
    const others = table.getBoundingClientRect().width - grow.getBoundingClientRect().width;
    grow.style.width = Math.max(min, target - others) + "px";
  }


  function initTable(table) {
    if (table._bars) return;
    const wrap = table.parentElement;
    if (!wrap.classList.contains("tbl-cols")) return;
    const cols = [...table.querySelectorAll("colgroup > col")];
    for (const col of cols) col.dataset.w = col.style.width;
    table._bars = [];
    for (let index = 0; index < cols.length; index++) {
      const bar = document.createElement("div");
      bar.className = "bar";
      bar.title = "drag to resize";
      bar.addEventListener("pointerdown", event => drag(event, table, index, bar));
      wrap.appendChild(bar);
      table._bars.push(bar);
    }
  }


  function resetCols(root) {
    root = root || document.body;
    for (const table of root.querySelectorAll("table.cols")) {
      if (!table._bars) continue;
      for (const col of table.querySelectorAll("colgroup > col")) col.style.width = col.dataset.w;
      table._dragged = false;
      if (table.classList.contains("fill")) fillTable(table);
      layoutBars(table);
    }
  }

  function alignSticky(scroller) {
    let top = 0;
    for (const band of scroller.querySelectorAll(":scope > .band")) {
      band.style.top = top + "px";
      top += band.getBoundingClientRect().height;
    }

    for (const headerCell of scroller.querySelectorAll("th")) if ((headerCell.closest(".tbl") || scroller) === scroller) headerCell.style.top = top + "px";
  }
  function relayout(root) {
    root = root || document.body;
    for (const table of root.querySelectorAll("table.cols")) {
      if (!table._bars) continue;
      if (table.classList.contains("fill") && !table._dragged) fillTable(table);
      layoutBars(table);
    }
    new Set([...root.querySelectorAll(".band")].map(band => band.parentElement)).forEach(alignSticky);
  }
  function init(root) {
    root = root || document.body;
    for (const table of root.querySelectorAll("table.cols")) initTable(table);
    relayout(root);
  }


  const store = {
    get(key) { try { return JSON.parse(localStorage.getItem(key)); } catch (error) { return null; } },
    set(key, value) { try { if (value == null) localStorage.removeItem(key); else localStorage.setItem(key, JSON.stringify(value)); } catch (error) {} },
  };
  function splitter(bar, pane, key, min) {
    key = "split." + key;
    const saved = store.get(key);
    if (saved) pane.style.width = saved + "px";
    bar.addEventListener("pointerdown", event => {
      const x0 = event.clientX, width0 = pane.getBoundingClientRect().width;
      bar.classList.add("active");
      if (bar.setPointerCapture) bar.setPointerCapture(event.pointerId);
      let frame = 0;
      const move = moveEvent => {
        pane.style.width = Math.min(window.innerWidth * 0.6, Math.max(min || 120, width0 + moveEvent.clientX - x0)) + "px";
        if (!frame) frame = requestAnimationFrame(() => { frame = 0; relayout(); });
      };
      const up = () => {
        bar.classList.remove("active");
        for (const [type, handler] of [["pointermove", move], ["pointerup", up], ["pointercancel", up]]) bar.removeEventListener(type, handler);
        store.set(key, pane.getBoundingClientRect().width);
      };
      for (const [type, handler] of [["pointermove", move], ["pointerup", up], ["pointercancel", up]]) bar.addEventListener(type, handler);
      event.preventDefault();
    });
  }

  let timer = null;
  window.addEventListener("resize", () => {
    clearTimeout(timer);
    timer = setTimeout(relayout, 120);
  });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => init());
  else init();
  return { init, relayout, resetCols, splitter, store };
})();
