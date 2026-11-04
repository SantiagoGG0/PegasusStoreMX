/**
 * En /carrito/ vacío: tras quick-add, reemplaza #cart-content sin recargar la página.
 */
(function () {
  var contentRoot = document.getElementById("cart-content");
  if (!contentRoot) return;

  var refreshing = false;

  function updateBadge(count) {
    var badge = document.getElementById("cart-badge");
    if (!badge) return;
    badge.textContent = count;
    badge.classList.toggle("hidden", !count);
  }

  function loadScript(src) {
    var base = src.split("?")[0];
    var existing = document.querySelector('script[src^="' + base + '"]');
    if (existing) {
      return Promise.resolve();
    }
    return new Promise(function (resolve, reject) {
      var script = document.createElement("script");
      script.src = src;
      script.onload = function () {
        resolve();
      };
      script.onerror = reject;
      document.body.appendChild(script);
    });
  }

  function mountCartScripts() {
    var jobs = [];
    if (document.getElementById("cart-page")) {
      jobs.push(
        loadScript(contentRoot.dataset.cartPageJs).then(function () {
          if (window.initCartPage) window.initCartPage();
        })
      );
    }
    if (document.getElementById("cart-suggested-load-more-wrap")) {
      jobs.push(
        loadScript(contentRoot.dataset.cartSuggestedJs).then(function () {
          if (window.initCartSuggestedLoadMore) window.initCartSuggestedLoadMore();
        })
      );
    }
    return Promise.all(jobs);
  }

  function refreshCartContent() {
    var url = contentRoot.dataset.fragmentUrl;
    if (!url || refreshing) return Promise.resolve();

    refreshing = true;
    contentRoot.setAttribute("aria-busy", "true");

    return fetch(url, {
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest" },
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (!data || data.empty || !data.html) return;
        contentRoot.innerHTML = data.html;
        if (typeof data.cart_count === "number") updateBadge(data.cart_count);
        return mountCartScripts();
      })
      .catch(function () {})
      .finally(function () {
        refreshing = false;
        contentRoot.removeAttribute("aria-busy");
      });
  }

  window.addEventListener("cart:updated", function (evt) {
    var data = evt && evt.detail;
    if (!data || !data.success || data.empty) return;
    if (document.getElementById("cart-page")) return;
    if (!document.getElementById("cart-empty-state")) return;
    refreshCartContent();
  });
})();
