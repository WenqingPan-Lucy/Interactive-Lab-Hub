"""New York City forecasts from Open-Meteo (https://open-meteo.com/)."""
import json
import math
import re
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from plan_dates import parse_plan_date, describe_date


def fetch_forecast():
    params = urlencode({
        'latitude': 40.7128, 'longitude': -74.0060,
        'timezone': 'America/New_York', 'forecast_days': 16,
        'temperature_unit': 'celsius',
        'current': 'temperature_2m,weather_code',
        'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max',
    })
    with urlopen('https://api.open-meteo.com/v1/forecast?' + params, timeout=10) as response:
        return json.load(response)


def condition(code):
    return {
        0: 'clear skies', 1: 'mainly clear skies', 2: 'partly cloudy skies',
        3: 'overcast skies', 45: 'fog', 48: 'freezing fog',
        51: 'light drizzle', 53: 'drizzle', 55: 'heavy drizzle',
        56: 'freezing drizzle', 57: 'heavy freezing drizzle',
        61: 'light rain', 63: 'rain', 65: 'heavy rain',
        66: 'freezing rain', 67: 'heavy freezing rain',
        71: 'light snow', 73: 'snow', 75: 'heavy snow', 77: 'snow grains',
        80: 'light rain showers', 81: 'rain showers', 82: 'heavy rain showers',
        85: 'snow showers', 86: 'heavy snow showers',
        95: 'thunderstorms', 96: 'thunderstorms with hail', 99: 'severe thunderstorms with hail',
    }.get(code, 'unavailable sky conditions')


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Missing weather measurement')
    return value


def weather_answer(text, today=None, fetch=None):
    """Return None for non-weather requests, or an English spoken response."""
    lower = text.lower()
    if not re.search(r'\b(weather|temperature|forecast|rain|raining|snow|snowing|hot|cold|sunny)\b', lower):
        return None
    # Do not intercept tasks or reminders which happen to mention weather.
    if re.search(r'\b(remind|reminder|add|i need|i have|i want|i should)\b', lower):
        return None
    if not re.search(r"\b(what|how|will|is|does|do|tell|weather|temperature|forecast)\b", lower):
        return None
    today = today or datetime.now(ZoneInfo('America/New_York')).date()
    if re.search(r'\b(yesterday|last week|last month)\b', lower):
        return 'I can look up forecasts for New York City, but not historical weather yet.'
    try:
        target, _ = parse_plan_date(text, today)
    except ValueError:
        return 'That date is not valid. Please give me a month and day.'
    if target is None and re.search(r'\b(next|this)\s+(week|month|year)|\bin\s+\d+\s+days?\b', lower):
        return 'Please give me a specific weekday or month and day for the New York City forecast.'
    target = target or today
    offset = (target - today).days
    if offset < 0:
        return 'I can look up forecasts for New York City, but not historical weather yet.'
    if offset >= 16:
        return 'I can only check New York City forecasts for today and the next 15 days. Please ask again closer to that date.'
    fahrenheit = 'fahrenheit' in lower
    unit = 'Fahrenheit' if fahrenheit else 'Celsius'
    def temperature(value):
        value = number(value)
        return f'{(value * 9 / 5 + 32) if fahrenheit else value:.0f} degrees {unit}'
    try:
        data = (fetch or fetch_forecast)()
        daily = data['daily']
        index = daily['time'].index(target.isoformat())
        high = temperature(daily['temperature_2m_max'][index])
        low = temperature(daily['temperature_2m_min'][index])
        sky = condition(daily['weather_code'][index])
        answer = f'In New York City on {describe_date(target)}, the forecast is {sky}, with a high of {high} and a low of {low}.'
        chance = daily.get('precipitation_probability_max', [None] * len(daily['time']))[index]
        if chance is not None:
            answer += f' The chance of precipitation is {number(chance):.0f} percent.'
        if target == today:
            current = data.get('current', {})
            # Only report current data if its New York date matches today.
            if str(current.get('time', '')).startswith(today.isoformat()) and current.get('temperature_2m') is not None:
                answer = f"In New York City, it is currently {temperature(current['temperature_2m'])}. " + answer
        return answer
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        print(f'Weather lookup failed: {type(exc).__name__}: {exc}')
        return "Sorry, I couldn't get the New York City weather right now. Please try again later."
