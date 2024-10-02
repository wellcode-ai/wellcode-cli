from splitio import get_factory
from splitio.exceptions import TimeoutException
from datetime import datetime, timedelta

try:
    from config import SPLIT_API_KEY
except ImportError:
    raise ImportError("Failed to import configuration. Ensure config.py exists and is properly set up.")

def get_split_metrics(start_date, end_date):
    factory = get_factory(SPLIT_API_KEY, config={'impressionsMode': 'optimized'})
    client = factory.client()

    metrics = {
        'total_splits': 0,
        'active_splits': 0,
        'splits_by_environment': {},
        'treatments_served': 0,
        'top_splits': [],
        'errors': []
    }

    try:
        # Wait for the client to be ready
        factory.block_until_ready(5)  # Wait up to 5 seconds for the client to be ready

        # Get all splits
        splits = client.get_all_splits()
        metrics['total_splits'] = len(splits)

        # Count active splits and splits by environment
        for split in splits:
            if split.status == 'ACTIVE':
                metrics['active_splits'] += 1
            
            for env in split.environments:
                if env not in metrics['splits_by_environment']:
                    metrics['splits_by_environment'][env] = 0
                metrics['splits_by_environment'][env] += 1

        # Get impression counts (treatments served)
        start_time = int(start_date.timestamp() * 1000)
        end_time = int(end_date.timestamp() * 1000)
        
        # Note: The impressions_count method might not be available in the current SDK version
        # You may need to implement a custom solution to count impressions
        # For now, we'll leave this as a placeholder
        metrics['treatments_served'] = "Not available in current SDK version"

        # Get top splits (this is a placeholder as we can't get impression counts easily)
        metrics['top_splits'] = [{'name': split.name, 'count': 'N/A'} for split in splits[:5]]

    except TimeoutException:
        error_message = "Timeout while waiting for Split.io client to be ready"
        print(error_message)
        metrics['errors'].append(error_message)
    except Exception as e:
        error_message = f"Error fetching Split.io metrics: {str(e)}"
        print(error_message)
        metrics['errors'].append(error_message)

    finally:
        client.destroy()

    return metrics

def print_split_metrics(metrics):
    print("\nSPLIT.IO METRICS:")
    print("=================")
    
    if metrics['errors']:
        print("\nErrors encountered:")
        for error in metrics['errors']:
            print(f"- {error}")
        print("\nNote: Some data may be incomplete due to errors.")
    
    print(f"\nTotal Splits: {metrics['total_splits']}")
    print(f"Active Splits: {metrics['active_splits']}")
    print(f"Total Treatments Served: {metrics['treatments_served']}")
    
    print("\nSplits by Environment:")
    for env, count in metrics['splits_by_environment'].items():
        print(f"  {env}: {count}")
    
    print("\nTop 5 Splits by Impression Count:")
    for split in metrics['top_splits']:
        print(f"  {split['name']}: {split['count']} impressions")
    
    print("\n" + "=" * 40)
