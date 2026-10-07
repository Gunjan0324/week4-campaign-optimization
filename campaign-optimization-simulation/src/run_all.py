"""
Run the full simulation study and write every result file.

Usage (from repo root):
    python -m src.run_all
Outputs: results/*.csv, results/campaign_simulation_results.xlsx, figures/*.png
"""
from __future__ import annotations

from dataclasses import replace

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .model import (DATA, ROOT, N_SIMS, SEED, TOTAL_BUDGET, draw_shocks, evaluate,
                    load_params, make_alloc, no_shocks, optimise, summarise)
from .scenarios import build_scenarios
from .upgrade_stats import statistical_tests

RES = ROOT / "results"
FIG = ROOT / "figures"
RES.mkdir(exist_ok=True)
FIG.mkdir(exist_ok=True)

BASE = "S0 Baseline (equal split)"
JOINT = "S7 Jointly optimised"
CRO = "S8 Joint + CRO"
PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
plt.rcParams.update({"figure.dpi": 150, "axes.spines.top": False, "axes.spines.right": False,
                     "font.size": 9})


# ----------------------------------------------------------------------------
def run_scenarios(p, scenarios):
    shocks = draw_shocks(p, N_SIMS, SEED)
    results = {n: evaluate(a, pp, shocks) for n, (a, pp) in scenarios.items()}
    summary = summarise(results, BASE)
    tests = statistical_tests(results, BASE)
    # incremental ROAS vs baseline (revenue gained per extra dollar of cost)
    base_rev, base_cost = results[BASE]["revenue"].mean(), results[BASE]["total_cost"][0]
    summary["incremental_roas_vs_base"] = [
        (results[n]["revenue"].mean() - base_rev) / (results[n]["total_cost"][0] - base_cost)
        if abs(results[n]["total_cost"][0] - base_cost) > 1 else np.nan
        for n in summary["scenario"]]
    return results, summary, shocks, tests


def allocation_tables(p, scenarios):
    rows, cells = [], []
    for n, (a, _) in scenarios.items():
        tot = a.sum()
        row = {"scenario": n, "media_budget": tot}
        for i, c in enumerate(p.channels):
            row[f"{c}_$"] = a[i].sum()
            row[f"{c}_%"] = a[i].sum() / tot * 100
        for j, s in enumerate(p.segments):
            row[f"{s}_$"] = a[:, j].sum()
            row[f"{s}_%"] = a[:, j].sum() / tot * 100
        rows.append(row)
        for i, c in enumerate(p.channels):
            for j, s in enumerate(p.segments):
                cells.append({"scenario": n, "channel": c, "segment": s, "spend_usd": a[i, j]})
    return pd.DataFrame(rows), pd.DataFrame(cells)


def sensitivity(p, alloc):
    """One-at-a-time +/-20% sensitivity of expected net profit for a fixed allocation."""
    base = evaluate(alloc, p)["net_profit"][0]
    rows = []
    specs = {
        "CPM (all channels)": lambda k: replace(p, cpm=p.cpm * k),
        "CTR (all channels)": lambda k: replace(p, ctr=p.ctr * k),
        "CVR (all channels)": lambda k: replace(p, cvr=p.cvr * k),
        "Average order value": lambda k: replace(p, aov=p.aov * k),
        "Gross margin": lambda k: replace(p, margin=p.margin * k),
        "Diminishing-returns exponent (alpha)": lambda k: replace(p, alpha=np.minimum(p.alpha * k, 1.0)),
        "Brand-halo strength": lambda k: replace(p, halo_max=p.halo_max * k),
    }
    for name, f in specs.items():
        lo = evaluate(alloc, f(0.8))["net_profit"][0] - base
        hi = evaluate(alloc, f(1.2))["net_profit"][0] - base
        rows.append({"parameter": name, "profit_change_at_-20%": lo, "profit_change_at_+20%": hi,
                     "swing": abs(hi - lo)})
    return pd.DataFrame(rows).sort_values("swing", ascending=False).reset_index(drop=True)


