#!/usr/bin/env python3
"""Build comparable public-evidence screens for the eight client-demo issuers.

The outputs deliberately separate a calculable gross carbon-price sensitivity
from a physical-exposure screen and from financial losses that remain blocked.
"""

import argparse
import csv
import hashlib
import json
import shutil
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import build_duke_pilot as duke
from scripts import ingest_authoritative_data as base


TICKERS = ("AAPL", "CAT", "CVX", "DE", "DUK", "MSFT", "NEE", "XOM")
RETRIEVED_AT = "2026-08-04T19:00:00Z"

# Comparable reported Scope 1 boundary. Values are not silently replaced with
# EPA facility totals because GHGRP is an incomplete U.S. reporting boundary.
REPORTED_SCOPE1 = {
    "AAPL": (2024, 55_200, "Apple 2025 Environmental Progress Report", "https://www.apple.com/environment/pdf/Apple_Environmental_Progress_Report_2025.pdf", "apple.pdf"),
    "CAT": (2024, 680_000, "Caterpillar sustainability data 2025", "https://s7d2.scene7.com/is/content/Caterpillar/CM20260508-cac43-ec231", "cat-data.pdf"),
    "CVX": (2024, 53_000_000, "Chevron Sustainability Highlights 2024", "https://www.chevron.com/-/media/shared-media/documents/chevron-sustainability-highlights-2024.pdf", None),
    "DE": (2024, 353_900, "John Deere 2024 Sustainability Disclosure", "https://www.deere.com/assets/pdfs/common/our-company/sustainability/data-book-2024.pdf", None),
    "DUK": (2024, 79_756_000, "Duke Energy 2025 Sustainability Metrics", "https://s201.q4cdn.com/583395453/files/doc_downloads/2026/2025-Sustainability-Metrics-Center.pdf", "duk-metrics.pdf"),
    "MSFT": (2024, 143_510, "Microsoft 2025 Environmental Data Fact Sheet", "https://aka.ms/SustainabilityFactsheet2025", "microsoft-fact-sheet.pdf"),
    "NEE": (2024, 42_674_351, "NextEra Energy 2025 Data Appendix", "https://www.investor.nexteraenergy.com/~/media/Files/N/NEE-IR/Sustainability/2025/Data%20Appendix.pdf", "nextera.pdf"),
    "XOM": (2024, 104_000_000, "ExxonMobil Metrics and Data", "https://corporate.exxonmobil.com/what-we-do/energy-supply/emissions-and-efficiency/metrics-and-data", None),
}

SCOPE1_LOCATIONS = {
    "AAPL": "Independent assurance table, FY2024 Scope 1",
    "CAT": "Operations GHG performance table, 2024 Scope 1",
    "CVX": "2024 GHG emissions metrics, Scope 1",
    "DE": "2024 environmental metrics table, Scope 1",
    "DUK": "2024 Scope 1 component table; sum of reported electric, gas, fleet, ancillary, SF6, refrigerant and building-gas rows",
    "MSFT": "FY24 emissions table, Scope 1",
    "NEE": "2025 Data Appendix, 2024 Scope 1",
    "XOM": "2024 operated GHG emissions table, Scope 1",
}

DISCLOSED_PHYSICAL = {
    "AAPL": {
        "metric": "corporate water use in high-basin-stress areas",
        "value": 70.0, "unit": "percent", "year": 2024,
        "source_url": REPORTED_SCOPE1["AAPL"][3],
        "interpretation": "company-disclosed operational water exposure; not financial loss",
    },
    "CAT": {
        "metric": "high-water-risk facilities meeting all water-management elements",
        "value": 77.0, "unit": "percent", "year": 2025,
        "source_url": REPORTED_SCOPE1["CAT"][3],
        "interpretation": "company-disclosed resilience coverage; not hazard or financial loss",
    },
    "MSFT": {
        "metric": "water withdrawals from areas with water stress",
        "value": 46.0, "unit": "percent", "year": 2024,
        "source_url": REPORTED_SCOPE1["MSFT"][3],
        "interpretation": "company-disclosed operational water exposure; not financial loss",
    },
}


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_rows(path, rows):
    if not rows:
        raise RuntimeError(f"No rows produced for {path}")
    base.write_csv_immutable(path, list(rows[0]), rows)


def weighted_mean(rows, value_key, weight_key):
    pairs = []
    for row in rows:
        value = duke.finite_number(row.get(value_key))
        weight = duke.finite_number(row.get(weight_key))
        if value is not None and weight is not None and weight > 0:
            pairs.append((value, weight))
    if not pairs:
        return None
    return sum(value * weight for value, weight in pairs) / sum(weight for _, weight in pairs)


