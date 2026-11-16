# Single bet placement QA

**Prepared:** 16 November 2026 (Europe/Skopje)

QA coverage for single bet placement: six prioritized scenarios, completed UI and exploratory testing, one Selenium UI test and one requests API test. Results, defects and automation decisions are documented below.

## Setup and run

Use Python 3.10+. Install current desktop Google Chrome for the UI scenario; API-only runs and offline framework checks do not require Chrome. SeleniumBase provides pytest's `sb` fixture, manages ChromeDriver and collects browser failure artifacts on top of Selenium WebDriver, pytest and requests.

PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:BETTING_USER_ID = "<your assigned candidate ID>"
.\.venv\Scripts\python.exe -m pytest tests -v --headed --window-size=1440,1000
```

macOS/Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
export BETTING_USER_ID='<your assigned candidate ID>'
.venv/bin/python -m pytest tests -v --headed --window-size=1440,1000
```

Use `tests/api` or `tests/ui` instead of `tests` to run one layer. Replace `--headed` with `--headless` for unattended UI execution. `pytest.ini` selects Chrome and the en-US browser locale.

## Offline framework checks

Run from the project root using the virtual environment's Python:

```powershell
# Windows
.\.venv\Scripts\python.exe -m checks.framework_checks
```

```bash
# macOS/Linux
.venv/bin/python -m checks.framework_checks
```

The checks are included in [checks/framework_checks.py](checks/framework_checks.py). They use local test doubles and make no sandbox requests. Replace `-m checks.framework_checks` with `-m pytest --collect-only -q` to inspect the two assignment scenarios without running them.

## Sandbox state and configuration

**Each test validates its match, then resets the assigned simulated wallet before running.** The API scenario then places EUR 100.00; the UI scenario places EUR 10.00. Setup reads `GET /api/balance` to establish actual funds. A disagreement with the reset response emits a visible BUG-04 warning; the reset response is not trusted as the baseline. There is no teardown reset, so the final balance remains available for investigation.

Run one process against this account and avoid simultaneous placements from other sessions. The framework rejects pytest parallel workers (`-n`) and positive automatic-rerun counts from `--reruns`, `--force-reruns`, the `reruns` ini setting or per-test `flaky` markers. These guards do not lock the account against other machines or browser sessions. An API placement transport failure triggers one balance read and an explicit unknown-outcome error, without another placement request. A balance snapshot alone does not prove the final outcome; inspect the attempt before a deliberate rerun.

| Setting | Default / purpose |
| --- | --- |
| `BETTING_USER_ID` | Required; supplied candidate ID, kept outside source control. |
| `BETTING_BASE_URL` | `https://qae-assignment-tau.vercel.app`; override for another compatible environment. |
| `BETTING_MATCH_ID` | Optional catalogue ID; eligibility is checked. Otherwise choose the latest eligible future-dated Home offer with odds other than 2.00. |
| `--no-reset-balance` | Preserve a deliberately prepared wallet. API testing still requires at least EUR 100.01; UI testing requires EUR 10.00. |

The catalogue is sample data rather than a real sports schedule. Both scenarios share a date-based eligibility check: kickoffDate must be after the runner's local calendar day, matching the application's normal local-date status calculation. TODAY is deliberately excluded because the API supplies no kickoff time. Explicit overrides must meet the same rule. An exhausted catalogue stops setup before any reset or placement POST, and the UI additionally requires an UPCOMING badge. Odds of 2.00 are excluded because they could conceal the known constant-payout defect.

## Automated coverage

- **API:** maximum-stake rejection and acceptance, success fields and persisted debit.
- **UI:** catalogue/card/slip consistency, receipt, persisted debit and visible wallet.

The [strategy](docs/strategy.md) explains the tradeoff with the critical financial defects, synchronization choices and coverage limits.

## Verification status

Latest verification on 16 November 2026:

- All 26 included offline framework checks passed, including uncertain placement outcomes, retry guards and stale receipt handling.
- Pytest collected exactly two sandbox scenarios; match validation precedes reset in both fixture setup plans.
- The live run completed with **2 failed, 2 warnings, 0 errors**. Existing API currency, receipt and stale-wallet defects were reproduced; both setups again reported BUG-04.
- Detailed results are in [execution-results.md](docs/execution-results.md).

## Documentation

- [Six-scenario test plan](docs/test-plan.md)
- [Execution results and defect reports](docs/execution-results.md)
- [Twenty consolidated bug tickets](docs/bug-tickets.md)
- [UI test](tests/ui/test_single_bet_placement.py) and [page object](tests/ui/pages/betting.py)
- [API test](tests/api/test_stake_limits.py) and [shared API helper](tests/support/api.py)
- [Offline framework checks](checks/framework_checks.py) and [match eligibility](tests/support/matches.py)
- [Strategy and recommendations](docs/strategy.md)

Browser failure artifacts can contain the authenticated URL. Logs, generated artifacts, the virtual environment and caches are ignored by Git. Keep the assigned ID in the environment and redact selected evidence before publication.
