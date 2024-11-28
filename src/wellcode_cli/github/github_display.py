from rich.console import Console
from rich.panel import Panel
from rich import box
from rich.table import Table
from datetime import datetime, timezone
import statistics

def display_github_metrics(org_metrics):
    """Display GitHub metrics with a modern UI using Rich components."""
    console = Console()
    
    # Header with organization info and time range
    now = datetime.now(timezone.utc)
    console.print(Panel(
        "[bold cyan]GitHub Engineering Analytics[/]\n" +
        f"[dim]Organization: {org_metrics.name}[/]\n" +
        f"[dim]Report Generated: {now.strftime('%Y-%m-%d %H:%M')} UTC[/]",
        box=box.ROUNDED,
        style="cyan"
    ))

    # 1. Core PR Metrics with visual indicators
    total_prs_created = sum(repo.prs_created for repo in org_metrics.repositories.values())
    total_prs_merged = sum(repo.prs_merged for repo in org_metrics.repositories.values())
    total_prs_to_main = sum(repo.prs_merged_to_main for repo in org_metrics.repositories.values())
    
    merge_rate = (total_prs_merged / total_prs_created * 100) if total_prs_created > 0 else 0
    main_rate = (total_prs_to_main / total_prs_merged * 100) if total_prs_merged > 0 else 0
    
    # Add health indicators
    merge_health = "🟢" if merge_rate > 80 else "🟡" if merge_rate > 60 else "🔴"
    
    console.print(Panel(
        f"{merge_health} [bold green]PRs Created:[/] {total_prs_created}\n" +
        f"[bold yellow]PRs Merged:[/] {total_prs_merged} ({merge_rate:.1f}% merge rate)\n" +
        f"[bold blue]Merged to Main:[/] {total_prs_to_main} ({main_rate:.1f}% of merged)\n" +
        f"[bold]Daily PR Volume:[/] {total_prs_created / 30:.1f} PRs/day",  # Assuming 30 days
        title="[bold]Pull Request Flow",
        box=box.ROUNDED
    ))

    # 2. Repository Overview (New Section)
    repo_table = Table(title="Repository Activity", box=box.ROUNDED)
    repo_table.add_column("Repository", style="cyan")
    repo_table.add_column("PRs", justify="right")
    repo_table.add_column("Contributors", justify="right")
    repo_table.add_column("Teams", justify="right")
    repo_table.add_column("Last Activity", justify="right")

    for repo_name, repo in org_metrics.repositories.items():
        last_activity = repo.last_updated.strftime("%Y-%m-%d") if repo.last_updated else "N/A"
        repo_table.add_row(
            repo_name,
            str(repo.prs_created),
            str(len(repo.contributors)),
            str(len(repo.teams_involved)),
            last_activity
        )
    
    console.print(repo_table)

    # 3. Team Performance (New Section)
    if org_metrics.teams:
        team_stats = {}
        for team_name, members in org_metrics.teams.items():
            team_prs = sum(org_metrics.users[user].prs_created for user in members if user in org_metrics.users)
            team_reviews = sum(org_metrics.users[user].review_metrics.reviews_performed for user in members if user in org_metrics.users)
            team_stats[team_name] = (team_prs, team_reviews)

        console.print(Panel(
            "\n".join(f"[bold]{team}:[/] {prs} PRs, {reviews} Reviews" 
                     for team, (prs, reviews) in team_stats.items()),
            title="[bold green]Team Performance",
            box=box.ROUNDED
        ))

    # 4. Review Quality Metrics (Enhanced)
    review = org_metrics.review_metrics
    avg_review_time = statistics.mean(review.time_to_first_review) if review.time_to_first_review else 0
    
    review_health = "🟢" if avg_review_time < 4 else "🟡" if avg_review_time < 24 else "🔴"
    

    # Add format_time helper function
    def format_time(hours: float) -> str:
        """Convert hours to a human-readable format"""
        if hours < 1:
            return f"{int(hours * 60)} minutes"
        elif hours < 24:
            return f"{round(hours, 1)} hours"
        else:
            days = hours / 24
            return f"{round(days, 1)} days"
        
    console.print(Panel(
        f"{review_health} [bold]Time to First Review:[/] {format_time(avg_review_time)}\n" +
        f"[bold]Review Cycles:[/] {statistics.mean(review.review_cycles) if review.review_cycles else 0:.1f}\n" +
        f"[bold]Blocking Reviews:[/] {review.blocking_reviews_given}\n" +
        f"[bold]Active Reviewers:[/] {len(set().union(*review.reviewers_per_pr.values())) if review.reviewers_per_pr else 0}\n" +
        f"[bold]Comments Given:[/] {review.review_comments_given}\n" +
        f"[bold]Avg Reviewers per PR:[/] {statistics.mean([len(r) for r in review.reviewers_per_pr.values()]) if review.reviewers_per_pr else 0:.1f}\n" +
        f"[bold]Review Coverage:[/] {(len(review.reviewers_per_pr) / total_prs_created * 100) if total_prs_created > 0 else 0:.1f}% PRs reviewed",
        title="[bold yellow]Review Health",
        box=box.ROUNDED
    ))


    # 3. Code Quality - Enhanced
    quality = org_metrics.code_metrics
    avg_changes = statistics.mean(quality.changes_per_pr) if quality.changes_per_pr else 0
    
    change_indicator = "🟢" if avg_changes < 200 else "🟡" if avg_changes < 500 else "🔴"
    
    console.print(Panel(
        f"{change_indicator} [bold]Avg Changes/PR:[/] {avg_changes:.0f}\n" +
        f"[bold]Files/PR:[/] {statistics.mean(quality.files_changed) if quality.files_changed else 0:.0f}\n" +
        f"[bold]Commits/PR:[/] {statistics.mean(quality.commits_count) if quality.commits_count else 0:.0f}\n" +
        f"[bold]Total Changes:[/] +{quality.total_additions}/-{quality.total_deletions}\n" +
        f"⚠️ [bold]Reverts:[/] {quality.reverts} | [bold]Hotfixes:[/] {quality.hotfixes}",
        title="[bold magenta]Code Quality",
        box=box.ROUNDED
    ))

    # 4. Team Collaboration - Enhanced
    collab = org_metrics.collaboration_metrics
    review_comments = list(collab.review_comments_per_pr.values())
    avg_comments = statistics.mean(review_comments) if review_comments else 0    
    console.print(Panel(
        f"[bold cyan]Cross-Team Reviews:[/] {collab.cross_team_reviews}\n" +
        f"[bold red]Self-Merges:[/] {collab.self_merges}\n" +
        f"[bold yellow]Team Reviews:[/] {collab.team_reviews}\n" +
        f"[bold blue]External Reviews:[/] {collab.external_reviews}\n" +
        f"[bold green]Avg Comments/PR:[/] {avg_comments:.1f}\n" +
        f"[bold]Review Participation:[/] {collab.get_stats().get('review_participation_rate', 0):.1%}",
        title="[bold]Team Collaboration",
        box=box.ROUNDED
    ))

    # 6. Time Metrics - Enhanced (New Section)
    time = org_metrics.time_metrics
    avg_merge_time = statistics.mean(time.time_to_merge) if time.time_to_merge else 0
    avg_lead_time = statistics.mean(time.lead_times) if time.lead_times else 0
    avg_cycle_time = statistics.mean(time.cycle_time) if time.cycle_time else 0
    
    console.print(Panel(
        f"[bold]Time to Merge:[/] {format_time(avg_merge_time)}\n" +
        f"[bold]Lead Time:[/] {format_time(avg_lead_time)}\n" +
        f"[bold]Cycle Time:[/] {format_time(avg_cycle_time)}",
        title="[bold blue]Time Metrics",
        box=box.ROUNDED
    ))

    # 7. System Health - Enhanced
    bottleneck = org_metrics.bottleneck_metrics
    avg_wait = statistics.mean(bottleneck.review_wait_times) if bottleneck.review_wait_times else 0
    avg_response = statistics.mean(bottleneck.review_response_times) if bottleneck.review_response_times else 0
    
    console.print(Panel(
        f"[bold red]Stale PRs:[/] {bottleneck.stale_prs}\n" +
        f"[bold yellow]Long-Running PRs:[/] {bottleneck.long_running_prs}\n" +
        f"[bold orange]Blocked PRs:[/] {bottleneck.blocked_prs}\n" +
        f"[bold]Avg Review Wait:[/] {format_time(avg_wait)}\n" +
        f"[bold]Avg Response Time:[/] {format_time(avg_response)}\n" +
        f"[bold]Top Bottleneck Users:[/] {', '.join(f'{user}({count})' for user, count in bottleneck.get_stats()['top_bottleneck_users'])}",
        title="[bold red]System Health",
        box=box.ROUNDED
    ))