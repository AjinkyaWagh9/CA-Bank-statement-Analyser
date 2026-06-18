"""
BRD §10 — Loan Matcher
Identifies bank loans (Case 1), friend/relative loans (Case 2),
and receipts with explicit loan evidence and no repayment (Case 3 → Review).

Conservative design: high precision over recall.
Only stdlib difflib is used for fuzzy name matching.
No external dependencies beyond pandas (already in the project).
"""

from __future__ import annotations

import difflib
import re
from typing import Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Case 1: matched as whole tokens/word-boundaries only
BANK_LOAN_CREDIT_PATTERN = re.compile(
    r'\b(loan|disb|hl|pl|lap|finance|nbfc|housing)\b', re.IGNORECASE
)
BANK_LOAN_DEBIT_KEYWORDS = {"emi", "loan repayment", "mortgage"}

# Counterparties that are definitely NOT individual persons
MERCHANT_SUBSTRINGS = [
    "services", "solutions", "pvt", "ltd", "llp", "inc", "tech",
    "pay", "rzp", "razorpay", "paytm", "phonepe", "gpay", "google",
    "goog", "amazon", "flipkart", "swiggy", "zomato", "enterprise",
    "traders", "store", "mart", "recharge", "bill", "gas", "electric",
    "insurance", "mutual", "bank", ".in", ".com", "@",
]

SKIP_COUNTERPARTIES = {"", "n/a", "na", "others", "self", "upi", "imps", "neft", "rtgs", "ph", "atm"}

# Loan keywords in narration that are explicit evidence of a personal loan
PERSONAL_LOAN_NARRATION_KEYWORDS = {"loan", "udhaar", "haath", "borrow", "lent"}

# Minimum amount (₹) for a one-directional credit to be treated as income-review
PERSONAL_LOAN_MIN_AMOUNT = 25_000.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _narration_matches_bank_loan(narration: str) -> bool:
    """Return True if narration contains a bank-loan keyword as a whole token."""
    return bool(BANK_LOAN_CREDIT_PATTERN.search(narration))


def _narration_matches_debit_kw(narration: str) -> bool:
    n = narration.lower()
    return any(kw in n for kw in BANK_LOAN_DEBIT_KEYWORDS)


def _narration_has_personal_loan_kw(narration: str) -> bool:
    n = narration.lower()
    return any(kw in n for kw in PERSONAL_LOAN_NARRATION_KEYWORDS)


def _looks_like_transaction_id(cp: str) -> bool:
    """Return True if counterparty looks like a transaction/reference ID (not a person name).
    Heuristic: contains digits AND has no spaces AND length >= 6.
    Person names typically have spaces or are purely alphabetic short strings.
    """
    import re as _re
    cp = cp.strip()
    if " " in cp:
        return False  # has spaces → likely a name
    if len(cp) < 6:
        return False
    has_digits = bool(_re.search(r'\d', cp))
    has_alpha = bool(_re.search(r'[A-Za-z]', cp))
    # Mixed alphanumeric with no spaces → likely a ref/ID
    return has_digits and has_alpha


def _is_merchant(cp: str) -> bool:
    """Return True if the counterparty looks like a merchant/service/entity (not a person)."""
    cp_lower = cp.lower()
    if any(sub in cp_lower for sub in MERCHANT_SUBSTRINGS):
        return True
    if _looks_like_transaction_id(cp):
        return True
    return False


def _is_skip(cp: str) -> bool:
    return cp.strip().lower() in SKIP_COUNTERPARTIES


def _is_self_transfer(cp: str, person_name: str) -> bool:
    """Return True if the counterparty fuzzy-matches any token of the account holder's name."""
    if not person_name or not cp:
        return False
    cp_lower = cp.strip().lower()
    # Check against each token of the person name (e.g. "SANJAY", "JINDAL")
    person_tokens = person_name.strip().lower().split()
    # Also check against the full name
    person_variants = person_tokens + [person_name.strip().lower()]
    for variant in person_variants:
        if not variant:
            continue
        ratio = difflib.SequenceMatcher(None, cp_lower, variant).ratio()
        if ratio >= 0.6:
            return True
    return False


