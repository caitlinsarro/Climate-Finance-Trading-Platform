# CFP-2026-002 — Replanning

## Trigger

CFP-2026-001 found that the current climate-risk engine is internally
reconcilable but depends heavily on project calibrations. It also found a
mixed-source cache that labels fallback temperature values as official.

The project will therefore establish a verified data foundation before
changing risk formulas or presenting new climate-risk scores.

## Replanned objective

Build a versioned, field-level climate-risk data pipeline and Excel review
workbook that:

1. collects authoritative public data where it exists;
2. preserves raw observations without modification;
3. normalizes units and identifiers in separate processed tables;
4. records provenance, timing, licenses, transformations, and quality checks;
5. refuses to calculate outputs whose required inputs are missing;
6. exports accepted machine-readable snapshots for application use.

The objective is **not** to maximize the number of populated cells. The
objective is to make every populated value defensible.

## Source hierarchy

Numerical inputs will use this priority:

1. official government, regulator, or scenario-provider data;
2. issuer-filed or issuer-published data with a stated reporting boundary;
3. licensed vendor data with documented methodology;
4. peer-reviewed calibration with a documented sample and mapping;
5. project calibration, permitted only for labeled research sensitivity.

Search results, news articles, unsourced web tables, AI-generated values, and
inferred numbers without evidence are prohibited as model inputs.

## Authoritative public-source map

