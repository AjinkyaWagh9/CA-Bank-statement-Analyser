import pandas as pd

def get_monthly_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Prepares Monthly Credits, Debits, and Closing Balance for charts."""
    if df.empty:
        return pd.DataFrame(columns=["Month", "Credits", "Debits", "Closing Balance"])
        
    df = df.copy()
    df["Month_Str"] = df["Date"].dt.strftime("%Y-%m")
    
    # Group by month and compute sums/last balance
    monthly = df.groupby("Month_Str").agg(
        Credits=("Credit", "sum"),
        Debits=("Debit", "sum"),
        Closing_Balance=("Balance", "last")
    ).reset_index().rename(columns={"Month_Str": "Month", "Closing_Balance": "Closing Balance"})
    
    return monthly.sort_values(by="Month")

def get_bank_contributions(df: pd.DataFrame) -> pd.DataFrame:
    """Prepares bank wise credit contribution for Donut Chart."""
    if df.empty:
        return pd.DataFrame(columns=["Bank", "Credit Amount"])
    
    cont = df.groupby("Bank_Name").agg(
        Credit_Amount=("Credit", "sum")
    ).reset_index().rename(columns={"Bank_Name": "Bank", "Credit_Amount": "Credit Amount"})
    
    return cont
