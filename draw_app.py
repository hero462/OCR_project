import os
import tkinter as tk
import torch
import numpy as np
from PIL import Image
from char_model import CharNet, CHAR_MAP
from ui_kit import THEMES, tint, shade, panel_img, InkModel

MODEL_PATH = "chars_model_mine.pth" if os.path.exists("chars_model_mine.pth") else "chars_model.pth"
RU_MAP = {'A':'А','B':'В','C':'С','E':'Е','H':'Н','K':'К','M':'М','O':'О','P':'Р','T':'Т','X':'Х','Y':'У'}
OFF_W, OFF_H = 360, 170
SCALE = 2
SPACE_GAP, LINE_GAP = 16, 6
BRUSH_OFF, ERASE_R = 6, 9
MIN_W, MIN_H = 720, 640

model = CharNet(len(CHAR_MAP))
model.load_state_dict(torch.load(MODEL_PATH, weights_only=True))
model.eval()

def char_tensor(piece):
    k = 20 / max(piece.size)
    ink = piece.resize((max(1, round(piece.width*k)), max(1, round(piece.height*k))), Image.LANCZOS)
    f = Image.new("L", (28, 28), 0)
    f.paste(ink, ((28-ink.width)//2, (28-ink.height)//2))
    return torch.from_numpy(np.array(f, dtype=np.float32)/255.0).view(1, 1, 28, 28)

def tta_probs(piece):
    with torch.no_grad():
        p = torch.softmax(model(char_tensor(piece)), dim=1)
        p = p + torch.softmax(model(char_tensor(piece.rotate(6, fillcolor=0))), dim=1)
        p = p + torch.softmax(model(char_tensor(piece.rotate(-6, fillcolor=0))), dim=1)
    return p / 3.0

def line_bands(arr):
    rows = (arr > 0).any(axis=1)
    raw, y, n = [], 0, len(rows)
    while y < n:
        if rows[y]:
            y0 = y
            while y < n and rows[y]: y += 1
            raw.append([y0, y])
        else: y += 1
    merged = []
    for b in raw:
        if merged and b[0] - merged[-1][1] < LINE_GAP: merged[-1][1] = b[1]
        else: merged.append(b)
    out, i = [], 0
    while i < len(merged):
        b = merged[i]
        if (b[1]-b[0]) <= 8 and i+1 < len(merged):
            nxt = merged[i+1]
            cc = (arr[b[0]:b[1]] > 0).any(axis=0); cn = (arr[nxt[0]:nxt[1]] > 0).any(axis=0)
            if (cc & cn).any():
                out.append([b[0], nxt[1]]); i += 2; continue
        out.append(b); i += 1
    return [b for b in out if b[1]-b[0] >= 3]

def segment_chars(line_img):
    cols = (np.array(line_img) > 0).any(axis=0)
    segs, x, n = [], 0, len(cols)
    while x < n:
        if cols[x]:
            x0 = x
            while x < n and cols[x]: x += 1
            segs.append(("char", x0, x))
        else:
            x0 = x
            while x < n and not cols[x]: x += 1
            if segs and (x-x0) >= SPACE_GAP and x < n: segs.append(("space",))
    return segs

def best_hypothesis(piece):
    if piece.height < 8 or piece.width <= 1.0*piece.height: return [piece]
    q = piece.width // 4
    mid = np.array(piece).sum(axis=0)[q:piece.width-q]
    if len(mid) == 0: return [piece]
    cut = q + int(mid.argmin())
    halves = []
    for x0, x1 in ((0, cut), (cut, piece.width)):
        p = piece.crop((x0, 0, x1, piece.height))
        bbox = p.getbbox()
        if not bbox: return [piece]
        p = p.crop(bbox)
        if p.width < 2 or p.height < 2: return [piece]
        halves.append(p)
    cw = tta_probs(piece).max().item()
    cs = 1.0
    for p in halves: cs *= tta_probs(p).max().item()
    return halves if cs > cw else [piece]

def recognize_page(off):
    lines = []
    for y0, y1 in line_bands(np.array(off)):
        li = off.crop((0, y0, off.width, y1))
        out, pieces, slots = [], [], []
        for s in segment_chars(li):
            if s[0] == "space": out.append(" "); continue
            strip = li.crop((s[1], 0, s[2], li.height))
            bbox = strip.getbbox()
            if not bbox: continue
            piece = strip.crop(bbox)
            if piece.width < 2 or piece.height < 2: continue
            for p in best_hypothesis(piece):
                pieces.append(p); out.append("?"); slots.append(len(out)-1)
        for i, slot in enumerate(slots):
            out[slot] = CHAR_MAP[tta_probs(pieces[i]).argmax().item()]
        line = "".join(out).strip()
        if line: lines.append(line)
    return "\n".join(lines)

class App:
    def __init__(self, root):
        self.root = root
        root.title("Персональный OCR")
        root.minsize(MIN_W, MIN_H)
        self.theme, self.kbd = "light", "EN"
        self.tool = "pen"
        self.ink = InkModel(OFF_W, OFF_H, BRUSH_OFF)
        self.result_lines = []
        self.drawing, self.prev_pt, self.hover = False, None, None
        self.c = tk.Canvas(root, highlightthickness=0)
        self.c.pack(fill="both", expand=True)
        self.c.bind("<ButtonPress-1>", self.on_press)
        self.c.bind("<B1-Motion>", self.on_drag)
        self.c.bind("<ButtonRelease-1>", lambda e: setattr(self, "prev_pt", None) or setattr(self, "drawing", False))
        self.c.bind("<Motion>", self.on_move)
        root.bind("<Return>", lambda e: self.run())
        root.bind("<Configure>", self.on_configure)
        self._after = None
        self.layout()
        self.draw_all()

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
        self.W, self.H, P, head, bh, gap, res_min = w, h, 20, 58, 44, 14, 110
        sw, sh = w - 2*P, 0
        sh = int(sw * OFF_H / OFF_W)
        cap = h - head - bh - res_min - 2*P - 2*gap - 8
        if sh > cap:
            sh = max(150, cap); sw = int(sh * OFF_W / OFF_H)
        x0 = (w - sw) // 2
        self.surf = (x0, head + 4, x0 + sw, head + 4 + sh)
        by = self.surf[3] + gap
        self.buttons, x = [], P
        specs = [("rec", "Распознать  (Enter)", "accent", self.run, 0.27),
                 ("clear", "Очистить", "panel", self.clear, 0.15),
                 ("layout", f"Раскладка: {self.kbd}", "panel", self.toggle_layout, 0.20),
                 ("tool", "🧽 Ластик", "panel", self.toggle_tool, 0.15)]
        for bid, label, style, action, frac in specs:
            bw = max(110, int((w - 2*P - 30) * frac))
            self.buttons.append(dict(id=bid, rect=(x, by, x+bw, by+bh), label=label,
                                     style=style, action=action))
            x += bw + 10
        self.theme_rect = (w-54, 12, w-18, 48)
        ry = by + bh + gap
        self.res_rect = (P, ry, w-P, max(ry + res_min, h - P))

    #*отрисовка
    def draw_all(self):
        t = self.t()
        self.c.delete("all")
        self.c.configure(bg=t["bg"])
        self.c.create_text(20, 30, anchor="w", text="✍  Рукописный ввод",
                           font=("Arial", 18, "bold"), fill=t["fg"], tags="static")
        self.c.create_text(self.W-70, 30, anchor="e", text=os.path.basename(MODEL_PATH),
                           font=("Arial", 8), fill=t["muted"], tags="static")
        self.draw_icon()
        self.draw_surface()
        self.draw_buttons()
        self.draw_result()

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
        kx = (self.surf[2]-self.surf[0]) / OFF_W
        ky = (self.surf[3]-self.surf[1]) / OFF_H
        for x1, y1, x2, y2 in self.ink.strokes:
            self.c.create_line(self.surf[0]+x1*kx, self.surf[1]+y1*ky,
                               self.surf[0]+x2*kx, self.surf[1]+y2*ky,
                               width=max(2, BRUSH_OFF*kx), fill=t["ink"],
                               capstyle="round", joinstyle="round", tags="ink")

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

    def draw_result(self):
        t = self.t()
        self.c.delete("restext")
        x1, y1, x2, y2 = self.res_rect
        photo, m = panel_img(x2-x1, y2-y1, 18, tint(t["result"], 0.0), shade(t["result"], 0.04),
                             border=t["border"], shadow=10)
        self.c.create_image(x1-m, y1-m, anchor="nw", image=photo, tags="static2")
        self.c.create_text(x1+16, y1+12, anchor="w", text="РЕЗУЛЬТАТ",
                           font=("Arial", 9, "bold"), fill=t["muted"], tags="restext")
        if not self.result_lines:
            self.c.create_text(x1+16, y1+34, anchor="w", text="…нарисуй текст и нажми Enter…",
                               font=("Arial", 13), fill=t["muted"], tags="restext")
            return
        max_lines = max(2, (y2-y1-40)//22)
        for i, line in enumerate(self.result_lines[:max_lines]):
            self.c.create_text(x1+16, y1+34+i*22, anchor="w", text=line,
                               font=("Arial", 15), fill=t["result_fg"], tags="restext")

    #*события
    def hit(self, x, y):
        if self.theme_rect[0] <= x <= self.theme_rect[2] and self.theme_rect[1] <= y <= self.theme_rect[3]:
            return "theme"
        for i, b in enumerate(self.buttons):
            x1, y1, x2, y2 = b["rect"]
            if x1 <= x <= x2 and y1 <= y <= y2: return i
        if self.surf[0] <= x <= self.surf[2] and self.surf[1] <= y <= self.surf[3]:
            return "surf"
        return None

    def to_off(self, x, y):
        kx = (self.surf[2]-self.surf[0]) / OFF_W
        ky = (self.surf[3]-self.surf[1]) / OFF_H
        return ((x-self.surf[0])/kx, (y-self.surf[1])/ky)

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
        ox = max(0, min(OFF_W-1, ox)); oy = max(0, min(OFF_H-1, oy))
        if self.tool == "pen":
            px, py = self.prev_pt
            self.ink.add_seg(px, py, ox, oy)
            kx = (self.surf[2]-self.surf[0]) / OFF_W
            ky = (self.surf[3]-self.surf[1]) / OFF_H
            t = self.t()
            self.c.create_line(self.surf[0]+px*kx, self.surf[1]+py*ky,
                               self.surf[0]+ox*kx, self.surf[1]+oy*ky,
                               width=max(2, BRUSH_OFF*kx), fill=t["ink"],
                               capstyle="round", joinstyle="round", tags="ink")
        else:
            if self.ink.erase_at(ox, oy, ERASE_R):
                self.redraw_ink()
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

    def toggle_layout(self):
        self.kbd = "RU" if self.kbd == "EN" else "EN"
        for b in self.buttons:
            if b["id"] == "layout": b["label"] = f"Раскладка: {self.kbd}"
        self.draw_buttons()

    def toggle_tool(self):
        self.tool = "eraser" if self.tool == "pen" else "pen"
        for b in self.buttons:
            if b["id"] == "tool": b["label"] = "🧽 Ластик" if self.tool == "pen" else "✏️ Перо"
        self.draw_buttons()

    def run(self):
        text = recognize_page(self.ink.off)
        if not text:
            self.result_lines = []
        else:
            if self.kbd == "RU":
                text = "".join(RU_MAP.get(c, c) for c in text)
            self.result_lines = text.split("\n")
            print("Распознано:\n" + text + "\n" + "-"*30)
        self.draw_result()

    def clear(self):
        self.ink.clear()
        self.result_lines = []
        self.redraw_ink()
        self.draw_result()

root = tk.Tk()
App(root)
root.mainloop()