/* Acordeones genéricos (FAQ del inicio, secciones de la ficha de producto).
 * Marcado esperado:
 * <div class="accordion" data-accordion-group="faq">
 *   <div class="accordion__item">
 *     <button class="accordion__trigger" data-accordion-trigger>Pregunta</button>
 *     <div class="accordion__panel" hidden>Respuesta</div>
 *   </div>
 * </div>
 * Una sola sección abierta a la vez dentro del mismo data-accordion-group. */
(function () {
  document.addEventListener('click', function (e) {
    var trigger = e.target.closest('[data-accordion-trigger]');
    if (!trigger) return;
    var item = trigger.closest('.accordion__item');
    if (!item) return;
    var panel = item.querySelector('.accordion__panel');
    var group = item.closest('[data-accordion-group]');
    var wasOpen = item.classList.contains('is-open');

    if (group) {
      group.querySelectorAll('.accordion__item.is-open').forEach(function (openItem) {
        if (openItem === item) return;
        openItem.classList.remove('is-open');
        var p = openItem.querySelector('.accordion__panel');
        if (p) p.hidden = true;
        var t = openItem.querySelector('[data-accordion-trigger]');
        if (t) t.setAttribute('aria-expanded', 'false');
      });
    }

    item.classList.toggle('is-open', !wasOpen);
    if (panel) panel.hidden = wasOpen;
    trigger.setAttribute('aria-expanded', wasOpen ? 'false' : 'true');
  });
})();
