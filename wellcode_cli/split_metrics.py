import logging

# Configure logging to suppress all Split.io related messages
logging.getLogger('splitio').setLevel(logging.CRITICAL)
logging.getLogger('splitio-events').setLevel(logging.CRITICAL)
logging.getLogger('splitio-metrics').setLevel(logging.CRITICAL)
logging.getLogger('splitio-telemetry').setLevel(logging.CRITICAL)
logging.getLogger('splitio-sync').setLevel(logging.CRITICAL)
logging.getLogger('splitio-auth').setLevel(logging.CRITICAL)

from splitio import get_factory
from splitio.exceptions import TimeoutException
from datetime import datetime, timedelta, date

try:
    from .config import SPLIT_API_KEY
except ImportError:
    raise ImportError("Failed to import configuration. Ensure config.py exists and is properly set up.")

def get_split_metrics(start_date: date, end_date: date):
    # Convert date to datetime for timestamp
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    
    # Convert to millisecond timestamps
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)

    factory = get_factory(SPLIT_API_KEY, config={'impressionsMode': 'optimized'})
    client = factory.client()
    split_manager = factory.manager()

    metrics = {
        'total_splits': 0,
        'active_splits': 0,
        'splits_by_environment': {},
        'treatments_served': 0,
        'top_splits': [],
        'changed_splits': [],
        'errors': []
    }

    try:
        factory.block_until_ready(5)

        splits = split_manager.splits()
        metrics['total_splits'] = len(splits)

        for split in splits:
            if not split.killed:
                metrics['active_splits'] += 1
            
            # Check if the split was changed during our date range
            if start_ts <= split.change_number <= end_ts:
                metrics['changed_splits'].append({
                    'name': split.name,
                    'change_time': datetime.fromtimestamp(split.change_number / 1000).strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'active' if not split.killed else 'killed',
                    'treatments': split.treatments,
                })

        # Store top splits with more useful information
        metrics['top_splits'] = [{
            'name': split.name,
            'traffic_type': split.traffic_type,
            'status': 'active' if not split.killed else 'killed',
            'treatments': split.treatments,
            'default': split.default_treatment,
            'has_rules': len(split.treatments) > 1,
            'configs': split.configs,
            'last_modified': datetime.fromtimestamp(split.change_number / 1000).strftime('%Y-%m-%d %H:%M:%S')
        } for split in list(splits)[:5]]

        metrics['splits_by_environment'] = {'production': metrics['total_splits']}

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
    
    print("\nSplits Changed During Period:")
    if metrics['changed_splits']:
        for split in metrics['changed_splits']:
            print(f"  {split['name']}:")
            print(f"    Changed at: {split['change_time']}")
            print(f"    Current Status: {split['status']}")
            print(f"    Available Treatments: {', '.join(split['treatments'])}")
    else:
        print("  No splits were changed during this period")
    
    print("\nTop 5 Splits:")
    for split in metrics['top_splits']:
        print(f"  {split['name']}:")
        print(f"    Traffic Type: {split['traffic_type']}")
        print(f"    Status: {split['status']}")
        print(f"    Treatments: {', '.join(split['treatments'])}")
        print(f"    Default: {split['default']}")
        print(f"    Has Rules: {'Yes' if split['has_rules'] else 'No (open to everyone)'}")
        print(f"    Last Modified: {split['last_modified']}")
        if split['configs']:
            print(f"    Configurations: {split['configs']}")
    
    print("\n" + "=" * 40)
