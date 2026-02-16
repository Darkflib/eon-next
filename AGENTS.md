# AGENTS.md

This document provides guidance for AI agents working on the eon-next codebase.

## Project Overview

**eon-next** is a Python CLI utility that allows users to log into their EON Next electricity account and retrieve account information including:
- Current electricity credit balance
- Tariff pricing information
- Usage statistics

The tool is designed to be simple, focused, and intentionally avoids over-engineering.

## Architecture

### Core Components

1. **CLI Interface** (`src/eon_next/cli.py`)
   - Command-line interface built with Click
   - Handles argument parsing and user interaction
   - Supports environment variables for credentials (EON_USERNAME, EON_PASSWORD)
   - Provides both human-readable and JSON output formats
   - Command-line options: `--username`, `--password`, `--tariff`, `--usage`, `--json`

2. **API Client** (`src/eon_next/client.py`)
   - HTTP client for EON Next website interaction
   - Built with httpx for async-capable HTTP requests
   - Uses BeautifulSoup4 and lxml for HTML parsing
   - Implements context manager pattern for resource cleanup
   - Key methods:
     - `login()` - Authenticates with EON Next
     - `get_balance()` - Retrieves current credit balance
     - `get_tariff()` - Fetches tariff pricing (placeholder implementation)
     - `get_usage()` - Gets usage statistics (placeholder implementation)

3. **Package Entry Point** (`src/eon_next/__init__.py`)
   - Exports the main CLI function
   - Defines package version

### Project Structure

```
eon-next/
├── src/
│   └── eon_next/
│       ├── __init__.py      # Package initialization
│       ├── cli.py           # Command-line interface
│       └── client.py        # EON Next API client
├── tests/
│   ├── test_cli.py          # CLI tests
│   └── test_client.py       # Client tests
├── pyproject.toml           # Project configuration
├── uv.lock                  # Dependency lock file
└── README.md                # User-facing documentation
```

## Dependencies

### Runtime Dependencies
- **httpx** (>=0.27.0) - Modern HTTP client with async support
- **beautifulsoup4** (>=4.12.0) - HTML parsing
- **lxml** (>=5.0.0) - Fast XML/HTML parser for BeautifulSoup
- **click** (>=8.1.0) - Command-line interface framework

### Development Dependencies
- **pytest** (>=8.0.0) - Testing framework
- **pytest-asyncio** (>=0.23.0) - Async test support
- **pytest-mock** (>=3.12.0) - Mocking utilities
- **mypy** (>=1.8.0) - Static type checking
- **ruff** (>=0.6.0) - Linting and formatting

Note: pytest-cov is NOT currently included in dev dependencies.

## Development Workflow

### Setup
```bash
# Clone and install
git clone https://github.com/Darkflib/eon-next.git
cd eon-next
uv sync --all-extras
```

### Code Quality Tools

1. **Linting** (Ruff)
   - Configuration in `pyproject.toml` ([tool.ruff.lint])
   - Selected rules: E, F, I, N, W, UP, B, C4, SIM, TCH
   - Line length: 100 characters
   - Target: Python 3.12+
   - Commands: `uv run ruff check src/ tests/`

2. **Formatting** (Ruff)
   - Commands: `uv run ruff format src/ tests/`

3. **Type Checking** (mypy)
   - Strict mode enabled
   - Configuration in `pyproject.toml` ([tool.mypy])
   - Commands: `uv run mypy src/`

4. **Testing** (pytest)
   - Test directory: `tests/`
   - Pattern: `test_*.py`
   - Commands: `uv run pytest`

## Testing Strategy

### Test Coverage

1. **CLI Tests** (`tests/test_cli.py`)
   - Validates argument parsing and validation
   - Tests all command-line flags (--tariff, --usage, --json)
   - Mocks the EONNextClient to avoid real API calls
   - Verifies error handling and user feedback

2. **Client Tests** (`tests/test_client.py`)
   - Tests client initialization and context manager
   - Validates login flow (both success and failure)
   - Ensures login is required for protected operations
   - Mocks httpx.Client to avoid real HTTP requests

### Testing Best Practices
- All tests use mocking to avoid external dependencies
- Tests verify both success and failure paths
- Type hints are used consistently in test functions

## Important Technical Details

### Security Considerations
- Credentials should NEVER be committed to version control
- The `--password` flag uses `hide_input=True` to prevent echoing
- Environment variables (EON_USERNAME, EON_PASSWORD) are the recommended credential storage method

### Implementation Status
- **Fully Implemented**: Login, balance retrieval, CLI framework
- **Placeholder Implementations**: `get_tariff()` and `get_usage()` methods return mock data
  - These would need actual page navigation and parsing logic to work with the real EON Next website

### Error Handling
- HTTP errors are propagated via `raise_for_status()`
- Login failures are detected by checking response URL and content
- RuntimeError is raised for authentication issues
- CLI captures all exceptions and exits with code 1 on failure

### HTML Parsing Strategy
- Uses BeautifulSoup with lxml parser for performance
- Looks for CSRF tokens in login forms
- Balance parsing looks for `<span class="balance">` elements
- Fallback parsing strategies are implemented where appropriate

## Development Guidelines

### Code Style
- Follow the project's simplicity principle - avoid over-engineering
- Use type hints consistently (enforced by mypy strict mode)
- Keep functions focused and single-purpose
- Prefer explicit over implicit

### Making Changes
1. Ensure all changes pass linting: `uv run ruff check src/ tests/`
2. Format code: `uv run ruff format src/ tests/`
3. Verify type correctness: `uv run mypy src/`
4. Run tests: `uv run pytest`
5. Update this document if architecture or dependencies change

### Adding New Features
- Keep the CLI simple and focused
- Follow the existing patterns in `cli.py` and `client.py`
- Add corresponding tests for new functionality
- Update README.md with new usage examples if needed
- Avoid adding features that aren't explicitly requested

## Python Version Support

- **Minimum**: Python 3.12
- **Maximum**: Python 3.13 (exclusive)
- Specified in pyproject.toml: `requires-python = ">=3.12,<3.14"`

## Package Management

This project uses **uv** for package management, which provides:
- Fast dependency resolution
- Lock file support (uv.lock)
- Virtual environment management
- Build backend support

## Entry Points

The CLI is exposed as a console script:
- Command: `eon-next`
- Entry point: `eon_next:main`
- Defined in pyproject.toml [project.scripts]
