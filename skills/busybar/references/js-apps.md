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

## Layout

```
my-app/
├── src/
│   ├── main.ts                 entry point (fixed name; becomes scripts/main.js)
│   ├── appmeta/
│   │   ├── manifest.json       required
│   │   ├── settings.json       optional settings screen
│   │   ├── icon_front_8x8.png  optional, 8×8 color
│   │   └── icon_back_11x11.png optional, 11×11 greyscale
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
- [ ] Requests are infrequent with backoff; settings defaults in code.
- [ ] manifest has real `id`, semver `version`, minimal `api_version`.
- [ ] Tested on the device: `npm run app:install && npm run app:run`.
