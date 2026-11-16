import re
from datetime import datetime


def valid_receipt_timestamp(label: str, started: datetime, finished: datetime) -> bool:
    """Validate the current English 'Today, HH:MM [AM/PM]' display to minute precision."""
    match = re.fullmatch(r"Today,\s*(\d{1,2}):(\d{2})(?:\s*([AP]M))?", label, re.IGNORECASE)
    if not match:
        return False
    hour, minute = int(match[1]), int(match[2])
    period = match[3]
    if minute > 59 or (period and not 1 <= hour <= 12) or (not period and hour > 23):
        return False
    if period:
        hour = hour % 12 + (12 if period.upper() == "PM" else 0)
    # Consider both dates if placement straddles midnight.
    for day in {started.date(), finished.date()}:
        displayed = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute)
        if started.replace(second=0, microsecond=0) <= displayed <= finished.replace(second=0, microsecond=0):
            return True
    return False


def valid_bet_id(value: str) -> bool:
    """Require identifier content and reject placeholders; the spec defines no format."""
    if not isinstance(value, str):
        return False
    identifier = value.strip()
    placeholders = {"n/a", "na", "null", "none", "undefined", "unknown", "pending", "placeholder"}
    return identifier.casefold() not in placeholders and any(character.isalnum() for character in identifier)
