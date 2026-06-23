"""
scenario.py
------------
Runs the production planning model across a grid of "what-if" scenarios by
scaling demand and worker availability, and collects the resulting cost,
fill-rate and utilization metrics into a single tidy DataFrame.

This is the part of the project that answers questions like:
    "What happens to cost and on-time delivery if demand jumps 40% during
     a 20% workforce shortage?"
"""

import copy
from typing import Iterable, List

import pandas as pd

from .data_loader import PlanningData
from .model import build_and_solve


def _scale_demand(data: PlanningData, factor: float) -> PlanningData:
    new_data = copy.deepcopy(data)
    new_data.demand = {k: v * factor for k, v in new_data.demand.items()}
    return new_data


def _scale_workforce(data: PlanningData, factor: float) -> PlanningData:
    new_data = copy.deepcopy(data)
    new_data.worker_hours_available = {k: v * factor for k, v in new_data.worker_hours_available.items()}
    return new_data


def run_scenarios(
    data: PlanningData,
    demand_multipliers: Iterable[float] = (0.8, 1.0, 1.2, 1.4, 1.6),
    workforce_multipliers: Iterable[float] = (0.7, 0.85, 1.0),
) -> pd.DataFrame:
    rows: List[dict] = []
    for dm in demand_multipliers:
        for wm in workforce_multipliers:
            scenario_data = _scale_workforce(_scale_demand(data, dm), wm)
            out = build_and_solve(scenario_data)

            total_demand = sum(scenario_data.demand.values())
            total_shortfall = out.shortfall["units"].sum() if out.success else float("nan")
            fill_rate = 1 - (total_shortfall / total_demand) if total_demand > 0 else None

            avg_machine_util = out.machine_usage["utilization"].mean() if out.success else float("nan")
            avg_labor_util = out.labor_usage["utilization"].mean() if out.success else float("nan")

            rows.append({
                "demand_multiplier": dm,
                "workforce_multiplier": wm,
                "success": out.success,
                "total_cost": out.total_cost,
                "production_cost": out.production_cost,
                "labor_cost": out.labor_cost_total,
                "holding_cost": out.holding_cost_total,
                "shortfall_cost": out.shortfall_cost,
                "total_demand_units": total_demand,
                "shortfall_units": total_shortfall,
                "fill_rate": fill_rate,
                "avg_machine_utilization": avg_machine_util,
                "avg_labor_utilization": avg_labor_util,
            })

    return pd.DataFrame(rows)
