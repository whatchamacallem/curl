// Shared behaviour for every page dev/perf2html.sh writes (inlined by theme.py).
//
//   table.cols   every column boundary gets a full-height divider bar that
//                can be dragged to resize the column on its left; widths are
//                remembered in localStorage under "cols.<data-key>".
//   .band + th   sticky elements inside one scroller are stacked in DOM
//                order (a legend above a header row) instead of overlapping.
//   splitter()   a draggable divider between two panes, width remembered
//                under "cols.<key>" as well.
//   reset()      drops every saved width and puts every table and splitter
//                on the page back to its default. The frame page's
//                [reset columns] link calls it and posts "theme:reset" to
//                the page in its iframe, which does the same for itself.
//
// Pages that render tables at runtime call Theme.init(container) after each
// render; static pages are initialised on DOMContentLoaded.
window.Theme = (function () {
  "use strict";
  const PREFIX = "cols.";
  const store = {
    get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } },
    set(k, v) { try { if (v == null) localStorage.removeItem(k); else localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} },
    keys() { try { return Object.keys(localStorage); } catch (e) { return []; } },
  };
  const MIN_COL = 24;
  const splitters = [];  // {pane} for reset()

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
  // Saved widths are keyed by header label (by index for header-less tables)
  // so they survive a column being added or dropped between profiles.
  function colKey(table, i) {
    const cell = table.tHead && headerCells(table)[i];
    return (cell && cell.textContent.trim()) || String(i);
  }
  // Saved widths carry the viewport width they were dragged at (_vw) and are
  // only honoured while the window is still that width: a pixel width
  // dragged at one window size stops meaning anything at another, so a
  // stored set from a since-resized window is dropped instead of applied
  // (getSaved) and every stored set is dropped outright the moment a resize
  // is actually seen (the "resize" listener below) -- both are needed since
  // a page can be reloaded at a new size without an in-page resize firing.
  function getSaved(table) {
    if (!table.dataset.key) return null;
    const saved = store.get(PREFIX + table.dataset.key);
    return (saved && saved._vw === window.innerWidth) ? saved : null;
  }
  function saveWidths(table) {
    if (!table.dataset.key) return;
    const o = { _vw: window.innerWidth };
    table.querySelectorAll("colgroup > col").forEach((c, i) => { if (c.style.width !== c.dataset.w) o[colKey(table, i)] = c.style.width; });
    store.set(PREFIX + table.dataset.key, Object.keys(o).length > 1 ? o : null);
  }
  function drag(e, table, i, bar) {
    const col = table.querySelectorAll("colgroup > col")[i], cell = headerCells(table)[i];
    if (!col || !cell) return;
    const x0 = e.clientX, w0 = cell.getBoundingClientRect().width;
    bar.classList.add("active");
    if (bar.setPointerCapture) bar.setPointerCapture(e.pointerId);
    const move = ev => { col.style.width = Math.max(MIN_COL, w0 + ev.clientX - x0) + "px"; layoutBars(table); };
    const up = () => {
      bar.classList.remove("active");
      for (const [t, f] of [["pointermove", move], ["pointerup", up], ["pointercancel", up]]) bar.removeEventListener(t, f);
      saveWidths(table);
    };
    for (const [t, f] of [["pointermove", move], ["pointerup", up], ["pointercancel", up]]) bar.addEventListener(t, f);
    e.preventDefault();
  }
  // The 90%-of-viewport baseline a `fill` table's open-ended last column
  // gets on first render (see initTable): computed the same way regardless
  // of whether a saved width is about to be applied on top, so it is always
  // the column's real default -- what [reset columns] restores and what
  // saveWidths compares a drag against to decide whether a column differs
  // from default at all.
  function fillBaseline(table, cols) {
    const last = cols[cols.length - 1];
    const target = window.innerWidth * 0.9;
    const others = table.getBoundingClientRect().width - last.getBoundingClientRect().width;
    return Math.max(MIN_COL, target - others) + "px";
  }
  function initTable(table) {
    if (table._bars) return;
    const wrap = table.parentElement;
    if (!wrap.classList.contains("tbl-cols")) return;
    const cols = [...table.querySelectorAll("colgroup > col")];
    if (table.classList.contains("fill") && cols.length) {
      // Establish the natural 90%-of-viewport width on the open-ended last
      // column *before* looking at any saved override, so dataset.w below
      // always captures the real default -- otherwise, on a repeat visit
      // with a saved width for some other column, this column's default
      // would never be computed at all and [reset columns] would collapse
      // it back to auto/0 instead of the 90% baseline.
      cols[cols.length - 1].style.width = fillBaseline(table, cols);
    }
    for (const c of cols) c.dataset.w = c.style.width;
    const saved = getSaved(table);
    if (saved) cols.forEach((c, i) => { const w = saved[colKey(table, i)]; if (w) c.style.width = w; });
    table._bars = [];
    for (let i = 0; i < cols.length; i++) {
      const bar = document.createElement("div");
      bar.className = "bar";
      bar.title = "drag to resize";
      bar.addEventListener("pointerdown", e => drag(e, table, i, bar));
      wrap.appendChild(bar);
      table._bars.push(bar);
    }
    layoutBars(table);
  }

  function alignSticky(scroller) {
    let y = 0;
    for (const band of scroller.querySelectorAll(":scope > .band")) {
      band.style.top = y + "px";
      y += band.getBoundingClientRect().height;
    }
    // header cells of tables that scroll with this scroller, not of a nested .tbl box
    for (const th of scroller.querySelectorAll("th")) if ((th.closest(".tbl") || scroller) === scroller) th.style.top = y + "px";
  }
  function relayout(root) {
    root = root || document.body;
    for (const t of root.querySelectorAll("table.cols")) if (t._bars) layoutBars(t);
    new Set([...root.querySelectorAll(".band")].map(b => b.parentElement)).forEach(alignSticky);
  }
  function init(root) {
    root = root || document.body;
    for (const t of root.querySelectorAll("table.cols")) initTable(t);
    relayout(root);
  }

  function reset() {
    for (const k of store.keys()) if (k.startsWith(PREFIX)) store.set(k, null);
    for (const t of document.querySelectorAll("table.cols")) if (t._bars) {
      for (const c of t.querySelectorAll("colgroup > col")) c.style.width = c.dataset.w;
    }
    for (const s of splitters) s.pane.style.width = "";
    relayout();
  }

  function splitter(bar, pane, key, min) {
    key = PREFIX + key;
    splitters.push({ pane });
    const saved = store.get(key);
    if (saved) pane.style.width = saved + "px";
    bar.addEventListener("pointerdown", e => {
      const x0 = e.clientX, w0 = pane.getBoundingClientRect().width;
      bar.classList.add("active");
      if (bar.setPointerCapture) bar.setPointerCapture(e.pointerId);
      const move = ev => {
        pane.style.width = Math.min(window.innerWidth * 0.6, Math.max(min || 120, w0 + ev.clientX - x0)) + "px";
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

  // A resize invalidates every saved column width outright (not just the
  // ones for tables on screen right now -- a table in a not-currently-shown
  // frame has just as stale a saved width once the window has moved), so
  // the next time each is opened it falls back to its natural/90% default
  // instead of reapplying a pixel width that made sense at the old size.
  function purgeStaleWidths() {
    for (const k of store.keys()) {
      if (!k.startsWith(PREFIX)) continue;
      const v = store.get(k);
      if (v && typeof v === "object" && v._vw !== window.innerWidth) store.set(k, null);
    }
  }
  let timer = null;
  window.addEventListener("resize", () => {
    clearTimeout(timer);
    timer = setTimeout(() => { purgeStaleWidths(); relayout(); }, 120);
  });
  window.addEventListener("message", e => { if (e.data === "theme:reset") reset(); });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => init());
  else init();
  return { init, relayout, reset, splitter, store };
})();
