import os
import yaml
from pathlib import Path

class AppConfig:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppConfig, cls).__new__(cls)
            cls._instance._load_all_configs()
        return cls._instance

    def _load_all_configs(self):
        config_dir = Path(__file__).parent.parent / "config"
        
        with open(config_dir / "thresholds.yaml", "r") as f:
            self.thresholds = yaml.safe_load(f)
            
        with open(config_dir / "category_rules.yaml", "r") as f:
            self.category_rules = yaml.safe_load(f)
            
        with open(config_dir / "bank_rules.yaml", "r") as f:
            self.bank_rules = yaml.safe_load(f)
            
        with open(config_dir / "styles.yaml", "r") as f:
            self.styles = yaml.safe_load(f)

# Singleton instance
config = AppConfig()
