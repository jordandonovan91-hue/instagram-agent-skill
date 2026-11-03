#!/usr/bin/env python3
"""Build a HyperFrames Reel (1080x1920) from a reel JSON file.

    python3 build.py reels/w1-tue-customer-replies.json            # writes index.html
    python3 build.py reels/x.json --vo-dir vo/                       # one voice clip per beat: 01.wav, 02.wav ...
    python3 build.py reels/x.json --timings t.json --audio vo.wav    # or one file plus your own beat timings

Without --timings, each beat is timed from its word count at the reel's wpm
(the same estimate skills/ig-reel/beats.py uses). With a voiceover, pass a JSON
list of {"start": s, "end": s} per beat, or a folder of per-beat clips, and the visuals and
captions follow the real audio. Python standard library, plus ffmpeg for --vo-dir.
"""

import argparse
import html
import json
import re
import subprocess
from pathlib import Path

W, H = 1080, 1920
# Instagram safe zone: nothing above y=230 or below y=1440, right 230px clear.
SAFE_TOP, SAFE_BOTTOM, SAFE_RIGHT = 230, 1440, 230
LEFT = 70
COL_W = W - SAFE_RIGHT - LEFT  # 780
TAIL = 0.6  # hold on the last frame so the loop lands


def esc(s):
    return html.escape(str(s), quote=True)


def beat_times(reel, timings):
    if timings:
        if len(timings) != len(reel["beats"]):
            raise SystemExit(f"timings has {len(timings)} entries, reel has {len(reel['beats'])} beats")
        out = []
        for i, t in enumerate(timings):
            start = 0.0 if i == 0 else float(t["start"])
            end = float(timings[i + 1]["start"]) if i + 1 < len(timings) else float(t["end"]) + TAIL
            out.append((round(start, 3), round(end - start, 3)))
        return out
    wpm = reel.get("wpm", 165)
    out, t = [], 0.0
    for b in reel["beats"]:
        words = len(re.findall(r"[\w$']+", b["say"]))
        d = max(1.8, words / wpm * 60 + 0.25)
        out.append((round(t, 3), round(d, 3)))
        t += d
    s, d = out[-1]
    out[-1] = (s, round(d + TAIL, 3))
    return out


# ---------- visuals: each returns (html, [js animation lines]) ----------

def v_repeat(v, sel, t, d):
    bubbles = "".join(
        f'<div class="bubble out rep" style="top:{i*120}px">{esc(v["text"])}</div>' for i in range(4)
    )
    h = f'<div class="vis" id="{sel}-v"><div class="stack">{bubbles}</div><div class="strike"></div><div class="count">x4 today</div></div>'
    js = [
        f'tl.from("#{sel}-v .rep", {{y: 60, opacity: 0, duration: 0.25, stagger: 0.18, ease: "power3.out"}}, {t + 0.05});',
        f'tl.fromTo("#{sel}-v .strike", {{scaleX: 0}}, {{scaleX: 1, duration: 0.3, ease: "power2.inOut"}}, {t + 0.95});',
        f'tl.from("#{sel}-v .count", {{scale: 0.4, opacity: 0, duration: 0.3, ease: "back.out(2)"}}, {t + 1.15});',
    ]
    return h, js


def v_bubbles(v, sel, t, d):
    items = v["items"]
    bubbles = "".join(
        f'<div class="bubble in b{i}" style="top:{i*112}px;left:{(i%2)*70}px">{esc(x)}</div>' for i, x in enumerate(items)
    )
    h = f'<div class="vis" id="{sel}-v"><div class="stack">{bubbles}</div></div>'
    step = min(0.4, (d - 0.6) / max(1, len(items)))
    js = [f'tl.from("#{sel}-v .bubble", {{x: -40, opacity: 0, duration: 0.22, stagger: {step:.3f}, ease: "power3.out"}}, {t + 0.05});']
    return h, js


