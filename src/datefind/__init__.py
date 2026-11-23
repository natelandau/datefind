"""Datefind."""

from collections.abc import Generator
from datetime import date, tzinfo
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tzlocal import get_localzone

from datefind._fragments import FirstNumber
from datefind._search import FoundDate, search_dates

__all__ = ["FoundDate", "find_dates"]


def find_dates(
    text: str,
    first: Literal["month", "day", "year"] = "month",
    tz: str | tzinfo = "",
    now: date | None = None,
    *,
    short_digit_dates: bool = False,
) -> Generator[FoundDate, None, None]:
    """Search text for dates and return them as FoundDate objects.

    Parse the input text to locate and extract dates in various formats. When ambiguous dates are encountered (e.g. 01/02/03), use the `first` parameter to determine the order of month/day/year. Return every date at midnight in the specified timezone.

    Args:
        text (str): The text to search for dates
        first (Literal["month", "day", "year"]): The position of month/day/year when parsing ambiguous dates. Defaults to "month"
        tz (str | tzinfo): The timezone of every returned datetime, as a name such as "America/New_York" or a tzinfo object. Uses the system timezone if empty. Defaults to ""
        now (date | None): The date that relative dates such as "tomorrow" or "3 days ago" resolve against. An aware datetime is converted to `tz`, and a naive one is read as a wall-clock time in `tz`. Defaults to the current time
        short_digit_dates (bool): Match runs of 4 to 7 digits with no separators, such as 9819 or 120524, as dates. Runs of 8 digits, such as 20240512, always match. Defaults to False

    Returns:
        Generator[FoundDate, None, None]: A generator yielding FoundDate objects for each date found in the text

    Raises:
        ValueError: If an invalid first parameter or timezone is provided
        TypeError: If `now` is not a date, a datetime, or None
    """
    if now is not None and not isinstance(now, date):
        msg = f"Invalid now: {now!r}, expected a date, a datetime, or None"
        raise TypeError(msg)

    try:
        first_number = FirstNumber[first.upper()]
    except KeyError as e:
        msg = f"Invalid first number: {first}, expected 'month', 'day', or 'year'"
        raise ValueError(msg) from e

    try:
        timezone = tz if isinstance(tz, tzinfo) else ZoneInfo(tz) if tz else get_localzone()
    # ZoneInfo raises a plain ValueError for malformed keys such as absolute paths
    except (ZoneInfoNotFoundError, ValueError) as e:
        msg = f"Invalid timezone: {tz}, expected an IANA timezone name such as 'America/New_York'"
        raise ValueError(msg) from e

    return search_dates(
        text=text, tz=timezone, first=first_number, now=now, short_digit_dates=short_digit_dates
    )
