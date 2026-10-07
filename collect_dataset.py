import os
import tkinter as tk
from PIL import Image, ImageDraw, ImageTk
from char_model import CHAR_MAP as CHARS
from ui_kit import THEMES, tint, shade, panel_img, InkModel

SAMPLES_PER_CHAR = 100
ROOT = "dataset"
OFF = 28
BRUSH = 3
ERASE_R = 5
MIN_W, MIN_H = 780, 640

def count_for(ch):
    folder = os.path.join(ROOT, ch)
    if not os.path.isdir(folder): return 0
    return len([f for f in os.listdir(folder) if f.lower().endswith(".png")])

def next_incomplete(from_i):
    for i in range(from_i, len(CHARS)):
        if count_for(CHARS[i]) < SAMPLES_PER_CHAR: return i
    return len(CHARS)

def free_path(folder):
    existing = {f for f in os.listdir(folder) if f.lower().endswith(".png")}
    n = 0
    while f"{n:03d}.png" in existing: n += 1
    return os.path.join(folder, f"{n:03d}.png")

def normalize(off):
    bbox = off.getbbox()
    if bbox is None: return None
    ink = off.crop(bbox)
    k = 20 / max(ink.size)
    ink = ink.resize((max(1, round(ink.width*k)), max(1, round(ink.height*k))), Image.LANCZOS)
    f = Image.new("L", (28, 28), 0)
    f.paste(ink, ((28-ink.width)//2, (28-ink.height)//2))
    return f

class Collector:
    def __init__(self, root):
        self.root = root
        root.title("Сборщик датасета")
        root.minsize(MIN_W, MIN_H)
        self.theme, self.tool = "light", "pen"
        self.char_i = next_incomplete(0)
        self.last_path = None
        self.drawing, self.prev_pt, self.hover = False, None, None
        self.ink = InkModel(OFF, OFF, BRUSH)
        self.c = tk.Canvas(root, highlightthickness=0)
        self.c.pack(fill="both", expand=True)
        self.c.bind("<ButtonPress-1>", self.on_press)
        self.c.bind("<B1-Motion>", self.on_drag)
        self.c.bind("<ButtonRelease-1>", lambda e: (setattr(self, "prev_pt", None),
                                                     setattr(self, "drawing", False),
                                                     self.update_preview()))
        self.c.bind("<Motion>", self.on_move)
        root.bind("<Return>", lambda e: self.save())
        root.bind("<BackSpace>", lambda e: self.undo())
        root.bind("<Configure>", self.on_configure)
        self._after, self.preview_photo = None, None
        self.layout(); self.draw_all()

    def t(self): return THEMES[self.theme]

    def on_configure(self, e):
        if self._after: self.root.after_cancel(self._after)
        self._after = self.root.after(80, self.reflow)

    def reflow(self):
        self._after = None
        self.layout(); self.draw_all()

    def layout(self):
        w = max(MIN_W, self.c.winfo_width() or MIN_W)
        h = max(MIN_H, self.c.winfo_height() or MIN_H)
        self.W, self.H, P, head, bh, gap = w, h, 20, 96, 44, 14
        side = min(int(w * 0.52), h - head - bh - 3*P)
        side = max(220, side)
        x0, y0 = P, head
        self.surf = (x0, y0, x0 + side, y0 + side)
        rx = x0 + side + 24
        self.prev_rect = (rx, head, rx + 170, head + 170)
        self.bar_rect = (rx, head + 190, rx + 170, head + 202)
        self.bar2_rect = (rx, head + 216, rx + 170, head + 228)
        by = y0 + side + gap
        self.buttons, x = [], P
        specs = [("save", "Сохранить (Enter)", "accent", self.save, 0.30),
                 ("undo", "Отменить", "panel", self.undo, 0.16),
                 ("skip", "Пропустить", "panel", self.skip_char, 0.16),
                 ("tool", "🧽 Ластик", "panel", self.toggle_tool, 0.14)]
        for bid, label, style, action, frac in specs:
            bw = max(100, int((w - 2*P - 30) * frac))
            self.buttons.append(dict(id=bid, rect=(x, by, x+bw, by+bh), label=label,
                                     style=style, action=action))
            x += bw + 10
        self.theme_rect = (w-54, 12, w-18, 48)

    def draw_all(self):
        t = self.t()
        self.c.delete("all")
        self.c.configure(bg=t["bg"])
        self.draw_icon()
        self.draw_labels()
        self.draw_surface()
        self.draw_side()
        self.draw_buttons()

    def draw_icon(self):
        import math
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
                r = math.radians(a)
                self.c.create_line(cx+9*math.cos(r), cy+9*math.sin(r), cx+13*math.cos(r), cy+13*math.sin(r),
                                   fill=t["fg"], width=2, tags="static")

    def draw_labels(self):
        t = self.t()
        self.c.create_text(20, 26, anchor="w", text="✍  Сборщик датасета",
                           font=("Arial", 17, "bold"), fill=t["fg"], tags="labels")
        if self.char_i < len(CHARS):
            ch = CHARS[self.char_i]
            self.c.create_text(20, 62, anchor="w", text=f"Нарисуй символ:  {ch}",
                               font=("Arial", 22, "bold"), fill=t["fg"], tags="labels")
            self.c.create_text(20, 88, anchor="w",
                               text=f"образец {count_for(ch)+1}/{SAMPLES_PER_CHAR}   •   "
                                    f"всего {sum(count_for(c) for c in CHARS)}/{len(CHARS)*SAMPLES_PER_CHAR}",
                               font=("Arial", 10), fill=t["muted"], tags="labels")
        else:
            self.c.create_text(20, 62, anchor="w", text="Датасет готов! 🎉",
                               font=("Arial", 22, "bold"), fill=t["fg"], tags="labels")

    def draw_surface(self):
        t = self.t()
        x1, y1, x2, y2 = self.surf
        photo, m = panel_img(x2-x1, y2-y1, 22, tint(t["panel"], 0.0), shade(t["panel"], 0.05),
                             border=t["border"], shadow=12)
        self.c.create_image(x1-m, y1-m, anchor="nw", image=photo, tags="static")
        self.redraw_ink()

    def redraw_ink(self):
        t = self.t()
        self.c.delete("ink")
        k = (self.surf[2]-self.surf[0]) / OFF
        for x1, y1, x2, y2 in self.ink.strokes:
            self.c.create_line(self.surf[0]+x1*k, self.surf[1]+y1*k, self.surf[0]+x2*k, self.surf[1]+y2*k,
                               width=max(2, BRUSH*k), fill=t["ink"], capstyle="round",
                               joinstyle="round", tags="ink")

    def draw_side(self):
        t = self.t()
        x1, y1, x2, y2 = self.prev_rect
        photo, m = panel_img(x2-x1, y2-y1, 16, tint(t["panel"], 0.0), shade(t["panel"], 0.05),
                             border=t["border"], shadow=8)
        self.c.create_image(x1-m, y1-m, anchor="nw", image=photo, tags="static")
        self.update_preview()
        done = count_for(CHARS[self.char_i]) / SAMPLES_PER_CHAR if self.char_i < len(CHARS) else 1
        total = sum(count_for(c) for c in CHARS) / (len(CHARS)*SAMPLES_PER_CHAR)
        for rect, frac in ((self.bar_rect, done), (self.bar2_rect, total)):
            bx1, by1, bx2, by2 = rect
            tr, tm = panel_img(bx2-bx1, by2-by1, 6, shade(t["bg"], 0.10), shade(t["bg"], 0.10), shadow=0)
            self.c.create_image(bx1-tm, by1-tm, anchor="nw", image=tr, tags="static")
            fw = max(12, int((bx2-bx1) * frac))
            fr, fm = panel_img(fw, by2-by1, 6, tint(t["accent"], 0.15), shade(t["accent"], 0.10), shadow=0)
            self.c.create_image(bx1-fm, by1-fm, anchor="nw", image=fr, tags="static")

    def update_preview(self):
        norm = normalize(self.ink.off)
        img = Image.new("L", (28, 28), 0) if norm is None else norm
        self.preview_photo = ImageTk.PhotoImage(img.resize((140, 140), Image.NEAREST))
        x1, y1 = self.prev_rect[0] + 15, self.prev_rect[1] + 15
        self.c.create_image(x1, y1, anchor="nw", image=self.preview_photo, tags="preview")

    def draw_buttons(self):
        t = self.t()
        self.c.delete("btns")
        for i, b in enumerate(self.buttons):
            x1, y1, x2, y2 = b["rect"]
            hov = self.hover == i
            if b["style"] == "accent":
                top = tint(t["accent"], 0.28 if hov else 0.12)
                bot = shade(t["accent"], 0.05 if hov else 0.10)
                fg, border = t["accent_fg"], t["accent"]
                font = ("Arial", 12, "bold")
            else:
                base = t["hover"] if hov else t["btn"]
                top, bot = tint(base, 0.03), shade(base, 0.06)
                fg, border = t["btn_fg"], t["border"]
                font = ("Arial", 12)
            photo, m = panel_img(x2-x1, y2-y1, 14, top, bot, border=border, shadow=6)
            self.c.create_image(x1-m, y1-m, anchor="nw", image=photo, tags="btns")
            self.c.create_text((x1+x2)/2, (y1+y2)/2, text=b["label"], fill=fg, font=font, tags="btns")

    #*события
    def hit(self, x, y):
        if self.theme_rect[0] <= x <= self.theme_rect[2] and self.theme_rect[1] <= y <= self.theme_rect[3]:
            return "theme"
        for i, b in enumerate(self.buttons):
            x1, y1, x2, y2 = b["rect"]
            if x1 <= x <= x2 and y1 <= y <= y2: return i
        if self.surf[0] <= x <= self.surf[2] and self.surf[1] <= y <= self.surf[3]: return "surf"
        return None

    def to_off(self, x, y):
        k = (self.surf[2]-self.surf[0]) / OFF
        return ((x-self.surf[0])/k, (y-self.surf[1])/k)

    def on_press(self, e):
        h = self.hit(e.x, e.y)
        if h == "theme":
            self.theme = "dark" if self.theme == "light" else "light"
            self.draw_all()
        elif isinstance(h, int):
            self.buttons[h]["action"]()
        elif h == "surf":
            self.drawing = True
            self.prev_pt = self.to_off(e.x, e.y)

    def on_drag(self, e):
        if not self.drawing: return
        ox, oy = self.to_off(e.x, e.y)
        ox = max(0, min(OFF-1, ox)); oy = max(0, min(OFF-1, oy))
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
                self.redraw_ink(); self.update_preview()
        self.prev_pt = (ox, oy)

    def on_move(self, e):
        h = self.hit(e.x, e.y)
        nh = h if isinstance(h, int) else None
        if nh != self.hover:
            self.hover = nh
            self.draw_buttons()
        self.c.configure(cursor="hand2" if nh is not None or h == "theme"
                         else "circle" if (h == "surf" and self.tool == "eraser")
                         else "cross" if h == "surf" else "")

    def toggle_tool(self):
        self.tool = "eraser" if self.tool == "pen" else "pen"
        for b in self.buttons:
            if b["id"] == "tool": b["label"] = "🧽 Ластик" if self.tool == "pen" else "✏️ Перо"
        self.draw_buttons()

    def save(self):
        if self.char_i >= len(CHARS): return
        norm = normalize(self.ink.off)
        if norm is None:
            print("SAVE: пусто!")
            return
        ch = CHARS[self.char_i]
        folder = os.path.join(ROOT, ch)
        os.makedirs(folder, exist_ok=True)
        path = free_path(folder)
        try:
            tmp = path + ".tmp"
            norm.save(tmp, format="PNG")
            os.replace(tmp, path)
        except Exception as e:
            print("SAVE ERROR:", type(e).__name__, e)
            return
        self.last_path = path
        print(f"SAVE ok: {path}   count={count_for(ch)}")
        self.clear_ink()
        if count_for(ch) >= SAMPLES_PER_CHAR:
            self.char_i = next_incomplete(self.char_i)
        self.draw_all()

    def undo(self):
        if not self.last_path or not os.path.exists(self.last_path): return
        os.remove(self.last_path)
        ch = os.path.basename(os.path.dirname(self.last_path))
        self.last_path = None
        if self.char_i >= len(CHARS) or CHARS[self.char_i] != ch:
            self.char_i = CHARS.index(ch)
        self.draw_all()

    def skip_char(self):
        self.char_i = next_incomplete(self.char_i + 1)
        self.clear_ink()
        self.draw_all()

    def clear_ink(self):
        self.ink.clear()
        self.prev_pt = None
        self.drawing = False

root = tk.Tk()
Collector(root)
root.mainloop()