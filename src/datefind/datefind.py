"""Datefind is a Python library for finding dates in text."""

from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import regex as re
from rich.console import Console

from datefind.pattern_factory import PatternFactory

from .constants import (
    CENTURY,
    SEP_CHARS,
    DayToNumber,
    FirstNumber,
)

console = Console()

_WEEKDAY_TO_NUM = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tues": 1,
    "tue": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thurs": 3,
    "thur": 3,
    "thu": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

_SIMPLE_OFFSET_DAYS = {
    "today": 0,
    "yesterday": -1,
    "tomorrow": 1,
    "last_week": -7,
    "next_week": 7,
    "this_week": 0,
    "this_month": 0,
    "this_year": 0,
}
_MONTH_ADJUSTMENTS = {"last_month": -1, "next_month": 1}
_YEAR_ADJUSTMENTS = {"last_year": -1, "next_year": 1}
_RELATIVE_DATE_KEYS = (
    frozenset(_SIMPLE_OFFSET_DAYS) | frozenset(_MONTH_ADJUSTMENTS) | frozenset(_YEAR_ADJUSTMENTS)
)

# Two-letter keys cover the `xx?` optional-final-char alternation branches in
# constants.MONTH (e.g., `jan?` can capture "ja"); three-letter keys cover standard
# abbreviations and longer names via a first-3-chars slice.
_MONTH_TEXT_MAP = {
    "ja": 1,
    "jan": 1,
    "fe": 2,
    "feb": 2,
    "ma": 3,
    "mar": 3,
    "ap": 4,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "au": 8,
    "aug": 8,
    "sep": 9,
    "oc": 10,
    "oct": 10,
    "no": 11,
    "nov": 11,
    "de": 12,
    "dec": 12,
}


def _offset_months(now: datetime, n: int) -> datetime:
    """Offset a datetime by n months, carrying across year boundaries.

    Naive `replace(month=now.month + n)` fails at year boundaries (January - 1 or December + 1). This helper uses divmod so the carry into year is correct.

    Args:
        now (datetime): The datetime to offset.
        n (int): The number of months to offset by. Positive shifts forward, negative backward.

    Returns:
        datetime: The offset datetime. May raise ValueError if the target day-of-month does not exist (e.g., January 31 + 1 month).
    """
    new_month_index = (now.month - 1) + n
    year_offset, month_zero = divmod(new_month_index, 12)
    return now.replace(year=now.year + year_offset, month=month_zero + 1)


@dataclass
class FoundDate:
    """Store information about a date found in text.

    Properties:
        date (datetime): The parsed datetime object
        match (str): The specific text that matched the date pattern
        span (tuple[int, int]): The start and end positions of the match in the text
    """

    datetime: datetime
    match: str
    span: tuple[int, int]


