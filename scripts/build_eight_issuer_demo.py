#!/usr/bin/env python3
"""Build the governed eight-issuer client-demo financial screen."""

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import ingest_authoritative_data as base


TICKERS = ("AAPL", "CAT", "CVX", "DE", "DUK", "MSFT", "NEE", "XOM")
SECTORS = {
    "AAPL": "Technology", "CAT": "Industrials", "CVX": "Energy",
    "DE": "Industrials", "DUK": "Utilities", "MSFT": "Technology",
    "NEE": "Utilities", "XOM": "Energy",
}
CAPEX_OVERRIDES = {
    "CVX": {
        "value": 17_347_000_000,
        "source_url": "https://www.sec.gov/Archives/edgar/data/93410/000009341026000078/cvx-20251231.htm",
        "source_note": "2025 Chevron 10-K capital expenditures",
    },
    "NEE": {
        "value": 24_053_000_000,
        "source_url": "https://www.sec.gov/Archives/edgar/data/753308/000075330826000015/nee-20251231.htm",
        "source_note": "2025 NEE cash-flow statement: FPL 8,719 + NEER 15,332 + other 2 million",
    },
}


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def latest_filing(rows, ticker):
    ticker_rows = [row for row in rows if row["ticker"] == ticker and row.get("fiscal_year", "").isdigit()]
    fiscal_year = max(int(row["fiscal_year"]) for row in ticker_rows)
    filings = sorted(
        {row["adsh"] for row in ticker_rows if int(row["fiscal_year"]) == fiscal_year},
        key=lambda adsh: max(row["filed"] for row in ticker_rows if row["adsh"] == adsh),
    )
    adsh = filings[-1]
    filing_rows = [row for row in ticker_rows if row["adsh"] == adsh]
    report_period = filing_rows[0]["report_period"]
    return fiscal_year, adsh, report_period, filing_rows


def one_fact(rows, tags, report_period):
    matches = [
        row for row in rows
        if row["tag"] in tags and row["date"] == report_period and row["unit"] == "USD"
    ]
    if not matches:
        return None, None
    row = matches[0]
    return float(row["value"]), row


def build_rows(sec_rows, candidate_rows, duke_fcff):
    candidate_by_ticker = {row["ticker"]: row for row in candidate_rows}
    output = []
    for ticker in TICKERS:
        fiscal_year, adsh, report_period, filing_rows = latest_filing(sec_rows, ticker)
        cfo, cfo_row = one_fact(filing_rows, {"NetCashProvidedByUsedInOperatingActivities"}, report_period)
        capex, capex_row = one_fact(
            filing_rows,
            {"PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsForAdditionsToPropertyPlantAndEquipment"},
            report_period,
        )
        capex_source = capex_row["source_url"] if capex_row else ""
        capex_note = "SEC structured filing fact" if capex_row else ""
        if ticker in CAPEX_OVERRIDES:
            capex = float(CAPEX_OVERRIDES[ticker]["value"])
            capex_source = CAPEX_OVERRIDES[ticker]["source_url"]
            capex_note = CAPEX_OVERRIDES[ticker]["source_note"]
        if cfo is None or capex is None:
            raise RuntimeError(f"Incomplete 2025 FCF baseline for {ticker}")
        screen = candidate_by_ticker.get(ticker, {})
        parent_records = int(screen.get("parent_records") or 0)
        direct_matches = int(screen.get("direct_emitter_matches") or 0)
        output.append({
            "ticker": ticker,
            "sector": SECTORS[ticker],
            "fiscal_year": fiscal_year,
            "adsh": adsh,
            "report_period": report_period,
            "operating_cash_flow_usd": cfo,
            "capital_expenditure_usd": capex,
            "free_cash_flow_usd": cfo - capex,
            "fcf_formula": "operating cash flow - capital expenditure",
            "duke_fcff_usd": duke_fcff.get("fcff", "") if ticker == "DUK" else "",
            "parent_facility_records": parent_records,
            "direct_emitter_matches": direct_matches,
            "transition_input": "Company data" if direct_matches else "Industry estimate",
            "physical_input": "Industry estimate",
            "financial_input": "Company data",
            "cfo_source_url": cfo_row["source_url"],
            "capex_source_url": capex_source,
            "capex_source_note": capex_note,
            "demo_role": "Deep dive" if ticker == "DUK" else "Screening comparison",
        })
    return output


def build_release(release_id, sec_release_id, evidence_release_id):
    release_dir = base.RELEASES_ROOT / release_id
    manifest = base.load_manifest(release_dir, release_id)
    sec_path = base.RELEASES_ROOT / sec_release_id / "processed" / "sec_financial_facts_2009q1_2026q1.csv"
    evidence_dir = base.RELEASES_ROOT / evidence_release_id / "processed"
    candidate_path = evidence_dir / "pilot_candidate_screen.csv"
    duke_fcff_path = evidence_dir / "duk_sec_fcff_bridge_2025.csv"
    duke_fcff = read_csv(duke_fcff_path)[0]
    rows = build_rows(read_csv(sec_path), read_csv(candidate_path), duke_fcff)
    output_path = release_dir / "processed" / "eight_issuer_demo_2025.csv"
    base.write_csv_immutable(output_path, list(rows[0]), rows)
    output_hash = hashlib.sha256(output_path.read_bytes()).hexdigest()
    manifest["eight_issuer_demo"] = {
        "tickers": list(TICKERS),
        "record_count": len(rows),
        "processed_path": str(output_path.relative_to(base.PROJECT_ROOT)),
        "processed_sha256": output_hash,
        "sec_source_release_id": sec_release_id,
        "evidence_source_release_id": evidence_release_id,
        "allowed_use": "client prototype screening and DUK deep dive",
        "fcf_definition": "operating cash flow - capital expenditure",
    }
    base.save_manifest(release_dir, manifest)
    return manifest["eight_issuer_demo"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--sec-release-id", required=True)
    parser.add_argument("--evidence-release-id", required=True)
    args = parser.parse_args()
    result = build_release(args.release_id, args.sec_release_id, args.evidence_release_id)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
