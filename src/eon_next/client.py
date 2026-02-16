"""EON Next API Client for retrieving account information."""

import base64
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx


class EONNextClient:
    """Client for interacting with the EON Next website."""

    BASE_URL = "https://www.eonnext.com"
    LOGIN_URL = f"{BASE_URL}/dashboard/sign-in"
    ACCOUNT_URL = f"{BASE_URL}/dashboard"
    GRAPHQL_URL = "https://api.eonnext-kraken.energy/v1/graphql/"

    LOGIN_MUTATION = """
    mutation loginEmailAuthentication($input: ObtainJSONWebTokenInput!) {
      obtainKrakenToken(input: $input) {
        payload
        refreshExpiresIn
        refreshToken
        token
      }
    }
    """

    GET_USER_ACCOUNTS_QUERY = """
    query getUserAccounts {
      viewer {
        accounts {
          ... on AccountType {
            accountType
            balance
            id
            number
            properties {
              address
              id
            }
          }
        }
        email
        id
      }
    }
    """

    SMART_DEVICES_FOR_ACCOUNT_QUERY = """
        query smartDevicesForAccount($account: String!) {
            account(accountNumber: $account) {
                id
                properties {
                    electricityMeterPoints {
                        id
                        meters {
                            id
                            smartDevices {
                                deviceId
                                weeklyDebtRecoveryRateInPence
                            }
                        }
                        mpan
                        targetSsd
                    }
                    gasMeterPoints {
                        id
                        meters {
                            id
                            smartDevices {
                                deviceId
                                weeklyDebtRecoveryRateInPence
                            }
                        }
                        mprn
                        targetSsd
                    }
                    id
                }
            }
        }
        """

    BALANCE_FOR_DEVICE_QUERY = """
        query balanceForDevice($deviceId: String!) {
            prepayBalanceSnapshot(deviceId: $deviceId) {
                asAt
                creditInPence
                debtInPence
            }
        }
        """

    TARIFFS_QUERY = """
        query tariffs($accountNumber: String!) {
            account(accountNumber: $accountNumber) {
                id
                properties {
                    electricityMeterPoints {
                        agreements {
                            id
                            validFrom
                            validTo
                            tariff {
                                __typename
                                ... on TariffType {
                                    displayName
                                    id
                                    preVatStandingCharge
                                    productCode
                                    standingCharge
                                    __typename
                                }
                                ... on StandardTariff {
                                    preVatUnitRate
                                    unitRate
                                    __typename
                                }
                                ... on PrepayTariff {
                                    preVatUnitRate
                                    unitRate
                                    __typename
                                }
                                ... on DayNightTariff {
                                    dayRate
                                    nightRate
                                    preVatDayRate
                                    preVatNightRate
                                    __typename
                                }
                                ... on HalfHourlyTariff {
                                    unitRates {
                                        validFrom
                                        validTo
                                        value
                                        __typename
                                    }
                                    __typename
                                }
                                ... on ThreeRateTariff {
                                    dayRate
                                    nightRate
                                    offPeakRate
                                    preVatDayRate
                                    preVatNightRate
                                    preVatOffPeakRate
                                    __typename
                                }
                            }
                        }
                    }
                }
            }
        }
        """

    ACCOUNT_METER_SELECTOR_QUERY = """
        query getAccountMeterSelector($accountNumber: String!, $showInactive: Boolean!) {
            properties(accountNumber: $accountNumber) {
                electricityMeterPoints {
                    id
                    meters(includeInactive: $showInactive) {
                        id
                    }
                }
            }
        }
        """

    METER_READINGS_HISTORY_ELECTRICITY_QUERY = """
        query meterReadingsHistoryTableElectricityReadings(
            $accountNumber: String!
            $cursor: String
            $meterId: String!
        ) {
            readings: electricityMeterReadings(
                accountNumber: $accountNumber
                after: $cursor
                first: 12
                meterId: $meterId
            ) {
                edges {
                    node {
                        id
                        readAt
                        readingSource
                        registers {
                            isQuarantined
                            name
                            value
                            __typename
                        }
                        source
                        __typename
                    }
                    __typename
                }
                pageInfo {
                    endCursor
                    hasNextPage
                    __typename
                }
                __typename
            }
        }
        """

    TOKEN_CACHE_BUFFER_SECONDS = 30

    def __init__(self, username: str, password: str, *, use_cache: bool = True) -> None:
        """Initialize the EON Next client.

        Args:
            username: The user's email address.
            password: The user's password.
            use_cache: Whether to use local token cache between runs.
        """
        self.username = username
        self.password = password
        self._use_cache = use_cache
        self.client = httpx.Client(follow_redirects=True, timeout=30.0)
        self._logged_in = False
        self._token: str | None = None
        self._account_number: str | None = None
        self._cache_path = Path.home() / ".eon-next" / "auth_cache.json"

    def __enter__(self) -> "EONNextClient":
        """Context manager entry."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context manager exit."""
        self.close()

    def close(self) -> None:
        """Close the HTTP client."""
        self.client.close()

    def _cache_key(self) -> str:
        """Get a stable cache key for this user."""
        return self.username.strip().lower()

    def _get_token_expiry(self, token: str) -> int | None:
        """Extract JWT exp claim without signature validation.

        Returns:
            Unix timestamp (seconds) or None if unavailable.
        """
        parts = token.split(".")
        if len(parts) < 2:
            return None

        payload = parts[1]
        padding = "=" * (-len(payload) % 4)
        try:
            decoded = base64.urlsafe_b64decode(payload + padding).decode("utf-8")
            payload_json = json.loads(decoded)
        except Exception:
            return None

        exp = payload_json.get("exp")
        if isinstance(exp, int):
            return exp
        return None

    def _load_cached_auth(self) -> tuple[str, str | None] | None:
        """Load cached auth token and account number for this user if valid."""
        if not self._cache_path.exists():
            return None

        try:
            cache_data = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except Exception:
            return None

        if not isinstance(cache_data, dict):
            return None

        users = cache_data.get("users")
        if not isinstance(users, dict):
            return None

        entry = users.get(self._cache_key())
        if not isinstance(entry, dict):
            return None

        token = entry.get("token")
        expires_at = entry.get("expires_at")
        if not isinstance(token, str) or not token:
            return None
        if not isinstance(expires_at, int):
            return None

        now = int(time.time())
        if expires_at <= now + self.TOKEN_CACHE_BUFFER_SECONDS:
            return None

        account_number = entry.get("account_number")
        if not isinstance(account_number, str):
            account_number = None

        return token, account_number

    def _save_cached_auth(self, token: str, account_number: str | None) -> None:
        """Persist auth token cache for this user.

        Only caches tokens that include a valid expiry claim.
        """
        expires_at = self._get_token_expiry(token)
        if expires_at is None:
            return

        cache_data: dict[str, Any] = {"users": {}}
        if self._cache_path.exists():
            try:
                loaded = json.loads(self._cache_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    cache_data = loaded
            except Exception:
                pass

        users = cache_data.get("users")
        if not isinstance(users, dict):
            users = {}
            cache_data["users"] = users

        users[self._cache_key()] = {
            "token": token,
            "account_number": account_number,
            "expires_at": expires_at,
        }

        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

    def _clear_cached_auth(self) -> None:
        """Remove cached auth entry for this user."""
        if not self._cache_path.exists():
            return

        try:
            cache_data = json.loads(self._cache_path.read_text(encoding="utf-8"))
        except Exception:
            return

        if not isinstance(cache_data, dict):
            return

        users = cache_data.get("users")
        if not isinstance(users, dict):
            return

        users.pop(self._cache_key(), None)
        self._cache_path.write_text(json.dumps(cache_data), encoding="utf-8")

    def clear_cached_auth(self) -> None:
        """Public wrapper to clear cached auth for this user."""
        self._clear_cached_auth()

    def _graphql_request(
        self,
        operation_name: str,
        query: str,
        variables: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a GraphQL request against the EON Next API.

        Args:
            operation_name: GraphQL operation name.
            query: GraphQL query or mutation text.
            variables: GraphQL variables payload.

        Returns:
            The GraphQL data object.

        Raises:
            RuntimeError: If the API returns GraphQL errors or malformed data.
        """
        headers = {
            "content-type": "application/json",
            "Origin": self.BASE_URL,
            "Referer": f"{self.BASE_URL}/",
        }
        if self._token:
            headers["authorization"] = self._token

        response = self.client.post(
            self.GRAPHQL_URL,
            json={
                "operationName": operation_name,
                "variables": variables,
                "query": query,
            },
            headers=headers,
        )

        payload: Any
        try:
            payload = response.json()
        except Exception:
            payload = None

        if response.is_error:
            if isinstance(payload, dict):
                errors = payload.get("errors")
                if errors:
                    raise RuntimeError(
                        f"GraphQL request failed ({response.status_code}): {errors}"
                    )
            response.raise_for_status()

        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected response format from GraphQL API")

        errors = payload.get("errors")
        if errors:
            raise RuntimeError(f"GraphQL request failed: {errors}")

        data = payload.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("GraphQL response did not include data")

        return data

    def login(self) -> None:
        """Log in to the EON Next website.

        Raises:
            RuntimeError: If login fails.
        """
        cached = self._load_cached_auth() if self._use_cache else None
        if cached:
            cached_token, cached_account_number = cached
            self._token = cached_token
            self._account_number = cached_account_number
            self.client.headers.update({"authorization": cached_token})

            try:
                accounts_data = self._graphql_request(
                    operation_name="getUserAccounts",
                    query=self.GET_USER_ACCOUNTS_QUERY,
                    variables={},
                )
                viewer = accounts_data.get("viewer")
                if isinstance(viewer, dict):
                    accounts = viewer.get("accounts")
                    if isinstance(accounts, list):
                        for account in accounts:
                            if isinstance(account, dict):
                                number = account.get("number")
                                if isinstance(number, str) and number:
                                    self._account_number = number
                                    break
                self._logged_in = True
                return
            except Exception:
                self._clear_cached_auth()
                self._token = None
                self.client.headers.pop("authorization", None)

        data = self._graphql_request(
            operation_name="loginEmailAuthentication",
            query=self.LOGIN_MUTATION,
            variables={"input": {"email": self.username, "password": self.password}},
        )

        token_data = data.get("obtainKrakenToken")
        if not isinstance(token_data, dict):
            raise RuntimeError("Login failed. Authentication payload was missing.")

        token = token_data.get("token")
        if not isinstance(token, str) or not token:
            raise RuntimeError("Login failed. Token not returned by API.")

        self._token = token
        self.client.headers.update({"authorization": token})
        self._logged_in = True

        # Prime account selection for subsequent API calls.
        accounts_data = self._graphql_request(
            operation_name="getUserAccounts",
            query=self.GET_USER_ACCOUNTS_QUERY,
            variables={},
        )
        viewer = accounts_data.get("viewer")
        if isinstance(viewer, dict):
            accounts = viewer.get("accounts")
            if isinstance(accounts, list):
                for account in accounts:
                    if isinstance(account, dict):
                        number = account.get("number")
                        if isinstance(number, str) and number:
                            self._account_number = number
                            break

        if self._use_cache:
            self._save_cached_auth(token=token, account_number=self._account_number)

    def get_balance(self) -> dict[str, Any]:
        """Get the current electricity credit balance.

        Returns:
            A dictionary containing balance information.

        Raises:
            RuntimeError: If not logged in or if balance retrieval fails.
        """
        if not self._logged_in:
            raise RuntimeError("Must login first")

        accounts_data = self._graphql_request(
            operation_name="getUserAccounts",
            query=self.GET_USER_ACCOUNTS_QUERY,
            variables={},
        )
        viewer = accounts_data.get("viewer")
        accounts = viewer.get("accounts") if isinstance(viewer, dict) else None

        if not isinstance(accounts, list) or not accounts:
            raise RuntimeError("No accounts were returned by the API")

        selected_account: dict[str, Any] | None = None
        if self._account_number:
            for account in accounts:
                if (
                    isinstance(account, dict)
                    and account.get("number") == self._account_number
                ):
                    selected_account = account
                    break

        if selected_account is None:
            first = accounts[0]
            if isinstance(first, dict):
                selected_account = first

        if selected_account is None:
            raise RuntimeError("Could not determine account data from API response")

        raw_balance = selected_account.get("balance")
        if raw_balance is None:
            raise RuntimeError("Balance field was missing from API response")

        account_number = selected_account.get("number")
        if isinstance(account_number, str) and account_number:
            self._account_number = account_number

        # For smart PAYG accounts, account.balance can be 0 while the live meter
        # credit is returned by prepayBalanceSnapshot(deviceId).
        try:
            account_balance_value = float(raw_balance)
        except (TypeError, ValueError):
            account_balance_value = None

        balance_to_return = raw_balance
        if self._account_number and account_balance_value == 0.0:
            smart_devices_data = self._graphql_request(
                operation_name="smartDevicesForAccount",
                query=self.SMART_DEVICES_FOR_ACCOUNT_QUERY,
                variables={"account": self._account_number},
            )

            account_obj = smart_devices_data.get("account")
            properties = account_obj.get("properties") if isinstance(account_obj, dict) else None
            device_id: str | None = None

            if isinstance(properties, list):
                for prop in properties:
                    if not isinstance(prop, dict):
                        continue
                    electricity_meter_points = prop.get("electricityMeterPoints")
                    if not isinstance(electricity_meter_points, list):
                        continue
                    for meter_point in electricity_meter_points:
                        if not isinstance(meter_point, dict):
                            continue
                        meters = meter_point.get("meters")
                        if not isinstance(meters, list):
                            continue
                        for meter in meters:
                            if not isinstance(meter, dict):
                                continue
                            smart_devices = meter.get("smartDevices")
                            if not isinstance(smart_devices, list):
                                continue
                            for smart_device in smart_devices:
                                if not isinstance(smart_device, dict):
                                    continue
                                maybe_device_id = smart_device.get("deviceId")
                                if isinstance(maybe_device_id, str) and maybe_device_id:
                                    device_id = maybe_device_id
                                    break
                            if device_id:
                                break
                        if device_id:
                            break
                    if device_id:
                        break

            if device_id:
                device_balance_data = self._graphql_request(
                    operation_name="balanceForDevice",
                    query=self.BALANCE_FOR_DEVICE_QUERY,
                    variables={"deviceId": device_id},
                )
                snapshot = device_balance_data.get("prepayBalanceSnapshot")
                if isinstance(snapshot, dict):
                    credit_in_pence = snapshot.get("creditInPence")
                    if isinstance(credit_in_pence, int):
                        balance_to_return = f"{credit_in_pence / 100:.2f}"

        return {
            "balance": str(balance_to_return),
            "currency": "GBP",
            "account_number": self._account_number,
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

        if not self._account_number:
            accounts_data = self._graphql_request(
                operation_name="getUserAccounts",
                query=self.GET_USER_ACCOUNTS_QUERY,
                variables={},
            )
            viewer = accounts_data.get("viewer")
            accounts = viewer.get("accounts") if isinstance(viewer, dict) else None
            if isinstance(accounts, list):
                for account in accounts:
                    if isinstance(account, dict):
                        number = account.get("number")
                        if isinstance(number, str) and number:
                            self._account_number = number
                            break

        if not self._account_number:
            raise RuntimeError("Could not determine account number for tariff lookup")

        tariff_data = self._graphql_request(
            operation_name="tariffs",
            query=self.TARIFFS_QUERY,
            variables={"accountNumber": self._account_number},
        )

        account_obj = tariff_data.get("account")
        if not isinstance(account_obj, dict):
            raise RuntimeError("Tariff lookup did not return account data")

        properties = account_obj.get("properties")
        if not isinstance(properties, list):
            raise RuntimeError("Tariff lookup did not include property data")

        selected_agreement: dict[str, Any] | None = None
        selected_tariff: dict[str, Any] | None = None

        def _agreement_score(agreement: dict[str, Any]) -> tuple[int, str]:
            valid_to = agreement.get("validTo")
            valid_from = agreement.get("validFrom")
            is_active = 1 if valid_to is None else 0
            valid_from_text = valid_from if isinstance(valid_from, str) else ""
            return is_active, valid_from_text

        for prop in properties:
            if not isinstance(prop, dict):
                continue
            electricity_meter_points = prop.get("electricityMeterPoints")
            if not isinstance(electricity_meter_points, list):
                continue

            for meter_point in electricity_meter_points:
                if not isinstance(meter_point, dict):
                    continue
                agreements = meter_point.get("agreements")
                if not isinstance(agreements, list) or not agreements:
                    continue

                for agreement in agreements:
                    if not isinstance(agreement, dict):
                        continue
                    tariff = agreement.get("tariff")
                    if not isinstance(tariff, dict):
                        continue

                    if selected_agreement is None:
                        selected_agreement = agreement
                        selected_tariff = tariff
                        continue

                    if _agreement_score(agreement) > _agreement_score(selected_agreement):
                        selected_agreement = agreement
                        selected_tariff = tariff

        if not isinstance(selected_tariff, dict):
            raise RuntimeError("No tariff agreement was found for this account")

        tariff_name = selected_tariff.get("displayName")
        product_code = selected_tariff.get("productCode")
        standing_charge = selected_tariff.get("standingCharge")
        unit_rate = selected_tariff.get("unitRate")
        day_rate = selected_tariff.get("dayRate")
        night_rate = selected_tariff.get("nightRate")

        def _format_rate(value: Any) -> str:
            if isinstance(value, int | float):
                return f"{value:.2f}"
            if isinstance(value, str):
                return value
            return "N/A"

        unit_rate_value = "N/A"
        if isinstance(unit_rate, int | float | str):
            unit_rate_value = _format_rate(unit_rate)
        elif isinstance(day_rate, int | float | str) and isinstance(
            night_rate,
            int | float | str,
        ):
            unit_rate_value = f"day: {_format_rate(day_rate)}, night: {_format_rate(night_rate)}"

        return {
            "tariff_name": tariff_name if isinstance(tariff_name, str) else "Unknown",
            "unit_rate": unit_rate_value,
            "standing_charge": _format_rate(standing_charge),
            "day_rate": _format_rate(day_rate),
            "night_rate": _format_rate(night_rate),
            "product_code": product_code if isinstance(product_code, str) else "N/A",
            "account_number": self._account_number,
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

        if not self._account_number:
            accounts_data = self._graphql_request(
                operation_name="getUserAccounts",
                query=self.GET_USER_ACCOUNTS_QUERY,
                variables={},
            )
            viewer = accounts_data.get("viewer")
            accounts = viewer.get("accounts") if isinstance(viewer, dict) else None
            if isinstance(accounts, list):
                for account in accounts:
                    if isinstance(account, dict):
                        number = account.get("number")
                        if isinstance(number, str) and number:
                            self._account_number = number
                            break

        if not self._account_number:
            raise RuntimeError("Could not determine account number for usage lookup")

        meter_selector_data = self._graphql_request(
            operation_name="getAccountMeterSelector",
            query=self.ACCOUNT_METER_SELECTOR_QUERY,
            variables={"accountNumber": self._account_number, "showInactive": False},
        )

        properties = meter_selector_data.get("properties")
        meter_id: str | None = None
        if isinstance(properties, list):
            for prop in properties:
                if not isinstance(prop, dict):
                    continue
                electricity_meter_points = prop.get("electricityMeterPoints")
                if not isinstance(electricity_meter_points, list):
                    continue
                for meter_point in electricity_meter_points:
                    if not isinstance(meter_point, dict):
                        continue
                    meters = meter_point.get("meters")
                    if not isinstance(meters, list):
                        continue
                    for meter in meters:
                        if not isinstance(meter, dict):
                            continue
                        maybe_meter_id = meter.get("id")
                        if isinstance(maybe_meter_id, str) and maybe_meter_id:
                            meter_id = maybe_meter_id
                            break
                    if meter_id:
                        break
                if meter_id:
                    break

        if not meter_id:
            return {
                "daily_usage": "N/A",
                "weekly_usage": "N/A",
                "monthly_usage": "N/A",
            }

        readings_series: list[tuple[datetime, float]] = []
        cursor: str | None = None

        for _ in range(8):
            history_data = self._graphql_request(
                operation_name="meterReadingsHistoryTableElectricityReadings",
                query=self.METER_READINGS_HISTORY_ELECTRICITY_QUERY,
                variables={
                    "accountNumber": self._account_number,
                    "cursor": cursor,
                    "meterId": meter_id,
                },
            )

            readings = history_data.get("readings")
            edges = readings.get("edges") if isinstance(readings, dict) else None
            if isinstance(edges, list):
                for edge in edges:
                    if not isinstance(edge, dict):
                        continue
                    node = edge.get("node")
                    if not isinstance(node, dict):
                        continue

                    read_at = node.get("readAt")
                    if not isinstance(read_at, str):
                        continue
                    try:
                        parsed_read_at = datetime.fromisoformat(
                            read_at.replace("Z", "+00:00")
                        )
                    except ValueError:
                        continue

                    registers = node.get("registers")
                    if not isinstance(registers, list):
                        continue

                    total_register_value = 0.0
                    saw_value = False
                    for register in registers:
                        if not isinstance(register, dict):
                            continue
                        if register.get("isQuarantined") is True:
                            continue
                        register_value = register.get("value")

                        parsed_value: float
                        try:
                            if isinstance(register_value, str | int | float):
                                parsed_value = float(register_value)
                            else:
                                continue
                        except (TypeError, ValueError):
                            continue

                        total_register_value += parsed_value
                        saw_value = True

                    if saw_value:
                        readings_series.append((parsed_read_at, total_register_value))

            page_info = readings.get("pageInfo") if isinstance(readings, dict) else None
            has_next_page = (
                page_info.get("hasNextPage") if isinstance(page_info, dict) else False
            )
            next_cursor = page_info.get("endCursor") if isinstance(page_info, dict) else None
            if has_next_page is True and isinstance(next_cursor, str) and next_cursor:
                cursor = next_cursor
            else:
                break

        if len(readings_series) < 2:
            return {
                "daily_usage": "N/A",
                "weekly_usage": "N/A",
                "monthly_usage": "N/A",
            }

        deduped: dict[datetime, float] = {}
        for timestamp, total_value in readings_series:
            current = deduped.get(timestamp)
            if current is None or total_value > current:
                deduped[timestamp] = total_value

        ordered = sorted(deduped.items(), key=lambda item: item[0])
        if len(ordered) < 2:
            return {
                "daily_usage": "N/A",
                "weekly_usage": "N/A",
                "monthly_usage": "N/A",
            }

        latest_timestamp, latest_value = ordered[-1]

        def _usage_for_days(days: int) -> str:
            cutoff = latest_timestamp - timedelta(days=days)
            baseline: tuple[datetime, float] | None = None
            for reading in ordered:
                if reading[0] <= cutoff:
                    baseline = reading
                else:
                    break

            if baseline is None:
                return "N/A"

            delta = latest_value - baseline[1]
            if delta < 0:
                return "N/A"

            return f"{delta:.2f} kWh"

        return {
            "daily_usage": _usage_for_days(1),
            "weekly_usage": _usage_for_days(7),
            "monthly_usage": _usage_for_days(30),
        }