def _qualifies_as_person(cp: str, person_name: str) -> bool:
    """
    A counterparty qualifies as an individual person (eligible for personal-loan
    matching) only if ALL of the following hold:
      1. Not blank / "N/A" / "OTHERS" / "Self"
      2. Does NOT look like a merchant / service / entity
      3. Does NOT fuzzy-match the account holder's own name (self-transfer)
    """
    if _is_skip(cp):
        return False
    if _is_merchant(cp):
        return False
    if _is_self_transfer(cp, person_name):
        return False
    return True


def _name_ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()


def _get_person_name(df: pd.DataFrame) -> str:
    """Extract account holder name from DataFrame if available."""
    for col in ("Person_Name", "Account_Holder", "Name"):
        if col in df.columns:
            vals = df[col].dropna().unique()
            if len(vals) > 0:
                return str(vals[0])
    return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def match_loans(df: pd.DataFrame, person_name: str = "") -> pd.DataFrame:
    """
    Add Loan_ID, Loan_Role, Loan_Status columns to a copy of *df*.

    Cases handled
    -------------
    Case 1 — Bank loan: Credit matching bank-loan keywords (as whole tokens) →
             Disbursement; subsequent Debits with EMI/repayment keywords → EMI.
    Case 2 — Personal loan (STRICT): Credit from a qualifying person AND
             at least one debit to the same person → Receipt + Repayment.
             Bidirectional evidence required. Outstanding = max(0, Received−Repaid).
    Case 3 — One-directional credit from a qualifying person WITH explicit loan
             keyword in narration AND amount >= ₹25,000 → "Loan Not Repaid - Review",
             Category="Other Sources", Confidence="Low".
             All other single-direction credits: UNTOUCHED (no loan classification).

    Inter-Bank Transfer rows are NEVER reclassified.
    Returns a copy; index/order are preserved.
    """
    df = df.copy()

    # Infer person_name from DataFrame if not provided
    if not person_name:
        person_name = _get_person_name(df)

    # Ensure new columns exist with default ""
    for col in ("Loan_ID", "Loan_Role", "Loan_Status"):
        if col not in df.columns:
            df[col] = ""

    for col in ("Loan_Flag", "Category", "Sub_Category", "Confidence"):
        if col not in df.columns:
            df[col] = ""

    loan_counter = [0]  # mutable so nested helpers can increment

    def _new_loan_id() -> str:
        loan_counter[0] += 1
        return f"LN-{loan_counter[0]:04d}"

    order = list(df.index)

    # ------------------------------------------------------------------
    # CASE 1 — Bank loans (keyword must be a whole token)
    # ------------------------------------------------------------------
    open_bank_loans: list[dict] = []

    for idx in order:
        row = df.loc[idx]
        # Skip inter-bank transfer rows
        if str(row.get("Category", "")) == "Inter-Bank Transfer":
            continue

        narration = str(row.get("Narration", ""))
        credit = float(row.get("Credit", 0) or 0)
        debit = float(row.get("Debit", 0) or 0)
        counterparty = str(row.get("Counterparty", ""))

        if credit > 0 and _narration_matches_bank_loan(narration):
            # Only treat as bank loan if the counterparty is NOT an individual person.
            # If it's a qualifying person, skip Case 1 and let Case 2/3 handle it.
            if _qualifies_as_person(counterparty, person_name):
                # This is a personal loan receipt, not a bank disbursement — skip Case 1
                pass
            else:
                lid = _new_loan_id()
                df.at[idx, "Loan_ID"] = lid
                df.at[idx, "Loan_Role"] = "Disbursement"
                df.at[idx, "Loan_Status"] = "Outstanding"
                df.at[idx, "Loan_Flag"] = "Y"
                df.at[idx, "Category"] = "Loans"
                df.at[idx, "Sub_Category"] = "Loan Disbursement"
                df.at[idx, "Confidence"] = "High"
                open_bank_loans.append({"loan_id": lid, "counterparty": counterparty})

        elif debit > 0 and _narration_matches_debit_kw(narration):
            if open_bank_loans:
                cp_lower = counterparty.strip().lower()
                matched_loan = None
                if cp_lower:
                    for loan in reversed(open_bank_loans):
                        if loan["counterparty"].strip().lower() == cp_lower:
                            matched_loan = loan
                            break
                if matched_loan is None:
                    matched_loan = open_bank_loans[-1]

                df.at[idx, "Loan_ID"] = matched_loan["loan_id"]
                df.at[idx, "Loan_Role"] = "EMI"
                df.at[idx, "Loan_Flag"] = "Y"

    # ------------------------------------------------------------------
    # CASE 2 & 3 — Personal loans (STRICT: person filter + bidirectional)
    # ------------------------------------------------------------------

    # Collect qualifying personal credits (receipts)
    personal_credits: list[dict] = []
    for idx in order:
        row = df.loc[idx]
        # Skip inter-bank transfers
        if str(row.get("Category", "")) == "Inter-Bank Transfer":
            continue
        # Skip rows already tagged as bank loans
        if df.at[idx, "Loan_Role"] in ("Disbursement", "EMI"):
            continue
        credit = float(row.get("Credit", 0) or 0)
        if credit <= 0:
            continue
        counterparty = str(row.get("Counterparty", ""))
        if not _qualifies_as_person(counterparty, person_name):
            continue
        narration = str(row.get("Narration", ""))
        # Note: we do NOT skip personal credits just because they have a loan keyword —
        # that keyword is evidence for Case 3 (review). Case 1 already excluded person
        # counterparties from bank-loan treatment above.
        personal_credits.append({
            "idx": idx,
            "counterparty": counterparty,
            "amount": credit,
            "date": row.get("Date"),
            "narration": narration,
        })

    # Collect qualifying personal debits (potential repayments)
    personal_debits: list[dict] = []
    for idx in order:
        row = df.loc[idx]
        if str(row.get("Category", "")) == "Inter-Bank Transfer":
            continue
        if df.at[idx, "Loan_Role"] in ("Disbursement", "EMI"):
            continue
        debit = float(row.get("Debit", 0) or 0)
        if debit <= 0:
            continue
        counterparty = str(row.get("Counterparty", ""))
        if not _qualifies_as_person(counterparty, person_name):
            continue
        narration = str(row.get("Narration", ""))
        if _narration_matches_debit_kw(narration):
            continue
        personal_debits.append({
            "idx": idx,
            "counterparty": counterparty,
            "amount": debit,
            "date": row.get("Date"),
            "assigned_loan_id": None,
        })

    # Group credits by normalised counterparty, aggregate debits per person
    # Build a map: normalised_cp → list of credit_info dicts
    from collections import defaultdict
    credits_by_cp: dict[str, list[dict]] = defaultdict(list)
    for c in personal_credits:
        credits_by_cp[c["counterparty"].strip().lower()].append(c)

    # For each unique creditor, find matching debits
    used_debit_indices: set[int] = set()

    for cp_norm, credit_list in credits_by_cp.items():
        # Find all debits from this same person (ratio >= 0.8)
        matching_debits = []
        for deb in personal_debits:
            if deb["idx"] in used_debit_indices:
                continue
            ratio = _name_ratio(cp_norm, deb["counterparty"])
            if ratio < 0.8:
                continue
            matching_debits.append(deb)

        total_received = sum(c["amount"] for c in credit_list)
        total_debited = sum(d["amount"] for d in matching_debits)

        if matching_debits:
            # CASE 2: Bidirectional evidence → establish ONE loan per person
            lid = _new_loan_id()
            received = total_received
            repaid = min(total_debited, received)  # NEVER allow repaid > received
            outstanding = max(0.0, received - repaid)
            status = "Repaid" if outstanding <= 1 else "Outstanding"

            # Tag all receipt rows
            for c in credit_list:
                df.at[c["idx"], "Loan_ID"] = lid
                df.at[c["idx"], "Loan_Role"] = "Receipt"
                df.at[c["idx"], "Loan_Flag"] = "Y"
                df.at[c["idx"], "Loan_Status"] = status
                df.at[c["idx"], "Confidence"] = "Medium"

            # Tag all repayment rows
            for deb in matching_debits:
                used_debit_indices.add(deb["idx"])
                df.at[deb["idx"], "Loan_ID"] = lid
                df.at[deb["idx"], "Loan_Role"] = "Repayment"
                df.at[deb["idx"], "Loan_Flag"] = "Y"
                df.at[deb["idx"], "Loan_Status"] = status
                df.at[deb["idx"], "Confidence"] = "Medium"

        else:
            # No repayments found — CASE 3 ONLY if explicit loan keyword + amount >= ₹25,000
            for c in credit_list:
                has_loan_kw = _narration_has_personal_loan_kw(c["narration"])
                if has_loan_kw and c["amount"] >= PERSONAL_LOAN_MIN_AMOUNT:
                    lid = _new_loan_id()
                    df.at[c["idx"], "Loan_ID"] = lid
                    df.at[c["idx"], "Loan_Role"] = "Receipt"
                    df.at[c["idx"], "Loan_Flag"] = "Y"
                    df.at[c["idx"], "Loan_Status"] = "Treated as Income"
                    df.at[c["idx"], "Category"] = "Other Sources"
                    df.at[c["idx"], "Sub_Category"] = "Loan Not Repaid - Review"
                    df.at[c["idx"], "Confidence"] = "Low"
                # else: leave the row completely untouched

    # ------------------------------------------------------------------
    # Back-fill Bank Loan statuses based on repayment totals
    # ------------------------------------------------------------------
    bank_received: dict[str, float] = {}
    bank_repaid: dict[str, float] = {}

    for idx in order:
        role = df.at[idx, "Loan_Role"]
        lid = df.at[idx, "Loan_ID"]
        if not lid:
            continue
        if role == "Disbursement":
            bank_received[lid] = float(df.at[idx, "Credit"] or 0)
            if lid not in bank_repaid:
                bank_repaid[lid] = 0.0
        elif role == "EMI":
            bank_repaid[lid] = bank_repaid.get(lid, 0.0) + float(df.at[idx, "Debit"] or 0)

    for lid, received in bank_received.items():
        repaid = bank_repaid.get(lid, 0.0)
        outstanding = received - repaid
        status = "Repaid" if outstanding <= 1 else "Outstanding"
        mask = df["Loan_ID"] == lid
        df.loc[mask, "Loan_Status"] = status

    return df


