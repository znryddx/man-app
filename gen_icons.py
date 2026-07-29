import math
from PIL import Image, ImageDraw

PAPER = (246, 243, 236, 255)
DAI = (46, 58, 78, 255)
MO = (58, 74, 63, 255)


def rounded_rect(draw, box, r, outline, width):
    draw.rounded_rectangle(box, radius=r, outline=outline, width=width)


def make(size):
    img = Image.new("RGBA", (size, size), PAPER)
    d = ImageDraw.Draw(img)
    m = int(size * 0.16)            # margin to keep safe zone
    w = max(2, int(size * 0.035))   # stroke width
    r = int(size * 0.18)            # corner radius
    # outer ink frame
    rounded_rect(d, [m, m, size - m, size - m], r, DAI, w)
    # inner thin frame
    m2 = int(size * 0.26)
    rounded_rect(d, [m2, m2, size - m2, size - m2], int(size * 0.10), DAI, max(1, int(size * 0.012)))
    # center ink dot (mo green)
    cr = int(size * 0.085)
    cx, cy = size // 2, size // 2
    d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=MO)
    return img


for s in (192, 512):
    out = f"C:/Users/jiang/WorkBuddy/2026-07-29-08-13-38/app/icons/icon-{s}.png"
    make(s).save(out, "PNG")
    print("wrote", out)
