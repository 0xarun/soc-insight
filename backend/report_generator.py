"""
report_generator.py
Generates self-contained HTML SOC operational reports.
"""

from datetime import datetime
from typing import Any
import metrics_engine as me
import pandas as pd


def _badge(severity: str) -> str:
    colors = {
        "Critical": "#ef4444",
        "High":     "#f97316",
        "Medium":   "#eab308",
        "Low":      "#22c55e",
        "Informational": "#3b82f6",
    }
    bg = colors.get(severity, "#6b7280")
    return f'<span style="background:{bg};color:#fff;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600">{severity}</span>'


def generate_html_report(df: pd.DataFrame, filters: dict | None = None) -> str:
    filters = filters or {}
    kpi    = me.kpi_summary(df, **filters)
    sev    = me.severity_metrics(df, **filters)
    monthly = me.monthly_metrics(df, **filters)
    analyst = me.analyst_metrics(df, **filters)
    tp     = me.true_positive_metrics(df, **filters)
    sla    = me.sla_metrics(df, **filters)
    trend  = me.trend_data(df, **filters)
    top    = me.top_alerts(df, n=10, **filters)

    # Build filter description
    parts = []
    if filters.get("month") and filters["month"] != "All":
        parts.append(filters["month"])
    if filters.get("year") and filters["year"] != "All":
        parts.append(filters["year"])
    if filters.get("severity") and filters["severity"] != "All":
        parts.append(filters["severity"])
    if filters.get("analyst") and filters["analyst"] != "All":
        parts.append(f"Analyst: {filters['analyst']}")
    scope = " | ".join(parts) if parts else "All Data"
    ts = datetime.now().strftime("%d %b %Y %H:%M")

    # ── Severity table ────────────────────────────────────────────────────────
    sev_rows = ""
    for r in sev:
        sev_rows += f"""<tr>
          <td>{_badge(r['severity'])}</td>
          <td class="num">{r['total_alerts']}</td>
          <td class="num">{r['avg_mttd']}</td>
          <td class="num">{r['avg_mttr']}</td>
        </tr>"""

    # ── Monthly table ─────────────────────────────────────────────────────────
    monthly_rows = ""
    for r in monthly:
        monthly_rows += f"""<tr>
          <td><strong>{r['month']}</strong></td>
          <td class="num">{r['total_alerts']}</td>
          <td class="num crit">{r['critical']}</td>
          <td class="num high">{r['high']}</td>
          <td class="num med">{r['medium']}</td>
          <td class="num low">{r['low']}</td>
          <td class="num">{r['avg_mttd']}</td>
          <td class="num">{r['avg_mttr']}</td>
        </tr>"""

    # ── Analyst table ─────────────────────────────────────────────────────────
    analyst_rows = ""
    for r in analyst:
        analyst_rows += f"""<tr>
          <td><strong>{r['analyst']}</strong></td>
          <td class="num">{r['total_alerts']}</td>
          <td class="num crit">{r['critical_count']}</td>
          <td class="num">{r['avg_mttd']}</td>
          <td class="num">{r['avg_mttr']}</td>
          <td>{r['top_alert']}</td>
        </tr>"""

    # ── TP table ──────────────────────────────────────────────────────────────
    tp_rows = ""
    if tp:
        for r in tp:
            tp_rows += f"""<tr>
              <td>{_badge(r['severity'])}</td>
              <td class="num">{r['true_positives']}</td>
              <td class="num">{r['avg_mttd']}</td>
              <td class="num">{r['avg_mttr']}</td>
            </tr>"""
    else:
        tp_rows = '<tr><td colspan="4" style="text-align:center;color:#888">No True Positive data (Result column may not be present)</td></tr>'

    # ── SLA table ─────────────────────────────────────────────────────────────
    sla_rows = ""
    for r in sla:
        status_color = "#22c55e" if r["compliance_pct"] >= 90 else ("#eab308" if r["compliance_pct"] >= 70 else "#ef4444")
        sla_rows += f"""<tr>
          <td>{_badge(r['severity'])}</td>
          <td class="num">{r['total']}</td>
          <td class="num">{r['sla_threshold']}</td>
          <td class="num">{r['breached']}</td>
          <td class="num" style="color:{status_color};font-weight:700">{r['compliance_pct']}%</td>
        </tr>"""

    # ── Top alerts ────────────────────────────────────────────────────────────
    top_rows = ""
    for i, r in enumerate(top, 1):
        top_rows += f'<tr><td>{i}</td><td>{r["alert"]}</td><td class="num">{r["count"]}</td></tr>'

    # ── Chart data ────────────────────────────────────────────────────────────
    import json
    sev_labels = json.dumps([r["severity"] for r in sev])
    sev_counts = json.dumps([r["total_alerts"] for r in sev])
    trend_labels = json.dumps(trend["labels"])
    trend_alerts = json.dumps(trend["alert_counts"])
    trend_mttd   = json.dumps(trend["mttd_avg_minutes"])
    trend_mttr   = json.dumps(trend["mttr_avg_hours"])

    analyst_labels = json.dumps([r["analyst"] for r in analyst[:10]])
    analyst_counts = json.dumps([r["total_alerts"] for r in analyst[:10]])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SOC Operational Report – {scope}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',sans-serif;background:#f8f9fa;color:#1a1a2e;font-size:14px}}
  .report-wrap{{max-width:1200px;margin:0 auto;padding:24px}}
  header{{background:linear-gradient(135deg,#1e3a5f,#0f2340);color:#fff;padding:32px 40px;border-radius:16px;margin-bottom:28px}}
  header h1{{font-size:28px;font-weight:700;margin-bottom:6px}}
  header .meta{{font-size:13px;opacity:.75;margin-top:4px}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:16px;margin-bottom:28px}}
  .kpi-card{{background:#fff;border-radius:12px;padding:20px;box-shadow:0 2px 12px rgba(0,0,0,.08);border-top:4px solid}}
  .kpi-card.blue{{border-color:#3b82f6}} .kpi-card.red{{border-color:#ef4444}}
  .kpi-card.green{{border-color:#22c55e}} .kpi-card.orange{{border-color:#f97316}}
  .kpi-card.purple{{border-color:#8b5cf6}} .kpi-card.cyan{{border-color:#06b6d4}}
  .kpi-label{{font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px}}
  .kpi-value{{font-size:28px;font-weight:700;color:#1a1a2e}}
  .section{{background:#fff;border-radius:12px;padding:24px;margin-bottom:24px;box-shadow:0 2px 12px rgba(0,0,0,.08)}}
  .section h2{{font-size:18px;font-weight:700;color:#1e3a5f;margin-bottom:16px;padding-bottom:10px;border-bottom:2px solid #e5e7eb}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th{{background:#f1f5f9;padding:10px 12px;text-align:left;font-weight:600;color:#374151;border-bottom:2px solid #e5e7eb}}
  td{{padding:9px 12px;border-bottom:1px solid #f1f5f9;vertical-align:middle}}
  tr:last-child td{{border:none}}
  tr:hover td{{background:#f8faff}}
  .num{{text-align:right;font-variant-numeric:tabular-nums;font-family:monospace;font-size:13px}}
  .crit{{color:#ef4444;font-weight:600}} .high{{color:#f97316;font-weight:600}}
  .med{{color:#eab308;font-weight:600}} .low{{color:#22c55e;font-weight:600}}
  .charts-grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px}}
  .chart-card{{background:#fff;border-radius:12px;padding:20px;box-shadow:0 2px 12px rgba(0,0,0,.08)}}
  .chart-card h3{{font-size:14px;font-weight:600;color:#374151;margin-bottom:14px}}
  footer{{text-align:center;color:#9ca3af;font-size:12px;margin-top:32px;padding:16px}}
  @media print{{.report-wrap{{max-width:100%}} .charts-grid{{grid-template-columns:1fr 1fr}}}}
</style>
</head>
<body>
<div class="report-wrap">

<header>
  <h1>🛡 SOC Operational Report</h1>
  <div class="meta">Scope: <strong>{scope}</strong> &nbsp;|&nbsp; Generated: {ts}</div>
</header>

<!-- KPI Cards -->
<div class="kpi-grid">
  <div class="kpi-card blue"><div class="kpi-label">Total Alerts</div><div class="kpi-value">{kpi['total_alerts']}</div></div>
  <div class="kpi-card red"><div class="kpi-label">Critical Alerts</div><div class="kpi-value">{kpi['critical_alerts']}</div></div>
  <div class="kpi-card orange"><div class="kpi-label">Avg MTTD</div><div class="kpi-value" style="font-size:20px">{kpi['avg_mttd']}</div></div>
  <div class="kpi-card purple"><div class="kpi-label">Avg MTTR</div><div class="kpi-value" style="font-size:20px">{kpi['avg_mttr']}</div></div>
  <div class="kpi-card green"><div class="kpi-label">True Positives</div><div class="kpi-value">{kpi['true_positives']}</div></div>
  <div class="kpi-card cyan"><div class="kpi-label">Analysts Active</div><div class="kpi-value">{kpi['analysts_active']}</div></div>
</div>

<!-- Charts -->
<div class="charts-grid">
  <div class="chart-card"><h3>Alerts by Severity</h3><canvas id="sevChart"></canvas></div>
  <div class="chart-card"><h3>Monthly Alert Trend</h3><canvas id="trendChart"></canvas></div>
  <div class="chart-card"><h3>MTTD / MTTR Trend (avg mins / hrs)</h3><canvas id="timeChart"></canvas></div>
  <div class="chart-card"><h3>Analyst Workload</h3><canvas id="analystChart"></canvas></div>
</div>

<!-- Severity Breakdown -->
<div class="section">
  <h2>📊 Severity Breakdown</h2>
  <table>
    <thead><tr><th>Severity</th><th class="num">Total Alerts</th><th class="num">Avg MTTD</th><th class="num">Avg MTTR</th></tr></thead>
    <tbody>{sev_rows}</tbody>
  </table>
</div>

<!-- Monthly Breakdown -->
<div class="section">
  <h2>📅 Monthly Breakdown</h2>
  <table>
    <thead><tr><th>Month</th><th class="num">Total</th><th class="num">Critical</th><th class="num">High</th><th class="num">Medium</th><th class="num">Low</th><th class="num">Avg MTTD</th><th class="num">Avg MTTR</th></tr></thead>
    <tbody>{monthly_rows}</tbody>
  </table>
</div>

<!-- Analyst Performance -->
<div class="section">
  <h2>👤 Analyst Performance</h2>
  <table>
    <thead><tr><th>Analyst</th><th class="num">Alerts</th><th class="num">Critical</th><th class="num">Avg MTTD</th><th class="num">Avg MTTR</th><th>Top Alert Type</th></tr></thead>
    <tbody>{analyst_rows}</tbody>
  </table>
</div>

<!-- True Positive Analysis -->
<div class="section">
  <h2>✅ True Positive Analysis</h2>
  <table>
    <thead><tr><th>Severity</th><th class="num">True Positives</th><th class="num">Avg MTTD</th><th class="num">Avg MTTR</th></tr></thead>
    <tbody>{tp_rows}</tbody>
  </table>
</div>

<!-- SLA Compliance -->
<div class="section">
  <h2>⏱ SLA Compliance</h2>
  <table>
    <thead><tr><th>Severity</th><th class="num">Total</th><th class="num">SLA Threshold</th><th class="num">Breached</th><th class="num">Compliance</th></tr></thead>
    <tbody>{sla_rows}</tbody>
  </table>
</div>

<!-- Top Alerts -->
<div class="section">
  <h2>🔥 Top Alert Types</h2>
  <table>
    <thead><tr><th>#</th><th>Alert Type</th><th class="num">Count</th></tr></thead>
    <tbody>{top_rows}</tbody>
  </table>
</div>

<footer>SOC Insight Platform &nbsp;|&nbsp; Confidential &nbsp;|&nbsp; {ts}</footer>
</div>

<script>
const SEV_COLORS = {{'Critical':'#ef4444','High':'#f97316','Medium':'#eab308','Low':'#22c55e','Informational':'#3b82f6','Unknown':'#6b7280'}};
const labels = {sev_labels};
const bg = labels.map(l=>SEV_COLORS[l]||'#6b7280');

new Chart(document.getElementById('sevChart'),{{
  type:'doughnut', data:{{labels:{sev_labels},datasets:[{{data:{sev_counts},backgroundColor:bg,borderWidth:2,borderColor:'#fff'}}]}},
  options:{{plugins:{{legend:{{position:'right'}}}},cutout:'60%'}}
}});

const tl={trend_labels}, ta={trend_alerts};
new Chart(document.getElementById('trendChart'),{{
  type:'bar', data:{{labels:tl,datasets:[{{label:'Alerts',data:ta,backgroundColor:'#3b82f6',borderRadius:6}}]}},
  options:{{plugins:{{legend:{{display:false}}}},scales:{{y:{{beginAtZero:true}}}}}}
}});

new Chart(document.getElementById('timeChart'),{{
  type:'line', data:{{labels:tl,datasets:[
    {{label:'Avg MTTD (min)',data:{trend_mttd},borderColor:'#8b5cf6',tension:.4,fill:false}},
    {{label:'Avg MTTR (hr)',data:{trend_mttr},borderColor:'#f97316',tension:.4,fill:false}}
  ]}}, options:{{scales:{{y:{{beginAtZero:true}}}}}}
}});

new Chart(document.getElementById('analystChart'),{{
  type:'bar', data:{{labels:{analyst_labels},datasets:[{{label:'Alerts',data:{analyst_counts},backgroundColor:'#06b6d4',borderRadius:4}}]}},
  options:{{indexAxis:'y',plugins:{{legend:{{display:false}}}},scales:{{x:{{beginAtZero:true}}}}}}
}});
</script>
</body>
</html>"""
