import unittest

import app


class EightIssuerClimateEvidenceTests(unittest.TestCase):
    def test_latest_release_is_hash_verified_and_complete(self):
        release = app.latest_eight_issuer_climate_evidence()
        self.assertTrue(release["is_loaded"])
        self.assertEqual(len(release["scope_rows"]), 8)
        self.assertEqual(len(release["ppe_rows"]), 8)
        self.assertEqual(len(release["physical_rows"]), 8)
        self.assertEqual(len(release["assumptions"]), 24)
        self.assertGreaterEqual(len(release["cie_rows"]), 30)

    def test_duke_uses_fema_eal_not_risk_score(self):
        value = app.climate_model_lab_payload(
            scope="issuer", target="current_policies", reference="baseline",
            horizon=2050, sector="Utilities", ticker="DUK", assumption_case="base",
        )["prototype_valuation"]
        observed = value["observed_inputs"]
        self.assertGreater(observed["net_ppe_usd"], 0)
        self.assertGreater(observed["fema_building_eal_rate"], 0)
        self.assertIn("FEMA", observed["fema_eal_source"])
        self.assertNotIn("score", observed["fema_eal_source"].lower())

    def test_transition_scope_legs_reconcile(self):
        value = app.climate_model_lab_payload(
            scope="issuer", target="net_zero_2050", reference="baseline",
            horizon=2050, sector="Technology", ticker="AAPL", assumption_case="base",
        )["prototype_valuation"]
        detail = value["terminal_component_detail"]
        transition = next(row for row in value["channels"] if row["key"] == "transition")
        self.assertGreater(detail["scope2"], 0)
        self.assertGreater(detail["scope3"], 0)
        self.assertAlmostEqual(
            detail["scope1"] + detail["scope2"] + detail["scope3"],
            transition["terminal_cash_flow_delta_usd"], places=5,
        )

    def test_physical_acute_and_chronic_reconcile(self):
        value = app.climate_model_lab_payload(
            scope="issuer", target="current_policies", reference="baseline",
            horizon=2050, sector="Utilities", ticker="DUK", assumption_case="base",
        )["prototype_valuation"]
        detail = value["terminal_component_detail"]
        physical = next(row for row in value["channels"] if row["key"] == "physical")
        self.assertGreater(detail["acute"], 0)
        self.assertGreater(detail["chronic"], 0)
        self.assertAlmostEqual(
            detail["acute"] + detail["chronic"],
            physical["terminal_cash_flow_delta_usd"], places=5,
        )

    def test_equal_scenario_conserves_all_five_components(self):
        value = app.climate_model_lab_payload(
            scope="issuer", target="below_2c", reference="below_2c",
            horizon=2050, sector="Industrials", ticker="DE", assumption_case="high",
        )["prototype_valuation"]
        for amount in value["terminal_component_detail"].values():
            self.assertAlmostEqual(amount, 0.0, places=6)
        self.assertAlmostEqual(value["value_impact"], 0.0, places=12)

    def test_macro_dependency_uses_sec_capex_to_cfo(self):
        values = {}
        for ticker, sector in (("AAPL", "Technology"), ("DUK", "Utilities")):
            value = app.climate_model_lab_payload(
                scope="issuer", target="current_policies", reference="baseline",
                horizon=2050, sector=sector, ticker=ticker, assumption_case="base",
            )["prototype_valuation"]
            observed = value["observed_inputs"]
            assumed = value["model_assumptions"]
            expected = min(2.0, max(0.5, 0.5 + observed["capex_to_operating_cash_flow"]))
            self.assertAlmostEqual(assumed["macro_dependency_scale"], expected, places=12)
            values[ticker] = next(row["terminal_cash_flow_delta_rate"] for row in value["channels"] if row["key"] == "macro_supply")
        self.assertNotAlmostEqual(values["AAPL"], values["DUK"], places=6)


if __name__ == "__main__":
    unittest.main()
