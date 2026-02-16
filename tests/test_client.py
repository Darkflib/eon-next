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

    # Mock POST request for login mutation
    mock_login_response = Mock()
    mock_login_response.raise_for_status = Mock()
    mock_login_response.json = Mock(
        return_value={"data": {"obtainKrakenToken": {"token": "jwt-token"}}}
    )

    # Mock POST request for getUserAccounts query
    mock_accounts_response = Mock()
    mock_accounts_response.raise_for_status = Mock()
    mock_accounts_response.json = Mock(
        return_value={
            "data": {
                "viewer": {
                    "accounts": [
                        {
                            "accountType": "DOMESTIC",
                            "balance": "123.45",
                            "id": "acc-id",
                            "number": "A-12345678",
                            "properties": [{"address": "Test Address", "id": "prop-id"}],
                        }
                    ],
                    "email": "test@example.com",
                    "id": "viewer-id",
                }
            }
        }
    )

    mock_client.post.side_effect = [mock_login_response, mock_accounts_response]

    # Test login
    client = EONNextClient("test@example.com", "password123")
    client.login()

    assert client._logged_in
    assert client._token == "jwt-token"
    assert client._account_number == "A-12345678"
    assert mock_client.post.call_count == 2
    client.close()


@patch("eon_next.client.httpx.Client")
def test_failed_login(mock_client_class: Mock) -> None:
    """Test failed login flow."""
    # Setup mock
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    # Mock POST request for login mutation with no token
    mock_login_response = Mock()
    mock_login_response.raise_for_status = Mock()
    mock_login_response.json = Mock(return_value={"data": {"obtainKrakenToken": None}})

    mock_client.post.return_value = mock_login_response

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

    # Mock GraphQL account query response
    mock_balance_response = Mock()
    mock_balance_response.raise_for_status = Mock()
    mock_balance_response.json = Mock(
        return_value={
            "data": {
                "viewer": {
                    "accounts": [
                        {
                            "accountType": "DOMESTIC",
                            "balance": "123.45",
                            "id": "acc-id",
                            "number": "A-12345678",
                            "properties": [{"address": "Test Address", "id": "prop-id"}],
                        }
                    ],
                    "email": "test@example.com",
                    "id": "viewer-id",
                }
            }
        }
    )

    mock_client.post.return_value = mock_balance_response

    # Test
    client = EONNextClient("test@example.com", "password123")
    client._logged_in = True  # Simulate successful login
    client._token = "jwt-token"

    balance = client.get_balance()

    assert "balance" in balance
    assert balance["balance"] == "123.45"
    assert balance["currency"] == "GBP"
    assert balance["account_number"] == "A-12345678"
    client.close()


@patch("eon_next.client.httpx.Client")
def test_get_balance_uses_smart_payg_snapshot_when_account_balance_zero(
    mock_client_class: Mock,
) -> None:
    """Test smart PAYG fallback uses prepay snapshot when account balance is zero."""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    # 1) getUserAccounts returns zero account balance
    mock_accounts_response = Mock()
    mock_accounts_response.raise_for_status = Mock()
    mock_accounts_response.json = Mock(
        return_value={
            "data": {
                "viewer": {
                    "accounts": [
                        {
                            "accountType": "DOMESTIC",
                            "balance": 0,
                            "id": "acc-id",
                            "number": "A-736729C3",
                            "properties": [{"address": "Test Address", "id": "prop-id"}],
                        }
                    ],
                    "email": "test@example.com",
                    "id": "viewer-id",
                }
            }
        }
    )

    # 2) smartDevicesForAccount returns smart device id
    mock_smart_devices_response = Mock()
    mock_smart_devices_response.raise_for_status = Mock()
    mock_smart_devices_response.json = Mock(
        return_value={
            "data": {
                "account": {
                    "id": "1923278",
                    "properties": [
                        {
                            "electricityMeterPoints": [
                                {
                                    "id": "1630709",
                                    "meters": [
                                        {
                                            "id": "8269374",
                                            "smartDevices": [
                                                {
                                                    "deviceId": "00-1C-55-00-20-04-83-67",
                                                    "weeklyDebtRecoveryRateInPence": 0,
                                                }
                                            ],
                                        }
                                    ],
                                    "mpan": "1100010855751",
                                    "targetSsd": "2021-04-12",
                                }
                            ],
                            "gasMeterPoints": [],
                            "id": "1849141",
                        }
                    ],
                }
            }
        }
    )

    # 3) balanceForDevice returns credit in pence
    mock_device_balance_response = Mock()
    mock_device_balance_response.raise_for_status = Mock()
    mock_device_balance_response.json = Mock(
        return_value={
            "data": {
                "prepayBalanceSnapshot": {
                    "asAt": "2026-02-15T00:00:00+00:00",
                    "creditInPence": 19059,
                    "debtInPence": 0,
                }
            }
        }
    )

    mock_client.post.side_effect = [
        mock_accounts_response,
        mock_smart_devices_response,
        mock_device_balance_response,
    ]

    client = EONNextClient("test@example.com", "password123")
    client._logged_in = True
    client._token = "jwt-token"
    client._account_number = "A-736729C3"

    balance = client.get_balance()

    assert balance["balance"] == "190.59"
    assert balance["currency"] == "GBP"
    assert balance["account_number"] == "A-736729C3"
    assert mock_client.post.call_count == 3
    client.close()


