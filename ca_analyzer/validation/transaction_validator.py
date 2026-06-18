import pandas as pd
from ca_analyzer.core.exceptions import SchemaError, ReconciliationError
from ca_analyzer.core.logger import get_logger

logger = get_logger("transaction_validator")

def validate_transactions(df: pd.DataFrame) -> bool:
    """Performs integrity checks on individual transaction rows."""
    # Rule 2: No null dates
    if df["Date"].isna().any():
        null_count = df["Date"].isna().sum()
        raise SchemaError(f"Null dates detected in {null_count} transaction row(s).")
        
    # Rule 4: Debit and Credit cannot both be populated
    both_populated = (df["Debit"] > 0.0) & (df["Credit"] > 0.0)
    if both_populated.any():
        violators = df[both_populated]
        logger.error(f"Debit and Credit both populated in rows:\n{violators}")
        raise ReconciliationError("A transaction cannot have both non-zero Debit and Credit values.")
        
    # Rule 1: Warning or log duplicate transactions
    duplicates = df.duplicated(subset=["Date", "Narration", "Debit", "Credit", "Balance"], keep=False)
    if duplicates.any():
        dup_count = df[duplicates].shape[0]
        logger.warning(f"{dup_count} potential duplicate transaction row(s) detected.")
        
    return True
