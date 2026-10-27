# Animation on the BUSY Bar

Four ways to make the bar move, cheapest first. Pick the cheapest that does the job — every redraw is an HTTP request the device's own web server has to handle.

## 1. Let the firmware animate (zero requests)

These animate on the device after a single draw:

- **Scrolling text** — give a `text` element a `width` narrower than the text plus `scroll_rate` (px per **minute**, e.g. `1000`), `scroll_start_delay` and `scroll_repeat_delay` (ms).
  ```json
  {"id":"msg","type":"text","text":"Next train to Downtown - 5 min","font":"small",
   "x":0,"y":4,"width":72,"scroll_rate":1200,"scroll_start_delay":1000,"scroll_repeat_delay":2500}
  ```
- **Countdown / count-up** — `countdown` element with `timestamp` (Unix seconds as string). Ticks every second on its own; never redraw a clock every second yourself.
- **LED blink** — `led_notification_color` on a draw request blinks the status LED. Send it once per event (track what you already blinked for) rather than on every redraw.
- **Element expiry** — `timeout` (s) or `display_until` makes temporary overlays disappear without a follow-up request.

## 2. `.anim` animation assets

```json
{"id":"spin","type":"animation","path":"spinner.anim","x":0,"y":0,"loop":true,"section":"default"}
```

| Field | Meaning |
|---|---|
| `path` / `stock_path` | `.anim` in the app's assets, or a firmware stock animation |
| `loop` | loop the requested section (default false) |
| `section` | named section to play; `"default"` = whole animation |
| `await_previous_end` | when re-sending the same id, let the current section finish before starting the new one — use for seamless state transitions (intro → loop → outro) |
| `opacity` | 0–100 |

- `.anim` is a BUSY-specific binary format. busy-cli only packages files that are already `.anim` (`src/animations/`); it does **not** convert GIFs or PNG sequences (a `.gif` lands in `resources/` with a build warning and can't be displayed). The public docs don't specify how to author `.anim` files — don't fabricate a converter. If the user has `.anim` files (e.g. exported from BUSY's tools), use them; otherwise use technique 3.
- In TypeScript, `import url from "./animations/x.anim"` is typed via `declare module '*.anim'` in `types/env.d.ts`.
- busy-lib layout needs explicit `width`/`height` on animation nodes.
- Section switching pattern: send `{id:"pet", section:"walk", loop:true}`; on an event send `{id:"pet", section:"jump", loop:false, await_previous_end:true}`, then back to `walk`.

## 3. Timer-driven frames (you redraw)

For custom motion with bitmaps/rectangles. Keep it **coarse**: a few frames per second at most, and only while visible motion is needed.

```ts
const NUDGE: [number, number][] = [[0, 0], [1, 0], [0, 0], [-1, 0]];   // tiny idle wiggle
let frameIdx = 0;
let animTimer: ReturnType<typeof setInterval> | null = null;

function startAnim() {
  if (animTimer) return;
  animTimer = setInterval(() => {
    frameIdx = (frameIdx + 1) % NUDGE.length;
    void draw().catch(report);            // diff-draw: only the moving element is resent
  }, 500);
}
function stopAnim() {
  if (animTimer) clearInterval(animTimer);
  animTimer = null;
  frameIdx = 0;
}

// in the frame builder: offset just the moving node
const [dx, dy] = NUDGE[frameIdx];
{ type: "xpmbitmap", id: "arrow", data, width: 8, height: 10, dx, dy }
```

Pattern that works well — a "nudging" trend arrow: a 400 ms step timer, the arrow rests for 4 steps then nudges 1 px along its direction (a `NUDGE` table of `[dx, dy]` per direction) for one step. The offset is applied to the rendered `arrow` element's `x/y` before diffing, so rest steps produce an identical frame and send **no request** — only two small draws per 2 s cycle. The timer starts only while an arrow is on screen and an "animate" setting is on, and is cleared on quit.

Rules:
- Animate only the element that moves; diff-drawing keeps the request tiny. Never resend the whole screen per frame.
- Skip a frame if the previous draw hasn't returned (single in-flight request).
- 2–4 fps is the practical ceiling over HTTP; for smooth motion use `.anim` instead.
- Precompute frames (XPM strings) once; don't regenerate per tick.
- Stop the interval when the animation isn't needed (stale data, error message, app quitting) — a running interval also keeps a JS app alive.
- Make motion optional via a settings boolean (e.g. `animate`) — some people find it distracting on a desk.

Ideas that read well at 72×16: 1-px "nudge" of a trend arrow in its direction, a progress bar filling, a sprite sliding along a road (`x` from a computed progress), blinking a colon via alternating color (cheaper than add/remove).

## 4. Transitions between states

- Fade: re-send an `image`/`xpmbitmap` with stepped `opacity` (3–4 steps), or text with stepped alpha in `color`.
- Slide: animate `dx` on a container node over a few frames, then settle.
- Keep transitions under ~1 s and don't run them for every data update — only on meaningful state changes (e.g. entering an alarm state).
