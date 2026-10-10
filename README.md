# eon-next

A simple Python CLI utility to log into the EON Next website and retrieve electricity account information.

## Features

- Log into EON Next account with username and password
- Retrieve current electricity credit balance
- Optionally retrieve tariff pricing information
- Optionally retrieve usage information
- Output in human-readable or JSON format

## Requirements

- Python 3.12 or 3.13
- uv (for package management)

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/Darkflib/eon-next.git
cd eon-next
uv sync
```

Or install directly:

```bash
uv pip install .
```

## Usage

### Basic Usage

Retrieve your current electricity credit balance:

```bash
eon-next --username your.email@example.com --password your_password
```

### Using Environment Variables

Set credentials via environment variables to avoid typing them each time:

```bash
export EON_USERNAME=your.email@example.com
export EON_PASSWORD=your_password
eon-next
```

### Get Tariff Information

Include tariff pricing details:

```bash
eon-next -u your.email@example.com -p your_password --tariff
```

### Get Usage Information

Include usage statistics:

```bash
eon-next -u your.email@example.com -p your_password --usage
```

### Get Everything

Retrieve balance, tariff, and usage:

```bash
eon-next -u your.email@example.com -p your_password --tariff --usage
```

### JSON Output

Get output in JSON format for scripting:

```bash
eon-next -u your.email@example.com -p your_password --json
```

## Development

### Setup

Install development dependencies:

```bash
uv sync --all-extras
```

### Linting and Formatting

```bash
# Run ruff linter
uv run ruff check src/ tests/

# Auto-fix linting issues
uv run ruff check --fix src/ tests/

# Format code
uv run ruff format src/ tests/
```

### Type Checking

```bash
uv run mypy src/
```

### Testing

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_client.py -v
```

## License

See LICENSE file for details.

## Note

This is a personal utility tool designed to scratch a specific itch. It is intentionally kept simple and focused on the core functionality without over-engineering.

**Security Notice**: Never commit your credentials to version control. Always use environment variables or secure credential storage for your EON Next username and password.