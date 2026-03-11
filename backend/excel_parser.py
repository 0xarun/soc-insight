"""
excel_parser.py
Robust Excel ingestion for SOC Insight.
Handles noisy SOC datasets, inconsistent Excel formats, and missing fields.
"""

import io
import re
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple


# ─────────────────────────── Column synonyms ────────────────────────────────

COLUMN_ALIASES = {
    "inc number": ["inc number","inc no","incident number","incident id","inc_number","incnumber","ticket","ticket id","id"],
    "date": ["date","incident date","inc date","log date"],
    "analyst": ["analyst","analyst name","assigned to","owner","handler","responder"],
    "alert": ["alert","alert name","alert type","alert description","threat","event","alerttitle"],
    "severity": [
        "severity","priority","sev","level","criticality",
        "alertlevel","alert level","risk level"
    ],
    "action taken": ["action taken","action","response","resolution","remediation"],
    "occurrence time": ["occurrence time","occurance time","occurred time","eventoccurence","event occurrence","event time","start time","occurred at"],
    "detection time": ["detection time","detected time","detected at","alert time","eventdetection"],
    "resolved time": ["resolved time","resolve time","closure time","close time","eventresolve"],
    "mttd": ["mttd","mean time to detect","time to detect","detection duration"],
    "mttr": ["mttr","mean time to respond","time to respond","response duration","resolution time"],
    "result": ["result","incident type","classification","tp/fp","true positive","verdict"],
}

MONTH_ORDER = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]


# ─────────────────────────── Helpers ────────────────────────────────

def _normalise_header(col: str) -> str:
    return re.sub(r"[\s_\-]+"," ",str(col)).strip().lower()


def _match_columns(df: pd.DataFrame) -> Dict[str,str]:
    """Map canonical column names to real dataframe columns (robust matching)."""

    norm_cols = {_normalise_header(c):c for c in df.columns}

    mapping = {}

    for canonical, aliases in COLUMN_ALIASES.items():

        for col_norm, original in norm_cols.items():

            for alias in aliases:

                alias_norm = _normalise_header(alias)

                if (
                    alias_norm == col_norm
                    or alias_norm in col_norm
                    or col_norm in alias_norm
                ):
                    mapping[canonical] = original
                    break

            if canonical in mapping:
                break

    return mapping


# ─────────────────────────── Time parsing ────────────────────────────────

def _parse_time_str(val):

    if pd.isna(val):
        return None

    if isinstance(val, pd.Timedelta):
        return val

    # Excel duration float (fraction of day)
    if isinstance(val, (int,float)):

        try:
            seconds = float(val) * 86400
            return pd.Timedelta(seconds=seconds)
        except:
            return None

    s = str(val).strip()

    # HH:MM:SS
    m = re.match(r"^(\d+):(\d{1,2}):(\d{1,2})$", s)
    if m:
        return pd.Timedelta(
            hours=int(m.group(1)),
            minutes=int(m.group(2)),
            seconds=int(m.group(3))
        )

    # HH:MM
    m = re.match(r"^(\d+):(\d{1,2})$", s)
    if m:
        return pd.Timedelta(
            hours=int(m.group(1)),
            minutes=int(m.group(2))
        )

    # numeric minutes
    try:
        s = s.replace(",","")
        return pd.Timedelta(minutes=float(s))
    except:
        return None


def _parse_datetime_col(series: pd.Series):

    return pd.to_datetime(
        series,
        errors="coerce",
        dayfirst=True,
        infer_datetime_format=True
    )


def _timedelta_to_str(td):

    if pd.isna(td) or not isinstance(td,pd.Timedelta):
        return "N/A"

    total = int(td.total_seconds())

    if total < 0:
        return "N/A"

    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60

    return f"{h:02d}:{m:02d}:{s:02d}"


def format_seconds(seconds):

    if seconds is None or pd.isna(seconds) or seconds < 0:
        return "N/A"

    seconds = int(seconds)

    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60

    return f"{h:02d}:{m:02d}:{s:02d}"


# ─────────────────────────── Severity normalization ─────────────────────────

def _normalize_severity(v):

    if pd.isna(v):
        return "Unknown"

    s = str(v).strip().lower()

    mapping = {

        "critical":"Critical",
        "crit":"Critical",
        "c":"Critical",

        "high":"High",
        "h":"High",

        "medium":"Medium",
        "med":"Medium",
        "m":"Medium",

        "low":"Low",
        "l":"Low",

        "informational":"Informational",
        "info":"Informational",
        "inf":"Informational"
    }

    return mapping.get(s, s.capitalize())


# ─────────────────────────── Main Parser ────────────────────────────────

