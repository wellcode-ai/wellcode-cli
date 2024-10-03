from colorama import init, Fore, Back, Style
from .github_metrics import get_github_metrics, format_ai_response, get_ai_analysis
from .linear_metrics import get_linear_metrics, print_linear_metrics
from .split_metrics import get_split_metrics, print_split_metrics
from datetime import datetime, timedelta
import argparse
from wellcode_cli import __version__
from .utils import color_print
# Initialize colorama
init(autoreset=True)

# Import configuration
try:
    from .config import GITHUB_ORG, GITHUB_TOKEN, LINEAR_API_KEY, SPLIT_API_KEY, ANTHROPIC_API_KEY
except ImportError: 
    raise ImportError(Fore.RED + "Failed to import configuration. Ensure config.py exists and is properly set up.")

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Get GitHub metrics")
    parser.add_argument("--user", help="GitHub username to filter by", default=None)
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    args = parser.parse_args()
    user_filter = args.user
 
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=end_date.weekday())

    all_metrics = {}

    color_print(f"Analyzing metrics from {start_date} to {end_date}", Fore.CYAN)
    if user_filter:
        color_print(f"Filtering by user: {user_filter}", Fore.CYAN)

    if not GITHUB_TOKEN:
        color_print("GITHUB_TOKEN not found in configuration, no GitHub metrics will be fetched", Fore.YELLOW)
    else:     
        metrics = get_github_metrics(GITHUB_ORG, start_date, end_date, user_filter)
        all_metrics['github'] = metrics
        color_print("\nGitHub Metrics:", Fore.GREEN, style=Style.BRIGHT)
        color_print(f"PRs created: {metrics['prs_created']}")
        color_print(f"PRs merged: {metrics['prs_merged']}")
        color_print(f"PRs merged to main/master (deployments): {metrics['prs_merged_to_main']}")
        color_print(f"Deployment Frequency: {metrics['deployment_frequency']:.2f} per day")
        color_print(f"Median Lead Time for Changes: {metrics['median_lead_time']:.2f} hours")
        color_print(f"Average comments per PR: {metrics['avg_comments_per_pr']:.2f}")
        color_print(f"Average time to merge (hours): {metrics['avg_time_to_merge']:.2f}")
        
        color_print("\nMost Active 3 Contributors:", Fore.MAGENTA)
        for user, contribution in metrics['top_performers']:
            color_print(f"  {user}: {contribution} contributions")
        
        color_print("\nLeast Active 3 Contributors:", Fore.YELLOW)
        for user, contribution in metrics['bottom_performers']:
            color_print(f"  {user}: {contribution} contributions")

        color_print("\nPR Details:", Fore.CYAN)
        print(metrics['prs_details'])        

    if not LINEAR_API_KEY:  
        color_print("LINEAR_API_KEY not found in configuration, no Linear metrics will be fetched", Fore.YELLOW)
    else:
        linear_metrics = get_linear_metrics(start_date, end_date, user_filter)
        all_metrics['linear'] = linear_metrics
        color_print("\nLinear Metrics:", Fore.GREEN, style=Style.BRIGHT)
        print_linear_metrics(linear_metrics)

    if not SPLIT_API_KEY:
        color_print("SPLIT_API_KEY not found in configuration, no Split metrics will be fetched", Fore.YELLOW)
    else:
        split_metrics = get_split_metrics(start_date, end_date)
        all_metrics['split'] = split_metrics
        color_print("\nSplit Metrics:", Fore.GREEN, style=Style.BRIGHT)
        print_split_metrics(split_metrics)

    if not ANTHROPIC_API_KEY:
        color_print("ANTHROPIC_API_KEY not found in configuration, no AI analysis will be fetched", Fore.YELLOW)
    else:
        color_print("\nAnalysis:", Fore.GREEN, style=Style.BRIGHT)
        print(format_ai_response(get_ai_analysis(all_metrics)))

if __name__ == "__main__":
    main()