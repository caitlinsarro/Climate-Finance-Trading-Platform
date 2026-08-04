# CFP-2026-001 — Validation Evidence

## Scope and environment

- **Feature:** CFP-2026-001
- **Validated:** 2026-07-28
- **Code revision inspected:** `c8bb1af32ba33f774e1a3ce5261b1214beea2c1c`
- **Environment:** macOS, project `.venv`, Python 3.9
- **Application changes:** None
- **Governance changes:** Constitution and CFP-2026-001 artifacts

## Current methodology trace

### Strategic physical risk

The application starts with project-calibrated scenario loss fractions for
acute and chronic physical risk. It downscales each country loss to sectors:

```text
sector loss multiplier
  = sector vulnerability
    / sum(value-added weight × sector vulnerability)
```

It then multiplies sector loss by a bounded issuer-to-sector vulnerability
ratio. Fixed-asset intensity is used as the acute proxy and labor intensity as
the chronic proxy. Annual loss paths are passed through the DCF.

### Tactical physical risk

The application computes:

```text
event indicator
  = hazard intensity × exposure × vulnerability × (1 − resilience)
```

NWS alert severity and counts form a unitless national hazard-pressure index.
When issuer facility data are absent, exposure, vulnerability, and resilience
come from sector and issuer fallback tables.

### Transition risk

The strategic DCF uses signed channels:

```text
transition effect
  = country GDP
  + supply chain
  + sector demand
  + carbon cost
  + energy cost
  + transition CapEx
  − pass-through
```

The current implementation multiplies project scenario shocks by normalized
sector coefficients and fixed scaling constants. It excludes atmospheric CO2
concentration from the transition score. Each channel is included once in the
DCF and exact Shapley attribution.

## Automated validation

Command:

```text
.venv/bin/python -m unittest -v test_climate_methodology.py
```

Result: **26 tests passed**.

Verified properties include:

- identical target and reference scenarios produce zero value impact;
- current-policies physical loss exceeds net-zero physical loss under the
  project assumptions;
- transition-channel signs and sums reconcile;
- atmospheric CO2 is excluded from transition pressure;
- physical sector downscaling conserves country loss;
- missing facility data are labeled as a sector fallback;
- scenario outputs do not claim occurrence probabilities;
- tactical overlays are zero-sum and capped;
- Shapley contributions reconcile to total value impact;
- walk-forward results report modeled costs and turnover.

An independent diagnostic confirmed:

```text
acute physical multiplier reconciliation   1.0000000000000002
chronic physical multiplier reconciliation 1.0
same-scenario value impact                  0.0
same-scenario attribution residual          0.0
```

## Authoritative-reference review

- [IFRS S2](https://www.ifrs.org/issued-standards/ifrs-sustainability-standards-navigator/ifrs-s2-climate-related-disclosures/)
  distinguishes physical and transition risks and links them to cash flows,
  financing, and business prospects.
- [IFRS S2 Basis for Conclusions](https://www.ifrs.org/content/dam/ifrs/publications/pdf-standards/issb/english/2023/issued/part-c/issb-2023-c-basis-for-conclusions-on-ifrs-s2-climate-related-disclosures-part-c.pdf)
  distinguishes acute and chronic physical risk and policy, legal, technology,
  and market transition drivers.
- [NGFS scenario guidance](https://www.ngfs.net/system/files/import/ngfs/medias/documents/ngfs_guidance_note_on_the_scenarios.pdf)
  states that scenarios are not forecasts and have acknowledged limitations.
- [NGFS Phase V documentation](https://www.ngfs.net/en/publications-and-statistics/publications/ngfs-climate-scenarios-central-banks-and-supervisors-phase-v)
  warns users about physical-risk methodology limitations and the retraction
  affecting part of the Phase V physical-loss work.
- [NASA GISTEMP v4](https://data.giss.nasa.gov/gistemp/index.html) describes its
  temperature series as estimates of global surface-temperature change.
- [NOAA GML CO2](https://gml.noaa.gov/ccgg/trends/index.html) identifies the
  series as atmospheric CO2 measurements at Mauna Loa, not a carbon-policy or
  issuer transition-risk measure.
- [NOAA NCEI disaster methodology](https://www.ncei.noaa.gov/news/calculating-cost-weather-and-climate-disasters)
  describes national historical event counts and direct-cost estimates; these
  are context, not issuer-specific damage.
- [NWS Alerts API documentation](https://www.weather.gov/documentation/services-web-alerts)
  supports use of alert urgency, severity, and certainty in decision tools, but
  does not turn nationwide alert counts into issuer loss probabilities.

## Findings

### Controls that work

1. **Internal identities are coherent.** Physical downscaling conserves the
   country loss by construction, and Shapley attribution reconciles.
2. **Risk categories are separated.** Acute, chronic, transition, tactical
   event, and market mechanisms remain distinguishable.
3. **Scenario semantics are mostly honest.** The UI states that scenarios are
   conditional and do not carry occurrence probabilities.
4. **CO2 misuse is avoided in transition risk.** Atmospheric concentration is
   shown as climate context rather than treated as carbon price or policy.
5. **Many fallbacks are disclosed.** Missing facility data and absent
   issuer-level transition inputs are identified in model output.

### Material gaps

1. **Mixed-source provenance defect — high severity.** The current official
   climate cache says `source_mode: "official climate data"` while its source
   notes say `fallback temperature proxy`. Rows created from the hard-coded
   proxy—including 2025 and 2026—are labeled `temperature_source: "official"`.
   This is a false representation risk.
2. **Scenario values are not official NGFS data.** Scenario paths in `app.py`
   are explicitly project calibrations. Their names resemble NGFS scenarios,
   but their numerical values are not versioned NGFS observations or licensed
   vendor data.
3. **Transition channels are dimensionless calibrations.** The implemented
   carbon-cost calculation is a normalized scenario shock × normalized sector
   intensity × a fixed scale, not issuer tCO2e × currency/tCO2e. Energy cost,
   demand, CapEx, and pass-through have the same calibration limitation.
   Internal reconciliation does not establish financial-unit validity.
4. **Tactical physical output is an indicator, not calibrated loss.** NWS
   alert counts are transformed through project-chosen weights and a logarithmic
   scale, then combined with non-geolocated sector exposures. The product is
   logical as a heuristic pressure indicator but not as probability, monetary
   loss, or issuer damage rate.
5. **Issuer differentiation is mostly proxy-based.** Facility coordinates,
   asset values, revenue geography, supplier/customer links, insurance, and
   adaptation data are not loaded for the normal path.
6. **Several financial assumptions are static.** Risk-free rate, equity-risk
   premium, debt cost, tax, leverage, and terminal growth are hard-coded or
   sector fallbacks rather than fully point-in-time issuer observations.
7. **Current tests emphasize internal consistency.** They do not establish
   external calibration, predictive validity, unit correctness, or production
   decision fitness.

## Validation conclusion

The implementation is **logically structured and internally testable**, but
its climate-loss magnitudes are **not empirically validated enough for
production investment use**. Most risk outputs should be interpreted as
conditional research sensitivities or unitless pressure indicators. The
mixed-source labeling defect requires remediation before the platform can
claim reliable provenance.

