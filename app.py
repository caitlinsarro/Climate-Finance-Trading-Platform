# -*- coding: utf-8 -*-
"""
Jennison Climate-Risk Research Platform

Local client-facing prototype inspired by the existing China A-share dashboard.
Run:
    python app.py
Open:
    http://127.0.0.1:8865
"""

from __future__ import annotations

import json
import hashlib
import math
import sys
import threading
import time
import webbrowser
import csv
import io
import random
import statistics
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
ISSUER_SECTOR_MASTER_PATH = DATA_DIR / "issuer_sector_master.csv"

PORT = 8865
DEFAULT_PORTFOLIO_VALUE = 50_000_000
START_YEAR = 2009
CURRENT_YEAR = datetime.now().year
CURRENT_WARMING_C = 1.28
FIRM_VULNERABILITY_MIN = 0.55
FIRM_VULNERABILITY_MAX = 1.45
SCENARIO_TAIL_COUNT = 2
TACTICAL_OVERLAY_LIMIT_BPS = 250
RISK_FREE_RATE = 0.0425
EQUITY_RISK_PREMIUM = 0.0450
PRETAX_COST_OF_DEBT = 0.0525
US_CORPORATE_TAX_RATE = 0.21

NASA_GISTEMP_CSV_URL = "https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv"
NOAA_CO2_CSV_URL = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv"
NCEI_BILLION_EVENTS_JSON_URL = "https://www.ncei.noaa.gov/monitoring-content/billions/data/events.json"
CLIMATE_DATA_CACHE = DATA_DIR / "official_climate_data_cache.json"
NWS_ACTIVE_ALERTS_URL = "https://api.weather.gov/alerts/active?status=actual&message_type=alert"
DAILY_CLIMATE_CACHE = DATA_DIR / "daily_climate_alerts_cache.json"
NWS_USER_AGENT = "JennisonClimateFinancePrototype/1.0 (local research)"
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
BEA_GDP_INDUSTRY_URL = "https://www.bea.gov/data/gdp/gdp-industry"
BEA_INPUT_OUTPUT_URL = "https://www.bea.gov/data/industries/input-output-accounts-data"
FRED_ALFRED_URL = "https://fred.stlouisfed.org/docs/api/fred/overview.html"
US_TREASURY_RATES_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
NOAA_STORM_EVENTS_BULK_URL = "https://www.ncei.noaa.gov/stormevents/ftp.jsp"
NASA_NEX_GDDP_URL = "https://www.nasa.gov/nasa-earth-exchange-nex/gddp/downscaled-climate-projections-nex-gddp-cmip6/"
FACILITY_EXPOSURE_FILE = DATA_DIR / "issuer_facility_exposure.json"


def governed_release_sort_key(release_id):
    """Sort CFP releases by numeric R ordinal instead of lexicographic text."""
    text = str(release_id or "")
    ordinal = 0
    for part in text.split("-"):
        if len(part) > 1 and part[0] == "R" and part[1:].isdigit():
            ordinal = int(part[1:])
            break
    return ordinal, text

NGFS_SCENARIO_LABELS = {
    "below_2c": "Below 2°C",
    "current_policies": "Current Policies",
    "delayed_transition": "Delayed transition",
    "fragmented_world": "Fragmented World",
    "net_zero_2050": "Net Zero 2050",
}


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
        "note": "Prioritize lower conditional climate loss and stronger resilience.",
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
        "country_gdp_loss_2050": 0.000,
        "supply_chain_shock_2050": 0.000,
        "inflation_shock_2050": 0.000,
        "unemployment_shock_2050": 0.000,
        "transition_demand_shock_2050": 0.000,
        "carbon_cost_shock_2050": 0.000,
        "energy_cost_shock_2050": 0.000,
        "transition_capex_shock_2050": 0.000,
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
        "country_gdp_loss_2050": 0.015,
        "supply_chain_shock_2050": 0.015,
        "inflation_shock_2050": 0.012,
        "unemployment_shock_2050": 0.008,
        "transition_demand_shock_2050": 0.180,
        "carbon_cost_shock_2050": 0.100,
        "energy_cost_shock_2050": 0.040,
        "transition_capex_shock_2050": 0.060,
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
        "country_gdp_loss_2050": 0.008,
        "supply_chain_shock_2050": 0.010,
        "inflation_shock_2050": 0.007,
        "unemployment_shock_2050": 0.004,
        "transition_demand_shock_2050": 0.105,
        "carbon_cost_shock_2050": 0.060,
        "energy_cost_shock_2050": 0.025,
        "transition_capex_shock_2050": 0.035,
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
        "country_gdp_loss_2050": 0.030,
        "supply_chain_shock_2050": 0.035,
        "inflation_shock_2050": 0.025,
        "unemployment_shock_2050": 0.018,
        "transition_demand_shock_2050": 0.205,
        "carbon_cost_shock_2050": 0.120,
        "energy_cost_shock_2050": 0.060,
        "transition_capex_shock_2050": 0.075,
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
        "country_gdp_loss_2050": 0.005,
        "supply_chain_shock_2050": 0.015,
        "inflation_shock_2050": 0.010,
        "unemployment_shock_2050": 0.006,
        "transition_demand_shock_2050": 0.025,
        "carbon_cost_shock_2050": 0.010,
        "energy_cost_shock_2050": 0.020,
        "transition_capex_shock_2050": 0.015,
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
        "country_gdp_loss_2050": 0.025,
        "supply_chain_shock_2050": 0.055,
        "inflation_shock_2050": 0.035,
        "unemployment_shock_2050": 0.022,
        "transition_demand_shock_2050": 0.160,
        "carbon_cost_shock_2050": 0.080,
        "energy_cost_shock_2050": 0.080,
        "transition_capex_shock_2050": 0.060,
        "carbon_price_label": "Uneven",
        "note": "Elevated physical losses combine with an inefficient, regionally fragmented transition.",
    },
}


# Cash-flow transmission parameters for the transition model. These are
# transparent sector calibrations, not observed issuer data. Production values
# should be replaced by NGFS/BNEF demand paths, EIA energy prices, EPA eGRID
# emissions, and SEC issuer financials. Demand elasticity is signed: negative
# values represent sectors that may benefit from transition demand.
SECTOR_TRANSITION_CHANNELS = {
    "Energy": {"carbon_intensity": 0.94, "demand_elasticity": 0.95, "energy_intensity": 0.85, "capex_intensity": 0.65, "pass_through": 0.45},
    "Utilities": {"carbon_intensity": 0.78, "demand_elasticity": 0.25, "energy_intensity": 0.85, "capex_intensity": 0.85, "pass_through": 0.65},
    "Industrials": {"carbon_intensity": 0.62, "demand_elasticity": 0.55, "energy_intensity": 0.70, "capex_intensity": 0.62, "pass_through": 0.45},
    "Technology": {"carbon_intensity": 0.30, "demand_elasticity": -0.45, "energy_intensity": 0.35, "capex_intensity": 0.20, "pass_through": 0.75},
    "Financial Services": {"carbon_intensity": 0.42, "demand_elasticity": 0.25, "energy_intensity": 0.18, "capex_intensity": 0.25, "pass_through": 0.70},
    "Financials": {"carbon_intensity": 0.42, "demand_elasticity": 0.25, "energy_intensity": 0.18, "capex_intensity": 0.25, "pass_through": 0.70},
    "Consumer Cyclical": {"carbon_intensity": 0.44, "demand_elasticity": 0.40, "energy_intensity": 0.55, "capex_intensity": 0.35, "pass_through": 0.55},
    "Consumer Defensive": {"carbon_intensity": 0.38, "demand_elasticity": 0.25, "energy_intensity": 0.60, "capex_intensity": 0.35, "pass_through": 0.65},
    "Healthcare": {"carbon_intensity": 0.28, "demand_elasticity": 0.20, "energy_intensity": 0.45, "capex_intensity": 0.30, "pass_through": 0.65},
    "Basic Materials": {"carbon_intensity": 0.82, "demand_elasticity": 0.75, "energy_intensity": 0.90, "capex_intensity": 0.72, "pass_through": 0.40},
    "Real Estate": {"carbon_intensity": 0.52, "demand_elasticity": 0.45, "energy_intensity": 0.70, "capex_intensity": 0.62, "pass_through": 0.45},
    "Communication Services": {"carbon_intensity": 0.30, "demand_elasticity": -0.15, "energy_intensity": 0.50, "capex_intensity": 0.25, "pass_through": 0.70},
}


# Revenue transmission fallback used when point-in-time issuer geography and
# supplier/customer data are unavailable. GDP beta maps the country pathway to
# issuer revenue; supply beta maps BEA-style indirect input-output disruption.
SECTOR_MACRO_TRANSMISSION = {
    "Energy": {"gdp_beta": 0.90, "supply_beta": 0.85},
    "Utilities": {"gdp_beta": 0.45, "supply_beta": 0.55},
    "Industrials": {"gdp_beta": 1.10, "supply_beta": 1.20},
    "Technology": {"gdp_beta": 1.05, "supply_beta": 0.90},
    "Financial Services": {"gdp_beta": 1.10, "supply_beta": 0.70},
    "Financials": {"gdp_beta": 1.10, "supply_beta": 0.70},
    "Consumer Cyclical": {"gdp_beta": 1.25, "supply_beta": 1.05},
    "Consumer Defensive": {"gdp_beta": 0.55, "supply_beta": 0.85},
    "Healthcare": {"gdp_beta": 0.50, "supply_beta": 0.75},
    "Basic Materials": {"gdp_beta": 1.00, "supply_beta": 1.15},
    "Real Estate": {"gdp_beta": 1.05, "supply_beta": 0.65},
    "Communication Services": {"gdp_beta": 0.95, "supply_beta": 0.65},
}

SECTOR_VALUATION_ASSUMPTIONS = {
    "Energy": {"equity_beta": 0.95, "debt_ratio": 0.32, "terminal_growth": 0.018},
    "Utilities": {"equity_beta": 0.65, "debt_ratio": 0.52, "terminal_growth": 0.020},
    "Industrials": {"equity_beta": 1.10, "debt_ratio": 0.30, "terminal_growth": 0.022},
    "Technology": {"equity_beta": 1.15, "debt_ratio": 0.16, "terminal_growth": 0.025},
    "Financial Services": {"equity_beta": 1.05, "debt_ratio": 0.38, "terminal_growth": 0.021},
    "Financials": {"equity_beta": 1.05, "debt_ratio": 0.38, "terminal_growth": 0.021},
    "Consumer Cyclical": {"equity_beta": 1.15, "debt_ratio": 0.34, "terminal_growth": 0.022},
    "Consumer Defensive": {"equity_beta": 0.70, "debt_ratio": 0.30, "terminal_growth": 0.021},
    "Healthcare": {"equity_beta": 0.80, "debt_ratio": 0.24, "terminal_growth": 0.023},
    "Basic Materials": {"equity_beta": 1.05, "debt_ratio": 0.32, "terminal_growth": 0.019},
    "Real Estate": {"equity_beta": 0.90, "debt_ratio": 0.48, "terminal_growth": 0.020},
    "Communication Services": {"equity_beta": 0.95, "debt_ratio": 0.30, "terminal_growth": 0.022},
}

SCENARIO_MATRIX_KEYS = (
    "net_zero_2050",
    "below_2c",
    "delayed_transition",
    "current_policies",
    "fragmented_world",
)


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


# Covered-sector value-added shares used to normalize top-down physical-risk
# multipliers. They are transparent prototype weights and can be replaced with
# country-specific UN/BEA weights without changing the equations.
SECTOR_VALUE_ADDED_WEIGHTS = {
    "Real Estate": 0.13,
    "Utilities": 0.03,
    "Energy": 0.04,
    "Basic Materials": 0.04,
    "Consumer Defensive": 0.09,
    "Consumer Cyclical": 0.10,
    "Industrials": 0.12,
    "Healthcare": 0.11,
    "Technology": 0.10,
    "Communication Services": 0.07,
    "Financials": 0.10,
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

# Controlled research taxonomy used by issuer-level application paths. This is
# an explicit project crosswalk, not observed issuer climate data and not a
# substitute for the governed Entity_Master export planned by CFP-2026-002.
ISSUER_SECTOR_CROSSWALK = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "FSLR": "Technology",
    "ENPH": "Technology",
    "XOM": "Energy",
    "CVX": "Energy",
    "NEE": "Utilities",
    "DUK": "Utilities",
    "JPM": "Financials",
    "BAC": "Financials",
    "GS": "Financials",
    "TRV": "Financials",
    "CB": "Financials",
    "CAT": "Industrials",
    "DE": "Industrials",
    "AMZN": "Consumer Cyclical",
    "TSLA": "Consumer Cyclical",
    "GOOGL": "Communication Services",
    "META": "Communication Services",
}
ISSUER_SECTOR_CROSSWALK_AS_OF = "2026-07-28"
ISSUER_SECTOR_CROSSWALK_SOURCE = "Controlled application research taxonomy; governed Entity_Master export pending"
MARKET_SECTOR_METADATA_SOURCE = "Yahoo Finance quote metadata via yfinance; reference classification, not issuer-verified"
MARKET_SECTOR_METADATA_CACHE = {}
MARKET_SECTOR_METADATA_LOCK = threading.Lock()
ISSUER_SECTOR_MASTER_CACHE = None
ISSUER_SECTOR_MASTER_LOCK = threading.Lock()


HAZARD_SECTOR_BETAS = {
    "heat": {"Energy": 0.66, "Utilities": 0.92, "Industrials": 0.76, "Technology": 0.44, "Financials": 0.28, "Financial Services": 0.28, "Consumer Cyclical": 0.55, "Consumer Defensive": 0.60, "Healthcare": 0.58, "Basic Materials": 0.78, "Real Estate": 0.54, "Communication Services": 0.38},
    "flood": {"Energy": 0.82, "Utilities": 0.90, "Industrials": 0.86, "Technology": 0.35, "Financials": 0.76, "Financial Services": 0.76, "Consumer Cyclical": 0.64, "Consumer Defensive": 0.70, "Healthcare": 0.55, "Basic Materials": 0.80, "Real Estate": 0.96, "Communication Services": 0.46},
    "fire": {"Energy": 0.72, "Utilities": 0.98, "Industrials": 0.64, "Technology": 0.34, "Financials": 0.72, "Financial Services": 0.72, "Consumer Cyclical": 0.48, "Consumer Defensive": 0.58, "Healthcare": 0.52, "Basic Materials": 0.74, "Real Estate": 0.88, "Communication Services": 0.42},
    "tropical": {"Energy": 0.94, "Utilities": 0.96, "Industrials": 0.90, "Technology": 0.38, "Financials": 0.84, "Financial Services": 0.84, "Consumer Cyclical": 0.72, "Consumer Defensive": 0.74, "Healthcare": 0.62, "Basic Materials": 0.82, "Real Estate": 0.96, "Communication Services": 0.50},
    "storm": {"Energy": 0.78, "Utilities": 0.90, "Industrials": 0.82, "Technology": 0.38, "Financials": 0.72, "Financial Services": 0.72, "Consumer Cyclical": 0.62, "Consumer Defensive": 0.66, "Healthcare": 0.58, "Basic Materials": 0.76, "Real Estate": 0.86, "Communication Services": 0.48},
    "air_quality": {"Energy": 0.52, "Utilities": 0.58, "Industrials": 0.62, "Technology": 0.34, "Financials": 0.24, "Financial Services": 0.24, "Consumer Cyclical": 0.42, "Consumer Defensive": 0.44, "Healthcare": 0.72, "Basic Materials": 0.64, "Real Estate": 0.38, "Communication Services": 0.30},
    "winter": {"Energy": 0.72, "Utilities": 0.88, "Industrials": 0.68, "Technology": 0.32, "Financials": 0.30, "Financial Services": 0.30, "Consumer Cyclical": 0.48, "Consumer Defensive": 0.52, "Healthcare": 0.50, "Basic Materials": 0.66, "Real Estate": 0.48, "Communication Services": 0.34},
}


HAZARD_CATEGORIES = ("heat", "flood", "fire", "tropical", "storm", "air_quality", "winter")

SECTOR_RESILIENCE_FALLBACK = {
    "Energy": 0.25,
    "Utilities": 0.60,
    "Industrials": 0.42,
    "Technology": 0.82,
    "Financials": 0.55,
    "Financial Services": 0.55,
    "Consumer Cyclical": 0.48,
    "Consumer Defensive": 0.58,
    "Healthcare": 0.62,
    "Basic Materials": 0.36,
    "Real Estate": 0.34,
    "Communication Services": 0.68,
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
        "risk_type": "Climate-state context",
        "status": "Official / cached",
        "url": NOAA_CO2_CSV_URL,
        "client_use": "Atmospheric climate-state context only; it is not used as a policy, carbon-cost, or transition-risk score.",
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
        "client_use": "Facility emissions input for the carbon-cost channel; source-ready and not silently replaced by CO2 concentration.",
    },
    {
        "name": "EPA eGRID",
        "risk_type": "Power-sector transition",
        "status": "Source-ready",
        "url": EPA_EGRID_URL,
        "client_use": "Generation mix and emission rates for the carbon-cost and energy-cost channels.",
    },
    {
        "name": "EIA Open Data",
        "risk_type": "Energy transition",
        "status": "API-ready",
        "url": EIA_OPEN_DATA_URL,
        "client_use": "Energy prices, generation mix, demand, and fuel use for the energy-cost and demand-shift channels.",
    },
    {
        "name": "NGFS Scenarios",
        "risk_type": "Scenario transition",
        "status": "Scenario-ready",
        "url": NGFS_SCENARIOS_URL,
        "client_use": "Conditional carbon-price, energy, macro, and sector-demand pathways; no occurrence probability is assigned.",
    },
    {
        "name": "SEC EDGAR APIs",
        "risk_type": "Disclosure / regulation",
        "status": "API-ready",
        "url": SEC_EDGAR_API_URL,
        "client_use": "Revenue, operating cost, CapEx, business segments, and disclosures for issuer-level transition cash-flow mapping.",
    },
    {
        "name": "BEA GDP by Industry",
        "risk_type": "Macro / sector demand",
        "status": "Source-ready",
        "url": BEA_GDP_INDUSTRY_URL,
        "client_use": "Industry value-added history for country-to-sector revenue beta calibration.",
    },
    {
        "name": "BEA Input-Output Accounts",
        "risk_type": "Indirect supply chain",
        "status": "Source-ready",
        "url": BEA_INPUT_OUTPUT_URL,
        "client_use": "Direct and indirect requirements for sector supply-chain shock propagation.",
    },
    {
        "name": "FRED / ALFRED",
        "risk_type": "Point-in-time macro",
        "status": "Source-ready",
        "url": FRED_ALFRED_URL,
        "client_use": "Vintage GDP, inflation, unemployment, rates, and energy series for revision-safe backtests.",
    },
    {
        "name": "U.S. Treasury Daily Rates",
        "risk_type": "Valuation input",
        "status": "Governed release check",
        "url": US_TREASURY_RATES_URL,
        "client_use": "Observed Treasury par yield input. It supplies the risk-free leg only and does not complete an issuer WACC.",
    },
    {
        "name": "NOAA Storm Events",
        "risk_type": "Historical acute physical",
        "status": "Source-ready",
        "url": NOAA_STORM_EVENTS_BULK_URL,
        "client_use": "Historical hazard occurrence and damage calibration; separate from live NWS alerts.",
    },
    {
        "name": "NASA NEX-GDDP-CMIP6",
        "risk_type": "Forward physical hazard",
        "status": "Source-ready",
        "url": NASA_NEX_GDDP_URL,
        "client_use": "Downscaled daily temperature and precipitation pathways for facility-level scenario analysis.",
    },
]


CLIMATE_PROXY = [
    # Research-only historical proxy. These values are never eligible for
    # decision input and stop at the last fixed historical placeholder vintage.
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
]


US_MARKET_NOTES = [
    "Universe uses U.S.-listed common stocks and sector ETFs with USD allocations.",
    "No China A-share 100-share lot rule is used; fractional or single-share sizing can be modeled.",
    "U.S. equities currently settle on T+1, but this is not the same as China-style T+1 resale restrictions.",
    "The prototype does not model PDT, margin, options, borrow fees, taxes, or live execution routing.",
]


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return float(value)
    except Exception:
        return default


def clamp(value, low, high):
    return max(low, min(high, value))


def percentile(values, q):
    vals = sorted([safe_float(v, 0.0) for v in values])
    if not vals:
        return 0.0
    q = clamp(safe_float(q, 0.5), 0.0, 1.0)
    position = (len(vals) - 1) * q
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return vals[lower]
    fraction = position - lower
    return vals[lower] * (1 - fraction) + vals[upper] * fraction


def expanding_zscore(values, index):
    history = [safe_float(value, 0.0) for value in values[: index + 1]]
    if len(history) < 3:
        return 0.0
    mean = sum(history) / len(history)
    variance = sum((value - mean) ** 2 for value in history) / max(1, len(history) - 1)
    std = math.sqrt(variance)
    return (history[-1] - mean) / std if std > 1e-12 else 0.0


def yahoo_symbol(symbol):
    return str(symbol).strip().upper().replace(".", "-")


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
                fallback_notes = [
                    note
                    for note in cached.get("source_notes", [])
                    if "fallback" in str(note).lower() or "proxy" in str(note).lower()
                ]
                if fallback_notes:
                    cached["source_mode_original"] = cached.get("source_mode")
                    cached["source_mode"] = (
                        "mixed official and non-official climate data"
                        if len(fallback_notes) < len(cached.get("source_notes", []))
                        else "non-official fallback climate data"
                    )
                    cached["classification_correction"] = (
                        "legacy cache relabeled because its source notes disclose fallback or proxy inputs"
                    )
                cached["cache_status"] = "cached"
                cached["cache_age_days"] = round(age_days, 4)
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
    source_status = {}
    try:
        temp_map = parse_nasa_gistemp(download_text(NASA_GISTEMP_CSV_URL, timeout=18))
        if not temp_map:
            raise ValueError("NASA GISTEMP returned no annual observations")
        source_notes.append("NASA GISTEMP land-ocean annual temperature anomaly")
        source_status["temperature"] = "observed official"
    except Exception:
        temp_map = fallback_temp
        source_notes.append("fallback temperature proxy")
        source_status["temperature"] = "calibrated proxy"

    try:
        co2_map = parse_noaa_co2(download_text(NOAA_CO2_CSV_URL, timeout=18))
        if not co2_map:
            raise ValueError("NOAA GML returned no CO2 observations")
        source_notes.append("NOAA GML Mauna Loa monthly CO2")
        source_status["co2"] = "observed official"
    except Exception:
        co2_map = fallback_co2
        source_notes.append("fallback CO2 proxy")
        source_status["co2"] = "calibrated proxy"

    try:
        disaster_map, cost_map = parse_ncei_disasters(download_text(NCEI_BILLION_EVENTS_JSON_URL, timeout=25))
        if not disaster_map:
            raise ValueError("NOAA NCEI returned no disaster observations")
        source_notes.append("NOAA NCEI billion-dollar weather and climate disasters")
        source_status["disasters"] = "observed official"
    except Exception:
        disaster_map, cost_map = fallback_disasters, fallback_costs
        source_notes.append("fallback disaster-frequency proxy")
        source_status["disasters"] = "calibrated proxy"

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
        temperature_source = None
        if temp is None:
            if source_status["temperature"] == "observed official" and last_temp is not None:
                temp = last_temp
                temperature_source = "official carry-forward"
            else:
                temp = fallback_temp.get(year)
                temperature_source = "calibrated proxy" if temp is not None else "unavailable"
        else:
            last_temp = temp
            last_temp_year = year
            temperature_source = (
                "official" if source_status["temperature"] == "observed official" else "calibrated proxy"
            )
        observed_co2 = co2_map.get(year)
        co2 = observed_co2
        co2_year = year if observed_co2 is not None else last_co2_year
        co2_source = None
        if co2 is None:
            if source_status["co2"] == "observed official" and last_co2 is not None:
                co2 = last_co2
                co2_source = "official carry-forward"
            else:
                co2 = fallback_co2.get(year)
                co2_source = "calibrated proxy" if co2 is not None else "unavailable"
        if observed_co2 is not None:
            last_co2 = observed_co2
            last_co2_year = year
        if co2 is not None:
            if co2_source is None:
                co2_source = "official" if source_status["co2"] == "observed official" else "calibrated proxy"
        disasters = disaster_map.get(year)
        disaster_year = year if disasters is not None else None
        if disasters is None and source_status["disasters"] == "calibrated proxy":
            disasters = fallback_disasters.get(year, 0)
            disaster_year = year if year in fallback_disasters else None
        cost = cost_map.get(year, fallback_costs.get(year, 0))
        if temp is None and co2 is None and not disasters:
            continue
        disaster_source = (
            "official"
            if source_status["disasters"] == "observed official" and disaster_year == year
            else ("calibrated proxy" if disaster_year == year else "unavailable")
        )
        complete_official = (
            year < CURRENT_YEAR
            and temperature_source == "official"
            and co2_source == "official"
            and disaster_source == "official"
        )
        field_sources = {temperature_source, co2_source, disaster_source}
        row_source_class = (
            "observed official"
            if complete_official
            else ("calibrated proxy" if field_sources == {"calibrated proxy"} else "mixed or incomplete")
        )
        rows.append(
            {
                "year": year,
                "temperature_anomaly": round(safe_float(temp, 0), 3) if temp is not None else None,
                "temperature_year": temp_year,
                "temperature_source": temperature_source,
                "co2_ppm": round(safe_float(co2, 0), 2) if co2 is not None else None,
                "co2_year": co2_year,
                "co2_source": co2_source,
                "billion_dollar_disasters": int(disasters) if disasters is not None else None,
                "disaster_year": disaster_year,
                "disaster_source": disaster_source,
                "disaster_cost_proxy": round(safe_float(cost, 0), 2) if cost is not None else None,
                "source_class": row_source_class,
                "is_complete_official_observation": complete_official,
                "allowed_use": "decision input" if complete_official else "context only",
            }
        )

    source_classes = set(source_status.values())
    contains_non_official = any(
        row.get(field) == "calibrated proxy"
        for row in rows
        for field in ("temperature_source", "co2_source", "disaster_source")
    )
    contains_incomplete = any(row.get("source_class") != "observed official" for row in rows)
    if source_classes == {"observed official"} and not contains_incomplete:
        source_mode = "official climate data"
    elif source_classes == {"calibrated proxy"}:
        source_mode = "non-official fallback climate data"
    elif contains_non_official:
        source_mode = "mixed official and non-official climate data"
    else:
        source_mode = "official-source climate data with incomplete observations"
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "release_id": f"climate-data-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "source_mode": source_mode,
        "source_status": source_status,
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
    decision_rows = [
        row
        for row in rows
        if row.get("is_complete_official_observation") is True
        and int(row.get("year", CURRENT_YEAR)) < CURRENT_YEAR
    ]
    if not decision_rows:
        return {
            "current_warming": None,
            "latest_year": None,
            "co2_ppm": None,
            "co2_10y_change": None,
            "disaster_10y_avg": None,
            "climate_pressure_multiplier": None,
            "source_mode": data.get("source_mode", "climate data unavailable"),
            "source_status": "not calculable — no complete official completed-year observation",
            "source_notes": data.get("source_notes", []),
            "source_urls": data.get("source_urls", {}),
        }
    latest = decision_rows[-1]
    recent = decision_rows[-10:] if len(decision_rows) >= 10 else decision_rows
    prior_idx = max(0, len(decision_rows) - 11)
    prior = decision_rows[prior_idx]
    disaster_10y_avg = sum(r.get("billion_dollar_disasters", 0) for r in recent) / max(1, len(recent))
    co2_change = safe_float(latest.get("co2_ppm"), 0) - safe_float(prior.get("co2_ppm"), 0)
    temp = safe_float(latest.get("temperature_anomaly"), 0.0)
    multiplier = (
        1.0
        + clamp((temp - 1.0) * 0.12, -0.04, 0.10)
        + clamp((disaster_10y_avg - 15) * 0.01, -0.03, 0.08)
    )
    return {
        "current_warming": round(max(0.75, temp), 3),
        "latest_year": latest.get("year"),
        "co2_ppm": latest.get("co2_ppm", 0),
        "co2_10y_change": round(co2_change, 2),
        "disaster_10y_avg": round(disaster_10y_avg, 2),
        "climate_pressure_multiplier": round(clamp(multiplier, 0.85, 1.30), 4),
        "source_mode": "validated official completed-year observations",
        "payload_source_mode": data.get("source_mode", "official climate data"),
        "source_status": "available",
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
                cached["source_mode_original"] = cached.get("source_mode", "NWS active weather alerts")
                cached["source_mode"] = "cached NWS active alerts"
                cached["cache_status"] = "cached"
                cached.setdefault("is_calculable", True)
                cached.setdefault("observed_zero", safe_float(cached.get("climate_alerts"), 0.0) == 0)
                cached.setdefault(
                    "decision_status",
                    (
                        "observed zero — NWS feed successful, no matched climate alerts"
                        if cached["observed_zero"]
                        else "calculable — observed NWS active-alert severity"
                    ),
                )
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
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_mode": "fallback daily climate pulse",
        "source_url": NWS_ACTIVE_ALERTS_URL,
        "alerts_total": None,
        "climate_alerts": None,
        "weighted_alert_score": None,
        "daily_pressure": None,
        "allocation_pressure": None,
        "top_driver": "unavailable",
        "is_calculable": False,
        "observed_zero": False,
        "decision_status": "not calculable — live NWS hazard data unavailable",
        "category_counts": {},
        "category_intensity": {},
        "sample_events": [],
    }


def short_term_hazard_is_calculable(daily_signal):
    if not isinstance(daily_signal, dict):
        return False
    explicit = daily_signal.get("is_calculable")
    if explicit is not None:
        return bool(explicit)
    status = str(daily_signal.get("decision_status", "")).lower()
    source_mode = str(daily_signal.get("source_mode", "")).lower()
    return "not calculable" not in status and "fallback" not in source_mode


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
        multiplier = context.get("climate_pressure_multiplier")
        long_run_available = multiplier is not None
        long_run_pressure = (
            clamp((safe_float(multiplier, 0.90) - 0.90) / 0.40, 0.0, 1.0)
            if long_run_available
            else None
        )
        allocation_pressure = (
            clamp(0.72 * daily_pressure + 0.28 * long_run_pressure, 0.0, 1.0)
            if long_run_pressure is not None
            else daily_pressure
        )
        top_driver = max(category_scores.items(), key=lambda kv: kv[1])[0] if weighted_score > 0 else "none"
        category_intensity = {
            k: round(clamp(v / max(1.0, weighted_score), 0.0, 1.0), 4)
            for k, v in category_scores.items()
        }
        observed_zero = climate_alerts == 0
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
            "is_calculable": True,
            "observed_zero": observed_zero,
            "decision_status": (
                "observed zero — NWS feed successful, no matched climate alerts"
                if observed_zero
                else "calculable — observed NWS active-alert severity"
            ),
            "long_run_context_status": (
                "available"
                if long_run_available
                else "not calculable — long-run context excluded from live NWS pressure"
            ),
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
    categories = daily_signal.get("category_intensity", {}) or {}
    category_total = sum(max(0.0, safe_float(categories.get(hazard), 0.0)) for hazard in HAZARD_CATEGORIES)
    event_pressure = clamp(safe_float(daily_signal.get("daily_pressure"), 0.0), 0.0, 1.0) if category_total > 0 else 0.0
    normalized_categories = {
        hazard: max(0.0, safe_float(categories.get(hazard), 0.0)) / category_total
        for hazard in HAZARD_CATEGORIES
    } if category_total > 0 else {hazard: 0.0 for hazard in HAZARD_CATEGORIES}
    row_scores = []
    for row in latest_alloc:
        ticker = row["ticker"]
        meta = SECTOR_ETFS.get(ticker, {})
        sector = normalize_model_sector(row.get("sector") or meta.get("name"))
        hazard_beta = sum(
            normalized_categories[hazard] * HAZARD_SECTOR_BETAS.get(hazard, {}).get(sector, 0.50)
            for hazard in HAZARD_CATEGORIES
        )
        sector_stress = event_pressure * hazard_beta
        adaptive_score = safe_float(meta.get("resilience"), 0.50) - hazard_beta
        row_scores.append((row, sector_stress, adaptive_score, hazard_beta))

    base_total = sum(safe_float(row.get("climate_weight"), 0.0) for row, _, _, _ in row_scores) or 1.0
    weighted_mean = sum(
        safe_float(row.get("climate_weight"), 0.0) / base_total * adaptive_score
        for row, _, adaptive_score, _ in row_scores
    )
    raw_deltas = {
        row["ticker"]: safe_float(row.get("climate_weight"), 0.0)
        * event_pressure
        * 0.50
        * (adaptive_score - weighted_mean)
        for row, _, adaptive_score, _ in row_scores
    }
    max_raw_delta = max((abs(delta) for delta in raw_deltas.values()), default=0.0)
    overlay_limit = TACTICAL_OVERLAY_LIMIT_BPS / 10_000
    delta_scale = min(1.0, overlay_limit / max_raw_delta) if max_raw_delta > 0 else 1.0
    raw_weights = {
        row["ticker"]: max(0.0, safe_float(row.get("climate_weight"), 0.0) + raw_deltas[row["ticker"]] * delta_scale)
        for row, _, _, _ in row_scores
    }
    total = sum(raw_weights.values()) or base_total

    adjusted = []
    for row, sector_stress, adaptive_score, hazard_beta in row_scores:
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
        out["daily_hazard_beta"] = round(hazard_beta, 4)
        out["daily_driver"] = (
            f"{daily_signal.get('top_driver', 'daily')} alert pulse; "
            f"NWS pressure index {event_pressure * 100:.1f}/100 x hazard beta {hazard_beta:.2f}; "
            f"resilience {safe_float(SECTOR_ETFS.get(row['ticker'], {}).get('resilience'), 0.0):.2f}"
        )
        out["action"] = allocation_action(final_weight, safe_float(row.get("benchmark_weight"), 0.0))
        adjusted.append(out)
    return adjusted


def climate_signal():
    official = load_official_climate_data()
    source_rows = [
        row
        for row in official.get("rows", [])
        if row.get("is_complete_official_observation") is True
        and 1980 <= int(row.get("year", 0)) < CURRENT_YEAR
    ]
    if not source_rows:
        return []
    years = [r["year"] for r in source_rows]
    temps = [r.get("temperature_anomaly", 0) for r in source_rows]
    disasters = [r.get("billion_dollar_disasters", 0) for r in source_rows]
    co2 = [r.get("co2_ppm", 0) for r in source_rows]
    costs = [r.get("disaster_cost_proxy", 0) for r in source_rows]
    score = []
    rows = []
    for i, year in enumerate(years):
        temperature_z = expanding_zscore(temps, i)
        disaster_z = expanding_zscore(disasters, i)
        co2_z = expanding_zscore(co2, i)
        cost_z = expanding_zscore(costs, i)
        # Atmospheric CO2 remains context only. It is displayed for lineage but
        # cannot directly drive the allocation regime or a transition score.
        current_score = 0.55 * temperature_z + 0.25 * disaster_z + 0.20 * cost_z
        score.append(current_score)
        threshold = percentile(score, 0.75)
        state = "High Climate Risk" if current_score >= threshold else "Normal Climate Risk"
        rows.append(
            {
                "year": year,
                "temperature_anomaly": round(temps[i], 3),
                "co2_ppm": round(co2[i], 2),
                "disaster_frequency": disasters[i],
                "disaster_cost_proxy": round(costs[i], 2),
                "temperature_z": round(temperature_z, 3),
                "co2_z": round(co2_z, 3),
                "disaster_z": round(disaster_z, 3),
                "cost_z": round(cost_z, 3),
                "climate_risk_score": round(current_score, 3),
                "risk_state": state,
                "top_quartile_threshold": round(threshold, 3),
                "normalization_window": f"expanding through {year}",
            }
        )
    return rows


def regime_for_year(year, climate_rows):
    eligible = [row for row in climate_rows if int(row.get("year", 0)) < int(year)]
    prev = max(eligible, key=lambda row: int(row.get("year", 0)), default=None)
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


