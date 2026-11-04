/* Carrusel de imágenes en tarjetas de producto (grid catálogo, rieles).
 * Las flechas prev/next y los puntos ya se renderizan en el markup
 * (product_card.html) pero no tenían JS que los conectara. */
(function () {
  function getWrap(btn) {
    return btn.closest('.product-card__media-wrap');
  }

  // Las fotos 2+ llegan sin src (data-src) para no descargarlas con la página.
  function loadSlide(slide) {
    if (slide && slide.dataset && slide.dataset.src) {
      slide.src = slide.dataset.src;
      slide.removeAttribute('data-src');
    }
  }

  function goTo(wrap, index) {
    var track = wrap.querySelector('.product-card__track');
    if (!track) return;
    var slides = track.children;
    if (!slides.length) return;
    index = ((index % slides.length) + slides.length) % slides.length;
    loadSlide(slides[index]);
    loadSlide(slides[(index + 1) % slides.length]);  // la siguiente, precargada
    track.style.transform = 'translateX(-' + (index * 100) + '%)';
    wrap.querySelectorAll('.product-card__dot').forEach(function (dot, i) {
      dot.classList.toggle('is-active', i === index);
    });
    wrap.dataset.carouselIndex = index;
  }

  document.addEventListener('click', function (e) {
    var navBtn = e.target.closest('.product-card__nav');
    var dotBtn = e.target.closest('.product-card__dot');
    var btn = navBtn || dotBtn;
    if (!btn) return;

    var wrap = getWrap(btn);
    if (!wrap) return;

    e.preventDefault();
    e.stopPropagation();

    var current = parseInt(wrap.dataset.carouselIndex || '0', 10);
    if (navBtn) {
      var dir = navBtn.classList.contains('product-card__nav--next') ? 1 : -1;
      goTo(wrap, current + dir);
    } else {
      goTo(wrap, parseInt(dotBtn.dataset.carouselDot || '0', 10));
    }
  });

  // Al pasar el mouse por una tarjeta, precargar su segunda foto.
  document.addEventListener('mouseover', function (e) {
    var wrap = e.target.closest && e.target.closest('.product-card__media-wrap');
    if (!wrap || wrap.dataset.preloaded) return;
    wrap.dataset.preloaded = '1';
    var track = wrap.querySelector('.product-card__track');
    if (track && track.children[1]) loadSlide(track.children[1]);
  });
})();
