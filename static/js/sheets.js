/* Hojas inferiores móviles genéricas (filtros, orden, etc.)
 * Abrir: <button data-sheet-open="id-de-la-hoja">
 * Cerrar: <button data-sheet-close> o clic en el backdrop
 * La hoja debe tener class="sheet" y el id referenciado. */
(function () {
  var backdrop = document.querySelector('[data-sheet-backdrop]');

  function closeAll() {
    document.querySelectorAll('.sheet').forEach(function (s) { s.hidden = true; });
    if (backdrop) backdrop.hidden = true;
    document.body.style.overflow = '';
  }

  function open(id) {
    var sheet = document.getElementById(id);
    if (!sheet) return;
    closeAll();
    sheet.hidden = false;
    if (backdrop) backdrop.hidden = false;
    document.body.style.overflow = 'hidden';
  }

  document.addEventListener('click', function (e) {
    var openBtn = e.target.closest('[data-sheet-open]');
    if (openBtn) { open(openBtn.getAttribute('data-sheet-open')); return; }
    var closeBtn = e.target.closest('[data-sheet-close]');
    if (closeBtn) { closeAll(); return; }
    if (e.target === backdrop) { closeAll(); }
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeAll();
  });

  window.closeSheets = closeAll;
})();
