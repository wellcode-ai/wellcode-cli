# Wellcode CLI Style Guide

## Python Code Style

### General Guidelines
- Follow [PEP 8](https://www.python.org/dev/peps/pep-0008/) conventions
- Use 4 spaces for indentation (no tabs)
- Maximum line length is 88 characters (compatible with Black formatter)
- Use type hints for all function parameters and return values

### Imports
```python
# Standard library imports
import os
from typing import List, Dict, Optional

# Third-party imports
import click
from rich.console import Console

# Local imports
from wellcode_cli.config import get_config
```

### Documentation
- Use Google-style docstrings
```python
def get_metrics(start_date: str, end_date: str) -> Dict[str, any]:
    """Retrieves metrics for the specified date range.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Dictionary containing the calculated metrics

    Raises:
        ValueError: If date format is invalid
    """
```

### Error Handling
```python
# Prefer specific exceptions over generic ones
try:
    result = process_data()
except ValueError as e:
    logger.error(f"Invalid data format: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise RuntimeError(f"Processing failed: {e}")
```

### Testing
- Write tests using pytest
- Use meaningful test names that describe the scenario
- Follow the Arrange-Act-Assert pattern
```python
def test_metric_calculation_with_valid_data():
    # Arrange
    data = {"value": 42}
    
    # Act
    result = calculate_metric(data)
    
    # Assert
    assert result == 84
```

## Command Line Interface
- Use clear, descriptive command names
- Provide helpful error messages
- Include examples in help text
```python
@click.command()
@click.option('--days', default=7, help='Number of days to analyze (default: 7)')
def analyze(days: int):
    """Analyzes repository metrics for the specified time period."""
```

## Logging
- Use appropriate log levels
- Include contextual information
```python
logger.debug("Processing data", extra={"start_date": start_date})
logger.info("Analysis completed successfully")
logger.error("API request failed", exc_info=True)
```

# Debugging Guide

## Common Issues and Solutions

### Installation Issues

#### Package Not Found
```bash
pip install wellcode-cli fails with "Package not found"
```
**Solution:**
- Verify you're using Python 3.8 or higher
- Check your pip version: `pip --version`
- Try upgrading pip: `python -m pip install --upgrade pip`

#### Permission Errors
```bash
Permission denied when installing package
```
**Solution:**
- Use a virtual environment
- Or install with user flag: `pip install --user wellcode-cli`

### Configuration Issues

#### GitHub Authentication
```
Error: Could not authenticate with GitHub
```
**Solution:**
1. Verify your GitHub App installation
2. Run `wellcode-cli config` again
3. Check organization permissions

#### API Key Issues
```
Error: Invalid API key
```
**Solution:**
1. Verify API keys in `~/.wellcode/config.json`
2. Regenerate API keys if necessary
3. Run `wellcode-cli config` to reconfigure

### Runtime Issues

#### High Memory Usage
If the CLI is using too much memory:
1. Reduce date range in analysis
2. Use `--limit` option if available
3. Check for memory leaks in custom scripts

#### Slow Performance
If commands are running slowly:
1. Enable debug logging: `export WELLCODE_DEBUG=1`
2. Check network connectivity
3. Verify API rate limits

## Debug Mode

Enable debug logging:
```bash
export WELLCODE_DEBUG=1
wellcode-cli review
```

Debug log location:
- Unix: `~/.wellcode/debug.log`
- Windows: `%USERPROFILE%\.wellcode\debug.log`

## Getting Support

If you can't resolve an issue:

1. Enable debug mode
2. Reproduce the issue
3. Collect logs
4. Create a GitHub issue with:
   - Steps to reproduce
   - Debug logs
   - Environment info
   - Expected vs actual behavior

## Environment Information

Collect system information:
```bash
wellcode-cli debug
```

This provides:
- Python version
- OS details
- Package versions
- Configuration status

## Contributing Debug Improvements

Found a common issue? Help others:
1. Document the solution
2. Add to this guide
3. Submit a PR
