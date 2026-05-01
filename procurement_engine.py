"""
D3 - Procurement Recommendation Engine for PackRight Industries
All constants imported from config.py. Working capital read dynamically.
"""
import pandas as pd
import math
import os
from config import CREDIT_LIMIT, AVG_PRICES, get_current_outstanding

def get_impact_factor(pay_terms):
    try:
        pay_terms = float(pay_terms)
    except:
        pay_terms = 30
    if pay_terms <= 30:   return 1.0
    elif pay_terms <= 45: return 0.67
    else:                 return 0.50

def run_procurement_engine(forecast_df, material_master, supplier_master, data_dir="data"):
    # FIXED: reads outstanding dynamically from CSV, not hardcoded
    current_outstanding = get_current_outstanding(data_dir)

    print("\n" + "="*80)
    print("  D3: PROCUREMENT RECOMMENDATION ENGINE")
    print("="*80)
    remaining = CREDIT_LIMIT - current_outstanding
    print(f"\n  Credit Limit  : Rs.{CREDIT_LIMIT:,}")
    print(f"  Outstanding   : Rs.{current_outstanding:,} (read from working_capital_log.csv)")
    print(f"  Available     : Rs.{remaining:,}")

    # Build supplier lookup - prefer higher reliability
    sup_lookup = {}
    for _, sup in supplier_master.iterrows():
        for mat in str(sup.get("materials_supplied","")).split(","):
            mat = mat.strip()
            if not mat: continue
            if mat not in sup_lookup or float(sup.get("reliability_score",0)) > float(sup_lookup[mat].get("reliability_score",0)):
                sup_lookup[mat] = sup.to_dict()

    forecast_sorted = forecast_df.sort_values("days_of_stock_remaining").copy()
    recommendations = []
    running = current_outstanding

    for _, row in forecast_sorted.iterrows():
        mat_id     = row["material_id"]
        cs         = row["current_stock"]
        ad         = row["adjusted_demand"]
        dr         = row["days_of_stock_remaining"]
        unit       = row["unit"]
        name       = row["material_name"]
        order_raw  = max(ad, row.get("reorder_point", 0)) - cs
        excess     = row.get("excess_stock", False)

        base = {
            "material_id": mat_id, "name": name, "current_stock": cs,
            "adjusted_demand": ad, "unit": unit, "order_qty_raw": round(order_raw, 2),
            "cumulative_outstanding": running, "credit_remaining": CREDIT_LIMIT - running,
        }

        if order_raw <= 0 or excess:
            reason = f"Stock({cs}) >= demand({ad:.1f})" if order_raw <= 0 else f"EXCESS: {cs} units vs demand {ad:.1f}"
            recommendations.append({**base, "priority":"-","order_qty_moq":0,
                "supplier_id":"-","supplier_name":"-","unit_price":AVG_PRICES.get(mat_id,0),
                "order_cost_inr":0,"payment_terms":"-","immediate_credit_impact":0,
                "status":"SUFFICIENT" if order_raw<=0 else "EXCESS - DO NOT ORDER",
                "recommendation_reason": reason})
            continue

        sup      = sup_lookup.get(mat_id, {})
        sup_id   = sup.get("supplier_id","N/A")
        sup_name = sup.get("supplier_name","N/A")
        moq      = float(sup.get("moq", 1))
        pay      = float(sup.get("payment_terms_days", 30))
        lead     = sup.get("lead_time_days", "?")
        factor   = get_impact_factor(pay)
        price    = AVG_PRICES.get(mat_id, 0)

        qty_moq  = math.ceil(order_raw / moq) * moq
        cost     = qty_moq * price
        impact   = cost * factor

        if running + impact > CREDIT_LIMIT:
            min_impact = moq * price * factor
            if running + min_impact > CREDIT_LIMIT:
                recommendations.append({**base, "priority":"HIGH" if dr<3 else "MED",
                    "order_qty_moq":0,"supplier_id":sup_id,"supplier_name":sup_name,
                    "unit_price":price,"order_cost_inr":0,"payment_terms":f"{int(pay)}d",
                    "immediate_credit_impact":0,"status":"BLOCKED",
                    "recommendation_reason":f"Credit limit breach - even 1 MOQ ({moq} {unit}) = Rs.{moq*price*factor:,.0f} impact"})
                print(f"  [!!] BLOCKED   {mat_id} {name:<25} - credit limit breach")
                continue
            max_moqs = 1
            for n in range(2, math.ceil(order_raw/moq)+2):
                if running + n*moq*price*factor <= CREDIT_LIMIT:
                    max_moqs = n
                else:
                    break
            qty_moq = max_moqs * moq
            cost    = qty_moq * price
            impact  = cost * factor
            status  = "PARTIAL"
        else:
            status  = "APPROVED"

        running += impact
        pri = "HIGH" if dr < 3 else ("MED" if dr <= 7 else "LOW")
        recommendations.append({**base, "priority":pri,
            "order_qty_moq":qty_moq,"supplier_id":sup_id,"supplier_name":sup_name,
            "unit_price":price,"order_cost_inr":cost,"payment_terms":f"{int(pay)}d",
            "immediate_credit_impact":round(impact,2),
            "cumulative_outstanding":round(running,2),
            "credit_remaining":round(CREDIT_LIMIT-running,2),
            "status":status,
            "recommendation_reason":f"Need {order_raw:.1f} → MOQ {qty_moq} {unit} | Lead {lead}d"})
        icon = "[OK]" if status=="APPROVED" else "[!!]"
        print(f"  {icon} {status:<8} {mat_id} {name:<22} {qty_moq:>5} {unit:<6} Rs.{cost:>10,.0f} | Credit left: Rs.{CREDIT_LIMIT-running:,.0f}")

    rec_df   = pd.DataFrame(recommendations)
    approved = rec_df[rec_df["status"].isin(["APPROVED","PARTIAL"])]
    blocked  = rec_df[rec_df["status"]=="BLOCKED"]
    excess   = rec_df[rec_df["status"].str.contains("EXCESS", na=False)]

    print(f"\n  SUMMARY: {len(approved)} approved | {len(blocked)} blocked | {len(excess)} excess (do not order)")
    print(f"  Total order value  : Rs.{approved['order_cost_inr'].sum():,.0f}")
    print(f"  Final outstanding  : Rs.{running:,.0f} / Rs.{CREDIT_LIMIT:,}")
    print("="*80)
    return rec_df

if __name__ == "__main__":
    from bom_forecaster import run_forecast
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    mat_master = pd.read_csv(os.path.join(DATA_DIR, "material_master.csv"))
    sup_master = pd.read_csv(os.path.join(DATA_DIR, "supplier_master.csv"))
    forecast, _, _ = run_forecast(DATA_DIR)
    run_procurement_engine(forecast, mat_master, sup_master, DATA_DIR)
