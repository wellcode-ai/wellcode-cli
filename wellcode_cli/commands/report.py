import rich_click as click
from rich.console import Console
from pathlib import Path
import plotly.graph_objects as go
import statistics
from datetime import datetime
import webbrowser
from ..utils import get_latest_analysis
import plotly.io as pio
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

