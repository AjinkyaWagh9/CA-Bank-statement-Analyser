def extract_transaction_mode(narration: str) -> str:
    """Detects transaction channel (UPI, NEFT, ATM, etc.) from narration text."""
    n = narration.lower()
    if "upi" in n:
        return "UPI"
    elif "neft" in n:
        return "NEFT"
    elif "rtgs" in n:
        return "RTGS"
    elif "imps" in n:
        return "IMPS"
    elif "atm" in n or "cash wd" in n or "cash withdrawal" in n:
        return "ATM"
    elif "cash" in n or "cdm" in n or "deposit cash" in n:
        return "CASH"
    elif "chq" in n or "cheque" in n or "clg" in n:
        return "CHEQUE"
    elif "interest" in n or "int cr" in n:
        return "INTEREST"
    elif "charge" in n or "fee" in n or "charges" in n:
        return "CHARGE"
    else:
        return "TRANSFER"
