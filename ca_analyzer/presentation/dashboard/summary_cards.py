from ca_analyzer.analytics.dashboard import generate_dashboard_kpis

def get_summary_cards_data(df) -> list:
    """Prepares formatted summaries for KPI card cells in Lakhs (L)."""
    kpis = generate_dashboard_kpis(df)
    if not kpis:
        return []
        
    def to_lakhs_str(val):
        lakhs = val / 100000.0
        return f"₹ {lakhs:.2f} L"
        
    return [
        {"title": "Total Credits", "value": to_lakhs_str(kpis["Total Credits"]), "raw": kpis["Total Credits"]},
        {"title": "Total Debits", "value": to_lakhs_str(kpis["Total Debits"]), "raw": kpis["Total Debits"]},
        {"title": "Net Cashflow", "value": to_lakhs_str(kpis["Net Cashflow"]), "raw": kpis["Net Cashflow"]},
        {"title": "Highest Balance", "value": to_lakhs_str(kpis["Highest Balance"]), "raw": kpis["Highest Balance"]},
    ]
