# Jennison Climate-Risk Research Platform

This repository is a research prototype for transparent climate scenario analysis. It separates physical risk, macro and supply-chain transmission, and direct transition channels so an analyst can see what drives a result.

The model is **not promoted for portfolio construction, security recommendations, tactical trading, audited valuation, or regulatory Climate VaR**. Engineering acceptance is separate from model and investment approval.

## Client demo entry point

Jennison users should use only the running application and the two retained
client references:

- `output/pdf/climate_model_calculation_workflow.pdf` for the calculation flow;
- `output/pdf/eight_issuer_climate_scenario_valuation_methodology.pdf` for the
  bounded eight-issuer methodology.

The `scripts/`, `test_*.py`, `.specify/`, and `specs/` paths are maintainer
assets. They are retained for reproducibility and model governance, not as
client workflows or supported Jennison tools.

## Current governed scope

The client-facing application currently supports:

- target-versus-reference scenario research;
- eight issuer demonstrations for AAPL, CAT, CVX, DE, DUK, MSFT, NEE, and XOM;
- separate physical, macro/supply-chain, and direct-transition attribution;
- annual FCFF and common-rate target/reference DCF with exact attribution;
- explicit public-data versus Low/Base/High assumption labels;
- data lineage and calculation-reconciliation evidence in a collapsed disclosure.

The former optimizer, climate buy/sell backtest, tactical basis-point overlay, and recommendation views remain isolated as engineering sandbox code. They are hidden from the governed interface and are not calculated on normal page load.

## What the numbers mean today

Long-term results are **conditional research sensitivities**. They answer: “If the selected target pathway replaced the reference pathway, how would the current project calibration change the modeled cash-flow proxy?” They are not event probabilities, forecasts, audited issuer values, or investment recommendations.

Short-term NWS output is not part of the client demonstration. The prototype is
limited to long-horizon scenario-conditioned valuation.

## Quantitative structure

### Direct transition risk

The intended issuer-level structure is:

```text
carbon cost
+ energy cost
+ incremental transition CapEx
+ climate-policy/product demand effect
- demonstrated cost pass-through
= annual transition cash-flow effect
```

The current prototype separates reported Scope 1 direct emissions, Scope 2
purchased-energy exposure, and Scope 3 value-chain exposure. It applies official
NGFS carbon-price paths and visible Low/Base/High incidence, pass-through, and
emissions-decline assumptions. Scope 3 is not treated as a direct issuer tax.

Atmospheric CO2 concentration is climate-state context only. It is not used as a carbon price or direct transition-risk score.

### Physical risk

The intended facility-level structure is:

```text
hazard intensity
x verified location exposure
x hazard-specific damage or vulnerability function
x asset or earnings value at risk
x (1 - evidenced resilience)
+ business interruption
= physical cash-flow effect
```

The current prototype uses SEC net PP&E and joins EPA parent facilities to FEMA
county building expected annual loss rates. Chronic physical stress uses the
official CIE USA heat-productivity pathway. Covered asset share,
insurance/adaptation, acute scenario scaling, and productivity-to-FCFF
conversion remain explicit assumptions; the output is not an observed loss.

### Valuation

The intended valuation is an annual FCFF bridge under both target and reference pathways, discounted under a governed assumption grid. A single market rate is insufficient for an issuer WACC.

The current governed calculation uses SEC FCFF inputs, five-year monthly market
beta, the dated U.S. Treasury yield, public debt/market capitalization, and a
visible ERP/terminal-growth assumption grid. It reports a modeled enterprise-
value sensitivity, not a decision-grade price target.

## Official data and provenance

Authoritative source ingestion preserves raw bytes, processed output, source URL, retrieval time, release ID, and SHA-256 hashes under `data/releases/`.

Currently loaded for feature `CFP-2026-003`:

