"""
Generates assets/sentinel.ico — a simple waveform / shield icon.
Run once before building. Requires no external dependencies beyond stdlib.

Uses Windows-compatible ICO format with 256x256, 48x48, 32x32, 16x16 sizes.
We generate a minimal valid ICO using raw BMP data written by hand.
"""

import struct
import math
import os

def make_bmp_pixel(r, g, b, a=255):
    return bytes([b, g, r, a])

def render_icon(size: int) -> bytes:
    """Render a size×size BGRA image of the Sentinel waveform icon."""
    pixels = bytearray(size * size * 4)

    cx, cy = size / 2, size / 2
    r_outer = size * 0.46
    r_inner = size * 0.34
    stroke = max(1, size // 20)

    for y in range(size):
        for x in range(size):
            idx = (y * size + x) * 4

            dx = x - cx
            dy = y - cy
            dist = math.sqrt(dx * dx + dy * dy)

            # Background: near-black
            pr, pg, pb, pa = 10, 13, 15, 255

            # Outer ring (cyan)
            if r_outer - stroke <= dist <= r_outer:
                pr, pg, pb = 90, 175, 207

            # Inner shield fill (slightly lighter dark)
            elif dist < r_inner:
                pr, pg, pb = 18, 28, 38

            # Waveform drawn as a sine wave band through the center
            norm_x = (x - cx) / (size * 0.38)
            if abs(norm_x) <= 1.0:
                wave_y = cy + math.sin(norm_x * math.pi * 1.5) * (size * 0.14)
                wave_thickness = max(1, size // 18)
                if abs(y - wave_y) <= wave_thickness:
                    # Color by amplitude (cyan → red toward peaks)
                    t = abs(math.sin(norm_x * math.pi * 1.5))
                    pr = int(90 + t * 134)
                    pg = int(175 - t * 135)
                    pb = int(207 - t * 177)
                    pa = 255

            pixels[idx:idx+4] = [pb, pg, pr, pa]  # BGRA

    return bytes(pixels)


def bgra_to_ico(sizes=(256, 48, 32, 16)) -> bytes:
    images = []
    for sz in sizes:
        bgra = render_icon(sz)
        # BMP info header (BITMAPINFOHEADER) — 40 bytes
        # Height is doubled for ICO (XOR mask + AND mask)
        header = struct.pack(
            "<IiiHHIIiiII",
            40,       # biSize
            sz,       # biWidth
            sz * 2,   # biHeight (doubled)
            1,        # biPlanes
            32,       # biBitCount
            0,        # biCompression (BI_RGB)
            0,        # biSizeImage
            0, 0,     # biXPelsPerMeter, biYPelsPerMeter
            0, 0,     # biClrUsed, biClrImportant
        )
        # Pixel data: bottom-up rows
        pixel_rows = []
        for row in range(sz - 1, -1, -1):
            pixel_rows.append(bgra[row * sz * 4:(row + 1) * sz * 4])
        pixel_data = b"".join(pixel_rows)
        # AND mask: all zeros (fully opaque)
        mask_row_bytes = ((sz + 31) // 32) * 4
        and_mask = b"\x00" * (mask_row_bytes * sz)
        images.append(header + pixel_data + and_mask)

    # ICO file header
    n = len(sizes)
    ico_header = struct.pack("<HHH", 0, 1, n)  # reserved, type=1, count

    # Directory entries (16 bytes each)
    offset = 6 + n * 16
    directory = b""
    for i, (sz, img) in enumerate(zip(sizes, images)):
        w = 0 if sz == 256 else sz   # 0 means 256 in ICO format
        h = 0 if sz == 256 else sz
        directory += struct.pack(
            "<BBBBHHII",
            w, h,       # width, height
            0,          # color count (0 = no palette)
            0,          # reserved
            1,          # planes
            32,         # bit count
            len(img),   # size of image data
            offset,     # offset from start of file
        )
        offset += len(img)

    return ico_header + directory + b"".join(images)


if __name__ == "__main__":
    os.makedirs("assets", exist_ok=True)
    ico_data = bgra_to_ico()
    with open("assets/sentinel.ico", "wb") as f:
        f.write(ico_data)
    print(f"Created assets/sentinel.ico  ({len(ico_data):,} bytes)")
