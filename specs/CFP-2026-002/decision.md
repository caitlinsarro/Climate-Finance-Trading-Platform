# CFP-2026-002 — Decision

## Engineering decision: Iterate

The provenance remediation, governed workbook, and first no-key hazard
ingestion are accepted as completed increments, but CFP-2026-002 as a whole
must **Iterate**.

The implementation now prevents mixed or proxy climate data from being
represented as wholly official, removes current/future embedded proxy
observations, excludes CO2 concentration from allocation scoring, and fails
closed when complete official observations are unavailable. The workbook
provides the required review structure and accurately exposes missing data,
blocked calibrations, and rejected outputs.

Release `CFP-2026-002-R2-20260728T2314Z` preserves and hashes NWS and NOAA
Storm Events data and verifies six SEC CIK mappings. These inputs improve
provenance and hazard context but do not supply issuer exposure or transition
financial channels.

The short-term fail-closed correction is engineering-accepted within Increment
F. A valid NWS payload is no longer discarded when independent long-run
climate inputs are unavailable. Unavailable NWS processing now returns `Not
calculable` with zero tactical overlay, while a successful observed-zero
response is identified separately. This correction does not validate the
sector hazard betas or issuer vulnerability proxies as financial loss models.

The feature cannot be engineering-accepted yet because most authoritative raw
sources, facility mapping, raw-to-normalized financial lineage, versioned
application exports, and application integration remain incomplete.

## Model-promotion decision: Not promoted

Physical- and transition-risk models remain **research only**. No investment,
paper-trading, shadow, limited-production, or production promotion is
authorized.

Promotion remains blocked by:

- only 6 of 13 entity mappings verified, with no verified fund look-through;
- only 2 of 11 raw source sheets populated;
- zero calculable issuer transition or physical records;
- six material project-calibration groups;
- absent external calibration, dimensional tie-outs, and independent
  validation.
- issuer short-term results still use sector hazard exposure and resilience
  fallbacks because facility geolocation is not loaded.

## Next iteration

Continue CFP-2026-002 with Increment C:

1. obtain free EIA, FRED/ALFRED, and BEA keys through user-controlled official
   registration and configure them only as local environment variables;
2. resolve SEC scripted HTTP 403 access without bypassing fair-access controls;
3. ingest immutable, hashed first releases from EPA GHGRP/eGRID, NGFS, BEA,
   FEMA NRI, and NASA hazard sources;
4. add EIA and ALFRED after their free credentials are configured locally;
5. populate `Rejected_Records` for failed mappings;
6. normalize accepted records with units and point-in-time fields;
7. perform representative manual carbon-cost and physical-exposure tie-outs;
8. export versioned CSV/JSON snapshots before application consumption.

## Rollback

If the application changes cause an operational regression, revert only the
runtime provenance changes while retaining the governance artifacts and
workbook evidence. Do not restore false official labels or future proxy
observations.

## Decision amendment — issuer risk-model integrity correction

### Engineering: Accepted increment; feature remains Iterate

The controlled issuer-sector mapping, unknown-ticker fail-closed behavior,
physical/macro/direct-transition separation, direct-channel driver selection,
unitless NWS index labeling, and issuer tactical suppression have passed 48
automated tests and local browser verification.

GS is now resolved as Financials even when Technology is selected, while MSFT
remains Technology. Supply chain is reported as macro transmission rather than
as the largest transition driver. Missing facility exposure no longer produces
an issuer risk percentage or tactical trade.

### Model promotion: Not promoted

This engineering acceptance does not authorize issuer investment decisions.
Long-term issuer values are conditional research proxies, short-term
sector-fallback indices are not issuer losses or probabilities, and financial
institutions require an approved equity or residual-income valuation method
before decision use.

The overall CFP-2026-002 decision therefore remains **Iterate**.

## Decision amendment — on-demand issuer-sector coverage

### Engineering: Accepted increment

The application now resolves a valid equity outside the controlled crosswalk
from no-key market quote metadata, but only when the quote type is `EQUITY` and
the sector maps to a supported canonical model sector. PFE was browser-verified
as Healthcare, while invalid tickers and non-equity instruments remain
fail-closed. All 51 automated tests pass.

### Coverage and promotion

This is broad on-demand coverage, not a claim that every global listing is
available. Quote metadata is a reference classification below the governed
crosswalk in the source hierarchy. Physical and transition outputs remain
sector-calibrated research proxies, and issuer tactical use remains blocked
without verified facilities.

The feature remains **Iterate** and the model remains **Not promoted**.

## Decision amendment — local issuer-sector master

### Engineering: Accepted increment

Release `issuer-sector-20260729T021957Z` preserves source bytes and hashes,
joins SEC ticker/CIK/exchange identity to Nasdaq sector/industry metadata, and
loads 5,730 eligible common-equity mappings locally. Non-common securities and
missing/unsupported sectors are explicitly rejected. PFE and IBM were
browser-verified, and all 52 tests pass.

### Model promotion: Not promoted

Sector identity coverage is materially improved, but sector membership is not
facility exposure, transition financial data, or issuer loss calibration.
Issuer event risk and tactical trading therefore remain blocked without
verified facility data. The overall feature remains **Iterate**.

## Decision amendment — Yahoo Finance WACC feasibility

### Engineering: Iterate

Using `yfinance` as the exclusive real-time WACC source is not accepted.
Runtime verification for Deere returned Yahoo rate-limit errors for price and
metadata endpoints and empty financial-statement tables. The library also
lacks standard expected-ERP and terminal-growth inputs, so it cannot by itself
produce a complete defensible WACC.

Installing the declared dependency corrects an environment gap but does not
make the data available or validated. Future implementation may use
Yahoo-distributed prices and issuer statements preferentially when field-level
dates, units, and completeness checks pass. Missing mandatory inputs must fail
closed rather than silently restore sector constants.

### Model promotion: Not promoted

The existing Deere 7.68% WACC remains an assumption-only research
calibration. No market-derived Deere WACC was produced by this verification.
The overall feature remains **Iterate**.
