#!/usr/bin/env python3

import json
import re
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from plan_dates import parse_plan_date, describe_date, calendar_answer
from weather_service import weather_answer

import numpy as np
import sherpa_onnx
import sounddevice as sd
from faster_whisper import WhisperModel

import board
import busio
import digitalio
import adafruit_mpr121

from PIL import Image, ImageDraw, ImageFont
from adafruit_rgb_display import st7789


# ============================================================
# CONFIGURATION
# ============================================================

SAMPLE_RATE = 16000

SCRIPT_DIR = Path(__file__).resolve().parent
LAB_DIR = SCRIPT_DIR.parent

VAD_MODEL = LAB_DIR / "models" / "silero_vad.onnx"

PLANS_FILE = SCRIPT_DIR / "plans.json"
REMINDERS_FILE = SCRIPT_DIR / "reminders.json"

VOICES_DIR = LAB_DIR / "voices"
PIPER_MODEL = "en_US-lessac-medium"

MIN_SILENCE = 0.7
MIN_SPEECH = 0.25

TOUCH_PAD = 6

SCREEN_WIDTH = 240
SCREEN_HEIGHT = 135
SCREEN_ROTATION = 90

AUDIO_LOCK = threading.Lock()
SCREEN_LOCK = threading.Lock()


# ============================================================
# SHORT-TERM CONVERSATION STATE
# ============================================================

conversation_state = {
    "waiting_for_reminder_time": False,
    "waiting_for_reminder_task": False,
    "pending_reminder_task": None,
    "pending_reminder_time": None,
}


def reset_conversation_state():

    conversation_state["waiting_for_reminder_time"] = False
    conversation_state["waiting_for_reminder_task"] = False
    conversation_state["pending_reminder_task"] = None
    conversation_state["pending_reminder_time"] = None


# ============================================================
# SCREEN
# ============================================================

def setup_screen():

    print("Initializing screen...")

    # Same pins as your working screen_boot_script.py
    cs_pin = digitalio.DigitalInOut(board.D5)
    dc_pin = digitalio.DigitalInOut(board.D25)

    spi = board.SPI()

    display = st7789.ST7789(
        spi,
        cs=cs_pin,
        dc=dc_pin,
        rst=None,
        baudrate=64000000,
        width=135,
        height=240,
        x_offset=53,
        y_offset=40,
    )

    backlight = digitalio.DigitalInOut(board.D22)
    backlight.switch_to_output()
    backlight.value = True

    print("Screen ready.")

    return display, backlight


def get_fonts():

    try:

        large_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            22
        )

        small_font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            15
        )

    except OSError:

        large_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    return large_font, small_font


def draw_centered_text(draw, text, y, font, fill="white"):

    bbox = draw.textbbox(
        (0, 0),
        text,
        font=font
    )

    text_width = bbox[2] - bbox[0]

    draw.text(
        (
            (SCREEN_WIDTH - text_width) // 2,
            y
        ),
        text,
        font=font,
        fill=fill
    )


def show_screen(display, state, detail=None):

    with SCREEN_LOCK:

        image = Image.new(
            "RGB",
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            "black"
        )

        draw = ImageDraw.Draw(image)

        large_font, small_font = get_fonts()


        # ----------------------------------------------------
        # IDLE
        # ----------------------------------------------------

        if state == "idle":

            draw.ellipse(
                (108, 20, 132, 44),
                outline="white",
                width=3
            )

            draw.ellipse(
                (115, 27, 125, 37),
                fill="white"
            )

            draw_centered_text(
                draw,
                "Touch to talk",
                78,
                large_font
            )


        # ----------------------------------------------------
        # LISTENING
        # ----------------------------------------------------

        elif state == "listening":

            # Microphone
            draw.rounded_rectangle(
                (108, 12, 132, 52),
                radius=10,
                outline="white",
                width=4
            )

            draw.arc(
                (98, 27, 142, 68),
                start=0,
                end=180,
                fill="white",
                width=4
            )

            draw.line(
                (120, 67, 120, 76),
                fill="white",
                width=4
            )

            draw.line(
                (108, 76, 132, 76),
                fill="white",
                width=4
            )

            draw_centered_text(
                draw,
                "Listening...",
                91,
                large_font
            )


        # ----------------------------------------------------
        # THINKING
        # ----------------------------------------------------

        elif state == "thinking":

            cx = 120
            cy = 42
            radius = 22

            draw.arc(
                (
                    cx - radius,
                    cy - radius,
                    cx + radius,
                    cy + radius
                ),
                start=25,
                end=305,
                fill="white",
                width=6
            )

            draw.ellipse(
                (139, 23, 147, 31),
                fill="white"
            )

            draw_centered_text(
                draw,
                "Thinking...",
                88,
                large_font
            )


        # ----------------------------------------------------
        # SPEAKING
        # ----------------------------------------------------

        elif state == "speaking":

            draw.polygon(
                [
                    (101, 35),
                    (111, 35),
                    (126, 23),
                    (126, 61),
                    (111, 49),
                    (101, 49)
                ],
                fill="white"
            )

            draw.arc(
                (121, 28, 147, 56),
                start=300,
                end=60,
                fill="white",
                width=3
            )

            draw_centered_text(
                draw,
                "Speaking...",
                88,
                large_font
            )


        # ----------------------------------------------------
        # REMINDER
        # ----------------------------------------------------

        elif state == "reminder":

            # Bell
            draw.arc(
                (104, 14, 136, 51),
                start=180,
                end=360,
                fill="white",
                width=4
            )

            draw.line(
                (104, 33, 104, 52),
                fill="white",
                width=4
            )

            draw.line(
                (136, 33, 136, 52),
                fill="white",
                width=4
            )

            draw.line(
                (102, 52, 138, 52),
                fill="white",
                width=4
            )

            draw.ellipse(
                (116, 55, 124, 63),
                fill="white"
            )

            draw_centered_text(
                draw,
                "Reminder",
                69,
                large_font
            )

            if detail:

                short_detail = detail[:32]

                draw_centered_text(
                    draw,
                    short_detail,
                    102,
                    small_font
                )


        display.image(
            image,
            SCREEN_ROTATION
        )


