import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# GitHub configuration
GITHUB_ORG = os.getenv('GITHUB_ORG')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

# Linear configuration
LINEAR_API_KEY = os.getenv('LINEAR_API_KEY')

# Add other configuration variables as needed
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

SPLIT_API_KEY = os.getenv('SPLIT_API_KEY')