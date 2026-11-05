#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""进度反推：按卷统计单元命中，给出覆盖上界与考试节点，输出报告所需的表格（Markdown）。"""
import json
import re
import statistics
import sys
from collections import OrderedDict, defaultdict

DATA = '/home/user/textbook-framework/本地化/数据'
rows = [json.loads(l) for l in open(f'{DATA}/题库.jsonl', encoding='utf-8')]
mapping = {r['id']: r for r in rows}
hits = {json.loads(l)['id']: json.loads(l) for l in open(f'{DATA}/题-单元.jsonl', encoding='utf-8')}
units = json.load(open(f'{DATA}/单元.json', encoding='utf-8'))
SEQ = {u['序']: u for u in units}


def unit_label(seq, cross_book_from=None):
    u = SEQ[seq]
    return f"{u['册']} {u['单元']}"


def fmt_range(upper):
    """必修一 Welcome Unit–Unit 3 写法：起点为第 1 序，终点为上界。"""
    start = unit_label(1)
    end = SEQ[upper]
    if end['册'] == SEQ[1]['册']:
        return f"{start}–{end['单元']}"
    return f"{start}–{end['册']} {end['单元']}"


# ---------------- 节点判定
def infer_term(sem, fn_month):
    if sem in ('上', '下'):
        return sem
    if fn_month is None:
        return None
    return '上' if fn_month in (9, 10, 11, 12, 1) else '下'


def node_of(fn, rs):
    grade = rs[0]['年级']
    sem = rs[0]['学期']
    yuan = {r['考试原文'] for r in rs}
    m = re.search(r'(?<!\d)(\d{1,2})月', fn)
    mo = int(m.group(1)) if m else None
    term = infer_term(sem, mo)
    if term is None:
        return grade, '?', '学期未知', mo
    if '期末' in fn or any('期末' in y for y in yuan):
        cat = '期末'
    elif '期中' in fn or '中段' in fn or any('期中' in y or '中段' in y for y in yuan):
        cat = '期中'
    else:
        cat = '月考'
    if cat in ('期中', '期末'):
        return grade, term, cat, mo
    # 月考类：先看序号，再看月份
    if re.search(r'第一次|月考一|月考（一）|（一）|第一次段考', fn):
        sub = '第一次月考'
    elif re.search(r'第二次|第三次|月考二|月考（二）|（二）|（三）|学习效率检测', fn):
        sub = '第二次月考'
    elif mo is not None:
        if term == '上':
            sub = {9: '第一次月考', 10: '第一次月考', 12: '第二次月考', 1: '第二次月考'}.get(mo, '月考?')
        else:
            sub = {2: '第一次月考', 3: '第一次月考', 6: '第二次月考'}.get(mo, '月考?')
    elif '期初' in fn or any('期初' in y for y in yuan):
        sub = '第一次月考'
    else:
        sub = '月考?'
    return grade, term, sub, mo


# ---------------- 按卷聚合
files = OrderedDict()
for r in rows:
    files.setdefault(r['文件'], []).append(r)

file_recs = []
for fn, rs in files.items():
    grade, term, cat, mo = node_of(fn, rs)
    node = f"{grade}{term}·{cat}" if term != '?' else f"{grade}·{cat}"
    usable = [r for r in rs if '疑似非单句题' not in (r.get('标记') or [])]
    per_seq = defaultdict(int)
    hit_q = 0
    for r in usable:
        seqs = {h['序'] for h in hits[r['id']]['命中'] if h['唯一']}
        if seqs:
            hit_q += 1
        for s in seqs:
            per_seq[s] += 1
    total = sum(per_seq.values())
    # 覆盖上界
    x_a = max((s for s, c in per_seq.items() if c >= 2), default=None)
    x_c = None
    cum = 0
    for s in range(1, 37):
        cum += per_seq.get(s, 0)
        if total and cum / total >= 0.9:
            x_c = s
            break
    cands = [x for x in (x_a, x_c) if x is not None]
    upper = max(cands) if cands else None
    short = fn.replace('广东省东莞市', '').replace('广东东莞市', '').replace('广东省', '')
    short = re.sub(r'英语(试卷|试题|试卷|题)?(\.md)?$', '', short.replace('.md', ''))
    file_recs.append({
        'file': fn, 'short': short, 'grade': grade, 'term': term, 'cat': cat, 'node': node,
        'sub': cat, 'n_q': len(usable), 'hit_q': hit_q, 'upper': upper, 'x_a': x_a, 'x_c': x_c,
        'per_seq': dict(sorted(per_seq.items())), 'total': total, 'mo': mo,
    })

