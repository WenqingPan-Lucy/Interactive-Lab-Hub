"""Offline forecast, failure and routing checks; no hardware required."""
import sys
from pathlib import Path
from datetime import date
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from weather_service import weather_answer

today = date(2026, 9, 30)
data = {
    'daily': {'time': ['2026-09-30', '2026-10-02'], 'weather_code': [0, 61],
              'temperature_2m_max': [22, 18], 'temperature_2m_min': [14, 10],
              'precipitation_probability_max': [0, 80]},
    'current': {'time': '2026-09-30T12:00', 'temperature_2m': 20},
}
def answer(text, payload=data):
    return weather_answer(text, today=today, fetch=lambda: payload)
assert 'currently 20 degrees Celsius' in answer("What's the weather today?")
for question in ['What is the temperature on Friday?', 'Will it rain on October 2?',
                 'How cold will it be on Friday?']:
    result = answer(question)
    assert 'October 2, 2026' in result and '18 degrees Celsius' in result
    assert '80 percent' in result and 'currently' not in result
assert '68 degrees Fahrenheit' in answer('What is the temperature in Fahrenheit?')
assert 'next 15 days' in answer('What is the weather on December 1?')
assert 'historical' in answer('What was the weather yesterday?')
assert 'not valid' in answer('What is the weather on February 30?')
assert 'specific weekday' in answer('What is the weather next week?')
for question in ['Add a weather report on Friday', 'Remind me to check the weather',
                 'What time is my meeting?', 'What day is today?']:
    assert answer(question) is None
for payload in [{}, {'daily': None}, {'daily': {'time': []}}]:
    assert "couldn't get" in answer('What is the weather?', payload)
def offline():
    raise TimeoutError('test timeout')
assert "couldn't get" in weather_answer('What is the weather?', today, offline)
print('Weather checks passed.')
