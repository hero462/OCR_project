import torch.nn as nn

CHAR_MAP = ("0123456789"
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            "БГДЁЖЗИЙЛПФЦЧШЩЪЫЬЭЮЯ"
            ".,:!?-+=/()@#%&*")

class CharNet(nn.Module):
    def __init__(self, num_classes=len(CHAR_MAP)):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(1, 32, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(32, 64, 3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
        )
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(3136, 256), nn.ReLU(),
            nn.Linear(256, num_classes),
        )

    def forward(self, x):
        return self.head(self.conv(x))