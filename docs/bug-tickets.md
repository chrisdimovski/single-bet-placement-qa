# Single bet placement - bug tickets

**Prepared:** 16 November 2026 (Europe/Skopje)

20 reported defects from UI and API testing. Each ticket includes severity, description, reproduction steps, expected and actual results, business impact and evidence.

## Test environment and evidence

| Reports | Evidence source |
| --- | --- |
| BUG-01 through BUG-06 | Latest Windows automated run: 16 November 2026; supporting exploratory notes. |
| BUG-07 through BUG-20 | Exploratory execution notes, referenced by EXP/C check IDs. |

- **Windows automation:** Windows 10 build 19045, Chrome 157.0.8103.51, ChromeDriver 157.0.8103.78; headless, 1440 x 1000, en-US.
- **Exploratory environments:** Chrome on Linux and Windows. Per-check browser versions are not recorded in the exploratory notes.
- **Evidence references:** EXP identifies exploratory reports; C identifies individual checks. Raw artifacts for these references are not bundled with this document.
- **Account:** use the same assigned user ID in the app URL and API `x-user-id` header. Send placement requests as JSON.
- **Balance:** run independent checks sequentially and read `GET /api/balance` before and after placements. Verify the persisted balance after reset (BUG-04).
- **Fixtures:** LAFC vs Inter Miami: `mls-lafc-inter-miami-2026-12-28`, Home 2.20. Marseille vs PSG: `ligue-1-marseille-psg-2026-11-17`, Home 4.10. Verify catalogue prices and statuses before reproduction.

Full test outcomes: [execution-results.md](execution-results.md).

## BUG-01 - Success receipt shows an incorrect potential payout

**Severity:** High

**Description**

The successful bet receipt shows a potential payout that disagrees with the pre-placement slip and the stake-times-odds calculation. For a EUR 10.00 Home bet at 2.20, the slip correctly previews EUR 22.00, but the receipt shows EUR 20.00.

**Steps to reproduce**

1. Open the application using the assigned user ID. Reset the sandbox account and verify its persisted balance with `GET /api/balance`; the reproduced baseline was EUR 120.00.
2. Locate LAFC vs Inter Miami, catalogue ID `mls-lafc-inter-miami-2026-12-28`, shown as UPCOMING.
3. Select Home at odds 2.20.
4. Enter a stake of EUR 10.00 and verify that the slip previews EUR 22.00.
5. Click Place Bet once and wait for the success receipt.
6. Inspect Potential Payout in the receipt.

**Expected result**

Potential Payout is EUR 22.00, calculated as EUR 10.00 x 2.20, and agrees with the slip. Feature specification sections 2.4 and 3 require consistent receipt values and payout calculation.

**Actual result**

Potential Payout is EUR 20.00, despite the receipt showing the EUR 10.00 stake and 2.20 odds.

**Business impact**

The customer receives incorrect information about the potential return and cannot reconcile the receipt with the accepted wager.

**Evidence**

The verified Selenium run reported:

```text
Receipt payout: expected 'EUR 22.00', got 'EUR 20.00'
```

Currency symbols in the assertion have been written as EUR for readability. The catalogue/card/slip consistency checks and receipt stake/odds checks passed. See [execution-results.md](execution-results.md) for the scenario and automated results.

Supporting exploratory notes:

The Linux run used Marseille vs PSG at 4.10 and recorded EUR 41.00 in the slip and EUR 20.00 in the receipt. See EXP-05, C033 and C044.

## BUG-02 - Success receipt reverses home and away teams

**Severity:** High

**Description**

The receipt reverses the team order shown by the API catalogue, match card and bet slip. The assignment defines the first team as Home, so reversing the order changes how the customer interprets the selected outcome.

**Steps to reproduce**

1. Open the application using the assigned user ID and verify sufficient funds for a EUR 10.00 bet.
2. Locate `mls-lafc-inter-miami-2026-12-28` and verify that the match card shows LAFC vs Inter Miami.
3. Select Home at 2.20 and enter EUR 10.00.
4. Verify that the slip still shows LAFC vs Inter Miami.
5. Click Place Bet once and wait for the success receipt.
6. Compare the receipt's Match field with the card and slip.

**Expected result**

The receipt shows LAFC vs Inter Miami, preserving LAFC as Home and Inter Miami as Away. This follows feature specification section 2.4 and the assignment's home-first match-ordering convention.

