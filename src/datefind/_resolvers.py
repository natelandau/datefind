"""Turn the named groups of one date-pattern match into a calendar date.

Each resolver handles one kind of match and receives the reference day instead of reading the clock, so callers control what "today" means. Resolvers work on dates, not datetimes, so no result can carry a time of day.
"""

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Literal, Protocol, TypeAlias

import regex as re

from datefind._fragments import ORDINAL_DAY_NUMBERS, PERIOD_MODIFIER_OFFSETS, SEP_CLASS

MatchGroups: TypeAlias = Mapping[str, str | None]
TimeUnit: TypeAlias = Literal["day", "week", "month", "year"]
# How much of the date the matched text pins down. A counted offset such as "3 months ago"
# lands on one day; a named period such as "last month" names only the month.
DatePrecision: TypeAlias = Literal[TimeUnit, "quarter"]
Direction: TypeAlias = Literal[-1, 1]


class Resolver(Protocol):
    """Turn the named groups of one pattern's match into a date, or None when the text is not a real date."""

    def __call__(self, *, groups: MatchGroups, today: date) -> date | None: ...


# Keyed by the first three letters, which identify every weekday name and abbreviation
_WEEKDAY_NUMBERS: dict[str, int] = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}

# Keyed by the first three letters, which identify every month name and abbreviation
_MONTH_NUMBERS: dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

_DAY_WORD_OFFSETS: dict[str, int] = {"yesterday": -1, "today": 0, "tomorrow": 1}
_SEPARATORS_AND_APOSTROPHES = re.compile(rf"{SEP_CLASS}|'")
# Case-insensitive matching treats these as ASCII letters, but str.lower() does not
_LOOKALIKE_LETTERS = str.maketrans({"\u017f": "s", "\u0130": "i"})


def _lookup_word(table: Mapping[str, int], text: str, prefix_length: int | None = None) -> int:
    """Look up matched word text in a table keyed by lowercase ASCII words.

    Normalize the text the same way for every table: lowercase it, remove separators and apostrophes, and fold look-alike letters to ASCII. Every word lookup goes through here so that text the regex accepts always has a key.

    Args:
        table: The lookup table.
        text: The matched text, such as "Last-week's" or "Twenty first".
        prefix_length: Look up only this many leading characters of the normalized text. Defaults to the whole text.

    Returns:
        int: The table value for the word.

    Raises:
        RuntimeError: If the normalized text has no key, which means a pattern and its table disagree.
    """
    without_separators = _SEPARATORS_AND_APOSTROPHES.sub(repl="", string=text)
    key = without_separators.translate(_LOOKALIKE_LETTERS).lower()[:prefix_length]
    if key not in table:
        msg = f"Expected a known word for {text!r}, got key {key!r}"
        raise RuntimeError(msg)
    return table[key]


def _offset_months(today: date, months: int) -> date:
    """Offset a date by whole months, carrying across year boundaries.

    Args:
        today: The date to offset.
        months: The number of months to offset by. Positive shifts forward, negative backward.

    Returns:
        date: The offset date.

    Raises:
        ValueError: If the target day does not exist in the target month, such as January 31 plus one month.
    """
    year_offset, month_zero = divmod(today.month - 1 + months, 12)
    return today.replace(year=today.year + year_offset, month=month_zero + 1)


def _shift(today: date, unit: TimeUnit, amount: int) -> date | None:
    """Offset a date by a count of one time unit, or give None when the target is not a real date.

    Args:
        today: The date to offset.
        unit: The time unit of the offset.
        amount: The number of units to offset by. Positive shifts forward, negative backward.

    Returns:
        date | None: The offset date, or None if the target date does not exist or is out of range.
    """
    try:
        match unit:
            case "day":
                return today + timedelta(days=amount)
            case "week":
                return today + timedelta(weeks=amount)
            case "month":
                return _offset_months(today=today, months=amount)
            case "year":
                return today.replace(year=today.year + amount)
    except (ValueError, OverflowError):
        return None


def _required_group(groups: MatchGroups, name: str) -> str:
    """Read a group that the matched pattern always captures.

    Args:
        groups: The named groups of the match.
        name: The group name.

    Returns:
        str: The captured text.

    Raises:
        RuntimeError: If the group is empty, which means a pattern and its resolver disagree.
    """
    if not (value := groups.get(name)):
        msg = f"Expected group {name!r} in the match, got {value!r}"
        raise RuntimeError(msg)
    return value


# A two-digit year lands within this many years of the reference year
_TWO_DIGIT_YEAR_WINDOW = 50


