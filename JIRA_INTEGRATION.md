# Jira Cloud Integration

This document describes how to set up and use the Jira Cloud integration with Wellcode CLI as an alternative to Linear for issue tracking metrics.

## Overview

The Jira Cloud integration provides comprehensive issue tracking analytics including:

- **Issue Flow Metrics**: Creation, completion, and in-progress tracking
- **Issue Type Analysis**: Bugs, Stories, Tasks, and Epics breakdown
- **Cycle Time Metrics**: Time from creation to resolution
- **Estimation Accuracy**: Story points vs actual time analysis
- **Project Performance**: Per-project metrics and health indicators
- **Assignee Performance**: Individual contributor metrics
- **Priority Distribution**: Issue priority analysis
- **Component & Version Tracking**: Component and fix version metrics

## Prerequisites

1. **Jira Cloud Instance**: You need access to a Jira Cloud instance (*.atlassian.net)
2. **API Token**: Generate an API token from your Atlassian account
3. **Permissions**: Read access to projects and issues you want to analyze

## Setup Instructions

### 1. Generate Jira API Token

1. Go to [Atlassian Account Security](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click "Create API token"
3. Give it a descriptive name (e.g., "Wellcode CLI")
4. Copy the generated token (you won't be able to see it again)

### 2. Configure Wellcode CLI

Run the configuration command:

```bash
wellcode-cli config
```

When prompted for Jira configuration, provide:

- **Domain**: Your Jira domain (e.g., `mycompany` for `mycompany.atlassian.net`)
- **Email**: Your Atlassian account email address
- **API Token**: The token you generated in step 1

The CLI will test the connection and save your configuration if successful.

### 3. Verify Setup

Test your configuration by running:

```bash
wellcode-cli review
```

You should see Jira metrics alongside your GitHub metrics.

## Usage

### Basic Usage

```bash
# Review last 7 days (default)
wellcode-cli review

# Review specific date range
wellcode-cli review --start-date 2024-01-01 --end-date 2024-01-31

# Review specific user's issues
wellcode-cli review --user "john.doe@company.com"
```

### Filtering Options

- `--user`: Filter by assignee (use email address or Jira username)
- `--start-date`: Start date for analysis (YYYY-MM-DD format)
- `--end-date`: End date for analysis (YYYY-MM-DD format)

## Metrics Explained

### Issue Flow Metrics

- **Issues Created**: Total issues created in the time period
- **Issues Completed**: Issues moved to "Done" status
- **Completion Rate**: Percentage of created issues that were completed
- **Issue Types**: Breakdown by Bugs, Stories, Tasks, and Epics

### Cycle Time Metrics

- **Average Cycle Time**: Mean time from creation to resolution
- **Median Cycle Time**: 50th percentile cycle time
- **95th Percentile**: 95th percentile cycle time (helps identify outliers)
- **Resolution Time**: Time to close/resolve issues

### Estimation Accuracy

- **Accuracy Rate**: Percentage of estimates within 25% of actual time
- **Underestimates**: Issues that took longer than estimated
- **Overestimates**: Issues that took less time than estimated
- **Variance**: Average percentage difference between estimate and actual

### Project Performance

- **Completion Rate**: Per-project completion percentage
- **Issue Distribution**: Breakdown by issue types per project
- **Assignee Involvement**: Number of people working on each project
- **Project Lead**: Project lead information
- **Project Type**: Software, Business, etc.

## Customization

### Story Points Field

The integration looks for story points in the `customfield_10016` field by default. If your Jira instance uses a different field for story points, you can modify this in the code:

```python
# In src/wellcode_cli/jira/models/metrics.py
story_points = fields.get("customfield_XXXXX")  # Replace XXXXX with your field ID
```

To find your story points field ID:
1. Go to Jira Settings → Issues → Custom Fields
2. Find your Story Points field
3. Note the field ID (usually in the format `customfield_XXXXX`)

### Time Estimation

The integration supports both:
- **Story Points**: Converted to hours (1 point = 4 hours by default)
- **Time Estimates**: Original time estimates in Jira

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Verify your email address is correct
   - Ensure your API token is valid and not expired
   - Check that your domain is correct (without .atlassian.net)

2. **No Issues Found**
   - Verify the date range includes issues
   - Check that you have read permissions for the projects
   - Ensure issues exist in the specified time period

3. **Missing Metrics**
   - Some metrics require specific Jira configurations (story points, time tracking)
   - Ensure your Jira instance has the required fields enabled

### Debug Mode

Enable debug logging to troubleshoot issues:

```bash
export WELLCODE_DEBUG=1
wellcode-cli review
```

### API Rate Limits

Jira Cloud has API rate limits:
- 300 requests per minute for most endpoints
- The integration uses pagination to handle large datasets efficiently

## Security

- API tokens are stored locally in `~/.wellcode/config.json`
- Tokens are transmitted over HTTPS only
- No data is sent to external services except Jira Cloud

## Comparison with Linear

| Feature | Jira Cloud | Linear |
|---------|------------|--------|
| Issue Types | Bugs, Stories, Tasks, Epics | Issues with Labels |
| Projects | Native project support | Team-based organization |
| Time Tracking | Built-in time tracking | Estimation-based |
| Custom Fields | Extensive customization | Limited custom fields |
| Workflow | Configurable workflows | Fixed workflow states |
| API Rate Limits | 300/minute | 1000/hour |

## Advanced Configuration

### Environment Variables

You can also configure Jira using environment variables:

```bash
export JIRA_DOMAIN="mycompany"
export JIRA_EMAIL="user@company.com"
export JIRA_API_KEY="your-api-token"
```

### JQL Customization

The integration uses JQL (Jira Query Language) to fetch issues. The default query is:

```jql
created >= 'YYYY-MM-DD' AND created <= 'YYYY-MM-DD'
```

For advanced users, you can modify the JQL in `src/wellcode_cli/jira/jira_metrics.py`.

## Support

For issues with the Jira integration:

1. Check the troubleshooting section above
2. Enable debug mode for detailed logs
3. Verify your Jira permissions and configuration
4. Create an issue in the Wellcode CLI repository with debug logs

## Contributing

To contribute to the Jira integration:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

The Jira integration follows the same patterns as other integrations in the codebase for consistency and maintainability. 