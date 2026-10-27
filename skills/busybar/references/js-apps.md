# On-device JavaScript apps

Firmware 1.3.1+ runs JavaScript apps on the bar itself in **JerryScript** (ES2020-ish). Not Node, not a browser. In a scaffolded project, read its `README.md` (and `AGENTS.md` if present) for the toolchain's own rules.

## Scaffold and toolchain

```bash
npm create @busy-app/app        # or: npx @busy-app/cli create my-app
```

Deps: `@busy-app/cli` (dev, provides `busy-cli`), `@busy-app/busy-lib` (runtime), `typescript`, `vite`.

**Use Node 24.** Node 26 breaks the busy-cli build. Put `v24` in `.nvmrc` and `"engines": {"node": ">=24 <26"}`. Without nvm/fnm: `npx -p node@24 npm run build`.

| Script | Command |
|---|---|
| `npm run typecheck` | `tsc` (strict) |
| `npm run build` | `busy-cli build` → `dist/<id>.tgz`. Flags: `--no-minify`, `--bundle`, `--emit dir|both`, `--addr <host>` |
| `npm run app:install` | upload + install `dist/<id>.tgz` (USB by default) |
| `npm run app:run` / `app:stop` / `app:uninstall` | launch / quit / remove (settings kept) |

Over Wi-Fi: `npm run app:install -- --addr <ip> --password <http-password>`. `app:install` does not build — build first.

The scaffold also ships `AGENTS.md` (rules for coding agents), a `README.md`, and two GitHub Actions workflows:
- **CI** (`ci.yml`): on push to `main` and PRs — `npm ci`, `npm run typecheck`, `npm run build`, on the Node version from `.nvmrc`.
- **Release** (`release.yml`): on a tag like `1.2.0` — fails unless the tag equals `version` in `src/appmeta/manifest.json` and `api_version` is set, then builds with `--tgz-name "{id}-{version}.tgz"` and attaches it to a GitHub release (creating it, or adding to one made in the UI). To release: bump `version` in the manifest (and `package.json`), commit, tag the same version, push the tag.

## Layout

```
my-app/
├── src/
│   ├── main.ts                 entry point (fixed name; becomes scripts/main.js)
│   ├── appmeta/
│   │   ├── manifest.json       required
│   │   ├── settings.json       optional settings screen
│   │   ├── icon_front_8x8.png  optional, 8×8 color (APPS menu, front)
│   │   └── icon_back_11x11.png optional, 11×11 greyscale (back screen)
│   ├── images/   (.png, .image)
│   ├── animations/ (.anim)
│   └── sounds/   (.snd)
├── shared/                     helpers imported as @shared/*
└── types/env.d.ts              globals: listen(), __BUSY_ADDR__, *.anim
```

Other formats (`.jpg`, `.gif`, `.svg`, `.wav`, `.mp3`) go to `resources/` with a warning and **can't be displayed or played** by the bar. Never edit `dist/`.

## manifest.json

```json
{
  "format_version": 1,
  "id": "net.example.weather",
  "name": "Weather",
  "version": "1.0.0",
  "api_version": "27.12.0",
  "description": "Current conditions",
  "author": "Your Name"
}
```

- `id`: ≤ 32 chars, `[A-Za-z0-9_.-]`, not starting with `.`; reverse-DNS style. Replace the template's `app.example`.
- `api_version`: minimum API needed; firmware refuses apps newer than itself. Keep it as low as works.
- `heap_size_kib`: 1–512, default 128. The **whole** heap. Raise only on "out of memory".
- `debug: true` hides the app unless developer mode is on.

## App icons

Without icons the APPS menu shows a generic "unknown app" icon — ship both:

| File | Size | Style |
|---|---|---|
| `src/appmeta/icon_front_8x8.png` | 8×8 | color, shaded pixel art |
| `src/appmeta/icon_back_11x11.png` | 11×11 | greyscale line art (back OLED) |

Save as 8-bit RGBA PNG with transparent background, matching the look of the built-in Clock/Weather icons. One recognizable silhouette; at 8×8 there's no room for detail or text. A tiny script (e.g. Python + Pillow, or a hand-written pixel grid) is fine for producing them.

## Lifecycle — the most important thing to get right

`main.ts` is a **script**, run once top to bottom. It must not export anything and ends with `main();`.

**`main()` is not looped.** The app stays alive only while something is pending:
- a `listen("input", …)` handler,
- a pending `setTimeout` / running `setInterval`,
- an unsettled `fetch`.

When the last of those goes away the process exits and the bar takes the screen back. Therefore:
- **Quitting = releasing every handle.** There is no `exit()`. Clear every timer, unbind the listener.
- **Don't unbind the last handler inside its own callback** — schedule it: `setTimeout(unbind, 0)`.
- `listen()` allows one handler; it throws if one is already attached.
- Keep `main()` synchronous; start async work with `void work().catch(report)`. Every promise gets a rejection handler.
- No dummy keep-alive timers, no busy-waits.
- Long-press **Back** is handled by firmware and force-quits the app — handle Back `short` as your quit.
- Use a `stopped` flag so in-flight async work doesn't reschedule timers after quit.

## Input

```ts
const unbind = listen("input", (event) => {
  if (event.key === "encoder") { selected += event.delta; return; }   // delta: 1 | -1
  if (event.action !== "short") return;                                // default tap action
  if (event.key === "ok") refreshNow();
  if (event.key === "back") quit();
});
```

- Buttons: `ok`, `start`, `back` with `press | release | short | long | repeat`. Encoder: `action` `clockwise | counterclockwise`, `delta` ±1.
- **Use `short` for taps, not `press`.** `press` fires on key-down and is followed by `short`, so handling `press` double-fires and reacts before the gesture is complete. `long`/`repeat` for holds; `press`/`release` only for games.

