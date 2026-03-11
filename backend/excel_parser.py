"""
excel_parser.py
Robust Excel ingestion for SOC Insight.
Handles noisy data, missing columns, varied date/time formats.
"""

import io
import re
import numpy as np
import pandas as pd
from dateutil import parser as date_parser
from typing import Dict, Any, Tuple

# ─────────────────────────── Column synonyms ────────────────────────────────
COLUMN_ALIASES = {
    "inc number":      ["inc number", "inc no", "incident number", "incident id", "inc_number", "incnumber", "ticket", "ticket id", "id"],
    "date":            ["date", "incident date", "inc date", "log date"],
    "analyst":         ["analyst", "analyst name", "assigned to", "owner", "handler", "responder"],
    "alert":           ["alert", "alert name", "alert type", "alert description", "threat", "event"],
    "severity":        ["severity", "priority", "sev", "level", "criticality"],
    "action taken":    ["action taken", "action", "response", "resolution", "remediation"],
    "occurrence time": ["occurrence time", "occurance time", "occurred time", "event time", "start time", "occurred at"],
    "detection time":  ["detection time", "detected time", "detected at", "alert time"],
    "mttd":            ["mttd", "mean time to detect", "time to detect", "detection duration"],
    "mttr":            ["mttr", "mean time to respond", "time to respond", "response duration", "resolution time"],
    "result":          ["result", "incident type", "classification", "tp/fp", "true positive", "verdict"],
    "resolved time":   ["resolved time", "resolve time", "closure time", "close time", "resolution time"],
}


def _normalise_header(col: str) -> str:
    return re.sub(r"[\s_\-]+", " ", str(col)).strip().lower()


def _match_columns(df: pd.DataFrame) -> Dict[str, str]:
    """Return mapping of canonical_name -> actual_df_column."""
    norm_cols = {_normalise_header(c): c for c in df.columns}
    mapping = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in norm_cols:
                mapping[canonical] = norm_cols[alias]
                break
    return mapping


def _parse_time_str(val) -> pd.Timedelta | None:
    """Parse HH:MM:SS / H:MM:SS / minutes strings into Timedelta."""
    if pd.isna(val):
        return None
    s = str(val).strip()
    # Already timedelta
    if isinstance(val, pd.Timedelta):
        return val
    # Pattern HH:MM:SS or H:MM:SS
    m = re.match(r"^(\d+):(\d{2}):(\d{2})$", s)
    if m:
        h, mi, sec = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return pd.Timedelta(hours=h, minutes=mi, seconds=sec)
    # Pattern HH:MM
    m = re.match(r"^(\d+):(\d{2})$", s)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        return pd.Timedelta(hours=h, minutes=mi)
    # Pure minutes number
    try:
        mins = float(s)
        return pd.Timedelta(minutes=mins)
    except ValueError:
        pass
    return None


def _parse_datetime_col(series: pd.Series) -> pd.Series:
    """Robustly parse a datetime column, ignoring unparseable values."""
    def _try(v):
        if pd.isna(v):
            return pd.NaT
        if isinstance(v, (pd.Timestamp,)):
            return v
        try:
            return date_parser.parse(str(v), dayfirst=True)
        except Exception:
            return pd.NaT
    return series.map(_try)


def _timedelta_to_str(td) -> str:
    """Convert Timedelta to HH:MM:SS string."""
    if pd.isna(td) or not isinstance(td, pd.Timedelta):
        return "N/A"
    total_seconds = int(td.total_seconds())
    if total_seconds < 0:
        return "N/A"
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def _mean_timedelta(series: pd.Series) -> pd.Timedelta | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return valid.mean()


