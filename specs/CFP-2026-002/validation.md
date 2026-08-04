# CFP-2026-002 — Validation Evidence

## Scope and environment

- **Feature:** CFP-2026-002
- **Validated:** 2026-07-28
- **Environment:** macOS, Python 3, Node.js with `@oai/artifact-tool`
- **Implemented increments:** A — provenance remediation; B — governed
  workbook and source register; C — first no-key hazard ingestion, partial
- **Workbook release:** `CFP-2026-002-R2-20260728T2314Z`
- **Model stage:** research only; not promoted

## Implementation evidence

### Provenance and fail-closed behavior

The application now:

- preserves a cached payload's original `source_mode`;
- records cache status separately from source classification;
- records field-level temperature, CO2, and disaster source classes;
- classifies mixed official/fallback payloads as mixed;
- labels fallback rows `calibrated proxy` or `mixed or incomplete`;
- prevents proxy, carry-forward, current-year, and future-year rows from entering
  the annual decision signal;
- returns `Not calculable` when no complete official completed-year observation
  is available;
- excludes atmospheric CO2 concentration from allocation and transition-score
  calculations while retaining it as context;
- removes embedded 2025 and 2026 proxy observations.

### Governed workbook

`data/climate_risk_data_foundation.xlsx` contains the 21 sheets required by the
specification. It separates source registration, entity and facility mapping,
raw source schemas, normalized transition and physical records, project
calibrations, formula-driven quality checks, and rejected records.

The workbook and its governed release now record:

- 13 authoritative source entries with direct URLs;
- 6 issuer CIKs verified against the official SEC ticker registry;
- 469 NWS active-alert snapshot records in the workbook and immutable raw
  GeoJSON;
- 72,360 NOAA Storm Events records for completed year 2025 in the complete
  processed CSV and immutable raw gzip;
- a deterministic first-5,000-row NOAA workbook audit extract, with the full
  file path and hash retained in the release manifest;
- 13 transition and 13 physical outputs marked `Not calculable`;
- 26 corresponding rejected records;
- 6 project calibration groups marked as model-promotion blockers.

This is a truthful control result. It must not be interpreted as zero climate
risk.

## Automated tests

Command:

```text
python3 -m unittest -v test_climate_methodology.py test_authoritative_ingestion.py
```

Result: **40 tests passed**.

Seven new regression tests verify:

1. mixed official/fallback payloads cannot label proxy temperature as official;
2. cached payloads preserve their original source classification;
3. legacy cache records with fallback notes are reclassified instead of
   retaining a false official label;
4. official feeds containing incomplete or carry-forward rows cannot make the
   whole payload appear wholly official;
5. proxy-only rows make decision outputs not calculable;
6. changing only CO2 concentration cannot change the allocation signal;
7. the embedded proxy table contains no current or future years.

Existing methodology, reconciliation, point-in-time, scenario, allocation,
valuation, and execution tests continued to pass.

Four ingestion tests additionally verify:

1. immutable release files cannot be overwritten with different bytes;
2. the latest NOAA correction stamp is selected deterministically;
3. credential status never returns secret values;
4. NWS ingestion preserves the raw bytes and marks records as context only.

Three short-term fail-closed tests additionally verify:

1. valid live NWS alerts remain calculable when the independent long-run
   climate context is unavailable;
2. a successful NWS response with no matched hazards is labeled as an observed
   zero and produces no tactical trade;
3. an unavailable NWS response produces `Not calculable`, null event risk,
   zero tactical overlay, and no tactical trade.

Additional checks:

```text
python3 -m py_compile app.py
git diff --check
```

Result: **passed**.

## Live source-degradation check

The runtime loader was executed with a temporary cache so the repository cache
was not modified. At validation time it reported:

```text
source_mode              mixed official and non-official climate data
temperature              calibrated proxy
CO2                      observed official
disasters                observed official
complete official rows   0
latest eligible year     null
context status           not calculable — no complete official completed-year observation
```

This confirms the source failure is not hidden: the aggregate payload is mixed,
the temperature field is a calibrated proxy, and the decision context fails
closed instead of calculating a score.

## Workbook validation

The workbook builder inspected `Quality_Checks!A5:H13` and reported:

| Check | Actual | Expected | Status |
|---|---:|---:|---|
| Registered sources with direct URL | 13 | 13 | OK |
| Verified entity mappings | 6 | 13 | NOT READY |
| Calculable transition records | 0 | 13 | NOT READY |
| Calculable physical records | 0 | 13 | NOT READY |
| Promotion-blocking calibrations | 6 | 0 | BLOCKED |
| Populated raw source sheets | 2 | 11 | NOT READY |
| Workbook release ID present | 1 | 1 | OK |
| Visible rejected records | 26 | 26 | OK |

