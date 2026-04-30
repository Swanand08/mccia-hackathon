"""
PackRight Industries — AI Inventory Intelligence Dashboard (Streamlit)
"""
import streamlit as st
import pandas as pd
import os
import sys
import json
import math
import plotly.express as px
import google.generativeai as genai
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
sys.path.insert(0, BASE_DIR)

TODAY = datetime(2023, 12, 1)
CREDIT_LIMIT = 3000000
CURRENT_OUTSTANDING = 1414385

AVG_PRICES = {
    "M01":22850,"M02":22929,"M03":22660,"M04":23096,"M05":23887,
    "M06":23333,"M07":23379,"M08":23620,"M09":23057,"M10":22613,
    "M11":23756,"M12":23087,"M13":23547,"M14":23128
}

BOM_MAP = {
    "small_std":{"M01":0.18,"M05":0.12,"M06":0.008,"M08":0.015,"M11":0.002,"M13":0.05},
    "medium_std":{"M01":0.32,"M05":0.22,"M06":0.014,"M08":0.025,"M11":0.003,"M13":0.08},
    "medium_printed":{"M02":0.32,"M05":0.22,"M06":0.014,"M09":0.006,"M10":0.006,"M11":0.003,"M13":0.08},
    "small_printed":{"M02":0.18,"M05":0.12,"M06":0.008,"M09":0.003,"M10":0.003,"M11":0.002,"M13":0.05},
    "large_std":{"M01":0.55,"M05":0.38,"M06":0.022,"M08":0.04,"M11":0.005,"M14":0.12},
    "large_premium":{"M04":0.55,"M05":0.38,"M07":0.022,"M09":0.008,"M10":0.008,"M12":0.004,"M14":0.12},
}

