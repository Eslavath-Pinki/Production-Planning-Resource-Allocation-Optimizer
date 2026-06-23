"""
lp_builder.py
-------------
A small, dependency-light linear programming builder.

Why this exists:
    Most tutorials reach for PuLP or Pyomo, but both are just convenience
    layers over an LP solver. scipy.optimize.linprog already ships with a
    production-grade solver (HiGHS) and is part of the standard scientific
    Python stack, so no extra install is required to run this project.

    This module gives that solver a friendlier, name-based interface:
    you declare variables and constraints by name instead of hand-building
    sparse matrices, which keeps src/model.py readable.

Usage:
    lp = LPModel(sense="min")
    x = lp.add_var("x")
    y = lp.add_var("y", lb=0, ub=10)
    lp.add_constraint({"x": 1, "y": 1}, "<=", 10, name="capacity")
    lp.set_objective({"x": 2, "y": 3})
    result = lp.solve()
    print(result.values["x"], result.status)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np
from scipy.optimize import linprog


@dataclass
class SolveResult:
    status: str
    success: bool
    objective_value: Optional[float]
    values: Dict[str, float]
    raw: object


class LPModel:
    def __init__(self, sense: str = "min"):
        if sense not in ("min", "max"):
            raise ValueError("sense must be 'min' or 'max'")
        self.sense = sense
        self._var_index: Dict[str, int] = {}
        self._var_names: List[str] = []
        self._lb: List[float] = []
        self._ub: List[Optional[float]] = []
        self._obj: Dict[str, float] = {}
        self._ub_rows: List[Tuple[Dict[str, float], float]] = []   # A_ub x <= b_ub
        self._eq_rows: List[Tuple[Dict[str, float], float]] = []   # A_eq x == b_eq
        self._constraint_names: List[str] = []

    # ---- variable & objective declaration -------------------------------

    def add_var(self, name: str, lb: float = 0.0, ub: Optional[float] = None) -> str:
        if name in self._var_index:
            raise ValueError(f"variable '{name}' already exists")
        self._var_index[name] = len(self._var_names)
        self._var_names.append(name)
        self._lb.append(lb)
        self._ub.append(ub)
        return name

    def set_objective(self, coeffs: Dict[str, float]):
        self._obj = dict(coeffs)

    # ---- constraints ------------------------------------------------------

    def add_constraint(self, coeffs: Dict[str, float], sense: str, rhs: float, name: str = ""):
        """sense is one of '<=', '>=', '=='."""
        for v in coeffs:
            if v not in self._var_index:
                raise ValueError(f"unknown variable '{v}' in constraint '{name}'")
        if sense == "<=":
            self._ub_rows.append((coeffs, rhs))
        elif sense == ">=":
            flipped = {k: -val for k, val in coeffs.items()}
            self._ub_rows.append((flipped, -rhs))
        elif sense == "==":
            self._eq_rows.append((coeffs, rhs))
        else:
            raise ValueError("sense must be '<=', '>=', or '=='")
        self._constraint_names.append(name or f"c{len(self._constraint_names)}")

    # ---- solve --------------------------------------------------------------

    def solve(self) -> SolveResult:
        n = len(self._var_names)
        c = np.zeros(n)
        for name, coeff in self._obj.items():
            c[self._var_index[name]] = coeff if self.sense == "min" else -coeff

        A_ub, b_ub = self._build_matrix(self._ub_rows, n)
        A_eq, b_eq = self._build_matrix(self._eq_rows, n)

        bounds = list(zip(self._lb, [u if u is not None else None for u in self._ub]))

        res = linprog(
            c,
            A_ub=A_ub if len(b_ub) else None,
            b_ub=b_ub if len(b_ub) else None,
            A_eq=A_eq if len(b_eq) else None,
            b_eq=b_eq if len(b_eq) else None,
            bounds=bounds,
            method="highs",
        )

        values = {name: float(res.x[i]) for name, i in self._var_index.items()} if res.success else {}
        obj_val = None
        if res.success:
            obj_val = float(res.fun) if self.sense == "min" else float(-res.fun)

        return SolveResult(
            status=res.message,
            success=bool(res.success),
            objective_value=obj_val,
            values=values,
            raw=res,
        )

    def _build_matrix(self, rows: List[Tuple[Dict[str, float], float]], n: int):
        if not rows:
            return np.zeros((0, n)), np.zeros(0)
        A = np.zeros((len(rows), n))
        b = np.zeros(len(rows))
        for i, (coeffs, rhs) in enumerate(rows):
            for name, val in coeffs.items():
                A[i, self._var_index[name]] = val
            b[i] = rhs
        return A, b
