# CFP-2026-003 — Quant Model Recalibration and Data Expansion Specification

## Problem and intended user

The current Model Lab explains a useful climate-to-finance workflow, but most
issuer outputs remain sector/project research proxies. Portfolio managers and
research analysts need to distinguish a sector stress from an issuer
calculation and must not receive unsupported tactical or probabilistic output.

## Scope

- output-semantics and client-view cleanup;
- official scenario, macro, sector, financial, emissions, facility, and hazard
  ingestion;
- issuer transition and physical cash-flow pilots;
- annual FCFF and valuation tie-out;
- uncertainty, coverage, and external validation;
- governed portfolio-eligibility gate.

## Non-goals

- claiming complete global issuer coverage;
- inferring missing company data from ticker or sector alone;
- producing short-term climate alpha or automatic trades;
- assigning scenario probabilities without a separately validated model;
- promoting the model beyond research through engineering acceptance;
- applying generic FCFF/WACC to financial institutions.

## Required removals

1. Replace `Conditional Climate VaR` with `Conditional Climate Value Impact`.
2. Remove issuer tactical overlays and automatic climate buy/sell decisions
   from the governed client view.
3. Replace numeric evidence-confidence percentages with categorical evidence
   grade plus observed/derived/proxy/missing coverage.
4. Remove unsupported issuer vulnerability overrides from calculable outputs.
5. Remove single-point WACC/terminal growth when mandatory inputs are absent.
6. Isolate the climate optimizer and backtest until issuer risk inputs and
   historical climate features pass external validation.

## Functional requirements

1. Every output MUST be classified as sector stress, issuer conditional
   sensitivity, portfolio aggregate, or not calculable.
2. Every material field MUST carry source class, source URL or release ID,
   observation/effective/retrieval dates, units, transformation, and coverage.
3. Official NGFS variables MUST replace hard-coded `NGFS-style` pathways in any
   calculable long-term output.
4. SEC financial facts MUST be selected with filing, period, form, unit,
   amendment, and point-in-time rules.
   The governed history MUST span every published SEC Financial Statement Data
   Set quarter from 2009 Q1 through the retrieval-date latest quarter; partial
   retrieval MUST be disclosed by quarter and MUST NOT be described as complete.
5. Transition channels MUST reconcile to currency or percent-of-FCFF units and
   MUST prevent carbon/energy and demand/macro double counting.
6. Physical issuer calculations MUST require verified facility coordinates,
   ownership confidence, economic exposure weight, hazard measure, documented
   damage relationship, and resilience/recovery status.
7. NWS alerts MUST remain a hazard monitor and MUST NOT create issuer loss,
   probability, basis-point overlay, or trade.
8. Annual scenario and reference FCFF MUST reconcile to the same accounting
   boundary before valuation.
9. Valuation MUST disclose base WACC, terminal growth, sensitivity grid, source
   date, and financial-method applicability.
10. Missing mandatory data MUST return null plus reason codes; zero is valid
    only when an observed or derived zero is supported.
11. Portfolio aggregation MUST disclose evidence coverage by portfolio weight
    and block decision use below an approved threshold.
12. Financial institutions MUST use a separately specified method or remain
    not calculable.

## Pilot scope

The first governed implementation will use a small non-financial U.S. issuer
sample selected only after confirming:

- SEC financial coverage;
- identifiable EPA or issuer-disclosed facilities;
- at least one defensible transition channel;
- at least one defensible physical exposure channel;
- sufficient evidence to perform manual unit tie-outs.

The pilot is selected by data fitness, not by a desired risk result.

## Acceptance criteria

1. Client view contains no `Climate VaR`, climate buy/sell, issuer tactical bps,
   or arbitrary numeric confidence label.
2. No calculable scenario uses hard-coded `NGFS-style` values as if official.
3. At least one pilot issuer carbon-cost calculation ties emissions quantity,
   carbon-price delta, coverage, pass-through, currency, and reporting year to
   source records within tolerance.
4. At least one pilot facility physical calculation ties coordinate, hazard,
   damage relationship, exposed value/weight, resilience status, and financial
   consequence to source records within tolerance.
