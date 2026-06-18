import re

def extract_merchant_and_counterparty(narration: str) -> tuple:
    """
    Parses bank narration and returns a tuple: (Merchant_Name, Counterparty)
    """
    n_clean = narration.strip()
    n_lower = n_clean.lower()
    
    merchant = ""
    counterparty = ""
    
    # 1. Handle UPI formats
    if "upi" in n_lower:
        parts = [p.strip() for p in n_clean.split("/")]
        if len(parts) >= 4:
            desc = parts[2]
            handle = parts[3]
            
            if "payment to" in desc.lower():
                counterparty = desc[10:].strip()
            elif "payment from" in desc.lower():
                counterparty = desc[12:].strip()
            else:
                counterparty = desc
                
            merchant = handle.split("@")[0]
        else:
            parts_hyphen = [p.strip() for p in n_clean.split("-")]
            if len(parts_hyphen) >= 3:
                merchant = parts_hyphen[1]
                counterparty = parts_hyphen[2].split("@")[0]
            else:
                match = re.search(r"upi[-/]([^-/]+)[-/]([^-/]+)", n_clean, re.IGNORECASE)
                if match:
                    merchant = match.group(1)
                    counterparty = match.group(2)
                    
    # 2. Handle NEFT / RTGS formats
    elif "neft" in n_lower or "rtgs" in n_lower:
        parts = [p.strip() for p in n_clean.split("/")]
        if len(parts) >= 4:
            counterparty = parts[3]
            merchant = parts[1]
        else:
            match = re.search(r"neft.*--\s*([A-Za-z0-9\s\.\&]+)", n_clean, re.IGNORECASE)
            if match:
                counterparty = match.group(1).strip()
                merchant = "NEFT"
                
    # 3. Handle IMPS formats
    elif "imps" in n_lower:
        merchant = "IMPS"
        match = re.search(r"imps\d*/([^/]+)/", n_lower)
        if match:
            counterparty = match.group(1).upper()
            
    # 4. Handle ATM / Cash formats
    elif "atm" in n_lower or "cdm" in n_lower or "cash" in n_lower:
        merchant = "ATM/CASH"
        counterparty = "Self"
        
    # Default Fallbacks
    if not merchant:
        words = n_clean.split()
        merchant = words[0] if words else "OTHERS"
    if not counterparty:
        counterparty = "N/A"
        
    # Clean merchant and counterparty texts
    merchant = merchant.replace("payment to", "").replace("payment from", "").strip().upper()
    counterparty = counterparty.replace("payment to", "").replace("payment from", "").strip().upper()
    
    # If values are purely digits or too short, default them
    if re.match(r"^\d+$", counterparty) or len(counterparty) < 2:
        counterparty = "N/A"
    if re.match(r"^\d+$", merchant) or len(merchant) < 2:
        merchant = "OTHERS"
        
    return merchant, counterparty
