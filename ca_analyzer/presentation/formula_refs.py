"""
formula_refs.py — Phase 1.1
Defines workbook-level DefinedNames that point to whole-column ranges
on the '📋 All Transactions' master sheet.

Named ranges (prefix m_ = master):
  m_Bank          -> Bank_Name column
  m_Date          -> Date column
  m_Debit         -> Debit column
  m_Credit        -> Credit column
  m_CatFinal      -> Category_Final column
  m_SubCatFinal   -> Sub_Category_Final column
  m_GSTFlag       -> GST_Flag column
  m_LoanFlag      -> Loan_Flag column
  m_TaxFlag       -> Tax_Flag column
  m_CGFlag        -> CG_Flag column
  m_Confidence    -> Confidence column

The sheet name contains an emoji and spaces, so it must be single-quoted
in the attr_text, e.g.: '📋 All Transactions'!$D:$D
"""

from openpyxl.workbook.defined_name import DefinedName
from openpyxl.utils import get_column_letter

MASTER_SHEET_NAME = "📋 All Transactions"

# Mapping: DefinedName -> column header in the master sheet
_RANGE_MAP = {
    "m_Bank":        "Bank_Name",
    "m_Date":        "Date",
    "m_Debit":       "Debit",
    "m_Credit":      "Credit",
    "m_CatFinal":    "Category_Final",
    "m_SubCatFinal": "Sub_Category_Final",
    "m_GSTFlag":     "GST_Flag",
    "m_LoanFlag":    "Loan_Flag",
    "m_TaxFlag":     "Tax_Flag",
    "m_CGFlag":      "CG_Flag",
    "m_Confidence":  "Confidence",
}


def define_named_ranges(wb, col_name_to_idx: dict) -> dict:
    """
    Register workbook-level DefinedNames for the 4 summary-formula sheets.

    Parameters
    ----------
    wb : openpyxl.Workbook
        The workbook to register names into.
    col_name_to_idx : dict
        Maps column header string -> 1-based column index
        (as returned by create_consolidated_master_sheet).

    Returns
    -------
    dict
        The same col_name_to_idx passed in, for convenience.
    """
    # Escape the sheet name: single-quote it because it contains spaces + emoji
    quoted_sheet = f"'{MASTER_SHEET_NAME}'"

    for range_name, col_header in _RANGE_MAP.items():
        col_idx = col_name_to_idx.get(col_header)
        if col_idx is None:
            # Column not present in the actual master sheet — skip gracefully
            continue

        col_letter = get_column_letter(col_idx)
        attr_text = f"{quoted_sheet}!${col_letter}:${col_letter}"

        dn = DefinedName(name=range_name, attr_text=attr_text)
        # openpyxl 3.1.x — DefinedNameDict supports direct item assignment
        try:
            wb.defined_names[range_name] = dn
        except Exception:
            # Fallback for older API variants
            wb.defined_names.add(dn)

    return col_name_to_idx
