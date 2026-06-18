import pandas as pd
from ca_analyzer.core.config import config

def generate_high_value_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identifies high value transactions defined as:
    1) Max of Debit/Credit >= threshold (default 50,000)
    2) OR within the top 5% (95th percentile) of all transaction sizes.
    """
    if df.empty:
        return pd.DataFrame(columns=["Date", "Bank", "Description", "Amount", "Type"])
        
    df = df.copy()
    df["Txn_Amount"] = df[["Debit", "Credit"]].max(axis=1)
    
    threshold = config.thresholds.get("high_value_transaction", {}).get("threshold", 50000.0)
    pct_95 = df["Txn_Amount"].quantile(0.95)
    
    hvt_mask = (df["Txn_Amount"] >= threshold) | (df["Txn_Amount"] >= pct_95)
    hvt_df = df[hvt_mask].copy()
    
    if hvt_df.empty:
        return pd.DataFrame(columns=["Date", "Bank", "Description", "Amount", "Type"])
        
    types = []
    amounts = []
    for _, row in hvt_df.iterrows():
        if row["Credit"] > 0.0:
            types.append("Credit")
            amounts.append(row["Credit"])
        else:
            types.append("Debit")
            amounts.append(row["Debit"])
            
    hvt_df["Type"] = types
    hvt_df["Amount"] = amounts
    
    hvt_df["Date"] = hvt_df["Date"].dt.strftime("%Y-%m-%d")
    hvt_df = hvt_df.rename(columns={"Bank_Name": "Bank", "Narration": "Description"})
    
    return hvt_df[["Date", "Bank", "Description", "Amount", "Type"]].sort_values(by="Amount", ascending=False).reset_index(drop=True)
