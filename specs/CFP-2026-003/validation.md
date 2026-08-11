# CFP-2026-003 — Validation Evidence

## Validation date

2026-07-31

## Scope of this increment

This validation covers Gate 0 output governance and the first governed official
valuation input. It does not validate an issuer transition model, facility
physical-loss model, forecast distribution, or investment decision.

## Automated engineering evidence

Command:

```text
.venv/bin/python -m unittest -v \
  test_climate_methodology.py \
  test_authoritative_ingestion.py
```

Result: **57 tests passed**.

Additional checks:

```text
.venv/bin/python -m py_compile app.py scripts/ingest_authoritative_data.py
git diff --check
```

Result: passed.

The test suite demonstrates engineering behavior including reconciliation,
monotonicity, unknown-ticker fail-closed behavior, CO2 exclusion from direct
transition risk, missing-facility suppression, unsupported issuer-override
removal, governed-release immutability, and Treasury parsing. It does not
demonstrate empirical damage accuracy or investment usefulness.

## Official data evidence

Governed release:

```text
CFP-2026-003-R1-20260731T2318Z
```

- source: U.S. Treasury official daily par-yield XML;
- records: 146 dated observations for 2026;
- latest observation: 2026-07-31;
- latest 10-year par yield: 4.75%;
- raw and processed SHA-256 recorded in the immutable manifest;
- source SHA-256:
  `56a95cef3047f94610fa7b38264a1ab0991dc08866e0663d4ebbffd546cea21a`.

The application uses this observation only as the risk-free leg. It explicitly
states that ERP, beta, debt cost, capital structure, terminal growth, and issuer
financial-line integration remain calibrations or missing.

SEC Company Facts was attempted from the documented no-key endpoint and
returned HTTP 403 in the current scripted environment. No bypass was attempted,
and no issuer financial data were invented.

## Browser validation

Local application: `http://127.0.0.1:8865/#model-lab-section`

Verified in the in-app browser:

- application title is `Jennison Climate-Risk Research Platform`;
- governed navigation excludes portfolio construction and backtest modules;
- the legacy optimizer/backtest sections are hidden and not calculated during
  normal dashboard loading;
- the pipeline says official NGFS 5.1 transition data are loaded while physical,
  macro, and governed BEA calibration remain pending;
- AAPL issuer scope is labeled a sector-calibrated conditional sensitivity,
  not an issuer loss estimate;
- issuer event risk is `Not calculable` without verified facilities and
  economic exposure;
- the Resolution & Data Honesty table distinguishes project calibration,
  missing issuer evidence, and official Treasury data;
- the Source Lineage table displays `10Y 4.75% | 2026-07-31 |
  CFP-2026-003-R1-20260731T2318Z`;
- no issuer decision output or forecast is authorized.

## Acceptance-criteria status

| Criterion group | Status | Evidence / blocker |
|---|---|---|
| Client semantic cleanup | Pass for governed view | Climate VaR, tactical bps, buy/sell, recommendation, and arbitrary confidence are removed or isolated from the visible governed workflow |
| Official Treasury ingestion | Pass | Immutable release, parser test, source/date/release display |
| Unsupported issuer vulnerability override removal | Pass | Issuer fallback is sector research context and explicitly not issuer-specific |
| Official NGFS pathways | Pass for transition evidence | Immutable 5.1 release, complete governed model/scenario set, hash-verified output, browser disclosure, and affected physical-variable exclusion |
| SEC annual FCFF bridge | Not met | 2009Q1-2026Q1 downloader and filing-selection parser are implemented, but official retrieval and accounting tie-out remain incomplete |
| Issuer carbon-cost pilot | Not met | Emissions, jurisdiction, carbon-price, free allocation, and pass-through evidence are not jointly loaded |
| Facility physical-loss pilot | Not met | Verified ownership, economic exposure, damage function, resilience, insurance, and business interruption are missing |
| Issuer WACC / terminal-value grid | Partial | Treasury risk-free leg is official; remaining issuer inputs and sensitivity grid are pending |
| External/holdout validation | Not met | No validated issuer loss history or external benchmark has been run |

## Validation conclusion

Gate 0 is engineering-valid and materially reduces the risk of false precision.
The quantitative model is still **proxy-dominant** and **not promoted**. The
next valid unit of work is a data-fit non-financial issuer pilot using official
scenario, financial, emissions, and facility evidence with manual unit tie-outs.

