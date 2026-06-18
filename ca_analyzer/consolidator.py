import os
import pandas as pd
from pathlib import Path
from ca_analyzer.core.exceptions import ParserError, AnalyzerError
from ca_analyzer.core.logger import get_logger
from ca_analyzer.parsers.hdfc_parser import HDFCParser
from ca_analyzer.parsers.icici_parser import ICICIParser
from ca_analyzer.parsers.sbi_parser import SBIParser
from ca_analyzer.validation.schema_validator import validate_schema
from ca_analyzer.validation.transaction_validator import validate_transactions
from ca_analyzer.validation.reconciliation import reconcile_all
from ca_analyzer.normalization.standardizer import standardize_dataframe
from ca_analyzer.transaction_engine.merchant_extractor import extract_merchant_and_counterparty
from ca_analyzer.transaction_engine.narration_parser import extract_transaction_mode
from ca_analyzer.transaction_engine.category_engine import apply_categorization
from ca_analyzer.presentation import build_ca_report

logger = get_logger("consolidator")

def detect_parser(filepath: str):
    name = Path(filepath).name.upper()
    if "HDFC" in name:
        return HDFCParser(filepath)
    elif "ICICI" in name:
        return ICICIParser(filepath)
    elif "SBI" in name:
        return SBIParser(filepath)
    else:
        raise ParserError(f"Unsupported bank statement or unknown parser format for: {filepath}")

def process_single_statement(filepath: str) -> pd.DataFrame:
    """Parses, standardizes, cleans, and categorizes a single bank statement file."""
    # 1. Parse using correct bank parser
    parser = detect_parser(filepath)
    raw_df = parser.parse()
    
    # 2. Standardize column headers and types
    df = standardize_dataframe(raw_df)
    
    # 3. Validate schema layout
    validate_schema(df)
    
    # 4. Clean and parse narration (mode, merchant, counterparty)
    modes = []
    merchants = []
    counterparties = []
    for _, row in df.iterrows():
        narr = row["Narration"]
        mode = extract_transaction_mode(narr)
        merchant, counterparty = extract_merchant_and_counterparty(narr)
        modes.append(mode)
        merchants.append(merchant)
        counterparties.append(counterparty)
        
    df["Transaction_Mode"] = modes
    df["Merchant_Name"] = merchants
    df["Counterparty"] = counterparties
    
    # 5. Apply categorization rules
    df = apply_categorization(df)
    
    return df

def consolidate_statements(filepaths: list, output_xlsx: str) -> str:
    """
    Core pipeline that consumes multiple statement files, parses, normalizes,
    concatenates, reconciles, and compiles them to a final CA analysis workbook.
    """
    logger.info(f"Starting consolidation pipeline for {len(filepaths)} files...")
    
    parsed_dfs = []
    for path in filepaths:
        if not os.path.exists(path):
            logger.error(f"File not found: {path}")
            continue
        try:
            df = process_single_statement(path)
            parsed_dfs.append(df)
        except Exception as e:
            logger.error(f"Error processing {path}: {e}")
            raise e
            
    if not parsed_dfs:
        raise AnalyzerError("No bank statements were successfully parsed.")
        
    # Concatenate all DataFrames
    consolidated_df = pd.concat(parsed_dfs, ignore_index=True)
    
    # Assertions for consolidated dataframe sanity
    assert consolidated_df.columns.is_unique, "Duplicate column headers detected!"
    assert not consolidated_df.iloc[:, 0].astype(str).str.contains(
        "Date|Income Type|Expense Type|Bank|Narration", case=False
    ).any(), "Repeated header values detected in transaction data rows!"
    
    # Run global validation checks
    validate_transactions(consolidated_df)
    
    # Reconcile bank balances
    reconcile_all(consolidated_df)
    
    # Build final Excel presentation report
    logger.info(f"Compiling final consolidated Excel report: {output_xlsx}")
    build_ca_report(consolidated_df, output_xlsx)
    
    logger.info("Consolidation pipeline completed successfully!")
    return output_xlsx
