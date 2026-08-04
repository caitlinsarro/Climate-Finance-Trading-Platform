#!/usr/bin/env python3
"""Build R15 public-data inputs for the eight-issuer climate DCF.

The release separates reported emissions, SEC asset values, FEMA expected
annual loss rates, and NGFS Climate Impact Explorer pathways.  It does not
convert a FEMA risk score into a loss rate or treat Scope 3 as a direct tax.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "data" / "releases"
TICKERS = ("AAPL", "CAT", "CVX", "DE", "DUK", "MSFT", "NEE", "XOM")
USER_AGENT = "Climate-Finance-Trading-Platform/1.0 zilunhe713@gmail.com"
FEMA_LAYER = "https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Counties/FeatureServer/0"
CIE_API = "https://cie-api-v2.climateanalytics.org/api/timeseries/"
RETRIEVED_AT = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

# Values are the issuer's published 2024 boundary.  Scope 3 boundaries differ
# by business model and are retained explicitly; they are never summed across
# issuers or treated as a tax payable by the issuer.
EMISSIONS = {
    "AAPL": (55_200, 3_300, 15_110_000, "total gross Scope 3", "Apple 2025 Environmental Progress Report", "https://www.apple.com/environment/pdf/Apple_Environmental_Progress_Report_2025.pdf", "apple.pdf"),
    "CAT": (680_000, 690_000, 680_000_000, "Category 11 use of sold products", "Caterpillar 2025 Sustainability Report", "https://s7d2.scene7.com/is/content/Caterpillar/CM20260508-cac43-ec231", "cat-data.pdf"),
    "CVX": (54_000_000, 4_000_000, 432_000_000, "Category 11 production method", "Chevron 2024 GHG Assurance Statement", "https://www.chevron.com/-/media/chevron/sustainability/documents/ghg-Assurance-Statement-2024.pdf", "chevron-ghg-2024.pdf"),
    "DE": (353_900, 224_000, 81_736_000, "Categories 1 and 11", "Deere 2024 Sustainability Disclosure", "https://www.deere.com/assets/pdfs/common/our-company/sustainability/data-book-2024.pdf", "deere-2024.pdf"),
    "DUK": (79_756_000, 254_000, 27_607_700, "reported upstream categories plus Category 11", "Duke Energy 2025 Sustainability Metrics", "https://s201.q4cdn.com/583395453/files/doc_downloads/2026/2025-Sustainability-Metrics-Center.pdf", "duk-metrics.pdf"),
    "MSFT": (143_510, 259_090, 15_140_000, "total reported Scope 3", "Microsoft 2025 Environmental Data Fact Sheet", "https://aka.ms/SustainabilityFactsheet2025", "microsoft-fact-sheet.pdf"),
    "NEE": (43_409_916.37, 25_603, 65_222.95, "Categories 3 and 6 only", "NextEra Energy 2025 Data Appendix", "https://www.investor.nexteraenergy.com/~/media/Files/N/NEE-IR/Sustainability/2025/Data%20Appendix.pdf", "nextera.pdf"),
    "XOM": (104_000_000, 7_000_000, 630_000_000, "Category 11 upstream-production method", "ExxonMobil 2025 Advancing Climate Solutions", "https://corporate.exxonmobil.com/-/media/global/files/advancing-climate-solutions/2025/advancing-climate-solutions-report.pdf", "exxon-2025.pdf"),
}

CIE_SCENARIOS = {
    "current_policies": "h_cpol",
    "net_zero_2050": "o_1p5c",
    "below_2c": "o_2c",
    "delayed_transition": "d_delfrag",
    "fragmented_world": "d_strain",
}

SECTORS = {
    "AAPL": "Technology", "CAT": "Industrials", "CVX": "Energy",
    "DE": "Industrials", "DUK": "Utilities", "MSFT": "Technology",
    "NEE": "Utilities", "XOM": "Energy",
}
SCOPE3_BASE_INCIDENCE = {"Technology": 0.020, "Industrials": 0.008, "Energy": 0.003, "Utilities": 0.005}
FACILITY_SHARE_BASE = {"Technology": 0.10, "Industrials": 0.25, "Energy": 0.45, "Utilities": 0.65}

PPE_TAGS = (
    "PropertyPlantAndEquipmentNet",
    "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization",
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_immutable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise RuntimeError(f"Immutable path differs: {path}")
    path.write_bytes(data)


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise RuntimeError(f"No rows for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    text = []
    from io import StringIO
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields)
    writer.writeheader()
    writer.writerows(rows)
    write_immutable(path, buf.getvalue().encode())


def download(url: str, accept: str = "*/*") -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read(), response.headers.get("Content-Type", "")


def latest_ppe(companyfacts: dict) -> dict | None:
    facts = companyfacts.get("facts", {}).get("us-gaap", {})
    candidates = []
    for tag in PPE_TAGS:
        for row in facts.get(tag, {}).get("units", {}).get("USD", []):
            if row.get("form") in {"10-K", "10-Q"} and row.get("end", "") <= "2025-12-31":
                candidates.append((row.get("end", ""), row.get("filed", ""), tag, row))
    if not candidates:
        return None
    _, _, tag, row = sorted(candidates)[-1]
    return {
        "net_ppe_usd": row["val"], "ppe_tag": tag, "ppe_period_end": row.get("end", ""),
        "ppe_filed": row.get("filed", ""), "ppe_accession": row.get("accn", ""),
    }


def weighted(rows: list[dict], value: str, weight: str) -> float | None:
    pairs = []
    for row in rows:
        try:
            v, w = float(row[value]), float(row[weight])
        except (KeyError, TypeError, ValueError):
            continue
        if w > 0:
            pairs.append((v, w))
    return None if not pairs else sum(v * w for v, w in pairs) / sum(w for _, w in pairs)


def build(release_id: str, evidence_release: str, valuation_release: str, report_dir: str) -> dict:
    release = RELEASES / release_id
    raw = release / "raw"
    processed = release / "processed"
    source_evidence = RELEASES / evidence_release
    report_dir = Path(report_dir)
    master = list(csv.DictReader((ROOT / "data" / "issuer_sector_master.csv").open()))
    master = {row["ticker"]: row for row in master if row["ticker"] in TICKERS}

    sources = []
    emissions_rows = []
    for ticker, (s1, s2, s3, s3_boundary, title, url, filename) in EMISSIONS.items():
        target = raw / "issuer_reports" / filename
        existing = report_dir / filename
        if not existing.is_file():
            prior = source_evidence / "raw" / "issuer_reports" / filename
            existing = prior if prior.is_file() else existing
        if existing.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(existing, target)
        else:
            try:
                body, _ = download(url, "application/pdf,text/html")
                write_immutable(target, body)
            except Exception:
                target = Path("")
        raw_path = str(target.relative_to(ROOT)) if target and target.is_file() else ""
        raw_hash = sha(target) if target and target.is_file() else ""
        emissions_rows.append({
            "ticker": ticker, "reporting_year": 2024, "scope1_tco2e": s1,
            "scope2_market_tco2e": s2, "scope3_tco2e": s3,
            "scope3_boundary": s3_boundary, "unit": "metric tCO2e",
            "organizational_boundary": "issuer published; operational/equity boundary as stated in source",
            "source_title": title, "source_url": url, "retrieved_at": RETRIEVED_AT,
            "raw_path": raw_path, "raw_sha256": raw_hash,
        })
        sources.append({"source": title, "url": url, "raw_path": raw_path, "sha256": raw_hash})

    emissions_path = processed / "eight_issuer_scope123_2024.csv"
    write_csv(emissions_path, emissions_rows)

    financial_rows = []
    for ticker in TICKERS:
        cik = int(float(master[ticker]["cik"]))
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
        body, _ = download(url, "application/json")
        path = raw / "sec_companyfacts" / f"{ticker}.json"
        write_immutable(path, body)
        result = latest_ppe(json.loads(body))
        if ticker == "DE" and (result is None or result.get("ppe_period_end", "") < "2024-01-01"):
            result = {
                "net_ppe_usd": 8_079_000_000, "ppe_tag": "10-K table: Property and equipment - net",
                "ppe_period_end": "2025-11-02", "ppe_filed": "2025-12-18",
                "ppe_accession": "0001104659-25-122321",
            }
        financial_rows.append({
            "ticker": ticker, **(result or {"net_ppe_usd": "", "ppe_tag": "", "ppe_period_end": "", "ppe_filed": "", "ppe_accession": ""}),
            "source_url": url if ticker != "DE" else "https://www.sec.gov/Archives/edgar/data/315189/000110465925122321/de-20251102x10k.htm",
            "raw_path": str(path.relative_to(ROOT)), "raw_sha256": sha(path),
        })
    financial_path = processed / "eight_issuer_sec_ppe_2025.csv"
    write_csv(financial_path, financial_rows)

    fema_fields = (
        "STCOFIPS,STATEABBRV,COUNTY,BUILDVALUE,EAL_VALB,ALR_VALB,"
        "CFLD_ALRB,HRCN_ALRB,HWAV_ALRB,IFLD_ALRB,SWND_ALRB,WFIR_ALRB,NRI_VER"
    )
    counties = []
    for offset in (0, 2000):
        params = urllib.parse.urlencode({
            "where": "1=1", "outFields": fema_fields, "returnGeometry": "false",
            "resultOffset": offset, "resultRecordCount": 2000,
            "orderByFields": "STCOFIPS", "f": "json",
        })
        body, _ = download(f"{FEMA_LAYER}/query?{params}", "application/json")
        path = raw / "fema_nri" / f"counties_eal_offset_{offset}.json"
        write_immutable(path, body)
        page = json.loads(body).get("features", [])
        counties.extend((row.get("attributes") or {}) for row in page)
        if len(page) < 2000:
            break
    by_fips = {row["STCOFIPS"]: row for row in counties}
    old_hazards = list(csv.DictReader((source_evidence / "processed" / "eight_issuer_fema_context_2025.csv").open()))
    facility_rows = []
    for row in old_hazards:
        county = by_fips.get(row.get("county_fips"), {})
        facility_rows.append({
            "ticker": row["ticker"], "epa_facility_id": row["epa_facility_id"],
            "facility_name": row["facility_name"], "state": row["state"], "county": row["county"],
            "county_fips": row.get("county_fips", ""), "reported_direct_tco2e": row.get("reported_direct_tco2e", ""),
            "county_building_value_usd": county.get("BUILDVALUE", ""),
            "county_building_eal_usd": county.get("EAL_VALB", ""),
            "county_building_eal_rate": county.get("ALR_VALB", ""),
            "coastal_flood_eal_rate": county.get("CFLD_ALRB", ""),
            "hurricane_eal_rate": county.get("HRCN_ALRB", ""),
            "heat_eal_rate": county.get("HWAV_ALRB", ""),
            "inland_flood_eal_rate": county.get("IFLD_ALRB", ""),
            "strong_wind_eal_rate": county.get("SWND_ALRB", ""),
            "wildfire_eal_rate": county.get("WFIR_ALRB", ""),
            "nri_version": county.get("NRI_VER", ""),
            "weighting_role": "EPA facility direct emissions is an operational-coverage weight, not asset value",
        })
    facilities_path = processed / "eight_issuer_facility_fema_eal.csv"
    write_csv(facilities_path, facility_rows)
    summary_rows = []
    for ticker in TICKERS:
        rows = [row for row in facility_rows if row["ticker"] == ticker]
        matched = [row for row in rows if row["county_building_eal_rate"] not in ("", None)]
        summary_rows.append({
            "ticker": ticker, "facility_count": len(rows), "fema_eal_matches": len(matched),
            "emissions_weighted_building_eal_rate": weighted(matched, "county_building_eal_rate", "reported_direct_tco2e") or "",
            "equal_weighted_building_eal_rate": (sum(float(r["county_building_eal_rate"]) for r in matched) / len(matched)) if matched else "",
            "weighting_method": "EPA reported direct tCO2e" if matched else "unavailable",
            "source_url": FEMA_LAYER,
        })
    physical_path = processed / "eight_issuer_fema_eal_summary.csv"
    write_csv(physical_path, summary_rows)

    cie_rows = []
    for model_key, cie_key in CIE_SCENARIOS.items():
        params = urllib.parse.urlencode({
            "iso": "USA", "region": "USA", "scenario": cie_key,
            "var": "labour-productivity-loss", "season": "annual",
            "aggregation_spatial": "gdp", "format": "json",
        })
        url = f"{CIE_API}?{params}"
        body, _ = download(url, "application/json")
        path = raw / "cie" / f"usa_labour_productivity_{cie_key}.json"
        write_immutable(path, body)
        payload = json.loads(body)
        for year, median, lower, upper in zip(payload["year"], payload["median"], payload["lower"], payload["upper"]):
            if 2025 <= int(year) <= 2050:
                cie_rows.append({
                    "scenario_key": model_key, "cie_scenario": cie_key, "year": year,
                    "median_loss_pct": median, "lower_loss_pct": lower, "upper_loss_pct": upper,
                    "country": "USA", "spatial_weight": "GDP", "unit": "percent labour productivity loss",
                    "source_url": url, "raw_path": str(path.relative_to(ROOT)), "raw_sha256": sha(path),
                })
    cie_path = processed / "ngfs_cie_usa_labour_productivity_2025_2050.csv"
    write_csv(cie_path, cie_rows)

    assumption_rows = []
    for ticker in TICKERS:
        sector = SECTORS[ticker]
        for case, scale, coverage, pass_through, s2_incidence, recovery, labour_share, labour_conversion, macro_elasticity in (
            ("low", 0.50, 0.50, 0.70, 0.25, 0.70, 0.05, 0.15, 0.35),
            ("base", 1.00, 0.75, 0.50, 0.50, 0.50, 0.10, 0.25, 0.60),
            ("high", 2.00, 1.00, 0.30, 0.75, 0.30, 0.20, 0.40, 1.00),
        ):
            assumption_rows.append({
                "ticker": ticker, "case": case,
                "scope1_policy_coverage": coverage,
                "direct_cost_pass_through": pass_through,
                "scope2_cost_incidence": s2_incidence,
                "scope3_value_chain_incidence": min(0.05, SCOPE3_BASE_INCIDENCE[sector] * scale),
                "annual_emissions_decline": {"low": 0.05, "base": 0.03, "high": 0.01}[case],
                "covered_ppe_share": min(0.90, FACILITY_SHARE_BASE[sector] * ({"low": 0.60, "base": 1.00, "high": 1.35}[case])),
                "insurance_adaptation_recovery": recovery,
                "labour_cost_share": labour_share,
                "labour_productivity_to_fcff": labour_conversion,
                "macro_cashflow_elasticity": macro_elasticity,
                "source_class": "Model assumption",
                "allowed_use": "Low/Base/High prototype sensitivity only; not issuer-observed",
            })
    assumption_path = processed / "eight_issuer_r15_model_assumptions.csv"
    write_csv(assumption_path, assumption_rows)

    paths = [emissions_path, financial_path, facilities_path, physical_path, cie_path, assumption_path]
    manifest = {
        "release_id": release_id, "feature_id": "CFP-2026-003", "created_at": RETRIEVED_AT,
        "supersedes": valuation_release,
        "status": "R15 public-data extension; engineering prototype, not model promotion",
        "climate_evidence": {"processed_paths": [str(p.relative_to(ROOT)) for p in paths]},
        "sha256": {str(p.relative_to(ROOT)): sha(p) for p in paths},
        "source_entries": sources + [
            {"source": "SEC Companyfacts", "url": "https://data.sec.gov/api/xbrl/companyfacts/", "allowed_use": "issuer net PP&E exposure base"},
            {"source": "FEMA National Risk Index", "url": FEMA_LAYER, "allowed_use": "county building expected annual loss rate"},
            {"source": "NGFS Climate Impact Explorer", "url": "https://climate-impact-explorer.climateanalytics.org/data-download/", "allowed_use": "scenario-conditioned chronic physical pathway"},
        ],
        "calculation_boundary": "Scope 1/2/3 are separate; FEMA EAL rates are not FEMA risk scores; financial conversions remain Low/Base/High assumptions.",
    }
    write_immutable(release / "manifest.json", json.dumps(manifest, indent=2).encode())
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--evidence-release", default="CFP-2026-003-R13-20260804T193000Z")
    parser.add_argument("--valuation-release", default="CFP-2026-003-R14-20260804T213000Z")
    parser.add_argument("--report-dir", default="data/releases/CFP-2026-003-R13-20260804T193000Z/raw/issuer_reports")
    args = parser.parse_args()
    print(json.dumps(build(args.release_id, args.evidence_release, args.valuation_release, args.report_dir), indent=2))
