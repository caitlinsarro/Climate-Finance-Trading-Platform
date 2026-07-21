import unittest
from unittest.mock import patch

import app


class ClimateMethodologyTests(unittest.TestCase):
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
            for key in app.TRANSITION_DCF_COMPONENTS
            if key != "macro_transition"
        )
        self.assertAlmostEqual(channel_sum, components["micro_transition"], places=12)
        self.assertGreater(components["carbon_cost"], 0.0)
        self.assertGreater(components["transition_capex"], 0.0)
        self.assertLess(components["pass_through_offset"], 0.0)

    def test_transition_pressure_has_a_traceable_sector_cash_flow_driver(self):
        energy = app.structural_transition_pressure("Energy")
        technology = app.structural_transition_pressure("Technology")
        self.assertGreater(energy["risk"], technology["risk"])
        self.assertGreater(energy["demand_shift"], 0.0)
        self.assertLess(technology["demand_shift"], 0.0)
        self.assertIn("issuer NGFS/EIA/EPA/SEC data not loaded", energy["status"])

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
        self.assertEqual(first["quality"], "Sector median fallback")

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
        self.assertEqual(len(budget["checks"]), 5)
        self.assertEqual(budget["effective_cap_breaches"], 0)
        self.assertTrue(all("cvor_proxy" not in row for row in result["rows"]))
        self.assertTrue(all("scenario_tail_proxy" in row for row in result["rows"]))

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


if __name__ == "__main__":
    unittest.main()
