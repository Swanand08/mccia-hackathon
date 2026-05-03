"""
PackRight Industries — AI Inventory Intelligence Dashboard (Streamlit)
Enhanced with Scenario Planning, Order History, and more.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os, sys, json, math
import google.generativeai as genai
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR  = os.path.join(BASE_DIR, "data")
OUTPUT_DIR= os.path.join(BASE_DIR, "output")
sys.path.insert(0, BASE_DIR)

from config import TODAY, CREDIT_LIMIT, AVG_PRICES, get_current_outstanding
from generate_data import generate_all_data
from order_history import log_approved_order
from data_utils import normalize_columns, validate_csv, load_normalized_csv

# BUG 1 FIX: Adding COLUMN_MAPPING to app.py as requested, although canonical source is data_utils.py
COLUMN_MAPPING = {
    "quantity": ["qty", "order_quantity", "amount", "order_qty"]
}

# ── Data loading (cached, with validation) ────────────────────────────────────
@st.cache_data
def load_and_process(hash_key, manual_adjustments=None):
    """Loads CSVs from disk, validates, runs full pipeline."""
    try:
        for df_key, fname in [("mat_master", "material_master.csv"), ("sup_master", "supplier_master.csv"),
                              ("prod_orders", "production_orders.csv"), ("seasonal", "seasonal_index.csv")]:
            df = load_normalized_csv(os.path.join(DATA_DIR, fname), fname)
            if df_key == "mat_master": mat_master = df
            elif df_key == "sup_master": sup_master = df
            elif df_key == "prod_orders": prod_orders = df
            elif df_key == "seasonal": seasonal = df

        wc_log = load_normalized_csv(os.path.join(DATA_DIR, "working_capital_log.csv"), "working_capital_log.csv")
        # BUG 5 FIX: Explicitly call validate_csv on wc_log
        validate_csv(wc_log, "working_capital_log.csv")

        # Apply manual stock adjustments
        if manual_adjustments:
            for mid, qty in manual_adjustments.items():
                mat_master.loc[mat_master["material_id"] == mid, "current_stock"] = qty

        from unit_normalizer import normalize_units
        from bom_forecaster import run_forecast
        from stockout_alerter import run_stockout_alerts
        from substitution_engine import run_substitution_engine
        from procurement_engine import run_procurement_engine

        inv_txn = load_normalized_csv(os.path.join(DATA_DIR,"inventory_transactions.csv"), "inventory_transactions.csv")
        inv_clean = normalize_units(inv_txn)

        forecast, explosion_df, upcoming = run_forecast(DATA_DIR, prod_orders=prod_orders, material_master=mat_master, seasonal_index=seasonal)
        alerts_df      = run_stockout_alerts(forecast, mat_master, sup_master)
        substitution_df= run_substitution_engine(forecast, mat_master, sup_master)
        proc_df        = run_procurement_engine(forecast, mat_master, sup_master, DATA_DIR)

        return forecast, alerts_df, proc_df, substitution_df, explosion_df, mat_master, sup_master, wc_log

    except Exception as e:
        st.error(f"Pipeline error: {e}")
        import traceback
        st.code(traceback.format_exc())
        return (None,)*8

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="PackRight AI Inventory", page_icon="[📦]", layout="wide")

st.markdown("""
<style>
.metric-card{background:var(--background-color);border:1px solid #334155;border-radius:12px;padding:20px;text-align:center;}
.metric-value{font-size:28px;font-weight:800;}
.metric-label{font-size:13px;color:#94a3b8;margin-top:6px;text-transform:uppercase;letter-spacing:1px;}
.card-red{border-left:5px solid #ef4444;padding:16px;background:rgba(239,68,68,0.08);border-radius:10px;margin-bottom:10px;}
.card-amber{border-left:5px solid #f59e0b;padding:16px;background:rgba(245,158,11,0.08);border-radius:10px;margin-bottom:10px;}
.card-green{border-left:5px solid #10b981;padding:16px;background:rgba(16,185,129,0.08);border-radius:10px;margin-bottom:10px;}
.card-blue{border-left:5px solid #3b82f6;padding:16px;background:rgba(59,130,246,0.08);border-radius:10px;margin-bottom:10px;}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## [📦] PackRight AI Hub")
    st.markdown(f"**Date:** {TODAY.strftime('%d %B %Y')} *(live)*")
    
    if not os.getenv("GEMINI_API_KEY"):
        st.warning("⚠️ AI Assistant disabled — add GEMINI_API_KEY to your .env file")

    if not os.path.exists(DATA_DIR):
        st.error("⚠️ Data directory missing! Click below to generate sample data.")

    current_outstanding = get_current_outstanding(DATA_DIR)
    credit_pct = (current_outstanding / CREDIT_LIMIT) * 100
    st.progress(min(credit_pct/100, 1.0))
    st.caption(f"Credit used: ₹{current_outstanding:,.0f} / ₹{CREDIT_LIMIT:,} ({credit_pct:.1f}%)")
    st.markdown("---")

    menu = st.radio("Navigation", [
        "| Dashboard",
        "| Procurement",
        "| Stockout Alerts",
        "| Substitutions",
        "| Excess Stock",
        "| AI Assistant",
        "| Scenario Planning",
        "| Order History",
        "| BOM",
    ])

    if st.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    if st.button("🏗️ Generate Sample Data", use_container_width=True):
        generate_all_data()
        st.cache_data.clear()
        st.success("Sample data generated!")
        st.rerun()

    st.markdown("---")
    
    # Manual Stock Adjustments
    with st.expander("🛠️ Manual Stock Adjustments"):
        if "manual_adjustments" not in st.session_state:
            st.session_state["manual_adjustments"] = {}
        
        # We need mat_master to pre-fill, so we'll load it briefly without caching
        if os.path.exists(os.path.join(DATA_DIR, "material_master.csv")):
            m_temp = pd.read_csv(os.path.join(DATA_DIR, "material_master.csv"))
            m_temp = normalize_columns(m_temp, "material_master.csv")
            for _, r in m_temp.iterrows():
                mid = r["material_id"]
                current = st.session_state["manual_adjustments"].get(mid, r["current_stock"])
                new_val = st.number_input(f"{mid} ({r['material_name'][:10]})", value=float(current), key=f"adj_{mid}")
                st.session_state["manual_adjustments"][mid] = new_val
            
            if st.button("Apply Adjustments", use_container_width=True):
                st.cache_data.clear()
                st.rerun()

    st.markdown("---")
    st.markdown("### 📥 Data Ingestion")
    with st.expander("Upload CSV Files"):
        uploaded_files = st.file_uploader("Override system files", type="csv", accept_multiple_files=True)
        if uploaded_files:
            if st.button("💾 Save & Apply", use_container_width=True):
                for f in uploaded_files:
                    target_path = os.path.join(DATA_DIR, f.name)
                    with open(target_path, "wb") as out:
                        out.write(f.getvalue())
                st.cache_data.clear()
                st.success(f"Saved {len(uploaded_files)} files!")
                st.rerun()

# ── Load data ─────────────────────────────────────────────────────────────────
# BUG 3 FIX: Dynamic hash key for cache invalidation
hash_key = str({f: os.path.getmtime(os.path.join(DATA_DIR, f)) for f in os.listdir(DATA_DIR) if f.endswith('.csv')}) if os.path.exists(DATA_DIR) else "no_data"

with st.spinner("Running inventory pipeline..."):
    results = load_and_process(hash_key, manual_adjustments=st.session_state.get("manual_adjustments"))

if results[0] is None:
    st.error("Could not load data. Generate sample data in the sidebar or upload CSVs.")
    st.stop()

forecast, alerts_df, proc_df, subs_df, explosion_df, mat_master, sup_master, wc_log = results

# Build supplier lookup
sup_lookup = {}
for _, sup in sup_master.iterrows():
    for m in str(sup.get("materials_supplied", "")).split(","):
        m = m.strip()
        if m and m not in sup_lookup:
            sup_lookup[m] = sup

# FEATURE 2: Excel download button in sidebar
with st.sidebar:
    st.markdown("---")
    try:
        from report_generator import generate_report
        report_path = generate_report(forecast, alerts_df, subs_df, proc_df, pd.DataFrame(), explosion_df, OUTPUT_DIR, supplier_master=sup_master)
        with open(report_path, "rb") as f:
            st.download_button("📥 Download Weekly Report", f, file_name=os.path.basename(report_path), mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    except Exception as e:
        st.caption(f"Excel report pending: {e}")

def color(status):
    s = str(status).upper()
    if "CRITICAL" in s or "BLOCKED" in s: return "#ef4444"
    if "WARNING" in s or "PARTIAL" in s:  return "#f59e0b"
    if "EXCESS" in s:                     return "#8b5cf6"
    return "#10b981"

# ── DASHBOARD ─────────────────────────────────────────────────────────────────
if "| Dashboard" in menu:
    st.markdown("# | Dashboard Overview")
    critical_count = len(forecast[forecast["days_of_stock_remaining"] < 3])
    approved       = proc_df[proc_df["status"].isin(["APPROVED","PARTIAL"])]
    total_val      = approved["order_cost_inr"].sum()
    final_out      = approved["cumulative_outstanding"].max() if not approved.empty else current_outstanding
    excess_count   = len(forecast[forecast.get("excess_stock", False) == True]) if "excess_stock" in forecast.columns else 0

    c1,c2,c3,c4,c5 = st.columns(5)
    for col, val, label, clr in [
        (c1, critical_count, "Critical materials", "#ef4444"),
        (c2, f"₹{total_val:,.0f}", "Order value", "#3b82f6"),
        (c3, f"₹{final_out:,.0f}", "Credit used after", "#f59e0b"),
        (c4, f"₹{CREDIT_LIMIT-final_out:,.0f}", "Credit remaining", "#10b981"),
        (c5, excess_count, "Excess stock items", "#8b5cf6"),
    ]:
        col.markdown(f"<div class='metric-card'><div class='metric-value' style='color:{clr};'>{val}</div><div class='metric-label'>{label}</div></div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_chart, col_grid = st.columns([1,2])

    with col_chart:
        st.markdown("### Inventory health")
        counts = forecast["status"].str.extract(r"(CRITICAL|WARNING|OK)")[0].value_counts().reset_index()
        counts.columns = ["Status","Count"]
        fig = px.pie(counts, names="Status", values="Count", hole=0.65,
                     color="Status", color_discrete_map={"CRITICAL":"#ef4444","WARNING":"#f59e0b","OK":"#10b981"})
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="white", showlegend=False, margin=dict(t=0,b=0,l=0,r=0))
        fig.add_annotation(text=f"{len(forecast)}<br>total", x=0.5, y=0.5,
                           font_size=20, font_color="#fff", showarrow=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_grid:
        st.markdown("### Material status grid")
        cols = st.columns(4)
        for i, (_, row) in enumerate(forecast.sort_values("days_of_stock_remaining").iterrows()):
            clr = color(row["status"])
            mid = row["material_id"]
            # Get primary supplier from lookup
            sup = sup_lookup.get(mid, {})
            sup_name = sup.get("supplier_name", "N/A")
            
            cols[i%4].markdown(
                f"<div style='border-left:4px solid {clr};padding:8px 12px;margin-bottom:10px;border-radius:0 6px 6px 0;background:rgba(255,255,255,0.03);'>"
                f"<strong style='color:{clr}'>{mid}</strong><br>"
                f"<span style='font-size:12px;color:#cbd5e1'>{row['material_name'][:14]}</span><br>"
                f"<span style='font-size:11px;color:#94a3b8'>{row['current_stock']} {row['unit']} · {row['days_of_stock_remaining']}d</span><br>"
                f"<span style='font-size:10px;color:#64748b'>Sup: {str(sup_name)[:12]}</span>"
                "</div>", unsafe_allow_html=True)

    st.markdown("### Full forecast table")
    display_cols = ["material_id","material_name","raw_demand","adjusted_demand",
                    "current_stock","daily_demand","days_of_stock_remaining","status"]
    st.dataframe(forecast.sort_values("days_of_stock_remaining")[display_cols], use_container_width=True)

# ── PROCUREMENT ───────────────────────────────────────────────────────────────
elif "| Procurement" in menu:
    st.markdown("# | Procurement Recommendations")
    st.info(f"Credit limit: ₹{CREDIT_LIMIT:,} | Current outstanding: ₹{current_outstanding:,} | Available: ₹{CREDIT_LIMIT-current_outstanding:,}")

    needs_order = proc_df[proc_df["order_qty_moq"] > 0]
    if not needs_order.empty:
        fig = go.Figure()
        fig.add_trace(go.Bar(x=needs_order["material_id"], y=needs_order["cumulative_outstanding"],
                              marker_color="#3b82f6", name="Cumulative outstanding"))
        fig.add_hline(y=CREDIT_LIMIT, line_dash="dash", line_color="#ef4444", annotation_text="₹30L limit")
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="white", margin=dict(t=20,b=0,l=0,r=0))
        st.plotly_chart(fig, use_container_width=True)

    active = proc_df[proc_df["order_qty_moq"] > 0]
    blocked = proc_df[proc_df["status"] == "BLOCKED"]
    
    if not blocked.empty:
        st.warning(f"⚠️ {len(blocked)} items are currently BLOCKED because ordering them would exceed your ₹30L credit limit. Please clear outstanding payments to enable these orders.")
        with st.expander("🚫 View Blocked Orders"):
            st.dataframe(blocked[["material_id", "name", "order_qty_raw", "status", "recommendation_reason"]], use_container_width=True)

    st.markdown("### ✅ Approved & Partial Orders")
    for idx, row in active.iterrows():
        clr = color(row["status"])
        sup_info = sup_master[sup_master["supplier_id"] == row["supplier_id"]]
        lead = sup_info.iloc[0]["lead_time_days"] if not sup_info.empty else 7
        
        st.markdown(f"""
        <div style='background:rgba(255,255,255,0.03);border:1px solid #334155;border-radius:12px;padding:20px;margin-bottom:16px;'>
          <div style='display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #334155;padding-bottom:12px;margin-bottom:12px;'>
            <strong style='font-size:18px'>{row['material_id']} - {row['name']}</strong>
            <span style='background:{clr};padding:4px 12px;border-radius:16px;font-size:12px;font-weight:700;color:white;'>{row['status']}</span>
          </div>
          <div style='display:flex;gap:24px;flex-wrap:wrap;'>
            <div><span style='color:#94a3b8;font-size:12px;'>ORDER QTY</span><br><strong style='font-size:20px'>{row['order_qty_moq']} {row['unit']}</strong></div>
            <div><span style='color:#94a3b8;font-size:12px;'>SUPPLIER</span><br><strong>{row['supplier_name']}</strong></div>
            <div><span style='color:#94a3b8;font-size:12px;'>COST</span><br><strong>Rs.{row['order_cost_inr']:,.0f}</strong></div>
            <div><span style='color:#94a3b8;font-size:12px;'>LEAD TIME</span><br><strong>{lead} Days</strong></div>
            <div><span style='color:#94a3b8;font-size:12px;'>CREDIT AFTER</span><br><strong>Rs.{row['credit_remaining']:,.0f}</strong></div>
          </div>
          <div style='margin-top:12px;font-size:13px;color:#94a3b8;'><i>Reason: {row['recommendation_reason']}</i></div>
        </div>""", unsafe_allow_html=True)
        
        c_p1, c_p2, c_p3 = st.columns([1,1,2])
        with c_p1:
            # FEATURE 6: PO Draft Generator
            if st.button(f"📧 Draft PO Email", key=f"draft_{idx}"):
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key: st.error("No API Key")
                else:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel("gemini-2.0-flash")
                    prompt = f"Write a professional PO email to {row['supplier_name']} for {row['order_qty_moq']} {row['unit']} of {row['name']}. Price: ₹{row['unit_price']}/unit, Total: ₹{row['order_cost_inr']:,.0f}. Lead time: {lead} days. Payment: {row['payment_terms']}."
                    msg = model.generate_content(prompt)
                    st.text_area("PO Draft", msg.text, height=200)
        with c_p2:
            # FEATURE 8: Order History integration
            if st.button(f"✅ Confirm Order", key=f"conf_{idx}"):
                log_approved_order(row, notes="Confirmed via Dashboard")
                st.success(f"Order for {row['material_id']} logged!")

    st.markdown("### | Supplier Intelligence")
    st.dataframe(sup_master[["supplier_id","supplier_name","lead_time_days","reliability_score","payment_terms_days"]], use_container_width=True)

# ── STOCKOUT ALERTS ───────────────────────────────────────────────────────────
elif "| Stockout" in menu:
    st.markdown("# | Stockout Alerts")
    critical = alerts_df[alerts_df["alert_level"].str.contains("CRITICAL", na=False)]
    warning  = alerts_df[alerts_df["alert_level"].str.contains("WARNING", na=False)]

    for _, a in critical.iterrows():
        st.markdown(f"<div class='card-red'><strong>🚨 {a['material_id']} — {a['name']}</strong><br>"
                    f"Only <strong style='color:#ef4444'>{a['days_remaining']} days</strong> of stock. "
                    f"Daily burn: {a['daily_demand']:.2f} {a['unit']}/day | 21-day shortfall: {a['shortfall']}</div>",
                    unsafe_allow_html=True)
    for _, a in warning.iterrows():
        st.markdown(f"<div class='card-amber'>⚠️ <strong>{a['material_id']} — {a['name']}</strong>: {a['days_remaining']} days remaining</div>",
                    unsafe_allow_html=True)

# ── SUBSTITUTIONS ─────────────────────────────────────────────────────────────
elif "| Substitutions" in menu:
    st.markdown("# | Substitution Advisories")
    if not subs_df.empty:
        for _, s in subs_df.iterrows():
            # BUG 2 FIX: Ensure correct field references
            sub_sup = sup_master[sup_master["materials_supplied"].str.contains(str(s.get("substitute_id","")))]
            sup_info = sub_sup.iloc[0] if not sub_sup.empty else {}
            st.markdown(f"""
            <div class='card-blue'>
              <strong>Switch from {s.get('material_id','')} ({s.get('material_name','')}) → {s.get('substitute_id','')} ({s.get('substitute_name','')})</strong><br>
              Primary stock: <span style='color:#ef4444'>{s.get('current_stock','')} units</span> (below reorder point)<br>
              Substitute available: <strong>{s.get('substitute_stock','')} units</strong><br>
              Status: <strong>{s.get('substitute_status','')}</strong> | Action: {s.get('action','')}
            </div>""", unsafe_allow_html=True)


# ── EXCESS STOCK ──────────────────────────────────────────────────────────────
elif "| Excess Stock" in menu:
    st.markdown("# | Excess Stock Analysis")
    st.markdown("Materials with high stock relative to upcoming demand or safety levels.")
    
    excess = forecast[forecast.get("excess_stock", False) == True]
    if not excess.empty:
        st.warning(f"⚠️ {len(excess)} materials identified as excess stock.")
        for _, row in excess.iterrows():
            with st.container():
                st.markdown(f"""
                <div class='card-blue'>
                    <strong>{row['material_id']} - {row['material_name']}</strong><br>
                    Current Stock: {row['current_stock']} {row['unit']} | 
                    Forecasted Demand: {row['adjusted_demand']} {row['unit']}<br>
                    <i>Status: High inventory relative to reorder point ({row['reorder_point']}) and demand.</i>
                </div>""", unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.success("✅ No excess stock identified based on current demand and reorder points.")

# ── SCENARIO PLANNING (FEATURE 5) ─────────────────────────────────────────────
elif "| Scenario Planning" in menu:
    st.markdown("# | Scenario Planning Mode")
    st.markdown("Test the impact of production volume changes on procurement and credit.")
    
    vol_change = st.slider("Production volume change", -50, 100, 0, step=5, format="%d%%")
    
    if vol_change != 0:
        # Clone and adjust forecast
        scen_forecast = forecast.copy()
        factor = 1 + vol_change/100
        scen_forecast["adjusted_demand"] *= factor
        scen_forecast["daily_demand"] *= factor
        scen_forecast["days_of_stock_remaining"] = scen_forecast.apply(lambda r: round(r["current_stock"]/r["daily_demand"],1) if r["daily_demand"]>0 else 999, axis=1)
        
        # Re-run procurement engine
        from procurement_engine import run_procurement_engine
        scen_proc = run_procurement_engine(scen_forecast, mat_master, sup_master, DATA_DIR)
        
        c_sc1, c_sc2 = st.columns(2)
        with c_sc1:
            st.markdown("### Original Plan")
            st.metric("Total Order Value", f"₹{proc_df[proc_df['status'].isin(['APPROVED','PARTIAL'])]['order_cost_inr'].sum():,.0f}")
            st.dataframe(proc_df[proc_df["order_qty_moq"]>0][["material_id","order_qty_moq","order_cost_inr","status"]], use_container_width=True)
        with c_sc2:
            st.markdown("### Scenario Plan")
            st.metric("New Order Value", f"₹{scen_proc[scen_proc['status'].isin(['APPROVED','PARTIAL'])]['order_cost_inr'].sum():,.0f}", 
                      delta=f"₹{scen_proc[scen_proc['status'].isin(['APPROVED','PARTIAL'])]['order_cost_inr'].sum() - proc_df[proc_df['status'].isin(['APPROVED','PARTIAL'])]['order_cost_inr'].sum():,.0f}", delta_color="inverse")
            st.dataframe(scen_proc[scen_proc["order_qty_moq"]>0][["material_id","order_qty_moq","order_cost_inr","status"]], use_container_width=True)
    else:
        st.info("Adjust the slider to see scenario impacts.")

# ── ORDER HISTORY (FEATURE 8) ─────────────────────────────────────────────────
elif "| Order History" in menu:
    st.markdown("# | Order History Log")
    if os.path.exists("data/order_history.csv"):
        history = pd.read_csv("data/order_history.csv")
        st.dataframe(history.sort_values("timestamp", ascending=False), use_container_width=True)
        st.metric("Total Historically Ordered", f"₹{history['total_cost_inr'].sum():,.0f}")
    else:
        st.info("No order history found yet. Confirm some orders in the Procurement tab!")

# ── AI ASSISTANT ──────────────────────────────────────────────────────────────
elif "| AI Assistant" in menu:
    st.markdown("# | AI Inventory Assistant")
    forecast_csv = forecast[["material_id","material_name","current_stock","adjusted_demand","days_of_stock_remaining","status"]].to_csv(index=False)
    approved = proc_df[proc_df["order_qty_moq"] > 0]
    proc_csv = approved[["material_id","name","order_qty_moq","order_cost_inr","status"]].to_csv(index=False) if not approved.empty else "No active orders."
    
    system_prompt = f"You are PackRight's AI. Inventory state as of {TODAY.strftime('%d %B %Y')}. Data:\n{forecast_csv}\n\nProcurement:\n{proc_csv}"

    col1, col2 = st.columns([3,1])
    with col2:
        for q in ["What's critically low?","Explain credit situation"]:
            if st.button(q, use_container_width=True): st.session_state["ai_q"] = q

    with col1:
        question = st.text_area("Your question:", value=st.session_state.get("ai_q",""), height=100)
        if st.button("Ask Gemini ↗", type="primary") and question:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key: st.error("API Key missing")
            else:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel("gemini-2.0-flash")
                msg = model.generate_content(system_prompt + "\n\n" + question)
                st.markdown(f"<div style='background:rgba(255,255,255,0.04);padding:20px;border-radius:10px;border:1px solid #334155;'>{msg.text}</div>", unsafe_allow_html=True)

# ── BOM CALCULATIONS ──────────────────────────────────────────────────────────
elif "| BOM" in menu:
    st.markdown("# | BOM (Bill of Materials) Calculations")
    st.markdown("Detailed breakdown of how demand is calculated from BOM explosion.")
    
    with st.expander("📖 View Master BOM Definitions"):
        st.markdown("These are the static BOM coefficients used to explode production orders into material demand.")
        from config import BOM_MAP
        bom_data = []
        for product, materials in BOM_MAP.items():
            for mat_id, coeff in materials.items():
                bom_data.append({"Product Type": product, "Material ID": mat_id, "Coefficient": coeff})
        st.table(pd.DataFrame(bom_data))

    from config import TODAY
    month_name = TODAY.strftime("%B")

    for _, mat in forecast.sort_values("days_of_stock_remaining").iterrows():
        mid = mat["material_id"]
        dr = mat["days_of_stock_remaining"]
        
        # Procurement info
        p = proc_df[proc_df["material_id"] == mid].iloc[0] if not proc_df[proc_df["material_id"] == mid].empty else None
        
        # Supplier info
        sup_rec = sup_lookup.get(mid, {})
        sup_id = sup_rec.get("supplier_id", "N/A")
        sup_name = sup_rec.get("supplier_name", "N/A")
        
        # Explosion info
        breakdown = explosion_df[explosion_df["material_id"] == mid]
        order_count = len(breakdown)
        
        expanded = dr < 3
        with st.expander(f"📦 {mid}: {mat['material_name']} — {dr} days remaining", expanded=expanded):
            # Clean Summary Block (No HTML tags)
            summary_text = f"""Upcoming orders (next 42 days): {order_count} order line items
Raw demand from BOM explosion: {mat['raw_demand']} {mat['unit']}
Seasonal adjustment ({month_name} x{mat['seasonal_multiplier']}): {mat['raw_demand']} x {mat['seasonal_multiplier']} = {mat['adjusted_demand']} {mat['unit']}
Current stock: {mat['current_stock']} {mat['unit']}
"""
            
            if p is not None and p['order_qty_moq'] > 0:
                diff = round(mat['adjusted_demand'] - mat['current_stock'], 2)
                summary_text += f"""
Order needed: {mat['adjusted_demand']} - {mat['current_stock']} = {diff} {mat['unit']}
Supplier: {sup_id} ({sup_name})
MOQ rounding: {diff} -> {p['order_qty_moq']} {mat['unit']}
Cost: {p['order_qty_moq']} x Rs.{p.get('unit_price','?')} = Rs.{p['order_cost_inr']:,.0f}
Payment terms: {p.get('payment_terms','?')} | Credit impact: Rs.{p.get('order_cost_inr',0):,.0f}
Status: {p['status']}
"""
            else:
                summary_text += f"\nStock sufficient: {mat['current_stock']} >= {mat['adjusted_demand']} → NO ORDER NEEDED"
            
            st.code(summary_text, language="text")
            
            st.markdown("---")
            st.write(f"**Daily Burn Rate:** {mat['daily_demand']:.4f} {mat['unit']}/day")
            st.write(f"**Calculation:** {mat['current_stock']} / {mat['daily_demand']:.4f} = {dr} days")