# ============================================================
# TOUCH SENSOR
# ============================================================

def setup_touch_sensor():

    print("Initializing touch sensor...")

    i2c = busio.I2C(
        board.SCL,
        board.SDA
    )

    sensor = adafruit_mpr121.MPR121(i2c)

    print("Touch sensor ready.")

    return sensor


def wait_for_touch(sensor):

    print("\n--------------------------------")
    print("IDLE")
    print("Touch pad 6 when you want to talk.")
    print("--------------------------------")

    while not sensor[TOUCH_PAD].value:
        time.sleep(0.05)

    print("\nTouch detected!")

    while sensor[TOUCH_PAD].value:
        time.sleep(0.05)

    time.sleep(0.2)


# ============================================================
# PLAN STORAGE
# ============================================================

def load_plans():

    if not PLANS_FILE.exists():
        return {}

    try:

        with open(PLANS_FILE, "r") as file:
            data = json.load(file)

        # Anchor legacy relative plans once, so they do not move every day.
        if "tomorrow" in data:
            key = (datetime.now().date() + timedelta(days=1)).isoformat()
            data.setdefault(key, []).extend(data.pop("tomorrow"))
            save_plans(data)

        return data

    except (json.JSONDecodeError, OSError):

        return {}


def save_plans(plans):

    with open(PLANS_FILE, "w") as file:

        json.dump(
            plans,
            file,
            indent=2
        )


# ============================================================
# REMINDER STORAGE
# ============================================================

def load_reminders():

    if not REMINDERS_FILE.exists():
        return []

    try:

        with open(REMINDERS_FILE, "r") as file:
            return json.load(file)

    except (json.JSONDecodeError, OSError):

        return []


def save_reminders(reminders):

    with open(REMINDERS_FILE, "w") as file:

        json.dump(
            reminders,
            file,
            indent=2
        )


# ============================================================
# TEXT TO SPEECH
# ============================================================

def speak(text):

    with AUDIO_LOCK:

        print(f"\nAssistant: {text}\n")

        piper_command = [
            sys.executable,
            "-m",
            "piper",
            "--model",
            PIPER_MODEL,
            "--data-dir",
            str(VOICES_DIR),
            "--output-raw",
            "--",
            text,
        ]

        piper = subprocess.Popen(
            piper_command,
            stdout=subprocess.PIPE
        )

        aplay = subprocess.Popen(
            [
                "aplay",
                "-r",
                "22050",
                "-f",
                "S16_LE",
                "-t",
                "raw",
                "-"
            ],
            stdin=piper.stdout
        )

        if piper.stdout:
            piper.stdout.close()

        aplay.communicate()
        piper.wait()


# ============================================================
# VOICE ACTIVITY DETECTION
# ============================================================

def build_vad():

    config = sherpa_onnx.VadModelConfig()

    config.silero_vad.model = str(
        VAD_MODEL
    )

    config.silero_vad.min_silence_duration = (
        MIN_SILENCE
    )

    config.silero_vad.min_speech_duration = (
        MIN_SPEECH
    )

    config.sample_rate = SAMPLE_RATE

    detector = sherpa_onnx.VoiceActivityDetector(
        config,
        buffer_size_in_seconds=30
    )

    return detector, config.silero_vad.window_size


# ============================================================
# LISTEN
# ============================================================

