import pandas as pd
from ca_analyzer.core.utilities import parse_date, parse_amount, get_financial_year, make_transaction_id
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

    # --- Phase 0: Derive Financial_Year from transaction Date ---
    df["Financial_Year"] = df["Date"].apply(get_financial_year)

    # --- Phase 0: Generate deterministic Transaction_ID ---
    def _make_txid(row):
        return make_transaction_id(
            bank_name=row.get("Bank_Name", ""),
            account_number=row.get("Account_Number", ""),
            date=row["Date"],
            narration=row.get("Narration", ""),
            debit=row.get("Debit", 0.0),
            credit=row.get("Credit", 0.0),
            balance=row.get("Balance", 0.0),
            txn_seq=row.get("txn_seq", 0),
        )

    df["Transaction_ID"] = df.apply(_make_txid, axis=1)

    # --- Phase 0: Default editable override columns ---
    # Category_Final / Sub_Category_Final will be synced from Category/Sub_Category
    # after apply_categorization runs (see consolidator.py). Initialise as empty here
    # so the canonical column list is satisfied.
    if "Category_Final" not in df.columns:
        df["Category_Final"] = ""
    if "Sub_Category_Final" not in df.columns:
        df["Sub_Category_Final"] = ""

    # Ensure all canonical columns exist (fills missing traceability + flag columns with "")
    for col in CANONICAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df[CANONICAL_COLUMNS]
