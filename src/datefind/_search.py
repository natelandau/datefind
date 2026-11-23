"""Scan text with the combined date regex and resolve each match."""

from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime, tzinfo

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


def search_dates(text: str, tz: tzinfo, first: FirstNumber) -> Generator[FoundDate, None, None]:
    """Yield every date in the text, resolved against the current time in `tz`.

    Matches that look like dates but are not real dates, such as February 30, are skipped.

    Args:
        text: The text to search.
        tz: The timezone of the reference time and of every returned datetime.
        first: Which part comes first in ambiguous numeric dates such as 01/02/03.

    Yields:
        FoundDate: Each date found, in text order.
    """
    regex = compile_date_regex(first)
    patterns = pattern_table(first)
    now = datetime.now(tz)

    for match in regex.finditer(text):
        groups = match.groupdict()
        # match.lastgroup is unreliable here: the patterns share inner group names
        pattern = next((p for p in patterns if groups[p.group_name] is not None), None)
        if pattern is None:
            msg = f"Expected one pattern group to match {match.group()!r}, got none"
            raise RuntimeError(msg)
        resolved = pattern.resolver(groups=groups, now=now)
        if resolved is not None:
            yield FoundDate(datetime=resolved, match=match.group(), span=match.span())
