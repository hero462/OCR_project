import os, sys, json, zipfile, datetime, time, math as _m
import tkinter as tk
import zlib, struct, base64

APP_VERSION = 1.0
CHAR_MAP = ("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "БГДЁЖЗИЙЛПФЦЧШЩЪЫЬЭЮЯ"
            ".,:!?-+=/()@#%&*")
SEC_PER_CHAR = 5
MIN_W, MIN_H = 860, 720
OFF, BRUSH, ERASE_R = 28, 3, 5
CNT_MIN, CNT_MAX = 5, 5000

def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE = app_dir()
ROOT = os.path.join(BASE, "volunteer_dataset")
SESSION = os.path.join(BASE, "session.json")

#*цвета
def hex_rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def rgb_hex(c): return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in c)
def mix(a, b, t):
    a, b = hex_rgb(a), hex_rgb(b); return rgb_hex([a[i] + (b[i]-a[i])*t for i in range(3)])
def shade(c, t): return mix(c, "#000000", t)
def tint(c, t): return mix(c, "#ffffff", t)

THEMES = {
    "light": dict(bg="#e9edf4", panel="#ffffff", ink="#15181d", fg="#1c1f26",
                  muted="#8a91a3", border="#dfe4ec", accent="#3d6dff", accent_fg="#ffffff",
                  btn="#ffffff", btn_fg="#232733", hover="#eef2fa", good="#1f9d55"),
    "dark": dict(bg="#101216", panel="#1d2129", ink="#f2f4f8", fg="#e8eaf0",
                 muted="#8b93a7", border="#2c3140", accent="#5b8cff", accent_fg="#0d1017",
                 btn="#242935", btn_fg="#e8eaf0", hover="#2e3442", good="#3ddc84"),
}

def system_theme():
    try:
        if sys.platform == "win32":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if val else "dark"
    except Exception: pass
    try:
        import subprocess
        if sys.platform == "darwin":
            r = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"],
                               capture_output=True, text=True)
            return "dark" if "Dark" in r.stdout else "light"
        r = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"],
                           capture_output=True, text=True)
        if "prefer-dark" in r.stdout: return "dark"
        if "prefer-light" in r.stdout: return "light"
        r2 = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                            capture_output=True, text=True)
        return "dark" if "dark" in r2.stdout.lower() else "light"
    except Exception: pass
    return "dark"

#*обработка изображений
def _chunk(tag, data):
    return (struct.pack(">I", len(data)) + tag + data +
            struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))

def png_rgb(w, h, buf):
    raw = bytearray()
    st = w * 3
    for y in range(h):
        raw += b"\x00" + buf[y*st:(y+1)*st]
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + _chunk(b"IEND", b""))

def png_gray(w, h, px):
    raw = bytearray()
    for y in range(h):
        raw += b"\x00" + px[y*w:(y+1)*w]
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + _chunk(b"IEND", b""))

def photo_rgb(w, h, buf):
    return tk.PhotoImage(data=base64.b64encode(png_rgb(w, h, buf)).decode())

#*панель
def _inset(y, h, r):
    r = max(1.0, min(float(r), h / 2.0))
    if y < r: dy = r - (y + 0.5)
    elif y >= h - r: dy = r - (h - 1 - y + 0.5)
    else: return 0.0
    dy = min(dy, r)
    return r - _m.sqrt(max(0.0, r*r - dy*dy))

