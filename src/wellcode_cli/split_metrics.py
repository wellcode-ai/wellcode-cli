import logging
from datetime import date, datetime, timedelta

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from splitio import get_factory
from splitio.exceptions import TimeoutException

from .config import get_split_api_key

# Configure logging to suppress all Split.io related messages
logging.getLogger("splitio").setLevel(logging.CRITICAL)
logging.getLogger("splitio-events").setLevel(logging.CRITICAL)
logging.getLogger("splitio-metrics").setLevel(logging.CRITICAL)
logging.getLogger("splitio-telemetry").setLevel(logging.CRITICAL)
logging.getLogger("splitio-sync").setLevel(logging.CRITICAL)
logging.getLogger("splitio-auth").setLevel(logging.CRITICAL)


console = Console()


def get_split_metrics(start_date: date, end_date: date):
    """Get Split.io metrics for the specified date range"""
    # Convert date to datetime for timestamp
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    # Convert to millisecond timestamps
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)

    try:
        # Initialize with environment variable
        if not get_split_api_key():
            return {
                "total_splits": 0,
                "active_splits": 0,
                "splits_by_environment": {},
                "treatments_served": 0,
                "top_splits": [],
                "changed_splits": [],
                "no_traffic_splits": [],
                "recently_modified_count": 0,
                "errors": ["SPLIT_API_KEY not set in environment"],
            }

        factory = get_factory(
            get_split_api_key(), config={"impressionsMode": "optimized"}
        )
        client = factory.client()
        split_manager = factory.manager()

        metrics = {
            "total_splits": 0,
            "active_splits": 0,
            "splits_by_environment": {},
            "treatments_served": 0,
            "top_splits": [],
            "changed_splits": [],
            "no_traffic_splits": [],
            "recently_modified_count": 0,
            "errors": [],
        }

        try:
            factory.block_until_ready(5)

            splits = split_manager.splits()
            metrics["total_splits"] = len(splits)

            # Get current timestamp for "recent" comparison (last 7 days)
            week_ago_ts = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)

            for split in splits:
                if not split.killed:
                    metrics["active_splits"] += 1

                # Check for recent modifications (last 7 days)
                if split.change_number >= week_ago_ts:
                    metrics["recently_modified_count"] += 1

                # Check for splits with no traffic
                if not getattr(split, "traffic_type", "") or split.killed:
                    metrics["no_traffic_splits"].append(
                        {
                            "name": split.name,
                            "status": "active" if not split.killed else "killed",
                            "last_modified": datetime.fromtimestamp(
                                split.change_number / 1000
                            ).strftime("%Y-%m-%d %H:%M:%S"),
                        }
                    )

                # Check if the split was changed during our date range
                if start_ts <= split.change_number <= end_ts:
                    metrics["changed_splits"].append(
                        {
                            "name": split.name,
                            "change_time": datetime.fromtimestamp(
                                split.change_number / 1000
                            ).strftime("%Y-%m-%d %H:%M:%S"),
                            "status": "active" if not split.killed else "killed",
                            "treatments": split.treatments,
                        }
                    )

            # Store top splits with more useful information
            metrics["top_splits"] = [
                {
                    "name": split.name,
                    "traffic_type": split.traffic_type,
                    "status": "active" if not split.killed else "killed",
                    "treatments": split.treatments,
                    "default": split.default_treatment,
                    "has_rules": len(split.treatments) > 1,
                    "configs": split.configs,
                    "last_modified": datetime.fromtimestamp(
                        split.change_number / 1000
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                }
                for split in list(splits)[:5]
            ]

            metrics["splits_by_environment"] = {"production": metrics["total_splits"]}

        except TimeoutException:
            error_message = "Timeout while waiting for Split.io client to be ready"
            console.print(f"[yellow]{error_message}[/]")
            metrics["errors"].append(error_message)
        except Exception as e:
            error_message = f"Error fetching Split.io metrics: {str(e)}"
            console.print(f"[yellow]{error_message}[/]")
            metrics["errors"].append(error_message)

        finally:
            client.destroy()

        return metrics

    except Exception as e:
        error_message = f"Error initializing Split client: {str(e)}"
        return {
            "total_splits": 0,
            "active_splits": 0,
            "splits_by_environment": {},
            "treatments_served": 0,
            "top_splits": [],
            "changed_splits": [],
            "no_traffic_splits": [],
            "recently_modified_count": 0,
            "errors": [error_message],
        }


def display_split_metrics(metrics):
    console.print("\n[bold green]Split.io Metrics[/]")

    if metrics["errors"]:
        console.print("\n[red]Errors encountered:[/]")
        for error in metrics["errors"]:
            console.print(f"[red]- {error}[/]")
        console.print("\n[yellow]Note: Some data may be incomplete due to errors.[/]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Total Splits", str(metrics["total_splits"]))
    table.add_row("Active Splits", str(metrics["active_splits"]))
    table.add_row("Recently Modified (7 days)", str(metrics["recently_modified_count"]))
    table.add_row("Flags with No Traffic", str(len(metrics["no_traffic_splits"])))

    console.print(table)

    # Environment breakdown
    if metrics["splits_by_environment"]:
        console.print("\n[bold magenta]Splits by Environment:[/]")
        env_table = Table(show_header=True, header_style="bold magenta")
        env_table.add_column("Environment", style="cyan")
        env_table.add_column("Count", justify="right")

        for env, count in metrics["splits_by_environment"].items():
            env_table.add_row(env, str(count))
        console.print(env_table)

    # Changed splits
    if metrics["changed_splits"]:
        console.print("\n[bold magenta]Recently Changed Splits:[/]")
        for split in metrics["changed_splits"]:
            console.print(
                Panel.fit(
                    f"""[cyan]{split['name']}[/]
Changed at: {split['change_time']}
Status: {split['status']}
Treatments: {', '.join(split['treatments'])}""",
                    border_style="blue",
                )
            )

    # Display flags with no traffic
    if metrics["no_traffic_splits"]:
        console.print("\n[bold magenta]Flags with No Traffic:[/]")
        no_traffic_table = Table(show_header=True, header_style="bold magenta")
        no_traffic_table.add_column("Flag Name", style="cyan")
        no_traffic_table.add_column("Status", style="yellow")
        no_traffic_table.add_column("Last Modified", style="dim")

        for split in metrics["no_traffic_splits"]:
            no_traffic_table.add_row(
                split["name"], split["status"], split["last_modified"]
            )
        console.print(no_traffic_table)
