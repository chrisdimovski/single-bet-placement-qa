# Single bet placement test plan

**Prepared:** 16 November 2026 (Europe/Skopje)

## Objective and scope

Verify that a customer can place one pre-match football bet and that the
selected outcome, stake, odds, payout and wallet reconcile. Check that the
slip and API enforce stake limits and that the customer can find and manage
the intended selection.

Coverage includes the desktop match list and filters, one active selection,
stake validation, placement, the receipt and the wallet. The feature
specification excludes live bets, accumulators, other sports and mobile UX.

## Test approach

- **Scenario execution.** Run SB-01, SB-02 and SB-03 in desktop Chrome. Cover a
  successful transaction first, then insufficient funds, then stake limits.
  SB-03 goes before SB-04 because every placement uses stake validation and
  the boundaries can be checked without submitting additional wagers.
- **Additional coverage.** SB-04 checks repeat submission. SB-05 and SB-06
  check selection and filtering before a wager. Run a short exploratory check
  around placement and wallet behavior after the three prioritized scenarios,
  including error feedback, retry and receipt dismissal.
- **Automation.** The Selenium test covers SB-01 across the catalogue, slip,
  receipt and persisted/visible wallet. The API test covers SB-03 by rejecting
  €100.01 without a debit, then accepting €100.00 and checking the success
  response and persisted balance.

## Environment and test data

Use the [assignment sandbox](https://qae-assignment-tau.vercel.app/) in
desktop Chrome and the assigned test account. Use
[Swagger](https://qae-assignment-tau.vercel.app/api/docs) or the direct API
for wallet readbacks. Start when at least one upcoming fixture and the
balance endpoint are available.

Run balance-changing scenarios sequentially. Where a reset is needed, verify
the persisted opening balance with `GET /api/balance` before using it as test
data. Use an upcoming match with a known price and a payout that is exact to
the cent. Use Home odds other than 2.00 so the known receipt payout defect
cannot match the preview by coincidence. Automation uses a future-dated
fixture; same-day eligibility requires clarification. For the stake-cap
check, start with at least €100.01 available so insufficient balance cannot
mask the per-bet maximum.

The working minimum is €1.00, based on the business rules and UI copy.
Feature Specification §4.1 lists €1.01. Record the exact €1.00 behavior and
carry the discrepancy forward as a clarification.

## Prioritized scenarios

### SB-01 — Place one bet and reconcile receipt and balance

**Priority** Critical

**Risk rationale** An incorrect debit or receipt can lead to a wager dispute.

**Steps**

1. Verify the opening wallet and select an upcoming Home outcome.
2. Enter €10.00, record the slip details and submit once.
3. Record the outcome. Compare the receipt with the slip, then close it and
   reconcile both onscreen balances with the API balance before refreshing.

**Expected result** One success receipt and one €10.00 debit. The receipt
contains a bet ID and placement timestamp. The match order, outcome, stake,
odds and payout agree with the slip. Payout equals stake × odds. Closing
the receipt clears the selection and the displayed wallets match the API.

### SB-02 — Reject a stake one cent above available funds

**Priority** Critical

**Risk rationale** Accepting an unfunded wager can leave the wallet overdrawn.

**Steps**

1. Establish and verify a wallet balance where the next cent is a valid stake
   under the per-bet limits. A €100.00 setup bet from €120.00 leaves €20.00.
2. Reload the app, select an upcoming outcome and enter one cent more than
   the verified wallet. For a €20.00 wallet, enter €20.01.
3. Inspect the validation and submit state, then verify the persisted wallet.

**Expected result** **Insufficient balance** is displayed, **Place Bet** is
disabled and the persisted wallet stays at the pre-attempt amount.

### SB-03 — Validate stake limits and decimal precision

**Priority** High

**Risk rationale** A boundary error can block a valid wager, exceed the
per-bet limit or change the customer's intended stake.

**Steps**

1. Verify the wallet has at least €100.01 and select an upcoming outcome.
2. Enter €0.99, €1.00, €1.01, €100.00 and €100.01 separately. Record the
   displayed value, validation message and submit state.
3. Paste `10.001`, then try `-10`, `1e2` and `1.2.3` separately. Record any
   conversion, validation and submit state. Stop at the slip for invalid inputs.
4. At the API, reject a €100.01 stake without a debit, then accept €100.00
   and verify response fields and the persisted debit.

**Expected result** €0.99 and €100.01 are blocked with the relevant limit
message. €1.00, €1.01 and €100.00 are enabled under the working minimum
with sufficient funds. Negative or malformed text must not silently become a
different valid stake. Record precision truncation separately: limiting a
third decimal may be a valid input restriction, and the intended normalization
behavior requires clarification.

### SB-04 — Prevent a duplicate placement during submission

**Priority** High

**Risk rationale** Repeated input while placement is in progress can result
in an extra wager and debit.

**Steps**

1. Verify the opening balance and prepare one €10.00 wager.
2. Double-click **Place Bet** and try another activation during **Placing…**.
3. Capture request start/end timings in Chrome DevTools Network. Compare
   requests, receipts and the persisted wallet.

**Expected result** One accepted wager, one success receipt and one €10.00
debit. The loading state protects the placement from repeat input. An API
request arriving while another bet is in progress should return HTTP 409.
A double-click alone does not establish request overlap, and separate completed
submissions are not covered by an idempotency guarantee.

### SB-05 — Replace and remove a selection

**Priority** Medium

**Risk rationale** A mismatched slip can lead the customer to confirm the
wrong outcome.

**Steps**

1. Select Home for one upcoming match, then Draw for another.
2. Check the active match, outcome, odds and slip count. Remove the selection
   with its `x` control.
3. Select another outcome and clear it with **Remove All**.

**Expected result** The slip holds one selection and matches the last
chosen outcome. Either removal path empties the slip and disables placement.

### SB-06 — Verify date and odds filters

**Priority** Medium

**Risk rationale** Incorrect boundaries can hide eligible offers or leave
the customer with unclear feedback.

**Steps**

1. Choose a date with a known fixture, then apply a range with known fixtures
   on both endpoints. Compare the visible fixtures with the catalog dates.
2. Clear the date filter. Use a displayed price as both odds endpoints.
3. Enter a minimum above the maximum and apply the odds filter.

**Expected result** The single-day result matches that day and the date
range includes both endpoints. A match at the exact odds price is visible.
The inverted odds range is rejected with clear feedback.

## Evidence and completion

Record the environment, inputs, actual behavior and Pass, Fail or Blocked
for SB-01 through SB-03. For a debit, compare the slip and receipt with an
independent balance read. Add a screenshot or exact values for any mismatch.
Log the exploratory check and link the corresponding bugs. The run is ready
for review when these outcomes and the two automated tests are available.

[Execution results](execution-results.md) · [Bug reports](bug-tickets.md) ·
[Automation strategy](strategy.md)
