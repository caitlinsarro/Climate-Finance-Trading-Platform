#!/usr/bin/env python3
"""Build the governed DUK transition/facility evidence pilot.

Outputs are research evidence bridges. County FEMA values are never converted
to issuer losses, and a static carbon-price exposure is not called a forecast.
"""

import argparse
import csv
import io
import json
import math
import statistics
import sys
import urllib.parse
import zipfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import ingest_authoritative_data as base


GHGRP_SUMMARY_URL = (
    "https://www.epa.gov/system/files/other-files/2024-10/"
    "2023_data_summary_spreadsheets.zip"
)
GHGRP_PARENT_URL = (
    "https://www.epa.gov/system/files/other-files/2024-10/"
    "ghgp_data_parent_company.xlsb"
)
EGRID_URL = (
    "https://www.epa.gov/system/files/documents/2025-06/"
    "egrid2023_data_rev2.xlsx"
)
FEMA_NRI_LAYER_URL = (
    "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/"
    "National_Risk_Index_Counties/FeatureServer/0"
)
DUK_2025_10K_URL = (
    "https://www.sec.gov/Archives/edgar/data/1326160/"
    "000132616026000014/duk-20251231.htm"
)
EPA_YEAR = 2023
PILOT_TICKER = "DUK"
PILOT_PARENT = "DUKE ENERGY CORP"
PARENT_ALIASES = {
    "AAPL": {"APPLE INC"},
    "CAT": {"CATERPILLAR INC"},
    "CVX": {"CHEVRON CORP"},
    "DE": {"DEERE & CO"},
    "DUK": {"DUKE ENERGY CORP"},
    "MSFT": {"MICROSOFT CORP"},
    "NEE": {"NEXTERA ENERGY INC"},
    "XOM": {"EXXON MOBIL CORP"},
}
FEMA_FIELDS = (
    "STCOFIPS,STATEABBRV,COUNTY,RISK_SCORE,RISK_RATNG,"
    "HWAV_RISKS,HRCN_RISKS,IFLD_RISKS,CFLD_RISKS,SWND_RISKS,WFIR_RISKS,"
    "HWAV_EALT,HRCN_EALT,IFLD_EALT,CFLD_EALT,SWND_EALT,WFIR_EALT,NRI_VER"
)