def climate_scenario_matrix(allocation_rows):
    if not allocation_rows:
        return [], {}
    latest_year = max(r["year"] for r in allocation_rows)
    latest_alloc = [r for r in allocation_rows if r["year"] == latest_year]
    total_weight = sum(safe_float(row.get("climate_weight"), 0.0) for row in latest_alloc) or 1.0
    scope_rows = []
    for row in latest_alloc:
        ticker = row.get("ticker")
        sector = normalize_model_sector(row.get("sector") or SECTOR_ETFS.get(ticker, {}).get("name"))
        scope_rows.append(
            {
                "name": ticker,
                "ticker": ticker,
                "sector": sector,
                "weight": safe_float(row.get("climate_weight"), 0.0) / total_weight,
                "vulnerability": issuer_vulnerability_profile(ticker, sector),
            }
        )

    reference = CLIMATE_SCENARIO_PATHS["baseline"]
    rows = []
    scenario_losses = []
    scenario_impacts = []
    sensitivity_low_losses = []
    sensitivity_high_losses = []
    for scenario_key in SCENARIO_MATRIX_KEYS:
        scenario = CLIMATE_SCENARIO_PATHS[scenario_key]
        result = scenario_repricing_for_scope(scope_rows, scenario, reference, 2050)
        value_impact = safe_float(result.get("value_impact"), 0.0)
        portfolio_loss = max(0.0, -value_impact)
        portfolio_opportunity = max(0.0, value_impact)
        low_impact = scenario_value_impact_without_attribution(
            scope_rows,
            physical_damage_sensitivity_scenario(scenario, 0.70),
            reference,
            2050,
        )
        high_impact = scenario_value_impact_without_attribution(
            scope_rows,
            physical_damage_sensitivity_scenario(scenario, 1.30),
            reference,
            2050,
        )
        low_loss = max(0.0, -low_impact)
        high_loss = max(0.0, -high_impact)
        sector_losses = {}
        for scope_row in scope_rows:
            sector_result = scenario_repricing_for_scope(
                [{**scope_row, "weight": 1.0}],
                scenario,
                reference,
                2050,
            )
            sector_losses[scope_row["ticker"]] = round(max(0.0, -safe_float(sector_result.get("value_impact"), 0.0)), 4)
        scenario_losses.append(portfolio_loss)
        scenario_impacts.append(value_impact)
        sensitivity_low_losses.append(low_loss)
        sensitivity_high_losses.append(high_loss)
        rows.append(
            {
                "scenario": scenario["label"],
                "scenario_key": scenario_key,
                "scenario_type": "Conditional stress",
                "category": scenario["category"],
                "carbon_price_label": scenario["carbon_price_label"],
                "portfolio_value_impact": round(value_impact, 4),
                "portfolio_loss_rate": round(portfolio_loss, 4),
                "conditional_climate_var_rate": round(portfolio_loss, 4),
                "portfolio_loss_dollars": round(portfolio_loss * DEFAULT_PORTFOLIO_VALUE, 2),
                "portfolio_opportunity_rate": round(portfolio_opportunity, 4),
                "physical_model_risk_low_loss_rate": round(low_loss, 4),
                "physical_model_risk_high_loss_rate": round(high_loss, 4),
                "physical_damage_multiplier_range": "0.70x-1.30x",
                "sector_losses": sector_losses,
                "narrative": scenario["note"],
            }
        )
    average_loss = sum(scenario_losses) / max(1, len(scenario_losses))
    average_impact = sum(scenario_impacts) / max(1, len(scenario_impacts))
    worst_loss = max(scenario_losses, default=0.0)
    best_loss = min(scenario_losses, default=0.0)
    sorted_rows = sorted(rows, key=lambda r: r["portfolio_loss_rate"], reverse=True)
    tail = sorted_rows[:SCENARIO_TAIL_COUNT]
    scenario_tail = sum(r["portfolio_loss_rate"] for r in tail) / max(1, len(tail))
    summary = {
        "unweighted_mean_value_impact": round(average_impact, 4),
        "cross_scenario_mean_loss_rate": round(average_loss, 4),
        "cross_scenario_mean_loss_dollars": round(average_loss * DEFAULT_PORTFOLIO_VALUE, 2),
        "average_scenario_loss_rate": round(average_loss, 4),
        "average_scenario_loss_dollars": round(average_loss * DEFAULT_PORTFOLIO_VALUE, 2),
        "worst_scenario_loss_rate": round(worst_loss, 4),
        "worst_scenario_loss_dollars": round(worst_loss * DEFAULT_PORTFOLIO_VALUE, 2),
        "scenario_loss_min_rate": round(best_loss, 4),
        "scenario_loss_max_rate": round(worst_loss, 4),
        "scenario_loss_range_rate": round(worst_loss - best_loss, 4),
        "scenario_tail_loss_rate": round(scenario_tail, 4),
        "scenario_tail_loss_dollars": round(scenario_tail * DEFAULT_PORTFOLIO_VALUE, 2),
        "tail_count": len(tail),
        "tail_scenarios": [row["scenario"] for row in tail],
        "cross_scenario_weighting": "Equal-weight diagnostic only; not an expectation",
        "scenario_probability_method": "No occurrence probabilities assigned. Results are conditional target-versus-baseline repricing stresses.",
        "model_ensemble_tail_loss_rate": round(scenario_tail, 4),
        "tail_label": "Model-ensemble tail: mean of two largest conditional scenario losses; not CVOR95 or Expected Shortfall",
        "physical_model_risk_loss_floor": round(min(sensitivity_low_losses, default=0.0), 4),
        "physical_model_risk_loss_ceiling": round(max(sensitivity_high_losses, default=0.0), 4),
        "physical_model_risk_method": "Physical damage coefficients are rerun at 0.70x and 1.30x; this is a transparent sensitivity band, not a confidence interval.",
        "conditional_value_definition": "Conditional loss sensitivity = max(0, [PV(reference FCFF) - PV(scenario FCFF)] / PV(reference FCFF)); project-calibrated and not statistical VaR",
        "calculation_rule": "Each scenario uses the same country-to-sector-to-issuer cash-flow and DCF engine as Model Lab.",
    }
    return rows, summary


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
    source = "market data unavailable"

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
        charts.setdefault(symbol, [])
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
    sector = normalize_model_sector(sector)
    if sector == "Economy":
        weights = normalized_sector_value_added_weights()
        factors = {
            key: sum(weight * safe_float(SECTOR_TRANSITION_FACTORS[name].get(key), 0.50) for name, weight in weights.items())
            for key in ("emissions", "policy", "carbon_price", "transition_opportunity")
        }
        factors["headline"] = "Diversified economy exposure uses value-added-weighted sector transition channels."
    else:
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
    event_pressure = clamp(
        safe_float(daily_signal.get("daily_pressure"), safe_float(daily_signal.get("allocation_pressure"), 0.0)),
        0.0,
        1.0,
    )
    allocation_pressure = clamp(safe_float(daily_signal.get("allocation_pressure"), event_pressure), 0.0, 1.0)
    acute_hazard = event_pressure
    chronic_available = (
        context.get("current_warming") is not None
        and context.get("disaster_10y_avg") is not None
        and context.get("source_status") != "not calculable — no complete official completed-year observation"
    )
    chronic_state = (
        clamp(
            0.65 * clamp((safe_float(context.get("current_warming"), 0.0) - 0.75) / 0.85, 0, 1)
            + 0.35 * clamp((safe_float(context.get("disaster_10y_avg"), 0.0) - 8) / 20, 0, 1),
            0.0,
            1.0,
        )
        if chronic_available
        else 0.0
    )
    # No live macro-transition score is fabricated from atmospheric CO2. The
    # strategic scenario engine supplies transition pathways; current-state
    # issuer scores use disclosed sector-channel calibrations until NGFS/EIA/
    # EPA/SEC inputs are loaded.
    macro_transition = 0.0
    official_mode = str(context.get("source_mode", "")).lower()
    alert_mode = str(daily_signal.get("source_mode", "")).lower()
    source_reliability = (
        0.95
        if official_mode == "validated official completed-year observations"
        else (0.65 if "mixed" in official_mode else 0.35)
    )
    alert_reliability = 0.95 if "nws active" in alert_mode else (0.85 if "cached nws" in alert_mode else 0.45)
    data_confidence = clamp(0.55 * source_reliability + 0.45 * alert_reliability, 0.35, 0.95)
    return {
        "acute_hazard_state": round(acute_hazard, 4),
        "chronic_climate_state": round(chronic_state, 4),
        "chronic_data_status": "available" if chronic_available else "not calculable — verified chronic inputs unavailable",
        "macro_transition_state": round(macro_transition, 4),
        "macro_transition_status": "Scenario-only; live NGFS/EIA/EPA/SEC transition inputs not loaded",
        "daily_pressure": round(event_pressure, 4),
        "allocation_pressure": round(allocation_pressure, 4),
        "data_confidence": round(data_confidence, 4),
        "top_driver": daily_signal.get("top_driver", "climate"),
        "source_mode": daily_signal.get("source_mode", context.get("source_mode", "cached data")),
        "calculation": {
            "acute": "NWS severity-weighted event pressure only",
            "chronic": "0.65 observed warming + 0.35 trailing disaster frequency from complete official years; CO2 is contextual only",
            "transition": "Carbon cost + demand shift + energy cost + transition CapEx - pass-through; no CO2 concentration input",
            "confidence": "0.55 official-climate reliability + 0.45 NWS reliability",
        },
    }


def realized_market_beta(asset_rows, benchmark_rows):
    asset = {str(row.get("date")): safe_float(row.get("close"), 0.0) for row in (asset_rows or []) if safe_float(row.get("close"), 0.0) > 0}
    benchmark = {str(row.get("date")): safe_float(row.get("close"), 0.0) for row in (benchmark_rows or []) if safe_float(row.get("close"), 0.0) > 0}
    dates = sorted(set(asset) & set(benchmark))
    if len(dates) < 40:
        return None
    asset_returns = []
    benchmark_returns = []
    for index in range(1, len(dates)):
        a0, a1 = asset[dates[index - 1]], asset[dates[index]]
        b0, b1 = benchmark[dates[index - 1]], benchmark[dates[index]]
        if a0 > 0 and b0 > 0:
            asset_returns.append(a1 / a0 - 1)
            benchmark_returns.append(b1 / b0 - 1)
    if len(asset_returns) < 30:
        return None
    mean_asset = sum(asset_returns) / len(asset_returns)
    mean_benchmark = sum(benchmark_returns) / len(benchmark_returns)
    covariance = sum(
        (asset_return - mean_asset) * (benchmark_return - mean_benchmark)
        for asset_return, benchmark_return in zip(asset_returns, benchmark_returns)
    ) / max(1, len(asset_returns) - 1)
    variance = sum((value - mean_benchmark) ** 2 for value in benchmark_returns) / max(1, len(benchmark_returns) - 1)
    return clamp(covariance / variance, 0.35, 2.25) if variance > 1e-12 else None


