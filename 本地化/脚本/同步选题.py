#!/usr/bin/env python3
"""同步课单元讲义 · 选题（人教版必修一 Welcome Unit、Unit 1、Unit 2）。

运行：python3 -I 本地化/脚本/同步选题.py
输入：本地化/数据/题库.jsonl、题-单元.jsonl、单元.json、词族索引.json、待校对.tsv（只读）
输出：本地化/内容/同步-必修一-W-U2.json（候选骨架：自动部分已填，人工部分留空）

结构：① 考情（统计）→ ② 词性转换 → ③ 单词拼写 → ④ 短语与句式转换（前半短语、后半句式）→ ⑤ 单元小测。
④ 句式的题由 TRICK_PICKS 人工挑选（题干带改写指令的东莞原题），脚本只校验，不替人选。
④ 前半的短语题跳过改写题，改写题只进句式块。

收录规则（2026-11-05 所有者定）：
- ① 考情：本单元所有考过的词（高一），全部进表，按题数降序、再按词头排序。
- ② 词性转换：只补「新形式」。候选 = 考法为「词性转换」、命中本单元、讲义里还没用过的题（高一、高二均可）。
  答案形式与词族里已有的形式相同的，一律不加；同一新形式有多道题时取年份最新的一道（同年高一优先）。
  新形式的题加进对应词族（已有词族追加；没有的按词族新建）。词族链只补新形式（hit=True）。
  已有词族的 atoms 从定稿读取，本脚本只输出新增的题，见 families 字段。
- ③ 单词拼写：题型为「单词拼写」、带中文提示、命中本单元、讲义其他位置未用过的题（高一、高二均可）。
  每单元 6–8 道，每词一道；词按考情表频次降序；同词取年份最新，同年高一优先。
- ⑤ 单元小测：沿用定稿里已定的题（不随 ② ③ 增减变动）；定稿不存在时才按剩余题取。
- 选题顺序：④ 短语先取题，② 只拿剩下的，③ 再拿，⑤ 小测不变。④ 的题因此不受 ② ③ 增减影响。
- 待校对.tsv 中的题默认排除。CHECKED_OK 列出的题已核对解析与答案无误，允许进入（见下）。

规则见 AGENTS.md「选题规则」。仅使用标准库，结果确定。

短语条标题：候选里取的是狂K 搭配原文，定稿时必须改成原题实际考的搭配（HANDOFF §5），狂K 只作参考、不标出处。
平局排序里的题号（如 `key=lambda x: (-年份, x[0])`）由 本地化/数据/卷号.json 固定：题号前三位不随语料增删而漂移。
"""
import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / '本地化' / '数据'
OUT = ROOT / '本地化' / '内容' / '同步-必修一-W-U2.json'

UNITS = {1: ('W', 'Welcome Unit', '欢迎单元', 'Welcome Unit'),
         2: ('U1', 'Unit 1', '青少年生活', 'Teenage Life'),
         3: ('U2', 'Unit 2', '环游世界', 'Travelling Around')}
# 中文标题：单元.json 无此字段，按人教版必修一目录补写
ZH_TITLE = {1: '欢迎单元', 2: '青少年生活', 3: '环游世界'}
BOOK = '必修第一册'
ORDER = [1, 2, 3]

# ③ 句式转换：人工从东莞原题中挑选（题干带改写指令的题）。每块 1–3 题，只用原题，不编题。
# 句式名 ≤6 字；柱注与公式在定稿 JSON 里填写。挑选结果由下面的校验检查：
# 题须在有效池内（去重后的代表题）、题干带改写指令（REWRITE_RE）、命中本单元。
TRICK_PICKS = {
    1: [('被动改主动', ['111-21', '155-20']),
        ('动词改短语', ['121-21', '158-21', '041-19']),
        ('形式主语', ['161-25'])],
    2: [('分词作状语', ['137-23']),
        ('定语从句', ['058-24']),
        ('倒装', ['066-25'])],
    3: [('进行时表将来', ['111-27']),
        ('动词改短语', ['050-29'])],
}
REWRITE_RE = re.compile(r'同义|改写|合并|转换|用.*翻译|句型')

