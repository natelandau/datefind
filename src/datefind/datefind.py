"""Datefind is a Python library for finding dates in text."""

from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import regex as re
from rich.console import Console

from datefind.utils import DatePatternFactory

from .constants import (
    APRIL,
    AUGUST,
    CENTURY,
    DECEMBER,
    FEBRUARY,
    JANUARY,
    JULY,
    JUNE,
    MARCH,
    MAY,
    NOVEMBER,
    OCTOBER,
    SEP_CHARS,
    SEPTEMBER,
    DayToNumber,
    FirstNumber,
)

console = Console()


@dataclass
class Date:
    """Store information about a date found in text.

    Properties:
        date (datetime): The parsed datetime object
        match (str): The specific text that matched the date pattern
        span (tuple[int, int]): The start and end positions of the match in the text
    """

    date: datetime
    match: str
    span: tuple[int, int]


class DateFind:
    """Find and parse dates within text using pattern matching.

    Searches text for date patterns and returns Date objects containing the parsed datetime, original text, matched pattern, and location of the match.

    Args:
        text (str): The text to search for dates
        tz (ZoneInfo): The timezone to use for the parsed dates
        first_number (FirstNumber): Whether the first number in a date pattern represents the day or month
    """

    def __init__(
        self,
        text: str,
        tz: ZoneInfo,
        first_number: FirstNumber,
    ):
        self.text = text
        self.tz = tz
        self.first_number = first_number
        self.base_date = datetime(datetime.now(self.tz).year, 1, 1, tzinfo=self.tz)
        self.factory = DatePatternFactory(first_number=self.first_number)

    def find_dates(self) -> Generator[Date, None, None]:
        """Search the text for date patterns and parse them into Date objects.

        Parse dates in various formats including relative dates like 'today', 'yesterday', 'next week' as well as explicit dates with day, month and year components. All dates are converted to datetime objects in the timezone specified during initialization.

        Yields:
            Generator[Date, None, None]: A sequence of Date objects containing the parsed datetime, original text, matched pattern, and location of the match.
        """
        regex = self.factory.make_regex()
        matches = regex.finditer(self.text)

        for match in matches:
            as_dt = self._handle_relative_dates(match=match)

            groups = match.groupdict()
            has_date_component = any(
                groups.get(key) for key in ("year", "month", "day", "month_as_text", "day_as_text")
            )
            if not as_dt and has_date_component:
                day = self._day_to_number(match=match) or 1
                month = self._month_to_number(match=match) or datetime.now(self.tz).month
                year = self._year_to_number(match=match) or datetime.now(self.tz).year
                as_dt = datetime(year=int(year), month=month, day=day, tzinfo=self.tz)

            if as_dt:
                date = Date(
                    date=as_dt,
                    match=match.group(),
                    span=match.span(),
                )
                yield date

    def _handle_relative_dates(self, match: re.Match) -> datetime | None:  # noqa: PLR0911
        """Parse relative date patterns like 'today', 'yesterday', 'next week' into datetime objects.

        Convert relative date references in the matched text into concrete datetime objects using the configured timezone. Handles basic time periods (today/tomorrow/yesterday) and relative time spans (last/next week/month/year).

        Args:
            match (re.Match): The regex match containing relative date pattern groups

        Returns:
            datetime | None: The parsed datetime object if a relative pattern was matched, None otherwise
        """
        groups = match.groupdict()
        now = datetime.now(self.tz)

        # Handle simple offsets
        if groups.get("today"):
            return now
        if groups.get("yesterday"):
            return now - timedelta(days=1)
        if groups.get("tomorrow"):
            return now + timedelta(days=1)
        if groups.get("last_week"):
            return now - timedelta(days=7)
        if groups.get("next_week"):
            return now + timedelta(days=7)

        # Handle month/year adjustments
        adjustments = {
            "last_month": {"month": now.month - 1},
            "next_month": {"month": now.month + 1},
            "last_year": {"year": now.year - 1},
            "next_year": {"year": now.year + 1},
        }

        for key, adj in adjustments.items():
            if groups.get(key):
                try:
                    return now.replace(tzinfo=self.tz, **adj)
                except ValueError:
                    return None

        return None

    @staticmethod
    def _year_to_number(match: re.Match) -> int | None:
        """Parse a year string from a regex match into a numeric year.

        Convert 2-digit years to 4-digit years by prepending the current century. For example, '23' becomes '2023'.

        Args:
            match (re.Match): The regex match containing year information in named groups

        Returns:
            int: The numeric year value
        """
        if year := match.groupdict().get("year"):
            if len(year) == 2:  # noqa: PLR2004
                return int(f"{CENTURY}{year}")
            return int(year)

        return None

    @staticmethod
    def _month_to_number(match: re.Match) -> int | None:
        """Parse a month string from a regex match into a numeric month (1-12).

        Convert both text month names (e.g. "January", "Feb") and numeric months from the regex match. Text matching is case-insensitive.

        Args:
            match (re.Match): The regex match containing month information in named groups

        Returns:
            int: The numeric month value (1-12)
        """
        month_patterns = {
            JANUARY: 1,
            FEBRUARY: 2,
            MARCH: 3,
            APRIL: 4,
            MAY: 5,
            JUNE: 6,
            JULY: 7,
            AUGUST: 8,
            SEPTEMBER: 9,
            OCTOBER: 10,
            NOVEMBER: 11,
            DECEMBER: 12,
        }

        if month_as_text := match.groupdict().get("month_as_text"):
            for pattern, number in month_patterns.items():
                if re.search(pattern, month_as_text, re.IGNORECASE):
                    return number

        if month := match.groupdict().get("month"):
            return int(month)

        return None

    @staticmethod
    def _day_to_number(match: re.Match) -> int | None:
        """Parse a day string from a regex match into a numeric day of month.

        Convert both text day representations (e.g. "1st", "2nd") and numeric days from the regex match.

        Args:
            match (re.Match): The regex match containing day information in named groups

        Returns:
            int | None: The numeric day value, or None if no day found
        """
        if day_as_text := match.groupdict().get("day_as_text"):
            day_as_text = re.sub(rf"[{SEP_CHARS}]", "", day_as_text)
            return DayToNumber[day_as_text.upper()].value

        if day := match.groupdict().get("day"):
            return int(day)

        return None
