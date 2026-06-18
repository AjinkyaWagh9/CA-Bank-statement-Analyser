import pandas as pd
from ca_analyzer.normalization.standardizer import standardize_dataframe
from ca_analyzer.core.schemas import CANONICAL_COLUMNS

def test_standardize_dataframe():
    raw = pd.DataFrame([
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
            "Statement_End": "31/03/2025"
        }
    ])
    
    df = standardize_dataframe(raw)
    assert df.shape[0] == 1
    for col in CANONICAL_COLUMNS:
        assert col in df.columns
    assert df["Debit"].iloc[0] == 250.0
    assert df["Credit"].iloc[0] == 0.0
