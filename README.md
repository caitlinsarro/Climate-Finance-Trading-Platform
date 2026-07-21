# Jennison Climate-Finance Trading & Risk Platform

Institutional U.S.-listed climate-finance research workspace for portfolio decisions, scenario repricing, risk attribution, and validation.

## What It Does

- Investment Committee View combining strategic posture, tactical action, largest risk contributor, evidence confidence, and affected holdings
- Portfolio construction workspace with ETF-only, ETF + stock, and stock-only modes; short/long horizons; and mandate-aware sizing
- Explicit portfolio risk budget with maximum position, HHI, effective positions, climate active share, weighted holding-tail proxy, capital at risk, and internal watch checks
- Market-only ablation for every holding so clients can see exactly how climate data changed the target weight
- Interactive Scenario & Event Lab across country, sector, issuer, and portfolio scopes
- Long-term target-vs-reference repricing through climate-adjusted cash flows and present value
- Short-term NWS event nowcast translating hazard intensity, exposure beta, and vulnerability into tactical basis points
- Conditional scenario-tail matrix with no assigned occurrence probabilities and no claim of regulatory Expected Shortfall
- Point-in-time climate buy/sell walk-forward validation over 3 weeks, 3 months, and 3 years using the selected portfolio universe; 3 months is the default evidence window and 3 weeks is explicitly treated as a monitoring diagnostic
- Configurable trading and short-borrow costs with net and gross return, compounded cost drag, turnover, drawdown, hit rate, and information-ratio reporting
- Climate Signals, Data Lineage & Coverage view combining NWS, NASA GISTEMP, NOAA GML CO2, NCEI disasters, allocation transmission, source status, and known data gaps
- Explicit separation of observed inputs, calibrated proxies, and missing facility/revenue/supply-chain data
- Issuer analysis inside the same target-versus-reference Scenario Lab used for country, sector, and portfolio scopes
- Automatic climate universe ranked from market behavior, live climate conditions, sector transmission, issuer resilience, and conditional scenario loss
- Institutional, responsive UI focused on decision, attribution, risk budget, and validation rather than generic quote or chart screens

## Validation discipline

The validation view evaluates the same universe selected by the portfolio optimizer. Each historical signal date ranks assets using information available up to that date, applies the buy and sell sleeves for the next trading day, and deducts modeled trading and borrow costs. The 3-week result is directional, the 3-month result is the default tactical evidence window, and the 3-year result provides longer-horizon context.

Historical market features are point-in-time. Annual climate features use expanding-window normalization and the latest completed calendar-year vintage. The signal holds a 100% long sleeve and a 25% short sleeve, so its 75% net risky exposure is compared with a 75% equal-weight universe plus 25% cash. The prototype does not reconstruct a complete archived daily NWS alert tape or survivorship-free historical constituents. Reported results therefore remain research evidence rather than a production performance claim, and they exclude market impact, taxes, financing, and security-level locate constraints.

## U.S. Market Assumptions

- Uses U.S. tickers, sector ETFs, and USD portfolio sizing
- Does not use China A-share boards, daily price limits, 100-share lot rules, or China resale constraints
- Supports single-share/fractional-share style allocation logic
- Research prototype only; not live investment advice

## Scenario & Event Methodology

The platform now separates strategic climate valuation from tactical event risk:

- `Long-term`: choose a target and reference scenario. Country-level acute, chronic, and macro transition shocks are downscaled to sectors, then to issuers using transparent fixed-asset, labor-intensity, and earnings-sensitivity proxies. Climate-adjusted cash flows are discounted into an as-of-date value impact. Nonlinear DCF attribution uses exact four-factor Shapley values.
- `Short-term`: NWS event pressure is multiplied by the observed hazard mix and hazard-specific sector beta. The portfolio tilt is centered to be zero-sum around strategic weights and scaled so no holding moves more than 250 basis points in one daily overlay. No hazard mix means no tactical trade.
- `Scope`: the same chain can be read at country, sector, issuer, or current-portfolio level.
- `Scenario rule`: NGFS-style scenarios are conditional stresses, not forecasts. The model does not assign occurrence probabilities to them.
- `Tail rule`: the mean of the two largest portfolio scenario losses is labeled a scenario-tail proxy, not regulatory Expected Shortfall. It is kept separate from physical and transition pressure to avoid double counting.

