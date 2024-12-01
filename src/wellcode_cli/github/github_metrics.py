import atexit
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from . import decorators
from .app_config import WELLCODE_APP
from .client import GithubClient
from .models.metrics import OrganizationMetrics
from .utils import ensure_datetime

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
connection_semaphore = threading.Semaphore(15)


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
def get_github_metrics(
    org_or_user: str, start_date, end_date, user_filter=None, team_filter=None
) -> OrganizationMetrics:
    """Main function with proper connection handling"""
    try:
        github_client = GithubClient()
        mode = github_client.get_config().get("GITHUB_MODE", "organization")

        with connection_semaphore:
            if mode == "organization":
                # Verify organization access first
                try:
                    org = github_client.client.get_organization(org_or_user)
                    _ = org.login  # Test access
                except Exception as e:
                    console.print(
                        f"[red]Error: Cannot access organization {org_or_user}[/]"
                    )
                    console.print("[yellow]Please verify:")
                    console.print("1. You have the correct organization name")
                    console.print("2. You have organization membership")
                    console.print("3. Your token has 'read:org' scope")
                    logging.error(f"Organization access error: {str(e)}")
                    return None

                # Then check app installation
                if not github_client._check_app_installation(org_or_user):
                    console.print("[red]Error: GitHub App not installed[/]")
                    console.print(
                        f"Please install the app at: {WELLCODE_APP['APP_URL']}"
                    )
                    console.print("And select your organization during installation")
                    return None

                repo_future = MAIN_EXECUTOR.submit(lambda: list(org.get_repos()))
            else:
                # Personal mode - use authenticated user
                user = github_client.client.get_user()
                repo_future = MAIN_EXECUTOR.submit(lambda: list(user.get_repos()))
                org_or_user = user.login

            repos = repo_future.result()

            # Only attempt team operations in organization mode
            team_members = set()
            if mode == "organization" and team_filter:
                team_future = MAIN_EXECUTOR.submit(get_team_members, org, team_filter)
                team_members = team_future.result()

        metrics = OrganizationMetrics(name=org_or_user)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(
                description="Processing repositories...", total=len(repos)
            )

            futures = [
                MAIN_EXECUTOR.submit(
                    process_repository_batch,
                    repo,
                    metrics,
                    start_date,
                    end_date,
                    user_filter,
                    team_filter,
                    team_members,
                )
                for repo in repos
            ]

            for future in as_completed(futures):
                try:
                    future.result()
                    progress.advance(task)
                except Exception as e:
                    logging.error(f"Error processing repository: {str(e)}")

        return metrics

    except Exception as e:
        logging.error(f"Error getting GitHub metrics: {str(e)}")
        raise