The formula-error scan matched **0** instances of `#REF!`, `#DIV/0!`,
`#VALUE!`, `#NAME?`, or `#N/A`.

The exported workbook passed ZIP package validation. Its SHA-256 at validation
time was:

```text
34fe721bb5c3affccc49700d3929a921b4efe712ba1ce3f00ecfaa83549f9b46
```

Source hashes:

```text
NWS active_alerts.geojson
b97f41922d8991e7f7b76b14dda2cd1360f26eddd09d7147291f7095d6e6bba6

NOAA StormEvents_details-ftp_v1.0_d2025_c20260728.csv.gz
447b536ce7796585b923b946f0b85be538bde142858674f5d0b45a3b4c134bf5
```

All 21 sheets were rendered to PNG and visually reviewed. Titles, headers,
dates, status callouts, source URLs, CIK display, formulas, and rejection
reasons were legible without material clipping.

The first attempt to place all 72,360 NOAA rows in Excel exceeded the
spreadsheet engine's memory limit after formula validation. No raw or processed
data were lost. Replanning changed the workbook to a deterministic 5,000-row
audit extract while retaining the complete immutable gzip and complete flat CSV
in the release. The final workbook export and ZIP validation passed.

## Short-term fail-closed correction

### Defect reproduction

The NWS API returned current alerts, but the live loader attempted:

```text
(null climate_pressure_multiplier - 0.90) / 0.40
```

The exception replaced the valid NWS response with a fallback containing zero
alerts and zero event pressure. The Model Lab then produced a positive tactical
overlay from resilience and opportunity calibrations. The displayed zero was
therefore unavailable processing, not an observed zero.

### Corrected behavior

- Live NWS pressure is computed independently from long-run climate
  computability.
- Missing long-run context is excluded rather than converted to zero.
- Successful NWS responses with no matched hazards are labeled `observed zero`
  and produce zero tactical overlay.
- Failed NWS responses return null event risk, `Not calculable`, and zero
  tactical overlay.
- The browser renders `Not calculable`, not `0.00%`, for unavailable live
  hazard data.

### Live browser evidence

After restarting the local application, the live NWS path reported:

```text
climate-related alerts  151
event pressure          97.08%
top driver              heat
portfolio event risk    31.26%
portfolio overlay       +45 bps
```

The AAPL issuer view for Current Policies versus Delayed Transition at 2050
reported:

```text
AAPL event risk         5.70%
heat contribution       2.19%
storm contribution      1.59%
flood contribution      1.43%
tactical overlay        +122 bps
```

The issuer view retained the limitation `Sector hazard fallback; issuer
facility geolocation not loaded`. Browser console inspection found no errors.
Counts and severity mix are point-in-time NWS observations and may change on
refresh.

## Acceptance-criteria assessment

| Criterion | Result |
|---|---|
| Fallback values cannot be labeled official | Pass |
| No hard-coded future observation is consumed | Pass |
| Workbook formula/schema/source layout checks | Pass for scaffold |
| Representative records tie to direct source | Pass for NWS and NOAA release records |
| Accepted normalized records trace to raw records | Not tested — no accepted records |
| Application snapshots include release/source status | Partial — application payload does; versioned export not built |
| Missing mandatory inputs produce `Not calculable` | Pass |
| Unavailable live hazard input cannot appear as observed zero | Pass |
| Observed-zero NWS response produces no tactical trade | Pass |
| Unitless indicators are not probabilities or losses | Pass for changed paths |
| Existing regression tests pass | Pass |
| Validation and decision record coverage gaps | Pass |

## Residual risks and limitations

1. The workbook is a partially populated governed ingestion release, not a
   production dataset.
2. Six issuer CIKs are verified, but LEIs, fund look-through,
   parent/facility ownership, and geolocation remain unverified.
3. NWS and NOAA Storm Events are tied out and hashed. SEC raw API access is
   blocked by HTTP 403, and EPA, NGFS, BEA, FEMA NRI, and NASA NEX records are
   not yet ingested.
4. Existing scenario, sector, hazard, resilience, and DCF coefficients remain
   project calibrations.
5. Transition channels still lack issuer emissions, energy, jurisdiction,
   scenario-price, and financial-boundary inputs.
6. Physical financial sensitivities still lack facility exposure, supported
   vulnerability/damage functions, resilience evidence, and uncertainty
   calibration.

## Validation conclusion

Increments A and B and the first no-key portion of Increment C are validated as
useful, fail-closed engineering progress. The full feature does not yet meet
its transition-input, facility-mapping, normalization, export, and
application-integration acceptance criteria. The appropriate decision remains
**Iterate**, with the model **not promoted**.

## Issuer transition/physical integrity verification — 2026-07-28

### Defects reproduced

