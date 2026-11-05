#!/usr/bin/env python3
"""段考专题 · 选题（阶段 1）：读题库，为两册生成讲解候选。

运行：python3 -I 本地化/脚本/段考选题.py
输入：本地化/数据/题库.jsonl、本地化/数据/段考专题.json（只读）；节点判定用 本地化/脚本/节点.py
输出：本地化/内容/段考-高一上-期中前月考.候选.json、本地化/内容/段考-高一上-期中.候选.json

规则：
- 只取该节点的卷（节点.papers 判定，同卷多文件按一卷）；排除 题型 单选 / 其他、标记含「疑似非单句题」。
- 同 重复组 只留一题（标签最完整者）。
- 主考点：解析中第一处「考查」之后的文字里，TOPICS 中最先出现的专题；
  其后无命中（或无「考查」）时用全文首个命中，记为 主考点来源=全文。一题只进一个专题。
- 其他命中：全文解析里除主考点外的其他 TOPICS 命中。
- 某讲专题本节点候选不足 8 题，从高一上其他节点补，补的题加 借用节点。
  补位顺序：互补节点（期中 ↔ 期中前月考）→ 期中后月考 → 期末。
- cue：题干里括号内的改写 / 翻译指令剥离成 cue；通用指令（所给词的适当形式填空、汉译英……）直接删；
  词形提示（如 ___ (attract)、(申请)）留在题干。
- 子类：每题按 SUBCLASSES 正则取第一条命中，粗聚类，供统计，不影响入选。
- 疑似缺陷：题干无空位、括号不配对、重复词、英文句末省略号、乱码。启发式，判不出语义缺词。
- 平局排序里的题号（rank 中的 r['id']）由 本地化/数据/卷号.json 固定：题号前三位不随语料增删而漂移。
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from 节点 import papers  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / '本地化' / '数据'
OUT_DIR = ROOT / '本地化' / '内容'

# ── 册配置 ─────────────────────────────────────────────
GRADE, TERM = '高一', '上'
BOOKS = {
    '期中前月考': {
        'topics': ['非谓语', 'it 形式主语／宾语', '名词性从句', '虚拟语气', '强调句', '主谓一致'],
        'skip': ['定语从句', '状语从句'],          # 总表另列，不讲
        'donors': ['期中', '期中后月考', '期末'],   # 补位顺序：互补节点在前
    },
    '期中': {
        'topics': ['非谓语', 'it 形式主语／宾语', '定语从句', '状语从句', '名词性从句',
                   '强调句', '虚拟语气', '主谓一致', '倒装'],
        'skip': [],
        'donors': ['期中前月考', '期中后月考', '期末'],
    },
}
MIN_CAND = 8
EXCLUDE_TYPES = ('单选', '其他')

# 与 段考专题.py / 段考选题.py 保持一致（那边是脚本，不能 import）
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

# ── 子类：粗聚类，按顺序取第一条命中；未命中归「其他」 ──
SUBCLASSES = {
    '虚拟语气': [
        ('What if / 要是…会怎样', r'What if|What would happen|要是|要不是'),
        ('wish / if only', r'\bwish(es|ed)?\b|if only'),
        ('It is time / about time', r"It (is|was|'s) (high time|time|about time)|It is time"),
        ('recommend / suggest / insist 类 that 从句', r'recommend|suggest|insist|demand|advise|require|order|propose|建议'),
        ('if 虚拟条件句', r'\bif\b|\bwere\b|\bhad\s+\w+\s+(been|done)'),
    ],
    '强调句': [
        ('not until 强调', r'not until'),
        ('It is/was … that/who 强调', r'It (is|was)\b.*\b(that|who|whom|which)\b'),
    ],
    'it 形式主语／宾语': [
        ('形式宾语 it（find/make/think… it adj.）', r'形式宾语|\b(find|make|think|consider|feel|believe|regard|keep|leave|hold|take)\b[^.。]{0,25}\bit\b'),
        ('It takes/took 时间 to do', r'\bIt (takes|took)\b|花费'),
        ('形式主语 It is adj. to do / that', r'形式主语|\bIt (is|was)\b'),
    ],
    '名词性从句': [
        ('表语从句', r'表语从句'),
        ('主语从句', r'主语从句'),
        ('同位语从句', r'同位语从句'),
        ('宾语从句', r'宾语从句'),
        ('引导词 whether / if', r'whether|\bif\b'),
        ('引导词 wh-', r'\b(what|who|whom|whose|which|when|where|why|how)\b'),
        ('引导词 that', r'\bthat\b'),
    ],
    '非谓语': [
        ('作宾补', r'宾补|宾语补足语'),
        ('作状语', r'状语'),
        ('作定语', r'定语'),
        ('作主语', r'作主语|充当主语|做主语'),
        ('作宾语 / 固定搭配', r'作宾语|动名词作|固定搭配|搭配'),
    ],
    '主谓一致': [
        ('together with / as well as 类', r'together with|as well as|along with|accompanied by'),
        ('就近原则', r'就近原则|就近'),
        ('the number of / a number of', r'(the|a) number of'),
        ('分数 / 百分数 of', r'分之|百分之|percent|%|fraction|\b(half|one third|two thirds|one-third|two-thirds)\b|\d+/\d+'),
        ('each / every / 不定代词', r'\b(each|every|either|neither|everyone|everybody|none|no one|anyone)\b'),
        ('动名词 / 不定式短语作主语', r'动名词|不定式作主语|作主语|Spending|Going|Being|Doing|Reading|Learning'),
        ('固定短语 / 固定句型', r'固定短语|固定句型|固定搭配|短语|would rather'),
        ('时间状语定时态', r'时间状语|so far|yesterday|last \w+|now\b|every\b|现在完成|一般现在时|一般过去时'),
        ('语态 + 主谓一致', r'被动|语态'),
        ('主语被修饰语隔开', r'定语从句|介词短语|修饰|\bof\b'),
    ],
    '倒装': [
        ('Only + 状语句首', r'\bOnly\b'),
        ('否定词句首', r'Not only|Not until|No sooner|Hardly|Scarcely|Seldom|Rarely|Never|Little\b|No\s'),
        ('So / Neither / Nor 倒装', r'\b(So|Neither|Nor)\s'),
        ('地点 / 方位状语句首全倒装', r'地点|方位|全部倒装|全倒装|\bHere\b|\bThere\b|\bOut\b|\bUp\b|\bDown\b|\bAway\b|\bBehind\b|\bAmong\b'),
    ],
    '定语从句': [
        ('关系副词 where / when / why', r'关系副词|\b(where|when|why)\b'),
        ('whose', r'\bwhose\b'),
        ('who / whom', r'\b(who|whom)\b'),
        ('which', r'\bwhich\b'),
        ('that', r'\bthat\b'),
    ],
    '状语从句': [
        ('让步', r'让步|although|though|even if|even though|no matter|whatever|whenever|however'),
        ('目的', r'目的|so that|in order that'),
        ('结果', r'结果|so\s+\w+\s+that|such\b.*\bthat\b'),
        ('条件', r'条件|\bif\b|unless|as long as|provided|only if'),
        ('时间', r'时间|\bwhen\b|\bwhile\b|as soon as|until|\bbefore\b|\bafter\b|\bsince\b|\bonce\b'),
        ('原因', r'原因|because|\bas\b|\bsince\b'),
        ('地点', r'地点|\bwhere\b|wherever'),
        ('比较', r'than|as\s+\w+\s+as'),
    ],
}

# ── 括号指令 ───────────────────────────────────────────
GENERIC_RE = re.compile(r'所给|适当|正确形式|根据.*提示|根据.*首字母|根据中英文|汉译英|^(翻译句子|完成句子|单词拼写|填空|翻译)$')
CUE_RE = re.compile(r'同义|改写|改成|转换|改为|转被动|合并|强调|句型|翻译|改编|转为|划线|语态|省略句|附加疑问')
PAREN_RE = re.compile(r'[ \t]*[（(]([^（）()\n]*)[）)]')


def read_rows():
    with open(DATA / '题库.jsonl', encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def node_files(rows):
    """高一上各节点的文件集合（同卷多文件已并卷）。"""
    files = defaultdict(set)
    for _rep, members, g, t, n, _guess in papers(rows):
        if (g, t) == (GRADE, TERM):
            files[n].update(members)
    return files


def eligible(r):
    if r['题型'] in EXCLUDE_TYPES:
        return False
    return '疑似非单句题' not in (r.get('标记') or [])


def gkey(r):
    return r['重复组'] if r['重复组'] is not None else f"id:{r['id']}"


def rank(r):
    lab = r.get('标签') or ''
    return (-lab.count('·'), -len(lab), r['id'])


def unique_pool(rows):
    best = {}
    for r in rows:
        k = gkey(r)
        if k not in best or rank(r) < rank(best[k]):
            best[k] = r
    return best


def first_hit(text, topics):
    best = None
    for name, pat in topics:
        m = re.search(pat, text)
        if m and (best is None or m.start() < best[0]):
            best = (m.start(), name)
    return best[1] if best else None


def classify(r):
    jie = r.get('解析') or ''
    m = re.search('考查', jie)
    if m:
        main = first_hit(jie[m.end():], TOPICS)
        if main:
            src = '考查'
            return main, src, [n for n, p in TOPICS if n != main and re.search(p, jie)]
    main = first_hit(jie, TOPICS)
    src = '全文' if main else None
    others = [n for n, p in TOPICS if n != main and re.search(p, jie)]
    return main, src, others


def clean_stem(stem):
    """剥离括号指令：通用指令直接删，改写 / 翻译指令进 cue；词形提示保留。换行保留（排版时转 →）。"""
    cues = []

    def repl(m):
        inner = m.group(1).strip()
        if GENERIC_RE.search(inner):
            return ' '
        if CUE_RE.search(inner):
            if inner not in cues:
                cues.append(inner)
            return ' '
        return m.group(0)

    s = PAREN_RE.sub(repl, stem or '')
    lines = [re.sub(r'\s+', ' ', ln).strip() for ln in s.split('\n')]
    return '\n'.join(ln for ln in lines if ln), cues


def stem_defects(r, stem, cues):
    out = []
    # 改写题（有 cue）本就没有待填句，不算缺空位
    if r['题型'] in ('语法填空', '完成句子', '单词拼写') and '___' not in stem and not cues:
        out.append('无空位')
    if stem.count('(') + stem.count('（') != stem.count(')') + stem.count('）'):
        out.append('括号不配对')
    if re.search(r'\b(the|a|an|to|of|in|is|are|and|he|she|it|we|they|you)\s+\1\b', stem, re.I):
        out.append('重复词')
    if re.search(r'[A-Za-z]\s*(…|\.\.\.)$', stem.strip()):
        out.append('句末省略号')
    # 学科名直接作主语后接动词，多半漏了 teacher 之类的中心词（如 My English recommended us…）
    if re.search(r'\b(My|Our|His|Her|Their|Your|The)\s+(English|Chinese|math|maths|music|history|science|physics|chemistry|biology|PE)\s+(\w+ed|told|gave|made|took|sent|taught|led|left|brought)\b', stem, re.I):
        out.append('疑似漏词（学科名后直接接动词）')
    if '�' in stem or re.search(r'[?？]{2,}', stem):
        out.append('乱码')
    return out


def subclass_of(topic, text, ans):
    for name, pat in SUBCLASSES.get(topic, []):
        if re.search(pat, text):
            return name
    if topic == '非谓语':   # 兜底：按答案形式归类
        a = (ans or '').strip().lower()
        if a.startswith('to '):
            return '形式：不定式'
        if re.search(r'ing$', a):
            return '形式：-ing'
        if re.search(r'(ed|en)$', a):
            return '形式：-ed'
    return '其他'


def make_entry(r, main, src, others, borrowed=None):
    stem, cues = clean_stem(r['题干'])
    d = {
        'id': r['id'], '标签': r['标签'], '题型': r['题型'], '题干': stem,
        '提示词': r.get('提示词'), '答案': r['答案'], '解析': r.get('解析'), '句意': r.get('句意'),
        'cue': cues, '主考点': main, '主考点来源': src, '其他命中': others,
    }
    if borrowed:
        d['借用节点'] = borrowed
    defects = stem_defects(r, stem, cues)
    d['疑似缺陷'] = bool(defects)
    if defects:
        d['缺陷原因'] = defects
    d['标记'] = r.get('标记') or []
    return d


def build(book, rows, files, cov):
    cfg = BOOKS[book]
    node = f'{GRADE}{TERM}·{book}'
    stat = {'节点文件数': len(files[book])}

    raw = [r for r in rows if r['文件'] in files[book]]
    stat['原始行数'] = len(raw)
    stat['单选其他'] = sum(r['题型'] in EXCLUDE_TYPES for r in raw)
    stat['疑似非单句'] = sum(r['题型'] not in EXCLUDE_TYPES and not eligible(r) for r in raw)
    own = unique_pool([r for r in raw if eligible(r)])
    stat['去重后题数'] = len(own)
    stat['重复组去掉'] = sum(eligible(r) for r in raw) - len(own)

    used = set(own)
    own_by = defaultdict(list)
    main_dist = Counter()
    for k, r in own.items():
        main, src, others = classify(r)
        main_dist[main or '未命中'] += 1
        if main:
            own_by[main].append(make_entry(r, main, src, others))
    stat['主考点分布'] = dict(main_dist.most_common())

    donor_pools = {dn: unique_pool([r for r in rows if r['文件'] in files[dn] and eligible(r)])
                   for dn in cfg['donors']}

    topics_out = []
    for topic in cfg['topics']:
        own_list = sorted(own_by[topic], key=lambda e: e['id'])
        borrowed = []
        need = MIN_CAND - len(own_list)
        if need > 0:
            for dn in cfg['donors']:
                for k, r in sorted(donor_pools[dn].items(), key=lambda kv: kv[1]['id']):
                    if need <= 0:
                        break
                    if k in used:
                        continue
                    main, src, others = classify(r)
                    if main != topic:
                        continue
                    used.add(k)
                    borrowed.append(make_entry(r, main, src, others, borrowed=dn))
                    need -= 1
        cands = own_list + borrowed
        sub = {}
        for e in cands:
            text = e['题干'] + ' ' + (e['解析'] or '')
            sub.setdefault(subclass_of(topic, text, e['答案']), []).append(e['id'])
        order = [n for n, _ in SUBCLASSES.get(topic, [])] + ['形式：不定式', '形式：-ing', '形式：-ed', '其他']
        sub_out = {n: {'题数': len(sub[n]), '题': sub[n]} for n in order if n in sub}
        c = cov[node]['专题'][topic]
        topics_out.append({
            '名称': topic, '讲': True,
            '覆盖卷': c['覆盖卷'], '覆盖率': c['覆盖率'], '题数': c['题数'],
            '候选': {'本节点': len(own_list), '借用': len(borrowed), '合计': len(cands)},
            '子类': sub_out,
            '题': cands,
        })
    # 讲的专题按覆盖率降序（并列按题数、再按册内顺序）
    topics_out.sort(key=lambda t: (-t['覆盖率'], -t['题数'], cfg['topics'].index(t['名称'])))
    for i, t in enumerate(topics_out, 1):
        t['编号'] = i

    for topic in cfg['skip']:
        c = cov[node]['专题'][topic]
        topics_out.append({
            '名称': topic, '讲': False, '编号': None,
            '覆盖卷': c['覆盖卷'], '覆盖率': c['覆盖率'], '题数': c['题数'],
            '候选': {'本节点': len(own_by[topic]), '借用': 0, '合计': 0},
            '子类': {}, '题': [],
        })

    stat['疑似缺陷题数'] = sum(e['疑似缺陷'] for t in topics_out for e in t['题'])
    stat['候选合计'] = sum(len(t['题']) for t in topics_out)
    stat['借用合计'] = sum(t['候选']['借用'] for t in topics_out)
    stat['借用节点分布'] = dict(Counter(e['借用节点'] for t in topics_out for e in t['题'] if '借用节点' in e))
    stat['不足 8 题的讲专题'] = [f"{t['名称']}({t['候选']['合计']})" for t in topics_out if t['讲'] and t['候选']['合计'] < MIN_CAND]

    return {
        '册': node,
        '节点': book,
        '卷数': cov[node]['卷数'],
        '题数_关键词': cov[node]['题数'],
        '专题': topics_out,
        '统计': stat,
    }


def main():
    rows = read_rows()
    files = node_files(rows)
    cov = json.loads((DATA / '段考专题.json').read_text(encoding='utf-8'))
    for book in BOOKS:
        out = build(book, rows, files, cov)
        p = OUT_DIR / f"段考-高一上-{book}.候选.json"
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
        s = out['统计']
        print(f"== {out['册']}  卷数 {out['卷数']}  关键词题数 {out['题数_关键词']}")
        print(f"   原始 {s['原始行数']} 行；单选/其他 {s['单选其他']}；疑似非单句 {s['疑似非单句']}；去重后 {s['去重后题数']}（重复组去掉 {s['重复组去掉']}）")
        print(f"   主考点分布 {s['主考点分布']}")
        for t in out['专题']:
            tag = f"{t['编号']}" if t['讲'] else '—'
            c = t['候选']
            print(f"   [{tag}] {t['名称']:<18} 覆盖 {t['覆盖卷']}/{out['卷数']} {t['覆盖率']:.0%} 关键词题 {t['题数']:>3} | "
                  f"候选 本节点 {c['本节点']:>2} + 借用 {c['借用']:>2} = {c['合计']:>2}"
                  + (f" | 子类 {({k: v['题数'] for k, v in t['子类'].items()})}" if t['子类'] else ''))
        print(f"   借用节点 {s['借用节点分布']}；疑似缺陷 {s['疑似缺陷题数']} 题；候选合计 {s['候选合计']}")
        print(f"   不足 8 题：{s['不足 8 题的讲专题'] or '无'}")
        print(f"   写入 {p}")


if __name__ == '__main__':
    main()
