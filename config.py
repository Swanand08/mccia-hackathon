"""
config.py — Single source of truth for PackRight Industries AI Inventory System.
All other modules import from here. NEVER hardcode these values elsewhere.
"""
import os
import pandas as pd
from datetime import datetime

# ── Date (DYNAMIC — always uses real today) ──────────────────────────────────
TODAY = datetime.now()
FORECAST_HORIZON_DAYS = 42

# ── Credit constants ─────────────────────────────────────────────────────────
CREDIT_LIMIT = 3_000_000

def get_current_outstanding(data_dir="data"):
    """Read latest outstanding payables from working_capital_log.csv dynamically."""
    path = os.path.join(data_dir, "working_capital_log.csv")
    try:
        wc = pd.read_csv(path)
        wc.columns = wc.columns.str.strip()
        # Try multiple possible column names
        for col in ["outstanding_payables", "outstanding_payables_inr", "credit_utilized"]:
            if col in wc.columns:
                val = wc.iloc[-1][col]
                return int(float(str(val).replace(",", "")))
        raise ValueError(f"No outstanding payables column found. Columns: {wc.columns.tolist()}")
    except Exception as e:
        print(f"  WARNING: Could not read working capital log: {e}. Using fallback.")
        return 1_414_385  # Nov 2023 fallback only

# ── Material unit groups ──────────────────────────────────────────────────────
PAPER_MATERIALS = {"M01", "M02", "M03", "M04", "M05", "M13", "M14"}
CHEM_MATERIALS  = {"M06", "M07", "M08", "M09", "M10", "M11", "M12"}

PAPER_UNIT_MAP = {"rolls": "rolls", "Rolls": "rolls", "roll": "rolls", "nos": "rolls", "pcs": "rolls"}
CHEM_UNIT_MAP  = {"kg": "kg", "KG": "kg", "Kg": "kg", "kgs": "kg", "kilograms": "kg"}

# ── Average unit prices (₹) ───────────────────────────────────────────────────
AVG_PRICES = {
    "M01": 22850, "M02": 22929, "M03": 22660, "M04": 23096, "M05": 23887,
    "M06": 23333, "M07": 23379, "M08": 23620, "M09": 23057, "M10": 22613,
    "M11": 23756, "M12": 23087, "M13": 23547, "M14": 23128,
}

# ── Bill of Materials per product type ───────────────────────────────────────
BOM_MAP = {
    "small_std":      {"M01": 0.18, "M05": 0.12, "M06": 0.008, "M08": 0.015, "M11": 0.002, "M13": 0.05},
    "medium_std":     {"M01": 0.32, "M05": 0.22, "M06": 0.014, "M08": 0.025, "M11": 0.003, "M13": 0.08},
    "medium_printed": {"M02": 0.32, "M05": 0.22, "M06": 0.014, "M09": 0.006, "M10": 0.006, "M11": 0.003, "M13": 0.08},
    "small_printed":  {"M02": 0.18, "M05": 0.12, "M06": 0.008, "M09": 0.003, "M10": 0.003, "M11": 0.002, "M13": 0.05},
    "large_std":      {"M01": 0.55, "M05": 0.38, "M06": 0.022, "M08": 0.04,  "M11": 0.005, "M14": 0.12},
    "large_premium":  {"M04": 0.55, "M05": 0.38, "M07": 0.022, "M09": 0.008, "M10": 0.008, "M12": 0.004, "M14": 0.12},
}

# ── Seasonal index (read dynamically) ────────────────────────────────────────
def get_seasonal_multiplier(data_dir="data", month=None):
    """Get seasonal multiplier for given month (default: current month)."""
    if month is None:
        month = TODAY.month
    path = os.path.join(data_dir, "seasonal_index.csv")
    try:
        si = pd.read_csv(path)
        si.columns = si.columns.str.strip()
        col = "seasonal_multiplier" if "seasonal_multiplier" in si.columns else "fmcg_demand_multiplier"
        row = si[si["month"] == month]
        if len(row) == 0:
            raise ValueError(f"Month {month} not found in seasonal_index.csv")
        return float(row[col].values[0])
    except Exception as e:
        print(f"  WARNING: Could not read seasonal index: {e}. Using 1.0 fallback.")
        return 1.0
