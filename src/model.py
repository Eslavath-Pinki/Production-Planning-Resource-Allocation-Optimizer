"""
model.py
---------
Builds and solves the multi-period, multi-product production planning LP.

Decision variables
  x[p,m,t]   units of product p produced on machine m in period t
  I[p,t]     ending inventory of product p in period t
  L[k,t]     labor hours of worker type k actually used in period t
  s[p,t]     unmet demand ("shortfall") of product p in period t

Objective (minimize)
  sum  prod_cost[p,m]   * x[p,m,t]      (variable production cost)
+ sum  labor_cost[k]    * L[k,t]        (labor cost)
+ sum  holding_cost[p]  * I[p,t]        (inventory holding cost)
+ sum  SHORTFALL_PENALTY * s[p,t]       (penalty for unmet demand)

Constraints
  (1) Inventory balance   I[p,t-1] + sum_m x[p,m,t] + s[p,t] - I[p,t] = demand[p,t]
  (2) Machine capacity    sum_p proc_time[p,m] * x[p,m,t] <= machine_hours_available[m,t]
  (3) Labor requirement   sum_{m: type(m)=k} sum_p proc_time[p,m]*x[p,m,t] <= L[k,t]
  (4) Labor availability  L[k,t] <= worker_hours_available[k,t]   (enforced as a variable bound)
  (5) Non-negativity      x, I, L, s >= 0

The shortfall variable keeps the model feasible even in stress scenarios
(e.g. a demand spike that exceeds total capacity). Instead of the solver
failing, it reports exactly how much demand could not be met and at what
cost -- this is what makes the scenario analysis in scenario.py meaningful.
"""

from dataclasses import dataclass
from typing import Dict

import pandas as pd

from .data_loader import PlanningData
from .lp_builder import LPModel

SHORTFALL_PENALTY = 1000.0  # $/unit; deliberately >> any real production cost


@dataclass
class SolveOutput:
    success: bool
    status: str
    total_cost: float
    production_cost: float
    labor_cost_total: float
    holding_cost_total: float
    shortfall_cost: float
    production: pd.DataFrame      # product, machine, period, units
    inventory: pd.DataFrame       # product, period, units
    labor_usage: pd.DataFrame     # worker_type, period, hours_used, hours_available, utilization
    machine_usage: pd.DataFrame   # machine, period, hours_used, hours_available, utilization
    shortfall: pd.DataFrame       # product, period, units


def _var(prefix: str, *idx) -> str:
    return prefix + "_" + "_".join(str(i) for i in idx)


