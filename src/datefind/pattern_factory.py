"""Create regex patterns for matching dates in text.

Contains pattern definitions and factory classes for building flexible date-matching regular expressions that handle various date formats and styles.
"""

from typing import assert_never

import regex as re

from datefind.constants import (
    DAY_NUMBERS,
    DD,
    DD_FLEXIBLE,
    DIGIT_SUFFIXES,
    LAST_MONTH,
    LAST_WEEK,
    LAST_YEAR,
    MM,
    MM_FLEXIBLE,
    MONTH,
    NEXT_MONTH,
    NEXT_WEEK,
    NEXT_YEAR,
    QUARTER,
    SEP_CHARS,
    THIS_MONTH,
    THIS_WEEK,
    THIS_YEAR,
    TODAY,
    TOMORROW,
    WEEKDAYS,
    YESTERDAY,
    YYYY,
    YYYY_FLEXIBLE,
    FirstNumber,
)

DD = f"(?P<day>{DD})(?:{DIGIT_SUFFIXES})?"
DD_AS_TEXT = f"(?P<day_as_text>{DAY_NUMBERS})"
DD_FLEXIBLE = f"(?P<day>{DD_FLEXIBLE})(?:{DIGIT_SUFFIXES})?"
END = rf"(?![0-9]|[{SEP_CHARS}][0-9])"
LAST_MONTH = rf"(?P<last_month>{LAST_MONTH})"
NEXT_MONTH = rf"(?P<next_month>{NEXT_MONTH})"
LAST_YEAR = rf"(?P<last_year>{LAST_YEAR})"
NEXT_YEAR = rf"(?P<next_year>{NEXT_YEAR})"
THIS_WEEK = rf"(?P<this_week>{THIS_WEEK})"
THIS_MONTH = rf"(?P<this_month>{THIS_MONTH})"
THIS_YEAR = rf"(?P<this_year>{THIS_YEAR})"
LAST_WEEK = rf"(?P<last_week>{LAST_WEEK})"
MM = rf"(?P<month>{MM})"
MM_FLEXIBLE = rf"(?P<month>{MM_FLEXIBLE})"
MONTH_AS_TEXT = f"(?P<month_as_text>{MONTH})"
NEXT_WEEK = rf"(?P<next_week>{NEXT_WEEK})"
SEPARATOR = rf"[{SEP_CHARS}]*?"
MONTH_DAY_SEPARATOR = rf"{SEPARATOR}(?:the|of)?{SEPARATOR}"
# [Qq] excluded so that a digit following an invalid quarter (e.g. "Q5 2024") cannot
# be consumed by numeric patterns like xxf_xxf_xxf.
START = rf"(?<![0-9]|[0-9][{SEP_CHARS}]|[Qq])"
TODAY = rf"(?P<today>{TODAY})"
TOMORROW = rf"(?P<tomorrow>{TOMORROW})"
YESTERDAY = rf"(?P<yesterday>{YESTERDAY})"
YYYY = rf"(?P<year>{YYYY})"
YYYY_FLEXIBLE = rf"(?P<year>{YYYY_FLEXIBLE})"
# 2-digit year alternative requires no preceding digit. Prevents MONTH_DD_YYYY from
# splitting a 4-digit year like "2025" into day=20 + 2-digit year=25.
YYYY_FLEXIBLE_NO_PREV_DIGIT = r"(?P<year>19\d\d|20\d\d|(?<!\d)\d\d)"

ISO8601 = r"(?P<year>-?(\:[1-9][0-9]*)?[0-9]{4})\-(?P<month>1[0-2]|0[1-9])\-(?P<day>3[01]|0[1-9]|[12][0-9])T(?P<hour>2[0-3]|[01][0-9])\:(?P<minute>[0-5][0-9]):(?P<seconds>[0-5][0-9])(?:[\.,]+(?P<microseconds>[0-9]+))?(?P<offset>(?:Z|[+-](?:2[0-3]|[01][0-9])\:[0-5][0-9]))?"


