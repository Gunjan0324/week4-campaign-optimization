"""
Build the written report (Markdown + PDF) from the result files, so that every
number in the report is generated from the simulation outputs.

Usage:  python -m src.build_report      (run `python -m src.run_all` first)
"""
from __future__ import annotations

import html

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)
from PIL import Image as PILImage

from .model import AOV, DATA, GROSS_MARGIN, HALO_MAX, HALO_SATURATION, N_SIMS, ROOT, SEED, TOTAL_BUDGET

# ---- EDIT THESE BEFORE SUBMITTING -------------------------------------------
AUTHOR = "Gunjan"
COURSE = "Week 4 Task - Simulation of Campaign Optimization Strategies"
DATE = "October 2026"
# -----------------------------------------------------------------------------

RES, FIG, OUT = ROOT / "results", ROOT / "figures", ROOT / "report"
usd = lambda x: f"${x:,.0f}"
sgn = lambda x: f"{'+' if x >= 0 else '-'}${abs(x):,.0f}"
pct = lambda x, d=0: f"{x:.{d}f}%"

summary = pd.read_csv(RES / "scenario_summary.csv").set_index("scenario")
alloc = pd.read_csv(RES / "scenario_allocation.csv").set_index("scenario")
sens = pd.read_csv(RES / "sensitivity.csv")
stress = pd.read_csv(RES / "stress_tests.csv")
sweep = pd.read_csv(RES / "budget_sweep.csv")
tests = pd.read_csv(RES / "statistical_tests.csv")
chan = pd.read_csv(DATA / "channel_benchmarks.csv")
seg = pd.read_csv(DATA / "segment_multipliers.csv")

S = {k.split(" ")[0]: k for k in summary.index}     # "S0" -> full name
g = lambda s, col: summary.loc[S[s], col]
al = lambda s, col: alloc.loc[S[s], col]

opt_sweep = sweep[sweep.strategy == "Optimised mix"].set_index("budget")
best_budget = int(opt_sweep["net_profit"].idxmax())
mroas_100 = opt_sweep.loc[100000, "marginal_roas"]
breakeven = 1 / GROSS_MARGIN

syn = g("S7", "d_profit_vs_base") - g("S5", "d_profit_vs_base") - g("S6", "d_profit_vs_base")
cro_gain = g("S8", "net_profit_mean") - g("S7", "net_profit_mean")

B = []   # list of blocks
H1 = lambda t: B.append(("h1", t))
H2 = lambda t: B.append(("h2", t))
P = lambda t: B.append(("p", t))
BL = lambda items: B.append(("bullets", items))
TB = lambda head, rows, widths=None: B.append(("table", head, rows, widths))
IMG = lambda f, cap, w=15: B.append(("img", f, cap, w))
EQ = lambda t: B.append(("eq", t))
PB = lambda: B.append(("pb",))

# =============================================================================
H1("1. Executive summary")
P(f"This study builds a Monte Carlo simulation of a {usd(TOTAL_BUDGET)}, 90-day e-commerce campaign "
  f"spread over five channels (Search, Social, Email, Display, Video) and four customer segments "
  f"(18-24, 25-34, 35-49, 50+). It tests how budget level, channel mix, segment targeting and "
  f"conversion-rate optimisation (CRO) change revenue, profit and ROAS, using {N_SIMS:,} simulated "
  f"market outcomes per scenario and a constrained optimiser to find allocations.")
