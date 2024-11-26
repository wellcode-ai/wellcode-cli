from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from github import Github
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
import logging
from . import decorators
from .utils import ensure_datetime
from ..config import get_github_token
from .models.metrics import OrganizationMetrics
from requests.adapters import HTTPAdapter
import threading
from urllib3.util import Retry
import requests
import atexit
console = Console()

# Global thread pool executors
MAIN_EXECUTOR = ThreadPoolExecutor(max_workers=8)
PR_EXECUTOR = ThreadPoolExecutor(max_workers=4)
DATA_EXECUTOR = ThreadPoolExecutor(max_workers=6)

# Register cleanup on program exit
def cleanup_executors():
    MAIN_EXECUTOR.shutdown(wait=True)
    PR_EXECUTOR.shutdown(wait=True)
    DATA_EXECUTOR.shutdown(wait=True)

atexit.register(cleanup_executors)

# Global semaphore to control concurrent connections
connection_semaphore = threading.Semaphore(15)  # Increased from 8 to 15

# Create a global session with proper pooling
def create_global_session():
    session = requests.Session()
    
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    
    # Increase pool settings to match our thread pool sizes
    adapter = HTTPAdapter(
        pool_connections=100,
        pool_maxsize=100,
        max_retries=retry_strategy,
        pool_block=True
    )
    
    session.mount('https://', adapter)
    return session

# Global session and semaphore
GITHUB_SESSION = create_global_session()

