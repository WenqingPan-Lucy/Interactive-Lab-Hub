import ast
import json
import re
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, date
SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))
from plan_dates import parse_plan_date, describe_date, calendar_answer
from weather_service import weather_answer
class Clock(datetime):
    @classmethod
    def now(cls):
        return cls(2026, 9, 30, 20, 12)
source = (SCRIPT_DIR / 'morning_assistant.py').read_text()
compile(source, 'morning_assistant.py', 'exec')
functions = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)]
ns = dict(re=re, json=json, datetime=Clock, timedelta=timedelta,
          weather_answer=weather_answer,
          parse_plan_date=parse_plan_date, describe_date=describe_date, calendar_answer=calendar_answer,
          conversation_state={})
exec(compile(ast.Module(body=functions, type_ignores=[]), 'morning_assistant.py', 'exec'), ns)
ns['reset_conversation_state']()
with tempfile.TemporaryDirectory() as tmp:
    ns['PLANS_FILE'] = Path(tmp) / 'plans.json'
    ns['PLANS_FILE'].write_text(json.dumps({'tomorrow': [{'task':'legacy task','time':None}]}))
    handle = ns['handle_user_input']
    before_clock = ns['PLANS_FILE'].read_text()
    for question in [
        'What time is it?', 'What time is it now?', "What's the time?",
        'What is the current time?', 'Could you please tell me what time it is?',
        'Can you tell me the time, please?',
    ]:
        assert handle(question) == "It's 8:12 PM.", question
    assert ns['PLANS_FILE'].read_text() == before_clock
    ns['conversation_state']['waiting_for_reminder_time'] = True
    assert handle('What time is it?') == "It's 8:12 PM."
    assert ns['conversation_state']['waiting_for_reminder_time'] is True
    ns['reset_conversation_state']()
    for hour, expected in [(0, "It's 12:00 AM."), (12, "It's 12:00 PM.")]:
        class BoundaryClock(datetime):
            @classmethod
            def now(cls):
                return cls(2026, 9, 30, hour, 0)
        ns['datetime'] = BoundaryClock
        assert handle('What time is it?') == expected
    ns['datetime'] = Clock
    for text in [
        'What date is it today?', 'What day is today?', 'What year is it?',
        'I also have a coach meeting at 11 a.m. on Friday.',
        'I need to submit homework on October 5 at 2 PM.',
        'Add a dentist appointment on January first.',
        'Could you add a class on the fifth of October 2027?',
        'What are my plans on Friday?', 'When is my coach meeting?',
        'What do I have tomorrow?',
    ]:
        print(text, '\n ', handle(text))
    data=json.loads(ns['PLANS_FILE'].read_text())
    assert data['2026-10-02'] == [{'task':'coach meeting','time':'11 AM'}], data
    assert data['2026-10-05'] == [{'task':'submit homework','time':'2 PM'}], data
    assert '2027-01-01' in data and '2027-10-05' in data
    assert 'tomorrow' not in data and data['2026-10-01'][0]['task']=='legacy task'
    assert '11 AM' in handle('What time is my coach meeting on Friday?')
    before=ns['PLANS_FILE'].read_text()
    assert 'not valid' in handle('Add homework on February 30')
    assert 'already passed' in handle('Add homework on September 1 2026')
    assert 'one date' in handle('I have a class Friday and I also have a meeting Monday')
    assert ns['PLANS_FILE'].read_text()==before
for text, expected in [('Friday','2026-10-02'), ('next Friday','2026-10-09'),
                       ('today','2026-09-30'), ('day after tomorrow','2026-10-02'),
                       ('February 29','2028-02-29'), ('12/31/2027','2027-12-31'),
                       ('2028-01-02','2028-01-02'), ('October twenty-first','2026-10-21')]:
    assert parse_plan_date(text, date(2026,9,30))[0].isoformat()==expected, text
print('All checks passed; real plans.json was not changed.')
