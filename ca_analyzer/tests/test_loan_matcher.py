"""
Tests for BRD §10 loan_matcher — Cases 1, 2, 3.
Conservative rewrite: high-precision personal-loan logic.
"""
import pandas as pd
import pytest

from ca_analyzer.transaction_engine.loan_matcher import match_loans, build_loan_ledger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_row(**kwargs):
    defaults = {
        "Date": "2024-01-01",
        "Narration": "",
        "Debit": 0.0,
        "Credit": 0.0,
        "Balance": 0.0,
        "Counterparty": "",
        "Category": "",
        "Sub_Category": "",
        "Confidence": "",
        "Loan_Flag": "",
    }
    defaults.update(kwargs)
    return defaults


# ---------------------------------------------------------------------------
# Case (a): Bank loan disbursement + one EMI
# ---------------------------------------------------------------------------

def test_case_a_bank_loan_disbursement_and_emi():
    rows = [
        _base_row(Date="2024-01-05", Narration="LOAN DISB FROM HDFC BANK", Credit=500000.0,
                  Counterparty="HDFC BANK"),
        _base_row(Date="2024-02-05", Narration="EMI PAYMENT HDFC", Debit=15000.0,
                  Counterparty="HDFC BANK"),
    ]
    df = pd.DataFrame(rows)
    result = match_loans(df)

    assert "Loan_ID" in result.columns
    assert "Loan_Role" in result.columns
    assert "Loan_Status" in result.columns

    disb_row = result.iloc[0]
    emi_row = result.iloc[1]

    assert disb_row["Loan_Role"] == "Disbursement"
    assert disb_row["Loan_ID"].startswith("LN-")
    assert disb_row["Category"] == "Loans"
    assert disb_row["Sub_Category"] == "Loan Disbursement"
    assert disb_row["Loan_Flag"] == "Y"
    assert disb_row["Confidence"] == "High"

    assert emi_row["Loan_Role"] == "EMI"
    assert emi_row["Loan_ID"] == disb_row["Loan_ID"]
    assert emi_row["Loan_Flag"] == "Y"

    assert disb_row["Loan_Status"] == "Outstanding"

    ledger = build_loan_ledger(result)
    assert list(ledger.columns) == ["Loan_ID", "Counterparty", "Type", "Received", "Repaid", "Outstanding", "Status"]
    assert len(ledger) == 1
    row = ledger.iloc[0]
    assert row["Type"] == "Bank"
    assert row["Received"] == 500000.0
    assert row["Repaid"] == 15000.0
    assert row["Outstanding"] == 485000.0
    assert row["Status"] == "Outstanding"


# ---------------------------------------------------------------------------
# Case (b): Friend loan — bidirectional, partial repayments → Outstanding
# ---------------------------------------------------------------------------

def test_case_b_friend_loan_partial_repayment():
    rows = [
        _base_row(Date="2024-01-10", Narration="NEFT FROM RAHUL SHARMA", Credit=100000.0,
                  Counterparty="Rahul Sharma"),
        _base_row(Date="2024-02-01", Narration="NEFT TO RAHUL SHARMA", Debit=20000.0,
                  Counterparty="Rahul Sharma"),
        _base_row(Date="2024-03-01", Narration="IMPS TO RAHUL SHARMA", Debit=30000.0,
                  Counterparty="Rahul Sharma"),
    ]
    df = pd.DataFrame(rows)
    result = match_loans(df)

    receipt_row = result.iloc[0]
    rep1 = result.iloc[1]
    rep2 = result.iloc[2]

    assert receipt_row["Loan_Role"] == "Receipt"
    assert receipt_row["Loan_ID"].startswith("LN-")
    assert receipt_row["Loan_Flag"] == "Y"
    assert receipt_row["Confidence"] == "Medium"

    assert rep1["Loan_Role"] == "Repayment"
    assert rep2["Loan_Role"] == "Repayment"
    assert rep1["Loan_ID"] == receipt_row["Loan_ID"]
    assert rep2["Loan_ID"] == receipt_row["Loan_ID"]

    # Status: 100000 received, 50000 repaid → Outstanding
    assert receipt_row["Loan_Status"] == "Outstanding"

    ledger = build_loan_ledger(result)
    assert len(ledger) == 1
    row = ledger.iloc[0]
    assert row["Type"] == "Personal"
    assert row["Received"] == 100000.0
    assert row["Repaid"] == 50000.0
    assert row["Outstanding"] == 50000.0
    assert row["Status"] == "Outstanding"
    # Outstanding must never be negative
    assert row["Outstanding"] >= 0


# ---------------------------------------------------------------------------
# Case (b2): Friend loan — fully repaid → Status=Repaid
# ---------------------------------------------------------------------------

