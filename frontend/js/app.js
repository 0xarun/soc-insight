/**
 * app.js – Main application controller for SOC Insight
 */

const BASE = '';
let SESSION_TOKEN = null;
let METADATA = null;
let CURRENT_TAB = 'dashboard';
let RAW_PAGE = 1;
let REPORT_HTML = null;

// ── Toast notifications ───────────────────────────────────────────────────────
const App = {
  toast(msg, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.innerHTML = `<span>${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ'}</span> ${msg}`;
    container.appendChild(el);
    setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; setTimeout(() => el.remove(), 400); }, duration);
  },
};

// ── Tab switching ─────────────────────────────────────────────────────────────
function switchTab(name) {
  CURRENT_TAB = name;
  document.querySelectorAll('.tab-panel').forEach(el => el.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
  const panel = document.getElementById(`tab-${name}`);
  if (panel) panel.classList.add('active');
  const navItem = document.querySelector(`.nav-item[data-tab="${name}"]`);
  if (navItem) navItem.classList.add('active');

  const titles = {
    dashboard: 'Dashboard', monthly: 'Monthly View',
    analyst: 'Analyst Performance', tpanalysis: 'True Positives',
    sla: 'SLA Compliance', rawdata: 'Raw Data', chat: 'AI Chat', report: 'Report',
  };
  document.getElementById('page-title').innerHTML =
    `${titles[name] || name} <span id="page-sub"></span>`;

  const showSearch = name === 'rawdata';
  document.getElementById('global-search-wrap').style.display = showSearch ? 'flex' : 'none';
}

document.querySelectorAll('.nav-item[data-tab]').forEach(el => {
  el.addEventListener('click', () => switchTab(el.dataset.tab));
});

// ── Filters ───────────────────────────────────────────────────────────────────
function getFilters() {
  return {
    month:    document.getElementById('filter-month').value,
    year:     document.getElementById('filter-year').value,
    severity: document.getElementById('filter-severity').value,
    analyst:  document.getElementById('filter-analyst').value,
  };
}

function buildQueryParams(extra = {}) {
  const f = { ...getFilters(), ...extra };
  const p = new URLSearchParams({ token: SESSION_TOKEN });
  Object.entries(f).forEach(([k, v]) => { if (v && v !== 'All') p.set(k, v); });
  return p.toString();
}

document.getElementById('apply-filters').addEventListener('click', loadMetrics);
document.getElementById('reset-filters').addEventListener('click', () => {
  ['filter-month', 'filter-year', 'filter-severity', 'filter-analyst'].forEach(id => {
    document.getElementById(id).value = 'All';
  });
  loadMetrics();
});

// ── Populate filter dropdowns ─────────────────────────────────────────────────
function populateFilters(meta) {
  const monthSel = document.getElementById('filter-month');
  monthSel.innerHTML = '<option value="All">All Months</option>';
  (meta.months_available || []).forEach(m => {
    monthSel.innerHTML += `<option>${m}</option>`;
  });

  const yearSel = document.getElementById('filter-year');
  yearSel.innerHTML = '<option value="All">All Years</option>';
  (meta.years_available || []).forEach(y => {
    yearSel.innerHTML += `<option>${y}</option>`;
  });

  const analystSel = document.getElementById('filter-analyst');
  analystSel.innerHTML = '<option value="All">All Analysts</option>';
  (meta.analysts || []).forEach(a => {
    analystSel.innerHTML += `<option>${a}</option>`;
  });
}

// ── Severity badge helper ─────────────────────────────────────────────────────
function sevBadge(s) {
  const cls = { Critical: 'critical', High: 'high', Medium: 'medium', Low: 'low', Informational: 'info' }[s] || 'unknown';
  return `<span class="badge badge-${cls}">${s}</span>`;
}

// ── Load all metrics ──────────────────────────────────────────────────────────
async function loadMetrics() {
  if (!SESSION_TOKEN) return;
  try {
    const resp = await fetch(`${BASE}/metrics?${buildQueryParams()}`);
    if (!resp.ok) { const e = await resp.json(); throw new Error(e.detail || 'Metrics fetch failed'); }
    const data = await resp.json();
    renderDashboard(data);
    renderMonthly(data);
    renderAnalyst(data);
    renderTP(data);
    renderSLA(data);
    loadRawData(1);
  } catch (e) {
    App.toast(`Error loading metrics: ${e.message}`, 'error');
  }
}

// ── Dashboard ─────────────────────────────────────────────────────────────────
function renderDashboard(data) {
  const k = data.kpi;
  document.getElementById('kpi-total').textContent    = k.total_alerts.toLocaleString();
  document.getElementById('kpi-critical').textContent = k.critical_alerts.toLocaleString();
  document.getElementById('kpi-mttd').textContent     = k.avg_mttd;
  document.getElementById('kpi-mttr').textContent     = k.avg_mttr;
  document.getElementById('kpi-tp').textContent       = k.true_positives.toLocaleString();
  document.getElementById('kpi-tp-ratio').textContent = k.tp_ratio + '% of total';
  document.getElementById('kpi-analysts').textContent = k.analysts_active;

  // Charts
  renderSeverityChart(data.severity_metrics);
  renderTrendChart(data.trend);
  renderTimeChart(data.trend);
  renderAnalystBarSmall(data.analyst_metrics);

  // Top alerts table
  const tbody = document.getElementById('top-alerts-tbody');
  tbody.innerHTML = data.top_alerts.map((r, i) =>
    `<tr><td>${i + 1}</td><td>${r.alert}</td><td class="num">${r.count}</td></tr>`
  ).join('') || '<tr><td colspan="3" class="empty-state"><small>No data</small></td></tr>';

  // Severity table
  const stbody = document.getElementById('severity-tbody');
  stbody.innerHTML = data.severity_metrics.map(r =>
    `<tr><td>${sevBadge(r.severity)}</td><td class="num">${r.total_alerts}</td><td class="num">${r.avg_mttd}</td><td class="num">${r.avg_mttr}</td></tr>`
  ).join('') || '<tr><td colspan="4"><small style="color:var(--text-muted)">No data</small></td></tr>';
}

// ── Monthly ───────────────────────────────────────────────────────────────────
function renderMonthly(data) {
  const tbody = document.getElementById('monthly-tbody');
  tbody.innerHTML = data.monthly_metrics.map(r =>
    `<tr>
      <td><strong>${r.month}</strong></td>
      <td class="num"><strong>${r.total_alerts}</strong></td>
      <td class="num" style="color:var(--critical)">${r.critical}</td>
      <td class="num" style="color:var(--orange)">${r.high}</td>
      <td class="num" style="color:var(--medium)">${r.medium}</td>
      <td class="num" style="color:var(--low)">${r.low}</td>
      <td class="num">${r.avg_mttd}</td>
      <td class="num">${r.avg_mttr}</td>
    </tr>`
  ).join('') || '<tr><td colspan="8" style="text-align:center;padding:24px;color:var(--text-muted)">No data for selected filters</td></tr>';

  document.getElementById('monthly-sub').textContent =
    `${data.monthly_metrics.length} months`;

  const s2body = document.getElementById('monthly-sev-tbody');
  s2body.innerHTML = data.monthly_severity.map(r =>
    `<tr><td>${r.month}</td><td>${sevBadge(r.severity)}</td><td class="num">${r.total_alerts}</td><td class="num">${r.avg_mttd}</td><td class="num">${r.avg_mttr}</td></tr>`
  ).join('') || '<tr><td colspan="5" style="text-align:center;padding:24px;color:var(--text-muted)">No data</td></tr>';
}

// ── Analyst ───────────────────────────────────────────────────────────────────
function renderAnalyst(data) {
  renderAnalystFull(data.analyst_metrics);
  renderAnalystMTTR(data.analyst_metrics);

  document.getElementById('analyst-count').textContent =
    `${data.analyst_metrics.length} analysts`;

  const tbody = document.getElementById('analyst-tbody');
  tbody.innerHTML = data.analyst_metrics.map(r =>
    `<tr>
      <td><strong>${r.analyst}</strong></td>
      <td class="num">${r.total_alerts}</td>
      <td class="num" style="color:var(--critical)">${r.critical_count}</td>
      <td class="num">${r.avg_mttd}</td>
      <td class="num">${r.avg_mttr}</td>
      <td style="font-size:12px;color:var(--text-muted)">${r.top_alert}</td>
    </tr>`
  ).join('') || '<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text-muted)">No data</td></tr>';
}

// ── True Positives ────────────────────────────────────────────────────────────
function renderTP(data) {
  renderTPChart(data.true_positive_metrics);
  const tbody = document.getElementById('tp-tbody');
  if (!data.true_positive_metrics.length) {
    tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;padding:24px;color:var(--text-muted)">
      No True Positive data found. Make sure your Excel has a "Result" column with "True Positive" values.</td></tr>`;
    return;
  }
  tbody.innerHTML = data.true_positive_metrics.map(r =>
    `<tr>
      <td>${sevBadge(r.severity)}</td>
      <td class="num"><strong>${r.true_positives}</strong></td>
      <td class="num">${r.avg_mttd}</td>
      <td class="num">${r.avg_mttr}</td>
    </tr>`
  ).join('');
}

// ── SLA ───────────────────────────────────────────────────────────────────────
function renderSLA(data) {
  renderSLAChart(data.sla_metrics);
  const tbody = document.getElementById('sla-tbody');
  tbody.innerHTML = data.sla_metrics.map(r => {
    const color = r.compliance_pct >= 90 ? '#3fb950' : r.compliance_pct >= 70 ? '#e3b341' : '#f85149';
    const bar = `<div class="sla-bar"><div class="sla-fill" style="width:${r.compliance_pct}%;background:${color}"></div></div>`;
    return `<tr>
      <td>${sevBadge(r.severity)}</td>
      <td class="num">${r.total}</td>
      <td class="num">${r.sla_threshold}</td>
      <td class="num" style="color:var(--red)">${r.breached}</td>
      <td class="num" style="color:${color};font-weight:700">${r.compliance_pct}%</td>
      <td>${bar}</td>
    </tr>`;
  }).join('') || '<tr><td colspan="6" style="text-align:center;padding:24px;color:var(--text-muted)">No SLA data available (MTTR not found)</td></tr>';
}

// ── Raw Data ──────────────────────────────────────────────────────────────────
async function loadRawData(page = 1) {
  if (!SESSION_TOKEN) return;
  RAW_PAGE = page;
  const search = document.getElementById('raw-search')?.value || '';
  const qs = buildQueryParams({ page, page_size: 50, search });
  try {
    const resp = await fetch(`${BASE}/data?${qs}`);
    const data = await resp.json();

    document.getElementById('raw-count').textContent = `${data.total} rows`;

    // Headers
    const thead = document.getElementById('raw-thead');
    thead.innerHTML = '<tr>' + data.columns.map(c => `<th>${c}</th>`).join('') + '</tr>';

    // Body
    const tbody = document.getElementById('raw-tbody');
    if (!data.rows.length) {
      tbody.innerHTML = `<tr><td colspan="${data.columns.length}" style="text-align:center;padding:40px;color:var(--text-muted)">No results found</td></tr>`;
      return;
    }
    tbody.innerHTML = data.rows.map(row =>
      '<tr>' + data.columns.map(c => {
        const v = row[c] || '';
        if (c === 'Severity') return `<td>${sevBadge(v)}</td>`;
        if (c === 'MTTD' || c === 'MTTR') return `<td class="num"><code style="font-size:12px">${v}</code></td>`;
        return `<td>${v}</td>`;
      }).join('') + '</tr>'
    ).join('');

    // Pagination
    const pg = document.getElementById('raw-pagination');
    pg.innerHTML = '';
    if (data.pages > 1) {
      const makeBtn = (label, p, active = false, disabled = false) => {
        const btn = document.createElement('button');
        btn.className = 'page-btn' + (active ? ' active' : '');
        btn.textContent = label;
        btn.disabled = disabled;
        btn.addEventListener('click', () => loadRawData(p));
        return btn;
      };
      pg.appendChild(makeBtn('‹ Prev', page - 1, false, page <= 1));
      const start = Math.max(1, page - 2), end = Math.min(data.pages, page + 2);
      for (let i = start; i <= end; i++) pg.appendChild(makeBtn(i, i, i === page));
      pg.appendChild(makeBtn('Next ›', page + 1, false, page >= data.pages));
      const info = document.createElement('span');
      info.className = 'page-info';
      info.textContent = `Page ${page} of ${data.pages}`;
      pg.appendChild(info);
    }
  } catch (e) {
    App.toast(`Error loading data: ${e.message}`, 'error');
  }
}

let _rawSearchTimer;
document.getElementById('raw-search')?.addEventListener('input', () => {
  clearTimeout(_rawSearchTimer);
  _rawSearchTimer = setTimeout(() => loadRawData(1), 400);
});

// ── Report ────────────────────────────────────────────────────────────────────
document.getElementById('gen-report-btn').addEventListener('click', async () => {
  if (!SESSION_TOKEN) { App.toast('Please upload a file first', 'error'); return; }
  const btn = document.getElementById('gen-report-btn');
  btn.disabled = true; btn.textContent = '⏳ Generating…';
  try {
    const resp = await fetch(`${BASE}/report?${buildQueryParams()}`);
    const html = await resp.text();
    REPORT_HTML = html;
    const frame = document.getElementById('report-frame');
    frame.srcdoc = html;
    App.toast('Report generated!', 'success');
  } catch (e) {
    App.toast('Report generation failed', 'error');
  } finally {
    btn.disabled = false; btn.textContent = '🔄 Generate Report';
  }
});

document.getElementById('download-report-btn').addEventListener('click', () => {
  if (!REPORT_HTML) { App.toast('Generate a report first', 'error'); return; }
  const blob = new Blob([REPORT_HTML], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = 'soc_report.html'; a.click();
  URL.revokeObjectURL(url);
});

// ── Export Excel ──────────────────────────────────────────────────────────────
document.getElementById('export-btn').addEventListener('click', () => {
  if (!SESSION_TOKEN) { App.toast('Please upload a file first', 'error'); return; }
  window.location.href = `${BASE}/export/excel?${buildQueryParams()}`;
});

// ── File Upload ───────────────────────────────────────────────────────────────
function resetUpload() {
  document.getElementById('upload-error').style.display = 'none';
  document.getElementById('upload-progress').classList.remove('show');
  document.getElementById('progress-bar').style.width = '0%';
  document.getElementById('file-input').value = '';
}

async function doUpload(file) {
  const errorEl = document.getElementById('upload-error');
  const progressEl = document.getElementById('upload-progress');
  const bar = document.getElementById('progress-bar');
  const statusText = document.getElementById('upload-status-text');

  errorEl.style.display = 'none';
  progressEl.classList.add('show');
  statusText.textContent = 'Reading file…';
  bar.style.width = '20%';

  const formData = new FormData();
  formData.append('file', file);

  try {
    bar.style.width = '50%';
    statusText.textContent = 'Parsing Excel data…';
    const resp = await fetch(`${BASE}/upload`, { method: 'POST', body: formData });
    bar.style.width = '80%';
    statusText.textContent = 'Computing metrics…';

    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Upload failed');
    }

    const data = await resp.json();
    bar.style.width = '100%';
    SESSION_TOKEN = data.session_token;
    METADATA = data;

    // Populate filters
    populateFilters(data);

    // Show app
    document.getElementById('upload-overlay').style.display = 'none';
    document.getElementById('app').style.display = 'flex';

    // Session info
    const si = document.getElementById('session-info');
    si.textContent = `${data.row_count} incidents · ${data.date_range.from} – ${data.date_range.to}`;

    // Warnings
    if (data.warnings && data.warnings.length) {
      data.warnings.forEach(w => App.toast(w, 'info', 8000));
    }

    await loadMetrics();
    App.toast(`✅ Loaded ${data.row_count} incidents from ${file.name}`, 'success');

  } catch (e) {
    bar.style.width = '0%';
    progressEl.classList.remove('show');
    errorEl.style.display = 'block';
    errorEl.textContent = '⚠ ' + e.message;
  }
}

// File input + drag-drop
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');

dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', e => { if (e.target.files[0]) doUpload(e.target.files[0]); });

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) doUpload(file);
});

// ── Health check & Ollama status ──────────────────────────────────────────────
async function checkHealth() {
  try {
    const resp = await fetch(`${BASE}/health`);
    const data = await resp.json();
    document.getElementById('server-dot').className = 'status-dot';
    document.getElementById('server-status').textContent = 'Server connected';

    const ollamaDot = document.getElementById('ollama-dot');
    const ollamaStatus = document.getElementById('ollama-status');
    const badge = document.getElementById('ollama-badge');

    if (data.ollama === 'connected') {
      ollamaDot.className = 'status-dot';
      ollamaStatus.textContent = 'Ollama ready';
      badge.textContent = 'AI ✓';
      badge.style.color = 'var(--green)';
    } else {
      ollamaDot.className = 'status-dot offline';
      ollamaStatus.textContent = 'Ollama offline';
      badge.textContent = 'AI ✗';
    }
  } catch {
    document.getElementById('server-dot').className = 'status-dot offline';
    document.getElementById('server-status').textContent = 'Server offline';
  }
}

checkHealth();
setInterval(checkHealth, 30000);

// ── Init chat ─────────────────────────────────────────────────────────────────
Chat.init(() => SESSION_TOKEN);
