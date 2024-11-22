import rich_click as click
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.panel import Panel
from datetime import datetime, timedelta
from pathlib import Path
import json
from rich.markdown import Markdown
import plotly.graph_objects as go
import webbrowser
import plotly.io as pio
import statistics

from .github_metrics import get_github_metrics, format_ai_response, get_ai_analysis, display_github_metrics
from .linear_metrics import get_linear_metrics, display_linear_metrics
from .split_metrics import get_split_metrics, display_split_metrics
from .performance_review import generate_performance_review
from wellcode_cli import __version__
from .utils import save_analysis_data, get_latest_analysis
import anthropic
from anthropic import InternalServerError, APIError, RateLimitError

# Configure rich-click
click.USE_RICH_MARKUP = True
click.USE_MARKDOWN = True
click.SHOW_ARGUMENTS = True
click.GROUP_ARGUMENTS_OPTIONS = True
click.STYLE_ERRORS_SUGGESTION = "yellow italic"
click.ERRORS_SUGGESTION = "Try '--help' for more information."

# Initialize rich console
console = Console()

# Define the config file location
CONFIG_DIR = Path.home() / '.wellcode'
CONFIG_FILE = CONFIG_DIR / 'config.json'

def load_config():
    """Load configuration from file."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(config):
    """Save configuration to file."""
    CONFIG_DIR.mkdir(exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def validate_date(ctx, param, value):
    if value is None:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        raise click.BadParameter('Date must be in YYYY-MM-DD format')

@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="wellcode-cli")
@click.pass_context
def cli(ctx):
    """🚀 Wellcode CLI - Engineering Metrics Analysis Tool"""
    if ctx.invoked_subcommand is None:
        # Start interactive mode by default
        ctx.invoke(chat_interface)

@cli.command()
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
    
    def show_help():
        console.print("\n[bold cyan]Available Commands:[/]")
        console.print("• [bold]analyze[/] - Analyze engineering metrics")
        console.print("  Example: 'analyze my team's performance' or 'show metrics for last week'")
        console.print("\n• [bold]config[/] - Configure your settings")
        console.print("  Example: 'setup my workspace' or 'configure integrations'")
        console.print("\n• [bold]report[/] - Generate visual reports")
        console.print("  Example: 'create a report' or 'show me charts of recent metrics'")
        console.print("\n• [bold]review[/] - Generate performance reviews")
        console.print("  Example: 'review john's performance' or 'generate review for username:john'")
        console.print("\n• [bold]exit[/] - Exit the application")
        console.print("\nJust describe what you want to do in natural language!")
    
    def execute_command(cmd_str):
        ctx = click.get_current_context()
        
        # Parse the command string into command and args
        parts = cmd_str.strip().split(' ')
        command = parts[0].lower()
        args = parts[1:]
        
        # Interactive commands should run without the spinner
        if command in ['config', 'help']:
            if command == 'config':
                ctx.invoke(config)
            elif command == 'help':
                show_help()
            return True  # Indicate that command was handled

        # Non-interactive commands can use the spinner
        if command == 'analyze':
            ctx.invoke(analyze)
        elif command == 'report':
            ctx.invoke(report)
        elif command == 'review' and args:
            ctx.invoke(review, github_username=args[0])
        else:
            console.print("[yellow]Invalid command. Type 'help' for available commands.[/]")
        return True

    while True:
        command = Prompt.ask("\n[bold cyan]What would you like to do?[/] (type 'help' for suggestions)")
        
        if command.lower() in ['exit', 'quit', 'q']:
            break
        
        if command.lower() in ['help', '?']:
            show_help()
            continue
            
        if client:
            # Use Claude to interpret the natural language command
            with console.status("[bold green]Processing command..."):
                response = client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=1024,
                    messages=[{
                        "role": "user",
                        "content": f"Convert this natural language request into a Wellcode CLI command: {command}"
                    }],
                    system="""You are a CLI command interpreter. Convert natural language to one of these commands:
                    - analyze
                    - config
                    - report
                    - review <github_username>
                    
                    Respond ONLY with the command string, nothing else. For example:
                    - "show me recent metrics" → "analyze"
                    - "review john's performance" → "review john"
                    - "setup my workspace" → "config"
                    - "generate charts" → "report"
                    
                    If you can't map the request to a command, respond with "help"."""
                )
                
                interpreted_command = response.content[0].text.strip()
            
            # Execute command without spinner for interactive commands
            try:
                execute_command(interpreted_command)
            except Exception as e:
                console.print(f"[red]Error executing command: {str(e)}[/]")
        else:
            # Basic command matching without AI
            if 'help' in command.lower():
                show_help()
            elif 'config' in command.lower():
                execute_command('config')
            elif 'analyze' in command.lower():
                with console.status("[bold green]Processing..."): 
                    execute_command('analyze')
            elif 'report' in command.lower():
                with console.status("[bold green]Processing..."): 
                    execute_command('report')
            elif 'review' in command.lower():
                console.print("[yellow]Please use 'review <github_username>' for performance reviews[/]")
            else:
                console.print("[yellow]Available commands: analyze, config, report, review[/]")

