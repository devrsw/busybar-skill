#!/usr/bin/env python3
"""
Renders BUSY Bar front-screen captures as LED-style PNGs (for READMEs, docs, bug reports).

    python3 tools/screenshot.py still OUT.png [BAR]          one capture from the bar
    python3 tools/screenshot.py record OUT.png SECONDS [BAR] an animated PNG

BAR is the bar's address, 10.0.4.20 (USB) by default. Captures come from
GET /api/screen?display=0: base64 of 72x16 pixels, 3 bytes each (BGR).
No dependencies.
"""

import base64
import struct
import sys
import time
import urllib.request
import zlib

W, H = 72, 16
CELL = 10  # pixels per LED
DOT = 8  # lit diameter
BORDER = 12
BACKGROUND = (14, 14, 16)
UNLIT = (32, 32, 36)


def capture(bar):
    raw = urllib.request.urlopen(f"http://{bar}/api/screen?display=0", timeout=5).read()
    data = base64.b64decode(raw)
    assert len(data) == W * H * 3, f"unexpected capture size {len(data)}"
    return data


def led_image(data):
    """RGB rows of the enlarged screen."""
    width, height = W * CELL + 2 * BORDER, H * CELL + 2 * BORDER
    rows = [bytearray(bytes(BACKGROUND) * width) for _ in range(height)]
    r2 = (DOT / 2) ** 2
    for y in range(H):
        for x in range(W):
            b, g, r = data[(y * W + x) * 3:(y * W + x) * 3 + 3]
            lit = max(r, g, b) > 8
            color = (r, g, b) if lit else UNLIT
            ox, oy = BORDER + x * CELL, BORDER + y * CELL
            for py in range(CELL):
                for px in range(CELL):
                    # A round dot, softened at the edge.
                    d2 = (px + 0.5 - CELL / 2) ** 2 + (py + 0.5 - CELL / 2) ** 2
                    if d2 > r2 + DOT:
                        continue
                    a = 1.0 if d2 <= r2 - DOT else (r2 + DOT - d2) / (2 * DOT)
                    i = (ox + px) * 3
                    row = rows[oy + py]
                    for c in range(3):
                        row[i + c] = round(BACKGROUND[c] + (color[c] - BACKGROUND[c]) * a)
    return width, height, rows


def chunk(kind, body):
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def idat(rows):
    return zlib.compress(b"".join(b"\x00" + bytes(r) for r in rows), 9)


def write_png(path, frames):
    """frames: list of (rows, delay_ms). One frame writes a PNG, more an animated PNG."""
    width, height = len(frames[0][0][0]) // 3, len(frames[0][0])
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    if len(frames) == 1:
        out += chunk(b"IDAT", idat(frames[0][0]))
    else:
        out += chunk(b"acTL", struct.pack(">II", len(frames), 0))
        seq = 0
        for i, (rows, delay) in enumerate(frames):
            out += chunk(b"fcTL", struct.pack(">IIIIIHHBB", seq, width, height, 0, 0, delay, 1000, 0, 0))
            seq += 1
            data = idat(rows)
            if i == 0:
                out += chunk(b"IDAT", data)
            else:
                out += chunk(b"fdAT", struct.pack(">I", seq) + data)
                seq += 1
    out += chunk(b"IEND", b"")
    open(path, "wb").write(out)


def record(bar, seconds):
    """Distinct captures over `seconds`, each with how long it stayed on screen."""
    shots, start = [], time.time()
    while time.time() - start < seconds:
        t, data = time.time(), capture(bar)
        if not shots or data != shots[-1][1]:
            shots.append((t, data))
    end = time.time()
    return [(data, round(((shots[i + 1][0] if i + 1 < len(shots) else end) - t) * 1000)) for i, (t, data) in enumerate(shots)]


def main():
    mode, out = sys.argv[1], sys.argv[2]
    if mode == "still":
        bar = sys.argv[3] if len(sys.argv) > 3 else "10.0.4.20"
        write_png(out, [(led_image(capture(bar))[2], 0)])
    elif mode == "record":
        seconds = float(sys.argv[3])
        bar = sys.argv[4] if len(sys.argv) > 4 else "10.0.4.20"
        write_png(out, [(led_image(data)[2], max(20, delay)) for data, delay in record(bar, seconds)])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