def latest_official_treasury_rate(maturity="10y", releases_root=None):
    """Return the latest governed Treasury par yield as a decimal rate."""
    releases_root = Path(releases_root) if releases_root else DATA_DIR / "releases"
    column = f"yield_{str(maturity).lower()}_pct"
    candidates = []
    for path in releases_root.glob("CFP-2026-003-*/processed/treasury_yield_curve_*.csv"):
        release_dir = path.parents[1]
        manifest_path = release_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            source = next(
                row for row in manifest.get("source_entries", [])
                if row.get("source_id") == "SRC-US-TREASURY" and row.get("processed_path", "").endswith(path.name)
            )
            with path.open(newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    rate_pct = safe_float(row.get(column), None)
                    if rate_pct is None or not row.get("date"):
                        continue
                    candidates.append(
                        {
                            "rate": rate_pct / 100.0,
                            "as_of": row["date"],
                            "release_id": manifest.get("release_id", release_dir.name),
                            "source_url": source.get("source_url"),
                            "source_class": "observed official government rate",
                        }
                    )
        except (OSError, ValueError, StopIteration, json.JSONDecodeError):
            continue
    if not candidates:
        return {
            "rate": None,
            "as_of": None,
            "release_id": None,
            "source_url": None,
            "source_class": "missing — dated Treasury release not loaded",
        }
    return max(candidates, key=lambda row: row["as_of"])


def latest_official_ngfs_transition(releases_root=None):
    """Load the newest hash-verified governed NGFS Phase 5.1 transition release."""
    releases_root = Path(releases_root) if releases_root else DATA_DIR / "releases"
    candidates = []
    for path in releases_root.glob("CFP-2026-003-*/processed/ngfs_5_1_transition_*_to_*.csv"):
        release_dir = path.parents[1]
        manifest_path = release_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            source = next(
                row for row in manifest.get("source_entries", [])
                if row.get("source_id") == "SRC-NGFS-PHASE-5-1-TRANSITION"
                and row.get("processed_path", "").endswith(path.name)
            )
            expected_hash = source.get("processed_sha256")
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if not expected_hash or actual_hash != expected_hash:
                continue
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            if not rows:
                continue
            candidates.append(
                {
                    "is_loaded": True,
                    "release_id": manifest.get("release_id", release_dir.name),
                    "source_release": source.get("source_vintage"),
                    "source_release_date": source.get("source_release_date"),
                    "source_url": source.get("source_url"),
                    "region": source.get("region"),
                    "variables": source.get("variables") or [],
                    "models": source.get("models") or [],
                    "scenarios": source.get("scenarios") or [],
                    "rows": rows,
                    "processed_sha256": actual_hash,
                    "physical_damage_status": "excluded — affected Phase 5 physical-damage variables are not used",
                }
            )
        except (OSError, ValueError, StopIteration, json.JSONDecodeError):
            continue
    if not candidates:
        return {
            "is_loaded": False,
            "release_id": None,
            "source_release": None,
            "source_release_date": None,
            "source_url": NGFS_SCENARIOS_URL,
            "region": None,
            "variables": [],
            "models": [],
            "scenarios": [],
            "rows": [],
            "physical_damage_status": "not evaluated",
        }
    return max(candidates, key=lambda row: governed_release_sort_key(row["release_id"]))


def latest_official_sec_financial_history(releases_root=None):
    """Load the newest hash-verified governed SEC financial-history release."""
    releases_root = Path(releases_root) if releases_root else DATA_DIR / "releases"
    candidates = []
    for release_dir in releases_root.glob("CFP-2026-003-*"):
        manifest_path = release_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            history = manifest.get("sec_financial_history") or {}
            fact_rel = history.get("processed_fact_path")
            coverage_rel = history.get("coverage_path")
            fact_path = PROJECT_DIR / fact_rel if fact_rel else None
            coverage_path = PROJECT_DIR / coverage_rel if coverage_rel else None
            if not fact_path or not coverage_path or not fact_path.exists() or not coverage_path.exists():
                continue
            fact_hash = hashlib.sha256(fact_path.read_bytes()).hexdigest()
            coverage_hash = hashlib.sha256(coverage_path.read_bytes()).hexdigest()
            if fact_hash != history.get("processed_fact_sha256"):
                continue
            if coverage_hash != history.get("coverage_sha256"):
                continue
            with coverage_path.open(newline="", encoding="utf-8") as handle:
                coverage_rows = list(csv.DictReader(handle))
            if not coverage_rows:
                continue
            candidates.append(
                {
                    "is_loaded": True,
                    "release_id": manifest.get("release_id", release_dir.name),
                    "start_period": history.get("start_period"),
                    "end_period": history.get("end_period"),
                    "quarter_count": int(history.get("quarter_count") or 0),
                    "fact_count": int(history.get("fact_count") or 0),
                    "filing_count": int(history.get("filing_count") or 0),
                    "tickers": history.get("tickers") or [],
                    "raw_source_release_id": history.get("raw_source_release_id"),
                    "coverage_rows": coverage_rows,
                    "processed_fact_sha256": fact_hash,
                    "coverage_sha256": coverage_hash,
                    "status": "official issuer-filed history loaded; accounting and FCFF tie-out pending",
                }
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    if not candidates:
        return {
            "is_loaded": False,
            "release_id": None,
            "start_period": None,
            "end_period": None,
            "quarter_count": 0,
            "fact_count": 0,
            "filing_count": 0,
            "tickers": [],
            "coverage_rows": [],
            "status": "official SEC financial history not loaded",
        }
    return max(candidates, key=lambda row: governed_release_sort_key(row["release_id"]))


def latest_governed_duke_pilot(releases_root=None):
    """Load the newest DUK pilot only when every processed file matches its hash."""
    releases_root = Path(releases_root) if releases_root else DATA_DIR / "releases"
    candidates = []
    for release_dir in releases_root.glob("CFP-2026-003-*"):
        manifest_path = release_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            pilot = manifest.get("duk_pilot") or {}
            hashes = pilot.get("processed_sha256") or {}
            if pilot.get("ticker") != "DUK" or not hashes:
                continue
            loaded = {}
            valid = True
            for relative, expected_hash in hashes.items():
                path = PROJECT_DIR / relative
                if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                    valid = False
                    break
                with path.open(newline="", encoding="utf-8") as handle:
                    loaded[path.name] = list(csv.DictReader(handle))
            if not valid:
                continue
            facilities = loaded.get("duk_epa_facility_emissions_2023.csv", [])
            physical = loaded.get("duk_facility_fema_context_2025.csv", [])
            candidates.append({
                "is_loaded": True,
                "release_id": manifest.get("release_id", release_dir.name),
                "epa_year": pilot.get("epa_year"),
                "parent_records": int(pilot.get("parent_records") or 0),
                "direct_emitter_matches": int(pilot.get("direct_emitter_matches") or 0),
                "coordinate_matches": int(pilot.get("coordinate_matches") or 0),
                "fema_county_matches": sum(row.get("hazard_match_status", "").startswith("matched") for row in physical),
                "ownership_adjusted_nonbiogenic_co2_tonnes": safe_float(pilot.get("ownership_adjusted_nonbiogenic_co2_tonnes"), None),
                "fcff_bridge": (loaded.get("duk_sec_fcff_bridge_2025.csv") or [{}])[0],
                "carbon_sensitivity": (loaded.get("duk_carbon_price_sensitivity.csv") or [{}])[0],
                "facility_rows": facilities,
                "physical_rows": physical,
                "physical_financial_status": pilot.get("physical_financial_status"),
                "valuation_status": pilot.get("valuation_status"),
                "sec_source_release_id": pilot.get("sec_source_release_id"),
                "ngfs_source_release_id": pilot.get("ngfs_source_release_id"),
                "processed_sha256": hashes,
            })
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    if not candidates:
        return {
            "is_loaded": False, "release_id": None, "parent_records": 0,
            "direct_emitter_matches": 0, "coordinate_matches": 0,
            "fema_county_matches": 0, "facility_rows": [], "physical_rows": [],
            "physical_financial_status": "not calculable",
            "valuation_status": "not calculable",
        }
    return max(candidates, key=lambda row: governed_release_sort_key(row["release_id"]))


def latest_eight_issuer_demo(releases_root=None):
    """Load the newest hash-verified eight-issuer demo screen."""
    releases_root = Path(releases_root) if releases_root else DATA_DIR / "releases"
    candidates = []
    for release_dir in releases_root.glob("CFP-2026-003-*"):
        manifest_path = release_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            demo = manifest.get("eight_issuer_demo") or {}
            relative = demo.get("processed_path")
            path = PROJECT_DIR / relative if relative else None
            if not path or not path.exists():
                continue
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual_hash != demo.get("processed_sha256"):
                continue
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            if len(rows) != 8:
                continue
            candidates.append({
                "is_loaded": True,
                "release_id": manifest.get("release_id", release_dir.name),
                "fcf_definition": demo.get("fcf_definition"),
                "rows": rows,
                "processed_sha256": actual_hash,
            })
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    if not candidates:
        return {"is_loaded": False, "release_id": None, "rows": []}
    return max(candidates, key=lambda row: governed_release_sort_key(row["release_id"]))


def latest_eight_issuer_public_evidence(releases_root=None):
    """Load the newest hash-verified eight-issuer public-evidence release."""
    releases_root = Path(releases_root) if releases_root else DATA_DIR / "releases"
    candidates = []
    for release_dir in releases_root.glob("CFP-2026-003-*"):
        manifest_path = release_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            evidence = manifest.get("eight_issuer_public_evidence") or {}
            hashes = evidence.get("processed_sha256") or {}
            if len(evidence.get("tickers") or []) != 8 or not hashes:
                continue
            loaded, valid = {}, True
            for relative, expected_hash in hashes.items():
                path = PROJECT_DIR / relative
                if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                    valid = False
                    break
                with path.open(newline="", encoding="utf-8") as handle:
                    loaded[path.name] = list(csv.DictReader(handle))
            if not valid:
                continue
            scope_rows = loaded.get("eight_issuer_reported_scope1.csv", [])
            physical_rows = loaded.get("eight_issuer_physical_exposure_summary.csv", [])
            transmission_rows = loaded.get("eight_issuer_financial_transmission_evidence.csv", [])
            if not all(len(rows) == 8 for rows in (scope_rows, physical_rows, transmission_rows)):
                continue
            candidates.append({
                "is_loaded": True,
                "release_id": manifest.get("release_id", release_dir.name),
                "scope1_rows": scope_rows,
                "physical_rows": physical_rows,
                "transmission_rows": transmission_rows,
                "facility_rows": loaded.get("eight_issuer_epa_facilities_2023.csv", []),
                "hazard_rows": loaded.get("eight_issuer_fema_context_2025.csv", []),
                "processed_sha256": hashes,
                "allowed_use": evidence.get("allowed_use"),
            })
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    if not candidates:
        return {"is_loaded": False, "release_id": None, "scope1_rows": [], "physical_rows": [], "transmission_rows": []}
    return max(candidates, key=lambda row: governed_release_sort_key(row["release_id"]))


def latest_eight_issuer_valuation_inputs(releases_root=None):
    """Load the newest hash-verified observed/assumed valuation input release."""
    releases_root = Path(releases_root) if releases_root else DATA_DIR / "releases"
    candidates = []
    for release_dir in releases_root.glob("CFP-2026-003-R14-*"):
        manifest_path = release_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            hashes = manifest.get("sha256") or {}
            loaded, valid = {}, True
            for relative, expected_hash in hashes.items():
                path = PROJECT_DIR / relative
                if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
                    valid = False
                    break
                if path.suffix == ".csv" and path.parent.name == "processed":
                    with path.open(newline="", encoding="utf-8") as handle:
                        loaded[path.name] = list(csv.DictReader(handle))
            inputs = loaded.get("eight_issuer_valuation_inputs_2025.csv", [])
            assumptions = loaded.get("eight_issuer_model_assumptions.csv", [])
            if not valid or len(inputs) != 8 or len(assumptions) != 24:
                continue
            candidates.append({
                "is_loaded": True,
                "release_id": manifest.get("release_id", release_dir.name),
                "inputs": inputs,
                "assumptions": assumptions,
                "status": manifest.get("status"),
                "valuation_rule": manifest.get("valuation_rule"),
                "source_entries": manifest.get("source_entries") or [],
            })
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    if not candidates:
        return {"is_loaded": False, "release_id": None, "inputs": [], "assumptions": []}
    return max(candidates, key=lambda row: governed_release_sort_key(row["release_id"]))


def latest_eight_issuer_climate_evidence(releases_root=None):
    """Load the newest hash-verified Scope 1/2/3, SEC, FEMA EAL and CIE release."""
    releases_root = Path(releases_root) if releases_root else DATA_DIR / "releases"
    candidates = []
    for release_dir in releases_root.glob("CFP-2026-003-R*-*"):
        manifest_path = release_dir / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            evidence = manifest.get("climate_evidence") or {}
            hashes = manifest.get("sha256") or {}
            if not evidence.get("processed_paths") or not hashes:
                continue
            loaded, valid = {}, True
            for relative in evidence["processed_paths"]:
                expected = hashes.get(relative)
                path = PROJECT_DIR / relative
                if not expected or not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    valid = False
                    break
                with path.open(newline="", encoding="utf-8") as handle:
                    loaded[path.name] = list(csv.DictReader(handle))
            if not valid:
                continue
            scopes = loaded.get("eight_issuer_scope123_2024.csv", [])
            ppe = loaded.get("eight_issuer_sec_ppe_2025.csv", [])
            physical = loaded.get("eight_issuer_fema_eal_summary.csv", [])
            assumptions = loaded.get("eight_issuer_r15_model_assumptions.csv", [])
            if not (len(scopes) == len(ppe) == len(physical) == 8 and len(assumptions) == 24):
                continue
            candidates.append({
                "is_loaded": True,
                "release_id": manifest.get("release_id", release_dir.name),
                "scope_rows": scopes,
                "ppe_rows": ppe,
                "physical_rows": physical,
                "cie_rows": loaded.get("ngfs_cie_usa_labour_productivity_2025_2050.csv", []),
                "assumptions": assumptions,
                "source_entries": manifest.get("source_entries") or [],
            })
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
    if not candidates:
        return {"is_loaded": False, "release_id": None, "scope_rows": [], "ppe_rows": [], "physical_rows": [], "cie_rows": [], "assumptions": []}
    return max(candidates, key=lambda row: governed_release_sort_key(row["release_id"]))


def official_ngfs_transition_pathway(scenario_key, horizon, release=None):
    """Summarize official transition variables without inventing issuer exposure."""
    release = release or latest_official_ngfs_transition()
    horizon = int(horizon)
    if scenario_key == "baseline":
        return {
            "scenario_key": "baseline",
            "scenario": "Climate-agnostic analytical reference",
            "is_official_scenario": False,
            "year": horizon,
            "carbon_price_median": 0.0,
            "carbon_price_min": 0.0,
            "carbon_price_max": 0.0,
            "carbon_price_unit": "US$2010/t CO2",
            "industry_energy": {},
            "status": "analytical zero-carbon-price reference; not an NGFS scenario",
        }
    scenario = NGFS_SCENARIO_LABELS.get(scenario_key)
    if not release.get("is_loaded") or not scenario:
        return {
            "scenario_key": scenario_key,
            "scenario": scenario,
            "is_official_scenario": False,
            "year": horizon,
            "carbon_price_median": None,
            "carbon_price_min": None,
            "carbon_price_max": None,
            "carbon_price_unit": None,
            "industry_energy": {},
            "status": "official NGFS transition pathway not available",
        }
    rows = [
        row for row in release["rows"]
        if row.get("scenario") == scenario and int(safe_float(row.get("year"), 0)) == horizon
    ]
    carbon_rows = [row for row in rows if row.get("variable") == "Price|Carbon"]
    carbon_values = [safe_float(row.get("value"), None) for row in carbon_rows]
    carbon_values = [value for value in carbon_values if value is not None]
    energy = {}
    for variable in (
        "Final Energy|Industry",
        "Final Energy|Industry|Electricity",
        "Final Energy|Industry|Gases",
        "Final Energy|Industry|Liquids",
        "Final Energy|Industry|Solids",
    ):
        values = [
            safe_float(row.get("value"), None)
            for row in rows
            if row.get("variable") == variable
        ]
        values = [value for value in values if value is not None]
        if values:
            energy[variable] = {
                "median": round(statistics.median(values), 6),
                "min": round(min(values), 6),
                "max": round(max(values), 6),
                "unit": next(row.get("unit") for row in rows if row.get("variable") == variable),
                "model_count": len(values),
            }
    return {
        "scenario_key": scenario_key,
        "scenario": scenario,
        "is_official_scenario": bool(carbon_values),
        "year": horizon,
        "carbon_price_median": round(statistics.median(carbon_values), 6) if carbon_values else None,
        "carbon_price_min": round(min(carbon_values), 6) if carbon_values else None,
        "carbon_price_max": round(max(carbon_values), 6) if carbon_values else None,
        "carbon_price_unit": carbon_rows[0].get("unit") if carbon_rows else None,
        "industry_energy": energy,
        "model_count": len(carbon_values),
        "status": (
            f"official NGFS {release['source_release']} transition pathway; "
            "model range is not a probability interval"
            if carbon_values
            else "official release loaded but selected pathway/year is missing"
        ),
        "release_id": release.get("release_id"),
        "source_release": release.get("source_release"),
        "source_release_date": release.get("source_release_date"),
        "source_url": release.get("source_url"),
        "region": release.get("region"),
        "physical_damage_status": release.get("physical_damage_status"),
    }


def annual_ngfs_carbon_price_path(scenario_key, horizon, release=None):
    """Interpolate the official five-year NGFS price grid to annual values."""
    horizon = int(horizon)
    if scenario_key == "baseline":
        return {year: 0.0 for year in range(2025, horizon + 1)}
    points = {}
    for year in (2025, 2030, 2035, 2040, 2045, 2050):
        if year > horizon and points:
            break
        row = official_ngfs_transition_pathway(scenario_key, year, release=release)
        value = safe_float(row.get("carbon_price_median"), None)
        if value is not None:
            points[year] = value
    if not points:
        return {year: 0.0 for year in range(2025, horizon + 1)}
    years = sorted(points)
    path = {}
    for year in range(2025, horizon + 1):
        if year <= years[0]:
            path[year] = points[years[0]]
            continue
        if year >= years[-1]:
            path[year] = points[years[-1]]
            continue
        right = next(item for item in years if item >= year)
        left = max(item for item in years if item <= year)
        if right == left:
            path[year] = points[left]
        else:
            fraction = (year - left) / (right - left)
            path[year] = points[left] + fraction * (points[right] - points[left])
    return path


def issuer_prototype_valuation(
    ticker,
    target_key,
    reference_key,
    horizon,
    assumption_case,
    scope1_row,
    physical_row,
    valuation_release,
    ngfs_release=None,
    climate_evidence=None,
):
    """Calculate an assumption-enabled annual FCFF/DCF scenario comparison.

    Observed inputs and model assumptions are returned separately.  A zero
    cash-flow floor prevents an assumption stress from creating a negative
    enterprise value; Shapley attribution preserves exact reconciliation.
    The returned audit trail exposes target and reference annual costs so the
    client layer never has to infer the calculation from a terminal headline.
    """
    symbol = yahoo_symbol(ticker)
    case = assumption_case if assumption_case in {"low", "base", "high"} else "base"
    input_row = next((row for row in valuation_release.get("inputs", []) if row.get("ticker") == symbol), None)
    assumption = next((row for row in valuation_release.get("assumptions", []) if row.get("ticker") == symbol and row.get("case") == case), None)
    if not input_row or not assumption:
        return {"is_calculable": False, "status": "Valuation input release is incomplete"}

    horizon = int(horizon)
    years = list(range(2026, horizon + 1))
    base_year = 2025
    base_fcff = safe_float(input_row.get("normalized_fcff_usd"), None)
    wacc = safe_float(input_row.get("wacc"), None)
    growth = safe_float(input_row.get("terminal_growth"), None)
    climate_evidence = climate_evidence or {}
    enhanced_scope = next((row for row in climate_evidence.get("scope_rows", []) if row.get("ticker") == symbol), {})
    enhanced_physical = next((row for row in climate_evidence.get("physical_rows", []) if row.get("ticker") == symbol), {})
    enhanced_ppe = next((row for row in climate_evidence.get("ppe_rows", []) if row.get("ticker") == symbol), {})
    enhanced_assumption = next((row for row in climate_evidence.get("assumptions", []) if row.get("ticker") == symbol and row.get("case") == case), {})
    tonnes = safe_float(enhanced_scope.get("scope1_tco2e"), safe_float(scope1_row.get("scope1_tco2e"), None))
    scope2_tonnes = safe_float(enhanced_scope.get("scope2_market_tco2e"), 0.0)
    scope3_tonnes = safe_float(enhanced_scope.get("scope3_tco2e"), 0.0)
    if base_fcff is None or base_fcff <= 0 or wacc is None or growth is None or wacc <= growth or tonnes is None:
        return {"is_calculable": False, "status": "Positive normalized FCFF, emissions, or valid WACC/g is missing"}

    target_price = annual_ngfs_carbon_price_path(target_key, horizon, release=ngfs_release)
    reference_price = annual_ngfs_carbon_price_path(reference_key, horizon, release=ngfs_release)
    coverage = safe_float(enhanced_assumption.get("scope1_policy_coverage"), safe_float(assumption.get("policy_coverage"), 0.75))
    pass_through = safe_float(enhanced_assumption.get("direct_cost_pass_through"), safe_float(assumption.get("pass_through"), 0.50))
    scope2_incidence = safe_float(enhanced_assumption.get("scope2_cost_incidence"), 0.50)
    scope3_incidence = safe_float(enhanced_assumption.get("scope3_value_chain_incidence"), 0.01)
    emissions_decline = safe_float(enhanced_assumption.get("annual_emissions_decline"), safe_float(assumption.get("annual_emissions_decline"), 0.03))
    covered_ppe_share = safe_float(enhanced_assumption.get("covered_ppe_share"), 0.30)
    recovery = safe_float(enhanced_assumption.get("insurance_adaptation_recovery"), 0.50)
    labour_share = safe_float(enhanced_assumption.get("labour_cost_share"), 0.10)
    labour_conversion = safe_float(enhanced_assumption.get("labour_productivity_to_fcff"), 0.25)
    macro_elasticity = safe_float(enhanced_assumption.get("macro_cashflow_elasticity"), safe_float(assumption.get("macro_cashflow_elasticity"), 0.60))
    net_ppe = safe_float(enhanced_ppe.get("net_ppe_usd"), None)
    operating_cash_flow = safe_float(input_row.get("operating_cash_flow_usd"), None)
    capital_expenditure = safe_float(input_row.get("capital_expenditure_usd"), None)
    capex_to_cfo = (
        capital_expenditure / operating_cash_flow
        if operating_cash_flow not in (None, 0.0) and capital_expenditure is not None
        else None
    )
    macro_dependency_scale = clamp(0.50 + safe_float(capex_to_cfo, 0.50), 0.50, 2.00)
    eal_rate = safe_float(enhanced_physical.get("emissions_weighted_building_eal_rate"), None)
    eal_source = "Issuer EPA facilities × FEMA county building EAL rate"
    facility_count = int(safe_float(enhanced_physical.get("facility_count"), 0))
    fema_matches = int(safe_float(enhanced_physical.get("fema_eal_matches"), 0))
    facility_match_coverage = fema_matches / facility_count if facility_count else 0.0
    physical_proxy_used = False
    if eal_rate is None:
        observed_eal = [
            safe_float(row.get("emissions_weighted_building_eal_rate"), None)
            for row in climate_evidence.get("physical_rows", [])
        ]
        observed_eal = sorted(value for value in observed_eal if value is not None)
        if observed_eal:
            middle = len(observed_eal) // 2
            eal_rate = observed_eal[middle] if len(observed_eal) % 2 else (observed_eal[middle - 1] + observed_eal[middle]) / 2.0
            eal_source = "Eight-issuer observed FEMA EAL median fallback"
            physical_proxy_used = True

    cie_by_scenario = {}
    for row in climate_evidence.get("cie_rows", []):
        cie_by_scenario.setdefault(row.get("scenario_key"), {})[int(safe_float(row.get("year"), 0))] = safe_float(row.get("median_loss_pct"), 0.0) / 100.0

    def cie_path(scenario_key):
        if scenario_key == "baseline":
            return {year: 0.0 for year in years}
        source = cie_by_scenario.get(scenario_key) or cie_by_scenario.get("current_policies") or {}
        points = sorted(source)
        if not points:
            return {year: 0.0 for year in years}
        path = {}
        for year in years:
            if year <= points[0]:
                path[year] = source[points[0]]
            elif year >= points[-1]:
                path[year] = source[points[-1]]
            else:
                right = next(point for point in points if point >= year)
                left = max(point for point in points if point <= year)
                fraction = 0.0 if right == left else (year - left) / (right - left)
                path[year] = source[left] + fraction * (source[right] - source[left])
        return path

    acute_factor = {
        "baseline": 0.00, "net_zero_2050": 0.60, "below_2c": 0.70,
        "delayed_transition": 0.85, "current_policies": 1.00,
        "fragmented_world": 1.15,
    }

    target_scenario = CLIMATE_SCENARIO_PATHS.get(target_key, CLIMATE_SCENARIO_PATHS["current_policies"])
    reference_scenario = CLIMATE_SCENARIO_PATHS.get(reference_key, CLIMATE_SCENARIO_PATHS["baseline"])

    def absolute_components(scenario_key, scenario, price_path):
        macro_terminal = (
            safe_float(scenario.get("country_gdp_loss_2050"), 0.0)
            + safe_float(scenario.get("supply_chain_shock_2050"), 0.0)
        )
        components = {"transition": {}, "physical": {}, "macro_supply": {}}
        detail = {
            "scope1": {}, "scope2": {}, "scope3": {},
            "scope1_gross": {}, "scope2_gross": {}, "scope3_gross": {},
            "acute": {}, "chronic": {},
        }
        chronic_path = cie_path(scenario_key)
        for year in years:
            elapsed = year - base_year
            ramp = elapsed / max(1, horizon - base_year)
            baseline = base_fcff * ((1.0 + growth) ** elapsed)
            decline = (1.0 - emissions_decline) ** elapsed
            carbon_price = safe_float(price_path.get(year), 0.0)
            # Gross costs include coverage/incidence but exclude pass-through.
            # Net costs apply pass-through exactly once; no later stage deducts
            # pass-through again.
            detail["scope1_gross"][year] = max(0.0, tonnes * decline * carbon_price * coverage)
            detail["scope2_gross"][year] = max(0.0, scope2_tonnes * decline * carbon_price * coverage * scope2_incidence)
            detail["scope3_gross"][year] = max(0.0, scope3_tonnes * decline * carbon_price * scope3_incidence)
            detail["scope1"][year] = detail["scope1_gross"][year] * (1.0 - pass_through)
            detail["scope2"][year] = detail["scope2_gross"][year] * (1.0 - pass_through)
            detail["scope3"][year] = detail["scope3_gross"][year] * (1.0 - pass_through)
            components["transition"][year] = sum(detail[name][year] for name in ("scope1", "scope2", "scope3"))
            detail["acute"][year] = max(
                0.0, (net_ppe or 0.0) * covered_ppe_share * (eal_rate or 0.0)
                * (1.0 - recovery) * acute_factor.get(scenario_key, 1.0) * ramp,
            )
            detail["chronic"][year] = max(
                0.0, baseline * labour_share * labour_conversion * safe_float(chronic_path.get(year), 0.0),
            )
            components["physical"][year] = detail["acute"][year] + detail["chronic"][year]
            components["macro_supply"][year] = max(
                0.0,
                baseline * macro_terminal * macro_elasticity * macro_dependency_scale * ramp,
            )
        components["detail"] = detail
        return components

    target_components = absolute_components(target_key, target_scenario, target_price)
    reference_components = absolute_components(reference_key, reference_scenario, reference_price)
    names = ("transition", "physical", "macro_supply")

    def value_for(coalition):
        cashflows = []
        annual_rows = []
        for year in years:
            elapsed = year - base_year
            baseline = base_fcff * ((1.0 + growth) ** elapsed)
            selected = {
                name: (target_components[name] if name in coalition else reference_components[name])[year]
                for name in names
            }
            losses = sum(selected.values())
            pre_floor = baseline - losses
            applied_cashflow = max(0.0, pre_floor)
            cashflows.append(applied_cashflow)
            annual_rows.append({
                "year": year,
                "baseline_fcff_usd": baseline,
                "transition_pressure_usd": selected["transition"],
                "physical_pressure_usd": selected["physical"],
                "macro_supply_pressure_usd": selected["macro_supply"],
                "gross_scenario_fcff_usd": pre_floor,
                "scenario_fcff_usd": applied_cashflow,
                "cash_flow_floor_usd": max(0.0, -pre_floor),
                "discount_factor": 1.0 / ((1.0 + wacc) ** (year - base_year)),
            })
        pv = sum(cashflow / ((1.0 + wacc) ** (index + 1)) for index, cashflow in enumerate(cashflows))
        terminal = cashflows[-1] * (1.0 + growth) / (wacc - growth)
        terminal_pv = terminal / ((1.0 + wacc) ** len(years))
        return pv + terminal_pv, cashflows, annual_rows, pv, terminal, terminal_pv

    coalition_values = {}
    for mask in range(1 << len(names)):
        coalition = frozenset(names[index] for index in range(len(names)) if mask & (1 << index))
        coalition_values[coalition] = value_for(coalition)[0]
    reference_value = coalition_values[frozenset()]
    target_result = value_for(frozenset(names))
    reference_result = value_for(frozenset())
    target_value, target_cashflows, target_annual, target_forecast_pv, target_terminal_value, target_terminal_pv = target_result
    _, reference_cashflows, reference_annual, reference_forecast_pv, reference_terminal_value, reference_terminal_pv = reference_result
    shapley = {}
    n = len(names)
    for name in names:
        others = [item for item in names if item != name]
        contribution = 0.0
        for mask in range(1 << len(others)):
            coalition = frozenset(others[index] for index in range(len(others)) if mask & (1 << index))
            weight = math.factorial(len(coalition)) * math.factorial(n - len(coalition) - 1) / math.factorial(n)
            contribution += weight * (coalition_values[coalition | {name}] - coalition_values[coalition])
        shapley[name] = contribution / reference_value

    value_impact = target_value / reference_value - 1.0
    symmetric_value_difference = (
        2.0 * (target_value - reference_value) / (abs(target_value) + abs(reference_value))
        if abs(target_value) + abs(reference_value) > 0.0 else None
    )
    ev_ratio = target_value / reference_value if reference_value else None
    denominator_sensitive = ev_ratio is None or ev_ratio >= 4.0 or ev_ratio <= 0.25
    total_unapplied_cost = sum(row["cash_flow_floor_usd"] for row in target_annual)
    terminal_fcff_clipped = target_annual[-1]["cash_flow_floor_usd"] > 0.0
    last_year = years[-1]
    channel_rows = []
    for name, label in (("transition", "Transition"), ("physical", "Physical"), ("macro_supply", "Macro / supply")):
        amount = target_components[name][last_year] - reference_components[name][last_year]
        channel_rows.append({
            "key": name,
            "label": label,
            "terminal_cash_flow_delta_usd": amount,
            "terminal_cash_flow_delta_rate": amount / (base_fcff * ((1.0 + growth) ** (last_year - base_year))),
            "value_contribution": shapley[name],
            "classification": "Modeled estimate using observed inputs + disclosed assumptions",
        })

    observed = {
        "normalized_fcff_usd": base_fcff,
        "fcff_status": input_row.get("fcff_status"),
        "fcff_accounting_class": (
            "Prototype demonstration assumption - not issuer-observed"
            if "Model assumption" in str(input_row.get("fcff_status") or "")
            else "Internally calculated unlevered-FCFF approximation from SEC CFO, CapEx, interest, and tax inputs"
        ),
        "reported_free_cash_flow_usd": safe_float(input_row.get("reported_free_cash_flow_usd"), None),
        "scope1_tco2e": tonnes,
        "scope2_tco2e": scope2_tonnes,
        "scope3_tco2e": scope3_tonnes,
        "scope3_boundary": enhanced_scope.get("scope3_boundary"),
        "scope1_year": int(safe_float(enhanced_scope.get("reporting_year"), safe_float(scope1_row.get("reporting_year"), 0))),
        "net_ppe_usd": net_ppe,
        "operating_cash_flow_usd": operating_cash_flow,
        "capital_expenditure_usd": capital_expenditure,
        "capex_to_operating_cash_flow": capex_to_cfo,
        "ppe_period_end": enhanced_ppe.get("ppe_period_end"),
        "fema_building_eal_rate": eal_rate,
        "fema_eal_source": eal_source,
        "fema_facility_count": facility_count,
        "fema_matches": fema_matches,
        "fema_match_coverage": facility_match_coverage,
        "cie_terminal_labour_loss_target": cie_path(target_key).get(last_year, 0.0),
        "cie_terminal_labour_loss_reference": cie_path(reference_key).get(last_year, 0.0),
        "beta": safe_float(input_row.get("five_year_monthly_beta"), None),
        "beta_observations": int(safe_float(input_row.get("beta_observations"), 0)),
        "market_cap_usd": safe_float(input_row.get("market_cap_usd"), None),
        "debt_usd": safe_float(input_row.get("debt_usd"), None),
        "tax_rate": safe_float(input_row.get("effective_tax_rate"), None),
        "risk_free_rate": safe_float(input_row.get("risk_free_rate"), None),
        "risk_free_as_of": input_row.get("risk_free_as_of"),
        "wacc": wacc,
    }
    assumption_label = "Prototype demonstration assumption - not issuer-observed"
    assumptions = {
        "case": case,
        "policy_coverage": coverage,
        "pass_through": pass_through,
        "scope2_cost_incidence": scope2_incidence,
        "scope3_value_chain_incidence": scope3_incidence,
        "annual_emissions_decline": emissions_decline,
        "covered_ppe_share": covered_ppe_share,
        "insurance_adaptation_recovery": recovery,
        "labour_cost_share": labour_share,
        "labour_productivity_to_fcff": labour_conversion,
        "acute_scenario_factor": acute_factor.get(target_key, 1.0),
        "macro_cashflow_elasticity": macro_elasticity,
        "macro_dependency_scale": macro_dependency_scale,
        "macro_dependency_rule": "0.50 + SEC CapEx / CFO, bounded to [0.50, 2.00]",
        "equity_risk_premium": safe_float(input_row.get("equity_risk_premium"), None),
        "terminal_growth": growth,
        "cash_flow_floor": "zero",
        "assumption_classification": assumption_label,
        "field_classifications": {
            key: assumption_label for key in (
                "policy_coverage", "pass_through", "scope2_cost_incidence",
                "scope3_value_chain_incidence", "annual_emissions_decline",
                "covered_ppe_share", "insurance_adaptation_recovery",
                "labour_cost_share", "labour_productivity_to_fcff",
                "acute_scenario_factor", "macro_cashflow_elasticity",
                "macro_dependency_scale", "equity_risk_premium",
                "terminal_growth", "forecast_growth_rule", "cash_flow_floor",
            )
        },
        "forecast_growth_rule": "Terminal-growth assumption also used as the annual reference-FCFF growth path through the selected horizon",
    }
    terminal_detail = {
        key: target_components["detail"][key][last_year] - reference_components["detail"][key][last_year]
        for key in ("scope1", "scope2", "scope3", "acute", "chronic")
    }
    transition_audit = []
    annual_calculation = []
    for target_row, reference_row in zip(target_annual, reference_annual):
        year = target_row["year"]
        target_gross = sum(target_components["detail"][key][year] for key in ("scope1_gross", "scope2_gross", "scope3_gross"))
        reference_gross = sum(reference_components["detail"][key][year] for key in ("scope1_gross", "scope2_gross", "scope3_gross"))
        target_net = target_components["transition"][year]
        reference_net = reference_components["transition"][year]
        transition_audit.append({
            "year": year,
            "target_gross_cost_usd": target_gross,
            "reference_gross_cost_usd": reference_gross,
            "target_net_cost_usd": target_net,
            "reference_net_cost_usd": reference_net,
            "net_transition_pressure_usd": target_net - reference_net,
            "pass_through_application_count": 1,
        })
        annual_calculation.append({
            "year": year,
            "reference_baseline_fcff_usd": reference_row["baseline_fcff_usd"],
            "target_transition_pressure_usd": target_components["transition"][year] - reference_components["transition"][year],
            "target_physical_pressure_usd": target_components["physical"][year] - reference_components["physical"][year],
            "target_macro_supply_pressure_usd": target_components["macro_supply"][year] - reference_components["macro_supply"][year],
            "reference_scenario_fcff_usd": reference_row["scenario_fcff_usd"],
            "target_gross_scenario_fcff_usd": target_row["gross_scenario_fcff_usd"],
            "target_scenario_fcff_usd": target_row["scenario_fcff_usd"],
            "unapplied_cost_due_to_floor_usd": target_row["cash_flow_floor_usd"],
            "discount_factor": target_row["discount_factor"],
            "target_present_value_usd": target_row["scenario_fcff_usd"] * target_row["discount_factor"],
            "reference_present_value_usd": reference_row["scenario_fcff_usd"] * reference_row["discount_factor"],
        })
    if terminal_fcff_clipped or total_unapplied_cost > 0.0 or denominator_sensitive or physical_proxy_used:
        ranking_status = "EXCLUDE"
    elif facility_match_coverage < 0.75:
        ranking_status = "CAUTION"
    else:
        ranking_status = "RANKABLE"
    return {
        "is_calculable": True,
        "release_id": climate_evidence.get("release_id") or valuation_release.get("release_id"),
        "assumption_case": case,
        "value_impact": value_impact,
        "symmetric_value_difference": symmetric_value_difference,
        "enterprise_value_delta_usd": target_value - reference_value,
        "enterprise_value_ratio": ev_ratio,
        "reference_enterprise_value_usd": reference_value,
        "target_enterprise_value_usd": target_value,
        "reference_terminal_fcff_usd": reference_cashflows[-1],
        "target_terminal_fcff_usd": target_cashflows[-1],
        "terminal_fcff_delta_usd": target_cashflows[-1] - reference_cashflows[-1],
        "annual_calculation": annual_calculation,
        "transition_audit": transition_audit,
        "valuation_audit": {
            "reference_forecast_fcff_pv_usd": reference_forecast_pv,
            "target_forecast_fcff_pv_usd": target_forecast_pv,
            "reference_terminal_value_usd": reference_terminal_value,
            "target_terminal_value_usd": target_terminal_value,
            "reference_terminal_value_pv_usd": reference_terminal_pv,
            "target_terminal_value_pv_usd": target_terminal_pv,
            "terminal_fcff_clipped": terminal_fcff_clipped,
            "total_unapplied_cost_usd": total_unapplied_cost,
            "denominator_sensitive": denominator_sensitive,
            "physical_proxy_used": physical_proxy_used,
            "ranking_status": ranking_status,
        },
        "driver_registry": {
            "transition": "Scope 1/2/3 emissions-price cost only; pass-through applied once",
            "physical": "acute asset damage plus chronic labour-productivity conversion",
            "macro_supply": "GDP and supply-chain shock only; excludes carbon-price cost and physical damage",
            "double_counting_rule": "Each active driver belongs to exactly one pillar in this implementation",
        },
        "equity_bridge": {
            "is_calculable": False,
            "equity_value_usd": None,
            "per_share_value_impact": None,
            "reason_codes": ["MISSING_GOVERNED_CASH_AND_NET_DEBT_BRIDGE", "MISSING_OTHER_CLAIMS_AND_NON_OPERATING_ASSETS", "MISSING_DILUTED_SHARE_COUNT"],
        },
        "channels": channel_rows,
        "terminal_component_detail": terminal_detail,
        "attribution_residual": value_impact - sum(shapley.values()),
        "observed_inputs": observed,
        "model_assumptions": assumptions,
        "wacc": wacc,
        "terminal_growth": growth,
        "status": f"Prototype enterprise-value sensitivity completed; ranking status {ranking_status}. Issuer facility exposure is {'represented by a prototype fallback' if physical_proxy_used else 'coverage-qualified'}. All non-observed conversions are prototype demonstration assumptions, not issuer-observed inputs. No equity-value bridge, share-price impact, automatic trade, audited valuation, forecast return, or probability.",
    }


def valuation_assumptions(ticker, sector, observed_beta=None):
    symbol = yahoo_symbol(ticker or "")
    if sector == "Economy":
        sector = "Industrials"
        quality = "Country valuation calibration"
    else:
        sector = normalize_model_sector(sector)
        quality = "Observed market beta + sector capital-structure fallback" if observed_beta is not None else "Sector beta and capital-structure fallback"
    fallback = SECTOR_VALUATION_ASSUMPTIONS[sector]
    treasury = latest_official_treasury_rate("10y")
    risk_free_rate = safe_float(treasury.get("rate"), RISK_FREE_RATE)
    beta = clamp(safe_float(observed_beta, fallback["equity_beta"]), 0.35, 2.25)
    debt_ratio = clamp(safe_float(fallback.get("debt_ratio"), 0.30), 0.0, 0.75)
    cost_of_equity = risk_free_rate + beta * EQUITY_RISK_PREMIUM
    after_tax_debt = PRETAX_COST_OF_DEBT * (1 - US_CORPORATE_TAX_RATE)
    wacc = (1 - debt_ratio) * cost_of_equity + debt_ratio * after_tax_debt
    terminal_growth = clamp(safe_float(fallback.get("terminal_growth"), 0.021), -0.01, wacc - 0.015)
    financial_issuer_proxy = (
        sector == "Financials"
        and symbol not in SECTOR_ETFS
        and symbol not in {"SECTOR", "US"}
    )
    return {
        "ticker": symbol,
        "equity_beta": round(beta, 4),
        "risk_free_rate": round(risk_free_rate, 6),
        "risk_free_source": treasury.get("source_class"),
        "risk_free_as_of": treasury.get("as_of"),
        "risk_free_release_id": treasury.get("release_id"),
        "debt_ratio": round(debt_ratio, 4),
        "cost_of_equity": round(cost_of_equity, 4),
        "after_tax_cost_of_debt": round(after_tax_debt, 4),
        "wacc": round(wacc, 4),
        "terminal_growth": round(terminal_growth, 4),
        "quality": f"{quality}; Treasury rate {'loaded' if treasury.get('rate') is not None else 'fallback assumption'}",
        "formula": "WACC = E/V x (risk-free + beta x ERP) + D/V x pre-tax debt cost x (1-tax)",
        "decision_suitable": not financial_issuer_proxy,
        "issuer_point_estimate_allowed": False,
        "applicability_status": (
            "research-only blocker — generic FCFF/WACC is not decision-suitable for a financial institution; use an approved equity/residual-income method"
            if financial_issuer_proxy
            else "research calibration — official Treasury rate does not complete issuer WACC"
        ),
    }


MACRO_DCF_COMPONENTS = (
    "country_gdp",
    "supply_chain",
)

TRANSITION_DCF_COMPONENTS = (
    "sector_demand",
    "carbon_cost",
    "energy_cost",
    "transition_capex",
    "pass_through_offset",
)

DCF_COMPONENTS = (
    ("acute_physical", "chronic_physical")
    + MACRO_DCF_COMPONENTS
    + TRANSITION_DCF_COMPONENTS
)


def transition_cash_flow_channels(scenario, sector, horizon_fraction=1.0):
    """Translate a scenario into signed terminal FCFF transition channels.

    Positive values reduce FCFF. The pass-through offset is negative because it
    mitigates carbon and energy costs. Inputs are explicit scenario/sector
    calibrations until official issuer-level sources are loaded.
    """
    if sector == "Economy":
        channel = {
            "carbon_intensity": 0.50,
            "demand_elasticity": 0.50,
            "energy_intensity": 0.50,
            "capex_intensity": 0.50,
            "pass_through": 0.50,
        }
    else:
        sector = normalize_model_sector(sector)
        channel = SECTOR_TRANSITION_CHANNELS[sector]

    carbon_cost = (
        safe_float(scenario.get("carbon_cost_shock_2050"), 0.0)
        * safe_float(channel.get("carbon_intensity"), 0.50)
        * 0.35
        * horizon_fraction
    )
    sector_demand = (
        safe_float(scenario.get("transition_demand_shock_2050"), 0.0)
        * safe_float(channel.get("demand_elasticity"), 0.0)
        * horizon_fraction
    )
    energy_cost = (
        safe_float(scenario.get("energy_cost_shock_2050"), 0.0)
        * safe_float(channel.get("energy_intensity"), 0.50)
        * 0.30
        * horizon_fraction
    )
    transition_capex = (
        safe_float(scenario.get("transition_capex_shock_2050"), 0.0)
        * safe_float(channel.get("capex_intensity"), 0.50)
        * 0.45
        * horizon_fraction
    )
    pass_through_offset = -(
        carbon_cost + energy_cost
    ) * safe_float(channel.get("pass_through"), 0.50)
    return {
        "carbon_cost": carbon_cost,
        "sector_demand": sector_demand,
        "demand_shift": sector_demand,
        "energy_cost": energy_cost,
        "transition_capex": transition_capex,
        "pass_through_offset": pass_through_offset,
        "gross_cost_before_pass_through": carbon_cost + energy_cost,
        "sector_inputs": dict(channel),
        "data_status": "Transparent sector calibration; official NGFS and SEC history loaded, but emissions, energy quantities, and accounting tie-out remain pending",
    }


def macro_revenue_transmission(scenario, sector, vulnerability, horizon_fraction=1.0):
    """Map country GDP and indirect supply shocks into issuer revenue loss."""
    if sector == "Economy":
        gdp_beta = supply_beta = issuer_beta = 1.0
        status = "Country scenario input"
    else:
        sector = normalize_model_sector(sector)
        transmission = SECTOR_MACRO_TRANSMISSION[sector]
        gdp_beta = safe_float(transmission.get("gdp_beta"), 1.0)
        supply_beta = safe_float(transmission.get("supply_beta"), 1.0)
        issuer_beta = clamp(safe_float(vulnerability.get("macro_beta"), 1.0), 0.50, 1.50)
        status = "BEA-style sector beta + issuer earnings-beta fallback; revenue geography and supplier links not loaded"
    country_gdp = (
        safe_float(scenario.get("country_gdp_loss_2050", scenario.get("macro_transition_loss_2050", 0.0)), 0.0)
        * gdp_beta
        * issuer_beta
        * horizon_fraction
    )
    supply_chain = (
        safe_float(scenario.get("supply_chain_shock_2050"), 0.0)
        * supply_beta
        * horizon_fraction
    )
    return {
        "country_gdp": country_gdp,
        "supply_chain": supply_chain,
        "gdp_beta": gdp_beta,
        "supply_beta": supply_beta,
        "issuer_beta": issuer_beta,
        "revenue_geography_share": 1.0,
        "status": status,
    }


def structural_transition_pressure(sector):
    """Sector fallback when issuer-level transition cash-flow data is absent."""
    sector = normalize_model_sector(sector)
    if sector == "Economy":
        weights = normalized_sector_value_added_weights()
        sector_rows = [(weight, structural_transition_pressure(name)) for name, weight in weights.items()]
        return {
            key: round(sum(weight * safe_float(row.get(key), 0.0) for weight, row in sector_rows), 4)
            for key in ("risk", "carbon_cost", "demand_shift", "energy_cost", "transition_capex", "pass_through_offset")
        } | {"status": "Value-added-weighted economy transition calibration; issuer climate translation not tied out"}
    channel = SECTOR_TRANSITION_CHANNELS[sector]
    carbon_cost = 0.30 * safe_float(channel.get("carbon_intensity"), 0.50)
    demand_shift = 0.25 * safe_float(channel.get("demand_elasticity"), 0.0)
    energy_cost = 0.20 * safe_float(channel.get("energy_intensity"), 0.50)
    transition_capex = 0.25 * safe_float(channel.get("capex_intensity"), 0.50)
    pass_through_offset = -0.30 * (carbon_cost + energy_cost) * safe_float(channel.get("pass_through"), 0.50)
    net_pressure = clamp(
        carbon_cost + demand_shift + energy_cost + transition_capex + pass_through_offset,
        0.02,
        0.98,
    )
    return {
        "risk": round(net_pressure, 4),
        "carbon_cost": round(carbon_cost, 4),
        "demand_shift": round(demand_shift, 4),
        "energy_cost": round(energy_cost, 4),
        "transition_capex": round(transition_capex, 4),
        "pass_through_offset": round(pass_through_offset, 4),
        "status": "Sector cash-flow calibration; NGFS and SEC history are loaded, but EIA/EPA quantities and issuer accounting tie-out are pending",
    }


def canonical_model_sector(sector):
    if sector is None or not str(sector).strip():
        return None
    sector = str(sector).strip()
    aliases = {
        "Financial": "Financials",
        "Finance": "Financials",
        "Financial Services": "Financials",
        "Materials": "Basic Materials",
        "Consumer Discretionary": "Consumer Cyclical",
        "Consumer Staples": "Consumer Defensive",
        "Health Care": "Healthcare",
        "Communications": "Communication Services",
        "Broad market": "Economy",
        "Broad Market": "Economy",
        "Growth / Technology": "Technology",
        "Climate / Clean Energy": "Utilities",
        "Rates / Credit": "Financials",
        "Commodities": "Basic Materials",
        "Energy commodity": "Energy",
    }
    sector = aliases.get(sector, sector)
    if sector == "Economy":
        return sector
    if sector not in SECTOR_DOWNSCALING_FACTORS:
        return None
    return sector


def normalize_model_sector(sector):
    return canonical_model_sector(sector) or "Technology"


def load_issuer_sector_master():
    global ISSUER_SECTOR_MASTER_CACHE
    with ISSUER_SECTOR_MASTER_LOCK:
        if ISSUER_SECTOR_MASTER_CACHE is not None:
            return ISSUER_SECTOR_MASTER_CACHE
        rows = {}
        if ISSUER_SECTOR_MASTER_PATH.exists():
            try:
                with ISSUER_SECTOR_MASTER_PATH.open(newline="", encoding="utf-8") as handle:
                    for row in csv.DictReader(handle):
                        ticker = yahoo_symbol(row.get("ticker") or "")
                        sector = canonical_model_sector(row.get("sector_canonical"))
                        if (
                            ticker
                            and sector
                            and row.get("mapping_status") == "eligible_equity_reference"
                        ):
                            rows[ticker] = dict(row)
            except Exception:
                rows = {}
        ISSUER_SECTOR_MASTER_CACHE = rows
        return ISSUER_SECTOR_MASTER_CACHE


def listed_equity_sector_metadata(ticker):
    symbol = yahoo_symbol(ticker or "")
    retrieved_at = datetime.now().strftime("%Y-%m-%d")
    source = MARKET_SECTOR_METADATA_SOURCE
    if not symbol or len(symbol) > 12 or any(not (char.isalnum() or char in ".-") for char in symbol):
        return {
            "is_resolved": False,
            "reason": "invalid ticker syntax",
            "source": source,
            "as_of": retrieved_at,
        }
    with MARKET_SECTOR_METADATA_LOCK:
        cached = MARKET_SECTOR_METADATA_CACHE.get(symbol)
    if cached:
        return dict(cached)
    if yf is None:
        return {
            "is_resolved": False,
            "reason": "market metadata provider unavailable",
            "source": source,
            "as_of": retrieved_at,
        }
    try:
        info = yf.Ticker(symbol).get_info() or {}
    except Exception as exc:
        return {
            "is_resolved": False,
            "reason": f"market metadata request failed ({type(exc).__name__})",
            "source": source,
            "as_of": retrieved_at,
        }
    quote_type = str(info.get("quoteType") or "").upper()
    if quote_type != "EQUITY":
        return {
            "is_resolved": False,
            "reason": f"quote type {quote_type or 'unknown'} is not an eligible listed equity",
            "quote_type": quote_type or None,
            "source": source,
            "as_of": retrieved_at,
        }
    raw_sector = info.get("sector")
    resolved_sector = canonical_model_sector(raw_sector)
    if resolved_sector is None or resolved_sector == "Economy":
        return {
            "is_resolved": False,
            "reason": f"unsupported or missing market sector {raw_sector or 'unknown'}",
            "quote_type": quote_type,
            "source": source,
            "as_of": retrieved_at,
        }
    result = {
        "is_resolved": True,
        "ticker": symbol,
        "resolved_sector": resolved_sector,
        "raw_sector": raw_sector,
        "issuer_name": info.get("shortName") or info.get("longName") or symbol,
        "exchange": info.get("exchange") or info.get("fullExchangeName"),
        "industry": info.get("industry"),
        "quote_type": quote_type,
        "source": source,
        "as_of": retrieved_at,
    }
    with MARKET_SECTOR_METADATA_LOCK:
        MARKET_SECTOR_METADATA_CACHE[symbol] = dict(result)
    return result


def resolve_issuer_sector(ticker, requested_sector=None):
    symbol = yahoo_symbol(ticker or "")
    requested = canonical_model_sector(requested_sector)
    resolved = ISSUER_SECTOR_CROSSWALK.get(symbol)
    if resolved is None:
        master_row = load_issuer_sector_master().get(symbol)
        if master_row:
            resolved = canonical_model_sector(master_row.get("sector_canonical"))
            conflict = requested is not None and requested != resolved
            return {
                "ticker": symbol,
                "requested_sector": requested,
                "resolved_sector": resolved,
                "is_calculable": True,
                "has_conflict": conflict,
                "status": (
                    f"local issuer-sector master applied — requested {requested} overridden by {resolved}"
                    if conflict
                    else f"local issuer-sector master applied — {resolved}"
                ),
                "mapping_tier": "local SEC/Nasdaq issuer-sector master",
                "issuer_name": master_row.get("company_name"),
                "exchange": master_row.get("exchange"),
                "industry": master_row.get("industry"),
                "quote_type": master_row.get("quote_type"),
                "cik": master_row.get("cik"),
                "country": master_row.get("country"),
                "source": "Local issuer-sector master; Nasdaq sector/industry joined to SEC ticker/CIK/exchange where matched",
                "as_of": master_row.get("as_of"),
            }
        metadata = listed_equity_sector_metadata(symbol)
        if metadata.get("is_resolved"):
            resolved = metadata["resolved_sector"]
            conflict = requested is not None and requested != resolved
            return {
                "ticker": symbol,
                "requested_sector": requested,
                "resolved_sector": resolved,
                "is_calculable": True,
                "has_conflict": conflict,
                "status": (
                    f"listed-equity market mapping applied — requested {requested} overridden by {resolved}"
                    if conflict
                    else f"listed-equity market mapping applied — {resolved}"
                ),
                "mapping_tier": "on-demand listed-equity metadata",
                "issuer_name": metadata.get("issuer_name"),
                "exchange": metadata.get("exchange"),
                "industry": metadata.get("industry"),
                "quote_type": metadata.get("quote_type"),
                "source": metadata["source"],
                "as_of": metadata["as_of"],
            }
        return {
            "ticker": symbol,
            "requested_sector": requested,
            "resolved_sector": None,
            "is_calculable": False,
            "has_conflict": False,
            "status": f"not calculable — {metadata.get('reason', 'issuer sector is not verified')}",
            "mapping_tier": "on-demand listed-equity metadata",
            "issuer_name": None,
            "exchange": None,
            "industry": None,
            "quote_type": metadata.get("quote_type"),
            "source": metadata.get("source", MARKET_SECTOR_METADATA_SOURCE),
            "as_of": metadata.get("as_of", datetime.now().strftime("%Y-%m-%d")),
        }
    conflict = requested is not None and requested != resolved
    return {
        "ticker": symbol,
        "requested_sector": requested,
        "resolved_sector": resolved,
        "is_calculable": True,
        "has_conflict": conflict,
        "mapping_tier": "controlled research crosswalk",
        "issuer_name": None,
        "exchange": None,
        "industry": None,
        "quote_type": "EQUITY",
        "status": (
            f"controlled mapping applied — requested {requested} overridden by {resolved}"
            if conflict
            else f"controlled mapping applied — {resolved}"
        ),
        "source": ISSUER_SECTOR_CROSSWALK_SOURCE,
        "as_of": ISSUER_SECTOR_CROSSWALK_AS_OF,
    }


def normalized_sector_value_added_weights():
    total = sum(max(0.0, safe_float(weight, 0.0)) for weight in SECTOR_VALUE_ADDED_WEIGHTS.values()) or 1.0
    return {sector: max(0.0, safe_float(weight, 0.0)) / total for sector, weight in SECTOR_VALUE_ADDED_WEIGHTS.items()}


def sector_vulnerability_multiplier(sector, risk_type):
    sector = normalize_model_sector(sector)
    factor_key = "fixed_asset" if risk_type == "acute" else "labor"
    weights = normalized_sector_value_added_weights()
    average_vulnerability = sum(
        weight * safe_float(SECTOR_DOWNSCALING_FACTORS[name].get(factor_key), 0.0)
        for name, weight in weights.items()
    )
    sector_vulnerability = safe_float(SECTOR_DOWNSCALING_FACTORS[sector].get(factor_key), average_vulnerability)
    return sector_vulnerability / max(average_vulnerability, 1e-12)


def physical_downscaling_reconciliation():
    weights = normalized_sector_value_added_weights()
    acute = sum(weight * sector_vulnerability_multiplier(sector, "acute") for sector, weight in weights.items())
    chronic = sum(weight * sector_vulnerability_multiplier(sector, "chronic") for sector, weight in weights.items())
    return {"acute": acute, "chronic": chronic}


def load_facility_exposure_data():
    if not FACILITY_EXPOSURE_FILE.exists():
        return {}
    try:
        payload = json.loads(FACILITY_EXPOSURE_FILE.read_text(encoding="utf-8"))
        return payload.get("issuers", payload) if isinstance(payload, dict) else {}
    except Exception:
        return {}


def issuer_hazard_exposure_profile(ticker, sector):
    symbol = yahoo_symbol(ticker or "")
    sector = normalize_model_sector(sector)
    facility_data = load_facility_exposure_data().get(symbol, {})
    hazard_data = facility_data.get("hazards", {}) if isinstance(facility_data, dict) else {}
    acute_ratio = safe_float(ISSUER_VULNERABILITY_OVERRIDES.get(symbol, {}).get("acute_ratio"), 1.0)
    resilience_fallback = SECTOR_RESILIENCE_FALLBACK.get(sector, 0.50)
    hazards = {}
    observed_count = 0
    for hazard in HAZARD_CATEGORIES:
        observed = hazard_data.get(hazard, {}) if isinstance(hazard_data, dict) else {}
        if observed:
            observed_count += 1
        exposure = clamp(
            safe_float(observed.get("exposure"), HAZARD_SECTOR_BETAS.get(hazard, {}).get(sector, 0.50)),
            0.0,
            1.50,
        )
        vulnerability = clamp(safe_float(observed.get("vulnerability"), acute_ratio), 0.0, 1.50)
        resilience = clamp(safe_float(observed.get("resilience"), resilience_fallback), 0.0, 0.95)
        hazards[hazard] = {
            "exposure": round(exposure, 4),
            "vulnerability": round(vulnerability, 4),
            "resilience": round(resilience, 4),
        }
    return {
        "ticker": symbol,
        "sector": sector,
        "hazards": hazards,
        "observed_hazards": observed_count,
        "data_quality": (
            f"Facility mapping loaded for {observed_count}/{len(HAZARD_CATEGORIES)} hazards"
            if observed_count
            else "Sector hazard fallback; issuer facility geolocation not loaded"
        ),
        "source": facility_data.get("source", "Sector calibration") if isinstance(facility_data, dict) else "Sector calibration",
    }


def physical_event_loss(hazard_intensity, exposure, vulnerability, resilience):
    return clamp(
        safe_float(hazard_intensity, 0.0)
        * safe_float(exposure, 0.0)
        * safe_float(vulnerability, 0.0)
        * (1 - clamp(safe_float(resilience, 0.0), 0.0, 0.95)),
        0.0,
        1.0,
    )


def issuer_vulnerability_profile(ticker, sector):
    symbol = yahoo_symbol(ticker or "AAPL")
    sector = normalize_model_sector(sector)
    # CFP-2026-003 removes unsupported point estimates by ticker. Until a
    # governed issuer exposure record exists, vulnerability remains at the
    # disclosed sector fallback and must not masquerade as issuer evidence.
    acute_ratio = 1.0
    chronic_ratio = 1.0
    quality = (
        "Sector calibration"
        if symbol in {"SECTOR", "US"} or symbol == sector.upper()
        else "Sector research fallback; issuer vulnerability not verified"
    )
    if sector == "Economy":
        weights = normalized_sector_value_added_weights()
        factors = {
            key: sum(weight * safe_float(SECTOR_DOWNSCALING_FACTORS[name].get(key), 0.0) for name, weight in weights.items())
            for key in ("fixed_asset", "labor", "macro_beta")
        }
        quality = "Economy-weighted sector fallback"
    else:
        factors = SECTOR_DOWNSCALING_FACTORS[sector]
    return {
        "acute_ratio": round(clamp(acute_ratio, FIRM_VULNERABILITY_MIN, FIRM_VULNERABILITY_MAX), 4),
        "chronic_ratio": round(clamp(chronic_ratio, FIRM_VULNERABILITY_MIN, FIRM_VULNERABILITY_MAX), 4),
        "fixed_asset_intensity": round(factors["fixed_asset"] * acute_ratio, 4),
        "labor_intensity": round(factors["labor"] * chronic_ratio, 4),
        "macro_beta": round(factors["macro_beta"], 4),
        "quality": quality,
        "issuer_specific": False,
        "evidence_grade": "Proxy-dominant",
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
    sector_resolution = resolve_issuer_sector(ticker, sector) if scope == "issuer" else None
    sector = (
        sector_resolution.get("resolved_sector")
        if sector_resolution and sector_resolution.get("resolved_sector")
        else normalize_model_sector(SECTOR_ETFS.get(yahoo_symbol(ticker), {}).get("name", sector))
    )
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
            "sector_resolution": sector_resolution,
        }
    ]


def scenario_terminal_components(scenario, sector, vulnerability, horizon):
    sector = normalize_model_sector(sector) if sector != "Economy" else "Economy"
    years_to_2050 = max(1, 2050 - CURRENT_YEAR)
    horizon_fraction = clamp((int(horizon) - CURRENT_YEAR) / years_to_2050, 0.04, 1.0)
    if sector == "Economy":
        acute_sector_multiplier = chronic_sector_multiplier = 1.0
        acute_firm_ratio = chronic_firm_ratio = macro_beta = 1.0
    else:
        factors = SECTOR_DOWNSCALING_FACTORS[sector]
        acute_sector_multiplier = sector_vulnerability_multiplier(sector, "acute")
        chronic_sector_multiplier = sector_vulnerability_multiplier(sector, "chronic")
        acute_firm_ratio = clamp(
            safe_float(vulnerability.get("acute_ratio"), 1.0),
            FIRM_VULNERABILITY_MIN,
            FIRM_VULNERABILITY_MAX,
        )
        chronic_firm_ratio = clamp(
            safe_float(vulnerability.get("chronic_ratio"), 1.0),
            FIRM_VULNERABILITY_MIN,
            FIRM_VULNERABILITY_MAX,
        )
        macro_beta = safe_float(vulnerability.get("macro_beta"), factors["macro_beta"])
    transition_channels = transition_cash_flow_channels(scenario, sector, horizon_fraction)
    macro_channels = macro_revenue_transmission(scenario, sector, vulnerability, horizon_fraction)
    category = str(scenario.get("category", "Reference"))
    transition_path_exponent = {
        "Orderly": 0.70,
        "Disorderly": 2.10,
        "Hot House World": 1.20,
        "Too little, too late": 1.55,
        "Reference": 1.00,
    }.get(category, 1.00)
    components = {
        "acute_physical": safe_float(scenario.get("acute_gdp_loss_2050"), 0.0)
        * acute_sector_multiplier
        * acute_firm_ratio
        * horizon_fraction,
        "chronic_physical": safe_float(scenario.get("chronic_gdp_loss_2050"), 0.0)
        * chronic_sector_multiplier
        * chronic_firm_ratio
        * horizon_fraction,
        "country_gdp": safe_float(macro_channels.get("country_gdp"), 0.0),
        "supply_chain": safe_float(macro_channels.get("supply_chain"), 0.0),
        "sector_demand": safe_float(transition_channels.get("sector_demand"), 0.0),
        "acute_sector_multiplier": acute_sector_multiplier,
        "chronic_sector_multiplier": chronic_sector_multiplier,
        "acute_firm_ratio": acute_firm_ratio,
        "chronic_firm_ratio": chronic_firm_ratio,
        "horizon_fraction": horizon_fraction,
    }
    for key in ("carbon_cost", "energy_cost", "transition_capex", "pass_through_offset"):
            components[key] = safe_float(transition_channels.get(key), 0.0)
    components["macro_transition"] = components["country_gdp"] + components["supply_chain"]
    components["demand_shift"] = components["sector_demand"]
    components["micro_transition"] = sum(
        safe_float(components.get(key), 0.0)
        for key in ("sector_demand", "carbon_cost", "energy_cost", "transition_capex", "pass_through_offset")
    )
    components["transition_channel_inputs"] = transition_channels.get("sector_inputs", {})
    components["transition_data_status"] = transition_channels.get("data_status")
    components["macro_channel_inputs"] = macro_channels
    components["path_exponents"] = {
        key: (1.35 if key in {"acute_physical", "chronic_physical"} else transition_path_exponent)
        for key in DCF_COMPONENTS
    }
    return components


def discounted_scenario_value(components, horizon, wacc=0.075, growth=0.025, return_details=False):
    horizon = int(clamp(safe_float(horizon, 2050), CURRENT_YEAR + 1, 2050))
    years = max(1, horizon - CURRENT_YEAR)
    wacc = clamp(safe_float(wacc, 0.075), 0.03, 0.20)
    growth = clamp(safe_float(growth, 0.025), -0.02, wacc - 0.015)
    pv = 0.0
    terminal_cash_flow = 1.0
    for step in range(1, years + 1):
        progress = step / years
        exponents = components.get("path_exponents", {}) or {}
        loss = sum(
            safe_float(components.get(key), 0.0)
            * progress ** clamp(safe_float(exponents.get(key), 1.0), 0.35, 3.0)
            for key in DCF_COMPONENTS
        )
        baseline_cash_flow = (1 + growth) ** step
        terminal_cash_flow = baseline_cash_flow * (1 - clamp(loss, -0.50, 0.80))
        pv += terminal_cash_flow / ((1 + wacc) ** step)
    terminal_physical_loss = max(
        0.0,
        safe_float(components.get("acute_physical"), 0.0) + safe_float(components.get("chronic_physical"), 0.0),
    )
    scenario_growth = clamp(growth - terminal_physical_loss / years, -0.02, wacc - 0.015)
    terminal_value = terminal_cash_flow * (1 + scenario_growth) / max(0.015, wacc - scenario_growth)
    pv += terminal_value / ((1 + wacc) ** years)
    if return_details:
        return {
            "present_value": pv,
            "terminal_cash_flow": terminal_cash_flow,
            "terminal_growth": scenario_growth,
            "wacc": wacc,
            "baseline_growth": growth,
            "years": years,
        }
    return pv


def shapley_value_attribution(reference_components, target_components, horizon, wacc=0.075, growth=0.025):
    keys = DCF_COMPONENTS
    reference_value = discounted_scenario_value(reference_components, horizon, wacc=wacc, growth=growth)
    coalition_cache = {}

    def coalition_value(active_keys):
        cache_key = frozenset(active_keys)
        if cache_key in coalition_cache:
            return coalition_cache[cache_key]
        mixed = dict(reference_components)
        for key in active_keys:
            mixed[key] = target_components[key]
        mixed_exponents = dict(reference_components.get("path_exponents", {}) or {})
        target_exponents = target_components.get("path_exponents", {}) or {}
        for key in active_keys:
            mixed_exponents[key] = target_exponents.get(key, 1.0)
        mixed["path_exponents"] = mixed_exponents
        value = discounted_scenario_value(mixed, horizon, wacc=wacc, growth=growth) / max(reference_value, 1e-12) - 1
        coalition_cache[cache_key] = value
        return value

    contributions = {}
    n = len(keys)
    for key in keys:
        others = [candidate for candidate in keys if candidate != key]
        contribution = 0.0
        for mask in range(1 << len(others)):
            coalition = {others[index] for index in range(len(others)) if mask & (1 << index)}
            size = len(coalition)
            weight = math.factorial(size) * math.factorial(n - size - 1) / math.factorial(n)
            contribution += weight * (coalition_value(coalition | {key}) - coalition_value(coalition))
        contributions[key] = contribution
    return contributions


def scenario_repricing_for_scope(scope_rows, target, reference, horizon):
    component_labels = {
        "acute_physical": "Acute physical",
        "chronic_physical": "Chronic physical",
        "country_gdp": "Country GDP",
        "sector_demand": "Sector demand",
        "supply_chain": "Supply chain",
        "carbon_cost": "Carbon cost",
        "energy_cost": "Energy cost",
        "transition_capex": "Transition CapEx",
        "pass_through_offset": "Cost pass-through",
    }
    aggregate_impact = 0.0
    aggregate_target = {key: 0.0 for key in component_labels}
    aggregate_reference = {key: 0.0 for key in component_labels}
    aggregate_contribution = {key: 0.0 for key in component_labels}
    weighted_target_value = 0.0
    weighted_reference_value = 0.0
    weighted_wacc = 0.0
    weighted_terminal_growth = 0.0
    instrument_rows = []
    for row in scope_rows:
        weight = safe_float(row.get("weight"), 0.0)
        valuation = row.get("valuation") or valuation_assumptions(row.get("ticker"), row.get("sector"))
        wacc = safe_float(valuation.get("wacc"), 0.075)
        growth = safe_float(valuation.get("terminal_growth"), 0.025)
        weighted_wacc += weight * wacc
        weighted_terminal_growth += weight * growth
        target_components = scenario_terminal_components(target, row["sector"], row["vulnerability"], horizon)
        reference_components = scenario_terminal_components(reference, row["sector"], row["vulnerability"], horizon)
        reference_value = discounted_scenario_value(reference_components, horizon, wacc=wacc, growth=growth)
        target_value = discounted_scenario_value(target_components, horizon, wacc=wacc, growth=growth)
        value_impact = target_value / max(reference_value, 1e-9) - 1
        shapley = shapley_value_attribution(reference_components, target_components, horizon, wacc=wacc, growth=growth)
        aggregate_impact += weight * value_impact
        weighted_target_value += weight * target_value
        weighted_reference_value += weight * reference_value
        component_contributions = {}
        for key in component_labels:
            contribution = shapley[key]
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
                "acute_sector_multiplier": round(target_components.get("acute_sector_multiplier", 1.0), 4),
                "chronic_sector_multiplier": round(target_components.get("chronic_sector_multiplier", 1.0), 4),
                "data_quality": row["vulnerability"].get("quality"),
                "transition_driver": max(
                    (
                        (key, safe_float(target_components.get(key), 0.0))
                        for key in TRANSITION_DCF_COMPONENTS
                    ),
                    key=lambda item: abs(item[1]),
                    default=("-", 0.0),
                )[0],
                "transition_driver_label": "largest calibrated direct transition channel",
                "transition_channel_inputs": target_components.get("transition_channel_inputs", {}),
                "transition_data_status": target_components.get("transition_data_status"),
                "macro_channel_inputs": target_components.get("macro_channel_inputs", {}),
                "valuation": valuation,
                "valuation_applicability": valuation.get("applicability_status"),
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
    attribution_total = sum(aggregate_contribution.values())
    attribution_residual = aggregate_impact - attribution_total
    return {
        "value_impact": round(aggregate_impact, 4),
        "physical_loss_delta": round(
            aggregate_target["acute_physical"]
            + aggregate_target["chronic_physical"]
            - aggregate_reference["acute_physical"]
            - aggregate_reference["chronic_physical"],
            4,
        ),
        "macro_loss_delta": round(
            sum(aggregate_target[key] - aggregate_reference[key] for key in MACRO_DCF_COMPONENTS),
            4,
        ),
        "transition_loss_delta": round(
            sum(aggregate_target[key] - aggregate_reference[key] for key in TRANSITION_DCF_COMPONENTS),
            4,
        ),
        "attribution": attribution,
        "attribution_method": "Exact Shapley decomposition across physical, macro, and direct-transition FCFF channels",
        "attribution_residual": round(attribution_residual, 8),
        "weighted_target_present_value": round(weighted_target_value, 6),
        "weighted_reference_present_value": round(weighted_reference_value, 6),
        "weighted_wacc": round(weighted_wacc, 4),
        "weighted_terminal_growth": round(weighted_terminal_growth, 4),
        "instruments": sorted(instrument_rows, key=lambda row: abs(row["value_impact"]), reverse=True),
    }


def scenario_value_impact_without_attribution(scope_rows, target, reference, horizon):
    """Fast DCF repricing used for model-risk sensitivity bands."""
    aggregate_impact = 0.0
    for row in scope_rows:
        weight = safe_float(row.get("weight"), 0.0)
        valuation = row.get("valuation") or valuation_assumptions(row.get("ticker"), row.get("sector"))
        wacc = safe_float(valuation.get("wacc"), 0.075)
        growth = safe_float(valuation.get("terminal_growth"), 0.025)
        target_components = scenario_terminal_components(target, row["sector"], row["vulnerability"], horizon)
        reference_components = scenario_terminal_components(reference, row["sector"], row["vulnerability"], horizon)
        target_value = discounted_scenario_value(target_components, horizon, wacc=wacc, growth=growth)
        reference_value = discounted_scenario_value(reference_components, horizon, wacc=wacc, growth=growth)
        aggregate_impact += weight * (target_value / max(reference_value, 1e-9) - 1)
    return aggregate_impact


def physical_damage_sensitivity_scenario(scenario, multiplier):
    adjusted = dict(scenario)
    adjusted["acute_gdp_loss_2050"] = safe_float(scenario.get("acute_gdp_loss_2050"), 0.0) * multiplier
    adjusted["chronic_gdp_loss_2050"] = safe_float(scenario.get("chronic_gdp_loss_2050"), 0.0) * multiplier
    return adjusted


def holding_scenario_tail_proxy(ticker, sector, horizon=2050, observed_beta=None):
    sector = normalize_model_sector(sector)
    scope_row = {
        "name": yahoo_symbol(ticker),
        "ticker": yahoo_symbol(ticker),
        "sector": sector,
        "weight": 1.0,
        "vulnerability": issuer_vulnerability_profile(ticker, sector),
        "valuation": valuation_assumptions(ticker, sector, observed_beta=observed_beta),
    }
    reference = CLIMATE_SCENARIO_PATHS["baseline"]
    losses = []
    scenario_losses = {}
    for scenario_key in SCENARIO_MATRIX_KEYS:
        result = scenario_repricing_for_scope(
            [scope_row],
            CLIMATE_SCENARIO_PATHS[scenario_key],
            reference,
            horizon,
        )
        loss = max(0.0, -safe_float(result.get("value_impact"), 0.0))
        losses.append((loss, scenario_key))
        scenario_losses[scenario_key] = round(loss, 6)
    tail = sorted(losses, reverse=True)[:SCENARIO_TAIL_COUNT]
    worst_loss, worst_key = max(losses, default=(0.0, "baseline"))
    return {
        "loss_rate": sum(loss for loss, _ in tail) / max(1, len(tail)),
        "worst_loss_rate": worst_loss,
        "worst_scenario": CLIMATE_SCENARIO_PATHS[worst_key]["label"],
        "scenario_losses": scenario_losses,
        "scenarios": [CLIMATE_SCENARIO_PATHS[key]["label"] for _, key in tail],
        "definition": "Mean of the two largest conditional target-versus-baseline losses; no probability claim",
    }


def event_nowcast_for_scope(scope_rows, daily_signal, state):
    if not short_term_hazard_is_calculable(daily_signal):
        return {
            "event_risk": None,
            "selection_risk": None,
            "tactical_overlay_bps": 0,
            "action": "No tactical trade — live hazard data unavailable",
            "data_confidence": None,
            "top_driver": "unavailable",
            "source_mode": daily_signal.get("source_mode", "NWS unavailable"),
            "is_calculable": False,
            "observed_zero": False,
            "decision_status": daily_signal.get(
                "decision_status",
                "not calculable — live NWS hazard data unavailable",
            ),
            "calculation": {
                "event_risk": "Not calculable because live NWS hazard data are unavailable",
                "selection_risk": "Suppressed",
                "overlay_limit_bps": 0,
                "probability_rule": "Unavailable data are not represented as observed zero risk",
            },
            "hazards": [],
        }
    issuer_row = scope_rows[0] if len(scope_rows) == 1 else None
    issuer_symbol = yahoo_symbol(issuer_row.get("ticker")) if issuer_row else ""
    issuer_scope = (
        issuer_row is not None
        and issuer_symbol not in {"", "US", "SECTOR"}
        and issuer_symbol not in SECTOR_ETFS
    )
    issuer_facility_profile = (
        issuer_hazard_exposure_profile(issuer_symbol, issuer_row.get("sector"))
        if issuer_scope
        else None
    )
    issuer_facility_verified = bool(
        issuer_facility_profile
        and issuer_facility_profile.get("observed_hazards") == len(HAZARD_CATEGORIES)
    )
    categories = daily_signal.get("category_intensity", {}) or {}
    confidence = safe_float(state.get("data_confidence"), 0.50)
    event_pressure = clamp(safe_float(state.get("daily_pressure"), 0.0), 0.0, 1.0)
    category_total = sum(max(0.0, safe_float(categories.get(hazard), 0.0)) for hazard in HAZARD_CATEGORIES)
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
    for hazard in HAZARD_CATEGORIES:
        intensity = safe_float(categories.get(hazard), 0.0)
        hazard_intensity = event_pressure * intensity
        weighted_exposure = 0.0
        weighted_vulnerability = 0.0
        weighted_hazard_resilience = 0.0
        represented = []
        quality_labels = set()
        contribution = 0.0
        for row in scope_rows:
            weight = safe_float(row.get("weight"), 0.0)
            sector = row["sector"]
            if sector == "Economy":
                exposure = vulnerability = 0.58
                resilience = 0.50
                quality = "Country aggregate fallback"
            else:
                profile = issuer_hazard_exposure_profile(row.get("ticker"), sector)
                hazard_profile = profile["hazards"][hazard]
                exposure = safe_float(hazard_profile.get("exposure"), 0.50)
                vulnerability = safe_float(hazard_profile.get("vulnerability"), 1.0)
                resilience = safe_float(hazard_profile.get("resilience"), 0.50)
                quality = profile.get("data_quality", "Sector hazard fallback")
            issuer_loss = physical_event_loss(hazard_intensity, exposure, vulnerability, resilience)
            contribution += weight * issuer_loss
            weighted_exposure += weight * exposure
            weighted_vulnerability += weight * vulnerability
            weighted_hazard_resilience += weight * resilience
            represented.append((issuer_loss, row["name"]))
            quality_labels.add(quality)
        raw_event_risk += contribution
        dominant = max(represented, default=(0.0, "-"))[1]
        hazard_rows.append(
            {
                "hazard": hazard,
                "label": hazard.replace("_", " ").title(),
                "intensity": round(intensity, 4),
                "hazard_intensity": round(hazard_intensity, 4),
                "exposure_beta": round(weighted_exposure, 4),
                "exposure": round(weighted_exposure, 4),
                "vulnerability": round(weighted_vulnerability, 4),
                "resilience": round(weighted_hazard_resilience, 4),
                "risk_contribution": round(contribution, 4),
                "dominant_exposure": dominant,
                "data_quality": "; ".join(sorted(quality_labels)),
            }
        )
    event_risk = clamp(raw_event_risk, 0.0, 1.0)
    if issuer_scope and not issuer_facility_verified:
        return {
            "event_risk": None,
            "research_event_index": round(event_risk, 4),
            "selection_risk": None,
            "tactical_overlay_bps": 0,
            "action": "No tactical trade — issuer facility exposure not verified",
            "data_confidence": round(confidence, 4),
            "top_driver": daily_signal.get("top_driver", "climate"),
            "source_mode": daily_signal.get("source_mode", "NWS signal"),
            "is_calculable": False,
            "hazard_feed_calculable": True,
            "issuer_exposure_calculable": False,
            "observed_zero": event_risk == 0.0,
            "decision_status": "not calculable — issuer facility exposure and geolocation are not verified",
            "calculation": {
                "event_risk": "Not calculable for the issuer; displayed research_event_index uses sector fallback",
                "research_event_index": "Unitless NWS severity x sector exposure x issuer proxy vulnerability x (1 - sector resilience)",
                "selection_risk": "Suppressed",
                "overlay_limit_bps": 0,
                "probability_rule": "The research index is not a probability, financial loss, or return",
            },
            "hazards": sorted(hazard_rows, key=lambda row: row["risk_contribution"], reverse=True),
        }
    selection_risk = clamp(0.72 * event_risk + 0.28 * (1 - confidence), 0.0, 1.0)
    observed_zero = category_total <= 0 or event_pressure <= 0
    if observed_zero:
        overlay_bps = 0
        action = "No tactical trade — no active matched NWS hazard"
    else:
        tactical_edge = (
            0.55 * weighted_resilience
            + 0.15 * weighted_opportunity
            - 0.75 * event_risk
        )
        overlay_bps = int(round(TACTICAL_OVERLAY_LIMIT_BPS * clamp(tactical_edge, -1.0, 1.0)))
        if overlay_bps <= -80:
            action = "Underweight / hedge"
        elif overlay_bps >= 80:
            action = "Tactical overweight"
        else:
            action = "Hold near strategic weight"
    return {
        "event_risk": round(event_risk, 4),
        "research_event_index": None,
        "selection_risk": round(selection_risk, 4),
        "tactical_overlay_bps": overlay_bps,
        "action": action,
        "data_confidence": round(confidence, 4),
        "top_driver": daily_signal.get("top_driver", "climate"),
        "source_mode": daily_signal.get("source_mode", "NWS signal"),
        "is_calculable": True,
        "observed_zero": observed_zero,
        "decision_status": (
            "observed zero — NWS feed successful, no matched climate alerts"
            if observed_zero
            else "calculable — observed NWS active-alert severity"
        ),
        "calculation": {
            "event_risk": "Sum[hazard severity x location/asset exposure x vulnerability x (1 - resilience)]",
            "selection_risk": "0.72 event risk + 0.28 data uncertainty",
            "overlay_limit_bps": TACTICAL_OVERLAY_LIMIT_BPS,
            "probability_rule": "NWS active alerts are a severity nowcast, not a disaster probability estimate",
        },
        "hazards": sorted(hazard_rows, key=lambda row: row["risk_contribution"], reverse=True),
    }


def _base_climate_model_lab_payload(scope="portfolio", target="current_policies", reference="baseline", horizon=2050, sector="Technology", ticker="AAPL"):
    target_key = target if target in CLIMATE_SCENARIO_PATHS else "current_policies"
    reference_key = reference if reference in CLIMATE_SCENARIO_PATHS else "baseline"
    horizon = int(clamp(safe_float(horizon, 2050), max(CURRENT_YEAR + 1, 2030), 2050))
    daily_signal = load_daily_climate_signal()
    context = climate_data_context()
    state = climate_state_variables(daily_signal=daily_signal, context=context)
    scope_key, scope_rows = climate_model_scope_rows(scope, sector=sector, ticker=ticker, daily_signal=daily_signal)
    target_scenario = CLIMATE_SCENARIO_PATHS[target_key]
    reference_scenario = CLIMATE_SCENARIO_PATHS[reference_key]
    ngfs_release = latest_official_ngfs_transition()
    sec_history = latest_official_sec_financial_history()
    issuer_demo = latest_eight_issuer_demo()
    target_ngfs = official_ngfs_transition_pathway(target_key, horizon, release=ngfs_release)
    reference_ngfs = official_ngfs_transition_pathway(reference_key, horizon, release=ngfs_release)
    long_term = scenario_repricing_for_scope(scope_rows, target_scenario, reference_scenario, horizon)
    short_term = event_nowcast_for_scope(scope_rows, daily_signal, state)
    scope_labels = {
        "country": "United States country-level stress",
        "sector": f"{normalize_model_sector(sector)} sector",
        "issuer": f"{yahoo_symbol(ticker or 'AAPL')} issuer proxy",
        "portfolio": "Current climate portfolio",
    }
    downscaling_check = physical_downscaling_reconciliation()
    scope_weight_sum = sum(safe_float(row.get("weight"), 0.0) for row in scope_rows)
    treasury = latest_official_treasury_rate("10y")
    treasury_loaded = treasury.get("rate") is not None
    ngfs_loaded = ngfs_release.get("is_loaded") is True
    resolution = [
        {
            "level": "Scenario pathways",
            "input": "Target-reference physical, macro, energy, carbon-price, and demand paths",
            "status": (
                f"Official NGFS {ngfs_release['source_release']} USA transition release loaded; "
                "physical and macro pathways remain project calibrations"
                if ngfs_loaded
                else "Project calibration — official NGFS pathway release not loaded"
            ),
            "output": "Official transition evidence is separate from the unvalidated physical/macro research proxy",
        },
        {"level": "Sector transmission", "input": "GDP beta, input-output supply beta, and physical vulnerability", "status": "Project calibration — governed BEA calibration not loaded", "output": "Sector proxy; not issuer evidence"},
        {
            "level": "Issuer evidence",
            "input": "Facilities, emissions, financial statements, revenue geography, suppliers/customers, and adaptation",
            "status": (
                f"Official SEC history loaded for {len(sec_history['tickers'])} candidates, "
                f"{sec_history['start_period']}-{sec_history['end_period']}; other issuer evidence remains missing"
                if sec_history.get("is_loaded")
                else "Missing or incomplete — no issuer-specific physical conclusion"
            ),
            "output": "SEC accounting/FCFF tie-out pending; sector-calibrated research proxy only",
        },
        {
            "level": "Valuation rate",
            "input": "U.S. Treasury 10-year par yield",
            "status": (
                f"Observed official — {treasury['as_of']}; release {treasury['release_id']}"
                if treasury_loaded
                else "Missing — fallback assumption remains active"
            ),
            "output": "Risk-free leg only; ERP, beta, debt cost, capital structure, and terminal growth remain calibrations",
        },
        {"level": "Portfolio", "input": "Normalized holding weights", "status": "Engineering reconciliation only", "output": "Research aggregation; no allocation recommendation"},
    ]
    calculation_ledger = [
        {
            "step": "Scenario delta",
            "formula": "Delta path = target scenario - reference scenario",
            "input": f"{target_scenario['label']} vs {reference_scenario['label']}",
            "output": f"{long_term['value_impact']:+.4%} as-of-date value impact",
            "check": "Pass" if target_key != reference_key or abs(long_term["value_impact"]) < 1e-10 else "Review",
        },
        {
            "step": "Official NGFS transition evidence",
            "formula": "Pathway delta = target model-median value - reference model-median value; min/max are model range, not probability bounds",
            "input": (
                f"{target_ngfs.get('scenario')}: {target_ngfs.get('carbon_price_median')} vs "
                f"{reference_ngfs.get('scenario')}: {reference_ngfs.get('carbon_price_median')} "
                f"{target_ngfs.get('carbon_price_unit') or reference_ngfs.get('carbon_price_unit') or ''}"
            ),
            "output": (
                f"NGFS release {ngfs_release.get('source_release')}; issuer carbon cost not calculated until covered emissions are loaded"
                if ngfs_loaded
                else "Not loaded; project calibration remains isolated"
            ),
            "check": "Pass" if ngfs_loaded else "Blocked",
        },
        {
            "step": "Sector conservation",
            "formula": "sector loss = country loss x beta_sector / weighted-average beta",
            "input": "Covered-sector value-added weights",
            "output": f"acute {downscaling_check['acute']:.6f}x; chronic {downscaling_check['chronic']:.6f}x",
            "check": "Pass" if abs(downscaling_check["acute"] - 1) < 1e-9 and abs(downscaling_check["chronic"] - 1) < 1e-9 else "Review",
        },
        {
            "step": "Issuer bound",
            "formula": "issuer loss = sector loss x clip(issuer / sector median, 0.55, 1.45)",
            "input": "Fixed-asset and labor-intensity relative ratios",
            "output": "No deterministic ticker-randomized ratio",
            "check": "Pass",
        },
        {
            "step": "Acute physical nowcast",
            "formula": "Loss = hazard severity x exposure x vulnerability x (1 - resilience)",
            "input": "NWS hazard mix plus facility mapping when loaded; otherwise sector fallback",
            "output": (
                f"event risk {short_term['event_risk']:.4%}; not an occurrence probability"
                if short_term["event_risk"] is not None
                else "Not calculable; issuer event output suppressed"
            ),
            "check": "Pass" if short_term.get("is_calculable") else "Blocked",
        },
        {
            "step": "Revenue transmission",
            "formula": "Revenue loss = beta_GDP x country GDP loss + beta_sector x demand shift + beta_supply x supply shock",
            "input": "Country scenario, sector transmission, issuer earnings beta",
            "output": "Country, sector-demand, and supply-chain channels shown separately",
            "check": "Pass",
        },
        {
            "step": "Transition cash flow",
            "formula": "TR = carbon cost + demand shift + energy cost + transition CapEx - pass-through",
            "input": "Scenario pathway x sector channel exposure; atmospheric CO2 excluded",
            "output": f"transition delta {long_term['transition_loss_delta']:+.4%}",
            "check": "Pass",
        },
        {
            "step": "Valuation",
            "formula": "PV = annual climate-adjusted FCFF + terminal value; WACC uses CAPM and sector capital structure",
            "input": f"Horizon {horizon}; weighted WACC {long_term['weighted_wacc']:.2%}; terminal growth {long_term['weighted_terminal_growth']:.2%}",
            "output": f"target PV {long_term['weighted_target_present_value']:.4f}; reference PV {long_term['weighted_reference_present_value']:.4f}",
            "check": "Pass" if long_term["weighted_reference_present_value"] > 0 else "Review",
        },
        {
            "step": "Attribution",
            "formula": "Exact Shapley value across physical and transition FCFF channels",
            "input": "Acute, chronic, country GDP, sector demand, supply chain, carbon, energy, CapEx, and pass-through",
            "output": f"residual {long_term['attribution_residual']:.8f}",
            "check": "Pass" if abs(long_term["attribution_residual"]) < 1e-8 else "Review",
        },
        {
            "step": "Portfolio weights",
            "formula": "portfolio impact = sum(weight x issuer impact)",
            "input": f"{len(scope_rows)} modeled exposure rows",
            "output": f"weight sum {scope_weight_sum:.6f}",
            "check": "Pass" if abs(scope_weight_sum - 1) < 1e-8 else "Review",
        },
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
        "official_transition": {
            "release": {
                "is_loaded": ngfs_loaded,
                "release_id": ngfs_release.get("release_id"),
                "source_release": ngfs_release.get("source_release"),
                "source_release_date": ngfs_release.get("source_release_date"),
                "source_url": ngfs_release.get("source_url"),
                "region": ngfs_release.get("region"),
                "physical_damage_status": ngfs_release.get("physical_damage_status"),
            },
            "target": target_ngfs,
            "reference": reference_ngfs,
            "issuer_translation_status": "blocked until covered issuer emissions, jurisdiction, free allocation, and pass-through evidence are loaded",
        },
        "demo_issuers": issuer_demo,
        "climate_state": state,
        "scope_resolution": resolution,
        "calculation_ledger": calculation_ledger,
        "methodology": {
            "long_term": "Target minus reference pathways flow through country GDP -> sector demand/input-output -> issuer earnings beta, then into FCFF. Transition FCFF is carbon cost + demand shift + energy cost + transition CapEx - pass-through; CO2 concentration is not a transition input.",
            "short_term": "NWS hazard severity is retained as research context. It is not an issuer probability or loss; issuer use requires verified facility exposure.",
            "probability_rule": "Scenario outputs are conditional stresses. The model does not assign occurrence probabilities to NGFS-style scenarios.",
            "tail_rule": "Scenario tail is reported separately from physical and transition pressure to avoid double counting in the client risk score.",
        },
        "calibration_notice": "Official NGFS Phase 5.1 USA transition pathways are loaded as a separate evidence layer. The current sector cash-flow coefficients are not re-labeled as official; issuer carbon cost remains blocked until emissions and policy-coverage evidence are loaded. Physical and macro pathways remain project calibrations.",
    }


def climate_model_lab_payload(scope="portfolio", target="current_policies", reference="baseline", horizon=2050, sector="Technology", ticker="AAPL", assumption_case="base"):
    scope_key = scope if scope in {"country", "sector", "issuer", "portfolio"} else "portfolio"
    symbol = yahoo_symbol(ticker or "AAPL")
    sector_resolution = resolve_issuer_sector(symbol, requested_sector=sector) if scope_key == "issuer" else None
    target_key = target if target in CLIMATE_SCENARIO_PATHS else "current_policies"
    reference_key = reference if reference in CLIMATE_SCENARIO_PATHS else "baseline"
    target_scenario = CLIMATE_SCENARIO_PATHS[target_key]
    reference_scenario = CLIMATE_SCENARIO_PATHS[reference_key]
    horizon_value = int(clamp(safe_float(horizon, 2050), max(CURRENT_YEAR + 1, 2030), 2050))

    if sector_resolution and not sector_resolution["is_calculable"]:
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "scope": "issuer",
            "scope_label": f"{symbol} issuer — not calculable",
            "target_key": target_key,
            "target": {**target_scenario, "key": target_key},
            "reference_key": reference_key,
            "reference": {**reference_scenario, "key": reference_key},
            "horizon": horizon_value,
            "sector": None,
            "ticker": symbol,
            "sector_resolution": sector_resolution,
            "long_term": {
                "value_impact": None,
                "physical_loss_delta": None,
                "macro_loss_delta": None,
                "transition_loss_delta": None,
                "attribution": [],
                "attribution_method": "Not run",
                "attribution_residual": None,
                "weighted_target_present_value": None,
                "weighted_reference_present_value": None,
                "weighted_wacc": None,
                "weighted_terminal_growth": None,
                "instruments": [],
            },
            "short_term": {
                "event_risk": None,
                "research_event_index": None,
                "selection_risk": None,
                "tactical_overlay_bps": 0,
                "action": "Issuer event output suppressed — issuer sector is not verified",
                "data_confidence": 0.0,
                "top_driver": None,
                "source_mode": "blocked before risk calculation",
                "is_calculable": False,
                "observed_zero": False,
                "decision_status": sector_resolution["status"],
                "hazards": [],
            },
            "climate_state": None,
            "scope_resolution": [
                {
                    "level": "Issuer mapping",
                    "input": symbol,
                    "status": "Blocked",
                    "output": "No verified sector; no Technology default and no risk score",
                }
            ],
            "calculation_ledger": [
                {
                    "step": "Issuer-sector mapping",
                    "formula": "ticker -> controlled issuer-sector crosswalk",
                    "input": symbol,
                    "output": sector_resolution["status"],
                    "check": "Blocked",
                }
            ],
            "decision_suitable": False,
                "decision_status": "Blocked — resolve the issuer sector before any physical, transition, or valuation calculation",
            "model_stage": "Research only — model not promoted",
            "output_class": "Not calculable",
            "evidence_grade": "Missing mandatory issuer mapping",
            "permitted_use": "Data-gap review only; no investment or tactical decision",
            "methodology": {
                "long_term": "Not run because the issuer sector is unverified.",
                "short_term": "Not run because sector and issuer exposure are unverified.",
                "probability_rule": "No missing input is represented as zero risk.",
                "tail_rule": "No scenario tail is produced from an unverified issuer mapping.",
            },
            "calibration_notice": "Unresolved tickers fail closed. Supply governed entity metadata or restore a resolvable listed-equity metadata source before rerunning the model.",
        }

    resolved_sector = sector_resolution["resolved_sector"] if sector_resolution else sector
    payload = _base_climate_model_lab_payload(
        scope=scope_key,
        target=target_key,
        reference=reference_key,
        horizon=horizon_value,
        sector=resolved_sector,
        ticker=symbol,
    )
    long_term = payload["long_term"]
    short_term = payload["short_term"]
    modeled_sector = (
        long_term["instruments"][0]["sector"]
        if scope_key in {"issuer", "sector"} and long_term.get("instruments")
        else normalize_model_sector(resolved_sector)
    )
    payload["sector"] = modeled_sector
    payload["sector_resolution"] = sector_resolution
    pilot = latest_governed_duke_pilot() if scope_key == "issuer" and symbol == "DUK" else {"is_loaded": False}
    payload["issuer_pilot"] = pilot
    if scope_key == "issuer":
        payload["scope_label"] = (
            f"{symbol} evidence pilot + {modeled_sector} sector stress"
            if pilot.get("is_loaded")
            else f"{symbol} issuer research proxy"
        )
        payload["scope_resolution"].insert(
            0,
            {
                "level": "Issuer mapping",
                "input": f"{symbol}; requested {sector_resolution['requested_sector'] or 'none'}",
                "status": sector_resolution["status"],
                "output": f"{modeled_sector}; {sector_resolution['source']} (as of {sector_resolution['as_of']})",
            },
        )
        payload["calculation_ledger"].insert(
            0,
            {
                "step": "Issuer-sector mapping",
                "formula": "ticker -> controlled issuer-sector crosswalk; verified mapping overrides UI selection",
                "input": f"{symbol}; requested {sector_resolution['requested_sector'] or 'none'}",
                "output": f"{modeled_sector}; {sector_resolution['status']}",
                "check": "Pass",
            },
        )
        if pilot.get("is_loaded"):
            payload["scope_resolution"].insert(
                1,
                {
                    "level": "DUK governed pilot",
                    "input": f"EPA {pilot['epa_year']} ownership/emissions + FEMA county context + SEC 2025",
                    "status": f"Hash verified — release {pilot['release_id']}",
                    "output": (
                        f"{pilot['direct_emitter_matches']}/{pilot['parent_records']} direct-emitter matches; "
                        f"{pilot['coordinate_matches']} coordinates; physical financial loss remains Not calculable"
                    ),
                },
            )
            for hazard in payload["short_term"].get("hazards", []):
                hazard["data_quality"] = (
                    "Sector hazard fallback; EPA facility ownership/coordinates and FEMA county context loaded, "
                    "but economic exposure and damage evidence are missing"
                )

    for row in payload["scope_resolution"]:
        if row["level"] == "Issuer":
            row.update(
                {
                    "input": "Controlled sector mapping; facility hazard exposure, earnings beta, revenue geography, and business links",
                    "status": "Research proxy; issuer event output blocked when facility mapping is missing",
                    "output": "Conditional issuer value proxy; no invented issuer event risk",
                }
            )

    valuation_suitable = all(
        bool((row.get("valuation") or {}).get("decision_suitable", True))
        for row in long_term.get("instruments", [])
    )
    for row in payload["calculation_ledger"]:
        if row["step"] == "Acute physical nowcast":
            row["formula"] = "Research index = hazard severity x exposure x vulnerability x (1 - resilience)"
            row["input"] = "NWS hazard mix plus verified facility mapping; sector fallback is display-only for issuer scope"
            if short_term.get("event_risk") is not None:
                row["output"] = f"hazard/exposure index {short_term['event_risk'] * 100:.2f} / 100; not a probability or financial loss"
            elif short_term.get("research_event_index") is not None:
                row["output"] = f"Issuer risk not calculable; sector proxy index {short_term['research_event_index'] * 100:.2f} / 100; no issuer decision output"
            else:
                row["output"] = "Not calculable; issuer event output suppressed"
        elif row["step"] == "Revenue transmission":
            row.update(
                {
                    "step": "Macro transmission",
                    "formula": "Macro loss = country GDP channel + input-output supply-chain channel",
                    "input": "Country scenario plus input-output supply calibration",
                    "output": f"macro delta {long_term['macro_loss_delta']:+.4%}; kept separate from direct transition risk",
                }
            )
        elif row["step"] == "Transition cash flow":
            row.update(
                {
                    "step": "Direct transition cash flow",
                    "formula": "TR = sector demand + carbon cost + energy cost + transition CapEx - pass-through",
                    "output": f"direct transition delta {long_term['transition_loss_delta']:+.4%}",
                }
            )
        elif row["step"] == "Valuation" and not valuation_suitable:
            row["output"] = "Research-only blocker: generic FCFF/WACC is not decision-suitable for a financial institution"
            row["check"] = "Blocked"
        elif row["step"] == "Attribution":
            row["formula"] = "Exact Shapley value across physical, macro, and direct-transition FCFF channels"

    payload["decision_suitable"] = bool(scope_key != "issuer" or (valuation_suitable and short_term.get("is_calculable")))
    issuer_blocks = []
    if scope_key == "issuer" and not short_term.get("is_calculable"):
        issuer_blocks.append(
            "issuer economic exposure and damage evidence are not verified; issuer event output suppressed"
            if pilot.get("is_loaded")
            else "issuer facility exposure is not verified; issuer event output suppressed"
        )
    if scope_key == "issuer" and not valuation_suitable:
        issuer_blocks.append("generic FCFF/WACC is not decision-suitable for a financial institution")
    if scope_key == "issuer" and pilot.get("is_loaded"):
        issuer_blocks.extend([
            "EPA emissions and facility evidence are loaded, but free allocation, pass-through, and emissions path are missing",
            "FEMA county hazard context is loaded, but exposed asset value and damage functions are missing",
            "SEC FCFF bridge is a filing-tie-out candidate; WACC/terminal-growth gate remains incomplete",
        ])
    evidence_limits = issuer_blocks or [
        "sector/project calibrations remain; official NGFS and SEC history are loaded, but emissions and accounting tie-out are pending"
    ]
    payload["decision_status"] = "Research-only — " + "; ".join(evidence_limits)
    payload["model_stage"] = "Research only — model not promoted"
    payload["output_class"] = (
        f"{modeled_sector} sector stress plus governed issuer evidence; issuer value not calculable"
        if scope_key == "issuer" and pilot.get("is_loaded")
        else ("Sector-calibrated issuer sensitivity" if scope_key == "issuer" else "Project-calibrated conditional stress")
    )
    payload["evidence_grade"] = "Mixed observed/derived/proxy with mandatory gaps" if pilot.get("is_loaded") else "Proxy-dominant"
    payload["permitted_use"] = "Scenario research and data-gap review only; no investment or tactical decision"
    payload["methodology"] = {
        "long_term": "Target minus reference pathways flow through country GDP and supply-chain macro transmission, direct transition cash-flow channels, and physical damage into a conditional FCFF research proxy. CO2 concentration is not a transition input.",
        "short_term": "NWS severity x exposure x vulnerability x (1-resilience) is a unitless research index. Issuer use requires verified facility exposure; a sector fallback never becomes an issuer loss or decision output.",
        "probability_rule": "Scenario outputs are conditional stresses. The model does not assign occurrence probabilities to NGFS-style scenarios.",
        "tail_rule": "Scenario tail is reported separately from physical and transition pressure to avoid double counting in the client risk score.",
    }
    payload["calibration_notice"] = (
        "Outputs are research proxies, not audited issuer forecasts. Industry mapping is controlled and disclosed; "
        "missing facility, revenue-geography, and supplier/customer data are not fabricated. Financial-institution "
        "FCFF/WACC results remain blocked from decision use pending an approved equity or residual-income method."
    )
    public_release = latest_eight_issuer_public_evidence()
    valuation_release = latest_eight_issuer_valuation_inputs()
    climate_evidence_release = latest_eight_issuer_climate_evidence()
    if public_release.get("is_loaded"):
        scope_by_ticker = {row.get("ticker"): row for row in public_release.get("scope1_rows", [])}
        physical_by_ticker = {row.get("ticker"): row for row in public_release.get("physical_rows", [])}
        payload["public_evidence_universe"] = {
            "release_id": public_release.get("release_id"),
            "rows": [
                {
                    "ticker": ticker_key,
                    "scope1_tco2e": safe_float((scope_by_ticker.get(ticker_key) or {}).get("scope1_tco2e"), None),
                    "fema_county_matches": int(safe_float((physical_by_ticker.get(ticker_key) or {}).get("fema_county_matches"), 0)),
                    "epa_parent_facilities": int(safe_float((physical_by_ticker.get(ticker_key) or {}).get("epa_parent_facilities"), 0)),
                    "disclosed_metric": (physical_by_ticker.get(ticker_key) or {}).get("disclosed_metric"),
                    "disclosed_value": safe_float((physical_by_ticker.get(ticker_key) or {}).get("disclosed_value"), None),
                }
                for ticker_key in sorted(scope_by_ticker)
            ],
        }
    if scope_key == "issuer" and public_release.get("is_loaded") and symbol in scope_by_ticker:
        def issuer_row(rows):
            return next((row for row in rows if row.get("ticker") == symbol), {})

        scope1 = issuer_row(public_release.get("scope1_rows", []))
        physical = issuer_row(public_release.get("physical_rows", []))
        transmission = issuer_row(public_release.get("transmission_rows", []))
        demo = issuer_row((payload.get("demo_issuers") or {}).get("rows", []))
        target_path = (payload.get("official_transition") or {}).get("target") or {}
        reference_path = (payload.get("official_transition") or {}).get("reference") or {}
        target_price = safe_float(target_path.get("carbon_price_median"), None)
        reference_price = safe_float(reference_path.get("carbon_price_median"), None)
        tonnes = safe_float(scope1.get("scope1_tco2e"), None)
        price_delta = None if target_price is None or reference_price is None else target_price - reference_price
        gross_sensitivity = None if tonnes is None or price_delta is None else tonnes * price_delta
        base_cash_flow = safe_float(demo.get("duke_fcff_usd"), None)
        baseline_type = "unlevered FCFF candidate"
        if base_cash_flow is None:
            base_cash_flow = safe_float(demo.get("free_cash_flow_usd"), None)
            baseline_type = "free cash flow"
        ratio = (
            gross_sensitivity / base_cash_flow
            if gross_sensitivity is not None and base_cash_flow is not None and base_cash_flow > 0
            else None
        )
        payload["issuer_public_evidence"] = {
            "is_loaded": True,
            "release_id": public_release.get("release_id"),
            "ticker": symbol,
            "transition": {
                "classification": "calculated uniform-price gross sensitivity",
                "scope1_tco2e": tonnes,
                "scope1_year": int(safe_float(scope1.get("reporting_year"), 0)),
                "source_title": scope1.get("source_title"),
                "source_url": scope1.get("source_url"),
                "target_price_usd2010_per_tco2": target_price,
                "reference_price_usd2010_per_tco2": reference_price,
                "price_delta_usd2010_per_tco2": price_delta,
                "gross_sensitivity_usd": gross_sensitivity,
                "cash_flow_baseline_usd": base_cash_flow,
                "cash_flow_baseline_type": baseline_type,
                "gross_sensitivity_to_cash_flow": ratio,
                "net_transition_cost_usd": None,
                "net_cost_status": "Not calculable — coverage, jurisdiction, free allocation, pass-through, and future emissions path are missing",
            },
            "physical": {
                "classification": "exposure screen",
                "epa_parent_facilities": int(safe_float(physical.get("epa_parent_facilities"), 0)),
                "epa_direct_emitter_matches": int(safe_float(physical.get("epa_direct_emitter_matches"), 0)),
                "fema_county_matches": int(safe_float(physical.get("fema_county_matches"), 0)),
                "emissions_weighted_county_nri_score": safe_float(physical.get("emissions_weighted_county_nri_score"), None),
                "weighting_method": physical.get("weighting_method"),
                "disclosed_metric": physical.get("disclosed_metric"),
                "disclosed_value": safe_float(physical.get("disclosed_value"), None),
                "disclosed_unit": physical.get("disclosed_unit"),
                "disclosed_year": physical.get("disclosed_year"),
                "screen_status": physical.get("screen_status"),
                "financial_loss_usd": None,
                "financial_loss_status": "Not calculable — asset value, damage function, interruption, and insurance/recovery are missing",
            },
            "macro_supply": {
                "classification": "observed financial context",
                "operating_cash_flow_usd": safe_float(transmission.get("operating_cash_flow_usd"), None),
                "capital_expenditure_usd": safe_float(transmission.get("capital_expenditure_usd"), None),
                "free_cash_flow_usd": safe_float(transmission.get("free_cash_flow_usd"), None),
                "capex_to_operating_cash_flow": safe_float(transmission.get("capex_to_operating_cash_flow"), None),
                "loss_usd": None,
                "loss_status": "Not calculable — revenue geography, value-chain weights, BEA industry join, and compatible scenario shock are missing",
            },
            "allowed_use": public_release.get("allowed_use"),
        }
        prototype = issuer_prototype_valuation(
            symbol,
            target_key,
            reference_key,
            payload.get("horizon"),
            assumption_case,
            scope1,
            physical,
            valuation_release,
            ngfs_release=latest_official_ngfs_transition(),
            climate_evidence=climate_evidence_release,
        )
        valuation_range = {}
        if prototype.get("is_calculable"):
            for case_name in ("low", "base", "high"):
                case_result = issuer_prototype_valuation(
                    symbol,
                    target_key,
                    reference_key,
                    payload.get("horizon"),
                    case_name,
                    scope1,
                    physical,
                    valuation_release,
                    ngfs_release=latest_official_ngfs_transition(),
                    climate_evidence=climate_evidence_release,
                )
                valuation_range[case_name] = case_result.get("value_impact")
        payload["prototype_valuation"] = prototype
        payload["valuation_range"] = valuation_range
        payload["sector_context"] = payload["long_term"]
        payload["long_term"] = {
            "value_impact": prototype.get("value_impact"),
            "physical_loss_delta": next((row.get("terminal_cash_flow_delta_rate") for row in prototype.get("channels", []) if row.get("key") == "physical"), None),
            "macro_loss_delta": next((row.get("terminal_cash_flow_delta_rate") for row in prototype.get("channels", []) if row.get("key") == "macro_supply"), None),
            "transition_loss_delta": next((row.get("terminal_cash_flow_delta_rate") for row in prototype.get("channels", []) if row.get("key") == "transition"), None),
            "attribution": prototype.get("channels", []),
            "attribution_method": "Exact three-channel Shapley decomposition of the assumption-enabled DCF",
            "attribution_residual": prototype.get("attribution_residual"),
            "weighted_target_present_value": prototype.get("target_enterprise_value_usd"),
            "weighted_reference_present_value": prototype.get("reference_enterprise_value_usd"),
            "weighted_wacc": prototype.get("wacc"),
            "weighted_terminal_growth": prototype.get("terminal_growth"),
            "instruments": [],
        }
        payload["scope_label"] = f"{symbol} long-term climate valuation"
        payload["decision_suitable"] = False
        payload["decision_status"] = prototype.get("status")
        payload["output_class"] = "Public-data + disclosed-assumption FCFF/DCF scenario sensitivity"
        payload["evidence_grade"] = "Issuer Scope 1/2/3, SEC PP&E/FCFF, FEMA EAL and CIE pathways separated from financial-conversion assumptions"
        payload["permitted_use"] = "Long-horizon scenario comparison, peer research, risk budgeting, and issuer engagement; no price target or automatic position"
        payload["calibration_notice"] = (
            "Company-reported Scope 1/2/3, SEC cash flow and PP&E, official NGFS transition paths, FEMA expected annual loss rates, CIE heat-productivity pathways, market beta, and Treasury data form the public-data layer. "
            "Policy incidence, pass-through, emissions decline, PP&E allocation, insurance/adaptation, labour conversion, macro elasticity, ERP, and terminal growth are explicit Low/Base/High assumptions."
        )
    return payload


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
    chronic = state["chronic_climate_state"]
    transition_channels = structural_transition_pressure(sector)
    physical_pressure = clamp(0.65 * chronic * sensitivity + 0.35 * climate_risk, 0.02, 0.98)
    transition_pressure = safe_float(transition_channels.get("risk"), 0.50)
    climate_pressure = clamp(0.54 * physical_pressure + 0.46 * transition_pressure, 0.02, 0.98)
    return {
        "physical_pressure": round(physical_pressure, 4),
        "transition_pressure": round(transition_pressure, 4),
        "climate_pressure": round(climate_pressure, 4),
        "resilience": round(resilience, 4),
        "opportunity": round(opportunity, 4),
        "data_confidence": round(confidence, 4),
        "sensitivity": round(sensitivity, 4),
        "transition_channels": transition_channels,
        "transition_data_status": transition_channels.get("status"),
    }


