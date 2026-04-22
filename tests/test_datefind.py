"""Tests for datefind."""

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from datefind import find_dates

fixture_file = Path(__file__).parent / "fixture.txt"


def test_raise_error_on_invalid_timezone():
    """Verify ValueError raised when invalid timezone provided."""
    # Given: An invalid timezone string
    invalid_tz = "America/California"

    # When/Then: find_dates raises ValueError
    with pytest.raises(ValueError, match="Invalid timezone: America/California"):
        find_dates("Hello, world! Today is 2024-01-01.", tz=invalid_tz)


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
        ("2024112", [datetime(2024, 11, 2)]),
        ("12112022", [datetime(2022, 12, 11)]),
        ("2111999", [datetime(1999, 2, 11)]),
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
        ("Mar 15, 24", [datetime(2024, 3, 15)]),
        ("March 15 24", [datetime(2024, 3, 15)]),
        ("march 3rd 99", [datetime(2099, 3, 3)]),
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
        # Bare weekday substring prevention
        ("among friends", []),
        ("sunlight", []),
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
    for i, date in enumerate(dates):
        assert date.datetime.strftime("%Y-%m-%d") == expected[i].strftime("%Y-%m-%d")
        assert date.match == text
        assert date.span == (0, len(text))


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
        datetime(2019, 9, 8, tzinfo=ZoneInfo("UTC")),
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
    for i, date in enumerate(dates):
        assert date.datetime.strftime("%Y-%m-%d") == expected[i].strftime("%Y-%m-%d")


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
    ],
)
def test_first_number(text: str, first: str, expected: list[datetime], debug) -> None:
    """Verify extracting dates from text returns expected datetime objects."""
    # Given: Text containing dates and expected datetime
    # When: Finding dates in the text
    dates = list(find_dates(text, first=first, tz="UTC"))

    # Then: Each found date matches expected datetime
    assert len(dates) == len(expected)
    for i, date in enumerate(dates):
        assert date.datetime.strftime("%Y-%m-%d") == expected[i].strftime("%Y-%m-%d")


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
