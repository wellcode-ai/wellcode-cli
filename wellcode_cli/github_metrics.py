from github import Github
from collections import defaultdict
import statistics
from anthropic import Anthropic
import re
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
import concurrent.futures
from rich.progress import Progress, SpinnerColumn, TextColumn
from datetime import datetime, timezone, date
from time import sleep
import math
import logging
# Import configuration
try:
    from .config import GITHUB_TOKEN, ANTHROPIC_API_KEY 
except ImportError: 
    raise ImportError("Failed to import configuration. Ensure config.py exists and is properly set up.")

client = Anthropic(
    # This is the default and can be omitted
    api_key=ANTHROPIC_API_KEY,
)

console = Console()

def format_ai_response(response):
    # Try to extract content inside <analysis> tags, but proceed even if not found
    analysis_match = re.search(r'<analysis>(.*?)</analysis>', response, re.DOTALL)
    analysis_content = analysis_match.group(1) if analysis_match else response

    # Split the content into sections, either by XML-like tags or by line breaks
    sections = re.findall(r'<(\w+)>(.*?)</\1>', analysis_content, re.DOTALL)
    if not sections:
        sections = [('general', para.strip()) for para in analysis_content.split('\n') if para.strip()]

    # Create a panel for the entire analysis
    console.print("\n[bold green]AI Analysis[/]")

    for section, content in sections:
        # Convert section name to title case and replace underscores with spaces
        section_title = section.replace('_', ' ').title()
        
        # Format content as markdown for better rendering
        formatted_content = content.strip()
        
        # Create a panel for each section
        console.print(Panel(
            Markdown(formatted_content),
            title=f"[bold yellow]{section_title}[/]",
            border_style="blue",
            padding=(1, 2)
        ))

    # Extract and display efficiency score and justification
    efficiency_score_match = re.search(r'<efficiency_score>(.*?)</efficiency_score>', response, re.DOTALL)
    efficiency_justification_match = re.search(r'<efficiency_score_justification>(.*?)</efficiency_score_justification>', response, re.DOTALL)
    
    if efficiency_score_match:
        score = efficiency_score_match.group(1).strip()
        justification = ""
        if efficiency_justification_match:
            justification = efficiency_justification_match.group(1).strip()
        
        console.print(Panel(
            f"[bold white]{score}/10[/]\n\n{justification}",
            title="[bold magenta]Efficiency Score & Justification[/]",
            border_style="magenta",
            padding=(1, 2)
        ))
    else:
        # Try to find a line that looks like an efficiency score
        score_line = re.search(r'efficiency.*?score.*?(\d+(/|\s*out of\s*)10)', response, re.IGNORECASE)
        justification_line = re.search(r'justification:?\s*(.*)', response, re.IGNORECASE)
        
        if score_line or justification_line:
            content = []
            if score_line:
                content.append(f"[bold white]{score_line.group(1)}[/]")
            if justification_line:
                content.append(f"\n{justification_line.group(1)}")
            
            console.print(Panel(
                "\n".join(content),
                title="[bold magenta]Efficiency Score & Justification[/]",
                border_style="magenta",
                padding=(1, 2)
            ))

