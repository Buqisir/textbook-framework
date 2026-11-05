"""方向稿生成：同一份 内容.html 套三套 CSS，输出 A/B/C.html（以及 -grid 调试版）。
用法：python3 -I 生成.py  → 再用 vivliostyle build 渲染。"""
import pathlib
here = pathlib.Path(__file__).parent
body = (here / "内容.html").read_text(encoding="utf-8")
for key, css, title in [("A", "A-柱.css", "方向 A · 柱式"), ("B", "B-对页.css", "方向 B · 对页单元"), ("C", "C-书页.css", "方向 C · 书页"), ("主线", "主线.css", "主线稿")]:
    if not (here / css).exists():
        continue
    for grid in (False, True):
        cls = ' class="grid"' if grid else ""
        html = f'<!DOCTYPE html>\n<html lang="zh-Hans"{cls}>\n<head><meta charset="UTF-8"><title>{title}</title><link rel="stylesheet" href="{css}"></head>\n<body>\n{body}\n</body>\n</html>\n'
        (here / f"{key}{'-grid' if grid else ''}.html").write_text(html, encoding="utf-8")
        print("wrote", key, grid)
