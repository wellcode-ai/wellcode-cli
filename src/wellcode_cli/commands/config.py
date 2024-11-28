from pathlib import Path
import json
import rich_click as click
from rich.console import Console
from rich.prompt import Prompt, Confirm
from ..config import get_github_org
from ..github.client import GithubClient
from ..github.app_config import WELLCODE_APP
console = Console()
CONFIG_FILE = Path.home() / '.wellcode' / 'config.json'

@click.command()
def config():
    """Configure the CLI"""
    console.print("\n[bold]Wellcode.ai Configuration[/]")
    config_data = {}
    
    # Load existing config if available
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config_data = json.load(f)

    # 1. GitHub Configuration (Required)
    console.print("\n[bold cyan]GitHub Configuration[/]")
    org_name = Prompt.ask(
        "Enter your GitHub organization",
        default=get_github_org()
    )
    
    # Check GitHub App installation
    try:
        github_client = GithubClient()
        installation_id = github_client._get_installation_id(org_name)
        
        if not installation_id:
            console.print("\n[yellow]Wellcode GitHub App needs to be installed[/]")
            console.print("Please install the app:")
            console.print(f"1. Visit: {WELLCODE_APP['APP_URL']}")
            console.print("2. Click 'Install'")
            console.print(f"3. Select your organization ({org_name})")
            
            if not Confirm.ask("Have you installed the GitHub App?"):
                console.print("[red]Configuration cancelled. Please install the GitHub App first.[/]")
                return
            
            installation_id = github_client._get_installation_id(org_name)
            if not installation_id:
                console.print("[red]Error: GitHub App installation not found. Please try again.[/]")
                return
        
        console.print("[green]✓ GitHub App installation verified[/]")
        config_data['GITHUB_ORG'] = org_name

        # 2. Linear Configuration (Optional)
        console.print("\n[bold cyan]Linear Configuration[/]")
        if Confirm.ask("Would you like to configure Linear integration?", default=False):
            linear_key = Prompt.ask("Enter your Linear API key")
            config_data['LINEAR_API_KEY'] = linear_key
            console.print("[green]✓ Linear integration configured[/]")

        # 3. Split.io Configuration (Optional)
        console.print("\n[bold cyan]Split.io Configuration[/]")
        if Confirm.ask("Would you like to configure Split.io integration?", default=False):
            split_key = Prompt.ask("Enter your Split.io API key")
            config_data['SPLIT_API_KEY'] = split_key
            console.print("[green]✓ Split.io integration configured[/]")

        # 4. Anthropic Configuration (Optional)
        console.print("\n[bold cyan]Anthropic Configuration[/]")
        if Confirm.ask("Would you like to configure AI-powered insights (using Anthropic)?", default=True):
            anthropic_key = Prompt.ask("Enter your Anthropic API key")
            config_data['ANTHROPIC_API_KEY'] = anthropic_key
            console.print("[green]✓ AI-powered insights enabled[/]")

        # Save configuration
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)

        # Show final configuration summary
        console.print("\n[bold]Final Configuration Summary:[/]")
        console.print("[green]✓ GitHub App installed and configured[/]")
        integrations = {
            'LINEAR_API_KEY': 'Linear',
            'SPLIT_API_KEY': 'Split.io',
            'ANTHROPIC_API_KEY': 'Anthropic AI'
        }
        
        for key, name in integrations.items():
            status = "✓" if key in config_data else "✗"
            color = "green" if key in config_data else "red"
            console.print(f"[{color}]{status} {name}[/]")

        console.print("\n✅ [green]Configuration saved successfully![/]")

    except Exception as e:
        console.print(f"[red]Error verifying GitHub App installation: {str(e)}[/]")
        return
