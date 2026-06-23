"""
data_loader.py
---------------
Loads the production-planning dataset from CSV files into plain Python
dicts that the model builder consumes directly. Keeping this separate from
model.py means swapping in a database or an ERP export later only touches
this one file.
"""

import os
from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd


@dataclass
class PlanningData:
    products: List[str]
    machines: List[str]
    worker_types: List[str]
    periods: List[int]
    machine_worker_type: Dict[str, str]
    compatibility: List[Tuple[str, str]]                 # (product, machine) pairs allowed
    proc_time: Dict[Tuple[str, str], float]               # hours/unit
    prod_cost: Dict[Tuple[str, str], float]               # $/unit
    holding_cost: Dict[str, float]                        # $/unit/period
    demand: Dict[Tuple[str, int], float]
    machine_hours_available: Dict[Tuple[str, int], float]
    worker_hours_available: Dict[Tuple[str, int], float]
    labor_cost: Dict[str, float]                          # $/hour, by worker type


def load_planning_data(data_dir: str) -> PlanningData:
    products_df = pd.read_csv(os.path.join(data_dir, "products.csv"))
    machines_df = pd.read_csv(os.path.join(data_dir, "machines.csv"))
    compat_df = pd.read_csv(os.path.join(data_dir, "product_machine_compatibility.csv"))
    demand_df = pd.read_csv(os.path.join(data_dir, "demand.csv"))
    capacity_df = pd.read_csv(os.path.join(data_dir, "machine_capacity.csv"))
    worker_df = pd.read_csv(os.path.join(data_dir, "worker_availability.csv"))

    products = sorted(products_df["product_id"].unique().tolist())
    machines = sorted(machines_df["machine_id"].unique().tolist())
    worker_types = sorted(worker_df["worker_type"].unique().tolist())
    periods = sorted(demand_df["period"].unique().tolist())

    machine_worker_type = dict(zip(machines_df["machine_id"], machines_df["worker_type"]))

    compatibility = list(zip(compat_df["product_id"], compat_df["machine_id"]))
    proc_time = {
        (r.product_id, r.machine_id): float(r.proc_time_hours_per_unit)
        for r in compat_df.itertuples()
    }
    prod_cost = {
        (r.product_id, r.machine_id): float(r.prod_cost_per_unit)
        for r in compat_df.itertuples()
    }

    holding_cost = dict(zip(products_df["product_id"], products_df["holding_cost_per_unit_period"]))

    demand = {(r.product_id, int(r.period)): float(r.demand_units) for r in demand_df.itertuples()}

    machine_hours_available = {
        (r.machine_id, int(r.period)): float(r.hours_available) for r in capacity_df.itertuples()
    }

    worker_hours_available = {
        (r.worker_type, int(r.period)): float(r.hours_available) for r in worker_df.itertuples()
    }

    labor_cost = (
        worker_df[["worker_type", "cost_per_hour"]]
        .drop_duplicates()
        .set_index("worker_type")["cost_per_hour"]
        .to_dict()
    )

    return PlanningData(
        products=products,
        machines=machines,
        worker_types=worker_types,
        periods=periods,
        machine_worker_type=machine_worker_type,
        compatibility=compatibility,
        proc_time=proc_time,
        prod_cost=prod_cost,
        holding_cost=holding_cost,
        demand=demand,
        machine_hours_available=machine_hours_available,
        worker_hours_available=worker_hours_available,
        labor_cost=labor_cost,
    )
