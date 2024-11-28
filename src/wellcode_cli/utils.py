import json
from datetime import datetime, timezone, date
import tempfile
import os
import pandas as pd
from collections import defaultdict
from pathlib import Path
from rich.console import Console

console = Console()

# Define config file location
CONFIG_DIR = Path.home() / '.wellcode'
CONFIG_FILE = CONFIG_DIR / 'config.json'


class WellcodeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, set):
            return list(obj)  # Convert sets to lists for JSON serialization
        if isinstance(obj, defaultdict):
            return dict(obj)  # Convert defaultdict to regular dict
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict(orient='records')
        if isinstance(obj, pd.Series):
            return obj.to_dict()
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        return super().default(obj)

def save_analysis_data(metrics_data, analysis_result):
    """Save metrics and analysis data to a temporary file"""
    # Convert any defaultdict to regular dict before serialization
    metrics_data = json.loads(json.dumps(metrics_data, cls=WellcodeJSONEncoder))
    
    data = {
        'metrics': metrics_data,
        'analysis': analysis_result,
        'timestamp': datetime.now(timezone.utc).isoformat()
    }
    
    temp_file = tempfile.NamedTemporaryFile(
        mode='w',
        suffix='.json',
        delete=False
    )
    
    with temp_file:
        json.dump(data, temp_file, indent=2, cls=WellcodeJSONEncoder)
    
    return temp_file.name

def get_latest_analysis():
    """Get the most recent analysis data"""
    try:
        # Get the temp directory
        temp_dir = tempfile.gettempdir()
        
        # Find all JSON files in temp directory that match our pattern
        analysis_files = [
            f for f in os.listdir(temp_dir)
            if f.endswith('.json')
        ]
        
        if not analysis_files:
            console.print("[yellow]No previous analysis found. Please run 'analyze' first.[/]")
            return None
        
        # Get the most recent file
        latest_file = max(
            [os.path.join(temp_dir, f) for f in analysis_files],
            key=os.path.getmtime
        )
        
        # Read and validate JSON content
        with open(latest_file, 'r') as f:
            try:
                content = f.read()
                # Try to parse the JSON
                data = json.loads(content)
                
                # Validate expected structure
                if not isinstance(data, dict) or 'metrics' not in data:
                    console.print("[yellow]Invalid analysis file format. Please run 'analyze' again.[/]")
                    return None
                
                return data
            except json.JSONDecodeError as e:
                console.print(f"[red]Error reading analysis file: {str(e)}[/]")
                console.print("[yellow]Please run 'analyze' again to generate new data.[/]")
                
                # Optionally, remove the corrupted file
                try:
                    os.remove(latest_file)
                except OSError:
                    pass
                    
                return None
            except Exception as e:
                console.print(f"[red]Unexpected error reading analysis file: {str(e)}[/]")
                return None
                
    except Exception as e:
        console.print(f"[red]Error accessing analysis data: {str(e)}[/]")
        return None

def load_config():
    """Load configuration with validation"""
    config = {}
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                config = json.load(f)
        except Exception as e:
            console.print(f"[yellow]Warning: Error reading config file: {e}[/]")
    
    # Check for required GitHub organization
    if not config.get('GITHUB_ORG'):
        console.print("[yellow]Warning: GitHub organization not configured[/]")
        console.print("Please run: wellcode-cli config")
    
    return config

def validate_github_config():
    """Validate GitHub configuration"""
    config = load_config()
    if not config.get('GITHUB_ORG'):
        raise ValueError("GitHub organization not configured. Please run: wellcode-cli config")
    return True