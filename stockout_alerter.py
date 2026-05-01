"""
D5 — Stockout Risk Alert Engine for PackRight Industries
Identifies materials at risk of stockout within 21-day horizon.
"""
import pandas as pd
import os
from config import TODAY

def run_stockout_alerts(forecast_df, material_master, supplier_master):
    """
    Generate stockout risk alerts based on BOM forecast.
    
    For each material:
    1. Compute daily_demand from BOM forecast (adjusted_demand / 28)
    2. days_of_stock = current_stock / daily_demand
    3. If days_of_stock < 3: CRITICAL ALERT 🔴
    4. Compute 21-day need and shortfall
    """
    print("\n" + "="*70)
    print("  D5: STOCKOUT RISK ALERTS")
    print("="*70)
    
    alerts = []
    
    # Build supplier lookup
    sup_lookup = {}
    for _, sup in supplier_master.iterrows():
        for mat in sup["materials_supplied"].split(","):
            mat = mat.strip()
            if mat not in sup_lookup or sup["reliability_score"] > sup_lookup[mat]["reliability_score"]:
                sup_lookup[mat] = sup
    
    for _, row in forecast_df.iterrows():
        mat_id = row["material_id"]
        current_stock = row["current_stock"]
        daily_demand = row.get("daily_demand", 0)
        adjusted_demand = row.get("adjusted_demand", 0)
        
        if daily_demand <= 0:
            days_remaining = 999
            need_21d = 0
        else:
            days_remaining = round(current_stock / daily_demand, 1)
            need_21d = round(daily_demand * 21, 2)
        
        shortfall = round(max(0, need_21d - current_stock), 2)
        
        if days_remaining < 3:
            alert_level = "CRITICAL"
        elif days_remaining <= 7:
            alert_level = "WARNING"
        else:
            alert_level = "OK"
        
        sup = sup_lookup.get(mat_id, {})
        sup_id = sup.get("supplier_id", "N/A") if isinstance(sup, dict) or isinstance(sup, pd.Series) else "N/A"
        lead_time = sup.get("lead_time_days", "N/A") if isinstance(sup, dict) or isinstance(sup, pd.Series) else "N/A"
        
        if isinstance(sup, pd.Series):
            sup_id = sup["supplier_id"]
            lead_time = sup["lead_time_days"]
        
        alerts.append({
            "material_id": mat_id,
            "name": row["material_name"],
            "current_stock": current_stock,
            "unit": row["unit"],
            "daily_demand": daily_demand,
            "days_remaining": days_remaining,
            "21d_need": need_21d,
            "shortfall": shortfall,
            "alert_level": alert_level,
            "supplier": sup_id,
            "lead_time_days": lead_time
        })
    
    alerts_df = pd.DataFrame(alerts)
    alerts_df = alerts_df.sort_values("days_remaining")
    
    # Print alerts
    critical = alerts_df[alerts_df["alert_level"].str.contains("CRITICAL")]
    warning = alerts_df[alerts_df["alert_level"].str.contains("WARNING")]
    
    if len(critical) > 0:
        print(f"\n  [!!] {len(critical)} CRITICAL STOCKOUT ALERT(S)!")
        print("  " + "-"*60)
        for _, a in critical.iterrows():
            print(f"  [!!] {a['material_id']} {a['name']}: {a['current_stock']} {a['unit']} remaining")
            print(f"     Daily demand: {a['daily_demand']:.2f} {a['unit']}/day -> Only {a['days_remaining']} days left!")
            print(f"     21-day need: {a['21d_need']:.2f} {a['unit']} | Shortfall: {a['shortfall']:.2f} {a['unit']}")
            print(f"     Supplier: {a['supplier']} | Lead time: {a['lead_time_days']} days")
            
            # Special rule: if M01 is flagged, show M02 as backup
            if a["material_id"] == "M01":
                m02 = alerts_df[alerts_df["material_id"] == "M02"]
                if len(m02) > 0:
                    m02_row = m02.iloc[0]
                    print(f"     [INFO] BACKUP: M02 {m02_row['name']} has {m02_row['current_stock']} {m02_row['unit']} in stock")
            print()
    
    if len(warning) > 0:
        print(f"\n  [!] {len(warning)} WARNING ALERT(S):")
        print("  " + "-"*60)
        for _, a in warning.iterrows():
            print(f"  [!] {a['material_id']} {a['name']}: {a['days_remaining']} days remaining")
    
    print(f"\n  Full Alert Table:")
    print(alerts_df.to_string(index=False))
    print("\n" + "="*70)
    
    return alerts_df


if __name__ == "__main__":
    from bom_forecaster import run_forecast
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    mat_master = pd.read_csv(os.path.join(DATA_DIR, "material_master.csv"))
    sup_master = pd.read_csv(os.path.join(DATA_DIR, "supplier_master.csv"))
    forecast, _, _ = run_forecast(DATA_DIR)
    run_stockout_alerts(forecast, mat_master, sup_master)