## Increment 2 — official transition pathway and SEC history loader

Automated result: **61 tests passed**, followed by successful Python compilation
and `git diff --check`.

Official NGFS evidence:

- immutable release `CFP-2026-003-R5-20260731T2351Z`;
- official NGFS Phase 5.1 data hosted by IIASA, release date 2026-03-20;
- 882 USA observations covering seven scenarios, three models, six transition
  variables, and five-year horizons through 2050;
- raw request, response, run metadata, processed output, and SHA-256 hashes are
  retained; processed SHA-256 is
  `f5f579911148f8665302603b5f6f45e8adce1e9938533b872c4a5f28e05c690a`;
- affected Phase 5 physical-damage variables are deliberately excluded;
- scenario model ranges are labeled as model ranges, not probability intervals;
- issuer carbon cost remains Not calculable until emissions, jurisdiction, free
  allocation, and pass-through evidence are loaded.

SEC history loader evidence:

- the deterministic quarter range is 2009 Q1 through 2026 Q1, 69 archives;
- a synthetic archive test verifies filing-period, form, unit, duration, and
  consolidated-fact selection;
- raw ZIP persistence, per-quarter manifest updates, and resume behavior are
  implemented;
- the official 2009 Q1 retrieval returned HTTP 403 because a compliant
  `SEC_USER_AGENT` contact email is not configured; therefore no SEC issuer
  history is claimed as loaded.

Browser evidence at `http://127.0.0.1:8865/#model-lab-section`:

- the evidence card displays release `CFP-2026-003-R5-20260731T2351Z`;
- Current Policies 2050 carbon price displays a three-model median of
  `$2.16/tCO2` and range `$0.00-$23.19/tCO2`;
- the climate-agnostic `$0.00/tCO2` reference is identified as analytical, not
  an NGFS scenario;
- the UI states that the model range is not a probability interval and that
  issuer carbon cost is Not calculable pending issuer evidence.

Increment 2 conclusion: the official transition-pathway ingestion and display
are engineering-accepted. SEC history, issuer cash-flow translation, physical
damage, and model/investment promotion remain unaccepted.

## Increment 3 — complete SEC history and entity-resolution correction

SEC fair-access retrieval completed after a compliant contact email was supplied
locally. The email was not written to source code, manifests, workbooks, or Git.

Raw evidence:

- release `CFP-2026-003-R6-20260801T003356Z`;
- all 69 official quarterly ZIP archives from 2009 Q1 through 2026 Q1;
- approximately 5.2 GB of local raw bytes, Git-ignored;
- every quarterly manifest entry records source URL, retrieval time, byte count,
  and raw SHA-256.

The first processed pass exposed a point-in-time entity-resolution issue: the
current XOM security master CIK belongs to a successor holding company, while
historical filings use CIK 34088. The parser now retains both current and
controlled historical registrant CIKs. The historical alias is sourced from SEC
FSDS `sub.txt`, not inferred from ticker text.

Final processed evidence:

- release `CFP-2026-003-R8-20260801T005207Z`, derived from immutable R6 raw data;
- 4,078 selected annual XBRL facts and 139 filings;
- candidates: AAPL, CAT, CVX, DE, DUK, MSFT, NEE, and XOM;
- broad annual coverage through fiscal 2025, with structured-field coverage
  varying by issuer and filing;
- facts SHA-256:
  `e326d9f39de75b7f59adbb594007c17ef2376b21b023f27203b916a87a175f6d`;
- coverage SHA-256:
  `9cf1bc4b50bdec55a4b58de1a62ebe9026a6353aee3218eafb195364ca0152e7`.

Automated result: **63 tests passed**, followed by successful Python compilation
and `git diff --check`. Tests cover the 69-quarter boundary, annual filing/fact
selection, immutable bytes, historical/current XOM CIK resolution, hash-verified
SEC loading, and the continued FCFF-pending label.

Final browser verification confirmed that the governed client view displays the
2009Q1-2026Q1 range, 4,078 facts, processed release
`CFP-2026-003-R8-20260801T005207Z`, and `accounting/FCFF tie-out pending` while
the legacy optimizer/backtest sandbox remains hidden.

Increment 3 conclusion: SEC history acquisition, provenance, and coverage
screening are engineering-accepted. Individual filing/accounting tie-out,
normalized FCFF, climate cash-flow translation, physical loss, and investment
use remain unaccepted.

