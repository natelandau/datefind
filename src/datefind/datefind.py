"""Datefind is a Python library for finding dates in text."""

from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import regex as re
from rich.console import Console

from datefind.pattern_factory import PatternFactory

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
        matches = regex.finditer(self.text)

        for match in matches:
            as_dt = self._handle_relative_dates(match=match)
            if not as_dt:
                as_dt = self._handle_relative_count(match=match)
            if not as_dt:
                as_dt = self._handle_weekday(match=match)

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
                date = FoundDate(
                    datetime=as_dt,
                    match=match.group(),
                    span=match.span(),
                )
                yield date

    def _handle_relative_dates(self, match: re.Match) -> datetime | None:
        """Parse relative date patterns like 'today', 'yesterday', 'next week' into datetime objects.

        Convert relative date references in the matched text into concrete datetime objects using the configured timezone. Handles basic time periods (today/tomorrow/yesterday), same-period "this" references (this week/month/year), and relative time spans (last/next week/month/year).

        Args:
            match (re.Match): The regex match containing relative date pattern groups

        Returns:
            datetime | None: The parsed datetime object if a relative pattern was matched, None otherwise
        """
        groups = match.groupdict()
        now = datetime.now(self.tz)

        simple_offsets = {
            "today": now,
            "yesterday": now - timedelta(days=1),
            "tomorrow": now + timedelta(days=1),
            "last_week": now - timedelta(days=7),
            "next_week": now + timedelta(days=7),
            "this_week": now,
            "this_month": now,
            "this_year": now,
        }
        for key, value in simple_offsets.items():
            if groups.get(key):
                return value

        adjustments = {
            "last_month": lambda: self._offset_months(now, -1),
            "next_month": lambda: self._offset_months(now, 1),
            "last_year": lambda: now.replace(year=now.year - 1),
            "next_year": lambda: now.replace(year=now.year + 1),
        }
        for key, fn in adjustments.items():
            if groups.get(key):
                try:
                    return fn()
                except ValueError:
                    # Target day-of-month does not exist in resolved month/year
                    return None

        return None

    @staticmethod
    def _offset_months(now: datetime, n: int) -> datetime:
        """Offset a datetime by n months, carrying across year boundaries.

        Use when shifting a month value by an arbitrary signed integer N. Naive `replace(month=now.month + n)` fails at year boundaries (January - 1 or December + 1). This helper uses divmod so the carry into year is correct.

        Args:
            now (datetime): The datetime to offset.
            n (int): The number of months to offset by. Positive shifts forward, negative backward.

        Returns:
            datetime: The offset datetime. May raise ValueError if the target day-of-month does not exist (e.g., January 31 + 1 month).
        """
        new_month_index = (now.month - 1) + n
        year_offset, month_zero = divmod(new_month_index, 12)
        return now.replace(year=now.year + year_offset, month=month_zero + 1)

    def _handle_weekday(self, match: re.Match) -> datetime | None:
        """Resolve weekday references to a concrete datetime.

        Convert bare weekday names (`Monday`) and modifier-prefixed weekdays (`next Monday`, `last Friday`, `this Tuesday`) into concrete datetime objects relative to the current date. Bare weekdays and `next`-prefixed resolve to the next occurrence (always future). `last`-prefixed resolves to the prior occurrence (always past). `this`-prefixed resolves to the next occurrence within 0-6 days (today if target is today).

        Args:
            match (re.Match): The regex match containing weekday information in named groups

        Returns:
            datetime | None: The resolved datetime, or None if no weekday group matched
        """
        groups = match.groupdict()
        weekday_str = groups.get("weekday") or groups.get("bare_weekday")
        if not weekday_str:
            return None

        target = _WEEKDAY_TO_NUM[weekday_str.lower()]
        now = datetime.now(self.tz)
        current = now.weekday()
        modifier = (groups.get("weekday_modifier") or "").lower()

        if modifier == "last":
            # Always prior week's occurrence, even if target == current day
            days_back = (current - target) % 7 or 7
            return now - timedelta(days=days_back)
        if modifier == "next":
            # Always next week's occurrence, even if target == current day
            days_fwd = (target - current) % 7 or 7
            return now + timedelta(days=days_fwd)
        if modifier == "this":
            # This calendar week's occurrence; today if target == current day
            return now + timedelta(days=(target - current) % 7)
        # Bare weekday — same as "next": always future
        return now + timedelta(days=(target - current) % 7 or 7)

    def _handle_relative_count(self, match: re.Match) -> datetime | None:  # noqa: PLR0911
        """Resolve N-unit-ago / in-N-unit / N-unit-from-now expressions to a datetime.

        Compute a concrete datetime by offsetting the current time by N of the matched unit (days, weeks, months, years). Direction is determined by presence of the `rel_ago` named group: if set, subtracts; otherwise (for "in" and "from now") adds. Invalid target dates (e.g., Feb 29 + 1 year in a non-leap year) resolve to None.

        Args:
            match (re.Match): The regex match containing rel_count, rel_unit, and optionally rel_ago

        Returns:
            datetime | None: The resolved datetime, or None if no relative-count groups matched or the target date is invalid
        """
        groups = match.groupdict()
        if not (count := groups.get("rel_count")) or not (unit := groups.get("rel_unit")):
            return None

        n = int(count)
        sign = -1 if groups.get("rel_ago") else 1
        unit_lower = unit.lower().rstrip("s")
        now = datetime.now(self.tz)

        if unit_lower == "day":
            return now + timedelta(days=n * sign)
        if unit_lower == "week":
            return now + timedelta(weeks=n * sign)

        try:
            if unit_lower == "month":
                return self._offset_months(now, n * sign)
            if unit_lower == "year":
                return now.replace(year=now.year + (n * sign))
        except ValueError:
            # Target day-of-month does not exist in resolved month/year
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
        """Parse a month string or quarter designator from a regex match into a numeric month (1-12).

        Convert quarter designators (e.g. "Q2" → 4), text month names (e.g. "January", "Feb"), and numeric months from the regex match. Text matching is case-insensitive.

        Args:
            match (re.Match): The regex match containing month or quarter information in named groups

        Returns:
            int: The numeric month value (1-12)
        """
        if quarter := match.groupdict().get("quarter"):
            q = int(quarter[-1])
            return (q - 1) * 3 + 1  # Q1→1, Q2→4, Q3→7, Q4→10

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
