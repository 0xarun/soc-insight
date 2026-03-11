# SOC Insight 🛡

**SOC Insight** is a modern SaaS-style platform that turns raw SOC incident Excel sheets into rich operational dashboards, metrics, and natural language insights.

---

## 🚀 Quick Start

### 1. Install Python dependencies

```powershell
cd "d:\Projects\New folder\soc-insight\backend"
pip install -r requirements.txt
```

### 2. Generate sample data (optional)

```powershell
cd "d:\Projects\New folder\soc-insight\sample_data"
python generate_sample.py
```

### 3. Start the server

```powershell
cd "d:\Projects\New folder\soc-insight\backend"
python main.py
```

Then open: **http://localhost:8000**

---

## 🤖 AI Chat (Ollama)

Make sure Ollama is running before using the AI chat feature:

```powershell
ollama serve
```

The app auto-detects Ollama. If your model is named differently (e.g. `llama3.2:3b`), update `DEFAULT_MODEL` in `backend/llm_query.py`.

---

## 📊 Features

| Feature | Description |
|---|---|
| Excel Ingestion | Drag & drop `.xlsx`, `.xls`, `.csv` — auto detects columns |
| KPI Dashboard | Total alerts, critical count, Avg MTTD, Avg MTTR, TP ratio |
| Severity Metrics | Per-severity breakdown with MTTD/MTTR |
| Monthly View | Month × severity cross-table with trends |
| Analyst Performance | Per-analyst alerts, response times, top alert types |
| True Positive Analysis | Filters on Result column TP/FP |
| SLA Compliance | Tracks MTTR vs SLA threshold per severity |
| Trend Charts | Monthly alerts, MTTD/MTTR trend lines |
| Raw Data Table | Searchable, paginated incident table with filters |
| AI Chat | Ask natural language questions via Ollama LLM |
| Report Generator | Download full HTML SOC operational report |
| Export Excel | Download filtered data as `.xlsx` |

---

## 📁 Project Structure

```
soc-insight/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── excel_parser.py      # Robust Excel ingestion
│   ├── metrics_engine.py    # Analytics engine
│   ├── llm_query.py         # Ollama NL→pandas queries
│   ├── report_generator.py  # HTML report builder
│   └── requirements.txt
├── frontend/
│   ├── index.html           # Single-page app
│   ├── css/style.css        # Dark SaaS design
│   └── js/
│       ├── app.js           # Main controller
│       ├── charts.js        # Chart.js renderers
│       └── chat.js          # Chat interface
└── sample_data/
    ├── generate_sample.py   # Sample data generator
    └── sample_incidents.xlsx
```

---

## 📋 Expected Excel Columns

The parser auto-detects these columns (case-insensitive, with synonyms):

| Column | Example | Required |
|---|---|---|
| INC Number | INC-1234 | Optional (auto-generated) |
| Date | 03/11/2026 | Recommended |
| Analyst | Arun Kumar | Recommended |
| Alert | Malware Detected | Recommended |
| Severity | Critical / High / Medium / Low | Required |
| Action Taken | Isolated host | Optional |
| Occurrence Time | 03/11/2026 12:00:00 | For MTTD calc |
| Detection Time | 03/11/2026 12:30:00 | For MTTD calc |
| MTTD | 00:30:00 | Or auto-calculated |
| MTTR | 02:10:00 | Required for MTTR metrics |
| Result | True Positive / False Positive | For TP analysis |

---

## ⚙️ Configuration

- **SLA Thresholds** (default): Critical=4h, High=8h, Medium=24h, Low=72h
  - Edit `SLA_DEFAULTS` in `backend/metrics_engine.py`
- **Ollama model**: Change `DEFAULT_MODEL` in `backend/llm_query.py`
- **Port**: Change `--port 8000` in startup command

---

## 🛡 Security Note

This tool is for **internal use only**. Data is held in server memory and cleared on restart. Do not expose to the public internet without authentication.
