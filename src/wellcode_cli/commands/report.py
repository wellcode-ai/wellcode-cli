import rich_click as click
from rich.console import Console
from pathlib import Path
import plotly.graph_objects as go
from datetime import datetime
import webbrowser
from ..utils import get_latest_analysis
import plotly.io as pio
from collections import defaultdict
import statistics
console = Console()

@click.command()
@click.option('--output', '-o', help="Output directory for the report", type=click.Path())
@click.option('--format', '-f', type=click.Choice(['html', 'pdf']), default='html', help="Report format")
def report(output, format):
    """Generate a visual report of engineering metrics"""
    try:
        data = get_latest_analysis()
        if not data:
            console.print("[red]No analysis data found. Please run 'review' first.[/]")
            return

        metrics = data.get('metrics', {})
        github_data = metrics.get('github')
        if not github_data:
            console.print("[red]No GitHub metrics found in the analysis data.[/]")
            return

        # Create output directory
        output_dir = Path(output) if output else Path.cwd() / 'reports'
        output_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"Output directory: {output_dir}")

        charts = []
        summary_stats = {}

        # GitHub Metrics Charts
        if github_data:
            # Organization Overview
            org_stats = {
                'Total Repositories': len(github_data.get('repositories', {})),
                'Active Contributors': len(set().union(*[set(repo.get('contributors', [])) 
                                                       for repo in github_data.get('repositories', {}).values()])),
                'Total PRs': sum(repo.get('prs_created', 0) for repo in github_data.get('repositories', {}).values()),
                'Merged PRs': sum(repo.get('prs_merged', 0) for repo in github_data.get('repositories', {}).values())
            }
            
            overview = go.Figure(data=[
                go.Bar(
                    x=list(org_stats.keys()),
                    y=list(org_stats.values()),
                    marker_color=['#6366F1', '#EC4899', '#10B981', '#F59E0B']
                )
            ])
            overview.update_layout(
                title='Organization Overview',
                yaxis_title='Count',
                plot_bgcolor='#F3F4F6',
                paper_bgcolor='#F3F4F6'
            )
            charts.append(overview)

            # Time Metrics
            time_metrics = []
            for repo in github_data.get('repositories', {}).values():
                time_metrics.extend(repo.get('time_metrics', {}).get('time_to_merge', []))
            
            if time_metrics:
                merge_dist = go.Figure(data=[
                    go.Histogram(
                        x=time_metrics,
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

            # User Activity
            user_data = {}
            for user in github_data.get('users', {}).values():
                user_data[user.get('username', '')] = {
                    'PRs Created': user.get('prs_created', 0),
                    'PRs Merged': user.get('prs_merged', 0),
                    'Reviews Given': user.get('review_metrics', {}).get('reviews_performed', 0),
                    'Comments Given': user.get('review_metrics', {}).get('review_comments_given', 0)
                }

            if user_data:
                user_activity = go.Figure()
                for metric in ['PRs Created', 'PRs Merged', 'Reviews Given', 'Comments Given']:
                    user_activity.add_trace(go.Bar(
                        name=metric,
                        x=list(user_data.keys()),
                        y=[user_data[user][metric] for user in user_data],
                    ))

                user_activity.update_layout(
                    title='User Activity',
                    barmode='group',
                    xaxis_title='Users',
                    yaxis_title='Count',
                    plot_bgcolor='#F3F4F6',
                    paper_bgcolor='#F3F4F6'
                )
                charts.append(user_activity)

            # Repository Metrics
            repo_metrics = {}
            for repo_name, repo in github_data.get('repositories', {}).items():
                repo_metrics[repo_name] = {
                    'PRs Created': repo.get('prs_created', 0),
                    'PRs Merged': repo.get('prs_merged', 0),
                    'Contributors': len(repo.get('contributors', [])),
                    'Reviews': repo.get('review_metrics', {}).get('reviews_performed', 0)
                }

            if repo_metrics:
                repo_activity = go.Figure()
                for metric in ['PRs Created', 'PRs Merged', 'Contributors', 'Reviews']:
                    repo_activity.add_trace(go.Bar(
                        name=metric,
                        x=list(repo_metrics.keys()),
                        y=[repo_metrics[repo][metric] for repo in repo_metrics],
                    ))

                repo_activity.update_layout(
                    title='Repository Activity',
                    barmode='group',
                    xaxis_title='Repositories',
                    yaxis_title='Count',
                    plot_bgcolor='#F3F4F6',
                    paper_bgcolor='#F3F4F6'
                )
                charts.append(repo_activity)

            # Code Quality Metrics
            code_metrics = {
                'Hotfixes': sum(repo.get('code_metrics', {}).get('hotfixes', 0) for repo in github_data.get('repositories', {}).values()),
                'Reverts': sum(repo.get('code_metrics', {}).get('reverts', 0) for repo in github_data.get('repositories', {}).values()),
                'Blocking Reviews': sum(user.get('review_metrics', {}).get('blocking_reviews_given', 0) for user in github_data.get('users', {}).values()),
                'Stale PRs': sum(repo.get('bottleneck_metrics', {}).get('stale_prs', 0) for repo in github_data.get('repositories', {}).values())
            }

            quality = go.Figure(data=[
                go.Bar(
                    x=list(code_metrics.keys()),
                    y=list(code_metrics.values()),
                    marker_color=['#EF4444', '#F59E0B', '#6366F1', '#EC4899']
                )
            ])
            quality.update_layout(
                title='Code Quality Metrics',
                yaxis_title='Count',
                plot_bgcolor='#F3F4F6',
                paper_bgcolor='#F3F4F6'
            )
            charts.append(quality)

            # Add new charts for engineering managers
            
            # 1. PR Review Time Distribution
            review_times = []
            for repo in github_data.get('repositories', {}).values():
                review_times.extend(repo.get('review_metrics', {}).get('review_wait_times', []))
            
            if review_times:
                review_dist = go.Figure(data=[
                    go.Histogram(
                        x=review_times,
                        nbinsx=20,
                        name='Review Time Distribution',
                        marker_color='#8B5CF6'
                    )
                ])
                review_dist.update_layout(
                    title='PR Review Time Distribution',
                    xaxis_title='Hours',
                    yaxis_title='Frequency',
                    plot_bgcolor='#F3F4F6',
                    paper_bgcolor='#F3F4F6'
                )
                charts.append(review_dist)

            # 2. Team Collaboration Metrics
            team_metrics = {}
            for repo in github_data.get('repositories', {}).values():
                collab_metrics = repo.get('collaboration_metrics', {})
                team_metrics['Cross-team Reviews'] = team_metrics.get('Cross-team Reviews', 0) + collab_metrics.get('cross_team_reviews', 0)
                team_metrics['Self-merges'] = team_metrics.get('Self-merges', 0) + collab_metrics.get('self_merges', 0)
                team_metrics['Team Reviews'] = team_metrics.get('Team Reviews', 0) + collab_metrics.get('team_reviews', 0)
                team_metrics['External Reviews'] = team_metrics.get('External Reviews', 0) + collab_metrics.get('external_reviews', 0)

            if team_metrics:
                collaboration = go.Figure(data=[
                    go.Bar(
                        x=list(team_metrics.keys()),
                        y=list(team_metrics.values()),
                        marker_color=['#3B82F6', '#EF4444', '#10B981', '#F59E0B']
                    )
                ])
                collaboration.update_layout(
                    title='Team Collaboration Overview',
                    yaxis_title='Count',
                    plot_bgcolor='#F3F4F6',
                    paper_bgcolor='#F3F4F6'
                )
                charts.append(collaboration)

            # 3. Bottleneck Analysis
            bottleneck_data = {
                'Metrics': ['Stale PRs', 'Long-running PRs', 'Blocked PRs', 'High Review Wait Time'],
                'Values': [
                    sum(repo.get('bottleneck_metrics', {}).get('stale_prs', 0) 
                        for repo in github_data.get('repositories', {}).values()),
                    sum(repo.get('bottleneck_metrics', {}).get('long_running_prs', 0) 
                        for repo in github_data.get('repositories', {}).values()),
                    sum(repo.get('bottleneck_metrics', {}).get('blocked_prs', 0) 
                        for repo in github_data.get('repositories', {}).values()),
                    len([t for repo in github_data.get('repositories', {}).values() 
                         for t in repo.get('bottleneck_metrics', {}).get('review_wait_times', []) 
                         if t > 48])  # PRs waiting > 48 hours for review
                ]
            }

            bottlenecks = go.Figure(data=[
                go.Bar(
                    x=bottleneck_data['Metrics'],
                    y=bottleneck_data['Values'],
                    marker_color='#EF4444'
                )
            ])
            bottlenecks.update_layout(
                title='Development Bottlenecks',
                yaxis_title='Count',
                plot_bgcolor='#F3F4F6',
                paper_bgcolor='#F3F4F6'
            )
            charts.append(bottlenecks)

            # 4. Team Velocity Trends
            velocity_data = {}
            for repo in github_data.get('repositories', {}).values():
                for pr in repo.get('time_metrics', {}).get('lead_times', []):
                    week = datetime.fromtimestamp(pr * 3600).strftime('%Y-%W')  # Convert hours to timestamp
                    velocity_data[week] = velocity_data.get(week, 0) + 1

            if velocity_data:
                weeks = sorted(velocity_data.keys())
                velocity = go.Figure(data=[
                    go.Scatter(
                        x=weeks,
                        y=[velocity_data[week] for week in weeks],
                        mode='lines+markers',
                        line=dict(color='#10B981')
                    )
                ])
                velocity.update_layout(
                    title='Team Velocity (PRs Merged per Week)',
                    xaxis_title='Week',
                    yaxis_title='PRs Merged',
                    plot_bgcolor='#F3F4F6',
                    paper_bgcolor='#F3F4F6'
                )
                charts.append(velocity)

            # 5. Code Review Participation
            reviewer_stats = defaultdict(int)
            for repo in github_data.get('repositories', {}).values():
                for reviewer_data in repo.get('review_metrics', {}).get('reviewers_per_pr', {}).values():
                    for reviewer in reviewer_data:
                        reviewer_stats[reviewer] += 1

            if reviewer_stats:
                reviewers = go.Figure(data=[
                    go.Bar(
                        x=list(reviewer_stats.keys()),
                        y=list(reviewer_stats.values()),
                        marker_color='#6366F1'
                    )
                ])
                reviewers.update_layout(
                    title='Code Review Participation by Team Member',
                    xaxis_title='Team Member',
                    yaxis_title='Reviews Performed',
                    plot_bgcolor='#F3F4F6',
                    paper_bgcolor='#F3F4F6'
                )
                charts.append(reviewers)

            # 6. PRs per Developer
            developer_prs = {}
            for username, user in github_data.get('users', {}).items():
                if username.endswith('[bot]'):  # Skip bot users
                    continue
                
                # Safely calculate average review time
                time_to_merge = user.get('time_metrics', {}).get('time_to_merge', [])
                avg_review_time = round(statistics.mean(time_to_merge)) if time_to_merge else 0
                
                developer_prs[username] = {
                    'Created': user.get('prs_created', 0),
                    'Merged': user.get('prs_merged', 0),
                    'Open': user.get('prs_created', 0) - user.get('prs_merged', 0),
                    'Avg Size': round(user.get('code_metrics', {}).get('avg_pr_size', 0), 2),
                    'Avg Review Time': avg_review_time
                }

            if developer_prs:
                # PR Creation and Merge Rate
                pr_activity = go.Figure()
                
                # Add traces for Created, Merged, and Open PRs
                pr_activity.add_trace(go.Bar(
                    name='Created PRs',
                    x=list(developer_prs.keys()),
                    y=[data['Created'] for data in developer_prs.values()],
                    marker_color='#3B82F6'
                ))
                
                pr_activity.add_trace(go.Bar(
                    name='Merged PRs',
                    x=list(developer_prs.keys()),
                    y=[data['Merged'] for data in developer_prs.values()],
                    marker_color='#10B981'
                ))
                
                pr_activity.add_trace(go.Bar(
                    name='Open PRs',
                    x=list(developer_prs.keys()),
                    y=[data['Open'] for data in developer_prs.values()],
                    marker_color='#F59E0B'
                ))

                pr_activity.update_layout(
                    title='PR Activity by Developer',
                    barmode='group',
                    xaxis_title='Developer',
                    yaxis_title='Number of PRs',
                    plot_bgcolor='#F3F4F6',
                    paper_bgcolor='#F3F4F6',
                    showlegend=True
                )
                charts.append(pr_activity)

                # PR Size and Review Time (only if we have data)
                if any(data['Avg Size'] > 0 or data['Avg Review Time'] > 0 for data in developer_prs.values()):
                    pr_metrics = go.Figure()
                    
                    pr_metrics.add_trace(go.Bar(
                        name='Avg PR Size (changes)',
                        x=list(developer_prs.keys()),
                        y=[data['Avg Size'] for data in developer_prs.values()],
                        marker_color='#8B5CF6',
                        yaxis='y'
                    ))
                    
                    pr_metrics.add_trace(go.Scatter(
                        name='Avg Review Time (hours)',
                        x=list(developer_prs.keys()),
                        y=[data['Avg Review Time'] for data in developer_prs.values()],
                        marker_color='#EC4899',
                        yaxis='y2'
                    ))

                    pr_metrics.update_layout(
                        title='PR Metrics by Developer',
                        xaxis_title='Developer',
                        yaxis=dict(
                            title='Average PR Size',
                            titlefont=dict(color='#8B5CF6'),
                            tickfont=dict(color='#8B5CF6')
                        ),
                        yaxis2=dict(
                            title='Average Review Time (hours)',
                            titlefont=dict(color='#EC4899'),
                            tickfont=dict(color='#EC4899'),
                            overlaying='y',
                            side='right'
                        ),
                        plot_bgcolor='#F3F4F6',
                        paper_bgcolor='#F3F4F6',
                        showlegend=True
                    )
                    charts.append(pr_metrics)

                # Update summary stats with developer PR metrics
                if developer_prs:
                    most_active = max(developer_prs.items(), key=lambda x: x[1]['Created'])
                    highest_merge_rate = max(
                        ((name, data['Merged'] / max(data['Created'], 1)) 
                         for name, data in developer_prs.items()),
                        key=lambda x: x[1]
                    )
                    
                    summary_stats.update({
                        'Most Active Developer': f"{most_active[0]} ({most_active[1]['Created']} PRs)",
                        'Highest Merge Rate': f"{highest_merge_rate[0]} ({round(highest_merge_rate[1] * 100)}%)",
                        'Average PRs per Developer': f"{round(sum(data['Created'] for data in developer_prs.values()) / len(developer_prs), 1)}"
                    })

            # Add summary statistics to the HTML report
            summary_stats = {
                'Avg Review Time': f"{sum(review_times) / len(review_times):.1f} hours" if review_times else "N/A",
                'PR Merge Rate': f"{(org_stats['Merged PRs'] / org_stats['Total PRs'] * 100):.1f}%" if org_stats['Total PRs'] > 0 else "N/A",
                'Active Repositories': org_stats['Total Repositories'],
                'Team Size': org_stats['Active Contributors'],
                'Review Participation Rate': f"{(len(reviewer_stats) / org_stats['Active Contributors'] * 100):.1f}%" if org_stats['Active Contributors'] > 0 else "N/A"
            }

            # Update the HTML template to include summary stats
            html_template = '''
            <!DOCTYPE html>
            <html>
                <head>
                    <title>Engineering Metrics Report</title>
                    <style>
                        body {
                            font-family: Arial, sans-serif;
                            margin: 20px;
                            background-color: #f5f5f5;
                        }
                        .summary-stats {
                            display: grid;
                            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                            gap: 20px;
                            margin: 20px 0;
                        }
                        .stat-card {
                            background-color: white;
                            padding: 20px;
                            border-radius: 8px;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        }
                        .stat-value {
                            font-size: 24px;
                            font-weight: bold;
                            color: #4F46E5;
                        }
                        .stat-label {
                            color: #6B7280;
                            margin-top: 8px;
                        }
                        .chart-container {
                            background-color: white;
                            padding: 20px;
                            margin: 20px 0;
                            border-radius: 8px;
                            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                        }
                        h1 {
                            color: #333;
                            text-align: center;
                        }
                    </style>
                </head>
                <body>
                    <h1>Engineering Metrics Report</h1>
                    <div class="summary-stats">
                        {summary_stats}
                    </div>
                    <div class="charts">
                        {charts}
                    </div>
                </body>
            </html>
            '''

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

def generate_html_content(charts):
    """Generate HTML content with all charts and explanations"""
    html_template = '''
    <!DOCTYPE html>
    <html>
        <head>
            <title>Wellcode Engineering Metrics Report</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    background-color: #f5f5f5;
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    text-align: center;
                    padding: 40px 0;
                    background: linear-gradient(135deg, #4F46E5, #7C3AED);
                    color: white;
                    border-radius: 8px;
                    margin-bottom: 40px;
                }}
                .header h1 {{
                    margin: 0;
                    font-size: 2.5em;
                }}
                .header p {{
                    margin: 10px 0 0;
                    opacity: 0.9;
                }}
                .chart-container {{
                    background-color: white;
                    padding: 30px;
                    margin: 30px 0;
                    border-radius: 8px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                }}
                .chart-description {{
                    color: #4B5563;
                    margin: 20px 0;
                    line-height: 1.6;
                }}
                .section-title {{
                    color: #1F2937;
                    margin-top: 40px;
                    padding-bottom: 10px;
                    border-bottom: 2px solid #E5E7EB;
                }}
                .timestamp {{
                    text-align: center;
                    color: #6B7280;
                    margin-top: 40px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Wellcode Engineering Metrics Report</h1>
                <p>Comprehensive analysis of your engineering team's performance</p>
            </div>
            
            <div class="charts">
                <h2 class="section-title">Organization Overview</h2>
                <div class="chart-container">
                    <div class="chart-description">
                        This chart provides a high-level view of your organization's GitHub activity, 
                        showing the total number of repositories, active contributors, and PR metrics.
                        It helps identify the overall scale of your engineering operations.
                    </div>
                    {charts[0]}
                </div>

                <h2 class="section-title">Time and Efficiency Metrics</h2>
                <div class="chart-container">
                    <div class="chart-description">
                        The Time to Merge distribution shows how quickly PRs move through your review process.
                        A left-skewed distribution indicates efficient PR processing, while long tails might
                        suggest bottlenecks in your review process.
                    </div>
                    {charts[1]}
                </div>

                <h2 class="section-title">Team Activity Analysis</h2>
                <div class="chart-container">
                    <div class="chart-description">
                        This visualization breaks down individual contributions across different metrics,
                        helping identify team members' strengths and participation patterns in the
                        development process.
                    </div>
                    {charts[2]}
                </div>

                <h2 class="section-title">Repository Performance</h2>
                <div class="chart-container">
                    <div class="chart-description">
                        Compare activity levels across different repositories to understand where most
                        development is happening and identify potential areas needing more attention
                        or support.
                    </div>
                    {charts[3]}
                </div>

                <h2 class="section-title">Code Quality Indicators</h2>
                <div class="chart-container">
                    <div class="chart-description">
                        Track key quality metrics including hotfixes, reverts, and blocking reviews.
                        These indicators help identify potential areas for process improvement and
                        where additional code review attention might be needed.
                    </div>
                    {charts[4]}
                </div>

                <h2 class="section-title">Review Process Analysis</h2>
                <div class="chart-container">
                    <div class="chart-description">
                        The PR Review Time Distribution shows how long PRs typically wait for review.
                        This helps identify if your review process is running smoothly or if there are
                        delays that need addressing.
                    </div>
                    {charts[5]}
                </div>

                <h2 class="section-title">Team Collaboration Patterns</h2>
                <div class="chart-container">
                    <div class="chart-description">
                        Understand how your team collaborates through different types of reviews.
                        High cross-team review numbers indicate good knowledge sharing, while high
                        self-merges might suggest areas for process improvement.
                    </div>
                    {charts[6]}
                </div>
            </div>

            <div class="timestamp">
                Generated on {timestamp}
            </div>
        </body>
    </html>
    '''
    
    timestamp = datetime.now().strftime('%B %d, %Y at %I:%M %p')
    charts_html = []
    for chart in charts:
        charts_html.append(pio.to_html(chart, full_html=False))
    
    return html_template.format(
        charts=charts_html,
        timestamp=timestamp
    )

