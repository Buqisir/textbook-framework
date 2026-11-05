import pymupdf as fitz, sys, re, collections, statistics as st, json
doc = fitz.open(sys.argv[1])
PT2MM = 25.4/72
def isCJK(c): return '　' <= c <= '鿿' or '＀' <= c <= '￯'
rows=[]
for pno,page in enumerate(doc,1):
    d=page.get_text("dict")
    for b in d["blocks"]:
        for l in b.get("lines",[]):
            spans=[s for s in l["spans"] if s["text"].strip()]
            if not spans: continue
            txt="".join(s["text"] for s in spans)
            x0=min(s["bbox"][0] for s in spans); x1=max(s["bbox"][2] for s in spans)
            rows.append(dict(p=pno,x0=round(x0,1),x1=round(x1,1),y=round(spans[0]["origin"][1],1),
              txt=txt,fonts=sorted({s["font"] for s in spans}),sizes=sorted({round(s["size"],2) for s in spans}),
              color=sorted({'#%06x'%s["color"] for s in spans})))
# 1. font/size inventory (by char count)
inv=collections.Counter()
for p in doc:
    for b in p.get_text("dict")["blocks"]:
        for l in b.get("lines",[]):
            for s in l["spans"]:
                inv[(s["font"],round(s["size"],2),'#%06x'%s["color"])]+=len(s["text"].strip())
print("== 字体×字号×颜色（按字符数）")
for k,v in inv.most_common(40): print(f"{v:6d}  {k[0]:28s} {k[1]:6.2f}pt  {k[2]}")
# 2. measure: full-width lines (width > 150mm) — characters per line
print("\n== 行长（宽度>140mm 的行）")
en=[];zh=[]
for r in rows:
    w=(r["x1"]-r["x0"])*PT2MM
    if w<140: continue
    t=r["txt"]; ncjk=sum(isCJK(c) for c in t); nlat=len(t)-ncjk
    if ncjk==0 and nlat>40: en.append((len(t),round(w),r["p"],t[:60]))
    elif ncjk>20: zh.append((ncjk+nlat/2,round(w),r["p"],t[:30]))
print("英文行 字符数:",sorted(x[0] for x in en))
for x in en[:6]: print("  ",x)
print("中文行 等效字数:",sorted(round(x[0]) for x in zh))
# 3. left axes
print("\n== 左缘起点 x(mm)（每页去重, 出现≥2次）")
for pno in range(1,len(doc)+1):
    c=collections.Counter(round(r["x0"]*PT2MM,1) for r in rows if r["p"]==pno)
    print(pno, sorted((k,v) for k,v in c.items() if v>=2))
# 4. baseline deltas (consecutive lines, same page, overlapping x)
print("\n== 相邻行基线距（pt），频次")
dl=collections.Counter()
for pno in range(1,len(doc)+1):
    ys=sorted({r["y"] for r in rows if r["p"]==pno and 40<r["y"]<800})
    for a,b in zip(ys,ys[1:]): dl[round(b-a,1)]+=1
print(sorted(dl.items()))
# 5. page fill: lowest text baseline (excluding footer)
print("\n== 每页正文最低基线 y(mm)/297")
for pno in range(1,len(doc)+1):
    ys=[r["y"] for r in rows if r["p"]==pno and r["y"]<800]
    print(pno, round(max(ys)*PT2MM,1))
# 6. drawings inventory
print("\n== 矢量图形：线宽×颜色")
dc=collections.Counter()
for p in doc:
    for g in p.get_drawings():
        col=g.get("color") or g.get("fill")
        hexc='#%02x%02x%02x'%tuple(int(c*255) for c in col[:3]) if col else None
        dc[(g["type"],round(g.get("width") or 0,2),hexc)]+=1
for k,v in dc.most_common(30): print(v,k)
json.dump(rows,open(sys.argv[2],'w'),ensure_ascii=False)