def historical_climate_pressure_for_year(year, climate_rows=None):
    climate_rows = climate_rows or climate_signal()
    if not climate_rows:
        return 0.50
    cutoff_year = int(year) - 1
    available_rows = sorted(
        [row for row in climate_rows if int(row.get("year", 0)) <= cutoff_year],
        key=lambda row: int(row.get("year", 0)),
    )
    if not available_rows:
        return 0.50
    row = available_rows[-1]
    score = safe_float(row.get("climate_risk_score"), 0.0)
    history = [safe_float(item.get("climate_risk_score"), 0.0) for item in available_rows]
    below = sum(1 for value in history if value < score)
    equal = sum(1 for value in history if abs(value - score) <= 1e-12)
    percentile_rank = (below + 0.5 * equal) / max(1, len(history))
    return round(clamp(percentile_rank, 0.05, 0.95), 4)


def climate_source_rows(daily_signal=None, context=None):
    daily_signal = daily_signal or load_daily_climate_signal()
    context = context or climate_data_context()
    treasury = latest_official_treasury_rate("10y")
    ngfs = latest_official_ngfs_transition()
    sec_history = latest_official_sec_financial_history()
    rows = []
    for item in CLIMATE_DATA_SOURCE_CATALOG:
        status = item["status"]
        mode = "Client reference"
        if item["name"] == "NWS Active Alerts":
            status = daily_signal.get("decision_status", daily_signal.get("source_mode", status))
            mode = "Live model input"
        elif item["name"] in {"NASA GISTEMP", "NOAA NCEI Billion-Dollar Disasters"}:
            status = context.get("source_mode", status)
            mode = "Official model input"
        elif item["name"] == "NOAA GML CO2":
            status = context.get("source_mode", status)
            mode = "Context only - excluded from transition score"
        elif item["name"] == "NGFS Scenarios":
            status = (
                f"Observed official | Phase {ngfs['source_release']} | USA transition | {ngfs['release_id']}"
                if ngfs.get("is_loaded")
                else "Not loaded — project scenario calibration remains isolated"
            )
            mode = "Official transition pathway input; issuer translation blocked"
        elif item["name"] == "SEC EDGAR APIs":
            status = (
                f"Observed official | {sec_history['start_period']}-{sec_history['end_period']} | "
                f"{sec_history['fact_count']:,} facts | {sec_history['release_id']}"
                if sec_history.get("is_loaded")
                else "Not loaded — issuer financial baseline unavailable"
            )
            mode = "Official financial-history input; accounting/FCFF tie-out pending"
        elif item["name"] in {"EPA GHGRP", "EPA eGRID", "EIA Open Data"}:
            mode = "Transition-risk source"
        elif item["name"] in {"BEA GDP by Industry", "BEA Input-Output Accounts", "FRED / ALFRED"}:
            mode = "Macro transmission source"
        elif item["name"] == "U.S. Treasury Daily Rates":
            if treasury.get("rate") is not None:
                status = f"Observed official | 10Y {treasury['rate']:.2%} | {treasury['as_of']} | {treasury['release_id']}"
            else:
                status = "Not loaded — valuation fallback remains active"
            mode = "Valuation input — risk-free leg only"
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
    scenario_tail_loss = safe_float(
        cvor_summary.get("scenario_tail_loss_rate"),
        0.0,
    )
    tail_watch_threshold = 0.05
    tail_high_threshold = 0.10
    if scenario_tail_loss <= tail_watch_threshold:
        scenario_tail_score = 0.33 * scenario_tail_loss / tail_watch_threshold
    elif scenario_tail_loss <= tail_high_threshold:
        scenario_tail_score = 0.33 + 0.33 * (
            (scenario_tail_loss - tail_watch_threshold) / (tail_high_threshold - tail_watch_threshold)
        )
    else:
        scenario_tail_score = 0.66 + 0.34 * clamp(
            (scenario_tail_loss - tail_high_threshold) / tail_high_threshold,
            0.0,
            1.0,
        )
    transition_weighted = 0.0
    top_affected = []
    if latest_alloc:
        total_weight = sum(safe_float(r.get("climate_weight"), 0.0) for r in latest_alloc) or 1.0
        transition_weighted = 0.0
        for row in latest_alloc:
            weight = safe_float(row.get("climate_weight"), 0.0) / total_weight
            sector = row.get("sector") or SECTOR_ETFS.get(row.get("ticker"), {}).get("name") or "Technology"
            transition = structural_transition_pressure(sector)
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
                        "action": "High proxy stress" if combined >= 0.68 else ("Medium proxy stress" if combined >= 0.46 else "Low proxy stress"),
                        "driver": row.get("daily_driver") or transition.get("status"),
                    }
                )
    transition_score = clamp(transition_weighted, 0.0, 1.0)
    pressure_score = clamp(0.55 * physical_score + 0.45 * transition_score, 0.0, 1.0)
    decision_score = max(pressure_score, scenario_tail_score)
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
        "macro_transition_score": 0.0,
        "transition_data_status": "Sector cash-flow calibration; live NGFS/EIA/EPA/SEC transition inputs not loaded",
        "scenario_tail_score": round(scenario_tail_score, 4),
        "scenario_tail_loss_rate": round(scenario_tail_loss, 4),
        "scenario_tail_thresholds": {
            "watch": tail_watch_threshold,
            "high": tail_high_threshold,
            "status": "High" if scenario_tail_loss >= tail_high_threshold else ("Watch" if scenario_tail_loss >= tail_watch_threshold else "Within guardrail"),
        },
        "confidence": round(confidence, 4),
        "climate_state": state,
        "methodology_stack": [
            {"step": "Country scenarios", "output": "Target minus reference acute, chronic, and transition paths"},
            {"step": "Downscaling", "output": "Sector vulnerability plus issuer fixed-asset and labor-intensity proxies"},
            {"step": "Valuation", "output": "Climate-adjusted cash flows discounted into an as-of-date value impact"},
            {"step": "Hazard context", "output": "NWS alert severity remains a unitless monitor and does not create issuer loss or a trade"},
            {"step": "Validation", "output": "Engineering checks pass; external calibration and independent model validation remain pending"},
        ],
        "calculation_rules": {
            "physical_pressure": "0.58 acute NWS state + 0.42 chronic official-data state",
            "transition_pressure": "Portfolio-weighted (carbon cost + demand shift + energy cost + transition CapEx - pass-through); CO2 concentration excluded",
            "client_pressure": "0.55 physical pressure + 0.45 transition pressure",
            "decision_rule": "Maximum of client pressure and the explicitly thresholded scenario-tail guardrail; no additive double count",
        },
        "model_coverage": [
            {
                "layer": "Live physical event nowcast",
                "coverage": "NWS alert type, intensity, and affected area",
                "status": "Operational",
                "decision_use": "Hazard monitoring only; no issuer loss, probability, or trade",
            },
            {
                "layer": "Chronic physical state",
                "coverage": "NASA temperature and NCEI disaster history; NOAA CO2 shown as context only",
                "status": "Operational",
                "decision_use": "Climate-state context; not issuer financial loss",
            },
            {
                "layer": "Scenario repricing",
                "coverage": "Target-reference acute, chronic, and transition paths",
                "status": "Calibrated proxy",
                "decision_use": "Sector research stress pending official NGFS ingestion",
            },
            {
                "layer": "Issuer downscaling",
                "coverage": "Sector sensitivity, fixed-asset and labor-intensity ratios",
                "status": "Proxy",
                "decision_use": "Not issuer-specific; display-only research fallback",
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
        "client_action": "Review scenario drivers, evidence coverage, and missing issuer data; no allocation action is authorized.",
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


def automatic_optimizer_universe(daily_signal=None, tactical=False):
    daily_signal = daily_signal or load_daily_climate_signal()
    etf_ranked = []
    for item in DAILY_CLIMATE_ETFS:
        if tactical:
            relation = climate_relation_score(item.get("exposure", {}), daily_signal)
        else:
            sector, risk, _ = etf_climate_profile(item["ticker"])
            transition = structural_transition_pressure(normalize_model_sector(sector))
            relation = 1 - 0.55 * risk - 0.45 * transition["risk"]
        etf_ranked.append((relation, item["ticker"]))
    stock_ranked = []
    for item in DAILY_CLIMATE_STOCKS:
        if tactical:
            relation = climate_relation_score(item.get("exposure", {}), daily_signal)
        else:
            sector = normalize_model_sector(item.get("sector") or guess_sector(item["ticker"]))
            transition = structural_transition_pressure(sector)
            stance_score = {"beneficiary": 0.20, "hedge": 0.12, "mixed": 0.0, "risk": -0.20}.get(item.get("stance"), 0.0)
            relation = 0.55 + stance_score - 0.35 * transition["risk"] - 0.10 * COMPANY_SECTOR_SENSITIVITY.get(sector, 0.50)
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


def bounded_priority_allocation(rows, budget, priority_key, effective_caps=None):
    if not rows or budget <= 0:
        return {}, {}
    budget = safe_float(budget, 0.0)
    minimum_feasible_cap = budget / len(rows)
    caps = effective_caps or {
        row["ticker"]: max(safe_float(row.get("confidence_cap"), minimum_feasible_cap), minimum_feasible_cap)
        for row in rows
    }
    priorities = {
        row["ticker"]: max(1e-8, safe_float(row.get(priority_key), 0.0))
        for row in rows
    }
    weights = {row["ticker"]: 0.0 for row in rows}
    active = set(weights)
    remaining = budget
    while active and remaining > 1e-12:
        denominator = sum(priorities[ticker] for ticker in active) or len(active)
        proposed = {ticker: remaining * priorities[ticker] / denominator for ticker in active}
        capped = [ticker for ticker, weight in proposed.items() if weight > caps[ticker] + 1e-12]
        if not capped:
            for ticker, weight in proposed.items():
                weights[ticker] += weight
            remaining = 0.0
            break
        for ticker in capped:
            allocation = min(caps[ticker] - weights[ticker], remaining)
            weights[ticker] += max(0.0, allocation)
            remaining -= max(0.0, allocation)
            active.remove(ticker)
    if remaining > 1e-9 and active:
        equal_add = remaining / len(active)
        for ticker in active:
            weights[ticker] += equal_add
        remaining = 0.0
    return weights, caps


def project_capped_simplex(values, total, caps):
    values = [safe_float(value, 0.0) for value in values]
    caps = [max(0.0, safe_float(cap, 0.0)) for cap in caps]
    total = max(0.0, safe_float(total, 0.0))
    if not values or total <= 0:
        return [0.0 for _ in values]
    if sum(caps) < total - 1e-12:
        floor_cap = total / len(caps)
        caps = [max(cap, floor_cap) for cap in caps]
    low = min(value - cap for value, cap in zip(values, caps)) - total
    high = max(values) + total
    for _ in range(100):
        midpoint = 0.5 * (low + high)
        projected = [min(cap, max(0.0, value - midpoint)) for value, cap in zip(values, caps)]
        if sum(projected) > total:
            low = midpoint
        else:
            high = midpoint
    projected = [min(cap, max(0.0, value - high)) for value, cap in zip(values, caps)]
    residual = total - sum(projected)
    for index in sorted(range(len(projected)), key=lambda i: caps[i] - projected[i], reverse=True):
        if residual <= 1e-12:
            break
        addition = min(residual, caps[index] - projected[index])
        projected[index] += addition
        residual -= addition
    return projected


def historical_return_covariance(rows, chart_lookup):
    return_maps = []
    for row in rows:
        observations = chart_lookup.get(row["ticker"], []) or []
        price_map = {str(item.get("date")): safe_float(item.get("close"), 0.0) for item in observations if safe_float(item.get("close"), 0.0) > 0}
        dates = sorted(price_map)
        returns = {
            dates[index]: price_map[dates[index]] / price_map[dates[index - 1]] - 1
            for index in range(1, len(dates))
            if price_map[dates[index - 1]] > 0
        }
        return_maps.append(returns)
    size = len(rows)
    covariance = [[0.0 for _ in range(size)] for _ in range(size)]
    for i in range(size):
        for j in range(i, size):
            common = sorted(set(return_maps[i]) & set(return_maps[j]))[-252:]
            if len(common) >= 20:
                left = [return_maps[i][date] for date in common]
                right = [return_maps[j][date] for date in common]
                mean_left = sum(left) / len(left)
                mean_right = sum(right) / len(right)
                cov = sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right)) / max(1, len(common) - 1)
                cov *= 252
            elif i == j:
                cov = max(0.0004, safe_float(rows[i].get("volatility"), 0.02) ** 2 * 252)
            else:
                cov = 0.0
            covariance[i][j] = covariance[j][i] = cov
    return covariance


