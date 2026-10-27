#!/usr/bin/env python3
"""
Writes BUSY Bar .anim files ("bicycle1" format), with no dependencies.

The format is defined in the firmware repo (busy-app/busybar-firmware):
lib/anim_file/anim_file_format.h, with the official PNG-sequence converter in
scripts/seq2anim.py. This writer uses the simplest valid encoding: BGRA8888
pixels stored raw, the first frame of each section whole, later frames as only
the pixels that changed (a per-pixel bitmap mask). The firmware plays it
without the app redrawing, at the file's fps.

Copy into an app as tools/make_anim.py, replace example() with your own frames,
and run from the app root:

    python3 tools/make_anim.py

Put the output in src/animations/ and draw it with
    {"type": "animation", "id": "...", "path": "animations/<name>.anim", "loop": true}
Colors are baked into the file: make one file per color you need.
"""

import struct
from pathlib import Path

MAGIC = b"bicycle1"
COLOR_BGRA8888 = 2  # "argb8888" in seq2anim.py; bytes per pixel are B, G, R, A
HEADER = "<8s BBBB HHBB II II"  # magic, flags, width, height, color mode, max mask len, max pixels len, fps, pad,
                                # sections chunk len, frames chunk len, section count, frame count


def rgba_to_bgra(pixels):
    """RGBA bytes → BGRA bytes. Fully transparent pixels become all zero, so they never count as changed."""
    out = bytearray()
    for i in range(0, len(pixels), 4):
        r, g, b, a = pixels[i:i + 4]
        out.extend((b, g, r, a) if a else (0, 0, 0, 0))
    return bytes(out)


def frame_bytes(pixels, previous):
    """One frame: everything when `previous` is None (a keyframe), else only the pixels that changed."""
    if previous is None:
        mask_enc, mask_bits, mask_data, changed = 1, 0, b"", pixels  # FullyWhite: every pixel present
    else:
        flags = [pixels[i:i + 4] != previous[i:i + 4] for i in range(0, len(pixels), 4)]
        changed = b"".join(pixels[i * 4:i * 4 + 4] for i, f in enumerate(flags) if f)
        if not any(flags):
            mask_enc, mask_bits, mask_data = 0, 0, b""  # FullyBlack: same as the previous frame
        elif all(flags):
            mask_enc, mask_bits, mask_data = 1, 0, b""
        else:
            bitmap = bytearray()
            for i in range(0, len(flags), 8):
                byte = 0
                for j, f in enumerate(flags[i:i + 8]):
                    byte |= (128 >> j) if f else 0
                bitmap.append(byte)
            mask_enc, mask_bits, mask_data = 4, len(flags), bytes(bitmap)  # Bitmap, MSB first
    pixel_enc = 0  # Raw
    header = struct.pack("<BHH", pixel_enc | (mask_enc << 4), mask_bits, len(changed))
    return header + mask_data + changed, mask_bits, len(changed)


def write_anim(path, frames, width, height, fps, sections=None):
    """Writes an .anim.

    frames: list of BGRA8888 byte strings, width*height*4 each (use rgba_to_bgra()).
    sections: list of (name, first_frame, last_frame); defaults to one "default" section over all frames.
              Play one with {"section": name}; "default" plays the whole file.
    """
    assert 0 < width <= 255 and 0 < height <= 255, "width/height are stored in one byte each"
    assert all(len(f) == width * height * 4 for f in frames), "every frame must be width*height*4 bytes"
    sections = sections or [("default", 0, len(frames) - 1)]
    starts = {start for _, start, _ in sections}

    encoded, offsets, max_mask, max_pixels, previous = [], [], 0, 0, None
    for i, pixels in enumerate(frames):
        # A section can be played on its own, so its first frame must be whole.
        data, mask_bits, pixel_len = frame_bytes(pixels, None if i in starts else previous)
        encoded.append(data)
        max_mask, max_pixels, previous = max(max_mask, mask_bits), max(max_pixels, pixel_len), pixels

    section_chunk_len = sum(12 + len(name.encode()) + 1 for name, _, _ in sections)
    offset = struct.calcsize(HEADER) + section_chunk_len
    for data in encoded:
        offsets.append(offset)
        offset += len(data)

    section_chunk = b"".join(
        struct.pack("<III", start, end, offsets[start]) + name.encode() + b"\0" for name, start, end in sections
    )
    frames_chunk = b"".join(encoded)
    header = struct.pack(
        HEADER, MAGIC,
        0, width, height, COLOR_BGRA8888,
        max_mask, max_pixels, fps, 0,
        len(section_chunk), len(frames_chunk), len(sections), len(frames),
    )
    Path(path).write_bytes(header + section_chunk + frames_chunk)


def example():
    """A 9x9 dot that pulses in and out, 20 fps, 1.5 s per loop."""
    import math

    size, fps, count = 9, 20, 30
    frames = []
    for f in range(count):
        level = 0.5 - 0.5 * math.cos(2 * math.pi * f / count)  # 0 → 1 → 0
        radius = 1.5 + 2.5 * level
        px = bytearray()
        for y in range(size):
            for x in range(size):
                d = math.hypot(x - size // 2, y - size // 2)
                a = max(0.0, min(1.0, radius - d + 0.5))  # soft edge
                px.extend((0, 255, 120, round(a * 255)))
        frames.append(rgba_to_bgra(bytes(px)))
    out = Path("src/animations")
    out.mkdir(parents=True, exist_ok=True)
    write_anim(out / "pulse.anim", frames, size, size, fps)
    print(f"wrote {out / 'pulse.anim'}")


if __name__ == "__main__":
    example()
