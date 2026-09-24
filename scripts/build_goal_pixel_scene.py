#!/usr/bin/env python3
"""Draw original orthographic pixel art with Python's standard library.

The output contains only IHDR/IDAT/IEND PNG chunks, no private metadata.
It is an intentionally small first art study, not a photo-derived avatar.
"""

import struct
import zlib
from pathlib import Path


OUT = Path(__file__).resolve().parents[1] / "docs" / "scene-assets"


def rgba(color):
    if color is None:
        return (0, 0, 0, 0)
    if isinstance(color, tuple):
        return color
    color = color.removeprefix("#")
    return tuple(bytes.fromhex(color)) + (255,)


class Canvas:
    def __init__(self, width, height, background=None):
        self.w, self.h = width, height
        self.pixels = bytearray(bytes(rgba(background)) * (width * height))

    def dot(self, x, y, color):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            offset = 4 * (y * self.w + x)
            self.pixels[offset:offset + 4] = bytes(rgba(color))

    def rect(self, x0, y0, x1, y1, color):
        for y in range(max(0, int(y0)), min(self.h, int(y1))):
            for x in range(max(0, int(x0)), min(self.w, int(x1))):
                self.dot(x, y, color)

    def line(self, x0, y0, x1, y1, color, width=1):
        x0, y0, x1, y1 = map(int, (x0, y0, x1, y1))
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx - dy
        while True:
            self.rect(x0 - width // 2, y0 - width // 2,
                      x0 - width // 2 + width, y0 - width // 2 + width, color)
            if x0 == x1 and y0 == y1:
                break
            twice = 2 * err
            if twice > -dy:
                err -= dy
                x0 += sx
            if twice < dx:
                err += dx
                y0 += sy

    def ellipse(self, cx, cy, rx, ry, color):
        for y in range(int(cy - ry), int(cy + ry + 1)):
            for x in range(int(cx - rx), int(cx + rx + 1)):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1:
                    self.dot(x, y, color)

    def polygon(self, points, color):
        lower = max(0, min(y for _, y in points))
        upper = min(self.h, max(y for _, y in points) + 1)
        for y in range(lower, upper):
            crossings = []
            for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
                if y0 <= y + .5 < y1 or y1 <= y + .5 < y0:
                    crossings.append(x0 + (x1 - x0) * ((y + .5 - y0) / (y1 - y0)))
            crossings.sort()
            for x0, x1 in zip(crossings[::2], crossings[1::2]):
                self.rect(int(x0 + .5), y, int(x1 + .5), y + 1, color)

    def save(self, path):
        def chunk(kind, payload):
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
        scanlines = b"".join(b"\x00" + self.pixels[y * self.w * 4:(y + 1) * self.w * 4]
                             for y in range(self.h))
        data = (b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(scanlines, level=9))
                + chunk(b"IEND", b""))
        path.write_bytes(data)


P = {
    "outline": "#263c4d", "wall": "#78909a", "wall_dark": "#657f8a",
    "wall_light": "#8aa2a8", "trim": "#496476", "floor": "#ad7b5e",
    "floor_light": "#c08c65", "floor_dark": "#815f55", "wood": "#a5654b",
    "wood_light": "#dc9c69", "cream": "#efd8b0", "paper": "#f6e5c8",
    "gold": "#e7b873", "gold_light": "#ffdc92", "teal": "#4c7c7b",
    "teal_light": "#8ab7ac", "blue": "#52788e", "blue_light": "#9ac5ca",
    "leaf": "#577967", "leaf_light": "#83a27b", "rust": "#bd7755",
    "skin": "#dba579", "skin_shadow": "#b8785b", "hair": "#26384b",
}