def enforce_linear_risk_budget(weights, exposures, limit, caps):
    weights = list(weights)
    for _ in range(len(weights) * 3):
        current = sum(weight * exposure for weight, exposure in zip(weights, exposures))
        if current <= limit + 1e-10:
            break
        high = max((i for i, weight in enumerate(weights) if weight > 1e-12), key=lambda i: exposures[i], default=None)
        low = min((i for i, weight in enumerate(weights) if weight < caps[i] - 1e-12), key=lambda i: exposures[i], default=None)
        if high is None or low is None or exposures[high] <= exposures[low] + 1e-12:
            break
        needed = (current - limit) / (exposures[high] - exposures[low])
        transfer = min(needed, weights[high], caps[low] - weights[low])
        if transfer <= 1e-12:
            break
        weights[high] -= transfer
        weights[low] += transfer
    return weights


def robust_sleeve_allocation(rows, budget, chart_lookup, style_key):
    if not rows or budget <= 0:
        return {}, {}, {}, {}
    priorities = []
    for row in rows:
        annual_vol = max(0.08, safe_float(row.get("volatility"), 0.02) * math.sqrt(252))
        priorities.append(max(0.002, safe_float(row.get("market_return_signal"), 0.50) / annual_vol))
        row["market_priority"] = priorities[-1]
    market_rows = [{**row, "market_priority": priority} for row, priority in zip(rows, priorities)]
    market_weights, caps_by_ticker = bounded_priority_allocation(market_rows, budget, "market_priority")
    caps = [caps_by_ticker[row["ticker"]] for row in rows]
    benchmark = [market_weights[row["ticker"]] for row in rows]
    covariance = historical_return_covariance(rows, chart_lookup)
    parameters = {
        "balanced": {"lambda": 3.0, "kappa": 0.42, "tracking": 0.65, "turnover": 0.0025, "tail_limit": 0.10, "physical_limit": 0.68, "transition_limit": 0.68, "carbon_limit": 0.70},
        "climate_defense": {"lambda": 3.5, "kappa": 0.75, "tracking": 0.55, "turnover": 0.0025, "tail_limit": 0.075, "physical_limit": 0.58, "transition_limit": 0.58, "carbon_limit": 0.55},
        "growth": {"lambda": 2.2, "kappa": 0.28, "tracking": 0.50, "turnover": 0.0020, "tail_limit": 0.12, "physical_limit": 0.72, "transition_limit": 0.72, "carbon_limit": 0.75},
        "low_vol": {"lambda": 5.0, "kappa": 0.48, "tracking": 0.75, "turnover": 0.0025, "tail_limit": 0.085, "physical_limit": 0.62, "transition_limit": 0.62, "carbon_limit": 0.62},
    }[style_key]
    mu = [(safe_float(row.get("market_return_signal"), 0.50) - 0.50) * 0.10 for row in rows]
    scenario_keys = sorted(
        {
            scenario_key
            for row in rows
            for scenario_key in (row.get("scenario_losses") or {})
        }
    )
    scenario_exposures = {
        scenario_key: [safe_float((row.get("scenario_losses") or {}).get(scenario_key), 0.0) for row in rows]
        for scenario_key in scenario_keys
    }
    physical = [safe_float(row.get("physical_risk"), 0.0) for row in rows]
    transition = [safe_float(row.get("transition_risk"), 0.0) for row in rows]
    carbon = [safe_float((row.get("transition_channels") or {}).get("carbon_cost"), 0.0) for row in rows]
    weights = list(benchmark)
    step = 0.18
    for _ in range(320):
        covariance_gradient = [2 * sum(covariance[i][j] * weights[j] for j in range(len(rows))) for i in range(len(rows))]
        worst_scenario = max(
            scenario_keys,
            key=lambda key: sum(weights[i] * scenario_exposures[key][i] for i in range(len(rows))),
            default=None,
        )
        worst_loss_gradient = scenario_exposures.get(worst_scenario, [0.0] * len(rows))
        active_weights = [weights[i] - benchmark[i] for i in range(len(rows))]
        tracking_gradient = [
            2 * sum(covariance[i][j] * active_weights[j] for j in range(len(rows)))
            for i in range(len(rows))
        ]
        gradient = []
        for i in range(len(rows)):
            turnover_direction = 0.0 if abs(weights[i] - benchmark[i]) < 1e-10 else (1.0 if weights[i] > benchmark[i] else -1.0)
            gradient.append(
                mu[i]
                - parameters["lambda"] * covariance_gradient[i]
                - parameters["kappa"] * worst_loss_gradient[i]
                - 0.035 * physical[i]
                - 0.035 * transition[i]
                - parameters["tracking"] * tracking_gradient[i]
                - parameters["turnover"] * turnover_direction
            )
        proposal = [weights[i] + step * gradient[i] for i in range(len(rows))]
        updated = project_capped_simplex(proposal, budget, caps)
        if max(abs(updated[i] - weights[i]) for i in range(len(rows))) < 1e-9:
            weights = updated
            break
        weights = updated
    for _ in range(3):
        worst_scenario = max(
            scenario_keys,
            key=lambda key: sum(weights[i] * scenario_exposures[key][i] for i in range(len(rows))),
            default=None,
        )
        if worst_scenario is not None:
            weights = enforce_linear_risk_budget(
                weights,
                scenario_exposures[worst_scenario],
                parameters["tail_limit"] * budget,
                caps,
            )
        weights = enforce_linear_risk_budget(weights, physical, parameters["physical_limit"] * budget, caps)
        weights = enforce_linear_risk_budget(weights, transition, parameters["transition_limit"] * budget, caps)
        weights = enforce_linear_risk_budget(weights, carbon, parameters["carbon_limit"] * budget, caps)
    target = {row["ticker"]: weight for row, weight in zip(rows, weights)}
    diagnostics = {
        "objective": "max mu'w - lambda w'Sigma w - kappa max_s L_s(w) - eta (w-w_market)'Sigma(w-w_market) - tau ||w-w_market||_1",
        "scenario_gradient_rule": "At each iteration, identify argmax_s sum_i(w_i * conditional_loss_i,s) and use that scenario's loss vector as the subgradient.",
        "conditional_scenarios": scenario_keys,
        "covariance_observations": "Up to 252 aligned daily returns; diagonal fallback when coverage is insufficient",
        **parameters,
    }
    return target, market_weights, caps_by_ticker, diagnostics


def issuer_tactical_event_risk(ticker, sector, daily_signal):
    profile = issuer_hazard_exposure_profile(ticker, sector)
    event_pressure = clamp(safe_float(daily_signal.get("daily_pressure"), 0.0), 0.0, 1.0)
    categories = daily_signal.get("category_intensity", {}) or {}
    contributions = {}
    for hazard in HAZARD_CATEGORIES:
        hazard_profile = profile["hazards"][hazard]
        intensity = event_pressure * safe_float(categories.get(hazard), 0.0)
        contributions[hazard] = physical_event_loss(
            intensity,
            hazard_profile["exposure"],
            hazard_profile["vulnerability"],
            hazard_profile["resilience"],
        )
    return {
        "risk": round(clamp(sum(contributions.values()), 0.0, 1.0), 4),
        "top_hazard": max(contributions, key=contributions.get, default="-"),
        "contributions": {key: round(value, 4) for key, value in contributions.items()},
        "data_quality": profile["data_quality"],
    }


def apply_zero_sum_tactical_overlay(rows, strategic_weights, effective_caps, sleeve_budgets):
    final_weights = dict(strategic_weights)
    overlays = {row["ticker"]: 0.0 for row in rows}
    for asset_type in ("ETF", "Stock"):
        group = [row for row in rows if row["asset_type"] == asset_type]
        budget = safe_float(sleeve_budgets.get(asset_type), 0.0)
        if not group or budget <= 0:
            continue
        raw_signals = [
            0.55 * (safe_float(row.get("tactical_market_score"), 0.50) - 0.50)
            - 0.45 * safe_float(row.get("tactical_event_risk"), 0.0)
            for row in group
        ]
        mean_signal = sum(raw_signals) / len(raw_signals)
        centered = [value - mean_signal for value in raw_signals]
        max_abs = max((abs(value) for value in centered), default=0.0)
        if max_abs <= 1e-12:
            continue
        proposed = [
            safe_float(strategic_weights.get(row["ticker"]), 0.0)
            + (TACTICAL_OVERLAY_LIMIT_BPS / 10_000) * centered[index] / max_abs
            for index, row in enumerate(group)
        ]
        caps = [safe_float(effective_caps.get(row["ticker"]), 1.0) for row in group]
        projected = project_capped_simplex(proposed, budget, caps)
        for row, weight in zip(group, projected):
            ticker = row["ticker"]
            final_weights[ticker] = weight
            overlays[ticker] = weight - safe_float(strategic_weights.get(ticker), 0.0)
    return final_weights, overlays


def enforce_sector_cap(weights, rows, caps, max_sector_weight=0.35):
    weights = dict(weights)
    row_lookup = {row["ticker"]: row for row in rows}
    for _ in range(len(rows) * 4):
        sector_weights = {}
        for ticker, weight in weights.items():
            sector = row_lookup[ticker].get("sector", "Unclassified")
            sector_weights[sector] = sector_weights.get(sector, 0.0) + weight
        over_sector = max(sector_weights, key=sector_weights.get, default=None)
        if over_sector is None or sector_weights[over_sector] <= max_sector_weight + 1e-10:
            break
        donors = [ticker for ticker in weights if row_lookup[ticker].get("sector") == over_sector and weights[ticker] > 1e-12]
        receivers = [
            ticker for ticker in weights
            if row_lookup[ticker].get("sector") != over_sector
            and weights[ticker] < safe_float(caps.get(ticker), 1.0) - 1e-12
            and sector_weights.get(row_lookup[ticker].get("sector"), 0.0) < max_sector_weight - 1e-12
        ]
        if not donors or not receivers:
            break
        donor = max(donors, key=lambda ticker: weights[ticker])
        receiver = min(receivers, key=lambda ticker: safe_float(row_lookup[ticker].get("scenario_tail_proxy"), 0.0))
        receiver_sector = row_lookup[receiver].get("sector")
        transfer = min(
            sector_weights[over_sector] - max_sector_weight,
            weights[donor],
            safe_float(caps.get(receiver), 1.0) - weights[receiver],
            max_sector_weight - sector_weights.get(receiver_sector, 0.0),
        )
        if transfer <= 1e-12:
            break
        weights[donor] -= transfer
        weights[receiver] += transfer
    return weights


def reconcile_display_weights(rows, weight_key, total=1.0, decimals=6, cap_key=None):
    if not rows:
        return
    unit = 10 ** (-decimals)
    residual = round(safe_float(total, 1.0) - sum(safe_float(row.get(weight_key), 0.0) for row in rows), decimals)
    if abs(residual) < unit / 2:
        return
    if residual > 0:
        candidates = sorted(
            rows,
            key=lambda row: safe_float(row.get(cap_key), 1.0) - safe_float(row.get(weight_key), 0.0)
            if cap_key
            else 1.0 - safe_float(row.get(weight_key), 0.0),
            reverse=True,
        )
    else:
        candidates = sorted(rows, key=lambda row: safe_float(row.get(weight_key), 0.0), reverse=True)
    for row in candidates:
        current = safe_float(row.get(weight_key), 0.0)
        lower_room = current
        upper_room = safe_float(row.get(cap_key), 1.0) - current if cap_key else 1.0 - current
        if (residual > 0 and upper_room + 1e-12 >= residual) or (residual < 0 and lower_room + 1e-12 >= -residual):
            row[weight_key] = round(current + residual, decimals)
            return