class DateFind:
    """Find and parse dates within text using pattern matching.

    Searches text for date patterns and returns FoundDate objects containing the parsed datetime, original text, matched pattern, and location of the match.

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
        self.factory = PatternFactory(first_number=self.first_number)

    def find_dates(self) -> Generator[FoundDate, None, None]:
        """Search the text for date patterns and parse them into FoundDate objects.

        Parse dates in various formats including relative dates like 'today', 'yesterday', 'next week' as well as explicit dates with day, month and year components. All dates are converted to datetime objects in the timezone specified during initialization.

        Yields:
            Generator[FoundDate, None, None]: A sequence of FoundDate objects containing the parsed datetime, original text, matched pattern, and location of the match.
        """
        regex = self.factory.make_regex()
        now = datetime.now(self.tz)

        for match in regex.finditer(self.text):
            groups = match.groupdict()
            as_dt: datetime | None = None

            if any(groups.get(k) for k in _RELATIVE_DATE_KEYS):
                as_dt = self._handle_relative_dates(groups, now)
            elif groups.get("rel_count"):
                as_dt = self._handle_relative_count(groups, now)
            elif groups.get("weekday") or groups.get("bare_weekday"):
                as_dt = self._handle_weekday(groups, now)

            has_date_component = any(
                groups.get(key) for key in ("year", "month", "day", "month_as_text", "day_as_text")
            )
            if not as_dt and has_date_component:
                day = self._day_to_number(groups) or 1
                month = self._month_to_number(groups) or now.month
                year = self._year_to_number(groups) or now.year
                as_dt = datetime(year=int(year), month=month, day=day, tzinfo=self.tz)

            if as_dt:
                yield FoundDate(
                    datetime=as_dt,
                    match=match.group(),
                    span=match.span(),
                )

    @staticmethod
    def _handle_relative_dates(groups: dict[str, str | None], now: datetime) -> datetime | None:
        """Parse relative date patterns like 'today', 'yesterday', 'next week' into datetime objects.

        Convert relative date references in the matched text into concrete datetime objects using the configured timezone. Handles basic time periods (today/tomorrow/yesterday), same-period "this" references (this week/month/year), and relative time spans (last/next week/month/year).

        Args:
            groups (dict[str, str | None]): The regex match groupdict containing relative date pattern groups
            now (datetime): The current time in the target timezone

        Returns:
            datetime | None: The parsed datetime object if a relative pattern was matched, None otherwise
        """
        for key, days in _SIMPLE_OFFSET_DAYS.items():
            if groups.get(key):
                return now + timedelta(days=days)

        for key, delta in _MONTH_ADJUSTMENTS.items():
            if groups.get(key):
                try:
                    return _offset_months(now, delta)
                except ValueError:
                    return None

        for key, delta in _YEAR_ADJUSTMENTS.items():
            if groups.get(key):
                try:
                    return now.replace(year=now.year + delta)
                except ValueError:
                    return None

        return None

    @staticmethod
    def _handle_weekday(groups: dict[str, str | None], now: datetime) -> datetime | None:
        """Resolve weekday references to a concrete datetime.

        Convert bare weekday names (`Monday`) and modifier-prefixed weekdays (`next Monday`, `last Friday`, `this Tuesday`) into concrete datetime objects relative to the current date. Bare weekdays and `next`-prefixed resolve to the next occurrence (always future). `last`-prefixed resolves to the prior occurrence (always past). `this`-prefixed resolves to the next occurrence within 0-6 days (today if target is today).

        Args:
            groups (dict[str, str | None]): The regex match groupdict containing weekday information in named groups
            now (datetime): The current time in the target timezone

        Returns:
            datetime | None: The resolved datetime, or None if no weekday group matched
        """
        weekday_str = groups.get("weekday") or groups.get("bare_weekday")
        if not weekday_str:
            return None

        target = _WEEKDAY_TO_NUM[weekday_str.lower()]
        current = now.weekday()
        modifier = (groups.get("weekday_modifier") or "").lower()

        if modifier == "last":
            # `or 7` forces a full-week jump when target == current
            return now - timedelta(days=(current - target) % 7 or 7)
        if modifier == "this":
            # No `or 7` here: today is a valid "this <weekday>"
            return now + timedelta(days=(target - current) % 7)
        # `next` or bare weekday — always future
        return now + timedelta(days=(target - current) % 7 or 7)

    @staticmethod
    def _handle_relative_count(  # noqa: PLR0911
        groups: dict[str, str | None], now: datetime
    ) -> datetime | None:
        """Resolve N-unit-ago / in-N-unit / N-unit-from-now expressions to a datetime.

        Compute a concrete datetime by offsetting the current time by N of the matched unit (days, weeks, months, years). Direction is determined by presence of the `rel_ago` named group: if set, subtracts; otherwise (for "in" and "from now") adds. Invalid target dates (e.g., Feb 29 + 1 year in a non-leap year) resolve to None.

        Args:
            groups (dict[str, str | None]): The regex match groupdict containing rel_count, rel_unit, and optionally rel_ago
            now (datetime): The current time in the target timezone

        Returns:
            datetime | None: The resolved datetime, or None if no relative-count groups matched or the target date is invalid
        """
        if not (count := groups.get("rel_count")) or not (unit := groups.get("rel_unit")):
            return None

        offset = int(count) * (-1 if groups.get("rel_ago") else 1)
        unit_lower = unit.lower().rstrip("s")

        try:
            if unit_lower == "day":
                return now + timedelta(days=offset)
            if unit_lower == "week":
                return now + timedelta(weeks=offset)
            if unit_lower == "month":
                return _offset_months(now, offset)
            if unit_lower == "year":
                return now.replace(year=now.year + offset)
        except ValueError:
            return None
        return None

    @staticmethod
    def _year_to_number(groups: dict[str, str | None]) -> int | None:
        """Parse a year string from a regex match into a numeric year.

        Convert 2-digit years to 4-digit years by prepending the current century. For example, '23' becomes '2023'.

        Args:
            groups (dict[str, str | None]): The regex match groupdict containing year information in named groups

        Returns:
            int: The numeric year value
        """
        if year := groups.get("year"):
            if len(year) == 2:  # noqa: PLR2004
                return int(f"{CENTURY}{year}")
            return int(year)

        return None

    @staticmethod
    def _month_to_number(groups: dict[str, str | None]) -> int | None:
        """Parse a month string or quarter designator from a regex match into a numeric month (1-12).

        Convert quarter designators (e.g. "Q2" → 4), text month names (e.g. "January", "Feb"), and numeric months from the regex match. Text matching is case-insensitive.

        Args:
            groups (dict[str, str | None]): The regex match groupdict containing month or quarter information in named groups

        Returns:
            int: The numeric month value (1-12)
        """
        if quarter := groups.get("quarter"):
            return (int(quarter[-1]) - 1) * 3 + 1

        if month_as_text := groups.get("month_as_text"):
            return _MONTH_TEXT_MAP.get(month_as_text.lower()[:3])

        if month := groups.get("month"):
            return int(month)

        return None

    @staticmethod
    def _day_to_number(groups: dict[str, str | None]) -> int | None:
        """Parse a day string from a regex match into a numeric day of month.

        Convert both text day representations (e.g. "1st", "2nd") and numeric days from the regex match.

        Args:
            groups (dict[str, str | None]): The regex match groupdict containing day information in named groups

        Returns:
            int | None: The numeric day value, or None if no day found
        """
        if day_as_text := groups.get("day_as_text"):
            day_as_text = re.sub(rf"[{SEP_CHARS}]", "", day_as_text)
            return DayToNumber[day_as_text.upper()].value

        if day := groups.get("day"):
            return int(day)

        return None