def build_and_solve(data: PlanningData) -> SolveOutput:
    lp = LPModel(sense="min")

    # ---- variables ----------------------------------------------------
    for (p, m) in data.compatibility:
        for t in data.periods:
            lp.add_var(_var("x", p, m, t), lb=0)

    for p in data.products:
        for t in data.periods:
            lp.add_var(_var("I", p, t), lb=0)
            lp.add_var(_var("s", p, t), lb=0)

    for k in data.worker_types:
        for t in data.periods:
            avail = data.worker_hours_available.get((k, t), 0.0)
            lp.add_var(_var("L", k, t), lb=0, ub=avail)

    # ---- objective ------------------------------------------------------
    obj: Dict[str, float] = {}
    for (p, m) in data.compatibility:
        cost = data.prod_cost[(p, m)]
        for t in data.periods:
            obj[_var("x", p, m, t)] = cost
    for k in data.worker_types:
        for t in data.periods:
            obj[_var("L", k, t)] = data.labor_cost.get(k, 0.0)
    for p in data.products:
        hc = data.holding_cost.get(p, 0.0)
        for t in data.periods:
            obj[_var("I", p, t)] = hc
            obj[_var("s", p, t)] = SHORTFALL_PENALTY
    lp.set_objective(obj)

    machines_by_product: Dict[str, list] = {}
    for (p, m) in data.compatibility:
        machines_by_product.setdefault(p, []).append(m)

    products_by_machine: Dict[str, list] = {}
    for (p, m) in data.compatibility:
        products_by_machine.setdefault(m, []).append(p)

    machines_by_worker_type: Dict[str, list] = {}
    for m, k in data.machine_worker_type.items():
        machines_by_worker_type.setdefault(k, []).append(m)

    # ---- constraints ------------------------------------------------------

    # (1) inventory balance
    for p in data.products:
        prev_I = None
        for t in data.periods:
            coeffs = {_var("I", p, t): -1.0, _var("s", p, t): 1.0}
            if prev_I is not None:
                coeffs[prev_I] = 1.0
            for m in machines_by_product.get(p, []):
                coeffs[_var("x", p, m, t)] = 1.0
            demand_pt = data.demand.get((p, t), 0.0)
            lp.add_constraint(coeffs, "==", demand_pt, name=f"inv_balance_{p}_{t}")
            prev_I = _var("I", p, t)

    # (2) machine capacity
    for m in data.machines:
        for t in data.periods:
            coeffs = {
                _var("x", p, m, t): data.proc_time[(p, m)]
                for p in products_by_machine.get(m, [])
            }
            if not coeffs:
                continue
            cap = data.machine_hours_available.get((m, t), 0.0)
            lp.add_constraint(coeffs, "<=", cap, name=f"machine_cap_{m}_{t}")

    # (3) labor requirement (machine-hours run must be covered by labor-hours of the matching type)
    for k in data.worker_types:
        for t in data.periods:
            coeffs: Dict[str, float] = {}
            for m in machines_by_worker_type.get(k, []):
                for p in products_by_machine.get(m, []):
                    key = _var("x", p, m, t)
                    coeffs[key] = coeffs.get(key, 0.0) + data.proc_time[(p, m)]
            coeffs[_var("L", k, t)] = -1.0
            lp.add_constraint(coeffs, "<=", 0.0, name=f"labor_link_{k}_{t}")

    # (4) labor availability is enforced via the variable upper bound set above

    # ---- solve --------------------------------------------------------------
    result = lp.solve()
    if not result.success:
        empty = pd.DataFrame()
        return SolveOutput(False, result.status, float("nan"), float("nan"),
                            float("nan"), float("nan"), float("nan"),
                            empty, empty, empty, empty, empty)

    v = result.values

    # ---- unpack into tidy dataframes -----------------------------------------
    prod_rows, production_cost = [], 0.0
    for (p, m) in data.compatibility:
        for t in data.periods:
            units = v[_var("x", p, m, t)]
            if units > 1e-6:
                prod_rows.append({"product": p, "machine": m, "period": t, "units": units})
            production_cost += units * data.prod_cost[(p, m)]
    production = pd.DataFrame(prod_rows)

    inv_rows = []
    holding_cost_total = 0.0
    for p in data.products:
        for t in data.periods:
            units = v[_var("I", p, t)]
            inv_rows.append({"product": p, "period": t, "units": units})
            holding_cost_total += units * data.holding_cost.get(p, 0.0)
    inventory = pd.DataFrame(inv_rows)

    shortfall_rows = []
    shortfall_cost = 0.0
    for p in data.products:
        for t in data.periods:
            units = v[_var("s", p, t)]
            shortfall_rows.append({"product": p, "period": t, "units": units})
            shortfall_cost += units * SHORTFALL_PENALTY
    shortfall = pd.DataFrame(shortfall_rows)

    labor_rows = []
    labor_cost_total = 0.0
    for k in data.worker_types:
        for t in data.periods:
            used = v[_var("L", k, t)]
            avail = data.worker_hours_available.get((k, t), 0.0)
            labor_rows.append({
                "worker_type": k, "period": t, "hours_used": used,
                "hours_available": avail,
                "utilization": (used / avail) if avail > 1e-9 else 0.0,
            })
            labor_cost_total += used * data.labor_cost.get(k, 0.0)
    labor_usage = pd.DataFrame(labor_rows)

    machine_rows = []
    for m in data.machines:
        for t in data.periods:
            used = sum(
                v[_var("x", p, m, t)] * data.proc_time[(p, m)]
                for p in products_by_machine.get(m, [])
            )
            avail = data.machine_hours_available.get((m, t), 0.0)
            machine_rows.append({
                "machine": m, "period": t, "hours_used": used,
                "hours_available": avail,
                "utilization": (used / avail) if avail > 1e-9 else 0.0,
            })
    machine_usage = pd.DataFrame(machine_rows)

    total_cost = production_cost + labor_cost_total + holding_cost_total + shortfall_cost

    return SolveOutput(
        success=True,
        status=result.status,
        total_cost=total_cost,
        production_cost=production_cost,
        labor_cost_total=labor_cost_total,
        holding_cost_total=holding_cost_total,
        shortfall_cost=shortfall_cost,
        production=production,
        inventory=inventory,
        labor_usage=labor_usage,
        machine_usage=machine_usage,
        shortfall=shortfall,
    )
