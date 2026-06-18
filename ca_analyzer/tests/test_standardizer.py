import pandas as pd
from ca_analyzer.normalization.standardizer import standardize_dataframe
from ca_analyzer.core.schemas import CANONICAL_COLUMNS
from ca_analyzer.core.utilities import make_transaction_id


def _make_raw():
    return pd.DataFrame([
        {
            "raw_date": "01/04/2024",
            "raw_narration": "UPI/ZOMATO",
            "raw_chq_ref": "-",
            "raw_debit": "250.0",
            "raw_credit": "0.0",
            "raw_balance": "10000.0",
            "Person_Name": "TEST USER",
            "Bank_Name": "HDFC",
            "Account_Number": "12345",
            "IFSC": "HDFC0001",
            "Statement_Start": "01/04/2024",
            "Statement_End": "31/03/2025",
        }
    ])


def test_standardize_dataframe():
    raw = _make_raw()
    df = standardize_dataframe(raw)
    assert df.shape[0] == 1
    for col in CANONICAL_COLUMNS:
        assert col in df.columns
    assert df["Debit"].iloc[0] == 250.0
    assert df["Credit"].iloc[0] == 0.0


def test_financial_year_derived():
    raw = _make_raw()
    df = standardize_dataframe(raw)
    # April 2024 falls in FY 2024-25
    assert df["Financial_Year"].iloc[0] == "2024-25"


def test_transaction_id_determinism():
    """Transaction_ID must be identical for two calls with the same inputs."""
    tid1 = make_transaction_id("HDFC", "12345", pd.Timestamp("2024-04-01"),
                               "UPI/ZOMATO", 250.0, 0.0, 10000.0, 0)
    tid2 = make_transaction_id("HDFC", "12345", pd.Timestamp("2024-04-01"),
                               "UPI/ZOMATO", 250.0, 0.0, 10000.0, 0)
    assert tid1 == tid2
    assert len(tid1) == 12

    # Different txn_seq must produce different ID
    tid3 = make_transaction_id("HDFC", "12345", pd.Timestamp("2024-04-01"),
                               "UPI/ZOMATO", 250.0, 0.0, 10000.0, 1)
    assert tid1 != tid3


def test_standardize_includes_transaction_id():
    raw = _make_raw()
    df = standardize_dataframe(raw)
    assert "Transaction_ID" in df.columns
    txid = df["Transaction_ID"].iloc[0]
    assert isinstance(txid, str)
    assert len(txid) == 12
