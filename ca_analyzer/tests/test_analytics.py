import pandas as pd
from ca_analyzer.analytics.dashboard import generate_dashboard_kpis
from ca_analyzer.analytics.high_value_transactions import generate_high_value_transactions

def test_kpi_generation():
    df = pd.DataFrame([
        {"Date": pd.Timestamp("2024-04-10"), "Credit": 100000.0, "Debit": 0.0, "Balance": 100000.0, "Bank_Name": "HDFC"},
        {"Date": pd.Timestamp("2024-04-15"), "Credit": 0.0, "Debit": 40000.0, "Balance": 60000.0, "Bank_Name": "HDFC"},
    ])
    kpis = generate_dashboard_kpis(df)
    assert kpis["Total Credits"] == 100000.0
    assert kpis["Total Debits"] == 40000.0
    assert kpis["Net Cashflow"] == 60000.0
    assert kpis["Highest Balance"] == 100000.0
    assert kpis["Lowest Balance"] == 60000.0

def test_high_value_filter():
    df = pd.DataFrame([
        {"Date": pd.Timestamp("2024-04-10"), "Credit": 1000.0, "Debit": 0.0, "Balance": 1000.0, "Bank_Name": "HDFC", "Narration": "CUP"},
        {"Date": pd.Timestamp("2024-04-15"), "Credit": 0.0, "Debit": 60000.0, "Balance": 0.0, "Bank_Name": "HDFC", "Narration": "PL EMI"},
    ])
    hvt = generate_high_value_transactions(df)
    assert hvt.shape[0] == 1
    assert hvt["Amount"].iloc[0] == 60000.0
