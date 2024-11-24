from github import Github
from collections import defaultdict
import statistics
from anthropic import Anthropic
import re
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
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
                'user_contributions': defaultdict(lambda: {
                    'created': 0,
                    'merged': 0,
                    'time_to_merge': [],
                    'lead_times': [],
                    'review_cycles': [],
                    'changes_per_pr': [],
                    'files_changed': [],
                    'commits_count': [],
                    'review_comments_received': 0,
                    'review_comments_given': 0,
                    'reviews_performed': 0,
                    'blocking_reviews_given': 0,
                    'self_merges': 0,
                    'cross_team_reviews': 0,
                    'review_wait_times': [],
                    'merge_distribution': {
                        'business_hours': 0,
                        'after_hours': 0,
                        'weekends': 0
                    }
                }),
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

def is_business_hours(dt):
    """Check if time is during business hours (9am-5pm)."""
    return 9 <= dt.hour < 17 and dt.weekday() < 5

def is_weekend(dt):
    """Check if date is weekend."""
    return dt.weekday() >= 5

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
        logging.warning(f"Error converting datetime: {str(e)}")
        return None

def process_pr(pr, repo_metrics, start_date, end_date, user_filter, team_filter, team_members=None):
    """Process a single pull request and update metrics."""
    # Skip if PR is outside date range
    if not (start_date <= pr.created_at.replace(tzinfo=timezone.utc) <= end_date):
        return

    # Get PR author
    author = pr.user.login
    
    # Initialize metrics for new author
    if author not in repo_metrics['user_contributions']:
        repo_metrics['user_contributions'][author] = {
            'created': 0,
            'merged': 0,
            'time_to_merge': [],
            'changes_per_pr': [],
            'files_changed': [],
            'commits_count': [],
            'review_comments_received': 0,
            'review_comments_given': {},
            'reviews_performed': set(),
            'blocking_reviews_given': 0,
            'self_merges': 0,
            'cross_team_reviews': 0,
            'review_wait_times': [],
            'lead_times': [],
            'review_cycles': []
        }

    # Update basic PR metrics
    repo_metrics['prs_created'] += 1
    repo_metrics['user_contributions'][author]['created'] += 1

    if pr.merged:
        repo_metrics['prs_merged'] += 1
        repo_metrics['user_contributions'][author]['merged'] += 1
        
        # Track self-merges
        if pr.merged_by and pr.merged_by.login == author:
            repo_metrics['collaboration']['self_merges'] += 1
            repo_metrics['user_contributions'][author]['self_merges'] += 1

        # Calculate merge time
        merge_time = (pr.merged_at - pr.created_at).total_seconds() / 3600
        repo_metrics['time_to_merge'].append(merge_time)
        repo_metrics['user_contributions'][author]['time_to_merge'].append(merge_time)

        # Track merged to main
        if pr.base.ref == 'main' or pr.base.ref == 'master':
            repo_metrics['prs_merged_to_main'] += 1

        # Process timing metrics for merged PRs
        try:
            if pr.merged:
                merge_time = ensure_datetime(pr.merged_at)
                if merge_time:
                    if is_weekend(merge_time):
                        repo_metrics['timing_metrics']['merge_time_distribution']['weekends'] += 1
                    elif is_business_hours(merge_time):
                        repo_metrics['timing_metrics']['merge_time_distribution']['business_hours'] += 1
                    else:
                        repo_metrics['timing_metrics']['merge_time_distribution']['after_hours'] += 1
                    
                    logging.info(f"PR #{pr.number} - Merged during: {'weekend' if is_weekend(merge_time) else 'business hours' if is_business_hours(merge_time) else 'after hours'}")
        except Exception as e:
            logging.warning(f"Error processing merge timing for PR {pr.number}: {str(e)}")

        # Calculate lead time for merged PRs
        try:
            commits = list(pr.get_commits())
            if commits:
                # Get first commit date (earliest commit)
                first_commit = ensure_datetime(commits[-1].commit.committer.date)
                merge_time = ensure_datetime(pr.merged_at)
                
                if first_commit and merge_time:
                    # Calculate lead time (first commit to merge)
                    lead_time = (merge_time - first_commit).total_seconds() / 3600
                    repo_metrics['lead_times'].append(lead_time)
                    repo_metrics['user_contributions'][author]['lead_times'].append(lead_time)
                    
                    logging.info(f"PR #{pr.number} - Lead Time: {lead_time:.1f}h (First Commit: {first_commit}, Merged: {merge_time})")
        except Exception as e:
            logging.warning(f"Error calculating lead time for PR {pr.number}: {str(e)}")

    # Initialize review cycle tracking
    review_cycles = 0
    last_review_state = None
    last_commit_sha = None
    
    # Get all commits and reviews in chronological order
    try:
        commits = list(pr.get_commits())
        reviews = list(pr.get_reviews())
        
        # Track unique reviewers
        pr_reviewers = {review.user.login for review in reviews if review.user and review.user.login != pr.user.login}
        
        # Sort reviews by submission time
        reviews = sorted(reviews, key=lambda x: x.submitted_at if x.submitted_at else datetime.min.replace(tzinfo=timezone.utc))
        
        # Track review cycles (changes requested -> new commit)
        for review in reviews:
            if not review.user or review.user.login == pr.user.login:  # Skip self-reviews
                continue
                
            if review.state == 'CHANGES_REQUESTED':
                # Count as new cycle if this is a new changes request
                if last_review_state != 'CHANGES_REQUESTED':
                    review_cycles += 1
                    
                # Track the commit SHA at time of review
                last_commit_sha = review.commit_id
                
            elif review.state == 'APPROVED':
                # If there were changes after last "changes requested"
                if last_review_state == 'CHANGES_REQUESTED' and last_commit_sha:
                    current_commit_sha = review.commit_id
                    if current_commit_sha != last_commit_sha:
                        review_cycles += 1
                        
            last_review_state = review.state
        
        # Only store cycles if we had any reviews
        if reviews:
            repo_metrics['review_metrics']['review_cycles'].append(review_cycles)
            logging.info(f"PR #{pr.number} - Review Cycles: {review_cycles}")
            
            # Store for the author
            author = pr.user.login
            if author in repo_metrics['user_contributions']:
                repo_metrics['user_contributions'][author]['review_cycles'].append(review_cycles)
                
    except Exception as e:
        logging.warning(f"Error calculating review cycles for PR {pr.number}: {str(e)}")

    # Update PR-level metrics
    if pr_reviewers:
        repo_metrics['review_metrics']['reviewers_per_pr'][pr.number] = pr_reviewers
        repo_metrics['review_metrics']['review_cycles'].append(review_cycles)

    # Process review comments
    try:
        # Get both review comments and issue comments
        review_comments = list(pr.get_review_comments())
        issue_comments = list(pr.get_comments())
        total_comments = len(review_comments) + len(issue_comments)

        # Track comments per PR
        repo_metrics['collaboration']['review_comments_per_pr'][pr.number] = total_comments

        # Track comments per user
        for comment in review_comments + issue_comments:
            commenter = comment.user.login if comment.user else None
            if commenter:
                if commenter not in repo_metrics['user_contributions']:
                    repo_metrics['user_contributions'][commenter] = {
                        'created': 0,
                        'merged': 0,
                        'review_comments_given': {},
                        # ... other user metrics ...
                    }
                
                if pr.number not in repo_metrics['user_contributions'][commenter]['review_comments_given']:
                    repo_metrics['user_contributions'][commenter]['review_comments_given'][pr.number] = 0
                repo_metrics['user_contributions'][commenter]['review_comments_given'][pr.number] += 1

    except Exception as e:
        logging.warning(f"Error processing PR comments: {str(e)}")

    # Enhanced code quality metrics
    try:
        # Detect reverts and hotfixes
        title_lower = pr.title.lower()
        if title_lower.startswith('revert'):
            repo_metrics['code_quality']['revert_count'] += 1
        if any(term in title_lower for term in ['hotfix', 'hot-fix', 'hot fix']):
            repo_metrics['code_quality']['hotfix_count'] += 1
            
        # Calculate changes
        changes = pr.additions + pr.deletions
        repo_metrics['code_quality']['changes_per_pr'].append(changes)
        
        # Calculate files changed
        files_changed = len(list(pr.get_files()))
        repo_metrics['code_quality']['files_changed_per_pr'].append(files_changed)
        
        # Calculate commit count
        commits = list(pr.get_commits())
        repo_metrics['code_quality']['commit_count_per_pr'].append(len(commits))
        
        # Store metrics for the author
        if author in repo_metrics['user_contributions']:
            repo_metrics['user_contributions'][author]['changes_per_pr'].append(changes)
            repo_metrics['user_contributions'][author]['files_changed'].append(files_changed)
            repo_metrics['user_contributions'][author]['commits_count'].append(len(commits))
            
    except Exception as e:
        logging.warning(f"Error processing code quality metrics for PR {pr.number}: {str(e)}")

    # Calculate bottleneck metrics
    try:
        current_time = datetime.now(timezone.utc)
        pr_created = ensure_datetime(pr.created_at)
        
        if not pr_created:
            return
            
        pr_age = (current_time - pr_created).total_seconds() / 3600  # hours
        
        # Stale PRs: Open PRs without activity in last 7 days (168 hours)
        if not pr.merged:
            # Get all activity timestamps
            timestamps = [
                ensure_datetime(pr.updated_at),
                *[ensure_datetime(c.commit.committer.date) for c in pr.get_commits()],
                *[ensure_datetime(r.submitted_at) for r in pr.get_reviews()]
            ]
            
            # Filter out None values and get latest activity
            timestamps = [t for t in timestamps if t is not None]
            
            if timestamps:
                last_activity = max(timestamps)
                hours_since_activity = (current_time - last_activity).total_seconds() / 3600
                if hours_since_activity > 168:  # 7 days
                    repo_metrics['bottleneck_metrics']['stale_prs'] += 1
                    logging.info(f"PR #{pr.number} marked as stale - {hours_since_activity:.1f}h since last activity")

        # Long-running PRs: Open for more than 14 days (336 hours)
        if pr_age > 336:
            repo_metrics['bottleneck_metrics']['long_running_prs'] += 1
            logging.info(f"PR #{pr.number} marked as long-running - Age: {pr_age:.1f}h")

        # Review wait time: Time to first meaningful review
        reviews = sorted(list(pr.get_reviews()), key=lambda x: x.submitted_at)
        meaningful_reviews = [r for r in reviews if r.state in ['APPROVED', 'CHANGES_REQUESTED']]
        
        if meaningful_reviews:
            first_review = meaningful_reviews[0]
            wait_time = (ensure_datetime(first_review.submitted_at) - pr_created).total_seconds() / 3600
            repo_metrics['bottleneck_metrics']['review_wait_time'].append(wait_time)
            logging.info(f"PR #{pr.number} - Review wait time: {wait_time:.1f}h")

    except Exception as e:
        logging.warning(f"Error calculating bottleneck metrics for PR {pr.number}: {str(e)}")

    # Enhanced review metrics tracking
    try:
        reviews = list(pr.get_reviews())
        meaningful_reviews = [r for r in reviews if r.state in ['APPROVED', 'CHANGES_REQUESTED']]
        reviews_by_date = sorted(meaningful_reviews, key=lambda x: x.submitted_at)
        
        # Time to first review
        if reviews_by_date:
            first_review_time = (reviews_by_date[0].submitted_at - pr.created_at).total_seconds() / 3600
            repo_metrics['review_metrics']['time_to_first_review'].append(first_review_time)
        
        # Track review cycles and blocking reviews
        current_review_cycle = 0
        last_commit_sha = None
        
        for review in reviews_by_date:
            if review.state == 'CHANGES_REQUESTED':
                repo_metrics['review_metrics']['blocking_reviews'] += 1
                current_review_cycle += 1
                last_commit_sha = review.commit_id
            elif review.state == 'APPROVED' and last_commit_sha and review.commit_id != last_commit_sha:
                current_review_cycle += 1
        
        if current_review_cycle > 0:
            repo_metrics['review_metrics']['review_cycles'].append(current_review_cycle)
            
        # Track reviewers
        pr_reviewers = {review.user.login for review in reviews_by_date 
                       if review.user and review.user.login != pr.user.login}
        if pr_reviewers:
            repo_metrics['review_metrics']['reviewers_per_pr'][pr.number].update(pr_reviewers)
            
            # Track cross-team reviews
            if team_members:
                external_reviewers = [r for r in pr_reviewers if r not in team_members]
                if external_reviewers:
                    repo_metrics['collaboration']['cross_team_reviews'] += len(external_reviewers)
                    
    except Exception as e:
        logging.warning(f"Error processing review metrics for PR {pr.number}: {str(e)}")

    # Update user metrics alongside existing metrics
    if pr.merged:
        # Existing code for merged PRs
        repo_metrics['prs_merged'] += 1
        repo_metrics['user_contributions'][author]['merged'] += 1
        
        # Add merge timing per user
        merge_time = ensure_datetime(pr.merged_at)
        if merge_time:
            timing_key = 'weekends' if is_weekend(merge_time) else 'business_hours' if is_business_hours(merge_time) else 'after_hours'
            repo_metrics['user_contributions'][author]['merge_distribution'][timing_key] += 1

    # Update review metrics
    try:
        reviews = list(pr.get_reviews())
        for review in reviews:
            if not review.user:
                continue
                
            reviewer = review.user.login
            repo_metrics['user_contributions'][reviewer]['reviews_performed'] += 1
            
            if review.state == 'CHANGES_REQUESTED':
                repo_metrics['user_contributions'][reviewer]['blocking_reviews_given'] += 1
                
            # Track cross-team reviews
            if team_members and reviewer not in team_members:
                repo_metrics['user_contributions'][reviewer]['cross_team_reviews'] += 1
    except Exception as e:
        logging.warning(f"Error processing review metrics for PR {pr.number}: {str(e)}")

    # Update code metrics per user
    try:
        changes = pr.additions + pr.deletions
        files_changed = len(list(pr.get_files()))
        commits = len(list(pr.get_commits()))
        
        repo_metrics['user_contributions'][author]['changes_per_pr'].append(changes)
        repo_metrics['user_contributions'][author]['files_changed'].append(files_changed)
        repo_metrics['user_contributions'][author]['commits_count'].append(commits)
    except Exception as e:
        logging.warning(f"Error processing code metrics for PR {pr.number}: {str(e)}")

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
    """Display GitHub metrics with properly aligned tables."""
    console = Console()
    
    # Header
    console.print("\n[bold cyan]┌───────────────────────────────────┐")
    console.print("[bold cyan]│     🚀 GitHub Engineering Matrix  │")
    console.print("[bold cyan]└───────────────────────────────────┘")

    # 1. Core PR Metrics
    console.print("\n[bold green]📊 Pull Request Matrix")
    console.print("┌──────────────────────────┬─────────┐\n"
                  "│ PRs Created              │ {0:>7d} │\n"
                  "│ PRs Merged                {1:>7d} │\n"
                  "│ Merged to Main           │ {2:>7d} │\n"
                  "│ Deployment Freq          │ {3:>7.2f} │\n"
                  "│ Median Lead Time         │ {4:>6.1f}h │\n"
                  "└─────────────────────────┴─────────┘".format(
                      metrics.get('prs_created', 0),
                      metrics.get('prs_merged', 0),
                      metrics.get('prs_merged_to_main', 0),
                      metrics.get('deployment_frequency', 0),
                      metrics.get('median_lead_time', 0)))

    # 2. Review Process Metrics
    if 'review_metrics' in metrics:
        review = metrics['review_metrics']
        console.print("\n[bold yellow]🔍 Review Process Monitor")
        console.print("┌──────────────────────────┬─────────┐\n"
                      "│ Time to First Review     │ {0:>6.1f}h │\n"
                      "│ Review Cycles            │ {1:>7.1f} │\n"
                      "│ Blocking Reviews         │ {2:>7d} │\n"
                      "│ Unique Reviewers         │ {3:>7d} │\n"
                      "└─────────────────────────-┴─────────┘".format(
                         statistics.mean(review['time_to_first_review']) if review['time_to_first_review'] else 0,
                         statistics.mean(review['review_cycles']) if review['review_cycles'] else 0,
                         review.get('blocking_reviews', 0),
                         sum(len(r) for r in review['reviewers_per_pr'].values())))

    # 3. Code Quality Metrics
    if 'code_quality' in metrics:
        quality = metrics['code_quality']
        console.print("\n[bold magenta]🧬 Code Quality Scanner")
        console.print("┌──────────────────────────┬─────────┐\n"
                      "│ Avg Changes/PR           │ {0:>7.0f} │\n"
                      "│ Avg Files/PR             │ {1:>7.0f} │\n"
                      "│ Avg Commits/PR           │ {2:>7.0f} │\n"
                      "│ Reverts                  │ {3:>7d} │\n"
                      "│ Hotfixes                 │ {4:>7d} │\n"
                      "└──────────────────────────┴─────────┘".format(
                         statistics.mean(quality['changes_per_pr']) if quality['changes_per_pr'] else 0,
                         statistics.mean(quality['files_changed_per_pr']) if quality['files_changed_per_pr'] else 0,
                         statistics.mean(quality['commit_count_per_pr']) if quality['commit_count_per_pr'] else 0,
                         quality.get('revert_count', 0),
                         quality.get('hotfix_count', 0)))

    # 4. Collaboration Metrics
    if 'collaboration' in metrics:
        collab = metrics['collaboration']
        console.print("\n[bold cyan]🤝 Team Collaboration Grid")
        console.print("┌──────────────────────────┬─────────┐\n"
                      "│ Cross-Team Reviews       │ {0:>7d} │\n"
                      "│ Self-Merges              │ {1:>7d} │\n"
                      "│ Avg Comments/PR          │ {2:>7.1f} │\n"
                      "└──────────────────────────┴─────────┘".format(
                         collab.get('cross_team_reviews', 0),
                         collab.get('self_merges', 0),
                         statistics.mean(list(collab['review_comments_per_pr'].values())) if collab['review_comments_per_pr'] else 0))

    # 5. Bottleneck Indicators
    if 'bottleneck_metrics' in metrics:
        bottleneck = metrics['bottleneck_metrics']
        console.print("\n[bold red]⚠️  System Bottlenecks")
        console.print("┌──────────────────────────┬─────────┐\n"
                      "│ Stale PRs                │ {0:>7d} │\n"
                      "│ Long-Running PRs         │ {1:>7d} │\n"
                      "│ Avg Review Wait          │ {2:>6.1f}h │\n"
                      "└──────────────────────────┴─────────┘".format(
                         bottleneck.get('stale_prs', 0),
                         bottleneck.get('long_running_prs', 0),
                         statistics.mean(bottleneck['review_wait_time']) if bottleneck['review_wait_time'] else 0))

    # 6. User Contributions (Top 5)
    if metrics.get('user_contributions'):
        console.print("\n[bold green]👥 Top Contributors")
        table = ["┌─────────────────┬──────────────┬─────────────┐"]
        sorted_users = sorted(
            metrics['user_contributions'].items(),
            key=lambda x: x[1]['created'],
            reverse=True
        )[:5]
        for user, stats in sorted_users:
            table.append("│ {:<15}  Created: {:>3d} │ Merged: {:>3d} │".format(
                user, stats['created'], stats['merged']))
        table.append("└─────────────────┴──────────────┴─────────────┘")
        console.print("\n".join(table))

    # Add timing metrics display
    console.print("\n[bold blue]⏰ Merge Timing Analysis")
    console.print("┌──────────────────────────┬─────────┐")
    
    timing = metrics['timing_metrics']['merge_time_distribution']
    total_merges = sum(timing.values())
    
    if total_merges > 0:
        business_pct = (timing['business_hours'] / total_merges) * 100
        after_pct = (timing['after_hours'] / total_merges) * 100
        weekend_pct = (timing['weekends'] / total_merges) * 100
        
        console.print(f"│ Business Hours          │ {timing['business_hours']:>4d} ({business_pct:>3.0f}%) │")
        console.print(f"│ After Hours             │ {timing['after_hours']:>4d} ({after_pct:>3.0f}%) │")
        console.print(f"│ Weekends                │ {timing['weekends']:>4d} ({weekend_pct:>3.0f}%) │")
    else:
        console.print("│ Business Hours          │     0  │")
        console.print("│ After Hours             │     0  │")
        console.print("│ Weekends                │     0  │")
    
    console.print("└───────────────────────┴─────────┘")

