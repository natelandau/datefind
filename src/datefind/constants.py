"""Constants for datefind."""

from enum import Enum


class FirstNumber(Enum):
    """Enum for the first number to find in ambiguous dates."""

    MONTH = "month"
    DAY = "day"
    YEAR = "year"


class DayToNumber(Enum):
    """Enum for the day to number."""

    FIRST = 1
    SECOND = 2
    THIRD = 3
    FOURTH = 4
    FIFTH = 5
    SIXTH = 6
    SEVENTH = 7
    EIGHTH = 8
    NINTH = 9
    TENTH = 10
    ELEVENTH = 11
    TWELFTH = 12
    THIRTEENTH = 13
    FOURTEENTH = 14
    FIFTEENTH = 15
    SIXTEENTH = 16
    SEVENTEENTH = 17
    EIGHTEENTH = 18
    NINETEENTH = 19
    TWENTIETH = 20
    TWENTYFIRST = 21
    TWENTYSECOND = 22
    TWENTYTHIRD = 23
    TWENTYFOURTH = 24
    TWENTYFIFTH = 25
    TWENTYSIXTH = 26
    TWENTYSEVENTH = 27
    TWENTYEIGHTH = 28
    TWENTYNINTH = 29
    THIRTIETH = 30
    THIRTYFIRST = 31


CENTURY = 20  # Used for years provided with two digits
SEP_CHARS = r"-\/:,._\+@ "  # Define separator chars for reuse
SEP_CHARS_REGEX = rf"[{SEP_CHARS}]*?"
DD_FLEXIBLE = r"[12][0-9]|3[01]|0?[1-9]"
DD = r"0[1-9]|[12][0-9]|3[01]"
MM = r"0[1-9]|1[012]"
MM_FLEXIBLE = r"1[012]|0?[1-9]"
YYYY = r"19\d\d|20\d\d"
YYYY_FLEXIBLE = rf"{YYYY}|\d\d"
JANUARY = r"january|jan?"
FEBRUARY = r"february|feb?"
MARCH = r"march|mar?"
APRIL = r"april|apr?"
MAY = r"may"
JUNE = r"june?"
JULY = r"july?"
AUGUST = r"august|aug?"
SEPTEMBER = r"september|sept?"
OCTOBER = r"october|oct?"
NOVEMBER = r"november|nov?"
DECEMBER = r"december|dec?"
MONTH = rf"{JANUARY}|{FEBRUARY}|{MARCH}|{APRIL}|{MAY}|{JUNE}|{JULY}|{AUGUST}|{SEPTEMBER}|{OCTOBER}|{NOVEMBER}|{DECEMBER}"
DAY_NUMBERS = rf"first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|thirteenth|fourteenth|fifteenth|sixteenth|seventeenth|eighteenth|nineteenth|twentieth|twenty{SEP_CHARS_REGEX}first|twenty{SEP_CHARS_REGEX}second|twenty{SEP_CHARS_REGEX}third|twenty{SEP_CHARS_REGEX}fourth|twenty{SEP_CHARS_REGEX}fifth|twenty{SEP_CHARS_REGEX}sixth|twenty{SEP_CHARS_REGEX}seventh|twenty{SEP_CHARS_REGEX}eighth|twenty{SEP_CHARS_REGEX}ninth|thirtieth|thirty{SEP_CHARS_REGEX}first"
DIGIT_SUFFIXES = r"st|th|rd|nd"
TODAY = r"today'?s?"
YESTERDAY = r"yesterday'?s?"
TOMORROW = r"tomorrow'?s?"
LAST_WEEK = rf"last{SEP_CHARS_REGEX}week'?s?"
NEXT_WEEK = rf"next{SEP_CHARS_REGEX}week'?s?"
WEEKDAYS = (
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tues?|wed|thu|thurs?|fri|sat|sun"
)
TIME_PERIOD = r"am|pm"
