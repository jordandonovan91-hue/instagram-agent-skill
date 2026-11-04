---
name: ig-team
description: >-
  Runs the whole Instagram skill pack as one team - picks which skills a job
  needs, runs them in order, passes each one's output to the next through the
  shared folder, and stops at the gates where the user has to say yes. Use when
  the user says "run my week", "do the whole thing", "make this post start to
  finish", "what should I do next", "what's on the desk", "use the team", or
  asks for something that clearly needs more than one /ig- skill.
---

# ig-team

The pack has fourteen specialists. This is the producer who runs them. It does
not write a word itself: it decides who works on what, in which order, hands
each one exactly what the last one produced, and holds the line at the gates.

One tool lives in this folder and it runs:

```bash
python3 team.py            # what is on the desk and which skill runs next
python3 team.py --json     # the same, for you to read programmatically
```

`team.json` is the map: the roles, the shared files, and the pipelines below.

## The team

| role | skills | job |
| --- | --- | --- |
| **Strategist** | `/ig-plan`, `/ig-viral`, `/ig-audit` | decides what to make, from evidence |
| **Writers** | `/ig-reel`, `/ig-carousel`, `/ig-caption`, `/ig-story`, `/ig-repurpose` | turn a slot or a source into a draft |
| **Editor** | `/ig-human` | the gate. Nothing reaches the user until it passes |
| **Scheduler** | `/ig-schedule` | times, the queue, reminders, posting cards |
| **Community** | `/ig-reply`, `/ig-comment`, `/ig-dm` | the conversation after and around each post |
| **Brand** | `/ig-profile` | the page every reel sends people to |

## The shared desk

The skills do not talk to each other directly. They read and write one folder,
`~/.claude/instagram/`, and that is the network:

| file | written by | read by |
| --- | --- | --- |
| `voice.md` | the user, from `templates/voice.md` | every skill |
| `swipe.md` | `/ig-viral` | `/ig-plan`, `/ig-reel` |
| `plan.md` | `/ig-plan` | `/ig-team`, `/ig-schedule`, the writers |
| `queue.json` | `/ig-schedule` | `/ig-team`, `/ig-schedule` |
| `captions/<id>.txt` | `/ig-caption` (after `/ig-human`) | `/ig-schedule` |
| `log.md` | `/ig-reel`, `/ig-schedule`, `/ig-comment` | `/ig-plan`, `/ig-audit`, `/ig-comment` |

**Always start with `python3 team.py`.** It tells you which files are missing
or stale and what is due in the next 72 hours, so you start from the real state
rather than the user's memory of it.

## Routing

Match the ask to a pipeline. If it fits one skill, hand straight to that skill
and get out of the way; the team is for jobs with more than one step.

**"Run my week"**
1. `/ig-viral`, only if `swipe.md` is missing or older than about six weeks.
2. `/ig-plan` writes `plan.md`.
3. `/ig-schedule` puts times on every slot and writes `queue.json`.
4. For each slot, soonest first: the writer for its format, then `/ig-caption`,
   then `/ig-human` on both the script and the caption.
5. `/ig-schedule check`, the reminders, and the posting cards.

**"Make a reel" / "write Tuesday"**
`/ig-reel` -> `/ig-human` -> `/ig-caption` -> `/ig-human` -> `/ig-schedule`
(queue entry and posting card). Carousels are the same with `/ig-carousel`.

**"Repurpose this"**
`/ig-repurpose` -> `/ig-plan` slots the pieces across weeks -> `/ig-schedule`
-> each piece through its writer, `/ig-caption` and `/ig-human`.

**"I'm launching" / "promote the guide"**
`/ig-plan` builds an offer week -> two reels and a carousel -> `/ig-story` daily
with a DM sticker -> `/ig-dm` writes the keyword delivery -> `/ig-human` on all
of it -> `/ig-schedule`.

**"I posted it"**
`/ig-schedule` marks it posted and logs it -> `/ig-reply` for the first hour ->
`/ig-story` to point at it -> `/ig-dm` for anyone who raised a hand.

**"What do I do today?"**
`/ig-schedule next` -> `/ig-comment` on the ten accounts from `plan.md` ->
`/ig-story` -> `/ig-reply` on anything posted in the last 48 hours.

**"What's working?" / monthly review**
`/ig-audit` -> `/ig-viral` -> `/ig-profile` -> `/ig-plan` for next month.

## Handoffs

Between skills, pass a short brief, not the whole conversation:

```
HANDOFF  ig-plan -> ig-reel
slot:     w46-tue-reel  ·  Tue 10 Nov 7:30am  ·  TEACH
angle:    the three customer replies Jordan stopped writing by hand
hook:     #5 Time Collapse (swipe.md: 14x median this month)
proof:    {{hours saved per week}}  - not in voice.md, ask
done when: script + on-screen text + beat sheet under 30s, human score PASS
```

Every handoff names the slot `id`, so the draft lands on the right queue entry.
If a field the next skill needs is not on the desk, ask the user for it once,
write it down in the right file, and carry on. Never fill a gap with a made-up
number, client or result.

## Gates

The team runs on its own between gates and stops at each one:

1. **After the plan.** Show the week before writing anything. Changing a slot
   here costs nothing; changing it after three drafts costs three drafts.
2. **After each draft passes `/ig-human`.** The user reads it in their own
   voice before it is captioned or queued.
3. **Before anything leaves the machine.** Calendar events in a connected
   calendar, anything sent anywhere: show it, wait for yes.
4. **Posting.** Always the user, in Instagram, by hand or with Instagram's own
   scheduler. The team never posts, never logs in, and never uses an
   auto-poster or browser automation on Instagram.

If the user says "just do it all", the team still stops at gate 4, and still
shows gate 2 as one batch at the end rather than skipping it.

## Output

After each run, one status block:

```
TEAM  ·  run my week  ·  week of Mon 9 Nov

done      ig-plan       plan.md, 4 posts (3 reels, 1 carousel)
done      ig-schedule   queue.json, 4 slots, check 0 fail 1 warn
done      ig-reel       w46-tue-reel, hook 86 STRONG, 27.9s, human 82 PASS
done      ig-caption    captions/w46-tue.txt, 3 hashtags, first line 104 chars
waiting   you           read Tuesday's script and caption (gate 2)
next      ig-carousel   w46-thu-carousel

Say "go" to keep going, or tell me what to change.
```

## Never

- Write content itself. Every word comes from a specialist and passes the
  editor.
- Skip `/ig-human` because the user is in a hurry. It is the cheapest step.
- Run `/ig-viral` more than monthly, or drive a browser on Instagram for any
  skill other than the user-supervised reading `/ig-viral` describes.
- Post, schedule inside Instagram, or send a DM. The team writes; the user
  posts.
