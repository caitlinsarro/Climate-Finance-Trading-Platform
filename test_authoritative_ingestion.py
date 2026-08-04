import json
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import ingest_authoritative_data as ingestion


class AuthoritativeIngestionTests(unittest.TestCase):
    def test_sec_candidate_resolution_keeps_current_and_historical_xom_ciks(self):
        master = (
            "ticker,cik\n"
            "XOM,2115436\n"
            "AAPL,320193\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            data_dir.mkdir()
            (data_dir / "issuer_sector_master.csv").write_text(master, encoding="utf-8")
            with patch.object(ingestion, "PROJECT_ROOT", Path(temp_dir)):
                resolved = ingestion.load_sec_candidate_ciks(["XOM", "AAPL"])
        self.assertEqual(resolved["2115436"], "XOM")
        self.assertEqual(resolved["34088"], "XOM")
        self.assertEqual(resolved["320193"], "AAPL")

    def test_sec_history_range_runs_from_2009_q1_through_2026_q1(self):
        periods = ingestion.sec_quarters(2009, 2026, 1)
        self.assertEqual(periods[0], (2009, 1))
        self.assertEqual(periods[-1], (2026, 1))
        self.assertEqual(len(periods), 69)

    def test_ngfs_run_selection_requires_all_governed_model_scenario_pairs(self):
        runs = []
        run_id = 1
        for model in ingestion.NGFS_TRANSITION_MODELS:
            for scenario in ingestion.NGFS_SCENARIOS:
                runs.append(
                    {
                        "model": model,
                        "scenario": scenario,
                        "run_id": run_id,
                        "version": 2,
                        "is_default": True,
                    }
                )
                run_id += 1
        selected = ingestion.select_ngfs_transition_runs(runs)
        self.assertEqual(len(selected), 21)
        self.assertEqual(len({(row["model"], row["scenario"]) for row in selected}), 21)
        incomplete = runs[:-1]
        with self.assertRaises(RuntimeError):
            ingestion.select_ngfs_transition_runs(incomplete)
        self.assertEqual(ingestion.normalize_ngfs_scenario_label("Below 2?C"), "Below 2°C")

    def test_sec_zip_parser_keeps_point_in_time_consolidated_annual_facts(self):
        sub_text = (
            "adsh\tcik\tname\tform\tperiod\tfy\tfp\tfiled\taccepted\tsic\tinstance\n"
            "0001-26-000001\t34088\tEXXON MOBIL CORP\t10-K\t20251231\t2025\tFY\t20260220\t20260220120000\t2911\txom-20251231.htm\n"
            "0002-26-000002\t34088\tEXXON MOBIL CORP\t10-Q\t20260331\t2026\tQ1\t20260430\t20260430120000\t2911\txom-20260331.htm\n"
        )
        num_text = (
            "adsh\ttag\tversion\tddate\tqtrs\tuom\tvalue\tfootnote\tsegments\n"
            "0001-26-000001\tOperatingIncomeLoss\tus-gaap/2025\t20251231\t4\tUSD\t32000000000\t\t\n"
            "0001-26-000001\tPaymentsToAcquirePropertyPlantAndEquipment\tus-gaap/2025\t20251231\t4\tUSD\t25000000000\t\t\n"
            "0001-26-000001\tOperatingIncomeLoss\tus-gaap/2025\t20251231\t4\tUSD\t9000000000\t\t{segment}\n"
            "0001-26-000001\tCustomIssuerTag\txom/2025\t20251231\t4\tUSD\t1\t\t\n"
        )
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("sub.txt", sub_text)
            archive.writestr("num.txt", num_text)
        facts, submissions = ingestion.parse_sec_financial_statement_zip(
            buffer.getvalue(),
            {"34088": "XOM"},
            "2026Q1",
        )
        self.assertEqual(len(submissions), 1)
        self.assertEqual(len(facts), 2)
        self.assertEqual({row["tag"] for row in facts}, {"OperatingIncomeLoss", "PaymentsToAcquirePropertyPlantAndEquipment"})
        self.assertTrue(all(row["source_period"] == "2026Q1" for row in facts))
        coverage = ingestion.sec_financial_coverage_rows(facts)
        self.assertEqual(coverage[0]["ticker"], "XOM")
        self.assertTrue(coverage[0]["has_operating_income"])
        self.assertTrue(coverage[0]["has_capital_expenditure"])
        self.assertFalse(coverage[0]["has_revenue"])

    def test_immutable_release_refuses_changed_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "raw.bin"
            self.assertTrue(ingestion.write_immutable(path, b"first"))
            self.assertFalse(ingestion.write_immutable(path, b"first"))
            with self.assertRaises(RuntimeError):
                ingestion.write_immutable(path, b"changed")

    def test_latest_noaa_file_uses_latest_correction_stamp(self):
        index = b"\n".join(
            [
                b"StormEvents_details-ftp_v1.0_d2025_c20260101.csv.gz",
                b"StormEvents_details-ftp_v1.0_d2025_c20260728.csv.gz",
                b"StormEvents_details-ftp_v1.0_d2024_c20260728.csv.gz",
            ]
        )
        with patch.object(ingestion, "download_bytes", return_value=(index, "text/html")):
            url, filename = ingestion.latest_noaa_storm_url(2025)
        self.assertTrue(url.endswith("StormEvents_details-ftp_v1.0_d2025_c20260728.csv.gz"))
        self.assertEqual(filename, "StormEvents_details-ftp_v1.0_d2025_c20260728.csv.gz")

    def test_credential_status_never_returns_secret_values(self):
        secret = "do-not-write-this-key"
        with patch.dict(
            os.environ,
            {
                "EIA_API_KEY": secret,
                "FRED_API_KEY": secret,
                "BEA_API_KEY": secret,
                "SEC_USER_AGENT": secret,
            },
            clear=False,
        ):
            payload = ingestion.credential_status()
        rendered = json.dumps(payload)
        self.assertNotIn(secret, rendered)
        self.assertTrue(all("configured" in row for row in payload))

    def test_nws_ingestion_preserves_raw_bytes_and_context_only_status(self):
        source = {
            "features": [
                {
                    "id": "urn:test:1",
                    "properties": {
                        "id": "https://api.weather.gov/alerts/urn:test:1",
                        "event": "Flood Warning",
                        "onset": "2026-07-28T00:00:00Z",
                        "expires": "2026-07-29T00:00:00Z",
                        "severity": "Severe",
                        "urgency": "Immediate",
                        "certainty": "Observed",
                        "areaDesc": "Test County",
                        "geocode": {"UGC": ["TST001"]},
                    },
                }
            ]
        }
        raw_bytes = json.dumps(source, separators=(",", ":")).encode()
        with tempfile.TemporaryDirectory() as temp_dir:
            release_dir = Path(temp_dir) / "release"
            manifest = {"source_entries": []}
            with patch.object(ingestion, "PROJECT_ROOT", Path(temp_dir)), patch.object(
                ingestion,
                "download_bytes",
                return_value=(raw_bytes, "application/geo+json"),
            ):
                result = ingestion.ingest_nws(release_dir, manifest)

            raw_path = release_dir / "raw" / "nws" / "active_alerts.geojson"
            flat_path = release_dir / "processed" / "nws_alerts_flat.csv"
            self.assertEqual(raw_path.read_bytes(), raw_bytes)
            flat_text = flat_path.read_text(encoding="utf-8")

        self.assertEqual(result["records"], 1)
        self.assertIn("tactical hazard context only", flat_text)
        self.assertIn("not an occurrence probability", flat_text)
        self.assertEqual(manifest["source_entries"][0]["raw_sha256"], ingestion.sha256_bytes(raw_bytes))

    def test_treasury_ingestion_preserves_raw_and_parses_dated_rates(self):
        raw_bytes = b'''<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
 xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"
 xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
 <entry><content type="application/xml"><m:properties>
  <d:NEW_DATE m:type="Edm.DateTime">2026-07-30T00:00:00</d:NEW_DATE>
  <d:BC_3MONTH m:type="Edm.Double">3.44</d:BC_3MONTH>
  <d:BC_10YEAR m:type="Edm.Double">4.18</d:BC_10YEAR>
  <d:BC_30YEAR m:type="Edm.Double">4.82</d:BC_30YEAR>
 </m:properties></content></entry>
</feed>'''
        rows = ingestion.parse_treasury_yield_curve(raw_bytes)
        self.assertEqual(rows[0]["date"], "2026-07-30")
        self.assertEqual(rows[0]["yield_10y_pct"], "4.18")

        with tempfile.TemporaryDirectory() as temp_dir:
            release_dir = Path(temp_dir) / "release"
            manifest = {"source_entries": []}
            with patch.object(ingestion, "PROJECT_ROOT", Path(temp_dir)), patch.object(
                ingestion,
                "download_bytes",
                return_value=(raw_bytes, "application/xml"),
            ):
                result = ingestion.ingest_treasury(release_dir, manifest, 2026)
            raw_path = release_dir / "raw" / "treasury" / "daily_yield_curve_2026.xml"
            flat_path = release_dir / "processed" / "treasury_yield_curve_2026.csv"
            self.assertEqual(raw_path.read_bytes(), raw_bytes)
            flat_text = flat_path.read_text(encoding="utf-8")

        self.assertEqual(result["records"], 1)
        self.assertEqual(result["latest_observation_date"], "2026-07-30")
        self.assertIn("4.18", flat_text)
        self.assertIn("not an ERP or complete WACC", flat_text)
        self.assertEqual(manifest["source_entries"][0]["source_id"], "SRC-US-TREASURY")


if __name__ == "__main__":
    unittest.main()
