from .github_metrics import get_github_metrics,format_ai_response,get_ai_analysis  # Add this import at the top of the file
from .linear_metrics import get_linear_metrics,print_linear_metrics
from .split_metrics import get_split_metrics,print_split_metrics
from datetime import datetime, timedelta
import argparse

# Import configuration
try:
    from .config import GITHUB_ORG, GITHUB_TOKEN, LINEAR_API_KEY, SPLIT_API_KEY
except ImportError: 
    raise ImportError("Failed to import configuration. Ensure config.py exists and is properly set up.")

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Get GitHub metrics")
    parser.add_argument("--user", help="GitHub username to filter by", default=None)
    args = parser.parse_args()
    user_filter = args.user
 
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=end_date.weekday())

    all_metrics = {}

    if not GITHUB_TOKEN:
        print(f"GITHUB_TOKEN not found in configuration, no github metrics will be fetched")
    else:     
        metrics = get_github_metrics(GITHUB_ORG, start_date, end_date, user_filter)
        all_metrics['github'] = metrics
        print(f"Metrics for {start_date} to {end_date}:")
        print(f"PRs created: {metrics['prs_created']}")
        print(f"PRs merged: {metrics['prs_merged']}")
        print(f"PRs merged to main/master (deployments): {metrics['prs_merged_to_main']}")
        print(f"Deployment Frequency: {metrics['deployment_frequency']:.2f} per day")
        print(f"Median Lead Time for Changes: {metrics['median_lead_time']:.2f} hours")
        print(f"Average comments per PR: {metrics['avg_comments_per_pr']:.2f}")
        print(f"Average time to merge (hours): {metrics['avg_time_to_merge']:.2f}")
        
        print("\nMost Active 3 Contributors:")
        for user, contribution in metrics['top_performers']:
            print(f"  {user}: {contribution} contributions")
        
        print("\nLeast Active 3 Contributors:")
        for user, contribution in metrics['bottom_performers']:
            print(f"  {user}: {contribution} contributions")

        print("\nPR Details:")
        print(metrics['prs_details'])        

    if not LINEAR_API_KEY:  
        print(f"LINEAR_API_KEY not found in configuration, no linear metrics will be fetched")
    else:
        linear_metrics = get_linear_metrics(start_date, end_date, user_filter)
        all_metrics['linear'] = linear_metrics
        print_linear_metrics(linear_metrics)

    if not SPLIT_API_KEY:
        print(f"SPLIT_API_KEY not found in configuration, no split metrics will be fetched")
    else:
        split_metrics = get_split_metrics(start_date, end_date)
        all_metrics['split'] = split_metrics
        print_split_metrics(split_metrics)
    if not ANTHROPIC_API_KEY:
        print(f"ANTHROPIC_API_KEY not found in configuration, no ai analysis will be fetched")
    else:
        print(format_ai_response(get_ai_analysis(all_metrics)))

if __name__ == "__main__":
    main()    