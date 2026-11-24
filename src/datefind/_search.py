"""Scan text with the combined date regex and resolve each match."""

from collections.abc import Generator
from dataclasses import dataclass
from datetime import date, datetime, time, tzinfo

import regex as re

from datefind._fragments import (
    ASCII_EQUIVALENTS,
    SEP_CLASS,
    UNAMBIGUOUS_WEEKDAYS,
    WEEKDAY_ABBREVIATIONS_THAT_ARE_WORDS,
    FirstNumber,
)
from datefind._patterns import BARE_WEEKDAY_PATTERN_NAME, compile_date_regex, pattern_table
from datefind._resolvers import TIME_UNITS, DatePrecision, offset_date, weekday_number

# A standalone "v" or "version" marks a version number ("v2.1.1500"), not a date. Checked
# per match rather than inside the date regex, where the lookbehind slows every scan.
_VERSION_PREFIX = re.compile(
    pattern=rf"(?<!\p{{L}})(?:v|version){SEP_CLASS}{{0,2}}\Z", flags=re.IGNORECASE
)
# Long enough to hold "version" and two separators
_VERSION_PREFIX_WINDOW = 9
# A weekday right before a date, as in "Friday, January 5" or "Wed, the 3rd of January". Checked
# per match rather than as an optional prefix in the date regex, which slows every scan. "wed",
# "sat", and "sun" are also English words ("we sat 2 days"), so they need a "," or "." after them.
_WEEKDAY_PREFIX = re.compile(
    pattern=rf"""
        (?<![\w'])
        (?:
            (?P<weekday>{UNAMBIGUOUS_WEEKDAYS})(?!\p{{L}}){SEP_CLASS}+
            |(?P<weekday>{WEEKDAY_ABBREVIATIONS_THAT_ARE_WORDS})[.,]{SEP_CLASS}*
        )
        (?:the{SEP_CLASS}+)?
        \Z
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)
# Long enough to hold "wednesday", "the", and a few separators
_WEEKDAY_PREFIX_WINDOW = 20
# A counted offset right before a date, as in "2 weeks after Jan 5, 2024"
_OFFSET_PREFIX = re.compile(
    pattern=rf"""
        (?<![\w.])
        (?P<count>\d{{1,4}}){SEP_CLASS}+
        (?P<unit>{"|".join(f"{unit}s?" for unit in TIME_UNITS)}){SEP_CLASS}+
        (?P<direction>after|before|from){SEP_CLASS}+
        (?:the{SEP_CLASS}+)?
        \Z
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)
# Long enough to hold a four-digit count, "months", "before", "the", and separators
_OFFSET_PREFIX_WINDOW = 28
# "from" before a date that starts a range ("3 years from 2020-01-01 to 2023-01-01") names
# the range's first day, not an offset
_RANGE_CONTINUES = re.compile(
    pattern=r"[\s,]*(?:-|(?:to|until|till|through|thru)(?!\p{L}))", flags=re.IGNORECASE
)


@dataclass
class FoundDate:
    """Store information about a date found in text.

    Attributes:
        datetime (datetime): The parsed datetime object
        match (str): The specific text that matched the date pattern
        span (tuple[int, int]): The start and end positions of the match in the text
        precision (DatePrecision): The unit of time the text names: "day", "week", "month", "quarter", "half", or "year". An explicit period returns its first day ("March 2025" gives March 1). A period relative to the reference day returns the day one period away ("next month" on November 23 gives December 23)
    """

    datetime: datetime
    match: str
    span: tuple[int, int]
    precision: DatePrecision = "day"


def reference_day(now: date | None, tz: tzinfo) -> date:
    """Find the calendar day in `tz` that relative dates resolve against.

    Args:
        now: The reference date. An aware datetime is converted to `tz`, and a naive one is read as a wall-clock time in `tz`. Defaults to the current time.
        tz: The timezone that decides which calendar day an aware or default `now` falls on.

    Returns:
        date: The reference day in `tz`.
    """
    if now is None:
        return datetime.now(tz).date()
    if isinstance(now, datetime):
        return now.astimezone(tz).date() if now.utcoffset() is not None else now.date()
    return now


def _midnight(day: date, tz: tzinfo) -> datetime:
    """Build the first moment of `day` in `tz`, with the offset that applies on that day.

    Args:
        day: The calendar day.
        tz: The timezone of the result.

    Returns:
        datetime: Midnight of `day` in `tz`.
    """
    naive = datetime.combine(day, time())
    # pytz zones attach their earliest historical offset (often LMT) unless they localize the time
    localize = getattr(tz, "localize", None)
    if callable(localize):
        return localize(naive)
    return naive.replace(tzinfo=tz)


def _follows_version_prefix(text: str, start: int) -> bool:
    """Check whether a match starting at `start` is a version number such as "v2.1.1500".

    Args:
        text: The text being searched.
        start: Where the match begins.

    Returns:
        bool: True when the match starts with a digit right after "v" or "version".
    """
    if text[start] not in "0123456789":
        return False
    return (
        _match_ending_at(
            pattern=_VERSION_PREFIX, text=text, end=start, window=_VERSION_PREFIX_WINDOW
        )
        is not None
    )


def _match_ending_at(
    pattern: re.Pattern[str], text: str, end: int, window: int, earliest: int = 0
) -> re.Match[str] | None:
    """Search the text just before `end` for a pattern anchored to the end of the text, such as a prefix of a date.

    Args:
        pattern: The pattern to search for. It must be anchored to the end of the text to match only text that ends at `end`.
        text: The text being searched.
        end: Where the searched text ends.
        window: How many characters before `end` to search.
        earliest: The first position the match can start at.

    Returns:
        re.Match[str] | None: The match, or None when the text before `end` does not end with the pattern.
    """
    # pos, unlike slicing, lets a lookbehind see the character before the window
    return pattern.search(string=text, pos=max(earliest, end - window), endpos=end)


