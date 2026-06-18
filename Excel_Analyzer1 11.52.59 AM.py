#!/usr/bin/env python3
import argparse
import sys
import os
from ca_analyzer.consolidator import consolidate_statements

def main():
    parser = argparse.ArgumentParser(
        description="Bank Statement Analyzer (multi-year) – CA / ITR Filing."
    )

    parser.add_argument("--input",  default=None, required=True, help="Path to bank statement (XLS/XLSX).")
    parser.add_argument("--output", default=None, help="Output Excel report path (optional)")
    parser.add_argument("--name",   default="N/A", help="Account holder name")
    parser.add_argument("--bank",   default="N/A", help="Bank and branch name")
    parser.add_argument("--account",default="N/A", help="Account number (partial)")
    parser.add_argument("--type",   default="N/A", help="Account type (Savings/Current)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file does not exist: {args.input}")
        sys.exit(1)
        
    output_path = args.output
    if not output_path:
        stem = os.path.splitext(os.path.basename(args.input))[0]
        output_path = f"{stem}_CA_Analysis.xlsx"
        
    print(f"Analyzing statement: {args.input}")
    try:
        consolidate_statements([args.input], output_path)
        print(f"✅ Success! Report saved to {output_path}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
