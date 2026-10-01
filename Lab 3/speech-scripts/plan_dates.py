"""Calendar parsing for the English voice assistant; no hardware dependencies."""

import calendar
import re
from datetime import date, timedelta


WEEKDAYS = {name.lower(): i for i, name in enumerate(calendar.day_name)}
MONTHS = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): i for i, name in enumerate(calendar.month_abbr) if name})
MONTHS['sept'] = 9
MONTH_PATTERN = '|'.join(sorted(MONTHS, key=len, reverse=True))
ORDINALS = dict(zip(
    'first second third fourth fifth sixth seventh eighth ninth tenth eleventh '
    'twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth '
    'nineteenth twentieth'.split(), range(1, 21)))
ORDINALS.update({'twenty first': 21, 'twenty second': 22, 'twenty third': 23,
                 'twenty fourth': 24, 'twenty fifth': 25, 'twenty sixth': 26,
                 'twenty seventh': 27, 'twenty eighth': 28, 'twenty ninth': 29,
                 'thirtieth': 30, 'thirty first': 31})


def parse_plan_date(text, today=None):
    """Return (date or None, text without date). Invalid dates raise ValueError.

    Bare weekdays mean the next occurrence including today; 'next Friday'
    means Friday in next calendar week. Yearless dates use the next occurrence.
    """
    today = today or date.today()
    text = text.lower()
    for ordinal in sorted(ORDINALS, key=len, reverse=True):
        text = re.sub(r'\b' + ordinal.replace(' ', r'[ -]') + r'\b',
                      str(ORDINALS[ordinal]), text)

    patterns = [
        ('iso', r'\b(?P<year>\d{4})-(?P<month>\d{1,2})-(?P<day>\d{1,2})\b'),
        ('named', rf'\b(?P<month>{MONTH_PATTERN})\.?\s+(?:the\s+)?(?P<day>\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(?P<year>\d{{4}}))?\b'),
        ('named', rf'\b(?:the\s+)?(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?(?P<month>{MONTH_PATTERN})\.?(?:,?\s+(?P<year>\d{{4}}))?\b'),
        ('numeric', r'\b(?P<month>\d{1,2})/(?P<day>\d{1,2})(?:/(?P<year>\d{4}))?\b'),
        ('relative', r'\b(day after tomorrow|tomorrow|today|tonight)\b'),
        ('weekday', r'\b(?:(next|this)\s+)?(' + '|'.join(WEEKDAYS) + r')\b'),
    ]
    for kind, pattern in patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        if kind == 'relative':
            offset = {'day after tomorrow': 2, 'tomorrow': 1, 'today': 0, 'tonight': 0}
            target = today + timedelta(days=offset[match[0]])
        elif kind == 'weekday':
            weekday = WEEKDAYS[match[2]]
            if match[1] == 'next':
                delta = 7 - today.weekday() + weekday
            elif match[1] == 'this':
                delta = weekday - today.weekday()
            else:
                delta = (weekday - today.weekday()) % 7
            target = today + timedelta(days=delta)
        else:
            month = MONTHS[match['month']] if kind == 'named' else int(match['month'])
            day = int(match['day'])
            year = int(match['year']) if match['year'] else today.year
            if match['year']:
                target = date(year, month, day)
            else:
                # Find the next valid occurrence, including leap day.
                date(2000, month, day)  # Reject impossible dates such as April 31.
                for candidate_year in range(year, year + 9):
                    try:
                        target = date(candidate_year, month, day)
                    except ValueError:
                        continue
                    if target >= today:
                        break
        before = re.sub(r'\b(?:on|for)\s*$', '', text[:match.start()])
        remainder = (before + ' ' + text[match.end():]).strip()
        return target, re.sub(r'\s+', ' ', remainder)
    return None, text


def describe_date(day):
    return f"{day:%A}, {day:%B} {day.day}, {day.year}"


def calendar_answer(text, today=None):
    today = today or date.today()
    text = text.lower().replace("what's", 'what is')
    if re.search(r'\b(what|which|tell)\b', text) and re.search(
        r'\b(date|day|year)\b', text
    ) and not re.search(r'\b(plan|plans|task|tasks|meeting|deadline|todo)\b', text):
        target, _ = parse_plan_date(text, today)
        if target is not None or re.search(r'\b(today|now|current|is it|are we)\b', text):
            return f"{'Today is' if target is None or target == today else 'That is'} {describe_date(target or today)}."
    return None
