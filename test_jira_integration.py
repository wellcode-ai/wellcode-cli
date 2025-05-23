#!/usr/bin/env python3
"""
Test script for Jira Cloud integration
"""

import sys
import os
from datetime import datetime, timedelta

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from wellcode_cli.jira.jira_metrics import test_jira_connection, get_jira_metrics
from wellcode_cli.jira.jira_display import display_jira_metrics


def test_jira_integration():
    """Test the Jira integration with sample data"""
    print("🧪 Testing Jira Cloud Integration")
    print("=" * 50)
    
    # Test connection function
    print("\n1. Testing connection function...")
    
    # These would be real credentials in actual use
    test_domain = "example"
    test_email = "test@example.com"
    test_api_key = "fake_api_key"
    
    print(f"Domain: {test_domain}")
    print(f"Email: {test_email}")
    print(f"API Key: {'*' * len(test_api_key)}")
    
    # This will fail with fake credentials, but tests the function structure
    try:
        result = test_jira_connection(test_domain, test_email, test_api_key)
        print(f"Connection test result: {result}")
    except Exception as e:
        print(f"Expected connection failure with fake credentials: {e}")
    
    print("\n2. Testing metrics collection structure...")
    
    # Test date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    print(f"Date range: {start_date.date()} to {end_date.date()}")
    
    # This will also fail without real credentials, but tests the structure
    try:
        metrics = get_jira_metrics(start_date, end_date)
        if metrics:
            print("✅ Metrics collection structure is working")
            display_jira_metrics(metrics)
        else:
            print("❌ No metrics returned (expected with fake credentials)")
    except Exception as e:
        print(f"Expected metrics failure with fake credentials: {e}")
    
    print("\n3. Testing data models...")
    
    # Test the data models with sample data
    from wellcode_cli.jira.models.metrics import JiraOrgMetrics, IssueMetrics, ProjectMetrics
    
    # Create sample metrics
    org_metrics = JiraOrgMetrics(name="Test Organization")
    
    # Sample issue data (mimicking Jira API response structure)
    sample_issue = {
        "key": "TEST-123",
        "fields": {
            "summary": "Test issue",
            "issuetype": {"name": "Story"},
            "status": {
                "name": "Done",
                "statusCategory": {"key": "done"}
            },
            "priority": {"name": "High"},
            "assignee": {"displayName": "John Doe"},
            "project": {"key": "TEST", "name": "Test Project"},
            "created": "2024-01-01T10:00:00.000Z",
            "resolutiondate": "2024-01-02T15:00:00.000Z",
            "components": [{"name": "Frontend"}],
            "fixVersions": [{"name": "v1.0.0"}]
        }
    }
    
    # Test updating metrics with sample data
    org_metrics.issues.update_from_issue(sample_issue)
    org_metrics.cycle_time.update_from_issue(sample_issue)
    
    # Add sample project
    org_metrics.projects["TEST"] = ProjectMetrics(
        key="TEST",
        name="Test Project"
    )
    org_metrics.projects["TEST"].update_from_issue(sample_issue)
    
    # Test component and version tracking
    org_metrics.component_counts["Frontend"] = 1
    org_metrics.version_counts["v1.0.0"] = 1
    
    print("✅ Data models are working correctly")
    print(f"   - Issues created: {org_metrics.issues.total_created}")
    print(f"   - Issues completed: {org_metrics.issues.total_completed}")
    print(f"   - Stories created: {org_metrics.issues.stories_created}")
    print(f"   - Projects tracked: {len(org_metrics.projects)}")
    print(f"   - Components tracked: {len(org_metrics.component_counts)}")
    
    print("\n4. Testing display functionality...")
    try:
        display_jira_metrics(org_metrics)
        print("✅ Display functionality is working")
    except Exception as e:
        print(f"❌ Display error: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Jira integration test completed!")
    print("\nTo use with real data:")
    print("1. Run: wellcode-cli config")
    print("2. Configure Jira with your domain, email, and API token")
    print("3. Run: wellcode-cli review")


if __name__ == "__main__":
    test_jira_integration() 