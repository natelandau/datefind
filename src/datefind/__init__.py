"""Datefind."""

from collections.abc import Generator
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tzlocal import get_localzone

from datefind.constants import FirstNumber
from datefind.datefind import Date, DateFind


def find_dates(
    text: str, first: Literal["month", "day", "year"] = "month", tz: str = ""
) -> Generator[Date, None, None]:
    """Search text for dates and return them as Date objects.

    Parse the input text to locate and extract dates in various formats. When ambiguous dates are encountered (e.g. 01/02/03), use the `first` parameter to determine the order of month/day/year. Convert all dates to the specified timezone.

    Args:
        text (str): The text to search for dates
        first (Literal["month", "day", "year"]): The position of month/day/year when parsing ambiguous dates. Defaults to "month"
        tz (str): The timezone name (e.g. "America/New_York") to localize dates. Uses system timezone if empty. Defaults to ""

    Returns:
        Generator[Date, None, None]: A generator yielding Date objects for each date found in the text

    Raises:
        ValueError: If an invalid first parameter or timezone is provided
    """
    try:
        first_number = FirstNumber[first.upper()]
    except KeyError as e:
        msg = f"Invalid first number: {first}"
        raise ValueError(msg) from e

    try:
        timezone = ZoneInfo(tz) if tz else get_localzone()
    except ZoneInfoNotFoundError as e:
        msg = f"Invalid timezone: {tz}"
        raise ValueError(msg) from e

    datefind = DateFind(text=text, tz=timezone, first_number=first_number)
    return datefind.find_dates()
