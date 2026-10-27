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

**The best option for smooth, continuous motion**: the firmware plays the frames itself at the file's fps (20 fps is typical), with zero requests from your app — this is how the built-in Weather icons animate.

```json
{"id":"spin","type":"animation","path":"animations/spinner.anim","x":0,"y":0,"loop":true}
```

In a JS app, `path` is relative to the app package: a file at `src/animations/spinner.anim` is drawn with `"path": "animations/spinner.anim"`.

| Field | Meaning |
|---|---|
| `path` / `stock_path` | `.anim` in the app's assets, or a firmware stock animation |
| `loop` | loop the requested section (default false) |
| `section` | named section to play; `"default"` = whole animation |
| `await_previous_end` | when re-sending the same id, let the current section finish before starting the new one — use for seamless state transitions (intro → loop → outro) |
| `opacity` | 0–100 |

- busy-cli only packages files that are already `.anim` (`src/animations/`); it does **not** convert GIFs or PNG sequences (a `.gif` lands in `resources/` with a build warning and can't be displayed). Generate `.anim` files yourself — see below.
- busy-lib layout needs explicit `width`/`height` on animation nodes.
- In TypeScript, `import url from "./animations/x.anim"` is typed via `declare module '*.anim'` in `types/env.d.ts`.
- Section switching pattern: send `{id:"pet", section:"walk", loop:true}`; on an event send `{id:"pet", section:"jump", loop:false, await_previous_end:true}`, then back to `walk`.

### The `.anim` format ("bicycle1") and how to make one

The format is defined in the firmware repo, `busy-app/busybar-firmware`: `lib/anim_file/anim_file_format.h`. Two ways to produce files:

1. **[templates/make_anim.py](../templates/make_anim.py)** (recommended for generated motion) — dependency-free Python. Build each frame as RGBA bytes in code, convert with `rgba_to_bgra()`, and call `write_anim(path, frames, width, height, fps, sections=None)`. It writes BGRA8888 raw pixels, the first frame of each section whole and later frames as only changed pixels. Its output is byte-identical to a generator whose animations are in production use on the device (single-section files; multi-section output follows the same rules as the official converter but hasn't been checked on a device yet).
2. **The firmware's own converter**, `scripts/seq2anim.py`, for hand-drawn frames: input is `name.zip` containing a `name/` folder with `0.png`, `1.png`, … (all the same size) and `meta.json`:
   ```json
   {"fps": 20, "color_mode": "argb8888", "sections": [{"name": "walk", "start": 0, "end": 7}]}
   ```
   `color_mode` is `argb8888`, `rgb888` or `gray4` (back screen). Run it from a firmware checkout (it imports the repo's `flipper` script helpers and needs Pillow): `python3 scripts/seq2anim.py -o out.anim name.zip`. It compresses better than the template (QOI/RLE pixel encodings).

Header layout, little-endian: `"bicycle1"`, flags u8, width u8, height u8 (so ≤ 255 px), color mode u8 (0 rgb888, 1 gray4, 2 argb8888 stored as B,G,R,A), max mask len u16, max pixels len u16, fps u8, pad u8, sections chunk len u32, frames chunk len u32, section count u32, frame count u32. Each section: start u32, end u32, byte offset of its first frame u32, NUL-terminated name. Each frame: a byte with pixel encoding (low nibble) and mask encoding (high nibble), mask bit count u16, pixel byte count u16, then the mask and pixel data.

Authoring tips (from a production trend-arrow animation):
- **Colors are baked in.** Generate one file per color the user can pick, and constrain the color setting to that palette (an `enum`, not a free `color`). If the configured color has no file, fall back to a static `xpmbitmap`.
- **Seamless loops:** move at constant speed along the path and fade in over the first ~30 % and out over the last ~30 %, so the jump back to the start is invisible.
- **Sub-pixel motion:** render with a box filter (pixel coverage → alpha) so 1–3 px of travel at 20 fps looks smooth instead of stepping.
- **Make transparent pixels all-zero** (`0,0,0,0`) so unchanged background never counts as a changed pixel — keeps files small.
- **Pad the canvas** along the direction of travel, keep the layout node at the unpadded size, and shift the element back with `dx`/`dy = -pad` so it sits where a static version would.
- Encode meaning in speed (e.g. faster loop for a faster-changing value) rather than adding more pixels.
- **Mind package size:** every variant is a file (7 shapes × 2 sizes × 12 colors = 168 files, 2.3 MB). Keep canvases small and the palette short.
- Regenerate with a script checked into the app (`tools/`), not by hand, and keep shapes shared with the TypeScript side in sync.

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
- About **3 visible frames per second** is the ceiling: the bar lays out roughly 3 draw requests a second, so faster timers just drop frames. For smooth motion use `.anim` instead.
- Precompute frames (XPM strings) once; don't regenerate per tick.
- Stop the interval when the animation isn't needed (stale data, error message, app quitting) — a running interval also keeps a JS app alive.
- Make motion optional via a settings boolean (e.g. `animate`) — some people find it distracting on a desk.

### Composite sprites: animate only the moving part

Split a scene into a static bitmap plus small moving parts, each its own element. Example — a 14×16 3D-printer icon:

```ts
const FRAME = generateXpm2({ palette: { "#": "#8C8C8C", "=": "#787878", _: "#B4B4B4", ".": "none" }, grid: [/* frame, rail, bed */] });
const HEAD  = generateXpm2({ palette: { H: "#E6E6E6", N: "#FF7A00", ".": "none" }, grid: ["HHHHH", "HHHHH", ".HHH.", "..N.."] });
const HEAD_X = [1, 2, 4, 6, 8, 8, 6, 4, 2, 1];          // sweep positions, one per 500 ms step

[
  { id: "frame", type: "xpmbitmap", data: FRAME, x: 2, y: 0 },                       // sent once
  { id: "head",  type: "xpmbitmap", data: HEAD,  x: 2 + HEAD_X[step], y: 2, z_index: 2 }, // resent per step
  { id: "part",  type: "rectangle", x: 6, y: 13 - h, width: 6, height: h,             // grows with progress
    fill: "solid", fill_colors: [color], border_width: 0, z_index: 1 },
]
```

Each step resends only the ~30-byte `head` element; the part grows only when progress changes. Park the moving part (fixed position, no timer) when the thing it represents is idle, failed or finished.

Ideas that read well at 72×16: 1-px "nudge" of a trend arrow in its direction, a progress bar filling, a sprite sliding along a road (`x` from a computed progress), blinking a colon via alternating color (cheaper than add/remove).

## 4. Transitions between states

- Fade: re-send an `image`/`xpmbitmap` with stepped `opacity` (3–4 steps), or text with stepped alpha in `color`.
- Slide: animate `dx` on a container node over a few frames, then settle.
- Keep transitions under ~1 s and don't run them for every data update — only on meaningful state changes (e.g. entering an alarm state).

### Counting a number to its new value

When a displayed value changes, count from the old value to the new one instead of jumping. Scale the duration to the size of the jump (at ~3 visible frames/s, 0.9 s ≈ 3 steps, 1.5 s ≈ 5, 2.2 s ≈ 7), skip it for tiny changes, ease in and out so the steps spread evenly, and flash the color toward white on big jumps:

```ts
const FRAME_MS = 110;   // timer runs only while a tween is active

function tweenFor(from: number, to: number, now: number) {
  const jump = Math.abs(to - from);
  if (jump < 3) return null;
  const duration = jump < 10 ? 900 : jump < 20 ? 1500 : 2200;
  return { from, to, start: now, duration, flash: jump >= 20 };
}

function tweenAt(t: { from: number; to: number; start: number; duration: number; flash: boolean }, now: number) {
  const p = (now - t.start) / t.duration;
  if (p >= 1) return null;                                   // done: clear the timer, draw the real value
  const u = Math.max(0, p);
  const eased = u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;
  return { value: t.from + (t.to - t.from) * eased, flash: t.flash ? Math.max(0, 1 - p * 2) : 0 };
}

/** Mixes two #RRGGBBAA colors; t = 0 gives a, 1 gives b. Use mixColor(color, "#FFFFFFFF", flash). */
function mixColor(a: string, b: string, t: number): string {
  let out = "#";
  for (let i = 1; i < 9; i += 2) {
    const x = parseInt(a.slice(i, i + 2), 16), y = parseInt(b.slice(i, i + 2), 16);
    const v = Math.round(x + (y - x) * t);
    out += (v < 16 ? "0" : "") + v.toString(16).toUpperCase();
  }
  return out;
}
```

Only the value element changes per frame, so diff-drawing sends one small element per step.