The issuer Model Lab previously accepted the UI sector for an ordinary ticker.
Consequently, `GS` could be calculated as Technology and any unrecognized
ticker silently defaulted to Technology. The largest “transition driver” also
included `country_gdp` and `supply_chain`, even though those are macro and
input-output transmission channels. Finally, an issuer without facility
geolocation received a sector-fallback short-term value displayed as a
percentage and a positive tactical trade.

The earlier AAPL browser evidence in this file showing `5.70%` issuer event
risk and `+122 bps` tactical overlay is therefore superseded. It remains useful
as defect-reproduction evidence but is not an accepted issuer-risk result.

### Corrected contracts

- A controlled issuer-sector crosswalk resolves supported tickers and records
  source, as-of date, and conflicts.
- A verified mapping overrides a conflicting UI sector. An unknown ticker
  fails closed with no physical, transition, valuation, or tactical result.
- Physical, macro/supply-chain, and direct-transition deltas are separate.
- Direct transition includes sector demand, carbon cost, energy cost,
  transition CapEx, and pass-through only.
- The largest transition driver is selected only from direct-transition
  channels.
- The NWS severity/exposure product is displayed as a unitless `/100` research
  index, not as a probability, financial loss, or expected return.
- Without verified issuer facility exposure, issuer event risk is `Not
  calculable`; the sector fallback is display-only and tactical overlay is
  zero.
- Generic FCFF/WACC output for a financial institution is explicitly blocked
  from decision use pending an approved equity or residual-income method.

### Automated verification

Command:

```text
.venv/bin/python -m unittest -v
```

Result:

```text
Ran 48 tests in 6.015s
OK
```

The new tests cover:

- GS/Technology conflict resolution to Financials;
- supported MSFT mapping and unknown-ticker fail-closed behavior;
- physical, macro, and direct-transition delta reconciliation;
- exclusion of GDP and supply chain from direct-transition driver selection;
- pass-through bounded by gross carbon and energy cost;
- monotonic higher carbon-cost shock behavior;
- missing-facility proxy-index display with zero issuer trade; and
- the financial-institution FCFF/WACC applicability blocker.

`python3 -m py_compile app.py` and `git diff --check` also passed.

### Live local-App verification

The local application was restarted at `http://127.0.0.1:8865/`. Point-in-time
NWS data showed 151 climate alerts and a national pressure index of
`97.08 / 100`.

When issuer `GS` was entered while Technology was selected, the application
overrode the request and disclosed:

```text
controlled mapping applied — requested Technology overridden by Financials
```

The corrected GS research view reported:

```text
sector                         Financials
conditional value proxy       -4.62%
physical scenario proxy       +4.04%
macro / supply-chain proxy    +1.54%
direct transition proxy       +0.87%
largest direct channel        sector demand
issuer event risk             Not calculable
sector proxy index            23.58 / 100
tactical overlay              0 bps
valuation applicability       Blocked
```

The corrected MSFT research view reported:

```text
sector                         Technology
conditional value proxy       -5.52%
physical scenario proxy       +7.70%
macro / supply-chain proxy    +1.80%
direct transition proxy       -0.91%
largest direct channel        sector demand
issuer event risk             Not calculable
sector proxy index            5.42 / 100
tactical overlay              0 bps
```

An unknown ticker returned `Not calculable` for every long-term component and
issuer event risk, with a zero tactical overlay and a blocked mapping ledger.
No local-server exception was emitted during these browser runs.

### Validation conclusion for the integrity correction

The issuer mapping, channel separation, unit labeling, and fail-closed tactical
corrections are engineering-validated. Numeric issuer outputs remain
conditional research proxies because issuer facilities, revenue geography,
supplier/customer links, and audited financial channel data are still absent.
The feature decision remains **Iterate** and model promotion remains **Not
promoted**.

## On-demand listed-equity mapping verification — 2026-07-28

The first issuer-integrity correction intentionally failed closed outside a
20-name controlled crosswalk. That prevented false Technology assignments but
also blocked valid equities such as PFE. Increment G adds a second,
lower-authority mapping tier using no-key quote metadata.

Automated result:

```text
Ran 51 tests in 10.898s
OK
```

New cases verify PFE/Healthcare resolution, conflict override, successful
in-process caching, non-equity rejection, and rejection of invalid ticker
syntax before any provider call.

Live browser verification entered `PFE` while `Financials` was selected. The
server disclosed and applied:

```text
listed-equity market mapping applied — requested Financials overridden by Healthcare
Pfizer, Inc. | NYQ | Drug Manufacturers - General
Source: Yahoo Finance quote metadata via yfinance
```

The resulting research view reported:

```text
sector                         Healthcare
conditional value proxy       -11.34%
physical scenario proxy       +12.21%
macro / supply-chain proxy    +1.28%
direct transition proxy       +0.83%
largest direct channel        sector demand
issuer event risk             Not calculable
sector proxy index            21.53 / 100
tactical overlay              0 bps
```

