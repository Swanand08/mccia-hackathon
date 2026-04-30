"""
D2 — BOM-Aware Demand Forecasting Module for PackRight Industries
Explodes BOMs from upcoming production orders and applies seasonal adjustment.
"""
import pandas as pd
import json
import os
from datetime import datetime, timedelta

TODAY = datetime(2023, 12, 1)
FORECAST_HORIZON_DAYS = 42  # 6 weeks
FORECAST_END = TODAY + timedelta(days=FORECAST_HORIZON_DAYS)

BOM_MAP = {
    "small_std": {"M01":0.18,"M05":0.12,"M06":0.008,"M08":0.015,"M11":0.002,"M13":0.05},
    "medium_std": {"M01":0.32,"M05":0.22,"M06":0.014,"M08":0.025,"M11":0.003,"M13":0.08},
    "medium_printed": {"M02":0.32,"M05":0.22,"M06":0.014,"M09":0.006,"M10":0.006,"M11":0.003,"M13":0.08},
    "small_printed": {"M02":0.18,"M05":0.12,"M06":0.008,"M09":0.003,"M10":0.003,"M11":0.002,"M13":0.05},
    "large_std": {"M01":0.55,"M05":0.38,"M06":0.022,"M08":0.04,"M11":0.005,"M14":0.12},
    "large_premium": {"M04":0.55,"M05":0.38,"M07":0.022,"M09":0.008,"M10":0.008,"M12":0.004,"M14":0.12},
}

def load_data(data_dir):
    prod_orders = pd.read_csv(os.path.join(data_dir, "production_orders.csv"))
    material_master = pd.read_csv(os.path.join(data_dir, "material_master.csv"))
    seasonal_index = pd.read_csv(os.path.join(data_dir, "seasonal_index.csv"))
    return prod_orders, material_master, seasonal_index

def get_upcoming_orders(prod_orders):
    """Step 2a: Filter upcoming orders within forecast horizon."""
    prod_orders["delivery_date"] = pd.to_datetime(prod_orders["delivery_date"])
    upcoming = prod_orders[
        (prod_orders["delivery_date"] >= TODAY) & 
        (prod_orders["delivery_date"] <= FORECAST_END)
    ].copy()
    return upcoming

def explode_bom(upcoming_orders):
    """Step 2b: BOM explosion — compute demand per material from each order."""
    explosion_rows = []
    
    for _, order in upcoming_orders.iterrows():
        bom = json.loads(order["material_bom"])
        for mat_id, coeff in bom.items():
            demand = order["quantity"] * coeff
            explosion_rows.append({
                "order_id": order["order_id"],
                "product_type": order["product_type"],
                "material_id": mat_id,
                "quantity": order["quantity"],
                "bom_coeff": coeff,
                "demand_contribution": round(demand, 4)
            })
    
    explosion_df = pd.DataFrame(explosion_rows)
    return explosion_df

def aggregate_demand(explosion_df):
    """Aggregate total raw demand per material."""
    agg = explosion_df.groupby("material_id").agg(
        raw_demand=("demand_contribution", "sum"),
        order_count=("order_id", "nunique")
    ).reset_index()
    agg["raw_demand"] = agg["raw_demand"].round(2)
    return agg

def apply_seasonal_adjustment(demand_df, seasonal_index):
    """Step 2c: Apply seasonal multiplier for current month (December)."""
    current_month = TODAY.month  # 12 = December
    multiplier = seasonal_index[seasonal_index["month"] == current_month]["seasonal_multiplier"].values[0]
    
    demand_df["seasonal_multiplier"] = multiplier
    demand_df["adjusted_demand"] = (demand_df["raw_demand"] * multiplier).round(2)
    return demand_df

def build_forecast_table(demand_df, material_master):
    """Step 2d: Build final forecast table with days-of-stock."""
    mat_info = material_master[["material_id", "material_name", "current_stock", "unit"]].copy()
    
    # Ensure all materials are in the forecast (even those with 0 demand)
    all_materials = mat_info.copy()
    forecast = all_materials.merge(demand_df, on="material_id", how="left")
    forecast["raw_demand"] = forecast["raw_demand"].fillna(0)
    forecast["adjusted_demand"] = forecast["adjusted_demand"].fillna(0)
    forecast["seasonal_multiplier"] = forecast["seasonal_multiplier"].fillna(demand_df["seasonal_multiplier"].iloc[0] if len(demand_df) > 0 else 1.40)
    forecast["order_count"] = forecast["order_count"].fillna(0).astype(int)
    
    # Days of stock remaining
    forecast["daily_demand"] = (forecast["adjusted_demand"] / 28).round(4)
    forecast["days_of_stock_remaining"] = forecast.apply(
        lambda r: round(r["current_stock"] / r["daily_demand"], 1) if r["daily_demand"] > 0 else 999, axis=1
    )
    
    # Traffic light flags
    def flag(days):
        if days < 3:
            return "🔴 CRITICAL"
        elif days <= 7:
            return "🟡 WARNING"
        else:
            return "🟢 OK"
    
    forecast["status"] = forecast["days_of_stock_remaining"].apply(flag)
    
    return forecast

def run_forecast(data_dir):
    """Main forecasting pipeline."""
    prod_orders, material_master, seasonal_index = load_data(data_dir)
    
    # Step 2a
    upcoming = get_upcoming_orders(prod_orders)
    
    print("\n" + "="*70)
    print("  D2: BOM-AWARE DEMAND FORECASTING")
    print("="*70)
    print(f"\n  Today's date:       {TODAY.strftime('%Y-%m-%d')}")
    print(f"  Forecast horizon:   {FORECAST_HORIZON_DAYS} days (until {FORECAST_END.strftime('%Y-%m-%d')})")
    print(f"  Upcoming orders:    {len(upcoming)}")
    
    # Step 2b
    explosion_df = explode_bom(upcoming)
    
    print(f"\n  BOM Explosion: {len(explosion_df)} line items from {len(upcoming)} orders")
    print(f"\n  Sample BOM explosion (first 10 rows):")
    print(explosion_df.head(10).to_string(index=False))
    
    # Aggregate
    demand_agg = aggregate_demand(explosion_df)
    
    # Step 2c
    demand_adj = apply_seasonal_adjustment(demand_agg, seasonal_index)
    
    # Step 2d
    forecast = build_forecast_table(demand_adj, material_master)
    
    print(f"\n\n  {'='*90}")
    print(f"  FORECAST TABLE (Seasonal Multiplier: {forecast['seasonal_multiplier'].iloc[0]}x for December)")
    print(f"  {'='*90}")
    
    display_cols = ["material_id", "material_name", "raw_demand", "seasonal_multiplier", 
                    "adjusted_demand", "unit", "current_stock", "daily_demand",
                    "days_of_stock_remaining", "status"]
    
    # Sort by days remaining
    forecast_sorted = forecast.sort_values("days_of_stock_remaining")
    print(forecast_sorted[display_cols].to_string(index=False))
    
    critical = forecast[forecast["days_of_stock_remaining"] < 3]
    warning = forecast[(forecast["days_of_stock_remaining"] >= 3) & (forecast["days_of_stock_remaining"] <= 7)]
    
    print(f"\n  Summary: {len(critical)} CRITICAL 🔴 | {len(warning)} WARNING 🟡 | {len(forecast) - len(critical) - len(warning)} OK 🟢")
    print("="*70)
    
    return forecast, explosion_df, upcoming


if __name__ == "__main__":
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    forecast, explosion, upcoming = run_forecast(DATA_DIR)