# 待校对.tsv 里的题，经核对解析与答案无误，允许进入选题（2026-11-05 负责人审校前核过）。
# 087-10 organisations（英式拼写，与题干 organise 一致）；101-12 accommodation（住宿义不可数，复数亦可）；
# 143-16 Amazingly（句首副词，首字母大写）；107-19 brochures（For more 后用复数，解析一致）。核对后可从 待校对.tsv 移除，并删去此处。
CHECKED_OK = {'087-10', '101-12', '143-16', '107-19'}
CN_HINT_RE = re.compile(r'[（(][^（）()]*[一-鿿][^（）()]*[）)]')
PREV = ROOT / '本地化' / '内容' / '同步-必修一-W-U2.定稿.json'

TYPE_ORDER = ['语法填空', '完成句子', '单词拼写', '翻译', '单选', '其他']
KAOFA_LABEL = {'词性转换': '词性转换', '动词形式': '动词形式', '名词复数': '复数'}
KAOFA_ORDER = ['词性转换', '动词形式', '复数', '短语', '拼写', '翻译']
AUX = {'is', 'are', 'was', 'were', 'am', 'be', 'been', 'has', 'have', 'had', 'does', 'do', 'did', 'not'}
PLACEHOLDER = {'sb', 'sth', 'doing', 'one', 'oneself', 'the', 'a', 'an', 'someone', 'something'}
INSTR_RE = re.compile(r'\s*[（(][^（）()]*(?:填空|完成句子|翻译|转换|拼写|合并|汉译英|英译汉|改写)[^（）()]*[）)]\s*$')
BLANK_RE = re.compile(r'_{2,}')
SINGLE_RE = re.compile(r"[A-Za-z][A-Za-z\-']*")
HEAD_OK = re.compile(r"[A-Za-z][A-Za-z '\-]*")
GENERIC_INSTR = {'所给词的适当形式填空', '根据汉语提示完成句子', '根据汉语提示单词拼写', '翻译句子', '汉译英'}
CUE_KEY_RE = re.compile(r'同义|改写|转换|改为|变成|合并|强调|用|译|句型|被动|倒装|从句|语态|改编|句式')
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]*")


