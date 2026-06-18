# CA Bank Statement Analyser — Implementation Plan

Gap-closing plan from the current working `ca_analyzer` pipeline to the BRD target.

## Locked decisions
1. **Refresh model:** Excel-formula workbook (BRD §18). CA edits a `Category_Final`/flag
   column on the Consolidated master sheet; all summary sheets recompute live via
   SUMIFS/COUNTIFS/XLOOKUP. No app/DB in this build.
2. **Evidence docs (26AS / AIS / TIS / broker):** deferred to Phase 3 (LLM extraction).
3. **LLM (Claude API):** allowed as a *fallback* — rules first, LLM only for low-confidence
   rows, unknown PDF/broker formats, and business-vs-personal calls. Gated behind a config
   flag with a deterministic-only mode.

## Model usage
- **Opus:** planning, Phase 1 formula-workbook architecture, review checkpoints.
- **Sonnet:** logic-bearing modules (engines, formula emission, LLM integration).
- **Haiku:** mechanical work (schema/column additions, YAML rules, sheet protection, simple sheets).

## Expectation-setting
- "95% accuracy" = **after** the HITL review pass, not zero-touch.
- Business/personal/household split and "any broker" parsing are assistive, review-required — never silent.
- Scanned-PDF/OCR statements out of scope until explicitly funded.

---

## Phase 0 — Foundation (traceability + confidence + safe master sheet)
- [ ] 0.1 Extend `CANONICAL_COLUMNS` + all parsers: add `Transaction_ID` (deterministic hash),
      `Statement_File_Name`, `Sheet_Name`, `Statement_Row_No`, `Financial_Year`. *(haiku)*
- [ ] 0.2 Add `Confidence` (High/Medium/Low) + `Match_Reason` columns; populate from match
      strength in `category_engine`. *(sonnet)*
- [ ] 0.3 Add editable override columns to the Consolidated master sheet: `Category_Final`,
      `Sub_Category_Final`, `GST_Flag`, `Loan_Flag`, `Tax_Flag`, `CG_Flag`, `Confidence`,
      `Remarks`. `*_Final` default to the engine's guess so the CA only edits exceptions. *(sonnet)*
- [ ] 0.4 Lock non-editable columns (Date/Narration/amounts/Bank) via sheet protection. *(haiku)*

## Phase 1 — Dynamic formula workbook (hardest core piece)
- [ ] 1.1 Rewrite `report_builder` summary sheets (Summary, Income, Expense, Cash Flow, Tax,
      80C, Loan, CG, Drawings) to emit SUMIFS/COUNTIFS/XLOOKUP against the Consolidated
      master sheet instead of static Python-computed values. *(sonnet, review checkpoints)*
- [ ] 1.2 Add missing §15 sheets: Potential Capital Gains, Loan Ledger, EMI Analysis,
      Inter-Bank Transfer, Related Party, Unclassified, CA Observations. *(sonnet)*
- [ ] 1.3 Named/dynamic ranges so adding rows doesn't break formulas. *(sonnet)*
- [ ] 1.4 Verify "edit a cell → all sheets refresh" in Excel/LibreOffice. *(verification)*

## Phase 2 — Smarter deterministic classification engines
- [ ] 2.1 Inter-bank transfer engine: match `(Date, |Amount|)` debit↔credit across accounts. *(sonnet)*
- [ ] 2.2 Loan engine v2: bank-loan disbursement↔EMI link + friend/relative ledger
      (name→amount→date, `rapidfuzz`), partial repayment, outstanding, "not repaid → income". *(sonnet)*
- [ ] 2.3 Salary pattern detector (amount + party + monthly recurrence) → "Potential Salary / Medium / Review". *(sonnet)*
- [ ] 2.4 Expanded YAML rules for §7–8 keyword sets; rental guard; cheque-bounce. *(haiku)*
- [ ] 2.5 GST breakup calculator (taxable/GST/gross at 18% when flagged). *(haiku)*

## Phase 3 — LLM-assisted extraction & classification
- [ ] 3.1 PDF bank parser: `pdfplumber`/`camelot` for digital PDFs → standardizer. *(sonnet)*
- [ ] 3.2 LLM fallback classifier: route low-confidence/`Miscellaneous`/business-vs-personal
      rows to Claude (structured output); result lands in editable column. *(sonnet)*
- [ ] 3.3 LLM extraction for 26AS / AIS / TIS / broker statements → normalized evidence tables. *(sonnet)*
- [ ] 3.4 Capital-gain reconciliation against extracted broker data. *(sonnet)*

## Phase 4 — Hardening
- [ ] 4.1 Performance pass for 100k+ transactions (vectorize, <30s). *(sonnet)*
- [ ] 4.2 Expand tests (parsers, transfer/loan matching, formula integrity). *(haiku/sonnet)*
- [ ] 4.3 Privacy: document external LLM calls; gate behind config flag; deterministic-only mode. *(doc)*

---

## Reference repos — verdict
Existing `ca_analyzer` is already ahead of most listed repos. Do **not** restructure around them.
- Basic parsers (MalayPalace, Club-Asymmetric, HDFC-Statement-Analyser, apoorvpatne10): skip; skim keyword lists only.
- `sebastienrousseau/bankstatementparser`: glance for PDF/validation patterns.
- `johnsonhk88` (LLM+OCR), `vas3k/TaxHacker`: relevant *approach* for Phase 3 PDF + evidence extraction.
- camelot/tabula-py examples: directly useful for Phase 3.1.
