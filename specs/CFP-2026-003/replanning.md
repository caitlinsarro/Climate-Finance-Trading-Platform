# CFP-2026-003 — Quant Model Recalibration and Data Expansion Replanning

## Trigger

CFP-2026-002 established useful engineering controls: risk channels reconcile,
issuer sectors are controlled, missing facilities suppress issuer tactical
output, and proxy data are disclosed. It also established that the model is not
promoted.

The next review found a deeper model-risk issue. The current engine is
internally consistent, but many decision-driving quantities are still project
calibrations rather than empirically estimated issuer inputs:

- the long-term pathways are hard-coded `NGFS-style` values, not imported NGFS
  scenario variables;
- sector transition, macro, vulnerability, resilience, pass-through, and
  valuation parameters are hand-set research assumptions;
- issuer vulnerability overrides are unsupported point estimates;
- national NWS alert mix is not issuer geolocation or financial loss;
- percentage `data confidence`, tactical basis points, buy/sell labels, and the
  `Climate VaR` name can imply more statistical validation than exists;
- the DCF maps terminal proxy percentages into annual FCFF paths without tying
  each channel to issuer financial statements.

The problem is therefore not primarily a user-interface problem. The model
requires a quantitative rebuild of its inputs, units, calibration, uncertainty,
and allowed output semantics before an external demonstration can be treated as
evidence of issuer climate risk.

## Replanned objective

Build a staged climate financial-sensitivity model whose issuer outputs are
calculated only from traceable data and dimensionally valid equations. Preserve
the transparent target-versus-reference workflow, but remove unsupported
precision and trading interpretation.

The model will progress through three distinct levels:

1. **Sector research stress** — official scenario and industry data, explicitly
   not issuer-specific.
2. **Issuer conditional sensitivity** — only when financial, emissions,
   facility, geography, and calibration coverage pass defined gates.
3. **Portfolio aggregation** — only when weighted issuer coverage and
   comparability thresholds pass.

No stage implies a forecast probability or investment recommendation.

## Immediate removals and suppressions

The next implementation MUST remove or isolate the following from the
client-facing research model until separately validated:

1. `Climate VaR` as a headline. Rename it `Conditional Climate Value Impact`
   or `Scenario Sensitivity Range`.
2. Issuer tactical basis-point overlays and automatic climate buy/sell labels.
3. Numeric `data confidence` percentages derived from arbitrary weights.
   Replace them with field-level coverage and evidence grades.
4. Portfolio optimizer climate tilts and climate-alpha backtest claims based on
   uncalibrated issuer climate scores.
5. Unsupported issuer vulnerability overrides and deterministic resilience
   values.
6. Single-point issuer WACC and terminal growth when required market and
   financial inputs are unavailable.
7. Any statement suggesting coverage of all listed companies. Coverage must be
   reported by issuer count, geography, security type, and portfolio weight.

These modules may remain in a separate engineering sandbox, but they must not
be part of the governed client research view.

## Components to retain

- target-versus-reference scenario comparison;
- separate acute physical, chronic physical, macro/supply-chain, and direct
  transition channels;
- explicit source and fallback status;
- issuer-sector verification and unknown-ticker fail-closed behavior;
- annual cash-flow bridge and DCF structure after financial tie-out;
- exact attribution after inputs and units are validated;
- missing-data `Not calculable` behavior;
- separation between engineering acceptance and model promotion.

## Required mathematical rebuild

### 1. Transition risk

Replace normalized sector constants with financial-line equations.

Carbon cost by issuer, jurisdiction, and year:

```text
Delta Carbon Cost(i,t)
= Sum_j [Covered Emissions(i,j,t)
         x (Carbon Price_target(j,t) - Carbon Price_reference(j,t))
         x (1 - Free Allocation(j,t))
         x (1 - Pass Through(i,j,t))]
```

Energy cost:

```text
Delta Energy Cost(i,t)
= Sum_j,f [Energy Quantity(i,j,f,t)
           x (Energy Price_target(j,f,t) - Energy Price_reference(j,f,t))
           x Hedge Exposure(i,j,f,t)]
```

Carbon embedded in energy prices MUST be reconciled so Scope 2/carbon and
energy channels are not double counted.

Demand effect:

```text
Delta Revenue(i,t)
= Sum_region,product [Revenue(i,region,product,t)
                      x Scenario Demand Change(sector,region,product,t)
                      x Documented Elasticity(i,product)]
```

Transition CapEx must equal incremental required spending above the reference
path. Announced issuer spending and already-completed historical action must be
credited rather than penalized a second time.

### 2. Physical risk

Acute risk must become facility-level before it becomes issuer-level:

```text
Expected Loss(i,h,t)
= Sum_facility,event_bin [Event Probability(facility,h,t,event_bin)
                          x Damage Ratio(asset_type,event_bin)
                          x Exposed Asset Value(facility)
                          x (1 - Recovery/Insurance/Resilience(facility))
                          + Business Interruption]
```

NWS alerts remain current hazard context only. FEMA/NOAA historical data may
support calibration; NASA CMIP6 pathways may support forward hazard changes.
None of them independently identifies issuer exposure or loss.

Chronic heat, water, sea-level, and precipitation channels must be separated
and tied to labor productivity, operating expense, revenue, CapEx, or asset
value. They must not be represented by a single generic chronic multiplier.

### 3. Financial translation and valuation

For each explicit forecast year:

```text
FCFF = EBIT x (1 - tax rate) + D&A - CapEx - change in NWC
```

Each climate channel must adjust exactly one documented financial line before
aggregation. Baseline and scenario paths must use the same accounting boundary.

Use the same base discount rate across target and reference paths unless a
separately specified risk-premium channel is introduced. Report WACC and
terminal-growth sensitivity grids. Do not produce a single issuer valuation
when beta, market capitalization, debt, interest cost, tax, or terminal-growth
evidence is missing.

Financial institutions remain outside generic FCFF/WACC and require a separate
residual-income or dividend/equity method.

### 4. Uncertainty

- Scenario differences are conditional stresses, not probabilities.
- Parameter ranges must come from source uncertainty, estimation error, or
  documented alternative specifications.
- P10/P50/P90 labels are prohibited unless a calibrated distribution exists.
- Report sensitivity ranges, coverage, and model-form alternatives separately.
- Portfolio results must disclose the percentage of portfolio weight with
  observed, derived, proxy, and missing inputs.

## Free and public data acquisition plan

### No-key or bulk-download priority

- NGFS/IIASA scenario pathways: carbon prices, energy, macro, sector output, and
  emissions variables, subject to the published license and current physical
  damage warning.
- SEC EDGAR Financial Statement Data Sets from the first available quarter
  (2009 Q1) through the latest published quarter, plus bulk submissions and
  Company Facts where useful: issuer identity, revenue, operating income, tax,
  CapEx, debt, interest, D&A, and filing dates. Raw quarterly archives remain
  local; processed facts and hashes remain governed.
- EPA GHGRP and eGRID downloads: reported U.S. facility emissions, locations,
  and regional electricity emission rates.
- EPA ECHO/FRS: U.S. regulated-facility coordinates and program identifiers;
  corporate ownership still requires manual verification.
- BEA input-output and supply/use tables: sector upstream/downstream structure,
  not issuer supplier identity.
- EIA bulk files: regional energy quantities and prices where issuer quantities
  are unavailable.
- U.S. Treasury: dated risk-free yield curve.
- FEMA NRI/OpenFEMA, FEMA Hazus, NOAA Storm Events, NWS, and NASA
  NEX-GDDP-CMIP6: hazard context, historical calibration, damage functions, and
  forward climate variables.

### Free registration keys

- FRED/ALFRED for point-in-time macro vintages;
- EIA API for selective queries, although bulk files do not require a key;
- BEA API for automated tables where bulk or interactive download is
  insufficient.

### Data that cannot be assumed freely available

- complete global parent-to-facility ownership;
- property replacement values and business-interruption exposure;
- complete Scope 2 and Scope 3 emissions;
- issuer energy quantity by facility and fuel;
- supplier/customer identity, location, and economic weight;
- regional/product revenue at the required granularity;
- insurance, adaptation, redundancy, and recovery evidence;
- comparable issuer transition CapEx and pass-through rates.

For these fields the model will attempt SEC filings, issuer sustainability
reports, EPA records, and controlled manual research. If the result cannot be
verified, the issuer output remains `Not calculable` or sector-only. A vendor
may later replace missing fields, but a guessed point value is prohibited.

## Implementation gates

### Gate 0 — Output integrity

Remove misleading names, numeric confidence, tactical trades, and client-facing
optimizer/backtest claims. Introduce evidence grades and coverage ratios.

### Gate 1 — Official scenario and financial spine

Ingest versioned NGFS variables, SEC financial statements, Treasury rates, BEA
tables, and point-in-time macro data. Replace hard-coded scenario paths and
sector valuation constants where valid source data exist.

### Gate 2 — Transition cash-flow pilot

Select a small set of non-financial U.S. issuers with verified emissions and
financial data. Build carbon, energy, demand, CapEx, and pass-through rows with
manual unit tie-outs and no double counting.

### Gate 3 — Facility physical-risk pilot

