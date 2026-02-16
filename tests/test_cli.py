"""Tests for the CLI interface."""

from unittest.mock import Mock, patch

from click.testing import CliRunner

from eon_next.cli import main


def test_cli_missing_username() -> None:
    """Test that CLI requires username."""
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code != 0
    assert "username" in result.output.lower() or "missing" in result.output.lower()


def test_cli_missing_password() -> None:
    """Test that CLI requires password."""
    runner = CliRunner()
    result = runner.invoke(main, ["--username", "test@example.com"])
    assert result.exit_code != 0


@patch("eon_next.cli.EONNextClient")
def test_cli_basic_usage(mock_client_class: Mock) -> None:
    """Test basic CLI usage."""
    # Setup mock
    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=None)
    mock_client.login = Mock()
    mock_client.get_balance = Mock(return_value={"balance": "£123.45", "currency": "GBP"})
    mock_client_class.return_value = mock_client

    # Test
    runner = CliRunner()
    result = runner.invoke(main, ["--username", "test@example.com", "--password", "password123"])

    assert result.exit_code == 0
    assert "123.45" in result.output
    mock_client.login.assert_called_once()
    mock_client.get_balance.assert_called_once()


@patch("eon_next.cli.EONNextClient")
def test_cli_with_tariff_flag(mock_client_class: Mock) -> None:
    """Test CLI with --tariff flag."""
    # Setup mock
    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=None)
    mock_client.login = Mock()
    mock_client.get_balance = Mock(return_value={"balance": "£123.45", "currency": "GBP"})
    mock_client.get_tariff = Mock(
        return_value={
            "tariff_name": "EON Next Flexi",
            "unit_rate": "25.5p",
            "standing_charge": "45p",
        }
    )
    mock_client_class.return_value = mock_client

    # Test
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--username", "test@example.com", "--password", "password123", "--tariff"],
    )

    assert result.exit_code == 0
    assert "123.45" in result.output
    assert "Tariff" in result.output
    mock_client.get_tariff.assert_called_once()


@patch("eon_next.cli.EONNextClient")
def test_cli_with_usage_flag(mock_client_class: Mock) -> None:
    """Test CLI with --usage flag."""
    # Setup mock
    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=None)
    mock_client.login = Mock()
    mock_client.get_balance = Mock(return_value={"balance": "£123.45", "currency": "GBP"})
    mock_client.get_usage = Mock(
        return_value={
            "daily_usage": "12 kWh",
            "weekly_usage": "84 kWh",
            "monthly_usage": "360 kWh",
        }
    )
    mock_client_class.return_value = mock_client

    # Test
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--username", "test@example.com", "--password", "password123", "--usage"],
    )

    assert result.exit_code == 0
    assert "123.45" in result.output
    assert "Usage" in result.output
    mock_client.get_usage.assert_called_once()


@patch("eon_next.cli.EONNextClient")
def test_cli_json_output(mock_client_class: Mock) -> None:
    """Test CLI with JSON output."""
    import json

    # Setup mock
    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=None)
    mock_client.login = Mock()
    mock_client.get_balance = Mock(return_value={"balance": "£123.45", "currency": "GBP"})
    mock_client_class.return_value = mock_client

    # Test
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["--username", "test@example.com", "--password", "password123", "--json"],
    )

    assert result.exit_code == 0
    # Parse JSON from stdout
    output_lines = result.output.strip().split("\n")
    excluded_prefixes = ("Logging", "Successfully", "Retrieving")
    json_output = "\n".join(
        line for line in output_lines if line.strip() and not line.startswith(excluded_prefixes)
    )
    data = json.loads(json_output)
    assert "balance" in data
    assert data["balance"]["balance"] == "£123.45"


@patch("eon_next.cli.EONNextClient")
def test_cli_login_error(mock_client_class: Mock) -> None:
    """Test CLI handles login errors."""
    # Setup mock
    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=None)
    mock_client.login = Mock(side_effect=RuntimeError("Login failed"))
    mock_client_class.return_value = mock_client

    # Test
    runner = CliRunner()
    result = runner.invoke(main, ["--username", "test@example.com", "--password", "password123"])

    assert result.exit_code != 0
    assert "Error" in result.output or "Login failed" in result.output