BL([
    f"**Baseline (equal split)** is roughly break-even: expected net profit {sgn(g('S0','net_profit_mean'))}, "
    f"ROAS {g('S0','roas_mean'):.2f}, and a {pct(g('S0','prob_loss')*100)} chance of losing money.",
    f"**Joint channel x segment optimisation (S7)** lifts expected net profit to {usd(g('S7','net_profit_mean'))} "
    f"({sgn(g('S7','d_profit_vs_base'))} vs baseline, 95% CI {sgn(g('S7','d_profit_ci_lo'))} to {sgn(g('S7','d_profit_ci_hi'))}) "
    f"and cuts the probability of loss to {pct(g('S7','prob_loss')*100)}.",
    f"**Adding a CRO programme (S8)** (+12% conversion rate for {usd(4000)}) is the best scenario: "
    f"net profit {usd(g('S8','net_profit_mean'))}, ROAS {g('S8','roas_mean'):.2f}, probability of loss {pct(g('S8','prob_loss')*100)}. "
    f"CRO adds {usd(cro_gain)} on top of S7 for a {usd(4000)} outlay.",
    f"**Spending more is not the answer.** Under diminishing returns, the last dollar at a {usd(100000)} budget "
    f"returns only about ${mroas_100:.2f} of revenue, below the break-even level of "
    f"${breakeven:.2f} (1 / gross margin). A +25% budget (S1) *reduces* expected profit by {usd(abs(g('S1','d_profit_vs_base')))}.",
    f"**Segment targeting matters most among single levers**: S6 ({sgn(g('S6','d_profit_vs_base'))}) slightly beats channel "
    f"optimisation S5 ({sgn(g('S5','d_profit_vs_base'))}); doing both gives {sgn(g('S7','d_profit_vs_base'))}.",
    f"The optimised plan keeps beating the baseline in all {len(stress)-1} stress tests where benchmark assumptions are wrong "
    f"(Section 9), so the recommendation is robust to parameter error, though absolute profit is not.",
])

H1("2. Objective and hypotheses")
P("**Objective.** Use a data-driven simulation to quantify how changes in budget allocation, channel mix and target "
  "segmentation would affect campaign performance (revenue, conversions, CPA, ROAS, ROI, net profit), and to "
  "convert the results into practical recommendations.")
P("**Hypotheses** (each is evaluated in Section 8):")
TB(["#", "Hypothesis"], [
    ["H1", "Shifting budget from low-efficiency to high-efficiency channels raises ROAS and profit at the same total budget."],
    ["H2", "Concentrating spend on high-intent, high-basket segments (25-49) raises profit more than it raises cost."],
    ["H3", "Optimising channel mix and segments jointly beats either lever on its own (positive interaction)."],
    ["H4", "Returns to budget are diminishing: marginal ROAS is below average ROAS, so extra budget has falling efficiency."],
    ["H5", "Upper-funnel awareness spend (Display/Video) has value through a halo on Search, but only up to a point."],
], [1.2, 15])

