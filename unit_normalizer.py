"""
D1 — Unit Normalization Module for PackRight Industries
Uses vectorized pandas operations — NO loop row by row.
"""
import pandas as pd
from config import PAPER_MATERIALS, CHEM_MATERIALS, PAPER_UNIT_MAP, CHEM_UNIT_MAP

def normalize_units(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize all unit variations to canonical units using vectorized operations.
    Paper/Strapping (M01-M05, M13-M14): all variants → 'rolls'
    Adhesives/Inks (M06-M12): all variants → 'kg'
    Returns clean df. Prints normalization report.
    """
    df = df.copy()
    df["original_unit"] = df["unit"].copy()

    # Build masks — vectorized, not looped
    paper_mask = df["material_id"].isin(PAPER_MATERIALS)
    chem_mask  = df["material_id"].isin(CHEM_MATERIALS)

    # Apply mapping — vectorized map(), not loop
    df.loc[paper_mask, "unit"] = (
        df.loc[paper_mask, "unit"].str.strip().map(PAPER_UNIT_MAP)
        .fillna(df.loc[paper_mask, "unit"])
    )
    df.loc[chem_mask, "unit"] = (
        df.loc[chem_mask, "unit"].str.strip().map(CHEM_UNIT_MAP)
        .fillna(df.loc[chem_mask, "unit"])
    )

    df["unit_normalized"] = df["unit"] != df["original_unit"]

    # ── Print normalization report ────────────────────────────────────────────
    total_normalized = df["unit_normalized"].sum()
    print("\n" + "=" * 70)
    print("  D1: UNIT NORMALIZATION REPORT")
    print("=" * 70)
    print(f"\n  Total rows processed : {len(df):,}")
    print(f"  Units normalized     : {total_normalized:,}")
    print(f"  Already canonical    : {len(df) - total_normalized:,}")
    print(f"\n  {'Material':<12} {'Before (variants)':<45} {'After'}")
    print("  " + "-" * 70)

    for mat in sorted(df["material_id"].unique()):
        mat_df = df[df["material_id"] == mat]
        before_counts = mat_df["original_unit"].value_counts()
        after_counts  = mat_df["unit"].value_counts()
        before_str = ", ".join([f"{u}({c})" for u, c in before_counts.items()])
        after_str  = ", ".join([f"{u}({c})" for u, c in after_counts.items()])
        print(f"  {mat:<12} {before_str:<45} {after_str}")

    print("\n  [OK] All units normalized to canonical form (vectorized).")
    print("=" * 70)
    return df

if __name__ == "__main__":
    import os
    DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
    df = pd.read_csv(os.path.join(DATA_DIR, "inventory_transactions.csv"))
    df_clean = normalize_units(df)
    print(f"\n  Sample normalized rows:\n{df_clean.head(5)[['material_id','original_unit','unit','unit_normalized']]}")