**Actual result**

The receipt shows Inter Miami vs LAFC.

**Business impact**

The customer can interpret the wager as applying to the wrong team, creating uncertainty or a dispute about the accepted bet.

**Evidence**

```text
Receipt match: expected 'LAFC vs Inter Miami', got 'Inter Miami vs LAFC'
```

The automated catalogue/card/slip comparison passed before placement. The receipt comparison failed after the same placement.

Supporting exploratory notes:

In the Linux run, **Marseille vs PSG** became **PSG vs Marseille**. See EXP-06, C003 and C040.

## BUG-03 - Header and bet-slip balances remain stale after a successful debit

**Severity:** High

**Description**

After a successful placement, the backend deducts the stake but both visible wallet balances retain their pre-placement value. The mismatch remains after the receipt closes and the five-second observation window expires.

**Steps to reproduce**

1. Reset the assigned sandbox account, then call `GET /api/balance` for the same account. Confirm the reproduced baseline of EUR 120.00.
2. Open or reload the application and confirm that both header and bet-slip balances show EUR 120.00.
3. Select Home for LAFC vs Inter Miami at 2.20 and enter EUR 10.00.
4. Click Place Bet once and wait for the success receipt.
5. Call `GET /api/balance` for the same account and record the persisted balance.
6. Close the receipt and observe the header balance, bet-slip balance and selection count for five seconds without refreshing the page.

**Expected result**

The persisted balance and both visible balances show EUR 110.00 after the single EUR 10.00 debit. The selection count becomes zero. References: feature specification sections 2.2-2.3 and the assignment's shared-balance rule.

**Actual result**

The persisted balance is EUR 110.00, but the header and bet slip still show EUR 120.00 after five seconds. The selection count correctly becomes zero.

**Business impact**

The customer can choose a subsequent stake using an overstated available balance.

**Evidence**

The persisted-debit assertion passed. The final UI observation was:

| Surface | Expected | Observed |
| --- | --- | --- |
| GET /api/balance | EUR 110.00 | EUR 110.00 |
| Header balance | EUR 110.00 | EUR 120.00 |
| Bet-slip balance | EUR 110.00 | EUR 120.00 |
| Active selections | 0 | 0 |

The failed wallet assertion retained these last observed values rather than failing immediately after submission.

Supporting exploratory notes:

| Balance source | Expected | Observed in Windows |
| --- | --- | --- |
| API | EUR 110.00 | EUR 110.00 |
| Header | EUR 110.00 | EUR 120.00 |
| Bet slip | EUR 110.00 | EUR 120.00 |

In the Linux exploratory run, the UI stayed at EUR 119.00 while the API showed EUR 109.00. See EXP-08 and C047.

## BUG-04 - Reset response disagrees with the persisted balance

**Severity:** Medium

**Description**

The reset endpoint reports a balance of EUR 125.50, while an immediate balance read for the same account returns EUR 120.00. The feature specification requires consistency, but the live OpenAPI description permits a discrepancy. This ticket includes that contract conflict for clarification.

**Steps to reproduce**

1. Use the assigned `x-user-id` for all requests and ensure no other session is placing bets on that account.
2. Send `POST /api/reset-balance`.
3. Record the HTTP status, balance and currency in the response.
4. Immediately send `GET /api/balance` with the same user header, without placing any bet between the requests.
5. Compare the two balance values.

**Expected result**

The reset response and persisted balance readback report the same configured initial EUR balance. Feature specification section 5.3 explicitly requires the response body and persisted state to be consistent after reset.

**Actual result**

Both requests return HTTP 200. Reset reports EUR 125.50; GET reports EUR 120.00.

**Business impact**

A consumer or test that trusts the reset response starts subsequent checks with an incorrect balance assumption.

**Evidence**

Both independently executed test setups reported:

```text
Reset contract mismatch (BUG-04): response balance=125.5,
persisted balance=120. Using the persisted baseline.
```

The live OpenAPI description for reset says the response payload may differ from persisted balance. That conflicts with the feature specification; product/API owners should confirm which contract to enforce. The automated scenarios use GET as their baseline and keep this warning visible.

Supporting exploratory notes:

The Linux and Windows runs both recorded the EUR 5.50 difference. The live OpenAPI reset description allows the response and stored balance to differ, while the feature spec requires them to agree. Use `GET /api/balance` as the starting balance for test steps until the intended contract is clarified. See EXP-13 and C098.

