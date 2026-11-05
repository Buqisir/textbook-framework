#!/usr/bin/env python3
"""段考专题 · 选题（阶段 1）：读题库，为各节点生成讲解候选。

运行：
  python3 -I 本地化/脚本/段考选题.py              # 16 个节点全部（高一上 / 高一下 / 高二上 / 高二下 × 四个节点）
  python3 -I 本地化/脚本/段考选题.py 高一下 期中    # 只跑一个节点
输入：本地化/数据/题库.jsonl、本地化/数据/段考专题.json（只读）；节点判定与专题口径用 本地化/脚本/节点.py（papers、topic_hit、TOPICS）
输出：本地化/内容/段考-<年级学期>-<节点>.候选.json，如 段考-高一下-期中.候选.json

规则：
- 只取该节点的卷（节点.papers 判定，同卷多文件按一卷）；排除 题型 单选 / 其他、标记含「疑似非单句题」。
- 同 重复组 只留一题（标签最完整者）。
- 主考点（所属专题）：节点.topic_hit 命中的专题里，取「考查」句内最早出现者；「考查」句无命中时取全文最早出现者（主考点来源=全文）。
  一题只进一个专题。
- 其他命中：节点.topic_hit 命中的其余专题。
- 讲哪些专题（字段「讲」）：
  · 高一上·期中前月考、高一上·期中：沿用手定的讲法（HAND_PLAN，2026-11-05 定，见 讲义专题来源）；
  · 其余 14 个节点：默认「覆盖率 ≥ 30%，覆盖 ≥ 2 卷，且不在 DEFAULT_OFF 里」（DEFAULT_OFF = 被动、时态、情态动词、比较级、省略、反意疑问，
    两册定稿的总表从未单列这几项）。默认结果待负责人确认后再写定稿。
  不讲的专题仍输出一条（讲=false，题为空），便于总表取数。
- 讲的专题本节点候选不足 8 题（MIN_CAND），从同年级学期的其他节点补，补的题加 借用节点。
  补位顺序（DONORS）：期中前月考 → 期中、期中后月考、期末；期中 → 期中前月考、期中后月考、期末；
  期中后月考 → 期中、期末、期中前月考；期末 → 期中后月考、期中、期中前月考。
- cue：题干里括号内的改写 / 翻译指令剥离成 cue；通用指令（所给词的适当形式填空、汉译英……）直接删；
  词形提示（如 ___ (attract)、(申请)）留在题干。
- 初步考法归类（每题带 子类、子类依据、考查句）：
  先在「考查」句（解析中第一处「考查」起到句号）里按 SUBCLASSES 取第一条命中，子类依据=考查句；
  考查句无命中时在题干+解析全文里找，子类依据=全文；都无命中归「其他」（非谓语另按答案形式归类，子类依据=答案）。
  子类只为统计和挑题用，不影响入选。
- 疑似缺陷：题干无空位、括号不配对、重复词、英文句末省略号、乱码。启发式，判不出语义缺词。
- 平局排序里的题号（rank 中的 r['id']）由 本地化/数据/卷号.json 固定：题号前三位不随语料增删而漂移。
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from 节点 import GRADE_TERMS, NODES, TOPICS, all_books, papers, topic_hit  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / '本地化' / '数据'
OUT_DIR = ROOT / '本地化' / '内容'

# ── 讲哪些专题 ─────────────────────────────────────────
# 手定：两册已成稿，讲的专题保持不变（「讲」的顺序无关，最终按覆盖率排）。
HAND_PLAN = {
    '高一上·期中前月考': ['非谓语', 'it 形式主语／宾语', '名词性从句', '虚拟语气', '强调句', '主谓一致'],
    '高一上·期中': ['非谓语', 'it 形式主语／宾语', '定语从句', '状语从句', '名词性从句',
                  '强调句', '虚拟语气', '主谓一致', '倒装'],
}
DEFAULT_MIN_COV = 0.3
DEFAULT_MIN_VOLS = 2     # 至少 2 卷考到：只在一卷里出现的不算节点专题
DEFAULT_OFF = ('被动', '时态', '情态动词', '比较级', '省略', '反意疑问')

# 补位顺序：同年级学期内的其他节点，先互补节点，再期中后月考、期末
DONORS = {
    '期中前月考': ['期中', '期中后月考', '期末'],
    '期中': ['期中前月考', '期中后月考', '期末'],
    '期中后月考': ['期中', '期末', '期中前月考'],
    '期末': ['期中后月考', '期中', '期中前月考'],
}
MIN_CAND = 8
EXCLUDE_TYPES = ('单选', '其他')
PAT = dict(TOPICS)
TOPIC_IDX = {n: i for i, (n, _) in enumerate(TOPICS)}

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
KAOCHA_RE = re.compile(r'考查[^。]*')


def read_rows():
    with open(DATA / '题库.jsonl', encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def node_files(P, gt):
    """某年级学期各节点的文件集合（同卷多文件已并卷）。P = papers(rows) 的结果。"""
    files = defaultdict(set)
    for _rep, members, g, t, n, _guess in P:
        if f'{g}{t}' == gt:
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


def kaocha(jie):
    """解析中第一处「考查」起到句号为止的一句；无则 None。"""
    m = KAOCHA_RE.search(jie or '')
    return m.group(0) if m else None


def classify(r):
    """主考点 = topic_hit 命中的专题中，考查句内最早出现者（无则全文最早出现者）。返回 (主考点, 来源, 其他命中)。"""
    jie = r.get('解析') or ''
    ans = r.get('答案') or ''
    hits = [n for n, p in TOPICS if topic_hit(n, p, jie, ans)]
    if not hits:
        return None, None, []
    m = re.search('考查', jie)
    after = jie[m.end():] if m else ''

    def pos(n):
        if after:
            mm = re.search(PAT[n], after)
            if mm:
                return (0, mm.start(), TOPIC_IDX[n])
        mm = re.search(PAT[n], jie)
        return (1, mm.start() if mm else 10 ** 9, TOPIC_IDX[n])

    main = min(hits, key=pos)
    src = '考查' if pos(main)[0] == 0 else '全文'
    return main, src, [n for n in hits if n != main]


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


def subclass_of(topic, kc, text, ans):
    """返回 (子类, 子类依据)。先看考查句，再看全文。"""
    for basis, s in (('考查句', kc or ''), ('全文', text)):
        if not s:
            continue
        for name, pat in SUBCLASSES.get(topic, []):
            if re.search(pat, s):
                return name, basis
    if topic == '非谓语':   # 兜底：按答案形式归类
        a = (ans or '').strip().lower()
        if a.startswith('to '):
            return '形式：不定式', '答案'
        if re.search(r'ing$', a):
            return '形式：-ing', '答案'
        if re.search(r'(ed|en)$', a):
            return '形式：-ed', '答案'
    return '其他', None


def make_entry(r, main, src, others, borrowed=None):
    stem, cues = clean_stem(r['题干'])
    jie = r.get('解析')
    d = {
        'id': r['id'], '标签': r['标签'], '题型': r['题型'], '题干': stem,
        '提示词': r.get('提示词'), '答案': r['答案'], '解析': jie, '句意': r.get('句意'),
        'cue': cues, '主考点': main, '主考点来源': src, '其他命中': others,
        '考查句': kaocha(jie),
    }
    if borrowed:
        d['借用节点'] = borrowed
    defects = stem_defects(r, stem, cues)
    d['疑似缺陷'] = bool(defects)
    if defects:
        d['缺陷原因'] = defects
    d['标记'] = r.get('标记') or []
    return d


def lecture_plan(key, cn):
    """返回 (讲的专题名, 讲义专题来源)。cn：该节点在 段考专题.json 里的 专题 字典。"""
    if key in HAND_PLAN:
        return HAND_PLAN[key], '手定（2026-11-05 两册定稿时的讲法）'
    lect = [n for n, _ in TOPICS if n not in DEFAULT_OFF
            and cn[n]['覆盖率'] >= DEFAULT_MIN_COV and cn[n]['覆盖卷'] >= DEFAULT_MIN_VOLS]
    return lect, (f'默认：覆盖率 ≥ {DEFAULT_MIN_COV:.0%} 且覆盖 ≥ {DEFAULT_MIN_VOLS} 卷，不含 '
                  + '、'.join(DEFAULT_OFF) + '（待负责人确认）')


def empty_cov():
    return {'卷数': 0, '推定卷数': 0, '题数': 0, '专题': {n: {'覆盖卷': 0, '覆盖率': 0, '题数': 0} for n, _ in TOPICS}}


def build(gt, node, rows, files, cov):
    key = f'{gt}·{node}'
    cv = cov.get(key) or empty_cov()
    cn = cv['专题']
    lect, source = lecture_plan(key, cn)
    stat = {'节点文件数': len(files[node])}

    raw = [r for r in rows if r['文件'] in files[node]]
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

    donors = DONORS.get(node, [])
    donor_pools = {dn: unique_pool([r for r in rows if r['文件'] in files[dn] and eligible(r)])
                   for dn in donors}

    topics_out = []
    for topic in lect:
        own_list = sorted(own_by[topic], key=lambda e: e['id'])
        borrowed = []
        need = MIN_CAND - len(own_list)
        if need > 0:
            for dn in donors:
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
        sub = defaultdict(list)
        for e in cands:
            e['子类'], e['子类依据'] = subclass_of(topic, e['考查句'], e['题干'] + ' ' + (e['解析'] or ''), e['答案'])
            sub[e['子类']].append(e['id'])
        order = [n for n, _ in SUBCLASSES.get(topic, [])] + ['形式：不定式', '形式：-ing', '形式：-ed', '其他']
        sub_out = {n: {'题数': len(sub[n]), '题': sub[n]} for n in order if n in sub}
        c = cn[topic]
        topics_out.append({
            '名称': topic, '讲': True,
            '覆盖卷': c['覆盖卷'], '覆盖率': c['覆盖率'], '题数': c['题数'],
            '候选': {'本节点': len(own_list), '借用': len(borrowed), '合计': len(cands)},
            '子类': sub_out,
            '题': cands,
        })
    # 讲的专题按覆盖率降序（并列按题数、再按 TOPICS 顺序）
    topics_out.sort(key=lambda t: (-t['覆盖率'], -t['题数'], TOPIC_IDX[t['名称']]))
    for i, t in enumerate(topics_out, 1):
        t['编号'] = i

    for topic, _ in TOPICS:
        if topic in lect:
            continue
        c = cn[topic]
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
        '册': key,
        '年级学期': gt,
        '节点': node,
        '讲义专题来源': source,
        '卷数': cv['卷数'],
        '推定卷数': cv['推定卷数'],
        '题数_关键词': cv['题数'],
        '专题': topics_out,
        '统计': stat,
    }


def targets(argv):
    if not argv:
        return all_books()
    if len(argv) == 2 and argv[0] in GRADE_TERMS and argv[1] in NODES:
        return [(argv[0], argv[1])]
    raise SystemExit('用法：段考选题.py [年级学期 节点]，如 段考选题.py 高一下 期中；不带参数跑全部 16 个节点。'
                     f'年级学期：{" / ".join(GRADE_TERMS)}；节点：{" / ".join(NODES)}')


def main():
    rows = read_rows()
    P = papers(rows)
    cov = json.loads((DATA / '段考专题.json').read_text(encoding='utf-8'))
    for gt, node in targets(sys.argv[1:]):
        out = build(gt, node, rows, node_files(P, gt), cov)
        p = OUT_DIR / f"段考-{gt}-{node}.候选.json"
        p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
        s = out['统计']
        print(f"== {out['册']}  卷数 {out['卷数']}（推定 {out['推定卷数']}）  关键词题数 {out['题数_关键词']}  讲义专题：{out['讲义专题来源']}")
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