# 节点名（用于汇总）
def node_key(rec):
    cat = rec['cat']
    if cat in ('第一次月考', '第二次月考', '期中', '期末', '月考?'):
        return f"{rec['grade']}{rec['term']}·{cat}"
    return f"{rec['grade']}{rec['term']}·{cat}"

for rec in file_recs:
    rec['key'] = node_key(rec)


def quart(vals):
    vals = sorted(vals)
    if len(vals) < 2:
        return (vals[0], vals[0]) if vals else (None, None)
    q = statistics.quantiles(vals, n=4, method='inclusive')
    return q[0], q[2]


MIN_HITQ = 5   # 命中题数不足 5 的卷，上界不可靠，不纳入节点汇总


def conf(n_files, n_hits):
    if n_files >= 8 and n_hits >= 60:
        return '高'
    if n_files >= 4 and n_hits >= 25:
        return '中'
    return '低'


def summarize(recs):
    recs = [r for r in recs if r['hit_q'] >= MIN_HITQ and r['upper'] is not None]
    uppers = [r['upper'] for r in recs]
    if not uppers:
        return None
    med = statistics.median(uppers)
    q1, q3 = quart(uppers)
    med_i = int(med + 0.5)  # 中位数向上取整到序
    q1i, q3i = int(q1 + 0.5), int(q3 + 0.5)
    pooled = sorted(s for r in recs for s, c in r['per_seq'].items() for _ in range(c))
    return {
        'n_files': len(recs), 'n_hits': sum(r['hit_q'] for r in recs),
        'pooled_med': statistics.median(pooled) if pooled else None,
        'recs': recs,
        'median': med, 'med_i': med_i, 'q1': q1, 'q3': q3, 'q1i': q1i, 'q3i': q3i,
        'range': fmt_range(med_i), 'iqr_range': f"{fmt_range(q1i)} ～ {fmt_range(q3i)}",
        'conf': conf(len(recs), sum(r['hit_q'] for r in recs)),
    }


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'all'
    groups = defaultdict(list)
    for rec in file_recs:
        groups[rec['key']].append(rec)
    print('## 节点结论表')
    print('| 节点 | 卷数（纳入/总） | 命中题数 | 覆盖范围（中位上界） | 四分位范围（上界 Q1～Q3） | 命中序中位数 | 置信度 |')
    print('|---|---|---|---|---|---|---|')
    for k in sorted(groups, key=lambda x: (x.split('·')[0], x)):
        s = summarize(groups[k])
        if not s:
            continue
        print(f"| {k} | {s['n_files']}/{len(groups[k])} | {s['n_hits']} | {s['range']}（序 {s['median']:g}） | "
              f"{s['q1']:g}～{s['q3']:g}（{s['iqr_range']}） | {s['pooled_med']:g} | {s['conf']} |")
    print()
    print('## 偏离大的卷（上界与节点中位数相差 ≥10 序）')
    for k in sorted(groups):
        s = summarize(groups[k])
        if not s:
            continue
        for r in s['recs']:
            if abs(r['upper'] - s['median']) >= 10:
                print(f"- {k}：{r['short']}（上界 {r['upper']}，中位 {s['median']:g}）")
    print()
    print('## 逐卷附表')
    print('| # | 文件简称 | 节点 | 题数 | 命中题数 | 上界 | 90%点 | 2题上界 | 各单元命中（序:题数） |')
    print('|---|---|---|---|---|---|---|---|---|')
    for i, rec in enumerate(file_recs, 1):
        dist = ' '.join(f"{s}:{c}" for s, c in rec['per_seq'].items())
        up = SEQ[rec['upper']]['册'] + ' ' + SEQ[rec['upper']]['单元'] if rec['upper'] else '—'
        flag = '' if rec['hit_q'] >= MIN_HITQ else '（命中不足，不纳入）'
        print(f"| {i} | {rec['short']} | {rec['key']} | {rec['n_q']} | {rec['hit_q']}{flag} | "
              f"{rec['upper'] if rec['upper'] else '—'}（{up}） | {rec['x_c'] or '—'} | {rec['x_a'] or '—'} | {dist} |")