def get_ai_analysis(all_metrics):
    prompt = f"""
You are a software development team analyst tasked with analyzing team metrics to provide insights on efficiency and areas for improvement. Your analysis should be data-driven, objective, and provide valuable insights for improving the team's performance.

You will be provided with metrics for the entire organization for all developers tools. Analyze these metrics carefully, considering industry standards and best practices for software development teams.

Here are the metrics:

<metrics>
{all_metrics}
</metrics>

Before providing your final analysis, use a <scratchpad> to organize your thoughts and initial observations. In the scratchpad, list key observations for each metric category and note any potential insights or areas that require further investigation.

Based on your analysis, provide the following in your final output:

1. An assessment of the team's overall efficiency
2. Specific areas where the team is performing well
3. Areas that need improvement
4. Actionable recommendations to increase efficiency

For each point, provide a brief explanation of your reasoning based on the metrics provided. Ensure that you reference specific metrics in your explanations.

Present your analysis in the following format:

<analysis>
<overall_efficiency>
[Your assessment of the team's overall efficiency]
</overall_efficiency>

<strengths>
[List and explain specific areas where the team is performing well]
</strengths>

<areas_for_improvement>
[List and explain areas that need improvement]
</areas_for_improvement>

<recommendations>
[Provide actionable recommendations to increase efficiency]
</recommendations>
</analysis>

Additional guidelines for your analysis:
1. Ensure that you consider all provided metrics in your analysis.
2. When discussing trends or comparisons, provide specific numbers or percentages from the metrics to support your points.
3. Consider how different metrics might be interrelated and how improvements in one area might affect others.
4. Prioritize your recommendations based on their potential impact on overall team efficiency.
5. If any metrics seem contradictory or unclear, mention this in your analysis and provide possible explanations or suggestions for further investigation.

Remember to maintain a professional and constructive tone throughout your analysis, focusing on opportunities for improvement rather than criticizing the team's performance.

After completing your analysis, provide a justification for an efficiency score, followed by the score itself. Use the following format:

<efficiency_score_justification>
[Provide a concise justification for the efficiency score, referencing key metrics and insights from your analysis]
</efficiency_score_justification>

<efficiency_score>
[Provide a numerical score from 1 to 10, where 1 is extremely inefficient and 10 is highly efficient]
</efficiency_score>

Ensure that your efficiency score aligns with your overall analysis and is supported by the metrics provided.
"""
    message = client.messages.create(
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="claude-3-5-sonnet-20240620",
    )
    
    # Return just the content without printing anything
    return message.content[0].text if message.content else ""

def get_repo_metrics(repo, start_date, end_date, user_filter, team_filter, team_members=None):
    """Process a single repository's metrics with retry logic"""
    max_retries = 3
    base_delay = 30
    
    for attempt in range(max_retries):
        try:
            # Initialize metrics dictionary
            repo_metrics = {
                'prs_created': 0,
                'prs_merged': 0,
                'prs_merged_to_main': 0,
                'comments_per_pr': {},
                'time_to_merge': [],
                'lead_times': [],
                'user_contributions': defaultdict(lambda: {'created': 0, 'merged': 0}),
                'review_metrics': {
                    'time_to_first_review': [],
                    'review_cycles': [],
                    'reviewers_per_pr': defaultdict(set),
                    'blocking_reviews': 0,
                },
                'code_quality': {
                    'changes_per_pr': [],
                    'files_changed_per_pr': [],
                    'commit_count_per_pr': [],
                    'revert_count': 0,
                    'hotfix_count': 0,
                },
                'collaboration': {
                    'cross_team_reviews': 0,
                    'review_comments_per_pr': {},
                    'self_merges': 0,
                },
                'timing_metrics': {
                    'merge_time_distribution': {
                        'business_hours': 0,
                        'after_hours': 0,
                        'weekends': 0,
                    }
                },
                'bottleneck_metrics': {
                    'stale_prs': 0,
                    'long_running_prs': 0,
                    'review_wait_time': [],
                }
            }

            # Get pull requests
            pulls = repo.get_pulls(state='all')
            for pr in pulls:
                try:
                    process_pr(pr, repo_metrics, start_date, end_date, user_filter, team_filter, team_members)
                except Exception as e:
                    if "403" in str(e) and "rate limit" in str(e).lower():
                        # Calculate exponential backoff delay
                        delay = base_delay * (math.pow(2, attempt))
                        console.print(f"[yellow]Rate limit hit, waiting {delay} seconds before retry...[/]")
                        sleep(delay)
                        break  # Break inner loop to retry the whole repo
                    else:
                        console.print(f"[yellow]Error processing PR {pr.number} in repo {repo.name}: {str(e)}[/]")
                        continue

            return repo_metrics

        except Exception as e:
            if "403" in str(e) and "rate limit" in str(e).lower():
                if attempt < max_retries - 1:  # Don't sleep on last attempt
                    delay = base_delay * (math.pow(2, attempt))
                    console.print(f"[yellow]Rate limit hit, waiting {delay} seconds before retry...[/]")
                    sleep(delay)
                    continue
            console.print(f"[red]Error processing repo {repo.name}: {str(e)}[/]")
            return None

    return None

