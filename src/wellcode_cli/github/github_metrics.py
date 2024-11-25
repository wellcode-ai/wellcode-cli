from github import Github
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
import logging
import statistics

from .models.metrics import (
    OrganizationMetrics, RepositoryMetrics
)
from ..config import GITHUB_TOKEN
from .utils import ensure_datetime

console = Console()

def get_github_metrics(org_name: str, start_date, end_date, user_filter=None, team_filter=None) -> OrganizationMetrics:
    """Main function to get GitHub metrics for an organization"""
    g = Github(GITHUB_TOKEN)
    org = g.get_organization(org_name)
    
    # Ensure start_date and end_date are timezone-aware
    start_date = ensure_datetime(start_date)
    end_date = ensure_datetime(end_date)
    
    # Initialize organization metrics
    org_metrics = OrganizationMetrics(name=org_name)
    
    # Get team members if team filter is specified
    team_members = get_team_members(org, team_filter) if team_filter else set()
    
    # Process repositories
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task(description="Processing repositories...", total=None)
        
        for repo in org.get_repos():
            try:
                process_repository(repo, org_metrics, start_date, end_date, user_filter, team_filter, team_members)
            except Exception as e:
                logging.error(f"Error processing repository {repo.name}: {str(e)}")
                continue
    
    # Aggregate metrics before returning
    org_metrics.aggregate_metrics()
    
    # Log organization metrics before returning
    logging.info("\n=== Organization Metrics Summary ===")
    logging.info(f"Organization: {org_metrics.name}")
    logging.info(f"Repositories processed: {len(org_metrics.repositories)}")
    logging.info(f"Total contributors: {len(org_metrics.get_all_contributors())}")
    
    logging.info("\nCode Metrics:")
    code_stats = org_metrics.code_metrics.get_stats()
    for key, value in code_stats.items():
        logging.info(f"- {key}: {value}")
    
    logging.info("\nReview Metrics:")
    review_stats = org_metrics.review_metrics.get_stats()
    for key, value in review_stats.items():
        logging.info(f"- {key}: {value}")
    
    logging.info("\nTime Metrics:")
    time_stats = org_metrics.time_metrics.get_stats()
    for key, value in time_stats.items():
        if isinstance(value, dict):  # For nested dictionaries like merge_distribution
            logging.info(f"- {key}:")
            for sub_key, sub_value in value.items():
                logging.info(f"  • {sub_key}: {sub_value}")
        else:
            logging.info(f"- {key}: {value}")
    
    logging.info("\nCollaboration Metrics:")
    collab_stats = org_metrics.collaboration_metrics.get_stats()
    for key, value in collab_stats.items():
        logging.info(f"- {key}: {value}")
    
    logging.info("\nBottleneck Metrics:")
    bottleneck_stats = org_metrics.bottleneck_metrics.get_stats()
    for key, value in bottleneck_stats.items():
        logging.info(f"- {key}: {value}")
    
    logging.info("\nPer Repository:")
    for repo_name, repo in org_metrics.repositories.items():
        logging.info(f"\n{repo_name}:")
        stats = {
            'prs_created': repo.prs_created,
            'prs_merged': repo.prs_merged,
            'contributors': len(repo.contributors),
            'teams_involved': len(repo.teams_involved),
            'avg_time_to_merge': statistics.mean(repo.time_metrics.time_to_merge) if repo.time_metrics.time_to_merge else 0,
            'avg_review_time': statistics.mean(repo.review_metrics.review_wait_times) if repo.review_metrics.review_wait_times else 0,
            'hotfixes': repo.code_metrics.hotfixes,
            'reverts': repo.code_metrics.reverts,
            'last_updated': repo.last_updated
        }
        for key, value in stats.items():
            logging.info(f"- {key}: {value}")
    
    logging.info("\nUser Metrics:")
    for username, user in org_metrics.users.items():
        logging.info(f"\n=== {username} ===")
        logging.info("Basic Info:")
        logging.info(f"- Team: {user.team}")
        logging.info(f"- Role: {user.role}")
        logging.info(f"- PRs Created: {user.prs_created}")
        logging.info(f"- PRs Merged: {user.prs_merged}")
        
        logging.info("\nCode Activity:")
        code_stats = user.code_metrics.get_stats()
        for key, value in code_stats.items():
            logging.info(f"- {key}: {value}")
        
        logging.info("\nReview Activity:")
        review_stats = user.review_metrics.get_stats()
        for key, value in review_stats.items():
            logging.info(f"- {key}: {value}")
        
        logging.info("\nTime Metrics:")
        time_stats = user.time_metrics.get_stats()
        for key, value in time_stats.items():
            if isinstance(value, dict):
                logging.info(f"- {key}:")
                for sub_key, sub_value in value.items():
                    logging.info(f"  • {sub_key}: {sub_value}")
            else:
                logging.info(f"- {key}: {value}")
        
        logging.info("\nCollaboration Activity:")
        collab_stats = user.collaboration_metrics.get_stats()
        for key, value in collab_stats.items():
            logging.info(f"- {key}: {value}")
    
    return org_metrics