@cli.command()
def config():
    """Configure your Wellcode CLI settings"""
    console.print("[bold blue]Wellcode CLI Configuration[/]")
    console.print("Let's set up your integrations.\n")
    
    console.print("[bold cyan]GitHub Token Requirements:[/]")
    console.print("Your token needs these minimum scopes:")
    console.print("• repo         - For accessing PR data and repository information")
    console.print("• read:org     - For accessing organization repositories")
    console.print("• read:user    - For reading user information in PRs")
    console.print("\nGenerate token at: https://github.com/settings/tokens\n")
    
    config_data = load_config()
    
    # GitHub Configuration
    if Confirm.ask("[bold cyan]Do you want to configure GitHub integration?[/]"):
        github_token = Prompt.ask(
            "[cyan]Enter your GitHub token[/]",
            password=True,
            default=config_data.get('GITHUB_TOKEN', '')
        )
        github_org = Prompt.ask(
            "[cyan]Enter your GitHub organization[/]",
            default=config_data.get('GITHUB_ORG', '')
        )
        config_data.update({
            'GITHUB_TOKEN': github_token,
            'GITHUB_ORG': github_org
        })
    
    # Linear Configuration
    if Confirm.ask("\n[bold cyan]Do you want to configure Linear integration?[/]"):
        linear_key = Prompt.ask(
            "[cyan]Enter your Linear API key[/]",
            password=True,
            default=config_data.get('LINEAR_API_KEY', '')
        )
        config_data['LINEAR_API_KEY'] = linear_key
    
    # Split.io Configuration 
    if Confirm.ask("\n[bold cyan]Do you want to configure Split.io integration?[/]"):
        split_key = Prompt.ask(
            "[cyan]Enter your Split.io API key[/]",
            password=True,
            default=config_data.get('SPLIT_API_KEY', '')
        )
        config_data['SPLIT_API_KEY'] = split_key
    
    # Anthropic Configuration
    if Confirm.ask("\n[bold cyan]Do you want to configure AI analysis (using Anthropic)?[/]"):
        anthropic_key = Prompt.ask(
            "[cyan]Enter your Anthropic API key[/]",
            password=True,
            default=config_data.get('ANTHROPIC_API_KEY', '')
        )
        config_data['ANTHROPIC_API_KEY'] = anthropic_key
    
    # Save configuration
    save_config(config_data)
    console.print("\n[bold green]Configuration saved successfully! ✨[/]")

