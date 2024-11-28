<p align="center">
  <img src="https://cli.wellcode.ai/wellcode.svg" alt="Wellcode Logo" width="200"/>
</p>

<h1 align="center">Wellcode CLI</h1>

<p align="center">
  <strong>Engineering Metrics and Insights at Your Fingertips</strong>
</p>

<p align="center">
  <a href="https://pypi.org/project/wellcode-cli/"><img src="https://img.shields.io/pypi/v/wellcode-cli.svg" alt="PyPI version"></a>
  <a href="https://pypi.org/project/wellcode-cli/"><img src="https://img.shields.io/pypi/pyversions/wellcode-cli.svg" alt="Python versions"></a>
  <a href="https://github.com/wellcode-ai/wellcode-cli/blob/main/LICENSE"><img src="https://img.shields.io/github/license/wellcode-ai/wellcode-cli.svg" alt="License"></a>
  <a href="https://github.com/wellcode-ai/wellcode-cli/actions"><img src="https://github.com/wellcode-ai/wellcode-cli/workflows/tests/badge.svg" alt="Tests"></a>
  <a href="https://codecov.io/gh/wellcode-ai/wellcode-cli"><img src="https://codecov.io/gh/wellcode-ai/wellcode-cli/branch/main/graph/badge.svg" alt="Coverage"></a>
</p>

## 🚀 Installation

```bash
pip install wellcode-cli
```

## 🏃 Quick Start

1. **Initial Setup**
```bash
wellcode-cli config
```

This will guide you through:
- GitHub App installation for your organization
- Optional Linear integration
- Optional Split.io integration
- Optional Anthropic integration (for AI-powered insights)

2. **Enable Shell Completion (Optional)**
```bash
# For bash
wellcode-cli completion bash >> ~/.bashrc

# For zsh
wellcode-cli completion zsh >> ~/.zshrc

# For fish
wellcode-cli completion fish > ~/.config/fish/completions/wellcode-cli.fish
```

## 💻 Usage

### Review Metrics
```bash
# Review last 7 days
wellcode-cli review

# Review specific date range
wellcode-cli review --start-date 2024-01-01 --end-date 2024-01-31

# Review specific user
wellcode-cli review --user johndoe

# Review specific team
wellcode-cli review --team engineering
```

### Interactive Mode
```bash
wellcode-cli

# Then use natural language:
> check performance last week
> show metrics for team frontend
> how was johndoe doing yesterday
```

## ✨ Features

- 📊 GitHub metrics analysis
- 📈 Linear issue tracking integration
- 🔄 Split.io feature flag metrics
- 🤖 AI-powered insights (via Anthropic)
- 💬 Natural language interface
- 📱 Interactive mode

## ⚙️ Configuration

### GitHub App Installation
1. Run `wellcode-cli config`
2. Enter your organization name
3. Follow the GitHub App installation link
4. Select your organization and repositories

### Optional Integrations
- **Linear**: Issue tracking metrics
- **Split.io**: Feature flag analytics
- **Anthropic**: AI-powered insights

## 🆘 Support

- Documentation: https://cli.wellcode.ai
- Issues: https://github.com/wellcode-ai/wellcode-cli/issues
- Email: support@wellcode.ai

## 📄 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## 💖 Contributors

Thanks goes to these wonderful people:

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<!-- Add contributors here -->
<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->
<!-- ALL-CONTRIBUTORS-LIST:END -->

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details