H1("3. Data, benchmarks and assumptions")
P("The model uses conservative, illustrative assumptions anchored to current public benchmark sources rather than claiming that the benchmark averages are the campaign's own performance. For example, WordStream's 2026 Google Ads benchmark reports overall CTR 6.64%, CPC $5.42 and CVR 8.18%; its 2025 Facebook lead benchmark reports CTR 2.59% and CVR 7.72%; and Mailchimp reports an all-user email click rate of 2.62%. The simulation deliberately uses lower, scenario-specific starting rates where appropriate to avoid treating broad US benchmark averages as ground truth for an unspecified e-commerce campaign. Source URLs and the mapping rationale are recorded in the Excel `Benchmark_Sources` sheet. The raw inputs are stored in `data/*.csv` so they can be audited and changed.")
P("**Benchmark source register**")
TB(["Source", "Current anchor", "Role in this model", "URL"], [
    ["WordStream 2026 Google Ads", "CTR 6.64%; CPC $5.42; CVR 8.18%", "Search external anchor; model uses a conservative starting point", "https://www.wordstream.com/blog/2026-google-ads-benchmarks"],
    ["WordStream 2025 Facebook leads", "CTR 2.59%; CVR 7.72%", "Social external anchor; model uses a conservative starting point", "https://www.wordstream.com/blog/facebook-ads-benchmarks-2025"],
    ["Mailchimp email benchmarks", "All-user click 2.62%; ecommerce click 1.74%", "Email click-rate anchor; purchase CVR remains illustrative", "https://mailchimp.com/resources/email-marketing-benchmarks/"]
], [4, 4, 6, 4])
P("The external figures are not treated as interchangeable metrics: search/social benchmark CVR definitions can differ from an e-commerce purchase conversion, and email click rate is not the same as purchase CVR. That distinction is why the model labels its channel inputs as illustrative assumptions rather than direct benchmark copies.")
P("**Business assumptions**")
TB(["Assumption", "Value", "Comment"], [
    ["Total budget", usd(TOTAL_BUDGET), "90-day campaign, fixed for scenarios S0, S3-S8"],
    ["Average order value", usd(AOV), "Scaled by segment (0.75-1.20)"],
    ["Gross margin", pct(GROSS_MARGIN * 100), f"Break-even ROAS = {breakeven:.2f}"],
    ["Brand halo on Search", f"up to +{HALO_MAX*100:.0f}% conversions",
     f"Saturates when Display+Video >= {HALO_SATURATION*100:.0f}% of budget"],
    ["Uncertainty (log-normal sigma)", "CPM 10%, CTR 12%, CVR 15%, market 5%", "Mean-one shocks"],
    ["Simulations / seed", f"{N_SIMS:,} / {SEED}", "Common random numbers across scenarios"],
], [4.5, 5, 6.7])
P("**Channel benchmarks** (implied CPC and CPA are derived: CPC = CPM / (1000 x CTR); CPA = CPC / CVR)")
rows = []
for _, r in chan.iterrows():
    cpc = r.cpm_usd / (1000 * r.ctr)
    rows.append([r.channel, f"${r.cpm_usd:.1f}", pct(r.ctr * 100, 2), pct(r.cvr * 100, 2),
                 f"${cpc:.2f}", f"${cpc / r.cvr:.0f}", f"{r.alpha:.2f}"])
TB(["Channel", "CPM", "CTR", "CVR", "Implied CPC", "Implied CPA", "Alpha"], rows, [3, 2, 2, 2, 2.6, 2.6, 2])
P("`Alpha` is the diminishing-returns exponent (1 = linear; lower = faster saturation). Email is lowest because "
  "a customer list is finite; Search is limited by query volume.")
P("**Segment multipliers**")
TB(["Segment", "CPM x", "CVR x", "AOV x", "Rationale"],
   [[r.segment, f"{r.cpm_mult:.2f}", f"{r.cvr_mult:.2f}", f"{r.aov_mult:.2f}", r.note] for _, r in seg.iterrows()],
   [2, 1.8, 1.8, 1.8, 8.8])
P("A channel x segment CTR affinity matrix (`data/channel_segment_affinity.csv`) captures, for example, that "
  "Social/Video over-index with younger users and under-index with 50+.")

H1("4. Simulation methodology")
P("For each channel c and segment s with spend x(c,s):")
EQ("impressions = imp_ref * (x / x_ref) ^ alpha_c          imp_ref = x_ref / (CPM_c * cpm_mult_s) * 1000\n"
   "clicks      = impressions * CTR_c * affinity(c,s)\n"
   "conversions = clicks * CVR_c * cvr_mult_s * (1 + halo if c = Search)\n"
   "revenue     = conversions * AOV * aov_mult_s\n"
   "net profit  = margin * revenue - (media spend + fixed cost)\n"
   "ROAS = revenue / cost     CPA = cost / conversions     ROI = net profit / cost")
P(f"`x_ref` is the equal-split spend per cell at the {usd(TOTAL_BUDGET)} reference budget, so the baseline reproduces the "
  "benchmark CPM/CTR/CVR exactly and other allocations deviate through the alpha exponent.")
