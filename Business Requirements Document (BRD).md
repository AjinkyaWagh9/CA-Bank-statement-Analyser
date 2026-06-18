# **Business Requirements Document (BRD)**

# **CA Bank Statement Consolidation & Financial Analysis Platform**

---

# **1\. Purpose**

The purpose of this system is to automate the extraction, consolidation, classification, reconciliation, and analysis of financial transactions from multiple bank statements and capital gain documents for Income Tax Return (ITR) preparation and financial analysis.

The system will act as an intelligent transaction classification engine that significantly reduces manual effort for Chartered Accountants while allowing manual review and reclassification wherever necessary.

The system follows a **Human-in-the-Loop (HITL)** approach, wherein all classifications are assumptions based on business rules, transaction patterns, and supporting documents and can be overridden by the CA/user.

---

# **2\. Business Objectives**

The system should:

1. Consolidate multiple bank statements into a single analysis workbook.  
2. Automatically classify credit and debit transactions.  
3. Identify loans, inter-bank transfers, taxes, deductions, investments, and capital gains.  
4. Generate CA-ready schedules and summaries.  
5. Allow manual overrides.  
6. Automatically refresh all reports when classifications change.  
7. Provide complete transaction traceability back to the original bank statements.  
8. Reduce manual bank statement analysis time by more than 80%.

---

# **3\. Scope**

## **Included**

### **Inputs**

* Multiple Bank Statements  
* Capital Gain Documents  
* Broker Statements  
* Form 26AS  
* AIS  
* TIS

### **Outputs**

* Consolidated Analysis Workbook  
* Income Schedules  
* Expense Schedules  
* Loan Schedules  
* Capital Gain Schedules  
* Tax Schedules  
* 80C Deduction Schedules  
* CA Review Reports

---

# **4\. Input Requirements**

## **4.1 Bank Statements**

Supported Formats:

* Excel (.xls)  
* Excel (.xlsx)  
* PDF

A taxpayer may upload:

* One or more bank statements  
* Multiple banks  
* Multiple accounts

Examples:

HDFC Bank Statement  
ICICI Bank Statement  
SBI Bank Statement

All statements will belong to the same Financial Year.

---

## **4.2 Capital Gain Documents**

Supported Formats:

* Excel  
* PDF

Supported Sources:

* Zerodha  
* Groww  
* Upstox  
* Motilal Oswal  
* HDFC Securities  
* Any other broker statement

---

## **4.3 Supporting Documents**

### **Form 26AS**

### **AIS**

### **TIS**

These documents will be used as additional evidence for:

* Salary  
* Interest Income  
* Dividend  
* Capital Gain  
* Tax Payments

---

# **5\. System Workflow**

Upload Documents  
↓

Extract Transactions  
↓

Consolidate Transactions  
↓

Classify Transactions  
↓

Generate Schedules  
↓

Manual Review  
↓

Reclassification (if required)  
↓

Automatic Refresh of Reports  
↓

Final CA Analysis Workbook

---

# **6\. Transaction Classification Engine**

The system shall classify every transaction into:

# **A. Credit Transactions**

# **B. Debit Transactions**

---

# **7\. Credit Classification Rules**

## **7.1 Salary**

### **Categories**

* Salary Income  
* Bonus Income  
* Pension Income

### **Detection Methods**

#### **Rule Based**

Keywords:

SALARY  
PAYROLL  
SAL  
BONUS  
PENSION

#### **Pattern Based**

Same Amount  
\+  
Same Party  
\+  
Monthly Frequency

#### **Evidence Based**

Form 26AS  
AIS  
TIS

If evidence is insufficient:

Classification:  
Potential Salary

Confidence:  
Medium

Status:  
Manual Review

---

## **7.2 Business Income**

Subcategories:

### **Business Income**

### **Professional Fees**

### **Cash Deposit**

### **Interest**

### **Dividend**

### **Refund**

### **Subsidy**

### **LIC Maturity**

Classification shall use:

* Narration keywords  
* Transaction patterns  
* Supporting documents  
* Manual review

---

## **7.3 House Property**

Subcategory:

Rental Income

Classification only if narration contains:

* Rent  
* Rental  
* Lease  
* House Rent

Monthly recurring credits alone shall NOT be treated as rental income.

---

## **7.4 Capital Gain**

Subcategory:

Capital Market Receipt

Sources:

* Capital Gain Reports  
* Broker Statements  
* SIP transactions  
* Investment transactions

---

## **7.5 Other Sources**

Any credit not classified into:

* Salary  
* Business  
* House Property  
* Capital Gain  
* Loan

shall be classified as:

Other Sources

or

Unclassified – Needs Review.

---

## **7.6 Loan Amount Deposited by Banks**

Examples:

Personal Loan  
Home Loan  
Vehicle Loan  
LAP  
Business Loan

Detection Methods:

Keywords:

LOAN  
DISB  
PL  
HL  
LAP  
FINANCE  
NBFC

Pattern Matching

Supporting Documents

Manual Review

---

# **8\. Debit Classification Rules**

## **8.1 Expenses**

Subcategories:

Business Expense

Personal Expense

Household Expense

Unclassified Expense

Business expenses may be identified through:

* Vendor Mapping  
* Narration Keywords  
* Assumptions  
* Manual Review

Household and personal expenses should not be categorised as business expenses.

---

## **8.2 Inter-Bank Transfers**

Definition:

Transfer between multiple accounts belonging to the same taxpayer.

Matching Conditions:

Same Amount  
\+  
Same Date

