---
name: ig-schedule
description: >-
  The scheduling assistant. Turns the week's plan and finished drafts into a
  posting queue with real times in the audience's timezone, checks it, writes
  calendar reminders, and hands over a copy-ready posting card for each slot so
  the user can post or schedule it themselves in Instagram. Use when the user
  says "schedule this", "when should I post", "set up my posting schedule",
  "remind me to post", "what's going out this week", "what's next", "I posted
  it", or has drafts ready and no times on them.
---

# ig-schedule

The scheduling assistant. `/ig-plan` decides what goes out; this decides
exactly when, keeps the queue honest, and makes sure the user is reminded,
ready, and around for the first hour after it goes live.

**It does not post and it does not log in.** Instagram's own scheduler (in the
app, on the last screen before Share, under *More options* or *Advanced
settings*, depending on the app version; or Meta Business Suite on desktop) is
the only scheduling route that is inside the
Terms for a normal account. This skill prepares everything that goes into that
screen, and the user taps the button. Third-party auto-posters and browser
automation get accounts action-blocked; do not suggest them.

One tool lives in this folder and it runs:

```bash
python3 schedule.py check queue.json          # what is wrong before the week starts
python3 schedule.py week  queue.json          # the week, slot by slot
python3 schedule.py next  queue.json          # what goes out next, and in how long
python3 schedule.py ics   queue.json --out week.ics   # calendar reminders
python3 schedule.py mark  queue.json <id> posted      # after it is live
```

The queue lives at `~/.claude/instagram/queue.json`. A worked example is in
`templates/queue.json`.

## Input

Read, in this order, whichever exist in `~/.claude/instagram/`:

1. `plan.md` from `/ig-plan`. The slots, pillars and hook formulas come from
   here. If there is no plan, say so and offer to run `/ig-plan` first. Do not
   invent a content plan inside this skill.
2. `queue.json`, the current queue. Never overwrite it wholesale. Add, move and
   update entries by `id`.
3. `voice.md`, for the timezone and who the audience is.
4. `log.md` and any insights the user pastes. If `/ig-audit` has found the
   account's own best hours, those outrank every default below.

Ask once, if it is not already written down: **which timezone is the audience
in?** Default to `Australia/Sydney` for this account. It follows AEDT and AEST
automatically. If the audience is spread across Australia, schedule for Sydney
and Melbourne time; Brisbane is an hour behind during daylight saving, Perth
three. Queensland, WA and the NT do not use daylight saving. In NSW, Victoria,
the ACT, Tasmania and SA it starts on the first Sunday of October and ends on
the first Sunday of April. `schedule.py check` fails a time the clocks skip
over and warns when a queue crosses a changeover.

## Picking times

Start from these defaults, then let the account's own data replace them as
soon as there is any:

| audience | best windows (audience local time) |
| --- | --- |
| small business owners, tradies, sole traders | 6:30 to 7:30am before the day starts; 12:00 to 1:00pm lunch scroll; 7:30 to 8:30pm after the kids are down |
| consumer | 6:00 to 9:00pm |
| office professionals | 7:00 to 8:30am commute; 12:00 to 1:00pm |

Rules that matter more than the hour:

- **Post when the user can stay for the next 60 minutes.** Replies in the first
  hour do more than the timeslot. A 7:30pm slot the user is never free for is
  worse than a 12:30pm slot they are. Ask what their week looks like.
- **Twelve hours minimum between feed posts.** Closer than that and the two
  posts compete for the same followers' attention.
- **Same time on the same weekday, week after week.** Followers learn it, and
  `/ig-audit` gets a clean comparison.
- **Never two of the same pillar back to back.** The checker flags it.
- **Schedule the day before it goes live**, not the morning of. A post that
  is still being finished at 7am goes out at 9am.
- **Up to 75 days ahead.** That is as far as Instagram's scheduler goes.
- **Stories are daily and are not time-critical.** Give them a rough window,
  not a minute.

Say plainly, every time this comes up: **the time matters far less than the
hook.** If the user is tuning minutes while their reels lose people at second
two, tell them to run `/ig-audit` and `/ig-reel` instead.

## Building the queue

For each slot in the plan, add or update one entry:

```json
{
  "id": "w46-tue-reel",
  "when": "2026-11-10 07:30",
  "format": "reel",
  "pillar": "teach",
  "title": "3 AI replies that save 5 hours a week",
  "hook": "#5 Time Collapse",
  "asset": "D:/ShortsForge/instagram-tools/out/w46-tue.mp4",
  "caption": "captions/w46-tue.txt",
  "status": "drafted"
}
```

