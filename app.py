# -*- coding: utf-8 -*-
"""
Jennison Climate-Finance Trading & Risk Platform

Local client-facing prototype inspired by the existing China A-share dashboard.
Run:
    python app.py
Open:
    http://127.0.0.1:8865
"""

from __future__ import annotations

import json
import math
import random
import sys
import threading
import time
import webbrowser
import csv
import io
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

try:
    import numpy as np
    import pandas as pd
except Exception:  # pragma: no cover
    np = None
    pd = None

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None


PROJECT_DIR = Path(__file__).parent
DATA_DIR = PROJECT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

PORT = 8865
DEFAULT_PORTFOLIO_VALUE = 50_000_000
START_YEAR = 2009
CURRENT_YEAR = datetime.now().year
METHOD2_END_YEAR = 2100
METHOD2_DRAWS = 900
METHOD2_DISCOUNT_RATE = 0.0407
METHOD2_DISCOUNT_SPREAD = 0.0036
METHOD2_ALPHA2 = 0.0028
METHOD2_ALPHA3_MAX = 0.248
CURRENT_WARMING_C = 1.28

NASDAQ_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_LISTED_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
UNIVERSE_CACHE = DATA_DIR / "us_listed_universe_cache.json"
NASA_GISTEMP_CSV_URL = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
NOAA_CO2_CSV_URL = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv"
NCEI_BILLION_EVENTS_JSON_URL = "https://www.ncei.noaa.gov/monitoring-content/billions/data/events.json"
CLIMATE_DATA_CACHE = DATA_DIR / "official_climate_data_cache.json"
NWS_ACTIVE_ALERTS_URL = "https://api.weather.gov/alerts/active?status=actual&message_type=alert"
DAILY_CLIMATE_CACHE = DATA_DIR / "daily_climate_alerts_cache.json"
NWS_USER_AGENT = "JennisonClimateFinancePrototype/1.0 (local research)"
DAILY_RECO_BACKTEST_CACHE = DATA_DIR / "daily_recommendation_backtest_cache.json"
FEMA_NRI_URL = "https://www.fema.gov/flood-maps/products-tools/national-risk-index"
FEMA_NRI_DATA_URL = "https://www.fema.gov/about/openfema/data-sets/national-risk-index-data"
NASA_FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/"
AIRNOW_API_URL = "https://docs.airnowapi.org/"
NOAA_CPC_URL = "https://www.cpc.ncep.noaa.gov/"
NOAA_WATER_API_URL = "https://water.noaa.gov/about/api"
NOAA_STORM_EVENTS_URL = "https://www.ncei.noaa.gov/stormevents/"
EPA_GHGRP_URL = "https://www.epa.gov/ghgreporting/ghgrp-reported-data"
EPA_EGRID_URL = "https://www.epa.gov/egrid"
EIA_OPEN_DATA_URL = "https://www.eia.gov/opendata/"
NGFS_SCENARIOS_URL = "https://www.ngfs.net/ngfs-scenarios-portal/"
SEC_EDGAR_API_URL = "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"


SECTOR_ETFS = {
    "XLE": {
        "name": "Energy",
        "physical": 0.65,
        "transition": 0.95,
        "resilience": 0.25,
        "client_note": "Transition exposure and carbon-policy sensitivity are high.",
    },
    "XLU": {
        "name": "Utilities",
        "physical": 0.75,
        "transition": 0.55,
        "resilience": 0.60,
        "client_note": "Physical risk is high, but regulated cash-flow resilience can help.",
    },
    "XLI": {
        "name": "Industrials",
        "physical": 0.58,
        "transition": 0.62,
        "resilience": 0.42,
        "client_note": "Supply-chain and infrastructure exposure create mixed climate risk.",
    },
    "XLK": {
        "name": "Technology",
        "physical": 0.28,
        "transition": 0.32,
        "resilience": 0.82,
        "client_note": "Asset-light and adaptive, but data-center energy intensity matters.",
    },
    "XLF": {
        "name": "Financials",
        "physical": 0.42,
        "transition": 0.50,
        "resilience": 0.55,
        "client_note": "Climate risk enters through credit, insurance, and asset exposure.",
    },
}


ETF_WATCHLIST = {
    "Core Index": ["SPY", "QQQ", "DIA", "IWM"],
    "Sector SPDR": ["XLK", "XLE", "XLF", "XLU", "XLI", "XLV", "XLY", "XLP"],
    "Rates / Credit": ["TLT", "IEF", "LQD", "HYG"],
    "Climate / Clean Energy": ["ICLN", "QCLN", "TAN", "PBW"],
    "Commodities": ["GLD", "SLV", "USO", "UNG"],
}


DEFAULT_OPTIMIZER_ETFS = ["SPY", "QQQ", "XLK", "XLF", "XLU", "XLE", "ICLN"]
DEFAULT_OPTIMIZER_STOCKS = ["AAPL", "MSFT", "NVDA", "JPM", "XOM", "NEE"]


OPTIMIZER_STYLES = {
    "balanced": {
        "label": "Balanced",
        "market_weight": 0.42,
        "climate_weight": 0.38,
        "risk_weight": 0.20,
        "stock_sleeve": 0.42,
        "note": "Blend market momentum, climate risk, and volatility control.",
    },
    "climate_defense": {
        "label": "Climate defense",
        "market_weight": 0.24,
        "climate_weight": 0.56,
        "risk_weight": 0.20,
        "stock_sleeve": 0.32,
        "note": "Prioritize lower climate VaR and stronger resilience.",
    },
    "growth": {
        "label": "Growth",
        "market_weight": 0.56,
        "climate_weight": 0.24,
        "risk_weight": 0.20,
        "stock_sleeve": 0.52,
        "note": "Allow more stock concentration when momentum is strong.",
    },
    "low_vol": {
        "label": "Low volatility",
        "market_weight": 0.28,
        "climate_weight": 0.32,
        "risk_weight": 0.40,
        "stock_sleeve": 0.28,
        "note": "Favor smoother holdings and reduce volatile single-name exposure.",
    },
}


OPTIMIZER_MODE_LABELS = {
    "etf_only": "ETF only",
    "etf_stock": "ETF + stock",
    "stock_only": "Stock only",
}


COMPANY_SECTOR_SENSITIVITY = {
    "Energy": 0.92,
    "Utilities": 0.70,
    "Industrials": 0.62,
    "Technology": 0.36,
    "Financial Services": 0.54,
    "Financials": 0.54,
    "Consumer Cyclical": 0.48,
    "Consumer Defensive": 0.38,
    "Healthcare": 0.34,
    "Basic Materials": 0.72,
    "Real Estate": 0.68,
    "Communication Services": 0.40,
}


SECTOR_TRANSITION_FACTORS = {
    "Energy": {
        "emissions": 0.94,
        "policy": 0.90,
        "carbon_price": 0.96,
        "transition_opportunity": 0.18,
        "headline": "High fossil fuel, methane, and carbon-price sensitivity.",
    },
    "Utilities": {
        "emissions": 0.78,
        "policy": 0.76,
        "carbon_price": 0.74,
        "transition_opportunity": 0.62,
        "headline": "Grid mix, reliability capex, and clean-power transition matter.",
    },
    "Industrials": {
        "emissions": 0.62,
        "policy": 0.58,
        "carbon_price": 0.60,
        "transition_opportunity": 0.42,
        "headline": "Supply chain, process heat, transport, and infrastructure capex.",
    },
    "Technology": {
        "emissions": 0.30,
        "policy": 0.34,
        "carbon_price": 0.28,
        "transition_opportunity": 0.70,
        "headline": "Asset-light, but data-center power demand and grid emissions matter.",
    },
    "Financial Services": {
        "emissions": 0.42,
        "policy": 0.56,
        "carbon_price": 0.46,
        "transition_opportunity": 0.46,
        "headline": "Transition risk enters through credit, insurance, and financed exposure.",
    },
    "Financials": {
        "emissions": 0.42,
        "policy": 0.56,
        "carbon_price": 0.46,
        "transition_opportunity": 0.46,
        "headline": "Transition risk enters through credit, insurance, and financed exposure.",
    },
    "Consumer Cyclical": {
        "emissions": 0.44,
        "policy": 0.42,
        "carbon_price": 0.38,
        "transition_opportunity": 0.44,
        "headline": "Consumer demand, logistics, and product energy intensity.",
    },
    "Consumer Defensive": {
        "emissions": 0.38,
        "policy": 0.36,
        "carbon_price": 0.34,
        "transition_opportunity": 0.36,
        "headline": "Agriculture, packaging, logistics, and water stress are key channels.",
    },
    "Healthcare": {
        "emissions": 0.28,
        "policy": 0.30,
        "carbon_price": 0.26,
        "transition_opportunity": 0.32,
        "headline": "Lower direct transition beta, with supply-chain and facility exposure.",
    },
    "Basic Materials": {
        "emissions": 0.82,
        "policy": 0.72,
        "carbon_price": 0.80,
        "transition_opportunity": 0.36,
        "headline": "High process emissions and commodity transition sensitivity.",
    },
    "Real Estate": {
        "emissions": 0.52,
        "policy": 0.62,
        "carbon_price": 0.48,
        "transition_opportunity": 0.38,
        "headline": "Building standards, insurance, and energy-efficiency capex.",
    },
    "Communication Services": {
        "emissions": 0.30,
        "policy": 0.32,
        "carbon_price": 0.28,
        "transition_opportunity": 0.48,
        "headline": "Lower direct exposure, with power and data-center links.",
    },
}


# Transparent prototype calibrations for the scenario lab. These are not licensed
# Bloomberg or NGFS output values; they preserve the target-vs-reference workflow
# and can be replaced with official scenario paths without changing the analytics.
CLIMATE_SCENARIO_PATHS = {
    "baseline": {
        "label": "Climate-agnostic baseline",
        "category": "Reference",
        "warming_2100": 1.30,
        "acute_gdp_loss_2050": 0.000,
        "chronic_gdp_loss_2050": 0.000,
        "macro_transition_loss_2050": 0.000,
        "transition_demand_shock_2050": 0.000,
        "carbon_price_label": "None",
        "note": "Counterfactual reference path with no modeled climate damage or transition shock.",
    },
    "net_zero_2050": {
        "label": "Net Zero 2050",
        "category": "Orderly",
        "warming_2100": 1.40,
        "acute_gdp_loss_2050": 0.018,
        "chronic_gdp_loss_2050": 0.012,
        "macro_transition_loss_2050": 0.022,
        "transition_demand_shock_2050": 0.180,
        "carbon_price_label": "High / early",
        "note": "Lower physical losses, with material near-term transition risks and opportunities.",
    },
    "below_2c": {
        "label": "Below 2C",
        "category": "Orderly",
        "warming_2100": 1.70,
        "acute_gdp_loss_2050": 0.024,
        "chronic_gdp_loss_2050": 0.018,
        "macro_transition_loss_2050": 0.012,
        "transition_demand_shock_2050": 0.105,
        "carbon_price_label": "Moderate / early",
        "note": "Moderate transition pressure and lower long-run physical damage.",
    },
    "delayed_transition": {
        "label": "Delayed Transition",
        "category": "Disorderly",
        "warming_2100": 1.70,
        "acute_gdp_loss_2050": 0.030,
        "chronic_gdp_loss_2050": 0.022,
        "macro_transition_loss_2050": 0.032,
        "transition_demand_shock_2050": 0.205,
        "carbon_price_label": "High / late",
        "note": "A late policy shock creates sharper repricing and execution risk.",
    },
    "current_policies": {
        "label": "Current Policies",
        "category": "Hot House World",
        "warming_2100": 2.90,
        "acute_gdp_loss_2050": 0.060,
        "chronic_gdp_loss_2050": 0.045,
        "macro_transition_loss_2050": 0.004,
        "transition_demand_shock_2050": 0.025,
        "carbon_price_label": "Low",
        "note": "Limited transition shock, but materially higher acute and chronic physical losses.",
    },
    "fragmented_world": {
        "label": "Fragmented World",
        "category": "Too little, too late",
        "warming_2100": 2.30,
        "acute_gdp_loss_2050": 0.050,
        "chronic_gdp_loss_2050": 0.036,
        "macro_transition_loss_2050": 0.028,
        "transition_demand_shock_2050": 0.160,
        "carbon_price_label": "Uneven",
        "note": "Elevated physical losses combine with an inefficient, regionally fragmented transition.",
    },
}


# Relative vulnerability factors follow the top-down logic in the uploaded
# Bloomberg methodology: acute risk scales with physical capital intensity,
# chronic heat risk with labor intensity, and macro transition with earnings beta.
SECTOR_DOWNSCALING_FACTORS = {
    "Real Estate": {"fixed_asset": 0.82, "labor": 0.16, "macro_beta": 0.82},
    "Utilities": {"fixed_asset": 0.68, "labor": 0.22, "macro_beta": 0.58},
    "Energy": {"fixed_asset": 0.62, "labor": 0.18, "macro_beta": 0.92},
    "Basic Materials": {"fixed_asset": 0.52, "labor": 0.42, "macro_beta": 1.02},
    "Consumer Defensive": {"fixed_asset": 0.44, "labor": 0.58, "macro_beta": 0.55},
    "Consumer Cyclical": {"fixed_asset": 0.40, "labor": 0.78, "macro_beta": 1.22},
    "Industrials": {"fixed_asset": 0.36, "labor": 0.66, "macro_beta": 1.05},
    "Healthcare": {"fixed_asset": 0.29, "labor": 1.00, "macro_beta": 0.62},
    "Technology": {"fixed_asset": 0.25, "labor": 0.88, "macro_beta": 0.86},
    "Communication Services": {"fixed_asset": 0.27, "labor": 0.46, "macro_beta": 0.84},
    "Financial Services": {"fixed_asset": 0.08, "labor": 0.36, "macro_beta": 0.90},
    "Financials": {"fixed_asset": 0.08, "labor": 0.36, "macro_beta": 0.90},
}


ISSUER_VULNERABILITY_OVERRIDES = {
    "AAPL": {"acute_ratio": 0.84, "chronic_ratio": 0.72, "quality": "Issuer proxy"},
    "MSFT": {"acute_ratio": 0.80, "chronic_ratio": 0.68, "quality": "Issuer proxy"},
    "NVDA": {"acute_ratio": 0.78, "chronic_ratio": 0.62, "quality": "Issuer proxy"},
    "XOM": {"acute_ratio": 1.18, "chronic_ratio": 0.78, "quality": "Issuer proxy"},
    "CVX": {"acute_ratio": 1.15, "chronic_ratio": 0.80, "quality": "Issuer proxy"},
    "NEE": {"acute_ratio": 1.10, "chronic_ratio": 0.86, "quality": "Issuer proxy"},
    "DUK": {"acute_ratio": 1.12, "chronic_ratio": 0.88, "quality": "Issuer proxy"},
    "JPM": {"acute_ratio": 0.74, "chronic_ratio": 0.92, "quality": "Issuer proxy"},
    "TRV": {"acute_ratio": 0.82, "chronic_ratio": 0.94, "quality": "Issuer proxy"},
    "CB": {"acute_ratio": 0.80, "chronic_ratio": 0.92, "quality": "Issuer proxy"},
}


HAZARD_SECTOR_BETAS = {
    "heat": {"Energy": 0.66, "Utilities": 0.92, "Industrials": 0.76, "Technology": 0.44, "Financials": 0.28, "Financial Services": 0.28, "Consumer Cyclical": 0.55, "Consumer Defensive": 0.60, "Healthcare": 0.58, "Basic Materials": 0.78, "Real Estate": 0.54, "Communication Services": 0.38},
    "flood": {"Energy": 0.82, "Utilities": 0.90, "Industrials": 0.86, "Technology": 0.35, "Financials": 0.76, "Financial Services": 0.76, "Consumer Cyclical": 0.64, "Consumer Defensive": 0.70, "Healthcare": 0.55, "Basic Materials": 0.80, "Real Estate": 0.96, "Communication Services": 0.46},
    "fire": {"Energy": 0.72, "Utilities": 0.98, "Industrials": 0.64, "Technology": 0.34, "Financials": 0.72, "Financial Services": 0.72, "Consumer Cyclical": 0.48, "Consumer Defensive": 0.58, "Healthcare": 0.52, "Basic Materials": 0.74, "Real Estate": 0.88, "Communication Services": 0.42},
    "tropical": {"Energy": 0.94, "Utilities": 0.96, "Industrials": 0.90, "Technology": 0.38, "Financials": 0.84, "Financial Services": 0.84, "Consumer Cyclical": 0.72, "Consumer Defensive": 0.74, "Healthcare": 0.62, "Basic Materials": 0.82, "Real Estate": 0.96, "Communication Services": 0.50},
    "storm": {"Energy": 0.78, "Utilities": 0.90, "Industrials": 0.82, "Technology": 0.38, "Financials": 0.72, "Financial Services": 0.72, "Consumer Cyclical": 0.62, "Consumer Defensive": 0.66, "Healthcare": 0.58, "Basic Materials": 0.76, "Real Estate": 0.86, "Communication Services": 0.48},
    "air_quality": {"Energy": 0.52, "Utilities": 0.58, "Industrials": 0.62, "Technology": 0.34, "Financials": 0.24, "Financial Services": 0.24, "Consumer Cyclical": 0.42, "Consumer Defensive": 0.44, "Healthcare": 0.72, "Basic Materials": 0.64, "Real Estate": 0.38, "Communication Services": 0.30},
    "winter": {"Energy": 0.72, "Utilities": 0.88, "Industrials": 0.68, "Technology": 0.32, "Financials": 0.30, "Financial Services": 0.30, "Consumer Cyclical": 0.48, "Consumer Defensive": 0.52, "Healthcare": 0.50, "Basic Materials": 0.66, "Real Estate": 0.48, "Communication Services": 0.34},
}


HAZARD_WEIGHTS = {
    "heat": 0.18,
    "flood": 0.19,
    "fire": 0.16,
    "tropical": 0.18,
    "storm": 0.14,
    "air_quality": 0.08,
    "winter": 0.07,
}


CLIMATE_DATA_SOURCE_CATALOG = [
    {
        "name": "NWS Active Alerts",
        "risk_type": "Acute physical",
        "status": "Live / cached",
        "url": NWS_ACTIVE_ALERTS_URL,
        "client_use": "Today's heat, flood, fire, tropical storm, severe storm, winter, and air-quality alert pulse.",
    },
    {
        "name": "NASA GISTEMP",
        "risk_type": "Chronic physical",
        "status": "Official / cached",
        "url": NASA_GISTEMP_CSV_URL,
        "client_use": "Current warming input and long-run temperature pressure.",
    },
    {
        "name": "NOAA GML CO2",
        "risk_type": "Transition pressure",
        "status": "Official / cached",
        "url": NOAA_CO2_CSV_URL,
        "client_use": "Atmospheric CO2 trend used as a transition-pressure and policy-lag indicator.",
    },
    {
        "name": "NOAA NCEI Billion-Dollar Disasters",
        "risk_type": "Physical loss history",
        "status": "Official / cached",
        "url": NCEI_BILLION_EVENTS_JSON_URL,
        "client_use": "Disaster frequency and loss proxy for chronic U.S. physical-risk calibration.",
    },
    {
        "name": "FEMA National Risk Index",
        "risk_type": "Baseline physical",
        "status": "Source-ready",
        "url": FEMA_NRI_DATA_URL,
        "client_use": "County and tract hazard baseline for future issuer facility/geographic mapping.",
    },
    {
        "name": "NASA FIRMS",
        "risk_type": "Wildfire / smoke",
        "status": "Source-ready",
        "url": NASA_FIRMS_URL,
        "client_use": "Near-real-time satellite active-fire signal for wildfire-sensitive issuers.",
    },
    {
        "name": "AirNow",
        "risk_type": "Air quality",
        "status": "API-ready",
        "url": AIRNOW_API_URL,
        "client_use": "AQI and PM2.5 smoke data for health, labor, logistics, and regional disruption risk.",
    },
    {
        "name": "NOAA CPC / NWPS",
        "risk_type": "Forecast physical",
        "status": "Source-ready",
        "url": NOAA_CPC_URL,
        "client_use": "Drought, temperature, precipitation, and flood outlooks for 1-12 week risk framing.",
    },
    {
        "name": "EPA GHGRP",
        "risk_type": "Transition emissions",
        "status": "Source-ready",
        "url": EPA_GHGRP_URL,
        "client_use": "Facility-level emissions for issuer transition-risk mapping.",
    },
    {
        "name": "EPA eGRID",
        "risk_type": "Power-sector transition",
        "status": "Source-ready",
        "url": EPA_EGRID_URL,
        "client_use": "Electricity generation mix and emission rates for utilities and data-center power exposure.",
    },
    {
        "name": "EIA Open Data",
        "risk_type": "Energy transition",
        "status": "API-ready",
        "url": EIA_OPEN_DATA_URL,
        "client_use": "Energy prices, generation mix, demand, fuel use, and emissions series.",
    },
    {
        "name": "NGFS Scenarios",
        "risk_type": "Scenario transition",
        "status": "Scenario-ready",
        "url": NGFS_SCENARIOS_URL,
        "client_use": "Orderly, disorderly, and hot-house pathways for carbon-price and macro transition shocks.",
    },
    {
        "name": "SEC EDGAR APIs",
        "risk_type": "Disclosure / regulation",
        "status": "API-ready",
        "url": SEC_EDGAR_API_URL,
        "client_use": "Issuer filings, climate-risk language, capex, insurance, and regulatory disclosure signals.",
    },
]


CLIMATE_PROXY = [
    # year, NASA-like global temperature anomaly proxy, NOAA billion-dollar disaster frequency proxy
    (2008, 0.54, 12),
    (2009, 0.64, 10),
    (2010, 0.72, 13),
    (2011, 0.60, 16),
    (2012, 0.65, 11),
    (2013, 0.68, 10),
    (2014, 0.75, 13),
    (2015, 0.90, 15),
    (2016, 1.02, 16),
    (2017, 0.93, 17),
    (2018, 0.85, 14),
    (2019, 0.98, 14),
    (2020, 1.02, 22),
    (2021, 0.86, 20),
    (2022, 0.89, 18),
    (2023, 1.18, 28),
    (2024, 1.28, 27),
    (2025, 1.22, 24),
    (2026, 1.26, 25),
]


CLIMATE_SCENARIOS = [
    {
        "name": "Orderly Transition",
        "physical_shock": 0.035,
        "transition_shock": 0.055,
        "litigation_shock": 0.010,
        "carbon_price": 75,
        "narrative": "Gradual policy tightening, higher carbon prices, manageable physical losses.",
    },
    {
        "name": "Disorderly Transition",
        "physical_shock": 0.060,
        "transition_shock": 0.120,
        "litigation_shock": 0.025,
        "carbon_price": 145,
        "narrative": "Late policy action reprices carbon-intensive sectors quickly.",
    },
    {
        "name": "Hot House World",
        "physical_shock": 0.155,
        "transition_shock": 0.035,
        "litigation_shock": 0.030,
        "carbon_price": 35,
        "narrative": "Weak policy response, stronger heat, flood, wildfire, and storm losses.",
    },
    {
        "name": "Liability Shock",
        "physical_shock": 0.070,
        "transition_shock": 0.080,
        "litigation_shock": 0.090,
        "carbon_price": 110,
        "narrative": "Climate disclosure, insurance, and legal liability risk reprices issuers.",
    },
]


US_MARKET_NOTES = [
    "Universe uses U.S.-listed common stocks and sector ETFs with USD allocations.",
    "No China A-share 100-share lot rule is used; fractional or single-share sizing can be modeled.",
    "U.S. equities currently settle on T+1, but this is not the same as China-style T+1 resale restrictions.",
    "The prototype does not model PDT, margin, options, borrow fees, taxes, or live execution routing.",
]


EXCHANGE_MAP = {
    "Q": "NASDAQ",
    "N": "NYSE",
    "A": "NYSE American",
    "P": "NYSE Arca",
    "Z": "Cboe BZX",
    "V": "IEX",
}


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except Exception:
        return default


def zscores(values):
    vals = [safe_float(v, 0.0) for v in values]
    if not vals:
        return []
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / max(1, len(vals) - 1)
    std = math.sqrt(var)
    if std <= 1e-12:
        return [0.0 for _ in vals]
    return [(v - mean) / std for v in vals]


def clamp(value, low, high):
    return max(low, min(high, value))


def percentile(values, q):
    vals = sorted([safe_float(v, 0.0) for v in values])
    if not vals:
        return 0.0
    idx = min(len(vals) - 1, max(0, int(round((len(vals) - 1) * q))))
    return vals[idx]


def yahoo_symbol(symbol):
    return str(symbol).strip().upper().replace(".", "-")


def parse_pipe_rows(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    headers = lines[0].split("|")
    rows = []
    for line in lines[1:]:
        if line.startswith("File Creation Time"):
            continue
        parts = line.split("|")
        if len(parts) != len(headers):
            continue
        rows.append(dict(zip(headers, parts)))
    return rows


def download_text(url, timeout=12, headers=None):
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def read_cached_official_climate_data(max_age_days=7):
    if CLIMATE_DATA_CACHE.exists():
        age_days = (time.time() - CLIMATE_DATA_CACHE.stat().st_mtime) / 86400
        if age_days <= max_age_days:
            try:
                cached = json.loads(CLIMATE_DATA_CACHE.read_text(encoding="utf-8"))
                cached["source_mode"] = "cached official climate data"
                return cached
            except Exception:
                pass
    return None


def parse_nasa_gistemp(text):
    lines = [line for line in text.splitlines() if line.strip()]
    if lines and lines[0].lower().startswith("land-ocean"):
        lines = lines[1:]
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    rows = {}
    for row in reader:
        try:
            year = int(row.get("Year", ""))
            annual = row.get("J-D", "").strip()
            if annual and annual != "***":
                rows[year] = float(annual)
        except Exception:
            continue
    return rows


def parse_noaa_co2(text):
    usable = [line for line in text.splitlines() if line.strip() and not line.startswith("#")]
    reader = csv.DictReader(io.StringIO("\n".join(usable)))
    by_year = {}
    for row in reader:
        try:
            year = int(row.get("year", ""))
            avg = float(row.get("average", "nan"))
            if avg > 0:
                by_year.setdefault(year, []).append(avg)
        except Exception:
            continue
    return {year: sum(vals) / len(vals) for year, vals in by_year.items() if vals}


def parse_ncei_disasters(text):
    raw = json.loads(text)
    counts = {}
    cost_proxy = {}
    for event in raw.values():
        try:
            beg = str(event.get("begDate", ""))
            year = int(beg[:4])
        except Exception:
            continue
        counts[year] = counts.get(year, 0) + 1
        low = safe_float(event.get("lower95"), 0)
        high = safe_float(event.get("upper95"), low)
        midpoint = (low + high) / 2 if high else low
        cost_proxy[year] = cost_proxy.get(year, 0) + midpoint
    return counts, cost_proxy


def fallback_climate_maps():
    temp = {year: anomaly for year, anomaly, _ in CLIMATE_PROXY}
    disasters = {year: count for year, _, count in CLIMATE_PROXY}
    co2 = {}
    for year in sorted(temp):
        co2[year] = 370 + max(0, year - 2000) * 2.35
    return temp, co2, disasters, {}


def load_official_climate_data(force_refresh=False):
    if not force_refresh:
        cached = read_cached_official_climate_data()
        if cached:
            return cached

    fallback_temp, fallback_co2, fallback_disasters, fallback_costs = fallback_climate_maps()
    source_notes = []
    try:
        temp_map = parse_nasa_gistemp(download_text(NASA_GISTEMP_CSV_URL, timeout=18))
        source_notes.append("NASA GISTEMP land-ocean annual temperature anomaly")
    except Exception:
        temp_map = fallback_temp
        source_notes.append("fallback temperature proxy")

    try:
        co2_map = parse_noaa_co2(download_text(NOAA_CO2_CSV_URL, timeout=18))
        source_notes.append("NOAA GML Mauna Loa monthly CO2")
    except Exception:
        co2_map = fallback_co2
        source_notes.append("fallback CO2 proxy")

    try:
        disaster_map, cost_map = parse_ncei_disasters(download_text(NCEI_BILLION_EVENTS_JSON_URL, timeout=25))
        source_notes.append("NOAA NCEI billion-dollar weather and climate disasters")
    except Exception:
        disaster_map, cost_map = fallback_disasters, fallback_costs
        source_notes.append("fallback disaster-frequency proxy")

    years = sorted(set(temp_map) | set(co2_map) | set(disaster_map))
    rows = []
    last_temp = None
    last_temp_year = None
    last_co2 = None
    last_co2_year = None
    for year in years:
        if year < 1980:
            continue
        temp = temp_map.get(year)
        temp_year = year if temp is not None else last_temp_year
        if temp is None:
            temp = last_temp if last_temp is not None else fallback_temp.get(year)
        else:
            last_temp = temp
            last_temp_year = year
        co2 = co2_map.get(year)
        co2_year = year if co2 is not None else last_co2_year
        if co2 is None:
            co2 = last_co2 if last_co2 is not None else fallback_co2.get(year)
        if co2 is not None:
            last_co2 = co2
            last_co2_year = year
        disasters = disaster_map.get(year)
        disaster_year = year if disasters is not None else None
        if disasters is None and source_notes[-1].startswith("fallback"):
            disasters = fallback_disasters.get(year, 0)
            disaster_year = year
        cost = cost_map.get(year, fallback_costs.get(year, 0))
        if temp is None and co2 is None and not disasters:
            continue
        rows.append(
            {
                "year": year,
                "temperature_anomaly": round(safe_float(temp, 0), 3),
                "temperature_year": temp_year,
                "temperature_source": "official" if temp_year == year else "official carry-forward",
                "co2_ppm": round(safe_float(co2, 0), 2),
                "co2_year": co2_year,
                "co2_source": "official" if co2_year == year else "official carry-forward",
                "billion_dollar_disasters": int(disasters) if disasters is not None else None,
                "disaster_year": disaster_year,
                "disaster_source": "official" if disaster_year == year else "not yet available",
                "disaster_cost_proxy": round(safe_float(cost, 0), 2),
            }
        )

    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_mode": "official climate data",
        "source_notes": source_notes,
        "source_urls": {
            "nasa_gistemp": NASA_GISTEMP_CSV_URL,
            "noaa_co2": NOAA_CO2_CSV_URL,
            "ncei_disasters": NCEI_BILLION_EVENTS_JSON_URL,
        },
        "rows": rows,
    }
    try:
        CLIMATE_DATA_CACHE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return payload


def climate_data_context():
    data = load_official_climate_data()
    rows = data.get("rows", [])
    if not rows:
        return {
            "current_warming": CURRENT_WARMING_C,
            "latest_year": CURRENT_YEAR,
            "co2_ppm": 420.0,
            "co2_10y_change": 20.0,
            "disaster_10y_avg": 18.0,
            "climate_pressure_multiplier": 1.0,
            "source_mode": "fallback",
        }
    latest = rows[-1]
    disaster_rows = [r for r in rows if r.get("billion_dollar_disasters") is not None]
    recent = disaster_rows[-10:] if len(disaster_rows) >= 10 else disaster_rows
    prior_idx = max(0, len(rows) - 11)
    prior = rows[prior_idx]
    disaster_10y_avg = sum(r.get("billion_dollar_disasters", 0) for r in recent) / max(1, len(recent))
    co2_change = safe_float(latest.get("co2_ppm"), 0) - safe_float(prior.get("co2_ppm"), 0)
    temp = safe_float(latest.get("temperature_anomaly"), CURRENT_WARMING_C)
    multiplier = 1.0 + clamp((temp - 1.0) * 0.12, -0.04, 0.10) + clamp((co2_change - 20) * 0.004, -0.04, 0.08) + clamp((disaster_10y_avg - 15) * 0.01, -0.03, 0.08)
    return {
        "current_warming": round(max(0.75, temp), 3),
        "latest_year": latest.get("year", CURRENT_YEAR),
        "co2_ppm": latest.get("co2_ppm", 0),
        "co2_10y_change": round(co2_change, 2),
        "disaster_10y_avg": round(disaster_10y_avg, 2),
        "climate_pressure_multiplier": round(clamp(multiplier, 0.85, 1.30), 4),
        "source_mode": data.get("source_mode", "official climate data"),
        "source_notes": data.get("source_notes", []),
        "source_urls": data.get("source_urls", {}),
    }


DAILY_ALERT_CATEGORY_WEIGHTS = {
    "heat": 1.45,
    "flood": 1.30,
    "fire": 1.35,
    "tropical": 1.60,
    "storm": 1.10,
    "winter": 0.55,
    "air_quality": 0.75,
}


CLIMATE_CATEGORY_LABELS = {
    "heat": "Heat",
    "flood": "Flood",
    "fire": "Wildfire",
    "tropical": "Tropical storm",
    "storm": "Severe storm",
    "winter": "Winter weather",
    "air_quality": "Air quality",
}


DAILY_CLIMATE_STOCKS = [
    {
        "ticker": "NEE",
        "name": "NextEra Energy",
        "theme": "Power grid / renewables",
        "stance": "mixed",
        "exposure": {"heat": 0.86, "storm": 0.52, "tropical": 0.46, "fire": 0.28},
        "note": "Power demand and grid reliability become more important during climate stress.",
    },
    {
        "ticker": "DUK",
        "name": "Duke Energy",
        "theme": "Regulated utilities",
        "stance": "risk",
        "exposure": {"heat": 0.78, "storm": 0.62, "tropical": 0.50, "winter": 0.34},
        "note": "Utilities face demand spikes, outage risk, and storm restoration costs.",
    },
    {
        "ticker": "XOM",
        "name": "Exxon Mobil",
        "theme": "Energy / Gulf infrastructure",
        "stance": "risk",
        "exposure": {"heat": 0.52, "tropical": 0.76, "storm": 0.35, "air_quality": 0.42},
        "note": "Energy infrastructure is sensitive to storms and transition headlines.",
    },
    {
        "ticker": "JPM",
        "name": "JPMorgan Chase",
        "theme": "Credit / financial exposure",
        "stance": "mixed",
        "exposure": {"flood": 0.45, "storm": 0.42, "fire": 0.30, "tropical": 0.40},
        "note": "Climate data can flow into credit, insurance, and regional loan exposure.",
    },
    {
        "ticker": "TRV",
        "name": "Travelers",
        "theme": "Property insurance",
        "stance": "risk",
        "exposure": {"flood": 0.82, "fire": 0.76, "storm": 0.88, "tropical": 0.74},
        "note": "Severe weather can increase catastrophe claims and reserve pressure.",
    },
    {
        "ticker": "CB",
        "name": "Chubb",
        "theme": "Insurance / catastrophe risk",
        "stance": "risk",
        "exposure": {"flood": 0.76, "fire": 0.68, "storm": 0.80, "tropical": 0.70},
        "note": "Catastrophe risk, pricing, and claims sensitivity rise with active alerts.",
    },
    {
        "ticker": "CAT",
        "name": "Caterpillar",
        "theme": "Infrastructure / rebuild",
        "stance": "beneficiary",
        "exposure": {"flood": 0.48, "storm": 0.54, "fire": 0.32, "tropical": 0.40},
        "note": "Disaster recovery and infrastructure spending can support demand.",
    },
    {
        "ticker": "DE",
        "name": "Deere",
        "theme": "Agriculture equipment",
        "stance": "risk",
        "exposure": {"heat": 0.62, "flood": 0.52, "winter": 0.28, "storm": 0.24},
        "note": "Crop conditions, drought, flood, and farm-income expectations matter.",
    },
    {
        "ticker": "FSLR",
        "name": "First Solar",
        "theme": "Solar / transition",
        "stance": "beneficiary",
        "exposure": {"heat": 0.58, "air_quality": 0.36, "storm": 0.18},
        "note": "Climate pressure can support clean-energy and grid-transition narratives.",
    },
    {
        "ticker": "ENPH",
        "name": "Enphase Energy",
        "theme": "Distributed solar",
        "stance": "beneficiary",
        "exposure": {"heat": 0.52, "fire": 0.30, "air_quality": 0.35, "storm": 0.22},
        "note": "Distributed power and resilience themes can become more relevant.",
    },
    {
        "ticker": "MSFT",
        "name": "Microsoft",
        "theme": "Data centers / power demand",
        "stance": "mixed",
        "exposure": {"heat": 0.34, "storm": 0.18, "air_quality": 0.18},
        "note": "Data-center power load and adaptation spending link climate to mega-cap tech.",
    },
    {
        "ticker": "NVDA",
        "name": "NVIDIA",
        "theme": "AI infrastructure",
        "stance": "mixed",
        "exposure": {"heat": 0.30, "storm": 0.14, "air_quality": 0.14},
        "note": "Climate relevance is indirect through power demand and infrastructure buildout.",
    },
]


