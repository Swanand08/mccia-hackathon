"""
D6 — Substitution Alert Engine for PackRight Industries
Identifies materials below reorder point and recommends substitutes.
"""
import pandas as pd
import os
from config import TODAY

def run_substitution_engine(forecast_df, material_master, supplier_master):
    """
    Check material stock against reorder points and recommend substitutes.
    
    Rules:
    1. Check material_master for substitute_material_ids
    2. If primary material stock < reorder_point and substitute exists:
       - Compute how much substitute is needed
       - Find supplier for substitute
       - Generate advisory
    3. Flag if BOTH primary and substitute are low
    """
    print("\n" + "="*70)
    print("  D6: SUBSTITUTION ALERT ENGINE")
    print("="*70)
    
    # Build supplier lookup
    sup_lookup = {}
    for _, sup in supplier_master.iterrows():
        for mat in sup["materials_supplied"].split(","):
            mat = mat.strip()
            if mat not in sup_lookup or sup["reliability_score"] > sup_lookup[mat]["reliability_score"]:
                sup_lookup[mat] = sup.to_dict()
    
    advisories = []
    
    for _, mat in material_master.iterrows():
        mat_id = mat["material_id"]
        current_stock = mat["current_stock"]
        reorder_point = mat["reorder_point"]
        substitute_ids = str(mat.get("substitute_material_ids", "")).strip()
        
        if current_stock >= reorder_point:
            continue  # No issue
        
        # Material is below reorder point
        shortfall = reorder_point - current_stock
        
        # Get forecast data
        fc = forecast_df[forecast_df["material_id"] == mat_id]
        adjusted_demand = fc["adjusted_demand"].values[0] if len(fc) > 0 else 0
        days_remaining = fc["days_of_stock_remaining"].values[0] if len(fc) > 0 else 999
        
        if not substitute_ids or substitute_ids == "" or substitute_ids == "nan":
            # No substitute available
            sup = sup_lookup.get(mat_id, {})
            advisories.append({
                "material_id": mat_id,
                "material_name": mat["material_name"],
                "current_stock": current_stock,
                "reorder_point": reorder_point,
                "shortfall_from_rop": shortfall,
                "days_remaining": days_remaining,
                "substitute_id": "NONE",
                "substitute_name": "N/A",
                "substitute_stock": "N/A",
                "substitute_status": "N/A",
                "action": f"ORDER {mat_id} from {sup.get('supplier_id', 'N/A')}",
                "advisory": f"No substitute available. Must order {mat_id} directly."
            })
            continue
        
        # Check substitute
        for sub_id in substitute_ids.split(","):
            sub_id = sub_id.strip()
            sub_mat = material_master[material_master["material_id"] == sub_id]
            
            if len(sub_mat) == 0:
                continue
            
            sub_mat = sub_mat.iloc[0]
            sub_stock = sub_mat["current_stock"]
            sub_rop = sub_mat["reorder_point"]
            
            sub_sup = sup_lookup.get(sub_id, {})
            primary_sup = sup_lookup.get(mat_id, {})
            
            both_low = sub_stock < sub_rop
            
            if both_low:
                status = "[!!] BOTH LOW"
                action = f"ORDER BOTH {mat_id} and {sub_id}"
                advisory = (f"CRITICAL: Both {mat_id} and substitute {sub_id} are below reorder point! "
                           f"Order both immediately.")
            elif sub_stock > adjusted_demand:
                status = "[OK] SUBSTITUTE AVAILABLE"
                action = f"Switch from {mat_id} to {sub_id}"
                sup_info = sub_sup
                advisory = (f"Switch from {mat_id} to {sub_id} - order {shortfall} {mat['unit']} from "
                           f"{sup_info.get('supplier_id', 'N/A')} ({sup_info.get('supplier_name', 'N/A')}) "
                           f"(lead {sup_info.get('lead_time_days', '?')} days, "
                           f"MOQ {sup_info.get('moq', '?')} {sup_info.get('moq_unit', '')}, "
                           f"reliability {sup_info.get('reliability_score', '?')})")
            else:
                status = "[!] PARTIAL"
                action = f"Use {sub_id} partially, order {mat_id}"
                advisory = (f"Substitute {sub_id} has {sub_stock} {sub_mat['unit']} "
                           f"(insufficient for full demand of {adjusted_demand:.1f}). "
                           f"Use partially and order {mat_id}.")
            
            advisories.append({
                "material_id": mat_id,
                "material_name": mat["material_name"],
                "current_stock": current_stock,
                "reorder_point": reorder_point,
                "shortfall_from_rop": shortfall,
                "days_remaining": days_remaining,
                "substitute_id": sub_id,
                "substitute_name": sub_mat["material_name"],
                "substitute_stock": sub_stock,
                "substitute_status": status,
                "action": action,
                "advisory": advisory
            })
    
    advisories_df = pd.DataFrame(advisories)
    
    if len(advisories_df) > 0:
        print(f"\n  Found {len(advisories_df)} substitution advisory/ies:\n")
        for _, adv in advisories_df.iterrows():
            print(f"  {'-'*60}")
            print(f"  Primary:    {adv['material_id']} {adv['material_name']}")
            print(f"  Stock:      {adv['current_stock']} (reorder point: {adv['reorder_point']})")
            print(f"  Days left:  {adv['days_remaining']}")
            print(f"  Substitute: {adv['substitute_id']} {adv['substitute_name']} (stock: {adv['substitute_stock']})")
            print(f"  Status:     {adv['substitute_status']}")
            print(f"  Action:     {adv['action']}")
            print(f"  Advisory:   {adv['advisory']}")
            print()
    else:
        print("\n  No materials below reorder point requiring substitution.\n")
    
    print("="*70)
    return advisories_df


if __name__ == "__main__":
    from bom_forecaster import run_forecast
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    mat_master = pd.read_csv(os.path.join(DATA_DIR, "material_master.csv"))
    sup_master = pd.read_csv(os.path.join(DATA_DIR, "supplier_master.csv"))
    forecast, _, _ = run_forecast(DATA_DIR)
    run_substitution_engine(forecast, mat_master, sup_master)
