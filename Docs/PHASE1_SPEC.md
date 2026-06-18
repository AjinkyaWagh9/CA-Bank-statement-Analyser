# Phase 1 — Dynamic Formula Workbook: Architecture Contract

Goal (BRD §18): summary sheets must recompute **inside Excel** when a CA edits
`Category_Final` / `Sub_Category_Final` / the flag columns on the master sheet.
No Python-computed static numbers in the convertible summaries.

## Single source of truth
Sheet **`📋 All Transactions`** (built by `create_consolidated_master_sheet`):
- Row 1 = title, row 2 = spacer, **row 3 = headers, data rows start at row 4**.
- Column order is defined by `display_cols` in that function. Current positions:
  | Col | Header | | Col | Header |
  |--|--|--|--|--|
  | A | Transaction_ID | | O | Merchant_Name |
  | B | Date | | P | Counterparty |
  | C | Financial_Year | | Q | Confidence |
  | D | Bank_Name | | R | Match_Reason |
  | E | Account_Number | | S | Category |
  | F | Statement_File_Name | | T | Sub_Category |
  | G | Sheet_Name | | U | **Category_Final** (editable) |
  | H | Statement_Row_No | | V | **Sub_Category_Final** (editable) |
  | I | Narration | | W | **GST_Flag** |
  | J | Chq_Ref | | X | **Loan_Flag** |
  | K | **Debit** | | Y | **Tax_Flag** |
  | L | **Credit** | | Z | **CG_Flag** |
  | M | Balance | | AA | Remarks |
  | N | Transaction_Mode | | | |

  **Do NOT hardcode these letters.** Compute them at build time from the header
  row (`col_name_to_idx`) so the contract survives column reordering.

## Named-range infrastructure (BRD §18 "Dynamic Named Ranges")
Define **workbook-level** `DefinedName`s pointing at whole columns of the master
sheet (whole-column refs are the simplest dynamic range — they auto-include rows a
CA inserts, and text in rows 1-3 never matches numeric/criteria so SUMIFS is safe):

```
m_Bank        -> '📋 All Transactions'!$D:$D
m_Date        -> '📋 All Transactions'!$B:$B
m_Debit       -> '📋 All Transactions'!$K:$K
m_Credit      -> '📋 All Transactions'!$L:$L
m_CatFinal    -> '📋 All Transactions'!$U:$U
m_SubCatFinal -> '📋 All Transactions'!$V:$V
m_GSTFlag     -> '📋 All Transactions'!$W:$W
m_LoanFlag    -> '📋 All Transactions'!$X:$X
m_TaxFlag     -> '📋 All Transactions'!$Y:$Y
m_CGFlag      -> '📋 All Transactions'!$Z:$Z
m_Confidence  -> '📋 All Transactions'!$Q:$Q
```
Build the column-letter -> named-range map programmatically. Quote the sheet name
(it contains an emoji + spaces). openpyxl: `wb.defined_names[name] = DefinedName(name, attr_text="...")` (use the version-correct API).

## Formula patterns (aggregate by `Category_Final`, not the old remapped labels)
The convertible summaries list a **fixed taxonomy of category labels down column A**
(static text) and put a SUMIFS/COUNTIFS in the value columns:
- Total amount for a category: `=SUMIFS(m_Credit, m_CatFinal, $A4)` (income) /
  `=SUMIFS(m_Debit, m_CatFinal, $A4)` (expense).
- Per-bank matrix (category rows × bank columns): add `m_Bank, B$3` as a second
  criteria pair.
- Frequency: `=COUNTIFS(m_CatFinal, $A4)` (optionally with `">0"` on the amount col).
- Monthly cashflow: a Month × Bank matrix using `SUMIFS(m_Credit, m_Bank, col,
  m_Date, ">="&monthStart, m_Date, "<="&monthEnd)` — or a helper Month text column.
- Totals rows: plain `SUM(...)` over the formula cells above.

The category label list comes from a canonical taxonomy (align with BRD §7-8 /
existing `category_rules.yaml`), NOT from scanning the data — labels are static,
numbers are live.

## Phase 1 deliverables
**1.1 (this sub-task):** named-range infra + convert **Bank Wise Summary, Income
Analysis, Expense Analysis, Monthly Cashflow** to formulas. Verify recompute.

**1.2 (next):** new formula-driven sheets — Tax Payments, 80C Tracker, Capital
Gain, Potential Capital Gains, Drawings, Loan Ledger, EMI Analysis, Inter-Bank
Transfer, Related Party, Unclassified, CA Observations (§15-17). Surface
reconciliation discrepancies in CA Observations.

**1.3:** verification — edit a `Category_Final` cell in LibreOffice/Excel headless,
recalc, confirm dependent sheets change.

## Verification of "live recompute"
Because openpyxl writes formulas but does not compute them, tests must:
- Confirm the target cells contain the expected **formula strings** (start with `=`,
  reference the named ranges).
- Use LibreOffice headless (`soffice --headless --convert-to xlsx --calc`) or
  `libreoffice --calc` macro to force a recalc, then read values — OR assert the
  formula text + a Python-side oracle that the SUMIFS *would* equal the known total.
- Keep all existing pytest green.
