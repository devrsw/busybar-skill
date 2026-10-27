# BUSY Bar skill for Claude

A [Claude skill](https://docs.claude.com/en/docs/claude-code/skills) for building software for the [BUSY Bar](https://busy.app/): the HTTP API, drawing on the 72×16 front display (and the 160×80 back display), animations, and on-device JavaScript apps.

## What's inside

| File | |
|---|---|
| `skills/busybar/SKILL.md` | Overview, architecture choice (on-device app vs HTTP client), non-negotiable rules, smoke test |
| `references/http-api.md` | Base URLs and auth, endpoint table, draw/clear payloads, priorities, endpoints a JS app may call |
| `references/drawing.md` | Element types and required fields, measured font metrics, busy-lib layout engine, XPM bitmaps, diff-drawing |
| `references/animation.md` | Firmware-side motion, `.anim` assets and sections, timer-driven frames, transitions |
| `references/js-apps.md` | App lifecycle, input, manifest, settings schema, busy-cli toolchain, resource limits, release checklist |
| `references/pitfalls.md` | Common mistakes and what actually fixes them |
| `templates/main.ts` | Minimal on-device app: poll, diff-draw, back off, quit cleanly |

## Install

### Claude Code

```
/plugin marketplace add devrsw/busybar-skill
/plugin install busybar@busybar-skill
```

Or copy/symlink `skills/busybar` into `~/.claude/skills/busybar`.

### Claude.ai / Claude desktop

Zip the `skills/busybar` folder and upload it under Settings → Capabilities → Skills.

## Sources

Built from the OpenAPI-generated types in [`@busy-app/busy-lib`](https://github.com/busy-app/busylib-ts), the [firmware JavaScript app docs](https://github.com/busy-app/busybar-firmware/blob/dev/documentation/JavaScript%20Applications.dox.md), [busy-tools](https://github.com/busy-app/busy-tools), and hands-on experience with the device. Always confirm against your device's `GET /api/version` and `http://<bar>/docs`.

## License

MIT
