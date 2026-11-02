"""
Desk Guardian: Morning Reveal.

    python morning_reveal.py
    python morning_reveal.py --log logs/night_log_real_2026-10-29_to_30.jsonl
    python morning_reveal.py --model qwen3:0.6b
"""
import argparse
import collections
import datetime
import json
import queue
import threading
import tkinter as tk

import requests

parser = argparse.ArgumentParser()
parser.add_argument("--log", default="night_log.jsonl")
parser.add_argument("--model", default="qwen3.5:0.8b")
args = parser.parse_args()

with open(args.log, encoding="utf-8") as f:
    entries = [json.loads(line) for line in f if line.strip()]

readings = [e for e in entries if "reading" in e]
seen = [e for e in readings if e["reading"] != "nobody" and not e["reading"].startswith("No person detected")]
beats = sum(1 for e in entries if e.get("alive"))
per_hour = collections.Counter(e["t"][:10] + " " + e["t"][11:13] + ":00" for e in seen)

if entries:
    started = datetime.datetime.fromisoformat(entries[0]["t"])
    finished = datetime.datetime.fromisoformat(entries[-1]["t"])
    total_minutes = int((finished - started).total_seconds() // 60)
    duration = f"{total_minutes // 60}h {total_minutes % 60}m"
    span = f"{started:%b %d, %I:%M %p}  –  {finished:%b %d, %I:%M %p}"
else:
    duration = "0m"
    span = "No observations recorded"

if per_hour:
    peak = max(per_hour, key=per_hour.get)
    peak_time = datetime.datetime.strptime(peak, "%Y-%m-%d %H:%M")
    takeaway = f"Most person-present detection changes were logged around {peak_time:%b %d at %I:%M %p} ({per_hour[peak]} changes)."
else:
    takeaway = "No person-present detection changes were recorded."

root = tk.Tk()
root.title("Desk Guardian — Morning Reveal")
root.geometry("950x720")
root.configure(bg="#111827")

header = tk.Frame(root, bg="#111827")
header.pack(fill="x", padx=28, pady=(20, 10))
tk.Label(header, text="GOOD MORNING  ☀", font=("Arial", 22, "bold"), fg="#f9fafb", bg="#111827").pack(anchor="w")
tk.Label(header, text="Desk Guardian  •  " + span, font=("Arial", 11), fg="#9ca3af", bg="#111827").pack(anchor="w", pady=(5, 0))

cards = tk.Frame(root, bg="#111827")
cards.pack(fill="x", padx=28, pady=(5, 12))
for title, value in [("MONITORED", duration), ("STATE CHANGES", str(len(readings))), ("PERSON-PRESENT READINGS", str(len(seen))), ("HEARTBEATS", str(beats))]:
    card = tk.Frame(cards, bg="#1f2937", padx=13, pady=10)
    card.pack(side="left", expand=True, fill="x", padx=(0, 9))
    tk.Label(card, text=title, font=("Arial", 9), fg="#9ca3af", bg="#1f2937").pack(anchor="w")
    tk.Label(card, text=value, font=("Arial", 20, "bold"), fg="white", bg="#1f2937").pack(anchor="w")

tk.Label(root, text="MAIN TAKEAWAY", font=("Arial", 11, "bold"), fg="#93c5fd", bg="#111827").pack(anchor="w", padx=28)
tk.Label(root, text=takeaway, font=("Arial", 12), fg="#f9fafb", bg="#111827", wraplength=890, justify="left").pack(anchor="w", padx=28, pady=(5, 14))

tk.Label(root, text="DETECTION TIMELINE", font=("Arial", 11, "bold"), fg="#93c5fd", bg="#111827").pack(anchor="w", padx=28)
timeline_frame = tk.Frame(root, bg="#1f2937")
timeline_frame.pack(fill="both", expand=True, padx=28, pady=(7, 14))
timeline = tk.Text(timeline_frame, height=11, bg="#1f2937", fg="#e5e7eb", font=("Courier", 11), relief="flat", padx=14, pady=12, wrap="word")
scroll = tk.Scrollbar(timeline_frame, command=timeline.yview)
timeline.configure(yscrollcommand=scroll.set)
scroll.pack(side="right", fill="y")
timeline.pack(side="left", fill="both", expand=True)
for e in readings:
    timestamp = e["t"][5:19].replace("T", "  ")
    timeline.insert("end", f"{timestamp}   {e['reading']}\n\n")
if not readings:
    timeline.insert("end", "No detection changes were recorded.\n")
timeline.configure(state="disabled")

tk.Label(root, text="QWEN MORNING SUMMARY", font=("Arial", 11, "bold"), fg="#93c5fd", bg="#111827").pack(anchor="w", padx=28)
summary = tk.Text(root, height=5, bg="#1f2937", fg="#f9fafb", font=("Arial", 11), relief="flat", padx=14, pady=12, wrap="word")
summary.pack(fill="x", padx=28, pady=(7, 10))
summary.insert("end", "Generating summary..." if seen else "No person-present changes were logged. There is not enough evidence to describe any activity.")
summary.configure(state="disabled")

tk.Label(root, text="Detection results may contain errors. This system cannot identify people or infer their activities.", font=("Arial", 10), fg="#9ca3af", bg="#111827").pack(anchor="w", padx=28, pady=(0, 16))

results = queue.Queue()

def generate_summary():
    digest = "\n".join(f'{e["t"]} {e["reading"]}' for e in readings[-200:])
    prompt = f"""You are Desk Guardian, a desk-monitoring device. These are timestamped camera detections, not confirmed human activities.

{digest}

Write exactly three short sentences describing the recorded detections. Mention a specific time from the log. Do not invent timestamps, activities, identities, or movement events. Different detections do not prove different people, and a gap in readings does not prove nobody was there."""
    try:
        response = requests.post("http://localhost:11434/api/generate", json={
            "model": args.model,
            "prompt": prompt,
            "think": False,
            "stream": False,
            "options": {"num_ctx": 4096, "temperature": 0.2},
        }, timeout=600)
        response.raise_for_status()
        results.put(response.json().get("response", "No summary returned."))
    except requests.RequestException as error:
        results.put(f"Qwen could not generate a summary: {error}")

def show_summary():
    try:
        message = results.get_nowait()
    except queue.Empty:
        root.after(300, show_summary)
        return
    summary.configure(state="normal")
    summary.delete("1.0", "end")
    summary.insert("end", message)
    summary.configure(state="disabled")

if seen:
    threading.Thread(target=generate_summary, daemon=True).start()
    root.after(300, show_summary)

root.mainloop()
