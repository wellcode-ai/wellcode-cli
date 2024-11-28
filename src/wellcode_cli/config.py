from pathlib import Path
import json
import os
from typing import Optional
from rich.console import Console
console = Console()

CONFIG_DIR = Path.home() / '.wellcode'
CONFIG_FILE = CONFIG_DIR / 'config.json'

def get_config_value(key: str) -> Optional[str]:
    """Get configuration value with fallback to environment variables"""
    # First try to load from config file
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config_data = json.load(f)
                if key in config_data and config_data[key]:
                    return config_data[key]
        except Exception as e:
            console.print(f"[yellow]Warning: Error reading config file: {e}[/]")
    
    # Fallback to environment variable
    return os.getenv(key)

# Export commonly used config values
def get_github_token() -> Optional[str]:
    return get_config_value('GITHUB_TOKEN')

def get_github_org() -> Optional[str]:
    return get_config_value('GITHUB_ORG')

def get_linear_api_key() -> Optional[str]:
    return get_config_value('LINEAR_API_KEY')

def get_anthropic_api_key() -> Optional[str]:
    return get_config_value('ANTHROPIC_API_KEY')

def get_split_api_key() -> Optional[str]:
    return get_config_value('SPLIT_API_KEY')