def portfolio_optimizer_payload(mode="etf_stock", capital=None, horizon="long", style="balanced", etfs="", stocks=""):
    mode = optimizer_mode(mode)
    horizon = optimizer_horizon(horizon)
    style_key = optimizer_style(style)
    profile = OPTIMIZER_STYLES[style_key]
    capital_value = clamp(safe_float(capital, DEFAULT_PORTFOLIO_VALUE), 10_000, 5_000_000_000)
    daily_signal = load_daily_climate_signal()
    auto_etfs, auto_stocks = automatic_optimizer_universe(daily_signal, tactical=horizon == "short")
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

    # Both modes start from a strategic one-year daily history. Short-term mode
    # then adds a separate 1-20 trading-day event/market overlay.
    market_period = "1y"
    market_interval = "1d"
    market_symbols = list(symbols)
    if "SPY" not in market_symbols:
        market_symbols.append("SPY")
    market = market_chart_payload(market_symbols, period=market_period, interval=market_interval)
    chart_lookup = market.get("charts", {})
    climate_context = climate_data_context()
    climate_state = climate_state_variables(daily_signal=daily_signal, context=climate_context)
    if horizon == "long":
        structural_confidence = 0.95 if "official" in str(climate_context.get("source_mode", "")).lower() else 0.55
        climate_state = {**climate_state, "data_confidence": structural_confidence}

    daily_pressure = safe_float(daily_signal.get("allocation_pressure"), 0.0)
    chronic_physical = clamp(
        0.50 * clamp((safe_float(climate_context.get("current_warming"), CURRENT_WARMING_C) - 0.75) / 0.85, 0, 1)
        + 0.50 * clamp((safe_float(climate_context.get("disaster_10y_avg"), 15) - 8) / 20, 0, 1),
        0.0,
        1.0,
    )
    rows = []
    for symbol in symbols:
        strategic_rows = chart_lookup.get(symbol, [])
        tactical_rows = strategic_rows[-21:]
        stats = market_stats(strategic_rows)
        tactical_stats = market_stats(tactical_rows)
        last_price = stats["last"]
        short_term = horizon == "short"
        momentum_raw = stats["period_return"] * 1.8 + stats["last_return"] * 4.0
        momentum_score = clamp(0.50 + momentum_raw, 0.03, 0.97)
        tactical_momentum_raw = tactical_stats["period_return"] * 5.0 + tactical_stats["last_return"] * 8.0
        tactical_momentum_score = clamp(0.50 + tactical_momentum_raw, 0.03, 0.97)
        vol_limit = 0.035
        risk_score = clamp(1 - stats["volatility"] / max(vol_limit, 1e-6), 0.03, 0.97)
        liquidity_score = clamp(math.log1p(stats["avg_volume"]) / math.log1p(60_000_000), 0.05, 0.98)
        market_score = clamp(0.55 * momentum_score + 0.25 * liquidity_score + 0.20 * risk_score, 0.03, 0.97)
        tactical_risk_score = clamp(1 - tactical_stats["volatility"] / 0.035, 0.03, 0.97)
        tactical_market_score = clamp(0.70 * tactical_momentum_score + 0.30 * tactical_risk_score, 0.03, 0.97)

        if symbol in stock_symbols:
            asset_type = "Stock"
            sector = normalize_model_sector(guess_sector(symbol))
            climate_risk = COMPANY_SECTOR_SENSITIVITY.get(sector, 0.50)
            climate_score = clamp(1 - climate_risk, 0.05, 0.95)
            rationale = (
                f"{sector}; sector exposure mapped through the same conditional scenario engine; "
                f"12M strategic trend {stats['period_return']:.2%}."
            )
        else:
            asset_type = "ETF"
            sector, climate_risk, note = etf_climate_profile(symbol)
            sector = normalize_model_sector(sector)
            climate_score = clamp(1 - climate_risk, 0.05, 0.95)
            rationale = f"{sector}; {note} 12M strategic trend {stats['period_return']:.2%}."

        observed_beta = realized_market_beta(strategic_rows, chart_lookup.get("SPY", []))
        valuation = valuation_assumptions(symbol, sector, observed_beta=observed_beta)
        holding_tail = holding_scenario_tail_proxy(symbol, sector, horizon=2050, observed_beta=observed_beta)
        scenario_tail_proxy = safe_float(holding_tail.get("loss_rate"), 0.0)
        transition = sector_transition_profile(sector)
        exposure = issuer_exposure_model(symbol, asset_type, sector, climate_risk, transition, climate_state, stats)
        tactical_event = issuer_tactical_event_risk(symbol, sector, daily_signal)
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
        market_return_signal = clamp(0.40 * momentum_score + 0.25 * liquidity_score + 0.20 * risk_score + 0.15 * market_score, 0.02, 0.98)
        climate_risk_indicator = clamp(
            0.42 * exposure["opportunity"]
            + 0.22 * exposure["resilience"]
            - 0.20 * physical_risk
            - 0.16 * transition_risk
            + 0.10 * exposure["data_confidence"],
            -0.45,
            0.65,
        )
        risk_penalty = clamp(0.52 * (1 - risk_score) + 0.28 * stats["volatility"] / max(vol_limit, 1e-6) + 0.20 * (1 - exposure["data_confidence"]), 0.0, 0.95)
        worst_scenario_loss = safe_float(holding_tail.get("worst_loss_rate"), scenario_tail_proxy)
        scenario_worst_penalty = clamp(worst_scenario_loss, 0.0, 1.0)
        theta_regime = clamp(0.35 + 0.35 * climate_state["chronic_climate_state"], 0.20, 0.70)
        decision_score = clamp(
            market_return_signal
            - 0.35 * scenario_worst_penalty
            - 0.10 * physical_risk
            - 0.10 * transition_risk
            - 0.08 * risk_penalty,
            0.01,
            0.99,
        )
        transition_channels = exposure.get("transition_channels", {})
        dominant_transition_channel = max(
            (key for key in ("carbon_cost", "demand_shift", "energy_cost", "transition_capex", "pass_through_offset")),
            key=lambda key: abs(safe_float(transition_channels.get(key), 0.0)),
            default="-",
        )
        attribution = (
            f"Market return proxy {market_return_signal:.0%}; climate risk indicator {climate_risk_indicator:+.0%}; "
            f"risk penalty {risk_penalty:.0%}; worst conditional loss {worst_scenario_loss:.2%}; "
            f"transition driver {dominant_transition_channel.replace('_', ' ')}; "
            f"confidence {exposure['data_confidence']:.0%}."
        )
        confidence_cap = clamp(0.055 + 0.13 * exposure["data_confidence"] + (0.06 if asset_type == "ETF" else 0.0), 0.055, 0.20)
        rows.append(
            {
                "ticker": symbol,
                "asset_type": asset_type,
                "sector": sector,
                "last": round(last_price, 4),
                "momentum": round(stats["period_return"], 5),
                "volatility": round(stats["volatility"], 5),
                "market_score": round(market_score, 4),
                "tactical_market_score": round(tactical_market_score, 4),
                "tactical_event_risk": tactical_event["risk"],
                "tactical_top_hazard": tactical_event["top_hazard"],
                "tactical_data_quality": tactical_event["data_quality"],
                "climate_score": round(climate_score, 4),
                "physical_risk": round(physical_risk, 4),
                "transition_risk": round(transition_risk, 4),
                "transition_channels": transition_channels,
                "transition_driver": dominant_transition_channel,
                "transition_data_status": exposure.get("transition_data_status"),
                "valuation": valuation,
                "transition_headline": transition.get("headline"),
                "market_return_signal": round(market_return_signal, 4),
                "climate_risk_indicator": round(climate_risk_indicator, 4),
                "risk_penalty": round(risk_penalty, 4),
                "scenario_worst_penalty": round(scenario_worst_penalty, 4),
                "theta_regime": round(theta_regime, 4),
                "data_confidence": exposure["data_confidence"],
                "confidence_cap": round(confidence_cap, 4),
                "issuer_sensitivity": exposure["sensitivity"],
                "resilience": exposure["resilience"],
                "opportunity": exposure["opportunity"],
                "risk_score": round(risk_score, 4),
                "total_score": round(decision_score, 4),
                "scenario_tail_proxy": round(scenario_tail_proxy, 4),
                "worst_scenario_loss": round(worst_scenario_loss, 4),
                "worst_scenario": holding_tail.get("worst_scenario"),
                "scenario_losses": holding_tail.get("scenario_losses", {}),
                "scenario_tail_scenarios": holding_tail.get("scenarios", []),
                "scenario_tail_definition": holding_tail.get("definition"),
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

    target_weights = {}
    market_only_weights = {}
    effective_caps = {}
    solver_diagnostics = {}
    for asset_type in ["ETF", "Stock"]:
        group = [row for row in rows if row["asset_type"] == asset_type]
        sleeve_weight = sleeves.get(asset_type, 0.0)
        if not group or sleeve_weight <= 0:
            continue
        group_target, group_market, group_caps, group_diagnostics = robust_sleeve_allocation(
            group,
            sleeve_weight,
            chart_lookup,
            style_key,
        )
        target_weights.update(group_target)
        market_only_weights.update(group_market)
        effective_caps.update(group_caps)
        solver_diagnostics[asset_type] = group_diagnostics

    target_weights = enforce_sector_cap(target_weights, rows, effective_caps, max_sector_weight=0.35)
    strategic_weights = dict(target_weights)
    tactical_overlays = {row["ticker"]: 0.0 for row in rows}
    if horizon == "short":
        target_weights, tactical_overlays = apply_zero_sum_tactical_overlay(
            rows,
            strategic_weights,
            effective_caps,
            sleeves,
        )
        target_weights = enforce_sector_cap(target_weights, rows, effective_caps, max_sector_weight=0.35)
        tactical_overlays = {
            ticker: target_weights.get(ticker, 0.0) - strategic_weights.get(ticker, 0.0)
            for ticker in target_weights
        }

    for row in rows:
        ticker = row["ticker"]
        weight = safe_float(target_weights.get(ticker), 0.0)
        market_only_weight = safe_float(market_only_weights.get(ticker), 0.0)
        row["allocation_priority"] = round(row.pop("market_priority", row.pop("raw_weight", 0.0)), 6)
        row["effective_cap"] = round(safe_float(effective_caps.get(ticker), row.get("confidence_cap", 1.0)), 6)
        row["cap_relaxed_for_feasibility"] = row["effective_cap"] > safe_float(row.get("confidence_cap"), 1.0) + 1e-10
        row["target_weight"] = round(weight, 6)
        row["strategic_weight"] = round(safe_float(strategic_weights.get(ticker), weight), 6)
        row["tactical_overlay"] = round(safe_float(tactical_overlays.get(ticker), 0.0), 6)
        row["tactical_overlay_bps"] = round(safe_float(tactical_overlays.get(ticker), 0.0) * 10_000, 1)
        row["target_dollars"] = round(row["target_weight"] * capital_value, 2)
        row["estimated_shares"] = round(row["target_dollars"] / row["last"], 2) if row["last"] else 0
        row["market_only_weight"] = round(market_only_weight, 6)
        row["climate_weight_delta"] = round(row["target_weight"] - market_only_weight, 6)
        row["action"] = allocation_signal(row["total_score"], row["climate_score"], row["risk_score"], weight)

    reconcile_display_weights(rows, "target_weight", total=1.0, decimals=6, cap_key="effective_cap")
    reconcile_display_weights(rows, "market_only_weight", total=1.0, decimals=6, cap_key="effective_cap")
    for row in rows:
        row["target_dollars"] = round(row["target_weight"] * capital_value, 2)
        row["estimated_shares"] = round(row["target_dollars"] / row["last"], 2) if row["last"] else 0
        row["climate_weight_delta"] = round(row["target_weight"] - row["market_only_weight"], 6)

    rows = sorted(rows, key=lambda r: r.get("target_weight", 0.0), reverse=True)

    weights = [safe_float(row.get("target_weight"), 0.0) for row in rows]
    hhi = sum(weight * weight for weight in weights)
    sector_weights = {}
    for row in rows:
        sector_name = row.get("sector") or "Unclassified"
        sector_weights[sector_name] = sector_weights.get(sector_name, 0.0) + safe_float(row.get("target_weight"), 0.0)
    top_sector, top_sector_weight = max(sector_weights.items(), key=lambda item: item[1], default=("-", 0.0))
    top_risk_row = max(
        rows,
        key=lambda row: safe_float(row.get("target_weight"), 0.0) * safe_float(row.get("scenario_tail_proxy"), 0.0),
        default={},
    )
    top_overweight = max(rows, key=lambda row: safe_float(row.get("climate_weight_delta"), 0.0), default={})
    top_underweight = min(rows, key=lambda row: safe_float(row.get("climate_weight_delta"), 0.0), default={})
    weighted_tail_proxy = sum(
        safe_float(row.get("target_weight"), 0.0) * safe_float(row.get("scenario_tail_proxy"), 0.0) for row in rows
    )
    portfolio_scenario_losses = {
        scenario_key: sum(
            safe_float(row.get("target_weight"), 0.0)
            * safe_float((row.get("scenario_losses") or {}).get(scenario_key), 0.0)
            for row in rows
        )
        for scenario_key in sorted(
            {key for row in rows for key in (row.get("scenario_losses") or {})}
        )
    }
    worst_portfolio_scenario, worst_portfolio_scenario_loss = max(
        portfolio_scenario_losses.items(),
        key=lambda item: item[1],
        default=("-", 0.0),
    )
    weighted_physical = sum(
        safe_float(row.get("target_weight"), 0.0) * safe_float(row.get("physical_risk"), 0.0) for row in rows
    )
    weighted_transition = sum(
        safe_float(row.get("target_weight"), 0.0) * safe_float(row.get("transition_risk"), 0.0) for row in rows
    )
    weighted_carbon = sum(
        safe_float(row.get("target_weight"), 0.0)
        * safe_float((row.get("transition_channels") or {}).get("carbon_cost"), 0.0)
        for row in rows
    )
    weighted_confidence = sum(
        safe_float(row.get("target_weight"), 0.0) * safe_float(row.get("data_confidence"), 0.0) for row in rows
    )
    weighted_climate_indicator = sum(
        safe_float(row.get("target_weight"), 0.0) * safe_float(row.get("climate_risk_indicator"), 0.0) for row in rows
    )
    climate_active_share = 0.5 * sum(abs(safe_float(row.get("climate_weight_delta"), 0.0)) for row in rows)
    turnover_vs_market = climate_active_share
    full_covariance = historical_return_covariance(rows, chart_lookup)
    active_weights = [safe_float(row.get("climate_weight_delta"), 0.0) for row in rows]
    tracking_variance = sum(
        active_weights[i] * full_covariance[i][j] * active_weights[j]
        for i in range(len(rows))
        for j in range(len(rows))
    )
    tracking_error = math.sqrt(max(0.0, tracking_variance))
    tactical_overlay_sum = sum(safe_float(row.get("tactical_overlay"), 0.0) for row in rows)
    max_position = max(weights, default=0.0)
    effective_positions = 1 / hhi if hhi > 0 else 0.0
    weight_sum = sum(weights)
    market_weight_sum = sum(safe_float(row.get("market_only_weight"), 0.0) for row in rows)
    cap_breaches = sum(
        1
        for row in rows
        if safe_float(row.get("target_weight"), 0.0) > safe_float(row.get("effective_cap"), 1.0) + 1e-8
    )
    relaxed_caps = sum(1 for row in rows if row.get("cap_relaxed_for_feasibility"))
    solver_limits = next(iter(solver_diagnostics.values()), {})
    scenario_loss_limit = safe_float(solver_limits.get("tail_limit"), 0.10)
    physical_limit = safe_float(solver_limits.get("physical_limit"), 0.68)
    transition_limit = safe_float(solver_limits.get("transition_limit"), 0.68)
    carbon_limit = safe_float(solver_limits.get("carbon_limit"), 0.70)
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
            "interpretation": "Weight-averaged mean of each holding's two worst conditional target-versus-baseline losses; no probability claim.",
        },
        {
            "name": "Worst conditional portfolio loss",
            "value": round(worst_portfolio_scenario_loss, 4),
            "limit": round(scenario_loss_limit, 4),
            "status": "Pass" if worst_portfolio_scenario_loss <= scenario_loss_limit + 1e-8 else "Watch",
            "interpretation": f"Maximum portfolio loss across the disclosed scenario set; active scenario {worst_portfolio_scenario}.",
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
        {
            "name": "Allocation reconciliation",
            "value": round(weight_sum, 6),
            "limit": 1.0,
            "status": "Pass" if abs(weight_sum - 1.0) <= 1e-5 and cap_breaches == 0 else "Watch",
            "interpretation": f"Weights sum to one with zero effective-cap breaches; {relaxed_caps} cap(s) relaxed only when required for sleeve feasibility.",
        },
        {
            "name": "Sector concentration",
            "value": round(top_sector_weight, 4),
            "limit": 0.35,
            "status": "Pass" if top_sector_weight <= 0.35 + 1e-8 else "Watch",
            "interpretation": "Hard transfer constraint applied after sleeve optimization.",
        },
        {
            "name": "Tracking error",
            "value": round(tracking_error, 4),
            "limit": 0.08,
            "status": "Pass" if tracking_error <= 0.08 else "Watch",
            "interpretation": "Annualized covariance-based active risk versus the market-only allocation.",
        },
        {
            "name": "Physical-risk budget",
            "value": round(weighted_physical, 4),
            "limit": round(physical_limit, 4),
            "status": "Pass" if weighted_physical <= physical_limit + 1e-8 else "Watch",
            "interpretation": "Portfolio-weighted structural physical pressure; live NWS alerts are excluded from the strategic budget.",
        },
        {
            "name": "Transition-risk budget",
            "value": round(weighted_transition, 4),
            "limit": round(transition_limit, 4),
            "status": "Pass" if weighted_transition <= transition_limit + 1e-8 else "Watch",
            "interpretation": "Portfolio-weighted transition cash-flow pressure; atmospheric CO2 concentration is excluded.",
        },
        {
            "name": "Carbon-cost exposure",
            "value": round(weighted_carbon, 4),
            "limit": round(carbon_limit, 4),
            "status": "Pass" if weighted_carbon <= carbon_limit + 1e-8 else "Watch",
            "interpretation": "Portfolio-weighted carbon-cost channel; not atmospheric CO2 concentration.",
        },
        {
            "name": "Tactical zero-sum overlay",
            "value": round(abs(tactical_overlay_sum), 6),
            "limit": 0.0001,
            "status": "Pass" if abs(tactical_overlay_sum) <= 0.0001 else "Watch",
            "interpretation": "Short-term event tilts must fund themselves around strategic weights.",
        },
    ]
    if weighted_tail_proxy >= 0.08 or max_position > 0.20:
        posture = "Defensive tilt"
        strategic_action = "Reduce the largest tail-risk contributor before adding climate opportunity exposure."
    elif climate_active_share >= 0.03:
        posture = "Climate-risk constrained"
        strategic_action = "Maintain market expected-return inputs while funding lower-risk holdings from higher conditional-loss exposures."
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
            "portfolio_scenario_losses": {key: round(value, 4) for key, value in portfolio_scenario_losses.items()},
            "worst_portfolio_scenario": worst_portfolio_scenario,
            "worst_portfolio_scenario_loss": round(worst_portfolio_scenario_loss, 4),
            "weighted_physical_risk": round(weighted_physical, 4),
            "weighted_transition_risk": round(weighted_transition, 4),
            "weighted_carbon_cost": round(weighted_carbon, 4),
            "weighted_climate_risk_indicator": round(weighted_climate_indicator, 4),
            "weighted_confidence": round(weighted_confidence, 4),
            "weight_sum": round(weight_sum, 6),
            "market_only_weight_sum": round(market_weight_sum, 6),
            "effective_cap_breaches": cap_breaches,
            "feasibility_cap_relaxations": relaxed_caps,
            "largest_risk_contributor": top_risk_row.get("ticker", "-"),
            "largest_climate_overweight": top_overweight.get("ticker", "-"),
            "largest_climate_overweight_delta": round(safe_float(top_overweight.get("climate_weight_delta"), 0.0), 4),
            "largest_climate_underweight": top_underweight.get("ticker", "-"),
            "largest_climate_underweight_delta": round(safe_float(top_underweight.get("climate_weight_delta"), 0.0), 4),
            "tracking_error": round(tracking_error, 4),
            "turnover_vs_market": round(turnover_vs_market, 4),
            "tactical_overlay_sum": round(tactical_overlay_sum, 6),
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
            "market_only_ablation": "Each row includes a market-only implied weight so the client can isolate the allocation effect of climate inputs.",
            "walk_forward_note": "True out-of-sample validation should rebalance historically using only information available before each rebalance date.",
        },
        "methodology": {
            "model": "Covariance-aware robust climate risk optimizer",
            "objective": "Maximize market expected-return proxy minus annualized covariance risk, the portfolio's worst conditional scenario loss, covariance tracking error, and active-share turnover proxy. Climate variables enter as risk penalties and hard budgets, not unvalidated alpha.",
            "formula": "max mu'w - lambda w'Sigma w - kappa max_s L_s(w) - eta (w-w_market)'Sigma(w-w_market) - tau ||w-w_market||_1",
            "risk": "Physical, transition, carbon-cost, and scenario-tail exposures are separate linear budgets; covariance uses up to 252 aligned daily observations.",
            "constraint": "Weights sum to one with single-name, confidence, sector, physical, transition, carbon, and tail constraints. Short-term overlays are zero-sum and capped at 250 bps per security.",
            "ablation": "The market-only book uses the same sleeves and caps; climate active share and tracking error isolate the allocation effect of climate risk.",
            "solver": solver_diagnostics,
        },
        "market_source": market["source"],
        "market_period": market["period"],
        "market_interval": market["interval"],
        "holding_note": (
            "Short-term mode starts from the strategic one-year allocation, then applies a separate 1-20 trading-day NWS/market overlay."
            if horizon == "short"
            else "Long-term mode uses one-year market evidence, 5-30 year target-versus-reference valuation, and no live NWS weight change."
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
    if not short_term_hazard_is_calculable(daily_signal):
        return [
            {
                "driver": "unavailable",
                "driver_label": "Live NWS hazard data unavailable",
                "count": None,
                "intensity": None,
                "reminder": "Not calculable; no tactical climate trade is permitted.",
                "sample_area": "-",
            }
        ]
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
                "driver": "observed_zero",
                "driver_label": "No matched active NWS hazards",
                "count": 0,
                "intensity": 0.0,
                "reminder": "Observed zero from a successful NWS response; no tactical climate trade.",
                "sample_area": "-",
            }
        )
    return sorted(rows, key=lambda r: (r["intensity"], r["count"]), reverse=True)