def process_repository_batch(
    repo, org_metrics, start_date, end_date, user_filter, team_filter, team_members
):
    """Process repository with proper connection handling"""
    try:
        with connection_semaphore:
            pulls_future = DATA_EXECUTOR.submit(
                lambda: list(repo.get_pulls(state="all"))
            )
            pulls = pulls_future.result()

        start_date = ensure_datetime(start_date)
        end_date = ensure_datetime(end_date)

        relevant_pulls = [
            pr
            for pr in pulls
            if start_date <= ensure_datetime(pr.created_at) <= end_date
            and (not user_filter or pr.user.login == user_filter)
        ]

        # Create repo metrics instance and update contributors
        repo_metrics = org_metrics.get_or_create_repository(repo.name)
        repo_metrics.default_branch = repo.default_branch

        # Track PR counts for both repo and org
        repo_metrics.prs_created += len(relevant_pulls)
        org_metrics.prs_created += len(relevant_pulls)

        merged_prs = [pr for pr in relevant_pulls if pr.merged]
        repo_metrics.prs_merged += len(merged_prs)
        org_metrics.prs_merged += len(merged_prs)

        merged_to_main = sum(
            1 for pr in merged_prs if pr.base.ref == repo_metrics.default_branch
        )
        repo_metrics.prs_merged_to_main += merged_to_main
        org_metrics.prs_merged_to_main += merged_to_main

        # Track direct merges to main
        direct_to_main = sum(
            1
            for pr in merged_prs
            if pr.base.ref == repo_metrics.default_branch
            and pr.head.ref == repo_metrics.default_branch
        )
        repo_metrics.direct_merges_to_main += direct_to_main
        org_metrics.direct_merges_to_main += direct_to_main

        # Add contributor tracking
        for pr in relevant_pulls:
            repo_metrics.contributors.add(pr.user.login)
            if hasattr(pr.user, "team"):
                repo_metrics.teams_involved.add(pr.user.team)

        # Update timestamp
        repo_metrics.update_timestamp()

        # Process in smaller batches
        batch_size = 50
        for i in range(0, len(relevant_pulls), batch_size):
            batch = relevant_pulls[i : i + batch_size]

            futures = {
                PR_EXECUTOR.submit(
                    process_pr, pr, repo_metrics, org_metrics, start_date, end_date
                ): pr
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
        logging.info(f"Starting to process PR #{pr.number} by {pr.user.login}")

        # Add PR author to contributors and create user metrics
        repo_metrics.contributors.add(pr.user.login)
        org_metrics.get_or_create_user(pr.user.login)

        pr_data = collect_pr_data(pr)

        futures = [
            DATA_EXECUTOR.submit(update_code_metrics, pr, repo_metrics, org_metrics),
            DATA_EXECUTOR.submit(
                update_review_metrics, pr, pr_data, repo_metrics, org_metrics
            ),
            DATA_EXECUTOR.submit(
                update_time_metrics,
                pr,
                pr_data.get("commits", []),
                repo_metrics,
                org_metrics,
                start_date,
                end_date,
            ),
            DATA_EXECUTOR.submit(
                update_collaboration_metrics,
                pr,
                pr_data.get("reviews", []),
                repo_metrics,
                org_metrics,
            ),
        ]

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
            "reviews": DATA_EXECUTOR.submit(lambda: list(pr.get_reviews())),
            "review_comments": DATA_EXECUTOR.submit(
                lambda: list(pr.get_review_comments())
            ),
            "issue_comments": DATA_EXECUTOR.submit(
                lambda: list(pr.get_issue_comments())
            ),
            "commits": [],
        }
    else:
        futures = {
            "reviews": DATA_EXECUTOR.submit(lambda: list(pr.get_reviews())),
            "review_comments": DATA_EXECUTOR.submit(
                lambda: list(pr.get_review_comments())
            ),
            "issue_comments": DATA_EXECUTOR.submit(
                lambda: list(pr.get_issue_comments())
            ),
            "commits": DATA_EXECUTOR.submit(lambda: list(pr.get_commits())),
        }

    return {
        key: future.result() if isinstance(future, Future) else future
        for key, future in futures.items()
    }


def update_code_metrics(pr, repo_metrics, org_metrics):
    """Update code metrics for a PR"""
    # Update organization and repository metrics
    org_metrics.code_metrics.update_from_pr(pr)
    repo_metrics.code_metrics.update_from_pr(pr)

    # Update author's code metrics
    author_metrics = org_metrics.get_or_create_user(pr.user.login)
    author_metrics.code_metrics.update_from_pr(pr)