## Increment 4 — DUK governed issuer-evidence pilot

Pilot selection: DUK was selected by combined data fitness, not by its risk
result. The candidate screen compares official EPA parent and direct-emitter
matches for AAPL, CAT, CVX, DE, DUK, MSFT, NEE, and XOM. DUK combines 2009-2025
SEC history with a utility accounting boundary, 49 EPA parent records, 40
direct-emitter matches, and 40 facility coordinates.

Governed release: `CFP-2026-003-R10-20260801T015000Z`.

- EPA GHGRP 2023 summary, GHGRP parent-company XLSB, eGRID 2023 Revision 2,
  FEMA NRI December 2025 county attributes, and the Duke 2025 10-K are retained
  as raw official source bytes with hashes;
- 49 Duke parent records are retained; 40 match the GHGRP direct-emitter sheet
  by EPA facility ID and 9 remain explicitly unmatched;
- reported ownership percentages are applied, including non-100% interests;
- ownership-adjusted matched non-biogenic CO2 is 72,003,079.35472 tonnes;
- 48 of 49 parent-facility records match FEMA county context; the FEMA values
  remain community hazard context and are not converted into Duke loss.

SEC 2025 FCFF bridge, USD:

```text
Operating cash flow                         12,330,000,000
- capital expenditure                      14,024,000,000
+ interest expense x (1 - effective tax)    3,225,556,722.69
= FCFF candidate                             1,531,556,722.69
```

The effective tax rate is `642 / 5,712 = 11.2394958%`. CFO, CapEx, interest,
pretax income, and tax expense were manually confirmed against the consolidated
statements in the filed Duke 2025 10-K. The arithmetic residual is zero. The
line-item tie-out passes; the FCFF method and any valuation remain research-only.

Transition unit bridge:

```text
72,003,079.35472 tCO2 x $2.1579/tCO2 = $155,375,444.94
```

This is a static gross sensitivity using 2023 matched emissions and the NGFS
Current Policies 2050 three-model median. It is not a 2050 emissions forecast,
net carbon cost, FCFF adjustment, or valuation. Jurisdictional incidence, free
allocation, pass-through, and the future emissions path remain missing.

Physical financial gate: **Not calculable**. Facility coordinates and county
hazard context are present, but exposed asset value, an asset-type damage
function, business interruption, and recovery/insurance treatment are missing.
County community Expected Annual Loss is not substituted for issuer damage.

Automated evidence:

```text
.venv/bin/python -m unittest -v
```

Result: **69 tests passed**. Compilation passed for `app.py` and the DUK pilot
builder. Tests include facility-ID/ownership joining, FCFF reconciliation,
equal-scenario zero, carbon-price monotonicity, missing physical inputs
fail-closed, processed-file hash verification, and numeric release ordering.

Browser evidence at `http://127.0.0.1:8865/#model-lab-section`:

- DUK loads hash-verified R10 evidence;
- the page shows 40/49 direct-emitter matches, 40 coordinates, 72.00 Mt CO2,
  $155.4m gross static exposure, and $1.53bn FCFF bridge;
- the former issuer percentage is now labeled `Utilities stress (not issuer
  value)` and the headline says it is not a DUK valuation;
- issuer event risk and physical financial loss remain `Not calculable`;
- hazard rows disclose that EPA/FEMA context is loaded while economic exposure
  and damage evidence remain missing;
- no browser console error or warning was present.

Increment 4 conclusion: official issuer financial, emissions, ownership,
coordinate, and county-hazard evidence is engineering-accepted as a transparent
research pilot. Net transition cost, issuer physical loss, DCF valuation,
external validity, and investment use remain unaccepted.

## Increment 5 — eight-issuer client prototype

Governed release `CFP-2026-003-R11-20260801T023000Z` contains a hash-verified
2025 financial screen for AAPL, CAT, CVX, DE, DUK, MSFT, NEE, and XOM.

- FCF is consistently defined as operating cash flow minus capital expenditure;
- AAPL $98.767bn, CAT $8.918bn, CVX $16.592bn, DE $6.099bn, DUK -$1.694bn,
  MSFT $71.611bn, NEE -$11.568bn, and XOM $23.612bn;
