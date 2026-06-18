import pandas as pd

def generate_dashboard_kpis(df: pd.DataFrame) -> dict:
    """Computes high level metrics across all consolidated accounts."""
    if df.empty:
        return {}
        
    total_credits = df["Credit"].sum()
    total_debits = df["Debit"].sum()
    net_cashflow = total_credits - total_debits
    
    highest_balance = df["Balance"].max()
    lowest_balance = df["Balance"].min()
    
    # Group by year-month to find actual number of months
    months = df["Date"].dt.to_period("M").nunique()
    months = max(1, months)
    
    avg_monthly_inflow = total_credits / months
    avg_monthly_outflow = total_debits / months
    
    number_of_banks = df["Bank_Name"].nunique()
    
    return {
        "Total Credits": total_credits,
        "Total Debits": total_debits,
        "Net Cashflow": net_cashflow,
        "Highest Balance": highest_balance,
        "Lowest Balance": lowest_balance,
        "Average Monthly Inflow": avg_monthly_inflow,
        "Average Monthly Outflow": avg_monthly_outflow,
        "Number of Banks": number_of_banks,
        "Total Transactions": len(df)
    }
