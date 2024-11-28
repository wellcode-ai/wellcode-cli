from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
@click.option(
    "--append", is_flag=True, help="Automatically append to shell config file"
)
def completion(shell, append):
    """Generate shell completion script"""
    completion_scripts = {
        "bash": """
# wellcode-cli bash completion
eval "$(_WELLCODE_CLI_COMPLETE=bash_source wellcode-cli)"
""",
        "zsh": """
# wellcode-cli zsh completion
eval "$(_WELLCODE_CLI_COMPLETE=zsh_source wellcode-cli)"
""",
        "fish": """
# wellcode-cli fish completion
eval (env _WELLCODE_CLI_COMPLETE=fish_source wellcode-cli)
""",
    }

    script = completion_scripts[shell]

    if append:
        config_file = {
            "bash": Path.home() / ".bashrc",
            "zsh": Path.home() / ".zshrc",
            "fish": Path.home() / ".config/fish/completions/wellcode-cli.fish",
        }[shell]

        try:
            # Create directory for fish if needed
            if shell == "fish":
                config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(config_file, "a") as f:
                f.write(f"\n{script}\n")

            console.print(
                f"[green]✓ Successfully added completion script to {config_file}[/]"
            )
            console.print("[yellow]Please restart your shell or run:[/]")
            console.print(f"[yellow]source {config_file}[/]")
        except Exception as e:
            console.print(f"[red]Error writing to {config_file}: {str(e)}[/]")
    else:
        console.print(
            Panel(
                f"""[bold green]Shell Completion Script for {shell}[/]
            
To enable completion, run:

[yellow]wellcode-cli completion {shell} --append[/]

Or manually add this to your shell configuration:

[yellow]{script}[/]

[bold red]Note:[/] You'll need to restart your shell or source the config file after adding the script.
""",
                title=f"Wellcode.ai {shell.upper()} Completion",
                border_style="blue",
            )
        )
