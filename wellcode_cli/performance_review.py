from rich.table import Table
from rich.panel import Panel
from rich.console import Console
from datetime import datetime, timedelta
from anthropic import Anthropic
from textwrap import fill
# Import configuration
try:
    from .config import ANTHROPIC_API_KEY 
except ImportError: 
    raise ImportError("Failed to import configuration. Ensure config.py exists and is properly set up.")


console = Console()


client = Anthropic(
    # This is the default and can be omitted
    api_key=ANTHROPIC_API_KEY,
)
def format_ai_response(response):
    """Format AI response with proper Rich formatting"""
    if not response:
        return
        
    try:
        # Handle string response from Claude
        text = str(response)
        
        # Split into sections and format
        sections = text.split('\n\n')
        
        for section in sections:
            if not section.strip():
                continue
                
            # Format section titles (numbered sections)
            if section.startswith(('1.', '2.', '3.', '4.')):
                title, content = section.split(':', 1)
                console.print(f"\n[bold cyan]{title.strip()}:[/]")
                
                # Format the content
                lines = content.strip().split('\n')
                for line in lines:
                    line = line.strip()
                    if line.startswith('-'):
                        # Format bullet points
                        console.print(f"  [cyan]•[/] {line[1:].strip()}")
                    else:
                        # Format regular text with proper wrapping
                        wrapped_text = fill(line, width=100)
                        console.print(wrapped_text)
            else:
                # Handle non-sectioned text
                console.print(section.strip())
                
    except Exception as e:
        console.print(f"\n[yellow]Using simplified formatting: {str(e)}[/]")
        try:
            console.print(str(response).replace('\n\n', '\n'))
        except:
            console.print("[red]Error: Unable to display AI response[/]")