def listen_for_one_turn(vad, window):

    print("\nLISTENING...")
    print("Speak now.")

    buffer = np.empty(
        0,
        dtype=np.float32
    )

    samples_per_read = int(
        0.1 * SAMPLE_RATE
    )

    with sd.InputStream(
        channels=1,
        dtype="float32",
        samplerate=SAMPLE_RATE
    ) as stream:

        while True:

            chunk, _ = stream.read(
                samples_per_read
            )

            buffer = np.concatenate(
                [
                    buffer,
                    chunk.reshape(-1)
                ]
            )

            while len(buffer) > window:

                vad.accept_waveform(
                    buffer[:window]
                )

                buffer = buffer[window:]

            if not vad.empty():

                utterance = np.array(
                    vad.front.samples,
                    dtype=np.float32
                )

                vad.pop()

                print("Speech complete.")

                return utterance


# ============================================================
# TRANSCRIPTION
# ============================================================

def transcribe_audio(recognizer, utterance):

    start = time.perf_counter()

    segments, _ = recognizer.transcribe(
        utterance,
        beam_size=1
    )

    text = " ".join(
        segment.text.strip()
        for segment in segments
    )

    elapsed = time.perf_counter() - start

    print(
        f"Transcription time: {elapsed:.2f}s"
    )

    if text:
        print(f"You: {text}")

    return text


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_text(text):

    lower = text.lower().strip()

    normalized = re.sub(
        r"[^\w\s']",
        " ",
        lower
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized
    )

    return normalized.strip()


# ============================================================
# QUESTION DETECTION
# ============================================================

def detect_question(text, normalized):

    words = normalized.split()

    question_words = [
        "what",
        "when",
        "which",
        "where",
        "who",
        "how",
    ]

    question_phrases = [
        "do i",
        "did i",
        "should i",
        "can you tell me",
        "could you tell me",
        "would you tell me",
        "may i ask",
        "i was wondering",
        "i'm wondering",
        "i wonder",
    ]

    if "?" in text:
        return True

    if any(
        word in words
        for word in question_words
    ):
        return True

    if any(
        phrase in normalized
        for phrase in question_phrases
    ):
        return True

    return False


# ============================================================
# TODO TIME EXTRACTION
# ============================================================

def extract_time(text):

    cleaned = text.lower()

    # 11:30 AM / 11.30 AM
    match = re.search(
        r"\b(\d{1,2})"
        r"(?:(?::|\.)(\d{2}))?"
        r"\s*"
        r"(a\.?m\.?|p\.?m\.?)"
        r"\b",
        cleaned,
        re.IGNORECASE
    )

    if match:

        hour = int(match.group(1))
        minute = match.group(2)

        if not 1 <= hour <= 12:
            return None

        if minute is not None and int(minute) > 59:
            return None

        period = (
            match.group(3)
            .replace(".", "")
            .upper()
        )

        if minute:
            return f"{hour}:{minute} {period}"

        return f"{hour} {period}"


    # Whisper can produce 805 PM
    compact = re.search(
        r"\b(\d{3,4})\s*"
        r"(a\.?m\.?|p\.?m\.?)\b",
        cleaned,
        re.IGNORECASE
    )

    if compact:

        digits = compact.group(1)

        if len(digits) == 3:
            hour = int(digits[0])
            minute = int(digits[1:])

        else:
            hour = int(digits[:2])
            minute = int(digits[2:])

        if not 1 <= hour <= 12:
            return None

        if not 0 <= minute <= 59:
            return None

        period = (
            compact.group(2)
            .replace(".", "")
            .upper()
        )

        return f"{hour}:{minute:02d} {period}"

    return None


# ============================================================
# REMINDER TIME PARSER
# ============================================================

