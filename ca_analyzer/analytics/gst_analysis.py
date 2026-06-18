import pandas as pd

def generate_gst_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Identifies and classifies GST-related transactions (Payments, Receipts, Refunds).
    For rows with GST, adds computed columns: Taxable, GST_Amount, Gross, GST_Rate.
    """
    if df.empty:
        return pd.DataFrame(columns=["Date", "Bank", "Narration", "Amount", "Type", "Taxable", "GST_Amount", "Gross", "GST_Rate"])

    df = df.copy()
    gst_mask = df["Narration"].str.lower().str.contains("gst", na=False)
    gst_txns = df[gst_mask].copy()

    if gst_txns.empty:
        return pd.DataFrame(columns=["Date", "Bank", "Narration", "Amount", "Type", "Taxable", "GST_Amount", "Gross", "GST_Rate"])

    types = []
    amounts = []
    taxables = []
    gst_amounts = []
    grosses = []
    gst_rates = []

    for _, row in gst_txns.iterrows():
        n = row["Narration"].lower()
        if row["Debit"] > 0.0:
            types.append("GST Payment")
            amount = row["Debit"]
            amounts.append(amount)
        elif "refund" in n or "ref" in n:
            types.append("GST Refund")
            amount = row["Credit"]
            amounts.append(amount)
        else:
            types.append("GST Receipt")
            amount = row["Credit"]
            amounts.append(amount)

        # GST breakup: treat Amount as Gross (inclusive of 18% GST)
        gross = amount
        taxable = round(gross / 1.18, 2)
        gst_amount = round(gross - taxable, 2)
        gst_rate = 0.18

        grosses.append(gross)
        taxables.append(taxable)
        gst_amounts.append(gst_amount)
        gst_rates.append(gst_rate)

    gst_txns["Type"] = types
    gst_txns["Amount"] = amounts
    gst_txns["Gross"] = grosses
    gst_txns["Taxable"] = taxables
    gst_txns["GST_Amount"] = gst_amounts
    gst_txns["GST_Rate"] = gst_rates

    gst_txns["Date"] = gst_txns["Date"].dt.strftime("%Y-%m-%d")
    gst_txns = gst_txns.rename(columns={"Bank_Name": "Bank"})

    return gst_txns[["Date", "Bank", "Narration", "Amount", "Type", "Taxable", "GST_Amount", "Gross", "GST_Rate"]].sort_values(by="Date").reset_index(drop=True)
