"""方向稿指标：python3 -I 指标.py a.pdf [b.pdf ...]
输出：页数、字号种数、最小字号、正文行空、标题/正文比、英文最长行字符数、中文最长行字数、描边框数、半格基线对齐率。"""
import pymupdf, sys, collections
MM = 25.4 / 72; TOP = 16 / MM
def cjk(c): return '　' <= c <= '鿿' or '＀' <= c <= '￯'
def run(path):
    d = pymupdf.open(path); sizes = collections.Counter(); en = []; zh = []; frames = 0; offs = collections.Counter(); pitch = []
    for p in d:
        lines = []
        for b in p.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                sp = [s for s in l["spans"] if s["text"].strip()]
                if not sp: continue
                for s in sp: sizes[round(s["size"], 1)] += len(s["text"].strip())
                t = "".join(s["text"] for s in sp); y = sp[0]["origin"][1]
                lines.append((round(y, 1), sp[0]["bbox"][0], max(s["size"] for s in sp), t))
                n = sum(cjk(c) for c in t)
                if n == 0 and len(t) > 30: en.append(len(t))
                elif n > 10: zh.append(n + (len(t) - n) / 2)
                if 11.5 <= sp[0]["size"] <= 14.5: offs[round((y - TOP) % 10.5, 1)] += 1
        lines.sort()
        for a, c in zip(lines, lines[1:]):
            if abs(a[1] - c[1]) < 2 and 11.5 <= a[2] <= 12.5 and 11.5 <= c[2] <= 12.5 and 0 < c[0] - a[0] < 30: pitch.append(c[0] - a[0])
        frames += sum(1 for g in p.get_drawings() if g["type"] in ("s", "fs") and g["rect"].width > 100 and g["rect"].height > 20)
    body = max(sizes, key=sizes.get); top = max(sizes)
    mode = offs.most_common(1)[0][0]; ok = sum(v for k, v in offs.items() if min(abs(k - mode), 10.5 - abs(k - mode)) <= 0.6)
    pmin = min(pitch) if pitch else 0
    return dict(页数=len(d), 字号种数=len(sizes), 最小字号=min(sizes), 正文字号=body, 正文行空mm=round((pmin - body) * MM, 2),
                标题正文比=round(top / body, 2), 英文最长行=max(en) if en else 0, 中文最长行=round(max(zh)) if zh else 0,
                描边框=frames, 半格对齐率=f"{ok * 100 // sum(offs.values())}%")
rows = {p.rsplit("/", 1)[-1]: run(p) for p in sys.argv[1:]}
keys = list(next(iter(rows.values())))
print("| 指标 | " + " | ".join(rows) + " |"); print("|---" * (len(rows) + 1) + "|")
for k in keys: print(f"| {k} | " + " | ".join(str(r[k]) for r in rows.values()) + " |")
