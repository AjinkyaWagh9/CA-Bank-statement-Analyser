import pandas as pd

def generate_expense_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Groups debits by bank and head of expenditure (Utilities, Food, Travel, etc.)."""
    debits = df[df["Debit"] > 0.0].copy()
    if debits.empty:
        return pd.DataFrame(columns=["Expense Category", "Bank", "Amount", "Frequency"])
        
    categories = []
    for _, row in debits.iterrows():
        cat = row["Category"]
        subcat = row["Sub_Category"]
        narr = row["Narration"].lower()
        
        if cat == "Utilities":
            exp_cat = "Utilities"
        elif cat == "Insurance":
            exp_cat = "Insurance"
        elif cat == "Taxes":
            exp_cat = "Taxes"
        elif cat == "Investments":
            exp_cat = "Investments"
        elif cat == "Rent":
            exp_cat = "Rent Payments"
        elif cat == "Loans" or subcat == "Loan EMI":
            exp_cat = "Loan Payments"
        elif cat == "Cash":
            exp_cat = "Cash Withdrawals"
        elif cat == "Bounces":
            exp_cat = "Cheque Bounces"
        elif cat == "Food" or "food" in subcat.lower() or any(x in narr for x in ["swiggy", "zomato", "restaurant", "hotel", "cafe"]):
            exp_cat = "Food"
        elif cat == "Travel" or "travel" in subcat.lower() or any(x in narr for x in ["uber", "ola", "travel", "fuel", "petrol", "irctc", "flight"]):
            exp_cat = "Travel"
        elif cat == "Shopping" or "shopping" in subcat.lower() or any(x in narr for x in ["amazon", "flipkart", "myntra", "retail", "shopping"]):
            exp_cat = "Shopping"
        elif cat == "Medical" or "medical" in subcat.lower() or any(x in narr for x in ["hospital", "pharmacy", "medical", "clinic", "doctor"]):
            exp_cat = "Medical"
        else:
            exp_cat = "Others"
            
        categories.append(exp_cat)
        
    debits["Expense_Category"] = categories
    
    summary = debits.groupby(["Expense_Category", "Bank_Name"]).agg(
        Amount=("Debit", "sum"),
        Frequency=("Debit", "count")
    ).reset_index()
    
    summary = summary.rename(columns={"Expense_Category": "Expense Category", "Bank_Name": "Bank"})
    return summary.sort_values(by="Amount", ascending=False).reset_index(drop=True)
