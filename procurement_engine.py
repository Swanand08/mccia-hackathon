"""
D3 — Procurement Recommendation Engine for PackRight Industries
"""
import pandas as pd
import math
import os

CREDIT_LIMIT = 3000000
CURRENT_OUTSTANDING = 1414385
AVG_PRICES = {
    "M01":22850,"M02":22929,"M03":22660,"M04":23096,"M05":23887,
    "M06":23333,"M07":23379,"M08":23620,"M09":23057,"M10":22613,
    "M11":23756,"M12":23087,"M13":23547,"M14":23128
}

def get_impact_factor(pay_terms):
    if pay_terms <= 30: return 1.0
    elif pay_terms <= 45: return 0.67
    else: return 0.50

def run_procurement_engine(forecast_df, material_master, supplier_master):
    print("\n" + "="*80)
    print("  D3: PROCUREMENT RECOMMENDATION ENGINE")
    print("="*80)
    remaining = CREDIT_LIMIT - CURRENT_OUTSTANDING
    print(f"\n  Credit Limit: Rs.{CREDIT_LIMIT:,} | Outstanding: Rs.{CURRENT_OUTSTANDING:,} | Available: Rs.{remaining:,}")

    sup_lookup = {}
    for _, sup in supplier_master.iterrows():
        for mat in sup["materials_supplied"].split(","):
            mat = mat.strip()
            if mat not in sup_lookup or sup["reliability_score"] > sup_lookup[mat]["reliability_score"]:
                sup_lookup[mat] = sup.to_dict()

    forecast_sorted = forecast_df.sort_values("days_of_stock_remaining").copy()
    recommendations = []
    running = CURRENT_OUTSTANDING

    for _, row in forecast_sorted.iterrows():
        mat_id = row["material_id"]
        cs = row["current_stock"]
        ad = row["adjusted_demand"]
        dr = row["days_of_stock_remaining"]
        unit = row["unit"]
        name = row["material_name"]
        order_raw = ad - cs

        if order_raw <= 0:
            recommendations.append({"priority":"—","material_id":mat_id,"name":name,
                "current_stock":cs,"adjusted_demand":ad,"order_qty_raw":0,"order_qty_moq":0,
                "unit":unit,"supplier_id":"—","supplier_name":"—","unit_price":AVG_PRICES.get(mat_id,0),
                "order_cost_inr":0,"payment_terms":"—","immediate_credit_impact":0,
                "cumulative_outstanding":running,"credit_remaining":CREDIT_LIMIT-running,
                "status":"SUFFICIENT","recommendation_reason":f"Stock({cs}) >= demand({ad:.1f})"})
            continue

        sup = sup_lookup.get(mat_id, {})
        sup_id = sup.get("supplier_id","N/A")
        sup_name = sup.get("supplier_name","N/A")
        moq = sup.get("moq",1)
        pay = sup.get("payment_terms_days",30)
        factor = get_impact_factor(pay)
        price = AVG_PRICES.get(mat_id,0)
        qty_moq = math.ceil(order_raw / moq) * moq
        cost = qty_moq * price
        impact = cost * factor

        if running + impact > CREDIT_LIMIT:
            min_impact = moq * price * factor
            if running + min_impact > CREDIT_LIMIT:
                status = "BLOCKED"
                recommendations.append({"priority":"HIGH" if dr<3 else "MED","material_id":mat_id,
                    "name":name,"current_stock":cs,"adjusted_demand":ad,"order_qty_raw":round(order_raw,2),
                    "order_qty_moq":0,"unit":unit,"supplier_id":sup_id,"supplier_name":sup_name,
                    "unit_price":price,"order_cost_inr":0,"payment_terms":f"{pay}d",
                    "immediate_credit_impact":0,"cumulative_outstanding":running,
                    "credit_remaining":CREDIT_LIMIT-running,"status":"BLOCKED",
                    "recommendation_reason":"Credit limit breach"})
                print(f"  BLOCKED {mat_id} {name}")
                continue
            max_moqs = 1
            for n in range(2, math.ceil(order_raw/moq)+1):
                if running + n*moq*price*factor <= CREDIT_LIMIT:
                    max_moqs = n
                else: break
            qty_moq = max_moqs * moq
            cost = qty_moq * price
            impact = cost * factor
            status = "PARTIAL"
        else:
            status = "APPROVED"

        running += impact
        pri = "HIGH" if dr < 3 else ("MED" if dr <= 7 else "LOW")
        recommendations.append({"priority":pri,"material_id":mat_id,"name":name,
            "current_stock":cs,"adjusted_demand":ad,"order_qty_raw":round(order_raw,2),
            "order_qty_moq":qty_moq,"unit":unit,"supplier_id":sup_id,"supplier_name":sup_name,
            "unit_price":price,"order_cost_inr":cost,"payment_terms":f"{pay}d",
            "immediate_credit_impact":round(impact,2),"cumulative_outstanding":round(running,2),
            "credit_remaining":round(CREDIT_LIMIT-running,2),"status":status,
            "recommendation_reason":f"Need {order_raw:.1f} -> MOQ {qty_moq} {unit}"})
        print(f"  {status} {mat_id} {name}: {qty_moq} {unit} | Cost Rs.{cost:,} | Impact Rs.{impact:,.0f} | Outstanding Rs.{running:,.0f}")

    rec_df = pd.DataFrame(recommendations)
    approved = rec_df[rec_df["status"].isin(["APPROVED","PARTIAL"])]
    print(f"\n  SUMMARY: {len(approved)} orders | Total Rs.{approved['order_cost_inr'].sum():,.0f} | Final outstanding Rs.{running:,.0f}")
    print("="*80)
    return rec_df

if __name__ == "__main__":
    from bom_forecaster import run_forecast
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    mat_master = pd.read_csv(os.path.join(DATA_DIR, "material_master.csv"))
    sup_master = pd.read_csv(os.path.join(DATA_DIR, "supplier_master.csv"))
    forecast, _, _ = run_forecast(DATA_DIR)
    run_procurement_engine(forecast, mat_master, sup_master)
