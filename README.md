# Jenneson Climate-Finance Trading & Risk Platform

English U.S.-listed climate-finance research cockpit inspired by the earlier China trading dashboard, but rebuilt for the U.S. market system.

## What It Does

- U.S.-listed sector ETF allocation dashboard
- Client climate-intelligence summary with physical pressure, transition pressure, an independent scenario-tail guardrail, data confidence, affected holdings, and suggested action
- Interactive Scenario & Event Lab with country, sector, issuer, and portfolio scopes
- Long-term target-vs-reference repricing through cash-flow and present-value impacts
- Short-term NWS event nowcast that converts hazard intensity, exposure, and vulnerability into tactical basis points
- Daily climate-alert overlay that moves current ETF allocation from NWS active weather alerts
- Climate signal from temperature anomaly and weather disaster frequency proxies
- Dedicated Climate Data Center with live, official, and source-ready physical/transition data inputs
- Climate buy/sell walk-forward backtest over 3 weeks, 3 months, and 3 years using the optimizer-selected universe
- Conditional portfolio scenario stress matrix with no claimed scenario occurrence probabilities
- Company-level issuer scanner for market CVaR and climate value-at-risk components
- U.S. listed company search from NasdaqTrader listings
- Method 2 Climate VaR approximation for each queried issuer
- BAU vs 2C mitigation comparison for issuer-level Method 2 CVOR
- Data quality labels explaining when market cap, sector, beta, or growth data are inferred
- Current U.S. stock and ETF quote board
- Professional TradingView-style K-line chart with high-DPI candles, crosshair OHLC readout, volume, MA20, EMA50, VWAP, Bollinger Bands, RSI/MACD, fit, dark mode, and PNG snapshot export
- Rolling K-line chart with a Today 1-minute intraday mode plus 5D, 1M, 3M, 6M, 1Y, and 2Y windows
- Faster market refresh for the intraday K-line view
- ETF watchlist across core index, sector, rates/credit, climate/clean energy, and commodities
- Portfolio optimizer with ETF-only, ETF + stock, and stock-only construction modes
- Optimizer controls for capital size, short-term vs long-term holding period, and style selection
- Automatic optimizer universe that ranks climate-related ETFs and stocks from the current daily climate signal, with optional advanced custom ticker override
- Optimizer output with target weight, target dollars, estimated shares, market score, physical risk, transition risk, climate score, and action
- Official climate data inputs from NASA GISTEMP, NOAA GML CO2, and NOAA NCEI billion-dollar disaster events
- Current climate data panel combining daily NWS alerts with official NASA/NOAA/NCEI inputs plus FEMA, NASA FIRMS, AirNow, NOAA CPC/NWPS, EPA GHGRP, EPA eGRID, EIA, NGFS, and SEC EDGAR source mapping
- Dedicated daily climate intelligence board linking current alerts to related stocks, ETF recommendations, and daily reminders
- Stock and ETF climate-relevance scoring from NWS alert type, alert intensity, market momentum, and climate exposure mapping
- Auto-refreshing market and climate allocation views for a cleaner investor cockpit
- Left-side section navigation for a China-platform-like trading cockpit workflow
- Market and issuer CVOR heat strips for faster visual scanning
- High-DPI chart rendering, responsive tables, and desktop/mobile layout scaling
- Plain-English client explanation panel

## U.S. Market Assumptions

- Uses U.S. tickers, sector ETFs, and USD portfolio sizing
- Does not use China A-share boards, daily price limits, 100-share lot rules, or China resale constraints
- Supports single-share/fractional-share style allocation logic
- Research prototype only; not live investment advice

## Method 2 Alignment

The issuer CVOR scanner follows the logic of Dietz, Bowen, Dixon and Gradwell (2016), "Climate value at risk of global financial assets":

- Compare the present value of a no-climate-damage cash-flow path with a climate-damaged path
- Express Climate VaR as the PV loss divided by the no-damage PV
- Use private-investor discounting rather than social discounting
- Use a DICE-style damage function: `g(T)=0.0028*T^2+(alpha3*T)^7`
- Sample uncertainty in productivity growth, climate sensitivity, and damage curvature
- Report mean, P95, P99, and CVOR95 tail expected loss for each issuer
- Report how much a 2C pathway reduces issuer P95/CVOR95 climate-impact risk
- Use current official climate inputs to set the current warming level and climate pressure multiplier

This is still a company-level approximation because true Method 2 DICE runs are global and require full IAM scenario paths. The platform maps the global method to U.S. issuers through sector sensitivity, beta, market capitalization, and available growth data.

## Scenario & Event Methodology

The platform now separates strategic climate valuation from tactical event risk:

- `Long-term`: choose a target and reference scenario. Country-level acute, chronic, and macro transition shocks are downscaled to sectors, then to issuers using transparent fixed-asset, labor-intensity, and earnings-sensitivity proxies. Climate-adjusted cash flows are discounted into an as-of-date value impact.
- `Short-term`: NWS alert intensity is combined with hazard-specific sector exposure and issuer vulnerability. The output is event selection risk and a tactical portfolio overlay in basis points.
- `Scope`: the same chain can be read at country, sector, issuer, or current-portfolio level.
- `Scenario rule`: NGFS-style scenarios are conditional stresses, not forecasts. The model does not assign occurrence probabilities to them.
- `Tail rule`: the mean of the two largest portfolio scenario losses is labeled a scenario-tail proxy, not regulatory Expected Shortfall. It is kept separate from physical and transition pressure to avoid double counting.

The scenario paths, sector medians, and issuer vulnerability ratios in this prototype are documented, replaceable calibrations. They are not Bloomberg data. A production implementation should replace issuer proxies with geolocated facilities, revenue segmentation, supply-chain links, and licensed NGFS or vendor scenario data.

## Portfolio Optimizer

The optimizer is designed for an asset-investor workflow:

- `ETF only`: builds diversified exposure from ETFs only
- `ETF + stock`: uses ETFs as the core sleeve and single stocks as satellite positions
- `Stock only`: allocates only across selected U.S.-listed companies
- `Short-term`: uses today's 1-minute intraday bars, momentum, volatility, liquidity, and the current climate alert overlay
- `Long-term`: uses recent daily trend, structural climate resilience, and Method 2 issuer CVOR
- `Balanced`: mixes market trend, climate score, and volatility control
- `Climate defense`: gives more weight to lower Climate VaR and resilient sectors
- `Growth`: gives more weight to market momentum and single-name upside
- `Low volatility`: reduces high-volatility and high-tail-risk exposure

By default, the optimizer uses an automatic climate universe. It ranks climate-related ETFs and stocks from the daily climate relation signal, broad-market anchors, and sector physical/transition risk profiles. Advanced users can still override the ETF and stock candidate lists manually.

For each asset, the optimizer estimates a score from market behavior, physical climate risk, transition risk, Method 2/CVOR proxy, and volatility, then converts it into a portfolio weight. It multiplies the weight by the selected capital amount to show target dollars and estimated shares.

The climate buy/sell backtest is a walk-forward test over the current optimizer-selected universe. Each historical signal date uses only information available before the next trading day, forms a climate-resilient buy book and a climate-vulnerable sell/underweight book, and compares the resulting overlay with the equal-weight universe over 3-week, 3-month, and 3-year windows. Capital affects dollar sizing, while return evidence remains capital-independent.

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

`yfinance`, `pandas`, and `numpy` are optional but recommended. If market data is unavailable, the app falls back to deterministic simulated returns so the dashboard still runs.

## Run

```powershell
python app.py
```

Then open:

```text
http://127.0.0.1:8865
```