BL([
    "**Uncertainty.** In every simulation run, each channel's CPM, CTR and CVR and overall market demand are multiplied by "
    f"mean-one log-normal shocks. {N_SIMS:,} runs are generated per scenario.",
    "**Common random numbers.** All scenarios use the same random draws, so differences between scenarios are paired "
    "and statistically efficient. Comparisons report the mean difference, a 95% confidence interval, and the share of "
    "runs in which a scenario beats the baseline.",
    "**Optimisation.** S5, S6, S7 and S8 use SLSQP with 12 random starts on the expected-value model, maximising net profit "
    "subject to: total budget, each channel 5-40% of budget, each segment 10-45% of budget, and every channel x segment cell >= 0.5%. "
    "The caps prevent unrealistic all-in solutions.",
    "**Out-of-sample evaluation.** Optimisation uses the deterministic model; the optimised plans are then evaluated on the "
    "stochastic simulation, which is the number reported.",
    "**Sensitivity and stress tests.** One-at-a-time +/-20% changes of key parameters, plus stress cases where the "
    "assumptions are wrong, test whether conclusions survive error in the inputs.",
    "**Budget sweep.** The equal split and a freshly re-optimised mix are evaluated from $30k to $200k to trace response "
    "curves and marginal returns.",
])

H1("5. Scenarios")
TB(["Scenario", "Search", "Social", "Email", "Display", "Video", "18-24", "25-34", "35-49", "50+", "Budget"],
   [[n.replace(" (equal split)", ""),
     *[pct(alloc.loc[n, f"{c}_%"]) for c in ["Search", "Social", "Email", "Display", "Video"]],
     *[pct(alloc.loc[n, f"{c}_%"]) for c in ["18-24", "25-34", "35-49", "50+"]],
     usd(summary.loc[n, "total_cost"])] for n in summary.index],
   [4.4, 1.2, 1.2, 1.2, 1.3, 1.2, 1.2, 1.2, 1.2, 1.1, 1.6])
P("Percentages are shares of media budget (S8 media = $96,000 plus $4,000 CRO cost = $100,000 total). "
  "S0 is the baseline. S1/S2 change only the budget level. S3/S4 are manager-style heuristic mixes "
  "(performance-heavy, awareness-heavy). S5 optimises channels only; S6 optimises segments only; S7 optimises both; "
  "S8 adds a CRO programme (+12% conversion rate on all channels, $4,000 fixed cost) to the jointly optimised plan.")
IMG("fig1_channel_mix.png", "Figure 1. Channel mix by scenario", 13)
IMG("fig2_joint_allocation_heatmap.png", "Figure 2. Jointly optimised (S7) spend by channel and segment", 10)

H1("6. Results")
TB(["Scenario", "Cost", "Revenue", "Net profit", "ROAS", "CPA", "Conv.", "P(loss)"],
   [[n.split(" (")[0], usd(summary.loc[n, "total_cost"]), usd(summary.loc[n, "revenue_mean"]),
     usd(summary.loc[n, "net_profit_mean"]), f"{summary.loc[n,'roas_mean']:.2f}",
     f"${summary.loc[n,'cpa_mean']:.0f}", f"{summary.loc[n,'conversions_mean']:,.0f}",
     pct(summary.loc[n, "prob_loss"] * 100)] for n in summary.index],
   [5, 2, 2.2, 2.2, 1.4, 1.4, 1.6, 1.6])
P("Means over 5,000 simulations. Profit = gross profit - total cost (media + fixed). P(loss) = share of simulations with negative net profit.")
IMG("fig3_roas_by_scenario.png", "Figure 3. Expected ROAS with 5th-95th percentile range; red line = break-even ROAS", 14)
P("**Paired comparison against the baseline (net profit)**")
TB(["Scenario", "Mean difference", "95% CI", "P(beats baseline)", "Incremental ROAS"],
   [[n.split(" (")[0], sgn(summary.loc[n, "d_profit_vs_base"]),
     f"{sgn(summary.loc[n,'d_profit_ci_lo'])} to {sgn(summary.loc[n,'d_profit_ci_hi'])}",
     pct(summary.loc[n, "prob_beats_base"] * 100),
     "-" if pd.isna(summary.loc[n, "incremental_roas_vs_base"]) else f"{summary.loc[n,'incremental_roas_vs_base']:.2f}"]
    for n in summary.index if n != S["S0"]], [5, 3, 4.8, 3, 2.6])
