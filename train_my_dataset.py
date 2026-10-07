import os
import torch, torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from PIL import Image
from char_model import CharNet, CHAR_MAP

ROOT = "dataset"
EMNIST_MODEL = "chars_model.pth" #датасет EMNIST(не используется)
MODEL_OUT = "chars_model_mine.pth"
EPOCHS = 100
VAL_PER_CLASS = 10

torch.set_num_threads(os.cpu_count())

def is_good(path):
    try:
        with Image.open(path) as img:
            img.load()
        return True
    except Exception:
        return False

class MyDataset(Dataset):
    def __init__(self, root, transform=None, val=False):
        self.transform = transform
        self.samples = []
        for ch in sorted(os.listdir(root)):
            folder = os.path.join(root, ch)
            if not os.path.isdir(folder) or ch not in CHAR_MAP:
                continue
            label = CHAR_MAP.index(ch)
            files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".png"))
            if val:
                files = files[-VAL_PER_CLASS:]
            elif len(files) > VAL_PER_CLASS:
                files = files[:-VAL_PER_CLASS]
            pairs = [(os.path.join(folder, f), label) for f in files]
            self.samples += [(p, l) for p, l in pairs if is_good(p)]

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, i):
        path, label = self.samples[i]
        img = Image.open(path).convert("L")
        if self.transform:
            img = self.transform(img)
        return img, label

tr = transforms.Compose([
    transforms.RandomRotation(10, fill=0),
    transforms.RandomAffine(degrees=0, translate=(0.1, 0.1), scale=(0.85, 1.15), fill=0),
    transforms.ToTensor(),
])
te = transforms.Compose([transforms.ToTensor()])

train_set = MyDataset(ROOT, tr)
val_set = MyDataset(ROOT, te, val=True)
print(f"Твоих образцов: train {len(train_set)}, val {len(val_set)}")
if len(train_set) == 0:
    raise SystemExit("Датасет пуст! Сначала: python collect_dataset.py")

model = CharNet(len(CHAR_MAP))
if os.path.exists(MODEL_OUT):
    model.load_state_dict(torch.load(MODEL_OUT, weights_only=True))
    lr = 0.0003
    print(f"🔄 Продолжаем обучение личной модели ({MODEL_OUT})")
elif os.path.exists(EMNIST_MODEL):
    model.load_state_dict(torch.load(EMNIST_MODEL, weights_only=True), strict=False)
    lr = 0.001
    print(f"🧠 Старт с базы EMNIST ({EMNIST_MODEL})")
else:
    lr = 0.001
    print("⚠️ Базы нет — обучение с нуля")

opt = torch.optim.Adam(model.parameters(), lr=lr)
criterion = nn.CrossEntropyLoss()
train_loader = DataLoader(train_set, batch_size=32, shuffle=True)
val_loader = DataLoader(val_set, batch_size=128)

def evaluate():
    model.eval()
    correct = 0
    with torch.no_grad():
        for x, y in val_loader:
            correct += (model(x).argmax(1) == y).sum().item()
    return correct / max(1, len(val_set))

best_acc = evaluate()                                            #*точность
print(f"Стартовая точка: val acc = {best_acc:.4f}")

for epoch in range(EPOCHS):
    model.train()
    total = 0.0
    for x, y in train_loader:
        opt.zero_grad()
        loss = criterion(model(x), y)
        loss.backward()
        opt.step()
        total += loss.item()
    acc = evaluate()
    marker = ""
    if acc > best_acc:
        best_acc = acc
        torch.save(model.state_dict(), MODEL_OUT)
        marker = "   💾 новый рекорд, сохранено"
    print(f"Epoch {epoch+1}/{EPOCHS}  loss={total/len(train_loader):.4f}  "
          f"val acc: {acc:.4f}  (best {best_acc:.4f}){marker}")

print(f"\nГотово. Лучший val acc: {best_acc:.4f}, веса в {MODEL_OUT}")