Narration matching is NOT mandatory.

Examples:

ICICI Debit ₹50,000

HDFC Credit ₹50,000

→ Inter Bank Transfer

This logic should work across all uploaded bank statements.

---

## **8.3 Business Payments**

Transactions identified as:

* Vendor payments  
* Office expenses  
* Professional expenses  
* Business purchases

shall be classified under Business Payments.

---

## **8.4 Cheque Bounce**

Examples:

CHQ RETURN  
CHEQUE RETURN  
RETURN CHARGES

Classification:

Cheque Bounce

---

# **9\. GST Classification Engine**

GST identification methods:

1. Narration Keywords  
2. Manual Classification

If narration explicitly indicates GST inclusion:

Assume:

GST Rate \= 18%

Calculate:

Taxable Amount

GST Amount

Gross Amount

GST Rate

If GST cannot be confidently identified:

No assumptions shall be made.

---

# **10\. Loan Analysis Engine**

## **Case 1 – Bank Loan**

Credit:

Loan Disbursement

Debit:

EMI

EMI shall be linked to the original loan.

---

## **Case 2 – Loan from Friend/Relative**

Example:

Credit:

Rajesh ₹1,00,000

Debit:

Rajesh ₹1,00,000

Matching Order:

1. Person Name  
2. Amount  
3. Date

The system shall calculate:

Loan Received

Loan Repaid

Outstanding Loan

---

## **Partial Repayment**

Example:

Credit:  
₹1,00,000

Repayment:  
₹20,000  
₹30,000

Outstanding:  
₹50,000

---

## **Case 3 – Loan Not Repaid**

If repayment is not found during the Financial Year:

Classification:

Income

The system should automatically update:

Income Summary

Loan Schedule

Tax Schedule

All dependent reports

---

# **11\. Capital Gain Engine**

Investment identification keywords:

SIP

MF

MUTUAL FUND

AMC

ZERODHA

GROWW

UPSTOX

HDFC SECURITIES

Investment transactions shall be reconciled with:

* Broker Statements  
* Capital Gain Reports

If no matching evidence exists:

Classification:

Potential Capital Gain

Status:

Manual Review

---

# **12\. Confidence Engine**

Every transaction shall contain:

High

Medium

Low

confidence score.

---

# **13\. Manual Override Engine**

Users shall be able to edit:

Category

Subcategory

GST Flag

Loan Flag

Tax Flag

Capital Gain Flag

Confidence

Remarks

Derived Fields

---

Users shall NOT be allowed to edit:

Date

Narration

Debit Amount

Credit Amount

Bank Name

Original Evidence Data

---

# **14\. Transaction Traceability**

Every transaction must store:

Transaction ID

Bank Name

Bank Account Number

Statement File Name

Sheet Name

Statement Row Number

Original Narration

Original Amount

Financial Year

This should allow tracing every transaction back to its source statement.

---

# **15\. Output Workbook Structure**

## **Sheet 1**

Cover Sheet

## **Sheet 2**

Summary

## **Sheet 3**

Consolidated All Transactions

## **Sheet 4**

HDFC Transactions

## **Sheet 5**

ICICI Transactions

## **Sheet 6**

SBI Transactions

(One sheet per bank)

## **Sheet 7**

Income Analysis

## **Sheet 8**

Expense Analysis

## **Sheet 9**

Monthly Cash Flow

## **Sheet 10**

Tax Payments

## **Sheet 11**

80C Deduction Tracker

## **Sheet 12**

Capital Gain Analysis

## **Sheet 13**

Potential Capital Gains

## **Sheet 14**

Loan Ledger

## **Sheet 15**

EMI Analysis

## **Sheet 16**

Inter-Bank Transfer Analysis

## **Sheet 17**

Related Party Analysis

## **Sheet 18**

Unclassified Transactions

## **Sheet 19**

CA Observations

---

# **16\. 80C Schedule**

Categories:

Insurance Premium

School Fees

PPF

Sukanya Samriddhi

NPS

Any other eligible deduction

---

# **17\. Drawings Schedule**

Categories:

Tax Payments

GST Payments

Utility Payments

Personal Withdrawals

Household Expenses

---

# **18\. Formula-Based Workbook Requirements**

Workbook must remain fully dynamic.

If user changes any classification:

All dependent sheets should refresh automatically.

Examples:

Summary

Income Analysis

Expense Analysis

Loan Schedule

Tax Schedule

Capital Gain Schedule

80C Schedule

Cash Flow Statements

All formulas should be Excel-based:

SUMIFS

COUNTIFS

INDEX MATCH

XLOOKUP

Dynamic Named Ranges

Pivot Tables (Optional)

---

# **19\. Non-Functional Requirements**

Accuracy:  
≥95%

Workbook Generation:  
\<30 seconds

Supported Transactions:  
100,000+

Scalability:  
Multiple Banks  
Multiple Statements  
Multiple Supporting Documents

Auditability:  
100%

Traceability:  
100%

Manual Override:  
100%

---

# **20\. Acceptance Criteria**

The system shall be accepted if:

✓ Multiple bank statements are consolidated.

✓ All transactions are classified.

✓ Loans are identified.

✓ Inter-bank transfers are identified.

✓ Capital gains are identified.

✓ Tax and GST schedules are generated.

✓ 80C schedules are generated.

✓ Workbook remains formula driven.

✓ Manual overrides automatically refresh reports.

✓ Every transaction can be traced back to the original bank statement.

✓ CA can review and reclassify any transaction without altering original evidence data.

