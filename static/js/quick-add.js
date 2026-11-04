/* Botón "+" de agregar rápido al carrito, en tarjetas de producto.
 * Dispara cart:updated (toast.js lo escucha) y actualiza el badge del header
 * y de la barra inferior móvil. Si el producto tiene variantes, primero pide
 * elegir una en un diálogo simple. */
if (!window.__quickAddInit) {
  window.__quickAddInit = true;

  var QUICK_ADD_BASE = '/carrito/agregar-rapido/';

  function getCSRF() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  function updateBadge(count) {
    ['cart-badge', 'mobile-cart-badge'].forEach(function (id) {
      var badge = document.getElementById(id);
      if (!badge) return;
      badge.textContent = count;
      badge.hidden = count === 0;
      badge.classList.toggle('hidden', count === 0);
    });
  }
  window.pegasusUpdateCartBadge = updateBadge;

  function flashBtn(btn, ok) {
    btn.classList.add(ok ? 'is-added' : 'is-error');
    btn.disabled = true;
    setTimeout(function () {
      btn.classList.remove('is-added', 'is-error');
      btn.disabled = false;
    }, 1200);
  }

  function tokenThen(fn) {
    // window.pgsCsrf (base.html) obtiene la cookie si la página vino de caché.
    return window.pgsCsrf ? window.pgsCsrf().then(fn) : Promise.resolve(getCSRF()).then(fn);
  }

  function doAdd(productId, variationId, btn) {
    tokenThen(function (token) {
      var body = new URLSearchParams({ quantity: '1', csrfmiddlewaretoken: token });
      if (variationId) body.set('variation_id', variationId);
      return fetch(QUICK_ADD_BASE + productId + '/', {
        method: 'POST',
        headers: { 'X-CSRFToken': token, 'X-Requested-With': 'XMLHttpRequest' },
        body: body,
      });
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        flashBtn(btn, data.success);
        updateBadge(data.cart_count);
        if (data.success) {
          window.dispatchEvent(new CustomEvent('cart:updated', { detail: data }));
          if (window.pgsTrackAddToCart) {
            window.pgsTrackAddToCart({
              id: productId,
              name: btn.dataset.name || '',
              category: btn.dataset.category || '',
              price: parseFloat(btn.dataset.price) || 0,
            }, 1);
          }
        }
      })
      .catch(function () { flashBtn(btn, false); });
  }

  function getOrCreateDialog() {
    var dlg = document.getElementById('variant-pick-dialog');
    if (dlg) return dlg;
    dlg = document.createElement('dialog');
    dlg.id = 'variant-pick-dialog';
    dlg.className = 'variant-dialog';
    dlg.innerHTML = [
      '<h2 class="variant-dialog__title">Selecciona una variante</h2>',
      '<div id="variant-pick-options" class="variant-dialog__options"></div>',
      '<div class="variant-dialog__actions">',
      '<button id="variant-pick-confirm" class="variant-dialog__confirm">Añadir al carrito</button>',
      '<button id="variant-pick-cancel" class="variant-dialog__cancel">Cancelar</button>',
      '</div>',
    ].join('');
    document.body.appendChild(dlg);
    dlg.querySelector('#variant-pick-cancel').addEventListener('click', function () { dlg.close(); });
    dlg.addEventListener('click', function (e) { if (e.target === dlg) dlg.close(); });
    return dlg;
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('.quick-add-btn');
    if (!btn) return;

    var productId = btn.dataset.productId;
    var variants = [];
    try { variants = JSON.parse(btn.dataset.variants || '[]'); } catch (_) {}

    if (variants.length === 0) {
      doAdd(productId, null, btn);
      return;
    }

    var dlg = getOrCreateDialog();
    var optionsEl = dlg.querySelector('#variant-pick-options');
    optionsEl.innerHTML = variants.map(function (v, i) {
      return [
        '<label class="variant-dialog__option">',
        '<input type="radio" name="vpick" value="' + v.id + '"' + (i === 0 ? ' checked' : '') + '>',
        '<span>' + v.label.replace(/</g, '&lt;') + '</span>',
        '</label>',
      ].join('');
    }).join('');

    var confirmBtn = dlg.querySelector('#variant-pick-confirm');
    var freshBtn = confirmBtn.cloneNode(true);
    confirmBtn.replaceWith(freshBtn);
    freshBtn.addEventListener('click', function () {
      var selected = dlg.querySelector('input[name="vpick"]:checked');
      if (!selected) return;
      dlg.close();
      doAdd(productId, selected.value, btn);
    });

    dlg.showModal();
  });
}
