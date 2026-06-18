import pandas as pd
from ca_analyzer.transaction_engine.rules import get_category_rules

def categorise_transaction(narration: str, debit: float, credit: float) -> tuple:
    """Matches a transaction narration string against credit/debit keyword rules."""
    n = narration.lower()
    rules = get_category_rules()
    
    category = "Others"
    subcategory = "Other Transactions"
    
    # 1. Credits (Inflows)
    if credit > 0.0:
        category = "Miscellaneous"
        subcategory = "Miscellaneous Inflow"
        
        credit_rules = rules.get("credit_categories", {})
        for cat_name, subcats in credit_rules.items():
            for subcat_name, keywords in subcats.items():
                if any(k in n for k in keywords):
                    return cat_name, subcat_name
                    
    # 2. Debits (Outflows)
    elif debit > 0.0:
        category = "Others"
        subcategory = "Other Expense"
        
        # Check cash withdrawal first with exclusion rules
        cash_rules = rules.get("debit_categories", {}).get("Cash", {}).get("Cash Withdrawal", [])
        if any(k in n for k in cash_rules):
            exclude_keywords = rules.get("cash_withdrawal_exclude", [])
            if not any(k in n for k in exclude_keywords):
                return "Cash", "Cash Withdrawal"
                
        debit_rules = rules.get("debit_categories", {})
        for cat_name, subcats in debit_rules.items():
            for subcat_name, keywords in subcats.items():
                if cat_name == "Cash" and subcat_name == "Cash Withdrawal":
                    continue
                if any(k in n for k in keywords):
                    return cat_name, subcat_name
                    
    return category, subcategory

def apply_categorization(df: pd.DataFrame) -> pd.DataFrame:
    """Runs keyword checks across all rows, setting Category and Sub_Category."""
    df = df.copy()
    cats = []
    subcats = []
    
    for _, row in df.iterrows():
        cat, subcat = categorise_transaction(
            row["Narration"], 
            row["Debit"], 
            row["Credit"]
        )
        cats.append(cat)
        subcats.append(subcat)
        
    df["Category"] = cats
    df["Sub_Category"] = subcats
    return df
