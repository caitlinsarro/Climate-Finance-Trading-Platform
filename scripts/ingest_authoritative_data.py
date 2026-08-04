#!/usr/bin/env python3
"""Controlled ingestion of authoritative public climate-risk inputs.

The script never writes credentials to files or logs. Raw downloads are
immutable within a release: if an existing release path has different bytes,
the script refuses to overwrite it and requires a new release ID.
"""

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RELEASES_ROOT = PROJECT_ROOT / "data" / "releases"
DEFAULT_USER_AGENT = (
    "Climate-Finance-Trading-Platform/1.0 "
    "https://github.com/zilunhe713-ops/Climate-Finance-Trading-Platform"
)
NWS_ACTIVE_ALERTS_URL = "https://api.weather.gov/alerts/active"
NOAA_STORM_INDEX_URL = "https://www.ncei.noaa.gov/pub/data/swdi/stormevents/csvfiles/"
TREASURY_YIELD_CURVE_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
    "?data=daily_treasury_yield_curve&field_tdr_date_value={year}"
)
SEC_FINANCIAL_STATEMENT_URL = (
    "https://www.sec.gov/files/dera/data/financial-statement-data-sets/{year}q{quarter}.zip"
)
NGFS_GUEST_TOKEN_URL = (
    "https://api.manager.ece.iiasa.ac.at/legacy/anonym/IXSE_NGFS_PHASE_5?algorithm=HS256"
)
NGFS_API_BASE_URL = "https://db1.ene.iiasa.ac.at/ngfs-phase-5-api/rest/v2.1"
NGFS_EXPLORER_URL = "https://data.ene.iiasa.ac.at/ngfs/"
NGFS_RELEASE_VERSION = "5.1"
NGFS_RELEASE_DATE = "2026-03-20"
NGFS_TRANSITION_MODELS = (
    "Downscaling[GCAM 6.0 NGFS]",
    "Downscaling[MESSAGEix-GLOBIOM 2.0-M-R12-NGFS]",
    "Downscaling[REMIND-MAgPIE 3.3-4.8]",
)
NGFS_SCENARIOS = (
    "Below 2°C",
    "Current Policies",
    "Delayed transition",
    "Fragmented World",
    "Low demand",
    "Nationally Determined Contributions (NDCs)",
    "Net Zero 2050",
)
NGFS_TRANSITION_VARIABLES = (
    "Price|Carbon",
    "Final Energy|Industry",
    "Final Energy|Industry|Electricity",
    "Final Energy|Industry|Gases",
    "Final Energy|Industry|Liquids",
    "Final Energy|Industry|Solids",
)
COMPLETED_STORM_YEAR = datetime.now(timezone.utc).year - 1

SEC_FINANCIAL_CONCEPTS = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ),
    "operating_income": ("OperatingIncomeLoss",),
    "pretax_income": (
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ),
    "tax_expense": ("IncomeTaxExpenseBenefit",),
    "depreciation_amortization": (
        "DepreciationDepletionAndAmortization",
        "DepreciationDepletionAndAmortizationPropertyPlantAndEquipment",
        "DepreciationDepletionAndAmortizationAndAccretionNet",
    ),
    "capital_expenditure": (
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
    ),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "interest_expense": (
        "InterestExpenseNonOperating",
        "InterestExpense",
        "InterestAndDebtExpense",
    ),
    "debt": (
        "LongTermDebtAndFinanceLeaseObligationsCurrent",
        "LongTermDebtCurrent",
        "LongTermDebtNoncurrent",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
        "ShortTermBorrowings",
    ),
    "cash": ("CashAndCashEquivalentsAtCarryingValue",),
}
SEC_FINANCIAL_TAGS = {
    tag for tags in SEC_FINANCIAL_CONCEPTS.values() for tag in tags
}

# Current security masters can point to a successor registrant and therefore
# cannot by themselves resolve a long filing history. These aliases are
# controlled issuer identities observed in the SEC FSDS sub.txt files. They are
# additive: both the current master CIK and historical registrant CIK are kept.
SEC_HISTORICAL_CIK_ALIASES = {
    "XOM": {
        "34088": {
            "issuer_name": "EXXON MOBIL CORP",
            "source": "SEC Financial Statement Data Sets sub.txt",
            "reason": "historical registrant preceding current XOM holding-company CIK",
        },
    },
}


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def download_bytes(url, accept="*/*", timeout=60):
    user_agent = os.environ.get("SEC_USER_AGENT", DEFAULT_USER_AGENT).strip()
    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": accept,
            "Accept-Encoding": "identity",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read(), response.headers.get("Content-Type", "")


