"""Define the ordered table of date patterns and the combined regex built from it.

Table order is alternation order in the combined regex, which decides the winner when two patterns can match at the same position.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from itertools import groupby
from typing import get_args

import regex as re

from datefind._fragments import (
    DD,
    DD_FLEXIBLE,
    DIGIT_SUFFIXES,
    MM,
    MM_FLEXIBLE,
    MONTH,
    ORDINAL_DAY_WORDS,
    PERIOD_MODIFIER_OFFSETS,
    QUARTER,
    SEP_CHARS_REGEX,
    SEP_CLASS,
    TODAY,
    TOMORROW,
    UNAMBIGUOUS_WEEKDAYS,
    WEEKDAYS,
    YESTERDAY,
    YYYY,
    YYYY_FLEXIBLE,
    YYYY_NARROW,
    YYYY_NARROW_FLEXIBLE,
    FirstNumber,
)
from datefind._resolvers import (
    Direction,
    Resolver,
    TimeUnit,
    relative_count_resolver,
    relative_word_resolver,
    resolve_calendar_date,
    resolve_weekday,
)

DAY_GROUP = f"(?P<day>{DD})(?:{DIGIT_SUFFIXES})?"
DAY_FLEXIBLE_GROUP = f"(?P<day>{DD_FLEXIBLE})(?:{DIGIT_SUFFIXES})?"
ORDINAL_DAY_GROUP = f"(?P<ordinal_day>{ORDINAL_DAY_WORDS})"
DAY_OR_ORDINAL_DAY_GROUP = f"(?:{DAY_FLEXIBLE_GROUP}|{ORDINAL_DAY_GROUP})"
MONTH_GROUP = rf"(?P<month>{MM})"
MONTH_FLEXIBLE_GROUP = rf"(?P<month>{MM_FLEXIBLE})"
MONTH_NAME_GROUP = f"(?P<month_name>{MONTH})"
YEAR_GROUP = rf"(?P<year>{YYYY})"
YEAR_FLEXIBLE_GROUP = rf"(?P<year>{YYYY_FLEXIBLE})"
YEAR_NARROW_GROUP = rf"(?P<year>{YYYY_NARROW})"
YEAR_NARROW_FLEXIBLE_GROUP = rf"(?P<year>{YYYY_NARROW_FLEXIBLE})"
# 2-digit year alternative requires no preceding digit. Prevents MONTH_DD_YYYY from
# splitting a 4-digit year like "2025" into day=20 + 2-digit year=25.
YEAR_FLEXIBLE_NO_PREV_DIGIT_GROUP = rf"(?P<year>{YYYY}|(?<!\d)\d\d)"

END = rf"(?![0-9]|{SEP_CLASS}[0-9])"
REQUIRED_SEPARATOR = rf"{SEP_CLASS}+?"
# A separator with / - or . marks a numeric year clearly enough for years outside 1900 to 2099.
# Spaces and commas alone also divide counts in prose, as in "10 2500 sold".
YEAR_MARKING_SEPARATOR = rf"{SEP_CHARS_REGEX}[-/.]{SEP_CHARS_REGEX}"
MONTH_DAY_SEPARATOR = rf"{SEP_CHARS_REGEX}(?:the|of)?{SEP_CHARS_REGEX}"
PERIOD_MODIFIER = "|".join(PERIOD_MODIFIER_OFFSETS)
# [Qq] excluded so that a digit following an invalid quarter (e.g. "Q5 2024") cannot
# be consumed by numeric patterns like xxf_xxf_xxf.
START = rf"(?<![0-9]|[0-9]{SEP_CLASS}|[Qq])"

YYYY_MONTH_DD = rf"""
    {START}
    {YEAR_GROUP}
    {SEP_CHARS_REGEX}
    {MONTH_NAME_GROUP}
    {SEP_CHARS_REGEX}
    {DAY_OR_ORDINAL_DAY_GROUP}
    {END}
"""
DD_MONTH_YYYY = rf"""
    {START}
    {DAY_OR_ORDINAL_DAY_GROUP}
    {MONTH_DAY_SEPARATOR}
    {MONTH_NAME_GROUP}
    {MONTH_DAY_SEPARATOR}
    {YEAR_GROUP}
    {END}
"""
# Month-first patterns skip START, which would reject a month name that follows a
# number, as in "item 5 January 3, 2024". A year glued to the day ("March 31999") is
# only a position in a digit run, so it takes the narrow compact range.
MONTH_DD_YYYY = rf"""
    {MONTH_NAME_GROUP}
    {MONTH_DAY_SEPARATOR}
    {DAY_OR_ORDINAL_DAY_GROUP}
    (?:
        {MONTH_DAY_SEPARATOR}(?<!\d){YEAR_FLEXIBLE_NO_PREV_DIGIT_GROUP}
        |{YEAR_NARROW_GROUP}
    )
    {END}
