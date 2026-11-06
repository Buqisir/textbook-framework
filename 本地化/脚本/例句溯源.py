"""讲解里的英文例句是否出自东莞原题。

逐册取讲解文字（段考：explain 的 p / pattern / note / gloss、keypoint；同步：短语、句式、词族的说明文字，不含原题本身），
抽出 ≥4 词的英文片段，到题库（题干填入答案后、原题干、改写后的句子）里找连续出现的位置。
找不到的列出，供人工换成本册例题或东莞原题。

用法: python3 -I 本地化/脚本/例句溯源.py [册名片段...]
"""
import json, re, sys, glob, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT = os.path.join(ROOT, '内容')

# 句型占位词：片段里有这些，说明是结构公式而不是例句
PLACEHOLDER = re.compile(r"\b(sb|sth|sb\.|sth\.|adj|adv|n|v|do|doing|done|to do|be done|prep|whoever|主语|谓语)\b\.?|[|…<>]|\.\.\.", re.I)
EN_SPAN = re.compile(r"[A-Za-z][A-Za-z'’\-]*(?:[ ,]+[A-Za-z][A-Za-z'’\-]*){3,}[.!?]?")


def norm(s):
    s = re.sub(r'\[_|_\]|\*\*|\[\[|\]\]|<[^>]+>', '', s.lower()).replace('’', "'")
    return re.sub(r"[^a-z0-9' ]+", ' ', s).split()


def contains(seq, sub):
    n = len(sub)
    return any(seq[i:i + n] == sub for i in range(len(seq) - n + 1))


def corpus():
    """题库每题生成若干候选句：答案填回空格（每种写法各一句）、原题干去空格。"""
    out = []
    for line in open(os.path.join(ROOT, '数据', '题库.jsonl'), encoding='utf-8'):
        q = json.loads(line)
        stem = q.get('题干') or ''
        ans = q.get('答案') or ''
        parts = [p.strip() for p in re.split(r'[；;]', ans)]
        stem = re.sub(r'\([^)]*\)|（[^）]*）', ' ', stem)
        variants = []
        # 每空的第一种写法、以及整题答案按 / 拆开的各写法
        firsts = [re.split(r'\s*/\s*', p)[0] for p in parts]
        variants.append(firsts)
        if len(parts) == 1 and '/' in parts[0]:
            variants += [[v] for v in re.split(r'\s*/\s*', parts[0])[1:]]
        for v in variants:
            s, it = stem, iter(v)
            s = re.sub(r'_{2,}', lambda m: ' ' + next(it, '') + ' ', s)
            out.append((q['id'], norm(s)))
        out.append((q['id'], norm(re.sub(r'_{2,}', ' ', stem))))
        if q.get('解析'):
            out.append((q['id'], norm(q['解析'])))
    return out


def lcs(a, b):
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0]
        for j, y in enumerate(b):
            cur.append(prev[j] + 1 if x == y else max(prev[j + 1], cur[j]))
        prev = cur
    return prev[-1]


def nearest(C, w):
    best = (0, None)
    ws = set(w)
    for qid, c in C:
        if len(ws & set(c)) < 0.6 * len(w):
            continue
        r = lcs(w, c) / len(w)
        if r > best[0]:
            best = (r, qid)
    return best


def spans(text):
    for m in EN_SPAN.finditer(text or ''):
        s = m.group(0).strip(' ,')
        if PLACEHOLDER.search(s):
            # 公式里夹着的整句（如 “，如 The school, where …”）只取占位词之前的部分
            s = PLACEHOLDER.split(s)[0].strip(' ,')
        if len(norm(s)) >= 4:
            yield s


def duankao_texts(d):
    for t in d['topics']:
        for e in t['explain']:
            if e['type'] == 'subhead':
                continue
            for s in [e.get('text', '')] + e.get('lines', []):
                yield t['name'], e['type'], s
        yield t['name'], 'keypoint', t.get('keypoint', '')


def tongbu_texts(d):
    for u in d['单元']:
        where = u['h2']
        for f in u.get('families', []):
            for k, v in f.items():
                if isinstance(v, str) and k not in ('词头',):
                    yield where, f'词族 {f["词头"]}', v
        for p in u.get('phrases', []):
            yield where, f'短语 {p["短语"]}', p.get('gloss', '')
        for t in u.get('tricks', []):
            for k in ('gloss', 'formula', 'note'):
                yield where, f'句式 {t["句式"]}', t.get(k, '')


def main():
    C = corpus()
    flt = sys.argv[1:]
    files = sorted(glob.glob(os.path.join(CONTENT, '*.定稿.json')))
    files = [f for f in files if '样' not in f and (not flt or any(a in f for a in flt))]
    total = 0
    for f in files:
        d = json.load(open(f, encoding='utf-8'))
        gen = tongbu_texts(d) if '单元' in d else duankao_texts(d)
        rows = []
        for where, kind, text in gen:
            for s in spans(text):
                w = norm(s)
                if any(contains(c, w) for _, c in C):
                    continue
                r, qid = nearest(C, w)
                tag = f'近似 {qid} {r:.0%}' if r >= 0.75 else '未见'
                rows.append(f'  [{tag}] {where} · {kind}：{s}')
        if rows:
            print(os.path.basename(f), len(rows))
            print('\n'.join(rows))
            total += len(rows)
    print('合计', total)


if __name__ == '__main__':
    main()