def parse_excel(file_bytes: bytes, filename: str) -> Tuple[pd.DataFrame, Dict[str,Any]]:

    # ───────── Read file ─────────

    try:

        buf = io.BytesIO(file_bytes)

        if filename.lower().endswith(".csv"):
            raw = pd.read_csv(buf, dtype=str)

        else:
            xl = pd.ExcelFile(buf)

            raw = None

            for sheet in xl.sheet_names:

                tmp = xl.parse(sheet, dtype=str)

                if not tmp.dropna(how="all").empty:
                    raw = tmp
                    break

            if raw is None:
                raise ValueError("No data found in Excel sheets")

    except Exception as e:
        raise ValueError(f"Cannot read file: {e}")


    # ───────── Clean dataframe ─────────

    raw.dropna(how="all", inplace=True)
    raw.dropna(axis=1, how="all", inplace=True)
    raw.reset_index(drop=True, inplace=True)

    if raw.empty:
        raise ValueError("Uploaded file contains no usable rows.")


    # ───────── Column mapping ─────────

    col_map = _match_columns(raw)

    df = pd.DataFrame()

    def _get(name):

        col = col_map.get(name)

        return raw[col].copy() if col else None


    # ───────── INC number ─────────

    inc = _get("inc number")

    df["INC Number"] = inc if inc is not None else [
        f"INC-{i+1}" for i in range(len(raw))
    ]


    # ───────── Date ─────────

    date_col = _get("date")

    if date_col is not None:
        df["Date"] = _parse_datetime_col(date_col)
    else:
        occ = _get("occurrence time")
        df["Date"] = _parse_datetime_col(occ) if occ is not None else pd.NaT


    # ───────── Basic fields ─────────

    for canon, dest in [
        ("analyst","Analyst"),
        ("alert","Alert"),
        ("action taken","Action Taken"),
        ("result","Result")
    ]:

        col = _get(canon)

        if col is not None:
            df[dest] = col.fillna("Unknown").astype(str).str.strip()
        else:
            df[dest] = "Unknown"


    # ───────── Severity ─────────

    sev = _get("severity")

    if sev is not None:
        df["Severity"] = sev.map(_normalize_severity)
    else:
        df["Severity"] = "Unknown"


    # ───────── Times ─────────

    occ = _get("occurrence time")
    det = _get("detection time")

    df["Occurrence Time"] = _parse_datetime_col(occ) if occ is not None else pd.NaT
    df["Detection Time"] = _parse_datetime_col(det) if det is not None else pd.NaT


    # ───────── MTTD ─────────

    mttd_raw = _get("mttd")

    if mttd_raw is not None:
        df["MTTD_td"] = mttd_raw.map(_parse_time_str)
    else:
        df["MTTD_td"] = pd.NaT


    mask = df["MTTD_td"].isna() & df["Occurrence Time"].notna() & df["Detection Time"].notna()

    df.loc[mask,"MTTD_td"] = df.loc[mask,"Detection Time"] - df.loc[mask,"Occurrence Time"]

    df["MTTD_td"] = df["MTTD_td"].apply(
        lambda x: x if (pd.notna(x) and x.total_seconds() >= 0) else pd.NaT
    )


    # ───────── MTTR ─────────

    mttr_raw = _get("mttr")

    if mttr_raw is not None:
        df["MTTR_td"] = mttr_raw.map(_parse_time_str)
    else:
        df["MTTR_td"] = pd.NaT


    res = _get("resolved time")

    if res is not None:

        resolved = _parse_datetime_col(res)

        mask = df["MTTR_td"].isna() & resolved.notna() & df["Detection Time"].notna()

        df.loc[mask,"MTTR_td"] = resolved[mask] - df.loc[mask,"Detection Time"]


    df["MTTR_td"] = df["MTTR_td"].apply(
        lambda x: x if (pd.notna(x) and x.total_seconds() >= 0) else pd.NaT
    )


    # ───────── Derived metrics ─────────

    df["MTTD"] = df["MTTD_td"].apply(_timedelta_to_str)
    df["MTTR"] = df["MTTR_td"].apply(_timedelta_to_str)

    df["MTTD_seconds"] = df["MTTD_td"].apply(lambda x: x.total_seconds() if pd.notna(x) else np.nan)
    df["MTTR_seconds"] = df["MTTR_td"].apply(lambda x: x.total_seconds() if pd.notna(x) else np.nan)

    df["MTTD_seconds"] = pd.to_numeric(df["MTTD_seconds"], errors="coerce")
    df["MTTR_seconds"] = pd.to_numeric(df["MTTR_seconds"], errors="coerce")


    # ───────── Date breakdown ─────────

    df["Month"] = df["Date"].dt.strftime("%b").fillna("Unknown")
    df["Year"] = df["Date"].dt.year.fillna(0).astype(int).astype(str)


    # ───────── Metadata ─────────

    valid_dates = df["Date"].dropna()

    months = df["Month"].loc[df["Month"] != "Unknown"].unique().tolist()
    years = df["Year"].loc[df["Year"] != "0"].unique().tolist()

    metadata = {

        "row_count": len(df),

        "columns_detected": list(col_map.keys()),

        "date_range": {
            "from": valid_dates.min().strftime("%d %b %Y") if not valid_dates.empty else "N/A",
            "to": valid_dates.max().strftime("%d %b %Y") if not valid_dates.empty else "N/A"
        },

        "months_available": sorted(
            months,
            key=lambda m: MONTH_ORDER.index(m) if m in MONTH_ORDER else 99
        ),

        "years_available": sorted(years),

        "analysts": sorted(df["Analyst"].dropna().astype(str).unique().tolist()),

        "severities": sorted(df["Severity"].dropna().astype(str).unique().tolist()),

        "has_result_column": df["Result"].nunique() > 1,

        "warnings":[]
    }


    if mttd_raw is None and occ is None:
        metadata["warnings"].append(
            "MTTD could not be calculated (missing occurrence or MTTD column)."
        )

    if mttr_raw is None and res is None:
        metadata["warnings"].append(
            "MTTR values unavailable (missing resolved or MTTR column)."
        )


    return df, metadata
