#!/usr/bin/env python3
"""
schedule.py - the posting queue: check it, print the week, and turn it into
calendar reminders.

Nothing in here posts to Instagram. It reads a queue file the other skills
write, tells you what is wrong with it before the week starts, and writes an
.ics file your own calendar (Google, Outlook, Apple) can import, so your phone
reminds you to post and then reminds you to stay for the first hour of
comments.

The queue is a JSON list. Each entry is one post:

  {
    "id": "w46-tue-reel",
    "when": "2026-11-10 07:30",          local time, in the queue's timezone
    "format": "reel",                      reel | carousel | image | story
    "pillar": "teach",                     proof | teach | opinion | story | offer
    "title": "3 AI replies that save 5 hours",
    "hook": "#5 Time Collapse",
    "asset": "D:/ShortsForge/out/w46-tue.mp4",
    "caption": "captions/w46-tue.txt",     path to the caption text, or the text
    "status": "ready"                      idea | drafted | ready | scheduled | posted
  }

The file can also be an object: {"timezone": "Australia/Sydney", "posts": [...]}.

Usage
  python3 schedule.py check queue.json
  python3 schedule.py week  queue.json [--from 2026-11-09] [--days 7]
  python3 schedule.py next  queue.json
  python3 schedule.py ics   queue.json --out week.ics [--remind 30] [--engage 60]
  python3 schedule.py mark  queue.json w46-tue-reel posted

Timezone
  --tz overrides the queue's timezone. The default is Australia/Sydney, which
  handles AEDT and AEST changeover for you. On Windows, Python's zoneinfo needs
  the tzdata package (pip install tzdata). Without it, pass a fixed offset with
  --offset +11:00 and remember it will not follow daylight saving.
"""

import argparse
import datetime as dt
import json
import os
import re
import sys
import uuid

DEFAULT_TZ = "Australia/Sydney"
FORMATS = {"reel", "carousel", "image", "story"}
PILLARS = {"proof", "teach", "opinion", "story", "offer"}
STATUSES = ["idea", "drafted", "ready", "scheduled", "posted"]
HASHTAG_LIMIT = 5        # Instagram's per-post cap since 18 Dec 2025.
CAPTION_LIMIT = 2200
HASHTAG_RE = re.compile(r"(?:^|\s)#[A-Za-z0-9_]+")
MIN_GAP_HOURS = 12       # Two feed posts closer than this split their own reach.


# ---------------------------------------------------------------- loading

def load(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, list):
        return {"timezone": None, "posts": data}
    if isinstance(data, dict) and isinstance(data.get("posts"), list):
        return data
    sys.exit(f"{path}: expected a list of posts or an object with a 'posts' list")


def save(path, data, original_was_list):
    out = data["posts"] if original_was_list else data
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def resolve_tz(name, offset):
    if offset:
        m = re.fullmatch(r"([+-])(\d{1,2}):?(\d{2})", offset.strip())
        if not m:
            sys.exit(f"--offset {offset!r}: use the form +11:00")
        sign = 1 if m.group(1) == "+" else -1
        delta = dt.timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
        return dt.timezone(sign * delta, f"UTC{offset}")
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(name)
    except Exception:
        sys.exit(
            f"Cannot load timezone {name!r}. On Windows run: pip install tzdata\n"
            f"Or pass a fixed offset instead, for example --offset +11:00"
        )


def parse_when(value, tz):
    if not value:
        return None
    text = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            naive = dt.datetime.strptime(text, fmt)
            return naive.replace(tzinfo=tz)
        except ValueError:
            continue
    return None


def caption_text(post, base_dir):
    cap = post.get("caption")
    if not cap:
        return None
    candidate = cap if os.path.isabs(cap) else os.path.join(base_dir, cap)
    if len(cap) < 260 and "\n" not in cap and os.path.isfile(candidate):
        with open(candidate, encoding="utf-8") as fh:
            return fh.read()
    if re.search(r"\.(txt|md)$", cap) and "\n" not in cap:
        return ""   # looks like a path that does not exist
    return cap


# ---------------------------------------------------------------- checks