def update_review_metrics(pr, pr_data, repo_metrics, org_metrics):
    """Update review metrics for a PR"""
    reviews = pr_data["reviews"]
    review_comments = pr_data["review_comments"]
    issue_comments = pr_data["issue_comments"]

    # Get author metrics and update received comments
    author_metrics = org_metrics.get_or_create_user(pr.user.login)
    author_metrics.review_metrics.review_comments_received += len(review_comments)

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
        commenter_metrics.collaboration_metrics.update_from_comments(
            [comment], pr.number
        )
        repo_metrics.collaboration_metrics.update_from_comments([comment], pr.number)
        org_metrics.collaboration_metrics.update_from_comments([comment], pr.number)
    # Process reviews
    process_reviews(pr, reviews, repo_metrics, org_metrics)
    if reviews:
        first_review = min(reviews, key=lambda r: r.submitted_at)
        wait_time = (
            first_review.submitted_at - pr.created_at
        ).total_seconds() / 60  # Convert to minutes

        # Add to author metrics
        author_metrics.review_metrics.review_wait_times.append(wait_time)

        org_metrics.bottleneck_metrics.review_wait_times.append(wait_time)
        repo_metrics.bottleneck_metrics.review_wait_times.append(wait_time)
    for review in reviews:
        if review.submitted_at and pr.created_at:
            response_time = (review.submitted_at - pr.created_at).total_seconds() / 60

            # Add to author metrics
            author_metrics.review_metrics.time_to_first_review.append(response_time)

            org_metrics.bottleneck_metrics.review_response_times.append(response_time)
            repo_metrics.bottleneck_metrics.review_response_times.append(response_time)
        org_metrics.bottleneck_metrics.review_wait_times.append(wait_time)


def update_time_metrics(pr, commits, repo_metrics, org_metrics, start_date, end_date):
    """Update time metrics for a PR"""
    try:
        if pr.merged_at:
            # Get author metrics
            author_metrics = org_metrics.get_or_create_user(pr.user.login)

            # Convert all times to datetime with timezone
            merge_time = ensure_datetime(pr.merged_at)
            created_time = ensure_datetime(pr.created_at)
            # Calculate time to merge in hours
            merge_duration = (merge_time - created_time).total_seconds() / 3600

            # Add author metrics
            author_metrics.time_metrics.time_to_merge.append(merge_duration)

            repo_metrics.time_metrics.time_to_merge.append(merge_duration)
            org_metrics.time_metrics.time_to_merge.append(merge_duration)
            # Calculate lead time if we have commits
            if commits and len(commits) > 0:
                first_commit = min(
                    commits, key=lambda c: ensure_datetime(c.commit.author.date)
                )
                first_commit_date = ensure_datetime(first_commit.commit.author.date)
                lead_time = (merge_time - first_commit_date).total_seconds() / 3600

                # Add author metrics
                author_metrics.time_metrics.lead_times.append(lead_time)
                repo_metrics.time_metrics.lead_times.append(lead_time)
                org_metrics.time_metrics.lead_times.append(lead_time)
                # Calculate cycle time
                cycle_time = (merge_time - first_commit_date).total_seconds() / 3600

                # Add author metrics
                author_metrics.time_metrics.cycle_time.append(cycle_time)
                repo_metrics.time_metrics.cycle_time.append(cycle_time)
                org_metrics.time_metrics.cycle_time.append(cycle_time)
            # Update merge distribution
            if merge_time.weekday() >= 5:  # Weekend
                # Add author metrics
                author_metrics.time_metrics.merge_distribution["weekends"] += 1
                repo_metrics.time_metrics.merge_distribution["weekends"] += 1
                org_metrics.time_metrics.merge_distribution["weekends"] += 1
            elif 9 <= merge_time.hour < 17:  # Business hours
                # Add author metrics
                author_metrics.time_metrics.merge_distribution["business_hours"] += 1
                repo_metrics.time_metrics.merge_distribution["business_hours"] += 1
                org_metrics.time_metrics.merge_distribution["business_hours"] += 1
            else:  # After hours
                # Add author metrics
                author_metrics.time_metrics.merge_distribution["after_hours"] += 1
                repo_metrics.time_metrics.merge_distribution["after_hours"] += 1
                org_metrics.time_metrics.merge_distribution["after_hours"] += 1
                
            # Calculate deployment frequency with safety check
            if pr.base.ref == repo_metrics.default_branch:
                one_day_seconds = 24 * 60 * 60
                days_in_period = max(
                    (end_date - start_date).total_seconds() / one_day_seconds, 1
                )  # Ensure minimum 1 day
                # Add safety checks for division
                if days_in_period > 0:
                    if repo_metrics.prs_merged_to_main > 0:
                        repo_metrics.time_metrics.deployment_frequency = (
                            repo_metrics.prs_merged_to_main / days_in_period
                        )
                    if org_metrics.prs_merged_to_main > 0:
                        org_metrics.time_metrics.deployment_frequency = (
                            org_metrics.prs_merged_to_main / days_in_period
                        )
    except Exception as e:
        logging.error(f"Error in update_time_metrics: {str(e)}")
        # Continue processing even if there's an error with one PR
        pass


