import pandas as pd
from ca_analyzer.core.utilities import parse_date, parse_amount
from ca_analyzer.core.schemas import CANONICAL_COLUMNS

def standardize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardizes a parsed bank-specific DataFrame to canonical column structures.
    Purges duplicate header rows containing multiple header keywords.
    """
    df = df.copy()
    
    # 1. Filter out duplicate header rows based on header keywords
    HEADER_KEYWORDS = [
        "DATE", "BANK", "NARRATION", "DEBIT", "CREDIT", "BALANCE", 
        "AMOUNT", "CATEGORY", "SUB CATEGORY", "INCOME TYPE", "EXPENSE TYPE"
    ]
    
    def is_header_row(row):
        match_count = 0
        for val in row.values:
            if pd.isna(val):
                continue
            val_str = str(val).upper().strip()
            for kw in HEADER_KEYWORDS:
                if kw in val_str:
                    match_count += 1
                    break
        return match_count >= 2

    # Drop any row that matches 2 or more header keywords
    header_mask = df.apply(is_header_row, axis=1)
    df = df[~header_mask].reset_index(drop=True)
    
    # Rename columns to standard internal names
    rename_map = {
        "raw_date": "Date",
        "raw_narration": "Narration",
        "raw_chq_ref": "Chq_Ref",
        "raw_debit": "Debit",
        "raw_credit": "Credit",
        "raw_balance": "Balance"
    }
    df = df.rename(columns=rename_map)
    
    # Clean and format Date
    df["Date"] = df["Date"].apply(parse_date)
    df = df.dropna(subset=["Date"]).reset_index(drop=True)
    
    # Check statement order and reverse if Newest -> Oldest
    if len(df) >= 2:
        first_date = df["Date"].iloc[0]
        last_date = df["Date"].iloc[-1]
        if pd.notna(first_date) and pd.notna(last_date) and first_date > last_date:
            df = df.iloc[::-1].reset_index(drop=True)
            
    # Tag sequence chronologically
    df["txn_seq"] = range(len(df))
    
    # Clean numeric fields
    df["Debit"] = df["Debit"].apply(parse_amount)
    df["Credit"] = df["Credit"].apply(parse_amount)
    df["Balance"] = df["Balance"].apply(parse_amount)
    
    # Initialize other schema fields if not present
    for col in ["Merchant_Name", "Transaction_Mode", "Counterparty", "Category", "Sub_Category"]:
        if col not in df.columns:
            df[col] = ""
            
    # Ensure all canonical columns exist
    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""
            
    return df[CANONICAL_COLUMNS]