def parse_reminder_datetime(text):
    """
    Understands examples such as:

    8:05 PM
    8.05 PM
    805 PM
    805 tonight
    805 this evening
    805 tomorrow morning
    8 PM
    """

    cleaned = text.lower().strip()

    hour = None
    minute = None
    period = None


    # --------------------------------------------------------
    # 8:05 PM / 8.05 PM / 8 05 PM
    # --------------------------------------------------------

    match = re.search(
        r"\b(?:at\s+)?"
        r"(\d{1,2})"
        r"(?:(?::|\.|\s)(\d{2}))"
        r"\s*"
        r"(a\.?m\.?|p\.?m\.?)"
        r"\b",
        cleaned,
        re.IGNORECASE
    )

    if match:

        hour = int(match.group(1))
        minute = int(match.group(2))

        period = (
            match.group(3)
            .replace(".", "")
            .lower()
        )


    # --------------------------------------------------------
    # 805 PM / 1159 PM
    # --------------------------------------------------------

    if hour is None:

        compact = re.search(
            r"\b(\d{3,4})\s*"
            r"(a\.?m\.?|p\.?m\.?)\b",
            cleaned,
            re.IGNORECASE
        )

        if compact:

            digits = compact.group(1)

            if len(digits) == 3:

                hour = int(digits[0])
                minute = int(digits[1:])

            else:

                hour = int(digits[:2])
                minute = int(digits[2:])

            period = (
                compact.group(2)
                .replace(".", "")
                .lower()
            )


    # --------------------------------------------------------
    # 805 tonight
    # 805 this evening
    # 805 tomorrow morning
    # --------------------------------------------------------

    if hour is None:

        compact_no_period = re.search(
            r"\b(\d{3,4})\b",
            cleaned
        )

        if compact_no_period:

            digits = compact_no_period.group(1)

            if len(digits) == 3:

                hour = int(digits[0])
                minute = int(digits[1:])

            else:

                hour = int(digits[:2])
                minute = int(digits[2:])

            if (
                "tonight" in cleaned
                or "evening" in cleaned
                or "afternoon" in cleaned
            ):

                period = "pm"

            elif "morning" in cleaned:

                period = "am"

            else:

                # 805 by itself is ambiguous
                return None


    # --------------------------------------------------------
    # 8 PM
    # --------------------------------------------------------

    if hour is None:

        simple = re.search(
            r"\b(?:at\s+)?"
            r"(\d{1,2})\s*"
            r"(a\.?m\.?|p\.?m\.?)"
            r"\b",
            cleaned,
            re.IGNORECASE
        )

        if simple:

            hour = int(simple.group(1))
            minute = 0

            period = (
                simple.group(2)
                .replace(".", "")
                .lower()
            )


    # --------------------------------------------------------
    # 8 tonight / 8 this evening / 8 tomorrow morning
    # --------------------------------------------------------

    if hour is None:

        contextual = re.search(
            r"\b(?:at\s+)?(\d{1,2})\b",
            cleaned
        )

        if contextual:

            candidate_hour = int(
                contextual.group(1)
            )

            if (
                "tonight" in cleaned
                or "evening" in cleaned
                or "afternoon" in cleaned
            ):

                hour = candidate_hour
                minute = 0
                period = "pm"

            elif "morning" in cleaned:

                hour = candidate_hour
                minute = 0
                period = "am"


    # --------------------------------------------------------
    # NOTHING FOUND
    # --------------------------------------------------------

    if hour is None:
        return None


    # --------------------------------------------------------
    # VALIDATE
    # --------------------------------------------------------

    if not 1 <= hour <= 12:
        return None

    if minute is None:
        minute = 0

    if not 0 <= minute <= 59:
        return None

    if period not in ("am", "pm"):
        return None


    # --------------------------------------------------------
    # 12-HOUR -> 24-HOUR
    # --------------------------------------------------------

    if period == "pm" and hour != 12:
        hour += 12

    elif period == "am" and hour == 12:
        hour = 0


    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    now = datetime.now()

    if "tomorrow" in cleaned:

        target_date = (
            now + timedelta(days=1)
        ).date()

    else:

        target_date = now.date()


    target = datetime.combine(
        target_date,
        datetime.min.time()
    ).replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0
    )

    return target


# ============================================================
# CLEAN TODO TASK
# ============================================================

def clean_task(text):

    task = text.strip(" .,?!")


    # Conversational beginnings
    task = re.sub(
        r"^(okay|ok|hey|hello|hi)[,\s]+",
        "",
        task,
        flags=re.IGNORECASE
    )

    task = re.sub(
        r"^(also|and also)[,\s]+",
        "",
        task,
        flags=re.IGNORECASE
    )


    # First-person beginnings
    patterns = [
        r"^i also have an?\s+",
        r"^i have an?\s+",
        r"^i also need to\s+",
        r"^i need to\s+",
        r"^i also have to\s+",
        r"^i have to\s+",
        r"^i also want to\s+",
        r"^i want to\s+",
        r"^i should\s+",
        r"^add\s+",
    ]

    for pattern in patterns:

        task = re.sub(
            pattern,
            "",
            task,
            flags=re.IGNORECASE
        )


    # Remove normal times
    task = re.sub(
        r"\b(?:at\s+)?"
        r"\d{1,2}"
        r"(?:(?::|\.)\d{2})?"
        r"\s*"
        r"(?:a\.?m\.?|p\.?m\.?)"
        r"\b",
        "",
        task,
        flags=re.IGNORECASE
    )


    # Remove compact times like 805 PM
    task = re.sub(
        r"\b(?:at\s+)?"
        r"\d{3,4}\s*"
        r"(?:a\.?m\.?|p\.?m\.?)"
        r"\b",
        "",
        task,
        flags=re.IGNORECASE
    )


    # Date / daypart
    task = re.sub(
        r"\b(today|tomorrow|tonight)\b",
        "",
        task,
        flags=re.IGNORECASE
    )

    task = re.sub(
        r"\b(this\s+)?"
        r"(morning|afternoon|evening|night)\b",
        "",
        task,
        flags=re.IGNORECASE
    )


    # Scheduling words
    task = re.sub(
        r"\b(due|scheduled)\b",
        "",
        task,
        flags=re.IGNORECASE
    )


    task = re.sub(
        r"\s+",
        " ",
        task
    )

    return task.strip(" .,?!")


# ============================================================
# MULTIPLE TODO EXTRACTION
# ============================================================