_CACHE = {}
def panel_photo(w, h, r, top, bottom, border, shadow, bg):
    w, h = int(w), int(h)
    key = (w, h, r, top, bottom, border, shadow, bg)
    if key in _CACHE: return _CACHE[key]
    if len(_CACHE) > 60: _CACHE.clear()
    if shadow:
        ml = mr = 4
        mt, mb = 3, 9
    else:
        ml = mr = mt = mb = 0
    W, H = w + ml + mr, h + mt + mb
    buf = bytearray(W*H*3)
    bgc = hex_rgb(bg)
    rowbg = bytes(bgc) * W
    for y in range(H):
        buf[y*W*3:(y+1)*W*3] = rowbg

    def fill_span(y, x0, x1, color):
        if x1 <= x0: return
        ix0 = int(_m.ceil(x0 + 0.5 - 1e-9)); ix1 = int(_m.floor(x1 - 0.5 + 1e-9)) + 1
        ix0c, ix1c = max(0, ix0), min(W, ix1)
        if ix1c > ix0c:
            base = y*W*3
            buf[base+ix0c*3:base+ix1c*3] = bytes(color) * (ix1c - ix0c)
        for ix, cov in ((ix0-1, (ix0-0.5) - x0), (ix1, x1 - (ix1-0.5))):
            cov = max(0.0, min(1.0, cov))
            if 0 <= ix < W and 0 < cov < 1:
                o = y*W*3 + ix*3
                for k in range(3):
                    buf[o+k] = int(buf[o+k]*(1-cov) + color[k]*cov)

    if shadow:
        for dy, ex, al in ((4, 3.0, 0.16), (3, 2.2, 0.12), (2, 1.5, 0.09), (1, 0.8, 0.06)):
            sc = tuple(int(v*(1-al)) for v in bgc)
            for y in range(mt+dy, min(H, mt+h+dy)):
                ly = y - dy - mt
                if ly < 0 or ly >= h: continue
                ins = _inset(ly, h, r) - ex
                fill_span(y, ml+ins, ml+w-ins, sc)
    tr, tg, tb = hex_rgb(top); br_, bg_, bb = hex_rgb(bottom)
    bor = hex_rgb(border) if border else None
    bw = 2
    for y in range(mt, mt+h):
        ly = y - mt
        f = ly / max(1, h-1)
        col = (int(tr+(br_-tr)*f), int(tg+(bg_-tg)*f), int(tb+(bb-tb)*f))
        ins = _inset(ly, h, r)
        x0, x1 = ml+ins, ml+w-ins
        fill_span(y, x0, x1, col)
        if bor:
            if ly < bw or ly >= h-bw:
                fill_span(y, x0, x1, bor)
            else:
                fill_span(y, x0, min(x0+bw, x1), bor)
                fill_span(y, max(x1-bw, x0), x1, bor)
    res = (photo_rgb(W, H, buf), (ml, mt))
    _CACHE[key] = res
    return res

def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2-x1, y2-y1; L2 = dx*dx + dy*dy
    if L2 == 0: return _m.hypot(px-x1, py-y1)
    t = max(0.0, min(1.0, ((px-x1)*dx + (py-y1)*dy) / L2))
    return _m.hypot(px-(x1+t*dx), py-(y1+t*dy))

#*преобразование изображений в 28 х 28
class Gray:
    __slots__ = ("w", "h", "px")
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w*h)
    def line(self, x1, y1, x2, y2, val, width):
        r = (width - 1) / 2 + 0.5
        xa = max(0, int(min(x1, x2) - r - 1)); xb = min(self.w, int(max(x1, x2) + r + 2))
        ya = max(0, int(min(y1, y2) - r - 1)); yb = min(self.h, int(max(y1, y2) + r + 2))
        for y in range(ya, yb):
            base = y*self.w
            for x in range(xa, xb):
                if seg_dist(x, y, x1, y1, x2, y2) <= r and self.px[base+x] < val:
                    self.px[base+x] = val
    def bbox(self):
        minx = miny = None; maxx = maxy = -1
        for y in range(self.h):
            base = y*self.w
            for x in range(self.w):
                if self.px[base+x]:
                    if minx is None or x < minx: minx = x
                    if x > maxx: maxx = x
                    if miny is None: miny = y
                    maxy = y
        return None if minx is None else (minx, miny, maxx+1, maxy+1)
    def crop(self, box):
        x0, y0, x1, y1 = box
        g = Gray(x1-x0, y1-y0)
        for y in range(y0, y1):
            g.px[(y-y0)*g.w:(y-y0+1)*g.w] = self.px[y*self.w+x0:y*self.w+x1]
        return g
    def resize(self, nw, nh):
        out = Gray(nw, nh)
        sx, sy = self.w/nw, self.h/nh
        for y in range(nh):
            fy = (y+0.5)*sy - 0.5
            y0 = max(0, min(self.h-1, int(_m.floor(fy)))); y1 = min(self.h-1, y0+1)
            ty = max(0.0, min(1.0, fy-y0))
            for x in range(nw):
                fx = (x+0.5)*sx - 0.5
                x0 = max(0, min(self.w-1, int(_m.floor(fx)))); x1 = min(self.w-1, x0+1)
                tx = max(0.0, min(1.0, fx-x0))
                p00 = self.px[y0*self.w+x0]; p10 = self.px[y0*self.w+x1]
                p01 = self.px[y1*self.w+x0]; p11 = self.px[y1*self.w+x1]
                a = p00 + (p10-p00)*tx; b = p01 + (p11-p01)*tx
                out.px[y*nw+x] = int(a + (b-a)*ty + 0.5)
        return out
    def paste(self, g, dx, dy):
        for y in range(g.h):
            ty = dy + y
            if 0 <= ty < self.h:
                for x in range(g.w):
                    tx = dx + x
                    if 0 <= tx < self.w and g.px[y*g.w+x]:
                        self.px[ty*self.w+tx] = g.px[y*g.w+x]

