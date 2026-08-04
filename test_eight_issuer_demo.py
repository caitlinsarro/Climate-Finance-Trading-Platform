import unittest

from scripts.build_eight_issuer_demo import build_rows


class EightIssuerDemoTests(unittest.TestCase):
    def test_negative_fcf_is_not_clipped(self):
        sec = []
        for ticker in ("AAPL", "CAT", "CVX", "DE", "DUK", "MSFT", "NEE", "XOM"):
            adsh = ticker + "-filing"
            for tag, value in (
                ("NetCashProvidedByUsedInOperatingActivities", 100),
                ("PaymentsToAcquirePropertyPlantAndEquipment", 120),
            ):
                sec.append({
                    "ticker": ticker, "fiscal_year": "2025", "adsh": adsh,
                    "filed": "20260201", "report_period": "20251231", "date": "20251231",
                    "tag": tag, "unit": "USD", "value": str(value), "source_url": "sec",
                })
        candidates = [{"ticker": ticker, "parent_records": 1, "direct_emitter_matches": 1} for ticker in ("AAPL", "CAT", "CVX", "DE", "DUK", "MSFT", "NEE", "XOM")]
        rows = build_rows(sec, candidates, {"fcff": "10"})
        by_ticker = {row["ticker"]: row for row in rows}
        self.assertEqual(by_ticker["AAPL"]["free_cash_flow_usd"], -20)
        self.assertEqual(by_ticker["DUK"]["duke_fcff_usd"], "10")


if __name__ == "__main__":
    unittest.main()
