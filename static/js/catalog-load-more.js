function initCatalogLoadMore() {
  var grid = document.getElementById("product-grid");
  var wrap = document.getElementById("catalog-load-more-wrap");
  var spinner = document.getElementById("catalog-load-spinner");
  var statusEl = document.getElementById("catalog-load-more-status");
  if (!grid || !wrap) return;
  if (wrap.dataset.bound === "1") return;
  wrap.dataset.bound = "1";

  var fragmentUrl = wrap.dataset.fragmentUrl;
  var hasNext = wrap.dataset.hasNext === "true";
  var currentPage = parseInt(wrap.dataset.nextPage || "2", 10);
  var loading = false;
  var observer = null;

  function setStatus(text) {
    if (statusEl) statusEl.textContent = text || "";
  }

  function setLoading(isLoading) {
    loading = isLoading;
    wrap.setAttribute("aria-busy", isLoading ? "true" : "false");
    if (spinner) spinner.classList.toggle("hidden", !isLoading);
  }

  function hideLoadMore() {
    hasNext = false;
    wrap.classList.add("hidden");
    if (observer) observer.disconnect();
  }

  if (!hasNext) {
    wrap.classList.add("hidden");
    return;
  }

  function loadMore() {
    if (loading || !hasNext || !fragmentUrl) return;
    setLoading(true);
    var params = new URLSearchParams(window.location.search);
    params.set("page", String(currentPage));
    if (wrap.dataset.stable === "1") params.set("stable", "1");
    // En /categoria/x/ la categoría va en la ruta, no en la query string.
    if (wrap.dataset.category && !params.has("category")) params.set("category", wrap.dataset.category);

    fetch(fragmentUrl + "?" + params.toString(), {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then(function (r) {
        if (!r.ok) throw new Error("load_failed");
        return r.json();
      })
      .then(function (data) {
        if (data.html) grid.insertAdjacentHTML("beforeend", data.html);
        hasNext = !!data.has_next;
        currentPage = (data.page || currentPage) + 1;
        if (!hasNext) hideLoadMore();
      })
      .catch(function () {
        setStatus("No se pudieron cargar más productos. Intenta de nuevo.");
      })
      .finally(function () {
        setLoading(false);
      });
  }

  if ("IntersectionObserver" in window) {
    observer = new IntersectionObserver(function (entries) {
      if (entries[0] && entries[0].isIntersecting) loadMore();
    }, { rootMargin: "900px 0px" });
    observer.observe(wrap);
  } else {
    loadMore();
  }
}

window.CatalogLoadMoreInit = initCatalogLoadMore;
initCatalogLoadMore();