"""
YYYY_MONTH = rf"""
    {START}
    {YEAR_GROUP}
    {SEP_CHARS_REGEX}
    {MONTH_NAME_GROUP}
    {END}
"""
MONTH_DD = rf"""
    {MONTH_NAME_GROUP}
    {MONTH_DAY_SEPARATOR}
    {DAY_OR_ORDINAL_DAY_GROUP}
    {END}
"""
MONTH_YYYY = rf"""
    {MONTH_NAME_GROUP}
    {MONTH_DAY_SEPARATOR}
    {YEAR_GROUP}
    {END}
"""
# A year glued to the quarter digit ("Q31500") takes the narrow year range, as in MONTH_DD_YYYY
QUARTER_YYYY = rf"""
    {START}
    (?P<quarter>{QUARTER})
    (?:
        {SEP_CHARS_REGEX}(?<!\d){YEAR_GROUP}
        |{YEAR_NARROW_GROUP}
    )
    {END}
"""
YYYY_QUARTER = rf"""
    {START}
    {YEAR_GROUP}
    {SEP_CHARS_REGEX}
    (?P<quarter>{QUARTER})
    {END}
"""
MODIFIED_WEEKDAY = rf"""
    {START}
    (?<!\w)(?P<weekday_modifier>{PERIOD_MODIFIER})
    {SEP_CHARS_REGEX}
    (?P<weekday>{WEEKDAYS})(?!\w)
    {END}
