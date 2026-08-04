#!/usr/bin/env python3
"""Build a traceable US exchange-listed issuer/sector reference master.

No API key is required. SEC supplies CIK/name/exchange identity fields and the
Nasdaq stock screener supplies reference sector/industry classifications.
The resulting sector mapping is research metadata, not issuer-verified climate
exposure or financial-risk data.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
LATEST_MASTER = DATA_DIR / "issuer_sector_master.csv"
SEC_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
NASDAQ_URL = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=20&offset=0&download=true"

SECTOR_ALIASES = {
    "Basic Materials": "Basic Materials",
    "Consumer Discretionary": "Consumer Cyclical",
    "Consumer Staples": "Consumer Defensive",
    "Energy": "Energy",
    "Finance": "Financials",
    "Financial Services": "Financials",
    "Health Care": "Healthcare",
    "Healthcare": "Healthcare",
    "Industrials": "Industrials",
    "Real Estate": "Real Estate",
    "Technology": "Technology",
    "Telecommunications": "Communication Services",
    "Communication Services": "Communication Services",
    "Utilities": "Utilities",
}

DISQUALIFYING_NAME_MARKERS = (
    " WARRANT ",
    " WARRANTS ",
    " RIGHTS ",
    " RIGHT ",
    " UNIT ",
    " UNITS ",
    " PREFERRED ",
    " PREFERENCE ",
)

OUTPUT_FIELDS = (
    "ticker",
    "company_name",
    "security_name",
    "cik",
    "exchange",
    "country",
    "sector_raw",
    "sector_canonical",
    "industry",
    "market_cap_usd",
    "quote_type",
    "mapping_status",
    "sec_matched",
    "as_of",
    "sector_source_url",
    "entity_source_url",
)


def normalize_ticker(value):
    return str(value or "").strip().upper().replace(".", "-")


def fetch_bytes(url, headers, timeout=90):
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        return response.read()


def sha256_bytes(payload):
    return hashlib.sha256(payload).hexdigest()


def parse_market_cap(value):
    raw = str(value or "").replace(",", "").replace("$", "").strip()
    try:
        return str(round(float(raw), 2)) if raw else ""
    except ValueError:
        return ""


def mapping_status(security_name, sector_canonical):
    upper_name = f" {str(security_name or '').upper()} "
    if any(marker in upper_name for marker in DISQUALIFYING_NAME_MARKERS):
        return "rejected_non_common_security"
    if not sector_canonical:
        return "rejected_missing_or_unsupported_sector"
    return "eligible_equity_reference"


def main():
    retrieved = datetime.now(timezone.utc)
    as_of = retrieved.strftime("%Y-%m-%d")
    release_id = f"issuer-sector-{retrieved.strftime('%Y%m%dT%H%M%SZ')}"
    release_dir = DATA_DIR / "issuer_sector" / release_id
    release_dir.mkdir(parents=True, exist_ok=False)

    sec_user_agent = os.environ.get(
        "SEC_USER_AGENT",
        "ClimateFinanceResearch/1.0 github.com/zilunhe713-ops/Climate-Finance-Trading-Platform",
    )
    sec_headers = {
        "User-Agent": sec_user_agent,
        "Accept": "application/json",
        "Accept-Encoding": "identity",
    }
    nasdaq_headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ClimateFinanceResearch/1.0)",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nasdaq.com/market-activity/stocks/screener",
    }

    sec_raw = fetch_bytes(SEC_URL, sec_headers)
    nasdaq_raw = fetch_bytes(NASDAQ_URL, nasdaq_headers)
    (release_dir / "sec_company_tickers_exchange.json").write_bytes(sec_raw)
    (release_dir / "nasdaq_stock_screener.json").write_bytes(nasdaq_raw)

    sec_payload = json.loads(sec_raw)
    sec_fields = sec_payload.get("fields") or []
    sec_by_ticker = {}
    for values in sec_payload.get("data") or []:
        row = dict(zip(sec_fields, values))
        ticker = normalize_ticker(row.get("ticker"))
        if ticker and ticker not in sec_by_ticker:
            sec_by_ticker[ticker] = row

    nasdaq_payload = json.loads(nasdaq_raw)
    nasdaq_rows = ((nasdaq_payload.get("data") or {}).get("rows") or [])
    output_rows = []
    for source_row in nasdaq_rows:
        ticker = normalize_ticker(source_row.get("symbol"))
        if not ticker:
            continue
        sec_row = sec_by_ticker.get(ticker) or {}
        raw_sector = str(source_row.get("sector") or "").strip()
        canonical_sector = SECTOR_ALIASES.get(raw_sector, "")
        security_name = str(source_row.get("name") or "").strip()
        status = mapping_status(security_name, canonical_sector)
        output_rows.append(
            {
                "ticker": ticker,
                "company_name": str(sec_row.get("name") or security_name).strip(),
                "security_name": security_name,
                "cik": str(sec_row.get("cik") or ""),
                "exchange": str(sec_row.get("exchange") or "").strip(),
                "country": str(source_row.get("country") or "").strip(),
                "sector_raw": raw_sector,
                "sector_canonical": canonical_sector,
                "industry": str(source_row.get("industry") or "").strip(),
                "market_cap_usd": parse_market_cap(source_row.get("marketCap")),
                "quote_type": "EQUITY" if status == "eligible_equity_reference" else "",
                "mapping_status": status,
                "sec_matched": "true" if sec_row else "false",
                "as_of": as_of,
                "sector_source_url": NASDAQ_URL,
                "entity_source_url": SEC_URL if sec_row else "",
            }
        )

    output_rows.sort(key=lambda row: row["ticker"])
    release_master = release_dir / "issuer_sector_master.csv"
    for path in (release_master, LATEST_MASTER):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
            writer.writeheader()
            writer.writerows(output_rows)

    latest_bytes = LATEST_MASTER.read_bytes()
    counts = {
        "sec_rows": len(sec_payload.get("data") or []),
        "nasdaq_rows": len(nasdaq_rows),
        "master_rows": len(output_rows),
        "eligible_equity_reference": sum(
            row["mapping_status"] == "eligible_equity_reference" for row in output_rows
        ),
        "sec_matched": sum(row["sec_matched"] == "true" for row in output_rows),
        "rejected_non_common_security": sum(
            row["mapping_status"] == "rejected_non_common_security" for row in output_rows
        ),
        "rejected_missing_or_unsupported_sector": sum(
            row["mapping_status"] == "rejected_missing_or_unsupported_sector"
            for row in output_rows
        ),
    }
    manifest = {
        "release_id": release_id,
        "retrieved_at": retrieved.isoformat(),
        "coverage_claim": "US exchange-listed equities present in the Nasdaq stock screener; not complete global coverage",
        "classification_status": "reference metadata; not issuer-verified",
        "sources": {
            "sec": {
                "url": SEC_URL,
                "sha256": sha256_bytes(sec_raw),
                "bytes": len(sec_raw),
            },
            "nasdaq": {
                "url": NASDAQ_URL,
                "sha256": sha256_bytes(nasdaq_raw),
                "bytes": len(nasdaq_raw),
            },
        },
        "output": {
            "path": str(LATEST_MASTER.relative_to(PROJECT_DIR)),
            "sha256": sha256_bytes(latest_bytes),
            "bytes": len(latest_bytes),
        },
        "counts": counts,
    }
    manifest_path = release_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (DATA_DIR / "issuer_sector_master_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
