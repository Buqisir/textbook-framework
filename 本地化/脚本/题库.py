#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""东莞单句语法语料 → 结构化题库。

用法（仓库根目录）：
    python3 -I 本地化/脚本/题库.py

输入：语料/东莞单句语法/*.md；语料/狂K重点/*.md（只读，用于拼写校对）；本地化/数据/卷号.json（卷号登记表，读写）。
输出：
    本地化/数据/题库.jsonl      每行一道题
    本地化/数据/学校简称.json   文件名中的学校全称 → 简称（含「（文件名无学校名）」→「东莞市」）
    本地化/数据/待校对.tsv      答案疑似拼写错的题（id、答案、提示词、题干）
    本地化/数据/卷号.json       卷号登记表（只在内容变化时写回；新文件登记后会写入）

只用标准库；同样的输入得到同样的输出（题按原文顺序，组号按首次出现顺序）。

[题号与卷号]
  题号 = 卷号（三位）-原卷题号（两位），如 005-15。卷号不再由排序序号现算，而是登记在 卷号.json：
    · 已登记的文件：用登记号。
    · 新文件（登记表里没有）：按文件名排序，依次取「当前最大号 + 1」，写回登记表。
    · 已登记、但文件已不存在：号保留，不复用、不删除。
  这样删除或新增语料文件时，其他卷的题号不变；定稿、选题结果里引用的题号才不会失效。
  卷号.json 的种子 = 2026-11-05 之前按文件名排序 enumerate 得到的序号（保证当时的题号一个不变）。
  「说明」字段随文件保留，脚本不改写。

================ 判定规则 ================

[文件名 → 元数据]
  年份：「YYYY-YYYY学年」时，上学期取第一年，下学期取第二年；学期为 null 时取第一年；
        写「YYYY年」时取 YYYY。
  学期：「高一上」「高一（下）」「第二学期」等 → 上/下；看不出 → null。
  年级：「高一」「高二」「高三」。
  考试：含「中段」「期中」→ 期中；含「期末」→ 期末；含「联考」→ 联考；其余（月考、段考、质检、
        期初、开学考、检测、检查、自查、测试……）→ 月考。
        考试原文：文件名中最具体的那个词（「第一次月考」「期初」「期中考试」）；
        「联考」与「月考」同时出现时写「联考+月考」。
  学校：按 SCHOOL_CANON 做子串匹配（长名优先，同一位置只取一次）；多校按文件名中的出现顺序用「、」连接。
        文件名里没有学校名的（市统考，以及只写「三校/五校/七校联考」未点名的）→「东莞市」。

[题目切分]
  「### 原卷第 N 题」开始一题；「**答案**：」前为题干；「**解析**：」后为解析，其中内嵌的
  【句意】【点评】【分析】【解答】按下文处理。「## 」大题标题只用于「疑似非单句题」的粗判，不用于题型。

[题干清洗]
  1. 去掉「(N分)」（独立成行或位于行首）。
  2. 空：NBSP（U+00A0）、全角空格（U+3000）、em 空格（U+2003）组成的空白串，以及下划线，统一为 ___。
     行尾的空白忽略；指令括号（如「（根据汉语提示…）」）前的空白是排版间距，不是空。
  3. 句首丢空：第一句英文若以小写字母开头，或以括号提示开头（如「(absorb) in …」「（watch）…」），
     说明句首的空被吞了 → 补「___ 」，标记「补句首空」。只处理句首，句中丢空无法可靠判断。

[题型]（按顺序判定，首条命中即定；不看 ## 标题）
  1. 单选：题干有 ≥2 行选项（A. B. C. D.）。
  2. 单词拼写：指令含「单词拼写」「首字母」。
  3. 完成句子：指令含「完成句子」。
  4. 翻译：题干中有整句中文的行（去掉括号与空后，中文 4–60 字，无小写英文词；允许人名），
     且题干不超过 160 字（更长的是书面表达或改错段落）。
  5. 完成句子：指令含改写类词语（同义/改写/转换/改为/合并/强调/从句/转被动/间接引语……）。
  6. 单词拼写 / 完成句子：空后紧跟中文提示；答案为一个词 → 单词拼写，多个词 → 完成句子。
  7. 语法填空：英文句中有空（有英文提示词，或无提示词、要填虚词/形式）。
  8. 其他：没有空、没有选项、也不是整句中文（如改错、英译汉、书面表达）。

  答案词数：取各「|」或「/」备选的最大词数；「；」分隔的各段计一词。

[提示词]：空后紧跟的英文括号内容（多个以 " / " 连接）；没有为 null。中文提示不入此字段，仍留在题干内。

[解析 / 句意 / 点评]
  「【句意】」→ 句意；无【句意】时，「【分析】」作句意（它是整句译文）；「【点评】」→ 点评；
  「【解答】」去掉标签并入解析；解析为「无」或空时为 null。【考点】等小标题留在解析正文中。

[重复组]：题干规范化（空记作占位符，去掉所有标点与空白，小写）相同的题共用一个组号（从 1 起，
          按首次出现顺序）；只出现一次的为 null。

[标记]
  补句首空     题干句首的空由脚本补上。
  疑似拼写错   答案中有长度 ≥4 的英文词，既不在 狂K重点 也不在任何题干中出现过。不自动改答案。
               注意：多数命中是屈折形式（如 delights、dragged），这是规则本身的噪声。
  疑似非单句题 满足任一：题干有两句以上英文或中文句子（不计缩写 Mr. 等，不计选项行）；
               题型为「其他」且题干超过 150 字；题型为「单选」或「其他」且所在大题（## 第X节 …）
               标题含 听力/阅读/完形/七选五/写作/改错/书面/语篇/短文。
  题型存疑     语法填空中，空后无英文提示词，且答案为多个词（空可能是短语，难以与完成句子区分）。
"""

import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SRC_DIR = os.path.join(ROOT, '语料', '东莞单句语法')
KH_DIR = os.path.join(ROOT, '语料', '狂K重点')
OUT_DIR = os.path.join(ROOT, '本地化', '数据')
VOL_PATH = os.path.join(OUT_DIR, '卷号.json')
VOL_NOTE = ('题号前三位为卷号，按文件名登记（规则见 题库.py docstring 的「题号与卷号」）。'
            '种子 = 2026-11-05 之前按文件名排序的序号；语料清洗前已删除的文件不在表中，其原号不再可考。'
            '文件删除后号保留、不复用。')

# ---------------------------------------------------------------- 常量

NB = '\xa0\u2003\u3000'  # NBSP / em space / ideographic space
BLANK_RE = re.compile(r'[ \t%s]*(?:[%s][ \t%s]*|_+[ \t%s_]*)' % (NB, NB, NB, NB))
PTS_RE = re.compile(r'^\s*[（(]\s*\d+(?:\.\d+)?\s*分\s*[）)]\s*')
OPT_RE = re.compile(r'^[A-D][.．、]')
CJK_RE = re.compile(r'[\u4e00-\u9fff]')
LAT_RE = re.compile(r'[A-Za-z]')
PAREN_RE = re.compile(r'[（(]([^（()）]*)[)）]')
# 指令类括号：题目要求，不是提示词
INSTR_KW = re.compile(
    r'填空|改写|转换|改为|改成|变为|合并|改简单句|同义|句型|翻译|拼写|完成句子|补全|所给词|适当|汉语提示|首字母|'
    r'倒装|复合|转述|强调|划线|从句|作状语|用[^）)]{0,12}(?:句|词|形式|结构|改写|合并|转换|从句|分词|不定式|介词)'
)
REWRITE_KW = re.compile(r'同义|改写|转换|改为|改成|变为|合并|改简单句|句型|倒装|转述|强调|从句|作状语|划线部分|'
                        r'转被动|被动语态|间接引语|变间接|转间接|放句首|加状语|作定语|作表语|分词|'
                        r'用[^）)]{0,12}改写|用[^）)]{0,12}合并')
SPELL_KW = re.compile(r'单词拼写|首字母')
COMPLETE_KW = re.compile(r'完成句子')
END_SENT_RE = re.compile(r'[.?!](?=\s+[A-Z"“])')
ABBR_BEFORE = {'Mr', 'Mrs', 'Ms', 'Dr', 'St', 'Jr', 'Sr', 'vs', 'No', 'a.m', 'p.m', 'etc', 'e.g', 'i.e'}
ALL_PAREN_RE = re.compile(r'[（(][^（()）]*[)）]')
CN_END_RE = re.compile(r'[。！？]')
# 大题标题关键词：只用于「疑似非单句题」的粗判，不用于题型
NONSINGLE_SEC_RE = re.compile(r'听力|阅读|完形|七选五|写作|改错|书面|语篇|短文')

# 学校全称（文件名中出现的形式）→ 讲义出处里的校名。长名优先匹配。
# 规则（2026-11-05 所有者定，取代旧的缩写规则）：只去掉「广东省东莞市」等地名前缀，保留学校本名，
# 老师一看就知道是哪所；「第X高级中学」补「东莞」；北京师范大学写作「北师大」。原「东华」「莞中」等缩写不再使用。
SCHOOL_CANON = [
    # spec 指定
    ('东华高级中学', '东华高级中学'),
    ('东莞中学', '东莞中学'),
    ('东莞实验中学', '东莞实验中学'),
    ('虎门外语学校', '虎门外国语学校'),
    ('虎门外国语学校', '虎门外国语学校'),
    ('石龙中学', '石龙中学'),
    ('光明中学', '光明中学'),
    ('南开实验学校', '南开实验学校'),
    ('北京师范大学东莞石竹附属学校', '北师大石竹附属学校'),
    ('莞美学校', '莞美学校'),
    # 按规则补充
    ('东华松山湖高级中学', '东华松山湖高级中学'),
    ('东华中学', '东华中学'),          # 文件 026，与「东华高级中学」是否同校待定，暂不合并
    ('东莞中学松山湖学校', '东莞中学松山湖学校'),
    ('东莞外国语学校', '东莞外国语学校'),
    ('东莞万江中学', '万江中学'),       # 与「万江中学」为同一所（文件 034 与 079–082）
    ('万江中学', '万江中学'),
    ('第一中学', '东莞第一中学'),
    ('第十中学', '东莞第十中学'),
    ('第五高级中学', '东莞第五高级中学'),
    ('第六高级中学', '东莞第六高级中学'),
    ('第八高级中学', '东莞第八高级中学'),
    ('第四高级中学', '东莞第四高级中学'),
    ('第十二高级中学', '东莞第十二高级中学'),
    ('东莞第二高级中学', '东莞第二高级中学'),
    ('东莞第四高级中学', '东莞第四高级中学'),
    ('东莞第八高级中学', '东莞第八高级中学'),
    ('东莞市高级中学', '东莞高级中学'),
    ('东莞高级中学', '东莞高级中学'),
    ('翰林高级中学', '翰林高级中学'),
    ('韩林高级中学', '翰林高级中学'),           # 文件 048 疑为「翰林」笔误，并入翰林并在报告中列出
    ('弘林高级中学', '弘林高级中学'),
    ('东莞弘林高级中学', '弘林高级中学'),
    ('东莞松山湖未来学校', '松山湖未来学校'),
    ('大岭山中学', '大岭山中学'),
    ('众美中学', '众美中学'),
    ('厚街中学', '厚街中学'),
    ('麻涌中学', '麻涌中学'),
    ('虎门中学', '虎门中学'),
    ('济川中学', '济川中学'),
    ('常平中学', '常平中学'),
    ('海逸外国语学校', '海逸外国语学校'),
    ('嘉荣外国语学校', '嘉荣外国语学校'),
    ('寮步镇外国语学校', '寮步外国语学校'),
    ('丰泰外国语', '丰泰外国语'),
    ('大朗佳美', '大朗佳美'),
    ('石竹实验学校', '石竹实验学校'),
    ('光正实验学校', '光正实验学校'),
    ('粤华学校', '粤华学校'),
    ('七中', '七中'),
    ('清溪', '清溪'),
    ('塘厦', '塘厦'),
]
SCHOOL_CANON.sort(key=lambda kv: -len(kv[0]))
SCHOOL_CANON_MAP = OrderedDict(SCHOOL_CANON)
NO_SCHOOL = '东莞市'
NO_SCHOOL_KEY = '（文件名无学校名）'

# ---------------------------------------------------------------- 文件元数据


def parse_semester(name):
    m = re.search(r'高[一二三][（(]?([上下])', name)
    if m:
        return m.group(1)
    m = re.search(r'第([一二])学期', name)
    if m:
        return '上' if m.group(1) == '一' else '下'
    m = re.search(r'([上下])学期', name)
    if m:
        return m.group(1)
    return None


def parse_grade(name):
    m = re.search(r'高([一二三])', name)
    return '高' + m.group(1) if m else None


EXAM_PRIORITY = [
    ('次', re.compile(r'第[一二三四五六七八九十\d]+次(?:月考|段考|考试|质检)')),
    ('specific', re.compile(r'期初考试|期初|开学考试|开学考|中段考试|段考|质检')),
    ('期中', re.compile(r'期中(?:考试|质量检测|教学质量自查|质量自查|测试|检测)?')),
    ('期末', re.compile(r'期末(?:考试|检查|测试|适应性考试|教学质量检查|质量检查|教学质量自查)?')),
    ('联考', re.compile(r'联考')),
    ('月考', re.compile(r'月考')),
    ('other', re.compile(r'学习效率检测|检测|考试|测试|检查|自查|适应性')),
]


def parse_exam(name):
    """返回 (考试, 考试原文)。"""
    if '中段' in name or '期中' in name:
        kind = '期中'
    elif '期末' in name:
        kind = '期末'
    elif '联考' in name:
        kind = '联考'
    else:
        kind = '月考'
    primary = None
    for _, rx in EXAM_PRIORITY:
        m = rx.search(name)
        if m:
            primary = m.group(0)
            break
    if primary is None:
        primary = ''
    if kind == '联考' and '月考' in name:
        primary = '联考+月考'
    return kind, primary


def parse_year(name, sem):
    m = re.search(r'(\d{4})\s*[-~～_－—–]\s*(\d{4})', name)
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        return y2 if sem == '下' else y1
    m = re.search(r'(\d{4})', name)
    return int(m.group(1)) if m else None


def parse_schools(name):
    """按文件名中的出现顺序返回 [(全称, 简称)]，同一位置只取最长匹配。"""
    hits = []
    used = [False] * len(name)
    for full, abbr in SCHOOL_CANON:
        start = 0
        while True:
            i = name.find(full, start)
            if i < 0:
                break
            if not any(used[i:i + len(full)]):
                for k in range(i, i + len(full)):
                    used[k] = True
                hits.append((i, full, abbr))
            start = i + len(full)
    hits.sort()
    return [(full, abbr) for _, full, abbr in hits]


def file_meta(fname):
    name = fname[:-3] if fname.endswith('.md') else fname
    sem = parse_semester(name)
    grade = parse_grade(name)
    year = parse_year(name, sem)
    kind, exam_raw = parse_exam(name)
    schools = parse_schools(name)
    if schools:
        abbrs = '、'.join(a for _, a in schools)
    else:
        abbrs = NO_SCHOOL
    return {
        '年份': year,
        '学校': abbrs,
        '学校全称': [f for f, _ in schools],
        '年级': grade,
        '学期': sem,
        '考试': kind,
        '考试原文': exam_raw,
    }


# ---------------------------------------------------------------- 题目切分


def split_blocks(text):
    """返回 [{'no', 'sec', 'stem', 'ans', 'exp'}]，按原文顺序。"""
    blocks = []
    cur = None
    mode = None
    sec = ''
    major = ''
    for raw in text.replace('\r\n', '\n').split('\n'):
        if raw.startswith('### '):
            m = re.match(r'### 原卷第\s*(\d+)\s*题', raw)
            cur = {'no': int(m.group(1)) if m else None, 'sec': (major + ' ' + sec).strip(),
                   'stem': [], 'ans': None, 'exp': []}
            blocks.append(cur)
            mode = 'stem'
            continue
        if raw.startswith('## '):
            sec = raw[3:].strip()
            if re.match(r'第[一二三四五六七八九十]+节', sec):
                major = sec
            cur = None
            mode = None
            continue
        if raw.startswith('# '):
            cur = None
            mode = None
            continue
        if cur is None:
            continue
        if raw.startswith('**答案**'):
            mode = 'ans'
            cur['ans'] = raw[len('**答案**'):].lstrip('：:').strip()
            continue
        if raw.startswith('**解析**'):
            mode = 'exp'
            cur['exp'].append(raw[len('**解析**'):].lstrip('：:'))
            continue
        if mode == 'stem':
            cur['stem'].append(raw)
        elif mode == 'exp':
            cur['exp'].append(raw)
    return blocks


def norm_nb(s):
    return s.replace('\xa0', ' ').replace('\u3000', ' ').replace('\u2003', ' ')


def clean_stem(lines):
    """返回 (题干行列表, 是否补了句首空)。"""
    out = []
    补 = False
    first_en_done = False
    for raw in lines:
        s = raw.rstrip(' \t' + NB)
        s = PTS_RE.sub('', s)
        # 行尾的「（根据汉语提示…）」等指令前的空白是排版间距，不是空
        s = re.sub(r'[ \t%s]+([（(][^（()）]*[)）])$' % NB,
                   lambda m: ' ' + m.group(1) if INSTR_KW.search(m.group(1)) else m.group(0), s)
        if not s.strip(' \t' + NB):
            continue
        if not first_en_done and LAT_RE.search(s) and not OPT_RE.match(s.strip()):
            first_en_done = True
            lead = s.lstrip(' \t' + NB)
            had_lead_blank = len(lead) != len(s)
            if not had_lead_blank:
                head = lead[:1]
                if head.islower() and head.isascii():
                    s = '___ ' + lead
                    补 = True
                elif head in '(（':
                    close = re.match(r'[（(][^）)]*[）)]', lead)
                    if close and LAT_RE.search(lead[close.end():]):
                        s = '___ ' + lead
                        补 = True
        out.append(s)
    cleaned = []
    for s in out:
        s = BLANK_RE.sub(' ___ ', s)
        s = re.sub(r' {2,}', ' ', s)
        s = re.sub(r'\s+([,.?!;:，。？！；：、])', r'\1', s)
        s = re.sub(r'___ +\(', '___ (', s)
        s = s.strip()
        if s:
            cleaned.append(s)
    return cleaned, 补


def count_en_sentence_breaks(line):
    """英文句间断点：句末标点后接空格加大写字母，忽略常见缩写（Mr. 等）。"""
    n = 0
    for m in END_SENT_RE.finditer(line):
        before = re.search(r'([A-Za-z.]+)$', line[:m.start()])
        if before and before.group(1).rstrip('.') in ABBR_BEFORE:
            continue
        if before and before.group(1) in ABBR_BEFORE:
            continue
        n += 1
    return n


def strip_instr_parens(text):
    def repl(m):
        return '' if INSTR_KW.search(m.group(0)) else m.group(0)
    return PAREN_RE.sub(repl, text)


def hints_after_blanks(text):
    """空后紧跟的括号内容（非指令）。返回 [原文括号内容]。"""
    res = []
    for m in re.finditer(r'___\s*[（(]([^（()）]*)[)）]', text):
        inner = m.group(1).strip()
        if inner and not INSTR_KW.search(inner):
            res.append(inner)
    return res


def is_cn_only(line):
    """整句中文：去掉括号（提示与要求）和空后，中文字符 ≥4，且无小写英文单词（允许人名等首字母大写的词）。"""
    s = BLANK_RE.sub(' ', line)
    s = re.sub(r'[（(][^（()）]*[)）]', ' ', s)
    words = [w for w in re.findall(r'[A-Za-z]{2,}', s) if not w[0].isupper()]
    n = len(CJK_RE.findall(s))
    return 4 <= n <= 60 and not words  # 超过 60 字的多半是指令段落，不是待译句


def classify(stem_lines, ans):
    """返回 (题型, 提示词列表, 标记集合)。"""
    text = '\n'.join(stem_lines)
    stem_text_all = text
    flags = set()
    option_lines = [l for l in stem_lines if OPT_RE.match(l)]
    has_opts = len(option_lines) >= 2 or (len(option_lines) >= 1 and re.fullmatch(r'[A-D]', ans or '') is not None)
    has_blank = '___' in text
    hints = hints_after_blanks(text)
    en_hints = [h for h in hints if LAT_RE.search(h) and not CJK_RE.search(h)]
    cn_hints = [h for h in hints if CJK_RE.search(h)]
    instr_text = ' '.join(m.group(0) for m in PAREN_RE.finditer(text))
    # 答案的词数：取第一个备选（「|」分隔的备选不计），「；」分隔的各段计为词或空
    alts = [a.strip() for a in re.split(r'\s*[|/]\s*', ans or '') if a.strip()] or ['']
    ans_count = max(len([t for t in re.split(r'\s*；\s*', a) if t]) if '；' in a else len(a.split()) for a in alts)
    single_word_ans = ans_count == 1
    cn_line = any(is_cn_only(l) for l in stem_lines)

    if has_opts:
        return '单选', en_hints, flags
    if SPELL_KW.search(text):
        return '单词拼写', en_hints, flags
    if COMPLETE_KW.search(text):
        return '完成句子', en_hints, flags
    short = len(stem_text_all) <= 160  # 书面表达、改错段落等长篇指令不是待译句
    if cn_line and short:
        return '翻译', en_hints, flags
    if cn_line and not short:
        return '其他', en_hints, flags
    if REWRITE_KW.search(instr_text):
        return '完成句子', en_hints, flags
    if has_blank and cn_hints:
        return ('单词拼写' if single_word_ans else '完成句子'), en_hints, flags
    if has_blank:
        if not en_hints and ans_count > 1:
            flags.add('题型存疑')
        return '语法填空', en_hints, flags
    return '其他', en_hints, flags


# ---------------------------------------------------------------- 解析 / 句意 / 点评

MARK_RE = re.compile(r'(【句意】|【点评】|【分析】|【解答】)')


def split_explanation(exp_lines):
    raw = norm_nb('\n'.join(exp_lines)).strip()
    parts = MARK_RE.split(raw)
    body = [parts[0].strip()]
    seg = {'【句意】': [], '【点评】': [], '【分析】': []}
    for i in range(1, len(parts) - 1, 2):
        label, content = parts[i], parts[i + 1].strip()
        if label == '【解答】':
            body.append(content)
        else:
            seg[label].append(content)
    jieyi = ' '.join(x for x in seg['【句意】'] if x) or ' '.join(x for x in seg['【分析】'] if x) or None
    dianping = ' '.join(x for x in seg['【点评】'] if x) or None
    jiexi = '\n'.join(x for x in body if x).strip()
    if jiexi in ('', '无'):
        jiexi = None
    return jiexi, jieyi, dianping


# ---------------------------------------------------------------- 拼写校对


def word_tokens(s):
    return [t.lower().replace('’', "'") for t in re.findall(r"[A-Za-z]+(?:['’][A-Za-z]+)*", s)]


def load_known_words(stems_text):
    known = set()
    for fn in sorted(os.listdir(KH_DIR)):
        if fn.endswith('.md'):
            with open(os.path.join(KH_DIR, fn), encoding='utf-8') as f:
                known.update(word_tokens(f.read()))
    known.update(word_tokens(stems_text))
    return known


# ---------------------------------------------------------------- 主流程


def load_volumes():
    """读 卷号.json → (登记表 {文件名: 号}, 说明)。文件不存在时为空表。"""
    if not os.path.exists(VOL_PATH):
        return {}, VOL_NOTE
    with open(VOL_PATH, encoding='utf-8') as f:
        obj = json.load(f)
    reg = {fn: int(n) for fn, n in obj.get('卷号', {}).items()}
    dup = sorted(n for n, c in Counter(reg.values()).items() if c > 1)
    if dup:
        sys.exit(f'卷号.json 有重复的号 {dup}，请人工修正后再运行')
    return reg, obj.get('说明', VOL_NOTE)


def assign_volumes(files, reg):
    """files：当前语料的 .md 文件名（已排序）。返回 (本次文件名 → 号, 新登记表)。
    已登记的用登记号；新文件按「登记表最大号 + 1」依次登记（登记表含已删除文件的号，号不复用）。"""
    new = dict(reg)
    nxt = max(reg.values(), default=0) + 1
    for fn in files:
        if fn not in new:
            new[fn] = nxt
            nxt += 1
    return {fn: new[fn] for fn in files}, new


def write_volumes(reg, note):
    """写回 卷号.json；内容与现有文件逐字相同则不写。返回是否写入。"""
    obj = {'卷号': {fn: reg[fn] for fn in sorted(reg, key=lambda k: (reg[k], k))}, '说明': note}
    text = json.dumps(obj, ensure_ascii=False, indent=2) + '\n'
    old = None
    if os.path.exists(VOL_PATH):
        with open(VOL_PATH, encoding='utf-8') as f:
            old = f.read()
    if old == text:
        return False
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(VOL_PATH, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    return True


def norm_key(stem_text):
    s = stem_text.replace('___', 'BLANKX').lower()
    out = []
    for ch in s:
        cat = unicodedata.category(ch)
        if cat[0] in 'LN':
            out.append(ch)
    return ''.join(out).replace('blankx', 'B')


def main():
    files = sorted(f for f in os.listdir(SRC_DIR) if f.endswith('.md'))
    reg, note = load_volumes()
    vol_of, reg_new = assign_volumes(files, reg)
    records = []
    school_used = OrderedDict()
    all_stem_text = []
    per_file_meta = {}
    empty_files = []

    for fn in files:
        fi = vol_of[fn]
        meta = file_meta(fn)
        per_file_meta[fn] = meta
        for full in meta['学校全称']:
            school_used[full] = SCHOOL_CANON_MAP[full]
        if not meta['学校全称']:
            school_used.setdefault(NO_SCHOOL_KEY, NO_SCHOOL)
        with open(os.path.join(SRC_DIR, fn), encoding='utf-8') as f:
            text = f.read()
        blocks = split_blocks(text)
        if not blocks:
            empty_files.append(fn)
            continue
        for b in blocks:
            stem_lines, filled = clean_stem(b['stem'])
            all_stem_text.append('\n'.join(stem_lines))
            records.append({'fi': fi, 'fn': fn, 'meta': meta, 'no': b['no'], 'sec': b['sec'], 'stem_lines': stem_lines,
                            'filled': filled, 'ans': norm_nb(b['ans'] or '').strip(), 'exp': b['exp']})

    known = load_known_words('\n'.join(all_stem_text))

    # 组号
    keys = [norm_key('\n'.join(r['stem_lines'])) for r in records]
    key_count = Counter(keys)
    group_ids = {}
    next_gid = 1
    for k in keys:
        if key_count[k] > 1 and k not in group_ids:
            group_ids[k] = next_gid
            next_gid += 1

    rows = []
    typo_rows = []
    id_seen = Counter()
    for r, k in zip(records, keys):
        meta = r['meta']
        stem_lines = r['stem_lines']
        ans = r['ans']
        qtype, en_hints, flags = classify(stem_lines, ans)
        if r['filled']:
            flags.add('补句首空')
        jiexi, jushi, dianping = split_explanation(r['exp'])
        # 疑似非单句题
        stem_text = '\n'.join(stem_lines)
        plain = strip_instr_parens(stem_text)
        non_opt = [l for l in stem_lines if not OPT_RE.match(l)]
        multi_en = any(count_en_sentence_breaks(strip_instr_parens(l)) >= 1 for l in non_opt)
        multi_cn = any(re.search(r'[。！？][\u4e00-\u9fff]', ALL_PAREN_RE.sub('', l)) for l in non_opt)
        multi = multi_en or multi_cn
        heading_flag = qtype in ('单选', '其他') and bool(NONSINGLE_SEC_RE.search(r['sec']))
        if (qtype == '其他' and len(plain) > 150) or multi or heading_flag:
            flags.add('疑似非单句题')
        # 疑似拼写错
        ans_words = [w for w in word_tokens(ans) if len(w) >= 4]
        bad = [w for w in ans_words if w not in known]
        if bad:
            flags.add('疑似拼写错')
        # 提示词
        hint_str = ' / '.join(en_hints) if en_hints else None
        # 标签
        sem = meta['学期']
        grade = meta['年级'] or ''
        if sem:
            tag_tail = f"{grade}{sem}{meta['考试']}"
        else:
            tag_tail = f"{grade}{meta['考试']}"
        tag = f"{meta['年份']} · {meta['学校']} · {tag_tail}"
        id_base = f"{r['fi']:03d}-{r['no']:02d}"
        id_seen[id_base] += 1
        qid = id_base if id_seen[id_base] == 1 else f"{id_base}-{id_seen[id_base]}"
        row = OrderedDict([
            ('id', qid),
            ('文件', r['fn']),
            ('年份', meta['年份']),
            ('学校', meta['学校']),
            ('年级', meta['年级']),
            ('学期', sem),
            ('考试', meta['考试']),
            ('考试原文', meta['考试原文']),
            ('标签', tag),
            ('题型', qtype),
            ('题干', stem_text),
            ('提示词', hint_str),
            ('答案', ans),
            ('解析', jiexi),
            ('句意', jushi),
            ('点评', dianping),
            ('重复组', group_ids.get(k)),
            ('标记', [f for f in ['补句首空', '疑似拼写错', '疑似非单句题', '题型存疑'] if f in flags]),
        ])
        rows.append(row)
        if bad:
            typo_rows.append((row, bad))

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, '题库.jsonl'), 'w', encoding='utf-8', newline='\n') as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')

    with open(os.path.join(OUT_DIR, '学校简称.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(school_used, f, ensure_ascii=False, indent=2)
        f.write('\n')

    with open(os.path.join(OUT_DIR, '待校对.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('id\t答案\t提示词\t题干\n')
        for row, bad in typo_rows:
            stem_one = row['题干'].replace('\n', ' / ').replace('\t', ' ')
            ans_one = row['答案'].replace('\t', ' ')
            f.write(f"{row['id']}\t{ans_one}\t{row['提示词'] or ''}\t{stem_one}\n")

    vol_written = write_volumes(reg_new, note)

    summary = {
        'files': len(files),
        'empty_files': empty_files,
        'questions': len(rows),
        'typo_rows': len(typo_rows),
        'groups': next_gid - 1,
        '卷号新增': len(reg_new) - len(reg),
        '卷号写回': vol_written,
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