def v_chat(v, sel, t, d):
    lines = "".join(f'<div class="cl">{esc(x)}</div>' for x in v.get("lines", []))
    h = (
        f'<div class="vis" id="{sel}-v"><div class="win">'
        f'<div class="win-bar"><span></span><span></span><span></span><b>{esc(v.get("label", ""))}</b></div>'
        f'<div class="win-body">{lines}</div>'
        f'<div class="win-input"><i class="caret"></i>Message</div></div></div>'
    )
    js = [f'tl.from("#{sel}-v .win", {{y: 40, opacity: 0, scale: 0.96, duration: 0.3, ease: "power3.out"}}, {t + 0.02});']
    n = len(v.get("lines", []))
    if n:
        step = min(0.45, (d - 0.7) / n)
        js.append(
            f'tl.fromTo("#{sel}-v .cl", {{clipPath: "inset(0 100% 0 0)"}}, {{clipPath: "inset(0 0% 0 0)", duration: {step*0.9:.3f}, stagger: {step:.3f}, ease: "steps(18)"}}, {t + 0.35});'
        )
    else:
        js.append(f'tl.fromTo("#{sel}-v .caret", {{opacity: 1}}, {{opacity: 0, duration: 0.4, repeat: {int(d/0.8)}, yoyo: true, ease: "steps(1)"}}, {t + 0.3});')
    return h, js


def v_prompt(v, sel, t, d):
    h = (
        f'<div class="vis" id="{sel}-v"><div class="win">'
        f'<div class="win-bar"><span></span><span></span><span></span><b>Your AI chat</b></div>'
        f'<div class="win-body"><div class="bubble out pr">{esc(v["text"])}</div>'
        f'<div class="dots"><i></i><i></i><i></i></div></div></div></div>'
    )
    js = [
        f'tl.from("#{sel}-v .win", {{opacity: 0, duration: 0.2}}, {t});',
        f'tl.fromTo("#{sel}-v .pr", {{clipPath: "inset(0 100% 0 0)"}}, {{clipPath: "inset(0 0% 0 0)", duration: {min(1.0, d*0.45):.3f}, ease: "steps(24)"}}, {t + 0.15});',
        f'tl.from("#{sel}-v .dots i", {{y: 0, opacity: 0, duration: 0.2, stagger: 0.12}}, {t + min(1.3, d*0.6):.3f});',
    ]
    return h, js


def v_cards(v, sel, t, d):
    cards = "".join(f'<div class="tcard c{i}" style="top:{i*118}px">{esc(x)}</div>' for i, x in enumerate(v["items"]))
    h = (
        f'<div class="vis" id="{sel}-v"><div class="stack">{cards}</div>'
        f'<div class="folder"><div class="tab"></div><b>{esc(v.get("target", "Templates"))}</b></div></div>'
    )
    js = [
        f'tl.from("#{sel}-v .tcard", {{x: 60, opacity: 0, duration: 0.22, stagger: 0.15, ease: "power3.out"}}, {t + 0.05});',
        f'tl.from("#{sel}-v .folder", {{y: 80, opacity: 0, duration: 0.3, ease: "power3.out"}}, {t + 0.5});',
        f'tl.to("#{sel}-v .tcard", {{y: 520, x: 200, scale: 0.3, opacity: 0, duration: 0.35, stagger: 0.12, ease: "power2.in"}}, {t + max(1.2, d - 1.2):.3f});',
    ]
    return h, js


