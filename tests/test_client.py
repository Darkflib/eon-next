"""Tests for the EON Next client."""

from unittest.mock import Mock, patch

import pytest

from eon_next.client import EONNextClient


def test_client_initialization() -> None:
    """Test that the client can be initialized with credentials."""
    client = EONNextClient("test@example.com", "password123")
    assert client.username == "test@example.com"
    assert client.password == "password123"
    assert not client._logged_in
    client.close()


def test_client_context_manager() -> None:
    """Test that the client works as a context manager."""
    with EONNextClient("test@example.com", "password123") as client:
        assert client.username == "test@example.com"


def test_login_required_for_balance() -> None:
    """Test that balance retrieval requires login."""
    client = EONNextClient("test@example.com", "password123")
    with pytest.raises(RuntimeError, match="Must login first"):
        client.get_balance()
    client.close()


def test_login_required_for_tariff() -> None:
    """Test that tariff retrieval requires login."""
    client = EONNextClient("test@example.com", "password123")
    with pytest.raises(RuntimeError, match="Must login first"):
        client.get_tariff()
    client.close()


def test_login_required_for_usage() -> None:
    """Test that usage retrieval requires login."""
    client = EONNextClient("test@example.com", "password123")
    with pytest.raises(RuntimeError, match="Must login first"):
        client.get_usage()
    client.close()


@patch("eon_next.client.httpx.Client")
def test_successful_login(mock_client_class: Mock) -> None:
    """Test successful login flow."""
    # Setup mock
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    # Mock GET request for login page
    mock_get_response = Mock()
    mock_get_response.text = (
        '<html><body><input name="csrf_token" value="test_token"/></body></html>'
    )
    mock_get_response.raise_for_status = Mock()

    # Mock POST request for login
    mock_post_response = Mock()
    mock_post_response.url = "https://eonnext.com/dashboard"
    mock_post_response.text = "Welcome to your dashboard"
    mock_post_response.raise_for_status = Mock()

    mock_client.get.return_value = mock_get_response
    mock_client.post.return_value = mock_post_response

    # Test login
    client = EONNextClient("test@example.com", "password123")
    client.login()

    assert client._logged_in
    mock_client.get.assert_called_once()
    mock_client.post.assert_called_once()
    client.close()


@patch("eon_next.client.httpx.Client")
def test_failed_login(mock_client_class: Mock) -> None:
    """Test failed login flow."""
    # Setup mock
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    # Mock GET request for login page
    mock_get_response = Mock()
    mock_get_response.text = "<html><body></body></html>"
    mock_get_response.raise_for_status = Mock()

    # Mock POST request that stays on signin page (login failed)
    mock_post_response = Mock()
    # Use a Mock that implements __str__ properly
    mock_url = Mock()
    mock_url.__str__ = Mock(return_value="https://eonnext.com/dashboard/sign-in")
    mock_post_response.url = mock_url
    mock_post_response.text = "Invalid credentials"
    mock_post_response.raise_for_status = Mock()

    mock_client.get.return_value = mock_get_response
    mock_client.post.return_value = mock_post_response

    # Test login failure
    client = EONNextClient("test@example.com", "wrong_password")
    with pytest.raises(RuntimeError, match="Login failed"):
        client.login()

    assert not client._logged_in
    client.close()


@patch("eon_next.client.httpx.Client")
def test_get_balance_after_login(mock_client_class: Mock) -> None:
    """Test getting balance after successful login."""
    # Setup mock
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    # Mock balance page response
    mock_balance_response = Mock()
    mock_balance_response.text = '<html><body><span class="balance">£123.45</span></body></html>'
    mock_balance_response.raise_for_status = Mock()

    mock_client.get.return_value = mock_balance_response

    # Test
    client = EONNextClient("test@example.com", "password123")
    client._logged_in = True  # Simulate successful login

    balance = client.get_balance()

    assert "balance" in balance
    assert balance["currency"] == "GBP"
    client.close()
