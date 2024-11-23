import rich_click as click
from rich.console import Console
from rich.prompt import Prompt
from .config import load_config,config
from .. import __version__
import anthropic
from rich.panel import Panel
from pathlib import Path
from .commands import show_help
from .commands import get_claude_system_prompt
from .commands import parse_command
from .commands import CommandType
from datetime import datetime, timedelta
from .review import review
from .report import report
from .chat import chat

console = Console()
CONFIG_FILE = Path.home() / '.wellcode' / 'config.json'

@click.command()
def chat_interface():
    """Interactive chat interface for Wellcode"""
    config_data = load_config()
    
    if not CONFIG_FILE.exists():
        console.print("[yellow]First time setup detected. Let's configure your workspace.[/]\n")
        config()
    
    console.print(Panel.fit(
        "[bold blue]Wellcode.ai[/] - Interactive Mode",
        subtitle=f"v{__version__}",
        border_style="blue"
    ))
    
    # Initialize Anthropic client if configured
    client = None
    if config_data.get('ANTHROPIC_API_KEY'):
        client = anthropic.Client(api_key=config_data['ANTHROPIC_API_KEY'])
    
    while True:
        try:
            command = Prompt.ask("\n[bold cyan]What would you like to do?[/] (type 'help' for suggestions)")
            
            if command.lower() in ['exit', 'quit', 'q']:
                break
            
            if command.lower() in ['help', '?']:
                show_help()
                continue
                
            if client:
                # Use Claude to interpret the natural language command
                try:
                    response = client.messages.create(
                        model="claude-3-sonnet-20240229",
                        max_tokens=1024,
                        messages=[{
                            "role": "user",
                            "content": f"Convert this natural language request into a Wellcode CLI command: {command}"
                        }],
                        system=get_claude_system_prompt()
                    )
                    
                    interpreted_command = response.content[0].text.strip()
                    console.print(f"Original command: '{command}' → Interpreted as: '{interpreted_command}'")
                    console.print(f"[dim]Interpreting as: {interpreted_command}[/dim]")
                    
                    if interpreted_command:
                        execute_command(interpreted_command)
                    else:
                        console.print("[yellow]I couldn't understand that request. Try rephrasing or type 'help' for suggestions.[/]")
                        
                except Exception as e:
                    console.print(f"[red]Error processing command: {str(e)}[/]")
            else:
                # Basic command parsing without AI
                execute_command(command)
                
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/]")


def execute_command(command_str: str) -> bool:
    """Execute a parsed command."""
    try:
        command_type, args, time_range = parse_command(command_str)
        ctx = click.get_current_context()
        
        if command_type == CommandType.REVIEW:
            # Parse dates and user from the command string
            date_args = {}
            for arg in args:
                if '=' in arg:
                    key, value = arg.split('=', 1)
                    date_args[key] = value
            
            # Parse dates exactly as provided by Claude
            if '--start-date' in date_args and '--end-date' in date_args:
                start_date = datetime.strptime(date_args['--start-date'], '%Y-%m-%d')
                end_date = datetime.strptime(date_args['--end-date'], '%Y-%m-%d')
                
                # Ensure end date includes the full day
                end_date = end_date.replace(hour=23, minute=59, second=59)
                # Ensure start date starts at beginning of day
                start_date = start_date.replace(hour=0, minute=0, second=0)
            else:
                # Default to last 7 days if no dates provided
                end_date = datetime.now()
                start_date = end_date - timedelta(days=7)
            
            user = next((args[i+1] for i, arg in enumerate(args) if arg in ['--user', '-u']), None)
            
            ctx.invoke(review, start_date=start_date, end_date=end_date, user=user, team=None)
        elif command_type == CommandType.CONFIG:
            ctx.invoke(config)
        elif command_type == CommandType.HELP:
            show_help()
        elif command_type == CommandType.CHAT:
            ctx.invoke(chat, initial_question=args[0] if args else None)
            return False  # Return to main prompt after chat completes
        elif command_type == CommandType.REPORT:
            ctx.invoke(report)
        else:
            console.print("[yellow]Invalid command. Type 'help' for available commands.[/]")
            return False
        return True
        
    except Exception as e:
        console.print(f"[red]Error executing command: {str(e)}[/]")
        return False
    