def generate_performance_review(github_metrics, linear_metrics, github_username, linear_username=None):
    """Generate a comprehensive performance review for a specific user"""
    
    linear_username = linear_username or github_username
    
    # Initialize metrics variables with defaults
    user_stats = {'created': 0, 'merged': 0}
    user_stats_linear = {'completed': 0}
    avg_changes = 0
    reviews_given = 0

    # Calculate review period
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    period = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"

    console.print(Panel.fit(
        "[bold blue]Performance Review[/]",
        subtitle=f"GitHub: {github_username}",
        border_style="blue"
    ))

    # 1. Code Contributions Section (GitHub)
    console.print("\n[bold magenta]1. Code Contributions (GitHub)[/]")
    code_table = Table(show_header=True, header_style="bold magenta")
    code_table.add_column("Metric", style="cyan")
    code_table.add_column("Value", justify="right")
    
    if github_metrics and 'user_contributions' in github_metrics:
        user_stats = github_metrics['user_contributions'].get(github_username, {'created': 0, 'merged': 0})
        code_table.add_row("Pull Requests Created", str(user_stats.get('created', 0)))
        code_table.add_row("Pull Requests Merged", str(user_stats.get('merged', 0)))
        
        # Calculate PR size and complexity metrics
        if 'code_quality' in github_metrics:
            changes_per_pr = github_metrics['code_quality'].get('changes_per_pr', [])
            if changes_per_pr:
                avg_changes = sum(changes_per_pr) / len(changes_per_pr)
                code_table.add_row("Average PR Size", f"{avg_changes:.0f} lines")
    
    console.print(code_table)

    # 2. Project Delivery Section (Linear)
    console.print("\n[bold magenta]2. Project Delivery (Linear)[/]")
    delivery_table = Table(show_header=True, header_style="bold magenta")
    delivery_table.add_column("Metric", style="cyan")
    delivery_table.add_column("Value", justify="right")
    
    if linear_metrics and 'user_contributions' in linear_metrics:
        user_stats_linear = linear_metrics['user_contributions'].get(linear_username, {'completed': 0})
        delivery_table.add_row("Issues Completed", str(user_stats_linear.get('completed', 0)))
        
        # Add estimation accuracy if available
        if 'estimation_accuracy' in linear_metrics:
            accuracy = linear_metrics['estimation_accuracy'].get('accurate_estimates', 0)
            total = linear_metrics['estimation_accuracy'].get('total_estimated', 0)
            if total > 0:
                delivery_table.add_row(
                    "Estimation Accuracy",
                    f"{(accuracy/total)*100:.1f}%"
                )
    
    console.print(delivery_table)

    # 3. Collaboration & Code Review Section
    console.print("\n[bold magenta]3. Collaboration & Code Review[/]")
    collab_table = Table(show_header=True, header_style="bold magenta")
    collab_table.add_column("Metric", style="cyan")
    collab_table.add_column("Value", justify="right")
    
    # Initialize with zero values
    reviews_given = 0
    review_comments = 0
    
    if github_metrics and 'review_metrics' in github_metrics:
        review_stats = github_metrics.get('review_metrics', {})
        
        # Count reviews given
        reviewers_per_pr = review_stats.get('reviewers_per_pr', {})
        if github_username in reviewers_per_pr:
            reviews_given = len(reviewers_per_pr[github_username])
            collab_table.add_row("Reviews Provided", str(reviews_given))
            
        # Count review comments
        review_comments_per_pr = review_stats.get('review_comments_per_pr', {})
        if github_username in review_comments_per_pr:
            review_comments = len(review_comments_per_pr[github_username])
            collab_table.add_row("Review Comments", str(review_comments))
            
        # Add average review time if available
        review_time = review_stats.get('average_review_time', {}).get(github_username)
        if review_time:
            collab_table.add_row("Avg. Review Time", f"{review_time:.1f} hours")
    
    # Only print the table if we have data
    if reviews_given > 0 or review_comments > 0:
        console.print(collab_table)
    else:
        console.print("[dim]No code review activity in this period[/]")

    # 4. AI Analysis Section
    console.print("\n[bold magenta]4. AI Analysis & Recommendations[/]")
    
    analysis_prompt = f"""
    Based on the following metrics for GitHub user '{github_username}' over the last 30 days:

    Code Contributions (GitHub):
    - Created {user_stats.get('created', 0)} Pull Requests
    - Merged {user_stats.get('merged', 0)} Pull Requests
    - Average PR size: {avg_changes:.0f} lines

    Project Delivery (Linear):
    - Completed {user_stats_linear.get('completed', 0)} issues
    - Provided {reviews_given} code reviews

    Please provide:
    1. A brief assessment of their performance and impact
    2. 3 specific strengths demonstrated by these metrics
    3. 2 potential areas for improvement
    4. Concrete suggestions for professional growth in the next quarter
    
    Format the response in a constructive and encouraging tone, focusing on both achievements and growth opportunities.
    Keep each section concise and actionable.
    """
    
    with console.status("[bold green]Generating AI analysis...") as status:
        try:
            ai_analysis = get_ai_analysis(analysis_prompt)
            if ai_analysis:
                format_ai_response(ai_analysis)
            else:
                console.print("[yellow]AI analysis unavailable at this time.[/]")
        except Exception as e:
            console.print(f"[yellow]Error generating AI analysis: {str(e)}[/]")

    # 5. Summary Section
    console.print("\n[bold magenta]5. Key Takeaways & Next Steps[/]")
    console.print(" 🎯 Key Achievements:")
    console.print(f" • Completed {user_stats_linear.get('completed', 0)} issues")
    console.print(f" • Created {user_stats.get('created', 0)} Pull Requests")
    if reviews_given > 0:
        console.print(f" • Provided {reviews_given} code reviews")

    return True

def get_ai_analysis(prompt):
    """Get AI analysis using Claude"""
    try:
        response = client.messages.create(        
            model="claude-3-sonnet-20240229",
            max_tokens=1024,
            temperature=0.7,
            system="You are an experienced engineering manager providing constructive feedback.",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        return response.content[0].text
    except Exception as e:
        console.print(f"[red]Error getting AI analysis: {str(e)}[/]")
        return None
    
    