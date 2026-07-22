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

- `Long-term`: choose a target and reference scenario. Country GDP and supply shocks pass through sector GDP/input-output betas and issuer earnings sensitivity. Acute and chronic physical losses are downscaled separately. Climate-adjusted FCFF is discounted with issuer/sector-specific WACC and terminal growth. Nonlinear attribution uses exact Shapley values across all disclosed cash-flow channels.
- `Transition cash flow`: atmospheric CO2 concentration is climate-state context, not a policy-risk input. Business-model transition risk is decomposed as `carbon cost + demand shift + energy cost + transition CapEx - pass-through`, with each channel shown separately in the valuation attribution.
- `Short-term`: each NWS hazard severity nowcast is multiplied by location exposure, hazard vulnerability, and one minus resilience. NWS alerts are not interpreted as disaster probabilities. The portfolio tilt is centered to be zero-sum around strategic weights and no holding moves more than 250 basis points. No hazard mix means no tactical trade.
- `Scope`: the same chain can be read at country, sector, issuer, or current-portfolio level.
- `Scenario rule`: NGFS-style scenarios are conditional stresses, not forecasts. The model does not assign occurrence probabilities to them.
- `Tail rule`: the mean of the two largest portfolio scenario losses is labeled a scenario-tail proxy, not regulatory Expected Shortfall. It is kept separate from physical and transition pressure to avoid double counting.
- `Model risk`: physical damage coefficients are rerun at `0.70x` and `1.30x`. The resulting range is a transparent sensitivity band, not a statistical confidence interval.

The scenario paths, sector medians, and issuer vulnerability ratios in this prototype are documented, replaceable calibrations. They are not Bloomberg data. The former stand-alone issuer Monte Carlo module was removed because its distributional assumptions were not calibrated strongly enough to support precise P95/P99 claims. Issuer scope now uses the same auditable target-reference scenario engine as every other scope. A production implementation should replace issuer proxies with geolocated facilities, revenue segmentation, supply-chain links, and licensed NGFS or vendor scenario data.

The physical downscaling follows the structure described in the supplied Bloomberg methodology: sector loss equals country loss multiplied by sector vulnerability divided by the economy-weighted average vulnerability; issuer loss then applies a bounded issuer-to-sector vulnerability ratio. Covered-sector value-added weights reconcile the weighted sector multiplier to exactly `1.0`. The app exposes this check, portfolio-weight reconciliation, target/reference present values, and Shapley residuals in the Calculation Ledger.

## Portfolio Optimizer

The optimizer is designed for an asset-investor workflow:

- `ETF only`: builds diversified exposure from ETFs only
- `ETF + stock`: uses ETFs as the core sleeve and single stocks as satellite positions
- `Stock only`: allocates only across selected U.S.-listed companies
- `Short-term`: starts from the strategic portfolio and applies a separate 1-20 trading-day market/event overlay
- `Long-term`: uses a one-year daily market history, structural physical/transition risk, and 5-30 year target-versus-reference cash-flow losses; current NWS alerts do not change strategic weights
- `Balanced`: balances expected return, covariance risk, scenario losses, tracking error, turnover, and explicit climate-risk budgets
- `Climate defense`: gives more weight to lower conditional climate loss and resilient sectors
- `Growth`: gives more weight to market momentum and single-name upside
- `Low volatility`: reduces high-volatility and high-tail-risk exposure

By default, the optimizer uses an automatic climate universe. It ranks climate-related ETFs and stocks from the daily climate relation signal, broad-market anchors, and sector physical/transition risk profiles. Advanced users can still override the ETF and stock candidate lists manually.

For each asset, the optimizer separates a market-derived expected-return signal from climate-risk indicators. Climate information is not assumed to be alpha. The strategic optimizer solves the disclosed robust objective

`max mu'w - lambda w'Sigma w - kappa max_s L_s(w) - eta (w-w_market)'Sigma(w-w_market) - tau ||w-w_market||_1`

subject to sleeve budgets, single-name and sector caps, liquidity/confidence limits, tracking error, maximum scenario loss, physical-risk, transition-risk, and carbon-cost budgets. At every projected-gradient iteration the solver identifies the current portfolio's worst conditional scenario and uses that scenario's loss vector as the subgradient. The final L1 term is active share versus the market-only reference, not realized turnover versus an uploaded prior portfolio. Capital only converts weights into target dollars and estimated shares.

The climate buy/sell backtest is a one-step walk-forward replay over the selected optimizer universe. Each historical signal date uses information available before the next trading day, forms climate-on and market-only buy/sell books with equal exposure and costs, and reports `IncrementalClimateValue = Performance_FullModel - Performance_MarketOnly`. It adds block-bootstrap intervals and a sign-permutation test. The current prototype still lacks a complete archived NWS tape, historical index constituents, delisted securities, and ALFRED macro vintages; these limitations are stated in the interface rather than hidden.

## Climate Data Sources

- NASA GISTEMP land-ocean annual temperature anomaly CSV
- NOAA Global Monitoring Laboratory Mauna Loa monthly CO2 CSV
- NOAA National Centers for Environmental Information billion-dollar weather and climate disaster event JSON
- NWS active weather alerts for acute daily physical climate pressure
- BEA GDP by Industry and Input-Output Accounts for country-to-sector and supply-chain transmission
- FRED/ALFRED for macroeconomic series and historical data vintages
- NOAA Storm Events for event calibration and NASA NEX-GDDP-CMIP6 for downscaled future hazard paths
- FEMA National Risk Index, NASA FIRMS, AirNow, NOAA CPC/NWPS, EPA GHGRP/eGRID, EIA Open Data, NGFS scenarios, and SEC EDGAR APIs as source-ready expansion points

The app caches official climate data locally under `data/official_climate_data_cache.json` and falls back to built-in proxy values if an external source is unavailable.

NOAA CO2 observations are displayed as climate context only and are explicitly excluded from the transition-risk score. Transition channels currently use disclosed sector calibrations when issuer-level NGFS, EIA, EPA eGRID/GHGRP, and SEC financial inputs are unavailable; the UI identifies that fallback rather than inventing a live policy signal.

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