@patch("eon_next.client.httpx.Client")
def test_get_tariff_day_night_active_agreement(mock_client_class: Mock) -> None:
    """Test tariff retrieval selects active day/night agreement data."""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    mock_tariff_response = Mock()
    mock_tariff_response.raise_for_status = Mock()
    mock_tariff_response.json = Mock(
        return_value={
            "data": {
                "account": {
                    "id": "1923278",
                    "number": "A-736729C3",
                    "properties": [
                        {
                            "id": "1849141",
                            "electricityMeterPoints": [
                                {
                                    "id": "1630709",
                                    "agreements": [
                                        {
                                            "validFrom": "2024-01-01",
                                            "validTo": "2024-12-31",
                                            "tariff": {
                                                "__typename": "DayNightTariff",
                                                "displayName": "Old Tariff",
                                                "productCode": "OLD",
                                                "standingCharge": 41.2,
                                                "dayRate": 28.01,
                                                "nightRate": 13.11,
                                            },
                                        },
                                        {
                                            "validFrom": "2025-01-01",
                                            "validTo": None,
                                            "tariff": {
                                                "__typename": "DayNightTariff",
                                                "displayName": "Next Flex Smart PAYG",
                                                "productCode": "E-2R-FLEX-SMART-PAYG",
                                                "standingCharge": 49.56,
                                                "dayRate": 31.09,
                                                "nightRate": 16.42,
                                            },
                                        },
                                    ],
                                }
                            ],
                        }
                    ],
                }
            }
        }
    )

    mock_client.post.return_value = mock_tariff_response

    client = EONNextClient("test@example.com", "password123")
    client._logged_in = True
    client._token = "jwt-token"
    client._account_number = "A-736729C3"

    tariff = client.get_tariff()

    assert tariff["tariff_name"] == "Next Flex Smart PAYG"
    assert tariff["unit_rate"] == "day: 31.09, night: 16.42"
    assert tariff["standing_charge"] == "49.56"
    assert tariff["day_rate"] == "31.09"
    assert tariff["night_rate"] == "16.42"
    assert tariff["product_code"] == "E-2R-FLEX-SMART-PAYG"
    assert tariff["account_number"] == "A-736729C3"
    client.close()


