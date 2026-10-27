// Minimal BUSY Bar on-device app: polls a remote JSON endpoint, diff-draws a 72x16 frame,
// backs off on failure, OK refreshes, Back quits cleanly.
// Assumes the @busy-app/create-app scaffold: shared/device.ts exports `device`,
// shared/settings.ts exports `loadValues`, types/env.d.ts declares `listen`.

import { device } from "@shared/device";
import { loadValues } from "@shared/settings";
import { render, row, type Node } from "@busy-app/busy-lib";
import manifest from "./appmeta/manifest.json";

const APP = manifest.id;
const POLL_MS = 5 * 60 * 1000;
const RETRY_MS = 30 * 1000;
const MAX_BACKOFF_MS = 5 * 60 * 1000;
const SUBTLE = "#FFFFFF99";

const report = (err: unknown) => console.error(`${APP}: ${err instanceof Error ? err.message : String(err)}`);

interface Data {
  value: string;
}

async function fetchData(url: string): Promise<Data> {
  const response = await fetch(url, { headers: { Accept: "application/json" } });
  // The device runtime may report the status as a string.
  const status = Number(response.status);
  if (status < 200 || status > 299) throw new Error(`HTTP ${status}`);
  let raw: unknown;
  try {
    raw = JSON.parse(await response.text());
  } catch {
    throw new Error("not JSON");
  }
  // Keep only what is drawn.
  const value = (raw as { value?: unknown }).value;
  return { value: String(value ?? "?").slice(0, 8) };
}

function main(): void {
  let data: Data | null = null;
  let message = "Loading...";
  let failures = 0;
  let polling = false;
  let stopped = false;
  let pollTimer: ReturnType<typeof setTimeout> | null = null;

  // Elements on screen, by id, as last sent.
  let shown = new Map<string, string>();
  let drawing = false;
  let redrawPending = false;

  function frame(): Node {
    if (data) {
      return row({ width: 72, height: 16, justify: "center", align: "center" }, [
        { type: "text", id: "value", text: data.value, font: "large", color: "#00FF88FF" },
      ]);
    }
    return row({ width: 72, height: 16, justify: "center", align: "center" }, [
      { type: "text", id: "message", text: message, font: "small", color: SUBTLE },
    ]);
  }

  async function draw(): Promise<void> {
    if (drawing) {
      redrawPending = true;
      return;
    }
    drawing = true;
    try {
      const elements = render(frame());
      const next = new Map<string, string>();
      const changed = [];
      for (const el of elements) {
        const json = JSON.stringify(el);
        next.set(el.id, json);
        if (shown.get(el.id) !== json) changed.push(el);
      }
      const removed = [...shown.keys()].filter((id) => !next.has(id));
      if (removed.length) await device.DisplayClear({ application_name: APP, element_ids: removed });
      if (changed.length) await device.DisplayDraw({ application_name: APP, priority: 50, elements: changed });
      shown = next;
    } catch (err) {
      // Screen state is unknown: resend everything next time.
      shown = new Map();
      throw err;
    } finally {
      drawing = false;
      if (redrawPending && !stopped) {
        redrawPending = false;
        void draw().catch(report);
      }
    }
  }

  function schedule(ms: number): void {
    if (stopped) return;
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = setTimeout(() => {
      pollTimer = null;
      void poll();
    }, ms);
  }

  async function poll(): Promise<void> {
    if (polling || stopped) return;
    polling = true;
    let next = POLL_MS;
    try {
      const values = (await loadValues()) ?? {};
      const url = typeof values.url === "string" ? values.url.trim() : "";
      if (!url) {
        data = null;
        message = "Set URL";
        next = RETRY_MS;
      } else {
        data = await fetchData(url);
        failures = 0;
      }
    } catch (err) {
      report(err);
      failures += 1;
      next = Math.min(RETRY_MS * Math.pow(2, failures - 1), MAX_BACKOFF_MS);
      // Keep the last value on screen; otherwise say why.
      if (!data) message = "No connection";
    } finally {
      polling = false;
    }
    if (stopped) return;
    void draw().catch(report);
    schedule(next);
  }

  void draw().catch(report);
  void poll();

  const unbind = listen("input", (event) => {
    if (stopped || event.key === "encoder" || event.action !== "short") return;
    if (event.key === "ok") {
      if (!polling) schedule(0);
      return;
    }
    if (event.key !== "back") return;

    stopped = true;
    if (pollTimer) clearTimeout(pollTimer);
    // The listener is the last handle: unbind after this callback returns.
    setTimeout(unbind, 0);
  });
}

main();
