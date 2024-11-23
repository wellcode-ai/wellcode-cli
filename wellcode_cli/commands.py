from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from dataclasses import dataclass

class CommandType(Enum):
    ANALYZE = "analyze"
    CONFIG = "config"
    REPORT = "report"
    REVIEW = "review"
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
    CommandType.ANALYZE: Command(
        type=CommandType.ANALYZE,
        description="Analyze engineering metrics",
        examples=[
            "analyze my team's performance",
            "show metrics for last week",
            "analyze pull requests",
        ]
    ),
    CommandType.CONFIG: Command(
        type=CommandType.CONFIG,
        description="Configure your settings",
        examples=[
            "setup my workspace",
            "configure integrations",
            "setup github token"
        ]
    ),
    CommandType.REPORT: Command(
        type=CommandType.REPORT,
        description="Generate visual reports",
        examples=[
            "create a report",
            "show me charts",
            "generate metrics visualization"
        ]
    ),
    CommandType.CHAT: Command(
        type=CommandType.CHAT,
        description="Start interactive chat mode",
        examples=[
            "start chat",
            "chat mode",
            "interactive mode"
        ]
    ),
    CommandType.HELP: Command(
        type=CommandType.HELP,
        description="Show available commands and examples",
        examples=["help", "?"]
    )
}

def get_claude_system_prompt():
    today = datetime.now(timezone.utc)
    yesterday = (today - timedelta(days=1)).strftime('%Y-%m-%d')
    today = today.strftime('%Y-%m-%d')
    
    return f"""You are a CLI command interpreter for the Wellcode engineering metrics tool. Convert natural language input into specific commands.

Today's date is {today}.

Available Commands and Options:
1. analyze
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
- "analyze team performance" → "analyze --team frontend"
- "show metrics for last week" → "analyze --start-date 2024-03-20 --end-date 2024-03-27"
- "how was pimouss yesterday" → "analyze --user pimouss --start-date {yesterday} --end-date {today}"
- "generate report" → "report --format html"
- "save report to desktop" → "report --output ~/Desktop --format html"
- "setup integrations" → "config"
- "start chat" → "chat"
- "what can I do?" → "help"
- "quit" → "exit"

Rules for Command Interpretation:
1. Time-based queries:
   - "yesterday" → calculate proper date
   - "last week" → calculate 7 days ago
   - "this month" → first day of current month
   - "today" → current date
   - Always convert to YYYY-MM-DD format

2. User queries:
   - "how was <user>" → analyze --user <user>
   - "<user>'s performance" → analyze --user <user>

3. Team queries:
   - "team <name>" → analyze --team <name>
   - "<team> performance" → analyze --team <name>

4. Report queries:
   - "generate report" → report with default options
   - "save report to <path>" → report --output <path>
   - Specify format with "pdf" or "html" keywords

Important:
- Output ONLY the command string with appropriate options
- Convert relative dates to actual YYYY-MM-DD format
- Include appropriate flags (--user, --team, --start-date, --end-date)
- Default to "help" if the intent is unclear

Example Inputs and Outputs:
- "how was pimouss yesterday" → "analyze --user pimouss --start-date {yesterday} --end-date {today}"
- "show team frontend metrics for last week" → "analyze --team frontend --start-date {(datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')} --end-date {today}"
- "generate html report" → "report --format html"
- "setup my workspace" → "config"
- "let's chat about metrics" → "chat"

Remember: Respond with ONLY the command and its options, nothing else."""

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
    cmd_mapping = {
        'analyze': CommandType.ANALYZE,
        'check': CommandType.ANALYZE,
        'show': CommandType.ANALYZE,
        'config': CommandType.CONFIG,
        'setup': CommandType.CONFIG,
        'configure': CommandType.CONFIG,
        'report': CommandType.REPORT,
        'chart': CommandType.REPORT,
        'review': CommandType.REVIEW,
        'chat': CommandType.CHAT,
        'interactive': CommandType.CHAT,
        'help': CommandType.HELP,
        '?': CommandType.HELP,
        'exit': CommandType.EXIT,
        'quit': CommandType.EXIT,
        'q': CommandType.EXIT
    }
    
    parts = command_str.strip().split()
    if not parts:
        return CommandType.HELP, [], None
    
    # If the command is already formatted (contains --), parse it directly
    if any(arg.startswith('--') for arg in parts):
        cmd = parts[0].lower()
        if cmd in cmd_mapping:
            return cmd_mapping[cmd], parts[1:], parse_time_range(command_str)
    
    # Rest of the existing parsing logic...
    cmd = parts[0].lower()
    args = parts[1:] if len(parts) > 1 else []
    time_range = parse_time_range(command_str)
    
    # Map common variations to commands
    cmd_mapping = {
        'analyze': CommandType.ANALYZE,
        'check': CommandType.ANALYZE,
        'show': CommandType.ANALYZE,
        'config': CommandType.CONFIG,
        'setup': CommandType.CONFIG,
        'configure': CommandType.CONFIG,
        'report': CommandType.REPORT,
        'chart': CommandType.REPORT,
        'review': CommandType.REVIEW,
        'chat': CommandType.CHAT,
        'interactive': CommandType.CHAT,
        'help': CommandType.HELP,
        '?': CommandType.HELP,
        'exit': CommandType.EXIT,
        'quit': CommandType.EXIT,
        'q': CommandType.EXIT
    }
    
    try:
        # Try direct mapping first
        if cmd in cmd_mapping:
            return cmd_mapping[cmd], args, time_range
            
        # Try to find command in the full string for natural language
        for key, value in cmd_mapping.items():
            if key in command_str.lower():
                # For review commands, try to extract username
                if value == CommandType.REVIEW:
                    # Look for username after "review" or at the end
                    parts = command_str.lower().split(key)
                    if len(parts) > 1 and parts[1].strip():
                        return value, [parts[1].strip().split()[0]], time_range
                return value, [], time_range
                
        return CommandType.HELP, [], time_range
    except (ValueError, IndexError):
        return CommandType.HELP, [], time_range

def show_help():
    """Display help information about available commands"""
    from rich.console import Console
    console = Console()
    
    console.print("\n[bold cyan]Available Commands:[/]")
    for cmd in COMMANDS.values():
        console.print(f"\n• [bold]{cmd.type.value}[/] - {cmd.description}")
        console.print("  Examples:")
        for example in cmd.examples:
            console.print(f"  - {example}")
