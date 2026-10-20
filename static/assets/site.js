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

  // Likes (counts live in a small Cloudflare Worker; this browser remembers what it liked)
  var api = document.body.getAttribute('data-likes-api');
  if (api) {
    var KEY = 'ws-liked';
    var liked = {};
    try { liked = JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (e) {}
    var save = function () { try { localStorage.setItem(KEY, JSON.stringify(liked)); } catch (e) {} };
    var fmt = function (n) { return n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + 'k' : String(n); };

    var btn = document.querySelector('[data-like]');
    var cardEls = Array.prototype.slice.call(document.querySelectorAll('.card[data-id]'));
    var ids = cardEls.map(function (c) { return c.getAttribute('data-id'); });
    if (btn) ids.unshift(btn.getAttribute('data-like'));
    ids = ids.filter(function (v, i, a) { return a.indexOf(v) === i; });

    var paint = function (counts) {
      cardEls.forEach(function (c) {
        var n = counts[c.getAttribute('data-id')];
        if (n > 0 && !c.querySelector('.card-likes')) {
          var s = document.createElement('span');
          s.className = 'card-likes';
          s.textContent = '\u2665 ' + fmt(n);
          c.appendChild(s);
        }
      });
      if (btn) setBtn(counts[btn.getAttribute('data-like')] || 0);
    };
    var setBtn = function (n) {
      var on = !!liked[btn.getAttribute('data-like')];
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      btn.querySelector('[data-count]').textContent = n > 0 ? fmt(n) : 'Like';
      btn.dataset.n = n;
    };

    for (var i = 0; i < ids.length; i += 60) {
      fetch(api + '/likes?ids=' + ids.slice(i, i + 60).join(','))
        .then(function (r) { return r.json(); }).then(paint).catch(function () {});
    }

    if (btn) {
      setBtn(0);
      btn.addEventListener('click', function () {
        var id = btn.getAttribute('data-like');
        var on = !liked[id];
        var n = Math.max(0, (parseInt(btn.dataset.n, 10) || 0) + (on ? 1 : -1));
        if (on) { liked[id] = 1; } else { delete liked[id]; }
        save(); setBtn(n);
        btn.classList.remove('pop'); void btn.offsetWidth; if (on) btn.classList.add('pop');
        fetch(api + '/like', { method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: id, action: on ? 'like' : 'unlike' }) })
          .then(function (r) { return r.json(); })
          .then(function (d) { if (typeof d.count === 'number') setBtn(d.count); })
          .catch(function () {});
      });
    }
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