- negative values are retained and are not clipped;
- CVX and NEE CapEx gaps in the controlled FSDS extraction were filled from
  their filed 2025 10-K cash-flow disclosures;
- DUK additionally uses the reconciled $1.532bn unlevered FCFF bridge for the
  continuing-value illustration.

Browser validation confirms eight clickable issuer cards, automatic scope and
sector selection, a visible FCF-to-scenario-cash-flow-to-value bridge, and no
console errors. For DUK the prototype shows $1.5bn FCFF, -11.75% physical,
-1.47% transition, -0.96% macro/supply, $1.3bn scenario cash flow, and a simple
continuing-value move from $40.7bn to $34.9bn using the displayed 5.84% WACC and
2.00% growth inputs.

The client-facing NWS short-term column and hazard table have been physically
removed from the model-lab HTML and JavaScript rendering path; they are not
merely hidden by CSS. The top NWS KPI strip and Climate Signals page remain
outside the client demo. NWS ingestion remains in the engineering code but no
longer participates in the client model-lab flow.

The issuer view now contains a separate company-information panel and an
explicit calculation table. Browser validation for DUK reconciles operating
cash flow `$12.3bn`, CapEx `$14.0bn`, FCF `-$1.7bn`, unlevered FCFF `$1.5bn`,
physical effect `-$180.0m`, transition effect `-$22.5m`, macro/supply effect
`-$14.7m`, scenario cash flow `$1.3bn`, and the continuing-value illustration
from `$40.7bn` to `$34.9bn`. The page contains none of the strings `Short-term`,
`NWS`, or `Hazard Transmission` within the model-lab section, and the browser
console contains no errors.

Final automated result: **70 tests passed**; `py_compile` and `git diff --check`
also passed.

## Increment 6 — risk-to-investment decision design

The selected-issuer view now reconciles one cash-flow denominator through
three separately reported channels: physical, direct transition, and
macro/supply-chain. Each card displays the rate, currency effect, formula,
component breakdown, and company-versus-industry input label.

Browser evidence for DUK:

```text
Base FCFF                                      $1.5bn
- physical, 11.75%                           $180.0m
- direct transition, 1.47%                    $22.5m
- macro / supply chain, 0.96%                 $14.7m
= scenario cash flow                           $1.3bn
```

The derived dominant channel is physical risk at 82.9% of absolute modeled
three-channel cash-flow pressure. It is computed from the displayed amounts,
not assigned by ticker. The continuing-value card shows `$40.7bn -> $34.9bn`,
WACC `5.84%`, and terminal growth `2.00%`, with an explicit statement that it
is not a price target.

AAPL was separately checked to ensure the design is not DUK-specific. It shows
three risk cards and a continuing-value sensitivity of `-11.56%`, with no
`NaN`, `undefined`, or `Infinity` output. The investment panel reports the
dominant channel, peer-comparison use, risk-budget use, and issuer-engagement
question; it produces no buy/sell or short-term signal.

Automated evidence: **70 tests passed**; Python compilation and `git diff
--check` passed. Browser console errors: none. Short-term/NWS content remains
absent from the Model Lab.

## Increment 7 — eight-issuer public-evidence screen

Governed release `CFP-2026-003-R13-20260804T193000Z` supersedes the former
issuer headline calculations for AAPL, CAT, CVX, DE, DUK, MSFT, NEE, and XOM.

Data and provenance checks:

- all eight issuers have a company-reported 2024 Scope 1 quantity, unit,
  organizational boundary, source title, source location, URL, retrieval time,
  and retained raw-file hash where the report was downloadable;
- the common scenario calculation is reported Scope 1 multiplied by the
  official NGFS target-reference carbon-price delta in US$2010/tCO2;
- company-reported Scope 1 is kept separate from EPA GHGRP facility emissions;
- 205 EPA parent-facility records were resolved across six issuers, with 134
  direct-emitter matches and 162 facility-to-FEMA county matches; facility
  coverage may exceed direct-emitter coverage because the parent workbook also
  contains records not present in the direct-emitter table;
- the physical summary reports an emissions-weighted county NRI context where
  EPA weights exist. Apple and Microsoft instead show their disclosed
  water-stress exposure metrics; Caterpillar also shows disclosed water-risk
  management coverage;
- every physical financial-loss field remains null because replacement value,
  asset-type damage, interruption, and insurance/recovery are incomplete;