def v_shortcut(v, sel, t, d):
    h = (
        f'<div class="vis" id="{sel}-v"><div class="phone"><div class="field">'
        f'<span class="trig">{esc(v["trigger"])}</span><span class="full">{esc(v["text"])}</span></div>'
        f'<div class="send">Send</div></div></div>'
    )
    js = [
        f'tl.from("#{sel}-v .phone", {{y: 60, opacity: 0, duration: 0.3, ease: "power3.out"}}, {t});',
        f'tl.fromTo("#{sel}-v .trig", {{clipPath: "inset(0 100% 0 0)"}}, {{clipPath: "inset(0 0% 0 0)", duration: 0.5, ease: "steps(6)"}}, {t + 0.3});',
        f'tl.to("#{sel}-v .trig", {{opacity: 0, duration: 0.1}}, {t + 1.0});',
        f'tl.fromTo("#{sel}-v .full", {{opacity: 0, y: 10}}, {{opacity: 1, y: 0, duration: 0.25, ease: "power2.out"}}, {t + 1.05});',
        f'tl.fromTo("#{sel}-v .send", {{scale: 1}}, {{scale: 1.12, duration: 0.15, yoyo: true, repeat: 1}}, {t + min(d - 0.4, 2.2):.3f});',
    ]
    return h, js


BOOKMARK = '<svg viewBox="0 0 24 24" width="300" height="300"><path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4.5L5 21V4a1 1 0 0 1 1-1z" fill="currentColor"/></svg>'


def v_cta(v, sel, t, d):
    h = f'<div class="vis center" id="{sel}-v"><div class="bm">{BOOKMARK}</div><div class="handle">{esc(v["text"])}</div></div>'
    js = [
        f'tl.from("#{sel}-v .bm", {{scale: 0.3, opacity: 0, duration: 0.4, ease: "back.out(2.2)"}}, {t + 0.05});',
        f'tl.to("#{sel}-v .bm", {{scale: 1.08, duration: 0.3, yoyo: true, repeat: 3, ease: "sine.inOut"}}, {t + 0.6});',
        f'tl.from("#{sel}-v .handle", {{y: 30, opacity: 0, duration: 0.3}}, {t + 0.5});',
    ]
    return h, js


VISUALS = {"repeat": v_repeat, "bubbles": v_bubbles, "chat": v_chat, "prompt": v_prompt,
           "cards": v_cards, "shortcut": v_shortcut, "cta": v_cta}


def build(reel, timings=None, audio=None):
    times = beat_times(reel, timings)
    total = round(times[-1][0] + times[-1][1], 3)
    scenes, captions, js = [], [], []
    for i, (b, (t, d)) in enumerate(zip(reel["beats"], times)):
        sel = f"s{i}"
        vh, vjs = VISUALS[b["visual"]["type"]](b["visual"], sel, t, d)
        scenes.append(
            f'<div class="clip scene" id="{sel}" data-start="{t}" data-duration="{d}" data-track-index="1">'
            f'<div class="card">{esc(b["card"])}</div>{vh}</div>'
        )
        js.append(f'tl.from("#{sel} .card", {{y: -24, opacity: 0, duration: 0.2, ease: "power3.out"}}, {t});')
        js += vjs
        words = b["say"].split()
        spans = " ".join(f'<span class="w">{esc(w)}</span>' for w in words)
        captions.append(
            f'<div class="clip cap" id="c{i}" data-start="{t}" data-duration="{d}" data-track-index="2"><p>{spans}</p></div>'
        )
        speak = d - (TAIL if i == len(times) - 1 else 0) - 0.15
        js.append(f'tl.to("#c{i} .w", {{color: "var(--accent)", duration: 0.05, stagger: {max(0.05, speak/len(words)):.3f}}}, {t});')
    audio_tag = ""
    if audio:
        audio_tag = f'<audio id="vo" class="clip" src="{esc(audio)}" data-start="0" data-duration="{total}" data-track-index="3"></audio>'
    return TEMPLATE.format(
        title=esc(reel.get("title", reel["id"])), total=total,
        scenes="\n      ".join(scenes), captions="\n      ".join(captions),
        audio=audio_tag, js="\n      ".join(js),
        safe_top=SAFE_TOP, safe_bottom=SAFE_BOTTOM, left=LEFT, col_w=COL_W,
    )


