<p align="center">
  <img src="https://cli.wellcode.ai/wellcode.svg" alt="Wellcode Logo" width="200"/>
</p>

<h1 align="center">Wellcode</h1>

<p align="center">
  <strong>Open-source developer productivity platform</strong>
</p>
<p align="center">
  Track engineering metrics, DORA performance, AI coding tool ROI, and developer experience.<br>
  The open-source alternative to Swarmia, GetDX, and LinearB.
</p>
<p align="center">
  <a href="#installation">Install</a> &middot;
  <a href="#quick-start">Quick Start</a> &middot;
  <a href="#features">Features</a> &middot;
  <a href="#web-dashboard">Dashboard</a> &middot;
  <a href="#building-plugins">Plugins</a> &middot;
  <a href="#api-reference">API</a>
</p>

---

## What is Wellcode?

Wellcode is a CLI + web dashboard that connects to your existing tools (GitHub, GitLab, Bitbucket, JIRA, Linear) and gives you a single view of your engineering team's performance:

- **DORA metrics** -- Deployment Frequency, Lead Time, Change Failure Rate, Mean Time to Recovery
- **AI coding metrics** -- GitHub Copilot adoption, Cursor usage, AI-assisted PR detection, ROI analysis
- **Pull request analytics** -- Cycle time, review bottlenecks, batch size, self-merges
- **Developer experience surveys** -- Pulse and full DX surveys based on the SPACE / DX Core 4 frameworks
- **Issue tracker metrics** -- JIRA and Linear cycle time, sprint velocity, estimation accuracy

Everything runs locally by default (SQLite database, no cloud dependency). For teams, deploy it with PostgreSQL via Docker.

---

## Installation

**Requirements:** Python 3.10+

```bash
pip install wellcode-cli
```

Or from source:

```bash
git clone https://github.com/wellcode-ai/wellcode-cli.git
cd wellcode-cli
python -m venv venv && source venv/bin/activate
pip install -e .
```

### Docker (self-hosted with PostgreSQL)

```bash
git clone https://github.com/wellcode-ai/wellcode-cli.git
cd wellcode-cli

# Set your tokens in .env or export them
export GITHUB_TOKEN=ghp_...
export GITHUB_ORG=your-org

docker compose up -d
# Dashboard at http://localhost:8787
```

---

## Quick Start

### 1. Configure integrations

```bash
wellcode config
```

This walks you through connecting:

| Integration     | What you need                    |
| --------------- | -------------------------------- |
| **GitHub**      | Personal access token or App     |
| **GitLab**      | Personal access token            |
| **Bitbucket**   | App password + workspace         |
| **JIRA**        | Email + API token + instance URL |
| **Linear**      | API key                          |
| **Anthropic**   | API key (for AI-powered insights)|

### 2. Collect metrics

```bash
# Collect last 7 days from all configured providers
wellcode collect

# Collect a specific date range
wellcode collect --start-date 2026-01-01 --end-date 2026-01-31
```

### 3. View results

```bash
# DORA metrics
wellcode dora

# AI coding tool metrics
wellcode ai-metrics

# Classic review (GitHub + JIRA + Linear in terminal)
wellcode review

# Start the web dashboard
wellcode serve
# Open http://localhost:8787
```

---

## Features

### CLI Commands

| Command          | Description                                                       |
| ---------------- | ----------------------------------------------------------------- |
| `wellcode serve` | Start the API server + web dashboard                              |
| `wellcode collect` | Collect metrics from all configured providers and persist them  |
| `wellcode dora`  | View DORA metrics with Elite/High/Medium/Low classification       |
| `wellcode ai-metrics` | View AI coding tool adoption and impact analysis             |
| `wellcode review` | Classic terminal metrics review (GitHub, JIRA, Linear, Split.io) |
| `wellcode survey` | Create developer experience surveys (pulse or full DX)          |
| `wellcode report` | Generate an HTML report with Plotly charts                      |
| `wellcode chat`  | Interactive AI chat about your metrics (powered by Claude)        |
| `wellcode config` | Configuration wizard for all integrations                       |
| `wellcode completion` | Generate shell completions (bash, zsh, fish)                |

### DORA Metrics

All four DORA metrics computed from your actual data, classified against the industry benchmarks from the State of DevOps report:

| Metric                   | Elite        | High          | Medium         | Low        |
| ------------------------ | ------------ | ------------- | -------------- | ---------- |
| Deployment Frequency     | On-demand    | Weekly-daily  | Monthly-weekly | < Monthly  |
| Lead Time for Changes    | < 1 hour     | < 1 day       | < 1 week       | > 1 week   |
| Change Failure Rate      | 0-15%        | 16-30%        | 31-45%         | > 45%      |
| Mean Time to Recovery    | < 1 hour     | < 1 day       | < 1 week       | > 1 week   |

Sources: GitHub/GitLab/Bitbucket deployments API, merged PRs to main, reverts, hotfixes, incidents.

### AI Coding Metrics

Track the adoption and ROI of AI coding tools across your organization:

- **GitHub Copilot** -- Suggestions shown/accepted, lines of code, active users (via the Copilot org API)
- **Cursor AI** -- Detected from PR metadata and commit patterns
- **Claude Code / Aider** -- Detected from commit co-author trailers and PR labels
- **Impact analysis** -- Compare cycle time, review time, and revert rates for AI-assisted vs non-AI pull requests
- **Cost tracking** -- Per-tool cost vs productivity gains

### SCM Integrations

| Provider     | PRs | Deployments | Teams | Reviews |
| ------------ | --- | ----------- | ----- | ------- |
| GitHub       | Yes | Yes         | Yes   | Yes     |
| GitLab       | Yes | Yes         | Yes   | --      |
| Bitbucket    | Yes | --          | Yes   | --      |

All providers implement the same `SCMProvider` protocol, so metrics are computed identically regardless of source.

### Developer Experience Surveys

Built-in survey templates based on the DX Core 4 and SPACE frameworks:

- **Pulse surveys** -- 3 quick questions (productivity, code review ease, deployment confidence)
- **Full DX surveys** -- 10 questions across speed, effectiveness, quality, and business impact
- **Analytics** -- Developer Experience Index (DXI) score, per-category breakdowns, text response aggregation
- **API-driven** -- Create, distribute, and analyze surveys via the REST API

### Web Dashboard

Start with `wellcode serve` and open `http://localhost:8787`:

- **Overview** -- Total PRs, merged PRs, cycle time, AI-assisted count
- **DORA** -- Four metrics with Elite/High/Medium/Low badge and trend chart
- **AI Metrics** -- Tool usage table, AI vs non-AI comparison, productivity impact
- **Pull Requests** -- Review time, PR size, reverts, self-merges
- **Surveys** -- Create surveys, view active surveys, analytics

The dashboard is a single-page app served directly by the FastAPI backend -- no separate Node.js build required.

### Data Persistence

Metrics are stored in a local SQLite database by default (`~/.wellcode/data/wellcode.db`). For team deployments, set `DATABASE_URL` to a PostgreSQL connection string.

15 tables covering pull requests, deployments, incidents, AI usage, issues, surveys, DORA snapshots, and more.

---

## API Reference

When running `wellcode serve`, the full OpenAPI docs are available at `http://localhost:8787/docs`.

Key endpoints:

| Method | Path                            | Description                      |
| ------ | ------------------------------- | -------------------------------- |
| GET    | `/health`                       | Health check + DB status         |
| GET    | `/api/v1/metrics/prs`           | PR metrics (filterable)          |
| GET    | `/api/v1/metrics/snapshots`     | Collection run history           |
| GET    | `/api/v1/dora`                  | DORA metrics for a period        |
| GET    | `/api/v1/dora/history`          | DORA trend over time             |
| GET    | `/api/v1/ai/impact`             | AI tool impact analysis          |
| GET    | `/api/v1/ai/usage`              | Daily AI tool usage data         |
| GET    | `/api/v1/surveys/templates`     | Available survey templates       |
| POST   | `/api/v1/surveys/create`        | Create a new survey              |
| GET    | `/api/v1/surveys/active`        | List active surveys              |
| POST   | `/api/v1/surveys/respond`       | Submit a survey response         |
| GET    | `/api/v1/surveys/{id}/analytics`| Survey analytics + DXI score     |

All endpoints accept `?start=YYYY-MM-DD&end=YYYY-MM-DD` for date filtering.

---

## Architecture