def stress_tests(p, a_base, a_opt, shocks):
    """Does the optimised plan still beat the baseline if our benchmarks are wrong?"""
    cases = {
        "No stress (reference)": p,
        "CTR 20% lower than assumed": replace(p, ctr=p.ctr * 0.8),
        "CVR 20% lower than assumed": replace(p, cvr=p.cvr * 0.8),
        "CPM 20% higher than assumed": replace(p, cpm=p.cpm * 1.2),
        "Harsher saturation (alpha - 0.15)": replace(p, alpha=np.maximum(p.alpha - 0.15, 0.1)),
        "No brand halo": replace(p, halo_max=0.0),
        "Search & Email 30% weaker": replace(p, cvr=p.cvr * np.array([0.7, 1, 0.7, 1, 1])),
    }
    rows = []
    for n, pp in cases.items():
        b, o = evaluate(a_base, pp, shocks), evaluate(a_opt, pp, shocks)
        d = o["net_profit"] - b["net_profit"]
        rows.append({"stress_case": n, "baseline_profit": b["net_profit"].mean(),
                     "optimised_profit": o["net_profit"].mean(), "uplift": d.mean(),
                     "prob_optimised_wins": float((d > 0).mean())})
    return pd.DataFrame(rows)


def budget_sweep(p, shocks):
    rows = []
    for b in range(30_000, 200_001, 10_000):
        a_eq = make_alloc(p, b)
        a_op = optimise(p, b, "joint", n_starts=6)
        for label, a in (("Equal split", a_eq), ("Optimised mix", a_op)):
            r = evaluate(a, p, shocks)
            rows.append({"budget": b, "strategy": label, "revenue": r["revenue"].mean(),
                         "net_profit": r["net_profit"].mean(), "roas": r["roas"].mean()})
    df = pd.DataFrame(rows)
    for s, g in df.groupby("strategy"):
        df.loc[g.index, "marginal_roas"] = g["revenue"].diff() / g["budget"].diff()
    return df


# ----------------------------------------------------------------------------
# Figures
# ----------------------------------------------------------------------------
def fig_allocation(p, alloc_df):
    short = [s.split(" ")[0] for s in alloc_df["scenario"]]
    fig, ax = plt.subplots(figsize=(8, 4))
    bottom = np.zeros(len(alloc_df))
    for i, c in enumerate(p.channels):
        ax.bar(short, alloc_df[f"{c}_%"], bottom=bottom, label=c, color=PALETTE[i])
        bottom += alloc_df[f"{c}_%"].to_numpy()
    ax.set_ylabel("Share of media budget (%)")
    ax.set_title("Channel mix by scenario")
    ax.legend(ncol=5, loc="upper center", bbox_to_anchor=(0.5, -0.08), frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig1_channel_mix.png")
    plt.close(fig)


def fig_heatmap(p, a):
    fig, ax = plt.subplots(figsize=(5.5, 3.6))
    pct = a / a.sum() * 100
    im = ax.imshow(pct, cmap="YlGnBu")
    ax.set_xticks(range(p.n_s), p.segments)
    ax.set_yticks(range(p.n_c), p.channels)
    for i in range(p.n_c):
        for j in range(p.n_s):
            ax.text(j, i, f"{pct[i, j]:.1f}", ha="center", va="center",
                    color="white" if pct[i, j] > pct.max() * 0.6 else "black")
    ax.set_title("S7 optimised allocation (% of media budget)")
    fig.colorbar(im, ax=ax, shrink=0.8)
    fig.tight_layout()
    fig.savefig(FIG / "fig2_joint_allocation_heatmap.png")
    plt.close(fig)


def fig_roas(summary):
    s = summary.copy()
    short = [n.split(" ")[0] for n in s["scenario"]]
    fig, ax = plt.subplots(figsize=(8, 3.8))
    err = [s["roas_mean"] - s["roas_p5"], s["roas_p95"] - s["roas_mean"]]
    ax.bar(short, s["roas_mean"], yerr=err, capsize=4, color="#4c78a8")
    ax.axhline(1 / 0.55, color="red", ls="--", lw=1)
    ax.text(-0.45, 1 / 0.55 + 0.05, "break-even ROAS (1 / margin)", color="red", ha="left", fontsize=8,
            bbox=dict(facecolor="white", edgecolor="none", pad=1))
    ax.set_ylabel("ROAS (revenue / total cost)")
    ax.set_title("Expected ROAS with 5th-95th percentile range (5,000 simulations)")
    fig.tight_layout()
    fig.savefig(FIG / "fig3_roas_by_scenario.png")
    plt.close(fig)


def fig_profit_dist(results):
    fig, ax = plt.subplots(figsize=(7, 3.8))
    for n, c in ((BASE, "#7f7f7f"), (JOINT, "#2ca02c"), (CRO, "#1f77b4")):
        ax.hist(results[n]["net_profit"] / 1e3, bins=60, alpha=0.55, label=n, color=c, density=True)
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("Net profit (USD thousand)")
    ax.set_ylabel("Density")
    ax.set_title("Distribution of simulated net profit")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig4_profit_distribution.png")
    plt.close(fig)


def fig_budget(sweep):
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6))
    for label, g in sweep.groupby("strategy"):
        axes[0].plot(g["budget"] / 1e3, g["revenue"] / 1e3, marker="o", label=label)
        axes[1].plot(g["budget"] / 1e3, g["marginal_roas"], marker="o", label=label)
    axes[0].set_xlabel("Media budget (USD thousand)")
    axes[0].set_ylabel("Expected revenue (USD thousand)")
    axes[0].set_title("Response curve")
    axes[1].axhline(1 / 0.55, color="red", ls="--", lw=1)
    axes[1].set_xlabel("Media budget (USD thousand)")
    axes[1].set_ylabel("Marginal revenue per extra $1")
    axes[1].set_title("Marginal ROAS (red = break-even)")
    axes[0].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig5_budget_response.png")
    plt.close(fig)