class GithubClient:
    """Thread-safe GitHub client wrapper"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, token):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance.token = token
                cls._instance._local = threading.local()
            return cls._instance
    
    @property
    def client(self):
        if not hasattr(self._local, 'github'):
            self._local.github = Github(
                login_or_token=self.token,
                per_page=100,
                retry=3,
                timeout=30,
            )
            self._local.github._Github__requester._Requester__session = GITHUB_SESSION
        return self._local.github

def get_github_client():
    """Get a thread-local GitHub client with proper connection pooling"""
    return GithubClient(get_github_token())

def safe_github_call(func):
    """Decorator to ensure safe GitHub API calls with semaphore"""
    def wrapper(*args, **kwargs):
        with connection_semaphore:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logging.error(f"GitHub API call failed: {str(e)}")
                raise
    return wrapper

@decorators.handle_github_errors()
def get_github_metrics(org_name: str, start_date, end_date, user_filter=None, team_filter=None) -> OrganizationMetrics:
    """Main function with proper connection handling"""
    github_client = get_github_client()
    
    with connection_semaphore:
        org = github_client.client.get_organization(org_name)
        repo_future = MAIN_EXECUTOR.submit(lambda: list(org.get_repos()))
        team_future = MAIN_EXECUTOR.submit(get_team_members, org, team_filter) if team_filter else None
        
        repos = repo_future.result()
        team_members = team_future.result() if team_filter else set()
    
    org_metrics = OrganizationMetrics(name=org_name)
    
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task(description="Processing repositories...", total=len(repos))
        
        futures = [
            MAIN_EXECUTOR.submit(
                process_repository_batch,
                repo, org_metrics, start_date, end_date,
                user_filter, team_filter, team_members
            ) for repo in repos
        ]
        
        for future in as_completed(futures):
            try:
                future.result()
                progress.advance(task)
            except Exception as e:
                logging.error(f"Error processing repository: {str(e)}")
    
    return org_metrics

def process_repository_batch(repo, org_metrics, start_date, end_date, user_filter, team_filter, team_members):
    """Process repository with proper connection handling"""
    try:
        with connection_semaphore:
            pulls_future = DATA_EXECUTOR.submit(lambda: list(repo.get_pulls(state='all')))
            pulls = pulls_future.result()
        
        start_date = ensure_datetime(start_date)
        end_date = ensure_datetime(end_date)
        
        relevant_pulls = [
            pr for pr in pulls 
            if start_date <= ensure_datetime(pr.created_at) <= end_date
            and (not user_filter or pr.user.login == user_filter)
        ]
        
        # Create repo metrics instance and update contributors
        repo_metrics = org_metrics.get_or_create_repository(repo.name)
        repo_metrics.default_branch = repo.default_branch
        
        # Track PR counts
        repo_metrics.prs_created += len(relevant_pulls)
        merged_prs = [pr for pr in relevant_pulls if pr.merged]
        repo_metrics.prs_merged += len(merged_prs)
        repo_metrics.prs_merged_to_main += sum(1 for pr in merged_prs if pr.base.ref == repo_metrics.default_branch)
        
        # Add contributor tracking
        for pr in relevant_pulls:
            repo_metrics.contributors.add(pr.user.login)
            if hasattr(pr.user, 'team'):
                repo_metrics.teams_involved.add(pr.user.team)
        
        # Update timestamp
        repo_metrics.update_timestamp()
        
        # Process in smaller batches
        batch_size = 50
        for i in range(0, len(relevant_pulls), batch_size):
            batch = relevant_pulls[i:i + batch_size]
            
            futures = {
                PR_EXECUTOR.submit(process_pr, pr, repo_metrics, org_metrics, start_date, end_date): pr 
                for pr in batch
            }
            
            for future in as_completed(futures):
                pr = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logging.error(f"Error processing PR {pr.number}: {str(e)}")                    
            
    except Exception as e:
        logging.error(f"Error processing repository {repo.name}: {str(e)}")
        raise

@safe_github_call
def process_pr(pr, repo_metrics, org_metrics, start_date, end_date):
    """Process a single PR with optimized data fetching"""
    try:
        pr_data = collect_pr_data(pr)
        
        futures = [
            DATA_EXECUTOR.submit(update_code_metrics, pr, repo_metrics, org_metrics),
            DATA_EXECUTOR.submit(update_review_metrics, pr, pr_data, repo_metrics, org_metrics),
            DATA_EXECUTOR.submit(update_time_metrics, pr, pr_data.get('commits', []), 
                               repo_metrics, org_metrics, start_date, end_date),
            DATA_EXECUTOR.submit(update_collaboration_metrics, pr, pr_data.get('reviews', []), 
                               repo_metrics, org_metrics)
        ]
        
        # Wait for all updates to complete
        for future in as_completed(futures):
            future.result()
            
    except Exception as e:
        logging.error(f"Error processing PR {pr.number}: {str(e)}")
        raise

@safe_github_call
def collect_pr_data(pr):
    """Collect PR data with proper connection handling"""
    if not pr.merged:
        # Skip commit fetching for unmerged PRs
        futures = {
            'reviews': DATA_EXECUTOR.submit(lambda: list(pr.get_reviews())),
            'review_comments': DATA_EXECUTOR.submit(lambda: list(pr.get_review_comments())),
            'issue_comments': DATA_EXECUTOR.submit(lambda: list(pr.get_issue_comments())),
            'commits': []
        }
    else:
        futures = {
            'reviews': DATA_EXECUTOR.submit(lambda: list(pr.get_reviews())),
            'review_comments': DATA_EXECUTOR.submit(lambda: list(pr.get_review_comments())),
            'issue_comments': DATA_EXECUTOR.submit(lambda: list(pr.get_issue_comments())),
            'commits': DATA_EXECUTOR.submit(lambda: list(pr.get_commits()))
        }
    
    return {key: future.result() if isinstance(future, Future) else future 
            for key, future in futures.items()}

def update_code_metrics(pr, repo_metrics, org_metrics):
    """Update code metrics for a PR"""
    org_metrics.code_metrics.update_from_pr(pr)
    repo_metrics.code_metrics.update_from_pr(pr)

def update_review_metrics(pr, pr_data, repo_metrics, org_metrics):
    """Update review metrics for a PR"""
    reviews = pr_data['reviews']
    review_comments = pr_data['review_comments']
    issue_comments = pr_data['issue_comments']
    
    # Update PR author's received comments
    org_metrics.review_metrics.review_comments_received += len(review_comments)
    
    # Process all comments
    for comment in review_comments + issue_comments:
        if not comment.user:
            continue
        
        commenter = comment.user.login
        commenter_metrics = org_metrics.get_or_create_user(commenter)
        
        # Update comment counts
        commenter_metrics.review_metrics.review_comments_given += 1
        repo_metrics.review_metrics.review_comments_given += 1
        org_metrics.review_metrics.review_comments_given += 1
        
        # Update collaboration metrics
        commenter_metrics.collaboration_metrics.update_from_comments([comment], pr.number)
        repo_metrics.collaboration_metrics.update_from_comments([comment], pr.number)
        org_metrics.collaboration_metrics.update_from_comments([comment], pr.number)
    
    # Process reviews
    process_reviews(pr, reviews, repo_metrics, org_metrics)
    
    if reviews:
        first_review = min(reviews, key=lambda r: r.submitted_at)
        wait_time = (first_review.submitted_at - pr.created_at).total_seconds() / 60  # Convert to minutes
        org_metrics.bottleneck_metrics.review_wait_times.append(wait_time)
        repo_metrics.bottleneck_metrics.review_wait_times.append(wait_time)
    
    for review in reviews:
        if review.submitted_at and pr.created_at:
            response_time = (review.submitted_at - pr.created_at).total_seconds() / 60
            org_metrics.bottleneck_metrics.review_response_times.append(response_time)
            repo_metrics.bottleneck_metrics.review_response_times.append(response_time)

def update_time_metrics(pr, commits, repo_metrics, org_metrics, start_date, end_date):
    """Update time metrics for a PR"""
    if pr.merged_at:
        merge_time = ensure_datetime(pr.merged_at)
        
        # Update merge distribution
        if merge_time.weekday() >= 5:  # Weekend
            repo_metrics.time_metrics.merge_distribution['weekends'] += 1
            org_metrics.time_metrics.merge_distribution['weekends'] += 1
        elif 9 <= merge_time.hour < 17:  # Business hours (simplified)
            repo_metrics.time_metrics.merge_distribution['business_hours'] += 1
            org_metrics.time_metrics.merge_distribution['business_hours'] += 1
        else:  # After hours
            repo_metrics.time_metrics.merge_distribution['after_hours'] += 1
            org_metrics.time_metrics.merge_distribution['after_hours'] += 1
            
        # Calculate deployment frequency (merges per day to main branch)
        if pr.base.ref == repo_metrics.default_branch:
            one_day_seconds = 24 * 60 * 60
            days_in_period = (end_date - start_date).total_seconds() / one_day_seconds
            repo_metrics.time_metrics.deployment_frequency = repo_metrics.prs_merged_to_main / days_in_period
            org_metrics.time_metrics.deployment_frequency = org_metrics.prs_merged_to_main / days_in_period

    # ... rest of existing update_time_metrics code ...

def process_reviews(pr, reviews, repo_metrics, org_metrics):
    """Process reviews for a PR"""
    sorted_reviews = sorted(reviews, key=lambda r: r.submitted_at)
    review_cycles = sum(1 for review in sorted_reviews if review.state == 'CHANGES_REQUESTED')
    
    if review_cycles > 0:
        repo_metrics.review_metrics.review_cycles.append(review_cycles)
        org_metrics.review_metrics.review_cycles.append(review_cycles)
    
    for review in reviews:
        if not review.user:
            continue
        
        reviewer = review.user.login
        reviewer_metrics = org_metrics.get_or_create_user(reviewer)
        
        # Update review metrics
        reviewer_metrics.review_metrics.update_from_review(review, pr)
        repo_metrics.review_metrics.update_from_review(review, pr)
        org_metrics.review_metrics.update_from_review(review, pr)
        
        # Update collaboration metrics
        update_collaboration_metrics(pr, review, repo_metrics, org_metrics, reviewer_metrics)

def update_collaboration_metrics(pr, reviews, repo_metrics, org_metrics):
    """Update collaboration metrics including participation rate"""
    # Process reviews for collaboration
    if reviews:
        repo_metrics.collaboration_metrics.self_merges += 1
        org_metrics.collaboration_metrics.self_merges += 1
    
    # Update collaboration metrics at all levels
    repo_metrics.collaboration_metrics.update_from_reviews(
        reviews, pr,
        author_team=pr.user.team,
        reviewer_team=reviews[0].user.team
    )
    org_metrics.collaboration_metrics.update_from_reviews(
        reviews, pr,
        author_team=pr.user.team,
        reviewer_team=reviews[0].user.team
    )
    
    # Update team reviews
    if reviews[0].user.team and pr.user.team:
        if reviews[0].user.team == pr.user.team:
            repo_metrics.collaboration_metrics.team_reviews += 1
            org_metrics.collaboration_metrics.team_reviews += 1
        else:
            repo_metrics.collaboration_metrics.cross_team_reviews += 1
            org_metrics.collaboration_metrics.cross_team_reviews += 1
    else:
        repo_metrics.collaboration_metrics.external_reviews += 1
        org_metrics.collaboration_metrics.external_reviews += 1
    
    # Calculate review participation rate
    total_reviews = repo_metrics.collaboration_metrics.team_reviews + \
                   repo_metrics.collaboration_metrics.cross_team_reviews + \
                   repo_metrics.collaboration_metrics.external_reviews
    total_prs = repo_metrics.prs_merged + repo_metrics.collaboration_metrics.self_merges
    
    if total_prs > 0:
        repo_metrics.collaboration_metrics.review_participation_rate = total_reviews / total_prs
        org_metrics.collaboration_metrics.review_participation_rate = \
            (org_metrics.collaboration_metrics.team_reviews + \
             org_metrics.collaboration_metrics.cross_team_reviews + \
             org_metrics.collaboration_metrics.external_reviews) / \
            (org_metrics.prs_merged + org_metrics.collaboration_metrics.self_merges)

def get_team_members(org, team_filter: str) -> set:
    """Get team members for a specific team"""
    team_members = set()
    try:
        teams = list(org.get_teams())
        team = next(
            (t for t in teams if t.name.lower() == team_filter.lower() or t.slug.lower() == team_filter.lower()),
            None
        )
        if team:
            team_members = {member.login for member in team.get_members(role='all')}
            console.print(f"[yellow]Found {len(team_members)} team members[/]")
        else:
            console.print(f"[red]Team '{team_filter}' not found[/]")
    except Exception as e:
        console.print(f"[red]Warning: Could not fetch team members for {team_filter}: {str(e)}[/]")
    
    return team_members

def update_bottleneck_metrics(pr, repo_metrics, org_metrics):
    """Add missing bottleneck metrics tracking"""
    repo_metrics.bottleneck_metrics.update_from_pr(pr)
    org_metrics.bottleneck_metrics.update_from_pr(pr)

