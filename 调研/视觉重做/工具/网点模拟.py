"""黑白激光打印模拟：PDF 页区域 → 600dpi 灰度 → 100 lpi 调幅网点（45° 圆点）→ 1-bit。
python3 -I 网点模拟.py in.pdf 页码 x0 y0 x1 y1(pt) out.png [放大倍数]"""
import sys, numpy as np, pymupdf
from PIL import Image
pdf, pno, x0, y0, x1, y1, out = sys.argv[1], int(sys.argv[2]), *map(float, sys.argv[3:7]), sys.argv[7]
zoom = int(sys.argv[8]) if len(sys.argv) > 8 else 2
pix = pymupdf.open(pdf)[pno - 1].get_pixmap(dpi=600, clip=pymupdf.Rect(x0, y0, x1, y1), colorspace=pymupdf.csGRAY)
g = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width).astype(float) / 255
# 45° 旋转的圆点网屏，网屏周期 6px@600dpi ≈ 100 lpi
yy, xx = np.mgrid[0:g.shape[0], 0:g.shape[1]].astype(float)
c, s = np.cos(np.pi / 4), np.sin(np.pi / 4); P = 6.0
u = ((xx * c + yy * s) % P) / P - 0.5; v = ((-xx * s + yy * c) % P) / P - 0.5
spot = (np.cos(2 * np.pi * u) + np.cos(2 * np.pi * v)) / 4 + 0.5     # 0..1，中心最大
ink = 1 - g                                                          # 0..1 墨量
bw = np.where(ink >= 0.995, 0, np.where(ink <= 0.005, 255, np.where(spot > 1 - ink, 0, 255))).astype(np.uint8)
im = Image.fromarray(bw)
if zoom > 1: im = im.resize((im.width * zoom // 3, im.height * zoom // 3), Image.NEAREST)
im.save(out)
