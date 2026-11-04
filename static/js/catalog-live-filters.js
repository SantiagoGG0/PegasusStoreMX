(function () {
  function isCatalogPage() {
    return !!document.getElementById("catalog-page");
  }

  if (!isCatalogPage()) return;

  function canHijackClick(event, link) {
    if (!link) return false;
    if (event.defaultPrevented) return false;
    if (event.button !== 0) return false;
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return false;
    return true;
  }

  function buildUrlFromParams(params) {
    var qs = params.toString();
    return window.location.pathname + (qs ? "?" + qs : "");
  }

  function updateFromHtml(html, nextUrl) {
    var parser = new DOMParser();
    var doc = parser.parseFromString(html, "text/html");

    var nextPage = doc.getElementById("catalog-page");
    var currPage = document.getElementById("catalog-page");
    if (nextPage && currPage) currPage.replaceWith(nextPage);

    var nextCatBar = doc.querySelector(".cat-rail");
    var currCatBar = document.querySelector(".cat-rail");
    if (nextCatBar && currCatBar) currCatBar.replaceWith(nextCatBar);

    window.history.replaceState({}, "", nextUrl);

    if (typeof window.CatalogLoadMoreInit === "function") window.CatalogLoadMoreInit();
    if (window.closeSheets) window.closeSheets();
  }

  function fetchCatalog(url) {
    return fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" }, credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) throw new Error("catalog_load_failed");
        return r.text();
      });
  }

  function applyCatalogParams(params) {
    var nextUrl = buildUrlFromParams(params);
    fetchCatalog(nextUrl)
      .then(function (html) { updateFromHtml(html, nextUrl); })
      .catch(function () { window.location.href = nextUrl; });
  }

  function applyCatalogSort(value) {
    var params = new URLSearchParams(window.location.search);
    params.set("sort", value);
    params.delete("page");
    applyCatalogParams(params);
  }

  window.applyCatalogParams = applyCatalogParams;
  window.applyCatalogSort = applyCatalogSort;

  document.addEventListener("submit", function (e) {
    var form = e.target.closest("form.search-bar");
    if (!form || !isCatalogPage()) return;

    e.preventDefault();
    var params = new URLSearchParams(window.location.search);
    var formData = new FormData(form);

    var q = (formData.get("q") || "").toString().trim();
    if (q) params.set("q", q); else params.delete("q");

    var category = formData.get("category");
    if (category) params.set("category", category.toString());

    params.delete("page");
    applyCatalogParams(params);
  });

  document.addEventListener("click", function (e) {
    var link = e.target.closest(".cat-rail a[href], .catalog-sidebar__cat[href]");
    if (!link || !isCatalogPage()) return;
    if (!canHijackClick(e, link)) return;

    var url = new URL(link.href, window.location.origin);
    if (url.pathname !== window.location.pathname) return;

    e.preventDefault();
    var params = new URLSearchParams(window.location.search);
    if (url.searchParams.has("category")) {
      params.set("category", url.searchParams.get("category"));
      params.delete("view");
    } else if (url.searchParams.has("view")) {
      params.set("view", url.searchParams.get("view"));
      params.delete("category");
    } else {
      params.delete("category");
      params.delete("view");
    }
    params.delete("page");
    applyCatalogParams(params);
  });

  /* Filter chips (envío gratis / rating / precio) — toggle a param and re-fetch. */
  window.toggleCatalogFilter = function (key, value) {
    var params = new URLSearchParams(window.location.search);
    if (params.get(key) === String(value)) params.delete(key);
    else params.set(key, String(value));
    params.delete("page");
    applyCatalogParams(params);
  };

  window.clearCatalogFilters = function () {
    var params = new URLSearchParams(window.location.search);
    ["envio", "rating", "precio", "page"].forEach(function (k) { params.delete(k); });
    applyCatalogParams(params);
  };
})();