class InkModel:
    def __init__(self, w, h, brush):
        self.w, self.h, self.brush = w, h, brush
        self.strokes = []; self.rebuild()
    def rebuild(self):
        self.off = Gray(self.w, self.h)
        for s in self.strokes:
            self.off.line(*s, 255, self.brush)
    def add_seg(self, x1, y1, x2, y2):
        self.strokes.append((x1, y1, x2, y2))
        self.off.line(x1, y1, x2, y2, 255, self.brush)
    def erase_at(self, x, y, r):
        kept = [s for s in self.strokes if seg_dist(x, y, *s) > r]
        if len(kept) == len(self.strokes): return False
        self.strokes = kept; self.rebuild(); return True
    def clear(self):
        self.strokes = []; self.rebuild()

def count_for(ch):
    folder = os.path.join(ROOT, ch)
    if not os.path.isdir(folder): return 0
    return len([f for f in os.listdir(folder) if f.lower().endswith(".png")])

def next_incomplete(from_i, per_char):
    for i in range(from_i, len(CHAR_MAP)):
        if count_for(CHAR_MAP[i]) < per_char: return i
    return len(CHAR_MAP)

def free_path(folder):
    existing = {f for f in os.listdir(folder) if f.lower().endswith(".png")}
    n = 0
    while f"{n:03d}.png" in existing: n += 1
    return os.path.join(folder, f"{n:03d}.png")