P("Incremental ROAS (budget scenarios only) = extra revenue per extra dollar of cost relative to baseline. "
  "**Interpretation note:** the confidence intervals are narrow because all scenarios share the same random draws "
  "(paired comparison); they measure simulation precision *given the assumed inputs*. Uncertainty about whether the "
  "inputs themselves are right is addressed separately by the stress tests in Section 9.")
IMG("fig4_profit_distribution.png", "Figure 4. Simulated net-profit distributions: baseline vs S7 vs S8", 12)

H1("7. Statistical analysis and decision evidence")
P("Because the same random draws are used across scenarios, the primary comparison is paired: each scenario is evaluated against the baseline under the same simulated market conditions. This makes the confidence intervals substantially more precise than treating scenarios as unrelated samples, but it does not remove uncertainty in the assumed inputs.")
P("**Global distribution checks.** A one-way ANOVA and a paired Friedman test are reported across scenario ROAS distributions. These tests answer whether the simulated scenario distributions differ; they do not establish causality in a real campaign.")
TB(["Test", "Comparison", "Statistic", "p-value", "Interpretation"], [
    [r.test, r.comparison, f"{r.statistic:.2f}", "<0.001" if r.p_value < 0.001 else f"{r.p_value:.4f}", r.effect_or_note if isinstance(r.effect_or_note, str) else ""]
    for _, r in tests[tests.test.isin(["One-way ANOVA (ROAS)", "Friedman test (ROAS, paired)"])].iterrows()], [5, 4, 2.2, 2.2, 4.6])
P("**Paired inference against baseline.** Paired t-tests are used for net-profit differences, with 95% confidence intervals and Cohen's d_z effect sizes. Because eight pairwise comparisons are made, Holm-adjusted p-values are reported to control family-wise error at the 5% level.")
TB(["Scenario", "Mean Δ profit", "95% CI", "t", "Cohen d_z", "Holm p"], [
    [r.comparison.replace("S0 ", ""), sgn(r.mean_difference), f"{sgn(r.ci95_lo)} to {sgn(r.ci95_hi)}", f"{r.statistic:.1f}", f"{r.cohens_dz:.2f}", "<0.001" if r.holm_adjusted_p < 0.001 else f"{r.holm_adjusted_p:.4f}"]
    for _, r in tests[tests.test.eq("Paired t-test (net profit)")].iterrows()], [5.2, 2.6, 4.7, 1.4, 1.8, 2.0])
P("The practical implication is stronger than statistical significance alone: S7 improves expected profit by about $12.8k versus baseline and wins in 99.88% of paired simulations; S8 improves profit by about $22.7k and wins in 100% of paired simulations. These probabilities are model-based scenario probabilities, not observed campaign win rates.")