def daily_climate_board_payload():
    daily_signal = load_daily_climate_signal()
    alert_rows = daily_climate_alert_rows(daily_signal)
    active_themes = [r["driver_label"] for r in alert_rows[:4]]
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source_mode": daily_signal.get("source_mode", "-"),
        "source_url": daily_signal.get("source_url", NWS_ACTIVE_ALERTS_URL),
        "alerts_total": daily_signal.get("alerts_total"),
        "climate_alerts": daily_signal.get("climate_alerts"),
        "top_driver": daily_signal.get("top_driver", "unavailable"),
        "daily_pressure": daily_signal.get("daily_pressure"),
        "allocation_pressure": daily_signal.get("allocation_pressure"),
        "is_calculable": short_term_hazard_is_calculable(daily_signal),
        "observed_zero": bool(daily_signal.get("observed_zero")),
        "decision_status": daily_signal.get("decision_status", "-"),
        "active_themes": active_themes,
        "daily_alerts": alert_rows,
    }


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
    source = "market data unavailable"
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

    covered = sum(1 for values in prices.values() if len(values) >= 80)
    if covered:
        source = f"{source} | {covered}/{len(symbols)} securities with at least 80 observations"
    return prices, source


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
        climate_resilience_raw = 0.52 + stance_bias + 0.34 * event_beta + 0.18 * opportunity - 0.12 * transition_risk
    elif stance == "hedge":
        climate_resilience_raw = 0.50 + stance_bias + 0.24 * event_beta + 0.08 * risk_score - 0.08 * transition_risk
    elif stance == "risk":
        climate_resilience_raw = 0.50 + stance_bias - 0.32 * event_beta - 0.18 * transition_risk - 0.10 * physical_sensitivity * climate_pressure
    else:
        climate_resilience_raw = 0.50 + stance_bias + 0.10 * event_beta + 0.12 * opportunity - 0.12 * transition_risk - 0.06 * physical_sensitivity * climate_pressure
    climate_resilience = clamp(
        climate_resilience_raw
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
    previous_market_positions = {}
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
        market_ranked = sorted(
            scored,
            key=lambda row: 0.72 * safe_float(row.get("market_score"), 0.50) + 0.28 * safe_float(row.get("risk_score"), 0.50),
            reverse=True,
        )
        market_buys = market_ranked[:buy_count]
        market_buy_set = {item["ticker"] for item in market_buys}
        market_sells = [item for item in reversed(market_ranked) if item["ticker"] not in market_buy_set][:sell_count]
        buy_symbols = [p["ticker"] for p in buys]
        sell_symbols = [p["ticker"] for p in sells]
        buy_returns = [next_returns[s] for s in buy_symbols if s in next_returns]
        sell_returns = [next_returns[s] for s in sell_symbols if s in next_returns]
        bench_returns = [next_returns[s] for s in available if s in next_returns]
        if not buy_returns or not sell_returns or not bench_returns:
            continue
        long_book = sum(buy_returns) / len(buy_returns)
        sell_book = sum(sell_returns) / len(sell_returns)
        unscaled_benchmark_return = sum(bench_returns) / len(bench_returns)
        benchmark_exposure = 0.75
        cash_weight = 0.25
        benchmark_return = benchmark_exposure * unscaled_benchmark_return
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

        market_buy_symbols = [item["ticker"] for item in market_buys]
        market_sell_symbols = [item["ticker"] for item in market_sells]
        market_long_book = sum(next_returns[symbol] for symbol in market_buy_symbols) / len(market_buy_symbols)
        market_short_book = sum(next_returns[symbol] for symbol in market_sell_symbols) / len(market_sell_symbols)
        gross_market_only_return = market_long_book - 0.25 * market_short_book
        market_positions = {symbol: 1.0 / len(market_buy_symbols) for symbol in market_buy_symbols}
        for symbol in market_sell_symbols:
            market_positions[symbol] = market_positions.get(symbol, 0.0) - 0.25 / len(market_sell_symbols)
        market_traded_notional = sum(
            abs(market_positions.get(symbol, 0.0) - previous_market_positions.get(symbol, 0.0))
            for symbol in set(market_positions) | set(previous_market_positions)
        )
        market_short_notional = sum(abs(weight) for weight in market_positions.values() if weight < 0)
        market_only_cost = market_traded_notional * trading_cost_rate + market_short_notional * daily_borrow_rate
        market_only_return = gross_market_only_return - market_only_cost
        previous_market_positions = market_positions
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
                "market_only_return": round(market_only_return, 5),
                "gross_market_only_return": round(gross_market_only_return, 5),
                "incremental_climate_return": round(signal_return - market_only_return, 5),
                "unscaled_benchmark_return": round(unscaled_benchmark_return, 5),
                "benchmark_exposure": benchmark_exposure,
                "cash_weight": cash_weight,
                "return_difference": round(signal_return - benchmark_return, 5),
                "gross_return_difference": round(gross_signal_return - benchmark_return, 5),
                "long_book_return": round(long_book, 5),
                "sell_book_return": round(sell_book, 5),
                "turnover": round(turnover, 5),
                "traded_notional": round(traded_notional, 5),
                "transaction_cost": round(transaction_cost, 6),
                "borrow_cost": round(borrow_cost, 6),
                "total_cost": round(total_cost, 6),
                "market_only_cost": round(market_only_cost, 6),
                "gross_exposure": round(sum(abs(weight) for weight in positions.values()), 4),
                "net_exposure": round(sum(positions.values()), 4),
                "picks": ", ".join(buy_symbols),
                "sells": ", ".join(sell_symbols),
                "market_only_picks": ", ".join(market_buy_symbols),
                "market_only_sells": ", ".join(market_sell_symbols),
                "top_drivers": f"Buy {', '.join(buy_symbols[:3])}; Sell {', '.join(sell_symbols[:3])}",
                "pick_details": pick_details,
                "coverage": f"{len(available)} / {len(symbols)}",
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


def block_bootstrap_total_return_ci(returns, samples=1000, block_size=5, seed=42):
    values = [safe_float(value, 0.0) for value in returns]
    if len(values) < 8:
        return {"lower": None, "median": None, "upper": None, "samples": 0, "block_size": block_size}
    rng = random.Random(seed)
    totals = []
    for _ in range(samples):
        draw = []
        while len(draw) < len(values):
            start = rng.randrange(0, len(values))
            draw.extend(values[(start + offset) % len(values)] for offset in range(block_size))
        wealth = 1.0
        for value in draw[: len(values)]:
            wealth *= 1 + value
        totals.append(wealth - 1)
    totals.sort()
    return {
        "lower": round(percentile(totals, 0.025), 4),
        "median": round(percentile(totals, 0.50), 4),
        "upper": round(percentile(totals, 0.975), 4),
        "samples": samples,
        "block_size": block_size,
    }


def sign_permutation_p_value(returns, samples=2000, seed=43):
    values = [safe_float(value, 0.0) for value in returns]
    if len(values) < 8:
        return None
    observed = abs(sum(values) / len(values))
    rng = random.Random(seed)
    exceed = 0
    for _ in range(samples):
        permuted = abs(sum(value if rng.random() >= 0.5 else -value for value in values) / len(values))
        if permuted >= observed - 1e-15:
            exceed += 1
    return round((exceed + 1) / (samples + 1), 4)


def summarize_daily_recommendation_window(rows, window_days, label):
    subset = rows[-window_days:] if len(rows) > window_days else list(rows)
    model_wealth = 1.0
    gross_model_wealth = 1.0
    bench_wealth = 1.0
    market_only_wealth = 1.0
    out_rows = []
    for row in subset:
        model_ret = safe_float(row.get("recommended_return"), 0.0)
        gross_model_ret = safe_float(row.get("gross_recommended_return"), model_ret)
        bench_ret = safe_float(row.get("benchmark_return"), 0.0)
        market_only_ret = safe_float(row.get("market_only_return"), bench_ret)
        model_wealth *= 1 + model_ret
        gross_model_wealth *= 1 + gross_model_ret
        bench_wealth *= 1 + bench_ret
        market_only_wealth *= 1 + market_only_ret
        out = dict(row)
        out["recommended_wealth"] = round(model_wealth, 4)
        out["gross_recommended_wealth"] = round(gross_model_wealth, 4)
        out["benchmark_wealth"] = round(bench_wealth, 4)
        out["market_only_wealth"] = round(market_only_wealth, 4)
        out_rows.append(out)
    returns = [safe_float(r.get("recommended_return"), 0.0) for r in out_rows]
    bench_returns = [safe_float(r.get("benchmark_return"), 0.0) for r in out_rows]
    market_only_returns = [safe_float(r.get("market_only_return"), 0.0) for r in out_rows]
    incremental_returns = [model - market for model, market in zip(returns, market_only_returns)]
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
    bootstrap_ci = block_bootstrap_total_return_ci(incremental_returns)
    permutation_p = sign_permutation_p_value(incremental_returns)
    summary = {
        "label": label,
        "trading_days": days,
        "recommended_total_return": round(model_wealth - 1, 4),
        "gross_recommended_total_return": round(gross_model_wealth - 1, 4),
        "benchmark_total_return": round(bench_wealth - 1, 4),
        "market_only_total_return": round(market_only_wealth - 1, 4),
        "incremental_climate_value": round(model_wealth - market_only_wealth, 4),
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
        "bootstrap_95_ci": bootstrap_ci,
        "permutation_p_value": permutation_p,
        "statistically_significant_5pct": bool(permutation_p is not None and permutation_p < 0.05),
        "return_attribution": {
            "market_only_terminal_wealth": round(market_only_wealth - 1, 4),
            "incremental_climate_terminal_wealth": round(model_wealth - market_only_wealth, 4),
            "modeled_cost_drag": round(gross_model_wealth - model_wealth, 4),
        },
        "latest_picks": out_rows[-1].get("pick_details", []) if out_rows else [],
    }
    return {"summary": summary, "rows": out_rows}


def daily_recommendation_backtest_payload(
    mode=None,
    capital=None,
    horizon=None,
    style=None,
    etfs="",
    stocks="",
    trading_cost_bps=10.0,
    annual_borrow_cost_bps=100.0,
):
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
    covered_securities = sum(1 for values in prices.values() if len(values) >= 80)
    windows = {
        "3w": summarize_daily_recommendation_window(rows, 15, "3 weeks"),
        "3m": summarize_daily_recommendation_window(rows, 63, "3 months"),
        "3y": summarize_daily_recommendation_window(rows, 756, "3 years"),
    }
    return {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": source,
        "data_status": "ready" if rows else "insufficient_history",
        "covered_securities": covered_securities,
        "requested_securities": len(symbols),
        "universe": symbols,
        "backtest_type": "one_step_walk_forward_climate_ablation",
        "validation_quality": {
            "market_features": "Point-in-time by signal date",
            "climate_features": "Latest completed annual vintage with expanding normalization",
            "macro_vintages": "ALFRED integration source-ready; not loaded in this run",
            "historical_event_tape": "Archived NWS/NOAA event tape not reconstructed; no current alert is applied retroactively",
            "universe_history": "Current selected universe replay; survivorship-free constituent history not loaded",
            "claim_level": "Research diagnostic, not production performance",
        },
        "cost_model": {
            "trading_cost_bps": round(clamp(safe_float(trading_cost_bps, 10.0), 0.0, 100.0), 2),
            "annual_borrow_cost_bps": round(clamp(safe_float(annual_borrow_cost_bps, 100.0), 0.0, 2_000.0), 2),
            "return_basis": "Net of modeled trading and borrow costs",
            "turnover_definition": "Half the sum of absolute position-weight changes; costs use full traded notional.",
            "benchmark_definition": "75% equal-weight selected universe plus 25% zero-return cash, matched to the signal portfolio's 75% net risky exposure.",
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
            "model": "One-step walk-forward Climate-on versus Market-only ablation using the optimizer-selected universe.",
            "selection": "For each historical signal date, the model uses prior market observations and the latest completed calendar-year climate vintage, buys the strongest climate-beneficiary/resilience bucket, and shorts the highest climate-vulnerability bucket for the next trading day.",
            "windows": "3 weeks, 3 months, and 3 years are recalculated from daily signal returns; the current portfolio is not used retroactively.",
            "costs": "Net returns deduct the selected trading cost from full traded notional and the selected annualized borrow cost from the 25% short sleeve.",
            "benchmark": "The comparator is exposure matched: 75% equal-weight universe and 25% cash, because the 100% long / 25% short signal has 75% net risky exposure.",
            "ablation": "IncrementalClimateValue = terminal wealth(Climate-on) - terminal wealth(Market-only), with identical assets, exposure, costs, and next-day execution.",
            "statistics": "Five-day moving-block bootstrap reports a 95% interval for incremental climate return; a deterministic sign-permutation test reports the two-sided p-value.",
            "caveat": "The test is a conditional historical replay of today's selected universe, not a survivorship-free constituent history. Annual climate features use expanding-window normalization and a one-year publication lag; a complete archived daily NWS tape is not reconstructed. Slippage, taxes, financing, and market-impact constraints remain excluded.",
        },
        "windows": windows,
    }


def build_allocation_history():
    tickers = list(SECTOR_ETFS.keys())
    climate_rows = climate_signal()
    years = list(range(START_YEAR + 1, datetime.now().year + 1))
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
    return allocation_rows, "official climate vintages; no market-return input"


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


def guess_sector(ticker):
    return resolve_issuer_sector(ticker, requested_sector=None).get("resolved_sector")


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
        "platform": "Jennison Climate-Risk Research Platform",
        "climate_source": "NWS + NASA/NOAA/NCEI official inputs, with FEMA/EPA/EIA/NGFS/SEC source-ready risk mapping",
        "market_source": market_source,
        "methodology": "Target-reference climate scenario repricing plus a separate NWS event-nowcast overlay",
        "scenario_methodology": {
            "scope": "Country -> sector -> issuer -> portfolio",
            "physical_downscaling": "Country acute/chronic losses are scaled by sector vulnerability, then by issuer fixed-asset and labor-intensity ratios.",
            "transition_downscaling": "Transition FCFF separates carbon cost, demand shift, energy cost, transition CapEx, and pass-through. Atmospheric CO2 is excluded from transition scoring.",
            "valuation": "Scenario-conditioned cash flows are discounted into an as-of-date value impact relative to a chosen reference scenario.",
            "probability": "No occurrence probabilities are assigned to NGFS-style scenarios.",
            "short_term": "NWS alerts provide current hazard context only. They do not establish issuer exposure, probability, financial loss, or a portfolio decision.",
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
  <title>Jennison Climate-Risk Research Platform</title>
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
    #allocationTable,#dailyAlertTable,#scenarioTable,#climateDataTable,#dailyImpactTable{min-width:860px}
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
    .model-lab-controls{display:grid;grid-template-columns:1.25fr 1.25fr .7fr 1fr .8fr auto;gap:8px;align-items:end}
    .issuer-demo-strip{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:7px;margin:12px 0 16px}
    .issuer-demo-card{border:1px solid var(--line);background:#fff;border-radius:8px;padding:9px 8px;text-align:left;cursor:pointer;min-height:82px}
    .issuer-demo-card:hover,.issuer-demo-card.active{border-color:var(--blue);box-shadow:0 3px 12px rgba(36,99,235,.12)}
    .issuer-demo-card b{display:block;font-size:14px;color:#173d7a}.issuer-demo-card span{display:block;font-size:10px;color:var(--muted);margin-top:3px}
    #summary-section,#climate-data-section{display:none!important}
    a[href="#climate-data-section"]{display:none!important}
    .lab-split{grid-template-columns:1fr!important}
    .model-lab-controls label{margin-bottom:4px}
    .model-lab-controls button{height:36px;white-space:nowrap}
    .method-flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid #dbe3ef;border-radius:8px;background:#f8fbff;margin:10px 0;overflow:hidden}
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
    .research-governance{border:1px solid #c8a25a;border-left:4px solid #a85d00;background:#fff8e8;padding:10px 12px;margin:10px 0;color:#4b3a1d;line-height:1.5}
    .research-governance strong{display:block;margin-bottom:2px}
    .quant-section-head{display:flex;align-items:center;gap:9px;margin:18px 0 8px;font-size:13px;font-weight:850}
    .quant-section-head span{display:inline-grid;place-items:center;width:24px;height:24px;background:var(--black);color:#fff;font-size:10px}
    .risk-channel-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
    .risk-channel-card{position:relative;border:1px solid var(--line);background:#fff;padding:14px;min-height:150px;overflow:hidden}
    .risk-channel-card::before{content:"";position:absolute;left:0;top:0;width:100%;height:3px;background:var(--electric)}
    .risk-channel-card.physical::before{background:var(--pink)}
    .risk-channel-card.transition::before{background:var(--cyan)}
    .risk-channel-card.macro::before{background:var(--acid)}
    .risk-card-kicker{font-size:9px;font-weight:850;text-transform:uppercase;color:var(--muted)}
    .risk-card-rate{font-size:29px;font-weight:900;line-height:1;margin:8px 0 3px;color:var(--red)}
    .risk-card-rate.green{color:var(--green)}.risk-card-rate.blue{color:#173d7a}
    .risk-card-money{font-size:15px;font-weight:850}
    .risk-card-formula{margin-top:10px;padding:8px;background:#f6f7f3;border-left:2px solid var(--line);font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:10px}
    .risk-card-components{margin-top:9px;color:var(--muted);font-size:10px;line-height:1.5}
    .risk-card-source{display:inline-block;margin-top:8px;padding:2px 6px;border:1px solid var(--line);font-size:9px;font-weight:800;text-transform:uppercase;color:#555851}
    .decision-bridge-grid{display:grid;grid-template-columns:1.5fr .85fr;gap:10px}
    .cashflow-bridge{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));border:1px solid var(--line);background:#fff}
    .cashflow-stage{position:relative;padding:13px 12px;min-height:110px;border-right:1px solid var(--line)}
    .cashflow-stage:last-child{border-right:0;background:#f2f7ff}
    .cashflow-stage:not(:last-child)::after{content:"→";position:absolute;right:-9px;top:42px;z-index:2;width:18px;height:18px;text-align:center;background:#fff;font-weight:900;color:var(--electric)}
    .cashflow-stage .stage-label{font-size:9px;text-transform:uppercase;color:var(--muted);font-weight:800}
    .cashflow-stage .stage-value{font-size:18px;font-weight:900;margin-top:8px}
    .cashflow-stage .stage-note{font-size:9px;color:var(--muted);margin-top:5px;line-height:1.35}
    .valuation-card{border:1px solid var(--line);background:var(--black);color:#fff;padding:14px;min-height:110px}
    .valuation-card .label{font-size:9px;text-transform:uppercase;color:#bfc2bb;font-weight:800}
    .valuation-card .value{font-size:29px;font-weight:900;margin:7px 0}
    .valuation-card .detail{font-size:10px;color:#d6d8d2;line-height:1.45}
    .investment-impact-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
    .investment-impact-card{border-top:3px solid var(--electric);background:#fff;padding:12px;border-left:1px solid var(--line);border-right:1px solid var(--line);border-bottom:1px solid var(--line);min-height:102px}
    .investment-impact-card .label{font-size:9px;text-transform:uppercase;color:var(--muted);font-weight:850}
    .investment-impact-card .headline{font-size:16px;font-weight:900;margin:7px 0}
    .investment-impact-card .copy{font-size:10px;color:#555851;line-height:1.5}
    .research-sandbox{display:none!important}
    #modelAttributionTable,#modelResolutionTable,#modelInstrumentTable,#modelCalculationTable,#issuerCalculationTable{min-width:720px}
    @media (max-width:1320px){.issuer-demo-strip{grid-template-columns:repeat(4,minmax(0,1fr))}.model-lab-controls{grid-template-columns:repeat(4,minmax(0,1fr))}.method-flow{grid-template-columns:repeat(4,minmax(0,1fr))}.lab-kpi{grid-template-columns:repeat(3,minmax(0,1fr))}.decision-bridge-grid{grid-template-columns:1fr}.investment-impact-grid{grid-template-columns:1fr 1fr}}
    @media (max-width:1100px){header{position:relative}.layout{grid-template-columns:1fr}.grid.kpi,.grid.two,.grid.three,.grid.four,.client-summary,.split-table,.lab-split,.risk-channel-grid{grid-template-columns:1fr}.model-lab-controls{grid-template-columns:1fr 1fr}.method-flow{grid-template-columns:1fr 1fr}.method-step{border-bottom:1px solid #dbe3ef}.method-step:nth-child(odd){border-right:1px solid #dbe3ef}.method-step:nth-child(even){border-right:0}.lab-column+ .lab-column{padding-left:0;border-left:0}.lab-kpi{grid-template-columns:1fr 1fr}.cashflow-bridge{grid-template-columns:1fr}.cashflow-stage{border-right:0;border-bottom:1px solid var(--line)}.cashflow-stage:not(:last-child)::after{content:"↓";right:50%;top:auto;bottom:-9px}.investment-impact-grid{grid-template-columns:1fr}aside{position:relative;top:0;height:auto}.kpi-value{font-size:21px}table{min-width:760px}}

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
    #cvor-section{order:5}#daily-reco-backtest-section{order:6}#climate-data-section{order:7}
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
    .source-card{border-radius:2px}
    .split-table>div{min-width:0;overflow:auto}
    .section-title{font-size:11px;text-transform:uppercase;margin:6px 0 8px}
    .disclosure-line{font-size:10px;color:var(--muted);padding:9px 0;border-top:1px solid var(--line)}
    .technical-details{margin-top:12px;border-top:1px solid var(--line);padding-top:10px}
    .technical-details summary{cursor:pointer;font-weight:800;font-size:11px;text-transform:uppercase}
    @media (max-width:1320px){.risk-budget-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.decision-grid{grid-template-columns:1fr 1fr}.institution-controls{grid-template-columns:repeat(3,minmax(0,1fr))}.control-wide{grid-column:span 1}}
    @media (max-width:1100px){header{position:sticky}.layout{grid-template-columns:1fr;padding:0 14px 30px;gap:12px}aside{position:relative;top:0;height:auto;border-right:0;border-bottom:1px solid var(--line);padding:10px 0}.side-nav{display:flex;overflow-x:auto;margin:0}.side-nav a{flex:0 0 auto;border-left:0;border-bottom:2px solid transparent}.side-nav a:hover{border-left:0;border-bottom-color:var(--electric)}.side-block{display:none}main{padding-top:10px}.grid.kpi{grid-template-columns:repeat(3,minmax(0,1fr))}.client-summary{grid-template-columns:1fr}.institution-controls{grid-template-columns:1fr 1fr}.model-lab-controls{grid-template-columns:1fr 1fr}.split-table,.lab-split{grid-template-columns:1fr}.lab-column+.lab-column{padding-left:0;border-left:0}.panel-head>span:last-child{max-width:48%}}
    @media (max-width:640px){.issuer-demo-strip{grid-template-columns:repeat(2,minmax(0,1fr))}header{padding:0 12px;min-height:54px}header .badge:not(#timeBadge){display:none}h1{font-size:13px}.layout{padding:0 10px 24px}.grid.kpi{grid-template-columns:1fr 1fr}.kpi-card{min-height:76px}.decision-grid,.risk-budget-grid,.institution-controls,.model-lab-controls,.lab-kpi{grid-template-columns:1fr}.grid.two,.grid.three,.grid.four{grid-template-columns:1fr}.method-flow{grid-template-columns:1fr}.method-step{border-right:0;border-bottom:1px solid var(--line)}.panel-head{align-items:flex-start;gap:10px}.panel-head>span:last-child{font-size:8px}.client-callout .headline{font-size:24px}table{min-width:700px}}

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
    .side-nav a span{font-size:10px;text-transform:none;color:#838c93;margin-left:4px}
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
    #model-lab-section{order:5}#cvor-section{order:6}#climate-data-section{order:7}
    @media (max-width:1100px){.validation-controls{grid-template-columns:1fr 1fr}.validation-controls .window-tabs{grid-column:1/-1}.client-summary{gap:12px}#dailyRecoSummary{grid-template-columns:repeat(2,minmax(0,1fr))}#dailyRecoSummary .signal-card:nth-child(4n+1){border-left:1px solid var(--line)}#dailyRecoSummary .signal-card:nth-child(2n+1){border-left:0}}
    @media (max-width:640px){body{font-size:12px}header{min-height:56px}h1{font-size:13px;font-weight:650}.panel-head>span:first-child{font-size:16px}.panel-head>span:last-child{font-size:9.5px}.grid.kpi{gap:8px}.kpi-card{min-height:78px}.kpi-label,.signal-card .label{font-size:10px}.kpi-value{font-size:21px}.client-callout .headline{font-size:27px}.validation-controls{grid-template-columns:1fr}.validation-controls .window-tabs{grid-column:auto}.decision-grid{gap:8px}#dailyRecoSummary .signal-card{padding:11px 8px}.validation-primary .value{font-size:21px}}

    /* Client demo view: one restrained valuation page, with technical detail on demand. */
    #regimeBadge,#sourceBadge,#timeBadge,#client-section,#cvor-section{display:none!important}
    .header-context{margin-left:auto;color:var(--muted);font-size:11px}
    .layout{display:block;max-width:1480px;padding:0 32px 40px}
    aside{display:none}
    main{padding-top:22px;gap:0}
    #model-lab-section{order:1;border-top-color:#8f999f}
    #model-lab-section::before{background:#355a8a}
    #model-lab-section .panel-body{padding-top:14px}
    #modelGovernanceBanner{padding:0 0 11px;border-top:0;color:#6b747b}
    .issuer-demo-strip{grid-template-columns:repeat(8,minmax(0,1fr));gap:0;margin:9px 0 15px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
    .issuer-demo-card{min-height:54px;border:0;border-left:1px solid var(--line);border-radius:0;padding:9px 10px;background:transparent}
    .issuer-demo-card:first-child{border-left:0}
    .issuer-demo-card:hover,.issuer-demo-card.active{border-color:var(--line);background:#eef2f5;box-shadow:none}
    .issuer-demo-card.active{box-shadow:inset 0 -2px 0 #355a8a}
    .issuer-demo-card b{font-size:14px;color:#274a72}.issuer-demo-card span{font-size:10.5px;margin-top:2px}
    .model-lab-controls{grid-template-columns:1.35fr 1.35fr .65fr .75fr .75fr auto;gap:9px}
    #modelSectorStatus,#ngfsTransitionEvidence{display:none!important}
    #issuerFinancialEvidence{padding:10px 0 0;border:0;color:#68737d}
    .quant-section-head{margin:16px 0 6px;font-size:13px}
    .quant-section-head span{width:20px;height:20px;background:#293946;font-size:9px}
    #issuerCompanyInfo{grid-template-columns:repeat(4,minmax(0,1fr))}
    .risk-channel-grid{gap:18px}
    .risk-channel-card{border:0;border-top:1px solid var(--line);background:transparent;padding:12px 2px;min-height:112px}
    .risk-channel-card::before{display:none}
    .risk-card-kicker{font-size:10.5px;text-transform:none;color:#68737d}
    .risk-card-rate{font-size:26px;font-weight:650;margin:7px 0 3px}
    .risk-card-money{font-size:14px;font-weight:650}
    .risk-card-formula{margin-top:7px;padding:0;border:0;background:transparent;font-family:inherit;font-size:10.5px;color:#68737d}
    .risk-card-source{display:none}
    .decision-bridge-grid{grid-template-columns:1.55fr .75fr;gap:16px}
    .cashflow-bridge{border-color:var(--line)}
    .cashflow-stage{min-height:94px;padding:12px 10px}
    .cashflow-stage .stage-value{font-size:17px;font-weight:650}
    .valuation-card{min-height:94px;background:#fff;color:var(--text);border:1px solid var(--line);border-left:4px solid #355a8a;padding:13px}
    .valuation-card .label{font-size:10px;text-transform:none;color:#68737d}
    .valuation-card .value{font-size:27px;font-weight:650;color:var(--red)}
    .valuation-card .detail{font-size:10.5px;color:#68737d}
    .investment-impact-grid{gap:18px}
    .investment-impact-card{min-height:78px;padding:11px 2px;background:transparent;border:0;border-top:1px solid var(--line)}
    .investment-impact-card .label{font-size:10px;text-transform:none}
    .investment-impact-card .headline{font-size:15px;font-weight:650;margin:6px 0 3px}
    .investment-impact-card .copy{font-size:10.5px;line-height:1.35}
    #issuerCalculationDisclosure{margin-top:16px}
    @media (max-width:1100px){.layout{padding:0 18px 30px}.issuer-demo-strip{grid-template-columns:repeat(4,minmax(0,1fr))}.issuer-demo-card:nth-child(5){border-left:0}.model-lab-controls{grid-template-columns:1fr 1fr 1fr}#issuerCompanyInfo{grid-template-columns:1fr 1fr}.decision-bridge-grid{grid-template-columns:1fr}}
    @media (max-width:640px){.header-context{display:none}.layout{padding:0 12px 24px}.issuer-demo-strip{grid-template-columns:repeat(2,minmax(0,1fr))}.issuer-demo-card:nth-child(odd){border-left:0}.model-lab-controls,#issuerCompanyInfo{grid-template-columns:1fr 1fr}.risk-channel-grid,.investment-impact-grid{grid-template-columns:1fr;gap:6px}}
  </style>
</head>
<body>
<header>
  <div class="light-mark" aria-hidden="true"><span></span><span></span><span></span></div>
  <h1>Jennison Climate-Risk Research Platform</h1>
  <span class="header-context">Long-term scenario valuation prototype</span>
  <span class="badge" id="regimeBadge">Loading regime...</span>
  <span class="badge" id="sourceBadge">Sources loading</span>
  <span style="margin-left:auto" class="badge" id="timeBadge">-</span>
</header>
<div class="layout">
  <aside>
    <nav class="side-nav" aria-label="Research workspace sections">
      <a href="#client-section">Evidence View <span>Research</span></a>
      <a href="#model-lab-section">Scenario Lab <span>Repricing</span></a>
      <a href="#cvor-section">Stress Matrix <span>Conditional</span></a>
      <a href="#climate-data-section">Climate Signals <span>Lineage</span></a>
    </nav>
    <div class="side-block">
      <div class="side-kicker">Research objective</div>
      <div class="side-value">Transparent conditional climate research</div>
      <div class="side-copy">Scenario, sector, issuer, and data-gap evidence are separated. No automatic investment recommendation is produced.</div>
    </div>
    <div class="side-block">
      <div class="side-kicker">Model status</div>
      <div class="side-value" id="sideModelStatus">Research only — not promoted</div>
      <div class="side-copy">Current scenario and issuer outputs are project-calibrated sensitivities, not forecasts, probabilities, or audited losses.</div>
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
      <div class="kpi-card"><div class="kpi-label">Research regime</div><div id="kpiRegime" class="kpi-value">-</div></div>
      <div class="kpi-card"><div class="kpi-label">Live NWS alerts</div><div id="kpiScore" class="kpi-value">-</div></div>
      <div class="kpi-card"><div class="kpi-label">NWS pressure index</div><div id="kpiReturn" class="kpi-value">-</div></div>
      <div class="kpi-card"><div class="kpi-label">Primary hazard</div><div id="kpiExcess" class="kpi-value">-</div></div>
      <div class="kpi-card"><div class="kpi-label">Climate vintage</div><div id="kpiDrawdown" class="kpi-value">-</div></div>
      <div class="kpi-card"><div class="kpi-label">Model stage</div><div id="kpiCvor" class="kpi-value">Research only</div></div>
    </section>

    <section class="panel accent-acid" id="client-section">
      <div class="panel-head"><span>Research Evidence Overview</span><span id="clientSummaryTag">Evidence grade and permitted use</span></div>
      <div class="panel-body">
        <div id="clientSummary" class="client-summary"></div>
        <div id="investmentCommitteeStrip" class="decision-grid"></div>
        <div class="research-governance"><strong>Governance boundary</strong>Engineering output is available for research review only. Model promotion, portfolio tilts, tactical overlays, and security recommendations are not authorized.</div>
      </div>
    </section>

    <section class="panel accent-pink" id="model-lab-section">
      <div class="panel-head"><span>Long-Term Climate Valuation</span><span id="modelLabTag">Scenario → FCFF → value</span></div>
      <div class="panel-body">
        <div class="disclosure-line" id="modelGovernanceBanner">Eight issuers · observed inputs · visible Low/Base/High assumptions</div>
        <div class="section-title">Select issuer</div>
        <div id="issuerDemoStrip" class="issuer-demo-strip"></div>
        <div class="model-lab-controls">
          <input type="hidden" id="modelScope" value="issuer">
          <input type="hidden" id="modelSector" value="Technology">
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
            <label for="modelTicker">Issuer ticker</label>
            <input id="modelTicker" value="AAPL" maxlength="12">
          </div>
          <div>
            <label for="modelAssumptionCase">Assumption case</label>
            <select id="modelAssumptionCase">
              <option value="low">Low</option>
              <option value="base" selected>Base</option>
              <option value="high">High</option>
            </select>
          </div>
          <button onclick="loadClimateModelLab()">Run Model</button>
        </div>
        <div id="modelSectorStatus" class="disclosure-line"></div>
        <div id="ngfsTransitionEvidence" class="disclosure-line"></div>
        <div id="issuerFinancialEvidence" class="disclosure-line"></div>
        <div id="issuerPilotEvidence" class="research-governance" style="display:none"></div>
        <div class="quant-section-head" id="issuerCompanyInfoTitle" style="display:none"><span>01</span>Company financial baseline</div>
        <div id="issuerCompanyInfo" class="grid lab-kpi"></div>
        <div id="issuerDecisionView" style="display:none">
          <div class="quant-section-head"><span>02</span>What changes FCFF</div>
          <div id="issuerRiskCards" class="risk-channel-grid"></div>
          <div class="quant-section-head"><span>03</span>From FCFF to value</div>
          <div class="decision-bridge-grid">
            <div id="issuerCashFlowBridge" class="cashflow-bridge"></div>
            <div id="issuerValuationCard" class="valuation-card"></div>
          </div>
          <div class="quant-section-head"><span>04</span>Investment use</div>
          <div id="issuerInvestmentImpact" class="investment-impact-grid"></div>
        </div>
        <details class="advanced-box" id="issuerCalculationDisclosure" style="display:none">
          <summary>Inputs, assumptions and calculation detail</summary>
          <div class="quant-section-head" id="issuerCalculationTitle"><span>05</span>Calculation detail and reconciliation</div>
          <table id="issuerCalculationTable"></table>
        </details>

        <div id="modelLabSummary" class="grid lab-kpi"></div>
        <div class="lab-column" id="modelLegacyLong">
            <h3>Long-term: scenario-conditioned value</h3>
            <div id="modelLongHeadline" class="hint"></div>
            <div id="modelLongAttributionBars" class="attribution-list"></div>
        </div>

        <div id="modelLegacyAttribution">
          <div class="section-title">Long-Term Value Attribution</div>
          <table id="modelAttributionTable"></table>
        </div>
        <div class="split-table" id="modelLegacyTables" style="margin-top:12px">
          <div>
            <div class="section-title">Largest Security / Sector Impacts</div>
            <table id="modelInstrumentTable"></table>
          </div>
          <div>
            <div class="section-title">Resolution &amp; Data Honesty</div>
            <table id="modelResolutionTable"></table>
          </div>
        </div>
        <div id="modelLegacyLedger">
          <div class="section-title" style="margin-top:14px">Calculation Ledger &amp; Reconciliation</div>
          <table id="modelCalculationTable"></table>
          <div id="modelCalibrationNotice" class="hint" style="margin-top:10px"></div>
        </div>
      </div>
    </section>

    <section class="panel accent-acid research-sandbox" id="daily-reco-backtest-section" aria-hidden="true">
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
          <button class="secondary" onclick="loadDailyRecommendationBacktest()">Run validation</button>
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
          <div class="research-sandbox" aria-hidden="true">
            <div class="section-title">Engineering overlay (not client-authorized)</div>
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

    <section class="panel accent-cyan research-sandbox" id="optimizer-section" aria-hidden="true">
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
      <div class="panel-head"><span>Conditional Climate Value Impact &amp; Scenario Range</span><span>Project-calibrated stress | no assigned probability</span></div>
      <div class="panel-body">
        <div id="scenarioSummary" class="risk-budget-grid"></div>
        <table id="scenarioTable"></table>
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
function fmtOptionalPct(x){ return x===null || x===undefined || !Number.isFinite(Number(x)) ? "Not calculable" : fmtPct(x); }
function fmtIndex100(x){ return x===null || x===undefined || !Number.isFinite(Number(x)) ? "Not calculable" : (Number(x)*100).toFixed(2)+" / 100"; }
function fmtMoney(x){ return "$"+Number(x||0).toLocaleString(undefined,{maximumFractionDigits:0}); }
function fmtPrice(x){ const n=Number(x); if(!Number.isFinite(n) || n<=0)return "-"; return "$"+n.toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}); }
function fmtVolume(x){ const n=Number(x); if(!Number.isFinite(n) || n<=0)return "-"; if(n>=1e9)return (n/1e9).toFixed(2)+"B"; if(n>=1e6)return (n/1e6).toFixed(2)+"M"; if(n>=1e3)return (n/1e3).toFixed(1)+"K"; return String(Math.round(n)); }
function fmtBps(x){ const n=Number(x)||0; return (n>0?"+":"") + n.toFixed(0) + " bps"; }
function fmtOptionalCount(x){ return x===null || x===undefined || !Number.isFinite(Number(x)) ? "Not calculable" : Number(x).toLocaleString(); }
function fmtSignedPct(x){ const n=Number(x)||0; return (n>0?"+":"") + (n*100).toFixed(2)+"%"; }
function fmtRiskSignedPct(x){
  const n=Number(x)||0;
  if(n!==0 && Math.abs(n)<0.0001) return n>0?"<0.01%":"-<0.01%";
  return fmtSignedPct(n);
}
function fmtOptionalSignedPct(x){ return x===null || x===undefined || !Number.isFinite(Number(x)) ? "Not calculable" : fmtSignedPct(x); }
function clsFor(v){ return Number(v)>=0 ? "green" : "red"; }
function clamp(x, lo, hi){ return Math.max(lo, Math.min(hi, Number(x))); }

async function loadDashboard(){
  const res = await fetch("/api/dashboard");
  DASH = await res.json();
  renderDashboard(DASH);
  await loadClimateModelLab();
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
    ticker: document.getElementById("modelTicker").value,
    assumption_case: document.getElementById("modelAssumptionCase").value
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
    const display = valueKey.includes("bps") ? fmtBps(value) : (valueKey === "risk_contribution" ? fmtIndex100(value) : fmtSignedPct(value));
    return `<div class="attribution-row">
      <span>${r[labelKey] || "-"}</span>
      <div class="attribution-track"><span class="${good?"positive":""}" style="width:${width}%"></span></div>
      <b class="${good?"green":"red"}">${display}</b>
    </div>`;
  }).join("");
}

function fmtMoneyCompact(value){
  const n = Number(value);
  if(!Number.isFinite(n)) return "-";
  const a = Math.abs(n);
  if(a>=1e9) return `${n<0?"-":""}$${(a/1e9).toFixed(1)}bn`;
  if(a>=1e6) return `${n<0?"-":""}$${(a/1e6).toFixed(1)}m`;
  if(a>=1e3) return `${n<0?"-":""}$${(a/1e3).toFixed(1)}k`;
  return `${n<0?"-":""}$${a.toFixed(0)}`;
}

function selectDemoIssuer(ticker, sector){
  document.getElementById("modelScope").value = "issuer";
  document.getElementById("modelSector").value = sector;
  document.getElementById("modelTicker").value = ticker;
  updateModelControlState();
  loadClimateModelLab();
}

function renderIssuerDemo(d){
  const strip = document.getElementById("issuerDemoStrip");
  if(!strip) return;
  const demo = d.demo_issuers || {};
  const rows = demo.rows || [];
  const publicRows = ((d.public_evidence_universe||{}).rows)||[];
  const publicByTicker = Object.fromEntries(publicRows.map(row=>[row.ticker,row]));
  strip.innerHTML = rows.map(row=>{
    const active = d.scope === "issuer" && d.ticker === row.ticker;
    return `<button class="issuer-demo-card ${active?"active":""}" onclick="selectDemoIssuer('${row.ticker}','${row.sector}')">
      <b>${row.ticker}</b><span>${row.sector}</span>
    </button>`;
  }).join("");
}

function renderClimateModelLab(d){
  if(!d || !d.long_term) return;
  const lt = d.long_term;
  const issuerPublicEvidence = d.issuer_public_evidence || {};
  const target = d.target || {};
  const reference = d.reference || {};
  renderIssuerDemo(d);
  const sectorResolution = d.sector_resolution || null;
  if(d.scope === "issuer" && d.sector){
    const sectorControl = document.getElementById("modelSector");
    if(sectorControl) sectorControl.value = d.sector;
  }
  const sectorStatus = document.getElementById("modelSectorStatus");
  if(sectorStatus){
    const issuerDetails = sectorResolution
      ? [
          sectorResolution.issuer_name,
          sectorResolution.exchange,
          sectorResolution.country,
          sectorResolution.industry,
          sectorResolution.cik ? `CIK ${sectorResolution.cik}` : ""
        ].filter(Boolean).join(" | ")
      : "";
    sectorStatus.innerHTML = sectorResolution
      ? `<b>${d.ticker} · ${d.sector}</b>${issuerDetails ? ` · ${issuerDetails}` : ""} · mapping ${sectorResolution.as_of}`
      : "Issuer mapping pending";
  }
  document.getElementById("modelLabTag").textContent = `${d.scope_label} | ${target.label} vs ${reference.label} | ${d.horizon}`;
  const pilot = d.issuer_pilot || {};
  const hasIssuerPilot = d.scope === "issuer" && pilot.is_loaded;
  const governanceBanner = document.getElementById("modelGovernanceBanner");
  if(governanceBanner){
    governanceBanner.textContent = `Eight issuers · source-backed inputs · prototype assumptions explicitly labelled`;
  }
  const financialEvidence = document.getElementById("issuerFinancialEvidence");
  const companyInfo = document.getElementById("issuerCompanyInfo");
  const companyInfoTitle = document.getElementById("issuerCompanyInfoTitle");
  const issuerDecisionView = document.getElementById("issuerDecisionView");
  const issuerRiskCards = document.getElementById("issuerRiskCards");
  const issuerCashFlowBridge = document.getElementById("issuerCashFlowBridge");
  const issuerValuationCard = document.getElementById("issuerValuationCard");
  const issuerInvestmentImpact = document.getElementById("issuerInvestmentImpact");
  const issuerCalculationTable = document.getElementById("issuerCalculationTable");
  const issuerCalculationTitle = document.getElementById("issuerCalculationTitle");
  if(financialEvidence){
    const demoRows = ((d.demo_issuers||{}).rows)||[];
    const issuer = demoRows.find(row=>row.ticker===d.ticker);
    if(d.scope === "issuer" && issuer){
      const companyNames = {
        AAPL:"Apple", CAT:"Caterpillar", CVX:"Chevron", DE:"Deere & Company",
        DUK:"Duke Energy", MSFT:"Microsoft", NEE:"NextEra Energy", XOM:"Exxon Mobil"
      };
      const companyFcf = Number(issuer.free_cash_flow_usd);
      const dukeFcff = Number(issuer.duke_fcff_usd);
      const baseCashFlow = Number.isFinite(dukeFcff) && issuer.duke_fcff_usd!=="" ? dukeFcff : companyFcf;
      const publicEvidence = d.issuer_public_evidence || {};
      if(publicEvidence.is_loaded){
        const transition = publicEvidence.transition || {};
        const physical = publicEvidence.physical || {};
        const valuation = d.prototype_valuation || {};
        const observed = valuation.observed_inputs || {};
        const assumptions = valuation.model_assumptions || {};
        const channels = valuation.channels || [];
        const audit = valuation.valuation_audit || {};
        const equityBridge = valuation.equity_bridge || {};
        const channel = key => channels.find(row=>row.key===key) || {};
        const range = d.valuation_range || {};
        const selectedCase = String(valuation.assumption_case || "base");
        const physicalCoverage = Number(physical.fema_county_matches||0)>0
          ? `${physical.fema_county_matches}/${physical.epa_parent_facilities} facilities matched`
          : `${Number(physical.disclosed_value||0).toFixed(0)}% disclosed exposure`;
        financialEvidence.style.display = "block";
        financialEvidence.innerHTML = `<b>${companyNames[issuer.ticker] || issuer.ticker}</b> · ${issuer.sector} · ${audit.ranking_status||"REVIEW"} · enterprise-value sensitivity · ${selectedCase.toUpperCase()} prototype assumptions`;
        if(companyInfo && companyInfoTitle){
          companyInfoTitle.style.display = "flex";
          companyInfoTitle.innerHTML = `<span>01</span>Valuation`;
          companyInfo.innerHTML = [
            ["Modeled value impact", valuation.is_calculable?fmtSignedPct(valuation.value_impact):"Not calculable", Number(valuation.value_impact)>=0?"green":"red"],
            [`${d.horizon} FCFF change`, valuation.is_calculable?fmtMoneyCompact(valuation.terminal_fcff_delta_usd):"-", Number(valuation.terminal_fcff_delta_usd)>=0?"green":"red"],
            ["Low / base / high", `${fmtSignedPct(range.low)} / ${fmtSignedPct(range.base)} / ${fmtSignedPct(range.high)}`, "blue"],
            ["Symmetric EV difference", valuation.symmetric_value_difference===null?"-":fmtSignedPct(valuation.symmetric_value_difference), Number(valuation.symmetric_value_difference)>=0?"green":"red"],
            ["WACC / terminal g", `${fmtPct(valuation.wacc)} / ${fmtPct(valuation.terminal_growth)}`, "blue"]
          ].map(c=>`<div class="signal-card"><div class="label">${c[0]}</div><div class="value ${c[2]}">${c[1]}</div></div>`).join("");
        }
        if(issuerDecisionView && issuerRiskCards && issuerCashFlowBridge && issuerValuationCard && issuerInvestmentImpact){
          issuerDecisionView.style.display = "block";
          issuerRiskCards.innerHTML = [
            ["transition","Transition",channel("transition")],
            ["physical","Physical",channel("physical")],
            ["macro","Macro / supply",channel("macro_supply")]
          ].map(c=>`<div class="risk-channel-card ${c[0]}">
            <div class="risk-card-kicker">${c[1]} FCFF pressure at ${d.horizon}</div>
            <div class="risk-card-rate ${Number(c[2].terminal_cash_flow_delta_rate)<0?"green":""}">${fmtRiskSignedPct(c[2].terminal_cash_flow_delta_rate)}</div>
            <div class="risk-card-money">${fmtMoneyCompact(-Number(c[2].terminal_cash_flow_delta_usd||0))} annual FCFF effect</div>
            <div class="risk-card-formula">DCF contribution ${fmtRiskSignedPct(c[2].value_contribution)}</div>
          </div>`).join("");
          issuerCashFlowBridge.innerHTML = [
            ["2025 normalized FCFF",fmtMoneyCompact(observed.normalized_fcff_usd),"SEC financial baseline"],
            ["Transition",fmtMoneyCompact(-Number(channel("transition").terminal_cash_flow_delta_usd||0)),"modeled annual delta"],
            ["Physical",fmtMoneyCompact(-Number(channel("physical").terminal_cash_flow_delta_usd||0)),"modeled annual delta"],
            ["Macro / supply",fmtMoneyCompact(-Number(channel("macro_supply").terminal_cash_flow_delta_usd||0)),"modeled annual delta"],
            [`${d.horizon} scenario FCFF`,fmtMoneyCompact(valuation.target_terminal_fcff_usd),"after growth and climate channels"]
          ].map(s=>`<div class="cashflow-stage"><div class="stage-label">${s[0]}</div><div class="stage-value">${s[1]}</div><div class="stage-note">${s[2]}</div></div>`).join("");
          issuerValuationCard.innerHTML = `<div class="label">Discounted enterprise-value impact</div>`+
            `<div class="value">${fmtSignedPct(valuation.value_impact)}</div>`+
            `<div class="detail">${fmtMoneyCompact(valuation.reference_enterprise_value_usd)} → ${fmtMoneyCompact(valuation.target_enterprise_value_usd)}<br>`+
            `Status ${audit.ranking_status||"REVIEW"} · common WACC ${fmtPct(valuation.wacc)}<br>`+
            `${audit.terminal_fcff_clipped?"Terminal FCFF floor applied · ":""}${audit.physical_proxy_used?"physical proxy used · ":""}`+
            `${equityBridge.is_calculable?"Equity bridge available":"EV only; no share-price impact"}.</div>`;
          const dominant = [...channels].sort((a,b)=>Math.abs(Number(b.value_contribution||0))-Math.abs(Number(a.value_contribution||0)))[0] || {};
          const comparisonUse = audit.ranking_status === "RANKABLE"
            ? "Rank peers only within the same scenario and assumption case."
            : audit.ranking_status === "CAUTION"
              ? "Compare only with an explicit coverage warning."
              : "Do not include this result in an ordinary issuer ranking.";
          issuerInvestmentImpact.innerHTML = [
            ["Compare",`Main driver: ${dominant.label || "-"}`,comparisonUse],
            ["Review","Low / Base / High","Challenge exposure, resilience and pass-through."],
            ["Use","Risk budget / engagement","Long-horizon review; no automatic trade."]
          ].map(c=>`<div class="investment-impact-card"><div class="label">${c[0]}</div><div class="headline">${c[1]}</div><div class="copy">${c[2]}</div></div>`).join("");
        }
        const disclosure = document.getElementById("issuerCalculationDisclosure");
        if(issuerCalculationTable && disclosure){
          disclosure.style.display = "block";
          if(issuerCalculationTitle) issuerCalculationTitle.style.display = "flex";
          issuerCalculationTable.style.display = "table";
          const detail = valuation.terminal_component_detail || {};
          const rows = [
            [String(observed.fcff_accounting_class||"").startsWith("Prototype")?"Demo assumption":"Calculated", "Normalized FCFF", `${observed.fcff_status}; ${observed.fcff_accounting_class||""}`, fmtMoneyCompact(observed.normalized_fcff_usd)],
            ["Observed", "Reported Scope 1 / 2 / 3", transition.source_title || "Issuer report", `${Number(observed.scope1_tco2e||0).toLocaleString()} / ${Number(observed.scope2_tco2e||0).toLocaleString()} / ${Number(observed.scope3_tco2e||0).toLocaleString()} tCO2e`],
            ["Observed", "SEC net PP&E", `Period end ${observed.ppe_period_end||"-"}`, fmtMoneyCompact(observed.net_ppe_usd)],
            [audit.physical_proxy_used?"Demo assumption":"Observed/derived", "FEMA building EAL rate", `${observed.fema_eal_source}; ${observed.fema_matches||0}/${observed.fema_facility_count||0} matches${audit.physical_proxy_used?"; prototype fallback":""}`, fmtPct(observed.fema_building_eal_rate)],
            ["Observed", "CIE heat-productivity loss", `Target / reference at ${d.horizon}`, `${fmtPct(observed.cie_terminal_labour_loss_target)} / ${fmtPct(observed.cie_terminal_labour_loss_reference)}`],
            ["Observed", "SEC CapEx / CFO", "Company macro/supply dependency input", fmtPct(observed.capex_to_operating_cash_flow)],
            ["Observed", "Beta / Treasury", `${observed.beta_observations} monthly returns; Treasury ${observed.risk_free_as_of}`, `${Number(observed.beta||0).toFixed(2)} / ${fmtPct(observed.risk_free_rate)}`],
            ["Demo assumption", "Policy coverage / pass-through", `${selectedCase}; not issuer-observed`, `${fmtPct(assumptions.policy_coverage)} / ${fmtPct(assumptions.pass_through)}`],
            ["Demo assumption", "Scope 2 / Scope 3 incidence", "Purchased energy / value chain; not issuer-observed", `${fmtPct(assumptions.scope2_cost_incidence)} / ${fmtPct(assumptions.scope3_value_chain_incidence)}`],
            ["Demo assumption", "Emissions decline", "Annual; not issuer-observed", fmtPct(assumptions.annual_emissions_decline)],
            ["Demo assumption", "Covered PP&E / recovery", "Facility allocation / insurance + adaptation; not issuer-observed", `${fmtPct(assumptions.covered_ppe_share)} / ${fmtPct(assumptions.insurance_adaptation_recovery)}`],
            ["Calculation", "Transition components", "Scope 1 + Scope 2 + Scope 3", `${fmtMoneyCompact(-Number(detail.scope1||0))} / ${fmtMoneyCompact(-Number(detail.scope2||0))} / ${fmtMoneyCompact(-Number(detail.scope3||0))}`],
            ["Calculation", "Physical components", "Acute FEMA EAL + chronic CIE heat", `${fmtMoneyCompact(-Number(detail.acute||0))} / ${fmtMoneyCompact(-Number(detail.chronic||0))}`],
            ["Demo assumption", "Macro transmission", `${assumptions.macro_dependency_rule}; not issuer-observed`, `${fmtPct(assumptions.macro_cashflow_elasticity)} × ${Number(assumptions.macro_dependency_scale||0).toFixed(2)}`],
            ["Demo assumption", "Forecast growth / terminal growth", assumptions.forecast_growth_rule, fmtPct(valuation.terminal_growth)],
            ["Calculation", "Transition difference", "Target net cost - reference net cost; pass-through applied once", fmtMoneyCompact(-Number(channel("transition").terminal_cash_flow_delta_usd||0))],
            ["Valuation", "Target vs reference EV", `Annual FCFF + terminal value; ${audit.ranking_status||"REVIEW"}; no equity/share-price bridge`, fmtSignedPct(valuation.value_impact)]
          ];
          issuerCalculationTable.innerHTML = `<tr><th>Class</th><th>Input</th><th>Source / rule</th><th>Value</th></tr>`+
            rows.map(r=>`<tr><td><b>${r[0]}</b></td><td>${r[1]}</td><td>${r[2]}</td><td>${r[3]}</td></tr>`).join("");
        }
      } else {
      const physicalRate = Number(lt.physical_loss_delta||0);
      const transitionRate = Number(lt.transition_loss_delta||0);
      const macroRate = Number(lt.macro_loss_delta||0);
      const physicalAmount = baseCashFlow*physicalRate;
      const transitionAmount = baseCashFlow*transitionRate;
      const macroAmount = baseCashFlow*macroRate;
      const scenarioCashFlow = Number.isFinite(baseCashFlow) ? baseCashFlow-physicalAmount-transitionAmount-macroAmount : null;
      const wacc = Number(lt.weighted_wacc);
      const growth = Number(lt.weighted_terminal_growth);
      const canValue = baseCashFlow>0 && scenarioCashFlow!==null && scenarioCashFlow>0 && wacc>growth;
      const referenceValue = canValue ? baseCashFlow*(1+growth)/(wacc-growth) : null;
      const scenarioValue = canValue ? scenarioCashFlow*(1+growth)/(wacc-growth) : null;
      const valueChange = referenceValue!==null ? scenarioValue/referenceValue-1 : null;
      const evidenceLabel = Number(issuer.direct_emitter_matches||0)>0
        ? `${issuer.direct_emitter_matches} EPA emitter matches / ${issuer.parent_facility_records} facilities`
        : "Industry inputs used where company data are unavailable";
      financialEvidence.style.display = "block";
      financialEvidence.innerHTML = `<strong>${companyNames[issuer.ticker] || issuer.ticker}: calculation summary</strong>`+
        `Operating cash flow ${fmtMoneyCompact(issuer.operating_cash_flow_usd)} − CapEx ${fmtMoneyCompact(issuer.capital_expenditure_usd)} = FCF ${fmtMoneyCompact(companyFcf)}. `+
        `${issuer.ticker==="DUK" ? `After adding after-tax interest, FCFF is ${fmtMoneyCompact(baseCashFlow)}. ` : ""}`+
        `The table below shows every substitution used in the climate-impact and continuing-value example.`;
      if(companyInfo && companyInfoTitle){
        companyInfoTitle.style.display = "flex";
        companyInfo.innerHTML = [
          ["Company", companyNames[issuer.ticker] || issuer.ticker],
          ["Ticker", issuer.ticker],
          ["Sector", issuer.sector],
          ["Financial year", String(issuer.fiscal_year || 2025)],
          ["Base cash flow", fmtMoneyCompact(baseCashFlow)],
          ["Input coverage", evidenceLabel]
        ].map(c=>`<div class="signal-card"><div class="label">${c[0]}</div><div class="value blue">${c[1]}</div></div>`).join("");
      }
      if(issuerDecisionView && issuerRiskCards && issuerCashFlowBridge && issuerValuationCard && issuerInvestmentImpact){
        const attribution = lt.attribution || [];
        const lossFor = label => Number((attribution.find(r=>r.label===label)||{}).loss_delta||0);
        const componentText = rows => rows.map(([label,key])=>`${label} ${fmtSignedPct(lossFor(key))}`).join(" · ");
        const inputSource = Number(issuer.direct_emitter_matches||0)>0 ? "Company + industry inputs" : "Industry estimate";
        const channels = [
          {
            key:"physical", label:"Physical risk", rate:physicalRate, amount:physicalAmount,
            formula:"Acute + chronic physical loss",
            components:componentText([["Acute","Acute physical"],["Chronic","Chronic physical"]]),
            source:inputSource
          },
          {
            key:"transition", label:"Direct transition risk", rate:transitionRate, amount:transitionAmount,
            formula:"Demand + carbon + energy + transition CapEx − pass-through",
            components:componentText([["Demand","Sector demand"],["Carbon","Carbon cost"],["Energy","Energy cost"],["CapEx","Transition CapEx"],["Pass-through","Cost pass-through"]]),
            source:inputSource
          },
          {
            key:"macro", label:"Macro / supply chain", rate:macroRate, amount:macroAmount,
            formula:"Country GDP + supply-chain transmission",
            components:componentText([["GDP","Country GDP"],["Supply chain","Supply chain"]]),
            source:"Industry estimate"
          }
        ];
        const totalPressure = channels.reduce((sum,c)=>sum+Math.abs(c.amount),0);
        const dominant = [...channels].sort((a,b)=>Math.abs(b.amount)-Math.abs(a.amount))[0];
        const dominantShare = totalPressure>0 ? Math.abs(dominant.amount)/totalPressure : 0;
        const managementQuestion = dominant.key==="physical"
          ? "Check facility locations, insurance, resilience and recovery plans."
          : dominant.key==="transition"
            ? "Check emissions, energy mix, transition CapEx and pricing power."
            : "Check supplier concentration, customer demand and regional exposure.";
        issuerDecisionView.style.display = "block";
        issuerRiskCards.innerHTML = channels.map(c=>`<div class="risk-channel-card ${c.key}">
          <div class="risk-card-kicker">${c.label}</div>
          <div class="risk-card-rate">${fmtSignedPct(c.rate)}</div>
          <div class="risk-card-money">Cash-flow effect ${fmtMoneyCompact(-c.amount)}</div>
          <div class="risk-card-formula">${fmtMoneyCompact(baseCashFlow)} × ${fmtPct(c.rate)} = ${fmtMoneyCompact(c.amount)}</div>
          <div class="risk-card-components">${c.formula}<br>${c.components}</div>
          <span class="risk-card-source">${c.source}</span>
        </div>`).join("");
        issuerCashFlowBridge.innerHTML = [
          ["Base cash flow",fmtMoneyCompact(baseCashFlow),issuer.ticker==="DUK"?"Unlevered FCFF":"2025 FCF"],
          ["Physical",fmtMoneyCompact(-physicalAmount),fmtPct(physicalRate)+" pressure"],
          ["Transition",fmtMoneyCompact(-transitionAmount),fmtPct(transitionRate)+" pressure"],
          ["Macro / supply",fmtMoneyCompact(-macroAmount),fmtPct(macroRate)+" pressure"],
          ["Scenario cash flow",fmtMoneyCompact(scenarioCashFlow),`${target.label} vs ${reference.label}`]
        ].map(s=>`<div class="cashflow-stage"><div class="stage-label">${s[0]}</div><div class="stage-value">${s[1]}</div><div class="stage-note">${s[2]}</div></div>`).join("");
        issuerValuationCard.innerHTML = `<div class="label">Continuing-value sensitivity</div>`+
          `<div class="value">${valueChange===null?"N/A":fmtSignedPct(valueChange)}</div>`+
          `<div class="detail">${referenceValue===null?"Positive normalized cash flow is required before this illustration is meaningful.":`${fmtMoneyCompact(referenceValue)} → ${fmtMoneyCompact(scenarioValue)}`}<br>`+
          `WACC ${(wacc*100).toFixed(2)}% · terminal growth ${(growth*100).toFixed(2)}%<br>Illustration, not a price target.</div>`;
        issuerInvestmentImpact.innerHTML = [
          ["Dominant modeled channel",dominant.label,`${(dominantShare*100).toFixed(1)}% of the absolute three-channel cash-flow pressure.`],
          ["Security selection","Compare with sector peers","Rank issuers under the same scenario and inspect why their cash-flow sensitivity differs."],
          ["Risk budget","Size the scenario exposure","Use the valuation sensitivity as one long-horizon risk-budget input alongside fundamentals and portfolio concentration."],
          ["Issuer engagement","Question the main driver",managementQuestion+" No automatic trade is produced."]
        ].map(c=>`<div class="investment-impact-card"><div class="label">${c[0]}</div><div class="headline">${c[1]}</div><div class="copy">${c[2]}</div></div>`).join("");
      }
      if(issuerCalculationTable && issuerCalculationTitle){
        issuerCalculationTitle.style.display = "flex";
        issuerCalculationTable.style.display = "table";
        const rows = [
          ["Operating cash flow", "SEC cash-flow statement", fmtMoneyCompact(issuer.operating_cash_flow_usd)],
          ["Capital expenditure", "SEC cash-flow statement", `− ${fmtMoneyCompact(issuer.capital_expenditure_usd)}`],
          ["Free cash flow", "Operating cash flow − capital expenditure", fmtMoneyCompact(companyFcf)]
        ];
        if(issuer.ticker==="DUK") rows.push(["Unlevered FCFF", `FCF + after-tax interest (${fmtMoneyCompact(baseCashFlow-companyFcf)})`, fmtMoneyCompact(baseCashFlow)]);
        rows.push(
          ["Physical-risk effect", `${fmtMoneyCompact(baseCashFlow)} × ${fmtPct(physicalRate)}`, fmtMoneyCompact(-physicalAmount)],
          ["Transition-risk effect", `${fmtMoneyCompact(baseCashFlow)} × ${fmtPct(transitionRate)}`, fmtMoneyCompact(-transitionAmount)],
          ["Macro / supply-chain effect", `${fmtMoneyCompact(baseCashFlow)} × ${fmtPct(macroRate)}`, fmtMoneyCompact(-macroAmount)],
          ["Scenario cash flow", "Base cash flow − physical − transition − macro/supply", fmtMoneyCompact(scenarioCashFlow)],
          ["Discount assumptions", `WACC ${(wacc*100).toFixed(2)}%; terminal growth ${(growth*100).toFixed(2)}%`, "Applied below"],
          ["Reference continuing value", "Base cash flow × (1 + g) ÷ (WACC − g)", referenceValue===null?"Not meaningful with non-positive cash flow":fmtMoneyCompact(referenceValue)],
          ["Scenario continuing value", "Scenario cash flow × (1 + g) ÷ (WACC − g)", scenarioValue===null?"Not meaningful with non-positive cash flow":fmtMoneyCompact(scenarioValue)],
          ["Continuing-value change", "Scenario value ÷ reference value − 1", valueChange===null?"Not calculated":fmtSignedPct(valueChange)]
        );
        issuerCalculationTable.innerHTML = `<tr><th>Calculation</th><th>Formula / input</th><th>Result</th></tr>`+
          rows.map(r=>`<tr><td><b>${r[0]}</b></td><td>${r[1]}</td><td>${r[2]}</td></tr>`).join("");
      }
      }
    } else {
      financialEvidence.style.display = "none";
      financialEvidence.innerHTML = "";
      if(companyInfo) companyInfo.innerHTML = "";
      if(companyInfoTitle) companyInfoTitle.style.display = "none";
      if(issuerDecisionView) issuerDecisionView.style.display = "none";
      if(issuerRiskCards) issuerRiskCards.innerHTML = "";
      if(issuerCashFlowBridge) issuerCashFlowBridge.innerHTML = "";
      if(issuerValuationCard) issuerValuationCard.innerHTML = "";
      if(issuerInvestmentImpact) issuerInvestmentImpact.innerHTML = "";
      if(issuerCalculationTable){ issuerCalculationTable.innerHTML = ""; issuerCalculationTable.style.display = "none"; }
      if(issuerCalculationTitle) issuerCalculationTitle.style.display = "none";
      const calculationDisclosure = document.getElementById("issuerCalculationDisclosure");
      if(calculationDisclosure) calculationDisclosure.style.display = "none";
    }
  }
  const ngfsEvidence = document.getElementById("ngfsTransitionEvidence");
  if(ngfsEvidence){
    const official = d.official_transition || {};
    const release = official.release || {};
    const targetPath = official.target || {};
    const referencePath = official.reference || {};
    const priceText = value => value===null || value===undefined ? "Not available" : `US$2010 ${Number(value).toFixed(2)}/tCO2`;
    ngfsEvidence.innerHTML = release.is_loaded && issuerPublicEvidence.is_loaded
      ? `<b>NGFS ${release.source_release}:</b> ${targetPath.scenario || target.label} ${priceText(targetPath.carbon_price_median)} vs ${referencePath.scenario || reference.label} ${priceText(referencePath.carbon_price_median)} at ${d.horizon}.`
      : release.is_loaded
      ? `<strong>Official NGFS ${release.source_release} USA transition evidence | ${release.release_id}</strong>` +
        `${targetPath.scenario || target.label}: median ${priceText(targetPath.carbon_price_median)}` +
        `${targetPath.carbon_price_min!==null && targetPath.carbon_price_min!==undefined ? `; model range ${priceText(targetPath.carbon_price_min)}–${priceText(targetPath.carbon_price_max)}` : ""}. ` +
        `${referencePath.scenario || reference.label}: ${priceText(referencePath.carbon_price_median)}. ` +
        `The model range is not a probability interval. ${hasIssuerPilot ? "A gross static emissions sensitivity is loaded below; net issuer carbon cost remains Not calculable because jurisdiction, free allocation, pass-through and the future emissions path are missing." : "Issuer carbon cost remains Not calculable until covered emissions, jurisdiction, free allocation, and pass-through evidence are loaded."} Affected Phase 5 physical-damage variables are excluded.`
      : `<strong>Official NGFS transition evidence not loaded</strong>Project pathway calibrations remain isolated and cannot be represented as official scenario data.`;
  }
  const pilotEvidence = document.getElementById("issuerPilotEvidence");
  if(pilotEvidence){
    if(d.scope === "issuer" && pilot.is_loaded && !issuerPublicEvidence.is_loaded){
      const carbon = pilot.carbon_sensitivity || {};
      const fcff = pilot.fcff_bridge || {};
      const tonnes = Number(pilot.ownership_adjusted_nonbiogenic_co2_tonnes || 0);
      const gross = Number(carbon.gross_static_exposure_usd || 0);
      const fcffValue = Number(fcff.fcff || 0);
      pilotEvidence.style.display = "block";
      pilotEvidence.innerHTML = `<strong>DUK governed issuer evidence | ${pilot.release_id}</strong>` +
        `EPA ${pilot.epa_year}: ${pilot.direct_emitter_matches}/${pilot.parent_records} parent records match direct emitters; ${pilot.coordinate_matches} have coordinates; ownership-adjusted non-biogenic CO2 is ${(tonnes/1e6).toFixed(2)} Mt. ` +
        `At the NGFS Current Policies 2050 median, the static gross price exposure is $${(gross/1e6).toFixed(1)}m. This is not net cost: free allocation, pass-through, jurisdiction and the future emissions path are missing. ` +
        `SEC 2025 FCFF bridge is $${(fcffValue/1e9).toFixed(2)}bn using CFO − CapEx + after-tax interest; source line items tie to the filed 10-K, while the FCFF method and valuation remain research-only. ` +
        `${pilot.fema_county_matches} facility records match FEMA county context, but issuer physical loss remains Not calculable because asset values, damage functions, interruption and recovery evidence are missing.`;
    } else {
      pilotEvidence.style.display = "none";
      pilotEvidence.innerHTML = "";
    }
  }
  const summary = document.getElementById("modelLabSummary");
  const isLongCalculable = lt.value_impact !== null && lt.value_impact !== undefined;
  const publicEvidence = issuerPublicEvidence;
  summary.innerHTML = publicEvidence.is_loaded ? [
    ["Scope", d.scope_label, ""],
    ["Gross transition sensitivity", fmtMoneyCompact((publicEvidence.transition||{}).gross_sensitivity_usd), "blue"],
    ["Physical financial loss", "Not calculable", "amber"],
    ["Macro / supply loss", "Not calculable", "amber"],
    ["Issuer value impact", "Not calculable", "amber"]
  ].map(c=>`<div class="signal-card"><div class="label">${c[0]}</div><div class="value ${c[2]}">${c[1]}</div></div>`).join("") : [
    ["Scope", d.scope_label, ""],
    [hasIssuerPilot ? `${d.sector} stress (not issuer value)` : (d.scope === "issuer" ? "Research value proxy" : "Value impact vs reference"), fmtOptionalSignedPct(lt.value_impact), isLongCalculable?clsFor(lt.value_impact):"amber"],
    [hasIssuerPilot ? `${d.sector} physical stress` : "Physical scenario proxy", fmtOptionalSignedPct(lt.physical_loss_delta), isLongCalculable?clsFor(-lt.physical_loss_delta):"amber"],
    [hasIssuerPilot ? `${d.sector} macro/supply stress` : "Macro / supply-chain proxy", fmtOptionalSignedPct(lt.macro_loss_delta), isLongCalculable?clsFor(-lt.macro_loss_delta):"amber"],
    [hasIssuerPilot ? `${d.sector} transition stress` : "Direct transition proxy", fmtOptionalSignedPct(lt.transition_loss_delta), isLongCalculable?clsFor(-lt.transition_loss_delta):"amber"],
    ["Financial baseline", d.scope === "issuer" ? "2025 company FCF" : "Scenario aggregate", "blue"]
  ].map(c=>`<div class="signal-card"><div class="label">${c[0]}</div><div class="value ${c[2]}">${c[1]}</div></div>`).join("");
  ["modelLabSummary","modelLegacyLong","modelLegacyAttribution","modelLegacyTables","modelLegacyLedger"].forEach(id=>{
    const el=document.getElementById(id);
    if(el) el.style.display=publicEvidence.is_loaded?"none":"";
  });

  if(publicEvidence.is_loaded){
    document.getElementById("modelLongHeadline").innerHTML = `<b>Calculated public-data comparison:</b> reported Scope 1 × the selected NGFS carbon-price delta. Physical information is an exposure screen. Net transition cost, physical loss, macro/supply loss, scenario FCFF and valuation are not calculated from incomplete evidence.`;
  } else if(isLongCalculable){
    const valueDirection = lt.value_impact < 0 ? "lower" : (lt.value_impact > 0 ? "higher" : "unchanged");
    document.getElementById("modelLongHeadline").innerHTML = hasIssuerPilot
      ? `The displayed <b>${fmtSignedPct(lt.value_impact)}</b> is the ${d.sector} project stress for ${target.label} versus ${reference.label}; it is <b>not a ${d.ticker} valuation</b>. DUK net transition cost, physical financial loss and issuer valuation remain Not calculable. <b>${d.decision_status || ""}</b>`
      : `If markets reprice from <b>${reference.label}</b> to <b>${target.label}</b>, the conditional research proxy values this ${d.scope} <b>${Math.abs(lt.value_impact*100).toFixed(2)}%</b> ${valueDirection}. This is neither a forecast probability nor an audited issuer valuation. <b>${d.decision_status || ""}</b>`;
  } else {
    document.getElementById("modelLongHeadline").innerHTML = `<b>Not calculable.</b> ${d.decision_status || "Required issuer inputs are not verified."}`;
  }
  renderAttributionBars("modelLongAttributionBars", lt.attribution || [], "value_contribution", "label", true);

  const attrTable = document.getElementById("modelAttributionTable");
  attrTable.innerHTML = `<tr><th>Component</th><th>Target loss</th><th>Reference loss</th><th>Loss delta</th><th>Value contribution</th></tr>` +
    (lt.attribution || []).map(r=>`<tr>
      <td><b>${r.label}</b></td><td>${fmtPct(r.target_loss)}</td><td>${fmtPct(r.reference_loss)}</td>
      <td class="${clsFor(-r.loss_delta)}">${fmtSignedPct(r.loss_delta)}</td>
      <td class="${clsFor(r.value_contribution)}"><b>${fmtSignedPct(r.value_contribution)}</b></td>
    </tr>`).join("");

  const instrumentTable = document.getElementById("modelInstrumentTable");
  instrumentTable.innerHTML = `<tr><th>Name</th><th>Sector</th><th>Weight</th><th>Value impact</th><th>Largest direct transition channel</th><th>Valuation input</th><th>Sector A / C</th><th>Issuer evidence</th><th>Data</th></tr>` +
    (lt.instruments || []).slice(0,8).map(r=>`<tr>
      <td><b>${r.name}</b></td><td>${r.sector}</td><td>${fmtPct(r.weight)}</td>
      <td class="${clsFor(r.value_impact)}"><b>${fmtSignedPct(r.value_impact)}</b></td>
      <td>${String(r.transition_driver || "-").replaceAll("_", " ")}</td>
      <td>${d.scope === "issuer" ? "Assumption grid pending" : "Sector research calibration"}<br><span class="hint">Single-point issuer WACC/g is not decision-authorized</span></td>
      <td>${Number(r.acute_sector_multiplier||0).toFixed(2)}x / ${Number(r.chronic_sector_multiplier||0).toFixed(2)}x</td>
      <td>${d.scope === "issuer" ? "Not verified" : "Not applicable"}</td>
      <td><span class="lab-status">${r.data_quality || "Proxy"}</span></td>
    </tr>`).join("");

  const resolutionTable = document.getElementById("modelResolutionTable");
  resolutionTable.innerHTML = `<tr><th>Level</th><th>Model input</th><th>Status</th><th>Output</th></tr>` +
    (d.scope_resolution || []).map(r=>`<tr>
      <td><b>${r.level}</b></td><td>${r.input}</td><td><span class="lab-status">${r.status}</span></td><td>${r.output}</td>
    </tr>`).join("");
  const calculationTable = document.getElementById("modelCalculationTable");
  const longTermLedger = (d.calculation_ledger || []).filter(r=>
    !/nws|nowcast|short.?term|hazard transmission/i.test(`${r.step||""} ${r.formula||""} ${r.input||""}`)
  );
  calculationTable.innerHTML = `<tr><th>Step</th><th>Equation / rule</th><th>Input</th><th>Reconciled output</th><th>Check</th></tr>` +
    longTermLedger.map(r=>`<tr>
      <td><b>${r.step}</b></td><td>${r.formula}</td><td>${r.input}</td><td>${r.output}</td>
      <td class="${r.check === "Pass" ? "status-pass" : "status-watch"}">${r.check}</td>
    </tr>`).join("");
  const methodology = d.methodology || {};
  document.getElementById("modelCalibrationNotice").textContent = `${d.calibration_notice || ""} ${methodology.probability_rule || ""} ${methodology.tail_rule || ""}`;
  renderInvestmentCommittee();
}

async function loadDailyClimateBoard(){
  const res = await fetch("/api/daily_climate_board");
  DAILY_CLIMATE_BOARD = await res.json();
  renderDailyClimateBoard(DAILY_CLIMATE_BOARD);
}

async function loadDailyRecommendationBacktest(){
  const params = new URLSearchParams();
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
  document.getElementById("dailyClimateTag").textContent = `${d.source_mode} | ${d.decision_status || (d.is_calculable ? "observed hazard mix" : "not calculable")}`;
  document.getElementById("dailyClimateSummary").innerHTML = [
    ["Top driver", driver],
    ["Climate alerts", fmtOptionalCount(d.climate_alerts)],
    ["NWS pressure index", fmtIndex100(d.daily_pressure)],
    ["Evidence grade", "Proxy-dominant"],
    ["Physical pressure", fmtPct(ci.physical_score || 0)],
    ["Transition pressure", fmtPct(ci.transition_score || 0)]
  ].map(c=>`<div class="signal-card"><div class="label">${c[0]}</div><div class="value">${c[1]}</div></div>`).join("");

  const alertTable = document.getElementById("dailyAlertTable");
  if(alertTable){
    alertTable.innerHTML = `<tr><th>Driver</th><th>Alerts</th><th>Intensity</th><th>Portfolio implication</th><th>Observed area</th></tr>` +
      (d.daily_alerts || []).map(r=>`<tr>
        <td><b>${r.driver_label}</b></td>
        <td>${fmtOptionalCount(r.count)}</td>
        <td>${fmtOptionalPct(r.intensity)}</td>
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
  const summaryEl = document.getElementById("dailyRecoSummary");
  const chart = document.getElementById("dailyRecoChart");
  if(!rows.length){
    if(tag) tag.textContent = `${label} | insufficient verified market history`;
    if(chart) chart.style.display = "none";
    if(summaryEl) summaryEl.innerHTML = `<div class="signal-card validation-primary" style="grid-column:1/-1"><div class="label">Validation unavailable</div><div class="value amber">No synthetic fallback</div><div class="hint">${d.covered_securities || 0} of ${d.requested_securities || 0} selected securities have sufficient verified observations. ${d.source || "Market data unavailable"}.</div></div>`;
    const pickTable = document.getElementById("dailyRecoPickTable");
    const dayTable = document.getElementById("dailyRecoYearTable");
    if(pickTable) pickTable.innerHTML = "";
    if(dayTable) dayTable.innerHTML = "";
    const note = document.getElementById("dailyRecoNote");
    if(note) note.textContent = "The platform suppresses performance when verified market history is unavailable; it never substitutes simulated returns.";
    return;
  }
  if(tag) tag.textContent = `${label} | net of ${Number(costs.trading_cost_bps || 0).toFixed(0)} bps trading + ${Number(costs.annual_borrow_cost_bps || 0).toFixed(0)} bps annual borrow | ${summary.trading_days || 0} days`;
  if(chart) chart.style.display = "block";
  if(summaryEl){
    const ci = summary.bootstrap_95_ci || {};
    const ciText = ci.lower == null ? "Insufficient sample" : `95% block-bootstrap ${fmtPct(ci.lower)} to ${fmtPct(ci.upper)}`;
    summaryEl.innerHTML = [
      ["Net signal return", fmtPct(summary.recommended_total_return || 0), clsFor(summary.recommended_total_return || 0), "After modeled costs", "validation-primary"],
      ["Incremental climate value", fmtPct(summary.incremental_climate_value || 0), clsFor(summary.incremental_climate_value || 0), "Climate-on minus Market-only terminal wealth", "validation-primary"],
      ["Maximum drawdown", fmtPct(summary.recommended_max_drawdown || 0), "red", "Net signal wealth", "validation-primary"],
      ["Statistical evidence", summary.permutation_p_value == null ? "N/A" : `p=${Number(summary.permutation_p_value).toFixed(3)}`, summary.statistically_significant_5pct ? "green" : "amber", ciText, "validation-primary"],
      ["Gross signal return", fmtPct(summary.gross_recommended_total_return || 0), clsFor(summary.gross_recommended_total_return || 0), "Before modeled costs", "validation-diagnostic"],
      ["Market-only ablation", fmtPct(summary.market_only_total_return || 0), clsFor(summary.market_only_total_return || 0), "Same assets, exposure, costs and execution", "validation-diagnostic"],
      ["Compounded cost drag", fmtPct(summary.compounded_cost_drag || 0), "amber", `${fmtPct(summary.reported_cost_sum || 0)} summed daily cost`, "validation-diagnostic"],
      ["Information / turnover", Number(summary.information_ratio || 0).toFixed(2), "blue", `${Number(summary.annualized_turnover || 0).toFixed(1)}x annualized turnover`, "validation-diagnostic"]
    ].map(c=>`<div class="signal-card ${c[4]}"><div class="label">${c[0]}</div><div class="value ${c[2]}">${c[1]}</div><div class="hint">${c[3]}</div></div>`).join("");
  }
  if(rows.length){
    drawLineChart(
      "dailyRecoChart",
      rows.map(r=>String(r.date).slice(5)),
      [
        {name:"Climate signal, net", values:rows.map(r=>Number(r.recommended_wealth || 1)), color:"#18765d"},
        {name:"Market-only ablation", values:rows.map(r=>Number(r.market_only_wealth || 1)), color:"#496786"},
        {name:"75% universe + 25% cash", values:rows.map(r=>Number(r.benchmark_wealth || 1)), color:"#6b7480"}
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
    dayTable.innerHTML = `<tr><th>Date</th><th>Buy signals</th><th>Sell signals</th><th>Climate-on</th><th>Market-only</th><th>Incremental</th><th>Benchmark</th><th>Turnover / cost</th></tr>` +
      rows.slice(-18).reverse().map(r=>`<tr>
        <td><b>${r.date}</b><br><span class="hint">signal ${r.signal_date}</span></td>
        <td>${r.picks}</td>
        <td>${r.sells || "-"}</td>
        <td class="${clsFor(r.recommended_return)}">${fmtPct(r.recommended_return)}</td>
        <td class="${clsFor(r.market_only_return)}">${fmtPct(r.market_only_return)}</td>
        <td class="${clsFor(r.incremental_climate_return)}"><b>${fmtPct(r.incremental_climate_return)}</b></td>
        <td class="${clsFor(r.benchmark_return)}">${fmtPct(r.benchmark_return)}</td>
        <td>${fmtPct(r.turnover || 0)}<br><span class="hint">${Number((r.total_cost || 0)*10000).toFixed(1)} bps | coverage ${r.coverage}</span></td>
      </tr>`).join("");
  }
  const note = document.getElementById("dailyRecoNote");
  if(note && d.methodology){
    note.textContent = `${d.methodology.model} ${d.methodology.selection} ${d.methodology.ablation || ""} ${d.methodology.statistics || ""} ${d.methodology.caveat}`;
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
  await loadDailyRecommendationBacktest();
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
    ["Model-ensemble tail", fmtPct(budget.weighted_tail_proxy || 0), fmtMoney(budget.capital_at_tail_proxy || 0)],
    ["Effective positions", Number(budget.effective_positions || 0).toFixed(1), `HHI ${Number(budget.hhi || 0).toFixed(3)}`],
    ["Tracking error", fmtPct(budget.tracking_error || 0), `${fmtPct(budget.turnover_vs_market || 0)} turnover vs market-only`],
    ["Physical pressure", fmtPct(budget.weighted_physical_risk || 0), "Weight-averaged issuer exposure"],
    ["Transition / carbon", fmtPct(budget.weighted_transition_risk || 0), `${fmtPct(budget.weighted_carbon_cost || 0)} carbon-cost channel`]
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
  table.innerHTML = `<tr><th>Ticker</th><th>Sector</th><th>Final / strategic</th><th>Tactical overlay</th><th>Market-only</th><th>Climate active</th><th>Capital</th><th>Market signal</th><th>Climate risk indicator</th><th>Tail</th><th>WACC</th><th>Action</th><th>Investment rationale</th></tr>` +
    (o.rows || []).map(r=>`<tr>
      <td><b>${r.ticker}</b><br><span class="hint">${r.asset_type}</span></td>
      <td>${r.sector}</td>
      <td><b>${fmtPct(r.target_weight)}</b><br><span class="hint">strategic ${fmtPct(r.strategic_weight || r.target_weight)}</span></td>
      <td class="${clsFor(r.tactical_overlay || 0)}">${fmtBps(r.tactical_overlay_bps || 0)}<br><span class="hint">${String(r.tactical_top_hazard || "-").replaceAll("_", " ")}</span></td>
      <td>${fmtPct(r.market_only_weight || 0)}</td>
      <td class="${clsFor(r.climate_weight_delta || 0)}"><b>${fmtBps((r.climate_weight_delta || 0) * 10000)}</b></td>
      <td>${fmtMoney(r.target_dollars)}</td>
      <td>${Number(r.market_return_signal || 0).toFixed(2)}<br><span class="hint">${fmtPct(r.momentum)} 12M</span></td>
      <td class="${clsFor(r.climate_risk_indicator || 0)}">${Number(r.climate_risk_indicator || 0).toFixed(2)}<br><span class="hint">risk indicator | P ${fmtPct(r.physical_risk || 0)} / T ${fmtPct(r.transition_risk || 0)}</span></td>
      <td class="amber">${fmtPct(r.scenario_tail_proxy || 0)}<br><span class="hint">conditional</span></td>
      <td>${fmtPct((r.valuation || {}).wacc || 0)}<br><span class="hint">g ${(Number((r.valuation || {}).terminal_growth || 0)*100).toFixed(1)}%</span></td>
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
  document.getElementById("clientSummaryTag").textContent = "Proxy-dominant evidence | research use only";
  summary.innerHTML = `
    <div class="client-callout">
      <div class="title">Model stage</div>
      <div class="headline amber">Research only</div>
      <div>Conditional scenario and sector-stress review. No portfolio tilt, tactical overlay, or security recommendation is authorized.</div>
      <div class="hint" style="margin-top:8px">Issuer outputs require verified facilities, financials, emissions, revenue geography, and value-chain exposure.</div>
    </div>
    <div class="grid two">
      <div class="signal-card"><div class="label">Physical evidence</div><div class="value amber">Sector / hazard context</div><div class="hint">Issuer loss is not calculable without verified facility and economic exposure.</div></div>
      <div class="signal-card"><div class="label">Transition evidence</div><div class="value blue">NGFS + SEC history loaded</div><div class="hint">Official pathways and candidate financial history are loaded; issuer cash-flow translation remains blocked pending emissions and accounting tie-out.</div></div>
      <div class="signal-card"><div class="label">Valuation evidence</div><div class="value amber">Conditional sensitivity</div><div class="hint">Not an audited issuer valuation or forecast return.</div></div>
      <div class="signal-card"><div class="label">Evidence grade</div><div class="value blue">Proxy-dominant</div><div class="hint">Observed, derived, proxy, and missing fields are reported separately.</div></div>
    </div>`;
  const sourceTable = document.getElementById("clientSourceTable");
  if(sourceTable){
    const sourceRows = ci.source_rows || [];
    const prioritySourceNames = ["U.S. Treasury Daily Rates", "NGFS Scenarios", "SEC EDGAR APIs"];
    const rows = [
      ...prioritySourceNames.flatMap(name=>sourceRows.filter(r=>r.name === name)),
      ...sourceRows.filter(r=>!prioritySourceNames.includes(r.name))
    ].slice(0, 8);
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
  el.innerHTML = [
    ["Permitted use", "Scenario research", "Compare named target and reference pathways; do not interpret the result as a forecast."],
    ["Physical status", "Issuer not calculable", "Verified facility location, economic exposure, damage function, and resilience evidence are required."],
    ["Transition status", "Official pathways + history / issuer blocked", "NGFS 5.1 pathways and SEC candidate history are loaded; issuer cash-flow coefficients remain project calibrations pending emissions and accounting tie-out."],
    ["Model promotion", "Not promoted", "Engineering checks do not authorize portfolio, shadow, paper, or production investment use."]
  ].map(c=>`<div class="decision-cell"><div class="eyebrow">${c[0]}</div><div class="decision">${c[1]}</div><div class="detail">${c[2]}</div></div>`).join("");
}

function renderDashboard(d){
  document.getElementById("timeBadge").textContent = "Updated " + d.generated_at;
  document.getElementById("sourceBadge").textContent =
    `Market + ${((d.climate_data_context || {}).source_mode || "climate data unavailable")}`;
  document.getElementById("regimeBadge").textContent = d.latest_regime.regime + " | signal " + d.latest_regime.signal_year;
  document.getElementById("kpiRegime").textContent = d.latest_regime.regime.replace(" Climate Risk","");
  document.getElementById("kpiRegime").className = "kpi-value " + (d.latest_regime.regime.includes("High") ? "red" : "green");
  const daily = d.daily_climate_signal || {};
  document.getElementById("kpiScore").textContent = fmtOptionalCount(daily.climate_alerts);
  document.getElementById("kpiScore").className = "kpi-value amber";
  document.getElementById("kpiReturn").textContent = fmtIndex100(daily.daily_pressure);
  document.getElementById("kpiReturn").className = "kpi-value blue";
  document.getElementById("kpiExcess").textContent = String(daily.top_driver || "none").replace("_"," ");
  document.getElementById("kpiExcess").className = "kpi-value amber";
  document.getElementById("kpiDrawdown").textContent = d.climate_data_context.latest_year || "-";
  document.getElementById("kpiDrawdown").className = "kpi-value blue";
  document.getElementById("kpiCvor").textContent = "Research only";
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
    ["NWS active alerts", fmtOptionalCount(daily.climate_alerts), "Current hazard context only; not issuer exposure or loss", daily.decision_status || daily.source_mode || "Live input"],
    ["NASA GISTEMP", c.current_warming == null ? "Unavailable" : `${Number(c.current_warming).toFixed(3)} C`, "Chronic warming state and physical-risk calibration", c.latest_year == null ? "Not calculable" : `Official completed-year vintage ${c.latest_year}`],
    ["NOAA GML CO2", c.co2_ppm == null ? "Unavailable" : `${Number(c.co2_ppm).toFixed(2)} ppm`, "Climate-state context only; no allocation or transition-score effect", c.co2_10y_change == null ? "Not calculable" : `Excluded from decision score | 10Y change ${Number(c.co2_10y_change).toFixed(2)} ppm`],
    ["NCEI disasters", `${Number(c.disaster_10y_avg).toFixed(2)} / year`, "Historical acute-loss frequency calibration", `Official vintage ${c.latest_year}`],
    ["Derived climate context", Number(c.climate_pressure_multiplier).toFixed(3), "Cross-check for climate dashboards; not a scenario probability or valuation multiplier", c.source_mode || "Derived"],
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
      ["Climate alerts", fmtOptionalCount(s.climate_alerts)],
      ["Daily pressure index", fmtIndex100(s.daily_pressure)],
      ["Allocation overlay index", fmtIndex100(s.allocation_pressure)],
      ["Top driver", top.replace("_"," ")],
      ["Physical risk", fmtPct(ci.physical_score || 0)],
      ["Transition risk", fmtPct(ci.transition_score || 0)]
    ].map(c=>`<div class="signal-card"><div class="label">${c[0]}</div><div class="value">${c[1]}</div></div>`).join("");
  }
  const rows = d.latest_allocation || [];
  const table = document.getElementById("dailyImpactTable");
  table.innerHTML = `<tr><th>ETF</th><th>Long-Term Weight</th><th>Daily Overlay</th><th>Final Weight</th><th>NWS stress</th><th>Hazard beta</th><th>Driver</th><th>Source</th></tr>` +
    rows.map(r=>{
      const bps = Number(r.daily_adjustment_bps || 0);
      return `<tr>
        <td><b>${r.ticker}</b></td>
        <td>${fmtPct(r.base_climate_weight ?? r.climate_weight)}</td>
        <td class="${bps>=0?'green':'red'}"><b>${fmtBps(bps)}</b></td>
        <td><b>${fmtPct(r.climate_weight)}</b></td>
        <td>${Number(r.daily_sector_stress || 0).toFixed(3)}</td><td>${Number(r.daily_hazard_beta || 0).toFixed(3)}</td>
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
      ["Model-ensemble tail", fmtPct(summary.model_ensemble_tail_loss_rate || 0), "Mean of two worst conditional losses"],
      ["Worst scenario", worst.scenario || "-", fmtPct(worst.portfolio_loss_rate || 0)],
      ["Lowest modeled loss", best.scenario || "-", fmtPct(best.portfolio_loss_rate || 0)],
      ["Scenario loss range", fmtPct(summary.scenario_loss_range_rate || 0), `${fmtPct(summary.scenario_loss_min_rate || 0)} to ${fmtPct(summary.scenario_loss_max_rate || 0)}`],
      ["Physical model-risk band", `${fmtPct(summary.physical_model_risk_loss_floor || 0)} to ${fmtPct(summary.physical_model_risk_loss_ceiling || 0)}`, "0.70x-1.30x damage coefficients; sensitivity, not confidence interval"],
      ["Occurrence probability", "Not assigned", "Scenario severity only"],
      ["Metric definition", "Conditional value impact", "Project-calibrated sensitivity; not VaR or Expected Shortfall"]
    ].map(c=>`<div class="signal-card"><div class="label">${c[0]}</div><div class="value">${c[1]}</div><div class="hint">${c[2]}</div></div>`).join("");
  }
  const table = document.getElementById("scenarioTable");
  table.innerHTML = `<tr><th>Scenario</th><th>Interpretation</th><th>Carbon-price path</th><th>Value impact</th><th>Conditional loss sensitivity</th><th>Physical model-risk band</th><th>Largest Sector Loss</th><th>Narrative</th></tr>` +
    rows.map(r=>{
      const losses = Object.entries(r.sector_losses || {}).sort((a,b)=>b[1]-a[1]);
      const top = losses.length ? `${losses[0][0]} ${fmtPct(losses[0][1])}` : "-";
      return `<tr>
        <td><b>${r.scenario}</b></td><td><span class="pill info">${r.scenario_type || "Conditional stress"}</span><br><span class="hint">No occurrence probability assigned</span></td><td>${r.carbon_price_label || "Scenario endpoint"}</td>
        <td class="${clsFor(r.portfolio_value_impact || 0)}">${fmtSignedPct(r.portfolio_value_impact || 0)}</td><td>${fmtPct(r.portfolio_loss_rate)}<br><span class="hint">${fmtMoney(r.portfolio_loss_dollars)}</span></td>
        <td>${fmtPct(r.physical_model_risk_low_loss_rate || 0)} to ${fmtPct(r.physical_model_risk_high_loss_rate || 0)}<br><span class="hint">damage function 0.70x-1.30x</span></td>
        <td>${top}</td><td>${r.narrative}</td>
      </tr>`;
    }).join("");
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

window.addEventListener("resize",()=>{ if(DASH) renderDashboard(DASH); if(OPTIMIZER) renderOptimizer(OPTIMIZER); });
loadDashboard();
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
                    assumption_case=q.get("assumption_case", ["base"])[0],
                )
            )
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
        if parsed.path == "/api/daily_recommendation_backtest":
            q = parse_qs(parsed.query, keep_blank_values=True)
            self._send_json(
                daily_recommendation_backtest_payload(
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
    print(f"Jennison Climate-Risk Research Platform started: {url}")
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