5. Carbon and energy, physical and macro, and direct and indirect channels pass
   explicit double-counting checks.
6. Annual FCFF bridges reconcile to SEC-derived baseline financials and the sum
   of climate adjustments.
7. Target equal to reference produces zero impact at every channel and valuation
   layer.
8. Higher carbon price cannot reduce gross carbon cost before pass-through;
   higher hazard intensity cannot reduce gross damage before resilience.
9. Missing facility or economic exposure data returns issuer physical risk as
   not calculable.
10. WACC and terminal-growth sensitivity are visible; a single-point issuer DCF
    is blocked when mandatory valuation inputs are missing.
11. Historical-event and holdout validation results remain visible even when
    they fail.
12. Engineering tests, data-quality checks, unit checks, reconciliation,
    browser review, and independent quant review pass before engineering
    acceptance.

## Promotion rule

Engineering acceptance permits a transparent research pilot only. Portfolio,
shadow, paper, limited-production, or production use requires a separate model
promotion decision with named approval authority, benchmark comparison,
monitoring thresholds, and rollback criteria.

## Review gate

The maintainer approved implementation on 2026-07-31 with the instruction to
begin modifying the model. Approval covers the staged engineering work in this
specification. It does not approve investment use or model promotion.

## Increment 4 — governed Duke Energy pilot

The first data-fitness pilot is Duke Energy (`DUK`). Selection is based on the
combination of long SEC history, an identifiable non-financial FCFF boundary,
official EPA parent-to-facility records, reported facility emissions, and
facility coordinates. Selection does not imply that Duke has higher or lower
climate risk than the other candidates.

This increment MUST:

1. preserve the official EPA GHGRP parent-company workbook, GHGRP facility
   summary, and eGRID workbook with hashes and source vintages;
2. match facilities by EPA facility identifier before using names, apply the
   reported parent ownership percentage, and keep unmatched records visible;
3. reconcile a 2025 SEC cash-flow FCFF candidate using a single 10-K filing and
   fiscal period as `CFO - CapEx + after-tax interest`, while clearly labeling
   it a candidate until the filing tie-out is complete;
4. report a gross carbon-price sensitivity in USD per $1/tCO2 and a separate
   NGFS scenario illustration; free allocation, pass-through, emissions decay,
   and jurisdictional incidence MUST remain missing rather than be guessed;
5. link EPA facility coordinates/counties to official FEMA NRI hazard context,
   but MUST NOT convert county community loss or risk scores into Duke loss;
6. return issuer physical financial loss as not calculable until exposed asset
   value, an asset-type damage function, business interruption, and recovery or
   insurance treatment are supported;
7. include candidate-selection, unit, coverage, monotonicity, equal-scenario,
   and double-counting checks in validation evidence.

## Increment 5 — eight-issuer client prototype

The client prototype will be reorganized around the eight screened issuers:
`AAPL`, `CAT`, `CVX`, `DE`, `DUK`, `MSFT`, `NEE`, and `XOM`.

1. Client-facing NWS short-term output is removed from the scenario demo. NWS
   ingestion may remain available as a separate engineering data source.
2. The demo flow is issuer selection, transition/physical sector stress,
   company financial baseline, issuer evidence, and valuation bridge.
3. The interface may use concise `Company data` and `Industry estimate` labels;
   it does not need repeated research-governance prose beside every value.
4. Annual free cash flow uses `operating cash flow - capital expenditure` on a
   consistent fiscal-year boundary. DUK may additionally display the reconciled
   unlevered FCFF bridge.
5. Missing company physical or transition inputs may use a sector estimate only
   when the UI identifies it as an industry estimate. A sector estimate MUST
   NOT be silently represented as a company-reported fact.
6. Negative FCF is displayed as such and MUST NOT be converted into a positive
   DCF by clipping or absolute value.
7. The existing visual design language is retained.

## Increment 6 — issuer risk-to-investment decision design

The client demo MUST explain the quantitative result in the order a portfolio
manager evaluates it: company baseline, risk transmission, cash-flow effect,
valuation effect, and permitted investment use.

1. Physical, direct-transition, and macro/supply-chain effects MUST be shown as
   separate rates and currency impacts on the same company cash-flow baseline.
