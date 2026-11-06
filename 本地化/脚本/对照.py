#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题目 → 单元匹配（人教版 2019 必修/选必 36 单元）。

用法：python3 -I 本地化/脚本/对照.py
输入：本地化/数据/题库.jsonl、单元.json、词族索引.json
输出：本地化/数据/题-单元.jsonl，每题一行：
    {"id", "命中": [{"序","词头","方式","证据","唯一"}], "考法"}

方式：
- 提示词：语法填空的提示词，还原后查词族索引。
- 答案：单词拼写，以及无提示词的语法填空；答案为单个实词（长度>=4、不在虚词表）时还原后查索引。
- 搭配：完成句子和翻译；答案里出现某单元搭配短语时命中（不查题干，见报告）。

只用标准库，结果确定（无随机、无集合迭代顺序依赖）。
"""

import json
import os
import re
import sys
from functools import lru_cache

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.normpath(os.path.join(HERE, '..', '数据'))
PATH_Q = os.path.join(DATA, '题库.jsonl')
PATH_U = os.path.join(DATA, '单元.json')
PATH_IDX = os.path.join(DATA, '词族索引.json')
PATH_OUT = os.path.join(DATA, '题-单元.jsonl')

# ---------------------------------------------------------------- 虚词停用表
# 功能词：不计入实词；单个功能词作答案时不查索引。
FUNC = set("""
a an the and or but nor yet so for of in on at to by with from into onto upon
about above across after against along among around as before behind below
beside besides between beyond both during either except inside like near
neither off once only over since through throughout till toward towards under
until up down out within without would could should might must shall will
can may ought be am is are was were been being do does did done doing have has
had having i me my mine myself you your yours yourself yourselves he him his
himself she her hers herself it its itself we us our ours ourselves they them
their theirs themselves this that these those there here what which who whom
whose when where why how whether if than then too very also just even still
again already ever never always often sometimes not no all any each every some
many much more most few less least other another such one ones oneself thus
while though although because unless whereas yes
""".split())
# 搭配里的占位词：规范化时直接去掉
PLACEHOLDER = {'sth', 'sb', 'sp', 'oneself', 'doing', 'do'}

# ---------------------------------------------------------------- 不规则形式
# 每行：原形 过去式 过去分词（分词可为 -）。not-in-table 的形式走规则。
_IRR_VERBS = """
be was were been
become became become
begin began begun
bend bent bent
bet bet bet
bind bound bound
bite bit bitten
blow blew blown
break broke broken
breed bred bred
bring brought brought
build built built
burn burnt burnt
burst burst burst
buy bought bought
catch caught caught
choose chose chosen
cling clung clung
come came come
cost cost cost
creep crept crept
cut cut cut
deal dealt dealt
dig dug dug
do did done
draw drew drawn
dream dreamt dreamt
drink drank drunk
drive drove driven
eat ate eaten
fall fell fallen
feed fed fed
feel felt felt
fight fought fought
find found found
flee fled fled
fling flung flung
fly flew flown
forbid forbade forbidden
forecast forecast forecast
forget forgot forgotten
forgive forgave forgiven
forsake forsook forsaken
freeze froze frozen
get got got
give gave given
go went gone
grind ground ground
grow grew grown
hang hung hung
have had had
hear heard heard
hide hid hidden
hit hit hit
hold held held
hurt hurt hurt
keep kept kept
kneel knelt knelt
lay laid laid
know knew known
lead led led
lean leant leant
leap leapt leapt
learn learnt learnt
leave left left
lend lent lent
let let let
lie lain lain
light lit lit
lose lost lost
make made made
mean meant meant
meet met met
mislead misled misled
mistake mistook mistaken
overcome overcame overcome
overhear overheard overheard
pay paid paid
put put put
quit quit quit
read read read
rid rid rid
ride rode ridden
ring rang rung
rise rose risen
run ran run
say said said
see saw seen
seek sought sought
sell sold sold
send sent sent
set set set
shake shook shaken
shed shed shed
shine shone shone
shoot shot shot
show showed shown
shrink shrank shrunk
shut shut shut
sing sang sung
sink sank sunk
sit sat sat
sleep slept slept
slide slid slid
smell smelt smelt
speak spoke spoken
speed sped sped
spell spelt spelt
spend spent spent
spill spilt spilt
spin spun spun
split split split
spread spread spread
spring sprang sprung
stand stood stood
steal stole stolen
stick stuck stuck
sting stung stung
stink stank stunk
strike struck struck
strive strove striven
swear swore sworn
sweep swept swept
swim swam swum
swing swung swung
take took taken
teach taught taught
tear tore torn
tell told told
think thought thought
throw threw thrown
tread trod trodden
undergo underwent undergone
understand understood understood
undertake undertook undertaken
upset upset upset
wake woke woken
wear wore worn
weave wove woven
weep wept wept
win won won
wind wound wound
withdraw withdrew withdrawn
withstand withstood withstood
write wrote written
bear bore borne
beat beat beaten
bid bid bid
sow sowed sown
oversleep overslept overslept
foresee foresaw foreseen
"""

IRR = {}  # 屈折形 -> [可能原形, ...]（有序）
for _line in _IRR_VERBS.strip().splitlines():
    _p = _line.split()
    _base = _p[0]
    for _f in _p[1:]:
        if _f not in ('-',):
            IRR.setdefault(_f, []).append(_base)
# 助动词/系动词的人称变化
for _f in ('am', 'is', 'are', 'being'):
    IRR[_f] = ['be']
for _f in ('has',):
    IRR[_f] = ['have']
for _f in ('does',):
    IRR[_f] = ['do']
for _f in ('goes',):
    IRR[_f] = ['go']
# 不规则名词复数
IRR.update({
    'children': ['child'], 'men': ['man'], 'women': ['woman'], 'feet': ['foot'],
    'teeth': ['tooth'], 'mice': ['mouse'], 'geese': ['goose'], 'oxen': ['ox'],
    'knives': ['knife'], 'wives': ['wife'], 'lives': ['life', 'live'],
    'leaves': ['leaf', 'leave'], 'halves': ['half'], 'shelves': ['shelf'],
    'wolves': ['wolf'], 'thieves': ['thief'], 'criteria': ['criterion'],
    'phenomena': ['phenomenon'], 'analyses': ['analysis', 'analyse'],
    'crises': ['crisis'], 'bases': ['base', 'basis'], 'theses': ['thesis'],
})
# 不规则比较级/最高级
IRR.update({
    'better': ['good', 'well'], 'best': ['good', 'well'],
    'worse': ['bad', 'badly'], 'worst': ['bad', 'badly'],
    'less': ['little'], 'least': ['little'],
    'further': ['far'], 'furthest': ['far'], 'farther': ['far'], 'farthest': ['far'],
    'elder': ['old'], 'eldest': ['old'],
    'more': ['many', 'much'], 'most': ['many', 'much'],
})
COMP_IRR = {'better', 'best', 'worse', 'worst', 'less', 'least', 'more', 'most',
            'further', 'furthest', 'farther', 'farthest', 'elder', 'eldest'}
IRR_PL = {'children', 'men', 'women', 'feet', 'teeth', 'mice', 'geese', 'oxen',
          'knives', 'wives', 'lives', 'leaves', 'halves', 'shelves', 'wolves',
          'thieves', 'criteria', 'phenomena', 'crises', 'theses'}
# 形似屈折、实为原形的词（不做 -s 还原）
NO_STRIP_S = {'news', 'series', 'species', 'means', 'physics', 'mathematics',
              'politics', 'economics', 'athletics', 'always', 'perhaps', 'thus',
              'this', 'his', 'its', 'was', 'has', 'does', 'is', 'as', 'yes', 'us',
              'bus', 'gas', 'plus', 'bonus', 'virus', 'status', 'lens', 'chaos',
              'pass', 'less', 'unless', 'across', 'princess', 'boss', 'glass'}

AUX = {'to', 'be', 'been', 'being', 'am', 'is', 'are', 'was', 'were', 'have', 'has',
       'had', 'do', 'does', 'did', 'will', 'would', 'shall', 'should', 'can', 'could',
       'may', 'might', 'must'}


def _doubled(s):
    return len(s) >= 2 and s[-1] == s[-2] and s[-1] not in 'lsz'


def _cands(w):
    """屈折还原候选，按优先级排列（不含 w 本身）。"""
    out = []
    if w in IRR:
        out.extend(IRR[w])
    if len(w) >= 5 and w.endswith('ying'):   # lying → lie, dying → die
        out.append(w[:-4] + 'ie')
    if len(w) >= 5 and w.endswith('ing'):
        b = w[:-3]
        if _doubled(b):
            out.append(b[:-1])
        if b.endswith('ck'):           # panic → panicking
            out.append(b[:-1])
        out += [b + 'e', b]
    if len(w) >= 4 and w.endswith('ied'):
        out.append(w[:-3] + 'y')
    if len(w) >= 4 and w.endswith('ed'):
        b = w[:-2]
        if _doubled(b):
            out.append(b[:-1])
        if b.endswith('ck'):           # panic → panicked
            out.append(b[:-1])
        out += [w[:-1], b]
    if len(w) >= 4 and w.endswith('ies'):
        out.append(w[:-3] + 'y')
    elif len(w) >= 4 and w.endswith('es'):
        out += [w[:-1], w[:-2]]
    elif len(w) >= 3 and w.endswith('s') and not w.endswith(('ss', 'us', 'is')) \
            and w not in NO_STRIP_S:
        out.append(w[:-1])
    if len(w) >= 5 and w.endswith('er'):
        b = w[:-2]
        if _doubled(b):
            out.append(b[:-1])
        out += [b, b + 'e']
    if len(w) >= 5 and w.endswith('est'):
        b = w[:-3]
        if _doubled(b):
            out.append(b[:-1])
        out += [b, b + 'e']
    seen, res = set(), []
    for c in out:
        if c and c != w and c not in seen:
            seen.add(c)
            res.append(c)
    return res


# ---------------------------------------------------------------- 数据加载
def load():
    with open(PATH_U, encoding='utf-8') as f:
        units = json.load(f)
    with open(PATH_IDX, encoding='utf-8') as f:
        idx_raw = json.load(f)
    with open(PATH_Q, encoding='utf-8') as f:
        qs = [json.loads(line) for line in f if line.strip()]

    # 词族索引中有若干条目的「词头」是例句而非词（数据缺陷），整条忽略。
    idx = {}
    dropped_bad = []
    for k, ents in idx_raw.items():
        keep = []
        for e in ents:
            if len(e['词头'].split()) > 6:
                dropped_bad.append((k, e['词头']))
                continue
            keep.append(e)
        if keep:
            idx[k] = keep

    derive_pairs = set()     # (词头, 派生词)，同一词条内
    heads = set()
    phrases = []             # (序, 词头, 短语原文, 变体, 变体键)
    for u in units:
        for w in u['词汇']:
            hw = w['词'].lower()
            heads.add(hw)
            for d in w.get('派生', []):
                dw = d['词'].lower()
                derive_pairs.add((hw, dw))
                derive_pairs.add((dw, hw))
            for c in w.get('搭配', []):
                phrases.append((u['序'], w['词'], c['短语']))
    return units, idx, qs, derive_pairs, heads, phrases, dropped_bad


# ---------------------------------------------------------------- 词形还原
def build_vocab(idx, heads, derive_words):
    v = {k for k in idx if ' ' not in k}
    v |= heads
    v |= derive_words
    return v


class Lemmer:
    def __init__(self, vocab, idx):
        self.vocab = vocab
        self.idx = idx

    @lru_cache(maxsize=None)
    def lemma(self, w):
        """语法层面的原形（用于判断词干是否相同），候选需在词表中。"""
        w = w.lower()
        for c in _cands(w):
            if c in self.vocab:
                return c
        return w

    def index_key(self, w):
        """查词族索引用：先还原（候选按优先级），最后才用原词。返回命中的索引键或 None。"""
        w = w.lower()
        for c in _cands(w):
            if c in self.idx:
                return c
        if w in self.idx:
            return w
        return None


# ---------------------------------------------------------------- 搭配规范化
def expand_phrase(phrase, lem):
    """搭配短语 → 实词原形元组列表（每个元组是一条匹配变体，实词>=2）。"""
    s = phrase.replace('（', '(').replace('）', ')').replace('…', ' ').replace('’', "'")
    s = re.sub(r'\([^()]*\)', ' ', s)          # 括号内容视为可选：匹配时省略
    s = re.sub(r"'s\b", ' ', s)               # one's / sb's 等所有格
    s = re.sub(r'\.{2,}', ' ', s)
    s = re.sub(r'[.,?!:;"“”]', ' ', s)
    tokens = s.split()
    slots = []
    for t in tokens:
        alts = [p.strip().lower() for p in t.split('/')]
        alts = [a for a in alts if a]
        if alts:
            slots.append(alts)
    if not slots:
        return []
    variants = [[]]
    for alts in slots:
        variants = [v + [a] for v in variants for a in alts]
        if len(variants) > 64:
            variants = variants[:64]
    res, seen = [], set()
    for v in variants:
        content = [w for w in v if w not in FUNC and w not in PLACEHOLDER]
        if len(content) < 2:
            continue
        key = tuple(lem.lemma(w) for w in content)
        if key not in seen:
            seen.add(key)
            res.append(key)
    return res


def clean_phrase(phrase):
    """搭配原文 → 词头用的短语：去括号内容与省略号，斜线备选取第一个，去掉句末占位词。
    如 make（good/full）use of → make use of；the first/second/... time → the first time；
    set an example for sb → set an example for；make up one's mind to do sth → make up one's mind。"""
    s = phrase.replace('（', '(').replace('）', ')').replace('…', ' ').replace('’', "'")
    s = re.sub(r'\([^()]*\)', ' ', s)
    s = re.sub(r'\.{2,}', ' ', s)
    out = [t.split('/')[0].strip(" .,;:!?\"“”").lower() for t in s.split()]
    out = [t for t in out if t and t not in ('sb', 'sth', 'sp', 'somebody', 'something')]
    while out and out[-1] in ('sb', 'sth', 'sp', 'somebody', 'something', 'do', 'doing'):
        last = out.pop()
        if last == 'do' and out and out[-1] == 'to':     # 不定式符号随 do 一起去掉
            out.pop()
    return ' '.join(out)


def chain_match(toks, key):
    """在文本词元序列 toks 中找 key（实词原形有序，相邻两词间最多隔 3 个词）。返回 (起, 止) 或 None。"""
    n = len(toks)
    for i in range(n):
        if toks[i] != key[0]:
            continue
        pos, ok = i, True
        for lm in key[1:]:
            j, found = pos + 1, False
            while j < n and j <= pos + 4:
                if toks[j] == lm:
                    found = True
                    break
                j += 1
            if not found:
                ok = False
                break
            pos = j
        if ok:
            return i, pos
    return None


# ---------------------------------------------------------------- 考法
POS_KW = ('形容词', '副词', '名词', '动词形式')


def _words(s):
    return re.findall(r"[a-z]+", s.lower())


def _first_alt(ans, lh=None, lem=None):
    """取答案的第一个备选；若给出提示词词根 lh，则优先取含该词根的备选。"""
    parts = [p.strip() for p in re.split(r'\s*[；;]\s*|/', ans) if p.strip()]
    if lh is not None and lem is not None:
        for p in parts:
            if any(lem.lemma(t) == lh for t in _words(p)):
                return p
    return parts[0] if parts else ''


def classify(hint, ans, expl, lem, derive_pairs):
    """有提示词的语法填空：判定考法。"""
    H = next((p.strip().lower() for p in hint.split('/') if p.strip()), '')
    A = _first_alt(ans, lem.lemma(H), lem)
    toks = _words(A)
    expl = expl or ''
    if not toks or not H:
        return '其他'
    if A.lower() == H:
        return '其他'
    lh = lem.lemma(H)
    kt = next((t for t in toks if lem.lemma(t) == lh), toks[-1])
    lk = lem.lemma(kt)
    same = lk == lh
    aux_or_to = any(t in AUX for t in toks)

    if not same:
        if (H, kt) in derive_pairs or (H, lk) in derive_pairs:
            return '词性转换'
        if any(k in expl for k in POS_KW):
            return '词性转换'
        return '其他'

    # 同词干
    if any(t in ('more', 'most', 'less', 'least') for t in toks) or kt in COMP_IRR \
            or (kt.endswith(('er', 'est')) and kt != H and ('比较级' in expl or '最高级' in expl)):
        return '比较级'
    if kt != H and kt.endswith(('ed', 'ing')) and not aux_or_to and '形容词' in expl:
        return '词性转换'
    is_pl = kt in IRR_PL or (kt != H and (kt == H + 's' or kt == H + 'es'
                                          or (H.endswith('y') and kt == H[:-1] + 'ies')))
    if is_pl and not aux_or_to:
        if '第三人称' in expl or '主谓' in expl:
            return '动词形式'
        return '名词复数'
    if kt != H or aux_or_to:
        return '动词形式'
    return '其他'


# ---------------------------------------------------------------- 主流程
def main():
    units, idx, qs, derive_pairs, heads, phrases, dropped_bad = load()
    derive_words = {d for (_, d) in derive_pairs}
    vocab = build_vocab(idx, heads, derive_words)
    # 提示词按惯例是原形，计入词表以便还原其他屈折形（如 interested→interest）
    for q in qs:
        h = (q.get('提示词') or '').strip().lower()
        if h and re.fullmatch(r'[a-z]+', h):
            vocab.add(h)
    lem = Lemmer(vocab, idx)

    # 索引：词头 → 序（用于唯一）
    key_units = {}
    for k, ents in idx.items():
        key_units[k] = {e['序'] for e in ents}

    # 搭配变体
    phrase_entries = []      # (序, 词头, 短语, 键)
    by_first = {}            # 首实词 → [phrase_entries]
    key_to_units = {}
    for (序, 词头, 短语) in phrases:
        for key in expand_phrase(短语, lem):
            pe = (序, 词头, 短语, key)
            phrase_entries.append(pe)
            by_first.setdefault(key[0], []).append(pe)
            key_to_units.setdefault(key, set()).add(序)

    def index_hits(word, method, evidence_src):
        """返回索引命中列表（未排序）。"""
        k = lem.index_key(word)
        if k is None:
            return []
        ents = idx[k]
        uniq = len(key_units[k]) == 1
        out = []
        for e in ents:
            out.append({'序': e['序'], '词头': e['词头'], '方式': method,
                        '证据': f"{evidence_src} {word}" + (f"→{k}" if k != word.lower() else ''),
                        '唯一': uniq})
        return out

    # 搭配的词头：狂K 把一些搭配挂在不相干的词条下（set an example 挂在 set sth up 下，
    # make fun of 挂在 make it 下，the first time 挂在 moment 下）。词条本身是单词、且搭配里
    # 有它的同族词时，词头仍用该词条；否则词头用搭配本身（规范化后的短语）。
    fam_lemmas = {}
    def family(hw):
        if hw not in fam_lemmas:
            ws = {hw} | {d for (a, d) in derive_pairs if a == hw}
            fam_lemmas[hw] = {lem.lemma(w) for w in ws} | ws
        return fam_lemmas[hw]

    def phrase_head(词头, 短语, key):
        hw = 词头.strip().lower()
        if re.fullmatch(r"[a-z][a-z'\-]*", hw) and set(key) & family(hw):
            return 词头.strip()
        # 词条是短语、且搭配只是它的变体（make some difference ← make a difference）：仍用词条。
        # 词条至少两个实词才算（make it 只有一个实词，make fun of 不能归它）。
        pk = expand_phrase(词头, lem)
        if pk and all(set(k) <= set(key) for k in pk):
            return 词头.strip()
        return clean_phrase(短语)

    def phrase_hits(text, scope):
        toks = [lem.lemma(t) for t in _words(text)]
        hits, seen = [], set()
        cands = set(toks)
        for t in sorted(cands):
            for (序, 词头, 短语, key) in by_first.get(t, []):
                if (序, 词头, 短语) in seen or chain_match(toks, key) is None:
                    continue
                seen.add((序, 词头, 短语))
                snippet = ' '.join(text.split())
                if len(snippet) > 60:
                    snippet = snippet[:60] + '…'
                hits.append({'序': 序, '词头': phrase_head(词头, 短语, key), '方式': '搭配',
                             '证据': f"{短语}｜{scope}：{snippet}",
                             '唯一': len(key_to_units[key]) == 1})
        return hits

    out_rows = []
    stats = {}
    for q in qs:
        题型 = q.get('题型')
        hint = (q.get('提示词') or '').strip() or None
        ans = (q.get('答案') or '').strip()
        stem = q.get('题干') or ''
        expl = q.get('解析') or ''
        hits, kaofa = [], None
        method_used = None

        if 题型 == '语法填空' and hint:
            kaofa = classify(hint, ans, expl, lem, derive_pairs)
            # 提示词：各备选分别查索引
            for alt in [p.strip() for p in hint.split('/') if p.strip()]:
                if ' ' in alt:      # 多词提示词：整体查索引，不做屈折还原
                    if alt.lower() in idx:
                        k = alt.lower()
                        hits += [{'序': e['序'], '词头': e['词头'], '方式': '提示词',
                                  '证据': f"提示词 {alt}", '唯一': len(key_units[k]) == 1}
                                 for e in idx[k]]
                    continue
                hits += index_hits(alt, '提示词', '提示词')
            method_used = '提示词'

        elif 题型 in ('单词拼写', '语法填空'):
            a = _first_alt(ans)
            aw = a.strip().lower()
            if re.fullmatch(r'[a-z]+', aw or '') and len(aw) >= 4 and aw not in FUNC:
                hits += index_hits(aw, '答案', '答案')
            method_used = '答案'

        elif 题型 in ('完成句子', '翻译'):
            method_used = '搭配'
            ans_plain = re.sub(r'\s*[；;]\s*', ' ', ans)
            # 只查答案：试过「题干英文＋答案」，题干里的原句搭配多为改写的素材而非考点，误命中率过高
            hits += phrase_hits(ans_plain, '答案')

        # 去重：同一序同一词头同一方式只留一条；同一序下的索引命中按词头合并
        uniq_hits, seen = [], set()
        for h in hits:
            h = {k: v for k, v in h.items() if not k.startswith('_')}
            key = (h['序'], h['词头'], h['方式'])
            if key in seen:
                continue
            seen.add(key)
            uniq_hits.append(h)
        uniq_hits.sort(key=lambda h: (h['序'], h['词头']))

        out_rows.append({'id': q['id'], '命中': uniq_hits, '考法': kaofa})
        s = stats.setdefault(题型, [0, 0])
        s[0] += 1
        s[1] += 1 if uniq_hits else 0

    with open(PATH_OUT, 'w', encoding='utf-8') as f:
        for r in out_rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    print(f'写入 {PATH_OUT}：{len(out_rows)} 题')
    print('题型  总数  至少命中1单元')
    for k, (n, h) in sorted(stats.items(), key=lambda x: -x[1][0]):
        print(f'{k}  {n}  {h}  ({h / n:.1%})')
    print(f'索引中因词头为例句而忽略的条目：{len(dropped_bad)}')


if __name__ == '__main__':
    main()
