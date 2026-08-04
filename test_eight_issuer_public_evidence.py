import unittest

import app


TICKERS = ("AAPL", "CAT", "CVX", "DE", "DUK", "MSFT", "NEE", "XOM")


class EightIssuerPublicEvidenceTests(unittest.TestCase):
    def test_release_is_hash_verified_and_covers_eight_issuers(self):
        release = app.latest_eight_issuer_public_evidence()
        self.assertTrue(release["is_loaded"])
        self.assertEqual({row["ticker"] for row in release["scope1_rows"]}, set(TICKERS))
        self.assertTrue(all(float(row["scope1_tco2e"]) > 0 for row in release["scope1_rows"]))
        self.assertTrue(all(row["source_url"].startswith("https://") for row in release["scope1_rows"]))

    def test_public_issuer_headlines_use_disclosed_assumption_valuation(self):
        for ticker in TICKERS:
            payload = app.climate_model_lab_payload(
                scope="issuer", target="current_policies", reference="baseline",
                horizon=2050, sector="Technology", ticker=ticker,
            )
            evidence = payload["issuer_public_evidence"]
            self.assertTrue(evidence["is_loaded"])
            self.assertIsNotNone(payload["long_term"]["value_impact"])
            self.assertTrue(payload["prototype_valuation"]["is_calculable"])
            self.assertEqual(payload["prototype_valuation"]["assumption_case"], "base")
            self.assertIn("model_assumptions", payload["prototype_valuation"])
            self.assertIsNone(evidence["transition"]["net_transition_cost_usd"])
            self.assertIsNone(evidence["physical"]["financial_loss_usd"])

    def test_transition_formula_reconciles_and_equal_scenario_is_zero(self):
        current = app.climate_model_lab_payload(
            scope="issuer", target="current_policies", reference="baseline",
            horizon=2050, sector="Utilities", ticker="DUK",
        )["issuer_public_evidence"]["transition"]
        expected = current["scope1_tco2e"] * current["price_delta_usd2010_per_tco2"]
        self.assertAlmostEqual(current["gross_sensitivity_usd"], expected, places=6)

        equal = app.climate_model_lab_payload(
            scope="issuer", target="current_policies", reference="current_policies",
            horizon=2050, sector="Utilities", ticker="DUK",
        )["issuer_public_evidence"]["transition"]
        self.assertEqual(equal["price_delta_usd2010_per_tco2"], 0)
        self.assertEqual(equal["gross_sensitivity_usd"], 0)

    def test_physical_screen_never_becomes_financial_loss(self):
        release = app.latest_eight_issuer_public_evidence()
        for row in release["physical_rows"]:
            self.assertEqual(row["financial_loss_status"], "not calculable")
            self.assertIn("not", row["allowed_use"].lower())
        by_ticker = {row["ticker"]: row for row in release["physical_rows"]}
        self.assertEqual(int(by_ticker["DUK"]["epa_parent_facilities"]), 49)
        self.assertGreater(int(by_ticker["DUK"]["fema_county_matches"]), 0)
        self.assertEqual(float(by_ticker["AAPL"]["disclosed_value"]), 70.0)
        self.assertEqual(float(by_ticker["MSFT"]["disclosed_value"]), 46.0)

    def test_negative_fcf_does_not_create_misleading_ratio(self):
        transition = app.climate_model_lab_payload(
            scope="issuer", target="current_policies", reference="baseline",
            horizon=2050, sector="Utilities", ticker="NEE",
        )["issuer_public_evidence"]["transition"]
        self.assertLess(transition["cash_flow_baseline_usd"], 0)
        self.assertIsNone(transition["gross_sensitivity_to_cash_flow"])


if __name__ == "__main__":
    unittest.main()
