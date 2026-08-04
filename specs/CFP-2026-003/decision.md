# CFP-2026-003 — Decision Record

## Decision

**Iterate — Gate 0 accepted as an engineering increment; quantitative model not
accepted and not promoted.**

## Date

2026-07-31

## Rationale

The governed client view now states the model's real evidence boundary, removes
unsupported issuer vulnerability overrides, fails closed on missing issuer
physical evidence, isolates unvalidated portfolio/trading modules, and uses a
dated official Treasury observation for the risk-free-rate leg.

Official NGFS 5.1 transition pathways are now loaded and governed, but their
translation into issuer cash flow and valuation still depends on project and
sector calibrations. Point-in-time issuer financial statements, emissions,
energy quantities, facility ownership/economic weights, hazard damage
functions, and business interruption are not yet jointly loaded and tied out.
Therefore the model cannot be accepted as an issuer risk model or used for
portfolio decisions.

## Permitted use

- research workflow demonstration;
- source and data-gap review;
- target-versus-reference scenario explanation;
- engineering reconciliation and unit-test review.

## Prohibited use

- issuer loss estimate or forecast probability;
- Climate VaR or regulatory risk measure;
- portfolio tilt, optimization, buy/sell, hedge, or tactical overlay;
- audited issuer valuation;
- shadow, paper, limited-production, or production investment use.

## Exit conditions for the next decision

1. Load governed official NGFS variables and remove hard-coded pathway values
   from any calculable long-term output. **Completed for transition-pathway
   evidence; issuer translation remains gated.**
2. Select one non-financial issuer based on data fitness, not desired result.
3. Tie SEC-derived annual financial statements to an FCFF baseline.
4. Complete at least one source-linked transition channel in currency units.
5. Complete at least one facility-linked physical channel with documented
   damage and economic exposure.
6. Add double-counting, unit, missing-data, sensitivity-grid, and external
   benchmark evidence.
7. Obtain independent quant review; engineering completion alone cannot promote
   the model.

## Increment 2 decision

**Iterate — official NGFS transition ingestion accepted; issuer model remains
unaccepted and not promoted.**

The governed NGFS 5.1 USA transition pathway satisfies the first exit condition
for scenario evidence. It does not by itself establish an issuer cash-flow or
valuation impact. The SEC quarterly-history loader now spans 2009 Q1 through
2026 Q1, but the official archives have not been retrieved because SEC requires
a compliant local contact email in `SEC_USER_AGENT`. Exit conditions 2-7 remain
open.

## Increment 3 decision

**Iterate — full SEC history ingestion accepted; issuer FCFF and climate model
remain unaccepted and not promoted.**

The official 2009 Q1-2026 Q1 archive is complete and hash-governed. The final
processed release corrects XOM's point-in-time registrant identity and exposes
issuer-level field coverage. This satisfies the data-acquisition portion of exit
condition 3, but not the accounting tie-out portion. A high coverage percentage
is not evidence that differently tagged facts share a consistent FCFF boundary.
Pilot selection must also consider emissions, facility, and value-chain evidence,
not financial coverage alone.

## Increment 4 decision

**Iterate — DUK evidence and unit bridges accepted; issuer climate valuation and
model promotion rejected at this gate.**

Exit condition 2 is complete. The SEC 2025 line items and FCFF arithmetic satisfy
the accounting tie-out portion of exit condition 3 for the cash-flow-method
candidate. The gross carbon-price sensitivity satisfies the unit/provenance
portion of exit condition 4, but not net issuer cost because policy incidence,
free allocation, pass-through, and future emissions are missing.

Exit condition 5 remains open. EPA coordinates and FEMA county context establish
facility-linked hazard screening, but do not establish exposed value or damage.
The correct decision is therefore to keep physical financial loss, issuer DCF,
and portfolio use Not calculable rather than fill the gaps with sector constants.

Next decision evidence must include issuer/plant economic weights, defensible
asset-type damage functions, interruption/recovery treatment, a governed WACC
and terminal-growth grid, and external comparison. Engineering acceptance of
R10 does not approve a client investment output.

## Increment 5 decision

**Accepted for prototype demonstration; Iterate for model validation.**

The eight-company navigation, common 2025 FCF baseline, DUK FCFF bridge, and
long-horizon valuation demonstration are accepted for a client walkthrough.
Short-term NWS content is removed from that walkthrough. Company inputs and
industry estimates remain distinguishable with compact source labels.

This decision does not validate the sector stress coefficients, WACC/g inputs,
physical damage, or investment performance. Those remain the next calibration
and external-validation work.

## Increment 6 decision

**Accepted for client demonstration; Iterate for parameter and external
validation.**

The risk-to-cash-flow, cash-flow-to-value, and value-to-investment-use interface
is accepted because its rates, currency effects, dominant-driver share, and
continuing-value bridge reconcile visibly. The design is suitable for showing
how a long-horizon climate scenario can inform peer comparison, risk budgeting,
and issuer engagement.