def extract_multiple_tasks(text):

    # Split by punctuation first
    sentence_parts = re.split(
        r"[.!?]+",
        text
    )

    parts = []

    for sentence in sentence_parts:

        sentence = sentence.strip()

        if not sentence:
            continue

        # Split when "also" introduces another task
        subparts = re.split(
            r"\b(?:and\s+)?also\b",
            sentence,
            flags=re.IGNORECASE
        )

        for part in subparts:

            part = part.strip(" ,.")

            if part:
                parts.append(part)


    tasks = []

    for part in parts:

        normalized_part = normalize_text(
            part
        )

        task_markers = [
            "i have",
            "i need",
            "i want",
            "i should",
            "i must",
            "i've got",
        ]

        looks_like_task = any(
            marker in normalized_part
            for marker in task_markers
        )

        if not looks_like_task:
            continue

        task_time = extract_time(
            part
        )

        task_name = clean_task(
            part
        )

        if task_name:

            tasks.append(
                {
                    "task": task_name,
                    "time": task_time
                }
            )

    return tasks


# ============================================================
# REMINDER TASK EXTRACTION
# ============================================================

def extract_reminder_task(text):

    task = text.strip()


    # Polite beginning
    task = re.sub(
        r"^(can you|could you|would you|please)\s+",
        "",
        task,
        flags=re.IGNORECASE
    )


    # "set a reminder..."
    task = re.sub(
        r"^set\s+(?:a\s+)?reminder"
        r"(?:\s+for\s+me)?"
        r"(?:\s+to)?\s*",
        "",
        task,
        flags=re.IGNORECASE
    )


    # "remind me..."
    task = re.sub(
        r"^remind\s+me"
        r"(?:\s+that)?"
        r"(?:\s+to)?\s*",
        "",
        task,
        flags=re.IGNORECASE
    )


    # 8:05 PM / 8.05 PM
    task = re.sub(
        r"\b(?:at\s+)?"
        r"\d{1,2}"
        r"(?:(?::|\.|\s)\d{2})?"
        r"\s*"
        r"(?:a\.?m\.?|p\.?m\.?)"
        r"\b",
        "",
        task,
        flags=re.IGNORECASE
    )


    # 805 PM
    task = re.sub(
        r"\b(?:at\s+)?"
        r"\d{3,4}\s*"
        r"(?:a\.?m\.?|p\.?m\.?)"
        r"\b",
        "",
        task,
        flags=re.IGNORECASE
    )


    # 805 tonight / this evening / morning
    task = re.sub(
        r"\b(?:at\s+)?"
        r"\d{3,4}\s+"
        r"(?:(?:this\s+)?"
        r"(?:morning|afternoon|evening|night)"
        r"|tonight)"
        r"\b",
        "",
        task,
        flags=re.IGNORECASE
    )


    # 8 tonight / this evening
    task = re.sub(
        r"\b(?:at\s+)?"
        r"\d{1,2}\s+"
        r"(?:(?:this\s+)?"
        r"(?:morning|afternoon|evening|night)"
        r"|tonight)"
        r"\b",
        "",
        task,
        flags=re.IGNORECASE
    )


    # Date/daypart leftovers
    task = re.sub(
        r"\b(today|tomorrow|tonight)\b",
        "",
        task,
        flags=re.IGNORECASE
    )

    task = re.sub(
        r"\bthis\s+"
        r"(morning|afternoon|evening|night)\b",
        "",
        task,
        flags=re.IGNORECASE
    )


    # Clean
    task = re.sub(
        r"\s+",
        " ",
        task
    )

    task = task.strip(" .,?!")


    # Remove leftover leading "to"
    task = re.sub(
        r"^to\s+",
        "",
        task,
        flags=re.IGNORECASE
    )

    return task.strip(" .,?!")


# ============================================================
# CREATE REMINDER
# ============================================================

def create_reminder(task, reminder_time):

    reminders = load_reminders()

    reminders.append(
        {
            "task": task,
            "datetime": reminder_time.isoformat(),
            "triggered": False
        }
    )

    save_reminders(
        reminders
    )

    spoken_time = (
        reminder_time
        .strftime("%I:%M %p")
        .lstrip("0")
    )

    if (
        reminder_time.date()
        ==
        datetime.now().date()
    ):

        day_text = "today"

    else:

        day_text = "tomorrow"

    return (
        f"Okay. I'll remind you at "
        f"{spoken_time} {day_text} "
        f"to {task}."
    )


# ============================================================
# TOMORROW PLAN
# ============================================================

def get_tomorrow_plan(plans):

    tasks = plans.get(
        "tomorrow",
        []
    )

    if not tasks:

        return (
            "You don't have anything "
            "saved for tomorrow yet."
        )

    descriptions = []

    for task in tasks:

        task_name = task.get(
            "task",
            ""
        )

        task_time = task.get(
            "time"
        )

        if task_time:

            descriptions.append(
                f"{task_name} at {task_time}"
            )

        else:

            descriptions.append(
                task_name
            )


    if len(descriptions) == 1:

        summary = descriptions[0]

    elif len(descriptions) == 2:

        summary = (
            f"{descriptions[0]} "
            f"and {descriptions[1]}"
        )

    else:

        summary = (
            ", ".join(descriptions[:-1])
            + f", and {descriptions[-1]}"
        )

    return (
        f"Tomorrow, you have {summary}."
    )


