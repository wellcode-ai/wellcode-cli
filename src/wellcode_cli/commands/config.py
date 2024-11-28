from pathlib import Path
import json
import rich_click as click
from rich.console import Console
from rich.prompt import Prompt, Confirm
from ..config import get_github_token, get_github_org, get_linear_api_key, get_split_api_key, get_anthropic_api_key
console = Console()
CONFIG_FILE = Path.home() / '.wellcode' / 'config.json'

@click.command()
def config():
    """Configure the CLI"""
    console.print("\n[bold]Wellcode.ai Configuration[/]")
    
    console.print("\n[bold cyan]GitHub Configuration[/]")
    console.print("[yellow]Required Token Permissions:[/]")
    console.print("• repo - Full repository access")
    console.print("• read:org - Read organization data")
    console.print("• read:user - Read user data")
    console.print("• read:discussion - Read discussions")
    console.print("[yellow]Note:[/] For SAML SSO organizations, authorize your token in GitHub settings")    
    # Create config directory if it doesn't exist
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config if available
    config_data = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            config_data = json.load(f)

    # GitHub configuration (required)
    console.print("\n[bold blue]GitHub Configuration[/] (required)")
    config_data['GITHUB_TOKEN'] = Prompt.ask(
        "Enter your GitHub token",
        default=get_github_token(),
        password=True
    )
    config_data['GITHUB_ORG'] = Prompt.ask(
        "Enter your GitHub organization",
        default=get_github_org()
    )

    # Linear configuration
    console.print("\n[bold green]Linear Configuration[/]")
    if Confirm.ask("Would you like to configure Linear integration?", 
                   default=bool(config_data.get('LINEAR_API_KEY'))):
        config_data['LINEAR_API_KEY'] = Prompt.ask(
            "Enter your Linear API key",
            default=get_linear_api_key(),
            password=True
        )
        console.print("[green]✓ Linear integration enabled[/]")
    else:
        if 'LINEAR_API_KEY' in config_data:
            del config_data['LINEAR_API_KEY']
            console.print("[yellow]→ Linear integration disabled[/]")

    # Split.io configuration
    console.print("\n[bold magenta]Split.io Configuration[/]")
    if Confirm.ask("Would you like to configure Split.io integration?", 
                   default=bool(config_data.get('SPLIT_API_KEY'))):
        config_data['SPLIT_API_KEY'] = Prompt.ask(
            "Enter your Split.io API key",
            default=get_split_api_key(),
            password=True
        )
        console.print("[green]✓ Split.io integration enabled[/]")
    else:
        if 'SPLIT_API_KEY' in config_data:
            del config_data['SPLIT_API_KEY']
            console.print("[yellow]→ Split.io integration disabled[/]")

    # Anthropic configuration
    console.print("\n[bold yellow]Anthropic Configuration[/]")
    if Confirm.ask("Would you like to configure AI-powered insights (using Anthropic)?", 
                   default=bool(config_data.get('ANTHROPIC_API_KEY'))):
        config_data['ANTHROPIC_API_KEY'] = Prompt.ask(
            "Enter your Anthropic API key",
            default=get_anthropic_api_key(),
            password=True
        )
        console.print("[green]✓ AI-powered insights enabled[/]")
    else:
        if 'ANTHROPIC_API_KEY' in config_data:
            del config_data['ANTHROPIC_API_KEY']
            console.print("[yellow]→ AI-powered insights disabled[/]")

    # Save configuration
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=2)

    # Show final configuration summary
    console.print("\n[bold]Final Configuration Summary:[/]")
    console.print("✓ GitHub (required)")
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
