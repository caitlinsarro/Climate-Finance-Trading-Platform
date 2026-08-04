# CFP-2026-002 — Verified Climate-Risk Data Foundation

## Problem

The platform currently has insufficient verified issuer-level data to support
production-grade physical- and transition-risk scores. Existing project
calibrations are useful for research sensitivity but cannot substitute for
observed emissions, energy use, facilities, financial exposures, or versioned
scenario data.

## Intended users

- model developers importing climate-risk inputs;
- validators reviewing sources, units, and transformations;
- investment stakeholders interpreting data coverage and limitations;
- maintainers updating source vintages.

## Scope

- Remediate false or ambiguous provenance labels.
- Collect a controlled first release of authoritative public climate,
  financial, scenario, hazard, and economic data.
- Create an auditable Excel review workbook.
- Export accepted machine-readable snapshots for the application.
- Add fail-closed input contracts and data-quality tests.

## Non-goals

- Claim complete issuer facility or Scope 3 coverage.
- Infer missing observations from an AI system or unaudited web source.
- Treat NWS alerts as probabilities or observed issuer losses.
- Treat NGFS scenarios as forecasts.
- Promote the climate-risk model to production.
- Create a combined score when mandatory channel data are incomplete.

## Data contract

Every numerical record must include:

- `record_id`;
- `entity_id`, geography, sector, or scenario identifier as applicable;
- `metric_id` and definition;
- numeric `value`;
- `unit`;
- `currency` and price basis where applicable;
- observation/effective period;
- publication/release time;
- retrieval time;
- source name and direct URL;
- source version or filing accession;
- source class;
- transformation identifier;
- data-quality status;
- allowed use;
- rejection or limitation reason.

Raw records must be immutable within a release. Corrections create a new
release or an explicitly versioned correction record.

## Excel workbook requirements

1. Raw and normalized data must be stored on separate sheets.
2. Each data column must contain one type and unit.
3. Source URLs must be stored in dedicated source fields.
4. Editable assumptions must be visually distinct from imported values and
   formulas.
5. Derived values must use auditable formulas or a documented transformation
   identifier.
6. Quality checks must expose actual, expected, difference, tolerance, status,
   and remediation location.
7. Failed and rejected records must remain visible.
8. The workbook must contain no formula errors.
9. The workbook must record its release ID, build time, source vintages, file
   hashes, and application-compatibility status.

## Physical-risk computability rules

### Exposure indicator

An issuer exposure indicator may be produced only when the relevant geography
or facility mapping is verified and the hazard dataset has compatible spatial
and temporal resolution.

### Financial physical-loss sensitivity

A financial loss sensitivity additionally requires:

- a reconciled exposed value or revenue base;
- a hazard intensity with stated unit and scenario;
- an externally supported vulnerability or damage relationship;
- explicit resilience/recovery treatment;
- currency and price-year conversion;
- uncertainty or sensitivity bounds.

If any mandatory element is missing, the output is `Not calculable`. A sector
fallback may be shown separately as a research indicator but not substituted
into an issuer loss.

## Transition-risk computability rules

### Carbon-cost channel

```text
gross carbon cost
  = attributable emissions (tCO2e)
    × scenario carbon-price change (currency/tCO2e)
```

The reporting scope, emissions boundary, currency, price year, jurisdiction,
free allocation, hedging, and pass-through must be explicit.

### Energy-cost channel

```text
energy cost change
  = energy consumption by carrier
    × scenario energy-price change by carrier
```

Issuer energy consumption must not be silently replaced with a sector
intensity.

### Demand and investment channels

Demand effects require an exposed revenue base, scenario demand path, and
evidence-supported elasticity. Transition CapEx requires an explicit investment
schedule. Pass-through must be bounded and must not exceed eligible gross
costs without a documented economic reason.

Missing channels remain missing; they are not converted to zero.

## Source and licensing controls

- Only direct authoritative downloads or APIs may populate official raw tabs.
- Access terms and redistribution restrictions must be recorded before data is
  committed.