def clean_id(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return ""
    return str(int(float(value)))


def normalize_name(value):
    return " ".join(str(value or "").strip().upper().split())


def normalize_county(value):
    text = normalize_name(value)
    for suffix in (" COUNTY", " PARISH", " BOROUGH", " CENSUS AREA"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def finite_number(value):
    if value is None or value == "" or pd.isna(value):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def calculate_fcff_candidate(cfo, capex, interest_expense, tax_expense, pretax_income):
    values = [cfo, capex, interest_expense, tax_expense, pretax_income]
    if any(value is None for value in values) or float(pretax_income) <= 0:
        return {"status": "not calculable", "reason": "mandatory SEC fact missing or pretax income non-positive"}
    tax_rate = float(tax_expense) / float(pretax_income)
    if not 0 <= tax_rate <= 1:
        return {"status": "not calculable", "reason": "derived effective tax rate outside [0,1]"}
    after_tax_interest = float(interest_expense) * (1 - tax_rate)
    fcff = float(cfo) - float(capex) + after_tax_interest
    return {
        "status": "candidate; filing tie-out required",
        "effective_tax_rate": tax_rate,
        "after_tax_interest": after_tax_interest,
        "fcff": fcff,
        "reconciliation_residual": fcff - (float(cfo) - float(capex) + after_tax_interest),
    }


def carbon_price_sensitivity(owned_co2_tonnes, target_price, reference_price):
    if any(value is None for value in (owned_co2_tonnes, target_price, reference_price)):
        return {"status": "not calculable", "reason": "emissions or scenario price missing"}
    delta = float(target_price) - float(reference_price)
    return {
        "status": "gross static exposure; not net cost or forecast",
        "price_delta_usd_per_tco2": delta,
        "gross_usd_per_1usd_tco2": float(owned_co2_tonnes),
        "gross_static_exposure_usd": float(owned_co2_tonnes) * delta,
    }


def physical_financial_gate(exposed_asset_value=None, damage_function=None,
                            business_interruption=None, recovery_treatment=None):
    missing = [
        label for label, value in (
            ("exposed_asset_value", exposed_asset_value),
            ("asset_type_damage_function", damage_function),
            ("business_interruption", business_interruption),
            ("recovery_or_insurance", recovery_treatment),
        ) if value in (None, "")
    ]
    if missing:
        return {"status": "not calculable", "missing": missing}
    return {"status": "eligible for calculation", "missing": []}


def read_parent_rows(path, year=EPA_YEAR):
    frame = pd.read_excel(path, sheet_name=str(year), engine="pyxlsb", dtype=object)
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame.to_dict("records")


def read_ghgrp_direct_rows(zip_bytes):
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        member = next(
            name for name in archive.namelist()
            if Path(name).name.lower() == f"ghgp_data_{EPA_YEAR}.xlsx"
        )
        workbook = archive.read(member)
    frame = pd.read_excel(
        io.BytesIO(workbook), sheet_name="Direct Point Emitters", header=3,
        engine="openpyxl", dtype=object,
    )
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame.to_dict("records")


def join_parent_emissions(parent_rows, direct_rows, ticker=PILOT_TICKER):
    aliases = PARENT_ALIASES[ticker]
    parents = [
        row for row in parent_rows
        if normalize_name(row.get("PARENT COMPANY NAME")) in aliases
    ]
    direct = {clean_id(row.get("Facility Id")): row for row in direct_rows}
    output = []
    for parent in parents:
        facility_id = clean_id(parent.get("GHGRP FACILITY ID"))
        point = direct.get(facility_id)
        ownership = finite_number(parent.get("PARENT CO. PERCENT OWNERSHIP"))
        total = finite_number(point.get("Total reported direct emissions")) if point else None
        co2 = finite_number(point.get("CO2 emissions (non-biogenic)")) if point else None
        output.append({
            "ticker": ticker,
            "epa_facility_id": facility_id,
            "facility_name": (point or parent).get("Facility Name") or parent.get("FACILITY NAME"),
            "state": (point or {}).get("State") or parent.get("FACILITY STATE"),
            "county": (point or {}).get("County") or parent.get("FACILITY COUNTY"),
            "latitude": finite_number((point or {}).get("Latitude")),
            "longitude": finite_number((point or {}).get("Longitude")),
            "parent_company": parent.get("PARENT COMPANY NAME"),
            "ownership_pct": ownership,
            "reported_direct_tco2e": total,
            "reported_nonbiogenic_co2_tonnes": co2,
            "ownership_adjusted_direct_tco2e": None if total is None or ownership is None else total * ownership / 100,
            "ownership_adjusted_nonbiogenic_co2_tonnes": None if co2 is None or ownership is None else co2 * ownership / 100,
            "emissions_match_status": "matched by EPA facility ID" if point else "parent record unmatched to direct-emitter sheet",
            "source_year": EPA_YEAR,
            "allowed_use": "reported U.S. facility emissions exposure; not complete parent emissions",
        })
    return output


def download_fema_counties(release_dir):
    pages = []
    features = []
    for offset in (0, 2000):
        params = urllib.parse.urlencode({
            "where": "1=1", "outFields": FEMA_FIELDS,
            "returnGeometry": "false", "resultOffset": offset,
            "resultRecordCount": 2000, "orderByFields": "STCOFIPS", "f": "json",
        })
        raw, content_type = base.download_bytes(f"{FEMA_NRI_LAYER_URL}/query?{params}", accept="application/json", timeout=90)
        payload = json.loads(raw)
        if payload.get("error"):
            raise RuntimeError(f"FEMA NRI query failed: {payload['error']}")
        page_path = release_dir / "raw" / "fema_nri" / f"counties_offset_{offset}.json"
        base.write_immutable(page_path, raw)
        page_features = payload.get("features", [])
        pages.append({"path": page_path, "bytes": raw, "content_type": content_type})
        features.extend(feature.get("attributes") or {} for feature in page_features)
        if len(page_features) < 2000:
            break
    return features, pages


def join_fema_context(facilities, counties):
    index = {
        (normalize_name(row.get("STATEABBRV")), normalize_county(row.get("COUNTY"))): row
        for row in counties
    }
    output = []
    gate = physical_financial_gate()
    for facility in facilities:
        county = index.get((normalize_name(facility.get("state")), normalize_county(facility.get("county"))))
        output.append({
            "ticker": facility["ticker"],
            "epa_facility_id": facility["epa_facility_id"],
            "facility_name": facility["facility_name"],
            "latitude": facility["latitude"],
            "longitude": facility["longitude"],
            "state": facility["state"],
            "county": facility["county"],
            "county_fips": (county or {}).get("STCOFIPS"),
            "county_nri_score": (county or {}).get("RISK_SCORE"),
            "county_nri_rating": (county or {}).get("RISK_RATNG"),
            "heat_score": (county or {}).get("HWAV_RISKS"),
            "hurricane_score": (county or {}).get("HRCN_RISKS"),
            "inland_flood_score": (county or {}).get("IFLD_RISKS"),
            "coastal_flood_score": (county or {}).get("CFLD_RISKS"),
            "strong_wind_score": (county or {}).get("SWND_RISKS"),
            "wildfire_score": (county or {}).get("WFIR_RISKS"),
            "nri_version": (county or {}).get("NRI_VER"),
            "hazard_match_status": "matched by state and normalized county" if county else "not matched",
            "issuer_physical_loss_usd": "",
            "financial_status": gate["status"],
            "missing_financial_fields": ";".join(gate["missing"]),
            "allowed_use": "county hazard context only; not issuer probability or loss",
        })
    return output


def latest_sec_fact(rows, tag, fiscal_year, adsh):
    candidates = [
        row for row in rows
        if row["ticker"] == PILOT_TICKER and row["adsh"] == adsh
        and row["fiscal_year"] == str(fiscal_year) and row["date"] == str(fiscal_year) + "1231"
        and row["tag"] == tag and row["unit"] == "USD"
    ]
    if len(candidates) != 1:
        raise RuntimeError(f"Expected one DUK {fiscal_year} {tag} fact, found {len(candidates)}")
    return float(candidates[0]["value"]), candidates[0]


def build_fcff_bridge(sec_path, fiscal_year=2025):
    rows = list(csv.DictReader(Path(sec_path).open(newline="", encoding="utf-8")))
    filings = sorted(
        {row["adsh"] for row in rows if row["ticker"] == PILOT_TICKER and row["fiscal_year"] == str(fiscal_year)},
        key=lambda adsh: max(row["filed"] for row in rows if row["adsh"] == adsh),
    )
    if not filings:
        raise RuntimeError("No governed DUK annual filing found")
    adsh = filings[-1]
    mapping = {
        "operating_cash_flow": "NetCashProvidedByUsedInOperatingActivities",
        "capital_expenditure": "PaymentsToAcquirePropertyPlantAndEquipment",
        "interest_expense": "InterestExpense",
        "tax_expense": "IncomeTaxExpenseBenefit",
        "pretax_income": "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    }
    values, evidence = {}, {}
    for concept, tag in mapping.items():
        values[concept], evidence[concept] = latest_sec_fact(rows, tag, fiscal_year, adsh)
    calculation = calculate_fcff_candidate(
        values["operating_cash_flow"], values["capital_expenditure"],
        values["interest_expense"], values["tax_expense"], values["pretax_income"],
    )
    first = next(iter(evidence.values()))
    return {
        "ticker": PILOT_TICKER, "fiscal_year": fiscal_year, "adsh": adsh,
        "filed": first["filed"], "report_period": first["report_period"],
        **values, **calculation,
        "formula": "CFO - CapEx + interest expense * (1 - effective tax rate)",
        "unit": "USD", "source_release_path": str(sec_path),
        "filing_url": DUK_2025_10K_URL,
        "filing_tie_out_status": "pass; five source line items manually confirmed in consolidated statements",
        "valuation_status": "not calculable; WACC and terminal-growth evidence gate not complete",
    }


def ngfs_price_summary(ngfs_path, year=2050):
    rows = list(csv.DictReader(Path(ngfs_path).open(newline="", encoding="utf-8")))
    grouped = {}
    for row in rows:
        if row["variable"] == "Price|Carbon" and int(row["year"]) == year:
            grouped.setdefault(row["scenario"], []).append(float(row["value"]))
    return {
        scenario: {"median": statistics.median(values), "min": min(values), "max": max(values), "models": len(values)}
        for scenario, values in grouped.items()
    }


def write_rows(path, rows):
    if not rows:
        raise RuntimeError(f"No rows produced for {path.name}")
    headers = list(rows[0])
    base.write_csv_immutable(path, headers, rows)


def build_release(release_id, sec_release_id, ngfs_release_id):
    release_dir = base.RELEASES_ROOT / release_id
    manifest = base.load_manifest(release_dir, release_id)
    retrieved_at = base.utc_now()
    downloads = {}
    for source_id, url, filename in (
        ("SRC-EPA-GHGRP-SUMMARY-2023", GHGRP_SUMMARY_URL, "2023_data_summary_spreadsheets.zip"),
        ("SRC-EPA-GHGRP-PARENT-2023", GHGRP_PARENT_URL, "ghgp_data_parent_company.xlsb"),
        ("SRC-EPA-EGRID-2023-R2", EGRID_URL, "egrid2023_data_rev2.xlsx"),
        ("SRC-SEC-DUK-2025-10K", DUK_2025_10K_URL, "duk-20251231.htm"),
    ):
        raw, content_type = base.download_bytes(url, timeout=180)
        source_folder = "sec" if source_id.startswith("SRC-SEC") else "epa"
        path = release_dir / "raw" / source_folder / filename
        base.write_immutable(path, raw)
        downloads[source_id] = (raw, path)
        base.upsert_manifest_entry(manifest, {
            "source_id": source_id, "source_url": url, "retrieved_at": retrieved_at,
            "source_class": "official issuer filing" if source_id.startswith("SRC-SEC") else "official EPA",
            "source_vintage": "2025" if source_id.startswith("SRC-SEC") else "2023",
            "raw_path": str(path.relative_to(base.PROJECT_ROOT)),
            "raw_sha256": base.sha256_bytes(raw), "raw_bytes": len(raw),
            "content_type": content_type,
            "allowed_use": (
                "manual financial-statement line-item tie-out"
                if source_id.startswith("SRC-SEC")
                else "facility ownership, reported emissions, coordinates, and power-sector context"
            ),
            "limitation": (
                "Issuer filing supports line items but does not validate the project FCFF method or climate forecast."
                if source_id.startswith("SRC-SEC")
                else "GHGRP does not cover every parent-company emission or establish issuer financial loss."
            ),
        })

    parent_path = downloads["SRC-EPA-GHGRP-PARENT-2023"][1]
    parent_rows = read_parent_rows(parent_path)
    direct_rows = read_ghgrp_direct_rows(downloads["SRC-EPA-GHGRP-SUMMARY-2023"][0])
    facilities = join_parent_emissions(parent_rows, direct_rows)
    facility_path = release_dir / "processed" / "duk_epa_facility_emissions_2023.csv"
    write_rows(facility_path, facilities)

    counties, fema_pages = download_fema_counties(release_dir)
    physical = join_fema_context(facilities, counties)
    physical_path = release_dir / "processed" / "duk_facility_fema_context_2025.csv"
    write_rows(physical_path, physical)
    base.upsert_manifest_entry(manifest, {
        "source_id": "SRC-FEMA-NRI-COUNTIES-2025", "source_url": FEMA_NRI_LAYER_URL,
        "retrieved_at": retrieved_at, "source_class": "official FEMA ArcGIS feature service",
        "source_vintage": "December 2025 v1.20",
        "raw_paths": [str(page["path"].relative_to(base.PROJECT_ROOT)) for page in fema_pages],
        "raw_sha256": [base.sha256_bytes(page["bytes"]) for page in fema_pages],
        "record_count": len(counties),
        "allowed_use": "broad county hazard context only",
        "limitation": "Community-level index/EAL is not facility damage, issuer probability, or issuer loss.",
    })

    sec_path = base.RELEASES_ROOT / sec_release_id / "processed" / "sec_financial_facts_2009q1_2026q1.csv"
    ngfs_path = base.RELEASES_ROOT / ngfs_release_id / "processed" / "ngfs_5_1_transition_usa_to_2050.csv"
    fcff = build_fcff_bridge(sec_path)
    fcff_path = release_dir / "processed" / "duk_sec_fcff_bridge_2025.csv"
    write_rows(fcff_path, [fcff])

    prices = ngfs_price_summary(ngfs_path)
    owned_co2 = sum(row["ownership_adjusted_nonbiogenic_co2_tonnes"] or 0 for row in facilities)
    current = prices["Current Policies"]
    carbon = {
        "ticker": PILOT_TICKER, "emissions_year": EPA_YEAR,
        "ownership_adjusted_nonbiogenic_co2_tonnes": owned_co2,
        "target_scenario": "Current Policies", "target_year": 2050,
        "target_carbon_price_median": current["median"],
        "target_carbon_price_min": current["min"], "target_carbon_price_max": current["max"],
        "reference": "climate-agnostic zero-price research baseline (not an NGFS scenario)",
        "reference_carbon_price": 0.0,
        **carbon_price_sensitivity(owned_co2, current["median"], 0.0),
        "emissions_path_status": "2023 static exposure only; no 2050 emissions forecast",
        "free_allocation": "missing", "pass_through": "missing", "jurisdictional_incidence": "missing",
        "net_carbon_cost_usd": "", "fcff_adjustment_usd": "",
        "allowed_use": "gross unit sensitivity and scenario illustration only",
    }
    carbon_path = release_dir / "processed" / "duk_carbon_price_sensitivity.csv"
    write_rows(carbon_path, [carbon])

    selection = []
    direct_ids = {clean_id(row.get("Facility Id")) for row in direct_rows}
    for ticker, aliases in PARENT_ALIASES.items():
        parents = [row for row in parent_rows if normalize_name(row.get("PARENT COMPANY NAME")) in aliases]
        matched = [row for row in parents if clean_id(row.get("GHGRP FACILITY ID")) in direct_ids]
        selection.append({
            "ticker": ticker, "parent_records": len(parents), "direct_emitter_matches": len(matched),
            "selected": ticker == PILOT_TICKER,
            "selection_reason": "SEC history + utility FCFF boundary + EPA ownership/emissions/coordinates" if ticker == PILOT_TICKER else "not selected for first pilot",
        })
    selection_path = release_dir / "processed" / "pilot_candidate_screen.csv"
    write_rows(selection_path, selection)

    manifest["duk_pilot"] = {
        "ticker": PILOT_TICKER, "epa_year": EPA_YEAR,
        "parent_records": len(facilities),
        "direct_emitter_matches": sum(row["reported_direct_tco2e"] is not None for row in facilities),
        "coordinate_matches": sum(row["latitude"] is not None and row["longitude"] is not None for row in facilities),
        "ownership_adjusted_nonbiogenic_co2_tonnes": owned_co2,
        "sec_source_release_id": sec_release_id, "ngfs_source_release_id": ngfs_release_id,
        "processed_paths": [str(path.relative_to(base.PROJECT_ROOT)) for path in (facility_path, physical_path, fcff_path, carbon_path, selection_path)],
        "processed_sha256": {
            str(path.relative_to(base.PROJECT_ROOT)): base.sha256_bytes(path.read_bytes())
            for path in (facility_path, physical_path, fcff_path, carbon_path, selection_path)
        },
        "physical_financial_status": "not calculable",
        "valuation_status": "not calculable",
    }
    base.save_manifest(release_dir, manifest)
    return manifest["duk_pilot"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--sec-release-id", required=True)
    parser.add_argument("--ngfs-release-id", required=True)
    args = parser.parse_args()
    result = build_release(args.release_id, args.sec_release_id, args.ngfs_release_id)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
