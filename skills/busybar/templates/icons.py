"""Writes BUSY Bar app icons (8-bit RGBA PNG) from pixel grids, with no dependencies.

Copy into an app as scripts/icons.py, edit the grids and palettes, then run from the app root:
    python3 scripts/icons.py
"""
import struct
import zlib


def png(path, grid, palette):
    rows = b"".join(b"\0" + b"".join(bytes(palette[c]) for c in row) for row in grid)

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    h, w = len(grid), len(grid[0])
    assert all(len(row) == w for row in grid), f"{path}: rows differ in width"
    with open(path, "wb") as f:
        f.write(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))  # 8-bit RGBA
            + chunk(b"IDAT", zlib.compress(rows))
            + chunk(b"IEND", b"")
        )


# Front: 8x8, color, shaded. Example: a green play button.
FRONT = [
    "........",
    ".GL.....",
    ".GGL....",
    ".GGGL...",
    ".GGGD...",
    ".GGD....",
    ".GD.....",
    "........",
]
png("src/appmeta/icon_front_8x8.png", FRONT, {
    ".": (0, 0, 0, 0),
    "G": (0, 200, 90, 255),
    "L": (120, 255, 170, 255),
    "D": (0, 120, 60, 255),
})

# Back: 11x11, greyscale line art.
BACK = [
    "...........",
    ".#.........",
    ".##........",
    ".#.#.......",
    ".#..#......",
    ".#...#.....",
    ".#..#......",
    ".#.#.......",
    ".##........",
    ".#.........",
    "...........",
]
png("src/appmeta/icon_back_11x11.png", BACK, {
    ".": (0, 0, 0, 0),
    "#": (255, 255, 255, 255),
})
