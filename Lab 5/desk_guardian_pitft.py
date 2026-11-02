"""Desk Guardian morning report for the Adafruit Mini PiTFT 1.14" (240x135).

    python pitft_morning.py --log logs/night_log_real_2026-10-29_to_30.jsonl
    python pitft_morning.py --log logs/night_log_fake_30s.jsonl --no-ai

Button A: next page. Button B: previous page. Ctrl+C: exit.
"""
import argparse
import collections
import datetime
import json
import queue
import threading
import time

import requests
from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser()
parser.add_argument("--log", default="night_log.jsonl")
parser.add_argument("--model", default="qwen3.5:0.8b")
parser.add_argument("--no-ai", action="store_true")
parser.add_argument("--preview", action="store_true", help="save preview PNGs instead of using PiTFT")
args = parser.parse_args()

with open(args.log, encoding="utf-8") as f:
    entries = [json.loads(line) for line in f if line.strip()]

readings = [e for e in entries if "reading" in e]
seen = [e for e in readings if e["reading"] != "nobody" and not e["reading"].startswith("No person detected")]
beats = sum(1 for e in entries if e.get("alive"))
per_hour = collections.Counter(e["t"][:13] for e in seen)
start = datetime.datetime.fromisoformat(entries[0]["t"]) if entries else None
end = datetime.datetime.fromisoformat(entries[-1]["t"]) if entries else None
minutes = max(0, int((end - start).total_seconds() // 60)) if start and end else 0
duration = f"{minutes // 60}h {minutes % 60}m" if entries else "No data"
peak = max(per_hour, key=per_hour.get) if per_hour else None
peak_label = datetime.datetime.strptime(peak, "%Y-%m-%dT%H").strftime("%I %p").lstrip("0") if peak else None

FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
font = ImageFont.truetype(FONT_PATH, 11)
small = ImageFont.truetype(FONT_PATH, 10)
bold = ImageFont.truetype(BOLD_PATH, 12)
big = ImageFont.truetype(BOLD_PATH, 21)
BG, FG, MUTED, BLUE, GREEN, ORANGE = "#101827", "#f8fafc", "#9ca3af", "#8ec5ff", "#60d6a0", "#f6ad55"
WIDTH, HEIGHT = 240, 135


def wrap(message, text_font, width):
    result = []
    for paragraph in message.splitlines():
        current = ""
        for word in paragraph.split():
            candidate = word if not current else current + " " + word
            if text_font.getlength(candidate) <= width:
                current = candidate
            else:
                if current:
                    result.append(current)
                current = word
        if current:
            result.append(current)
    return result or ["No summary available."]


def factual_summary():
    if not entries or not readings:
        return "No detection readings were recorded. The log cannot establish whether activity occurred."
    if not seen:
        return "No person was detected in the recorded readings. This does not prove that no one was present."
    return f"There were {len(seen)} person-present detection changes. Most were logged near {peak_label}. The camera cannot identify people or confirm their activities."


summary_text = factual_summary() if args.no_ai or not seen else "Generating Qwen summary..."
summary_label = "FACTUAL SUMMARY" if args.no_ai or not seen else "QWEN SUMMARY (AI)"
updates = queue.Queue()


def request_summary():
    digest = "\n".join(f'{e["t"]} {e["reading"]}' for e in readings[-200:])
    prompt = f"""You are Desk Guardian. These are discrete camera detections, not confirmed activities.
{digest}
Write exactly three short factual sentences. Use timestamps only from the log.
Do not invent people, identities, actions, or events between readings.
Do not infer that a person left the room when a frame has no detection."""
    try:
        result = requests.post("http://localhost:11434/api/generate", json={
            "model": args.model, "prompt": prompt, "think": False, "stream": False,
            "options": {"num_ctx": 4096, "temperature": 0.2},
        }, timeout=600)
        result.raise_for_status()
        updates.put((result.json().get("response", "No AI summary returned."), "QWEN SUMMARY (AI)"))
    except requests.RequestException:
        updates.put(("Qwen unavailable. " + factual_summary(), "FACTUAL SUMMARY"))


def make_pages():
    wrapped = wrap(summary_text, font, WIDTH - 18)
    chunks = [wrapped[i:i + 5] for i in range(0, len(wrapped), 5)]
    return ["overview", "timeline"] + [("summary", chunk) for chunk in chunks]


def render(page, index, count):
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.text((9, 5), "DESK GUARDIAN", font=bold, fill=BLUE)
    draw.text((174, 7), f"{index + 1}/{count}", font=small, fill=MUTED)
    draw.line((9, 26, 231, 26), fill="#334155", width=1)

    if page == "overview":
        draw.text((9, 34), "GOOD MORNING", font=big, fill=FG)
        draw.text((9, 62), f"{duration} monitored", font=bold, fill=GREEN)
        draw.text((9, 82), f"{len(readings)} changes  |  {len(seen)} person logs", font=font, fill=FG)
        draw.text((9, 100), f"{beats} heartbeats", font=font, fill=MUTED)
    elif page == "timeline":
        draw.text((9, 32), "NIGHT TIMELINE", font=bold, fill=FG)
        if start and end:
            draw.text((9, 49), f"{start:%H:%M}  to  {end:%H:%M}", font=font, fill=MUTED)
            draw.line((14, 79, 225, 79), fill="#64748b", width=2)
            span = max((end - start).total_seconds(), 1)
            for e in readings:
                t = datetime.datetime.fromisoformat(e["t"])
                x = 14 + round(211 * (t - start).total_seconds() / span)
                color = GREEN if e in seen else ORANGE
                draw.ellipse((x - 2, 76, x + 2, 82), fill=color)
            if peak_label:
                draw.text((9, 93), f"Peak: {peak_label} ({per_hour[peak]} changes)", font=small, fill=FG)
            else:
                draw.text((9, 93), "No person detections logged", font=small, fill=FG)
        else:
            draw.text((9, 63), "No observations recorded", font=font, fill=MUTED)
    else:
        draw.text((9, 32), summary_label, font=bold, fill=FG)
        for i, line in enumerate(page[1]):
            draw.text((9, 51 + 14 * i), line, font=font, fill=FG)

    draw.line((9, 119, 231, 119), fill="#334155", width=1)
    draw.text((9, 122), "A: NEXT    B: BACK", font=small, fill=MUTED)
    return image


if not args.no_ai and seen:
    threading.Thread(target=request_summary, daemon=True).start()

if args.preview:
    for i, page in enumerate(make_pages()):
        render(page, i, len(make_pages())).save(f"pitft_preview_{i + 1}.png")
    print("Saved pitft_preview_*.png")
    raise SystemExit

import board
import digitalio
from adafruit_rgb_display import st7789

cs = None
dc = digitalio.DigitalInOut(board.D25)
display = st7789.ST7789(board.SPI(), cs=cs, dc=dc, rst=None,
                        baudrate=64000000, width=135, height=240,
                        x_offset=53, y_offset=40)
backlight = digitalio.DigitalInOut(board.D22)
backlight.switch_to_output(value=True)
button_a = digitalio.DigitalInOut(board.D23)
button_b = digitalio.DigitalInOut(board.D24)
button_a.switch_to_input()
button_b.switch_to_input()

page_index = 0
last_a = last_b = False
redraw = True
print("Mini PiTFT morning report running. A=Next B=Back Ctrl+C=Exit", flush=True)

try:
    while True:
        try:
            summary_text, summary_label = updates.get_nowait()
            redraw = True
        except queue.Empty:
            pass
        pages = make_pages()
        page_index %= len(pages)
        a, b = not button_a.value, not button_b.value
        if a and not last_a:
            page_index = (page_index + 1) % len(pages)
            redraw = True
        if b and not last_b:
            page_index = (page_index - 1) % len(pages)
            redraw = True
        last_a, last_b = a, b
        if redraw:
            display.image(render(pages[page_index], page_index, len(pages)), rotation=90)
            redraw = False
        time.sleep(0.08)
except KeyboardInterrupt:
    print("Mini PiTFT report stopped", flush=True)
finally:
    button_a.deinit()
    button_b.deinit()
    backlight.deinit()
    dc.deinit()
