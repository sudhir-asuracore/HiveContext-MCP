# Contributing to HiveContext-MCP

Thank you for your interest in contributing to HiveContext FastMCP server!

## Development Setup

1. Fork the repository and create a new feature branch.
2. Requirements:
   - Python 3.12+
   - AWS SAM CLI
   - Docker (for SAM container builds)
3. Copy `.env.example` to `.env` and `samconfig.toml.example` to `samconfig.toml`.
4. Test and validate:
   ```bash
   sam validate --lint
   sam build --use-container
   ```

## Pull Request Guidelines

- Never commit credentials or live database URLs in templates or configuration files.
- Ensure SAM builds succeed before opening a pull request.
