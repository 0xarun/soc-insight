"""
main.py – SOC Insight FastAPI Application
"""

import io
import os
import uuid
import json
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                                StreamingResponse)
from fastapi.staticfiles import StaticFiles

import excel_parser as ep
import llm_query as lq
import metrics_engine as me
import report_generator as rg

# ──────────────────────────────────────────────────────────────────────────────
app = FastAPI(title="SOC Insight", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store  { session_token: {"df": DataFrame, "metadata": dict} }
SESSIONS: dict = {}

# Resolve paths relative to this file
BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR.parent / "frontend"

# ── Static files ──────────────────────────────────────────────────────────────
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    index = FRONTEND_DIR / "index.html"
    return HTMLResponse(content=index.read_text(encoding="utf-8"))


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    ollama = lq.get_ollama_status()
    return {
        "status": "ok",
        "sessions_active": len(SESSIONS),
        "ollama": "connected" if ollama["connected"] else "unavailable",
        "ollama_models": ollama.get("available_models", []),
    }


# ── Upload ────────────────────────────────────────────────────────────────────
@app.post("/upload")
async def upload_excel(file: UploadFile = File(...)):
    allowed = {".xlsx", ".xls", ".csv"}
    ext = Path(file.filename).suffix.lower()
    if ext not in allowed:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Use .xlsx, .xls, or .csv")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(413, "File too large (max 50 MB)")

    try:
        df, metadata = ep.parse_excel(content, file.filename)
    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        raise HTTPException(500, f"Unexpected error during parsing: {e}")

    token = str(uuid.uuid4())
    SESSIONS[token] = {"df": df, "metadata": metadata}

    return {"session_token": token, **metadata}


# ── Metrics endpoint helpers ──────────────────────────────────────────────────
def _get_session(token: str) -> dict:
    if not token or token not in SESSIONS:
        raise HTTPException(401, "Invalid or expired session token. Please upload your Excel file again.")
    return SESSIONS[token]


def _parse_filters(month, year, severity, analyst) -> dict:
    f = {}
    if month and month != "All":
        f["month"] = month
    if year and year != "All":
        f["year"] = year
    if severity and severity != "All":
        f["severity"] = severity
    if analyst and analyst != "All":
        f["analyst"] = analyst
    return f


# ── All metrics in one call ───────────────────────────────────────────────────
@app.get("/metrics")
async def get_metrics(
    token: str = Query(...),
    month: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    analyst: Optional[str] = Query(None),
):
    session = _get_session(token)
    df = session["df"]
    filters = _parse_filters(month, year, severity, analyst)

    return {
        "kpi":                    me.kpi_summary(df, **filters),
        "severity_metrics":       me.severity_metrics(df, **filters),
        "monthly_metrics":        me.monthly_metrics(df, **filters),
        "monthly_severity":       me.monthly_severity_breakdown(df, **filters),
        "analyst_metrics":        me.analyst_metrics(df, **filters),
        "true_positive_metrics":  me.true_positive_metrics(df, **filters),
        "sla_metrics":            me.sla_metrics(df, **filters),
        "top_alerts":             me.top_alerts(df, n=10, **filters),
        "trend":                  me.trend_data(df, **filters),
        "metadata":               session["metadata"],
    }


# ── Raw data paged ────────────────────────────────────────────────────────────
@app.get("/data")
async def get_raw_data(
    token: str = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
    search: str = Query(""),
    month: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    analyst: Optional[str] = Query(None),
):
    session = _get_session(token)
    df = session["df"]
    filters = _parse_filters(month, year, severity, analyst)
    return me.raw_data_page(df, page=page, page_size=page_size, search=search, **filters)


# ── AI Chat ───────────────────────────────────────────────────────────────────
@app.post("/chat")
async def chat(body: dict):
    token = body.get("token", "")
    question = body.get("question", "").strip()
    model = body.get("model", lq.DEFAULT_MODEL)

    if not question:
        raise HTTPException(400, "Question cannot be empty")

    session = _get_session(token)
    df = session["df"]
    result = lq.query(question, df, model=model)
    return result


# ── Report Generator ──────────────────────────────────────────────────────────
@app.get("/report", response_class=HTMLResponse)
async def get_report(
    token: str = Query(...),
    month: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    analyst: Optional[str] = Query(None),
):
    session = _get_session(token)
    df = session["df"]
    filters = _parse_filters(month, year, severity, analyst)
    html = rg.generate_html_report(df, filters)
    return HTMLResponse(content=html)


# ── Export Excel ──────────────────────────────────────────────────────────────
@app.get("/export/excel")
async def export_excel(
    token: str = Query(...),
    month: Optional[str] = Query(None),
    year: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    analyst: Optional[str] = Query(None),
):
    session = _get_session(token)
    df = session["df"]
    filters = _parse_filters(month, year, severity, analyst)
    from metrics_engine import _apply_filters
    d = _apply_filters(df, **filters)

    export_cols = ["INC Number", "Date", "Analyst", "Alert", "Severity",
                   "Action Taken", "MTTD", "MTTR", "Result", "Month", "Year"]
    export_cols = [c for c in export_cols if c in d.columns]

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
        d[export_cols].to_excel(writer, index=False, sheet_name="Incidents")
        me.severity_metrics(d).__class__  # just to keep import
        sev_df = pd.DataFrame(me.severity_metrics(d))
        if not sev_df.empty:
            sev_df.to_excel(writer, index=False, sheet_name="Severity Metrics")
        ana_df = pd.DataFrame(me.analyst_metrics(d))
        if not ana_df.empty:
            ana_df.to_excel(writer, index=False, sheet_name="Analyst Metrics")

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="soc_export.xlsx"'},
    )


# ── Session metadata ──────────────────────────────────────────────────────────
@app.get("/session/{token}")
async def session_meta(token: str):
    session = _get_session(token)
    return session["metadata"]


# ── Delete session ────────────────────────────────────────────────────────────
@app.delete("/session/{token}")
async def delete_session(token: str):
    SESSIONS.pop(token, None)
    return {"status": "deleted"}


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
