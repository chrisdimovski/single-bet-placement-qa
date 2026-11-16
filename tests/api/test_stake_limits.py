from decimal import Decimal

import requests

from tests.support.api import BettingApi


def test_maximum_stake_boundary(api: BettingApi, sandbox_balance: Decimal, match: dict) -> None:
    """Check both sides of the cap: rejection preserves funds and the valid maximum works."""
    assert sandbox_balance >= Decimal("100.01"), "The stake-cap check needs at least EUR 100.01 after setup."

    rejected = api.place_bet(match["id"], Decimal("100.01"))
    # Preserve placement evidence even if the following balance request also fails.
    errors = []
    if rejected.status_code != 422:
        errors.append(f"Over-limit placement: expected 422; {api.describe(rejected)}")
    try:
        payload = rejected.json()
        if not isinstance(payload, dict) or payload.get("error") != "invalid_stake_max":
            errors.append(f"Expected invalid_stake_max; {api.describe(rejected)}")
    except ValueError:
        errors.append(f"Over-limit response was not JSON; {api.describe(rejected)}")
    try:
        closing_balance = api.get_balance()
        if closing_balance != sandbox_balance:
            errors.append(f"Rejected bet changed balance: before={sandbox_balance}, after={closing_balance}")
    except (requests.RequestException, AssertionError, ValueError, KeyError, TypeError) as exc:
        errors.append(
            f"Balance readback failed; expected {sandbox_balance} EUR; {api.failure_details(exc)}; "
            f"placement evidence: {api.describe(rejected)}"
        )
    assert not errors, "\n".join(errors)

    # A reject-everything implementation must not pass this boundary scenario.
    stake = Decimal("100.00")
    accepted = api.place_bet(match["id"], stake)
    errors = []
    if accepted.status_code != 200:
        errors.append(f"Maximum valid stake: expected 200; {api.describe(accepted)}")
    else:
        try:
            result = accepted.json(parse_float=Decimal)
            expected = {
                "matchId": match["id"], "selection": "HOME", "stake": stake,
                "odds": match["odds"]["home"],
                "payout": stake * Decimal(str(match["odds"]["home"])),
                "balance": sandbox_balance - stake, "currency": "EUR",
            }
            for field, value in expected.items():
                if result.get(field) != value:
                    errors.append(f"Accepted bet {field}: expected {value!r}, got {result.get(field)!r}")
        except (ValueError, AttributeError) as exc:
            errors.append(f"Invalid success payload ({type(exc).__name__}); {api.describe(accepted)}")
    try:
        closing_balance = api.get_balance()
        if closing_balance != sandbox_balance - stake:
            errors.append(f"Valid maximum debit: expected {sandbox_balance - stake}, got {closing_balance}")
    except (requests.RequestException, AssertionError, ValueError, KeyError, TypeError) as exc:
        errors.append(
            f"Balance readback failed; expected {sandbox_balance - stake} EUR; {api.failure_details(exc)}; "
            f"placement evidence: {api.describe(accepted)}"
        )
    assert not errors, "\n".join(errors)
