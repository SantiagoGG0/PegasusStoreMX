/**
 * Carrito: actualizar cantidad y quitar líneas sin recargar la página.
 */
(function () {
  var pendingRemoveConfirm = null;

  function closeRemoveConfirm(result) {
    var removeModal = document.getElementById("cart-remove-modal");
    if (removeModal) {
      removeModal.classList.add("hidden");
      removeModal.hidden = true;
    }
    if (pendingRemoveConfirm) {
      pendingRemoveConfirm(!!result);
      pendingRemoveConfirm = null;
    }
  }

  window.askCartRemoveConfirm = function (row) {
    var removeModal = document.getElementById("cart-remove-modal");
    var removeModalText = document.getElementById("cart-remove-modal-text");
    var removeModalConfirm = removeModal
      ? removeModal.querySelector("[data-cart-remove-confirm]")
      : null;
    var name = (row && row.dataset.productName) || "este producto";
    var message = "¿Desea eliminar \"" + name + "\" del carrito?";

    if (!removeModal || !removeModalText) {
      return Promise.resolve(window.confirm(message));
    }

    return new Promise(function (resolve) {
      pendingRemoveConfirm = resolve;
      removeModalText.textContent = message;
      removeModal.classList.remove("hidden");
      removeModal.hidden = false;
      if (removeModalConfirm) removeModalConfirm.focus();
    });
  };

  if (!window.__cartRemoveModalBound) {
    window.__cartRemoveModalBound = true;
    document.addEventListener("click", function (e) {
      if (!document.getElementById("cart-remove-modal")) return;
      if (e.target.closest("[data-cart-remove-dismiss]")) {
        closeRemoveConfirm(false);
      }
      if (e.target.closest("[data-cart-remove-confirm]")) {
        closeRemoveConfirm(true);
      }
    });
    document.addEventListener("keydown", function (e) {
      var removeModal = document.getElementById("cart-remove-modal");
      if (e.key === "Escape" && removeModal && !removeModal.hidden) {
        closeRemoveConfirm(false);
      }
    });
  }
})();

