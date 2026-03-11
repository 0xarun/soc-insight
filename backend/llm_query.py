"""
llm_query.py
Natural language → SOC metrics query engine using Ollama.
"""

import json
import re
import requests
import pandas as pd
from typing import Any

OLLAMA_URL = "http://172.20.20.35/api/chat"  # ← Fixed: your Ollama host
DEFAULT_MODEL = "llama3.2:3b"                           # ← Fixed: your model name

SYSTEM_PROMPT = """You are a SOC (Security Operations Center) data analyst assistant.

You have access to a pandas DataFrame called `df` with these columns:
- INC Number (str): Incident ticket ID
- Date (datetime): Incident date
- Analyst (str): Analyst who handled it
- Alert (str): Alert/threat name
- Severity (str): Critical / High / Medium / Low / Informational
- Action Taken (str): Response action
- MTTD (str HH:MM:SS): Mean Time To Detect formatted
- MTTR (str HH:MM:SS): Mean Time To Respond formatted
- MTTD_seconds (float): MTTD in seconds (use for calculations)
- MTTR_seconds (float): MTTR in seconds (use for calculations)
- Result (str): True Positive / False Positive
- Month (str): Jan/Feb/Mar...
- Year (str): 2025/2026...

Your job: Convert the user's natural language question into one pandas expression.
Output ONLY the pandas expression (no explanation, no markdown, no code block).

Examples:
Q: show critical incidents in february
A: df[(df["Severity"]=="Critical") & (df["Month"]=="Feb")]

Q: which analyst has the highest average MTTR
A: df.groupby("Analyst")["MTTR_seconds"].mean().idxmax()

Q: total alerts by severity
A: df["Severity"].value_counts()

Q: average mttd for high severity incidents
A: df[df["Severity"]=="High"]["MTTD_seconds"].mean()

Q: incidents handled by Arun in March
A: df[(df["Analyst"].str.lower()=="arun") & (df["Month"]=="Mar")]

Q: top 5 most frequent alerts
A: df["Alert"].value_counts().head(5)

Q: analyst performance this month
A: df.groupby("Analyst")[["MTTD_seconds","MTTR_seconds"]].mean()

Q: true positive rate
A: df[df["Result"].str.lower().str.contains("true positive", na=False)].shape[0] / len(df) * 100

Only output a valid pandas expression. Nothing else.
"""


def _call_ollama(prompt: str, model: str = DEFAULT_MODEL) -> str:
    """Call local Ollama API and return the generated text."""
    try:
        resp = requests.post(
            OLLAMA_URL,                                         # ← Uses module-level constant
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "").strip()
    except requests.exceptions.ConnectionError:
        raise RuntimeError(
            f"Cannot connect to Ollama at {OLLAMA_URL}. "
            "Check that Ollama is running and the host/port is reachable."
        )
    except requests.exceptions.Timeout:
        raise RuntimeError("Ollama took too long to respond. Try a smaller model.")
    except Exception as e:
        raise RuntimeError(f"Ollama error: {e}")


def _safe_eval(expr: str, df: pd.DataFrame) -> Any:
    """Safely evaluate a pandas expression."""
    # Strip markdown code blocks if LLM wraps it
    expr = re.sub(r"```(?:python)?", "", expr).replace("```", "").strip()
    # Only allow safe pandas ops
    local_ns = {"df": df, "pd": pd}
    try:
        result = eval(expr, {"__builtins__": {}}, local_ns)
        return result
    except Exception as e:
        raise ValueError(f"Could not evaluate query: {e}\nExpression: {expr}")


def _result_to_json(result: Any) -> dict:
    """Convert pandas result to JSON-friendly format."""
    if isinstance(result, str):
        return {"type": "scalar", "value": result}

    if isinstance(result, (int, float)):
        return {"type": "scalar", "value": round(result, 4)}

    if isinstance(result, pd.Series):
        if result.dtype == object or len(result) > 1:
            return {
                "type": "series",
                "columns": ["Label", "Value"],
                "rows": [[str(k), str(v)] for k, v in result.items()],
            }
        return {"type": "scalar", "value": round(float(result.iloc[0]), 4)}

    if isinstance(result, pd.DataFrame):
        cols_keep = ["INC Number", "Date", "Analyst", "Alert", "Severity",
                     "Action Taken", "MTTD", "MTTR", "Result", "Month", "Year",
                     "MTTD_seconds", "MTTR_seconds"]
        show_cols = [c for c in cols_keep if c in result.columns]
        if not show_cols:
            show_cols = list(result.columns[:10])
        display = result[show_cols].head(100)
        rows = []
        for _, row in display.iterrows():
            rec = {}
            for c in show_cols:
                v = row[c]
                if pd.isna(v):
                    rec[c] = ""
                elif isinstance(v, pd.Timestamp):
                    rec[c] = v.strftime("%d %b %Y %H:%M")
                elif isinstance(v, float):
                    rec[c] = round(v, 2)
                else:
                    rec[c] = str(v)
            rows.append(rec)
        return {
            "type": "dataframe",
            "columns": show_cols,
            "rows": rows,
            "total": len(result),
        }

    return {"type": "scalar", "value": str(result)}


def query(user_question: str, df: pd.DataFrame, model: str = DEFAULT_MODEL) -> dict:
    """
    Main entry point.
    Returns: { success, question, pandas_expr, result, result_type, error }
    """
    full_prompt = f"{SYSTEM_PROMPT}\n\nQ: {user_question}\nA:"

    try:
        expr = _call_ollama(full_prompt, model)
    except RuntimeError as e:
        return {
            "success": False,
            "question": user_question,
            "pandas_expr": "",
            "result": None,
            "error": str(e),
        }

    try:
        raw_result = _safe_eval(expr, df)
        json_result = _result_to_json(raw_result)
        return {
            "success": True,
            "question": user_question,
            "pandas_expr": expr,
            "result": json_result,
            "error": None,
        }
    except ValueError as e:
        return {
            "success": False,
            "question": user_question,
            "pandas_expr": expr,
            "result": None,
            "error": str(e),
        }


def get_ollama_status(model: str = DEFAULT_MODEL) -> dict:
    """Check if Ollama is reachable and model is available."""
    try:
        # ← Fixed: derive base URL from OLLAMA_URL instead of hardcoding localhost
        base_url = OLLAMA_URL.rsplit("/api/", 1)[0]
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        return {
            "connected": True,
            "model_available": any(model in m for m in models),
            "available_models": models,
        }
    except Exception as e:
        return {"connected": False, "model_available": False, "available_models": [], "error": str(e)}
