import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from char_model import CharNet, CHAR_MAP
from PIL import Image

model = CharNet(len(CHAR_MAP))
model.load_state_dict(torch.load("chars_model.pth", weights_only=True))
model.eval()

te = transforms.Compose([transforms.ToTensor()])
test_set = datasets.EMNIST("data", split="balanced", train=False, transform=te)
loader = DataLoader(test_set, batch_size=256)

correct = 0
with torch.no_grad():
    for x, y in loader:
        correct += (model(x).argmax(1) == y).sum().item()
print(f"Точность на тесте EMNIST: {correct/len(test_set):.4f}\n")

def ascii_art(t):
    chars = " .:-=+*#%@"
    return "\n".join("".join(chars[int(v*9.99)] for v in row) for row in t)

bx, by = next(iter(loader))
with torch.no_grad():
    preds = model(bx[:8]).argmax(1)
for i in range(8):
    print(f"истина: {CHAR_MAP[by[i]]}   ответ модели: {CHAR_MAP[preds[i]]}")
    print(ascii_art(bx[i][0]))
    print()
for i in range(8):
    arr = (bx[i][0].numpy() * 255).astype('uint8')
    Image.fromarray(arr).resize((224, 224), Image.NEAREST).save(f"sample_{i}.png")