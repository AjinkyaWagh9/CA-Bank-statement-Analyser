import pandas as pd
from ca_analyzer.core.config import config

def generate_cash_deposit_analysis(df: pd.DataFrame) -> dict:
    """
    Identifies cash deposits, aggregates totals by bank, and flags transactions
    that violate tax limits (e.g. PAN card requirement > 50k, SFT reporting > 2L).
    """
    category_rules = config.category_rules
    # Cash deposits are credits where subcategory is Cash CDM/deposit or narration matches cash keywords
    cash_kws = category_rules.get("credit_categories", {}).get("Cash", {}).get("Cash Deposit", ["cash deposit", "cash dep", "cdm"])
    if not cash_kws:
        cash_kws = ["cash deposit", "cash dep", "cdm", "cash credit", "deposit cash"]
        
    # Standardize keywords check
    is_cash = df["Narration"].str.lower().apply(lambda x: any(kw in x for kw in cash_kws))
    cash_deposits = df[(df["Credit"] > 0.0) & (is_cash | (df["Category"] == "Cash"))].copy()
    
    if cash_deposits.empty:
        summary_df = pd.DataFrame(columns=["Bank", "Total Cash Deposits"])
        flagged_df = pd.DataFrame(columns=["Date", "Bank", "Narration", "Amount", "Flag Type", "Potential IT Scrutiny"])
        return {"summary": summary_df, "flagged": flagged_df}
        
    # Aggregate summary
    summary_df = cash_deposits.groupby("Bank_Name").agg(
        Total_Cash_Deposits=("Credit", "sum")
    ).reset_index().rename(columns={"Bank_Name": "Bank", "Total_Cash_Deposits": "Total Cash Deposits"})
    
    # Audit limits
    sft_threshold = config.thresholds.get("cash_deposit", {}).get("annual_threshold", 200000.0)
    single_threshold = config.thresholds.get("cash_deposit", {}).get("single_threshold", 50000.0)
    
    sft_flagged_banks = set()
    for _, row in summary_df.iterrows():
        if row["Total Cash Deposits"] > sft_threshold:
            sft_flagged_banks.add(row["Bank"])
            
    flagged = []
    for _, row in cash_deposits.iterrows():
        amount = row["Credit"]
        bank = row["Bank_Name"]
        flags = []
        scrutiny = "No"
        reasons = []
        
        if amount > single_threshold:
            flags.append(f"Single Deposit > {int(single_threshold/1000)}K")
            scrutiny = "Yes"
            reasons.append("PAN card required under Rule 114B; potential IT query for cash source verification.")
            
        if bank in sft_flagged_banks:
            flags.append(f"Annual Cash Deposits > {int(sft_threshold/1000)}K in Bank")
            scrutiny = "Yes"
            reasons.append(f"Exceeds SFT reportable limit under Rule 114E; bank submits details to Income Tax Dept.")
            
        if flags:
            flagged.append({
                "Date": row["Date"].strftime("%Y-%m-%d") if pd.notna(row["Date"]) else "N/A",
                "Bank": bank,
                "Narration": row["Narration"],
                "Amount": amount,
                "Flag Type": ", ".join(flags),
                "Potential IT Scrutiny": scrutiny + " - " + "; ".join(reasons)
            })
            
    flagged_df = pd.DataFrame(flagged)
    if flagged_df.empty:
        flagged_df = pd.DataFrame(columns=["Date", "Bank", "Narration", "Amount", "Flag Type", "Potential IT Scrutiny"])
        
    return {"summary": summary_df, "flagged": flagged_df}
