import os
import pandas as pd
from pathlib import Path
from ca_analyzer.core.exceptions import ParserError
from ca_analyzer.core.logger import get_logger

logger = get_logger("base_parser")

class BaseParser:
    def __init__(self, filepath, password=None):
        self.filepath = Path(filepath)
        self.password = password
        if not self.filepath.exists():
            raise FileNotFoundError(f"File not found: {self.filepath}")

    def extract_metadata(self) -> dict:
        """Extract name, account number, bank, start/end date from header."""
        raise NotImplementedError("Subclasses must implement extract_metadata()")

    def extract_transactions(self) -> pd.DataFrame:
        """Extract transactions list and return raw DataFrame."""
        raise NotImplementedError("Subclasses must implement extract_transactions()")

    def parse(self) -> pd.DataFrame:
        """Runs the parsing workflow, returning a DataFrame with transaction rows + metadata."""
        logger.info(f"Parsing statement: {self.filepath.name}")
        metadata = self.extract_metadata()
        df = self.extract_transactions()
        
        # Add metadata columns
        for key, val in metadata.items():
            df[key] = val
            
        return df
