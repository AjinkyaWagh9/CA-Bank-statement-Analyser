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

## Phase 0 — Foundation (traceability + confidence + safe master sheet) — DONE (commit 970a19d)
- [x] 0.1 Extended `CANONICAL_COLUMNS` (now 32 cols) + parsers: `Transaction_ID` (sha1 hash),
      `Statement_File_Name`, `Sheet_Name`, `Statement_Row_No`, `Financial_Year`.
- [x] 0.2 `Confidence` (High/Medium/Low) + `Match_Reason` from match strength.
- [x] 0.3 Editable override columns on Consolidated master sheet (`Category_Final`,
      `Sub_Category_Final`, `GST/Loan/Tax/CG_Flag`, `Remarks`); `*_Final` default to engine guess.
- [x] 0.4 Non-editable evidence columns locked via openpyxl sheet protection.
- [x] (side) Fixed ICICI S.No column index bug.

## Phase 0.5 — Parser hardening — DONE (commit 3edbce3)
- [x] Root-caused transaction row loss: `is_header_row()` scanned the new `Statement_File_Name`
      column ("BANK") and dropped any txn whose narration held CREDIT/DEBIT/BANK as a fake header.
      Restricted scan to the 6 raw txn columns. Counts: HDFC 740→799, ICICI 39→163, SBI 23.
      Reconciliation warnings 76→0 across all banks. Numbers now trustworthy for Phase 1.

## Phase 1 — Dynamic formula workbook (hardest core piece)
- [x] 1.1 Converted Bank Wise Summary, Income, Expense, Monthly Cashflow to live
      SUMIFS/COUNTIFS keyed on Category_Final/Bank_Name/Date; 11 workbook named ranges
      (whole-column refs to master sheet, letters derived programmatically). (commit 0986989)
      Note: on sample data ~87% of txns are Others/Miscellaneous — classification quality is
      weak by design until Phase 2/3; formulas are correct and auto-refresh on reclassification.
- [ ] 1.2 New formula-only sheets (no engine dependency): Tax Payments, 80C Tracker,
      Capital Gain (flag-based), Drawings, Unclassified (Others/Misc + Low confidence),
      CA Observations (compliance flags + reconciliation discrepancies). *(sonnet)*
      → make `reconcile_bank` RETURN discrepancies so CA Observations can list them.
- [x] 1.3 Verified live recompute with the `formulas` pure-Python engine: flipping a master
      `Category_Final` Misc→Salary (₹6,000) recomputed Income Salary ₹28,000→₹34,000 (delta exact).
      BRD §18 satisfied. (`formulas` recalc takes minutes on whole-column refs, so it's a
      manual/opt-in check, not a default pytest.)

### Moved to Phase 2 (engine-dependent sheets, were §15)
- Inter-Bank Transfer sheet → after 2.1 transfer engine.
- Loan Ledger + EMI Analysis + Related Party → after 2.2 loan engine.
- Potential Capital Gains → after 3.x broker reconciliation.

## Phase 2 — Smarter deterministic classification engines — DONE (commit 3b032c5)
- [x] 2.1 Inter-bank transfer engine (`transaction_engine/inter_bank_transfer.py`): same-amount/±1-day
      debit↔credit across accounts → 68 legs tagged. Terminal: later engines never reclassify a leg.
- [x] 2.2 Loan engine v2 (`loan_matcher.py`): bank-loan (word-boundary keywords) + STRICT personal-loan
      requiring bidirectional evidence + person filter (excludes merchants/payment-rails/self).
      Earlier draft over-matched 90 fabricated income loans → fixed to 0; no negative outstanding.
      "Not repaid → income" gated by explicit loan keyword + ≥₹25k, marked Low confidence for CA review.
- [x] 2.3 Salary pattern detector (`salary_detector.py`): recurring monthly credits → Potential Salary /
      Medium (3 → 13). Skips transfer legs.
- [x] 2.4 Expanded YAML keyword sets (salary/loan/rent/cheque-bounce) + rental guard + cheque-bounce category.
- [x] 2.5 GST 18% breakup (Taxable/GST_Amount/Gross/GST_Rate) when narration indicates GST.
- [x] New sheets: Inter-Bank Transfers, Loan Ledger, EMI Analysis, Related Party. 65 tests pass; reconcile 0.
      Result: Miscellaneous 194→160, Others 661→629, +Inter-Bank Transfer 68, +Salary 13.
      Classification still coarse (~80% Others/Misc) — needs Phase 3 LLM fallback for real lift.

## Phase 3 — LLM-assisted extraction & classification
- [ ] 3.1 PDF bank parser: `pdfplumber`/`camelot` for digital PDFs → standardizer. *(sonnet)*
      BLOCKED: need a sample PDF bank statement to build/verify against.
- [x] 3.2 LLM fallback classifier (`transaction_engine/llm_classifier.py`, commit efa4030):
      refines Others/Misc/Low-confidence rows via **OpenAI GPT-4o** (default gpt-4o-mini);
      chunked structured output (`chat.completions.parse` + Pydantic); allowed-taxonomy guard.
      Triple-gated (llm.enabled flag default OFF + openai SDK + OPENAI_API_KEY) → no-op until
      enabled; deterministic-only mode preserved. Mock-tested only (70 pass).
      (Was briefly on Bedrock; user switched to OpenAI — Bedrock code removed.)
      TO RUN: `pip install openai`, `export OPENAI_API_KEY=sk-...`, set `llm.enabled: true`.
      NOT YET validated against the live OpenAI API (no key in env).
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