def test_case_b2_friend_loan_fully_repaid():
    rows = [
        _base_row(Date="2024-01-10", Narration="NEFT FROM AMIT KUMAR", Credit=50000.0,
                  Counterparty="Amit Kumar"),
        _base_row(Date="2024-02-01", Narration="NEFT TO AMIT KUMAR", Debit=50000.0,
                  Counterparty="Amit Kumar"),
    ]
    df = pd.DataFrame(rows)
    result = match_loans(df)

    receipt_row = result.iloc[0]
    rep_row = result.iloc[1]

    assert receipt_row["Loan_Role"] == "Receipt"
    assert rep_row["Loan_Role"] == "Repayment"
    assert receipt_row["Loan_Status"] == "Repaid"

    ledger = build_loan_ledger(result)
    assert len(ledger) == 1
    row = ledger.iloc[0]
    assert row["Outstanding"] == 0.0
    assert row["Status"] == "Repaid"
    assert row["Outstanding"] >= 0


# ---------------------------------------------------------------------------
# Case (c-NEW): One-directional credit WITHOUT loan keyword → untouched
# ---------------------------------------------------------------------------

def test_case_c_one_directional_credit_no_loan_keyword_untouched():
    """
    A credit from a person with NO repayment and NO loan keyword in narration
    must NOT be classified as a loan. Row remains untouched.
    """
    rows = [
        _base_row(Date="2024-01-15", Narration="NEFT FROM PRIYA MEHTA", Credit=75000.0,
                  Counterparty="Priya Mehta", Category="Other Sources"),
    ]
    df = pd.DataFrame(rows)
    result = match_loans(df)

    row = result.iloc[0]
    # Must NOT be tagged as a loan
    assert row["Loan_Role"] == ""
    assert row["Loan_ID"] == ""
    assert row["Loan_Flag"] == ""
    # Category must remain untouched
    assert row["Category"] == "Other Sources"


# ---------------------------------------------------------------------------
# Case (c-REVIEW): One-directional credit WITH explicit loan keyword + >= ₹25k
# ---------------------------------------------------------------------------

def test_case_c_loan_keyword_large_amount_flagged_for_review():
    """
    A credit from a person with NO repayment but WITH explicit loan keyword
    (e.g. 'LOAN') and amount >= 25000 → flagged as Loan Not Repaid - Review.
    """
    rows = [
        _base_row(Date="2024-01-15", Narration="LOAN FROM PRIYA MEHTA", Credit=75000.0,
                  Counterparty="Priya Mehta"),
    ]
    df = pd.DataFrame(rows)
    result = match_loans(df)

    row = result.iloc[0]
    assert row["Loan_Role"] == "Receipt"
    assert row["Loan_Status"] == "Treated as Income"
    assert row["Category"] == "Other Sources"
    assert row["Sub_Category"] == "Loan Not Repaid - Review"
    assert row["Confidence"] == "Low"
    assert row["Loan_Flag"] == "Y"


# ---------------------------------------------------------------------------
# Case (c-small): Explicit loan keyword but amount < ₹25k → untouched
# ---------------------------------------------------------------------------

def test_case_c_loan_keyword_small_amount_untouched():
    """
    Even with loan keyword, amounts below ₹25,000 are NOT flagged.
    """
    rows = [
        _base_row(Date="2024-01-15", Narration="UDHAAR FROM RAVI", Credit=3.0,
                  Counterparty="RAVI"),
    ]
    df = pd.DataFrame(rows)
    result = match_loans(df)

    row = result.iloc[0]
    assert row["Loan_Role"] == ""
    assert row["Loan_ID"] == ""


# ---------------------------------------------------------------------------
# Negative test: Merchant counterparty is NEVER treated as personal loan
# ---------------------------------------------------------------------------

def test_merchant_not_treated_as_loan():
    """
    ONTYMSERVICES contains 'SERVICES' → must NOT be flagged as a personal loan
    even if there are both credits and debits.
    """
    rows = [
        _base_row(Date="2024-01-01", Narration="CREDIT FROM ONTYMSERVICES", Credit=5000.0,
                  Counterparty="ONTYMSERVICES"),
        _base_row(Date="2024-02-01", Narration="DEBIT TO ONTYMSERVICES", Debit=5000.0,
                  Counterparty="ONTYMSERVICES"),
    ]
    df = pd.DataFrame(rows)
    result = match_loans(df)

    assert (result["Loan_Role"] == "").all()
    assert (result["Loan_ID"] == "").all()
    assert (result["Loan_Flag"] == "").all()


# ---------------------------------------------------------------------------
# Negative test: Self UPI handle is never a loan (self-transfer)
# ---------------------------------------------------------------------------

def test_self_handle_not_treated_as_loan():
    """
    If the counterparty is the account holder's own UPI handle (e.g. 'SANJAYJINDAL.IN'),
    it must NOT be treated as a personal loan. '.IN' in name + self-transfer guard.
    """
    rows = [
        _base_row(Date="2024-01-01", Narration="UPI CREDIT SANJAYJINDAL", Credit=10000.0,
                  Counterparty="SANJAYJINDAL.IN"),
        _base_row(Date="2024-02-01", Narration="UPI DEBIT SANJAYJINDAL", Debit=5000.0,
                  Counterparty="SANJAYJINDAL.IN"),
    ]
    df = pd.DataFrame(rows)
    result = match_loans(df, person_name="SANJAY JINDAL")

    assert (result["Loan_Role"] == "").all()
    assert (result["Loan_ID"] == "").all()


