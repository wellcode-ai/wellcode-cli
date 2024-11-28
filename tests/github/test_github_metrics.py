from wellcode_cli.github.models.metrics import OrganizationMetrics


def test_github_metrics_initialization():
    """Test that OrganizationMetrics initializes with empty default values."""
    metrics = OrganizationMetrics(name="test")

    assert metrics.name == "test"
    assert metrics.repositories == {}
    assert metrics.teams == {}
    assert metrics.users == {}
