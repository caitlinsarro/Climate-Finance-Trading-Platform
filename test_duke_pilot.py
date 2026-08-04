import unittest

from scripts.build_duke_pilot import (
    calculate_fcff_candidate,
    carbon_price_sensitivity,
    join_parent_emissions,
    physical_financial_gate,
)


class DukePilotTests(unittest.TestCase):
    def test_fcff_candidate_reconciles(self):
        result = calculate_fcff_candidate(12_330, 14_024, 3_634, 642, 5_712)
        self.assertAlmostEqual(result["effective_tax_rate"], 642 / 5712)
        self.assertAlmostEqual(result["reconciliation_residual"], 0)
        self.assertEqual(result["status"], "candidate; filing tie-out required")

    def test_carbon_sensitivity_is_zero_for_equal_scenarios_and_monotonic(self):
        equal = carbon_price_sensitivity(100, 20, 20)
        higher = carbon_price_sensitivity(100, 21, 20)
        self.assertEqual(equal["gross_static_exposure_usd"], 0)
        self.assertGreater(higher["gross_static_exposure_usd"], equal["gross_static_exposure_usd"])

    def test_parent_emissions_join_uses_id_and_ownership(self):
        parent = [{
            "GHGRP FACILITY ID": 10, "FACILITY NAME": "Parent name",
            "PARENT COMPANY NAME": "DUKE ENERGY CORP",
            "PARENT CO. PERCENT OWNERSHIP": 62.5, "FACILITY STATE": "NC",
            "FACILITY COUNTY": "TEST COUNTY",
        }]
        direct = [{
            "Facility Id": 10, "Facility Name": "EPA name", "State": "NC", "County": "Test",
            "Latitude": 35, "Longitude": -80, "Total reported direct emissions": 1000,
            "CO2 emissions (non-biogenic)": 900,
        }]
        row = join_parent_emissions(parent, direct)[0]
        self.assertEqual(row["ownership_adjusted_direct_tco2e"], 625)
        self.assertEqual(row["ownership_adjusted_nonbiogenic_co2_tonnes"], 562.5)

    def test_missing_physical_financial_inputs_fail_closed(self):
        result = physical_financial_gate()
        self.assertEqual(result["status"], "not calculable")
        self.assertIn("exposed_asset_value", result["missing"])
        self.assertIn("asset_type_damage_function", result["missing"])


if __name__ == "__main__":
    unittest.main()
