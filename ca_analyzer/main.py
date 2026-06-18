import argparse
import sys
import traceback
from ca_analyzer.consolidator import consolidate_statements
from ca_analyzer.core.logger import get_logger

logger = get_logger("cli")

def main():
    parser = argparse.ArgumentParser(
        description="Production-grade Bank Statement Analyzer & Consolidator"
    )
    parser.add_argument(
        "--inputs", 
        nargs="+", 
        required=True, 
        help="List of space-separated bank statement file paths"
    )
    parser.add_argument(
        "--output", 
        default="Consolidated_CA_Analysis.xlsx", 
        help="Output consolidated Excel filename"
    )
    
    args = parser.parse_args()
    
    try:
        consolidate_statements(args.inputs, args.output)
        print(f"\n✅ CA Financial Intelligence Report saved to: {args.output}\n")
    except Exception as e:
        logger.error(f"Execution failed: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
