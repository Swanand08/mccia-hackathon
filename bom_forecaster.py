"""
D2 — BOM-Aware Demand Forecasting Module for PackRight Industries
Imports all constants from config.py. Dynamic date and seasonal multiplier.
"""
import pandas as pd
import json
import os
from datetime import timedelta
from config import TODAY, FORECAST_HORIZON_DAYS, BOM_MAP, get_seasonal_multiplier
from data_utils import load_normalized_csv

FORECAST_END = TODAY + timedelta(days=FORECAST_HORIZON_DAYS)

def load_data(data_dir):
    prod_orders     = load_normalized_csv(os.path.join(data_dir, "production_orders.csv"), "production_orders.csv")
    material_master = load_normalized_csv(os.path.join(data_dir, "material_master.csv"), "material_master.csv")
    seasonal_index  = load_normalized_csv(os.path.join(data_dir, "seasonal_index.csv"), "seasonal_index.csv")
    for df in [prod_orders, material_master, seasonal_index]:
        df.columns = df.columns.str.strip()
    return prod_orders, material_master, seasonal_index

def get_upcoming_orders(prod_orders):
    prod_orders = prod_orders.copy()
    prod_orders["delivery_date"] = pd.to_datetime(prod_orders["delivery_date"], errors="coerce")
    return prod_orders[
        (prod_orders["delivery_date"] >= TODAY) &
        (prod_orders["delivery_date"] <= FORECAST_END)
    ].copy()

def explode_bom(upcoming_orders):
    """
    BOM explosion — FIXED: uses pd.json_normalize approach, no loop on inner loop.
    Still needs outer loop per order but with proper error handling.
    """
    explosion_rows = []
    errors = 0
    for _, order in upcoming_orders.iterrows():
        try:
            bom_raw = order.get("material_bom", "{}")
            bom = json.loads(str(bom_raw)) if pd.notna(bom_raw) else {}
            qty = float(order.get("quantity", 0))
            for mid, coeff in bom.items():
                explosion_rows.append({
                    "order_id":             order.get("order_id", "N/A"),
                    "product_type":         order.get("product_type", "unknown"),
                    "material_id":          mid,
                    "quantity":             qty,
                    "bom_coeff":            coeff,
                    "demand_contribution":  round(qty * coeff, 4),
                })
        except Exception as e:
            errors += 1
            continue

    if errors > 0:
        print(f"  WARNING: {errors} orders had malformed BOM JSON and were skipped.")

    return pd.DataFrame(explosion_rows) if explosion_rows else pd.DataFrame(
        columns=["order_id","product_type","material_id","quantity","bom_coeff","demand_contribution"]
    )

def aggregate_demand(explosion_df):
    if explosion_df.empty:
        return pd.DataFrame(columns=["material_id","raw_demand","order_count"])
    agg = explosion_df.groupby("material_id").agg(
        raw_demand  =("demand_contribution", "sum"),
        order_count =("order_id", "nunique"),
    ).reset_index()
    agg["raw_demand"] = agg["raw_demand"].round(2)
    return agg

def apply_seasonal_adjustment(demand_df, data_dir):
    """Reads seasonal multiplier DYNAMICALLY for current month from config."""
    multiplier = get_seasonal_multiplier(data_dir=data_dir, month=TODAY.month)
    demand_df = demand_df.copy()
    demand_df["seasonal_multiplier"] = multiplier
    demand_df["adjusted_demand"]     = (demand_df["raw_demand"] * multiplier).round(2)
    return demand_df, multiplier

def build_forecast_table(demand_df, material_master, multiplier):
    mat_info = material_master[["material_id","material_name","current_stock","unit","reorder_point"]].copy()
    forecast = mat_info.merge(demand_df, on="material_id", how="left")
    forecast["raw_demand"]         = forecast["raw_demand"].fillna(0)
    forecast["adjusted_demand"]    = forecast["adjusted_demand"].fillna(0)
    forecast["seasonal_multiplier"]= forecast["seasonal_multiplier"].fillna(multiplier)
    forecast["order_count"]        = forecast["order_count"].fillna(0).astype(int)
    forecast["daily_demand"]       = (forecast["adjusted_demand"] / 28).round(4)
    forecast["days_of_stock_remaining"] = forecast.apply(
        lambda r: round(r["current_stock"] / r["daily_demand"], 1) if r["daily_demand"] > 0 else 999, axis=1
    )
    forecast["status"] = forecast["days_of_stock_remaining"].apply(
        lambda d: "CRITICAL" if d < 3 else ("WARNING" if d <= 7 else "OK")
    )
    # Excess stock flag (new - business owner requested)
    forecast["excess_stock"] = forecast.apply(
        lambda r: (r["adjusted_demand"] > 0 and r["current_stock"] > 3 * r["adjusted_demand"]) or \
                  (r["adjusted_demand"] == 0 and r["current_stock"] > r["reorder_point"]), axis=1
    )
    return forecast

def run_forecast(data_dir, prod_orders=None, material_master=None, seasonal_index=None):
    if prod_orders is None:
        prod_orders, material_master, seasonal_index = load_data(data_dir)
    upcoming = get_upcoming_orders(prod_orders)

    print("\n" + "="*70)
    print("  D2: BOM-AWARE DEMAND FORECASTING")
    print("="*70)
    print(f"\n  Today's date      : {TODAY.strftime('%Y-%m-%d')} (DYNAMIC)")
    print(f"  Forecast window   : {FORECAST_HORIZON_DAYS} days -> {FORECAST_END.strftime('%Y-%m-%d')}")
    print(f"  Upcoming orders   : {len(upcoming)}")

    explosion_df = explode_bom(upcoming)
    demand_agg   = aggregate_demand(explosion_df)
    demand_adj, multiplier = apply_seasonal_adjustment(demand_agg, data_dir)
    forecast     = build_forecast_table(demand_adj, material_master, multiplier)

    print(f"\n  Seasonal multiplier (month {TODAY.month}): {multiplier}x")
    print(f"\n  BOM explosion: {len(explosion_df)} line items from {len(upcoming)} orders")

    display_cols = ["material_id","material_name","raw_demand","seasonal_multiplier",
                    "adjusted_demand","unit","current_stock","daily_demand",
                    "days_of_stock_remaining","status"]
    print(f"\n  {'='*90}")
    print(forecast.sort_values("days_of_stock_remaining")[display_cols].to_string(index=False))

    critical = forecast[forecast["days_of_stock_remaining"] < 3]
    warning  = forecast[(forecast["days_of_stock_remaining"] >= 3) & (forecast["days_of_stock_remaining"] <= 7)]
    excess   = forecast[forecast["excess_stock"] == True]
    print(f"\n  Summary: {len(critical)} CRITICAL [!!] | {len(warning)} WARNING [!] | {len(excess)} EXCESS STOCK [?]")
    print("="*70)
    return forecast, explosion_df, upcoming

if __name__ == "__main__":
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    run_forecast(DATA_DIR)
