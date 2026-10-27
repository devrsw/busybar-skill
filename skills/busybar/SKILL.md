---
name: busybar
description: Build software for the BUSY Bar (busy.app) — the 72×16 RGB LED status display with a 160×80 back OLED. Use whenever the user is drawing to a BUSY Bar, calling its HTTP API (display/draw, assets, audio, apps, input, status websocket), writing an on-device JavaScript app (busy-cli, @busy-app/busy-lib, manifest.json, settings.json, listen("input")), designing pixel layouts/fonts/bitmaps for the bar, animating it, or debugging 400/404/405 errors from it. Also triggers on "busybar", "busy bar", "BUSY Bar", 10.0.4.20, busylib.
---

# BUSY Bar

The BUSY Bar is a desk status device. What matters for code:

| | |
|---|---|
| Front screen | **72 × 16** RGB LED matrix. Default target. Colors are `#RRGGBBAA`. |
| Back screen | **160 × 80** greyscale OLED (`display: "back"`). |
| Inputs | Buttons `ok`, `start`, `back`, plus a rotary `encoder`. Long-press Back force-quits a JS app. |
| Status LED | Blink it with `led_notification_color` on a draw request. |
| Firmware | Exposes an HTTP API (`/api/...`), a status websocket, and runs JS apps (firmware 1.3.1+). |
| USB address | Plugged in over USB the bar is a network device at `http://10.0.4.20` — no password. |

## Pick the right architecture first

1. **On-device JavaScript app** (preferred for anything that should keep running): runs on the bar in JerryScript, fetches remote data itself over Wi-Fi, draws via `http://localhost/api/display/draw`, reads buttons. No computer needs to stay on. → [references/js-apps.md](references/js-apps.md)
2. **External HTTP client** (a server, script, Home Assistant, etc. pushes frames): good for integrations that already live elsewhere, or for controlling things apps can't reach (apps install, input injection, storage). → [references/http-api.md](references/http-api.md)

Both use the same draw payload and the same layout helpers. Read:

- [references/drawing.md](references/drawing.md) — element types, fonts with measured pixel metrics, coordinates, the busy-lib `row/column/stack` layout engine, XPM bitmaps, diff-drawing.
- [references/animation.md](references/animation.md) — `.anim` elements and sections, timer-driven frame animation, scrolling text, countdowns, LED blink.
- [references/pitfalls.md](references/pitfalls.md) — **read before debugging.** Common BUSY Bar mistakes and what actually fixes them.
- [templates/main.ts](templates/main.ts) — a correct minimal on-device app (poll + diff-draw + clean quit).
- [templates/icons.py](templates/icons.py) — dependency-free generator for the 8×8 front / 11×11 back app icons from pixel grids.

## Non-negotiables (learned the hard way)

1. **Ground truth is the device, not memory.** Check `GET /api/version` (`{"api_semver":"..."}`) and the device's own docs at `http://<bar>/docs` before claiming an endpoint or field exists. The typed source of truth is `@busy-app/busy-lib`'s `dist/index.d.ts` (`components['schemas']`). Never invent endpoints like `/api/display/text` — they don't exist.
2. **A 400 from `/display/draw` is a payload bug, not a firmware limitation.** Every element needs `id` and `type`; `text` needs `text` **and** `font`; `rectangle` needs `width`/`height`; `countdown` needs `timestamp` (string), `direction`, `show_hours`. Read the error body — it names the problem.
3. **Rectangles fill with `fill: "solid"` + `fill_colors: ["#RRGGBBAA"]`.** There is no `color` on rectangles; the default is `fill: "none"` with a 1 px white border. Set `border_width: 0` for a plain block.
4. **16 pixels is tiny.** One `extra_large`/`large` line, or two `small`/`tiny` lines. Text `y` is the top of the font's line box, which includes blank rows — measure, don't guess (see font table in drawing.md).
5. **Elements persist by `id` per `application_name`.** Redrawing does not erase old ids. Send only changed elements; remove vanished ids with `DELETE /display/draw` + `element_ids`. There is no `clear_before_draw` field.
6. **Fonts are ASCII bitmap fonts.** No `→`, `°`, emoji. Draw symbols as `xpmbitmap` elements. In apps, write every font as a literal `font: "..."` in source — busy-cli bundles metrics only for those, and `textWidth()`/`render()` throw for any other.
7. **Priority 1–100, default 50.** Built-in apps are 10, an active BUSY/CUSTOM work session is 90. Use 50 unless the user wants to interrupt a focus session (91+), and never use 100 by habit.
8. **The bar is a small embedded device.** Poll on human time scales, keep one draw request in flight, back off on errors, redraw only when something visible changes. A JS app that runs out of heap can **reboot the whole bar** — size `heap_size_kib` for your script plus the responses you parse (256 for larger apps).
9. **The app runtime is JerryScript, with quirks:** `Number(response.status)` (it may be a string), never pass `body: undefined` to `fetch`, and don't rely on `instanceof` for Error subclasses — see js-apps.md.
10. **Never modify BUSY Bar firmware.** If a capability is missing, degrade gracefully or report the required API version.

## Quick smoke test (USB)

```bash
curl http://10.0.4.20/api/version
curl -X POST http://10.0.4.20/api/display/draw -H 'Content-Type: application/json' -d '{
  "application_name": "test", "priority": 50,
  "elements": [{"id": "hello", "type": "text", "text": "Hello!", "font": "normal",
                "color": "#00FF88FF", "x": 36, "y": 8, "align": "center", "timeout": 10}]
}'
curl -X DELETE 'http://10.0.4.20/api/display/draw?application_name=test'
```

Over Wi-Fi add `-H 'X-API-Token: <HTTP access password>'` and use the bar's LAN IP.

## Workflow for a new BUSY Bar feature

1. Decide app vs external client (above). Confirm the target firmware's `api_semver`.
2. Sketch the 72×16 layout in pixels first (use the font table), then build it with busy-lib `row/column/stack` + `render()`.
3. Give every element a stable id; implement diff-drawing.
4. For apps: manage lifecycle explicitly (timers, listeners), quit cleanly on Back `short`, run `npm run typecheck && npm run build`, install with `npm run app:install` (Node 24, not 26).
5. Verify on the device; for headless checks, `GET /api/screen?display=0` returns the current front frame.
