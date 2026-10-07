import os
from PIL import Image

ROOT = "dataset"
BAD_DIR = "dataset_faild"

good = bad = 0
for ch in sorted(os.listdir(ROOT)):
    folder = os.path.join(ROOT, ch)
    if not os.path.isdir(folder):
        continue
    for f in sorted(os.listdir(folder)):
        if not f.lower().endswith(".png"):
            continue
        path = os.path.join(folder, f)
        try:
            with Image.open(path) as img:
                img.load()
            good += 1
        except Exception as e:
            bad += 1
            print(f"БИТАЯ: {path}  ({e})")
            os.makedirs(BAD_DIR, exist_ok=True)
            os.replace(path, os.path.join(BAD_DIR, f"{ch}_{f}"))

print(f"Годных: {good}, битых убрано в {BAD_DIR}: {bad}")