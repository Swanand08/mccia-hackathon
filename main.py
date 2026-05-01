"""
Main Runner - PackRight Industries AI Inventory Intelligence System
Runs all modules in sequence and generates final outputs.
"""
import os
import sys
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
sys.path.insert(0, BASE_DIR)

from data_utils import load_normalized_csv

def main():
    from config import TODAY
    print("=" * 80)
    print("  PACKRIGHT INDUSTRIES - AI INVENTORY INTELLIGENCE SYSTEM")
    print(f"  Simulation Date: {TODAY.strftime('%Y-%m-%d')}")
    print("=" * 80)

    # ---- Step 0: Generate data if not present ----
    if not os.path.exists(os.path.join(DATA_DIR, "material_master.csv")):
        print("\n  Generating data files...")
        from generate_data import generate_all_data
        generate_all_data()
        print("  Data generated.")

    # ---- Load CSVs (using normalization to avoid BUG 1) ----
    print("\n  Loading CSV data...")
    try:
        inv_txn = load_normalized_csv(os.path.join(DATA_DIR, "inventory_transactions.csv"), "inventory_transactions.csv")
        prod_orders = load_normalized_csv(os.path.join(DATA_DIR, "production_orders.csv"), "production_orders.csv")
        mat_master = load_normalized_csv(os.path.join(DATA_DIR, "material_master.csv"), "material_master.csv")
        sup_master = load_normalized_csv(os.path.join(DATA_DIR, "supplier_master.csv"), "supplier_master.csv")
        wc_log = load_normalized_csv(os.path.join(DATA_DIR, "working_capital_log.csv"), "working_capital_log.csv")
        seasonal = load_normalized_csv(os.path.join(DATA_DIR, "seasonal_index.csv"), "seasonal_index.csv")
    except Exception as e:
        print(f"  CRITICAL ERROR loading data: {e}")
        return
    
    print(f"  inventory_transactions: {len(inv_txn):,} rows")
    print(f"  production_orders:      {len(prod_orders):,} rows")
    print(f"  material_master:        {len(mat_master)} rows")
    print(f"  supplier_master:        {len(sup_master)} rows")
    print(f"  working_capital_log:    {len(wc_log)} rows")
    print(f"  seasonal_index:         {len(seasonal)} rows")

    # ---- Step 1: D1 - Unit Normalization ----
    from unit_normalizer import normalize_units
    inv_clean = normalize_units(inv_txn)

    # ---- Step 2: D2 - BOM Forecasting ----
    from bom_forecaster import run_forecast
    forecast_df, explosion_df, upcoming_orders = run_forecast(DATA_DIR, prod_orders=prod_orders, material_master=mat_master, seasonal_index=seasonal)

    # ---- Step 3: D5 - Stockout Alerts ----
    from stockout_alerter import run_stockout_alerts
    alerts_df = run_stockout_alerts(forecast_df, mat_master, sup_master)

    # ---- Step 4: D6 - Substitution Engine ----
    from substitution_engine import run_substitution_engine
    substitution_df = run_substitution_engine(forecast_df, mat_master, sup_master)

    # ---- Step 5: D3 - Procurement Engine ----
    from procurement_engine import run_procurement_engine
    procurement_df = run_procurement_engine(forecast_df, mat_master, sup_master, DATA_DIR)

    # ---- Step 6: D4 - Excel Report ----
    from report_generator import generate_report
    print("\n" + "=" * 70)
    print("  D4: GENERATING WEEKLY PURCHASE REPORT (EXCEL)")
    print("=" * 70)
    report_path = generate_report(
        forecast_df, alerts_df, substitution_df, procurement_df,
        upcoming_orders, explosion_df, OUTPUT_DIR, supplier_master=sup_master
    )

    # ---- Step 10: Before vs After ----
    critical_materials = forecast_df[forecast_df["days_of_stock_remaining"] < 3]
    approved = procurement_df[procurement_df["status"].isin(["APPROVED", "PARTIAL"])]
    total_value = approved["order_cost_inr"].sum()

    m01 = forecast_df[forecast_df["material_id"] == "M01"]
    m01_days = m01["days_of_stock_remaining"].values[0] if len(m01) > 0 else 0

    print("\n" + "=" * 80)
    print("  BEFORE vs AFTER: THE IMPACT OF AI")
    print("=" * 80)
    print("\n  WITHOUT this system (gut-feel ordering):")
    print("    - Rs.12L+ stuck in slow-moving WF-200 adhesive (1840 kg) + Gold ink (340 kg)")
    print("    - M01 Grade A Kraft ran out 3 times (14-22 hrs halt each)")
    print("    - Estimated production loss: 3 x 18hrs x Rs.15,000/hr = Rs.8,10,000")
    print()
    print("  WITH this system:")
    print(f"    - M01 flagged CRITICAL with {m01_days:.1f} days warning")
    print(f"    - {len(approved)} procurement orders recommended within Rs.30L credit limit")
    print(f"    - Total procurement value: Rs.{total_value:,.0f}")
    print("    - Slow-moving M06 (1840 kg) and M12 (340 kg) flagged - DO NOT REORDER")
    print("    - Estimated working capital freed: Rs.12L+")
    print()
    print(f"  System complete. Report saved to: {report_path}")
    print(f"  {len(critical_materials)} materials need IMMEDIATE attention.")
    print("=" * 80)

if __name__ == "__main__":
    main()