TEMPLATE = """<!doctype html>
<!-- Generated by build.py. Edit the reel JSON and rebuild rather than editing this file. -->
<html lang="en" data-resolution="portrait">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1080, height=1920" />
    <title>{title}</title>
    <script src="assets/gsap.min.js"></script>
    <style>
      @font-face {{ font-family: "InterReel"; font-weight: 500; src: url(assets/fonts/inter-latin-500-normal.woff2) format("woff2"); }}
      @font-face {{ font-family: "InterReel"; font-weight: 700; src: url(assets/fonts/inter-latin-700-normal.woff2) format("woff2"); }}
      @font-face {{ font-family: "InterReel"; font-weight: 800; src: url(assets/fonts/inter-latin-800-normal.woff2) format("woff2"); }}
      :root {{
        --ground: #0b1324; --ground-2: #13203a; --panel: #172642; --line: #2a3d63;
        --ink: #f7f3ea; --muted: #9fb0cc; --accent: #ffb547; --teal: #5eead4;
      }}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: 1080px; height: 1920px; overflow: hidden; background: var(--ground); }}
      #root {{ position: relative; width: 1080px; height: 1920px; font-family: "InterReel", "Inter", sans-serif; color: var(--ink);
        background: radial-gradient(1200px 900px at 20% 15%, var(--ground-2), var(--ground) 70%); }}
      .scene {{ position: absolute; inset: 0; }}
      .card {{ position: absolute; left: {left}px; top: {safe_top}px; width: {col_w}px; font-size: 92px; line-height: 0.98;
        font-weight: 800; letter-spacing: -0.035em; text-transform: uppercase; }}
      .vis {{ position: absolute; left: {left}px; top: 520px; width: {col_w}px; height: 660px; }}
      .vis.center {{ display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 24px; }}
      .stack {{ position: relative; width: 100%; height: 100%; }}
      .bubble {{ position: absolute; max-width: 640px; padding: 26px 32px; border-radius: 34px; font-size: 38px; font-weight: 500; line-height: 1.2; }}
      .bubble.in {{ background: var(--panel); border: 2px solid var(--line); border-bottom-left-radius: 8px; }}
      .bubble.out {{ right: 0; background: var(--teal); color: #052b26; border-bottom-right-radius: 8px; }}
      .strike {{ position: absolute; left: -10px; right: -10px; top: 250px; height: 12px; background: var(--accent); transform-origin: left; border-radius: 6px; }}
      .count {{ position: absolute; left: 0; top: 520px; font-size: 64px; font-weight: 800; color: var(--accent); }}
      .win {{ position: absolute; inset: 0; background: var(--panel); border: 2px solid var(--line); border-radius: 36px; overflow: hidden; }}
      .win-bar {{ height: 84px; display: flex; align-items: center; gap: 12px; padding: 0 30px; border-bottom: 2px solid var(--line); }}
      .win-bar span {{ width: 18px; height: 18px; border-radius: 50%; background: var(--line); }}
      .win-bar b {{ margin-left: 14px; font-size: 30px; font-weight: 700; color: var(--muted); }}
      .win-body {{ position: relative; padding: 34px 34px; display: flex; flex-direction: column; gap: 22px; font-size: 36px; font-weight: 500; }}
      .win-body .bubble {{ position: relative; align-self: flex-end; }}
      .cl {{ white-space: nowrap; overflow: hidden; }}
      .win-input {{ position: absolute; left: 30px; right: 30px; bottom: 30px; height: 92px; border-radius: 46px; background: var(--ground);
        display: flex; align-items: center; padding: 0 34px; font-size: 32px; color: var(--muted); }}
      .caret {{ width: 4px; height: 40px; background: var(--accent); margin-right: 14px; }}
      .dots {{ display: flex; gap: 12px; padding: 18px 0; }}
      .dots i {{ width: 18px; height: 18px; border-radius: 50%; background: var(--muted); }}
      .tcard {{ position: absolute; left: 0; width: 520px; padding: 28px 34px; border-radius: 26px; background: var(--ink); color: var(--ground);
        font-size: 38px; font-weight: 700; }}
      .folder {{ position: absolute; right: 0; bottom: 0; width: 300px; height: 220px; background: var(--accent); border-radius: 22px;
        display: flex; align-items: flex-end; padding: 26px; color: var(--ground); font-size: 36px; font-weight: 800; }}
      .folder .tab {{ position: absolute; top: -26px; left: 0; width: 130px; height: 40px; background: var(--accent); border-radius: 14px 14px 0 0; }}
      .phone {{ position: absolute; left: 70px; top: 0; width: 640px; height: 660px; border-radius: 60px; border: 10px solid var(--line);
        background: var(--panel); padding: 70px 36px; }}
      .field {{ position: relative; min-height: 300px; background: var(--ground); border-radius: 30px; padding: 30px; font-size: 38px; line-height: 1.3; }}
      .trig {{ position: absolute; color: var(--accent); font-weight: 700; }}
      .send {{ margin-top: 40px; margin-left: auto; width: 200px; text-align: center; padding: 22px 0; border-radius: 40px; background: var(--teal);
        color: #052b26; font-size: 34px; font-weight: 800; }}
      .bm {{ color: var(--accent); }}
      .handle {{ font-size: 54px; font-weight: 800; }}
      .cap {{ position: absolute; left: {left}px; width: {col_w}px; bottom: calc(1920px - {safe_bottom}px + 10px); }}
      .cap p {{ font-size: 50px; font-weight: 700; line-height: 1.2; text-align: center; padding: 22px 26px; border-radius: 22px;
        background: rgba(5, 10, 20, 0.72); }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total}" data-width="1080" data-height="1920">
      {scenes}
      {captions}
      {audio}
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      {js}
      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
"""


