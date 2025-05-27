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
    LAST_WEEK,
    MM,
    MM_FLEXIBLE,
    MONTH,
    NEXT_WEEK,
    SEP_CHARS,
    TODAY,
    TOMORROW,
    YESTERDAY,
    YYYY,
    YYYY_FLEXIBLE,
    FirstNumber,
)

DD = f"(?P<day>{DD})(?:{DIGIT_SUFFIXES})?"
DD_AS_TEXT = f"(?P<day_as_text>{DAY_NUMBERS})"
DD_FLEXIBLE = f"(?P<day>{DD_FLEXIBLE})(?:{DIGIT_SUFFIXES})?"
END = rf"(?![0-9]|[{SEP_CHARS}][0-9])"
LAST_WEEK = rf"(?P<last_week>{LAST_WEEK})"
MM = rf"(?P<month>{MM})"
MM_FLEXIBLE = rf"(?P<month>{MM_FLEXIBLE})"
MONTH_AS_TEXT = f"(?P<month_as_text>{MONTH})"
NEXT_WEEK = rf"(?P<next_week>{NEXT_WEEK})"
SEPARATOR = rf"[{SEP_CHARS}]*?"
MONTH_DAY_SEPARATOR = rf"{SEPARATOR}(?:the|of)?{SEPARATOR}"
START = rf"(?<![0-9]|[0-9][{SEP_CHARS}])"
TODAY = rf"(?P<today>{TODAY})"
TOMORROW = rf"(?P<tomorrow>{TOMORROW})"
YESTERDAY = rf"(?P<yesterday>{YESTERDAY})"
YYYY = rf"(?P<year>{YYYY})"
YYYY_FLEXIBLE = rf"(?P<year>{YYYY_FLEXIBLE})"

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
    {YYYY}
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
    {TODAY}|{YESTERDAY}|{TOMORROW}|{LAST_WEEK}|{NEXT_WEEK}
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


class DatePatternFactory:
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
            f"""{DD_MONTH_YYYY}|{MONTH_DD_YYYY}|{YYYY_MONTH_DD}|{MONTH_DD}|{YYYY_MONTH}|{MONTH_YYYY}|{NATURAL_DATE}|{yyyy_xx_xx}|{xx_xx_xx}|{YYYY_MM}|{MM_YYYY}|{yyyy_xxf_xxf}|{xxf_xxf_xxf}""",
            re.IGNORECASE | re.VERBOSE | re.MULTILINE | re.UNICODE | re.DOTALL,
        )
