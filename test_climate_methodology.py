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

    def test_value_attribution_reconciles_to_total(self):
        result = app.scenario_repricing_for_scope(
            [self.energy],
            app.CLIMATE_SCENARIO_PATHS["current_policies"],
            app.CLIMATE_SCENARIO_PATHS["baseline"],
            2050,
        )
        contribution = sum(row["value_contribution"] for row in result["attribution"])
        self.assertAlmostEqual(contribution, result["value_impact"], places=3)

    def test_scenario_matrix_does_not_claim_probabilities(self):
        allocation = [
            {"year": 2026, "ticker": ticker, "climate_weight": 1 / len(app.SECTOR_ETFS)}
            for ticker in app.SECTOR_ETFS
        ]
        rows, summary = app.climate_scenario_matrix(allocation)
        self.assertTrue(rows)
        self.assertTrue(all("probability" not in row for row in rows))
        self.assertIn("No occurrence probabilities", summary["scenario_probability_method"])

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
        self.assertEqual(len(budget["checks"]), 4)

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
        window = app.summarize_daily_recommendation_window(rows, 15, "3 months")
        self.assertGreaterEqual(
            window["summary"]["gross_recommended_total_return"],
            window["summary"]["recommended_total_return"],
        )
        self.assertIn("information_ratio", window["summary"])


if __name__ == "__main__":
    unittest.main()
