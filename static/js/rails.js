/* Rieles horizontales arrastrables (categorías, destacados, relacionados).
 * Arrastre con mouse/touch vía Pointer Events + inercia + autoscroll opcional
 * (data-autoscroll="px/frame"), pausado en hover/touch y reanudado 2.6s
 * después de soltar. Aplica sobre cualquier [data-rail]. */
(function () {
  function initRail(el) {
    if (el.__pgRail) return;
    el.__pgRail = true;
    el.style.cursor = 'grab';
    el.style.touchAction = 'pan-y';

    var down = false, touch = false, sx = 0, sy = 0, sl = 0, dragged = false, lx = 0, lt = 0, vel = 0;

    function stopGlide() {
      if (el.__glide) { cancelAnimationFrame(el.__glide); el.__glide = null; }
    }

    function onDown(e) {
      stopGlide();
      down = true; touch = e.pointerType !== 'mouse'; dragged = false;
      sx = lx = e.clientX; sy = e.clientY; sl = el.scrollLeft;
      lt = e.timeStamp || Date.now(); vel = 0;
      if (!touch) el.style.cursor = 'grabbing';
    }

    function onMove(e) {
      if (!down) return;
      var dx = e.clientX - sx;
      if (!dragged) {
        if (touch && Math.abs(e.clientY - sy) > Math.abs(dx) && Math.abs(e.clientY - sy) > 8) { down = false; return; }
        if (Math.abs(dx) > (touch ? 5 : 3)) { dragged = true; el.__dragging = true; }
      }
      if (!dragged) return;
      var t = e.timeStamp || Date.now();
      var dt = t - lt;
      if (dt > 0) vel = 0.8 * ((lx - e.clientX) / dt) + 0.2 * vel;
      lx = e.clientX; lt = t;
      el.scrollLeft = sl - dx; el.__acc = el.scrollLeft;
    }

    function onUp() {
      if (!down) return;
      down = false; el.style.cursor = 'grab'; el.__dragging = false;
      if (!dragged) return;
      el.__suppress = Date.now();
      if (touch && Math.abs(vel) > 0.15) {
        var v = Math.max(-3.2, Math.min(3.2, vel)) * 16;
        var glide = function () {
          v *= 0.93;
          var before = el.scrollLeft;
          el.scrollLeft = before + v;
          el.__acc = el.scrollLeft;
          if (Math.abs(v) > 0.4 && el.scrollLeft !== before) el.__glide = requestAnimationFrame(glide);
          else el.__glide = null;
        };
        el.__glide = requestAnimationFrame(glide);
      }
    }

    el.addEventListener('pointerdown', onDown);
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerup', onUp);
    window.addEventListener('pointercancel', onUp);
    el.addEventListener('click', function (e) {
      if (el.__suppress && Date.now() - el.__suppress < 260) { e.preventDefault(); e.stopPropagation(); }
    }, true);

    var speed = parseFloat(el.getAttribute('data-autoscroll') || '0');
    if (speed > 0) {
      var paused = false, resumeAt = 0;
      el.addEventListener('pointerenter', function (e) { if (e.pointerType === 'mouse') paused = true; });
      el.addEventListener('pointerleave', function (e) { if (e.pointerType === 'mouse') paused = false; });
      el.addEventListener('pointerdown', function (e) { if (e.pointerType !== 'mouse') { paused = true; resumeAt = 0; } });
      var scheduleResume = function (e) {
        if (e.pointerType === 'mouse' || !paused) return;
        resumeAt = Date.now() + 2600;
      };
      window.addEventListener('pointerup', scheduleResume);
      window.addEventListener('pointercancel', scheduleResume);
      el.__acc = el.scrollLeft;
      var step = function () {
        if (!el.isConnected) return;
        if (paused && resumeAt && Date.now() > resumeAt && !el.__glide) { paused = false; resumeAt = 0; }
        if (!paused && !el.__dragging && !el.__glide) {
          var half = el.scrollWidth / 2;
          el.__acc = (el.__acc || 0) + speed;
          if (half > 10 && el.__acc >= half) el.__acc -= half;
          el.scrollLeft = el.__acc;
        } else {
          el.__acc = el.scrollLeft;
        }
        el.__raf = requestAnimationFrame(step);
      };
      el.__raf = requestAnimationFrame(step);
    }
  }

  function initAll(root) {
    (root || document).querySelectorAll('[data-rail]').forEach(initRail);
  }

  document.addEventListener('DOMContentLoaded', function () { initAll(document); });
  if (document.readyState !== 'loading') initAll(document);

  if (window.MutationObserver) {
    var observer = new MutationObserver(function (mutations) {
      mutations.forEach(function (m) {
        m.addedNodes.forEach(function (node) {
          if (node.nodeType !== 1) return;
          if (node.matches && node.matches('[data-rail]')) initRail(node);
          else if (node.querySelectorAll) initAll(node);
        });
      });
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }
})();