DAILY_CLIMATE_ETFS = [
    {"ticker": "XLU", "role": "Utilities stress / resilience", "stance": "mixed", "exposure": {"heat": 0.82, "storm": 0.62, "tropical": 0.50, "winter": 0.32}},
    {"ticker": "XLE", "role": "Energy infrastructure risk", "stance": "risk", "exposure": {"heat": 0.52, "tropical": 0.78, "storm": 0.36, "air_quality": 0.42}},
    {"ticker": "XLF", "role": "Credit and insurance channel", "stance": "mixed", "exposure": {"flood": 0.50, "storm": 0.46, "fire": 0.34, "tropical": 0.42}},
    {"ticker": "XLI", "role": "Infrastructure / supply chain", "stance": "mixed", "exposure": {"flood": 0.44, "storm": 0.50, "fire": 0.30, "tropical": 0.34}},
    {"ticker": "XLK", "role": "Power demand / adaptive tech", "stance": "beneficiary", "exposure": {"heat": 0.34, "storm": 0.18, "air_quality": 0.18}},
    {"ticker": "ICLN", "role": "Clean-energy transition", "stance": "beneficiary", "exposure": {"heat": 0.56, "air_quality": 0.48, "storm": 0.18}},
    {"ticker": "TAN", "role": "Solar transition", "stance": "beneficiary", "exposure": {"heat": 0.60, "air_quality": 0.46, "fire": 0.22}},
    {"ticker": "QCLN", "role": "Clean tech / EV", "stance": "beneficiary", "exposure": {"heat": 0.42, "air_quality": 0.50, "storm": 0.16}},
    {"ticker": "GLD", "role": "Macro hedge", "stance": "hedge", "exposure": {"storm": 0.24, "flood": 0.24, "tropical": 0.24, "fire": 0.22, "heat": 0.18}},
    {"ticker": "TLT", "role": "Duration / risk-off hedge", "stance": "hedge", "exposure": {"storm": 0.20, "flood": 0.20, "tropical": 0.18, "fire": 0.18, "heat": 0.14}},
]


def read_cached_daily_climate_signal(max_age_hours=3):
    if DAILY_CLIMATE_CACHE.exists():
        age_hours = (time.time() - DAILY_CLIMATE_CACHE.stat().st_mtime) / 3600
        if age_hours <= max_age_hours:
            try:
                cached = json.loads(DAILY_CLIMATE_CACHE.read_text(encoding="utf-8"))
                cached["source_mode"] = "cached NWS active alerts"
                return cached
            except Exception:
                pass
    return None


def classify_nws_alert(event):
    text = str(event or "").lower()
    categories = []
    if "heat" in text:
        categories.append("heat")
    if "flood" in text or "hydrologic" in text:
        categories.append("flood")
    if "fire" in text or "red flag" in text:
        categories.append("fire")
    if "hurricane" in text or "tropical" in text or "storm surge" in text:
        categories.append("tropical")
    if "thunderstorm" in text or "tornado" in text or "wind" in text or "dust storm" in text:
        categories.append("storm")
    if "winter" in text or "blizzard" in text or "snow" in text or "ice" in text or "freeze" in text:
        categories.append("winter")
    if "air quality" in text or "ozone" in text:
        categories.append("air_quality")
    return categories or ["other"]


def severity_weight(severity):
    return {
        "Extreme": 1.80,
        "Severe": 1.45,
        "Moderate": 1.10,
        "Minor": 0.75,
        "Unknown": 0.90,
    }.get(str(severity or "Unknown"), 0.90)


def fallback_daily_climate_signal():
    context = climate_data_context()
    pressure = clamp((context["climate_pressure_multiplier"] - 0.90) / 0.40, 0.0, 1.0)
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_mode": "fallback daily climate pulse",
        "source_url": NWS_ACTIVE_ALERTS_URL,
        "alerts_total": 0,
        "climate_alerts": 0,
        "weighted_alert_score": 0.0,
        "daily_pressure": round(pressure, 4),
        "allocation_pressure": round(pressure * 0.55, 4),
        "top_driver": "long-run climate pressure",
        "category_counts": {k: 0 for k in DAILY_ALERT_CATEGORY_WEIGHTS},
        "category_intensity": {k: 0.0 for k in DAILY_ALERT_CATEGORY_WEIGHTS},
        "sample_events": [],
    }


def load_daily_climate_signal(force_refresh=False):
    if not force_refresh:
        cached = read_cached_daily_climate_signal()
        if cached:
            return cached

    try:
        text = download_text(
            NWS_ACTIVE_ALERTS_URL,
            timeout=18,
            headers={"User-Agent": NWS_USER_AGENT, "Accept": "application/geo+json"},
        )
        raw = json.loads(text)
        features = raw.get("features", [])
        category_counts = {k: 0 for k in DAILY_ALERT_CATEGORY_WEIGHTS}
        category_scores = {k: 0.0 for k in DAILY_ALERT_CATEGORY_WEIGHTS}
        samples = []
        weighted_score = 0.0
        climate_alerts = 0

        for feature in features:
            props = feature.get("properties", {}) if isinstance(feature, dict) else {}
            event = props.get("event", "")
            categories = [c for c in classify_nws_alert(event) if c in DAILY_ALERT_CATEGORY_WEIGHTS]
            if not categories:
                continue
            climate_alerts += 1
            sev = severity_weight(props.get("severity"))
            primary = max(categories, key=lambda c: DAILY_ALERT_CATEGORY_WEIGHTS[c])
            event_score = sev * DAILY_ALERT_CATEGORY_WEIGHTS[primary]
            weighted_score += event_score
            category_counts[primary] += 1
            category_scores[primary] += event_score
            if len(samples) < 5:
                samples.append(
                    {
                        "event": event,
                        "category": primary,
                        "severity": props.get("severity", "Unknown"),
                        "area": str(props.get("areaDesc", ""))[:90],
                    }
                )

        daily_pressure = clamp(math.log1p(weighted_score) / math.log1p(260), 0.0, 1.0)
        context = climate_data_context()
        long_run_pressure = clamp((context["climate_pressure_multiplier"] - 0.90) / 0.40, 0.0, 1.0)
        allocation_pressure = clamp(0.72 * daily_pressure + 0.28 * long_run_pressure, 0.0, 1.0)
        top_driver = max(category_scores.items(), key=lambda kv: kv[1])[0] if weighted_score > 0 else "none"
        category_intensity = {
            k: round(clamp(v / max(1.0, weighted_score), 0.0, 1.0), 4)
            for k, v in category_scores.items()
        }
        payload = {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source_mode": "NWS active weather alerts",
            "source_url": NWS_ACTIVE_ALERTS_URL,
            "alerts_total": len(features),
            "climate_alerts": climate_alerts,
            "weighted_alert_score": round(weighted_score, 3),
            "daily_pressure": round(daily_pressure, 4),
            "allocation_pressure": round(allocation_pressure, 4),
            "top_driver": top_driver,
            "category_counts": category_counts,
            "category_intensity": category_intensity,
            "sample_events": samples,
        }
        DAILY_CLIMATE_CACHE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload
    except Exception:
        return fallback_daily_climate_signal()


def apply_daily_climate_overlay(latest_alloc, daily_signal):
    if not latest_alloc:
        return []
    pressure = safe_float(daily_signal.get("allocation_pressure"), 0.0)
    categories = daily_signal.get("category_intensity", {})
    physical_load = clamp(
        0.24 * safe_float(categories.get("heat"), 0.0)
        + 0.22 * safe_float(categories.get("flood"), 0.0)
        + 0.21 * safe_float(categories.get("fire"), 0.0)
        + 0.25 * safe_float(categories.get("tropical"), 0.0)
        + 0.16 * safe_float(categories.get("storm"), 0.0)
        + 0.06 * safe_float(categories.get("winter"), 0.0),
        0.0,
        1.0,
    )
    transition_load = clamp(0.30 * pressure + 0.20 * safe_float(categories.get("air_quality"), 0.0), 0.0, 1.0)
    row_scores = []
    for row in latest_alloc:
        ticker = row["ticker"]
        meta = SECTOR_ETFS.get(ticker, {})
        sector_stress = (
            0.58 * safe_float(meta.get("physical"), 0.50) * max(pressure, physical_load)
            + 0.25 * safe_float(meta.get("transition"), 0.50) * transition_load
            + 0.17 * (1 - safe_float(meta.get("resilience"), 0.50)) * max(pressure, physical_load)
        )
        adaptive_score = safe_float(meta.get("resilience"), 0.50) - sector_stress
        row_scores.append((row, sector_stress, adaptive_score))

    mean_score = sum(score for _, _, score in row_scores) / max(1, len(row_scores))
    raw_weights = {}
    for row, sector_stress, adaptive_score in row_scores:
        long_weight = safe_float(row.get("climate_weight"), 0.0)
        multiplier = clamp(1 + 0.36 * pressure * (adaptive_score - mean_score), 0.72, 1.28)
        raw_weights[row["ticker"]] = max(0.025, long_weight * multiplier)
    total = sum(raw_weights.values()) or 1.0

    adjusted = []
    for row, sector_stress, adaptive_score in row_scores:
        out = dict(row)
        long_weight = safe_float(row.get("climate_weight"), 0.0)
        final_weight = raw_weights[row["ticker"]] / total
        out["base_climate_weight"] = round(long_weight, 4)
        out["climate_weight"] = round(final_weight, 4)
        out["target_dollars"] = round(final_weight * DEFAULT_PORTFOLIO_VALUE, 2)
        out["long_term_adjustment_bps"] = int(round((long_weight - safe_float(row.get("benchmark_weight"), 0.0)) * 10000))
        out["daily_adjustment_bps"] = int(round((final_weight - long_weight) * 10000))
        out["total_adjustment_bps"] = int(round((final_weight - safe_float(row.get("benchmark_weight"), 0.0)) * 10000))
        out["daily_sector_stress"] = round(sector_stress, 4)
        out["daily_adaptive_score"] = round(adaptive_score, 4)
        out["daily_driver"] = (
            f"{daily_signal.get('top_driver', 'daily')} alert pulse; "
            f"sector stress {sector_stress:.2f}, resilience {safe_float(SECTOR_ETFS.get(row['ticker'], {}).get('resilience'), 0.0):.2f}"
        )
        out["action"] = allocation_action(final_weight, safe_float(row.get("benchmark_weight"), 0.0))
        adjusted.append(out)
    return adjusted


def fallback_us_universe():
    rows = [
        ("AAPL", "Apple Inc. Common Stock", "NASDAQ", False),
        ("MSFT", "Microsoft Corporation Common Stock", "NASDAQ", False),
        ("NVDA", "NVIDIA Corporation Common Stock", "NASDAQ", False),
        ("AMZN", "Amazon.com Inc. Common Stock", "NASDAQ", False),
        ("GOOGL", "Alphabet Inc. Class A Common Stock", "NASDAQ", False),
        ("META", "Meta Platforms Inc. Class A Common Stock", "NASDAQ", False),
        ("TSLA", "Tesla Inc. Common Stock", "NASDAQ", False),
        ("JPM", "JPMorgan Chase & Co. Common Stock", "NYSE", False),
        ("XOM", "Exxon Mobil Corporation Common Stock", "NYSE", False),
        ("CVX", "Chevron Corporation Common Stock", "NYSE", False),
        ("NEE", "NextEra Energy Inc. Common Stock", "NYSE", False),
        ("CAT", "Caterpillar Inc. Common Stock", "NYSE", False),
        ("XLE", "Energy Select Sector SPDR Fund", "NYSE Arca", True),
        ("XLK", "Technology Select Sector SPDR Fund", "NYSE Arca", True),
    ]
    return [
        {
            "symbol": s,
            "name": n,
            "exchange": e,
            "is_etf": is_etf,
            "security_type": "ETF" if is_etf else "Common Stock",
            "source": "fallback",
        }
        for s, n, e, is_etf in rows
    ]


def load_us_listed_universe(force_refresh=False):
    if not force_refresh and UNIVERSE_CACHE.exists():
        age_days = (time.time() - UNIVERSE_CACHE.stat().st_mtime) / 86400
        if age_days <= 7:
            try:
                return json.loads(UNIVERSE_CACHE.read_text(encoding="utf-8"))
            except Exception:
                pass

    universe = []
    try:
        nasdaq_rows = parse_pipe_rows(download_text(NASDAQ_LISTED_URL))
        for row in nasdaq_rows:
            if row.get("Test Issue", "N") != "N":
                continue
            symbol = row.get("Symbol", "").strip()
            if not symbol:
                continue
            is_etf = row.get("ETF", "N") == "Y"
            universe.append(
                {
                    "symbol": symbol,
                    "name": row.get("Security Name", symbol).strip(),
                    "exchange": "NASDAQ",
                    "is_etf": is_etf,
                    "security_type": "ETF" if is_etf else "Common Stock",
                    "source": "nasdaqtrader",
                }
            )

        other_rows = parse_pipe_rows(download_text(OTHER_LISTED_URL))
        for row in other_rows:
            if row.get("Test Issue", "N") != "N":
                continue
            symbol = row.get("ACT Symbol", "").strip()
            if not symbol:
                continue
            is_etf = row.get("ETF", "N") == "Y"
            exchange = EXCHANGE_MAP.get(row.get("Exchange", ""), row.get("Exchange", "Other"))
            universe.append(
                {
                    "symbol": symbol,
                    "name": row.get("Security Name", symbol).strip(),
                    "exchange": exchange,
                    "is_etf": is_etf,
                    "security_type": "ETF" if is_etf else "Common Stock",
                    "source": "nasdaqtrader",
                }
            )
    except Exception:
        universe = fallback_us_universe()

    deduped = {}
    for row in universe:
        symbol = row["symbol"]
        if symbol not in deduped:
            deduped[symbol] = row
    out = sorted(deduped.values(), key=lambda r: (r["is_etf"], r["symbol"]))
    try:
        UNIVERSE_CACHE.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return out


def search_us_universe(query="", limit=80, include_etfs=False):
    query = str(query or "").strip().upper()
    limit = int(clamp(safe_float(limit, 80), 1, 500))
    rows = load_us_listed_universe()
    if not include_etfs:
        rows = [r for r in rows if not r.get("is_etf")]
    if query:
        tokens = [t for t in query.replace(",", " ").split() if t]
        def matches(row):
            haystack = f"{row.get('symbol','')} {row.get('name','')} {row.get('exchange','')}".upper()
            return all(t in haystack for t in tokens)
        rows = [r for r in rows if matches(r)]
    return rows[:limit]


def climate_signal():
    official = load_official_climate_data()
    source_rows = official.get("rows", [])
    if not source_rows:
        years = [r[0] for r in CLIMATE_PROXY]
        temps = [r[1] for r in CLIMATE_PROXY]
        disasters = [r[2] for r in CLIMATE_PROXY]
        co2 = [0 for _ in years]
        costs = [0 for _ in years]
    else:
        source_rows = [r for r in source_rows if r.get("year", 0) >= 1980 and r.get("billion_dollar_disasters") is not None]
        years = [r["year"] for r in source_rows]
        temps = [r.get("temperature_anomaly", 0) for r in source_rows]
        disasters = [r.get("billion_dollar_disasters", 0) for r in source_rows]
        co2 = [r.get("co2_ppm", 0) for r in source_rows]
        costs = [r.get("disaster_cost_proxy", 0) for r in source_rows]
    zt = zscores(temps)
    zd = zscores(disasters)
    zc = zscores(co2)
    zk = zscores(costs)
    score = [0.40 * a + 0.20 * b + 0.25 * c + 0.15 * k for a, b, c, k in zip(zt, zd, zc, zk)]
    threshold = percentile(score, 0.75)
    rows = []
    for i, year in enumerate(years):
        state = "High Climate Risk" if score[i] >= threshold else "Normal Climate Risk"
        rows.append(
            {
                "year": year,
                "temperature_anomaly": round(temps[i], 3),
                "co2_ppm": round(co2[i], 2),
                "disaster_frequency": disasters[i],
                "disaster_cost_proxy": round(costs[i], 2),
                "temperature_z": round(zt[i], 3),
                "co2_z": round(zc[i], 3),
                "disaster_z": round(zd[i], 3),
                "cost_z": round(zk[i], 3),
                "climate_risk_score": round(score[i], 3),
                "risk_state": state,
                "top_quartile_threshold": round(threshold, 3),
            }
        )
    return rows


def regime_for_year(year, climate_rows):
    lookup = {r["year"]: r for r in climate_rows}
    prev = lookup.get(year - 1) or lookup.get(max(lookup))
    high = prev and prev["risk_state"] == "High Climate Risk"
    return {
        "allocation_year": year,
        "signal_year": prev["year"] if prev else year - 1,
        "regime": "High Climate Risk" if high else "Normal Climate Risk",
        "score": prev["climate_risk_score"] if prev else 0,
    }


def climate_weight_policy(regime):
    tickers = list(SECTOR_ETFS.keys())
    base = {t: 1 / len(tickers) for t in tickers}
    if regime != "High Climate Risk":
        return base
    raw = {}
    for ticker, meta in SECTOR_ETFS.items():
        risk = 0.55 * meta["physical"] + 0.45 * meta["transition"]
        resilience = meta["resilience"]
        raw[ticker] = max(0.05, 1.0 + 0.65 * resilience - 0.90 * risk)
    total = sum(raw.values())
    return {k: v / total for k, v in raw.items()}


def sector_climate_loss_rate(meta, scenario):
    physical = scenario["physical_shock"] * meta["physical"]
    transition = scenario["transition_shock"] * meta["transition"]
    litigation = scenario["litigation_shock"] * (1 - meta["resilience"])
    gross = physical + transition + litigation
    resilience_offset = 0.030 * meta["resilience"]
    return max(0.0, gross - resilience_offset)


def climate_scenario_matrix(allocation_rows):
    if not allocation_rows:
        return [], {}
    latest_year = max(r["year"] for r in allocation_rows)
    latest_alloc = [r for r in allocation_rows if r["year"] == latest_year]
    weights = {r["ticker"]: safe_float(r["climate_weight"]) for r in latest_alloc}
    rows = []
    scenario_losses = []
    for scenario in CLIMATE_SCENARIOS:
        sector_losses = {}
        portfolio_loss = 0.0
        for ticker, meta in SECTOR_ETFS.items():
            loss = sector_climate_loss_rate(meta, scenario)
            sector_losses[ticker] = round(loss, 4)
            portfolio_loss += weights.get(ticker, 0.0) * loss
        scenario_losses.append(portfolio_loss)
        rows.append(
            {
                "scenario": scenario["name"],
                "scenario_type": "Conditional stress",
                "carbon_price": scenario["carbon_price"],
                "portfolio_loss_rate": round(portfolio_loss, 4),
                "portfolio_loss_dollars": round(portfolio_loss * DEFAULT_PORTFOLIO_VALUE, 2),
                "sector_losses": sector_losses,
                "narrative": scenario["narrative"],
            }
        )
    average_loss = sum(scenario_losses) / max(1, len(scenario_losses))
    worst_loss = max(scenario_losses, default=0.0)
    sorted_rows = sorted(rows, key=lambda r: r["portfolio_loss_rate"], reverse=True)
    tail = sorted_rows[:2]
    scenario_tail = sum(r["portfolio_loss_rate"] for r in tail) / max(1, len(tail))
    summary = {
        "average_scenario_loss_rate": round(average_loss, 4),
        "average_scenario_loss_dollars": round(average_loss * DEFAULT_PORTFOLIO_VALUE, 2),
        "expected_climate_loss_rate": round(average_loss, 4),
        "expected_climate_loss_dollars": round(average_loss * DEFAULT_PORTFOLIO_VALUE, 2),
        "worst_scenario_loss_rate": round(worst_loss, 4),
        "worst_scenario_loss_dollars": round(worst_loss * DEFAULT_PORTFOLIO_VALUE, 2),
        "scenario_tail_loss_rate": round(scenario_tail, 4),
        "scenario_tail_loss_dollars": round(scenario_tail * DEFAULT_PORTFOLIO_VALUE, 2),
        "cvor_95_loss_rate": round(scenario_tail, 4),
        "cvor_95_loss_dollars": round(scenario_tail * DEFAULT_PORTFOLIO_VALUE, 2),
        "scenario_probability_method": "No occurrence probabilities assigned. Results are conditional scenario stresses; tail proxy is the mean of the two largest scenario losses.",
        "tail_label": "Scenario tail proxy - not regulatory Expected Shortfall",
    }
    return rows, summary


def method2_damage_fraction(temp_c, alpha3):
    # Dietz et al. Method 2 uses D_t = 1 / (1 + g(T_t)).
    # The loss share is therefore 1 - D_t, with g(T) = alpha2*T^2 + (alpha3*T)^7.
    g_t = METHOD2_ALPHA2 * (temp_c ** 2) + ((alpha3 * temp_c) ** 7)
    return 1 - (1 / (1 + g_t))


def method2_temperature_path(step, steps, target_warming, current_warming=CURRENT_WARMING_C):
    progress = step / max(1, steps)
    return current_warming + (target_warming - current_warming) * (progress ** 1.15)


def method2_loss_pct_for_path(steps, cashflow_growth, discount_rate, target_warming, alpha3, company_exposure, current_warming):
    pv_no_damage = 0.0
    pv_climate_damage = 0.0
    cashflow_no_damage = 1.0
    for step in range(1, steps + 1):
        cashflow_no_damage *= 1 + cashflow_growth
        temp = method2_temperature_path(step, steps, target_warming, current_warming=current_warming)
        global_damage = method2_damage_fraction(temp, alpha3)
        issuer_damage = clamp(global_damage * company_exposure, 0.0, 0.75)
        discount = (1 + discount_rate) ** step
        pv_no_damage += cashflow_no_damage / discount
        pv_climate_damage += (cashflow_no_damage * (1 - issuer_damage)) / discount
    return max(0.0, (pv_no_damage - pv_climate_damage) / max(1e-12, pv_no_damage))


def summarize_method2_losses(losses, market_cap):
    losses = sorted(losses)
    mean_loss = sum(losses) / max(1, len(losses))
    p95 = percentile(losses, 0.95)
    p99 = percentile(losses, 0.99)
    tail = [x for x in losses if x >= p95] or [p95]
    tail_mean = sum(tail) / len(tail)
    return {
        "mean_pct": round(mean_loss, 4),
        "p95_pct": round(p95, 4),
        "p99_pct": round(p99, 4),
        "cvor95_pct": round(tail_mean, 4),
        "mean_dollars": round(mean_loss * market_cap, 2),
        "cvor95_dollars": round(tail_mean * market_cap, 2),
    }


def method2_data_quality(info):
    score = 20
    notes = []
    if info.get("marketCap"):
        score += 25
    else:
        notes.append("market cap fallback")
    if info.get("sector"):
        score += 20
    else:
        notes.append("sector inferred")
    if info.get("beta") is not None:
        score += 15
    else:
        notes.append("beta fallback")
    if info.get("revenueGrowth") is not None or info.get("earningsGrowth") is not None:
        score += 15
    else:
        notes.append("growth fallback")
    if info.get("shortName") or info.get("longName"):
        score += 5
    return {
        "score": int(clamp(score, 0, 100)),
        "label": "High" if score >= 80 else ("Medium" if score >= 55 else "Low"),
        "notes": ", ".join(notes) if notes else "market data available",
    }


def method2_company_cvor(ticker, info=None, draws=METHOD2_DRAWS, end_year=METHOD2_END_YEAR):
    info = info or {}
    context = climate_data_context()
    symbol = yahoo_symbol(ticker)
    sector = info.get("sector") or guess_sector(symbol)
    sensitivity = COMPANY_SECTOR_SENSITIVITY.get(sector, 0.50)
    market_cap = safe_float(info.get("marketCap"), fallback_market_cap(symbol))
    beta = safe_float(info.get("beta"), 1.0)
    revenue_growth = safe_float(info.get("revenueGrowth"), 0.0)
    earnings_growth = safe_float(info.get("earningsGrowth"), 0.0)
    growth_signal = revenue_growth if abs(revenue_growth) > 1e-6 else earnings_growth
    growth_signal = clamp(growth_signal, -0.05, 0.08)
    steps = max(20, int(end_year - CURRENT_YEAR))
    rng = random.Random(sum(ord(c) for c in symbol) + 2100)
    bau_losses = []
    mitigation_losses = []

    for _ in range(int(draws)):
        tfp_growth = clamp(rng.gauss(0.0084, 0.0059), -0.006, 0.026)
        cashflow_growth = clamp(0.024 + tfp_growth + 0.18 * growth_signal, 0.004, 0.060)
        climate_sensitivity = clamp(rng.lognormvariate(math.log(2.9) - 0.5 * (0.38 ** 2), 0.38), 0.75, 6.0)
        bau_target_warming = clamp(2.5 * climate_sensitivity / 2.9 * context["climate_pressure_multiplier"], max(context["current_warming"], 1.35), 5.95)
        mitigation_target_warming = min(bau_target_warming, clamp(2.0 * climate_sensitivity / 2.9, max(1.10, context["current_warming"] * 0.95), 3.35))
        alpha3 = rng.uniform(0.0, METHOD2_ALPHA3_MAX)
        discount_rate = clamp(METHOD2_DISCOUNT_RATE + 0.006 * (beta - 1.0), 0.025, 0.075)
        company_exposure = clamp((0.42 + 0.92 * sensitivity + 0.14 * max(0.0, beta - 1.0)) * context["climate_pressure_multiplier"], 0.28, 1.95)
        bau_losses.append(method2_loss_pct_for_path(steps, cashflow_growth, discount_rate, bau_target_warming, alpha3, company_exposure, context["current_warming"]))
        mitigation_losses.append(method2_loss_pct_for_path(steps, cashflow_growth, discount_rate, mitigation_target_warming, alpha3, company_exposure, context["current_warming"]))

    bau = summarize_method2_losses(bau_losses, market_cap)
    mitigation = summarize_method2_losses(mitigation_losses, market_cap)
    quality = method2_data_quality(info)
    return {
        "method2_mean_pct": bau["mean_pct"],
        "method2_p95_pct": bau["p95_pct"],
        "method2_p99_pct": bau["p99_pct"],
        "method2_cvor95_pct": bau["cvor95_pct"],
        "method2_mean_dollars": bau["mean_dollars"],
        "method2_cvor95_dollars": bau["cvor95_dollars"],
        "method2_2c_mean_pct": mitigation["mean_pct"],
        "method2_2c_p95_pct": mitigation["p95_pct"],
        "method2_2c_p99_pct": mitigation["p99_pct"],
        "method2_2c_cvor95_pct": mitigation["cvor95_pct"],
        "method2_2c_cvor95_dollars": mitigation["cvor95_dollars"],
        "method2_p95_reduction_pct": round(max(0.0, bau["p95_pct"] - mitigation["p95_pct"]), 4),
        "method2_cvor95_reduction_pct": round(max(0.0, bau["cvor95_pct"] - mitigation["cvor95_pct"]), 4),
        "method2_market_cap": round(market_cap, 2),
        "method2_discount_rate": round(clamp(METHOD2_DISCOUNT_RATE + 0.006 * (beta - 1.0), 0.025, 0.075), 4),
        "method2_horizon_year": end_year,
        "method2_draws": int(draws),
        "method2_sector": sector,
        "method2_sector_sensitivity": round(sensitivity, 3),
        "method2_current_warming": context["current_warming"],
        "method2_climate_data_year": context["latest_year"],
        "method2_co2_ppm": context["co2_ppm"],
        "method2_disaster_10y_avg": context["disaster_10y_avg"],
        "method2_climate_pressure_multiplier": context["climate_pressure_multiplier"],
        "method2_climate_source_mode": context["source_mode"],
        "method2_data_quality_score": quality["score"],
        "method2_data_quality_label": quality["label"],
        "method2_data_quality_notes": quality["notes"],
        "method2_note": "PV loss from climate-damaged cash-flow path vs no-damage counterfactual, based on Dietz et al. Method 2. The 2C path excludes mitigation costs, matching climate-impact VaR rather than net transition-cost PV.",
    }


def fetch_etf_prices(tickers, start=f"{START_YEAR}-01-01"):
    cache = DATA_DIR / "etf_prices_cache.json"
    if yf is not None:
        try:
            data = yf.download(tickers, start=start, auto_adjust=True, progress=False, threads=True)
            if data is not None and not data.empty:
                close = data["Close"] if "Close" in data.columns else data
                if hasattr(close, "dropna"):
                    annual = {}
                    for t in tickers:
                        series = close[t].dropna() if t in close else close.dropna()
                        if len(series) > 30:
                            yearly = series.resample("YE").last().pct_change().dropna()
                            annual[t] = {str(idx.year): round(float(v), 5) for idx, v in yearly.items()}
                    if annual:
                        cache.write_text(json.dumps(annual, indent=2), encoding="utf-8")
                        return annual, "yfinance live market data"
        except Exception:
            pass
    if cache.exists():
        try:
            return json.loads(cache.read_text(encoding="utf-8")), "cached yfinance market data"
        except Exception:
            pass
    return simulated_annual_returns(tickers), "deterministic simulated market data"


def normalize_symbols(raw, max_count=12):
    if isinstance(raw, str):
        parts = raw.replace("\n", ",").replace(";", ",").split(",")
    else:
        parts = list(raw or [])
    symbols = []
    for item in parts:
        symbol = yahoo_symbol(str(item))
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols[:max_count]


def simulated_ohlcv(symbol, period="6mo", interval="1d"):
    if interval in {"1m", "2m", "5m", "15m", "30m"} or period == "1d":
        minute_step = {"1m": 1, "2m": 2, "5m": 5, "15m": 15, "30m": 30}.get(interval, 1)
        bars = max(16, min(390, 390 // minute_step))
        rng = random.Random(sum(ord(c) for c in symbol) + bars + minute_step)
        price = 80 + (sum(ord(c) for c in symbol) % 180)
        rows = []
        market_open = datetime.now().replace(hour=9, minute=30, second=0, microsecond=0)
        for i in range(bars):
            stamp = market_open.timestamp() + i * minute_step * 60
            date = datetime.fromtimestamp(stamp).strftime("%Y-%m-%d %H:%M")
            drift = rng.gauss(0.00008, 0.0028 * math.sqrt(minute_step))
            open_price = price
            close = open_price * (1 + drift)
            high = max(open_price, close) * (1 + abs(rng.gauss(0.0008, 0.0007)))
            low = min(open_price, close) * (1 - abs(rng.gauss(0.0008, 0.0007)))
            volume = int(10_000 + rng.random() * 900_000)
            rows.append(
                {
                    "date": date,
                    "open": round(open_price, 4),
                    "high": round(high, 4),
                    "low": round(low, 4),
                    "close": round(close, 4),
                    "volume": volume,
                }
            )
            price = close
        return rows

    days_map = {"5d": 5, "1mo": 22, "3mo": 66, "6mo": 132, "1y": 252, "2y": 504}
    days = days_map.get(period, 132)
    rng = random.Random(sum(ord(c) for c in symbol) + days)
    price = 80 + (sum(ord(c) for c in symbol) % 180)
    rows = []
    for i in range(days):
        date = datetime.fromtimestamp(time.time() - (days - i) * 86400).strftime("%Y-%m-%d")
        gap = rng.gauss(0, 0.006)
        drift = rng.gauss(0.0004, 0.018)
        open_price = price * (1 + gap)
        close = open_price * (1 + drift)
        high = max(open_price, close) * (1 + abs(rng.gauss(0.006, 0.006)))
        low = min(open_price, close) * (1 - abs(rng.gauss(0.006, 0.006)))
        volume = int(1_000_000 + rng.random() * 12_000_000)
        rows.append(
            {
                "date": date,
                "open": round(open_price, 2),
                "high": round(high, 2),
                "low": round(low, 2),
                "close": round(close, 2),
                "volume": volume,
            }
        )
        price = close
    return rows


def frame_to_ohlcv_rows(frame):
    rows = []
    if frame is None or getattr(frame, "empty", True):
        return rows
    frame = frame.dropna(how="all")
    for idx, row in frame.iterrows():
        try:
            open_price = safe_float(row.get("Open"), None)
            high = safe_float(row.get("High"), None)
            low = safe_float(row.get("Low"), None)
            close = safe_float(row.get("Close"), None)
            volume = safe_float(row.get("Volume"), 0)
            if open_price is None or high is None or low is None or close is None:
                continue
            if hasattr(idx, "strftime"):
                if getattr(idx, "hour", 0) or getattr(idx, "minute", 0):
                    date_label = idx.strftime("%Y-%m-%d %H:%M")
                else:
                    date_label = idx.strftime("%Y-%m-%d")
            else:
                date_label = str(idx)[:16]
            rows.append(
                {
                    "date": date_label,
                    "open": round(open_price, 4),
                    "high": round(high, 4),
                    "low": round(low, 4),
                    "close": round(close, 4),
                    "volume": int(volume or 0),
                }
            )
        except Exception:
            continue
    return rows


def market_chart_payload(symbols, period="6mo", interval="1d"):
    symbols = normalize_symbols(symbols, max_count=12)
    if not symbols:
        symbols = ["SPY", "QQQ", "AAPL", "XOM"]
    period = period if period in {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y"} else "6mo"
    interval = interval if interval in {"1m", "2m", "5m", "15m", "30m", "1d", "1wk", "1mo"} else "1d"
    if period == "1d" and interval not in {"1m", "2m", "5m", "15m", "30m"}:
        interval = "1m"
    if interval in {"1m", "2m", "5m", "15m", "30m"} and period not in {"1d", "5d"}:
        period = "1d"
    charts = {}
    quotes = []
    source = "deterministic fallback"

    if yf is not None:
        try:
            data = yf.download(
                tickers=symbols,
                period=period,
                interval=interval,
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            if data is not None and not data.empty:
                source = "yfinance live/delayed OHLCV"
                for symbol in symbols:
                    if len(symbols) == 1:
                        frame = data.copy()
                    elif hasattr(data.columns, "nlevels") and data.columns.nlevels > 1 and symbol in data.columns.get_level_values(0):
                        frame = data[symbol].copy()
                    else:
                        frame = None
                    rows = frame_to_ohlcv_rows(frame)
                    if rows:
                        charts[symbol] = rows
        except Exception:
            charts = {}

    for symbol in symbols:
        if symbol not in charts:
            charts[symbol] = simulated_ohlcv(symbol, period=period, interval=interval)
        rows = charts.get(symbol, [])
        last = rows[-1] if rows else {}
        prev = rows[-2] if len(rows) >= 2 else last
        close = safe_float(last.get("close"), 0)
        prev_close = safe_float(prev.get("close"), close)
        change = close - prev_close
        change_pct = change / prev_close if prev_close else 0
        quotes.append(
            {
                "ticker": symbol,
                "last": round(close, 4),
                "change": round(change, 4),
                "change_pct": round(change_pct, 4),
                "open": last.get("open"),
                "high": last.get("high"),
                "low": last.get("low"),
                "volume": last.get("volume"),
                "bars": len(rows),
            }
        )

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "period": period,
        "interval": interval,
        "source": source,
        "symbols": symbols,
        "active_ticker": next((symbol for symbol in symbols if charts.get(symbol)), symbols[0]),
        "quotes": quotes,
        "charts": charts,
    }


def etf_watchlist_payload():
    symbols = []
    for group_symbols in ETF_WATCHLIST.values():
        for symbol in group_symbols:
            if symbol not in symbols:
                symbols.append(symbol)
    market = market_chart_payload(symbols, period="1mo", interval="1d")
    quote_lookup = {q["ticker"]: q for q in market["quotes"]}
    rows = []
    for group, group_symbols in ETF_WATCHLIST.items():
        for symbol in group_symbols:
            q = quote_lookup.get(symbol, {"ticker": symbol})
            rows.append({**q, "group": group})
    return {
        "generated_at": market["generated_at"],
        "source": market["source"],
        "rows": rows,
        "groups": ETF_WATCHLIST,
    }


def market_stats(rows):
    rows = rows or []
    closes = [safe_float(r.get("close"), 0.0) for r in rows if safe_float(r.get("close"), 0.0) > 0]
    volumes = [safe_float(r.get("volume"), 0.0) for r in rows]
    if len(closes) < 2:
        return {
            "last": closes[-1] if closes else 0.0,
            "period_return": 0.0,
            "last_return": 0.0,
            "volatility": 0.0,
            "avg_volume": sum(volumes) / max(1, len(volumes)),
        }
    returns = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes)) if closes[i - 1] > 0]
    mean = sum(returns) / max(1, len(returns))
    vol = math.sqrt(sum((r - mean) ** 2 for r in returns) / max(1, len(returns) - 1)) if len(returns) > 1 else 0.0
    return {
        "last": closes[-1],
        "period_return": closes[-1] / closes[0] - 1 if closes[0] else 0.0,
        "last_return": returns[-1] if returns else 0.0,
        "volatility": vol,
        "avg_volume": sum(volumes) / max(1, len(volumes)),
    }


def etf_group(symbol):
    for group, symbols in ETF_WATCHLIST.items():
        if symbol in symbols:
            return group
    return "ETF"


def etf_climate_profile(symbol):
    if symbol in SECTOR_ETFS:
        meta = SECTOR_ETFS[symbol]
        risk = clamp(
            0.42 * safe_float(meta.get("physical"), 0.5)
            + 0.42 * safe_float(meta.get("transition"), 0.5)
            + 0.16 * (1 - safe_float(meta.get("resilience"), 0.5)),
            0.05,
            0.95,
        )
        return meta["name"], risk, meta["client_note"]
    if symbol in {"ICLN", "QCLN", "TAN", "PBW"}:
        return "Climate / Clean Energy", 0.26, "Cleaner-energy exposure can benefit from transition demand, but short-term volatility can be high."
    if symbol in {"TLT", "IEF", "LQD", "HYG"}:
        return "Rates / Credit", 0.38, "Climate risk enters through credit spreads, insurance, and macro-rate sensitivity."
    if symbol in {"GLD", "SLV"}:
        return "Commodities", 0.32, "Hard-asset hedge sleeve with indirect climate and inflation sensitivity."
    if symbol in {"USO", "UNG"}:
        return "Energy commodity", 0.78, "Direct fossil-energy commodity exposure is climate and policy sensitive."
    if symbol in {"SPY", "DIA", "IWM"}:
        return "Broad market", 0.48, "Broad index exposure diversifies issuer-specific climate risk."
    if symbol == "QQQ":
        return "Growth / Technology", 0.36, "Tech-heavy index is relatively asset-light but still exposed to power and data-center demand."
    return etf_group(symbol), 0.50, "ETF climate score is estimated from group exposure."