def normalize(g):
    bb = g.bbox()
    if bb is None: return None
    ink = g.crop(bb)
    k = 20 / max(ink.w, ink.h)
    ink = ink.resize(max(1, round(ink.w*k)), max(1, round(ink.h*k)))
    f = Gray(28, 28)
    f.paste(ink, (28-ink.w)//2, (28-ink.h)//2)
    return f

def preview_photo(g):
    S = 5
    w = h = 28*S
    buf = bytearray(w*h*3)
    for y in range(h):
        srow = (y//S)*28
        row = bytearray(w*3)
        for x in range(w):
            v = g.px[srow + x//S]
            row[x*3:x*3+3] = bytes((v, v, v))
        buf[y*w*3:(y+1)*w*3] = row
    return photo_rgb(w, h, buf)

def fmt_time(seconds):
    minutes = seconds / 60
    if minutes < 60: return f"≈ {minutes:.0f} мин"
    hours = minutes / 60
    return f"≈ {int(hours)} ч {int(round(minutes % 60))} мин"

class App:
    def __init__(self, root):
        self.root = root
        root.title("Помоги ИИ читать почерк")
        root.minsize(MIN_W, MIN_H)
        self.theme = system_theme()
        self.tool = "pen"
        self.screen = "start"
        self.per_char, self.nick = 50, ""
        self.char_i, self.last_path = 0, None
        self.drawing, self.prev_pt, self.hover = False, None, None
        self.notice, self.archive_path = "", None
        self.t0, self.show_timer = None, False
        self.ink = InkModel(OFF, OFF, BRUSH)
        if os.path.exists(SESSION):
            try:
                s = json.load(open(SESSION, encoding="utf-8"))
                self.per_char = max(CNT_MIN, min(CNT_MAX, s.get("per_char", 50)))
                self.nick = s.get("nick", "")
            except Exception: pass
        self.c = tk.Canvas(root, highlightthickness=0)
        self.c.pack(fill="both", expand=True)
        self.c.bind("<ButtonPress-1>", self.on_press)
        self.c.bind("<B1-Motion>", self.on_drag)
        self.c.bind("<ButtonRelease-1>", self.on_release)
        self.c.bind("<Motion>", self.on_move)
        root.bind("<Return>", lambda e: self.on_enter())
        root.bind("<BackSpace>", self.on_backspace)
        root.bind("<Configure>", self.on_configure)
        self._after = None
        self.nick_entry = tk.Entry(root, relief="flat", borderwidth=0, highlightthickness=0,
                                   font=("Arial", 13))
        self.nick_entry.bind("<KeyRelease>", lambda e: self.set_nick(self.nick_entry.get()))
        self.count_entry = tk.Entry(root, relief="flat", borderwidth=0, highlightthickness=0,
                                    font=("Arial", 16, "bold"))
        self.count_entry.bind("<KeyRelease>", self.on_count_change)
        self.preview_ph = None
        self.layout(); self.draw_all()
        self._tick()

    def t(self): return THEMES[self.theme]
    def set_nick(self, v):
        self.nick = v.strip()[:24]; self.save_session()
    def save_session(self):
        json.dump({"per_char": self.per_char, "nick": self.nick},
                  open(SESSION, "w", encoding="utf-8"), ensure_ascii=False)
    def on_configure(self, e):
        if self._after: self.root.after_cancel(self._after)
        self._after = self.root.after(80, self.reflow)
    def reflow(self):
        self._after = None; self.layout(); self.draw_all()
    def focus_in_entry(self):
        w = self.root.focus_get()
        if w not in (self.nick_entry, self.count_entry): return False
        return bool(w.winfo_ismapped())
    def current_count(self):
        v = self.count_entry.get().strip()
        return int(v) if v else None
    def on_count_change(self, *e):
        v = self.count_entry.get()
        digits = "".join(ch for ch in v if ch.isdigit())[:4]
        if digits != v:
            self.count_entry.delete(0, "end"); self.count_entry.insert(0, digits)
        self.draw_start_info()
    def _tick(self):
        if self.screen == "draw" and self.t0 and self.show_timer:
            self.draw_timer()
        self.root.after(1000, self._tick)

    def layout(self):
        w = max(MIN_W, self.c.winfo_width() or MIN_W)
        h = max(MIN_H, self.c.winfo_height() or MIN_H)
        self.W, self.H, P, bh, gap = w, h, 24, 46, 14
        self.theme_rect = (w-54, 12, w-18, 48)
        self.buttons = []
        if self.screen == "start":
            self.card = (P, 92, w-P, h-P-84)
            cx = self.card[0] + 40
            self.nick_panel = (cx, self.card[1]+124, cx+340, self.card[1]+168)
            self.count_panel = (cx, self.card[1]+212, cx+150, self.card[1]+260)
            self.info_y = self.card[1] + 300
            self.nick_entry.place(x=self.nick_panel[0]+14, y=self.nick_panel[1]+11, width=312)
            self.count_entry.place(x=self.count_panel[0]+14, y=self.count_panel[1]+9, width=122)
            by = h - P - 62
            specs = [("begin", "✏️  Начать рисовать", "accent", self.begin, 0.30)]
            total_done = sum(count_for(c) for c in CHAR_MAP)
            if total_done > 0:
                specs.append(("cont", f"▶  Продолжить (готово {total_done})",
                              "panel", self.begin, 0.34))
            self.pack_row(specs, by)
        elif self.screen == "draw":
            self.nick_entry.place_forget(); self.count_entry.place_forget()
            head = 96
            side = max(220, min(int(w*0.5), h - head - bh - 2*P - gap))
            self.surf = (P, head, P+side, head+side)
            rx = P + side + 30
            self.prev_rect = (rx, head, rx+170, head+170)
            self.bar1 = (rx, head+250, rx+170, head+262)
            self.bar2 = (rx, head+298, rx+170, head+310)
            self.show_timer = side >= 390
            by = head + side + gap
            specs = [("save", "Сохранить (Enter)", "accent", self.save, 0.23),
                     ("clear", "🗑 Очистить", "panel", self.clear_ink, 0.13),
                     ("undo", "Отменить", "panel", self.undo, 0.12),
                     ("skip", "Пропустить", "panel", self.skip_char, 0.12),
                     ("tool", "🧽 Ластик" if self.tool == "pen" else "✏️ Перо",
                      "panel", self.toggle_tool, 0.12),
                     ("pack", "📦 Упаковать архив", "panel", self.pack_archive, 0.19)]
            self.pack_row(specs, by)
        else:
            self.nick_entry.place_forget(); self.count_entry.place_forget()
            by = h - P - 62
            specs = [("open", "📂 Открыть папку", "accent", self.open_folder, 0.30),
                     ("back", "Вернуться", "panel", lambda: self.goto("draw"), 0.28)]
            self.pack_row(specs, by)

    def pack_row(self, specs, by):
        """Расставляет кнопки ряда так, чтобы ряд ВСЕГДА помещался в окно."""
        P, bh, gap = 24, 46, 10
        avail = self.W - 2*P
        widths = [max(90, int((avail - gap*(len(specs)-1)) * s[4])) for s in specs]
        total = sum(widths) + gap*(len(specs)-1)
        if total > avail:
            k = (avail - gap*(len(specs)-1)) / sum(widths)
            widths = [max(70, int(x*k)) for x in widths]
        x = P
        for (bid, label, style, action, frac), bw in zip(specs, widths):
            self.buttons.append(dict(id=bid, rect=(x, by, x+bw, by+bh),
                                     label=label, style=style, action=action))
            x += bw + gap

    def goto(self, s):
        self.screen = s
        self.root.focus_set()
        self.layout(); self.draw_all()
    def begin(self):
        n = self.current_count()
        if n is None or n < CNT_MIN or n > CNT_MAX:
            self.notify(f"Введи число от {CNT_MIN} до {CNT_MAX}")
            return
        self.per_char = n
        self.char_i = next_incomplete(0, self.per_char)
        self.t0 = time.time()
        self.save_session(); self.goto("draw")
    def toggle_tool(self):
        self.tool = "eraser" if self.tool == "pen" else "pen"; self.layout(); self.draw_all()

    #*отрисовка
    def draw_all(self):
        t = self.t()
        self.c.delete("all"); self.c.configure(bg=t["bg"])
        self.draw_icon()
        getattr(self, "draw_" + self.screen)()
        self.draw_buttons()

    def draw_icon(self):
        t = self.t()
        x1, y1, x2, y2 = self.theme_rect
        cx, cy = (x1+x2)/2, (y1+y2)/2
        self.c.create_oval(x1, y1, x2, y2, fill=t["btn"], outline=t["border"], width=2, tags="static")
        if self.theme == "light":
            self.c.create_oval(cx-9, cy-9, cx+9, cy+9, fill=t["fg"], outline="", tags="static")
            self.c.create_oval(cx-4, cy-12, cx+14, cy+6, fill=t["btn"], outline="", tags="static")
        else:
            self.c.create_oval(cx-6, cy-6, cx+6, cy+6, fill=t["fg"], outline="", tags="static")
            for a in range(0, 360, 45):
                r = _m.radians(a)
                self.c.create_line(cx+9*_m.cos(r), cy+9*_m.sin(r), cx+13*_m.cos(r), cy+13*_m.sin(r),
                                   fill=t["fg"], width=2, tags="static")

    def put_panel(self, rect, r, top, bottom, border, shadow, tag="static", under=None):
        photo, (ml, mt) = panel_photo(rect[2]-rect[0], rect[3]-rect[1], r, top, bottom,
                                      border, shadow,
                                      under if under is not None else self.t()["bg"])
        self.c.create_image(rect[0]-ml, rect[1]-mt, anchor="nw", image=photo, tags=tag)
        return photo

    def card_color_at(self, y):
        t = self.t()
        f = max(0.0, min(1.0, (y - self.card[1]) / max(1, self.card[3] - self.card[1])))
        return mix(t["panel"], shade(t["panel"], 0.05), f)

    def draw_buttons(self):
        t = self.t()
        self.c.delete("btns")
        for i, b in enumerate(self.buttons):
            x1, y1, x2, y2 = b["rect"]; hov = self.hover == i
            if b["style"] == "accent":
                top, bot = tint(t["accent"], 0.28 if hov else 0.12), shade(t["accent"], 0.05 if hov else 0.10)
                fg, border, font = t["accent_fg"], t["accent"], ("Arial", 12, "bold")
            else:
                base = t["hover"] if hov else t["btn"]
                top, bot = tint(base, 0.03), shade(base, 0.06)
                fg, border, font = t["btn_fg"], t["border"], ("Arial", 12)
            self.put_panel(b["rect"], 14, top, bot, border, 6, tag="btns")
            self.c.create_text((x1+x2)/2, (y1+y2)/2, text=b["label"], fill=fg, font=font, tags="btns")

    def draw_start(self):
        t = self.t()
        x1, y1, x2, y2 = self.card
        self.put_panel(self.card, 24, t["panel"], shade(t["panel"], 0.05), t["border"], 14)
        cx = x1 + 40
        self.c.create_text(cx, y1+34, anchor="w", text="✍  Помоги ИИ читать почерк!",
                           font=("Arial", 24, "bold"), fill=t["fg"], tags="static")
        self.c.create_text(cx, y1+72, anchor="w",
                           text="Рисуй символы мышкой — твой почерк станет частью открытого датасета.",
                           font=("Arial", 12), fill=t["muted"], tags="static")
        self.c.create_text(cx, y1+112, anchor="w",
                           text="ТВОЙ НИК ИЛИ ИМЯ (НЕОБЯЗАТЕЛЬНО) — ИМ ПОДПИШУТ ТВОЙ ВКЛАД",
                           font=("Arial", 9, "bold"), fill=t["muted"], tags="static")
        self.put_panel(self.nick_panel, 12, t["panel"], shade(t["panel"], 0.04), t["border"], 0,
                       under=self.card_color_at((self.nick_panel[1] + self.nick_panel[3]) // 2))
        self.nick_entry.configure(bg=t["panel"], fg=t["fg"], insertbackground=t["accent"],
                                  selectbackground=t["accent"], selectforeground=t["accent_fg"])
        if not self.nick_entry.get() and self.nick:
            self.nick_entry.insert(0, self.nick)
        self.c.create_text(cx, y1+200, anchor="w",
                           text=f"СКОЛЬКО ПРИМЕРОВ НА СИМВОЛ ГОТОВ НАРИСОВАТЬ? ({CNT_MIN}–{CNT_MAX})",
                           font=("Arial", 9, "bold"), fill=t["muted"], tags="static")
        self.put_panel(self.count_panel, 12, t["panel"], shade(t["panel"], 0.04), t["border"], 0,
                       under=self.card_color_at((self.count_panel[1] + self.count_panel[3]) // 2))
        self.count_entry.configure(bg=t["panel"], fg=t["fg"], insertbackground=t["accent"],
                                   selectbackground=t["accent"], selectforeground=t["accent_fg"])
        if not self.count_entry.get():
            self.count_entry.insert(0, str(self.per_char))
        self.c.create_text(self.count_panel[2]+20, (self.count_panel[1]+self.count_panel[3])//2,
                           anchor="w", text="примеров на каждый из 73 знаков",
                           font=("Arial", 11), fill=t["muted"], tags="static")
        self.draw_start_info()
        self.c.create_text(cx, y1+384, anchor="w",
                           text="Можно закрывать программу в любой момент — прогресс сохраняется. "
                                "Частичный вклад тоже полезен!",
                           font=("Arial", 11), fill=t["muted"], tags="static")

    def draw_start_info(self):
        t = self.t()
        self.c.delete("info")
        val = self.current_count() or self.per_char
        n = val * len(CHAR_MAP)
        self.c.create_text(self.card[0]+40, self.info_y, anchor="w",
                           text=f"Количество символов:  {n}", font=("Arial", 15), fill=t["fg"], tags="info")
        self.c.create_text(self.card[0]+40, self.info_y+30, anchor="w",
                           text=f"Примерное время:  {fmt_time(n * SEC_PER_CHAR)}",
                           font=("Arial", 15), fill=t["fg"], tags="info")

    def draw_draw(self):
        t = self.t()
        self.put_panel(self.surf, 22, t["panel"], shade(t["panel"], 0.05), t["border"], 12)
        self.redraw_ink()
        done_all = sum(count_for(c) for c in CHAR_MAP)
        goal = self.per_char * len(CHAR_MAP)
        if self.char_i < len(CHAR_MAP):
            ch = CHAR_MAP[self.char_i]
            self.c.create_text(24, 26, anchor="w", text=f"Символ:  {ch}",
                               font=("Arial", 24, "bold"), fill=t["fg"], tags="static")
            self.c.create_text(24, 64, anchor="w",
                               text=f"образец {count_for(ch)+1}/{self.per_char}   •   "
                                    f"всего {done_all}/{goal}   •   рисуй как пишешь обычно",
                               font=("Arial", 11), fill=t["muted"], tags="static")
        else:
            self.c.create_text(24, 40, anchor="w", text="Всё готово! 🎉 Упакуй архив и отправь автору.",
                               font=("Arial", 20, "bold"), fill=t["good"], tags="static")
        self.put_panel(self.prev_rect, 16, t["panel"], shade(t["panel"], 0.05), t["border"], 8)
        self.draw_preview()
        px1, py1, px2, py2 = self.prev_rect
        self.c.create_text((px1+px2)//2, py2+12, anchor="n", text="так символ увидит сеть",
                           font=("Arial", 10), fill=t["muted"], tags="static")
        self.c.create_line(px1, py2+40, px2, py2+40, fill=t["border"], width=2, tags="static")
        self.draw_bar(self.bar1, count_for(CHAR_MAP[min(self.char_i, len(CHAR_MAP)-1)]) / self.per_char,
                      "текущий символ")
        self.draw_bar(self.bar2, done_all / goal, "весь датасет")
        if self.show_timer: self.draw_timer()
        if self.notice:
            self.c.create_text(self.W-70, 78, anchor="e", text=self.notice,
                               font=("Arial", 11, "bold"), fill=t["good"], tags="static")

    def draw_timer(self):
        t = self.t()
        self.c.delete("timer")
        el = max(0, int(time.time() - self.t0)) if self.t0 else 0
        h, m, s = el // 3600, (el % 3600) // 60, el % 60
        rx = self.prev_rect[0]
        y = self.bar2[3] + 36
        self.c.create_text(rx, y, anchor="nw", text="ВРЕМЯ СЕССИИ",
                           font=("Arial", 9, "bold"), fill=t["muted"], tags="timer")
        self.c.create_text(rx, y+16, anchor="nw", text=f"{h:02d}:{m:02d}:{s:02d}",
                           font=("Monospace", 20, "bold"), fill=t["fg"], tags="timer")

    def draw_preview(self):
        self.c.delete("preview")
        g = normalize(self.ink.off)
        self.preview_ph = preview_photo(g if g is not None else Gray(28, 28))
        self.c.create_image(self.prev_rect[0]+15, self.prev_rect[1]+15, anchor="nw",
                            image=self.preview_ph, tags="preview")

    def draw_bar(self, rect, frac, label):
        t = self.t()
        bx1, by1, bx2, by2 = rect
        frac = max(0.0, min(1.0, frac))
        self.c.create_text(bx1, by1-18, anchor="nw", text=label,
                           font=("Arial", 10), fill=t["muted"], tags="static")
        self.c.create_text(bx2, by1-18, anchor="ne", text=f"{int(frac*100)}%",
                           font=("Arial", 10, "bold"), fill=t["fg"], tags="static")
        self.put_panel(rect, 6, shade(t["bg"], 0.10), shade(t["bg"], 0.10), None, 0)
        fw = max(12, int((bx2-bx1) * frac))
        self.put_panel((bx1, by1, bx1+fw, by2), 6,
                       tint(t["accent"], 0.15), shade(t["accent"], 0.10), None, 0)

    def redraw_ink(self):
        t = self.t()
        self.c.delete("ink")
        k = (self.surf[2]-self.surf[0]) / OFF
        for x1, y1, x2, y2 in self.ink.strokes:
            self.c.create_line(self.surf[0]+x1*k, self.surf[1]+y1*k, self.surf[0]+x2*k, self.surf[1]+y2*k,
                               width=max(2, BRUSH*k), fill=t["ink"], capstyle="round",
                               joinstyle="round", tags="ink")

    #*события
    def hit(self, x, y):
        if self.theme_rect[0] <= x <= self.theme_rect[2] and self.theme_rect[1] <= y <= self.theme_rect[3]:
            return "theme"
        for i, b in enumerate(self.buttons):
            x1, y1, x2, y2 = b["rect"]
            if x1 <= x <= x2 and y1 <= y <= y2: return i
        if self.screen == "draw" and self.surf[0] <= x <= self.surf[2] and self.surf[1] <= y <= self.surf[3]:
            return "surf"
        return None

    def to_off(self, x, y):
        k = (self.surf[2]-self.surf[0]) / OFF
        return ((x-self.surf[0])/k, (y-self.surf[1])/k)

    def on_press(self, e):
        h = self.hit(e.x, e.y)
        if h == "theme":
            self.theme = "dark" if self.theme == "light" else "light"; self.draw_all()
        elif isinstance(h, int):
            self.buttons[h]["action"]()
        elif h == "surf":
            self.drawing = True; self.prev_pt = self.to_off(e.x, e.y)

    def on_drag(self, e):
        if not self.drawing: return
        ox, oy = self.to_off(e.x, e.y)
        ox, oy = max(0, min(OFF-1, ox)), max(0, min(OFF-1, oy))
        if self.tool == "pen":
            px, py = self.prev_pt
            self.ink.add_seg(px, py, ox, oy)
            k = (self.surf[2]-self.surf[0]) / OFF
            t = self.t()
            self.c.create_line(self.surf[0]+px*k, self.surf[1]+py*k, self.surf[0]+ox*k, self.surf[1]+oy*k,
                               width=max(2, BRUSH*k), fill=t["ink"], capstyle="round",
                               joinstyle="round", tags="ink")
        else:
            if self.ink.erase_at(ox, oy, ERASE_R):
                self.redraw_ink(); self.draw_preview()
        self.prev_pt = (ox, oy)

    def on_release(self, e):
        if self.drawing and self.screen == "draw":
            self.draw_preview()
        self.drawing, self.prev_pt = False, None

    def on_move(self, e):
        h = self.hit(e.x, e.y)
        nh = h if isinstance(h, int) else None
        if nh != self.hover:
            self.hover = nh; self.draw_buttons()
        cur = ("hand2" if nh is not None or h == "theme"
               else "circle" if (h == "surf" and self.tool == "eraser")
               else "cross" if h == "surf" else "")
        try:
            self.c.configure(cursor=cur)
        except Exception:
            self.c.configure(cursor="cross" if h == "surf" else "")

    def on_enter(self):
        if self.focus_in_entry(): return
        if self.screen == "draw": self.save()
        elif self.screen == "start": self.begin()

    def on_backspace(self, e):
        if self.screen == "draw" and not self.focus_in_entry():
            self.undo()

    #*логика
    def notify(self, msg):
        self.notice = msg; self.draw_all()
        self.root.after(2500, self._clear_notice)
    def _clear_notice(self):
        self.notice = ""; self.draw_all()

    def save(self):
        if self.char_i >= len(CHAR_MAP): return
        norm = normalize(self.ink.off)
        if norm is None:
            self.notify("Пусто — сначала нарисуй символ"); return
        ch = CHAR_MAP[self.char_i]
        folder = os.path.join(ROOT, ch)
        os.makedirs(folder, exist_ok=True)
        path = free_path(folder)
        try:
            tmp = path + ".tmp"
            with open(tmp, "wb") as f:
                f.write(png_gray(28, 28, norm.px))
            os.replace(tmp, path)
        except Exception as ex:
            print("SAVE ERROR:", ex); self.notify("Ошибка записи!"); return
        self.last_path = path
        self.ink.clear()
        if count_for(ch) >= self.per_char:
            self.char_i = next_incomplete(self.char_i, self.per_char)
        self.draw_all()

    def undo(self):
        if not self.last_path or not os.path.exists(self.last_path): return
        os.remove(self.last_path)
        ch = os.path.basename(os.path.dirname(self.last_path))
        self.last_path = None
        if self.char_i >= len(CHAR_MAP) or CHAR_MAP[self.char_i] != ch:
            self.char_i = CHAR_MAP.index(ch)
        self.draw_all()

    def skip_char(self):
        self.char_i = next_incomplete(self.char_i + 1, self.per_char)
        self.ink.clear(); self.draw_all()

    def clear_ink(self):
        self.ink.clear()
        self.prev_pt = None; self.drawing = False
        self.redraw_ink(); self.draw_preview()
        self.notify("Поле очищено")

    def pack_archive(self):
        total = sum(count_for(c) for c in CHAR_MAP)
        if total == 0:
            self.notify("Нечего паковать — датасет пуст"); return
        if getattr(self, "packed_total", None) == total:
            self.notify("Новых символов нет — архив уже актуален"); return
        stamp = datetime.date.today().isoformat()
        name = f"handwrite_{self.nick or 'anon'}_{self.per_char}_{stamp}.zip"
        path = os.path.join(BASE, name)
        counts = {ch: count_for(ch) for ch in CHAR_MAP}
        meta = dict(app_version=APP_VERSION, nick=self.nick, per_char=self.per_char,
                    char_map=CHAR_MAP, counts=counts, total=total, packed_at=stamp)
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            for ch in CHAR_MAP:
                folder = os.path.join(ROOT, ch)
                if not os.path.isdir(folder): continue
                for f in sorted(os.listdir(folder)):
                    if f.lower().endswith(".png"):
                        z.write(os.path.join(folder, f), arcname=f"dataset/{ch}/{f}")
            z.writestr("meta.json", json.dumps(meta, ensure_ascii=False, indent=2))
        self.archive_path = path
        self.packed_total = total
        print("Архив:", path)
        self.goto("done")

    def open_folder(self):
        import subprocess
        try:
            if sys.platform == "win32":
                os.startfile(BASE)
            elif sys.platform == "darwin":
                subprocess.run(["open", BASE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["xdg-open", BASE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as ex:
            print("Не удалось открыть папку:", ex)

    def draw_done(self):
        t = self.t()
        self.c.create_text(self.W//2, 120, anchor="n", text="📦 Архив готов!",
                           font=("Arial", 28, "bold"), fill=t["fg"], tags="static")
        if self.archive_path:
            size_mb = os.path.getsize(self.archive_path) / 1e6
            self.c.create_text(self.W//2, 180, anchor="n", text=os.path.basename(self.archive_path),
                               font=("Arial", 14, "bold"), fill=t["accent"], tags="static")
            self.c.create_text(self.W//2, 212, anchor="n",
                               text=f"{size_mb:.1f} МБ   •   {self.archive_path}",
                               font=("Arial", 10), fill=t["muted"], tags="static")
        self.c.create_text(self.W//2, 268, anchor="n",
                           text="Отправь этот файл автору проекта (ссылка и контакты — в описании видео).\n"
                                "Спасибо! Твой почерк теперь часть датасета 💙",
                           font=("Arial", 13), fill=t["fg"], justify="center", tags="static")

root = tk.Tk()
App(root)
root.mainloop()