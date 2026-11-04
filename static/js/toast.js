/* Toast global — se muestra al agregar al carrito o tras otras acciones. */
(function () {
  var toast = document.getElementById('toast');
  var msgEl = document.getElementById('toast-msg');
  if (!toast || !msgEl) return;

  var hideTimer = null;

  function showToast(message) {
    msgEl.textContent = message;
    toast.hidden = false;
    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = setTimeout(function () { toast.hidden = true; }, 2600);
  }

  window.showToast = showToast;

  window.addEventListener('cart:updated', function (e) {
    var detail = e.detail || {};
    if (detail.success === false) return;
    var name = detail.added_product && detail.added_product.name;
    showToast(name ? 'Agregado al carrito' : 'Carrito actualizado');
  });
})();
