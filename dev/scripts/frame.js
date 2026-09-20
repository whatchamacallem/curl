(function () {
  const bar = document.getElementById("bar");
  const home = document.getElementById("home");
  const view = document.getElementById("view");
  const titleElement = document.getElementById("title");
  const links = [...bar.querySelectorAll("a[data-view]")];
  const util = document.getElementById("util");
  const framed = window.parent !== window;
  let page = "", state = "", title = titleElement.textContent;
  function setTitle(newTitle) {
    title = newTitle;
    titleElement.textContent = framed ? "" : newTitle;
    document.title = newTitle;
    if (!framed) return;
    window.parent.postMessage({ theme: "title", title: newTitle }, "*");
  }

  function parse(hash) {
    const match = /^#([\w-]*)(?:\/(.*))?$/.exec(hash || "");
    return match ? [match[1], match[2] ? "#" + match[2] : ""] : ["", ""];
  }
  const build = (key, sub) =>
    key ? "#" + key + (sub ? "/" + sub.slice(1) : "") : "";
  function sync(hash) {
    if (hash !== location.hash) history.replaceState(null, "", hash || "#");
    if (framed) window.parent.postMessage({ theme: "hash", hash: hash }, "*");
  }
  function show(hash) {
    const [key, sub] = parse(hash);
    const link = links.find(anchor => anchor.dataset.view === key);
    const current = link || links[0];
    for (const anchor of links) {
      anchor.classList.toggle("on", anchor === current);
    }
    setTitle(current.dataset.title);
    util.hidden = !framed && !!(link && key && link.dataset.frame);
    if (!link || !key) {
      view.hidden = true; home.hidden = false;
      window.Theme.relayout(home);
      sync(""); return;
    }
    const href = link.getAttribute("href");
    if (href !== page || sub !== state) {
      view.contentWindow.location.replace(href + (sub || "#"));
    } else view.contentWindow.postMessage("theme:title?", "*");
    page = href; state = sub;
    home.hidden = true; view.hidden = false;
    sync(build(key, sub));
  }
  function hashFor(href) {
    for (const anchor of links) {
      const base = anchor.getAttribute("href");
      if (anchor.dataset.view && href.startsWith(base)) {
        const rest = href.slice(base.length);
        return build(anchor.dataset.view, rest.startsWith("#") ? rest : "");
      }
    }
    return null;
  }
  const resetCols = document.getElementById("reset-cols");
  function resetAll() {
    window.Theme.resetCols(home);
    if (page) view.contentWindow.postMessage("theme:reset-cols", "*");
  }
  resetCols.addEventListener("click", event => {
    event.preventDefault();
    resetAll();
  });
  document.addEventListener("click", event => {
    const anchor = event.target.closest("a[href]");
    if (!anchor || anchor === resetCols || anchor.target) return;
    if (event.ctrlKey || event.metaKey || event.shiftKey) return;
    if (event.button) return;
    const href = anchor.getAttribute("href");
    const hash = anchor.dataset.view != null
      ? build(anchor.dataset.view, "") : hashFor(href);
    if (hash == null) return;
    event.preventDefault();
    if (hash === (location.hash || "")) show(hash); else location.hash = hash;
  });
  window.addEventListener("message", event => {
    if (event.source === view.contentWindow && event.data) {
      if (event.data.theme === "title") setTitle(event.data.title);
      else if (event.data.theme === "hash" && page) {
        state = event.data.hash;
        sync(build(parse(location.hash)[0], state));
      }
      return;
    }
    if (framed && event.source === window.parent) {
      if (event.data === "theme:title?") setTitle(title);
      else if (event.data === "theme:reset-cols") resetAll();
    }
  });
  window.addEventListener("hashchange", () => show(location.hash));
  show(location.hash);
})();
