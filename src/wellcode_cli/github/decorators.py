from functools import wraps
from github import GithubException
from rich.console import Console
import time

console = Console()

def handle_github_errors(retries=3, delay=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < retries:
                try:
                    return func(*args, **kwargs)
                except GithubException as e:
                    attempts += 1
                    if e.status == 401:
                        console.print("[red]GitHub authentication failed. Please check your token and run 'wellcode-cli config'[/]")
                        raise
                    elif e.status == 403:
                        # Get rate limit information from headers
                        headers = e.headers
                        remaining = int(headers.get('x-ratelimit-remaining', 0))
                        reset_time = int(headers.get('x-ratelimit-reset', 0))
                        limit = int(headers.get('x-ratelimit-limit', 5000))
                        used = int(headers.get('x-ratelimit-used', 0))
                        resource = headers.get('x-ratelimit-resource', 'core')
                        
                        # Calculate wait time
                        current_time = int(time.time())
                        wait_time = max(reset_time - current_time, 0)
                        
                        if remaining == 0:
                            console.print(f"[yellow]Rate limit exceeded. Waiting {wait_time} seconds until reset...[/]")
                            time.sleep(wait_time + 1)  # Add 1 second buffer
                        else:
                            # Implement exponential backoff
                            backoff = delay * (2 ** (attempts - 1))
                            console.print(f"[yellow]Rate limit warning. Backing off for {backoff} seconds...[/]")
                            time.sleep(backoff)
                            
                        if attempts == retries:
                            raise
                    else:
                        if attempts == retries:
                            console.print(f"[red]GitHub API error: {e.data.get('message', str(e))}[/]")
                            raise
                        # Implement exponential backoff for other errors
                        backoff = delay * (2 ** (attempts - 1))
                        console.print(f"[yellow]Error occurred. Retrying in {backoff} seconds...[/]")
                        time.sleep(backoff)
            return None
        return wrapper
    return decorator