- SEC cash flow, CapEx, FCF, and CapEx/CFO are retained as financial context.
  Macro/supply loss remains null because revenue geography, value-chain
  economic weights, the governed BEA industry join, and a compatible scenario
  shock are not jointly available.

Formula checks:

- DUK Current Policies versus the climate-agnostic reference at 2050 uses
  79.756 MtCO2e reported Scope 1 and a US$2010 2.1579/tCO2 price delta, producing
  a $172,105,472.40 uniform-price gross sensitivity;
- dividing by the positive $1,531,556,722.69 FCFF candidate produces an 11.2373%
  reference ratio. The interface states that it is not a loss rate;
- equal target and reference scenarios produce zero price delta and zero gross
  sensitivity;
- a higher target price cannot reduce gross sensitivity;
- NEE's negative FCF is preserved and no gross-sensitivity/FCF ratio is shown.

Client-output checks:

- the issuer payload sets physical loss, net transition cost, macro/supply
  loss, scenario FCFF, issuer value impact, and DCF valuation to null;
- the former DUK `11.75%`, `1.47%`, and `0.96%` project coefficients do not
  appear in the selected issuer view;
- the compact view contains four workflow steps, three evidence cards, one
  transition calculation bridge, one valuation gate, and three permitted-use
  cards. Legacy attribution, sector-impact, and calculation-ledger sections are
  hidden for the eight public-evidence issuers;
- changing the reference from the climate-agnostic reference to Delayed
  Transition recomputes the price delta and gross sensitivity without changing
  the emissions boundary or relabeling the result as financial loss;
- browser console errors: none.

Automated evidence:

```text
python3 -m unittest discover -v
Ran 75 tests in 11.692s — OK
python3 -m py_compile app.py scripts/build_eight_issuer_public_evidence.py
git diff --check
```

Increment 7 conclusion: the public-data ingestion, uniform-price transition
sensitivity, facility/hazard exposure screen, fail-closed semantics, and compact
client interface are engineering-accepted. Net issuer transition cost,
physical financial loss, macro/supply loss, scenario FCFF, valuation, Climate
VaR, and investment use remain unaccepted.

## Increment 8 — assumption-enabled annual FCFF and DCF bridge

Governed release `CFP-2026-003-R14-20260804T213000Z` adds the missing valuation
layer without relabeling estimates as observed facts. The main interface now
shows observed inputs, a selectable Low/Base/High assumption case, annual
target/reference FCFF paths, a common-rate DCF, and exact channel attribution.

Data and calculation checks:

- 2025 FCFF candidates are derived from SEC operating cash flow, capital
  expenditure, and after-tax interest. NEE's negative reported FCF is retained
  in the source data and replaced only in the valuation layer by an explicitly
  labeled maintenance-CapEx normalization;
- equity beta is estimated from five years of monthly adjusted issuer and SPY
  returns. Capital structure uses public market capitalization and debt; the
  risk-free rate is sourced from the governed Treasury release;
- WACC uses `E/V * (rf + beta * ERP) + D/V * pre-tax debt cost * (1-tax)`.
  ERP, terminal growth, policy coverage, pass-through, emissions decline,
  physical conversion, resilience, and macro cash-flow elasticity remain
  visible model assumptions;
- transition, physical, and macro/supply shocks are applied annually to the
  target and reference FCFF paths. Both paths use the same WACC and terminal
  growth rate, so the output isolates the selected scenario difference;
- three-channel Shapley contributions reconcile exactly to the total DCF value
  impact. Equal target and reference scenarios produce zero for every channel
  and zero total value impact;
- for DUK, Current Policies versus the climate-agnostic reference at 2050 gives
  a Base modeled enterprise-value impact of `-1.69%`, with a Low/Base/High
  range of `-0.73% / -1.69% / -3.83%`. Base channel contributions reconcile to
  transition `-0.71%`, physical `-0.12%`, and macro/supply `-0.86%` after
  rounding;
- the same Current Policies comparison under the Base case gives modeled value
  impacts of AAPL `-0.697%`, CAT `-0.624%`, CVX `-0.920%`, DE `-0.786%`, DUK
  `-1.693%`, MSFT `-0.658%`, NEE `-0.905%`, and XOM `-1.068%`.

Interface and browser checks:

- the primary view is reduced to scenario, horizon, ticker, and assumption-case
  controls followed by four sections: valuation result, FCFF drivers, FCFF-to-
  value bridge, and investment use;
