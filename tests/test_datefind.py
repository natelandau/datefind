"""Tests for datefind."""

import re
from datetime import UTC, date, datetime, timedelta, tzinfo
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from datefind import DatePrecision, find_dates

fixture_file = Path(__file__).parent / "fixture.txt"


@pytest.mark.parametrize("invalid_tz", ["America/California", "/etc/localtime", "Foo/../Bar"])
def test_raise_error_on_invalid_timezone(invalid_tz: str) -> None:
    """Verify ValueError raised when invalid timezone provided."""
    # When/Then: find_dates raises ValueError naming the timezone
    with pytest.raises(ValueError, match=f"Invalid timezone: {re.escape(invalid_tz)}"):
        find_dates("Hello, world! Today is 2024-01-01.", tz=invalid_tz)


@pytest.mark.parametrize(
    ("text", "first", "expected"),
    [
        ("9819", "month", date(2019, 9, 8)),
        ("2024112", "month", date(2024, 11, 2)),
        ("2111999", "month", date(1999, 2, 11)),
        ("120524", "month", date(2024, 12, 5)),
        ("120524", "day", date(2024, 5, 12)),
        ("202412", "month", date(2024, 12, 1)),
    ],
)
@freeze_time("2024-03-01")
def test_short_digit_dates(
    text: str, first: Literal["month", "day", "year"], expected: date, debug
) -> None:
    """Verify runs of 4 to 7 digits read as dates when the caller opts in."""
    # When: finding dates with short digit runs enabled
    dates = list(find_dates(text, first=first, tz="UTC", short_digit_dates=True))

    # Then: the whole run is one date
    assert [found.datetime.date() for found in dates] == [expected]
    assert dates[0].match == text
    assert dates[0].span == (0, len(text))


@pytest.mark.parametrize(
    ("text", "now", "expected"),
    [
        ("born 12/25/85", date(2026, 11, 23), date(1985, 12, 25)),
        ("march 3rd 75", date(2026, 11, 23), date(2075, 3, 3)),
        ("march 3rd 76", date(2026, 11, 23), date(1976, 3, 3)),
        ("1/2/00", date(2026, 11, 23), date(2000, 1, 2)),
        # The window follows the reference date, not the clock
        ("march 3rd 39", date(1990, 1, 1), date(2039, 3, 3)),
        ("march 3rd 40", date(1990, 1, 1), date(1940, 3, 3)),
    ],
)
def test_two_digit_year_century(text: str, now: date, expected: date, debug) -> None:
    """Verify a two-digit year takes the century that keeps it within 50 years of the reference date."""
    # When: finding dates with a reference date
    dates = list(find_dates(text, tz="UTC", now=now))

    # Then: the year lands in the expected century
    assert [found.datetime.date() for found in dates] == [expected]


