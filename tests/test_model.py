"""
test_model.py
--------------
Unit tests for the LP builder and the production planning model.
Run with:  python -m pytest tests/  (or: python -m unittest discover tests)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.lp_builder import LPModel
from src.data_loader import load_planning_data
from src.model import build_and_solve

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


class TestLPBuilder(unittest.TestCase):
    def test_simple_max_problem(self):
        lp = LPModel(sense="max")
        lp.add_var("x", ub=10)
        lp.add_var("y", ub=10)
        lp.add_constraint({"x": 1, "y": 1}, "<=", 12, name="cap")
        lp.set_objective({"x": 3, "y": 5})
        result = lp.solve()
        self.assertTrue(result.success)
        self.assertAlmostEqual(result.objective_value, 56.0, places=4)

    def test_infeasible_problem_is_reported(self):
        lp = LPModel(sense="min")
        lp.add_var("x", lb=5, ub=10)
        lp.add_constraint({"x": 1}, "<=", 2, name="impossible")
        lp.set_objective({"x": 1})
        result = lp.solve()
        self.assertFalse(result.success)


class TestProductionPlanningModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load_planning_data(DATA_DIR)
        cls.out = build_and_solve(cls.data)

    def test_solve_succeeds(self):
        self.assertTrue(self.out.success)

    def test_baseline_has_no_shortfall(self):
        # the sample dataset is tuned so the baseline plan is fully feasible
        self.assertLess(self.out.shortfall["units"].sum(), 1e-3)

    def test_machine_capacity_not_exceeded(self):
        self.assertTrue((self.out.machine_usage["utilization"] <= 1.0 + 1e-6).all())

    def test_labor_capacity_not_exceeded(self):
        self.assertTrue((self.out.labor_usage["utilization"] <= 1.0 + 1e-6).all())

    def test_demand_is_met_exactly_via_production_inventory_and_shortfall(self):
        # for each (product, period): production_in + inflow_inventory + shortfall - outflow_inventory == demand
        prod_by_pt = self.out.production.groupby(["product", "period"])["units"].sum() \
            if not self.out.production.empty else {}
        inv_by_pt = self.out.inventory.set_index(["product", "period"])["units"]
        short_by_pt = self.out.shortfall.set_index(["product", "period"])["units"]

        for p in self.data.products:
            prev_inv = 0.0
            for t in self.data.periods:
                produced = prod_by_pt.get((p, t), 0.0) if hasattr(prod_by_pt, "get") else 0.0
                shortfall = short_by_pt.get((p, t), 0.0)
                inv = inv_by_pt.get((p, t), 0.0)
                demand = self.data.demand.get((p, t), 0.0)
                balance = prev_inv + produced + shortfall - inv
                self.assertAlmostEqual(balance, demand, places=2,
                                        msg=f"balance violated for {p}, period {t}")
                prev_inv = inv

    def test_total_cost_matches_components(self):
        component_sum = (
            self.out.production_cost + self.out.labor_cost_total
            + self.out.holding_cost_total + self.out.shortfall_cost
        )
        self.assertAlmostEqual(self.out.total_cost, component_sum, places=2)


if __name__ == "__main__":
    unittest.main()
