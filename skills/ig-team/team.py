#!/usr/bin/env python3
"""
team.py - the team's shared desk. Shows which shared files exist, how old they
are, what is in the queue, and which skill should run next.

Every skill in the pack reads and writes the same folder,
~/.claude/instagram/. That folder is how they hand work to each other. This
script reads it and nothing else: no network, no Instagram, no writes.

Usage
  python3 team.py                       status of the default folder
  python3 team.py --dir path/to/folder  a different folder
  python3 team.py --json                machine-readable, for the skill
"""

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = os.path.join(os.path.expanduser("~"), ".claude", "instagram")


def load_team():
    with open(os.path.join(HERE, "team.json"), encoding="utf-8") as fh:
        return json.load(fh)


def file_state(folder, name, stale_days, now):
    path = os.path.join(folder, name)
    if not os.path.isfile(path):
        return {"file": name, "state": "missing", "age_days": None}
    age = (now - dt.datetime.fromtimestamp(os.path.getmtime(path))).total_seconds() / 86400
    state = "stale" if age > stale_days else "ok"
    if os.path.getsize(path) == 0:
        state = "empty"
    return {"file": name, "state": state, "age_days": round(age, 1)}


def queue_summary(folder, now):
    path = os.path.join(folder, "queue.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return {"error": f"queue.json is not valid JSON: {exc}"}
    posts = data if isinstance(data, list) else data.get("posts", [])
    counts, upcoming, overdue = {}, [], []
    for p in posts:
        status = p.get("status") or "idea"
        counts[status] = counts.get(status, 0) + 1
        try:
            when = dt.datetime.strptime(str(p.get("when", "")).replace("T", " ")[:16], "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        if status == "posted":
            continue
        # Local naive comparison: the queue's times are the user's local times.
        if when < now:
            overdue.append(p.get("id"))
        elif when - now < dt.timedelta(hours=72):
            upcoming.append({"id": p.get("id"), "when": p.get("when"), "status": status})
    return {"counts": counts, "next_72h": sorted(upcoming, key=lambda x: x["when"]), "overdue": overdue}


def next_moves(files, queue):
    """The one or two skills worth running now, in order."""
    by = {f["file"]: f["state"] for f in files}
    moves = []
    if by["voice.md"] in ("missing", "empty"):
        moves.append(("voice.md", "Fill in templates/voice.md first, or send three of your reels and say 'write my voice.md'."))
    if by["swipe.md"] in ("missing", "stale"):
        moves.append(("ig-viral", "No recent evidence of what is working in the niche. Run /ig-viral (monthly)."))
    if by["plan.md"] in ("missing", "stale"):
        moves.append(("ig-plan", "No plan for this week. Run /ig-plan."))
    elif by["queue.json"] in ("missing", "stale"):
        moves.append(("ig-schedule", "There is a plan but no queue. Run /ig-schedule to put times on it."))
    if queue and not queue.get("error"):
        if queue["overdue"]:
            moves.append(("ig-schedule", f"{len(queue['overdue'])} post(s) past their time and not marked posted: {', '.join(map(str, queue['overdue']))}."))
        for item in queue["next_72h"]:
            if item["status"] in ("idea", "drafted"):
                moves.append(("writers", f"[{item['id']}] goes out {item['when']} and is only '{item['status']}'. Draft it: /ig-reel or /ig-carousel, then /ig-caption and /ig-human."))
                break
    if queue and queue.get("error"):
        moves.append(("ig-schedule", queue["error"]))
    if by["log.md"] == "missing":
        moves.append(("log.md", "Nothing logged yet. Say 'I posted it' after each post so /ig-audit has history."))
    if not moves:
        moves.append(("daily", "Desk is clear. Do the daily round: /ig-comment, /ig-story, /ig-reply."))
    return moves


def main(argv=None):
    ap = argparse.ArgumentParser(description="Status of the Instagram skill team's shared folder.")
    ap.add_argument("--dir", default=DEFAULT_DIR)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--now", help=argparse.SUPPRESS)   # for tests: YYYY-MM-DD HH:MM
    a = ap.parse_args(argv)

    now = dt.datetime.strptime(a.now, "%Y-%m-%d %H:%M") if a.now else dt.datetime.now()
    team = load_team()
    files = [file_state(a.dir, name, spec["stale_days"], now) for name, spec in team["files"].items()]
    queue = queue_summary(a.dir, now)
    moves = next_moves(files, queue)

    if a.json:
        print(json.dumps({"dir": a.dir, "files": files, "queue": queue,
                          "next": [{"who": w, "why": y} for w, y in moves]}, indent=2))
        return 0

    print(f"TEAM DESK  ·  {a.dir}")
    print("=" * 78)
    for f in files:
        spec = team["files"][f["file"]]
        age = "-" if f["age_days"] is None else f"{f['age_days']}d"
        print(f"  {f['state'].upper():<8} {f['file']:<11} {age:>6}   written by {spec['writer']}")
    print("-" * 78)
    if queue is None:
        print("  QUEUE    none yet")
    elif queue.get("error"):
        print(f"  QUEUE    {queue['error']}")
    else:
        c = queue["counts"]
        print("  QUEUE    " + "   ".join(f"{k}: {v}" for k, v in c.items()))
        for item in queue["next_72h"]:
            print(f"           next 72h  {item['when']}  {item['id']}  [{item['status']}]")
    print("-" * 78)
    print("  NEXT")
    for who, why in moves:
        print(f"    {who:<12} {why}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
