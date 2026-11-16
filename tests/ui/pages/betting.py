import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TypeVar

from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import WebDriverWait
from seleniumbase import BaseCase

Snapshot = TypeVar("Snapshot")


@dataclass(frozen=True)
class MatchOffer:
    match: str
    odds: Decimal


@dataclass(frozen=True)
class BetSlip:
    match: str
    market: str
    odds: str
    stake: str
    payout: str


@dataclass(frozen=True)
class ReceiptDetails:
    match: str
    selection: str | None
    odds: str
    stake: str
    payout: str
    bet_id: str
    placed_at: str


@dataclass(frozen=True)
class WalletState:
    header_balance: str | None
    slip_balance: str | None
    active_selections: str | None


class BettingPage:
    _STAKE_INPUT = "#bet-slip-stake-input"
    _PLACE_BET = "#bet-slip-place-bet"
    _HEADER_BALANCE = "#header-balance > span:last-child"
    _SLIP_BALANCE = "#bet-slip-balance"
    _SLIP_COUNT = "#bet-slip-count"

    def __init__(self, browser: BaseCase) -> None:
        self._browser = browser

    def open(self, url: str) -> None:
        self._browser.open(url)
        self._browser.wait_for_element_visible("#match-list", timeout=30)

    def select_home_win(self, match_id: str) -> MatchOffer:
        card = self._browser.wait_for_element_visible(f"match-card-{match_id}", by=By.ID)
        status = card.find_element(By.CSS_SELECTOR, ".badge").text
        assert status == "UPCOMING", f"Selected catalogue fixture is not UPCOMING in the UI: {status!r}"
        home, away = card.find_elements(By.CSS_SELECTOR, ".teamName")
        button = card.find_element(By.CSS_SELECTOR, "button[id$='-home']")
        odds = button.find_element(By.CSS_SELECTOR, ".oddsButtonValue")
        offer = MatchOffer(match=f"{home.text} vs {away.text}", odds=Decimal(odds.text))
        button_id = button.get_attribute("id")
        self._browser.wait_for_element_clickable(button_id, by=By.ID)
        self._browser.click(button_id, by=By.ID)
        return offer

    def enter_stake(self, stake: Decimal) -> None:
        self._browser.type(self._STAKE_INPUT, f"{stake:.2f}")

    def read_slip(self) -> BetSlip:
        # Read immediately; the surrounding poll owns the single timeout budget.
        def text(selector: str) -> str:
            return self._browser.driver.find_element(By.CSS_SELECTOR, selector).text.strip()

        return BetSlip(
            match=text("#bet-slip .betSelectionTeams"),
            market=text("#bet-slip .betSelectionMarket"),
            odds=text("#bet-slip .betSelectionOdds"),
            stake=text("#bet-slip-total-stake"),
            payout=text("#bet-slip-potential-payout"),
        )

    def _wait_for_snapshot(
        self, read: Callable[[], Snapshot], expected: Snapshot, *, timeout: float
    ) -> Snapshot | None:
        """Retain the last observation so a timeout produces useful assertion evidence."""
        observed = None

        def updated(_driver) -> bool:
            nonlocal observed
            try:
                observed = read()
            except (NoSuchElementException, StaleElementReferenceException):
                return False
            return observed == expected

        try:
            WebDriverWait(self._browser.driver, timeout, poll_frequency=0.2).until(updated)
        except TimeoutException:
            pass  # The caller asserts against the returned observation.
        return observed

    def wait_for_slip(self, expected: BetSlip, *, timeout: float = 5) -> BetSlip | None:
        return self._wait_for_snapshot(self.read_slip, expected, timeout=timeout)

    def place_bet(self) -> "PlacementDialog":
        self._browser.wait_for_element_clickable(self._PLACE_BET)
        self._browser.click(self._PLACE_BET)
        return PlacementDialog.wait_for(self._browser)

    def local_time(self) -> datetime:
        """The receipt uses the browser's local timezone and clock."""
        parts = self._browser.execute_script(
            "const d = new Date(); return [d.getFullYear(), d.getMonth()+1, "
            "d.getDate(), d.getHours(), d.getMinutes(), d.getSeconds()];"
        )
        return datetime(*parts)

    def _visible_text(self, selector: str) -> str | None:
        elements = self._browser.driver.find_elements(By.CSS_SELECTOR, selector)
        if elements and elements[0].is_displayed():
            return elements[0].text.removeprefix("Balance:").strip()
        return None

    def read_wallet(self) -> WalletState:
        return WalletState(
            header_balance=self._visible_text(self._HEADER_BALANCE),
            slip_balance=self._visible_text(self._SLIP_BALANCE),
            active_selections=self._visible_text(self._SLIP_COUNT),
        )

    def wait_for_wallet_state(self, expected: WalletState, *, timeout: float = 5) -> WalletState | None:
        return self._wait_for_snapshot(self.read_wallet, expected, timeout=timeout)


class PlacementDialog:
    _SUCCESS = "modal-success"
    _ERROR = "modal-error"

    def __init__(self, browser: BaseCase, element: WebElement) -> None:
        self._browser = browser
        self._element = element

    @classmethod
    def wait_for(cls, browser: BaseCase) -> "PlacementDialog":
        def visible_dialog(driver):
            for element in driver.find_elements(By.CSS_SELECTOR, f"#{cls._SUCCESS}, #{cls._ERROR}"):
                try:
                    if element.is_displayed():
                        return element
                except StaleElementReferenceException:
                    continue
            return False

        element = WebDriverWait(browser.driver, 25, poll_frequency=0.2).until(visible_dialog)
        return cls(browser, element)

    @property
    def is_success(self) -> bool:
        return self._element.get_attribute("id") == self._SUCCESS

    @property
    def text(self) -> str:
        return self._element.text

    def read_receipt(self) -> ReceiptDetails:
        def field(name: str) -> str:
            elements = self._element.find_elements(By.ID, f"{self._SUCCESS}-{name}")
            return elements[0].text.strip() if elements else ""

        selection = re.search(
            r"^(?:(?:Selection|Match Winner)[ \t]*:?[ \t\n]*)?(Home|Draw|Away)[ \t]*$",
            self.text,
            re.IGNORECASE | re.MULTILINE,
        )
        return ReceiptDetails(
            match=field("match"),
            selection=selection.group(1).title() if selection else None,
            odds=field("odds"), stake=field("stake"), payout=field("payout"),
            bet_id=field("bet-id"), placed_at=field("placed-at"),
        )

    def close_receipt(self) -> None:
        self._browser.click(f"#{self._SUCCESS}-close")
        self._browser.wait_for_element_not_visible(f"#{self._SUCCESS}")
