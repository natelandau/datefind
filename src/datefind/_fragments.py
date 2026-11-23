"""Raw regex fragments and lookup tables for datefind patterns."""

from enum import Enum


class FirstNumber(Enum):
    """Enum for the first number to find in ambiguous dates."""

    MONTH = "month"
    DAY = "day"
    YEAR = "year"


CENTURY = 20  # Used for years provided with two digits
SEP_CHARS = r"-\/:,._\+@ "  # Define separator chars for reuse
SEP_CLASS = rf"[{SEP_CHARS}]"
SEP_CHARS_REGEX = rf"{SEP_CLASS}*?"
DD_FLEXIBLE = r"[12][0-9]|3[01]|0?[1-9]"
DD = r"0[1-9]|[12][0-9]|3[01]"
MM = r"0[1-9]|1[012]"
MM_FLEXIBLE = r"1[012]|0?[1-9]"
YYYY = r"19\d\d|20\d\d"
YYYY_FLEXIBLE = rf"{YYYY}|\d\d"
JANUARY = r"january|jan"
FEBRUARY = r"february|feb"
MARCH = r"march|mar"
APRIL = r"april|apr"
MAY = r"may"
JUNE = r"june?"
JULY = r"july?"
AUGUST = r"august|aug"
SEPTEMBER = r"september|sept?"
OCTOBER = r"october|oct"
NOVEMBER = r"november|nov"
DECEMBER = r"december|dec"
MONTH = rf"{JANUARY}|{FEBRUARY}|{MARCH}|{APRIL}|{MAY}|{JUNE}|{JULY}|{AUGUST}|{SEPTEMBER}|{OCTOBER}|{NOVEMBER}|{DECEMBER}"
# In day order, which is also the pattern's alternation order. A space marks where
# compound ordinals accept a separator ("twenty first", "twenty-first", "twentyfirst").
_ORDINAL_DAY_WORDS_IN_ORDER = (
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
    "ninth",
    "tenth",
    "eleventh",
    "twelfth",
    "thirteenth",
    "fourteenth",
    "fifteenth",
    "sixteenth",
    "seventeenth",
    "eighteenth",
    "nineteenth",
    "twentieth",
    "twenty first",
    "twenty second",
    "twenty third",
    "twenty fourth",
    "twenty fifth",
    "twenty sixth",
    "twenty seventh",
    "twenty eighth",
    "twenty ninth",
    "thirtieth",
    "thirty first",
)
# Keyed by the word with separators removed
ORDINAL_DAY_NUMBERS: dict[str, int] = {
    word.replace(" ", ""): day
    for day, word in enumerate(iterable=_ORDINAL_DAY_WORDS_IN_ORDER, start=1)
}
ORDINAL_DAY_WORDS = "|".join(
    word.replace(" ", SEP_CHARS_REGEX) for word in _ORDINAL_DAY_WORDS_IN_ORDER
)
DIGIT_SUFFIXES = r"st|th|rd|nd"
TODAY = r"today'?s?"
YESTERDAY = r"yesterday'?s?"
TOMORROW = r"tomorrow'?s?"
# Offset, in units, of "<modifier> week", "<modifier> month", "<modifier> year"
PERIOD_MODIFIER_OFFSETS: dict[str, int] = {"last": -1, "next": 1, "this": 0}
UNAMBIGUOUS_WEEKDAYS = (
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tues?|thu|thurs?|fri"
)
# Also common English words, so they count as weekdays only after last, this, or next
WEEKDAY_ABBREVIATIONS_THAT_ARE_WORDS = r"wed|sat|sun"
WEEKDAYS = rf"{UNAMBIGUOUS_WEEKDAYS}|{WEEKDAY_ABBREVIATIONS_THAT_ARE_WORDS}"
QUARTER = r"[Qq][1-4]"
