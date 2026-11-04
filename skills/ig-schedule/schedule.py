#!/usr/bin/env python3
"""
schedule.py - check a posting queue and turn it into calendar reminders.

You write the queue, one post per line. This prints it back in your own
timezone with the weekday next to each date, flags the things that go wrong
when you load a week into Instagram's scheduler, and (with --ics) writes a
calendar file you can import into Google Calendar, Outlook or Apple Calendar.

It does not post and it does not talk to Instagram. Nothing leaves your
machine. The calendar file is a set of reminders for you: one the day before
("load this into the Instagram scheduler") and one at go-live ("be around to
answer comments for 30 minutes").

Queue format (pipe separated, # starts a comment, blank lines ignored)

  2026-11-10 07:00 | REEL     | PROOF | Customer replies in 5 min | w1-tue-customer-replies.mp4 | captions/w1-tue.txt
  2026-11-12 19:30 | CAROUSEL | TEACH | 3 ChatGPT prompts for quotes | w1-thu-quotes.pdf

  fields: date time | format | type | title | asset | caption file (optional)
  format: REEL, CAROUSEL, POST or STORY
  type:   anything (PROOF, TEACH, OPINION, STORY, OFFER ...), used for the mix check
  caption file paths are relative to the queue file

Usage
  python3 schedule.py queue.txt
  python3 schedule.py queue.txt --tz Australia/Brisbane
  python3 schedule.py queue.txt --ics ~/.claude/instagram/schedule.ics
  python3 schedule.py queue.txt --json
  python3 schedule.py --best-times
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TZ = "Australia/Sydney"
FORMATS = {"REEL", "CAROUSEL", "POST", "STORY"}
CAPTION_LIMIT = 2200
HASHTAG_LIMIT = 5          # Instagram's cap since 18 December 2025
SCHEDULE_AHEAD_DAYS = 75   # how far ahead the Instagram app lets you schedule
HASHTAG_RE = re.compile(r"(?<![\w&])#\w+")

# Starting windows for an Australian small-business audience, in the
# audience's local time. A guess until the account has its own numbers:
# Professional dashboard > Total followers > Most active times.
BEST_TIMES = [
    ("06:30", "08:00", "before the shop opens, phone over coffee"),
    ("12:00", "13:00", "lunch break scroll"),
    ("19:00", "20:30", "after close, the strongest window for owners"),
]


def parse_queue(path):
    base = os.path.dirname(os.path.abspath(path)) if path != "-" else os.getcwd()
    text = sys.stdin.read() if path == "-" else open(path, encoding="utf-8").read()
    rows, errors = [], []
    for n, raw in enumerate(text.splitlines(), 1):
        # only whole-line comments: a '#' inside a title is part of the title
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 4:
            errors.append(f"line {n}: needs at least 'date time | format | type | title'")
            continue
        parts += [""] * (6 - len(parts))
        when, fmt, kind, title, asset, caption = parts[:6]
        try:
            naive = dt.datetime.strptime(when, "%Y-%m-%d %H:%M")
        except ValueError:
            errors.append(f"line {n}: '{when}' is not YYYY-MM-DD HH:MM")
            continue
        rows.append({
            "line": n, "naive": naive, "format": fmt.upper(), "type": kind.upper(),
            "title": title, "asset": asset,
            "caption_file": os.path.join(base, caption) if caption else "",
        })
    rows.sort(key=lambda r: r["naive"])
    return rows, errors


def in_best_window(local):
    hm = local.strftime("%H:%M")
    return any(a <= hm <= b for a, b, _ in BEST_TIMES)


def check(rows, tz, now):
    flags = []

    def flag(row, level, msg):
        flags.append({"line": row["line"] if row else None, "level": level, "msg": msg})

    feed = [r for r in rows if r["format"] != "STORY"]
    for r in rows:
        local = r["naive"].replace(tzinfo=tz)
        # A wall-clock time that does not exist (the hour skipped when daylight
        # saving starts) round-trips to a different hour.
        back = local.astimezone(dt.timezone.utc).astimezone(tz)
        if back.replace(tzinfo=None) != r["naive"]:
            flag(r, "FAIL", f"{r['naive']:%d %b %H:%M} does not exist in {tz.key}: "
                            "the clocks skip that hour for daylight saving")
        r["local"] = local
        r["utc"] = local.astimezone(dt.timezone.utc)
        if r["format"] not in FORMATS:
            flag(r, "FAIL", f"format '{r['format']}' is not one of {', '.join(sorted(FORMATS))}")
        if local < now:
            flag(r, "FAIL", "this time has already passed")
        elif local - now > dt.timedelta(days=SCHEDULE_AHEAD_DAYS):
            flag(r, "WARN", f"more than {SCHEDULE_AHEAD_DAYS} days out, "
                            "Instagram's scheduler will not take it yet")
        if not r["asset"]:
            flag(r, "WARN", "no asset named, so nothing to upload")
        if r["format"] != "STORY" and not in_best_window(local):
            flag(r, "INFO", f"{local:%H:%M} is outside the starting windows (--best-times). "
                            "Fine if your own Most active times say otherwise")
        if r["caption_file"]:
            if not os.path.exists(r["caption_file"]):
                flag(r, "FAIL", f"caption file not found: {r['caption_file']}")
            else:
                cap = open(r["caption_file"], encoding="utf-8").read().strip()
                r["caption"] = cap
                if len(cap) > CAPTION_LIMIT:
                    flag(r, "FAIL", f"caption is {len(cap)} characters, limit {CAPTION_LIMIT}")
                tags = HASHTAG_RE.findall(cap)
                if len(tags) > HASHTAG_LIMIT:
                    flag(r, "FAIL", f"{len(tags)} hashtags, Instagram's cap is {HASHTAG_LIMIT}")
                if re.search(r"https?://", cap):
                    flag(r, "INFO", "caption has a link, which is not clickable on Instagram. "
                                    "Use a Story link sticker or 'link in bio'")
        elif r["format"] != "STORY":
            flag(r, "WARN", "no caption file. Run /ig-caption before you load it")

    for a, b in zip(feed, feed[1:]):
        if a["format"] == b["format"] and a["type"] == b["type"]:
            flag(b, "WARN", f"same format and type as the post before it ({a['format']} {a['type']})")
        if a["naive"].date() == b["naive"].date():
            flag(b, "WARN", "second feed post on the same day, the two compete for the same people")
        gap = (b["utc"] - a["utc"]).total_seconds() / 3600
        if 0 <= gap < 4:
            flag(b, "WARN", f"only {gap:.1f}h after the previous post")

    # A week that crosses a daylight saving change is where 'same time as last
    # week' quietly moves by an hour for viewers in states that do not change.
    if rows:
        offsets = {r["local"].utcoffset() for r in rows}
        if len(offsets) > 1:
            flag(None, "WARN", f"this queue crosses a daylight saving change in {tz.key}. "
                               "Check each time in the scheduler, not just the first")

    if len(feed) > 0 and sum(1 for r in feed if r["format"] == "REEL") * 2 < len(feed):
        flag(None, "INFO", "fewer than half the feed posts are Reels. "
                           "Reels are the format that reaches non-followers")
    return flags


def ics_escape(s):
    return (s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
             .replace("\r\n", "\\n").replace("\n", "\\n"))


def fold(line):
    """RFC 5545 lines are folded at 75 octets."""
    out, raw = [], line.encode("utf-8")
    while len(raw) > 75:
        cut = 75 if not out else 74
        while cut > 0 and (raw[cut] & 0xC0) == 0x80:  # do not split a UTF-8 character
            cut -= 1
        out.append(raw[:cut].decode("utf-8"))
        raw = raw[cut:]
    out.append(raw.decode("utf-8"))
    return "\r\n ".join(out)


def write_ics(rows, path, stamp):
    fmt = "%Y%m%dT%H%M%SZ"
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//instagram-agent-skill//ig-schedule//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "X-WR-CALNAME:Instagram posting"]
    for r in rows:
        steps = [
            f"{r['format']} · {r['type']} · {r['title']}",
            f"Goes live {r['local']:%a %d %b %Y %H:%M %Z}",
            f"Asset: {r['asset'] or '(none named)'}",
            "",
            "Day before: load it into Instagram's own scheduler",
            "(app: Advanced settings > Schedule this post, or Meta Business Suite > Planner).",
            "At go-live: open the post and answer comments for 30 minutes.",
        ]
        if r.get("caption"):
            steps += ["", "CAPTION", r["caption"]]
        uid = uuid.uuid5(uuid.NAMESPACE_URL, f"ig-schedule:{r['naive'].isoformat()}:{r['title']}")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{stamp.strftime(fmt)}",
            f"DTSTART:{r['utc'].strftime(fmt)}",
            f"DTEND:{(r['utc'] + dt.timedelta(minutes=30)).strftime(fmt)}",
            f"SUMMARY:{ics_escape('IG ' + r['format'] + ': ' + r['title'])}",
            f"DESCRIPTION:{ics_escape(chr(10).join(steps))}",
            "BEGIN:VALARM", "ACTION:DISPLAY", "TRIGGER:-P1D",
            f"DESCRIPTION:{ics_escape('Load into the Instagram scheduler: ' + r['title'])}",
            "END:VALARM",
            "BEGIN:VALARM", "ACTION:DISPLAY", "TRIGGER:PT0M",
            f"DESCRIPTION:{ics_escape('Live now, answer comments for 30 min: ' + r['title'])}",
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    path = os.path.expanduser(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\r\n".join(fold(l) for l in lines) + "\r\n")
    return path


def print_best_times(tz):
    print(f"\nSTARTING WINDOWS  ·  {tz.key}  ·  audience local time")
    print("=" * 60)
    for a, b, why in BEST_TIMES:
        print(f"  {a}-{b}  {why}")
    print("-" * 60)
    print("  These are a starting guess. Once the account has followers,")
    print("  Professional dashboard > Total followers > Most active times")
    print("  is the real answer, and it beats this table.")
    print("  The hook matters more than the hour.\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("queue", nargs="?", help="queue file, or - for stdin")
    ap.add_argument("--tz", default=DEFAULT_TZ, help=f"audience timezone (default {DEFAULT_TZ})")
    ap.add_argument("--ics", help="write a calendar file of reminders to this path")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--best-times", action="store_true", help="print the starting posting windows")
    ap.add_argument("--now", help=argparse.SUPPRESS)  # for tests: YYYY-MM-DD HH:MM in --tz
    args = ap.parse_args()

    try:
        tz = ZoneInfo(args.tz)
    except ZoneInfoNotFoundError:
        sys.exit(f"unknown timezone '{args.tz}'. Try Australia/Sydney, Australia/Brisbane, Australia/Perth")

    if args.best_times:
        print_best_times(tz)
        if not args.queue:
            return
    if not args.queue:
        ap.error("give a queue file, or --best-times")

    now = (dt.datetime.strptime(args.now, "%Y-%m-%d %H:%M").replace(tzinfo=tz)
           if args.now else dt.datetime.now(tz))
    rows, errors = parse_queue(args.queue)
    flags = check(rows, tz, now)
    fails = sum(1 for f in flags if f["level"] == "FAIL") + len(errors)

    if args.json:
        print(json.dumps({
            "timezone": tz.key,
            "posts": [{"line": r["line"], "local": r["local"].isoformat(), "utc": r["utc"].isoformat(),
                       "format": r["format"], "type": r["type"], "title": r["title"],
                       "asset": r["asset"], "caption_file": r["caption_file"]} for r in rows],
            "errors": errors, "flags": flags,
        }, indent=2))
    else:
        print(f"\nPOSTING QUEUE  ·  {len(rows)} posts  ·  {tz.key}")
        print("=" * 78)
        by_line = {}
        for f in flags:
            by_line.setdefault(f["line"], []).append(f)
        for r in rows:
            mark = "!!" if any(f["level"] == "FAIL" for f in by_line.get(r["line"], [])) else "  "
            print(f"{mark} {r['local']:%a %d %b  %H:%M %Z}  {r['format']:<8} {r['type']:<8} {r['title'][:34]}")
            for f in by_line.get(r["line"], []):
                print(f"{'':6}{f['level']:<5} {f['msg']}")
        for e in errors:
            print(f"!! FAIL  {e}")
        print("-" * 78)
        for f in by_line.get(None, []):
            print(f"  {f['level']:<5} {f['msg']}")
        print(f"  {fails} to fix before loading" if fails else "  ready to load into the scheduler")

    if args.ics:
        failed = {f["line"] for f in flags if f["level"] == "FAIL"}
        good = [r for r in rows if r["line"] not in failed]
        if good:
            path = write_ics(good, args.ics, dt.datetime.now(dt.timezone.utc))
            if not args.json:
                skipped = len(rows) - len(good)
                print(f"  {len(good)} calendar reminders written to {path}"
                      + (f" ({skipped} with a FAIL left out)" if skipped else "") + "\n")

    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
