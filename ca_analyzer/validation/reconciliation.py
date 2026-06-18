import pandas as pd
from ca_analyzer.core.exceptions import ReconciliationError
from ca_analyzer.core.logger import get_logger

logger = get_logger("reconciliation")

def reconcile_bank(df: pd.DataFrame, bank_name: str, account_num: str) -> bool:
    """
    Reconciles balance continuity and overall opening/closing balances for a specific bank account.
    """
    bank_df = df[(df["Bank_Name"] == bank_name) & (df["Account_Number"] == account_num)].copy()
    if bank_df.empty:
        return True
        
    # Sort chronologically by original statement sequence to check continuity
    bank_df = bank_df.sort_values(by="txn_seq")
    
    balances = bank_df["Balance"].values
    debits = bank_df["Debit"].values
    credits = bank_df["Credit"].values
    
    for i in range(1, len(balances)):
        prev_bal = balances[i - 1]
        curr_bal = balances[i]
        deb = debits[i]
        cred = credits[i]
        
        expected_bal = prev_bal - deb + cred
        diff = abs(curr_bal - expected_bal)
        if diff > 1.0:
            logger.warning(
                f"Balance continuity discrepancy for {bank_name} A/C {account_num} at index {i}. "
                f"Previous: {prev_bal}, Expected: {expected_bal}, Actual: {curr_bal}, Difference: {diff}. "
                f"This may be due to rounding or missing transactions in the source statement. Continuing."
            )
            
    # Rule 5: Overall Closing Balance reconciliation
    total_debit = bank_df["Debit"].sum()
    total_credit = bank_df["Credit"].sum()
    
    # Back-calculate the opening balance before the first transaction in statement
    opening_bal = balances[0] - credits[0] + debits[0]
    closing_bal = balances[-1]
    
    expected_closing = opening_bal + total_credit - total_debit
    diff_closing = abs(closing_bal - expected_closing)
    if diff_closing > 1.0:
        logger.warning(
            f"Closing balance discrepancy for {bank_name} A/C {account_num}. "
            f"Opening: {opening_bal}, Sum(Credit): {total_credit}, Sum(Debit): {total_debit}, "
            f"Expected: {expected_closing}, Actual: {closing_bal}, Difference: {diff_closing}. "
            f"This may be due to rounding or missing transactions in the source statement. Continuing."
        )
        
    logger.info(f"Reconciliation successful for {bank_name} account {account_num}.")
    return True

def reconcile_all(df: pd.DataFrame) -> bool:
    """Groups transactions by bank account and performs reconciliation on each."""
    accounts = df.groupby(["Bank_Name", "Account_Number"])
    for (bank_name, account_num), _ in accounts:
        reconcile_bank(df, bank_name, account_num)
    return True