MONTH_ORDER = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_excel(file_bytes: bytes, filename: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Main entry point. Returns (clean_df, metadata).
    Raises ValueError with a user-friendly message on fatal errors.
    """
    # ── 1. Read file ──────────────────────────────────────────────────────────
    try:
        buf = io.BytesIO(file_bytes)
        if filename.lower().endswith(".csv"):
            raw = pd.read_csv(buf, dtype=str)
        else:
            # Try reading first sheet; if empty try second
            xl = pd.ExcelFile(buf)
            sheet = xl.sheet_names[0]
            raw = xl.parse(sheet, dtype=str)
            if raw.empty and len(xl.sheet_names) > 1:
                raw = xl.parse(xl.sheet_names[1], dtype=str)
    except Exception as e:
        raise ValueError(f"Cannot read file: {e}")

    # ── 2. Drop fully-empty rows / cols ──────────────────────────────────────
    raw.dropna(how="all", inplace=True)
    raw.dropna(axis=1, how="all", inplace=True)
    raw.reset_index(drop=True, inplace=True)

    if raw.empty:
        raise ValueError("The uploaded file has no data rows.")

    # ── 3. Map columns ────────────────────────────────────────────────────────
    col_map = _match_columns(raw)          # canonical → actual col name
    df = pd.DataFrame()

    def _get(canon: str) -> pd.Series | None:
        actual = col_map.get(canon)
        return raw[actual].copy() if actual else None

    # ── 4. INC Number ─────────────────────────────────────────────────────────
    inc = _get("inc number")
    df["INC Number"] = inc if inc is not None else pd.Series(
        [f"INC-{i+1}" for i in range(len(raw))]
    )

    # ── 5. Date ───────────────────────────────────────────────────────────────
    date_col = _get("date")
    if date_col is not None:
        df["Date"] = _parse_datetime_col(date_col)
    else:
        # Try occurrence time as fallback
        occ = _get("occurrence time")
        df["Date"] = _parse_datetime_col(occ) if occ is not None else pd.NaT

    # ── 6. Simple string columns ──────────────────────────────────────────────
    for canon, dest in [("analyst", "Analyst"), ("alert", "Alert"),
                        ("action taken", "Action Taken"), ("result", "Result")]:
        col = _get(canon)
        df[dest] = col.str.strip() if col is not None else "Unknown"

    # ── 7. Severity ───────────────────────────────────────────────────────────
    sev = _get("severity")
    if sev is not None:
        # Normalize casing
        df["Severity"] = sev.str.strip().str.capitalize()
        df["Severity"] = df["Severity"].replace({
            "Crit": "Critical", "Hi": "High", "Med": "Medium",
            "Lo": "Low", "Info": "Informational", "Inf": "Informational"
        })
    else:
        df["Severity"] = "Unknown"

    # ── 8. Occurrence / Detection times ──────────────────────────────────────
    occ_col = _get("occurrence time")
    det_col = _get("detection time")
    df["Occurrence Time"] = _parse_datetime_col(occ_col) if occ_col is not None else pd.NaT
    df["Detection Time"] = _parse_datetime_col(det_col) if det_col is not None else pd.NaT

    # ── 9. MTTD ───────────────────────────────────────────────────────────────
    mttd_raw = _get("mttd")
    if mttd_raw is not None:
        df["MTTD_td"] = mttd_raw.map(_parse_time_str)
    else:
        df["MTTD_td"] = pd.NaT

    # Auto-calculate where missing
    mask_mttd = df["MTTD_td"].isna() & df["Detection Time"].notna() & df["Occurrence Time"].notna()
    df.loc[mask_mttd, "MTTD_td"] = df.loc[mask_mttd, "Detection Time"] - df.loc[mask_mttd, "Occurrence Time"]
    # Clamp negatives
    df["MTTD_td"] = df["MTTD_td"].apply(lambda x: x if (pd.notna(x) and x.total_seconds() >= 0) else pd.NaT)

    # ── 10. MTTR ──────────────────────────────────────────────────────────────
    mttr_raw = _get("mttr")
    if mttr_raw is not None:
        df["MTTR_td"] = mttr_raw.map(_parse_time_str)
    else:
        df["MTTR_td"] = pd.NaT

    # Try resolved time fallback
    res_col = _get("resolved time")
    if res_col is not None:
        resolved = _parse_datetime_col(res_col)
        mask_mttr = df["MTTR_td"].isna() & resolved.notna() & df["Detection Time"].notna()
        df.loc[mask_mttr, "MTTR_td"] = resolved[mask_mttr] - df.loc[mask_mttr, "Detection Time"]
    df["MTTR_td"] = df["MTTR_td"].apply(lambda x: x if (pd.notna(x) and x.total_seconds() >= 0) else pd.NaT)

    # ── 11. Derived columns ───────────────────────────────────────────────────
    df["MTTD"] = df["MTTD_td"].apply(_timedelta_to_str)
    df["MTTR"] = df["MTTR_td"].apply(_timedelta_to_str)
    df["MTTD_seconds"] = df["MTTD_td"].apply(
        lambda x: x.total_seconds() if pd.notna(x) else np.nan)
    df["MTTR_seconds"] = df["MTTR_td"].apply(
        lambda x: x.total_seconds() if pd.notna(x) else np.nan)

    # Month / Year / Week
    df["Month"] = df["Date"].apply(
        lambda x: x.strftime("%b") if pd.notna(x) else "Unknown")
    df["Year"] = df["Date"].apply(
        lambda x: x.year if pd.notna(x) else 0).astype(str)
    df["Month_Num"] = df["Date"].apply(
        lambda x: x.month if pd.notna(x) else 0)

    # ── 12. Metadata ──────────────────────────────────────────────────────────
    valid_dates = df["Date"].dropna()
    metadata = {
        "row_count": len(df),
        "columns_detected": list(col_map.keys()),
        "date_range": {
            "from": valid_dates.min().strftime("%d %b %Y") if not valid_dates.empty else "N/A",
            "to":   valid_dates.max().strftime("%d %b %Y") if not valid_dates.empty else "N/A",
        },
        months = (
            df["Month"]
            .dropna()
            .astype(str)
            .loc[lambda x: x != "Unknown"]
            .unique()
            .tolist()
        )
        
        "months_available": sorted(
            months,
            key=lambda m: MONTH_ORDER.index(m) if m in MONTH_ORDER else 99
        ),
        ),
        "years_available": sorted(
            [y for y in df["Year"].unique().tolist() if y != "0"]
        ),
        "analysts": sorted(df[df["Analyst"] != "Unknown"]["Analyst"].unique().tolist()),
        "severities": sorted(df[df["Severity"] != "Unknown"]["Severity"].unique().tolist()),
        "has_result_column": df["Result"].nunique() > 1,
        "warnings": [],
    }

    if mttd_raw is None and occ_col is None:
        metadata["warnings"].append(
            "MTTD and Occurrence Time columns not found – MTTD cannot be calculated.")
    if mttr_raw is None and res_col is None:
        metadata["warnings"].append(
            "MTTR column not found – MTTR values will be unavailable.")

    return df, metadata


def format_seconds(seconds: float | None) -> str:
    """Convert seconds to HH:MM:SS string."""
    if seconds is None or np.isnan(seconds) or seconds < 0:
        return "N/A"
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def mean_seconds_to_str(series: pd.Series) -> str:
    valid = series.dropna()
    if valid.empty:
        return "N/A"
    return format_seconds(valid.mean())
