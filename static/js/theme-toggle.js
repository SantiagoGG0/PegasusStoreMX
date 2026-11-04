/* Interruptor de modo claro/oscuro — la lógica de tokens vive inline en
 * <head> (window.pgsTheme, ver base.html) para aplicarse antes de pintar.
 * Este archivo solo conecta los botones del header. */
(function () {
  function syncButtons(theme) {
    var isLight = theme === 'light';
    document.querySelectorAll('[data-theme-toggle]').forEach(function (btn) {
      btn.setAttribute('aria-label', isLight ? 'Cambiar a modo oscuro' : 'Cambiar a modo claro');
      var sun = btn.querySelector('.theme-toggle__icon--sun');
      var moon = btn.querySelector('.theme-toggle__icon--moon');
      if (sun) sun.hidden = !isLight;
      if (moon) moon.hidden = isLight;
    });
  }

  if (window.pgsTheme) syncButtons(window.pgsTheme.get());

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-theme-toggle]');
    if (!btn || !window.pgsTheme) return;
    window.pgsTheme.toggle();
  });

  document.addEventListener('pgs:theme-changed', function (e) {
    syncButtons(e.detail.theme);
  });
})();
