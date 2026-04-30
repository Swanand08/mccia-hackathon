"""
D1 — Unit Normalization Module for PackRight Industries
Normalizes all unit variations to canonical units across inventory transactions.
"""
import pandas as pd

# Paper/Strapping materials
PAPER_MATERIALS = {"M01","M02","M03","M04","M05","M13","M14"}
# Adhesive/Ink materials
CHEM_MATERIALS = {"M06","M07","M08","M09","M10","M11","M12"}

PAPER_UNIT_MAP = {
    "rolls": "rolls", "Rolls": "rolls", "roll": "rolls",
    "nos": "rolls", "pcs": "rolls"
}

CHEM_UNIT_MAP = {
    "kg": "kg", "KG": "kg", "Kg": "kg",
    "kgs": "kg", "kilograms": "kg"
}

def normalize_units(df):
    """
    Normalize all unit variations to canonical units.
    
    Canonical units:
    - Paper/Strapping (M01-M05, M13-M14): all variants → 'rolls'
    - Adhesives/Inks (M06-M12): all variants → 'kg'
    
    Returns clean df with normalized 'unit' column and 'unit_normalized' flag.
    Prints a normalization report showing before/after counts per material.
    """
    df = df.copy()
    
    # Store original units for reporting
    df["original_unit"] = df["unit"].copy()
    df["unit_normalized"] = False
    
    # Build before counts
    before_counts = df.groupby(["material_id", "unit"]).size().reset_index(name="count")
    
    # Normalize
    for idx, row in df.iterrows():
        mat = row["material_id"]
        unit = row["unit"]
        
        if mat in PAPER_MATERIALS:
            new_unit = PAPER_UNIT_MAP.get(unit, unit)
        elif mat in CHEM_MATERIALS:
            new_unit = CHEM_UNIT_MAP.get(unit, unit)
        else:
            new_unit = unit
        
        if new_unit != unit:
            df.at[idx, "unit_normalized"] = True
        df.at[idx, "unit"] = new_unit
    
    # Build after counts
    after_counts = df.groupby(["material_id", "unit"]).size().reset_index(name="count")
    
    # Print normalization report
    print("\n" + "="*70)
    print("  D1: UNIT NORMALIZATION REPORT")
    print("="*70)
    
    total_normalized = df["unit_normalized"].sum()
    total_rows = len(df)
    print(f"\n  Total transactions processed: {total_rows:,}")
    print(f"  Units normalized:             {total_normalized:,}")
    print(f"  Already canonical:            {total_rows - total_normalized:,}")
    
    print(f"\n  {'Material':<12} {'Before (variants)':<40} {'After':<20}")
    print("  " + "-"*68)
    
    for mat in sorted(df["material_id"].unique()):
        before = before_counts[before_counts["material_id"]==mat]
        after = after_counts[after_counts["material_id"]==mat]
        
        before_str = ", ".join([f"{r['unit']}({r['count']})" for _, r in before.iterrows()])
        after_str = ", ".join([f"{r['unit']}({r['count']})" for _, r in after.iterrows()])
        
        print(f"  {mat:<12} {before_str:<40} {after_str:<20}")
    
    print("\n  ✅ All units normalized to canonical form.")
    print("="*70)
    
    return df


if __name__ == "__main__":
    import os
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    df = pd.read_csv(os.path.join(DATA_DIR, "inventory_transactions.csv"))
    df_clean = normalize_units(df)
    df_clean.to_csv(os.path.join(DATA_DIR, "inventory_transactions_clean.csv"), index=False)
    print("\n  Saved cleaned data to inventory_transactions_clean.csv")
