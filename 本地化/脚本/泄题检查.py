"""段考：讲解或要点里出现练一练原句（答案连同题干前后词，≥3 词）→ 列出。用法: python3 -I 本地化/脚本/泄题检查.py 本地化/内容 [册名片段...]"""
import json, re, sys, glob, os
D = sys.argv[1]
def norm(s): return re.sub(r'[^a-z0-9\' ]+', ' ', re.sub(r'\[_|_\]|\*\*|\[\[|\]\]', '', s.lower())).split()
def has(seq, sub):
    n=len(sub); return n>0 and any(seq[i:i+n]==sub for i in range(len(seq)-n+1))
files = sorted(glob.glob(os.path.join(D,'段考-*.定稿.json')))
files = [f for f in files if '样' not in f and (len(sys.argv)<3 or any(a in f for a in sys.argv[2:]))]
tot=0
for f in files:
    d=json.load(open(f)); k=0; out=[]
    for t in d['topics']:
        ex=' '.join([e.get('text','')+' '+' '.join(e.get('lines',[])) for e in t['explain'] if e['type']!='gloss']+[t.get('keypoint','')])
        ew=norm(ex)
        for i,dr in enumerate(t['drill'],1):
            k+=1
            st=dr['stem'].split('\n')[-1]
            if '___' not in st: continue
            first=re.split(r'\s*/\s*', re.sub(r'\([^)]*\)','',dr['ans']))[0]
            a,_,b=st.partition('___')
            L=norm(a)[-1:]; R=norm(re.sub(r'^\s*\([^)]*\)','',b))[:1]
            aw=norm(first)
            if not aw: continue
            for ctx in (L+aw+R, L+aw, aw+R):
                if len(ctx)>=3 and has(ew,ctx):
                    out.append(f"  {t['name']} 练一练[{i}]（全册第 {k} 题）：{' '.join(ctx)}"); break
    if out:
        print(os.path.basename(f), len(out)); print('\n'.join(out)); tot+=len(out)
print('合计', tot)
