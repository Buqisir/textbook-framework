"""段考聚焦专题：按 年级·学期·节点 统计各语法专题的试卷覆盖率。

专题标签来自 解析 关键词（正则），不是人工标注；只算单句类题（排除 单选、其他）。
输出：数据/段考专题.json、报告/段考专题.md
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from 节点 import NODES, papers  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TOPICS = [
    ('非谓语', r'非谓语|动名词|不定式|现在分词|过去分词'),
    ('it 形式主语／宾语', r'形式主语|形式宾语'),
    ('定语从句', r'定语从句'),
    ('名词性从句', r'宾语从句|主语从句|表语从句|同位语从句|名词性从句'),
    ('状语从句', r'状语从句'),
    ('强调句', r'强调句'),
    ('虚拟语气', r'虚拟'),
    ('倒装', r'倒装'),
    ('主谓一致', r'主谓一致|就近原则'),
    ('独立主格／with 复合', r'独立主格|with\s*复合|with的复合'),
    ('被动', r'被动'),
    ('时态', r'一般过去时|现在完成|过去完成|将来时|进行时'),
    ('情态动词', r'情态动词'),
    ('比较级', r'比较级|最高级'),
    ('省略', r'省略'),
    ('反意疑问', r'反意疑问|附加疑问'),
]

rows = [json.loads(l) for l in open(ROOT / '数据/题库.jsonl', encoding='utf-8')]
files = defaultdict(list)
for r in rows:
    files[r['文件']].append(r)

nodes = defaultdict(lambda: {'卷': [], '推定': [], '并卷': [], '题': 0, '专题': defaultdict(lambda: {'卷': set(), '题': []})})
for rep, members, g, t, n, guess in papers(rows):
    key = f'{g}{t}·{n}'
    nd = nodes[key]
    nd['卷'].append(rep)
    if guess:
        nd['推定'].append(rep)
    if len(members) > 1:
        nd['并卷'].append(members)
    seen = set()
    for f in members:
        for r in files[f]:
            if r['题型'] in ('单选', '其他'):
                continue
            dk = r['重复组'] if r['重复组'] is not None else r['id']
            if dk in seen:      # 同卷多份文件里的同一题只算一次
                continue
            seen.add(dk)
            nd['题'] += 1
            for name, pat in TOPICS:
                if re.search(pat, r['解析'] or ''):
                    nd['专题'][name]['卷'].add(rep)
                    nd['专题'][name]['题'].append(r['id'])


def order(k):
    gs = ['高一上', '高一下', '高二上', '高二下']
    head, _, n = k.partition('·')
    return (gs.index(head) if head in gs else 9, NODES.index(n) if n in NODES else 9)


out = {}
for k in sorted(nodes, key=order):
    nd = nodes[k]
    P = len(nd['卷'])
    out[k] = {
        '卷数': P, '推定卷数': len(nd['推定']), '题数': nd['题'],
        '卷': sorted(nd['卷']), '推定卷': sorted(nd['推定']), '并卷': nd['并卷'],
        '专题': {name: {'覆盖卷': len(nd['专题'][name]['卷']),
                       '覆盖率': round(len(nd['专题'][name]['卷']) / P, 2) if P else 0,
                       '题数': len(nd['专题'][name]['题']),
                       '题': nd['专题'][name]['题']}
                for name, _ in TOPICS},
    }
(ROOT / '数据/段考专题.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')

L = ['# 段考聚焦专题 · 试卷覆盖率', '',
     '每格：覆盖率（该节点有多少比例的卷考到这个专题）/ 题数。标签来自解析关键词，只算单句类题。',
     '节点规则见 `脚本/节点.py`；「推定」= 只能按月份推定期中前后的卷；同一份卷的多个文件（重复题 ≥80%）按一卷计。', '']
for g in ['高一上', '高一下', '高二上', '高二下']:
    ks = [f'{g}·{n}' for n in NODES if f'{g}·{n}' in out]
    if not ks:
        continue
    L.append(f'## {g}')
    L.append('')
    L.append('| 专题 | ' + ' | '.join(f"{k.split('·')[1]}（{out[k]['卷数']} 卷）" for k in ks) + ' |')
    L.append('|---' * (len(ks) + 1) + '|')
    for name, _ in TOPICS:
        cells = [f"{out[k]['专题'][name]['覆盖率']:.0%} / {out[k]['专题'][name]['题数']}" for k in ks]
        L.append(f'| {name} | ' + ' | '.join(cells) + ' |')
    L.append('')
    for k in ks:
        if out[k]['推定卷']:
            L.append(f"- {k} 推定卷：" + '；'.join(Path(f).stem for f in out[k]['推定卷']))
        for m in out[k]['并卷']:
            L.append(f"- {k} 同卷多文件，按一卷计：" + ' ＝ '.join(Path(f).stem for f in m))
    L.append('')
odd = [k for k in out if k.split('·')[1] not in NODES or k.startswith(('高一?', '高二?'))]
if odd:
    L.append('## 未归入节点')
    for k in odd:
        L.append(f"- {k}：" + '；'.join(Path(f).stem for f in out[k]['卷']))
(ROOT / '报告/段考专题.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
print('\n'.join(L))
