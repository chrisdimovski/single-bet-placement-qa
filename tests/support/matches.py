from datetime import date
from decimal import Decimal


def select_upcoming_match(
    matches: list[dict], *, reference_date: date, match_id: str = ""
) -> dict:
    """Choose future-dated sandbox data; TODAY is ambiguous without a kickoff time."""
    candidates = [item for item in matches if item["id"] == match_id] if match_id else matches
    if not candidates:
        message = "BETTING_MATCH_ID was not found in the sandbox catalogue." if match_id else "Empty match catalogue."
        raise ValueError(message)

    dated = [(date.fromisoformat(item["kickoffDate"]), item) for item in candidates]
    eligible = [
        (kickoff, item)
        for kickoff, item in dated
        if kickoff > reference_date and Decimal(str(item["odds"]["home"])) != Decimal("2.00")
    ]
    if not eligible:
        selection = f"BETTING_MATCH_ID={match_id!r}" if match_id else "The sandbox catalogue"
        raise ValueError(
            f"{selection} has no eligible UPCOMING Home offer. Require a date after {reference_date} "
            "and odds other than 2.00. PAST and TODAY fixtures are not used for placement."
        )
    return max(eligible, key=lambda candidate: candidate[0])[1]
