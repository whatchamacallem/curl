window.Theme = (function () {
  "use strict";
  const MIN_COL = 24;

  function headerCells(table) {
    const row = table.tHead ? table.tHead.rows[0] : table.rows[0];
    return row ? [...row.cells] : [];
  }
  function layoutBars(table) {
    const x0 = table.parentElement.getBoundingClientRect().left;
    const cells = headerCells(table);
    table._bars.forEach((bar, i) => {
      bar.hidden = !cells[i];
      if (cells[i]) bar.style.left = (cells[i].getBoundingClientRect().right - x0) + "px";
    });
  }
  function drag(e, table, i, bar) {
    const col = table.querySelectorAll("colgroup > col")[i], cell = headerCells(table)[i];
    if (!col || !cell) return;
    table._dragged = true;
    const x0 = e.clientX, w0 = cell.getBoundingClientRect().width;
    bar.classList.add("active");
    if (bar.setPointerCapture) bar.setPointerCapture(e.pointerId);
    const move = ev => { col.style.width = Math.max(MIN_COL, w0 + ev.clientX - x0) + "px"; layoutBars(table); };
    const up = () => {
      bar.classList.remove("active");
      for (const [t, f] of [["pointermove", move], ["pointerup", up], ["pointercancel", up]]) bar.removeEventListener(t, f);
    };
    for (const [t, f] of [["pointermove", move], ["pointerup", up], ["pointercancel", up]]) bar.addEventListener(t, f);
    e.preventDefault();
  }


  function scrollerOf(el) {
    for (let p = el.parentElement; p; p = p.parentElement) {
      const o = getComputedStyle(p).overflowY;
      if (o === "auto" || o === "scroll") return p;
    }
    return document.documentElement;
  }


  function fillTable(table) {
    if (!table.offsetWidth) return;
    const cols = [...table.querySelectorAll("colgroup > col")];
    if (!cols.length) return;
    const grow = cols.find(c => c.classList.contains("grow")) || cols[cols.length - 1];
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
    for (const c of cols) c.dataset.w = c.style.width;
    table._bars = [];
    for (let i = 0; i < cols.length; i++) {
      const bar = document.createElement("div");
      bar.className = "bar";
      bar.title = "drag to resize";
      bar.addEventListener("pointerdown", e => drag(e, table, i, bar));
      wrap.appendChild(bar);
      table._bars.push(bar);
    }
  }


  function resetCols(root) {
    root = root || document.body;
    for (const t of root.querySelectorAll("table.cols")) {
      if (!t._bars) continue;
      for (const c of t.querySelectorAll("colgroup > col")) c.style.width = c.dataset.w;
      t._dragged = false;
      if (t.classList.contains("fill")) fillTable(t);
      layoutBars(t);
    }
  }

  function alignSticky(scroller) {
    let y = 0;
    for (const band of scroller.querySelectorAll(":scope > .band")) {
      band.style.top = y + "px";
      y += band.getBoundingClientRect().height;
    }

    for (const th of scroller.querySelectorAll("th")) if ((th.closest(".tbl") || scroller) === scroller) th.style.top = y + "px";
  }
  function relayout(root) {
    root = root || document.body;
    for (const t of root.querySelectorAll("table.cols")) {
      if (!t._bars) continue;
      if (t.classList.contains("fill") && !t._dragged) fillTable(t);
      layoutBars(t);
    }
    new Set([...root.querySelectorAll(".band")].map(b => b.parentElement)).forEach(alignSticky);
  }
  function init(root) {
    root = root || document.body;
    for (const t of root.querySelectorAll("table.cols")) initTable(t);
    relayout(root);
  }


  const store = {
    get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } },
    set(k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
  };
  function splitter(bar, pane, key, min) {
    key = "split." + key;
    const saved = store.get(key);
    if (saved) pane.style.width = saved + "px";
    bar.addEventListener("pointerdown", e => {
      const x0 = e.clientX, w0 = pane.getBoundingClientRect().width;
      bar.classList.add("active");
      if (bar.setPointerCapture) bar.setPointerCapture(e.pointerId);
      let raf = 0;
      const move = ev => {
        pane.style.width = Math.min(window.innerWidth * 0.6, Math.max(min || 120, w0 + ev.clientX - x0)) + "px";
        if (!raf) raf = requestAnimationFrame(() => { raf = 0; relayout(); });
      };
      const up = () => {
        bar.classList.remove("active");
        for (const [t, f] of [["pointermove", move], ["pointerup", up], ["pointercancel", up]]) bar.removeEventListener(t, f);
        store.set(key, pane.getBoundingClientRect().width);
      };
      for (const [t, f] of [["pointermove", move], ["pointerup", up], ["pointercancel", up]]) bar.addEventListener(t, f);
      e.preventDefault();
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
