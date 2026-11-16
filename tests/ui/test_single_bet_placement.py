from decimal import Decimal

import pytest
import requests
from selenium.common.exceptions import WebDriverException
from seleniumbase import BaseCase

from tests.support.api import BettingApi
from tests.support.receipts import valid_bet_id, valid_receipt_timestamp

from .pages.betting import BettingPage, BetSlip, MatchOffer, WalletState


def test_single_bet_receipt_and_balance(
    sb: BaseCase, app_url: str, api: BettingApi, sandbox_balance: Decimal, match: dict
) -> None:
    """One UI placement reconciles the catalogue, slip, receipt and persisted/visible funds."""
    stake = Decimal("10.00")
    assert sandbox_balance >= stake, "The sandbox balance must cover the EUR 10.00 stake."
    betting = BettingPage(sb)
    betting.open(app_url)
    starting_wallet = WalletState(f"€{sandbox_balance:.2f}", f"€{sandbox_balance:.2f}", "0")
    opening_wallet = betting.wait_for_wallet_state(starting_wallet)
    assert opening_wallet == starting_wallet, f"Opening UI/API balances disagree: {opening_wallet!r}"

    expected_offer = MatchOffer(
        match=f"{match['homeTeam']} vs {match['awayTeam']}", odds=Decimal(str(match["odds"]["home"]))
    )
    offer = betting.select_home_win(match["id"])
    assert offer == expected_offer, f"Match card disagrees with the API catalogue: {offer!r}"
    betting.enter_stake(stake)
    expected_slip = BetSlip(
        match=offer.match, market="Match Winner: Home", odds=f"Odds: {offer.odds:.2f}",
        stake=f"€{stake:.2f}", payout=f"€{stake * offer.odds:.2f}",
    )
    observed_slip = betting.wait_for_slip(expected_slip)
    assert observed_slip == expected_slip, f"Slip did not reach {expected_slip!r}; last observed: {observed_slip!r}"

    started = betting.local_time()
    try:
        dialog = betting.place_bet()
    except WebDriverException as exc:
        pytest.fail(
            f"Placement outcome unavailable ({type(exc).__name__}). {api.balance_diagnostic()} "
            "Inspect the attempt before retrying.",
            pytrace=False,
        )
    finished = betting.local_time()
    assert dialog.is_success, (
        f"Expected a success receipt, saw {dialog.text!r}. {api.balance_diagnostic()} "
        "Inspect the attempt before retrying."
    )
    errors = []
    try:
        receipt = dialog.read_receipt()
    except WebDriverException as exc:
        errors.append(f"Receipt could not be inspected: {api.failure_details(exc)}")
    else:
        checks = {
            "Receipt match": (receipt.match, expected_slip.match),
            "Receipt selection": (receipt.selection, "Home"),
            "Receipt stake": (receipt.stake, expected_slip.stake),
            "Receipt odds": (receipt.odds, f"{offer.odds:.2f}"),
            "Receipt payout": (receipt.payout, expected_slip.payout),
        }
        errors.extend(
            f"{label}: expected {expected!r}, got {actual!r}"
            for label, (actual, expected) in checks.items() if actual != expected
        )
        if not valid_bet_id(receipt.bet_id):
            errors.append(f"Receipt bet ID is missing, malformed or a placeholder: {receipt.bet_id!r}")
        if not valid_receipt_timestamp(receipt.placed_at, started, finished):
            errors.append(
                f"Receipt timestamp {receipt.placed_at!r} is invalid or outside placement window {started} to {finished}"
            )

    expected_balance = sandbox_balance - stake
    # Read funds before dismissing the modal so a close failure cannot hide the debit evidence.
    try:
        persisted = api.get_balance()
        if persisted != expected_balance:
            errors.append(f"Persisted balance: expected {expected_balance}, got {persisted}")
    except (requests.RequestException, AssertionError, ValueError, KeyError, TypeError) as exc:
        errors.append(
            f"Persisted balance could not be verified; expected {expected_balance} EUR; {api.failure_details(exc)}"
        )

    try:
        dialog.close_receipt()
    except WebDriverException as exc:
        errors.append(f"Receipt dismissal failed ({type(exc).__name__})")
    expected_wallet = WalletState(f"€{expected_balance:.2f}", f"€{expected_balance:.2f}", "0")
    try:
        wallet = betting.wait_for_wallet_state(expected_wallet)
        if wallet != expected_wallet:
            errors.append(f"Wallet after close: expected {expected_wallet!r}, last observed {wallet!r}")
    except WebDriverException as exc:
        errors.append(f"Wallet could not be inspected ({type(exc).__name__})")
    assert not errors, "\n".join(errors)