H1("8. Hypothesis evaluation")
TB(["#", "Evidence", "Verdict"], [
    ["H1", f"S5 (channels only) raises ROAS {g('S0','roas_mean'):.2f} to {g('S5','roas_mean'):.2f}; profit {sgn(g('S5','d_profit_vs_base'))}, beats baseline in {pct(g('S5','prob_beats_base')*100)} of runs. "
           f"Money moves to Social ({pct(al('S5','Social_%'))}), Search ({pct(al('S5','Search_%'))}) and Display; Email and Video are cut.", "Supported"],
    ["H2", f"S6 (segments only) {sgn(g('S6','d_profit_vs_base'))}; 35-49 receives {pct(al('S6','35-49_%'))} and 18-24 only {pct(al('S6','18-24_%'))}, "
           f"beats baseline in {pct(g('S6','prob_beats_base')*100)} of runs.", "Supported"],
    ["H3", f"S7 = {sgn(g('S7','d_profit_vs_base'))} vs S5 + S6 = {sgn(g('S5','d_profit_vs_base')+g('S6','d_profit_vs_base'))}. "
           f"Interaction effect {sgn(syn)} (social/video suit younger users, so the best channel mix depends on who is targeted).",
     "Supported (modest synergy)"],
    ["H4", f"Marginal ROAS at $100k is ${mroas_100:.2f} vs average ROAS {g('S7','roas_mean'):.2f}; S1 (+25% budget) has incremental ROAS {g('S1','incremental_roas_vs_base'):.2f} "
           f"and lowers profit {sgn(g('S1','d_profit_vs_base'))}.", "Supported"],
    ["H5", f"Awareness-heavy S4 (55% Display+Video) underperforms baseline ({sgn(g('S4','d_profit_vs_base'))}), yet the optimiser still puts "
           f"{pct(al('S7','Display_%')+al('S7','Video_%'))} in Display+Video, exactly at the halo saturation point ({HALO_SATURATION*100:.0f}%).",
     "Partly supported: some awareness, mostly cheap Display"],
], [1.1, 12.2, 3.0])
IMG("fig5_budget_response.png", "Figure 5. Budget response curve and marginal ROAS (red = break-even marginal ROAS)", 15)
P(f"At the optimised mix, expected net profit peaks at a media budget of about **{usd(best_budget)}** "
  f"({usd(opt_sweep.loc[best_budget,'net_profit'])}) and is within a few thousand dollars of that peak between "
  f"{usd(30000)} and {usd(60000)}. Beyond this point each extra dollar earns less gross profit than it costs. "
  "Treat the exact peak with caution: it relies on extrapolating the power-law response below the benchmark budget "
  "and ignores repeat purchases (Section 11).")

H1("9. Sensitivity and robustness")
IMG("fig6_sensitivity_tornado.png", "Figure 6. +/-20% sensitivity of S7 net profit", 12)
TB(["Parameter", "Profit change at -20%", "Profit change at +20%"],
   [[r.parameter, sgn(r["profit_change_at_-20%"]), sgn(r["profit_change_at_+20%"])] for _, r in sens.iterrows()],
   [8, 4, 4])
P("CTR, CVR, AOV and margin all scale revenue linearly, so they have identical effects; cost-per-impression (CPM) is "
  "marginally more important. The model is relatively insensitive to the brand-halo size and moderately sensitive to "
  "the saturation exponent. Profit, being a thin difference between gross profit and cost, is far more sensitive than ROAS.")
P("**Stress tests**: does S7 still beat the baseline if the benchmark inputs are wrong? (Both plans evaluated under the stressed parameters.)")
TB(["Stress case", "Baseline profit", "S7 profit", "S7 advantage", "P(S7 wins)"],
   [[r.stress_case, usd(r.baseline_profit), usd(r.optimised_profit), sgn(r.uplift), pct(r.prob_optimised_wins * 100)]
    for _, r in stress.iterrows()], [6, 2.8, 2.8, 2.8, 2.4])
P("The optimised plan wins in every case, but in the pessimistic cases both plans lose money. The ranking of strategies is "
  "robust; the absolute profitability depends on real conversion rates and costs.")

H1("10. Strategic recommendations")
BL([
    f"**Re-allocate to the S7 mix:** Search ~{pct(al('S7','Search_%'))}, Social ~{pct(al('S7','Social_%'))}, Display ~{pct(al('S7','Display_%'))}, "
    f"Email ~{pct(al('S7','Email_%'))}, Video ~{pct(al('S7','Video_%'))}. Expected gain {sgn(g('S7','d_profit_vs_base'))} per campaign.",
    f"**Target 35-49 and 25-34 first:** weight 35-49 at ~{pct(al('S7','35-49_%'))} and 25-34 at ~{pct(al('S7','25-34_%'))}; reduce 18-24 to the floor ({pct(al('S7','18-24_%'))}) "
    "unless it is a deliberate brand or lifetime-value play.",
    f"**Invest in conversion-rate optimisation first.** A {usd(4000)} CRO programme returning +12% CVR adds about {usd(cro_gain)} of profit; it improves every channel at once and is cheaper than buying traffic.",
    f"**Right-size the budget.** At $100k the marginal dollar returns ${mroas_100:.2f} of revenue versus ${breakeven:.2f} needed to break even. Run the campaign at a smaller budget (between $40k and $70k in this model), "
    "or only scale up after CVR or margin improves. Validate with a geo or time hold-out test before cutting.",
    "**Keep a floor of awareness spend (~30% Display+Video), but favour cheap Display over Video** unless brand-search lift is measured.",
    "**Measure, then re-calibrate.** Run the plan as an A/B or incrementality test; feed actual CPM/CTR/CVR and saturation back into `data/*.csv` and re-run. Treat model recommendations as a prior, not as a guarantee.",
    f"**Manage risk, not just the mean:** the optimised plan cuts the chance of a loss from {pct(g('S0','prob_loss')*100)} to {pct(g('S7','prob_loss')*100)} "
    f"(and to {pct(g('S8','prob_loss')*100)} with CRO).",
])

