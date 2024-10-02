from github import Github
import pandas as pd
from collections import defaultdict
import statistics
from anthropic import Anthropic
import re

# Import configuration
try:
    from .config import GITHUB_TOKEN, ANTHROPIC_API_KEY 
except ImportError: 
    raise ImportError("Failed to import configuration. Ensure config.py exists and is properly set up.")

client = Anthropic(
    # This is the default and can be omitted
    api_key=ANTHROPIC_API_KEY,
)

def format_ai_response(response):
    # Extract the content inside the <analysis> tags
    analysis = re.search(r'<analysis>(.*?)</analysis>', response, re.DOTALL)
    if not analysis:
        return "No analysis found in the response."
    
    analysis = analysis.group(1)

    # Split the analysis into sections
    sections = re.findall(r'<(\w+)>(.*?)</\1>', analysis, re.DOTALL)

    formatted_output = "Analysis:\n\n"
    for section, content in sections:
        # Convert section name to title case and replace underscores with spaces
        section_title = section.replace('_', ' ').title()
        formatted_output += f"{section_title}:\n"
        
        # Split content into paragraphs and number them if necessary
        paragraphs = content.strip().split('\n')
        for i, para in enumerate(paragraphs, 1):
            para = para.strip()
            if para:
                if len(paragraphs) > 1 and not para.startswith(str(i)):
                    formatted_output += f"{i}. {para}\n"
                else:
                    formatted_output += f"{para}\n"
        formatted_output += "\n"

    # Extract and add efficiency score
    efficiency_score = re.search(r'<efficiency_score>(.*?)</efficiency_score>', response, re.DOTALL)
    if efficiency_score:
        formatted_output += f"Efficiency Score: {efficiency_score.group(1).strip()}/10\n"

    return formatted_output

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
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        model="claude-3-5-sonnet-20240620",
    )
    return message.content[0].text

def get_github_metrics(org_name, start_date, end_date, user_filter=None):
    # Initialize GitHub client using token from config
    g = Github(GITHUB_TOKEN)
    
    # Get the organization
    org = g.get_organization(org_name)
    
    # Initialize metrics
    metrics = {
        'prs_created': 0,
        'prs_merged': 0,
        'prs_merged_to_main': 0,
        'comments_per_pr': {},
        'prs_details': [],
        'time_to_merge': [],
        'user_contributions': defaultdict(lambda: {'created': 0, 'merged': 0}),
        'deployments': 0,
        'lead_times': [],
    }

    print(f"Wellcode CLI!")
    # Iterate through all repositories in the organization
    for repo in org.get_repos():
        
        # Get pull requests within date range
        pulls = repo.get_pulls(state='all', sort='created', direction='desc')
        for pr in pulls:
            if start_date <= pr.created_at.date() <= end_date:
                if user_filter is None or pr.user.login == user_filter:
                    metrics['prs_created'] += 1
                    metrics['user_contributions'][pr.user.login]['created'] += 1
                    
                    # Count comments
                    comments = pr.get_issue_comments()
                    comment_count = comments.totalCount
                    metrics['comments_per_pr'][pr.number] = comment_count
                    
                    # Check if PR was merged
                    if pr.merged:
                        metrics['prs_merged'] += 1
                        metrics['user_contributions'][pr.user.login]['merged'] += 1
                        
                        # Check if PR was merged to main/master (consider as deployment)
                        if pr.base.ref in ['main', 'master']:
                            metrics['prs_merged_to_main'] += 1
                            metrics['deployments'] += 1
                        
                        # Calculate lead time (time from PR creation to merge)
                        lead_time = (pr.merged_at - pr.created_at).total_seconds() / 3600  # in hours
                        metrics['lead_times'].append(lead_time)
                        metrics['time_to_merge'].append(lead_time)
                    
                    # Collect PR details
                    metrics['prs_details'].append({
                        'repo': repo.name,
                        'pr_number': pr.number,
                        'title': pr.title,
                        'user': pr.user.login,
                        'created_at': pr.created_at,
                        'merged_at': pr.merged_at,
                        'comments': comment_count,
                        'merged_to_main': pr.merged and pr.base.ref in ['main', 'master'],
                        'lead_time': lead_time if pr.merged else None
                    })
            elif pr.created_at.date() < start_date:
                # Stop checking older PRs
                break

    # Calculate DORA metrics
    days_in_period = (end_date - start_date).days + 1
    metrics['deployment_frequency'] = metrics['deployments'] / days_in_period
    metrics['median_lead_time'] = statistics.median(metrics['lead_times']) if metrics['lead_times'] else 0
    
    # Calculate other summary metrics
    metrics['avg_comments_per_pr'] = sum(metrics['comments_per_pr'].values()) / metrics['prs_created'] if metrics['prs_created'] > 0 else 0
    metrics['avg_time_to_merge'] = sum(metrics['time_to_merge']) / len(metrics['time_to_merge']) if metrics['time_to_merge'] else 0

    # Calculate top and bottom performers
    user_performance = [(user, data['created'] + data['merged']) for user, data in metrics['user_contributions'].items()]
    user_performance.sort(key=lambda x: x[1], reverse=True)
    
    metrics['top_performers'] = user_performance[:3]
    metrics['bottom_performers'] = user_performance[-3:] if len(user_performance) > 3 else user_performance

    # Convert PR details to DataFrame
    metrics['prs_details'] = pd.DataFrame(metrics['prs_details'])

    return metrics