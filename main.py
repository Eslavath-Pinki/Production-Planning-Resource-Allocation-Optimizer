"""
main.py
--------
CLI entry point.

Usage:
    python main.py

Solves the baseline production plan, prints a summary to the console,
runs the demand/workforce scenario grid, and writes all charts + a CSV
report to outputs/.
"""

import os

from src.data_loader import load_planning_data
from src.model import build_and_solve
from src.scenario import run_scenarios
from src import visualize as viz

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs")


def main():
    print("Loading planning data...")
    data = load_planning_data(DATA_DIR)
    print(f"  {len(data.products)} products, {len(data.machines)} machines, "
          f"{len(data.worker_types)} worker types, {len(data.periods)} periods")

    print("\nSolving baseline production plan...")
    out = build_and_solve(data)
    if not out.success:
        print(f"  Solve failed: {out.status}")
        return

    print(f"  Status: {out.status}")
    print(f"  Total cost:        ${out.total_cost:,.2f}")
    print(f"    Production cost: ${out.production_cost:,.2f}")
    print(f"    Labor cost:      ${out.labor_cost_total:,.2f}")
    print(f"    Holding cost:    ${out.holding_cost_total:,.2f}")
    print(f"    Shortfall cost:  ${out.shortfall_cost:,.2f}")

    total_demand = sum(data.demand.values())
    total_shortfall = out.shortfall["units"].sum()
    fill_rate = 1 - total_shortfall / total_demand
    print(f"  Demand fill rate:  {fill_rate:.1%}")
    print(f"  Avg machine utilization: {out.machine_usage['utilization'].mean():.1%}")
    print(f"  Avg labor utilization:   {out.labor_usage['utilization'].mean():.1%}")

    print("\nGenerating baseline charts...")
    viz.plot_utilization_heatmap(out.machine_usage, "machine", OUTPUTS_DIR,
                                  "machine_utilization.png", "Machine Utilization by Period")
    viz.plot_utilization_heatmap(out.labor_usage, "worker_type", OUTPUTS_DIR,
                                  "labor_utilization.png", "Workforce Utilization by Period")
    viz.plot_production_schedule(out.production, OUTPUTS_DIR, "production_schedule.png")
    viz.plot_cost_breakdown(out, OUTPUTS_DIR, "cost_breakdown.png")

    out.production.to_csv(os.path.join(OUTPUTS_DIR, "baseline_production_schedule.csv"), index=False)
    out.machine_usage.to_csv(os.path.join(OUTPUTS_DIR, "baseline_machine_utilization.csv"), index=False)
    out.labor_usage.to_csv(os.path.join(OUTPUTS_DIR, "baseline_labor_utilization.csv"), index=False)

    print("\nRunning scenario analysis (demand x workforce grid)...")
    scenario_df = run_scenarios(data)
    scenario_df.to_csv(os.path.join(OUTPUTS_DIR, "scenario_results.csv"), index=False)
    print(scenario_df[["demand_multiplier", "workforce_multiplier", "fill_rate", "total_cost"]]
          .round(3).to_string(index=False))

    viz.plot_scenario_metric(scenario_df, "fill_rate", "Demand fill rate", OUTPUTS_DIR,
                              "scenario_fill_rate.png", "Demand Fill Rate vs. Demand & Workforce Stress")
    viz.plot_scenario_metric(scenario_df, "total_cost", "Total cost ($)", OUTPUTS_DIR,
                              "scenario_total_cost.png", "Total Cost vs. Demand & Workforce Stress")

    print(f"\nAll charts and CSV reports written to: {OUTPUTS_DIR}")


if __name__ == "__main__":
    main()