@cli.command()
@click.option('--start-date', '-s', type=click.DateTime(), help='Start date for analysis (YYYY-MM-DD)')
@click.option('--end-date', '-e', type=click.DateTime(), help='End date for analysis (YYYY-MM-DD)')
@click.option('--user', '-u', help='Filter by GitHub username')
@click.option('--team', '-t', help='Filter by GitHub team name')
def analyze(start_date, end_date, user, team):
    """Analyze engineering metrics"""
    # Handle end date
    if end_date is None:
        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        # Strip time information to work with whole days
        end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # Handle start date
    if start_date is None:
        # Only calculate default if no start date provided
        start_date = end_date - timedelta(days=5)
    
    # Ensure we're working with start of day
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    console.print(f"\n📅 Analyzing metrics from {start_date.date()} to {end_date.date()}")
    
    # Check if config exists
    if not CONFIG_FILE.exists():
        console.print("[yellow]No configuration found. Running initial setup...[/]\n")
        config()
        console.print()  # Add a blank line for spacing
    
    # Load configuration
    config_data = load_config()
    
    console.print(Panel.fit(
        "[bold blue]Wellcode.ai[/] - Engineering Metrics Analysis",
        subtitle=f"v{__version__}",
        border_style="blue"
    ))

    if user:
        console.print(f"👤 Filtering by user: [yellow]{user}[/]")

    all_metrics = {}
    analysis_result = None

    with console.status("[bold green]Fetching metrics...") as status:
        # GitHub metrics
        if config_data.get('GITHUB_TOKEN'):
            status.update("Fetching GitHub metrics...")
            metrics = get_github_metrics(config_data['GITHUB_ORG'], start_date, end_date, user, team)
            all_metrics['github'] = metrics
            display_github_metrics(metrics)
        else:
            console.print("[yellow]⚠️  GitHub integration not configured[/]")

        # Linear metrics
        if config_data.get('LINEAR_API_KEY'):
            status.update("Fetching Linear metrics...")
            linear_metrics = get_linear_metrics(start_date, end_date, user)
            all_metrics['linear'] = linear_metrics
            display_linear_metrics(linear_metrics)
        else:
            console.print("[yellow]⚠️  Linear integration not configured[/]")

        # Split metrics
        if config_data.get('SPLIT_API_KEY'):
            status.update("Fetching Split metrics...")
            split_metrics = get_split_metrics(start_date, end_date)
            all_metrics['split'] = split_metrics
            display_split_metrics(split_metrics)
        else:
            console.print("[yellow]⚠️  Split.io integration not configured[/]")

        # AI Analysis
        if config_data.get('ANTHROPIC_API_KEY'):
            try:
                status.update("Generating AI analysis...")
                analysis_result = get_ai_analysis(all_metrics)
                console.print("\n[bold cyan]AI Analysis:[/]")
                format_ai_response(analysis_result)
            except InternalServerError as e:
                if "overloaded_error" in str(e):
                    console.print("\n[yellow]⚠️  Claude is currently overloaded. Analysis will continue without AI insights.[/]")
                else:
                    console.print("\n[yellow]⚠️  Claude encountered an internal error. Analysis will continue without AI insights.[/]")
                console.print("[dim]Error details: " + str(e) + "[/dim]")
            except RateLimitError:
                console.print("\n[yellow]⚠️  API rate limit reached. Analysis will continue without AI insights.[/]")
            except APIError as e:
                console.print(f"\n[yellow]⚠️  API error occurred: {str(e)}[/]")
                console.print("Analysis will continue without AI insights.")
            except Exception as e:
                console.print(f"\n[red]Unexpected error during AI analysis: {str(e)}[/]")
                console.print("Analysis will continue without AI insights.")
        else:
            console.print("[yellow]⚠️  AI analysis not configured[/]")

    # Save the analysis data
    temp_file = save_analysis_data(all_metrics, analysis_result)
    console.print(f"\n[dim]Analysis saved to: {temp_file}[/]")

@cli.command()
def chat():
    """Interactive chat about your engineering metrics"""
    # Get the latest analysis data
    data = get_latest_analysis()
    if not data:
        console.print("[yellow]No recent analysis found. Running new analysis...[/]\n")
        ctx = click.get_current_context()
        ctx.invoke(analyze)
        data = get_latest_analysis()
    
    # Load configuration
    config_data = load_config()
    if not config_data.get('ANTHROPIC_API_KEY'):
        console.print("[red]Error: Anthropic API key not configured. Please run 'wellcode-cli config'[/]")
        return

    client = anthropic.Client(api_key=config_data['ANTHROPIC_API_KEY'])
    
    console.print("[bold blue]Wellcode AI Chat[/]")
    console.print("Ask questions about your engineering metrics. Type 'exit' to quit.\n")

    # Initialize system prompt
    system_prompt = f"""You are an engineering metrics analyst. You have access to the following data:

<metrics>
{data['metrics']}
</metrics>

You also have access to a previous analysis:

<previous_analysis>
{data['analysis']}
</previous_analysis>

Your task is to answer questions about this data in a clear, concise way. Follow these guidelines:

1. Use specific numbers and metrics when relevant to support your answers.
2. When asked about trends or patterns, refer to the actual data points provided in the metrics.
3. If asked for recommendations, base them on the specific metrics and context provided in both the metrics and previous analysis.
4. Ensure your answers are directly related to the engineering metrics and context provided.
5. If the question cannot be answered based on the given information, state this clearly and explain why.

Before providing your final answer, use a <scratchpad> to organize your thoughts and identify relevant data points. This will help you structure a comprehensive response.

Format your response as follows:
1. <scratchpad> (for your thought process)
2. <answer> (for your final, polished response)


Please provide your analysis and answer based on the given metrics and previous analysis."""

    # Initialize conversation history
    messages = []

    while True:
        # Get user input
        question = Prompt.ask("\n[cyan]What would you like to know about your metrics?[/]")
        
        if question.lower() in ['exit', 'quit', 'q']:
            break

        with console.status("[bold green]Thinking..."):
            # Add user question to messages
            messages.append({"role": "user", "content": question})
            
            # Get response from Claude
            response = client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2048,
                messages=messages,
                system=system_prompt
            )
            
            # Add assistant response to messages
            assistant_message = response.content[0].text
            messages.append({"role": "assistant", "content": assistant_message})

        # Display response with markdown formatting
        console.print("\n[bold green]Answer:[/]")
        console.print(Markdown(assistant_message))