def process_pr(pr, repo_metrics, start_date, end_date, user_filter, team_filter, team_members=None):
    """Process a single PR with proper merge detection"""
    try:
        # Skip if team filter is active and author is not in team
        if team_filter and pr.user and pr.user.login not in (team_members or set()):
            return
        
        # Convert GitHub timestamps to naive datetimes by removing timezone info
        created_at = pr.created_at.replace(tzinfo=None)
        merged_at = pr.merged_at.replace(tzinfo=None) if pr.merged_at else None
        closed_at = pr.closed_at.replace(tzinfo=None) if pr.closed_at else None

        # Convert input dates to naive datetimes for comparison
        start_date = start_date.replace(tzinfo=None)
        end_date = end_date.replace(tzinfo=None)

        # Check if PR is within date range
        if created_at < start_date or created_at > end_date:
            return

        # Basic PR metrics
        repo_metrics['prs_created'] += 1
        
        # Check if PR is merged
        if pr.merged:  # Add proper merge check
            repo_metrics['prs_merged'] += 1
            
            # Check if merged to main/master
            base_branch = pr.base.ref.lower()
            if base_branch in ['main', 'master']:
                repo_metrics['prs_merged_to_main'] += 1
            
            # Record merge time if available
            if merged_at:
                merge_time = (merged_at - created_at).total_seconds() / 3600  # hours
                repo_metrics['time_to_merge'].append(merge_time)

        # Process comments
        comments = list(pr.get_comments())
        repo_metrics['comments_per_pr'][pr.number] = len(comments)

        # Calculate time to merge
        if merged_at:
            time_to_merge = (merged_at - created_at).total_seconds() / 3600
            repo_metrics['time_to_merge'].append(time_to_merge)
            repo_metrics['lead_times'].append(time_to_merge)

        # Process reviews
        reviews = list(pr.get_reviews())
        for review in reviews:
            review_submitted_at = review.submitted_at.replace(tzinfo=None) if review.submitted_at else None
            if review_submitted_at:
                time_to_review = (review_submitted_at - created_at).total_seconds() / 3600
                repo_metrics['review_metrics']['time_to_first_review'].append(time_to_review)

        # Process commits
        commits = list(pr.get_commits())
        repo_metrics['code_quality']['commit_count_per_pr'].append(len(commits))
        
        # Process user contributions
        author = pr.user.login if pr.user else 'unknown'
        if not user_filter or author == user_filter:
            repo_metrics['user_contributions'][author]['created'] += 1
            if pr.merged:
                repo_metrics['user_contributions'][author]['merged'] += 1

        # Process review comments
        review_comments = list(pr.get_review_comments())
        comments_count = len(review_comments)
        if comments_count > 0:  # Only add if there are comments
            repo_metrics['collaboration']['review_comments_per_pr'][pr.number] = comments_count

        # Process file changes
        if pr.additions is not None and pr.deletions is not None:
            total_changes = pr.additions + pr.deletions
            if total_changes > 0:  # Only add if there are changes
                repo_metrics['code_quality']['changes_per_pr'].append(total_changes)

        if pr.changed_files is not None and pr.changed_files > 0:
            repo_metrics['code_quality']['files_changed_per_pr'].append(pr.changed_files)

        # Track unique reviewers
        reviewers = set()
        for review in reviews:
            if review.user and review.user.login != pr.user.login:  # Exclude self-reviews
                reviewers.add(review.user.login)
        
        if reviewers:  # Only add if there are reviewers
            repo_metrics['review_metrics']['reviewers_per_pr'][pr.number] = reviewers
            
            # Check for cross-team reviews (you might want to customize this logic)
            if len(reviewers) > 1:
                repo_metrics['collaboration']['cross_team_reviews'] += 1

        # Check for self-merges
        if pr.merged and pr.merged_by:
            if pr.user and pr.merged_by.login == pr.user.login:
                repo_metrics['collaboration']['self_merges'] += 1

        # Process merge timing
        if merged_at:
            merge_hour = merged_at.hour
            merge_weekday = merged_at.weekday()
            
            if merge_weekday < 5:  # Weekday
                if 9 <= merge_hour < 17:  # Business hours (9 AM to 5 PM)
                    repo_metrics['timing_metrics']['merge_time_distribution']['business_hours'] += 1
                else:
                    repo_metrics['timing_metrics']['merge_time_distribution']['after_hours'] += 1
            else:  # Weekend
                repo_metrics['timing_metrics']['merge_time_distribution']['weekends'] += 1

    except Exception as e:
        logging.error(f"Error processing PR {pr.number} in {pr.base.repo.name}: {str(e)}")
        raise