2. Physical risk MUST expose acute and chronic components. Direct transition
   MUST expose demand, carbon, energy, transition-CapEx, and pass-through
   components without moving macro or supply-chain effects into that bucket.
3. A visible bridge MUST reconcile base FCF/FCFF minus each risk channel to
   scenario cash flow. The displayed signs and units MUST match the formula.
4. Valuation MUST visibly disclose WACC and terminal growth and distinguish the
   continuing-value illustration from an audited market value or price target.
5. The investment section MUST translate the output into scenario comparison,
   peer ranking, risk budgeting, and issuer-engagement questions. It MUST NOT
   produce a short-term signal, buy/sell instruction, or automatic position.
6. The main driver and its share of the combined modeled cash-flow pressure
   MUST be derived from the three displayed channel amounts, not assigned by a
   ticker lookup or narrative rule.
7. Company data and industry estimates MUST remain visibly distinguishable.

## Increment 7 — compact data-first issuer view

The issuer demo MUST prioritize calculated public-source evidence and must not
fill a missing company result with a manual coefficient.

1. The main issuer view MUST contain no headline issuer percentage derived from
   `SCENARIO_LIBRARY`, `SECTOR_TRANSITION`, `SECTOR_GDP_BETA`,
   `SECTOR_SUPPLY_BETA`, or the project FCFF conversion multipliers.
2. A missing issuer physical financial consequence MUST display **Not
   calculable**. Facility-to-FEMA matching may be shown as hazard context, but
   not as issuer loss, probability, or Climate VaR.
3. A missing issuer net transition bridge MUST display **Not calculable**.
   Governed emissions multiplied by the target-reference carbon-price delta may
   be shown as a gross static sensitivity only, with its units and exclusions.
4. A missing revenue-geography or supplier/customer economic-weight bridge MUST
   display issuer macro/supply-chain risk as **Not calculable**.
5. Scenario cash flow and issuer value impact MUST remain **Not calculable**
   unless every included channel and the valuation inputs pass their evidence
   gates. The UI MUST NOT multiply base cash flow by sector stress rates to
   manufacture an issuer bridge.
6. For DUK Current Policies versus the climate-agnostic baseline at 2050, the
   client view MUST reconcile the governed release within rounding tolerance:
   2025 FCFF candidate, EPA ownership-adjusted emissions, emitter and FEMA
   coverage counts, NGFS carbon-price delta, gross USD sensitivity, and gross
   sensitivity divided by FCFF as a reference ratio. That ratio MUST NOT be
   labeled a loss rate.
7. The main presentation view MUST use no more than three concise evidence
   panels and one compact calculation bridge. Long methodology, provenance,
   and proxy detail MUST move into a collapsed disclosure.
8. The existing restrained blue/green/white design language, square geometry,
   typography, spacing, and hierarchy MUST be preserved. Decorative gradients,
   novelty icons, chat-like copy, and excessive card repetition are prohibited.
9. The eight-issuer selector remains available. An issuer without adequate
   evidence may still show its SEC-derived FCF and coverage status, but all
   unsupported risk and valuation fields MUST fail closed.

### Increment 7 public-evidence acceptance criteria

10. All eight demo issuers MUST have a versioned reported-emissions record with
    reporting year, organizational boundary, unit, source URL, and retrieval
    date. EPA and issuer-reported quantities MUST not be silently combined.
11. Gross carbon-price sensitivity MUST equal reported Scope 1 emissions times
    the official NGFS target-reference price delta. The UI MUST show USD,
    USD-per-$1/tCO2, and the ratio to SEC-derived cash flow separately from net
    transition cost.
12. The same ticker, scenario, horizon, and data vintage MUST reproduce the
    same calculation. Equal target and reference prices MUST produce zero gross
    sensitivity, and a higher target price MUST not lower gross sensitivity.
13. Facility and hazard outputs MUST state the coverage denominator and the
    economic weighting method. A facility count or FEMA community-risk measure
    MUST not be labeled issuer financial loss.
14. Macro/supply outputs MUST identify the observed SEC financial field, the
    BEA table and industry mapping, and the scenario shock. Missing any join
    component MUST return `Not calculable`, not an industry beta.
