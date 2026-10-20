"""English figures for the Independent Project report.

Every number plotted here is copied from the stored outputs of
backend/notebooks/WaterTracker_pipeline.ipynb (run of 8 October 2026) or read from
backend/reports/table_test_scores.csv. Nothing is recomputed or estimated.

Usage (from the repository root):  python docs/independent-project/scripts/make_figures.py
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs" / "independent-project" / "figures"
NB_FIG = ROOT / "backend" / "reports" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# Reference palette (light mode): categorical slots in fixed order, grays for baselines
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
GRAY_LIGHT, GRAY_DARK = "#b9b8b3", "#6f6e69"
RED = "#e34948"
MONTHS = list("JFMAMJJASOND")

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK2,
    "axes.titlecolor": INK,
    "axes.titlesize": 11,
    "axes.titleweight": "semibold",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "legend.frameon": False,
    "figure.dpi": 110,
    "savefig.dpi": 220,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})


def save(fig, name, also_notebook=False):
    fig.savefig(OUT / f"{name}.png")
    if also_notebook:
        fig.savefig(NB_FIG / f"{name}.png")
    plt.close(fig)


# ---------------------------------------------------------------- diagrams
def box(ax, x, y, w, h, title, body, color, hh=0.055):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.018",
                                fc="white", ec=color, lw=1.6))
    ax.add_patch(FancyBboxPatch((x, y + h - hh), w, hh, boxstyle="round,pad=0.012,rounding_size=0.018",
                                fc=color, ec=color, lw=0))
    ax.text(x + w / 2, y + h - hh / 2, title, ha="center", va="center", color="white", fontsize=9.2, weight="bold")
    ax.text(x + w / 2, y + (h - hh) / 2, body, ha="center", va="center", color=INK, fontsize=8, linespacing=1.35)


def arrow(ax, p, q, color=MUTED):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=12, lw=1.4, color=color,
                                 shrinkA=2, shrinkB=2))


def workflow():
    fig, ax = plt.subplots(figsize=(11, 5.6))
    ax.set_xlim(-0.015, 1.0)
    ax.set_ylim(0, 1)
    ax.axis("off")
    w, h = 0.215, 0.30
    xs = [0.01, 0.262, 0.514, 0.766]
    top = [
        ("1. Inventory (GIS)", "65 application water points\n→ 44 physical reservoirs\n+ 56 JRC water bodies ≥ 10 ha\n= 100 analysis regions"),
        ("2. Extraction (GEE)", "Sentinel-2 MNDWI at 10 m\n(Cloud Score+ mask)\nSentinel-1 VV backscatter\nCHIRPS, ERA5-Land, SRTM"),
        ("3. Quality control", "reliable months (≥ 90 % valid)\nradar gap-filling (Theil-Sen)\nHampel filter, short gaps\n→ monthly panel 2019-2026"),
        ("4. Hydrological analysis", "filling ratio = area / A_ref\nregime, response to rain\ndry-season drawdown\ntrends (Mann-Kendall + FDR)"),
    ]
    bottom = [
        ("8. Delivery", "monthly API update\nbulletin ranked by risk\nmap, reservoir sheet\nCSV export"),
        ("7. Final model", "retrained on all data\nbundle + model card\nreload check\nstatus: actif / à risque / tari"),
        ("6. Evaluation", "temporal split 2019-23 / 24 / 25-26\nstrong baselines, bootstrap\nconformal 80 % intervals\nalerts, grouped CV"),
        ("5. Modelling", "32 features known at time t\nRidge, random forest, HGB\nlevel vs change, h = 1-3 months\nalert classifier"),
    ]
    colors_top = [BLUE] * 4
    colors_bottom = [AQUA, AQUA, ORANGE, ORANGE]
    for x, (t, b), c in zip(xs, top, colors_top):
        box(ax, x, 0.60, w, h, t, b, c)
    for x, (t, b), c in zip(xs, bottom, colors_bottom):
        box(ax, x, 0.12, w, h, t, b, c)
    for i in range(3):
        arrow(ax, (xs[i] + w, 0.75), (xs[i + 1], 0.75))
        arrow(ax, (xs[i + 1], 0.27), (xs[i] + w, 0.27))
    arrow(ax, (xs[3] + w / 2, 0.60), (xs[3] + w / 2, 0.42))
    ax.text(0.5, 0.985, "WaterTracker v3: from satellite images to a monthly early-warning bulletin",
            ha="center", va="top", fontsize=12, weight="bold", color=INK)
    ax.text(0.5, 0.045, "Audit of the previous model (v2) → justified the redesign of steps 2-6",
            ha="center", va="center", fontsize=8.5, color=INK2, style="italic")
    for label, c, x in [("Data and measurement", BLUE, 0.22), ("Forecasting and evaluation", ORANGE, 0.45),
                        ("Operations", AQUA, 0.69)]:
        ax.add_patch(FancyBboxPatch((x, 0.505), 0.014, 0.03, boxstyle="round,pad=0,rounding_size=0.004", fc=c, ec=c))
        ax.text(x + 0.02, 0.52, label, va="center", fontsize=8.5, color=INK2)
    save(fig, "fig00_workflow", also_notebook=True)


def project_stages():
    fig, ax = plt.subplots(figsize=(11, 2.6))
    ax.set_xlim(-0.015, 1.0)
    ax.set_ylim(0, 1)
    ax.axis("off")
    stages = [
        ("Problem definition", "unmonitored small\nreservoirs; audit of\nthe v2 model"),
        ("Research questions", "RQ1-RQ4 and\ntestable hypotheses\nH1-H4"),
        ("Literature review", "remote sensing of\nwater, reservoir\nhydrology, forecasting"),
        ("Methodology", "GEE pipeline, fusion,\ntemporal validation,\nbaselines"),
        ("Analysis", "results, hypothesis\nverdicts, limits,\nrecommendations"),
    ]
    w = 0.165
    for i, (t, b) in enumerate(stages):
        x = 0.005 + i * 0.2
        box(ax, x, 0.08, w, 0.80, t, b, [BLUE, BLUE, AQUA, ORANGE, ORANGE][i], hh=0.16)
        if i < 4:
            arrow(ax, (x + w, 0.45), (x + 0.2, 0.45))
    save(fig, "fig00b_project_stages")


def architecture():
    fig, ax = plt.subplots(figsize=(11, 4.6))
    ax.set_xlim(-0.015, 1.015)
    ax.set_ylim(0, 1)
    ax.axis("off")
    box(ax, 0.01, 0.55, 0.22, 0.36, "Google Earth Engine", "Sentinel-2, Sentinel-1\nCHIRPS, ERA5-Land\nJRC GSW, SRTM, HydroBASINS", BLUE)
    box(ax, 0.01, 0.08, 0.22, 0.36, "Research notebook", "extraction, QC, analysis\ntraining, evaluation\nbundle.joblib + model card", ORANGE)
    box(ax, 0.39, 0.30, 0.24, 0.48, "Backend API (FastAPI)", "monthly collector (APScheduler)\nml/features.py + forecasting.py\nbulletin, history, forecast\nadmin endpoints (API key)\nhosted on Render", BLUE)
    box(ax, 0.39, 0.02, 0.24, 0.22, "PostgreSQL + PostGIS", "reservoirs, monthly areas\nforecasts (hosted on Neon)", AQUA)
    box(ax, 0.77, 0.55, 0.22, 0.36, "Web application", "React + TypeScript + Leaflet\nmap, reservoir sheet\nmonthly bulletin, CSV\nhosted on Vercel", AQUA)
    box(ax, 0.77, 0.08, 0.22, 0.36, "External services", "OpenRouteService (routes)\nGroq LLM (advice text,\nlegacy v2)", GRAY_DARK)
    arrow(ax, (0.23, 0.73), (0.39, 0.62))
    arrow(ax, (0.12, 0.55), (0.12, 0.44))
    arrow(ax, (0.23, 0.26), (0.39, 0.45))
    arrow(ax, (0.51, 0.30), (0.51, 0.24))
    arrow(ax, (0.63, 0.62), (0.77, 0.73))
    arrow(ax, (0.63, 0.45), (0.77, 0.26))
    ax.text(0.31, 0.71, "monthly\nextraction", fontsize=7.5, color=INK2, ha="center")
    ax.text(0.27, 0.40, "trained\nmodel", fontsize=7.5, color=INK2, ha="center")
    ax.text(0.70, 0.71, "JSON / CSV", fontsize=7.5, color=INK2, ha="center")
    save(fig, "fig_architecture")


# ---------------------------------------------------------------- data figures
def regime():
    # Notebook §5.1 (filling quantiles by calendar month) and §7 (share below the critical threshold)
    q = pd.DataFrame({
        "p10": [0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.12, 0.46, 0.44, 0.18, 0.13, 0.08],
        "p25": [0.14, 0.00, 0.00, 0.00, 0.00, 0.08, 0.39, 0.70, 0.66, 0.46, 0.38, 0.33],
        "p50": [0.39, 0.15, 0.00, 0.00, 0.02, 0.31, 0.71, 0.94, 0.84, 0.66, 0.59, 0.54],
        "p75": [0.58, 0.38, 0.13, 0.05, 0.18, 0.64, 0.94, 1.02, 0.97, 0.85, 0.75, 0.70],
        "p90": [0.74, 0.56, 0.34, 0.21, 0.47, 0.91, 1.04, 1.13, 1.02, 0.95, 0.86, 0.82],
    })
    crit = [0.31, 0.55, 0.80, 0.89, 0.76, 0.38, 0.15, 0.03, 0.04, 0.10, 0.13, 0.17]
    x = np.arange(12)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 5.6), sharex=True, gridspec_kw={"height_ratios": [1.5, 1]})
    a1.fill_between(x, q.p10, q.p90, color=BLUE, alpha=0.10, lw=0, label="10th-90th percentile")
    a1.fill_between(x, q.p25, q.p75, color=BLUE, alpha=0.22, lw=0, label="25th-75th percentile")
    a1.plot(x, q.p50, color=BLUE, lw=2, marker="o", ms=5, mec="white", mew=1.5, label="median")
    a1.axhline(0.2, color=RED, lw=1.2, ls=(0, (2, 2)))
    a1.text(11.3, 0.215, "critical level (20 %)", color=INK2, fontsize=8, ha="right", va="bottom")
    a1.set_ylabel("Filling ratio")
    a1.set_title("Mean regime of the 96 modelled reservoirs (2019-2026)", loc="left")
    a1.legend(loc="upper left", fontsize=8.5)
    a2.bar(x, crit, width=0.55, color=ORANGE)
    for i in (3, 8):
        a2.text(x[i], crit[i] + 0.03, f"{crit[i]:.0%}", ha="center", fontsize=8.5, color=INK)
    a2.set_ylim(0, 1)
    a2.set_ylabel("Share below 20 %")
    a2.set_title("Share of reservoirs below the critical level", loc="left")
    a2.set_xticks(x, MONTHS)
    a2.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    fig.align_ylabels()
    save(fig, "fig_regime")


def volume():
    # Notebook §4.7: estimated total volume of the 53 reservoirs inside the Liebe et al. (2005) domain
    v = [4.33, 1.91, 0.56, 0.29, 1.37, 5.71, 11.43, 16.84, 15.06, 10.40, 8.29, 6.73]
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.bar(np.arange(12), v, width=0.55, color=BLUE)
    for i in (3, 7):
        ax.text(i, v[i] + 0.4, f"{v[i]:.2f}", ha="center", fontsize=8.5, color=INK)
    ax.set_xticks(np.arange(12), MONTHS)
    ax.set_ylabel("Million m³")
    ax.set_title("Indicative stored volume of the 53 reservoirs of 1-35 ha (monthly mean)", loc="left")
    save(fig, "fig_volume")


def test_mae():
    t = pd.read_csv(ROOT / "backend" / "reports" / "table_test_scores.csv", header=[0, 1], index_col=0)
    mae = t["MAE"]
    mae.columns = [int(c) for c in mae.columns]
    rename = {"Persistance": "Persistence", "Climatologie": "Climatology"}
    mae.index = [rename.get(i, i) for i in mae.index]
    series = [("Persistence", GRAY_LIGHT), ("Climatology", GRAY_DARK), ("Ridge", AQUA),
              ("RandomForest", BLUE), ("HGB", ORANGE)]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    w = 0.15
    for i, (name, c) in enumerate(series):
        vals = mae.loc[name, [1, 2, 3]].values
        ax.bar(np.arange(3) + (i - 2) * (w + 0.012), vals, width=w, color=c, label=name)
        if name == "RandomForest":
            for j, v in enumerate(vals):
                ax.text(j + (i - 2) * (w + 0.012), v + 0.008, f"{v:.3f}", ha="center", fontsize=8, color=INK)
        if name == "Climatology":
            for j, v in enumerate(vals):
                ax.text(j + (i - 2) * (w + 0.012), v + 0.008, f"{v:.3f}", ha="center", fontsize=8, color=INK2)
    ax.set_xticks(np.arange(3), ["1 month ahead", "2 months ahead", "3 months ahead"])
    ax.set_ylabel("Test MAE (filling ratio)")
    ax.set_title("Forecast error on the test period (2025-2026)", loc="left")
    ax.legend(ncol=5, loc="upper left", fontsize=8.5, bbox_to_anchor=(0, 1.0))
    ax.set_ylim(0, 0.5)
    save(fig, "fig_test_mae")


def skill():
    # Notebook §10.4: block-bootstrap MAE gain of the random forest over climatology
    gain = [0.0262, 0.0012, 0.0045]
    lo = [0.0161, -0.0158, -0.0026]
    hi = [0.0359, 0.0140, 0.0105]
    fig, ax = plt.subplots(figsize=(6, 3.2))
    x = np.arange(3)
    ax.axhline(0, color=INK2, lw=1)
    ax.errorbar(x, gain, yerr=[np.subtract(gain, lo), np.subtract(hi, gain)], fmt="o", color=BLUE,
                ms=8, mec="white", mew=2, capsize=5, lw=2)
    for xi, g, p in zip(x, gain, ["p < 0.001", "p = 0.41", "p = 0.11"]):
        ax.text(xi + 0.08, g, f"{g:+.4f}\n{p}", va="center", fontsize=8.5, color=INK)
    ax.set_xticks(x, ["1 month", "2 months", "3 months"])
    ax.set_xlim(-0.4, 2.7)
    ax.set_ylabel("MAE reduction vs climatology")
    ax.set_title("Gain of the random forest over climatology (95 % CI)", loc="left")
    save(fig, "fig_skill")


def alerts():
    # Notebook §11.2: F1 on the test set and detection of entries into crisis
    f1 = {"Persistence": [0.769, 0.568, 0.398], "Regression rule": [0.883, 0.812, 0.853],
          "HGB classifier": [0.886, 0.833, 0.853]}
    onsets = np.array([175, 332, 468])
    detected = np.array([123, 256, 374])
    false_alarms = np.array([25, 36, 40])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.6))
    w = 0.22
    for i, ((name, vals), c) in enumerate(zip(f1.items(), [GRAY_LIGHT, AQUA, BLUE])):
        a1.bar(np.arange(3) + (i - 1) * (w + 0.015), vals, width=w, color=c, label=name)
    a1.set_xticks(np.arange(3), ["1 month", "2 months", "3 months"])
    a1.set_ylim(0, 1.18)
    a1.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
    a1.set_ylabel("F1 score (test)")
    a1.set_title("Alert quality: critical level (< 20 %)", loc="left")
    a1.legend(loc="upper right", fontsize=8, ncol=3, bbox_to_anchor=(1.0, 1.0))
    x = np.arange(3)
    a2.bar(x - 0.2, detected, width=0.36, color=BLUE, label="onsets detected")
    a2.bar(x - 0.2, onsets - detected, width=0.36, bottom=detected, color="#b7d3f6", label="onsets missed")
    a2.bar(x + 0.2, false_alarms, width=0.36, color=ORANGE, label="false alarms")
    for xi, d, n, fa in zip(x, detected, onsets, false_alarms):
        a2.text(xi - 0.2, n + 8, f"{d}/{n}", ha="center", fontsize=8.5, color=INK)
        a2.text(xi + 0.2, fa + 8, f"{fa}", ha="center", fontsize=8.5, color=INK)
    a2.set_xticks(x, ["1 month", "2 months", "3 months"])
    a2.set_ylabel("Number of situations")
    a2.set_title("Entries into crisis on the test set", loc="left")
    a2.legend(loc="upper left", fontsize=8)
    a2.set_ylim(0, 540)
    save(fig, "fig_alerts")


def importance():
    # Notebook §11.3: permutation importance (increase in MAE), random forest, test set
    imp = pd.DataFrame({
        "h1": [0.0928, 0.0805, 0.0262, 0.0179, 0.0090, 0.0087, 0.0061, 0.0054, 0.0033, 0.0029],
        "h3": [0.0053, 0.1383, 0.0191, 0.0190, 0.0011, 0.0032, 0.0031, 0.0020, 0.0066, 0.0060],
    }, index=["fill_l0 (current filling)", "clim_target (target-month climatology)", "precip_mm (rain of the month)",
              "clim_precip_target (rain climatology)", "dfill_1 (1-month change)", "anom_issue (current anomaly)",
              "precip_3m (3-month rain)", "clim_issue (issue-month climatology)", "issue_month_cos (calendar)",
              "jrc_seasonality (permanence)"])
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    y = np.arange(len(imp))
    for ax, col, title, c in zip(axes, ["h1", "h3"], ["1 month ahead", "3 months ahead"], [BLUE, ORANGE]):
        ax.barh(y, imp[col], height=0.55, color=c)
        ax.set_title(title, loc="left")
        ax.set_xlabel("Increase in MAE when permuted")
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(y, imp.index, fontsize=8.5)
    axes[0].invert_yaxis()
    save(fig, "fig_importance")


def v2_audit():
    # Notebook §6, D2: v2 random forest under a random and a temporal split
    labels = ["Random split", "Temporal split"]
    r2 = [0.190, -0.452]
    fig, ax = plt.subplots(figsize=(5.2, 3))
    ax.bar([0, 1], r2, width=0.45, color=[GRAY_DARK, ORANGE])
    ax.axhline(0, color=INK2, lw=1)
    for i, v in enumerate(r2):
        ax.text(i, v + (0.03 if v > 0 else -0.06), f"R² = {v:+.2f}", ha="center", fontsize=9, color=INK)
    ax.set_xticks([0, 1], labels)
    ax.set_ylim(-0.6, 0.35)
    ax.set_ylabel("R² on held-out data")
    ax.set_title("Previous model (v2): the score depends on the split", loc="left")
    save(fig, "fig_v2_audit")


if __name__ == "__main__":
    workflow()
    project_stages()
    architecture()
    regime()
    volume()
    test_mae()
    skill()
    alerts()
    importance()
    v2_audit()
    print("figures written to", OUT)