def sector_transition_profile(sector):
    factors = SECTOR_TRANSITION_FACTORS.get(sector) or SECTOR_TRANSITION_FACTORS.get("Technology")
    emissions = safe_float(factors.get("emissions"), 0.50)
    policy = safe_float(factors.get("policy"), 0.50)
    carbon_price = safe_float(factors.get("carbon_price"), 0.50)
    opportunity = safe_float(factors.get("transition_opportunity"), 0.40)
    risk = clamp(0.36 * emissions + 0.28 * policy + 0.26 * carbon_price - 0.12 * opportunity + 0.08, 0.04, 0.96)
    return {
        "risk": round(risk, 4),
        "emissions": emissions,
        "policy": policy,
        "carbon_price": carbon_price,
        "opportunity": opportunity,
        "headline": factors.get("headline", "Transition exposure estimated from sector profile."),
    }


def climate_state_variables(daily_signal=None, context=None):
    daily_signal = daily_signal or load_daily_climate_signal()
    context = context or climate_data_context()
    categories = daily_signal.get("category_intensity", {}) or {}
    daily_pressure = safe_float(daily_signal.get("allocation_pressure"), 0.0)
    acute_hazard = clamp(
        0.34 * daily_pressure
        + 0.15 * safe_float(categories.get("heat"), 0.0)
        + 0.13 * safe_float(categories.get("flood"), 0.0)
        + 0.13 * safe_float(categories.get("fire"), 0.0)
        + 0.14 * safe_float(categories.get("tropical"), 0.0)
        + 0.08 * safe_float(categories.get("storm"), 0.0)
        + 0.03 * safe_float(categories.get("air_quality"), 0.0),
        0.0,
        1.0,
    )
    chronic_state = clamp(
        0.45 * clamp((safe_float(context.get("current_warming"), CURRENT_WARMING_C) - 0.75) / 0.85, 0, 1)
        + 0.35 * clamp((safe_float(context.get("disaster_10y_avg"), 15) - 8) / 20, 0, 1)
        + 0.20 * clamp((safe_float(context.get("co2_10y_change"), 20) - 12) / 25, 0, 1),
        0.0,
        1.0,
    )
    macro_transition = clamp(
        0.40 * clamp((safe_float(context.get("co2_ppm"), 420) - 390) / 55, 0, 1)
        + 0.35 * clamp((safe_float(context.get("co2_10y_change"), 20) - 12) / 25, 0, 1)
        + 0.25 * daily_pressure,
        0.0,
        1.0,
    )
    active_sources = (
        1
        + int(bool(context.get("source_mode")))
        + int(bool(daily_signal.get("source_mode")))
        + int(bool(daily_signal.get("climate_alerts")))
    )
    source_reliability = 0.92 if context.get("source_mode", "").lower().startswith("cached official") else 0.76
    alert_reliability = 0.88 if "nws" in str(daily_signal.get("source_mode", "")).lower() else 0.64
    data_confidence = clamp(0.18 + 0.38 * source_reliability + 0.28 * alert_reliability + 0.06 * min(active_sources, 3), 0.35, 0.95)
    return {
        "acute_hazard_state": round(acute_hazard, 4),
        "chronic_climate_state": round(chronic_state, 4),
        "macro_transition_state": round(macro_transition, 4),
        "daily_pressure": round(daily_pressure, 4),
        "data_confidence": round(data_confidence, 4),
        "top_driver": daily_signal.get("top_driver", "climate"),
        "source_mode": daily_signal.get("source_mode", context.get("source_mode", "cached data")),
    }


def normalize_model_sector(sector):
    sector = str(sector or "Technology").strip()
    aliases = {
        "Financial": "Financials",
        "Finance": "Financials",
        "Materials": "Basic Materials",
        "Consumer Discretionary": "Consumer Cyclical",
        "Consumer Staples": "Consumer Defensive",
        "Health Care": "Healthcare",
        "Communications": "Communication Services",
    }
    sector = aliases.get(sector, sector)
    if sector not in SECTOR_DOWNSCALING_FACTORS:
        return "Technology"
    return sector


def issuer_vulnerability_profile(ticker, sector):
    symbol = yahoo_symbol(ticker or "AAPL")
    sector = normalize_model_sector(sector)
    override = ISSUER_VULNERABILITY_OVERRIDES.get(symbol)
    if override:
        acute_ratio = safe_float(override.get("acute_ratio"), 1.0)
        chronic_ratio = safe_float(override.get("chronic_ratio"), 1.0)
        quality = override.get("quality", "Issuer proxy")
    else:
        seed = sum((idx + 3) * ord(char) for idx, char in enumerate(symbol or sector))
        acute_ratio = 0.82 + (seed % 31) / 100
        chronic_ratio = 0.80 + ((seed // 7) % 33) / 100
        quality = "Sector median + deterministic issuer proxy"
    factors = SECTOR_DOWNSCALING_FACTORS[sector]
    return {
        "acute_ratio": round(clamp(acute_ratio, 0.55, 1.45), 4),
        "chronic_ratio": round(clamp(chronic_ratio, 0.55, 1.45), 4),
        "fixed_asset_intensity": round(factors["fixed_asset"] * acute_ratio, 4),
        "labor_intensity": round(factors["labor"] * chronic_ratio, 4),
        "macro_beta": round(factors["macro_beta"], 4),
        "quality": quality,
    }


def current_model_portfolio(daily_signal=None):
    daily_signal = daily_signal or load_daily_climate_signal()
    climate_rows = climate_signal()
    regime = regime_for_year(CURRENT_YEAR, climate_rows)
    weights = climate_weight_policy(regime["regime"])
    base_rows = []
    for ticker, weight in weights.items():
        base_rows.append(
            {
                "year": CURRENT_YEAR,
                "ticker": ticker,
                "sector": SECTOR_ETFS[ticker]["name"],
                "benchmark_weight": round(1 / len(SECTOR_ETFS), 4),
                "climate_weight": round(weight, 4),
                "sector_note": SECTOR_ETFS[ticker]["client_note"],
            }
        )
    return apply_daily_climate_overlay(base_rows, daily_signal)


def climate_model_scope_rows(scope="portfolio", sector="Technology", ticker="AAPL", daily_signal=None):
    scope = str(scope or "portfolio").lower()
    if scope not in {"country", "sector", "issuer", "portfolio"}:
        scope = "portfolio"
    daily_signal = daily_signal or load_daily_climate_signal()
    sector = normalize_model_sector(SECTOR_ETFS.get(yahoo_symbol(ticker), {}).get("name", sector))
    if scope == "portfolio":
        rows = []
        portfolio = current_model_portfolio(daily_signal)
        total = sum(safe_float(row.get("climate_weight"), 0.0) for row in portfolio) or 1.0
        for row in portfolio:
            row_sector = normalize_model_sector(row.get("sector"))
            rows.append(
                {
                    "name": row.get("ticker"),
                    "ticker": row.get("ticker"),
                    "sector": row_sector,
                    "weight": safe_float(row.get("climate_weight"), 0.0) / total,
                    "vulnerability": issuer_vulnerability_profile(row.get("ticker"), row_sector),
                }
            )
        return scope, rows
    if scope == "country":
        return scope, [
            {
                "name": "United States economy",
                "ticker": "US",
                "sector": "Economy",
                "weight": 1.0,
                "vulnerability": {
                    "acute_ratio": 1.0,
                    "chronic_ratio": 1.0,
                    "fixed_asset_intensity": 0.42,
                    "labor_intensity": 0.55,
                    "macro_beta": 1.0,
                    "quality": "Country scenario input",
                },
            }
        ]
    if scope == "sector":
        vulnerability = issuer_vulnerability_profile(sector, sector)
        vulnerability.update({"acute_ratio": 1.0, "chronic_ratio": 1.0, "quality": "Sector calibration"})
        return scope, [{"name": sector, "ticker": "SECTOR", "sector": sector, "weight": 1.0, "vulnerability": vulnerability}]
    return scope, [
        {
            "name": yahoo_symbol(ticker or "AAPL"),
            "ticker": yahoo_symbol(ticker or "AAPL"),
            "sector": sector,
            "weight": 1.0,
            "vulnerability": issuer_vulnerability_profile(ticker, sector),
        }
    ]


def scenario_terminal_components(scenario, sector, vulnerability, horizon):
    sector = normalize_model_sector(sector) if sector != "Economy" else "Economy"
    years_to_2050 = max(1, 2050 - CURRENT_YEAR)
    horizon_fraction = clamp((int(horizon) - CURRENT_YEAR) / years_to_2050, 0.04, 1.0)
    physical_scale = horizon_fraction ** 1.25
    transition_scale = horizon_fraction ** 0.72
    if sector == "Economy":
        acute_ratio = chronic_ratio = macro_beta = 1.0
        transition_risk = 0.50
        transition_opportunity = 0.45
    else:
        factors = SECTOR_DOWNSCALING_FACTORS[sector]
        acute_ratio = clamp((factors["fixed_asset"] / 0.42) * safe_float(vulnerability.get("acute_ratio"), 1.0), 0.50, 1.70)
        chronic_ratio = clamp((factors["labor"] / 0.55) * safe_float(vulnerability.get("chronic_ratio"), 1.0), 0.50, 1.70)
        macro_beta = safe_float(vulnerability.get("macro_beta"), factors["macro_beta"])
        transition = sector_transition_profile(sector)
        transition_risk = transition["risk"]
        transition_opportunity = transition["opportunity"]
    return {
        "acute_physical": safe_float(scenario.get("acute_gdp_loss_2050"), 0.0) * acute_ratio * physical_scale,
        "chronic_physical": safe_float(scenario.get("chronic_gdp_loss_2050"), 0.0) * chronic_ratio * physical_scale,
        "macro_transition": safe_float(scenario.get("macro_transition_loss_2050"), 0.0) * macro_beta * transition_scale,
        "micro_transition": safe_float(scenario.get("transition_demand_shock_2050"), 0.0)
        * (transition_risk - 0.70 * transition_opportunity)
        * transition_scale,
    }


def discounted_scenario_value(components, horizon, wacc=0.075, growth=0.025):
    horizon = int(clamp(safe_float(horizon, 2050), CURRENT_YEAR + 1, 2050))
    years = max(1, horizon - CURRENT_YEAR)
    pv = 0.0
    terminal_cash_flow = 1.0
    for step in range(1, years + 1):
        progress = step / years
        loss = (
            safe_float(components.get("acute_physical"), 0.0) * (progress ** 1.35)
            + safe_float(components.get("chronic_physical"), 0.0) * (progress ** 1.20)
            + safe_float(components.get("macro_transition"), 0.0) * (progress ** 0.68)
            + safe_float(components.get("micro_transition"), 0.0) * (progress ** 0.58)
        )
        baseline_cash_flow = (1 + growth) ** step
        terminal_cash_flow = baseline_cash_flow * (1 - clamp(loss, -0.25, 0.70))
        pv += terminal_cash_flow / ((1 + wacc) ** step)
    terminal_value = terminal_cash_flow * (1 + growth) / max(0.015, wacc - growth)
    pv += terminal_value / ((1 + wacc) ** years)
    return pv


def scenario_repricing_for_scope(scope_rows, target, reference, horizon):
    component_labels = {
        "acute_physical": "Acute physical",
        "chronic_physical": "Chronic physical",
        "macro_transition": "Macro transition",
        "micro_transition": "Business-model transition",
    }
    aggregate_impact = 0.0
    aggregate_target = {key: 0.0 for key in component_labels}
    aggregate_reference = {key: 0.0 for key in component_labels}
    aggregate_contribution = {key: 0.0 for key in component_labels}
    instrument_rows = []
    for row in scope_rows:
        weight = safe_float(row.get("weight"), 0.0)
        target_components = scenario_terminal_components(target, row["sector"], row["vulnerability"], horizon)
        reference_components = scenario_terminal_components(reference, row["sector"], row["vulnerability"], horizon)
        reference_value = discounted_scenario_value(reference_components, horizon)
        target_value = discounted_scenario_value(target_components, horizon)
        value_impact = target_value / max(reference_value, 1e-9) - 1
        aggregate_impact += weight * value_impact
        component_contributions = {}
        for key in component_labels:
            mixed = dict(reference_components)
            mixed[key] = target_components[key]
            contribution = discounted_scenario_value(mixed, horizon) / max(reference_value, 1e-9) - 1
            component_contributions[key] = contribution
            aggregate_target[key] += weight * target_components[key]
            aggregate_reference[key] += weight * reference_components[key]
            aggregate_contribution[key] += weight * contribution
        instrument_rows.append(
            {
                "name": row["name"],
                "ticker": row["ticker"],
                "sector": row["sector"],
                "weight": round(weight, 4),
                "value_impact": round(value_impact, 4),
                "acute_ratio": row["vulnerability"].get("acute_ratio"),
                "chronic_ratio": row["vulnerability"].get("chronic_ratio"),
                "data_quality": row["vulnerability"].get("quality"),
            }
        )
    attribution = []
    for key, label in component_labels.items():
        attribution.append(
            {
                "component": key,
                "label": label,
                "target_loss": round(aggregate_target[key], 4),
                "reference_loss": round(aggregate_reference[key], 4),
                "loss_delta": round(aggregate_target[key] - aggregate_reference[key], 4),
                "value_contribution": round(aggregate_contribution[key], 4),
            }
        )
    return {
        "value_impact": round(aggregate_impact, 4),
        "physical_loss_delta": round(
            aggregate_target["acute_physical"]
            + aggregate_target["chronic_physical"]
            - aggregate_reference["acute_physical"]
            - aggregate_reference["chronic_physical"],
            4,
        ),
        "transition_loss_delta": round(
            aggregate_target["macro_transition"]
            + aggregate_target["micro_transition"]
            - aggregate_reference["macro_transition"]
            - aggregate_reference["micro_transition"],
            4,
        ),
        "attribution": attribution,
        "instruments": sorted(instrument_rows, key=lambda row: abs(row["value_impact"]), reverse=True),
    }


def event_nowcast_for_scope(scope_rows, daily_signal, state):
    categories = daily_signal.get("category_intensity", {}) or {}
    confidence = safe_float(state.get("data_confidence"), 0.50)
    hazard_rows = []
    raw_event_risk = 0.0
    weighted_resilience = 0.0
    weighted_opportunity = 0.0
    for row in scope_rows:
        weight = safe_float(row.get("weight"), 0.0)
        if row["sector"] == "Economy":
            weighted_resilience += weight * 0.50
            weighted_opportunity += weight * 0.42
        else:
            transition = sector_transition_profile(row["sector"])
            sensitivity = COMPANY_SECTOR_SENSITIVITY.get(row["sector"], 0.50)
            weighted_resilience += weight * (1 - 0.62 * sensitivity)
            weighted_opportunity += weight * transition["opportunity"]
    for hazard, hazard_weight in HAZARD_WEIGHTS.items():
        intensity = safe_float(categories.get(hazard), 0.0)
        exposure_beta = 0.0
        represented = []
        for row in scope_rows:
            weight = safe_float(row.get("weight"), 0.0)
            sector = row["sector"]
            if sector == "Economy":
                beta = 0.58
            else:
                beta = HAZARD_SECTOR_BETAS.get(hazard, {}).get(sector, 0.50)
                beta *= safe_float(row["vulnerability"].get("acute_ratio"), 1.0)
            exposure_beta += weight * beta
            represented.append((beta, row["name"]))
        contribution = hazard_weight * intensity * exposure_beta
        raw_event_risk += contribution
        dominant = max(represented, default=(0.0, "-"))[1]
        hazard_rows.append(
            {
                "hazard": hazard,
                "label": hazard.replace("_", " ").title(),
                "intensity": round(intensity, 4),
                "exposure_beta": round(exposure_beta, 4),
                "risk_contribution": round(contribution, 4),
                "dominant_exposure": dominant,
            }
        )
    event_risk = clamp(0.72 * raw_event_risk + 0.28 * safe_float(state.get("daily_pressure"), 0.0), 0.0, 1.0)
    selection_risk = clamp(0.72 * event_risk + 0.28 * (1 - confidence), 0.0, 1.0)
    tactical_edge = 0.52 * weighted_resilience + 0.18 * weighted_opportunity - 0.82 * event_risk - 0.14 * state["macro_transition_state"]
    overlay_bps = int(round(clamp(tactical_edge * 450, -300, 250)))
    if overlay_bps <= -80:
        action = "Underweight / hedge"
    elif overlay_bps >= 80:
        action = "Tactical overweight"
    else:
        action = "Hold near strategic weight"
    return {
        "event_risk": round(event_risk, 4),
        "selection_risk": round(selection_risk, 4),
        "tactical_overlay_bps": overlay_bps,
        "action": action,
        "data_confidence": round(confidence, 4),
        "top_driver": daily_signal.get("top_driver", "climate"),
        "source_mode": daily_signal.get("source_mode", "NWS signal"),
        "hazards": sorted(hazard_rows, key=lambda row: row["risk_contribution"], reverse=True),
    }


def climate_model_lab_payload(scope="portfolio", target="current_policies", reference="baseline", horizon=2050, sector="Technology", ticker="AAPL"):
    target_key = target if target in CLIMATE_SCENARIO_PATHS else "current_policies"
    reference_key = reference if reference in CLIMATE_SCENARIO_PATHS else "baseline"
    horizon = int(clamp(safe_float(horizon, 2050), max(CURRENT_YEAR + 1, 2030), 2050))
    daily_signal = load_daily_climate_signal()
    context = climate_data_context()
    state = climate_state_variables(daily_signal=daily_signal, context=context)
    scope_key, scope_rows = climate_model_scope_rows(scope, sector=sector, ticker=ticker, daily_signal=daily_signal)
    target_scenario = CLIMATE_SCENARIO_PATHS[target_key]
    reference_scenario = CLIMATE_SCENARIO_PATHS[reference_key]
    long_term = scenario_repricing_for_scope(scope_rows, target_scenario, reference_scenario, horizon)
    short_term = event_nowcast_for_scope(scope_rows, daily_signal, state)
    scope_labels = {
        "country": "United States country-level stress",
        "sector": f"{normalize_model_sector(sector)} sector",
        "issuer": f"{yahoo_symbol(ticker or 'AAPL')} issuer proxy",
        "portfolio": "Current climate portfolio",
    }
    resolution = [
        {"level": "Country", "input": "NGFS-style acute/chronic GDP and macro paths", "status": "Scenario calibration", "output": "Country cash-flow shock"},
        {"level": "Sector", "input": "Fixed assets, labor intensity, macro earnings beta", "status": "Sector calibration", "output": "Sector value-added shock"},
        {"level": "Issuer", "input": "Sector median plus issuer vulnerability ratio", "status": "Proxy until facility/revenue data", "output": "Issuer cash-flow and value impact"},
        {"level": "Portfolio", "input": "Current holding weights", "status": "Model portfolio", "output": "Weighted impact and risk attribution"},
    ]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "scope": scope_key,
        "scope_label": scope_labels[scope_key],
        "target_key": target_key,
        "target": {**target_scenario, "key": target_key},
        "reference_key": reference_key,
        "reference": {**reference_scenario, "key": reference_key},
        "horizon": horizon,
        "sector": normalize_model_sector(sector),
        "ticker": yahoo_symbol(ticker or "AAPL"),
        "long_term": long_term,
        "short_term": short_term,
        "climate_state": state,
        "scope_resolution": resolution,
        "methodology": {
            "long_term": "Target scenario minus reference scenario, downscaled country -> sector -> issuer, then discounted into an as-of-date value impact.",
            "short_term": "NWS hazard intensity x sector exposure beta x vulnerability, translated into selection risk and a tactical weight overlay.",
            "probability_rule": "Scenario outputs are conditional stresses. The model does not assign occurrence probabilities to NGFS-style scenarios.",
            "tail_rule": "Scenario tail is reported separately from physical and transition pressure to avoid double counting in the client risk score.",
        },
        "calibration_notice": "Prototype calibration inspired by the uploaded Bloomberg workflow. Scenario paths, sector medians, and issuer ratios are transparent replaceable proxies, not Bloomberg data or investment advice.",
    }


def issuer_exposure_model(symbol, asset_type, sector, climate_risk, transition, state, stats):
    sensitivity = COMPANY_SECTOR_SENSITIVITY.get(sector, 0.50)
    if symbol in SECTOR_ETFS:
        sensitivity = safe_float(SECTOR_ETFS[symbol].get("physical"), sensitivity)
    opportunity = safe_float(transition.get("opportunity"), 0.40)
    resilience = 1 - clamp(0.60 * climate_risk + 0.40 * sensitivity, 0.0, 1.0)
    if sector in {"Technology", "Healthcare", "Communication Services"}:
        resilience = clamp(resilience + 0.20, 0.0, 1.0)
    if sector in {"Utilities", "Financials", "Financial Services"}:
        resilience = clamp(resilience + 0.08, 0.0, 1.0)
    liquidity = clamp(math.log1p(stats.get("avg_volume", 0)) / math.log1p(60_000_000), 0.05, 0.98)
    confidence = clamp(state["data_confidence"] * (0.94 if asset_type == "ETF" else 0.86) + 0.06 * liquidity, 0.20, 0.98)
    acute = state["acute_hazard_state"]
    chronic = state["chronic_climate_state"]
    macro = state["macro_transition_state"]
    physical_pressure = clamp(0.52 * acute * sensitivity + 0.33 * chronic * sensitivity + 0.15 * climate_risk, 0.02, 0.98)
    transition_pressure = clamp(
        0.48 * safe_float(transition.get("risk"), 0.50)
        + 0.32 * macro
        + 0.20 * climate_risk
        - 0.18 * opportunity,
        0.02,
        0.98,
    )
    climate_pressure = clamp(0.54 * physical_pressure + 0.46 * transition_pressure, 0.02, 0.98)
    return {
        "physical_pressure": round(physical_pressure, 4),
        "transition_pressure": round(transition_pressure, 4),
        "climate_pressure": round(climate_pressure, 4),
        "resilience": round(resilience, 4),
        "opportunity": round(opportunity, 4),
        "data_confidence": round(confidence, 4),
        "sensitivity": round(sensitivity, 4),
    }


def historical_climate_pressure_for_year(year, climate_rows=None):
    climate_rows = climate_rows or climate_signal()
    if not climate_rows:
        return 0.45
    lookup = {int(r.get("year", 0)): r for r in climate_rows}
    available_year = max((y for y in lookup if y <= int(year)), default=max(lookup))
    row = lookup.get(available_year, climate_rows[-1])
    score = safe_float(row.get("climate_risk_score"), 0.0)
    threshold = safe_float(row.get("top_quartile_threshold"), 0.0)
    normalized = 0.50 + 0.18 * score + (0.16 if score >= threshold else -0.04)
    return round(clamp(normalized, 0.08, 0.92), 4)


def climate_source_rows(daily_signal=None, context=None):
    daily_signal = daily_signal or load_daily_climate_signal()
    context = context or climate_data_context()
    rows = []
    for item in CLIMATE_DATA_SOURCE_CATALOG:
        status = item["status"]
        mode = "Client reference"
        if item["name"] == "NWS Active Alerts":
            status = daily_signal.get("source_mode", status)
            mode = "Live model input"
        elif item["name"] in {"NASA GISTEMP", "NOAA GML CO2", "NOAA NCEI Billion-Dollar Disasters"}:
            status = context.get("source_mode", status)
            mode = "Official model input"
        elif item["name"] in {"EPA GHGRP", "EPA eGRID", "EIA Open Data", "NGFS Scenarios", "SEC EDGAR APIs"}:
            mode = "Transition-risk source"
        else:
            mode = "Physical-risk source"
        rows.append(
            {
                **item,
                "status": status,
                "model_mode": mode,
            }
        )
    return rows


def climate_intelligence_payload(latest_alloc=None, daily_signal=None, cvor_summary=None, context=None):
    daily_signal = daily_signal or load_daily_climate_signal()
    context = context or climate_data_context()
    cvor_summary = cvor_summary or {}
    state = climate_state_variables(daily_signal=daily_signal, context=context)
    daily_pressure = state["daily_pressure"]
    acute_physical = state["acute_hazard_state"]
    chronic_physical = state["chronic_climate_state"]
    physical_score = clamp(0.58 * acute_physical + 0.42 * chronic_physical, 0.0, 1.0)
    macro_transition = state["macro_transition_state"]
    scenario_tail_loss = safe_float(
        cvor_summary.get("scenario_tail_loss_rate"),
        safe_float(cvor_summary.get("cvor_95_loss_rate"), 0.0),
    )
    scenario_tail_score = clamp(scenario_tail_loss / 0.12, 0.0, 1.0)
    transition_weighted = macro_transition
    top_affected = []
    if latest_alloc:
        total_weight = sum(safe_float(r.get("climate_weight"), 0.0) for r in latest_alloc) or 1.0
        transition_weighted = 0.0
        for row in latest_alloc:
            weight = safe_float(row.get("climate_weight"), 0.0) / total_weight
            sector = row.get("sector") or SECTOR_ETFS.get(row.get("ticker"), {}).get("name") or "Technology"
            transition = sector_transition_profile(sector)
            sensitivity = COMPANY_SECTOR_SENSITIVITY.get(sector, safe_float(SECTOR_ETFS.get(row.get("ticker"), {}).get("physical"), 0.50))
            physical = clamp(0.48 * safe_float(row.get("daily_sector_stress"), physical_score) + 0.34 * sensitivity * physical_score + 0.18 * chronic_physical, 0.0, 1.0)
            combined = clamp(0.52 * physical + 0.48 * transition["risk"], 0.0, 1.0)
            transition_weighted += weight * transition["risk"]
            if combined >= 0.28:
                top_affected.append(
                    {
                        "ticker": row.get("ticker"),
                        "sector": sector,
                        "weight": row.get("climate_weight"),
                        "physical_risk": round(physical, 4),
                        "transition_risk": transition["risk"],
                        "combined_risk": round(combined, 4),
                        "action": "Hedge / reduce" if combined >= 0.68 else ("Watch closely" if combined >= 0.46 else "Monitor"),
                        "driver": row.get("daily_driver") or transition["headline"],
                    }
                )
    transition_score = clamp(0.58 * transition_weighted + 0.42 * macro_transition, 0.0, 1.0)
    pressure_score = clamp(0.55 * physical_score + 0.45 * transition_score, 0.0, 1.0)
    decision_score = max(pressure_score, 0.80 * scenario_tail_score)
    source_rows = climate_source_rows(daily_signal=daily_signal, context=context)
    live_inputs = sum(1 for r in source_rows if "input" in r["model_mode"].lower())
    confidence = clamp(0.40 * state["data_confidence"] + 0.08 * live_inputs + 0.08 * (1 if latest_alloc else 0), 0.0, 0.95)
    top_affected = sorted(top_affected, key=lambda r: r["combined_risk"], reverse=True)[:6]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "risk_level": "High" if decision_score >= 0.66 else ("Elevated" if decision_score >= 0.44 else "Watch"),
        "total_score": round(pressure_score, 4),
        "decision_score": round(decision_score, 4),
        "physical_score": round(physical_score, 4),
        "acute_physical_score": round(acute_physical, 4),
        "chronic_physical_score": round(chronic_physical, 4),
        "transition_score": round(transition_score, 4),
        "macro_transition_score": round(macro_transition, 4),
        "cvor_score": round(scenario_tail_score, 4),
        "scenario_tail_score": round(scenario_tail_score, 4),
        "scenario_tail_loss_rate": round(scenario_tail_loss, 4),
        "confidence": round(confidence, 4),
        "climate_state": state,
        "methodology_stack": [
            {"step": "Country scenarios", "output": "Target minus reference acute, chronic, and transition paths"},
            {"step": "Downscaling", "output": "Sector vulnerability plus issuer fixed-asset and labor-intensity proxies"},
            {"step": "Valuation", "output": "Climate-adjusted cash flows discounted into an as-of-date value impact"},
            {"step": "Event nowcast", "output": "NWS hazard intensity becomes a separate tactical selection overlay"},
            {"step": "Validation", "output": "Walk-forward backtest, market-only ablation, and parameter sensitivity"},
        ],
        "model_coverage": [
            {
                "layer": "Live physical event nowcast",
                "coverage": "NWS alert type, intensity, and affected area",
                "status": "Operational",
                "decision_use": "Tactical sector and security selection overlay",
            },
            {
                "layer": "Chronic physical state",
                "coverage": "NASA temperature, NOAA CO2, NCEI disaster history",
                "status": "Operational",
                "decision_use": "Regime and long-run physical-pressure calibration",
            },
            {
                "layer": "Scenario repricing",
                "coverage": "Target-reference acute, chronic, and transition paths",
                "status": "Calibrated proxy",
                "decision_use": "Conditional value impact and portfolio stress",
            },
            {
                "layer": "Issuer downscaling",
                "coverage": "Sector sensitivity, fixed-asset and labor-intensity ratios",
                "status": "Proxy",
                "decision_use": "Security-level cash-flow and tail-risk estimate",
            },
            {
                "layer": "Facility geolocation",
                "coverage": "Plant, office, supplier, and insured-asset coordinates",
                "status": "Data gap",
                "decision_use": "Required for bottom-up peril damage and business interruption",
            },
            {
                "layer": "Revenue and supply-chain mapping",
                "coverage": "Regional revenue, product taxonomy, supplier concentration",
                "status": "Data gap",
                "decision_use": "Required for Bloomberg-style micro-transition attribution",
            },
        ],
        "headline": (
            f"{daily_signal.get('top_driver', 'climate').replace('_', ' ')} is the top daily driver; "
            f"transition pressure is {'high' if transition_score >= 0.62 else 'moderate' if transition_score >= 0.38 else 'low'}."
        ),
        "client_action": (
            "Reduce climate concentration and keep the scenario-tail guardrail active"
            if decision_score >= 0.66
            else ("Hold core exposures, raise monitoring on affected sectors" if decision_score >= 0.44 else "Maintain allocation with routine monitoring")
        ),
        "top_affected": top_affected,
        "source_rows": source_rows,
    }


def optimizer_mode(mode):
    mode = str(mode or "etf_stock").lower()
    return mode if mode in OPTIMIZER_MODE_LABELS else "etf_stock"


def optimizer_horizon(horizon):
    horizon = str(horizon or "long").lower()
    return horizon if horizon in {"short", "long"} else "long"


def optimizer_style(style):
    style = str(style or "balanced").lower()
    return style if style in OPTIMIZER_STYLES else "balanced"


def allocation_signal(total_score, climate_score, risk_score, weight):
    if weight >= 0.18 and total_score >= 0.68:
        return "Core / overweight"
    if total_score >= 0.60:
        return "Add / hold"
    if climate_score < 0.35:
        return "Climate-risk watch"
    if risk_score < 0.35:
        return "Volatility watch"
    return "Small weight / monitor"


def automatic_optimizer_universe(daily_signal=None):
    daily_signal = daily_signal or load_daily_climate_signal()
    etf_ranked = []
    for item in DAILY_CLIMATE_ETFS:
        relation = climate_relation_score(item.get("exposure", {}), daily_signal)
        etf_ranked.append((relation, item["ticker"]))
    stock_ranked = []
    for item in DAILY_CLIMATE_STOCKS:
        relation = climate_relation_score(item.get("exposure", {}), daily_signal)
        stock_ranked.append((relation, item["ticker"]))

    etfs = ["SPY", "QQQ"]
    for _, ticker in sorted(etf_ranked, reverse=True):
        if ticker not in etfs:
            etfs.append(ticker)
    for ticker in DEFAULT_OPTIMIZER_ETFS:
        if ticker not in etfs:
            etfs.append(ticker)

    stocks = []
    for _, ticker in sorted(stock_ranked, reverse=True):
        if ticker not in stocks:
            stocks.append(ticker)
    for ticker in DEFAULT_OPTIMIZER_STOCKS:
        if ticker not in stocks:
            stocks.append(ticker)

    return etfs[:10], stocks[:10]