- detailed observed inputs, assumptions, formulas, and source labels are moved
  behind a collapsed disclosure control rather than repeated in the headline;
- selecting DUK and changing Base to High recomputes the modeled value impact
  from `-1.69%` to `-3.83%`; returning to Base restores `-1.69%`;
- the FCFF bridge displays the normalized financial baseline, annual transition,
  physical and macro/supply deltas, scenario FCFF, reference and target enterprise
  values, WACC, and terminal growth;
- browser console errors: none.

Automated evidence:

```text
python3 -m unittest discover -v
Ran 80 tests in 14.417s — OK
python3 -m py_compile app.py scripts/build_eight_issuer_valuation.py
git diff --check
```

Increment 8 conclusion: the transparent assumption-enabled FCFF/DCF bridge and
compact demonstration interface are engineering-accepted for prototype use.
The output is a conditional modeled enterprise-value sensitivity, not a
Bloomberg/MSCI replication, audited valuation, forecast probability, price
target, automatic trade, or production Climate VaR. Production use remains an
Iterate decision pending issuer-specific economic exposure, damage functions,
policy incidence, value-chain weights, parameter estimation, and independent
external validation.

## Increment 9 — client-demo UI validation

The default portal now renders one long-term valuation page. The side rail,
Evidence Overview, repeated status prose, header metadata badges, and legacy
Stress Matrix are hidden from the client-demo view. Eight issuer selectors show
only ticker and sector. The selected issuer then shows four valuation metrics,
three FCFF channels, the FCFF-to-DCF bridge, three concise portfolio uses, and a
collapsed input/assumption table.

Visual checks confirmed the existing flat navy/grey Jennison design is retained:
no gradients, rounded pills, decorative dashboard tiles, or AI-style explanatory
copy were added. AAPL renders `-$12.5k` rather than the unformatted `-$12515`.
DUK Current Policies versus climate-agnostic baseline remains `-1.69%`, with
Low/Base/High `-0.73% / -1.69% / -3.83%`; channel contributions remain
`-0.71% / -0.12% / -0.86%`. Browser console errors: none.

```text
python3 -m unittest discover -v
Ran 80 tests in 12.574s — OK
python3 -m py_compile app.py
git diff --check
```

## Increment 10 — public-data climate calculation validation

Governed release `CFP-2026-003-R17-20260804T234500Z` extends the eight-issuer
valuation with retained and hash-verified public evidence. The final R17 release
supersedes the intermediate R15/R16 build attempts; the older releases remain
traceable and are not selected by the application.

Data checks:

- all eight issuers have separately stored 2024 Scope 1, market-based Scope 2,
  and published Scope 3 values, including the stated Scope 3 boundary;
- issuer reports are retained where the public server permitted download;
  SEC Companyfacts JSON, FEMA query pages, and CIE JSON responses are retained
  with hashes in the release;
- SEC net PP&E is available for all eight issuers. Deere uses its official 2025
  10-K table because the standard Companyfacts PPE tag is stale;
- 205 EPA parent-facility records are joined to expanded FEMA county records.
  FEMA `ALR_VALB`, not the NRI risk score, supplies the building expected annual
  loss rate. DUK has 48 matched county EAL records from 49 parent facilities;
- the CIE USA GDP-weighted labour-productivity-loss pathway is stored for five
  NGFS scenarios at 2025-2050 grid years and linearly interpolated for annual
  FCFF calculations.

Formula checks:

- transition cost is the sum of three separately returned legs: Scope 1 direct
  policy cost, Scope 2 purchased-energy incidence, and Scope 3 value-chain
  incidence. Scope 3 is not treated as a direct issuer tax;
- acute physical cost uses `SEC PP&E × covered PP&E share × FEMA building EAL
  rate × (1 - insurance/adaptation recovery) × scenario factor`;
- chronic physical cost uses annual baseline FCFF, the CIE heat-productivity
  loss, labour share, and an explicit productivity-to-FCFF conversion;
- macro/supply transmission uses the scenario stress, selected elasticity, and
  a company dependency scale derived from SEC `CapEx/CFO`, bounded to `[0.5,
  2.0]`, so all eight issuers no longer receive the same macro result;
