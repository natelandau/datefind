"""Scan text with the combined date regex and resolve each match."""

from collections.abc import Generator
from dataclasses import dataclass
from datetime import date, datetime, time, tzinfo

from datefind._fragments import FirstNumber
from datefind._patterns import compile_date_regex, pattern_table


@dataclass
class FoundDate:
    """Store information about a date found in text.

    Attributes:
        datetime (datetime): The parsed datetime object
        match (str): The specific text that matched the date pattern
        span (tuple[int, int]): The start and end positions of the match in the text
    """

    datetime: datetime
    match: str
    span: tuple[int, int]


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


def search_dates(
    text: str, tz: tzinfo, first: FirstNumber, now: date | None, *, short_digit_dates: bool
) -> Generator[FoundDate, None, None]:
    """Yield every date in the text as midnight in `tz`, with relative dates resolved against `now`.

    Matches that look like dates but are not real dates, such as February 30, are skipped.

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

    for match in regex.finditer(text):
        groups = match.groupdict()
        # match.lastgroup is unreliable here: the patterns share inner group names
        pattern = next((p for p in patterns if groups[p.group_name] is not None), None)
        if pattern is None:
            msg = f"Expected one pattern group to match {match.group()!r}, got none"
            raise RuntimeError(msg)
        resolved = pattern.resolver(groups=groups, today=today)
        if resolved is not None:
            yield FoundDate(
                datetime=_midnight(day=resolved, tz=tz),
                match=match.group(),
                span=match.span(),
            )
