import unittest

import app
from scripts import build_report_charts as charts


class ReportChartExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = charts.build_results()

    def test_export_covers_eight_issuers_five_pairs_and_three_cases(self):
        self.assertEqual(len(self.rows), 8 * 5 * 3)
        self.assertEqual({row["ticker"] for row in self.rows}, set(charts.ISSUERS))
        self.assertEqual(len({row["scenario_pair_key"] for row in self.rows}), 5)
        self.assertEqual({row["assumption_case"] for row in self.rows}, set(charts.CASES))

    def test_duke_export_matches_governed_application_payload(self):
        exported = next(
            row for row in self.rows
            if row["ticker"] == "DUK"
            and row["scenario_pair_key"] == "cp_vs_baseline"
            and row["assumption_case"] == "base"
        )
        governed = app.climate_model_lab_payload(
            scope="issuer", target="current_policies", reference="baseline",
            horizon=2050, sector="Utilities", ticker="DUK", assumption_case="base",
        )["prototype_valuation"]
        self.assertAlmostEqual(exported["value_impact_pct"], governed["value_impact"] * 100.0, places=10)

    def test_channel_attribution_reconciles_to_value_impact(self):
        for row in self.rows:
            if not row["is_calculable"]:
                continue
            total = (
                row["transition_value_contribution_pct"]
                + row["physical_value_contribution_pct"]
                + row["macro_supply_value_contribution_pct"]
            )
            self.assertAlmostEqual(total, row["value_impact_pct"], places=8)

    def test_missing_number_is_not_coerced_to_zero(self):
        self.assertIsNone(charts._number(None))
        self.assertIsNone(charts._number(""))
        self.assertEqual(charts._number(0), 0.0)

    def test_physical_confidence_distinguishes_proxy_from_facility_match(self):
        rows = {
            row["ticker"]: row for row in self.rows
            if row["scenario_pair_key"] == "cp_vs_baseline" and row["assumption_case"] == "base"
        }
        self.assertEqual(rows["AAPL"]["physical_data_confidence"], "Unverified")
        self.assertIsNone(rows["AAPL"]["facility_match_coverage_pct"])
        self.assertIn("Proxy", rows["AAPL"]["physical_evidence_type"])
        self.assertEqual(rows["DUK"]["physical_data_confidence"], "High")
        self.assertAlmostEqual(rows["DUK"]["facility_match_coverage_pct"], 48 / 49 * 100, places=10)

    def test_duke_terminal_fcff_bridge_reconciles(self):
        row = next(
            row for row in self.rows
            if row["ticker"] == "DUK"
            and row["scenario_pair_key"] == "cp_vs_baseline"
            and row["assumption_case"] == "base"
        )
        expected_target = row["reference_terminal_fcff_usd"] - (
            row["transition_terminal_cost_usd"]
            + row["physical_terminal_cost_usd"]
            + row["macro_supply_terminal_cost_usd"]
        )
        self.assertAlmostEqual(expected_target, row["target_terminal_fcff_usd"], places=5)

    def test_extreme_results_are_flagged_not_hidden(self):
        duke_nz = next(
            row for row in self.rows
            if row["ticker"] == "DUK"
            and row["scenario_pair_key"] == "nz_vs_baseline"
            and row["assumption_case"] == "base"
        )
        self.assertEqual(duke_nz["value_impact_pct"], -100.0)
        self.assertTrue(duke_nz["target_ev_floor_flag"])
        self.assertIn("zero-value floor", duke_nz["result_interpretation"])


if __name__ == "__main__":
    unittest.main()
