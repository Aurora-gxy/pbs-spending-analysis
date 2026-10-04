"""PBS spending overview dashboard.

Run locally:  streamlit run app/Home.py
Data: app/data/monthly_drug.parquet, exported from the PostgreSQL materialised view
      mv_monthly_drug by scripts/export_results.py.
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BLUE, ORANGE, GRID = "#2a78d6", "#eb6834", "#e6e5e1"
DATA = Path(__file__).parent / "data" / "monthly_drug.parquet"

st.set_page_config(page_title="PBS Spending Overview", layout="wide")


@st.cache_data
def load():
    df = pd.read_parquet(DATA)
    df["month_start"] = pd.to_datetime(df["month_start"])
    return df


df = load()

# Only financial years with all 12 months can be compared with each other.
months_per_fy = df.groupby("fin_year")["month_start"].nunique()
full_years = sorted(months_per_fy[months_per_fy == 12].index)

st.title("PBS prescription spending")
st.caption(
    "Australian Pharmaceutical Benefits Scheme, date-of-supply data, "
    f"{df['month_start'].min():%b %Y} to {df['month_start'].max():%b %Y}. "
    "Financial years run July to June and are named by their ending year."
)

fy = st.selectbox("Financial year", full_years, index=len(full_years) - 1,
                  format_func=lambda y: f"FY{y}")
cur = df[df["fin_year"] == fy]
prev = df[df["fin_year"] == fy - 1] if (fy - 1) in full_years else None


def pct_change(col):
    if prev is None:
        return None
    return f"{100 * (cur[col].sum() / prev[col].sum() - 1):+.1f}% vs FY{fy - 1}"


def patient_share(d):
    return 100 * d["patient_cost"].sum() / d["total_cost"].sum()


c1, c2, c3, c4 = st.columns(4)
c1.metric("Total cost", f"A${cur['total_cost'].sum() / 1e9:.2f}B", pct_change("total_cost"))
c2.metric("Government cost", f"A${cur['govt_cost'].sum() / 1e9:.2f}B", pct_change("govt_cost"))
c3.metric("Prescriptions", f"{cur['scripts'].sum() / 1e6:.1f}M", pct_change("scripts"))
c4.metric(
    "Patient share of cost",
    f"{patient_share(cur):.1f}%",
    None if prev is None else f"{patient_share(cur) - patient_share(prev):+.1f} pts vs FY{fy - 1}",
    delta_color="off",
)

left, right = st.columns(2)

with left:
    st.subheader("Monthly total cost")
    monthly = df.groupby("month_start", as_index=False)["total_cost"].sum()
    monthly["rolling_12m"] = monthly["total_cost"].rolling(12).mean()
    fig = go.Figure()
    fig.add_scatter(x=monthly["month_start"], y=monthly["total_cost"] / 1e9, name="Monthly",
                    mode="lines", line=dict(color=BLUE, width=2),
                    hovertemplate="%{x|%b %Y}: A$%{y:.2f}B<extra>Monthly</extra>")
    fig.add_scatter(x=monthly["month_start"], y=monthly["rolling_12m"] / 1e9, name="12-month average",
                    mode="lines", line=dict(color=ORANGE, width=2),
                    hovertemplate="%{x|%b %Y}: A$%{y:.2f}B<extra>12-month average</extra>")
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10),
                      yaxis_title="A$ billion", legend=dict(orientation="h", y=1.08),
                      hovermode="x unified")
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor=GRID)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Spending peaks every December and drops every January, when the safety net resets.")

with right:
    st.subheader(f"Total cost by drug group, FY{fy}")
    cat = (cur.groupby("atc1_name", as_index=False)[["total_cost", "scripts"]].sum()
           .sort_values("total_cost"))
    cat["share"] = 100 * cat["total_cost"] / cat["total_cost"].sum()
    fig = go.Figure(go.Bar(
        x=cat["total_cost"] / 1e9, y=cat["atc1_name"], orientation="h", marker_color=BLUE,
        customdata=cat[["share", "scripts"]],
        hovertemplate="%{y}<br>A$%{x:.2f}B (%{customdata[0]:.1f}% of total)"
                      "<br>%{customdata[1]:,.0f} scripts<extra></extra>",
    ))
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), xaxis_title="A$ billion")
    fig.update_xaxes(gridcolor=GRID)
    fig.update_yaxes(showgrid=False)
    st.plotly_chart(fig, use_container_width=True)
    top = cat.iloc[-1]
    st.caption(f"{top['atc1_name']} is the largest group at {top['share']:.0f}% of total cost.")

with st.expander("Show the data behind the charts"):
    st.dataframe(
        cat.sort_values("total_cost", ascending=False)
           .assign(total_cost_m=lambda d: (d["total_cost"] / 1e6).round(1),
                   share_pct=lambda d: d["share"].round(1))
           [["atc1_name", "total_cost_m", "share_pct", "scripts"]],
        hide_index=True, use_container_width=True,
    )
