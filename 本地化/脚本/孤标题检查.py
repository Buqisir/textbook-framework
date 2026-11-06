#!/usr/bin/env python3
"""渲染后自查：找出「页末只有标题」的页（所有者 2026-11-05：这种情况标题应换到下一页）。
用法：python3 -I 本地化/脚本/孤标题检查.py 渲染/本地化/_out/*.pdf；无输出即通过。需 pymupdf。"""
import pymupdf,sys
HEADS={'单元考情','词性转换','短语与句式转换','单元小测','答案与解析','练一练答案','练一练','句式转换','考情总览'}
for f in sys.argv[1:]:
    d=pymupdf.open(f)
    for i,p in enumerate(d):
        L=[]
        for b in p.get_text('dict')['blocks']:
            for l in b.get('lines',[]):
                t=''.join(s['text'] for s in l['spans']).strip()
                if t and l['bbox'][3]<780: L.append((round(l['bbox'][3]),t,max(s['size'] for s in l['spans'])))
        if not L: continue
        bottom=max(x[0] for x in L)
        last=[x for x in L if x[0]>=bottom-30]
        if any((x[1] in HEADS and x[2]>=12) or x[2]>=16 for x in last) and not any(x[2]>=12 and x[1] not in HEADS and len(x[1])>3 for x in last):
            print(f.split('/')[-1],'页',i+1,'页末是标题：',[x[1] for x in last])
