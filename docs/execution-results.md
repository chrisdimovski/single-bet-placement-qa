# Test execution results

**Prepared:** 16 November 2026 (Europe/Skopje)

Desktop Chrome and wallet API - [Assignment sandbox][sandbox]

## Summary

- **SB-01 - Fail:** Single-bet receipt and wallet reconciliation.
- **SB-02 - Pass:** Stake one cent above the available balance, checked through the UI.
- **SB-03 - Fail:** Negative and malformed inputs become different valid stakes; precision normalization is a separate clarification.

[Reproduction steps][walkthrough] - [Bug reports][bugs] - [Automated results](#automated-verification)

## SB-01 - Placement and reconciliation

The API confirmed an opening wallet of €120.00. One simulated €10.00 Home bet was placed on LAFC vs Inter Miami at 2.20.

**Receipt**

- The slip showed LAFC vs Inter Miami, Home. The receipt reversed the teams and omitted the selection.
- The stake and odds matched the slip at €10.00 and 2.20.
- The payout preview showed €22.00. The receipt showed **€20.00**.
- One success receipt appeared. Bet ID `#B-24052`, displayed timestamp `Today, 02:37 PM`.

**Wallet after closing the receipt and before refreshing**

- The header and empty bet slip both showed **€120.00**.
- `GET /api/balance` returned HTTP 200 with **€110.00 EUR**, the expected amount after one €10.00 debit.
- The slip showed zero active selections and the empty-state prompt.

**Related bugs:** [BUG-01][bug-01] - [BUG-02][bug-02] - [BUG-03][bug-03] - [BUG-06][bug-06]

## SB-02 - Insufficient balance

A €100.00 setup bet left **€20.00** in the wallet. Entering **€20.01** displayed **Insufficient balance** and disabled **Place Bet**. `GET /api/balance` in Swagger still returned **€20.00**.

**Result: Pass for UI validation.** The separate API insufficient-funds bypass is recorded in [BUG-08][bug-08].

## SB-03 - Stake validation

The Home outcome for LAFC vs Inter Miami used a verified balance of €120.00. These checks used the €1.00 minimum from the business rule and UI message. Feature Specification section 4.1 lists €1.01; the minimum remains a specification conflict.

**Boundary checks**

| Entered stake | Displayed stake | Place Bet | Validation |
| --- | --- | --- | --- |
| €0.99 | €0.99 | Disabled | Minimum stake is €1.00. |
| €1.00 | €1.00 | Enabled | None. |
| €1.01 | €1.01 | Enabled | None. |
| €100.00 | €100.00 | Enabled | None. |
| €100.01 | €100.01 | Disabled | Maximum stake is €100.00. |

**Signed and malformed input - Fail**

The recorded input checks in [BUG-12][bug-12] showed:

| Entered text | Displayed stake | Place Bet |
| --- | --- | --- |
| `-10` | `10` | Enabled |
| `1e2` | `12` | Enabled |
| `1.2.3` | `1.23` | Enabled |

These conversions change the intended amount, including turning a negative stake into a positive one. The checks stopped at the slip; no wagers were submitted for these inputs. These observations support the scenario's Fail result.

**Extra decimal precision - Clarification**

Pasting **`10.001`** changed the field to **`10.00`**, with **Place Bet** enabled and no validation message. At 2.20 the slip showed a €10.00 total stake and a €22.00 potential payout. The check ended at the slip; no bet was submitted for this input.

Truncating a third decimal may be an acceptable input restriction. This observation needs a normalization-rule clarification and is not the basis for the Fail result above.

## Quick exploration

**Wallet reset - Fail.** The reset response reported €125.50 and the wallet readback showed €120.00. On repeat, both endpoints returned HTTP 200 with those respective amounts. The reset response should agree with the persisted wallet under the feature specification. [BUG-04][bug-04]

Other exploratory findings, including financial validation, duplicate submission and filters, are recorded in the [20-ticket defect register][bugs].

## Automated verification

**Latest run:** 16 November 2026. **Result: 2 failed, 2 warnings, 0 errors.**

- **API stake boundaries - Pass; overall API scenario - Fail.** The API rejected €100.01 with sufficient funds and accepted €100.00 with the expected debit. The success response used `USD` instead of `EUR`, failing the complete scenario. [BUG-05][bug-05]
- **Selenium receipt and wallet - Fail.** Reproduced the receipt and balance discrepancies in SB-01.
- **Framework checks - Pass.** All 26 offline checks passed, including uncertain placement diagnostics, retry guards, stale receipt handling and receipt-ID validation. Pytest collects exactly two sandbox scenarios.
- **Setup warnings:** reset returned 125.50 while the persisted balance was 120.00 in each setup. [BUG-04][bug-04]

The [README][framework] contains setup, run commands and verification history. Generated browser logs and JUnit output remain in ignored `latest_logs/` and `artifacts/`; redact authenticated URLs before sharing selected evidence.

[sandbox]: https://qae-assignment-tau.vercel.app/
[walkthrough]: test-plan.md
[bugs]: bug-tickets.md
[bug-01]: bug-tickets.md#bug-01---success-receipt-shows-an-incorrect-potential-payout
[bug-02]: bug-tickets.md#bug-02---success-receipt-reverses-home-and-away-teams
[bug-03]: bug-tickets.md#bug-03---header-and-bet-slip-balances-remain-stale-after-a-successful-debit
[bug-04]: bug-tickets.md#bug-04---reset-response-disagrees-with-the-persisted-balance
[bug-05]: bug-tickets.md#bug-05---successful-placement-response-reports-usd-for-a-eur-wager
[bug-06]: bug-tickets.md#bug-06---success-receipt-omits-the-selected-outcome
[bug-08]: bug-tickets.md#bug-08---the-api-accepts-a-bet-above-the-available-balance
[bug-12]: bug-tickets.md#bug-12---invalid-stake-input-is-converted-into-a-different-submittable-amount
[framework]: ../README.md#verification-status
