"""Define the ordered table of date patterns and the combined regex built from it.

Table order is alternation order in the combined regex, which decides the winner when two patterns can match at the same position.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from itertools import groupby
from typing import Literal, TypeAlias

import regex as re

from datefind._fragments import (
    DAY_AFTER_TOMORROW,
    DAY_BEFORE_YESTERDAY,
    DD,
    DD_FLEXIBLE,
    DIGIT_SUFFIXES,
    MM,
    MM_FLEXIBLE,
    MONTH,
    ORDINAL_DAY_WORDS,
    ORDINAL_DAY_WORDS_IN_ORDER,
    PERIOD_MODIFIER_OFFSETS,
    SEP_CHARS_REGEX,
    SEP_CLASS,
    SEP_CLASS_WITHOUT_COMMA,
    SEP_CLASS_WITHOUT_HYPHEN,
    TIME_OF_DAY,
    TODAY,
    TOMORROW,
    UNAMBIGUOUS_WEEKDAYS,
    WEAK_SEP_CLASS,
    WEEKDAYS,
    YESTERDAY,
    YYYY,
    YYYY_FLEXIBLE,
    YYYY_NARROW,
    YYYY_NARROW_FLEXIBLE,
    FirstNumber,
)
from datefind._resolvers import (
    TIME_UNITS,
    DatePrecision,
    Direction,
    Resolver,
    TimeUnit,
    part_of_year_resolver,
    relative_count_resolver,
    relative_word_resolver,
    resolve_calendar_date,
    resolve_iso_week,
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
# Digits after a date that are a time ("Jan 5 10:30", "2024-01-05, 3pm") are not part of a
# longer number, so they do not stop the date from matching. Comes right before a check for
# a following digit.
_UNLESS_TIME_FOLLOWS = rf"(?![\s,@]+{TIME_OF_DAY})"
# Rejects a date that runs into more digits
END = rf"(?![0-9]|{_UNLESS_TIME_FOLLOWS}{SEP_CLASS}[0-9])"
REQUIRED_SEPARATOR = rf"{WEAK_SEP_CLASS}+?"
MIXED_SEPARATOR = rf"{SEP_CLASS}+?"
# A separator with / - or . marks a numeric year clearly enough for years outside 1900 to 2099.
# Spaces and commas alone also divide counts in prose, as in "10 2500 sold".
YEAR_MARKING_SEPARATOR = rf"{SEP_CHARS_REGEX}[-/.]{SEP_CHARS_REGEX}"
MONTH_DAY_SEPARATOR = rf"{SEP_CHARS_REGEX}(?:the|of)?{SEP_CHARS_REGEX}"
# A day number before a month name starts a day-first date ("Jan 28 - 3 Feb")
_NOT_BEFORE_MONTH_NAME = rf"(?!{MONTH_DAY_SEPARATOR}(?:{MONTH}))"
# A two-digit year after a month name and day is not the end of a four-digit year ("March
# 2025" is not March 20, 25), minutes ("Feb 10:00"), an hour ("Jan 5 10pm"), or the day of
# a later date ("Jan 5 - 10 March"). A letter after it makes a decade ("Jan 5 '90s").
# An apostrophe can mark a two-digit year ("Jan 5 '24").
YEAR_AFTER_MONTH_DAY_GROUP = rf"(?:(?P<year>{YYYY})|(?<!\d|:)'?(?!{TIME_OF_DAY})(?P<year>\d\d)(?!\p{{L}}){_NOT_BEFORE_MONTH_NAME})"
# A two-digit year marked by an apostrophe ("Q4 '23", "Jan '24"). A letter after it makes a
# decade ("the '90s").
APOSTROPHE_YEAR_GROUP = r"'(?P<year>\d\d)(?![\d\p{L}])"
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
# A range of days in one month ("Jan 5-10, 2024", "March 1 - 3", "Jan 5 to 10") matches so
# that no part of it reads as a date, and resolves to no date. A hyphen between month and day
# ("Jan-05-24") or a zero-padded day ("Jan 05-24") makes a hyphen after the day a date
# separator instead. A month name after the second day ("Jan 28 - 3 Feb") makes two dates.
_DAY_RANGE_END = rf"""
    (?<=\p{{L}}{SEP_CLASS_WITHOUT_HYPHEN}+(?:(?:the|of){SEP_CLASS_WITHOUT_HYPHEN}+)?(?:[12]\d|3[01]|[1-9])(?:{DIGIT_SUFFIXES})?)
    (?:\s*-\s*|\s+(?:to|through|thru)\s+)
    (?P<range_end_day>{DD_FLEXIBLE})(?:{DIGIT_SUFFIXES})?
    {_NOT_BEFORE_MONTH_NAME}
    (?:{MONTH_DAY_SEPARATOR}{YEAR_GROUP})?
