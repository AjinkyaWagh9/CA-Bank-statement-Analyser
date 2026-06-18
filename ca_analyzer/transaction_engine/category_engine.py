import pandas as pd
from ca_analyzer.transaction_engine.rules import get_category_rules


def categorise_transaction(narration: str, debit: float, credit: float) -> tuple:
    """
    Matches a transaction narration string against credit/debit keyword rules.

    Returns: (category, subcategory, confidence, match_reason)
      - confidence: "High" | "Medium" | "Low"
      - match_reason: the matched keyword, or a short descriptor for default/fallback
    """
    n = narration.lower()
    rules = get_category_rules()

    # -----------------------------------------------------------------------
    # 1. Credits (Inflows)
    # -----------------------------------------------------------------------
    if credit > 0.0:
        default_cat = "Miscellaneous"
        default_sub = "Miscellaneous Inflow"

        credit_rules = rules.get("credit_categories", {})
        for cat_name, subcats in credit_rules.items():
            for subcat_name, keywords in subcats.items():
                matched_kw = next((k for k in keywords if k in n), None)
                if matched_kw is not None:
                    # Assess confidence: single short token -> Medium, longer/specific -> High
                    if len(matched_kw) <= 3:
                        confidence = "Medium"
                        reason = f"short token: '{matched_kw}'"
                    else:
                        confidence = "High"
                        reason = f"keyword: '{matched_kw}'"
                    return cat_name, subcat_name, confidence, reason

        # No rule matched — credit is generic inflow
        return default_cat, default_sub, "Low", "no rule matched"

    # -----------------------------------------------------------------------
    # 2. Debits (Outflows)
    # -----------------------------------------------------------------------
    elif debit > 0.0:
        default_cat = "Others"
        default_sub = "Other Expense"

        # Cash withdrawal check with exclusion rules
        cash_rules = rules.get("debit_categories", {}).get("Cash", {}).get("Cash Withdrawal", [])
        matched_cash = next((k for k in cash_rules if k in n), None)
        if matched_cash is not None:
            exclude_keywords = rules.get("cash_withdrawal_exclude", [])
            if not any(k in n for k in exclude_keywords):
                confidence = "High" if len(matched_cash) > 3 else "Medium"
                reason = f"keyword: '{matched_cash}'"
                return "Cash", "Cash Withdrawal", confidence, reason

        debit_rules = rules.get("debit_categories", {})
        for cat_name, subcats in debit_rules.items():
            for subcat_name, keywords in subcats.items():
                if cat_name == "Cash" and subcat_name == "Cash Withdrawal":
                    continue
                matched_kw = next((k for k in keywords if k in n), None)
                if matched_kw is not None:
                    if len(matched_kw) <= 3:
                        confidence = "Medium"
                        reason = f"short token: '{matched_kw}'"
                    else:
                        confidence = "High"
                        reason = f"keyword: '{matched_kw}'"
                    return cat_name, subcat_name, confidence, reason

        # No rule matched — fallback
        return default_cat, default_sub, "Low", "no rule matched"

    # -----------------------------------------------------------------------
    # 3. Zero debit and zero credit (unusual/erroneous row)
    # -----------------------------------------------------------------------
    return "Others", "Other Transactions", "Low", "no rule matched"


def apply_categorization(df: pd.DataFrame) -> pd.DataFrame:
    """Runs keyword checks across all rows, setting Category, Sub_Category,
    Confidence, and Match_Reason."""
    df = df.copy()
    cats = []
    subcats = []
    confidences = []
    reasons = []

    for _, row in df.iterrows():
        cat, subcat, conf, reason = categorise_transaction(
            row["Narration"],
            row["Debit"],
            row["Credit"],
        )
        cats.append(cat)
        subcats.append(subcat)
        confidences.append(conf)
        reasons.append(reason)

    df["Category"] = cats
    df["Sub_Category"] = subcats
    df["Confidence"] = confidences
    df["Match_Reason"] = reasons
    return df