GAP = 0.15  # silence between beats when stitching per-beat voiceover clips


def stitch_vo(vo_dir, n, here):
    """Join vo/01.wav .. vo/NN.wav (one clip per beat) into voiceover.wav and return timings."""
    clips = sorted(p for p in Path(vo_dir).iterdir() if p.suffix.lower() in (".wav", ".mp3", ".m4a"))
    if len(clips) != n:
        raise SystemExit(f"{vo_dir} has {len(clips)} audio clips, reel has {n} beats (name them 01.wav, 02.wav, ...)")
    timings, t = [], 0.0
    for c in clips:
        dur = float(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(c)], text=True))
        timings.append({"start": round(t, 3), "end": round(t + dur, 3)})
        t += dur + GAP
    inputs, filters = [], []
    for i, c in enumerate(clips):
        inputs += ["-i", str(c)]
        filters.append(f"[{i}:a]aresample=44100,apad=pad_dur={GAP}[a{i}]")
    graph = ";".join(filters) + ";" + "".join(f"[a{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", graph, "-map", "[out]",
                    str(here / "voiceover.wav")], check=True)
    return timings


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("reel", type=Path)
    ap.add_argument("--vo-dir", type=Path, help="folder of per-beat voiceover clips (01.wav, 02.wav, ...)")
    ap.add_argument("--timings", type=Path, help="JSON list of {start, end} per beat, from the voiceover")
    ap.add_argument("--audio", help="voiceover file path, relative to this folder")
    ap.add_argument("--out", type=Path, default=Path(__file__).with_name("index.html"))
    a = ap.parse_args()
    reel = json.loads(a.reel.read_text())
    timings = json.loads(a.timings.read_text()) if a.timings else None
    if a.vo_dir:
        timings = stitch_vo(a.vo_dir, len(reel["beats"]), a.out.parent)
        a.audio = "voiceover.wav"
    a.out.write_text(build(reel, timings, a.audio))
    times = beat_times(reel, timings)
    print(f"wrote {a.out}  ·  {len(times)} beats  ·  {times[-1][0] + times[-1][1]:.1f}s")


if __name__ == "__main__":
    main()
