// WallSpotter: small progressive enhancements (the site works fully without this file).
(function () {
  var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Lock-screen clock and date (shown in the phone frames)
  function tick() {
    var d = new Date();
    var t = d.getHours() + ':' + String(d.getMinutes()).padStart(2, '0');
    var ds = d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
    document.querySelectorAll('[data-time]').forEach(function (el) { el.textContent = t; });
    document.querySelectorAll('[data-date]').forEach(function (el) { el.textContent = ds; });
  }
  tick();
  setInterval(tick, 15000);

  // Cards fade in as they scroll into view
  var cards = document.querySelectorAll('.card');
  if (!reduce && 'IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); }
      });
    }, { rootMargin: '0px 0px -40px 0px' });
    cards.forEach(function (c, i) {
      c.style.transitionDelay = (i % 5) * 60 + 'ms';
      io.observe(c);
    });
  } else {
    cards.forEach(function (c) { c.classList.add('in'); });
  }

  // Home showcase: cross-fade through Originals
  var shows = document.querySelectorAll('.showcase .screen img');
  if (shows.length > 1 && !reduce) {
    var k = 0;
    setInterval(function () {
      shows[k].classList.remove('on');
      k = (k + 1) % shows.length;
      shows[k].classList.add('on');
    }, 3500);
  }

  // Lock-screen preview dialog
  var dlg = document.getElementById('preview');
  var openBtn = document.querySelector('[data-preview]');
  if (dlg && openBtn && typeof dlg.showModal === 'function') {
    openBtn.addEventListener('click', function () { tick(); dlg.showModal(); });
    dlg.addEventListener('click', function (e) {
      if (e.target === dlg || e.target.closest('[data-close]')) dlg.close();
    });
  } else if (openBtn) {
    openBtn.hidden = true;
  }
})();