| Risk channel | Primary source | Intended use | Important limitation |
|---|---|---|---|
| Issuer financials | [SEC EDGAR Company Facts and filings](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | Revenue, operating costs, CapEx, debt, tax, shares, filing dates | XBRL tags and reporting periods vary; climate-specific quantities are not guaranteed |
| Facility emissions | [EPA GHGRP](https://www.epa.gov/ghgreporting/find-and-use-ghgrp-data) | Reported facility GHG emissions and location | Covers reporting facilities, not every issuer or Scope 3; ownership mapping requires validation |
| Grid emissions | [EPA eGRID](https://www.epa.gov/egrid) | Plant/subregion generation and emissions rates | Latest published vintage lags current operations |
| Energy prices and quantities | [EIA Open Data](https://www.eia.gov/opendata/index.php/api) | Electricity/fuel price, consumption, generation, and regional energy paths | Some endpoints require an API key; issuer consumption is generally unavailable |
| Transition scenarios | [NGFS Phase V / IIASA](https://data.ene.iiasa.ac.at/ngfs/) | Versioned carbon price, energy, macro, and transition paths | Conditional scenarios, not forecasts; license applies; affected physical-damage variables require special caution |
| Industry transmission | [BEA Input-Output and GDP by Industry](https://www.bea.gov/data/industries/input-output-accounts-data) | Direct/indirect requirements and sector value-added relationships | Industry mapping to securities and issuers requires a controlled crosswalk |
| Point-in-time macro | [ALFRED](https://fred.stlouisfed.org/docs/api/fred/overview.html) | Vintage-aware rates, GDP, inflation, and related series | API key and release/vintage handling required |
| Historical acute hazards | [NOAA Storm Events](https://www.ncei.noaa.gov/stormevents/ftp.jsp) | Event location, type, date, property/crop damage context | Damage reporting is incomplete and not an issuer loss estimate |
| Current acute hazards | [NWS Alerts API](https://www.weather.gov/documentation/services-web-alerts) | Current hazard, severity, urgency, certainty, and area | Alerts are not occurrence probabilities or issuer damages |
| Baseline hazard risk | [FEMA National Risk Index / OpenFEMA](https://www.fema.gov/about/reports-and-data/openfema) | County/tract hazard context, expected annual loss components, resilience | Community baseline is not facility-specific issuer loss |
| Forward hazard pathways | [NASA NEX-GDDP-CMIP6](https://www.nccs.nasa.gov/data-collections/nex-gddp-cmip6/) | Bias-corrected daily temperature and precipitation projections | Requires hazard derivation, model ensemble treatment, and facility geolocation |
| Climate state | [NASA GISTEMP](https://data.giss.nasa.gov/gistemp/index.html) and [NOAA GML](https://gml.noaa.gov/ccgg/trends/index.html) | Observed climate context and data-quality cross-checks | Not direct issuer financial-risk or transition-policy inputs |

## Replanned sequence

### Gate 1 — Stop false precision

- Correct mixed-source labels before ingesting new data.
- Remove fabricated or future fallback observations from decision-facing
  calculations.
- Replace unavailable values with null plus a reason code.
- Rename existing uncalibrated loss-like outputs as research indicators where
  their units are unsupported.

### Gate 2 — Build the governed data workbook

Create `data/climate_risk_data_foundation.xlsx` with these sheets:

1. `README`
2. `Release_Manifest`
3. `Source_Register`
4. `Entity_Master`
5. `Facility_Map`
6. `Raw_SEC_XBRL`
7. `Raw_EPA_GHGRP`
8. `Raw_EPA_eGRID`
9. `Raw_EIA`
10. `Raw_NGFS`
11. `Raw_BEA_IO`
12. `Raw_ALFRED`
13. `Raw_NOAA_Storms`
14. `Raw_NWS_Alerts`
15. `Raw_FEMA_NRI`
16. `Raw_NASA_Hazard`
17. `Normalized_Transition`
18. `Normalized_Physical`
19. `Calibration_Register`
20. `Quality_Checks`
21. `Rejected_Records`

Raw sheets will contain source values exactly as received. Normalization,
crosswalks, calculations, and rejection reasons will be kept separately.

### Gate 3 — Establish computability

Each output will be classified independently:

- **Observed exposure:** sufficient verified observations exist.
- **Derived exposure indicator:** calculation is dimensionally valid but not
  calibrated to financial loss.
- **Conditional financial sensitivity:** units reconcile to a financial line
  under a named scenario, but predictive interpretation is prohibited.
- **Not calculable:** one or more mandatory inputs are missing, stale,
  irreconcilable, or outside the permitted license.

An overall physical- or transition-risk score will not be produced merely
because some channels are available.

### Gate 4 — Implement only accepted data contracts

After workbook review, accepted tables will be exported to versioned CSV or
JSON snapshots. The application will consume those snapshots, not arbitrary
cells or unreviewed workbook formulas.

### Gate 5 — Validate and decide

Validation will cover source hashes, row counts, units, identifiers, date
availability, transformations, rejected records, formula errors, coverage,
reconciliation, sensitivity, and representative manual tie-outs.

Engineering acceptance will remain separate from model promotion.

## Replanning decision

The specification was approved on 2026-07-28. Gates 1 and 2 are implemented,
and Increment C may proceed without creating a new decision-facing score.

## Increment C replanning update — 2026-07-28

### Evidence change

The first no-key release retrieved:

- 469 NWS active alerts;
- 72,360 NOAA Storm Events records for completed year 2025.

Writing all NOAA processed rows into the governed workbook exceeded the
spreadsheet engine's approximately 2 GB working-memory limit. The immutable
NOAA source gzip and complete flat CSV were already preserved with SHA-256
hashes and were not damaged.

### Revised storage rule

1. Complete raw downloads and complete machine-readable processed extracts
   remain in the versioned release directory.
2. The workbook may contain a deterministic audit extract when a complete flat
   source would make the workbook operationally unreviewable.
3. The workbook must state the selection rule, complete record count, release
   path, source URL, and hash.
4. An audit extract is not an accepted normalized dataset and cannot improve
   model computability by itself.

For release `CFP-2026-002-R2-20260728T2314Z`, `Raw_NOAA_Storms` contains the
first 5,000 source-order records. The full 72,360-row CSV and immutable source
gzip remain governed by the release manifest. `Raw_NWS_Alerts` contains all 469
snapshot records.

### Access replanning

- EIA, FRED/ALFRED, and BEA credentials are free but require user-controlled
  registration and must remain local environment variables.
- SEC public APIs require no key. Local scripted access returned HTTP 403 even
  with an identifiable project User-Agent; identifier mapping was verified
  from the official ticker registry, but raw SEC ingestion remains blocked.
- NWS, NOAA Storm Events, OpenFEMA, and public bulk downloads remain the
  priority while credentialed sources are being configured.

### Current decision

Continue Increment C. Do not calculate issuer physical or transition risk from
the newly ingested hazard context because facility exposure, financial
boundaries, vulnerability, resilience, emissions, energy, and scenario-price
inputs remain incomplete.

## Short-term fail-closed correction — 2026-07-28

### Defect evidence

The live NWS request returned current alert records, but
`load_daily_climate_signal()` attempted to subtract from a null long-run
`climate_pressure_multiplier`. The resulting exception replaced the valid NWS
payload with a fallback payload containing zero alerts and zero event pressure.
The Model Lab then produced a positive tactical overlay from resilience and
opportunity calibrations even though the fallback explicitly said the live
hazard input was not calculable.

The displayed `0.00%` therefore represented unavailable processing, not an
observed zero. This violates the constitution's missing-data, provenance, and
execution-realism requirements.

### Revised short-term contract

1. Live NWS processing must not depend on long-run climate-state
   computability.
2. A successful NWS response with no matched hazard events may produce an
   observed zero and must state that the feed was successfully observed.
3. A failed or unavailable NWS response must produce `Not calculable`, never a
   numeric zero presented as observed risk.
4. When short-term hazard data are not calculable, event selection risk is
   unavailable and tactical overlay/action must be suppressed to zero/no
   trade.
5. Long-run scenario outputs may remain available independently, but they must
   not be described as a live NWS driver.
6. Regression tests must cover valid live alerts with unavailable long-run
   context, observed-zero alerts, and unavailable alerts.

## Issuer risk-model integrity correction — 2026-07-28

### Defect evidence

The Model Lab accepted an arbitrary issuer ticker while retaining the manually
selected sector. `GS` was consequently modeled as Technology, which caused GS
and MSFT to share identical Technology transition channels and WACC
assumptions. Unknown tickers also defaulted silently to Technology.

The audit additionally found:

- `country_gdp` and `supply_chain` were included in both the displayed
  transition delta and the selected transition driver, obscuring the
  distinction between macro transmission and direct transition channels;
- a unitless NWS hazard/exposure/vulnerability product was displayed as a
  percentage risk;
- issuer tactical trades were produced from sector hazard fallback even when
  no issuer facility geolocation was loaded;
- financial-sector issuer valuation used a generic FCFF/WACC sector proxy
  without a financial-institution applicability warning.

### Revised issuer contract

1. Known issuers use a controlled ticker-to-sector crosswalk. The server-side
   crosswalk is authoritative for the research taxonomy.
2. A conflicting user-selected sector is overridden and disclosed. An unknown
   ticker is `Not calculable`; it must not default to Technology.
3. Sector source, mapping status, requested sector, resolved sector, and any
   conflict must be returned and displayed.
4. Direct transition channels are carbon cost, sector demand, energy cost,
   transition CapEx, and pass-through. Country GDP and supply chain remain
   separate macro-transmission channels and are included exactly once in total
   valuation.
5. The displayed transition driver is the largest absolute direct transition
   channel and must be labeled `largest calibrated transition channel`.
6. The short-term product is a unitless research index. It must be displayed
   as index points, not a probability, financial loss, or percentage return.
7. Without verified issuer facility exposure, issuer event risk is `Not
   calculable`; a sector proxy index may be displayed separately, but tactical
   overlay is zero and no trade is permitted.
8. Issuer physical and transition outputs based on sector calibrations must be
   labeled conditional research proxies.
9. FCFF/WACC output for financial institutions must carry a visible
   not-decision-suitable warning pending an approved financial-sector valuation
   method.
10. Verification must cover mapping, conflicts, unknown tickers, component
    reconciliation, signs, bounds, monotonicity, conservation, missing
    facilities, financial-sector applicability, and visual output.

## On-demand listed-equity sector coverage — 2026-07-28

### Replanning trigger

`PFE` is a valid listed equity and resolves to Healthcare in available market
metadata, but the first controlled crosswalk contains only 20 research names.
The application therefore failed closed even though the Healthcare sector
model exists. The 20-name crosswalk must not be represented as comprehensive
listed-company coverage.

### Revised mapping hierarchy

1. Use the governed controlled crosswalk when a ticker is present.
2. Otherwise, for a syntactically valid ticker, request no-key market quote
   metadata on demand.
3. Accept the mapping only when quote type is `EQUITY` and the returned sector
   maps to a supported canonical sector.
4. Record ticker, issuer name, exchange, industry, source class, retrieval date,
   and whether the UI sector was overridden.
5. Cache successful results in process to avoid repeated requests.
6. Fail closed for unavailable metadata, ETFs/funds, invalid tickers, or
   unsupported sectors.

## Point-in-time issuer WACC correction — 2026-07-29

### Replanning trigger

The issuer scenario page presents an FCFF valuation using sector-level beta,
capital structure, debt cost, tax, and terminal-growth assumptions. A runtime
audit found that `yfinance` is declared in `requirements.txt` but is not
installed in the Python environment currently serving the application.
Import failure is tolerated, so Deere displays a mathematically reconciled
7.68% WACC built entirely from project constants without making the missing
market dependency prominent.

Yahoo Finance can supply delayed market prices and issuer financial-statement
fields through `yfinance`, but it cannot supply a complete, audited WACC:
expected equity risk premium and defensible terminal growth are not standard
issuer fields, reported debt and interest expense can have boundary and timing
differences, and a market-derived beta depends on the chosen window,
frequency, benchmark, and adjustment rules.

### Revised valuation-input hierarchy

1. For a resolvable non-financial listed equity, retrieve adjusted issuer and
   benchmark prices through `yfinance` and calculate beta internally from
   date-aligned returns. Record benchmark, window, frequency, observation
   count, first/last date, retrieval time, and formula.
2. Retrieve current/delayed market capitalization and the latest available
   reported total debt through `yfinance`. Calculate market-value debt weight
   as `debt / (debt + market capitalization)` and retain the financial
   statement period separately from the market observation date.
3. Calculate a trailing effective tax rate and debt-cost proxy only when the
   required statement lines and periods reconcile. Each result must be labeled
   internally calculated from Yahoo Finance-distributed issuer statements,
   not real-time and not issuer-audited by the application.
4. Retrieve a dated Treasury-yield market proxy through `yfinance` only when
   the selected symbol, scale, and observation date validate. It is a market
   proxy, not an exact maturity-matched issuer valuation input.
5. Expected equity risk premium and terminal growth remain explicit project
   assumptions until governed dated sources are implemented. They must never
   be labeled as Yahoo Finance observations.
6. No unavailable Yahoo-derived issuer field may silently inherit a sector
   constant in an issuer result. Missing mandatory inputs make issuer FCFF/WACC
   valuation `Not calculable`; research assumptions may be displayed only in
   a separately labeled sensitivity result.
7. The application must report dependency availability, field-level source
   class, observation/period dates, retrieval time, fallbacks, and limitations.
8. Financial institutions remain blocked from generic FCFF/WACC valuation even
   when Yahoo fields are available.
9. Tests must cover successful calculation, missing dependency, missing or
   malformed fields, stale/misaligned observations, beta alignment, WACC
   reconciliation, and source-label honesty.

### Scope decision

Use `yfinance` preferentially for the fields it can support, but do not call
the resulting WACC fully real-time or fully Yahoo-sourced. Engineering may
proceed under CFP-2026-002; model promotion remains prohibited.

### Coverage claim

The application may state `on-demand coverage for market-metadata-resolvable
listed equities`. It must not claim complete global listed-company coverage.
Issuer facility and financial-channel limitations remain unchanged after
sector resolution.
