"""Ask the PBS data in plain English or Chinese.

The question goes to an LLM, which writes SQL through a run_sql tool; the query runs on the
same data as the dashboard. The page shows the answer, the result table, a chart when the
result is a ranking or a time series, and the SQL so users can check how the number was made.
"""
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# On Streamlit Cloud, API keys are set in the app's Secrets.
# Locally there is no secrets file, so fall back to environment variables set with export.
try:
    _secrets = dict(st.secrets)
except Exception:
    _secrets = {}
for k in ("LLM_PROVIDER", "LLM_MODEL", "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL"):
    if k in _secrets and k not in os.environ:
        os.environ[k] = str(_secrets[k])

from assistant.agent import ask  # noqa: E402

BLUE = "#2a78d6"
LOG = Path(__file__).resolve().parents[2] / "logs" / "questions.csv"


def log_question(question, res, feedback=""):
    """Save every real question so failures can be reviewed and added to the eval set."""
    try:
        LOG.parent.mkdir(exist_ok=True)
        new = not LOG.exists()
        with LOG.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new:
                w.writerow(["time", "question", "sql", "error", "answer", "feedback"])
            w.writerow([datetime.now().isoformat(timespec="seconds"), question, res.get("sql"),
                        res.get("error"), res.get("answer"), feedback])
    except OSError:
        pass  # read-only hosting: skip logging rather than break the page
MONEY_COLS = ("total_cost", "govt_cost", "patient_cost", "cost")

st.set_page_config(page_title="Ask the PBS data", layout="wide")
st.title("Ask the PBS data")
st.caption("Ask a question in English or Chinese. The assistant writes SQL, runs it on the PBS data "
           "(FY2023–FY2026) and explains the result. Check the SQL before using a number in a decision.")

EXAMPLES = [
    "What share of total cost did patients pay in FY2026?",
    "What were the top 5 drugs by total cost in FY2026?",
    "FY2026 政府支出最高的 3 种药是什么？",
    "How did total cost change each financial year?",
]


def pretty_sql(sql):
    try:
        import sqlparse
        return sqlparse.format(sql, reindent=True, keyword_case="upper")
    except ImportError:
        return sql


def fmt_money(v):
    v = float(v)
    if abs(v) >= 1e9:
        return f"A${v / 1e9:,.2f}B"
    if abs(v) >= 1e6:
        return f"A${v / 1e6:,.1f}M"
    return f"A${v:,.0f}"


def to_frame(res):
    df = pd.DataFrame(res["rows"], columns=res["columns"])
    for c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="ignore") if df[c].dtype == object else df[c]
    return df


def nice_name(c):
    return c.replace("_", " ").strip().capitalize()


def is_money(col, series):
    name = col.lower()
    if any(m in name for m in MONEY_COLS) or "spend" in name or "aud" in name:
        return True
    return pd.api.types.is_float_dtype(series) and series.abs().max() >= 1e5


def show_table(df):
    shown = df.copy()
    for c in shown.columns:
        col = shown[c]
        if not pd.api.types.is_numeric_dtype(col):
            continue
        name = c.lower()
        if any(k in name for k in ("share", "pct", "percent", "ratio", "growth")):
            shown[c] = (col * 100 if col.abs().max() <= 1 else col).map(lambda x: f"{x:.1f}%")
        elif name in ("fin_year", "cal_year", "cal_month"):
            shown[c] = col.astype(int).astype(str)
        elif is_money(c, col):
            shown[c] = col.map(fmt_money)
        elif pd.api.types.is_float_dtype(col):
            shown[c] = col.map(lambda x: f"{x:,.2f}")
        else:
            shown[c] = col.map(lambda x: f"{x:,}")
    shown.columns = [nice_name(c) for c in shown.columns]
    st.dataframe(shown, hide_index=True, use_container_width=True)


def show_chart(df):
    """Bar chart for a ranking (text + number, 2–20 rows); line chart when the first column is time."""
    if df.shape[1] < 2 or not (2 <= len(df) <= 20):
        return
    label = df.columns[0]
    nums = [c for c in df.columns[1:] if pd.api.types.is_numeric_dtype(df[c])]
    if not nums:
        return
    value = nums[0]  # chart the first measure; the table shows the rest
    df = df[[label, value]]
    if label.lower() in ("fin_year", "cal_year", "cal_month", "month_start"):
        fig = px.line(df, x=label, y=value, markers=True)
        fig.update_traces(line_color=BLUE, line_width=2)
    else:
        d = df.sort_values(value)
        fig = px.bar(d, x=value, y=label, orientation="h")
        fig.update_traces(marker_color=BLUE)
    fig.update_layout(height=60 + 32 * len(df), margin=dict(l=0, r=0, t=10, b=0),
                      xaxis_title=None, yaxis_title=None, plot_bgcolor="white")
    fig.update_xaxes(gridcolor="#e6e5e1")
    st.plotly_chart(fig, use_container_width=True)


cols = st.columns(len(EXAMPLES))
for c, ex in zip(cols, EXAMPLES):
    if c.button(ex, use_container_width=True):
        st.session_state["q"] = ex

q = st.text_input("Your question", key="q", placeholder="e.g. Which drug group grew fastest from FY2025 to FY2026?")
if q:
    if st.session_state.get("last_q") != q:
        with st.spinner("Querying the data..."):
            try:
                res = ask(q, "v2")
            except Exception as e:
                st.error(f"The assistant is not available: {e}")
                st.stop()
        st.session_state.update(last_q=q, last_res=res, rated=False)
        log_question(q, res)
    res = st.session_state["last_res"]

    st.markdown((res["answer"] or "_No answer._").replace("$", "\\$"))

    if res["rows"]:
        df = to_frame(res)
        left, right = st.columns([1, 1])
        with left:
            show_table(df)
        with right:
            show_chart(df)
    if res["sql"]:
        with st.expander("How this was calculated (SQL)"):
            st.code(pretty_sql(res["sql"]), language="sql")
            if res["error"]:
                st.warning(res["error"])

    if not st.session_state.get("rated"):
        st.caption("Was this answer correct?")
        c1, c2, _ = st.columns([1, 1, 8])
        if c1.button("👍 Yes"):
            log_question(q, res, "correct")
            st.session_state["rated"] = True
            st.rerun()
        if c2.button("👎 No"):
            log_question(q, res, "wrong")
            st.session_state["rated"] = True
            st.rerun()
    else:
        st.caption("Thanks — feedback saved for review.")
