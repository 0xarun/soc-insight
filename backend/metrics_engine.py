"""
metrics_engine.py
Analytics engine for SOC Insight.
All functions take the clean DataFrame from excel_parser and return JSON-serialisable dicts.
"""

import numpy as np
import pandas as pd
from excel_parser import format_seconds, MONTH_ORDER

SLA_DEFAULTS = {
    "Critical": 4 * 3600,      # 4 hours in seconds
    "High":     8 * 3600,      # 8 hours
    "Medium":   24 * 3600,     # 24 hours
    "Low":      72 * 3600,     # 72 hours
}


def _safe_mean(series: pd.Series) -> float | None:
    v = series.dropna()
    return float(v.mean()) if not v.empty else None


def _fmt(val) -> str:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    return format_seconds(val)


def _apply_filters(df: pd.DataFrame, month=None, year=None,
                   severity=None, analyst=None) -> pd.DataFrame:
    if month and month != "All":
        df = df[df["Month"].str.lower() == month.lower()]
    if year and year != "All":
        df = df[df["Year"] == str(year)]
    if severity and severity != "All":
        df = df[df["Severity"].str.lower() == severity.lower()]
    if analyst and analyst != "All":
        df = df[df["Analyst"].str.lower() == analyst.lower()]
    return df


# ──────────────────────────────────────────────────────────────────────────────
def kpi_summary(df: pd.DataFrame, **filters) -> dict:
    d = _apply_filters(df, **filters)
    total = len(d)
    critical = len(d[d["Severity"] == "Critical"])
    avg_mttd = _safe_mean(d["MTTD_seconds"])
    avg_mttr = _safe_mean(d["MTTR_seconds"])

    tp_count = 0
    tp_ratio = 0.0
    if "Result" in d.columns and d["Result"].nunique() > 1:
        tp_df = d[d["Result"].str.lower().str.contains("true positive", na=False)]
        tp_count = len(tp_df)
        tp_ratio = round((tp_count / total * 100), 1) if total > 0 else 0.0

    analysts_active = d["Analyst"].nunique()

    return {
        "total_alerts": total,
        "critical_alerts": critical,
        "avg_mttd": _fmt(avg_mttd),
        "avg_mttr": _fmt(avg_mttr),
        "avg_mttd_seconds": avg_mttd,
        "avg_mttr_seconds": avg_mttr,
        "true_positives": tp_count,
        "tp_ratio": tp_ratio,
        "analysts_active": analysts_active,
    }


# ──────────────────────────────────────────────────────────────────────────────
def severity_metrics(df: pd.DataFrame, **filters) -> list[dict]:
    d = _apply_filters(df, **filters)
    rows = []
    sev_order = ["Critical", "High", "Medium", "Low", "Informational", "Unknown"]
    for sev in sev_order:
        sub = d[d["Severity"] == sev]
        if sub.empty:
            continue
        rows.append({
            "severity": sev,
            "total_alerts": len(sub),
            "avg_mttd": _fmt(_safe_mean(sub["MTTD_seconds"])),
            "avg_mttr": _fmt(_safe_mean(sub["MTTR_seconds"])),
            "avg_mttd_seconds": _safe_mean(sub["MTTD_seconds"]),
            "avg_mttr_seconds": _safe_mean(sub["MTTR_seconds"]),
        })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
def monthly_metrics(df: pd.DataFrame, **filters) -> list[dict]:
    d = _apply_filters(df, month=None, year=filters.get("year"),
                       severity=filters.get("severity"), analyst=filters.get("analyst"))
    rows = []
    months = sorted(d["Month"].unique().tolist(),
                    key=lambda m: MONTH_ORDER.index(m) if m in MONTH_ORDER else 99)
    for month in months:
        if month == "Unknown":
            continue
        sub = d[d["Month"] == month]
        rows.append({
            "month": month,
            "total_alerts": len(sub),
            "critical": len(sub[sub["Severity"] == "Critical"]),
            "high": len(sub[sub["Severity"] == "High"]),
            "medium": len(sub[sub["Severity"] == "Medium"]),
            "low": len(sub[sub["Severity"] == "Low"]),
            "avg_mttd": _fmt(_safe_mean(sub["MTTD_seconds"])),
            "avg_mttr": _fmt(_safe_mean(sub["MTTR_seconds"])),
            "avg_mttd_seconds": _safe_mean(sub["MTTD_seconds"]),
            "avg_mttr_seconds": _safe_mean(sub["MTTR_seconds"]),
        })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
def monthly_severity_breakdown(df: pd.DataFrame, **filters) -> list[dict]:
    """Month x Severity cross-table."""
    d = _apply_filters(df, month=None, year=filters.get("year"),
                       severity=None, analyst=filters.get("analyst"))
    rows = []
    months = sorted(d["Month"].unique().tolist(),
                    key=lambda m: MONTH_ORDER.index(m) if m in MONTH_ORDER else 99)
    sev_order = ["Critical", "High", "Medium", "Low", "Informational"]
    for month in months:
        if month == "Unknown":
            continue
        sub_m = d[d["Month"] == month]
        for sev in sev_order:
            sub = sub_m[sub_m["Severity"] == sev]
            if sub.empty:
                continue
            rows.append({
                "month": month,
                "severity": sev,
                "total_alerts": len(sub),
                "avg_mttd": _fmt(_safe_mean(sub["MTTD_seconds"])),
                "avg_mttr": _fmt(_safe_mean(sub["MTTR_seconds"])),
            })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
