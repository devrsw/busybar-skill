# Drawing on the BUSY Bar

## Screens

| Display | Size | Kind |
|---|---|---|
| `front` (default) | 72 × 16 | RGB LED matrix, `#RRGGBBAA` colors |
| `back` | 160 × 80 | greyscale OLED; color is mapped to grey |

Origin is top-left. Anything outside the screen is clipped. On the LED matrix black (`#000000FF`) is "off"; dim colors look much dimmer than on a monitor, and alpha blends toward black. Prefer saturated colors and keep secondary text around `#FFFFFF99`.

## Common element fields

Every element in `elements[]`:

| Field | Req | Notes |
|---|---|---|
| `id` | ✔ | unique within your `application_name`; drawing the same id replaces it |
| `type` | ✔ | `text`, `image`, `animation`, `countdown`, `rectangle`, `xpmbitmap` |
| `x`, `y` | | position of the **anchor** (default 0,0) |
| `align` | | which point of the element sits at `(x,y)`: `top_left` (default), `top_mid`, `top_right`, `mid_left`, `center`, `mid_right`, `bottom_left`, `bottom_mid`, `bottom_right` |
| `display` | | `front` (default) / `back` |
| `z_index` | | higher draws on top |
| `timeout` | | seconds before the element disappears; `0` = never. Mutually exclusive with `display_until` |
| `display_until` | | Unix seconds **as a string** |

`align: "center", x: 36, y: 8` centers an element on the front screen.

## Element types

### `text`
```json
{"id":"t","type":"text","text":"72F","font":"large","color":"#00FFCCFF","x":0,"y":1}
```
- `font` is **required**. `color` default white.
- Printable ASCII only — the fonts are bitmap ASCII. Anything else renders as fallback boxes or fails. Sanitize every string that comes from outside (song titles, names, API text) before drawing — keep the original for anything you send back to a service:
  ```ts
  const ascii = (text: string) => text
    .replace(/[‘’]/g, "'").replace(/[“”]/g, '"').replace(/[–—]/g, "-")
    .replace(/[^\x20-\x7E]/g, "")     // drops everything else, including accented letters and CJK
    .trim();
  ```
  Where you control a helper/server, strip accents there (`é` → `e`, e.g. Python `unicodedata.normalize("NFKD", s)` then drop combining marks) — JerryScript may not have `String.prototype.normalize`. Text that becomes empty after sanitizing (e.g. CJK lyrics) needs a fallback (show the title, or skip the line).
- `width` + `scroll_rate` (pixels per **minute**), `scroll_start_delay`, `scroll_repeat_delay` (ms) make a marquee when the text is wider than `width`.

### `rectangle`
```json
{"id":"bar","type":"rectangle","x":4,"y":12,"width":48,"height":3,"radius":1,
 "fill":"solid","fill_colors":["#00FF00FF"],"border_width":0}
```
- `fill`: `none` (default!), `solid`, `gradient_h`, `gradient_v`. Gradients take two `fill_colors`.
- Border defaults to **1 px white**. For a plain filled block always set `border_width: 0`.
- There is **no `color` field** on rectangles — it's silently ignored and you get a white outline.

### `xpmbitmap` — the way to draw icons, arrows, sprites
```json
{"id":"arrow","type":"xpmbitmap","x":40,"y":3,"data":"! XPM2\n3 3 2 1\n# c #FF0000\n. c none\n.#.\n###\n.#.\n"}
```
- XPM2 text: `! XPM2`, then `width height ncolors cpp`, color lines (`<chars> c <value>`), then pixel rows.
- Limits: ≤ 32 colors, cpp ≤ 4, size ≤ target display. `none` = transparent. Optional `opacity` 0–100.
- Build it with busy-lib instead of by hand:

```ts
import { generateXpm2, scaleGrid } from "@busy-app/busy-lib";
const UP = ["...##...", "..####..", ".######.", "########", "...##...", "...##...", "...##..."];
const data = generateXpm2({ palette: { "#": "#00FF30", ".": "none" }, grid: UP });
// { type: "xpmbitmap", id: "arrow", data, width: 8, height: 7 }   (width/height needed for layout)
```
- Derive variants with grid transforms rather than hand-drawing each direction. `scaleGrid(grid, 2)` doubles pixels.

```ts
const flipV = (g: string[]) => g.slice().reverse();
const flipH = (g: string[]) => g.map((line) => line.split("").reverse().join(""));
const transpose = (g: string[]) => g[0].split("").map((_, x) => g.map((line) => line[x]).join(""));
const RIGHT = flipH(transpose(UP));
const DOWN = flipV(UP);
const DOUBLE_UP = UP.map((line) => `${line}.${line}`);
```
- Recolor a bitmap by regenerating with a different palette — cheap and avoids shipping assets.

### `image`
`{"type":"image","path":"icon.png"}` (app/uploaded asset) or `{"stock_path":"..."}` (firmware stock). PNG; in a JS app put files in `src/images/`. Uploaded via `/assets/upload` from external clients. Optional `opacity`. The device doesn't report image size, so give `width`/`height` to the busy-lib layout engine.

### `countdown`
Firmware-rendered live timer — no redraws needed.
```json
{"id":"cd","type":"countdown","timestamp":"1767225600","direction":"time_left","show_hours":"when_non_zero",
 "color":"#FFB000FF","x":36,"y":8,"align":"center"}
```
`timestamp` is Unix seconds **as a string**. `direction`: `time_left` / `time_since`. `show_hours`: `when_non_zero` / `always`.

### Custom ticking clock (when `countdown` isn't enough)

Need your own format, font, colors, or a paused/frozen state? Draw the clock yourself, but cheaply:

- **One text element per character, each centered in a fixed-width cell** (cell = widest digit from `textWidth("0".."9", font)`; colon gets its own width; add the font's inter-glyph gap `textWidth("00") - 2*textWidth("0")`). A narrow `1` then doesn't shift its neighbours, and text beside the clock only moves when a digit is added (`9:59` → `10:00`).
- **Number the ids from the right** (`d0` = last seconds digit). When a digit is added on the left, the seconds keep their ids, so diff-drawing still resends only what changed — usually just 1–2 tiny elements per second.
- **Tick on the second boundary**, not with `setInterval(1000)` which drifts: `setTimeout(tick, 1000 - ((Date.now() - startMs) % 1000) + 30)` and reschedule after each draw. Run it only while the clock is running.

### Negative `y` to align caps

Text `y` is the line-box top, so caps start a row or two below it (cap top in the font table). Negative `y` is fine: `bold` at `y: -1` puts its caps on rows 1–7, leaving rows 9–15 for a `small` line at `y: 7`. Use this to pack a bold line over a small line.

### `animation`
See [animation.md](animation.md).

## Fonts — measured metrics

From busy-lib's glyph maps (`lineHeight`, `fontBaseline`, `capBox`, `textWidth`). "Cap top" is how many blank rows sit above a capital inside the line box; text `y` positions the **line box top**, so a `normal` capital drawn at `y=0` actually starts lighting at row 2.

| font | line height | baseline | cap top | cap height | "0" width | "12:34" width | "Hello" width |
|---|---|---|---|---|---|---|---|
| `tiny` | 6 | 5 | 1 | 4 | 4 | 18 | 16 |
| `small` | 9 | 7 | 2 | 5 | 4 | 17 | 17 |
| `normal` | 11 | 9 | 2 | 7 | 6 | 26 | 24 |
| `condensed` | 11 | 9 | 2 | 7 | 5 | 22 | 24 |
| `bold` | 11 | 9 | 2 | 7 | 7 | 30 | 29 |
| `large` | 13 | 11 | 2 | 9 | 7 | 28 | 28 |
| `extra_large` | 14 | 12 | 2 | 10 | 8 | 32 | 37 |
| `global` | 11 | 8 | 1 | 7 | 6 | 23 | 20 |
| `superscript` (fw 1.3.1+) | 11 | 9 | 2 | 7 | 4 | 18 | 24 |

Rules of thumb for 72×16:
- Hero number: `extra_large` (10 px caps) or `large` (9 px). Leaves room for one side column.
- Two stacked lines: `small` + `small` (5 px caps each) or `tiny` + `tiny`. Two `normal` lines do **not** fit.
- ~12 `small` chars or ~9 `normal` chars span the full width. Truncate or marquee long strings.
- Measure in code with `textWidth(text, font)` — no guessing.

### Font metrics are bundled only for fonts named literally

busy-cli scans the source for literal `font: "..."` properties and bundles glyph maps **only for those fonts**. `DisplayDraw` doesn't care, but `textWidth()`, `measure()` and `render()` **throw at runtime** for a font whose map wasn't bundled. So never build font names dynamically (`font: big ? "large" : "small"` from a variable, `font: cfg.font`, string concatenation). Keep each font as a literal property somewhere in the source:

```ts
// Literal `font:` properties tell the build which glyph maps to bundle.
const SMALL = { font: "small" } as const;
const LARGE = { font: "large" } as const;
const el = { id: "t", type: "text", text, ...(big ? LARGE : SMALL) } as const;
```

### Largest font that fits

```ts
import { textWidth, type DeviceFont } from "@busy-app/busy-lib";
// Objects with literal `font:` keep every candidate bundled (see above).
const FONTS: { font: DeviceFont }[] = [{ font: "extra_large" }, { font: "large" }, { font: "normal" }, { font: "small" }];

function fit(text: string, room: number): DeviceFont {
  for (const { font } of FONTS) if (textWidth(text, font) <= room) return font;
  return FONTS[FONTS.length - 1].font;
}
// room = 72 - (width already used by siblings) - gaps
```

### Marquee only when it overflows

```ts
const el = { id: "task", type: "text", text, font: "small", x, y, color } as Record<string, unknown>;
if (textWidth(text, "small") > room) {
  Object.assign(el, { width: room, scroll_rate: 1200, scroll_start_delay: 1500, scroll_repeat_delay: 3000 });
}
```
Text that fits stays still and readable; only overflowing text scrolls.

To use the metric helpers outside the busy-cli build (e.g. Node tests), register the maps:
```ts
import * as fonts from "@busy-app/busy-lib/fonts";
import { registerFontMaps } from "@busy-app/busy-lib";
registerFontMaps({ fonts: Object.assign({}, ...Object.values(fonts).map((f: any) => f.fonts)) });
```
(busy-cli's Vite plugin bundles them automatically for apps.)

## Layout engine (busy-lib)

Don't hand-place coordinates for anything non-trivial. Build a tree and let `render()` compute `x/y`:

```ts
import { row, column, stack, render, type Node } from "@busy-app/busy-lib";

const frame: Node = row({ width: 72, height: 16, justify: "center", align: "center", gap: 3 }, [
  { type: "text", id: "value", text: "123", font: "extra_large", color: "#00FF30FF" },
  column({ gap: 2, align: "end" }, [
    { type: "text", id: "delta", text: "+4", font: "small", color: "#FFFFFF99" },
    { type: "text", id: "age",   text: "2m", font: "small", color: "#FFFFFF99" },
  ]),
]);
const elements = render(frame);            // → DisplayDraw elements with x/y filled in
// render(frame, { display: "back", width: 160, height: 80 }) for the back screen
```

- `row` (left→right), `column` (top→bottom), `stack` (overlapping; last child on top).
- Container props: `gap`, `padding` (number or `{top,right,bottom,left}`), `justify` (`start|center|end|between`), `align` (`start|center|end|baseline`), fixed `width`/`height` (else fits content).
- Any node can carry `dx`/`dy` to nudge it after layout — handy for 1-px animation offsets.
- Text is measured by the engine. `image`, `animation`, `countdown`, `xpmbitmap` need explicit `width`/`height`.
- `align: "baseline"` in a row lines up mixed font sizes on their baselines.
- `measure(node)` returns computed sizes if you need them.
- `list({ id, items, selected, x, y, width, height, font, style: {color, activeColor}, scrollbarStyle: {trackColor, thumbColor} })` returns ready elements for a scrolling menu with the selected row centered — pair it with the encoder.

## Diff-drawing (do this always)

Elements persist by id, so only send what changed and delete what disappeared:

```ts
let shown = new Map<string, string>();      // id → JSON last sent

async function draw(frame: Node) {
  const elements = render(frame);
  const next = new Map<string, string>();
  const changed = [];
  for (const el of elements) {
    const json = JSON.stringify(el);
    next.set(el.id, json);
    if (shown.get(el.id) !== json) changed.push(el);
  }
  const removed = [...shown.keys()].filter((id) => !next.has(id));
  try {
    if (removed.length) await device.DisplayClear({ application_name: APP, element_ids: removed });
    if (changed.length) await device.DisplayDraw({ application_name: APP, priority: 50, elements: changed });
    shown = next;
  } catch (err) {
    shown = new Map();                      // screen state unknown → resend everything next time
    throw err;
  }
}
```

Also guard against overlapping draws: if a draw is in flight, set a `redrawPending` flag and run once more when it finishes (see `templates/main.ts`).

## Design guidance for 72×16

- One glanceable fact per screen. Big value + small secondary info beats a sentence.
- Color carries meaning (range/status); keep it consistent and configurable.
- Show staleness: grey the value when data is old, replace with `---` when very old.
- Use short status messages for error states (`No connection`, `Bad login`, `Set API key`) — the user has no other UI.
- **Use the back screen for details.** The front gets the one glanceable fact; the 160×80 greyscale back can hold description, project, totals, the last error, and a control cheat-sheet (`OK refresh  BACK quit`). Set `display: "back"` on those elements (or `render(tree, { display: "back", width: 160, height: 80 })`). Keep back-screen text within ~145 px: the firmware draws status icons along the right edge. Make it a setting (some users never look at the back).
- **Small status markers** — a 1–2 px dot in a corner (e.g. amber = changes waiting to sync, red = sync failing) says a lot without stealing space; explain it on the back screen.
- **Transient feedback**: after a button action, flash a short word (`Started`, `Paused`) for ~1.5 s via a timer, plus a one-off `led_notification_color` (green/amber/red), then return to the normal frame.
- Symbols (arrows, weather icons, progress) → `xpmbitmap`, not text.
- Progress indicators — two recipes:
  - **Bar** (2 px along the bottom): a translucent track plus a fill on top. Skip the fill element when its width rounds to 0 (and clear it if it was shown).
    ```ts
    const w = Math.round((72 * percent) / 100);
    const els = [{ id: "track", type: "rectangle", x: 0, y: 14, width: 72, height: 2,
                   fill: "solid", fill_colors: ["#FFFFFF26"], border_width: 0 }];
    if (w > 0) els.push({ id: "fill", type: "rectangle", x: 0, y: 14, width: w, height: 2,
                          fill: "solid", fill_colors: [color], border_width: 0, z_index: 1 });
    ```
  - **Segmented 1 px line** (e.g. time until the next data update): a single 72×1 `xpmbitmap` built from a string grid (`#` filled, `-` dim, `.` gap between segments). Layout: `column({ width: 72, height: 16, gap: 1 }, [row({ height: 14, ... }, content), line])` — 14 + 1 + 1 = 16.
  - Advancing either on a coarse tick (e.g. every 5 s) with diff-drawing sends only the one changed element.
