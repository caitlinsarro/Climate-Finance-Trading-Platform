# Climate-Finance Trading & Risk Platform Constitution

## Preamble

This constitution governs changes to the Climate-Finance Trading & Risk
Platform. Its purpose is to keep research, engineering, validation, and model
governance traceable from the initial proposal through the final decision.

All material changes MUST follow this lifecycle:

**Constitution → Replanning → Specification → Implementation → Validation →
Decision → Roadmap update**

The constitution is the highest-authority project document. A feature
specification, implementation plan, code change, validation report, decision,
or roadmap entry that conflicts with it is invalid until the conflict is
resolved through an explicit constitutional amendment.

## Article I — Spec-First Delivery

1. Every material change MUST have one active feature ID before application
   code is changed.
2. Feature IDs MUST use the form `CFP-YYYY-NNN`, where `YYYY` is the year and
   `NNN` is a zero-padded sequence number.
3. The feature specification MUST define:
   - the problem and intended user;
   - scope and explicit non-goals;
   - functional and non-functional requirements;
   - data inputs, outputs, assumptions, and dependencies;
   - measurable acceptance criteria;
   - known risks, failure modes, and rollback conditions.
4. Replanning MUST occur before implementation whenever evidence changes the
   scope, requirements, assumptions, dependencies, or risk classification.
5. Code MUST NOT be used as the only specification of behavior.
6. Emergency fixes MAY use a shortened specification, but MUST still receive a
   feature ID, validation evidence, decision, and roadmap update.

**Rationale:** Work must remain reviewable and reproducible after the original
author or context is no longer available.

## Article II — Point-in-Time Correctness and Reproducibility

1. A calculation presented as historical MUST use only information that would
   have been available at the stated observation or decision time.
2. Features, targets, portfolio membership, corporate actions, macroeconomic
   vintages, climate observations, and scenario inputs MUST be timestamped or
   have their timing limitation explicitly disclosed.
3. Training, calibration, validation, and evaluation periods MUST be separated
   to prevent look-ahead leakage.
4. Historical joins MUST define release dates, effective dates, timezone
   treatment, lag rules, and missing-data behavior where applicable.
5. Results MUST be reproducible from versioned code, configuration, input
   references, and documented runtime assumptions.
6. If survivorship-free constituents, archived alerts, vintage data, or other
   point-in-time inputs are unavailable, the limitation MUST be visible in the
   specification, validation evidence, and user-facing result.
7. Synthetic or proxy data MUST NOT be presented as observed historical data.

**Rationale:** A plausible result produced with future information is not valid
research evidence.

## Article III — Data Provenance and Honest Representation

1. Every decision-relevant input MUST be classified as one of:
   - observed;
   - vendor or official derived;
   - internally calculated;
   - calibrated proxy;
   - scenario assumption;
   - synthetic test fixture;
   - missing or unavailable.
2. Each external dataset MUST record its source, retrieval or as-of time,
   transformation lineage, units, coverage, and applicable license or usage
   constraint.
3. Fallback behavior MUST be explicit. A fallback MUST NOT silently replace
   unavailable verified data in a client-facing performance result.
4. Scenario assumptions MUST be labeled as conditional stresses rather than
   forecasts unless a separately governed forecasting model supports that
   interpretation.
5. Unsupported precision, invented probabilities, and misleading statistical
   labels are prohibited.
6. Material transformations MUST include reconciliation checks from raw input
   through displayed output.
7. Source status MUST be accurate at both field and aggregate levels. If any
   material field uses a fallback, proxy, synthetic value, or stale carry-forward,
   the containing row and payload MUST NOT be labeled wholly official or observed.
   Aggregate confidence MUST be no higher than the weakest material input unless
   a documented method justifies a different aggregation.

**Rationale:** Users must be able to distinguish evidence from assumptions and
trace a result back to its source.

## Article IV — Execution Realism

1. A strategy, backtest, or portfolio recommendation MUST state its rebalance
   timing, signal availability, order timing, holding period, and benchmark.
2. Validation MUST account for relevant trading costs, bid-ask effects,
   turnover, short-borrow costs, liquidity, and security availability, or
   clearly disclose each omission.
3. A result MUST NOT assume execution at a price that was unavailable after the
   signal became observable.
4. Position sizing and portfolio construction MUST respect the stated market,
   instrument, capital, fractional-share, and mandate assumptions.
5. Gross, net, benchmark-relative, and climate-incremental performance MUST
   remain separately identifiable.
6. Simulated, backtested, paper, and live results MUST never be conflated.

**Rationale:** Research value depends on whether a stated decision could have
been executed under the modeled conditions.

## Article V — Risk Controls and Fail-Safe Behavior

