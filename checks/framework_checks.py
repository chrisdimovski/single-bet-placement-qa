import json
import os
import unittest
import warnings
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import quote
from unittest.mock import Mock, patch

import requests
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

from tests import conftest
from tests.api.test_stake_limits import test_maximum_stake_boundary
from tests.support.api import BettingApi, PlacementOutcomeUnknown
from tests.support.matches import select_upcoming_match
from tests.support.receipts import valid_bet_id, valid_receipt_timestamp
from tests.ui import test_single_bet_placement as ui
from tests.ui.pages.betting import BettingPage, BetSlip, MatchOffer, ReceiptDetails, WalletState

MATCH = {
    'id': 'sample', 'homeTeam': 'A', 'awayTeam': 'B',
    'kickoffDate': '2026-11-14', 'odds': {'home': Decimal('2.20')},
}
START = datetime(2026, 11, 14, 12, 0, 1)
END = datetime(2026, 11, 14, 12, 0, 5)


def response(status, payload):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(payload).encode()
    return result


def success_payload(currency='EUR'):
    return {
        'matchId': 'sample', 'selection': 'HOME', 'stake': 100,
        'odds': 2.2, 'payout': 220, 'balance': 20, 'currency': currency,
    }


def fake_api(responses, balances):
    api = Mock(spec=BettingApi)
    api.place_bet.side_effect = responses
    api.get_balance.side_effect = balances
    api.describe.side_effect = lambda result: f'HTTP {result.status_code}: {result.text}'
    api.failure_details.side_effect = lambda exc: f'{type(exc).__name__}: {exc}'
    return api