The scenario paths, sector medians, and issuer vulnerability ratios in this prototype are documented, replaceable calibrations. They are not Bloomberg data. The former stand-alone issuer Monte Carlo module was removed because its distributional assumptions were not calibrated strongly enough to support precise P95/P99 claims. Issuer scope now uses the same auditable target-reference scenario engine as every other scope. A production implementation should replace issuer proxies with geolocated facilities, revenue segmentation, supply-chain links, and licensed NGFS or vendor scenario data.

The physical downscaling follows the structure described in the supplied Bloomberg methodology: sector loss equals country loss multiplied by sector vulnerability divided by the economy-weighted average vulnerability; issuer loss then applies a bounded issuer-to-sector vulnerability ratio. Covered-sector value-added weights reconcile the weighted sector multiplier to exactly `1.0`. The app exposes this check, portfolio-weight reconciliation, target/reference present values, and Shapley residuals in the Calculation Ledger.

## Portfolio Optimizer

The optimizer is designed for an asset-investor workflow:

- `ETF only`: builds diversified exposure from ETFs only
- `ETF + stock`: uses ETFs as the core sleeve and single stocks as satellite positions
- `Stock only`: allocates only across selected U.S.-listed companies
- `Short-term`: uses today's 1-minute intraday bars, momentum, volatility, liquidity, and the current climate alert overlay
- `Long-term`: uses recent daily trend, structural climate resilience, and target-versus-reference scenario loss
- `Balanced`: mixes market trend, climate score, and volatility control
- `Climate defense`: gives more weight to lower conditional climate loss and resilient sectors
- `Growth`: gives more weight to market momentum and single-name upside
- `Low volatility`: reduces high-volatility and high-tail-risk exposure

By default, the optimizer uses an automatic climate universe. It ranks climate-related ETFs and stocks from the daily climate relation signal, broad-market anchors, and sector physical/transition risk profiles. Advanced users can still override the ETF and stock candidate lists manually.

For each asset, the optimizer separates base alpha, climate alpha, volatility/confidence control, and conditional scenario-tail loss. Within each ETF or stock sleeve, it solves a bounded proportional allocation equivalent to maximizing `sum(priority_i * log(weight_i))` subject to the sleeve budget and effective confidence caps. The market-only ablation uses the same sleeves and caps, so climate active weight is directly comparable. Capital only converts the reconciled weight into target dollars and estimated shares.

The climate buy/sell backtest is a conditional walk-forward replay over the current optimizer-selected universe. Each historical signal date uses only information available before the next trading day, forms a climate-resilient buy book and a climate-vulnerable sell/underweight book, and compares the resulting overlay with an exposure-matched benchmark over 3-week, 3-month, and 3-year windows. Capital affects dollar sizing, while return evidence remains capital-independent.

## Climate Data Sources

- NASA GISTEMP land-ocean annual temperature anomaly CSV
- NOAA Global Monitoring Laboratory Mauna Loa monthly CO2 CSV
- NOAA National Centers for Environmental Information billion-dollar weather and climate disaster event JSON
- NWS active weather alerts for acute daily physical climate pressure
- FEMA National Risk Index, NASA FIRMS, AirNow, NOAA CPC/NWPS, EPA GHGRP, EPA eGRID, EIA Open Data, NGFS scenarios, and SEC EDGAR APIs as source-ready expansion points for richer physical and transition risk mapping

The app caches official climate data locally under `data/official_climate_data_cache.json` and falls back to built-in proxy values if an external source is unavailable.

## Install

```powershell
pip install -r requirements.txt
```

`yfinance`, `pandas`, and `numpy` are optional but recommended. If verified market data is unavailable or insufficient, portfolio validation is suppressed and labeled unavailable. The app does not substitute simulated prices or returns into client-facing performance.

## Run

```powershell
python app.py
```

Then open:

```text
http://127.0.0.1:8865
```
