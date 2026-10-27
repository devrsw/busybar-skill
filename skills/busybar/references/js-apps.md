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

- `id`: ≤ 32 chars, `[A-Za-z0-9_.-]`, not starting with `.`. Replace the template's `app.example`. Choose it once: **changing the id makes the bar treat it as a different app** — settings must be re-entered and the old install lingers until uninstalled. Reverse-DNS (`com.yourdomain.app`) avoids collisions; a generic `app.<name>` keeps personal names out of packages and release assets. Same goes for `author` (optional) if the app will be shared publicly.
- `api_version`: minimum API needed; firmware refuses apps newer than itself. Keep it as low as works.
- `heap_size_kib`: 1–512, default 128. The **whole** heap — it holds your script *and* every response you parse. Running out of heap doesn't just throw: on firmware 1.3.1 it **rebooted the whole bar**. Rough guide: a small app (≲ 20 KB built `main.js`, small responses) is fine at 128; a ~50 KB script parsing multi-KB JSON responses needed **256**. Check `dist/` script size after building, and raise the heap before shipping if you're near that range, rather than waiting for a crash.
- `debug: true` hides the app unless developer mode is on.

## App icons

Without icons the APPS menu shows a generic "unknown app" icon — ship both:

| File | Size | Style |
|---|---|---|
| `src/appmeta/icon_front_8x8.png` | 8×8 | color, shaded pixel art |
| `src/appmeta/icon_back_11x11.png` | 11×11 | greyscale line art (back OLED) |

Save as 8-bit RGBA PNG with transparent background, matching the look of the built-in Clock/Weather icons. One recognizable silhouette; at 8×8 there's no room for detail or text. Generate them from pixel grids with [templates/icons.py](../templates/icons.py) (dependency-free Python; copy to `scripts/icons.py`, edit the grids, run `python3 scripts/icons.py` from the app root) so they stay reproducible and reviewable.

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
- A useful control scheme: **START** = primary toggle (start/pause), **hold START** (`long`) = the stronger variant (stop / start new), **OK** = refresh now, **knob** = browse a list (`list()` from busy-lib) with OK/START to choose and BACK to cancel, **BACK** = quit (or cancel when a picker is open). Close a picker automatically after ~15 s without input.
- Make button actions **feel instant**: update the screen immediately, then do the network call (see "Optimistic actions" below).

## Runtime APIs

Available: `console`, `fetch` (+ `Request`, `Response`, `Headers`, `URL`), `setTimeout/setInterval`, `localStorage`, `Date`, `JSON`, standard ECMAScript, global `Settings` (`load()`, `save()`).

Not available: `fs`, `path`, `process`, `document`, `window`, Node built-ins, DOM. Third-party npm packages must run without those.

- Talk to the bar via busy-lib: `export const device = new BusyBar({ addr: __BUSY_ADDR__ })` (`__BUSY_ADDR__` is `localhost` unless built with `--addr`).
- Only a whitelist of local endpoints is reachable (see http-api.md → "Endpoints a JS app may call"): draw/clear, brightness, audio play/volume, busy snapshot, own settings, read-only status.
- Remote `fetch` to the internet works when Wi-Fi is connected. Parse `response.text()` then `JSON.parse` in a try/catch — a captive portal or wrong URL returns HTML.
- `localStorage.setItem` rewrites the whole store to flash: small values, rare writes.
- **HTTP only.** There's no MQTT, raw TCP or WebSocket client in the app runtime. If a service publishes live data only over MQTT/WebSocket, poll its REST API (and estimate between polls, e.g. progress from start time + expected duration, capped at 99 % until the service reports completion).
- **Local time:** don't trust `Date`'s local-time methods for the bar's timezone. Read the bar's offset from `device.TimeGet()` (its `timestamp` ends in `±HH:MM`), keep `utcOffsetS`, and compute local midnight etc. as `Math.floor((nowS + off) / 86400) * 86400 - off`. Refresh it occasionally.

### Runtime quirks (JerryScript `fetch` and errors)

Workarounds that are needed on firmware 1.3.x:

- **`response.status` may be a string.** Always `const status = Number(response.status)` before comparing.
- **Don't pass `body: undefined`.** The device `fetch` sends it as the literal text `"undefined"`. Build `init` and add the `body` key only when there is a body.
- **`instanceof` on `Error` subclasses is unreliable.** Give your errors a `kind` field (`"auth" | "network" | "quota" | "http"`) and branch on that (duck typing), not on `err instanceof AuthError`.
- **Error pages:** summarize non-JSON error bodies (HTML `<title>`, or JSON `error_description`) into a few words for logs/back screen; never log the whole body.

```ts
async function request(method: string, url: string, body?: unknown): Promise<unknown> {
  const init: RequestInit = { method, headers: { Accept: "application/json", Authorization: auth } };
  if (body !== undefined) {                       // no body key at all otherwise
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  let response: Response;
  try { response = await fetch(url, init); }
  catch (err) { throw Object.assign(new Error(String(err)), { kind: "network" }); }
  const status = Number(response.status);        // may arrive as a string
  const text = await response.text();
  if (status === 401 || status === 403) throw Object.assign(new Error(`HTTP ${status}`), { kind: "auth" });
  if (status === 429 || status === 402) {
    const wait = Number(response.headers.get("Retry-After"));
    throw Object.assign(new Error(`HTTP ${status}`), { kind: "quota", retryAfterS: isFinite(wait) ? wait : 0 });
  }
  if (status < 200 || status > 299) throw Object.assign(new Error(`HTTP ${status}`), { kind: status >= 500 ? "network" : "http" });
  try { return text ? JSON.parse(text) : null; }
  catch { throw Object.assign(new Error("not JSON"), { kind: "network" }); }
}
```

### Primary and fallback data sources

When two services can supply the same data, don't make the user pick one in settings. Use the primary when it's configured, and fall back to the secondary when the primary isn't set up, errors, rejects the login (then leave the primary alone for a while, e.g. 10 min), returns no data, or returns stale data. Optional extras (fields only one service has) come from whichever service is configured.

### Rate-limited APIs

Many services cap calls per hour (some free tiers ~30/h). Budget them: default refresh every few minutes (~12/h), one request per refresh, cache rarely-changing lookups (names, colors) in `localStorage`, and leave headroom for button presses. On 429/quota responses honor `Retry-After` (or the service's reset header), show `Rate limited`, and wait — don't back off blindly from 30 s.

### Optimistic actions with a persistent sync queue

For apps that *control* a remote service (start/stop a timer, toggle something):

1. On the press, change local state and redraw **immediately**, stamped with the press time.
2. Append the operation (with that timestamp) to a queue persisted in `localStorage`, then sync in the background, so the service records the true time even if the sync happens later.
3. Retry the queue with backoff; keep it across app restarts.
4. While the queue isn't empty, **don't let polling overwrite local state**. If the service refuses an op, drop it and poll once the queue is empty to resync.
5. Show a small corner dot while ops are pending (amber) or failing (red); explain on the back screen.

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