def build_loan_ledger(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a summary table: one row per Loan_ID.
    Columns: Loan_ID, Counterparty, Type, Received, Repaid, Outstanding, Status.
    Returns empty DataFrame with those columns if no loans exist.
    """
    ledger_cols = ["Loan_ID", "Counterparty", "Type", "Received", "Repaid", "Outstanding", "Status"]

    if "Loan_ID" not in df.columns or df["Loan_ID"].eq("").all():
        return pd.DataFrame(columns=ledger_cols)

    loan_df = df[df["Loan_ID"] != ""].copy()
    if loan_df.empty:
        return pd.DataFrame(columns=ledger_cols)

    rows = []
    for lid, group in loan_df.groupby("Loan_ID"):
        has_disbursement = (group["Loan_Role"] == "Disbursement").any()
        loan_type = "Bank" if has_disbursement else "Personal"

        receipt_rows = group[group["Loan_Role"].isin(("Disbursement", "Receipt"))]
        counterparty = receipt_rows["Counterparty"].iloc[0] if not receipt_rows.empty else ""

        if has_disbursement:
            received = float(group.loc[group["Loan_Role"] == "Disbursement", "Credit"].sum())
            repaid = float(group.loc[group["Loan_Role"] == "EMI", "Debit"].sum())
        else:
            received = float(group.loc[group["Loan_Role"] == "Receipt", "Credit"].sum())
            repaid = float(group.loc[group["Loan_Role"] == "Repayment", "Debit"].sum())

        # Guard: outstanding can never be negative
        outstanding = max(0.0, received - repaid)

        status = receipt_rows["Loan_Status"].iloc[0] if not receipt_rows.empty else ""

        rows.append({
            "Loan_ID": lid,
            "Counterparty": counterparty,
            "Type": loan_type,
            "Received": received,
            "Repaid": repaid,
            "Outstanding": outstanding,
            "Status": status,
        })

    return pd.DataFrame(rows, columns=ledger_cols)
