import pandas as pd

def generate_tds_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Identifies tax deduction transactions and extracts the relevant section (194A, 194J, 194C)."""
    if df.empty:
        return pd.DataFrame(columns=["Date", "Bank", "Narration", "Amount", "Section"])
        
    df = df.copy()
    tds_mask = df["Narration"].str.lower().apply(
        lambda x: any(kw in x for kw in ["tds", "194a", "194j", "194c", "tax deducted"])
    )
    tds_txns = df[tds_mask].copy()
    
    if tds_txns.empty:
        return pd.DataFrame(columns=["Date", "Bank", "Narration", "Amount", "Section"])
        
    sections = []
    amounts = []
    for _, row in tds_txns.iterrows():
        n = row["Narration"].lower()
        amount = max(row["Debit"], row["Credit"])
        amounts.append(amount)
        
        if "194a" in n or "int" in n:
            sect = "Sec 194A (Interest)"
        elif "194j" in n or "prof" in n:
            sect = "Sec 194J (Professional Fees)"
        elif "194c" in n or "contract" in n:
            sect = "Sec 194C (Contractors)"
        else:
            sect = "Sec 194 (TDS General)"
        sections.append(sect)
        
    tds_txns["Section"] = sections
    tds_txns["Amount"] = amounts
    
    tds_txns["Date"] = tds_txns["Date"].dt.strftime("%Y-%m-%d")
    tds_txns = tds_txns.rename(columns={"Bank_Name": "Bank"})
    
    return tds_txns[["Date", "Bank", "Narration", "Amount", "Section"]].sort_values(by="Date").reset_index(drop=True)