def process_repository(repo, org_metrics: OrganizationMetrics, start_date, end_date, 
                      user_filter=None, team_filter=None, team_members=None):
    """Process a single repository's metrics"""
    repo_metrics = org_metrics.get_or_create_repository(repo.name, repo.default_branch)
    
    # Initialize last_updated to start_date
    repo_metrics.last_updated = start_date
    
    pulls = repo.get_pulls(state='all')
    for pr in pulls:
        try:
            pr_created = ensure_datetime(pr.created_at)
            if not (start_date <= pr_created <= end_date):
                continue
                
            # Update repository timestamp with PR creation date
            if pr_created > repo_metrics.last_updated:
                repo_metrics.last_updated = pr_created
            
            # If PR is merged, also check merge date
            if pr.merged:
                merge_date = ensure_datetime(pr.merged_at)
                if merge_date > repo_metrics.last_updated and merge_date <= end_date:
                    repo_metrics.last_updated = merge_date
            
            process_pr(pr, repo_metrics, org_metrics)
        except Exception as e:
            logging.warning(f"Error processing PR {pr.number}: {str(e)}")
            continue

def process_pr(pr, repo_metrics: RepositoryMetrics, org_metrics: OrganizationMetrics):
    """Process a single pull request with complete metrics tracking"""
    pr_timestamp = ensure_datetime(pr.created_at)
    repo_metrics.update_timestamp(pr_timestamp)
    
    try:
        # Add PR context
        logging.debug(f"Processing PR #{pr.number} - '{pr.title}' by {pr.user.login if pr.user else 'unknown'}")
        
        # Get author metrics
        author = pr.user.login if pr.user else 'unknown'
        user_metrics = org_metrics.get_or_create_user(author)
        
        # Update basic PR metrics and contributors
        repo_metrics.prs_created += 1
        user_metrics.prs_created += 1
        repo_metrics.contributors.add(author)
        
        if pr.merged:
            repo_metrics.prs_merged += 1
            user_metrics.prs_merged += 1
            
            if pr.base.ref == repo_metrics.default_branch:
                repo_metrics.prs_merged_to_main += 1
        
        # Process code metrics at all levels
        repo_metrics.code_metrics.update_from_pr(pr)
        user_metrics.code_metrics.update_from_pr(pr)
        org_metrics.code_metrics.update_from_pr(pr)
        
        # Get all reviews and comments
        reviews = list(pr.get_reviews())
        review_comments = list(pr.get_review_comments())
        issue_comments = list(pr.get_issue_comments())
        
        # Update PR author's received comments
        user_metrics.review_metrics.review_comments_received += len(review_comments)
        
        # Process all comments
        for comment in review_comments + issue_comments:
            if not comment.user:
                continue
            
            commenter = comment.user.login
            commenter_metrics = org_metrics.get_or_create_user(commenter)
            
            # Update comment counts at all levels
            commenter_metrics.review_metrics.review_comments_given += 1
            repo_metrics.review_metrics.review_comments_given += 1
            org_metrics.review_metrics.review_comments_given += 1
            
            # Update collaboration metrics for comments
            commenter_metrics.collaboration_metrics.update_from_comments([comment], pr.number)
            repo_metrics.collaboration_metrics.update_from_comments([comment], pr.number)
            org_metrics.collaboration_metrics.update_from_comments([comment], pr.number)
        
        # Track review cycles
        sorted_reviews = sorted(reviews, key=lambda r: r.submitted_at)
        review_cycles = sum(1 for review in sorted_reviews if review.state == 'CHANGES_REQUESTED')
        
        # Update review cycles at all levels if there were any
        if review_cycles > 0:
            repo_metrics.review_metrics.review_cycles.append(review_cycles)
            org_metrics.review_metrics.review_cycles.append(review_cycles)
            user_metrics.review_metrics.review_cycles.append(review_cycles)
        
        # Process each review
        for review in reviews:
            if not review.user:
                continue
                
            reviewer = review.user.login
            reviewer_metrics = org_metrics.get_or_create_user(reviewer)
            
            # Update review metrics at all levels
            reviewer_metrics.review_metrics.update_from_review(review, pr)
            repo_metrics.review_metrics.update_from_review(review, pr)
            org_metrics.review_metrics.update_from_review(review, pr)
            
            # Process reviews for collaboration
            if reviewer == pr.user.login:
                repo_metrics.collaboration_metrics.self_merges += 1
                org_metrics.collaboration_metrics.self_merges += 1
                user_metrics.collaboration_metrics.self_merges += 1
            
            # Update collaboration metrics at all levels
            repo_metrics.collaboration_metrics.update_from_review(
                review, pr,
                author_team=user_metrics.team,
                reviewer_team=reviewer_metrics.team
            )
            org_metrics.collaboration_metrics.update_from_review(
                review, pr,
                author_team=user_metrics.team,
                reviewer_team=reviewer_metrics.team
            )
            reviewer_metrics.collaboration_metrics.update_from_review(
                review, pr,
                author_team=user_metrics.team,
                reviewer_team=reviewer_metrics.team
            )
            
            # Update team reviews
            if reviewer_metrics.team and user_metrics.team:
                if reviewer_metrics.team == user_metrics.team:
                    repo_metrics.collaboration_metrics.team_reviews += 1
                    org_metrics.collaboration_metrics.team_reviews += 1
                    reviewer_metrics.collaboration_metrics.team_reviews += 1
                else:
                    repo_metrics.collaboration_metrics.cross_team_reviews += 1
                    org_metrics.collaboration_metrics.cross_team_reviews += 1
                    reviewer_metrics.collaboration_metrics.cross_team_reviews += 1
            else:
                repo_metrics.collaboration_metrics.external_reviews += 1
                org_metrics.collaboration_metrics.external_reviews += 1
                reviewer_metrics.collaboration_metrics.external_reviews += 1
        
        # Process time metrics for merged PRs
        if pr.merged:
            commits = list(pr.get_commits())
            first_commit_date = commits[-1].commit.committer.date if commits else None
            
            # Update time metrics at all levels
            repo_metrics.time_metrics.update_from_pr(pr, first_commit_date)
            user_metrics.time_metrics.update_from_pr(pr, first_commit_date)
            org_metrics.time_metrics.update_from_pr(pr, first_commit_date)
            
            # Calculate and update cycle time if we have first commit
            if first_commit_date:
                cycle_time = (pr.merged_at - first_commit_date).total_seconds() / 3600
                repo_metrics.time_metrics.cycle_time.append(cycle_time)
                user_metrics.time_metrics.cycle_time.append(cycle_time)
                org_metrics.time_metrics.cycle_time.append(cycle_time)
        
        # Process bottleneck metrics at all levels
        repo_metrics.bottleneck_metrics.update_from_pr(pr)
        org_metrics.bottleneck_metrics.update_from_pr(pr)
        user_metrics.bottleneck_metrics.update_from_pr(pr)
        
        # Process review wait times
        if reviews:
            first_review = min(reviews, key=lambda r: r.submitted_at)
            # Ensure both datetimes are timezone-aware
            review_time = ensure_datetime(first_review.submitted_at)
            created_time = ensure_datetime(pr.created_at)
            wait_time = (review_time - created_time).total_seconds() / 3600
            
            # Update wait times at all levels
            repo_metrics.bottleneck_metrics.review_wait_times.append(wait_time)
            org_metrics.bottleneck_metrics.review_wait_times.append(wait_time)
            user_metrics.bottleneck_metrics.review_wait_times.append(wait_time)
            
            # Calculate response times between reviews - also fix timezone awareness
            sorted_reviews = sorted(reviews, key=lambda r: r.submitted_at)
            for i in range(1, len(sorted_reviews)):
                current_review = ensure_datetime(sorted_reviews[i].submitted_at)
                previous_review = ensure_datetime(sorted_reviews[i-1].submitted_at)
                response_time = (current_review - previous_review).total_seconds() / 3600
                repo_metrics.bottleneck_metrics.review_response_times.append(response_time)
                org_metrics.bottleneck_metrics.review_response_times.append(response_time)
                user_metrics.bottleneck_metrics.review_response_times.append(response_time)
        
        # Update team involvement
        if user_metrics.team:
            repo_metrics.teams_involved.add(user_metrics.team)
        
        for review in reviews:
            if review.user and review.user.login in org_metrics.users:
                reviewer_team = org_metrics.users[review.user.login].team
                if reviewer_team:
                    repo_metrics.teams_involved.add(reviewer_team)
        
        merge_timestamp = ensure_datetime(pr.merged_at)
        repo_metrics.update_timestamp(merge_timestamp)
        
    except Exception as e:
        logging.error(f"Error processing PR {pr.number}: {str(e)}", exc_info=True)

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