@pytest.mark.parametrize(
    ("text", "now", "tz", "expected"),
    [
        # A date resolves relative words against that day
        ("tomorrow", date(2024, 3, 1), "UTC", datetime(2024, 3, 2, tzinfo=ZoneInfo("UTC"))),
        ("next friday", date(2024, 3, 1), "UTC", datetime(2024, 3, 8, tzinfo=ZoneInfo("UTC"))),
        # An aware datetime is converted to the output timezone, then cut to midnight
        (
            "today",
            datetime(2024, 3, 1, 23, 30, tzinfo=ZoneInfo("UTC")),
            "Asia/Tokyo",
            datetime(2024, 3, 2, tzinfo=ZoneInfo("Asia/Tokyo")),
        ),
        # A naive datetime is read as a wall-clock time in the output timezone
        (
            "3 days ago",
            datetime(2024, 3, 1, 23, 30),
            "Asia/Tokyo",
            datetime(2024, 2, 27, tzinfo=ZoneInfo("Asia/Tokyo")),
        ),
        # The timezone can be a tzinfo object instead of a name
        (
            "yesterday",
            date(2024, 3, 1),
            ZoneInfo("Asia/Tokyo"),
            datetime(2024, 2, 29, tzinfo=ZoneInfo("Asia/Tokyo")),
        ),
        ("2024-01-12", date(2024, 3, 1), UTC, datetime(2024, 1, 12, tzinfo=UTC)),
    ],
)
def test_find_dates_with_reference_date(
    text: str, now: date | datetime, tz: str | tzinfo, expected: datetime, debug
) -> None:
    """Verify dates resolve against the caller's reference date, at midnight in the output timezone."""
    # When: finding dates with an explicit reference date
    dates = list(find_dates(text, tz=tz, now=now))

    # Then: the single date matches exactly, including time of day and timezone
    assert [found.datetime for found in dates] == [expected]
    assert dates[0].datetime.tzinfo == expected.tzinfo


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("01-12", []),
        ("2024-24-12", []),
        ("2024-01-32", []),
        ("march thirtysecond 2025", []),
        ("hello world", []),
        ("2019-99-01", []),
        ("30122022", []),  # fails b/c month is first
        ("01122024", [datetime(2024, 1, 12)]),
        ("01:12:2024", [datetime(2024, 1, 12)]),
        ("2024-01-12", [datetime(2024, 1, 12)]),
        ("2024/01/12", [datetime(2024, 1, 12)]),
        ("20240112", [datetime(2024, 1, 12)]),
        ("2024-1-12", [datetime(2024, 1, 12)]),
        ("2024/1/12", [datetime(2024, 1, 12)]),
        ("2024112", []),
        ("12112022", [datetime(2022, 12, 11)]),
        ("2111999", []),
        # Runs of 4 to 7 digits match only with short_digit_dates=True
        ("9819", []),
        ("1985", []),
        ("120524", []),
        ("202412", []),
        ("order 120524 shipped", []),
        # No part of a run longer than 8 digits matches
        ("1234567890", []),
        ("202405121", []),
        # A separator or month name marks the year, so years 1000 to 2999 match
        ("dec 31 1899", [datetime(1899, 12, 31)]),
        ("12/25/1850", [datetime(1850, 12, 25)]),
        ("1850-12-25", [datetime(1850, 12, 25)]),
        ("March 1105", [datetime(1105, 3, 1)]),
        ("Q2 1500", [datetime(1500, 4, 1)]),
        ("2999-12-31", [datetime(2999, 12, 31)]),
        ("12/25/0999", []),
        ("3000-01-01", []),
        ("call 555-1212", []),
        # A year glued to the quarter needs a year from 1900 to 2099
        ("Q31500", []),
        ("Q32024", [datetime(2024, 7, 1)]),
        # A day glued to the year after a month name needs a year from 1900 to 2099
        ("March 31105", []),
        ("jan 12500 units", []),
        ("march 21500", []),
        ("March 31999", [datetime(1999, 3, 3)]),
        # In all-number dates, years outside 1900 to 2099 need a / - or . separator
        ("10 2500 sold", []),
        ("page 12, 1500 words", []),
        ("12 25 1850", []),
        ("1850 12 25", []),
        ("12 . 25 . 1850", [datetime(1850, 12, 25)]),
        # A numeric month and year without a day needs a year from 1900 to 2099
        ("12/1500", []),
        ("1850.12", []),
        ("price 1500.05", []),
        ("lat 10.1234", []),
        ("pages 10-1500", []),
        # A three-letter month abbreviation inside a longer word is not a month
        ("grammar 1500 words", []),
        ("2500 Market Street", []),
        ("1500 Mayfield Rd", []),
        ("Kumar 1500", []),
        ("2022-12", [datetime(2022, 12, 1)]),
        ("12 2022", [datetime(2022, 12, 1)]),
        ("sep. 4", [datetime(2024, 9, 4)]),
        ("sept. fifth", [datetime(2024, 9, 5)]),
        ("2022, 12, 24", [datetime(2022, 12, 24)]),
        ("23 march, 2020", [datetime(2020, 3, 23)]),
        ("23rd, march-2020", [datetime(2020, 3, 23)]),
        ("23rd of march 2020", [datetime(2020, 3, 23)]),
        ("fifteenth march, 2025", [datetime(2025, 3, 15)]),
        ("twenty fifth of march, 2025", [datetime(2025, 3, 25)]),
        ("twentyfifth of march, 2025", [datetime(2025, 3, 25)]),
        ("march 23", [datetime(2024, 3, 23)]),
        ("march 23 2025", [datetime(2025, 3, 23)]),
        ("march 21st 2025", [datetime(2025, 3, 21)]),
        ("march the 23rd 2025", [datetime(2025, 3, 23)]),
        ("march the 23rd of 2025", [datetime(2025, 3, 23)]),
        ("march 23rd", [datetime(2024, 3, 23)]),
        ("march the 22nd", [datetime(2024, 3, 22)]),
        ("march twenty second", [datetime(2024, 3, 22)]),
        ("march the twentysecond", [datetime(2024, 3, 22)]),
        ("march the first of 2025", [datetime(2025, 3, 1)]),
        # Day before month, without a year
        ("14 feb", [datetime(2024, 2, 14)]),
        ("25 December", [datetime(2024, 12, 25)]),
        ("3rd march", [datetime(2024, 3, 3)]),
        ("twenty fifth of december", [datetime(2024, 12, 25)]),
        ("31 feb", []),
        # "may" is also a verb, so a bare number before it needs "of", "the", or an ordinal
        ("2nd May", [datetime(2024, 5, 2)]),
        ("2nd of May", [datetime(2024, 5, 2)]),
        ("2 of may", [datetime(2024, 5, 2)]),
        ("second of may", [datetime(2024, 5, 2)]),
        ("2 may", []),
        ("option 2 may work", []),
        ("Mar 15, 24", [datetime(2024, 3, 15)]),
        ("March 15 24", [datetime(2024, 3, 15)]),
        ("march 3rd 99", [datetime(1999, 3, 3)]),
        ("march 20 2025", [datetime(2025, 3, 20)]),
        ("march 2025", [datetime(2025, 3, 1)]),
        ("january, of 1998", [datetime(1998, 1, 1)]),
        ("second january, of 1998", [datetime(1998, 1, 2)]),
        ("today", [datetime(2024, 3, 1)]),
        ("yesterday", [datetime(2024, 3, 1) - timedelta(days=1)]),
        ("tomorrow", [datetime(2024, 3, 1) + timedelta(days=1)]),
        ("last week", [datetime(2024, 3, 1) - timedelta(days=7)]),
        ("next week", [datetime(2024, 3, 1) + timedelta(days=7)]),
        (
            "last month",
            [datetime(2024, 3, 1).replace(month=2)],
        ),
        (
            "next month",
            [datetime(2024, 3, 1).replace(month=4)],
        ),
        (
            "last year",
            [datetime(2024, 3, 1).replace(year=2023)],
        ),
        (
            "next year",
            [datetime(2024, 3, 1).replace(year=2025)],
        ),
        ("this week", [datetime(2024, 3, 1)]),
        ("this month", [datetime(2024, 3, 1)]),
        ("this year", [datetime(2024, 3, 1)]),
        ("Q1 2024", [datetime(2024, 1, 1)]),
        ("Q2 2024", [datetime(2024, 4, 1)]),
        ("Q3 2024", [datetime(2024, 7, 1)]),
        ("Q4 2024", [datetime(2024, 10, 1)]),
        ("q1 2024", [datetime(2024, 1, 1)]),
        ("Q1-2024", [datetime(2024, 1, 1)]),
        ("2024 Q1", [datetime(2024, 1, 1)]),
        ("2024-Q4", [datetime(2024, 10, 1)]),
        ("Q5 2024", []),
        ("Q1", []),
        # Bare weekday — next occurrence
        ("Monday", [datetime(2024, 3, 4)]),
        ("Friday", [datetime(2024, 3, 8)]),
        ("mon", [datetime(2024, 3, 4)]),
        ("sunday", [datetime(2024, 3, 3)]),
        # Relative weekday
        ("next Monday", [datetime(2024, 3, 4)]),
        ("last Monday", [datetime(2024, 2, 26)]),
        ("this Monday", [datetime(2024, 3, 4)]),
        ("this Friday", [datetime(2024, 3, 1)]),
        ("last Friday", [datetime(2024, 2, 23)]),
        ("next Friday", [datetime(2024, 3, 8)]),
        ("next sat", [datetime(2024, 3, 2)]),
        ("last sun", [datetime(2024, 2, 25)]),
        ("this wed", [datetime(2024, 3, 6)]),
        # Bare weekday substring prevention
        ("among friends", []),
        ("sunlight", []),
        ("c'mon", []),
        # Abbreviations that are also English words need a modifier
        ("I sat down on the sun deck", []),
        ("they wed", []),
        # Version numbers after "v" or "version" are not dates
        ("version 2.1.1500", []),
        ("v2.1.1500", []),
        ("V1.2.2024", []),
        ("Version: 1.2.2024", []),
        # Relative count patterns
        ("3 days ago", [datetime(2024, 2, 27)]),
        ("in 3 days", [datetime(2024, 3, 4)]),
        ("3 days from now", [datetime(2024, 3, 4)]),
        ("1 day ago", [datetime(2024, 2, 29)]),
        ("2 weeks ago", [datetime(2024, 2, 16)]),
        ("in 2 weeks", [datetime(2024, 3, 15)]),
        ("2 weeks from now", [datetime(2024, 3, 15)]),
        ("1 month ago", [datetime(2024, 2, 1)]),
        ("in 2 months", [datetime(2024, 5, 1)]),
        ("2 years ago", [datetime(2022, 3, 1)]),
        ("in 1 year", [datetime(2025, 3, 1)]),
        ("1 year from now", [datetime(2025, 3, 1)]),
        ("0 days ago", [datetime(2024, 3, 1)]),
        ("days ago", []),
        ("in days", []),
        # Word-boundary anchoring for relative counts
        ("spin 3 days", []),
        ("contain 2 weeks", []),
        ("in 2 weekly", []),
        ("in 3 daysx", []),
        ("1000000 days ago", []),
        ("99999999999 days ago", []),
        # Calendar-invalid dates
        ("February 30, 2024", []),
        ("Feb 29 2023", []),
        # Two-letter words are not month abbreviations
        ("No 10", []),
        ("ma 15", []),
        # Word-boundary anchoring for natural dates
        ("this weekend", []),
        ("next monthly", []),
        ("ultimatoday", []),
        # A number followed by a year is not split into month, day, and two-digit year
        ("3, 2024", []),
        # Case-insensitive matching treats long s (U+017F) as "s" and dotted capital I (U+0130) as "i"
        ("la\u017ft week", [datetime(2024, 2, 23)]),
        ("th\u0130s month", [datetime(2024, 3, 1)]),
        ("today\u017f", [datetime(2024, 3, 1)]),
        ("fir\u017ft of march 2024", [datetime(2024, 3, 1)]),
        ("\u017funday", [datetime(2024, 3, 3)]),
        ("la\u017ft monday", [datetime(2024, 2, 26)]),
        ("\u017feptember 5 2024", [datetime(2024, 9, 5)]),
        ("in 2 day\u017f", [datetime(2024, 3, 3)]),
        # A count too long to convert to an integer is not a date
        ("in " + "9" * 5000 + " days", []),
        # A weekday before a date is part of that date
        ("Friday, January 5, 2024", [datetime(2024, 1, 5)]),
        ("Wed, 03 Jan 2024", [datetime(2024, 1, 3)]),
        ("Sat. 6 January", [datetime(2024, 1, 6)]),
        ("Friday the 5th of January 2024", [datetime(2024, 1, 5)]),
        ("Fri 01/05/2024", [datetime(2024, 1, 5)]),
        ("Thursday 2024-01-04", [datetime(2024, 1, 4)]),
        # Two days away
        ("day after tomorrow", [datetime(2024, 3, 3)]),
        ("day before yesterday", [datetime(2024, 2, 28)]),
        # A day of the month relative to this month
        ("3rd of next month", [datetime(2024, 4, 3)]),
        ("twentieth of last month", [datetime(2024, 2, 20)]),
        ("15 of this month", [datetime(2024, 3, 15)]),
        ("31st of next month", []),
        # A day range after a month name is not a day and a two-digit year
        ("Jan 5-10", []),
        ("Jan 5 - 10", []),
        ("Jan 5-10, 2024", []),
        ("Jan 5\u201310, 2024", []),
        ("Jan 5 \u2013 10, 2024", []),
        ("Jan 5 to 10, 2024", []),
        ("Jan-05-24", [datetime(2024, 1, 5)]),
        ("Jan 05-24", [datetime(2024, 1, 5)]),
        ("March 5-2024", [datetime(2024, 3, 5)]),
    ],
)
@freeze_time("2024-03-01")
def test_find_dates(text, expected, debug):
    """Verify extracting dates from short text returns expected datetime objects."""
    # Given: Text containing dates and expected datetime

    # When: Finding dates in the text
    dates = list(find_dates(text, first="month", tz="UTC"))

    # Then: Each found date matches expected datetime
    assert len(dates) == len(expected)
    for i, found in enumerate(dates):
        assert found.datetime.strftime("%Y-%m-%d") == expected[i].strftime("%Y-%m-%d")
        assert found.match == text
        assert found.span == (0, len(text))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("March 1 2025", "day"),
        ("1 March 2025", "day"),
        ("2025 March 1", "day"),
        ("March 1", "day"),
        ("2025-03-01", "day"),
        ("03/01/2025", "day"),
        ("3/1/25", "day"),
        ("20250301", "day"),
        ("today", "day"),
        ("3 months ago", "day"),
        ("in 2 weeks", "day"),
        ("1 year from now", "day"),
        ("friday", "day"),
        ("next friday", "day"),
        ("last week", "week"),
        ("march 2025", "month"),
        ("2025 march", "month"),
        ("2025-03", "month"),
        ("03/2025", "month"),
        ("next month", "month"),
        ("Q1 2025", "quarter"),
        ("2025 Q1", "quarter"),
        ("this year", "year"),
    ],
)
def test_precision(text: str, expected: DatePrecision, debug) -> None:
    """Verify each found date reports how much of the date its text pins down."""
    # When: finding the date
    dates = list(find_dates(text=text, tz="UTC", now=date(2026, 11, 23)))

    # Then: the whole text is one date with the expected precision
    assert [(found.match, found.precision) for found in dates] == [(text, expected)]


