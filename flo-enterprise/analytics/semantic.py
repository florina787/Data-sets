"""Semantic metrics layer: the single governed definition of every financial metric shown by FLO.

Dashboards, agents and exports reference metrics by id; they never re-implement a formula. Changing a definition
requires a version bump (recorded in `version`) and is visible in each chart's lineage panel.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

SEMANTIC_LAYER_VERSION = "2026.10.1"


@dataclass(frozen=True)
class Metric:
    id: str
    name: str
    definition: str
    formula: str
    unit: str
    grain: str
    sources: tuple[str, ...]
    owner: str
    data_product: str
    version: str = "1.0"


METRICS: dict[str, Metric] = {m.id: m for m in [
    Metric("aum.total", "Total AUM", "Sum of month-end net asset value of all FLO products.",
           "sum(product_monthly.aum_close) at month-end", "CAD", "month", ("portfolio_accounting",), "Finance", "finance"),
    Metric("aum.growth", "AUM growth", "Change in total AUM between the opening of the first month and the close of the last month of the period.",
           "AUM_close(end) / AUM_open(start) - 1", "%", "period", ("portfolio_accounting",), "Finance", "finance"),
    Metric("flows.subscriptions", "Gross subscriptions", "Client purchases into FLO products.", "sum(subscriptions)", "CAD", "month",
           ("portfolio_accounting",), "Distribution Finance", "finance"),
    Metric("flows.redemptions", "Gross redemptions", "Client redemptions from FLO products.", "sum(redemptions)", "CAD", "month",
           ("portfolio_accounting",), "Distribution Finance", "finance"),
    Metric("flows.net", "Net client flows", "Subscriptions minus redemptions. Excludes market movement and distributions reinvested.",
           "sum(subscriptions) - sum(redemptions)", "CAD", "month", ("portfolio_accounting",), "Distribution Finance", "finance"),
    Metric("aum.market_movement", "Market movement", "Change in AUM not explained by client flows (investment return, FX, distributions).",
           "AUM_close - AUM_open - net flows", "CAD", "month", ("portfolio_accounting",), "Finance", "finance"),
    Metric("aum.fee_earning", "Fee-earning assets", "AUM of products charging a management fee > 0 bps in the month (excludes fee-waived incubation products).",
           "sum(aum_close where fee_bps > 0)", "CAD", "month", ("portfolio_accounting",), "Finance", "finance"),
    Metric("revenue.management_fees", "Management fee revenue", "Accrued management fees: average monthly AUM x contractual fee rate / 12.",
           "sum((aum_open + aum_close)/2 * fee_bps / 10000 / 12)", "CAD", "month", ("portfolio_accounting", "erp"), "Finance", "finance"),
    Metric("revenue.yield_bps", "Revenue yield", "Annualized management fee revenue divided by average AUM.",
           "revenue * 12 / months / avg(monthly average AUM) * 10000", "bps", "period", ("portfolio_accounting",), "Finance", "finance"),
    Metric("expenses.operating", "Operating expenses", "Sum of compensation, technology, distribution, marketing and G&A expense lines in the general ledger.",
           "sum(finance_monthly.actual where line like 'expense_%')", "CAD", "month", ("erp",), "Finance", "finance"),
    Metric("margin.operating", "Operating margin", "Operating income divided by management fee revenue.",
           "(revenue - operating expenses) / revenue", "%", "period", ("erp",), "Finance", "finance"),
    Metric("product.contribution", "Product contribution", "Product revenue less direct distribution cost (40 bps trailer on mutual funds) less shared cost allocated by revenue share. Illustrative management allocation.",
           "revenue - direct cost - shared cost * revenue share", "CAD", "period", ("portfolio_accounting", "erp"), "Finance", "finance"),
    Metric("clients.retention", "Client retention", "Share of clients active 12 months before period end who were not closed during the following 12 months.",
           "1 - closed_in_window / active_at_window_start", "%", "period", ("crm",), "Private Wealth", "wealth"),
    Metric("perf.twr", "Time-weighted return", "Geometrically linked monthly returns with external flows at month-end.",
           "prod(1 + (MV_close - flow)/MV_open - 1) - 1", "%", "period", ("portfolio_management",), "Investment Performance", "investment"),
    Metric("perf.mwr", "Money-weighted return", "Annual IRR of the opening value, external flows and closing value.",
           "IRR(cash flows)", "% p.a.", "period", ("portfolio_management",), "Investment Performance", "investment"),
    Metric("risk.volatility", "Volatility", "Annualized sample standard deviation of monthly returns.", "stdev(r) * sqrt(12)", "%", "period",
           ("portfolio_management", "market_data"), "Risk", "risk"),
    Metric("risk.sharpe", "Sharpe ratio", "Annualized mean excess return over the synthetic T-bill index divided by annualized volatility of excess returns.",
           "mean(r - rf) * 12 / (stdev(r - rf) * sqrt(12))", "ratio", "period", ("portfolio_management", "market_data"), "Risk", "risk"),
    Metric("risk.max_drawdown", "Maximum drawdown", "Largest peak-to-trough decline of the cumulative wealth index.", "min(W_t / max(W_s<=t) - 1)", "%", "period",
           ("portfolio_management",), "Risk", "risk"),
    Metric("risk.hhi", "Concentration (HHI)", "Herfindahl-Hirschman index of holding weights; effective N = 1/HHI.", "sum(w_i^2)", "index", "point-in-time",
           ("portfolio_management",), "Risk", "risk"),
    Metric("risk.single_issuer", "Single-issuer weight", "Largest holding weight vs the 10% single-issuer limit (CTL-CONC-01).", "max(w_i)", "%", "point-in-time",
           ("portfolio_management",), "Risk", "risk"),
    Metric("risk.drift", "Allocation drift", "One-way turnover needed to return to target weights.", "0.5 * sum|w_current - w_target|", "%", "point-in-time",
           ("portfolio_management",), "Investment Management", "investment"),
    Metric("exposure.geographic", "Geographic exposure", "Look-through exposure by issuer country: product AUM x product holding weights plus portfolio MV x holding weights.",
           "sum(AUM_p * w_p,i) + sum(MV_k * w_k,i) grouped by country", "CAD", "point-in-time", ("portfolio_accounting", "portfolio_management", "market_data"), "Risk", "investment"),
    Metric("budget.variance", "Actual vs budget", "Actual minus budget per ledger line for the period.", "sum(actual) - sum(budget)", "CAD", "period", ("erp",), "FP&A", "finance"),
    Metric("strategy.initiative_progress", "Initiative progress", "Reported % complete vs time-elapsed planned % complete.", "progress_pct - planned_progress_pct", "pp", "point-in-time",
           ("strategy",), "Strategy Office", "strategy"),
    Metric("risk.enterprise_score", "Enterprise risk score", "Likelihood x impact (1-25) from the risk register.", "likelihood * impact", "score", "point-in-time",
           ("risk_register",), "CRO", "risk"),
]}


def describe(*metric_ids: str) -> list[dict]:
    return [asdict(METRICS[m]) | {"semantic_layer_version": SEMANTIC_LAYER_VERSION} for m in metric_ids]
