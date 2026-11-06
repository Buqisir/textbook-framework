#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题干修订：按 本地化/数据/题干修订.tsv 改语料源头与定稿（2026-11-06 所有者定：题干语病、错字修正后再印）。

用法（仓库根目录）：
    python3 -I 本地化/脚本/题干修订.py          # 干跑：只报每条在语料、定稿里各命中几处
    python3 -I 本地化/脚本/题干修订.py --apply  # 写回

规则：
- 「改前」原样匹配；含 ___ 的片段在语料里另按「空格串」匹配（语料里的空位是一串空格）。
- 定稿 JSON 解析后改所有字符串值（题干、题干HTML、stem.text、答案、ans、answer_show、解析……），不碰键名。
- 幂等：「改后」里若包含「改前」（champion → championship），已改好的不会再改一遍。
- 定稿写回时沿用原文件的缩进。
修订后重跑 题库.py 与排版脚本。修订记录即 本地化/报告/病句/清单.md 与本 tsv。
"""
import json, re, sys, glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TSV = ROOT / '本地化/数据/题干修订.tsv'
CORPUS = sorted((ROOT / '语料/东莞单句语法').glob('*.md'))
FINALS = sorted(p for p in (ROOT / '本地化/内容').glob('*.定稿.json') if '-样.' not in p.name)   # 手样回放件不改


def rows():
    L = TSV.read_text(encoding='utf-8').splitlines()
    return [dict(zip(L[0].split('\t'), l.split('\t'))) for l in L[1:] if l.strip()]


# 语料里的空位：一串含 NBSP / 全角空格的空白，或下划线（与 题库.py 的 BLANK_RE 一致）
NB = '\xa0\u2003\u3000'
CORPUS_BLANK = r'[ \t%s]*(?:[%s][ \t%s]*|_+[ \t%s_]*)' % (NB, NB, NB, NB)


def corpus_pat(a):
    parts = [re.escape(p.strip(' ')) for p in a.split('___')]
    return re.compile(CORPUS_BLANK.join(parts)) if len(parts) > 1 else re.compile(re.escape(a))


def corpus_sub(b):
    # 改后里的 ___ 写回语料时用 NBSP 空位，题库.py 才认得
    return lambda m: re.sub(r' ?___ ?', ' \xa0\xa0\xa0 ', b)


TOKEN = '\x00已改\x00'


def safe_replace(t, a, b, cnt):
    """把 t 里的 a 换成 b，已经是 b 的地方不动。"""
    t = t.replace(b, TOKEN)
    cnt[0] += t.count(a)
    return t.replace(a, b).replace(TOKEN, b)


def walk(n, a, b, cnt):
    if isinstance(n, dict):
        return {k: walk(v, a, b, cnt) for k, v in n.items()}
    if isinstance(n, list):
        return [walk(v, a, b, cnt) for v in n]
    if isinstance(n, str) and a in n:
        return safe_replace(n, a, b, cnt)
    return n


def main(argv):
    apply = '--apply' in argv
    R = rows()
    texts = {p: p.read_text(encoding='utf-8') for p in CORPUS}
    finals = {p: json.loads(p.read_text(encoding='utf-8')) for p in FINALS}
    for r in R:
        a, b = r['改前'], r['改后']
        pat = corpus_pat(a)
        nc = 0
        done_pat = corpus_pat(b)
        for p, t in texts.items():
            held = []
            t = done_pat.sub(lambda m: held.append(m.group(0)) or TOKEN, t)
            k = len(pat.findall(t))
            if k:
                nc += k
                t = pat.sub(corpus_sub(b), t)
            for h in held:
                t = t.replace(TOKEN, h, 1)
            texts[p] = t
        nf = [0]
        blank = '<span class="blank"></span>'
        for p in finals:
            finals[p] = walk(finals[p], a, b, nf)
            if '___' in a:      # 同步定稿的 题干HTML 里空位是 span
                finals[p] = walk(finals[p], a.replace('___', blank), b.replace('___', blank), nf)
        print(f"{r['题号']:7} 语料 {nc} 定稿 {nf[0]}  {a[:50]}" + ('  （语料未命中）' if nc == 0 else ''))
    if apply:
        for p, t in texts.items():
            if t != p.read_text(encoding='utf-8'):
                p.write_text(t, encoding='utf-8')
        for p, d in finals.items():
            raw = p.read_text(encoding='utf-8')
            m = re.match(r'\{\n( +)', raw)
            new = json.dumps(d, ensure_ascii=False, indent=len(m.group(1)) if m else 2) + ('\n' if raw.endswith('\n') else '')
            if new != p.read_text(encoding='utf-8'):
                p.write_text(new, encoding='utf-8')
        print('已写回')


if __name__ == '__main__':
    main(sys.argv[1:])
