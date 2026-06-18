class AnalyzerError(Exception):
    """Base exception class for ca_analyzer."""
    pass

class ParserError(AnalyzerError):
    """Raised when parsing fails."""
    pass

class SchemaError(AnalyzerError):
    """Raised when validation fails for canonical schema."""
    pass

class ReconciliationError(AnalyzerError):
    """Raised when transaction reconciliation audits fail."""
    pass

class RuleError(AnalyzerError):
    """Raised when transaction classification engine rules fail."""
    pass
