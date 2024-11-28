import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Wellcode GitHub App configuration
WELLCODE_APP = {
    'APP_ID': os.getenv('WELLCODE_APP_ID', "DEMO_APP_ID"),  # Default to demo values for development
    'APP_URL': "https://github.com/apps/wellcode-cli",
    'CLIENT_ID': os.getenv('WELLCODE_CLIENT_ID', "DEMO_CLIENT_ID"),  # Default to demo values for development
    'AUTH_URL': "https://github.com/login/device"
}

# Only validate in production
if os.getenv('ENVIRONMENT') == 'production':
    if not all([WELLCODE_APP['APP_ID'], WELLCODE_APP['CLIENT_ID']]):
        raise ValueError(
            "Missing required GitHub App configuration. "
            "Please ensure WELLCODE_APP_ID and WELLCODE_CLIENT_ID "
            "environment variables are set."
        )