def ngfs_api_bytes(url, token, payload=None, timeout=120):
    """Call the public NGFS guest API without persisting its ephemeral token."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=data,
        method="POST" if data is not None else "GET",
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read(), response.headers.get("Content-Type", "")


def write_immutable(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_bytes()
        if existing != data:
            raise RuntimeError(
                f"Refusing to overwrite immutable release file with different bytes: {path}. "
                "Create a new release ID."
            )
        return False
    path.write_bytes(data)
    return True


def write_csv_immutable(path, headers, rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=headers, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return write_immutable(path, buffer.getvalue().encode("utf-8"))


def load_manifest(release_dir, release_id):
    manifest_path = release_dir / "manifest.json"
    if not manifest_path.exists():
        return {
            "release_id": release_id,
            "feature_id": "CFP-2026-003",
            "created_at": utc_now(),
            "source_entries": [],
            "credential_values_stored": False,
        }
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("release_id") != release_id:
        raise RuntimeError("Release manifest ID does not match target directory")
    return manifest


def save_manifest(release_dir, manifest):
    manifest["updated_at"] = utc_now()
    manifest_path = release_dir / "manifest.json"
    payload = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    if manifest_path.exists():
        manifest_path.write_bytes(payload)
    else:
        write_immutable(manifest_path, payload)


def upsert_manifest_entry(manifest, entry):
    entries = [
        existing
        for existing in manifest.get("source_entries", [])
        if existing.get("source_id") != entry.get("source_id")
    ]
    entries.append(entry)
    manifest["source_entries"] = sorted(entries, key=lambda row: row["source_id"])


def ingest_nws(release_dir, manifest):
    retrieved_at = utc_now()
    raw_bytes, content_type = download_bytes(
        NWS_ACTIVE_ALERTS_URL,
        accept="application/geo+json",
        timeout=45,
    )
    source_hash = sha256_bytes(raw_bytes)
    raw_path = release_dir / "raw" / "nws" / "active_alerts.geojson"
    write_immutable(raw_path, raw_bytes)

    payload = json.loads(raw_bytes.decode("utf-8"))
    rows = []
    for index, feature in enumerate(payload.get("features", []), start=1):
        properties = feature.get("properties") or {}
        alert_id = properties.get("id") or feature.get("id") or f"row-{index}"
        geocode = properties.get("geocode") or {}
        rows.append(
            {
                "record_id": f"NWS-{hashlib.sha256(str(alert_id).encode()).hexdigest()[:16]}",
                "alert_id": alert_id,
                "event": properties.get("event"),
                "onset": properties.get("onset"),
                "expires": properties.get("expires"),
                "severity": properties.get("severity"),
                "urgency": properties.get("urgency"),
                "certainty": properties.get("certainty"),
                "area_desc": properties.get("areaDesc"),
                "geocode": json.dumps(geocode, ensure_ascii=False, sort_keys=True),
                "source_url": alert_id if str(alert_id).startswith("http") else NWS_ACTIVE_ALERTS_URL,
                "retrieved_at": retrieved_at,
                "source_hash": source_hash,
                "quality_status": "observed official active alert",
                "allowed_use": "tactical hazard context only",
                "limitation": "Alert is not an occurrence probability, issuer exposure, or financial loss.",
            }
        )

    headers = [
        "record_id",
        "alert_id",
        "event",
        "onset",
        "expires",
        "severity",
        "urgency",
        "certainty",
        "area_desc",
        "geocode",
        "source_url",
        "retrieved_at",
        "source_hash",
        "quality_status",
        "allowed_use",
        "limitation",
    ]
    flat_path = release_dir / "processed" / "nws_alerts_flat.csv"
    write_csv_immutable(flat_path, headers, rows)
    upsert_manifest_entry(
        manifest,
        {
            "source_id": "SRC-NWS",
            "source_url": NWS_ACTIVE_ALERTS_URL,
            "retrieved_at": retrieved_at,
            "source_class": "official government",
            "raw_path": str(raw_path.relative_to(PROJECT_ROOT)),
            "processed_path": str(flat_path.relative_to(PROJECT_ROOT)),
            "raw_sha256": source_hash,
            "raw_bytes": len(raw_bytes),
            "content_type": content_type,
            "record_count": len(rows),
            "allowed_use": "tactical hazard context only",
            "limitation": "Active-alert snapshot; not a historical tape, probability, exposure, or loss.",
        },
    )
    return {"source_id": "SRC-NWS", "records": len(rows), "sha256": source_hash}


def latest_noaa_storm_url(year):
    index_bytes, _ = download_bytes(NOAA_STORM_INDEX_URL, accept="text/html", timeout=45)
    index_text = index_bytes.decode("utf-8", errors="replace")
    pattern = re.compile(
        rf"(StormEvents_details-ftp_v1\.0_d{year}_c(?P<stamp>\d{{8}})\.csv\.gz)"
    )
    candidates = [(match.group("stamp"), match.group(1)) for match in pattern.finditer(index_text)]
    if not candidates:
        raise RuntimeError(f"No NOAA Storm Events details file found for completed year {year}")
    _, filename = max(candidates)
    return NOAA_STORM_INDEX_URL + filename, filename


def ingest_noaa_storms(release_dir, manifest, year):
    source_url, filename = latest_noaa_storm_url(year)
    retrieved_at = utc_now()
    raw_bytes, content_type = download_bytes(source_url, accept="application/gzip", timeout=120)
    source_hash = sha256_bytes(raw_bytes)
    raw_path = release_dir / "raw" / "noaa_storms" / filename
    write_immutable(raw_path, raw_bytes)

    decompressed = gzip.decompress(raw_bytes).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(decompressed))
    rows = []
    for index, source in enumerate(reader, start=1):
        event_id = source.get("EVENT_ID") or f"row-{index}"
        rows.append(
            {
                "record_id": f"NOAA-STORM-{event_id}",
                "event_id": event_id,
                "event_type": source.get("EVENT_TYPE"),
                "begin_time": source.get("BEGIN_DATE_TIME"),
                "end_time": source.get("END_DATE_TIME"),
                "state": source.get("STATE"),
                "county_or_zone": source.get("CZ_NAME"),
                "latitude": source.get("BEGIN_LAT"),
                "longitude": source.get("BEGIN_LON"),
                "property_damage_reported": source.get("DAMAGE_PROPERTY"),
                "damage_unit": "USD source-coded suffix",
                "source_url": source_url,
                "retrieved_at": retrieved_at,
                "source_hash": source_hash,
                "quality_status": "official publication; source reports may be unverified",
                "limitation": "Reported damage is incomplete context and not an issuer loss estimate.",
            }
        )

    headers = [
        "record_id",
        "event_id",
        "event_type",
        "begin_time",
        "end_time",
        "state",
        "county_or_zone",
        "latitude",
        "longitude",
        "property_damage_reported",
        "damage_unit",
        "source_url",
        "retrieved_at",
        "source_hash",
        "quality_status",
        "limitation",
    ]
    flat_path = release_dir / "processed" / f"noaa_storms_{year}_flat.csv"
    write_csv_immutable(flat_path, headers, rows)
    upsert_manifest_entry(
        manifest,
        {
            "source_id": "SRC-NOAA-STORMS",
            "source_url": source_url,
            "retrieved_at": retrieved_at,
            "source_class": "official government",
            "source_vintage": str(year),
            "raw_path": str(raw_path.relative_to(PROJECT_ROOT)),
            "processed_path": str(flat_path.relative_to(PROJECT_ROOT)),
            "raw_sha256": source_hash,
            "raw_bytes": len(raw_bytes),
            "content_type": content_type,
            "record_count": len(rows),
            "allowed_use": "historical hazard context only",
            "limitation": "Official publication with incomplete/unverified source reports; not issuer loss.",
        },
    )
    return {"source_id": "SRC-NOAA-STORMS", "records": len(rows), "sha256": source_hash}


def parse_treasury_yield_curve(raw_bytes):
    """Parse the official Treasury Atom XML into dated percentage yields."""
    root = ET.fromstring(raw_bytes)
    atom = "{http://www.w3.org/2005/Atom}"
    metadata = "{http://schemas.microsoft.com/ado/2007/08/dataservices/metadata}"
    data = "{http://schemas.microsoft.com/ado/2007/08/dataservices}"
    field_map = {
        "BC_1MONTH": "yield_1m_pct",
        "BC_2MONTH": "yield_2m_pct",
        "BC_3MONTH": "yield_3m_pct",
        "BC_4MONTH": "yield_4m_pct",
        "BC_6MONTH": "yield_6m_pct",
        "BC_1YEAR": "yield_1y_pct",
        "BC_2YEAR": "yield_2y_pct",
        "BC_3YEAR": "yield_3y_pct",
        "BC_5YEAR": "yield_5y_pct",
        "BC_7YEAR": "yield_7y_pct",
        "BC_10YEAR": "yield_10y_pct",
        "BC_20YEAR": "yield_20y_pct",
        "BC_30YEAR": "yield_30y_pct",
    }
    rows = []
    for entry in root.findall(f"{atom}entry"):
        properties = entry.find(f"{atom}content/{metadata}properties")
        if properties is None:
            continue
        date_node = properties.find(f"{data}NEW_DATE")
        if date_node is None or not date_node.text:
            continue
        row = {"date": date_node.text[:10]}
        for source_name, output_name in field_map.items():
            node = properties.find(f"{data}{source_name}")
            row[output_name] = node.text if node is not None and node.text else ""
        rows.append(row)
    return sorted(rows, key=lambda row: row["date"])


def ingest_treasury(release_dir, manifest, year):
    source_url = TREASURY_YIELD_CURVE_URL.format(year=int(year))
    retrieved_at = utc_now()
    raw_bytes, content_type = download_bytes(source_url, accept="application/xml", timeout=60)
    source_hash = sha256_bytes(raw_bytes)
    raw_path = release_dir / "raw" / "treasury" / f"daily_yield_curve_{int(year)}.xml"
    write_immutable(raw_path, raw_bytes)
    rows = parse_treasury_yield_curve(raw_bytes)
    if not rows:
        raise RuntimeError("Treasury yield-curve response contains no dated observations")
    headers = [
        "date",
        "yield_1m_pct",
        "yield_2m_pct",
        "yield_3m_pct",
        "yield_4m_pct",
        "yield_6m_pct",
        "yield_1y_pct",
        "yield_2y_pct",
        "yield_3y_pct",
        "yield_5y_pct",
        "yield_7y_pct",
        "yield_10y_pct",
        "yield_20y_pct",
        "yield_30y_pct",
        "source_url",
        "retrieved_at",
        "source_hash",
        "source_class",
        "allowed_use",
    ]
    enriched = [
        {
            **row,
            "source_url": source_url,
            "retrieved_at": retrieved_at,
            "source_hash": source_hash,
            "source_class": "observed official government rate",
            "allowed_use": "dated risk-free-rate input and valuation sensitivity; not an ERP or complete WACC",
        }
        for row in rows
    ]
    flat_path = release_dir / "processed" / f"treasury_yield_curve_{int(year)}.csv"
    write_csv_immutable(flat_path, headers, enriched)
    upsert_manifest_entry(
        manifest,
        {
            "source_id": "SRC-US-TREASURY",
            "source_url": source_url,
            "retrieved_at": retrieved_at,
            "source_class": "official government",
            "source_vintage": str(int(year)),
            "raw_path": str(raw_path.relative_to(PROJECT_ROOT)),
            "processed_path": str(flat_path.relative_to(PROJECT_ROOT)),
            "raw_sha256": source_hash,
            "raw_bytes": len(raw_bytes),
            "content_type": content_type,
            "record_count": len(rows),
            "latest_observation_date": rows[-1]["date"],
            "allowed_use": "dated risk-free-rate input and valuation sensitivity",
            "limitation": "Treasury yields do not provide equity risk premium, issuer beta, debt cost, tax, or terminal growth.",
        },
    )
    return {
        "source_id": "SRC-US-TREASURY",
        "records": len(rows),
        "latest_observation_date": rows[-1]["date"],
        "sha256": source_hash,
    }


def select_ngfs_transition_runs(runs):
    """Select exactly one current default run per governed model/scenario pair."""
    selected = []
    for model in NGFS_TRANSITION_MODELS:
        for scenario in NGFS_SCENARIOS:
            candidates = [
                row for row in runs
                if row.get("model") == model
                and row.get("scenario") == scenario
                and row.get("is_default") is True
            ]
            if not candidates:
                raise RuntimeError(f"NGFS default run missing for {model} / {scenario}")
            selected.append(max(candidates, key=lambda row: (int(row.get("version") or 0), int(row["run_id"]))))
    return selected


def normalize_ngfs_scenario_label(value):
    """Repair the documented degree-symbol substitution in bulk API labels."""
    return "Below 2°C" if value in {"Below 2?C", "Below 2�C"} else value


def ingest_ngfs_transition(release_dir, manifest, region="USA", end_year=2050):
    """Ingest unaffected Phase 5.1 transition variables from the public guest API."""
    retrieved_at = utc_now()
    token_bytes, _ = download_bytes(NGFS_GUEST_TOKEN_URL, accept="application/json", timeout=30)
    token = json.loads(token_bytes.decode("utf-8"))
    if not isinstance(token, str) or not token:
        raise RuntimeError("NGFS guest authentication did not return an ephemeral access token")

    runs_bytes, runs_content_type = ngfs_api_bytes(f"{NGFS_API_BASE_URL}/runs", token)
    metadata_bytes, metadata_content_type = ngfs_api_bytes(f"{NGFS_API_BASE_URL}/ts", token)
    runs = json.loads(runs_bytes.decode("utf-8"))
    metadata = json.loads(metadata_bytes.decode("utf-8"))
    selected_runs = select_ngfs_transition_runs(runs)
    selected_run_ids = [int(row["run_id"]) for row in selected_runs]
    variable_metadata = [
        row for row in metadata
        if row.get("variable") in NGFS_TRANSITION_VARIABLES
        and set(row.get("runIds") or []).intersection(selected_run_ids)
    ]
    available_variables = {row["variable"] for row in variable_metadata}
    missing_variables = sorted(set(NGFS_TRANSITION_VARIABLES) - available_variables)
    if missing_variables:
        raise RuntimeError(f"NGFS transition variable metadata missing: {', '.join(missing_variables)}")
    units = sorted({row["unit"] for row in variable_metadata})
    query = {
        "filters": {
            "runs": selected_run_ids,
            "regions": [region],
            "variables": list(NGFS_TRANSITION_VARIABLES),
            "units": units,
            "years": list(range(2020, int(end_year) + 1, 5)),
            "timeslices": ["Year"],
        }
    }
    query_bytes, query_content_type = ngfs_api_bytes(
        f"{NGFS_API_BASE_URL}/runs/bulk/ts",
        token,
        payload=query,
        timeout=180,
    )
    rows = json.loads(query_bytes.decode("utf-8"))
    if not rows:
        raise RuntimeError("NGFS filtered transition query returned no observations")
    for row in rows:
        if row.get("variable") not in NGFS_TRANSITION_VARIABLES:
            raise RuntimeError(f"NGFS response contains unapproved variable: {row.get('variable')}")
        if int(row.get("year") or 0) > int(end_year):
            raise RuntimeError("NGFS response exceeded governed end year")

    raw_dir = release_dir / "raw" / "ngfs_phase_5_1"
    runs_path = raw_dir / "runs.json"
    metadata_path = raw_dir / "timeseries_metadata.json"
    query_request_path = raw_dir / "usa_transition_request.json"
    query_response_path = raw_dir / "usa_transition_response.json"
    write_immutable(runs_path, runs_bytes)
    write_immutable(metadata_path, metadata_bytes)
    write_immutable(query_request_path, json.dumps(query, indent=2, sort_keys=True).encode("utf-8"))
    write_immutable(query_response_path, query_bytes)

    processed = []
    for row in rows:
        source_scenario = row.get("scenario")
        processed.append(
            {
                "model": row.get("model"),
                "scenario": normalize_ngfs_scenario_label(source_scenario),
                "source_scenario_label": source_scenario,
                "run_id": row.get("runId"),
                "run_version": row.get("version"),
                "region": row.get("region"),
                "variable": row.get("variable"),
                "unit": row.get("unit"),
                "year": row.get("year"),
                "value": row.get("value"),
                "source_release": NGFS_RELEASE_VERSION,
                "source_release_date": NGFS_RELEASE_DATE,
                "source_url": NGFS_EXPLORER_URL,
                "retrieved_at": retrieved_at,
                "source_class": "official NGFS/IIASA scenario output",
                "allowed_use": "conditional transition pathway; no occurrence probability",
                "physical_damage_status": "not used; Phase 5 affected physical-damage variables excluded",
            }
        )
    headers = [
        "model", "scenario", "source_scenario_label", "run_id", "run_version", "region", "variable",
        "unit", "year", "value", "source_release", "source_release_date",
        "source_url", "retrieved_at", "source_class", "allowed_use",
        "physical_damage_status",
    ]
    processed_path = release_dir / "processed" / f"ngfs_5_1_transition_{region.lower()}_to_{int(end_year)}.csv"
    write_csv_immutable(processed_path, headers, processed)
    processed_hash = sha256_bytes(processed_path.read_bytes())
    hashes = {
        "runs": sha256_bytes(runs_bytes),
        "timeseries_metadata": sha256_bytes(metadata_bytes),
        "query_request": sha256_bytes(query_request_path.read_bytes()),
        "query_response": sha256_bytes(query_bytes),
    }
    upsert_manifest_entry(
        manifest,
        {
            "source_id": "SRC-NGFS-PHASE-5-1-TRANSITION",
            "source_url": NGFS_EXPLORER_URL,
            "api_url": NGFS_API_BASE_URL,
            "retrieved_at": retrieved_at,
            "source_class": "official NGFS scenario data hosted by IIASA",
            "source_vintage": NGFS_RELEASE_VERSION,
            "source_release_date": NGFS_RELEASE_DATE,
            "raw_paths": {
                "runs": str(runs_path.relative_to(PROJECT_ROOT)),
                "timeseries_metadata": str(metadata_path.relative_to(PROJECT_ROOT)),
                "query_request": str(query_request_path.relative_to(PROJECT_ROOT)),
                "query_response": str(query_response_path.relative_to(PROJECT_ROOT)),
            },
            "raw_sha256": hashes,
            "content_types": {
                "runs": runs_content_type,
                "timeseries_metadata": metadata_content_type,
                "query_response": query_content_type,
            },
            "processed_path": str(processed_path.relative_to(PROJECT_ROOT)),
            "processed_sha256": processed_hash,
            "record_count": len(processed),
            "models": list(NGFS_TRANSITION_MODELS),
            "scenarios": list(NGFS_SCENARIOS),
            "region": region,
            "variables": list(NGFS_TRANSITION_VARIABLES),
            "credential_values_stored": False,
            "allowed_use": "conditional transition pathways only; no scenario probability",
            "limitation": "Phase 5 physical damage variables affected by the retracted Kotz et al. paper are excluded.",
        },
    )
    return {
        "source_id": "SRC-NGFS-PHASE-5-1-TRANSITION",
        "records": len(processed),
        "models": len(NGFS_TRANSITION_MODELS),
        "scenarios": len(NGFS_SCENARIOS),
        "region": region,
        "sha256": hashes["query_response"],
    }


def sec_quarters(start_year, end_year, end_quarter=4):
    """Return inclusive SEC quarterly data-set periods in chronological order."""
    start_year = int(start_year)
    end_year = int(end_year)
    end_quarter = int(end_quarter)
    if start_year < 2009 or end_year < start_year or end_quarter not in {1, 2, 3, 4}:
        raise ValueError("SEC range must start in 2009 or later and have a valid inclusive end quarter")
    return [
        (year, quarter)
        for year in range(start_year, end_year + 1)
        for quarter in range(1, 5)
        if year < end_year or quarter <= end_quarter
    ]


def load_sec_candidate_ciks(tickers):
    """Resolve requested tickers to CIKs from the governed local issuer master."""
    master_path = PROJECT_ROOT / "data" / "issuer_sector_master.csv"
    requested = {ticker.strip().upper() for ticker in tickers if ticker.strip()}
    if not requested:
        raise ValueError("At least one SEC pilot ticker is required")
    resolved = {}
    with master_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            ticker = (row.get("ticker") or "").strip().upper()
            cik = (row.get("cik") or "").strip()
            if ticker in requested and cik:
                resolved[str(int(cik))] = ticker
    missing = sorted(requested - set(resolved.values()))
    if missing:
        raise ValueError(f"Ticker(s) absent from governed issuer master: {', '.join(missing)}")
    for ticker in requested:
        for cik in SEC_HISTORICAL_CIK_ALIASES.get(ticker, {}):
            resolved[str(int(cik))] = ticker
    return resolved


def read_zip_tsv(archive, filename):
    """Yield dictionaries from a named SEC tab-separated file."""
    member = next(
        (name for name in archive.namelist() if Path(name).name.lower() == filename.lower()),
        None,
    )
    if member is None:
        raise RuntimeError(f"SEC archive is missing required file: {filename}")
    with archive.open(member) as handle:
        text = io.TextIOWrapper(handle, encoding="utf-8-sig", errors="replace", newline="")
        yield from csv.DictReader(text, delimiter="\t")


def parse_sec_financial_statement_zip(raw_bytes, cik_to_ticker, source_period):
    """Extract point-in-time annual filing facts for governed pilot issuers."""
    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as archive:
        submissions = {}
        for row in read_zip_tsv(archive, "sub.txt"):
            cik_raw = (row.get("cik") or "").strip()
            form = (row.get("form") or "").strip().upper()
            if not cik_raw or form not in {"10-K", "10-K/A"}:
                continue
            cik = str(int(cik_raw))
            if cik not in cik_to_ticker:
                continue
            submissions[row["adsh"]] = {
                "ticker": cik_to_ticker[cik],
                "cik": cik.zfill(10),
                "issuer_name": row.get("name"),
                "form": form,
                "report_period": row.get("period"),
                "fiscal_year": row.get("fy"),
                "fiscal_period": row.get("fp"),
                "filed": row.get("filed"),
                "accepted": row.get("accepted"),
                "sic": row.get("sic"),
                "instance": row.get("instance"),
            }

        facts = []
        if not submissions:
            return facts, []
        for row in read_zip_tsv(archive, "num.txt"):
            adsh = row.get("adsh")
            tag = row.get("tag")
            if adsh not in submissions or tag not in SEC_FINANCIAL_TAGS:
                continue
            version = (row.get("version") or "").lower()
            if not version.startswith("us-gaap"):
                continue
            segments = (row.get("segments") or "").strip()
            if segments not in {"", "[]", "{}", "\\N"}:
                continue
            facts.append(
                {
                    **submissions[adsh],
                    "source_period": source_period,
                    "adsh": adsh,
                    "tag": tag,
                    "taxonomy_version": row.get("version"),
                    "date": row.get("ddate"),
                    "quarters": row.get("qtrs"),
                    "unit": row.get("uom"),
                    "value": row.get("value"),
                    "footnote": row.get("footnote"),
                    "segments": segments,
                    "source_class": "official issuer-filed XBRL fact",
                    "allowed_use": "point-in-time financial baseline candidate; filing tie-out required",
                }
            )
        return facts, list(submissions.values())


def sec_financial_coverage_rows(facts):
    """Summarize concept coverage without treating availability as validity."""
    by_filing = {}
    tag_to_concept = {
        tag: concept for concept, tags in SEC_FINANCIAL_CONCEPTS.items() for tag in tags
    }
    for row in facts:
        key = (row["ticker"], row["adsh"])
        filing = by_filing.setdefault(
            key,
            {
                "ticker": row["ticker"],
                "cik": row["cik"],
                "issuer_name": row["issuer_name"],
                "adsh": row["adsh"],
                "form": row["form"],
                "report_period": row["report_period"],
                "filed": row["filed"],
                "concepts": set(),
            },
        )
        concept = tag_to_concept.get(row["tag"])
        if concept:
            filing["concepts"].add(concept)
    output = []
    for filing in by_filing.values():
        concepts = filing.pop("concepts")
        row = {**filing}
        for concept in SEC_FINANCIAL_CONCEPTS:
            row[f"has_{concept}"] = concept in concepts
        row["concept_count"] = len(concepts)
        row["concept_total"] = len(SEC_FINANCIAL_CONCEPTS)
        row["coverage_pct"] = round(100 * len(concepts) / len(SEC_FINANCIAL_CONCEPTS), 2)
        row["quality_status"] = "coverage screening only; facts require filing and accounting tie-out"
        output.append(row)
    return sorted(output, key=lambda row: (row["ticker"], row.get("filed") or "", row["adsh"]))


def ingest_sec_financial_history(
    release_dir,
    manifest,
    start_year,
    end_year,
    end_quarter,
    tickers,
    raw_release_id=None,
):
    """Download every SEC quarterly archive and extract governed pilot facts."""
    cik_to_ticker = load_sec_candidate_ciks(tickers)
    all_facts = []
    periods = sec_quarters(start_year, end_year, end_quarter)
    raw_release_dir = RELEASES_ROOT / raw_release_id if raw_release_id else release_dir
    raw_source_manifest = None
    raw_source_entries = {}
    if raw_release_id:
        raw_source_manifest_path = raw_release_dir / "manifest.json"
        if not raw_source_manifest_path.exists():
            raise RuntimeError(f"SEC raw source release is missing: {raw_release_id}")
        raw_source_manifest = json.loads(raw_source_manifest_path.read_text(encoding="utf-8"))
        raw_source_entries = {
            row.get("source_id"): row
            for row in raw_source_manifest.get("source_entries", [])
        }
    for index, (year, quarter) in enumerate(periods, start=1):
        source_period = f"{year}Q{quarter}"
        source_url = SEC_FINANCIAL_STATEMENT_URL.format(year=year, quarter=quarter)
        source_id = f"SRC-SEC-FSDS-{year}Q{quarter}"
        raw_path = raw_release_dir / "raw" / "sec_financial_statements" / f"{year}q{quarter}.zip"
        original_entry = raw_source_entries.get(source_id, {})
        retrieved_at = original_entry.get("retrieved_at") or utc_now()
        if raw_path.exists():
            print(f"SEC {source_period}: using immutable local raw {index}/{len(periods)}", flush=True)
            raw_bytes = raw_path.read_bytes()
            content_type = "application/zip"
        elif raw_release_id:
            raise RuntimeError(f"SEC raw source release is incomplete at {source_period}: {raw_path}")
        else:
            print(f"SEC {source_period}: downloading {index}/{len(periods)}", flush=True)
            try:
                raw_bytes, content_type = download_bytes(
                    source_url,
                    accept="application/octet-stream,application/zip",
                    timeout=180,
                )
            except HTTPError as exc:
                raise RuntimeError(f"SEC {source_period} download failed with HTTP {exc.code}: {source_url}") from exc
            write_immutable(raw_path, raw_bytes)
        source_hash = sha256_bytes(raw_bytes)
        facts, submissions = parse_sec_financial_statement_zip(
            raw_bytes,
            cik_to_ticker,
            source_period,
        )
        for row in facts:
            row.update(
                {
                    "source_url": source_url,
                    "retrieved_at": retrieved_at,
                    "source_hash": source_hash,
                }
            )
        all_facts.extend(facts)
        upsert_manifest_entry(
            manifest,
            {
                "source_id": source_id,
                "source_url": source_url,
                "retrieved_at": retrieved_at,
                "source_class": "official government issuer-filed XBRL compilation",
                "source_vintage": source_period,
                "raw_path": str(raw_path.relative_to(PROJECT_ROOT)),
                "raw_source_release_id": raw_release_id,
                "raw_sha256": source_hash,
                "raw_bytes": len(raw_bytes),
                "content_type": content_type,
                "candidate_submission_count": len(submissions),
                "candidate_fact_count": len(facts),
                "allowed_use": "point-in-time financial baseline candidate; filing tie-out required",
                "limitation": "As-filed structured data may contain filer or extraction errors and is not a substitute for the filing.",
            },
        )
        save_manifest(release_dir, manifest)
        print(
            f"SEC {source_period}: {len(raw_bytes) / (1024 * 1024):.2f} MiB, "
            f"{len(submissions)} candidate filings, {len(facts)} candidate facts",
            flush=True,
        )

    fact_headers = [
        "ticker", "cik", "issuer_name", "source_period", "adsh", "form",
        "report_period", "fiscal_year", "fiscal_period", "filed", "accepted",
        "sic", "instance", "tag", "taxonomy_version", "date", "quarters",
        "unit", "value", "footnote", "segments", "source_url", "retrieved_at",
        "source_hash", "source_class", "allowed_use",
    ]
    fact_path = release_dir / "processed" / f"sec_financial_facts_{start_year}q1_{end_year}q{end_quarter}.csv"
    write_csv_immutable(fact_path, fact_headers, all_facts)
    coverage = sec_financial_coverage_rows(all_facts)
    coverage_headers = [
        "ticker", "cik", "issuer_name", "adsh", "form", "report_period", "filed",
        *[f"has_{concept}" for concept in SEC_FINANCIAL_CONCEPTS],
        "concept_count", "concept_total", "coverage_pct", "quality_status",
    ]
    coverage_path = release_dir / "processed" / f"sec_financial_coverage_{start_year}_{end_year}q{end_quarter}.csv"
    write_csv_immutable(coverage_path, coverage_headers, coverage)
    manifest["sec_financial_history"] = {
        "start_period": f"{start_year}Q1",
        "end_period": f"{end_year}Q{end_quarter}",
        "quarter_count": len(periods),
        "tickers": sorted(set(cik_to_ticker.values())),
        "cik_to_ticker": dict(sorted(cik_to_ticker.items(), key=lambda item: int(item[0]))),
        "historical_cik_aliases": {
            ticker: SEC_HISTORICAL_CIK_ALIASES[ticker]
            for ticker in sorted(set(cik_to_ticker.values()))
            if ticker in SEC_HISTORICAL_CIK_ALIASES
        },
        "raw_source_release_id": raw_release_id,
        "processed_fact_path": str(fact_path.relative_to(PROJECT_ROOT)),
        "processed_fact_sha256": sha256_bytes(fact_path.read_bytes()),
        "coverage_path": str(coverage_path.relative_to(PROJECT_ROOT)),
        "coverage_sha256": sha256_bytes(coverage_path.read_bytes()),
        "fact_count": len(all_facts),
        "filing_count": len(coverage),
        "raw_archives_committed_to_git": False,
    }
    save_manifest(release_dir, manifest)
    return {
        "source_id": "SRC-SEC-FSDS-HISTORY",
        "quarters": len(periods),
        "facts": len(all_facts),
        "filings": len(coverage),
        "tickers": sorted(set(cik_to_ticker.values())),
    }


def credential_status():
    rows = [
        {
            "service": "SEC EDGAR public data",
            "environment_variable": "SEC_USER_AGENT",
            "configured": bool(os.environ.get("SEC_USER_AGENT", "").strip()),
            "key_required": False,
            "free_path": "No key; use an identifiable User-Agent and stay below fair-access limits.",
        },
        {
            "service": "EIA API",
            "environment_variable": "EIA_API_KEY",
            "configured": bool(os.environ.get("EIA_API_KEY", "").strip()),
            "key_required": True,
            "free_path": "Free key: https://www.eia.gov/opendata/register.php; bulk downloads need no key.",
        },
        {
            "service": "FRED / ALFRED API",
            "environment_variable": "FRED_API_KEY",
            "configured": bool(os.environ.get("FRED_API_KEY", "").strip()),
            "key_required": True,
            "free_path": "Free account/key: https://fred.stlouisfed.org/docs/api/fred/v2/api_key.html",
        },
        {
            "service": "BEA API",
            "environment_variable": "BEA_API_KEY",
            "configured": bool(os.environ.get("BEA_API_KEY", "").strip()),
            "key_required": True,
            "free_path": "Free key with durable email: https://apps.bea.gov/api/signup/",
        },
        {
            "service": "NWS / OpenFEMA / NOAA Storm Events",
            "environment_variable": "",
            "configured": True,
            "key_required": False,
            "free_path": "No registration; respect published rate limits and terms.",
        },
    ]
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=("status", "nws", "noaa-storms", "treasury", "ngfs-transition", "sec-financials", "all-no-key"),
        help="Data source to ingest or credential status to display",
    )
    parser.add_argument("--release-id", help="Immutable release identifier")
    parser.add_argument("--storm-year", type=int, default=COMPLETED_STORM_YEAR)
    parser.add_argument("--treasury-year", type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument("--ngfs-region", default="USA")
    parser.add_argument("--ngfs-end-year", type=int, default=2050)
    parser.add_argument("--sec-start-year", type=int, default=2009)
    parser.add_argument("--sec-end-year", type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument(
        "--sec-end-quarter",
        type=int,
        default=1,
        help="Latest published SEC Financial Statement Data Set quarter (inclusive)",
    )
    parser.add_argument(
        "--sec-tickers",
        default="AAPL,CAT,CVX,DE,DUK,MSFT,NEE,XOM",
        help="Comma-separated non-financial candidate tickers extracted from every raw quarter",
    )
    parser.add_argument(
        "--sec-raw-release-id",
        help="Existing immutable release containing all SEC raw ZIPs; reprocess without redownloading",
    )
    args = parser.parse_args()

    if args.command == "status":
        print(json.dumps(credential_status(), indent=2))
        return 0
    if not args.release_id:
        parser.error("--release-id is required for ingestion")

    release_dir = RELEASES_ROOT / args.release_id
    manifest = load_manifest(release_dir, args.release_id)
    results = []
    try:
        if args.command in ("nws", "all-no-key"):
            results.append(ingest_nws(release_dir, manifest))
        if args.command in ("noaa-storms", "all-no-key"):
            results.append(ingest_noaa_storms(release_dir, manifest, args.storm_year))
        if args.command in ("treasury", "all-no-key"):
            results.append(ingest_treasury(release_dir, manifest, args.treasury_year))
        if args.command in ("ngfs-transition", "all-no-key"):
            results.append(
                ingest_ngfs_transition(
                    release_dir,
                    manifest,
                    region=args.ngfs_region,
                    end_year=args.ngfs_end_year,
                )
            )
        if args.command == "sec-financials":
            results.append(
                ingest_sec_financial_history(
                    release_dir,
                    manifest,
                    args.sec_start_year,
                    args.sec_end_year,
                    args.sec_end_quarter,
                    args.sec_tickers.split(","),
                    raw_release_id=args.sec_raw_release_id,
                )
            )
        save_manifest(release_dir, manifest)
    except Exception as exc:
        print(f"ingestion failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps({"release_id": args.release_id, "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