- equal target and reference scenarios return zero for Scope 1, Scope 2, Scope
  3, acute, chronic, macro/supply, total FCFF, and DCF value impact;
- five component legs reconcile to the three displayed channels, and exact
  three-channel Shapley attribution reconciles to total value impact.

DUK Current Policies versus climate-agnostic baseline at 2050, Base case:

```text
reported Scope 1 / 2 / 3       79.756m / 0.254m / 27.608m tCO2e
SEC net PP&E                    $129.959bn
FEMA building EAL rate         0.17566% (48 matches; emissions weighted)
CIE heat productivity loss     7.57987%
transition FCFF pressure       1.2041%  ($30.3m)
physical FCFF pressure         3.1422%  ($79.0m)
macro/supply FCFF pressure     1.9649%  ($49.4m)
modeled value impact           -4.7356%
Low / Base / High              -1.9123% / -4.7356% / -9.8188%
```

AAPL Current Policies transition is small but non-zero. The UI reports
`<0.01%` instead of rounding the value to `0.00%`. AAPL and MSFT, which have no
EPA facility matches in the governed parent file, use the observed eight-issuer
FEMA EAL median and identify that fallback in the calculation disclosure.

Browser validation loaded the refreshed local application, ran AAPL and DUK,
changed the selected issuer, and opened the calculation disclosure. DUK showed
the three channel values above and tied Scope 1/2/3, SEC PP&E, FEMA EAL, CIE,
CapEx/CFO, Low/Base/High assumptions, annual FCFF, and DCF without `NaN`,
`undefined`, or missing fields. The compact flat Jennison visual hierarchy was
retained.

Automated evidence:

```text
python3 -m unittest discover -v
Ran 86 tests in 15.440s — OK
python3 -m py_compile app.py scripts/build_eight_issuer_climate_evidence.py
git diff --check
```

Increment 10 conclusion: the public-data calculation upgrade is
engineering-accepted for the eight-issuer client prototype. Model and investment
promotion remain Iterate because facility asset allocation, insurance and
adaptation, Scope 2/3 incidence, acute scenario scaling, macro elasticities,
terminal growth, and ERP still contain assumptions and have not been externally
benchmarked or independently approved.

## Increment 11 validation — report chart and scenario comparison export

The export called `climate_model_lab_payload` for AAPL, CAT, CVX, DE, DUK,
MSFT, NEE and XOM across five governed target/reference comparisons and the
Low/Base/High cases at 2050. It produced 120 calculable rows in
`reports/data/eight_issuer_scenario_results_2050.csv` and eight issuer-input
rows in `reports/data/eight_issuer_model_inputs.csv`. All rows identify the R17
release and preserve scenario, case, channel, FCFF, WACC, emissions, FEMA and
assumption fields.

Reconciliation checks:

- the issuer, scenario-pair and assumption-case Cartesian product is complete;
- DUK Current Policies versus baseline Base remains `-4.735551%`, equal to the
  governed application payload rather than a copied chart value;
- transition, physical and macro/supply value contributions reconcile to total
  value impact for every calculable row;
- missing values pass through as blank/`None`; numeric zero remains distinct;
- no application valuation, channel or DCF formula was duplicated or changed.

Seven independent report figures and one contact sheet were rendered and
visually inspected. The heatmap annotates uncapped results while capping colour
at ±100% so the DUK terminal cash-flow-floor outcomes do not erase smaller
cross-issuer differences. The physical-evidence chart explicitly names AAPL
and MSFT as lacking an issuer facility-match denominator rather than plotting
that missing coverage as zero. Every figure carries the research-prototype,
conditional-comparison and release limitation.

Automated evidence:

```text
.venv/bin/python scripts/build_report_charts.py
Built 120 model rows (120 calculable); 7 figures and 1 contact sheet

.venv/bin/python -m unittest discover -v
Ran 90 tests in 28.476s — OK

.venv/bin/python -m py_compile app.py scripts/build_report_charts.py
git diff --check
```

Increment 11 conclusion: Accepted for reproducible report and presentation
export. The underlying model remains Iterate/research-only; the figures do not
constitute vendor replication, model validation, a price target or an
investment recommendation.

## Increment 12 validation — client-review diagnostics and workbook

The governed export still contains 120 calculable rows: eight issuers, five
target/reference comparisons and Low/Base/High assumption cases at 2050. The
R17 valuation logic was not changed. The reporting layer now adds the boundary,
data-quality and assumption diagnostics requested during client review.