def analyst_metrics(df: pd.DataFrame, **filters) -> list[dict]:
    d = _apply_filters(df, **filters)
    rows = []
    for analyst in sorted(d["Analyst"].unique()):
        if analyst in ("Unknown", ""):
            continue
        sub = d[d["Analyst"] == analyst]
        rows.append({
            "analyst": analyst,
            "total_alerts": len(sub),
            "avg_mttd": _fmt(_safe_mean(sub["MTTD_seconds"])),
            "avg_mttr": _fmt(_safe_mean(sub["MTTR_seconds"])),
            "avg_mttd_seconds": _safe_mean(sub["MTTD_seconds"]),
            "avg_mttr_seconds": _safe_mean(sub["MTTR_seconds"]),
            "critical_count": len(sub[sub["Severity"] == "Critical"]),
            "top_alert": sub["Alert"].mode().iloc[0] if not sub["Alert"].mode().empty else "N/A",
        })
    # Sort by alerts handled desc
    rows.sort(key=lambda r: r["total_alerts"], reverse=True)
    return rows


# ──────────────────────────────────────────────────────────────────────────────
def true_positive_metrics(df: pd.DataFrame, **filters) -> list[dict]:
    d = _apply_filters(df, **filters)
    tp = d[d["Result"].str.lower().str.contains("true positive", na=False)]
    if tp.empty:
        return []
    rows = []
    sev_order = ["Critical", "High", "Medium", "Low", "Informational"]
    for sev in sev_order:
        sub = tp[tp["Severity"] == sev]
        if sub.empty:
            continue
        rows.append({
            "severity": sev,
            "true_positives": len(sub),
            "avg_mttd": _fmt(_safe_mean(sub["MTTD_seconds"])),
            "avg_mttr": _fmt(_safe_mean(sub["MTTR_seconds"])),
        })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
def sla_metrics(df: pd.DataFrame, sla_map: dict | None = None, **filters) -> list[dict]:
    d = _apply_filters(df, **filters)
    sla = sla_map or SLA_DEFAULTS
    rows = []
    for sev, threshold in sla.items():
        sub = d[d["Severity"] == sev]
        total = len(sub)
        if total == 0:
            continue
        valid = sub["MTTR_seconds"].dropna()
        breached = int((valid > threshold).sum())
        compliance = round((1 - breached / total) * 100, 1) if total > 0 else 100.0
        rows.append({
            "severity": sev,
            "total": total,
            "sla_threshold": format_seconds(threshold),
            "breached": breached,
            "compliance_pct": compliance,
        })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
def top_alerts(df: pd.DataFrame, n: int = 10, **filters) -> list[dict]:
    d = _apply_filters(df, **filters)
    counts = d["Alert"].value_counts().head(n)
    return [{"alert": k, "count": int(v)} for k, v in counts.items()]


# ──────────────────────────────────────────────────────────────────────────────
def trend_data(df: pd.DataFrame, **filters) -> dict:
    """Return data for trend charts (monthly)."""
    d = _apply_filters(df, month=None, year=filters.get("year"),
                       severity=filters.get("severity"), analyst=filters.get("analyst"))
    months = sorted(d["Month"].unique().tolist(),
                    key=lambda m: MONTH_ORDER.index(m) if m in MONTH_ORDER else 99)
    months = [m for m in months if m != "Unknown"]

    labels = months
    alert_counts = []
    mttd_avgs = []
    mttr_avgs = []

    for m in months:
        sub = d[d["Month"] == m]
        alert_counts.append(len(sub))
        mttd_avgs.append(round(_safe_mean(sub["MTTD_seconds"]) / 60, 1)
                         if _safe_mean(sub["MTTD_seconds"]) else 0)
        mttr_avgs.append(round(_safe_mean(sub["MTTR_seconds"]) / 3600, 2)
                         if _safe_mean(sub["MTTR_seconds"]) else 0)

    return {
        "labels": labels,
        "alert_counts": alert_counts,
        "mttd_avg_minutes": mttd_avgs,
        "mttr_avg_hours": mttr_avgs,
    }


# ──────────────────────────────────────────────────────────────────────────────
def raw_data_page(df: pd.DataFrame, page: int = 1, page_size: int = 50,
                  search: str = "", **filters) -> dict:
    d = _apply_filters(df, **filters)
    if search:
        mask = d.apply(lambda row: row.astype(str).str.contains(
            search, case=False, na=False).any(), axis=1)
        d = d[mask]

    total = len(d)
    start = (page - 1) * page_size
    end = start + page_size
    page_df = d.iloc[start:end]

    cols = ["INC Number", "Date", "Analyst", "Alert", "Severity",
            "Action Taken", "MTTD", "MTTR", "Result", "Month"]
    cols = [c for c in cols if c in page_df.columns]

    records = []
    for _, row in page_df[cols].iterrows():
        rec = {}
        for c in cols:
            v = row[c]
            if pd.isna(v):
                rec[c] = ""
            elif isinstance(v, pd.Timestamp):
                rec[c] = v.strftime("%d %b %Y %H:%M")
            else:
                rec[c] = str(v)
        records.append(rec)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 1,
        "rows": records,
        "columns": cols,
    }
