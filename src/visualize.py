"""
visualize.py
--------------
Matplotlib charts for the production planning optimizer. Kept deliberately
plain (no seaborn dependency) so the project installs with nothing beyond
numpy / pandas / matplotlib / scipy.
"""

import os

import matplotlib.pyplot as plt
import pandas as pd


def _save(fig, outputs_dir: str, filename: str):
    os.makedirs(outputs_dir, exist_ok=True)
    path = os.path.join(outputs_dir, filename)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_utilization_heatmap(usage_df: pd.DataFrame, index_col: str, outputs_dir: str,
                              filename: str, title: str):
    pivot = usage_df.pivot(index=index_col, columns="period", values="utilization")
    fig, ax = plt.subplots(figsize=(8, 0.6 * len(pivot) + 2))
    im = ax.imshow(pivot.values, cmap="YlOrRd", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_xlabel("Period")
    ax.set_title(title)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            val = pivot.values[i, j]
            ax.text(j, i, f"{val:.0%}", ha="center", va="center",
                     color="white" if val > 0.6 else "black", fontsize=8)
    fig.colorbar(im, ax=ax, label="Utilization")
    return _save(fig, outputs_dir, filename)


def plot_production_schedule(production_df: pd.DataFrame, outputs_dir: str, filename: str):
    pivot = production_df.pivot_table(index="period", columns="product", values="units", aggfunc="sum").fillna(0)
    fig, ax = plt.subplots(figsize=(9, 5))
    bottom = None
    for product in pivot.columns:
        ax.bar(pivot.index, pivot[product], bottom=bottom, label=product)
        bottom = pivot[product] if bottom is None else bottom + pivot[product]
    ax.set_xlabel("Period")
    ax.set_ylabel("Units produced")
    ax.set_title("Production Schedule by Product")
    ax.legend(title="Product")
    return _save(fig, outputs_dir, filename)


def plot_cost_breakdown(out, outputs_dir: str, filename: str):
    labels = ["Production", "Labor", "Holding", "Shortfall penalty"]
    values = [out.production_cost, out.labor_cost_total, out.holding_cost_total, out.shortfall_cost]
    fig, ax = plt.subplots(figsize=(6, 5))
    bars = ax.bar(labels, values, color=["#4C72B0", "#DD8452", "#55A868", "#C44E52"])
    ax.set_ylabel("Cost ($)")
    ax.set_title(f"Cost Breakdown (Total = ${out.total_cost:,.0f})")
    for b, v in zip(bars, values):
        ax.text(b.get_x() + b.get_width() / 2, v, f"${v:,.0f}", ha="center", va="bottom", fontsize=8)
    plt.xticks(rotation=15)
    return _save(fig, outputs_dir, filename)


def plot_scenario_metric(scenario_df: pd.DataFrame, metric: str, ylabel: str,
                          outputs_dir: str, filename: str, title: str):
    fig, ax = plt.subplots(figsize=(8, 5))
    for wm, group in scenario_df.groupby("workforce_multiplier"):
        group = group.sort_values("demand_multiplier")
        ax.plot(group["demand_multiplier"], group[metric], marker="o",
                 label=f"Workforce @ {wm:.0%}")
    ax.set_xlabel("Demand multiplier")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    ax.grid(alpha=0.3)
    return _save(fig, outputs_dir, filename)
