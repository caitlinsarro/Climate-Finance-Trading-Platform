#!/usr/bin/env python3
"""Build reproducible eight-issuer climate-model charts for reports and slides.

The exporter deliberately calls the governed application model in ``app.py``.
It does not recreate the valuation formulas or replace missing values with zero.
All outputs are conditional research-prototype comparisons, not forecasts.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import app  # noqa: E402  (repo root is added before importing the governed model)


ISSUERS: Tuple[str, ...] = ("AAPL", "CAT", "CVX", "DE", "DUK", "MSFT", "NEE", "XOM")
HORIZON = 2050
CASES: Tuple[str, ...] = ("low", "base", "high")
SCENARIO_PAIRS: Tuple[Mapping[str, str], ...] = (
    {
        "key": "cp_vs_baseline",
        "label": "Current Policies vs baseline",
        "short_label": "CP vs baseline",
        "target": "current_policies",
        "reference": "baseline",
    },
    {
        "key": "nz_vs_baseline",
        "label": "Net Zero 2050 vs baseline",
        "short_label": "Net Zero vs baseline",
        "target": "net_zero_2050",
        "reference": "baseline",
    },
    {
        "key": "below2c_vs_cp",
        "label": "Below 2°C vs Current Policies",
        "short_label": "Below 2°C vs CP",
        "target": "below_2c",
        "reference": "current_policies",
    },
    {
        "key": "cp_vs_delayed",
        "label": "Current Policies vs Delayed Transition",
        "short_label": "CP vs delayed",
        "target": "current_policies",
        "reference": "delayed_transition",
    },
    {
        "key": "fragmented_vs_baseline",
        "label": "Fragmented World vs baseline",
        "short_label": "Fragmented vs baseline",
        "target": "fragmented_world",
        "reference": "baseline",
    },
)

NAVY = "#214E8A"
TEAL = "#00838A"
RED = "#C34249"
GOLD = "#C28A2C"
GREEN = "#3B7F5C"
INK = "#1D2733"
MUTED = "#65717E"
GRID = "#D8DEE5"
PAPER = "#FFFFFF"
PALETTE = {
    "transition": GOLD,
    "physical": RED,
    "macro_supply": NAVY,
}


def _number(value: Any) -> Optional[float]:
    """Return a finite float, preserving missing values as None."""
    if value is None or value == "":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _pct(value: Any) -> Optional[float]:
    number = _number(value)
    return None if number is None else number * 100.0


def _channel_map(value: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    return {str(row["key"]): row for row in value.get("channels", [])}


def _physical_confidence(facility_count: Optional[float], matches: Optional[float]) -> Tuple[Optional[float], str, str]:
    """Return match coverage, confidence tier, and evidence type."""
    if facility_count is None or facility_count <= 0:
        return None, "Unverified", "Proxy fallback; no issuer facilities in governed match file"
    match_count = max(0.0, matches or 0.0)
    coverage = min(1.0, match_count / facility_count)
    if coverage > 0.80:
        confidence = "High"
    elif coverage >= 0.50:
        confidence = "Medium"
    else:
        confidence = "Low"
    return coverage, confidence, "Issuer facility-to-FEMA county match"


def _result_diagnostics(
    value_impact_pct: Optional[float],
    reference_ev: Optional[float],
    target_ev: Optional[float],
) -> Dict[str, Any]:
    target_floor = target_ev is not None and target_ev <= 0.0
    reference_floor = reference_ev is not None and reference_ev <= 0.0
    extreme = value_impact_pct is not None and abs(value_impact_pct) >= 100.0
    if target_floor:
        interpretation = "Target EV hit the model zero-value floor; boundary stress result"
    elif reference_floor:
        interpretation = "Reference EV hit the model zero-value floor; relative percentage not meaningful"
    elif extreme:
        interpretation = "Extreme relative scenario differential; denominator-sensitive"
    else:
        interpretation = "Conditional scenario sensitivity; not a forecast or probability"
    return {
        "target_ev_floor_flag": target_floor,
        "reference_ev_floor_flag": reference_floor,
        "extreme_relative_value_flag": extreme,
        "result_interpretation": interpretation,
        "reference_ev_share_of_target_pct": None if not target_ev or reference_ev is None else reference_ev / target_ev * 100.0,
    }


def sector_map() -> Dict[str, str]:
    release = app.latest_eight_issuer_demo()
    if not release.get("is_loaded"):
        raise RuntimeError("The governed eight-issuer demo release is not loaded.")
    result = {str(row["ticker"]): str(row["sector"]) for row in release.get("rows", [])}
    missing = [ticker for ticker in ISSUERS if ticker not in result]
    if missing:
        raise RuntimeError(f"Missing issuer-sector rows: {', '.join(missing)}")
    return result


def physical_evidence_map() -> Dict[str, Mapping[str, Any]]:
    release = app.latest_eight_issuer_climate_evidence()
    if not release.get("is_loaded"):
        raise RuntimeError("The governed R17 climate-evidence release is not loaded.")
    return {str(row["ticker"]): row for row in release.get("physical_rows", [])}


def build_results() -> List[Dict[str, Any]]:
    """Run all eight issuers, five scenario pairs, and three assumption cases."""
    sectors = sector_map()
    physical_rows = physical_evidence_map()
    rows: List[Dict[str, Any]] = []

    for pair in SCENARIO_PAIRS:
        for ticker in ISSUERS:
            for case in CASES:
                payload = app.climate_model_lab_payload(
                    scope="issuer",
                    target=pair["target"],
                    reference=pair["reference"],
                    horizon=HORIZON,
                    sector=sectors[ticker],
                    ticker=ticker,
                    assumption_case=case,
                )
                valuation = payload.get("prototype_valuation") or {}
                calculable = bool(valuation.get("is_calculable"))
                channels = _channel_map(valuation) if calculable else {}
                observed = valuation.get("observed_inputs") or {}
                assumptions = valuation.get("model_assumptions") or {}
                detail = valuation.get("terminal_component_detail") or {}
                audit = valuation.get("valuation_audit") or {}
                physical = physical_rows.get(ticker, {})

                facility_count = _number(physical.get("facility_count")) if calculable else None
                fema_matches = _number(physical.get("fema_eal_matches")) if calculable else None
                match_coverage, confidence, physical_evidence_type = _physical_confidence(facility_count, fema_matches)
                value_impact_pct = _pct(valuation.get("value_impact")) if calculable else None
                reference_ev = _number(valuation.get("reference_enterprise_value_usd")) if calculable else None
                target_ev = _number(valuation.get("target_enterprise_value_usd")) if calculable else None
                diagnostics = _result_diagnostics(value_impact_pct, reference_ev, target_ev)

                row: Dict[str, Any] = {
                    "ticker": ticker,
                    "sector": sectors[ticker],
                    "scenario_pair_key": pair["key"],
                    "scenario_pair": pair["label"],
                    "scenario_pair_short": pair["short_label"],
                    "target_scenario": pair["target"],
                    "reference_scenario": pair["reference"],
                    "horizon": HORIZON,
                    "assumption_case": case,
                    "is_calculable": calculable,
                    "release_id": valuation.get("release_id"),
                    "status": valuation.get("status") or payload.get("reason"),
                    "value_impact_pct": value_impact_pct,
                    "reference_enterprise_value_usd": reference_ev,
                    "target_enterprise_value_usd": target_ev,
                    "enterprise_value_delta_usd": _number(valuation.get("enterprise_value_delta_usd")) if calculable else None,
                    "symmetric_value_difference_pct": _pct(valuation.get("symmetric_value_difference")) if calculable else None,
                    "engine_ranking_status": audit.get("ranking_status") if calculable else None,
                    "terminal_fcff_clipped": bool(audit.get("terminal_fcff_clipped")) if calculable else None,
                    "total_unapplied_cost_usd": _number(audit.get("total_unapplied_cost_usd")) if calculable else None,
                    "denominator_sensitive": bool(audit.get("denominator_sensitive")) if calculable else None,
                    "physical_proxy_used": bool(audit.get("physical_proxy_used")) if calculable else None,
                    "equity_bridge_status": "Not calculable - governed EV-to-equity inputs missing" if calculable else None,
                    "reference_terminal_fcff_usd": _number(valuation.get("reference_terminal_fcff_usd")) if calculable else None,
                    "target_terminal_fcff_usd": _number(valuation.get("target_terminal_fcff_usd")) if calculable else None,
                    "terminal_fcff_delta_usd": _number(valuation.get("terminal_fcff_delta_usd")) if calculable else None,
                    "normalized_fcff_usd": _number(observed.get("normalized_fcff_usd")) if calculable else None,
                    "fcff_accounting_class": observed.get("fcff_accounting_class") if calculable else None,
                    "transition_fcff_pressure_pct": _pct(channels.get("transition", {}).get("terminal_cash_flow_delta_rate")) if calculable else None,
                    "physical_fcff_pressure_pct": _pct(channels.get("physical", {}).get("terminal_cash_flow_delta_rate")) if calculable else None,
                    "macro_supply_fcff_pressure_pct": _pct(channels.get("macro_supply", {}).get("terminal_cash_flow_delta_rate")) if calculable else None,
                    "transition_terminal_cost_usd": _number(channels.get("transition", {}).get("terminal_cash_flow_delta_usd")) if calculable else None,
                    "physical_terminal_cost_usd": _number(channels.get("physical", {}).get("terminal_cash_flow_delta_usd")) if calculable else None,
                    "macro_supply_terminal_cost_usd": _number(channels.get("macro_supply", {}).get("terminal_cash_flow_delta_usd")) if calculable else None,
                    "transition_value_contribution_pct": _pct(channels.get("transition", {}).get("value_contribution")) if calculable else None,
                    "physical_value_contribution_pct": _pct(channels.get("physical", {}).get("value_contribution")) if calculable else None,
                    "macro_supply_value_contribution_pct": _pct(channels.get("macro_supply", {}).get("value_contribution")) if calculable else None,
                    "scope1_terminal_cost_usd": _number(detail.get("scope1")) if calculable else None,
                    "scope2_terminal_cost_usd": _number(detail.get("scope2")) if calculable else None,
                    "scope3_terminal_cost_usd": _number(detail.get("scope3")) if calculable else None,
                    "acute_terminal_cost_usd": _number(detail.get("acute")) if calculable else None,
                    "chronic_terminal_cost_usd": _number(detail.get("chronic")) if calculable else None,
                    "scope1_tco2e": _number(observed.get("scope1_tco2e")) if calculable else None,
                    "scope2_tco2e": _number(observed.get("scope2_tco2e")) if calculable else None,
                    "scope3_tco2e": _number(observed.get("scope3_tco2e")) if calculable else None,
                    "net_ppe_usd": _number(observed.get("net_ppe_usd")) if calculable else None,
                    "fema_building_eal_rate_pct": _pct(observed.get("fema_building_eal_rate")) if calculable else None,
                    "fema_eal_matches": fema_matches,
                    "facility_count": facility_count,
                    "facility_match_coverage_pct": _pct(match_coverage),
                    "physical_data_confidence": confidence,
                    "physical_evidence_type": physical_evidence_type,
                    "issuer_specific_fema_rate_pct": _pct(observed.get("fema_building_eal_rate")) if calculable and facility_count and facility_count > 0 else None,
                    "cie_target_labour_loss_pct": _pct(observed.get("cie_terminal_labour_loss_target")) if calculable else None,
                    "cie_reference_labour_loss_pct": _pct(observed.get("cie_terminal_labour_loss_reference")) if calculable else None,
                    "wacc_pct": _pct(valuation.get("wacc")) if calculable else None,
                    "terminal_growth_pct": _pct(valuation.get("terminal_growth")) if calculable else None,
                    "policy_coverage": _number(assumptions.get("policy_coverage")) if calculable else None,
                    "pass_through": _number(assumptions.get("pass_through")) if calculable else None,
                    "scope2_cost_incidence": _number(assumptions.get("scope2_cost_incidence")) if calculable else None,
                    "scope3_value_chain_incidence": _number(assumptions.get("scope3_value_chain_incidence")) if calculable else None,
                    "annual_emissions_decline": _number(assumptions.get("annual_emissions_decline")) if calculable else None,
                    "covered_ppe_share": _number(assumptions.get("covered_ppe_share")) if calculable else None,
                    "insurance_adaptation_recovery": _number(assumptions.get("insurance_adaptation_recovery")) if calculable else None,
                    "labour_cost_share": _number(assumptions.get("labour_cost_share")) if calculable else None,
                    "labour_productivity_to_fcff": _number(assumptions.get("labour_productivity_to_fcff")) if calculable else None,
                    "acute_scenario_factor": _number(assumptions.get("acute_scenario_factor")) if calculable else None,
                    "macro_cashflow_elasticity": _number(assumptions.get("macro_cashflow_elasticity")) if calculable else None,
                    "macro_dependency_scale": _number(assumptions.get("macro_dependency_scale")) if calculable else None,
                    "macro_specificity": "Common scenario elasticity + issuer SEC CapEx/CFO dependency scale" if calculable else None,
                    "assumption_classification": assumptions.get("assumption_classification") if calculable else None,
                    "classification": "Prototype enterprise-value sensitivity using source-backed inputs + demonstration assumptions" if calculable else "Not calculable",
                    **diagnostics,
                }
                rows.append(row)
    return rows


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": PAPER,
            "axes.facecolor": PAPER,
            "axes.edgecolor": GRID,
            "axes.labelcolor": INK,
            "axes.titlecolor": INK,
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "xtick.color": MUTED,
            "ytick.color": INK,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def _subtitle(ax: plt.Axes, text: str) -> None:
    ax.text(0, 1.02, text, transform=ax.transAxes, ha="left", va="bottom", color=MUTED, fontsize=9)


def _footer(fig: plt.Figure, release_id: str) -> None:
    fig.text(
        0.01,
        0.012,
        f"Prototype demonstration | Source-backed inputs + explicitly labelled assumptions (not issuer-observed) | EV sensitivity, not probability or price target | {release_id}",
        ha="left",
        va="bottom",
        color=MUTED,
        fontsize=7.5,
    )


def _save(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=PAPER)
    plt.close(fig)


def _base_cp(df: pd.DataFrame) -> pd.DataFrame:
    return df[(df["scenario_pair_key"] == "cp_vs_baseline") & (df["assumption_case"] == "base")].copy()


def chart_value_range(df: pd.DataFrame, output: Path, release_id: str) -> None:
    subset = df[df["scenario_pair_key"] == "cp_vs_baseline"].copy()
    pivot = subset.pivot(index="ticker", columns="assumption_case", values="value_impact_pct")
    pivot = pivot.sort_values("base")
    y = np.arange(len(pivot))
    base = pivot["base"].to_numpy(dtype=float)
    low_bound = np.minimum(pivot["low"], pivot["high"]).to_numpy(dtype=float)
    high_bound = np.maximum(pivot["low"], pivot["high"]).to_numpy(dtype=float)
    xerr = np.vstack((base - low_bound, high_bound - base))

    fig, ax = plt.subplots(figsize=(11.5, 6.4))
    ax.errorbar(base, y, xerr=xerr, fmt="o", color=NAVY, ecolor=GRID, elinewidth=7, capsize=0, markersize=7, zorder=3)
    ax.axvline(0, color=INK, linewidth=0.8)
    ax.set_yticks(y, pivot.index)
    ax.set_xlabel("Discounted enterprise-value impact (%)")
    ax.set_title("Eight-issuer value impact and disclosed assumption range", loc="left", fontsize=17, fontweight="bold", pad=28)
    _subtitle(ax, "Current Policies versus climate-agnostic baseline | Low, Base and High demonstration assumptions—not issuer observations")
    ax.grid(axis="x")
    for yi, val in zip(y, base):
        ax.annotate(f"{val:+.2f}%", (val, yi), xytext=(7 if val >= 0 else -7, 0), textcoords="offset points", ha="left" if val >= 0 else "right", va="center", color=INK, fontsize=9)
    _footer(fig, release_id)
    fig.subplots_adjust(bottom=0.12, top=0.84, left=0.12, right=0.98)
    _save(fig, output)


def chart_channel_attribution(df: pd.DataFrame, output: Path, release_id: str) -> None:
    subset = _base_cp(df).sort_values("value_impact_pct")
    fig, ax = plt.subplots(figsize=(11.5, 6.4))
    y = np.arange(len(subset))
    left = np.zeros(len(subset))
    columns = (
        ("transition_value_contribution_pct", "Transition", "transition"),
        ("physical_value_contribution_pct", "Physical", "physical"),
        ("macro_supply_value_contribution_pct", "Macro / supply", "macro_supply"),
    )
    for column, label, key in columns:
        values = subset[column].to_numpy(dtype=float)
        ax.barh(y, values, left=left, label=label, color=PALETTE[key], height=0.62)
        left += values
    ax.axvline(0, color=INK, linewidth=0.8)
    ax.set_yticks(y, subset["ticker"])
    ax.set_xlabel("Contribution to discounted enterprise-value impact (%)")
    ax.set_title("What drives the Current Policies value impact?", loc="left", fontsize=17, fontweight="bold", pad=28)
    _subtitle(ax, "The three modeled channels stay separate; stacked contributions reconcile to the total value impact")
    ax.grid(axis="x")
    ax.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.18))
    _footer(fig, release_id)
    fig.subplots_adjust(bottom=0.2, top=0.84, left=0.12, right=0.98)
    _save(fig, output)


def chart_scenario_heatmap(df: pd.DataFrame, output: Path, release_id: str) -> None:
    base = df[df["assumption_case"] == "base"].copy()
    labels = [pair["short_label"] for pair in SCENARIO_PAIRS]
    matrix = base.pivot(index="ticker", columns="scenario_pair_short", values="value_impact_pct").reindex(index=ISSUERS, columns=labels)
    floor_matrix = base.pivot(index="ticker", columns="scenario_pair_short", values="target_ev_floor_flag").reindex(index=ISSUERS, columns=labels)
    extreme_matrix = base.pivot(index="ticker", columns="scenario_pair_short", values="extreme_relative_value_flag").reindex(index=ISSUERS, columns=labels)
    values = matrix.to_numpy(dtype=float)
    # Keep extreme terminal-floor outcomes visible in the annotation without
    # letting one cell wash out all other cross-issuer differences.
    scale = min(max(abs(np.nanmin(values)), abs(np.nanmax(values)), 0.01), 100.0)

    fig, ax = plt.subplots(figsize=(12.5, 6.5))
    image = ax.imshow(values, cmap="RdYlGn", vmin=-scale, vmax=scale, aspect="auto")
    ax.set_xticks(np.arange(len(labels)), labels, rotation=20, ha="right")
    ax.set_yticks(np.arange(len(ISSUERS)), ISSUERS)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            marker = "†" if bool(floor_matrix.iloc[i, j]) else ("‡" if bool(extreme_matrix.iloc[i, j]) else "")
            text = "N/C" if np.isnan(values[i, j]) else f"{values[i, j]:+.2f}%{marker}"
            color = "white" if abs(values[i, j]) > scale * 0.55 else INK
            ax.text(j, i, text, ha="center", va="center", color=color, fontsize=9, fontweight="bold")
    cbar = fig.colorbar(image, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("Value impact (%)")
    ax.set_title("Scenario choice changes the investment question", loc="left", fontsize=17, fontweight="bold", pad=28)
    _subtitle(ax, "Base demonstration assumptions—not issuer observations | Relative EV differential, not a return forecast | Colour capped at ±100%")
    for spine in ax.spines.values():
        spine.set_visible(False)
    fig.text(0.09, 0.055, "† target EV reached the model's zero-value floor    ‡ extreme relative percentage is denominator-sensitive", color=MUTED, fontsize=8.5)
    _footer(fig, release_id)
    fig.subplots_adjust(bottom=0.25, top=0.82, left=0.09, right=0.92)
    _save(fig, output)


def chart_rank_stability(df: pd.DataFrame, output: Path, release_id: str) -> None:
    base = df[df["assumption_case"] == "base"].copy()
    labels = [pair["short_label"] for pair in SCENARIO_PAIRS]
    pivot = base.pivot(index="ticker", columns="scenario_pair_short", values="value_impact_pct").reindex(index=ISSUERS, columns=labels)
    ranks = pivot.rank(axis=0, ascending=True, method="min")
    colors = plt.cm.tab10(np.linspace(0, 1, len(ISSUERS)))

    fig, ax = plt.subplots(figsize=(12.5, 6.8))
    x = np.arange(len(labels))
    for color, ticker in zip(colors, ISSUERS):
        ax.plot(x, ranks.loc[ticker].to_numpy(dtype=float), marker="o", linewidth=2, label=ticker, color=color)
        ax.text(x[-1] + 0.06, ranks.loc[ticker].iloc[-1], ticker, va="center", ha="left", color=color, fontsize=8.5)
    ax.set_xticks(x, labels, rotation=20, ha="right")
    ax.set_yticks(np.arange(1, len(ISSUERS) + 1))
    ax.set_ylim(len(ISSUERS) + 0.5, 0.5)
    ax.set_ylabel("Relative downside rank (1 = largest modeled downside)")
    ax.set_title("Does the issuer ranking survive a change in scenario?", loc="left", fontsize=17, fontweight="bold", pad=28)
    _subtitle(ax, "Rank stability is often more decision-useful than trusting one standalone Climate VaR number")
    ax.grid(axis="y")
    _footer(fig, release_id)
    fig.subplots_adjust(bottom=0.22, top=0.83, left=0.1, right=0.91)
    _save(fig, output)


def chart_emissions(df: pd.DataFrame, output: Path, release_id: str) -> None:
    subset = _base_cp(df).set_index("ticker").reindex(ISSUERS)
    columns = ["scope1_tco2e", "scope2_tco2e", "scope3_tco2e"]
    raw = subset[columns].to_numpy(dtype=float)
    values = np.log10(1.0 + raw)

    fig, ax = plt.subplots(figsize=(9.5, 6.5))
    image = ax.imshow(values, cmap="YlGnBu", aspect="auto", vmin=0)
    ax.set_xticks(np.arange(3), ["Scope 1", "Scope 2", "Scope 3"])
    ax.set_yticks(np.arange(len(ISSUERS)), ISSUERS)
    for i in range(raw.shape[0]):
        for j in range(raw.shape[1]):
            amount = raw[i, j]
            label = "N/A" if np.isnan(amount) else (f"{amount/1_000_000:.1f}m" if amount >= 1_000_000 else f"{amount/1_000:.0f}k")
            ax.text(j, i, label, ha="center", va="center", color="white" if values[i, j] > 5 else INK, fontsize=9, fontweight="bold")
    cbar = fig.colorbar(image, ax=ax, fraction=0.035, pad=0.03)
    cbar.set_label("log10(1 + reported tCO₂e)")
    ax.set_title("Reported emissions entering transition-cost sensitivity", loc="left", fontsize=17, fontweight="bold", pad=28)
    _subtitle(ax, "Issuer-reported 2024 Scope 1, 2 and 3 evidence; boundary differences remain material")
    for spine in ax.spines.values():
        spine.set_visible(False)
    _footer(fig, release_id)
    fig.subplots_adjust(bottom=0.12, top=0.82, left=0.12, right=0.9)
    _save(fig, output)


def chart_physical_exposure(df: pd.DataFrame, output: Path, release_id: str) -> None:
    subset = _base_cp(df).copy()
    order = {"High": 0, "Medium": 1, "Low": 2, "Unverified": 3}
    subset["confidence_order"] = subset["physical_data_confidence"].map(order)
    subset = subset.sort_values(["confidence_order", "facility_match_coverage_pct"], ascending=[True, False])
    y = np.arange(len(subset))
    coverage = subset["facility_match_coverage_pct"].fillna(0.0).to_numpy(dtype=float)
    confidence_colors = {"High": GREEN, "Medium": GOLD, "Low": RED, "Unverified": "#A9B1BA"}
    colors = [confidence_colors.get(value, MUTED) for value in subset["physical_data_confidence"]]

    fig, ax = plt.subplots(figsize=(11.5, 6.6))
    ax.barh(y, coverage, color=colors, height=0.62)
    ax.set_yticks(y, subset["ticker"])
    ax.invert_yaxis()
    for yi, (_, row) in zip(y, subset.iterrows()):
        if row["physical_data_confidence"] == "Unverified":
            label = "Unverified — FEMA proxy; no issuer facilities"
            xloc = 1.5
        else:
            label = f"{row['facility_match_coverage_pct']:.0f}%  {int(row['fema_eal_matches'])}/{int(row['facility_count'])}  {row['physical_data_confidence']}"
            xloc = min(float(row["facility_match_coverage_pct"]) + 1.5, 102)
        ax.text(xloc, yi, label, va="center", ha="left", color=INK, fontsize=9)
    ax.set_xlim(0, 118)
    ax.set_xlabel("Issuer facility-to-FEMA county match coverage (%)")
    ax.set_title("Physical-risk confidence is not equal across issuers", loc="left", fontsize=17, fontweight="bold", pad=28)
    _subtitle(ax, "High >80% | Medium 50–80% | Low <50% | Unverified = no issuer facilities in the governed match file")
    ax.grid(axis="x")
    handles = [plt.Rectangle((0, 0), 1, 1, color=color) for color in confidence_colors.values()]
    ax.legend(handles, confidence_colors.keys(), frameon=False, ncol=4, loc="lower center", bbox_to_anchor=(0.5, -0.19))
    _footer(fig, release_id)
    fig.subplots_adjust(bottom=0.2, top=0.83, left=0.11, right=0.98)
    _save(fig, output)


def chart_duke_bridge(df: pd.DataFrame, output: Path, release_id: str) -> None:
    row = _base_cp(df)
    row = row[row["ticker"] == "DUK"].iloc[0]
    labels = ["Reference\nFCFF", "Transition", "Physical", "Macro /\nsupply", "Target\nFCFF"]
    baseline = float(row["reference_terminal_fcff_usd"]) / 1e9
    transition_cost = float(row["transition_terminal_cost_usd"])
    physical_cost = float(row["physical_terminal_cost_usd"])
    macro_supply_cost = float(row["macro_supply_terminal_cost_usd"])
    deltas = [
        -transition_cost / 1e9,
        -physical_cost / 1e9,
        -macro_supply_cost / 1e9,
    ]
    scenario = float(row["target_terminal_fcff_usd"]) / 1e9
    starts = [0, baseline, baseline + deltas[0], baseline + sum(deltas[:2]), 0]
    heights = [baseline, deltas[0], deltas[1], deltas[2], scenario]
    colors = [TEAL, GOLD, RED, NAVY, TEAL]

    fig, ax = plt.subplots(figsize=(11.2, 6.4))
    for i, (start, height, color) in enumerate(zip(starts, heights, colors)):
        ax.bar(i, height, bottom=start, color=color, width=0.62)
        end = start + height
        label_y = max(start, end) + (0.018 if i in (1, 2, 3) else 0.035)
        ax.text(i, label_y, f"{height:+.3f}bn" if i not in (0, 4) else f"{height:.3f}bn", ha="center", va="bottom", color=INK, fontsize=9, fontweight="bold")
        if i < 4:
            ax.plot([i + 0.31, i + 0.69], [end, end], color=GRID, linewidth=1)
    ax.set_xticks(np.arange(5), labels)
    ax.set_ylabel("2050 annual FCFF (USD billions)")
    ax.set_ylim(0, baseline * 1.15)
    ax.set_title("DUK example: scenario channels meet in terminal FCFF", loc="left", fontsize=17, fontweight="bold", pad=28)
    _subtitle(ax, f"Current Policies vs baseline | Base demonstration assumptions—not issuer observations | Enterprise-value sensitivity {row['value_impact_pct']:+.2f}%")
    ax.grid(axis="y")
    _footer(fig, release_id)
    fig.subplots_adjust(bottom=0.15, top=0.83, left=0.11, right=0.98)
    _save(fig, output)


def chart_net_zero_range(df: pd.DataFrame, output: Path, release_id: str) -> None:
    subset = df[df["scenario_pair_key"] == "nz_vs_baseline"].copy()
    pivot = subset.pivot(index="ticker", columns="assumption_case", values="value_impact_pct")
    pivot = pivot.sort_values("base")
    y = np.arange(len(pivot))
    base = pivot["base"].to_numpy(dtype=float)
    low_bound = np.minimum(pivot["low"], pivot["high"]).to_numpy(dtype=float)
    high_bound = np.maximum(pivot["low"], pivot["high"]).to_numpy(dtype=float)
    xerr = np.vstack((base - low_bound, high_bound - base))

    fig, ax = plt.subplots(figsize=(11.5, 6.4))
    ax.errorbar(base, y, xerr=xerr, fmt="o", color=NAVY, ecolor=GRID, elinewidth=7, capsize=0, markersize=7, zorder=3)
    ax.axvline(0, color=INK, linewidth=0.8)
    ax.axvline(-100, color=RED, linewidth=1.2, linestyle="--")
    ax.set_yticks(y, pivot.index)
    ax.set_xlabel("Discounted enterprise-value impact (%)")
    ax.set_title("Net Zero results are ranges—not point estimates", loc="left", fontsize=17, fontweight="bold", pad=28)
    _subtitle(ax, "Net Zero 2050 versus baseline | Low, Base and High demonstration assumptions—not issuer observations")
    ax.grid(axis="x")
    for yi, val in zip(y, base):
        suffix = "†" if val <= -100 else ""
        ax.annotate(f"{val:+.2f}%{suffix}", (val, yi), xytext=(7, 0), textcoords="offset points", ha="left", va="center", color=INK, fontsize=9)
    fig.text(0.12, 0.055, "† target EV reached the model's zero-value floor; treat as a boundary stress, not a precise Climate VaR", color=MUTED, fontsize=8.5)
    _footer(fig, release_id)
    fig.subplots_adjust(bottom=0.16, top=0.83, left=0.12, right=0.98)
    _save(fig, output)


def chart_net_zero_channel_mix(df: pd.DataFrame, output: Path, release_id: str) -> None:
    subset = df[(df["scenario_pair_key"] == "nz_vs_baseline") & (df["assumption_case"] == "base")].copy()
    contribution_cols = [
        "transition_value_contribution_pct",
        "physical_value_contribution_pct",
        "macro_supply_value_contribution_pct",
    ]
    denominator = subset[contribution_cols].abs().sum(axis=1).replace(0, np.nan)
    for column in contribution_cols:
        subset[column + "_share"] = subset[column].abs() / denominator * 100.0
    subset = subset.sort_values("transition_value_contribution_pct_share", ascending=False)
    y = np.arange(len(subset))
    left = np.zeros(len(subset))
    series = (
        ("transition_value_contribution_pct_share", "Transition", GOLD),
        ("physical_value_contribution_pct_share", "Physical", RED),
        ("macro_supply_value_contribution_pct_share", "Macro / supply", NAVY),
    )

    fig, ax = plt.subplots(figsize=(11.5, 6.4))
    for column, label, color in series:
        values = subset[column].to_numpy(dtype=float)
        ax.barh(y, values, left=left, color=color, label=label, height=0.62)
        left += values
    ax.set_yticks(y, subset["ticker"])
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of absolute modeled value impact (%)")
    ax.set_title("Net Zero separates transition stories from broader climate exposure", loc="left", fontsize=17, fontweight="bold", pad=28)
    _subtitle(ax, "Base demonstration assumptions—not issuer observations | Absolute channel shares sum to 100% for each issuer")
    ax.grid(axis="x")
    ax.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(0.5, -0.18))
    _footer(fig, release_id)
    fig.subplots_adjust(bottom=0.2, top=0.83, left=0.11, right=0.98)
    _save(fig, output)


def chart_extreme_diagnostic(df: pd.DataFrame, output: Path, release_id: str) -> None:
    subset = df[(df["scenario_pair_key"] == "nz_vs_baseline") & (df["assumption_case"] == "base")].copy()
    subset["terminal_stress_pct"] = (
        subset["transition_terminal_cost_usd"]
        + subset["physical_terminal_cost_usd"]
        + subset["macro_supply_terminal_cost_usd"]
    ) / subset["reference_terminal_fcff_usd"] * 100.0
    subset = subset.sort_values("terminal_stress_pct")
    y = np.arange(len(subset))
    colors = [RED if value >= 100 else (GOLD if value >= 50 else NAVY) for value in subset["terminal_stress_pct"]]

    fig, ax = plt.subplots(figsize=(11.5, 6.4))
    ax.barh(y, subset["terminal_stress_pct"], color=colors, height=0.62)
    ax.axvline(100, color=RED, linewidth=1.2, linestyle="--")
    ax.text(101, -0.65, "stress equals reference FCFF", color=RED, fontsize=8.5, ha="left")
    ax.set_yticks(y, subset["ticker"])
    ax.set_xlabel("2050 terminal channel stress / reference terminal FCFF (%)")
    ax.set_title("DUK reveals the model's nonlinear boundary condition", loc="left", fontsize=17, fontweight="bold", pad=28)
    _subtitle(ax, "Net Zero 2050 versus baseline | Base demonstration assumptions—not issuer observations | Values above 100% can trigger the EV floor")
    ax.grid(axis="x")
    for yi, value, floor in zip(y, subset["terminal_stress_pct"], subset["target_ev_floor_flag"]):
        label = f"{value:.1f}%" + ("  target EV floor" if floor else "")
        ax.text(value + 3, yi, label, va="center", ha="left", color=INK, fontsize=9)
    _footer(fig, release_id)
    fig.subplots_adjust(bottom=0.13, top=0.83, left=0.11, right=0.98)
    _save(fig, output)


def chart_duke_provenance(df: pd.DataFrame, output: Path, release_id: str) -> None:
    row = _base_cp(df)
    row = row[row["ticker"] == "DUK"].iloc[0]
    fig, ax = plt.subplots(figsize=(12.4, 6.6))
    ax.set_xlim(0, 12.4)
    ax.set_ylim(0, 6.6)
    ax.axis("off")
    ax.set_title("DUK model data provenance", loc="left", fontsize=18, fontweight="bold", pad=18)
    ax.text(0, 6.14, "Each output is traceable to observed data, scenario pathways, explicit demo assumptions, or derived calculations.", color=MUTED, fontsize=9.5)

    boxes = [
        (0.0, NAVY, "OBSERVED DATA\nSEC CFO / CapEx / PP&E\nEPA emissions\nFEMA EAL + 48/49 matches"),
        (3.1, TEAL, "SCENARIO PATHS\nNGFS / CIE carbon\nGDP / energy\nphysical pathways"),
        (6.2, GOLD, "DEMO ASSUMPTIONS\nNot issuer-observed\nCoverage 75% · pass-through 50%\nRecovery 50% · covered PP&E 65%"),
        (9.3, GREEN, "DERIVED OUTPUTS\nThree FCFF pressure pillars\nAnnual FCFF / discount path\nEnterprise-value sensitivity"),
    ]
    for x, color, label in boxes:
        patch = plt.Rectangle((x, 3.9), 2.75, 1.55, facecolor=color, edgecolor="none")
        ax.add_patch(patch)
        ax.text(x + 1.375, 4.675, label, ha="center", va="center", color="white", fontsize=9.4, fontweight="bold")
    for x in (2.75, 5.85, 8.95):
        ax.annotate("", xy=(x + 0.35, 4.675), xytext=(x, 4.675), arrowprops={"arrowstyle": "-|>", "color": MUTED, "lw": 1.5})

    pillars = [
        (1.7, RED, "Physical", row["physical_terminal_cost_usd"]),
        (4.6, TEAL, "Transition", row["transition_terminal_cost_usd"]),
        (7.5, GOLD, "Macro / supply", row["macro_supply_terminal_cost_usd"]),
    ]
    for x, color, label, value in pillars:
        patch = plt.Rectangle((x, 1.65), 2.9, 1.25, facecolor=color, edgecolor="none")
        ax.add_patch(patch)
        ax.text(x + 1.45, 2.275, f"{label}\n${float(value)/1e6:.1f}m annual 2050 FCFF pressure", ha="center", va="center", color="white", fontsize=9.4, fontweight="bold")
    ax.annotate("", xy=(6.2, 2.95), xytext=(10.7, 3.9), arrowprops={"arrowstyle": "-|>", "color": MUTED, "lw": 1.6})

    total = sum(float(row[key]) for key in ("transition_terminal_cost_usd", "physical_terminal_cost_usd", "macro_supply_terminal_cost_usd"))
    ax.text(6.2, 1.0, f"DUK demo readout: −${total/1e6:.1f}m annual 2050 FCFF change and {row['value_impact_pct']:+.2f}% enterprise-value sensitivity.", ha="center", va="center", color=INK, fontsize=11.2, fontweight="bold")
    ax.text(6.2, 0.58, "Enterprise value only; equity value and share-price impact are not calculable without a governed EV-to-equity bridge.", ha="center", va="center", color=RED, fontsize=9.2)
    _footer(fig, release_id)
    fig.subplots_adjust(bottom=0.08, top=0.86, left=0.04, right=0.98)
    _save(fig, output)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Optional[Sequence[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError("Cannot write an empty result table.")
    fieldnames = list(fields or rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def create_contact_sheet(paths: Sequence[Path], output: Path) -> None:
    rows = math.ceil(len(paths) / 2)
    fig, axes = plt.subplots(rows, 2, figsize=(16, 4.5 * rows), facecolor="#EFF2F5")
    axes_array = np.atleast_1d(axes).flat
    for ax, path in zip(axes_array, paths):
        ax.imshow(plt.imread(path))
        ax.set_title(path.stem.replace("_", " "), loc="left", fontsize=11, fontweight="bold", color=INK)
        ax.axis("off")
    for ax in list(np.atleast_1d(axes).flat)[len(paths):]:
        ax.axis("off")
    fig.suptitle("Eight-issuer climate-model chart pack", x=0.03, y=0.995, ha="left", fontsize=22, fontweight="bold", color=INK)
    fig.text(0.03, 0.976, "Report-ready outputs generated from the governed application model", ha="left", color=MUTED, fontsize=11)
    fig.tight_layout(rect=(0.02, 0.02, 0.98, 0.95))
    _save(fig, output)


def build_outputs(output_root: Path) -> Dict[str, Any]:
    _style()
    rows = build_results()
    results_path = output_root / "data" / "eight_issuer_scenario_results_2050.csv"
    write_csv(results_path, rows)

    input_fields = [
        "ticker", "sector", "release_id", "normalized_fcff_usd", "scope1_tco2e", "scope2_tco2e", "scope3_tco2e",
        "net_ppe_usd", "facility_count", "fema_eal_matches", "facility_match_coverage_pct", "physical_data_confidence",
        "physical_evidence_type", "fema_building_eal_rate_pct", "issuer_specific_fema_rate_pct", "wacc_pct", "terminal_growth_pct",
        "policy_coverage", "pass_through", "scope2_cost_incidence", "scope3_value_chain_incidence", "annual_emissions_decline",
        "covered_ppe_share", "insurance_adaptation_recovery", "labour_cost_share", "labour_productivity_to_fcff",
        "acute_scenario_factor", "macro_cashflow_elasticity", "macro_dependency_scale", "macro_specificity", "classification",
    ]
    input_rows = [row for row in rows if row["scenario_pair_key"] == "cp_vs_baseline" and row["assumption_case"] == "base"]
    inputs_path = output_root / "data" / "eight_issuer_model_inputs.csv"
    write_csv(inputs_path, input_rows, input_fields)

    evidence_release = app.latest_eight_issuer_climate_evidence()
    source_rows = []
    for source in evidence_release.get("source_entries", []):
        source_rows.append(
            {
                "release_id": evidence_release.get("release_id"),
                "source": source.get("source"),
                "url": source.get("url"),
                "allowed_use": source.get("allowed_use") or "issuer-reported climate evidence",
                "raw_path": source.get("raw_path"),
                "sha256": source.get("sha256"),
            }
        )
    sources_path = output_root / "data" / "model_source_audit.csv"
    write_csv(sources_path, source_rows)

    release_ids = sorted({str(row["release_id"]) for row in rows if row.get("release_id")})
    release_id = ", ".join(release_ids) or "release unavailable"
    figure_dir = output_root / "figures" / "model_comparison"
    figure_paths = [
        figure_dir / "01_value_impact_range.png",
        figure_dir / "02_channel_attribution.png",
        figure_dir / "03_scenario_value_heatmap.png",
        figure_dir / "04_scenario_rank_stability.png",
        figure_dir / "05_reported_emissions.png",
        figure_dir / "06_physical_evidence.png",
        figure_dir / "07_duke_fcff_bridge.png",
        figure_dir / "08_net_zero_assumption_range.png",
        figure_dir / "09_net_zero_channel_mix.png",
        figure_dir / "10_extreme_case_diagnostic.png",
        figure_dir / "11_duke_data_provenance.png",
    ]
    frame = pd.DataFrame(rows)
    chart_value_range(frame, figure_paths[0], release_id)
    chart_channel_attribution(frame, figure_paths[1], release_id)
    chart_scenario_heatmap(frame, figure_paths[2], release_id)
    chart_rank_stability(frame, figure_paths[3], release_id)
    chart_emissions(frame, figure_paths[4], release_id)
    chart_physical_exposure(frame, figure_paths[5], release_id)
    chart_duke_bridge(frame, figure_paths[6], release_id)
    chart_net_zero_range(frame, figure_paths[7], release_id)
    chart_net_zero_channel_mix(frame, figure_paths[8], release_id)
    chart_extreme_diagnostic(frame, figure_paths[9], release_id)
    chart_duke_provenance(frame, figure_paths[10], release_id)
    contact_sheet = figure_dir / "00_contact_sheet.png"
    create_contact_sheet(figure_paths, contact_sheet)

    return {
        "rows": len(rows),
        "calculable_rows": sum(bool(row["is_calculable"]) for row in rows),
        "issuers": sorted({str(row["ticker"]) for row in rows}),
        "scenario_pairs": sorted({str(row["scenario_pair_key"]) for row in rows}),
        "release_ids": release_ids,
        "results_csv": str(results_path),
        "inputs_csv": str(inputs_path),
        "sources_csv": str(sources_path),
        "figures": [str(path) for path in figure_paths],
        "contact_sheet": str(contact_sheet),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, default=REPO_ROOT / "reports")
    args = parser.parse_args()
    summary = build_outputs(args.output_root.resolve())
    print(f"Built {summary['rows']} model rows ({summary['calculable_rows']} calculable).")
    print(f"Results: {summary['results_csv']}")
    print(f"Inputs: {summary['inputs_csv']}")
    print(f"Sources: {summary['sources_csv']}")
    print(f"Figures: {len(summary['figures'])}; contact sheet: {summary['contact_sheet']}")


if __name__ == "__main__":
    main()