def fig_tornado(sens):
    s = sens.iloc[::-1]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    y = np.arange(len(s))
    ax.barh(y, s["profit_change_at_-20%"] / 1e3, color="#d62728", label="-20%")
    ax.barh(y, s["profit_change_at_+20%"] / 1e3, color="#2ca02c", label="+20%")
    ax.set_yticks(y, s["parameter"])
    ax.axvline(0, color="k", lw=0.8)
    ax.set_xlabel("Change in expected net profit (USD thousand)")
    ax.set_title("Sensitivity of S7 plan to +/-20% parameter changes")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(FIG / "fig6_sensitivity_tornado.png")
    plt.close(fig)


# ----------------------------------------------------------------------------
def write_excel(p, summary, alloc_df, cells_df, sens, stress, sweep, tests):
    ch = pd.read_csv(DATA / "channel_benchmarks.csv")
    sg = pd.read_csv(DATA / "segment_multipliers.csv")
    af = pd.read_csv(DATA / "channel_segment_affinity.csv")
    glob = pd.DataFrame({
        "assumption": ["Total budget (USD)", "Average order value (USD)", "Gross margin",
                       "Max brand halo on Search", "Halo saturation (awareness share)",
                       "Std-dev log CPM", "Std-dev log CTR", "Std-dev log CVR",
                       "Std-dev log market demand", "Simulations per scenario", "Random seed"],
        "value": [TOTAL_BUDGET, p.aov, p.margin, p.halo_max, p.halo_sat,
                  dict(p.sigma)["cpm"], dict(p.sigma)["ctr"], dict(p.sigma)["cvr"],
                  dict(p.sigma)["market"], N_SIMS, SEED]})
    readme = pd.DataFrame({"Sheet": [
        "Assumptions_Global", "Assumptions_Channels", "Assumptions_Segments", "Affinity",
        "Scenario_Allocation", "Scenario_Cells", "Results_Summary", "Sensitivity",
        "Stress_Tests", "Budget_Sweep", "Statistical_Tests", "Benchmark_Sources"],
        "Content": [
        "Global business and uncertainty assumptions", "Channel benchmarks (CPM, CTR, CVR, alpha)",
        "Segment multipliers", "Channel x segment CTR affinity",
        "Spend by channel and segment per scenario ($ and %)",
        "Full channel x segment spend matrix per scenario",
        "Monte Carlo results (mean, P5, P95) and paired comparison vs baseline",
        "+/-20% one-at-a-time sensitivity of S7", "Robustness of S7 vs baseline under wrong assumptions",
        "Budget response curves", "ANOVA, Kruskal-Wallis and paired t-tests with Holm correction", "Current public benchmark anchors and how they map to the conservative simulation inputs"]})
    with pd.ExcelWriter(RES / "campaign_simulation_results.xlsx", engine="openpyxl") as xw:
        readme.to_excel(xw, sheet_name="README", index=False)
        glob.to_excel(xw, sheet_name="Assumptions_Global", index=False)
        ch.to_excel(xw, sheet_name="Assumptions_Channels", index=False)
        sg.to_excel(xw, sheet_name="Assumptions_Segments", index=False)
        af.to_excel(xw, sheet_name="Affinity", index=False)
        alloc_df.round(2).to_excel(xw, sheet_name="Scenario_Allocation", index=False)
        cells_df.round(2).to_excel(xw, sheet_name="Scenario_Cells", index=False)
        summary.round(3).to_excel(xw, sheet_name="Results_Summary", index=False)
        sens.round(1).to_excel(xw, sheet_name="Sensitivity", index=False)
        stress.round(3).to_excel(xw, sheet_name="Stress_Tests", index=False)
        sweep.round(3).to_excel(xw, sheet_name="Budget_Sweep", index=False)
        tests.to_excel(xw, sheet_name="Statistical_Tests", index=False)
        sources = pd.DataFrame({"Source": ["WordStream 2026 Google Ads benchmarks", "WordStream 2025 Facebook Ads benchmarks", "Mailchimp email marketing benchmarks"], "URL": ["https://www.wordstream.com/blog/2026-google-ads-benchmarks", "https://www.wordstream.com/blog/facebook-ads-benchmarks-2025", "https://mailchimp.com/resources/email-marketing-benchmarks/"], "Use_in_model": ["Search benchmark anchor; model uses a deliberately conservative scenario assumption rather than copying the US aggregate", "Social benchmark anchor; model uses conservative e-commerce-style assumptions", "Email click-rate anchor; model uses a conservative click-to-purchase assumption"]})
        sources.to_excel(xw, sheet_name="Benchmark_Sources", index=False)
        for ws in xw.book.worksheets:           # tidy column widths
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)
            ws.freeze_panes = "A2"