# ============================================================
# Data Loading & Processing (cached)
# ============================================================
@st.cache_data
def load_and_process():
    mat_master = pd.read_csv(os.path.join(DATA_DIR, "material_master.csv"))
    sup_master = pd.read_csv(os.path.join(DATA_DIR, "supplier_master.csv"))
    prod_orders = pd.read_csv(os.path.join(DATA_DIR, "production_orders.csv"))
    seasonal = pd.read_csv(os.path.join(DATA_DIR, "seasonal_index.csv"))
    wc_log = pd.read_csv(os.path.join(DATA_DIR, "working_capital_log.csv"))

    # BOM Forecast
    prod_orders["delivery_date"] = pd.to_datetime(prod_orders["delivery_date"])
    end = TODAY + timedelta(days=42)
    upcoming = prod_orders[(prod_orders["delivery_date"] >= TODAY) & (prod_orders["delivery_date"] <= end)]
    
    explosion_rows = []
    for _, order in upcoming.iterrows():
        bom = json.loads(order["material_bom"])
        for mid, coeff in bom.items():
            explosion_rows.append({"order_id":order["order_id"],"material_id":mid,
                "quantity":order["quantity"],"bom_coeff":coeff,
                "demand_contribution":round(order["quantity"]*coeff,4)})
    explosion_df = pd.DataFrame(explosion_rows)
    
    demand_agg = explosion_df.groupby("material_id").agg(
        raw_demand=("demand_contribution","sum"), order_count=("order_id","nunique")).reset_index()
    demand_agg["raw_demand"] = demand_agg["raw_demand"].round(2)
    multiplier = 1.40
    demand_agg["seasonal_multiplier"] = multiplier
    demand_agg["adjusted_demand"] = (demand_agg["raw_demand"] * multiplier).round(2)
    
    mat_info = mat_master[["material_id","material_name","current_stock","unit","reorder_point"]].copy()
    forecast = mat_info.merge(demand_agg, on="material_id", how="left")
    forecast["raw_demand"] = forecast["raw_demand"].fillna(0)
    forecast["adjusted_demand"] = forecast["adjusted_demand"].fillna(0)
    forecast["seasonal_multiplier"] = forecast["seasonal_multiplier"].fillna(multiplier)
    forecast["order_count"] = forecast["order_count"].fillna(0).astype(int)
    forecast["daily_demand"] = (forecast["adjusted_demand"]/28).round(4)
    forecast["days_of_stock_remaining"] = forecast.apply(
        lambda r: round(r["current_stock"]/r["daily_demand"],1) if r["daily_demand"]>0 else 999, axis=1)
    forecast["status"] = forecast["days_of_stock_remaining"].apply(
        lambda d: "🔴 CRITICAL" if d<3 else ("🟡 WARNING" if d<=7 else "🟢 OK"))

    # Stockout Alerts
    sup_lookup = {}
    for _, s in sup_master.iterrows():
        for m in s["materials_supplied"].split(","):
            m = m.strip()
            if m not in sup_lookup or s["reliability_score"] > sup_lookup[m]["reliability_score"]:
                sup_lookup[m] = s.to_dict()
    
    alerts = []
    for _, row in forecast.iterrows():
        dd = row["daily_demand"]
        dr = row["days_of_stock_remaining"]
        n21 = round(dd*21,2)
        sf = round(max(0, n21-row["current_stock"]),2)
        sup = sup_lookup.get(row["material_id"],{})
        alerts.append({"material_id":row["material_id"],"name":row["material_name"],
            "current_stock":row["current_stock"],"unit":row["unit"],"daily_demand":dd,
            "days_remaining":dr,"21d_need":n21,"shortfall":sf,
            "alert_level":"🔴 CRITICAL" if dr<3 else ("🟡 WARNING" if dr<=7 else "🟢 OK"),
            "supplier":sup.get("supplier_id","N/A"),"lead_time_days":sup.get("lead_time_days","N/A")})
    alerts_df = pd.DataFrame(alerts).sort_values("days_remaining")

    # Procurement
    def get_factor(pt):
        if pt<=30: return 1.0
        elif pt<=45: return 0.67
        else: return 0.50
    
    recs = []
    running = CURRENT_OUTSTANDING
    for _, row in forecast.sort_values("days_of_stock_remaining").iterrows():
        mid = row["material_id"]
        cs = row["current_stock"]
        ad = row["adjusted_demand"]
        dr = row["days_of_stock_remaining"]
        oraw = ad - cs
        if oraw <= 0:
            recs.append({"material_id":mid,"name":row["material_name"],"current_stock":cs,
                "adjusted_demand":ad,"order_qty_moq":0,"unit":row["unit"],"supplier_id":"—",
                "supplier_name":"—","order_cost_inr":0,"payment_terms":"—",
                "immediate_credit_impact":0,"cumulative_outstanding":running,
                "credit_remaining":CREDIT_LIMIT-running,"status":"SUFFICIENT","priority":"—"})
            continue
        sup = sup_lookup.get(mid,{})
        moq = sup.get("moq",1)
        pt = sup.get("payment_terms_days",30)
        factor = get_factor(pt)
        price = AVG_PRICES.get(mid,0)
        qty = math.ceil(oraw/moq)*moq
        cost = qty*price
        impact = cost*factor
        if running+impact > CREDIT_LIMIT:
            mi = moq*price*factor
            if running+mi > CREDIT_LIMIT:
                recs.append({"material_id":mid,"name":row["material_name"],"current_stock":cs,
                    "adjusted_demand":ad,"order_qty_moq":0,"unit":row["unit"],
                    "supplier_id":sup.get("supplier_id","?"),"supplier_name":sup.get("supplier_name","?"),
                    "order_cost_inr":0,"payment_terms":f"{pt}d","immediate_credit_impact":0,
                    "cumulative_outstanding":running,"credit_remaining":CREDIT_LIMIT-running,
                    "status":"BLOCKED","priority":"HIGH" if dr<3 else "MED"})
                continue
            mx = 1
            for n in range(2, math.ceil(oraw/moq)+1):
                if running+n*moq*price*factor<=CREDIT_LIMIT: mx=n
                else: break
            qty=mx*moq; cost=qty*price; impact=cost*factor
            status="PARTIAL"
        else:
            status="APPROVED"
        running += impact
        recs.append({"material_id":mid,"name":row["material_name"],"current_stock":cs,
            "adjusted_demand":ad,"order_qty_moq":qty,"unit":row["unit"],
            "supplier_id":sup.get("supplier_id","?"),"supplier_name":sup.get("supplier_name","?"),
            "order_cost_inr":cost,"payment_terms":f"{pt}d","immediate_credit_impact":round(impact,2),
            "cumulative_outstanding":round(running,2),"credit_remaining":round(CREDIT_LIMIT-running,2),
            "status":status,"priority":"HIGH" if dr<3 else ("MED" if dr<=7 else "LOW")})
    
    proc_df = pd.DataFrame(recs)

    # Substitution
    subs = []
    for _, m in mat_master.iterrows():
        sid = str(m.get("substitute_material_ids","")).strip()
        if m["current_stock"] >= m["reorder_point"] or not sid or sid=="nan": continue
        for sub_id in sid.split(","):
            sub_id = sub_id.strip()
            sub = mat_master[mat_master["material_id"]==sub_id]
            if len(sub)==0: continue
            sub = sub.iloc[0]
            subs.append({"primary":m["material_id"],"primary_name":m["material_name"],
                "primary_stock":m["current_stock"],"reorder_point":m["reorder_point"],
                "substitute":sub_id,"substitute_name":sub["material_name"],
                "substitute_stock":sub["current_stock"],
                "both_low":"YES" if sub["current_stock"]<sub["reorder_point"] else "NO"})
    subs_df = pd.DataFrame(subs)

    return forecast, alerts_df, proc_df, subs_df, explosion_df, mat_master, sup_master