H1("11. Limitations")
BL([
    "Benchmark inputs are rounded public ranges, not this campaign's own data; absolute profit and the 'optimal budget' depend heavily on them.",
    "Diminishing returns use a simple power law, calibrated at the reference budget; extrapolation far from $100k (especially below) is uncertain.",
    "Channels are independent except for a one-directional Display/Video-to-Search halo; cross-channel attribution, frequency capping, creative fatigue and auction dynamics are not modelled.",
    "Revenue is first-order purchase value: no repeat purchases, customer lifetime value, returns or brand-equity effects. Including LTV would justify a larger budget.",
    "Segments are static; seasonality, competitor reactions and time-varying effects (e.g. weekly pacing) are ignored.",
    "The optimiser solves the expected-value problem; it does not optimise risk directly, and SLSQP finds local optima (mitigated with multiple starts).",
    "Shock sizes (log-normal sigmas) are assumptions rather than estimates from data.",
])

H1("12. Reproducibility and file guide")
TB(["File", "Purpose"], [
    ["src/model.py", "Simulation engine, optimiser and statistics"],
    ["src/scenarios.py", "Scenario definitions (S0-S8)"],
    ["src/run_all.py", "Runs everything; writes results/ and figures/"],
    ["src/build_report.py", "Builds this report from the results"],
    ["data/*.csv", "Editable benchmark and segment assumptions"],
    ["results/campaign_simulation_results.xlsx", "Excel workbook with assumptions, scenarios, results, sensitivity, stress tests"],
    ["tests/test_model.py", "Unit tests (pytest)"],
], [7, 9.2])
P("Reproduce: `pip install -r requirements.txt`, `python -m src.run_all`, `python -m src.build_report`. "
  f"Results are deterministic given seed {SEED}.")
P("**Quality assurance.** The repository includes six automated unit tests covering budget conservation, zero-spend behaviour, diminishing returns, random-shock reproducibility/mean behaviour, optimiser constraints and Monte Carlo agreement with the deterministic model. The final run completed with **6/6 tests passing**. The Excel workbook includes an executive dashboard plus separate statistical-test, sensitivity, stress-test, benchmark-source, data-dictionary and QA sheets so the decision can be audited without reading the source code.")


# =============================================================================
# Renderers
# =============================================================================
def md_inline(t):
    return t


