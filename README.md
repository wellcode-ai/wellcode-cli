# Wellcode.ai - Engineering Metrics Script

wellcode.ai is a powerful script that integrates with GitHub, Linear, and Split.io to gather and analyze engineering team metrics. It helps identify productivity trends, potential blockers, and provides AI-powered insights into team performance.

## Prerequisites

- Python 3.7+
- Access to GitHub, Linear, and Split.io APIs
- OpenAI API access for AI analysis (optional)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/wellcode-ai/wellcode-cli.git
   cd wellcode-cli
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Configuration

1. Create a `config.py` file in the project root with the following content:
   ```python
   GITHUB_TOKEN = 'your_github_token'
   GITHUB_ORG = 'your_github_organization'
   LINEAR_API_KEY = 'your_linear_api_key'
   SPLIT_API_KEY = 'your_split_api_key'
   OPENAI_API_KEY = 'your_openai_api_key'  # Optional, for AI analysis
   ```

2. Replace the placeholder values with your actual API tokens and settings.

## Usage

Run the script with:

```
python main.py [--user USERNAME]
```

Options:
- `--user USERNAME`: Filter metrics by a specific username

By default, the script will analyze data from the current week (Monday to today) and generate a report.

## Features

- GitHub metrics: PRs created, merged, deployment frequency, lead time, etc.
- Linear metrics: Issues created, completed, cycle time, priority breakdown, etc.
- Split.io metrics: Total splits, active splits, treatments served, etc.
- AI-powered analysis of team performance (requires OpenAI API key)
- Customizable date ranges for analysis

## Customization

- Adjust the date range in the `main.py` file
- Modify the metrics collected in each service-specific file (`github_metrics.py`, `linear_metrics.py`, `split_metrics.py`)
- Customize the AI analysis prompts in `github_metrics.py`

## Contributing

Please read CONTRIBUTING.md for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the LICENSE.md file for details.

## Acknowledgments

- OpenAI for providing the AI analysis capabilities
- The teams behind GitHub, Linear, and Split.io for their excellent APIs