This acceptance does not convert industry estimates into company facts and does
not authorize a position, trade, price target, or model promotion. Facility
economic exposure, physical damage functions, issuer transition calibration,
WACC/g governance, and external benchmarking remain Iterate items.

## Increment 7 decision

**Accepted for a public-data client prototype; Iterate for issuer financial
loss, valuation, external validation, and model promotion.**

The previous prototype acceptance is narrowed. Issuer percentages produced by
multiplying company cash flow by project or sector coefficients are no longer
accepted in the eight-issuer client view. The new accepted outputs are:

- a source-linked uniform-price gross transition sensitivity using reported
  Scope 1 and the selected official NGFS target-reference carbon-price delta;
- an EPA/FEMA or issuer-disclosed physical-exposure screen with an explicit
  coverage denominator and weighting method;
- SEC financial capacity context and a visible macro/supply data gate;
- comparison and underwriting use without a forecast probability, price
  target, automatic position, or Climate VaR claim.

The gross sensitivity is not a net policy cost. A common NGFS USA analytical
price is applied to global company-reported Scope 1 so that the eight issuers
can be compared on one transparent stress boundary. Jurisdiction, covered
emissions, allocation, pass-through, and the future emissions path remain open.

Physical financial loss is rejected at this gate. FEMA community hazard context
and EPA emissions weights identify where to investigate, but do not provide
replacement value, damage ratios, interruption, or recovery. Macro/supply loss
is also rejected until the BEA/scenario/issuer value-chain join is complete.

Engineering acceptance of R13 does not authorize portfolio, shadow, paper,
limited-production, or production use. The next promotion evidence must include
jurisdictional transition incidence, economic facility weights and damage
functions, issuer value-chain weights, an approved valuation bridge, external
benchmark comparison, and independent quant review.

## Increment 8 decision

**Accepted for an assumption-enabled client prototype; Iterate for production
Climate VaR and investment approval.**

The R14 annual FCFF and common-rate DCF implementation is accepted because the
target/reference paths, Low/Base/High assumptions, WACC inputs, terminal growth,
enterprise-value comparison, and exact three-channel Shapley attribution are
visible and reconciled. The compact interface is accepted for demonstrating how
physical, direct-transition, and macro/supply channels can affect long-horizon
cash flow and valuation.

This acceptance deliberately supersedes Increment 7's fail-closed valuation
presentation for the eight demonstration issuers. When issuer evidence is
missing, R14 may calculate a sensitivity using a clearly identified assumption;
it may not present that assumption as observed data. The selected case and the
Low/Base/High range must remain visible.

R14 is a transparent conceptual implementation of a scenario-to-value workflow,
not a replication of Bloomberg or MSCI proprietary formulas, data, calibration,
or validation. It does not authorize a price target, forecast probability,
automatic position, shadow portfolio, paper trade, or production decision.
Promotion still requires independently estimated parameters, issuer-specific
facility and value-chain economics, damage and recovery functions,
jurisdictional transition incidence, external vendor benchmarking, out-of-sample
tests, and independent quant approval.

## Increment 9 decision

**Accepted for the client-demo interface; calculation status unchanged.**

The single-page information hierarchy and restrained report styling are
accepted. R14 valuation formulas, assumption policy, data provenance, and model
promotion boundary are unchanged. Detailed evidence remains available through
the collapsed calculation disclosure rather than repeated in the headline.

## Increment 10 decision

**Accepted for the eight-issuer public-data client prototype; Iterate for model
promotion and investment use.**

R17 is accepted because it materially replaces two earlier manual shortcuts.
Transition now uses separately disclosed Scope 1, Scope 2, and Scope 3 evidence,
and physical risk now uses SEC PP&E, facility-to-county FEMA expected annual
loss rates, and official CIE heat-productivity pathways. FEMA NRI scores no
longer create issuer loss percentages. SEC CapEx/CFO also differentiates the
company-level macro/supply transmission instead of assigning one identical rate
to all issuers.

The acceptance is conditional on the visible Low/Base/High layer. Scope 2 and
Scope 3 incidence, covered PP&E share, insurance/adaptation recovery, chronic
financial conversion, acute scenario factor, macro elasticity, ERP, and
terminal growth remain model assumptions. For issuers without matched EPA
facilities, the FEMA EAL median remains an identified fallback. These quantities
must not be described as observed issuer losses.

The result remains a transparent scenario-conditioned FCFF/DCF sensitivity,
not a replication of Bloomberg or MSCI, production Climate VaR, forecast
probability, audited valuation, price target, or automatic investment decision.
External vendor benchmarking, issuer facility economics, policy-jurisdiction
mapping, supplier/customer weights, parameter estimation from history, and
independent quant approval remain required before promotion.