```
src/wellcode_cli/
  main.py                          # CLI entry point (Click commands)
  config.py                        # Configuration management
  api/                             # FastAPI web server
    app.py                         #   Application factory
    routes/                        #   health, metrics, dora, ai_metrics, surveys
  services/                        # Business logic (shared by CLI + API)
    dora.py                        #   DORA metric calculations
    ai_metrics.py                  #   AI tool detection + impact analysis
    collector.py                   #   Metric collection orchestrator
    surveys.py                     #   DX survey engine
  integrations/                    # External provider clients
    scm_protocol.py                #   Unified SCMProvider protocol
    github/provider.py             #   GitHub implementation
    gitlab/provider.py             #   GitLab implementation
    bitbucket/provider.py          #   Bitbucket implementation
  db/                              # Persistence layer
    engine.py                      #   SQLite/PostgreSQL connection factory
    models.py                      #   SQLAlchemy models (15 tables)
    repository.py                  #   Data access layer (MetricStore)
    migrations/                    #   Alembic migrations
  workers/                         # Background jobs
    scheduler.py                   #   APScheduler for periodic collection
  web/static/                      # Dashboard SPA
    index.html                     #   Single-page app (Tailwind + Chart.js)
  github/                          # Legacy GitHub integration (Rich display)
  jira/                            # JIRA integration
  linear/                          # Linear integration
  commands/                        # CLI command handlers
```

The key design principle is **separation of concerns**: integrations fetch data, services process it, and the CLI/API are thin presentation layers. This makes it straightforward to add new data sources without touching business logic.

---

## Building Plugins

Wellcode uses a protocol-based plugin architecture. Adding a new SCM provider (e.g., Azure DevOps, Gitea) requires implementing a single Python class.

### Step 1: Implement the `SCMProvider` protocol

Create a new file at `src/wellcode_cli/integrations/<your_provider>/provider.py`:

```python
from datetime import datetime
from typing import Optional

from wellcode_cli.config import get_config_value
from wellcode_cli.integrations.scm_protocol import (
    SCMDeployment,
    SCMPullRequest,
    SCMRepository,
    SCMTeam,
)


class AzureDevOpsProvider:
    """Azure DevOps implementation of the SCM provider protocol."""

    def __init__(self, token: Optional[str] = None, org: Optional[str] = None):
        self._token = token or get_config_value("AZURE_DEVOPS_TOKEN")
        self._org = org or get_config_value("AZURE_DEVOPS_ORG")

    @property
    def provider_name(self) -> str:
        return "azure_devops"

    def get_repositories(self) -> list[SCMRepository]:
        # Call the Azure DevOps REST API and return SCMRepository objects
        ...

    def get_pull_requests(
        self,
        since: datetime,
        until: datetime,
        repo_full_name: Optional[str] = None,
        author: Optional[str] = None,
    ) -> list[SCMPullRequest]:
        # Fetch pull requests and map them to SCMPullRequest
        ...

    def get_deployments(
        self,
        since: datetime,
        until: datetime,
        repo_full_name: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> list[SCMDeployment]:
        # Fetch release/deployment data and map to SCMDeployment
        ...

    def get_teams(self) -> list[SCMTeam]:
        # Fetch teams and members
        ...
```

The protocol defines five data classes you must map your provider's data into:

| Data class        | Purpose                                      |
| ----------------- | -------------------------------------------- |
| `SCMRepository`   | Repository metadata (name, default branch)   |
| `SCMPullRequest`  | PR with timestamps, sizes, review info        |
| `SCMDeployment`   | Deployment event (env, status, timestamps)   |
| `SCMTeam`         | Team with member list                        |
| `SCMReview`       | Individual code review                       |

### Step 2: Register the provider

Edit `src/wellcode_cli/services/collector.py` and add your provider to `_get_configured_providers()`:

```python
def _get_configured_providers() -> list[SCMProvider]:
    providers = []

    # ... existing providers ...

    if get_config_value("AZURE_DEVOPS_TOKEN"):
        from ..integrations.azure_devops.provider import AzureDevOpsProvider
        providers.append(AzureDevOpsProvider())

    return providers
```

That's it. The collector will automatically call your provider during `wellcode collect`, store the data in the same database tables, and all downstream features (DORA metrics, AI detection, dashboards, API) work without any further changes.

### Step 3: Add config keys (optional)

If your provider needs configuration, add getter functions to `src/wellcode_cli/config.py`:

```python
def get_azure_devops_token() -> Optional[str]:
    return get_config_value("AZURE_DEVOPS_TOKEN")

def get_azure_devops_org() -> Optional[str]:
    return get_config_value("AZURE_DEVOPS_ORG")
```

Users can then set these via `~/.wellcode/config.json` or environment variables.

### Adding a new issue tracker