def check(data, tz, base_dir, now):
    """Return (errors, warnings) as lists of strings."""
    errors, warnings = [], []
    posts = data["posts"]
    seen = set()
    dated = []

    for i, p in enumerate(posts):
        pid = p.get("id") or f"#{i + 1}"
        where = f"[{pid}]"
        if p.get("id") in seen:
            errors.append(f"{where} duplicate id")
        seen.add(p.get("id"))

        fmt = (p.get("format") or "").lower()
        if fmt not in FORMATS:
            errors.append(f"{where} format {p.get('format')!r} is not one of {', '.join(sorted(FORMATS))}")
        pillar = (p.get("pillar") or "").lower()
        if pillar and pillar not in PILLARS:
            warnings.append(f"{where} pillar {pillar!r} is not one of {', '.join(sorted(PILLARS))}")
        status = (p.get("status") or "idea").lower()
        if status not in STATUSES:
            errors.append(f"{where} status {status!r} is not one of {', '.join(STATUSES)}")

        when = parse_when(p.get("when"), tz)
        if p.get("when") and when is None:
            errors.append(f"{where} cannot read time {p.get('when')!r}, use YYYY-MM-DD HH:MM")
        if when is None:
            if status in ("ready", "scheduled"):
                errors.append(f"{where} is {status} but has no time")
            continue
        dated.append((when, p, pid))

        if when < now and status != "posted":
            warnings.append(f"{where} was due {when:%a %d %b %H:%M} and is still '{status}'")

        if when >= now and status in ("ready", "scheduled") and fmt != "story":
            if not p.get("asset"):
                errors.append(f"{where} is {status} but has no asset")
            elif not re.match(r"^[A-Za-z]:[\\/]", p["asset"]) and not os.path.exists(
                    p["asset"] if os.path.isabs(p["asset"]) else os.path.join(base_dir, p["asset"])):
                warnings.append(f"{where} asset not found from here: {p['asset']}")
            text = caption_text(p, base_dir)
            if text is None:
                errors.append(f"{where} is {status} but has no caption")
            elif text == "":
                errors.append(f"{where} caption file not found: {p.get('caption')}")
            else:
                tags = len(HASHTAG_RE.findall(text))
                if tags > HASHTAG_LIMIT:
                    errors.append(f"{where} caption has {tags} hashtags, the cap is {HASHTAG_LIMIT}")
                if len(text) > CAPTION_LIMIT:
                    errors.append(f"{where} caption is {len(text)} characters, the limit is {CAPTION_LIMIT}")
                if "{{" in text:
                    errors.append(f"{where} caption still has a {{{{placeholder}}}} in it")

        if status in ("drafted", "idea") and when >= now and when - now < dt.timedelta(hours=24):
            warnings.append(f"{where} goes out in under 24h and is only '{status}'")

    feed = sorted([d for d in dated if (d[1].get("format") or "").lower() != "story"],
                  key=lambda d: d[0])
    for (a, pa, ia), (b, pb, ib) in zip(feed, feed[1:]):
        gap = (b - a).total_seconds() / 3600
        if gap < MIN_GAP_HOURS:
            warnings.append(f"[{ia}] and [{ib}] are {gap:.1f}h apart. Feed posts this close split their own reach")
        fa, fb = (pa.get("format") or "").lower(), (pb.get("format") or "").lower()
        pla, plb = (pa.get("pillar") or "").lower(), (pb.get("pillar") or "").lower()
        if pla and pla == plb:
            warnings.append(f"[{ia}] and [{ib}] are both {pla} back to back")

    # Weekly shape, per ISO week, for future weeks that have anything in them.
    weeks = {}
    for when, p, pid in feed:
        if when >= now - dt.timedelta(days=7):
            weeks.setdefault(when.isocalendar()[:2], []).append(p)
    for (year, week), items in sorted(weeks.items()):
        reels = sum(1 for p in items if (p.get("format") or "").lower() == "reel")
        if len(items) > 7:
            warnings.append(f"week {week}: {len(items)} feed posts. Four or five done well beats seven")
        if len(items) >= 3 and reels < 3:
            warnings.append(f"week {week}: {reels} reel(s) of {len(items)} posts. Reels are what reach non-followers; aim for three")

    return errors, warnings


