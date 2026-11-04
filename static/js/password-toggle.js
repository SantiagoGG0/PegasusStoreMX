/* Botón de "mostrar/ocultar contraseña" en campos [data-password-toggle]. */
(function () {
  document.querySelectorAll('[data-password-toggle]').forEach(function (wrap) {
    var btn = wrap.querySelector('[data-password-toggle-btn]');
    var input = wrap.querySelector('input');
    if (!btn || !input) return;

    var eye = btn.querySelector('.icon-eye');
    var eyeOff = btn.querySelector('.icon-eye-off');

    btn.addEventListener('click', function () {
      var willShow = input.type === 'password';
      input.type = willShow ? 'text' : 'password';
      btn.setAttribute('aria-pressed', String(willShow));
      btn.setAttribute('aria-label', willShow ? 'Ocultar contraseña' : 'Mostrar contraseña');
      if (eye) eye.hidden = willShow;
      if (eyeOff) eyeOff.hidden = !willShow;
    });
  });
})();
