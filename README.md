# Week 4 – Campaign Optimization Simulation

## Simulation of Campaign Optimization Strategies

A data-driven marketing analytics project that uses **Monte Carlo simulation, constrained optimization, scenario analysis, statistical testing, and sensitivity analysis** to evaluate marketing campaign strategies.

The project investigates how **budget allocation, channel mix, customer segmentation, conversion-rate optimization (CRO), and diminishing returns** affect campaign revenue, ROAS, CPA, ROI, and net profit.

> **Important:** The results in this project are simulated results based on illustrative benchmark assumptions. They are not actual campaign performance or guaranteed business outcomes.

---

## 📌 Project Objective

The objective of this project is to simulate and evaluate different marketing campaign optimization strategies and identify which strategy provides the strongest financial performance under uncertainty.

The simulation evaluates:

- Budget allocation
- Marketing channel mix
- Customer segment targeting
- Conversion-rate optimization
- Diminishing returns
- Revenue and conversion performance
- ROAS and CPA
- Net profit
- Probability of loss
- Sensitivity to model assumptions
- Robustness under adverse conditions

---

## 🎯 Business Problem

Marketing teams must decide:

- How much should be spent?
- Which channels should receive more budget?
- Which customer segments should be prioritized?
- Should the company invest in CRO instead of buying additional traffic?
- How does diminishing return affect additional spending?
- How robust is an optimization strategy if benchmark assumptions are wrong?

This project uses simulation and optimization to answer these questions before making a real-world budget decision.

---

## 🔬 Methodology

The project uses a **Monte Carlo simulation framework** with:

- **9 scenarios**
- **5,000 simulations per scenario**
- Common random numbers across scenarios
- Log-normal uncertainty
- Channel-level CPM, CTR and CVR assumptions
- Customer segment multipliers
- Channel × segment affinity
- Diminishing-return functions
- Search brand-halo effects
- Constrained numerical optimization
- Statistical comparison
- Sensitivity analysis
- Stress testing

### Core simulation flow

```text
Benchmark Inputs
       ↓
Channel & Segment Assumptions
       ↓
Scenario Allocation
       ↓
Monte Carlo Simulation
       ↓
Revenue / Conversion / Cost
       ↓
ROAS / CPA / ROI / Net Profit
       ↓
Statistical Analysis
       ↓
Sensitivity & Stress Tests
       ↓
Strategic Recommendations
