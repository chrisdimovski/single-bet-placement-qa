# Strategy and recommendations

**Prepared:** 16 November 2026 (Europe/Skopje)

## Why these two automated scenarios

The UI scenario covers the core money flow in one placement: API catalogue, match card, calculated slip, receipt, persisted debit and both visible balances. This detects frontend/backend disagreement while limiting test-data consumption. Home odds differ from 2.00 to expose the known receipt payout defect.

The API scenario checks both sides of the EUR 100.00 cap using sufficient funds: reject EUR 100.01 without a debit, then accept EUR 100.00 with the correct response and persisted balance. Pairing rejection with a positive control prevents a reject-everything implementation from passing and also verifies payout and currency on success.

**Risk tradeoff:** negative-stake balance inflation (BUG-07) and insufficient-funds acceptance (BUG-08) are more severe than a stake-cap defect. This selection meets the two-scenario scope with one complete UI journey and one API scenario covering rejection, acceptance and response consistency. The critical financial defects are documented gaps in automated coverage and take priority when the API suite expands.

## Framework and data choices

SeleniumBase supplies pytest's browser fixture, ChromeDriver lifecycle and failure artifacts. The page object owns interactions and snapshots; tests own expected outcomes. A small requests helper centralizes endpoints, Decimal balance parsing, transport timeouts and redacted diagnostics.

Both scenarios validate a future-dated, non-2.00 Home offer before resetting the shared wallet. The UI also requires the UPCOMING badge. TODAY remains excluded until date-only eligibility is clarified. Setup reads persisted funds and warns on the reset mismatch (BUG-04); no teardown reset erases the final state. Parallel workers and automatic reruns are blocked for the shared account, including forced reruns and per-test flaky markers.

Explicit waits poll for the next required UI state. Snapshot failures retain the last observation; balance errors retain expected amounts and HTTP evidence. A lost API placement response triggers one read-only wallet diagnostic and an unknown-outcome error without retrying the POST. Receipt-read failures are reported while the independent debit, dismissal and wallet checks continue. Transport timeouts bound connection/read inactivity and are not performance assertions. Receipt IDs require meaningful, non-placeholder content without a format restriction. Timestamps are checked against the browser's placement interval using the current en-US display. No history endpoint exists to independently verify stored bet count or receipt-ID authenticity.

The [offline framework checks](../checks/framework_checks.py) exercise valid and faulty implementations without sandbox requests. They run separately from pytest's two assignment scenarios. Platform-specific commands and configuration are in the [README](../README.md#offline-framework-checks).

## Exploratory coverage

Loading feedback, retry/Close/X behavior, rapid clicks, selection changes and filters suit exploratory UI checks within the assignment's time budget. Browser request blocking simulates a transport failure; a request log distinguishes duplicate UI submissions from overlapping API requests. [Execution results](execution-results.md) record completed scenarios and link to the defect evidence.

## Top three recommendations if the project scales

1. Add the critical negative-stake and insufficient-funds API regressions first. Then add controlled concurrency checks and a small Chrome smoke suite to CI, retaining redacted failure evidence.
2. Provision isolated accounts per run/worker and repair reset consistency. This enables repeatable setup and safe parallelism.
3. Resolve minimum stake, input normalization, same-day eligibility and receipt-field guarantees across the feature specification, OpenAPI, API and UI.
