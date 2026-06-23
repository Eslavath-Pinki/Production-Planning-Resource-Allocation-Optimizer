"""
generate_sample_data.py
------------------------
Generates a reproducible synthetic dataset for the production planning
optimizer: product-machine compatibility & costs, weekly demand, machine
capacity calendar (with a maintenance dip), and worker availability.

Run once with:  python scripts/generate_sample_data.py
The committed CSVs in data/ are the output of this script with SEED=42,
so anyone cloning the repo can reproduce them exactly.
"""

import csv
import os
import random

SEED = 42
N_PERIODS = 8  # 8 weekly planning periods
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

random.seed(SEED)

# ---------------------------------------------------------------------------
# Product <-> machine compatibility, processing time (hr/unit), cost ($/unit)
# ---------------------------------------------------------------------------
COMPAT = [
    # product, machine, proc_time_hours_per_unit, prod_cost_per_unit
    ("P1", "M1", 0.50, 12.0),
    ("P1", "M2", 0.60, 11.0),
    ("P2", "M3", 0.30, 8.0),
    ("P2", "M4", 0.35, 7.5),
    ("P3", "M1", 0.40, 10.0),
    ("P3", "M3", 0.45, 9.0),
    ("P4", "M4", 0.25, 6.0),
    ("P4", "M5", 0.20, 5.5),
]

# ---------------------------------------------------------------------------
# Weekly demand: base level + mild trend + noise, per product
# ---------------------------------------------------------------------------
DEMAND_BASE = {"P1": 120, "P2": 200, "P3": 150, "P4": 260}
DEMAND_TREND = {"P1": 4, "P2": 6, "P3": -2, "P4": 10}  # units/period drift


def gen_demand():
    rows = []
    for p, base in DEMAND_BASE.items():
        for t in range(1, N_PERIODS + 1):
            trend = DEMAND_TREND[p] * (t - 1)
            noise = random.randint(-15, 15)
            demand = max(0, round(base + trend + noise))
            rows.append((p, t, demand))
    return rows


# ---------------------------------------------------------------------------
# Machine capacity calendar: base hours from machines.csv, with a scheduled
# maintenance dip on M2 in period 5 and a minor random fluctuation elsewhere.
# ---------------------------------------------------------------------------
MACHINE_BASE_HOURS = {"M1": 80, "M2": 80, "M3": 96, "M4": 96, "M5": 60}


def gen_capacity():
    rows = []
    for m, base in MACHINE_BASE_HOURS.items():
        for t in range(1, N_PERIODS + 1):
            hours = base
            if m == "M2" and t == 5:
                hours = base * 0.4  # scheduled maintenance week
            else:
                hours = base * random.uniform(0.95, 1.0)
            rows.append((m, t, round(hours, 1)))
    return rows


# ---------------------------------------------------------------------------
# Worker availability: hours per worker-type per period, plus hourly cost.
# A one-period staffing shortfall is injected for "Skilled" workers (period 6)
# to make the scenario analysis section meaningful.
# ---------------------------------------------------------------------------
WORKER_BASE_HOURS = {"Skilled": 165, "General": 230}
WORKER_COST = {"Skilled": 28.0, "General": 18.0}


def gen_worker_availability():
    rows = []
    for k, base in WORKER_BASE_HOURS.items():
        for t in range(1, N_PERIODS + 1):
            hours = base
            if k == "Skilled" and t == 6:
                hours = base * 0.6  # two technicians out that week
            rows.append((k, t, round(hours, 1), WORKER_COST[k]))
    return rows


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)

    write_csv(
        os.path.join(OUT_DIR, "product_machine_compatibility.csv"),
        ["product_id", "machine_id", "proc_time_hours_per_unit", "prod_cost_per_unit"],
        COMPAT,
    )
    write_csv(
        os.path.join(OUT_DIR, "demand.csv"),
        ["product_id", "period", "demand_units"],
        gen_demand(),
    )
    write_csv(
        os.path.join(OUT_DIR, "machine_capacity.csv"),
        ["machine_id", "period", "hours_available"],
        gen_capacity(),
    )
    write_csv(
        os.path.join(OUT_DIR, "worker_availability.csv"),
        ["worker_type", "period", "hours_available", "cost_per_hour"],
        gen_worker_availability(),
    )
    print(f"Sample data written to {os.path.abspath(OUT_DIR)}")
