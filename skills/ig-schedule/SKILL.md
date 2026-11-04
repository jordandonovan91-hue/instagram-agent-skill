---
name: ig-schedule
description: >-
  Turn the week's plan into a posting schedule - dated slots in the audience's
  timezone, a ready-to-load pack per post (asset, caption, cover, alt text),
  the checks that catch a bad slot, and calendar reminders. The user loads it
  into Instagram's own scheduler. Use when the user says "schedule my posts",
  "when should I post", "set up my posting schedule", "load the week", "remind
  me to post", or has finished /ig-plan and wants it on a calendar.
---

# ig-schedule

`/ig-plan` decides what goes out. This puts each post on a date and a time,
makes sure everything it needs exists, and hands the user a calendar file of
reminders. The posting itself happens in Instagram's own scheduler, by the
user. Nothing here logs in, uploads or posts.

One tool lives in this folder and it runs:

```bash
python3 schedule.py queue.txt                                  # check the queue
python3 schedule.py queue.txt --ics ~/.claude/instagram/schedule.ics
python3 schedule.py queue.txt --tz Australia/Brisbane          # audience timezone
python3 schedule.py --best-times                               # starting windows
```

## Input

Read `~/.claude/instagram/plan.md` if `/ig-plan` wrote one. If not, ask for
the posts the user has ready or nearly ready, and their format. Also read
`voice.md` for the audience.

Ask once for the **audience's** timezone, and default to `Australia/Sydney`
if they are an Australian business and do not say. Two things trip people up
here and are worth saying out loud:

- Queensland, Western Australia and the Northern Territory do not use daylight
  saving. Between October and April, 7pm in Sydney is 6pm in Brisbane. If the
  audience is spread across states, schedule for the east coast and accept it.
- Daylight saving starts on the first Sunday in October and ends on the first
  Sunday in April. A week that crosses either is a week where "same time as
  last week" moves. The tool flags it.

## Choosing the times

Start from these, in audience local time, for a small-business audience:

| window | why |
| --- | --- |
| 06:30 to 08:00 | before the shop opens, phone over coffee |
| 12:00 to 13:00 | the lunch break scroll |
| 19:00 to 20:30 | after close. The strongest one for owners. |

These are a starting guess, and the account's own numbers replace them as
soon as it has some: **Professional dashboard > Total followers > Most active
times.** Once that shows a pattern, use it and say so.

Same thing `/ig-plan` says, and it bears repeating: the hour matters far less
than the first two seconds. If the user is fussing over 7:00 versus 7:15 and
the hooks are untested, point that out.

Rules for the slots:

- One feed post a day at most. Two on the same day compete for the same people.
- Reels on the days the user can be around for the first 30 minutes after
  go-live. Answering comments early is worth more than the perfect hour.
- Never two of the same format and type back to back.
- Stories do not need a slot. They go out daily and are planned by `/ig-story`.

## Write the queue

One line per post, written to `~/.claude/instagram/queue.txt`:

```
# date time        | format   | type    | title                        | asset                          | caption file
2026-11-10 07:00   | REEL     | PROOF   | Customer replies in 5 min    | w1-tue-customer-replies.mp4    | captions/w1-tue.txt
2026-11-12 19:30   | CAROUSEL | TEACH   | 3 ChatGPT prompts for quotes | w1-thu-quotes.pdf              | captions/w1-thu.txt
2026-11-14 19:00   | REEL     | OPINION | Stop answering every call    | w1-sat-calls.mp4               | captions/w1-sat.txt
```

Caption files sit next to the queue, one per post, written by `/ig-caption`
and cleaned by `/ig-human`. Asset names are the files the user exports, so
use the names they actually have. Never invent a filename that does not exist
and present it as ready: if the Reel is not cut yet, write `TO MAKE` and say so.

Then run `schedule.py` on it. **FAIL** lines are fixed before anything else:
a time that has passed, an hour that does not exist because the clocks jump,
a caption over 2,200 characters, more than five hashtags, a missing caption
file. **WARN** lines get a sentence each on whether to change them. **INFO**
lines are context.

## The post pack

For each slot, give the user one block they can work straight from:

```
TUE 10 NOV  07:00 AEDT  ·  REEL  ·  PROOF
  asset      w1-tue-customer-replies.mp4
  cover      frame at 0:01, or a cover image with the on-screen hook
  caption    captions/w1-tue.txt   (passes caption.py, 3 hashtags)
  alt text   one plain sentence on what is on screen
  first comment   none, or the keyword reply if the caption asks for one
  after      be on the post 07:00 to 07:30 to answer comments
```

Alt text is written, not skipped. It is under Advanced settings, and it is
what a screen reader says instead of the picture.

## Loading it into Instagram's own scheduler

Both of these are Meta's own tools and both are inside the Terms. Menu names
move. If what the user sees differs from this, Instagram is right.

**In the Instagram app.** Make the post or Reel as normal. On the last screen,
before Share, open **More options** (older versions: **Advanced settings**)
and turn on **Schedule this post**, then pick the date and time. You can
schedule up to 75 days ahead. Scheduled posts live under your profile menu in
**Scheduled content**, where you can move or delete them.

**On a computer, in Meta Business Suite** (business.facebook.com, the
**Planner** or **Content** tab). Better for loading a whole week at once from
the files on the PC that made them. It needs the Instagram account linked to
a Facebook Page. If a Reel uses a track from Instagram's music library, load
that one from the phone app instead, because the library is not always offered
on desktop.

Schedule the day before go-live, not the morning of. That leaves time to fix
an upload that fails.

## Reminders

With `--ics`, the tool writes a calendar file with two reminders per post:
one the day before (load it into the scheduler) and one at go-live (be there
to answer comments for 30 minutes). Rows with a FAIL are left out. The user
imports it into Google Calendar, Outlook or Apple Calendar. It is a file on
their machine and it sends nothing anywhere.

## Output

```
SCHEDULE  ·  week of 10 Nov  ·  Australia/Sydney (AEDT, UTC+11)

TUE 10 NOV  07:00  REEL      PROOF    Customer replies in 5 min     ready
THU 12 NOV  19:30  CAROUSEL  TEACH    3 ChatGPT prompts for quotes  caption to write
SAT 14 NOV  19:00  REEL      OPINION  Stop answering every call     TO MAKE

schedule.py: 0 to fix. 1 WARN (Saturday: are you around at 7pm?).

Post packs below. Calendar reminders: ~/.claude/instagram/schedule.ics

Say "pack Thursday" and I will write the caption and alt text for it.
```

Write the schedule to `~/.claude/instagram/schedule.md` so `/ig-audit` can
compare what went out against when it was meant to. Nothing is scheduled or
posted by this skill. The user loads each post into Instagram's scheduler and
presses the button.
