import json
from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.prompt import Confirm, Prompt

from ..config import get_github_org
from ..github.app_config import WELLCODE_APP
from ..github.auth import clear_user_token, get_user_token
from ..github.client import GithubClient

console = Console()
CONFIG_FILE = Path.home() / ".wellcode" / "config.json"


@click.command()
def config():
    """Configure the CLI"""
    try:
        console.print("\n[bold]Wellcode.ai Configuration[/]")
        config_data = {}

        # Load existing config if available
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                config_data = json.load(f)

        # 1. GitHub Mode Selection
        console.print("\n[bold cyan]GitHub Configuration[/]")
        current_mode = config_data.get("GITHUB_MODE", "organization")
        github_mode = Prompt.ask(
            "Choose GitHub mode",
            choices=["organization", "personal"],
            default=current_mode,
        )

        # Clear organization-specific settings if switching from org to personal
        if github_mode != current_mode and github_mode == "personal":
            if "GITHUB_ORG" in config_data:
                del config_data["GITHUB_ORG"]
                # Reset GitHub client cache
                github_client = GithubClient()
                if hasattr(github_client._local, "github"):
                    delattr(github_client._local, "github")

        config_data["GITHUB_MODE"] = github_mode

        # 2. GitHub Organization (only if org mode)
        if github_mode == "organization":
            current_org = config_data.get("GITHUB_ORG", get_github_org())
            org_name = Prompt.ask("Enter your GitHub organization", default=current_org)
            config_data["GITHUB_ORG"] = org_name

        # 3. User Authentication
        console.print("\n[bold cyan]GitHub Authentication[/]")
        has_token = "GITHUB_USER_TOKEN" in config_data
        if has_token:
            console.print("[yellow]GitHub token is already configured[/]")
            if Confirm.ask(
                "Would you like to reconfigure GitHub authentication?", default=False
            ):
                clear_user_token()
                token = get_user_token()
                if not token:
                    console.print("[red]Error: GitHub authentication failed[/]")
                    return
                config_data["GITHUB_USER_TOKEN"] = token
        else:
            token = get_user_token()
            if not token:
                console.print("[red]Error: GitHub authentication failed[/]")
                return
            config_data["GITHUB_USER_TOKEN"] = token

        # 4. GitHub App Installation (only for organization mode)
        if github_mode == "organization":
            console.print("\n[bold cyan]GitHub App Installation[/]")
            github_client = GithubClient()
            github_client._local.token = config_data["GITHUB_USER_TOKEN"]

            if not github_client._check_app_installation(org_name):
                console.print("\n[yellow]Wellcode GitHub App needs to be installed[/]")
                console.print("Please install the app:")
                console.print(f"1. Visit: {WELLCODE_APP['APP_URL']}")
                console.print("2. Click 'Install'")
                console.print(f"3. Select your organization ({org_name})")

                if not Confirm.ask("Have you installed the GitHub App?"):
                    console.print(
                        "[red]Configuration cancelled. Please install the GitHub App first.[/]"
                    )
                    return

                import time

                console.print("[yellow]Waiting for installation to propagate...[/]")
                time.sleep(2)

                if not github_client._check_app_installation(org_name):
                    console.print(
                        "[red]Error: GitHub App installation not found. Please try again.[/]"
                    )
                    console.print(
                        "[yellow]Note: If you just installed the app, it might take a few moments to be available.[/]"
                    )
                    return

            console.print("[green]✓ GitHub configuration complete![/]")

        # Optional integrations with secret masking
        optional_configs = {
            "Linear": ("LINEAR_API_KEY", "Enter your Linear API key"),
            "Split.io": ("SPLIT_API_KEY", "Enter your Split.io API key"),
            "Anthropic": ("ANTHROPIC_API_KEY", "Enter your Anthropic API key"),
        }

        for name, (key, prompt) in optional_configs.items():
            console.print(f"\n[bold cyan]{name} Configuration[/]")
            handle_sensitive_config(config_data, name, key, prompt)

        # Save configuration
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=2)

        # Show final configuration summary
        console.print("\n[bold]Final Configuration Summary:[/]")
        console.print(f"[green]✓ GitHub Mode: {github_mode}[/]")
        if github_mode == "organization":
            console.print(
                f"[green]✓ GitHub Organization: {config_data['GITHUB_ORG']}[/]"
            )
            console.print("[green]✓ GitHub App installed and configured[/]")

        for name, (key, _) in optional_configs.items():
            status = "✓" if key in config_data else "✗"
            color = "green" if key in config_data else "red"
            console.print(f"[{color}]{status} {name}[/]")

        console.print("\n✅ [green]Configuration saved successfully![/]")

        # Reset GitHub client to use new configuration
        github_client = GithubClient()
        if hasattr(github_client._local, "github"):
            delattr(github_client._local, "github")

        # Force reload of GitHub client configuration
        github_client = GithubClient()
        github_client.reload_config()

        return True  # Indicate success without exiting

    except Exception as e:
        console.print(f"\n[red]Error during configuration: {str(e)}[/]")
        console.print("[yellow]Configuration not saved. Please try again.[/]")
        return False  # Indicate failure without exiting


def handle_sensitive_config(config_data, name, key, prompt_text):
    """Handle sensitive configuration values with option to keep existing"""
    has_key = key in config_data

    if has_key:
        console.print(f"[yellow]{name} API key is already configured (*****)[/]")
        choice = Prompt.ask(
            f"Would you like to reconfigure {name}?",
            choices=["y", "n", "clear"],
            default="n",
        )

        if choice == "y":
            value = Prompt.ask(prompt_text)
            if value:
                config_data[key] = value
        elif choice == "clear":
            if key in config_data:
                del config_data[key]
                console.print(f"[yellow]{name} configuration cleared[/]")
    else:
        if Confirm.ask(
            f"Would you like to configure {name} integration?", default=False
        ):
            value = Prompt.ask(prompt_text)
            if value:
                config_data[key] = value
