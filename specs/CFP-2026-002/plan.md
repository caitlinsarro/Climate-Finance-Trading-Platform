# CFP-2026-002 — Implementation Plan

## Constitution

Articles II, III, V, VI, VII, VIII, and IX govern this feature.

## Replanning

Use `replanning.md`. The key change is to build verified data and computability
gates before modifying the risk engine.

## Specification

Use `spec.md`. Maintainer approval is required before implementation.

## Planned implementation increments

### Increment A — Provenance remediation

**Status: implemented and validated in this iteration.**

- Correct aggregate and field-level source labels.
- Remove future/fabricated fallback observations from decision-facing use.
- Add null reason codes, source classes, retrieval dates, and release IDs.
- Add regression tests for mixed official/fallback payloads.

### Increment B — Workbook and source register

**Status: implemented as governed release `CFP-2026-002-R1`; authoritative raw
ingestion remains intentionally empty and is reported as not ready.**

- Create the governed Excel workbook and all required sheets.
- Populate the source register, entity master, data dictionaries, and quality
  checks before downloading bulk records.
- Add explicit input coloring, formulas, data validation, freeze panes, filters,
  and a readable audit layout.

### Increment C — First authoritative ingestion

**Status: in progress.** Release `CFP-2026-002-R2-20260728T2314Z` contains
immutable, hashed NWS and NOAA Storm Events source files, complete processed
extracts, and workbook audit tables. Six issuer CIKs are verified from the
official SEC ticker registry; raw SEC API access remains blocked by HTTP 403.

Prioritize sources that do not require manual issuer-facility inference:

1. SEC Company Facts and filings;
2. EPA GHGRP and eGRID;
3. NGFS transition scenario data;
4. BEA Input-Output data;
5. NOAA Storm Events and FEMA NRI;
6. NASA climate and hazard data;
7. EIA and ALFRED after required API credentials are configured locally.

### Increment D — Controlled entity and facility mapping

- Establish ticker, CIK, LEI where available, EPA facility, NAICS, geography,
  and scenario-region crosswalks.
- Require evidence for parent/subsidiary and facility ownership.
- Record unresolved and ambiguous mappings in `Rejected_Records`.

### Increment E — Normalization and exports

- Normalize units, currencies, dates, identifiers, and reporting boundaries.
- Export only accepted rows to versioned CSV/JSON files.
- Include hashes and manifest metadata.

### Increment F — Application integration

- **Current hotfix:** decouple live NWS processing from unavailable long-run
  climate context; distinguish observed zero from unavailable; suppress
  tactical actions when the live hazard input is not calculable.
- **Issuer integrity hotfix:** add a controlled ticker-sector resolver; fail
  closed for unknown issuers; separate macro transmission from direct
  transition; relabel unitless event indices; suppress issuer tactical action
  without facility mapping; disclose financial-institution valuation
  inapplicability.
- Introduce fail-closed data contracts.
- Keep exposure indicators separate from financial sensitivities.
- Suppress unsupported combined scores.
- Retain project calibrations only in an explicitly selected research mode.

### Increment G — On-demand issuer-sector coverage

**Status: implemented and verified in local issuer-sector release
`issuer-sector-20260729T021957Z`.**

- Add a no-key market-metadata resolver behind the controlled crosswalk.
- Accept only listed-equity quote types and supported canonical sectors.
- Cache successful mappings and preserve source/retrieval metadata.
- Add PFE/Healthcare, non-equity rejection, and invalid-ticker tests.
- Verify PFE and an invalid ticker in the local browser.

## Validation plan

- Source accessibility and direct-record tie-outs
- Schema and required-field checks
- Unit and dimensional consistency
- Point-in-time availability
- Duplicate and ownership conflicts
- Raw-to-normalized record counts and hashes
- Workbook formula-error scan and visual review
- Missing/stale input behavior
- Model regression tests
- Independent manual calculation for representative physical and transition
  records

## Decision gate

- **Engineering decision:** whether the pipeline and application contracts meet
  the specification.
- **Model-promotion decision:** remains separate and defaults to not promoted
  until calibration and external validation are sufficient.