## BUG-05 - Successful placement response reports USD for a EUR wager

**Severity:** High

**Description**

The placement endpoint returns `currency: "USD"` for a successful wager against a EUR-denominated wallet. The stake, odds, payout and balance amounts otherwise match the expected EUR transaction.

**Steps to reproduce**

1. Reset the assigned sandbox account and verify `GET /api/balance` returns balance 120.00 and currency EUR.
2. Confirm `mls-lafc-inter-miami-2026-12-28` exists in `GET /api/matches` and has Home odds 2.20.
3. Send `POST /api/place-bet` with the assigned `x-user-id`, JSON content type and this body:

   ```json
   {
     "matchId": "mls-lafc-inter-miami-2026-12-28",
     "selection": "HOME",
     "stake": 100.00
   }
   ```

4. Inspect `currency` and `balance` in the HTTP 200 response.
5. Call `GET /api/balance` for the same account and compare its currency and amount.

**Expected result**

The placement response reports currency EUR, payout 220.00 and balance 20.00. The balance readback also reports EUR 20.00. References: feature specification section 3 (EUR currency) and section 5.3 (placement response).

**Actual result**

The placement succeeds with currency USD and balance 20.00. GET reports currency EUR and balance 20.00. The other checked success fields, including payout, match the expected values.

**Business impact**

A downstream consumer can interpret wager, payout or wallet amounts in the wrong currency.

**Evidence**

```text
Accepted bet currency: expected 'EUR', got 'USD'
```

The API scenario passed its match, selection, stake, odds, payout, returned-balance and persisted-debit comparisons. Only the success currency comparison failed.

Supporting exploratory notes:

The Linux run also found USD on successful placement responses and EUR in the balance response. See EXP-11, C058, C092–C095 and C097.

## BUG-06 - Success receipt omits the selected outcome

**Severity:** High

**Description**

The receipt does not show whether the accepted wager selected Home, Draw or Away. Match, stake and odds alone do not satisfy the explicit requirement to show the selected outcome.

**Steps to reproduce**

1. Open the application using the assigned user ID and verify sufficient funds for a EUR 10.00 bet.
2. Locate LAFC vs Inter Miami, catalogue ID `mls-lafc-inter-miami-2026-12-28`.
3. Select Home at odds 2.20 and enter EUR 10.00.
4. Confirm that the slip shows `Match Winner: Home`.
5. Click Place Bet once and wait for the success receipt.
6. Inspect the receipt for the selected outcome.

**Expected result**

The receipt explicitly shows Home, consistent with the selected outcome in the slip. Feature specification section 2.4 lists Selection as a mandatory receipt field.

**Actual result**

The selected outcome is absent. The automated receipt reader returns no Home/Draw/Away selection.

**Business impact**

The customer cannot verify the outcome attached to the accepted wager, especially when the receipt also reverses team order (BUG-02).

**Evidence**

```text
Receipt selection: expected 'Home', got None
```

The pre-placement `Match Winner: Home` slip assertion passed in the same run. Related defect: BUG-02 covers the reversed team order in the same receipt.

Supporting exploratory notes:

The Linux run also found the selection missing from the Marseille vs PSG receipt. See EXP-07, C011 and C041.

## BUG-07 - A negative API stake adds money to the balance

**Severity:** Critical

**Description**

Submitting a numeric stake of -1.00 EUR through the API increases the balance by EUR 1.00.

**Steps to reproduce**

1. Read the starting balance with `GET /api/balance`.
2. Send `POST /api/place-bet` with a valid upcoming match, `selection: "HOME"` and numeric `stake: -1`. The verified run used Marseille vs PSG.
3. Read the balance again for the same account.

**Expected result**

The API rejects the bet with HTTP 422 and leaves the balance unchanged. See the feature spec, sections 4.1 and 5.3.

**Actual result**

The API returns HTTP 200 and accepts the negative stake. The balance increases by EUR 1.00.

**Business impact**

A caller can increase available funds by submitting an invalid bet.

**Evidence**

C078 recorded HTTP 200, `stake: -1` and a balance rise from EUR 109.00 to EUR 110.00. C091 recorded another EUR 1.00 increase during the invalid-input checks. See EXP-01.

## BUG-08 - The API accepts a bet above the available balance