"""
# Month-first patterns skip START, which would reject a month name that follows a
# number, as in "item 5 January 3, 2024". A year glued to the day ("March 31999") is
# only a position in a digit run, so it takes the narrow compact range.
MONTH_DD_YYYY = rf"""
    {MONTH_NAME_GROUP}
    {MONTH_DAY_SEPARATOR}
    {DAY_OR_ORDINAL_DAY_GROUP}
    (?:
        {_DAY_RANGE_END}
        |{MONTH_DAY_SEPARATOR}(?<!\d){YEAR_AFTER_MONTH_DAY_GROUP}
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
# A number after the month belongs to a month-first date ("5 January 3, 2024") or a
# year, so the day-first reading stops before it. "may" is also a verb ("option 2 may
# work"), so a bare number before it needs an ordinal or "the" / "of" to count as a day.
# A day can also name its month relative to the reference day ("3rd of next month"). A bare
# number before a possessive ("page 2 of this month's issue") counts items, not days.
DD_MONTH = rf"""
    {START}
    (?:
        {DAY_OR_ORDINAL_DAY_GROUP}
        (?:
            {MONTH_DAY_SEPARATOR}(?!may(?!\p{{L}})){MONTH_NAME_GROUP}
            |(?:(?<=\p{{L}})|(?!{SEP_CLASS}+of{SEP_CLASS}+(?:{PERIOD_MODIFIER}){SEP_CLASS}+month'))
                {SEP_CLASS}+of{SEP_CLASS}+(?P<month_modifier>{PERIOD_MODIFIER}){SEP_CLASS}+month
        )
        |(?:(?P<day>{DD_FLEXIBLE})(?:{DIGIT_SUFFIXES})|{ORDINAL_DAY_GROUP})
            {MONTH_DAY_SEPARATOR}(?P<month_name>may)
        |(?P<day>{DD_FLEXIBLE}){SEP_CHARS_REGEX}(?:the|of){SEP_CHARS_REGEX}(?P<month_name>may)
    )
    (?!\p{{L}}|{_UNLESS_TIME_FOLLOWS}{SEP_CHARS_REGEX}\d)
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
    (?:{YEAR_GROUP}|{APOSTROPHE_YEAR_GROUP})
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
BARE_WEEKDAY_PATTERN_NAME = "bare_weekday"
BARE_WEEKDAY = rf"""
    {START}
    (?<![\w'])(?P<weekday>{UNAMBIGUOUS_WEEKDAYS})(?!\w)
    {END}
"""

# Relative words, grouped by the unit they offset, in alternation order
_RELATIVE_WORDS_BY_UNIT: tuple[tuple[TimeUnit, str], ...] = (
    ("day", f"{TODAY}|{YESTERDAY}|{TOMORROW}|{DAY_AFTER_TOMORROW}|{DAY_BEFORE_YESTERDAY}"),
    *(
        (unit, rf"(?:{PERIOD_MODIFIER}){SEP_CHARS_REGEX}{unit}'?s?")
        for unit in TIME_UNITS
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


PartOfYearKind: TypeAlias = Literal["quarter", "half"]


@dataclass(frozen=True, slots=True)
class PartOfYear:
    """How one kind of part of a year is written and how long it is.

    Attributes:
        letter: The letter before the part number, as in "Q3", in lowercase.
        letter_after_number: The regex for the letter after the part number, as in "3Q".
        numbers: The regex for the part numbers.
        parts_per_year: How many parts make a year, which limits the ordinal words ("fourth quarter").
        months_per_part: How many months each part covers.
        any_year_range: Whether a year from 1000 to 2999 can follow the letter-first form ("Q2 1500"). Otherwise the year must be from 1900 to 2099, because the number is more often a count ("H2 1000 kg").
    """

    letter: str
    letter_after_number: str
    numbers: str
    parts_per_year: int
    months_per_part: Literal[3, 6]
    any_year_range: bool


PARTS_OF_YEAR: dict[PartOfYearKind, PartOfYear] = {
    "quarter": PartOfYear(
        letter="q",
        letter_after_number="q",
        numbers="[1-4]",
        parts_per_year=4,
        months_per_part=3,
        any_year_range=True,
    ),
    "half": PartOfYear(
        letter="h",
        # Only a capital H: a lowercase h after a number is an hour ("1h30", "2h of downtime")
        letter_after_number="(?-i:H)",
        numbers="[12]",
        parts_per_year=2,
        months_per_part=6,
        any_year_range=False,
    ),
}
_PART_OF_YEAR_RESOLVERS: dict[PartOfYearKind, Resolver] = {
    kind: part_of_year_resolver(part.months_per_part) for kind, part in PARTS_OF_YEAR.items()
}
_PART_LETTERS = "".join(part.letter for part in PARTS_OF_YEAR.values())
# The end of a letter-first part that can take any year from 1000 to 2999 ("Q2"). Number-first
# and word forms ("4Q 1500 units", "4th quarter 1500 fans") are more often followed by a count.
_ANY_YEAR_RANGE_PART_ENDS = "|".join(
    rf"{part.letter}\d" for part in PARTS_OF_YEAR.values() if part.any_year_range
)


def _part_of_year_member(kind: PartOfYearKind) -> str:
    """Match one kind of part of a year without its year, as in "Q3", "3Q", or "third quarter".

    Args:
        kind: Which part of a year to match.

    Returns:
        str: The regex for the part.
    """
    part = PARTS_OF_YEAR[kind]
    number = f"(?P<part_number>{part.numbers})"
    ordinal_words = "|".join(ORDINAL_DAY_WORDS_IN_ORDER[: part.parts_per_year])
    return rf"""(?:
        {part.letter}{number}
        |{number}{part.letter_after_number}
        |(?:{number}(?:{DIGIT_SUFFIXES})|(?P<part_ordinal>{ordinal_words})){SEP_CLASS}+{kind}
    )"""


_ISO_WEEK_NUMBER = r"5[0-3]|[1-4]\d|0[1-9]"
# An ISO week is a part of a year too, so it shares the part-of-year families and their scan cost.
# A bare "W" needs a two-digit week, as ISO 8601 writes it, so tax forms ("W2 2024") do not match.
# After the year, a hyphen starts a day within the week ("2024-W23-2"), which is not matched.
_ISO_WEEK_MEMBERS: dict[str, str] = {
    "part_year": (
        rf"w(?:eek{SEP_CLASS}+(?P<iso_week>{_ISO_WEEK_NUMBER}|[1-9])|(?P<iso_week>{_ISO_WEEK_NUMBER}))"
    ),
    "year_part": rf"w(?P<iso_week>{_ISO_WEEK_NUMBER})(?!-)",
}


def _part_year_pattern(parts: str) -> str:
    """Match a part of a year before its year, such as "Q3 2024", "H1'24", "1H24", "third quarter of 2024", or "week 23 2024".

    Only a letter-first part whose kind allows any year range, divided from its year without a comma, takes a year from 1000 to 2999 ("Q2 1500"). Other parts, and parts followed by a comma, take the narrow year range, because the number is more often a count ("H2 1000 kg", "in week 3, 1500 users"). A two-digit year can be glued only to a number-first part ("4Q23"), because "Q423" could also be a quarter and a longer number.

    The pattern skips START, so a number before the part ("table 3 week 12 2024") does not stop it. Its own guard rejects a part inside a longer word.

    Args:
        parts: The alternation of part kinds, each in its own pattern group.

    Returns:
        str: The regex for the part and year.
    """
    # Letters before the part belong to a longer word ("CH1") and "<" or "</" to an HTML tag ("<h1")
    return rf"""
    (?<![\w<]|</)
    {parts}
    (?:
        (?<={_ANY_YEAR_RANGE_PART_ENDS})(?:{SEP_CLASS_WITHOUT_COMMA}+of)?{SEP_CLASS_WITHOUT_COMMA}+?(?<!\d){YEAR_GROUP}
        |(?:{SEP_CLASS}+of)?{SEP_CHARS_REGEX}(?<!\d){YEAR_NARROW_GROUP}
        |{SEP_CHARS_REGEX}{APOSTROPHE_YEAR_GROUP}
        |(?<=[{_PART_LETTERS}]\d){YEAR_NARROW_GROUP}
        |(?<=\d[{_PART_LETTERS}])(?P<year>\d\d)(?!\p{{L}})
    )
    {END}
"""


def _year_part_pattern(parts: str) -> str:
    """Match a year before a part of that year, such as "2024 Q3", "2024-H1", or "2024-W23".

    Args:
        parts: The alternation of part kinds, each in its own pattern group.

    Returns:
        str: The regex for the year and part.
    """
    # A digit glued to the year belongs to a longer number ("20243Q"), not to the part
    return rf"""
    {START}
    {YEAR_GROUP}
    {SEP_CHARS_REGEX}
    (?:(?<!\d)|(?=\p{{L}}))
    {parts}(?!\w)
    {END}
"""


# Each family compiles into one shared pattern with one table entry, and one group, per unit.
# Compiling each unit as its own top-level alternative makes the scan many times slower.
_FAMILY_PATTERNS: dict[str, Callable[[str], str]] = {
    "relative_word": _relative_word_pattern,
    "count_ago": _count_ago_pattern,
    "count_in": _count_in_pattern,
    "count_from_now": _count_from_now_pattern,
    "part_year": _part_year_pattern,
    "year_part": _year_part_pattern,
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

    Mixing adjacent and separated parts is rejected so a run like "3, 2024" is not split into 3/20/24. Parts divided by / - or . take the year from `parts`; a digit run, or parts divided only by other separators such as spaces, take `narrow_year`. Parts divided by a mix of both ("12/25, 2024") need a year from 1900 to 2099.

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
        join(MIXED_SEPARATOR, parts | {"year": YEAR_NARROW_GROUP}),
    ]
    # A two-digit year after mixed separators is another number ("3.8, 10", "pages 3-8, 10")
    if narrow_year != YEAR_NARROW_GROUP:
        alternatives.append(join(REQUIRED_SEPARATOR, narrow_parts))
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
        precision: How much of the date the matched text pins down.
        family: The shared pattern this entry belongs to, if any. Consecutive members of a family compile into one shared pattern.
    """

    name: str
    regex: str
    resolver: Resolver
    precision: DatePrecision
    family: str | None = None

    @property
    def group_name(self) -> str:
        """Name of the group that wraps this pattern in the combined regex."""
        return f"pattern_{self.name}"

    @property
    def names_calendar_day(self) -> bool:
        """Whether the match names one calendar day, so a weekday or an offset before it belongs to the date.

        Examples: "Friday, January 5, 2024" and "2 weeks after Jan 5, 2024".
        """
        return self.resolver is resolve_calendar_date and self.precision == "day"


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
        DatePattern(
            name="day_month_year",
            regex=DD_MONTH_YYYY,
            resolver=resolve_calendar_date,
            precision="day",
        ),
        DatePattern(
            name="month_day_year",
            regex=MONTH_DD_YYYY,
            resolver=resolve_calendar_date,
            precision="day",
        ),
        DatePattern(
            name="year_month_day",
            regex=YYYY_MONTH_DD,
            resolver=resolve_calendar_date,
            precision="day",
        ),
        DatePattern(
            name="month_day", regex=MONTH_DD, resolver=resolve_calendar_date, precision="day"
        ),
        DatePattern(
            name="day_month", regex=DD_MONTH, resolver=resolve_calendar_date, precision="day"
        ),
        DatePattern(
            name="year_month", regex=YYYY_MONTH, resolver=resolve_calendar_date, precision="month"
        ),
        DatePattern(
            name="month_year", regex=MONTH_YYYY, resolver=resolve_calendar_date, precision="month"
        ),
        *(
            DatePattern(
                name=f"relative_{unit}_word",
                regex=words,
                resolver=relative_word_resolver(unit),
                precision=unit,
                family="relative_word",
            )
            for unit, words in _RELATIVE_WORDS_BY_UNIT
        ),
        *(
            DatePattern(
                name=f"{family}_{unit}",
                regex=f"{unit}s?",
                resolver=relative_count_resolver(unit=unit, direction=direction),
                precision="day",
                family=family,
            )
            for family, direction in _COUNT_DIRECTIONS.items()
            for unit in TIME_UNITS
        ),
        *(
            pattern
            for family in ("part_year", "year_part")
            for pattern in (
                *(
                    DatePattern(
                        name=f"{family}_{kind}",
                        regex=_part_of_year_member(kind),
                        resolver=_PART_OF_YEAR_RESOLVERS[kind],
                        precision=kind,
                        family=family,
                    )
                    for kind in PARTS_OF_YEAR
                ),
                DatePattern(
                    name=f"{family}_iso_week",
                    regex=_ISO_WEEK_MEMBERS[family],
                    resolver=resolve_iso_week,
                    precision="week",
                    family=family,
                ),
            )
        ),
        DatePattern(
            name="modified_weekday",
            regex=MODIFIED_WEEKDAY,
            resolver=resolve_weekday,
            precision="day",
        ),
        DatePattern(
            name="numeric_year_first",
            regex=_numeric_pattern(
                order=year_first,
                parts=_STRICT_PARTS,
                narrow_year=YEAR_NARROW_GROUP,
                include_compact=True,
            ),
            resolver=resolve_calendar_date,
            precision="day",
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
            precision="day",
        ),
        DatePattern(
            name="numeric_year_month",
            regex=_year_month_pattern(year_first=True, include_compact=short_digit_dates),
            resolver=resolve_calendar_date,
            precision="month",
        ),
        DatePattern(
            name="numeric_month_year",
            regex=_year_month_pattern(year_first=False, include_compact=short_digit_dates),
            resolver=resolve_calendar_date,
            precision="month",
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
            precision="day",
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
            precision="day",
        ),
        DatePattern(
            name=BARE_WEEKDAY_PATTERN_NAME,
            regex=BARE_WEEKDAY,
            resolver=resolve_weekday,
            precision="day",
        ),
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