15. The main view MUST distinguish `calculated sensitivity`, `exposure screen`,
    and `not calculable`; these labels cannot be replaced with an unqualified
    `risk percentage`.

## Increment 8 — prototype FCFF and valuation completion

1. The issuer view MUST offer Low, Base, and High assumption cases and pass the
   selected case through the API.
2. Observed and assumed inputs MUST be machine-readable and visually distinct.
3. WACC MUST use a dated Treasury rate, an observed five-year monthly beta when
   available, dated market capitalization, SEC debt/tax/interest fields where
   available, and disclosed fallback values for missing legs.
4. Annual transition cost MUST use reported Scope 1 and the official NGFS
   target-reference carbon-price path before policy-coverage, pass-through, and
   emissions-path assumptions are applied.
5. Physical and macro/supply amounts MUST be displayed as modeled estimates,
   not observed losses, whenever their financial translation uses assumptions.
6. Target-equals-reference MUST produce zero channel deltas and zero value
   impact. Channel amounts MUST reconcile to the annual FCFF delta and displayed
   valuation attribution within rounding tolerance.
7. The main client view MUST contain no long narrative banner, no duplicate
   result section, and no more than three risk-channel cards.
## Increment 9 — compact portal requirements

- Default view contains issuer selection, scenario controls, valuation, three
  FCFF drivers, DCF bridge, portfolio use, and one collapsed calculation detail.
- Evidence overview, side-rail explanations, and the legacy stress matrix are
  not shown in the client-demo view.
- Eight issuer selectors show ticker and sector only; detailed evidence appears
  after selection.
- Typography, navy/grey palette, flat rules, and square controls remain
  consistent with the existing Jennison presentation design.
- R14 formulas and results must not change as a consequence of the UI edit.

## Increment 10 — public-data transition and physical calculation

1. Each of the eight demo issuers MUST have separately stored Scope 1, Scope 2,
   and Scope 3 values when an issuer publishes them. Reporting year, boundary,
   source, unit, retrieval date, and unavailable categories MUST be explicit.
2. Scope 1 direct carbon cost, Scope 2 purchased-energy exposure, and Scope 3
   value-chain exposure MUST remain separate calculation legs. Scope 3 MUST NOT
   be treated as a direct tax payable by the issuer.
3. Every conversion from a Scope 2 or Scope 3 exposure into issuer FCFF MUST use
   an explicit incidence/pass-through assumption and MUST be included in the
   selected Low/Base/High assumption case.
4. Acute physical loss MUST use an economic exposure value and official FEMA
   expected-annual-loss-rate fields for matched facilities. FEMA risk scores,
   percentiles, and ratings MUST NOT be converted into financial loss rates.
5. Facility aggregation MUST disclose its denominator and weighting method.
   Capacity or asset-value weights are preferred; emissions weights may be used
   only as an identified operational-coverage proxy.
6. Chronic physical stress MUST use an official scenario-conditioned physical
   pathway. A financial conversion such as labour share, revenue sensitivity,
   adaptation, or insurance MUST remain an assumption unless issuer evidence is
   loaded.
7. SEC property, plant and equipment and FCFF facts MUST retain filing date,
   period end, accession or source URL, unit, and raw-source hash.
8. Target-equals-reference MUST produce zero transition, physical, macro/supply,
   FCFF, and valuation deltas. Higher carbon-price exposure or physical severity
   MUST NOT improve value before an evidenced opportunity/pass-through channel.
9. The displayed Base value MUST be accompanied by Low and High results. Each
   result MUST reconcile from annual channel amounts to scenario FCFF and DCF.
10. The client view MUST show the material company inputs and calculation in a
    compact disclosure, use `<0.01%` rather than `0.00%` for non-zero rounded
    rates, and identify any assumption without adding a long methodology banner.
11. Raw public files and processed outputs MUST be immutable, hash-governed, and
    reproducible from a versioned build script.
12. Validation MUST cover units, formula tie-outs, scenario conservation,
    monotonicity, missing-data behavior, source/assumption separation, API
    output, and browser presentation. Engineering acceptance remains separate
    from model or investment approval.