**Severity:** Critical

**Description**

The API accepts a EUR 20.01 stake when the wallet has only EUR 20.00.

**Steps to reproduce**

1. Reset the sandbox account and verify EUR 120.00 with `GET /api/balance`.
2. Place a EUR 100.00 bet on an upcoming match. Confirm the remaining balance is EUR 20.00.
3. Send another `POST /api/place-bet` for a valid match and outcome with `stake: 20.01`.
4. Read the wallet balance again.

**Expected result**

The API returns HTTP 422 for insufficient funds and the balance stays at EUR 20.00. See the feature spec, sections 4.1 and 5.3.

**Actual result**

The API returns HTTP 200 and the balance drops to EUR −0.01. The browser blocks the same stake at the same opening balance and shows **Insufficient balance**.

**Business impact**

A direct API caller can place bets the account does not have enough money to cover.

**Evidence**

C096 recorded the EUR −0.01 balance. A separate check reproduced the overdraft with a EUR 1.63 stake against EUR 1.62. See EXP-02.

## BUG-09 - Double-clicking Place Bet places two bets

**Severity:** Critical

**Description**

A double-click can create two receipts and two charges for one intended bet.

**Steps to reproduce**

1. Verify an opening balance of EUR 120.00 with `GET /api/balance`.
2. Select **Home** for **Marseille vs PSG** and enter EUR 10.00.
3. Double-click **Place Bet** once.
4. Close the first success receipt and check for a second. Read `GET /api/balance`.

**Expected result**

One success receipt appears and the balance decreases by EUR 10.00 to EUR 110.00. See the feature spec, section 2.3.

**Actual result**

The button stays enabled during **Placing…**. Two success receipts appear and the balance decreases to EUR 100.00.

**Business impact**

Customers can be charged twice for one intended bet.

**Evidence**

C029 and its recheck each recorded two receipts and the same EUR 20.00 total debit. In the separate direct API test C100, two synchronized requests returned HTTP 200 and 409 with a single debit. See EXP-03.

Scope: the double-click check recorded two receipts and a total debit of EUR 20.00. These observations do not establish overlapping API requests or an in-progress lock failure. C100 covers direct API concurrency separately.

## BUG-10 - Past matches can still be selected and bet on

**Severity:** High

**Description**

A match marked **PAST** appears in the upcoming list, can be selected, and accepts a bet through the API.

**Steps to reproduce**

1. Open **Upcoming Football Matches** and locate **Manchester Utd vs Chelsea**, dated 27 February 2026.
2. Confirm the card shows **PAST**, then click its Home odds.
3. Record the balance. Send `POST /api/place-bet` using `matchId: "premier-league-manutd-chelsea"`, `selection: "HOME"` and `stake: 1`.
4. Read the balance again.

**Expected result**

Past matches are outside the pre-match scope. The fixture is unavailable for selection and the API rejects the bet without changing the balance. See the feature spec, sections 1, 2.1 and 3.

**Actual result**

The match appears in the upcoming list and opens the slip when selected. The API accepts the wager and deducts EUR 1.00.

**Business impact**

The system can take bets on events outside its supported pre-match window, creating disputes over whether those bets are valid.

**Evidence**

C007 and C008 recorded the **PAST** badge and the active selection. C057 found 91 past-dated entries among 103 catalog matches. C099 recorded HTTP 200 and a balance drop from EUR 120.00 to EUR 119.00. See EXP-04.

Scope note: reproduce against a card explicitly labelled PAST by the application. This report concerns the sandbox's own status and supported pre-match scope; it does not assume a live sports calendar.

## BUG-11 - The available balance disappears from the active bet slip

**Severity:** Medium

**Description**

The slip shows the wallet balance when empty and hides it when an outcome is selected.

**Steps to reproduce**

1. Open the betting page with an empty slip and locate the balance in it.
2. Select an outcome for an upcoming match.
3. Enter a stake and inspect the bet slip.

**Expected result**

The active slip shows the available balance with the stake and potential payout. See the feature spec, section 2.2.

**Actual result**

The slip balance disappears. **Remove All** appears in its place. The header keeps showing the balance.

**Business impact**

Customers lose sight of their funds within the form where they choose a stake.

**Evidence**

C010 verified the empty-slip balance. C035 recorded its disappearance after an outcome was selected. See EXP-09.

## BUG-12 - Invalid stake input is converted into a different submittable amount

