import pandas as pd
from ca_analyzer.core.exceptions import SchemaError
from ca_analyzer.core.schemas import CANONICAL_COLUMNS
from ca_analyzer.core.logger import get_logger

logger = get_logger("schema_validator")

def validate_schema(df: pd.DataFrame) -> bool:
    """Verifies that the DataFrame has the canonical schema structure and columns."""
    missing = [c for c in CANONICAL_COLUMNS if c not in df.columns]
    if missing:
        logger.error(f"Schema validation failed. Missing columns: {missing}")
        raise SchemaError(f"DataFrame is missing canonical columns: {missing}")
    return True
