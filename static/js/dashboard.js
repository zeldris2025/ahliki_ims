/* Executive dashboard: charts, measure toggles, table views, filters, tabs.
   Data comes from the json_script block "dash-data" written by the view. */
(function () {
  'use strict';
  var dataEl = document.getElementById('dash-data');
  if (!dataEl) return;
  var D = JSON.parse(dataEl.textContent);
  var reduce = window.IMS && window.IMS.reduceMotion;

  /* ── Filters: apply on change (custom dates use the Apply button) ── */
  var form = document.getElementById('dashFilters');
  if (form) {
    var custom = form.querySelector('.custom-dates');
    form.addEventListener('change', function (e) {
      if (e.target.name === 'range') {
        form.querySelectorAll('.seg-opt').forEach(function (o) { o.classList.toggle('on', o.contains(e.target)); });
        if (e.target.value === 'custom') { custom.hidden = false; custom.querySelector('input').focus(); return; }
        custom.querySelectorAll('input').forEach(function (i) { i.disabled = true; });
      }
      if (e.target.name === 'from' || e.target.name === 'to') return;
      document.body.classList.add('dash-loading');
      form.submit();
    });
  }

  /* ── Sections remember open/closed ── */
  document.querySelectorAll('.dash-section').forEach(function (s) {
    var key = 'ims.dash.' + s.dataset.section;
    try { if (localStorage.getItem(key) === 'closed') s.open = false; } catch (e) {}
    s.addEventListener('toggle', function () {
      try { localStorage.setItem(key, s.open ? 'open' : 'closed'); } catch (e) {}
      if (s.open) charts.forEach(function (c) { c.resize(); });
    });
  });

  /* ── Low / out-of-stock tabs (opens the tab whose page was just changed) ── */
  var tabs = document.querySelectorAll('#stock-attention .tab');
  function showTab(name) {
    tabs.forEach(function (t) { var on = t.dataset.tab === name; t.classList.toggle('on', on); t.setAttribute('aria-selected', on); });
    document.querySelectorAll('#stock-attention .tab-panel').forEach(function (p) { p.hidden = p.dataset.panel !== name; });
  }
  tabs.forEach(function (t) { t.addEventListener('click', function () { showTab(t.dataset.tab); }); });
  if (/[?&]out_page=/.test(location.search) && !/[?&]low_page=/.test(location.search)) showTab('out');

  /* ── Charts ── */
  var charts = [];
  function whenChart(fn) {
    if (window.Chart) return fn();
    var tries = 0, t = setInterval(function () {
      if (window.Chart || ++tries > 100) { clearInterval(t); if (window.Chart) fn(); }
    }, 50);
  }

  /* Validated categorical order (reference palette) for multi-series; brand blue for one series. */
  var S = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100'];
  var BRAND = '#2457A7';
  var STATUS = { good: '#0ca30c', warn: '#fab219', crit: '#d03b3b' };
  var INK = '#172B4D', MUTED = '#64748B', GRID = '#EDF0F5';
  var nf = new Intl.NumberFormat('en-NZ', { maximumFractionDigits: 0 });
  var money = function (v) { return 'SAT$' + nf.format(v); };
  var compact = new Intl.NumberFormat('en-NZ', { notation: 'compact', maximumFractionDigits: 1 });

  function base(opts) {
    return Object.assign({
      responsive: true, maintainAspectRatio: false,
      animation: reduce ? false : { duration: 600, easing: 'easeOutQuart' },
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { display: false, labels: { color: INK, boxWidth: 10, boxHeight: 10, usePointStyle: true, pointStyle: 'rectRounded', padding: 14 } },
        tooltip: { backgroundColor: '#14243A', titleColor: '#fff', bodyColor: '#E3E8EF', padding: 10, cornerRadius: 8,
                   boxPadding: 4, usePointStyle: true }
      }
    }, opts || {});
  }
  function axis(fmt, extra) {
    return Object.assign({ grid: { color: GRID, drawTicks: false }, border: { display: false },
      ticks: { color: MUTED, padding: 6, callback: function (v) { return fmt ? fmt(v) : compact.format(v); } } }, extra || {});
  }
  function catAxis(extra) {
    return Object.assign({ grid: { display: false }, border: { color: '#CDD5E0' }, ticks: { color: MUTED, autoSkipPadding: 10 } }, extra || {});
  }
  function make(id, config) {
    var el = document.getElementById(id);
    if (!el) return null;
    var c = new Chart(el, config);
    el.parentNode.classList.add('ready');
    el._fmt = config._fmt;
    charts.push(c);
    return c;
  }
  function bar(color, horizontal) {
    return { backgroundColor: color, borderRadius: 4, borderSkipped: horizontal ? 'left' : 'bottom',
             borderColor: '#fff', borderWidth: 0, maxBarThickness: horizontal ? 22 : 34, categoryPercentage: .8, barPercentage: .9 };
  }

  whenChart(function () {
    Chart.defaults.font.family = "Inter, -apple-system, 'Segoe UI', sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = MUTED;

    /* Stock health — status colours, legend + icons beside it */
    if (D.health) make('chHealth', {
      type: 'doughnut',
      data: { labels: D.health.labels, datasets: [{ data: D.health.values,
        backgroundColor: [STATUS.good, STATUS.warn, STATUS.crit], borderColor: '#fff', borderWidth: 2, hoverOffset: 4 }] },
      options: base({ cutout: '70%', interaction: { mode: 'nearest' },
        plugins: { legend: { display: false }, tooltip: base().plugins.tooltip } })
    });

    /* Stock by category / supplier: one series → single hue, no legend; Units/Value toggle */
    function rankChart(id, units, value) {
      if (!units) return;
      var horizontal = true;
      var c = make(id, {
        type: 'bar',
        data: { labels: units.labels, datasets: [Object.assign({ label: 'Units', data: units.values }, bar(BRAND, horizontal))] },
        options: base({ indexAxis: 'y', interaction: { mode: 'nearest', axis: 'y', intersect: false },
          scales: { x: axis(), y: catAxis({ ticks: { color: INK, callback: function (v) { var l = this.getLabelForValue(v); return l.length > 26 ? l.slice(0, 25) + '…' : l; } } }) } })
      });
      return { chart: c, sets: { units: units, value: value } };
    }
    var rank = {
      category: rankChart('chCategory', D.by_category, D.by_category_value),
      supplier: rankChart('chSupplier', D.by_supplier, D.by_supplier_value)
    };

    /* Daily movement: 4 types, stacked, legend on */
    var MV = [['in', 'Received'], ['out', 'Dispatched / out'], ['adjustment', 'Adjustments'], ['return', 'Returns']];
    var movement = null;
    if (D.movement) {
      movement = make('chMovement', {
        type: 'bar',
        data: { labels: D.movement.labels, datasets: MV.map(function (m, i) {
          return Object.assign({ label: m[1], data: D.movement.series[m[0]].units, _kind: m[0] }, bar(S[i]), { borderWidth: { top: 2 }, borderColor: '#fff', borderRadius: 3 });
        }) },
        options: base({ plugins: { legend: { display: true, position: 'bottom', labels: base().plugins.legend.labels }, tooltip: base().plugins.tooltip },
          scales: { x: catAxis({ stacked: true, ticks: { color: MUTED, maxRotation: 0, autoSkipPadding: 14 } }), y: axis(null, { stacked: true, beginAtZero: true }) } })
      });
      make('chMonths', {
        type: 'bar',
        data: { labels: D.movement.months.labels, datasets: [
          Object.assign({ label: 'Stock in', data: D.movement.months['in'] }, bar(S[0])),
          Object.assign({ label: 'Stock out', data: D.movement.months.out }, bar(S[1]))
        ] },
        options: base({ plugins: { legend: { display: true, position: 'bottom', labels: base().plugins.legend.labels }, tooltip: base().plugins.tooltip },
          scales: { x: catAxis(), y: axis(null, { beginAtZero: true }) } })
      });
    }

    /* Dispatch */
    if (D.dispatch) {
      make('chDispatch', {
        type: 'bar',
        data: { labels: D.dispatch.labels, datasets: [Object.assign({ label: 'Invoices dispatched', data: D.dispatch.daily }, bar(BRAND))] },
        options: base({ scales: { x: catAxis({ ticks: { color: MUTED, maxRotation: 0, autoSkipPadding: 14 } }),
          y: axis(function (v) { return Number.isInteger(v) ? nf.format(v) : ''; }, { beginAtZero: true }) } })
      });
      make('chSites', {
        type: 'bar',
        data: { labels: D.dispatch.sites.labels, datasets: [
          Object.assign({ label: 'Pending', data: D.dispatch.sites.pending }, bar(S[0], true)),
          Object.assign({ label: 'Dispatched (period)', data: D.dispatch.sites.dispatched }, bar(S[1], true))
        ] },
        options: base({ indexAxis: 'y', plugins: { legend: { display: true, position: 'bottom', labels: base().plugins.legend.labels }, tooltip: base().plugins.tooltip },
          scales: { x: axis(null, { beginAtZero: true }), y: catAxis({ ticks: { color: INK } }) } })
      });
    }

    /* Measure toggles */
    document.querySelectorAll('.mini-seg[data-toggle]').forEach(function (seg) {
      seg.addEventListener('click', function (e) {
        var btn = e.target.closest('button');
        if (!btn) return;
        seg.querySelectorAll('button').forEach(function (b) { b.classList.toggle('on', b === btn); });
        var mode = btn.dataset.mode, which = seg.dataset.toggle;
        if (which === 'movement' && movement) {
          movement.data.datasets.forEach(function (ds) { ds.data = D.movement.series[ds._kind][mode === 'count' ? 'count' : 'units']; });
          movement.update();
        } else if (rank[which]) {
          var r = rank[which], set = r.sets[mode] || r.sets.units;
          r.chart.data.labels = set.labels;
          r.chart.data.datasets[0].data = set.values;
          r.chart.data.datasets[0].label = mode === 'value' ? 'Value (SAT$, at cost)' : 'Units';
          r.chart.options.scales.x.ticks.callback = mode === 'value' ? function (v) { return 'SAT$' + compact.format(v); } : function (v) { return compact.format(v); };
          r.chart.options.plugins.tooltip.callbacks = mode === 'value' ? { label: function (ctx) { return ' ' + money(ctx.parsed.x); } } : {};
          r.chart.update();
          var tbl = document.querySelector('.chart-table[data-for="' + r.chart.canvas.id + '"]');
          if (tbl) { tbl.remove(); toggleTable(r.chart.canvas.id); }
        }
      });
    });
  });

  /* ── Table view for any chart (the accessible, exact-number alternative) ── */
  function toggleTable(id) {
    var canvas = document.getElementById(id);
    var chart = charts.find(function (c) { return c.canvas === canvas; });
    if (!chart) return;
    var box = canvas.parentNode;
    var existing = box.parentNode.querySelector('.chart-table[data-for="' + id + '"]');
    if (existing) { existing.remove(); return false; }
    var sets = chart.data.datasets;
    var html = '<table><thead><tr><th></th>' + sets.map(function (s) { return '<th class="num">' + esc(s.label) + '</th>'; }).join('') + '</tr></thead><tbody>';
    chart.data.labels.forEach(function (label, i) {
      html += '<tr><td>' + esc(label) + '</td>' + sets.map(function (s) { return '<td class="num">' + nf.format(s.data[i] || 0) + '</td>'; }).join('') + '</tr>';
    });
    var wrap = document.createElement('div');
    wrap.className = 'chart-table';
    wrap.dataset.for = id;
    wrap.innerHTML = html + '</tbody></table>';
    box.after(wrap);
    return true;
  }
  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  document.querySelectorAll('[data-table-for]').forEach(function (b) {
    b.addEventListener('click', function () {
      var open = toggleTable(b.dataset.tableFor);
      b.textContent = open ? 'Hide table' : 'Table';
    });
  });
})();