def ensure_datetime(dt):
    """Utility function to ensure a date or datetime object is a timezone-aware datetime"""
    try:
        if dt is None:
            return None
        if isinstance(dt, date) and not isinstance(dt, datetime):
            dt = datetime.combine(dt, datetime.min.time())
        if isinstance(dt, datetime) and dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as e:
        console.print(f"[red]Error converting datetime: {str(e)}[/]")
        return None

def is_within_range(date_to_check, start_date, end_date):
    """Safely check if a date is within a range"""
    try:
        date_to_check = ensure_datetime(date_to_check)
        start_date = ensure_datetime(start_date)
        end_date = ensure_datetime(end_date)
        
        if any(d is None for d in [date_to_check, start_date, end_date]):
            return False
            
        return start_date <= date_to_check <= end_date
    except Exception as e:
        console.print(f"[red]Error checking date range: {str(e)}[/]")
        return False

def merge_metrics(metrics_list):
    """Merge metrics from multiple repositories"""
    combined_metrics = {
        # Core metrics
        'prs_created': 0,
        'prs_merged': 0,
        'prs_merged_to_main': 0,
        'comments_per_pr': {},
        'time_to_merge': [],
        'lead_times': [],
        'user_contributions': defaultdict(lambda: {'created': 0, 'merged': 0}),
        
        # Review metrics
        'review_metrics': {
            'time_to_first_review': [],
            'review_cycles': [],
            'reviewers_per_pr': defaultdict(set),
            'blocking_reviews': 0,
        },
        
        # Code quality metrics
        'code_quality': {
            'changes_per_pr': [],
            'files_changed_per_pr': [],
            'commit_count_per_pr': [],
            'revert_count': 0,
            'hotfix_count': 0,
        },
        
        # Collaboration metrics
        'collaboration': {
            'cross_team_reviews': 0,
            'review_comments_per_pr': {},
            'self_merges': 0,
        },
        
        # Timing metrics
        'timing_metrics': {
            'merge_time_distribution': {
                'business_hours': 0,
                'after_hours': 0,
                'weekends': 0,
            },
        },
        
        # Bottleneck metrics
        'bottleneck_metrics': {
            'stale_prs': 0,
            'long_running_prs': 0,
            'review_wait_time': [],
        },
    }
    
    for metrics in metrics_list:
        # Merge core metrics
        combined_metrics['prs_created'] += metrics['prs_created']
        combined_metrics['prs_merged'] += metrics['prs_merged']
        combined_metrics['prs_merged_to_main'] += metrics['prs_merged_to_main']
        combined_metrics['comments_per_pr'].update(metrics['comments_per_pr'])
        combined_metrics['time_to_merge'].extend(metrics['time_to_merge'])
        combined_metrics['lead_times'].extend(metrics['lead_times'])
        
        # Merge user contributions
        for user, stats in metrics['user_contributions'].items():
            combined_metrics['user_contributions'][user]['created'] += stats['created']
            combined_metrics['user_contributions'][user]['merged'] += stats['merged']
        
        # Merge review metrics
        if 'review_metrics' in metrics:
            combined_metrics['review_metrics']['time_to_first_review'].extend(metrics['review_metrics']['time_to_first_review'])
            combined_metrics['review_metrics']['review_cycles'].extend(metrics['review_metrics']['review_cycles'])
            combined_metrics['review_metrics']['blocking_reviews'] += metrics['review_metrics']['blocking_reviews']
            for pr_num, reviewers in metrics['review_metrics']['reviewers_per_pr'].items():
                combined_metrics['review_metrics']['reviewers_per_pr'][pr_num].update(reviewers)
        
        # Merge code quality metrics
        if 'code_quality' in metrics:
            combined_metrics['code_quality']['changes_per_pr'].extend(metrics['code_quality']['changes_per_pr'])
            combined_metrics['code_quality']['files_changed_per_pr'].extend(metrics['code_quality']['files_changed_per_pr'])
            combined_metrics['code_quality']['revert_count'] += metrics['code_quality']['revert_count']
            combined_metrics['code_quality']['hotfix_count'] += metrics['code_quality']['hotfix_count']
        
        # Merge collaboration metrics
        if 'collaboration' in metrics:
            combined_metrics['collaboration']['cross_team_reviews'] += metrics['collaboration']['cross_team_reviews']
            combined_metrics['collaboration']['review_comments_per_pr'].update(metrics['collaboration']['review_comments_per_pr'])
            combined_metrics['collaboration']['self_merges'] += metrics['collaboration']['self_merges']
        
        # Merge timing metrics
        if 'timing_metrics' in metrics:
            for period in ['business_hours', 'after_hours', 'weekends']:
                combined_metrics['timing_metrics']['merge_time_distribution'][period] += \
                    metrics['timing_metrics']['merge_time_distribution'][period]
        
        # Merge bottleneck metrics
        if 'bottleneck_metrics' in metrics:
            combined_metrics['bottleneck_metrics']['stale_prs'] += metrics['bottleneck_metrics']['stale_prs']
            combined_metrics['bottleneck_metrics']['long_running_prs'] += metrics['bottleneck_metrics']['long_running_prs']
            combined_metrics['bottleneck_metrics']['review_wait_time'].extend(metrics['bottleneck_metrics']['review_wait_time'])
    
    return combined_metrics