def portfolio_optimizer_payload(mode="etf_stock", capital=None, horizon="long", style="balanced", etfs="", stocks=""):
    mode = optimizer_mode(mode)
    horizon = optimizer_horizon(horizon)
    style_key = optimizer_style(style)
    profile = OPTIMIZER_STYLES[style_key]
    capital_value = clamp(safe_float(capital, DEFAULT_PORTFOLIO_VALUE), 10_000, 5_000_000_000)
    daily_signal = load_daily_climate_signal()
    auto_etfs, auto_stocks = automatic_optimizer_universe(daily_signal)
    custom_etfs = bool(str(etfs or "").strip())
    custom_stocks = bool(str(stocks or "").strip())

    etf_symbols = normalize_symbols(etfs, max_count=18) if custom_etfs else auto_etfs
    stock_symbols = normalize_symbols(stocks, max_count=12) if custom_stocks else auto_stocks
    include_etfs = mode in {"etf_only", "etf_stock"}
    include_stocks = mode in {"stock_only", "etf_stock"}
    if not include_etfs:
        etf_symbols = []
    if not include_stocks:
        stock_symbols = []

    symbols = []
    for symbol in etf_symbols + stock_symbols:
        if symbol not in symbols:
            symbols.append(symbol)
    if not symbols:
        symbols = list(auto_etfs or DEFAULT_OPTIMIZER_ETFS)
        etf_symbols = list(auto_etfs or DEFAULT_OPTIMIZER_ETFS)
        include_etfs = True

    market_period = "1d" if horizon == "short" else "3mo"
    market_interval = "1m" if horizon == "short" else "1d"
    market = market_chart_payload(symbols, period=market_period, interval=market_interval)
    chart_lookup = market.get("charts", {})
    climate_context = climate_data_context()
    climate_state = climate_state_variables(daily_signal=daily_signal, context=climate_context)

    stock_scan = {}
    if stock_symbols:
        try:
            stock_scan = {r["ticker"]: r for r in company_scan(stock_symbols)}
        except Exception:
            stock_scan = {}

    daily_pressure = safe_float(daily_signal.get("allocation_pressure"), 0.0)
    chronic_physical = clamp(
        0.50 * clamp((safe_float(climate_context.get("current_warming"), CURRENT_WARMING_C) - 0.75) / 0.85, 0, 1)
        + 0.50 * clamp((safe_float(climate_context.get("disaster_10y_avg"), 15) - 8) / 20, 0, 1),
        0.0,
        1.0,
    )
    rows = []
    for symbol in symbols:
        stats = market_stats(chart_lookup.get(symbol, []))
        last_price = stats["last"]
        short_term = horizon == "short"
        momentum_raw = stats["period_return"] * (16 if short_term else 5) + stats["last_return"] * (28 if short_term else 6)
        momentum_score = clamp(0.50 + momentum_raw, 0.03, 0.97)
        vol_limit = 0.0048 if short_term else 0.035
        risk_score = clamp(1 - stats["volatility"] / max(vol_limit, 1e-6), 0.03, 0.97)
        liquidity_score = clamp(math.log1p(stats["avg_volume"]) / math.log1p(60_000_000), 0.05, 0.98)
        market_score = clamp(0.55 * momentum_score + 0.25 * liquidity_score + 0.20 * risk_score, 0.03, 0.97)

        if symbol in stock_symbols:
            scan = stock_scan.get(symbol, {})
            asset_type = "Stock"
            sector = scan.get("sector") or guess_sector(symbol)
            cvor_proxy = max(
                safe_float(scan.get("method2_p95_pct"), 0.055),
                abs(safe_float(scan.get("market_cvar_95"), -0.03)) * 0.55,
            )
            climate_risk = clamp(cvor_proxy / 0.14, 0.05, 0.95)
            climate_score = clamp(1 - climate_risk, 0.05, 0.95)
            rationale = (
                f"{sector}; Method 2 P95 {cvor_proxy:.2%}; "
                f"{'today momentum' if short_term else '3M trend'} {stats['period_return']:.2%}."
            )
        else:
            asset_type = "ETF"
            sector, climate_risk, note = etf_climate_profile(symbol)
            cvor_proxy = climate_risk * 0.10
            climate_score = clamp(1 - climate_risk, 0.05, 0.95)
            rationale = f"{sector}; {note} {'Today 1m trend' if short_term else '3M trend'} {stats['period_return']:.2%}."

        transition = sector_transition_profile(sector)
        exposure = issuer_exposure_model(symbol, asset_type, sector, climate_risk, transition, climate_state, stats)
        physical_risk = exposure["physical_pressure"]
        transition_risk = exposure["transition_pressure"]
        climate_score = clamp(
            0.38 * (1 - physical_risk)
            + 0.30 * (1 - transition_risk)
            + 0.17 * exposure["opportunity"]
            + 0.15 * exposure["data_confidence"],
            0.05,
            0.95,
        )
        base_alpha = clamp(0.40 * momentum_score + 0.25 * liquidity_score + 0.20 * risk_score + 0.15 * market_score, 0.02, 0.98)
        climate_alpha = clamp(
            0.42 * exposure["opportunity"]
            + 0.22 * exposure["resilience"]
            - 0.20 * physical_risk
            - 0.16 * transition_risk
            + 0.10 * exposure["data_confidence"],
            -0.45,
            0.65,
        )
        risk_penalty = clamp(0.52 * (1 - risk_score) + 0.28 * stats["volatility"] / max(vol_limit, 1e-6) + 0.20 * (1 - exposure["data_confidence"]), 0.0, 0.95)
        cvor_penalty = clamp(cvor_proxy / 0.12, 0.0, 1.0)
        theta_regime = clamp(0.34 + 0.36 * climate_state["acute_hazard_state"] + 0.30 * climate_state["macro_transition_state"], 0.20, 0.88)
        robust_score = clamp(
            profile["market_weight"] * base_alpha
            + profile["climate_weight"] * (0.50 + theta_regime * climate_alpha)
            + profile["risk_weight"] * (1 - risk_penalty)
            - 0.10 * cvor_penalty,
            0.01,
            0.99,
        )
        attribution = (
            f"Base alpha {base_alpha:.0%}; climate alpha {climate_alpha:+.0%}; "
            f"risk penalty {risk_penalty:.0%}; CVOR penalty {cvor_penalty:.0%}; confidence {exposure['data_confidence']:.0%}."
        )
        total_score = robust_score
        if short_term:
            total_score = 0.76 * total_score + 0.24 * market_score
        else:
            total_score = 0.82 * total_score + 0.18 * climate_score
        total_score *= 1 - 0.16 * daily_pressure * climate_risk
        confidence_cap = clamp(0.055 + 0.13 * exposure["data_confidence"] + (0.06 if asset_type == "ETF" else 0.0), 0.055, 0.24)
        rows.append(
            {
                "ticker": symbol,
                "asset_type": asset_type,
                "sector": sector,
                "last": round(last_price, 4),
                "momentum": round(stats["period_return"], 5),
                "volatility": round(stats["volatility"], 5),
                "market_score": round(market_score, 4),
                "climate_score": round(climate_score, 4),
                "physical_risk": round(physical_risk, 4),
                "transition_risk": round(transition_risk, 4),
                "transition_headline": transition.get("headline"),
                "base_alpha": round(base_alpha, 4),
                "climate_alpha": round(climate_alpha, 4),
                "risk_penalty": round(risk_penalty, 4),
                "cvor_penalty": round(cvor_penalty, 4),
                "theta_regime": round(theta_regime, 4),
                "data_confidence": exposure["data_confidence"],
                "confidence_cap": round(confidence_cap, 4),
                "issuer_sensitivity": exposure["sensitivity"],
                "resilience": exposure["resilience"],
                "opportunity": exposure["opportunity"],
                "risk_score": round(risk_score, 4),
                "total_score": round(clamp(total_score, 0.01, 0.99), 4),
                "cvor_proxy": round(cvor_proxy, 4),
                "raw_weight": max(0.002, clamp(total_score, 0.01, 0.99) ** 1.35),
                "rationale": f"{rationale} {attribution}",
            }
        )

    if mode == "etf_only":
        sleeves = {"ETF": 1.0, "Stock": 0.0}
    elif mode == "stock_only":
        sleeves = {"ETF": 0.0, "Stock": 1.0}
    else:
        stock_sleeve = profile["stock_sleeve"]
        if horizon == "short":
            stock_sleeve += 0.08
        if style_key == "growth":
            stock_sleeve += 0.06
        if style_key in {"low_vol", "climate_defense"}:
            stock_sleeve -= 0.06
        stock_sleeve = clamp(stock_sleeve, 0.20, 0.62)
        sleeves = {"ETF": 1 - stock_sleeve, "Stock": stock_sleeve}

    for asset_type in ["ETF", "Stock"]:
        group = [r for r in rows if r["asset_type"] == asset_type]
        sleeve_weight = sleeves.get(asset_type, 0.0)
        raw_total = sum(r["raw_weight"] for r in group) or 1.0
        for row in group:
            weight = sleeve_weight * row["raw_weight"] / raw_total
            weight = min(weight, row.get("confidence_cap", 0.24))
            row["target_weight"] = round(weight, 4)
            row["target_dollars"] = round(weight * capital_value, 2)
            row["estimated_shares"] = round(row["target_dollars"] / row["last"], 2) if row["last"] else 0
            row["action"] = allocation_signal(row["total_score"], row["climate_score"], row["risk_score"], weight)

    weight_total = sum(r.get("target_weight", 0.0) for r in rows) or 1.0
    market_raw_total = sum(max(0.002, safe_float(r.get("base_alpha"), r.get("market_score", 0.5)) ** 1.35) for r in rows) or 1.0
    for row in rows:
        row["target_weight"] = round(row.get("target_weight", 0.0) / weight_total, 4)
        row["target_dollars"] = round(row["target_weight"] * capital_value, 2)
        row["estimated_shares"] = round(row["target_dollars"] / row["last"], 2) if row["last"] else 0
        market_only_weight = max(0.002, safe_float(row.get("base_alpha"), row.get("market_score", 0.5)) ** 1.35) / market_raw_total
        row["market_only_weight"] = round(market_only_weight, 4)
        row["climate_weight_delta"] = round(row["target_weight"] - market_only_weight, 4)

    rows = sorted(rows, key=lambda r: r.get("target_weight", 0.0), reverse=True)
    for row in rows:
        row.pop("raw_weight", None)

    weights = [safe_float(row.get("target_weight"), 0.0) for row in rows]
    hhi = sum(weight * weight for weight in weights)
    sector_weights = {}
    for row in rows:
        sector_name = row.get("sector") or "Unclassified"
        sector_weights[sector_name] = sector_weights.get(sector_name, 0.0) + safe_float(row.get("target_weight"), 0.0)
    top_sector, top_sector_weight = max(sector_weights.items(), key=lambda item: item[1], default=("-", 0.0))
    top_risk_row = max(
        rows,
        key=lambda row: safe_float(row.get("target_weight"), 0.0) * safe_float(row.get("cvor_proxy"), 0.0),
        default={},
    )
    top_overweight = max(rows, key=lambda row: safe_float(row.get("climate_weight_delta"), 0.0), default={})
    top_underweight = min(rows, key=lambda row: safe_float(row.get("climate_weight_delta"), 0.0), default={})
    weighted_tail_proxy = sum(
        safe_float(row.get("target_weight"), 0.0) * safe_float(row.get("cvor_proxy"), 0.0) for row in rows
    )
    weighted_physical = sum(
        safe_float(row.get("target_weight"), 0.0) * safe_float(row.get("physical_risk"), 0.0) for row in rows
    )
    weighted_transition = sum(
        safe_float(row.get("target_weight"), 0.0) * safe_float(row.get("transition_risk"), 0.0) for row in rows
    )
    weighted_confidence = sum(
        safe_float(row.get("target_weight"), 0.0) * safe_float(row.get("data_confidence"), 0.0) for row in rows
    )
    weighted_climate_alpha = sum(
        safe_float(row.get("target_weight"), 0.0) * safe_float(row.get("climate_alpha"), 0.0) for row in rows
    )
    climate_active_share = 0.5 * sum(abs(safe_float(row.get("climate_weight_delta"), 0.0)) for row in rows)
    max_position = max(weights, default=0.0)
    effective_positions = 1 / hhi if hhi > 0 else 0.0
    budget_checks = [
        {
            "name": "Single-position concentration",
            "value": round(max_position, 4),
            "limit": 0.20,
            "status": "Pass" if max_position <= 0.20 else "Watch",
            "interpretation": "Internal watch threshold, not a regulatory limit.",
        },
        {
            "name": "Weighted holding tail proxy",
            "value": round(weighted_tail_proxy, 4),
            "limit": 0.08,
            "status": "Pass" if weighted_tail_proxy <= 0.08 else "Watch",
            "interpretation": "Weighted security-level P95/CVOR proxy; separate from scenario tail stress.",
        },
        {
            "name": "Effective positions",
            "value": round(effective_positions, 2),
            "limit": 6.0,
            "status": "Pass" if effective_positions >= 6.0 else "Watch",
            "interpretation": "Inverse HHI; higher values indicate broader diversification.",
        },
        {
            "name": "Model confidence",
            "value": round(weighted_confidence, 4),
            "limit": 0.65,
            "status": "Pass" if weighted_confidence >= 0.65 else "Watch",
            "interpretation": "Weight-averaged source and issuer mapping confidence.",
        },
    ]
    if weighted_tail_proxy >= 0.08 or max_position > 0.20:
        posture = "Defensive tilt"
        strategic_action = "Reduce the largest tail-risk contributor before adding climate opportunity exposure."
    elif weighted_climate_alpha >= 0.05:
        posture = "Selective climate overweight"
        strategic_action = "Maintain the core book and fund resilient opportunities from climate-sensitive underweights."
    else:
        posture = "Climate-aware neutral"
        strategic_action = "Keep benchmark-like exposure while using climate risk as a position-sizing constraint."
    if daily_pressure >= 0.45:
        tactical_action = "Tighten short-horizon risk and require stronger market confirmation for new buys."
    elif daily_pressure >= 0.20:
        tactical_action = "Keep the live event overlay active; rebalance only where sector transmission is material."
    else:
        tactical_action = "No broad tactical hedge; monitor event-sensitive sectors and retain strategic weights."

    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "mode": mode,
        "mode_label": OPTIMIZER_MODE_LABELS[mode],
        "style": style_key,
        "style_label": profile["label"],
        "style_note": profile["note"],
        "horizon": horizon,
        "horizon_label": "Short-term holding" if horizon == "short" else "Long-term holding",
        "capital": round(capital_value, 2),
        "universe_mode": "Custom override" if custom_etfs or custom_stocks else "Automatic climate universe",
        "auto_etfs": auto_etfs,
        "auto_stocks": auto_stocks,
        "custom_etfs": custom_etfs,
        "custom_stocks": custom_stocks,
        "universe_note": (
            "Candidate universe is automatically ranked from climate state variables, market anchors, issuer exposure, and climate-sensitive profiles."
            if not (custom_etfs or custom_stocks)
            else "Advanced custom tickers override the automatic climate universe for this optimizer run."
        ),
        "daily_climate_overlay": daily_pressure,
        "climate_state": climate_state,
        "risk_budget": {
            "max_position": round(max_position, 4),
            "hhi": round(hhi, 4),
            "effective_positions": round(effective_positions, 2),
            "top_sector": top_sector,
            "top_sector_weight": round(top_sector_weight, 4),
            "climate_active_share": round(climate_active_share, 4),
            "weighted_tail_proxy": round(weighted_tail_proxy, 4),
            "capital_at_tail_proxy": round(weighted_tail_proxy * capital_value, 2),
            "weighted_physical_risk": round(weighted_physical, 4),
            "weighted_transition_risk": round(weighted_transition, 4),
            "weighted_climate_alpha": round(weighted_climate_alpha, 4),
            "weighted_confidence": round(weighted_confidence, 4),
            "largest_risk_contributor": top_risk_row.get("ticker", "-"),
            "largest_climate_overweight": top_overweight.get("ticker", "-"),
            "largest_climate_overweight_delta": round(safe_float(top_overweight.get("climate_weight_delta"), 0.0), 4),
            "largest_climate_underweight": top_underweight.get("ticker", "-"),
            "largest_climate_underweight_delta": round(safe_float(top_underweight.get("climate_weight_delta"), 0.0), 4),
            "checks": budget_checks,
        },
        "investment_view": {
            "posture": posture,
            "strategic_action": strategic_action,
            "tactical_action": tactical_action,
            "largest_risk": f"{top_risk_row.get('ticker', '-')} is the largest weighted holding-tail contributor.",
            "largest_opportunity": f"{top_overweight.get('ticker', '-')} receives the largest climate-aware overweight versus the market-only book.",
            "governance_note": "Risk-budget thresholds are transparent internal watch levels. They are not regulatory limits or investment advice.",
        },
        "validation": {
            "same_pick_benchmark": "Backtest compares optimizer weights against equal-weight same holdings.",
            "market_only_ablation": "Each row includes a market-only implied weight so the client can see how climate/CVOR changed allocation.",
            "walk_forward_note": "True out-of-sample validation should rebalance historically using only information available before each rebalance date.",
        },
        "methodology": {
            "model": "Climate-conditioned multi-factor optimizer",
            "objective": "Maximize expected return adjusted for climate alpha while penalizing volatility, CVOR tail loss, turnover, and low-confidence data.",
            "expected_return": "ExpectedReturn = BaseAlpha + theta_regime * ClimateAlpha",
            "risk": "Risk layer separates volatility/drawdown risk from CVOR scenario tail loss.",
            "constraint": "Data confidence creates a soft position cap before final weights are normalized.",
        },
        "market_source": market["source"],
        "market_period": market["period"],
        "market_interval": market["interval"],
        "holding_note": (
            "Short-term mode uses today's 1-minute bars plus the live climate alert overlay."
            if horizon == "short"
            else "Long-term mode uses recent daily trend, Method 2 CVOR, and structural climate resilience."
        ),
        "rows": rows,
    }


def daily_climate_category_signal(daily_signal, category):
    counts = daily_signal.get("category_counts", {}) or {}
    intensity = daily_signal.get("category_intensity", {}) or {}
    count_score = clamp(safe_float(counts.get(category), 0.0) / 45.0, 0.0, 1.0)
    intensity_score = safe_float(intensity.get(category), 0.0)
    return clamp(0.72 * intensity_score + 0.28 * count_score, 0.0, 1.0)


def climate_relation_score(exposure, daily_signal):
    pressure = safe_float(daily_signal.get("allocation_pressure"), 0.0)
    if not exposure:
        return round(pressure * 0.25, 4)
    active = 0.0
    possible = 0.0
    for category, weight in exposure.items():
        w = safe_float(weight, 0.0)
        possible += w
        active += w * daily_climate_category_signal(daily_signal, category)
    if possible <= 0:
        return round(pressure * 0.25, 4)
    relation = active / possible
    relation = 0.74 * relation + 0.26 * pressure * min(1.0, possible / max(0.01, len(exposure)))
    return round(clamp(relation, 0.0, 1.0), 4)


def daily_climate_action(stance, relation, momentum):
    relation = safe_float(relation, 0.0)
    momentum = safe_float(momentum, 0.0)
    if relation < 0.12:
        return "Low signal / monitor"
    if stance == "beneficiary":
        if relation >= 0.34 and momentum >= 0:
            return "Daily buy candidate"
        return "Watch for entry"
    if stance == "hedge":
        return "Hedge candidate" if relation >= 0.26 else "Keep as hedge"
    if stance == "risk":
        if relation >= 0.38:
            return "Reduce / hedge"
        return "Risk watch"
    if relation >= 0.38 and momentum >= 0:
        return "Selective overweight"
    if relation >= 0.28:
        return "Hold with hedge"
    return "Monitor"


def category_reminder(category):
    reminders = {
        "heat": "Power demand, utilities, data centers, solar, and grid stress.",
        "flood": "Insurers, banks, real estate credit, industrial recovery, and transport.",
        "fire": "Utilities, insurers, timber, air quality, and distributed power.",
        "tropical": "Gulf energy, utilities, property insurance, logistics, and rebuilding.",
        "storm": "Insurance claims, utilities, construction, industrials, and power outages.",
        "winter": "Natural gas, utilities, power demand, and transport delays.",
        "air_quality": "Health, clean energy, EV, utilities, and regional activity.",
    }
    return reminders.get(category, "Monitor climate-sensitive sectors.")


def top_sample_area(daily_signal, category):
    samples = daily_signal.get("sample_events", []) or []
    for sample in samples:
        if sample.get("category") == category:
            return sample.get("area") or sample.get("event") or "-"
    return "-"


def daily_climate_alert_rows(daily_signal):
    counts = daily_signal.get("category_counts", {}) or {}
    rows = []
    for category in DAILY_ALERT_CATEGORY_WEIGHTS:
        count = int(safe_float(counts.get(category), 0))
        intensity = daily_climate_category_signal(daily_signal, category)
        if count <= 0 and intensity <= 0.01:
            continue
        rows.append(
            {
                "driver": category,
                "driver_label": CLIMATE_CATEGORY_LABELS.get(category, category.title()),
                "count": count,
                "intensity": round(intensity, 4),
                "reminder": category_reminder(category),
                "sample_area": top_sample_area(daily_signal, category),
            }
        )
    if not rows:
        rows.append(
            {
                "driver": "long_run",
                "driver_label": "Long-run climate pressure",
                "count": 0,
                "intensity": round(safe_float(daily_signal.get("allocation_pressure"), 0.0), 4),
                "reminder": "Use official temperature, CO2, and disaster-frequency inputs as the base climate risk signal.",
                "sample_area": "-",
            }
        )
    return sorted(rows, key=lambda r: (r["intensity"], r["count"]), reverse=True)


def daily_market_lookup(symbols):
    market = market_chart_payload(symbols, period="1d", interval="1m")
    charts = market.get("charts", {})
    return market, {symbol: market_stats(charts.get(symbol, [])) for symbol in symbols}


def daily_climate_stock_recommendations(daily_signal):
    ranked = []
    for item in DAILY_CLIMATE_STOCKS:
        relation = climate_relation_score(item.get("exposure", {}), daily_signal)
        ranked.append((relation, item))
    ranked = sorted(ranked, key=lambda x: x[0], reverse=True)[:10]
    symbols = [item["ticker"] for _, item in ranked]
    market, stats_lookup = daily_market_lookup(symbols)
    rows = []
    for relation, item in ranked:
        stats = stats_lookup.get(item["ticker"], {})
        momentum = safe_float(stats.get("period_return"), 0.0)
        rows.append(
            {
                "ticker": item["ticker"],
                "name": item["name"],
                "theme": item["theme"],
                "stance": item["stance"],
                "relation_score": relation,
                "last": round(safe_float(stats.get("last"), 0.0), 4),
                "today_return": round(momentum, 5),
                "volatility": round(safe_float(stats.get("volatility"), 0.0), 5),
                "action": daily_climate_action(item["stance"], relation, momentum),
                "climate_link": item["note"],
            }
        )
    return rows, market


def daily_climate_etf_recommendations(daily_signal):
    ranked = []
    for item in DAILY_CLIMATE_ETFS:
        relation = climate_relation_score(item.get("exposure", {}), daily_signal)
        ranked.append((relation, item))
    ranked = sorted(ranked, key=lambda x: x[0], reverse=True)[:10]
    symbols = [item["ticker"] for _, item in ranked]
    market, stats_lookup = daily_market_lookup(symbols)
    rows = []
    for relation, item in ranked:
        stats = stats_lookup.get(item["ticker"], {})
        group, climate_risk, note = etf_climate_profile(item["ticker"])
        momentum = safe_float(stats.get("period_return"), 0.0)
        rows.append(
            {
                "ticker": item["ticker"],
                "group": group,
                "role": item["role"],
                "stance": item["stance"],
                "relation_score": relation,
                "climate_risk": round(climate_risk, 4),
                "last": round(safe_float(stats.get("last"), 0.0), 4),
                "today_return": round(momentum, 5),
                "action": daily_climate_action(item["stance"], relation, momentum),
                "climate_link": note,
            }
        )
    return rows, market


def daily_climate_board_payload():
    daily_signal = load_daily_climate_signal()
    alert_rows = daily_climate_alert_rows(daily_signal)
    stock_rows, stock_market = daily_climate_stock_recommendations(daily_signal)
    etf_rows, etf_market = daily_climate_etf_recommendations(daily_signal)
    active_themes = [r["driver_label"] for r in alert_rows[:4]]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_mode": daily_signal.get("source_mode", "-"),
        "source_url": daily_signal.get("source_url", NWS_ACTIVE_ALERTS_URL),
        "alerts_total": daily_signal.get("alerts_total", 0),
        "climate_alerts": daily_signal.get("climate_alerts", 0),
        "top_driver": daily_signal.get("top_driver", "none"),
        "daily_pressure": daily_signal.get("daily_pressure", 0.0),
        "allocation_pressure": daily_signal.get("allocation_pressure", 0.0),
        "active_themes": active_themes,
        "market_source": stock_market.get("source") or etf_market.get("source"),
        "market_interval": stock_market.get("interval") or etf_market.get("interval"),
        "stock_recommendations": stock_rows,
        "etf_recommendations": etf_rows,
        "daily_alerts": alert_rows,
    }


def simulated_annual_returns(tickers):
    rng = random.Random(42)
    annual = {t: {} for t in tickers}
    for year in range(START_YEAR + 1, datetime.now().year + 1):
        market = rng.gauss(0.08, 0.13)
        for t in tickers:
            beta = {"XLE": 1.15, "XLU": 0.65, "XLI": 1.05, "XLK": 1.18, "XLF": 1.10}.get(t, 1)
            tilt = {"XLE": -0.005, "XLU": 0.012, "XLI": 0.003, "XLK": 0.025, "XLF": 0.006}.get(t, 0)
            annual[t][str(year)] = round(market * beta + tilt + rng.gauss(0, 0.06), 5)
    return annual


def extract_close_series(data, symbol, symbols):
    if data is None or not hasattr(data, "columns"):
        return None
    columns = data.columns
    try:
        if getattr(columns, "nlevels", 1) > 1:
            level0 = set(columns.get_level_values(0))
            level1 = set(columns.get_level_values(1))
            if "Close" in level0:
                close_frame = data["Close"]
                if hasattr(close_frame, "columns") and symbol in close_frame.columns:
                    return close_frame[symbol]
                if len(symbols) == 1:
                    return close_frame
            if symbol in level0:
                frame = data[symbol]
                if hasattr(frame, "columns") and "Close" in frame.columns:
                    return frame["Close"]
            if "Close" in level1:
                for key in [(symbol, "Close"), ("Close", symbol)]:
                    try:
                        return data[key]
                    except Exception:
                        continue
        if "Close" in columns:
            close = data["Close"]
            if hasattr(close, "columns") and symbol in close.columns:
                return close[symbol]
            return close
        if symbol in columns:
            return data[symbol]
    except Exception:
        return None
    return None


def fetch_annual_market_returns(tickers, cache_name="optimizer_backtest_returns_cache.json", start=f"{START_YEAR}-01-01"):
    symbols = []
    for raw in tickers:
        symbol = yahoo_symbol(raw)
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    if not symbols:
        return {}, "no symbols"

    cache = DATA_DIR / cache_name
    annual = {}
    source = None
    if yf is not None:
        try:
            data = yf.download(symbols, start=start, auto_adjust=True, progress=False, threads=True)
            if data is not None and not data.empty:
                for symbol in symbols:
                    series = extract_close_series(data, symbol, symbols)
                    if series is None and len(symbols) == 1 and "Close" in data:
                        series = data["Close"]
                    if series is None or not hasattr(series, "dropna"):
                        continue
                    series = series.dropna()
                    if len(series) > 30 and hasattr(series, "resample"):
                        yearly = series.resample("YE").last().pct_change().dropna()
                        if len(yearly):
                            annual[symbol] = {str(idx.year): round(float(v), 5) for idx, v in yearly.items()}
                if annual:
                    cache.write_text(json.dumps(annual, indent=2), encoding="utf-8")
                    source = "yfinance historical annual returns"
        except Exception:
            annual = {}

    if not annual and cache.exists():
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            annual = {symbol: cached.get(symbol, {}) for symbol in symbols if cached.get(symbol)}
            if annual:
                source = "cached historical annual returns"
        except Exception:
            annual = {}

    simulated = simulated_annual_returns(symbols)
    missing = [symbol for symbol in symbols if not annual.get(symbol)]
    for symbol in missing:
        annual[symbol] = simulated.get(symbol, {})
    if missing:
        source = (source + " plus deterministic fallback") if source else "deterministic simulated market data"
    return annual, source or "deterministic simulated market data"


def read_cached_daily_recommendation_backtest(max_age_hours=8):
    if DAILY_RECO_BACKTEST_CACHE.exists():
        age_hours = (time.time() - DAILY_RECO_BACKTEST_CACHE.stat().st_mtime) / 3600
        if age_hours <= max_age_hours:
            try:
                cached = json.loads(DAILY_RECO_BACKTEST_CACHE.read_text(encoding="utf-8"))
                cached["source"] = cached.get("source", "cached daily recommendation backtest")
                return cached
            except Exception:
                pass
    return None


def daily_recommendation_symbols():
    symbols = []
    for item in DAILY_CLIMATE_STOCKS:
        ticker = yahoo_symbol(item.get("ticker"))
        if ticker and ticker not in symbols:
            symbols.append(ticker)
    for ticker in DEFAULT_OPTIMIZER_STOCKS:
        symbol = yahoo_symbol(ticker)
        if symbol and symbol not in symbols:
            symbols.append(symbol)
    return symbols[:16]


def daily_stock_meta(symbol):
    for item in DAILY_CLIMATE_STOCKS:
        if yahoo_symbol(item.get("ticker")) == symbol:
            return item
    for item in DAILY_CLIMATE_ETFS:
        if yahoo_symbol(item.get("ticker")) == symbol:
            sector, climate_risk, note = etf_climate_profile(symbol)
            return {
                "ticker": symbol,
                "name": symbol,
                "theme": item.get("role", sector),
                "sector": sector,
                "stance": item.get("stance", "mixed"),
                "exposure": item.get("exposure", {}),
                "climate_risk": climate_risk,
                "note": note,
            }
    return {
        "ticker": symbol,
        "name": symbol,
        "theme": guess_sector(symbol),
        "sector": guess_sector(symbol),
        "stance": "mixed",
        "exposure": {},
        "note": "Fallback issuer profile from sector and market data.",
    }


def fetch_daily_close_history(symbols, period="3y"):
    symbols = [yahoo_symbol(s) for s in symbols if yahoo_symbol(s)]
    prices = {symbol: {} for symbol in symbols}
    source = "deterministic simulated daily closes"
    if yf is not None:
        try:
            data = yf.download(symbols, period=period, interval="1d", auto_adjust=True, progress=False, threads=True)
            if data is not None and not getattr(data, "empty", True):
                for symbol in symbols:
                    series = extract_close_series(data, symbol, symbols)
                    if series is None or not hasattr(series, "dropna"):
                        continue
                    for idx, value in series.dropna().items():
                        try:
                            date = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
                            close = safe_float(value, None)
                            if close and close > 0:
                                prices[symbol][date] = round(close, 4)
                        except Exception:
                            continue
                if any(prices.values()):
                    source = "yfinance daily adjusted closes"
        except Exception:
            prices = {symbol: {} for symbol in symbols}

    if not any(prices.values()):
        days = 820
        for symbol in symbols:
            rng = random.Random(sum(ord(c) for c in symbol) + 3200)
            price = 55 + (sum(ord(c) for c in symbol) % 220)
            for i in range(days):
                stamp = time.time() - (days - i) * 86400
                dt = datetime.fromtimestamp(stamp)
                if dt.weekday() >= 5:
                    continue
                beta = 0.85 + (sum(ord(c) for c in symbol) % 45) / 100
                drift = rng.gauss(0.00042, 0.014 * beta)
                price = max(3, price * (1 + drift))
                prices[symbol][dt.strftime("%Y-%m-%d")] = round(price, 4)
    else:
        simulated = fetch_daily_close_history_fallback(symbols)
        for symbol in symbols:
            if len(prices.get(symbol, {})) < 80:
                prices[symbol] = simulated.get(symbol, {})
                source += " plus deterministic fallback"
    return prices, source


def fetch_daily_close_history_fallback(symbols):
    prices = {}
    days = 820
    for symbol in symbols:
        rng = random.Random(sum(ord(c) for c in symbol) + 3200)
        price = 55 + (sum(ord(c) for c in symbol) % 220)
        prices[symbol] = {}
        for i in range(days):
            stamp = time.time() - (days - i) * 86400
            dt = datetime.fromtimestamp(stamp)
            if dt.weekday() >= 5:
                continue
            beta = 0.85 + (sum(ord(c) for c in symbol) % 45) / 100
            drift = rng.gauss(0.00042, 0.014 * beta)
            price = max(3, price * (1 + drift))
            prices[symbol][dt.strftime("%Y-%m-%d")] = round(price, 4)
    return prices


def trailing_returns_for_symbol(price_map, dates, idx, lookback=20):
    returns = []
    start = max(1, idx - lookback + 1)
    for j in range(start, idx + 1):
        prev = price_map.get(dates[j - 1])
        cur = price_map.get(dates[j])
        if prev and cur:
            returns.append(cur / prev - 1)
    return returns


def score_daily_recommendation(symbol, prices, dates, idx, climate_rows):
    price_map = prices.get(symbol, {})
    current = price_map.get(dates[idx])
    prior = price_map.get(dates[max(0, idx - 20)])
    if not current or not prior:
        return None
    returns = trailing_returns_for_symbol(price_map, dates, idx, lookback=20)
    if len(returns) < 8:
        return None
    momentum = current / prior - 1
    mean = sum(returns) / len(returns)
    vol = math.sqrt(sum((r - mean) ** 2 for r in returns) / max(1, len(returns) - 1))
    market_score = clamp(0.52 + 1.35 * momentum + 0.20 * mean, 0.02, 0.98)
    risk_score = clamp(1 - vol / 0.035, 0.02, 0.98)
    meta = daily_stock_meta(symbol)
    sector = meta.get("sector") or guess_sector(symbol)
    transition = sector_transition_profile(sector)
    climate_pressure = historical_climate_pressure_for_year(int(dates[idx][:4]), climate_rows)
    physical_sensitivity = COMPANY_SECTOR_SENSITIVITY.get(sector, 0.50)
    relation = sum(safe_float(v, 0.0) for v in (meta.get("exposure") or {}).values()) / max(1, len(meta.get("exposure") or {}))
    stance = meta.get("stance", "mixed")
    opportunity = safe_float(transition.get("opportunity"), 0.40)
    transition_risk = safe_float(transition.get("risk"), 0.50)
    event_beta = clamp(relation * climate_pressure, 0.0, 1.0)
    stance_bias = {"beneficiary": 0.18, "hedge": 0.11, "mixed": 0.02, "risk": -0.20}.get(stance, 0.0)
    if stance == "beneficiary":
        climate_alpha = 0.52 + stance_bias + 0.34 * event_beta + 0.18 * opportunity - 0.12 * transition_risk
    elif stance == "hedge":
        climate_alpha = 0.50 + stance_bias + 0.24 * event_beta + 0.08 * risk_score - 0.08 * transition_risk
    elif stance == "risk":
        climate_alpha = 0.50 + stance_bias - 0.32 * event_beta - 0.18 * transition_risk - 0.10 * physical_sensitivity * climate_pressure
    else:
        climate_alpha = 0.50 + stance_bias + 0.10 * event_beta + 0.12 * opportunity - 0.12 * transition_risk - 0.06 * physical_sensitivity * climate_pressure
    climate_resilience = clamp(
        climate_alpha
        + 0.12 * risk_score
        + 0.06 * market_score
        - 0.10 * max(0.0, -momentum),
        0.03,
        0.97,
    )
    sell_score = clamp(
        (0.55 if stance == "risk" else 0.22 if stance == "mixed" else 0.04)
        + 0.32 * event_beta
        + 0.22 * transition_risk
        + 0.12 * physical_sensitivity * climate_pressure
        - 0.18 * opportunity
        - 0.10 * market_score,
        0.01,
        0.99,
    )
    total_score = clamp(0.64 * climate_resilience + 0.24 * market_score + 0.12 * risk_score, 0.01, 0.99)
    return {
        "ticker": symbol,
        "name": meta.get("name", symbol),
        "sector": sector,
        "theme": meta.get("theme", sector),
        "stance": stance,
        "score": round(total_score, 4),
        "market_score": round(market_score, 4),
        "climate_resilience": round(climate_resilience, 4),
        "climate_signal_score": round(total_score, 4),
        "sell_score": round(sell_score, 4),
        "risk_score": round(risk_score, 4),
        "momentum_20d": round(momentum, 5),
        "volatility_20d": round(vol, 5),
        "physical_pressure": round(physical_sensitivity * climate_pressure, 4),
        "transition_risk": transition["risk"],
        "driver": f"{meta.get('theme', sector)}; climate signal {total_score:.0%}, market {market_score:.0%}, resilience {climate_resilience:.0%}.",
    }


def walk_forward_adjusted_score(score, style="balanced", horizon="long"):
    style = optimizer_style(style)
    horizon = optimizer_horizon(horizon)
    weights = {
        "balanced": (0.42, 0.36, 0.22),
        "climate_defense": (0.22, 0.56, 0.22),
        "growth": (0.58, 0.22, 0.20),
        "low_vol": (0.26, 0.30, 0.44),
    }.get(style, (0.42, 0.36, 0.22))
    market_w, climate_w, risk_w = weights
    if horizon == "short":
        market_w += 0.10
        climate_w -= 0.05
        risk_w -= 0.05
    else:
        market_w -= 0.03
        climate_w += 0.05
        risk_w -= 0.02
    total = market_w + climate_w + risk_w
    market_w, climate_w, risk_w = market_w / total, climate_w / total, risk_w / total
    return clamp(
        market_w * safe_float(score.get("market_score"), 0.50)
        + climate_w * safe_float(score.get("climate_resilience"), 0.50)
        + risk_w * safe_float(score.get("risk_score"), 0.50),
        0.01,
        0.99,
    )


def build_daily_recommendation_backtest_rows(symbols, prices, climate_rows, top_n=5):
    date_sets = [set(p.keys()) for p in prices.values() if p]
    if not date_sets:
        return []
    common_dates = sorted(set.intersection(*date_sets)) if len(date_sets) == len(symbols) else []
    all_dates = sorted(set.union(*date_sets))
    dates = common_dates if len(common_dates) >= 120 else all_dates
    rows = []
    for idx in range(25, len(dates) - 1):
        scored = []
        available = []
        for symbol in symbols:
            price_map = prices.get(symbol, {})
            current = price_map.get(dates[idx])
            nxt = price_map.get(dates[idx + 1])
            if not current or not nxt:
                continue
            score = score_daily_recommendation(symbol, prices, dates, idx, climate_rows)
            if score:
                scored.append(score)
                available.append(symbol)
        if len(scored) < 4:
            continue
        picks = sorted(scored, key=lambda r: r["score"], reverse=True)[:top_n]
        pick_symbols = [p["ticker"] for p in picks]
        model_returns = []
        bench_returns = []
        for symbol in available:
            current = prices[symbol].get(dates[idx])
            nxt = prices[symbol].get(dates[idx + 1])
            ret = nxt / current - 1 if current and nxt else 0.0
            bench_returns.append(ret)
            if symbol in pick_symbols:
                model_returns.append(ret)
        if not model_returns or not bench_returns:
            continue
        rows.append(
            {
                "date": dates[idx + 1],
                "signal_date": dates[idx],
                "recommended_return": round(sum(model_returns) / len(model_returns), 5),
                "benchmark_return": round(sum(bench_returns) / len(bench_returns), 5),
                "return_difference": round(sum(model_returns) / len(model_returns) - sum(bench_returns) / len(bench_returns), 5),
                "picks": ", ".join(pick_symbols),
                "top_drivers": "; ".join(p["driver"] for p in picks[:3]),
                "pick_details": picks,
                "coverage": f"{len(available)} / {len(symbols)}",
            }
        )
    return rows


