from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import rich_click as click
from rich.console import Console
from rich.panel import Panel


class CommandType(Enum):
    REVIEW = "review"
    CONFIG = "config"
    REPORT = "report"
    HELP = "help"
    EXIT = "exit"
    CHAT = "chat"


@dataclass
class TimeRange:
    start_date: datetime
    end_date: datetime


@dataclass
class Command:
    type: CommandType
    args: Optional[list] = None
    description: str = ""
    examples: list[str] = None
    time_range: Optional[TimeRange] = None


COMMANDS = {
    CommandType.REVIEW: Command(
        type=CommandType.REVIEW,
        description="Review engineering metrics",
        examples=[
            "review my team's performance",
            "show metrics for last week",
            "review pull requests",
        ],
    ),
    CommandType.CONFIG: Command(
        type=CommandType.CONFIG,
        description="Configure your settings",
        examples=["setup my workspace", "configure integrations", "setup github token"],
    ),
    CommandType.REPORT: Command(
        type=CommandType.REPORT,
        description="Generate visual reports",
        examples=[
            "create a report",
            "show me charts",
            "generate metrics visualization",
        ],
    ),
    CommandType.CHAT: Command(
        type=CommandType.CHAT,
        description="Start interactive chat mode",
        examples=["start chat", "chat mode", "interactive mode"],
    ),
    CommandType.HELP: Command(
        type=CommandType.HELP,
        description="Show available commands and examples",
        examples=["help", "?"],
    ),
}


def get_claude_system_prompt():
    today = datetime.now(timezone.utc)
    yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    today = today.strftime("%Y-%m-%d")

    return f"""You are a CLI command interpreter for the Wellcode engineering metrics tool. Convert natural language input into specific commands.

Today's date is {today}.

Available Commands and Options:
1. review
   Options:
   --start-date, -s DATE    Start date for analysis (YYYY-MM-DD)
   --end-date, -e DATE      End date for analysis (YYYY-MM-DD)
   --user, -u USERNAME      Filter by GitHub username
   --team, -t TEAMNAME      Filter by GitHub team name

2. report
   Options:
   --output, -o PATH        Output directory for the report
   --format, -f FORMAT      Report format (html or pdf)

3. config
   Interactive command to configure:
   - GitHub integration (token and organization)
   - Linear integration (API key)
   - Split.io integration (API key)
   - Anthropic integration (API key)

4. chat
   Start interactive chat mode to discuss metrics

5. help
   Show available commands and examples

6. exit/quit
   Exit the application

Command Examples:
- "review team performance" → "review --team frontend"
- "show metrics for last week" → "review --start-date 2024-03-20 --end-date 2024-03-27"
- "how was pimouss yesterday" → "review --user pimouss --start-date {yesterday} --end-date {today}"
- "generate report" → "report --format html"
- "save report to desktop" → "report --output ~/Desktop --format html"
- "setup integrations" → "config"
- "start chat" → "chat"
- "what can I do?" → "help"
- "quit" → "exit"

CRITICAL RULES:
1. Team Handling:
   - Add --team flag when:
     * Input contains "team <name>" OR
     * Input contains "team" followed by a name anywhere in the sentence
   - Examples:
     ✅ "team frontend performance" → "review --team frontend"
     ✅ "check performance of team tata" → "review --team tata"
     ✅ "lets check performance of the team plop" → "review --team plop"
   - NEVER add a --team flag unless the input EXPLICITLY contains "team <name>"
   - The word "team" by itself should NEVER result in a --team flag

   Examples:
   ❌ "check the team performance" → "review"
   ❌ "let's check the team" → "review"
   ❌ "performance of the team" → "review"
   ✅ "team frontend performance" → "review --team frontend"
   ✅ "check team backend metrics" → "review --team backend"

2. Use REVIEW command ONLY for direct metric queries:
   - "show metrics for user X"
   - "get last week's stats for team Y"
   - Simple performance data requests

3. Use CHAT command for:
   - Analysis questions ("why is performance dropping?")
   - Comparative questions ("how is X doing compared to last month?")
   - Improvement suggestions ("how can team Y improve?")
   - Complex queries requiring context
   - Any questions starting with "why", "how", "what about", "any idea"
   - Performance discussions and insights

4. Time-based queries:
   - "yesterday" → calculate proper date
   - "last week" → calculate 7 days ago
   - "this month" → first day of current month
   - "today" → current date
   - Always convert to YYYY-MM-DD format

5. User queries:
   - "how was <user>" → review --user <user>
   - "<user>'s performance" → review --user <user>

6. Team queries:
   - "team <name>" → review --team <name>
   - "<team> performance" → review --team <name>

7. Report queries:
   - "generate report" → report with default options
   - "save report to <path>" → report --output <path>
   - Specify format with "pdf" or "html" keywords

Important:
- Output ONLY the command string with appropriate options
- Convert relative dates to actual YYYY-MM-DD format
- Include appropriate flags (--user, --team, --start-date, --end-date)
- Default to "help" if the intent is unclear

Example Inputs and Outputs:
- "how was pimouss yesterday" → "review --user pimouss --start-date {yesterday} --end-date {today}"
- "show team frontend metrics for last week" → "review --team frontend --start-date {(datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')} --end-date {today}"
- "generate html report" → "report --format html"
- "setup my workspace" → "config"
- "let's chat about metrics" → "chat"
- "show ymatagne's metrics" → "review --user ymatagne"
- "how is ymatagne performing?" → "chat"
- "any suggestions for ymatagne?" → "chat"
- "what's causing ymatagne's performance drop?" → "chat"
- "show team frontend stats" → "review --team frontend"
- "how can frontend team improve?" → "chat"

Remember: Use chat mode for analytical questions and review for direct metric queries."""


