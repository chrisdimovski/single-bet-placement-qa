# Single bet placement test plan

**Prepared:** 16 November 2026 (Europe/Skopje)

Scope: latest desktop Chrome, football, single pre-match bets and the supporting API. Six scenarios are ordered by financial risk. Reset and read back the sandbox balance before each independent scenario; record the actual baseline rather than assuming the advertised EUR 125.50. Use the application's sample catalogue and status labels; this assignment does not use a real sports schedule.

## SB-01 - Place one bet and reconcile receipt and balance

**Priority** Critical

**Risk rationale** An incorrect debit or misleading receipt can cause a financial dispute even when the success modal appears.

**Steps**

1. Read `GET /api/balance`. Verify both UI balances agree. Select an upcoming Home outcome with odds other than 2.00. Record the catalogue ID, home/away order and odds.
2. Enter EUR 10.00, verify the slip and payout preview, and submit once. Observe the loading state and final outcome.
3. Compare every receipt field with the slip. Read the persisted balance, close the receipt, and check both wallet displays and selection count.

**Expected result** One successful placement and one EUR 10.00 debit. Receipt match order, selection, stake, odds and payout agree with the catalogue/slip. Payout equals stake times odds. The receipt includes a meaningful bet ID and placement timestamp. Closing it clears the selection; both displays agree with the persisted balance. References: sections 2.2-2.4 and 3.

## SB-02 - Reject a stake one cent above available funds

**Priority** Critical

**Risk rationale** Accepting an unfunded wager can overdraw the wallet.

**Steps**

1. Reset, read the persisted balance, and confirm it covers EUR 100.00. Place one EUR 100.00 bet to seed a balance below the per-bet cap; record its outcome.
2. Read the resulting persisted balance and reload the UI. Use one cent above that amount as the next stake, provided it is between EUR 1.01 and EUR 100.00. Otherwise record a setup blocker.
3. Select an upcoming match, enter the stake and inspect validation and the placement button. Read the balance again without submitting an invalid UI bet.

**Expected result** The UI shows `Insufficient balance`, prevents placement and leaves persisted funds unchanged from step 2. No second receipt appears. Reference: section 4.1.

## SB-03 - Validate stake boundaries and decimal precision

**Priority** High

**Risk rationale** A one-cent boundary error can block valid wagers or accept excess exposure. Invalid precision can change the intended amount.

**Steps**

1. Reset and verify at least EUR 100.01 of persisted funds, then select an upcoming outcome.
2. Try 0.99, 1.00, 1.01, 100.00 and 100.01 individually. Record validation, displayed input and whether placement is enabled. Clear the input between attempts; these UI checks do not require submitting every value.
3. Paste `10.001`, then try blank, zero, a negative amount and nonnumeric text. Record whether the input prevents invalid text or shows validation. Confirm invalid amounts cannot be submitted.
4. Independently check the API maximum: reject 100.01 without a debit, then accept 100.00 and verify the response and persisted debit. The automated API scenario covers this pair.

**Expected result** Reject below-minimum values, amounts over EUR 100.00, missing/nonnumeric stakes and more than two decimal places at the API. The UI prevents an invalid stake from reaching placement. Accept 1.01 and 100.00 with sufficient funds. Record 1.00 separately under the unresolved minimum conflict below. References: sections 3, 4.1 and 4.4.

## SB-04 - Prevent overlapping placement requests

**Priority** High

**Risk rationale** Overlapping submissions can create unintended wagers and extra debits.

**Steps**

1. Record persisted funds, select an upcoming outcome and enter EUR 10.00. Open Chrome DevTools Network and preserve the request log.
2. Double-click Place Bet and try clicking during `Placing...`. Record actual request start/end timing, request payloads and responses.
3. Close the receipt and read the persisted balance. If no requests overlap, record only the UI prevention result; mark API concurrency unverified.

**Expected result** The UI prevents repeated submission while processing, resolves to one outcome and deducts EUR 10.00 once. If a second request arrives while the same user's first bet is being processed, the documented API response is HTTP 409. Separate submissions after completion are separate bets, not a promised idempotency mechanism. References: sections 2.3 and 5.3.

## SB-05 - Recover from a failed placement

**Priority** High

**Risk rationale** A misleading retry or dismissal can place an unintended bet, lose the user's input or leave the flow unusable.

**Steps**

1. Record persisted funds, select an upcoming outcome and enter EUR 10.00. In Chrome DevTools, block only the browser request to `/api/place-bet`, then submit once. Record that this simulates a transport failure, not an observed server HTTP 500.
2. Verify the error modal, its title/body and all three actions. Read persisted funds through the unblocked balance endpoint; the blocked placement must not have debited them.
3. Remove the blocking rule, click Rebet once and observe a fresh submission using the same selection/stake. Check the final receipt and one persisted debit.
4. In separate failed attempts, test Close and the top-right X. For each, record a fresh baseline, block placement, wait for the error, dismiss it and inspect selection, stake, request count and funds. Remove the blocking rule afterward.

**Expected result** The modal says `Something went wrong` and explains the failure. Rebet closes it and retries the retained bet, eventually yielding one final outcome. Close and X clear the selection/stake, do not retry and preserve funds. References: sections 2.3 and 2.5.

## SB-06 - Replace and remove a selection

**Priority** Medium

**Risk rationale** A stale selection can make the user wager on a different outcome than intended.

**Steps**

1. Select Home, then select Draw on a different upcoming match.
2. Compare count, teams, outcome and odds with the second selection. Remove it using its x control.
3. Make another selection, choose Remove All and inspect the slip and placement availability.

**Expected result** Replacement leaves one active selection with the second match and Draw odds. Either removal leaves an empty slip and placement unavailable. References: sections 2.1-2.2.

## Exploratory charters

Time permitting, check inclusive date/odds endpoints, inverted filter feedback, direct-API authentication/selection/match/body validation, and whether refresh shows the debited balance after a stale display. Record only checks actually performed. These are exploration candidates rather than extra mandatory scenarios.

## Clarifications

| Topic | Conflicting or incomplete requirement | Treatment |
| --- | --- | --- |
| Minimum stake | Section 3 and section 4.4 say EUR 1.00; section 4.1 says EUR 1.01. OpenAPI specifies minimum 1.00. | Record EUR 1.00 behavior without declaring the conflict resolved; request product clarification. |
| Same-day eligibility | API exposes a date only; the UI distinguishes TODAY from UPCOMING. | Do not infer a kickoff time or compare against real sports schedules. Automated placement requires a future-dated UPCOMING offer; explore TODAY separately until its eligibility is clarified. |
| Reset balance | Specification requires response/persisted consistency; observed reset response differs. | Record BUG-04 and establish baselines through GET, never the reset response alone. |
