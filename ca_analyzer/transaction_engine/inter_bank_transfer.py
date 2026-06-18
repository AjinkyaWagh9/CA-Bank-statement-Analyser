"""
inter_bank_transfer.py — BRD §8.2 Inter-Bank Transfer Detection
================================================================
Identifies fund movements between the SAME taxpayer's accounts held at
different banks (or different account numbers at the same bank).

Matching rules
--------------
* A Debit row in account A matches a Credit row in account B when:
  - Account_Number differs between the two rows.
  - abs(Debit - Credit) <= 1.00  (tolerance for rounding / charges).
  - abs(Date_A - Date_B) <= 1 calendar day.
* Matching is greedy: candidates are sorted by (date-proximity, amount-diff)
  and each row may be matched at most once.
* Matches within the same Person_Name are preferred over cross-person matches.

Efficiency
----------
Rows are first bucketed by rounded amount (floor to nearest rupee) so the
inner comparison is only performed between rows whose amounts are close,
avoiding an O(n²) scan over the full DataFrame.
"""

from __future__ import annotations

import math
from typing import List, Tuple

import pandas as pd


_IBT_CATEGORY = "Inter-Bank Transfer"
_IBT_SUBCAT = "Inter-Bank Transfer"
_IBT_CONFIDENCE = "High"


def tag_inter_bank_transfers(df: pd.DataFrame) -> pd.DataFrame:
    """Detect inter-bank transfers across the same taxpayer's accounts.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: Person_Name, Bank_Name, Account_Number, Date
        (datetime64), Debit (float), Credit (float), Narration, Counterparty,
        Category, Sub_Category, Confidence, txn_seq.

    Returns
    -------
    pd.DataFrame
        A copy of *df* with Category / Sub_Category / Confidence updated for
        matched rows, and a new ``Transfer_Group`` column (empty string for
        unmatched rows, "IBT-NNNN" for matched pairs).
    """
    df = df.copy()

    # Initialise Transfer_Group column if absent
    if "Transfer_Group" not in df.columns:
        df["Transfer_Group"] = ""
    else:
        df["Transfer_Group"] = df["Transfer_Group"].fillna("").astype(str)

    # Work on integer index positions to safely update df later
    debit_idx: List[int] = df.index[df["Debit"] > 0].tolist()
    credit_idx: List[int] = df.index[df["Credit"] > 0].tolist()

    if not debit_idx or not credit_idx:
        return df

    # -----------------------------------------------------------------------
    # Build amount-bucket lookup for credits
    # Bucket key = floor(Credit) so that a debit of 10 000.50 can find a
    # credit of 10 000.00 (difference ≤ 1.00).
    # -----------------------------------------------------------------------
    from collections import defaultdict

    credit_buckets: dict = defaultdict(list)
    for ci in credit_idx:
        row = df.loc[ci]
        bucket = math.floor(row["Credit"])
        credit_buckets[bucket].append(ci)

    matched_credits: set = set()
    matched_debits: set = set()

    ibt_counter = 0

    # -----------------------------------------------------------------------
    # For each debit row find candidate credits, rank, pick best unmatched
    # -----------------------------------------------------------------------
    for di in debit_idx:
        if di in matched_debits:
            continue

        d_row = df.loc[di]
        d_amount = d_row["Debit"]
        d_date: pd.Timestamp = d_row["Date"]
        d_account = d_row["Account_Number"]
        d_person = d_row["Person_Name"]

        # Candidate buckets: floor(d_amount-1) .. floor(d_amount+1)
        base = math.floor(d_amount)
        candidate_ci: List[int] = []
        for b in (base - 1, base, base + 1):
            candidate_ci.extend(credit_buckets.get(b, []))

        if not candidate_ci:
            continue

        # Filter and score candidates
        scored: List[Tuple[float, float, bool, int]] = []
        for ci in candidate_ci:
            if ci in matched_credits:
                continue
            c_row = df.loc[ci]
            # Must be a different account
            if c_row["Account_Number"] == d_account:
                continue
            # Amount tolerance
            amt_diff = abs(d_amount - c_row["Credit"])
            if amt_diff > 1.0:
                continue
            # Date tolerance
            date_diff_days = abs((c_row["Date"] - d_date).days)
            if date_diff_days > 1:
                continue
            # Prefer same Person_Name (lower sort value = preferred)
            same_person = not (c_row["Person_Name"] == d_person)  # False=0 preferred
            scored.append((date_diff_days, amt_diff, same_person, ci))

        if not scored:
            continue

        # Best match: same-person first, then closest date, then smallest amt diff
        scored.sort(key=lambda x: (x[2], x[0], x[1]))
        best_ci = scored[0][3]

        # Record the match
        ibt_counter += 1
        group_id = f"IBT-{ibt_counter:04d}"

        for idx in (di, best_ci):
            df.at[idx, "Category"] = _IBT_CATEGORY
            df.at[idx, "Sub_Category"] = _IBT_SUBCAT
            df.at[idx, "Confidence"] = _IBT_CONFIDENCE
            df.at[idx, "Transfer_Group"] = group_id

        matched_debits.add(di)
        matched_credits.add(best_ci)

    return df
