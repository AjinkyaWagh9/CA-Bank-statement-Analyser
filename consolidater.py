#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from ca_analyzer.consolidator import consolidate_statements

def main():
    statement_files = [
        "SANJAY JINDAL HDFC BANK STATEMENT FY 2024-25.xls",
        "SANJAY JINDAL ICICI BANK FY 2024-25.xls",
        "SANJAY JINDAL SBI 2024-25.xlsx"
    ]
    
    resolved_files = []
    for f in statement_files:
        if os.path.exists(f):
            resolved_files.append(f)
        else:
            unprocessed_path = os.path.join("Bank Statements", "Unprocessed", f)
            if os.path.exists(unprocessed_path):
                resolved_files.append(unprocessed_path)
            else:
                print(f"Warning: File not found: {f}")
                
    if not resolved_files:
        print("Error: No statement files found.")
        sys.exit(1)
        
    output_xlsx = "Consolidated_CA_Analysis.xlsx"
    
    print(f"Consolidating statements: {resolved_files}")
    consolidate_statements(resolved_files, output_xlsx)
    print(f"✅ Success! Consolidated analysis saved to {output_xlsx}")

if __name__ == "__main__":
    main()