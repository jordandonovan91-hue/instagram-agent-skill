# Reel template

Turns a reel script into a finished 1080x1920 Instagram Reel with
[HyperFrames](https://github.com/heygen-com/hyperframes): animated cards, simple
UI mockups, and word-by-word burned-in captions, all inside Instagram's safe zone.
No filming. Built for the talk-based format of @small_bizaitools.

## Make a Reel

1. Write the script with `/ig-reel`, then copy it into a new file in `reels/`
   (see `reels/w1-tue-customer-replies.json`). Each beat has the spoken line
   (`say`), a 6-word on-screen card (`card`), and a visual.
2. Build and render:

   ```bash
   export HYPERFRAMES_NO_TELEMETRY=1        # turns off HyperFrames' anonymous usage stats
   python3 build.py reels/my-reel.json      # writes index.html
   npm run check                            # layout, contrast and motion lint
   npm run render                           # MP4 lands in renders/
   ```

## Add the voiceover

Generate one audio clip per beat (Kokoro-FastAPI on your own machine, ElevenLabs,
or your own recordings), name them `vo/01.wav`, `vo/02.wav`, and so on, then:

```bash
python3 build.py reels/my-reel.json --vo-dir vo/
npm run render
```

The clips are joined into `voiceover.wav` and every scene and caption is re-timed
to the real audio. Needs `ffmpeg`.

Every beat after the hook is held long enough for its on-screen text to be read
(about 0.5s plus 0.3s a word, the floor `npm run check` uses). With a voiceover,
that hold is added as a short pause after the line. The hook is never stretched.

## Visual types

| type | what it shows | fields |
| --- | --- | --- |
| `repeat` | the same message stacked and struck through | `text` |
| `bubbles` | incoming customer messages | `items` |
| `chat` | a generic AI chat window, lines typed in | `label`, `lines` |
| `prompt` | a prompt typed into the chat | `text` |
| `cards` | cards filed into a folder | `items`, `target` |
| `shortcut` | a text shortcut expanding into a full reply | `trigger`, `text` |
| `tiles` | numbered tiles, some highlighted | `items`, `active` (index, list or `"all"`) |
| `cta` | save icon and handle | `text` |

Mockups are generic on purpose. Use a tool's own screenshots only from its
official press kit, and never imply you've used a tool you haven't.

Requirements: Node 22+, Python 3, ffmpeg. GSAP and Inter (SIL OFL) are bundled in
`assets/` so renders work offline. HyperFrames is pinned to 0.9.6.
