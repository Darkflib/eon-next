"""EON Next API Client for retrieving account information."""

from typing import Any

import httpx
from bs4 import BeautifulSoup


class EONNextClient:
    """Client for interacting with the EON Next website."""

    BASE_URL = "https://eonnext.com"
    LOGIN_URL = f"{BASE_URL}/dashboard/sign-in"
    ACCOUNT_URL = f"{BASE_URL}/dashboard"

    def __init__(self, username: str, password: str) -> None:
        """Initialize the EON Next client.

        Args:
            username: The user's email address.
            password: The user's password.
        """
        self.username = username
        self.password = password
        self.client = httpx.Client(follow_redirects=True, timeout=30.0)
        self._logged_in = False

    def __enter__(self) -> "EONNextClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def login(self) -> None:
        """Log in to the EON Next website.

        Raises:
            RuntimeError: If login fails.
        """
        # First, get the login page to obtain any CSRF tokens
        response = self.client.get(self.LOGIN_URL)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # Look for CSRF token or similar
        csrf_token: str | None = None
        csrf_input = soup.find("input", {"name": "csrf_token"})
        if csrf_input and hasattr(csrf_input, "get"):
            token_value = csrf_input.get("value")
            if isinstance(token_value, str):
                csrf_token = token_value

        # Prepare login data
        login_data: dict[str, str] = {
            "username": self.username,
            "password": self.password,
        }

        if csrf_token:
            login_data["csrf_token"] = csrf_token

        # Submit login form
        response = self.client.post(self.LOGIN_URL, data=login_data)
        response.raise_for_status()

        # Check if login was successful
        url_str = str(response.url)
        if "sign-in" in url_str.lower() or "error" in response.text.lower():
            raise RuntimeError("Login failed. Please check your credentials.")

        self._logged_in = True

    def get_balance(self) -> dict[str, Any]:
        """Get the current electricity credit balance.

        Returns:
            A dictionary containing balance information.

        Raises:
            RuntimeError: If not logged in or if balance retrieval fails.
        """
        if not self._logged_in:
            raise RuntimeError("Must login first")

        response = self.client.get(self.ACCOUNT_URL)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "lxml")

        # Parse the balance from the page
        # This is a placeholder - actual parsing will depend on the page structure
        balance_element = soup.find("span", {"class": "balance"})
        if balance_element:
            balance_text = balance_element.text.strip()
        else:
            # Try to find any element with £ sign as fallback
            balance_text = "Balance information not found"

        return {
            "balance": balance_text,
            "currency": "GBP",
        }

    def get_tariff(self) -> dict[str, Any]:
        """Get the current tariff pricing information.

        Returns:
            A dictionary containing tariff information.

        Raises:
            RuntimeError: If not logged in or if tariff retrieval fails.
        """
        if not self._logged_in:
            raise RuntimeError("Must login first")

        # This would need to navigate to the tariff page
        # Placeholder implementation
        return {
            "tariff_name": "Not implemented",
            "unit_rate": "N/A",
            "standing_charge": "N/A",
        }

    def get_usage(self) -> dict[str, Any]:
        """Get the current usage information.

        Returns:
            A dictionary containing usage information.

        Raises:
            RuntimeError: If not logged in or if usage retrieval fails.
        """
        if not self._logged_in:
            raise RuntimeError("Must login first")

        # This would need to navigate to the usage page
        # Placeholder implementation
        return {
            "daily_usage": "N/A",
            "weekly_usage": "N/A",
            "monthly_usage": "N/A",
        }
