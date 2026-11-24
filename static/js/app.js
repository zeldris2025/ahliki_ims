/* Ah Liki IMS — page shell behaviour (sidebar, dropdowns, flash messages, form guard,
   KPI counters). Plain JavaScript, no dependencies. Everything here is progressive:
   pages work without it. */
(function () {
  'use strict';
  var root = document.documentElement;
  var sidebar = document.getElementById('sidebar');
  var overlay = document.getElementById('sidebarOverlay');
  var burger = document.getElementById('hamburgerBtn');
  var layout = document.querySelector('.layout');
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var store = {
    get: function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) {} }
  };

  /* ── Sidebar: off-canvas drawer below 1024px (and always for WMS floor roles) ── */
  var drawerQuery = window.matchMedia('(max-width: 1024px)');
  function isDrawer() {
    return drawerQuery.matches || (layout && layout.classList.contains('wms-op-layout'));
  }
  function setDrawer(open) {
    if (!sidebar) return;
    sidebar.classList.toggle('open', open);
    if (overlay) overlay.classList.toggle('open', open);
    if (burger) burger.setAttribute('aria-expanded', open ? 'true' : 'false');
    document.body.classList.toggle('nav-locked', open);
    if (open) { var first = sidebar.querySelector('.nav-link.active, .nav-link'); if (first) first.focus({ preventScroll: true }); }
  }
  if (burger) burger.addEventListener('click', function () {
    if (isDrawer()) setDrawer(!sidebar.classList.contains('open'));
    else toggleCollapsed();
  });
  document.querySelectorAll('[data-nav-close]').forEach(function (el) {
    el.addEventListener('click', function () { setDrawer(false); });
  });
  drawerQuery.addEventListener('change', function () { setDrawer(false); });

  /* Desktop: collapse to an icon rail, remembered per browser. */
  function toggleCollapsed() {
    var on = !root.classList.contains('nav-collapsed');
    root.classList.toggle('nav-collapsed', on);
    store.set('ims.nav.collapsed', on ? '1' : '0');
  }
  var collapseBtn = document.getElementById('collapseBtn');
  if (collapseBtn) collapseBtn.addEventListener('click', toggleCollapsed);

  /* Menu groups open/close; the group holding the current page always starts open. */
  document.querySelectorAll('.nav-group').forEach(function (group) {
    var btn = group.querySelector('.nav-section');
    var key = 'ims.nav.group.' + group.dataset.group;
    function set(open) {
      group.classList.toggle('closed', !open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    if (store.get(key) === 'closed' && !group.classList.contains('has-active')) set(false);
    btn.addEventListener('click', function () {
      var open = group.classList.contains('closed');
      set(open);
      store.set(key, open ? 'open' : 'closed');
    });
  });

  /* ── Dropdowns ([data-dropdown] > [data-dropdown-toggle] + .dropdown-menu) ── */
  function closeDropdowns(except) {
    document.querySelectorAll('[data-dropdown].open').forEach(function (d) {
      if (d !== except) {
        d.classList.remove('open');
        var t = d.querySelector('[data-dropdown-toggle]');
        if (t) t.setAttribute('aria-expanded', 'false');
      }
    });
  }
  document.querySelectorAll('[data-dropdown]').forEach(function (d) {
    var toggle = d.querySelector('[data-dropdown-toggle]');
    if (!toggle) return;
    toggle.addEventListener('click', function (e) {
      e.stopPropagation();
      var open = !d.classList.contains('open');
      closeDropdowns(d);
      d.classList.toggle('open', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  });
  document.addEventListener('click', function (e) {
    if (!e.target.closest('[data-dropdown]')) closeDropdowns();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { closeDropdowns(); setDrawer(false); }
    /* "/" focuses the header search, unless the user is typing somewhere. */
    if (e.key === '/' && !e.target.closest('input, textarea, select, [contenteditable]')) {
      var s = document.querySelector('.global-search input');
      if (s) { e.preventDefault(); s.focus(); }
    }
  });

  /* ── Flash messages: dismissable; success notes fade after a while ── */
  document.querySelectorAll('.flash').forEach(function (el) {
    function dismiss() {
      el.classList.add('leaving');
      setTimeout(function () { el.remove(); }, reduceMotion ? 0 : 220);
    }
    var x = el.querySelector('.alert-close');
    if (x) x.addEventListener('click', dismiss);
    if (el.classList.contains('alert-success')) setTimeout(dismiss, 8000);
  });

  /* ── Double-submit guard ─────────────────────────────────────────────────────
     After a POST form is sent, its submit buttons are disabled so a second click
     can't send it again while the server is working. This is a convenience only:
     the server-side checks are what actually prevent duplicate stock movements.
     Opt out with data-no-guard on the form. Buttons come back after 10 s (e.g. a
     file download leaves the page in place) or when the page is restored from cache. */
  document.addEventListener('submit', function (e) {
    var form = e.target;
    if (e.defaultPrevented || (form.method || '').toLowerCase() !== 'post') return;
    if (form.hasAttribute('data-no-guard') || form.target === '_blank') return;
    if (form.dataset.submitting === '1') { e.preventDefault(); return; }
    form.dataset.submitting = '1';
    var buttons = form.querySelectorAll('button[type="submit"], button:not([type]), input[type="submit"]');
    /* Disable after the browser has read the clicked button's name/value. */
    setTimeout(function () {
      buttons.forEach(function (b) { b.disabled = true; b.classList.add('is-busy'); });
    }, 0);
    setTimeout(function () { release(form); }, 10000);
  });
  function release(form) {
    delete form.dataset.submitting;
    form.querySelectorAll('.is-busy').forEach(function (b) { b.disabled = false; b.classList.remove('is-busy'); });
  }
  window.addEventListener('pageshow', function (e) {
    if (e.persisted) document.querySelectorAll('form[data-submitting]').forEach(release);
  });

  /* ── KPI counters: <span data-count="1234" data-decimals="2" data-prefix="SAT$"> ── */
  function format(n, decimals) {
    return n.toLocaleString('en-NZ', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  }
  window.IMS = window.IMS || {};
  window.IMS.countUp = function (scope) {
    (scope || document).querySelectorAll('[data-count]').forEach(function (el) {
      var target = parseFloat(el.dataset.count);
      if (isNaN(target)) return;
      var decimals = parseInt(el.dataset.decimals || '0', 10);
      var prefix = el.dataset.prefix || '';
      var end = prefix + format(target, decimals);
      if (reduceMotion || Math.abs(target) < 2) { el.textContent = end; return; }
      var start = performance.now(), dur = 700;
      (function tick(now) {
        var t = Math.min(1, (now - start) / dur);
        var eased = 1 - Math.pow(1 - t, 3);
        el.textContent = t < 1 ? prefix + format(target * eased, decimals) : end;
        if (t < 1) requestAnimationFrame(tick);
      })(start);
    });
  };
  window.IMS.reduceMotion = reduceMotion;
  window.IMS.countUp();
})();
