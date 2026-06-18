import pandas as pd
from ca_analyzer.presentation.dashboard.kpis import get_monthly_trends, get_bank_contributions
from ca_analyzer.analytics.expense_analysis import generate_expense_analysis

def write_dashboard_charts_data(ws, df: pd.DataFrame) -> dict:
    """
    Writes helper data tables to column Z and onwards of the dashboard sheet,
    returning chart reference specifications.
    """
    trends = get_monthly_trends(df)
    
    # 1. Monthly Credits vs Debits
    ws["Z1"] = "Month"
    ws["AA1"] = "Credits"
    ws["AB1"] = "Debits"
    for idx, row in trends.reset_index(drop=True).iterrows():
        r = idx + 2
        ws[f"Z{r}"] = row["Month"]
        ws[f"AA{r}"] = row["Credits"]
        ws[f"AB{r}"] = row["Debits"]
    
    # 2. Monthly Closing Balance
    ws["AD1"] = "Month"
    ws["AE1"] = "Closing Balance"
    for idx, row in trends.reset_index(drop=True).iterrows():
        r = idx + 2
        ws[f"AD{r}"] = row["Month"]
        ws[f"AE{r}"] = row["Closing Balance"]
        
    # 3. Expense Categories
    exp_summary = generate_expense_analysis(df)
    ws["AG1"] = "Expense Category"
    ws["AH1"] = "Amount"
    exp_grouped = exp_summary.groupby("Expense Category")["Amount"].sum().reset_index().sort_values(by="Amount", ascending=False)
    for idx, row in exp_grouped.reset_index(drop=True).iterrows():
        r = idx + 2
        ws[f"AG{r}"] = row["Expense Category"]
        ws[f"AH{r}"] = row["Amount"]
        
    # 4. Bank Contributions
    bank_contrib = get_bank_contributions(df)
    ws["AJ1"] = "Bank"
    ws["AK1"] = "Credit Amount"
    for idx, row in bank_contrib.reset_index(drop=True).iterrows():
        r = idx + 2
        ws[f"AJ{r}"] = row["Bank"]
        ws[f"AK{r}"] = row["Credit Amount"]
        
    # 5. Monthly Cashflow Stacked Table (Credits by bank per month)
    df_copy = df.copy()
    df_copy["Month"] = df_copy["Date"].dt.strftime("%Y-%m")
    credits = df_copy[df_copy["Credit"] > 0.0]
    
    if not credits.empty:
        pivot = credits.pivot_table(
            index="Month",
            columns="Bank_Name",
            values="Credit",
            aggfunc="sum",
            fill_value=0.0
        ).reset_index()
        bank_cols = [c for c in pivot.columns if c != "Month"]
        pivot["Total"] = pivot[bank_cols].sum(axis=1)
    else:
        pivot = pd.DataFrame(columns=["Month", "Total"])
        bank_cols = []
        
    start_col = 39  # Column AM
    for c_idx, col_name in enumerate(pivot.columns):
        col_idx = start_col + c_idx
        ws.cell(row=1, column=col_idx, value=col_name)
        
    for r_idx, row in pivot.iterrows():
        r = r_idx + 2
        for c_idx, col_name in enumerate(pivot.columns):
            col_idx = start_col + c_idx
            ws.cell(row=r, column=col_idx, value=row[col_name])
            
    return {
        "trends": {
            "data_min_col": 27,  # AA
            "data_max_col": 28,  # AB
            "data_max_row": len(trends) + 1,
            "cats_col": 26,      # Z
            "cats_row_end": len(trends) + 1
        },
        "balance": {
            "data_min_col": 31,  # AE
            "data_max_col": 31,
            "data_max_row": len(trends) + 1,
            "cats_col": 30,      # AD
            "cats_row_end": len(trends) + 1
        },
        "expense": {
            "data_min_col": 34,  # AH
            "data_max_col": 34,
            "data_max_row": len(exp_grouped) + 1,
            "cats_col": 33,      # AG
            "cats_row_end": len(exp_grouped) + 1
        },
        "bank": {
            "data_min_col": 37,  # AK
            "data_max_col": 37,
            "data_max_row": len(bank_contrib) + 1,
            "cats_col": 36,      # AJ
            "cats_row_end": len(bank_contrib) + 1
        },
        "cashflow": {
            "data_min_col": 40,  # AN (First Bank)
            "data_max_col": 39 + len(bank_cols) if bank_cols else 40,  # Excludes Total
            "data_max_row": len(pivot) + 1,
            "cats_col": 39,      # AM (Month)
            "cats_row_end": len(pivot) + 1
        }
    }