def parse_time_range(command_str: str) -> Optional[TimeRange]:
    """Parse temporal expressions from command string"""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if "yesterday" in command_str.lower():
        end_date = today_start
        start_date = end_date - timedelta(days=1)
        return TimeRange(start_date, end_date)

    if "last week" in command_str.lower():
        end_date = today_start
        start_date = end_date - timedelta(days=7)
        return TimeRange(start_date, end_date)

    if "this week" in command_str.lower():
        end_date = today_start + timedelta(days=1)  # Include today
        start_date = today_start - timedelta(days=today_start.weekday())
        return TimeRange(start_date, end_date)

    # Default to last 7 days if no temporal expression found
    return None


def parse_command(command_str: str) -> tuple[CommandType, list, Optional[TimeRange]]:
    """Parse a command string into command type, arguments, and time range"""
    # Single command mapping definition
    cmd_mapping = {
        "review": CommandType.REVIEW,
        "check": CommandType.REVIEW,
        "show": CommandType.REVIEW,
        "config": CommandType.CONFIG,
        "setup": CommandType.CONFIG,
        "configure": CommandType.CONFIG,
        "report": CommandType.REPORT,
        "chart": CommandType.REPORT,
        "help": CommandType.HELP,
        "?": CommandType.HELP,
        "exit": CommandType.EXIT,
        "quit": CommandType.EXIT,
        "q": CommandType.EXIT,
    }

    parts = command_str.strip().split()
    time_range = parse_time_range(command_str)

    if not parts:
        return CommandType.CHAT, [command_str], time_range

    cmd = parts[0].lower()
    args = parts[1:] if len(parts) > 1 else []

    # Check for exact command match
    if cmd in cmd_mapping:
        return cmd_mapping[cmd], args, time_range

    # Check if any command keyword is in the string
    for key, value in cmd_mapping.items():
        if key in command_str.lower():
            if value == CommandType.REVIEW:
                parts = command_str.lower().split(key)
                if len(parts) > 1 and parts[1].strip():
                    return value, [parts[1].strip().split()[0]], time_range
            return value, [], time_range

    # Default to chat with original input
    return CommandType.CHAT, [command_str], time_range


def show_help():
    """Show help information"""
    console = Console()

    console.print(
        Panel(
            """
[bold cyan]Available Commands:[/]

[bold]1. Review Performance[/]
  • [yellow]review[/] - Show metrics for specified time range
    Examples:
    - [dim]"check performance of team frontend"[/dim]
    - [dim]"show metrics for user johndoe"[/dim]
    - [dim]"check performance of the last three days"[/dim]
    - [dim]"how was team backend doing last week"[/dim]

[bold]2. Configuration[/]
  • [yellow]config[/] - Configure integrations
    [bold cyan]GitHub App Installation:[/]
    1. Enter your organization name
    2. Install the Wellcode GitHub App
    3. Select repositories to analyze

    [bold cyan]Optional Integrations:[/]
    - Linear (for issue tracking)
    - Split.io (for feature flags)
    - Anthropic (for AI-powered insights)

[bold]3. Shell Completion[/]
  • [yellow]completion[/] - Enable shell autocompletion
    For bash: [dim]wellcode-cli completion bash >> ~/.bashrc[/dim]
    For zsh:  [dim]wellcode-cli completion zsh >> ~/.zshrc[/dim]
    For fish: [dim]wellcode-cli completion fish > ~/.config/fish/completions/wellcode-cli.fish[/dim]

[bold]4. Reports[/]
  • [yellow]report[/] - Generate detailed HTML reports
    Example: [dim]"generate report for last month"[/dim]

[bold]5. Chat[/]
  • [yellow]chat[/] - Start interactive analysis chat
    Example: [dim]"let's analyze team performance"[/dim]

[bold]6. Exit[/]
  • Type 'exit', 'quit', or 'q' to exit

[bold cyan]Getting Started:[/]
1. Run [yellow]config[/] to set up GitHub App and optional integrations
2. Enable autocompletion with [yellow]completion[/] command
3. Try [yellow]"check performance of team <teamname>"[/] to see team metrics
4. Use [yellow]"help"[/] anytime to see this message

[bold red]Troubleshooting:[/]
• If GitHub metrics are not showing, verify the GitHub App is installed correctly
• For organizations with SAML SSO, ensure the GitHub App is authorized for your organization
• For other integrations, check your API keys in the configuration
""",
            title="Wellcode.ai Help",
            border_style="blue",
        )
    )


console = Console()


@click.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion(shell):
    """Generate shell completion script"""
    completion_scripts = {
        "bash": """
# Wellcode CLI bash completion
eval "$(_WELLCODE_CLI_COMPLETE=bash_source wellcode-cli)"
""",
        "zsh": """
# Wellcode CLI zsh completion
eval "$(_WELLCODE_CLI_COMPLETE=zsh_source wellcode-cli)"
""",
        "fish": """
# Wellcode CLI fish completion
eval (env _WELLCODE_CLI_COMPLETE=fish_source wellcode-cli)
""",
    }

    console.print(
        Panel(
            f"""[bold green]Shell Completion Script for {shell}[/]

To enable completion, add this to your shell configuration:

[yellow]{completion_scripts[shell]}[/]

[bold]Configuration File Locations:[/]
• bash: ~/.bashrc
• zsh:  ~/.zshrc
• fish: ~/.config/fish/completions/wellcode-cli.fish

[bold red]Note:[/] You'll need to restart your shell or source the config file after adding the script.
""",
            title=f"Wellcode.ai {shell.upper()} Completion",
            border_style="blue",
        )
    )
