from decimal import Decimal
from urllib.parse import quote

import requests

# Connect and read-inactivity limits, not a total request deadline.
HTTP_TIMEOUT = (5, 15)


class PlacementOutcomeUnknown(RuntimeError):
    """A transport failure cannot establish whether a placement was accepted."""


class BettingApi:
    """Sandbox operations; placement requests are deliberately never retried."""

    def __init__(self, session: requests.Session, base_url: str) -> None:
        self.session = session
        self.base_url = base_url

    def get_balance(self) -> Decimal:
        response = self.session.get(f"{self.base_url}/api/balance", timeout=HTTP_TIMEOUT)
        evidence = self.describe(response)
        assert response.status_code == 200, evidence
        try:
            payload = response.json(parse_float=Decimal)
        except ValueError as exc:
            raise ValueError(f"Balance response is not valid JSON; {evidence}") from exc
        assert isinstance(payload, dict), f"Balance response must be an object; {evidence}"
        assert payload.get("currency") == "EUR", (
            f"Unexpected balance currency: {payload.get('currency')!r}; {evidence}"
        )
        value = payload.get("balance")
        assert type(value) in (int, Decimal), f"Balance must be numeric, got {value!r}; {evidence}"
        balance = Decimal(value)
        assert balance.is_finite() and balance >= 0, f"Invalid balance: {balance} EUR; {evidence}"
        return balance

    def get_matches(self) -> list[dict]:
        response = self.session.get(f"{self.base_url}/api/matches", timeout=HTTP_TIMEOUT)
        assert response.status_code == 200, self.describe(response)
        matches = response.json(parse_float=Decimal)
        assert isinstance(matches, list) and matches, "The sandbox match catalogue is empty or invalid."
        return matches

    def balance_diagnostic(self) -> str:
        """Inspect an uncertain placement without ever resubmitting it."""
        try:
            return f"Persisted balance after attempt: {self.get_balance()} EUR."
        except (requests.RequestException, AssertionError, ValueError, KeyError, TypeError) as exc:
            return f"Persisted balance could not be read: {self.failure_details(exc)}"

    def place_bet(self, match_id: str, stake: Decimal) -> requests.Response:
        try:
            return self.session.post(
                f"{self.base_url}/api/place-bet",
                json={"matchId": match_id, "selection": "HOME", "stake": float(stake)},
                timeout=HTTP_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise PlacementOutcomeUnknown(
                f"Placement outcome unknown for stake {stake:.2f} EUR. {self.failure_details(exc)}. "
                f"{self.balance_diagnostic()} No placement retry was attempted; inspect the attempt "
                "before another submission. A balance snapshot alone does not establish the final outcome."
            ) from None

    def reset_balance(self) -> requests.Response:
        return self.session.post(f"{self.base_url}/api/reset-balance", timeout=HTTP_TIMEOUT)

    def describe(self, response: requests.Response) -> str:
        """Keep placement evidence in diagnostics without echoing the account ID."""
        return f"HTTP {response.status_code}: {self.redact(response.text)[:1500]}"

    def redact(self, value: str) -> str:
        user_id = self.session.headers.get("x-user-id")
        if user_id:
            for token in {user_id, quote(user_id, safe="")}:
                value = value.replace(token, "<redacted>")
        return value

    def failure_details(self, exc: Exception) -> str:
        """Preserve the reason and response for a failed read, with account IDs redacted."""
        message = self.redact(str(exc))
        response = getattr(exc, "response", None)
        if response is not None:
            message = f"{message}; {self.describe(response)}"
        return f"{type(exc).__name__}: {message[:2500]}"