def get_github_metrics(org_name, start_date, end_date, user_filter=None, team_filter=None):
    g = Github(GITHUB_TOKEN)
    org = g.get_organization(org_name)
    
    # Fetch team members first if team filter is specified
    team_members = set()
    if team_filter:
        try:
            teams = list(org.get_teams())
            console.print(f"[yellow]There are {len(teams)} teams[/]")
            for t in teams:
                console.print(f"[yellow]Team: {t.name} (slug: {t.slug})[/]")
            
            # Try to find team by name if slug fails
            team = None
            for t in teams:
                if t.name.lower() == team_filter.lower() or t.slug.lower() == team_filter.lower():
                    team = t
                    break
                    
            if team:
                team_members = {member.login for member in team.get_members(role='all')}
                console.print(f"[yellow]Found {len(team_members)} team members[/]")
            else:
                console.print(f"[red]Team '{team_filter}' not found[/]")
        except Exception as e:
            console.print(f"[red]Warning: Could not fetch team members for {team_filter}: {str(e)}[/]")
            console.print(f"[yellow]Error type: {type(e).__name__}[/]")

    start_date = ensure_datetime(start_date)
    end_date = ensure_datetime(end_date)

    # Get list of repositories first
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        progress.add_task(description="[yellow]Fetching repositories...[/]", total=None)
        repos = list(org.get_repos())
        console.print(f"[yellow]Found {len(repos)} repositories[/]")
    
    # Process repositories in parallel
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
    ) as progress:
        task = progress.add_task(description="Processing repositories...", total=None)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_repo = {
                executor.submit(get_repo_metrics, repo, start_date, end_date, user_filter, team_filter, team_members): repo
                for repo in repos
            }
            
            metrics_list = []
            for future in concurrent.futures.as_completed(future_to_repo):
                repo = future_to_repo[future]
                console.print(f"[yellow] 🔍 Processing repository: {repo.name}[/]")
                try:
                    metrics = future.result()
                    metrics_list.append(metrics)
                except Exception as e:
                    console.print(f"[yellow]Error processing repo {repo.name}: {str(e)}[/]")
    
    # Merge metrics from all repositories
    combined_metrics = merge_metrics(metrics_list)
    
    # Calculate summary metrics
    days_in_period = (end_date - start_date).days + 1
    combined_metrics.update({
        'deployment_frequency': combined_metrics['prs_merged_to_main'] / days_in_period,
        'median_lead_time': statistics.median(combined_metrics['lead_times']) if combined_metrics['lead_times'] else 0,
        'avg_comments_per_pr': (
            sum(combined_metrics['comments_per_pr'].values()) / combined_metrics['prs_created']
            if combined_metrics['prs_created'] > 0 else 0
        ),
        'avg_time_to_merge': (
            sum(combined_metrics['time_to_merge']) / len(combined_metrics['time_to_merge'])
            if combined_metrics['time_to_merge'] else 0
        )
    })
    
    return combined_metrics

