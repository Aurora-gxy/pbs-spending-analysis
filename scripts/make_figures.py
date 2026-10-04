"""Draw the README figures from the exported results.

Reads results/*.csv and app/data/monthly_drug.parquet (run scripts/export_results.py first).
Writes docs/fig_a1..a5 as PNG.  Usage:  python scripts/make_figures.py
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap

RES, DOCS = Path("results"), Path("docs")
DOCS.mkdir(exist_ok=True)

BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e6e5e1", "#fcfcfb"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
})


def finish(fig, ax, title, subtitle, name):
    fig.suptitle(title, x=0.02, y=0.985, ha="left", va="top", fontsize=13, fontweight="bold")
    fig.text(0.02, 0.915, subtitle, ha="left", va="top", fontsize=9.5, color=INK2)
    fig.text(0.02, 0.012, "Source: PBS and RPBS Date of Supply data, Australian Government (pbs.gov.au). "
             "Financial year = July to June, named by its ending year.",
             ha="left", va="bottom", fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.035, 1, 0.85))
    fig.savefig(DOCS / name, dpi=160)
    plt.close(fig)
    print("wrote", DOCS / name)


# ---- Figure 1: spending by ATC level 1, latest full financial year -------------------------
a1 = pd.read_csv(RES / "05_a1_category_spend_1.csv")
fy1, fy0 = a1.fin_year.max(), a1.fin_year.min()
d = a1[a1.fin_year == fy1].sort_values("total_cost_m")
fig, ax = plt.subplots(figsize=(9, 5.6))
ax.barh(d.atc1_name, d.total_cost_m / 1000, color=BLUE, height=0.62)
for y, (v, s) in enumerate(zip(d.total_cost_m / 1000, d.share_pct)):
    ax.text(v + 0.08, y, f"\\${v:.1f}B  ({s:.0f}%)", va="center", fontsize=8.5, color=INK2)
ax.set_xlabel("Total cost, A$ billion")
ax.set_xlim(0, d.total_cost_m.max() / 1000 * 1.22)
ax.grid(axis="y", visible=False)
top = d.iloc[-1]
finish(fig, ax,
       f"Cancer and immune-system drugs take {top.share_pct:.0f}% of PBS spending",
       f"Total cost (government + patient) by ATC anatomical group, FY{fy1}", "fig_a1_category_spend.png")

# ---- Figure 2: patient share of total cost ------------------------------------------------
a2 = pd.read_csv(RES / "06_a2_burden_share_1.csv", parse_dates=["month_start"])
full = a2[a2.months_in_window == 12]
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.plot(a2.month_start, a2.patient_share_pct, color=BLUE, lw=2, label="Monthly")
ax.plot(full.month_start, full.patient_share_12m_pct, color=ORANGE, lw=2, label="12-month rolling")
for jan in a2.month_start[a2.month_start.dt.month == 1]:
    ax.axvline(jan, color=MUTED, lw=0.8, ls=(0, (2, 3)))
ax.text(a2.month_start[a2.month_start.dt.month == 1].iloc[0], a2.patient_share_pct.max() + 0.55,
        " 1 January: safety net resets", fontsize=8.5, color=INK2, va="bottom")
ax.set_ylabel("Patient share of total cost, %")
ax.set_ylim(a2.patient_share_pct.min() - 1.5, a2.patient_share_pct.max() + 1.8)
ax.grid(axis="x", visible=False)
ax.legend(frameon=False, loc="lower left", ncol=2)
finish(fig, ax,
       f"Patients' share of PBS cost fell from {full.patient_share_12m_pct.iloc[0]:.1f}% to "
       f"{full.patient_share_12m_pct.iloc[-1]:.1f}%, with a sharp yearly cycle",
       "Patient contribution as a share of total cost. The share drops through the year\n"
       "as patients reach the safety net, then jumps each January.", "fig_a2_patient_share.png")

# ---- Figure 3: concentration of government spending (Pareto curve) --------------------------
app = pd.read_parquet("app/data/monthly_drug.parquet")
months = app.groupby("fin_year").month_start.nunique()
last_fy = months[months == 12].index.max()
drug = (app[app.fin_year == last_fy].groupby("drug_name").govt_cost.sum()
        .sort_values(ascending=False).reset_index())
drug["rank"] = np.arange(1, len(drug) + 1)
drug["cum_pct"] = 100 * drug.govt_cost.cumsum() / drug.govt_cost.sum()
fig, ax = plt.subplots(figsize=(9, 4.8))
ax.plot(drug["rank"], drug.cum_pct, color=BLUE, lw=2)
for target in (50, 80):
    r = int(drug.loc[drug.cum_pct >= target, "rank"].iloc[0])
    ax.plot([r], [target], "o", ms=8, color=BLUE, mec=SURFACE, mew=2)
    ax.annotate(f"{r} drugs = {target}%", (r, target), xytext=(14, -14), textcoords="offset points",
                fontsize=9.5, color=INK)
ax.set_xlabel(f"Drugs ranked by government spending (1 = highest), of {len(drug):,}")
ax.set_ylabel("Cumulative share of government spending, %")
ax.set_xlim(0, len(drug)); ax.set_ylim(0, 102)
n50 = int(drug.loc[drug.cum_pct >= 50, "rank"].iloc[0])
finish(fig, ax, f"{n50} of {len(drug):,} drugs account for half of government PBS spending",
       f"Cumulative share of government contribution by generic drug, FY{last_fy}",
       "fig_a3_concentration.png")

# ---- Figure 4: seasonal index heatmap -----------------------------------------------------
a4 = pd.read_csv(RES / "08_a4_seasonality_2.csv")
order = a4.drop_duplicates("atc2_code").sort_values("total_scripts_m", ascending=False).atc2_code
mat = a4.pivot(index="atc2_code", columns="cal_month", values="seasonal_index").loc[order]
cmap = LinearSegmentedColormap.from_list("div", ["#eb6834", "#f0efec", "#2a78d6"])
span = max(mat.values.max() - 1, 1 - mat.values.min())
fig, ax = plt.subplots(figsize=(9, 6))
im = ax.imshow(mat.values, cmap=cmap, vmin=1 - span, vmax=1 + span, aspect="auto")
ax.set_xticks(range(12), ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
ax.set_yticks(range(len(mat)), mat.index)
ax.set_xticks(np.arange(-.5, 12, 1), minor=True); ax.set_yticks(np.arange(-.5, len(mat), 1), minor=True)
ax.grid(False); ax.grid(which="minor", color=SURFACE, linewidth=2); ax.tick_params(which="both", length=0)
for s in ax.spines.values():
    s.set_visible(False)
for i in range(mat.shape[0]):
    for j in range(mat.shape[1]):
        v = mat.values[i, j]
        if v == mat.values[i].max() or v == mat.values[i].min():
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8, color=INK)
ax.set_ylabel("ATC level 2 group (15 largest by scripts)")
cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
cb.set_label("Seasonal index (1.00 = average month)", color=INK2); cb.outline.set_visible(False)
dec_peak = int((mat.idxmax(axis=1) == 12).sum())
finish(fig, ax, f"December is the peak month for {dec_peak} of the 15 largest drug groups",
       "Scripts in each calendar month relative to the group's average month. "
       "Each row shows its highest and lowest value.", "fig_a4_seasonality.png")

# ---- Figure 5: volume effect vs price effect ----------------------------------------------
a5 = pd.read_csv(RES / "09_a5_price_volume_1.csv")
tot = pd.read_csv(RES / "09_a5_price_volume_2.csv").iloc[0]
d = a5[a5.atc1_code != "X"].sort_values("change_m")
y = np.arange(len(d)); h = 0.36
fig, ax = plt.subplots(figsize=(9, 6))
ax.barh(y + h / 2, d.volume_effect_m / 1000, height=h, color=BLUE, label="Volume effect (more or fewer scripts)")
ax.barh(y - h / 2, d.price_effect_m / 1000, height=h, color=ORANGE, label="Price effect (cost per script)")
ax.axvline(0, color=MUTED, lw=1)
ax.set_yticks(y, d.atc1_name)
ax.set_xlabel(f"Change in total cost, FY{fy0} to FY{fy1}, A$ billion")
ax.grid(axis="y", visible=False)
ax.legend(frameon=False, loc="center right", bbox_to_anchor=(1.0, 0.36))
finish(fig, ax,
       f"Spending rose {tot.cost_growth_pct:.0f}% while scripts rose {tot.script_growth_pct:.0f}%: "
       "cost per script drove the growth",
       f"Change in total cost split into a volume effect and a price effect, by ATC group.\n"
       f"Average cost per script went from A\\${tot.cost_per_script_y0:.2f} to A\\${tot.cost_per_script_y1:.2f}.",
       "fig_a5_price_volume.png")
