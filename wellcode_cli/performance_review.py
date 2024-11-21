from rich.table import Table
from rich.panel import Panel
from rich.console import Console
from datetime import datetime, timedelta
from anthropic import Anthropic
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
def generate_performance_review(github_metrics, linear_metrics, github_username, linear_username=None):
    """Generate a comprehensive performance review for a specific user"""
    
    linear_username = linear_username or github_username
    
    # Calculate review period
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    period = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"

    console.print(Panel.fit(
        "[bold blue]Performance Review[/]",
        subtitle=f"GitHub: {github_username} | Linear: {linear_username} | Period: {period}",
        border_style="blue"
    ))

    # 1. Code Contributions Section (GitHub)
    console.print("\n[bold magenta]1. Code Contributions (GitHub)[/]")
    code_table = Table(show_header=True, header_style="bold magenta")
    code_table.add_column("Metric", style="cyan")
    code_table.add_column("Value", justify="right")
    
    if github_metrics and 'user_contributions' in github_metrics:
        user_stats = github_metrics['user_contributions'].get(github_username, {})
        code_table.add_row("Pull Requests Created", str(user_stats.get('created', 0)))
        code_table.add_row("Pull Requests Merged", str(user_stats.get('merged', 0)))
        
        # Calculate PR size and complexity metrics
        if 'code_quality' in github_metrics:
            avg_changes = sum(github_metrics['code_quality']['changes_per_pr']) / len(github_metrics['code_quality']['changes_per_pr']) if github_metrics['code_quality']['changes_per_pr'] else 0
            code_table.add_row("Average PR Size", f"{avg_changes:.0f} lines")
    
    console.print(code_table)

    # 2. Project Delivery Section (Linear)
    console.print("\n[bold magenta]2. Project Delivery (Linear)[/]")
    delivery_table = Table(show_header=True, header_style="bold magenta")
    delivery_table.add_column("Metric", style="cyan")
    delivery_table.add_column("Value", justify="right")
    
    if linear_metrics and 'user_contributions' in linear_metrics:
        user_stats_linear = linear_metrics['user_contributions'].get(linear_username, {})
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

    # 3. Collaboration & Review Section
    console.print("\n[bold magenta]3. Collaboration & Code Review[/]")
    collab_table = Table(show_header=True, header_style="bold magenta")
    collab_table.add_column("Metric", style="cyan")
    collab_table.add_column("Value", justify="right")
    
    if github_metrics and 'review_metrics' in github_metrics:
        review_stats = github_metrics['review_metrics']
        if github_username in review_stats.get('reviewers_per_pr', {}):
            reviews_given = len(review_stats['reviewers_per_pr'][github_username])
            collab_table.add_row("Reviews Provided", str(reviews_given))
    
    console.print(collab_table)

    # 4. AI Analysis Section
    console.print("\n[bold magenta]4. AI Analysis & Recommendations[/]")
    
    analysis_prompt = f"""
    Based on the following metrics for GitHub user '{github_username}' and Linear user '{linear_username}' over the last 30 days:

    Code Contributions (GitHub):
    - Created {user_stats.get('created', 0)} Pull Requests
    - Merged {user_stats.get('merged', 0)} Pull Requests
    - Average PR size: {avg_changes:.0f} lines

    Project Delivery (Linear):
    - Completed {user_stats_linear.get('completed', 0)} issues
    - Provided {reviews_given if 'reviews_given' in locals() else 0} code reviews

    Please provide:
    1. A brief assessment of their performance and impact
    2. 3 specific strengths demonstrated by these metrics
    3. 2 potential areas for improvement
    4. Concrete suggestions for professional growth in the next quarter
    
    Format the response in a constructive and encouraging tone, focusing on both achievements and growth opportunities.
    Keep each section concise and actionable.
    """
    
    try:
        ai_analysis = get_ai_analysis(analysis_prompt)
        console.print(Panel(ai_analysis, border_style="blue"))
    except Exception as e:
        console.print("[yellow]AI analysis unavailable at this time.[/]")
        console.print(f"[red]Error: {str(e)}[/]")

    # 5. Summary Section
    console.print("\n[bold magenta]5. Key Takeaways & Next Steps[/]")
    summary_table = Table(show_header=False, box=None)
    summary_table.add_column("", style="cyan")
    
    # Add key metrics summary
    summary_table.add_row("🎯 Key Achievements:")
    summary_table.add_row(f"• Completed {user_stats_linear.get('completed', 0)} issues")
    summary_table.add_row(f"• Created {user_stats.get('created', 0)} Pull Requests")
    if 'reviews_given' in locals():
        summary_table.add_row(f"• Provided {reviews_given} code reviews")
    
    console.print(summary_table)

    return True

def get_ai_analysis(prompt):
    """Get AI analysis using Anthropic's Claude"""
    try:
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            temperature=0.7,
            system="You are an experienced engineering manager providing constructive feedback.",
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )
        
        return response.content
    except Exception as e:
        raise Exception(f"Failed to get AI analysis: {str(e)}") 
    
    