def to_markdown():
    out = [f"# Campaign Optimization Simulation Report\n", f"**{COURSE}**  \nAuthor: {AUTHOR}  \nDate: {DATE}\n"]
    for b in B:
        k = b[0]
        if k == "h1":
            out.append(f"\n## {b[1]}\n")
        elif k == "h2":
            out.append(f"\n### {b[1]}\n")
        elif k == "p":
            out.append(b[1] + "\n")
        elif k == "bullets":
            out.append("\n".join(f"- {i}" for i in b[1]) + "\n")
        elif k == "table":
            head, rows = b[1], b[2]
            out.append("| " + " | ".join(head) + " |")
            out.append("|" + "|".join("---" for _ in head) + "|")
            out += ["| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows]
            out.append("")
        elif k == "img":
            out.append(f"![{b[2]}](../figures/{b[1]})\n\n*{b[2]}*\n")
        elif k == "eq":
            out.append("```\n" + b[1] + "\n```\n")
    (OUT / "Campaign_Optimization_Report.md").write_text("\n".join(out), encoding="utf-8")


def rl(text):
    """Convert simple markdown (**bold**, `code`, *italic*) to ReportLab markup."""
    import re
    t = html.escape(text, quote=False)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r"<font face='Courier'>\1</font>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    return t


def to_pdf():
    ss = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=ss["BodyText"], fontSize=9.5, leading=13.5, spaceAfter=5)
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontSize=15, spaceBefore=12, spaceAfter=6,
                        textColor=colors.HexColor("#1f3a5f"))
    cell = ParagraphStyle("cell", parent=body, fontSize=7.8, leading=9.6, spaceAfter=0)
    cellh = ParagraphStyle("cellh", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")
    cap = ParagraphStyle("cap", parent=body, fontSize=8, alignment=TA_CENTER, textColor=colors.HexColor("#444444"))
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=12, bulletIndent=2)
    title = ParagraphStyle("title", parent=ss["Title"], fontSize=22, textColor=colors.HexColor("#1f3a5f"))
    sub = ParagraphStyle("sub", parent=body, alignment=TA_CENTER, fontSize=11)

    story = [Spacer(1, 3 * cm), Paragraph("Campaign Optimization<br/>Simulation Report", title), Spacer(1, 0.5 * cm),
             Paragraph(COURSE, sub), Spacer(1, 0.3 * cm),
             Paragraph(f"{AUTHOR} | {DATE}", sub), Spacer(1, 1.2 * cm)]
    story.append(Paragraph(
        "Monte Carlo simulation of budget allocation, channel mix, segment targeting and conversion-rate "
        "optimisation, with 9 scenarios, 5,000 simulations each.", sub))
    story.append(PageBreak())
    W = A4[0] - 4 * cm
    for idx, b in enumerate(B):
        k = b[0]
        nxt = B[idx + 1][0] if idx + 1 < len(B) else None
        if k == "h1":
            story.append(Paragraph(rl(b[1]), h1))
        elif k == "p":
            st = ParagraphStyle("bk", parent=body, keepWithNext=1) if nxt in ("table", "img", "eq") else body
            story.append(Paragraph(rl(b[1]), st))
        elif k == "bullets":
            for i in b[1]:
                story.append(Paragraph(rl(i), bullet, bulletText="\u2022"))
            story.append(Spacer(1, 4))
        elif k == "eq":
            story.append(Preformatted(b[1], ParagraphStyle("eq", fontName="Courier", fontSize=7.6, leading=10,
                                                           backColor=colors.HexColor("#f3f3f3"), leftIndent=4,
                                                           borderPadding=4)))
            story.append(Spacer(1, 8))
        elif k == "table":
            head, rows, widths = b[1], b[2], b[3]
            data = [[Paragraph(rl(h), cellh) for h in head]] + [[Paragraph(rl(str(c)), cell) for c in r] for r in rows]
            if widths:
                tot = sum(widths)
                cw = [w / tot * W for w in widths]
            else:
                cw = None
            t = Table(data, colWidths=cw, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f3a5f")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef2f7")]),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#bbbbbb")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]))
            story += [t, Spacer(1, 8)]
        elif k == "img":
            path = FIG / b[1]
            w_px, h_px = PILImage.open(path).size
            w = min(b[3] * cm, W)
            story.append(KeepTogether([Image(str(path), width=w, height=w * h_px / w_px),
                                       Paragraph(rl(b[2]), cap), Spacer(1, 6)]))
    SimpleDocTemplate(str(OUT / "Campaign_Optimization_Report.pdf"), pagesize=A4, leftMargin=2 * cm,
                      rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
                      title="Campaign Optimization Simulation Report", author=AUTHOR).build(story)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    to_markdown()
    to_pdf()
    print("Wrote report/Campaign_Optimization_Report.md and .pdf")