# ---------------------------------------------------------------- views

def label(p):
    fmt = (p.get("format") or "?").upper()
    pillar = (p.get("pillar") or "").upper()
    hook = p.get("hook") or ""
    return f"{fmt:<9} {pillar:<8} {hook:<20} {p.get('title') or ''}".rstrip()


def cmd_week(data, tz, start, days):
    end = start + dt.timedelta(days=days)
    items = []
    for p in data["posts"]:
        when = parse_when(p.get("when"), tz)
        if when and start <= when < end:
            items.append((when, p))
    items.sort(key=lambda x: x[0])
    print(f"WEEK OF {start:%a %d %b %Y}  ({getattr(tz, 'key', tz)})")
    print("=" * 78)
    day = start
    while day < end:
        todays = [(w, p) for w, p in items if w.date() == day.date()]
        if not todays:
            print(f"{day:%a %d}  -")
        for n, (w, p) in enumerate(todays):
            prefix = f"{day:%a %d}" if n == 0 else "      "
            status = (p.get("status") or "idea")
            print(f"{prefix}  {w:%H:%M}  {label(p)}  [{status}]")
        day += dt.timedelta(days=1)
    print("-" * 78)
    counts = {}
    for _, p in items:
        counts[p.get("status") or "idea"] = counts.get(p.get("status") or "idea", 0) + 1
    print("  " + "   ".join(f"{s}: {counts[s]}" for s in STATUSES if s in counts) if counts else "  nothing queued")


def cmd_next(data, tz, now):
    upcoming = []
    for p in data["posts"]:
        when = parse_when(p.get("when"), tz)
        if when and when >= now and (p.get("status") or "idea") != "posted":
            upcoming.append((when, p))
    if not upcoming:
        print("Nothing queued. Run /ig-plan, then /ig-schedule.")
        return
    when, p = min(upcoming, key=lambda x: x[0])
    hours = (when - now).total_seconds() / 3600
    print(f"NEXT  {when:%a %d %b %H:%M}  (in {hours:.1f}h)")
    print(f"      {label(p)}")
    print(f"      status: {p.get('status') or 'idea'}   asset: {p.get('asset') or '-'}")