Issue trackers (JIRA, Linear) currently use their own collection logic in `src/wellcode_cli/jira/` and `src/wellcode_cli/linear/`. To add a new one, follow the same pattern: create a module under `integrations/`, map issues to `IssueMetric` DB models, and wire it into the collector.

### Adding a new AI tool

To detect a new AI coding tool (e.g., Windsurf, Cody), add patterns to `src/wellcode_cli/services/ai_metrics.py`:

```python
# In detect_ai_tool_from_pr()
if "windsurf" in text or "windsurf" in label_text:
    return "windsurf"
```

For tools with their own usage API, add a collection function similar to `collect_copilot_metrics()` and call it from the collector.

---

## Configuration

All configuration can be set via `~/.wellcode/config.json` or environment variables:

| Variable                    | Description                          |
| --------------------------- | ------------------------------------ |
| `GITHUB_TOKEN`              | GitHub personal access token         |
| `GITHUB_ORG`                | GitHub organization name             |
| `GITHUB_MODE`               | `organization` or `personal`         |
| `GITLAB_TOKEN`              | GitLab personal access token         |
| `GITLAB_URL`                | GitLab instance URL (default: gitlab.com) |
| `BITBUCKET_USERNAME`        | Bitbucket username                   |
| `BITBUCKET_APP_PASSWORD`    | Bitbucket app password               |
| `BITBUCKET_WORKSPACE`       | Bitbucket workspace slug             |
| `JIRA_URL`                  | JIRA instance URL                    |
| `JIRA_EMAIL`                | JIRA account email                   |
| `JIRA_API_TOKEN`            | JIRA API token                       |
| `LINEAR_API_KEY`            | Linear API key                       |
| `SPLIT_API_KEY`             | Split.io API key                     |
| `ANTHROPIC_API_KEY`         | Anthropic API key (for AI insights)  |
| `DATABASE_URL`              | PostgreSQL URL (default: SQLite)     |

---

## Self-Hosting with Docker

The included `docker-compose.yml` runs Wellcode with PostgreSQL:

```bash
# Copy and edit your environment variables
cp .env.example .env

# Start the stack
docker compose up -d

# Dashboard: http://localhost:8787
# API docs:  http://localhost:8787/docs
```

The compose file includes:
- **wellcode** -- API server + web dashboard + background collector
- **postgres** -- PostgreSQL 16 for persistent storage

---

## Development

```bash
git clone https://github.com/wellcode-ai/wellcode-cli.git
cd wellcode-cli
python -m venv venv && source venv/bin/activate
pip install -e ".[dev,test]"

# Run tests
pytest

# Start dev server with auto-reload
wellcode serve --reload

# Run linting
ruff check src/
```

### Project structure

- `src/wellcode_cli/` -- All source code
- `tests/` -- Test suite
- `alembic.ini` -- Database migration config
- `Dockerfile` -- Container image
- `docker-compose.yml` -- Full stack deployment

---

## Comparison with Commercial Tools

| Feature                    | Wellcode   | Swarmia     | GetDX       |
| -------------------------- | ---------- | ----------- | ----------- |
| DORA metrics               | Yes        | Yes         | Yes         |
| AI coding metrics          | Yes        | Yes         | Yes         |
| GitHub                     | Yes        | Yes         | Yes         |
| GitLab                     | Yes        | Yes         | Yes         |
| Bitbucket                  | Yes        | No          | Yes         |
| JIRA                       | Yes        | Yes         | Yes         |
| Linear                     | Yes        | Yes         | Yes         |
| DX surveys                 | Yes        | Yes         | Yes         |
| Web dashboard              | Yes        | Yes         | Yes         |
| CLI interface              | Yes        | No          | No          |
| AI-powered insights        | Yes        | No          | Yes         |
| Self-hosted                | Yes        | No          | No          |
| Open source                | Yes        | No          | No          |
| Plugin architecture        | Yes        | No          | No          |
| Price                      | Free       | From $20/dev| From $20/dev|

---

## Support

- Documentation: https://cli.wellcode.ai
- Issues: https://github.com/wellcode-ai/wellcode-cli/issues
- Email: support@wellcode.ai

## Contributing

We welcome contributions. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Areas where help is especially welcome:
- New SCM provider plugins (Azure DevOps, Gitea, Forgejo)
- Incident management integrations (PagerDuty, Opsgenie)
- CI/CD integrations (Jenkins, CircleCI, Buildkite)
- Slack/Teams notification support
- Additional AI tool detection patterns

## License

MIT License -- see [LICENSE](LICENSE) for details.
