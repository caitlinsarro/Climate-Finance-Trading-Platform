# CFP-2026-003 — Implementation Plan

1. Remove misleading client-facing output semantics and isolate unvalidated
   optimizer/backtest modules.
2. Extend the governed workbook and immutable release format for NGFS, SEC,
   Treasury, BEA, EPA, EIA, FEMA, NOAA, and NASA inputs.
3. Ingest official scenario and financial data with point-in-time rules.
4. Select a data-fit non-financial issuer pilot.
5. Implement and manually tie out transition cash-flow channels.
6. Build facility ownership/geolocation and physical-loss pilot channels.
7. Rebuild annual FCFF and DCF with WACC/terminal-growth sensitivity.
8. Add uncertainty, coverage, double-counting, and external-validation reports.
9. Run automated, data, mathematical, visual, and independent quant validation.
10. Record decision and update the roadmap; do not promote automatically.

## Increment status — 2026-07-31

- Completed: official NGFS 5.1 transition ingestion, immutable provenance,
  scenario normalization, model-range summary, and governed UI disclosure.
- Completed: resumable SEC Financial Statement Data Set ingestion for every
  quarter from 2009 Q1 through 2026 Q1 (69 archives), controlled historical CIK
  resolution, processed hashes, and issuer coverage screening.
- Next: select the pilot using financial plus emissions/facility data fitness,
  manually tie the selected filing lines to a normalized FCFF baseline, and tie
  the first currency-unit transition channel to that baseline.
- Still pending: verified emissions/policy coverage, facilities, damage
  functions, issuer WACC grid, external benchmark, and independent quant review.

## Increment 7 plan — compact data-first issuer view

1. Audit every client-visible issuer metric and classify it as data-derived,
   proxy, or not calculable.
2. Add a governed issuer-evidence payload that exposes calculations and evidence
   gates without promoting sector coefficients to issuer outputs.
3. Replace the verbose issuer risk/valuation story with three compact evidence
   panels and one calculation bridge in the established visual language.
4. Keep sector stress available only as a collapsed, clearly separated context
   view; remove it from issuer cash-flow and valuation arithmetic.
5. Add tests for DUK reconciliation, missing-data fail-closed behavior, forbidden
   manual-factor headline output, and concise UI semantics.
6. Validate the local portal in the browser, record screenshots and test output,
   then update the decision record and roadmap without promoting the model.

## Increment 7 amended execution — eight public-data issuers

1. Build a versioned evidence table for reported Scope 1 emissions and public
   operational-exposure disclosures for all eight demo issuers.
2. Calculate comparable gross NGFS carbon-price sensitivity against each
   issuer's SEC-derived cash-flow baseline; keep net transition cost separate.
3. Join EPA facility ownership to FEMA hazard context and EIA operational
   weights where available; otherwise show a coverage-qualified exposure screen.
4. Replace macro/supply betas with SEC financial dependency and BEA
   input-output evidence; block the scenario loss when the official shock join
   is incomplete.
5. Rebuild the client view around three concise evidence panels and remove all
   issuer headlines manufactured by multiplying FCF by project constants.
6. Run provenance, formula, monotonicity, equal-scenario, missing-data,
   reconciliation, API, and browser-layout tests.
7. Record validation, an Accepted/Iterate/Rejected decision, and the roadmap
   status. Engineering acceptance remains separate from model promotion.

## Increment 8 plan — complete the prototype valuation

1. Build a governed R14 valuation-input release from R13 evidence, SEC facts,
   dated market capitalization, five-year monthly issuer/SPY returns, and the
   official Treasury leg.
2. Implement annual transition, physical, and macro/supply target-reference
   cash-flow paths with explicit Low/Base/High assumptions.
3. Discount reference and scenario FCFF with a common WACC and reconcile value
   attribution by channel.
4. Replace the verbose evidence screen with a compact Jennison-oriented
   valuation view and collapsed methodology/assumption detail.
5. Run unit, regression, reconciliation, and browser-layout validation before
   recording the decision and roadmap update.
## Increment 9 implementation plan

1. Remove default-view sections that duplicate model status and limitations.
2. Compress issuer selectors and result copy without removing calculation data.
3. Replace decorative cards with flat report-style rows and restrained rules.
4. Verify AAPL and DUK in the local browser and rerun the full test suite.

## Increment 10 implementation plan

1. Retain official issuer emissions disclosures, SEC company facts, expanded
   FEMA county expected-loss-rate fields, EIA operational weights where usable,
   and NGFS/Climate Impact Explorer physical pathways in an immutable R15
   release with hashes and as-of dates.
2. Build comparable eight-issuer Scope 1/2/3 and physical-exposure tables,
   recording unavailable categories instead of silently substituting values.
3. Replace the Scope-1-only transition leg with separated direct,
   purchased-energy, and value-chain calculations and case-specific incidence
   assumptions.
4. Replace FEMA-score loss conversion with facility-weighted FEMA expected
   annual loss and add a separately attributed chronic heat/productivity leg.
5. Reconcile the enhanced annual channel amounts through scenario FCFF and the
   existing DCF, then expose concise company inputs and formulas in the portal.
6. Run data, unit, dimensional, conservation, monotonicity, regression, API,
   and browser-layout tests for AAPL and DUK plus the eight-issuer matrix.
7. Write validation evidence, record an Accepted/Iterate/Rejected engineering
   decision, and update the roadmap without implying production model approval.

## Increment 11 implementation plan

1. Add a Python report-export script that calls the governed issuer valuation
   payload for the eight demo issuers, five scenario comparisons, and
   Low/Base/High cases.
2. Write tidy issuer-scenario and issuer-input CSV files with model release,
   horizon, scenario, assumption, source, and calculability fields.
3. Generate report-ready PNG figures for value impact, channel attribution,
   scenario heatmap, uncertainty range, emissions, and physical exposure.
4. Add automated tests for row counts, DUK reconciliation, equal-scenario
   conservation, missing-value behavior, and figure creation.
5. Record validation evidence and update the decision and roadmap while
   preserving the research-only promotion boundary.

## Increment 12 implementation plan

1. Extend the governed report export with result-boundary, facility-coverage,
   proxy and common-assumption diagnostics without changing R17 valuation logic.
2. Correct the DUK chart bridge to the 2050 reference/target terminal FCFF and
   add reconciliation tests.
3. Rebuild the chart pack around cross-scenario value, assumption range,
   channel mix, physical confidence and extreme-case diagnostics.
4. Build a formatted Excel workbook with formula-driven summaries and checks
   using the two governed CSV exports as source sheets.
5. Render every workbook sheet and revised figure, resolve formula/layout
   defects, run the full regression suite and record evidence.
6. Only after the charts and workbook are accepted, use those final assets in
   the client prototype presentation.

## Increment 13 implementation plan

1. Add explicit source-status and prototype-assumption classifications to the
   issuer valuation payload without replacing observed values.
2. Refactor the annual transition calculation to retain target and reference
   gross/net costs by scope and prove pass-through is applied once.
3. Return the annual FCFF/discount audit trail and terminal-value bridge.
4. Add floor, unapplied-cost, symmetric-EV, denominator and physical-proxy
   diagnostics plus an EV-to-equity not-calculable gate.
5. Update the compact client disclosure to show the calculation boundary and
   assumption labels without adding a verbose methodology portal.
6. Regenerate report exports/workbook inputs, add regression tests and run the
   full suite, API tie-outs and local browser visual verification.
7. Record validation, engineering decision and roadmap state separately from
   model promotion.
