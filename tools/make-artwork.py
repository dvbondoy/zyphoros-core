#!/usr/bin/env python3
"""Generate the template's placeholder artwork (no image tools needed).

Writes, for DISTRO_ID from distro.conf:
  packages/DISTRO_ID-artwork/usr/share/desktop-base/DISTRO_ID-theme/
      wallpaper/, lockscreen/, login/  SVG backgrounds (desktop, lock screen, login screen)
      grub/grub-16x9.png, grub-4x3.png  GRUB menu backgrounds of installed systems
  packages/DISTRO_ID-artwork/usr/share/icons/hicolor/scalable/apps/DISTRO_ID-logo.svg
  packages/DISTRO_ID-installer/usr/share/calamares/branding/DISTRO_ID/
      logo.png, welcome.png, slide.png  the installer's logo, welcome page and slideshow

Replace these files with your own artwork whenever you like (keep the names
and sizes) and delete this script, or change COLORS below and run it again.
Either way, add a changelog entry to the packages (dch -i -D trixie "...").
"""

import math
import os
import shlex
import struct
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Background gradient from top to bottom, and the accent of shapes and logo.
COLORS = {"top": (0x0F, 0x20, 0x27), "middle": (0x20, 0x3A, 0x43), "bottom": (0x2C, 0x53, 0x64),
          "accent": (0x4A, 0x90, 0xD9)}


def distro_id():
    for line in open(os.path.join(ROOT, "distro.conf")):
        if line.startswith("DISTRO_ID="):
            return shlex.split(line.partition("=")[2], comments=True)[0]
    raise SystemExit("distro.conf sets no DISTRO_ID")


def hex_color(rgb):
    return "#%02x%02x%02x" % rgb


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if isinstance(data, bytes) else "w"
    with open(path, mode) as f:
        f.write(data)
    print("wrote", os.path.relpath(path, ROOT))


def png(width, height, pixel):
    """PNG bytes; pixel(x, y) returns (r, g, b, a) with 0-255 values."""
    rows = bytearray()
    for y in range(height):
        rows.append(0)  # filter: none
        for x in range(width):
            rows.extend(pixel(x, y))

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)  # 8-bit RGBA
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(rows), 9)) + chunk(b"IEND", b""))


def gradient(t):
    """Color at t (0 top, 1 bottom) of the three-stop background gradient."""
    a, b, t = ((COLORS["top"], COLORS["middle"], t * 2) if t < 0.5
               else (COLORS["middle"], COLORS["bottom"], t * 2 - 1))
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def background_svg(width, height):
    """Gradient with two soft accent waves."""
    top, middle, bottom, accent = (hex_color(COLORS[k]) for k in ("top", "middle", "bottom", "accent"))
    w, h = width, height
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
  <defs>
    <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{top}"/>
      <stop offset="0.5" stop-color="{middle}"/>
      <stop offset="1" stop-color="{bottom}"/>
    </linearGradient>
  </defs>
  <rect width="{w}" height="{h}" fill="url(#sky)"/>
  <path d="M0 {h * 0.72:.0f} C {w * 0.25:.0f} {h * 0.58:.0f}, {w * 0.55:.0f} {h * 0.86:.0f}, {w} {h * 0.66:.0f} L {w} {h} L 0 {h} Z"
        fill="{accent}" fill-opacity="0.18"/>
  <path d="M0 {h * 0.82:.0f} C {w * 0.3:.0f} {h * 0.72:.0f}, {w * 0.6:.0f} {h * 0.95:.0f}, {w} {h * 0.78:.0f} L {w} {h} L 0 {h} Z"
        fill="{accent}" fill-opacity="0.22"/>
</svg>
"""


def logo_svg():
    accent, bottom = hex_color(COLORS["accent"]), hex_color(COLORS["bottom"])
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
  <defs>
    <linearGradient id="disc" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{accent}"/>
      <stop offset="1" stop-color="{bottom}"/>
    </linearGradient>
  </defs>
  <circle cx="64" cy="64" r="60" fill="url(#disc)"/>
  <circle cx="64" cy="64" r="34" fill="none" stroke="#ffffff" stroke-width="10"/>
  <circle cx="64" cy="64" r="10" fill="#ffffff"/>
</svg>
"""


def logo_pixel(size):
    """pixel(x, y) of the logo above at SIZE pixels, drawn with 4x4 supersampling."""
    accent, bottom = COLORS["accent"], COLORS["bottom"]
    scale = size / 128
    samples = [(i + 0.5) / 4 for i in range(4)]

    def pixel(x, y):
        r = g = b = a = 0.0
        for sy in samples:
            for sx in samples:
                px, py = (x + sx) / scale - 64, (y + sy) / scale - 64
                d = math.hypot(px, py)
                if d > 60:
                    continue
                if d <= 10 or 29 <= d <= 39:
                    color = (255, 255, 255)
                else:
                    t = (py + 60) / 120
                    color = tuple(accent[i] + (bottom[i] - accent[i]) * t for i in range(3))
                r, g, b, a = r + color[0], g + color[1], b + color[2], a + 1
        if not a:
            return (0, 0, 0, 0)
        return (round(r / a), round(g / a), round(b / a), round(255 * a / 16))

    return pixel


def logo_png(size):
    return png(size, size, logo_pixel(size))


def slide_png(width, height, logo_size):
    """The installer's slideshow: the background gradient with the logo in the middle."""
    logo = logo_pixel(logo_size)
    left, top = (width - logo_size) // 2, (height - logo_size) // 2

    def pixel(x, y):
        background = gradient(y / (height - 1))
        if not (left <= x < left + logo_size and top <= y < top + logo_size):
            return background + (255,)
        r, g, b, a = logo(x - left, y - top)
        return tuple(round(c * a / 255 + bg * (1 - a / 255)) for c, bg in zip((r, g, b), background)) + (255,)

    return png(width, height, pixel)


def grub_png(width, height):
    return png(width, height, lambda x, y: gradient(y / (height - 1)) + (255,))


def main():
    did = distro_id()
    theme = os.path.join(ROOT, "packages", f"{did}-artwork", "usr", "share", "desktop-base", f"{did}-theme")
    installed = f"/usr/share/desktop-base/{did}-theme"
    for part in ("wallpaper", "lockscreen"):
        write(os.path.join(theme, part, "contents", "images", "1920x1080.svg"), background_svg(1920, 1080))
        write(os.path.join(theme, part, "gnome-background.xml"), f"""<background>
  <static>
    <duration>8640000.0</duration>
    <file>
      <size width="1920" height="1080">{installed}/{part}/contents/images/1920x1080.svg</size>
    </file>
  </static>
</background>
""")
    for name in ("background.svg", "background-nologo.svg"):
        write(os.path.join(theme, "login", name), background_svg(1920, 1080))
    write(os.path.join(theme, "grub", "grub-16x9.png"), grub_png(1920, 1080))
    write(os.path.join(theme, "grub", "grub-4x3.png"), grub_png(1024, 768))
    write(os.path.join(ROOT, "packages", f"{did}-artwork", "usr", "share", "icons", "hicolor",
                       "scalable", "apps", f"{did}-logo.svg"), logo_svg())
    branding = os.path.join(ROOT, "packages", f"{did}-installer", "usr", "share", "calamares", "branding", did)
    write(os.path.join(branding, "logo.png"), logo_png(128))
    write(os.path.join(branding, "welcome.png"), logo_png(256))
    write(os.path.join(branding, "slide.png"), slide_png(800, 440, 160))


if __name__ == "__main__":
    main()
