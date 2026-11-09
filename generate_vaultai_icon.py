#!/usr/bin/env python3
"""Generate a VaultAI app icon (PNG + .icns) using Pillow."""

import os
from PIL import Image, ImageDraw

# ─── 1. Icon design ────────────────────────────────────────────────

SIZE = 1024  # master size (all other sizes derived by scaling)


def make_master():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    cx = SIZE / 2
    cy = SIZE / 2
    w = SIZE * 0.75
    h = SIZE * 0.85

    # Vault-shield polygon (rounded-ish)
    shield = [
        (cx, SIZE * 0.10),
        (cx - w / 2, SIZE * 0.18),
        (cx - w / 2, SIZE * 0.50),
        (cx, SIZE * 0.80),
        (cx + w / 2, SIZE * 0.50),
        (cx + w / 2, SIZE * 0.18),
    ]
    d.polygon(shield, fill=(46, 125, 50, 255), outline=(32, 80, 32, 255))

    # Checkmark – drawn as two thick lines with rounded joins
    margin = SIZE * 0.20
    line_w = int(SIZE * 0.10)

    def rounded_line(draw, p1, p2, width, color=(255, 255, 255, 255)):
        try:
            draw.line([p1, p2], fill=color, width=width, joint="curve")
        except TypeError:
            # Fallback for older Pillow versions
            draw.line([p1, p2], fill=color, width=width)

    # Segment 1
    rounded_line(
        d,
        (cx - w / 2 + margin, cy + SIZE * 0.18),
        (cx - margin, cy + w / 2 - margin),
        line_w,
    )
    # Segment 2
    rounded_line(
        d,
        (cx - margin, cy + w / 2 - margin),
        (cx + w / 2 - margin, cy - margin),
        line_w,
    )

    return img


def make_icns():
    """Create a full .iconset directory and convert it to .icns."""
    master = make_master()

    # Required sizes for an .iconset
    sizes = [16, 32, 64, 128, 256, 512, 1024]

    iconset = "VaultAI.iconset"
    if os.path.exists(iconset):
        for f in os.listdir(iconset):
            os.remove(os.path.join(iconset, f))
        os.rmdir(iconset)

    os.makedirs(iconset)
    for s in sizes:
        if s == SIZE:
            # Master is just used for the 1024x1024 entry
            master.save(os.path.join(iconset, f"icon_{s}x{s}.png"))
        else:
            s_img = master.resize((s, s), Image.LANCZOS)
            s_img.save(os.path.join(iconset, f"icon_{s}x{s}.png"))

    # Convert .iconset to .icns
    exit_code = os.system(
        "cd VaultAI.iconset && iconutil -c icns ../VaultAI_icon.icns >/dev/null 2>&1"
    )
    if exit_code != 0:
        raise RuntimeError("iconutil failed to generate .icns file")

    print("Generated VaultAI_icon.icns")


if __name__ == "__main__":
    make_icns()
