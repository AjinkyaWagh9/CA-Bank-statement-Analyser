import xlrd
import re
import pandas as pd
from ca_analyzer.parsers.base_parser import BaseParser
from ca_analyzer.core.exceptions import ParserError
from ca_analyzer.core.utilities import parse_amount, parse_date

class HDFCParser(BaseParser):
    def extract_metadata(self) -> dict:
        book = xlrd.open_workbook(self.filepath)
        sheet = book.sheet_by_index(0)
        
        person_name = "N/A"
        account_number = "N/A"
        ifsc = "HDFC0002092" # parsed below or fallback
        start_date = "N/A"
        end_date = "N/A"
        
        for r in range(min(30, sheet.nrows)):
            row_vals = [str(sheet.cell_value(r, c)).strip() for c in range(sheet.ncols)]
            
            # Extract Person Name from row 5, col A (0-indexed)
            if r == 5 and row_vals[0]:
                person_name = row_vals[0].replace("MR.", "").replace("MRS.", "").replace("MS.", "").strip()
                # Clean multiple spaces
                person_name = " ".join(person_name.split())
                
            # Search for Account Number
            row_str = " ".join(row_vals)
            if "Account No" in row_str:
                match = re.search(r"Account No\s*:\s*([A-Za-z0-9]+)", row_str)
                if match:
                    account_number = match.group(1).strip()
            
            # Search for IFSC
            if "IFSC" in row_str:
                match = re.search(r"IFSC\s*:\s*([A-Z0-9]+)", row_str)
                if match:
                    ifsc = match.group(1).strip()
            
            # Search for dates
            if "Statement From" in row_str or "Statement Period" in row_str:
                date_matches = re.findall(r"(\d{2}/\d{2}/\d{4})", row_str)
                if len(date_matches) >= 2:
                    start_date = date_matches[0]
                    end_date = date_matches[1]
                    
        return {
            "Person_Name": person_name,
            "Bank_Name": "HDFC",
            "Account_Number": account_number,
            "IFSC": ifsc,
            "Statement_Start": start_date,
            "Statement_End": end_date
        }

    def extract_transactions(self) -> pd.DataFrame:
        book = xlrd.open_workbook(self.filepath)
        sheet = book.sheet_by_index(0)
        
        header_row_idx = None
        for r in range(min(50, sheet.nrows)):
            row_vals = [str(sheet.cell_value(r, c)).strip().lower() for c in range(sheet.ncols)]
            if "date" in row_vals and "narration" in row_vals and "closing balance" in row_vals:
                header_row_idx = r
                break
                
        if header_row_idx is None:
            raise ParserError("Could not find transaction header row for HDFC statement.")
            
        headers = [str(sheet.cell_value(header_row_idx, c)).strip() for c in range(sheet.ncols)]
        
        rows = []
        source_row_nos = []
        for r in range(header_row_idx + 1, sheet.nrows):
            row_vals = [sheet.cell_value(r, c) for c in range(sheet.ncols)]

            # Skip separator lines or empty lines
            val_0 = str(row_vals[0]).strip()
            if val_0.startswith("*") or val_0.startswith("Statement") or "registered office" in val_0.lower():
                continue
            if all(str(x).strip() == "" for x in row_vals):
                # If we've reached a large block of empty rows, stop
                break
            if val_0 == "":
                # Could be a line with empty date but has details, or just padding
                # Bank statements sometimes have narration wrapping to next line,
                # but standard HDFC has 1 txn per line. Let's make sure it's a valid row
                if not any(str(x).strip() != "" for x in row_vals):
                    continue
            rows.append(row_vals)
            source_row_nos.append(r + 1)  # 1-based row number in original statement

        df = pd.DataFrame(rows, columns=headers)
        
        # Rename columns to standard internal names
        col_map = {
            "Date": "raw_date",
            "Narration": "raw_narration",
            "Chq./Ref.No.": "raw_chq_ref",
            "Withdrawal Amt.": "raw_debit",
            "Deposit Amt.": "raw_credit",
            "Closing Balance": "raw_balance"
        }
        
        df_renamed = pd.DataFrame()
        for excel_col, canonical_col in col_map.items():
            if excel_col in df.columns:
                df_renamed[canonical_col] = df[excel_col]
            else:
                df_renamed[canonical_col] = 0.0 if "debit" in canonical_col or "credit" in canonical_col or "balance" in canonical_col else ""

        # Traceability columns
        import os
        df_renamed["Statement_File_Name"] = os.path.basename(str(self.filepath))
        df_renamed["Sheet_Name"] = sheet.name
        df_renamed["Statement_Row_No"] = source_row_nos

        return df_renamed