def build_walk_forward_buy_sell_backtest_rows(
    symbols,
    prices,
    climate_rows,
    style="balanced",
    horizon="long",
    top_n=None,
    trading_cost_bps=10.0,
    annual_borrow_cost_bps=100.0,
):
    symbols = [yahoo_symbol(s) for s in symbols if yahoo_symbol(s)]
    date_sets = [set(prices.get(symbol, {}).keys()) for symbol in symbols if prices.get(symbol)]
    if not date_sets:
        return []
    common_dates = sorted(set.intersection(*date_sets)) if len(date_sets) == len(symbols) else []
    all_dates = sorted(set.union(*date_sets))
    dates = common_dates if len(common_dates) >= 120 else all_dates
    rows = []
    previous_positions = {}
    trading_cost_rate = clamp(safe_float(trading_cost_bps, 10.0), 0.0, 100.0) / 10_000
    daily_borrow_rate = clamp(safe_float(annual_borrow_cost_bps, 100.0), 0.0, 2_000.0) / 10_000 / 252
    for idx in range(25, len(dates) - 1):
        scored = []
        available = []
        next_returns = {}
        for symbol in symbols:
            price_map = prices.get(symbol, {})
            current = price_map.get(dates[idx])
            nxt = price_map.get(dates[idx + 1])
            if not current or not nxt:
                continue
            score = score_daily_recommendation(symbol, prices, dates, idx, climate_rows)
            if not score:
                continue
            adjusted = walk_forward_adjusted_score(score, style=style, horizon=horizon)
            score["score"] = round(adjusted, 4)
            score["signal_strength"] = round(abs(adjusted - 0.50) * 2, 4)
            scored.append(score)
            available.append(symbol)
            next_returns[symbol] = nxt / current - 1
        if len(scored) < 4:
            continue
        scored = sorted(scored, key=lambda r: r["score"], reverse=True)
        bucket = top_n or max(2, min(5, round(len(scored) * 0.28)))
        buy_count = min(bucket, max(1, len(scored) // 2))
        sell_count = min(bucket, max(1, len(scored) - buy_count))
        buys = scored[:buy_count]
        buy_set = {p["ticker"] for p in buys}
        sell_pool = [p for p in scored if p["ticker"] not in buy_set and p.get("stance") != "beneficiary"]
        sell_pool = sorted(sell_pool or [p for p in scored if p["ticker"] not in buy_set], key=lambda r: r.get("sell_score", 0.0), reverse=True)
        sells = sell_pool[:sell_count]
        buy_symbols = [p["ticker"] for p in buys]
        sell_symbols = [p["ticker"] for p in sells]
        buy_returns = [next_returns[s] for s in buy_symbols if s in next_returns]
        sell_returns = [next_returns[s] for s in sell_symbols if s in next_returns]
        bench_returns = [next_returns[s] for s in available if s in next_returns]
        if not buy_returns or not sell_returns or not bench_returns:
            continue
        long_book = sum(buy_returns) / len(buy_returns)
        sell_book = sum(sell_returns) / len(sell_returns)
        benchmark_return = sum(bench_returns) / len(bench_returns)
        gross_signal_return = long_book - 0.25 * sell_book
        positions = {symbol: 1.0 / len(buy_symbols) for symbol in buy_symbols}
        for symbol in sell_symbols:
            positions[symbol] = positions.get(symbol, 0.0) - 0.25 / len(sell_symbols)
        traded_notional = sum(
            abs(positions.get(symbol, 0.0) - previous_positions.get(symbol, 0.0))
            for symbol in set(positions) | set(previous_positions)
        )
        turnover = 0.5 * traded_notional
        short_notional = sum(abs(weight) for weight in positions.values() if weight < 0)
        transaction_cost = traded_notional * trading_cost_rate
        borrow_cost = short_notional * daily_borrow_rate
        total_cost = transaction_cost + borrow_cost
        signal_return = gross_signal_return - total_cost
        previous_positions = positions
        pick_details = []
        for item in buys:
            detail = dict(item)
            detail["stance"] = "Buy"
            detail["driver"] = f"BUY: {item.get('driver', '')}"
            pick_details.append(detail)
        for item in sells:
            detail = dict(item)
            detail["stance"] = "Sell / underweight"
            detail["driver"] = f"SELL: climate vulnerability score {item.get('sell_score', 0):.0%}; {item.get('driver', '')}"
            pick_details.append(detail)
        rows.append(
            {
                "date": dates[idx + 1],
                "signal_date": dates[idx],
                "recommended_return": round(signal_return, 5),
                "gross_recommended_return": round(gross_signal_return, 5),
                "benchmark_return": round(benchmark_return, 5),
                "return_difference": round(signal_return - benchmark_return, 5),
                "gross_return_difference": round(gross_signal_return - benchmark_return, 5),
                "long_book_return": round(long_book, 5),
                "sell_book_return": round(sell_book, 5),
                "turnover": round(turnover, 5),
                "traded_notional": round(traded_notional, 5),
                "transaction_cost": round(transaction_cost, 6),
                "borrow_cost": round(borrow_cost, 6),
                "total_cost": round(total_cost, 6),
                "gross_exposure": round(sum(abs(weight) for weight in positions.values()), 4),
                "net_exposure": round(sum(positions.values()), 4),
                "picks": ", ".join(buy_symbols),
                "sells": ", ".join(sell_symbols),
                "top_drivers": f"Buy {', '.join(buy_symbols[:3])}; Sell {', '.join(sell_symbols[:3])}",
                "pick_details": pick_details,
                "coverage": f"{len(available)} / {len(symbols)}",
            }
        )
    return rows


def build_portfolio_selection_backtest_rows(portfolio_rows, prices):
    selected = []
    for row in portfolio_rows or []:
        ticker = row.get("ticker")
        weight = safe_float(row.get("target_weight"), 0.0)
        if ticker and weight > 0:
            selected.append(
                {
                    "ticker": ticker,
                    "weight": weight,
                    "asset_type": row.get("asset_type", ""),
                    "sector": row.get("sector", ""),
                    "action": row.get("action", ""),
                    "driver": row.get("rationale", ""),
                }
            )
    if not selected:
        return []

    total_weight = sum(item["weight"] for item in selected) or 1.0
    for item in selected:
        item["weight"] = item["weight"] / total_weight

    date_sets = [set(prices.get(item["ticker"], {}).keys()) for item in selected if prices.get(item["ticker"])]
    if not date_sets:
        return []
    common_dates = sorted(set.intersection(*date_sets)) if len(date_sets) == len(selected) else []
    all_dates = sorted(set.union(*date_sets))
    dates = common_dates if len(common_dates) >= 120 else all_dates
    rows = []
    for idx in range(1, len(dates)):
        model_returns = []
        bench_returns = []
        covered = []
        for item in selected:
            price_map = prices.get(item["ticker"], {})
            prev = price_map.get(dates[idx - 1])
            cur = price_map.get(dates[idx])
            if not prev or not cur:
                continue
            ret = cur / prev - 1
            model_returns.append(ret * item["weight"])
            bench_returns.append(ret)
            covered.append(item)
        if not model_returns or not bench_returns:
            continue
        portfolio_return = sum(model_returns)
        benchmark_return = sum(bench_returns) / len(bench_returns)
        rows.append(
            {
                "date": dates[idx],
                "signal_date": dates[idx - 1],
                "recommended_return": round(portfolio_return, 5),
                "benchmark_return": round(benchmark_return, 5),
                "return_difference": round(portfolio_return - benchmark_return, 5),
                "picks": ", ".join(item["ticker"] for item in covered),
                "top_drivers": "; ".join(
                    f"{item['ticker']} {item['weight']:.1%} {item['action']}".strip() for item in covered[:4]
                ),
                "pick_details": [
                    {
                        "ticker": item["ticker"],
                        "name": item["ticker"],
                        "sector": item.get("sector", ""),
                        "theme": item.get("asset_type", ""),
                        "stance": item.get("action", ""),
                        "score": item["weight"],
                        "market_score": 0,
                        "climate_resilience": 0,
                        "transition_risk": 0,
                        "momentum_20d": 0,
                        "driver": item.get("driver", ""),
                    }
                    for item in covered
                ],
                "coverage": f"{len(covered)} / {len(selected)}",
            }
        )
    return rows


def max_drawdown_from_returns(returns):
    wealth = 1.0
    values = []
    for ret in returns:
        wealth *= 1 + ret
        values.append(wealth)
    return max_drawdown(values)


def summarize_daily_recommendation_window(rows, window_days, label):
    subset = rows[-window_days:] if len(rows) > window_days else list(rows)
    model_wealth = 1.0
    gross_model_wealth = 1.0
    bench_wealth = 1.0
    out_rows = []
    for row in subset:
        model_ret = safe_float(row.get("recommended_return"), 0.0)
        gross_model_ret = safe_float(row.get("gross_recommended_return"), model_ret)
        bench_ret = safe_float(row.get("benchmark_return"), 0.0)
        model_wealth *= 1 + model_ret
        gross_model_wealth *= 1 + gross_model_ret
        bench_wealth *= 1 + bench_ret
        out = dict(row)
        out["recommended_wealth"] = round(model_wealth, 4)
        out["gross_recommended_wealth"] = round(gross_model_wealth, 4)
        out["benchmark_wealth"] = round(bench_wealth, 4)
        out_rows.append(out)
    returns = [safe_float(r.get("recommended_return"), 0.0) for r in out_rows]
    bench_returns = [safe_float(r.get("benchmark_return"), 0.0) for r in out_rows]
    excess_returns = [model - bench for model, bench in zip(returns, bench_returns)]
    mean_excess = sum(excess_returns) / max(1, len(excess_returns))
    excess_vol = (
        math.sqrt(sum((value - mean_excess) ** 2 for value in excess_returns) / max(1, len(excess_returns) - 1))
        if len(excess_returns) > 1
        else 0.0
    )
    days = len(out_rows)
    annualized = model_wealth ** (252 / days) - 1 if days and model_wealth > 0 else 0.0
    information_ratio = mean_excess / excess_vol * math.sqrt(252) if excess_vol > 0 else 0.0
    average_daily_turnover = sum(safe_float(r.get("turnover"), 0.0) for r in out_rows) / max(1, days)
    total_reported_cost = sum(safe_float(r.get("total_cost"), 0.0) for r in out_rows)
    summary = {
        "label": label,
        "trading_days": days,
        "recommended_total_return": round(model_wealth - 1, 4),
        "gross_recommended_total_return": round(gross_model_wealth - 1, 4),
        "benchmark_total_return": round(bench_wealth - 1, 4),
        "excess_return": round(model_wealth - bench_wealth, 4),
        "excess_wealth_ratio": round(model_wealth / bench_wealth, 4) if bench_wealth else 0,
        "annualized_return": round(annualized, 4),
        "recommended_max_drawdown": round(max_drawdown_from_returns(returns), 4),
        "benchmark_max_drawdown": round(max_drawdown_from_returns(bench_returns), 4),
        "winning_days": sum(1 for r in out_rows if safe_float(r.get("return_difference"), 0.0) > 0),
        "hit_rate": round(sum(1 for value in excess_returns if value > 0) / max(1, days), 4),
        "information_ratio": round(information_ratio, 3),
        "average_daily_turnover": round(average_daily_turnover, 4),
        "annualized_turnover": round(average_daily_turnover * 252, 4),
        "reported_cost_sum": round(total_reported_cost, 4),
        "compounded_cost_drag": round(gross_model_wealth - model_wealth, 4),
        "latest_picks": out_rows[-1].get("pick_details", []) if out_rows else [],
    }
    return {"summary": summary, "rows": out_rows}


def daily_recommendation_backtest_payload(
    force_refresh=False,
    mode=None,
    capital=None,
    horizon=None,
    style=None,
    etfs="",
    stocks="",
    use_portfolio=False,
    trading_cost_bps=10.0,
    annual_borrow_cost_bps=100.0,
):
    if use_portfolio:
        optimizer = portfolio_optimizer_payload(
            mode=mode or "etf_stock",
            capital=capital or DEFAULT_PORTFOLIO_VALUE,
            horizon=horizon or "long",
            style=style or "balanced",
            etfs=etfs or "",
            stocks=stocks or "",
        )
        selected_rows = optimizer.get("rows", [])
        symbols = [r["ticker"] for r in selected_rows if r.get("ticker")]
        prices, source = fetch_daily_close_history(symbols, period="3y")
        climate_rows = climate_signal()
        rows = build_walk_forward_buy_sell_backtest_rows(
            symbols,
            prices,
            climate_rows,
            style=style or "balanced",
            horizon=horizon or "long",
            trading_cost_bps=trading_cost_bps,
            annual_borrow_cost_bps=annual_borrow_cost_bps,
        )
        windows = {
            "3w": summarize_daily_recommendation_window(rows, 15, "3 weeks"),
            "3m": summarize_daily_recommendation_window(rows, 63, "3 months"),
            "3y": summarize_daily_recommendation_window(rows, 756, "3 years"),
        }
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": source,
            "universe": symbols,
            "backtest_type": "climate_walk_forward_buy_sell",
            "cost_model": {
                "trading_cost_bps": round(clamp(safe_float(trading_cost_bps, 10.0), 0.0, 100.0), 2),
                "annual_borrow_cost_bps": round(clamp(safe_float(annual_borrow_cost_bps, 100.0), 0.0, 2_000.0), 2),
                "return_basis": "Net of modeled trading and borrow costs",
                "turnover_definition": "Half the sum of absolute position-weight changes; costs use full traded notional.",
            },
            "portfolio_context": {
                "mode": optimizer.get("mode"),
                "mode_label": optimizer.get("mode_label"),
                "style": optimizer.get("style"),
                "style_label": optimizer.get("style_label"),
                "horizon": optimizer.get("horizon"),
                "horizon_label": optimizer.get("horizon_label"),
                "capital": optimizer.get("capital"),
                "universe_mode": optimizer.get("universe_mode"),
                "selected_count": len(selected_rows),
                "selected_tickers": symbols,
            },
            "methodology": {
                "model": "Daily walk-forward climate buy/sell overlay using the current optimizer universe.",
                "selection": "For each historical signal date, the model scores only information available up to that date, buys the strongest climate-beneficiary/resilience bucket, and underweights or shorts the highest climate-vulnerability bucket for the next trading day.",
                "windows": "3 weeks, 3 months, and 3 years are recalculated from daily signal returns; the current portfolio is not used retroactively.",
                "costs": "Net returns deduct the selected trading cost from full traded notional and the selected annualized borrow cost from the 25% short sleeve.",
                "caveat": "Historical climate state uses point-in-time market features and lagged annual climate calibration; it does not reconstruct a complete archive of daily NWS alerts. Slippage, taxes, financing, and market-impact constraints remain excluded.",
            },
            "windows": windows,
        }

    if not force_refresh:
        cached = read_cached_daily_recommendation_backtest()
        if cached:
            return cached
    symbols = daily_recommendation_symbols()
    prices, source = fetch_daily_close_history(symbols, period="3y")
    climate_rows = climate_signal()
    rows = build_daily_recommendation_backtest_rows(symbols, prices, climate_rows, top_n=5)
    windows = {
        "3w": summarize_daily_recommendation_window(rows, 15, "3 weeks"),
        "3m": summarize_daily_recommendation_window(rows, 63, "3 months"),
        "3y": summarize_daily_recommendation_window(rows, 756, "3 years"),
    }
    payload = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "universe": symbols,
        "methodology": {
            "model": "Daily walk-forward stock recommendation using prior 20-day market trend, volatility, official annual climate pressure, and sector physical/transition risk.",
            "selection": "Each signal day selects the top five stocks; the next trading day return is compared with an equal-weight universe benchmark.",
            "windows": "3 weeks, 3 months, and 3 years are recalculated from daily model returns.",
            "caveat": "Historical NWS alert archives are not used here; live NWS is used for today's recommendation, while history uses official annual climate pressure plus sector source proxies.",
        },
        "windows": windows,
    }
    try:
        DAILY_RECO_BACKTEST_CACHE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return payload


def build_allocation_history():
    tickers = list(SECTOR_ETFS.keys())
    climate_rows = climate_signal()
    returns, source = fetch_etf_prices(tickers)
    years = sorted({int(y) for t in returns.values() for y in t.keys() if int(y) >= START_YEAR})
    allocation_rows = []
    for year in years:
        regime = regime_for_year(year, climate_rows)
        eq_w = {t: 1 / len(tickers) for t in tickers}
        cw = climate_weight_policy(regime["regime"])
        for ticker in tickers:
            allocation_rows.append(
                {
                    "year": year,
                    "ticker": ticker,
                    "sector": SECTOR_ETFS[ticker]["name"],
                    "benchmark_weight": round(eq_w[ticker], 4),
                    "climate_weight": round(cw[ticker], 4),
                    "action": allocation_action(cw[ticker], eq_w[ticker]),
                    "target_dollars": round(cw[ticker] * DEFAULT_PORTFOLIO_VALUE, 2),
                    "sector_note": SECTOR_ETFS[ticker]["client_note"],
                }
            )
    return allocation_rows, source


def allocation_action(weight, benchmark):
    diff = weight - benchmark
    if diff > 0.03:
        return "Overweight / Buy"
    if diff < -0.03:
        return "Underweight / Reduce"
    return "Hold near benchmark"


def max_drawdown(values):
    peak = -1e9
    worst = 0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            worst = min(worst, v / peak - 1)
    return worst


def company_scan(tickers):
    climate_rows = climate_signal()
    latest_score = climate_rows[-1]["climate_risk_score"]
    context = climate_data_context()
    pressure = max(0.02, min(0.24, (0.06 + latest_score * 0.025) * context["climate_pressure_multiplier"]))
    out = []
    for raw in tickers:
        ticker = yahoo_symbol(raw)
        if not ticker:
            continue
        info = {}
        returns = []
        source = "fallback"
        if yf is not None:
            try:
                tk = yf.Ticker(ticker)
                info = tk.info or {}
                hist = tk.history(period="3y", auto_adjust=True)
                if hist is not None and not hist.empty:
                    returns = hist["Close"].pct_change().dropna().tolist()
                    source = "yfinance"
            except Exception:
                info = {}
        if not returns:
            rng = random.Random(sum(ord(c) for c in ticker))
            returns = [rng.gauss(0.0004, 0.018) for _ in range(650)]
        sorted_ret = sorted(returns)
        tail_n = max(1, int(len(sorted_ret) * 0.05))
        market_cvar = sum(sorted_ret[:tail_n]) / tail_n
        sector = info.get("sector") or guess_sector(ticker)
        sensitivity = COMPANY_SECTOR_SENSITIVITY.get(sector, 0.50)
        market_cap = safe_float(info.get("marketCap"), fallback_market_cap(ticker))
        beta = safe_float(info.get("beta"), 1.0)
        method2 = method2_company_cvor(ticker, info=info)
        physical_var = market_cap * pressure * sensitivity * 0.48
        transition_var = market_cap * pressure * sensitivity * 0.37 * max(0.70, min(1.40, beta))
        litigation_var = market_cap * pressure * max(0.10, 1 - sensitivity) * 0.15
        climate_var = (physical_var + transition_var + litigation_var) * max(0.65, min(1.45, beta))
        cvor_ratio = climate_var / market_cap if market_cap else 0
        out.append(
            {
                "ticker": ticker,
                "company": info.get("shortName") or info.get("longName") or ticker,
                "sector": sector,
                "market_cap": round(market_cap, 2),
                "beta": round(beta, 3),
                "market_cvar_95": round(market_cvar, 5),
                "climate_pressure": round(pressure, 4),
                "sector_sensitivity": round(sensitivity, 3),
                "physical_var": round(physical_var, 2),
                "transition_var": round(transition_var, 2),
                "litigation_var": round(litigation_var, 2),
                "climate_var": round(climate_var, 2),
                "climate_var_pct_mcap": round(cvor_ratio, 4),
                "source": source,
                "method2_mean_pct": method2["method2_mean_pct"],
                "method2_p95_pct": method2["method2_p95_pct"],
                "method2_p99_pct": method2["method2_p99_pct"],
                "method2_cvor95_pct": method2["method2_cvor95_pct"],
                "method2_cvor95_dollars": method2["method2_cvor95_dollars"],
                "method2_2c_p95_pct": method2["method2_2c_p95_pct"],
                "method2_2c_p99_pct": method2["method2_2c_p99_pct"],
                "method2_2c_cvor95_pct": method2["method2_2c_cvor95_pct"],
                "method2_2c_cvor95_dollars": method2["method2_2c_cvor95_dollars"],
                "method2_p95_reduction_pct": method2["method2_p95_reduction_pct"],
                "method2_cvor95_reduction_pct": method2["method2_cvor95_reduction_pct"],
                "method2_discount_rate": method2["method2_discount_rate"],
                "method2_draws": method2["method2_draws"],
                "method2_current_warming": method2["method2_current_warming"],
                "method2_climate_data_year": method2["method2_climate_data_year"],
                "method2_co2_ppm": method2["method2_co2_ppm"],
                "method2_disaster_10y_avg": method2["method2_disaster_10y_avg"],
                "method2_climate_pressure_multiplier": method2["method2_climate_pressure_multiplier"],
                "method2_climate_source_mode": method2["method2_climate_source_mode"],
                "method2_data_quality_score": method2["method2_data_quality_score"],
                "method2_data_quality_label": method2["method2_data_quality_label"],
                "method2_data_quality_notes": method2["method2_data_quality_notes"],
                "action": issuer_action(market_cvar, sensitivity, beta, max(cvor_ratio, method2["method2_p95_pct"])),
            }
        )
    return out


def guess_sector(ticker):
    mapping = {
        "AAPL": "Technology",
        "MSFT": "Technology",
        "NVDA": "Technology",
        "XOM": "Energy",
        "CVX": "Energy",
        "JPM": "Financial Services",
        "BAC": "Financial Services",
        "NEE": "Utilities",
        "DUK": "Utilities",
        "CAT": "Industrials",
        "DE": "Industrials",
        "TRV": "Financial Services",
        "CB": "Financial Services",
        "FSLR": "Technology",
        "ENPH": "Technology",
        "AMZN": "Consumer Cyclical",
        "GOOGL": "Communication Services",
        "META": "Communication Services",
        "TSLA": "Consumer Cyclical",
    }
    return mapping.get(ticker, "Technology")


def fallback_market_cap(ticker):
    base = 80_000_000_000
    return base * (1 + (sum(ord(c) for c in ticker) % 25))


def issuer_action(cvar, sensitivity, beta, cvor_ratio=0.0):
    if cvor_ratio >= 0.10:
        return "Reduce / hedge climate concentration"
    if sensitivity >= 0.75 and beta >= 1.1:
        return "High climate VaR watchlist"
    if cvar < -0.035:
        return "Market-tail risk elevated"
    if sensitivity <= 0.40:
        return "Relatively adaptive exposure"
    return "Monitor with sector overlay"