@patch("eon_next.client.httpx.Client")
def test_get_tariff_primes_account_number_when_missing(mock_client_class: Mock) -> None:
    """Test tariff retrieval resolves account number first when not already set."""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    mock_accounts_response = Mock()
    mock_accounts_response.raise_for_status = Mock()
    mock_accounts_response.json = Mock(
        return_value={
            "data": {
                "viewer": {
                    "accounts": [
                        {
                            "accountType": "DOMESTIC",
                            "balance": 0,
                            "id": "acc-id",
                            "number": "A-12345678",
                            "properties": [],
                        }
                    ],
                    "email": "test@example.com",
                    "id": "viewer-id",
                }
            }
        }
    )

    mock_tariff_response = Mock()
    mock_tariff_response.raise_for_status = Mock()
    mock_tariff_response.json = Mock(
        return_value={
            "data": {
                "account": {
                    "id": "1923278",
                    "number": "A-12345678",
                    "properties": [
                        {
                            "id": "1849141",
                            "electricityMeterPoints": [
                                {
                                    "id": "1630709",
                                    "agreements": [
                                        {
                                            "validFrom": "2025-01-01",
                                            "validTo": None,
                                            "tariff": {
                                                "__typename": "StandardTariff",
                                                "displayName": "Next Flex",
                                                "productCode": "E-1R-FLEX",
                                                "standingCharge": 48.12,
                                                "unitRate": 26.12,
                                            },
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            }
        }
    )

    mock_client.post.side_effect = [mock_accounts_response, mock_tariff_response]

    client = EONNextClient("test@example.com", "password123")
    client._logged_in = True
    client._token = "jwt-token"

    tariff = client.get_tariff()

    assert client._account_number == "A-12345678"
    assert tariff["tariff_name"] == "Next Flex"
    assert tariff["unit_rate"] == "26.12"
    assert tariff["standing_charge"] == "48.12"
    assert mock_client.post.call_count == 2
    client.close()


@patch("eon_next.client.httpx.Client")
def test_get_usage_from_meter_readings_history(mock_client_class: Mock) -> None:
    """Test usage derivation from cumulative electricity register readings."""
    mock_client = Mock()
    mock_client_class.return_value = mock_client

    meter_selector_response = Mock()
    meter_selector_response.raise_for_status = Mock()
    meter_selector_response.json = Mock(
        return_value={
            "data": {
                "properties": [
                    {
                        "electricityMeterPoints": [
                            {
                                "id": "1630709",
                                "meters": [{"id": "8269374"}],
                            }
                        ]
                    }
                ]
            }
        }
    )

    readings_history_response = Mock()
    readings_history_response.raise_for_status = Mock()
    readings_history_response.json = Mock(
        return_value={
            "data": {
                "readings": {
                    "edges": [
                        {
                            "node": {
                                "id": "r1",
                                "readAt": "2026-01-15T00:00:00+00:00",
                                "readingSource": "Smart reading",
                                "registers": [
                                    {
                                        "isQuarantined": False,
                                        "name": "Day",
                                        "value": "10000.00",
                                    },
                                    {
                                        "isQuarantined": False,
                                        "name": "Night",
                                        "value": "5000.00",
                                    },
                                ],
                                "source": "SMART_METER",
                            }
                        },
                        {
                            "node": {
                                "id": "r2",
                                "readAt": "2026-02-07T00:00:00+00:00",
                                "readingSource": "Smart reading",
                                "registers": [
                                    {
                                        "isQuarantined": False,
                                        "name": "Day",
                                        "value": "10150.00",
                                    },
                                    {
                                        "isQuarantined": False,
                                        "name": "Night",
                                        "value": "5100.00",
                                    },
                                ],
                                "source": "SMART_METER",
                            }
                        },
                        {
                            "node": {
                                "id": "r3",
                                "readAt": "2026-02-13T00:00:00+00:00",
                                "readingSource": "Smart reading",
                                "registers": [
                                    {
                                        "isQuarantined": False,
                                        "name": "Day",
                                        "value": "10170.00",
                                    },
                                    {
                                        "isQuarantined": False,
                                        "name": "Night",
                                        "value": "5110.00",
                                    },
                                ],
                                "source": "SMART_METER",
                            }
                        },
                        {
                            "node": {
                                "id": "r4",
                                "readAt": "2026-02-14T00:00:00+00:00",
                                "readingSource": "Smart reading",
                                "registers": [
                                    {
                                        "isQuarantined": False,
                                        "name": "Day",
                                        "value": "10176.00",
                                    },
                                    {
                                        "isQuarantined": False,
                                        "name": "Night",
                                        "value": "5114.00",
                                    },
                                ],
                                "source": "SMART_METER",
                            }
                        },
                    ],
                    "pageInfo": {
                        "endCursor": None,
                        "hasNextPage": False,
                    },
                }
            }
        }
    )

    mock_client.post.side_effect = [meter_selector_response, readings_history_response]

    client = EONNextClient("test@example.com", "password123")
    client._logged_in = True
    client._token = "jwt-token"
    client._account_number = "A-736729C3"

    usage = client.get_usage()

    assert usage["daily_usage"] == "10.00 kWh"
    assert usage["weekly_usage"] == "40.00 kWh"
    assert usage["monthly_usage"] == "290.00 kWh"
    assert mock_client.post.call_count == 2
    client.close()
