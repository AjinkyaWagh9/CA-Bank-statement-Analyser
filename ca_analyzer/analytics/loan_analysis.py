import pandas as pd

def generate_loan_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Identifies EMI debits, groups them by loan type, and aggregates median EMI values."""
    debits = df[df["Debit"] > 0.0].copy()
    if debits.empty:
        return pd.DataFrame(columns=["Loan Type", "Monthly EMI", "Bank", "Frequency"])
        
    # Standard loan filter
    loan_txns = debits[(debits["Category"] == "Loans") | (debits["Sub_Category"] == "Loan EMI")].copy()
    
    # Catch narrations containing loan/EMI indicators
    is_loan_by_narr = debits["Narration"].str.lower().apply(lambda x: "emi" in x or "loan repayment" in x or "mortgage" in x)
    loan_txns = pd.concat([loan_txns, debits[is_loan_by_narr]]).drop_duplicates(subset=["Date", "Narration", "Debit", "Balance"])
    
    if loan_txns.empty:
        return pd.DataFrame(columns=["Loan Type", "Monthly EMI", "Bank", "Frequency"])
        
    loan_types = []
    for _, row in loan_txns.iterrows():
        n = row["Narration"].lower()
        if "home" in n or "house" in n or "housing" in n or "hl " in n:
            ltype = "Home Loan"
        elif "car" in n or "auto" in n or "vehicle" in n or "honda" in n or "maruti" in n or "cl " in n:
            ltype = "Car Loan"
        elif "credit card" in n or "sbi card" in n or "cc emi" in n or "card payment" in n or "cc pay" in n:
            ltype = "Credit Card EMI"
        else:
            ltype = "Personal Loan"
        loan_types.append(ltype)
        
    loan_txns["Loan_Type"] = loan_types
    
    summary = loan_txns.groupby(["Loan_Type", "Bank_Name"]).agg(
        Monthly_EMI=("Debit", "median"), # Median is robust to represent fixed EMI
        Frequency=("Debit", "count")
    ).reset_index()
    
    summary = summary.rename(columns={"Loan_Type": "Loan Type", "Monthly_EMI": "Monthly EMI", "Bank_Name": "Bank"})
    return summary.sort_values(by="Monthly EMI", ascending=False).reset_index(drop=True)
