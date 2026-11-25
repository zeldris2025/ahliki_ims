/* Declarative Chart.js charts for the catalogue and stock pages.

   The view writes {key: spec} into a json_script block with id "chart-data"; each
   <canvas data-chart="key"> is drawn from its spec:
     { type: 'bar' | 'line', labels: [...], datasets: [{label, data}], stacked: bool,
       horizontal: bool, reference: {label, value} }
   Any button with data-table-for="<canvas id>" swaps in an exact-number table.
   A form with data-autosubmit submits when a select or radio changes. */
(function () {
  'use strict';
  var reduce = window.IMS && window.IMS.reduceMotion;

  /* Filters: submit on change; custom date range waits for its Apply button. */
  document.querySelectorAll('form[data-autosubmit]').forEach(function (form) {
    var custom = form.querySelector('.custom-dates');
    form.addEventListener('change', function (e) {
      if (e.target.name === 'range') {
        form.querySelectorAll('.seg-opt').forEach(function (o) { o.classList.toggle('on', o.contains(e.target)); });
        if (e.target.value === 'custom' && custom) { custom.hidden = false; custom.querySelector('input').focus(); return; }
        if (custom) custom.querySelectorAll('input').forEach(function (i) { i.disabled = true; });
      }
      if (e.target.type === 'date' || e.target.type === 'text' || e.target.type === 'search') return;
      document.body.classList.add('dash-loading');
      form.submit();
    });
  });

  var dataEl = document.getElementById('chart-data');
  if (!dataEl) return;
  var SPECS = JSON.parse(dataEl.textContent);

  /* Validated categorical order; brand blue when there is a single series. */
  var S = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100'];
  var BRAND = '#2457A7', INK = '#172B4D', MUTED = '#64748B', GRID = '#EDF0F5';
  var nf = new Intl.NumberFormat('en-NZ', { maximumFractionDigits: 0 });
  var compact = new Intl.NumberFormat('en-NZ', { notation: 'compact', maximumFractionDigits: 1 });
  var charts = [];

  function tooltip() {
    return { backgroundColor: '#14243A', titleColor: '#fff', bodyColor: '#E3E8EF', padding: 10, cornerRadius: 8,
             boxPadding: 4, usePointStyle: true,
             callbacks: { label: function (c) { return ' ' + c.dataset.label + ': ' + nf.format(c.parsed[c.chart.options.indexAxis === 'y' ? 'x' : 'y']); } } };
  }

  function config(spec) {
    var many = spec.datasets.length > 1 || spec.reference;
    var horizontal = !!spec.horizontal;
    var sets = spec.datasets.map(function (d, i) {
      var color = spec.datasets.length > 1 ? S[i % S.length] : BRAND;
      if (spec.type === 'line') {
        return { label: d.label, data: d.data, borderColor: color, backgroundColor: color + '1F', fill: true,
                 borderWidth: 2, tension: 0.25, pointRadius: 0, pointHoverRadius: 4, pointHitRadius: 10 };
      }
      return { label: d.label, data: d.data, backgroundColor: color, borderRadius: 4,
               borderSkipped: horizontal ? 'left' : 'bottom', borderColor: '#fff',
               borderWidth: spec.stacked ? { top: 2 } : 0,
               maxBarThickness: horizontal ? 22 : 34, categoryPercentage: 0.8, barPercentage: 0.9 };
    });
    if (spec.reference) {
      sets.push({ type: 'line', label: spec.reference.label, data: spec.labels.map(function () { return spec.reference.value; }),
                  borderColor: MUTED, borderDash: [5, 4], borderWidth: 1.5, pointRadius: 0, pointHitRadius: 0, fill: false });
    }
    var valueAxis = { beginAtZero: true, stacked: !!spec.stacked, grid: { color: GRID, drawTicks: false }, border: { display: false },
                      ticks: { color: MUTED, padding: 6, precision: 0, callback: function (v) { return compact.format(v); } } };
    var catAxis = { stacked: !!spec.stacked, grid: { display: false }, border: { color: '#CDD5E0' },
                    ticks: { color: horizontal ? INK : MUTED, maxRotation: 0, autoSkipPadding: 14 } };
    return {
      type: spec.type === 'line' ? 'line' : 'bar',
      data: { labels: spec.labels, datasets: sets },
      options: {
        responsive: true, maintainAspectRatio: false, indexAxis: horizontal ? 'y' : 'x',
        animation: reduce ? false : { duration: 600, easing: 'easeOutQuart' },
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: !!many, position: 'bottom',
                    labels: { color: INK, boxWidth: spec.type === 'line' ? 22 : 10, boxHeight: 10, usePointStyle: true,
                              pointStyle: spec.type === 'line' ? 'line' : 'rectRounded', padding: 14 } },
          tooltip: tooltip()
        },
        scales: horizontal ? { x: valueAxis, y: catAxis } : { x: catAxis, y: valueAxis }
      }
    };
  }

  function draw() {
    Chart.defaults.font.family = "Inter, -apple-system, 'Segoe UI', sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.color = MUTED;
    document.querySelectorAll('canvas[data-chart]').forEach(function (el) {
      var spec = SPECS[el.dataset.chart];
      if (!spec) return;
      charts.push(new Chart(el, config(spec)));
      el.parentNode.classList.add('ready');
    });
  }
  if (window.Chart) draw();
  else {
    var tries = 0, t = setInterval(function () {
      if (window.Chart || ++tries > 100) { clearInterval(t); if (window.Chart) draw(); }
    }, 50);
  }

  /* Sections (<details data-section>) remember open/closed and redraw charts on open. */
  document.querySelectorAll('details[data-section]').forEach(function (s) {
    var key = 'ims.sec.' + s.dataset.section;
    try { if (localStorage.getItem(key) === 'closed') s.open = false; } catch (e) {}
    s.addEventListener('toggle', function () {
      try { localStorage.setItem(key, s.open ? 'open' : 'closed'); } catch (e) {}
      if (s.open) charts.forEach(function (c) { c.resize(); });
    });
  });

  function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function toggleTable(id) {
    var canvas = document.getElementById(id);
    var chart = charts.find(function (c) { return c.canvas === canvas; });
    if (!chart) return false;
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
  document.querySelectorAll('[data-table-for]').forEach(function (b) {
    b.addEventListener('click', function () {
      b.textContent = toggleTable(b.dataset.tableFor) ? 'Hide table' : 'Table';
    });
  });
})();