def ics_escape(text):
    return (str(text).replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def fold(line):
    # RFC 5545: lines longer than 75 octets are folded with CRLF + space.
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, current = [], b""
    for ch in line:
        b = ch.encode("utf-8")
        if len(current) + len(b) > (75 if not parts else 74):
            parts.append(current.decode("utf-8"))
            current = b""
        current += b
    parts.append(current.decode("utf-8"))
    return "\r\n ".join(parts)


def utc(when):
    return when.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def cmd_ics(data, tz, base_dir, out, remind, engage, now):
    stamp = utc(now)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//instagram-agent-skill//ig-schedule//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             "X-WR-CALNAME:Instagram posting"]
    count = 0
    for p in data["posts"]:
        when = parse_when(p.get("when"), tz)
        status = p.get("status") or "idea"
        if not when or when < now or status == "posted":
            continue
        fmt = (p.get("format") or "post").lower()
        title = p.get("title") or p.get("id") or "post"
        steps = [
            f"Post the {fmt}: {title}",
            f"Asset: {p.get('asset') or 'not set'}",
            f"Caption: {p.get('caption') or 'not set'}",
            f"Hook: {p.get('hook') or '-'}",
            "",
            "Before you tap Share: cover frame, alt text, the 125-character first line,",
            "max 5 hashtags, location, and that the link in bio still works.",
            f"Then stay {engage} minutes and reply to every real comment (/ig-reply).",
            f"After: python3 schedule.py mark queue.json {p.get('id')} posted",
        ]
        uid = p.get("id") or uuid.uuid5(uuid.NAMESPACE_URL, f"{title}{when}").hex
        lines += ["BEGIN:VEVENT",
                  f"UID:{uid}@ig-schedule",
                  f"DTSTAMP:{stamp}",
                  f"DTSTART:{utc(when)}",
                  f"DTEND:{utc(when + dt.timedelta(minutes=max(engage, 15)))}",
                  f"SUMMARY:{ics_escape(f'IG {fmt}: {title}')}",
                  f"DESCRIPTION:{ics_escape(chr(10).join(steps))}",
                  "BEGIN:VALARM", "ACTION:DISPLAY",
                  f"DESCRIPTION:{ics_escape(f'Post in {remind} min: {title}')}",
                  f"TRIGGER:-PT{remind}M", "END:VALARM",
                  "END:VEVENT"]
        count += 1
    lines.append("END:VCALENDAR")
    with open(out, "w", encoding="utf-8", newline="") as fh:
        fh.write("\r\n".join(fold(l) for l in lines) + "\r\n")
    print(f"Wrote {count} event(s) to {out}. Import it into Google Calendar, Outlook or Apple Calendar.")
    print(f"Each one alarms {remind} min before and blocks {max(engage, 15)} min for the comment hour.")


def cmd_mark(path, data, was_list, pid, status):
    if status not in STATUSES:
        sys.exit(f"status must be one of {', '.join(STATUSES)}")
    for p in data["posts"]:
        if p.get("id") == pid:
            old = p.get("status") or "idea"
            p["status"] = status
            if status == "posted":
                p["posted_at"] = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
            save(path, data, was_list)
            print(f"[{pid}] {old} -> {status}")
            return
    sys.exit(f"no post with id {pid!r}")


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="Check and print the Instagram posting queue, and write calendar reminders.")
    ap.add_argument("command", choices=["check", "week", "next", "ics", "mark"])
    ap.add_argument("queue")
    ap.add_argument("args", nargs="*", help="for mark: <id> <status>")
    ap.add_argument("--tz", help=f"IANA timezone (default: the queue's, else {DEFAULT_TZ})")
    ap.add_argument("--offset", help="fixed UTC offset like +11:00, if zoneinfo is unavailable")
    ap.add_argument("--from", dest="start", help="week start date YYYY-MM-DD (default: today)")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", default="instagram-posting.ics")
    ap.add_argument("--remind", type=int, default=30, help="minutes before the post to alarm")
    ap.add_argument("--engage", type=int, default=60, help="minutes to block after posting for comments")
    ap.add_argument("--now", help=argparse.SUPPRESS)   # for tests: YYYY-MM-DD HH:MM
    a = ap.parse_args(argv)

    with open(a.queue, encoding="utf-8") as fh:
        was_list = isinstance(json.load(fh), list)
    data = load(a.queue)
    tz = resolve_tz(a.tz or data.get("timezone") or DEFAULT_TZ, a.offset)
    base_dir = os.path.dirname(os.path.abspath(a.queue))
    now = parse_when(a.now, tz) if a.now else dt.datetime.now(tz)

    if a.command == "check":
        errors, warnings = check(data, tz, base_dir, now)
        n = len(data["posts"])
        print(f"QUEUE CHECK  ·  {n} post(s)  ·  {getattr(tz, 'key', tz)}")
        print("=" * 78)
        for e in errors:
            print(f"  FAIL  {e}")
        for w in warnings:
            print(f"  WARN  {w}")
        if not errors and not warnings:
            print("  PASS  nothing to fix")
        print("-" * 78)
        print(f"  {len(errors)} fail, {len(warnings)} warn")
        return 1 if errors else 0
    if a.command == "week":
        if a.start:
            start = parse_when(a.start, tz)
            if start is None:
                sys.exit("--from: use YYYY-MM-DD")
        else:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        cmd_week(data, tz, start, a.days)
    elif a.command == "next":
        cmd_next(data, tz, now)
    elif a.command == "ics":
        cmd_ics(data, tz, base_dir, a.out, a.remind, a.engage, now)
    elif a.command == "mark":
        if len(a.args) != 2:
            sys.exit("usage: schedule.py mark queue.json <id> <status>")
        cmd_mark(a.queue, data, was_list, a.args[0], a.args[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