- U.S. Treasury daily par yields, including the observed 10-year yield, release `CFP-2026-003-R1-20260731T2318Z`.
- Official NGFS Phase 5.1 USA transition pathways, release `CFP-2026-003-R5-20260731T2351Z`: 882 observations across seven scenarios, three models, six transition variables, and 2020-2050 five-year horizons. The model range is not a probability interval. Phase 5 physical-damage variables affected by the retracted Kotz et al. paper are excluded.
- SEC Financial Statement Data Sets from 2009 Q1 through 2026 Q1: all 69 official quarterly ZIP archives are preserved locally in raw release `CFP-2026-003-R6-20260801T003356Z` (about 5.2 GB). Hash-verified processed release `CFP-2026-003-R8-20260801T005207Z` contains 4,078 candidate facts and 139 annual filings for AAPL, CAT, CVX, DE, DUK, MSFT, NEE, and XOM. This is a financial-history input, not a completed FCFF tie-out.
- DUK governed pilot release `CFP-2026-003-R10-20260801T015000Z`: official Duke 2025 10-K, EPA GHGRP/eGRID, and FEMA NRI evidence; 49 EPA parent records, 40 direct-emitter and coordinate matches, 72.00 Mt ownership-adjusted matched non-biogenic CO2, a manually tied $1.53bn 2025 FCFF bridge, and a $155.4m gross static NGFS carbon-price illustration. The illustration is not net cost or a forecast. Issuer physical loss and DCF remain Not calculable.
- Eight-issuer prototype release `CFP-2026-003-R11-20260801T023000Z`: consistent 2025 FCF screen for AAPL, CAT, CVX, DE, DUK, MSFT, NEE, and XOM. The client Model Lab uses clickable issuer cards and follows transition, physical, and macro/supply effects through FCF and a simple continuing-value bridge. Client-facing NWS short-term output is removed from this demo flow.
- The Model Lab decision view now shows each issuer's physical, direct-transition, and macro/supply-chain rates and currency effects on one FCF/FCFF baseline, reconciles them to scenario cash flow and continuing-value sensitivity, and translates the result into peer comparison, risk-budget, and issuer-engagement uses without generating a trade.
- R17 public-data extension `CFP-2026-003-R17-20260804T234500Z`: issuer Scope
  1/2/3, SEC net PP&E, expanded FEMA building EAL rates, CIE USA
  heat-productivity paths, and 24 Low/Base/High assumption rows are retained and
  hash verified. FEMA scores no longer create issuer loss rates.

Available governed context from earlier releases includes NWS alerts, NOAA Storm Events, and the issuer-sector master. These datasets do not by themselves establish issuer facility exposure or climate loss.

EPA GHGRP, FEMA EAL, SEC, NGFS, and CIE inputs are integrated for the bounded
eight-issuer prototype. EIA capacity weights, BEA input-output company mapping,
issuer supplier/customer economics, insurance, adaptation, and licensed vendor
benchmarks remain future work.

SEC financial data require no API key. The completed downloader preserves each raw ZIP locally, supports resume and source-release reprocessing, resolves controlled historical registrant CIK aliases, and extracts governed candidate-issuer facts. The contact email used for SEC fair-access compliance is not stored. The model still fails closed on issuer FCFF until filing and accounting tie-outs are completed.

See [docs/api-access.md](docs/api-access.md) for access rules and local credentials. Secrets must never be committed, logged, written to workbooks, or included in release manifests.

## Governed workflow

All model changes follow:

```text
Constitution -> Replanning -> Specification -> Implementation
-> Validation -> Decision -> Roadmap update
```

The active overhaul is `CFP-2026-003`. Its documents are under `specs/CFP-2026-003/`. Validation must distinguish mathematical reconciliation from empirical validity. Passing unit tests does not promote a model.

## Run locally

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

Open `http://127.0.0.1:8865`.

## Maintainer-only data and validation assets

Data-ingestion scripts, immutable-release builders, and automated tests are not
required to run the client demo. Maintainers should consult
`docs/api-access.md`, the active `specs/CFP-2026-003/` records, and the test
modules before rebuilding data or changing calculations. These assets preserve
reproducibility; they do not establish forecast accuracy, damage-function
validity, model promotion, or investment usefulness.