- API keys and credentials must never be stored in the workbook or repository.
- NGFS release/version and affected Phase V physical variables must be flagged.
- SEC requests must use an appropriate user agent and respect published access
  guidance.

## Acceptance criteria

1. Existing fallback values cannot be labeled official.
2. No hard-coded future observation is consumed as observed data.
3. The workbook passes formula, schema, source, unit, date, duplicate, and
   completeness checks.
4. Representative records tie to the direct source.
5. Accepted normalized records trace to immutable raw records.
6. Application snapshots contain release IDs and field-level source status.
7. Missing mandatory inputs produce `Not calculable`.
8. Unitless indicators are never exposed as probabilities or financial losses.
9. Existing methodology regression tests continue to pass.
10. Validation and decision documents record remaining coverage gaps.
11. A valid NWS payload remains usable when long-run climate inputs are not
    calculable.
12. A successful NWS observation with no matched hazards is distinguishable
    from an unavailable NWS observation.
13. Unavailable live hazard data produce `Not calculable`, zero tactical
    overlay, and no tactical trade recommendation.
14. Short-term event risk cannot be labeled as an observed `0.00%` unless the
    NWS request completed successfully.
15. GS resolves to Financials and MSFT resolves to Technology from a controlled
    application crosswalk; conflicting UI sectors are overridden and disclosed.
16. Unknown issuer tickers do not default to Technology and produce `Not
    calculable`.
17. Direct transition delta excludes country-GDP and supply-chain macro
    transmission; total valuation includes every physical, macro, and direct
    transition component exactly once.
18. The transition driver is selected only from direct transition channels and
    is labeled as a calibrated research driver.
19. Unitless NWS issuer indicators are displayed as index points rather than
    probabilities, losses, or returns.
20. Missing issuer facility mapping suppresses issuer event risk and tactical
    trading while permitting a separately labeled sector research proxy.
21. Financial-institution FCFF/WACC outputs carry a visible applicability
    blocker and cannot be represented as decision-suitable valuation.
22. Representative transition and physical tests cover identity,
    reconciliation, bounds, monotonicity, conservation, sign, and missing-data
    behavior.
23. A valid listed equity absent from the controlled crosswalk may use
    on-demand no-key market metadata only when quote type is `EQUITY` and its
    sector maps to a supported canonical sector.
24. Dynamic mappings disclose issuer name, exchange, industry, source class,
    and retrieval date; a conflicting UI sector is overridden and disclosed.
25. ETFs, funds, invalid tickers, unavailable metadata, and unsupported sectors
    remain `Not calculable` rather than inheriting Technology or the UI sector.
26. Product copy describes coverage as on-demand and resolvable, never as
    complete coverage of every global listed company.
27. Issuer beta is calculated from date-aligned adjusted issuer and benchmark
    returns obtained through `yfinance`, with benchmark, window, frequency,
    observation count, first/last date, and retrieval time disclosed.
28. Issuer market-value debt weight uses a Yahoo Finance-distributed market
    capitalization and the latest compatible reported total debt; market and
    statement dates and source classes remain distinct.
29. Tax-rate and debt-cost proxies are calculated only from reconcilable
    statement periods and are labeled internally calculated rather than
    real-time observed values.
30. Any Treasury yield obtained through `yfinance` records ticker, scale,
    observation date, and retrieval time. Expected ERP and terminal growth are
    separately labeled dated project assumptions unless governed sources
    replace them.
31. Missing `yfinance`, insufficient price history, unavailable mandatory
    issuer fields, or invalid units cannot silently trigger an issuer
    sector-WACC fallback. Issuer valuation becomes `Not calculable`, while an
    optional assumption-only sensitivity remains visually and semantically
    separate.
32. WACC output exposes every component, formula, source class, date, and
    limitation, and reconciles within a defined numerical tolerance.
33. Generic FCFF/WACC remains blocked for financial institutions regardless of
    market-data availability.

## Review gate

This specification was **approved for implementation by the maintainer on
2026-07-28** through the explicit instruction to begin modifying the project.
The approval authorizes the scoped engineering increments; it does not approve
the model for investment use or authorize unsupported data substitution.
