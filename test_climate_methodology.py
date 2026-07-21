import unittest

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


if __name__ == "__main__":
    unittest.main()
