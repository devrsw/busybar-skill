# Common BUSY Bar pitfalls

Mistakes that come up again and again when building for the BUSY Bar. Each entry: what goes wrong → what's actually true.

## API & payloads

**"The firmware doesn't support drawing over HTTP"** — concluded after many payload attempts all return 400.
→ Wrong conclusion. `POST /api/display/draw` works. A 400 almost always means a required field is missing: every element needs `id`; text needs `font`. Read the 400 body, check the schema in busy-lib's `index.d.ts`, and fix the payload before blaming firmware.

**Invented endpoints** — `/api/display/text`, `/api/display/update`, `/api/display/clear` → 404/405.
→ They don't exist. Drawing text is a `text` element in `/display/draw`; clearing is `DELETE /display/draw`. Check `http://<bar>/docs`.

**`/busybar/display/draw` → 404 on the device.**
→ `/busybar/` is the cloud proxy prefix (`https://api.busy.app/busybar`). The device uses `/api/`.

**Auth header `X-Token`.**
→ It's `X-API-Token` (LAN HTTP password). Cloud uses `Authorization: Bearer`. USB needs nothing.

**`POST /display/brightness` with a JSON body → 400.**
→ Brightness, volume, input and app actions take **query parameters** (`?value=50`, `?key=ok`, `?app_id=...`).