"""
# The apostrophe check keeps contractions like "c'mon" from matching
BARE_WEEKDAY = rf"""
    {START}
    (?<![\w'])(?P<weekday>{UNAMBIGUOUS_WEEKDAYS})(?!\w)
    {END}
"""

# Relative words, grouped by the unit they offset, in alternation order
_TIME_UNITS: tuple[TimeUnit, ...] = get_args(TimeUnit)
_RELATIVE_WORDS_BY_UNIT: tuple[tuple[TimeUnit, str], ...] = (
    ("day", f"{TODAY}|{YESTERDAY}|{TOMORROW}"),
    *(
        (unit, rf"(?:{PERIOD_MODIFIER}){SEP_CHARS_REGEX}{unit}'?s?")
        for unit in _TIME_UNITS
        if unit != "day"
    ),
)


def _relative_word_pattern(words: str) -> str:
    """Match relative words such as "today" or "next month" as whole words.

    Args:
        words: The alternation of relative words, each unit in its own pattern group.

    Returns:
        str: The regex for the relative words.
    """
    return rf"""
    {START}
    (?<!\w)(?P<relative_word>{words})(?!\w)
    {END}
"""


def _count_ago_pattern(units: str) -> str:
    """Match "N <unit>s ago".

    Args:
        units: The alternation of unit words, each in its own pattern group.

    Returns:
        str: The regex for the counted offset.
    """
    return rf"""
    {START}
    (?P<rel_count>\d+)
    {SEP_CHARS_REGEX}
    {units}
    {SEP_CHARS_REGEX}
    ago(?!\w)
    {END}
"""


def _count_in_pattern(units: str) -> str:
    """Match "in N <unit>s".

    Args:
        units: The alternation of unit words, each in its own pattern group.

    Returns:
        str: The regex for the counted offset.
    """
    return rf"""
    {START}
    (?<!\w)(?:in)
    {SEP_CHARS_REGEX}
    (?P<rel_count>\d+)
    {SEP_CHARS_REGEX}
    {units}(?!\w)
    {END}
"""


def _count_from_now_pattern(units: str) -> str:
    """Match "N <unit>s from now".

    Args:
        units: The alternation of unit words, each in its own pattern group.

    Returns:
        str: The regex for the counted offset.
    """
    return rf"""
    {START}
    (?P<rel_count>\d+)
    {SEP_CHARS_REGEX}
    {units}
    {SEP_CHARS_REGEX}
    (?:from{SEP_CHARS_REGEX}now)(?!\w)
    {END}
"""


# Each family compiles into one shared pattern with one table entry, and one group, per unit.
# Compiling each unit as its own top-level alternative makes the scan many times slower.
_FAMILY_PATTERNS: dict[str, Callable[[str], str]] = {
    "relative_word": _relative_word_pattern,
    "count_ago": _count_ago_pattern,
    "count_in": _count_in_pattern,
    "count_from_now": _count_from_now_pattern,
}
_COUNT_DIRECTIONS: dict[str, Direction] = {"count_ago": -1, "count_in": 1, "count_from_now": 1}

_PART_ORDER: dict[FirstNumber, tuple[str, str, str]] = {
    FirstNumber.MONTH: ("month", "day", "year"),
    FirstNumber.DAY: ("day", "month", "year"),
    FirstNumber.YEAR: ("year", "month", "day"),
}
_STRICT_PARTS: dict[str, str] = {"year": YEAR_GROUP, "month": MONTH_GROUP, "day": DAY_GROUP}
_FLEXIBLE_PARTS: dict[str, str] = {
    "year": YEAR_FLEXIBLE_GROUP,
    "month": MONTH_FLEXIBLE_GROUP,
    "day": DAY_FLEXIBLE_GROUP,
}
# A year-first date needs a four-digit year, so a leading two-digit run is never read as the year
_YEAR_FIRST_FLEXIBLE_PARTS: dict[str, str] = _FLEXIBLE_PARTS | {"year": YEAR_GROUP}


def _numeric_pattern(
    order: Sequence[str], parts: dict[str, str], narrow_year: str, *, include_compact: bool
) -> str:
    """Join numeric date parts in the given order, either all adjacent or all separated.

    Mixing adjacent and separated parts is rejected so a run like "3, 2024" is not split into 3/20/24. Parts divided by / - or . take the year from `parts`; a digit run, or parts divided only by other separators such as spaces, take `narrow_year`.

    Args:
        order: The date part names ("year", "month", "day"), in text order.
        parts: The group fragment for each part.
        narrow_year: The year group for a digit run or for parts divided only by weak separators.
        include_compact: Whether to match a digit run with no separators.

    Returns:
        str: The regex for the numeric date.
    """
    narrow_parts = parts | {"year": narrow_year}

    def join(separator: str, fragments: dict[str, str]) -> str:
        return separator.join(fragments[part] for part in order)

    alternatives = [
        *([join("", narrow_parts)] if include_compact else []),
        join(YEAR_MARKING_SEPARATOR, parts),
        join(REQUIRED_SEPARATOR, narrow_parts),
    ]
    return f"{START}(?:{'|'.join(alternatives)}){END}"


def _year_month_pattern(*, year_first: bool, include_compact: bool) -> str:
    """Match a numeric month and year, in either order, such as 2024-12 or 12/2024.

    The year is always from 1900 to 2099: without a day, two numbers divided by / - or . are as likely to be a decimal, a price, or a range ("10-1500") as a date.

    Args:
        year_first: Whether the year comes before the month.
        include_compact: Whether to match a digit run with no separators, such as 202412.

    Returns:
        str: The regex for the month and year.
    """
    # (?!\d) requires at least one separator in the separated form
    if year_first:
        compact = f"{YEAR_NARROW_GROUP}{MONTH_GROUP}"
        separated = rf"{YEAR_NARROW_GROUP}(?!\d){SEP_CHARS_REGEX}{MONTH_GROUP}"
    else:
        compact = f"{MONTH_GROUP}{YEAR_NARROW_GROUP}"
        separated = rf"{MONTH_GROUP}(?!\d){MONTH_DAY_SEPARATOR}{YEAR_NARROW_GROUP}"
    alternatives = [compact, separated] if include_compact else [separated]
    return f"{START}(?:{'|'.join(alternatives)}){END}"


@dataclass(frozen=True, slots=True)
class DatePattern:
    """One kind of date text and the resolver that turns its match into a date.

    Attributes:
        name: A unique identifier, also used to name the pattern's group in the combined regex.
        regex: The regex fragment that matches the date text. For a member of a family, only the part that differs between members.
        resolver: The function that turns the match's named groups into a date.
        family: The shared pattern this entry belongs to, if any. Consecutive members of a family compile into one shared pattern.
    """

    name: str
    regex: str
    resolver: Resolver
    family: str | None = None

    @property
    def group_name(self) -> str:
        """Name of the group that wraps this pattern in the combined regex."""
        return f"pattern_{self.name}"


@cache
def pattern_table(first: FirstNumber, *, short_digit_dates: bool) -> tuple[DatePattern, ...]:
    """Build the ordered pattern table for one reading of ambiguous numeric dates.

    Args:
        first: Which part comes first in ambiguous numeric dates such as 01/02/03.
        short_digit_dates: Whether runs of 4 to 7 digits with no separators can match. 8-digit runs always can.

    Returns:
        tuple[DatePattern, ...]: The patterns in alternation order.
    """
    order = _PART_ORDER[first]
    year_first = ["year", *(part for part in order if part != "year")]

    return (
        DatePattern(name="day_month_year", regex=DD_MONTH_YYYY, resolver=resolve_calendar_date),
        DatePattern(name="month_day_year", regex=MONTH_DD_YYYY, resolver=resolve_calendar_date),
        DatePattern(name="year_month_day", regex=YYYY_MONTH_DD, resolver=resolve_calendar_date),
        DatePattern(name="month_day", regex=MONTH_DD, resolver=resolve_calendar_date),
        DatePattern(name="year_month", regex=YYYY_MONTH, resolver=resolve_calendar_date),
        DatePattern(name="month_year", regex=MONTH_YYYY, resolver=resolve_calendar_date),
        *(
            DatePattern(
                name=f"relative_{unit}_word",
                regex=words,
                resolver=relative_word_resolver(unit),
                family="relative_word",
            )
            for unit, words in _RELATIVE_WORDS_BY_UNIT
        ),
        *(
            DatePattern(
                name=f"{family}_{unit}",
                regex=f"{unit}s?",
                resolver=relative_count_resolver(unit=unit, direction=direction),
                family=family,
            )
            for family, direction in _COUNT_DIRECTIONS.items()
            for unit in _TIME_UNITS
        ),
        DatePattern(name="quarter_year", regex=QUARTER_YYYY, resolver=resolve_calendar_date),
        DatePattern(name="year_quarter", regex=YYYY_QUARTER, resolver=resolve_calendar_date),
        DatePattern(name="modified_weekday", regex=MODIFIED_WEEKDAY, resolver=resolve_weekday),
        DatePattern(
            name="numeric_year_first",
            regex=_numeric_pattern(
                order=year_first,
                parts=_STRICT_PARTS,
                narrow_year=YEAR_NARROW_GROUP,
                include_compact=True,
            ),
            resolver=resolve_calendar_date,
        ),
        DatePattern(
            name="numeric_strict",
            regex=_numeric_pattern(
                order=order,
                parts=_STRICT_PARTS,
                narrow_year=YEAR_NARROW_GROUP,
                include_compact=True,
            ),
            resolver=resolve_calendar_date,
        ),
        DatePattern(
            name="numeric_year_month",
            regex=_year_month_pattern(year_first=True, include_compact=short_digit_dates),
            resolver=resolve_calendar_date,
        ),
        DatePattern(
            name="numeric_month_year",
            regex=_year_month_pattern(year_first=False, include_compact=short_digit_dates),
            resolver=resolve_calendar_date,
        ),
        DatePattern(
            name="numeric_year_first_flexible",
            regex=_numeric_pattern(
                order=year_first,
                parts=_YEAR_FIRST_FLEXIBLE_PARTS,
                narrow_year=YEAR_NARROW_GROUP,
                include_compact=short_digit_dates,
            ),
            resolver=resolve_calendar_date,
        ),
        DatePattern(
            name="numeric_flexible",
            regex=_numeric_pattern(
                order=order,
                parts=_FLEXIBLE_PARTS,
                narrow_year=YEAR_NARROW_FLEXIBLE_GROUP,
                include_compact=short_digit_dates,
            ),
            resolver=resolve_calendar_date,
        ),
        DatePattern(name="bare_weekday", regex=BARE_WEEKDAY, resolver=resolve_weekday),
    )


def _alternatives(table: tuple[DatePattern, ...]) -> list[str]:
    """Wrap each table entry in its named group, merging each family into its shared pattern.

    Args:
        table: The patterns in alternation order.

    Returns:
        list[str]: The top-level alternatives of the combined regex, in order.
    """
    alternatives: list[str] = []
    for family, members in groupby(iterable=table, key=lambda pattern: pattern.family):
        grouped = [f"(?P<{pattern.group_name}>{pattern.regex})" for pattern in members]
        if family is None:
            alternatives.extend(grouped)
        else:
            alternatives.append(_FAMILY_PATTERNS[family](f"(?:{'|'.join(grouped)})"))
    return alternatives


@cache
def compile_date_regex(first: FirstNumber, *, short_digit_dates: bool) -> re.Pattern[str]:
    """Compile the pattern table into one regex, each pattern in its own named group.

    Args:
        first: Which part comes first in ambiguous numeric dates such as 01/02/03.
        short_digit_dates: Whether runs of 4 to 7 digits with no separators can match. 8-digit runs always can.

    Returns:
        re.Pattern[str]: The combined regex, case-insensitive and verbose.
    """
    return re.compile(
        pattern="|".join(
            _alternatives(pattern_table(first=first, short_digit_dates=short_digit_dates))
        ),
        flags=re.IGNORECASE | re.VERBOSE | re.MULTILINE | re.UNICODE | re.DOTALL,
    )
