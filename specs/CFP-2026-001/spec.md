# CFP-2026-001 — Climate-Risk Mathematical Integrity Governance

## Problem

The platform calculates physical- and transition-risk indicators, conditional
scenario value impacts, and tactical hazard overlays. Some inputs are observed
official data, while others are transparent prototype calibrations or
fallbacks. Governance must prevent a calibrated or unitless value from being
represented as observed data, probability, forecast, or financially calibrated
loss.

## Intended user

Maintainers, model developers, validators, and investment stakeholders who
need to understand whether a climate-risk result is mathematically coherent,
traceable, and suitable for its stated use.

## Scope

- Add constitutional requirements for physical- and transition-risk
  definitions, equations, units, signs, aggregation, calibration, and testing.
- Require explicit separation of observations, estimates, calibrations,
  scenarios, and synthetic/fallback data.
- Record a point-in-time audit of the current implementation and identify
  remediation work.

## Non-goals

- Replace current scenario calibrations with licensed or official NGFS data.
- Rebuild the physical- or transition-risk engines in this feature.
- Promote any model to production or authorize investment use.

## Requirements

1. A decision-facing climate-risk metric must have a written mathematical
   definition, variable dictionary, units, sign convention, horizon,
   aggregation rule, bounds, and uncertainty treatment.
2. Physical risk must separate hazard, exposure, vulnerability, resilience,
   and financial consequence; acute and chronic pathways must remain distinct.
3. Transition risk must separate policy/legal, technology, market/demand,
   energy, carbon, investment, and pass-through channels and reconcile them to
   cash-flow lines without double counting.
4. Unitless scores must not be labeled as probabilities, monetary losses,
   return estimates, or calibrated loss rates.
5. Official, observed, derived, calibrated, proxy, fallback, and synthetic
   values must be represented accurately at field and aggregate levels.
6. Mixed-source payloads must not be labeled wholly official.
7. Model validation must include dimensional, identity, boundary, monotonicity,
   conservation, reconciliation, sensitivity, and independent benchmark tests
   appropriate to the metric.
8. Engineering acceptance and model promotion must remain separate.

## Acceptance criteria

- The constitution contains enforceable climate-risk mathematical-integrity
  requirements covering Requirements 1–8.
- The current model is assessed against those requirements with file/line and
  test evidence.
- Known provenance or representation defects are recorded without being
  concealed or reclassified.
- The decision is `Accepted`, `Iterate`, or `Rejected`.
- `ROADMAP.md` records the result and required follow-up.

## Risks and rollback

- Stronger governance can reveal that existing outputs are not eligible for
  production use. That is an intended control, not a regression.
- This governance-only change can be rolled back by reverting the constitution
  and CFP-2026-001 artifacts, subject to the amendment rules.