`BAD_TICKER` remained fully `Not calculable` with a suppressed tactical
overlay. The quote-metadata classification is a transparent reference source,
not an issuer-verified or authoritative entity master. The accepted coverage
claim is on-demand support for resolvable listed equities, not universal global
coverage.

Increment G is engineering-validated. It does not change the overall
**Iterate / Not promoted** decision because issuer facility and financial
channel inputs remain unverified.

## Yahoo Finance WACC feasibility verification — 2026-07-29

### Environment and dependency check

The application server was running with Apple Command Line Tools Python 3.9.
Before the check, `requirements.txt` declared `yfinance`, but that interpreter
reported:

```text
WARNING: Package(s) not found: yfinance
```

Because `app.py` catches the import exception, issuer valuation silently used
sector WACC constants. This explains Deere's displayed `beta 1.10; research
calibration`.

The declared dependencies were installed successfully:

```text
yfinance 1.2.0
pandas 2.3.3
numpy 2.0.2
```

### Live Deere field test

Procedure:

```text
yf.Ticker("DE").fast_info
yf.Ticker("DE").info
yf.Ticker("DE").history(period="2y", interval="1d", auto_adjust=True)
yf.Ticker("DE").quarterly_balance_sheet
yf.Ticker("DE").quarterly_income_stmt
yf.Ticker("DE").balance_sheet
yf.Ticker("DE").income_stmt
```

Observed result:

```text
fast_info                 YFRateLimitError: Too Many Requests
info                      YFRateLimitError: Too Many Requests
adjusted price history    YFRateLimitError: Too Many Requests
quarterly balance sheet   0 rows x 0 columns
quarterly income statement 0 rows x 0 columns
annual balance sheet      0 rows x 0 columns
annual income statement   0 rows x 0 columns
```

### Interpretation

The current environment cannot calculate a Deere market-derived beta, market
capitalization, debt weight, debt-cost proxy, or effective tax rate from
Yahoo Finance at this time. Even when requests succeed, Yahoo Finance does not
provide a standard expected equity-risk-premium or defensible terminal-growth
field. Therefore a complete WACC cannot honestly be described as real-time or
entirely obtained from `yfinance`.

The exclusive-Yahoo approach fails the availability, completeness,
point-in-time, and provenance acceptance gates. `yfinance` may be a
best-effort market-data input with cache and fail-closed behavior, but it
cannot replace governed valuation sources or justify a silent sector fallback.

Post-install regression:

```text
Ran 52 tests in 11.212s
OK
```

The runtime emitted an Apple Python LibreSSL compatibility warning from
`urllib3`; this is an additional deployment-environment item to resolve before
relying on outbound market-data ingestion.

The feature decision remains **Iterate** and model promotion remains **Not
promoted**.

## Local US listed-equity sector master — 2026-07-29 UTC

Release `issuer-sector-20260729T021957Z` replaces repeated online sector lookup
with a local, auditable reference master.

Source and output evidence:

```text
SEC ticker/CIK/exchange rows                 10,411
Nasdaq stock-screener rows                    7,130
eligible common-equity sector mappings        5,730
SEC-matched Nasdaq rows                       6,722
rejected non-common securities                1,078
rejected missing/unsupported sector              322

SEC raw SHA-256
4ee71d696e0219644700efd31c23013d6acf30de2ed64c001c01081a2de32c86

Nasdaq raw SHA-256
8b5ecfb2e8a4372410d2168bf7025f8f49dd77c5e711adf1ef679cac9dd9281f

issuer_sector_master.csv SHA-256
73e6152bb14c792fa4a334ac4099c62df3087adc927633b899550a84132a1042
```

Eligible canonical-sector counts:

```text
Basic Materials             134
Communication Services       94
Consumer Cyclical         1,079
Consumer Defensive          143
Energy                      175
Financials                1,346
Healthcare                1,022
Industrials                 586
Real Estate                 261
Technology                  720
Utilities                   170
```

The runtime hierarchy is now controlled crosswalk, local SEC/Nasdaq master,
then on-demand market metadata, then fail-closed.

Automated verification:

```text
Ran 52 tests in 12.628s
OK
```

Browser verification showed PFE sourced locally as:

```text
PFIZER INC | NYSE | United States
Healthcare | Biotechnology: Pharmaceutical Preparations | CIK 78003
```

Entering PFE while Financials was selected was overridden to Healthcare. An
additional non-crosswalk sample, IBM, was sourced locally as Technology with
CIK 51143. Issuer facility risk remained `Not calculable` and tactical overlay
remained zero for both names.

The master is broad US exchange-listed reference coverage, not complete global
coverage and not issuer-verified climate exposure. Increment G remains
engineering-accepted; model promotion remains blocked.
