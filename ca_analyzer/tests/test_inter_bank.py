"""Tests for inter_bank_transfer.tag_inter_bank_transfers (BRD §8.2)."""

import pandas as pd
import pytest

from ca_analyzer.transaction_engine.inter_bank_transfer import tag_inter_bank_transfers


def _make_df() -> pd.DataFrame:
    """Small synthetic DataFrame: 2 accounts, 1 clear matching pair + non-matches."""
    rows = [
        # idx 0 — Debit 5000 in ACC-001 on 2024-01-10  ← should match idx 3
        {
            "Person_Name": "Ramesh Kumar",
            "Bank_Name": "HDFC",
            "Account_Number": "ACC-001",
            "Date": pd.Timestamp("2024-01-10"),
            "Debit": 5000.0,
            "Credit": 0.0,
            "Narration": "NEFT to self",
            "Counterparty": "",
            "Category": "Others",
            "Sub_Category": "Other Expense",
            "Confidence": "Low",
            "txn_seq": 1,
        },
        # idx 1 — Debit 1200 in ACC-001, no matching credit
        {
            "Person_Name": "Ramesh Kumar",
            "Bank_Name": "HDFC",
            "Account_Number": "ACC-001",
            "Date": pd.Timestamp("2024-01-11"),
            "Debit": 1200.0,
            "Credit": 0.0,
            "Narration": "Amazon purchase",
            "Counterparty": "Amazon",
            "Category": "Shopping",
            "Sub_Category": "Online Shopping",
            "Confidence": "High",
            "txn_seq": 2,
        },
        # idx 2 — Credit 3000 in ACC-002, amount too different to match idx 0
        {
            "Person_Name": "Ramesh Kumar",
            "Bank_Name": "SBI",
            "Account_Number": "ACC-002",
            "Date": pd.Timestamp("2024-01-10"),
            "Debit": 0.0,
            "Credit": 3000.0,
            "Narration": "Salary credit",
            "Counterparty": "Employer",
            "Category": "Income",
            "Sub_Category": "Salary",
            "Confidence": "High",
            "txn_seq": 3,
        },
        # idx 3 — Credit 5000 in ACC-002 on 2024-01-10  ← should match idx 0
        {
            "Person_Name": "Ramesh Kumar",
            "Bank_Name": "SBI",
            "Account_Number": "ACC-002",
            "Date": pd.Timestamp("2024-01-10"),
            "Debit": 0.0,
            "Credit": 5000.0,
            "Narration": "NEFT received",
            "Counterparty": "",
            "Category": "Miscellaneous",
            "Sub_Category": "Miscellaneous Inflow",
            "Confidence": "Low",
            "txn_seq": 4,
        },
        # idx 4 — Credit 5000 but date is 5 days away — should NOT match idx 0
        {
            "Person_Name": "Ramesh Kumar",
            "Bank_Name": "SBI",
            "Account_Number": "ACC-002",
            "Date": pd.Timestamp("2024-01-15"),
            "Debit": 0.0,
            "Credit": 5000.0,
            "Narration": "Transfer late",
            "Counterparty": "",
            "Category": "Miscellaneous",
            "Sub_Category": "Miscellaneous Inflow",
            "Confidence": "Low",
            "txn_seq": 5,
        },
    ]
    return pd.DataFrame(rows)


def test_matched_pair_gets_ibt_category():
    df = _make_df()
    result = tag_inter_bank_transfers(df)

    # Both legs of the matched pair (idx 0 and idx 3) must be tagged
    assert result.at[0, "Category"] == "Inter-Bank Transfer"
    assert result.at[3, "Category"] == "Inter-Bank Transfer"
    assert result.at[0, "Sub_Category"] == "Inter-Bank Transfer"
    assert result.at[3, "Sub_Category"] == "Inter-Bank Transfer"
    assert result.at[0, "Confidence"] == "High"
    assert result.at[3, "Confidence"] == "High"


def test_matched_pair_shares_transfer_group():
    df = _make_df()
    result = tag_inter_bank_transfers(df)

    grp0 = result.at[0, "Transfer_Group"]
    grp3 = result.at[3, "Transfer_Group"]
    assert grp0 != "", "Debit leg must have a Transfer_Group"
    assert grp3 != "", "Credit leg must have a Transfer_Group"
    assert grp0 == grp3, "Both legs must share the same Transfer_Group"
    assert grp0.startswith("IBT-"), f"Expected IBT- prefix, got {grp0}"


def test_unmatched_rows_are_untouched():
    df = _make_df()
    result = tag_inter_bank_transfers(df)

    # idx 1 — unmatched debit (shopping)
    assert result.at[1, "Category"] == "Shopping"
    assert result.at[1, "Transfer_Group"] == ""

    # idx 2 — unmatched credit (salary)
    assert result.at[2, "Category"] == "Income"
    assert result.at[2, "Transfer_Group"] == ""

    # idx 4 — credit with correct amount but date too far away
    assert result.at[4, "Transfer_Group"] == ""


def test_original_df_not_mutated():
    df = _make_df()
    _ = tag_inter_bank_transfers(df)
    # Original should still have old categories
    assert df.at[0, "Category"] == "Others"
    assert df.at[3, "Category"] == "Miscellaneous"