window.initCartPage = function () {
  var root = document.getElementById("cart-page");
  if (!root || root.dataset.cartPageInit === "1") return;
  root.dataset.cartPageInit = "1";

  var UPDATE_URL = root.dataset.updateUrl;
  var REMOVE_URL = root.dataset.removeUrl;
  var linesRoot = document.getElementById("cart-lines");

  function getCSRF() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : "";
  }

  function formatCop(value) {
    var n = Math.round(parseFloat(value) || 0);
    return "$" + n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  function esc(text) {
    return String(text || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function buildLineRow(line) {
    var name = esc(line.product_name || "Producto");
    var slug = esc(line.product_slug || "");
    var image = esc(line.product_image || "");
    var variation = esc(line.variation_label || "");
    var maxStock = parseInt(line.max_stock || 1, 10);
    var qty = parseInt(line.quantity || 1, 10);
    var atMax = qty >= maxStock;
    var href = slug ? "/producto/" + slug + "/" : "#";

    return [
      '<article class="cart-line" data-cart-key="' + esc(line.cart_key) + '" data-product-name="' + name + '">',
      '<a href="' + href + '" class="cart-line__media">',
      image ? '<img src="' + image + '" alt="' + name + '" />' : '',
      '</a>',
      '<div class="cart-line__body">',
      '<a href="' + href + '" class="cart-line__name">' + name + '</a>',
      variation ? '<p class="cart-line__variant">' + variation + '</p>' : '',
      '<p class="cart-line__unit">' + formatCop(line.unit_price) + ' c/u</p>',
      '</div>',
      '<div class="cart-line__stepper" role="group" aria-label="Cantidad">',
      '<button type="button" data-cart-dec aria-label="Disminuir cantidad" class="cart-line__step-btn">&minus;</button>',
      '<input type="number" data-cart-qty value="' + qty + '" min="1" max="' + maxStock + '" class="cart-line__qty" aria-label="Cantidad" />',
      '<button type="button" data-cart-inc aria-label="Aumentar cantidad" class="cart-line__step-btn"' + (atMax ? ' disabled' : '') + '>+</button>',
      '</div>',
      '<div class="cart-line__total" data-cart-subtotal>' + formatCop(line.subtotal) + '</div>',
      '<button type="button" data-cart-remove class="cart-line__remove" title="Quitar del carrito">',
      '<svg viewBox="0 0 24 24" width="19" height="19" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 6.5h15M9.5 6.5V4.8h5v1.7M6.6 6.5l.9 12.2a1.6 1.6 0 0 0 1.6 1.5h5.8a1.6 1.6 0 0 0 1.6-1.5l.9-12.2M10.3 10v6.6M13.7 10v6.6"></path></svg>',
      '</button>',
      '</article>'
    ].join("");
  }

  function updateBadge(count) {
    if (window.pegasusUpdateCartBadge) { window.pegasusUpdateCartBadge(count); return; }
    var badge = document.getElementById("cart-badge");
    if (!badge) return;
    badge.textContent = count;
    badge.hidden = count === 0;
  }

  function flashMessage(text, type) {
    var box = document.getElementById("cart-flash");
    if (!box || !text) return;
    box.textContent = text;
    box.className = "cart-flash cart-flash--" + (type || "info");
    box.classList.remove("hidden");
    clearTimeout(box._hideTimer);
    box._hideTimer = setTimeout(function () {
      box.classList.add("hidden");
    }, 4000);
  }

  function postCart(url, params) {
    var body = new URLSearchParams(params);
    body.set("csrfmiddlewaretoken", getCSRF());
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "X-CSRFToken": getCSRF(),
        "X-Requested-With": "XMLHttpRequest",
      },
      body: body,
    }).then(function (r) {
      return r.text().then(function (text) {
        var data = {};
        try {
          data = text ? JSON.parse(text) : {};
        } catch (_) {
          data = { error: "Respuesta inválida del servidor." };
        }
        if (!r.ok && !data.error) {
          data.error = "No se pudo actualizar el carrito.";
        }
        return data;
      });
    });
  }

  function postFallback(url, params) {
    var form = document.createElement("form");
    form.method = "POST";
    form.action = url;
    form.style.display = "none";

    var csrf = document.createElement("input");
    csrf.type = "hidden";
    csrf.name = "csrfmiddlewaretoken";
    csrf.value = getCSRF();
    form.appendChild(csrf);

    Object.keys(params || {}).forEach(function (key) {
      var input = document.createElement("input");
      input.type = "hidden";
      input.name = key;
      input.value = params[key];
      form.appendChild(input);
    });

    document.body.appendChild(form);
    form.submit();
  }

  function applyLine(line) {
    var row = document.querySelector('[data-cart-key="' + line.cart_key + '"]');
    if (!row && linesRoot) {
      linesRoot.insertAdjacentHTML("beforeend", buildLineRow(line));
      row = document.querySelector('[data-cart-key="' + line.cart_key + '"]');
    }
    if (!row) return;
    var qtyInput = row.querySelector("[data-cart-qty]");
    var subtotalEl = row.querySelector("[data-cart-subtotal]");
    var incBtn = row.querySelector("[data-cart-inc]");
    if (qtyInput) {
      qtyInput.value = line.quantity;
      qtyInput.max = line.max_stock;
    }
    if (subtotalEl) subtotalEl.textContent = formatCop(line.subtotal);
    if (incBtn) {
      incBtn.disabled = line.quantity >= line.max_stock;
    }
  }

  function applySummary(data) {
    var summaryState = document.getElementById("cart-summary-state-wrap");
    if (summaryState && data.summary_totals_html !== undefined) {
      summaryState.innerHTML = data.summary_totals_html;
    }

    var totalEl = document.getElementById("cart-total");
    var summaryLines = document.getElementById("cart-summary-lines");
    if (totalEl) totalEl.textContent = formatCop(data.total);
    var highlight = document.getElementById("cart-summary-highlight");
    if (highlight) {
      var unitWord = data.item_count === 1 ? "unidad" : "unidades";
      highlight.innerHTML =
        '<strong id="cart-item-count">' + data.item_count + " " + unitWord + "</strong> · listo para pagar";
    }
    if (summaryLines) {
      summaryLines.innerHTML = "";
      data.lines.forEach(function (line) {
        var row = document.querySelector('[data-cart-key="' + line.cart_key + '"]');
        var name = row ? row.dataset.productName : "Producto";
        var div = document.createElement("div");
        div.className = "cart-summary__line";
        div.innerHTML =
          '<span>' + name + ' <span class="cart-summary__line-qty">&times;' + line.quantity + '</span></span>' +
          '<span>' + formatCop(line.subtotal) + '</span>';
        summaryLines.appendChild(div);
      });
    }
    updateBadge(data.cart_count);

    var noticeWrap = document.getElementById("supplier-notice-wrap");
    if (noticeWrap && data.notice_html !== undefined) {
      noticeWrap.innerHTML = data.notice_html;
    }

    var shippingWrap = document.getElementById("cart-shipping-summary-wrap");
    if (shippingWrap && data.shipping_groups_html !== undefined) {
      shippingWrap.innerHTML = data.shipping_groups_html;
    }
  }

  function syncRows(data) {
    var keep = {};
    (data.lines || []).forEach(function (line) {
      keep[line.cart_key] = true;
    });
    root.querySelectorAll("[data-cart-key]").forEach(function (row) {
      var key = row.getAttribute("data-cart-key");
      if (!keep[key]) {
        row.remove();
      }
    });
  }

  function renderEmptyState() {
    updateBadge(0);
    root.outerHTML = [
      '<div class="cart-empty" id="cart-empty-state">',
      '<div class="cart-empty__text">Todavía no has agregado nada.</div>',
      '<a href="/?view=all" class="btn-gold-pill">Explorar catálogo</a>',
      '</div>'
    ].join("");
  }

  function handleResponse(data) {
    if (data.error) {
      flashMessage(data.error, "error");
      return;
    }
    if (data.warning) flashMessage(data.warning, "warning");
    if (data.empty) {
      renderEmptyState();
      return;
    }
    syncRows(data);
    data.lines.forEach(applyLine);
    applySummary(data);
  }

  function removeLine(cartKey) {
    postCart(REMOVE_URL, { cart_key: cartKey })
      .then(handleResponse)
      .catch(function () {
        postFallback(REMOVE_URL, { cart_key: cartKey });
      });
  }

  function updateLine(cartKey, action) {
    postCart(UPDATE_URL, { cart_key: cartKey, action: action })
      .then(handleResponse)
      .catch(function () {
        postFallback(UPDATE_URL, { cart_key: cartKey, action: action });
      });
  }

  root.addEventListener("click", function (e) {
    var dec = e.target.closest("[data-cart-dec]");
    var inc = e.target.closest("[data-cart-inc]");
    var remove = e.target.closest("[data-cart-remove]");
    if (!dec && !inc && !remove) return;

    e.preventDefault();
    e.stopPropagation();

    var row = e.target.closest("[data-cart-key]");
    if (!row) return;
    var cartKey = row.getAttribute("data-cart-key");

    if (remove) {
      window.askCartRemoveConfirm(row).then(function (ok) {
        if (ok) removeLine(cartKey);
      });
      return;
    }

    if (dec) {
      var qtyInput = row.querySelector("[data-cart-qty]");
      var qty = qtyInput ? parseInt(qtyInput.value, 10) : 1;
      if (qty <= 1) {
        window.askCartRemoveConfirm(row).then(function (ok) {
          if (ok) removeLine(cartKey);
        });
        return;
      }
    }

    updateLine(cartKey, inc ? "increment" : "decrement");
  });

  root.addEventListener("change", function (e) {
    var input = e.target.closest("[data-cart-qty]");
    if (!input) return;
    e.preventDefault();
    var row = input.closest("[data-cart-key]");
    if (!row) return;
    var cartKey = row.getAttribute("data-cart-key");
    var qty = parseInt(input.value, 10);
    if (qty < 1) {
      window.askCartRemoveConfirm(row).then(function (ok) {
        if (ok) {
          removeLine(cartKey);
        } else if (row.querySelector("[data-cart-qty]")) {
          row.querySelector("[data-cart-qty]").value = "1";
        }
      });
      return;
    }
    postCart(UPDATE_URL, { cart_key: cartKey, quantity: input.value })
      .then(handleResponse)
      .catch(function () {
        postFallback(UPDATE_URL, { cart_key: cartKey, quantity: input.value });
      });
  });

  window.__cartPageHandleResponse = handleResponse;

  if (!window.__cartPageCartUpdatedBound) {
    window.__cartPageCartUpdatedBound = true;
    window.addEventListener("cart:updated", function (evt) {
      if (!document.getElementById("cart-page")) return;
      var data = evt && evt.detail;
      if (!data || !data.success) return;
      if (window.__cartPageHandleResponse) {
        window.__cartPageHandleResponse(data);
      }
    });
  }
};

if (document.getElementById("cart-page")) {
  window.initCartPage();
}