def calculate_review_metrics(metrics):
    """Calculate summary review metrics."""
    review_metrics = metrics['review_metrics']
    
    # Calculate average review cycles
    review_cycles = review_metrics.get('review_cycles', [])
    avg_review_cycles = (
        statistics.mean(review_cycles)
        if review_cycles else 0
    )
    
    logging.info(f"Review Cycles - Count: {len(review_cycles)}, Avg: {avg_review_cycles:.1f}")
    
    return {
        'review_cycles': avg_review_cycles,
        'total_prs_with_reviews': len(review_cycles),
        'blocking_reviews': review_metrics['blocking_reviews']
    }

def calculate_collaboration_metrics(metrics):
    """Calculate collaboration metrics including average comments."""
    collab_metrics = metrics['collaboration']
    
    # Calculate average comments per PR
    total_comments = sum(collab_metrics['review_comments_per_pr'].values())
    total_prs = len(collab_metrics['review_comments_per_pr'])
    avg_comments = total_comments / total_prs if total_prs > 0 else 0
    
    return {
        'cross_team_reviews': collab_metrics['cross_team_reviews'],
        'self_merges': collab_metrics['self_merges'],
        'avg_comments_per_pr': avg_comments
    }

def calculate_bottleneck_metrics(metrics):
    """Calculate summary bottleneck metrics."""
    bottleneck = metrics['bottleneck_metrics']
    
    avg_wait_time = (
        statistics.mean(bottleneck['review_wait_time'])
        if bottleneck['review_wait_time'] else 0
    )
    
    return {
        'stale_prs': bottleneck['stale_prs'],
        'long_running_prs': bottleneck['long_running_prs'],
        'avg_review_wait': avg_wait_time
    }

def calculate_summary_metrics(metrics):
    """Calculate summary metrics including lead time."""
    try:
        lead_times = metrics.get('lead_times', [])
        if lead_times:
            median_lead_time = statistics.median(lead_times)
            avg_lead_time = statistics.mean(lead_times)
            
            logging.info(f"Lead Times - Count: {len(lead_times)}, Median: {median_lead_time:.1f}h, Avg: {avg_lead_time:.1f}h")
            
            return {
                'median_lead_time': median_lead_time,
                'avg_lead_time': avg_lead_time,
                'total_prs_with_lead_time': len(lead_times)
            }
    except Exception as e:
        logging.error(f"Error calculating lead time metrics: {str(e)}")
        return {'median_lead_time': 0, 'avg_lead_time': 0, 'total_prs_with_lead_time': 0}