Diagnostics and reconciliation checks:

- DUK's FCFF chart now bridges its 2050 reference terminal FCFF of `$2.513bn`
  through transition `-$0.030bn`, physical `-$0.079bn` and macro/supply
  `-$0.049bn` to target terminal FCFF of `$2.354bn`;
- the DUK Net Zero Base target enterprise-value floor remains visible at
  `-100%` and is labelled as a boundary result rather than a point estimate;
- DUK Current Policies versus Delayed Transition remains visible at
  `+425.67%` and is flagged as denominator-sensitive rather than interpreted as
  a forecast return;
- physical-data confidence is High above 80% issuer facility-to-FEMA match
  coverage, Medium from 50% through 80%, Low below 50%, and Unverified where
  issuer facilities are absent;
- AAPL and MSFT are explicitly Unverified and retain a blank issuer-specific
  FEMA rate because the model uses a disclosed cross-issuer proxy for them;
- the common scenario macro elasticity and the separate issuer-specific SEC
  CapEx/CFO dependency scale are both exported and labelled;
- Scope 2 and Scope 3 financial-incidence assumptions remain separate from
  reported emissions and visible in the input export.

Ten figures plus the contact sheet were regenerated and visually inspected.
The new Net Zero range, channel-mix and extreme-case figures retain raw values,
while heatmap colour alone is capped for readability. No result was removed or
winsorized.

`reports/Eight_Issuer_Climate_Stress_Test.xlsx` was built from the governed CSV
exports with seven sheets: Read Me, Inputs, Scenario Results, Base Matrix, Data
Quality, Checks and Source Audit. The Base Matrix and Checks sheets are
formula-driven. Rendered-sheet inspection found no clipped decision fields or
formula errors. The workbook reports overall export status `OK`, including the
120-row/8-issuer/release checks, DUK attribution and terminal-FCFF tie-outs,
physical confidence, proxy count, facility coverage, EV-floor flag and common
macro-assumption count.

Automated evidence:

```text
.venv/bin/python scripts/build_report_charts.py
Built 120 model rows (120 calculable); 10 figures and 1 contact sheet

.venv/bin/python -m unittest discover -v
Ran 93 tests in 28.095s — OK

.venv/bin/python -m py_compile app.py scripts/build_report_charts.py
git diff --check
```

Increment 12 conclusion: Accepted for client-review chart and workbook use.
The analytical layer is reconciled and transparent, but independent model
validation and investment/model promotion remain Iterate.

## Increment 13 validation — repair-review integration

The repair review was traced into the source engine, API, compact client UI,
calculation-workflow PDF and reviewed workbook. The repaired engine now exposes
target and reference transition costs separately, applies pass-through once,
returns the annual FCFF and discount path, and stops at enterprise value when a
governed EV-to-equity bridge is unavailable.

Decision diagnostics now include the symmetric enterprise-value difference,
dollar EV delta, FCFF floor and unapplied cost, denominator sensitivity,
physical-proxy use and `RANKABLE / CAUTION / EXCLUDE` status. Every remaining
calibration input that is not issuer-observed is labelled `Prototype
demonstration assumption - not issuer-observed`; it is retained only to
demonstrate the scenario-to-FCFF-to-enterprise-value workflow.

Validation evidence:

```text
.venv/bin/python -m unittest discover -v
Ran 96 tests in 51.250s — OK

.venv/bin/python -m py_compile app.py scripts/build_report_charts.py
git diff --check
```

The six-page calculation PDF was rendered and visually reviewed. The revised
12-sheet workbook was rendered sheet by sheet, and its formula-error scan found
no `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?` or `#N/A` errors.

The full chart pack was regenerated after repair integration. All chart footers
now label non-observed calibration inputs as prototype demonstration
assumptions. The new eleventh chart traces the DUK result from observed data and
scenario paths through demo assumptions to annual 2050 FCFF pressure and
enterprise-value sensitivity, and explicitly blocks an equity/share-price
interpretation. Fifteen targeted chart and valuation tests passed after this
regeneration.

Increment 13 conclusion: Engineering Accepted for repair integration and
demonstration disclosure. Quant/model promotion remains Iterate because the
remaining incidence, physical conversion, macro transmission, forecast-growth
and EV-to-equity inputs are not independently estimated or validated.