@freeze_time("2024-03-01")
def test_find_dates_in_file(debug):
    """Verify extracting dates from a large text input returns expected datetime objects."""
    file = Path(__file__).parent / "fixture.txt"
    text = file.read_text()

    expected = [
        datetime(2025, 3, 22, tzinfo=ZoneInfo("UTC")),
        datetime(1999, 9, 13, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 12, 2, tzinfo=ZoneInfo("UTC")),
        datetime(2023, 7, 4, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 5, 12, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 1, 9, tzinfo=ZoneInfo("UTC")),
        datetime(2025, 1, 23, tzinfo=ZoneInfo("UTC")),
        datetime(1999, 3, 1, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 2, 1, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 8, 2, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 1, 10, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 4, 1, tzinfo=ZoneInfo("UTC")),
        datetime(1999, 8, 25, tzinfo=ZoneInfo("UTC")),
        datetime(datetime.now(ZoneInfo("UTC")).year, 1, 11, tzinfo=ZoneInfo("UTC")),
        datetime(datetime.now(ZoneInfo("UTC")).year, 3, 11, tzinfo=ZoneInfo("UTC")),
        datetime(1999, 12, 1, tzinfo=ZoneInfo("UTC")),
        datetime(2024, 1, 10, tzinfo=ZoneInfo("UTC")),
        datetime.now(ZoneInfo("UTC")),
        datetime.now(ZoneInfo("UTC")) - timedelta(days=1),
        datetime.now(ZoneInfo("UTC")) + timedelta(days=1),
        datetime.now(ZoneInfo("UTC")) - timedelta(days=7),
        datetime.now(ZoneInfo("UTC")) + timedelta(days=7),
        datetime.now(ZoneInfo("UTC")).replace(year=datetime.now(ZoneInfo("UTC")).year - 1),
        # New paragraph: Q1 2024, 2024 Q3, next Monday, March 15 24, 3 days ago, in 2 weeks,
        # This month, this year's, last Friday
        datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),  # Q1 2024
        datetime(2024, 7, 1, tzinfo=ZoneInfo("UTC")),  # 2024 Q3
        datetime.now(ZoneInfo("UTC"))
        + timedelta(days=(0 - datetime.now(ZoneInfo("UTC")).weekday()) % 7 or 7),  # next Monday
        datetime(2024, 3, 15, tzinfo=ZoneInfo("UTC")),  # March 15, 24
        datetime.now(ZoneInfo("UTC")) - timedelta(days=3),  # 3 days ago
        datetime.now(ZoneInfo("UTC")) + timedelta(days=14),  # in 2 weeks
        datetime.now(ZoneInfo("UTC")),  # This month
        datetime.now(ZoneInfo("UTC")),  # this year's
        datetime.now(ZoneInfo("UTC"))
        - timedelta(days=(datetime.now(ZoneInfo("UTC")).weekday() - 4) % 7 or 7),  # last Friday
    ]

    # When: Finding dates in the text
    dates = list(find_dates(text, first="month", tz="UTC"))

    # Then: Each found date matches expected datetime
    assert len(dates) == len(expected)
    for i, found in enumerate(dates):
        assert found.datetime.strftime("%Y-%m-%d") == expected[i].strftime("%Y-%m-%d")