def build_payload():
    climate_rows = climate_signal()
    official_climate = load_official_climate_data()
    context = climate_data_context()
    daily_signal = load_daily_climate_signal()
    allocation_rows, market_source = build_allocation_history()
    latest_year = max(r["year"] for r in allocation_rows)
    latest_alloc = apply_daily_climate_overlay([r for r in allocation_rows if r["year"] == latest_year], daily_signal)
    current_allocation_rows = [r for r in allocation_rows if r["year"] != latest_year] + latest_alloc
    scenario_rows, cvor_summary = climate_scenario_matrix(current_allocation_rows)
    climate_intelligence = climate_intelligence_payload(
        latest_alloc=latest_alloc,
        daily_signal=daily_signal,
        cvor_summary=cvor_summary,
        context=context,
    )
    latest_regime = regime_for_year(latest_year, climate_rows)
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "platform": "Jennison Climate-Finance Trading & Risk Platform",
        "climate_source": "NWS + NASA/NOAA/NCEI official inputs, with FEMA/EPA/EIA/NGFS/SEC source-ready risk mapping",
        "market_source": market_source,
        "methodology": "Target-reference climate scenario repricing plus a separate NWS event-nowcast overlay",
        "scenario_methodology": {
            "scope": "Country -> sector -> issuer -> portfolio",
            "physical_downscaling": "Country acute/chronic losses are scaled by sector vulnerability, then by issuer fixed-asset and labor-intensity ratios.",
            "transition_downscaling": "Macro earnings sensitivity is separated from business-model transition risk and opportunity.",
            "valuation": "Scenario-conditioned cash flows are discounted into an as-of-date value impact relative to a chosen reference scenario.",
            "probability": "No occurrence probabilities are assigned to NGFS-style scenarios.",
            "short_term": "NWS alerts affect event selection risk and tactical portfolio basis points, not long-run scenario probability.",
        },
        "method2_methodology": {
            "paper": "Dietz, Bowen, Dixon and Gradwell (2016), 'Climate value at risk' of global financial assets",
            "equation": "Climate VaR = PV(no-damage cash-flow growth path) - PV(climate-damaged cash-flow growth path), divided by PV(no-damage path).",
            "implementation": "Company-level approximation using U.S. issuer sector sensitivity, beta, market cap, cash-flow growth proxy, DICE-style damage function, and Monte Carlo uncertainty.",
            "draws": METHOD2_DRAWS,
            "discount_rate": METHOD2_DISCOUNT_RATE,
            "horizon": METHOD2_END_YEAR,
            "damage_function": "g(T)=0.0028*T^2+(alpha3*T)^7, with alpha3 sampled from 0 to 0.248.",
            "scenario_comparison": "Each issuer is evaluated under a BAU warming path and a 2C mitigation path. The 2C column excludes mitigation costs and shows climate-impact risk reduction.",
            "climate_data_upgrade": "Current warming, CO2 trend, and U.S. billion-dollar disaster frequency now come from NASA/NOAA/NCEI official data when available.",
        },
        "portfolio_value": DEFAULT_PORTFOLIO_VALUE,
        "latest_regime": latest_regime,
        "climate_rows": climate_rows,
        "official_climate_rows": official_climate.get("rows", []),
        "official_climate_sources": official_climate.get("source_urls", {}),
        "official_climate_notes": official_climate.get("source_notes", []),
        "climate_data_context": context,
        "climate_intelligence": climate_intelligence,
        "climate_data_sources": climate_intelligence.get("source_rows", []),
        "daily_climate_signal": daily_signal,
        "allocation_rows": current_allocation_rows,
        "latest_allocation": latest_alloc,
        "scenario_rows": scenario_rows,
        "cvor_summary": cvor_summary,
        "us_market_notes": US_MARKET_NOTES,
        "sector_meta": SECTOR_ETFS,
    }


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Jennison Climate-Finance Trading & Risk Platform</title>
  <style>
    :root {
      --bg:#f5f7fb; --panel:#ffffff; --panel2:#f9fbff; --line:#dbe3ef; --text:#172033;
      --muted:#66758f; --blue:#2463eb; --green:#078a4f; --red:#d93025; --amber:#b66a00;
      --shadow:0 8px 22px rgba(18,31,54,.08);
    }
    *{box-sizing:border-box}
    html{scroll-behavior:smooth}
    body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,Segoe UI,Arial,sans-serif;font-size:13px;line-height:1.35;-webkit-font-smoothing:antialiased}
    header{min-height:52px;display:flex;align-items:center;gap:14px;padding:8px 18px;border-bottom:1px solid var(--line);background:#fff;position:sticky;top:0;z-index:20;box-shadow:0 1px 12px rgba(18,31,54,.05)}
    .brand-dot{width:9px;height:24px;border-radius:0;background:#2563eb}
    h1{font-size:16px;margin:0;font-weight:800}
    .badge{padding:4px 8px;border:1px solid var(--line);border-radius:999px;background:#fff;color:var(--muted);font-size:12px}
    .layout{display:grid;grid-template-columns:280px minmax(0,1fr);gap:14px;padding:14px;max-width:1880px;margin:0 auto}
    aside{position:sticky;top:66px;height:calc(100vh - 80px);background:#fff;border:1px solid var(--line);border-radius:8px;padding:14px;overflow:auto}
    main{display:flex;flex-direction:column;gap:12px;min-width:0}
    label{font-weight:700;font-size:12px;color:#2d3a50;display:block;margin-bottom:6px}
    textarea,input,button,select{font:inherit}
    textarea,input,select{width:100%;border:1px solid #cfd9e8;border-radius:7px;padding:9px;background:#fff;color:var(--text)}
    textarea:focus,input:focus,select:focus{outline:2px solid rgba(37,99,235,.18);border-color:#8bb2ff}
    textarea{min-height:92px;resize:vertical}
    button{border:1px solid #bcd0ff;background:#2563eb;color:#fff;border-radius:7px;padding:9px 12px;font-weight:800;cursor:pointer}
    button.secondary{background:#fff;color:#2563eb}
    .hint{color:var(--muted);font-size:12px;line-height:1.45}
    .grid{display:grid;gap:8px}
    .grid.kpi{grid-template-columns:repeat(6,minmax(0,1fr))}
    .grid.two{grid-template-columns:1.35fr .85fr}
    .grid.three{grid-template-columns:repeat(3,minmax(0,1fr))}
    .grid.four{grid-template-columns:repeat(4,minmax(0,1fr))}
    .panel{background:var(--panel);border:1px solid var(--line);border-radius:8px;box-shadow:0 1px 0 rgba(20,35,60,.03);overflow:hidden;scroll-margin-top:72px}
    .panel-head{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border-bottom:1px solid #e9eef6;background:#fbfdff;font-weight:800}
    .panel-body{padding:12px;overflow:auto}
    .kpi-card{background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px;min-height:82px;overflow:hidden}
    .kpi-label{color:var(--muted);font-size:12px}
    .kpi-value{font-size:23px;font-weight:850;margin-top:5px;white-space:nowrap}
    .green{color:var(--green)} .red{color:var(--red)} .amber{color:var(--amber)} .blue{color:var(--blue)}
    table{width:100%;border-collapse:collapse;min-width:860px}
    #quoteTable{min-width:100%;table-layout:auto}
    #quoteTable th,#quoteTable td{padding:9px 7px;font-size:12px;white-space:nowrap}
    #allocationTable,#dailyStockTable,#dailyEtfRecoTable,#dailyAlertTable,#scenarioTable,#climateDataTable,#etfTable,#companyTable,#detailTable,#dailyImpactTable{min-width:860px}
    #optimizerTable{min-width:1320px}
    th,td{padding:8px;border-bottom:1px solid #edf1f7;text-align:left;vertical-align:top}
    th{font-size:12px;color:#52627c;background:#fbfcff}
    tr:hover{background:#f7fbff}
    .compact-table{min-width:620px}
    canvas{width:100%;height:260px;border:1px solid #e1e8f2;border-radius:6px;background:#fff}
    canvas.tall{height:390px}
    canvas.backtest-canvas{height:300px}
    .log{font-family:Consolas,monospace;background:#0f172a;color:#dbeafe;border-radius:7px;padding:10px;height:150px;overflow:auto;font-size:12px}
    .pill{display:inline-flex;align-items:center;gap:4px;border:1px solid #d7e1ef;border-radius:999px;padding:3px 7px;background:#fff;font-size:11px;margin:2px}
    .pill.high{background:#fff1f1;color:#b42318;border-color:#ffc9c2}
    .pill.ok{background:#edfdf5;color:#047857;border-color:#bbf7d0}
    .pill.info{background:#eff6ff;color:#1d4ed8;border-color:#bfdbfe}
    .section-title{font-size:13px;font-weight:850;margin:4px 0 8px}
    .toolbar{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-bottom:10px}
    .toolbar button{padding:7px 10px}
    .toolbar button.active{background:#0f172a;border-color:#0f172a}
    .toolbar .chart-tool{padding:6px 9px;font-size:12px}
    .chart-shell{position:relative;border:1px solid #dce5f1;border-radius:8px;background:#fff;overflow:hidden}
    .chart-shell.dark{background:#101827;border-color:#243247}
    .trading-chart{height:430px;min-height:360px}
    .indicator-chart{height:150px;border-top:1px solid #e6edf7}
    .chart-shell.dark .indicator-chart{border-top-color:#243247}
    .chart-readout{position:absolute;z-index:3;left:10px;top:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:6px 8px;border:1px solid rgba(148,163,184,.28);border-radius:7px;background:rgba(255,255,255,.88);backdrop-filter:blur(8px);font-size:12px;font-weight:750;color:#243147}
    .chart-shell.dark .chart-readout{background:rgba(15,23,42,.86);color:#dbeafe;border-color:#334155}
    .chart-readout span{white-space:nowrap}
    canvas.chart-fallback{display:none;height:560px;border:0;border-radius:0}
    .control-row{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px}
    .small-input{margin-bottom:8px}
    .mini-stat{display:inline-flex;align-items:center;gap:6px;margin-right:10px;color:var(--muted)}
    .signal-card{border:1px solid #dbe3ef;border-radius:8px;background:#fff;padding:10px;min-height:70px}
    .signal-card .label{color:var(--muted);font-size:11px;font-weight:750}
    .signal-card .value{font-size:20px;font-weight:850;margin-top:4px}
    .metric-strip{display:flex;gap:8px;overflow-x:auto;overflow-y:hidden;padding:2px 2px 10px;scroll-snap-type:x proximity;scrollbar-gutter:stable}
    .metric-strip .signal-card{flex:0 0 188px;scroll-snap-align:start}
    .metric-strip::-webkit-scrollbar{height:8px}
    .metric-strip::-webkit-scrollbar-track{background:#eef3f9;border-radius:999px}
    .metric-strip::-webkit-scrollbar-thumb{background:#b9c7da;border-radius:999px}
    .metric-strip::-webkit-scrollbar-thumb:hover{background:#8fa3bd}
    .data-note{display:flex;gap:8px;align-items:center;flex-wrap:wrap;color:var(--muted);font-size:12px}
    .side-nav{display:grid;gap:6px;margin-bottom:12px}
    .side-nav a{display:flex;align-items:center;justify-content:space-between;text-decoration:none;color:#25324a;border:1px solid #dbe3ef;border-radius:7px;padding:8px 9px;background:#fbfdff;font-weight:750}
    .side-nav a:hover{border-color:#9bbcff;background:#f3f7ff}
    .heat-strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(118px,1fr));gap:6px}
    .heat-cell{border:1px solid #dbe3ef;border-radius:7px;padding:8px;background:#fff;min-height:58px}
    .heat-cell .top{display:flex;align-items:center;justify-content:space-between;font-weight:850}
    .heat-cell .sub{font-size:11px;color:var(--muted);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .heat-cell.pos{background:#eefdf6;border-color:#b9f2d3}
    .heat-cell.neg{background:#fff2f1;border-color:#ffc8c2}
    .risk-meter{height:8px;border-radius:999px;background:#edf2f7;overflow:hidden;margin-top:6px}
    .risk-meter span{display:block;height:100%;border-radius:999px;background:#2563eb}
    .risk-meter span.warn{background:#b66a00}
    .risk-meter span.danger{background:#d93025}
    .client-summary{display:grid;grid-template-columns:1.1fr .9fr;gap:10px}
    .client-callout{border:1px solid #d7e1ef;border-radius:8px;background:#fff;padding:14px;min-height:132px}
    .client-callout .title{font-size:13px;font-weight:850;color:#52627c}
    .client-callout .headline{font-size:24px;font-weight:900;margin:6px 0;color:#172033}
    .score-bar{height:9px;border-radius:999px;background:#edf2f7;overflow:hidden;margin-top:8px}
    .score-bar span{display:block;height:100%;border-radius:999px;background:#2563eb}
    .score-bar span.warn{background:#b66a00}
    .score-bar span.danger{background:#d93025}
    .source-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:8px}
    .source-card{border:1px solid #dbe3ef;border-radius:8px;background:#fff;padding:10px;min-height:118px}
    .source-card .name{font-weight:850}
    .source-card .type{color:#52627c;font-size:12px;margin:3px 0 7px}
    .window-tabs{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:10px}
    .window-tabs button{padding:7px 10px}
    .split-table{display:grid;grid-template-columns:1fr 1fr;gap:10px}
    details.advanced-box{border:1px solid #dbe3ef;border-radius:8px;background:#fbfdff;padding:8px;margin:8px 0}
    details.advanced-box summary{cursor:pointer;font-weight:850;color:#25324a}
    .auto-universe-note{border:1px solid #dbe3ef;border-radius:8px;background:#f7fbff;padding:9px;color:#52627c;font-size:12px;line-height:1.45;margin:8px 0}
    .model-lab-controls{display:grid;grid-template-columns:1.05fr 1.25fr 1.25fr .8fr 1fr 1fr auto;gap:8px;align-items:end}
    .model-lab-controls label{margin-bottom:4px}
    .model-lab-controls button{height:36px;white-space:nowrap}
    .method-flow{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));border:1px solid #dbe3ef;border-radius:8px;background:#f8fbff;margin:10px 0;overflow:hidden}
    .method-step{padding:10px 11px;min-height:78px;border-right:1px solid #dbe3ef}
    .method-step:last-child{border-right:0}
    .method-step .number{font-size:11px;font-weight:850;color:#2563eb;text-transform:uppercase}
    .method-step .name{font-weight:850;margin-top:4px}
    .method-step .detail{font-size:11px;color:#66758f;margin-top:3px}
    .lab-kpi{grid-template-columns:repeat(6,minmax(0,1fr))}
    .lab-split{display:grid;grid-template-columns:1fr 1fr;gap:0;border-top:1px solid #e7edf6;border-bottom:1px solid #e7edf6;margin:10px 0}
    .lab-column{padding:12px 14px 12px 0;min-width:0}
    .lab-column+ .lab-column{padding-left:14px;border-left:1px solid #e7edf6}
    .lab-column h3{font-size:14px;margin:0 0 5px}
    .model-rule{display:flex;gap:12px;align-items:flex-start;background:#f3f7ff;border-left:4px solid #2563eb;padding:9px 11px;margin:10px 0;color:#33415b}
    .model-rule strong{white-space:nowrap}
    .attribution-list{display:grid;gap:7px;margin-top:10px}
    .attribution-row{display:grid;grid-template-columns:150px minmax(0,1fr) 72px;gap:8px;align-items:center;font-size:12px}
    .attribution-track{height:9px;background:#edf2f7;border-radius:999px;overflow:hidden;position:relative}
    .attribution-track span{display:block;height:100%;border-radius:999px;background:#d93025}
    .attribution-track span.positive{background:#078a4f}
    .lab-status{display:inline-flex;align-items:center;border:1px solid #c9d8ea;border-radius:999px;padding:3px 7px;font-size:11px;color:#52627c;background:#fff}
    #modelAttributionTable,#modelHazardTable,#modelResolutionTable,#modelInstrumentTable{min-width:720px}
    @media (max-width:1320px){.model-lab-controls{grid-template-columns:repeat(4,minmax(0,1fr))}.method-flow{grid-template-columns:repeat(3,minmax(0,1fr))}.method-step:nth-child(3){border-right:0}.method-step:nth-child(-n+3){border-bottom:1px solid #dbe3ef}.lab-kpi{grid-template-columns:repeat(3,minmax(0,1fr))}}
    @media (max-width:1100px){header{position:relative}.layout{grid-template-columns:1fr}.grid.kpi,.grid.two,.grid.three,.grid.four,.client-summary,.split-table,.lab-split{grid-template-columns:1fr}.model-lab-controls{grid-template-columns:1fr 1fr}.method-flow{grid-template-columns:1fr 1fr}.method-step{border-bottom:1px solid #dbe3ef}.method-step:nth-child(odd){border-right:1px solid #dbe3ef}.method-step:nth-child(even){border-right:0}.lab-column+ .lab-column{padding-left:0;border-left:0}.lab-kpi{grid-template-columns:1fr 1fr}aside{position:relative;top:0;height:auto}.kpi-value{font-size:21px}table{min-width:760px}}

    /* Institutional research workspace: hard-edged light, quiet data density. */
    :root{
      --bg:#f4f4ef;--panel:#ffffff;--panel2:#f8f8f4;--line:#d8d8d0;--text:#111318;
      --muted:#666861;--blue:#1549ff;--green:#008b62;--red:#d51f3f;--amber:#a85d00;
      --electric:#1c5cff;--cyan:#00c8e8;--acid:#b7ef18;--pink:#ff3aa7;--black:#111318;
      --shadow:none;
    }
    body{background:var(--bg);font-family:Inter,Arial,sans-serif;font-size:12px;line-height:1.4;letter-spacing:0}
    header{min-height:60px;padding:0 22px;background:#fff;border-bottom:1px solid var(--black);box-shadow:none;gap:13px}
    h1{font-size:15px;font-weight:800;letter-spacing:0}
    .light-mark{display:flex;align-items:flex-end;gap:3px;width:30px;height:24px}
    .light-mark span{display:block;width:5px;border-radius:0}
    .light-mark span:nth-child(1){height:24px;background:var(--electric);box-shadow:0 0 9px rgba(28,92,255,.55)}
    .light-mark span:nth-child(2){height:17px;background:var(--cyan);box-shadow:0 0 9px rgba(0,200,232,.5)}
    .light-mark span:nth-child(3){height:10px;background:var(--acid);box-shadow:0 0 8px rgba(183,239,24,.55)}
    .brand-dot{display:none}
    .badge{padding:4px 7px;border:0;border-left:2px solid var(--line);border-radius:0;background:transparent;color:var(--muted);font-size:10px;text-transform:uppercase;font-weight:700}
    .layout{grid-template-columns:214px minmax(0,1fr);gap:28px;padding:0 26px 40px;max-width:1900px}
    aside{top:60px;height:calc(100vh - 60px);padding:25px 18px 30px 0;background:transparent;border:0;border-right:1px solid var(--line);border-radius:0}
    main{gap:24px;padding-top:24px}
    #summary-section{order:1}#client-section{order:2}#optimizer-section{order:3}#model-lab-section{order:4}
    #cvor-section{order:5}#daily-reco-backtest-section{order:6}#climate-data-section{order:7}#issuer-section{order:8}
    .side-nav{gap:2px;margin:0 0 26px}
    .side-nav a{min-height:36px;padding:8px 9px;border:0;border-left:2px solid transparent;border-radius:0;background:transparent;color:#3c3e39;font-size:11px;font-weight:700}
    .side-nav a span{color:#92948d;font-size:9px;text-transform:uppercase}
    .side-nav a:hover,.side-nav a:focus{background:#fff;border-left-color:var(--electric);color:var(--black)}
    .side-block{padding:14px 0;border-top:1px solid var(--line)}
    .side-kicker{font-size:9px;font-weight:800;text-transform:uppercase;color:#8a8c84;margin-bottom:8px}
    .side-value{font-size:13px;font-weight:800;color:var(--black)}
    .side-copy{font-size:10px;color:var(--muted);margin-top:4px;line-height:1.45}
    .panel{position:relative;background:transparent;border:0;border-top:1px solid var(--black);border-bottom:1px solid var(--line);border-radius:0;box-shadow:none;overflow:visible;scroll-margin-top:76px}
    .panel::before{content:"";position:absolute;left:0;top:-2px;width:86px;height:3px;background:var(--electric);box-shadow:0 0 10px rgba(28,92,255,.42)}
    .panel.accent-acid::before{background:var(--acid);box-shadow:0 0 10px rgba(183,239,24,.5)}
    .panel.accent-cyan::before{background:var(--cyan);box-shadow:0 0 10px rgba(0,200,232,.45)}
    .panel.accent-pink::before{background:var(--pink);box-shadow:0 0 10px rgba(255,58,167,.35)}
    .panel-head{padding:15px 0 11px;background:transparent;border-bottom:1px solid var(--line);font-size:12px;letter-spacing:0}
    .panel-head>span:first-child{font-size:14px;font-weight:850}
    .panel-head>span:last-child{font-size:9px;color:var(--muted);text-transform:uppercase;font-weight:750;text-align:right}
    .panel-body{padding:16px 0 20px;overflow:auto}
    .grid{gap:7px}.grid.kpi{grid-template-columns:repeat(6,minmax(128px,1fr))}
    .kpi-card,.signal-card{background:#fff;border:1px solid var(--line);border-radius:2px;box-shadow:none}
    .kpi-card{min-height:86px;padding:13px}
    .kpi-label,.signal-card .label{font-size:9px;color:#777970;text-transform:uppercase;font-weight:800}
    .kpi-value{font-size:21px;font-weight:800;margin-top:8px;letter-spacing:0}
    .signal-card{min-height:76px;padding:11px}
    .signal-card .value{font-size:18px;font-weight:800;margin-top:6px}
    .client-summary{grid-template-columns:minmax(290px,.85fr) minmax(480px,1.15fr);gap:8px}
    .client-callout{position:relative;background:var(--black);color:#fff;border:0;border-radius:2px;padding:18px;min-height:158px;overflow:hidden}
    .client-callout::after{content:"";position:absolute;right:0;bottom:20px;width:7px;height:82px;background:var(--acid);box-shadow:0 0 13px rgba(183,239,24,.7)}
    .client-callout .title{color:#b9bbb5;font-size:9px;text-transform:uppercase}
    .client-callout .headline{font-size:28px;color:#fff;margin:10px 0 6px}
    .decision-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:8px}
    .decision-cell{background:#fff;border:1px solid var(--line);border-radius:2px;padding:12px;min-height:102px}
    .decision-cell .eyebrow{font-size:9px;color:var(--muted);text-transform:uppercase;font-weight:800}
    .decision-cell .decision{font-size:14px;font-weight:800;margin:7px 0 4px}
    .decision-cell .detail{font-size:10px;color:var(--muted)}
    .institution-controls{display:grid;grid-template-columns:1fr 1fr 1fr 1fr auto;gap:7px;align-items:end;margin-bottom:10px}
    .control-wide{grid-column:span 2}
    label{font-size:9px;text-transform:uppercase;color:#6d6f68;margin-bottom:5px}
    textarea,input,select{border:1px solid #cfcfc7;border-radius:2px;padding:8px;background:#fff;color:var(--text)}
    textarea:focus,input:focus,select:focus{outline:2px solid rgba(28,92,255,.14);border-color:var(--electric)}
    button{border:1px solid var(--black);background:var(--black);color:#fff;border-radius:2px;padding:8px 11px;font-weight:800}
    button:hover{background:var(--electric);border-color:var(--electric)}
    button.secondary{background:#fff;color:var(--black);border-color:#bfc0b9}
    button.secondary:hover{color:var(--electric);border-color:var(--electric)}
    .toolbar button.active,.window-tabs button.active{background:var(--electric);border-color:var(--electric)}
    .auto-universe-note,.model-rule{border:0;border-left:3px solid var(--cyan);border-radius:0;background:#f3fbfc;padding:9px 11px}
    details.advanced-box{border:1px solid var(--line);border-radius:2px;background:#fff;padding:9px;margin:8px 0}
    details.advanced-box summary{color:var(--black)}
    .method-flow{border:1px solid var(--line);border-radius:2px;background:#fff}
    .method-step{border-color:var(--line);min-height:84px}
    .method-step .number{color:var(--electric);font-size:9px}
    .method-step .detail{color:var(--muted)}
    .lab-split{border-color:var(--line)}
    .lab-column+.lab-column{border-color:var(--line)}
    .risk-budget-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:7px;margin-bottom:12px}
    .budget-checks{min-width:720px}
    .status-pass{color:var(--green);font-weight:800}.status-watch{color:var(--red);font-weight:800}.status-proxy{color:var(--amber);font-weight:800}
    table{background:#fff;min-width:780px}
    th,td{padding:8px 7px;border-bottom:1px solid #e7e7e1}
    th{font-size:9px;text-transform:uppercase;color:#666861;background:#f7f7f3;position:sticky;top:0;z-index:1}
    tr:hover{background:#f4f8ff}
    .pill{border-radius:2px;padding:3px 5px;font-size:9px;text-transform:uppercase;font-weight:800}
    .risk-meter,.score-bar,.attribution-track{border-radius:0;background:#e8e8e2}
    .risk-meter span,.score-bar span,.attribution-track span{border-radius:0}
    .metric-strip{gap:7px;padding-bottom:8px}
    .metric-strip .signal-card{flex-basis:170px}
    canvas{border:1px solid var(--line);border-radius:2px}
    .source-card,.heat-cell{border-radius:2px}
    .heat-cell.pos{background:#f0fff8}.heat-cell.neg{background:#fff4f6}
    .split-table>div{min-width:0;overflow:auto}
    .section-title{font-size:11px;text-transform:uppercase;margin:6px 0 8px}
    .disclosure-line{font-size:10px;color:var(--muted);padding:9px 0;border-top:1px solid var(--line)}
    .issuer-controls{display:grid;grid-template-columns:minmax(260px,1fr) auto;gap:7px;align-items:end;max-width:650px;margin-bottom:12px}
    .technical-details{margin-top:12px;border-top:1px solid var(--line);padding-top:10px}
    .technical-details summary{cursor:pointer;font-weight:800;font-size:11px;text-transform:uppercase}
    @media (max-width:1320px){.risk-budget-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.decision-grid{grid-template-columns:1fr 1fr}.institution-controls{grid-template-columns:repeat(3,minmax(0,1fr))}.control-wide{grid-column:span 1}}
    @media (max-width:1100px){header{position:sticky}.layout{grid-template-columns:1fr;padding:0 14px 30px;gap:12px}aside{position:relative;top:0;height:auto;border-right:0;border-bottom:1px solid var(--line);padding:10px 0}.side-nav{display:flex;overflow-x:auto;margin:0}.side-nav a{flex:0 0 auto;border-left:0;border-bottom:2px solid transparent}.side-nav a:hover{border-left:0;border-bottom-color:var(--electric)}.side-block{display:none}main{padding-top:10px}.grid.kpi{grid-template-columns:repeat(3,minmax(0,1fr))}.client-summary{grid-template-columns:1fr}.institution-controls{grid-template-columns:1fr 1fr}.model-lab-controls{grid-template-columns:1fr 1fr}.split-table,.lab-split{grid-template-columns:1fr}.lab-column+.lab-column{padding-left:0;border-left:0}.panel-head>span:last-child{max-width:48%}}
    @media (max-width:640px){header{padding:0 12px;min-height:54px}header .badge:not(#timeBadge){display:none}h1{font-size:13px}.layout{padding:0 10px 24px}.grid.kpi{grid-template-columns:1fr 1fr}.kpi-card{min-height:76px}.decision-grid,.risk-budget-grid,.institution-controls,.model-lab-controls,.lab-kpi{grid-template-columns:1fr}.grid.two,.grid.three,.grid.four{grid-template-columns:1fr}.method-flow{grid-template-columns:1fr}.method-step{border-right:0;border-bottom:1px solid var(--line)}.panel-head{align-items:flex-start;gap:10px}.panel-head>span:last-child{font-size:8px}.client-callout .headline{font-size:24px}.issuer-controls{grid-template-columns:1fr}table{min-width:700px}}

    /* Typography and color refinement: research-report restraint over dashboard decoration. */
    :root{
      --bg:#f1f3f2;--panel:#ffffff;--panel2:#f7f8f7;--line:#d3d8dc;--text:#17212b;
      --muted:#68737d;--blue:#355a8a;--green:#1e7358;--red:#b33f4a;--amber:#94671f;
      --electric:#355a8a;--cyan:#6b96a2;--acid:#bdca52;--pink:#8e778e;--black:#17212b;
    }
    body{font-family:Aptos,"Helvetica Neue","Segoe UI",Arial,sans-serif;font-size:12.5px;line-height:1.46;color:var(--text)}
    header{min-height:62px;border-bottom-color:#aeb6bc;gap:12px}
    h1{font-size:15px;font-weight:650}
    .light-mark{width:17px;height:25px;gap:2px}
    .light-mark span{width:3px}
    .light-mark span:nth-child(1){height:25px;background:#355a8a;box-shadow:none}
    .light-mark span:nth-child(2){height:18px;background:#c5a43b;box-shadow:none}
    .light-mark span:nth-child(3){height:11px;background:#a85b56;box-shadow:none}
    .badge{font-size:10.5px;text-transform:none;font-weight:500;color:#707b84}
    .side-nav a{font-size:12px;font-weight:600;color:#394650}
    .side-nav a span{font-size:10px;text-transform:none;color:#838c93}
    .side-kicker{font-size:10px;font-weight:600;text-transform:none;color:#78828a}
    .side-value{font-size:14px;font-weight:650}
    .side-copy{font-size:11px}
    .panel{border-top-color:#9ca6ad}
    .panel::before{width:48px;height:2px;background:var(--electric);box-shadow:none}
    .panel.accent-acid::before{background:#a8b748;box-shadow:none}
    .panel.accent-cyan::before{background:#668f9a;box-shadow:none}
    .panel.accent-pink::before{background:#867287;box-shadow:none}
    .panel-head{padding:19px 0 13px}
    .panel-head>span:first-child{font-size:17px;font-weight:650}
    .panel-head>span:last-child{font-size:10.5px;text-transform:none;font-weight:500;line-height:1.35}
    .panel-body{padding:19px 0 23px}
    .grid.kpi{gap:18px}
    .kpi-card{min-height:88px;padding:12px 2px;background:transparent;border:0;border-top:1px solid var(--line)}
    .kpi-label,.signal-card .label{font-size:10.5px;text-transform:none;font-weight:600;color:#6a747c}
    .kpi-value{font-size:24px;font-weight:650;margin-top:9px}
    .signal-card{min-height:78px;padding:10px 12px;background:transparent;border:0;border-left:1px solid var(--line)}
    .signal-card .value{font-size:20px;font-weight:650;margin-top:6px}
    .client-summary{gap:24px}
    .client-callout{min-height:158px;background:#fff;color:var(--text);border:1px solid var(--line);border-left:4px solid #a8b748;border-radius:0;padding:20px;overflow:visible}
    .client-callout::after{display:none}
    .client-callout .title{color:#6b757e;font-size:10.5px;text-transform:none;font-weight:600}
    .client-callout .headline{font-size:31px;font-weight:650;color:var(--text);margin:11px 0 7px}
    .client-callout .headline.red{color:var(--red)}.client-callout .headline.amber{color:var(--amber)}.client-callout .headline.green{color:var(--green)}
    .decision-grid{gap:18px;margin-top:18px}
    .decision-cell{background:transparent;border:0;border-top:1px solid var(--line);border-radius:0;padding:12px 2px;min-height:108px}
    .decision-cell .eyebrow{font-size:10.5px;text-transform:none;font-weight:600}
    .decision-cell .decision{font-size:16px;font-weight:650;margin:8px 0 5px}
    .decision-cell .detail{font-size:11px;line-height:1.45}
    label{font-size:10.5px;text-transform:none;font-weight:600;color:#68737c}
    textarea,input,select{border-color:#c7ced3;border-radius:0;padding:9px 10px;background:#fff}
    textarea:focus,input:focus,select:focus{outline:2px solid rgba(53,90,138,.12);border-color:var(--blue)}
    button{background:#233241;border-color:#233241;border-radius:0;font-weight:600;padding:9px 13px}
    button:hover{background:#355a8a;border-color:#355a8a}
    button.secondary{border-color:#b8c0c6;color:#34434e}
    .toolbar button.active,.window-tabs button.active{background:#355a8a;border-color:#355a8a}
    .auto-universe-note,.model-rule{border-left-color:#6b96a2;background:#f1f5f5;color:#3f4d56}
    .method-flow{border-radius:0}
    .method-step .number{font-size:10px;color:#496786;text-transform:none}
    .risk-budget-grid{gap:14px}
    th{font-size:10.5px;text-transform:none;font-weight:600;color:#56636d;background:#f3f5f4}
    th,td{padding:9px 8px;border-bottom-color:#e0e4e6}
    .pill{font-size:10px;text-transform:none;font-weight:600;border-radius:0}
    .score-bar,.risk-meter,.attribution-track{height:5px;background:#e2e6e5}
    .section-title{font-size:12px;text-transform:none;font-weight:650;margin:8px 0 10px}
    .technical-details summary{font-size:12px;text-transform:none;font-weight:600}
    .metric-strip{gap:14px}
    .metric-strip .signal-card{flex-basis:178px}
    #dailyRecoSummary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;overflow:visible;padding:0;margin:0 0 16px!important}
    #dailyRecoSummary .signal-card{min-width:0;min-height:82px;padding:12px 14px;border-left:1px solid var(--line)}
    #dailyRecoSummary .signal-card:nth-child(4n+1){border-left:0}
    #dailyRecoSummary .validation-primary{border-top:2px solid #6b96a2}
    #dailyRecoSummary .validation-primary .value{font-size:23px}
    #dailyRecoSummary .validation-diagnostic{border-top:1px solid var(--line)}
    #dailyRecoSummary .validation-diagnostic .value{font-size:18px}
    .validation-controls{display:grid;grid-template-columns:minmax(330px,1fr) 145px 145px auto;gap:10px;align-items:end;margin-bottom:14px}
    .validation-controls .window-tabs{margin:0;align-items:flex-end}
    .validation-details{margin-top:16px}
    #summary-section{order:1}#client-section{order:2}#optimizer-section{order:3}#daily-reco-backtest-section{order:4}
    #model-lab-section{order:5}#cvor-section{order:6}#climate-data-section{order:7}#issuer-section{order:8}
    @media (max-width:1100px){.validation-controls{grid-template-columns:1fr 1fr}.validation-controls .window-tabs{grid-column:1/-1}.client-summary{gap:12px}#dailyRecoSummary{grid-template-columns:repeat(2,minmax(0,1fr))}#dailyRecoSummary .signal-card:nth-child(4n+1){border-left:1px solid var(--line)}#dailyRecoSummary .signal-card:nth-child(2n+1){border-left:0}}
    @media (max-width:640px){body{font-size:12px}header{min-height:56px}h1{font-size:13px;font-weight:650}.panel-head>span:first-child{font-size:16px}.panel-head>span:last-child{font-size:9.5px}.grid.kpi{gap:8px}.kpi-card{min-height:78px}.kpi-label,.signal-card .label{font-size:10px}.kpi-value{font-size:21px}.client-callout .headline{font-size:27px}.validation-controls{grid-template-columns:1fr}.validation-controls .window-tabs{grid-column:auto}.decision-grid{gap:8px}#dailyRecoSummary .signal-card{padding:11px 8px}.validation-primary .value{font-size:21px}}
  </style>
</head>
<body>
<header>
  <div class="light-mark" aria-hidden="true"><span></span><span></span><span></span></div>
  <h1>Jennison Climate-Finance Trading & Risk Platform</h1>
  <span class="badge" id="regimeBadge">Loading regime...</span>
  <span class="badge" id="sourceBadge">Sources loading</span>
  <span style="margin-left:auto" class="badge" id="timeBadge">-</span>
</header>
<div class="layout">
  <aside>
    <nav class="side-nav" aria-label="Research workspace sections">
      <a href="#client-section">Investment View <span>Decision</span></a>
      <a href="#optimizer-section">Portfolio <span>Risk Budget</span></a>
      <a href="#daily-reco-backtest-section">Validation <span>Net of costs</span></a>
      <a href="#model-lab-section">Scenario Lab <span>Repricing</span></a>
      <a href="#cvor-section">Stress Matrix <span>Tail</span></a>
      <a href="#climate-data-section">Climate Signals <span>Lineage</span></a>
      <a href="#issuer-section">Issuer Deep Dive <span>Method 2</span></a>
    </nav>
    <div class="side-block">
      <div class="side-kicker">Research objective</div>
      <div class="side-value">Climate-aware alpha with explicit risk budgets</div>
      <div class="side-copy">Country-to-security repricing, live event transmission, portfolio construction, and point-in-time validation.</div>
    </div>
    <div class="side-block">
      <div class="side-kicker">Model status</div>
      <div class="side-value" id="sideModelStatus">Conditional, not probabilistic</div>
      <div class="side-copy">Scenario tail, pressure scores, and market risk remain separate to prevent double counting.</div>
    </div>
    <div class="side-block">
      <div class="side-kicker">Coverage discipline</div>
      <div class="side-value">Observed + proxy + gap</div>
      <div class="side-copy">Facility geolocation and company revenue/supply-chain mapping are shown as data gaps, never implied as observed inputs.</div>
    </div>
    <div class="side-block">
      <button class="secondary" onclick="loadDashboard()" style="width:100%">Refresh research view</button>
    </div>
  </aside>
  <main>
    <section class="grid kpi" id="summary-section">
      <div class="kpi-card"><div class="kpi-label">Portfolio state</div><div id="kpiRegime" class="kpi-value">-</div></div>
      <div class="kpi-card"><div class="kpi-label">Live NWS alerts</div><div id="kpiScore" class="kpi-value">-</div></div>
      <div class="kpi-card"><div class="kpi-label">Tactical pressure</div><div id="kpiReturn" class="kpi-value">-</div></div>
      <div class="kpi-card"><div class="kpi-label">Primary hazard</div><div id="kpiExcess" class="kpi-value">-</div></div>
      <div class="kpi-card"><div class="kpi-label">Climate vintage</div><div id="kpiDrawdown" class="kpi-value">-</div></div>
      <div class="kpi-card"><div class="kpi-label">Scenario tail</div><div id="kpiCvor" class="kpi-value">-</div></div>
    </section>

    <section class="panel accent-acid" id="client-section">
      <div class="panel-head"><span>Investment Committee View</span><span id="clientSummaryTag">Decision, evidence, confidence</span></div>
      <div class="panel-body">
        <div id="clientSummary" class="client-summary"></div>
        <div id="investmentCommitteeStrip" class="decision-grid"></div>
        <div class="section-title" style="margin-top:14px">Holdings requiring committee attention</div>
        <table id="clientAffectedTable"></table>
      </div>
    </section>

    <section class="panel accent-pink" id="model-lab-section">
      <div class="panel-head"><span>Scenario Repricing &amp; Event Transmission</span><span id="modelLabTag">Country -> sector -> issuer -> portfolio</span></div>
      <div class="panel-body">
        <div class="model-lab-controls">
          <div>
            <label for="modelScope">Analysis scope</label>
            <select id="modelScope" onchange="updateModelControlState()">
              <option value="portfolio">Portfolio</option>
              <option value="issuer">Issuer</option>
              <option value="sector">Sector</option>
              <option value="country">Country</option>
            </select>
          </div>
          <div>
            <label for="modelTarget">Target scenario</label>
            <select id="modelTarget">
              <option value="current_policies">Current Policies</option>
              <option value="net_zero_2050">Net Zero 2050</option>
              <option value="below_2c">Below 2C</option>
              <option value="delayed_transition">Delayed Transition</option>
              <option value="fragmented_world">Fragmented World</option>
            </select>
          </div>
          <div>
            <label for="modelReference">Reference scenario</label>
            <select id="modelReference">
              <option value="baseline">Climate-agnostic baseline</option>
              <option value="current_policies">Current Policies</option>
              <option value="net_zero_2050">Net Zero 2050</option>
              <option value="below_2c">Below 2C</option>
              <option value="delayed_transition">Delayed Transition</option>
            </select>
          </div>
          <div>
            <label for="modelHorizon">Horizon</label>
            <select id="modelHorizon">
              <option value="2030">2030</option>
              <option value="2040">2040</option>
              <option value="2050" selected>2050</option>
            </select>
          </div>
          <div>
            <label for="modelSector">Sector</label>
            <select id="modelSector">
              <option value="Technology">Technology</option>
              <option value="Energy">Energy</option>
              <option value="Utilities">Utilities</option>
              <option value="Industrials">Industrials</option>
              <option value="Financials">Financials</option>
              <option value="Real Estate">Real Estate</option>
              <option value="Basic Materials">Basic Materials</option>
              <option value="Consumer Cyclical">Consumer Cyclical</option>
              <option value="Consumer Defensive">Consumer Defensive</option>
              <option value="Healthcare">Healthcare</option>
              <option value="Communication Services">Communication Services</option>
            </select>
          </div>
          <div>
            <label for="modelTicker">Issuer ticker</label>
            <input id="modelTicker" value="AAPL" maxlength="12">
          </div>
          <button onclick="loadClimateModelLab()">Run Model</button>
        </div>

        <div class="model-rule">
          <strong>Quant rule</strong>
          <span>Long-term scenarios are conditional repricing exercises, not forecasts and not occurrence probabilities. NWS alerts feed the short-term event engine only.</span>
        </div>

        <div class="method-flow" aria-label="Climate model pipeline">
          <div class="method-step"><div class="number">01 Input</div><div class="name">Target vs reference</div><div class="detail">NGFS-style acute, chronic, macro and demand paths</div></div>
          <div class="method-step"><div class="number">02 Country</div><div class="name">Economic shock</div><div class="detail">Country GDP and transition pathway delta</div></div>
          <div class="method-step"><div class="number">03 Sector</div><div class="name">Vulnerability</div><div class="detail">Fixed assets, labor intensity and earnings beta</div></div>
          <div class="method-step"><div class="number">04 Issuer</div><div class="name">Cash-flow impact</div><div class="detail">Winsorized issuer-to-sector exposure ratio</div></div>
          <div class="method-step"><div class="number">05 Valuation</div><div class="name">As-of-date repricing</div><div class="detail">Discounted climate-adjusted cash-flow path</div></div>
          <div class="method-step"><div class="number">06 Decision</div><div class="name">Strategic + tactical</div><div class="detail">Long-term value tilt plus NWS event overlay</div></div>
        </div>

        <div id="modelLabSummary" class="grid lab-kpi"></div>
        <div class="lab-split">
          <div class="lab-column">
            <h3>Long-term: scenario-conditioned value</h3>
            <div id="modelLongHeadline" class="hint"></div>
            <div id="modelLongAttributionBars" class="attribution-list"></div>
          </div>
          <div class="lab-column">
            <h3>Short-term: NWS event nowcast</h3>
            <div id="modelShortHeadline" class="hint"></div>
            <div id="modelShortHazardBars" class="attribution-list"></div>
          </div>
        </div>

        <div class="split-table">
          <div>
            <div class="section-title">Long-Term Value Attribution</div>
            <table id="modelAttributionTable"></table>
          </div>
          <div>
            <div class="section-title">Short-Term Hazard Transmission</div>
            <table id="modelHazardTable"></table>
          </div>
        </div>
        <div class="split-table" style="margin-top:12px">
          <div>
            <div class="section-title">Largest Security / Sector Impacts</div>
            <table id="modelInstrumentTable"></table>
          </div>
          <div>
            <div class="section-title">Resolution &amp; Data Honesty</div>
            <table id="modelResolutionTable"></table>
          </div>
        </div>
        <div id="modelCalibrationNotice" class="hint" style="margin-top:10px"></div>
      </div>
    </section>

    <section class="panel accent-acid" id="daily-reco-backtest-section">
      <div class="panel-head"><span>Portfolio Validation</span><span id="dailyRecoBacktestTag">Point-in-time signal -> next trading day | net returns</span></div>
      <div class="panel-body">
        <div class="validation-controls">
          <div class="window-tabs">
            <button class="active reco-window-btn" onclick="setRecoBacktestWindow('3m', this)">3M evidence</button>
            <button class="secondary reco-window-btn" onclick="setRecoBacktestWindow('3y', this)">3Y evidence</button>
            <button class="secondary reco-window-btn" onclick="setRecoBacktestWindow('3w', this)">3W monitor</button>
          </div>
          <div>
            <label for="recoTradingCost">Trading cost</label>
            <select id="recoTradingCost">
              <option value="5">5 bps</option>
              <option value="10" selected>10 bps</option>
              <option value="20">20 bps</option>
            </select>
          </div>
          <div>
            <label for="recoBorrowCost">Annual borrow</label>
            <select id="recoBorrowCost">
              <option value="0">0 bps</option>
              <option value="100" selected>100 bps</option>
              <option value="300">300 bps</option>
            </select>
          </div>
          <button class="secondary" onclick="loadDailyRecommendationBacktest(true)">Recalculate</button>
        </div>
        <div id="dailyRecoSummary" class="metric-strip" style="margin-bottom:10px"></div>
        <canvas id="dailyRecoChart" class="backtest-canvas"></canvas>
        <details class="technical-details validation-details">
          <summary>Daily signal audit trail</summary>
          <div class="split-table" style="margin-top:10px">
            <div>
              <div class="section-title">Latest historical buy / sell signals</div>
              <table id="dailyRecoPickTable"></table>
            </div>
            <div>
              <div class="section-title">Recent walk-forward trading days</div>
              <table id="dailyRecoYearTable"></table>
            </div>
          </div>
        </details>
        <div id="dailyRecoNote" class="hint" style="margin-top:10px"></div>
      </div>
    </section>

    <section class="panel accent-cyan" id="climate-data-section">
      <div class="panel-head"><span>Climate Signals, Data Lineage &amp; Coverage</span><span id="dailyClimateTag">NWS + NASA + NOAA + NCEI</span></div>
      <div class="panel-body">
        <div id="dailyClimateSummary" class="risk-budget-grid" style="margin-bottom:10px"></div>
        <div class="split-table">
          <div>
            <div class="section-title">Live hazard tape</div>
            <table id="dailyAlertTable"></table>
          </div>
          <div>
            <div class="section-title">Allocation transmission</div>
            <table id="dailyImpactTable"></table>
          </div>
        </div>
        <div class="split-table" style="margin-top:14px">
          <div>
            <div class="section-title">Observed model inputs</div>
            <table id="climateDataTable"></table>
          </div>
          <div>
            <div class="section-title">Source lineage</div>
            <table id="clientSourceTable"></table>
          </div>
        </div>
        <div class="section-title" style="margin-top:14px">Coverage and known gaps</div>
        <table id="modelCoverageTable"></table>
        <div class="disclosure-line">Observed inputs, calibrated proxies, and data gaps are labeled separately. Facility geolocation and revenue/supply-chain mapping remain future data integrations.</div>
      </div>
    </section>

    <section class="panel accent-cyan" id="optimizer-section">
      <div class="panel-head"><span>Portfolio Construction &amp; Risk Budget</span><span id="optimizerTag">Automatic climate universe</span></div>
      <div class="panel-body">
        <div class="institution-controls">
          <div>
            <label for="optimizerMode">Instrument set</label>
            <select id="optimizerMode">
              <option value="etf_stock">ETF + stock</option>
              <option value="etf_only">ETF only</option>
              <option value="stock_only">Stock only</option>
            </select>
          </div>
          <div>
            <label for="optimizerHorizon">Decision horizon</label>
            <select id="optimizerHorizon">
              <option value="long">Long-term</option>
              <option value="short">Short-term</option>
            </select>
          </div>
          <div>
            <label for="optimizerStyle">Risk posture</label>
            <select id="optimizerStyle">
              <option value="balanced">Balanced</option>
              <option value="climate_defense">Climate defense</option>
              <option value="growth">Growth</option>
              <option value="low_vol">Low volatility</option>
            </select>
          </div>
          <div>
            <label for="optimizerCapital">Mandate capital</label>
            <input id="optimizerCapital" value="50000000" inputmode="numeric">
          </div>
          <button onclick="runOptimizer()">Rebuild portfolio</button>
        </div>
        <details class="advanced-box">
          <summary>Custom research universe</summary>
          <div class="grid two" style="margin-top:9px">
            <div><label for="optimizerEtfs">ETF override</label><textarea id="optimizerEtfs" placeholder="Optional: SPY, QQQ, XLK"></textarea></div>
            <div><label for="optimizerStocks">Stock override</label><textarea id="optimizerStocks" placeholder="Optional: AAPL, MSFT, NVDA"></textarea></div>
          </div>
        </details>
        <div class="auto-universe-note" id="optimizerUniverseNote">Automatic climate universe is loading.</div>
        <div id="optimizerDecision" class="decision-grid" style="margin-bottom:10px"></div>
        <div id="optimizerSummary" class="risk-budget-grid"></div>
        <div class="section-title">Risk-budget controls</div>
        <table id="riskBudgetTable" class="budget-checks"></table>
        <div class="section-title" style="margin-top:14px">Recommended holdings and climate active weights</div>
        <table id="optimizerTable"></table>
      </div>
    </section>

    <section class="panel accent-pink" id="cvor-section">
      <div class="panel-head"><span>Conditional Scenario Tail Matrix</span><span>Physical + transition + liability | no assigned probability</span></div>
      <div class="panel-body">
        <div id="scenarioSummary" class="risk-budget-grid"></div>
        <table id="scenarioTable"></table>
      </div>
    </section>

    <section class="panel accent-cyan" id="issuer-section">
      <div class="panel-head"><span>Issuer Climate-Risk Deep Dive</span><span>Method 2 valuation + security-level tail readout</span></div>
      <div class="panel-body">
        <div class="issuer-controls">
          <div><label for="tickerInput">Issuer universe</label><input id="tickerInput" value="AAPL, MSFT, XOM, NEE, JPM"></div>
          <button onclick="scanCompanies()">Run issuer analysis</button>
        </div>
        <div id="issuerHeatStrip" class="heat-strip" style="margin-bottom:12px"></div>
        <table id="companyTable"></table>
        <details class="technical-details">
          <summary>Technical component detail</summary>
          <div class="panel-body"><table id="detailTable"></table></div>
        </details>
        <div class="disclosure-line">Issuer outputs are valuation and tail-risk research proxies. Dollar losses should be read with the percentage-of-market-cap measure and data-quality label.</div>
      </div>
    </section>

  </main>
</div>
<script>
let DASH = null;
let OPTIMIZER = null;
let DAILY_CLIMATE_BOARD = null;
let DAILY_RECO_BACKTEST = null;
let CLIMATE_MODEL_LAB = null;
let RECO_BACKTEST_WINDOW = "3m";

function fmtPct(x){ return ((Number(x)||0)*100).toFixed(2)+"%"; }
function fmtMoney(x){ return "$"+Number(x||0).toLocaleString(undefined,{maximumFractionDigits:0}); }
function fmtPrice(x){ const n=Number(x); if(!Number.isFinite(n) || n<=0)return "-"; return "$"+n.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}); }
function fmtVolume(x){ const n=Number(x); if(!Number.isFinite(n) || n<=0)return "-"; if(n>=1e9)return (n/1e9).toFixed(2)+"B"; if(n>=1e6)return (n/1e6).toFixed(2)+"M"; if(n>=1e3)return (n/1e3).toFixed(1)+"K"; return String(Math.round(n)); }
function fmtBps(x){ const n=Number(x)||0; return (n>0?"+":"") + n.toFixed(0) + " bps"; }
function fmtSignedPct(x){ const n=Number(x)||0; return (n>0?"+":"") + (n*100).toFixed(2)+"%"; }
function clsFor(v){ return Number(v)>=0 ? "green" : "red"; }
function clamp(x, lo, hi){ return Math.max(lo, Math.min(hi, Number(x))); }

async function loadDashboard(){
  const res = await fetch("/api/dashboard");
  DASH = await res.json();
  renderDashboard(DASH);
  await Promise.allSettled([
    runOptimizer(),
    loadClimateModelLab(),
    scanCompanies(),
    loadDailyClimateBoard()
  ]);
  renderInvestmentCommittee();
}

function updateModelControlState(){
  const scope = document.getElementById("modelScope").value;
  const sector = document.getElementById("modelSector");
  const ticker = document.getElementById("modelTicker");
  sector.disabled = scope === "portfolio" || scope === "country";
  ticker.disabled = scope !== "issuer";
}

async function loadClimateModelLab(){
  updateModelControlState();
  const params = new URLSearchParams({
    scope: document.getElementById("modelScope").value,
    target: document.getElementById("modelTarget").value,
    reference: document.getElementById("modelReference").value,
    horizon: document.getElementById("modelHorizon").value,
    sector: document.getElementById("modelSector").value,
    ticker: document.getElementById("modelTicker").value
  });
  const res = await fetch("/api/climate_model_lab?" + params.toString());
  CLIMATE_MODEL_LAB = await res.json();
  renderClimateModelLab(CLIMATE_MODEL_LAB);
}

function renderAttributionBars(targetId, rows, valueKey, labelKey, positiveMeansGood=true){
  const el = document.getElementById(targetId);
  if(!el) return;
  const values = (rows || []).map(r=>Math.abs(Number(r[valueKey] || 0)));
  const maxAbs = Math.max(...values, 0.0001);
  el.innerHTML = (rows || []).slice(0,5).map(r=>{
    const value = Number(r[valueKey] || 0);
    const good = positiveMeansGood ? value >= 0 : value <= 0;
    const width = Math.max(3, Math.min(100, Math.abs(value)/maxAbs*100));
    const display = valueKey.includes("bps") ? fmtBps(value) : fmtSignedPct(value);
    return `<div class="attribution-row">
      <span>${r[labelKey] || "-"}</span>
      <div class="attribution-track"><span class="${good?"positive":""}" style="width:${width}%"></span></div>
      <b class="${good?"green":"red"}">${display}</b>
    </div>`;
  }).join("");
}

function renderClimateModelLab(d){
  if(!d || !d.long_term || !d.short_term) return;
  const lt = d.long_term;
  const st = d.short_term;
  const target = d.target || {};
  const reference = d.reference || {};
  document.getElementById("modelLabTag").textContent = `${d.scope_label} | ${target.label} vs ${reference.label} | ${d.horizon}`;
  const summary = document.getElementById("modelLabSummary");
  summary.innerHTML = [
    ["Scope", d.scope_label, ""],
    ["Value impact vs reference", fmtSignedPct(lt.value_impact), clsFor(lt.value_impact)],
    ["Physical loss delta", fmtSignedPct(lt.physical_loss_delta), clsFor(-lt.physical_loss_delta)],
    ["Transition loss delta", fmtSignedPct(lt.transition_loss_delta), clsFor(-lt.transition_loss_delta)],
    ["NWS event risk", fmtPct(st.event_risk), st.event_risk>=.55?"red":(st.event_risk>=.30?"amber":"green")],
    ["Tactical overlay", fmtBps(st.tactical_overlay_bps), clsFor(st.tactical_overlay_bps)]
  ].map(c=>`<div class="signal-card"><div class="label">${c[0]}</div><div class="value ${c[2]}">${c[1]}</div></div>`).join("");

  const valueDirection = lt.value_impact < 0 ? "lower" : (lt.value_impact > 0 ? "higher" : "unchanged");
  document.getElementById("modelLongHeadline").innerHTML = `If markets reprice from <b>${reference.label}</b> to <b>${target.label}</b>, the model values this ${d.scope} <b>${Math.abs(lt.value_impact*100).toFixed(2)}%</b> ${valueDirection}. This is a conditional valuation delta, not a forecast probability.`;
  document.getElementById("modelShortHeadline").innerHTML = `<b>${String(st.top_driver || "climate").replace("_"," ")}</b> is the dominant live driver. Event risk is ${fmtPct(st.event_risk)}, producing <b>${st.action}</b> at ${fmtBps(st.tactical_overlay_bps)} with ${fmtPct(st.data_confidence)} data confidence.`;

  renderAttributionBars("modelLongAttributionBars", lt.attribution || [], "value_contribution", "label", true);
  renderAttributionBars("modelShortHazardBars", (st.hazards || []).slice(0,5), "risk_contribution", "label", false);

  const attrTable = document.getElementById("modelAttributionTable");
  attrTable.innerHTML = `<tr><th>Component</th><th>Target loss</th><th>Reference loss</th><th>Loss delta</th><th>Value contribution</th></tr>` +
    (lt.attribution || []).map(r=>`<tr>
      <td><b>${r.label}</b></td><td>${fmtPct(r.target_loss)}</td><td>${fmtPct(r.reference_loss)}</td>
      <td class="${clsFor(-r.loss_delta)}">${fmtSignedPct(r.loss_delta)}</td>
      <td class="${clsFor(r.value_contribution)}"><b>${fmtSignedPct(r.value_contribution)}</b></td>
    </tr>`).join("");

  const hazardTable = document.getElementById("modelHazardTable");
  hazardTable.innerHTML = `<tr><th>Hazard</th><th>NWS intensity</th><th>Exposure beta</th><th>Risk contribution</th><th>Dominant exposure</th></tr>` +
    (st.hazards || []).map(r=>`<tr>
      <td><b>${r.label}</b></td><td>${fmtPct(r.intensity)}</td><td>${Number(r.exposure_beta||0).toFixed(2)}</td>
      <td class="amber">${fmtPct(r.risk_contribution)}</td><td>${r.dominant_exposure}</td>
    </tr>`).join("");

  const instrumentTable = document.getElementById("modelInstrumentTable");
  instrumentTable.innerHTML = `<tr><th>Name</th><th>Sector</th><th>Weight</th><th>Value impact</th><th>Acute ratio</th><th>Chronic ratio</th><th>Data</th></tr>` +
    (lt.instruments || []).slice(0,8).map(r=>`<tr>
      <td><b>${r.name}</b></td><td>${r.sector}</td><td>${fmtPct(r.weight)}</td>
      <td class="${clsFor(r.value_impact)}"><b>${fmtSignedPct(r.value_impact)}</b></td>
      <td>${Number(r.acute_ratio||0).toFixed(2)}x</td><td>${Number(r.chronic_ratio||0).toFixed(2)}x</td>
      <td><span class="lab-status">${r.data_quality || "Proxy"}</span></td>
    </tr>`).join("");

  const resolutionTable = document.getElementById("modelResolutionTable");
  resolutionTable.innerHTML = `<tr><th>Level</th><th>Model input</th><th>Status</th><th>Output</th></tr>` +
    (d.scope_resolution || []).map(r=>`<tr>
      <td><b>${r.level}</b></td><td>${r.input}</td><td><span class="lab-status">${r.status}</span></td><td>${r.output}</td>
    </tr>`).join("");
  document.getElementById("modelCalibrationNotice").textContent = `${d.calibration_notice} ${d.methodology.probability_rule} ${d.methodology.tail_rule}`;
  renderInvestmentCommittee();
}

async function loadDailyClimateBoard(){
  const res = await fetch("/api/daily_climate_board");
  DAILY_CLIMATE_BOARD = await res.json();
  renderDailyClimateBoard(DAILY_CLIMATE_BOARD);
}

async function loadDailyRecommendationBacktest(refresh=false){
  const params = new URLSearchParams({portfolio:"true"});
  if(refresh) params.set("refresh","true");
  const modeEl = document.getElementById("optimizerMode");
  const horizonEl = document.getElementById("optimizerHorizon");
  const styleEl = document.getElementById("optimizerStyle");
  const capitalEl = document.getElementById("optimizerCapital");
  const etfsEl = document.getElementById("optimizerEtfs");
  const stocksEl = document.getElementById("optimizerStocks");
  const tradingCostEl = document.getElementById("recoTradingCost");
  const borrowCostEl = document.getElementById("recoBorrowCost");
  if(modeEl) params.set("mode", modeEl.value);
  if(horizonEl) params.set("horizon", horizonEl.value);
  if(styleEl) params.set("style", styleEl.value);
  if(capitalEl) params.set("capital", capitalEl.value);
  if(etfsEl) params.set("etfs", etfsEl.value);
  if(stocksEl) params.set("stocks", stocksEl.value);
  if(tradingCostEl) params.set("trading_cost_bps", tradingCostEl.value);
  if(borrowCostEl) params.set("annual_borrow_cost_bps", borrowCostEl.value);
  const res = await fetch("/api/daily_recommendation_backtest?" + params.toString());
  DAILY_RECO_BACKTEST = await res.json();
  renderDailyRecommendationBacktest(DAILY_RECO_BACKTEST);
}

function setRecoBacktestWindow(key, btn){
  RECO_BACKTEST_WINDOW = key;
  document.querySelectorAll(".reco-window-btn").forEach(b=>{
    b.classList.remove("active");
    b.classList.add("secondary");
  });
  if(btn){
    btn.classList.add("active");
    btn.classList.remove("secondary");
  }
  renderDailyRecommendationBacktest(DAILY_RECO_BACKTEST);
}

function renderDailyClimateBoard(d){
  if(!d) return;
  const driver = String(d.top_driver || "none").replace("_"," ");
  const ci = (DASH && DASH.climate_intelligence) || {};
  document.getElementById("dailyClimateTag").textContent = `${d.source_mode} | ${d.market_interval || "1m"} market pulse`;
  document.getElementById("dailyClimateSummary").innerHTML = [
    ["Top driver", driver],
    ["Climate alerts", Number(d.climate_alerts || 0).toLocaleString()],
    ["Event pressure", fmtPct(d.daily_pressure || 0)],
    ["Tactical overlay", fmtPct((DASH && DASH.daily_climate_signal && DASH.daily_climate_signal.allocation_pressure) || 0)],
    ["Physical pressure", fmtPct(ci.physical_score || 0)],
    ["Transition pressure", fmtPct(ci.transition_score || 0)]
  ].map(c=>`<div class="signal-card"><div class="label">${c[0]}</div><div class="value">${c[1]}</div></div>`).join("");

  const alertTable = document.getElementById("dailyAlertTable");
  if(alertTable){
    alertTable.innerHTML = `<tr><th>Driver</th><th>Alerts</th><th>Intensity</th><th>Portfolio implication</th><th>Observed area</th></tr>` +
      (d.daily_alerts || []).map(r=>`<tr>
        <td><b>${r.driver_label}</b></td>
        <td>${Number(r.count || 0).toLocaleString()}</td>
        <td>${fmtPct(r.intensity)}</td>
        <td>${r.reminder}</td>
        <td>${r.sample_area || "-"}</td>
      </tr>`).join("");
  }
}

function renderDailyRecommendationBacktest(d){
  if(!d) return;
  const active = d.windows && d.windows[RECO_BACKTEST_WINDOW] ? d.windows[RECO_BACKTEST_WINDOW] : null;
  if(!active) return;
  const summary = active.summary || {};
  const rows = active.rows || [];
  const label = summary.label || RECO_BACKTEST_WINDOW.toUpperCase();
  const context = d.portfolio_context || {};
  const costs = d.cost_model || {};
  const tag = document.getElementById("dailyRecoBacktestTag");
  if(tag) tag.textContent = `${label} | net of ${Number(costs.trading_cost_bps || 0).toFixed(0)} bps trading + ${Number(costs.annual_borrow_cost_bps || 0).toFixed(0)} bps annual borrow | ${summary.trading_days || 0} days`;
  const summaryEl = document.getElementById("dailyRecoSummary");
  if(summaryEl){
    summaryEl.innerHTML = [
      ["Net signal return", fmtPct(summary.recommended_total_return || 0), clsFor(summary.recommended_total_return || 0), "After modeled costs", "validation-primary"],
      ["Net excess return", fmtPct(summary.excess_return || 0), clsFor(summary.excess_return || 0), `${Number(summary.excess_wealth_ratio || 0).toFixed(3)}x terminal wealth`, "validation-primary"],
      ["Maximum drawdown", fmtPct(summary.recommended_max_drawdown || 0), "red", "Net signal wealth", "validation-primary"],
      ["Information ratio", Number(summary.information_ratio || 0).toFixed(2), clsFor(summary.information_ratio || 0), `${fmtPct(summary.hit_rate || 0)} excess hit rate`, "validation-primary"],
      ["Gross signal return", fmtPct(summary.gross_recommended_total_return || 0), clsFor(summary.gross_recommended_total_return || 0), "Before modeled costs", "validation-diagnostic"],
      ["Universe benchmark", fmtPct(summary.benchmark_total_return || 0), clsFor(summary.benchmark_total_return || 0), context.mode_label || "Selected universe", "validation-diagnostic"],
      ["Compounded cost drag", fmtPct(summary.compounded_cost_drag || 0), "amber", `${fmtPct(summary.reported_cost_sum || 0)} summed daily cost`, "validation-diagnostic"],
      ["Annualized turnover", Number(summary.annualized_turnover || 0).toFixed(1) + "x", "blue", `${fmtPct(summary.average_daily_turnover || 0)} average daily`, "validation-diagnostic"]
    ].map(c=>`<div class="signal-card ${c[4]}"><div class="label">${c[0]}</div><div class="value ${c[2]}">${c[1]}</div><div class="hint">${c[3]}</div></div>`).join("");
  }
  if(rows.length){
    drawLineChart(
      "dailyRecoChart",
      rows.map(r=>String(r.date).slice(5)),
      [
        {name:"Climate signal, net", values:rows.map(r=>Number(r.recommended_wealth || 1)), color:"#18765d"},
        {name:"Equal-weight universe", values:rows.map(r=>Number(r.benchmark_wealth || 1)), color:"#6b7480"}
      ]
    );
  }
  const pickTable = document.getElementById("dailyRecoPickTable");
  if(pickTable){
    const picks = summary.latest_picks || [];
    pickTable.innerHTML = `<tr><th>Ticker</th><th>Signal</th><th>Score</th><th>Market</th><th>Climate</th><th>Driver</th></tr>` +
      picks.map(p=>`<tr>
        <td><b>${p.ticker}</b><br><span class="hint">${p.name || ""}</span></td>
        <td><span class="pill ${String(p.stance || "").includes("Sell") ? "high" : "ok"}">${p.stance || "-"}</span><br><span class="hint">${p.theme || p.sector || ""}</span></td>
        <td><b>${Number(p.score || 0).toFixed(2)}</b></td>
        <td>${Number(p.market_score || 0).toFixed(2)}<br><span class="hint">${fmtPct(p.momentum_20d || 0)} 20D</span></td>
        <td>${Number(p.climate_resilience || 0).toFixed(2)}<br><span class="hint">Transition ${fmtPct(p.transition_risk || 0)}</span></td>
        <td>${p.driver || "-"}</td>
      </tr>`).join("");
  }
  const dayTable = document.getElementById("dailyRecoYearTable");
  if(dayTable){
    dayTable.innerHTML = `<tr><th>Date</th><th>Buy signals</th><th>Sell signals</th><th>Net</th><th>Gross</th><th>Benchmark</th><th>Excess</th><th>Turnover / cost</th></tr>` +
      rows.slice(-18).reverse().map(r=>`<tr>
        <td><b>${r.date}</b><br><span class="hint">signal ${r.signal_date}</span></td>
        <td>${r.picks}</td>
        <td>${r.sells || "-"}</td>
        <td class="${clsFor(r.recommended_return)}">${fmtPct(r.recommended_return)}</td>
        <td class="${clsFor(r.gross_recommended_return)}">${fmtPct(r.gross_recommended_return)}</td>
        <td class="${clsFor(r.benchmark_return)}">${fmtPct(r.benchmark_return)}</td>
        <td class="${clsFor(r.return_difference)}"><b>${fmtPct(r.return_difference)}</b></td>
        <td>${fmtPct(r.turnover || 0)}<br><span class="hint">${Number((r.total_cost || 0)*10000).toFixed(1)} bps | coverage ${r.coverage}</span></td>
      </tr>`).join("");
  }
  const note = document.getElementById("dailyRecoNote");
  if(note && d.methodology){
    note.textContent = `${d.methodology.model} ${d.methodology.selection} ${d.methodology.costs || ""} ${d.methodology.caveat}`;
  }
  renderInvestmentCommittee();
}

async function runOptimizer(){
  const params = new URLSearchParams({
    mode: document.getElementById("optimizerMode").value,
    horizon: document.getElementById("optimizerHorizon").value,
    style: document.getElementById("optimizerStyle").value,
    capital: document.getElementById("optimizerCapital").value,
    etfs: document.getElementById("optimizerEtfs").value,
    stocks: document.getElementById("optimizerStocks").value
  });
  const res = await fetch("/api/portfolio_optimizer?"+params.toString());
  OPTIMIZER = await res.json();
  renderOptimizer(OPTIMIZER);
  await loadDailyRecommendationBacktest(true);
}

function renderOptimizer(o){
  if(!o) return;
  document.getElementById("optimizerTag").textContent = `${o.universe_mode || "Automatic climate universe"} | ${o.mode_label} | ${o.horizon_label} | ${fmtMoney(o.capital)}`;
  const universeNote = document.getElementById("optimizerUniverseNote");
  if(universeNote){
    universeNote.innerHTML = `<b>${o.universe_mode || "Automatic climate universe"}</b><br>${o.universe_note || ""}<br><span class="hint">ETFs: ${(o.auto_etfs || []).slice(0,6).join(", ")}${(o.auto_etfs || []).length>6?", ...":""}<br>Stocks: ${(o.auto_stocks || []).slice(0,6).join(", ")}${(o.auto_stocks || []).length>6?", ...":""}</span>`;
  }
  const summary = document.getElementById("optimizerSummary");
  const budget = o.risk_budget || {};
  const view = o.investment_view || {};
  const decision = document.getElementById("optimizerDecision");
  if(decision){
    decision.innerHTML = [
      ["Portfolio posture", view.posture || "-", view.strategic_action || "-"],
      ["Tactical control", o.horizon_label || "-", view.tactical_action || "-"],
      ["Largest risk contributor", budget.largest_risk_contributor || "-", `Weighted holding-tail proxy ${fmtPct(budget.weighted_tail_proxy || 0)}`],
      ["Largest climate tilt", budget.largest_climate_overweight || "-", `${fmtBps((budget.largest_climate_overweight_delta || 0)*10000)} vs market-only; ${budget.largest_climate_underweight || "-"} ${fmtBps((budget.largest_climate_underweight_delta || 0)*10000)}`]
    ].map(c=>`<div class="decision-cell"><div class="eyebrow">${c[0]}</div><div class="decision">${c[1]}</div><div class="detail">${c[2]}</div></div>`).join("");
  }
  summary.innerHTML = [
    ["Climate active share", fmtPct(budget.climate_active_share || 0), "Allocation difference vs market-only"],
    ["Weighted tail proxy", fmtPct(budget.weighted_tail_proxy || 0), fmtMoney(budget.capital_at_tail_proxy || 0)],
    ["Effective positions", Number(budget.effective_positions || 0).toFixed(1), `HHI ${Number(budget.hhi || 0).toFixed(3)}`],
    ["Largest position", fmtPct(budget.max_position || 0), `${budget.top_sector || "-"} ${fmtPct(budget.top_sector_weight || 0)}`],
    ["Physical pressure", fmtPct(budget.weighted_physical_risk || 0), "Weight-averaged issuer exposure"],
    ["Transition pressure", fmtPct(budget.weighted_transition_risk || 0), `${fmtPct(budget.weighted_confidence || 0)} evidence confidence`]
  ].map(c=>`<div class="signal-card"><div class="label">${c[0]}</div><div class="value">${c[1]}</div><div class="hint">${c[2]}</div></div>`).join("");

  const riskTable = document.getElementById("riskBudgetTable");
  if(riskTable){
    riskTable.innerHTML = `<tr><th>Control</th><th>Portfolio</th><th>Watch level</th><th>Status</th><th>Interpretation</th></tr>` +
      (budget.checks || []).map(r=>{
        const isEffective = String(r.name || "").includes("Effective");
        const displayValue = isEffective ? Number(r.value || 0).toFixed(2) : fmtPct(r.value || 0);
        const displayLimit = isEffective ? `>= ${Number(r.limit || 0).toFixed(1)}` : `<= ${fmtPct(r.limit || 0)}`;
        const cls = r.status === "Pass" ? "status-pass" : "status-watch";
        return `<tr><td><b>${r.name}</b></td><td>${displayValue}</td><td>${displayLimit}</td><td class="${cls}">${r.status}</td><td>${r.interpretation}</td></tr>`;
      }).join("");
  }
  const table = document.getElementById("optimizerTable");
  table.innerHTML = `<tr><th>Ticker</th><th>Sector</th><th>Target</th><th>Market-only</th><th>Climate active</th><th>Capital</th><th>Base alpha</th><th>Climate alpha</th><th>Tail proxy</th><th>Confidence</th><th>Action</th><th>Investment rationale</th></tr>` +
    (o.rows || []).map(r=>`<tr>
      <td><b>${r.ticker}</b><br><span class="hint">${r.asset_type}</span></td>
      <td>${r.sector}</td>
      <td><b>${fmtPct(r.target_weight)}</b></td>
      <td>${fmtPct(r.market_only_weight || 0)}</td>
      <td class="${clsFor(r.climate_weight_delta || 0)}"><b>${fmtBps((r.climate_weight_delta || 0) * 10000)}</b></td>
      <td>${fmtMoney(r.target_dollars)}</td>
      <td>${Number(r.base_alpha || 0).toFixed(2)}<br><span class="hint">${fmtPct(r.momentum)} move</span></td>
      <td class="${clsFor(r.climate_alpha || 0)}">${Number(r.climate_alpha || 0).toFixed(2)}<br><span class="hint">P ${fmtPct(r.physical_risk || 0)} / T ${fmtPct(r.transition_risk || 0)}</span></td>
      <td class="amber">${fmtPct(r.cvor_proxy || 0)}<br><span class="hint">penalty ${fmtPct(r.cvor_penalty || 0)}</span></td>
      <td>${fmtPct(r.data_confidence || 0)}<br><span class="hint">cap ${fmtPct(r.confidence_cap || 0)}</span></td>
      <td><span class="pill ${r.action.includes("Core") || r.action.includes("Add") ? "ok" : (r.action.includes("watch") ? "high" : "info")}">${r.action}</span></td>
      <td>${r.rationale}</td>
    </tr>`).join("");
  renderInvestmentCommittee();
}

function scoreClass(score){
  const n = Number(score || 0);
  if(n >= 0.66) return "danger";
  if(n >= 0.44) return "warn";
  return "";
}

function renderScoreBar(score){
  const n = Math.max(0, Math.min(1, Number(score || 0)));
  return `<div class="score-bar"><span class="${scoreClass(n)}" style="width:${Math.max(3, n*100)}%"></span></div>`;
}

function renderClientClimateIntelligence(ci){
  const summary = document.getElementById("clientSummary");
  if(!summary) return;
  const riskClass = ci.risk_level === "High" ? "red" : (ci.risk_level === "Elevated" ? "amber" : "green");
  document.getElementById("clientSummaryTag").textContent = `${ci.risk_level || "Watch"} | independent pressure and tail controls | ${fmtPct(ci.confidence || 0)} confidence`;
  summary.innerHTML = `
    <div class="client-callout">
      <div class="title">Current portfolio risk posture</div>
      <div class="headline ${riskClass}">${ci.risk_level || "Watch"}</div>
      <div>${ci.client_action || "-"}</div>
      ${renderScoreBar(ci.decision_score || ci.total_score || 0)}
      <div class="hint" style="margin-top:8px">${ci.headline || ""}</div>
    </div>
    <div class="grid two">
      <div class="signal-card"><div class="label">Physical pressure</div><div class="value ${clsFor(.44-(ci.physical_score || 0))}">${fmtPct(ci.physical_score || 0)}</div>${renderScoreBar(ci.physical_score || 0)}<div class="hint">Severity index, not event probability</div></div>
      <div class="signal-card"><div class="label">Transition pressure</div><div class="value ${clsFor(.44-(ci.transition_score || 0))}">${fmtPct(ci.transition_score || 0)}</div>${renderScoreBar(ci.transition_score || 0)}<div class="hint">Sector + macro transition state</div></div>
      <div class="signal-card"><div class="label">Conditional scenario tail</div><div class="value amber">${fmtPct(ci.scenario_tail_loss_rate || 0)}</div>${renderScoreBar(ci.scenario_tail_score || 0)}<div class="hint">Mean of two worst scenario losses</div></div>
      <div class="signal-card"><div class="label">Evidence confidence</div><div class="value blue">${fmtPct(ci.confidence || 0)}</div>${renderScoreBar(ci.confidence || 0)}<div class="hint">Observed inputs plus proxy coverage</div></div>
    </div>`;
  const affected = document.getElementById("clientAffectedTable");
  if(affected){
    const rows = ci.top_affected || [];
    affected.innerHTML = `<tr><th>Holding</th><th>Sector</th><th>Weight</th><th>Physical</th><th>Transition</th><th>Action</th><th>Driver</th></tr>` +
      rows.map(r=>`<tr>
        <td><b>${r.ticker}</b></td>
        <td>${r.sector}</td>
        <td>${fmtPct(r.weight)}</td>
        <td>${fmtPct(r.physical_risk)}</td>
        <td>${fmtPct(r.transition_risk)}</td>
        <td><span class="pill ${r.action.includes("Hedge") ? "high" : (r.action.includes("Watch") ? "info" : "ok")}">${r.action}</span></td>
        <td>${r.driver || "-"}</td>
      </tr>`).join("");
  }
  const sourceTable = document.getElementById("clientSourceTable");
  if(sourceTable){
    const rows = (ci.source_rows || []).slice(0, 8);
    sourceTable.innerHTML = `<tr><th>Source</th><th>Risk Type</th><th>Status</th><th>Model Use</th></tr>` +
      rows.map(r=>`<tr>
        <td><b>${r.name}</b></td>
        <td>${r.risk_type}</td>
        <td><span class="pill ${String(r.model_mode || "").includes("input") ? "ok" : "info"}">${r.status}</span></td>
        <td>${r.client_use}</td>
      </tr>`).join("");
  }
  renderInvestmentCommittee();
}

function renderInvestmentCommittee(){
  const el = document.getElementById("investmentCommitteeStrip");
  if(!el || !DASH) return;
  const ci = DASH.climate_intelligence || {};
  const view = (OPTIMIZER && OPTIMIZER.investment_view) || {};
  const budget = (OPTIMIZER && OPTIMIZER.risk_budget) || {};
  const shortTerm = (CLIMATE_MODEL_LAB && CLIMATE_MODEL_LAB.short_term) || {};
  const threeMonth = DAILY_RECO_BACKTEST && DAILY_RECO_BACKTEST.windows ? DAILY_RECO_BACKTEST.windows["3m"] : null;
  const validation = threeMonth && threeMonth.summary
    ? `${fmtPct(threeMonth.summary.recommended_total_return || 0)} net signal vs ${fmtPct(threeMonth.summary.benchmark_total_return || 0)} universe`
    : "Walk-forward evidence loading";
  el.innerHTML = [
    ["Strategic posture", view.posture || ci.risk_level || "Watch", view.strategic_action || ci.client_action || "-"],
    ["Tactical decision", shortTerm.action || "Event overlay active", shortTerm.tactical_overlay_bps!==undefined ? `${fmtBps(shortTerm.tactical_overlay_bps)} from ${String(shortTerm.top_driver || "climate").replace("_"," ")}` : (view.tactical_action || "-")],
    ["Largest portfolio risk", budget.largest_risk_contributor || "-", `${view.largest_risk || ""} Weighted tail proxy ${fmtPct(budget.weighted_tail_proxy || 0)}.`],
    ["Validation evidence", validation, `${fmtPct(ci.confidence || 0)} model confidence; short windows are directional, not statistically conclusive.`]
  ].map(c=>`<div class="decision-cell"><div class="eyebrow">${c[0]}</div><div class="decision">${c[1]}</div><div class="detail">${c[2]}</div></div>`).join("");
}

function renderDashboard(d){
  document.getElementById("timeBadge").textContent = "Updated " + d.generated_at;
  document.getElementById("sourceBadge").textContent = "Market + official climate inputs";
  document.getElementById("regimeBadge").textContent = d.latest_regime.regime + " | signal " + d.latest_regime.signal_year;
  document.getElementById("kpiRegime").textContent = d.latest_regime.regime.replace(" Climate Risk","");
  document.getElementById("kpiRegime").className = "kpi-value " + (d.latest_regime.regime.includes("High") ? "red" : "green");
  const daily = d.daily_climate_signal || {};
  document.getElementById("kpiScore").textContent = Number(daily.climate_alerts || 0).toLocaleString();
  document.getElementById("kpiScore").className = "kpi-value amber";
  document.getElementById("kpiReturn").textContent = fmtPct(daily.allocation_pressure || 0);
  document.getElementById("kpiReturn").className = "kpi-value blue";
  document.getElementById("kpiExcess").textContent = String(daily.top_driver || "none").replace("_"," ");
  document.getElementById("kpiExcess").className = "kpi-value amber";
  document.getElementById("kpiDrawdown").textContent = d.climate_data_context.latest_year || "-";
  document.getElementById("kpiDrawdown").className = "kpi-value blue";
  document.getElementById("kpiCvor").textContent = fmtPct(d.cvor_summary.scenario_tail_loss_rate || d.cvor_summary.cvor_95_loss_rate);
  document.getElementById("kpiCvor").className = "kpi-value amber";
  renderClientClimateIntelligence(d.climate_intelligence || {});
  renderScenarios(d.scenario_rows, d.cvor_summary || {});
  renderClimateData(d);
  renderDailyClimateSignal(d);
  renderInvestmentCommittee();
}

function renderClimateData(d){
  const c = d.climate_data_context;
  const ci = d.climate_intelligence || {};
  const sources = d.official_climate_sources || {};
  const notes = (d.official_climate_notes || []).join("; ");
  const latestRows = (d.official_climate_rows || []).slice(-5).reverse();
  const sourceGrid = document.getElementById("climateSourceGrid");
  if(sourceGrid){
    sourceGrid.innerHTML = (d.climate_data_sources || []).map(r=>`<div class="source-card">
      <div class="name">${r.name}</div>
      <div class="type">${r.risk_type}</div>
      <span class="pill ${String(r.model_mode || "").includes("input") ? "ok" : "info"}">${r.model_mode || r.status}</span>
      <div class="hint" style="margin-top:7px">${r.client_use}</div>
    </div>`).join("");
  }
  const table = document.getElementById("climateDataTable");
  const daily = d.daily_climate_signal || {};
  const inputs = [
    ["NWS active alerts", Number(daily.climate_alerts || 0).toLocaleString(), "Acute event intensity and tactical sector overlay", daily.source_mode || "Live input"],
    ["NASA GISTEMP", `${Number(c.current_warming).toFixed(3)} C`, "Chronic warming state and physical-risk calibration", `Official vintage ${c.latest_year}`],
    ["NOAA GML CO2", `${Number(c.co2_ppm).toFixed(2)} ppm`, "Macro transition-pressure proxy", `10Y change ${Number(c.co2_10y_change).toFixed(2)} ppm`],
    ["NCEI disasters", `${Number(c.disaster_10y_avg).toFixed(2)} / year`, "Historical acute-loss frequency calibration", `Official vintage ${c.latest_year}`],
    ["Derived climate pressure", Number(c.climate_pressure_multiplier).toFixed(3), "Scales issuer Method 2 and portfolio climate state", c.source_mode || "Derived"],
  ];
  table.innerHTML = `<tr><th>Input</th><th>Latest</th><th>Decision role</th><th>Lineage</th></tr>` +
    inputs.map(r=>`<tr><td><b>${r[0]}</b></td><td>${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td></tr>`).join("");

  const coverageTable = document.getElementById("modelCoverageTable");
  if(coverageTable){
    coverageTable.innerHTML = `<tr><th>Model layer</th><th>Coverage</th><th>Status</th><th>Decision use</th></tr>` +
      (ci.model_coverage || []).map(r=>{
        const status = String(r.status || "");
        const cls = status === "Operational" ? "status-pass" : (status === "Data gap" ? "status-watch" : "status-proxy");
        return `<tr><td><b>${r.layer}</b></td><td>${r.coverage}</td><td class="${cls}">${status}</td><td>${r.decision_use}</td></tr>`;
      }).join("");
  }
}

function renderDailyClimateSignal(d){
  const s = d.daily_climate_signal || {};
  const ci = d.climate_intelligence || {};
  const cards = document.getElementById("dailyClimateCards");
  const top = s.top_driver || "none";
  const source = s.source_mode || "-";
  if(cards){
    cards.innerHTML = [
      ["Climate alerts", Number(s.climate_alerts || 0).toLocaleString()],
      ["Daily pressure", fmtPct(s.daily_pressure || 0)],
      ["Allocation overlay", fmtPct(s.allocation_pressure || 0)],
      ["Top driver", top.replace("_"," ")],
      ["Physical risk", fmtPct(ci.physical_score || 0)],
      ["Transition risk", fmtPct(ci.transition_score || 0)]
    ].map(c=>`<div class="signal-card"><div class="label">${c[0]}</div><div class="value">${c[1]}</div></div>`).join("");
  }
  const rows = d.latest_allocation || [];
  const table = document.getElementById("dailyImpactTable");
  table.innerHTML = `<tr><th>ETF</th><th>Long-Term Weight</th><th>Daily Overlay</th><th>Final Weight</th><th>Daily Stress</th><th>Driver</th><th>Source</th></tr>` +
    rows.map(r=>{
      const bps = Number(r.daily_adjustment_bps || 0);
      return `<tr>
        <td><b>${r.ticker}</b></td>
        <td>${fmtPct(r.base_climate_weight ?? r.climate_weight)}</td>
        <td class="${bps>=0?'green':'red'}"><b>${fmtBps(bps)}</b></td>
        <td><b>${fmtPct(r.climate_weight)}</b></td>
        <td>${Number(r.daily_sector_stress || 0).toFixed(3)}</td>
        <td>${r.daily_driver || r.sector_note}</td>
        <td>${source}</td>
      </tr>`;
    }).join("");
}

function renderScenarios(rows, summary={}){
  const summaryEl = document.getElementById("scenarioSummary");
  if(summaryEl){
    const sorted = [...(rows || [])].sort((a,b)=>Number(b.portfolio_loss_rate||0)-Number(a.portfolio_loss_rate||0));
    const worst = sorted[0] || {};
    const best = sorted[sorted.length-1] || {};
    summaryEl.innerHTML = [
      ["Scenario tail", fmtPct(summary.scenario_tail_loss_rate || summary.cvor_95_loss_rate || 0), "Mean of two worst conditional losses"],
      ["Worst scenario", worst.scenario || "-", fmtPct(worst.portfolio_loss_rate || 0)],
      ["Lowest modeled loss", best.scenario || "-", fmtPct(best.portfolio_loss_rate || 0)],
      ["Tail capital", fmtMoney(summary.scenario_tail_loss_dollars || summary.cvor_95_loss_dollars || 0), "Current model mandate"],
      ["Occurrence probability", "Not assigned", "Scenario severity only"],
      ["Tail definition", "Worst two mean", "Not regulatory Expected Shortfall"]
    ].map(c=>`<div class="signal-card"><div class="label">${c[0]}</div><div class="value">${c[1]}</div><div class="hint">${c[2]}</div></div>`).join("");
  }
  const table = document.getElementById("scenarioTable");
  table.innerHTML = `<tr><th>Scenario</th><th>Interpretation</th><th>Carbon Price</th><th>Portfolio Loss</th><th>Loss Dollars</th><th>Largest Sector Loss</th><th>Narrative</th></tr>` +
    rows.map(r=>{
      const losses = Object.entries(r.sector_losses || {}).sort((a,b)=>b[1]-a[1]);
      const top = losses.length ? `${losses[0][0]} ${fmtPct(losses[0][1])}` : "-";
      return `<tr>
        <td><b>${r.scenario}</b></td><td><span class="pill info">${r.scenario_type || "Conditional stress"}</span><br><span class="hint">No occurrence probability assigned</span></td><td>$${r.carbon_price}/tCO2e</td>
        <td class="red">${fmtPct(r.portfolio_loss_rate)}</td><td>${fmtMoney(r.portfolio_loss_dollars)}</td>
        <td>${top}</td><td>${r.narrative}</td>
      </tr>`;
    }).join("");
}

async function scanCompanies(){
  const tickers = document.getElementById("tickerInput").value;
  const res = await fetch("/api/company_scan?tickers="+encodeURIComponent(tickers));
  const rows = await res.json();
  const table = document.getElementById("companyTable");
  table.innerHTML = `<tr><th>Ticker</th><th>Company</th><th>Sector</th><th>Beta</th><th>Market CVaR 95%</th><th>BAU P95</th><th>BAU P99</th><th>2C P95</th><th>P95 Reduction</th><th>BAU CVOR95 $</th><th>Data Quality</th><th>Action</th><th>Source</th></tr>` +
    rows.map(r=>`<tr>
      <td><b>${r.ticker}</b></td><td>${r.company}</td><td>${r.sector}</td><td>${r.beta}</td>
      <td class="red">${fmtPct(r.market_cvar_95)}</td>
      <td class="amber">${fmtPct(r.method2_p95_pct)}</td>
      <td class="red">${fmtPct(r.method2_p99_pct)}</td>
      <td class="blue">${fmtPct(r.method2_2c_p95_pct)}</td>
      <td class="green">${fmtPct(r.method2_p95_reduction_pct)}</td>
      <td>${fmtMoney(r.method2_cvor95_dollars)}</td>
      <td><span class="pill ${r.method2_data_quality_score>=80?"ok":(r.method2_data_quality_score>=55?"info":"high")}">${r.method2_data_quality_label} ${r.method2_data_quality_score}</span><br><span class="hint">${r.method2_data_quality_notes}</span></td>
      <td>${r.action}</td><td>${r.source}</td>
    </tr>`).join("");
  renderIssuerHeatStrip(rows);
  renderIssuerDetails(rows);
}

function renderIssuerHeatStrip(rows){
  const strip = document.getElementById("issuerHeatStrip");
  if(!strip) return;
  strip.innerHTML = rows.map(r=>{
    const p95 = Number(r.method2_p95_pct)||0;
    const reduction = Number(r.method2_p95_reduction_pct)||0;
    const level = p95 >= 0.08 ? "danger" : (p95 >= 0.045 ? "warn" : "");
    const fill = Math.max(4, Math.min(100, p95*1000));
    const cls = p95 >= 0.06 ? "neg" : "pos";
    return `<div class="heat-cell ${cls}">
      <div class="top"><span>${r.ticker}</span><span class="${p95>=0.06?'red':'green'}">${fmtPct(p95)}</span></div>
      <div class="sub">${r.sector} | 2C reduces ${fmtPct(reduction)}</div>
      <div class="risk-meter"><span class="${level}" style="width:${fill}%"></span></div>
    </div>`;
  }).join("");
}

function renderIssuerDetails(rows){
  const table = document.getElementById("detailTable");
  table.innerHTML = `<tr><th>Ticker</th><th>Physical VaR</th><th>Transition VaR</th><th>Liability VaR</th><th>Simple Total CVOR</th><th>BAU CVOR95</th><th>2C CVOR95</th><th>Tail Reduction</th><th>Discount</th><th>Draws</th></tr>` +
    rows.map(r=>`<tr>
      <td><b>${r.ticker}</b></td>
      <td>${fmtMoney(r.physical_var)}</td><td>${fmtMoney(r.transition_var)}</td><td>${fmtMoney(r.litigation_var)}</td>
      <td>${fmtMoney(r.climate_var)} <span class="hint">(${fmtPct(r.climate_var_pct_mcap)} mcap)</span></td>
      <td class="red">${fmtPct(r.method2_cvor95_pct)} / ${fmtMoney(r.method2_cvor95_dollars)}</td>
      <td class="blue">${fmtPct(r.method2_2c_cvor95_pct)} / ${fmtMoney(r.method2_2c_cvor95_dollars)}</td>
      <td class="green">${fmtPct(r.method2_cvor95_reduction_pct)}</td>
      <td>${fmtPct(r.method2_discount_rate)}</td><td>${r.method2_draws}<br><span class="hint">${r.method2_climate_data_year}, ${Number(r.method2_current_warming).toFixed(2)}C, ${Number(r.method2_co2_ppm).toFixed(1)}ppm</span></td>
    </tr>`).join("");
}

function chartTime(row){
  const raw = String(row.date || "");
  if(raw.includes(" ")){
    const dt = new Date(raw.replace(" ", "T"));
    if(Number.isFinite(dt.getTime())) return Math.floor(dt.getTime()/1000);
  }
  return raw.slice(0,10);
}

function timeLabel(t){
  if(typeof t === "number"){
    const d = new Date(t*1000);
    return d.toLocaleString(undefined,{month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"});
  }
  return String(t || "-");
}

function chartRows(){
  if(!MARKET || !ACTIVE_TICKER) return [];
  return (MARKET.charts[ACTIVE_TICKER] || []).filter(r =>
    Number.isFinite(Number(r.open)) && Number.isFinite(Number(r.high)) &&
    Number.isFinite(Number(r.low)) && Number.isFinite(Number(r.close))
  );
}

function toCandleData(rows){
  return rows.map(r=>({
    time: chartTime(r),
    open: Number(r.open),
    high: Number(r.high),
    low: Number(r.low),
    close: Number(r.close)
  }));
}

function toVolumeData(rows){
  return rows.map(r=>({
    time: chartTime(r),
    value: Number(r.volume || 0),
    color: Number(r.close) >= Number(r.open) ? "rgba(16,185,129,.42)" : "rgba(239,68,68,.38)"
  }));
}

function smaSeries(rows, period){
  const out = [];
  for(let i=period-1;i<rows.length;i++){
    const slice = rows.slice(i-period+1,i+1).map(r=>Number(r.close));
    out.push({time:chartTime(rows[i]), value:slice.reduce((a,b)=>a+b,0)/period});
  }
  return out;
}

function emaValues(values, period){
  const k = 2/(period+1);
  const out = [];
  let prev = null;
  const seed = [];
  values.forEach((v,i)=>{
    const n = Number(v);
    if(!Number.isFinite(n)){ out.push(null); return; }
    if(prev === null){
      seed.push(n);
      if(seed.length < period){ out.push(null); return; }
      prev = seed.slice(-period).reduce((a,b)=>a+b,0)/period;
    } else {
      prev = n*k + prev*(1-k);
    }
    out.push(prev);
  });
  return out;
}

function emaSeries(rows, period){
  const vals = emaValues(rows.map(r=>r.close), period);
  return vals.map((v,i)=>v===null?null:{time:chartTime(rows[i]), value:v}).filter(Boolean);
}

function vwapSeries(rows){
  const out = [];
  let pv = 0, vv = 0;
  rows.forEach(r=>{
    const vol = Math.max(1, Number(r.volume || 0));
    const typical = (Number(r.high)+Number(r.low)+Number(r.close))/3;
    pv += typical * vol; vv += vol;
    out.push({time:chartTime(r), value:pv/vv});
  });
  return out;
}

function bollingerSeries(rows, period=20, mult=2){
  const upper = [], mid = [], lower = [];
  for(let i=period-1;i<rows.length;i++){
    const slice = rows.slice(i-period+1,i+1).map(r=>Number(r.close));
    const mean = slice.reduce((a,b)=>a+b,0)/period;
    const std = Math.sqrt(slice.reduce((a,b)=>a+(b-mean)*(b-mean),0)/period);
    const time = chartTime(rows[i]);
    upper.push({time, value:mean + mult*std});
    mid.push({time, value:mean});
    lower.push({time, value:mean - mult*std});
  }
  return {upper, mid, lower};
}

function rsiSeries(rows, period=14){
  const closes = rows.map(r=>Number(r.close));
  const out = [];
  for(let i=period;i<closes.length;i++){
    let gain = 0, loss = 0;
    for(let j=i-period+1;j<=i;j++){
      const diff = closes[j]-closes[j-1];
      if(diff >= 0) gain += diff; else loss -= diff;
    }
    const rs = loss === 0 ? 100 : gain / loss;
    const rsi = loss === 0 ? 100 : 100 - 100/(1+rs);
    out.push({time:chartTime(rows[i]), value:rsi});
  }
  return out;
}

function macdSeries(rows){
  const closes = rows.map(r=>Number(r.close));
  const ema12 = emaValues(closes, 12);
  const ema26 = emaValues(closes, 26);
  const macdVals = closes.map((_,i)=>ema12[i]===null || ema26[i]===null ? null : ema12[i]-ema26[i]);
  const signalVals = emaValues(macdVals.map(v=>v===null?NaN:v), 9);
  const line = [], signal = [], hist = [];
  macdVals.forEach((v,i)=>{
    if(v === null || signalVals[i] === null) return;
    const time = chartTime(rows[i]);
    line.push({time, value:v});
    signal.push({time, value:signalVals[i]});
    hist.push({time, value:v-signalVals[i], color:(v-signalVals[i])>=0?"rgba(16,185,129,.55)":"rgba(239,68,68,.50)"});
  });
  return {line, signal, hist};
}

function chartTheme(){
  const dark = CHART_LAYERS.dark;
  return {
    bg: dark ? "#101827" : "#ffffff",
    panel: dark ? "#0f172a" : "#ffffff",
    text: dark ? "#dbeafe" : "#334155",
    grid: dark ? "rgba(148,163,184,.16)" : "rgba(148,163,184,.22)",
    border: dark ? "#334155" : "#d9e2ef",
    up: "#10b981",
    down: "#ef4444",
    blue: "#3b82f6",
    amber: "#f59e0b",
    purple: "#8b5cf6",
    cyan: "#06b6d4"
  };
}

function baseChartOptions(height){
  const t = chartTheme();
  return {
    height,
    layout:{background:{type:"solid",color:t.bg},textColor:t.text,fontFamily:"Segoe UI, Arial"},
    grid:{vertLines:{color:t.grid},horzLines:{color:t.grid}},
    crosshair:{mode: window.LightweightCharts?.CrosshairMode?.Normal ?? 0},
    rightPriceScale:{borderColor:t.border,scaleMargins:{top:.08,bottom:.26}},
    timeScale:{borderColor:t.border,timeVisible:true,secondsVisible:false,rightOffset:8,barSpacing:7,minBarSpacing:2},
    localization:{priceFormatter:p=>"$"+Number(p).toFixed(2)}
  };
}

function resetTradingChart(){
  const priceEl = document.getElementById("tradingChart");
  const indEl = document.getElementById("indicatorChart");
  if(priceEl) priceEl.innerHTML = "";
  if(indEl) indEl.innerHTML = "";
  TRADING_CHART = null;
}

function ensureTradingChart(){
  if(!window.LightweightCharts) return false;
  const priceEl = document.getElementById("tradingChart");
  const indEl = document.getElementById("indicatorChart");
  if(!priceEl || !indEl) return false;
  if(TRADING_CHART) return true;
  const t = chartTheme();
  const chart = LightweightCharts.createChart(priceEl, baseChartOptions(priceEl.clientHeight || 430));
  const indicator = LightweightCharts.createChart(indEl, {
    ...baseChartOptions(indEl.clientHeight || 150),
    rightPriceScale:{borderColor:t.border,scaleMargins:{top:.12,bottom:.12}},
    localization:{priceFormatter:p=>Number(p).toFixed(2)}
  });
  const candle = chart.addCandlestickSeries({
    upColor:t.up,downColor:t.down,borderUpColor:t.up,borderDownColor:t.down,wickUpColor:t.up,wickDownColor:t.down,
    priceLineVisible:true,lastValueVisible:true
  });
  const volume = chart.addHistogramSeries({priceScaleId:"",priceFormat:{type:"volume"},lastValueVisible:false,priceLineVisible:false});
  volume.priceScale().applyOptions({scaleMargins:{top:.78,bottom:0}});
  const ma = chart.addLineSeries({color:t.blue,lineWidth:2,lastValueVisible:false,priceLineVisible:false});
  const ema = chart.addLineSeries({color:t.amber,lineWidth:2,lastValueVisible:false,priceLineVisible:false});
  const vwap = chart.addLineSeries({color:t.purple,lineWidth:2,lastValueVisible:false,priceLineVisible:false});
  const bbUpper = chart.addLineSeries({color:"rgba(6,182,212,.72)",lineWidth:1,lastValueVisible:false,priceLineVisible:false});
  const bbMid = chart.addLineSeries({color:"rgba(6,182,212,.40)",lineWidth:1,lastValueVisible:false,priceLineVisible:false});
  const bbLower = chart.addLineSeries({color:"rgba(6,182,212,.72)",lineWidth:1,lastValueVisible:false,priceLineVisible:false});
  const rsi = indicator.addLineSeries({color:t.blue,lineWidth:2,lastValueVisible:true,priceLineVisible:false});
  const macd = indicator.addLineSeries({color:t.blue,lineWidth:2,lastValueVisible:false,priceLineVisible:false});
  const signal = indicator.addLineSeries({color:t.amber,lineWidth:2,lastValueVisible:false,priceLineVisible:false});
  const hist = indicator.addHistogramSeries({priceFormat:{type:"price",precision:2,minMove:.01},lastValueVisible:false,priceLineVisible:false});
  let syncing = false;
  chart.timeScale().subscribeVisibleLogicalRangeChange(range=>{
    if(syncing || !range) return;
    syncing = true; indicator.timeScale().setVisibleLogicalRange(range); syncing = false;
  });
  indicator.timeScale().subscribeVisibleLogicalRangeChange(range=>{
    if(syncing || !range) return;
    syncing = true; chart.timeScale().setVisibleLogicalRange(range); syncing = false;
  });
  chart.subscribeCrosshairMove(param=>{
    if(!param || !param.time || !param.seriesData) { updateChartReadout(); return; }
    const bar = param.seriesData.get(candle);
    if(bar) updateChartReadout({time:param.time,...bar});
  });
  TRADING_CHART = {chart,indicator,candle,volume,ma,ema,vwap,bbUpper,bbMid,bbLower,rsi,macd,signal,hist,key:null};
  resizeTradingChart();
  return true;
}

function resizeTradingChart(){
  if(!TRADING_CHART) return;
  const priceEl = document.getElementById("tradingChart");
  const indEl = document.getElementById("indicatorChart");
  if(priceEl) TRADING_CHART.chart.resize(Math.max(320, priceEl.clientWidth), Math.max(320, priceEl.clientHeight));
  if(indEl) TRADING_CHART.indicator.resize(Math.max(320, indEl.clientWidth), Math.max(120, indEl.clientHeight));
}

function updateChartReadout(bar=null){
  const rows = chartRows();
  const last = rows[rows.length-1];
  const prev = rows[rows.length-2] || last;
  const b = bar || (last ? {time:chartTime(last),open:Number(last.open),high:Number(last.high),low:Number(last.low),close:Number(last.close)} : null);
  const readout = document.getElementById("chartReadout");
  if(!readout || !b) return;
  const change = last && prev ? Number(last.close)/Number(prev.close)-1 : 0;
  const vol = last ? fmtVolume(last.volume) : "-";
  readout.innerHTML = `
    <span><b>${ACTIVE_TICKER || "-"}</b></span>
    <span>${timeLabel(b.time)}</span>
    <span>O ${fmtPrice(b.open)}</span>
    <span>H ${fmtPrice(b.high)}</span>
    <span>L ${fmtPrice(b.low)}</span>
    <span>C ${fmtPrice(b.close)}</span>
    <span class="${clsFor(change)}">${fmtPct(change)}</span>
    <span>Vol ${vol}</span>`;
}

function renderProfessionalKline(){
  const shell = document.getElementById("chartShell");
  const priceEl = document.getElementById("tradingChart");
  const indEl = document.getElementById("indicatorChart");
  const canvas = document.getElementById("candleChart");
  if(!window.LightweightCharts || !shell || !priceEl || !indEl){
    if(priceEl) priceEl.style.display = "none";
    if(indEl) indEl.style.display = "none";
    if(canvas) canvas.style.display = "block";
    return false;
  }
  if(canvas) canvas.style.display = "none";
  priceEl.style.display = "block";
  indEl.style.display = "block";
  shell.classList.toggle("dark", CHART_LAYERS.dark);
  if(!ensureTradingChart()) return false;
  const rows = chartRows();
  if(!rows.length) return true;
  const key = `${ACTIVE_TICKER}|${MARKET?.period}|${MARKET?.interval}`;
  const candles = toCandleData(rows);
  TRADING_CHART.candle.setData(candles);
  TRADING_CHART.volume.setData(CHART_LAYERS.volume ? toVolumeData(rows) : []);
  TRADING_CHART.ma.setData(CHART_LAYERS.ma ? smaSeries(rows,20) : []);
  TRADING_CHART.ema.setData(CHART_LAYERS.ema ? emaSeries(rows,50) : []);
  TRADING_CHART.vwap.setData(CHART_LAYERS.vwap ? vwapSeries(rows) : []);
  const bb = bollingerSeries(rows,20,2);
  TRADING_CHART.bbUpper.setData(CHART_LAYERS.bands ? bb.upper : []);
  TRADING_CHART.bbMid.setData(CHART_LAYERS.bands ? bb.mid : []);
  TRADING_CHART.bbLower.setData(CHART_LAYERS.bands ? bb.lower : []);
  if(CHART_LAYERS.macd){
    const m = macdSeries(rows);
    TRADING_CHART.rsi.setData([]);
    TRADING_CHART.macd.setData(m.line);
    TRADING_CHART.signal.setData(m.signal);
    TRADING_CHART.hist.setData(m.hist);
  } else {
    TRADING_CHART.rsi.setData(rsiSeries(rows,14));
    TRADING_CHART.macd.setData([]);
    TRADING_CHART.signal.setData([]);
    TRADING_CHART.hist.setData([]);
  }
  if(TRADING_CHART.key !== key){
    TRADING_CHART.chart.timeScale().fitContent();
    TRADING_CHART.indicator.timeScale().fitContent();
    TRADING_CHART.key = key;
  }
  updateChartReadout();
  resizeTradingChart();
  return true;
}

function drawCandleChart(){
  try {
    drawCanvasFallback();
  } catch (err) {
    console.error("K-line render failed", err);
    const readout = document.getElementById("chartReadout");
    if(readout) readout.textContent = "K-line render error: " + (err && err.message ? err.message : err);
  }
}

function toggleChartLayer(layer, btn){
  CHART_LAYERS[layer] = !CHART_LAYERS[layer];
  if(btn){
    btn.classList.toggle("active", CHART_LAYERS[layer]);
    btn.classList.toggle("secondary", !CHART_LAYERS[layer]);
  }
  drawCandleChart();
}

function toggleChartTheme(){
  CHART_LAYERS.dark = !CHART_LAYERS.dark;
  const btn = document.getElementById("chartThemeBtn");
  if(btn) btn.textContent = CHART_LAYERS.dark ? "Light" : "Dark";
  resetTradingChart();
  drawCandleChart();
}

function fitTradingChart(){
  const rows = chartRows();
  CANVAS_CHART.start = 0;
  CANVAS_CHART.end = Math.max(0, rows.length - 1);
  CANVAS_CHART.key = `${ACTIVE_TICKER}|${MARKET?.period}|${MARKET?.interval}`;
  drawCanvasFallback();
}

function exportTradingChart(){
  const shot = document.getElementById("candleChart");
  if(!shot) return;
  const link = document.createElement("a");
  link.download = `${ACTIVE_TICKER || "chart"}-${MARKET?.period || "chart"}-${MARKET?.interval || "1d"}.png`;
  link.href = shot.toDataURL("image/png");
  link.click();
}

function drawCanvasFallback(){
  const canvas = document.getElementById("candleChart");
  if(!canvas || !MARKET || !ACTIVE_TICKER) return;
  const priceEl = document.getElementById("tradingChart");
  const indEl = document.getElementById("indicatorChart");
  if(priceEl) priceEl.style.display = "none";
  if(indEl) indEl.style.display = "none";
  canvas.style.display = "block";
  const shell = document.getElementById("chartShell");
  if(shell) shell.classList.toggle("dark", CHART_LAYERS.dark);

  const rows = chartRows();
  const key = `${ACTIVE_TICKER}|${MARKET.period}|${MARKET.interval}|${rows.length}`;
  if(CANVAS_CHART.key !== key){
    const windowSize = MARKET.interval === "1d" ? Math.min(rows.length, 170) : Math.min(rows.length, 180);
    CANVAS_CHART.start = Math.max(0, rows.length - windowSize);
    CANVAS_CHART.end = Math.max(0, rows.length - 1);
    CANVAS_CHART.cross = null;
    CANVAS_CHART.key = key;
  }
  CANVAS_CHART.start = clamp(Math.round(CANVAS_CHART.start), 0, Math.max(0, rows.length - 2));
  CANVAS_CHART.end = clamp(Math.round(CANVAS_CHART.end), CANVAS_CHART.start + 1, Math.max(1, rows.length - 1));
  const visible = rows.slice(CANVAS_CHART.start, CANVAS_CHART.end + 1);

  if(!canvas.dataset.bound){
    canvas.dataset.bound = "1";
    canvas.addEventListener("mousemove", e=>{
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      if(CANVAS_CHART.drag){
        const rowsNow = chartRows();
        const count = Math.max(2, CANVAS_CHART.dragEnd - CANVAS_CHART.dragStart + 1);
        const chartW = Math.max(1, rect.width - 62 - 70);
        const step = chartW / Math.max(1, count - 1);
        const delta = Math.round((CANVAS_CHART.dragX - x) / Math.max(1, step));
        let start = CANVAS_CHART.dragStart + delta;
        start = clamp(start, 0, Math.max(0, rowsNow.length - count));
        CANVAS_CHART.start = start;
        CANVAS_CHART.end = start + count - 1;
      } else {
        CANVAS_CHART.cross = {x,y};
      }
      drawCanvasFallback();
    });
    canvas.addEventListener("mouseleave", ()=>{
      CANVAS_CHART.cross = null;
      CANVAS_CHART.drag = false;
      drawCanvasFallback();
    });
    canvas.addEventListener("mousedown", e=>{
      const rect = canvas.getBoundingClientRect();
      CANVAS_CHART.drag = true;
      CANVAS_CHART.dragX = e.clientX - rect.left;
      CANVAS_CHART.dragStart = CANVAS_CHART.start;
      CANVAS_CHART.dragEnd = CANVAS_CHART.end;
    });
    window.addEventListener("mouseup", ()=>{ CANVAS_CHART.drag = false; });
    canvas.addEventListener("wheel", e=>{
      e.preventDefault();
      const rowsNow = chartRows();
      const count = CANVAS_CHART.end - CANVAS_CHART.start + 1;
      const zoomIn = e.deltaY < 0;
      const nextCount = clamp(Math.round(count * (zoomIn ? 0.82 : 1.22)), 28, Math.max(30, rowsNow.length));
      const rect = canvas.getBoundingClientRect();
      const frac = clamp((e.clientX - rect.left - 62) / Math.max(1, rect.width - 132), 0, 1);
      const center = CANVAS_CHART.start + Math.round(count * frac);
      let start = Math.round(center - nextCount * frac);
      start = clamp(start, 0, Math.max(0, rowsNow.length - nextCount));
      CANVAS_CHART.start = start;
      CANVAS_CHART.end = Math.min(rowsNow.length - 1, start + nextCount - 1);
      drawCanvasFallback();
    }, {passive:false});
  }

  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.round(rect.width*dpr));
  canvas.height = Math.max(1, Math.round(rect.height*dpr));
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr,dpr);
  const w = rect.width, h = rect.height;
  const t = chartTheme();
  ctx.clearRect(0,0,w,h);
  ctx.fillStyle=t.bg;
  ctx.fillRect(0,0,w,h);
  if(!rows.length){
    ctx.fillStyle=t.text; ctx.font="13px Segoe UI"; ctx.fillText("No market bars available.", 20, 32); return;
  }
  const pad = {l:62,r:70,t:42,b:28};
  const priceBottom = Math.max(330, h - 150);
  const priceH = priceBottom - pad.t;
  const indTop = priceBottom + 22;
  const indBottom = h - pad.b;
  const indH = Math.max(90, indBottom - indTop);
  const chartW = w - pad.l - pad.r;
  const volH = Math.min(82, priceH * 0.26);
  const volTop = priceBottom - volH;

  const byTime = series => {
    const m = new Map();
    series.forEach(p=>m.set(String(p.time), Number(p.value)));
    return m;
  };
  const maMap = byTime(smaSeries(rows, 20));
  const emaMap = byTime(emaSeries(rows, 50));
  const vwapMap = byTime(vwapSeries(rows));
  const bb = bollingerSeries(rows, 20, 2);
  const bbUpperMap = byTime(bb.upper), bbMidMap = byTime(bb.mid), bbLowerMap = byTime(bb.lower);

  const highs = visible.map(r=>Number(r.high));
  const lows = visible.map(r=>Number(r.low));
  const extraVals = [];
  visible.forEach(r=>{
    const k = String(chartTime(r));
    if(CHART_LAYERS.ma && maMap.has(k)) extraVals.push(maMap.get(k));
    if(CHART_LAYERS.ema && emaMap.has(k)) extraVals.push(emaMap.get(k));
    if(CHART_LAYERS.vwap && vwapMap.has(k)) extraVals.push(vwapMap.get(k));
    if(CHART_LAYERS.bands){
      [bbUpperMap, bbMidMap, bbLowerMap].forEach(m=>{ if(m.has(k)) extraVals.push(m.get(k)); });
    }
  });
  let minP = Math.min(...lows), maxP = Math.max(...highs);
  extraVals.forEach(v=>{ if(Number.isFinite(v)){ minP=Math.min(minP,v); maxP=Math.max(maxP,v); } });
  if(minP===maxP){ minP-=1; maxP+=1; }
  const pExtra = (maxP-minP)*0.10; minP-=pExtra; maxP+=pExtra;
  const maxVol = Math.max(...visible.map(r=>Number(r.volume)||0), 1);
  const xStep = chartW/Math.max(1, visible.length-1);
  const candleW = Math.max(2, Math.min(15, xStep*0.58));
  const xFor = i => pad.l + xStep*i;
  const yFor = p => pad.t + priceH*(1-(Number(p)-minP)/(maxP-minP));

  ctx.strokeStyle=t.grid; ctx.lineWidth=1; ctx.font="11px Segoe UI"; ctx.fillStyle=t.text;
  for(let i=0;i<=5;i++){
    const y=pad.t+priceH*i/5;
    ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke();
    const val=maxP-(maxP-minP)*i/5;
    ctx.fillText("$"+val.toFixed(2), w-pad.r+8, y+4);
  }
  const labelIdx = [0,.25,.5,.75,1].map(p=>Math.round((visible.length-1)*p));
  labelIdx.forEach(i=>{
    const x = xFor(i);
    ctx.beginPath(); ctx.moveTo(x,pad.t); ctx.lineTo(x,priceBottom); ctx.stroke();
    ctx.fillText(String(visible[i]?.date || "").slice(MARKET.interval==="1d"?5:5, MARKET.interval==="1d"?10:16), Math.max(pad.l, Math.min(w-pad.r-70, x-28)), priceBottom+16);
  });
  ctx.strokeStyle=t.border;
  ctx.beginPath(); ctx.rect(pad.l,pad.t,chartW,priceH); ctx.stroke();

  if(CHART_LAYERS.volume){
    visible.forEach((r,i)=>{
      const x=xFor(i);
      const v=Number(r.volume)||0;
      const up = Number(r.close)>=Number(r.open);
      const vh = volH*(v/maxVol);
      ctx.fillStyle = up ? "rgba(16,185,129,.28)" : "rgba(239,68,68,.24)";
      ctx.fillRect(x-candleW/2, priceBottom - vh, candleW, vh);
    });
    ctx.fillStyle=t.text; ctx.font="11px Segoe UI"; ctx.fillText("Volume", pad.l+6, volTop+14);
  }

  visible.forEach((r,i)=>{
    const x=xFor(i);
    const o=Number(r.open), c=Number(r.close), hi=Number(r.high), lo=Number(r.low), v=Number(r.volume)||0;
    const up = c>=o;
    const color = up ? t.up : t.down;
    ctx.strokeStyle=color; ctx.fillStyle=color;
    ctx.lineWidth = Math.max(1, Math.min(2, candleW*.22));
    ctx.beginPath(); ctx.moveTo(x, yFor(hi)); ctx.lineTo(x, yFor(lo)); ctx.stroke();
    const yOpen=yFor(o), yClose=yFor(c);
    const bodyTop=Math.min(yOpen,yClose), bodyH=Math.max(2.2, Math.abs(yClose-yOpen));
    if(up){
      ctx.fillStyle = t.bg;
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.3;
      ctx.fillRect(x-candleW/2, bodyTop, candleW, bodyH);
      ctx.strokeRect(x-candleW/2, bodyTop, candleW, bodyH);
    } else {
      ctx.fillStyle = color;
      ctx.fillRect(x-candleW/2, bodyTop, candleW, bodyH);
    }
  });

  function drawMappedLine(map, color, width=1.8, dashed=false){
    ctx.save();
    ctx.strokeStyle=color; ctx.lineWidth=width;
    if(dashed) ctx.setLineDash([4,4]);
    ctx.beginPath();
    let started=false;
    visible.forEach((r,i)=>{
      const v = map.get(String(chartTime(r)));
      if(!Number.isFinite(v)) return;
      const x=xFor(i), y=yFor(v);
      if(!started){ ctx.moveTo(x,y); started=true; } else ctx.lineTo(x,y);
    });
    if(started) ctx.stroke();
    ctx.restore();
  }
  if(CHART_LAYERS.bands){
    drawMappedLine(bbUpperMap, "rgba(6,182,212,.78)", 1.2);
    drawMappedLine(bbMidMap, "rgba(6,182,212,.40)", 1.1, true);
    drawMappedLine(bbLowerMap, "rgba(6,182,212,.78)", 1.2);
  }
  if(CHART_LAYERS.ma) drawMappedLine(maMap, t.blue, 2.1);
  if(CHART_LAYERS.ema) drawMappedLine(emaMap, t.amber, 2.0);
  if(CHART_LAYERS.vwap) drawMappedLine(vwapMap, t.purple, 1.8);

  ctx.strokeStyle=t.grid;
  ctx.fillStyle=t.text;
  ctx.font="11px Segoe UI";
  ctx.beginPath(); ctx.moveTo(pad.l,indTop); ctx.lineTo(w-pad.r,indTop); ctx.stroke();
  ctx.strokeStyle=t.border; ctx.strokeRect(pad.l, indTop, chartW, indH);
  if(CHART_LAYERS.macd){
    const m = macdSeries(rows);
    const maps = [byTime(m.line), byTime(m.signal), byTime(m.hist)];
    const vals = [];
    visible.forEach(r=>maps.forEach(mp=>{ const v=mp.get(String(chartTime(r))); if(Number.isFinite(v)) vals.push(v); }));
    let minI = Math.min(...vals, -0.01), maxI = Math.max(...vals, 0.01);
    if(minI===maxI){ minI-=1; maxI+=1; }
    const yI = v => indTop + indH*(1-(v-minI)/(maxI-minI));
    const zero = yI(0);
    ctx.strokeStyle=t.grid; ctx.beginPath(); ctx.moveTo(pad.l,zero); ctx.lineTo(w-pad.r,zero); ctx.stroke();
    visible.forEach((r,i)=>{
      const v = maps[2].get(String(chartTime(r)));
      if(!Number.isFinite(v)) return;
      const x = xFor(i);
      ctx.fillStyle = v>=0 ? "rgba(16,185,129,.55)" : "rgba(239,68,68,.50)";
      ctx.fillRect(x-candleW/2, Math.min(zero,yI(v)), candleW, Math.max(1, Math.abs(yI(v)-zero)));
    });
    const drawIndicatorLine = (map,color)=>{
      ctx.strokeStyle=color; ctx.lineWidth=1.8; ctx.beginPath(); let started=false;
      visible.forEach((r,i)=>{ const v=map.get(String(chartTime(r))); if(!Number.isFinite(v))return; const x=xFor(i), y=yI(v); if(!started){ctx.moveTo(x,y); started=true;} else ctx.lineTo(x,y); });
      if(started)ctx.stroke();
    };
    drawIndicatorLine(maps[0], t.blue);
    drawIndicatorLine(maps[1], t.amber);
    ctx.fillText("MACD", pad.l+6, indTop+16);
  } else {
    const rsiMap = byTime(rsiSeries(rows,14));
    const yR = v => indTop + indH*(1-v/100);
    [70,50,30].forEach(level=>{
      ctx.strokeStyle = level===50 ? t.grid : "rgba(245,158,11,.32)";
      ctx.beginPath(); ctx.moveTo(pad.l,yR(level)); ctx.lineTo(w-pad.r,yR(level)); ctx.stroke();
      ctx.fillStyle=t.text; ctx.fillText(String(level), w-pad.r+8, yR(level)+4);
    });
    ctx.strokeStyle=t.blue; ctx.lineWidth=1.9; ctx.beginPath(); let started=false;
    visible.forEach((r,i)=>{ const v=rsiMap.get(String(chartTime(r))); if(!Number.isFinite(v))return; const x=xFor(i), y=yR(v); if(!started){ctx.moveTo(x,y); started=true;} else ctx.lineTo(x,y); });
    if(started)ctx.stroke();
    ctx.fillStyle=t.text; ctx.fillText("RSI 14", pad.l+6, indTop+16);
  }

  const first=visible[0], last=visible[visible.length-1];
  const chg = Number(last.close) - Number((rows[rows.length-2] || last).close);
  const chgPct = chg / Number((rows[rows.length-2] || last).close || 1);
  ctx.fillStyle=t.text; ctx.font="bold 14px Segoe UI";
  ctx.fillText(`${ACTIVE_TICKER} ${fmtPrice(last.close)}  ${fmtPct(chgPct)}  ${MARKET.period}/${MARKET.interval}`, pad.l, 22);
  ctx.font="11px Segoe UI";
  ctx.fillText(`${first.date} -> ${last.date} | ${visible.length}/${rows.length} bars | wheel zoom, drag pan`, pad.l+245, 22);

  if(CANVAS_CHART.cross){
    const cx = clamp(CANVAS_CHART.cross.x, pad.l, w-pad.r);
    const cy = clamp(CANVAS_CHART.cross.y, pad.t, indBottom);
    const idx = clamp(Math.round((cx-pad.l)/Math.max(1,xStep)), 0, visible.length-1);
    const r = visible[idx];
    const x = xFor(idx);
    ctx.save();
    ctx.setLineDash([5,5]);
    ctx.strokeStyle = CHART_LAYERS.dark ? "rgba(226,232,240,.50)" : "rgba(71,85,105,.45)";
    ctx.beginPath(); ctx.moveTo(x,pad.t); ctx.lineTo(x,indBottom); ctx.stroke();
    if(cy <= priceBottom){
      ctx.beginPath(); ctx.moveTo(pad.l,cy); ctx.lineTo(w-pad.r,cy); ctx.stroke();
      const price = maxP - (cy-pad.t)/priceH*(maxP-minP);
      ctx.setLineDash([]);
      ctx.fillStyle="#111827"; ctx.fillRect(w-pad.r+4, cy-11, 58, 22);
      ctx.fillStyle="#fff"; ctx.font="bold 11px Segoe UI"; ctx.fillText("$"+price.toFixed(2), w-pad.r+8, cy+4);
    }
    ctx.setLineDash([]);
    ctx.fillStyle="#111827"; ctx.fillRect(Math.max(pad.l, Math.min(w-pad.r-110, x-44)), priceBottom+2, 110, 22);
    ctx.fillStyle="#fff"; ctx.font="bold 11px Segoe UI"; ctx.fillText(String(r.date).slice(2,16), Math.max(pad.l+4, Math.min(w-pad.r-106, x-40)), priceBottom+17);
    ctx.restore();
    updateChartReadout({time:chartTime(r),open:Number(r.open),high:Number(r.high),low:Number(r.low),close:Number(r.close)});
  } else {
    updateChartReadout({time:chartTime(last),open:Number(last.open),high:Number(last.high),low:Number(last.low),close:Number(last.close)});
  }
}

function drawLineChart(id, labels, series){
  const canvas = document.getElementById(id);
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = Math.max(1, Math.round(rect.width*dpr));
  canvas.height = Math.max(1, Math.round(rect.height*dpr));
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr,dpr);
  const w = rect.width, h = rect.height;
  ctx.clearRect(0,0,w,h);
  const legendRows = series.length > 3 ? 2 : 1;
  const pad = {l:42,r:18,t:22 + (legendRows - 1) * 16,b:34};
  const vals = series.flatMap(s=>s.values).filter(v=>Number.isFinite(Number(v))).map(Number);
  let min = Math.min(...vals), max = Math.max(...vals);
  if (min===max){ min-=1; max+=1; }
  const extra=(max-min)*0.12; min-=extra; max+=extra;
  ctx.strokeStyle="#e3eaf4"; ctx.lineWidth=1;
  ctx.font="11px Segoe UI";
  ctx.fillStyle="#64748b";
  for(let i=0;i<5;i++){
    const y=pad.t+(h-pad.t-pad.b)*i/4;
    ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke();
    const val=max-(max-min)*i/4;
    ctx.fillText(val.toFixed(2),4,y+4);
  }
  const xFor=i=>pad.l+(w-pad.l-pad.r)*(i/Math.max(1,labels.length-1));
  const yFor=v=>pad.t+(h-pad.t-pad.b)*(1-(v-min)/(max-min));
  series.forEach(s=>{
    ctx.strokeStyle=s.color; ctx.lineWidth=2; ctx.beginPath();
    s.values.forEach((v,i)=>{ const x=xFor(i), y=yFor(Number(v)); if(i===0)ctx.moveTo(x,y); else ctx.lineTo(x,y); });
    ctx.stroke();
  });
  let lx=pad.l, ly=12;
  series.forEach(s=>{
    const label = String(s.name);
    const approx = 22 + label.length * 6.5;
    if(lx + approx > w - pad.r){ lx = pad.l; ly += 14; }
    ctx.fillStyle=s.color; ctx.fillRect(lx,ly-4,12,3);
    ctx.fillStyle="#334155"; ctx.fillText(label,lx+16,ly);
    lx += approx + 18;
  });
  ctx.fillStyle="#64748b";
  if(labels.length){ ctx.fillText(labels[0],pad.l,h-10); ctx.fillText(labels[labels.length-1],w-pad.r-36,h-10); }
}

window.addEventListener("resize",()=>{ if(DASH) renderDashboard(DASH); if(OPTIMIZER) renderOptimizer(OPTIMIZER); if(DAILY_CLIMATE_BOARD) renderDailyClimateBoard(DAILY_CLIMATE_BOARD); });
loadDashboard();
setInterval(()=>{ loadDailyClimateBoard(); }, 300000);
setInterval(()=>{ loadDailyRecommendationBacktest(); }, 3600000);
setInterval(()=>{ loadDashboard(); }, 900000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self):
        body = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):  # keep terminal quiet and product-like
        return

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/", "/index.html"]:
            self._send_html()
            return
        if parsed.path == "/api/dashboard":
            self._send_json(build_payload())
            return
        if parsed.path == "/api/climate_intelligence":
            self._send_json(climate_intelligence_payload())
            return
        if parsed.path == "/api/climate_model_lab":
            q = parse_qs(parsed.query, keep_blank_values=True)
            self._send_json(
                climate_model_lab_payload(
                    scope=q.get("scope", ["portfolio"])[0],
                    target=q.get("target", ["current_policies"])[0],
                    reference=q.get("reference", ["baseline"])[0],
                    horizon=q.get("horizon", ["2050"])[0],
                    sector=q.get("sector", ["Technology"])[0],
                    ticker=q.get("ticker", ["AAPL"])[0],
                )
            )
            return
        if parsed.path == "/api/company_scan":
            q = parse_qs(parsed.query)
            tickers = ",".join(q.get("tickers", ["AAPL,MSFT,XOM,NEE,JPM"]))
            self._send_json(company_scan(tickers.split(",")))
            return
        if parsed.path == "/api/universe_search":
            q = parse_qs(parsed.query)
            query = q.get("query", [""])[0]
            limit = q.get("limit", ["80"])[0]
            include_etfs = q.get("include_etfs", ["false"])[0].lower() in ["1", "true", "yes"]
            self._send_json(search_us_universe(query=query, limit=limit, include_etfs=include_etfs))
            return
        if parsed.path == "/api/market_chart":
            q = parse_qs(parsed.query)
            tickers = q.get("tickers", ["SPY,QQQ,AAPL,XOM"])[0]
            period = q.get("period", ["6mo"])[0]
            interval = q.get("interval", ["1d"])[0]
            self._send_json(market_chart_payload(tickers, period=period, interval=interval))
            return
        if parsed.path == "/api/etf_watchlist":
            self._send_json(etf_watchlist_payload())
            return
        if parsed.path == "/api/portfolio_optimizer":
            q = parse_qs(parsed.query, keep_blank_values=True)
            self._send_json(
                portfolio_optimizer_payload(
                    mode=q.get("mode", ["etf_stock"])[0],
                    capital=q.get("capital", [str(DEFAULT_PORTFOLIO_VALUE)])[0],
                    horizon=q.get("horizon", ["long"])[0],
                    style=q.get("style", ["balanced"])[0],
                    etfs=q.get("etfs", [""])[0],
                    stocks=q.get("stocks", [""])[0],
                )
            )
            return
        if parsed.path == "/api/daily_climate_board":
            self._send_json(daily_climate_board_payload())
            return
        if parsed.path == "/api/daily_climate_signal":
            self._send_json(load_daily_climate_signal())
            return
        if parsed.path == "/api/daily_recommendation_backtest":
            q = parse_qs(parsed.query, keep_blank_values=True)
            refresh = q.get("refresh", ["false"])[0].lower() in ["1", "true", "yes"]
            use_portfolio = q.get("portfolio", ["false"])[0].lower() in ["1", "true", "yes"]
            self._send_json(
                daily_recommendation_backtest_payload(
                    force_refresh=refresh,
                    use_portfolio=use_portfolio,
                    mode=q.get("mode", ["etf_stock"])[0],
                    capital=q.get("capital", [str(DEFAULT_PORTFOLIO_VALUE)])[0],
                    horizon=q.get("horizon", ["long"])[0],
                    style=q.get("style", ["balanced"])[0],
                    etfs=q.get("etfs", [""])[0],
                    stocks=q.get("stocks", [""])[0],
                    trading_cost_bps=q.get("trading_cost_bps", ["10"])[0],
                    annual_borrow_cost_bps=q.get("annual_borrow_cost_bps", ["100"])[0],
                )
            )
            return
        self._send_json({"error": "Not found"}, status=404)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"Jennison Climate-Finance Platform started: {url}")
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