def display_github_metrics(metrics):
    console.print("\n[bold green]GitHub Metrics Analysis[/]")
    
    # Main metrics table
    console.print("\n[bold magenta]Core Metrics[/]")
    main_table = Table(show_header=True, header_style="bold magenta")
    main_table.add_column("Metric", style="cyan")
    main_table.add_column("Value", justify="right")
    
    main_table.add_row("Pull Requests Created (Total)", str(metrics.get('prs_created', 0)))
    main_table.add_row("Pull Requests Merged (Total)", str(metrics.get('prs_merged', 0)))
    main_table.add_row("Pull Requests Merged to Main Branch", str(metrics.get('prs_merged_to_main', 0)))
    if metrics.get('deployment_frequency'):
        main_table.add_row("Deployments per Day", f"{metrics['deployment_frequency']:.2f}/day")
    if metrics.get('median_lead_time'):
        main_table.add_row("Median Time from Creation to Merge", f"{metrics['median_lead_time']:.1f} hours")
    
    console.print(main_table)

    # Review Process Metrics
    if 'review_metrics' in metrics:
        console.print("\n[bold magenta]Review Process[/]")
        review_table = Table(show_header=True, header_style="bold magenta")
        review_table.add_column("Metric", style="cyan")
        review_table.add_column("Value", justify="right")
        
        review_metrics = metrics['review_metrics']
        
        # Safely calculate averages with error handling
        try:
            avg_time_to_review = statistics.mean(review_metrics['time_to_first_review']) if review_metrics.get('time_to_first_review') else 0
            review_table.add_row("Average Time Until First Review", f"{avg_time_to_review:.1f} hours")
        except statistics.StatisticsError:
            review_table.add_row("Average Time Until First Review", "N/A")
            
        try:
            avg_review_cycles = statistics.mean(review_metrics['review_cycles']) if review_metrics.get('review_cycles') else 0
            review_table.add_row("Avg Review Cycles", f"{avg_review_cycles:.1f}")
        except statistics.StatisticsError:
            review_table.add_row("Avg Review Cycles", "N/A")
        
        review_table.add_row("Blocking Reviews", str(review_metrics.get('blocking_reviews', 0)))
        
        try:
            reviewers_per_pr = review_metrics.get('reviewers_per_pr', {})
            if reviewers_per_pr:
                avg_reviewers = statistics.mean(len(reviewers) for reviewers in reviewers_per_pr.values())
                review_table.add_row("Avg Reviewers per PR", f"{avg_reviewers:.1f}")
            else:
                review_table.add_row("Avg Reviewers per PR", "N/A")
        except statistics.StatisticsError:
            review_table.add_row("Avg Reviewers per PR", "N/A")
        
        console.print(review_table)

    # Code Quality Metrics
    if 'code_quality' in metrics:
        console.print("\n[bold magenta]Code Quality[/]")
        quality_table = Table(show_header=True, header_style="bold magenta")
        quality_table.add_column("Metric", style="cyan")
        quality_table.add_column("Value", justify="right")
        
        code_quality = metrics['code_quality']
        
        try:
            avg_changes = statistics.mean(code_quality['changes_per_pr']) if code_quality.get('changes_per_pr') else 0
            quality_table.add_row("Average Lines Changed per Pull Request", f"{avg_changes:.0f} lines")
        except statistics.StatisticsError:
            quality_table.add_row("Average Lines Changed per Pull Request", "N/A")
            
        try:
            avg_files = statistics.mean(code_quality['files_changed_per_pr']) if code_quality.get('files_changed_per_pr') else 0
            quality_table.add_row("Avg Files Changed", f"{avg_files:.1f}")
        except statistics.StatisticsError:
            quality_table.add_row("Avg Files Changed", "N/A")
        
        quality_table.add_row("Hotfix Count", str(code_quality.get('hotfix_count', 0)))
        quality_table.add_row("Revert Count", str(code_quality.get('revert_count', 0)))
        
        console.print(quality_table)

    # Collaboration Metrics
    if 'collaboration' in metrics:
        console.print("\n[bold magenta]Team Collaboration[/]")
        collab_table = Table(show_header=True, header_style="bold magenta")
        collab_table.add_column("Metric", style="cyan")
        collab_table.add_column("Value", justify="right")
        
        collaboration = metrics['collaboration']
        
        try:
            review_comments = collaboration.get('review_comments_per_pr', {})
            if review_comments:
                avg_comments = statistics.mean(review_comments.values())
                collab_table.add_row("Avg Review Comments", f"{avg_comments:.1f}")
            else:
                collab_table.add_row("Avg Review Comments", "N/A")
        except statistics.StatisticsError:
            collab_table.add_row("Avg Review Comments", "N/A")
        
        collab_table.add_row("Self-Merged Pull Requests", str(collaboration.get('self_merges', 0)))
        collab_table.add_row("Cross-Team Review Count", str(collaboration.get('cross_team_reviews', 0)))
        
        console.print(collab_table)

    # Timing Metrics
    if 'timing_metrics' in metrics:
        console.print("\n[bold magenta]Timing Distribution[/]")
        timing_table = Table(show_header=True, header_style="bold magenta")
        timing_table.add_column("Time Period", style="cyan")
        timing_table.add_column("Count", justify="right")
        
        timing = metrics['timing_metrics'].get('merge_time_distribution', {})
        
        timing_table.add_row("Merges During Business Hours (9-5)", str(timing.get('business_hours', 0)))
        timing_table.add_row("Merges After Business Hours", str(timing.get('after_hours', 0)))
        timing_table.add_row("Merges During Weekends", str(timing.get('weekends', 0)))
        
        console.print(timing_table)

    # Bottleneck Metrics
    if 'bottleneck_metrics' in metrics:
        console.print("\n[bold magenta]Process Bottlenecks[/]")
        bottleneck_table = Table(show_header=True, header_style="bold magenta")
        bottleneck_table.add_column("Metric", style="cyan")
        bottleneck_table.add_column("Value", justify="right")
        
        bottlenecks = metrics['bottleneck_metrics']
        
        bottleneck_table.add_row("Stale Pull Requests (>7 days)", str(bottlenecks.get('stale_prs', 0)))
        bottleneck_table.add_row("Long-Running Pull Requests (>14 days)", str(bottlenecks.get('long_running_prs', 0)))
        
        try:
            wait_times = bottlenecks.get('review_wait_time', [])
            if wait_times:
                avg_wait_time = statistics.mean(wait_times)
                bottleneck_table.add_row("Avg Review Wait Time", f"{avg_wait_time:.1f} hours")
            else:
                bottleneck_table.add_row("Avg Review Wait Time", "N/A")
        except statistics.StatisticsError:
            bottleneck_table.add_row("Avg Review Wait Time", "N/A")
        
        console.print(bottleneck_table)

    # User Contributions
    if 'user_contributions' in metrics and metrics['user_contributions']:
        console.print("\n[bold magenta]User Contributions[/]")
        user_table = Table(show_header=True, header_style="bold magenta")
        user_table.add_column("User", style="cyan")
        user_table.add_column("Pull Requests Created", justify="right")
        user_table.add_column("Pull Requests Merged", justify="right")
        
        # Sort users by number of PRs created
        sorted_users = sorted(
            metrics['user_contributions'].items(),
            key=lambda x: x[1]['created'],
            reverse=True
        )
        
        for user, stats in sorted_users[:10]:  # Show top 10 contributors
            user_table.add_row(
                user,
                str(stats['created']),
                str(stats['merged'])
            )
        
        console.print(user_table)

    # Summary Statistics
    console.print("\n[bold magenta]Summary Statistics[/]")
    summary_table = Table(show_header=True, header_style="bold magenta")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", justify="right")
    
    try:
        if metrics.get('time_to_merge'):
            avg_time = statistics.mean(metrics['time_to_merge'])
            summary_table.add_row("Average Time from Creation to Merge", f"{avg_time:.1f} hours")
        else:
            summary_table.add_row("Average Time from Creation to Merge", "N/A")
    except statistics.StatisticsError:
        summary_table.add_row("Average Time from Creation to Merge", "N/A")
    
    try:
        if metrics.get('lead_times'):
            median_lead = statistics.median(metrics['lead_times'])
            summary_table.add_row("Median Lead Time", f"{median_lead:.1f} hours")
        else:
            summary_table.add_row("Median Lead Time", "N/A")
    except statistics.StatisticsError:
        summary_table.add_row("Median Lead Time", "N/A")
    
    console.print(summary_table)