- `id` is `w<ISO week>-<day>-<format>`, so it is stable when the time moves.
- `when` is local time in the queue's timezone, `YYYY-MM-DD HH:MM`.
- `status` moves `idea` -> `drafted` -> `ready` -> `scheduled` -> `posted`.
  `ready` means the asset is exported and the caption has passed `/ig-caption`
  and `/ig-human`. `scheduled` means the user has set it up in Instagram's own
  scheduler. Only the user moves a post to `scheduled` or `posted`.
- Save captions as files next to the queue under `captions/`, so the checker
  can lint the hashtag count and catch a leftover `{{your number}}`.

Then run `python3 schedule.py check` and fix every FAIL before showing the
user anything. WARNs get shown with a one-line reason to keep or change.

## The posting card

For every slot that is `ready`, give the user a card they can work from on
their phone without opening anything else:

```
TUE 10 NOV  7:30am AEDT  ·  REEL  ·  TEACH
---------------------------------------------
File:      D:/ShortsForge/instagram-tools/out/w46-tue.mp4
Cover:     frame at 0:01, text "5 hours back"
Caption:   (the full caption, in its own block, ready to copy)
Alt text:  Screen recording of an AI tool drafting three customer replies.
Location:  Sydney, Australia
Hashtags:  inside the caption, 3 of max 5

Schedule it now: on Instagram's last screen before Share, open More options
(or Advanced settings) > Schedule, and pick Tue 10 Nov, 7:30am. Or set the calendar reminder and post it live.
At 7:30 to 8:30am stay on for comments, then say "I posted it".
```

Show the caption in its own fenced block so it copies clean.

- **Alt text on every post.** Never skip it. It helps screen-reader users and
  tells Instagram what the post is about.
- **Links in a caption are not clickable.** Point to the bio link or a Story
  link sticker. The checker warns on any `http` in a caption.
- **Reels with music from Instagram's library:** schedule them from the phone
  app. Business Suite on desktop does not always offer the music library.

## Reminders

Two options. Offer both, do the one the user picks.

1. **A calendar file.** `python3 schedule.py ics queue.json --out week.ics`.
   One event per post, an alarm 30 minutes before (`--remind`), and the event
   blocks the hour after posting for comments (`--engage`). Posts that fail the
   check are left out until they are fixed. The user imports it
   into Google Calendar, Outlook or Apple Calendar. Nothing is sent anywhere.
2. **Their Google Calendar directly**, if a Google Calendar connector is
   available in this session. Show the list of events first and create them
   only after the user says yes. Use the same title, description and alarm the
   `.ics` would have.

## After it goes live

When the user says "I posted it" (or "done", or "it's up"):

1. `python3 schedule.py mark queue.json <id> posted`.
2. Append to `~/.claude/instagram/log.md`: date, time, format, pillar, hook
   formula, first line. `/ig-audit` reads this later.
3. Hand off to `/ig-reply` for the first-hour comments, and to `/ig-story` if a
   story is planned to point at the post.

## Output

```
SCHEDULE  ·  week of Mon 9 Nov  ·  Australia/Sydney (AEDT)

MON 09  -          engage only (20 min)
TUE 10  07:30  REEL      TEACH    #5 Time Collapse   3 AI replies...      ready
WED 11  -          stories + engage
THU 12  12:30  CAROUSEL  PROOF    -                  The 10-setup guide   drafted
FRI 13  19:30  REEL      OPINION  #2 Negative Cmd    Stop hiring a VA...  idea
SUN 15  19:00  REEL      STORY    #21 Mid-Sentence   The Sunday invoice   idea

check:     0 fail, 1 warn (Friday is only an idea and goes out in 3 days)
reminders: week.ics written, 4 events, 30 min alarm, 60 min comment block

Next up: Tuesday 7:30am. Say "card for Tuesday" for the posting card.
```

## Never

- Post, schedule inside Instagram, or log in on the user's behalf.
- Recommend a third-party auto-poster, a browser bot, or a "growth" service.
- Move a post to `scheduled` or `posted` without the user saying so.
- Change what a post says. Wording goes back to `/ig-reel`, `/ig-caption` or
  `/ig-human`. This skill only moves times and statuses.