# ============================================================
# Streamlit App
# ============================================================
st.set_page_config(page_title="PackRight AI Inventory", page_icon="📦", layout="wide")

# Custom CSS
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .metric-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #0f3460;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .metric-value { font-size: 28px; font-weight: bold; }
    .metric-label { font-size: 14px; color: #8892b0; margin-top: 5px; }
    .critical-banner {
        background: linear-gradient(90deg, #ff0000 0%, #cc0000 100%);
        color: white; padding: 15px; border-radius: 8px;
        font-weight: bold; font-size: 16px; margin: 10px 0;
    }
    .status-dot-red { color: #ff4444; font-size: 24px; }
    .status-dot-yellow { color: #ffaa00; font-size: 24px; }
    .status-dot-green { color: #44ff44; font-size: 24px; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1a2e; border-radius: 8px 8px 0 0;
        padding: 10px 20px; color: #8892b0;
    }
    .stTabs [aria-selected="true"] {
        background-color: #0f3460; color: #e6f1ff;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("## 📦 PackRight AI")
    st.markdown("### Inventory Intelligence System")
    st.markdown(f"**Date:** {TODAY.strftime('%d %B %Y')}")
    st.markdown("---")
    st.markdown("**PackRight Industries, Pune**")
    st.markdown("Corrugated Box Manufacturer")
    st.markdown("---")
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# Load data
forecast, alerts_df, proc_df, subs_df, explosion_df, mat_master, sup_master = load_and_process()

# Tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏠 Overview", "📦 Procurement", "⚠️ Stockout Alerts",
    "🔄 Substitution", "🤖 AI Assistant", "📊 Calculation Chain"
])

# ========== TAB 1: Overview ==========
with tab1:
    st.markdown("# 🏠 Inventory Overview")
    
    critical_count = len(forecast[forecast["days_of_stock_remaining"] < 3])
    approved = proc_df[proc_df["status"].isin(["APPROVED","PARTIAL"])]
    total_orders = approved["order_cost_inr"].sum()
    final_out = approved["cumulative_outstanding"].max() if len(approved) > 0 else CURRENT_OUTSTANDING
    credit_free = CREDIT_LIMIT - final_out
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🔴 Critical Materials", critical_count)
    c2.metric("📋 Recommended Orders", f"₹{total_orders:,.0f}")
    c3.metric("💳 Credit Used", f"₹{final_out:,.0f}")
    c4.metric("✅ Credit Free", f"₹{credit_free:,.0f}")
    
    st.markdown("### Material Status Grid")
    cols = st.columns(7)
    for i, (_, row) in enumerate(forecast.sort_values("material_id").iterrows()):
        with cols[i % 7]:
            if row["days_of_stock_remaining"] < 3:
                color = "🔴"
            elif row["days_of_stock_remaining"] <= 7:
                color = "🟡"
            else:
                color = "🟢"
            st.markdown(f"**{color} {row['material_id']}**")
            st.caption(f"{row['material_name'][:15]}")
            st.caption(f"Stock: {row['current_stock']} | {row['days_of_stock_remaining']}d")
    
    st.markdown("### Forecast Table")
    display_cols = ["material_id","material_name","raw_demand","seasonal_multiplier",
                    "adjusted_demand","unit","current_stock","daily_demand",
                    "days_of_stock_remaining","status"]
    st.dataframe(forecast[display_cols].sort_values("days_of_stock_remaining"), 
                 use_container_width=True, height=500)

# ========== TAB 2: Procurement ==========
with tab2:
    st.markdown("# 📦 Procurement Recommendations")
    
    st.markdown(f"**Credit Limit:** ₹{CREDIT_LIMIT:,} | **Outstanding:** ₹{CURRENT_OUTSTANDING:,}")
    
    active = proc_df[proc_df["order_qty_moq"] > 0]
    if len(active) > 0:
        st.dataframe(active, use_container_width=True, height=400)
        
        st.markdown("### Running Credit Balance")
        fig = px.bar(active, x="material_id", y="cumulative_outstanding", 
                     title="Cumulative Outstanding vs Credit Limit",
                     color_discrete_sequence=["#FF8C00"])
        fig.add_hline(y=CREDIT_LIMIT, line_dash="dash", line_color="red", annotation_text="Credit Limit")
        fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color="white")
        st.plotly_chart(fig, use_container_width=True)
    
    # Download Excel
    report_path = os.path.join(OUTPUT_DIR, f"packright_weekly_report_{TODAY.strftime('%Y%m%d')}.xlsx")
    if os.path.exists(report_path):
        with open(report_path, "rb") as f:
            st.download_button("📥 Download Excel Report", f, 
                             file_name=os.path.basename(report_path),
                             mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    st.markdown("### All Materials")
    st.dataframe(proc_df, use_container_width=True)

# ========== TAB 3: Stockout Alerts ==========
with tab3:
    st.markdown("# ⚠️ Stockout Alerts")
    
    critical = alerts_df[alerts_df["alert_level"].str.contains("CRITICAL")]
    if len(critical) > 0:
        for _, a in critical.iterrows():
            st.error(f"🔴 CRITICAL: {a['material_id']} {a['name']} — Only {a['days_remaining']} days remaining! "
                    f"Stock: {a['current_stock']} {a['unit']} | Daily demand: {a['daily_demand']:.2f}")
    
    st.dataframe(alerts_df, use_container_width=True, height=400)
    
    st.markdown("### Days of Stock (by material)")
    chart = alerts_df[["material_id","name","days_remaining"]].copy()
    chart["days_remaining_clipped"] = chart["days_remaining"].clip(upper=30)
    fig2 = px.bar(chart, x="days_remaining_clipped", y="material_id", orientation='h',
                  hover_data=["days_remaining", "name"], 
                  color="days_remaining_clipped", color_continuous_scale="RdYlGn")
    fig2.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color="white")
    st.plotly_chart(fig2, use_container_width=True)

# ========== TAB 4: Substitution ==========
with tab4:
    st.markdown("# 🔄 Substitution Alerts")
    
    if len(subs_df) > 0:
        for _, s in subs_df.iterrows():
            st.warning(f"**{s['primary']} {s['primary_name']}** — {s['primary_stock']} units "
                      f"(below reorder point {s['reorder_point']})")
            st.info(f"➡️ Substitute: **{s['substitute']} {s['substitute_name']}** — "
                   f"{s['substitute_stock']} units available | Both low: {s['both_low']}")
            
            sup = sup_master[sup_master["materials_supplied"].str.contains(s["substitute"])]
            if len(sup) > 0:
                best = sup.sort_values("reliability_score", ascending=False).iloc[0]
                st.success(f"📞 Order from: {best['supplier_name']} ({best['supplier_id']}) | "
                          f"Lead: {best['lead_time_days']}d | MOQ: {best['moq']} | "
                          f"Reliability: {best['reliability_score']}")
            st.markdown("---")
    else:
        st.success("No substitution advisories needed at this time.")

# ========== TAB 5: AI Assistant ==========
with tab5:
    st.markdown("# 🤖 AI Inventory Assistant")
    
    forecast_summary = forecast[["material_id","material_name","current_stock","adjusted_demand",
                                  "days_of_stock_remaining","status"]].to_string(index=False)
    proc_summary = proc_df[proc_df["order_qty_moq"]>0][["material_id","name","order_qty_moq",
                    "order_cost_inr","status"]].to_string(index=False) if len(proc_df[proc_df["order_qty_moq"]>0])>0 else "None"
    
    system_prompt = f"""You are PackRight Industries' AI Inventory Assistant.
You have complete knowledge of the current inventory state.

CURRENT INVENTORY STATUS (as of 2023-12-01):
{forecast_summary}

PROCUREMENT RECOMMENDATIONS:
{proc_summary}

CREDIT STATUS:
- Outstanding payables: Rs.14,14,385
- Credit limit: Rs.30,00,000
- Available credit: Rs.15,85,615

CRITICAL ALERTS:
- M01 Grade A Kraft: CRITICALLY LOW (18 rolls)
- Substitute M02 available: 55 rolls in stock

Your job: Answer purchase manager questions in plain, simple English.
No jargon. Give specific numbers. Always mention credit impact.
When recommending an order, always say: supplier name, quantity, cost,
delivery days, and resulting credit balance."""

    st.markdown("### Ask anything about inventory")
    
    col1, col2 = st.columns([3,1])
    with col2:
        st.markdown("**Suggested questions:**")
        suggestions = [
            "Why are we ordering M01 today?",
            "Which materials are safe for next month?",
            "What happens if we don't order this week?",
            "Explain the credit situation"
        ]
        for s in suggestions:
            if st.button(s, key=f"sug_{s[:10]}"):
                st.session_state["ai_question"] = s
    
    with col1:
        question = st.text_input("Your question:", 
                                value=st.session_state.get("ai_question", ""),
                                key="ai_input")
        
        if st.button("Ask AI 🚀") and question:
            try:
                genai.configure(api_key="AIzaSyARbiMma7srKmpUUPtW9Afz4ER6syqqQWg")
                model = genai.GenerativeModel("gemini-1.5-pro", system_instruction=system_prompt)
                response = model.generate_content(question)
                st.markdown("### 💡 AI Response")
                st.markdown(response.text)
            except Exception as e:
                st.warning(f"API call failed: {e}")
                st.markdown("### 📋 System prompt (for reference):")
                st.code(system_prompt[:800] + "...")

# ========== TAB 6: Calculation Chain ==========
with tab6:
    st.markdown("# 📊 Calculation Chain")
    st.markdown("Full BOM math for every material recommendation")
    
    for _, mat_row in forecast.sort_values("days_of_stock_remaining").iterrows():
        mid = mat_row["material_id"]
        mname = mat_row["material_name"]
        rd = mat_row["raw_demand"]
        ad = mat_row["adjusted_demand"]
        cs = mat_row["current_stock"]
        unit = mat_row["unit"]
        dr = mat_row["days_of_stock_remaining"]
        
        mat_exp = explosion_df[explosion_df["material_id"]==mid] if explosion_df is not None else pd.DataFrame()
        proc = proc_df[proc_df["material_id"]==mid]
        
        status_icon = "🔴" if dr < 3 else ("🟡" if dr <= 7 else "🟢")
        
        with st.expander(f"{status_icon} {mid}: {mname} — {dr} days remaining"):
            lines = [
                f"**BOM Explosion:** {len(mat_exp)} order line items in next 42 days",
                f"**Raw demand:** {rd:.2f} {unit} (aggregated from {len(mat_exp)} orders via BOM coefficients)",
                f"**Seasonal adjustment** (Dec ×1.40): {rd:.2f} × 1.40 = **{ad:.2f} {unit}**",
                f"**Current stock:** {cs} {unit}",
                f"**Daily demand:** {ad/28:.2f} {unit}/day",
                f"**Days of stock:** {cs} / {ad/28:.2f} = **{dr} days**",
            ]
            
            order_needed = ad - cs
            if order_needed > 0:
                lines.append(f"**Order needed:** {ad:.2f} - {cs} = {order_needed:.2f} {unit}")
                if len(proc) > 0:
                    p = proc.iloc[0]
                    price = AVG_PRICES.get(mid, 0)
                    lines.append(f"**Supplier:** {p.get('supplier_id','?')} ({p.get('supplier_name','?')})")
                    lines.append(f"**MOQ rounding:** {order_needed:.2f} → {p.get('order_qty_moq',0)} {unit}")
                    lines.append(f"**Cost:** {p.get('order_qty_moq',0)} × ₹{price:,} = ₹{p.get('order_cost_inr',0):,.0f}")
                    lines.append(f"**Payment terms:** {p.get('payment_terms','?')} | Credit impact: ₹{p.get('immediate_credit_impact',0):,.0f}")
                    lines.append(f"**Result:** {p.get('status','?')}")
            else:
                lines.append(f"**✅ Stock sufficient** — {cs} ≥ {ad:.2f} → NO ORDER NEEDED")
            
            for line in lines:
                st.markdown(line)