@dataclass(frozen=True)
class _PrefixedDay:
    """A calendar day after reading the weekday and counted offset written before it.

    Attributes:
        start: Where the date's match starts, including any weekday that agrees with it and any offset.
        claimed_start: Where the text the date accounts for starts. Differs from `start` only for a weekday that disagrees with the date, which is dropped rather than reported on its own.
        day: The date after any offset, or None when the offset lands on a day that does not exist.
    """

    start: int
    claimed_start: int
    day: date | None


def _read_prefixes(
    text: str, start: int, end: int, day: date, earliest: int, *, year_stated: bool
) -> _PrefixedDay:
    """Read a weekday ("Friday, Jan 5") and a counted offset ("2 weeks after Jan 5") before a calendar day.

    Args:
        text: The text being searched.
        start: Where the date match begins.
        end: Where the date match ends.
        day: The date the match resolves to.
        earliest: The end of the last date already yielded, so no text belongs to two dates.
        year_stated: Whether the text gives the year. Without one the year is a guess, so a weekday that disagrees with the date still belongs to it.

    Returns:
        _PrefixedDay: The date with its extended start and any offset applied.
    """
    claimed_start = start
    if weekday := _match_ending_at(
        pattern=_WEEKDAY_PREFIX,
        text=text,
        end=start,
        window=_WEEKDAY_PREFIX_WINDOW,
        earliest=earliest,
    ):
        claimed_start = weekday.start()
        if not year_stated or weekday_number(weekday.group("weekday")) == day.weekday():
            start = weekday.start()
    offset = _match_ending_at(
        pattern=_OFFSET_PREFIX,
        text=text,
        end=claimed_start,
        window=_OFFSET_PREFIX_WINDOW,
        earliest=earliest,
    )
    if offset is None or (
        offset.group("direction").lower() == "from"
        and _RANGE_CONTINUES.match(string=text, pos=end) is not None
    ):
        return _PrefixedDay(start=start, claimed_start=claimed_start, day=day)
    return _PrefixedDay(
        start=offset.start(),
        claimed_start=offset.start(),
        day=offset_date(
            day=day,
            count=offset.group("count"),
            unit=offset.group("unit"),
            direction=offset.group("direction"),
        ),
    )


def search_dates(
    text: str, tz: tzinfo, first: FirstNumber, now: date | None, *, short_digit_dates: bool
) -> Generator[FoundDate, None, None]:
    """Yield every date in the text as midnight in `tz`, with relative dates resolved against `now`.

    Matches that look like dates but are not real dates, such as February 30, are skipped. A weekday right before a date is part of that date, not a date of its own, and a weekday that disagrees with the date is dropped. A counted offset right before a date ("2 weeks after Jan 5, 2024") shifts it. Unicode spaces, dashes, apostrophes, and full-width digits match as their ASCII forms.

    Args:
        text: The text to search.
        tz: The timezone of the reference day and of every returned datetime.
        first: Which part comes first in ambiguous numeric dates such as 01/02/03.
        now: The date that relative dates such as "tomorrow" resolve against. None means the current time.
        short_digit_dates: Whether runs of 4 to 7 digits with no separators can match. 8-digit runs always can.

    Yields:
        FoundDate: Each date found, in text order.
    """
    regex = compile_date_regex(first=first, short_digit_dates=short_digit_dates)
    patterns = pattern_table(first=first, short_digit_dates=short_digit_dates)
    today = reference_day(now=now, tz=tz)
    # One character for one, so positions in `searched` are positions in `text`
    searched = text.translate(ASCII_EQUIVALENTS)

    # A bare weekday is held back until the next match shows whether it starts a longer date
    pending_weekday: FoundDate | None = None
    # End of the last yielded date that is not a bare weekday, so no weekday joins two dates
    previous_end = 0
    for match in regex.finditer(searched):
        if _follows_version_prefix(text=searched, start=match.start()):
            continue
        groups = match.groupdict()
        # match.lastgroup is unreliable here: the patterns share inner group names
        pattern = next((p for p in patterns if groups[p.group_name] is not None), None)
        if pattern is None:
            msg = f"Expected one pattern group to match {match.group()!r}, got none"
            raise RuntimeError(msg)
        resolved = pattern.resolver(groups=groups, today=today)
        if resolved is None:
            continue
        start, end = match.span()
        claimed_start = start
        if pattern.names_calendar_day:
            prefixed = _read_prefixes(
                text=searched,
                start=start,
                end=end,
                day=resolved,
                earliest=previous_end,
                year_stated=groups.get("year") is not None,
            )
            start, claimed_start, resolved = prefixed.start, prefixed.claimed_start, prefixed.day
        # A held-back weekday inside the text this date accounts for is part of the date
        if pending_weekday is not None and pending_weekday.span[0] < claimed_start:
            yield pending_weekday
        pending_weekday = None
        if resolved is None:
            previous_end = end
            continue
        found = FoundDate(
            datetime=_midnight(day=resolved, tz=tz),
            match=text[start:end],
            span=(start, end),
            precision=pattern.precision,
        )
        if pattern.name == BARE_WEEKDAY_PATTERN_NAME:
            pending_weekday = found
        else:
            previous_end = end
            yield found
    if pending_weekday is not None:
        yield pending_weekday
