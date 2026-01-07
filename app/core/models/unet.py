import torch
import torch.nn as nn
import torch.nn.functional as F

class DoubleConv(nn.Module):
    """(convolution => [BN] => ReLU) * 2"""
    def __init__(self, in_channels, out_channels):
        super().__init__()
        self.double_conv = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_channels, out_channels, kernel_size=3, padding=1),
            nn.BatchNorm2d(out_channels),
            nn.ReLU(inplace=True)
        )

    def forward(self, x):
        return self.double_conv(x)

class UNet(nn.Module):
    """
    Standard U-Net architecture for Semantic Segmentation.
    """
    def __init__(self, n_channels, n_classes):
        super(UNet, self).__init__()
        self.n_channels = n_channels
        self.n_classes = n_classes
        self.bilinear = True
        self.inc = DoubleConv(n_channels, 64)
        self.down1 = DoubleConv(64, 128)
        self.down2 = DoubleConv(128, 256)
        self.down3 = DoubleConv(256, 512)
        factor = 2 if self.bilinear else 1
        self.down4 = DoubleConv(512, 1024 // factor)
        
        # MaxPool
        self.pool = nn.MaxPool2d(2)
        self.up1 = DoubleConv(1024, 512 // factor)
        self.up2 = DoubleConv(512, 256 // factor)
        self.up3 = DoubleConv(256, 128 // factor)
        self.up4 = DoubleConv(128, 64)
        self.outc = nn.Conv2d(64, n_classes, kernel_size=1)

    def forward(self, x):
        x1 = self.inc(x)
        x2 = self.down1(self.pool(x1))
        x3 = self.down2(self.pool(x2))
        x4 = self.down3(self.pool(x3))
        x5 = self.down4(self.pool(x4))
        
        # Upsampling
        x = self._up_block(x5, x4, self.up1)
        x = self._up_block(x, x3, self.up2)
        x = self._up_block(x, x2, self.up3)
        x = self._up_block(x, x1, self.up4)
        
        logits = self.outc(x)
        return logits

    def _up_block(self, x, x_skip, up_layer):
        x = F.interpolate(x, scale_factor=2, mode='bilinear', align_corners=True)
        # Pad if necessary to match x_skip
        diffY = x_skip.size()[2] - x.size()[2]
        diffX = x_skip.size()[3] - x.size()[3]
        x = F.pad(x, [diffX // 2, diffX - diffX // 2, diffY // 2, diffY - diffY // 2])
        
        x = torch.cat([x_skip, x], dim=1)
        return up_layer(x)
