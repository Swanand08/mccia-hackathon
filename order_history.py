import pandas as pd
import os
from datetime import datetime

HISTORY_FILE = "data/order_history.csv"

def log_approved_order(procurement_row, notes=""):
    """
    Appends a row to data/order_history.csv with order details.
    """
    new_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "material_id": procurement_row.get("material_id"),
        "supplier_id": procurement_row.get("supplier_id"),
        "quantity": procurement_row.get("order_qty_moq"),
        "unit_price": procurement_row.get("unit_price"),
        "total_cost_inr": procurement_row.get("order_cost_inr"),
        "status": procurement_row.get("status"),
        "notes": notes
    }
    
    df = pd.DataFrame([new_entry])
    
    if not os.path.exists(HISTORY_FILE):
        df.to_csv(HISTORY_FILE, index=False)
    else:
        df.to_csv(HISTORY_FILE, mode='a', header=False, index=False)
