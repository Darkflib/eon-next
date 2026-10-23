# eon-next

A simple Python CLI utility to log into the EON Next website and retrieve electricity account information.

## Features

- Log into EON Next account with an account API key (or, for older accounts, username and password)
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

### Authentication

E.ON Next moved customer sign-in to Auth0 (`auth.eonnext.com`, with a
verification code). Its Kraken API no longer accepts email and password, so
`--username`/`--password` now fail with a message pointing you at API keys.
See [issue #8](https://github.com/Darkflib/eon-next/issues/8) for background.

Log in with your account API key (`sk_live_...`) instead:

```bash
eon-next --api-key sk_live_your_key
```

The key is swapped for a short-lived token with `obtainKrakenToken(input: {APIKey})`.
The cached token is stored under a hash of the key, never the key itself.

#### Getting an API key

This CLI does not create keys. Ways to get one:

- **Already have one?** Another integration (for example a Home Assistant add-on)
  may already use a key for your account. Reuse that key.
- **E.ON customer services** can in principle issue one.
- **From your browser session** (confirmed October 2026):
  1. Sign in at [eonnext.com](https://www.eonnext.com) and open your browser's
     developer tools on the Network tab.
  2. Find a request to `api.eonnext-kraken.energy/v1/graphql/` and copy its
     `Authorization` request header. This is an Auth0 token that Kraken accepts
     as-is (no `Bearer`/`JWT` prefix). It expires after about an hour.
  3. With that header, check `query { viewer { liveSecretKey } }`. Only if it
     returns `null`, run `mutation { regenerateSecretKey { key } }`.
  4. The full `sk_live_...` key is shown **once**: store it straight away.

Caveats:

- Each account has **one** live key, shared by every app that uses it.
- `regenerateSecretKey` **replaces** the existing key, cutting off every app still
  using the old one. Check `query { viewer { liveSecretKey } }` first: it returns
  a masked value if a key exists, or `null` if not.
- Some accounts may have API access switched off; login then fails with
  `KT-CT-11334`.

### Using Environment Variables

Set credentials via environment variables to avoid typing them each time:

```bash
export EON_API_KEY=sk_live_your_key
eon-next
```

`EON_USERNAME` and `EON_PASSWORD` are still read, for accounts where
email/password login still works. If `EON_API_KEY` is set it takes precedence.

With 1Password, inject the key without exporting it:

```bash
EON_API_KEY="op://<vault>/<item>/api_key" op run -- eon-next
```

### Get Tariff Information

Include tariff pricing details:

```bash
eon-next -k sk_live_your_key --tariff
```

### Get Usage Information

Include usage statistics:

```bash
eon-next -k sk_live_your_key --usage
```

### Get Everything

Retrieve balance, tariff, and usage:

```bash
eon-next -k sk_live_your_key --tariff --usage
```

### JSON Output

Get output in JSON format for scripting:

```bash
eon-next -k sk_live_your_key --json
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

**Security Notice**: Never commit your credentials to version control. Always use environment variables or secure credential storage for your EON Next API key, username and password.