**Made-up device settings menus** in docs or troubleshooting advice.
→ Don't document UI paths you haven't seen. The real one: Web UI (http://10.0.4.20 over USB) → Settings → HTTP Access.

## Drawing

**Rectangles drawn with `color`** → white 1 px outlines instead of filled blocks.
→ Use `fill: "solid"`, `fill_colors: ["#RRGGBBAA"]`, `border_width: 0`.

**`clear_before_draw: true` in the draw payload** → not a firmware field; silently ignored. Stale elements from previous frames stay on screen.
→ Elements persist by id. Use stable ids and diff-draw; remove disappeared ids with `DELETE /display/draw` + `element_ids`, or `DELETE ?application_name=` before a full redraw. (Some wrapper libraries expose a `clear_before_draw` *option* that does that DELETE first — it's not an API field.)

**Lines stacked 16 px apart** (`y += 16` for each of several lines) → only the first line is visible; the front screen is 16 px tall.
→ Budget pixels with the font table: one large line, or two small/tiny lines.

**Text clipped at the bottom** (`tiny`/`small` text at `y=13`).
→ `y` is the line-box top and fonts have descenders; a `small` line needs ~9 rows. Check `y + lineHeight(font) <= 16`. A unit test asserting every element stays inside 72×16 catches this early.

**Unicode arrows/degree signs/emoji in text.**
→ Fonts are ASCII-only. Draw symbols as `xpmbitmap`.

**Back-screen coordinates used on the front** (e.g. `y: 24–28` with `display: "front"`), or a whole layout designed for a guessed screen size like 320×128.
→ Front is 72×16; back is 160×80. Check `display` and its real size (`SCREEN`, `getDisplayDimensions()` in busy-lib) before choosing coordinates.

**`textWidth()` / `render()` throws "font has no metrics loaded" at runtime** even though the build passed.
→ busy-cli bundles glyph maps only for fonts that appear as literal `font: "..."` properties in the source. A font name chosen from a variable or setting isn't bundled. Keep every font used as a literal (e.g. `const LARGE = { font: "large" } as const`).

**Priority 100 by default** → stomps on the user's BUSY focus timer (priority 90).
→ Default 50. Go above 90 only for things the user explicitly wants to interrupt focus.

## JS apps

**Treating `main()` like an Arduino `loop()`** → the app exits immediately or never quits.
→ The app lives only while a listener/timer/fetch is pending; quit by releasing all of them.

**Unbinding the input listener inside its own callback** → process stops mid-callback.
→ `setTimeout(unbind, 0)`.

**Handling `press` as a tap** → double actions.
→ Use `short`.

**Building with Node 26** → busy-cli build breaks.
→ Node 24 (`.nvmrc`, `engines: ">=24 <26"`, or `npx -p node@24 npm run build`).

**Assuming settings come back flat / always present.**
→ Groups are nested objects; values may be missing. Default everything in code; normalize colors to `#RRGGBBAA`.

**Assuming apps can't change their own settings.**
→ The `Settings.save()` global can write them (e.g. clear a one-time login code after use). Only the HTTP API is read-only for a running app.

**No app icons** → the APPS menu shows the generic unknown-app icon.
→ Ship `icon_front_8x8.png` (color) and `icon_back_11x11.png` (greyscale), 8-bit RGBA.

**Retrying a login every 30 s after "bad password"** → risks lockout on third-party accounts.
→ Distinguish auth errors from network errors; auth errors retry slowly (e.g. 10 min) and show the message on screen.

**Shipping GIF/WAV/JPG assets** → packaged to `resources/`, can't be displayed/played.
→ PNG/`.image` for images, `.anim` for animations, `.snd` for sounds.

**Calling `/assets/upload` or `/input` from an app** → blocked.
→ Apps can reach only the whitelisted local endpoints; ship assets inside the package.

**The bar reboots while the app runs** (default 128 KiB heap, ~50 KB script parsing JSON responses).
→ JS out-of-memory took down the whole device on firmware 1.3.1. Set `heap_size_kib: 256` for larger apps; parse only what you need.

**`if (response.status === 200)` never true** → the device runtime can report `status` as a string.
→ `Number(response.status)`.

**The server receives the text `undefined` as the request body** (and may reject the request) → `body: undefined` was in the fetch init.
→ Omit the `body` key unless there is a body.

**Error handling branches never match** (`err instanceof AuthError` is false for an `AuthError`).
→ `instanceof` on Error subclasses is unreliable in JerryScript; use a `kind` field.

**Trying to use MQTT/WebSockets from an app** → no client in the runtime.
→ HTTP `fetch` only; poll REST endpoints and estimate in between.

**Using a plain 1 s `setInterval` for a seconds display** → it isn't aligned to the second boundary and drifts, so displayed seconds can lag, skip or repeat.
→ Schedule each tick with `setTimeout` to the next second boundary (+~30 ms).

**Settings changes have no effect on the device** — every value stays at its default.
→ The `Settings` global is missing on some firmware (e.g. 27.14.0), so `loadValues()` returns `null`. Fall back to `device.AppsSettingsGet({ app_id })`, and don't rely on `saveValues()` (a silent no-op there).

**`npm run app:install` fails** (busy-cli 0.6 against firmware 27.14.0: the stage response closes early).
→ Install with curl: `POST /api/apps/stage` with the `.tgz` as the body, then `POST /api/apps/install?install_key=...` (see js-apps.md), or upload the `.tgz` in the bar's Web UI under Apps → Add app.

**Elements vanish after a notification or another app used the screen, and never come back.**
→ Diff-drawing only resends changed elements. Resend the whole frame every minute or so (reset the diff cache).

**Song titles, names or lyrics show boxes or nothing.**
→ Fonts are ASCII. Swap typographic quotes/dashes, strip accents (on a helper/server if you have one) and drop the rest; fall back when nothing is left.

**Holds feel unresponsive** — the firmware's `long` needs a longer hold than people expect.
→ Time `press` → `release` yourself (~600 ms threshold), and treat a `short` with no preceding `press` (from `/api/input`) as a tap.

**A macOS helper installed as a login item never starts** (or can't read its files) when the user unzipped it in Downloads/Desktop/Documents.
→ Copy it to `~/Library/Application Support/<app>/` and run it from there.

**A shell installer misreads saved values on the first install** — `PlistBuddy` printed "File Doesn't Exist, Will Create" to stdout.
→ Use its output only when it exits 0.

**The installer finishes but the bar never reaches the helper.**
→ Check end to end: the helper is listening, then the bar's first request arrives; otherwise suspect the macOS firewall or the network.

**A double-tap handler also fires the single-tap action.**
→ Delay the single action by the double-tap window (~400 ms) and cancel it when the second tap arrives.

## Animation

**"There's no way to make `.anim` files, so animate with timers"** → choppy motion capped at ~3 fps and a draw request per frame.
→ The format is documented in the firmware repo (`lib/anim_file/anim_file_format.h`), the firmware ships `scripts/seq2anim.py` for PNG sequences, and `templates/make_anim.py` generates them from code. Native `.anim` plays at 20 fps with no app requests.

**Animated element in the wrong color** → `.anim` colors are baked into the file.
→ One file per color option; restrict the color setting to that palette and fall back to a static bitmap.

**Animated element offset from where the static version sat** → the `.anim` canvas was padded for travel room.
→ Lay out at the unpadded size and shift the element by `-pad` with `dx`/`dy`.

## Process

- Verify against the real device early (`curl /api/version`, one test draw) before writing large amounts of code or docs around an assumption.
- Don't write pages of speculative troubleshooting docs; one correct, tested request beats them.
- `GET /api/screen?display=0` lets you check what's actually on the front screen without looking at the device (base64 BGR). `templates/screenshot.py` renders it as an LED-style PNG, or records an animated PNG — good for READMEs and for verifying animations.
- The apps API (`/apps/*`) is USB/LAN only and needs firmware 1.3.1+. The API doesn't tell you which app is running.
