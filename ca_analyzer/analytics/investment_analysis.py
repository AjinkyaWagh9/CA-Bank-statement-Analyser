import pandas as pd

def generate_investment_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Identifies investment and insurance transactions and classifies them (SIP, PPF, NPS, stocks, etc.)."""
    if df.empty:
        return pd.DataFrame(columns=["Date", "Bank", "Narration", "Amount", "Investment Type"])
        
    df = df.copy()
    
    is_invest = (df["Category"] == "Investments") | (df["Sub_Category"] == "Investment Outflow")
    is_insurance = (df["Category"] == "Insurance") | (df["Sub_Category"] == "Insurance Premium")
    
    invest_kws = ["sip", "mutual fund", "ppf", "nps", "elss", "tax saver", "post office", 
                  "nsc", "kvp", "sukanya", "demat", "nsdl", "cdsl", "stocks", "shares", 
                  "equity", "fd ", "fixed deposit", "term deposit"]
    is_by_narr = df["Narration"].str.lower().apply(lambda x: any(kw in x for kw in invest_kws))
    
    inv_df = df[is_invest | is_insurance | is_by_narr].copy()
    
    if inv_df.empty:
        return pd.DataFrame(columns=["Date", "Bank", "Narration", "Amount", "Investment Type"])
        
    types = []
    amounts = []
    for _, row in inv_df.iterrows():
        n = row["Narration"].lower()
        amount = max(row["Debit"], row["Credit"])
        amounts.append(amount)
        
        if "sip" in n:
            itype = "SIP"
        elif "mutual fund" in n or " elss" in n or "mf " in n or "units" in n:
            itype = "Mutual Fund"
        elif "premium" in n or "insurance" in n or "lic" in n or "jeevan" in n:
            itype = "Insurance Premium"
        elif "ppf" in n:
            itype = "PPF"
        elif "nps" in n:
            itype = "NPS"
        elif "fd" in n or "fixed deposit" in n or "term deposit" in n:
            itype = "Fixed Deposit"
        elif any(x in n for x in ["demat", "nsdl", "cdsl", "stock", "share", "equity"]):
            itype = "Stocks/Equities"
        else:
            itype = "Other Investment"
        types.append(itype)
        
    inv_df["Investment Type"] = types
    inv_df["Amount"] = amounts
    
    inv_df["Date"] = inv_df["Date"].dt.strftime("%Y-%m-%d")
    inv_df = inv_df.rename(columns={"Bank_Name": "Bank"})
    
    return inv_df[["Date", "Bank", "Narration", "Amount", "Investment Type"]].sort_values(by="Date").reset_index(drop=True)