YYYY_MONTH_DD = rf"""
    {START}
    {YYYY}
    {SEPARATOR}
    {MONTH_AS_TEXT}
    {SEPARATOR}
    ({DD_FLEXIBLE}|{DD_AS_TEXT})
    {END}
"""
DD_MONTH_YYYY = rf"""
    {START}
    ({DD_FLEXIBLE}|{DD_AS_TEXT})
    {MONTH_DAY_SEPARATOR}
    {MONTH_AS_TEXT}
    {MONTH_DAY_SEPARATOR}
    {YYYY}
    {END}
"""
MONTH_DD_YYYY = rf"""
    {START}
    {MONTH_AS_TEXT}
    {MONTH_DAY_SEPARATOR}
    ({DD_FLEXIBLE}|{DD_AS_TEXT})
    {MONTH_DAY_SEPARATOR}
    {YYYY_FLEXIBLE_NO_PREV_DIGIT}
    {END}
"""
YYYY_MONTH = rf"""
    {START}
    {YYYY}
    {SEPARATOR}
    {MONTH_AS_TEXT}
    {END}
"""
MONTH_DD = rf"""
    {START}
    {MONTH_AS_TEXT}
    {MONTH_DAY_SEPARATOR}
    ({DD_FLEXIBLE}|{DD_AS_TEXT})
    {END}
"""
MONTH_YYYY = rf"""
    {START}
    {MONTH_AS_TEXT}
    {MONTH_DAY_SEPARATOR}
    {YYYY}
    {END}
"""
NATURAL_DATE = rf"""
    {START}
    {TODAY}|{YESTERDAY}|{TOMORROW}|{LAST_WEEK}|{NEXT_WEEK}|{THIS_WEEK}|{LAST_MONTH}|{NEXT_MONTH}|{THIS_MONTH}|{LAST_YEAR}|{NEXT_YEAR}|{THIS_YEAR}
    {END}
"""
YYYY_MM = rf"""
    {START}
    {YYYY}
    {SEPARATOR}
    {MM}
    {END}
"""
MM_YYYY = rf"""
    {START}
    {MM}
    {MONTH_DAY_SEPARATOR}
    {YYYY}
    {END}
"""
QUARTER_YYYY = rf"""
    {START}
    (?P<quarter>{QUARTER})
    {SEPARATOR}
    {YYYY}
    {END}
"""
YYYY_QUARTER = rf"""
    {START}
    {YYYY}
    {SEPARATOR}
    (?P<quarter>{QUARTER})
    {END}
"""
RELATIVE_WEEKDAY = rf"""
    {START}
    (?P<weekday_modifier>last|next|this)
    {SEPARATOR}
    (?P<weekday>{WEEKDAYS})
    {END}
"""
BARE_WEEKDAY = rf"""
    {START}
    (?P<bare_weekday>{WEEKDAYS})
    {END}
"""


class PatternFactory:
    """Factory for creating date patterns."""

    def __init__(self, first_number: FirstNumber) -> None:
        """Initialize the factory. Defaults to US date format with month first.

        Args:
            first_number (FirstNumber): The first number to use.
        """
        self.first_number = first_number

    @staticmethod
    def _make_pattern(order: list[str]) -> str:
        """Create a regex pattern by joining date components in the specified order.

        Combine date pattern components (year, month, day) with separators to form a complete regex pattern. The components are joined in the order specified, with each component separated by the SEPARATOR pattern except for the last one.

        Args:
            order (list[str]): List of date pattern components in the desired order (e.g. [YYYY, MM, DD])

        Returns:
            str: A raw formatted string containing the complete regex pattern with start/end markers
        """
        pattern = f"{START}"
        for part in order:
            pattern += part
            if part != order[-1]:
                pattern += f"{SEPARATOR}"
        pattern += f"{END}"
        return rf"{pattern}"

    def make_regex(self) -> re.Pattern:
        """Create a compiled regular expression pattern for matching dates in text.

        Generate a regex pattern that matches various date formats including natural language dates (today, tomorrow, etc) and numeric dates. The order of numeric components is determined by the first_number setting specified during initialization.

        Returns:
            re.Pattern: A compiled regex pattern with flags for case-insensitive and verbose matching
        """
        # Set patterns that rely on the first_number flag.
        match self.first_number:
            case FirstNumber.MONTH:
                yyyy_xx_xx = self._make_pattern([YYYY, MM, DD])
                yyyy_xxf_xxf = self._make_pattern([YYYY, MM_FLEXIBLE, DD_FLEXIBLE])
                xx_xx_xx = self._make_pattern([MM, DD, YYYY])
                xxf_xxf_xxf = self._make_pattern([MM_FLEXIBLE, DD_FLEXIBLE, YYYY_FLEXIBLE])
            case FirstNumber.DAY:
                yyyy_xx_xx = self._make_pattern([YYYY, DD, MM])
                xx_xx_xx = self._make_pattern([DD, MM, YYYY])
                yyyy_xxf_xxf = self._make_pattern([YYYY, DD_FLEXIBLE, MM_FLEXIBLE])
                xxf_xxf_xxf = self._make_pattern([DD_FLEXIBLE, MM_FLEXIBLE, YYYY_FLEXIBLE])
            case FirstNumber.YEAR:
                yyyy_xx_xx = self._make_pattern([YYYY, MM, DD])
                xx_xx_xx = self._make_pattern([YYYY, MM, DD])
                yyyy_xxf_xxf = self._make_pattern([YYYY, MM_FLEXIBLE, DD_FLEXIBLE])
                xxf_xxf_xxf = self._make_pattern([YYYY_FLEXIBLE, MM_FLEXIBLE, DD_FLEXIBLE])
            case _:  # pragma: no cover
                assert_never(self.first_number)

        return re.compile(
            f"""{DD_MONTH_YYYY}|{MONTH_DD_YYYY}|{YYYY_MONTH_DD}|{MONTH_DD}|{YYYY_MONTH}|{MONTH_YYYY}|{NATURAL_DATE}|{QUARTER_YYYY}|{YYYY_QUARTER}|{RELATIVE_WEEKDAY}|{yyyy_xx_xx}|{xx_xx_xx}|{YYYY_MM}|{MM_YYYY}|{yyyy_xxf_xxf}|{xxf_xxf_xxf}|{BARE_WEEKDAY}""",
            re.IGNORECASE | re.VERBOSE | re.MULTILINE | re.UNICODE | re.DOTALL,
        )
