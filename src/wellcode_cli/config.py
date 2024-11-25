import os
from pathlib import Path
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Define config file location
CONFIG_DIR = Path.home() / '.wellcode'
CONFIG_FILE = CONFIG_DIR / 'config.json'

# Load configuration from file
config_data = {}
if CONFIG_FILE.exists():
    with open(CONFIG_FILE) as f:
        config_data = json.load(f)

# GitHub configuration
GITHUB_ORG = config_data.get('GITHUB_ORG') or os.getenv('GITHUB_ORG')
GITHUB_TOKEN = config_data.get('GITHUB_TOKEN') or os.getenv('GITHUB_TOKEN')

# Linear configuration
LINEAR_API_KEY = config_data.get('LINEAR_API_KEY') or os.getenv('LINEAR_API_KEY')

# Anthropic configuration
ANTHROPIC_API_KEY = config_data.get('ANTHROPIC_API_KEY') or os.getenv('ANTHROPIC_API_KEY')

# Split.io configuration
SPLIT_API_KEY = config_data.get('SPLIT_API_KEY') or os.getenv('SPLIT_API_KEY')