# ============================================================
# DEADLINES
# ============================================================

def get_deadlines(plans):

    tasks = plans.get(
        "tomorrow",
        []
    )

    if not tasks:

        return (
            "You don't have any tasks "
            "saved for tomorrow."
        )

    timed_tasks = [
        task
        for task in tasks
        if task.get("time")
    ]

    if not timed_tasks:

        return (
            "You have tasks saved for tomorrow, "
            "but I don't have specific times "
            "for them."
        )

    descriptions = []

    for task in timed_tasks:

        descriptions.append(
            f"{task['task']} "
            f"at {task['time']}"
        )

    if len(descriptions) == 1:

        summary = descriptions[0]

    elif len(descriptions) == 2:

        summary = (
            f"{descriptions[0]} "
            f"and {descriptions[1]}"
        )

    else:

        summary = (
            ", ".join(descriptions[:-1])
            + f", and {descriptions[-1]}"
        )

    return (
        f"Your timed tasks for tomorrow are "
        f"{summary}."
    )


# ============================================================
# FIND SPECIFIC TASK TIME
# ============================================================

def find_task_time(normalized, plans):

    tasks = plans.get(
        "tomorrow",
        []
    )

    for task in tasks:

        task_name = task.get(
            "task",
            ""
        )

        important_words = [
            word.lower()

            for word in task_name.split()

            if len(word) >= 4
        ]

        if any(
            word in normalized
            for word in important_words
        ):

            if task.get("time"):

                return (
                    f"{task_name} is scheduled "
                    f"for {task['time']} tomorrow."
                )

            return (
                f"You saved {task_name} "
                f"for tomorrow, "
                f"but I don't have "
                f"a specific time."
            )

    return (
        "I couldn't find that task "
        "in tomorrow's plan."
    )


# ============================================================
# REMINDER BACKGROUND WORKER
# ============================================================

def reminder_worker(display):

    while True:

        reminders = load_reminders()

        now = datetime.now()

        changed = False

        for reminder in reminders:

            if reminder.get(
                "triggered",
                False
            ):
                continue

            try:

                reminder_time = (
                    datetime.fromisoformat(
                        reminder["datetime"]
                    )
                )

            except (
                ValueError,
                KeyError
            ):

                continue


            if now >= reminder_time:

                reminder["triggered"] = True
                changed = True

                task = reminder.get(
                    "task",
                    "your task"
                )

                print(
                    "\n================================"
                )

                print(
                    f"REMINDER: {task}"
                )

                print(
                    "================================"
                )

                show_screen(
                    display,
                    "reminder",
                    task
                )

                speak(
                    f"Wenqing, it's time to {task}."
                )

                time.sleep(2)

                show_screen(
                    display,
                    "idle"
                )


        if changed:

            save_reminders(
                reminders
            )

        time.sleep(1)


# ============================================================
# MAIN CONVERSATION LOGIC
# ============================================================

def current_time_answer(normalized):
    """Recognize clock questions without consuming task-time questions."""
    question = normalized.replace("what's", "what is").strip()
    pattern = (
        r"(?:(?:hey|hello|hi)\s+)?"
        r"(?:(?:can|could|would) you\s+)?"
        r"(?:please\s+)?"
        r"(?:tell me\s+)?"
        r"(?:what time (?:is it|it is)|"
        r"what is the (?:current |local )?time|"
        r"the (?:current |local )?time)"
        r"(?:\s+(?:right now|now|currently))?"
        r"(?:\s+please)?"
    )
    if re.fullmatch(pattern, question):
        spoken_time = datetime.now().strftime("%I:%M %p").lstrip("0")
        return f"It's {spoken_time}."
    return None


