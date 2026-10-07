import math
import tkinter as tk
from PIL import Image, ImageDraw, ImageFilter, ImageTk

def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def rgb_hex(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in c)

def mix(c1, c2, t):
    a, b = hex_rgb(c1), hex_rgb(c2)
    return rgb_hex([a[i] + (b[i] - a[i]) * t for i in range(3)])

def shade(c, t): return mix(c, "#000000", t)
def tint(c, t): return mix(c, "#ffffff", t)

THEMES = {
    "light": dict(bg="#e9edf4", panel="#ffffff", ink="#15181d", fg="#1c1f26",
                  muted="#8a91a3", border="#dfe4ec", accent="#3d6dff", accent_fg="#ffffff",
                  btn="#ffffff", btn_fg="#232733", result="#ffffff", result_fg="#10131a",
                  hover="#eef2fa"),
    "dark": dict(bg="#101216", panel="#1d2129", ink="#f2f4f8", fg="#e8eaf0",
                 muted="#8b93a7", border="#2c3140", accent="#5b8cff", accent_fg="#0d1017",
                 btn="#242935", btn_fg="#e8eaf0", result="#171a21", result_fg="#eef0f6",
                 hover="#2e3442"),
}

_CACHE = {}

def panel_img(w, h, r, top, bottom, border=None, shadow=10, ss=3):
    w, h = int(w), int(h)
    key = (w, h, r, top, bottom, border, shadow)
    if key in _CACHE:
        return _CACHE[key]
    if len(_CACHE) > 80:
        _CACHE.clear()
    m = shadow + 6
    W, H = w + 2 * m, h + 2 * m
    img = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    if shadow:
        sh = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
        ImageDraw.Draw(sh).rounded_rectangle(
            [m*ss, (m + shadow*0.7)*ss, (m+w)*ss, (m + h + shadow*0.7)*ss],
            radius=r*ss, fill=(0, 0, 0, 120))
        sh = sh.filter(ImageFilter.GaussianBlur(shadow * ss * 0.6))
        img = Image.alpha_composite(img, sh)
    grad = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
    dg = ImageDraw.Draw(grad)
    for i in range(h * ss + 1):
        dg.line([(m*ss, m*ss + i), ((m+w)*ss, m*ss + i)],
                fill=hex_rgb(mix(top, bottom, i / (h * ss))) + (255,))
    mask = Image.new("L", (W * ss, H * ss), 0)
    ImageDraw.Draw(mask).rounded_rectangle([m*ss, m*ss, (m+w)*ss, (m+h)*ss], radius=r*ss, fill=255)
    grad.putalpha(mask)
    img = Image.alpha_composite(img, grad)
    if border:
        ImageDraw.Draw(img).rounded_rectangle([m*ss, m*ss, (m+w)*ss, (m+h)*ss],
                                              radius=r*ss, outline=hex_rgb(border)+(255,), width=ss*2)
    photo = ImageTk.PhotoImage(img.resize((W, H), Image.LANCZOS))
    _CACHE[key] = (photo, m)
    return photo, m

def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx*dx + dy*dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1)*dx + (py - y1)*dy) / L2))
    return math.hypot(px - (x1 + t*dx), py - (y1 + t*dy))

class InkModel:
    def __init__(self, off_w, off_h, brush):
        self.w, self.h, self.brush = off_w, off_h, brush
        self.strokes = []
        self.off = Image.new("L", (off_w, off_h), 0)
        self.draw = ImageDraw.Draw(self.off)

    def add_seg(self, x1, y1, x2, y2):
        self.strokes.append((x1, y1, x2, y2))
        self.draw.line([x1, y1, x2, y2], fill=255, width=self.brush)

    def erase_at(self, x, y, r):
        kept = [s for s in self.strokes if seg_dist(x, y, *s) > r]
        if len(kept) == len(self.strokes):
            return False
        self.strokes = kept
        self.rebuild()
        return True

    def rebuild(self):
        self.off = Image.new("L", (self.w, self.h), 0)
        self.draw = ImageDraw.Draw(self.off)
        for s in self.strokes:
            self.draw.line(s, fill=255, width=self.brush)

    def clear(self):
        self.strokes = []
        self.rebuild()