1. Portfolio changes MUST define applicable position, sleeve, sector,
   concentration, liquidity, tracking-error, turnover, scenario-loss, physical
   risk, transition risk, and carbon-cost controls.
2. Limits MUST be measurable, tested, and visible at the point where a user
   makes or evaluates a decision.
3. Missing, stale, malformed, or irreconcilable critical data MUST cause a
   fail-closed or prominently degraded state; it MUST NOT silently produce a
   normal-confidence recommendation.
4. Changes affecting calculations, optimizer constraints, scenario logic,
   execution assumptions, or risk limits MUST include regression coverage.
5. Security, privacy, secrets, and dependency risks MUST be considered during
   specification and validation.
6. The platform remains a research prototype unless a separate production
   approval explicitly changes that status.

**Rationale:** Risk controls are product requirements, not optional reporting
decorations.

## Article VI — Validation and Evidence

1. Validation MUST map directly to the specification's acceptance criteria.
2. Evidence MUST include, as applicable:
   - automated unit, integration, and regression results;
   - data-quality and reconciliation checks;
   - point-in-time and leakage checks;
   - numerical tolerance and sensitivity analysis;
   - portfolio and risk-limit checks;
   - execution-cost and benchmark comparisons;
   - visual or manual review of decision-facing output;
   - documented known limitations.
3. Validation evidence MUST identify the feature ID, code revision, test
   environment, data as-of time, commands or procedures, and outcome.
4. Failed checks MUST remain visible. They MUST NOT be removed, weakened, or
   reclassified solely to obtain acceptance.
5. Where complete validation is impossible, the decision MUST state the
   remaining uncertainty and restrict the permitted use of the feature.

**Rationale:** Acceptance requires durable evidence, not an informal statement
that the application appears to work.

## Article VII — Climate-Risk Mathematical Integrity

1. Climate-related physical risk MUST distinguish:
   - **hazard** — the type, intensity, frequency, duration, or probability of a
     climate or weather event or chronic condition;
   - **exposure** — the assets, operations, revenue, employees, suppliers, or
     counterparties located in or dependent on the affected area;
   - **vulnerability** — the conditional susceptibility of the exposed item to
     damage or disruption;
   - **resilience** — adaptation, insurance, redundancy, substitution, and
     recovery capacity;
   - **financial consequence** — the resulting effect on revenue, operating
     expense, capital expenditure, asset value, financing, or cash flow.
2. Acute physical risk and chronic physical risk MUST be modeled, disclosed,
   and validated separately before any aggregation. Weather alerts MAY measure
   current hazard conditions; they MUST NOT be represented as event
   probabilities, issuer losses, or long-run climate trends without a separately
   calibrated and validated mapping.
3. Transition risk MUST distinguish policy and legal, technology, market and
   demand, energy-price, emissions/carbon-cost, transition-investment, and
   pass-through channels. Each active channel MUST map to an identifiable
   financial statement or valuation line.
4. Every decision-facing climate-risk equation MUST document:
   - every variable and parameter;
   - units and scale;
   - sign convention;
   - observation, release, effective, and valuation dates;
   - time horizon and path interpolation;
   - aggregation and normalization rules;
   - bounds, clipping, and missing-value behavior;
   - calibration source and estimation method;
   - uncertainty and sensitivity treatment.
5. Dimensional consistency is mandatory. Examples include:
   - carbon cost = attributable emissions quantity × carbon-price change,
     converted into the reporting currency and period;
   - energy cost = energy consumption × energy-price change, adjusted for
     hedging and pass-through;
   - demand effect = exposed revenue × scenario demand change × documented
     elasticity;
   - physical financial loss = exposed value × calibrated damage or disruption
     relationship, net of explicitly modeled recovery and resilience.
6. A unitless index, rank, normalized score, or heuristic product MUST be
   labeled as such. It MUST NOT be displayed as a probability, currency loss,
   cash-flow percentage, return, Value at Risk, Expected Shortfall, or calibrated
   damage rate unless empirical calibration and validation support that unit and
   interpretation.
7. Physical and transition channels MUST be mutually reviewed for double
   counting. Country, sector, issuer, supply-chain, market, and valuation effects
   MUST reconcile through a documented aggregation hierarchy.
8. Scenario paths are conditional inputs, not forecasts. Scenario names,
   parameters, version, provider, retrieval date, transformations, and deviations
   from the provider's published data MUST be disclosed. Internally invented or
   adapted paths MUST be called project calibrations and MUST NOT use wording
   that implies they are official provider values.
9. Calibration parameters MUST have an evidence register containing their
   source, sample, estimation method, units, effective period, owner, approval
   status, and allowed use. Unsupported constants MAY be used only as clearly
   labeled research assumptions and MUST block production model promotion.