## Runtime APIs

Available: `console`, `fetch` (+ `Request`, `Response`, `Headers`, `URL`), `setTimeout/setInterval`, `localStorage`, `Date`, `JSON`, standard ECMAScript, global `Settings` (`load()`, `save()`).

Not available: `fs`, `path`, `process`, `document`, `window`, Node built-ins, DOM. Third-party npm packages must run without those.

- Talk to the bar via busy-lib: `export const device = new BusyBar({ addr: __BUSY_ADDR__ })` (`__BUSY_ADDR__` is `localhost` unless built with `--addr`).
- Only a whitelist of local endpoints is reachable (see http-api.md → "Endpoints a JS app may call"): draw/clear, brightness, audio play/volume, busy snapshot, own settings, read-only status.
- Remote `fetch` to the internet works when Wi-Fi is connected. Parse `response.text()` then `JSON.parse` in a try/catch — a captive portal or wrong URL returns HTML.
- `localStorage.setItem` rewrites the whole store to flash: small values, rare writes.

## Settings

`src/appmeta/settings.json` defines a settings screen editable on the device and in the bar's Web UI:

```json
{
  "format_version": 1,
  "version": 1,
  "fields": {
    "api_key": { "type": "string", "label": "API key", "default": "", "max_length": 128, "sensitive": true },
    "units":   { "type": "enum", "label": "Units", "default": "metric",
                 "options": [{ "value": "metric", "label": "Metric" }, { "value": "imperial", "label": "Imperial" }] },
    "display": { "type": "group", "label": "Display", "fields": {
      "refresh_min": { "type": "integer", "label": "Refresh (min)", "default": 10, "min": 5, "max": 60, "step": 5 },
      "accent":      { "type": "color", "label": "Accent", "default": "#00FF88" }
    } }
  }
}
```

- Types: `boolean`, `integer` (32-bit; `step` must divide `max-min`), `string` (≤255 bytes, `max_length` default 64, `sensitive` masks it), `enum` (≤32 options), `color` (`#RRGGBB[AA]`), `time` (`HH:MM[:SS]`), `geolocation` (`auto`/`fixed` with lat/lon), `group` (nest ≤ 4 levels).
- `color` and `geolocation` can't be edited on the device itself — only Web UI/API.
- Read values with the `Settings` global (`@shared/settings` `loadValues()` wrapper; it may return `{values}` or the values directly) and fall back to `device.AppsSettingsGet({ app_id })`. Groups arrive as **nested objects**; accept flat ids too.
- **Always default in code** — values can be missing, `null`, or wrong-typed. Validate (`typeof v === "number" && isFinite(v)`).
- Color settings may lack alpha: normalize `#RRGGBB` → `#RRGGBBFF` before drawing.
- Re-read settings on each poll (and on OK) so changes apply without restarting.
- Secrets typed by the user go in `sensitive` string settings, never in source.
- The app can **write** its settings back with `Settings.save(values)` (`saveValues()` in `@shared/settings`; it's a no-op when the global is missing). Save the whole document you loaded with the change applied: `saveValues({ ...values, code: "" })`. The HTTP API from inside an app is read-only for settings.

### Sign-in flows through settings

The bar has no keyboard, so third-party logins go through the settings screen (Web UI):

- Credentials (`email`, `password` with `sensitive: true`) in settings; on success store the **access token** in `localStorage` and use it until it expires, then sign in again with the password.
- **Email / 2FA codes:** add a `sensitive` string field like "Login code (if asked)". When the service demands a code, show `Check email` on screen and poll settings every ~15 s. When a new code appears, use it once, then clear the field with `saveValues({ ...values, code: "" })` so it's ready for the next one. Remember the last used code so a failed one isn't retried.
- **Rejected password:** remember it and don't retry until the user changes it (compare against the stored value) — repeated failures lock accounts. Show `Bad login` on screen.
- OK button = retry now / resend a code.
- Debug-log only the few response fields you rely on, never tokens or passwords.

## Resource discipline (the bar's CPU/RAM are shared with its web server)

- Poll remote data on human time scales (minutes). Align to when new data is expected (e.g. a source that updates every 5 min: poll ~20 s after the next update is due, not on a blind fixed interval).
- One draw request in flight; coalesce updates with a `redrawPending` flag.
- Bounded exponential backoff on failures (e.g. 30 s → 5 min). Auth failures: retry rarely (10 min) to avoid account lockouts, and show the problem on screen.
- Coarse timers: redraw "minutes ago" once a minute, not every second.
- Parse only fields you need; no unbounded arrays/caches; no logging in per-frame paths.
- Report errors with `console.error(\`${APP}: ...\`)`; one failed request must not kill timers or input handling.

## Before finishing an app

- [ ] `npm run typecheck` and `npm run build` pass (Node 24).
- [ ] Back `short` quits cleanly: every interval/timeout cleared, listener unbound via `setTimeout(unbind, 0)`.
- [ ] No code path leaks a timer after errors or after quit (`stopped` flag checked before rescheduling).
- [ ] Taps use `short`; holds use `long`/`repeat`.
- [ ] Diff-drawing with stable ids; removed ids cleared.
- [ ] Every font used with `textWidth`/`render` appears as a literal `font: "..."` in source.
- [ ] Both app icons present.
- [ ] Requests are infrequent with backoff; settings defaults in code.
- [ ] manifest has real `id`, semver `version`, minimal `api_version`.
- [ ] Tested on the device: `npm run app:install && npm run app:run`.
