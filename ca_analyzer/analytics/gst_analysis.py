import pandas as pd

def generate_gst_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Identifies and classifies GST-related transactions (Payments, Receipts, Refunds)."""
    if df.empty:
        return pd.DataFrame(columns=["Date", "Bank", "Narration", "Amount", "Type"])
        
    df = df.copy()
    gst_mask = df["Narration"].str.lower().str.contains("gst", na=False)
    gst_txns = df[gst_mask].copy()
    
    if gst_txns.empty:
        return pd.DataFrame(columns=["Date", "Bank", "Narration", "Amount", "Type"])
        
    types = []
    amounts = []
    for _, row in gst_txns.iterrows():
        n = row["Narration"].lower()
        if row["Debit"] > 0.0:
            types.append("GST Payment")
            amounts.append(row["Debit"])
        elif "refund" in n or "ref" in n:
            types.append("GST Refund")
            amounts.append(row["Credit"])
        else:
            types.append("GST Receipt")
            amounts.append(row["Credit"])
            
    gst_txns["Type"] = types
    gst_txns["Amount"] = amounts
    
    gst_txns["Date"] = gst_txns["Date"].dt.strftime("%Y-%m-%d")
    gst_txns = gst_txns.rename(columns={"Bank_Name": "Bank"})
    
    return gst_txns[["Date", "Bank", "Narration", "Amount", "Type"]].sort_values(by="Date").reset_index(drop=True)