def build_release(release_id, evidence_release_id, demo_release_id, ngfs_release_id, report_dir):
    release_dir = base.RELEASES_ROOT / release_id
    manifest = base.load_manifest(release_dir, release_id)
    report_dir = Path(report_dir)

    source_release = base.RELEASES_ROOT / evidence_release_id
    parent_path = source_release / "raw" / "epa" / "ghgp_data_parent_company.xlsb"
    summary_zip = source_release / "raw" / "epa" / "2023_data_summary_spreadsheets.zip"
    fema_raw = sorted((source_release / "raw" / "fema_nri").glob("*.json"))
    parent_rows = duke.read_parent_rows(parent_path)
    direct_rows = duke.read_ghgrp_direct_rows(summary_zip.read_bytes())
    counties = []
    for path in fema_raw:
        payload = json.loads(path.read_text(encoding="utf-8"))
        counties.extend((feature.get("attributes") or {}) for feature in payload.get("features", []))

    facilities, facility_hazards = [], []
    for ticker in TICKERS:
        issuer_facilities = duke.join_parent_emissions(parent_rows, direct_rows, ticker=ticker)
        facilities.extend(issuer_facilities)
        weights = {row["epa_facility_id"]: row.get("reported_direct_tco2e") for row in issuer_facilities}
        issuer_hazards = duke.join_fema_context(issuer_facilities, counties)
        for row in issuer_hazards:
            row["reported_direct_tco2e"] = weights.get(row["epa_facility_id"])
        facility_hazards.extend(issuer_hazards)

    facility_path = release_dir / "processed" / "eight_issuer_epa_facilities_2023.csv"
    hazard_path = release_dir / "processed" / "eight_issuer_fema_context_2025.csv"
    write_rows(facility_path, facilities)
    write_rows(hazard_path, facility_hazards)

    scope_rows = []
    for ticker, (year, tonnes, title, source_url, local_name) in REPORTED_SCOPE1.items():
        raw_path = ""
        raw_sha = ""
        if local_name and (report_dir / local_name).is_file():
            target = release_dir / "raw" / "issuer_reports" / local_name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(report_dir / local_name, target)
            raw_path = str(target.relative_to(PROJECT_ROOT))
            raw_sha = hashlib.sha256(target.read_bytes()).hexdigest()
        scope_rows.append({
            "ticker": ticker, "reporting_year": year,
            "scope1_tco2e": tonnes, "unit": "metric tCO2e",
            "organizational_boundary": "company-reported Scope 1",
            "source_title": title, "source_url": source_url,
            "source_location": SCOPE1_LOCATIONS[ticker],
            "retrieved_at": RETRIEVED_AT, "raw_path": raw_path,
            "raw_sha256": raw_sha,
            "allowed_use": "gross carbon-price sensitivity on a common Scope 1 boundary",
            "limitation": "not covered emissions and not net transition cost",
        })
        base.upsert_manifest_entry(manifest, {
            "source_id": f"SRC-ISSUER-{ticker}-SCOPE1-2024",
            "source_url": source_url, "retrieved_at": RETRIEVED_AT,
            "source_class": "issuer-published sustainability disclosure",
            "source_vintage": str(year), "source_title": title,
            "source_location": SCOPE1_LOCATIONS[ticker],
            "raw_path": raw_path or None, "raw_sha256": raw_sha or None,
            "allowed_use": "reported Scope 1 quantity for a uniform analytical carbon-price sensitivity",
            "limitation": "organizational and geographic boundaries vary; this is not verified covered emissions or net transition cost",
        })
    scope_path = release_dir / "processed" / "eight_issuer_reported_scope1.csv"
    write_rows(scope_path, scope_rows)

    demo_rows = read_csv(base.RELEASES_ROOT / demo_release_id / "processed" / "eight_issuer_demo_2025.csv")
    demo = {row["ticker"]: row for row in demo_rows}
    ngfs_rows = read_csv(base.RELEASES_ROOT / ngfs_release_id / "processed" / "ngfs_5_1_transition_usa_to_2050.csv")
    current_prices = [float(row["value"]) for row in ngfs_rows if row["scenario"] == "Current Policies" and row["variable"] == "Price|Carbon" and row["year"] == "2050"]
    if not current_prices:
        raise RuntimeError("Current Policies 2050 carbon price is missing")
    current_price = statistics.median(current_prices)

    transition_rows = []
    for row in scope_rows:
        ticker = row["ticker"]
        tonnes = float(row["scope1_tco2e"])
        fcf = float(demo[ticker]["duke_fcff_usd"] or demo[ticker]["free_cash_flow_usd"])
        gross = tonnes * current_price
        transition_rows.append({
            "ticker": ticker, "scenario": "Current Policies",
            "reference": "Climate-agnostic analytical reference",
            "horizon": 2050, "scope1_tco2e": tonnes,
            "carbon_price_delta_usd2010_per_tco2": current_price,
            "gross_sensitivity_usd": gross,
            "cash_flow_baseline_usd": fcf,
            "gross_sensitivity_to_cash_flow": "" if fcf == 0 else gross / fcf,
            "formula": "reported Scope 1 x NGFS target-reference carbon-price delta",
            "status": "calculated gross sensitivity; net transition cost not calculable",
            "missing_net_cost_fields": "covered emissions; jurisdiction; free allocation; pass-through; future emissions path",
        })
    transition_path = release_dir / "processed" / "eight_issuer_transition_sensitivity_2050.csv"
    write_rows(transition_path, transition_rows)

    physical_rows = []
    for ticker in TICKERS:
        issuer_facilities = [row for row in facilities if row["ticker"] == ticker]
        issuer_hazards = [row for row in facility_hazards if row["ticker"] == ticker]
        matched = [row for row in issuer_hazards if str(row.get("hazard_match_status", "")).startswith("matched")]
        disclosure = DISCLOSED_PHYSICAL.get(ticker, {})
        physical_rows.append({
            "ticker": ticker,
            "epa_parent_facilities": len(issuer_facilities),
            "epa_direct_emitter_matches": sum(row.get("reported_direct_tco2e") is not None for row in issuer_facilities),
            "fema_county_matches": len(matched),
            "emissions_weighted_county_nri_score": weighted_mean(matched, "county_nri_score", "reported_direct_tco2e"),
            "weighting_method": "EPA reported direct tCO2e" if matched else "",
            "disclosed_metric": disclosure.get("metric", ""),
            "disclosed_value": disclosure.get("value", ""),
            "disclosed_unit": disclosure.get("unit", ""),
            "disclosed_year": disclosure.get("year", ""),
            "disclosed_source_url": disclosure.get("source_url", ""),
            "screen_status": "facility-to-county hazard screen" if matched else ("company-disclosed operational exposure screen" if disclosure else "not calculable"),
            "financial_loss_status": "not calculable",
            "missing_financial_fields": "asset replacement value; asset-type damage function; business interruption; insurance/recovery",
            "allowed_use": disclosure.get("interpretation", "county hazard context; not issuer probability or financial loss"),
        })
    physical_path = release_dir / "processed" / "eight_issuer_physical_exposure_summary.csv"
    write_rows(physical_path, physical_rows)

    transmission_rows = []
    for row in demo_rows:
        cfo = float(row["operating_cash_flow_usd"])
        capex = float(row["capital_expenditure_usd"])
        transmission_rows.append({
            "ticker": row["ticker"], "fiscal_year": row["fiscal_year"],
            "operating_cash_flow_usd": cfo, "capital_expenditure_usd": capex,
            "free_cash_flow_usd": float(row["free_cash_flow_usd"]),
            "capex_to_operating_cash_flow": "" if cfo == 0 else capex / cfo,
            "observed_use": "financial capacity/dependency context only",
            "macro_supply_loss_status": "not calculable",
            "missing_scenario_join": "issuer revenue geography; supplier/customer economic weights; BEA industry join; compatible target-reference demand/input-price shock",
            "source_url": row["cfo_source_url"],
        })
    transmission_path = release_dir / "processed" / "eight_issuer_financial_transmission_evidence.csv"
    write_rows(transmission_path, transmission_rows)

    processed = [scope_path, transition_path, facility_path, hazard_path, physical_path, transmission_path]
    manifest["eight_issuer_public_evidence"] = {
        "tickers": list(TICKERS), "record_count": 8,
        "evidence_release_id": evidence_release_id,
        "demo_release_id": demo_release_id,
        "ngfs_release_id": ngfs_release_id,
        "processed_paths": [str(path.relative_to(PROJECT_ROOT)) for path in processed],
        "processed_sha256": {str(path.relative_to(PROJECT_ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in processed},
        "transition_status": "gross Scope 1 carbon-price sensitivity calculated for eight issuers",
        "physical_status": "exposure screens only; financial loss not calculable",
        "macro_supply_status": "financial context loaded; scenario loss not calculable",
        "allowed_use": "long-horizon public-data issuer comparison and data-gap review; not Climate VaR or investment recommendation",
    }
    base.save_manifest(release_dir, manifest)
    return manifest["eight_issuer_public_evidence"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--evidence-release-id", required=True)
    parser.add_argument("--demo-release-id", required=True)
    parser.add_argument("--ngfs-release-id", required=True)
    parser.add_argument("--report-dir", required=True)
    args = parser.parse_args()
    result = build_release(args.release_id, args.evidence_release_id, args.demo_release_id, args.ngfs_release_id, args.report_dir)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
