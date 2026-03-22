import numpy as np
import pandas as pd

from core.constants import VOLUME_RANGE_STEPS, VOLUME_RANGE_MAX


def calculate_cost_per_task(
    input_tokens: int,
    loop_tokens: int,
    output_tokens: int,
    agentic_multiplier: float,
    input_price_per_token: float,
    output_price_per_token: float,
) -> float:
    """Calculate the cost in USD for a single task execution.

    Loop tokens are treated as input tokens (internal reasoning context).
    Formula: cost = (input_tokens + loop_tokens * μ) * input_price
                  + output_tokens * output_price
    """
    total_input_tokens = input_tokens + (loop_tokens * agentic_multiplier)
    return (total_input_tokens * input_price_per_token) + (output_tokens * output_price_per_token)


def calculate_total_api_cost(cost_per_task: float, volume: int) -> float:
    """Total monthly API cost for a given task volume."""
    return cost_per_task * volume


def calculate_onprem_total_cost(
    fixed_monthly_cost: float,
    volume: int,
    marginal_cost_per_task: float = 0.0,
) -> float:
    """Total monthly on-premises cost (fixed + marginal)."""
    return fixed_monthly_cost + (marginal_cost_per_task * volume)


def calculate_breakeven_volume(
    fixed_monthly_cost: float,
    cost_per_task_api: float,
    marginal_onprem: float = 0.0,
) -> float | None:
    """Monthly task volume at which on-prem cost equals API cost.

    Returns None if on-prem can never be cheaper (API cost <= on-prem marginal cost).
    """
    denominator = cost_per_task_api - marginal_onprem
    if denominator <= 0:
        return None
    return fixed_monthly_cost / denominator


def calculate_revenue(
    revenue_model: str,
    volume: int,
    price_per_task: float = 0.0,
    seat_price: float = 0.0,
    num_seats: int = 0,
) -> float:
    """Monthly revenue based on pricing model.

    task_based:   revenue = price_per_task * volume
    subscription: revenue = seat_price * num_seats  (volume-invariant)
    """
    if revenue_model == "task_based":
        return price_per_task * volume
    return seat_price * num_seats


def calculate_gross_margin(revenue: float, cogs: float) -> float | None:
    """Gross Margin % = (Revenue - COGS) / Revenue * 100.

    Returns None if revenue is zero. Negative values are meaningful.
    """
    if revenue == 0:
        return None
    return ((revenue - cogs) / revenue) * 100


def build_cost_volume_dataframe(
    cost_per_task_api: float,
    fixed_monthly_cost: float,
    marginal_cost_per_task_onprem: float = 0.0,
    price_per_task: float = 0.0,
    revenue_model: str = "task_based",
    seat_price: float = 0.0,
    num_seats: int = 0,
    volume_min: int = 0,
    volume_max: int = VOLUME_RANGE_MAX,
    n_points: int = VOLUME_RANGE_STEPS,
) -> pd.DataFrame:
    """Build a DataFrame with cost and revenue at each volume point for charting."""
    volumes = np.linspace(volume_min, volume_max, n_points).astype(int)

    api_cost = volumes * cost_per_task_api
    onprem_cost = fixed_monthly_cost + (volumes * marginal_cost_per_task_onprem)

    if revenue_model == "task_based":
        revenue = volumes * price_per_task
    else:
        revenue = np.full(len(volumes), seat_price * num_seats)

    return pd.DataFrame(
        {
            "volume": volumes,
            "api_cost": api_cost,
            "onprem_cost": onprem_cost,
            "revenue": revenue,
            "api_gross_profit": revenue - api_cost,
            "onprem_gross_profit": revenue - onprem_cost,
        }
    )


def build_pnl_snapshot(
    volume: int,
    cost_per_task_api: float,
    fixed_monthly_cost: float,
    revenue: float,
    hosting_strategy: str,
    marginal_onprem: float = 0.0,
) -> dict:
    """Return a P&L snapshot dict for KPI cards and the margin analysis chart."""
    if hosting_strategy == "onprem":
        cogs = calculate_onprem_total_cost(fixed_monthly_cost, volume, marginal_onprem)
        breakeven_volume = calculate_breakeven_volume(
            fixed_monthly_cost, cost_per_task_api, marginal_onprem
        )
    else:
        cogs = calculate_total_api_cost(cost_per_task_api, volume)
        breakeven_volume = None

    gross_profit = revenue - cogs
    gross_margin_pct = calculate_gross_margin(revenue, cogs)

    return {
        "revenue": revenue,
        "cogs": cogs,
        "gross_profit": gross_profit,
        "gross_margin_pct": gross_margin_pct,
        "cost_per_task": cost_per_task_api,
        "breakeven_volume": breakeven_volume,
    }
