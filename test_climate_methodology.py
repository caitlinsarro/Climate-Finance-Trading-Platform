import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class ClimateMethodologyTests(unittest.TestCase):
    def test_hash_verified_sec_history_is_loaded_but_fcff_remains_pending(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            release = root / "CFP-2026-003-R8-test"
            processed = release / "processed"
            processed.mkdir(parents=True)
            facts = processed / "facts.csv"
            coverage = processed / "coverage.csv"
            facts.write_text("ticker,value\nAAPL,1\n", encoding="utf-8")
            coverage.write_text("ticker,coverage_pct\nAAPL,90\n", encoding="utf-8")
            manifest = {
                "release_id": "CFP-2026-003-R8-test",
                "sec_financial_history": {
                    "start_period": "2009Q1",
                    "end_period": "2026Q1",
                    "quarter_count": 69,
                    "tickers": ["AAPL"],
                    "processed_fact_path": str(facts),
                    "processed_fact_sha256": hashlib.sha256(facts.read_bytes()).hexdigest(),
                    "coverage_path": str(coverage),
                    "coverage_sha256": hashlib.sha256(coverage.read_bytes()).hexdigest(),
                    "fact_count": 1,
                    "filing_count": 1,
                },
            }
            (release / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            loaded = app.latest_official_sec_financial_history(root)
        self.assertTrue(loaded["is_loaded"])
        self.assertEqual(loaded["quarter_count"], 69)
        self.assertIn("FCFF tie-out pending", loaded["status"])

    def setUp(self):
        self.energy = {
            "name": "Energy",
            "ticker": "SECTOR",
            "sector": "Energy",
            "weight": 1.0,
            "vulnerability": app.issuer_vulnerability_profile("Energy", "Energy"),
        }

    def test_same_target_and_reference_has_zero_impact(self):
        scenario = app.CLIMATE_SCENARIO_PATHS["current_policies"]
        result = app.scenario_repricing_for_scope([self.energy], scenario, scenario, 2050)
        self.assertAlmostEqual(result["value_impact"], 0.0, places=6)
        self.assertAlmostEqual(result["physical_loss_delta"], 0.0, places=6)
        self.assertAlmostEqual(result["transition_loss_delta"], 0.0, places=6)

    def test_current_policies_has_more_physical_loss_than_net_zero(self):
        vulnerability = self.energy["vulnerability"]
        hot = app.scenario_terminal_components(app.CLIMATE_SCENARIO_PATHS["current_policies"], "Energy", vulnerability, 2050)
        net_zero = app.scenario_terminal_components(app.CLIMATE_SCENARIO_PATHS["net_zero_2050"], "Energy", vulnerability, 2050)
        hot_physical = hot["acute_physical"] + hot["chronic_physical"]
        net_zero_physical = net_zero["acute_physical"] + net_zero["chronic_physical"]
        self.assertGreater(hot_physical, net_zero_physical)

    def test_net_zero_creates_energy_transition_stress_and_technology_opportunity(self):
        energy = app.scenario_terminal_components(
            app.CLIMATE_SCENARIO_PATHS["net_zero_2050"],
            "Energy",
            app.issuer_vulnerability_profile("XOM", "Energy"),
            2050,
        )
        technology = app.scenario_terminal_components(
            app.CLIMATE_SCENARIO_PATHS["net_zero_2050"],
            "Technology",
            app.issuer_vulnerability_profile("AAPL", "Technology"),
            2050,
        )
        self.assertGreater(energy["micro_transition"], 0.0)
        self.assertLess(technology["micro_transition"], 0.0)

    def test_transition_channels_reconcile_and_exclude_co2_concentration(self):
        low_co2 = {
            "current_warming": 1.20,
            "disaster_10y_avg": 18.0,
            "co2_ppm": 395.0,
            "co2_10y_change": 10.0,
            "source_mode": "official test data",
        }
        high_co2 = {**low_co2, "co2_ppm": 470.0, "co2_10y_change": 45.0}
        signal = {"daily_pressure": 0.2, "allocation_pressure": 0.2, "source_mode": "NWS active test"}
        low_state = app.climate_state_variables(signal, low_co2)
        high_state = app.climate_state_variables(signal, high_co2)
        self.assertEqual(low_state["macro_transition_state"], 0.0)
        self.assertEqual(high_state["macro_transition_state"], 0.0)
        self.assertEqual(low_state["chronic_climate_state"], high_state["chronic_climate_state"])
        self.assertNotIn("transition_proxy", low_state["calculation"])

        components = app.scenario_terminal_components(
            app.CLIMATE_SCENARIO_PATHS["net_zero_2050"],
            "Energy",
            app.issuer_vulnerability_profile("XOM", "Energy"),
            2050,
        )
        channel_sum = sum(
            components[key]
            for key in ("sector_demand", "carbon_cost", "energy_cost", "transition_capex", "pass_through_offset")
        )
        self.assertAlmostEqual(channel_sum, components["micro_transition"], places=12)
        self.assertGreater(components["carbon_cost"], 0.0)
        self.assertGreater(components["transition_capex"], 0.0)
        self.assertLess(components["pass_through_offset"], 0.0)

    def test_mixed_payload_never_labels_proxy_temperature_as_official(self):
        def fake_download(url, timeout=12, headers=None):
            if url == app.NASA_GISTEMP_CSV_URL:
                raise OSError("NASA unavailable")
            if url == app.NOAA_CO2_CSV_URL:
                return "year,month,average\n2024,1,424.2\n2024,2,425.0\n"
            if url == app.NCEI_BILLION_EVENTS_JSON_URL:
                return json.dumps(
                    {
                        "event-1": {
                            "begDate": "20240101",
                            "lower95": 1.0,
                            "upper95": 3.0,
                        }
                    }
                )
            raise AssertionError(f"Unexpected URL: {url}")

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "climate.json"
            with patch.object(app, "CLIMATE_DATA_CACHE", cache_path), patch.object(
                app, "download_text", side_effect=fake_download
            ):
                payload = app.load_official_climate_data(force_refresh=True)

        row_2024 = next(row for row in payload["rows"] if row["year"] == 2024)
        self.assertEqual(payload["source_mode"], "mixed official and non-official climate data")
        self.assertEqual(row_2024["temperature_source"], "calibrated proxy")
        self.assertFalse(row_2024["is_complete_official_observation"])
        self.assertEqual(row_2024["allowed_use"], "context only")

    def test_cached_payload_preserves_original_source_classification(self):
        payload = {
            "source_mode": "mixed official and non-official climate data",
            "rows": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "climate.json"
            cache_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(app, "CLIMATE_DATA_CACHE", cache_path):
                cached = app.read_cached_official_climate_data()

        self.assertEqual(cached["source_mode"], payload["source_mode"])
        self.assertEqual(cached["cache_status"], "cached")

    def test_legacy_cache_with_fallback_notes_is_reclassified(self):
        payload = {
            "source_mode": "official climate data",
            "source_notes": [
                "fallback temperature proxy",
                "NOAA GML Mauna Loa monthly CO2",
            ],
            "rows": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "climate.json"
            cache_path.write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(app, "CLIMATE_DATA_CACHE", cache_path):
                cached = app.read_cached_official_climate_data()

        self.assertEqual(cached["source_mode"], "mixed official and non-official climate data")
        self.assertEqual(cached["source_mode_original"], "official climate data")
        self.assertIn("legacy cache relabeled", cached["classification_correction"])

    def test_official_feeds_with_incomplete_rows_are_not_wholly_official(self):
        def fake_download(url, timeout=12, headers=None):
            if url == app.NASA_GISTEMP_CSV_URL:
                return "Year,J-D\n2024,1.2\n"
            if url == app.NOAA_CO2_CSV_URL:
                return "year,month,average\n2024,1,424.2\n2026,1,430.0\n"
            if url == app.NCEI_BILLION_EVENTS_JSON_URL:
                return json.dumps(
                    {
                        "event-2024": {"begDate": "20240101", "lower95": 1.0, "upper95": 3.0},
                        "event-2026": {"begDate": "20260101", "lower95": 1.0, "upper95": 3.0},
                    }
                )
            raise AssertionError(f"Unexpected URL: {url}")

        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "climate.json"
            with patch.object(app, "CLIMATE_DATA_CACHE", cache_path), patch.object(
                app, "download_text", side_effect=fake_download
            ):
                payload = app.load_official_climate_data(force_refresh=True)

        self.assertEqual(
            payload["source_mode"],
            "official-source climate data with incomplete observations",
        )
        self.assertTrue(next(row for row in payload["rows"] if row["year"] == 2024)["is_complete_official_observation"])
        self.assertFalse(next(row for row in payload["rows"] if row["year"] == 2026)["is_complete_official_observation"])

    def test_proxy_rows_make_climate_outputs_not_calculable(self):
        payload = {
            "source_mode": "non-official fallback climate data",
            "source_notes": ["fallback proxies"],
            "source_urls": {},
            "rows": [
                {
                    "year": 2024,
                    "temperature_anomaly": 1.2,
                    "co2_ppm": 425.0,
                    "billion_dollar_disasters": 20,
                    "disaster_cost_proxy": 50.0,
                    "is_complete_official_observation": False,
                }
            ],
        }
        with patch.object(app, "load_official_climate_data", return_value=payload):
            context = app.climate_data_context()
            signal = app.climate_signal()

        self.assertIsNone(context["current_warming"])
        self.assertIsNone(context["climate_pressure_multiplier"])
        self.assertIn("not calculable", context["source_status"])
        self.assertEqual(signal, [])

    def test_co2_is_context_only_in_allocation_signal(self):
        base_rows = [
            {
                "year": year,
                "temperature_anomaly": temperature,
                "co2_ppm": co2,
                "billion_dollar_disasters": disasters,
                "disaster_cost_proxy": cost,
                "is_complete_official_observation": True,
            }
            for year, temperature, co2, disasters, cost in (
                (2022, 0.9, 415.0, 12, 30.0),
                (2023, 1.1, 420.0, 15, 40.0),
                (2024, 1.3, 425.0, 20, 70.0),
            )
        ]
        high_co2_rows = [{**row, "co2_ppm": row["co2_ppm"] + index * 100} for index, row in enumerate(base_rows)]

        with patch.object(app, "load_official_climate_data", return_value={"rows": base_rows}):
            base_signal = app.climate_signal()
        with patch.object(app, "load_official_climate_data", return_value={"rows": high_co2_rows}):
            high_co2_signal = app.climate_signal()

        self.assertEqual(
            [row["climate_risk_score"] for row in base_signal],
            [row["climate_risk_score"] for row in high_co2_signal],
        )

    def test_embedded_proxy_table_has_no_current_or_future_years(self):
        self.assertTrue(app.CLIMATE_PROXY)
        self.assertLess(max(row[0] for row in app.CLIMATE_PROXY), app.CURRENT_YEAR)

    def test_transition_pressure_has_a_traceable_sector_cash_flow_driver(self):
        energy = app.structural_transition_pressure("Energy")
        technology = app.structural_transition_pressure("Technology")
        self.assertGreater(energy["risk"], technology["risk"])
        self.assertGreater(energy["demand_shift"], 0.0)
        self.assertLess(technology["demand_shift"], 0.0)
        self.assertIn("NGFS and SEC history are loaded", energy["status"])
        self.assertIn("issuer accounting tie-out", energy["status"])

    def test_three_layer_revenue_transmission_is_separate_and_traceable(self):
        scenario = app.CLIMATE_SCENARIO_PATHS["delayed_transition"]
        industrial = app.scenario_terminal_components(
            scenario,
            "Industrials",
            app.issuer_vulnerability_profile("SECTOR", "Industrials"),
            2050,
        )
        utility = app.scenario_terminal_components(
            scenario,
            "Utilities",
            app.issuer_vulnerability_profile("SECTOR", "Utilities"),
            2050,
        )
        self.assertGreater(industrial["country_gdp"], utility["country_gdp"])
        self.assertGreater(industrial["supply_chain"], utility["supply_chain"])
        self.assertIn("gdp_beta", industrial["macro_channel_inputs"])
        self.assertIn("revenue geography", industrial["macro_channel_inputs"]["status"])

    def test_sector_demand_is_counted_once_in_dcf_components(self):
        self.assertIn("sector_demand", app.DCF_COMPONENTS)
        self.assertNotIn("demand_shift", app.DCF_COMPONENTS)
        self.assertNotIn("macro_transition", app.DCF_COMPONENTS)

    def test_value_attribution_reconciles_to_total(self):
        result = app.scenario_repricing_for_scope(
            [self.energy],
            app.CLIMATE_SCENARIO_PATHS["current_policies"],
            app.CLIMATE_SCENARIO_PATHS["baseline"],
            2050,
        )
        contribution = sum(row["value_contribution"] for row in result["attribution"])
        self.assertAlmostEqual(contribution, result["value_impact"], places=3)
        self.assertAlmostEqual(result["attribution_residual"], 0.0, places=7)

    def test_physical_downscaling_conserves_country_loss(self):
        weights = app.normalized_sector_value_added_weights()
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=12)
        reconciliation = app.physical_downscaling_reconciliation()
        self.assertAlmostEqual(reconciliation["acute"], 1.0, places=12)
        self.assertAlmostEqual(reconciliation["chronic"], 1.0, places=12)

    def test_unknown_issuer_uses_sector_median_fallback(self):
        first = app.issuer_vulnerability_profile("UNKNOWN1", "Technology")
        second = app.issuer_vulnerability_profile("UNKNOWN2", "Technology")
        self.assertEqual(first, second)
        self.assertEqual(first["acute_ratio"], 1.0)
        self.assertEqual(first["chronic_ratio"], 1.0)
        self.assertEqual(first["quality"], "Sector research fallback; issuer vulnerability not verified")
        self.assertFalse(first["issuer_specific"])
        self.assertEqual(first["evidence_grade"], "Proxy-dominant")

    def test_unsupported_ticker_overrides_do_not_create_issuer_vulnerability(self):
        apple = app.issuer_vulnerability_profile("AAPL", "Technology")
        microsoft = app.issuer_vulnerability_profile("MSFT", "Technology")
        unknown = app.issuer_vulnerability_profile("UNKNOWN1", "Technology")
        self.assertEqual(apple, microsoft)
        self.assertEqual(apple, unknown)
        self.assertEqual(apple["acute_ratio"], 1.0)
        self.assertEqual(apple["chronic_ratio"], 1.0)

    def test_expanding_zscore_is_invariant_to_future_append(self):
        prefix = [1.0, 2.0, 4.0, 3.0]
        extended = prefix + [100.0, -50.0]
        self.assertAlmostEqual(
            app.expanding_zscore(prefix, len(prefix) - 1),
            app.expanding_zscore(extended, len(prefix) - 1),
            places=12,
        )

    def test_historical_climate_pressure_uses_only_prior_vintages(self):
        rows = [
            {"year": 2024, "climate_risk_score": 1.0},
            {"year": 2025, "climate_risk_score": 100.0},
        ]
        self.assertEqual(app.historical_climate_pressure_for_year(2025, rows), 0.5)
        self.assertGreater(app.historical_climate_pressure_for_year(2026, rows), 0.5)

    def test_regime_fallback_never_uses_future_vintage(self):
        rows = [
            {"year": 2025, "risk_state": "High Climate Risk", "climate_risk_score": 2.0},
            {"year": 2027, "risk_state": "High Climate Risk", "climate_risk_score": 3.0},
        ]
        result = app.regime_for_year(2024, rows)
        self.assertEqual(result["signal_year"], 2023)
        self.assertEqual(result["regime"], "Normal Climate Risk")

    def test_scenario_matrix_does_not_claim_probabilities(self):
        allocation = [
            {"year": 2026, "ticker": ticker, "climate_weight": 1 / len(app.SECTOR_ETFS)}
            for ticker in app.SECTOR_ETFS
        ]
        rows, summary = app.climate_scenario_matrix(allocation)
        self.assertTrue(rows)
        self.assertTrue(all("probability" not in row for row in rows))
        self.assertIn("No occurrence probabilities", summary["scenario_probability_method"])
        self.assertNotIn("cvor_95", summary)
        self.assertEqual(summary["tail_count"], app.SCENARIO_TAIL_COUNT)
        self.assertIn("physical_model_risk_loss_floor", summary)
        self.assertIn("physical_model_risk_loss_ceiling", summary)
        self.assertGreaterEqual(
            summary["physical_model_risk_loss_ceiling"],
            summary["physical_model_risk_loss_floor"],
        )
        self.assertTrue(all("physical_model_risk_high_loss_rate" in row for row in rows))

    def test_daily_overlay_is_zero_sum_hazard_specific_and_capped(self):
        base_rows = [
            {"year": 2026, "ticker": ticker, "sector": app.SECTOR_ETFS[ticker]["name"], "climate_weight": 0.20, "benchmark_weight": 0.20}
            for ticker in ["XLK", "XLE", "XLU", "XLI", "XLF"]
        ]
        signal = {
            "daily_pressure": 0.80,
            "allocation_pressure": 0.90,
            "top_driver": "heat",
            "category_intensity": {"heat": 1.0},
        }
        adjusted = app.apply_daily_climate_overlay(base_rows, signal)
        self.assertAlmostEqual(sum(row["climate_weight"] for row in adjusted), 1.0, places=3)
        self.assertLessEqual(max(abs(row["daily_adjustment_bps"]) for row in adjusted), app.TACTICAL_OVERLAY_LIMIT_BPS)
        by_ticker = {row["ticker"]: row for row in adjusted}
        self.assertGreater(by_ticker["XLK"]["daily_hazard_beta"], 0.0)
        self.assertLess(by_ticker["XLK"]["daily_hazard_beta"], by_ticker["XLU"]["daily_hazard_beta"])
        self.assertGreater(by_ticker["XLK"]["daily_adjustment_bps"], by_ticker["XLU"]["daily_adjustment_bps"])

    def test_daily_overlay_does_not_trade_without_hazard_mix(self):
        base_rows = [
            {"year": 2026, "ticker": ticker, "sector": app.SECTOR_ETFS[ticker]["name"], "climate_weight": 0.20, "benchmark_weight": 0.20}
            for ticker in ["XLK", "XLE", "XLU", "XLI", "XLF"]
        ]
        adjusted = app.apply_daily_climate_overlay(
            base_rows,
            {"daily_pressure": 0.80, "allocation_pressure": 0.90, "top_driver": "fallback", "category_intensity": {}},
        )
        self.assertTrue(all(row["daily_adjustment_bps"] == 0 for row in adjusted))

    def test_live_nws_remains_calculable_when_long_run_context_is_unavailable(self):
        nws_payload = {
            "features": [
                {
                    "properties": {
                        "event": "Excessive Heat Warning",
                        "severity": "Severe",
                        "areaDesc": "Test County",
                    }
                }
            ]
        }
        unavailable_context = {
            "climate_pressure_multiplier": None,
            "source_status": "not calculable — no complete official completed-year observation",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "daily.json"
            with patch.object(app, "DAILY_CLIMATE_CACHE", cache_path), patch.object(
                app, "download_text", return_value=json.dumps(nws_payload)
            ), patch.object(app, "climate_data_context", return_value=unavailable_context):
                signal = app.load_daily_climate_signal(force_refresh=True)

        self.assertTrue(signal["is_calculable"])
        self.assertFalse(signal["observed_zero"])
        self.assertEqual(signal["climate_alerts"], 1)
        self.assertGreater(signal["daily_pressure"], 0.0)
        self.assertEqual(signal["allocation_pressure"], signal["daily_pressure"])
        self.assertIn("long-run context excluded", signal["long_run_context_status"])

    def test_successful_nws_observed_zero_produces_no_tactical_trade(self):
        nws_payload = {
            "features": [
                {
                    "properties": {
                        "event": "Administrative Message",
                        "severity": "Unknown",
                        "areaDesc": "Test Area",
                    }
                }
            ]
        }
        unavailable_context = {
            "climate_pressure_multiplier": None,
            "source_status": "not calculable — no complete official completed-year observation",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "daily.json"
            with patch.object(app, "DAILY_CLIMATE_CACHE", cache_path), patch.object(
                app, "download_text", return_value=json.dumps(nws_payload)
            ), patch.object(app, "climate_data_context", return_value=unavailable_context):
                signal = app.load_daily_climate_signal(force_refresh=True)

        state = app.climate_state_variables(daily_signal=signal, context=unavailable_context)
        nowcast = app.event_nowcast_for_scope([self.energy], signal, state)
        self.assertTrue(signal["is_calculable"])
        self.assertTrue(signal["observed_zero"])
        self.assertEqual(signal["daily_pressure"], 0.0)
        self.assertEqual(nowcast["event_risk"], 0.0)
        self.assertEqual(nowcast["tactical_overlay_bps"], 0)
        self.assertIn("No tactical trade", nowcast["action"])
        self.assertIn("observed zero", nowcast["decision_status"])

    def test_unavailable_nws_is_not_numeric_zero_and_suppresses_tactical_trade(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / "daily.json"
            with patch.object(app, "DAILY_CLIMATE_CACHE", cache_path), patch.object(
                app, "download_text", side_effect=OSError("NWS unavailable")
            ):
                signal = app.load_daily_climate_signal(force_refresh=True)

        state = app.climate_state_variables(daily_signal=signal, context={})
        nowcast = app.event_nowcast_for_scope([self.energy], signal, state)
        self.assertFalse(signal["is_calculable"])
        self.assertIsNone(signal["daily_pressure"])
        self.assertIsNone(signal["climate_alerts"])
        self.assertIsNone(nowcast["event_risk"])
        self.assertIsNone(nowcast["selection_risk"])
        self.assertEqual(nowcast["tactical_overlay_bps"], 0)
        self.assertIn("No tactical trade", nowcast["action"])
        self.assertIn("not calculable", nowcast["decision_status"])

    def test_physical_event_loss_uses_hazard_exposure_vulnerability_resilience(self):
        loss = app.physical_event_loss(0.80, 0.75, 1.20, 0.40)
        self.assertAlmostEqual(loss, 0.80 * 0.75 * 1.20 * 0.60, places=12)
        self.assertLess(app.physical_event_loss(0.80, 0.75, 1.20, 0.80), loss)

    def test_missing_facility_data_is_labeled_as_sector_fallback(self):
        with patch.object(app, "load_facility_exposure_data", return_value={}):
            profile = app.issuer_hazard_exposure_profile("UNKNOWN", "Industrials")
        self.assertEqual(profile["observed_hazards"], 0)
        self.assertIn("facility geolocation not loaded", profile["data_quality"])
        self.assertEqual(set(profile["hazards"]), set(app.HAZARD_CATEGORIES))

    def test_climate_board_contains_observed_alerts_not_duplicate_picks(self):
        signal = {
            "source_mode": "test NWS input",
            "source_url": "https://api.weather.gov/alerts/active",
            "alerts_total": 2,
            "climate_alerts": 2,
            "top_driver": "heat",
            "daily_pressure": 0.5,
            "allocation_pressure": 0.4,
            "category_counts": {"heat": 2},
            "category_intensity": {"heat": 0.7},
            "sample_events": [],
        }
        with patch.object(app, "load_daily_climate_signal", return_value=signal):
            result = app.daily_climate_board_payload()

        self.assertTrue(result["daily_alerts"])
        self.assertNotIn("stock_recommendations", result)
        self.assertNotIn("etf_recommendations", result)
        self.assertNotIn("market_interval", result)

    def test_market_history_never_substitutes_simulated_returns(self):
        with patch.object(app, "yf", None):
            prices, source = app.fetch_daily_close_history(["SPY", "QQQ"], period="3y")

        self.assertTrue(all(not values for values in prices.values()))
        self.assertEqual(source, "market data unavailable")

    def test_bounded_priority_allocation_respects_budget_and_effective_caps(self):
        rows = [
            {"ticker": "A", "priority": 4.0, "confidence_cap": 0.45},
            {"ticker": "B", "priority": 2.0, "confidence_cap": 0.35},
            {"ticker": "C", "priority": 1.0, "confidence_cap": 0.30},
        ]
        weights, caps = app.bounded_priority_allocation(rows, 1.0, "priority")
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=10)
        for ticker, weight in weights.items():
            self.assertLessEqual(weight, caps[ticker] + 1e-12)
        self.assertGreaterEqual(weights["A"], weights["B"])
        self.assertGreaterEqual(weights["B"], weights["C"])

    def test_optimizer_risk_budget_reconciles_with_weights(self):
        daily_signal = {
            "allocation_pressure": 0.20,
            "category_intensity": {},
            "category_counts": {},
            "source_mode": "test NWS input",
            "climate_alerts": 1,
            "top_driver": "heat",
        }
        climate_context = {
            "current_warming": 1.20,
            "disaster_10y_avg": 18.0,
            "co2_ppm": 425.0,
            "co2_10y_change": 24.0,
            "source_mode": "cached official test data",
        }

        def fake_market(symbols, period="3mo", interval="1d"):
            charts = {
                symbol: [
                    {"close": 100.0, "volume": 1_000_000},
                    {"close": 101.0, "volume": 1_100_000},
                ]
                for symbol in symbols
            }
            return {"source": "test", "period": period, "interval": interval, "charts": charts}

        with patch.object(app, "load_daily_climate_signal", return_value=daily_signal), patch.object(
            app, "climate_data_context", return_value=climate_context
        ), patch.object(app, "market_chart_payload", side_effect=fake_market):
            result = app.portfolio_optimizer_payload(
                mode="etf_only",
                capital=50_000_000,
                horizon="long",
                style="balanced",
                etfs="SPY,QQQ,XLK,XLE,XLU,XLI",
            )

        weights = [row["target_weight"] for row in result["rows"]]
        expected_hhi = sum(weight * weight for weight in weights)
        budget = result["risk_budget"]
        self.assertAlmostEqual(sum(weights), 1.0, places=3)
        self.assertAlmostEqual(budget["hhi"], expected_hhi, places=3)
        self.assertAlmostEqual(budget["effective_positions"], 1 / expected_hhi, places=1)
        self.assertGreaterEqual(len(budget["checks"]), 12)
        self.assertEqual(budget["effective_cap_breaches"], 0)
        self.assertIn("worst_portfolio_scenario_loss", budget)
        self.assertTrue(budget["portfolio_scenario_losses"])
        self.assertTrue(all("cvor_proxy" not in row for row in result["rows"]))
        self.assertTrue(all("scenario_tail_proxy" in row for row in result["rows"]))
        self.assertTrue(all("climate_alpha" not in row for row in result["rows"]))
        self.assertTrue(all("climate_risk_indicator" in row for row in result["rows"]))
        self.assertIn("max mu'w", result["methodology"]["formula"])

    def test_valuation_uses_capm_wacc_and_sector_capital_structure(self):
        energy = app.valuation_assumptions("XOM", "Energy", observed_beta=1.10)
        utility = app.valuation_assumptions("XLU", "Utilities", observed_beta=0.60)
        self.assertNotEqual(energy["wacc"], utility["wacc"])
        self.assertNotEqual(energy["terminal_growth"], utility["terminal_growth"])
        self.assertIn("risk-free + beta x ERP", energy["formula"])
        self.assertFalse(energy["issuer_point_estimate_allowed"])

    def test_governed_treasury_release_supplies_dated_risk_free_rate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            release = Path(temp_dir) / "CFP-2026-003-R1-test"
            processed = release / "processed"
            processed.mkdir(parents=True)
            csv_path = processed / "treasury_yield_curve_2026.csv"
            csv_path.write_text("date,yield_10y_pct\n2026-07-30,4.18\n", encoding="utf-8")
            manifest = {
                "release_id": "CFP-2026-003-R1-test",
                "source_entries": [
                    {
                        "source_id": "SRC-US-TREASURY",
                        "source_url": "https://home.treasury.gov/test",
                        "processed_path": "data/releases/CFP-2026-003-R1-test/processed/treasury_yield_curve_2026.csv",
                    }
                ],
            }
            (release / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            result = app.latest_official_treasury_rate("10y", releases_root=temp_dir)
        self.assertAlmostEqual(result["rate"], 0.0418, places=8)
        self.assertEqual(result["as_of"], "2026-07-30")
        self.assertEqual(result["source_class"], "observed official government rate")

    def test_broad_market_etf_uses_economy_composite_not_technology(self):
        sector, _, _ = app.etf_climate_profile("SPY")
        self.assertEqual(app.normalize_model_sector(sector), "Economy")
        transition = app.structural_transition_pressure("Economy")
        self.assertIn("Value-added-weighted economy", transition["status"])
        vulnerability = app.issuer_vulnerability_profile("SPY", "Economy")
        self.assertEqual(vulnerability["quality"], "Economy-weighted sector fallback")

    def test_short_term_overlay_is_zero_sum_around_strategic_weights(self):
        rows = [
            {"ticker": "A", "asset_type": "ETF", "tactical_market_score": 0.8, "tactical_event_risk": 0.1},
            {"ticker": "B", "asset_type": "ETF", "tactical_market_score": 0.5, "tactical_event_risk": 0.4},
            {"ticker": "C", "asset_type": "ETF", "tactical_market_score": 0.3, "tactical_event_risk": 0.7},
        ]
        strategic = {"A": 0.34, "B": 0.33, "C": 0.33}
        caps = {"A": 0.50, "B": 0.50, "C": 0.50}
        final, overlays = app.apply_zero_sum_tactical_overlay(rows, strategic, caps, {"ETF": 1.0, "Stock": 0.0})
        self.assertAlmostEqual(sum(final.values()), 1.0, places=12)
        self.assertAlmostEqual(sum(overlays.values()), 0.0, places=12)
        self.assertLessEqual(max(abs(value) for value in overlays.values()), app.TACTICAL_OVERLAY_LIMIT_BPS / 10_000 + 1e-12)

    def test_walk_forward_backtest_reports_net_cost_and_turnover(self):
        dates = [f"2026-{1 + index // 28:02d}-{1 + index % 28:02d}" for index in range(50)]
        daily_moves = {"SPY": 0.0010, "QQQ": 0.0018, "XLE": -0.0004, "XLU": 0.0003, "XLI": 0.0007}
        prices = {
            symbol: {date: 100 * ((1 + move) ** index) for index, date in enumerate(dates)}
            for symbol, move in daily_moves.items()
        }
        climate_rows = [{"year": 2026, "climate_risk_score": 1.0, "top_quartile_threshold": 0.5}]
        rows = app.build_walk_forward_buy_sell_backtest_rows(
            list(daily_moves),
            prices,
            climate_rows,
            top_n=2,
            trading_cost_bps=10,
            annual_borrow_cost_bps=100,
        )

        self.assertTrue(rows)
        self.assertGreater(rows[0]["turnover"], 0)
        self.assertGreater(rows[0]["total_cost"], 0)
        self.assertLess(rows[0]["recommended_return"], rows[0]["gross_recommended_return"])
        self.assertEqual(rows[0]["benchmark_exposure"], 0.75)
        self.assertEqual(rows[0]["cash_weight"], 0.25)
        self.assertIn("market_only_return", rows[0])
        self.assertIn("incremental_climate_return", rows[0])
        self.assertAlmostEqual(
            rows[0]["benchmark_return"],
            0.75 * rows[0]["unscaled_benchmark_return"],
            places=5,
        )
        window = app.summarize_daily_recommendation_window(rows, 15, "3 months")
        self.assertGreaterEqual(
            window["summary"]["gross_recommended_total_return"],
            window["summary"]["recommended_total_return"],
        )
        self.assertIn("information_ratio", window["summary"])
        self.assertIn("incremental_climate_value", window["summary"])
        self.assertIn("bootstrap_95_ci", window["summary"])

    def test_controlled_issuer_sector_mapping_overrides_conflicting_ui_sector(self):
        gs = app.resolve_issuer_sector("GS", "Technology")
        msft = app.resolve_issuer_sector("MSFT", "Technology")
        self.assertTrue(gs["is_calculable"])
        self.assertTrue(gs["has_conflict"])
        self.assertEqual(gs["resolved_sector"], "Financials")
        self.assertIn("overridden", gs["status"])
        self.assertTrue(msft["is_calculable"])
        self.assertFalse(msft["has_conflict"])
        self.assertEqual(msft["resolved_sector"], "Technology")

    def test_local_issuer_sector_master_has_broad_coverage_and_pfe_healthcare(self):
        with app.ISSUER_SECTOR_MASTER_LOCK:
            app.ISSUER_SECTOR_MASTER_CACHE = None
        master = app.load_issuer_sector_master()
        resolution = app.resolve_issuer_sector("PFE", "Financials")

        self.assertGreaterEqual(len(master), 5_000)
        self.assertIn("PFE", master)
        self.assertEqual(master["PFE"]["sector_canonical"], "Healthcare")
        self.assertEqual(master["PFE"]["mapping_status"], "eligible_equity_reference")
        self.assertTrue(resolution["is_calculable"])
        self.assertTrue(resolution["has_conflict"])
        self.assertEqual(resolution["resolved_sector"], "Healthcare")
        self.assertEqual(resolution["mapping_tier"], "local SEC/Nasdaq issuer-sector master")
        self.assertTrue(resolution["cik"])
        self.assertTrue(resolution["exchange"])

    def test_on_demand_metadata_is_used_when_ticker_is_absent_from_local_master(self):
        class FakeTicker:
            def get_info(self):
                return {
                    "symbol": "TESTCO",
                    "shortName": "Test Company",
                    "quoteType": "EQUITY",
                    "exchange": "NYQ",
                    "sector": "Healthcare",
                    "industry": "Drug Manufacturers - General",
                }

        class FakeYFinance:
            @staticmethod
            def Ticker(symbol):
                self.assertEqual(symbol, "TESTCO")
                return FakeTicker()

        with patch.object(app, "yf", FakeYFinance), patch.object(
            app, "load_issuer_sector_master", return_value={}
        ), patch.dict(app.MARKET_SECTOR_METADATA_CACHE, {}, clear=True):
            resolution = app.resolve_issuer_sector("TESTCO", "Financials")
            cached = app.resolve_issuer_sector("TESTCO", "Healthcare")

        self.assertTrue(resolution["is_calculable"])
        self.assertTrue(resolution["has_conflict"])
        self.assertEqual(resolution["resolved_sector"], "Healthcare")
        self.assertEqual(resolution["issuer_name"], "Test Company")
        self.assertEqual(resolution["exchange"], "NYQ")
        self.assertEqual(resolution["industry"], "Drug Manufacturers - General")
        self.assertEqual(resolution["mapping_tier"], "on-demand listed-equity metadata")
        self.assertFalse(cached["has_conflict"])

    def test_on_demand_sector_mapping_rejects_non_equity_quote_types(self):
        class FakeTicker:
            def get_info(self):
                return {
                    "symbol": "FAKEETF",
                    "quoteType": "ETF",
                    "sector": "Technology",
                }

        class FakeYFinance:
            @staticmethod
            def Ticker(symbol):
                return FakeTicker()

        with patch.object(app, "yf", FakeYFinance), patch.object(
            app, "load_issuer_sector_master", return_value={}
        ), patch.dict(app.MARKET_SECTOR_METADATA_CACHE, {}, clear=True):
            resolution = app.resolve_issuer_sector("FAKEETF", "Technology")

        self.assertFalse(resolution["is_calculable"])
        self.assertIsNone(resolution["resolved_sector"])
        self.assertIn("not an eligible listed equity", resolution["status"])

    def test_invalid_ticker_syntax_does_not_call_market_metadata_provider(self):
        class FailingYFinance:
            @staticmethod
            def Ticker(symbol):
                raise AssertionError("invalid ticker must not reach the provider")

        with patch.object(app, "yf", FailingYFinance), patch.object(
            app, "load_issuer_sector_master", return_value={}
        ), patch.dict(app.MARKET_SECTOR_METADATA_CACHE, {}, clear=True):
            resolution = app.resolve_issuer_sector("BAD_TICKER", "Technology")

        self.assertFalse(resolution["is_calculable"])
        self.assertIn("invalid ticker syntax", resolution["status"])

    def test_unknown_issuer_fails_closed_without_technology_default(self):
        resolution = app.resolve_issuer_sector("NOT_A_REAL_TICKER", "Technology")
        payload = app.climate_model_lab_payload(
            scope="issuer",
            ticker="NOT_A_REAL_TICKER",
            sector="Technology",
        )
        self.assertFalse(resolution["is_calculable"])
        self.assertIsNone(resolution["resolved_sector"])
        self.assertIsNone(payload["sector"])
        self.assertIsNone(payload["long_term"]["value_impact"])
        self.assertIsNone(payload["short_term"]["event_risk"])
        self.assertEqual(payload["short_term"]["tactical_overlay_bps"], 0)
        self.assertFalse(payload["decision_suitable"])

    def test_macro_and_direct_transition_deltas_reconcile_separately(self):
        result = app.scenario_repricing_for_scope(
            [self.energy],
            app.CLIMATE_SCENARIO_PATHS["current_policies"],
            app.CLIMATE_SCENARIO_PATHS["baseline"],
            2050,
        )
        by_component = {row["component"]: row["loss_delta"] for row in result["attribution"]}
        expected_macro = sum(by_component[key] for key in app.MACRO_DCF_COMPONENTS)
        expected_transition = sum(by_component[key] for key in app.TRANSITION_DCF_COMPONENTS)
        expected_physical = by_component["acute_physical"] + by_component["chronic_physical"]
        self.assertAlmostEqual(result["macro_loss_delta"], expected_macro, places=3)
        self.assertAlmostEqual(result["transition_loss_delta"], expected_transition, places=3)
        self.assertAlmostEqual(result["physical_loss_delta"], expected_physical, places=3)
        self.assertNotIn("supply_chain", app.TRANSITION_DCF_COMPONENTS)
        self.assertNotIn("country_gdp", app.TRANSITION_DCF_COMPONENTS)

    def test_largest_transition_driver_uses_only_direct_transition_channels(self):
        row = {
            "name": "MSFT",
            "ticker": "MSFT",
            "sector": "Technology",
            "weight": 1.0,
            "vulnerability": app.issuer_vulnerability_profile("MSFT", "Technology"),
            "valuation": app.valuation_assumptions("MSFT", "Technology"),
        }
        result = app.scenario_repricing_for_scope(
            [row],
            app.CLIMATE_SCENARIO_PATHS["current_policies"],
            app.CLIMATE_SCENARIO_PATHS["baseline"],
            2050,
        )
        driver = result["instruments"][0]["transition_driver"]
        self.assertIn(driver, app.TRANSITION_DCF_COMPONENTS)
        self.assertNotEqual(driver, "supply_chain")
        self.assertNotEqual(driver, "country_gdp")

    def test_transition_pass_through_never_exceeds_gross_carbon_and_energy_cost(self):
        for sector in app.SECTOR_TRANSITION_CHANNELS:
            for scenario in app.CLIMATE_SCENARIO_PATHS.values():
                channels = app.transition_cash_flow_channels(scenario, sector)
                gross = channels["carbon_cost"] + channels["energy_cost"]
                self.assertLessEqual(abs(channels["pass_through_offset"]), gross + 1e-12)
                self.assertLessEqual(channels["pass_through_offset"], 0.0)

    def test_higher_carbon_shock_monotonically_raises_direct_cost_before_pass_through(self):
        base = dict(app.CLIMATE_SCENARIO_PATHS["current_policies"])
        high = {**base, "carbon_cost_shock_2050": base["carbon_cost_shock_2050"] + 0.10}
        base_channels = app.transition_cash_flow_channels(base, "Energy")
        high_channels = app.transition_cash_flow_channels(high, "Energy")
        base_net = base_channels["carbon_cost"] + base_channels["energy_cost"] + base_channels["pass_through_offset"]
        high_net = high_channels["carbon_cost"] + high_channels["energy_cost"] + high_channels["pass_through_offset"]
        self.assertGreater(high_channels["carbon_cost"], base_channels["carbon_cost"])
        self.assertGreater(high_net, base_net)

    def test_issuer_without_verified_facilities_has_proxy_index_but_no_trade(self):
        signal = {
            "is_calculable": True,
            "source_mode": "NWS active test",
            "daily_pressure": 0.60,
            "allocation_pressure": 0.60,
            "category_counts": {"heat": 3, "flood": 2},
            "category_intensity": {"heat": 0.70, "flood": 0.40},
            "top_driver": "heat",
        }
        context = {
            "current_warming": 1.20,
            "disaster_10y_avg": 18.0,
            "source_mode": "validated official completed-year observations",
        }
        with patch.object(app, "load_daily_climate_signal", return_value=signal), patch.object(
            app, "climate_data_context", return_value=context
        ), patch.object(app, "load_facility_exposure_data", return_value={}):
            payload = app.climate_model_lab_payload(
                scope="issuer",
                ticker="MSFT",
                sector="Technology",
                target="current_policies",
                reference="baseline",
            )
        short_term = payload["short_term"]
        self.assertIsNone(short_term["event_risk"])
        self.assertGreater(short_term["research_event_index"], 0.0)
        self.assertEqual(short_term["tactical_overlay_bps"], 0)
        self.assertFalse(short_term["is_calculable"])
        self.assertIn("facility exposure", payload["decision_status"])

    def test_financial_issuer_is_mapped_correctly_and_fcff_is_blocked_for_decision_use(self):
        signal = {
            "is_calculable": True,
            "source_mode": "NWS active test",
            "daily_pressure": 0.40,
            "allocation_pressure": 0.40,
            "category_counts": {"storm": 1},
            "category_intensity": {"storm": 0.50},
            "top_driver": "storm",
        }
        context = {
            "current_warming": 1.20,
            "disaster_10y_avg": 18.0,
            "source_mode": "validated official completed-year observations",
        }
        with patch.object(app, "load_daily_climate_signal", return_value=signal), patch.object(
            app, "climate_data_context", return_value=context
        ), patch.object(app, "load_facility_exposure_data", return_value={}):
            payload = app.climate_model_lab_payload(
                scope="issuer",
                ticker="GS",
                sector="Technology",
                target="current_policies",
                reference="baseline",
            )
        instrument = payload["long_term"]["instruments"][0]
        valuation_row = next(row for row in payload["calculation_ledger"] if row["step"] == "Valuation")
        self.assertEqual(payload["sector"], "Financials")
        self.assertTrue(payload["sector_resolution"]["has_conflict"])
        self.assertEqual(instrument["sector"], "Financials")
        self.assertFalse(instrument["valuation"]["decision_suitable"])
        self.assertEqual(valuation_row["check"], "Blocked")
        self.assertIn(instrument["transition_driver"], app.TRANSITION_DCF_COMPONENTS)

    def test_governed_client_pipeline_does_not_claim_unloaded_official_calibration(self):
        self.assertNotIn("NGFS-style acute", app.HTML)
        self.assertNotIn("BEA-style demand", app.HTML)
        self.assertNotIn("Strategic + tactical", app.HTML)
        self.assertIn("NGFS", app.HTML)
        self.assertIn("Assumption case", app.HTML)

    def test_hash_verified_ngfs_release_reports_model_median_not_probability(self):
        csv_text = (
            "model,scenario,source_scenario_label,run_id,run_version,region,variable,unit,year,value\n"
            "M1,Current Policies,Current Policies,1,2,USA,Price|Carbon,US$2010/t CO2,2050,10\n"
            "M2,Current Policies,Current Policies,2,2,USA,Price|Carbon,US$2010/t CO2,2050,20\n"
            "M3,Current Policies,Current Policies,3,2,USA,Price|Carbon,US$2010/t CO2,2050,40\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            release_dir = Path(temp_dir) / "CFP-2026-003-RTEST"
            processed = release_dir / "processed" / "ngfs_5_1_transition_usa_to_2050.csv"
            processed.parent.mkdir(parents=True)
            processed.write_text(csv_text, encoding="utf-8")
            digest = app.hashlib.sha256(processed.read_bytes()).hexdigest()
            manifest = {
                "release_id": "CFP-2026-003-RTEST",
                "source_entries": [
                    {
                        "source_id": "SRC-NGFS-PHASE-5-1-TRANSITION",
                        "processed_path": str(processed),
                        "processed_sha256": digest,
                        "source_vintage": "5.1",
                        "source_release_date": "2026-03-20",
                        "source_url": "https://data.ene.iiasa.ac.at/ngfs/",
                        "region": "USA",
                        "variables": ["Price|Carbon"],
                        "models": ["M1", "M2", "M3"],
                        "scenarios": ["Current Policies"],
                    }
                ],
            }
            (release_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            release = app.latest_official_ngfs_transition(temp_dir)
        pathway = app.official_ngfs_transition_pathway("current_policies", 2050, release=release)
        self.assertTrue(release["is_loaded"])
        self.assertEqual(pathway["carbon_price_median"], 20.0)
        self.assertEqual(pathway["carbon_price_min"], 10.0)
        self.assertEqual(pathway["carbon_price_max"], 40.0)
        self.assertIn("not a probability interval", pathway["status"])

    def test_model_lab_discloses_treasury_scope_and_missing_quant_inputs(self):
        signal = {
            "is_calculable": False,
            "source_mode": "test unavailable",
            "daily_pressure": None,
            "allocation_pressure": None,
            "category_counts": {},
            "category_intensity": {},
            "top_driver": None,
        }
        context = {
            "current_warming": 1.20,
            "disaster_10y_avg": 18.0,
            "source_mode": "test context",
        }
        missing_ngfs = {
            "is_loaded": False,
            "release_id": None,
            "source_release": None,
            "source_release_date": None,
            "source_url": app.NGFS_SCENARIOS_URL,
            "region": None,
            "variables": [],
            "models": [],
            "scenarios": [],
            "rows": [],
            "physical_damage_status": "not evaluated",
        }
        missing_sec = {
            "is_loaded": False,
            "release_id": None,
            "start_period": None,
            "end_period": None,
            "quarter_count": 0,
            "fact_count": 0,
            "filing_count": 0,
            "tickers": [],
            "coverage_rows": [],
            "status": "official SEC financial history not loaded",
        }
        with patch.object(app, "load_daily_climate_signal", return_value=signal), patch.object(
            app, "climate_data_context", return_value=context
        ), patch.object(app, "load_facility_exposure_data", return_value={}), patch.object(
            app, "latest_official_ngfs_transition", return_value=missing_ngfs
        ), patch.object(
            app, "latest_official_sec_financial_history", return_value=missing_sec
        ):
            payload = app.climate_model_lab_payload(
                scope="issuer",
                ticker="AAPL",
                sector="Technology",
                target="current_policies",
                reference="baseline",
            )
        by_level = {row["level"]: row for row in payload["scope_resolution"]}
        self.assertIn("official NGFS pathway release not loaded", by_level["Scenario pathways"]["status"])
        self.assertIn("governed BEA calibration not loaded", by_level["Sector transmission"]["status"])
        self.assertIn("Missing or incomplete", by_level["Issuer evidence"]["status"])
        self.assertIn("Risk-free leg only", by_level["Valuation rate"]["output"])

    def test_duke_pilot_release_is_hash_verified_and_fail_closed_for_physical_loss(self):
        pilot = app.latest_governed_duke_pilot()
        self.assertTrue(pilot["is_loaded"])
        self.assertEqual(pilot["release_id"], "CFP-2026-003-R10-20260801T015000Z")
        self.assertEqual(pilot["parent_records"], 49)
        self.assertEqual(pilot["direct_emitter_matches"], 40)
        self.assertEqual(pilot["coordinate_matches"], 40)
        self.assertEqual(pilot["physical_financial_status"], "not calculable")
        self.assertEqual(pilot["fcff_bridge"]["filing_tie_out_status"].split(";")[0], "pass")
        self.assertEqual(pilot["carbon_sensitivity"]["net_carbon_cost_usd"], "")

    def test_release_sort_uses_numeric_ordinal(self):
        ids = ["CFP-2026-003-R9-20260801T014000Z", "CFP-2026-003-R10-20260801T015000Z"]
        self.assertEqual(max(ids, key=app.governed_release_sort_key), ids[1])


if __name__ == "__main__":
    unittest.main()
