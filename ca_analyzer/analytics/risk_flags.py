import pandas as pd
from ca_analyzer.core.config import config

def generate_risk_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Scans transactions for audit risks, round-sum patterns, sudden inflows, 
    large ATM withdrawals, layering/circular transactions, and negative cashflow months.
    """
    if df.empty:
        return pd.DataFrame(columns=["Date", "Bank", "Transaction Details", "Amount", "Risk Flag Type", "Severity"])
        
    df = df.copy()
    flags = []
    
    # 1. Round Amounts check
    for _, row in df.iterrows():
        amount = max(row["Debit"], row["Credit"])
        if amount >= 50000.0 and amount % 50000.0 == 0.0:
            flags.append({
                "Date": row["Date"],
                "Bank": row["Bank_Name"],
                "Transaction Details": f"{row['Narration']} (Exact multiple of 50K)",
                "Amount": amount,
                "Risk Flag Type": "Round Value Transfer",
                "Severity": "Medium"
            })
            
    # 2. Large Withdrawals
    withdrawal_threshold = config.thresholds.get("cash_deposit", {}).get("annual_threshold", 200000.0)
    for _, row in df[df["Debit"] >= withdrawal_threshold].iterrows():
        flags.append({
            "Date": row["Date"],
            "Bank": row["Bank_Name"],
            "Transaction Details": row["Narration"],
            "Amount": row["Debit"],
            "Risk Flag Type": "Large Outflow/Withdrawal",
            "Severity": "High"
        })
        
    # 3. Sudden Inflow
    inflow_threshold = config.thresholds.get("cash_deposit", {}).get("annual_threshold", 200000.0)
    for _, row in df[df["Credit"] >= inflow_threshold].iterrows():
        flags.append({
            "Date": row["Date"],
            "Bank": row["Bank_Name"],
            "Transaction Details": row["Narration"],
            "Amount": row["Credit"],
            "Risk Flag Type": "Sudden High Inflow",
            "Severity": "High"
        })
        
    # 4. Layering: Credit followed by a similar Debit (within 5%, within 2 days)
    sorted_df = df.sort_values(by="Date").reset_index(drop=True)
    for i in range(len(sorted_df)):
        row_i = sorted_df.iloc[i]
        if row_i["Credit"] > 10000.0:
            for j in range(i + 1, min(i + 20, len(sorted_df))):
                row_j = sorted_df.iloc[j]
                day_diff = (row_j["Date"] - row_i["Date"]).days
                if day_diff > 2:
                    break
                if row_j["Debit"] > 0.0:
                    diff_pct = abs(row_j["Debit"] - row_i["Credit"]) / row_i["Credit"]
                    if diff_pct <= 0.05:
                        flags.append({
                            "Date": row_j["Date"],
                            "Bank": row_j["Bank_Name"],
                            "Transaction Details": f"Inflow of {row_i['Credit']:.0f} on {row_i['Date'].strftime('%d-%b')} followed by Outflow of {row_j['Debit']:.0f} on {row_j['Date'].strftime('%d-%b')}",
                            "Amount": row_j["Debit"],
                            "Risk Flag Type": "Potential Layering / Circular Flow",
                            "Severity": "High"
                        })
                        
    # 5. Negative Cashflow Months
    df["Year_Month"] = df["Date"].dt.to_period("M")
    monthly = df.groupby(["Year_Month", "Bank_Name"]).agg(
        Credits=("Credit", "sum"),
        Debits=("Debit", "sum")
    ).reset_index()
    for _, row in monthly[monthly["Debits"] > monthly["Credits"]].iterrows():
        net = row["Debits"] - row["Credits"]
        dt_rep = row["Year_Month"].to_timestamp()
        flags.append({
            "Date": dt_rep,
            "Bank": row["Bank_Name"],
            "Transaction Details": f"Negative Cashflow for Month {row['Year_Month']} (Credits: {row['Credits']:.2f}, Debits: {row['Debits']:.2f})",
            "Amount": net,
            "Risk Flag Type": "Negative Cashflow Month",
            "Severity": "Medium"
        })
        
    if not flags:
        return pd.DataFrame(columns=["Date", "Bank", "Transaction Details", "Amount", "Risk Flag Type", "Severity"])
        
    flags_df = pd.DataFrame(flags)
    flags_df = flags_df.sort_values(by="Date").reset_index(drop=True)
    flags_df["Date"] = flags_df["Date"].dt.strftime("%Y-%m-%d")
    return flags_df
