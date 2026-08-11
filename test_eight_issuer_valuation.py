import unittest

import app


class EightIssuerValuationTests(unittest.TestCase):
    def test_r14_release_is_hash_verified_and_complete(self):
        release = app.latest_eight_issuer_valuation_inputs()
        self.assertTrue(release["is_loaded"])
        self.assertEqual(len(release["inputs"]), 8)
        self.assertEqual(len(release["assumptions"]), 24)

    def test_equal_scenario_has_zero_cash_flow_and_value_delta(self):
        value = app.climate_model_lab_payload(
            scope="issuer", target="current_policies", reference="current_policies",
            horizon=2050, sector="Utilities", ticker="DUK", assumption_case="base",
        )["prototype_valuation"]
        self.assertAlmostEqual(value["value_impact"], 0.0, places=12)
        self.assertAlmostEqual(value["attribution_residual"], 0.0, places=12)
        for channel in value["channels"]:
            self.assertAlmostEqual(channel["terminal_cash_flow_delta_usd"], 0.0, places=6)

    def test_three_channel_shapley_reconciles(self):
        value = app.climate_model_lab_payload(
            scope="issuer", target="net_zero_2050", reference="baseline",
            horizon=2050, sector="Energy", ticker="CVX", assumption_case="base",
        )["prototype_valuation"]
        self.assertTrue(value["is_calculable"])
        self.assertAlmostEqual(
            sum(row["value_contribution"] for row in value["channels"]),
            value["value_impact"], places=10,
        )
        self.assertAlmostEqual(value["attribution_residual"], 0.0, places=10)

    def test_assumption_cases_are_visible_and_monotonic_for_duke(self):
        impacts = []
        for case in ("low", "base", "high"):
            value = app.climate_model_lab_payload(
                scope="issuer", target="net_zero_2050", reference="baseline",
                horizon=2050, sector="Utilities", ticker="DUK", assumption_case=case,
            )["prototype_valuation"]
            self.assertEqual(value["model_assumptions"]["case"], case)
            impacts.append(value["value_impact"])
        self.assertGreaterEqual(impacts[0], impacts[1])
        self.assertGreaterEqual(impacts[1], impacts[2])

    def test_ui_is_compact_and_exposes_assumption_case(self):
        self.assertIn('id="modelAssumptionCase"', app.HTML)
        self.assertIn("Long-Term Climate Valuation", app.HTML)
        self.assertIn("Inputs, assumptions and calculation detail", app.HTML)
        self.assertIn("#regimeBadge,#sourceBadge,#timeBadge,#client-section,#cvor-section{display:none!important}", app.HTML)
        self.assertIn("Long-term scenario valuation prototype", app.HTML)
        self.assertIn("Eight issuers · source-backed inputs · prototype assumptions explicitly labelled", app.HTML)
        self.assertIn("Demo assumption", app.HTML)
        self.assertNotIn("Comparable evidence by risk channel", app.HTML)

    def test_repair_audit_exposes_annual_paths_and_ev_only_boundary(self):
        value = app.climate_model_lab_payload(
            scope="issuer", target="current_policies", reference="baseline",
            horizon=2050, sector="Utilities", ticker="DUK", assumption_case="base",
        )["prototype_valuation"]
        self.assertEqual(len(value["annual_calculation"]), 25)
        self.assertEqual(len(value["transition_audit"]), 25)
        self.assertFalse(value["equity_bridge"]["is_calculable"])
        self.assertIsNone(value["equity_bridge"]["per_share_value_impact"])
        self.assertIn(value["valuation_audit"]["ranking_status"], {"RANKABLE", "CAUTION", "EXCLUDE"})
        self.assertAlmostEqual(
            value["symmetric_value_difference"],
            2 * (value["target_enterprise_value_usd"] - value["reference_enterprise_value_usd"])
            / (abs(value["target_enterprise_value_usd"]) + abs(value["reference_enterprise_value_usd"])),
            places=12,
        )

    def test_transition_is_target_net_cost_less_reference_net_cost(self):
        value = app.climate_model_lab_payload(
            scope="issuer", target="current_policies", reference="delayed_transition",
            horizon=2050, sector="Utilities", ticker="DUK", assumption_case="base",
        )["prototype_valuation"]
        terminal = value["transition_audit"][-1]
        channel = next(row for row in value["channels"] if row["key"] == "transition")
        self.assertEqual(terminal["pass_through_application_count"], 1)
        self.assertAlmostEqual(
            terminal["target_net_cost_usd"] - terminal["reference_net_cost_usd"],
            terminal["net_transition_pressure_usd"], places=6,
        )
        self.assertAlmostEqual(terminal["net_transition_pressure_usd"], channel["terminal_cash_flow_delta_usd"], places=6)

    def test_every_assumption_is_explicitly_demo_only(self):
        value = app.climate_model_lab_payload(
            scope="issuer", target="current_policies", reference="baseline",
            horizon=2050, sector="Utilities", ticker="DUK", assumption_case="base",
        )["prototype_valuation"]
        assumptions = value["model_assumptions"]
        self.assertEqual(assumptions["assumption_classification"], "Prototype demonstration assumption - not issuer-observed")
        self.assertTrue(assumptions["field_classifications"])
        self.assertEqual(set(assumptions["field_classifications"].values()), {assumptions["assumption_classification"]})


if __name__ == "__main__":
    unittest.main()