10. Mathematical validation MUST include, where applicable:
    - identity and reconciliation tests;
    - dimensional-analysis and unit-conversion tests;
    - boundary, clipping, and missing-data tests;
    - monotonicity and sign tests;
    - conservation and portfolio-aggregation tests;
    - alternative specifications and sensitivity ranges;
    - out-of-sample, backtest, and independent benchmark comparison;
    - uncertainty decomposition across data, parameters, model form, and
      scenarios.
11. A model result is not mathematically validated merely because code executes
    or internal identities reconcile. External calibration, empirical validity,
    stability, and decision fitness MUST be assessed separately.
12. Model promotion is prohibited while a material input is falsely labeled,
    provenance cannot be reproduced, units do not reconcile, double counting is
    unresolved, or output semantics exceed the supporting evidence.

**Rationale:** Logical consistency is necessary but insufficient. Climate-risk
outputs must also have correct units, empirically defensible mappings, honest
labels, and financial meaning.

## Article VIII — Decision and Model Promotion

1. Every implemented feature MUST receive exactly one engineering decision:
   - **Accepted** — acceptance criteria are satisfied and residual risks are
     documented;
   - **Iterate** — useful progress exists, but specified gaps require further
     work before acceptance;
   - **Rejected** — the approach fails requirements, creates unacceptable
     risk, or lacks sufficient evidence.
2. The decision record MUST cite validation evidence and list unresolved
   limitations, follow-up actions, and the responsible feature ID.
3. Engineering acceptance means the software change satisfies its engineering
   specification. It does **not** authorize a model for investment use.
4. Model promotion MUST be a separate decision with an explicit target stage,
   such as research, shadow, paper, limited production, or production.
5. Model promotion requires independent evidence appropriate to the stage,
   including performance stability, benchmark comparison, sensitivity,
   monitoring thresholds, rollback criteria, and named approval authority.
6. A feature MAY be engineering-accepted while its model remains research-only
   or is rejected for promotion.

**Rationale:** Correct software can implement an unproven model; the two
judgments must never be collapsed.

## Article IX — Roadmap and Traceability

1. Each decision MUST produce a roadmap update.
2. The roadmap entry MUST include the feature ID, current status, decision,
   delivered scope, deferred scope, dependencies, risks, and next review or
   milestone.
3. Roadmap status MUST reflect evidence rather than percentage-complete
   estimates unsupported by defined deliverables.
4. Rejected and superseded work MUST remain traceable; history MUST NOT be
   rewritten to imply that abandoned approaches were accepted.
5. Specifications, plans, validation evidence, decisions, and roadmap entries
   MUST cross-reference the same feature ID.

**Rationale:** The roadmap is the auditable state of project intent, not merely
an aspirational task list.

## Required Change Artifacts

For each material feature, the repository MUST eventually contain:

```text
specs/CFP-YYYY-NNN/
├── spec.md
├── plan.md
├── validation.md
└── decision.md
```

The shared project roadmap MUST be maintained at:

```text
ROADMAP.md
```

Artifacts MAY begin as concise documents, but they MUST contain enough
information to enforce the articles above. Validation and decision artifacts
MUST be completed before a feature is represented as delivered.

## Change Gate

Before implementation begins, the contributor MUST confirm:

- the constitution has been read;
- an active feature ID exists;
- the specification and acceptance criteria are current;
- replanning impacts have been resolved;
- provenance, timing, execution, and risk requirements are identified.

Before a feature is closed, the contributor MUST confirm:

- relevant tests and reviews were executed;
- validation evidence was recorded;
- an engineering decision was recorded;
- any model-promotion decision remained separate;
- the roadmap was updated.

## Governance and Amendment Procedure

1. This constitution supersedes conflicting process guidance in lower-level
   project documents.
2. Amendments require:
   - a written proposal describing the change and rationale;
   - an impact review covering existing specifications and accepted features;
   - explicit maintainer approval;
   - a version increment and amended date.
3. Versioning follows semantic governance:
   - **MAJOR** — removes or fundamentally redefines a governing principle;
   - **MINOR** — adds a principle, article, or materially stronger obligation;
   - **PATCH** — clarifies wording without changing its governing meaning.
4. Compliance MUST be reviewed during specification, implementation review,
   validation, and final decision.
5. Exceptions MUST be written, scoped, time-bounded, risk-assessed, and
   approved. An undocumented exception is a violation.

## Ratification

- **Constitution version:** 1.0.0-draft
- **Status:** Draft — pending maintainer review
- **Drafted:** 2026-07-28
- **Ratified:** Not yet ratified
- **Last amended:** 2026-07-28
