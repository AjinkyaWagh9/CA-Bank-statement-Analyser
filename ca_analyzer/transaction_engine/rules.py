from ca_analyzer.core.config import config

def get_category_rules() -> dict:
    """Loads matching keywords and categorization maps from yaml config."""
    return config.category_rules
