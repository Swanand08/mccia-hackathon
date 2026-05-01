import pandas as pd
import os

REQUIRED_COLUMNS = {
    "material_master.csv":   ["material_id","material_name","current_stock","unit","reorder_point"],
    "supplier_master.csv":   ["supplier_id","supplier_name","materials_supplied","lead_time_days","moq","payment_terms_days","reliability_score"],
    "production_orders.csv": ["order_id","product_type","quantity","delivery_date","material_bom"],
    "seasonal_index.csv":    ["month"],
    "working_capital_log.csv":["outstanding_payables"],
    "inventory_transactions.csv": ["material_id", "quantity", "type", "date"]
}

COLUMN_MAPPING = {
    "material_id":   ["id", "material", "item_id", "part_number", "sku"],
    "material_name": ["name", "item_name", "description", "material_description"],
    "reorder_point": ["reorder_point_current", "rop", "reorder_level", "min_stock"],
    "current_stock": ["stock", "on_hand", "qty", "inventory"],
    "quantity":      ["qty", "order_quantity", "amount", "order_qty", "order_size", "transaction_qty"],
    "unit":          ["uom", "units", "measurement"],
    "supplier_name": ["name", "vendor_name", "supplier"],
    "materials_supplied": ["material_supplied", "items_supplied", "products", "materials"],
    "material_bom":  ["bom", "components", "bill_of_materials", "material_list"],
    "type":          ["transaction_type", "txn_type", "entry_type", "movement_type"],
    "outstanding_payables": ["outstanding_payables_inr", "credit_utilized", "payables", "balance"],
}

def normalize_columns(df, filename):
    """Map aliases to canonical column names."""
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()
    
    reverse_map = {}
    for canonical, aliases in COLUMN_MAPPING.items():
        if canonical in df.columns:
            continue
        for alias in aliases:
            if alias in df.columns:
                reverse_map[alias] = canonical
                break
    
    if reverse_map:
        df = df.rename(columns=reverse_map)
    
    final_map = {}
    for col in df.columns:
        for req_file, req_cols in REQUIRED_COLUMNS.items():
            for rc in req_cols:
                if col == rc.lower():
                    final_map[col] = rc
    
    df = df.rename(columns=final_map)
    
    # Fallback logic for critical missing columns
    if filename == "material_master.csv":
        if "material_name" not in df.columns:
            df["material_name"] = df["material_id"] if "material_id" in df.columns else "Unnamed Item"
        if "reorder_point" not in df.columns:
            df["reorder_point"] = 0
        if "current_stock" not in df.columns:
            df["current_stock"] = 0
        if "unit" not in df.columns:
            df["unit"] = "Units"
            
    if filename == "supplier_master.csv":
        if "lead_time_days" not in df.columns:
            df["lead_time_days"] = 7
        if "moq" not in df.columns:
            df["moq"] = 1
            
    return df

def validate_csv(df, filename):
    required = REQUIRED_COLUMNS.get(filename, [])
    missing  = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{filename} is missing columns: {missing}. Found: {df.columns.tolist()}")
    return True

def load_normalized_csv(path, filename):
    df = pd.read_csv(path)
    df = normalize_columns(df, filename)
    validate_csv(df, filename)
    return df