@pytest.mark.parametrize(
    ("text", "first", "expected"),
    [
        ("2024-01-12", "day", [datetime(2024, 12, 1, tzinfo=ZoneInfo("UTC"))]),
        ("1-12-2024", "day", [datetime(2024, 12, 1, tzinfo=ZoneInfo("UTC"))]),
        ("01-12-24", "day", [datetime(2024, 12, 1, tzinfo=ZoneInfo("UTC"))]),
        ("1-12-24", "day", [datetime(2024, 12, 1, tzinfo=ZoneInfo("UTC"))]),
        ("1-2-24", "day", [datetime(2024, 2, 1, tzinfo=ZoneInfo("UTC"))]),
        ("2024-01-12", "month", [datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC"))]),
        ("1-12-2024", "month", [datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC"))]),
        ("01-12-24", "month", [datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC"))]),
        ("1-12-24", "month", [datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC"))]),
        ("1-2-24", "month", [datetime(2024, 1, 2, tzinfo=ZoneInfo("UTC"))]),
        ("2024-01-12", "year", [datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC"))]),
        ("1-12-2024", "year", []),
        ("01-12-24", "year", [datetime(2001, 12, 24, tzinfo=ZoneInfo("UTC"))]),
        ("2001-12-24", "year", [datetime(2001, 12, 24, tzinfo=ZoneInfo("UTC"))]),
        ("01-2-1", "year", [datetime(2001, 2, 1, tzinfo=ZoneInfo("UTC"))]),
        ("2001-02-1", "year", [datetime(2001, 2, 1, tzinfo=ZoneInfo("UTC"))]),
        ("2001-2-01", "year", [datetime(2001, 2, 1, tzinfo=ZoneInfo("UTC"))]),
        ("16041905", "day", [datetime(1905, 4, 16, tzinfo=ZoneInfo("UTC"))]),
    ],
)
@freeze_time("2024-03-01")
def test_first_number(
    text: str, first: Literal["month", "day", "year"], expected: list[datetime], debug
) -> None:
    """Verify extracting dates from text returns expected datetime objects."""
    # Given: Text containing dates and expected datetime
    # When: Finding dates in the text
    dates = list(find_dates(text, first=first, tz="UTC"))

    # Then: Each found date matches expected datetime
    assert len(dates) == len(expected)
    for i, found in enumerate(dates):
        assert found.datetime.strftime("%Y-%m-%d") == expected[i].strftime("%Y-%m-%d")


def test_date_object(debug):
    """Verify FoundDate object has expected properties."""
    text = "Hello, world! 2024-01-12 and jan. eighteenth, 2024"
    dates = list(find_dates(text, first="month", tz="UTC"))
    assert len(dates) == 2
    assert dates[0].datetime == datetime(2024, 1, 12, tzinfo=ZoneInfo("UTC"))
    assert dates[0].match == "2024-01-12"
    assert dates[0].span == (14, 24)

    assert dates[1].datetime == datetime(2024, 1, 18, tzinfo=ZoneInfo("UTC"))
    assert dates[1].match == "jan. eighteenth, 2024"
    assert dates[1].span == (29, 50)


@freeze_time("2024-02-29")
def test_leap_year(debug):
    """Verify leap year is handled correctly."""
    text = "last year"
    dates = list(find_dates(text, first="month", tz="UTC"))
    assert len(dates) == 0


@freeze_time("2024-03-31")
def test_last_month(debug):
    """Verify last month is handled correctly."""
    text = "last month"
    dates = list(find_dates(text, first="month", tz="UTC"))
    assert len(dates) == 0


@freeze_time("2024-01-15")
def test_last_month_crosses_year_boundary(debug):
    """Verify 'last month' from January resolves to December of the prior year."""
    # Given: today is January 15, 2024
    # When: parsing "last month"
    dates = list(find_dates("last month", first="month", tz="UTC"))
    # Then: resolves to December 15, 2023
    assert len(dates) == 1
    assert dates[0].datetime.strftime("%Y-%m-%d") == "2023-12-15"


@freeze_time("2024-12-15")
def test_next_month_crosses_year_boundary(debug):
    """Verify 'next month' from December resolves to January of the next year."""
    # Given: today is December 15, 2024
    # When: parsing "next month"
    dates = list(find_dates("next month", first="month", tz="UTC"))
    # Then: resolves to January 15, 2025
    assert len(dates) == 1
    assert dates[0].datetime.strftime("%Y-%m-%d") == "2025-01-15"


@freeze_time("2024-03-31")
def test_relative_count_month_end_edge(debug):
    """Verify 'in 1 month' from March 31 returns no match (April has no 31st)."""
    # Given: today is March 31, 2024
    # When: parsing "in 1 month"
    dates = list(find_dates("in 1 month", first="month", tz="UTC"))
    # Then: no date resolved (April 31 is invalid)
    assert len(dates) == 0


@freeze_time("2024-02-29")
def test_relative_count_leap_day(debug):
    """Verify '1 year ago' from Feb 29 returns no match (2023 is not a leap year)."""
    # Given: today is Feb 29, 2024 (leap day)
    # When: parsing "1 year ago"
    dates = list(find_dates("1 year ago", first="month", tz="UTC"))
    # Then: no date resolved (Feb 29, 2023 does not exist)
    assert len(dates) == 0


@freeze_time("2024-03-01")
def test_find_dates_partial_match_in_word_context(debug):
    """Verify weekday patterns match only whole words, not substrings of other words."""
    # Given: text where a full weekday word appears alongside a word that contains a weekday substring
    text = "thursday thunder"

    # When: finding dates
    dates = list(find_dates(text, first="month", tz="UTC"))

    # Then: only the full weekday word matches; "thu" inside "thunder" does not
    assert len(dates) == 1
    assert dates[0].datetime.strftime("%Y-%m-%d") == "2024-03-07"
    assert dates[0].match == "thursday"
    assert dates[0].span == (0, 8)


def test_find_dates_after_word_ending_in_v(debug):
    """Verify only a standalone "v" marks a version number, not a word that ends in v."""
    # Given: a date after a word ending in "v"
    text = "dev 1.2.2024"

    # When: finding dates
    dates = list(find_dates(text, first="month", tz="UTC"))

    # Then: the date still matches
    assert [(found.match, found.datetime.date()) for found in dates] == [
        ("1.2.2024", date(2024, 1, 2))
    ]


@freeze_time("2024-03-01")
def test_find_dates_month_name_after_number(debug):
    """Verify a month name preceded by a number still anchors a month-first date."""
    # Given: a month-first date that follows an unrelated number
    text = "item 5 January 3, 2024"

    # When: finding dates
    dates = list(find_dates(text, first="month", tz="UTC"))

    # Then: the full month-first date matches
    assert len(dates) == 1
    assert dates[0].datetime.strftime("%Y-%m-%d") == "2024-01-03"
    assert dates[0].match == "January 3, 2024"


@pytest.mark.parametrize(
    ("text", "expected_match", "expected_date"),
    [
        ("05 Jan 2024 10:00:00", "05 Jan 2024", date(2024, 1, 5)),
        ("Wed, 03 Jan 2024 10:00:00 +0000", "Wed, 03 Jan 2024", date(2024, 1, 3)),
        ("2024-01-05 14:30", "2024-01-05", date(2024, 1, 5)),
        ("1/5/2024 9:15 am", "1/5/2024", date(2024, 1, 5)),
        ("Jan 5, 2024, 3 PM", "Jan 5, 2024", date(2024, 1, 5)),
        ("Jan 5 10:00:00", "Jan 5", date(2024, 1, 5)),
        ("Jan 5 10pm", "Jan 5", date(2024, 1, 5)),
        ("Jan 5 10 p.m.", "Jan 5", date(2024, 1, 5)),
        ("14 Feb 10:00", "14 Feb", date(2024, 2, 14)),
        ("next friday 3pm", "next friday", date(2024, 3, 8)),
        ("today 10:30", "today", date(2024, 3, 1)),
        ("March 5 24:00", "March 5", date(2024, 3, 5)),
    ],
)
def test_find_dates_followed_by_time(
    text: str, expected_match: str, expected_date: date, debug
) -> None:
    """Verify a time of day after a date leaves the date found and is not read as part of it."""
    # When: finding dates in text where a time follows the date
    dates = list(find_dates(text, tz="UTC", now=date(2024, 3, 1)))

    # Then: only the date part matches
    assert [(found.match, found.datetime.date()) for found in dates] == [
        (expected_match, expected_date)
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # A range across two months gives both dates
        (
            "Jan 28 - 3 Feb",
            [("Jan 28", date(2024, 1, 28)), ("3 Feb", date(2024, 2, 3))],
        ),
        (
            "Jan 5 - 10 March",
            [("Jan 5", date(2024, 1, 5)), ("10 March", date(2024, 3, 10))],
        ),
        # "sat" is a verb unless punctuation marks it as a weekday
        ("we sat 2 jan 2024", [("2 jan 2024", date(2024, 1, 2))]),
        # A bare number before a possessive month counts items, not days
        ("page 2 of this month's issue", [("this month's", date(2024, 3, 1))]),
        ("the day after tomorrow", [("day after tomorrow", date(2024, 3, 3))]),
        ("on the 3rd of next month", [("3rd of next month", date(2024, 4, 3))]),
        # A weekday already part of an earlier date is not also part of the next date
        (
            "next Friday, January 5",
            [("next Friday", date(2024, 3, 8)), ("January 5", date(2024, 1, 5))],
        ),
        # A weekday not directly before a date stays a date of its own
        (
            "Monday, then January 5",
            [("Monday", date(2024, 3, 4)), ("January 5", date(2024, 1, 5))],
        ),
    ],
)
def test_find_dates_partial_phrases(text: str, expected: list[tuple[str, date]], debug) -> None:
    """Verify phrases around a date yield the whole date or nothing, never a wrong date."""
    # When: finding dates in the phrase
    dates = list(find_dates(text, tz="UTC", now=date(2024, 3, 1)))

    # Then: the matched text and date are exactly as expected
    assert [(found.match, found.datetime.date()) for found in dates] == expected