# ---------------------------------------------------------------------------
# Negative test: ₹3 from "GOOG" (Google) → NOT a loan/income
# ---------------------------------------------------------------------------

def test_goog_small_credit_not_a_loan():
    """
    ₹3 from 'GOOG' must not be treated as a personal loan.
    'GOOG' contains 'GOOG' which is in the merchant exclusion list.
    """
    rows = [
        _base_row(Date="2024-01-01", Narration="GOOGLE PLAY REFUND", Credit=3.0,
                  Counterparty="GOOG"),
    ]
    df = pd.DataFrame(rows)
    result = match_loans(df)

    row = result.iloc[0]
    assert row["Loan_Role"] == ""
    assert row["Loan_ID"] == ""
    assert row["Category"] == ""  # untouched


# ---------------------------------------------------------------------------
# Negative test: Outstanding must never be negative
# ---------------------------------------------------------------------------

def test_no_negative_outstanding_in_ledger():
    """
    Even if debits exceed the credit, outstanding must be 0, not negative.
    """
    rows = [
        _base_row(Date="2024-01-10", Narration="NEFT FROM DEEPAK", Credit=10000.0,
                  Counterparty="Deepak"),
        _base_row(Date="2024-02-01", Narration="NEFT TO DEEPAK", Debit=15000.0,
                  Counterparty="Deepak"),
    ]
    df = pd.DataFrame(rows)
    result = match_loans(df)
    ledger = build_loan_ledger(result)

    assert len(ledger) == 1
    assert ledger.iloc[0]["Outstanding"] >= 0


# ---------------------------------------------------------------------------
# Negative test: Inter-Bank Transfer rows are never reclassified as loans
# ---------------------------------------------------------------------------

def test_inter_bank_transfer_not_reclassified():
    """
    Rows already tagged Category='Inter-Bank Transfer' must be skipped entirely.
    """
    rows = [
        _base_row(Date="2024-01-01", Narration="TRANSFER TO OWN ACCOUNT", Credit=100000.0,
                  Counterparty="Rahul Sharma", Category="Inter-Bank Transfer"),
        _base_row(Date="2024-02-01", Narration="TRANSFER BACK", Debit=100000.0,
                  Counterparty="Rahul Sharma", Category="Inter-Bank Transfer"),
    ]
    df = pd.DataFrame(rows)
    result = match_loans(df)

    assert (result["Loan_Role"] == "").all()
    assert (result["Loan_ID"] == "").all()
    # Category must remain Inter-Bank Transfer
    assert (result["Category"] == "Inter-Bank Transfer").all()


# ---------------------------------------------------------------------------
# Empty DataFrame → no crash, ledger empty with correct columns
# ---------------------------------------------------------------------------

def test_empty_df():
    df = pd.DataFrame(columns=["Date", "Narration", "Debit", "Credit", "Balance",
                                "Counterparty", "Category", "Sub_Category",
                                "Confidence", "Loan_Flag"])
    result = match_loans(df)
    ledger = build_loan_ledger(result)
    assert list(ledger.columns) == ["Loan_ID", "Counterparty", "Type", "Received", "Repaid", "Outstanding", "Status"]
    assert len(ledger) == 0


# ---------------------------------------------------------------------------
# Skip invalid counterparties (Case 2 should not trigger)
# ---------------------------------------------------------------------------

def test_skip_invalid_counterparty():
    rows = [
        _base_row(Date="2024-01-01", Narration="CREDIT RECEIVED", Credit=50000.0,
                  Counterparty="N/A"),
        _base_row(Date="2024-02-01", Narration="DEBIT SENT", Debit=50000.0,
                  Counterparty="OTHERS"),
    ]
    df = pd.DataFrame(rows)
    result = match_loans(df)
    # No personal loan rows should be tagged
    assert (result["Loan_Role"] == "").all()


# ---------------------------------------------------------------------------
# Bank loan: "PL" must match as whole token, not substring inside a word
# ---------------------------------------------------------------------------

def test_bank_loan_pl_whole_token_only():
    """
    'REPLAY' contains 'PL' as a substring but should NOT trigger a bank loan.
    'PL FROM HDFC BANK' with word boundary and bank counterparty SHOULD trigger.
    """
    rows = [
        _base_row(Date="2024-01-01", Narration="REPLAY CREDIT", Credit=50000.0,
                  Counterparty="HDFC BANK"),
        _base_row(Date="2024-01-02", Narration="PL FROM HDFC BANK", Credit=200000.0,
                  Counterparty="HDFC BANK"),
    ]
    df = pd.DataFrame(rows)
    result = match_loans(df)

    # REPLAY row must NOT be a bank loan (no whole-token match)
    assert result.iloc[0]["Loan_Role"] == ""
    # PL FROM HDFC BANK row SHOULD be a bank loan disbursement
    assert result.iloc[1]["Loan_Role"] == "Disbursement"
