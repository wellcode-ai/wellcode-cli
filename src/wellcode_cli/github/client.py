from github import Github, GithubIntegration
from rich.console import Console
import threading
from ..utils import load_config
from .app_config import WELLCODE_APP
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

console = Console()

# Create a global session with proper pooling
def create_global_session():
    session = requests.Session()
    
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    adapter = HTTPAdapter(
        pool_connections=100,
        pool_maxsize=100,
        max_retries=retry_strategy,
        pool_block=True
    )
    
    session.mount('https://', adapter)
    return session

# Global session
GITHUB_SESSION = create_global_session()

class GithubClient:
    """Thread-safe GitHub client wrapper using Wellcode GitHub App"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._local = threading.local()
            return cls._instance
    
    @property
    def client(self):
        if not hasattr(self._local, 'github'):
            config = load_config()
            org_name = config.get('GITHUB_ORG')
            
            if not org_name:
                console.print("[red]Error: Organization name not configured[/]")
                console.print("Please run: wellcode-cli config")
                raise ValueError("Organization name required")
            
            installation_id = self._get_installation_id(org_name)
            if not installation_id:
                console.print(f"""[red]Error: Wellcode GitHub App not installed for {org_name}[/]
                
Please install the Wellcode GitHub App:
1. Visit: {WELLCODE_APP['APP_URL']}
2. Click "Install"
3. Select your organization ({org_name})
""")
                raise ValueError("GitHub App installation required")
            
            self._local.github = self._get_app_client(installation_id)
            self._local.github._Github__requester._Requester__session = GITHUB_SESSION
        
        return self._local.github
    
    def _get_installation_id(self, org_name):
        """Get installation ID for the organization"""
        try:
            # Create JWT for app authentication
            integration = GithubIntegration(
                WELLCODE_APP['APP_ID'],
                WELLCODE_APP['PRIVATE_KEY']
            )
            jwt = integration.create_jwt()
            
            # Use REST API with JWT authentication
            headers = {
                'Accept': 'application/vnd.github.v3+json',
                'Authorization': f'Bearer {jwt}',
            }
            
            response = GITHUB_SESSION.get(
                f'https://api.github.com/orgs/{org_name}/installation',
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()['id']
            return None
        except Exception as e:
            console.print(f"[red]Error checking app installation: {str(e)}[/]")
            return None
    
    def _get_app_client(self, installation_id):
        """Get authenticated client using Wellcode GitHub App"""
        try:            
            integration = GithubIntegration(
                WELLCODE_APP['APP_ID'],
                WELLCODE_APP['PRIVATE_KEY'],
            )
            # Get installation token
            access_token = integration.get_access_token(installation_id)
            
            # Create Github instance with the token string
            return Github(access_token.token)
        except Exception as e:
            console.print(f"[red]Error getting app client: {str(e)}[/]")
            return None
    
def get_github_client():
    """Returns an authenticated GitHub client instance using GitHub App"""
    github_client = GithubClient()
    return github_client.client