def checkered(c, x0, y0, x1, y1, color, step=4, phase=0):
    for y in range(y0, y1, step):
        for x in range(x0 + ((y // step + phase) % 2) * step, x1, step * 2):
            c.rect(x, y, x + 1, y + 1, color)


def draw_room(evening=False):
    c = Canvas(320, 180, P["wall"])
    c.rect(0, 0, 320, 7, P["trim"])
    c.rect(0, 7, 320, 114, P["wall"] if not evening else "#506677")
    for y in (17, 46, 75, 103):
        c.rect(0, y, 320, y + 1, P["wall_light"] if not evening else "#5d7482")
    checkered(c, 4, 13, 318, 110, "#9aabb0" if not evening else "#69808b", 8)
    c.rect(0, 113, 320, 121, P["trim"])
    c.rect(0, 121, 320, 180, P["floor_dark"] if evening else P["floor"])
    for y in (137, 156, 176):
        c.rect(0, y, 320, y + 2, "#704e4d" if evening else P["floor_dark"])
    for row, y0, y1 in ((0, 122, 137), (1, 139, 156), (2, 158, 176)):
        for x in range(34 + row * 17, 320, 72):
            c.rect(x, y0, x + 1, y1, P["floor_dark"])
        c.rect(0, y0 + 3, 320, y0 + 4, P["floor_light"] if not evening else "#986c58")

    # Soft, rectangular window light remains pixel-native: no blur or filter.
    if not evening:
        c.polygon([(36, 117), (106, 117), (154, 160), (68, 160)], "#b69c75")
        checkered(c, 49, 122, 143, 160, "#d0ad7d", 3)

    # The window shows a flat 2D campus skyline and autumn leaves.
    c.rect(22, 16, 117, 88, P["outline"])
    c.rect(26, 19, 113, 84, P["cream"])
    c.rect(31, 23, 108, 80, "#b9d6d5" if not evening else "#344f72")
    c.rect(31, 62, 108, 80, "#e9c193" if not evening else "#a67270")
    if evening:
        for x, y in ((43, 32), (58, 25), (91, 35), (101, 27)):
            c.rect(x, y, x + 2, y + 2, "#f6d6a0")
    else:
        c.rect(84, 30, 95, 41, "#f8e6b1")
        c.rect(88, 28, 92, 43, "#f8e6b1")
        for x, y in ((40, 33), (48, 30), (67, 38)):
            c.rect(x, y, x + 10, y + 2, "#f2e6d4")
    for x, top, width in ((33, 61, 16), (49, 55, 9), (58, 59, 16), (74, 53, 12), (88, 60, 19)):
        c.rect(x, top, x + width, 79, "#486474" if not evening else "#304761")
        if evening:
            for yy in range(top + 4, 76, 7):
                for xx in range(x + 3, x + width - 1, 5):
                    if (xx + yy) % 3:
                        c.rect(xx, yy, xx + 2, yy + 2, "#eac293")
    c.rect(30, 66, 108, 80, "#637a68" if not evening else "#526877")
    c.rect(43, 55, 46, 79, "#755e56")
    c.rect(91, 51, 94, 79, "#755e56")
    for x, y, color in ((36, 49, P["rust"]), (45, 43, P["gold"]),
                        (54, 53, P["rust"]), (82, 44, P["rust"]), (94, 43, P["gold"]),
                        (100, 52, P["rust"])):
        c.rect(x, y, x + 11, y + 8, color)
        c.rect(x + 3, y - 4, x + 10, y + 2, color)
    c.rect(66, 23, 72, 84, P["cream"])
    c.rect(31, 51, 108, 56, P["cream"])
    c.rect(17, 83, 122, 90, P["outline"])
    c.rect(20, 83, 118, 87, P["cream"])
    c.rect(16, 18, 27, 91, P["teal"])
    c.rect(112, 18, 123, 91, P["teal"])
    c.rect(18, 21, 24, 80, P["teal_light"] if not evening else "#6f908f")
    c.rect(114, 21, 120, 80, P["teal_light"] if not evening else "#6f908f")

    # Bookshelf below the window: staggered spines, drawers, plant.
    c.rect(13, 93, 87, 151, P["outline"])
    c.rect(17, 96, 83, 145, P["wood"])
    c.rect(20, 119, 80, 122, P["wood_light"])
    for idx, (x, height, color) in enumerate(((22, 15, "#d18b64"), (28, 18, "#678b8b"),
                                              (34, 13, "#e3b66f"), (40, 20, "#557287"),
                                              (47, 16, "#c57a59"), (54, 18, "#84a48f"),
                                              (61, 14, "#e9c88e"), (68, 20, "#6f8298"))):
        c.rect(x, 119 - height, x + 4, 118, color)
        c.rect(x + 1, 119 - height + 3, x + 3, 119 - height + 4, P["cream"])
    c.rect(19, 128, 81, 144, "#b77755")
    c.rect(25, 132, 74, 134, P["wood_light"])
    c.rect(47, 135, 53, 138, P["gold"])
    c.rect(61, 85, 76, 96, P["rust"])
    c.rect(63, 87, 74, 94, "#d39d73")
    c.rect(67, 70, 70, 86, P["leaf"])
    for x, y in ((56, 67), (68, 61), (75, 72), (78, 63), (61, 76)):
        c.rect(x, y, x + 10, y + 6, P["leaf_light"])

    # Unlabelled cards encode a real pinboard, never fabricated achievements.
    c.rect(255, 21, 306, 90, P["outline"])
    c.rect(259, 25, 302, 86, "#bc9772")
    for x, y, w, h, color in ((264, 31, 17, 22, P["paper"]),
                              (282, 38, 15, 18, "#e5b985"),
                              (267, 61, 27, 17, "#b2cfbf")):
        c.rect(x, y, x + w, y + h, color)
        c.rect(x + 3, y + 6, x + w - 3, y + 7, "#a9a697")
        c.rect(x + 3, y + 11, x + w - 6, y + 12, "#a9a697")
        c.rect(x + w // 2, y + 1, x + w // 2 + 2, y + 3, P["rust"])

    # Side-on desk, monitor, keyboard and an open study notebook.
    c.rect(106, 107, 261, 116, P["outline"])
    c.rect(109, 103, 259, 111, P["wood_light"])
    c.rect(112, 116, 120, 150, P["wood"])
    c.rect(244, 116, 253, 151, P["wood"])
    c.rect(112, 143, 120, 149, P["floor_dark"])
    c.rect(244, 144, 253, 150, P["floor_dark"])
    c.rect(185, 67, 237, 101, P["outline"])
    c.rect(189, 71, 233, 97, "#2c596e" if not evening else "#224051")
    c.rect(193, 75, 215, 78, "#add3ce" if not evening else "#8db7bc")
    c.rect(193, 81, 225, 83, "#84a9ad" if not evening else "#6095a1")
    c.rect(193, 87, 219, 89, "#84a9ad" if not evening else "#6095a1")
    c.rect(208, 101, 215, 106, P["outline"])
    c.rect(196, 105, 226, 108, P["outline"])
    c.rect(181, 108, 238, 112, "#4b6773")
    for x in range(187, 233, 5):
        c.rect(x, 109, x + 3, 110, P["cream"])
    c.rect(131, 109, 167, 113, P["paper"])
    c.rect(148, 109, 150, 113, "#c2a98e")
    c.rect(135, 110, 146, 111, "#b7a991")
    c.rect(153, 110, 163, 111, "#b7a991")
    c.rect(121, 104, 125, 108, "#ecd3a5")
    c.line(123, 102, 131, 78, P["outline"], 2)
    c.line(131, 78, 146, 77, P["outline"], 2)
    c.rect(140, 71, 153, 80, P["gold"])
    c.rect(141, 79, 151, 81, P["gold_light"])
    if evening:
        c.polygon([(142, 81), (152, 81), (169, 102), (120, 102)], "#b99976")
        c.rect(117, 102, 174, 104, "#d2a574")
        checkered(c, 117, 92, 176, 104, "#ead092", 3)
        c.rect(141, 79, 151, 82, "#fff0b3")

    # Pixel rug and chair anchor the character instead of using fake depth.
    c.rect(91, 150, 233, 176, P["outline"])
    c.rect(95, 153, 229, 173, "#789999")
    c.rect(99, 156, 225, 170, "#9db9aa")
    for x in range(99, 225, 9):
        c.rect(x, 153, x + 4, 155, P["cream"])
        c.rect(x + 3, 171, x + 7, 173, P["cream"])
    c.rect(273, 104, 311, 147, P["outline"])
    c.rect(277, 107, 307, 138, P["rust"])
    c.rect(281, 111, 303, 134, "#d49471")
    c.rect(268, 128, 316, 146, P["outline"])
    c.rect(272, 129, 312, 142, "#bb7a60")
    c.rect(273, 145, 281, 162, P["outline"])
    c.rect(303, 145, 311, 162, P["outline"])
    c.rect(258, 147, 265, 170, "#536b65")
    c.rect(250, 150, 272, 154, P["leaf"])
    c.rect(244, 136, 255, 151, P["leaf_light"])
    c.rect(256, 128, 266, 145, P["leaf"])
    c.rect(248, 128, 254, 139, P["leaf_light"])
    c.rect(250, 168, 270, 174, P["rust"])

    # A dark edge gives the tiny room the same crisp frame at every size.
    c.rect(0, 0, 320, 3, P["outline"])
    c.rect(0, 177, 320, 180, P["outline"])
    c.rect(0, 0, 3, 180, P["outline"])
    c.rect(317, 0, 320, 180, P["outline"])
    return c


def draw_avatar(mode):
    c = Canvas(64, 96)
    outline, skin, shade, hair = P["outline"], P["skin"], P["skin_shadow"], P["hair"]
    # A transparent 64x96 sheet cell; pose is drawn at native pixel size.
    c.ellipse(32, 90, 24, 4, (24, 47, 58, 75))
    if mode == "rest":
        c.rect(17, 70, 50, 77, outline)
        c.rect(22, 76, 31, 86, "#435461")
        c.rect(39, 76, 49, 85, "#435461")
        c.rect(19, 84, 34, 88, P["cream"])
        c.rect(36, 83, 52, 87, P["cream"])
        c.rect(18, 55, 48, 74, outline)
        c.rect(21, 56, 46, 71, "#61918b")
    else:
        c.rect(21, 68, 31, 86, outline)
        c.rect(34, 68, 44, 86, outline)
        c.rect(22, 69, 30, 85, "#566b77")
        c.rect(35, 69, 43, 85, "#566b77")
        c.rect(18, 83, 32, 89, outline)
        c.rect(33, 83, 48, 89, outline)
        c.rect(20, 84, 31, 87, P["cream"])
        c.rect(35, 84, 46, 87, P["cream"])
        c.rect(19, 46, 46, 73, outline)
        c.rect(22, 48, 44, 69, P["teal"] if mode != "interview" else "#415978")
        c.rect(22, 48, 26, 69, "#6b9a91" if mode != "interview" else "#617a91")
        c.rect(42, 49, 44, 69, "#305e6b")
        if mode == "interview":
            c.rect(29, 49, 37, 62, P["cream"])
            c.polygon([(32, 49), (35, 49), (35, 58), (33, 63), (31, 58)], P["rust"])

    # Neck, head and asymmetric hair clusters. Solid pixels, no blur.
    c.rect(27, 43, 39, 50, shade)
    c.rect(21, 19, 44, 43, outline)
    c.rect(23, 21, 42, 41, skin)
    c.rect(25, 41, 41, 45, shade)
    c.rect(19, 20, 23, 37, hair)
    c.rect(22, 15, 42, 22, hair)
    c.rect(27, 12, 39, 16, hair)
    c.rect(41, 18, 45, 34, hair)
    c.rect(22, 18, 34, 24, hair)
    c.rect(27, 20, 38, 22, hair)
    c.rect(20, 31, 24, 37, shade)
    c.rect(42, 31, 46, 37, shade)
    c.rect(27, 31, 29, 34, outline)
    c.rect(37, 31, 39, 34, outline)
    c.rect(28, 40, 37, 41, shade)
    if mode == "rest":
        c.rect(27, 32, 30, 33, outline)
        c.rect(37, 32, 40, 33, outline)
    elif mode == "interview":
        c.rect(31, 38, 36, 39, "#945b58")
    else:
        c.rect(31, 38, 35, 39, "#945b58")
    c.rect(24, 37, 27, 38, "#c58b70")
    c.rect(39, 37, 42, 38, "#c58b70")

    if mode == "idle":
        c.rect(14, 51, 23, 70, outline)
        c.rect(16, 52, 21, 67, P["teal"])
        c.rect(16, 68, 22, 73, skin)
        c.rect(43, 51, 52, 70, outline)
        c.rect(45, 52, 50, 67, P["teal"])
        c.rect(44, 68, 50, 73, skin)
        c.rect(23, 53, 41, 54, P["teal_light"])
    elif mode == "desk":
        c.rect(15, 50, 23, 64, outline)
        c.rect(16, 52, 21, 62, P["teal"])
        c.rect(20, 59, 35, 65, skin)
        c.rect(42, 50, 50, 64, outline)
        c.rect(44, 52, 49, 62, P["teal"])
        c.rect(35, 60, 49, 66, skin)
        c.rect(26, 63, 35, 65, shade)
        c.rect(35, 64, 45, 66, shade)
    elif mode == "study":
        c.rect(14, 51, 22, 64, outline)
        c.rect(16, 53, 21, 61, P["teal"])
        c.rect(43, 51, 51, 64, outline)
        c.rect(45, 53, 50, 61, P["teal"])
        c.rect(18, 61, 27, 67, skin)
        c.rect(39, 61, 48, 67, skin)
        c.rect(18, 62, 33, 75, outline)
        c.rect(33, 62, 48, 75, outline)
        c.rect(20, 64, 32, 72, P["paper"])
        c.rect(34, 64, 46, 72, P["paper"])
        c.rect(32, 63, 34, 75, "#b39278")
        for x in (23, 36):
            c.rect(x, 67, x + 7, 68, "#acb7a5")
        c.rect(22, 23, 24, 39, P["gold"])
        c.rect(42, 23, 44, 39, P["gold"])
        c.rect(24, 17, 42, 20, P["gold"])
    elif mode == "interview":
        c.rect(15, 51, 23, 68, outline)
        c.rect(17, 53, 22, 64, "#415978")
        c.rect(19, 64, 29, 69, skin)
        c.rect(43, 51, 51, 68, outline)
        c.rect(44, 53, 49, 64, "#415978")
        c.rect(38, 64, 47, 69, skin)
        c.rect(19, 23, 22, 37, P["cream"])
        c.rect(44, 23, 47, 38, P["cream"])
        c.rect(21, 17, 45, 19, P["cream"])
        c.rect(45, 36, 52, 38, P["cream"])
        c.rect(51, 36, 54, 39, P["gold"])
    elif mode == "rest":
        c.rect(14, 52, 21, 67, outline)
        c.rect(16, 53, 20, 63, P["teal"])
        c.rect(20, 63, 31, 67, skin)
        c.rect(43, 52, 51, 67, outline)
        c.rect(45, 53, 49, 63, P["teal"])
        c.rect(41, 63, 51, 67, skin)
        c.rect(48, 58, 57, 67, P["cream"])
        c.rect(51, 59, 58, 64, "#eab77e")
        c.rect(56, 60, 61, 65, P["cream"])
        c.rect(57, 49, 58, 55, "#d0d4c7")
    return c


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    draw_room(False).save(OUT / "room-day.png")
    draw_room(True).save(OUT / "room-evening.png")
    for mode in ("idle", "desk", "study", "interview", "rest"):
        draw_avatar(mode).save(OUT / f"avatar-{mode}.png")
    for path in sorted(OUT.glob("*.png")):
        print(f"{path.relative_to(OUT.parent.parent)} {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