def main():
    p = load_params()
    scenarios = build_scenarios(p)
    results, summary, shocks, tests = run_scenarios(p, scenarios)
    alloc_df, cells_df = allocation_tables(p, scenarios)
    a_base, a_opt = scenarios[BASE][0], scenarios[JOINT][0]
    sens = sensitivity(p, a_opt)
    stress = stress_tests(p, a_base, a_opt, shocks)
    sweep = budget_sweep(p, shocks)

    summary.to_csv(RES / "scenario_summary.csv", index=False)
    alloc_df.to_csv(RES / "scenario_allocation.csv", index=False)
    cells_df.to_csv(RES / "scenario_allocation_cells.csv", index=False)
    sens.to_csv(RES / "sensitivity.csv", index=False)
    stress.to_csv(RES / "stress_tests.csv", index=False)
    sweep.to_csv(RES / "budget_sweep.csv", index=False)
    tests.to_csv(RES / "statistical_tests.csv", index=False)
    write_excel(p, summary, alloc_df, cells_df, sens, stress, sweep, tests)

    fig_allocation(p, alloc_df)
    fig_heatmap(p, a_opt)
    fig_roas(summary)
    fig_profit_dist(results)
    fig_budget(sweep)
    fig_tornado(sens)

    pd.set_option("display.width", 220, "display.max_columns", 30)
    print(summary[["scenario", "total_cost", "revenue_mean", "net_profit_mean", "roas_mean",
                   "cpa_mean", "conversions_mean", "d_profit_vs_base", "prob_beats_base",
                   "prob_loss", "incremental_roas_vs_base"]].round(2).to_string(index=False))
    print(alloc_df.filter(regex="scenario|_%").round(1).to_string(index=False))
    print(sens.round(0).to_string(index=False))
    print(stress.round(2).to_string(index=False))
    print(sweep.round(2).to_string(index=False))


if __name__ == "__main__":
    main()