class FrameworkChecks(unittest.TestCase):
    def test_api_boundary_accepts_correct_implementation(self):
        api = fake_api(
            [response(422, {'error': 'invalid_stake_max'}), response(200, success_payload())],
            [Decimal('120'), Decimal('20')],
        )
        test_maximum_stake_boundary(api, Decimal('120'), MATCH)
        self.assertEqual(api.place_bet.call_count, 2)

    def test_api_boundary_reject_everything_cannot_pass(self):
        api = fake_api(
            [response(422, {'error': 'invalid_stake_max'}), response(422, {'error': 'invalid_stake_max'})],
            [Decimal('120'), Decimal('120')],
        )
        with self.assertRaisesRegex(AssertionError, 'Maximum valid stake'):
            test_maximum_stake_boundary(api, Decimal('120'), MATCH)

    def test_api_response_evidence_survives_balance_failure(self):
        api = fake_api([response(201, {'error': 'unexpected'})], [requests.ConnectionError('offline')])
        with self.assertRaises(AssertionError) as caught:
            test_maximum_stake_boundary(api, Decimal('120'), MATCH)
        self.assertIn('201', str(caught.exception))
        self.assertIn('Balance readback failed', str(caught.exception))
        self.assertEqual(api.place_bet.call_count, 1)

    def test_api_detects_wrong_success_currency(self):
        api = fake_api(
            [response(422, {'error': 'invalid_stake_max'}), response(200, success_payload('USD'))],
            [Decimal('120'), Decimal('20')],
        )
        with self.assertRaisesRegex(AssertionError, 'currency'):
            test_maximum_stake_boundary(api, Decimal('120'), MATCH)

    def run_ui(
        self, persisted='110', bet_id='#B-12345', timestamp='Today, 12:00 PM',
        close_error=False, balance_error=None, receipt_error=None,
    ):
        api = Mock(spec=BettingApi)
        api.get_balance.return_value = Decimal(persisted)
        if balance_error:
            api.get_balance.side_effect = balance_error
        api.failure_details.side_effect = lambda exc: f'{type(exc).__name__}: {exc}'
        page = Mock()
        page.wait_for_wallet_state.side_effect = [
            WalletState('\u20ac120.00', '\u20ac120.00', '0'), WalletState('\u20ac110.00', '\u20ac110.00', '0'),
        ]
        page.select_home_win.return_value = MatchOffer('A vs B', Decimal('2.20'))
        page.wait_for_slip.return_value = BetSlip(
            'A vs B', 'Match Winner: Home', 'Odds: 2.20', '\u20ac10.00', '\u20ac22.00',
        )
        page.local_time.side_effect = [START, END]
        dialog = page.place_bet.return_value
        dialog.is_success = True
        dialog.read_receipt.return_value = ReceiptDetails(
            'A vs B', 'Home', '2.20', '\u20ac10.00', '\u20ac22.00', bet_id, timestamp,
        )
        if receipt_error is not None:
            dialog.read_receipt.side_effect = receipt_error
        if close_error:
            dialog.close_receipt.side_effect = TimeoutException('close failed')
        self.ui_api, self.ui_dialog, self.ui_page = api, dialog, page
        with patch.object(ui, 'BettingPage', return_value=page):
            ui.test_single_bet_receipt_and_balance(object(), 'https://local.invalid', api, Decimal('120'), MATCH)

    def test_ui_correct_implementation_passes(self):
        self.run_ui()

    def test_ui_detects_backend_no_debit_even_if_ui_is_correct(self):
        with self.assertRaisesRegex(AssertionError, 'Persisted balance'):
            self.run_ui(persisted='120')

    def test_ui_detects_placeholder_id_and_garbage_timestamp(self):
        with self.assertRaises(AssertionError) as caught:
            self.run_ui(bet_id='-', timestamp='not a timestamp')
        self.assertIn('bet ID', str(caught.exception))
        self.assertIn('timestamp', str(caught.exception))

    def test_receipt_ids_allow_unspecified_formats_and_reject_placeholders(self):
        for identifier in ['#B-12345', 'bet.123', 'bet/123', 'urn:bet:123']:
            with self.subTest(identifier=identifier):
                self.assertTrue(valid_bet_id(identifier))
                self.run_ui(bet_id=identifier)
        for identifier in ['', '   ', '-', '#', '...', 'N/A', ' undefined ', 'pending', None]:
            with self.subTest(identifier=identifier):
                self.assertFalse(valid_bet_id(identifier))

    def test_close_failure_does_not_hide_backend_failure(self):
        with self.assertRaises(AssertionError) as caught:
            self.run_ui(persisted='120', close_error=True)
        self.assertIn('Persisted balance', str(caught.exception))
        self.assertIn('dismissal failed', str(caught.exception))

    def test_snapshot_wait_handles_stale_element_and_preserves_last_value(self):
        browser = Mock()
        page = BettingPage(browser)
        read = Mock(side_effect=[StaleElementReferenceException(), 'old', 'ready'])
        self.assertEqual(page._wait_for_snapshot(read, 'ready', timeout=1), 'ready')
        self.assertEqual(read.call_count, 3)
        self.assertEqual(page._wait_for_snapshot(lambda: 'old', 'ready', timeout=0.01), 'old')

    def test_receipt_timestamp_formats_and_midnight(self):
        self.assertTrue(valid_receipt_timestamp('Today, 12:00 PM', START, END))
        self.assertTrue(valid_receipt_timestamp('Today, 12:00', START, END))
        self.assertFalse(valid_receipt_timestamp('Today, 24:00', START, END))
        self.assertFalse(valid_receipt_timestamp('Today, 11:59 AM', START, END))
        self.assertFalse(valid_receipt_timestamp('Today, 12:60 PM', START, END))
        self.assertTrue(valid_receipt_timestamp(
            'Today, 12:00 AM', datetime(2026, 11, 14, 23, 59, 59), datetime(2026, 11, 15, 0, 0, 3),
        ))
        self.assertFalse(valid_bet_id('undefined'))
        self.assertFalse(valid_bet_id('-'))
        self.assertTrue(valid_bet_id('#B-12345'))

    def test_match_selection_requires_future_data_and_validates_overrides(self):
        api = Mock(spec=BettingApi)
        api.get_matches.return_value = [MATCH]
        api.redact.side_effect = lambda value: value
        with patch.dict(os.environ, {'BETTING_MATCH_ID': ''}), patch.object(conftest, 'date') as clock:
            clock.today.return_value = date(2026, 11, 13)
            self.assertEqual(conftest.match.__wrapped__(api), MATCH)
        with self.assertRaisesRegex(ValueError, 'not found'):
            select_upcoming_match([MATCH], reference_date=date(2026, 11, 13), match_id='missing')

    def test_reset_uses_readback_and_reports_contract_mismatch(self):
        api = Mock(spec=BettingApi)
        api.reset_balance.return_value = response(200, {'balance': 125.5, 'currency': 'EUR'})
        api.get_balance.return_value = Decimal('120')
        request = Mock()
        request.config.getoption.return_value = False
        with warnings.catch_warnings(record=True) as reported:
            warnings.simplefilter('always')
            self.assertEqual(conftest.sandbox_balance.__wrapped__(api, MATCH, request), Decimal('120'))
        self.assertEqual(len(reported), 1)
        self.assertIn('BUG-04', str(reported[0].message))

    def test_past_and_today_offers_are_rejected(self):
        for reference in [date(2026, 11, 14), date(2026, 11, 15)]:
            with self.subTest(reference=reference), self.assertRaisesRegex(ValueError, 'no eligible UPCOMING'):
                select_upcoming_match([MATCH], reference_date=reference)

    def test_explicit_past_override_is_not_replaced_with_another_offer(self):
        future = {**MATCH, 'id': 'future', 'kickoffDate': '2026-12-28'}
        with self.assertRaisesRegex(ValueError, 'BETTING_MATCH_ID'):
            select_upcoming_match([MATCH, future], reference_date=date(2026, 11, 16), match_id='sample')

    def test_mixed_catalogue_selects_latest_eligible_non_two_odds(self):
        future = {**MATCH, 'id': 'future', 'kickoffDate': '2026-12-28'}
        masked = {**MATCH, 'id': 'masked', 'kickoffDate': '2026-12-29', 'odds': {'home': 2}}
        selected = select_upcoming_match([MATCH, future, masked], reference_date=date(2026, 11, 16))
        self.assertEqual(selected['id'], 'future')

    def test_fixture_reports_invalid_override_as_setup_failure(self):
        api = Mock(spec=BettingApi)
        api.get_matches.return_value = [MATCH]
        api.redact.side_effect = lambda value: value
        with patch.dict(os.environ, {'BETTING_MATCH_ID': 'sample'}), patch.object(conftest, 'date') as clock:
            clock.today.return_value = date(2026, 11, 16)
            with self.assertRaisesRegex(conftest.pytest.fail.Exception, 'Test-data setup blocked'):
                conftest.match.__wrapped__(api)
        api.reset_balance.assert_not_called()
        api.place_bet.assert_not_called()

    def test_negative_balance_diagnostic_keeps_amount_response_and_redacts_account(self):
        session = Mock()
        account = 'private test/id'
        session.headers = {'x-user-id': account}
        session.get.return_value = response(200, {'balance': -0.01, 'currency': 'EUR', 'account': account})
        diagnostic = BettingApi(session, 'https://local.invalid').balance_diagnostic()
        self.assertIn('-0.01', diagnostic)
        self.assertIn('HTTP 200', diagnostic)
        self.assertIn('AssertionError', diagnostic)
        self.assertIn('<redacted>', diagnostic)
        self.assertNotIn(account, diagnostic)
        session.get.assert_called_once()

    def test_balance_http_and_json_errors_keep_response_evidence(self):
        for status, body, expected in [(500, 'service unavailable', 'HTTP 500'), (200, 'not-json', 'not valid JSON')]:
            with self.subTest(status=status):
                session = Mock()
                session.headers = {}
                result = response(status, {})
                result._content = body.encode()
                session.get.return_value = result
                diagnostic = BettingApi(session, 'https://local.invalid').balance_diagnostic()
                self.assertIn(expected, diagnostic)
                self.assertIn(body, diagnostic)

    def test_request_exception_keeps_response_and_redacts_raw_and_encoded_id(self):
        session = Mock()
        account = 'private test/id'
        session.headers = {'x-user-id': account}
        result = response(503, {'error': 'unavailable', 'account': account})
        failure = requests.HTTPError(f'read failed for {quote(account, safe="")}', response=result)
        diagnostic = BettingApi(session, 'https://local.invalid').failure_details(failure)
        self.assertIn('HTTP 503', diagnostic)
        self.assertIn('unavailable', diagnostic)
        self.assertNotIn(account, diagnostic)
        self.assertNotIn(quote(account, safe=''), diagnostic)

    def test_ui_preserves_balance_validation_reason_and_expected_amount(self):
        with self.assertRaises(AssertionError) as caught:
            self.run_ui(balance_error=AssertionError('Invalid balance: -0.01 EUR; HTTP 200'))
        self.assertIn('expected 110.00 EUR', str(caught.exception))
        self.assertIn('-0.01', str(caught.exception))
        self.assertIn('HTTP 200', str(caught.exception))

    def test_lost_placement_response_reads_funds_once_without_resubmitting(self):
        session = Mock()
        account = 'private test/id'
        session.headers = {'x-user-id': account}
        session.post.side_effect = requests.ReadTimeout(f'response lost for {account}')
        session.get.return_value = response(200, {'balance': 20, 'currency': 'EUR'})
        with self.assertRaises(PlacementOutcomeUnknown) as caught:
            BettingApi(session, 'https://local.invalid').place_bet('sample', Decimal('100'))
        diagnostic = str(caught.exception)
        self.assertIn('ReadTimeout', diagnostic)
        self.assertIn('20 EUR', diagnostic)
        self.assertIn('No placement retry', diagnostic)
        self.assertNotIn(account, diagnostic)
        session.post.assert_called_once()
        session.get.assert_called_once()

    def test_lost_placement_response_survives_failed_balance_diagnostic(self):
        session = Mock()
        session.headers = {}
        session.post.side_effect = requests.ReadTimeout('original placement timeout')
        session.get.side_effect = requests.ConnectionError('balance endpoint offline')
        with self.assertRaises(PlacementOutcomeUnknown) as caught:
            BettingApi(session, 'https://local.invalid').place_bet('sample', Decimal('100'))
        self.assertIn('original placement timeout', str(caught.exception))
        self.assertIn('balance endpoint offline', str(caught.exception))
        session.post.assert_called_once()
        session.get.assert_called_once()

    def test_retry_config_guards_cover_options_and_ini(self):
        for options, ini in [({'force_reruns': 1}, 0), ({'reruns': 1}, 0), ({}, 1)]:
            with self.subTest(options=options, ini=ini):
                config = Mock()
                config.getoption.side_effect = lambda name, default=None: options.get(name, default)
                config.getini.return_value = ini
                with self.assertRaises(conftest.pytest.UsageError):
                    conftest.pytest_configure(config)

    def test_flaky_markers_cannot_enable_placement_retries(self):
        for marker in [conftest.pytest.mark.flaky(), conftest.pytest.mark.flaky(2),
                       conftest.pytest.mark.flaky(reruns=1)]:
            with self.subTest(marker=marker):
                item = Mock(nodeid='tests/example.py::placement')
                item.get_closest_marker.return_value = marker.mark
                with self.assertRaises(conftest.pytest.UsageError):
                    conftest.pytest_collection_modifyitems([item])
        item.get_closest_marker.return_value = conftest.pytest.mark.flaky(reruns=0).mark
        conftest.pytest_collection_modifyitems([item])

    def test_receipt_read_failure_retains_independent_wallet_evidence(self):
        with self.assertRaises(AssertionError) as caught:
            self.run_ui(receipt_error=StaleElementReferenceException('receipt replaced'))
        self.assertIn('Receipt could not be inspected', str(caught.exception))
        self.assertIn('receipt replaced', str(caught.exception))
        self.ui_api.get_balance.assert_called_once()
        self.ui_dialog.close_receipt.assert_called_once()
        self.ui_page.place_bet.assert_called_once()
        self.assertEqual(self.ui_page.wait_for_wallet_state.call_count, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