**Severity:** High

**Description**

The stake field silently changes invalid entries into a different amount that can be submitted.

**Steps to reproduce**

1. Select an upcoming match with enough funds for a EUR 12.00 bet.
2. Paste `10.001` into **Stake**. Record the field value and whether **Place Bet** is enabled.
3. Clear the field and repeat with `-10`, `1e2` and `1.2.3`.

**Expected result**

The field enforces numeric, positive stakes with a single decimal separator and at most two decimal places (feature specification sections 4.1 and 4.4). Negative or malformed text must not become a different valid wager without clear feedback. The specification does not explicitly define normalization behavior; confirm the intended handling with product.

**Actual result**

| Entered | Displayed | Place Bet |
| --- | --- | --- |
| `10.001` | `10.00` | Enabled |
| `-10` | `10` | Enabled |
| `1e2` | `12` | Enabled |
| `1.2.3` | `1.23` | Enabled |

**Business impact**

A customer can submit an amount they did not intend, including a positive bet after entering a negative stake.

**Evidence**

C025, C027, C028 and C030 verified the field values and enabled button in Chrome using paste-equivalent input. The checks stopped before submitting the changed amounts. See EXP-10.

Clarification: preventing a third decimal by truncating `10.001` to `10.00` may be an acceptable input restriction on its own. The financial-risk examples are `-10` becoming `10`, `1e2` becoming `12`, and `1.2.3` becoming `1.23`. These changes should be reviewed against the agreed input-normalization contract rather than treating every formatting change as a confirmed defect.

## BUG-13 - The placement API returns a payout one cent too low

**Severity:** High

**Description**

For two stakes at odds 4.10, the placement response returns a payout one cent below the exact result.

**Steps to reproduce**

1. Verify there is at least EUR 101.00 in the wallet and that **Marseille vs PSG** has Home odds of 4.10.
2. Send a EUR 1.00 Home bet to `POST /api/place-bet` and read `payout`.
3. Send a EUR 100.00 Home bet at the same odds and read `payout`.

**Expected result**

The payouts are 4.10 and 410.00 under the assignment’s stake-times-odds formula. Both products are exact to the cent.

**Actual result**

The payouts returned are 4.09 and 409.99.

**Business impact**

Systems using the response can display or record an incorrect potential return.

**Evidence**

C092 recorded `{"stake": 1, "odds": 4.1, "payout": 4.09}`. C095 recorded `{"stake": 100, "odds": 4.1, "payout": 409.99}`. Both responses returned HTTP 200. See EXP-12.

Scope note: this is the API response payout at odds 4.10. BUG-01 concerns a different observed result in the UI receipt. No shared root cause has been established.

## BUG-14 - Incomplete JSON triggers HTTP 500

**Severity:** Medium

**Description**

The placement endpoint reports a server error when the caller sends incomplete JSON.

**Steps to reproduce**

1. Prepare `POST /api/place-bet` with `Content-Type: application/json` and the assigned `x-user-id`.
2. Send the exact raw body `{"stake":`, with no value or closing brace.
3. Read the HTTP status and response body.

**Expected result**

The API returns HTTP 400 for malformed JSON. See the feature spec, sections 4.3 and 5.3.

**Actual result**

The API returns HTTP 500 with error `internal_server_error`.

**Business impact**

Clients may retry a request that needs to be corrected, and monitoring may count a client input error as a server incident.

**Evidence**

C069 reproduced HTTP 500 with the response message `Unable to process request.` See EXP-14.

## BUG-15 - GET on the placement endpoint returns success

**Severity:** Medium

**Description**

The placement endpoint returns HTTP 200 for GET even though the documented placement method is POST.

**Steps to reproduce**

1. Send `GET /api/place-bet` with the assigned `x-user-id`.
2. Read the response status and body.

**Expected result**

The API returns HTTP 405 because GET is unsupported. See the feature spec, sections 4.3 and 5.3.

**Actual result**

The API returns HTTP 200 with an empty JSON object, `{}`.

**Business impact**

Clients can mistake a request made with the wrong method for a successful operation.

**Evidence**

C067 reproduced HTTP 200 and `{}` with a valid candidate header. See EXP-15.

## BUG-16 - The odds filter hides a match at the exact requested price

**Severity:** Medium

**Description**

The filter returns no matches for 4.10–4.10 even though a match offers odds of 4.10.

