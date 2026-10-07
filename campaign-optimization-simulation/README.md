# Campaign Optimization Simulation — Week 4

A transparent Monte Carlo decision model for a **$100,000, 90-day e-commerce campaign** across five channels and four customer segments. The project evaluates budget level, channel mix, segment targeting, conversion-rate optimization (CRO), diminishing returns, uncertainty, sensitivity, stress tests and constrained optimization.

## Executive result

| Scenario | Expected net profit | ROAS | Probability of loss |
|---|---:|---:|---:|
| S0 Baseline | -$973 | 1.80x | 55% |
| S7 Jointly optimized | **+$11,842** | **2.03x** | **20%** |
| S8 Joint + CRO | **+$21,766** | **2.21x** | **6%** |

**Recommendation:** use S7 as the media-allocation hypothesis and test S8 as the preferred growth strategy if the $4,000 CRO programme can credibly deliver the assumed +12% conversion-rate improvement. Do not treat the simulated profit as a forecast; it is a model-based scenario result.

## What makes this submission strong

- 9 clearly defined scenarios, including budget tests, heuristic mixes, channel-only optimization, segment-only optimization, joint optimization and CRO.
- 5,000 Monte Carlo runs per scenario using common random numbers for paired comparisons.
- SLSQP constrained optimization with channel, segment and cell-level guardrails.
- 95% confidence intervals, paired t-tests, Cohen's d_z, Holm correction, global ANOVA/Friedman diagnostics.
- One-at-a-time sensitivity analysis and seven stress cases.
- Budget response curve and marginal ROAS analysis.
- Six automated unit tests; latest run: **6/6 passing**.
- Excel workbook with an executive dashboard, assumptions, allocation matrices, results, statistical tests, sensitivity, stress tests, budget sweep and benchmark-source register.
- PDF report and reproducible Python source.

## Benchmark provenance

Public benchmarks are used as **external anchors**, not as claims about a real campaign. Current anchors include WordStream's 2026 Google Ads benchmark, WordStream's 2025 Facebook lead benchmark, and Mailchimp's email benchmarks. Search/Social/Email model inputs are deliberately conservative and Display/Video inputs are explicitly illustrative where no single source is treated as authoritative. See `data/source_register.csv` and the Excel `Benchmark_Sources` sheet.

## Repository structure

```text
.
├── README.md
├── requirements.txt
├── LICENSE
├── data/
│   ├── channel_benchmarks.csv
│   ├── channel_segment_affinity.csv
│   ├── segment_multipliers.csv
│   └── source_register.csv
├── src/
│   ├── model.py
│   ├── scenarios.py
│   ├── upgrade_stats.py
│   ├── run_all.py
│   └── build_report.py
├── tests/test_model.py
├── results/
│   ├── campaign_simulation_results.xlsx
│   ├── scenario_summary.csv
│   ├── scenario_allocation.csv
│   ├── scenario_allocation_cells.csv
│   ├── statistical_tests.csv
│   ├── sensitivity.csv
│   ├── stress_tests.csv
│   └── budget_sweep.csv
├── figures/
└── report/
    ├── Campaign_Optimization_Report.pdf
    └── Campaign_Optimization_Report.md
```

## Reproduce

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.run_all
python -m src.build_report
pytest -q
```

The simulation uses seed **42**, so results are deterministic for the supplied assumptions. `run_all.py` regenerates all result files and figures. The current workbook can also be inspected directly without running Python.

## Model logic

For each channel/segment cell, spend is converted to impressions using CPM and a power-law diminishing-returns exponent. Impressions become clicks through CTR and channel-segment affinity; clicks become conversions through CVR and segment multipliers; conversions become revenue through AOV and segment AOV multipliers. Display/Video can create a capped Search conversion halo. Net profit is gross margin × revenue minus media and fixed CRO cost.

## Important limitations

This is a **synthetic decision model**, not observed campaign data. The largest risks are benchmark mismatch, simplified saturation, first-purchase-only revenue, missing lifetime value, simplified attribution, no auction dynamics, no seasonality, and uncertainty parameters that are assumed rather than estimated from account history. The recommended next step is to replace the benchmark assumptions with first-party CPM/CTR/CVR/AOV/margin data and rerun the model.
