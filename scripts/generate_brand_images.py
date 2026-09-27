#!/usr/bin/env python3
"""Generate the brand images Home Assistant uses for this integration.

Home Assistant takes integration icons and logos from the
home-assistant/brands repository, which expects:

    icon.png      256x256, square, transparent background
    icon@2x.png   512x512
    logo.png      up to 256 tall, width free
    logo@2x.png   up to 512 tall

Run:  python scripts/generate_brand_images.py

Everything is drawn at 4x and downsampled, which is what keeps the curves
and the sweep edge smooth.
"""

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "brands",
    "sportsradar",
)

SS = 4  # supersampling factor

NAVY = (11, 37, 69, 255)
NAVY_EDGE = (8, 27, 51, 255)
GREEN = (47, 191, 135, 255)
GREEN_SOFT = (47, 191, 135, 90)
WHITE = (255, 255, 255, 255)
BALL_DARK = (16, 42, 67, 255)
# The wordmark sits on whatever card colour the theme uses, so it has to
# stay legible on both white and near-black. Navy failed on dark.
SLATE = (100, 116, 139, 255)

FONT_CANDIDATES = (
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
)


def _trim(img):
    """Crop away fully transparent edges.

    home-assistant/brands rejects images with empty space around the artwork,
    so every output is trimmed to its alpha bounding box before resizing.
    """
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def _font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_football(draw, cx, cy, r):
    """A small football: white ball with a dark pentagon and seams."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=WHITE)

    # Central pentagon
    pent = []
    for i in range(5):
        angle = math.radians(-90 + i * 72)
        pent.append((cx + r * 0.42 * math.cos(angle), cy + r * 0.42 * math.sin(angle)))
    draw.polygon(pent, fill=BALL_DARK)

    # Seams running out from each corner of the pentagon
    for px, py in pent:
        dx, dy = px - cx, py - cy
        length = (dx * dx + dy * dy) ** 0.5
        if not length:
            continue
        draw.line(
            [(px, py), (cx + dx / length * r * 0.98, cy + dy / length * r * 0.98)],
            fill=BALL_DARK,
            width=max(2, int(r * 0.13)),
        )


def build_icon(size):
    """The radar dish with a ball as the contact."""
    s = size * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = s * 0.02
    box = [pad, pad, s - pad, s - pad]

    # Dish
    draw.ellipse(box, fill=NAVY, outline=NAVY_EDGE, width=int(s * 0.012))

    cx = cy = s / 2
    radius = (s - 2 * pad) / 2

    # Range rings
    ring_w = max(2, int(s * 0.011))
    for factor in (0.34, 0.62, 0.88):
        rr = radius * factor
        draw.ellipse(
            [cx - rr, cy - rr, cx + rr, cy + rr],
            outline=(47, 191, 135, 120),
            width=ring_w,
        )

    # Cross hairs
    draw.line([(cx, cy - radius * 0.88), (cx, cy + radius * 0.88)],
              fill=(47, 191, 135, 70), width=ring_w)
    draw.line([(cx - radius * 0.88, cy), (cx + radius * 0.88, cy)],
              fill=(47, 191, 135, 70), width=ring_w)

    # Sweep: wedges of falling opacity behind the leading edge
    sweep = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sweep_draw = ImageDraw.Draw(sweep)
    lead = -58  # degrees
    for step in range(28):
        alpha = int(150 * (1 - step / 28) ** 2)
        if alpha <= 0:
            continue
        start = lead + step * 2.6
        sweep_draw.pieslice(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            start=start,
            end=start + 2.8,
            fill=(47, 191, 135, alpha),
        )
    img = Image.alpha_composite(img, sweep)
    draw = ImageDraw.Draw(img)

    # Leading edge of the sweep
    angle = math.radians(lead)
    draw.line(
        [(cx, cy), (cx + radius * math.cos(angle), cy + radius * math.sin(angle))],
        fill=GREEN,
        width=max(3, int(s * 0.016)),
    )

    # The contact: a football sitting on the sweep
    bx = cx + radius * 0.52 * math.cos(math.radians(lead - 6))
    by = cy + radius * 0.52 * math.sin(math.radians(lead - 6))
    glow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        [bx - s * 0.17, by - s * 0.17, bx + s * 0.17, by + s * 0.17],
        fill=GREEN_SOFT,
    )
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)
    _draw_football(draw, bx, by, s * 0.115)

    # Centre pin
    pin = s * 0.022
    draw.ellipse([cx - pin, cy - pin, cx + pin, cy + pin], fill=GREEN)

    return _trim(img).resize((size, size), Image.Resampling.LANCZOS)


def build_logo(height):
    """Icon plus wordmark, on a transparent background."""
    icon_px = height
    icon = build_icon(icon_px)

    gap = int(height * 0.16)
    font_size = int(height * 0.40)
    font = _font(font_size)

    probe = Image.new("RGBA", (10, 10))
    pdraw = ImageDraw.Draw(probe)
    top_w = pdraw.textbbox((0, 0), "SPORTS", font=font)[2]
    bot_w = pdraw.textbbox((0, 0), "RADAR", font=font)[2]
    text_w = max(top_w, bot_w)

    width = icon_px + gap + text_w + int(height * 0.06)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    img.paste(icon, (0, 0), icon)

    draw = ImageDraw.Draw(img)
    x = icon_px + gap
    draw.text((x, height * 0.11), "SPORTS", font=font, fill=SLATE)
    draw.text((x, height * 0.51), "RADAR", font=font, fill=GREEN)

    # Trim, then scale back so the height is exactly what was asked for.
    img = _trim(img)
    scale = height / img.height
    return img.resize(
        (max(1, round(img.width * scale)), height), Image.Resampling.LANCZOS
    )


def main():
    """Write every brand image and report what was produced."""
    os.makedirs(OUT_DIR, exist_ok=True)

    # Build the @2x versions and halve them, so the 1x is exactly half the
    # 2x in both dimensions. Rounding each size independently can leave the
    # widths a pixel or two apart, which their CI rejects.
    icon_2x = build_icon(512)
    logo_2x = build_logo(512)

    outputs = {
        "icon.png": icon_2x.resize((256, 256), Image.Resampling.LANCZOS),
        "icon@2x.png": icon_2x,
        "logo.png": logo_2x.resize(
            (logo_2x.width // 2, logo_2x.height // 2), Image.Resampling.LANCZOS
        ),
        "logo@2x.png": logo_2x,
    }

    for name, image in outputs.items():
        path = os.path.join(OUT_DIR, name)
        image.save(path, "PNG", optimize=True)
        print("  %-14s %sx%s  %d bytes" % (
            name, image.width, image.height, os.path.getsize(path)))

    print("")
    print("Written to %s" % OUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
