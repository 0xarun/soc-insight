/**
 * charts.js – Chart.js renderers for SOC Insight
 */

const CHART_DEFAULTS = {
  font: { family: 'Inter, -apple-system, sans-serif', size: 12 },
  color: '#8b949e',
};
Chart.defaults.font = CHART_DEFAULTS.font;
Chart.defaults.color = CHART_DEFAULTS.color;

const SEV_COLORS = {
  Critical:      '#f85149',
  High:          '#e3b341',
  Medium:        '#d29922',
  Low:           '#3fb950',
  Informational: '#58a6ff',
  Unknown:       '#6e7681',
};

const PALETTE = ['#1f6feb','#3fb950','#e3b341','#f85149','#bc8cff','#58a6ff','#06d6a0','#f97316'];

const _chartInstances = {};

function _destroy(id) {
  if (_chartInstances[id]) {
    _chartInstances[id].destroy();
    delete _chartInstances[id];
  }
}

function _gridColor() { return 'rgba(48,54,61,.6)'; }

// ── Severity Doughnut ─────────────────────────────────────────────────────────
function renderSeverityChart(data) {
  _destroy('chart-severity');
  const ctx = document.getElementById('chart-severity');
  if (!ctx || !data.length) return;
  const labels = data.map(d => d.severity);
  const counts = data.map(d => d.total_alerts);
  const colors = labels.map(l => SEV_COLORS[l] || '#6e7681');
  _chartInstances['chart-severity'] = new Chart(ctx, {
    type: 'doughnut',
    data: { labels, datasets: [{ data: counts, backgroundColor: colors, borderWidth: 2, borderColor: '#0d1117', hoverOffset: 6 }] },
    options: {
      plugins: { legend: { position: 'right', labels: { padding: 14, font: { size: 12 }, color: '#e6edf3' } } },
      cutout: '62%',
    },
  });
}

// ── Monthly Trend Bar ─────────────────────────────────────────────────────────
function renderTrendChart(trend) {
  _destroy('chart-trend');
  const ctx = document.getElementById('chart-trend');
  if (!ctx || !trend.labels.length) return;
  _chartInstances['chart-trend'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: trend.labels,
      datasets: [{
        label: 'Alerts',
        data: trend.alert_counts,
        backgroundColor: 'rgba(31,111,235,.7)',
        borderColor: '#1f6feb',
        borderWidth: 1,
        borderRadius: 6,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: _gridColor() } },
        y: { beginAtZero: true, grid: { color: _gridColor() } },
      },
    },
  });
}

// ── MTTD / MTTR Line ──────────────────────────────────────────────────────────
function renderTimeChart(trend) {
  _destroy('chart-time');
  const ctx = document.getElementById('chart-time');
  if (!ctx || !trend.labels.length) return;
  _chartInstances['chart-time'] = new Chart(ctx, {
    type: 'line',
    data: {
      labels: trend.labels,
      datasets: [
        {
          label: 'Avg MTTD (min)',
          data: trend.mttd_avg_minutes,
          borderColor: '#bc8cff',
          backgroundColor: 'rgba(188,140,255,.1)',
          tension: 0.4,
          fill: true,
          pointRadius: 4,
          pointHoverRadius: 6,
        },
        {
          label: 'Avg MTTR (hr)',
          data: trend.mttr_avg_hours,
          borderColor: '#f97316',
          backgroundColor: 'rgba(249,115,22,.1)',
          tension: 0.4,
          fill: true,
          pointRadius: 4,
          pointHoverRadius: 6,
        },
      ],
    },
    options: {
      scales: {
        x: { grid: { color: _gridColor() } },
        y: { beginAtZero: true, grid: { color: _gridColor() } },
      },
    },
  });
}

// ── Analyst Workload Bar (small, sidebar style) ───────────────────────────────
function renderAnalystBarSmall(data) {
  _destroy('chart-analyst-bar');
  const ctx = document.getElementById('chart-analyst-bar');
  if (!ctx || !data.length) return;
  const top = data.slice(0, 8);
  _chartInstances['chart-analyst-bar'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: top.map(d => d.analyst),
      datasets: [{ label: 'Alerts', data: top.map(d => d.total_alerts), backgroundColor: '#06b6d4', borderRadius: 4 }],
    },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { beginAtZero: true, grid: { color: _gridColor() } },
        y: { grid: { display: false } },
      },
    },
  });
}

// ── Analyst Full Chart ─────────────────────────────────────────────────────────
function renderAnalystFull(data) {
  _destroy('chart-analyst-full');
  const ctx = document.getElementById('chart-analyst-full');
  if (!ctx || !data.length) return;
  _chartInstances['chart-analyst-full'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.analyst),
      datasets: [
        { label: 'Total', data: data.map(d => d.total_alerts), backgroundColor: 'rgba(31,111,235,.75)', borderRadius: 4 },
        { label: 'Critical', data: data.map(d => d.critical_count), backgroundColor: 'rgba(248,81,73,.75)', borderRadius: 4 },
      ],
    },
    options: {
      plugins: { legend: { labels: { color: '#e6edf3' } } },
      scales: {
        x: { grid: { color: _gridColor() } },
        y: { beginAtZero: true, grid: { color: _gridColor() } },
      },
    },
  });
}

// ── Analyst MTTR ──────────────────────────────────────────────────────────────
function renderAnalystMTTR(data) {
  _destroy('chart-analyst-mttr');
  const ctx = document.getElementById('chart-analyst-mttr');
  if (!ctx || !data.length) return;
  const filtered = data.filter(d => d.avg_mttr_seconds != null);
  _chartInstances['chart-analyst-mttr'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: filtered.map(d => d.analyst),
      datasets: [{
        label: 'Avg MTTR (hrs)',
        data: filtered.map(d => d.avg_mttr_seconds ? +(d.avg_mttr_seconds / 3600).toFixed(2) : 0),
        backgroundColor: filtered.map((_, i) => PALETTE[i % PALETTE.length]),
        borderRadius: 4,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: _gridColor() } },
        y: { beginAtZero: true, grid: { color: _gridColor() }, title: { display: true, text: 'Hours', color: '#8b949e' } },
      },
    },
  });
}

// ── True Positive Bar ─────────────────────────────────────────────────────────
function renderTPChart(data) {
  _destroy('chart-tp');
  const ctx = document.getElementById('chart-tp');
  if (!ctx || !data.length) return;
  _chartInstances['chart-tp'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.severity),
      datasets: [{
        label: 'True Positives',
        data: data.map(d => d.true_positives),
        backgroundColor: data.map(d => SEV_COLORS[d.severity] || '#6e7681'),
        borderRadius: 6,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: _gridColor() } },
        y: { beginAtZero: true, grid: { color: _gridColor() } },
      },
    },
  });
}

// ── SLA Chart ─────────────────────────────────────────────────────────────────
function renderSLAChart(data) {
  _destroy('chart-sla');
  const ctx = document.getElementById('chart-sla');
  if (!ctx || !data.length) return;
  _chartInstances['chart-sla'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.severity),
      datasets: [{
        label: 'Compliance %',
        data: data.map(d => d.compliance_pct),
        backgroundColor: data.map(d => d.compliance_pct >= 90 ? '#3fb950' : d.compliance_pct >= 70 ? '#e3b341' : '#f85149'),
        borderRadius: 6,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: _gridColor() } },
        y: { beginAtZero: true, max: 100, grid: { color: _gridColor() }, ticks: { callback: v => v + '%' } },
      },
    },
  });
}
