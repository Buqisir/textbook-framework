#!/usr/bin/env python3
"""解析《狂K重点》文字稿（语料/狂K重点/*.md），按单元产出结构化数据。

运行：python3 -I 本地化/脚本/狂K.py
输入：语料/狂K重点/*.md（只读，不修改）
输出：本地化/数据/单元.json、本地化/数据/词族索引.json
解析告警写到 stderr。仅使用标准库，结果确定性可重复。
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / '语料' / '狂K重点'
OUT_DIR = ROOT / '本地化' / '数据'

SOURCES = [
    ('必修1必修2.md', ['必修一', '必修二']),
    ('必修3.md', ['必修三']),
    ('选修1选修2.md', ['选必一', '选必二']),
    ('选修3选修4.md', ['选必三', '选必四']),
]

WARN = []


def warn(fname, lineno, msg):
    WARN.append(f'{fname}:{lineno}: {msg}')


# ---------------------------------------------------------------- 正则
PAGE_RE = re.compile(r'^<!--\s*page-\d+\s*-->$')
RUNNING_RE = re.compile(r'^#+\s*狂\s*K\s*重点.*$')
CUT_RE = re.compile(r'包学习——|高质量的学习搭子|^［封底|^\[封底|^［插画|^【封底页|扫码获取更多学习资源')
UNIT_RE = re.compile(
    r'^(?:(?P<book>(?:选择性)?必修\s*第?[一二三四]册)[\s　]*)?'
    r'(?:(?P<w>Welcome\s+Unit)|Unit\s*(?P<n>\d+)(?!\d))(?P<rest>.*)$')
BOOK_RE = re.compile(r'(?P<pre>选择性)?必修\s*第?(?P<n>[一二三四])册')
CN_NUM = {'一': '一', '二': '二', '三': '三', '四': '四'}

_POS_LIST = sorted(['n', 'v', 'vt', 'vi', 'adj', 'adv', 'prep', 'conj', 'pron', 'num', 'det',
                    'abbr', 'int', 'aux', 'modal', 'art', 'pl', 'interj'], key=len, reverse=True)
POS = '(?:' + '|'.join(_POS_LIST) + ')'
POS_SEQ = POS + r'\.?(?:\s*(?:&|/|和)\s*' + POS + r'\.?)*(?=[\s*［（\[]|$)'
DERIV_RE = re.compile(
    r"^(?P<w>[A-Za-z][A-Za-z\-']*)\s+\*?(?P<pos>" + POS_SEQ + r")\*?\s*(?P<m>.*)$")
POS_START_RE = re.compile(r'^' + POS + r'\.\s')
REL_DERIV_RE = re.compile(
    r"^(?P<w>[A-Za-z][A-Za-z\-'/]*)\s+\*?(?P<pos>" + POS_SEQ + r")\*?\s*(?P<m>.*)$")
PHRASE_RE = re.compile(
    r"^(?P<p>(?:[A-Za-z0-9 .,'’/\-&?=()]|（[A-Za-z0-9 .,'’/\-&?=]*）)+)\s*(?P<m>.*)$")
HEAD_RE = re.compile(
    r"^[A-Za-z](?:[A-Za-z0-9 .'’\-/&?]|（[A-Za-z0-9 .,'’/\-?]*）|\([A-Za-z0-9 .,'’/\-?]*\))*")
NUM_PREFIX_RE = re.compile(r'^(?:\d+[\.\s]\s*)')
PLAIN_LABEL_RE = re.compile(
    r'^(?P<name>常用搭配|常见用法|常见搭配|联想拓展|联想记|联想词|同义词|近义词|反义词|'
    r'同义短语|近义短语|特别注意|易混辨析|知识拓展|熟词生义|释义|教材原句(?: P\d+)?|'
    r'经典例句|衔接课文|课文原义|易混词|原典溯源)(?=[\s\u3000]|$)(?P<rest>.*)$')
BRACKET_LABEL_RE = re.compile(r'^【(?P<name>[^】]{1,12})】(?P<rest>.*)$')
NUMBOLD_RE = re.compile(r'^\d+\.\s*\*\*(?P<in>[A-Za-z][^*]*?)\*\*(?P<rest>.*)$')
HEAD_POS_RE = re.compile(r'^(?P<h>.*?)\s+' + POS_SEQ)
LABEL_RE = re.compile(r'^\*\*(?P<name>[^*]+?)\*\*\s*(?P<rest>.*)$')
CIRC = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳'
SENSE_MARKS = '❶❷❸❹❺❻❼❽❾❿➊➋➌➍➎➏➐➑➒➓'
CN_CHAR = r'　-〿぀-ヿ㐀-䶿一-鿿＀-￯'
SENT_END = '。！？!?.”"」』'  # 句末标点：硬换行只在句中断开时才接回
SENTENCE_RE = re.compile(r'[。！？]')
EXT_MARKS = ('✎', '✓', '∠')  # 基础词汇表格中“拓展”标记的几种字形
PAGE_REF_RE = re.compile(r'\s*[〔\[]P\d+[〕\]]')
SENSE_START_RE = re.compile(r'^[' + SENSE_MARKS + r']')
ITEM_START_RE = re.compile(r'^(?:\d+\.\s*|[' + CIRC + SENSE_MARKS + r'])')

# 标签 -> 处理方式
MIXED = ('mixed',)
IGNORE = ('ignore',)


def label_kind(name):
    n = re.sub(r'\s+', '', name)
    if n.startswith('教材原句') or n.startswith('教材例句'):
        return IGNORE
    if n in ('链接课文', '体验感悟', '封底页'):
        return IGNORE
    table = {
        '常用搭配': MIXED, '常见用法': MIXED, '常见搭配': MIXED, '联想拓展': MIXED,
        '联想记': MIXED, '联想词': MIXED,
        '同义词': ('rel', '同', False), '同义短语': ('rel', '同', True),
        '近义词': ('rel', '近', False), '近义短语': ('rel', '近', True),
        '反义词': ('rel', '反', False),
        '释义': IGNORE, '特别注意': IGNORE, '易混辨析': IGNORE, '易混词': IGNORE,
        '知识拓展': IGNORE, '经典例句': IGNORE, '衔接课文': IGNORE, '课文原义': IGNORE,
        '原典溯源': IGNORE, '方法总结': IGNORE, '熟词生义': IGNORE, '句意': IGNORE,
        '语段课文': IGNORE, '学法': IGNORE, '拓展': IGNORE, '连接词': IGNORE,
        '连接副词': IGNORE, '连接代词': IGNORE, '定语从句': IGNORE, '句式': IGNORE,
    }
    return table.get(n)


def norm_key(s):
    return re.sub(r'[#*【】\[\]\s]', '', s)


def join_text(a, b):
    if not a:
        return b
    if not b:
        return a
    if re.search(f'[{CN_CHAR}]$', a) or re.match(f'[{CN_CHAR}]', b):
        return a + b
    return a + ' ' + b


def ends_terminal(s):
    return s.rstrip()[-1:] in SENT_END


def is_struct(s):
    return bool(re.match(
        r'^(?:#|\||- |\* |●|\*\*|【|📖|句意|（|\(|<!--|\d+\.\s|\d+、|[' + CIRC + SENSE_MARKS + r'])', s))


def is_header(s):
    return s.startswith('#') or s.startswith('**')


# ---------------------------------------------------------------- 预处理
def tokenize(fname, lines):
    """去掉页码注释、分页符、运行页眉，保留空行与分页标记；返回 token 列表。"""
    toks = []
    page = False
    blank = False
    for i, raw in enumerate(lines, 1):
        s = raw.strip()
        if CUT_RE.search(s):  # 文末宣传页（封底/二维码/App 推广）：之后的内容不属于正文
            break
        if PAGE_RE.match(s):
            page = True
            continue
        if s == '---':
            blank = True
            continue
        if re.match(r'^[（(]?续表[）)]?$', s):
            page = True
            blank = True
            continue
        if RUNNING_RE.match(s):
            continue
        quoted = s.startswith('>')
        if quoted:
            s = s[1:].strip()
        if s == '':
            blank = True
            continue
        toks.append({'text': s, 'page': page, 'blank': blank, 'lineno': i, 'quoted': quoted})
        page = False
        blank = False
    return toks


def logical_lines(fname, toks):
    """把硬换行、跨页断句接回去，得到逻辑行。"""
    out = []
    for t in toks:
        s = t['text']
        if out:
            prev = out[-1]
            p = prev['text']
            can_join = (not is_struct(s)) and (not is_header(p)) and not p.startswith('|')
            if p.startswith('|'):
                can_join = (not s.startswith('|')) and (not p.endswith('|')) and not is_struct(s)
            if not t['blank'] and can_join:
                prev['quoted'] = prev['quoted'] and t['quoted']
                prev['parts'].append(s)
                prev['text'] = join_text(p, s)
                prev['joined'] += 1
                continue
            # 跨页断句：前一行若是加粗标签行（如 **教材原句 P4**）也接回；标题行不接
            page_ok = ((not is_struct(s)) and (not p.startswith(('#', '|')))
                       and not re.match(r'^\*\*\d', p) and not ends_terminal(p))
            if t['page'] and page_ok:
                prev['parts'].append(s)
                prev['text'] = join_text(p, s)
                prev['joined'] += 1
                prev['page_joins'] += 1
                continue
        out.append({'text': s, 'lineno': t['lineno'], 'joined': 0, 'page_joins': 0,
                    'quoted': t['quoted'], 'parts': [s]})
    return out


# ---------------------------------------------------------------- 词条与子项解析
def clean_item(text):
    t = text.replace('**', '')
    t = re.sub(r'(?<!\*)\*(?!\*)', '', t)  # 单个星号（强调/斜体）
    t = t.replace('✎', '').strip()
    return re.sub(r'[ \t]+', ' ', t).strip()


def strip_circled(t):
    return re.sub(r'^[' + CIRC + r']\s*', '', t)


def add_deriv(E, seg):
    m = DERIV_RE.match(seg)
    if not m:
        return False
    if m.group('w').lower() == E['词'].lower():
        return True  # 词条自身的词性行不是派生词
    pos = re.sub(r'\s+', ' ', m.group('pos')).strip()
    item = {'词': m.group('w'), '词性': pos, '释义': m.group('m').strip()}
    if item not in E['派生']:
        E['派生'].append(item)
    return True


def add_phrase(E, seg):
    if not re.search(r'[A-Za-z]', seg) or SENTENCE_RE.search(seg):
        return False
    parts = [x.strip() for x in seg.split('；')]
    if len(parts) > 1 and all(re.match(r'^[A-Za-z]', x) and not re.search(f'[{CN_CHAR}]', x)
                              for x in parts):
        # 仅列短语、不带释义的“；”并列（如 focus on；be absorbed in）
        for x in parts:
            item = {'短语': x, '释义': ''}
            if item not in E['搭配']:
                E['搭配'].append(item)
        return True
    if re.match(r'^' + POS_SEQ + r'\.?\s', seg + ' '):
        return True  # 仅有词性、没有词的残片（如 “n. 款待”）不单独成条
    m = PHRASE_RE.match(seg)
    if not m:
        return False
    p = m.group('p').strip()
    meaning = (m.group('m') or '').strip()
    pos = re.match(r'^(.*?[A-Za-z])\s+(' + POS_SEQ + r'\.)\s*(.*)$', p)
    if pos:  # 短语里夹带词性（如 owing to prep.）：词性并入释义
        p = pos.group(1)
        meaning = (pos.group(2) + ' ' + pos.group(3) + ' ' + meaning).strip()
    if len(p.split()) > (16 if '=' in p else 9):
        return False
    item = {'短语': p, '释义': meaning}
    if item not in E['搭配']:
        E['搭配'].append(item)
    return True


def add_mixed(E, text):
    """搭配/派生类混合文本：按项拆分后分别归入派生或搭配。"""
    t = clean_item(text)
    for seg in re.split(r'　+(?=[A-Za-z])|(?=[' + CIRC + r'])', t):
        seg = strip_circled(seg.strip()).strip()
        if not seg or SENTENCE_RE.search(seg):
            continue
        if add_deriv(E, seg):
            continue
        add_phrase(E, seg)


def add_rel(E, text, typ, phrase=False):
    t = clean_item(text)
    last = None
    for seg in re.split(r'　+(?=[A-Za-z①②③④⑤⑥⑦⑧⑨⑩])|(?=[' + CIRC + r'])', t):
        seg = strip_circled(seg.strip()).strip()
        if not seg or SENTENCE_RE.search(seg):
            continue
        if POS_START_RE.match(seg) and last is not None:
            last['释义'] = (last['释义'] + ' ' + seg).strip()
            continue
        m = REL_DERIV_RE.match(seg)
        if m:
            last = {'类型': typ, '词': m.group('w'),
                    '词性': re.sub(r'\s+', ' ', m.group('pos')).strip(),
                    '释义': m.group('m').strip()}
            E['近反义'].append(last)
            continue
        for part in re.split(r'[；;]', seg):
            part = part.strip()
            if not part:
                continue
            if phrase:
                pm = PHRASE_RE.match(part)
                if pm:
                    last = {'类型': typ, '词': pm.group('p').strip(), '词性': '',
                            '释义': (pm.group('m') or '').strip()}
                    E['近反义'].append(last)
            elif re.match(r"^[A-Za-z][A-Za-z\-'’ ]*$", part):
                last = {'类型': typ, '词': part, '词性': '', '释义': ''}
                E['近反义'].append(last)
            else:
                pm = PHRASE_RE.match(part)
                if pm and re.search(r'[A-Za-z]', part):
                    last = {'类型': typ, '词': pm.group('p').strip(), '词性': '',
                            '释义': (pm.group('m') or '').strip()}
                    E['近反义'].append(last)


def new_entry(U, text, level, fname, lineno):
    text = text.strip()
    m = HEAD_RE.match(text)
    if not m:
        warn(fname, lineno, f'词条标题无法解析: {text[:40]}')
        return None
    head = m.group(0).rstrip(' ')
    rest = text[m.end():]
    pm = HEAD_POS_RE.match(head)
    if pm and len(pm.group('h')) > 0:
        head = pm.group('h')
        rest = text[len(head):]
    E = {'词': re.sub(r'\s+', ' ', head).strip(), '层级': level,
         '词性释义': rest.strip(' 　'), '派生': [], '搭配': [], '近反义': [],
         '_senses': [], '_label': None, '_line': lineno}
    U['词汇'].append(E)
    return E


def apply_label(E, name, rest, fname):
    """切换当前标签，并处理标签同行的内容。"""
    kind = label_kind(name)
    if kind is None:
        warn(fname, E['_line'], f'未知标签 {name!r}')
    E['_label'] = kind
    rest = rest.strip()
    if rest and kind == MIXED:
        add_mixed(E, rest)
    elif rest and kind and kind[0] == 'rel':
        add_rel(E, rest, kind[1], kind[2])


def feed_entry(E, s, fname):
    """把词条下的一个物理行喂给词条：义项、标签、搭配、派生、近反义。"""
    core = s.replace('**', '').strip() if s.startswith('**') else s
    if SENSE_START_RE.match(core):
        E['_senses'].append(core)
        return
    if not s.startswith('**'):
        pm = PLAIN_LABEL_RE.match(s)
        if pm:
            apply_label(E, pm.group('name'), pm.group('rest'), fname)
            return
    if s.startswith('**'):
        m = LABEL_RE.match(s)
        if m:
            apply_label(E, m.group('name'), m.group('rest'), fname)
        return
    bm = BRACKET_LABEL_RE.match(s)
    if bm and bm.group('name') not in ('派', '同', '近', '反'):
        apply_label(E, bm.group('name'), bm.group('rest'), fname)
        return
    if s.startswith('●'):
        return
    if s.startswith('- ') or s.startswith('* '):
        # 联想拓展/常用搭配下的小写短语列表；大写开头的是例句
        body = s[2:].strip()
        if E['_label'] == MIXED and re.match(r'^[a-z]', body):
            add_mixed(E, body)
        return
    if s.startswith('【派】'):
        add_mixed(E, s[3:])
        return
    for tag, typ in (('【同】', '同'), ('【近】', '近'), ('【反】', '反')):
        if s.startswith(tag):
            add_rel(E, s[len(tag):], typ)
            return
    if s.startswith('【') or s.startswith('📖'):
        return
    if s[0] in CIRC and E['_label'] is None and re.match(r'^[' + CIRC + r']\s*' + POS + r'\.', s):
        E['_senses'].append(s)  # 无标签时的 “① vt. …” 义项行
        return
    if E['_label'] == MIXED:
        add_mixed(E, s)
    elif E['_label'] and E['_label'][0] == 'rel':
        add_rel(E, s, E['_label'][1], E['_label'][2])


def make_basic(U, word, cell, fname, lineno):
    """基础词汇表格行 -> 词条。"""
    E = {'词': word.strip().replace('*', ''), '层级': '基础', '词性释义': '', '派生': [],
         '搭配': [], '近反义': [], '_senses': [], '_label': None, '_line': lineno}
    U['词汇'].append(E)
    meaning = []
    ext = False
    for seg in [x.strip() for x in cell.split('<br>') if x.strip()]:
        if seg[:1] in EXT_MARKS:
            ext = True
            seg = seg[1:].strip()
            if seg.startswith(('【熟词生义】', '【生义】')):
                meaning.append(seg)
                continue
        elif seg.startswith(('【熟词生义】', '【生义】')):
            meaning.append(seg)
            continue
        if not ext:
            meaning.append(seg)
            continue
        if seg.startswith('【派】'):
            add_mixed(E, seg[3:])
        elif seg.startswith(('【同】', '【近】', '【反】')):
            tag = {'【同】': '同', '【近】': '近', '【反】': '反'}[seg[:3]]
            add_rel(E, seg[3:], tag)
        else:
            add_mixed(E, seg)
    E['词性释义'] = ' / '.join(meaning)
    return E


# ---------------------------------------------------------------- 主解析
def parse_file(fname, books):
    lines = (SRC_DIR / fname).read_text(encoding='utf-8').split('\n')
    toks = tokenize(fname, lines)
    lls = logical_lines(fname, toks)
    units = []
    S = {'bidx': 0, 'cur': None, 'part': None, 'sub': None, 'sent': None,
         'gram': None, 'started': False, 'books': books, 'units': units,
         'page_joins': 0}

    def set_book(name, lineno):
        if name not in books:
            warn(fname, lineno, f'册 {name} 不在本文件册列表 {books} 中')
            return
        S['bidx'] = books.index(name)
        S['cur'] = None

    for ln in lls:
        s = ln['text']
        lineno = ln['lineno']
        S['page_joins'] += ln['page_joins']
        if not S['started']:
            if s.startswith('#') and UNIT_RE.match(s.lstrip('#').strip()) and '…' not in s:
                S['started'] = True
            else:
                continue
        # ---- 册 / 单元标题
        if s.startswith('#'):
            h = s.lstrip('#').strip()
            um = UNIT_RE.match(h)
            if um:
                on_unit_header(S, um, fname, lineno)
                continue
            bm = BOOK_RE.search(h)
            if bm and '…' not in h:
                name = ('选必' if bm.group('pre') else '必修') + CN_NUM[bm.group('n')]
                set_book(name, lineno)
                continue
        S['_quoted_now'] = ln.get('quoted', False)
        S['_parts'] = ln.get('parts', [s])
        U = S['cur']
        if U is None:
            warn(fname, lineno, f'单元外内容: {s[:30]}')
            continue
        key = norm_key(s)
        # ---- 部分与小节
        if '词汇分层解析' in key and len(key) < 16:
            S['part'], S['sub'], S['sent'], S['gram'] = 'I', None, None, None
            continue
        if '句子分类探究' in key and len(key) < 16:
            S['part'], S['sub'], S['sent'], S['gram'] = 'II', None, None, None
            continue
        if '单元语法归纳' in key and len(key) < 16:
            S['part'], S['sub'], S['sent'], S['gram'] = 'III', None, None, None
            continue
        is_sec = s.startswith(('#', '**', '【')) or len(key) <= 12
        if is_sec:
            if '基础词汇' in key:
                S['part'], S['sub'] = 'I', '基础'
                continue
            if '探究词汇' in key:
                S['part'], S['sub'] = 'I', '探究'
                continue
            if '差距词汇' in key:
                S['part'], S['sub'] = 'I', '差距'
                continue
            if '长难句' in key:
                S['part'], S['sub'], S['sent'] = 'II', '长难', None
                continue
            if '高频句式' in key:
                S['part'], S['sub'], S['sent'] = 'II', '高频', None
                continue
        if S['part'] == 'I':
            on_part1(S, U, s, fname, lineno)
        elif S['part'] == 'II':
            on_part2(S, U, s, fname, lineno)
        elif S['part'] == 'III':
            on_part3(S, U, s, fname, lineno)
        else:
            pass  # 引言等，忽略
    return units


def on_unit_header(S, um, fname, lineno):
    books = S['books']
    book = um.group('book')
    num = 0 if um.group('w') else int(um.group('n'))
    rest = um.group('rest') or ''
    cont = '续' in rest
    if book:
        m = BOOK_RE.search(book)
        name = ('选必' if m.group('pre') else '必修') + CN_NUM[m.group('n')]
        if name not in books:
            warn(fname, lineno, f'单元头册名 {name} 不在 {books}')
        else:
            S['bidx'] = books.index(name)
        S['cur'] = None
    cur = S['cur']
    if cur is not None and not book:
        if cont or num == cur['_num']:
            # 同一单元重复出现的标题（含“（续）”）：并入当前单元，保留小节状态
            if num != cur['_num']:
                warn(fname, lineno, '续标题单元号不一致')
            return
        if num > cur['_num']:
            pass
        else:
            S['bidx'] += 1
            if S['bidx'] >= len(books):
                warn(fname, lineno, '册数超出文件册列表，单元可能归错册')
                S['bidx'] = len(books) - 1
    if cur is not None and book and num == cur['_num'] and cont:
        return
    title = rest.replace('（续）', '').replace('(续)', '').strip(' 　…')
    U = {'册': books[S['bidx']],
         '单元': 'Welcome Unit' if num == 0 else f'Unit {num}',
         '标题': title, '序': None, '词汇': [], '句式': [], '语法': [],
         '_num': num, '_line': lineno}
    S['units'].append(U)
    S['cur'] = U
    S['part'] = S['sub'] = S['sent'] = S['gram'] = None


def on_part1(S, U, s, fname, lineno):
    if s.startswith('|'):
        if S['sub'] not in ('基础', None):
            return  # 探究/差距中的“易混词”小表不是基础词汇
        cells = [c.strip() for c in s.strip().strip('|').split('|')]
        if all(re.match(r'^-+$', c) for c in cells) or cells[:2] == ['词汇', '含义及拓展']:
            return
        if len(cells) % 2:
            warn(fname, lineno, f'表格行列数异常: {s[:40]}')
        for i in range(0, len(cells) - 1, 2):
            w, cell = cells[i], cells[i + 1]
            if not w or w == '词汇':
                continue
            w = re.sub(r'\s*<br>\s*', ' ', w)  # 词头格里的换行：如 “take up<br>a position”
            make_basic(U, w, cell, fname, lineno)
        return
    sub = S['sub']
    E = S.get('entry')
    ent_text = None
    if s.startswith('#'):
        content = s.lstrip('#').strip()
        if SENSE_START_RE.match(content):
            if E is not None:
                E['_senses'].append(content)
            else:
                warn(fname, lineno, f'释义行无归属词条: {s[:40]}')
            return
        if re.match(r'^(?:\d+[\.\s]\s*)?[A-Za-z]', content):
            ent_text = NUM_PREFIX_RE.sub('', content, count=1)
        elif sub is not None:
            warn(fname, lineno, f'小节内非词条标题: {s[:40]}')
    elif NUMBOLD_RE.match(s):
        nm = NUMBOLD_RE.match(s)
        ent_text = nm.group('in') + nm.group('rest')
    elif s.startswith('**'):
        core = s.replace('**', '').strip()
        if SENSE_START_RE.match(core):
            if E is not None:
                E['_senses'].append(core)
            else:
                warn(fname, lineno, f'释义行无归属词条: {s[:40]}')
            return
        m = re.match(r'^\*\*(?P<in>[^*]+?)\*\*(?P<rest>.*)$', s)
        if m and re.match(r'^(?:\d+[\.\s]\s*)?[A-Za-z]', m.group('in')) and label_kind(m.group('in')) is None:
            ent_text = NUM_PREFIX_RE.sub('', m.group('in'), count=1) + m.group('rest')
    if ent_text is not None:
        if sub is None:
            S['sub'] = sub = '探究'
            warn(fname, lineno, '词条出现于未标注小节处，按探究处理')
        E = new_entry(U, ent_text, sub, fname, lineno)
        S['entry'] = E
        return
    if sub == '基础':
        warn(fname, lineno, f'基础词汇中非表格内容: {s[:40]}')
        return
    if E is None:
        warn(fname, lineno, f'词条外内容: {s[:40]}')
        return
    parts = S.get('_parts') or [s]
    if len(parts) > 1:  # 词条内只用到标签块，逐物理行处理，避免相邻短语粘连
        for x in parts:
            feed_entry(E, x, fname)
    else:
        feed_entry(E, s, fname)


def add_text(obj, key, text):
    obj[key] = (obj[key] + '\n' + text) if obj[key] else text


def on_part2(S, U, s, fname, lineno):
    sub = S['sub']
    core = s.replace('**', '').strip()
    h = re.match(r'^(?:\*\*|#+\s*)?句[式型]\s*\d*\s*', s)
    if h:
        body = s.replace('**', '').lstrip('#').strip()
        body = re.sub(r'^句[式型]\s*\d*\s*', '', body).strip()
        item = {'类型': '长难句' if sub == '长难' else '高频句式', '句子': body, '说明': ''}
        U['句式'].append(item)
        S['sent'] = item
        return
    is_num = bool(ITEM_START_RE.match(core)) and sub != '高频'
    if is_num and not re.match(r'^\d+\.', core):
        # ①/❶ 类标记只有在英文长句上才开新条（中文“特别注意”里的 ② 是说明）
        body_txt = re.sub(r'^[' + CIRC + SENSE_MARKS + r']\s*', '', core)
        n_en = len(re.findall(r'[A-Za-z]', body_txt))
        n_cn = len(re.findall(f'[{CN_CHAR}]', body_txt))
        is_num = n_en >= 20 and n_en > 2 * n_cn
    # 长难句在引用块（> 开头）中给出时，英文句首即新条目；前一条已有句意时才开新条
    quoted_sentence = (sub == '长难' and S.get('_quoted_now', False)
                       and bool(re.match(r'^[A-Za-z]', core))
                       and (S['sent'] is None or '句意' in S['sent']['说明']))
    if is_num or quoted_sentence:
        sent = re.sub(r'^(?:\d+\.\s*|[' + CIRC + SENSE_MARKS + r']\s*)', '', core)
        sent = PAGE_REF_RE.sub('', sent).strip()
        item = {'类型': '长难句', '句子': sent, '说明': ''}
        U['句式'].append(item)
        S['sent'] = item
        return
    if S['sent'] is None:
        warn(fname, lineno, f'句式部分无归属内容: {s[:40]}')
        item = {'类型': '长难句' if sub == '长难' else '高频句式', '句子': '', '说明': ''}
        U['句式'].append(item)
        S['sent'] = item
    add_text(S['sent'], '说明', s)


def gram_title(s):
    t = s.lstrip('#').strip().strip('*').strip()
    return re.sub(r'^【?重点\s*\d*\s*】?\s*', '', t).strip()


def on_part3(S, U, s, fname, lineno):
    t = s.lstrip('#').strip().strip('*').strip()
    if (s.startswith('#') or s.startswith('**') or s.startswith('【')) and re.match(r'^【?重点', t):
        item = {'标题': gram_title(s), '正文': ''}
        U['语法'].append(item)
        S['gram'] = item
        return
    if S['gram'] is None:
        warn(fname, lineno, f'语法部分在“重点”之前出现内容: {s[:40]}')
        item = {'标题': '', '正文': ''}
        U['语法'].append(item)
        S['gram'] = item
    add_text(S['gram'], '正文', s)


# ---------------------------------------------------------------- 后处理与输出
def finalize(units):
    for n, U in enumerate(units, 1):
        U['序'] = n
        for E in U['词汇']:
            if E['_senses']:
                # 义项行（❶❷…）并入词性释义，保留原文顺序；标题已含释义时接在其后
                sense_txt = ' '.join(E['_senses'])
                E['词性释义'] = (E['词性释义'] + ' ' + sense_txt).strip() if E['词性释义'] else sense_txt
            for k in ('派生', '搭配', '近反义'):
                seen, uniq = set(), []
                for it in E[k]:
                    key = json.dumps(it, ensure_ascii=False, sort_keys=True)
                    if key not in seen:
                        seen.add(key)
                        uniq.append(it)
                E[k] = uniq
        for it in U['句式']:
            it['说明'] = it['说明'].strip()
        for g in U['语法']:
            g['正文'] = g['正文'].strip()
    out = []
    for U in units:
        out.append({
            '册': U['册'], '单元': U['单元'], '标题': U['标题'], '序': U['序'],
            '词汇': [{k: v for k, v in E.items() if not k.startswith('_')} for E in U['词汇']],
            '句式': U['句式'], '语法': U['语法'],
        })
    return out


STOP = {'a', 'an', 'the', 'of', 'to', 'in', 'on', 'at', 'for', 'with', 'by', 'from', 'up',
        'down', 'out', 'off', 'over', 'into', 'it', 'be', 'do', 'sb', 'sth', 'one', 'as',
        'and', 'or', 'that', 'if', 'is', 'not', 'so', 'than', 'about', 'through', 'away',
        'back', 'around', 'after', 'before', 'between', 'under', 'upon', 'i', 'me', 'my',
        'your', 'his', 'her', 'their', 'its', 'you', 'he', 'she', 'we', 'they', 'what',
        'how', 'there', 'this', 'these', 'those', 'all', 'some', 'any', 'no', 'more', 'most'}


def index_keys(head):
    base = re.sub(r'（[^）]*）|\([^)]*\)', '', head)
    base = base.replace('...', ' ').replace('..', ' ')
    base = re.sub(r'\s+', ' ', base).strip().lower()
    keys = set()
    if base:
        keys.add(base)
    words = re.findall(r"[a-z][a-z\-']*", base)
    if len(words) > 1:
        for w in words:
            if w not in STOP and len(w) > 1:
                keys.add(w)
    return keys


def build_index(units):
    idx = {}

    def put(key, U, E):
        if not key:
            return
        ref = {'序': U['序'], '册': U['册'], '单元': U['单元'], '词头': E['词']}
        lst = idx.setdefault(key, [])
        if ref not in lst:
            lst.append(ref)

    for U in units:
        for E in U['词汇']:
            for k in index_keys(E['词']):
                put(k, U, E)
            for d in E['派生']:
                put(d['词'].lower(), U, E)
    return dict(sorted(idx.items()))


def main():
    units = []
    for fname, books in SOURCES:
        units.extend(parse_file(fname, books))
    units = finalize(units)
    index = build_index(units)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / '单元.json').write_text(
        json.dumps(units, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (OUT_DIR / '词族索引.json').write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'units={len(units)} index_keys={len(index)} warnings={len(WARN)}', file=sys.stderr)
    for w in WARN:
        print('WARN ' + w, file=sys.stderr)


if __name__ == '__main__':
    main()