def process_reviews(pr, reviews, repo_metrics, org_metrics):
    """Process reviews for a PR"""
    sorted_reviews = sorted(reviews, key=lambda r: r.submitted_at)
    review_cycles = sum(
        1 for review in sorted_reviews if review.state == "CHANGES_REQUESTED"
    )

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

        # Fix: Remove reviewer_metrics from this call
        update_collaboration_metrics(pr, reviews, repo_metrics, org_metrics)


def update_collaboration_metrics(pr, reviews, repo_metrics, org_metrics):
    """Update collaboration metrics including participation rate"""
    # Check for self-merges by comparing PR author with merger
    if pr.merged and pr.merged_by and pr.user.login == pr.merged_by.login:
        repo_metrics.collaboration_metrics.self_merges += 1
        org_metrics.collaboration_metrics.self_merges += 1

        # Update author's metrics
        author_metrics = org_metrics.get_or_create_user(pr.user.login)
        author_metrics.collaboration_metrics.self_merges += 1

    # Update collaboration metrics at all levels
    if (
        reviews
        and len(reviews) > 0
        and hasattr(pr.user, "team")
        and hasattr(reviews[0].user, "team")
    ):
        repo_metrics.collaboration_metrics.update_from_reviews(
            reviews, pr, author_team=pr.user.team, reviewer_team=reviews[0].user.team
        )
        org_metrics.collaboration_metrics.update_from_reviews(
            reviews, pr, author_team=pr.user.team, reviewer_team=reviews[0].user.team
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
    # Calculate review participation rate for repository
    repo_total_reviews = (
        repo_metrics.collaboration_metrics.team_reviews
        + repo_metrics.collaboration_metrics.cross_team_reviews
        + repo_metrics.collaboration_metrics.external_reviews
    )
    if repo_metrics.prs_created > 0:
        repo_metrics.collaboration_metrics.review_participation_rate = (
            repo_total_reviews / repo_metrics.prs_created
        )
    # Calculate review participation rate for organization
    org_total_reviews = (
        org_metrics.collaboration_metrics.team_reviews
        + org_metrics.collaboration_metrics.cross_team_reviews
        + org_metrics.collaboration_metrics.external_reviews
    )
    # Fix: Use prs_created instead of total_prs
    if org_metrics.prs_created > 0:  # Changed from total_prs to prs_created
        org_metrics.collaboration_metrics.review_participation_rate = (
            org_total_reviews / org_metrics.prs_created
        )


# Create console instance
console = Console()


def get_team_members(org_or_user, team_filter: str) -> set:
    """Get team members for a specific team"""
    team_members = set()

    # Skip team lookup for personal mode
    if not hasattr(org_or_user, "get_teams"):
        return team_members

    try:
        teams = list(org_or_user.get_teams())
        team = next(
            (
                t
                for t in teams
                if t.name.lower() == team_filter.lower()
                or t.slug.lower() == team_filter.lower()
            ),
            None,
        )
        if team:
            team_members = {member.login for member in team.get_members(role="all")}
            console.print(f"[yellow]Found {len(team_members)} team members[/]")
        else:
            console.print(f"[red]Team '{team_filter}' not found[/]")
    except Exception as e:
        console.print(
            f"[red]Warning: Could not fetch team members for {team_filter}: {str(e)}[/]"
        )

    return team_members


def update_bottleneck_metrics(pr, repo_metrics, org_metrics):
    """Add missing bottleneck metrics tracking"""
    repo_metrics.bottleneck_metrics.update_from_pr(pr)
    org_metrics.bottleneck_metrics.update_from_pr(pr)