**Steps to reproduce**

1. Clear the odds filter. Find **Marseille vs PSG** and confirm its Home odds are 4.10.
2. Open **Odds** and set both **Min** and **Max** to 4.10.
3. Click **Apply** and check the result list.

**Expected result**

Marseille vs PSG remains in the list. The range includes both endpoints. See the feature spec, section 2.6.

**Actual result**

The result list contains zero matches.

**Business impact**

Customers can miss a match that offers the exact price they searched for.

**Evidence**

C006 verified the 4.10 Home odds before filtering. C048 recorded zero cards after applying 4.10–4.10. See EXP-16.

## BUG-17 - The odds filter accepts a minimum above the maximum

**Severity:** Medium

**Description**

The application applies an invalid odds range and gives the user no explanation.

**Steps to reproduce**

1. Open **Odds**.
2. Enter 6.00 for **Min** and 2.00 for **Max**.
3. Click **Apply** and inspect the filter label and match list.

**Expected result**

The application rejects the range and explains that the minimum cannot exceed the maximum. See the feature spec, section 2.6.

**Actual result**

The panel closes. The active filter shows 6.00–2.00, the list is empty, and there is no error message.

**Business impact**

Customers can mistake an invalid search for a valid search with no matching offers.

**Evidence**

C049 recorded the applied range 6.00–2.00, a closed filter panel and zero cards. See EXP-17.

## BUG-18 - The date filter misses a match in the New York time zone

**Severity:** Medium

**Description**

The same calendar date returns a match in a Skopje browser session and zero matches in a New York session.

**Steps to reproduce**

1. Verify that `GET /api/matches` lists **Marseille vs PSG** with `kickoffDate: "2026-11-17"`.
2. In Chrome DevTools Sensors, override the browser time zone to **Europe/Skopje**, reload the page and filter for **17 November 2026**.
3. Change only the time-zone override to **America/New_York**. Keep locale, catalogue and selected calendar date unchanged; reload and apply the same filter.
4. Compare the match lists.

**Expected result**

Both sessions show Marseille vs PSG on its published date. The API supplies a calendar date without a time or offset. See the feature spec, sections 2.6 and 5.3.

**Actual result**

Skopje returns one card for Marseille vs PSG. New York returns zero cards.

**Business impact**

Customers in affected time zones can miss scheduled matches when filtering by date.

**Evidence**

The supplemental date check changed only the browser time zone. The selected date and catalog were the same in both runs. See EXP-18.

## BUG-19 - Canceling a date selection changes the filter label

**Severity:** Low

**Description**

Clicking **Cancel** leaves the results unchanged, but the date label shows the selection that was canceled.

**Steps to reproduce**

1. Start with **Date: All** and record the number of match cards.
2. Open **Date** and select **17 November 2026**.
3. Click **Cancel**. Read the date label and count the cards again.

**Expected result**

The label stays at **Date: All** and the match list remains unchanged.

**Actual result**

The label changes to **Date: 17/11/2026** and all 103 match cards stay visible.

**Business impact**

Customers may think the list was filtered and misinterpret which matches are shown.

**Evidence**

The supplemental date-cancel check recorded **Date: 17/11/2026** with the original 103 cards still visible. See EXP-19.

## BUG-20 - The odds filter silently changes a maximum of 20.00 to 10.00

**Severity:** Medium

**Description**

The filter applies a lower maximum than the user enters and does not explain the limit.

**Steps to reproduce**

1. Open **Odds**. Enter 1.01 for **Min** and 20.00 for **Max**.
2. Click **Apply**.
3. Read the label of the applied range.

**Expected result**

The filter applies 1.01–20.00 or explains why that range cannot be applied. The feature spec documents odds from 1.01 to 1000.00 in section 3.

**Actual result**

The filter applies 1.01–10.00 without feedback.

**Business impact**

Customers cannot set their intended upper limit and may assume the filter used their original values.

**Evidence**

The supplemental odds check recorded the applied label **Odds: 1.01 - 10.00**. The highest price in the test catalog was 7.50, so the run verified the changed filter value. See EXP-20 and C056.

Verification limit: the tested catalogue had no odds above 7.50. The observed defect is the unexplained change to the applied maximum; exclusion of offers above 10.00 was not demonstrated. Confirm whether a separate odds-filter cap is intended and, if so, document and communicate it.
