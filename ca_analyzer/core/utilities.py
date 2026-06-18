import re
import pandas as pd
from datetime import datetime, date

def parse_amount(val) -> float:
    if pd.isna(val): return 0.0
    s = str(val).replace(",", "").replace("₹", "").replace(" ", "").replace("(", "-").replace(")", "")
    s = re.sub(r"[^\d.\-]", "", s)
    try: return float(s)
    except: return 0.0

def parse_date(val):
    if pd.isna(val):
        return pd.NaT
    if isinstance(val, (datetime, pd.Timestamp)):
        return pd.to_datetime(val)
    val = str(val).strip()
    if not val:
        return pd.NaT

    formats = [
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%d-%b-%Y",
        "%d-%b-%y",
        "%d/%b/%Y",
        "%d %b %Y",
        "%d-%B-%Y",
        "%d %B %Y",
        "%Y-%m-%d",
        "%d-%m-%y",
        "%d/%m/%y",
    ]

    for fmt in formats:
        try:
            return pd.to_datetime(datetime.strptime(val, fmt))
        except:
            pass

    try:
        return pd.to_datetime(val, dayfirst=True, errors="coerce")
    except:
        return pd.NaT

def get_financial_year(dt):
    if pd.isna(dt):
        return "N/A"
    if dt.month >= 4:
        return f"{dt.year}-{str(dt.year + 1)[-2:]}"
    return f"{dt.year - 1}-{str(dt.year)[-2:]}"

def fy_to_ay(fy):
    if not fy or fy == "N/A":
        return "N/A"
    start = int(fy.split("-")[0])
    return f"{start + 1}-{str(start + 2)[-2:]}"

def fy_bounds(fy):
    if not fy or fy == "N/A":
        return date(2024, 4, 1), date(2025, 3, 31)
    start = int(fy.split("-")[0])
    return date(start, 4, 1), date(start + 1, 3, 31)

def format_inr(v) -> str:
    if pd.isna(v): return "₹ 0"
    v = float(v)
    sign = "-" if v < 0 else ""
    v = abs(v)
    s = f"{v:,.2f}"
    parts = s.split(".")
    integer = parts[0].replace(",", "")
    if len(integer) > 3:
        last3 = integer[-3:]
        rest   = integer[:-3]
        groups = []
        while len(rest) > 2:
            groups.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.append(rest)
        groups.reverse()
        integer = ",".join(groups) + "," + last3
    return f"₹ {sign}{integer}.{parts[1]}"