def get_review_metrics(pull_requests):
    """Extract review metrics from pull requests"""
    review_metrics = {
        'reviewers_per_pr': {},
        'review_comments_per_pr': {},
        'average_review_time': {}
    }
    
    for pr in pull_requests:
        # Get reviews
        reviews = pr.get_reviews()
        for review in reviews:
            reviewer = review.user.login
            
            # Count reviews per reviewer
            if reviewer not in review_metrics['reviewers_per_pr']:
                review_metrics['reviewers_per_pr'][reviewer] = []
            review_metrics['reviewers_per_pr'][reviewer].append(pr.number)
            
            # Count review comments
            if reviewer not in review_metrics['review_comments_per_pr']:
                review_metrics['review_comments_per_pr'][reviewer] = []
            review_metrics['review_comments_per_pr'][reviewer].extend(review.get_comments())
            
            # Calculate review time
            if reviewer not in review_metrics['average_review_time']:
                review_metrics['average_review_time'][reviewer] = []
            if pr.created_at and review.submitted_at:
                review_time = (review.submitted_at - pr.created_at).total_seconds() / 3600  # hours
                review_metrics['average_review_time'][reviewer].append(review_time)
    
    # Calculate averages
    for reviewer in review_metrics['average_review_time']:
        times = review_metrics['average_review_time'][reviewer]
        if times:
            review_metrics['average_review_time'][reviewer] = sum(times) / len(times)
    
    return review_metrics