def read_jsonl(p):
    with open(p, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def norm_key(s):
    return re.sub(r'[\s\W_]+', '', (s or '').lower())


GENERIC_RE = re.compile(r'所给词|适当形式|正确形式|根据汉语提示|根据首字母|汉译英|翻译句子|单词拼写')


def is_generic(inner):
    return inner in GENERIC_INSTR or bool(GENERIC_RE.search(inner)) and not CUE_KEY_RE.search(inner.replace('翻译句子', '')) 


def cue_text(inner):
    return inner[:-4] if inner.endswith('句子') and '翻译' in inner[:-4] and inner.endswith('翻译句子') else inner.replace('翻译句子', '翻译')


def clean_stem_full(stem):
    """题干清洗：通用指令去掉；具体改写指令留作 cue（放句末）；句中的改写指令换成 → 连接两句。
    返回 (题干文本, [cue 文本，不含括号])。"""
    s = (stem or '').strip()
    cues = []
    while True:
        m = re.search(r'\s*[（(]([^（）()]*)[）)]\s*$', s)
        if not m:
            break
        inner = m.group(1).strip()
        if is_generic(inner):
            s = s[:m.start()].rstrip()
        elif CUE_KEY_RE.search(inner):
            cues.insert(0, cue_text(inner))
            s = s[:m.start()].rstrip()
        else:
            break

    def mid(m):
        inner = m.group(1).strip()
        if is_generic(inner):
            return ' '
        if CUE_KEY_RE.search(inner):
            if cue_text(inner) not in cues:
                cues.append(cue_text(inner))
            return ' → '
        return m.group(0)

    s = re.sub(r'\s*[（(]([^（）()]*)[）)]\s*', mid, s)
    s = re.sub(r'\s*\n\s*', ' ', s).strip()
    s = re.sub(r'(\s*→\s*)+', ' → ', s).strip(' →')
    s = re.sub(r'\s+', ' ', s).strip()
    return s, cues


def clean_stem(stem):
    return clean_stem_full(stem)[0]


def is_rewrite(q):
    """题干带改写指令（同义句转换、用…改写、用…合并、用…翻译、句型转换）。"""
    return any(REWRITE_RE.search(c) for c in clean_stem_full(q['题干'])[1])


def to_html_stem(stem):
    return BLANK_RE.sub('<span class="blank"></span>', stem)


def pick_answer_part(stem_raw, hint, answer):
    """多空题：按空位序号取答案的对应分段；单空或段数不符时整体返回。"""
    parts = [p.strip() for p in re.split(r'[；;]', answer) if p.strip()]
    nb = len(BLANK_RE.findall(stem_raw))
    if nb <= 1 or len(parts) != nb or not hint:
        return answer.strip()
    hints = re.findall(r'_{2,}\s*[（(]([^）)]*)[）)]', stem_raw)
    for j, h in enumerate(hints):
        if h.strip().lower() == hint.strip().lower():
            return parts[j]
    return parts[0]


def phrase_span(answer, phrase, head):
    """搭配命中：在答案句里框出短语形式（如 is addicted to）。框不出或过长则回退到词头。"""
    toks = list(WORD_RE.finditer(answer))
    pw = [w.lower() for w in WORD_RE.findall(phrase or '') if w.lower() not in PLACEHOLDER]
    hit = [i for i, t in enumerate(toks)
           if any(t.group(0).lower() == w or (len(w) >= 4 and t.group(0).lower()[:4] == w[:4]) for w in pw)]
    if not hit:
        return head
    s, e = hit[0], hit[-1]
    if s > 0 and toks[s - 1].group(0).lower() in AUX:
        s -= 1
    if e - s > 4:
        return head
    return answer[toks[s].start():toks[e].end()]


def form_of(hit, q):
    ans = re.sub(r'\s*(?:##|\|)\s*', ' / ', (q.get('答案') or '').strip())
    if hit['方式'] == '搭配':
        phrase = hit['证据'].split('｜')[0]
        f = phrase_span(re.sub(r'\s*[；;]\s*', ' ', ans), phrase, hit['词头'])
    elif hit['方式'] == '提示词':
        f = pick_answer_part(q.get('题干') or '', q.get('提示词'), ans)
    else:
        f = ans
    f = re.sub(r'\s+', ' ', f).strip().strip('。.，,;；').lower()
    return f


def first_sense(text):
    """取第一个义项，去掉词性标记与括号注，截到 8 个字以内。"""
    t = text or ''
    t = re.sub(r'^[❶❷❸]\s*', '', t)
    t = re.split(r'[❷❸]', t)[0]
    t = re.sub(r'\*[^*]*\*', '', t)
    t = re.sub(r'[［\[][^］\]]*[］\]]', '', t)
    t = re.sub(r'^[（(][^）)]*[）)]', '', t).strip()
    piece = re.split(r'[；;/／]', t)[0].strip()
    piece = re.sub(r'[（(][^）)]*[）)]$', '', piece).strip()
    return piece[:8]


def first_pos(text):
    m = re.search(r'\*([^*]+)\*', text or '')
    return m.group(1).strip() if m else ''


def chain_match(form, word):
    """形式里的某个词是否就是链上的词（屈折形按前缀认）。"""
    w = word.lower()
    for t in WORD_RE.findall(form):
        t = t.lower()
        if t in AUX or t in PLACEHOLDER:
            continue
        if t == w or (len(w) >= 5 and t.startswith(w)):
            return True
    return False


def stem_hint(q):
    return (q.get('提示词') or '').strip() or None


def main():
    Q = {q['id']: q for q in read_jsonl(DATA / '题库.jsonl')}
    U = {u['id']: u for u in read_jsonl(DATA / '题-单元.jsonl')}
    idx = json.loads((DATA / '词族索引.json').read_text(encoding='utf-8'))
    units_raw = json.loads((DATA / '单元.json').read_text(encoding='utf-8'))
    unit_by_seq = {u['序']: u for u in units_raw}
    checked = set()
    with open(DATA / '待校对.tsv', encoding='utf-8') as f:
        next(f)
        for line in f:
            if line.strip():
                checked.add(line.split('\t')[0].strip())

    # ---- 1. 命中清洗：词头过长（例句）剔除
    def ok_hit(h):
        return len((h.get('词头') or '').strip()) <= 30

    # ---- 2. 归属：每个词头归到它出现过的最早序
    owner_seqs = collections.defaultdict(set)
    for u in U.values():
        for h in u['命中']:
            if ok_hit(h):
                owner_seqs[h['词头']].add(h['序'])
    for ents in idx.values():
        for e in ents:
            owner_seqs[e['词头']].add(e['序'])
    owner = {w: min(s) for w, s in owner_seqs.items()}

    # ---- 3. 有效题：排除标记、解析为 null、待校对
    def valid(q, hi=False):
        """hi=False：考情与 ③④⑤ 用的池（高一）；hi=True：② ③ 单词与词族新形式另可用高二题。"""
        marks = set(q.get('标记') or [])
        if marks & {'疑似非单句题', '题型存疑'}:
            return False
        if q.get('解析') is None:
            return False
        if q['id'] in checked and q['id'] not in CHECKED_OK:
            return False
        seg = (q.get('标签') or '').split(' · ')[-1]
        if hi:
            if '高一' not in seg and '高二' not in seg:
                return False
        elif '高一' not in seg or '高二' in seg:
            return False
        if re.search(r'划线|画线|下划线', q.get('题干') or ''):
            return False
        # 多空题：空位数与答案分段数必须对得上，否则空位与答案无法一一对应
        nb = len(BLANK_RE.findall(q.get('题干') or ''))
        parts = [p for p in re.split(r'[；;]', q.get('答案') or '') if p.strip()]
        if nb >= 2 and len(parts) != nb:
            return False
        return True

    cand = {}
    for qid, q in Q.items():
        if not valid(q):
            continue
        hits = []
        for h in U[qid]['命中']:
            if not ok_hit(h):
                continue
            if h['方式'] in ('提示词', '答案') and not SINGLE_RE.fullmatch(h['词头']):
                continue
            if h['序'] in ORDER and owner.get(h['词头']) == h['序']:
                hits.append(h)
        if hits:
            cand[qid] = (q, hits)

    # ---- 4. 去重：重复组留年份最新；再按题干去重
    def newest(a, b):
        ka = (Q[a]['年份'] or 0, a)
        kb = (Q[b]['年份'] or 0, b)
        return a if ka >= kb else b

    kept = {}
    groups = collections.defaultdict(list)
    for qid in cand:
        g = Q[qid].get('重复组')
        if g is not None:
            groups[g].append(qid)
    drop_group = set()
    for g, ids in groups.items():
        best = ids[0]
        for i in ids[1:]:
            best = newest(best, i)
        drop_group.update(i for i in ids if i != best)
    stem_best = {}
    for qid in cand:
        if qid in drop_group:
            continue
        k = norm_key(clean_stem(Q[qid]['题干']))
        if k in stem_best:
            stem_best[k] = newest(stem_best[k], qid)
        else:
            stem_best[k] = qid
    pool_ids = set(stem_best.values())
    pool = {qid: cand[qid] for qid in pool_ids}

    # ---- 4b. ② 新形式与 ③ 单词拼写的候选池：高一、高二均可，重复组与题干去重（同上，年份最新优先）
    cand_hi = {}
    for qid, q in Q.items():
        if not valid(q, hi=True):
            continue
        hits = []
        for h in U[qid]['命中']:
            if not ok_hit(h):
                continue
            if h['方式'] in ('提示词', '答案') and not SINGLE_RE.fullmatch(h['词头']):
                continue
            if h['序'] in ORDER and owner.get(h['词头']) == h['序']:
                hits.append(h)
        if hits:
            cand_hi[qid] = (q, hits)
    hi_groups = collections.defaultdict(list)
    for qid in cand_hi:
        g = Q[qid].get('重复组')
        if g is not None:
            hi_groups[g].append(qid)
    hi_drop = set()
    for g, ids in hi_groups.items():
        best = ids[0]
        for i in ids[1:]:
            best = newest(best, i)
        hi_drop.update(i for i in ids if i != best)
    hi_stem = {}
    for qid in cand_hi:
        if qid in hi_drop:
            continue
        k = norm_key(clean_stem(Q[qid]['题干']))
        hi_stem[k] = newest(hi_stem[k], qid) if k in hi_stem else qid
    hi_reps = set(hi_stem.values())

    def fresh_hi(already):
        """② ③ 可用的候选：去掉已用题、与已用题同重复组或同题干的题。"""
        ug = {Q[i].get('重复组') for i in already} - {None}
        us = {norm_key(clean_stem(Q[i]['题干'])) for i in already}
        return [i for i in hi_reps
                if i not in already and Q[i].get('重复组') not in ug
                and norm_key(clean_stem(Q[i]['题干'])) not in us]

    def is_gaoyi(q):
        return '高一' in ((q.get('标签') or '').split(' · ')[-1])

    def prefer_key(qid):
        """同条件取舍：年份新优先；同年高一优先；再按题号。"""
        return (Q[qid]['年份'] or 0, 1 if is_gaoyi(Q[qid]) else 0, qid)

    prev = json.loads(PREV.read_text(encoding='utf-8')) if PREV.exists() else None
    prev_units = {u['序']: u for u in prev['单元']} if prev else {}
    prev_all_ids = set()
    if prev:
        def _walk(n):
            if isinstance(n, dict):
                if 'id' in n:
                    prev_all_ids.add(n['id'])
                for v in n.values():
                    _walk(v)
            elif isinstance(n, list):
                for v in n:
                    _walk(v)
        _walk(prev)

    def form_for(qid, w, seq):
        """题在词族 w 下的答案形式（与 form_of 同口径）。"""
        hits = [h for h in U[qid]['命中'] if h['词头'] == w and h['序'] == seq] or \
               [{'方式': '答案', '词头': w, '证据': ''}]
        return form_of(hits[0], Q[qid])

    def prev_family_forms(seq, w):
        pu = prev_units.get(seq)
        if not pu:
            return set()
        for f in pu['families']:
            if f['词头'] == w:
                return {form_for(a['id'], w, seq) for a in f['atoms']}
        return set()
    # ---- 6. ③ 句式：人工挑选的改写题须在有效池内（去重后的代表题）、题干带改写指令、命中本单元
    trick_ids = set()
    for seq, blocks in TRICK_PICKS.items():
        for name, ids in blocks:
            if len(name) > 6:
                raise SystemExit(f'句式名超过 6 字：{name}')
            for qid in ids:
                if qid not in pool or not is_rewrite(Q[qid]) or not any(h['序'] == seq for h in pool[qid][1]):
                    raise SystemExit(f'句式选题无效：{qid}（{name}）')
                if qid in trick_ids:
                    raise SystemExit(f'句式选题重复：{qid}')
                trick_ids.add(qid)

    # ---- 5. 统计：词头 → 题、形式、考法（只统计 owner 为 1–3 的命中）
    head_qs = collections.defaultdict(list)     # 词头 → [(qid, hit)]
    for qid, (q, hits) in pool.items():
        seen = set()
        for h in hits:
            if h['词头'] in seen:
                continue
            seen.add(h['词头'])
            head_qs[(owner[h['词头']], h['词头'])].append((qid, h))

    def labels_for(qid, h):
        q = Q[qid]
        out = set()
        if q['题型'] == '翻译':
            out.add('翻译')
        if h['方式'] == '搭配':
            out.add('短语')
        if q['题型'] == '单词拼写':
            out.add('拼写')
        kf = U[qid].get('考法')
        if kf in KAOFA_LABEL and h['方式'] == '提示词':
            out.add(KAOFA_LABEL[kf])
        return out

    # 单元词汇索引
    vocab = {}
    for u in units_raw:
        for e in u['词汇']:
            vocab.setdefault(e['词'], e)
    phrase_zh = {}
    for u in units_raw:
        for e in u['词汇']:
            for c in e.get('搭配', []):
                phrase_zh.setdefault(c['短语'], c['释义'])
    unit_meta = {u['序']: u for u in units_raw}

    report = collections.defaultdict(list)
    skeleton = {'生成': '本地化/脚本/同步选题.py', '书': BOOK, '单元': []}

    used = set(trick_ids)   # 全书已用题：③ 句式的题先预留，② ③ 前半 ⑤ 不再用

    for seq in ORDER:
        code, title_en_key, zh, en = UNITS[seq]
        uraw = unit_meta[seq]
        heads = {w: v for (s, w), v in head_qs.items() if s == seq}
        # ① 考情总表
        freq_rows = []
        for w, lst in heads.items():
            if not HEAD_OK.fullmatch(w):
                continue
            forms = collections.Counter()
            labels = collections.Counter()
            for qid, h in lst:
                q = Q[qid]
                forms[form_of(h, q)] += 1
                labels.update(labels_for(qid, h))
            ordered = sorted(labels, key=lambda k: (-labels[k], KAOFA_ORDER.index(k)))[:2]
            freq_rows.append({
                '词头': w,
                'forms': [{'form': f, 'n': n} for f, n in sorted(forms.items(), key=lambda x: (-x[1], x[0]))],
                '考法': ordered,
                '题数': len(lst),
            })
        freq_rows.sort(key=lambda r: (-r['题数'], r['词头']))

        # 归属本单元的题（用于 ②③⑤ 选题）
        def qs_for(w):
            return [(qid, h) for qid, h in heads.get(w, [])]

        def lst_all_for(w):
            return heads.get(w, [])

        # ③ 短语与句型：搭配命中（完成句子、翻译）
        pgroups = collections.defaultdict(list)   # (词头, 短语) → [(qid, h)]
        for w, lst in heads.items():
            for qid, h in lst:
                if qid in used or h['方式'] != '搭配' or is_rewrite(Q[qid]):
                    continue
                phrase = h['证据'].split('｜')[0]
                pgroups[(w, phrase)].append((qid, h))
        porder = sorted(pgroups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        phrases = []
        for (w, phrase), lst in porder:
            if len(phrases) == 6:
                break
            lst = sorted(lst, key=lambda x: (-(Q[x[0]]['年份'] or 0), x[0]))
            pick = []
            for qid, h in lst:
                if qid in used:
                    continue
                pick.append(qid)
                if len(pick) == 2:
                    break
            if not pick:
                continue
            for qid in pick:
                used.add(qid)
            phrases.append({'短语': phrase, '释义': phrase_zh.get(phrase, ''), '词头': w,
                            'atoms': [build_atom(Q[qid]) for qid in pick], 'gloss': ''})
        # ② 词性转换：只补新形式。答案形式在词族里已有的不加；同一新形式取 prefer_key 最大的一道。
        fresh = fresh_hi(used | prev_all_ids)
        new_forms = collections.defaultdict(dict)   # 词头 → {形式: qid}
        for qid in fresh:
            q = Q[qid]
            if U[qid].get('考法') != '词性转换':
                continue
            for h in cand_hi[qid][1]:
                if h['序'] != seq or h['方式'] != '提示词':
                    continue
                w = h['词头']
                f = form_of(h, q)
                if not f or f in prev_family_forms(seq, w):
                    continue
                cur = new_forms[w].get(f)
                if cur is None or prefer_key(qid) > prefer_key(cur):
                    new_forms[w][f] = qid
        families = []
        fam_rows = [r for r in freq_rows if r['词头'] in new_forms]   # 考情表里有该词头的才入词族
        fam_rows.sort(key=lambda r: (-r['题数'], r['词头']))
        for w in new_forms:
            if w not in {r['词头'] for r in fam_rows}:
                report[seq].append(('新形式词头不在考情表（未入选）', w))
        for r in fam_rows:
            w = r['词头']
            picks = sorted(new_forms[w].values(), key=prefer_key, reverse=True)
            for qid in picks:
                used.add(qid)
            # 词族链：词性转换题里考过的形式（高一池）＋本次新增的形式
            chain_forms = collections.Counter()
            for qid, h in lst_all_for(w):
                if U[qid].get('考法') == '词性转换' and h['方式'] == '提示词':
                    chain_forms[form_of(h, Q[qid])] += 1
            for qid in picks:
                chain_forms[form_for(qid, w, seq)] += 1
            base = vocab.get(w)
            chain = []
            if base:
                chain.append({'词': w, '词性': first_pos(base['词性释义']), '释义': first_sense(base['词性释义']),
                              'hit': False, '来源': '词头'})
            else:
                report[seq].append(('词头不在词汇表', w))
                chain.append({'词': w, '词性': '', '释义': '', 'hit': False, '来源': '词头'})
            for d in (base['派生'] if base else []):
                chain.append({'词': d['词'], '词性': d['词性'], '释义': first_sense(d['释义']),
                              'hit': False, '来源': '派生'})
            for f in chain_forms:
                if not f:
                    continue
                # 匹配：优先精确词，其次前缀
                best = None
                for c in chain:
                    if chain_match(f, c['词']):
                        if best is None or len(c['词']) > len(best['词']):
                            best = c
                if best is not None:
                    best['hit'] = True
                else:
                    chain.append({'词': f, '词性': '', '释义': '', 'hit': True, '来源': '补入'})
                    report[seq].append(('补入形式(需补词性释义)', w, f))
            while len(chain) > 4:
                for i in range(len(chain) - 1, 0, -1):
                    if not chain[i]['hit']:
                        del chain[i]
                        break
                else:
                    break
            families.append({
                '词头': w,
                '题数': r['题数'],
                'chain': chain,
                'atoms': [build_atom(Q[qid]) for qid in picks],
                'gloss': '',
            })

        # ③ 单词拼写：题型为单词拼写、带中文提示、命中本单元，讲义其他位置未用过。
        # 每词一道；词按考情表频次降序；同词取 prefer_key 最大（年份新，同年高一优先）；6–8 道。
        fresh = fresh_hi(used | prev_all_ids)
        freq_map = {r['词头']: r['题数'] for r in freq_rows}
        sp_words = collections.defaultdict(list)
        for qid in fresh:
            q = Q[qid]
            if q['题型'] != '单词拼写' or ('疑似拼写错' in (q.get('标记') or []) and qid not in CHECKED_OK):
                continue
            stem = clean_stem(q['题干'])
            if len(BLANK_RE.findall(stem)) != 1 or not CN_HINT_RE.search(stem):
                continue
            for w in {h['词头'] for h in cand_hi[qid][1] if h['序'] == seq}:
                sp_words[w].append(qid)
        spelling = []
        for w in sorted(sp_words, key=lambda w: (-freq_map.get(w, 0), w)):
            if len(spelling) == 8:
                break
            for qid in sorted(sp_words[w], key=prefer_key, reverse=True):
                if qid not in used:
                    spelling.append(qid)
                    used.add(qid)
                    break
        if len(spelling) < 6:
            report[seq].append(('单词拼写不足 6 道', len(spelling)))

        # ③ 后半：句式块（题在 TRICK_PICKS 里人工挑定）
        tricks = [{'句式': name, 'gloss': '', 'formula': '',
                   'atoms': [build_atom(Q[qid]) for qid in ids]}
                  for name, ids in TRICK_PICKS.get(seq, [])]

        # ⑤ 单元小测：未用到的本单元题，按题型混排，最多 8 道
        leftovers = collections.defaultdict(list)
        for w, lst in heads.items():
            for qid, h in lst:
                if qid in used:
                    continue
                leftovers[Q[qid]['题型']].append(qid)
        for t in leftovers:
            leftovers[t] = sorted(set(leftovers[t]), key=lambda i: (-(Q[i]['年份'] or 0), i))
        quiz = []
        types = [t for t in TYPE_ORDER if leftovers.get(t)] if not prev_units.get(seq) else []
        if prev_units.get(seq):
            quiz = [a['id'] for a in prev_units[seq]['quiz']]
            for qid in quiz:
                used.add(qid)
        while len(quiz) < 8 and any(leftovers[t] for t in types):
            for t in types:
                if len(quiz) == 8:
                    break
                if leftovers[t]:
                    qid = leftovers[t].pop(0)
                    if qid in used:
                        continue
                    used.add(qid)
                    quiz.append(qid)

        # 统计
        uniq_files = {Q[qid]['文件'] for qid, _ in pool.items() if any(owner[h['词头']] == seq for h in pool[qid][1])}
        phrase_count = sum(len(e.get('搭配', [])) for e in uraw['词汇'])
        unit_qids = {qid for w, lst in heads.items() for qid, _ in lst}
        years = [Q[i]['年份'] for i in unit_qids if Q[i]['年份']]
        n_kaofa = sum(1 for i in unit_qids if U[i].get('考法') == '词性转换')
        n_phr = len({qid for (w, ph), lst in pgroups.items() for qid, _ in lst})
        skeleton['单元'].append({
            '序': seq, 'data_no': code, 'unit_book': f'{BOOK}　{title_en_key}',
            'chips': {'year_range': f'{min(years)}–{max(years)}' if years else '',
                      'n_questions': len(unit_qids), 'n_kaofa': n_kaofa, 'n_phrase': n_phr},
            'h2': en, 'zh': ZH_TITLE[seq],
            'stats': {'卷数': len(uniq_files), '词数': len(uraw['词汇']), '短语数': phrase_count,
                      '句式题数': sum(len(t['atoms']) for t in tricks)},
            'freq': freq_rows,
            'families': families,
            'spelling': [build_atom(Q[qid]) for qid in spelling],
            'phrases': phrases,
            'tricks': tricks,
            'quiz': [build_atom(Q[qid]) for qid in quiz],
        })

    # 编号：每单元内 ② ③ ④（短语、句式）⑤ 连续编号；答案同号
    for u in skeleton['单元']:
        n = 0
        for fam in u['families']:
            for a in fam['atoms']:
                n += 1
                a['no'] = n
        for a in u['spelling']:
            n += 1
            a['no'] = n
        for ph in u['phrases']:
            for a in ph['atoms']:
                n += 1
                a['no'] = n
        for t in u['tricks']:
            for a in t['atoms']:
                n += 1
                a['no'] = n
        for a in u['quiz']:
            n += 1
            a['no'] = n
        u['numbered_total'] = n

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(skeleton, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'写入 {OUT}')
    for u in skeleton['单元']:
        print(u['data_no'], u['stats'], '频次行', len(u['freq']), '词族', len(u['families']),
              '短语', len(u['phrases']), '句式', [(t['句式'], [a['id'] for a in t['atoms']]) for t in u['tricks']],
              '小测', len(u['quiz']), '编号至', u['numbered_total'])
    for seq, items in sorted(report.items()):
        for it in items:
            print('报告', UNITS[seq][0], it, file=sys.stderr)


def build_atom(q):
    stem, cues = clean_stem_full(q['题干'])
    if q['题型'] in ('完成句子', '翻译') and not BLANK_RE.search(stem):
        # 原句改写 / 翻译：没有书写空的，补一个在句末
        stem = stem + ' → ___'
    return {
        'id': q['id'],
        'no': None,
        '标签': q['标签'],
        '题型': q['题型'],
        '题干': stem,
        '题干HTML': to_html_stem(stem),
        'cue': cues,
        '提示词': q.get('提示词'),
        '答案': re.sub(r'\s*(?:##|\|)\s*', ' / ', (q.get('答案') or '').strip()),
        '解析': q.get('解析') or '',
        '句意': q.get('句意') or '',
        'reason': '',
    }


if __name__ == '__main__':
    main()