def expand_two_digit_year(two_digit_year: int, reference_year: int) -> int:
    """Pick the century that puts a two-digit year within 50 years of the reference year, the rule dateutil uses.

    Args:
        two_digit_year: The year as written, from 0 to 99.
        reference_year: The year of the reference day.

    Returns:
        int: The four-digit year.
    """
    year = reference_year - reference_year % 100 + two_digit_year
    if year >= reference_year + _TWO_DIGIT_YEAR_WINDOW:
        return year - 100
    if year < reference_year - _TWO_DIGIT_YEAR_WINDOW:
        return year + 100
    return year


def _year_number(groups: MatchGroups, today: date) -> int | None:
    """Read the year, giving a two-digit year the century closest to `today`."""
    if year := groups.get("year"):
        if len(year) == 2:  # noqa: PLR2004
            return expand_two_digit_year(two_digit_year=int(year), reference_year=today.year)
        return int(year)
    return None


def _month_number(groups: MatchGroups) -> int | None:
    """Read the month from a quarter, a month name, or a month number."""
    if quarter := groups.get("quarter"):
        return (int(quarter[-1]) - 1) * 3 + 1
    if month_name := groups.get("month_name"):
        return _lookup_word(table=_MONTH_NUMBERS, text=month_name, prefix_length=3)
    if month := groups.get("month"):
        return int(month)
    return None


def _day_number(groups: MatchGroups) -> int | None:
    """Read the day from an ordinal word or a day number."""
    if ordinal_day := groups.get("ordinal_day"):
        return _lookup_word(table=ORDINAL_DAY_NUMBERS, text=ordinal_day)
    if day := groups.get("day"):
        return int(day)
    return None


def resolve_calendar_date(groups: MatchGroups, today: date) -> date | None:
    """Build an explicit calendar date, filling a missing part from the reference day.

    A missing day becomes the first of the month. A missing month or year comes from `today`.

    Args:
        groups: The named groups of the match.
        today: The reference day.

    Returns:
        date | None: The date, or None if the parts do not form a real date, such as February 30.
    """
    try:
        return date(
            year=_year_number(groups=groups, today=today) or today.year,
            month=_month_number(groups) or today.month,
            day=_day_number(groups) or 1,
        )
    except ValueError:
        return None


def resolve_weekday(groups: MatchGroups, today: date) -> date:
    """Resolve a weekday, with or without a `last`, `this`, or `next` modifier.

    `last` gives the prior occurrence, never today. `this` gives the next occurrence within 0-6 days, so today counts. `next`, and no modifier, give the next occurrence, never today.

    Args:
        groups: The named groups of the match.
        today: The reference day.

    Returns:
        date: The resolved date.
    """
    weekday = _required_group(groups=groups, name="weekday")
    target = _lookup_word(table=_WEEKDAY_NUMBERS, text=weekday, prefix_length=3)
    current = today.weekday()
    modifier = groups.get("weekday_modifier")
    direction = _lookup_word(table=PERIOD_MODIFIER_OFFSETS, text=modifier) if modifier else 1

    if direction < 0:
        # `or 7` forces a full-week jump when target == current
        return today - timedelta(days=(current - target) % 7 or 7)
    if direction == 0:
        return today + timedelta(days=(target - current) % 7)
    return today + timedelta(days=(target - current) % 7 or 7)


def relative_word_resolver(unit: TimeUnit) -> Resolver:
    """Create a resolver for relative words of one unit, such as "yesterday" or "next month".

    Args:
        unit: The time unit the words of this pattern refer to.

    Returns:
        Resolver: A resolver that offsets the reference day by the word's amount of `unit`.
    """
    base_offsets = (
        _DAY_WORD_OFFSETS
        if unit == "day"
        else {f"{modifier}{unit}": amount for modifier, amount in PERIOD_MODIFIER_OFFSETS.items()}
    )
    # Possessive and plural forms ("today's", "last weeks") normalize to a trailing "s"
    offsets = base_offsets | {f"{word}s": amount for word, amount in base_offsets.items()}

    def resolve(groups: MatchGroups, today: date) -> date | None:
        word = _required_group(groups=groups, name="relative_word")
        return _shift(today=today, unit=unit, amount=_lookup_word(table=offsets, text=word))

    return resolve


def relative_count_resolver(unit: TimeUnit, direction: Direction) -> Resolver:
    """Create a resolver for counted offsets of one unit, such as "3 days ago" or "in 2 weeks".

    Args:
        unit: The time unit the count refers to.
        direction: -1 for past offsets ("ago"), 1 for future offsets ("in", "from now").

    Returns:
        Resolver: A resolver that offsets the reference day by the matched count of `unit`.
    """

    def resolve(groups: MatchGroups, today: date) -> date | None:
        try:
            count = int(_required_group(groups=groups, name="rel_count"))
        except ValueError:
            # Counts past Python's integer string conversion limit
            return None
        return _shift(today=today, unit=unit, amount=count * direction)

    return resolve