def handle_user_input(text):

    global conversation_state

    normalized = normalize_text(
        text
    )

    words = normalized.split()

    # Answer clock questions even during a reminder follow-up, keeping its state.
    time_answer = current_time_answer(normalized)
    if time_answer:
        return time_answer

    forecast_answer = weather_answer(text)
    if forecast_answer:
        return forecast_answer


    # ========================================================
    # 1. FOLLOW-UP:
    # WAITING FOR REMINDER TIME
    # ========================================================

    if conversation_state[
        "waiting_for_reminder_time"
    ]:

        reminder_time = (
            parse_reminder_datetime(
                text
            )
        )

        if reminder_time is None:

            return (
                "I still didn't catch the time. "
                "You can say something like "
                "8:05 PM or 8:05 this evening."
            )


        if reminder_time <= datetime.now():

            return (
                "That time has already passed. "
                "Please give me a later time."
            )


        task = conversation_state[
            "pending_reminder_task"
        ]

        reset_conversation_state()

        return create_reminder(
            task,
            reminder_time
        )


    # ========================================================
    # 2. FOLLOW-UP:
    # WAITING FOR REMINDER TASK
    # ========================================================

    if conversation_state[
        "waiting_for_reminder_task"
    ]:

        reminder_time = conversation_state[
            "pending_reminder_time"
        ]

        task = text.strip(
            " .,?!"
        )

        task = re.sub(
            r"^(remind me to|please remind me to|to)\s+",
            "",
            task,
            flags=re.IGNORECASE
        )

        task = task.strip(
            " .,?!"
        )

        if not task:

            return (
                "I didn't catch what you want "
                "me to remind you about."
            )

        reset_conversation_state()

        return create_reminder(
            task,
            reminder_time
        )


    # ========================================================
    # QUESTION?
    # ========================================================

    is_question = detect_question(
        text,
        normalized
    )


    # ========================================================
    # 3. NEW REMINDER REQUEST
    # ========================================================

    reminder_phrases = [
        "remind me",
        "set a reminder",
        "set reminder",
    ]

    wants_reminder = any(
        phrase in normalized
        for phrase in reminder_phrases
    )

    if wants_reminder:

        reminder_time = (
            parse_reminder_datetime(
                text
            )
        )

        reminder_task = (
            extract_reminder_task(
                text
            )
        )


        meaningless_tasks = [
            "",
            "for me",
            "a reminder",
            "reminder",
        ]

        has_task = (
            reminder_task
            .lower()
            .strip()
            not in meaningless_tasks
        )

        has_time = (
            reminder_time is not None
        )


        # ----------------------------------------------------
        # HAVE BOTH TASK + TIME
        # ----------------------------------------------------

        if has_task and has_time:

            if reminder_time <= datetime.now():

                return (
                    "That time has already passed. "
                    "Please give me a later time."
                )

            reset_conversation_state()

            return create_reminder(
                reminder_task,
                reminder_time
            )


        # ----------------------------------------------------
        # HAVE TASK, MISSING TIME
        # ----------------------------------------------------

        if has_task and not has_time:

            reset_conversation_state()

            conversation_state[
                "pending_reminder_task"
            ] = reminder_task

            conversation_state[
                "waiting_for_reminder_time"
            ] = True

            return (
                "Sure. What time would you like "
                "me to remind you?"
            )


        # ----------------------------------------------------
        # HAVE TIME, MISSING TASK
        # ----------------------------------------------------

        if has_time and not has_task:

            reset_conversation_state()

            conversation_state[
                "pending_reminder_time"
            ] = reminder_time

            conversation_state[
                "waiting_for_reminder_task"
            ] = True

            return (
                "Sure. What would you like "
                "me to remind you about?"
            )


        # ----------------------------------------------------
        # MISSING BOTH
        # ----------------------------------------------------

        return (
            "Sure. What would you like "
            "me to remind you about, and when?"
        )


    # ========================================================
    # 4. CASUAL RESPONSES
    # ========================================================

    casual_phrases = [
        "thank you",
        "thanks",
        "sounds good",
        "that's good",
        "that is good",
        "that's not too much",
        "that is not too much",
        "okay thanks",
        "ok thanks",
    ]

    if any(
        phrase in normalized
        for phrase in casual_phrases
    ):

        return "You're welcome."


    # Resolve calendar questions and dated plans from the Pi's local date.
    try:
        answer = calendar_answer(text, datetime.now().date())
        if answer:
            return answer
        target_date, task_text = parse_plan_date(text, datetime.now().date())
    except ValueError:
        return "That date is not valid. Please give me a month, day, and optional year."

    plans = load_plans()
    add_patterns = [
        "i need to ", "i have to ", "i want to ", "i should ",
        "i have a ", "i have an ", "i also have ", "i also need ",
        "add ", "i must ", "i've got ",
    ]
    wants_to_add = any(pattern in normalized for pattern in add_patterns)
    # Polite requests such as "Can you add ...?" are still additions.
    if re.match(r"^(?:can you|could you|please)\s+(?:please\s+)?add\b", normalized):
        wants_to_add = True
        is_question = False
        task_text = re.sub(r"^(?:can you|could you|please)\s+(?:please\s+)?",
                           "", task_text, flags=re.IGNORECASE)

    if wants_to_add and not is_question:
        if target_date is None:
            return "Which date? Please include today, a weekday, or a month and day with your task."
        if target_date < datetime.now().date():
            return "That date has already passed. Please choose today or a future date."
        # Avoid silently assigning a second task's explicit date to the first.
        try:
            extra_date, _ = parse_plan_date(task_text, datetime.now().date())
        except ValueError:
            return "Please add tasks for one date at a time."
        if extra_date is not None:
            return "Please add tasks for one date at a time."
        # Protect a.m./p.m. and decimal clock times from sentence splitting.
        task_text = re.sub(r"\b([ap])\.m\.?", r"\1m", task_text, flags=re.IGNORECASE)
        task_text = re.sub(r"(?<=\d)\.(?=\d{2}\b)", ":", task_text)
        extracted_tasks = extract_multiple_tasks(task_text)
        if not extracted_tasks:
            task_name = clean_task(task_text)
            if task_name:
                extracted_tasks = [{"task": task_name, "time": extract_time(task_text)}]
        if not extracted_tasks:
            return "I didn't catch the task. Please say the task and date again."
        plans.setdefault(target_date.isoformat(), []).extend(extracted_tasks)
        save_plans(plans)
        descriptions = [
            task["task"] + (f" at {task['time']}" if task.get("time") else "")
            for task in extracted_tasks
        ]
        return f"Got it. I added {' and '.join(descriptions)} for {describe_date(target_date)}."

    if is_question:
        if target_date is None:
            if "when" in words or "what time" in normalized:
                matches = []
                for key, tasks in sorted(plans.items()):
                    for task in tasks:
                        important = [w for w in normalize_text(task.get("task", "")).split() if len(w) >= 4]
                        if any(w in words for w in important):
                            matches.append(f"{task['task']} on {key}" +
                                           (f" at {task['time']}" if task.get("time") else ""))
                return ("; ".join(matches) + ".") if matches else "I couldn't find that task in your plans."
            target_date = datetime.now().date()
        tasks = plans.get(target_date.isoformat(), [])
        if "deadline" in normalized:
            tasks = [task for task in tasks if task.get("time")]
        if "when" in words or "what time" in normalized:
            tasks = [task for task in tasks if any(
                word in words for word in normalize_text(task.get("task", "")).split() if len(word) >= 4
            )]
        if not tasks:
            return f"You have no matching tasks saved for {describe_date(target_date)}."
        descriptions = [task["task"] + (f" at {task['time']}" if task.get("time") else "") for task in tasks]
        return f"On {describe_date(target_date)}, you have {' and '.join(descriptions)}."

    # ========================================================
    # 9. UNCLEAR
    # ========================================================

    return (
        "I'm not sure whether you want "
        "to add a task, set a reminder, "
        "or ask about your plan. "
        "Could you please repeat or rephrase?"
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not VAD_MODEL.is_file():

        sys.exit(
            f"VAD model not found at "
            f"{VAD_MODEL}. "
            f"Run setup.sh first."
        )


    print(
        "\n"
        "================================\n"
        "       MORNING ASSISTANT\n"
        "================================\n"
    )


    # --------------------------------------------------------
    # SCREEN
    # --------------------------------------------------------

    display, backlight = setup_screen()

    show_screen(
        display,
        "idle"
    )


    # --------------------------------------------------------
    # TOUCH
    # --------------------------------------------------------

    sensor = setup_touch_sensor()


    # --------------------------------------------------------
    # WHISPER
    # --------------------------------------------------------

    print(
        "Loading speech recognition model..."
    )

    recognizer = WhisperModel(
        "tiny.en",
        device="cpu",
        compute_type="int8"
    )


    # --------------------------------------------------------
    # VAD
    # --------------------------------------------------------

    vad, window = build_vad()


    print(
        "\nMorning Assistant is ready."
    )

    print(
        f"Endpointing after "
        f"{MIN_SILENCE} seconds "
        f"of silence."
    )


    # --------------------------------------------------------
    # REMINDER THREAD
    # --------------------------------------------------------

    reminder_thread = threading.Thread(
        target=reminder_worker,
        args=(display,),
        daemon=True
    )

    reminder_thread.start()

    print(
        "Reminder service is running."
    )


    # --------------------------------------------------------
    # GREETING
    # --------------------------------------------------------

    show_screen(
        display,
        "speaking"
    )

    speak(
        "Hello Wenqing. "
        "Touch the sensor "
        "when you want to talk."
    )


    # ========================================================
    # MAIN INTERACTION LOOP
    # ========================================================

    while True:

        # IDLE
        show_screen(
            display,
            "idle"
        )

        wait_for_touch(
            sensor
        )


        # LISTEN
        show_screen(
            display,
            "listening"
        )

        utterance = listen_for_one_turn(
            vad,
            window
        )


        # THINK
        show_screen(
            display,
            "thinking"
        )

        print(
            "\nTHINKING..."
        )

        text = transcribe_audio(
            recognizer,
            utterance
        )


        # Nothing recognized
        if not text.strip():

            print(
                "No speech recognized. "
                "Returning to idle."
            )

            show_screen(
                display,
                "idle"
            )

            continue


        # Understand
        response = handle_user_input(
            text
        )


        # Speak
        show_screen(
            display,
            "speaking"
        )

        speak(
            response
        )


        # Idle
        show_screen(
            display,
            "idle"
        )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print(
            "\nMorning Assistant stopped."
        )