Build a governed facility ownership map for the same pilot issuers. Intersect
facility coordinates with observed and forward hazards. Apply documented Hazus
or independently justified damage relationships and show missing asset-value or
business-interruption fields explicitly.

### Gate 4 — Annual FCFF, valuation, and uncertainty

Produce annual target/reference cash-flow bridges, discount-rate sensitivity,
parameter sensitivity, and exact attribution. Block single-point valuation
where mandatory inputs fail.

### Gate 5 — External validation and portfolio eligibility

Compare direction, rank, and attribution with historical events, issuer
disclosures, analyst review, and—when available—licensed MSCI/Bloomberg/Forward
Analytics-style benchmarks. Portfolio aggregation requires a documented
weighted-coverage threshold. Trading use remains a separate model-promotion
decision.

## Review gate

This replanning supersedes the earlier demo-readiness draft for CFP-2026-003.
No calculation code should be changed until the specification and pilot scope
are approved. Client demonstration may show the existing workflow only if it is
described as an unvalidated research prototype and does not show tactical or
investment recommendations.

## Increment 4 replanning decision

DUK is selected as the first governed issuer pilot because its official data
fitness is stronger than the other screened candidates for the combined task:
SEC annual financial history, EPA parent ownership, facility emissions, and
facility coordinates are all available. The model will first produce auditable
input bridges and sensitivities, not a polished single-point issuer value.

The physical-risk gate is split deliberately:

- facility-linked FEMA hazard context is allowed as an exposure screen;
- issuer financial damage remains blocked until Duke-specific exposed values
  and documented asset-type damage relationships are available.

This is a model-control outcome, not an implementation failure. A county-level
community Expected Annual Loss value is not a substitute for the value or loss
of a Duke facility.

## Increment 5 replanning decision

The client story is narrowed to long-horizon scenario and valuation use. The
short-term NWS panel is removed because a live alert is not an issuer cash-flow
input and distracts from the investment workflow.

The eight issuers form a clickable screening universe. Public company financial
data populate a common FCF baseline. Company emissions/facility evidence is used
where available; otherwise the existing sector model is shown as an industry
estimate. DUK remains the deepest evidence example. The interface is simplified
for a prototype, while the data model retains the company-versus-industry source
distinction needed to prevent misleading results.

## Increment 6 replanning decision

The next interface revision is organized as a quantitative decision story,
not a collection of independent KPIs. For a selected issuer the primary client
view will be:

```text
Company FCF/FCFF
  -> physical | direct transition | macro/supply-chain
  -> scenario cash flow
  -> continuing-value sensitivity
  -> portfolio-manager use
```

The three risk channels use the same cash-flow denominator so their rates,
currency effects, and shares reconcile. Long-form attribution and calculation
tables remain available below the executive view for auditability. Investment
use is limited to long-horizon scenario comparison, relative issuer research,
risk budgeting, and engagement; no tactical NWS layer is reintroduced.

## Increment 7 replanning decision

Client review identified two linked problems in the current portal. First, the
issuer view contains too much explanatory text for a live presentation.
Second, project and sector coefficients still appear beside company data in a
way that makes the modeled percentages look more company-specific than the
evidence supports.

The next revision is therefore data-first and fail-closed:

- the main issuer view will use a compact, flat visual hierarchy consistent
  with the existing Jennison presentation language;
- verified company and public-source quantities will be calculated and shown
  before any proxy;
- project or sector parameters will not create headline issuer physical,
  transition, macro/supply-chain, cash-flow, or valuation percentages;
- missing issuer economic exposure, damage functions, pass-through, policy
  incidence, revenue geography, or value-chain weights will return **Not
  calculable**;
- a proxy may remain only as optional sector context, separated from the
  issuer result and never used in the issuer cash-flow or valuation bridge.

For DUK, the permitted data-derived outputs are the governed SEC FCFF candidate,
EPA emissions/facility coverage, FEMA facility-location context coverage, and
the NGFS gross static carbon-price sensitivity. DUK physical financial loss,
net transition cost, issuer macro/supply loss, scenario FCFF, and issuer value
impact remain blocked. The earlier `11.75%`, `1.47%`, and `0.96%` sector-derived
figures are not eligible as DUK headline results.

## Increment 7 scope amendment — eight-issuer public-evidence build

The maintainer rejected a DUK-only fail-closed screen as insufficient for the
client demonstration. The implementation will therefore make a bounded public
data effort for `AAPL`, `CAT`, `CVX`, `DE`, `DUK`, `MSFT`, `NEE`, and `XOM`.

The revised objective is not to force three loss percentages for every issuer.
It is to calculate the strongest comparable quantity supported by public data
at each layer:

1. **Transition:** company-reported Scope 1 emissions, EPA GHGRP where covered,
   official NGFS target-reference carbon prices, and SEC cash flow produce a
   gross carbon-price sensitivity in USD and as a ratio to cash flow. It is not
   net transition cost until policy coverage, free allocation, pass-through,
   and the future emissions path are evidenced.
2. **Physical:** verified facilities or disclosed operational exposure are
   matched to official hazard context. A financial loss is produced only when
   exposed value or an economic weight and a documented damage relationship
   are available. Otherwise the output is a physical-exposure screen, not a
   loss percentage.
3. **Macro/supply:** SEC-reported financial dependency and BEA input-output
   structure replace hand-set issuer/sector betas. A scenario loss is produced
   only when the corresponding target-reference macro or input-price shock can
   be joined on consistent geography, industry, year, and units.

Company reports, SEC filings, EPA, EIA, FEMA, BEA, and NGFS records will be
stored with retrieval dates, source URLs, reporting boundaries, units, and
hashes where a raw file can be retained. Cross-company comparison must use a
common boundary or disclose the boundary difference. Sector constants may not
be used to fill a client-facing issuer headline.

## Increment 8 replanning decision — assumption-enabled client valuation

Increment 7 correctly removed unsupported issuer loss headlines, but it also
stopped the prototype before the financial question a long-horizon asset
manager needs to examine: how a stated climate scenario could change FCFF and
discounted enterprise value. Increment 8 restores that bridge under a strict
two-layer convention:

1. **Observed layer.** SEC cash flow and financial statement facts, reported
   Scope 1 emissions, official NGFS carbon-price paths, EPA facility ownership,
   FEMA county context, dated market prices, and the Treasury rate remain
   separately identifiable and reproducible.
2. **Assumption layer.** Policy coverage, pass-through, emissions decline,
   physical damage conversion, resilience, macro cash-flow elasticity, ERP,
   and terminal growth may be used for a prototype valuation only when each is
   labeled `Model assumption`, included in a Low/Base/High case, and exposed in
   the UI.
3. The prototype MUST calculate annual target and reference cash flows through
   the selected horizon, discount both with the same WACC, and report
   `(PV_target / PV_reference) - 1` with transition, physical, and macro/supply
   attribution.
4. A FEMA score remains a relative hazard input. It may affect an assumed loss
   conversion but MUST never be presented as an observed loss rate.
5. The client headline is `Modeled value impact`, not audited valuation,
   forecast return, probability, price target, or production Climate VaR.
6. The main view is reduced to one result strip, three channel cards, one FCFF
   bridge, and one compact decision panel. Detailed sources and assumptions
   move into a collapsed disclosure.
## Increment 9 — client-demo information hierarchy

The R14 calculation is retained. Replanning is limited to presentation: make
the default portal a single long-term valuation page, remove duplicated research
status prose from the default view, keep the eight issuers and scenario controls
visible, and preserve source/assumption detail behind one disclosure control.
Use the existing restrained Jennison report styling; do not add gradients,
decorative badges, chat-like copy, or dashboard ornament.

## Increment 10 replanning decision — public-data climate-risk extension

R14 completes the annual FCFF and discounted-value bridge, but the quantitative
review identifies two material limitations. A Scope-1-only transition equation
understates companies whose climate exposure is concentrated in purchased
energy or the value chain. The physical equation also converts a relative FEMA
risk score into a financial loss through a project coefficient rather than an
observed loss-rate field.

R15 will therefore replace those two shortcuts where public evidence permits:

- transition risk will keep Scope 1 direct emissions, Scope 2 purchased-energy
  emissions, and Scope 3 value-chain emissions separate, then apply distinct
  and visible policy-incidence and pass-through assumptions;
- acute physical risk will use issuer facilities, an economic exposure base,
  and official FEMA expected-annual-loss rates rather than treating a community
  risk score as a loss rate;
- chronic physical risk will use official scenario-conditioned heat/labour
  productivity pathways and a separately disclosed financial conversion;
- SEC property, plant and equipment and company cash flow will provide the
  financial exposure and valuation denominators where available;
- issuer disclosure, SEC, EPA, FEMA, EIA, and NGFS/Climate Impact Explorer data
  will be retained with source URL, date, units, boundary, and file hash;
- a missing economic allocation, insurance/adaptation effect, policy incidence,
  or value-chain transmission may be filled only by a named Low/Base/High model
  assumption. The interface must not call that assumption observed data.

The scope remains the eight client-demo issuers. R15 is an engineering and
research-prototype iteration; it is not model promotion or a vendor-equivalent
Climate VaR claim.
