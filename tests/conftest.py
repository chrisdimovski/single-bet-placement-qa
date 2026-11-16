import os
import warnings
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode, urlsplit

import pytest
import requests

from tests.support.api import BettingApi
from tests.support.matches import select_upcoming_match


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--no-reset-balance", action="store_true",
        help="Use the existing sandbox balance instead of resetting before each test.",
    )


def pytest_configure(config) -> None:
    if config.getoption("numprocesses", default=0):
        raise pytest.UsageError("These tests share one sandbox wallet. Run sequentially without -n.")
    reruns = config.getoption("reruns", default=None)
    if reruns is None:
        reruns = config.getini("reruns") or 0
    if int(reruns) > 0:
        raise pytest.UsageError(
            "Do not automatically rerun money-moving tests. Inspect the balance before a deliberate rerun."
        )
    if int(config.getoption("force_reruns", default=None) or 0) > 0:
        raise pytest.UsageError("--force-reruns cannot be used with shared-wallet placement tests.")


def pytest_collection_modifyitems(items) -> None:
    for item in items:
        marker = item.get_closest_marker("flaky")
        if marker is None:
            continue
        # Match pytest-rerunfailures' keyword, positional and default marker forms.
        count = marker.kwargs.get("reruns", marker.args[0] if marker.args else 1)
        try:
            enabled = int(count) > 0
        except (TypeError, ValueError):
            raise pytest.UsageError(f"Invalid flaky rerun count on {item.nodeid}.") from None
        if enabled:
            raise pytest.UsageError(
                f"Automatic flaky-marker reruns are blocked for {item.nodeid}; inspect funds before rerunning."
            )


@pytest.fixture
def base_url() -> str:
    value = os.getenv("BETTING_BASE_URL", "https://qae-assignment-tau.vercel.app").strip().rstrip("/")
    parts = urlsplit(value)
    if (
        parts.scheme not in {"http", "https"} or not parts.netloc
        or parts.query or parts.fragment or parts.username or parts.password
    ):
        pytest.fail("BETTING_BASE_URL must be an HTTP(S) URL without credentials, query or fragment.")
    return value


@pytest.fixture
def user_id() -> str:
    value = os.getenv("BETTING_USER_ID", "").strip()
    if not value:
        pytest.fail("Set BETTING_USER_ID to your assigned candidate ID.")
    return value


@pytest.fixture
def app_url(base_url: str, user_id: str) -> str:
    query = urlencode({"user-id": user_id})
    return f"{base_url}/?{query}"


@pytest.fixture
def api_session(user_id: str) -> Iterator[requests.Session]:
    with requests.Session() as session:
        session.headers.update({"x-user-id": user_id, "Accept": "application/json"})
        yield session


@pytest.fixture
def api(api_session: requests.Session, base_url: str) -> BettingApi:
    return BettingApi(api_session, base_url)


@pytest.fixture
def sandbox_balance(api: BettingApi, match: dict, request) -> Decimal:
    """Reset before each scenario; read persisted funds instead of trusting reset copy."""
    # The match dependency validates data before any reset or placement POST.
    if request.config.getoption("no_reset_balance"):
        return api.get_balance()
    reset = api.reset_balance()
    assert reset.status_code == 200, api.describe(reset)
    payload = reset.json(parse_float=Decimal)
    assert payload["currency"] == "EUR", "Reset must return EUR."
    persisted = api.get_balance()
    if payload["balance"] != persisted:
        warnings.warn(
            f"Reset contract mismatch (BUG-04): response balance={payload['balance']}, "
            f"persisted balance={persisted}. Using the persisted baseline.",
            pytest.PytestWarning,
            stacklevel=2,
        )
    return persisted


@pytest.fixture
def match(api: BettingApi) -> dict:
    """Share future-date eligibility across both scenarios, including explicit overrides."""
    try:
        return select_upcoming_match(
            api.get_matches(), reference_date=date.today(),
            match_id=os.getenv("BETTING_MATCH_ID", "").strip(),
        )
    except ValueError as exc:
        pytest.fail(f"Test-data setup blocked: {api.redact(str(exc))}", pytrace=False)
