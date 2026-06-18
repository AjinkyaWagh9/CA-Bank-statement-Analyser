"""
BRD §7.1 — Pattern-based salary detection.

Detects recurring monthly credits from the same counterparty that look like
salary even when no salary keyword was matched by the keyword engine.
"""

import pandas as pd


def detect_salary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect potential salary credits via recurring monthly pattern.

    Rules (BRD §7.1):
    - Only considers Credit > 0 rows whose Category is NOT already "Salary"
      (preserves high-confidence keyword-based detections).
    - Groups eligible rows by Counterparty; skips blank / "N/A" / "OTHERS".
    - A counterparty qualifies if it has credits in >= 3 distinct calendar months
      where each credit amount is within ±5% of the group's median credit.
    - Qualifying rows get Category="Salary", Sub_Category="Potential Salary",
      Confidence="Medium".
    - All other rows are left untouched.

    Returns a copy of df with the same index and column order.
    """
    result = df.copy()

    SKIP_COUNTERPARTIES = {"", "n/a", "others"}

    # Candidate mask: credit rows not already categorised as Salary or Inter-Bank Transfer
    candidate_mask = (
        (result["Credit"] > 0)
        & (result["Category"] != "Salary")
        & (result["Category"] != "Inter-Bank Transfer")
    )

    candidates = result.loc[candidate_mask].copy()
    if candidates.empty:
        return result

    # Normalise counterparty for grouping (keep original values in df)
    candidates["_cp_norm"] = candidates["Counterparty"].fillna("").str.strip().str.lower()

    # Remove counterparties we want to skip
    candidates = candidates[~candidates["_cp_norm"].isin(SKIP_COUNTERPARTIES)]

    if candidates.empty:
        return result

    # Extract year-month for each row
    candidates["_ym"] = candidates["Date"].dt.to_period("M")

    qualifying: list[int] = []

    for _cp, grp in candidates.groupby("_cp_norm", group_keys=False):
        median_credit = grp["Credit"].median()
        lo = median_credit * 0.95
        hi = median_credit * 1.05

        # Rows within ±5% of median
        within_band = grp[grp["Credit"].between(lo, hi)]

        # Distinct calendar months among those rows
        distinct_months = within_band["_ym"].nunique()

        if distinct_months >= 3:
            qualifying.extend(within_band.index.tolist())

    valid_idx = pd.Index(qualifying).unique()
    valid_idx = valid_idx[valid_idx.isin(result.index)]

    result.loc[valid_idx, "Category"] = "Salary"
    result.loc[valid_idx, "Sub_Category"] = "Potential Salary"
    result.loc[valid_idx, "Confidence"] = "Medium"

    return result
