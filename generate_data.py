"""
Data Generator for PackRight Industries Inventory System.
Generates all 6 CSV files with realistic data matching the specifications.
"""
import pandas as pd
import numpy as np
import json
import random
import os
from datetime import datetime, timedelta

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def generate_all_data():
    random.seed(42)
    np.random.seed(42)

    os.makedirs(DATA_DIR, exist_ok=True)

    # ============================================================
    # 1. MATERIAL MASTER (14 rows)
    # ============================================================
    material_master = pd.DataFrame([
        {"material_id":"M01","material_name":"Kraft Grade A","category":"Paper","unit":"rolls","current_stock":18,"reorder_point":40,"safety_stock":15,"substitute_material_ids":"M02","avg_unit_price":22850},
        {"material_id":"M02","material_name":"Kraft Grade B","category":"Paper","unit":"rolls","current_stock":55,"reorder_point":30,"safety_stock":10,"substitute_material_ids":"M01","avg_unit_price":22929},
        {"material_id":"M03","material_name":"Kraft Grade C","category":"Paper","unit":"rolls","current_stock":62,"reorder_point":20,"safety_stock":8,"substitute_material_ids":"","avg_unit_price":22660},
        {"material_id":"M04","material_name":"White Top Liner","category":"Paper","unit":"rolls","current_stock":30,"reorder_point":15,"safety_stock":5,"substitute_material_ids":"","avg_unit_price":23096},
        {"material_id":"M05","material_name":"Corrugating Medium","category":"Paper","unit":"rolls","current_stock":44,"reorder_point":25,"safety_stock":10,"substitute_material_ids":"","avg_unit_price":23887},
        {"material_id":"M06","material_name":"Adhesive WF-200","category":"Adhesive","unit":"kg","current_stock":1840,"reorder_point":200,"safety_stock":80,"substitute_material_ids":"","avg_unit_price":23333},
        {"material_id":"M07","material_name":"Adhesive PF-100","category":"Adhesive","unit":"kg","current_stock":620,"reorder_point":100,"safety_stock":40,"substitute_material_ids":"","avg_unit_price":23379},
        {"material_id":"M08","material_name":"Starch Adhesive","category":"Adhesive","unit":"kg","current_stock":920,"reorder_point":500,"safety_stock":200,"substitute_material_ids":"","avg_unit_price":23620},
        {"material_id":"M09","material_name":"Ink Cyan","category":"Ink","unit":"kg","current_stock":480,"reorder_point":50,"safety_stock":20,"substitute_material_ids":"","avg_unit_price":23057},
        {"material_id":"M10","material_name":"Ink Magenta","category":"Ink","unit":"kg","current_stock":510,"reorder_point":50,"safety_stock":20,"substitute_material_ids":"","avg_unit_price":22613},
        {"material_id":"M11","material_name":"Ink Black","category":"Ink","unit":"kg","current_stock":390,"reorder_point":60,"safety_stock":25,"substitute_material_ids":"","avg_unit_price":23756},
        {"material_id":"M12","material_name":"Specialty Gold Ink","category":"Ink","unit":"kg","current_stock":340,"reorder_point":20,"safety_stock":8,"substitute_material_ids":"","avg_unit_price":23087},
        {"material_id":"M13","material_name":"PP Strapping 12mm","category":"Strapping","unit":"rolls","current_stock":85,"reorder_point":30,"safety_stock":12,"substitute_material_ids":"","avg_unit_price":23547},
        {"material_id":"M14","material_name":"PP Strapping 16mm","category":"Strapping","unit":"rolls","current_stock":70,"reorder_point":20,"safety_stock":8,"substitute_material_ids":"","avg_unit_price":23128},
    ])
    material_master.to_csv(os.path.join(DATA_DIR, "material_master.csv"), index=False)

    # ============================================================
    # 2. SUPPLIER MASTER (9 rows)
    # ============================================================
    supplier_master = pd.DataFrame([
        {"supplier_id":"SUP01","supplier_name":"West Coast Paper Mills","materials_supplied":"M01,M02,M03","lead_time_days":7,"moq":20,"moq_unit":"rolls","payment_terms_days":30,"reliability_score":0.92,"contact_email":"orders@westcoastpaper.in","contact_phone":"+91-20-2567-8901"},
        {"supplier_id":"SUP02","supplier_name":"BILT Graphic","materials_supplied":"M04,M05","lead_time_days":10,"moq":15,"moq_unit":"rolls","payment_terms_days":45,"reliability_score":0.88,"contact_email":"supply@biltgraphic.in","contact_phone":"+91-22-4567-1234"},
        {"supplier_id":"SUP03","supplier_name":"Pidilite Industries","materials_supplied":"M06,M07","lead_time_days":5,"moq":100,"moq_unit":"kg","payment_terms_days":30,"reliability_score":0.95,"contact_email":"bulk@pidilite.com","contact_phone":"+91-22-2345-6789"},
        {"supplier_id":"SUP04","supplier_name":"National Starch","materials_supplied":"M08","lead_time_days":4,"moq":500,"moq_unit":"kg","payment_terms_days":30,"reliability_score":0.90,"contact_email":"orders@nationalstarch.in","contact_phone":"+91-11-3456-7890"},
        {"supplier_id":"SUP05","supplier_name":"Toyo Inks","materials_supplied":"M09,M10,M11","lead_time_days":12,"moq":25,"moq_unit":"kg","payment_terms_days":45,"reliability_score":0.87,"contact_email":"india@toyoinks.com","contact_phone":"+91-44-5678-2345"},
        {"supplier_id":"SUP06","supplier_name":"Siegwerk India","materials_supplied":"M12","lead_time_days":21,"moq":10,"moq_unit":"kg","payment_terms_days":60,"reliability_score":0.82,"contact_email":"sales@siegwerk.in","contact_phone":"+91-20-6789-3456"},
        {"supplier_id":"SUP07","supplier_name":"Supreme Industries","materials_supplied":"M13,M14","lead_time_days":6,"moq":20,"moq_unit":"rolls","payment_terms_days":30,"reliability_score":0.94,"contact_email":"orders@supreme.co.in","contact_phone":"+91-22-7890-4567"},
        {"supplier_id":"SUP08","supplier_name":"ITC Paper Division","materials_supplied":"M01,M04","lead_time_days":8,"moq":25,"moq_unit":"rolls","payment_terms_days":30,"reliability_score":0.91,"contact_email":"paper@itc.in","contact_phone":"+91-33-8901-5678"},
        {"supplier_id":"SUP09","supplier_name":"Hindustan Paper Corp","materials_supplied":"M02,M03","lead_time_days":14,"moq":20,"moq_unit":"rolls","payment_terms_days":60,"reliability_score":0.79,"contact_email":"sales@hindustanpaper.in","contact_phone":"+91-36-9012-6789"},
    ])
    supplier_master.to_csv(os.path.join(DATA_DIR, "supplier_master.csv"), index=False)

    # ============================================================
    # 3. SEASONAL INDEX (12 rows)
    # ============================================================
    seasonal_index = pd.DataFrame([
        {"month":1,"month_name":"January","seasonal_multiplier":0.78},
        {"month":2,"month_name":"February","seasonal_multiplier":0.80},
        {"month":3,"month_name":"March","seasonal_multiplier":0.92},
        {"month":4,"month_name":"April","seasonal_multiplier":0.95},
        {"month":5,"month_name":"May","seasonal_multiplier":0.88},
        {"month":6,"month_name":"June","seasonal_multiplier":0.82},
        {"month":7,"month_name":"July","seasonal_multiplier":0.85},
        {"month":8,"month_name":"August","seasonal_multiplier":0.90},
        {"month":9,"month_name":"September","seasonal_multiplier":0.95},
        {"month":10,"month_name":"October","seasonal_multiplier":1.35},
        {"month":11,"month_name":"November","seasonal_multiplier":1.62},
        {"month":12,"month_name":"December","seasonal_multiplier":1.40},
    ])
    seasonal_index.to_csv(os.path.join(DATA_DIR, "seasonal_index.csv"), index=False)

    # ============================================================
    # 4. WORKING CAPITAL LOG (24 rows — Jan 2022 to Nov 2023)
    # ============================================================
    wc_rows = []
    base_credit = 1800000
    for i in range(24):
        yr = 2022 + (i // 12)
        mo = (i % 12) + 1
        if yr == 2022:
            credit_util = base_credit + random.randint(-200000, 300000)
        else:
            credit_util = base_credit + random.randint(0, 500000)
        
        outstanding = int(credit_util * random.uniform(0.55, 0.75))
        available = 3000000 - credit_util
        overdue = int(outstanding * random.uniform(0.05, 0.18))
        
        # Last month (Nov 2023) must match spec
        if yr == 2023 and mo == 11:
            credit_util = 2175977
            outstanding = 1414385
            available = 824023
            overdue = 187431
        
        wc_rows.append({
            "month": f"{yr}-{mo:02d}",
            "credit_utilized": credit_util,
            "outstanding_payables": outstanding,
            "available_credit": available,
            "overdue_amount": overdue,
            "credit_limit": 3000000
        })

    working_capital = pd.DataFrame(wc_rows)
    working_capital.to_csv(os.path.join(DATA_DIR, "working_capital_log.csv"), index=False)

    # ============================================================
    # 5. PRODUCTION ORDERS (1400 rows)
    # ============================================================
    BOM_MAP = {
        "small_std": {"M01":0.18,"M05":0.12,"M06":0.008,"M08":0.015,"M11":0.002,"M13":0.05},
        "medium_std": {"M01":0.32,"M05":0.22,"M06":0.014,"M08":0.025,"M11":0.003,"M13":0.08},
        "medium_printed": {"M02":0.32,"M05":0.22,"M06":0.014,"M09":0.006,"M10":0.006,"M11":0.003,"M13":0.08},
        "small_printed": {"M02":0.18,"M05":0.12,"M06":0.008,"M09":0.003,"M10":0.003,"M11":0.002,"M13":0.05},
        "large_std": {"M01":0.55,"M05":0.38,"M06":0.022,"M08":0.04,"M11":0.005,"M14":0.12},
        "large_premium": {"M04":0.55,"M05":0.38,"M07":0.022,"M09":0.008,"M10":0.008,"M12":0.004,"M14":0.12},
    }

    product_types = list(BOM_MAP.keys())
    clients = [f"CLI{i:03d}" for i in range(1, 51)]
    box_sizes = ["small", "medium", "large"]

    prod_rows = []
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2024, 1, 15)
    total_days = (end_date - start_date).days

    for i in range(1, 1401):
        pt = random.choice(product_types)
        bom = BOM_MAP[pt]
        
        # Spread orders across the year with seasonal weighting
        order_day_offset = random.randint(0, total_days - 1)
        order_date = start_date + timedelta(days=order_day_offset)
        delivery_date = order_date + timedelta(days=random.randint(5, 21))
        
        qty = random.choice([100, 150, 200, 250, 300, 400, 500, 600, 750, 800, 1000])
        bs = "small" if "small" in pt else ("large" if "large" in pt else "medium")
        
        prod_rows.append({
            "order_id": f"PO{i:04d}",
            "client_id": random.choice(clients),
            "product_type": pt,
            "box_size": bs,
            "quantity": qty,
            "delivery_date": delivery_date.strftime("%Y-%m-%d"),
            "order_date": order_date.strftime("%Y-%m-%d"),
            "material_bom": json.dumps(bom)
        })

    production_orders = pd.DataFrame(prod_rows)
    production_orders.to_csv(os.path.join(DATA_DIR, "production_orders.csv"), index=False)

    # ============================================================
    # 6. INVENTORY TRANSACTIONS (18,003 rows)
    # ============================================================
    materials = material_master["material_id"].tolist()
    paper_materials = ["M01","M02","M03","M04","M05","M13","M14"]
    chem_materials = ["M06","M07","M08","M09","M10","M11","M12"]

    paper_unit_variants = ["rolls", "Rolls", "roll", "nos", "pcs"]
    chem_unit_variants = ["kg", "KG", "Kg", "kgs", "kilograms"]

    supplier_material_map = {}
    for _, row in supplier_master.iterrows():
        for m in row["materials_supplied"].split(","):
            if m not in supplier_material_map:
                supplier_material_map[m] = []
            supplier_material_map[m].append(row["supplier_id"])

    txn_types = ["issue", "receipt", "return", "writeoff"]
    txn_weights = [0.45, 0.40, 0.10, 0.05]

    inv_rows = []
    for i in range(18003):
        mat = random.choice(materials)
        txn_type = random.choices(txn_types, weights=txn_weights, k=1)[0]
        
        # Date spread over 2023
        day_offset = random.randint(0, 334)
        date = datetime(2023, 1, 1) + timedelta(days=day_offset)
        
        # Unit with intentional messiness
        if mat in paper_materials:
            unit = random.choice(paper_unit_variants)
            qty = random.randint(1, 50)
            price = material_master[material_master["material_id"]==mat]["avg_unit_price"].values[0]
            price = price + random.randint(-2000, 2000)
        else:
            unit = random.choice(chem_unit_variants)
            qty = random.randint(10, 500)
            price = material_master[material_master["material_id"]==mat]["avg_unit_price"].values[0]
            price = price + random.randint(-2000, 2000)
        
        sup = ""
        if txn_type == "receipt":
            sups = supplier_material_map.get(mat, [])
            if sups:
                sup = random.choice(sups)
        
        po_num = f"PUR{random.randint(10000,99999)}" if txn_type == "receipt" else ""
        
        inv_rows.append({
            "date": date.strftime("%Y-%m-%d"),
            "material_id": mat,
            "transaction_type": txn_type,
            "quantity": qty,
            "unit": unit,
            "supplier_id": sup,
            "unit_price": round(price, 2),
            "po_number": po_num
        })

    inventory_transactions = pd.DataFrame(inv_rows)
    inventory_transactions.to_csv(os.path.join(DATA_DIR, "inventory_transactions.csv"), index=False)

    print(f"✅ Data generated successfully in {DATA_DIR}")
    print(f"   material_master.csv:         {len(material_master)} rows")
    print(f"   supplier_master.csv:         {len(supplier_master)} rows")
    print(f"   seasonal_index.csv:          {len(seasonal_index)} rows")
    print(f"   working_capital_log.csv:     {len(working_capital)} rows")
    print(f"   production_orders.csv:       {len(production_orders)} rows")
    print(f"   inventory_transactions.csv:  {len(inventory_transactions)} rows")

if __name__ == "__main__":
    generate_all_data()
