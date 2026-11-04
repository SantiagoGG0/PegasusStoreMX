function initCartSuggestedLoadMore() {
  var grid = document.getElementById("cart-suggested-grid");
  var wrap = document.getElementById("cart-suggested-load-more-wrap");
  var spinner = document.getElementById("cart-suggested-load-spinner");
  var statusEl = document.getElementById("cart-suggested-load-more-status");
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

  function updateStatus(loaded, total) {
    if (loaded && total) {
      setStatus("Mostrando " + loaded + " de " + total + " productos");
      wrap.dataset.loadedCount = String(loaded);
    }
  }

  function hideLoadMore() {
    hasNext = false;
    wrap.classList.add("hidden");
    if (observer) observer.disconnect();
  }

  if (!hasNext) {
    hideLoadMore();
    return;
  }

  updateStatus(
    parseInt(wrap.dataset.loadedCount || "0", 10),
    parseInt(wrap.dataset.totalCount || "0", 10)
  );

  function loadMore() {
    if (loading || !hasNext || !fragmentUrl) return;
    setLoading(true);

    fetch(fragmentUrl + "?page=" + encodeURIComponent(String(currentPage)), {
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then(function (response) {
        if (!response.ok) throw new Error("load_failed");
        return response.json();
      })
      .then(function (data) {
        if (data.html) grid.insertAdjacentHTML("beforeend", data.html);
        hasNext = !!data.has_next;
        currentPage = (data.page || currentPage) + 1;
        if (data.loaded_count != null && data.total_count != null) {
          updateStatus(data.loaded_count, data.total_count);
        }
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
    }, { rootMargin: "350px 0px" });
    observer.observe(wrap);
  } else {
    loadMore();
  }
}

window.CartSuggestedLoadMoreInit = initCartSuggestedLoadMore;
initCartSuggestedLoadMore();
