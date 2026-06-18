import pandas as pd

def generate_income_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Groups credits by bank and head of income (Salary, Rent, Interest, etc.)."""
    credits = df[df["Credit"] > 0.0].copy()
    if credits.empty:
        return pd.DataFrame(columns=["Income Type", "Bank", "Amount", "Frequency"])
        
    income_types = []
    for _, row in credits.iterrows():
        cat = row["Category"]
        subcat = row["Sub_Category"]
        narr = row["Narration"].lower()
        
        if cat == "Salary":
            itype = "Salary"
        elif cat == "House Property" or "rental" in subcat.lower():
            itype = "Rent"
        elif "interest" in subcat.lower() or "interest" in cat.lower():
            itype = "Interest"
        elif cat == "Business/Profession" or "gst refund" in narr:
            itype = "Business Receipts"
        elif "refund" in narr or "reversal" in narr:
            itype = "Refunds"
        else:
            itype = "Miscellaneous"
        income_types.append(itype)
        
    credits["Income_Type"] = income_types
    
    summary = credits.groupby(["Income_Type", "Bank_Name"]).agg(
        Amount=("Credit", "sum"),
        Frequency=("Credit", "count")
    ).reset_index()
    
    summary = summary.rename(columns={"Income_Type": "Income Type", "Bank_Name": "Bank"})
    return summary.sort_values(by="Amount", ascending=False).reset_index(drop=True)
