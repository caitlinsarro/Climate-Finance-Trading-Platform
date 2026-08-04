#!/usr/bin/env python3
"""Build governed market/financial inputs for the eight-issuer DCF prototype.

Observed inputs and model assumptions are deliberately stored in different
files.  The release does not claim that an assumption is an issuer disclosure.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf


ROOT = Path(__file__).resolve().parents[1]
TICKERS = ("AAPL", "CAT", "CVX", "DE", "DUK", "MSFT", "NEE", "XOM")
SECTORS = {
    "AAPL": "Technology", "CAT": "Industrials", "CVX": "Energy",
    "DE": "Industrials", "DUK": "Utilities", "MSFT": "Technology",
    "NEE": "Utilities", "XOM": "Energy",
}
TERMINAL_GROWTH = {"Technology": 0.025, "Industrials": 0.022, "Energy": 0.018, "Utilities": 0.020}
PASS_THROUGH_BASE = {"Technology": 0.70, "Industrials": 0.40, "Energy": 0.30, "Utilities": 0.60}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def latest_fact(frame: pd.DataFrame, ticker: str, tags: tuple[str, ...], fiscal_year: int = 2025):
    rows = frame[
        (frame["ticker"] == ticker)
        & (frame["fiscal_year"] == fiscal_year)
        & (frame["quarters"] == 4)
        & (frame["tag"].isin(tags))
    ].sort_values(["filed", "date"])
    if rows.empty:
        return None, None
    row = rows.iloc[-1]
    return float(row["value"]), row["source_url"]


def latest_instant_fact(frame: pd.DataFrame, ticker: str, tag: str, fiscal_year: int = 2025):
    rows = frame[
        (frame["ticker"] == ticker)
        & (frame["fiscal_year"] == fiscal_year)
        & (frame["quarters"] == 0)
        & (frame["tag"] == tag)
    ].sort_values(["filed", "date"])
    if rows.empty:
        return None, None
    row = rows.iloc[-1]
    return float(row["value"]), row["source_url"]


def monthly_beta(close: pd.DataFrame, ticker: str) -> tuple[float, int]:
    returns = close[[ticker, "SPY"]].pct_change(fill_method=None).dropna()
    if len(returns) < 24 or float(returns["SPY"].var()) <= 0:
        return float("nan"), len(returns)
    return float(returns[ticker].cov(returns["SPY"]) / returns["SPY"].var()), len(returns)


def debt_value(frame: pd.DataFrame, ticker: str, public_total_debt=None):
    current, source1 = latest_instant_fact(frame, ticker, "LongTermDebtCurrent")
    noncurrent, source2 = latest_instant_fact(frame, ticker, "LongTermDebtNoncurrent")
    if current is not None or noncurrent is not None:
        return (current or 0.0) + (noncurrent or 0.0), source1 or source2, "SEC observed"
    total, source = latest_instant_fact(frame, ticker, "LongTermDebt")
    if total is not None:
        return total, source, "SEC observed"
    if public_total_debt is not None and public_total_debt > 0:
        return float(public_total_debt), "https://finance.yahoo.com/", "Public market-data field"
    return None, None, "Model assumption"


def build(release_id: str, evidence_release_id: str, sec_release_id: str, demo_release_id: str):
    release = ROOT / "data" / "releases" / release_id
    processed = release / "processed"
    raw = release / "raw" / "market"
    processed.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)

    sec_path = ROOT / "data" / "releases" / sec_release_id / "processed" / "sec_financial_facts_2009q1_2026q1.csv"
    demo_path = ROOT / "data" / "releases" / demo_release_id / "processed" / "eight_issuer_demo_2025.csv"
    treasury_path = ROOT / "data" / "releases" / "CFP-2026-003-R1-20260731T2318Z" / "processed" / "treasury_yield_curve_2026.csv"
    master_path = ROOT / "data" / "issuer_sector_master.csv"

    sec = pd.read_csv(sec_path)
    demo = pd.read_csv(demo_path).set_index("ticker")
    treasury = pd.read_csv(treasury_path).sort_values("date").iloc[-1]
    risk_free = float(treasury["yield_10y_pct"]) / 100.0
    master = pd.read_csv(master_path).set_index("ticker")

    market = yf.download(list(TICKERS) + ["SPY"], period="5y", interval="1mo", auto_adjust=True, progress=False, threads=True)
    close = market["Close"].copy().dropna(how="all")
    close.index = close.index.strftime("%Y-%m-%d")
    market_path = raw / "yfinance_5y_monthly_adjusted_close.csv"
    close.to_csv(market_path, index_label="date")
    public_market_fields = {}
    for ticker in TICKERS:
        info = yf.Ticker(ticker).get_info() or {}
        public_market_fields[ticker] = {
            "marketCap": info.get("marketCap"),
            "totalDebt": info.get("totalDebt"),
            "reportedBeta": info.get("beta"),
        }
    market_fields_path = raw / "yfinance_public_market_fields.json"
    market_fields_path.write_text(json.dumps(public_market_fields, indent=2), encoding="utf-8")

    rows = []
    for ticker in TICKERS:
        sector = SECTORS[ticker]
        revenue, revenue_url = latest_fact(sec, ticker, (
            "RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
        ))
        pretax, _ = latest_fact(sec, ticker, (
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        ))
        tax, _ = latest_fact(sec, ticker, ("IncomeTaxExpenseBenefit",))
        interest, interest_url = latest_fact(sec, ticker, ("InterestExpense", "InterestExpenseNonOperating"))
        debt, debt_url, debt_status = debt_value(sec, ticker, public_market_fields[ticker].get("totalDebt"))
        cfo = float(demo.loc[ticker, "operating_cash_flow_usd"])
        capex = float(demo.loc[ticker, "capital_expenditure_usd"])
        reported_fcf = cfo - capex
        tax_rate = min(0.35, max(0.0, (tax / pretax))) if tax is not None and pretax not in (None, 0) else 0.21
        tax_status = "SEC observed" if tax is not None and pretax not in (None, 0) else "Model assumption"
        market_cap = float(master.loc[ticker, "market_cap_usd"])
        beta, observations = monthly_beta(close, ticker)
        beta_status = "Observed 5y monthly returns" if np.isfinite(beta) else "Model assumption"
        if not np.isfinite(beta):
            beta = {"Technology": 1.15, "Industrials": 1.10, "Energy": 0.95, "Utilities": 0.65}[sector]
        if debt is None or debt <= 0:
            debt_ratio = {"Technology": 0.16, "Industrials": 0.30, "Energy": 0.32, "Utilities": 0.52}[sector]
            debt = market_cap * debt_ratio / (1.0 - debt_ratio)
            debt_status = "Model assumption"
        if interest is not None and interest > 0 and debt > 0:
            pre_tax_debt_cost = min(0.12, max(0.02, interest / debt))
            debt_cost_status = "SEC interest / SEC debt"
        else:
            pre_tax_debt_cost = 0.0525
            debt_cost_status = "Model assumption"
        after_tax_interest = (interest if interest is not None else debt * pre_tax_debt_cost) * (1.0 - tax_rate)
        fcff = reported_fcf + after_tax_interest
        fcff_status = "SEC CFO - CapEx + after-tax interest"
        if fcff <= 0:
            # Growth utilities can have negative reported FCF.  Keep the
            # observed figures visible and use a labeled maintenance-CapEx
            # normalization rather than pretending the value is observed.
            fcff = cfo * 0.40 + after_tax_interest
            fcff_status = "Model assumption: CFO x 40% maintenance-CapEx allowance + after-tax interest"
        erp = 0.045
        cost_equity = risk_free + beta * erp
        equity_weight = market_cap / (market_cap + debt)
        debt_weight = 1.0 - equity_weight
        wacc = equity_weight * cost_equity + debt_weight * pre_tax_debt_cost * (1.0 - tax_rate)
        rows.append({
            "ticker": ticker, "sector": sector, "fiscal_year": 2025,
            "revenue_usd": revenue or "", "operating_cash_flow_usd": cfo,
            "capital_expenditure_usd": capex, "reported_free_cash_flow_usd": reported_fcf,
            "normalized_fcff_usd": fcff, "fcff_status": fcff_status,
            "interest_expense_usd": interest or "", "debt_usd": debt,
            "market_cap_usd": market_cap, "market_cap_as_of": master.loc[ticker, "as_of"],
            "effective_tax_rate": tax_rate, "tax_status": tax_status,
            "five_year_monthly_beta": beta, "beta_observations": observations,
            "beta_status": beta_status, "risk_free_rate": risk_free,
            "risk_free_as_of": treasury["date"], "equity_risk_premium": erp,
            "erp_status": "Model assumption", "pre_tax_debt_cost": pre_tax_debt_cost,
            "debt_cost_status": debt_cost_status, "wacc": wacc,
            "terminal_growth": TERMINAL_GROWTH[sector], "terminal_growth_status": "Model assumption",
            "revenue_source_url": revenue_url or "", "debt_source_url": debt_url or "",
            "interest_source_url": interest_url or "",
            "market_source_url": "https://finance.yahoo.com/",
            "treasury_source_url": treasury["source_url"],
        })

    assumptions = []
    for ticker in TICKERS:
        base_pass = PASS_THROUGH_BASE[SECTORS[ticker]]
        for case, policy, pass_adjust, emissions_decline, physical_conversion, resilience, macro_elasticity in (
            ("low", 0.50, 0.15, 0.05, 0.0025, 0.70, 0.35),
            ("base", 0.75, 0.00, 0.03, 0.0050, 0.50, 0.60),
            ("high", 1.00, -0.15, 0.01, 0.0100, 0.30, 1.00),
        ):
            assumptions.append({
                "ticker": ticker, "case": case,
                "policy_coverage": policy,
                "pass_through": min(0.90, max(0.05, base_pass + pass_adjust)),
                "annual_emissions_decline": emissions_decline,
                "physical_cashflow_conversion": physical_conversion,
                "resilience": resilience,
                "macro_cashflow_elasticity": macro_elasticity,
                "source_class": "Model assumption",
                "allowed_use": "prototype scenario sensitivity; editable and not issuer-observed",
            })

    inputs_path = processed / "eight_issuer_valuation_inputs_2025.csv"
    assumptions_path = processed / "eight_issuer_model_assumptions.csv"
    write_csv(inputs_path, rows)
    write_csv(assumptions_path, assumptions)
    files = [inputs_path, assumptions_path, market_path, market_fields_path]
    manifest = {
        "release_id": release_id,
        "feature_id": "CFP-2026-003",
        "created_at": "2026-08-04T21:30:00Z",
        "supersedes": evidence_release_id,
        "status": "prototype valuation inputs; observed and assumed layers separated",
        "processed_paths": [str(p.relative_to(ROOT)) for p in files],
        "sha256": {str(p.relative_to(ROOT)): sha(p) for p in files},
        "source_entries": [
            {"source_class": "official issuer-filed SEC XBRL", "source_url": "https://www.sec.gov/dera/data/financial-statement-data-sets", "allowed_use": "financial baseline"},
            {"source_class": "official U.S. Treasury", "source_url": str(treasury["source_url"]), "allowed_use": "risk-free WACC leg"},
            {"source_class": "public market-data cache", "source_url": "https://finance.yahoo.com/", "allowed_use": "five-year monthly beta"},
            {"source_class": "project assumptions", "allowed_use": "Low/Base/High sensitivity only"},
        ],
        "valuation_rule": "Annual target/reference FCFF paths use common WACC; output is modeled value impact, not price target or forecast probability.",
    }
    (release / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--evidence-release-id", default="CFP-2026-003-R13-20260804T193000Z")
    parser.add_argument("--sec-release-id", default="CFP-2026-003-R8-20260801T005207Z")
    parser.add_argument("--demo-release-id", default="CFP-2026-003-R11-20260801T023000Z")
    args = parser.parse_args()
    print(json.dumps(build(args.release_id, args.evidence_release_id, args.sec_release_id, args.demo_release_id), indent=2))
