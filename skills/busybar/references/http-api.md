# BUSY Bar HTTP API

Source of truth: the device's own docs at `http://<bar>/docs`, the public reference at <https://api.busy.app/busybar/docs>, and the OpenAPI-generated types in `@busy-app/busy-lib` (`node_modules/@busy-app/busy-lib/dist/index.d.ts`, search for `components['schemas']` and `paths`). Field names below come from busy-lib 0.21 (API ~27.x, firmware 1.3.x).

## Base URLs and auth

| Connection | Base URL | Auth |
|---|---|---|
| USB (USB-Ethernet) | `http://10.0.4.20/api` | none |
| LAN / Wi-Fi | `http://<bar-ip>/api` | `X-API-Token: <password>` if HTTP access password is enabled (Settings → HTTP Access in the web UI) |
| BUSY cloud proxy | `https://api.busy.app/busybar` | `Authorization: Bearer <token>` from <https://cloud.busy.app/api-tokens> |
| From a JS app on the bar | `http://localhost/api` | none |

- Paths are `/api/...` on the device and `/busybar/...` on the cloud proxy. The public docs show `/busybar/` paths — on a local device swap to `/api/`.
- The header is `X-API-Token` (not `X-Token`). Missing/wrong → 401/403.
- The apps API (`/apps/*`) does **not** work through the cloud proxy.

## Clients

- **TypeScript**: `@busy-app/busy-lib` → `new BusyBar({ addr, HTTPAccessPassword?, token?, timeout? })`. Default `addr` is `10.0.4.20`; default timeout 3000 ms. Methods are PascalCase per namespace: `DisplayDraw`, `DisplayClear`, `DisplayBrightnessSet`, `AudioPlay`, `AssetsUpload`, `AppsList`, `AppsSettingsGet`, `InputSend`, `SystemStatusGet`, `SystemVersionGet`, `ScreenFrameGet`, … Errors carry `status`, `statusText`, `body`; timeouts are `DOMException` `TimeoutError`.
- **Python**: `busylib` (`pip install busylib`), `BusyBar(ip)`.
- **Raw**: plain `fetch`/`curl`/`aiohttp` with JSON bodies. Many "set" endpoints take **query parameters**, not JSON bodies (see table).

## Endpoints

| Path | Methods | Notes |
|---|---|---|
| `/version` | GET | `{"api_semver":"27.12.0"}` — check this first |
| `/status`, `/status/device`, `/status/firmware`, `/status/system`, `/status/power` | GET | device/firmware/battery info |
| `/status/ws` | WS | live state stream (input events, frames, power, wifi…). busy-lib's `LocalStateStream` decodes the protobuf stream (browser only). From non-browser clients you can connect, send `{"enable": true}`, and read JSON messages (e.g. button events). |
| `/display/draw` | POST, DELETE | draw elements / clear (see below) |
| `/display/brightness` | GET, POST | POST `?value=auto` or `?value=0..100` |
| `/screen` | GET | `?display=0` (front) / `1` (back): current frame. Default pixel format is BGR; busy-lib `ScreenFrameGet(..., {dataType:'binary', format:'rgba'})` converts |
| `/audio/play` | POST, DELETE | POST JSON `{application_name, path}` or `{application_name, stock_path}`; DELETE stops |
| `/audio/volume` | GET, POST | POST `?volume=0..100` (5 % steps; optional `&silent=1`) |
| `/assets/upload` | POST, DELETE | POST `?application_name=X&file=name.png`, raw body `application/octet-stream`. DELETE `?application_name=X` removes the app's assets |
| `/input` | POST | `?key=up|down|ok|back|start|busy|custom|off|apps|settings` — injects a key press |
| `/busy/snapshot` | GET, PUT | BUSY timer state + `busy_bar_settings` (theme etc.). PUT the whole document back after editing |
| `/busy/profiles/{slot}` | GET, PUT | timer profiles |
| `/name` | GET, POST | device name; POST `{"name": "..."}` |
| `/time`, `/time/timezone`, `/time/tzlist`, `/time/timestamp` | GET/POST | clock |
| `/apps/list` | GET | `{apps:[{id,name,version,author,description,icon_path,is_debug}]}` |
| `/apps/stage` | POST | raw `.tgz`/`.tar` body → `{install_key, staged, installed?}` |
| `/apps/install` | POST | `?install_key=<from stage>` |
| `/apps/launch` | POST | `?app_id=...` |
| `/apps/quit` | POST | quit running app. The API doesn't report which app is running |
| `/apps` | DELETE | `?app_id=...` uninstall (keeps settings) |
| `/apps/settings` | GET, PUT, DELETE | `?app_id=...`; document is `{version, values}` with groups as nested objects. DELETE resets to defaults |
| `/storage/{read,write,list,remove,mkdir,rename,status}` | various | raw file access |
| `/update/*`, `/wifi/*`, `/ble/*`, `/account/*`, `/access*`, `/smart_home/*` | various | device management — don't touch unless asked |

## `POST /display/draw`

```jsonc
{
  "application_name": "my_app",          // namespace; your elements live under it
  "priority": 50,                        // 1..100, default 50
  "led_notification_color": "#FF0000FF", // optional: blink status LED once
  "elements": [ /* see drawing.md */ ]
}
```

**Priority semantics** (from the schema): a draw is accepted when its priority is `>=` the running system app's priority. Stub/power-off = 0, built-in apps = 10, an active BUSY/CUSTOM work session = 90. Equal priority from a different `application_name` replaces what's on screen. The API accepts only 1–100.

Response: `{"result":"OK"}`. Errors: `{"error": "...", "error_code": "..."}` — always log the body.

## `DELETE /display/draw`

- `?application_name=my_app` — clears everything that app drew.
- Optional JSON body `{"application_name": "my_app", "element_ids": ["a","b"]}` — remove specific elements. busy-lib: `DisplayClear({ application_name, element_ids })`.
- Omitting `application_name` clears all elements regardless of owner — avoid.

## Endpoints a JS app may call

A running app can only reach these on `http://localhost/api` (methods in parentheses):

`display/draw` (POST, DELETE), `display/brightness` (GET, POST), `audio/play` (POST, DELETE), `audio/volume` (GET, POST), `busy` (GET, PUT), `apps/settings` (GET, own id only), and GET-only `name`, `time`, `wifi/status`, `version`, `access`, `transport`, `status`, `status/device`, `status/firmware`, `status/system`, `status/power`.

Not `assets/upload`, `input`, `storage`, or other apps. Package assets with the app instead.

## Good external-client hygiene

- Normalize the base URL: if the user gives just `http://host`, append `/api` (or `/busybar` for `api.busy.app`).
- Set a timeout (3–5 s); the device can be asleep or rebooting (503).
- Draw on change, not on a fixed fast loop. 30 s+ polling for status is plenty.
- Use your own stable `application_name` so `DELETE ?application_name=` cleans up only your content.