def generate_html_content(charts):
    """Generate HTML content with all charts"""
    html_template = '''
    <!DOCTYPE html>
    <html>
        <head>
            <title>Engineering Metrics Report</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    background-color: #f5f5f5;
                }}
                .chart-container {{
                    background-color: white;
                    padding: 20px;
                    margin: 20px 0;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #333;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <h1>Engineering Metrics Report</h1>
            <div class="charts">
                {charts}
            </div>
        </body>
    </html>
    '''
    
    charts_html = ""
    for i, chart in enumerate(charts):
        charts_html += f'<div class="chart-container">{pio.to_html(chart, full_html=False)}</div>'
    
    return html_template.format(charts=charts_html)

@cli.command()
@click.option('--output', '-o', help="Output directory for the report", type=click.Path())
@click.option('--format', '-f', type=click.Choice(['html', 'pdf']), default='html', help="Report format")
def report(output, format):
    """Generate a visual report of engineering metrics"""
    try:
        data = get_latest_analysis()
        if not data:
            console.print("[red]No analysis data found. Please run 'analyze' first.[/]")
            return

        metrics = data.get('metrics', {})
        github_metrics = metrics.get('github', {})
        linear_metrics = metrics.get('linear', {})
        split_metrics = metrics.get('split', {})
        
        # Debug print
        console.print("[yellow]Available metrics:[/]")
        console.print(f"GitHub metrics: {github_metrics.keys()}")
        console.print(f"Linear metrics: {linear_metrics.keys()}")
        console.print(f"Split metrics: {split_metrics.keys()}")

        # Create output directory
        output_dir = Path(output) if output else Path.cwd() / 'reports'
        output_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"Output directory: {output_dir}")

        charts = []

        # GitHub Metrics Charts
        if github_metrics:
            # PR Summary Bar Chart
            if all(key in github_metrics for key in ['prs_created', 'prs_merged', 'prs_merged_to_main']):
                pr_summary = go.Figure(data=[
                    go.Bar(
                        x=['PRs Created', 'PRs Merged', 'PRs Merged to Main'],
                        y=[
                            github_metrics['prs_created'],
                            github_metrics['prs_merged'],
                            github_metrics['prs_merged_to_main']
                        ],
                        marker_color=['#6366F1', '#EC4899', '#10B981']
                    )
                ])
                pr_summary.update_layout(
                    title='Pull Request Summary',
                    yaxis_title='Count',
                    plot_bgcolor='#F3F4F6',
                    paper_bgcolor='#F3F4F6'
                )
                charts.append(pr_summary)

            # Comments Distribution
            if 'comments_per_pr' in github_metrics:
                comments_values = list(github_metrics['comments_per_pr'].values())
                if comments_values:
                    comments_dist = go.Figure(data=[
                        go.Histogram(
                            x=comments_values,
                            nbinsx=20,
                            name='Comments Distribution',
                            marker_color='#6366F1'
                        )
                    ])
                    comments_dist.update_layout(
                        title='PR Comments Distribution',
                        xaxis_title='Number of Comments',
                        yaxis_title='Frequency',
                        plot_bgcolor='#F3F4F6',
                        paper_bgcolor='#F3F4F6'
                    )
                    charts.append(comments_dist)

            # Time to Merge Distribution
            if 'time_to_merge' in github_metrics and github_metrics['time_to_merge']:
                merge_dist = go.Figure(data=[
                    go.Histogram(
                        x=github_metrics['time_to_merge'],
                        nbinsx=20,
                        name='Time to Merge Distribution',
                        marker_color='#EC4899'
                    )
                ])
                merge_dist.update_layout(
                    title='Time to Merge Distribution',
                    xaxis_title='Hours',
                    yaxis_title='Frequency',
                    plot_bgcolor='#F3F4F6',
                    paper_bgcolor='#F3F4F6'
                )
                charts.append(merge_dist)

            # User Contributions
            if 'user_contributions' in github_metrics:
                user_data = github_metrics['user_contributions']
                if user_data:
                    users = list(user_data.keys())
                    created = [user_data[user]['created'] for user in users]
                    merged = [user_data[user]['merged'] for user in users]

                    user_fig = go.Figure(data=[
                        go.Bar(name='Created', x=users, y=created, marker_color='#6366F1'),
                        go.Bar(name='Merged', x=users, y=merged, marker_color='#EC4899')
                    ])
                    user_fig.update_layout(
                        title='User Contributions',
                        barmode='group',
                        xaxis_title='Users',
                        yaxis_title='Count',
                        plot_bgcolor='#F3F4F6',
                        paper_bgcolor='#F3F4F6'
                    )
                    charts.append(user_fig)

            # DORA Metrics Charts
            if github_metrics:
                # Deployment Frequency
                if 'deployment_frequency' in github_metrics:
                    deploy_freq = go.Figure(data=[
                        go.Indicator(
                            mode="gauge+number",
                            value=github_metrics['deployment_frequency'],
                            title={'text': "Deployments per Day"},
                            gauge={
                                'axis': {'range': [None, 10]},
                                'steps': [
                                    {'range': [0, 1], 'color': "lightgray"},
                                    {'range': [1, 3], 'color': "gray"}
                                ],
                                'threshold': {
                                    'line': {'color': "red", 'width': 4},
                                    'thickness': 0.75,
                                    'value': 3
                                }
                            }
                        )
                    ])
                    deploy_freq.update_layout(
                        title='Deployment Frequency',
                        height=400,
                        plot_bgcolor='#F3F4F6',
                        paper_bgcolor='#F3F4F6'
                    )
                    charts.append(deploy_freq)

                # Lead Time for Changes
                if 'lead_times' in github_metrics and github_metrics['lead_times']:
                    lead_times = github_metrics['lead_times']
                    lead_time_dist = go.Figure(data=[
                        go.Histogram(
                            x=lead_times,
                            nbinsx=20,
                            name='Lead Time Distribution',
                            marker_color='#10B981'
                        )
                    ])
                    lead_time_dist.update_layout(
                        title='Lead Time for Changes',
                        xaxis_title='Hours',
                        yaxis_title='Frequency',
                        plot_bgcolor='#F3F4F6',
                        paper_bgcolor='#F3F4F6'
                    )
                    charts.append(lead_time_dist)

                # DORA Metrics Summary
                dora_summary = go.Figure(data=[
                    go.Bar(
                        x=['Deployment Frequency', 'Median Lead Time', 'Avg Time to Merge'],
                        y=[
                            github_metrics.get('deployment_frequency', 0),
                            github_metrics.get('median_lead_time', 0),
                            github_metrics.get('avg_time_to_merge', 0)
                        ],
                        marker_color=['#6366F1', '#EC4899', '#10B981']
                    )
                ])
                dora_summary.update_layout(
                    title='DORA Metrics Summary',
                    yaxis_title='Hours/Count',
                    plot_bgcolor='#F3F4F6',
                    paper_bgcolor='#F3F4F6'
                )
                charts.append(dora_summary)

                # Code Quality Metrics
                if 'code_quality' in github_metrics:
                    code_quality = github_metrics['code_quality']
                    quality_metrics = go.Figure(data=[
                        go.Bar(
                            x=['Avg Changes/PR', 'Avg Files/PR', 'Hotfixes', 'Reverts'],
                            y=[
                                statistics.mean(code_quality['changes_per_pr']) if code_quality['changes_per_pr'] else 0,
                                statistics.mean(code_quality['files_changed_per_pr']) if code_quality['files_changed_per_pr'] else 0,
                                code_quality.get('hotfix_count', 0),
                                code_quality.get('revert_count', 0)
                            ],
                            marker_color=['#6366F1', '#EC4899', '#F59E0B', '#EF4444']
                        )
                    ])
                    quality_metrics.update_layout(
                        title='Code Quality Metrics',
                        yaxis_title='Count',
                        plot_bgcolor='#F3F4F6',
                        paper_bgcolor='#F3F4F6'
                    )
                    charts.append(quality_metrics)

                # Review Process Metrics
                if 'review_metrics' in github_metrics:
                    review_metrics = github_metrics['review_metrics']
                    if review_metrics.get('time_to_first_review'):
                        review_time_dist = go.Figure(data=[
                            go.Histogram(
                                x=review_metrics['time_to_first_review'],
                                nbinsx=20,
                                name='Time to First Review',
                                marker_color='#8B5CF6'
                            )
                        ])
                        review_time_dist.update_layout(
                            title='Time to First Review Distribution',
                            xaxis_title='Hours',
                            yaxis_title='Frequency',
                            plot_bgcolor='#F3F4F6',
                            paper_bgcolor='#F3F4F6'
                        )
                        charts.append(review_time_dist)

                # Bottleneck Metrics
                if 'bottleneck_metrics' in github_metrics:
                    bottleneck = github_metrics['bottleneck_metrics']
                    bottleneck_summary = go.Figure(data=[
                        go.Bar(
                            x=['Stale PRs', 'Long-Running PRs'],
                            y=[
                                bottleneck.get('stale_prs', 0),
                                bottleneck.get('long_running_prs', 0)
                            ],
                            marker_color=['#F59E0B', '#EF4444']
                        )
                    ])
                    bottleneck_summary.update_layout(
                        title='Process Bottlenecks',
                        yaxis_title='Count',
                        plot_bgcolor='#F3F4F6',
                        paper_bgcolor='#F3F4F6'
                    )
                    charts.append(bottleneck_summary)

        # Linear Metrics Charts
        if linear_metrics:
            # Issue Summary
            if all(key in linear_metrics for key in ['issues_created', 'issues_completed']):
                issue_summary = go.Figure(data=[
                    go.Bar(
                        x=['Issues Created', 'Issues Completed'],
                        y=[
                            linear_metrics['issues_created'],
                            linear_metrics['issues_completed']
                        ],
                        marker_color=['#6366F1', '#10B981']
                    )
                ])
                issue_summary.update_layout(
                    title='Issue Summary',
                    yaxis_title='Count',
                    plot_bgcolor='#F3F4F6',
                    paper_bgcolor='#F3F4F6'
                )
                charts.append(issue_summary)

        # Split Metrics Charts
        if split_metrics:
            # Feature Flags Overview
            splits_overview = go.Figure(data=[
                go.Bar(
                    x=['Total', 'Active'],
                    y=[
                        split_metrics.get('total_splits', 0),
                        split_metrics.get('active_splits', 0)
                    ],
                    marker_color='#F59E0B'
                )
            ])
            splits_overview.update_layout(
                title='Feature Flags Overview',
                yaxis_title='Count',
                plot_bgcolor='#F3F4F6',
                paper_bgcolor='#F3F4F6'
            )
            charts.append(splits_overview)

        # Generate HTML report
        if charts:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_file = output_dir / f'engineering_report_{timestamp}.html'
            
            html_content = generate_html_content(charts)
            
            with open(report_file, 'w') as f:
                f.write(html_content)
            
            console.print(f"\n[bold green]Report generated: {report_file}[/]")
            
            try:
                webbrowser.open(f'file://{report_file}')
            except Exception as e:
                console.print(f"[yellow]Could not open report automatically: {e}[/]")
            
            return report_file
        else:
            console.print("[yellow]No data available to generate charts[/]")
            return None

    except Exception as e:
        console.print(f"[red]Error generating report: {str(e)}[/]")
        raise

@cli.command()
@click.argument('github_username')
@click.option('--linear-username', '-l', help='Linear username (if different from GitHub username)')
@click.option('--days', '-d', default=30, help='Number of days to analyze')
def review(github_username, linear_username, days):
    """Generate a performance review for a specific user
    
    GITHUB_USERNAME: GitHub username of the person to review
    """
    config_data = load_config()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    console.print(Panel.fit(
        "[bold blue]Wellcode.ai[/] - Performance Review Generator",
        subtitle=f"v{__version__}",
        border_style="blue"
    ))
    
    with console.status("[bold green]Gathering metrics...") as status:
        status.update("Fetching GitHub metrics...")
        github_metrics = get_github_metrics(config_data['GITHUB_ORG'], start_date, end_date, user_filter=github_username)
        
        status.update("Fetching Linear metrics...")
        linear_metrics = get_linear_metrics(start_date, end_date, user_filter=linear_username or github_username)
        
        status.update("Generating review...")
        generate_performance_review(github_metrics, linear_metrics, github_username, linear_username)

def main():
    cli()

if __name__ == "__main__":
    main()